"""
recognizer.py — Hybrid PII Recognition Engine for SovereignPrivacy AI.

Implements multi-pattern PII detection combining:
  • Regex-based pattern matching for structured identifiers
  • Luhn algorithm validation for credit card numbers
  • Verhoeff algorithm validation for Aadhaar numbers
  • Contextual validation to reduce false positives

Supports both Indian-specific and international PII types.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PIIEntity:
    """A detected PII entity in text."""
    entity_type: str
    value: str
    original_match: str
    start: int
    end: int
    confidence: float = 1.0
    validation_method: str = "regex"

    def to_dict(self):
        return {
            "entity_type": self.entity_type,
            "value": self.value,
            "original_match": self.original_match,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "validation_method": self.validation_method,
        }


# ─── Verhoeff Algorithm for Aadhaar Validation ───────────────────────────────

_VERHOEFF_TABLE_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_TABLE_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

_VERHOEFF_TABLE_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_validate(number: str) -> bool:
    """Validate a number string using the Verhoeff checksum algorithm."""
    try:
        digits = [int(d) for d in str(number)]
    except (ValueError, TypeError):
        return False
    c = 0
    for i, digit in enumerate(reversed(digits)):
        c = _VERHOEFF_TABLE_D[c][_VERHOEFF_TABLE_P[i % 8][digit]]
    return c == 0


def luhn_validate(number: str) -> bool:
    """Validate a number string using the Luhn algorithm (credit cards)."""
    try:
        digits = [int(d) for d in str(number)]
    except (ValueError, TypeError):
        return False
    if len(digits) < 13:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# ─── PII Pattern Definitions ────────────────────────────────────────────────

# Each pattern: (compiled_regex, entity_type, validator_fn_or_None, confidence)
_PII_PATTERNS = []


def _compile_patterns():
    """Compile all PII detection patterns."""
    global _PII_PATTERNS
    if _PII_PATTERNS:
        return

    patterns = [
        # ── Indian Aadhaar Number (12 digits, starts with 2-9) ──
        # Formats: 2345 6789 0123, 234567890123
        (
            r'\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b',
            "AADHAAR",
            lambda m: verhoeff_validate(m.group(1) + m.group(2) + m.group(3)),
            0.85,
            lambda m: m.group(1) + m.group(2) + m.group(3),
        ),

        # ── Indian PAN Card (AAAAA9999A) ──
        (
            r'\b([A-Z]{3}[PCHABFTGJL][A-Z]\d{4}[A-Z])\b',
            "PAN",
            None,
            0.95,
            lambda m: m.group(1),
        ),

        # ── Indian Voter ID / EPIC ──
        (
            r'\b([A-Z]{2,3}/\d{2}/\d{3}/\d{5,6})\b',
            "VOTER_ID",
            None,
            0.80,
            lambda m: m.group(1),
        ),

        # ── IFSC Code (4 letter bank code + 0 + 5-digit branch) ──
        (
            r'\b([A-Z]{4}0\d{6})\b',
            "IFSC",
            None,
            0.90,
            lambda m: m.group(1),
        ),

        # ── UPI ID ──
        (
            r'\b([\w.\-]+@(?:okaxis|ybl|paytm|ibl|upi|sbi|icici|hdfcbank|axisbank|kotak|indus|federal|apl|boi|citi|dlb|fbl|idbi|kbl|kvb|obc|pnb|rbl|sc|ubi|united|vijb|okicici|okhdfcbank))\b',
            "UPI",
            None,
            0.90,
            lambda m: m.group(1),
        ),

        # ── Email Address ──
        (
            r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b',
            "EMAIL",
            None,
            0.95,
            lambda m: m.group(1),
        ),

        # ── Indian Phone Number (various formats) ──
        # +91-XXXXXXXXXX, +91 XXXXX XXXXX, 0XXXXXXXXXX, etc.
        (
            r'(?:\+91[\s\-]?|91[\s\-]?|0)([6-9]\d{4}[\s\-]?\d{5})\b',
            "PHONE_IN",
            None,
            0.90,
            lambda m: re.sub(r'[\s\-]', '', m.group(1)),
        ),

        # Bare Indian mobile: 10 digits starting with 6-9
        (
            r'(?<![0-9\+])([6-9]\d{9})(?![0-9])',
            "PHONE_IN",
            None,
            0.70,
            lambda m: m.group(1),
        ),

        # ── International Phone ──
        (
            r'\+1[\s\-]?(\d{3})[\s\-]?(\d{3})[\s\-]?(\d{4})\b',
            "PHONE_INTL",
            None,
            0.85,
            lambda m: m.group(1) + m.group(2) + m.group(3),
        ),

        # ── Credit Card Number (13-19 digits, optionally spaced/dashed) ──
        (
            r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{1,7})\b',
            "CREDIT_CARD",
            lambda m: luhn_validate(re.sub(r'[\s\-]', '', m.group(1))),
            0.80,
            lambda m: re.sub(r'[\s\-]', '', m.group(1)),
        ),

        # ── IPv4 Address ──
        (
            r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
            "IP_ADDRESS",
            lambda m: all(0 <= int(o) <= 255 for o in m.group(1).split('.')),
            0.85,
            lambda m: m.group(1),
        ),

        # ── Bank Account Number (10-18 digit number, context-dependent) ──
        (
            r'(?:account|acct|a/c)[\s:#]*(\d{10,18})\b',
            "BANK_ACCOUNT",
            None,
            0.75,
            lambda m: m.group(1),
        ),

        # ── Indian PIN Code (6 digits, context-dependent) ──
        (
            r'(?:pin\s*code|pincode|zip)[\s:#]*(\d{6})\b',
            "PIN_CODE",
            None,
            0.70,
            lambda m: m.group(1),
        ),
    ]

    _PII_PATTERNS = [
        (re.compile(pattern, re.IGNORECASE if etype in ("BANK_ACCOUNT", "PIN_CODE") else 0), etype, validator, conf, extractor)
        for pattern, etype, validator, conf, extractor in patterns
    ]


class PIIRecognizer:
    """
    Hybrid PII Recognition Engine.

    Detects personally identifiable information in unstructured text
    using regex patterns, algorithmic validators (Luhn, Verhoeff),
    and contextual heuristics.
    """

    def __init__(self):
        _compile_patterns()
        self._seen_positions: set = set()

    def recognize(self, text: str) -> list[PIIEntity]:
        """
        Scan text and return all detected PII entities.

        Returns a deduplicated list of PIIEntity objects, sorted by position.
        """
        entities = []
        self._seen_positions = set()

        for regex, entity_type, validator, base_confidence, extractor in _PII_PATTERNS:
            for match in regex.finditer(text):
                # Deduplicate overlapping matches
                pos_key = (match.start(), match.end())
                if pos_key in self._seen_positions:
                    continue

                # Run validator if present
                confidence = base_confidence
                validation_method = "regex"
                if validator is not None:
                    try:
                        if not validator(match):
                            # For Aadhaar, still accept but lower confidence
                            if entity_type == "AADHAAR":
                                confidence *= 0.6
                                validation_method = "regex_only"
                            else:
                                continue
                        else:
                            confidence = min(confidence * 1.15, 1.0)
                            validation_method = "regex+algorithm"
                    except Exception:
                        continue

                # Extract the normalized value
                try:
                    value = extractor(match)
                except Exception:
                    value = match.group(0)

                entity = PIIEntity(
                    entity_type=entity_type,
                    value=value,
                    original_match=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    confidence=round(confidence, 3),
                    validation_method=validation_method,
                )
                entities.append(entity)
                self._seen_positions.add(pos_key)

        # Sort by position, then deduplicate by value+type
        entities.sort(key=lambda e: (e.start, -e.confidence))

        # Remove duplicates where the same value was matched by multiple patterns
        seen_values = set()
        deduped = []
        for entity in entities:
            key = (entity.entity_type, entity.value)
            if key not in seen_values:
                seen_values.add(key)
                deduped.append(entity)

        return deduped

    def recognize_dict(self, text: str) -> list[dict]:
        """Return entities as a list of dictionaries."""
        return [e.to_dict() for e in self.recognize(text)]

    def get_summary(self, entities: list[PIIEntity]) -> dict:
        """
        Summarize detected entities grouped by type.

        Returns a dict like:
        {
            "EMAIL": ["a@b.com", ...],
            "PAN": ["ABCDE1234F", ...],
            ...
            "total_count": 5,
            "types_found": ["EMAIL", "PAN"],
        }
        """
        summary: dict = {}
        for e in entities:
            if e.entity_type not in summary:
                summary[e.entity_type] = []
            summary[e.entity_type].append(e.value)

        summary["total_count"] = len(entities)
        summary["types_found"] = list(set(e.entity_type for e in entities))
        return summary
