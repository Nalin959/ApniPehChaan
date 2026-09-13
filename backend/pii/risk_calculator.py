"""
risk_calculator.py — Dynamic Privacy Risk Scoring Engine.

Computes a composite privacy vulnerability score (0–100) based on:
  • Volume of exposed data points
  • Sensitivity weighting of each data type
  • Source credibility (verified breach vs paste)
  • Recency of exposure
  • Data broker coverage
"""

import math
from datetime import datetime, timedelta
from dataclasses import dataclass


# Sensitivity weights: higher = more dangerous if exposed
SENSITIVITY_WEIGHTS = {
    "AADHAAR":       10.0,   # Highest — national ID, irreplaceable
    "PAN":            9.0,   # Tax/financial identity
    "BANK_ACCOUNT":   9.0,
    "CREDIT_CARD":    8.5,
    "IFSC":           4.0,
    "UPI":            6.0,
    "VOTER_ID":       7.0,
    "EMAIL":          3.0,
    "PHONE_IN":       4.0,
    "PHONE_INTL":     3.5,
    "IP_ADDRESS":     2.5,
    "PIN_CODE":       1.5,
    "NAME":           2.0,
    "ADDRESS":        3.5,
    # A leaked password is not a fact about you, it is live access to an
    # account, and it is reusable everywhere you reused it.
    "PASSWORD":       9.0,
    "AUTH_TOKEN":     9.5,   # a session token bypasses the password entirely
    "SECURITY_ANSWER": 8.0,  # resets the password, so it outranks the password
    "GOVERNMENT_ID":  9.5,   # national ID: cannot be reissued like a card
    "PASSPORT":       9.0,
    "SSN":            9.5,
    "DATE_OF_BIRTH":  5.0,   # the other half of most identity-verification pairs
    # Special-category data under DPDP s.2 / GDPR Art.9. The harm is not
    # financial and cannot be undone by changing a credential.
    "SPECIAL_CATEGORY": 7.5,
    "PRIVATE_MESSAGE": 6.0,
    "INCOME":         4.5,
    "EMPLOYER":       2.5,
    "VEHICLE":        4.0,
}

# Source credibility multipliers
SOURCE_CREDIBILITY = {
    "hibp_verified":      1.0,
    # An open-web hit that was confirmed by fetching the page and finding the
    # identifier in it verbatim is directly observed, not inferred — stronger
    # evidence than a broker's probabilistic claim that it holds a record.
    "open_web_verified":  0.95,
    # A named infection in a specialist infostealer corpus, with the machine and
    # the date of compromise attached. This is the most reliable signal the
    # product handles, and the most serious: the credentials are current rather
    # than historic.
    "infostealer":        1.0,
    "dark_web_paste":     0.85,
    "data_broker":        0.90,
    "combo_list":         0.70,
    "public_search":      0.60,
    "synthetic":          0.30,
}


@dataclass
class RiskAssessment:
    """Complete privacy risk assessment for a user."""
    overall_score: float          # 0–100
    risk_level: str               # "Critical", "High", "Medium", "Low", "Minimal"
    risk_color: str               # CSS color
    breakdown: dict               # Detailed scoring breakdown
    recommendations: list[str]    # Prioritized action items
    exposures_by_severity: dict   # grouped exposures

    def to_dict(self):
        return {
            "overall_score": round(self.overall_score, 1),
            "risk_level": self.risk_level,
            "risk_color": self.risk_color,
            "breakdown": self.breakdown,
            "recommendations": self.recommendations,
            "exposures_by_severity": self.exposures_by_severity,
        }


