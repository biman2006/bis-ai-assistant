"""
Document ingestion service — orchestrates PDF/URL processing,
embedding generation, and database storage.
"""

from __future__ import annotations
import logging
import uuid
from datetime import date
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Document, DocumentChunk, SourceType, DocumentType
from app.services.ingestion.pdf_processor import process_pdf_bytes
from app.services.ingestion.web_processor import fetch_and_process_url, process_raw_text
from app.services.ingestion.chunker import TextChunk
from app.services.ingestion.embedder import embed_batch
from app.config import settings

logger = logging.getLogger(__name__)


async def _store_chunks(
    session: AsyncSession,
    document_id: str,
    chunks: List[TextChunk],
    doc_metadata: dict,
) -> int:
    """Embed and store chunks for a document. Returns count stored."""
    if not chunks:
        return 0

    texts = [c.text for c in chunks]
    embeddings = embed_batch(texts)

    stored = 0
    for chunk, embedding in zip(chunks, embeddings):
        db_chunk = DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=document_id,
            chunk_text=chunk.text,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            embedding=embedding,
            token_count=chunk.token_count,
            metadata_={
                **doc_metadata,
                **chunk.metadata,
            },
        )
        session.add(db_chunk)
        stored += 1

    return stored


async def _update_search_vectors(session: AsyncSession, document_id: str):
    """Update PostgreSQL full-text search vectors for all chunks of a document."""
    from sqlalchemy import text
    await session.execute(
        text("""
            UPDATE document_chunks
            SET search_vector = to_tsvector('english', chunk_text)
            WHERE document_id = :doc_id
        """),
        {"doc_id": document_id},
    )


async def ingest_pdf(
    session: AsyncSession,
    pdf_bytes: bytes,
    title: str,
    source_url: Optional[str] = None,
    source_type: str = "BIS",
    document_type: str = "pdf",
    description: Optional[str] = None,
    organization: str = "BIS",
    language: str = "en",
    published_date: Optional[date] = None,
    file_path: Optional[str] = None,
    extra_metadata: Optional[dict] = None,
) -> Document:
    """Ingest a PDF: extract, chunk, embed, store. Returns Document."""
    # Check for duplicate via checksum
    from app.services.ingestion.pdf_processor import compute_checksum
    checksum = compute_checksum(pdf_bytes)

    existing = await session.execute(
        select(Document).where(Document.checksum == checksum)
    )
    existing_doc = existing.scalar_one_or_none()
    if existing_doc:
        logger.info(f"Document already ingested (checksum match): {existing_doc.id}")
        return existing_doc

    chunks, pdf_meta, _ = process_pdf_bytes(
        pdf_bytes,
        source_url=source_url,
        document_title=title,
        source_type=source_type,
        extra_metadata=extra_metadata or {},
    )

    if not chunks:
        raise ValueError("No extractable text found in PDF.")

    doc = Document(
        id=str(uuid.uuid4()),
        title=title or pdf_meta.get("title", "Untitled"),
        source_url=source_url,
        source_type=SourceType(source_type) if source_type in SourceType._value2member_map_ else SourceType.OTHER,
        organization=organization,
        document_type=DocumentType(document_type) if document_type in DocumentType._value2member_map_ else DocumentType.PDF,
        description=description,
        language=language,
        checksum=checksum,
        file_path=file_path,
        published_date=published_date,
        last_verified=date.today(),
        chunk_count=len(chunks),
    )
    session.add(doc)
    await session.flush()  # get doc.id

    doc_metadata = {
        "document_id": doc.id,
        "title": doc.title,
        "source_url": source_url,
        "source_type": source_type,
        "organization": organization,
        "last_verified": str(date.today()),
    }

    stored = await _store_chunks(session, doc.id, chunks, doc_metadata)
    doc.chunk_count = stored

    await session.commit()
    await _update_search_vectors(session, doc.id)
    await session.commit()

    logger.info(f"Ingested PDF '{doc.title}': {stored} chunks stored.")
    return doc


