from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        """Generate a text response from the LLM."""


def get_llm_provider(provider_name: str = "anthropic") -> LLMProvider:
    if provider_name == "anthropic":
        from app.services.llm.anthropic import AnthropicLLM

        return AnthropicLLM()
    elif provider_name == "gemini":
        from app.services.llm.gemini import GeminiLLM

        return GeminiLLM()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
