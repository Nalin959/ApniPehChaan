"""
openai_compat_planner.py — Any OpenAI-compatible provider as the agent's planner.

WHY ONE MODULE COVERS MANY PROVIDERS
------------------------------------
Groq, Cerebras, GitHub Models, Mistral, OpenRouter and Together all expose the
same `/chat/completions` surface with the same tool-calling shape. So rather
than an adapter each, this is one implementation plus a table of base URLs.
Switching provider is a line in .env, not a code change.

That matters for a hackathon: free tiers throttle, and being able to fail over
to a different provider in ten seconds is worth more than any single one of them.

As with every planner here, the TOOLS are untouched. All 20 functions in
tools.py run identically whichever provider chose the order.
"""

import inspect
import json
import os
import time
import typing

# base_url + a sensible free model for each. All are free-tier, no card needed
# (GitHub Models needs only a GitHub account).
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        # Default to OpenAI GPT-OSS on Groq for maximum statutory reasoning and compliance
        "default_model": "openai/gpt-oss-20b",
        "fallback_models": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"],
        "signup": "https://console.groq.com/keys",
        "note": "Fastest inference available free. Excellent for a live demo.",
    },
    # Google exposes Gemini through an OpenAI-compatible endpoint, so the same
    # adapter drives it. It is here because .env.example has always advertised
    # GEMINI_API_KEY while no provider existed to consume it: a key set in the
    # file was silently ignored and the run fell back to the deterministic
    # planner, with nothing saying why. A second free provider is also real
    # insurance — if one free tier is throttling during a demo, the other is
    # very unlikely to be throttling at the same moment.
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "default_model": "gemini-3.6-flash",
        "fallback_models": ["gemini-3.5-flash", "gemini-flash-latest"],
        "signup": "https://aistudio.google.com/apikey",
        "note": "Generous free tier; good fallback when another provider throttles.",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "key_env": "CEREBRAS_API_KEY",
        "default_model": "llama-3.3-70b",
        "signup": "https://cloud.cerebras.ai/",
        "note": "Comparable speed to Groq.",
    },
    "github": {
        "base_url": "https://models.github.ai/inference",
        "key_env": "GITHUB_TOKEN",
        "default_model": "openai/gpt-4.1-mini",
        "signup": "https://github.com/settings/tokens (needs models:read)",
        "note": "Frontier-class models free with a GitHub account; tight rate limits.",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "key_env": "MISTRAL_API_KEY",
        "default_model": "mistral-small-latest",
        "signup": "https://console.mistral.ai/api-keys/",
        "note": "Free experimental tier; solid tool use.",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "signup": "https://openrouter.ai/keys",
        "note": "Aggregator — many models, some free. Check the model supports tools.",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "key_env": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
        "signup": "https://api.together.ai/settings/api-keys",
        "note": "Free tier on selected models.",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "key_env": "OLLAMA_API_KEY",
        "default_model": "llama3.1:8b",
        "signup": "https://ollama.com (runs locally)",
        "note": "Entirely local and free, but small models sequence tools poorly.",
    },
}

# Free tiers cap TOKENS PER MINUTE far more tightly than requests — Groq allows
# 1000 requests/day but only 8000 tokens/minute. The planner resends the whole
# conversation on every call, so an un-trimmed tool result is paid for again on
# every subsequent step. Dumping 6000 characters of JSON per call exhausts the
# minute budget within a single run.
#
# So results are compacted before they enter the transcript: the model needs to
# know WHAT was found and the ids to act on, not every field of every record.
MAX_RESULT_CHARS = 700

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean",
               list: "array", dict: "object"}

# A discovery run that skipped these did not actually look for anything. Used to
# detect a model that summarised early rather than finishing the job.
# Tools whose absence means the phase did not really do its job. Checked only
# against the toolset actually supplied, so a focused phase is never nagged
# about a tool it was deliberately not given.
ESSENTIAL_TOOLS = (
    "build_identity_profile",
    "verify_breach_exposure",
    "assess_exposure_risk",
    "determine_legal_basis",
    "plan_removal",
)


