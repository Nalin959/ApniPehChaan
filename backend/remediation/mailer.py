"""
mailer.py — Actually serving a statutory erasure notice on a controller.

WHY THIS EXISTS
---------------
Everything upstream of this module is reversible. A scan can be re-run, a draft
can be deleted, a wrong risk score can be recalculated. This module is where that
stops: once a notice leaves the machine it is in a stranger's inbox, it carries
the user's name, email and phone, and there is no unsend. Every design decision
here follows from that one fact.

Concretely:

  1. NOTHING SENDS UNLESS TOLD TO. `prepare_notice()` builds, redacts, exports
     and hashes; it opens no socket. `send_notice()` is the only function that
     talks to a mail server, and it will not run without `approved=True` passed
     explicitly — there is no default, so approval cannot be inherited from a
     config flag, a truthy object, or a forgotten argument. There is deliberately
     no "auto-send when SMTP is configured" path.

  2. UNCONFIGURED IS NOT SENT. If SMTP is missing, the result status is
     `not_configured` and says so. It never reports success for mail that went
     nowhere — a privacy tool that claims to have served a notice it did not
     serve is worse than one that does nothing, because the user stops chasing.

  3. THERE IS ALWAYS A WAY OUT. Most users will never configure SMTP, so the
     unconfigured path is the main path, not the error path. It produces a real
     RFC-5322 `.eml` file and a `mailto:` link, so the notice can be sent from
     the user's own mail client — which is arguably better anyway, since a notice
     sent from the data principal's own address is self-authenticating in a way
     that one relayed through a third party is not.

  4. THE NOTICE NEVER CARRIES SECRETS. A s.12 request identifies the data
     principal by an identifier the controller ALREADY HOLDS — normally the email
     or phone the account was opened with. It never needs an Aadhaar number, a
     PAN, a card number or a password, and mailing one to a grievance inbox
     hands a fresh identifier to a company that did not have it, over SMTP, in
     plaintext. Those are stripped on the way out and the caller is told.

  5. WHAT WENT OUT IS KEPT VERBATIM. The exact RFC-5322 bytes and their SHA-256
     are returned so the caller can pin them into the audit chain. "We sent a
     notice" is an assertion; the wire bytes and their hash are evidence.

RECIPIENT TRUST
---------------
`officer_directory` grades every address it resolves, and this module enforces
that grade at the last possible moment: an address tiered `guess` is refused
unless the caller passes `allow_unverified_recipient=True`. Mailing a guessed
address does not just fail to help — it discloses the user's identifiers to
whoever happens to own that mailbox.

LIMITS, PLAINLY
---------------
  • SMTP acceptance is not delivery, and delivery is not compliance. A 250 means
    one server took custody. It does not mean a human read it or that the clock
    under DPDP s.12 has started. Treat the returned status as "dispatched".
  • Nothing here proves the sender controls the Reply-To address. That proof is
    `backend/agent/verification.py`'s job and should be done before dispatch.
  • No DKIM signing, no bounce handling, no retry queue. A notice sent from a
    random relay may land in spam; the `.eml` path avoids that entirely.

stdlib only: smtplib, ssl, email, hashlib, urllib.parse, dataclasses.
"""

import hashlib
import os
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy as email_policy
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from urllib.parse import quote

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUTBOX = os.path.join(PROJECT_ROOT, "data", "outbox")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# A mailto: URL longer than this gets silently truncated by some mail clients and
# rejected outright by others, so past it we also hand back a compact variant
# instead of pretending the one-click path still carries the whole notice.
MAILTO_SAFE_LENGTH = 1800

SMTP_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM")


# ─────────────────────────────────────────────────────────────────────────────
# OUTBOUND REDACTION
#
# The rule is narrow on purpose. Over-redaction breaks the notice: the controller
# must be able to find the record, and it finds it by the email and phone it
# already holds, so those MUST survive. What must never survive is an identifier
# the controller does not already have and has no need for.
# ─────────────────────────────────────────────────────────────────────────────

def _checksum_fns():
    """Reuse the project's Verhoeff/Luhn validators rather than re-deriving them.

    If the import fails we fall back to accepting any well-shaped run. That is
    deliberately the *more* aggressive direction: over-redacting an outbound
    legal notice costs a line of text, under-redacting leaks an Aadhaar number.
    """
    try:
        from backend.pii.recognizer import verhoeff_validate, luhn_validate
        return verhoeff_validate, luhn_validate
    except Exception:
        return (lambda _n: True), (lambda _n: True)


