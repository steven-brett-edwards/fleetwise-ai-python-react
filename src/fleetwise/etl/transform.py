"""Value coercion + canonicalization for one CSV row.

Each coercer takes a string and returns either the canonical Python type
or raises a ``RowTransformError`` with a human-readable reason. The
pipeline collects rejection reasons per row so the CLI can print
"V-2020-0010 was dropped because: could not parse mileage '45.1q'".

The deterministic ``compute_row_hash`` is the idempotency contract --
hash a NormalizedInspection's content (excluding ``source_file`` and
``source_row_hash`` themselves) and the same logical row produces the
same hash on every run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Final

from dateutil import parser as date_parser

from fleetwise.etl.schema import NormalizedInspection

# Pass/fail vocabulary. Lowercased on input. Anything outside both sets
# is a rejection -- we never default-to-pass when the field is ambiguous.
_PASS_TOKENS: Final[frozenset[str]] = frozenset(
    {"pass", "passed", "p", "y", "yes", "true", "ok", "okay"}
)
_FAIL_TOKENS: Final[frozenset[str]] = frozenset(
    {"fail", "failed", "f", "n", "no", "false", "not ok"}
)


class RowTransformError(ValueError):
    """A row couldn't be coerced. The message is shown to the operator."""


def coerce_date(raw: str) -> datetime:
    """Parse one of the eight CSV date formats we've seen in the wild.

    `dateutil.parser.parse` covers ISO, US-slashed, written, and
    abbreviated forms. ``dayfirst=False`` keeps it consistent for the
    US-municipal data we're modeling -- override at the pipeline level if
    we ever ingest non-US sources.
    """
    raw = (raw or "").strip()
    if not raw:
        raise RowTransformError("date is blank")
    try:
        parsed: datetime = date_parser.parse(raw, dayfirst=False)
    except (ValueError, OverflowError) as exc:
        raise RowTransformError(f"could not parse date {raw!r}") from exc
    return parsed


def coerce_mileage(raw: str | None) -> int | None:
    """Strip commas, accept ``45.1k`` / ``45k`` shorthand, allow blank.

    Blank returns ``None`` (a real-world signal: "the inspector didn't
    record it"). Anything non-numeric after stripping the suffix is a
    rejection -- silently zeroing would falsify the data.
    """
    if raw is None:
        return None
    cleaned = raw.strip().replace(",", "")
    if not cleaned:
        return None
    if cleaned.lower().endswith("k"):
        try:
            return round(float(cleaned[:-1]) * 1000)
        except ValueError as exc:
            raise RowTransformError(f"could not parse mileage {raw!r}") from exc
    try:
        return round(float(cleaned))
    except ValueError as exc:
        raise RowTransformError(f"could not parse mileage {raw!r}") from exc


def coerce_passed(raw: str) -> bool:
    """Map the pass/fail vocabulary to a bool. Unknown tokens reject."""
    token = (raw or "").strip().lower()
    if token in _PASS_TOKENS:
        return True
    if token in _FAIL_TOKENS:
        return False
    raise RowTransformError(f"unrecognized pass/fail value {raw!r}")


def coerce_optional_text(raw: str | None) -> str | None:
    """Strip whitespace; return ``None`` if empty.

    Used for ``recommendations`` -- a blank cell is valid (no follow-up
    needed) and shouldn't become an empty-string sentinel downstream.
    """
    if raw is None:
        return None
    cleaned = raw.strip()
    return cleaned or None


def coerce_required_text(raw: str | None, *, field: str) -> str:
    """Strip whitespace; reject if empty after stripping."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise RowTransformError(f"{field} is blank")
    return cleaned


def compute_row_hash(
    *,
    asset_number: str,
    inspected_at: datetime,
    inspector_name: str,
    mileage: int | None,
    passed: bool,
    findings: str,
    recommendations: str | None,
) -> str:
    """Deterministic sha256 of the canonical content. Input order is sorted."""
    payload = {
        "asset_number": asset_number,
        "inspected_at": inspected_at.isoformat(),
        "inspector_name": inspector_name,
        "mileage": mileage,
        "passed": passed,
        "findings": findings,
        "recommendations": recommendations,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def transform_row(
    mapped: dict[str, str | None],
    *,
    source_file: str,
) -> NormalizedInspection:
    """Apply every coercer in turn; bail on the first rejection.

    ``mapped`` is the post-mapping dict (canonical keys -> raw string
    values). Caller is responsible for filtering out columns the mapper
    couldn't place; this function assumes every required canonical key
    is present (raising :class:`RowTransformError` if the value itself
    is bad, not if the key is missing).
    """
    asset_number = coerce_required_text(mapped.get("asset_number"), field="asset_number")
    inspected_at = coerce_date(mapped.get("inspected_at") or "")
    inspector_name = coerce_required_text(mapped.get("inspector_name"), field="inspector_name")
    mileage = coerce_mileage(mapped.get("mileage"))
    passed = coerce_passed(mapped.get("passed") or "")
    findings = coerce_required_text(mapped.get("findings"), field="findings")
    recommendations = coerce_optional_text(mapped.get("recommendations"))

    row_hash = compute_row_hash(
        asset_number=asset_number,
        inspected_at=inspected_at,
        inspector_name=inspector_name,
        mileage=mileage,
        passed=passed,
        findings=findings,
        recommendations=recommendations,
    )

    return NormalizedInspection(
        asset_number=asset_number,
        inspected_at=inspected_at,
        inspector_name=inspector_name,
        mileage=mileage,
        passed=passed,
        findings=findings,
        recommendations=recommendations,
        source_file=source_file,
        source_row_hash=row_hash,
    )
