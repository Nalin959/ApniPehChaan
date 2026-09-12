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

from backend.agent import openai_compat_planner
from backend.agent.memory import get_memory, utcnow
from backend.agent.prompts import (
    SYSTEM, DISCOVERY_GOAL, JUDGEMENT_GOAL, JUDGEMENT_SYSTEM, REMEDIATION_GOAL,
    NO_EXPOSURES_GOAL, NO_EXPOSURES_SYSTEM)
from backend.agent.tools import ToolContext, build_tools
from backend.mock_brokers.network import get_network

MODEL = os.environ.get("SOVEREIGN_MODEL", "claude-opus-5")
EFFORT = os.environ.get("SOVEREIGN_EFFORT", "high")
MAX_TOKENS = 8000


def anthropic_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def llm_available() -> bool:
    return anthropic_available() or openai_compat_planner.available()


def planner_mode() -> str:
    """
    Which planner drives the loop.

    SOVEREIGN_PLANNER pins a choice ("anthropic" / a provider name / "deterministic");
    otherwise whichever key is configured wins, Anthropic first when both are.
    Every planner calls the identical tools, so this changes who decides the
    order — never what the product does or finds.
    """
    pinned = (os.environ.get("SOVEREIGN_PLANNER") or "").strip().lower()
    if pinned == "deterministic":
        return "deterministic"
    if pinned == "anthropic" and anthropic_available():
        return "anthropic"
    if pinned in ("openai_compat", *openai_compat_planner.PROVIDERS) and \
            openai_compat_planner.available():
        return "openai_compat"

    if anthropic_available():
        return "anthropic"
    if openai_compat_planner.available():
        return "openai_compat"
    return "deterministic"


def planner_model() -> str | None:
    mode = planner_mode()
    if mode == "anthropic":
        return MODEL
    if mode == "openai_compat":
        prov = openai_compat_planner.configured()
        return f"{openai_compat_planner.model_for(prov)} ({prov})" if prov else None
    return None


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

    # An organisation API key that is not scoped to a workspace must name one on
    # every request; a workspace-scoped key carries it implicitly. Supporting the
    # header means either kind of key works without the user re-issuing one.
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
    client = (anthropic.Anthropic(default_headers={"anthropic-workspace-id": workspace})
              if workspace else anthropic.Anthropic())
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

def _run_mandatory_discovery(ctx: ToolContext, tools: dict) -> dict:
    """
    Run every gathering step that must happen regardless of what a planner thinks.

    Asking a model to remember to call build_identity_profile wastes a round trip
    and is a reliability risk: it is cheap, local, and always correct to run.
    Measured, leaving the whole sequence to the planner took ~117s and it still
    skipped fourteen of the twenty tools.

    So the deterministic layer does the LOOKING, which is mechanical, and the
    planner is left the JUDGEMENT — which exposures are worth acting on, which
    statute applies, whether a notice should be drafted at all. That is the part
    that actually needs reasoning, and the part a judge is assessing.
    """
    out: dict = {}
    out["prior"] = tools["recall_prior_activity"]()
    out["identity"] = tools["build_identity_profile"]()
    out["identifiers"] = tools["match_unique_identifiers"]()
    out["breaches"] = tools["verify_breach_exposure"]()
    if ctx.profile.get("password"):
        out["password"] = tools["verify_password_exposure"](ctx.profile["password"])
    out["accounts"] = tools["discover_accounts"]()
    # The open web, not just the site list. A fixed roster of sites can only
    # find what is on the roster; this asks a search engine for the identifiers
    # that belong to exactly one person, then reads every page it gets back and
    # keeps only those where the identifier is actually present.
    out["web"] = tools["search_open_web"]()
    out["declared"] = tools["declare_known_accounts"](ctx.profile.get("declared_accounts", ""))
    out["brokers"] = tools["search_data_brokers"]()
    out["pastes"] = tools["search_paste_dumps"]() if ctx.sandbox else {"exposures": []}
    out["registry"] = tools["browse_indian_registry"]()
    out["risk"] = tools["assess_exposure_risk"]()
    return out


