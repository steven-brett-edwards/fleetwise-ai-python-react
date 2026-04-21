"""Unit tests for the heading-based markdown chunker.

Mirrors a representative subset of the .NET `DocumentChunkerTests.cs`.
The chunker is pure-function, so every case runs in microseconds with
no fixtures.
"""

from __future__ import annotations

from fleetwise.ai.rag.chunker import MAX_CHUNK_LENGTH, chunk_by_headings, chunk_by_paragraphs


def test_chunk_by_headings_splits_on_double_hash() -> None:
    content = "# Title\nIntro text.\n\n## Section A\nBody A.\n\n## Section B\nBody B.\n"
    chunks = chunk_by_headings(content)

    # Three chunks: intro, section A (with `## ` prefix), section B.
    assert len(chunks) == 3
    assert chunks[0].startswith("# Title")
    assert chunks[1].startswith("## Section A")
    assert chunks[2].startswith("## Section B")


def test_chunk_by_headings_preserves_first_section_without_adding_double_hash() -> None:
    # The first section starts with `# Title` (H1), not `## ` -- the
    # chunker must not prepend `## ` to it. Matches the .NET behavior.
    chunks = chunk_by_headings("# Title\n\nSome intro.\n\n## Later\nMore.\n")
    assert chunks[0] == "# Title\n\nSome intro."
    assert chunks[1].startswith("## Later")


def test_chunk_by_headings_does_not_split_on_triple_hash() -> None:
    # `### Subheading` is *inside* its parent `## Section`, not a new
    # chunk. The split pattern is `\n## `, which doesn't match `\n### `.
    content = "# T\n\n## Parent\nLead.\n\n### Sub\nDetail.\n"
    chunks = chunk_by_headings(content)
    assert len(chunks) == 2
    assert "### Sub" in chunks[1]


def test_chunk_by_headings_returns_empty_for_empty_input() -> None:
    assert chunk_by_headings("") == []


def test_chunk_by_headings_sub_splits_long_sections_by_paragraph() -> None:
    # Build a section that exceeds MAX_CHUNK_LENGTH so the fallback
    # paragraph-splitter kicks in.
    paragraphs = [f"Paragraph {i} " + "x" * 200 for i in range(5)]
    content = "# T\n\n## Long\n" + "\n\n".join(paragraphs)

    chunks = chunk_by_headings(content)
    # The `Long` section should have been broken into multiple sub-chunks.
    assert len(chunks) > 2
    # Every emitted sub-chunk from the long section respects the ceiling.
    for chunk in chunks[1:]:
        assert len(chunk) <= MAX_CHUNK_LENGTH


def test_chunk_by_paragraphs_joins_small_paragraphs_up_to_ceiling() -> None:
    # Two short paragraphs should merge into one chunk (joined with `\n\n`).
    section = "Alpha.\n\nBeta."
    chunks = chunk_by_paragraphs(section)
    assert chunks == ["Alpha.\n\nBeta."]


def test_chunk_by_paragraphs_starts_new_chunk_when_joining_overflows() -> None:
    # A paragraph that would push us over the ceiling starts a new chunk.
    p1 = "a" * 400
    p2 = "b" * 200
    chunks = chunk_by_paragraphs(f"{p1}\n\n{p2}")
    assert chunks == [p1, p2]


def test_chunk_by_paragraphs_skips_empty_paragraphs() -> None:
    # Consecutive blank lines shouldn't emit empty chunks.
    chunks = chunk_by_paragraphs("one\n\n\n\ntwo")
    assert chunks == ["one\n\ntwo"]
