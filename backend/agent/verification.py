"""
verification.py — Proving an email address or phone number is actually yours.

WHY THIS GATES EVERYTHING ELSE
------------------------------
Attribution works by corroboration: a profile is yours if the page carries your
email, your phone, your UPI handle. That logic is only as trustworthy as the
identifiers it starts from. If someone types an address they do not own — by
typo, by mistake, or deliberately — every account corroborated against it is
attributed to the wrong person, and the tool then helps them demand deletion of
a stranger's data.

So an identifier is not attribution-grade until ownership is demonstrated:

  syntactic   The string is well-formed. Proves nothing.
  deliverable The domain publishes MX records, so it can receive mail at all.
              Catches typos and invented domains. Still proves no ownership.
  verified    A one-time code sent to that address or number was returned.
              This is the only tier that proves control.

Only `verified` identifiers are used to attribute an account to a person.
Unverified ones can still be searched with, but a match on them yields a
candidate that the user must confirm — never a finding.

DELIVERY
--------
Email uses SMTP when SMTP_HOST/SMTP_USER/SMTP_PASS are configured. SMS needs a
paid gateway and has none wired in. When a channel is unconfigured the module
runs in `dev` mode: the code is returned to the caller and written to the server
log instead of being delivered, and every response says so plainly. Dev mode
proves nothing about ownership and is marked as such wherever it appears —
it exists so the flow can be exercised, not to fake a verification.
"""

import hashlib
import hmac
import os
import re
import secrets
import subprocess
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from backend.agent.memory import DB_PATH, utcnow

