"""
orchestrator.py — The agent loop.

Two planners drive the same tools:

  LLM planner (default when ANTHROPIC_API_KEY is set)
      Claude decides which tool to call next and why, using the tool runner's
      agentic loop. Its reasoning text is streamed to the UI, so what the judge
      sees is the model's actual decision-making, not a scripted animation.

  Deterministic planner (fallback)
      A fixed pipeline over the identical tools. Used when no key is configured
      or the venue has no network. The product still works end to end; only the
      reasoning is canned, and the UI says which planner ran.

Both emit the same event stream, so the frontend does not care which ran.
"""

import json
import os
import queue
import traceback
from dataclasses import dataclass

from backend.agent.memory import get_memory, utcnow
from backend.agent.prompts import SYSTEM, DISCOVERY_GOAL, REMEDIATION_GOAL
from backend.agent.tools import ToolContext, build_tools
from backend.mock_brokers.network import get_network

MODEL = os.environ.get("SOVEREIGN_MODEL", "claude-opus-5")
EFFORT = os.environ.get("SOVEREIGN_EFFORT", "high")
MAX_TOKENS = 8000


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def planner_mode() -> str:
    return "llm" if llm_available() else "deterministic"


class EventStream:
    """Thread-safe sink the tools emit into; the WebSocket drains it."""

    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.events: list[dict] = []

    def put(self, event: dict):
        self.events.append(event)
        self.q.put(event)

    def close(self):
        self.q.put(None)


def _make_emitter(memory, user_id: str, run_id: str, stream: EventStream):
    def emit(agent: str, phase: str, message: str, tool_name: str = "",
             tool_input=None, tool_output=None, status: str = "ok"):
        ev = memory.log_event(user_id, run_id, agent, phase, message,
                              tool_name, tool_input, tool_output, status)
        ev["run_id"] = run_id
        stream.put({"type": "agent_event", **ev})
    return emit


# ── LLM planner ──────────────────────────────────────────────────────────────

def _run_llm(ctx: ToolContext, tools: dict, goal: str, stream: EventStream) -> str:
    import anthropic
    from anthropic import beta_tool

    client = anthropic.Anthropic()
    wrapped = [beta_tool(fn) for fn in tools.values()]

    ctx.emit("orchestrator", "plan", f"Planning with {MODEL} (effort={EFFORT})…")

    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        tools=wrapped,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": EFFORT},
        messages=[{"role": "user", "content": goal}],
    )

    final_text = ""
    for message in runner:
        if getattr(message, "stop_reason", None) == "refusal":
            ctx.emit("orchestrator", "error", "Model declined this request.", status="error")
            break
        for block in message.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                stream.put({"type": "agent_reasoning", "run_id": ctx.run_id,
                            "ts": utcnow(), "text": block.thinking})
            elif block.type == "text" and block.text.strip():
                final_text = block.text
                ctx.emit("orchestrator", "reasoning", block.text.strip())
    return final_text


# ── Deterministic planner ────────────────────────────────────────────────────

def _run_deterministic_discovery(ctx: ToolContext, tools: dict) -> str:
    ctx.emit("orchestrator", "plan",
             "Planning with the deterministic pipeline (no ANTHROPIC_API_KEY configured).")

    tools["recall_prior_activity"]()
    tools["build_identity_profile"]()

    # Real checks first. These query live endpoints and return proof.
    breaches = tools["verify_breach_exposure"]()
    if ctx.profile.get("password"):
        tools["verify_password_exposure"](ctx.profile["password"])
    # Accounts the user says they hold — their own knowledge, valid grounds.
    declared = tools["declare_known_accounts"](ctx.profile.get("declared_accounts", ""))
    # Sandbox, only if explicitly enabled.
    brokers = tools["search_data_brokers"]()
    pastes = tools["search_paste_dumps"]() if ctx.sandbox else {"exposures": []}
    risk = tools["assess_exposure_risk"]()

    actionable = [{"exposure_id": d["exposure_id"], "broker": d["service"]}
                  for d in declared.get("declared", [])]
    actionable += [{"exposure_id": r["exposure_id"], "broker": r["broker"]}
                   for r in brokers.get("removable_records", [])]

    drafted, refused = [], []
    for rec in actionable:
        basis = tools["determine_legal_basis"](rec["exposure_id"])
        if not basis.get("erasure_available"):
            refused.append((rec.get("broker", ""), basis.get("recommended_action", "")))
            ctx.emit("legal", "refuse",
                     f"Declining to draft for {rec.get('broker', '')} — "
                     f"{basis.get('legal_basis', '')[:150]}")
            continue
        d = tools["draft_erasure_request"](rec["exposure_id"], basis["jurisdiction"])
        if "request_id" in d:
            drafted.append(d)

    n_verified = len(breaches.get("verified_exposures", []))
    n_declared = len(declared.get("declared", []))
    n_sandbox = len(brokers.get("removable_records", []))
    n_unchecked = len(breaches.get("not_checked", []))
    summary = (
        f"{n_verified} VERIFIED exposure(s) from live checks, "
        f"{n_declared} self-declared account(s)"
        + (f", {n_sandbox} sandbox record(s)" if n_sandbox else "")
        + f". {n_unchecked} check(s) could not run and nothing was guessed for them. "
        f"Privacy Risk Score {risk['overall_score']} ({risk['risk_level']}). "
        f"Drafted {len(drafted)} erasure notice(s) awaiting your approval. "
        + (f"Declined to draft for {len(refused)} source(s) where erasure does not lie "
           f"({'; '.join(f'{n} → {a}' for n, a in refused)}). " if refused else "")
        + "Breach records cannot be un-published — rotate those credentials and enable 2FA."
    )
    ctx.emit("orchestrator", "summary", summary)
    return summary


