"""
broker_scanner.py — Data Broker Exposure Scanner.

Searches the Optery data broker directory (956+ brokers) to identify
which data brokers likely hold user data, categorized by broker type,
removal difficulty, and available opt-out mechanisms.
"""

import json
import os
from datetime import datetime


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
BROKERS_FILE = os.path.join(DATA_DIR, "brokers", "optery_brokers.json")


class BrokerScanner:
    """Scanner that evaluates data broker exposure risk."""

    def __init__(self):
        self._brokers: list[dict] = []
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        try:
            with open(BROKERS_FILE, "r") as f:
                self._brokers = json.load(f)
            self._loaded = True
        except FileNotFoundError:
            self._brokers = []
            self._loaded = True

    def scan(self, user_name: str = "", user_email: str = "", user_phone: str = "", user_city: str = "") -> dict:
        """
        Scan data broker directory for potential exposure.

        Since we can't actually query each broker site (rate limits, CAPTCHAs),
        we estimate exposure based on broker category and user data types.

        Returns broker matches with opt-out information and risk assessment.
        """
        self._load()

        if not any([user_name, user_email, user_phone]):
            return {"status": "error", "message": "Insufficient identity data", "matches": [], "stats": {}}

        # Categorize brokers and determine likely exposure
        matches = []
        categories_found = {}

        for broker in self._brokers:
            category = broker.get("category", "Unknown")
            name = broker.get("name", "")

            # Estimate exposure likelihood based on category and user data
            exposure_likelihood = 0.0
            exposure_reason = []

            # Category matching is substring-based against the categories the
            # Optery export actually uses. The previous exact-equality list
            # matched none of "People Search Site" (386 brokers), "B2B Lead
            # Generation" (127), "Business Search" (72) or "Profile Data
            # Broker" (46), so 631 of 956 brokers silently fell through to the
            # generic branch and every user got the identical result.
            cat = category.lower()

            if "people search" in cat or "people directory" in cat or "profile data" in cat:
                if user_name:
                    exposure_likelihood = 0.85
                    exposure_reason.append("People search sites aggregate public records by name")
                if user_city:
                    exposure_likelihood = min(exposure_likelihood + 0.10, 0.95)
                    exposure_reason.append("City narrows profile match accuracy")

            elif "phone" in cat:
                if user_phone:
                    exposure_likelihood = 0.80
                    exposure_reason.append("Phone directories index mobile and landline numbers")

            elif "background" in cat or "criminal" in cat:
                if user_name:
                    exposure_likelihood = 0.60
                    exposure_reason.append("Background check services compile identity profiles")

            elif "b2b" in cat or "lead generation" in cat or "business search" in cat:
                if user_email:
                    exposure_likelihood = 0.65
                    exposure_reason.append("B2B lead vendors resell work contact details")
                elif user_name:
                    exposure_likelihood = 0.40
                    exposure_reason.append("B2B vendors index professional profiles by name")

            elif "marketing" in cat or "data broker" in cat or "aggregator" in cat:
                exposure_likelihood = 0.50
                exposure_reason.append("Marketing data brokers purchase and resell consumer data")

            elif "email" in cat:
                if user_email:
                    exposure_likelihood = 0.70
                    exposure_reason.append("Email lookup services index email-to-identity mappings")

            else:
                exposure_likelihood = 0.30
                exposure_reason.append("General data aggregation — possible exposure")

            if exposure_likelihood >= 0.30:
                # Determine removal difficulty
                opt_out_url = broker.get("opt_out_url", "")
                privacy_email = broker.get("privacy_email", "")
                removal_tier = broker.get("removal_tier", "Unknown")

                if opt_out_url:
                    removal_difficulty = "Easy"
                    removal_method = "Online opt-out form available"
                elif privacy_email:
                    removal_difficulty = "Medium"
                    removal_method = "Email privacy officer for removal"
                else:
                    removal_difficulty = "Hard"
                    removal_method = "No direct opt-out — legal notice required"

                matches.append({
                    "broker_name": name,
                    "website": broker.get("website", ""),
                    "category": category,
                    "exposure_likelihood": round(exposure_likelihood, 2),
                    "exposure_reason": exposure_reason,
                    "opt_out_url": opt_out_url,
                    "privacy_email": privacy_email,
                    "removal_difficulty": removal_difficulty,
                    "removal_method": removal_method,
                    "removal_tier": removal_tier,
                    "description": broker.get("description", "")[:200],
                })

                # Count categories
                categories_found[category] = categories_found.get(category, 0) + 1

        # Sort by exposure likelihood descending, then easiest removal first.
        # The tie-break used the difficulty STRING, which sorts alphabetically —
        # Easy, Hard, Medium — so the ones needing a legal notice were ranked
        # above the ones needing an email, the opposite of the intended order.
        _difficulty_rank = {"Easy": 0, "Medium": 1, "Hard": 2}
        matches.sort(key=lambda x: (-x["exposure_likelihood"],
                                    _difficulty_rank.get(x["removal_difficulty"], 3)))

        # Stats
        high_risk = [m for m in matches if m["exposure_likelihood"] >= 0.70]
        easy_removals = [m for m in matches if m["removal_difficulty"] == "Easy"]

        stats = {
            "total_brokers_checked": len(self._brokers),
            "potential_matches": len(matches),
            "high_risk_matches": len(high_risk),
            "easy_removals_available": len(easy_removals),
            "categories_found": categories_found,
            "scan_timestamp": datetime.now().isoformat(),
        }

        return {
            "status": "complete",
            "matches": matches[:100],  # Top 100
            "high_risk": high_risk[:20],
            "stats": stats,
            # Said plainly in the payload, not only in the docstring. No broker
            # here was queried — they sit behind rate limits and CAPTCHAs — so
            # every number above is a scope estimate from the broker's CATEGORY
            # and which identity fields the user supplied. Downstream copy must
            # not render it as "your data was found on N sites".
            "basis": "estimated_from_category",
            "confirmed": False,
            "note": ("No broker was queried. Each broker is scored from its category and the "
                     "identity fields supplied, so these are candidates to check and opt out "
                     "of, not confirmed hits. A name is a weak signal on its own: any name "
                     "produces the same people-search estimate."),
        }

    def get_broker_count(self) -> int:
        self._load()
        return len(self._brokers)

    def get_categories(self) -> dict:
        """Return category breakdown of all brokers."""
        self._load()
        cats = {}
        for b in self._brokers:
            c = b.get("category", "Unknown")
            cats[c] = cats.get(c, 0) + 1
        return dict(sorted(cats.items(), key=lambda x: -x[1]))
