"""CSV extraction stage.

Pure file IO: open the path, parse with stdlib ``csv``, hand back the
header row and every data row as ``(headers, rows)``. The stdlib module
handles the messy bits (embedded commas inside quoted fields, multi-line
quoted values, mixed line endings) correctly already; we don't need a
heavier dependency for this.

Why not return dicts? The mapper needs to see the header order to ask the
LLM about unknown columns; positional rows preserve that. The transform
stage zips headers + values back into a dict after mapping.
"""

from __future__ import annotations

import csv
from pathlib import Path


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    """Return ``(headers, rows)`` from ``path``.

    Headers are stripped of leading / trailing whitespace -- a common
    real-world CSV defect that should be normalized at the door, not
    threaded through the pipeline.
    """
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    return headers, rows[1:]
