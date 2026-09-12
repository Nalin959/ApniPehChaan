"""
supabase_memory.py — Supabase PostgREST Storage Adapter for SovereignPrivacy AI.

Provides persistent cloud database storage across serverless functions (Vercel)
and worker nodes without requiring external heavy database drivers. Uses Python's
built-in urllib standard library.
"""

import json
import os
import urllib.request
import urllib.parse
import urllib.error
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseMemory:
    """Cloud memory adapter that connects to Supabase via PostgREST."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.rest_endpoint = f"{self.url}/rest/v1"
        self._headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        data: Optional[Any] = None,
        prefer: Optional[str] = None,
    ) -> Any:
        url = f"{self.rest_endpoint}/{path}"
        if params:
            url += f"?{urllib.parse.urlencode(params)}"

        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer

        body_bytes = None
        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                resp_body = resp.read().decode("utf-8")
                if resp_body:
                    try:
                        return json.loads(resp_body)
                    except json.JSONDecodeError:
                        return resp_body
                return None
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            print(f"[Supabase Error {e.code}] {method} {path}: {err_msg}")
            raise
        except Exception as e:
            print(f"[Supabase Request Failed] {method} {path}: {e}")
            raise

    # ── Users ───────────────────────────────────────────────────────────────

    def upsert_user(self, profile: dict) -> str:
        user_id = profile.get("id") or str(uuid.uuid4())
        record = {
            "id": user_id,
            "name": profile.get("name", ""),
            "email": (profile.get("email") or "").strip().lower(),
            "phone": profile.get("phone", ""),
            "pan": (profile.get("pan") or "").strip().upper(),
            "city": profile.get("city", ""),
            "country": profile.get("country", "IN"),
            "created_at": utcnow(),
        }
        self._request("POST", "users", prefer="resolution=merge-duplicates,return=representation", data=record)
        return user_id

    def get_user(self, user_id: str) -> dict | None:
        rows = self._request("GET", "users", params={"id": f"eq.{user_id}", "select": "*"})
        return rows[0] if rows else None

    # ── Runs ────────────────────────────────────────────────────────────────

    def start_run(self, user_id: str, mode: str, model: str = "") -> str:
        run_id = f"run_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}"
        record = {
            "id": run_id,
            "user_id": user_id,
            "started_at": utcnow(),
            "mode": mode,
            "model": model,
        }
        self._request("POST", "runs", data=record)
        return run_id

    def finish_run(self, run_id: str, risk_before: float, risk_after: float, summary: str):
        record = {
            "finished_at": utcnow(),
            "risk_before": risk_before,
            "risk_after": risk_after,
            "summary": summary,
        }
        self._request("PATCH", "runs", params={"id": f"eq.{run_id}"}, data=record)

    def last_run_before(self, user_id: str, run_id: str) -> dict | None:
        params = {
            "user_id": f"eq.{user_id}",
            "id": f"neq.{run_id}",
            "finished_at": "not.is.null",
            "order": "started_at.desc",
            "limit": "1",
            "select": "*",
        }
        rows = self._request("GET", "runs", params=params)
        return rows[0] if rows else None

    # ── Identities ──────────────────────────────────────────────────────────

    def add_identity(self, user_id: str, alias: str, alias_type: str, confidence: float, rationale: str = "") -> str:
        ident_id = str(uuid.uuid4())
        record = {
            "id": ident_id,
            "user_id": user_id,
            "alias": alias,
            "alias_type": alias_type,
            "confidence": confidence,
            "rationale": rationale,
            "created_at": utcnow(),
        }
        self._request("POST", "identities", data=record)
        return ident_id

    def get_identities(self, user_id: str) -> list[dict]:
        params = {"user_id": f"eq.{user_id}", "order": "confidence.desc", "select": "*"}
        return self._request("GET", "identities", params=params) or []

    def clear_identities(self, user_id: str):
        self._request("DELETE", "identities", params={"user_id": f"eq.{user_id}"})

    # ── Exposures ───────────────────────────────────────────────────────────

    def record_exposure(self, user_id: str, run_id: str, exp: dict) -> tuple[str, bool]:
        source_id = exp.get("source_id", "")
        source_name = exp.get("source_name", "")
        source_type = exp.get("source_type", "")

        # Check existing exposure
        params = {
            "user_id": f"eq.{user_id}",
            "source_type": f"eq.{source_type}",
            "source_id": f"eq.{source_id}",
            "select": "*",
        }
        existing = self._request("GET", "exposures", params=params)
        now = utcnow()

        data_found = exp.get("data_found", [])
        detail = exp.get("detail", {})
        evidence = exp.get("evidence", [])

        if existing:
            exp_id = existing[0]["id"]
            fields = {
                "run_id": run_id,
                "data_found": data_found,
                "detail": detail,
                "evidence": evidence,
                "risk_score": exp.get("risk_score", 0.0),
                "severity": exp.get("severity", "medium"),
                "status": "exposed" if existing[0]["status"] in ("removed", "reappeared") else existing[0]["status"],
            }
            if existing[0]["status"] == "removed":
                fields["status"] = "reappeared"
            self._request("PATCH", "exposures", params={"id": f"eq.{exp_id}"}, data=fields)
            return exp_id, False
        else:
            exp_id = exp.get("id") or f"exp_{uuid.uuid4().hex[:12]}"
            record = {
                "id": exp_id,
                "user_id": user_id,
                "run_id": run_id,
                "source_type": source_type,
                "source_name": source_name,
                "source_id": source_id,
                "record_id": exp.get("record_id", ""),
                "data_found": data_found,
                "detail": detail,
                "match_confidence": exp.get("match_confidence", 1.0),
                "match_tier": exp.get("match_tier", "definite"),
                "evidence_class": exp.get("evidence_class", "verified"),
                "evidence": evidence,
                "risk_score": exp.get("risk_score", 0.0),
                "severity": exp.get("severity", "medium"),
                "status": "exposed",
                "discovered_at": now,
            }
            self._request("POST", "exposures", data=record)
            return exp_id, True

    def get_exposures(self, user_id: str, status: str | None = None) -> list[dict]:
        params = {"user_id": f"eq.{user_id}", "order": "risk_score.desc", "select": "*"}
        if status:
            params["status"] = f"eq.{status}"
        return self._request("GET", "exposures", params=params) or []

    def get_exposure(self, exposure_id: str) -> dict | None:
        rows = self._request("GET", "exposures", params={"id": f"eq.{exposure_id}", "select": "*"})
        return rows[0] if rows else None

    def set_exposure_status(self, exposure_id: str, status: str, **stamps):
        allowed = {"removed_at", "verified_at"}
        body = {"status": status}
        for k, v in stamps.items():
            if k in allowed:
                body[k] = v
        self._request("PATCH", "exposures", params={"id": f"eq.{exposure_id}"}, data=body)

    # ── Requests ────────────────────────────────────────────────────────────

    def create_request(self, user_id: str, exposure_id: str, req: dict) -> str:
        req_id = req.get("id") or f"req_{uuid.uuid4().hex[:12]}"
        record = {
            "id": req_id,
            "user_id": user_id,
            "exposure_id": exposure_id,
            "jurisdiction": req.get("jurisdiction", "dpdp"),
            "statute": req.get("statute", ""),
            "legal_basis": req.get("legal_basis", ""),
            "request_text": req.get("request_text", ""),
            "reference_id": req.get("reference_id", ""),
            "receipt_hash": req.get("receipt_hash", ""),
            "status": req.get("status", "drafted"),
            "confirmation_id": req.get("confirmation_id", ""),
            "created_at": utcnow(),
            "deadline": req.get("deadline"),
            "deadline_days": req.get("deadline_days", 30),
        }
        self._request("POST", "requests", data=record)
        return req_id

    def open_request_for(self, exposure_id: str) -> dict | None:
        params = {
            "exposure_id": f"eq.{exposure_id}",
            "status": "in.(drafted,awaiting_approval,submitted,acknowledged,overdue)",
            "order": "created_at.desc",
            "limit": "1",
            "select": "*",
        }
        rows = self._request("GET", "requests", params=params)
        return rows[0] if rows else None

    def get_request(self, request_id: str) -> dict | None:
        rows = self._request("GET", "requests", params={"id": f"eq.{request_id}", "select": "*"})
        return rows[0] if rows else None

    def get_requests(self, user_id: str) -> list[dict]:
        params = {"user_id": f"eq.{user_id}", "order": "created_at.desc", "select": "*"}
        return self._request("GET", "requests", params=params) or []

    def update_request(self, request_id: str, **fields):
        self._request("PATCH", "requests", params={"id": f"eq.{request_id}"}, data=fields)

    def overdue_requests(self, user_id: str) -> list[dict]:
        now = utcnow()
        params = {
            "user_id": f"eq.{user_id}",
            "status": "in.(submitted,acknowledged)",
            "deadline": f"lt.{now}",
            "order": "deadline.asc",
            "select": "*",
        }
        return self._request("GET", "requests", params=params) or []

    # ── Events ──────────────────────────────────────────────────────────────

    def log_event(
        self,
        user_id: str,
        run_id: str,
        agent: str,
        phase: str,
        message: str,
        tool_name: str = "",
        tool_input: Any = None,
        tool_output: Any = None,
        status: str = "ok",
    ):
        record = {
            "user_id": user_id,
            "run_id": run_id,
            "ts": utcnow(),
            "agent": agent,
            "phase": phase,
            "message": message,
            "tool_name": tool_name,
            "tool_input": json.dumps(tool_input) if isinstance(tool_input, (dict, list)) else (tool_input or ""),
            "tool_output": json.dumps(tool_output) if isinstance(tool_output, (dict, list)) else (tool_output or ""),
            "status": status,
        }
        self._request("POST", "agent_events", data=record)

    def get_events(self, run_id: str) -> list[dict]:
        params = {"run_id": f"eq.{run_id}", "order": "id.asc", "select": "*"}
        return self._request("GET", "agent_events", params=params) or []

    def recent_events(self, user_id: str, limit: int = 50) -> list[dict]:
        params = {"user_id": f"eq.{user_id}", "order": "id.desc", "limit": str(limit), "select": "*"}
        rows = self._request("GET", "agent_events", params=params) or []
        rows.reverse()
        return rows

    # ── Audit Chain ─────────────────────────────────────────────────────────

    def append_receipt(self, receipt: dict):
        record = {
            "receipt_id": receipt.get("receipt_id", ""),
            "timestamp": receipt.get("timestamp", utcnow()),
            "action": receipt.get("action", ""),
            "details": receipt.get("details", {}),
            "previous_hash": receipt.get("previous_hash", ""),
            "hash": receipt.get("hash", ""),
        }
        self._request("POST", "audit_receipts", data=record)

    def load_receipts(self) -> list[dict]:
        params = {"order": "seq.asc", "select": "*"}
        return self._request("GET", "audit_receipts", params=params) or []

    # ── User Summary ────────────────────────────────────────────────────────

    def user_summary(self, user_id: str) -> dict:
        exps = self.get_exposures(user_id)
        reqs = self.get_requests(user_id)
        by_status: dict[str, int] = {}
        for e in exps:
            by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        return {
            "exposures_total": len(exps),
            "exposures_by_status": by_status,
            "high_risk": len([e for e in exps if (e.get("severity") or "").lower() in ("critical", "high")]),
            "requests_total": len(reqs),
            "requests_submitted": len([
                r for r in reqs if r.get("status") in ("submitted", "acknowledged", "completed", "escalated")
            ]),
            "removals_verified": len([e for e in exps if e.get("status") == "removed"]),
            "overdue": len(self.overdue_requests(user_id)),
        }
