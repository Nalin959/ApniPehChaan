"""
notice_generator.py — Statutory Legal Notice Generator.

Generates legally-grounded data erasure / right-to-be-forgotten notices
citing the correct sections of:
  • India DPDP Act 2023 (Sections 12 & 13)
  • EU GDPR (Article 17)
  • US CCPA/CPRA (Cal. Civ. Code § 1798.105)
"""

import os
import hashlib
from datetime import datetime, timedelta
from string import Template


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates")

# Jurisdiction configurations
JURISDICTIONS = {
    "dpdp": {
        "name": "India — Digital Personal Data Protection Act, 2023",
        "short": "DPDP Act 2023",
        "template_file": "dpdp_erasure_notice.txt",
        "statute": "Sections 12 & 13, DPDP Act 2023",
        "response_deadline_days": 30,
        "escalation_body": "Data Protection Board of India (DPBI)",
        "escalation_section": "Section 27, DPDP Act 2023",
    },
    "gdpr": {
        "name": "European Union — General Data Protection Regulation",
        "short": "GDPR",
        "template_file": "gdpr_art17_notice.txt",
        "statute": "Article 17, Regulation (EU) 2016/679",
        "response_deadline_days": 30,
        "escalation_body": "Relevant EU Supervisory Authority",
        "escalation_section": "Article 77 GDPR",
    },
    "ccpa": {
        "name": "California — Consumer Privacy Act (CCPA/CPRA)",
        "short": "CCPA/CPRA",
        "template_file": "ccpa_deletion_notice.txt",
        "statute": "Cal. Civ. Code §§ 1798.105, 1798.106",
        "response_deadline_days": 45,
        "escalation_body": "California Privacy Protection Agency (CPPA)",
        "escalation_section": "Cal. Civ. Code § 1798.199.40",
    },
}


class NoticeGenerator:
    """Generator for statutory data erasure legal notices."""

    def __init__(self):
        self._templates: dict[str, str] = {}
        self._load_templates()

    def _load_templates(self):
        """Load all template files."""
        for key, config in JURISDICTIONS.items():
            template_path = os.path.join(TEMPLATES_DIR, config["template_file"])
            try:
                with open(template_path, "r") as f:
                    self._templates[key] = f.read()
            except FileNotFoundError:
                self._templates[key] = f"[Template not found: {template_path}]"

    def generate(
        self,
        jurisdiction: str,
        user_name: str,
        user_email: str,
        user_phone: str = "",
        additional_ids: str = "",
        company_name: str = "",
        company_address: str = "",
        detected_pii_summary: str = "",
    ) -> dict:
        """
        Generate a statutory legal notice.

        Args:
            jurisdiction: "dpdp", "gdpr", or "ccpa"
            user_name: Data principal's name
            user_email: Data principal's email
            user_phone: Data principal's phone
            additional_ids: Other identifiers (PAN, Aadhaar masked, etc.)
            company_name: Target company / data fiduciary
            company_address: Company address
            detected_pii_summary: Summary of detected PII exposure

        Returns:
            Dict with generated notice, metadata, and receipt hash.
        """
        if jurisdiction not in JURISDICTIONS:
            return {"status": "error", "message": f"Unknown jurisdiction: {jurisdiction}"}

        config = JURISDICTIONS[jurisdiction]
        template_text = self._templates.get(jurisdiction, "")

        now = datetime.now()
        reference_id = f"SP-{jurisdiction.upper()}-{now.strftime('%Y%m%d')}-{hashlib.sha256(f'{user_email}{now.isoformat()}'.encode()).hexdigest()[:8].upper()}"

        deadline = now + timedelta(days=config["response_deadline_days"])

        # Generate receipt hash
        receipt_content = f"{reference_id}|{user_email}|{company_name}|{now.isoformat()}"
        receipt_hash = hashlib.sha256(receipt_content.encode()).hexdigest()

        # Fill template
        notice_text = template_text.replace("{{date}}", now.strftime("%d %B %Y"))
        notice_text = notice_text.replace("{{reference_id}}", reference_id)
        notice_text = notice_text.replace("{{user_name}}", user_name or "[Your Full Name]")
        notice_text = notice_text.replace("{{user_email}}", user_email or "[Your Email]")
        notice_text = notice_text.replace("{{user_phone}}", user_phone or "[Your Phone]")
        notice_text = notice_text.replace("{{additional_ids}}", additional_ids or "N/A")
        notice_text = notice_text.replace("{{company_name}}", company_name or "[Company Name]")
        notice_text = notice_text.replace("{{company_address}}", company_address or "[Company Address]")
        notice_text = notice_text.replace("{{detected_pii_summary}}", detected_pii_summary or "[Details of personal data detected in your systems]")
        notice_text = notice_text.replace("{{receipt_hash}}", receipt_hash)

        return {
            "status": "generated",
            "reference_id": reference_id,
            "jurisdiction": jurisdiction,
            "jurisdiction_name": config["name"],
            "jurisdiction_short": config["short"],
            "statute_cited": config["statute"],
            "notice_text": notice_text,
            "generated_at": now.isoformat(),
            "response_deadline": deadline.isoformat(),
            "response_deadline_days": config["response_deadline_days"],
            "escalation_body": config["escalation_body"],
            "escalation_section": config["escalation_section"],
            "receipt_hash": receipt_hash,
            "recipient": {
                "company_name": company_name,
                "company_address": company_address,
            },
            "sender": {
                "name": user_name,
                "email": user_email,
                "phone": user_phone,
            },
        }

    def get_jurisdictions(self) -> list[dict]:
        """Return list of available jurisdictions."""
        return [
            {
                "key": key,
                "name": config["name"],
                "short": config["short"],
                "statute": config["statute"],
                "deadline_days": config["response_deadline_days"],
            }
            for key, config in JURISDICTIONS.items()
        ]
