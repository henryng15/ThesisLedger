"""Text chunking for SEC filings.

Splits long documents into overlapping chunks suitable for embedding.
Attempts to preserve section boundaries and paragraph structure.
"""

import re
from dataclasses import dataclass
from typing import Iterator

# Target chunk size in characters (roughly 300-500 tokens)
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 200
MIN_CHUNK_SIZE = 200


@dataclass
class ChunkInfo:
    """Metadata about a text chunk."""

    text: str
    ordinal: int
    section: str
    char_start: int
    char_end: int


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (avg 4 chars per token)."""
    return len(text) // 4


def split_into_paragraphs(text: str) -> list[str]:
    """Split text on double newlines, keeping non-empty paragraphs."""
    paragraphs = re.split(r"\n\n+", text)
    return [p.strip() for p in paragraphs if p.strip()]


def detect_section_header(text: str) -> str:
    """Try to find an Item header in the text."""
    patterns = [
        (r"Item\s+1A[.\s:]+Risk", "Item 1A. Risk Factors"),
        (r"Item\s+1[.\s:]+Business", "Item 1. Business"),
        (r"Item\s+7A[.\s:]+Quantitative", "Item 7A. Quantitative"),
        (r"Item\s+7[.\s:]+Management", "Item 7. MD&A"),
        (r"Item\s+8[.\s:]+Financial", "Item 8. Financial Statements"),
    ]

    for pattern, label in patterns:
        if re.search(pattern, text[:500], re.IGNORECASE):
            return label

    return ""


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Iterator[ChunkInfo]:
    """Split text into overlapping chunks.

    Tries to break at paragraph boundaries when possible.

    Args:
        text: Full document text
        chunk_size: Target size per chunk in characters
        overlap: Overlap between consecutive chunks

    Yields:
        ChunkInfo objects with text and metadata
    """
    if len(text) < MIN_CHUNK_SIZE:
        yield ChunkInfo(
            text=text,
            ordinal=0,
            section=detect_section_header(text),
            char_start=0,
            char_end=len(text),
        )
        return

    paragraphs = split_into_paragraphs(text)
    current_chunk = []
    current_size = 0
    chunk_start = 0
    ordinal = 0
    position = 0

    for para in paragraphs:
        para_size = len(para)

        # If single paragraph exceeds chunk size, force split it
        if para_size > chunk_size:
            # Flush current chunk first
            if current_chunk:
                chunk_text_str = "\n\n".join(current_chunk)
                yield ChunkInfo(
                    text=chunk_text_str,
                    ordinal=ordinal,
                    section=detect_section_header(chunk_text_str),
                    char_start=chunk_start,
                    char_end=position,
                )
                ordinal += 1
                current_chunk = []
                current_size = 0

            # Split long paragraph
            for i in range(0, para_size, chunk_size - overlap):
                sub_text = para[i : i + chunk_size]
                if len(sub_text) >= MIN_CHUNK_SIZE:
                    yield ChunkInfo(
                        text=sub_text,
                        ordinal=ordinal,
                        section=detect_section_header(sub_text),
                        char_start=position + i,
                        char_end=position + i + len(sub_text),
                    )
                    ordinal += 1

            chunk_start = position + para_size
            position += para_size + 2  # +2 for \n\n
            continue

        # Would adding this paragraph exceed chunk size?
        if current_size + para_size > chunk_size and current_chunk:
            # Emit current chunk
            chunk_text_str = "\n\n".join(current_chunk)
            yield ChunkInfo(
                text=chunk_text_str,
                ordinal=ordinal,
                section=detect_section_header(chunk_text_str),
                char_start=chunk_start,
                char_end=position,
            )
            ordinal += 1

            # Start new chunk with overlap
            overlap_paras = []
            overlap_size = 0
            for prev_para in reversed(current_chunk):
                if overlap_size + len(prev_para) <= overlap:
                    overlap_paras.insert(0, prev_para)
                    overlap_size += len(prev_para)
                else:
                    break

            current_chunk = overlap_paras
            current_size = overlap_size
            chunk_start = position - overlap_size

        current_chunk.append(para)
        current_size += para_size
        position += para_size + 2

    # Emit final chunk
    if current_chunk:
        chunk_text_str = "\n\n".join(current_chunk)
        if len(chunk_text_str) >= MIN_CHUNK_SIZE:
            yield ChunkInfo(
                text=chunk_text_str,
                ordinal=ordinal,
                section=detect_section_header(chunk_text_str),
                char_start=chunk_start,
                char_end=len(text),
            )
