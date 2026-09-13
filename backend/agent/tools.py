"""
tools.py — The agent's tool surface.

Each function here is one capability the privacy agent can invoke. They are
plain callables returning JSON-serialisable dicts, which matters because two
different planners drive them:

  • the LLM planner (Claude decides which tool to call next, and why), and
  • the deterministic planner (a fixed pipeline used when no API key is
    configured, or when the demo must run offline).

Both paths execute the *same* tools against the *same* state, so the product
behaves identically; only the reasoning layer differs.

Every tool emits a trace event so the UI can show the agent working.
"""

import hashlib
import json
import os
import re
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from backend.agent import account_discovery, extra_sources, verifiers, web_search
from backend.remediation.mailer import prepare_notice, send_notice, smtp_status
from backend.remediation.officer_directory import resolve_officer
from backend.remediation.self_serve import (
    plan_unsubscribe, resolve_route, unsubscribe_one_click, verify_removal as verify_gone)
from backend.agent.verification import get_verifier
from backend.agent.memory import Memory, utcnow
from backend.mock_brokers.network import (
    BrokerNetwork, BROKERS, NON_SERVABLE_CLASSES, subject_key)
from backend.pii.recognizer import PIIRecognizer
from backend.pii.resolver import IdentityResolver
from backend.pii.risk_calculator import RiskCalculator
from backend.remediation.notice_generator import NoticeGenerator
from backend.scanners.hibp_scanner import HIBPScanner
from backend.scanners.paste_scanner import PasteScanner
from backend.scanners.broker_scanner import BrokerScanner

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_recognizer = PIIRecognizer()
_resolver = IdentityResolver()
_risk = RiskCalculator()
_notices = NoticeGenerator()
_hibp = HIBPScanner()
_pastes = PasteScanner()
_optery = BrokerScanner()

# Jurisdiction selection: where the data subject is, and what the controller faces.
JURISDICTION_BY_COUNTRY = {
    "IN": "dpdp",
    "EU": "gdpr", "DE": "gdpr", "FR": "gdpr", "IE": "gdpr", "NL": "gdpr",
    "US": "ccpa", "CA": "ccpa",
}

SEVERITY_BY_FIELD = {
    "aadhaar": "critical", "pan": "critical", "credit_card": "critical",
    "bank_account": "critical", "password": "critical",
    "government_id": "critical", "passport": "critical", "ssn": "critical",
    "auth_token": "critical", "security_question": "critical",
    # Special-category data. DPDP s.2 and GDPR Art.9 treat these differently
    # from ordinary personal data because the harm from disclosure is not
    # financial and cannot be undone by changing a password.
    "religion": "high", "sexual_preference": "high", "health": "high",
    "ethnicity": "high", "biometric": "high",
    "address": "high", "phone": "high", "date_of_birth": "high",
    "private_message": "high", "income": "high", "vehicle": "high",
    "email": "medium", "employer": "medium", "username": "medium",
    "social_profile": "medium", "photo": "medium", "purchase": "medium",
    "academic": "medium", "gender": "medium", "nationality": "medium",
    "marital_status": "medium", "ip_address": "medium",
    "city": "low", "name": "low", "age_range": "low", "interests": "low",
    "device": "low", "browser": "low", "language": "low", "website_activity": "low",
}

# XposedOrNot names the data classes in its own vocabulary. Mapping it onto the
# canonical field names is what makes severity correct: unmapped labels fall
# through to "low", which reported a breach of government IDs and passwords as a
# minor one.
XPOSED_LABEL_TO_FIELD = {
    "email addresses": "email", "passwords": "password",
    "passwords history": "password", "historical passwords": "password",
    "credit card details": "credit_card", "auth tokens": "auth_token",
    "security questions and answers": "security_question",
    "names": "name", "titles": "name", "spouses names": "name",
    "mothers maiden names": "security_question", "spouses details": "name",
    "usernames": "username", "instant messenger identities": "username",
    "social media profiles": "social_profile", "profile photos": "photo",
    "phone numbers": "phone", "physical addresses": "address",
    "geographic locations": "city", "places of birth": "date_of_birth",
    "dates of birth": "date_of_birth", "ip addresses": "ip_address",
    "genders": "gender", "nationalities": "nationality", "nationality": "nationality",
    "ethnicities": "ethnicity", "religions": "religion",
    "sexual preferences": "sexual_preference", "marital statuses": "marital_status",
    "spoken languages": "language", "drink habits": "interests",
    "drug habits": "health", "government ids": "government_id",
    "government issued ids": "government_id",
    "partial government issued ids": "government_id",
    "national ids": "government_id", "passport numbers": "passport",
    "social security numbers": "ssn", "credit cards": "credit_card",
    "partial credit card data": "credit_card",
    "bank account numbers": "bank_account", "account balances": "bank_account",
    "financial transactions": "bank_account", "income levels": "income",
    "employers": "employer", "job titles": "employer", "occupations": "employer",
    "private messages": "private_message", "support tickets": "private_message",
    "customer support tickets": "private_message", "ai prompts": "private_message",
    "purchases": "purchase", "website activity": "website_activity",
    "academic records": "academic", "device information": "device",
    "browser user agent details": "browser", "browser user agents": "browser",
    "browsers": "browser", "vehicle details": "vehicle",
    "vehicle registration numbers": "vehicle",
    "vehicle identification numbers": "vehicle", "licence plates": "vehicle",
}


# Substring hints for labels the table has not seen. Ordered: the first match
# wins, so the more specific needle must come first.
_SEVERE_LABEL_HINTS = [
    ("credit card", "credit_card"), ("debit card", "credit_card"),
    ("bank account", "bank_account"), ("bank", "bank_account"),
    ("password", "password"), ("auth token", "auth_token"),
    ("session", "auth_token"), ("security question", "security_question"),
    ("passport", "passport"), ("social security", "ssn"),
    ("government", "government_id"), ("national id", "government_id"),
    ("aadhaar", "government_id"), ("biometric", "biometric"),
    ("health", "health"), ("medical", "health"),
    ("sexual", "sexual_preference"), ("religio", "religion"),
    ("private message", "private_message"),
]


def xposed_fields(raw) -> list[str]:
    """Canonical field names for one breach's exposed-data labels."""
    import ast as _ast
    items: list = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if text.startswith("["):
            try:
                items = _ast.literal_eval(text)
            except (ValueError, SyntaxError):
                items = []
        if not items:
            items = [x for x in re.split(r"[;,]", text) if x.strip()]
    out: list[str] = []
    for label in items:
        key = str(label).strip().lower()
        field = XPOSED_LABEL_TO_FIELD.get(key)
        if field is None:
            # An unmapped label falls through to a normalised slug, which is not
            # in SEVERITY_BY_FIELD and therefore scores "low". That is fine for
            # something genuinely minor, and badly wrong for a severe class the
            # table simply has not seen: the live catalogue emits both
            # "Credit card details" and "Historical passwords", neither of which
            # matched, so a card breach was reported as a minor one. Named
            # labels are mapped above; this is the safety net for the ones that
            # get added upstream tomorrow.
            for needle, severe_field in _SEVERE_LABEL_HINTS:
                if needle in key:
                    field = severe_field
                    break
            else:
                field = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
        if field and field not in out:
            out.append(field)
    return out


@dataclass
class ToolContext:
    """Per-run state shared by every tool."""
    memory: Memory
    network: BrokerNetwork
    user_id: str
    run_id: str
    profile: dict
    emit: Callable[..., None]
    auto_approve: bool = False
    sandbox: bool = False   # opt-in demo environment; OFF by default
    pending_approvals: dict = field(default_factory=dict)


# ── helpers ──────────────────────────────────────────────────────────────────

def _severity_of(fields: list[str]) -> str:
    ranks = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    worst = max((ranks.get(SEVERITY_BY_FIELD.get(f.lower(), "low"), 1) for f in fields), default=1)
    return {4: "critical", 3: "high", 2: "medium", 1: "low"}[worst]


_INDIA_BREACH_RE = re.compile(r"\b(india|indian)\b|\.in\b", re.I)

# One written-down number, separators and all: digits joined by at most two
# spacing characters. Real identifiers are written "+91 98765 43210" or
# "2341 2345 4416", so the separators must be absorbed — but JSON's own
# punctuation (", : " [ ] { }) is deliberately outside the class, so two
# unrelated fields can never be spliced into one "identifier".
_NUMERIC_RUN_RE = re.compile(r"\d(?:[\s\-().+]{0,2}\d)*")


def _looks_indian(breach: dict) -> bool:
    blob = " ".join(str(breach.get(k) or "") for k in ("name", "title", "domain", "description"))
    return bool(_INDIA_BREACH_RE.search(blob))