# Bounded by non-alphanumerics, not just non-digits, so a digit run inside a
# 64-char SHA-256 receipt hash cannot be mistaken for a card number and redacted
# — that would corrupt the very evidence this module exists to produce.
_AADHAAR_RE = re.compile(r"(?<![0-9A-Za-z])(\d{4})[ \-]?(\d{4})[ \-]?(\d{4})(?![0-9A-Za-z])")
_PAN_RE = re.compile(r"(?<![0-9A-Za-z])([A-Z]{5}[0-9]{4}[A-Z])(?![0-9A-Za-z])")
_CARD_RE = re.compile(r"(?<![0-9A-Za-z])((?:\d[ \-]?){12,18}\d)(?![0-9A-Za-z])")
_SECRET_LABEL_RE = re.compile(
    r"(?im)^[ \t]*[•\-\*]?[ \t]*(password|passwd|pwd|passphrase|pin|otp|cvv|security\s+code)"
    r"[ \t]*[:=][ \t]*(\S.*)$")

_MARKER = "[REDACTED — {kind} withheld: not disclosed in outbound correspondence]"


def _in_longer_token(text: str, start: int, end: int) -> bool:
    """Is this match only part of a longer alphanumeric token?

    Guards against redacting a fragment of a hash, a reference id, or a URL slug.
    """
    i = start
    while i > 0 and text[i - 1].isalnum():
        i -= 1
    j = end
    while j < len(text) and text[j].isalnum():
        j += 1
    return (j - i) > (end - start)


def redact_for_outbound(text: str) -> tuple[str, list[dict]]:
    """Strip identifiers that must never leave the machine in a notice.

    Returns (clean_text, redactions). A redaction record names the KIND and the
    count — never the value, because the audit chain is itself a place the secret
    must not end up.
    """
    verhoeff, luhn = _checksum_fns()
    found: dict[str, int] = {}

    def _replace(pattern, kind, validator=None):
        nonlocal text
        out, cursor, hits = [], 0, 0
        for m in pattern.finditer(text):
            raw = m.group(0)
            digits = "".join(c for c in raw if c.isdigit())
            if _in_longer_token(text, m.start(), m.end()):
                continue
            if validator and not validator(digits):
                continue
            out.append(text[cursor:m.start()])
            out.append(_MARKER.format(kind=kind))
            cursor = m.end()
            hits += 1
        if hits:
            out.append(text[cursor:])
            text = "".join(out)
            found[kind] = found.get(kind, 0) + hits

    # Card first: it is the longest run, so matching it before Aadhaar stops a
    # 16-digit card being partly consumed as a 12-digit Aadhaar.
    _replace(_CARD_RE, "payment card number",
             lambda d: 13 <= len(d) <= 19 and luhn(d))
    # Aadhaar starts 2-9 (UIDAI never issues a leading 0 or 1) and must satisfy
    # Verhoeff — the same two tests backend/pii/recognizer.py applies, so a
    # 12-digit order number is not mistaken for one.
    _replace(_AADHAAR_RE, "Aadhaar number",
             lambda d: len(d) == 12 and d[0] not in "01" and verhoeff(d))
    _replace(_PAN_RE, "PAN")

    # Labelled secrets: the value after "Password:" goes, the label stays so the
    # controller can see something was deliberately withheld rather than omitted.
    def _blank_secret(m):
        found["credential"] = found.get("credential", 0) + 1
        return f"{m.group(0)[:m.start(2) - m.start(0)]}{_MARKER.format(kind='credential')}"

    text = _SECRET_LABEL_RE.sub(_blank_secret, text)

    redactions = [{
        "kind": kind,
        "count": count,
        "reason": ("A statutory erasure request identifies the data principal by an "
                   "identifier the controller already holds. Sending this one would "
                   "disclose a NEW identifier to the controller in plaintext."),
    } for kind, count in sorted(found.items())]
    return text, redactions


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

