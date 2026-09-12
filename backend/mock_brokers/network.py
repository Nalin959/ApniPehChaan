"""
network.py — A controlled data-broker environment.

Why this exists
---------------
The headline claim of this project is a closed loop:

    discover exposure -> assert a statutory right -> the data actually disappears

You cannot demonstrate the last step against real data brokers: removals take
weeks, need identity verification, and are not reproducible on a demo laptop.
So the removal loop runs against five simulated brokers that behave like the
real thing — each exposes a search surface, a privacy contact, a deletion
endpoint and a status endpoint, and each has its own response behaviour.

This is a simulation and the UI says so. What is NOT simulated is the part the
judges are actually assessing: the agent's discovery, reasoning, legal
selection, request drafting, dispatch, follow-up and verification all run for
real against these endpoints.

Records are seeded *from the identity the user enters*, so the demo works for
any name typed at the podium rather than only for a hardcoded persona.
"""

import hashlib
import json
import random
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from backend.agent.memory import DB_PATH, utcnow


BROKERS = {
    # ── India: commercial processing, full DPDP s.12 erasure right ───────────
    "truecaller-in": {
        "name": "Truecaller",
        "category": "Phone Directory",
        "country": "IN",
        "legal_class": "dpdp_erasure",
        "privacy_email": "privacy@truecaller.example",
        "privacy_url": "https://www.truecaller.com/unlisting",
        "behaviour": "prompt",
        "fields": ["name", "phone", "city", "employer"],
        "description": ("Reverse phone lookup built from contact books uploaded by other users. "
                        "Your number is listed because somebody else had you saved."),
    },
    "justdial-in": {
        "name": "JustDial",
        "category": "Local Search Directory",
        "country": "IN",
        "legal_class": "dpdp_erasure",
        "privacy_email": "grievance@justdial.example",
        "privacy_url": "https://www.justdial.com/",
        "behaviour": "slow",
        "fields": ["name", "phone", "email", "city"],
        "description": "Local search directory retaining caller and enquiry records.",
    },
    "naukri-in": {
        "name": "Naukri Resume Database",
        "category": "Resume Database",
        "country": "IN",
        "legal_class": "dpdp_erasure",
        "privacy_email": "dpo@naukri.example",
        "privacy_url": "https://www.naukri.com/",
        "behaviour": "compliant",
        "fields": ["name", "phone", "email", "city", "employer", "date_of_birth"],
        "description": ("Searchable CV database. Subscribing recruiters can download full profiles "
                        "including date of birth, salary and address."),
    },
    "leadkart-in": {
        "name": "LeadKart India",
        "category": "Marketing",
        "country": "IN",
        "legal_class": "dpdp_erasure",
        "privacy_email": "grievance@leadkart.example",
        "privacy_url": "https://leadkart.example/dpdp-request",
        "behaviour": "stubborn",
        "fields": ["name", "phone", "email", "city", "interests"],
        "description": ("Sells consumer lead lists segmented by city and purchase intent, "
                        "primarily to lenders and insurers."),
    },

    # ── India: statutory / judicial — erasure does NOT lie ───────────────────
    "indiankanoon-in": {
        "name": "Indian Kanoon",
        "category": "Judicial Records",
        "country": "IN",
        "legal_class": "judicial_record",
        "privacy_email": "",
        "privacy_url": "https://indiankanoon.org/",
        "behaviour": "not_servable",
        "fields": ["name", "city", "case_details"],
        "description": ("Full-text index of Indian court judgments, searchable by party name. "
                        "A DPDP notice does not reach a court record."),
    },
    "mcamirror-in": {
        "name": "MCA Director Registry Mirror",
        "category": "Corporate Registry Mirror",
        "country": "IN",
        "legal_class": "statutory_publication",
        "privacy_email": "",
        "privacy_url": "https://www.mca.gov.in/",
        "behaviour": "not_servable",
        "fields": ["name", "city", "din", "date_of_birth"],
        "description": ("Director particulars scraped from MCA21 filings published under the "
                        "Companies Act 2013."),
    },

    # ── International: kept so multi-jurisdiction routing is demonstrable ────
    "profilehub-eu": {
        "name": "ProfileHub",
        "category": "People Search Site",
        "country": "EU",
        "legal_class": "gdpr_erasure",
        "privacy_email": "gdpr@profilehub.example",
        "privacy_url": "https://profilehub.example/erasure",
        "behaviour": "compliant",
        "fields": ["name", "email", "username", "city"],
        "description": "Mirrors public social profiles into an indexed directory.",
    },
    "datafind-us": {
        "name": "DataFind Global",
        "category": "Profile Data Broker",
        "country": "US",
        "legal_class": "ccpa_deletion",
        "privacy_email": "dsr@datafindglobal.example",
        "privacy_url": "https://datafindglobal.example/ccpa-request",
        "behaviour": "slow",
        "fields": ["name", "email", "employer", "city"],
        "description": "Sells enriched B2B contact profiles built from scraped professional networks.",
    },
}

