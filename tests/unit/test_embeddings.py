"""Unit tests for the embedding-provider factory.

Lazy imports mean we can assert the return class + configuration without
touching a network socket; the providers raise only when their first
embed call is made.
"""

from __future__ import annotations

import pytest
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings

from fleetwise.ai.embeddings import build_embeddings
from fleetwise.settings import Settings


def _settings(**overrides: object) -> Settings:
    # Use `model_construct` so the test env's real `.env` can't leak keys
    # into these checks -- only the overrides matter.
    base = Settings.model_construct(
        embedding_provider="auto",
        openai_api_key=None,
        openai_embedding_model="text-embedding-3-small",
        ollama_endpoint="http://localhost:11434",
        ollama_embedding_model="nomic-embed-text",
    )
    return base.model_copy(update=overrides)


def test_disabled_returns_none() -> None:
    assert build_embeddings(_settings(embedding_provider="disabled")) is None


def test_auto_prefers_openai_when_key_present() -> None:
    emb = build_embeddings(_settings(openai_api_key="sk-test"))
    assert isinstance(emb, OpenAIEmbeddings)


def test_auto_falls_back_to_ollama_without_openai_key() -> None:
    emb = build_embeddings(_settings(openai_api_key=None))
    assert isinstance(emb, OllamaEmbeddings)


def test_explicit_openai_without_key_raises() -> None:
    # Explicit providers don't silently downgrade -- the operator asked
    # for OpenAI and deserves a clear error when the key is missing.
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_embeddings(_settings(embedding_provider="openai", openai_api_key=None))


def test_explicit_ollama_returns_ollama() -> None:
    emb = build_embeddings(_settings(embedding_provider="ollama"))
    assert isinstance(emb, OllamaEmbeddings)