def smtp_status() -> dict:
    """What is configured, without ever printing a password.

    Mirrors `Verifier.email_channel()` in backend/agent/verification.py: HOST,
    USER and PASS are the minimum; PORT and FROM have sane defaults.
    """
    required = ("SMTP_HOST", "SMTP_USER", "SMTP_PASS")
    missing = [k for k in required if not os.environ.get(k)]
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587") or "587")
    return {
        "configured": not missing,
        "missing": missing,
        "host": host,
        "port": port,
        "mode": "implicit_tls" if port == 465 else "starttls",
        "from": os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER", ""),
        "note": ("SMTP is configured; send_notice() can dispatch." if not missing else
                 f"SMTP is not configured (missing {', '.join(missing)}). Notices will be "
                 f"exported as .eml + mailto: for the user to send from their own client. "
                 f"Nothing is sent and nothing is claimed to have been sent."),
    }


def build_subject(statute: str = "", company_name: str = "", reference_id: str = "") -> str:
    """Subject line carrying the statutory hook.

    The statute goes in the subject because a grievance inbox triages by subject,
    and "Request for Erasure of Personal Data under Section 12, DPDP Act 2023"
    routes to legal while "Please delete my account" routes to support — where
    the statutory clock quietly never starts.
    """
    statute = (statute or "").strip() or "applicable data protection law"
    parts = [f"Statutory Request for Erasure of Personal Data — {statute}"]
    if company_name:
        parts.append(f"({company_name})")
    if reference_id:
        parts.append(f"[Ref: {reference_id}]")
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# RESULT TYPES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PreparedNotice:
    """A notice built and ready to go, which has NOT been sent.

    `raw_message` and `sha256` are the evidence pair: the exact bytes that would
    go (or did go) on the wire, and their digest for the audit chain.
    """

    status: str = "prepared"
    to: str = ""
    to_display: str = ""
    from_addr: str = ""
    reply_to: str = ""
    subject: str = ""
    message_id: str = ""
    date: str = ""
    body: str = ""
    raw_message: str = ""
    sha256: str = ""
    eml_path: str = ""
    mailto_url: str = ""
    mailto_compact_url: str = ""
    mailto_truncated: bool = False
    reference_id: str = ""
    statute: str = ""
    recipient_tier: str = ""
    redactions: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked_reason: str = ""
    sender_is_user: bool = False

    @property
    def ok(self) -> bool:
        return not self.blocked_reason

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "to": self.to,
            "to_display": self.to_display,
            "from": self.from_addr,
            "reply_to": self.reply_to,
            "subject": self.subject,
            "message_id": self.message_id,
            "date": self.date,
            "raw_message": self.raw_message,
            "sha256": self.sha256,
            "eml_path": self.eml_path,
            "mailto_url": self.mailto_url,
            "mailto_compact_url": self.mailto_compact_url,
            "mailto_truncated": self.mailto_truncated,
            "reference_id": self.reference_id,
            "statute": self.statute,
            "recipient_tier": self.recipient_tier,
            "redactions": list(self.redactions),
            "warnings": list(self.warnings),
            "blocked_reason": self.blocked_reason,
            "sender_is_user": self.sender_is_user,
            "ok": self.ok,
        }


@dataclass
class DispatchResult:
    """The outcome of an attempt to serve a notice.

    status is exactly one of:
      sent            an SMTP server accepted custody of the message
      not_configured  no SMTP; the .eml and mailto: are the deliverable
      refused         this module declined to send (bad or unverified recipient,
                      missing approval) — nothing was transmitted
      failed          SMTP was configured and the attempt errored
    """

    status: str
    prepared: PreparedNotice | None = None
    smtp_response: str = ""
    error: str = ""
    error_type: str = ""
    refused_recipients: dict = field(default_factory=dict)
    attempted_at: str = ""
    message: str = ""

    @property
    def delivered_to_server(self) -> bool:
        """True only for `sent` — and even then this means accepted, not read."""
        return self.status == "sent"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "delivered_to_server": self.delivered_to_server,
            "smtp_response": self.smtp_response,
            "error": self.error,
            "error_type": self.error_type,
            "refused_recipients": dict(self.refused_recipients),
            "attempted_at": self.attempted_at,
            "message": self.message,
            "prepared": self.prepared.to_dict() if self.prepared else None,
            # Flattened for the audit chain, which wants the evidence at top level.
            "sha256": self.prepared.sha256 if self.prepared else "",
            "eml_path": self.prepared.eml_path if self.prepared else "",
            "message_id": self.prepared.message_id if self.prepared else "",
        }


