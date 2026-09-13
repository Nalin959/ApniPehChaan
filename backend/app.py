"""
app.py — ApniPehChaan: FastAPI Backend Server.

Main server providing REST API endpoints and WebSocket for real-time
scan feed. Orchestrates all scanner, PII, and remediation modules.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load .env before any module reads an environment variable — the LLM planner
# and the HIBP check both switch on purely by variable presence.
from backend.agent.env import load_env, status as env_status  # noqa: E402
load_env()

from backend.scanners.hibp_scanner import HIBPScanner
from backend.scanners.broker_scanner import BrokerScanner
from backend.scanners.paste_scanner import PasteScanner
from backend.pii.recognizer import PIIRecognizer
from backend.pii.resolver import IdentityResolver
from backend.pii.risk_calculator import RiskCalculator
from backend.remediation.notice_generator import NoticeGenerator
from backend.remediation.audit_crypto import AuditTrail
from backend.remediation.statutory_tracker import StatutoryTracker
from backend.agent.supabase_memory import SupabaseUnavailable

# ─── Global Instances ──────────────────────────────────────────────────────────

hibp_scanner = HIBPScanner()
broker_scanner = BrokerScanner()
paste_scanner = PasteScanner()
pii_recognizer = PIIRecognizer()
identity_resolver = IdentityResolver()
risk_calculator = RiskCalculator()
notice_generator = NoticeGenerator()
from backend.agent.memory import get_memory as _get_memory_for_audit
audit_trail = AuditTrail(store=_get_memory_for_audit())
statutory_tracker = StatutoryTracker()

# ─── WebSocket Manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    """Manages WebSocket connections for real-time scan updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

ws_manager = ConnectionManager()


# ─── FastAPI App ───────────────────────────────────────────────────────────────

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("=" * 60)
    print("  ApniPehChaan — Server Starting")
    print("=" * 60)
    print(f"  Breaches loaded:   {hibp_scanner.get_breach_count()}")
    print(f"  Data brokers:      {broker_scanner.get_broker_count()}")
    print(f"  Paste corpus:      {paste_scanner.get_paste_count()}")
    print(f"  Jurisdictions:     {len(notice_generator.get_jurisdictions())}")
    _env = env_status()
    print("-" * 60)
    from backend.agent.orchestrator import planner_mode as _pm, planner_model as _pmod
    _mode = _pm()
    print(f"  Planner:           {_mode}"
          + (f" ({_pmod()})" if _pmod() else
             "  (set ANTHROPIC_API_KEY or GEMINI_API_KEY in .env)"))
    print(f"  Breach checks:     {_env['breach_checks']}"
          + ("" if _env["breach_checks"] == "ENABLED" else "  (set HIBP_API_KEY in .env)"))
    print("=" * 60)
    yield
    # Shutdown
    print("ApniPehChaan — Server Stopped")