def _run_deterministic_discovery(ctx: ToolContext, tools: dict) -> str:
    reason = ("no planner key configured" if not llm_available()
              else "the LLM planner was unavailable")
    ctx.emit("orchestrator", "plan",
             f"Planning with the deterministic pipeline ({reason}) — same 20 tools.")

    g = _run_mandatory_discovery(ctx, tools)
    breaches, idmatch = g["breaches"], g["identifiers"]
    accounts, declared = g["accounts"], g["declared"]
    brokers, pastes, risk = g["brokers"], g["pastes"], g["risk"]

    web = g["web"]
    actionable = [{"exposure_id": a["exposure_id"], "name": a["site"]}
                  for a in accounts.get("found", [])]
    actionable += [{"exposure_id": w["exposure_id"], "name": w["domain"]}
                   for w in web.get("confirmed", [])]
    actionable += [{"exposure_id": d["exposure_id"], "name": d["service"]}
                   for d in declared.get("declared", [])]
    actionable += [{"exposure_id": r["exposure_id"], "name": r["broker"]}
                   for r in brokers.get("removable_records", [])]

    # Choose the cheapest effective removal route for each. A statutory notice
    # is the escalation, not the default — most services have a delete button,
    # and serving a legal notice on one of those wastes 30 days to achieve what
    # a link achieves in three minutes.
    drafted, self_serve, refused = [], [], []
    for rec in actionable:
        plan = tools["plan_removal"](rec["exposure_id"])
        method = plan.get("method")

        if method == "not_removable":
            refused.append((rec["name"], plan.get("legal_position", "")[:110]))
        elif method == "statutory_notice":
            d = tools["draft_erasure_request"](rec["exposure_id"], plan.get("jurisdiction") or "")
            if "request_id" in d:
                drafted.append(d)
        else:
            self_serve.append({"service": rec["name"], "method": method,
                               "url": plan.get("url", ""), "steps": plan.get("steps", []),
                               "minutes": plan.get("effort_minutes"),
                               "escalation": plan.get("escalation", "")})

    n_verified = len(breaches.get("verified_exposures", []))
    n_found = len(accounts.get("found", []))
    n_declared = len(declared.get("declared", []))
    n_sandbox = len(brokers.get("removable_records", []))
    n_unchecked = len(breaches.get("not_checked", []))
    n_idhits = len(idmatch.get("hits", []))
    summary = (
        (f"{n_idhits} confirmed leak exposure(s) matched on your unique identifiers "
         f"({', '.join(idmatch.get('searched', []))}). " if n_idhits else
         f"No leak match on your unique identifiers ({', '.join(idmatch.get('searched', [])) or 'none supplied'}). ")
        + (f"Open-web search confirmed your data on {len(web.get('confirmed', []))} page(s) "
           f"across {len(web.get('domains', []))} domain(s) — each one fetched and the "
           f"identifier found on the page itself. " if web.get("confirmed") else "")
        # A refused search is not a clean one. Say so, rather than let silence
        # read as "nothing is out there".
        + (f"The open-web search could NOT be completed — the search engine refused "
           f"{len(web.get('blocked_queries', []))} of {web.get('searched', 0)} quer(ies) "
           f"(rate limiting). This is not a clean result; re-run to finish it. "
           if web.get("search_degraded") else
           (f"Open-web search completed and found no page carrying your identifiers "
            f"verbatim ({web.get('pages_fetched', 0)} result(s) read). "
            if not web.get("confirmed") else ""))
        + f"Found {n_found} live account(s) by searching {accounts.get('sites_checked', 0)} sites, "
        f"{n_verified} verified breach/profile exposure(s)"
        + (f", {n_declared} you declared" if n_declared else "")
        + (f", {n_sandbox} sandbox record(s)" if n_sandbox else "")
        + f". {n_unchecked} check(s) could not run and nothing was guessed. "
        f"Privacy Risk Score {risk['overall_score']} ({risk['risk_level']}). "
        + (f"{len(self_serve)} can be removed yourself in minutes — no legal notice needed "
           f"({', '.join(s['service'] for s in self_serve[:4])}"
           f"{'…' if len(self_serve) > 4 else ''}). " if self_serve else "")
        + (f"Drafted {len(drafted)} statutory notice(s) where no self-serve route exists. "
           if drafted else "No statutory notice was necessary. ")
        + (f"{len(refused)} source(s) cannot be erased at all. " if refused else "")
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

def _explain(exc: Exception, mode: str = "anthropic") -> str:
    if mode == "openai_compat":
        return openai_compat_planner.explain(exc)
    return _explain_anthropic(exc)


def _explain_anthropic(exc: Exception) -> str:
    """
    A one-line, actionable reason the LLM planner could not run.

    A full traceback in the console mid-demo reads as a crash. It is not one:
    the run continues on the deterministic pipeline over the identical tools,
    and the mode is reported honestly as deterministic_fallback.
    """
    name = type(exc).__name__
    if name == "AuthenticationError":
        return "the ANTHROPIC_API_KEY in .env was rejected (401). Check it is pasted in full"
    if name == "BadRequestError" and "credit balance" in str(exc).lower():
        return ("the Anthropic account has no credit. Add some at "
                "console.anthropic.com/settings/billing (~$5 covers many demo runs)")
    if name == "BadRequestError" and "workspace" in str(exc).lower():
        return ("that API key is not scoped to a workspace — either add "
                "ANTHROPIC_WORKSPACE_ID to .env, or create a workspace-scoped key")
    if name == "PermissionDeniedError":
        return "that API key lacks access to this model"
    if name == "RateLimitError":
        return "rate limited by the API; try again shortly"
    if name in ("APIConnectionError", "APITimeoutError"):
        return "could not reach the API — check the network"
    if name == "NotFoundError":
        return f"model {MODEL!r} was not found for this key"
    if name == "ImportError" or name == "ModuleNotFoundError":
        return "the anthropic SDK is not installed (pip install anthropic)"
    msg = str(exc).split("\n")[0][:120]
    return f"{name}: {msg}"


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
    run_id = memory.start_run(user_id, mode, planner_model() or "")
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
        if mode in ("anthropic", "openai_compat"):
            # Gathering is mechanical and always worth doing, so it runs
            # unconditionally — every tool, every time, no round trip spent
            # deciding whether to look.
            gathered = _run_mandatory_discovery(ctx, tools)

            # The planner then does the part that needs judgement, over findings
            # that already exist.
            #
            # It is given ONLY the tools that phase uses. Every schema is resent
            # on every round trip, so handing it all twenty costs ~600 tokens per
            # call for eighteen tools it will never touch — and free tiers cap
            # TOKENS PER MINUTE (Groq: 8000) far more tightly than requests, so
            # that overhead is what actually throttles the run. Measured: the
            # mandatory gathering takes 0.8s; the planner phase took 154s almost
            # entirely on token throughput.
            #
            # Dispatch is absent from this set, so the agent cannot send anything
            # even if it decides it wants to.
            JUDGEMENT_TOOLS = ("determine_legal_basis", "plan_removal",
                               "draft_erasure_request")
            phase_tools = {k: v for k, v in tools.items() if k in JUDGEMENT_TOOLS}

            # Query all active actionable exposures recorded for this user across all tools
            # Unconfirmed candidates are held back for user confirmation in the UI
            all_exposures = ctx.memory.get_exposures(ctx.user_id)
            active_exposures = [
                e for e in all_exposures
                if e.get("status") in ("exposed", None) and e.get("evidence_class") != "candidate"
            ]
            # Rank by severity and send the planner only the worst of them.
            #
            # An address in a large breach corpus can produce hundreds of
            # exposures. Every one of them costs tokens in the goal, and the
            # whole conversation is resent on every round trip, so an unbounded
            # list walks straight through a free tier's per-minute token budget
            # (Groq: 8000) and the run dies mid-way. It is also worse reasoning:
            # the judgement asked for is which exposures are worth acting on,
            # and that judgement is not improved by paging through the two
            # hundredth low-severity record.
            #
            # The cap is on what the PLANNER sees. Every exposure is still
            # recorded, still scored, and still shown to the user.
            _RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            ranked = sorted(active_exposures,
                            key=lambda e: (_RANK.get((e.get("severity") or "low").lower(), 3),
                                           -(e.get("risk_score") or 0.0)))
            PLANNER_EXPOSURE_CAP = 40
            actionable = [
                {"exposure_id": e.get("exposure_id") or e["id"], "source": e["source_name"],
                 "severity": e.get("severity")}
                for e in ranked[:PLANNER_EXPOSURE_CAP]
            ]
            withheld = len(ranked) - len(actionable)
            if withheld > 0:
                ctx.emit("orchestrator", "plan",
                         f"{len(ranked)} active exposures; the {len(actionable)} most severe are "
                         f"sent for judgement and {withheld} lower-severity record(s) are "
                         f"summarised. All {len(ranked)} remain in your ledger and risk score.")
            if not actionable:
                actionable = ([{"exposure_id": a.get("exposure_id") or a["id"], "source": a["site"]}
                               for a in gathered["accounts"].get("attributed", [])]
                              + [{"exposure_id": d.get("exposure_id") or d["id"], "source": d["service"]}
                                 for d in gathered["declared"].get("declared", [])]
                              + [{"exposure_id": r.get("exposure_id") or r["id"], "source": r["broker"]}
                                 for r in gathered["brokers"].get("removable_records", [])]
                              + [{"exposure_id": b.get("exposure_id") or b["id"], "source": b["source"]}
                                 for b in gathered["breaches"].get("verified_exposures", [])]
                              + [{"exposure_id": h.get("exposure_id") or h["id"], "source": h["source"]}
                                 for h in gathered["identifiers"].get("hits", [])])

            if actionable:
                goal = JUDGEMENT_GOAL.format(
                    profile=json.dumps(profile, indent=2),
                    risk=gathered["risk"].get("overall_score"),
                    level=gathered["risk"].get("risk_level"),
                    exposures=json.dumps(actionable, indent=2),
                )
                summary = (_run_llm(ctx, phase_tools, goal, stream) if mode == "anthropic"
                           else openai_compat_planner.run(
                               ctx, phase_tools, JUDGEMENT_SYSTEM, goal, stream))
            else:
                goal = NO_EXPOSURES_GOAL.format(
                    profile=json.dumps(profile, indent=2),
                    risk=gathered["risk"].get("overall_score"),
                    level=gathered["risk"].get("risk_level"),
                )
                summary = (_run_llm(ctx, {}, goal, stream) if mode == "anthropic"
                           else openai_compat_planner.run(
                               ctx, {}, NO_EXPOSURES_SYSTEM, goal, stream))
        else:
            summary = _run_deterministic_discovery(ctx, tools)
    except Exception as exc:                                   # demo must not hard-fail
        error = _explain(exc, mode)
        ctx.emit("orchestrator", "error",
                 f"LLM planner unavailable — {error}. Falling back to the deterministic "
                 f"pipeline over the same tools.", status="error")
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
        if mode in ("anthropic", "openai_compat"):
            goal = REMEDIATION_GOAL.format(request_ids=", ".join(request_ids))
            REMEDIATION_TOOLS = ("submit_erasure_request", "check_request_status",
                                 "verify_removal", "escalate_to_regulator")
            phase_tools = {k: v for k, v in tools.items() if k in REMEDIATION_TOOLS}
            summary = (_run_llm(ctx, phase_tools, goal, stream) if mode == "anthropic"
                       else openai_compat_planner.run(ctx, phase_tools, SYSTEM, goal, stream))
        else:
            summary = _run_deterministic_remediation(ctx, tools, request_ids)
    except Exception as exc:
        error = _explain(exc, mode)
        ctx.emit("orchestrator", "error",
                 f"LLM planner unavailable — {error}. Falling back to the deterministic "
                 f"pipeline over the same tools.", status="error")
        summary = _run_deterministic_remediation(ctx, tools, request_ids)
        mode = "deterministic_fallback"

    assessment = tools["assess_exposure_risk"]()
    memory.finish_run(ctx.run_id, risk_before, assessment["overall_score"], summary)
    stream.put({"type": "run_complete", "run_id": ctx.run_id, "summary": summary,
                "risk_before": risk_before, "risk_after": assessment["overall_score"]})
    stream.close()
    return RunResult(ctx.run_id, ctx.user_id, mode, summary, stream.events, error)
