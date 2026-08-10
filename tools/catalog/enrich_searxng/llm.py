"""Pluggable LLM backends for catalog enrich (nvidia / openrouter / bedrock)."""

from __future__ import annotations

import json
import os
import time

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

import config

LLM_BACKEND = os.environ.get("LLM_BACKEND", "nvidia")  # bedrock | openrouter | nvidia
LLM_HTTP_PROXY = (os.environ.get("LLM_HTTP_PROXY") or "").strip()
LLM_USE_SESSION_PROXY = config.env_bool("LLM_USE_SESSION_PROXY", True)

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"
BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-1")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
)

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.environ.get(
    "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
)
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "z-ai/glm-5.2")

LLM_MAX_TOKENS = 4096
LLM_HTTP_TIMEOUT = float(os.environ.get("LLM_HTTP_TIMEOUT", "300"))
LLM_RETRIES = int(os.environ.get("LLM_RETRIES", "4"))

# Set after ProxyBrowserSession.open when LLM/SearXNG should share session proxy.
_ACTIVE_HTTP_PROXY: str | None = None


def set_active_http_proxy(proxy_url: str | None) -> None:
    global _ACTIVE_HTTP_PROXY
    _ACTIVE_HTTP_PROXY = (proxy_url or "").strip() or None


def requests_proxies() -> dict[str, str] | None:
    if not _ACTIVE_HTTP_PROXY:
        return None
    return {"http": _ACTIVE_HTTP_PROXY, "https": _ACTIVE_HTTP_PROXY}


def llm_proxy_url() -> str | None:
    if LLM_HTTP_PROXY:
        return LLM_HTTP_PROXY
    if LLM_USE_SESSION_PROXY:
        return _ACTIVE_HTTP_PROXY
    return None


def _httpx_timeout():
    import httpx

    # Long enrich JSON (25–30 sentences) needs a generous read window.
    return httpx.Timeout(
        LLM_HTTP_TIMEOUT,
        connect=min(30.0, LLM_HTTP_TIMEOUT),
        read=LLM_HTTP_TIMEOUT,
        write=min(60.0, LLM_HTTP_TIMEOUT),
        pool=min(30.0, LLM_HTTP_TIMEOUT),
    )


def _openai_client(*, base_url: str, api_key: str) -> OpenAI:
    proxy = llm_proxy_url()
    timeout = _httpx_timeout()
    if not proxy:
        return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    import httpx

    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        http_client=httpx.Client(proxy=proxy, timeout=timeout),
    )


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError, TimeoutError)):
        return True
    name = type(exc).__name__
    if name in {"ReadTimeout", "ConnectTimeout", "WriteTimeout", "PoolTimeout"}:
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in {408, 429, 500, 502, 503, 504}
    return False


def _with_retries(label: str, fn):
    last: BaseException | None = None
    for attempt in range(LLM_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — re-raise non-retryable below
            last = exc
            if not _is_retryable(exc) or attempt >= LLM_RETRIES:
                raise
            wait = min(2**attempt * 3, 60)
            code = getattr(exc, "status_code", None) or type(exc).__name__
            print(f"  llm {label} retryable ({code}); sleep {wait}s then retry")
            time.sleep(wait)
    assert last is not None
    raise last


def llm_text(system: str, user: str, *, max_tokens: int = LLM_MAX_TOKENS) -> str:
    """One chat completion via configured LLM_BACKEND; returns raw text."""
    if LLM_BACKEND == "bedrock":
        import boto3

        def _bedrock() -> str:
            client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            response = client.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(response["body"].read())
            return payload["content"][0]["text"]

        return _with_retries("bedrock", _bedrock)

    if LLM_BACKEND == "openrouter":

        def _openrouter() -> str:
            client = _openai_client(
                base_url=OPENROUTER_BASE_URL,
                api_key=os.environ["OPENROUTER_API_KEY"],
            )
            completion = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                max_tokens=max_tokens,
            )
            return completion.choices[0].message.content or ""

        return _with_retries("openrouter", _openrouter)

    if LLM_BACKEND == "nvidia":
        if not NVIDIA_API_KEY:
            raise RuntimeError("NVIDIA_API_KEY is missing (set it in .env)")

        def _nvidia() -> str:
            client = _openai_client(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)
            # Non-stream: long sales copy often times out mid-stream on NVIDIA.
            completion = client.chat.completions.create(
                model=NVIDIA_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                top_p=1,
                max_tokens=max_tokens,
                seed=42,
                stream=False,
            )
            return completion.choices[0].message.content or ""

        return _with_retries("nvidia", _nvidia)

    raise ValueError(f"Unknown LLM_BACKEND: {LLM_BACKEND!r}")