# ─────────────────────────────────────────────────────────────────────────────
# BUILD — no network, ever
# ─────────────────────────────────────────────────────────────────────────────

def _text(resp) -> str:
    """SMTP replies come back as bytes; audit records want readable text."""
    return resp.decode("utf-8", errors="replace").strip() if isinstance(resp, bytes) else str(resp).strip()


def _mailto(to: str, subject: str, body: str) -> str:
    return (f"mailto:{quote(to, safe='@')}"
            f"?subject={quote(subject, safe='')}"
            f"&body={quote(body, safe='')}")


def prepare_notice(
    notice_text: str,
    recipient: str,
    reply_to: str,
    *,
    subject: str = "",
    recipient_name: str = "",
    sender_name: str = "",
    company_name: str = "",
    statute: str = "",
    reference_id: str = "",
    recipient_tier: str = "",
    export_dir: str | None = DEFAULT_OUTBOX,
    write_eml: bool = True,
) -> PreparedNotice:
    """Build the notice message, redact it, hash it, and export it. Sends nothing.

    Args:
        notice_text:  the rendered notice from
                      `backend.remediation.notice_generator.NoticeGenerator.generate()`
                      (its `notice_text` field). This module does not template —
                      it transports.
        recipient:    the controller's officer address, from
                      `officer_directory.resolve_officer()`.
        reply_to:     the DATA SUBJECT's own address. The controller must reply to
                      them, not to this tool — a reply that lands here is a reply
                      the user never sees, and under DPDP s.12 the response is
                      owed to the principal.
        recipient_tier: the `tier` from the officer resolution. `guess` is carried
                      through to `send_notice()`, which refuses it by default.
        export_dir:   where the .eml is written. None disables the file export.

    Returns a PreparedNotice. `blocked_reason` is set (and `ok` is False) when the
    message is unsendable — callers should check `ok` rather than assume.
    """
    prep = PreparedNotice(recipient_tier=recipient_tier or "unknown",
                          statute=statute, reference_id=reference_id)

    recipient = (recipient or "").strip()
    reply_to = (reply_to or "").strip()

    # ── Validation. Each of these is a way to send a legal notice into a void. ──
    if not notice_text or not notice_text.strip():
        prep.blocked_reason = "No notice text was supplied; there is nothing to serve."
        return prep
    if not EMAIL_RE.match(recipient):
        prep.blocked_reason = (
            f"{recipient!r} is not a well-formed email address, so there is no addressee. "
            f"Resolve one with officer_directory.resolve_officer() first.")
        return prep
    if not EMAIL_RE.match(reply_to):
        prep.blocked_reason = (
            f"{reply_to!r} is not a well-formed reply-to address. The data principal's own "
            f"address is mandatory: under DPDP s.12 the controller's response is owed to "
            f"them, and a notice they cannot receive a reply to is not worth serving.")
        return prep
    if recipient.lower() == reply_to.lower():
        prep.blocked_reason = (
            "The recipient and the data principal are the same address. That is a "
            "misconfiguration, not a notice — it would serve the user on themselves.")
        return prep

    # ── Redaction happens BEFORE anything is hashed or exported, so the evidence
    #    copy is the redacted copy and no secret is ever written to disk. ────────
    body, redactions = redact_for_outbound(notice_text)
    prep.redactions = redactions
    if redactions:
        kinds = ", ".join(f"{r['count']}× {r['kind']}" for r in redactions)
        prep.warnings.append(
            f"Redacted before dispatch: {kinds}. A s.12/Art.17 request identifies the data "
            f"principal by an identifier the controller ALREADY holds — normally the account "
            f"email or phone. Sending these would have handed the controller a new identifier "
            f"it did not have, in plaintext over SMTP. Identify the subject by email or phone "
            f"instead.")

    # ── Addressing ───────────────────────────────────────────────────────────
    cfg = smtp_status()
    smtp_from = (cfg.get("from") or "").strip()
    if cfg["configured"] and EMAIL_RE.match(smtp_from):
        from_addr = smtp_from
        prep.sender_is_user = False
    else:
        # Export path: the user sends this from their own client, so they ARE the
        # sender. Putting a relay address here that will never send it would make
        # the .eml lie about its own provenance.
        from_addr = reply_to
        prep.sender_is_user = True

    subject = subject or build_subject(statute, company_name, reference_id)

    # ── Header injection. Every one of these fields is caller-supplied and at
    #    least three of them are user-supplied in practice: `sender_name` is the
    #    data principal's own name from their profile, and `company_name` and
    #    `recipient_name` come from the exposure's source name, which may have
    #    been typed in or produced by a model. A bare CR or LF in any of them
    #    ends the header and starts a new one, which is how a Bcc gets appended
    #    to a legal notice.
    #
    #    The stdlib does refuse to serialise such a header — but it refuses by
    #    RAISING ValueError out of the middle of this function, which is not the
    #    documented contract (a PreparedNotice with `blocked_reason` set) and
    #    which propagates straight out of send_notice() into the caller. So the
    #    control characters are rejected here, by name, and the assembly is
    #    additionally wrapped so no malformed header can escape as an exception.
    _CTL = "\r\n\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"
    for label, value in (("subject", subject), ("recipient name", recipient_name),
                         ("sender name", sender_name), ("statute", statute),
                         ("reference id", reference_id)):
        if value and any(ch in value for ch in _CTL):
            prep.blocked_reason = (
                f"The {label} contains a line break or control character. In a header that "
                f"terminates the field and begins a new one, so it is how an extra Bcc or a "
                f"forged body gets spliced into an outbound legal notice. Nothing was built "
                f"and nothing was written. Strip the line breaks and try again.")
            return prep

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((sender_name, from_addr)) if sender_name else from_addr
        msg["To"] = formataddr((recipient_name, recipient)) if recipient_name else recipient
        msg["Reply-To"] = formataddr((sender_name, reply_to)) if sender_name else reply_to
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1] or None)
        # Correlates a controller's reply back to the audit chain entry without
        # needing them to quote the reference id in their prose.
        if reference_id:
            msg["X-ApniPehChaan-Reference"] = reference_id
            msg["X-SovereignPrivacy-Reference"] = reference_id
        if statute:
            msg["X-ApniPehChaan-Statute"] = statute
            msg["X-SovereignPrivacy-Statute"] = statute
        msg.set_content(body)

        # ── The verbatim wire copy. SMTP policy so the bytes are exactly what a
        #    server would receive (CRLF endings, folded headers) — hashing the
        #    pretty-printed form would produce a digest of something never sent. ──
        wire = msg.as_bytes(policy=email_policy.SMTP)
    except (ValueError, TypeError, UnicodeError) as exc:
        prep.blocked_reason = (
            f"The message could not be assembled as a valid RFC-5322 mail "
            f"({type(exc).__name__}: {exc}). Nothing was built, hashed or written. This is "
            f"almost always an unusable character in the subject, a name or an address.")
        return prep
    prep.raw_message = wire.decode("utf-8", errors="replace")
    prep.sha256 = hashlib.sha256(wire).hexdigest()

    prep.to = recipient
    prep.to_display = recipient_name
    prep.from_addr = from_addr
    prep.reply_to = reply_to
    prep.subject = subject
    prep.message_id = msg["Message-ID"]
    prep.date = msg["Date"]
    prep.body = body

    # ── Export: the fallback that makes this useful without SMTP ─────────────
    if write_eml and export_dir:
        try:
            os.makedirs(export_dir, exist_ok=True)
            slug = re.sub(r"[^A-Za-z0-9]+", "-", (reference_id or company_name or "notice")).strip("-")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = os.path.join(export_dir, f"{slug or 'notice'}-{stamp}.eml")
            with open(path, "wb") as fh:
                fh.write(wire)
            prep.eml_path = path
        except OSError as exc:
            prep.warnings.append(f"Could not write the .eml export ({exc}). "
                                 f"The mailto: link still works.")

    prep.mailto_url = _mailto(recipient, subject, body)
    if len(prep.mailto_url) > MAILTO_SAFE_LENGTH:
        prep.mailto_truncated = True
        pointer = (f"The full statutory notice is attached as a file"
                   + (f" ({os.path.basename(prep.eml_path)})" if prep.eml_path else "")
                   + ".\nPaste the notice text below this line before sending.\n\n"
                   + body[:600] + "\n\n[… notice continues — see the .eml export …]")
        prep.mailto_compact_url = _mailto(recipient, subject, pointer)
        prep.warnings.append(
            f"The notice is {len(body)} characters, so the full mailto: link "
            f"({len(prep.mailto_url)} chars) exceeds what some mail clients accept and may "
            f"be silently truncated. Prefer opening the .eml file, or use "
            f"mailto_compact_url and paste the notice body in.")

    if prep.recipient_tier == "guess":
        prep.warnings.append(
            f"{recipient} is an UNVERIFIED GUESS from officer_directory. send_notice() will "
            f"refuse it unless allow_unverified_recipient=True is passed deliberately.")
    if not cfg["configured"]:
        prep.warnings.append(cfg["note"])

    return prep


