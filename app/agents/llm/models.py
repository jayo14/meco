from datetime import datetime, timezone
import os
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class LLMUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = Field(default_factory=lambda: os.getenv("MECO_LLM_PROVIDER", "mock"))
    model: str = Field(default_factory=lambda: os.getenv("MECO_LLM_MODEL", "gpt-4o-mini"))
    api_key: str | None = Field(default_factory=lambda: os.getenv("MECO_LLM_API_KEY"))
    api_base: str | None = Field(default_factory=lambda: os.getenv("MECO_LLM_API_BASE"))
    timeout_seconds: float = 20.0
    max_retries: int = 2
    temperature: float = 0.1
    max_tokens: int = 1500
    track_cost: bool = True


class LLMResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    parsed: T | None = None
    raw_text: str = ""
    usage: LLMUsage = Field(default_factory=LLMUsage)
    model: str = ""
    provider: str = ""
    prompt_version: str = ""
    duration_ms: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
