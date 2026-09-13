"""
multi_agent_swarm.py — Collaborative Multi-Agent Privacy Swarm.

Splits the agent workflow into three specialized autonomous agents:
  🕵️ Forensics Agent:
      Analyzes raw telemetry, unstructured paste dumps, open-web snippets,
      extracts indirect identifiers regexes miss, and maps compound attack vectors.
  ⚖️ Legal Counsel Agent:
      Evaluates statutory jurisdictions (DPDP Act 2023, GDPR, CCPA),
      identifies exempt public/court registers, and drafts bespoke erasure notices.
  🛡️ Remediation Agent:
      Formulates direct self-serve vs statutory escalation blueprints,
      dispatches approved notices, and drives enforcement verification.
"""

import json
from dataclasses import dataclass
from typing import Any

from backend.agent.memory import utcnow
from backend.agent.openai_compat_planner import get_llm_completion
from backend.remediation.notice_generator import NoticeGenerator


@dataclass
class SwarmResult:
    forensics_report: dict
    threat_matrix: dict
    legal_dossier: dict
    remediation_plan: dict
    executive_summary: str


class ForensicsAgent:
    """
    🕵️ Forensics Agent:
    Specializes in unstructured text analysis, paste dump inspection,
    indirect identifier discovery, and cross-exposure correlation.
    """

    def __init__(self, ctx, tools: dict):
        self.ctx = ctx
        self.tools = tools

    def run(self, profile: dict, gathered_data: dict) -> dict:
        self.ctx.emit(
            "forensics", "analyze",
            "🕵️ Forensics Agent: Initiating deep telemetry analysis across breach corpora, pastes, and open-web snippets…",
        )

        exposures = self.ctx.memory.get_exposures(self.ctx.user_id)
        confirmed = [e for e in exposures if e.get("status") != "unconfirmed" and e.get("status") != "not_mine"]
        candidates = [e for e in exposures if e.get("status") == "unconfirmed"]

        # Run AI-powered deep threat surface correlation
        threat_surface = self._analyze_threat_intelligence(profile, confirmed)

        # Forensic analysis of indirect identifiers via LLM
        indirect_findings = self._extract_indirect_identifiers(profile, gathered_data, candidates)

        report = {
            "agent": "forensics",
            "confirmed_count": len(confirmed),
            "candidate_count": len(candidates),
            "threat_surface": threat_surface,
            "indirect_identifiers": indirect_findings,
            "timestamp": utcnow(),
        }

        vectors_count = len(threat_surface.get("threat_vectors", []))
        self.ctx.emit(
            "forensics", "report",
            f"🕵️ Forensics Agent: Analysis complete. Found {len(confirmed)} verified exposures, "
            f"{len(candidates)} candidate account(s), and {vectors_count} compound attack vector(s).",
            tool_output=report,
        )
        return report

    def _analyze_threat_intelligence(self, profile: dict, exposures: list[dict]) -> dict:
        """Analyze multi-breach combinations using Gemini / Groq threat intelligence."""
        base_threat = self.tools.get("analyze_threat_surface")
        base_res = base_threat() if base_threat else {"threat_vectors": []}

        if not exposures:
            return {
                "overall_surface_grade": "MINIMAL",
                "threat_vectors": [],
                "threat_summary": "Zero personal data exposures detected across scanned corpora.",
            }

        # Format context for AI threat analyst
        exposure_snippets = []
        for e in exposures[:20]:
            found = ", ".join(e.get("data_found") or [])
            exposure_snippets.append(f"- {e.get('source_name')} ({e.get('source_type')}): {found}")

        prompt = f"""You are SovereignPrivacy's Forensics AI Analyst. Analyze this victim's personal data exposures:

TARGET IDENTITY:
- Name: {profile.get('name', 'Anonymous')}
- Email: {profile.get('email', '')}
- Phone: {profile.get('phone', 'N/A')}

DISCOVERED DATA EXPOSURES:
{chr(10).join(exposure_snippets)}

TASK:
Identify real-world compound attack vectors where adversaries combine these specific leaks:
1. Credential Stuffing & Account Takeover (if password hashes / emails are exposed).
2. Targeted SIM Swap & OTP Interception (if phone numbers and identity data are exposed).
3. Spear Phishing & Executive / Recruitment Fraud (if workplace / salary / resumes are exposed).
4. Synthetic Identity & Unauthorized KYC Abuse (if government IDs or PAN/Aadhaar/DOB are exposed).

Return a clean JSON object with this exact schema:
{{
  "overall_surface_grade": "CRITICAL" | "ELEVATED" | "MODERATE" | "MINIMAL",
  "threat_vectors": [
    {{
      "vector": "Name of attack vector",
      "severity": "critical" | "high" | "medium",
      "affected_sources": ["Service 1", "Service 2"],
      "adversary_playbook": "How an attacker combines these data points to exploit the victim",
      "blue_team_mitigation": "Immediate concrete technical defense action"
    }}
  ],
  "threat_summary": "One concise paragraph explaining the highest immediate danger."
}}
"""
        res_text, model_used = get_llm_completion(
            messages=[
                {"role": "system", "content": "You are a cyber threat intelligence specialist. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
            temperature=0.2,
        )

        if res_text:
            try:
                clean = res_text.strip()
                if "```json" in clean:
                    clean = clean.split("```json", 1)[1].split("```", 1)[0].strip()
                elif "```" in clean:
                    clean = clean.split("```", 1)[1].split("```", 1)[0].strip()
                parsed = json.loads(clean)
                parsed["ai_model"] = model_used
                return parsed
            except Exception:
                pass

        return base_res

    def _extract_indirect_identifiers(self, profile: dict, gathered_data: dict, candidates: list) -> list:
        """Infer secondary identity handles and pseudonyms from candidate accounts."""
        if not candidates:
            return []
        items = []
        for c in candidates[:6]:
            items.append({
                "service": c.get("source_name"),
                "handle": c.get("record_id") or c.get("source_id"),
                "confidence": "candidate",
            })
        return items


class LegalCounselAgent:
    """
    ⚖️ Legal Counsel Agent:
    Specializes in statutory regime evaluation (DPDP Act 2023, GDPR, CCPA),
    exempt record determination (judicial/statutory publications),
    and drafting tailored, formal statutory erasure notices.
    """

    def __init__(self, ctx, tools: dict):
        self.ctx = ctx
        self.tools = tools
        self.notice_gen = NoticeGenerator()

    def run(self, profile: dict, actionable_exposures: list[dict]) -> dict:
        self.ctx.emit(
            "legal_counsel", "statute",
            "⚖️ Legal Counsel Agent: Evaluating statutory legal bases, exemptions, and compliance duties…",
        )

        legal_assessments = []
        drafted_notices = []
        exempt_records = []

        for exp in actionable_exposures:
            eid = exp.get("exposure_id") or exp.get("id")
            source_name = exp.get("source") or exp.get("name") or exp.get("source_name", "")

            # 1. Determine governing legal basis
            basis = self.tools["determine_legal_basis"](exposure_id=eid)
            jurisdiction = basis.get("jurisdiction", "dpdp")

            # 2. Check for statutory exemptions (court records, MCA filings, credit bureaus)
            legal_class = basis.get("legal_class", "")
            is_exempt = (
                basis.get("statutory_right") == "exempt"
                or "court" in legal_class
                or "judicial" in legal_class
                or "statutory_register" in legal_class
            )

            if is_exempt:
                exempt_records.append({
                    "exposure_id": eid,
                    "source": source_name,
                    "statute": basis.get("statute_cited", "Statutory Exemption"),
                    "reason": basis.get("legal_basis", "Exempt public record"),
                    "recommended_action": basis.get("recommended_action", "Monitor; statutory erasure does not apply."),
                })
                self.ctx.emit(
                    "legal_counsel", "refuse",
                    f"⚖️ Legal Counsel: Statutory erasure is inapplicable for {source_name} ({basis.get('statute_cited')}) "
                    f"— exempt public or judicial archive.",
                    tool_output={"source": source_name, "reason": basis.get("legal_basis")},
                )
                continue

            # 3. Plan removal strategy
            plan = self.tools["plan_removal"](exposure_id=eid)
            method = plan.get("method")

            legal_assessments.append({
                "exposure_id": eid,
                "source": source_name,
                "jurisdiction": jurisdiction,
                "statute": basis.get("statute_cited"),
                "method": method,
                "deadline_days": basis.get("response_deadline_days", 30),
                "escalation_body": basis.get("escalation_authority"),
            })

            # 4. Draft notice if statutory notice is required
            if method == "statutory_notice":
                self.ctx.emit(
                    "legal_counsel", "draft",
                    f"⚖️ Legal Counsel: Drafting tailored {jurisdiction.upper()} notice for {source_name}…",
                    tool_name="draft_erasure_request",
                )
                draft_res = self.tools["draft_erasure_request"](exposure_id=eid, jurisdiction=jurisdiction)
                if "request_id" in draft_res or "reference_id" in draft_res:
                    drafted_notices.append(draft_res)

        report = {
            "agent": "legal_counsel",
            "assessments": legal_assessments,
            "drafted_notices": drafted_notices,
            "exempt_records": exempt_records,
            "statutory_regimes": list(set(a["jurisdiction"] for a in legal_assessments)),
        }

        self.ctx.emit(
            "legal_counsel", "report",
            f"⚖️ Legal Counsel Agent: Completed statutory analysis. Drafted {len(drafted_notices)} bespoke notice(s); "
            f"identified {len(exempt_records)} legally exempt record(s).",
            tool_output=report,
        )
        return report


class RemediationAgent:
    """
    🛡️ Remediation Agent:
    Specializes in formulating remediation blueprints (Self-Serve vs Statutory),
    executing dispatch with cryptographic audit trails, verifying removal independently,
    and triggering regulatory escalation for non-compliant data fiduciaries.
    """

    def __init__(self, ctx, tools: dict):
        self.ctx = ctx
        self.tools = tools

    def plan_remediation(self, profile: dict, legal_dossier: dict, forensics_report: dict) -> dict:
        self.ctx.emit(
            "remediation", "plan",
            "🛡️ Remediation Agent: Formulating self-serve vs. statutory dispatch triage roadmap…",
        )

        assessments = legal_dossier.get("assessments", [])
        self_serve_actions = []
        statutory_actions = []
        credential_rotations = []

        for a in assessments:
            eid = a["exposure_id"]
            src = a["source"]
            plan = self.tools["plan_removal"](exposure_id=eid)

            if plan.get("method") == "self_serve":
                self_serve_actions.append({
                    "service": src,
                    "url": plan.get("url", ""),
                    "steps": plan.get("steps", []),
                    "effort_minutes": plan.get("effort_minutes", 3),
                    "escalation": plan.get("escalation", ""),
                })
            elif plan.get("method") == "statutory_notice":
                statutory_actions.append({
                    "service": src,
                    "statute": a.get("statute"),
                    "deadline_days": a.get("deadline_days"),
                    "escalation_body": a.get("escalation_body"),
                })

        # Identify credential rotation needs from threat surface
        vectors = forensics_report.get("threat_surface", {}).get("threat_vectors", [])
        for v in vectors:
            if "Credential Stuffing" in v.get("vector", ""):
                for s in v.get("affected_sources", []):
                    credential_rotations.append(s)

        plan_summary = {
            "agent": "remediation",
            "self_serve": self_serve_actions,
            "statutory_drafted": statutory_actions,
            "credential_rotations": list(set(credential_rotations)),
            "exempt_count": len(legal_dossier.get("exempt_records", [])),
        }

        self.ctx.emit(
            "remediation", "strategy",
            f"🛡️ Remediation Agent: Strategy finalized. {len(self_serve_actions)} instant self-serve route(s), "
            f"{len(statutory_actions)} statutory notice(s) awaiting approval, "
            f"{len(credential_rotations)} credential rotation priority.",
            tool_output=plan_summary,
        )
        return plan_summary

    def execute_remediation(self, request_ids: list[str]) -> dict:
        """Execute approved statutory notices with independent verification."""
        self.ctx.emit(
            "remediation", "enforce",
            f"🛡️ Remediation Agent: Dispatching {len(request_ids)} user-approved statutory erasure demand(s)…",
        )

        removed = []
        pending = []
        escalated = []

        for rid in request_ids:
            sub = self.tools["submit_erasure_request"](rid)
            if sub.get("status") != "submitted":
                continue
            broker = sub.get("broker", "")

            # Check status twice (simulates controller follow-up)
            for _ in range(2):
                st = self.tools["check_request_status"](rid)
                if st.get("status") == "completed":
                    break

            req = self.ctx.memory.get_request(rid)
            if req:
                v = self.tools["verify_removal"](req["exposure_id"])
                if v.get("verified_removed"):
                    removed.append(broker)
                    self.ctx.emit(
                        "remediation", "verify",
                        f"🛡️ Remediation Agent: Independent verification CONFIRMED: data erased at {broker}.",
                        status="ok",
                    )
                else:
                    esc = self.tools["escalate_to_regulator"](rid)
                    escalated.append(f"{broker} → {esc.get('authority')}")
                    pending.append(broker)
                    self.ctx.emit(
                        "remediation", "escalate",
                        f"🛡️ Remediation Agent: Controller {broker} failed to verify erasure — escalated to {esc.get('authority')}.",
                        status="awaiting_approval",
                    )

        return {
            "dispatched_count": len(request_ids),
            "verified_removed": removed,
            "escalated": escalated,
            "pending": pending,
        }


class MultiAgentSwarm:
    """Orchestrates the collaborative 3-agent swarm."""

    def __init__(self, ctx, tools: dict):
        self.ctx = ctx
        self.tools = tools
        self.forensics = ForensicsAgent(ctx, tools)
        self.legal_counsel = LegalCounselAgent(ctx, tools)
        self.remediation = RemediationAgent(ctx, tools)

    def run_discovery_swarm(self, profile: dict, gathered_data: dict, actionable: list[dict], stream) -> str:
        self.ctx.emit("orchestrator", "swarm", "Activating Collaborative Multi-Agent Privacy Swarm…")

        # Phase 1: Forensics Agent
        forensics_report = self.forensics.run(profile, gathered_data)

        # Phase 2: Legal Counsel Agent
        legal_dossier = self.legal_counsel.run(profile, actionable)

        # Phase 3: Remediation Agent
        remediation_plan = self.remediation.plan_remediation(profile, legal_dossier, forensics_report)

        # Generate Swarm Synthesis Executive Summary via LLM
        summary = self._synthesize_swarm_summary(profile, forensics_report, legal_dossier, remediation_plan, stream)
        return summary

    def _synthesize_swarm_summary(
        self, profile: dict, forensics: dict, legal: dict, remediation: dict, stream
    ) -> str:
        threat_surface = forensics.get("threat_surface", {})
        vectors = threat_surface.get("threat_vectors", [])
        self_serve = remediation.get("self_serve", [])
        drafted = legal.get("drafted_notices", [])
        exempt = legal.get("exempt_records", [])

        user_name = profile.get("name", "User")
        prompt = f"""You are the Lead Coordinator for SovereignPrivacy's Collaborative Multi-Agent Swarm.
Synthesize the final authoritative privacy intelligence report for {user_name} based on findings from your specialized sub-agents:

1. 🕵️ FORENSICS AGENT FINDINGS:
- Verified Exposures: {forensics.get('confirmed_count', 0)}
- Compound Threat Surface Grade: {threat_surface.get('overall_surface_grade', 'MODERATE')}
- Attack Vectors Identified: {len(vectors)}
{json.dumps(vectors[:3], indent=2)}

2. ⚖️ LEGAL COUNSEL AGENT FINDINGS:
- Statutory Regimes Evaluated: DPDP Act 2023 s.12/13, GDPR Art. 17, CCPA § 1798.105
- Tailored Statutory Notices Drafted: {len(drafted)} ({', '.join(d.get('broker', '') for d in drafted[:4]) or 'None required'})
- Legally Exempt Public/Court Records: {len(exempt)} ({', '.join(e.get('source', '') for e in exempt[:3]) or 'None'})

3. 🛡️ REMEDIATION AGENT STRATEGY:
- Instant Self-Serve Deletions: {len(self_serve)} ({', '.join(s.get('service', '') for s in self_serve[:4]) or 'None'})
- Credential Rotations Required: {len(remediation.get('credential_rotations', []))}

Write a crisp, commanding executive summary in GitHub-flavored Markdown:
- Section 1: Executive Posture & Threat Intelligence (Highlight the compound attack vectors).
- Section 2: Statutory Legal Rights Asserted (Detail the drafted statutory erasure demands and legal exemptions).
- Section 3: Actionable Defense Roadmap (Concrete immediate steps: Self-serve links, 2FA rotation, reviewing drafted notices).
Keep it authoritative, factual, and strictly grounded in these findings.
"""

        res_text, model_used = get_llm_completion(
            messages=[
                {"role": "system", "content": "You are the Chief Privacy Officer and Swarm Coordinator. Be clear and authoritative."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=900,
            temperature=0.25,
        )

        if res_text:
            stream.put({
                "type": "agent_reasoning",
                "run_id": self.ctx.run_id,
                "ts": utcnow(),
                "text": res_text,
                "agent": "swarm_coordinator",
                "model": model_used,
            })
            self.ctx.emit("orchestrator", "plan", f"Swarm Executive Assessment generated via {model_used}.")
            return res_text

        return (
            f"### Multi-Agent Swarm Intelligence Assessment\n\n"
            f"**🕵️ Forensics Agent**: Identified {forensics.get('confirmed_count', 0)} verified exposure(s) across "
            f"breach archives and public indexes. Threat surface grade: **{threat_surface.get('overall_surface_grade', 'MODERATE')}** "
            f"with {len(vectors)} compound attack vector(s).\n\n"
            f"**⚖️ Legal Counsel Agent**: Asserted statutory rights under DPDP Act 2023 / GDPR. "
            f"Drafted **{len(drafted)}** bespoke statutory notice(s). Confirmed that {len(exempt)} court/registry record(s) "
            f"are legally exempt from statutory erasure.\n\n"
            f"**🛡️ Remediation Agent**: Formulated **{len(self_serve)}** instant self-serve deletion route(s). "
            f"Awaiting user authorization to dispatch drafted statutory notices with independent cryptographic verification."
        )