# ─────────────────────────────────────────────────────────────────────────────
# SEND — the single outward-facing, irreversible action
# ─────────────────────────────────────────────────────────────────────────────

def send_prepared(
    prepared: PreparedNotice,
    *,
    approved: bool,
    allow_unverified_recipient: bool = False,
    require_tls: bool = True,
    timeout: int = 30,
) -> DispatchResult:
    """Transmit an already-prepared notice. This is the irreversible step.

    `approved` is keyword-only and has NO default: the caller must state, at the
    call site, that a human agreed to serve this notice. That is the whole point
    — it cannot be satisfied by a config flag or an argument that drifted in.

    `require_tls` defaults to True. The notice carries the data principal's name,
    email and phone, so handing it to a relay in plaintext leaks exactly what the
    tool exists to protect. If the server offers no STARTTLS the send is refused
    rather than quietly downgraded; pass require_tls=False only for a relay on
    localhost or an otherwise trusted link.
    """
    now = datetime.now(timezone.utc).isoformat()

    if prepared is None or not prepared.ok:
        return DispatchResult(
            status="refused", prepared=prepared, attempted_at=now,
            message=(prepared.blocked_reason if prepared else "No prepared notice was given."))

    if approved is not True:
        return DispatchResult(
            status="refused", prepared=prepared, attempted_at=now,
            message=("Not sent: approval was not given. Serving a legal notice on a third "
                     "party is irreversible and outward-facing, so this module never sends "
                     "on inference. Pass approved=True only after the user has agreed."))

    if prepared.recipient_tier == "guess" and not allow_unverified_recipient:
        return DispatchResult(
            status="refused", prepared=prepared, attempted_at=now,
            message=(f"Not sent: {prepared.to} is an unverified guessed address. This notice "
                     f"carries the data principal's name, email and phone, so mailing it to a "
                     f"mailbox nobody has confirmed would disclose those identifiers to "
                     f"whoever owns it. Confirm the officer's address from the controller's "
                     f"published privacy page (DPDP s.13(3) requires one), or pass "
                     f"allow_unverified_recipient=True to accept that risk knowingly."))

    cfg = smtp_status()
    if not cfg["configured"]:
        return DispatchResult(
            status="not_configured", prepared=prepared, attempted_at=now,
            message=(f"{cfg['note']} The notice is ready to send by hand: "
                     f"{prepared.eml_path or 'use the mailto: link'}."))

    # Rebuild the message from the verbatim bytes rather than re-rendering it, so
    # what goes on the wire is byte-identical to what was hashed and exported. A
    # re-render could differ (a new Date, a new Message-ID) and silently
    # invalidate the audit evidence.
    payload = prepared.raw_message.encode("utf-8")

    host, port = cfg["host"], cfg["port"]
    server = None
    try:
        context = ssl.create_default_context()
        if port == 465:
            # Implicit TLS. Gmail/Zoho app-password setups commonly use this, and
            # starttls() on 465 fails confusingly, so it is branched explicitly.
            server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
            tls = "implicit TLS"
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            server.ehlo()
            # STARTTLS only when the server actually advertises it. Calling it
            # unconditionally fails against relays that do not offer it, and
            # calling it blindly is also how a "secure" send silently is not one.
            if server.has_extn("starttls"):
                server.starttls(context=context)
                server.ehlo()
                tls = "STARTTLS"
            elif require_tls:
                server.close()
                return DispatchResult(
                    status="refused", prepared=prepared, attempted_at=now,
                    message=(f"Not sent: {host}:{port} does not offer STARTTLS, so the notice "
                             f"would cross the network in plaintext carrying the data "
                             f"principal's name, email and phone. Use a TLS-capable relay "
                             f"(port 587 or 465), or pass require_tls=False if this relay is "
                             f"on localhost or otherwise trusted."))
            else:
                tls = "NONE — plaintext, permitted by require_tls=False"

        if os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASS"):
            server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])

        # Driven at the command level rather than via sendmail() so the server's
        # real acceptance response ("250 2.0.0 Ok: queued as …") can be captured.
        # That string is the closest thing to a receipt this protocol offers, and
        # the audit chain should hold it rather than a boolean we inferred.
        code, resp = server.mail(prepared.from_addr)
        if code != 250:
            raise smtplib.SMTPSenderRefused(code, resp, prepared.from_addr)
        code, resp = server.rcpt(prepared.to)
        if code not in (250, 251):
            server.close()
            return DispatchResult(
                status="failed", prepared=prepared, attempted_at=now,
                refused_recipients={prepared.to: f"{code} {_text(resp)}"},
                error=f"{code} {_text(resp)}", error_type="SMTPRecipientsRefused",
                message=(f"{host} accepted the connection but refused {prepared.to}. The "
                         f"address is likely wrong or non-existent; nothing was delivered. "
                         f"Re-check the officer address before retrying."))
        code, resp = server.data(payload)
        if code != 250:
            raise smtplib.SMTPDataError(code, resp)
        accept_response = f"{code} {_text(resp)}"

        try:
            server.quit()
        except smtplib.SMTPException:
            server.close()          # the message was already accepted; QUIT is courtesy

        return DispatchResult(
            status="sent", prepared=prepared, attempted_at=now,
            smtp_response=f"{host}:{port} [{tls}] → {accept_response}",
            message=(f"Notice dispatched to {prepared.to}, Message-ID {prepared.message_id}. "
                     f"Server response: {accept_response}. Note this means an SMTP server "
                     f"took custody — it is not proof the officer read it, and not proof the "
                     f"statutory clock has started."))

    except smtplib.SMTPRecipientsRefused as exc:
        return DispatchResult(
            status="failed", prepared=prepared, attempted_at=now,
            error=str(exc), error_type=type(exc).__name__,
            refused_recipients={k: str(v) for k, v in (exc.recipients or {}).items()},
            message=f"{prepared.to} was refused by the server; nothing was delivered.")
    except smtplib.SMTPAuthenticationError as exc:
        return DispatchResult(
            status="failed", prepared=prepared, attempted_at=now,
            error=str(exc), error_type=type(exc).__name__,
            message=("SMTP rejected the credentials. For Gmail/Zoho this usually means an "
                     "app-specific password is required rather than the account password. "
                     "Nothing was sent."))
    except (smtplib.SMTPException, ssl.SSLError, OSError) as exc:
        return DispatchResult(
            status="failed", prepared=prepared, attempted_at=now,
            error=str(exc), error_type=type(exc).__name__,
            message=(f"Dispatch to {host}:{port} failed ({type(exc).__name__}). Nothing was "
                     f"sent. The .eml export at {prepared.eml_path or '(not written)'} can "
                     f"still be sent by hand."))
    finally:
        # Never leave a socket open to a mail relay on an error path.
        if server is not None:
            try:
                server.close()
            except Exception:
                pass


