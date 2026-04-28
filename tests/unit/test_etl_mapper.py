"""Header-mapping tests with a fake structured-output chat model.

The mapper has three layers we need to cover:

1. The cheap path (case-insensitive exact matches against canonical
   names) resolves without touching the LLM.
2. The cache layer persists results across calls and rehydrates by
   header fingerprint.
3. The LLM-call layer uses ``with_structured_output`` and merges the
   suggested mappings with the seeded ones.

We use a minimal ``BaseChatModel`` subclass that returns a scripted
``HeaderMappingResult`` so tests don't need a live provider key and
stay deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from fleetwise.etl.mapper import map_headers
from fleetwise.etl.schema import HeaderMapping, HeaderMappingResult
from fleetwise.settings import Settings


def _settings_with_cache_dir(tmp_path: Path) -> Settings:
    """Override the cache directory so each test starts from a clean slate."""
    return Settings(etl_cache_dir=str(tmp_path))


def _scripted_chat_model(mappings: list[HeaderMapping]) -> MagicMock:
    """Fake chat model whose ``.with_structured_output(...).invoke(...)`` returns ``mappings``."""
    structured = MagicMock()
    structured.invoke.return_value = HeaderMappingResult(mappings=mappings)
    chat = MagicMock()
    chat.with_structured_output.return_value = structured
    return chat


# ── cheap path ─────────────────────────────────────────────────────────


def test_map_headers_resolves_canonical_names_without_llm(tmp_path: Path) -> None:
    """All headers are canonical -> no LLM call, no cache write."""
    chat = _scripted_chat_model([])  # would explode if invoked
    headers = ["asset_number", "inspected_at", "inspector_name", "passed", "findings"]

    out = map_headers(headers, settings=_settings_with_cache_dir(tmp_path), model=chat)

    assert out == {h: h for h in headers}
    chat.with_structured_output.assert_not_called()


def test_map_headers_matches_canonical_case_insensitively(tmp_path: Path) -> None:
    """``Asset_Number`` and ``ASSET_NUMBER`` should both resolve to ``asset_number``."""
    chat = _scripted_chat_model([])
    headers = ["Asset_Number", "INSPECTED_AT", "Inspector_Name", "Passed", "Findings"]

    out = map_headers(headers, settings=_settings_with_cache_dir(tmp_path), model=chat)

    assert out == {
        "Asset_Number": "asset_number",
        "INSPECTED_AT": "inspected_at",
        "Inspector_Name": "inspector_name",
        "Passed": "passed",
        "Findings": "findings",
    }


# ── LLM merge ──────────────────────────────────────────────────────────


def test_map_headers_calls_llm_for_unknown_headers_and_merges(tmp_path: Path) -> None:
    chat = _scripted_chat_model(
        [
            HeaderMapping(source="Vehicle ID", canonical="asset_number"),
            HeaderMapping(source="Tech", canonical="inspector_name"),
            HeaderMapping(source="Result", canonical="passed"),
            HeaderMapping(source="Followup", canonical="recommendations"),
        ]
    )
    headers = ["Vehicle ID", "Inspection Date", "Tech", "Result", "Notes", "Followup"]

    out = map_headers(headers, settings=_settings_with_cache_dir(tmp_path), model=chat)

    assert out["Vehicle ID"] == "asset_number"
    assert out["Tech"] == "inspector_name"
    assert out["Result"] == "passed"
    assert out["Followup"] == "recommendations"
    # Unmapped header passes through as None.
    assert out["Notes"] is None
    chat.with_structured_output.assert_called_once()


def test_map_headers_swallows_provider_failure(tmp_path: Path) -> None:
    """If the provider's structured-output call raises, we fall back to seeded only."""
    structured = MagicMock()
    structured.invoke.side_effect = RuntimeError("network down")
    chat = MagicMock()
    chat.with_structured_output.return_value = structured

    headers = ["asset_number", "Tech"]
    out = map_headers(headers, settings=_settings_with_cache_dir(tmp_path), model=chat)

    # Canonical resolves; the unknown stays None rather than crashing.
    assert out == {"asset_number": "asset_number", "Tech": None}


# ── cache ──────────────────────────────────────────────────────────────


def test_map_headers_caches_llm_result_to_disk(tmp_path: Path) -> None:
    chat = _scripted_chat_model([HeaderMapping(source="Tech", canonical="inspector_name")])
    headers = ["asset_number", "inspected_at", "Tech", "passed", "findings"]
    settings = _settings_with_cache_dir(tmp_path)

    map_headers(headers, settings=settings, model=chat)

    cache_file = tmp_path / "header-mappings.json"
    assert cache_file.exists()
    cache: dict[str, Any] = json.loads(cache_file.read_text())
    # One fingerprint, with the LLM's mapping merged into the seeded ones.
    assert len(cache) == 1
    [entry] = cache.values()
    assert entry["tech"] == "inspector_name"


def test_map_headers_skips_llm_on_cache_hit(tmp_path: Path) -> None:
    """Second call with the same header set should not touch the chat model."""
    settings = _settings_with_cache_dir(tmp_path)
    headers = ["asset_number", "inspected_at", "Tech", "passed", "findings"]

    # Prime the cache via a real call.
    chat1 = _scripted_chat_model([HeaderMapping(source="Tech", canonical="inspector_name")])
    map_headers(headers, settings=settings, model=chat1)
    assert chat1.with_structured_output.call_count == 1

    # Second call: a fresh chat model that would explode if invoked.
    chat2 = _scripted_chat_model([])
    out = map_headers(headers, settings=settings, model=chat2)

    chat2.with_structured_output.assert_not_called()
    assert out["Tech"] == "inspector_name"
