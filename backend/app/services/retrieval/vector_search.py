"""
Vector search using pgvector cosine similarity.
"""

from __future__ import annotations
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models import DocumentChunk, Document
from app.services.ingestion.embedder import embed_text
from app.config import settings

logger = logging.getLogger(__name__)


async def vector_search(
    session: AsyncSession,
    query: str,
    top_k: int = None,
    source_types: Optional[List[str]] = None,
) -> List[dict]:
    """
    Perform cosine similarity search using pgvector.
    Returns ranked list of chunk dicts with scores.
    """
    top_k = top_k or settings.TOP_K
    query_embedding = embed_text(query)

    # Build filter clause
    filter_clause = ""
    bind_params: dict = {
        "embedding": str(query_embedding),
        "top_k": top_k,
    }

    if source_types:
        filter_clause = "AND d.source_type = ANY(:source_types)"
        bind_params["source_types"] = source_types

    sql = text(f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.chunk_text,
            c.chunk_index,
            c.page_number,
            c.section_title,
            c.metadata,
            d.title AS document_title,
            d.source_url,
            d.source_type,
            d.organization,
            1 - (c.embedding <=> :embedding::vector) AS similarity_score
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.is_active = true
          AND c.embedding IS NOT NULL
          {filter_clause}
        ORDER BY c.embedding <=> :embedding::vector
        LIMIT :top_k
    """)

    result = await session.execute(sql, bind_params)
    rows = result.mappings().all()

    return [
        {
            "chunk_id": str(row["chunk_id"]),
            "document_id": str(row["document_id"]),
            "chunk_text": row["chunk_text"],
            "chunk_index": row["chunk_index"],
            "page_number": row["page_number"],
            "section_title": row["section_title"],
            "metadata": row["metadata"] or {},
            "document_title": row["document_title"],
            "source_url": row["source_url"],
            "source_type": row["source_type"],
            "organization": row["organization"],
            "vector_score": float(row["similarity_score"]),
        }
        for row in rows
    ]
