"""Shared helpers for tool return strings.

The .NET plugins return a fixed two-part shape:

    <short prefatory line describing count / context>
    <indented JSON payload>

Matching that shape keeps the Claude tool-use loop grounded: the model
has learned (from the .NET transcripts we've been running) that the
prefatory line is where to look for counts. Don't drop it.

`json_dumps` handles the two types `json.dumps` refuses out of the box:
`Decimal` (serialized as a JSON number via `float`, same convention as
`domain.dto`) and `datetime` (serialized as ISO-8601).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def json_dumps(value: Any) -> str:
    """Indented JSON with Decimal + datetime support."""
    return json.dumps(value, indent=2, default=_default)


def format_list(
    preface: str,
    rows: Sequence[Mapping[str, Any]],
) -> str:
    """Return `preface\\n<indented-JSON>`. Callers build `preface` with the
    "Found N foo" convention the .NET side uses.
    """
    return f"{preface}\n{json_dumps(list(rows))}"


def format_single(preface: str, row: Mapping[str, Any]) -> str:
    return f"{preface}\n{json_dumps(row)}"
