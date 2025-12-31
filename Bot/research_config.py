import os


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse boolean-ish env vars."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Default research behavior
DEFAULT_RESEARCH_SOURCE = os.getenv("DEFAULT_RESEARCH_SOURCE", "perplexity").strip().lower()
ENABLE_PERPLEXITY = _env_bool("ENABLE_PERPLEXITY", True)

# Optional providers
ENABLE_SERPER = _env_bool("ENABLE_SERPER", False)
ENABLE_BRIGHT_DATA = _env_bool("ENABLE_BRIGHT_DATA", False)
ENABLE_ASKNEWS = _env_bool("ENABLE_ASKNEWS", False)

# Fallback handling
FALLBACK_TO_PERPLEXITY = _env_bool("FALLBACK_TO_PERPLEXITY", True)

# Perplexity usage budget (total calls per run). Should be even; pairs are split historical/current.
PERPLEXITY_CALL_LIMIT = int(os.getenv("PERPLEXITY_CALL_LIMIT", "2"))


def prefer_perplexity() -> bool:
    """Whether we should treat Perplexity deep research as the primary source."""
    return DEFAULT_RESEARCH_SOURCE == "perplexity" and ENABLE_PERPLEXITY
