"""
memory.py — Durable agent memory for ApniPehChaan.

Everything the agent learns and does is written here, so that:
  • state survives a server restart (the previous build kept the audit chain
    and the compliance tracker in process memory, so `--reload` wiped them),
  • a later run can reason about what an earlier run already did
    ("I requested erasure from PeopleSearchIndia on 12 Sep; no reply in 9 days"),
  • the agent can answer "what changed since last time?".

Plain stdlib sqlite3 — no ORM. FastAPI serves requests from a thread pool, so
the connection is opened with check_same_thread=False and guarded by a lock.
"""

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.environ.get("APNIPEHCHAAN_DB") or os.environ.get("SOVEREIGN_DB") or os.path.join(PROJECT_ROOT, "data", "sovereign.db")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    name          TEXT,
    email         TEXT,
    phone         TEXT,
    pan           TEXT,
    city          TEXT,
    country       TEXT DEFAULT 'IN',
    created_at    TEXT
);

-- Identity Agent output: aliases/handles believed to belong to the user.
CREATE TABLE IF NOT EXISTS identities (
    id          TEXT PRIMARY KEY,
    user_id     TEXT,
    alias       TEXT,
    alias_type  TEXT,
    confidence  REAL,
    rationale   TEXT,
    created_at  TEXT
);

-- One row per place the user's data was found.
CREATE TABLE IF NOT EXISTS exposures (
    id               TEXT PRIMARY KEY,
    user_id          TEXT,
    run_id           TEXT,
    source_type      TEXT,   -- breach | data_broker | paste | public_profile | open_web
    source_name      TEXT,
    source_id        TEXT,   -- broker slug / breach name
    record_id        TEXT,   -- id of the record inside that source (for removal + verify)
    data_found       TEXT,   -- JSON list of PII entity types
    detail           TEXT,   -- JSON blob
    match_confidence REAL,
    match_tier       TEXT,   -- definite | probable | possible
    evidence_class   TEXT,   -- verified | self_declared | sandbox
    evidence         TEXT,   -- JSON list of Evidence records (endpoint, proof, ...)
    risk_score       REAL,
    severity         TEXT,
    status           TEXT,   -- exposed | requested | acknowledged | removed | reappeared
    discovered_at    TEXT,
    removed_at       TEXT,
    verified_at      TEXT
);

-- Erasure requests the agent prepared / dispatched.
CREATE TABLE IF NOT EXISTS requests (
    id              TEXT PRIMARY KEY,
    user_id         TEXT,
    exposure_id     TEXT,
    jurisdiction    TEXT,
    statute         TEXT,
    legal_basis     TEXT,
    request_text    TEXT,
    reference_id    TEXT,
    receipt_hash    TEXT,
    status          TEXT,   -- drafted | awaiting_approval | submitted | acknowledged | completed | rejected | overdue | escalated
    confirmation_id TEXT,
    created_at      TEXT,
    submitted_at    TEXT,
    deadline        TEXT,
    deadline_days   INTEGER,
    last_followup   TEXT,
    followup_count  INTEGER DEFAULT 0
);

-- Every reasoning step / tool call the agent makes. This is the demo's trace.
CREATE TABLE IF NOT EXISTS agent_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    run_id     TEXT,
    ts         TEXT,
    agent      TEXT,   -- identity | discovery | risk | legal | action | followup | verification | orchestrator
    phase      TEXT,
    message    TEXT,
    tool_name  TEXT,
    tool_input TEXT,
    tool_output TEXT,
    status     TEXT    -- running | ok | error | awaiting_approval
);

-- Chained audit receipts, persisted (previously in-process only).
CREATE TABLE IF NOT EXISTS audit_receipts (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id    TEXT,
    timestamp     TEXT,
    action        TEXT,
    details       TEXT,
    previous_hash TEXT,
    hash          TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    user_id     TEXT,
    started_at  TEXT,
    finished_at TEXT,
    mode        TEXT,   -- llm | deterministic
    model       TEXT,
    risk_before REAL,
    risk_after  REAL,
    summary     TEXT
);

