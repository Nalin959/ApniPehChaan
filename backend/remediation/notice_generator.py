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

    def _draft_with_ai(
        self,
        jurisdiction: str,
        config: dict,
        user_name: str,
        user_email: str,
        user_phone: str,
        additional_ids: str,
        company_name: str,
        company_address: str,
        detected_pii_summary: str,
        reference_id: str,
        receipt_hash: str,
        deadline_str: str,
        exposure_context: str = "",
    ) -> tuple[str | None, str | None]:
        """Generate a bespoke statutory erasure notice using an LLM (Gemini/Groq)."""
        try:
            from backend.agent.openai_compat_planner import get_llm_completion
        except Exception:
            return None, None

        j_info = config["name"]
        statute = config["statute"]
        escalation_body = config["escalation_body"]
        escalation_section = config["escalation_section"]
        days = config["response_deadline_days"]

        system_msg = (
            "You are SovereignPrivacy AI's Senior Privacy Counsel. Draft a formal, rigorous, "
            "and legally binding statutory data erasure notice on behalf of the Data Principal. "
            "The notice must be authoritative, cite specific statutory sections, and assert "
            "unconditional demands for complete deletion of the individual's personal data across all "
            "production, backup, profiling, and third-party vendor databases."
        )

        user_prompt = f"""Draft an authoritative statutory data erasure demand letter:

STATUTORY CONTEXT:
- Legal Regime: {j_info}
- Governing Statute: {statute}
- Statutory Response Deadline: {days} days ({deadline_str})
- Regulatory Escalation Authority: {escalation_body} under {escalation_section}

IDENTIFICATION PARTICULARS:
- Reference ID: {reference_id}
- Cryptographic Audit Hash: {receipt_hash}
- Data Principal: {user_name or 'The Undersigned Principal'}
- Email: {user_email}
- Phone: {user_phone or 'On File'}
- Masked Government / Account Identifiers: {additional_ids or 'N/A'}

RECIPIENT (DATA FIDUCIARY / CONTROLLER):
- Entity Name: {company_name or 'Data Protection Officer / Corporate Grievance Officer'}
- Registered Address / Department: {company_address or 'Grievance Redressal Office'}

EXPOSURE EVIDENCE & DETECTED PERSONAL DATA:
- Data Classes Detected: {detected_pii_summary or 'Personal and identity records'}
- Additional Exposure Context: {exposure_context or 'Discovered through unauthorized exposure / data breach telemetry'}

MANDATORY NOTICE STRUCTURE:
1. Formal Letterhead (Date, Reference ID, Addressee, Subject line citing {statute}).
2. Formal Declaration of Identity and withdrawal of any prior consent.
3. Specific Erasure Demands (immediate permanent deletion from primary databases, third-party sub-processors, and anonymization of audit logs).
4. Cessation of all processing, marketing, profiling, and data broker syndicate dissemination.
5. Statutory Duty to Confirm: Demand written confirmation of erasure within {days} calendar days ({deadline_str}).
6. Formal Notice of Regulatory Escalation: Explicitly cite {escalation_body} ({escalation_section}) and statutory penalties for non-compliance (e.g., up to ₹250 crore under DPDP Act 2023 Schedule or €20M / 4% global turnover under GDPR Art. 83).
7. Reservation of Rights and complete formal Signature Block for {user_name or 'Data Principal'}.

Generate only the complete, ready-to-send formal legal notice in clean Markdown format. Be legally precise and concise (under 750 words). IMPORTANT: You MUST generate the complete notice all the way to the final closing signature block. Never stop mid-sentence or omit the closing signature block."""

        ai_text, model_used = get_llm_completion(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2800,
            temperature=0.15,
        )

        if ai_text:
            ai_text = ai_text.strip()
            # Ensure the closing signature block is never truncated or omitted
            lower_tail = ai_text[-350:].lower()
            has_closing = any(sig in lower_tail for sig in ["sincerely", "faithfully", "signature", "data principal", "complainant"])
            if not has_closing:
                if ai_text.rstrip().endswith("This notice"):
                    ai_text = ai_text.rstrip()[:-len("This notice")].rstrip()
                ai_text += f"\n\n#### **7. RESERVATION OF RIGHTS & CONCLUSION**\n\n" \
                           f"This notice is issued without prejudice to any other rights, powers, privileges, or statutory remedies available to the Data Principal under the {statute} or applicable law.\n\n" \
                           f"Failure, refusal, or unwarranted delay in complying with this statutory demand within the stipulated {days}-day window ({deadline_str}) shall immediately trigger formal complaint escalation to the {escalation_body} ({escalation_section}) for statutory inquiry and penal proceedings.\n\n" \
                           f"**Yours faithfully,**\n\n" \
                           f"**{user_name or 'Data Principal'}**  \n" \
                           f"Data Principal & Complainant  \n" \
                           f"Email: {user_email or '[On Record]'}  \n" \
                           f"Reference ID: {reference_id}  \n" \
                           f"Cryptographic Hash: `{receipt_hash}`\n"

        return ai_text, model_used

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
        ai_tailored: bool = True,
        exposure_context: str = "",
    ) -> dict:
        """
        Generate a statutory legal notice (AI-tailored with Gemini or template fallback).

        Args:
            jurisdiction: "dpdp", "gdpr", or "ccpa"
            user_name: Data principal's name
            user_email: Data principal's email
            user_phone: Data principal's phone
            additional_ids: Other identifiers (PAN, Aadhaar masked, etc.)
            company_name: Target company / data fiduciary
            company_address: Company address
            detected_pii_summary: Summary of detected PII exposure
            ai_tailored: Whether to use Gemini/LLM to draft a bespoke statutory notice
            exposure_context: Specific breach or incident background

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
        deadline_str = deadline.strftime("%d %B %Y")

        # Generate receipt hash
        receipt_content = f"{reference_id}|{user_email}|{company_name}|{now.isoformat()}"
        receipt_hash = hashlib.sha256(receipt_content.encode()).hexdigest()

        notice_text = None
        model_used = None
        is_ai = False

        if ai_tailored:
            ai_text, model_used = self._draft_with_ai(
                jurisdiction=jurisdiction,
                config=config,
                user_name=user_name,
                user_email=user_email,
                user_phone=user_phone,
                additional_ids=additional_ids,
                company_name=company_name,
                company_address=company_address,
                detected_pii_summary=detected_pii_summary,
                reference_id=reference_id,
                receipt_hash=receipt_hash,
                deadline_str=deadline_str,
                exposure_context=exposure_context,
            )
            if ai_text and len(ai_text) > 200:
                notice_text = ai_text
                is_ai = True

        # Fallback to deterministic template if AI was not requested or failed
        if not notice_text:
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
            "ai_generated": is_ai,
            "ai_model": model_used,
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
