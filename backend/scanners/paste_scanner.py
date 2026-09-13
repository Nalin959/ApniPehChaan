"""
paste_scanner.py — Dark Web Paste & Breach Dump Scanner.

Scans the paste corpus for leaked PII matching a user's identity.
Uses the PII recognizer to extract entities, then the identity resolver
to match them against the user's profile.

ATTRIBUTION RULE
----------------
A paste is only reported when it carries an identifier UNIQUE to this person —
their email address, their mobile subscriber number, their Aadhaar, PAN or UPI
ID. A legal name is never sufficient and never triggers a match on its own.

That is not a style preference. A paste dump is a list of strangers, and
"Sharma" is a surname shared by tens of millions of people, so a substring hit
on a name component attributes a stranger's leaked Aadhaar number to the user
and tells them their national ID is on a dark-web forum. A three-character name
part ("raj", "ann", "ali") is worse still: it matches inside unrelated words.
A name is recorded here as corroboration next to an identifier hit, never as
the reason for one.

The same rule governs which ENTITIES are attributed. A combo list or a CSV
scrape holds one record per line for hundreds of different people; finding the
user on one line does not make the other 200 lines theirs. So entities are
attributed from the record that actually carries the user's identifier, not
from the whole file.
"""

import json
import os
import re
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

    # ── identifier normalisation ─────────────────────────────────────────────
    # Everything below compares IDENTIFIERS, never names. Each normaliser
    # returns "" when the value is not usable as a unique identifier, and ""
    # can never match anything, so an empty or malformed profile field cannot
    # produce a hit.

    @staticmethod
    def _digits(value) -> str:
        return re.sub(r"\D", "", str(value or ""))

    @classmethod
    def _subscriber(cls, value) -> str:
        """The last ten digits of an Indian mobile — what identifies it however
        it was written (+91 / 91 / 0 / bare). Fewer than ten digits is not a
        phone number and is refused: a three-digit fragment must never be able
        to attribute a leak."""
        d = cls._digits(value)
        return d[-10:] if len(d) >= 10 else ""

    @staticmethod
    def _bounded(needle: str, haystack: str, alnum: bool = True) -> bool:
        """Literal search that will not fire inside a longer token.

        Without the boundary, a 10-digit mobile matches inside a 12-digit
        account number and a PAN matches inside a hash.
        """
        if not needle:
            return False
        edge = "A-Za-z0-9" if alnum else "0-9"
        return re.search(rf"(?<![{edge}]){re.escape(needle)}(?![{edge}])",
                         haystack, re.IGNORECASE) is not None

    def _identifier_hits(self, content: str, ids: dict) -> list[str]:
        """Which of the user's UNIQUE identifiers this paste actually carries.

        An empty list means the paste is not this person's, whatever else it
        contains and whoever else it names.
        """
        lower = content.lower()
        squashed = re.sub(r"[\s\-()]", "", content)
        hits = []
        if ids["email"] and ids["email"] in lower:
            hits.append(f"Email address {ids['email']} found verbatim in content")
        # The country code is part of how the number is written, not part of
        # what identifies it, so an optional +91/91/0 is allowed to sit
        # immediately in front of the subscriber number. Without this the
        # boundary check treats the '1' of '+91' as a preceding digit and a
        # dump that records "Phone: +91 6967454652" fails to match the very
        # number it contains.
        if ids["phone"] and re.search(
                rf"(?<![0-9])(?:\+?91|0)?{re.escape(ids['phone'])}(?![0-9])", squashed):
            hits.append("Mobile subscriber number found in content")
        if ids["aadhaar"] and self._bounded(ids["aadhaar"], squashed, alnum=False):
            hits.append("Aadhaar number found in content")
        if ids["pan"] and self._bounded(ids["pan"], content):
            hits.append(f"PAN {ids['pan']} found in content")
        if ids["upi"] and ids["upi"] in lower:
            hits.append(f"UPI ID {ids['upi']} found in content")
        return hits

    def _attributable_text(self, content: str, ids: dict) -> str:
        """The part of the paste that is actually about this person.

        A combo list or a CSV scrape is one record per line for hundreds of
        different people. Returning every entity in such a file would hand the
        user two hundred strangers' Aadhaar numbers as their own exposure, so
        when a paste plainly holds many subjects the attribution is narrowed to
        the line(s) carrying the user's identifier.

        A single-subject record — a SQL INSERT, a doxx block, a breach
        fragment — spreads one person's fields across several lines, so line
        scoping would throw away the Aadhaar that sits on the next line. Those
        are attributed whole. "Single-subject" is decided by evidence, not by
        the paste's self-declared type: at most one distinct email address and
        at most one distinct mobile number in the entire file.
        """
        entities = self._recognizer.recognize(content)
        emails = {e.value.lower() for e in entities if e.entity_type == "EMAIL"}
        phones = {self._subscriber(e.value) for e in entities
                  if e.entity_type in ("PHONE_IN", "PHONE_INTL")}
        phones.discard("")
        if len(emails) <= 1 and len(phones) <= 1:
            return content
        return "\n".join(ln for ln in content.splitlines()
                          if self._identifier_hits(ln, ids))

    def scan(self, user_profile: dict) -> dict:
        """
        Scan paste corpus for leaks matching the user's identity.

        Args:
            user_profile: dict with keys like "name", "email", "phone", "aadhaar", "pan"

        Returns:
            Dict with matched leaks, extracted PII, and identity resolution results.
        """
        self._load()

        ids = {
            "email": (user_profile.get("email") or "").strip().lower(),
            "phone": self._subscriber(user_profile.get("phone")),
            "aadhaar": self._digits(user_profile.get("aadhaar")),
            "pan": re.sub(r"\s", "", str(user_profile.get("pan") or "")).upper(),
            "upi": (user_profile.get("upi") or "").strip().lower(),
        }
        # An Aadhaar is twelve digits and a PAN is ten characters. Anything
        # shorter is a fragment, and a fragment is not unique to anyone.
        if len(ids["aadhaar"]) != 12:
            ids["aadhaar"] = ""
        if not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", ids["pan"] or ""):
            ids["pan"] = ""

        user_name = (user_profile.get("name") or "").strip().lower()
        has_identifier = any(ids.values())

        matches = []
        scan_steps = []

        for paste in self._pastes:
            content = paste.get("content", "")
            paste_id = paste.get("id", "")
            paste_type = paste.get("type", "unknown")

            # Step 1: does this paste carry an identifier unique to the user?
            # A name is NOT one and is deliberately not consulted here.
            quick_reasons = self._identifier_hits(content, ids) if has_identifier else []
            quick_match = bool(quick_reasons)

            # Step 2: If an identifier matched, run full PII extraction — but
            # only over the record that is actually this person's.
            if quick_match:
                # No `or content` fallback. If a multi-subject file matched but no
                # single line carries the identifier, the conservative answer is
                # to attribute NOTHING rather than to fall back to the whole file
                # — falling back is precisely the over-attribution being fixed.
                # The match is still reported; `matched_identifiers` is its evidence.
                scope = self._attributable_text(content, ids)
                entities = self._recognizer.recognize(scope)
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

                # A name agreeing alongside the identifier is corroboration and
                # is reported as such. It is recorded only AFTER the identifier
                # has already established the match, so it can never create one.
                corroboration = []
                scope_lower = scope.lower()
                for part in user_name.split():
                    if len(part) >= 3 and part in scope_lower:
                        corroboration.append(
                            f"Name component '{part}' also appears in the matched record "
                            f"(corroboration only — a name identifies no one on its own)")

                # Determine severity
                has_financial = any(e.entity_type in ("AADHAAR", "PAN", "CREDIT_CARD", "BANK_ACCOUNT") for e in entities)
                severity = "critical" if has_financial else ("high" if resolution.is_match else "medium")

                matches.append({
                    "paste_id": paste_id,
                    "paste_type": paste_type,
                    "source": paste.get("source", ""),
                    "date_found": paste.get("date_found", ""),
                    "severity": severity,
                    "quick_match_reasons": quick_reasons + corroboration,
                    "matched_identifiers": quick_reasons,
                    "attribution_scope": "whole_paste" if scope == content else "matched_record_only",
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
            "identifiers_searched": [k for k, v in ids.items() if v],
            "scan_timestamp": datetime.now().isoformat(),
        }
        if not has_identifier:
            stats["note"] = (
                "No unique identifier (email, phone, Aadhaar, PAN or UPI) was supplied, so "
                "nothing could be attributed. A name alone is never enough to claim a paste "
                "is yours.")

        return {
            "status": "complete",
            "matches": matches,
            "scan_steps": scan_steps,
            "stats": stats,
        }

    def get_paste_count(self) -> int:
        self._load()
        return len(self._pastes)