CODE_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS verified_identifiers (
    user_id     TEXT,
    kind        TEXT,          -- email | phone
    value       TEXT,          -- normalised
    verified_at TEXT,
    method      TEXT,          -- otp_email | otp_sms | dev_mode
    PRIMARY KEY (user_id, kind, value)
);
CREATE TABLE IF NOT EXISTS pending_codes (
    user_id    TEXT,
    kind       TEXT,
    value      TEXT,
    code_hash  TEXT,
    salt       TEXT,
    issued_at  TEXT,
    expires_at TEXT,
    attempts   INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, kind, value)
);
"""


def normalise_email(v: str) -> str:
    return (v or "").strip().lower()


def normalise_phone(v: str) -> str:
    d = "".join(c for c in (v or "") if c.isdigit())
    return d[-10:] if len(d) >= 10 else d


def check_mx(domain: str) -> dict:
    """Does this domain publish MX records? Free, real, and catches typos."""
    try:
        r = subprocess.run(["dig", "+short", "MX", domain],
                           capture_output=True, text=True, timeout=12)
        records = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    except Exception as e:
        return {"checked": False, "deliverable": None, "records": [],
                "note": f"MX lookup unavailable ({type(e).__name__})."}

    # "0 ." is a null MX: the domain declares it accepts no mail at all (RFC 7505).
    if records and all(rec.split()[-1] == "." for rec in records):
        return {"checked": True, "deliverable": False, "records": records,
                "note": f"{domain} publishes a null MX — it accepts no email."}
    if not records:
        return {"checked": True, "deliverable": False, "records": [],
                "note": f"{domain} publishes no MX records — mail cannot be delivered."}
    return {"checked": True, "deliverable": True, "records": records[:3],
            "note": f"{domain} publishes {len(records)} MX record(s)."}


class Verifier:
    """Issues and checks one-time codes, and records what has been proven."""

    def __init__(self, path: str = DB_PATH):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def _exec(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _row(self, sql, params=()):
        with self._lock:
            r = self._conn.execute(sql, params).fetchone()
            return dict(r) if r else None

    def _rows(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # ── channel availability ─────────────────────────────────────────────────

    @staticmethod
    def email_channel() -> str:
        return "smtp" if all(os.environ.get(k) for k in
                             ("SMTP_HOST", "SMTP_USER", "SMTP_PASS")) else "dev"

    @staticmethod
    def sms_channel() -> str:
        return "sms" if os.environ.get("SMS_API_KEY") else "dev"

    # ── issuing ──────────────────────────────────────────────────────────────

    def request_code(self, user_id: str, kind: str, raw_value: str) -> dict:
        if kind == "email":
            value = normalise_email(raw_value)
            if not EMAIL_RE.match(value):
                return {"status": "invalid", "message": "That is not a well-formed email address."}
            mx = check_mx(value.split("@")[-1])
            if mx["checked"] and mx["deliverable"] is False:
                return {"status": "undeliverable", "mx": mx,
                        "message": mx["note"] + " Check for a typo."}
            channel = self.email_channel()
        elif kind == "phone":
            value = normalise_phone(raw_value)
            if len(value) != 10:
                return {"status": "invalid",
                        "message": "Enter a 10-digit Indian mobile number."}
            mx = None
            channel = self.sms_channel()
        else:
            return {"status": "invalid", "message": f"Unknown identifier kind {kind!r}."}

        existing = self._row(
            "SELECT issued_at FROM pending_codes WHERE user_id=? AND kind=? AND value=?",
            (user_id, kind, value))
        if existing:
            try:
                age = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(existing["issued_at"])).total_seconds()
                if age < RESEND_COOLDOWN_SECONDS:
                    return {"status": "cooldown",
                            "retry_after_seconds": int(RESEND_COOLDOWN_SECONDS - age),
                            "message": "A code was just sent. Wait before requesting another."}
            except ValueError:
                pass

        code = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_hex(16)
        expires = (datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES)).isoformat()
        self._exec(
            "INSERT OR REPLACE INTO pending_codes "
            "(user_id,kind,value,code_hash,salt,issued_at,expires_at,attempts) "
            "VALUES (?,?,?,?,?,?,?,0)",
            (user_id, kind, value, self._hash(code, salt), salt, utcnow(), expires))

        delivered, dev_code = self._deliver(kind, value, code, channel)
        out = {
            "status": "sent" if delivered else "dev_mode",
            "kind": kind, "value": value, "channel": channel,
            "expires_in_minutes": CODE_TTL_MINUTES,
        }
        if kind == "email":
            out["mx"] = mx
        if not delivered:
            out["dev_code"] = dev_code
            out["message"] = (
                f"No {'SMTP' if kind == 'email' else 'SMS'} channel is configured, so the code "
                f"was not actually delivered. It is shown here so the flow can be exercised. "
                f"THIS PROVES NOTHING about ownership and is recorded as dev_mode. "
                f"Configure {'SMTP_HOST/SMTP_USER/SMTP_PASS' if kind == 'email' else 'SMS_API_KEY'} "
                f"for real verification.")
        else:
            out["message"] = f"A 6-digit code was sent to {value}. It expires in {CODE_TTL_MINUTES} minutes."
        return out

    def _deliver(self, kind: str, value: str, code: str, channel: str) -> tuple[bool, str | None]:
        if kind == "email" and channel == "smtp":
            try:
                import smtplib
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["Subject"] = "Your SovereignPrivacy verification code"
                msg["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
                msg["To"] = value
                msg.set_content(
                    f"Your verification code is {code}.\n\n"
                    f"It expires in {CODE_TTL_MINUTES} minutes. If you did not request this, "
                    f"ignore this message — somebody may have mistyped their address.")
                with smtplib.SMTP(os.environ["SMTP_HOST"],
                                  int(os.environ.get("SMTP_PORT", "587")), timeout=20) as smtp:
                    smtp.starttls()
                    smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
                    smtp.send_message(msg)
                return True, None
            except Exception as e:
                print(f"  [verify] SMTP send failed: {type(e).__name__}: {e}")
                return False, code
        # No SMS gateway is wired in; that needs a paid provider.
        print(f"  [verify] dev_mode code for {kind} {value}: {code}")
        return False, code

    # ── checking ─────────────────────────────────────────────────────────────

    @staticmethod
    def _hash(code: str, salt: str) -> str:
        return hashlib.sha256((salt + code).encode()).hexdigest()

    def submit_code(self, user_id: str, kind: str, raw_value: str, code: str) -> dict:
        value = normalise_email(raw_value) if kind == "email" else normalise_phone(raw_value)
        row = self._row(
            "SELECT * FROM pending_codes WHERE user_id=? AND kind=? AND value=?",
            (user_id, kind, value))
        if not row:
            return {"status": "no_pending", "message": "No code was issued for that identifier."}

        if utcnow() > row["expires_at"]:
            self._exec("DELETE FROM pending_codes WHERE user_id=? AND kind=? AND value=?",
                       (user_id, kind, value))
            return {"status": "expired", "message": "That code has expired. Request a new one."}

        if row["attempts"] >= MAX_ATTEMPTS:
            self._exec("DELETE FROM pending_codes WHERE user_id=? AND kind=? AND value=?",
                       (user_id, kind, value))
            return {"status": "locked",
                    "message": "Too many incorrect attempts. Request a new code."}

        if not hmac.compare_digest(self._hash((code or "").strip(), row["salt"]), row["code_hash"]):
            self._exec("UPDATE pending_codes SET attempts=attempts+1 "
                       "WHERE user_id=? AND kind=? AND value=?", (user_id, kind, value))
            return {"status": "incorrect",
                    "attempts_left": MAX_ATTEMPTS - row["attempts"] - 1,
                    "message": "That code is not correct."}

        method = ("otp_email" if kind == "email" and self.email_channel() == "smtp"
                  else "otp_sms" if kind == "phone" and self.sms_channel() == "sms"
                  else "dev_mode")
        self._exec("INSERT OR REPLACE INTO verified_identifiers "
                   "(user_id,kind,value,verified_at,method) VALUES (?,?,?,?,?)",
                   (user_id, kind, value, utcnow(), method))
        self._exec("DELETE FROM pending_codes WHERE user_id=? AND kind=? AND value=?",
                   (user_id, kind, value))
        return {"status": "verified", "kind": kind, "value": value, "method": method,
                "attribution_grade": method != "dev_mode",
                "message": (f"{value} is verified."
                            if method != "dev_mode" else
                            f"{value} is marked verified, but via dev_mode — no code was "
                            f"actually delivered, so this does NOT prove ownership and is "
                            f"not used to attribute accounts.")}

    # ── reading ──────────────────────────────────────────────────────────────

    def verified(self, user_id: str, kind: str | None = None) -> list[dict]:
        if kind:
            return self._rows("SELECT * FROM verified_identifiers WHERE user_id=? AND kind=?",
                              (user_id, kind))
        return self._rows("SELECT * FROM verified_identifiers WHERE user_id=?", (user_id,))

    def attribution_grade(self, user_id: str) -> dict:
        """Identifiers strong enough to attribute an account. dev_mode is excluded."""
        rows = [r for r in self.verified(user_id) if r["method"] != "dev_mode"]
        return {
            "emails": [r["value"] for r in rows if r["kind"] == "email"],
            "phones": [r["value"] for r in rows if r["kind"] == "phone"],
        }

    def status_for(self, user_id: str, email: str = "", phone: str = "") -> dict:
        v = {(r["kind"], r["value"]): r for r in self.verified(user_id)}
        out = {}
        if email:
            e = normalise_email(email)
            rec = v.get(("email", e))
            out["email"] = {"value": e,
                            "tier": ("verified" if rec and rec["method"] != "dev_mode"
                                     else "dev_mode" if rec else "unverified"),
                            "method": (rec or {}).get("method")}
        if phone:
            ph = normalise_phone(phone)
            rec = v.get(("phone", ph))
            out["phone"] = {"value": ph,
                            "tier": ("verified" if rec and rec["method"] != "dev_mode"
                                     else "dev_mode" if rec else "unverified"),
                            "method": (rec or {}).get("method")}
        return out


_verifier: Verifier | None = None


def get_verifier() -> Verifier:
    global _verifier
    if _verifier is None:
        _verifier = Verifier()
    return _verifier