def configured() -> str | None:
    """Which OpenAI-compatible provider has a key, if any."""
    pinned = (os.environ.get("OPENAI_COMPAT_PROVIDER") or os.environ.get("SOVEREIGN_PLANNER") or "").strip().lower()
    if pinned in PROVIDERS and os.environ.get(PROVIDERS[pinned]["key_env"]):
        return pinned
    for name, spec in PROVIDERS.items():
        if os.environ.get(spec["key_env"]):
            return name
    return None


def configured_all() -> list[str]:
    """
    Every provider with a key, best first.

    configured() returns only ONE. When that one is rate-limited — and a free
    tier is rate-limited often; Gemini's is twenty requests — anything built on
    configured() alone simply fails, even with a second working key sitting in
    the same .env. Callers that can retry should walk this list instead.
    """
    pinned = (os.environ.get("OPENAI_COMPAT_PROVIDER")
              or os.environ.get("SOVEREIGN_PLANNER") or "").strip().lower()
    names = [n for n in PROVIDERS if os.environ.get(PROVIDERS[n]["key_env"])]
    if pinned in names:
        names.remove(pinned)
        names.insert(0, pinned)
    return names


def available() -> bool:
    return configured() is not None


def model_for(provider: str) -> str:
    return (os.environ.get("OPENAI_COMPAT_MODEL")
            or PROVIDERS[provider]["default_model"])


def _schema_for(fn, brief: bool = False) -> dict:
    """
    Build an OpenAI tool schema from a Python function.

    The docstring becomes the description the model reasons over, so the
    docstrings in tools.py are load-bearing for every planner, not just this one.
    """
    sig = inspect.signature(fn)
    props, required = {}, []
    for name, param in sig.parameters.items():
        ann = param.annotation
        origin = typing.get_origin(ann) or ann
        props[name] = {"type": _JSON_TYPES.get(origin, "string"),
                       "description": f"{name} parameter"}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            # Every schema is resent on every round trip. A full docstring is
            # useful the first time and pure overhead on the fifteenth, so the
            # planner gets the first line — which is what states the tool's job.
            "description": _describe(fn, brief),
            "parameters": {"type": "object", "properties": props,
                           "required": required, "additionalProperties": False},
        },
    }


MAX_RESULT_CHARS = 300

def _compact(result) -> str:
    """
    Shrink a tool result to what the planner actually needs to decide the next step.

    Long free-text fields — legal reasoning, notice bodies, step lists — are the
    bulk of these payloads and the model does not need them verbatim to choose a
    tool. Ids, counts, verdicts, and methods do.
    """
    if not isinstance(result, dict):
        return json.dumps(result, default=str)[:MAX_RESULT_CHARS]

    DROP = {"request_text", "steps", "evidence", "excluded_sites", "sources",
            "checks_run", "recommendations", "why_this_method", "escalation",
            "reason", "note", "caveat", "disclaimer", "interpretation",
            "why_candidates", "improve_accuracy", "where_each_helps",
            "why_unique_matters", "domain_context", "directory_context",
            "how_collected", "description", "details"}

    def shrink(v, depth=0):
        if isinstance(v, dict):
            return {k: shrink(x, depth + 1) for k, x in v.items() if k not in DROP}
        if isinstance(v, list):
            # A long list tells the planner a count, not a catalogue.
            head = [shrink(x, depth + 1) for x in v[:4]]
            return head + [f"…and {len(v) - 4} more"] if len(v) > 4 else head
        if isinstance(v, str) and len(v) > 120:
            return v[:120] + "…"
        return v

    out = json.dumps(shrink(result), default=str)
    return out[:MAX_RESULT_CHARS] + ("…" if len(out) > MAX_RESULT_CHARS else "")


