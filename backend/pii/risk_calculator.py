"""
risk_calculator.py — Dynamic Privacy Risk Scoring Engine.

Computes a composite privacy vulnerability score (0–100) based on:
  • Volume of exposed data points
  • Sensitivity weighting of each data type
  • Source credibility (verified breach vs paste)
  • Recency of exposure
  • Data broker coverage
"""

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
}

# Source credibility multipliers
SOURCE_CREDIBILITY = {
    "hibp_verified":      1.0,
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

        # ── Component 1: Data Sensitivity Score (0–40 points) ──
        sensitivity_total = 0
        entity_counts = {}
        for exp in exposures:
            etype = exp.get("entity_type", "UNKNOWN")
            weight = SENSITIVITY_WEIGHTS.get(etype, 1.0)
            sensitivity_total += weight
            entity_counts[etype] = entity_counts.get(etype, 0) + 1

        # Normalize: 40 points for score >= 25 raw sensitivity
        # (3 critical items like Aadhaar+PAN+Card = ~27.5, should max out)
        sensitivity_score = min(40, (sensitivity_total / 25) * 40)

        # ── Component 2: Source Credibility Risk (0–25 points) ──
        source_total = 0
        source_counts = {}
        for exp in exposures:
            stype = exp.get("source_type", "synthetic")
            cred = SOURCE_CREDIBILITY.get(stype, 0.5)
            source_total += cred
            source_counts[stype] = source_counts.get(stype, 0) + 1

        source_score = min(25, (source_total / 10) * 25)

        # ── Component 3: Recency Risk (0–20 points) ──
        recency_scores = []
        now = datetime.now()
        for exp in exposures:
            date_str = exp.get("date_found")
            if date_str:
                try:
                    found_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    days_ago = (now - found_date).days
                    if days_ago <= 7:
                        recency_scores.append(1.0)
                    elif days_ago <= 30:
                        recency_scores.append(0.8)
                    elif days_ago <= 90:
                        recency_scores.append(0.6)
                    elif days_ago <= 365:
                        recency_scores.append(0.3)
                    else:
                        recency_scores.append(0.1)
                except (ValueError, TypeError):
                    recency_scores.append(0.5)
            else:
                recency_scores.append(0.5)

        avg_recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0
        recency_score = avg_recency * 20

        # ── Component 4: Data Broker Exposure (0–15 points) ──
        if total_brokers_checked > 0:
            broker_ratio = broker_matches / total_brokers_checked
            broker_score = min(15, broker_ratio * 150)  # 10% match = 15 points
        else:
            broker_score = 0

        # ── Compute overall score ──
        overall = sensitivity_score + source_score + recency_score + broker_score
        overall = min(100, max(0, overall))

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
            recs.append(f"🟠 MEDIUM: Your data appears on {broker_matches} data broker sites. Use the Legal Remediation Studio to send automated deletion requests.")
        if score >= 60:
            recs.append("📋 File a formal data erasure request under DPDP Act 2023 (Section 12) with each data holder using the one-click Legal Notice Generator.")
        if score >= 40:
            recs.append("🔒 Enable a credit freeze with CIBIL/Equifax/Experian India to prevent unauthorized credit applications.")

        if not recs:
            recs.append("✅ No significant exposures detected. Continue periodic monitoring.")

        return recs
