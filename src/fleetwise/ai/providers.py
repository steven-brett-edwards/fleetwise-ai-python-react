"""Chat-model factory.

One place where `settings.ai_provider` turns into a concrete
`BaseChatModel`. Provider SDKs are imported lazily so the test suite
doesn't have to have every provider's optional deps on the happy path.

Embeddings live in a sibling `embeddings.py` in Phase 5 -- same shape.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from fleetwise.settings import Settings


def build_chat_model(settings: Settings) -> BaseChatModel:
    """Return the configured chat model, constructed lazily per call."""
    match settings.ai_provider:
        case "anthropic":
            from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

            if not settings.anthropic_api_key:
                raise RuntimeError(
                    "AI_PROVIDER=anthropic but ANTHROPIC_API_KEY is unset. "
                    "Set the key in .env or switch AI_PROVIDER."
                )
            return ChatAnthropic(
                model_name=settings.anthropic_chat_model,
                api_key=settings.anthropic_api_key,  # type: ignore[arg-type]
                timeout=None,
                stop=None,
            )
        case "openai":
            from langchain_openai import ChatOpenAI  # noqa: PLC0415

            if not settings.openai_api_key:
                raise RuntimeError(
                    "AI_PROVIDER=openai but OPENAI_API_KEY is unset. "
                    "Set the key in .env or switch AI_PROVIDER."
                )
            return ChatOpenAI(
                model=settings.openai_chat_model,
                api_key=settings.openai_api_key,  # type: ignore[arg-type]
            )
        case "ollama":
            from langchain_ollama import ChatOllama  # noqa: PLC0415

            return ChatOllama(
                model=settings.ollama_chat_model,
                base_url=settings.ollama_endpoint,
            )
