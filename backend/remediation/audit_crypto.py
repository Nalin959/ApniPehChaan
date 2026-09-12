"""
audit_crypto.py — Cryptographic Audit Receipt Generator.

Generates immutable SHA-256 digital receipts for every privacy action
(scan completed, notice generated, request dispatched), creating a
verifiable audit trail for regulatory compliance.
"""

import hashlib
import json
import uuid
from datetime import datetime


class AuditReceipt:
    """Represents an immutable cryptographic audit receipt."""

    def __init__(self, action: str, details: dict, previous_hash: str = ""):
        self.receipt_id = str(uuid.uuid4())
        self.timestamp = datetime.now().isoformat()
        self.action = action
        self.details = details
        self.previous_hash = previous_hash

        # Compute SHA-256 hash of entire receipt content
        content = json.dumps({
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }, sort_keys=True, default=str)
        self.hash = hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }

    def verify(self) -> bool:
        """Verify the receipt's hash integrity."""
        content = json.dumps({
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest() == self.hash


class AuditTrail:
    """
    Chain of cryptographic audit receipts.

    Each receipt references the hash of the previous receipt,
    forming a tamper-evident chain (similar to blockchain blocks).
    """

    def __init__(self):
        self._receipts: list[AuditReceipt] = []

        # Genesis receipt
        genesis = AuditReceipt(
            action="AUDIT_TRAIL_INITIALIZED",
            details={"agent": "SovereignPrivacy AI", "version": "1.0.0"},
            previous_hash="0" * 64,
        )
        self._receipts.append(genesis)

    def add(self, action: str, details: dict) -> AuditReceipt:
        """
        Add a new receipt to the audit trail.

        Args:
            action: Type of action (e.g., "SCAN_COMPLETED", "NOTICE_GENERATED", "REQUEST_DISPATCHED")
            details: Dict of action-specific details

        Returns:
            The newly created AuditReceipt
        """
        previous_hash = self._receipts[-1].hash if self._receipts else "0" * 64
        receipt = AuditReceipt(action=action, details=details, previous_hash=previous_hash)
        self._receipts.append(receipt)
        return receipt

    def get_all(self) -> list[dict]:
        """Return all receipts as dicts."""
        return [r.to_dict() for r in self._receipts]

    def get_latest(self, n: int = 10) -> list[dict]:
        """Return the last N receipts."""
        return [r.to_dict() for r in self._receipts[-n:]]

    def verify_chain(self) -> dict:
        """
        Verify the integrity of the entire audit chain.

        Returns:
            Dict with verification status and any breaks found.
        """
        breaks = []
        for i, receipt in enumerate(self._receipts):
            # Verify individual hash
            if not receipt.verify():
                breaks.append({
                    "index": i,
                    "receipt_id": receipt.receipt_id,
                    "issue": "Hash mismatch — receipt may have been tampered with",
                })

            # Verify chain linkage
            if i > 0:
                expected_prev = self._receipts[i - 1].hash
                if receipt.previous_hash != expected_prev:
                    breaks.append({
                        "index": i,
                        "receipt_id": receipt.receipt_id,
                        "issue": "Chain break — previous_hash does not match prior receipt",
                    })

        return {
            "total_receipts": len(self._receipts),
            "chain_valid": len(breaks) == 0,
            "breaks": breaks,
            "latest_hash": self._receipts[-1].hash if self._receipts else None,
        }

    def get_count(self) -> int:
        return len(self._receipts)
