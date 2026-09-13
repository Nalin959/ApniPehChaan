"""
statutory_tracker.py — 30-Day Statutory Compliance & Escalation Engine.

Tracks the lifecycle of data erasure requests across jurisdictions,
computes statutory deadlines, triggers escalation milestones,
and manages request state transitions.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field
import math
import uuid
import hashlib


def _parse(stamp: str, fallback: datetime) -> datetime:
    """Read a stored ISO timestamp as a naive local datetime.

    Two things this guards. A stamp that round-tripped through a timestamptz
    column comes back carrying an offset, and subtracting an aware datetime
    from a naive one raises TypeError — which would take out every endpoint
    that renders a tracked request, not just the arithmetic. And a malformed
    stamp raises ValueError from fromisoformat for the same blast radius. Both
    fall back to a supplied default rather than propagating.
    """
    try:
        dt = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return fallback
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


@dataclass
class ErasureRequest:
    """Represents a single data erasure request."""
    request_id: str
    jurisdiction: str
    company_name: str
    company_email: str
    user_name: str
    user_email: str
    notice_reference: str
    receipt_hash: str

    status: str = "pending"  # pending, dispatched, acknowledged, completed, escalated, expired
    created_at: str = ""
    dispatched_at: str = ""
    acknowledged_at: str = ""
    completed_at: str = ""
    deadline: str = ""
    deadline_days: int = 30

    milestones: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        now = datetime.now()
        deadline_dt = _parse(self.deadline, now) if self.deadline else now
        # timedelta.days TRUNCATES, and every deadline here is set to a whole
        # number of days after a moment that has already passed, so the remainder
        # is 29 days 23:59:59 from the instant the request is created — and a
        # notice served seconds ago reported "29 days remaining" on a 30-day
        # statutory clock (44 on CCPA's 45). Worse at the other end: with twelve
        # hours still to run it reported 0 while is_overdue was still False, so
        # the UI said the clock had expired when it had not. A partly-elapsed day
        # is a day the controller still has, so the remainder rounds up.
        if self.deadline:
            remaining = (deadline_dt - now).total_seconds()
            days_remaining = max(0, math.ceil(remaining / 86400.0))
        else:
            days_remaining = 0
        days_elapsed = (now - _parse(self.created_at, now)).days if self.created_at else 0
        progress_pct = min(100, (days_elapsed / self.deadline_days * 100)) if self.deadline_days else 0

        # Milestone dates are fixed at creation and their `status` was too, so a
        # request 20 days old still reported Day 7 and Day 14 as "pending". The
        # stored status is left alone deliberately — flipping a "First follow-up
        # reminder" to "completed" would claim a reminder was sent, and nothing
        # here sends one — but whether the date has been REACHED is a fact, and
        # it is now reported so a consumer need not recompute it.
        milestones = []
        for ms in (self.milestones or []):
            ms_dt = _parse(ms.get("date", ""), now) if isinstance(ms, dict) else now
            entry = dict(ms) if isinstance(ms, dict) else {"date": "", "label": str(ms)}
            entry["reached"] = now >= ms_dt
            entry["days_until"] = math.ceil((ms_dt - now).total_seconds() / 86400.0)
            milestones.append(entry)

        return {
            "request_id": self.request_id,
            "jurisdiction": self.jurisdiction,
            "company_name": self.company_name,
            "company_email": self.company_email,
            "user_name": self.user_name,
            "user_email": self.user_email,
            "notice_reference": self.notice_reference,
            "receipt_hash": self.receipt_hash,
            "status": self.status,
            "created_at": self.created_at,
            "dispatched_at": self.dispatched_at,
            "acknowledged_at": self.acknowledged_at,
            "completed_at": self.completed_at,
            "deadline": self.deadline,
            "deadline_days": self.deadline_days,
            "days_remaining": days_remaining,
            "days_elapsed": days_elapsed,
            "progress_pct": round(progress_pct, 1),
            "milestones": milestones,
            "notes": self.notes,
            "is_overdue": now > deadline_dt if self.deadline else False,
        }


# Jurisdiction-specific deadline configurations
DEADLINE_CONFIGS = {
    "dpdp": {
        "total_days": 30,
        "acknowledgment_days": 2,
        "milestones": [
            {"day": 0, "label": "Notice dispatched", "action": "dispatch"},
            {"day": 2, "label": "48-hour acknowledgment deadline", "action": "check_ack"},
            {"day": 7, "label": "First follow-up reminder", "action": "reminder_1"},
            {"day": 14, "label": "Second follow-up — formal warning", "action": "reminder_2"},
            {"day": 21, "label": "Pre-escalation notice", "action": "pre_escalate"},
            {"day": 30, "label": "Statutory deadline — DPBI complaint eligible", "action": "escalate"},
        ],
        "escalation_body": "Data Protection Board of India (DPBI)",
        "escalation_url": "https://www.meity.gov.in/data-protection",
    },
    "gdpr": {
        "total_days": 30,
        "acknowledgment_days": 3,
        "milestones": [
            {"day": 0, "label": "Request submitted", "action": "dispatch"},
            {"day": 3, "label": "72-hour acknowledgment window", "action": "check_ack"},
            {"day": 7, "label": "Follow-up inquiry", "action": "reminder_1"},
            {"day": 14, "label": "Second follow-up", "action": "reminder_2"},
            {"day": 25, "label": "Final notice before escalation", "action": "pre_escalate"},
            {"day": 30, "label": "Article 77 Supervisory Authority complaint", "action": "escalate"},
        ],
        "escalation_body": "EU Data Protection Supervisory Authority",
        "escalation_url": "https://edpb.europa.eu/about-edpb/about-edpb/members_en",
    },
    "ccpa": {
        "total_days": 45,
        "acknowledgment_days": 10,
        "milestones": [
            {"day": 0, "label": "Deletion request submitted", "action": "dispatch"},
            {"day": 10, "label": "10 business day acknowledgment deadline", "action": "check_ack"},
            {"day": 20, "label": "Mid-period follow-up", "action": "reminder_1"},
            {"day": 35, "label": "Pre-deadline reminder", "action": "reminder_2"},
            {"day": 45, "label": "45-day statutory deadline — CPPA complaint eligible", "action": "escalate"},
        ],
        "escalation_body": "California Privacy Protection Agency (CPPA)",
        "escalation_url": "https://cppa.ca.gov/",
    },
}


class StatutoryTracker:
    """Tracks statutory compliance deadlines for data erasure requests."""

    def __init__(self):
        self._requests: dict[str, ErasureRequest] = {}

    def create_request(
        self,
        jurisdiction: str,
        company_name: str,
        company_email: str,
        user_name: str,
        user_email: str,
        notice_reference: str,
        receipt_hash: str,
    ) -> dict:
        """Create a new tracked erasure request."""
        config = DEADLINE_CONFIGS.get(jurisdiction, DEADLINE_CONFIGS["dpdp"])
        now = datetime.now()
        deadline = now + timedelta(days=config["total_days"])

        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"

        # Compute milestones with absolute dates
        milestones = []
        for ms in config["milestones"]:
            ms_date = now + timedelta(days=ms["day"])
            milestones.append({
                "day": ms["day"],
                "date": ms_date.isoformat(),
                "label": ms["label"],
                "action": ms["action"],
                "status": "completed" if ms["day"] == 0 else "pending",
            })

        req = ErasureRequest(
            request_id=request_id,
            jurisdiction=jurisdiction,
            company_name=company_name,
            company_email=company_email,
            user_name=user_name,
            user_email=user_email,
            notice_reference=notice_reference,
            receipt_hash=receipt_hash,
            status="dispatched",
            created_at=now.isoformat(),
            dispatched_at=now.isoformat(),
            deadline=deadline.isoformat(),
            deadline_days=config["total_days"],
            milestones=milestones,
        )

        self._requests[request_id] = req
        return req.to_dict()

    def get_request(self, request_id: str) -> dict | None:
        req = self._requests.get(request_id)
        return req.to_dict() if req else None

    def get_all_requests(self) -> list[dict]:
        return [req.to_dict() for req in self._requests.values()]

    def update_status(self, request_id: str, new_status: str, note: str = "") -> dict | None:
        """Update the status of a request."""
        req = self._requests.get(request_id)
        if not req:
            return None

        now = datetime.now()
        req.status = new_status
        if new_status == "acknowledged":
            req.acknowledged_at = now.isoformat()
        elif new_status == "completed":
            req.completed_at = now.isoformat()

        if note:
            req.notes.append({"timestamp": now.isoformat(), "note": note})

        return req.to_dict()

    def get_overdue_requests(self) -> list[dict]:
        """Get requests that have exceeded their statutory deadline."""
        now = datetime.now()
        overdue = []
        for req in self._requests.values():
            if req.deadline and req.status not in ("completed", "escalated"):
                deadline_dt = _parse(req.deadline, now)
                if now > deadline_dt:
                    overdue.append(req.to_dict())
        return overdue

    def get_summary(self) -> dict:
        """Get summary statistics of all tracked requests."""
        statuses = {}
        for req in self._requests.values():
            statuses[req.status] = statuses.get(req.status, 0) + 1

        return {
            "total_requests": len(self._requests),
            "by_status": statuses,
            "overdue_count": len(self.get_overdue_requests()),
        }
