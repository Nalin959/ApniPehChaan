"""
resolver.py — Probabilistic Identity Resolution Engine.

Determines whether detected PII records belong to the same real-world
individual using fuzzy string matching (Jaro-Winkler similarity),
token set overlap, and multi-field confidence scoring.
"""

import re
from dataclasses import dataclass


def _jaro_similarity(s1: str, s2: str) -> float:
    """Compute the Jaro similarity between two strings."""
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3


def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1) -> float:
    """
    Compute the Jaro-Winkler similarity between two strings.

    The Winkler modification gives more weight to strings that share
    a common prefix, which is useful for names.
    """
    jaro = _jaro_similarity(s1, s2)
    # Common prefix (up to 4 chars)
    prefix_len = 0
    for i in range(min(len(s1), len(s2), 4)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break
    return jaro + prefix_len * p * (1 - jaro)


def token_set_ratio(s1: str, s2: str) -> float:
    """
    Compute the token set ratio between two strings.

    Tokenizes both strings, computes intersection over union of tokens.
    More robust than raw string similarity for names in different order.
    """
    tokens1 = set(s1.lower().split())
    tokens2 = set(s2.lower().split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)


@dataclass
class IdentityMatch:
    """Result of identity resolution between user profile and a detected record."""
    overall_score: float  # 0.0 to 1.0
    field_scores: dict  # field -> similarity score
    matched_fields: list[str]
    unmatched_fields: list[str]
    is_match: bool
    confidence_label: str  # "definite", "likely", "possible", "unlikely"
    raw_score: float = 0.0       # similarity before corroboration is applied
    corroboration: float = 1.0   # discount for thin evidence (see _corroboration)
    evidence_note: str = ""

    def to_dict(self):
        return {
            "overall_score": round(self.overall_score, 4),
            "raw_score": round(self.raw_score, 4),
            "corroboration": round(self.corroboration, 3),
            "evidence_note": self.evidence_note,
            "field_scores": {k: round(v, 4) for k, v in self.field_scores.items()},
            "matched_fields": self.matched_fields,
            "unmatched_fields": self.unmatched_fields,
            "is_match": self.is_match,
            "confidence_label": self.confidence_label,
        }


class IdentityResolver:
    """
    Probabilistic Identity Resolution Engine.

    Compares a user's identity profile against a detected PII record
    and produces a confidence score for whether they refer to the same person.
    """

    # Field weights for computing overall match score
    FIELD_WEIGHTS = {
        "email": 0.25,
        "phone": 0.20,
        "name": 0.15,
        "aadhaar": 0.15,
        "pan": 0.10,
        "address": 0.05,
        "ip_address": 0.05,
        "upi": 0.05,
        "city": 0.05,
    }

    # Identifiers unique enough to identify a person on their own.
    STRONG_IDENTIFIERS = {"email", "phone", "aadhaar", "pan", "upi"}

    # Thresholds for field-level match
    EXACT_FIELDS = {"email", "phone", "aadhaar", "pan", "upi", "ip_address"}
    FUZZY_FIELDS = {"name", "address", "city"}
    FUZZY_THRESHOLD = 0.80

    def resolve(self, user_profile: dict, detected_record: dict) -> IdentityMatch:
        """
        Compare a user profile against a detected PII record.

        Args:
            user_profile: dict with keys like "name", "email", "phone", etc.
            detected_record: dict of detected PII values (same keys).

        Returns:
            IdentityMatch with detailed scoring.
        """
        field_scores = {}
        matched_fields = []
        unmatched_fields = []

        for field, weight in self.FIELD_WEIGHTS.items():
            user_val = self._normalize(field, user_profile.get(field, ""))
            detected_val = self._normalize(field, detected_record.get(field, ""))

            if not user_val or not detected_val:
                continue

            if field in self.EXACT_FIELDS:
                score = 1.0 if user_val == detected_val else 0.0
            else:
                # Fuzzy matching for names, addresses
                jw = jaro_winkler_similarity(user_val, detected_val)
                tsr = token_set_ratio(user_val, detected_val)
                score = max(jw, tsr)

            field_scores[field] = score
            if score >= self.FUZZY_THRESHOLD:
                matched_fields.append(field)
            else:
                unmatched_fields.append(field)

        # Compute weighted overall score
        total_weight = 0
        weighted_sum = 0
        for field, score in field_scores.items():
            w = self.FIELD_WEIGHTS.get(field, 0.05)
            weighted_sum += score * w
            total_weight += w

        raw_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Discount thin evidence. Averaging only over the fields that happen to be
        # present means a record containing nothing but a matching name scores 1.0
        # — and on a common name that is a stranger, not the user. Acting on that
        # would serve a legal notice about somebody else's record, so a match must
        # be corroborated by more than one non-unique identifier.
        corroboration, evidence_note = self._corroboration(matched_fields)
        overall_score = raw_score * corroboration

        # Determine confidence label
        if overall_score >= 0.90:
            label = "definite"
        elif overall_score >= 0.70:
            label = "likely"
        elif overall_score >= 0.45:
            label = "possible"
        else:
            label = "unlikely"

        return IdentityMatch(
            overall_score=overall_score,
            field_scores=field_scores,
            matched_fields=matched_fields,
            unmatched_fields=unmatched_fields,
            is_match=overall_score >= 0.45,
            confidence_label=label,
            raw_score=raw_score,
            corroboration=corroboration,
            evidence_note=evidence_note,
        )

    def _corroboration(self, matched_fields: list[str]) -> tuple[float, str]:
        """
        How much independent evidence supports this being the same person?

        A matching email or phone number is close to conclusive on its own.
        A matching name is not: it is shared by thousands of people. So a match
        resting only on non-unique fields is discounted until corroborated.
        """
        strong = [f for f in matched_fields if f in self.STRONG_IDENTIFIERS]
        weak = [f for f in matched_fields if f not in self.STRONG_IDENTIFIERS]

        if strong:
            return 1.0, f"Corroborated by unique identifier(s): {', '.join(strong)}."
        if len(weak) >= 3:
            return 0.80, f"No unique identifier; supported by {len(weak)} non-unique fields."
        if len(weak) == 2:
            return 0.65, (f"No unique identifier; only {' + '.join(weak)} agree. "
                          "Treated as possible, not confirmed.")
        if len(weak) == 1:
            return 0.40, (f"Only '{weak[0]}' matches, which is not unique to this person. "
                          "Insufficient to attribute this record.")
        return 0.0, "No fields matched." 

    def _normalize(self, field: str, value: str) -> str:
        """Normalize a field value for comparison."""
        if not value:
            return ""
        value = str(value).strip()
        if field in ("email", "upi"):
            return value.lower()
        elif field == "phone":
            # Strip country code and spaces
            return re.sub(r'[\s\-\+]', '', value).lstrip('0').lstrip('91')
        elif field in ("aadhaar", "pan"):
            return re.sub(r'\s', '', value).upper()
        elif field == "name":
            return value.lower().strip()
        elif field == "address":
            return value.lower().strip()
        return value