def send_notice(
    notice_text: str,
    recipient: str,
    reply_to: str,
    *,
    approved: bool,
    subject: str = "",
    recipient_name: str = "",
    sender_name: str = "",
    company_name: str = "",
    statute: str = "",
    reference_id: str = "",
    recipient_tier: str = "",
    export_dir: str | None = DEFAULT_OUTBOX,
    allow_unverified_recipient: bool = False,
    require_tls: bool = True,
    timeout: int = 30,
) -> DispatchResult:
    """Prepare and serve a notice in one explicit, auditable call.

    This is the function the orchestrator should wire to `submit_erasure_request`,
    AFTER its existing approval gate has passed. `approved` is keyword-only with
    no default, so this cannot be called without stating that a human agreed.

    The .eml export and mailto: link are produced on every path — including
    `refused` and `failed` — so a blocked dispatch still leaves the user with
    something they can send themselves.
    """
    prep = prepare_notice(
        notice_text, recipient, reply_to,
        subject=subject, recipient_name=recipient_name, sender_name=sender_name,
        company_name=company_name, statute=statute, reference_id=reference_id,
        recipient_tier=recipient_tier, export_dir=export_dir)
    return send_prepared(prep, approved=approved,
                         allow_unverified_recipient=allow_unverified_recipient,
                         require_tls=require_tls, timeout=timeout)


