import logging
from typing import TypeVar

from pydantic import BaseModel

from app.agents.llm.models import LLMConfig, LLMResponse
from app.agents.llm.providers import BaseLLMProvider, MockLLMProvider, OpenAILikeProvider

logger = logging.getLogger("meco.agents.llm.client")

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Provider-independent facade for LLM interaction with graceful degradation,
    secret redaction, cost tracking, and structured output parsing.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._provider_instance = self._build_provider(self.config)

    def _build_provider(self, config: LLMConfig) -> BaseLLMProvider:
        prov = (config.provider or "mock").lower()
        if prov in ("mock", "none", "disabled") or not config.api_key:
            return MockLLMProvider(config)
        return OpenAILikeProvider(config)

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        prompt_version: str,
        model_override: str | None = None,
    ) -> LLMResponse[T]:
        """
        Execute structured generation with graceful degradation to MockLLMProvider
        if external calls fail.
        """
        try:
            resp = await self._provider_instance.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=response_schema,
                prompt_version=prompt_version,
                model_override=model_override,
            )

            # If external call had an error and fallback is needed
            if resp.error and not isinstance(self._provider_instance, MockLLMProvider):
                logger.warning(
                    f"External LLM failed ({resp.error}). Gracefully degrading to heuristic mock provider."
                )
                mock_provider = MockLLMProvider(self.config)
                fallback_resp = await mock_provider.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    prompt_version=prompt_version,
                    model_override=model_override,
                )
                fallback_resp.error = f"Degraded fallback after: {resp.error}"
                return fallback_resp

            return resp

        except Exception as exc:
            logger.error(f"Unexpected error in LLMClient: {exc}. Gracefully falling back.")
            mock_provider = MockLLMProvider(self.config)
            fallback_resp = await mock_provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_schema=response_schema,
                prompt_version=prompt_version,
                model_override=model_override,
            )
            fallback_resp.error = f"Degraded fallback after exception: {str(exc)}"
            return fallback_resp