# Sources an erasure notice cannot be served on. The agent must recognise these
# and explain why, rather than drafting a letter that has no addressee in law.
NON_SERVABLE_CLASSES = {"judicial_record", "statutory_publication"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS broker_records (
    id         TEXT PRIMARY KEY,
    broker_id  TEXT,
    subject_key TEXT,
    name       TEXT,
    email      TEXT,
    phone      TEXT,
    city       TEXT,
    fields     TEXT,
    removed    INTEGER DEFAULT 0,
    created_at TEXT,
    removed_at TEXT
);
CREATE TABLE IF NOT EXISTS broker_requests (
    id              TEXT PRIMARY KEY,
    broker_id       TEXT,
    record_id       TEXT,
    requester_email TEXT,
    statute         TEXT,
    status          TEXT,
    followups       INTEGER DEFAULT 0,
    created_at      TEXT,
    updated_at      TEXT,
    confirmation_id TEXT,
    note            TEXT
);
CREATE INDEX IF NOT EXISTS idx_brec_subject ON broker_records(subject_key);
"""

EMPLOYERS = ["Infosys", "TCS", "Zomato", "HDFC Bank", "Freelance", "Wipro", "Paytm"]
INTERESTS = ["personal loans", "credit cards", "insurance", "real estate", "travel"]


def subject_key(name: str, email: str) -> str:
    """Stable key for 'this person' across brokers."""
    basis = (email or name or "").strip().lower()
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


class BrokerNetwork:
    """Five simulated brokers sharing one sqlite file with the agent's memory."""

    def __init__(self, path: str = DB_PATH):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()
        self._purge_retired_brokers()

    def _purge_retired_brokers(self):
        """Remove records whose broker slug is no longer in the registry."""
        known = set(BROKERS)
        rows = self._rows("SELECT DISTINCT broker_id FROM broker_records")
        stale = [r["broker_id"] for r in rows if r["broker_id"] not in known]
        for slug in stale:
            self._exec("DELETE FROM broker_requests WHERE broker_id=?", (slug,))
            self._exec("DELETE FROM broker_records WHERE broker_id=?", (slug,))
        if stale:
            print(f"  [brokers] purged records for retired slugs: {', '.join(stale)}")

    def _exec(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _rows(self, sql, params=()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _row(self, sql, params=()) -> dict | None:
        r = self._rows(sql, params)
        return r[0] if r else None

    # ── seeding ──────────────────────────────────────────────────────────────

    def seed_for_profile(self, profile: dict) -> int:
        """
        Plant records for this person across a deterministic subset of brokers.

        Deterministic in the person: the same identity always produces the same
        exposure pattern, so a rehearsed demo is reproducible, but any identity
        a judge types in also works.
        """
        name = (profile.get("name") or "").strip()
        email = (profile.get("email") or "").strip()
        if not name and not email:
            return 0

        key = subject_key(name, email)
        if self._row("SELECT id FROM broker_records WHERE subject_key=? LIMIT 1", (key,)):
            return 0  # already seeded

        rng = random.Random(key)              # seeded by identity -> reproducible
        phone = (profile.get("phone") or "").strip()
        city = (profile.get("city") or "Bengaluru").strip()

        # Every identity lands on 3-4 of the 5 brokers, always including the two
        # that make the demo's narrative work (a compliant one and a stubborn one).
        # India-first, and every run must contain all three teaching cases:
        #   naukri-in        -> clean DPDP erasure, critical-severity CV data
        #   leadkart-in      -> ignores the notice, drives DPBI escalation
        #   indiankanoon-in  -> erasure does not lie; the agent must refuse
        guaranteed = ["naukri-in", "leadkart-in", "indiankanoon-in"]
        optional = [b for b in BROKERS if b not in guaranteed]
        rng.shuffle(optional)
        chosen = guaranteed + optional[: rng.choice([2, 3])]

        count = 0
        for broker_id in chosen:
            spec = BROKERS[broker_id]
            extra: dict = {}
            if "employer" in spec["fields"]:
                extra["employer"] = rng.choice(EMPLOYERS)
            if "age_range" in spec["fields"]:
                extra["age_range"] = rng.choice(["18-24", "25-34", "35-44"])
            if "interests" in spec["fields"]:
                extra["interests"] = rng.sample(INTERESTS, 2)
            if "username" in spec["fields"] and email:
                extra["username"] = email.split("@")[0]

            rec_id = "rec_" + uuid.uuid4().hex[:10]
            self._exec(
                "INSERT INTO broker_records (id,broker_id,subject_key,name,email,phone,city,fields,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (rec_id, broker_id, key, name,
                 email if "email" in spec["fields"] else "",
                 phone if "phone" in spec["fields"] else "",
                 city, json.dumps(extra), utcnow()),
            )
            count += 1
        return count

    # ── broker API surface ───────────────────────────────────────────────────

    def list_brokers(self) -> list[dict]:
        out = []
        for bid, spec in BROKERS.items():
            live = self._row(
                "SELECT COUNT(*) c FROM broker_records WHERE broker_id=? AND removed=0", (bid,))
            out.append({"broker_id": bid, **spec, "live_records": live["c"] if live else 0})
        return out

    def privacy_policy(self, broker_id: str) -> dict | None:
        spec = BROKERS.get(broker_id)
        if not spec:
            return None
        return {
            "broker_id": broker_id,
            "name": spec["name"],
            "privacy_email": spec["privacy_email"],
            "privacy_url": spec["privacy_url"],
            "country": spec["country"],
            "accepts_erasure_requests": True,
            "data_categories": spec["fields"],
            "description": spec["description"],
        }

    def search(self, name: str = "", email: str = "", phone: str = "") -> list[dict]:
        """Search live (non-removed) records across the network."""
        clauses, params = [], []
        if email:
            clauses.append("LOWER(email)=?")
            params.append(email.strip().lower())
        if phone:
            digits = "".join(c for c in phone if c.isdigit())[-10:]
            if digits:
                clauses.append("REPLACE(REPLACE(phone,' ',''),'+','') LIKE ?")
                params.append(f"%{digits}")
        if name:
            clauses.append("LOWER(name)=?")
            params.append(name.strip().lower())
        if not clauses:
            return []

        rows = self._rows(
            f"SELECT * FROM broker_records WHERE removed=0 AND ({' OR '.join(clauses)})", tuple(params))
        results = []
        for r in rows:
            spec = BROKERS.get(r["broker_id"], {})
            fields = json.loads(r["fields"] or "{}")
            exposed = {k: v for k, v in
                       (("name", r["name"]), ("email", r["email"]), ("phone", r["phone"]), ("city", r["city"]))
                       if v}
            exposed.update(fields)
            results.append({
                "broker_id": r["broker_id"],
                "broker_name": spec.get("name", r["broker_id"]),
                "category": spec.get("category", ""),
                "country": spec.get("country", ""),
                "record_id": r["id"],
                "exposed_fields": exposed,
                "profile_url": f"https://{r['broker_id']}.example/p/{r['id']}",
            })
        return results

    def submit_erasure(self, broker_id: str, record_id: str, requester_email: str,
                       statute: str = "") -> dict:
        """Lodge an erasure request. Behaviour differs per broker, by design."""
        rec = self._row("SELECT * FROM broker_records WHERE id=? AND broker_id=?", (record_id, broker_id))
        if not rec:
            return {"status": "error", "message": "No such record at this broker."}
        if rec["removed"]:
            return {"status": "already_removed", "record_id": record_id}

        spec = BROKERS.get(broker_id)
        if spec is None:
            return {"status": "error",
                    "message": f"Unknown controller {broker_id!r} — the record predates the "
                               f"current broker registry. Re-scan this identity."}
        behaviour = spec["behaviour"]

        if behaviour == "not_servable":
            return {"status": "not_servable",
                    "broker": spec["name"],
                    "legal_class": spec.get("legal_class", ""),
                    "message": ("This source publishes under a statutory or judicial mandate. "
                                "An erasure notice has no addressee in law here.")}

        req_id = "brq_" + uuid.uuid4().hex[:10]
        confirmation = f"{broker_id.upper().replace('-', '')}-{uuid.uuid4().hex[:8].upper()}"

        if behaviour == "compliant":
            status, note = "completed", "Record erased on receipt of a valid request."
            self._remove(record_id)
        elif behaviour == "prompt":
            status, note = "acknowledged", "Request received and queued for processing."
        elif behaviour == "slow":
            status, note = "acknowledged", "Request received. Identity verification pending."
        else:  # stubborn
            status, note = "submitted", "No response from controller."

        self._exec(
            "INSERT INTO broker_requests (id,broker_id,record_id,requester_email,statute,status,"
            "created_at,updated_at,confirmation_id,note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (req_id, broker_id, record_id, requester_email, statute, status,
             utcnow(), utcnow(), confirmation, note),
        )
        return {
            "status": status,
            "broker_request_id": req_id,
            "confirmation_id": confirmation,
            "broker": spec["name"],
            "note": note,
        }

    def check_status(self, broker_request_id: str) -> dict:
        """
        Poll a lodged request. Polling advances the state machine, which is how
        the follow-up agent makes progress without a real calendar.
        """
        req = self._row("SELECT * FROM broker_requests WHERE id=?", (broker_request_id,))
        if not req:
            return {"status": "error", "message": "Unknown request id."}

        spec = BROKERS.get(req["broker_id"])
        if spec is None:
            return {"status": "error", "message": f"Unknown controller {req['broker_id']!r}."}
        behaviour, status = spec["behaviour"], req["status"]
        followups = req["followups"] + 1

        if behaviour == "prompt" and status == "acknowledged":
            status = "completed"
            self._remove(req["record_id"])
        elif behaviour == "slow" and status == "acknowledged" and followups >= 2:
            status = "completed"
            self._remove(req["record_id"])
        # 'stubborn' never advances — deliberately.

        self._exec("UPDATE broker_requests SET status=?, followups=?, updated_at=? WHERE id=?",
                   (status, followups, utcnow(), broker_request_id))
        return {
            "broker_request_id": broker_request_id,
            "broker": spec["name"],
            "status": status,
            "followups": followups,
            "confirmation_id": req["confirmation_id"],
            "note": req["note"],
        }

    def _remove(self, record_id: str):
        self._exec("UPDATE broker_records SET removed=1, removed_at=? WHERE id=?", (utcnow(), record_id))

    def record_exists(self, broker_id: str, record_id: str) -> bool:
        r = self._row("SELECT removed FROM broker_records WHERE id=? AND broker_id=?",
                      (record_id, broker_id))
        return bool(r) and not r["removed"]

    def reset_subject(self, name: str, email: str) -> int:
        """Wipe this person's records so a demo can be run again from scratch."""
        key = subject_key(name, email)
        ids = [r["id"] for r in self._rows("SELECT id FROM broker_records WHERE subject_key=?", (key,))]
        for rid in ids:
            self._exec("DELETE FROM broker_requests WHERE record_id=?", (rid,))
        self._exec("DELETE FROM broker_records WHERE subject_key=?", (key,))
        return len(ids)


_network: BrokerNetwork | None = None


def get_network() -> BrokerNetwork:
    global _network
    if _network is None:
        _network = BrokerNetwork()
    return _network