app = FastAPI(
    title="ApniPehChaan",
    description="Digital Identity & Sovereign Privacy Protection Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# allow_credentials must stay False. Starlette cannot honour "*" together with
# credentials (the Fetch spec forbids it), so it silently switches to echoing
# the caller's Origin back with Access-Control-Allow-Credentials: true —
# verified: a request from https://evil.example carrying a cookie came back
# with "Access-Control-Allow-Origin: https://evil.example". That is a strictly
# more permissive policy than the wildcard it looks like. Nothing here
# authenticates with cookies or an Authorization header, so no caller needs
# credentialed CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# The cloud store answering 5xx (or not answering) is a dependency outage, not
# a bug in the request: it used to escape urllib as HTTPError and surface as an
# opaque HTTP 500, e.g. POST /api/agent/scan dying on a Supabase 504.
@app.exception_handler(SupabaseUnavailable)
async def _storage_unavailable(request: Request, exc: SupabaseUnavailable):
    return JSONResponse(
        status_code=503,
        content={"error": "storage_unavailable",
                 "detail": "The persistence backend is unreachable. Nothing was recorded; "
                           "retry shortly.",
                 "cause": str(exc)},
    )

# Mount frontend static files
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    aadhaar: str = ""
    pan: str = ""
    city: str = ""

class NoticeRequest(BaseModel):
    jurisdiction: str = "dpdp"
    user_name: str = ""
    user_email: str = ""
    user_phone: str = ""
    additional_ids: str = ""
    company_name: str = ""
    company_email: str = ""
    company_address: str = ""
    detected_pii_summary: str = ""
    ai_tailored: bool = True
    exposure_context: str = ""

class LegalChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    jurisdiction: str = "dpdp"
    company_name: str = ""
    company_email: str = ""
    company_address: str = ""
    user_name: str = ""
    user_email: str = ""
    user_phone: str = ""
    detected_pii: str = ""
    current_notice: str = ""

class TrackRequest(BaseModel):
    jurisdiction: str = "dpdp"
    company_name: str = ""
    company_email: str = ""
    user_name: str = ""
    user_email: str = ""
    notice_reference: str = ""
    receipt_hash: str = ""

class StatusUpdate(BaseModel):
    request_id: str
    status: str
    note: str = ""

class PIITestRequest(BaseModel):
    text: str = ""


# ─── Routes: Frontend ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main SPA frontend."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>ApniPehChaan</h1><p>Frontend not found. Place files in /frontend/</p>")


# ─── Routes: System Info ──────────────────────────────────────────────────────

@app.get("/api/status")
async def system_status():
    """Return system health and dataset statistics."""
    return {
        "status": "operational",
        "agent": "ApniPehChaan",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "datasets": {
            "hibp_breaches": hibp_scanner.get_breach_count(),
            "data_brokers": broker_scanner.get_broker_count(),
            "paste_corpus": paste_scanner.get_paste_count(),
            "jurisdictions": len(notice_generator.get_jurisdictions()),
        },
        "audit_trail": {
            "total_receipts": audit_trail.get_count(),
            "chain_valid": audit_trail.verify_chain()["chain_valid"],
        },
        "compliance_tracker": statutory_tracker.get_summary(),
    }


@app.get("/api/datasets/summary")
async def dataset_summary():
    """Return summary of all loaded datasets."""
    return {
        "breaches": {
            "count": hibp_scanner.get_breach_count(),
            "top_10": hibp_scanner.get_top_breaches(10),
        },
        "brokers": {
            "count": broker_scanner.get_broker_count(),
            "categories": broker_scanner.get_categories(),
        },
        "pastes": {
            "count": paste_scanner.get_paste_count(),
        },
        "jurisdictions": notice_generator.get_jurisdictions(),
    }


# ─── Scanning helpers ─────────────────────────────────────────────────────────

def _breach_entity_type(data_class: str) -> str:
    """
    Map a HIBP breach data class onto the PII entity type it actually is.

    A leaked password used to be reported here as entity_type "CREDIT_CARD",
    with the comment "elevate severity". It did not even do that — the risk
    calculator weights PASSWORD at 9.0 and CREDIT_CARD at 8.5 — but it did put
    "CREDIT_CARD" into risk_assessment.exposures_by_severity and trip the
    recommendation "URGENT: Credit card numbers detected in breach data.
    Contact your bank immediately to block and reissue affected cards" for a
    user whose card was never in the breach. Report what leaked.
    """
    dc = (data_class or "").lower()
    # Order matters: "Email addresses", "IP addresses" and "Physical addresses"
    # all contain "address", and the old chain resolved all three to ADDRESS.
    for needles, entity in (
        (("password",), "PASSWORD"),
        (("auth token", "session token"), "AUTH_TOKEN"),
        (("security question", "security answer"), "SECURITY_ANSWER"),
        (("email",), "EMAIL"),
        (("ip address",), "IP_ADDRESS"),
        (("phone", "mobile"), "PHONE_IN"),
        (("physical address", "geographic location", "home address"), "ADDRESS"),
        (("date of birth", "dates of birth", "age group"), "DATE_OF_BIRTH"),
        (("credit card", "payment card"), "CREDIT_CARD"),
        (("bank account",), "BANK_ACCOUNT"),
        (("passport",), "PASSPORT"),
        (("government issued id", "national id"), "GOVERNMENT_ID"),
        (("social security",), "SSN"),
        (("private message", "chat log"), "PRIVATE_MESSAGE"),
        (("income", "salar"), "INCOME"),
        (("employer", "job title"), "EMPLOYER"),
        (("vehicle", "licence plate", "license plate"), "VEHICLE"),
        (("username", "screen name"), "USERNAME"),
        (("name", "salutation"), "NAME"),
    ):
        if any(n in dc for n in needles):
            return entity
    # Anything unrecognised keeps its own label and so carries the risk
    # calculator's neutral default weight. Falling back to "EMAIL" asserted
    # that an email address had leaked for classes like "Genders",
    # "Purchases" and "Browser user agent details" — 170 distinct data
    # classes in the catalogue all reported as the same exposure.
    return (data_class or "UNKNOWN").strip().upper().replace(" ", "_") or "UNKNOWN"


# The legacy /api/scan/* and /ws/scan endpoints read
# data/synthetic_pastes/pastes_corpus.json, which download_datasets.py
# GENERATES: invented people with invented Aadhaar, PAN and account numbers.
# Whatever attribution rule the scanner applies, a record that was fabricated
# by a generator was never about this user, so it cannot be one of their
# exposures. This layer used to fold every entity out of every "matching"
# record straight into the user's exposure list with source_type
# "dark_web_paste" — strangers' invented identifiers presented as the user's
# confirmed dark-web leaks, and fed into the risk score and the audit receipt.
#
# The endpoints stay (they are documented and their dataset counts are used by
# /api/status), but they no longer attribute anything from this corpus. The
# live agent path — /api/agent/scan and /ws/agent — is untouched.
SYNTHETIC_PASTE_DISCLOSURE = (
    "The bundled paste corpus under data/synthetic_pastes/ is generated test data, "
    "not a real leak archive. Records from it are never attributed to a user, "
    "never scored, and never written to the audit trail. Use the Privacy Agent "
    "(/api/agent/scan) for real, evidence-backed discovery."
)


def _non_attributing_paste_result(result: dict) -> dict:
    """Keep the corpus statistics; drop every attributed match."""
    return {
        "status": "synthetic_corpus_not_attributed",
        "matches": [],
        "attributed": False,
        "disclosure": SYNTHETIC_PASTE_DISCLOSURE,
        "corpus_records_scanned": (result or {}).get("stats", {}).get("total_pastes_checked",
                                                                     paste_scanner.get_paste_count()),
    }


# ─── Routes: Scanning ─────────────────────────────────────────────────────────

@app.post("/api/scan/full")
async def full_scan(req: ScanRequest):
    """
    Run a full privacy scan across all sources.

    Returns combined results from HIBP, data brokers, and dark-web pastes,
    with risk assessment and recommendations.
    """
    user_profile = {
        "name": req.name,
        "email": req.email,
        "phone": req.phone,
        "aadhaar": req.aadhaar,
        "pan": req.pan,
    }

    # Run all scans
    hibp_results = hibp_scanner.scan(req.email, req.name)
    broker_results = broker_scanner.scan(req.name, req.email, req.phone, req.city)
    paste_results = _non_attributing_paste_result(paste_scanner.scan(user_profile))

    # Aggregate exposures for risk calculation
    exposures = []

    for breach in hibp_results.get("breaches", []):
        for dc in breach.get("data_classes", []):
            exposures.append({
                "entity_type": _breach_entity_type(dc),
                "source_type": "hibp_verified",
                "date_found": breach.get("breach_date"),
                "value": f"[from {breach.get('name', 'unknown breach')}]",
            })

    # Nothing from the synthetic paste corpus enters `exposures`: see
    # SYNTHETIC_PASTE_DISCLOSURE above.

    # Calculate risk
    broker_matches = broker_results.get("stats", {}).get("high_risk_matches", 0)
    total_brokers = broker_results.get("stats", {}).get("total_brokers_checked", 0)
    risk_assessment = risk_calculator.calculate(exposures, broker_matches, total_brokers)

    # Create audit receipt
    receipt = audit_trail.add("FULL_SCAN_COMPLETED", {
        "user_email_hash": __import__('hashlib').sha256(req.email.encode()).hexdigest()[:16] if req.email else "none",
        "breaches_found": len(hibp_results.get("breaches", [])),
        "paste_matches": 0,
        "broker_matches": broker_matches,
        "risk_score": risk_assessment.overall_score,
    })

    return {
        "status": "scan_complete",
        "timestamp": datetime.now().isoformat(),
        "hibp": hibp_results,
        "brokers": broker_results,
        "pastes": paste_results,
        "risk_assessment": risk_assessment.to_dict(),
        "audit_receipt": receipt.to_dict(),
        "summary": {
            "total_breaches": len(hibp_results.get("breaches", [])),
            "total_paste_matches": 0,
            "total_broker_matches": broker_matches,
            "risk_score": risk_assessment.overall_score,
            "risk_level": risk_assessment.risk_level,
        },
        "disclosure": SYNTHETIC_PASTE_DISCLOSURE,
    }


@app.post("/api/scan/hibp")
async def scan_hibp(req: ScanRequest):
    """Scan HIBP breach database only."""
    result = hibp_scanner.scan(req.email, req.name)
    receipt = audit_trail.add("HIBP_SCAN", {"email_hash": __import__('hashlib').sha256(req.email.encode()).hexdigest()[:16] if req.email else "none"})
    result["audit_receipt"] = receipt.to_dict()
    return result


@app.post("/api/scan/brokers")
async def scan_brokers(req: ScanRequest):
    """Scan data broker directory only."""
    result = broker_scanner.scan(req.name, req.email, req.phone, req.city)
    receipt = audit_trail.add("BROKER_SCAN", {"brokers_checked": result.get("stats", {}).get("total_brokers_checked", 0)})
    result["audit_receipt"] = receipt.to_dict()
    return result


@app.post("/api/scan/pastes")
async def scan_pastes(req: ScanRequest):
    """Scan dark-web paste corpus only."""
    user_profile = {"name": req.name, "email": req.email, "phone": req.phone, "aadhaar": req.aadhaar, "pan": req.pan}
    result = _non_attributing_paste_result(paste_scanner.scan(user_profile))
    receipt = audit_trail.add("PASTE_SCAN", {"matches_found": 0, "corpus": "synthetic"})
    result["audit_receipt"] = receipt.to_dict()
    return result


# ─── Routes: PII Detection ────────────────────────────────────────────────────

@app.post("/api/pii/detect")
async def detect_pii(req: PIITestRequest):
    """Run PII detection on arbitrary text."""
    entities = pii_recognizer.recognize(req.text)
    summary = pii_recognizer.get_summary(entities)
    return {
        "text_length": len(req.text),
        "entities": [e.to_dict() for e in entities],
        "summary": summary,
    }


@app.get("/api/pii/benchmark")
async def run_pii_benchmark():
    """
    Run the PII recognizer against the ground-truth benchmark dataset
    and return precision, recall, and F1 metrics.
    """
    benchmark_path = os.path.join(PROJECT_ROOT, "data", "benchmarks", "pii_ground_truth.json")
    try:
        with open(benchmark_path, "r") as f:
            samples = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Benchmark dataset not found")

    results = []
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    category_metrics = {}

    for sample in samples:
        text = sample.get("text", "")
        expected = sample.get("expected_entities", [])
        category = sample.get("category", "unknown")

        detected = pii_recognizer.recognize(text)

        # Compare detected vs expected
        expected_types = set(e["type"] for e in expected)
        detected_types = set(e.entity_type for e in detected)

        tp = len(expected_types & detected_types)
        fp = len(detected_types - expected_types)
        fn = len(expected_types - detected_types)

        true_positives += tp
        false_positives += fp
        false_negatives += fn

        # Track per-category
        if category not in category_metrics:
            category_metrics[category] = {"tp": 0, "fp": 0, "fn": 0}
        category_metrics[category]["tp"] += tp
        category_metrics[category]["fp"] += fp
        category_metrics[category]["fn"] += fn

        results.append({
            "id": sample.get("id", ""),
            "category": category,
            "expected_types": list(expected_types),
            "detected_types": list(detected_types),
            "tp": tp, "fp": fp, "fn": fn,
            "correct": fp == 0 and fn == 0,
        })

    # Compute aggregate metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # Per-category metrics
    per_category = {}
    for cat, m in category_metrics.items():
        p = m["tp"] / (m["tp"] + m["fp"]) if (m["tp"] + m["fp"]) > 0 else 0
        r = m["tp"] / (m["tp"] + m["fn"]) if (m["tp"] + m["fn"]) > 0 else 0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0
        per_category[cat] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "samples": m["tp"] + m["fn"]}

    receipt = audit_trail.add("PII_BENCHMARK_RUN", {
        "samples": len(samples),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    })

    return {
        "total_samples": len(samples),
        "aggregate": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
        },
        "per_category": per_category,
        "sample_results": results[:50],  # First 50 detailed
        "audit_receipt": receipt.to_dict(),
    }


# ─── Routes: Legal Remediation ────────────────────────────────────────────────

@app.get("/api/legal/jurisdictions")
async def get_jurisdictions():
    """List available jurisdictions for legal notices."""
    return notice_generator.get_jurisdictions()


@app.post("/api/legal/generate")
async def generate_notice(req: NoticeRequest):
    """Generate a statutory legal erasure notice."""
    # ai_tailored=True makes a blocking LLM call inside notice_generator.
    result = await asyncio.to_thread(
        notice_generator.generate,
        jurisdiction=req.jurisdiction,
        user_name=req.user_name,
        user_email=req.user_email,
        user_phone=req.user_phone,
        additional_ids=req.additional_ids,
        company_name=req.company_name,
        company_address=req.company_address,
        detected_pii_summary=req.detected_pii_summary,
        ai_tailored=req.ai_tailored,
        exposure_context=req.exposure_context,
    )

    if result.get("status") == "generated":
        audit_trail.add("NOTICE_GENERATED", {
            "reference_id": result.get("reference_id"),
            "jurisdiction": req.jurisdiction,
            "company": req.company_name,
            "ai_generated": result.get("ai_generated", False),
            "ai_model": result.get("ai_model"),
        })

    return result