def _run_deterministic_remediation(ctx: ToolContext, tools: dict, request_ids: list[str]) -> str:
    ctx.emit("orchestrator", "plan", f"Dispatching {len(request_ids)} approved notice(s).")
    removed, pending, escalated = [], [], []

    for rid in request_ids:
        sub = tools["submit_erasure_request"](rid)
        if sub.get("status") != "submitted":
            continue
        broker = sub.get("broker", "")
        # Follow up twice: enough for a prompt or slow controller to complete.
        status = None
        for _ in range(2):
            status = tools["check_request_status"](rid)
            if status.get("status") == "completed":
                break
        req = ctx.memory.get_request(rid)
        v = tools["verify_removal"](req["exposure_id"])
        if v.get("verified_removed"):
            removed.append(broker)
        else:
            esc = tools["escalate_to_regulator"](rid)
            escalated.append(f"{broker} → {esc.get('authority')}")
            pending.append(broker)

    summary = (
        f"Dispatched {len(request_ids)} notice(s). "
        f"Verified removal at {len(removed)} controller(s)"
        + (f" ({', '.join(removed)})" if removed else "")
        + ". "
        + (f"{len(escalated)} unresolved and escalated: {'; '.join(escalated)}." if escalated
           else "No escalations required.")
    )
    ctx.emit("orchestrator", "summary", summary)
    return summary


# ── public entry points ──────────────────────────────────────────────────────

@dataclass
class RunResult:
    run_id: str
    user_id: str
    mode: str
    summary: str
    events: list
    error: str = ""


def _prepare(profile: dict, stream: EventStream, auto_approve: bool):
    """Build the run context. `sandbox` is opt-in and off unless asked for."""
    memory = get_memory()
    user_id = memory.upsert_user(profile)
    mode = planner_mode()
    run_id = memory.start_run(user_id, mode, MODEL if mode == "llm" else "")
    ctx = ToolContext(
        memory=memory, network=get_network(), user_id=user_id, run_id=run_id,
        profile=profile, emit=_make_emitter(memory, user_id, run_id, stream),
        auto_approve=auto_approve,
        sandbox=bool(profile.get("sandbox", False)),
    )
    return memory, ctx, build_tools(ctx), mode


def run_discovery(profile: dict, stream: EventStream) -> RunResult:
    """Phase 1: discover, assess, decide, draft. Never dispatches."""
    memory, ctx, tools, mode = _prepare(profile, stream, auto_approve=False)
    risk_before = 0.0
    prior = memory.last_run_before(ctx.user_id, ctx.run_id)
    if prior and prior.get("risk_after") is not None:
        risk_before = prior["risk_after"]

    error = ""
    try:
        if mode == "llm":
            # Dispatch is withheld from the toolset in this phase — the agent
            # cannot send anything even if it decides it wants to.
            phase_tools = {k: v for k, v in tools.items() if k != "submit_erasure_request"}
            summary = _run_llm(ctx, phase_tools,
                               DISCOVERY_GOAL.format(profile=json.dumps(profile, indent=2)), stream)
        else:
            summary = _run_deterministic_discovery(ctx, tools)
    except Exception as exc:                                   # demo must not hard-fail
        error = f"{type(exc).__name__}: {exc}"
        ctx.emit("orchestrator", "error",
                 f"LLM planner failed ({error}). Falling back to the deterministic pipeline.",
                 status="error")
        traceback.print_exc()
        summary = _run_deterministic_discovery(ctx, tools)
        mode = "deterministic_fallback"

    assessment = tools["assess_exposure_risk"]()
    memory.finish_run(ctx.run_id, risk_before, assessment["overall_score"], summary)
    stream.put({"type": "run_complete", "run_id": ctx.run_id, "summary": summary})
    stream.close()
    return RunResult(ctx.run_id, ctx.user_id, mode, summary, stream.events, error)


def run_remediation(profile: dict, request_ids: list[str], stream: EventStream) -> RunResult:
    """Phase 2: the user approved; dispatch, follow up, verify, escalate."""
    memory, ctx, tools, mode = _prepare(profile, stream, auto_approve=True)
    risk_before = 0.0
    assessment_before = tools["assess_exposure_risk"]()
    risk_before = assessment_before["overall_score"]

    error = ""
    try:
        if mode == "llm":
            summary = _run_llm(ctx, tools,
                               REMEDIATION_GOAL.format(request_ids=", ".join(request_ids)), stream)
        else:
            summary = _run_deterministic_remediation(ctx, tools, request_ids)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        ctx.emit("orchestrator", "error",
                 f"LLM planner failed ({error}). Falling back to the deterministic pipeline.",
                 status="error")
        traceback.print_exc()
        summary = _run_deterministic_remediation(ctx, tools, request_ids)
        mode = "deterministic_fallback"

    assessment = tools["assess_exposure_risk"]()
    memory.finish_run(ctx.run_id, risk_before, assessment["overall_score"], summary)
    stream.put({"type": "run_complete", "run_id": ctx.run_id, "summary": summary,
                "risk_before": risk_before, "risk_after": assessment["overall_score"]})
    stream.close()
    return RunResult(ctx.run_id, ctx.user_id, mode, summary, stream.events, error)