def load_indian_sources() -> list[dict]:
    """
    Reference directory of Indian sources that hold personal data.

    This is a DIRECTORY, not a set of findings. It says these organisations
    exist and what law governs them. It makes no claim that any particular
    person appears in any of them — nothing here queries anything.
    """
    path = os.path.join(PROJECT_ROOT, "data", "brokers", "indian_sources.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_playbooks() -> dict:
    """How to actually get data removed, per service."""
    path = os.path.join(PROJECT_ROOT, "data", "removal_playbooks.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"playbooks": [], "method_order": [], "method_info": {}}


def find_playbook(*names: str) -> dict | None:
    """Match a service to its removal playbook by id or name."""
    pbs = load_playbooks().get("playbooks", [])
    for raw in names:
        needle = (raw or "").strip().lower()
        if not needle:
            continue
        for pb in pbs:
            if needle in (pb["id"].lower(), pb["service"].lower()):
                return pb
        for pb in pbs:
            if needle in pb["service"].lower() or pb["id"].lower() in needle:
                return pb
    return None


def find_source(slug_or_name: str) -> dict | None:
    """Look up a source in the Indian registry by id or name (case-insensitive)."""
    needle = (slug_or_name or "").strip().lower()
    for src in load_indian_sources():
        if needle in (src["id"].lower(), src["name"].lower()):
            return src
    # The fuzzy pass needs a length floor. Unbounded, `needle in name` let a
    # one-character token resolve to a real fiduciary with a real legal class:
    # find_source("x") returned CIBIL (dpdp_limited), find_source("t") returned
    # Truecaller, find_source("reg") returned the Central KYC Registry. That
    # matters because determine_legal_basis derives its statute from this
    # lookup — `source_id.split(":", 1)[1]` on an id like "infostealer:t"
    # yields a stub token, and the bogus legal_class then OUTRANKS the
    # source_type branch, so an info-stealer infection was assessed as a
    # credit-bureau record ("dispute_or_correct"). The shortest real id is 5
    # chars and the shortest real name 6, so a 4-char floor loses no genuine
    # lookup; exact id/name matches are handled above and are unaffected.
    MIN_FUZZY_NEEDLE = 4
    if len(needle) >= MIN_FUZZY_NEEDLE:
        for src in load_indian_sources():
            if needle in src["name"].lower():
                return src
    return None


# ── tool implementations ─────────────────────────────────────────────────────

def build_tools(ctx: ToolContext) -> dict[str, Callable]:
    """Return {tool_name: callable}. Closures capture the run context."""

    _legal_cache: dict[str, dict] = {}

    def build_identity_profile() -> dict:
        """Normalise the user's identity and derive likely aliases with confidence
        scores. Run this first: later searches use the aliases it produces."""
        ctx.emit("identity", "profile", "Normalising identity and deriving aliases…",
                 tool_name="build_identity_profile")
        p = ctx.profile
        name = (p.get("name") or "").strip()
        email = (p.get("email") or "").strip()
        aliases = []

        if name:
            aliases.append({"alias": name, "type": "full_name", "confidence": 1.0,
                            "rationale": "Supplied directly by the user."})
            parts = name.split()
            if len(parts) >= 2:
                aliases.append({"alias": f"{parts[0][0]}. {parts[-1]}", "type": "name_variant",
                                "confidence": 0.72,
                                "rationale": "Common abbreviated form of the supplied name."})
        if email:
            local = email.split("@")[0]
            aliases.append({"alias": local, "type": "username", "confidence": 0.88,
                            "rationale": "Email local-part is frequently reused as a handle."})
            stripped = "".join(c for c in local if c.isalpha())
            if stripped and stripped != local:
                aliases.append({"alias": stripped, "type": "username", "confidence": 0.55,
                                "rationale": "Email local-part with digits removed; weaker signal."})

        ctx.memory.clear_identities(ctx.user_id)
        for a in aliases:
            ctx.memory.add_identity(ctx.user_id, a["alias"], a["type"], a["confidence"], a["rationale"])

        # Zero synthetic or fake records: strictly real data
        seeded = 0

        result = {
            "user_id": ctx.user_id,
            "name": name, "email": email,
            "phone": p.get("phone", ""), "city": p.get("city", ""),
            "country": p.get("country", "IN"),
            "aliases": aliases,
            "sandbox_enabled": False,
            "sandbox_records_seeded": 0,
        }
        ctx.emit("identity", "profile",
                 f"Identity resolved: {len(aliases)} alias(es) derived.",
                 tool_output={"aliases": [a["alias"] for a in aliases]})
        return result

    def recall_prior_activity() -> dict:
        """Recall what was already found and done for this user in earlier runs.
        Use this to avoid re-requesting removals that are already in flight."""
        ctx.emit("orchestrator", "memory", "Recalling prior runs for this identity…",
                 tool_name="recall_prior_activity")
        prior = ctx.memory.last_run_before(ctx.user_id, ctx.run_id)
        exposures = ctx.memory.get_exposures(ctx.user_id)
        requests = ctx.memory.get_requests(ctx.user_id)
        out = {
            "has_prior_run": bool(prior),
            "last_run_at": prior["started_at"] if prior else None,
            "last_risk_score": prior["risk_after"] if prior else None,
            "known_exposures": [
                {"exposure_id": e["id"], "source": e["source_name"], "status": e["status"],
                 "severity": e["severity"]} for e in exposures],
            "open_requests": [
                {"request_id": r["id"], "jurisdiction": r["jurisdiction"], "status": r["status"],
                 "deadline": r["deadline"]}
                for r in requests if r["status"] not in ("completed", "rejected")],
        }
        msg = ("No prior activity for this identity — this is a first scan."
               if not prior else
               f"Recalled {len(exposures)} known exposure(s) and {len(out['open_requests'])} open request(s).")
        ctx.emit("orchestrator", "memory", msg)
        return out

    def verify_breach_exposure() -> dict:
        """Run every breach check that can actually be performed against this
        identity, and return the evidence. Makes no claim it cannot substantiate."""
        ctx.emit("discovery", "breach", "Running real breach checks…",
                 tool_name="verify_breach_exposure")
        email = ctx.profile.get("email", "")
        _hibp._load()

        # Identifiers beyond the email address. A phone number is the identifier
        # most Indian services key on, and until now nothing checked it against
        # any breach corpus at all.
        raw_phone = "".join(c for c in str(ctx.profile.get("phone") or "") if c.isdigit())
        # Only a genuine 10-digit Indian mobile is searched. Truncating any
        # number to its last ten digits invents an identifier: '011-2345 6789'
        # becomes 1123456789, which belongs to somebody else, and a hit on it
        # would be filed as this user's exposure.
        phone = raw_phone[-10:] if len(raw_phone) in (10, 11, 12, 13) else ""
        if len(raw_phone) > 10 and not raw_phone[:-10].lstrip("0").startswith("91"):
            phone = ""
        if phone and phone[0] not in "6789":
            phone = ""
        # If a number WAS supplied and none of that could make a mobile out of
        # it, the phone corpora are simply never queried. That has to be said:
        # silently skipping the check makes an unparsed number look like a
        # number that was checked and came back clean.
        phone_unparsed = bool(raw_phone) and not phone

        # DECLARED handles only.
        #
        # derive_usernames also returns handles GUESSED from an email or UPI
        # local part, and a guess is not this person: 'john' from john@gmail.com
        # matches a stranger on every corpus that indexes usernames. Account
        # discovery can afford to search guesses because attribution clamps
        # whatever it finds to tier "candidate". These breach corpora have no
        # such clamp — a hit here is written straight to the ledger as
        # match_tier "definite", evidence_class "verified", and it then moves
        # the risk score and the removal plan. So only a handle the user has
        # actually claimed may drive them.
        handles = [h for h, src in account_discovery.derive_usernames(ctx.profile)
                   if src == "declared"][:2]

        checks = [
            verifiers.check_hibp_account(email),
            # Free, keyless, and a different corpus from HIBP. Without this the
            # product's central question — "is my address in a breach?" — went
            # unanswered for anyone without a paid HIBP subscription.
            verifiers.check_xposedornot(email),
            # A stolen-from-the-browser exposure, which no other check covers.
            verifiers.check_infostealer(email),
            verifiers.check_email_domain_breached(email, _hibp._breaches),
            verifiers.check_gravatar(email),
        ]
        # Free, keyless corpora that answer for identifiers the checks above
        # cannot take. Each is wrapped so one flaky third party cannot take the
        # scan down with it — an exception here must degrade to "could not
        # check", never to "clear".
        def _safe(fn, *a):
            try:
                return fn(*a)
            except Exception as exc:
                # Dropping the check entirely would make a timeout or a refused
                # connection indistinguishable from "this source holds nothing
                # on you". Return an explicit "unavailable" instead, so it is
                # counted and shown as a check that could not run.
                return extra_sources.Finding(
                    check=getattr(fn, "__name__", "extra_source").replace("check_", ""),
                    target=(str(a[0]) if a else ""),
                    endpoint="", queried_at=utcnow(), http_status=None,
                    result="unavailable",
                    proof=f"{type(exc).__name__}: {exc}",
                    interpretation=("The source could not be reached, so it proves nothing. "
                                    "This is NOT a clean result."),
                    reproduce="")

        extra = []
        if email:
            extra += [_safe(extra_sources.check_leakcheck, email),
                      _safe(extra_sources.check_github_email_exposure, email)]
        if len(phone) == 10:
            extra.append(_safe(extra_sources.check_leakcheck, phone))
        for h in handles:
            extra += [_safe(extra_sources.check_leakcheck, h),
                      _safe(extra_sources.check_infostealer_by_username, h)]
        checks += [e for e in extra if e is not None]

        recorded, not_checked, unavailable = [], [], []
        if phone_unparsed:
            not_checked.append({
                "check": "leakcheck_public (phone)", "result": "not_checked",
                "http_status": None,
                "why": (f"The number supplied does not resolve to a 10-digit Indian mobile, so "
                        f"it was NOT searched. Truncating it would search an identifier "
                        f"belonging to somebody else. Re-enter it as a 10-digit mobile "
                        f"(optionally +91-prefixed) to have it checked."),
            })
        for ev in checks:
            # A check that could not run is NOT a clean check. "unavailable"
            # (HTTP 429, a timeout, a 5xx) used to fall straight through the
            # `!= "hit"` guard below and vanish, so a scan in which every
            # corpus rate-limited us reported "0 exposure(s), 0 check(s)
            # unavailable" — indistinguishable from a genuinely clear result.
            if ev.result in ("not_checked", "unavailable"):
                entry = {"check": ev.check, "result": ev.result,
                         "http_status": getattr(ev, "http_status", None),
                         "why": ev.interpretation or ev.proof}
                not_checked.append(entry)
                if ev.result == "unavailable":
                    unavailable.append(entry)
                continue
            if ev.result != "hit":
                continue

            # A domain-level breach is a fact about the DOMAIN, not the person.
            # It is reported as context and never becomes a personal exposure.
            if ev.check == "email_domain_breached":
                continue

            if ev.check == "hibp_breached_account":
                names = ev.proof.split(": ", 1)[-1]
                for name in [n.strip() for n in names.split(",") if n.strip()]:
                    exp = {
                        "source_type": "breach", "source_name": name,
                        "source_id": "breach:" + name, "record_id": "",
                        "data_found": ["email"], "detail": {"evidence": ev.to_dict()},
                        "match_confidence": 1.0, "match_tier": "definite",
                        "severity": "high", "risk_score": 0.0,
                        "evidence_class": "verified", "evidence": [ev.to_dict()],
                    }
                    exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
                    recorded.append({"exposure_id": exp_id, "source": name,
                                     "evidence_class": "verified", "is_new": is_new})

            elif ev.check == "xposedornot_breached_account":
                meta = getattr(ev, "metadata", None) or {}
                for b in meta.get("breaches", []):
                    name = b.get("breach") or "Unknown breach"
                    # The dataset says WHAT leaked; carry it through rather than
                    # flattening every breach to "an email address was in it".
                    fields = xposed_fields(b.get("xposed_data"))
                    exp = {
                        "source_type": "breach", "source_name": name,
                        "source_id": "breach:" + name, "record_id": "",
                        "data_found": fields or ["email"],
                        "detail": {"evidence": ev.to_dict(), "breach": b,
                                   "domain": b.get("domain", ""),
                                   "industry": b.get("industry", ""),
                                   "description": b.get("details", ""),
                                   "source_dataset": "XposedOrNot"},
                        "match_confidence": 1.0, "match_tier": "definite",
                        "severity": _severity_of(fields or ["email"]),
                        "risk_score": 0.0,
                        "evidence_class": "verified", "evidence": [ev.to_dict()],
                    }
                    exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
                    recorded.append({"exposure_id": exp_id, "source": name,
                                     "evidence_class": "verified", "is_new": is_new})

            elif ev.check == "infostealer_infection":
                meta = getattr(ev, "metadata", None) or {}
                exp = {
                    "source_type": "infostealer", "source_name": "Info-stealer malware infection",
                    "source_id": "infostealer", "record_id": "",
                    # Everything saved in that browser went at once, so this is
                    # a credential exposure, not merely an email exposure.
                    "data_found": ["email", "password", "session_cookies"],
                    "detail": {"evidence": ev.to_dict(),
                               "machines": meta.get("stealers", []),
                               "user_services": meta.get("total_user_services"),
                               "corporate_services": meta.get("total_corporate_services"),
                               "source_dataset": "Hudson Rock Cavalier"},
                    "match_confidence": 1.0, "match_tier": "definite",
                    "severity": "critical", "risk_score": 0.0,
                    "evidence_class": "verified", "evidence": [ev.to_dict()],
                }
                exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
                recorded.append({"exposure_id": exp_id, "source": "Info-stealer infection",
                                 "evidence_class": "verified", "is_new": is_new})

            elif ev.check in ("leakcheck_public", "github_email_exposure",
                              "infostealer_username"):
                # What identifier did this answer for? It is not always the
                # email — a phone or a handle may be what matched — and saying
                # so is the whole point of an evidence-led report.
                meta = getattr(ev, "metadata", None) or {}
                kind = meta.get("identifier_type") or (
                    "phone" if ev.target.isdigit() else
                    "email" if "@" in str(ev.target) else "username")
                # Sources arrive as {"name": ..., "date": ...} from one corpus
                # and as bare strings from another. Normalise before they reach
                # a label, or the user is shown a Python dict.
                raw_sources = meta.get("sources") or meta.get("named_sources") or []
                sources = []
                for item in raw_sources:
                    name = item.get("name") if isinstance(item, dict) else item
                    if name and str(name) not in sources:
                        sources.append(str(name))
                exp = {
                    "source_type": "breach",
                    "source_name": (f"{ev.check.replace('_', ' ').title()} — {kind}"
                                    if not sources else
                                    f"{sources[0]} (+{len(sources) - 1} more)"
                                    if len(sources) > 1 else str(sources[0])),
                    "source_id": f"{ev.check}:{kind}",
                    "record_id": "",
                    "data_found": [kind],
                    "detail": {"evidence": ev.to_dict(), "identifier_type": kind,
                               "named_sources": sources, "source_records": raw_sources,
                               "source_dataset": ev.check},
                    "match_confidence": 1.0, "match_tier": "definite",
                    "severity": _severity_of([kind]),
                    "risk_score": 0.0,
                    "evidence_class": "verified", "evidence": [ev.to_dict()],
                }
                exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
                recorded.append({"exposure_id": exp_id, "source": exp["source_name"],
                                 "evidence_class": "verified", "is_new": is_new})

            elif ev.check == "gravatar":
                meta = getattr(ev, "metadata", None) or {}
                username = meta.get("username", "")
                display_name = meta.get("displayName", "")
                profile_url = meta.get("profileUrl", "") or f"https://gravatar.com/{hashlib.md5(email.strip().lower().encode()).hexdigest()}"
                rec_id = username or (email.split("@")[0] if email else "gravatar")
                exp = {
                    "source_type": "public_profile", "source_name": "Gravatar",
                    "source_id": "gravatar", "record_id": rec_id,
                    "data_found": ["email", "photo", "public_profile"],
                    "detail": {
                        "url": profile_url,
                        "username": username,
                        "displayName": display_name,
                        "evidence": ev.to_dict(),
                    },
                    "match_confidence": 1.0, "match_tier": "definite",
                    "severity": "medium", "risk_score": 0.0,
                    "evidence_class": "verified", "evidence": [ev.to_dict()],
                }
                exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
                recorded.append({"exposure_id": exp_id, "source": "Gravatar",
                                 "evidence_class": "verified", "is_new": is_new})

        domain_ev = next(c for c in checks if c.check == "email_domain_breached")
        degraded = bool(unavailable)
        ctx.emit("discovery", "breach",
                 (f"Breach checks INCOMPLETE — {len(unavailable)} corpus/corpora could not be "
                  f"reached ({', '.join(u['check'] for u in unavailable)}). "
                  f"{len(recorded)} VERIFIED exposure(s) so far; a clean result CANNOT be "
                  f"claimed until those checks complete."
                  if degraded else
                  f"Breach checks complete: {len(recorded)} VERIFIED exposure(s), "
                  f"{len(not_checked)} check(s) unavailable."),
                 status="error" if degraded else "ok",
                 tool_output={"verified": len(recorded), "not_checked": len(not_checked),
                              "unavailable": len(unavailable), "coverage_complete": not degraded})

        return {
            "verified_exposures": recorded,
            "checks_run": [c.to_dict() for c in checks],
            "not_checked": not_checked,
            "unavailable": unavailable,
            "coverage_complete": not degraded,
            "domain_context": domain_ev.to_dict(),
            "note": ("Only checks that returned a positive hit became exposures. Where a check "
                     "could not run — nothing supplied, rate-limited, timed out — it is listed "
                     "in not_checked. An unreachable source is never counted as a clear one, "
                     "and no membership is guessed."),
        }

    def verify_password_exposure(password: str) -> dict:
        """Check whether a specific password appears in breach corpora, using
        k-anonymity so the password never leaves this machine."""
        ctx.emit("discovery", "password", "Checking password against breach corpora (k-anonymous)…",
                 tool_name="verify_password_exposure")
        ev = verifiers.check_password_pwned(password)
        ctx.emit("discovery", "password",
                 ("COMPROMISED — " + ev.proof) if ev.result == "hit"
                 else f"Password check: {ev.result}.",
                 tool_output={"result": ev.result})
        return ev.to_dict()

    def declare_known_accounts(services: str) -> dict:
        """Record services the user says they hold an account with. Their own
        knowledge is valid grounds for a DPDP s.12 request — no scraping needed."""
        names = [n.strip() for n in (services or "").replace("\n", ",").split(",") if n.strip()]
        if not names:
            return {"declared": [], "note": "No services supplied."}

        ctx.emit("discovery", "declared", f"Recording {len(names)} user-declared account(s)…",
                 tool_name="declare_known_accounts")
        out = []
        for name in names:
            src = find_source(name)
            ev = {
                "check": "user_declaration", "target": name,
                "endpoint": "(none — asserted by the data principal)",
                "queried_at": utcnow(), "http_status": None, "result": "hit",
                "proof": f"The data principal states they hold an account with {name}.",
                "interpretation": ("Self-declared. Not independently verified, but a person's own "
                                   "knowledge of their accounts is valid grounds to exercise "
                                   "erasure under DPDP s.12."),
                "reproduce": "",
            }
            exp = {
                "source_type": "data_broker",
                "source_name": src["name"] if src else name,
                "source_id": ("declared:" + (src["id"] if src else name.lower().replace(" ", "-"))),
                "record_id": "",
                "data_found": src["data_exposed"] if src else ["name", "email"],
                "detail": {"registry": src or {}, "declared": True},
                "match_confidence": 1.0, "match_tier": "self_declared",
                "severity": (src or {}).get("severity", "medium"), "risk_score": 0.0,
                "evidence_class": "self_declared", "evidence": [ev],
            }
            exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
            out.append({
                "exposure_id": exp_id, "service": src["name"] if src else name,
                "in_registry": bool(src),
                "legal_class": (src or {}).get("legal_class", "dpdp_erasure"),
                "is_new": is_new,
            })

        ctx.emit("discovery", "declared",
                 f"Recorded {len(out)} declared account(s) as actionable exposures.",
                 tool_output={"count": len(out)})
        return {"declared": out,
                "note": "Self-declared. Valid grounds to serve an erasure notice."}

    def browse_indian_registry() -> dict:
        """The reference directory of Indian sources and the law governing each.
        A directory, not findings — it makes no claim about this person."""
        srcs = load_indian_sources()
        ctx.emit("discovery", "registry",
                 f"Indian source registry: {len(srcs)} organisations on file (reference only).",
                 tool_name="browse_indian_registry")
        return {
            "count": len(srcs),
            "sources": [{k: v for k, v in s.items() if k != "how_collected"} for s in srcs],
            "disclaimer": ("REFERENCE DIRECTORY. Nothing here was queried and no claim is made "
                           "that this person appears in any of them. Use declare_known_accounts "
                           "to turn one into an actionable exposure."),
        }

    def search_data_brokers() -> dict:
        """Search data-broker registries for intelligence on this identity.
        Zero synthetic or fake data is ever generated."""
        p = ctx.profile
        directory = _optery.scan(p.get("name", ""), p.get("email", ""), p.get("phone", ""), p.get("city", ""))
        indian = load_indian_sources()
        ctx.emit("discovery", "broker",
                 f"Data Fiduciary directory evaluated: {len(indian)} statutory source(s) indexed under DPDP Act 2023.",
                 tool_name="search_data_brokers")
        return {
            "removable_records": [],
            "sandbox_enabled": False,
            "directory_context": {
                "optery_brokers_indexed": directory.get("stats", {}).get("total_brokers_checked", 0),
                "indian_sources_indexed": len(indian),
                "indian_sources_erasable": len([x for x in indian if x.get("legal_class") == "dpdp_erasure"]),
                "note": "Operating strictly on verified public databases and operating Data Fiduciaries under DPDP Act 2023. Zero synthetic records.",
            },
        }

    def search_paste_dumps() -> dict:
        """Search dark-web paste dumps for this identity's PII."""
        ctx.emit("discovery", "paste", "Scanning paste/leak corpus…", tool_name="search_paste_dumps")
        res = _pastes.scan(ctx.profile)
        recorded = []
        for m in res.get("matches", []):
            resolution = m.get("identity_resolution") or {}
            # Only count a paste as the user's own exposure when identity resolution
            # actually supports it — shared dumps contain thousands of strangers.
            if not resolution.get("is_match", False):
                continue
            fields = [e.get("entity_type", "").lower() for e in m.get("entities_found", [])]
            exp = {
                "source_type": "paste",
                "source_name": m.get("title") or m.get("paste_id") or "paste",
                "source_id": "paste:" + str(m.get("paste_id") or m.get("title")),
                "record_id": "",
                "data_found": fields,
                "detail": {k: v for k, v in m.items() if k != "entities_found"},
                "match_confidence": resolution.get("overall_score", 0.0),
                "match_tier": resolution.get("confidence_label", ""),
                "severity": _severity_of(fields),
                "risk_score": 0.0,
            }
            exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
            recorded.append({"exposure_id": exp_id, "paste": exp["source_name"],
                             "data_found": fields, "severity": exp["severity"],
                             "match_confidence": round(resolution.get("overall_score", 0.0), 3),
                             "is_new": is_new})
        ctx.emit("discovery", "paste",
                 f"Paste scan complete: {len(recorded)} attributable leak(s).",
                 tool_output={"count": len(recorded)})
        return {"corpus_size": res.get("stats", {}).get("total_pastes_checked", 0), "exposures": recorded}

    def discover_accounts() -> dict:
        """Search the web for accounts belonging to this identity, then decide
        which are genuinely theirs. A username match alone is never enough."""
        # Handles derived from an email/UPI local part ARE searched, because
        # otherwise a user who supplies only an address gets zero sites checked
        # and the scan reports nothing. What protects accuracy is not refusing
        # to look — it is refusing to ATTRIBUTE: every guessed hit is clamped to
        # tier "candidate" in discover_accounts() unless the page itself carries
        # a verified identifier, so it is shown for confirmation and never
        # counted as the user's. Legal names are still never used.
        search_guessed = bool(ctx.profile.get("search_guessed_handles", True))
        handles = account_discovery.derive_usernames(ctx.profile, search_guessed)
        if not handles:
            ctx.emit("discovery", "accounts",
                     "No custom handles declared. Discovery running with 100% precision on your "
                     "unique identifiers (email, mobile phone, Aadhaar, PAN, UPI).",
                     tool_name="discover_accounts")
        else:
            by_src: dict = {}
            for h, src in handles:
                by_src.setdefault(src, []).append(h)
            desc = "; ".join(f"{src.replace('_', ' ')}: {', '.join(v)}" for src, v in by_src.items())
            ctx.emit("discovery", "accounts",
                     f"Searching handles — {desc}", tool_name="discover_accounts")
        # Identifiers the user typed are trusted for corroboration.
        #
        # This is safe because corroboration requires the identifier to ACTUALLY
        # APPEAR on the profile page. A mistyped address simply matches nothing,
        # so the failure mode is fewer attributions — never wrong ones. The
        # protection that matters, that a shared name can never attribute a
        # stranger's account, does not depend on proving ownership at all; it
        # depends on requiring corroboration in the first place.
        #
        # An OTP flow exists in backend/agent/verification.py and can be
        # re-enabled to raise this to proven-ownership; it is unwired for now.
        graded = {
            "emails": [e.strip().lower() for e in
                       re.split(r"[,\n;]+", str(ctx.profile.get("email") or "") + "," +
                                str(ctx.profile.get("alt_emails") or "")) if e.strip()],
            "phones": [d for d in
                       ("".join(c for c in x if c.isdigit())[-10:] for x in
                        re.split(r"[,\n;]+", str(ctx.profile.get("phone") or "") + "," +
                                 str(ctx.profile.get("alt_phones") or ""))) if len(d) == 10],
        }
        res = account_discovery.discover_accounts(
            ctx.profile, verified=graded,
            include_guessed=bool(search_guessed))

        # What the user has ALREADY decided about each record, read before
        # record_exposure() overwrites the row. Keyed the same way the memory
        # layer keys an exposure: (source_id, record_id).
        _existing_rows = ctx.memory.get_exposures(ctx.user_id)
        _prior_by_key = {(e["source_id"], e["record_id"] or ""): e for e in _existing_rows}
        # Statuses that only a human (or a dispatched request) can have set. A
        # candidate in one of these has been ruled on and must not be re-parked.
        _USER_SETTLED = ("exposed", "not_mine", "requested", "acknowledged",
                         "removed", "reappeared")

        def _record(hit: dict, mine: bool):
            pb = find_playbook(hit["site"])
            att = hit.get("attribution", {})
            ev = {
                "check": "public_profile_fetch",
                "target": f"{hit['site']}/{hit['username']}",
                "endpoint": hit["url"], "queried_at": hit["checked_at"],
                "http_status": hit["http_status"], "result": "hit",
                "proof": f"HTTP {hit['http_status']} — a public profile is served at {hit['url']}",
                "interpretation": (
                    f"ATTRIBUTION: {att.get('tier', '?')} — {att.get('explanation', '')} "
                    f"Signals: {'; '.join(att.get('signals', [])) or 'none'}. "
                    f"Handle collision risk: {hit.get('collision_risk', '?')}."),
                "reproduce": hit["reproduce"],
            }
            exp = {
                "source_type": "public_profile", "source_name": hit["site"],
                "source_id": "profile:" + hit["site"].lower().replace(" ", "-"),
                "record_id": hit["username"],
                "data_found": ["username", "public_profile"],
                "detail": {"url": hit["url"], "category": hit["category"],
                           "username": hit["username"], "playbook": pb or {},
                           "attribution": att,
                           "collision_risk": hit.get("collision_risk", ""),
                           "collision_note": hit.get("collision_note", ""),
                           "handle_source": hit.get("handle_source", "")},
                "match_confidence": att.get("score", 0.0),
                "match_tier": att.get("tier", ""),
                "severity": "medium" if mine else "low",
                "risk_score": 0.0,
                "evidence_class": "verified" if mine else "candidate",
                "evidence": [ev],
            }
            prior = _prior_by_key.get((exp["source_id"], exp["record_id"] or ""))
            exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
            # A candidate is parked. It is kept out of the ledger, the risk
            # score and the removal plan until the user confirms it is theirs.
            #
            # But only a candidate the user has not already ruled on.
            # record_exposure() preserves the row's status yet overwrites
            # evidence_class and match_tier, so re-parking unconditionally
            # silently undid confirm_account(): an account the user had
            # confirmed dropped back out of the ledger and the risk score, and
            # one they had rejected as "not mine" came back asking again.
            if not mine:
                if prior and prior.get("status") in _USER_SETTLED:
                    ctx.memory.update_exposure(
                        exp_id,
                        evidence_class=prior.get("evidence_class") or "",
                        match_tier=prior.get("match_tier") or "",
                        severity=prior.get("severity") or "low")
                else:
                    ctx.memory.set_exposure_status(exp_id, "unconfirmed")
            return {"exposure_id": exp_id, "site": hit["site"], "username": hit["username"],
                    "url": hit["url"], "tier": att.get("tier"),
                    "collision_risk": hit.get("collision_risk"),
                    "why": att.get("explanation", ""),
                    "signals": att.get("signals", []),
                    "removal_method": (pb or {}).get("method", "unknown"), "is_new": is_new}

        def _key(source_id: str) -> str:
            # "gravatar" (email-keyed) and "profile:gravatar" (username-keyed)
            # are the same service; compare on the bare name.
            return (source_id or "").split(":", 1)[-1].lower()

        # A service already settled by an identifier-keyed check needs no handle
        # guess at all. Gravatar is looked up by MD5 of the email — that answer
        # is about that exact address, and is strictly better evidence than any
        # username match. Listing the service twice invites the user to
        # re-decide something already proven.
        settled = {
            _key(e["source_id"]) for e in ctx.memory.get_exposures(ctx.user_id)
            if e["evidence_class"] == "verified" and e["status"] != "unconfirmed"
        }

        def _fresh(hits):
            return [h for h in hits
                    if h["site"].lower().replace(" ", "-") not in settled]

        attributed = [_record(h, True) for h in _fresh(res.get("attributed", []))]
        candidates = [_record(h, False) for h in _fresh(res.get("candidates", []))]

        ctx.emit("discovery", "accounts",
                 f"Account discovery: {len(attributed)} attributed to you, "
                 f"{len(candidates)} unconfirmed candidate(s) held back. "
                 f"{res.get('checks_performed', 0)} checks across "
                 f"{res.get('sites_checked', 0)} sites.",
                 tool_output={"attributed": len(attributed), "candidates": len(candidates)})

        if candidates:
            ctx.emit("discovery", "accounts",
                     f"{len(candidates)} handle(s) exist but nothing on those pages ties them "
                     f"to you. Confirm each, or add a site-scoped handle "
                     f"(e.g. 'github:yourhandle') to settle them automatically.",
                     status="awaiting_approval")

        return {"attributed": attributed, "candidates": candidates,
                "usernames_tried": res.get("usernames_tried", []),
                "username_risks": res.get("username_risks", {}),
                "identifier_strength": res.get("identifier_strength", 0),
                "sites_checked": res.get("sites_checked", 0),
                "excluded_sites": res.get("excluded", {}),
                "why_candidates": res.get("why_candidates", ""),
                "improve_accuracy": res.get("improve_accuracy", "")}

    def confirm_account(exposure_id: str, is_mine: bool = True) -> dict:
        """Resolve a parked candidate: the user says whether it is theirs."""
        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}
        if is_mine:
            ctx.memory.set_exposure_status(exposure_id, "exposed")
            if exp.get("evidence_class") != "verified":
                ctx.memory.update_exposure(exposure_id, evidence_class="self_declared", match_tier="user_confirmed")
            ctx.emit("discovery", "confirm",
                     f"You confirmed {exp['source_name']} ({exp['record_id']}) is yours.")
            return {"exposure_id": exposure_id, "status": "exposed", "confirmed": True}
        ctx.memory.set_exposure_status(exposure_id, "not_mine")
        ctx.emit("discovery", "confirm",
                 f"You rejected {exp['source_name']} ({exp['record_id']}) — belongs to someone else.")
        return {"exposure_id": exposure_id, "status": "not_mine", "confirmed": False}

    def plan_removal(exposure_id: str) -> dict:
        """Choose the cheapest effective way to get this data removed.

        A statutory notice is the ESCALATION, not the opening move. If the
        service has a delete button, the answer is the delete button."""
        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}

        basis = determine_legal_basis(exposure_id)
        pb = find_playbook(exp["source_name"], exp["source_id"].split(":")[-1])
        info = load_playbooks().get("method_info", {})

        # A playbook is concrete knowledge about how this service actually works,
        # so it outranks the generic legal branch. Only a playbook that itself
        # says "not_removable", or the absence of any erasure right with no
        # playbook to contradict it, blocks removal.
        if pb:
            method = pb["method"]
        else:
            from backend.agent.fiduciary_directory import get_fiduciary_contact
            fiduciary = get_fiduciary_contact(exp["source_name"])
            # Only a CURATED directory entry describes a route somebody looked
            # up. The fallback entry synthesises its fields from the source's
            # name — "Wattpad" yields https://www.wattpad.com/privacy — and
            # flags itself contact_tier="synthesised" precisely so a caller does
            # not treat it as researched. Acting on it did two wrong things at
            # once: it handed the user an invented link, and, by returning
            # method="self_serve", it suppressed the statutory notice that the
            # legal branch below would otherwise have warranted.
            if (fiduciary and fiduciary.get("self_serve_url")
                    and fiduciary.get("contact_tier") == "curated"):
                pb = {
                    "id": exp["source_name"].lower(),
                    "service": fiduciary.get("company_name", exp["source_name"]),
                    "method": "self_serve",
                    "url": fiduciary["self_serve_url"],
                    "effort_minutes": 5,
                    "steps": [
                        f"Visit {fiduciary['self_serve_url']}.",
                        "Navigate to Account Settings → Privacy / Security.",
                        "Request account deactivation or personal data deletion.",
                        f"If unresponsive, escalate with a statutory notice to {fiduciary.get('dpo_email', 'the Grievance Officer')}."
                    ],
                    "escalation": f"Escalate under DPDP s.12/s.13 notice to Grievance Officer ({fiduciary.get('dpo_email')}).",
                    "legal_class": fiduciary.get("legal_class", "dpdp_erasure"),
                }
                method = "self_serve"
            elif basis.get("erasure_available"):
                method = "statutory_notice"
            else:
                method = "not_removable"

        plan = {
            "exposure_id": exposure_id,
            "source": exp["source_name"],
            "method": method,
            "label": info.get(method, {}).get("label", method),
            "why_this_method": info.get(method, {}).get("why", ""),
            "typical_time": info.get(method, {}).get("typical_time", ""),
            "url": (pb or {}).get("url", ""),
            "effort_minutes": (pb or {}).get("effort_minutes"),
            "steps": (pb or {}).get("steps", []),
            "escalation": (pb or {}).get("escalation", ""),
            "legal_position": basis.get("legal_basis", ""),
            "jurisdiction": basis.get("jurisdiction", ""),
            "statute": basis.get("statute", ""),
            "needs_legal_notice": method == "statutory_notice",
        }

        if method == "self_serve":
            msg = (f"{exp['source_name']}: self-serve deletion available "
                   f"(~{plan['effort_minutes']} min) — no legal notice needed.")
        elif method == "not_removable":
            msg = f"{exp['source_name']}: erasure does not apply — {basis.get('recommended_action')}."
        elif method == "statutory_notice":
            msg = f"{exp['source_name']}: no self-serve route — a statutory notice is warranted."
        else:
            msg = f"{exp['source_name']}: {plan['label'].lower()} ({plan['typical_time']})."

        ctx.emit("legal", "plan", msg,
                 tool_name="plan_removal", tool_output={"method": method})
        return plan

    def match_unique_identifiers() -> dict:
        """Search leak corpora for the user's UNIQUE identifiers — email, phone,
        Aadhaar, PAN, UPI, card. A match on one of these IS proof of identity,
        unlike a name, which thousands of people share."""
        from backend.pii.recognizer import verhoeff_validate, luhn_validate

        p = ctx.profile
        # Each identifier, with whether it can be validated and where it can help.
        raw = [
            ("email",    p.get("email", ""),    None,                "unique"),
            ("phone",    p.get("phone", ""),    None,                "unique"),
            ("aadhaar",  p.get("aadhaar", ""),  "verhoeff",          "unique"),
            ("pan",      p.get("pan", ""),      "pan_format",        "unique"),
            ("upi",      p.get("upi_id", ""),   None,                "unique"),
            ("passport", p.get("passport", ""), None,                "unique"),
        ]

        checked, invalid, supplied = [], [], []
        for kind, value, validator, _ in raw:
            v = (value or "").strip()
            if not v:
                continue
            supplied.append(kind)

            # Validate before searching: a mistyped Aadhaar would search for a
            # number belonging to someone else entirely.
            if validator == "verhoeff":
                digits = "".join(c for c in v if c.isdigit())
                if len(digits) != 12 or not verhoeff_validate(digits):
                    invalid.append({"kind": kind,
                                    "why": "Fails the Verhoeff checksum — not a valid Aadhaar. "
                                           "Check for a typo; searching it would look for "
                                           "somebody else's number."})
                    continue
                v = digits
            elif validator == "pan_format":
                if not re.fullmatch(r"[A-Z]{3}[PCHABFTGJL][A-Z]\d{4}[A-Z]", v.upper()):
                    invalid.append({"kind": kind,
                                    "why": "Not a valid PAN structure (4th character encodes "
                                           "holder type). Check for a typo."})
                    continue
                v = v.upper()
            checked.append((kind, v))

        if not checked:
            ctx.emit("discovery", "identifiers",
                     "No unique identifier supplied to search. Name alone cannot identify you — "
                     "add an email, phone, Aadhaar or PAN.",
                     status="awaiting_approval")
            return {"searched": [], "hits": [], "invalid": invalid,
                    "note": "Nothing unique to search on."}

        ctx.emit("discovery", "identifiers",
                 f"Searching leak corpora for {len(checked)} unique identifier(s): "
                 f"{', '.join(k for k, _ in checked)}…",
                 tool_name="match_unique_identifiers")

        _pastes._load()
        corpus = getattr(_pastes, "_pastes", []) or []

        # The only paste corpus shipped with this project is
        # data/synthetic_pastes/pastes_corpus.json — randomly GENERATED records
        # for fictional people (see data/download_datasets.py
        # generate_synthetic_pastes). A "hit" against it is fabricated by
        # construction, so recording one as evidence_class "verified" /
        # severity "critical" and telling the user it is "proof this record
        # concerns you" asserts something untrue about real people's data.
        # orchestrator.py already keeps this corpus out of the pipeline
        # (out["pastes"] = {"exposures": []}); this tool was the remaining way in.
        #
        # Reporting zero hits instead would be just as wrong — "0 confirmed
        # exposure(s) across 50 leak record(s)" reads as a completed clean
        # search. So when no real corpus is configured the check reports as
        # UNAVAILABLE, per the project's rule that a check which could not
        # actually run never comes back "clear".
        from backend.scanners import paste_scanner as _paste_mod
        corpus_is_synthetic = "synthetic" in str(
            getattr(_paste_mod, "PASTES_FILE", "")).lower()
        searchable = [] if corpus_is_synthetic else corpus

        hits = []
        for kind, value in checked:
            needle = value.lower()
            digits = "".join(c for c in value if c.isdigit())
            for entry in searchable:
                blob = json.dumps(entry, default=str).lower()
                # Concatenating EVERY digit in the record and searching that
                # invented identifiers. A row holding "(1000, ... '2026-08-06"
                # collapses to "...10002026080...", in which a ten-digit window
                # spans three unrelated columns — and a user whose phone equalled
                # that window was told it "appears verbatim" in the dump, which
                # is a false positive and a false proof statement. Every entry in
                # the shipped corpus contains at least one such window. Matching
                # per written number keeps real formatting working without
                # manufacturing a number nobody ever wrote down.
                found = needle in blob
                if not found and len(digits) >= 10:
                    found = any(
                        digits in "".join(c for c in run if c.isdigit())
                        for run in _NUMERIC_RUN_RE.findall(blob))
                if not found:
                    continue
                title = entry.get("title") or entry.get("paste_id") or "leak dump"
                ev = {
                    "check": "unique_identifier_in_leak", "target": f"{kind}",
                    "endpoint": f"(local corpus) {title}",
                    "queried_at": utcnow(), "http_status": None, "result": "hit",
                    "proof": f"Your {kind} appears verbatim in '{title}'.",
                    "interpretation": (
                        f"CONFIRMED: {kind} is unique to you, so a verbatim match is proof "
                        f"this record concerns you — unlike a name match, which is not."),
                    # Never echo any part of the identifier here. This string is
                    # persisted into the exposure's evidence blob and returned by
                    # the API, so `value[:4]` put the first four characters of the
                    # user's Aadhaar or PAN into stored, retrievable data.
                    "reproduce": (f"grep -i '<your {kind}>' "
                                  f"data/synthetic_pastes/pastes_corpus.json"),
                }
                exp = {
                    "source_type": "paste", "source_name": title,
                    "source_id": "leak:" + str(title), "record_id": kind,
                    "data_found": [kind], "detail": {"identifier": kind, "source": title},
                    "match_confidence": 1.0, "match_tier": "definite",
                    "severity": "critical" if kind in ("aadhaar", "pan", "passport") else "high",
                    "risk_score": 0.0,
                    "evidence_class": "verified", "evidence": [ev],
                }
                exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
                hits.append({"exposure_id": exp_id, "identifier": kind,
                             "source": title, "is_new": is_new})
                break   # one hit per identifier is enough to establish exposure

        for bad in invalid:
            ctx.emit("discovery", "identifiers",
                     f"{bad['kind'].upper()} rejected: {bad['why']}", status="error")

        if corpus_is_synthetic:
            ctx.emit("discovery", "identifiers",
                     "Leak-corpus check UNAVAILABLE — no real paste corpus is configured "
                     "(the only one shipped is a synthetic sample), so your identifiers "
                     "could NOT be checked against leak dumps. This is not a clean result.",
                     status="error", tool_output={"hits": 0, "corpus_available": False})
        else:
            ctx.emit("discovery", "identifiers",
                     f"Identifier search complete: {len(hits)} confirmed exposure(s) across "
                     f"{len(searchable)} leak record(s).",
                     tool_output={"hits": len(hits)})

        return {
            "searched": [k for k, _ in checked],
            "supplied": supplied,
            "invalid": invalid,
            "hits": hits,
            "corpus_available": not corpus_is_synthetic,
            "not_checked": ([{"check": "leak_corpus", "why": "No real paste corpus is "
                              "configured; the shipped corpus is synthetic sample data."}]
                            if corpus_is_synthetic else []),
            "corpus_size": len(searchable),
            "where_each_helps": {
                "email": "Identifier-keyed lookups (Gravatar, HIBP), leak matching, and "
                         "corroborating a profile page.",
                "phone": "Leak matching and corroborating a profile page.",
                "upi": "Leak matching and corroborating a profile page.",
                "aadhaar": "Leak matching ONLY. No public profile displays an Aadhaar, so it "
                           "cannot corroborate a web account.",
                "pan": "Leak matching ONLY, for the same reason.",
                "passport": "Leak matching ONLY, for the same reason.",
            },
            "why_unique_matters": (
                "These identifiers have exactly one owner, so a verbatim match proves the "
                "record concerns you. A name does not — it is shared by thousands, which is "
                "why a name is never used as a search key here."),
        }

    def detect_pii_in_text(text: str) -> dict:
        """Run the hybrid PII recogniser (Verhoeff/Luhn-validated) over raw text."""
        ctx.emit("discovery", "pii", "Running PII recogniser over supplied text…",
                 tool_name="detect_pii_in_text")
        ents = _recognizer.recognize(text or "")
        return {
            "entities": [e.to_dict() for e in ents],
            "summary": _recognizer.get_summary(ents),
        }

    def assess_exposure_risk() -> dict:
        """Score every known exposure and compute the overall Privacy Risk Score."""
        ctx.emit("risk", "score", "Computing Privacy Risk Score…", tool_name="assess_exposure_risk")
        exposures = ctx.memory.get_exposures(ctx.user_id)
        live = [e for e in exposures if e["status"] in ("exposed", "requested", "acknowledged", "reappeared")]

        flat = []
        for e in live:
            src = {"breach": "hibp_verified", "data_broker": "data_broker",
                   "paste": "dark_web_paste",
                   "open_web": "open_web_verified",
                   "infostealer": "infostealer"}.get(e["source_type"], "public_search")
            for f in e["data_found"]:
                flat.append({
                    "entity_type": _FIELD_TO_ENTITY.get(f.lower(), f.upper()),
                    "source_type": src,
                    "date_found": (e["detail"] or {}).get("breach_date") or e["discovered_at"],
                    "value": "",
                })

        broker_hits = len([e for e in live if e["source_type"] == "data_broker"])
        assessment = _risk.calculate(flat, broker_hits, len(BROKERS)).to_dict()

        # Persist a per-exposure score so the UI can rank them.
        ranks = {"critical": 95.0, "high": 72.0, "medium": 45.0, "low": 20.0}
        for e in live:
            score = ranks.get((e["severity"] or "low").lower(), 20.0) * max(0.35, e["match_confidence"] or 0.5)
            ctx.memory.update_exposure(e["id"], risk_score=round(score, 1))

        ctx.emit("risk", "score",
                 f"Privacy Risk Score: {assessment['overall_score']} ({assessment['risk_level']}).",
                 tool_output={"score": assessment["overall_score"], "level": assessment["risk_level"]})
        return {
            "overall_score": assessment["overall_score"],
            "risk_level": assessment["risk_level"],
            "breakdown": assessment["breakdown"],
            "recommendations": assessment["recommendations"],
            "live_exposures": len(live),
            "by_severity": {s: len([e for e in live if (e["severity"] or "") == s])
                            for s in ("critical", "high", "medium", "low")},
        }

    def determine_legal_basis(exposure_id: str) -> dict:
        """Decide which statute applies to one exposure and whether erasure is
        available. Call this before drafting a request."""
        if exposure_id in _legal_cache:
            return _legal_cache[exposure_id]

        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}

        ctx.emit("legal", "assess", f"Assessing legal basis for {exp['source_name']}…",
                 tool_name="determine_legal_basis")

        # Resolve the controller. Sandbox records live in BROKERS; user-declared
        # accounts resolve against the Indian registry. Operating companies from
        # breaches or profile lookups resolve against the Fiduciary Directory.
        spec = BROKERS.get(exp["source_id"], {}) or {}
        if not spec:
            sid_part = exp["source_id"].split(":", 1)[1] if ":" in exp["source_id"] else exp["source_id"]
            spec = find_source(sid_part) or find_source(exp["source_name"]) or {}
        if not spec:
            from backend.agent.fiduciary_directory import get_fiduciary_contact
            spec = get_fiduciary_contact(exp["source_name"]) or {}

        user_country = (ctx.profile.get("country") or "IN").upper()
        controller_country = spec.get("country", user_country)
        legal_class = spec.get("legal_class", "")

        # The data principal's own law governs their right to ask; the
        # controller's location decides the regime they must answer under.
        user_j = JURISDICTION_BY_COUNTRY.get(user_country, "dpdp")
        ctrl_j = JURISDICTION_BY_COUNTRY.get(controller_country, user_j)
        jurisdiction = ctrl_j if exp["source_type"] == "data_broker" else user_j

        meta = {j["key"]: j for j in _notices.get_jurisdictions()}.get(jurisdiction, {})

        # ── Is erasure actually available? ───────────────────────────────────
        # In India this is not one question. A people-search site and a High
        # Court judgment both hold your name, but only one of them can be served.
        if legal_class == "judicial_record":
            removable = False
            action = "court_application"
            basis = ("Court record. DPDP s.12 does not reach judicial records — the Act's "
                     "obligations do not displace a court's control of its own proceedings. "
                     "Indian courts have ordered redaction in narrow cases (Delhi HC, Jorawer "
                     "Singh Mundy v. Union of India, 2021, concerning an acquitted party), but "
                     "that requires an application to the court that issued the judgment, not "
                     "a notice to a website.")
            confidence = 0.88

        elif legal_class == "statutory_publication":
            removable = False
            action = "correction_only"
            basis = ("Published pursuant to a legal obligation (Companies Act 2013 filings, "
                     "Representation of the People Act 1950 rolls, or state land-revenue "
                     "records). DPDP s.3(c)(ii) excludes personal data made publicly available "
                     "under such an obligation, so the erasure right in s.12 is not engaged. "
                     "Correction through the prescribed statutory form is available; erasure "
                     "is not. Note that commercial MIRRORS which re-host this data for profit "
                     "are a different matter and can be served.")
            confidence = 0.85

        elif legal_class == "dpdp_limited":
            removable = False
            action = "dispute_or_correct"
            basis = ("A competing statutory retention duty applies (CICRA 2005 for credit "
                     "information, telecom licence conditions, or PMLA KYC records). Erasure "
                     "is not available for the retention period; dispute and correction are.")
            confidence = 0.80

        elif exp["source_type"] == "public_profile":
            removable = True
            action = "request_erasure"
            basis = ("Your own account on a commercial service. The controller processes this "
                     "on consent, so you may withdraw it and require erasure. In practice "
                     "almost every such service offers self-serve deletion, which is faster "
                     "and just as final as a statutory notice.")
            confidence = 0.92

        elif exp["source_type"] == "open_web":
            # search_open_web() records the DOMAIN as source_name and the exact
            # URL as record_id, having fetched the page and found the identifier
            # in it verbatim. Falling through to the catch-all below described
            # that as "an unattributed dump with no identifiable controller" and
            # marked it not_removable — so the strongest evidence the product
            # produces was the one class it told the user it could do nothing
            # about.
            removable = True
            action = "request_erasure"
            basis = (f"A page served by {exp['source_name']} was fetched and the identifier "
                     "found in it verbatim, so the publisher of that page is an identifiable "
                     "controller processing this personal data: DPDP s.12 (and GDPR Art. 17 "
                     "where it applies) reach it. Two carve-outs are worth confirming before "
                     "serving — data published pursuant to a legal obligation is outside the "
                     "Act by s.3(c)(ii), and journalistic publication is treated differently. "
                     "Neither is assumed here.")
            confidence = 0.80

        elif exp["source_type"] == "data_broker":
            removable = True
            action = "request_erasure"
            basis = ("Personal data processed for a commercial profiling or lead-generation "
                     "purpose with no continuing necessity, and consent (where relied upon) "
                     "is withdrawn.")
            confidence = 0.90

        elif exp["source_type"] == "breach":
            from backend.agent.fiduciary_directory import is_darkweb_dump
            if is_darkweb_dump(exp["source_name"]) or is_darkweb_dump(exp["source_id"]):
                removable = False
                action = "secure_accounts"
                basis = ("Historical un-attributed breach dump. Erasure cannot be directed to an "
                         "identifiable corporate controller. The effective remedies are credential "
                         "rotation and active dark-web monitoring.")
                confidence = 0.80
            else:
                removable = True
                action = "request_erasure"
                cname = spec.get("company_name") or exp["source_name"]
                basis = (f"Operating Data Fiduciary ({cname}). While historical leaked copies on "
                         "third-party dark web archives cannot be un-published, you hold a statutory right "
                         "under DPDP Act 2023 s.12 (and GDPR Art. 17) to require the operating fiduciary to "
                         "close your account and completely erase personal data from active and backup systems, "
                         "accompanied by credential rotation.")
                confidence = 0.92

        elif exp["source_type"] == "infostealer":
            # This used to land in the catch-all below, which called it an
            # "unattributed dump" and told the user to MONITOR it. Both halves
            # are wrong: nothing was published, and the credentials are known to
            # an attacker right now, so passive monitoring is the one response
            # that guarantees the compromise persists.
            removable = False
            action = "secure_accounts"
            basis = ("Info-stealer malware ran on the data principal's OWN device and exfiltrated "
                     "the browser credential store live. Nothing was published by a third party, "
                     "so there is no controller for a DPDP s.12 notice to address — and equally, "
                     "this is not something to monitor for republication: the credentials are "
                     "already in an attacker's hands. The remedy is immediate rotation of every "
                     "password saved in that browser (email first, then the SIM/telecom account, "
                     "then banking and UPI), revocation of active sessions and auth tokens, and "
                     "cleaning or rebuilding the infected machine BEFORE the new passwords are "
                     "typed into it. Where a particular service's account was taken over as a "
                     "result, an erasure or account-closure request against that service remains "
                     "available on its own footing.")
            confidence = 0.85

        else:
            removable = False
            action = "monitor"
            basis = ("Data appears in an unattributed dump with no identifiable controller to "
                     "serve, so erasure cannot be directed. Monitor for republication.")
            confidence = 0.75

        result = {
            "exposure_id": exposure_id,
            "source": exp["source_name"],
            "jurisdiction": jurisdiction,
            "statute": meta.get("statute", ""),
            "deadline_days": meta.get("deadline_days", 30),
            "erasure_available": removable,
            "legal_class": legal_class or exp["source_type"],
            "legal_basis": basis,
            "recommended_action": action,
            "confidence": confidence,
            "disclaimer": "Automated privacy-request assistance, not legal advice.",
        }
        # Don't cite a statute at a source that statute cannot reach. Saying
        # "Indian Kanoon: DPDP Act 2023 → court_application" implies the Act
        # governs a court record, which is exactly the confusion to avoid.
        if removable:
            line = f"{exp['source_name']}: {meta.get('short', jurisdiction.upper())} → {action}."
        else:
            why = {
                "judicial_record": "court record, DPDP does not reach it",
                "statutory_publication": "published under legal mandate, s.3(c)(ii) excludes it",
                "dpdp_limited": "statutory retention duty competes",
            }.get(legal_class, "erasure not available against this source type")
            line = f"{exp['source_name']}: NO ERASURE RIGHT ({why}) → {action}."

        ctx.emit("legal", "assess", line,
                 tool_output={"jurisdiction": jurisdiction, "action": action,
                              "erasure_available": removable, "legal_class": legal_class})
        _legal_cache[exposure_id] = result
        return result

    def draft_erasure_request(exposure_id: str, jurisdiction: str = "") -> dict:
        """Draft a statutory erasure notice for one exposure. Does not send it."""
        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}

        from backend.agent.fiduciary_directory import is_darkweb_dump, get_fiduciary_contact
        if exp["source_type"] not in ("data_broker", "breach", "public_profile",
                                      "declared", "open_web"):
            return {"error": "Erasure notices are only servable on an identified controller.",
                    "exposure_id": exposure_id}
        if exp["source_type"] == "breach" and (is_darkweb_dump(exp["source_name"]) or is_darkweb_dump(exp["source_id"])):
            return {"error": "Breach dump has no identifiable corporate controller to serve.",
                    "exposure_id": exposure_id}

        # Re-scanning must not mint a duplicate notice for the same record.
        existing = ctx.memory.open_request_for(exposure_id)
        if existing:
            ctx.emit("action", "draft",
                     f"A notice for {exp['source_name']} is already open "
                     f"({existing['reference_id']}, status {existing['status']}) — reusing it.",
                     tool_output={"request_id": existing["id"]})
            return {
                "request_id": existing["id"], "exposure_id": exposure_id,
                "broker": exp["source_name"], "jurisdiction": existing["jurisdiction"],
                "statute": existing["statute"], "reference_id": existing["reference_id"],
                "receipt_hash": existing["receipt_hash"],
                "deadline_days": existing["deadline_days"],
                "request_text": existing["request_text"], "status": existing["status"],
                "already_existed": True,
            }

        spec = BROKERS.get(exp["source_id"], {}) or {}
        if not spec:
            sid_part = exp["source_id"].split(":", 1)[1] if ":" in exp["source_id"] else exp["source_id"]
            spec = find_source(sid_part) or find_source(exp["source_name"]) or {}
        if not spec:
            spec = get_fiduciary_contact(exp["source_name"]) or {}

        legal_class = spec.get("legal_class", "")
        if legal_class in NON_SERVABLE_CLASSES:
            basis = determine_legal_basis(exposure_id)
            ctx.emit("legal", "refuse",
                     f"Will not draft for {exp['source_name']}: {basis['recommended_action']} "
                     f"— an erasure notice has no addressee in law here.",
                     tool_output={"legal_class": legal_class})
            return {
                "refused": True,
                "exposure_id": exposure_id,
                "source": exp["source_name"],
                "legal_class": legal_class,
                "reason": basis["legal_basis"],
                "recommended_action": basis["recommended_action"],
            }
        if not jurisdiction:
            jurisdiction = determine_legal_basis(exposure_id).get("jurisdiction", "dpdp")

        ctx.emit("action", "draft", f"Drafting {jurisdiction.upper()} notice for {exp['source_name']}…",
                 tool_name="draft_erasure_request")

        pii_summary = ", ".join(sorted(exp["data_found"])) or "personal data"
        gen = _notices.generate(
            jurisdiction=jurisdiction,
            user_name=ctx.profile.get("name", ""),
            user_email=ctx.profile.get("email", ""),
            user_phone=ctx.profile.get("phone", ""),
            additional_ids="",
            company_name=spec.get("company_name") or spec.get("operator") or spec.get("name", exp["source_name"]),
            company_address=spec.get("address") or spec.get("privacy_url", "Corporate Grievance Office"),
            detected_pii_summary=pii_summary,
            ai_tailored=True,
            exposure_context=f"Source: {exp.get('source_name')} ({exp.get('source_type')}). Discovered telemetry: {json.dumps(exp.get('detail') or {})[:200]}",
        )
        if gen.get("status") != "generated":
            return {"error": gen.get("message", "notice generation failed")}

        req_id = ctx.memory.create_request(ctx.user_id, exposure_id, {
            "jurisdiction": jurisdiction,
            "statute": gen.get("statute_cited", ""),
            "legal_basis": pii_summary,
            "request_text": gen.get("notice_text", ""),
            "reference_id": gen.get("reference_id", ""),
            "receipt_hash": gen.get("receipt_hash", ""),
            "deadline_days": gen.get("response_deadline_days", 30),
            "status": "awaiting_approval",
        })
        ctx.pending_approvals[req_id] = exposure_id

        ctx.emit("action", "draft",
                 f"Notice drafted for {spec.get('name', exp['source_name'])} — awaiting user approval.",
                 tool_output={"request_id": req_id}, status="awaiting_approval")
        return {
            "request_id": req_id, "exposure_id": exposure_id,
            "broker": spec.get("name", exp["source_name"]),
            "jurisdiction": jurisdiction, "statute": gen.get("statute_cited", ""),
            "reference_id": gen.get("reference_id", ""),
            "receipt_hash": gen.get("receipt_hash", ""),
            "deadline_days": gen.get("response_deadline_days", 30),
            "request_text": gen.get("notice_text", ""),
            "status": "awaiting_approval",
            "next_step": "Call submit_erasure_request once the user approves.",
        }

    def submit_erasure_request(request_id: str) -> dict:
        """Send a drafted erasure notice to the controller. Requires user approval:
        irreversible outward actions are never taken autonomously."""
        req = ctx.memory.get_request(request_id)
        if not req:
            return {"error": f"No request {request_id}"}
        exp = ctx.memory.get_exposure(req["exposure_id"])
        if not exp:
            return {"error": "Exposure missing for this request."}

        # Approval is carried by the RUN, not by the row. Gating on
        # `req["status"] == "awaiting_approval"` left every other status open:
        # a dispatch that was refused or failed leaves the request at
        # "awaiting_send", and a second, unapproved call then sailed past this
        # check and served the notice. ctx.auto_approve is set only by
        # run_remediation(), which is only reached from /api/agent/approve with
        # the request ids the user explicitly approved — so that, and nothing
        # else, is what authorises an irreversible outward action.
        if not ctx.auto_approve:
            ctx.emit("action", "approval",
                     f"Awaiting user approval to serve notice on {exp['source_name']}.",
                     tool_output={"request_id": request_id}, status="awaiting_approval")
            return {"status": "awaiting_approval", "request_id": request_id,
                    "broker": exp["source_name"],
                    "message": "Blocked pending user approval. The user must approve before dispatch."}

        ctx.emit("action", "dispatch", f"Serving notice on {exp['source_name']}…",
                 tool_name="submit_erasure_request")

        # Real dispatch, by email, to the controller's published grievance
        # officer. The sandbox broker network is only used when the user has
        # explicitly turned it on — it contains synthetic controllers, and
        # "delivered" there means nothing was sent anywhere.
        if not ctx.sandbox:
            detail = exp.get("detail") or {}
            domain = str(detail.get("domain") or "")
            officer = resolve_officer(exp["source_name"], domain)
            reply_to = (ctx.profile.get("email") or "").strip()

            if not officer.primary:
                ctx.emit("action", "dispatch",
                         f"No published grievance-officer address is known for "
                         f"{exp['source_name']}, and one will not be invented. "
                         f"The notice is exported for you to send yourself.",
                         status="error")
            outcome = send_notice(
                notice_text=req.get("request_text") or "",
                recipient=(officer.primary.email if officer.primary else ""),
                reply_to=reply_to,
                approved=True,   # the gate above is the only thing that gets us here
                subject=f"Erasure request under {req.get('statute') or 'DPDP Act 2023'} "
                        f"— ref {request_id}",
                recipient_name=(officer.company_name or exp["source_name"]),
                sender_name=ctx.profile.get("name", ""),
                company_name=officer.company_name or exp["source_name"],
                statute=req.get("statute") or "",
                reference_id=request_id,
                recipient_tier=(officer.primary.tier if officer.primary else ""),
            )
            od = outcome.to_dict()

            # A refusal must still leave the user with something they can act
            # on. The mailer is right to refuse an address it only guessed —
            # a notice carries the user's identifiers, and sending it to an
            # invented domain discloses them to a stranger. But refusing to
            # SEND is not a reason to produce nothing: draft the message, export
            # it, and hand over the candidate addresses so a human can confirm
            # the right one and send it themselves.
            if od.get("status") == "refused":
                # Always hand back the addresses we know of, whether or not the
                # mailer already exported the draft. A refusal tells the user
                # "not this address, unverified" — it is only useful next to the
                # candidates they can check.
                cands = []
                if officer.primary:
                    cands.append(officer.primary.email)
                for a in (officer.to_dict().get("alternates") or []):
                    addr = a.get("email")
                    if addr and addr not in cands:
                        cands.append(addr)
                od["candidate_addresses"] = cands
                od["officer_status"] = officer.status
            if od.get("status") == "refused" and not od.get("eml_path"):
                try:
                    prepared = prepare_notice(
                        notice_text=req.get("request_text") or "",
                        recipient=(officer.primary.email if officer.primary else ""),
                        reply_to=reply_to,
                        subject=f"Erasure request under {req.get('statute') or 'DPDP Act 2023'} "
                                f"— ref {request_id}",
                        sender_name=ctx.profile.get("name", ""),
                        company_name=officer.company_name or exp["source_name"],
                        statute=req.get("statute") or "",
                        reference_id=request_id,
                    )
                    pd = prepared.to_dict() if hasattr(prepared, "to_dict") else {}
                    od["eml_path"] = pd.get("eml_path", "")
                    od["mailto"] = pd.get("mailto_url", "")
                except Exception as exc:
                    od["export_error"] = f"{type(exc).__name__}: {exc}"
            ctx.emit("action", "dispatch",
                     {"sent": f"Notice emailed to {od.get('recipient')} for {exp['source_name']}.",
                      "not_configured": f"No SMTP configured, so nothing was sent. The notice for "
                                        f"{exp['source_name']} is saved as a .eml you can open in "
                                        f"your own mail client: {od.get('eml_path')}",
                      "refused": (f"Not sent — {od.get('reason') or od.get('error') or ''} "
                                  f"The notice is drafted and exported; confirm the controller's "
                                  f"published grievance address and send it yourself: "
                                  f"{od.get('eml_path') or '(export failed)'}"),
                      "failed": f"Send failed: {od.get('error') or ''}"}.get(
                         od.get("status"), f"Dispatch result: {od.get('status')}"),
                     tool_output=od,
                     status="error" if od.get("status") in ("refused", "failed") else "ok")

            ctx.memory.update_request(
                request_id,
                status="submitted" if od.get("status") == "sent" else "awaiting_send",
                submitted_at=utcnow() if od.get("status") == "sent" else None,
                confirmation_id=od.get("message_id", "") or "")
            if od.get("status") == "sent":
                ctx.memory.set_exposure_status(req["exposure_id"], "requested")
            # "status"/"broker" are what every caller keys on (the sandbox
            # branch below returns them). Omitting them here meant the real
            # path — the only one that runs, since ctx.sandbox is always False
            # — always read as "not submitted": the remediation loops in
            # orchestrator.py and multi_agent_swarm.py skipped their follow-up,
            # verification and escalation for every notice, silently.
            sent = od.get("status") == "sent"
            return {"status": "submitted" if sent else "not_sent",
                    "request_id": request_id,
                    "broker": exp["source_name"], "service": exp["source_name"],
                    "dispatch": od, "dispatch_status": od.get("status"),
                    "officer": officer.to_dict(),
                    "smtp": smtp_status(),
                    "note": ("A statutory notice was emailed to the controller's published "
                             "grievance officer." if sent else
                             "Nothing was transmitted. The drafted notice is exported for you "
                             "to send from your own mail client.")}

        res = ctx.network.submit_erasure(
            exp["source_id"], exp["record_id"], ctx.profile.get("email", ""), req["statute"] or "")

        if res.get("status") == "error":
            ctx.memory.update_request(request_id, status="rejected")
            return {"error": res.get("message")}

        ctx.memory.update_request(
            request_id, status="submitted", submitted_at=utcnow(),
            confirmation_id=res.get("broker_request_id", ""))
        ctx.memory.set_exposure_status(req["exposure_id"], "requested")

        ctx.emit("action", "dispatch",
                 f"Notice served on {exp['source_name']} — confirmation {res.get('confirmation_id')}.",
                 tool_output=res)
        return {
            "status": "submitted", "request_id": request_id,
            "broker": exp["source_name"],
            "broker_request_id": res.get("broker_request_id"),
            "confirmation_id": res.get("confirmation_id"),
            "controller_response": res.get("note"),
            "deadline": req["deadline"],
        }

    def check_request_status(request_id: str) -> dict:
        """Poll a submitted request and advance its lifecycle. Counts as a follow-up."""
        req = ctx.memory.get_request(request_id)
        if not req:
            return {"error": f"No request {request_id}"}
        if not req["confirmation_id"]:
            return {"status": req["status"], "message": "Not yet submitted to a controller."}

        ctx.emit("followup", "poll", f"Following up on request {req['reference_id']}…",
                 tool_name="check_request_status")
        res = ctx.network.check_status(req["confirmation_id"])
        # A notice served by EMAIL has no pollable state machine here: its
        # confirmation id is an SMTP Message-ID, which the broker network has
        # never heard of. It answered {"status": "error"}, which mapped to "keep
        # the current status" and was then emitted as "None -> submitted" while
        # incrementing followup_count — a follow-up that never happened, logged
        # against a controller that was never contacted.
        if res.get("status") == "error":
            ctx.emit("followup", "poll",
                     f"No machine-readable status exists for request {req['reference_id']} "
                     f"— {res.get('message')} It remains {req['status']}; the controller's "
                     f"reply, if any, arrives in your own mailbox.",
                     tool_output=res, status="error")
            return {"request_id": request_id, "status": req["status"], "pollable": False,
                    "followups": req["followup_count"] or 0,
                    "note": res.get("message")}
        status_map = {"completed": "completed", "acknowledged": "acknowledged", "submitted": "submitted"}
        new_status = status_map.get(res.get("status", ""), req["status"])

        ctx.memory.update_request(request_id, status=new_status, last_followup=utcnow(),
                                  followup_count=(req["followup_count"] or 0) + 1)
        if new_status == "completed":
            ctx.memory.set_exposure_status(req["exposure_id"], "removed", removed_at=utcnow())

        ctx.emit("followup", "poll",
                 f"{res.get('broker')} → {new_status}.", tool_output=res)
        return {"request_id": request_id, "broker": res.get("broker"), "status": new_status,
                "followups": res.get("followups"), "note": res.get("note")}

    def verify_removal(exposure_id: str) -> dict:
        """Independently re-query the source to confirm the data is actually gone.
        A controller saying 'deleted' is not proof; this checks."""
        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}
        if exp["source_type"] != "data_broker":
            return {"exposure_id": exposure_id, "verifiable": False,
                    "message": "Breach and paste records cannot be un-published; not verifiable."}

        ctx.emit("verification", "verify", f"Re-querying {exp['source_name']} to confirm removal…",
                 tool_name="verify_removal")
        still_there = ctx.network.record_exists(exp["source_id"], exp["record_id"])

        if still_there:
            ctx.emit("verification", "verify", f"{exp['source_name']}: record STILL PRESENT.",
                     tool_output={"present": True})
            return {"exposure_id": exposure_id, "broker": exp["source_name"],
                    "verifiable": True, "still_present": True, "verified_removed": False,
                    "message": "Record is still live. Keep the request open and follow up."}

        ctx.memory.set_exposure_status(exposure_id, "removed", removed_at=exp["removed_at"] or utcnow(),
                                       verified_at=utcnow())
        ctx.emit("verification", "verify", f"{exp['source_name']}: removal VERIFIED — record no longer returned.",
                 tool_output={"present": False})
        return {"exposure_id": exposure_id, "broker": exp["source_name"],
                "verifiable": True, "still_present": False, "verified_removed": True,
                "message": "Independently verified: the record is no longer returned by the source."}

    def escalate_to_regulator(request_id: str) -> dict:
        """Escalate an overdue request to the competent supervisory authority
        (DPBI in India, the supervisory authority under GDPR, CPPA in California)."""
        req = ctx.memory.get_request(request_id)
        if not req:
            return {"error": f"No request {request_id}"}
        exp = ctx.memory.get_exposure(req["exposure_id"])

        authority = {
            "dpdp": "Data Protection Board of India (DPBI)",
            "gdpr": "Lead Supervisory Authority (GDPR Art. 77)",
            "ccpa": "California Privacy Protection Agency (CPPA)",
        }.get(req["jurisdiction"], "Competent supervisory authority")

        deadline = req["deadline"]
        overdue = deadline and deadline < utcnow()

        ctx.emit("followup", "escalate",
                 f"Escalating {exp['source_name'] if exp else request_id} to {authority}…",
                 tool_name="escalate_to_regulator")
        ctx.memory.update_request(request_id, status="escalated")
        ctx.emit("followup", "escalate", f"Escalation lodged with {authority}.",
                 tool_output={"authority": authority})
        return {
            "request_id": request_id, "authority": authority,
            "jurisdiction": req["jurisdiction"], "statute": req["statute"],
            "deadline_passed": bool(overdue), "deadline": deadline,
            "status": "escalated",
            # The grounds must match the facts. This asserted a blown statutory
            # period unconditionally, including on a notice served minutes
            # earlier whose own deadline_passed field said False.
            "grounds": ("Controller failed to respond within the statutory period."
                        if overdue else
                        "Controller has not verifiably complied. The statutory period has not "
                        "yet expired, so this is lodged as a pre-emptive complaint record, not "
                        "as an allegation of a missed deadline."),
        }

    def search_open_web() -> dict:
        """Search the open web for this identity's unique identifiers, then
        fetch every result and confirm the identifier is really on the page."""
        queries = web_search.build_queries(ctx.profile)
        if not queries:
            ctx.emit("discovery", "web",
                     "Open-web search skipped — no unique identifier supplied. A name is "
                     "shared by thousands of people and is never searched.",
                     tool_name="search_open_web")
            return {"confirmed": [], "unconfirmed": [], "searched": 0}

        ctx.emit("discovery", "web",
                 f"Searching the open web for {len(queries)} unique identifier(s): "
                 + ", ".join(q[0] for q in queries[:6]) + ". Every result will be fetched "
                 "and the identifier must appear on the page before anything is reported.",
                 tool_name="search_open_web")

        res = web_search.search_exposures(ctx.profile)
        recorded = []
        for h in res.get("confirmed", []):
            ev = {
                "check": "open_web_search",
                "target": f"{h['identifier_type']}:{h['identifier']}",
                "endpoint": h["url"], "queried_at": h["checked_at"],
                "http_status": h["http_status"], "result": "hit",
                "proof": f"The exact {h['identifier_type']} appears in the page served at "
                         f"{h['url']} — {h['matched_text'][:300]}",
                "interpretation": (
                    f"CONFIRMED: your {h['identifier_type']} is published on {h['domain']}. "
                    f"This was not inferred from a search snippet — the page was fetched and "
                    f"the identifier found in it verbatim."),
                "reproduce": h["reproduce"],
            }
            exp = {
                "source_type": "open_web", "source_name": h["domain"],
                "source_id": "web:" + h["domain"],
                "record_id": h["url"],
                "data_found": [h["identifier_type"]],
                "detail": {"url": h["url"], "title": h["title"], "query": h["query"],
                           "identifier_type": h["identifier_type"],
                           "matched_text": h["matched_text"]},
                "match_confidence": 0.95,
                "match_tier": "proven",
                "severity": "high" if h["identifier_type"] in ("phone", "pan", "upi") else "medium",
                "risk_score": 0.0,
                "evidence_class": "verified",
                "evidence": [ev],
            }
            exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
            recorded.append({"exposure_id": exp_id, "domain": h["domain"], "url": h["url"],
                             "identifier_type": h["identifier_type"], "is_new": is_new})

        degraded = res.get("search_degraded", False)
        ctx.emit("discovery", "web",
                 (f"Open-web search INCOMPLETE — the engine refused "
                  f"{len(res.get('blocked_queries', []))} of {res.get('searched', 0)} "
                  f"query(ies). {len(recorded)} confirmed exposure(s) so far. A clean "
                  f"result cannot be claimed until the search completes."
                  if degraded else
                  f"Open-web search complete: {len(recorded)} confirmed exposure(s) across "
                  f"{len(set(r['domain'] for r in recorded))} domain(s); "
                  f"{len(res.get('unconfirmed', []))} result(s) could not be confirmed and "
                  f"are reported as leads only."),
                 status="error" if degraded else "",
                 tool_output={"confirmed": len(recorded),
                              "unconfirmed": len(res.get("unconfirmed", [])),
                              "search_degraded": degraded})
        return {"confirmed": recorded, "unconfirmed": res.get("unconfirmed", []),
                "queries": res.get("queries", []), "domains": res.get("domains", []),
                "pages_fetched": res.get("pages_fetched", 0),
                "search_degraded": degraded,
                "blocked_queries": res.get("blocked_queries", []),
                "searched": res.get("searched", 0),
                "coverage_note": res.get("coverage_note", ""),
                "method": res.get("method", "")}

    def analyze_threat_surface() -> dict:
        """Perform cross-exposure correlation to map multi-vector attack surfaces:
        credential stuffing risk, spear-phishing exposure, and SIM swap vulnerability.
        Generates an actionable ApniPehChaan defense hardening matrix."""
        exposures = ctx.memory.get_exposures(ctx.user_id)
        p = ctx.profile

        breaches = [e for e in exposures if e.get("source_type") == "breach"]
        passwords_leaked = [e for e in breaches if any("password" in str(d).lower() for d in e.get("data_found", []))]
        resumes_leaked = [e for e in exposures if any(k in str(d).lower() for d in e.get("data_found", [])
                                                      for k in ("salary", "employer", "resume", "cv", "job"))]
        contact_leaked = [e for e in exposures if any(k in str(d).lower() for d in e.get("data_found", [])
                                                      for k in ("phone", "mobile", "address"))]

        vectors = []
        if passwords_leaked:
            vectors.append({
                "vector": "Credential Stuffing & Account Takeover",
                "severity": "critical" if len(passwords_leaked) >= 2 else "high",
                "affected_sources": [b["source_name"] for b in passwords_leaked],
                "threat_model": (f"Plaintext or hashed credentials exposed across {len(passwords_leaked)} service(s). "
                                 "Automated botnets use these to attempt credential stuffing across email providers, "
                                 "banking portals, and cloud services."),
                "mitigation": "Immediately rotate passwords on all services. Enable hardware/TOTP MFA (avoid SMS 2FA)."
            })
        if resumes_leaked:
            vectors.append({
                "vector": "Spear Phishing & Career/Recruitment Fraud",
                "severity": "high",
                "affected_sources": [b["source_name"] for b in resumes_leaked],
                "threat_model": "Employment history, current employer, salary brackets, and work history exposed. "
                                "Adversaries can craft high-credibility spear-phishing emails or fake recruiter offers.",
                "mitigation": "Exercise statutory right to erasure under DPDP s.12 to delete inactive recruitment profiles."
            })
        if contact_leaked and p.get("phone"):
            vectors.append({
                "vector": "SIM Swap & Targeted Vishing / OTP Interception",
                "severity": "high",
                "affected_sources": [b["source_name"] for b in contact_leaked],
                "threat_model": "Mobile number and associated identity details exposed. Enables social engineering "
                                "against telecom operators for SIM duplication or vishing.",
                "mitigation": "Set telecom account PIN/passcode. Move critical 2FA from SMS to authenticator apps."
            })

        result = {
            "user_id": ctx.user_id,
            "total_analyzed_exposures": len(exposures),
            "threat_vectors": vectors,
            "overall_surface_grade": "ELEVATED" if len(vectors) >= 2 else ("MODERATE" if vectors else "MINIMAL"),
            "defense_actions_recommended": len(vectors) + 1,
        }
        ctx.emit("risk", "score",
                 f"Threat Surface Analysis: {len(vectors)} attack vector(s) identified (Grade: {result['overall_surface_grade']}).",
                 tool_name="analyze_threat_surface", tool_output=result)
        return result

    def self_serve_removal(exposure_id: str, list_unsubscribe: str = "",
                           list_unsubscribe_post: str = "") -> dict:
        """Find the exact account-deletion or opt-out route for an exposure, and
        one-click unsubscribe where the message's headers actually support it.
        Unsubscribing is outward-facing, so it needs approval first."""
        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}

        route = resolve_route(exp["source_name"],
                              str((exp.get("detail") or {}).get("domain") or ""))
        rd = route.to_dict()

        out = {"exposure_id": exposure_id, "service": exp["source_name"], "route": rd}

        # A one-click unsubscribe is a property of the individual MESSAGE, not
        # of the service: it exists only when that message carries
        # List-Unsubscribe-Post. So it is never assumed — the headers are read,
        # and a plain RFC 2369 link is returned as something to open rather than
        # POSTed, because POSTing an unadvertised link is outside the standard.
        if list_unsubscribe:
            plan = plan_unsubscribe(list_unsubscribe, list_unsubscribe_post or None)
            pd = plan.to_dict() if hasattr(plan, "to_dict") else {}
            out["unsubscribe_plan"] = pd
            if ctx.auto_approve and pd.get("action") == "one_click_post":
                ctx.emit("action", "unsubscribe",
                         f"One-click unsubscribing from {exp['source_name']}…",
                         tool_name="self_serve_removal")
                res = unsubscribe_one_click(list_unsubscribe, list_unsubscribe_post or None)
                out["unsubscribe_result"] = res.to_dict() if hasattr(res, "to_dict") else {}
            elif pd.get("action") == "one_click_post":
                ctx.emit("action", "approval",
                         f"{exp['source_name']} supports one-click unsubscribe. Approve to send it.",
                         tool_output=pd, status="awaiting_approval")
                out["status"] = "awaiting_approval"

        if rd.get("is_deep_link") and rd.get("url"):
            ctx.emit("remediation", "self_serve",
                     f"{exp['source_name']}: delete directly at {rd['url']} "
                     f"(~{rd.get('effort_minutes', '?')} min).",
                     tool_output=rd)
        else:
            ctx.emit("remediation", "self_serve",
                     f"{exp['source_name']}: no verified self-serve deletion link is known, so "
                     f"none is invented. " + (rd.get("why") or rd.get("method") or ""),
                     tool_output=rd)
        return out

    def confirm_removal(exposure_id: str) -> dict:
        """Check whether a profile actually stopped being served after a deletion.
        A removal nobody verified is a claim, not an outcome."""
        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}
        detail = exp.get("detail") or {}
        url = detail.get("url") or ""
        if not url:
            return {"exposure_id": exposure_id, "result": "not_checkable",
                    "why": "No public profile URL was recorded for this exposure."}
        chk = verify_gone(url, site=exp["source_name"], username=exp.get("record_id") or "")
        cd = chk.to_dict() if hasattr(chk, "to_dict") else {}
        ctx.emit("verify", "removal",
                 f"Re-checked {exp['source_name']}: {cd.get('result', 'unknown')}.",
                 tool_output=cd)
        return {"exposure_id": exposure_id, "service": exp["source_name"], "check": cd}

    return {
        "build_identity_profile": build_identity_profile,
        "recall_prior_activity": recall_prior_activity,
        "verify_breach_exposure": verify_breach_exposure,
        "verify_password_exposure": verify_password_exposure,
        "declare_known_accounts": declare_known_accounts,
        "browse_indian_registry": browse_indian_registry,
        "discover_accounts": discover_accounts,
        "confirm_account": confirm_account,
        "plan_removal": plan_removal,
        "self_serve_removal": self_serve_removal,
        "confirm_removal": confirm_removal,
        "search_data_brokers": search_data_brokers,
        "search_paste_dumps": search_paste_dumps,
        "search_open_web": search_open_web,
        "match_unique_identifiers": match_unique_identifiers,
        "detect_pii_in_text": detect_pii_in_text,
        "assess_exposure_risk": assess_exposure_risk,
        "determine_legal_basis": determine_legal_basis,
        "draft_erasure_request": draft_erasure_request,
        "submit_erasure_request": submit_erasure_request,
        "check_request_status": check_request_status,
        "verify_removal": verify_removal,
        "escalate_to_regulator": escalate_to_regulator,
        "analyze_threat_surface": analyze_threat_surface,
    }