@app.post("/api/legal/chat")
async def legal_chat(req: LegalChatRequest):
    """
    Interactive Legal Counsel Chatbot for Statutory Notice Studio.
    Grounds legal drafting, amends notices, cites penalty schedules, and drafts formal notices.
    Works dynamically for any unknown or user-specified company.
    """
    user_msg = (req.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    from backend.agent.openai_compat_planner import get_llm_completion
    from backend.remediation.notice_generator import JURISDICTIONS
    import re
    import hashlib
    from datetime import datetime, timedelta

    jurisdiction_info = JURISDICTIONS.get(req.jurisdiction.lower(), JURISDICTIONS["dpdp"])
    statute_name = jurisdiction_info.get("name", "Digital Personal Data Protection Act, 2023")
    statute_cite = jurisdiction_info.get("statute", "Sections 12 & 13, DPDP Act 2023")
    escalation_body = jurisdiction_info.get("escalation_body", "Data Protection Board of India (DPBI)")
    default_deadline = jurisdiction_info.get("response_deadline_days", 30)

    user_name = req.user_name.strip() or "Data Principal"
    user_email = req.user_email.strip() or "[User Email on Record]"
    user_phone = req.user_phone.strip() or "[User Phone on Record]"
    
    company_name = req.company_name.strip()
    company_email = req.company_email.strip()
    company_address = req.company_address.strip()

    # Dynamic company detection: extract ANY unknown or named company from user prompt
    patterns = [
        r"(?:change|switch|update|set)\s*(?:the)?\s*(?:target|company|fiduciary|entity)?\s*(?:name)?\s*(?:to|as)\s+([A-Za-z0-9\s\.\,\&\|\-\'\"]+)",
        r"(?:target|company|fiduciary)\s*[:=]\s*([A-Za-z0-9\s\.\,\&\|\-\'\"]+)",
        r"(?:draft|write|create|send|issue|generate)?\s*(?:a|an)?\s*(?:statutory)?\s*(?:notice|demand|letter)\s*(?:for|to|against|regarding)\s+([A-Za-z0-9\s\.\,\&\|\-\'\"]+?)(?:\s+(?:under|citing|demanding|with|for|in|based|\.|\n|$)|$)",
        r"(?:notice|demand|erasure)\s*(?:for|to|against)\s+([A-Za-z0-9\s\.\,\&\|\-\'\"]+?)(?:\s+(?:under|citing|demanding|with|for|in|based|\.|\n|$)|$)",
    ]
    for pat in patterns:
        m = re.search(pat, user_msg, re.IGNORECASE)
        if m:
            cand = m.group(1).strip(" \"'.,:;")
            cand_lower = cand.lower()
            stop_words = {"the company", "them", "data fiduciary", "this company", "notice", "me", "dpdp", "gdpr", "ccpa", "more legal terms", "legal terms", "penalties", "7 days", "immediate", "erasure"}
            if cand and cand_lower not in stop_words and len(cand) >= 2:
                company_name = cand
                break

    if not company_name or company_name == "[Target Data Fiduciary / Company]":
        company_name = "Data Fiduciary"

    company_email = company_email if company_email and company_email != "[Privacy / Grievance Officer Email]" else ""
    company_address = company_address or ""

    system_prompt = f"""You are the Senior Statutory Legal Counsel and Automated Notice Drafting Specialist at ApniPehChaan.
You assist users in understanding data protection legislation and drafting legally airtight, binding data erasure and privacy compliance notices.

PRIMARY STATUTORY FRAMEWORKS:
1. India: Digital Personal Data Protection (DPDP) Act, 2023
   - Section 12: Right to correction and erasure of personal data.
   - Section 13: Right of grievance redressal (mandatory response within reasonable/prescribed period).
   - Section 33 & Schedule: Penalties up to ₹250 Crores for significant breaches / non-compliance, enforced by the Data Protection Board of India (DPBI).
2. European Union: General Data Protection Regulation (GDPR)
   - Article 17: Right to erasure ('Right to be Forgotten').
   - Article 19: Notification obligation regarding erasure.
   - Article 83: Administrative fines up to €20,000,000 or 4% of worldwide annual turnover.
3. California: California Consumer Privacy Act / CPRA (Cal. Civ. Code § 1798.105 / § 1798.120).

CURRENT CONTEXT:
- Active Jurisdiction: {req.jurisdiction.upper()} ({statute_name})
- Statutory Citation: {statute_cite}
- Regulatory Escalation Authority: {escalation_body}
- Target Company / Data Fiduciary: {company_name}
- Privacy Officer Email: {company_email}
- User (Data Principal): {user_name} (Email: {user_email}, Phone: {user_phone})
- Detected PII / Scope of Erasure: {req.detected_pii or 'Compromised personal data including contact information and identifiers'}
- Current Notice in Editor: {f'Present ({len(req.current_notice)} characters)' if req.current_notice else 'None'}

COMPANY DISCOVERY & INTEL:
- Companies will often be arbitrary or unknown entities. Do not rely on fixed hardcoded rosters.
- As the Statutory Counsel Agent, determine the entity's exact corporate name, appropriate Grievance Officer / DPO email (e.g. grievance@domain, privacy@domain, or dpo@domain), and registered office address.
- At the very start of your reply, ALWAYS output a metadata block:
<<<TARGET_META>>>
COMPANY_NAME: [Official Corporate Entity Name]
COMPANY_EMAIL: [Grievance / DPO Email]
COMPANY_ADDRESS: [Corporate Headquarters / Grievance Redressal Office]
<<<END_TARGET_META>>>

RULES:
1. If the user asks to DRAFT, AMEND, TIGHTEN, REWRITE, ADD CLAUSES, or SHORTEN DEADLINES for the notice:
   - Provide a concise legal briefing (1-2 short paragraphs) in Markdown explaining the statutory strategy applied.
   - Output the COMPLETE, formal, professional statutory notice text enclosed strictly between:
<<<START_NOTICE>>>
[Complete formal statutory notice here, including Date, Reference ID, Addressee, Governing Legal Grounds, Specific PII to Erase, Third-Party Processor Audit demand, Written Confirmation Timeline, and Penalties for Non-Compliance]
<<<END_NOTICE>>>
2. If the user asks a STATUTORY QUESTION or seeks legal counsel:
   - Answer directly and authoritatively in clear Markdown.
   - Cite specific statutory sections, rights, and regulatory penalty amounts.
   - Explain how they can enforce compliance through ApniPehChaan.
3. Maintain an authoritative, commanding legal tone protecting the fundamental privacy rights of the data principal.
"""

    messages = [{"role": "system", "content": system_prompt}]
    for h in (req.history or [])[-6:]:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_msg})

    # Every LLM call below goes out through the SYNCHRONOUS OpenAI/Anthropic
    # clients, and get_llm_completion walks a list of providers x candidate models,
    # each a full blocking round-trip. Called directly from an `async def` that
    # froze the whole event loop for the duration — one chat message stalled every
    # other request on the server, the live /ws/agent trace included, and a
    # rate-limited key turned that into tens of seconds. They run on a worker
    # thread now.
    llm_res, model_used = await asyncio.to_thread(
        get_llm_completion,
        messages=messages,
        max_tokens=1400,
        temperature=0.2,
    )

    if not llm_res:
        # Graceful fallback: generate notice or provide statutory answer
        if any(w in user_msg.lower() for w in ["draft", "notice", "generate", "write", "create", "letter", "demand"]):
            gen = await asyncio.to_thread(
                notice_generator.generate,
                jurisdiction=req.jurisdiction,
                user_name=user_name,
                user_email=user_email,
                user_phone=user_phone,
                company_name=company_name,
                company_address=company_address,
                detected_pii_summary=req.detected_pii,
                ai_tailored=False,
            )
            notice_txt = gen.get("notice_text", "")
            return {
                "reply": f"I have generated a formal statutory erasure notice under **{statute_cite}** addressed to **{company_name}**. You can review and apply it directly to your notice preview.",
                "has_notice": True,
                "notice_text": notice_txt,
                "reference_id": gen.get("reference_id"),
                "receipt_hash": gen.get("receipt_hash"),
                "response_deadline_days": gen.get("response_deadline_days", default_deadline),
                "response_deadline": gen.get("response_deadline"),
                "jurisdiction": req.jurisdiction,
                "company_name": company_name,
                "company_email": company_email,
                "company_address": company_address,
                "model": "deterministic_counsel_engine",
                "suggested_prompts": [
                    "Add ₹250 Cr DPDP penalty warning",
                    "Reduce deadline to 7 business days",
                    "Demand third-party processor erasure confirmation"
                ]
            }
        else:
            return {
                "reply": f"Under **{statute_cite}**, data fiduciaries must comply with erasure requests within **{default_deadline} days**. Failure to comply can be escalated to the **{escalation_body}** with statutory penalties up to ₹250 Crores under Schedule 1 of the DPDP Act 2023.",
                "has_notice": False,
                "company_name": company_name,
                "company_email": company_email,
                "company_address": company_address,
                "model": "deterministic_counsel_engine",
                "suggested_prompts": [
                    f"Draft statutory notice for {company_name}",
                    "What are the penalties under Section 33?",
                    "How do I file a complaint with DPBI?"
                ]
            }

    # Extract dynamic company metadata resolved by the AI agent
    meta_match = re.search(r"<<<TARGET_META>>>\s*(.*?)\s*<<<END_TARGET_META>>>", llm_res, re.DOTALL)
    if meta_match:
        meta_block = meta_match.group(1)
        llm_res = (llm_res[:meta_match.start()] + "\n" + llm_res[meta_match.end():]).strip()
        for line in meta_block.splitlines():
            line = line.strip()
            if line.startswith("COMPANY_NAME:"):
                val = line.split(":", 1)[1].strip()
                if val and not val.startswith("[") and val.lower() != "data fiduciary":
                    company_name = val
            elif line.startswith("COMPANY_EMAIL:"):
                val = line.split(":", 1)[1].strip()
                if val and "@" in val and not val.startswith("["):
                    company_email = val
            elif line.startswith("COMPANY_ADDRESS:"):
                val = line.split(":", 1)[1].strip()
                if val and not val.startswith("["):
                    company_address = val

    # Check for notice delimiters in LLM response
    has_notice = False
    notice_text = ""
    clean_reply = llm_res

    match = re.search(r"<<<START_NOTICE>>>\s*(.*?)\s*<<<END_NOTICE>>>", llm_res, re.DOTALL)
    if match:
        has_notice = True
        notice_text = match.group(1).strip()
        # Clean reply removes the delimited block
        clean_reply = (llm_res[:match.start()] + "\n" + llm_res[match.end():]).strip()
        if not clean_reply:
            clean_reply = f"I have drafted the tailored statutory erasure demand for **{company_name}** citing **{statute_cite}**. You can review and apply it directly to your live notice editor."

    ref_id = f"SP-{req.jurisdiction.upper()}-{datetime.utcnow().strftime('%Y%m%d')}-{hashlib.sha256((company_name + user_msg).encode()).hexdigest()[:8].upper()}"
    receipt_hash = hashlib.sha256(notice_text.encode('utf-8')).hexdigest() if notice_text else ""
    deadline_date = (datetime.utcnow() + timedelta(days=default_deadline)).strftime('%Y-%m-%d')

    if has_notice:
        audit_trail.add("LEGAL_CHATBOT_DRAFT", {
            "reference_id": ref_id,
            "company": company_name,
            "jurisdiction": req.jurisdiction,
            "model": model_used
        })

    return {
        "reply": clean_reply,
        "has_notice": has_notice,
        "notice_text": notice_text,
        "reference_id": ref_id,
        "receipt_hash": receipt_hash,
        "response_deadline_days": default_deadline,
        "response_deadline": deadline_date,
        "jurisdiction": req.jurisdiction,
        "company_name": company_name,
        "company_email": company_email,
        "company_address": company_address,
        "model": model_used,
        "suggested_prompts": [
            "Add ₹250 Cr DPDP penalty warning" if req.jurisdiction == "dpdp" else "Cite GDPR Article 83 maximum fines",
            "Reduce deadline to 7 business days",
            "Demand sub-processor and cloud backup purge",
            "Switch to GDPR Article 17" if req.jurisdiction != "gdpr" else "Switch to DPDP Act 2023"
        ]
    }


