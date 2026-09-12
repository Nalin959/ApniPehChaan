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
import typing

# base_url + a sensible free model for each. All are free-tier, no card needed
# (GitHub Models needs only a GitHub account).
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        # Measured on a live free key, single tool-calling round trip:
        #   openai/gpt-oss-120b  1.3s   <- default; largest, clean tool calls
        #   openai/gpt-oss-20b   0.5s   faster but smaller
        #   qwen/qwen3.x-27b     rejects a 20-tool schema as "request too large"
        "default_model": "openai/gpt-oss-120b",
        "signup": "https://console.groq.com/keys",
        "note": "Fastest inference available free. Excellent for a live demo.",
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
ESSENTIAL_TOOLS = (
    "build_identity_profile",
    "verify_breach_exposure",
    "assess_exposure_risk",
)


def configured() -> str | None:
    """Which OpenAI-compatible provider has a key, if any."""
    pinned = (os.environ.get("OPENAI_COMPAT_PROVIDER") or "").strip().lower()
    if pinned in PROVIDERS and os.environ.get(PROVIDERS[pinned]["key_env"]):
        return pinned
    for name, spec in PROVIDERS.items():
        if os.environ.get(spec["key_env"]):
            return name
    return None


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


def _compact(result) -> str:
    """
    Shrink a tool result to what the planner actually needs to decide the next step.

    Long free-text fields — legal reasoning, notice bodies, step lists — are the
    bulk of these payloads and the model does not need them verbatim to choose a
    tool. Ids, counts and verdicts do.
    """
    if not isinstance(result, dict):
        return json.dumps(result, default=str)[:MAX_RESULT_CHARS]

    DROP = {"request_text", "steps", "legal_basis", "legal_position", "evidence",
            "excluded_sites", "sources", "checks_run", "recommendations",
            "why_this_method", "escalation", "reason", "note", "caveat",
            "disclaimer", "method", "interpretation", "why_candidates",
            "improve_accuracy", "where_each_helps", "why_unique_matters",
            "domain_context", "directory_context"}

    def shrink(v, depth=0):
        if isinstance(v, dict):
            return {k: shrink(x, depth + 1) for k, x in v.items() if k not in DROP}
        if isinstance(v, list):
            # A long list tells the planner a count, not a catalogue.
            head = [shrink(x, depth + 1) for x in v[:4]]
            return head + [f"…and {len(v) - 4} more"] if len(v) > 4 else head
        if isinstance(v, str) and len(v) > 160:
            return v[:160] + "…"
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

    total_in = total_out = 0
    for _ in range(max_steps):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=schemas,
            tool_choice="auto", temperature=0.2,
            # Explicitly allow many tool calls per turn. One call per exposure
            # means the whole conversation is resent per exposure, which is what
            # exhausts a per-minute token budget; batching collapses ~16 round
            # trips into ~3.
            parallel_tool_calls=True,
        )
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
            missing = [t for t in ESSENTIAL_TOOLS if t not in called_tools]
            if missing and nudges < 1:
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

        messages.append({
            "role": "assistant", "content": msg.content,
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name,
                                         "arguments": c.function.arguments}}
                           for c in msg.tool_calls],
        })

        for call in msg.tool_calls:
            called_tools.add(call.function.name)
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
        ctx.emit("orchestrator", "reasoning", final_text)
    return final_text
