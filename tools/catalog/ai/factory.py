from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_AI_DIR = Path(__file__).resolve().parent
_CATALOG_DIR = _AI_DIR.parent
sys.path.insert(0, str(_CATALOG_DIR))
sys.path.insert(0, str(_AI_DIR))

import config
import aws as aws_provider
import nvidia as nvidia_provider
import openrouter as openrouter_provider
import perplexity as perplexity_provider

# Providers / models that search the web themselves (no local DuckDuckGo).
_WEB_CAPABLE = {"perplexity"}


def get_ai_client() -> Any:
    provider = config.AI_PROVIDER
    if provider == "nvidia":
        return nvidia_provider.build(
            base_url=config.NVIDIA_BASE_URL,
            api_key=config.NVIDIA_API_KEY,
            model=config.NVIDIA_MODEL,
        )
    if provider == "openrouter":
        return openrouter_provider.build(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.OPENROUTER_API_KEY,
            model=config.OPENROUTER_MODEL,
        )
    if provider == "aws":
        return aws_provider.build(
            region=config.AWS_REGION,
            model_id=config.AWS_BEDROCK_MODEL_ID,
            access_key=config.AWS_ACCESS_KEY_ID,
            secret_key=config.AWS_SECRET_ACCESS_KEY,
        )
    if provider == "perplexity":
        return perplexity_provider.build(
            base_url=config.PERPLEXITY_BASE_URL,
            api_key=config.PERPLEXITY_API_KEY,
            model=config.PERPLEXITY_MODEL,
        )
    raise SystemExit(
        f"Unknown AI_PROVIDER={provider!r} (use nvidia|openrouter|aws|perplexity)"
    )


def get_enrich_ai_client() -> Any:
    """LLM used for catalog enrich — must browse/search the web itself."""
    provider = config.ENRICH_AI_PROVIDER or "perplexity"
    if provider not in _WEB_CAPABLE and provider != "openrouter":
        raise SystemExit(
            "Enrich needs an LLM with internet access. "
            "Set ENRICH_AI_PROVIDER=perplexity (and PERPLEXITY_API_KEY), "
            "or ENRICH_AI_PROVIDER=openrouter with OPENROUTER_MODEL=perplexity/sonar-pro"
        )
    if provider == "perplexity":
        return perplexity_provider.build(
            base_url=config.PERPLEXITY_BASE_URL,
            api_key=config.PERPLEXITY_API_KEY,
            model=config.PERPLEXITY_MODEL,
        )
    # openrouter: use sonar (or whatever OPENROUTER_MODEL / ENRICH_OPENROUTER_MODEL is)
    model = config.ENRICH_OPENROUTER_MODEL or config.OPENROUTER_MODEL
    if "sonar" not in model.lower() and "perplexity" not in model.lower():
        print(
            f"Warning: OpenRouter model {model!r} may not have live web search; "
            "prefer perplexity/sonar-pro"
        )
    return openrouter_provider.build(
        base_url=config.OPENROUTER_BASE_URL,
        api_key=config.OPENROUTER_API_KEY,
        model=model,
    )