async def ingest_url(
    session: AsyncSession,
    url: str,
    title: Optional[str] = None,
    source_type: str = "BIS",
    document_type: str = "webpage",
    description: Optional[str] = None,
    organization: str = "BIS",
    language: str = "en",
    extra_metadata: Optional[dict] = None,
) -> Document:
    """Fetch a URL, extract text, chunk, embed, and store."""
    chunks, page_meta, checksum = await fetch_and_process_url(
        url,
        document_title=title,
        source_type=source_type,
        extra_metadata=extra_metadata or {},
    )

    # Dedup check
    existing = await session.execute(
        select(Document).where(Document.checksum == checksum)
    )
    existing_doc = existing.scalar_one_or_none()
    if existing_doc:
        logger.info(f"URL already ingested: {url}")
        return existing_doc

    resolved_title = title or page_meta.get("title", url)
    doc = Document(
        id=str(uuid.uuid4()),
        title=resolved_title,
        source_url=url,
        source_type=SourceType(source_type) if source_type in SourceType._value2member_map_ else SourceType.BIS,
        organization=organization,
        document_type=DocumentType(document_type) if document_type in DocumentType._value2member_map_ else DocumentType.WEBPAGE,
        description=description,
        language=language,
        checksum=checksum,
        last_verified=date.today(),
        chunk_count=len(chunks),
    )
    session.add(doc)
    await session.flush()

    doc_metadata = {
        "document_id": doc.id,
        "title": resolved_title,
        "source_url": url,
        "source_type": source_type,
        "organization": organization,
        "last_verified": str(date.today()),
    }

    stored = await _store_chunks(session, doc.id, chunks, doc_metadata)
    doc.chunk_count = stored

    await session.commit()
    await _update_search_vectors(session, doc.id)
    await session.commit()

    logger.info(f"Ingested URL '{resolved_title}': {stored} chunks stored.")
    return doc


async def ingest_text(
    session: AsyncSession,
    text: str,
    title: str,
    source_url: Optional[str] = None,
    source_type: str = "BIS",
    document_type: str = "other",
    organization: str = "BIS",
    language: str = "en",
    extra_metadata: Optional[dict] = None,
) -> Document:
    """Ingest raw text (used for seeding)."""
    import hashlib
    checksum = hashlib.sha256(text.encode()).hexdigest()

    existing = await session.execute(
        select(Document).where(Document.checksum == checksum)
    )
    if existing.scalar_one_or_none():
        logger.info(f"Text already ingested: {title}")
        return existing.scalar_one_or_none()

    chunks, meta, _ = process_raw_text(
        text, title, source_url=source_url, source_type=source_type,
        extra_metadata=extra_metadata or {},
    )

    doc = Document(
        id=str(uuid.uuid4()),
        title=title,
        source_url=source_url,
        source_type=SourceType(source_type) if source_type in SourceType._value2member_map_ else SourceType.BIS,
        organization=organization,
        document_type=DocumentType(document_type) if document_type in DocumentType._value2member_map_ else DocumentType.OTHER,
        language=language,
        checksum=checksum,
        last_verified=date.today(),
        chunk_count=len(chunks),
    )
    session.add(doc)
    await session.flush()

    doc_metadata = {
        "document_id": doc.id,
        "title": title,
        "source_url": source_url,
        "source_type": source_type,
        "organization": organization,
        "last_verified": str(date.today()),
    }

    stored = await _store_chunks(session, doc.id, chunks, doc_metadata)
    doc.chunk_count = stored

    await session.commit()
    await _update_search_vectors(session, doc.id)
    await session.commit()

    return doc


async def delete_document(session: AsyncSession, document_id: str) -> bool:
    """Delete a document and all its chunks."""
    doc = await session.get(Document, document_id)
    if not doc:
        return False
    await session.delete(doc)
    await session.commit()
    return True


async def reindex_document(session: AsyncSession, document_id: str) -> int:
    """Re-embed all chunks of a document (e.g. after model change)."""
    from sqlalchemy import text
    result = await session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    chunks = result.scalars().all()
    if not chunks:
        return 0

    texts = [c.chunk_text for c in chunks]
    embeddings = embed_batch(texts)

    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    await session.commit()
    await _update_search_vectors(session, document_id)
    await session.commit()
    return len(chunks)