@app.post("/api/legal/dispatch")
async def dispatch_notice(req: TrackRequest):
    """
    Simulate dispatching a legal notice and begin compliance tracking.
    """
    # Create tracked request
    tracked = statutory_tracker.create_request(
        jurisdiction=req.jurisdiction,
        company_name=req.company_name,
        company_email=req.company_email,
        user_name=req.user_name,
        user_email=req.user_email,
        notice_reference=req.notice_reference,
        receipt_hash=req.receipt_hash,
    )

    # Create audit receipt for dispatch
    receipt = audit_trail.add("NOTICE_DISPATCHED", {
        "request_id": tracked["request_id"],
        "jurisdiction": req.jurisdiction,
        "company": req.company_name,
        "deadline": tracked["deadline"],
    })

    return {
        "status": "dispatched",
        "message": f"Legal notice dispatched to {req.company_name}. Statutory {tracked['deadline_days']}-day countdown initiated.",
        "tracked_request": tracked,
        "audit_receipt": receipt.to_dict(),
    }


# ─── Routes: Compliance Tracking ──────────────────────────────────────────────

@app.get("/api/compliance/requests")
async def get_all_requests():
    """Get all tracked erasure requests."""
    return {
        "requests": statutory_tracker.get_all_requests(),
        "summary": statutory_tracker.get_summary(),
    }


