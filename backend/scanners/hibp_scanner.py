"""
hibp_scanner.py — Have I Been Pwned Breach Intelligence Scanner.

Queries the locally-cached HIBP breach catalog and performs
domain-based and data-class matching to identify relevant breaches
for a given user's email address.
"""

import json
import os
from datetime import datetime


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
BREACHES_FILE = os.path.join(DATA_DIR, "breaches", "hibp_breaches.json")


class HIBPScanner:
    """Scanner that matches user email domains against the HIBP breach catalog."""

    def __init__(self):
        self._breaches: list[dict] = []
        self._loaded = False

    def _load(self):
        """Load the HIBP breach catalog from local cache."""
        if self._loaded:
            return
        try:
            with open(BREACHES_FILE, "r") as f:
                self._breaches = json.load(f)
            self._loaded = True
        except FileNotFoundError:
            self._breaches = []
            self._loaded = True

    def scan(self, email: str, name: str = "") -> dict:
        """
        Scan for breaches relevant to a given email/domain.

        Returns a summary dict with matched breaches, statistics, and risk indicators.
        """
        self._load()

        if not email:
            return {"status": "error", "message": "No email provided", "breaches": [], "stats": {}}

        domain = email.split("@")[-1].lower() if "@" in email else ""
        email_lower = email.lower()
        results = []
        total_records_exposed = 0

        for breach in self._breaches:
            breach_domain = (breach.get("domain") or "").lower()
            breach_name = (breach.get("name") or "").lower()
            data_classes = breach.get("data_classes", [])

            # Match by domain
            relevance_score = 0
            match_reason = []

            if breach_domain and breach_domain == domain:
                relevance_score += 0.9
                match_reason.append(f"Email domain matches breach domain ({breach_domain})")

            # Check for email-containing data classes
            has_email = any("email" in dc.lower() for dc in data_classes)
            has_passwords = any("password" in dc.lower() for dc in data_classes)
            has_names = any("name" in dc.lower() for dc in data_classes)
            has_phone = any("phone" in dc.lower() for dc in data_classes)
            has_address = any("address" in dc.lower() for dc in data_classes)
            has_financial = any(
                any(term in dc.lower() for term in ["credit", "bank", "financial", "payment"])
                for dc in data_classes
            )

            if relevance_score > 0:
                # Determine severity
                severity = "low"
                if has_financial or has_passwords:
                    severity = "critical"
                elif has_phone or has_address:
                    severity = "high"
                elif has_email:
                    severity = "medium"

                pwn_count = breach.get("pwn_count", 0)
                total_records_exposed += pwn_count

                results.append({
                    "name": breach.get("name", ""),
                    "title": breach.get("title", ""),
                    "domain": breach.get("domain", ""),
                    "breach_date": breach.get("breach_date", ""),
                    "pwn_count": pwn_count,
                    "data_classes": data_classes,
                    "is_verified": breach.get("is_verified", False),
                    "is_sensitive": breach.get("is_sensitive", False),
                    "severity": severity,
                    "relevance_score": round(relevance_score, 2),
                    "match_reason": match_reason,
                    "has_email": has_email,
                    "has_passwords": has_passwords,
                    "has_financial": has_financial,
                })

        # Also do a general keyword scan for large breaches (>1M records) that
        # may have collected data from many domains
        major_breaches = []
        for breach in self._breaches:
            if breach.get("pwn_count", 0) >= 1_000_000:
                data_classes = breach.get("data_classes", [])
                has_email = any("email" in dc.lower() for dc in data_classes)
                if has_email and breach not in [r for r in results]:
                    # Flag as potential exposure
                    if not any(r["name"] == breach["name"] for r in results):
                        major_breaches.append({
                            "name": breach.get("name", ""),
                            "title": breach.get("title", ""),
                            "domain": breach.get("domain", ""),
                            "breach_date": breach.get("breach_date", ""),
                            "pwn_count": breach.get("pwn_count", 0),
                            "data_classes": data_classes,
                            "severity": "potential",
                            "note": "Major breach (>1M records) with email data — possible indirect exposure",
                        })

        # Sort by severity, then by pwn_count descending
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "potential": 4}
        results.sort(key=lambda x: (severity_order.get(x.get("severity", "low"), 5), -x.get("pwn_count", 0)))

        stats = {
            "total_breaches_checked": len(self._breaches),
            "direct_matches": len(results),
            "major_breaches_flagged": len(major_breaches),
            "total_records_exposed": total_records_exposed,
            "critical_count": sum(1 for r in results if r.get("severity") == "critical"),
            "high_count": sum(1 for r in results if r.get("severity") == "high"),
            "scan_timestamp": datetime.now().isoformat(),
        }

        return {
            "status": "complete",
            "email_scanned": email,
            "domain_scanned": domain,
            "breaches": results,
            "major_breaches": major_breaches[:10],  # Top 10 major
            "stats": stats,
        }

    def get_breach_count(self) -> int:
        """Return total number of breaches in catalog."""
        self._load()
        return len(self._breaches)

    def get_top_breaches(self, n: int = 10) -> list[dict]:
        """Return top N breaches by record count."""
        self._load()
        sorted_breaches = sorted(self._breaches, key=lambda b: b.get("pwn_count", 0), reverse=True)
        return sorted_breaches[:n]
