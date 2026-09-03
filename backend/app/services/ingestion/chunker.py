"""
Text chunking utilities — splits document text into overlapping chunks.
Preserves metadata and handles IS number / QCO extraction.
"""

from __future__ import annotations
import re
from typing import List, Optional
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def extract_is_numbers(text: str) -> List[str]:
    """Extract Indian Standard numbers from text."""
    pattern = r"IS[\s:\-]?\d{3,6}(?:[\s:]*(?:Part[\s\-]?\d+)?)?(?:[\s:]*\d{4})?"
    return list(set(re.findall(pattern, text, re.IGNORECASE)))


def extract_section_title(text: str) -> Optional[str]:
    """Heuristically detect a section heading in the chunk."""
    lines = text.strip().split("\n")
    for line in lines[:3]:
        line = line.strip()
        if len(line) < 100 and (line.isupper() or re.match(r"^\d+[\.\)]\s+\w", line)):
            return line[:200]
    return None


def chunk_text(
    text: str,
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
    page_number: Optional[int] = None,
    base_metadata: Optional[dict] = None,
) -> List[TextChunk]:
    """
    Split text into overlapping chunks of approximately chunk_size tokens.
    Returns a list of TextChunk objects with metadata.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP
    base_metadata = base_metadata or {}

    # Convert chunk size (tokens) to approx chars
    char_size = chunk_size * 4
    char_overlap = overlap * 4
    min_len = settings.MIN_CHUNK_LENGTH

    # Split on double newlines first, then recombine
    paragraphs = re.split(r"\n{2,}", text)
    chunks: List[TextChunk] = []
    current = ""
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 <= char_size:
            current = current + "\n\n" + para if current else para
        else:
            # Flush current
            if len(current) >= min_len:
                token_count = estimate_tokens(current)
                is_numbers = extract_is_numbers(current)
                metadata = {
                    **base_metadata,
                    "is_numbers": is_numbers,
                    "token_count": token_count,
                }
                chunks.append(TextChunk(
                    text=current,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    section_title=extract_section_title(current),
                    token_count=token_count,
                    metadata=metadata,
                ))
                chunk_index += 1
                # Overlap: keep last portion of current
                overlap_text = current[-char_overlap:] if char_overlap > 0 else ""
                current = (overlap_text + "\n\n" + para).strip() if overlap_text else para
            else:
                current = (current + "\n\n" + para).strip() if current else para

    # Flush remaining
    if current and len(current) >= min_len:
        token_count = estimate_tokens(current)
        is_numbers = extract_is_numbers(current)
        chunks.append(TextChunk(
            text=current,
            chunk_index=chunk_index,
            page_number=page_number,
            section_title=extract_section_title(current),
            token_count=token_count,
            metadata={**base_metadata, "is_numbers": is_numbers, "token_count": token_count},
        ))

    return chunks
