"""
Keyword/full-text search using PostgreSQL tsvector/tsquery.
"""

from __future__ import annotations
import logging
import re
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)


def _build_tsquery(query: str) -> str:
    """Convert a natural language query to a PostgreSQL tsquery."""
    # Remove special characters, lowercase
    clean = re.sub(r"[^\w\s]", " ", query.lower())
    words = [w.strip() for w in clean.split() if len(w.strip()) > 2]
    if not words:
        return ""
    # Use prefix matching for flexibility
    return " | ".join(f"{w}:*" for w in words[:10])


async def keyword_search(
    session: AsyncSession,
    query: str,
    top_k: int = None,
    source_types: Optional[List[str]] = None,
) -> List[dict]:
    """
    PostgreSQL full-text search using tsvector.
    Returns ranked list of chunk dicts with keyword scores.
    """
    top_k = top_k or settings.TOP_K
    tsquery = _build_tsquery(query)

    if not tsquery:
        return []

    filter_clause = ""
    bind_params: dict = {
        "tsquery": tsquery,
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
            ts_rank_cd(c.search_vector, to_tsquery('english', :tsquery)) AS keyword_score
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.is_active = true
          AND c.search_vector @@ to_tsquery('english', :tsquery)
          {filter_clause}
        ORDER BY keyword_score DESC
        LIMIT :top_k
    """)

    try:
        result = await session.execute(sql, bind_params)
        rows = result.mappings().all()
    except Exception as e:
        logger.warning(f"Keyword search error (tsquery='{tsquery}'): {e}")
        # Fallback: ILIKE search
        rows = await _ilike_fallback(session, query, top_k, source_types)
        return rows

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
            "keyword_score": float(row["keyword_score"]),
        }
        for row in rows
    ]


async def _ilike_fallback(
    session: AsyncSession,
    query: str,
    top_k: int,
    source_types: Optional[List[str]],
) -> List[dict]:
    """Fallback ILIKE search when tsquery fails."""
    words = query.split()[:5]
    conditions = " OR ".join(f"c.chunk_text ILIKE '%{w}%'" for w in words if len(w) > 3)
    if not conditions:
        return []

    filter_clause = ""
    bind_params: dict = {"top_k": top_k}
    if source_types:
        filter_clause = "AND d.source_type = ANY(:source_types)"
        bind_params["source_types"] = source_types

    sql = text(f"""
        SELECT c.id AS chunk_id, c.document_id, c.chunk_text, c.chunk_index,
               c.page_number, c.section_title, c.metadata,
               d.title AS document_title, d.source_url, d.source_type, d.organization,
               0.5 AS keyword_score
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.is_active = true AND ({conditions}) {filter_clause}
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
            "keyword_score": 0.5,
        }
        for row in rows
    ]
