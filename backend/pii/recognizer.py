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
        # A leading '+' marks a telephone country code, never a national ID:
        # '+91' followed by a 10-digit mobile is 12 digits that clear Verhoeff
        # about 10% of the time, so without this guard one Indian mobile in ten
        # is reported as somebody's Aadhaar number.
        (
            r'(?<![+\d])\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b',
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
            r'(?<![0-9])(?:\+91[\s\-]?|91[\s\-]?|0)([6-9]\d{4}[\s\-]?\d{5})(?![0-9])',
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

        Candidates from every pattern are gathered first, then overlaps are
        resolved by evidence strength rather than by pattern declaration order.
        This matters: the Aadhaar pattern matches the first 12 digits of a
        16-digit payment card, so a naive first-wins scan reports a card number
        as somebody's national ID. Preferring checksum-validated, longer matches
        resolves that correctly and in general.
        """
        candidates: list[tuple[int, int, int, PIIEntity]] = []

        for regex, entity_type, validator, base_confidence, extractor in _PII_PATTERNS:
            for match in regex.finditer(text):
                confidence = base_confidence
                validation_method = "regex"
                algorithmically_valid = 0

                if validator is not None:
                    try:
                        if not validator(match):
                            # A failed checksum is disqualifying. Aadhaar, card and
                            # account numbers all carry check digits precisely so a
                            # number-shaped string can be rejected; honouring that is
                            # the entire value of the algorithm.
                            continue
                        confidence = min(confidence * 1.15, 1.0)
                        validation_method = "regex+algorithm"
                        algorithmically_valid = 1
                    except Exception:
                        continue

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
                span = match.end() - match.start()
                candidates.append((algorithmically_valid, span, int(confidence * 1000), entity))

        # Strongest evidence wins its span: the longer match first, then
        # checksum-validated, then the more confident one.
        #
        # Span has to outrank the checksum flag. Candidates whose validator
        # failed were dropped above, so this flag only separates "carries a
        # check digit" from "carries none" — and a 12-digit checksum clears by
        # chance once in ten. Ranking the flag first let a chance Verhoeff hit
        # inside a longer phone number outrank the phone match that explained
        # the whole string.
        candidates.sort(key=lambda c: (-c[1], -c[0], -c[2], c[3].start))

        accepted: list[PIIEntity] = []
        claimed: list[tuple[int, int]] = []
        seen_values: set = set()

        for _, _, _, entity in candidates:
            if any(entity.start < c_end and c_start < entity.end for c_start, c_end in claimed):
                continue  # overlaps a span already explained by stronger evidence
            key = (entity.entity_type, entity.value)
            if key in seen_values:
                continue
            seen_values.add(key)
            claimed.append((entity.start, entity.end))
            accepted.append(entity)

        accepted.sort(key=lambda e: e.start)
        return accepted

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
