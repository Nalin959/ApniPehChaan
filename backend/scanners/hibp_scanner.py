"""
hibp_scanner.py — Have I Been Pwned Breach Intelligence Scanner.

Queries the locally-cached HIBP breach catalog for breaches that are worth
REVIEWING for a given email address.

WHAT THIS CATALOG CAN AND CANNOT ANSWER
---------------------------------------
The cached file is HIBP's *breach catalog*: one record per breached
organisation — its name, domain, date, record count and data classes. It
contains no email addresses at all. So nothing in this file can establish that
a particular mailbox was in a particular dump. Only the per-account API can do
that, and it needs a paid key; `backend/agent/verifiers.check_hibp_account`
is where that lives, and it correctly refuses to claim anything without one.

This module therefore never reports a confirmed exposure. It reports SIGNALS.

THE FAILURE THIS WAS BUILT TO PREVENT
-------------------------------------
The original matcher's only condition was `breach_domain == domain`, where
`domain` is the domain of the user's own address. It then emitted the breach
into `breaches` with relevance 0.9 and severity "critical", and the /api/scan/full
endpoint turned every one of that breach's data classes into an exposure tagged
`hibp_verified` (credibility 1.0) in the risk score.

The domain of an ordinary person's address is their MAIL PROVIDER. The catalog
carries yahoo.com, mail.ru and 163.com as breached organisations, so every user
with a Yahoo address was told, as a confirmed critical finding, that they were
in the Yahoo breach — on the strength of who hosts their mailbox. The same held
for a work address at any catalogued company.

A domain match is a real fact about the DOMAIN and says nothing about the
individual mailbox, exactly as `verifiers.check_email_domain_breached` already
explains. It is now returned in `domain_signals`, labelled unconfirmed, and
`breaches` — the list downstream code treats as attributed exposure — stays
empty because this catalog can confirm nothing.
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

        Returns a summary dict. `breaches` holds CONFIRMED exposures only and is
        therefore always empty here: the local catalog holds no account data, so
        membership of a dump cannot be established from it. Domain coincidences
        and large email-bearing breaches are returned separately, labelled as
        the unconfirmed leads they are.
        """
        self._load()

        if not email:
            return {"status": "error", "message": "No email provided", "breaches": [], "stats": {}}

        domain = email.split("@")[-1].lower().strip() if "@" in email else ""
        results = []
        domain_signals = []

        for breach in self._breaches:
            breach_domain = (breach.get("domain") or "").lower()
            data_classes = breach.get("data_classes", [])

            if not (breach_domain and breach_domain == domain):
                continue

            has_email = any("email" in dc.lower() for dc in data_classes)
            has_passwords = any("password" in dc.lower() for dc in data_classes)
            has_phone = any("phone" in dc.lower() for dc in data_classes)
            has_address = any("address" in dc.lower() for dc in data_classes)
            has_financial = any(
                any(term in dc.lower() for term in ["credit", "bank", "financial", "payment"])
                for dc in data_classes
            )

            domain_signals.append({
                "name": breach.get("name", ""),
                "title": breach.get("title", ""),
                "domain": breach.get("domain", ""),
                "breach_date": breach.get("breach_date", ""),
                "pwn_count": breach.get("pwn_count", 0),
                "data_classes": data_classes,
                "is_verified": breach.get("is_verified", False),
                "is_sensitive": breach.get("is_sensitive", False),
                # Deliberately NOT a severity grade. Grading an unconfirmed lead
                # "critical" is how it gets read as a finding.
                "severity": "unconfirmed",
                "confirmed": False,
                "relevance_score": 0.0,
                "match_reason": [
                    f"The organisation behind '{breach_domain}' was itself breached."
                ],
                "caveat": (
                    f"This is a fact about the domain '{breach_domain}', not about this "
                    f"mailbox. If '{breach_domain}' is your mail PROVIDER, it says only that "
                    f"your provider was breached — it is not evidence that this address was "
                    f"in the dump. Confirming that needs a per-account HIBP lookup "
                    f"(backend/agent/verifiers.check_hibp_account, paid API key required)."
                ),
                "has_email": has_email,
                "has_passwords": has_passwords,
                "has_financial": has_financial,
                "has_phone": has_phone,
                "has_address": has_address,
            })

        # Large email-bearing breaches. Also a lead, never a finding: a breach
        # being big is not evidence that it holds this person.
        major_breaches = []
        for breach in self._breaches:
            if breach.get("pwn_count", 0) < 1_000_000:
                continue
            data_classes = breach.get("data_classes", [])
            if not any("email" in dc.lower() for dc in data_classes):
                continue
            if any(s["name"] == breach.get("name", "") for s in domain_signals):
                continue
            major_breaches.append({
                "name": breach.get("name", ""),
                "title": breach.get("title", ""),
                "domain": breach.get("domain", ""),
                "breach_date": breach.get("breach_date", ""),
                "pwn_count": breach.get("pwn_count", 0),
                "data_classes": data_classes,
                "severity": "potential",
                "confirmed": False,
                "note": "Major breach (>1M records) with email data — possible indirect exposure",
            })

        domain_signals.sort(key=lambda x: -x.get("pwn_count", 0))
        major_breaches.sort(key=lambda x: -x.get("pwn_count", 0))

        stats = {
            "total_breaches_checked": len(self._breaches),
            "direct_matches": len(results),
            "confirmed_matches": len(results),
            "domain_signals": len(domain_signals),
            "major_breaches_flagged": len(major_breaches),
            # Records exposed by CONFIRMED matches. Summing the record counts of
            # unconfirmed leads produced a headline number ("234,842,089 of your
            # records exposed") out of a domain coincidence.
            "total_records_exposed": 0,
            "critical_count": sum(1 for r in results if r.get("severity") == "critical"),
            "high_count": sum(1 for r in results if r.get("severity") == "high"),
            "scan_timestamp": datetime.now().isoformat(),
        }

        return {
            "status": "complete",
            "email_scanned": email,
            "domain_scanned": domain,
            # Confirmed, attributable exposures only. Downstream code (the risk
            # score, the exposure list) consumes this key, so an unconfirmed lead
            # must never appear in it.
            "breaches": results,
            "domain_signals": domain_signals,
            "major_breaches": major_breaches[:10],  # Top 10 major
            "stats": stats,
            "note": (
                "The local HIBP catalog lists breached ORGANISATIONS, not the addresses in "
                "them, so it cannot confirm that this address was in any dump. Everything "
                "returned here is a lead to check, not a finding."
            ),
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
