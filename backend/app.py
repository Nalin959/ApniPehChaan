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
audit_trail = AuditTrail()
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