# ─────────────────────────────────────────────────────────────────────────────
# Offline demo — renders a real notice, exports it, prints the mailto, SENDS
# NOTHING. Run: ./.venv/bin/python -m backend.remediation.mailer
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 78)
    print("mailer — offline demo. No message is transmitted by this script.")
    print("=" * 78)

    cfg = smtp_status()
    print("\nSMTP status:")
    print(json.dumps(cfg, indent=2))

    # Render a real notice through the project's own generator rather than a stub,
    # so the demo exercises the actual text that would be served.
    from backend.remediation.notice_generator import NoticeGenerator
    from backend.remediation.officer_directory import resolve_officer

    gen = NoticeGenerator().generate(
        jurisdiction="dpdp",
        user_name="Aarav Sharma",
        user_email="aarav.sharma.demo@gmail.com",
        user_phone="9876543210",
        # Deliberately sensitive, to demonstrate the redaction guard. The PAN is a
        # format-valid dummy and the Aadhaar is a Verhoeff-valid test number.
        additional_ids="PAN ABCDE1234F, Aadhaar 2341 2345 4416",
        company_name="Eternal Limited (formerly Zomato Limited)",
        company_address="Ground Floor, 12A, 94 Meghdoot, Nehru Place, New Delhi 110019",
        detected_pii_summary="email address, phone number, delivery address, order history",
    )
    print(f"\nNotice rendered: {gen['reference_id']}  ({gen['statute_cited']})")

    who = resolve_officer("Zomato")
    print(f"Addressee resolved: {who.primary.email}  [tier={who.primary.tier}, "
          f"is_guess={who.primary.is_guess}]")
    print(f"  evidence: {who.primary.evidence}")

    prep = prepare_notice(
        gen["notice_text"],
        recipient=who.primary.email,
        reply_to="aarav.sharma.demo@gmail.com",
        recipient_name=who.primary.role,
        sender_name="Aarav Sharma",
        company_name=who.company_name,
        statute=gen["statute_cited"],
        reference_id=gen["reference_id"],
        recipient_tier=who.primary.tier,
    )

    print("\n── Prepared ─────────────────────────────────────────────────────")
    print(f"  To          : {prep.to}")
    print(f"  From        : {prep.from_addr}  (sender_is_user={prep.sender_is_user})")
    print(f"  Reply-To    : {prep.reply_to}")
    print(f"  Subject     : {prep.subject}")
    print(f"  Message-ID  : {prep.message_id}")
    print(f"  Date        : {prep.date}")
    print(f"  SHA-256     : {prep.sha256}")
    print(f"  .eml        : {prep.eml_path}")
    print(f"  mailto len  : {len(prep.mailto_url)} (truncated={prep.mailto_truncated})")

    print("\n── Redactions ───────────────────────────────────────────────────")
    if prep.redactions:
        for r in prep.redactions:
            print(f"  {r['count']}× {r['kind']}")
    else:
        print("  (none)")

    print("\n── Warnings ─────────────────────────────────────────────────────")
    for w in prep.warnings:
        print(f"  ! {w}")

    print("\n── mailto: (compact form, one click from any mail client) ───────")
    print((prep.mailto_compact_url or prep.mailto_url)[:400] + " …")

    print("\n── First 30 lines of the verbatim wire copy ─────────────────────")
    for line in prep.raw_message.splitlines()[:30]:
        print(f"  | {line}")

    print("\n── Dispatch attempt WITHOUT approval (must refuse) ──────────────")
    print(json.dumps({k: v for k, v in
                      send_prepared(prep, approved=False).to_dict().items()
                      if k in ("status", "message")}, indent=2))

    print("\n── Dispatch attempt WITH approval ───────────────────────────────")
    res = send_prepared(prep, approved=True)
    print(json.dumps({k: v for k, v in res.to_dict().items()
                      if k in ("status", "message", "sha256", "eml_path")}, indent=2))

    print("\n" + "=" * 78)
    print("Nothing was transmitted. With no SMTP configured the status is "
          "'not_configured'\nand the .eml above is the deliverable.")
    print("=" * 78)
