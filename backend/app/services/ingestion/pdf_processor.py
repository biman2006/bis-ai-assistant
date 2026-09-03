"""
PDF document processor using PyMuPDF (fitz).
Extracts text page-by-page, cleans it, chunks it, and returns ingestable chunks.
"""

from __future__ import annotations
import hashlib
import logging
import re
from pathlib import Path
from typing import List, Optional

from app.services.ingestion.chunker import chunk_text, TextChunk

logger = logging.getLogger(__name__)


def compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_text(text: str) -> str:
    """Remove PDF extraction artifacts and normalise whitespace."""
    # Remove form feed characters
    text = text.replace("\f", "\n")
    # Normalise Unicode hyphens
    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014]", "-", text)
    # Collapse excessive whitespace but preserve paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove page headers/footers patterns (e.g., "Page 1 of 20")
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", "", text, flags=re.IGNORECASE)
    return text.strip()


def extract_pdf_metadata(doc) -> dict:
    """Extract metadata from a fitz document."""
    meta = doc.metadata or {}
    return {
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "subject": meta.get("subject", ""),
        "creator": meta.get("creator", ""),
        "page_count": doc.page_count,
    }


def process_pdf_bytes(
    pdf_bytes: bytes,
    source_url: Optional[str] = None,
    document_title: Optional[str] = None,
    source_type: str = "BIS",
    extra_metadata: Optional[dict] = None,
) -> tuple[List[TextChunk], dict, str]:
    """
    Process a PDF from raw bytes.

    Returns:
        chunks: list of TextChunk
        pdf_meta: extracted PDF metadata
        checksum: sha256 of the PDF bytes
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF (fitz) is required. Install with: pip install pymupdf")

    checksum = compute_checksum(pdf_bytes)
    extra_metadata = extra_metadata or {}

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.error(f"Failed to open PDF: {e}")
        raise ValueError(f"Cannot open PDF: {e}") from e

    pdf_meta = extract_pdf_metadata(doc)
    if document_title:
        pdf_meta["title"] = document_title

    all_chunks: List[TextChunk] = []

    for page_num in range(doc.page_count):
        try:
            page = doc[page_num]
            text = page.get_text("text")
            text = clean_text(text)
            if not text or len(text) < 20:
                continue

            base_metadata = {
                "source_url": source_url,
                "source_type": source_type,
                "document_title": pdf_meta.get("title", document_title),
                **extra_metadata,
            }

            page_chunks = chunk_text(
                text,
                page_number=page_num + 1,
                base_metadata=base_metadata,
            )
            all_chunks.extend(page_chunks)
        except Exception as e:
            logger.warning(f"Error processing page {page_num + 1}: {e}")
            continue

    doc.close()
    logger.info(f"PDF processed: {len(all_chunks)} chunks from {doc.page_count} pages")
    return all_chunks, pdf_meta, checksum


def process_pdf_file(
    file_path: str,
    source_url: Optional[str] = None,
    document_title: Optional[str] = None,
    source_type: str = "BIS",
    extra_metadata: Optional[dict] = None,
) -> tuple[List[TextChunk], dict, str]:
    """Process a PDF from a file path."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    pdf_bytes = path.read_bytes()
    return process_pdf_bytes(pdf_bytes, source_url, document_title or path.stem, source_type, extra_metadata)