@app.get("/api/compliance/request/{request_id}")
async def get_request(request_id: str):
    result = statutory_tracker.get_request(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    return result


@app.post("/api/compliance/update")
async def update_request_status(req: StatusUpdate):
    """Update the status of a tracked request."""
    result = statutory_tracker.update_status(req.request_id, req.status, req.note)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")

    audit_trail.add("REQUEST_STATUS_UPDATED", {
        "request_id": req.request_id,
        "new_status": req.status,
        "note": req.note,
    })
    return result


@app.get("/api/compliance/overdue")
async def get_overdue():
    """Get overdue requests that need escalation."""
    return {"overdue": statutory_tracker.get_overdue_requests()}


# ─── Routes: Audit Trail ──────────────────────────────────────────────────────

@app.get("/api/audit/trail")
async def get_audit_trail():
    """Get the full cryptographic audit trail."""
    return {
        "receipts": audit_trail.get_all(),
        "verification": audit_trail.verify_chain(),
    }


@app.get("/api/audit/latest")
async def get_latest_audit(n: int = 10):
    """Get the latest N audit receipts."""
    return {
        "receipts": audit_trail.get_latest(n),
        "total": audit_trail.get_count(),
    }


@app.get("/api/audit/verify")
async def verify_audit_chain():
    """Verify the integrity of the entire audit chain."""
    return audit_trail.verify_chain()


# ─── WebSocket: Real-time Scan Feed ───────────────────────────────────────────

@app.websocket("/ws/scan")
async def websocket_scan(websocket: WebSocket):
    """
    WebSocket endpoint for real-time scan progress.

    Client sends a user profile, server streams scan steps in real-time.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("action") == "start_scan":
                profile = data.get("profile", {})

                # Stream scan steps
                async def send_step(step: str, detail: str, progress: int):
                    await websocket.send_json({
                        "type": "scan_step",
                        "step": step,
                        "detail": detail,
                        "progress": progress,
                        "timestamp": datetime.now().isoformat(),
                    })

                await send_step("init", "Initializing privacy scan engine...", 5)
                await asyncio.sleep(0.3)

                await send_step("hibp_start", f"Querying HIBP breach database ({hibp_scanner.get_breach_count()} breaches)...", 10)
                await asyncio.sleep(0.5)
                hibp_results = hibp_scanner.scan(profile.get("email", ""), profile.get("name", ""))
                breach_count = len(hibp_results.get("breaches", []))
                await send_step("hibp_done", f"HIBP scan complete: {breach_count} breach matches found", 30)
                await asyncio.sleep(0.3)

                await send_step("broker_start", f"Scanning Optery data broker directory ({broker_scanner.get_broker_count()} brokers)...", 35)
                await asyncio.sleep(0.5)
                broker_results = broker_scanner.scan(
                    profile.get("name", ""), profile.get("email", ""),
                    profile.get("phone", ""), profile.get("city", "")
                )
                broker_matches = broker_results.get("stats", {}).get("high_risk_matches", 0)
                await send_step("broker_done", f"Broker scan complete: {broker_matches} high-risk matches", 55)
                await asyncio.sleep(0.3)

                await send_step("paste_start", f"Scanning dark-web paste corpus ({paste_scanner.get_paste_count()} entries)...", 60)
                await asyncio.sleep(0.5)
                paste_results = _non_attributing_paste_result(paste_scanner.scan(profile))
                paste_matches = 0
                await send_step("paste_done",
                                "Dark-web corpus is synthetic test data — no matches attributed", 75)
                await asyncio.sleep(0.3)

                await send_step("risk_calc", "Computing Privacy Risk Score...", 80)
                await asyncio.sleep(0.3)

                # Aggregate exposures
                # Identical classification to POST /api/scan/full. This loop
                # used to label EVERY data class "EMAIL", so the same profile
                # scored differently over the socket than over REST, and a
                # breach of passwords and addresses was reported as three
                # separate email exposures.
                exposures = []
                for breach in hibp_results.get("breaches", []):
                    for dc in breach.get("data_classes", []):
                        exposures.append({
                            "entity_type": _breach_entity_type(dc),
                            "source_type": "hibp_verified",
                            "date_found": breach.get("breach_date"),
                            "value": f"[{breach.get('name', '')}]",
                        })
                # The synthetic paste corpus contributes nothing — see
                # SYNTHETIC_PASTE_DISCLOSURE.

                risk = risk_calculator.calculate(exposures, broker_matches, broker_results.get("stats", {}).get("total_brokers_checked", 0))

                receipt = audit_trail.add("WS_FULL_SCAN_COMPLETED", {
                    "breaches": breach_count,
                    "paste_matches": paste_matches,
                    "broker_matches": broker_matches,
                    "risk_score": risk.overall_score,
                })

                await send_step("complete", "Privacy scan complete!", 100)
                await asyncio.sleep(0.2)

                # Send final results
                await websocket.send_json({
                    "type": "scan_complete",
                    "results": {
                        "hibp": hibp_results,
                        "brokers": broker_results,
                        "pastes": paste_results,
                        "risk_assessment": risk.to_dict(),
                        "audit_receipt": receipt.to_dict(),
                        "summary": {
                            "total_breaches": breach_count,
                            "total_paste_matches": paste_matches,
                            "total_broker_matches": broker_matches,
                            "risk_score": risk.overall_score,
                            "risk_level": risk.risk_level,
                        },
                        "disclosure": SYNTHETIC_PASTE_DISCLOSURE,
                    },
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        # Say why before hanging up. Swallowing this closed the socket in
        # mid-scan with no frame at all, so the client could not tell a crash
        # apart from a network drop and sat on a progress bar for ever.
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Scan failed: {type(exc).__name__}: {exc}",
            })
        except Exception:
            pass
        ws_manager.disconnect(websocket)


# ─── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[PROJECT_ROOT],
    )


# ══════════════════════════════════════════════════════════════════════════════
#  AGENTIC LAYER
#
#  Everything above this line is the deterministic engine: scanners, PII
#  recognition, notice templates, the audit chain. Everything below exposes the
#  privacy AGENT that plans over those capabilities as tools — discovering
#  exposure, judging what is actionable, choosing a statute, drafting notices,
#  dispatching on approval, following up, and verifying removal independently.
# ══════════════════════════════════════════════════════════════════════════════

import asyncio as _asyncio
import queue as _queue
import threading as _threading

from backend.agent.memory import get_memory
from backend.agent.orchestrator import (
    EventStream, run_discovery, run_remediation, planner_mode, planner_model, MODEL,
)
from backend.mock_brokers.network import get_network

_memory = get_memory()
_network = get_network()


class AgentScanRequest(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    country: str = "IN"
    # Services the user says they hold an account with. Their own knowledge is
    # valid grounds for a DPDP s.12 request, and needs no scraping.
    declared_accounts: str = ""
    # Optional. Checked k-anonymously — only a 5-char SHA-1 prefix is sent.
    # `password` is the original single-value field; `passwords` carries every
    # credential the user entered. Both are checked, de-duplicated.
    password: str = ""
    passwords: list[str] = []

    # ── Optional corroborating identifiers ──
    # All optional. Each one lets more candidate profiles be resolved in either
    # direction, which is the whole trade: more identifiers, fewer strangers
    # misattributed to you.
    alt_emails: str = ""         # other addresses you use
    alt_phones: str = ""         # other numbers you use
    known_usernames: str = ""    # handles you know are yours; "site:handle" scopes one
    date_of_birth: str = ""      # YYYY-MM-DD
    upi_id: str = ""             # e.g. yourname@okaxis
    websites: str = ""           # personal sites that link back to you
    # Guess handles from the email local-part and the legal name. Off by
    # default: neither is unique. nalinchamp@gmail.com and nalinchamp@yahoo.com
    # are different people, and a name is shared by thousands — so every guessed
    # hit stays an unconfirmed candidate for ever.
    search_guessed_handles: bool = False
    # Never stored or transmitted in the clear — hashed on arrival and used only
    # to match against local leak corpora. No public profile displays these, so
    # they do nothing for account attribution.
    pan: str = ""
    aadhaar: str = ""
    passport: str = ""
    card_last4: str = ""


class AgentApproveRequest(AgentScanRequest):
    request_ids: list[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: str = "user"
    content: str = ""


class AgentChatRequest(BaseModel):
    message: str = ""
    history: list[ChatMessage] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)


def _all_passwords(req: AgentScanRequest) -> list[str]:
    """Every supplied credential, order preserved, de-duplicated. Empty strings
    are dropped so a blank field cannot be checked as if it were a password."""
    out: list[str] = []
    for p in [req.password, *(req.passwords or [])]:
        if p and p not in out:
            out.append(p)
    return out


def _profile_of(req: AgentScanRequest) -> dict:
    return {"name": req.name, "email": req.email, "phone": req.phone,
            "city": req.city, "country": req.country or "IN",
            "declared_accounts": req.declared_accounts, "password": req.password,
            "passwords": _all_passwords(req),
            "alt_emails": req.alt_emails, "alt_phones": req.alt_phones,
            "known_usernames": req.known_usernames, "date_of_birth": req.date_of_birth,
            "upi_id": req.upi_id, "websites": req.websites,
            "search_guessed_handles": bool(req.search_guessed_handles),
            "pan": req.pan, "aadhaar": req.aadhaar, "passport": req.passport,
            "card_last4": req.card_last4}


# Anything that can identify a person to search for. A request carrying none
# of them has nothing to scan: it used to run the whole pipeline anyway and
# mint an "anonymous" user row (on the cloud backend, a production row) whose
# results belonged to no one and were then served to the next caller of
# /api/agent/latest.
_IDENTIFIER_FIELDS = ("email", "phone", "name", "declared_accounts", "known_usernames",
                      "alt_emails", "alt_phones", "upi_id", "websites",
                      "pan", "aadhaar", "passport", "card_last4")


def _require_identifier(req: "AgentScanRequest") -> None:
    if not any(str(getattr(req, f, "") or "").strip() for f in _IDENTIFIER_FIELDS):
        raise HTTPException(
            status_code=400,
            detail=("At least one identifier is required — an email, phone, name, "
                    "declared account or known username. There is nothing to search for."),
        )


def _owned_request_ids(user_id: str, request_ids: list[str]) -> None:
    """
    Refuse to dispatch a notice drafted for somebody else.

    /api/agent/approve took request_ids on trust, and /api/agent/latest hands
    the most recent user's request ids to any caller — so anyone could read an
    id there and then have a statutory erasure notice served in that person's
    name by approving it under their own profile. Approval has to be approval
    BY the data principal the notice is for.
    """
    for rid in request_ids:
        row = _memory.get_request(rid)
        if not row:
            raise HTTPException(status_code=404, detail=f"Unknown request {rid}.")
        if row.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail=f"Request {rid} was drafted for a different data principal.")


def _dashboard_state(user_id: str) -> dict:
    """Everything the UI needs to render the agent's current picture."""
    exposures = _memory.get_exposures(user_id)
    requests = _memory.get_requests(user_id)
    exp_by_id = {e["id"]: e for e in exposures}
    for r in requests:
        exp = exp_by_id.get(r["exposure_id"])
        r["source_name"] = exp["source_name"] if exp else ""
        r["source_type"] = exp["source_type"] if exp else ""
    return {
        "user_id": user_id,
        "summary": _memory.user_summary(user_id),
        "exposures": exposures,
        "requests": requests,
        "identities": _memory.get_identities(user_id),
        "removal_plan": _removal_plan(user_id, exposures),
    }


def _removal_plan(user_id: str, exposures: list[dict]) -> dict:
    """
    The action plan, grouped by how the data actually comes down.

    This is the part the user acts on. Most entries are a link and three steps,
    not a legal notice — because most services have a delete button, and serving
    a statutory notice on one of those wastes a month to achieve what a link
    achieves in three minutes.
    """
    from backend.agent.tools import find_playbook, load_playbooks

    info = load_playbooks().get("method_info", {})
    order = load_playbooks().get("method_order", [])
    groups: dict[str, list] = {}

    for e in exposures:
        # Unconfirmed candidates and rejected profiles never enter the plan —
        # acting on them would mean requesting deletion of someone else's data.
        if e["status"] in ("removed", "unconfirmed", "not_mine"):
            continue
        pb = find_playbook(e["source_name"], (e["source_id"] or "").split(":")[-1])
        method = (pb or {}).get("method")
        if not method:
            method = "statutory_notice" if e["source_type"] == "data_broker" else "not_removable"
        groups.setdefault(method, []).append({
            "exposure_id": e["id"],
            "source": e["source_name"],
            "evidence_class": e["evidence_class"],
            "url": (pb or {}).get("url", "") or (e["detail"] or {}).get("url", ""),
            "profile_url": (e["detail"] or {}).get("url", ""),
            "effort_minutes": (pb or {}).get("effort_minutes"),
            "steps": (pb or {}).get("steps", []),
            "escalation": (pb or {}).get("escalation", ""),
            "status": e["status"],
        })

    total_minutes = sum(
        (item.get("effort_minutes") or 0)
        for m in ("self_serve", "privacy_form", "email_request")
        for item in groups.get(m, [])
    )
    return {
        "groups": [
            {"method": m, **info.get(m, {}), "items": groups[m]}
            for m in order if m in groups
        ],
        "self_serve_count": len(groups.get("self_serve", [])),
        "needs_notice_count": len(groups.get("statutory_notice", [])),
        "not_removable_count": len(groups.get("not_removable", [])),
        "estimated_minutes": total_minutes,
        "principle": ("A statutory notice is the escalation, not the opening move. "
                      "Where a service offers deletion directly, that is the route."),
    }


def _live_tool_names() -> list[str]:
    """Names straight from build_tools, so this can never drift from reality."""
    from unittest.mock import MagicMock
    from backend.agent.tools import ToolContext, build_tools
    probe = ToolContext(memory=MagicMock(), network=MagicMock(), user_id="", run_id="",
                        profile={}, emit=lambda *a, **k: None)
    return sorted(build_tools(probe).keys())


@app.get("/api/agent/info")
async def agent_info():
    """Which planner is driving the agent, and what it can do."""
    mode = planner_mode()
    notes = {
        "anthropic": "Claude is planning each step and choosing tools.",
        "openai_compat": "The configured model is planning each step and choosing tools.",
        "deterministic": ("No planner key configured — running the deterministic pipeline "
                          "over the identical tools. Set ANTHROPIC_API_KEY or GEMINI_API_KEY "
                          "in .env to enable live planning."),
    }
    return {
        "planner": mode,
        "model": planner_model(),
        "llm_active": mode in ("anthropic", "openai_compat"),
        "note": notes.get(mode, ""),
        # Derived from the live registry, not hand-maintained — a stale hardcoded
        # list here previously reported 13 tools when 16 were registered.
        "tools": _live_tool_names(),
        "evidence_policy": {
            "rule": ("No source is reported as holding your data unless a live check returned "
                     "a hit, or you declared the account yourself."),
            "classes": {
                "verified": "A live endpoint was queried and returned a positive hit; proof attached.",
                "self_declared": "You stated you hold this account. Valid grounds under DPDP s.12.",
            },
            "free_checks": [
                "xposedornot_breached_account (breach membership, no key)",
                "infostealer_infection (Hudson Rock Cavalier, no key)",
                "hibp_pwned_passwords (k-anonymous, no key)",
                "gravatar",
                "hibp_breach_catalog",
                "open_web_search (identifier verified on the fetched page)",
            ],
            "needs_key": {"hibp_breached_account":
                          "Set HIBP_API_KEY (~$3.95/mo) to add Have I Been Pwned as a SECOND "
                          "breach corpus. Not required: breach membership is answered for free "
                          "by XposedOrNot. Without an HIBP key this one check reports "
                          "not_checked — it is never guessed, and never silently merged with "
                          "the free dataset's answer."},
            "not_attempted": ("Indian people-search sites publish no API for this, and probing "
                              "signup or password-reset endpoints to enumerate accounts would "
                              "breach their terms. The tool asks the user instead."),
        },
        "human_in_the_loop": "submit_erasure_request is withheld until the user approves.",
    }


@app.get("/api/agent/brokers")
async def agent_brokers():
    """Live statutory directory disclosure."""
    return {
        "environment": "live",
        "disclosure": ("100% Real Data · Zero synthetic records. Operates exclusively on verified "
                       "breach intelligence, live web discovery, and statutory registers under DPDP Act 2023."),
        "brokers": [],
    }


@app.get("/api/agent/state/{user_id}")
async def agent_state(user_id: str):
    if not _memory.get_user(user_id):
        raise HTTPException(status_code=404, detail="Unknown user")
    return _dashboard_state(user_id)


@app.get("/api/agent/latest")
async def agent_latest():
    """Return dashboard state for the most recently active user."""
    row = _memory._row("SELECT user_id FROM runs ORDER BY started_at DESC LIMIT 1")
    if not row:
        row = _memory._row("SELECT id as user_id FROM users ORDER BY created_at DESC LIMIT 1")
    if not row or not row.get("user_id"):
        return {"user_id": None, "exposures": [], "requests": [], "summary": {}}
    return _dashboard_state(row["user_id"])



@app.get("/api/agent/events/{run_id}")
async def agent_events(run_id: str):
    return {"run_id": run_id, "events": _memory.get_events(run_id)}


def _get_chat_suggestions(tab: str, user_msg: str) -> list[dict]:
    suggestions = []
    low = (user_msg or "").lower()
    if "scan" in low or "check" in low:
        suggestions.append({"label": "Deploy Privacy Agent", "action": "navigate_tab", "tab": "agent"})
    if "exposure" in low or "breach" in low or "leak" in low:
        suggestions.append({"label": "View Discovered Exposures", "action": "navigate_tab", "tab": "exposures"})
    if "notice" in low or "legal" in low or "dpdp" in low or "gdpr" in low:
        suggestions.append({"label": "Open Legal Studio", "action": "navigate_tab", "tab": "legal"})
    if "compliance" in low or "deadline" in low or "tracker" in low:
        suggestions.append({"label": "Check Statutory Deadlines", "action": "navigate_tab", "tab": "compliance"})

    if not suggestions:
        if tab == "dashboard":
            suggestions = [
                {"label": "Run Privacy Agent", "action": "navigate_tab", "tab": "agent"},
                {"label": "Explain Risk Score", "action": "ask", "prompt": "Why is my risk score calculated the way it is?"},
                {"label": "View Exposures", "action": "navigate_tab", "tab": "exposures"},
            ]
        elif tab == "exposures":
            suggestions = [
                {"label": "How to Remove Truecaller", "action": "ask", "prompt": "How do I remove my listing from Truecaller?"},
                {"label": "Draft Legal Notice", "action": "navigate_tab", "tab": "legal"},
                {"label": "Explain Indian Registry", "action": "ask", "prompt": "Why can court records and MCA filings not be erased under DPDP?"},
            ]
        elif tab == "legal":
            suggestions = [
                {"label": "DPDP s.12 Erasure", "action": "ask", "prompt": "Explain DPDP Act 2023 Section 12 requirements."},
                {"label": "30-Day Rule", "action": "ask", "prompt": "What happens if a data fiduciary misses the 30-day DPDP deadline?"},
                {"label": "View Tracker", "action": "navigate_tab", "tab": "compliance"},
            ]
        elif tab == "compliance":
            suggestions = [
                {"label": "Escalate to DPBI", "action": "ask", "prompt": "How do I escalate an unresponsive broker to the Data Protection Board of India?"},
                {"label": "Verify Removals", "action": "navigate_tab", "tab": "agent"},
            ]
        else:
            suggestions = [
                {"label": "Run Full Privacy Audit", "action": "navigate_tab", "tab": "agent"},
                {"label": "Check Exposures", "action": "navigate_tab", "tab": "exposures"},
            ]
    return suggestions[:3]


def _expert_privacy_reply(user_msg: str, tab: str, risk_score: float | None, exposure_count: int) -> str:
    msg = (user_msg or "").lower()
    if any(w in msg for w in ("dpdp", "india", "section 12", "s.12", "erasure")):
        return (
            "### India DPDP Act 2023 — Data Subject Rights\n\n"
            "Under **Section 12 of the Digital Personal Data Protection Act 2023**, you have the right to request **correction, completion, updating, and erasure** of personal data from data fiduciaries once the original purpose of processing is complete.\n\n"
            "**Key Principles:**\n"
            "- **30-Day Statutory Timeline**: Fiduciaries must address your request within 30 days.\n"
            "- **Section 13 Grievance Redressal**: If ignored, you can formally escalate to the Data Fiduciary's Grievance Officer.\n"
            "- **DPBI Escalation**: Unresolved complaints may be escalated to the **Data Protection Board of India (DPBI)**, which can levy penalties up to ₹250 crore for significant breaches.\n\n"
            "*Note: Erasure does NOT apply to mandatory legal retentions (e.g. tax laws, KYC records) or public court records.*"
        )
    if any(w in msg for w in ("gdpr", "europe", "article 17", "art 17", "right to be forgotten")):
        return (
            "### EU GDPR — Article 17 (Right to Erasure)\n\n"
            "GDPR **Article 17 ('Right to be Forgotten')** grants data subjects the right to obtain erasure of personal data without undue delay when:\n"
            "- The personal data is no longer necessary for the purpose it was collected.\n"
            "- You withdraw consent on which processing is based.\n"
            "- You object to direct marketing or illegitimate profiling.\n\n"
            "**Statutory Period**: Controllers must respond and comply within **1 calendar month** (extendable by 2 months for complex cases with prior notice)."
        )
    if any(w in msg for w in ("truecaller", "naukri", "shaadi", "justdial", "self-serve", "self serve")):
        return (
            "### Self-Serve Removals vs Statutory Notices\n\n"
            "A core rule of ApniPehChaan: **A legal notice is the escalation, not the opening move.**\n\n"
            "- **Truecaller**: Direct unlisting form at `truecaller.com/unlisting` takes ~3 minutes and removes your number from public search.\n"
            "- **Naukri / Job Portals**: Profile deletion is directly available in Account Settings.\n"
            "- **Public Social Profiles**: Direct account deactivation or deletion avoids 30 days of waiting for a legal notice.\n\n"
            "Our system only generates statutory notices for persistent data brokers, scrapers, and entities without self-serve tools."
        )
    if any(w in msg for w in ("candidate", "username", "handle", "torvalds", "collision", "not mine")):
        return (
            "### Identity Attribution & Handle Collisions\n\n"
            "Unlike simple scanners that assume any matching username belongs to you, ApniPehChaan uses **strict attribution**:\n\n"
            "- **Name collisions**: Usernames that match common names (like `@torvalds` or `@rahulsharma`) are shared by thousands across the web.\n"
            "- **Unconfirmed Candidates**: When an account is found with your searched handle, our agent parks it as an **unconfirmed candidate**.\n"
            "- **Your Control**: It is NOT counted in your risk score or removal plan until you click **'Yes, mine'**.\n"
            "- Clicking **'Not me'** permanently excludes that stranger's profile from your privacy record."
        )
    if any(w in msg for w in ("risk", "score", "calculate", "overall")):
        score_desc = f"Your current calculated risk score is **{risk_score} / 100**." if risk_score is not None else "Run a privacy audit in the Privacy Agent tab to calculate your risk score."
        return (
            f"### Privacy Risk Score Breakdown\n\n{score_desc}\n\n"
            "**How it is computed:**\n"
            "1. **Verified Breaches**: Leaked plain-text credentials or sensitive identifiers (Aadhaar, PAN, financial cards) carry highest severity (Critical/High).\n"
            "2. **Dark-Web Pastes**: Raw dumps containing your contact info and personal records.\n"
            "3. **Data Broker Exposure**: Aggregation of marketing dossiers, phone directories, and location profiles.\n"
            "4. **Corroboration Factor**: Multiple sources holding the same unique identifier compound your vulnerability."
        )

    return (
        f"### ApniPehChaan Rights Advisor\n\n"
        f"I am monitoring your privacy posture on the **{tab.replace('-', ' ').title()}** tab. "
        f"Currently, {exposure_count} exposures have been tracked.\n\n"
        f"**Actions you can take right now:**\n"
        f"- **Discover**: Run the autonomous Privacy Agent to scan breach intelligence, dark web pastes, and people directories.\n"
        f"- **Verify**: Review candidate handles so strangers' accounts are not attributed to you.\n"
        f"- **Remediate**: Review the removal plan — execute quick self-serve removals or approve statutory DPDP/GDPR erasure notices.\n"
        f"- **Audit**: All actions generate cryptographic SHA-256 receipts in the immutable audit ledger."
    )



@app.get("/api/agent/threat-surface/{user_id}")
async def agent_threat_surface(user_id: str):
    """Retrieve AI-correlated threat surface intelligence for a user."""
    profile = _memory.get_user(user_id) or {}
    exposures = [e for e in _memory.get_exposures(user_id) if e.get("status") != "not_mine"]
    from backend.agent.multi_agent_swarm import ForensicsAgent
    from backend.agent.tools import ToolContext, build_tools
    from backend.mock_brokers.network import get_network
    ctx = ToolContext(
        memory=_memory, network=get_network(), user_id=user_id, run_id="",
        profile=profile, emit=lambda *a, **kw: None, auto_approve=False
    )
    tools = build_tools(ctx)
    agent = ForensicsAgent(ctx, tools)
    # Also an LLM round-trip; same reason as above.
    return await asyncio.to_thread(agent._analyze_threat_intelligence, profile, exposures)


@app.get("/api/agent/threat-surface")
async def agent_threat_surface_latest():
    """Retrieve AI-correlated threat surface for the most recently active user."""
    row = _memory._row("SELECT user_id FROM runs ORDER BY started_at DESC LIMIT 1")
    if not row or not row.get("user_id"):
        return {"overall_surface_grade": "MINIMAL", "threat_vectors": []}
    return await agent_threat_surface(row["user_id"])


def _chat_grounding(user_id: str | None = None) -> tuple[str, int]:
    """Ground the Copilot on verified exposures, active notices, and threat vectors."""
    try:
        if not user_id:
            row = _memory._row("SELECT user_id FROM runs ORDER BY started_at DESC LIMIT 1")
            user_id = (row or {}).get("user_id")
        if not user_id:
            return "", 0
        exposures = [e for e in _memory.get_exposures(user_id) if e.get("status") != "not_mine"]
        requests = _memory.get_requests(user_id) if user_id else []
    except Exception:
        return "", 0

    if not exposures:
        return ("\nTHE USER'S ACTUAL FINDINGS: none recorded yet. No scan has produced an "
                "exposure. Advise the user to deploy the Privacy Agent to discover their digital footprint.\n"), 0

    confirmed = [e for e in exposures if e.get("status") != "unconfirmed"]
    candidates = [e for e in exposures if e.get("status") == "unconfirmed"]

    lines = ["\nTHE USER'S ACTUAL FINDINGS — answer from THESE ROWS ONLY:"]
    for e in confirmed[:25]:
        detail = e.get("detail") or {}
        found = ", ".join(e.get("data_found") or []) or "unspecified"
        where = detail.get("source_dataset") or e.get("source_type") or ""
        lines.append(
            f"  - {e.get('source_name')} | type={e.get('source_type')} | "
            f"severity={e.get('severity')} | data exposed: {found}"
            + (f" | found via: {where}" if where else ""))
    if len(confirmed) > 25:
        lines.append(f"  ...and {len(confirmed) - 25} more confirmed exposure(s).")
    if candidates:
        lines.append(f"  {len(candidates)} UNCONFIRMED candidate(s) held back pending confirmation: "
                     + ", ".join(str(c.get("source_name")) for c in candidates[:8]))

    if requests:
        lines.append("\nACTIVE STATUTORY ERASURE NOTICES & COMPLIANCE DEADLINES:")
        for r in requests[:6]:
            lines.append(
                f"  - Ref {r.get('reference_id')}: Controller={r.get('broker')} | "
                f"Jurisdiction={str(r.get('jurisdiction')).upper()} | Status={r.get('status')} | "
                f"Deadline={str(r.get('response_deadline', ''))[:10]}")

    lines.append(
        "  If asked something these rows do not answer, say you do not have it and suggest "
        "running a scan. Never name a company, a breach or a data type that is not listed "
        "above, and never describe a risk contributor that is not present here.")
    return "\n".join(lines) + "\n", len(confirmed)


@app.post("/api/agent/chat")
async def agent_chat(req: AgentChatRequest):
    """
    Sitewide Rights Advisor — available across all tabs.
    Context-aware reasoning powered by Groq (openai/gpt-oss-120b) or expert knowledge engine.
    """
    user_msg = (req.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    ctx = req.context or {}
    tab = ctx.get("tab", "dashboard")
    risk_score = ctx.get("risk_score")
    exposure_count = ctx.get("exposure_count", 0)
    profile = ctx.get("profile", {})
    user_name = profile.get("name", "User")
    grounding, grounded_count = _chat_grounding(ctx.get("user_id"))
    if grounded_count:
        exposure_count = grounded_count

    system_prompt = (
        "You are the ApniPehChaan Rights Advisor — an expert privacy and statutory-rights assistant. "
        "You help users identify personal data exposures, understand data privacy legislation (India DPDP Act 2023, EU GDPR, US CCPA), "
        "and assert their statutory rights to erasure, correction, and opt-out.\n\n"
        f"CURRENT SESSION CONTEXT:\n"
        f"- Active UI Tab: {tab}\n"
        f"- User Name: {user_name}\n"
        f"- Current Risk Score: {risk_score if risk_score is not None else 'Not yet calculated'}\n"
        f"- Exposures Count: {exposure_count}\n\n"
        "GUIDELINES:\n"
        "1. Give direct, actionable, legally precise advice.\n"
        "2. When discussing Indian law, cite Section 12 (Right to correction and erasure) and Section 13 (Grievance redressal) of DPDP Act 2023.\n"
        "3. Emphasize that self-serve deletion links should be prioritized over legal notices for services that offer instant deletion (e.g. Truecaller, Naukri, social profiles).\n"
        "4. Clarify that statutory notices apply to commercial data brokers and data fiduciaries, but NOT public court records (e.g. Indian Kanoon) or statutory corporate filings (MCA21).\n"
        "5. Keep responses concise (under 250 words), structured with markdown formatting.\n"
        "6. GROUNDING RULE, which overrides every other guideline: the findings listed below "
        "are the only exposures this user has. Answer questions about their data from those "
        "rows and nothing else. Do not invent a company, a breach, a data type or a risk "
        "contributor that is not listed. If the answer is not there, say so.\n"
        + grounding
    )

    # 1. Primary: Gemini (with Groq as automatic backup)
    from backend.agent.openai_compat_planner import get_llm_completion
    llm_errors: list[str] = []

    chat_messages = [{"role": "system", "content": system_prompt}]
    for h in (req.history or [])[-6:]:
        if h.content and h.role in ("user", "assistant"):
            chat_messages.append({"role": h.role, "content": h.content})
    chat_messages.append({"role": "user", "content": user_msg})

    # Every LLM call below goes out through the SYNCHRONOUS OpenAI/Anthropic
    # clients, and get_llm_completion walks a list of providers x candidate models,
    # each a full blocking round-trip. Called directly from an `async def` that
    # froze the whole event loop for the duration — one chat message stalled every
    # other request on the server, the live /ws/agent trace included, and a
    # rate-limited key turned that into tens of seconds. They run on a worker
    # thread now.
    reply, model_used = await asyncio.to_thread(
        get_llm_completion,
        messages=chat_messages,
        max_tokens=800,
        temperature=0.3,
        preferred_provider="gemini",
    )
    if reply:
        return {
            "reply": reply,
            "model": model_used,
            "suggested_actions": _get_chat_suggestions(tab, user_msg)
        }

    # 2. Try Anthropic if configured
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            client = Anthropic()
            claude_msgs = []
            for h in (req.history or [])[-6:]:
                if h.content and h.role in ("user", "assistant"):
                    claude_msgs.append({"role": h.role, "content": h.content})
            claude_msgs.append({"role": "user", "content": user_msg})
            resp = await asyncio.to_thread(
                client.messages.create,
                model="claude-3-5-sonnet-20241022",
                max_tokens=600,
                system=system_prompt,
                messages=claude_msgs,
            )
            reply = (resp.content[0].text or "").strip()
            if reply:
                return {
                    "reply": reply,
                    "model": "claude-3-5-sonnet",
                    "suggested_actions": _get_chat_suggestions(tab, user_msg)
                }
        except Exception as exc:
            llm_errors.append(f"anthropic: {type(exc).__name__}: {str(exc)[:160]}")

    # 3. Expert Knowledge Engine fallback — a scripted reply, and it must say so.
    reply = _expert_privacy_reply(user_msg, tab, risk_score, exposure_count)
    # Say plainly that no model answered. The UI header read "Groq · GPT-OSS
    # Active" over this scripted text, so a rate-limited key looked exactly like
    # a working assistant — and a user asking "which companies have my data"
    # got a confident answer from a script that had never seen their data.
    if llm_errors:
        reply += ("\n\n---\n*Answered from the built-in knowledge base — no AI model was "
                  "reachable just now (" + "; ".join(llm_errors[:2]) + "). "
                  "This reply is not grounded in your scan results.*")
    return {
        "reply": reply,
        "model": "ApniPehChaan knowledge base (no AI model available)",
        "llm_unavailable": bool(llm_errors),
        "llm_errors": llm_errors,
        "suggested_actions": _get_chat_suggestions(tab, user_msg)
    }


@app.post("/api/agent/scan")
async def agent_scan(req: AgentScanRequest):
    """Phase 1 — discover, assess, decide, draft. Dispatches nothing."""
    _require_identifier(req)
    profile = _profile_of(req)
    stream = EventStream()
    result = await _asyncio.to_thread(run_discovery, profile, stream)
    return {
        "run_id": result.run_id, "user_id": result.user_id, "planner": result.mode,
        "summary": result.summary, "error": result.error,
        "events": [e for e in result.events if e.get("type") == "agent_event"],
        "risk_before": (_memory.get_run(result.run_id) or {}).get("risk_before"),
        "risk_after": (_memory.get_run(result.run_id) or {}).get("risk_after"),
        "state": _dashboard_state(result.user_id),
    }


@app.post("/api/agent/approve")
async def agent_approve(req: AgentApproveRequest):
    """Phase 2 — the user approved; dispatch, follow up, verify, escalate."""
    if not req.request_ids:
        raise HTTPException(status_code=400, detail="No request_ids supplied.")
    _require_identifier(req)
    profile = _profile_of(req)
    _owned_request_ids(_memory.upsert_user(profile), req.request_ids)
    stream = EventStream()
    result = await _asyncio.to_thread(run_remediation, profile, req.request_ids, stream)
    return {
        "run_id": result.run_id, "user_id": result.user_id, "planner": result.mode,
        "summary": result.summary, "error": result.error,
        "events": [e for e in result.events if e.get("type") == "agent_event"],
        "risk_before": (_memory.get_run(result.run_id) or {}).get("risk_before"),
        "risk_after": (_memory.get_run(result.run_id) or {}).get("risk_after"),
        "state": _dashboard_state(result.user_id),
    }


@app.post("/api/agent/reset")
async def agent_reset(req: AgentScanRequest):
    """Wipe this identity so a demo can be re-run from a clean slate."""
    if not (req.name or "").strip() and not (req.email or "").strip():
        raise HTTPException(status_code=400,
                            detail="A name or email is required to identify what to reset.")
    removed = _network.reset_subject(req.name, req.email)
    user_id = _memory.upsert_user(_profile_of(req))
    _memory.reset_user(user_id)
    return {"status": "reset", "user_id": user_id, "broker_records_cleared": removed}


async def _pump(websocket: WebSocket, fn, *args):
    """Run a blocking agent phase in a worker thread, forwarding its events live."""
    stream = EventStream()
    holder: dict = {}

    def work():
        try:
            holder["result"] = fn(*args, stream)
        except Exception as exc:                       # keep the socket informative
            holder["error"] = f"{type(exc).__name__}: {exc}"
            stream.put({"type": "agent_event", "agent": "orchestrator", "phase": "error",
                        "message": str(exc), "status": "error"})
            stream.close()

    thread = _threading.Thread(target=work, daemon=True)
    thread.start()

    # Drained by polling rather than loop.run_in_executor(None, stream.q.get).
    # That parked a thread of the DEFAULT executor on a blocking get for the
    # whole run — and asyncio.to_thread, which POST /api/agent/scan uses, draws
    # from that same pool (max_workers = min(32, cpu+4)). Enough concurrent
    # live runs and every REST scan queued behind sockets that were doing
    # nothing but waiting. Polling holds no pool thread, and noticing a dead
    # worker means a phase that dies without closing its stream no longer hangs
    # the socket for ever.
    while True:
        try:
            event = stream.q.get_nowait()
        except _queue.Empty:
            if not thread.is_alive():
                break
            await _asyncio.sleep(0.02)
            continue
        if event is None:
            break
        await websocket.send_json(event)

    # close() happens just before the phase returns, so the result may not be
    # assigned yet when the sentinel arrives.
    while thread.is_alive():
        await _asyncio.sleep(0.01)
    return holder.get("result"), holder.get("error")


@app.websocket("/ws/agent")
async def websocket_agent(websocket: WebSocket):
    """
    Live agent feed.

    Unlike the legacy /ws/scan, nothing here is padded with sleeps: each message
    is emitted at the moment the agent actually reaches that step, so the trace
    the judge watches is the real execution order.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # A frame that is not an object, or carries "profile": null, used
            # to raise AttributeError out of the handler and kill the socket
            # with no explanation. Client input is not to be trusted to be the
            # shape the happy path assumes.
            if not isinstance(data, dict):
                await websocket.send_json({"type": "error",
                                           "message": "Expected a JSON object frame."})
                continue
            action = data.get("action")
            profile = data.get("profile") or {}
            if not isinstance(profile, dict):
                await websocket.send_json({"type": "error",
                                           "message": "'profile' must be a JSON object."})
                continue
            profile = dict(profile)
            profile.setdefault("country", "IN")

            if action == "scan":
                if not any(str(profile.get(f) or "").strip() for f in _IDENTIFIER_FIELDS):
                    await websocket.send_json({
                        "type": "error",
                        "message": ("At least one identifier is required — an email, phone, "
                                    "name, declared account or known username.")})
                    continue
                result, err = await _pump(websocket, run_discovery, profile)
            elif action == "approve":
                ids = data.get("request_ids") or []
                if not isinstance(ids, list) or not ids:
                    await websocket.send_json({"type": "error", "message": "No request_ids supplied."})
                    continue
                # Same gate as POST /api/agent/approve: a notice is only
                # dispatched by the data principal it was drafted for.
                try:
                    _owned_request_ids(_memory.upsert_user(profile), ids)
                except HTTPException as exc:
                    await websocket.send_json({"type": "error", "message": exc.detail})
                    continue
                result, err = await _pump(websocket, run_remediation, profile, ids)
            else:
                await websocket.send_json({"type": "error", "message": f"Unknown action {action!r}"})
                continue

            if result is None:
                await websocket.send_json({"type": "error", "message": err or "Agent run failed."})
                continue

            run_row = _memory._row("SELECT risk_before, risk_after FROM runs WHERE id=?",
                                   (result.run_id,)) or {}
            await websocket.send_json({
                "type": "phase_complete",
                "action": action,
                "run_id": result.run_id,
                "user_id": result.user_id,
                "planner": result.mode,
                "summary": result.summary,
                "risk_before": run_row.get("risk_before"),
                "risk_after": run_row.get("risk_after"),
                "state": _dashboard_state(result.user_id),
            })

    except WebSocketDisconnect:
        # A clean client-side close. Nothing to report back to a socket that
        # is already gone.
        ws_manager.disconnect(websocket)
    except Exception as exc:
        # Anything else — a storage outage mid-run, a planner blowing up — is
        # something the user needs told. This used to close the socket in
        # silence, so the UI could not distinguish a crash from a dropped
        # connection.
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Agent run failed: {type(exc).__name__}: {exc}",
            })
        except Exception:
            pass
        ws_manager.disconnect(websocket)


@app.get("/api/sources/indian")
async def indian_sources():
    """
    The Indian exposure surface, with its legal classification.

    The Optery directory is 956 brokers with no country field and is heavily
    US-weighted — it surfaces Alabama court-record sites to an Indian user.
    This registry covers the domestic surface and, more usefully, records
    WHICH LAW applies to each: a people-search site and a High Court judgment
    both hold your name, but only one can be served with a DPDP notice.
    """
    from backend.agent.tools import load_indian_sources
    sources = load_indian_sources()
    by_class: dict = {}
    for s in sources:
        by_class.setdefault(s.get("legal_class", "unknown"), []).append(s["name"])
    return {
        "count": len(sources),
        "sources": sources,
        "legal_classes": {
            "dpdp_erasure": "DPDP Act 2023 s.12 — erasure available on request.",
            "dpdp_limited": "DPDP applies but a statutory retention duty competes (CICRA 2005, "
                            "telecom licence, PMLA KYC). Dispute and correct, not erase.",
            "statutory_publication": "Published under a legal obligation (Companies Act 2013, "
                                     "Representation of the People Act 1950, state land records). "
                                     "DPDP s.3(c)(ii) excludes it — erasure does not lie.",
            "judicial_record": "Court record. Redaction requires an application to the court "
                               "(cf. Delhi HC, Jorawer Singh Mundy v. Union of India, 2021).",
        },
        "by_class": by_class,
    }


# ── Identifier verification ───────────────────────────────────────────────────
# Attribution is only as trustworthy as the identifiers it starts from. An email
# somebody mistyped, or does not own, poisons everything downstream: accounts get
# attributed to the wrong person and the tool then helps demand deletion of a
# stranger's data. So ownership must be demonstrated before an identifier is
# allowed to corroborate anything.

from backend.agent.verification import get_verifier

_verifier = get_verifier()


class VerifyRequest(BaseModel):
    name: str = ""
    email: str = ""
    kind: str = "email"          # email | phone
    value: str = ""


class VerifySubmit(VerifyRequest):
    code: str = ""


def _uid_for(req) -> str:
    return _memory.upsert_user({"name": req.name, "email": req.email})


@app.get("/api/verify/status")
async def verify_status(name: str = "", email: str = "", phone: str = ""):
    uid = _memory.upsert_user({"name": name, "email": email})
    graded = _verifier.attribution_grade(uid)
    return {
        "user_id": uid,
        "status": _verifier.status_for(uid, email, phone),
        "attribution_grade": graded,
        "can_attribute": bool(graded["emails"] or graded["phones"]),
        "channels": {"email": _verifier.email_channel(), "sms": _verifier.sms_channel()},
        "policy": ("Only identifiers proven by a delivered one-time code are used to attribute "
                   "an account to you. Unverified ones can still be searched with, but a match "
                   "yields a candidate you must confirm — never a finding."),
    }


@app.post("/api/verify/request")
async def verify_request(req: VerifyRequest):
    """Issue a one-time code. Checks MX first, so typos fail before anything is sent."""
    uid = _uid_for(req)
    return _verifier.request_code(uid, req.kind, req.value)


@app.post("/api/verify/submit")
async def verify_submit(req: VerifySubmit):
    """Check a code and, on success, mark the identifier as owned."""
    uid = _uid_for(req)
    return _verifier.submit_code(uid, req.kind, req.value, req.code)


class ConfirmRequest(AgentScanRequest):
    exposure_id: str = ""
    is_mine: bool = True


@app.post("/api/agent/confirm")
async def agent_confirm(req: ConfirmRequest):
    """
    Resolve a parked candidate.

    A candidate is a profile whose handle matched but which nothing tied to the
    user. Until this call it is excluded from the ledger, the risk score and the
    removal plan — because acting on it would mean requesting deletion of
    somebody else's account.
    """
    if not req.exposure_id:
        raise HTTPException(status_code=400, detail="exposure_id is required.")
    exp = _memory.get_exposure(req.exposure_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Unknown exposure.")
    user_id = exp["user_id"]

    if req.is_mine:
        _memory.set_exposure_status(req.exposure_id, "exposed")
        _memory.update_exposure(req.exposure_id, evidence_class="self_declared", match_tier="user_confirmed")
    else:
        _memory.set_exposure_status(req.exposure_id, "not_mine")

    return {"exposure_id": req.exposure_id,
            "status": "exposed" if req.is_mine else "not_mine",
            "state": _dashboard_state(user_id)}


@app.get("/api/config/status")
async def config_status():
    """
    Which capabilities are switched on, without ever revealing a key value.

    Both the LLM planner and real breach-membership checks are gated purely on
    the presence of an environment variable, so it must be possible to see at a
    glance which one is live — restarting in a fresh shell is an easy way to
    demo the deterministic pipeline by accident and not notice.
    """
    from backend.agent.env import status as _status
    st = _status()
    return {
        **st,
        "how_to_enable": {
            "llm_planner": ("Put ANTHROPIC_API_KEY in .env (copy .env.example), then restart. "
                            "Key from https://console.anthropic.com/settings/keys — under $1 "
                            "for a full demo run."),
            "breach_checks": ("Put HIBP_API_KEY in .env, then restart. "
                              "Key from https://haveibeenpwned.com/API/Key — about $3.95/month."),
        },
        "without_them": ("The product still runs end to end: a deterministic pipeline drives the "
                         "identical 20 tools, and breach membership reports 'not checked' rather "
                         "than guessing."),
    }
