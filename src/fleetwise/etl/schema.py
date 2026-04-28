"""Canonical inspection-row shape + LLM mapping contracts.

The canonical headers are the **only** truth for what column names mean.
Every messy CSV header gets mapped to one of these or to ``None`` (no
match -- the column is dropped). When you change this list, also update
:data:`HEADER_DESCRIPTIONS` so the LLM mapper has the same vocabulary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Required canonical fields. Optional ones (mileage, recommendations) are
# tracked separately so the transform stage knows which absences are OK.
REQUIRED_CANONICAL = (
    "asset_number",
    "inspected_at",
    "inspector_name",
    "passed",
    "findings",
)
OPTIONAL_CANONICAL = ("mileage", "recommendations")
CANONICAL_HEADERS = REQUIRED_CANONICAL + OPTIONAL_CANONICAL

CanonicalHeader = Literal[
    "asset_number",
    "inspected_at",
    "inspector_name",
    "mileage",
    "passed",
    "findings",
    "recommendations",
]

HEADER_DESCRIPTIONS: dict[str, str] = {
    "asset_number": "vehicle's asset/unit identifier (e.g., V-2020-0015, fleet ID)",
    "inspected_at": "date the inspection occurred",
    "inspector_name": "person or vendor who performed the inspection",
    "mileage": "odometer reading at time of inspection (numeric, may be blank)",
    "passed": "pass/fail outcome, may be coded as Pass/Fail, Y/N, OK/FAIL, true/false, etc.",
    "findings": "free-text description of what the inspection observed",
    "recommendations": (
        "follow-up actions, recommendations, or notes for next steps "
        "(distinct from findings; may be blank)"
    ),
}


class HeaderMapping(BaseModel):
    """LLM-produced mapping from one CSV header to one canonical name.

    Used as the element shape inside :class:`HeaderMappingResult`. ``null``
    on ``canonical`` means "no match -- drop this column."
    """

    source: str = Field(description="The original CSV header verbatim.")
    canonical: CanonicalHeader | None = Field(
        description=(
            "Which canonical field this column represents, or null if no field describes it well."
        ),
    )


class HeaderMappingResult(BaseModel):
    """Wrapper for ``with_structured_output`` -- one entry per input header.

    Kept as an explicit wrapper (rather than a bare list) because some
    structured-output providers expect a top-level object, not array.
    """

    mappings: list[HeaderMapping]


class NormalizedInspection(BaseModel):
    """Canonical post-transform row shape.

    What :func:`fleetwise.etl.transform.transform_row` produces and
    :func:`fleetwise.etl.load.load_row` consumes. Hash-stable: the same
    inputs in any order produce the same ``source_row_hash`` because
    :func:`fleetwise.etl.transform.compute_row_hash` sorts keys.
    """

    model_config = ConfigDict(frozen=True)

    asset_number: str
    inspected_at: datetime
    inspector_name: str
    mileage: int | None
    passed: bool
    findings: str
    recommendations: str | None
    source_file: str
    source_row_hash: str