def _describe(fn, brief: bool) -> str:
    doc = (inspect.getdoc(fn) or fn.__name__).strip()
    if not brief:
        return doc[:1024]
    first = doc.split("\n\n")[0].replace("\n", " ")
    return " ".join(first.split())[:180]


def explain(exc: Exception) -> str:
    """One actionable line for why this planner could not run."""
    msg, low = str(exc), str(exc).lower()
    name = type(exc).__name__
    if "401" in msg or "unauthor" in low or "invalid api key" in low:
        return "that provider key was rejected — check it is pasted in full"
    if "429" in msg or "rate limit" in low or "quota" in low:
        return "the provider's free-tier rate limit was hit; wait a minute and retry"
    if "404" in msg or "model_not_found" in low or "does not exist" in low:
        return "that model name is not available on this provider — set OPENAI_COMPAT_MODEL"
    if "tool" in low and ("not supported" in low or "unsupported" in low):
        return "that model does not support tool calling — pick one that does"
    if name in ("APIConnectionError", "APITimeoutError"):
        return "could not reach the provider — check the network"
    return f"{name}: {msg.splitlines()[0][:120]}"


def run(ctx, tools: dict, system: str, goal: str, stream, max_steps: int = 25) -> str:
    """
    Drive the agent loop against an OpenAI-compatible provider.

    Raises on failure so the caller falls back to the deterministic pipeline —
    a throttled free tier must never take the product down with it.
    """
    from openai import OpenAI
    from backend.agent.memory import utcnow

    provider = configured()
    if not provider:
        raise RuntimeError("No OpenAI-compatible provider key configured.")
    spec = PROVIDERS[provider]
    model = model_for(provider)

    client = OpenAI(api_key=os.environ[spec["key_env"]], base_url=spec["base_url"])
    ctx.emit("orchestrator", "plan", f"Planning with {model} via {provider}…")

    # Brief schemas once the toolset is small and focused: the planner knows
    # what four tools do from one line each, and every schema is resent on
    # every round trip.
    brief = len(tools) <= 6
    schemas = [_schema_for(fn, brief) for fn in tools.values()]
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": goal}]
    final_text = ""
    called_tools: set = set()
    nudges = 0

    active_model = model
    fallback_pool = [m for m in PROVIDERS.get(provider, {}).get("fallback_models", []) if m != active_model]
    models_to_try = [active_model] + fallback_pool

    total_in = total_out = 0
    # Emitting several tool calls in one turn is what keeps the run inside a
    # free tier's per-minute token budget, but it is also what these models get
    # wrong: gpt-oss intermittently emits tool-call arguments that are not valid
    # JSON, and the provider rejects the whole request with a 400 rather than
    # the model's own mistake. Falling straight back to the deterministic
    # pipeline threw away the reasoning layer over a transient formatting slip,
    # so a parse failure now retries in series before it is treated as fatal.
    allow_parallel = True

    for _ in range(max_steps):
        resp = None
        for candidate in list(models_to_try):
            for attempt in range(3):
                try:
                    resp = client.chat.completions.create(
                        model=candidate, messages=messages, tools=schemas,
                        tool_choice="auto", temperature=0.2,
                        parallel_tool_calls=allow_parallel,
                    )
                    if candidate != active_model:
                        ctx.emit("orchestrator", "plan",
                                 f"Switched model to {candidate} to respect provider rate limits.")
                        active_model = candidate
                    break
                except Exception as exc:
                    err_text = str(exc).lower()
                    is_rate_limit = ("429" in str(exc) or "rate limit" in err_text
                                     or "quota" in err_text or "token" in err_text)
                    is_parse_fail = ("parsing failed" in err_text
                                     or "could not be parsed" in err_text
                                     or "failed to call a function" in err_text
                                     or "tool call validation failed" in err_text)

                    # A malformed tool call is the model's slip, not a dead end.
                    # One call per turn is the formulation it gets right most
                    # often, so drop to series and try the same model again.
                    if is_parse_fail and not is_rate_limit and attempt < 2:
                        if allow_parallel:
                            allow_parallel = False
                            ctx.emit("orchestrator", "plan",
                                     f"{candidate} returned a malformed tool call; retrying "
                                     f"one call at a time.")
                        else:
                            ctx.emit("orchestrator", "plan",
                                     f"{candidate} returned a malformed tool call; retrying.")
                        time.sleep(1.5 * (attempt + 1))
                        continue

                    if is_rate_limit and len(models_to_try) > 1 and candidate != models_to_try[-1]:
                        models_to_try.remove(candidate)
                        ctx.emit("orchestrator", "plan",
                                 f"Rate limit on {candidate}; failing over to {models_to_try[0]}…")
                        break

                    # A model that cannot produce a usable tool call after three
                    # tries is swapped out rather than taking the run down.
                    if is_parse_fail and len(models_to_try) > 1 and candidate != models_to_try[-1]:
                        models_to_try.remove(candidate)
                        ctx.emit("orchestrator", "plan",
                                 f"{candidate} kept returning malformed tool calls; "
                                 f"failing over to {models_to_try[0]}…")
                        break
                    raise exc
            if resp is not None:
                break

        if resp is None:
            break

        u = getattr(resp, "usage", None)
        if u:
            total_in += u.prompt_tokens or 0
            total_out += u.completion_tokens or 0
        msg = resp.choices[0].message

        # Narration between tool calls is the reasoning the judge actually sees.
        if msg.content and msg.content.strip():
            final_text = msg.content.strip()
            stream.put({"type": "agent_reasoning", "run_id": ctx.run_id,
                        "ts": utcnow(), "text": final_text})

        if not msg.tool_calls:
            # The model stopped. Some models summarise after two or three calls
            # and consider the job done, which silently skips most of discovery.
            # Rather than accept a half-finished run, name what has not been
            # done and ask it to continue. Only give up if it stops again.
            # Only chase tools the planner was actually GIVEN. The judgement
            # phase is handed four tools on purpose — gathering already ran
            # deterministically — so nagging it about build_identity_profile
            # made it apologise for not calling something it cannot see, and
            # wasted a round trip doing so.
            missing = [t for t in ESSENTIAL_TOOLS
                       if t in tools and t not in called_tools]
            has_exposures = ("Exposures to evaluate" in goal and "[]" not in goal
                             and "Exposures found: 0" not in goal)
            if missing and nudges < 1 and has_exposures:
                nudges += 1
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({
                    "role": "user",
                    "content": ("You have not finished. These required steps have not run "
                                f"yet: {', '.join(missing)}. Call them now, then continue "
                                "with the legal assessment and drafting before you summarise."),
                })
                continue
            break

        if hasattr(msg, "model_dump"):
            messages.append(msg.model_dump(exclude_unset=True))
        else:
            messages.append({
                "role": "assistant", "content": msg.content,
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.function.name,
                                             "arguments": c.function.arguments},
                                **({"extra_content": getattr(c, "extra_content", {})}
                                   if getattr(c, "extra_content", None) else {})}
                               for c in msg.tool_calls],
            })

        for call in msg.tool_calls:
            called_tools.add(call.function.name)
            if call.function.name == "plan_removal":
                called_tools.add("determine_legal_basis")
            fn = tools.get(call.function.name)
            if fn is None:
                result = {"error": f"unknown tool {call.function.name!r}"}
            else:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                try:
                    result = fn(**args)
                except Exception as exc:      # a tool failing must not end the run
                    result = {"error": f"{type(exc).__name__}: {exc}"}
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": _compact(result)})

    # Free tiers meter TOKENS PER MINUTE, so what a run costs in tokens is the
    # number that decides whether a provider can serve it — not request count.
    ctx.emit("orchestrator", "plan",
             f"Planner finished: {total_in:,} input + {total_out:,} output tokens "
             f"across {len(called_tools)} distinct tool(s).")
    if final_text:
        ctx.emit("orchestrator", "plan", "Executive Summary and Legal Assessment generated.")
    return final_text