class RiskCalculator:
    """
    Dynamic Privacy Risk Scoring Engine.

    Combines data sensitivity, source credibility, recency, and breadth of
    exposure into a single 0–100 risk score with actionable recommendations.
    """

    def calculate(
        self,
        exposures: list[dict],
        broker_matches: int = 0,
        total_brokers_checked: int = 0,
    ) -> RiskAssessment:
        """
        Calculate overall privacy risk score.

        Args:
            exposures: list of dicts, each with:
                - "entity_type": str (e.g., "AADHAAR", "EMAIL")
                - "source_type": str (e.g., "hibp_verified", "dark_web_paste")
                - "date_found": ISO date string or None
                - "value": str (the exposed value)
            broker_matches: number of data brokers likely holding user data
            total_brokers_checked: total brokers scanned

        Returns:
            RiskAssessment with score, level, breakdown, and recommendations.
        """
        if not exposures and broker_matches == 0:
            return RiskAssessment(
                overall_score=0.0,
                risk_level="Minimal",
                risk_color="#10b981",
                breakdown={"data_sensitivity": 0, "source_risk": 0, "recency_risk": 0, "broker_risk": 0},
                recommendations=["Your digital footprint appears clean. Continue monitoring periodically."],
                exposures_by_severity={},
            )

        # ── Exposure pressure ──
        # Each exposure contributes sensitivity x source-credibility x recency.
        # The previous model summed these into components capped at 40/25/20/15
        # with divisors so small that two of them pinned at ~12 exposures: past
        # that point the score stopped responding, so removing data barely moved
        # it. Since the entire product promise is "your score falls when your
        # data comes down", the components now saturate smoothly (exponential
        # diminishing returns) instead of clipping. Every removal moves the number.
        now = datetime.now()
        pressure = 0.0
        entity_counts: dict = {}
        source_counts: dict = {}
        sources_seen: set = set()

        for exp in exposures:
            etype = exp.get("entity_type", "UNKNOWN")
            stype = exp.get("source_type", "synthetic")
            weight = SENSITIVITY_WEIGHTS.get(etype, 1.0)
            cred = SOURCE_CREDIBILITY.get(stype, 0.5)
            recency = self._recency_factor(exp.get("date_found"), now)

            pressure += weight * cred * recency
            entity_counts[etype] = entity_counts.get(etype, 0) + 1
            source_counts[stype] = source_counts.get(stype, 0) + 1
            # str(... or "") rather than .get("value", ""): a key that is PRESENT
            # and None returns None, and None[:24] is a TypeError that takes the
            # whole scan down. Exposure dicts are assembled by several callers and
            # a missing value is a normal shape, not an error worth crashing on.
            sources_seen.add(f"{stype}:{str(exp.get('value') or '')[:24]}")

        # Core: what is exposed, how credible the source, how fresh (0-75).
        core_score = 75.0 * (1.0 - math.exp(-pressure / 15.0))

        # Broker coverage: commercial resale is a distinct harm (0-15).
        broker_score = 15.0 * (1.0 - math.exp(-broker_matches / 3.0)) if broker_matches else 0.0

        # Breadth: the same datum in many places is harder to contain (0-10).
        breadth_score = 10.0 * (1.0 - math.exp(-len(sources_seen) / 4.0)) if sources_seen else 0.0

        overall = min(100.0, max(0.0, core_score + broker_score + breadth_score))

        # Keep the published breakdown shape stable for the UI.
        sensitivity_score = core_score * 0.60
        source_score = core_score * 0.25
        recency_score = core_score * 0.15

        # ── Determine risk level ──
        if overall >= 80:
            risk_level = "Critical"
            risk_color = "#ef4444"
        elif overall >= 60:
            risk_level = "High"
            risk_color = "#f97316"
        elif overall >= 40:
            risk_level = "Medium"
            risk_color = "#eab308"
        elif overall >= 20:
            risk_level = "Low"
            risk_color = "#22c55e"
        else:
            risk_level = "Minimal"
            risk_color = "#10b981"

        # ── Group exposures by severity ──
        exposures_by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for exp in exposures:
            etype = exp.get("entity_type", "UNKNOWN")
            weight = SENSITIVITY_WEIGHTS.get(etype, 1.0)
            if weight >= 8:
                exposures_by_severity["critical"].append(exp)
            elif weight >= 6:
                exposures_by_severity["high"].append(exp)
            elif weight >= 3:
                exposures_by_severity["medium"].append(exp)
            else:
                exposures_by_severity["low"].append(exp)

        # ── Generate recommendations ──
        recommendations = self._generate_recommendations(
            entity_counts, source_counts, broker_matches, overall
        )

        breakdown = {
            "data_sensitivity": round(sensitivity_score, 1),
            "source_risk": round(source_score, 1),
            "recency_risk": round(recency_score, 1),
            "broker_risk": round(broker_score, 1),
            "entity_counts": entity_counts,
            "source_counts": source_counts,
        }

        return RiskAssessment(
            overall_score=overall,
            risk_level=risk_level,
            risk_color=risk_color,
            breakdown=breakdown,
            recommendations=recommendations,
            exposures_by_severity=exposures_by_severity,
        )

    @staticmethod
    def _recency_factor(date_str, now) -> float:
        """Fresh exposures are more dangerous than decade-old ones."""
        if not date_str:
            return 0.5
        try:
            found = datetime.fromisoformat(str(date_str).replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            return 0.5
        days = (now - found).days
        if days <= 7:
            return 1.0
        if days <= 30:
            return 0.8
        if days <= 90:
            return 0.6
        if days <= 365:
            return 0.3
        return 0.15

    def _generate_recommendations(
        self, entity_counts: dict, source_counts: dict, broker_matches: int, score: float
    ) -> list[str]:
        """Generate prioritized, actionable recommendations."""
        recs = []

        if "AADHAAR" in entity_counts:
            recs.append("🔴 CRITICAL: Your Aadhaar number has been exposed. Lock your Aadhaar biometrics immediately at mAadhaar app or https://uidai.gov.in and file a complaint with CERT-In.")
        if "PAN" in entity_counts:
            recs.append("🔴 CRITICAL: Your PAN card is exposed. Monitor your Income Tax account at https://incometax.gov.in for unauthorized filings. Consider PAN-Aadhaar unlinking if fraudulent.")
        if "CREDIT_CARD" in entity_counts:
            recs.append("🔴 URGENT: Credit card numbers detected in breach data. Contact your bank immediately to block and reissue affected cards.")
        if "BANK_ACCOUNT" in entity_counts:
            recs.append("🔴 URGENT: Bank account numbers exposed. Alert your bank's fraud department and enable enhanced transaction alerts.")
        if "EMAIL" in entity_counts:
            recs.append("🟡 HIGH: Your email address appears in breach databases. Change passwords on all accounts using this email. Enable 2FA everywhere.")
        if "PHONE_IN" in entity_counts:
            recs.append("🟡 HIGH: Your phone number is exposed. Be vigilant against phishing calls/SMS. Consider enabling DND and call screening.")
        if broker_matches > 0:
            # "Your data appears on N sites" was an assertion of fact, and it was
            # not one. broker_scanner queries no broker — it cannot, they are behind
            # CAPTCHAs — it scores each broker's CATEGORY against which identity
            # fields the user supplied. Supplying a name alone yields 432 "high
            # risk matches" for any name at all, including one no person has, so
            # the sentence told every user their data had been found in 432 places
            # that were never asked. The count is a scope estimate and now says so.
            recs.append(f"🟠 MEDIUM: {broker_matches} data broker categories are likely to hold "
                        f"a profile on someone with your details — an estimate from each broker's "
                        f"category and the identifiers you supplied, not a confirmed hit: these "
                        f"sites were not queried. Use the Legal Remediation Studio to send "
                        f"deletion requests to the ones that matter.")
        if score >= 60:
            recs.append("📋 File a formal data erasure request under DPDP Act 2023 (Section 12) with each data holder using the one-click Legal Notice Generator.")
        if score >= 40:
            recs.append("🔒 Enable a credit freeze with CIBIL/Equifax/Experian India to prevent unauthorized credit applications.")

        if not recs:
            recs.append("✅ No significant exposures detected. Continue periodic monitoring.")

        return recs
