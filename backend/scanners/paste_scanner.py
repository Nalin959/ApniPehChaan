"""
paste_scanner.py — Dark Web Paste & Breach Dump Scanner.

Scans the synthetic paste corpus for leaked PII matching a user's identity.
Uses the PII recognizer to extract entities, then the identity resolver
to match them against the user's profile.
"""

import json
import os
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pii.recognizer import PIIRecognizer
from pii.resolver import IdentityResolver


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
PASTES_FILE = os.path.join(DATA_DIR, "synthetic_pastes", "pastes_corpus.json")


class PasteScanner:
    """Scanner for dark-web paste dumps and breach fragments."""

    def __init__(self):
        self._pastes: list[dict] = []
        self._loaded = False
        self._recognizer = PIIRecognizer()
        self._resolver = IdentityResolver()

    def _load(self):
        if self._loaded:
            return
        try:
            with open(PASTES_FILE, "r") as f:
                self._pastes = json.load(f)
            self._loaded = True
        except FileNotFoundError:
            self._pastes = []
            self._loaded = True

    def scan(self, user_profile: dict) -> dict:
        """
        Scan paste corpus for leaks matching the user's identity.

        Args:
            user_profile: dict with keys like "name", "email", "phone", "aadhaar", "pan"

        Returns:
            Dict with matched leaks, extracted PII, and identity resolution results.
        """
        self._load()

        user_email = (user_profile.get("email") or "").lower()
        user_phone = (user_profile.get("phone") or "").replace(" ", "").replace("-", "").replace("+91", "").lstrip("0")
        user_name = (user_profile.get("name") or "").lower()

        matches = []
        scan_steps = []

        for paste in self._pastes:
            content = paste.get("content", "")
            paste_id = paste.get("id", "")
            paste_type = paste.get("type", "unknown")

            # Step 1: Quick text search for any user identifiers
            content_lower = content.lower()
            quick_match = False
            quick_reasons = []

            if user_email and user_email in content_lower:
                quick_match = True
                quick_reasons.append("Email found in content")
            if user_phone and len(user_phone) >= 10 and user_phone in content.replace(" ", "").replace("-", ""):
                quick_match = True
                quick_reasons.append("Phone number found in content")
            if user_name and len(user_name) >= 3:
                name_parts = user_name.split()
                for part in name_parts:
                    if len(part) >= 3 and part in content_lower:
                        quick_match = True
                        quick_reasons.append(f"Name component '{part}' found in content")
                        break

            # Step 2: If quick match found, run full PII extraction
            if quick_match:
                entities = self._recognizer.recognize(content)
                entity_summary = self._recognizer.get_summary(entities)

                # Step 3: Build detected record from extracted entities
                detected_record = {}
                for e in entities:
                    if e.entity_type == "EMAIL":
                        detected_record["email"] = e.value
                    elif e.entity_type in ("PHONE_IN", "PHONE_INTL"):
                        detected_record["phone"] = e.value
                    elif e.entity_type == "AADHAAR":
                        detected_record["aadhaar"] = e.value
                    elif e.entity_type == "PAN":
                        detected_record["pan"] = e.value
                    elif e.entity_type == "UPI":
                        detected_record["upi"] = e.value

                # Step 4: Run identity resolution
                resolution = self._resolver.resolve(user_profile, detected_record)

                # Determine severity
                has_financial = any(e.entity_type in ("AADHAAR", "PAN", "CREDIT_CARD", "BANK_ACCOUNT") for e in entities)
                severity = "critical" if has_financial else ("high" if resolution.is_match else "medium")

                matches.append({
                    "paste_id": paste_id,
                    "paste_type": paste_type,
                    "source": paste.get("source", ""),
                    "date_found": paste.get("date_found", ""),
                    "severity": severity,
                    "quick_match_reasons": quick_reasons,
                    "entities_found": [e.to_dict() for e in entities],
                    "entity_summary": {k: v for k, v in entity_summary.items() if k not in ("total_count", "types_found")},
                    "entity_types_found": entity_summary.get("types_found", []),
                    "entity_count": entity_summary.get("total_count", 0),
                    "identity_resolution": resolution.to_dict(),
                    "content_preview": content[:300] + ("..." if len(content) > 300 else ""),
                })

            scan_steps.append({
                "paste_id": paste_id,
                "paste_type": paste_type,
                "checked": True,
                "matched": quick_match,
            })

        # Sort matches by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        matches.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 5))

        stats = {
            "total_pastes_scanned": len(self._pastes),
            "matches_found": len(matches),
            "critical_matches": sum(1 for m in matches if m.get("severity") == "critical"),
            "high_matches": sum(1 for m in matches if m.get("severity") == "high"),
            "scan_timestamp": datetime.now().isoformat(),
        }

        return {
            "status": "complete",
            "matches": matches,
            "scan_steps": scan_steps,
            "stats": stats,
        }

    def get_paste_count(self) -> int:
        self._load()
        return len(self._pastes)
