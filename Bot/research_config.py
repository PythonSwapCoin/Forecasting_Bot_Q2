import os
from functools import lru_cache
from typing import Dict
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse boolean-ish env vars."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Default research behavior
DEFAULT_RESEARCH_SOURCE = os.getenv("DEFAULT_RESEARCH_SOURCE", "perplexity").strip().lower()
ENABLE_PERPLEXITY = _env_bool("ENABLE_PERPLEXITY", True)

# Provider keys
SERPER_KEY = os.getenv("SERPER_KEY")
ASKNEWS_CLIENT_ID = os.getenv("ASKNEWS_CLIENT_ID")
ASKNEWS_SECRET = os.getenv("ASKNEWS_SECRET")
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
METACULUS_TOKEN = os.getenv("METACULUS_TOKEN")

# Optional providers
ENABLE_SERPER = _env_bool("ENABLE_SERPER", bool(SERPER_KEY))
ENABLE_BRIGHT_DATA = _env_bool("ENABLE_BRIGHT_DATA", bool(BRIGHT_DATA_API_KEY))
ENABLE_ASKNEWS = _env_bool("ENABLE_ASKNEWS", bool(ASKNEWS_CLIENT_ID and ASKNEWS_SECRET))

# Fallback handling
FALLBACK_TO_PERPLEXITY = _env_bool("FALLBACK_TO_PERPLEXITY", True)

# Perplexity usage budget (total calls per run). Should be even; pairs are split historical/current.
PERPLEXITY_CALL_LIMIT = int(os.getenv("PERPLEXITY_CALL_LIMIT", "2"))

# Provider env vars
_PROVIDER_ENV_VARS = {
    "openrouter": "OPENROUTER_API_KEY",
    "perplexity": "OPENROUTER_API_KEY",  # routed via OpenRouter
    "serper": "SERPER_KEY",
    "asknews": "ASKNEWS_CLIENT_ID",
    "metaculus": "METACULUS_TOKEN",
    "bright_data": "BRIGHT_DATA_API_KEY",
}


@lru_cache(maxsize=1)
def get_research_provider_status() -> Dict[str, dict]:
    """
    Return a structured view of provider availability and config flags.

    Keys:
      - enabled: flag from config
      - has_key: env var present
      - reason: short status string (empty when healthy)
    """
    status = {}
    for name, env_var in _PROVIDER_ENV_VARS.items():
        has_key = bool(os.getenv(env_var))
        status[name] = {
            "enabled": False,
            "has_key": has_key,
            "reason": "",
        }

    status["perplexity"]["enabled"] = ENABLE_PERPLEXITY
    status["perplexity"]["reason"] = "" if (ENABLE_PERPLEXITY and status["perplexity"]["has_key"]) else "disabled or missing key"

    status["openrouter"]["enabled"] = bool(OPENROUTER_API_KEY)
    status["openrouter"]["reason"] = "" if status["openrouter"]["enabled"] else "missing OPENROUTER_API_KEY"

    status["serper"]["enabled"] = ENABLE_SERPER
    status["serper"]["reason"] = "" if (ENABLE_SERPER and status["serper"]["has_key"]) else "disabled or missing SERPER_KEY"

    status["asknews"]["enabled"] = ENABLE_ASKNEWS
    status["asknews"]["reason"] = "" if (ENABLE_ASKNEWS and status["asknews"]["has_key"]) else "disabled or missing ASKNEWS creds"

    status["bright_data"]["enabled"] = ENABLE_BRIGHT_DATA
    status["bright_data"]["reason"] = "" if (ENABLE_BRIGHT_DATA and status["bright_data"]["has_key"]) else "disabled or missing BRIGHT_DATA_API_KEY"

    status["metaculus"]["enabled"] = bool(METACULUS_TOKEN)
    status["metaculus"]["reason"] = "" if status["metaculus"]["enabled"] else "missing METACULUS_TOKEN"

    return status


def get_research_flags() -> Dict[str, bool]:
    """Expose current research toggles for logging/metadata."""
    return {
        "DEFAULT_RESEARCH_SOURCE": DEFAULT_RESEARCH_SOURCE,
        "ENABLE_PERPLEXITY": ENABLE_PERPLEXITY,
        "ENABLE_SERPER": ENABLE_SERPER,
        "ENABLE_BRIGHT_DATA": ENABLE_BRIGHT_DATA,
        "ENABLE_ASKNEWS": ENABLE_ASKNEWS,
        "FALLBACK_TO_PERPLEXITY": FALLBACK_TO_PERPLEXITY,
        "PERPLEXITY_CALL_LIMIT": PERPLEXITY_CALL_LIMIT,
    }


def prefer_perplexity() -> bool:
    """Whether we should treat Perplexity deep research as the primary source."""
    return DEFAULT_RESEARCH_SOURCE == "perplexity" and ENABLE_PERPLEXITY
