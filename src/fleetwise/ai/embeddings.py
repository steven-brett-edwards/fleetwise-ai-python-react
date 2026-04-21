"""Embedding-provider factory.

Anthropic has no embeddings endpoint -- same constraint the .NET
edition had with Groq -- so the embedding provider is configured
independently of the chat provider. `auto` is the friendly default:
prefer OpenAI if a key is available, fall back to Ollama's local
`nomic-embed-text`, and only disable RAG if neither is reachable.

A `None` return means RAG is cleanly disabled: the agent won't bind
the `search_fleet_documentation` tool and the system prompt drops the
documentation stanza. Lives in its own module because embeddings
need heavier imports than chat (`langchain-openai` / `langchain-ollama`)
and lazy imports keep the test-time import graph small.
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from fleetwise.settings import Settings


def build_embeddings(settings: Settings) -> Embeddings | None:
    """Return the configured embedding model, or None if RAG is disabled.

    The `auto` provider walks the preference list once; explicit settings
    (`openai` / `ollama`) raise if their config is missing so the operator
    isn't silently downgraded.
    """
    provider = settings.embedding_provider

    if provider == "disabled":
        return None

    if provider == "auto":
        if settings.openai_api_key:
            return _openai(settings)
        # Ollama runs locally; there's no key to check. Assume reachable
        # and let the first embed() raise if it isn't -- better feedback
        # than a silent RAG-disabled state.
        return _ollama(settings)

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is unset. "
                "Set the key in .env or switch EMBEDDING_PROVIDER."
            )
        return _openai(settings)

    if provider == "ollama":
        return _ollama(settings)

    # Unreachable under Literal typing, but keeps the function exhaustive
    # if the literal is widened later.
    raise ValueError(f"Unknown embedding_provider: {provider}")  # pragma: no cover


def _openai(settings: Settings) -> Embeddings:
    from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,  # type: ignore[arg-type]
    )


def _ollama(settings: Settings) -> Embeddings:
    from langchain_ollama import OllamaEmbeddings  # noqa: PLC0415

    return OllamaEmbeddings(
        model=settings.ollama_embedding_model,
        base_url=settings.ollama_endpoint,
    )
