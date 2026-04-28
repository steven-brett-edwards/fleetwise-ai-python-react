"""Header-mapping stage: messy CSV header set -> canonical field names.

The cache key is the lowercased, sorted header set (a ``frozenset``-style
fingerprint serialized as a sorted-tuple JSON key). On a hit we skip the
LLM entirely; on a miss we ask the chat model for a structured mapping
and persist the result, so re-ingesting the same file shapes is free.

Two design choices worth flagging:

1. We always include the canonical synonyms cheaply via :func:`_seed_known`
   before reaching for the LLM. Identical-name and case-insensitive matches
   resolve without paying an API call.
2. The LLM call returns a ``HeaderMappingResult`` validated by Pydantic via
   ``with_structured_output``. If the provider returns junk that can't be
   parsed, we fall back to a "drop everything we don't already know"
   behavior so the pipeline still produces *some* output (the load stage
   will then reject any row that's missing required fields with a clear
   reason). Better to surface "this provider's structured-output broke" as
   a per-row rejection than to crash the whole ingest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fleetwise.ai.providers import build_chat_model
from fleetwise.etl.schema import (
    CANONICAL_HEADERS,
    HEADER_DESCRIPTIONS,
    HeaderMapping,
    HeaderMappingResult,
)
from fleetwise.settings import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


def _cache_path(settings: Settings | None = None) -> Path:
    s = settings or get_settings()
    return Path(s.etl_cache_dir) / "header-mappings.json"


def _fingerprint(headers: list[str]) -> str:
    """Stable cache key for a header set. Lowercase + sort -> JSON list."""
    return json.dumps(sorted(h.strip().lower() for h in headers))


def _load_cache(path: Path) -> dict[str, dict[str, str | None]]:
    if not path.exists():
        return {}
    try:
        return cast(dict[str, dict[str, str | None]], json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError):
        # Corrupt cache shouldn't tank the pipeline; rebuild on next miss.
        return {}


def _save_cache(path: Path, cache: dict[str, dict[str, str | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _seed_known(headers: list[str]) -> dict[str, str | None]:
    """Free wins -- exact (case-insensitive) matches against canonical names."""
    canonical_lower = {c.lower(): c for c in CANONICAL_HEADERS}
    return {h: canonical_lower.get(h.strip().lower()) for h in headers}


def _build_prompt(headers: list[str]) -> str:
    canon_block = "\n".join(f"  - {h}: {HEADER_DESCRIPTIONS[h]}" for h in CANONICAL_HEADERS)
    headers_block = "\n".join(f"  - {h!r}" for h in headers)
    return (
        "You map messy CSV headers from vehicle-inspection files to a fixed "
        "vocabulary of canonical field names.\n\n"
        f"Canonical fields:\n{canon_block}\n\n"
        f"CSV headers to map:\n{headers_block}\n\n"
        "For each CSV header, return the canonical field that best describes "
        "the column's contents, or null if no canonical field fits. A header "
        'like "Tech" maps to "inspector_name". A header like "Followup" or '
        '"Action Items" maps to "recommendations". A header like "Result" or '
        '"Outcome" maps to "passed". Do not invent canonical names that '
        "are not in the list above."
    )


def map_headers(
    headers: list[str],
    *,
    settings: Settings | None = None,
    model: BaseChatModel | None = None,
) -> dict[str, str | None]:
    """Return a ``{csv_header: canonical_name_or_none}`` mapping for ``headers``.

    Cache-first. Ask the LLM only for the unmatched remainder, then merge.
    Persists the merged result so subsequent calls with the same header set
    skip the network.
    """
    settings = settings or get_settings()
    seeded = _seed_known(headers)

    # If the cheap path resolved every column, nothing to do.
    unknowns = [h for h, mapped in seeded.items() if mapped is None]
    if not unknowns:
        return seeded

    cache_path = _cache_path(settings)
    cache = _load_cache(cache_path)
    fingerprint = _fingerprint(headers)
    cached = cache.get(fingerprint)
    if cached is not None:
        # The cached mapping is keyed on lowercase headers; rehydrate to
        # the original casing the caller passed in.
        return {h: cached.get(h.strip().lower()) for h in headers}

    # `build_chat_model` is inside the try because a misconfigured provider
    # (e.g. AI_PROVIDER=anthropic with ANTHROPIC_API_KEY unset on CI) raises
    # at construction time, not at invoke time. The mapper's contract is
    # "best-effort -- fall back to seeded-only on any provider trouble,"
    # which includes config trouble. The pipeline will surface unmapped
    # headers as per-row rejections, which is more actionable than "the
    # whole ingest crashed."
    try:
        chat = model if model is not None else build_chat_model(settings)
        structured = chat.with_structured_output(HeaderMappingResult)
        result = structured.invoke(_build_prompt(headers))
    except Exception:
        return seeded

    # Pydantic structured output gives us HeaderMappingResult. Some providers
    # return a bare dict, and mypy can't narrow the wide return type either
    # way -- always re-validate so the downstream type is concrete.
    parsed = (
        HeaderMappingResult.model_validate(result)
        if not isinstance(result, HeaderMappingResult)
        else result
    )
    by_source: dict[str, HeaderMapping] = {m.source: m for m in parsed.mappings}

    merged: dict[str, str | None] = dict(seeded)
    for h in headers:
        if merged[h] is not None:
            continue
        suggestion = by_source.get(h)
        if suggestion is not None and suggestion.canonical is not None:
            merged[h] = suggestion.canonical

    # Persist a lower-cased view so cache hits work regardless of header
    # casing in subsequent files.
    cache[fingerprint] = {h.strip().lower(): merged[h] for h in headers}
    _save_cache(cache_path, cache)

    return merged
