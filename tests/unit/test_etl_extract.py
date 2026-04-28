"""CSV reader sanity checks against the committed inspection fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fleetwise.etl.extract import read_csv

INSPECTIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "inspections"


def test_read_csv_strips_header_whitespace() -> None:
    headers, _ = read_csv(INSPECTIONS_DIR / "inspections-2026-03-batch-a.csv")
    assert "Asset Number" in headers
    assert all(h == h.strip() for h in headers)


def test_read_csv_returns_data_rows_only() -> None:
    """Header row is excluded from the data rows list."""
    headers, rows = read_csv(INSPECTIONS_DIR / "inspections-2026-03-batch-a.csv")
    assert len(headers) > 0
    # First data row's first column is the asset number, not the header.
    assert rows[0][0].startswith("V-")


def test_read_csv_handles_quoted_multiline_findings() -> None:
    """Real-world CSVs embed newlines inside quoted free-text fields."""
    headers, rows = read_csv(INSPECTIONS_DIR / "incident-followups-q1-2026.csv")
    findings_idx = headers.index("Findings")
    multiline_findings = [r[findings_idx] for r in rows if "\n" in r[findings_idx]]
    assert multiline_findings, "expected at least one multiline findings cell"


def test_read_csv_empty_file_returns_empty() -> None:
    """Defensive: a zero-byte file shouldn't raise."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        empty = Path(fh.name)
    try:
        headers, rows = read_csv(empty)
        assert headers == []
        assert rows == []
    finally:
        empty.unlink()
