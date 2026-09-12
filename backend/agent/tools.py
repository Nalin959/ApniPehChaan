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

from backend.agent import verifiers
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
    "address": "high", "phone": "high", "date_of_birth": "high",
    "email": "medium", "employer": "medium", "username": "medium",
    "city": "low", "name": "low", "age_range": "low", "interests": "low",
}


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


def find_source(slug_or_name: str) -> dict | None:
    """Look up a source in the Indian registry by id or name (case-insensitive)."""
    needle = (slug_or_name or "").strip().lower()
    for src in load_indian_sources():
        if needle in (src["id"].lower(), src["name"].lower()):
            return src
    for src in load_indian_sources():
        if needle and needle in src["name"].lower():
            return src
    return None


# ── tool implementations ─────────────────────────────────────────────────────

def build_tools(ctx: ToolContext) -> dict[str, Callable]:
    """Return {tool_name: callable}. Closures capture the run context."""

    def build_identity_profile() -> dict:
        """Normalise the user's identity and derive likely aliases with confidence
        scores. Run this first: later searches use the aliases it produces."""
        ctx.emit("identity", "profile", "Normalising identity and deriving aliases…")
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

        # The demo environment plants synthetic records. That is fabrication, so
        # it only happens when the user explicitly turns the sandbox on.
        seeded = ctx.network.seed_for_profile(p) if ctx.sandbox else 0

        result = {
            "user_id": ctx.user_id,
            "name": name, "email": email,
            "phone": p.get("phone", ""), "city": p.get("city", ""),
            "country": p.get("country", "IN"),
            "aliases": aliases,
            "sandbox_enabled": ctx.sandbox,
            "sandbox_records_seeded": seeded,
        }
        ctx.emit("identity", "profile",
                 f"Identity resolved: {len(aliases)} alias(es) derived.",
                 tool_output={"aliases": [a["alias"] for a in aliases]})
        return result

    def recall_prior_activity() -> dict:
        """Recall what was already found and done for this user in earlier runs.
        Use this to avoid re-requesting removals that are already in flight."""
        ctx.emit("orchestrator", "memory", "Recalling prior runs for this identity…")
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

        checks = [
            verifiers.check_hibp_account(email),
            verifiers.check_email_domain_breached(email, _hibp._breaches),
            verifiers.check_gravatar(email),
        ]

        recorded, not_checked = [], []
        for ev in checks:
            if ev.result == "not_checked":
                not_checked.append({"check": ev.check, "why": ev.interpretation})
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

            elif ev.check == "gravatar":
                exp = {
                    "source_type": "public_profile", "source_name": "Gravatar",
                    "source_id": "gravatar", "record_id": "",
                    "data_found": ["email", "photo"], "detail": {"evidence": ev.to_dict()},
                    "match_confidence": 1.0, "match_tier": "definite",
                    "severity": "medium", "risk_score": 0.0,
                    "evidence_class": "verified", "evidence": [ev.to_dict()],
                }
                exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
                recorded.append({"exposure_id": exp_id, "source": "Gravatar",
                                 "evidence_class": "verified", "is_new": is_new})

        domain_ev = next(c for c in checks if c.check == "email_domain_breached")
        ctx.emit("discovery", "breach",
                 f"Breach checks complete: {len(recorded)} VERIFIED exposure(s), "
                 f"{len(not_checked)} check(s) unavailable.",
                 tool_output={"verified": len(recorded), "not_checked": len(not_checked)})

        return {
            "verified_exposures": recorded,
            "checks_run": [c.to_dict() for c in checks],
            "not_checked": not_checked,
            "domain_context": domain_ev.to_dict(),
            "note": ("Only checks that returned a positive hit became exposures. Where a check "
                     "could not run, that is reported as not_checked — no membership is guessed."),
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
        """Search the data-broker network for records matching this identity.
        Returns removable records, each with a record_id usable for erasure."""
        if not ctx.sandbox:
            ctx.emit("discovery", "broker",
                     "Skipping the broker sandbox — it contains synthetic records, not real "
                     "findings. Use declare_known_accounts for services you actually hold.")
            return {"removable_records": [],
                    "sandbox_enabled": False,
                    "note": ("The simulated broker network is OFF. No Indian people-search site "
                             "publishes an API to check whether it holds a given person, and "
                             "probing them would breach their terms — so nothing is guessed.")}

        ctx.emit("discovery", "broker",
                 "Scanning the SANDBOX broker network (synthetic records)…",
                 tool_name="search_data_brokers")
        p = ctx.profile
        hits = ctx.network.search(name=p.get("name", ""), email=p.get("email", ""), phone=p.get("phone", ""))

        recorded = []
        for h in hits:
            fields = list(h["exposed_fields"].keys())
            candidate = {
                "name": h["exposed_fields"].get("name", ""),
                "email": h["exposed_fields"].get("email", ""),
                "phone": h["exposed_fields"].get("phone", ""),
                "city": h["exposed_fields"].get("city", ""),
            }
            match = _resolver.resolve(
                {"name": p.get("name", ""), "email": p.get("email", ""),
                 "phone": p.get("phone", ""), "city": p.get("city", "")},
                candidate).to_dict()

            exp = {
                "source_type": "data_broker",
                "source_name": h["broker_name"],
                "source_id": h["broker_id"],
                "record_id": h["record_id"],
                "data_found": fields,
                "detail": h,
                "match_confidence": match.get("overall_score", 0.0),
                "match_tier": match.get("confidence_label", ""),
                "severity": _severity_of(fields),
                "risk_score": 0.0,
                "evidence_class": "sandbox",
                "evidence": [{
                    "check": "sandbox_broker_query", "target": h["broker_name"],
                    "endpoint": f"(simulated) {h['broker_id']}",
                    "queried_at": utcnow(), "http_status": None, "result": "hit",
                    "proof": f"Synthetic record {h['record_id']} in the demo environment.",
                    "interpretation": ("SANDBOX. This record was generated by this application to "
                                       "demonstrate the removal lifecycle. It is not evidence "
                                       "about any real person."),
                    "reproduce": "",
                }],
            }
            exp_id, is_new = ctx.memory.record_exposure(ctx.user_id, ctx.run_id, exp)
            recorded.append({
                "exposure_id": exp_id, "broker_id": h["broker_id"], "broker": h["broker_name"],
                "record_id": h["record_id"], "category": h["category"], "country": h["country"],
                "exposed_fields": fields, "severity": exp["severity"],
                "match_confidence": round(match.get("overall_score", 0.0), 3),
                "match_tier": match.get("confidence_label", ""), "is_new": is_new,
            })

        # Breadth signal from the real 956-broker Optery directory (not removable).
        directory = _optery.scan(p.get("name", ""), p.get("email", ""), p.get("phone", ""), p.get("city", ""))
        ctx.emit("discovery", "broker",
                 f"Broker scan complete: {len(recorded)} removable record(s) located.",
                 tool_output={"removable": len(recorded)})
        indian = load_indian_sources()
        return {
            "removable_records": recorded,
            "directory_context": {
                "optery_brokers_indexed": directory.get("stats", {}).get("total_brokers_checked", 0),
                "indian_sources_indexed": len(indian),
                "indian_sources_erasable": len([x for x in indian
                                                if x.get("legal_class") == "dpdp_erasure"]),
                "note": ("Optery gives global breadth (US-weighted). The Indian registry covers "
                         "the domestic surface with its legal classification. Only the demo "
                         "network is actually removable."),
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
                   "paste": "dark_web_paste"}.get(e["source_type"], "public_search")
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
            ctx.memory._exec("UPDATE exposures SET risk_score=? WHERE id=?", (round(score, 1), e["id"]))

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
        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}

        ctx.emit("legal", "assess", f"Assessing legal basis for {exp['source_name']}…",
                 tool_name="determine_legal_basis")

        # Resolve the controller. Sandbox records live in BROKERS; user-declared
        # accounts resolve against the Indian registry. Missing this second path
        # meant a declared "Indian Kanoon" was treated as an ordinary broker and
        # got an erasure notice drafted against a court record.
        spec = BROKERS.get(exp["source_id"], {}) or {}
        if not spec and exp["source_id"].startswith("declared:"):
            spec = find_source(exp["source_id"].split(":", 1)[1]) or \
                   find_source(exp["source_name"]) or {}

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

        elif exp["source_type"] == "data_broker":
            removable = True
            action = "request_erasure"
            basis = ("Personal data processed for a commercial profiling or lead-generation "
                     "purpose with no continuing necessity, and consent (where relied upon) "
                     "is withdrawn.")
            confidence = 0.90

        elif exp["source_type"] == "breach":
            removable = False
            action = "secure_accounts"
            basis = ("Historical breach record. Erasure is not available against a breach "
                     "corpus — the data is already replicated beyond any single controller. "
                     "The effective remedies are credential rotation and monitoring.")
            confidence = 0.80

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
        return result

    def draft_erasure_request(exposure_id: str, jurisdiction: str = "") -> dict:
        """Draft a statutory erasure notice for one exposure. Does not send it."""
        exp = ctx.memory.get_exposure(exposure_id)
        if not exp:
            return {"error": f"No exposure {exposure_id}"}
        if exp["source_type"] != "data_broker":
            return {"error": "Erasure notices are only servable on an identified controller.",
                    "exposure_id": exposure_id}

        spec = BROKERS.get(exp["source_id"], {}) or {}
        if not spec and exp["source_id"].startswith("declared:"):
            spec = find_source(exp["source_id"].split(":", 1)[1]) or \
                   find_source(exp["source_name"]) or {}
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
            company_name=spec.get("name", exp["source_name"]),
            company_address=spec.get("privacy_url", ""),
            detected_pii_summary=pii_summary,
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

        if not ctx.auto_approve and req["status"] == "awaiting_approval":
            ctx.emit("action", "approval",
                     f"Awaiting user approval to serve notice on {exp['source_name']}.",
                     tool_output={"request_id": request_id}, status="awaiting_approval")
            return {"status": "awaiting_approval", "request_id": request_id,
                    "broker": exp["source_name"],
                    "message": "Blocked pending user approval. The user must approve before dispatch."}

        ctx.emit("action", "dispatch", f"Serving notice on {exp['source_name']}…",
                 tool_name="submit_erasure_request")
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
            "grounds": "Controller failed to respond within the statutory period.",
        }

    return {
        "build_identity_profile": build_identity_profile,
        "recall_prior_activity": recall_prior_activity,
        "verify_breach_exposure": verify_breach_exposure,
        "verify_password_exposure": verify_password_exposure,
        "declare_known_accounts": declare_known_accounts,
        "browse_indian_registry": browse_indian_registry,
        "search_data_brokers": search_data_brokers,
        "search_paste_dumps": search_paste_dumps,
        "detect_pii_in_text": detect_pii_in_text,
        "assess_exposure_risk": assess_exposure_risk,
        "determine_legal_basis": determine_legal_basis,
        "draft_erasure_request": draft_erasure_request,
        "submit_erasure_request": submit_erasure_request,
        "check_request_status": check_request_status,
        "verify_removal": verify_removal,
        "escalate_to_regulator": escalate_to_regulator,
    }


_FIELD_TO_ENTITY = {
    "aadhaar": "AADHAAR", "pan": "PAN", "credit_card": "CREDIT_CARD",
    "credit_cards": "CREDIT_CARD", "bank_account": "BANK_ACCOUNT",
    "passwords": "CREDIT_CARD", "password": "CREDIT_CARD",
    "email": "EMAIL", "email_addresses": "EMAIL",
    "phone": "PHONE_IN", "phone_numbers": "PHONE_IN",
    "address": "ADDRESS", "physical_addresses": "ADDRESS",
    "name": "NAME", "names": "NAME", "username": "NAME", "usernames": "NAME",
    "city": "PIN_CODE", "ip_address": "IP_ADDRESS", "ip_addresses": "IP_ADDRESS",
    "upi": "UPI", "ifsc": "IFSC",
}
