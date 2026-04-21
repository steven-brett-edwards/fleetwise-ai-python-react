"""Heading-based markdown chunker.

Direct port of the .NET `DocumentChunker` (see `DocumentChunker.cs`).
The SOPs are structured with `## Section` headings; splitting on those
preserves section boundaries in retrieval output, which is why the
cited chunks read cleanly in the agent's response.

`RecursiveCharacterTextSplitter` from LangChain would work, but it
produces smaller, less semantically coherent chunks -- and the whole
point of this project's portfolio value is that the domain shape is
deliberate. Hand-rolled mirrors the .NET implementation exactly.

Two knobs that matter:

- `MAX_CHUNK_LENGTH = 500` is a soft ceiling. Sections under it stay
  whole; longer sections get sub-split by paragraph (double-newline)
  boundaries, joining adjacent paragraphs until the ceiling would be
  exceeded.
- The first section starts with a `# Title`, not `## Heading`, so the
  split pattern `\\n## ` drops it into `sections[0]` without a leading
  `## ` and we skip re-adding the prefix there. Matches .NET behavior.
"""

from __future__ import annotations

MAX_CHUNK_LENGTH = 500


def chunk_by_headings(content: str) -> list[str]:
    """Split markdown on `## ` boundaries, sub-split oversized sections.

    The `\\n## ` split pattern keeps the lead-in newline as the section
    terminator and only matches `## ` at a line start -- triple-hash
    sub-headings (`### Foo`) are NOT split, they live inside their parent
    section. That's the same behavior as the .NET `string.Split("\\n## ")`.
    """
    chunks: list[str] = []
    sections = [s for s in content.split("\n## ") if s]
    if not sections:
        return chunks

    first = sections[0]
    for section in sections:
        # The first section starts with the document's `# Title`; later
        # sections lost their `## ` prefix to the split and we re-add it.
        text = section.strip() if section is first else f"## {section.strip()}"

        if len(text) <= MAX_CHUNK_LENGTH:
            chunks.append(text)
        else:
            chunks.extend(chunk_by_paragraphs(text))

    return chunks


def chunk_by_paragraphs(section: str) -> list[str]:
    """Split an oversized section at paragraph boundaries.

    Joins consecutive paragraphs with a blank line between them while
    the running chunk stays under `MAX_CHUNK_LENGTH` (the `+ 2` accounts
    for the `\\n\\n` separator added when joining). Overflowing paragraph
    starts a new chunk; the in-flight chunk is flushed.
    """
    chunks: list[str] = []
    paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= MAX_CHUNK_LENGTH:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks
