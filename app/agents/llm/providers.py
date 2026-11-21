from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.agents.llm.models import LLMConfig, LLMResponse, LLMUsage

logger = logging.getLogger("meco.agents.llm.providers")

T = TypeVar("T", bound=BaseModel)


def _redact_key(key: str | None) -> str:
    if not key:
        return "[NONE]"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


class BaseLLMProvider(ABC):
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        prompt_version: str,
        model_override: str | None = None,
    ) -> LLMResponse[T]:
        pass


class MockLLMProvider(BaseLLMProvider):
    """
    Offline/deterministic mock provider for testing, fallback, and zero-dependency runs.
    Inspects input and builds structured schema responses.
    """

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        prompt_version: str,
        model_override: str | None = None,
    ) -> LLMResponse[T]:
        start = time.perf_counter()
        model = model_override or self.config.model

        # Extract hints or keywords from user_prompt
        prompt_lower = user_prompt.lower()
        findings = []
        unanswered = []

        if "mint" in prompt_lower or "token" in prompt_lower:
            findings.append({
                "type": "verified_fact",
                "title": "Token Identity Verified",
                "statement": "Token parameters and metadata loaded from authoritative storage.",
                "confidence": 1.0,
                "evidence_sources": [
                    {
                        "source": "canonical_profile",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reference": "onchain_profile",
                        "details": {},
                    }
                ],
                "metadata": {},
            })

        if "liquidity" in prompt_lower:
            findings.append({
                "type": "statistical_observation",
                "title": "Liquidity Observation",
                "statement": "Liquidity metrics evaluated against baseline thresholds.",
                "confidence": 0.9,
                "evidence_sources": [
                    {
                        "source": "dexscreener_snapshot",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reference": "pair_observation",
                        "details": {},
                    }
                ],
                "metadata": {},
            })

        duration_ms = int((time.perf_counter() - start) * 1000)

        mock_payload: dict[str, Any] = {
            "summary": "Automated deterministic synthesis based on available profile and metrics.",
            "confidence": 0.85,
            "findings": findings,
            "unanswered_questions": unanswered,
            "inferences": ["Ecosystem metrics indicate standard DEX activity patterns."],
            "hypotheses": ["Token behavior may correlate with overall market trend."],
            "missing_information": [],
        }

        try:
            parsed = response_schema.model_validate(mock_payload)
        except Exception:
            # If the schema has different fields, create an empty instance or construct defaults
            try:
                parsed = response_schema()
            except Exception:
                parsed = None

        return LLMResponse[T](
            parsed=parsed,
            raw_text=json.dumps(mock_payload),
            usage=LLMUsage(prompt_tokens=120, completion_tokens=80, total_tokens=200, estimated_cost_usd=0.0001),
            model=f"mock-{model}",
            provider="mock",
            prompt_version=prompt_version,
            duration_ms=duration_ms,
        )


class OpenAILikeProvider(BaseLLMProvider):
    """
    Universal HTTP client for OpenAI-compatible LLM endpoints (OpenAI, OpenRouter, vLLM, Ollama, etc.).
    """

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self.base_url = (self.config.api_base or "https://api.openai.com/v1").rstrip("/")

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        prompt_version: str,
        model_override: str | None = None,
    ) -> LLMResponse[T]:
        start = time.perf_counter()
        model = model_override or self.config.model
        api_key = self.config.api_key

        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        schema_json = json.dumps(response_schema.model_json_schema())
        augmented_system_prompt = (
            f"{system_prompt}\n\n"
            f"You MUST format your entire response as a single valid JSON object strictly complying with this JSON Schema:\n"
            f"{schema_json}\n"
            f"Do not include any text before or after the JSON."
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": augmented_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
        }

        retries = 0
        backoff = 1.0
        last_error = None

        while retries <= self.config.max_retries:
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    raw_content = data["choices"][0]["message"]["content"]
                    usage_data = data.get("usage", {})
                    prompt_tokens = usage_data.get("prompt_tokens", 0)
                    completion_tokens = usage_data.get("completion_tokens", 0)
                    total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)

                    # Estimate cost: approx $0.15/1M input, $0.60/1M output for gpt-4o-mini
                    est_cost = (prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)

                    # Extract JSON if enclosed in markdown
                    json_text = raw_content.strip()
                    if json_text.startswith("```"):
                        json_match = re.search(r"```(?:json)?(.*?)```", json_text, re.DOTALL)
                        if json_match:
                            json_text = json_match.group(1).strip()

                    parsed_dict = json.loads(json_text)
                    parsed_obj = response_schema.model_validate(parsed_dict)

                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return LLMResponse[T](
                        parsed=parsed_obj,
                        raw_text=raw_content,
                        usage=LLMUsage(
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            estimated_cost_usd=est_cost,
                        ),
                        model=model,
                        provider=self.config.provider,
                        prompt_version=prompt_version,
                        duration_ms=duration_ms,
                    )

            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"LLM request error ({type(exc).__name__}) with key {_redact_key(api_key)}, "
                    f"attempt {retries + 1}/{self.config.max_retries + 1}: {exc}"
                )
                if retries < self.config.max_retries:
                    retries += 1
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue
                break

        duration_ms = int((time.perf_counter() - start) * 1000)
        return LLMResponse[T](
            parsed=None,
            raw_text="",
            error=f"{type(last_error).__name__}: {str(last_error)}",
            model=model,
            provider=self.config.provider,
            prompt_version=prompt_version,
            duration_ms=duration_ms,
        )