_FIELD_TO_ENTITY = {
    "aadhaar": "AADHAAR", "pan": "PAN", "credit_card": "CREDIT_CARD",
    "credit_cards": "CREDIT_CARD", "bank_account": "BANK_ACCOUNT",
    # Passwords were mapped onto CREDIT_CARD to borrow its weight. They now
    # carry their own, because a password is a different kind of loss: a card
    # can be reissued, and a password reused elsewhere cannot be recalled.
    "passwords": "PASSWORD", "password": "PASSWORD",
    "auth_token": "AUTH_TOKEN", "session_cookies": "AUTH_TOKEN",
    "security_question": "SECURITY_ANSWER",
    "government_id": "GOVERNMENT_ID", "passport": "PASSPORT", "ssn": "SSN",
    "date_of_birth": "DATE_OF_BIRTH", "dates_of_birth": "DATE_OF_BIRTH",
    "religion": "SPECIAL_CATEGORY", "sexual_preference": "SPECIAL_CATEGORY",
    "ethnicity": "SPECIAL_CATEGORY", "health": "SPECIAL_CATEGORY",
    "biometric": "SPECIAL_CATEGORY",
    "private_message": "PRIVATE_MESSAGE", "income": "INCOME",
    "employer": "EMPLOYER", "vehicle": "VEHICLE",
    "social_profile": "NAME", "photo": "NAME", "gender": "NAME",
    "email": "EMAIL", "email_addresses": "EMAIL",
    "phone": "PHONE_IN", "phone_numbers": "PHONE_IN",
    "address": "ADDRESS", "physical_addresses": "ADDRESS",
    "name": "NAME", "names": "NAME", "username": "NAME", "usernames": "NAME",
    "city": "PIN_CODE", "ip_address": "IP_ADDRESS", "ip_addresses": "IP_ADDRESS",
    "upi": "UPI", "ifsc": "IFSC",
}
