"""AWS Bedrock chat via boto3 (optional dependency)."""
from __future__ import annotations

import json
import re
from typing import Any


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("AI response did not contain JSON object")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("AI JSON root must be an object")
    return data


class BedrockClient:
    def __init__(
        self,
        *,
        region: str,
        model_id: str,
        access_key: str,
        secret_key: str,
    ) -> None:
        self._region = region
        self._model_id = model_id
        self._access_key = access_key
        self._secret_key = secret_key

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        try:
            import boto3
        except ImportError as exc:
            raise SystemExit("Install boto3 for AI_PROVIDER=aws: pip install boto3") from exc
        if not self._model_id:
            raise SystemExit("Set AWS_BEDROCK_MODEL_ID")
        client = boto3.client(
            "bedrock-runtime",
            region_name=self._region,
            aws_access_key_id=self._access_key or None,
            aws_secret_access_key=self._secret_key or None,
        )
        response = client.converse(
            modelId=self._model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": f"{system}\n\n{user}"}],
                }
            ],
            inferenceConfig={"temperature": 0.2, "maxTokens": 2048},
        )
        parts = response["output"]["message"]["content"]
        text = "".join(part.get("text", "") for part in parts)
        return _extract_json_object(text)


def build(
    *,
    region: str,
    model_id: str,
    access_key: str,
    secret_key: str,
) -> BedrockClient:
    return BedrockClient(
        region=region,
        model_id=model_id,
        access_key=access_key,
        secret_key=secret_key,
    )