CREATE INDEX IF NOT EXISTS idx_exposures_user ON exposures(user_id);
CREATE INDEX IF NOT EXISTS idx_events_run     ON agent_events(run_id);
CREATE INDEX IF NOT EXISTS idx_requests_user  ON requests(user_id);
"""


class Memory:
    """Durable store for agent state. Safe for concurrent FastAPI threads."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def flush(self):
        """No-op for SQLite (WAL mode commits on exec), provided for parity with SupabaseMemory."""
        pass

    # ── low level ────────────────────────────────────────────────────────────

    def _exec(self, sql: str, params: tuple = ()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _rows(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _row(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    # ── users ────────────────────────────────────────────────────────────────

    def upsert_user(self, profile: dict) -> str:
        """Return a stable user id keyed on email (or name when email is absent)."""
        key = (profile.get("email") or profile.get("name") or "anonymous").strip().lower()
        user_id = "usr_" + uuid.uuid5(uuid.NAMESPACE_DNS, key).hex[:12]
        existing = self._row("SELECT id FROM users WHERE id = ?", (user_id,))
        if existing:
            self._exec(
                "UPDATE users SET name=?, email=?, phone=?, pan=?, city=?, country=? WHERE id=?",
                (profile.get("name", ""), profile.get("email", ""), profile.get("phone", ""),
                 profile.get("pan", ""), profile.get("city", ""), profile.get("country", "IN"), user_id),
            )
        else:
            self._exec(
                "INSERT INTO users (id,name,email,phone,pan,city,country,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, profile.get("name", ""), profile.get("email", ""), profile.get("phone", ""),
                 profile.get("pan", ""), profile.get("city", ""), profile.get("country", "IN"), utcnow()),
            )
        return user_id

    def get_user(self, user_id: str) -> dict | None:
        return self._row("SELECT * FROM users WHERE id=?", (user_id,))

    # ── runs ─────────────────────────────────────────────────────────────────

    def start_run(self, user_id: str, mode: str, model: str = "") -> str:
        run_id = "run_" + uuid.uuid4().hex[:12]
        self._exec(
            "INSERT INTO runs (id,user_id,started_at,mode,model) VALUES (?,?,?,?,?)",
            (run_id, user_id, utcnow(), mode, model),
        )
        return run_id

    def finish_run(self, run_id: str, risk_before: float, risk_after: float, summary: str):
        self._exec(
            "UPDATE runs SET finished_at=?, risk_before=?, risk_after=?, summary=? WHERE id=?",
            (utcnow(), risk_before, risk_after, summary, run_id),
        )

    def last_run_before(self, user_id: str, run_id: str) -> dict | None:
        return self._row(
            "SELECT * FROM runs WHERE user_id=? AND id!=? AND finished_at IS NOT NULL "
            "ORDER BY started_at DESC LIMIT 1",
            (user_id, run_id),
        )

    def get_run(self, run_id: str) -> dict | None:
        return self._row("SELECT * FROM runs WHERE id=?", (run_id,))


    # ── identities ───────────────────────────────────────────────────────────

    def add_identity(self, user_id: str, alias: str, alias_type: str, confidence: float, rationale: str = "") -> str:
        ident_id = "idn_" + uuid.uuid4().hex[:10]
        self._exec(
            "INSERT INTO identities (id,user_id,alias,alias_type,confidence,rationale,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (ident_id, user_id, alias, alias_type, confidence, rationale, utcnow()),
        )
        return ident_id

    def get_identities(self, user_id: str) -> list[dict]:
        return self._rows("SELECT * FROM identities WHERE user_id=? ORDER BY confidence DESC", (user_id,))

    def clear_identities(self, user_id: str):
        self._exec("DELETE FROM identities WHERE user_id=?", (user_id,))

    # ── exposures ────────────────────────────────────────────────────────────

    def record_exposure(self, user_id: str, run_id: str, exp: dict) -> tuple[str, bool]:
        """
        Insert or refresh an exposure. Returns (exposure_id, is_new).

        Identity is (user, source_id, record_id) so that re-scanning does not
        duplicate rows — and so a record that comes BACK after removal is
        detected as a reappearance rather than logged as brand new.
        """
        existing = self._row(
            "SELECT * FROM exposures WHERE user_id=? AND source_id=? AND IFNULL(record_id,'')=?",
            (user_id, exp.get("source_id", ""), exp.get("record_id", "") or ""),
        )
        if existing:
            status = existing["status"]
            if status == "removed":
                status = "reappeared"
            self._exec(
                "UPDATE exposures SET data_found=?, detail=?, match_confidence=?, match_tier=?, "
                "risk_score=?, severity=?, status=?, run_id=?, evidence_class=?, evidence=? "
                "WHERE id=?",
                (json.dumps(exp.get("data_found", [])), json.dumps(exp.get("detail", {})),
                 exp.get("match_confidence", 0.0), exp.get("match_tier", ""),
                 exp.get("risk_score", 0.0), exp.get("severity", ""), status, run_id,
                 exp.get("evidence_class", ""), json.dumps(exp.get("evidence", []), default=str),
                 existing["id"]),
            )
            return existing["id"], False

        exp_id = "exp_" + uuid.uuid4().hex[:10]
        self._exec(
            "INSERT INTO exposures (id,user_id,run_id,source_type,source_name,source_id,record_id,"
            "data_found,detail,match_confidence,match_tier,risk_score,severity,status,"
            "discovered_at,evidence_class,evidence) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (exp_id, user_id, run_id, exp.get("source_type", ""), exp.get("source_name", ""),
             exp.get("source_id", ""), exp.get("record_id", ""),
             json.dumps(exp.get("data_found", [])), json.dumps(exp.get("detail", {})),
             exp.get("match_confidence", 0.0), exp.get("match_tier", ""),
             exp.get("risk_score", 0.0), exp.get("severity", ""), "exposed", utcnow(),
             exp.get("evidence_class", ""), json.dumps(exp.get("evidence", []), default=str)),
        )
        return exp_id, True

    def get_exposures(self, user_id: str, status: str | None = None) -> list[dict]:
        if status:
            rows = self._rows(
                "SELECT * FROM exposures WHERE user_id=? AND status=? ORDER BY risk_score DESC",
                (user_id, status))
        else:
            rows = self._rows(
                "SELECT * FROM exposures WHERE user_id=? ORDER BY risk_score DESC", (user_id,))
        for r in rows:
            r["data_found"] = json.loads(r["data_found"] or "[]")
            r["detail"] = json.loads(r["detail"] or "{}")
            r["evidence"] = json.loads(r["evidence"] or "[]")
        return rows

    def get_exposure(self, exposure_id: str) -> dict | None:
        r = self._row("SELECT * FROM exposures WHERE id=?", (exposure_id,))
        if r:
            r["data_found"] = json.loads(r["data_found"] or "[]")
            r["detail"] = json.loads(r["detail"] or "{}")
            r["evidence"] = json.loads(r["evidence"] or "[]")
        return r

    def set_exposure_status(self, exposure_id: str, status: str, **stamps):
        sets = ["status=?"]
        params: list = [status]
        for col in ("removed_at", "verified_at"):
            if col in stamps:
                sets.append(f"{col}=?")
                params.append(stamps[col])
        params.append(exposure_id)
        self._exec(f"UPDATE exposures SET {', '.join(sets)} WHERE id=?", tuple(params))

    def update_exposure(self, exposure_id: str, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields.keys())
        params = list(fields.values()) + [exposure_id]
        self._exec(f"UPDATE exposures SET {cols} WHERE id=?", tuple(params))

    # ── requests ─────────────────────────────────────────────────────────────

    def create_request(self, user_id: str, exposure_id: str, req: dict) -> str:
        req_id = "req_" + uuid.uuid4().hex[:10]
        days = int(req.get("deadline_days", 30))
        deadline = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        self._exec(
            "INSERT INTO requests (id,user_id,exposure_id,jurisdiction,statute,legal_basis,request_text,"
            "reference_id,receipt_hash,status,created_at,deadline,deadline_days) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (req_id, user_id, exposure_id, req.get("jurisdiction", ""), req.get("statute", ""),
             req.get("legal_basis", ""), req.get("request_text", ""), req.get("reference_id", ""),
             req.get("receipt_hash", ""), req.get("status", "awaiting_approval"), utcnow(), deadline, days),
        )
        return req_id

    def open_request_for(self, exposure_id: str) -> dict | None:
        """An existing request for this exposure that has not been closed out.

        Re-scanning the same identity must not mint a second notice for the same
        record — that would serve a controller two identical demands and inflate
        the tracker with duplicates.
        """
        return self._row(
            "SELECT * FROM requests WHERE exposure_id=? "
            "AND status NOT IN ('completed','rejected') ORDER BY created_at DESC LIMIT 1",
            (exposure_id,),
        )

    def get_request(self, request_id: str) -> dict | None:
        return self._row("SELECT * FROM requests WHERE id=?", (request_id,))

    def get_requests(self, user_id: str) -> list[dict]:
        return self._rows("SELECT * FROM requests WHERE user_id=? ORDER BY created_at DESC", (user_id,))

    def update_request(self, request_id: str, **fields):
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._exec(f"UPDATE requests SET {sets} WHERE id=?", (*fields.values(), request_id))

    def overdue_requests(self, user_id: str) -> list[dict]:
        now = utcnow()
        return self._rows(
            "SELECT * FROM requests WHERE user_id=? AND deadline < ? "
            "AND status NOT IN ('completed','rejected','escalated')",
            (user_id, now),
        )

    # ── agent events (the trace) ─────────────────────────────────────────────

    def log_event(self, user_id: str, run_id: str, agent: str, phase: str, message: str,
                  tool_name: str = "", tool_input=None, tool_output=None, status: str = "ok") -> dict:
        ts = utcnow()
        self._exec(
            "INSERT INTO agent_events (user_id,run_id,ts,agent,phase,message,tool_name,tool_input,tool_output,status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (user_id, run_id, ts, agent, phase, message, tool_name,
             json.dumps(tool_input, default=str)[:4000] if tool_input is not None else None,
             json.dumps(tool_output, default=str)[:4000] if tool_output is not None else None,
             status),
        )
        return {"ts": ts, "agent": agent, "phase": phase, "message": message,
                "tool_name": tool_name, "status": status}

    def get_events(self, run_id: str) -> list[dict]:
        return self._rows("SELECT * FROM agent_events WHERE run_id=? ORDER BY id ASC", (run_id,))

    def recent_events(self, user_id: str, limit: int = 50) -> list[dict]:
        return self._rows(
            "SELECT * FROM agent_events WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))

    # ── audit receipts ───────────────────────────────────────────────────────

    def append_receipt(self, receipt: dict):
        self._exec(
            "INSERT INTO audit_receipts (receipt_id,timestamp,action,details,previous_hash,hash) "
            "VALUES (?,?,?,?,?,?)",
            (receipt.get("receipt_id"), receipt.get("timestamp"), receipt.get("action"),
             json.dumps(receipt.get("details", {}), sort_keys=True, default=str),
             receipt.get("previous_hash"), receipt.get("hash")),
        )

    def load_receipts(self) -> list[dict]:
        rows = self._rows("SELECT * FROM audit_receipts ORDER BY seq ASC")
        for r in rows:
            r["details"] = json.loads(r["details"] or "{}")
        return rows

    # ── summary for the dashboard ────────────────────────────────────────────

    def user_summary(self, user_id: str) -> dict:
        exps = self.get_exposures(user_id)
        reqs = self.get_requests(user_id)
        by_status: dict[str, int] = {}
        for e in exps:
            by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        return {
            "exposures_total": len(exps),
            "exposures_by_status": by_status,
            "high_risk": len([e for e in exps if (e["severity"] or "").lower() in ("critical", "high")]),
            "requests_total": len(reqs),
            "requests_submitted": len([r for r in reqs if r["status"] in
                                       ("submitted", "acknowledged", "completed", "escalated")]),
            "removals_verified": len([e for e in exps if e["status"] == "removed"]),
            "overdue": len(self.overdue_requests(user_id)),
        }

    def reset_user(self, user_id: str):
        """Wipe all agent records for a given user from SQLite."""
        for table in ("exposures", "requests", "agent_events", "identities", "runs"):
            self._exec(f"DELETE FROM {table} WHERE user_id=?", (user_id,))


_memory: Any = None


def get_memory() -> Any:
    global _memory
    if _memory is None:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if supabase_url and supabase_key:
            try:
                from backend.agent.supabase_memory import SupabaseMemory
                _memory = SupabaseMemory(supabase_url, supabase_key)
                print(f"[Supabase] Connected to Supabase Cloud Memory: {supabase_url}")
            except Exception as e:
                print(f"[Supabase] Warning: Failed to connect to Supabase ({e}), falling back to SQLite.")
                _memory = Memory()
        else:
            _memory = Memory()
    return _memory

