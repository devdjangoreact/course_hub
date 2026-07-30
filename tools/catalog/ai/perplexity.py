from __future__ import annotations

from openai_compat import OpenAiCompatibleClient


def build(*, base_url: str, api_key: str, model: str) -> OpenAiCompatibleClient:
    return OpenAiCompatibleClient(base_url=base_url, api_key=api_key, model=model)
