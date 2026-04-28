"""Coercer + hash tests for fleetwise.etl.transform.

These are the tests the rest of the pipeline leans on -- if `coerce_date`
or `compute_row_hash` regress, every higher-level test is suddenly
testing the wrong thing. Hold the line.
"""

from __future__ import annotations

import pytest

from fleetwise.etl.transform import (
    RowTransformError,
    coerce_date,
    coerce_mileage,
    coerce_optional_text,
    coerce_passed,
    coerce_required_text,
    compute_row_hash,
    transform_row,
)

# ── coerce_date ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        "2026-03-15",
        "3/15/2026",
        "March 15 2026",
        "March 15, 2026",
        "15-Mar-2026",
        "2026-03-15T00:00:00",
    ],
)
def test_coerce_date_accepts_messy_real_world_formats(raw: str) -> None:
    parsed = coerce_date(raw)
    assert parsed.year == 2026
    assert parsed.month == 3
    assert parsed.day == 15


def test_coerce_date_rejects_blank() -> None:
    with pytest.raises(RowTransformError, match="blank"):
        coerce_date("")


def test_coerce_date_rejects_garbage() -> None:
    with pytest.raises(RowTransformError, match="could not parse"):
        coerce_date("not a date at all")


# ── coerce_mileage ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("45123", 45123),
        ("45,123", 45123),
        ("45.1k", 45100),
        ("45k", 45000),
        ("48.2K", 48200),
        ("", None),
        (None, None),
        ("  ", None),
    ],
)
def test_coerce_mileage_accepts_messy_formats(raw: str | None, expected: int | None) -> None:
    assert coerce_mileage(raw) == expected


def test_coerce_mileage_rejects_garbage() -> None:
    with pytest.raises(RowTransformError, match="could not parse"):
        coerce_mileage("forty thousand")


# ── coerce_passed ──────────────────────────────────────────────────────


@pytest.mark.parametrize("raw", ["Pass", "PASSED", "P", "Y", "true", "OK", "Yes"])
def test_coerce_passed_accepts_pass_vocabulary(raw: str) -> None:
    assert coerce_passed(raw) is True


@pytest.mark.parametrize("raw", ["Fail", "FAILED", "F", "N", "false", "No"])
def test_coerce_passed_accepts_fail_vocabulary(raw: str) -> None:
    assert coerce_passed(raw) is False


def test_coerce_passed_rejects_unknown_token() -> None:
    with pytest.raises(RowTransformError, match="unrecognized"):
        coerce_passed("maybe")


# ── text helpers ───────────────────────────────────────────────────────


def test_coerce_required_text_strips_whitespace() -> None:
    assert coerce_required_text("  hello  ", field="findings") == "hello"


def test_coerce_required_text_rejects_blank() -> None:
    with pytest.raises(RowTransformError, match="findings is blank"):
        coerce_required_text("   ", field="findings")


def test_coerce_optional_text_returns_none_for_blank() -> None:
    assert coerce_optional_text("   ") is None
    assert coerce_optional_text("") is None
    assert coerce_optional_text(None) is None


def test_coerce_optional_text_strips_when_present() -> None:
    assert coerce_optional_text("  schedule next week ") == "schedule next week"


# ── compute_row_hash ──────────────────────────────────────────────────


def test_compute_row_hash_is_deterministic_across_calls() -> None:
    """Idempotency contract -- same logical row -> same hash, every time."""
    base = {
        "asset_number": "V-2020-0015",
        "inspected_at": coerce_date("2026-03-15"),
        "inspector_name": "Maria Alvarez",
        "mileage": 49100,
        "passed": True,
        "findings": "Brakes 50% remaining.",
        "recommendations": None,
    }
    assert compute_row_hash(**base) == compute_row_hash(**base)


def test_compute_row_hash_changes_when_any_field_changes() -> None:
    """Sanity belt -- hash isn't accidentally constant for unrelated rows."""
    base = {
        "asset_number": "V-2020-0015",
        "inspected_at": coerce_date("2026-03-15"),
        "inspector_name": "Maria Alvarez",
        "mileage": 49100,
        "passed": True,
        "findings": "Brakes 50% remaining.",
        "recommendations": None,
    }
    h1 = compute_row_hash(**base)
    h2 = compute_row_hash(**{**base, "mileage": 49200})
    h3 = compute_row_hash(**{**base, "passed": False})
    h4 = compute_row_hash(**{**base, "findings": "Brakes 60% remaining."})
    assert len({h1, h2, h3, h4}) == 4


# ── transform_row ──────────────────────────────────────────────────────


def test_transform_row_produces_normalized_inspection_with_stable_hash() -> None:
    mapped = {
        "asset_number": "V-2020-0015",
        "inspected_at": "March 15 2026",
        "inspector_name": " Maria Alvarez ",
        "mileage": "49,100",
        "passed": "Pass",
        "findings": "Brakes 50% remaining.",
        "recommendations": "",
    }
    out = transform_row(mapped, source_file="admin-fleet-checks-jan-2026.csv")

    assert out.asset_number == "V-2020-0015"
    assert out.inspected_at.year == 2026 and out.inspected_at.month == 3
    assert out.inspector_name == "Maria Alvarez"
    assert out.mileage == 49100
    assert out.passed is True
    assert out.recommendations is None
    assert out.source_file == "admin-fleet-checks-jan-2026.csv"
    # Re-running produces the same hash.
    again = transform_row(mapped, source_file="admin-fleet-checks-jan-2026.csv")
    assert out.source_row_hash == again.source_row_hash


def test_transform_row_surfaces_first_rejection_reason() -> None:
    mapped = {
        "asset_number": "V-2020-0015",
        "inspected_at": "2026-03-15",
        "inspector_name": "Maria",
        "mileage": "forty",
        "passed": "Pass",
        "findings": "All good.",
        "recommendations": None,
    }
    with pytest.raises(RowTransformError, match="mileage"):
        transform_row(mapped, source_file="x.csv")
