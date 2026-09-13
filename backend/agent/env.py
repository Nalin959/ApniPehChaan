"""
env.py — Load API keys from a .env file at startup.

Why this exists: the agent's LLM planner and the HIBP breach check both switch on
purely by the presence of an environment variable. Requiring the user to export
them in every shell is a reliable way to demo the wrong thing by accident — you
restart the server in a fresh terminal and silently drop back to the
deterministic planner without noticing.

So keys live in a gitignored .env at the project root and are loaded once at
import. Real environment variables always win, so `ANTHROPIC_API_KEY=... ./run_demo.sh`
still overrides the file.
"""

import os
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# Only these are read. A .env can hold anything; loading arbitrary keys out of a
# file into the process environment is a good way to shadow something important.
RECOGNISED = {
    "ANTHROPIC_API_KEY",    # enables the LLM planner
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_WORKSPACE_ID",  # org keys not scoped to a workspace need this
    "HIBP_API_KEY",         # enables real breach-membership checks
    "APNIPEHCHAAN_PLANNER", "SOVEREIGN_PLANNER",    # pin a planner: anthropic | <provider> | deterministic
    # OpenAI-compatible free providers — one adapter covers all of them.
    "GROQ_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL",
    "CEREBRAS_API_KEY", "GITHUB_TOKEN", "MISTRAL_API_KEY",
    "OPENROUTER_API_KEY", "TOGETHER_API_KEY", "OLLAMA_API_KEY",
    "OPENAI_COMPAT_PROVIDER", "OPENAI_COMPAT_MODEL",
    "APNIPEHCHAAN_MODEL", "SOVEREIGN_MODEL",
    "APNIPEHCHAAN_EFFORT", "SOVEREIGN_EFFORT",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM",
    # Supabase & Cloud Database
    "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL",
    "APNIPEHCHAAN_DB", "SOVEREIGN_DB",
}


def load_env(path: pathlib.Path = ENV_FILE) -> list[str]:
    """Load recognised keys from .env. Returns the names that were set."""
    if not path.is_file():
        return []

    loaded = []
    try:
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key not in RECOGNISED:
                continue
            value = value.strip().strip('"').strip("'")
            # A real environment variable always wins over the file.
            if value and not os.environ.get(key):
                os.environ[key] = value
                loaded.append(key)
    except OSError:
        return []
    return loaded


def status() -> dict:
    """What is configured, without ever revealing a value."""
    def mask(k):
        v = os.environ.get(k, "")
        return f"set ({v[:7]}…{v[-4:]})" if len(v) > 14 else ("set" if v else "not set")

    return {
        "env_file": str(ENV_FILE), "env_file_exists": ENV_FILE.is_file(),
        "ANTHROPIC_API_KEY": mask("ANTHROPIC_API_KEY"),
        "HIBP_API_KEY": mask("HIBP_API_KEY"),
        "ANTHROPIC_WORKSPACE_ID": mask("ANTHROPIC_WORKSPACE_ID"),
        "llm_planner": ("ENABLED" if (os.environ.get("ANTHROPIC_API_KEY")
                                      or os.environ.get("GROQ_API_KEY")
                                      or os.environ.get("CEREBRAS_API_KEY")
                                      or os.environ.get("GITHUB_TOKEN")
                                      or os.environ.get("MISTRAL_API_KEY")) else "disabled"),
        "breach_checks": "ENABLED" if os.environ.get("HIBP_API_KEY") else "disabled",
    }


loaded_keys = load_env()
