"""
Stage 2 of the pipeline: splitting documents into chunks.

⚠️ THIS IS THE FILE YOU CHANGE IN MILESTONE 3.

`split_documents` below is deliberately plain. It cuts every document into
fixed-size pieces with a fixed overlap and pays no attention to where sentences
or paragraphs end. It works, and it is not good.

On a corpus of short posts it may not cut anything at all: `campus_life` comes
out as 88 documents and 88 chunks, because almost nothing in it reaches 800
characters. That is the baseline, not a bug — Milestone 3 is where you decide
whether one post should stay one chunk.

Your job in Milestone 3 is to replace the *body* of `split_documents` with a
strategy that fits the documents you actually read in Milestone 1. Keep the
name and the shape of what it returns — the rest of the pipeline calls it, and
your README has to name the function that produced your chunks.

If you get stuck for 30 minutes, `fallback_split` is the original. Switch back
to it, write down what you saw, and move on. That's a real observation about
your pipeline, not giving up.
"""

import re
from dataclasses import dataclass

import config
from ingest import Document

MIN_CHUNK_CHARS = 80  # a chunk shorter than this is a fragment, not an answer — see criteria.md #4


@dataclass
class Chunk:
    """One piece of one document."""

    text: str
    source: str        # which file it came from
    index: int         # which chunk within that file, starting at 0
    produced_by: str   # the function that made it — cite this in your README

    @property
    def label(self) -> str:
        return f"{self.source}#{self.index}"


def fallback_split(
    documents: list[Document],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    The starter's original chunker. Fixed-size character windows with overlap.

    Keep this function. Milestone 3's stop rule points back at it, and having
    something to compare your own strategy against is useful in week 2.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    overlap = overlap or config.CHUNK_OVERLAP

    if overlap >= chunk_size:
        raise ValueError("overlap has to be smaller than chunk_size")

    chunks: list[Chunk] = []
    for doc in documents:
        start = 0
        index = 0
        while start < len(doc.text):
            piece = doc.text[start : start + chunk_size].strip()
            if piece:
                chunks.append(
                    Chunk(
                        text=piece,
                        source=doc.source,
                        index=index,
                        produced_by="chunker.py::fallback_split",
                    )
                )
                index += 1
            start += chunk_size - overlap

    return chunks


def _paragraphs(text: str) -> list[str]:
    """Split a document on blank lines."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def split_documents(documents: list[Document]) -> list[Chunk]:
    """
    Group each document's paragraphs into chunks up to CHUNK_SIZE, breaking
    only at a paragraph boundary — never mid-sentence.

    campus_life is 88 short posts, each one topic: 183 to 554 characters,
    every one of them under CHUNK_SIZE. Reading all 88 in Milestone 1 showed
    their paragraphs are sub-points of that one topic (a course post's intro,
    workload line, and advice line; a dining post's wait times, hours, and
    cost), not separate topics — there's nothing here worth pulling apart. So
    for this corpus, every document stays one chunk, but as a consequence of
    walking its paragraphs and finding they all fit, not because a fixed
    800-character cutoff happened not to bite. A document that ran long would
    still split cleanly at a paragraph break here instead of slicing a
    sentence in half.

    If a split would leave a trailing group under MIN_CHUNK_CHARS characters
    — a bare fragment like course_econ_101.txt's "Expect 4 hours a week
    outside class." on its own, with no course name in it — that group is
    merged into the one before it instead of standing alone.
    """
    chunk_size = config.CHUNK_SIZE
    chunks: list[Chunk] = []

    for doc in documents:
        paragraphs = _paragraphs(doc.text)
        groups: list[list[str]] = []
        current: list[str] = []
        current_len = 0

        for para in paragraphs:
            added_len = len(para) + (2 if current else 0)  # + the "\n\n" joiner
            if current and current_len + added_len > chunk_size:
                groups.append(current)
                current = [para]
                current_len = len(para)
            else:
                current.append(para)
                current_len += added_len
        if current:
            groups.append(current)

        if len(groups) > 1 and sum(len(p) for p in groups[-1]) < MIN_CHUNK_CHARS:
            groups[-2].extend(groups.pop())

        for index, group in enumerate(groups):
            chunks.append(
                Chunk(
                    text="\n\n".join(group),
                    source=doc.source,
                    index=index,
                    produced_by="chunker.py::split_documents",
                )
            )

    return chunks


def describe(chunks: list[Chunk]) -> str:
    """A one-line summary, printed after indexing."""
    if not chunks:
        return "0 chunks"
    lengths = [len(c.text) for c in chunks]
    return (
        f"{len(chunks)} chunks, "
        f"{sum(lengths) // len(lengths)} characters on average "
        f"(shortest {min(lengths)}, longest {max(lengths)}), "
        f"produced by {chunks[0].produced_by}"
    )


if __name__ == "__main__":
    from ingest import load_documents

    chunks = split_documents(load_documents())
    print(describe(chunks))
