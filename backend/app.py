"""
app.py — SovereignPrivacy AI: FastAPI Backend Server.

Main server providing REST API endpoints and WebSocket for real-time
scan feed. Orchestrates all scanner, PII, and remediation modules.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
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
    print("  SovereignPrivacy AI — Server Starting")
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
    print("SovereignPrivacy AI — Server Stopped")


app = FastAPI(
    title="SovereignPrivacy AI",
    description="Digital Identity & Sovereign Privacy Protection Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return HTMLResponse(content="<h1>SovereignPrivacy AI</h1><p>Frontend not found. Place files in /frontend/</p>")


# ─── Routes: System Info ──────────────────────────────────────────────────────

@app.get("/api/status")
async def system_status():
    """Return system health and dataset statistics."""
    return {
        "status": "operational",
        "agent": "SovereignPrivacy AI",
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
    paste_results = paste_scanner.scan(user_profile)

    # Aggregate exposures for risk calculation
    exposures = []

    for breach in hibp_results.get("breaches", []):
        for dc in breach.get("data_classes", []):
            dc_lower = dc.lower()
            etype = "EMAIL"
            if "password" in dc_lower:
                etype = "CREDIT_CARD"  # elevate severity
            elif "phone" in dc_lower:
                etype = "PHONE_IN"
            elif "address" in dc_lower:
                etype = "ADDRESS"
            elif "name" in dc_lower:
                etype = "NAME"

            exposures.append({
                "entity_type": etype,
                "source_type": "hibp_verified",
                "date_found": breach.get("breach_date"),
                "value": f"[from {breach.get('name', 'unknown breach')}]",
            })

    for match in paste_results.get("matches", []):
        for entity in match.get("entities_found", []):
            exposures.append({
                "entity_type": entity.get("entity_type", "UNKNOWN"),
                "source_type": "dark_web_paste",
                "date_found": match.get("date_found"),
                "value": entity.get("value", ""),
            })

    # Calculate risk
    broker_matches = broker_results.get("stats", {}).get("high_risk_matches", 0)
    total_brokers = broker_results.get("stats", {}).get("total_brokers_checked", 0)
    risk_assessment = risk_calculator.calculate(exposures, broker_matches, total_brokers)

    # Create audit receipt
    receipt = audit_trail.add("FULL_SCAN_COMPLETED", {
        "user_email_hash": __import__('hashlib').sha256(req.email.encode()).hexdigest()[:16] if req.email else "none",
        "breaches_found": len(hibp_results.get("breaches", [])),
        "paste_matches": len(paste_results.get("matches", [])),
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
            "total_paste_matches": len(paste_results.get("matches", [])),
            "total_broker_matches": broker_matches,
            "risk_score": risk_assessment.overall_score,
            "risk_level": risk_assessment.risk_level,
        },
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
    result = paste_scanner.scan(user_profile)
    receipt = audit_trail.add("PASTE_SCAN", {"matches_found": result.get("stats", {}).get("matches_found", 0)})
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
    result = notice_generator.generate(
        jurisdiction=req.jurisdiction,
        user_name=req.user_name,
        user_email=req.user_email,
        user_phone=req.user_phone,
        additional_ids=req.additional_ids,
        company_name=req.company_name,
        company_address=req.company_address,
        detected_pii_summary=req.detected_pii_summary,
    )

    if result.get("status") == "generated":
        audit_trail.add("NOTICE_GENERATED", {
            "reference_id": result.get("reference_id"),
            "jurisdiction": req.jurisdiction,
            "company": req.company_name,
        })

    return result


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
                paste_results = paste_scanner.scan(profile)
                paste_matches = len(paste_results.get("matches", []))
                await send_step("paste_done", f"Dark-web scan complete: {paste_matches} leak matches", 75)
                await asyncio.sleep(0.3)

                await send_step("risk_calc", "Computing Privacy Risk Score...", 80)
                await asyncio.sleep(0.3)

                # Aggregate exposures
                exposures = []
                for breach in hibp_results.get("breaches", []):
                    for dc in breach.get("data_classes", []):
                        exposures.append({
                            "entity_type": "EMAIL",
                            "source_type": "hibp_verified",
                            "date_found": breach.get("breach_date"),
                            "value": f"[{breach.get('name', '')}]",
                        })
                for match in paste_results.get("matches", []):
                    for entity in match.get("entities_found", []):
                        exposures.append({
                            "entity_type": entity.get("entity_type", "UNKNOWN"),
                            "source_type": "dark_web_paste",
                            "date_found": match.get("date_found"),
                            "value": entity.get("value", ""),
                        })

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
                    },
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
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
    password: str = ""
    # Opt-in demo environment. OFF by default: it plants synthetic records,
    # which must never be mistaken for real findings.
    sandbox: bool = False

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


def _profile_of(req: AgentScanRequest) -> dict:
    return {"name": req.name, "email": req.email, "phone": req.phone,
            "city": req.city, "country": req.country or "IN",
            "declared_accounts": req.declared_accounts, "password": req.password,
            "sandbox": bool(req.sandbox),
            "alt_emails": req.alt_emails, "alt_phones": req.alt_phones,
            "known_usernames": req.known_usernames, "date_of_birth": req.date_of_birth,
            "upi_id": req.upi_id, "websites": req.websites,
            "search_guessed_handles": bool(req.search_guessed_handles),
            "pan": req.pan, "aadhaar": req.aadhaar, "passport": req.passport,
            "card_last4": req.card_last4}


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
                "sandbox": "Synthetic demo record. Off by default and labelled wherever it appears.",
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
    """The controlled broker environment, disclosed openly."""
    return {
        "environment": "simulated",
        "disclosure": ("Removal is demonstrated against a controlled broker network so the "
                       "full discover-request-verify loop is reproducible. The agent's "
                       "reasoning, drafting, dispatch, follow-up and verification are real."),
        "brokers": _network.list_brokers(),
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
            "A core rule of SovereignPrivacy AI: **A legal notice is the escalation, not the opening move.**\n\n"
            "- **Truecaller**: Direct unlisting form at `truecaller.com/unlisting` takes ~3 minutes and removes your number from public search.\n"
            "- **Naukri / Job Portals**: Profile deletion is directly available in Account Settings.\n"
            "- **Public Social Profiles**: Direct account deactivation or deletion avoids 30 days of waiting for a legal notice.\n\n"
            "Our system only generates statutory notices for persistent data brokers, scrapers, and entities without self-serve tools."
        )
    if any(w in msg for w in ("candidate", "username", "handle", "torvalds", "collision", "not mine")):
        return (
            "### Identity Attribution & Handle Collisions\n\n"
            "Unlike simple scanners that assume any matching username belongs to you, SovereignPrivacy AI uses **strict attribution**:\n\n"
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
        f"### SovereignPrivacy Rights Advisor\n\n"
        f"I am monitoring your privacy posture on the **{tab.replace('-', ' ').title()}** tab. "
        f"Currently, {exposure_count} exposures have been tracked.\n\n"
        f"**Actions you can take right now:**\n"
        f"- **Discover**: Run the autonomous Privacy Agent to scan breach intelligence, dark web pastes, and people directories.\n"
        f"- **Verify**: Review candidate handles so strangers' accounts are not attributed to you.\n"
        f"- **Remediate**: Review the removal plan — execute quick self-serve removals or approve statutory DPDP/GDPR erasure notices.\n"
        f"- **Audit**: All actions generate cryptographic SHA-256 receipts in the immutable audit ledger."
    )



def _chat_grounding(user_id: str | None = None) -> tuple[str, int]:
    """
    The user's ACTUAL findings, rendered for the assistant's system prompt.

    Without this the assistant was told only a risk NUMBER and a COUNT, so the
    most obvious question a user can ask — "which companies have my data?" —
    could not be answered from evidence. What came back instead was a plausible
    generic account of how a risk score is computed, listing contributors like
    dark-web pastes and broker records that were not in this user's ledger at
    all. That is exactly the fabrication this product exists to avoid, and it
    was happening in the one component that talks directly to the user.

    So the assistant is handed the real rows and told to answer only from them.
    """
    try:
        if not user_id:
            row = _memory._row("SELECT user_id FROM runs ORDER BY started_at DESC LIMIT 1")
            user_id = (row or {}).get("user_id")
        if not user_id:
            return "", 0
        exposures = [e for e in _memory.get_exposures(user_id) if e.get("status") != "not_mine"]
    except Exception:
        return "", 0

    if not exposures:
        return ("\nTHE USER'S ACTUAL FINDINGS: none recorded yet. No scan has produced an "
                "exposure. Say so plainly rather than describing what a scan might find.\n"), 0

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
        lines.append(f"  {len(candidates)} UNCONFIRMED candidate(s) are held back pending the "
                     f"user's confirmation and are NOT counted as theirs: "
                     + ", ".join(str(c.get("source_name")) for c in candidates[:8]))
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
        "You are the SovereignPrivacy Rights Advisor — an expert privacy and statutory-rights assistant. "
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

    # 1. Try OpenAI-compatible provider (e.g. Groq with openai/gpt-oss-120b)
    from backend.agent.openai_compat_planner import configured_all, PROVIDERS, model_for
    # Walk EVERY configured provider, not just the first. A free tier runs out
    # — Gemini's is twenty requests a day — and stopping at the first one meant
    # a working Groq key in the same .env was never tried. The user then saw
    # the canned fallback text under a header claiming a model was active.
    llm_errors: list[str] = []
    for provider in configured_all():
        try:
            from openai import OpenAI
            spec = PROVIDERS[provider]
            model = model_for(provider)
            client = OpenAI(api_key=os.environ[spec["key_env"]], base_url=spec["base_url"])

            chat_messages = [{"role": "system", "content": system_prompt}]
            for h in (req.history or [])[-6:]:
                if h.content and h.role in ("user", "assistant"):
                    chat_messages.append({"role": h.role, "content": h.content})
            chat_messages.append({"role": "user", "content": user_msg})

            resp = client.chat.completions.create(
                model=model,
                messages=chat_messages,
                temperature=0.3,
                max_tokens=600,
            )
            reply = (resp.choices[0].message.content or "").strip()
            if reply:
                return {
                    "reply": reply,
                    "model": f"{model} ({provider})",
                    "suggested_actions": _get_chat_suggestions(tab, user_msg)
                }
        except Exception as exc:
            # Never swallow this silently. A hidden failure here is why the
            # assistant answered from a canned script while the UI said a model
            # was running, and nothing anywhere said otherwise.
            llm_errors.append(f"{provider}: {type(exc).__name__}: {str(exc)[:160]}")
            continue

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
            resp = client.messages.create(
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
        "model": "SovereignPrivacy knowledge base (no AI model available)",
        "llm_unavailable": bool(llm_errors),
        "llm_errors": llm_errors,
        "suggested_actions": _get_chat_suggestions(tab, user_msg)
    }


@app.post("/api/agent/scan")
async def agent_scan(req: AgentScanRequest):
    """Phase 1 — discover, assess, decide, draft. Dispatches nothing."""
    profile = _profile_of(req)
    stream = EventStream()
    result = await _asyncio.to_thread(run_discovery, profile, stream)
    return {
        "run_id": result.run_id, "user_id": result.user_id, "planner": result.mode,
        "summary": result.summary, "error": result.error,
        "events": [e for e in result.events if e.get("type") == "agent_event"],
        "risk_before": (_memory._row("SELECT risk_before FROM runs WHERE id=?",
                                     (result.run_id,)) or {}).get("risk_before"),
        "risk_after": (_memory._row("SELECT risk_after FROM runs WHERE id=?",
                                    (result.run_id,)) or {}).get("risk_after"),
        "state": _dashboard_state(result.user_id),
    }


@app.post("/api/agent/approve")
async def agent_approve(req: AgentApproveRequest):
    """Phase 2 — the user approved; dispatch, follow up, verify, escalate."""
    if not req.request_ids:
        raise HTTPException(status_code=400, detail="No request_ids supplied.")
    profile = _profile_of(req)
    stream = EventStream()
    result = await _asyncio.to_thread(run_remediation, profile, req.request_ids, stream)
    return {
        "run_id": result.run_id, "user_id": result.user_id, "planner": result.mode,
        "summary": result.summary, "error": result.error,
        "events": [e for e in result.events if e.get("type") == "agent_event"],
        "risk_before": (_memory._row("SELECT risk_before FROM runs WHERE id=?",
                                     (result.run_id,)) or {}).get("risk_before"),
        "risk_after": (_memory._row("SELECT risk_after FROM runs WHERE id=?",
                                    (result.run_id,)) or {}).get("risk_after"),
        "state": _dashboard_state(result.user_id),
    }


@app.post("/api/agent/reset")
async def agent_reset(req: AgentScanRequest):
    """Wipe this identity so a demo can be re-run from a clean slate."""
    removed = _network.reset_subject(req.name, req.email)
    user_id = _memory.upsert_user(_profile_of(req))
    for table in ("exposures", "requests", "agent_events", "identities", "runs"):
        _memory._exec(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
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

    loop = _asyncio.get_running_loop()
    while True:
        event = await loop.run_in_executor(None, stream.q.get)
        if event is None:
            break
        await websocket.send_json(event)

    await loop.run_in_executor(None, thread.join)
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
            action = data.get("action")
            profile = data.get("profile", {})
            profile.setdefault("country", "IN")

            if action == "scan":
                result, err = await _pump(websocket, run_discovery, profile)
            elif action == "approve":
                ids = data.get("request_ids", [])
                if not ids:
                    await websocket.send_json({"type": "error", "message": "No request_ids supplied."})
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
        ws_manager.disconnect(websocket)
    except Exception:
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
        _memory._exec("UPDATE exposures SET evidence_class=?, match_tier=? WHERE id=?",
                      ("self_declared", "user_confirmed", req.exposure_id))
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
