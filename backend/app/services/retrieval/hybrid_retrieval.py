"""
Hybrid retrieval — combines vector and keyword search using
Reciprocal Rank Fusion (RRF), then optionally reranks with a cross-encoder.
"""

from __future__ import annotations
import logging
from typing import List, Optional, Dict

from app.services.retrieval.local_knowledge import local_retrieve
from app.config import settings

logger = logging.getLogger(__name__)

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None and settings.ENABLE_RERANKER:
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker: {settings.RERANKER_MODEL}")
            _reranker = CrossEncoder(settings.RERANKER_MODEL, max_length=512)
            logger.info("Reranker loaded.")
        except Exception as e:
            logger.warning(f"Reranker unavailable ({e}). Skipping reranking.")
            _reranker = False  # Mark as unavailable
    return _reranker if _reranker else None


def _reciprocal_rank_fusion(
    vector_results: List[dict],
    keyword_results: List[dict],
    k: int = 60,
    vector_weight: float = None,
    keyword_weight: float = None,
) -> List[dict]:
    """
    Combine two ranked lists using Reciprocal Rank Fusion.
    RRF score = Σ (weight / (k + rank))
    """
    vector_weight = vector_weight or settings.VECTOR_SEARCH_WEIGHT
    keyword_weight = keyword_weight or settings.KEYWORD_SEARCH_WEIGHT

    scores: Dict[str, float] = {}
    chunks_by_id: Dict[str, dict] = {}

    for rank, chunk in enumerate(vector_results, start=1):
        cid = chunk["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + vector_weight / (k + rank)
        chunks_by_id[cid] = chunk

    for rank, chunk in enumerate(keyword_results, start=1):
        cid = chunk["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + keyword_weight / (k + rank)
        chunks_by_id[cid] = chunk

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result = []
    for cid, score in ranked:
        chunk = dict(chunks_by_id[cid])
        chunk["rrf_score"] = round(score, 6)
        result.append(chunk)

    return result


def _rerank(query: str, chunks: List[dict], top_k: int) -> List[dict]:
    """Rerank using cross-encoder if available."""
    reranker = _get_reranker()
    if not reranker or len(chunks) <= 1:
        return chunks[:top_k]

    try:
        pairs = [(query, c["chunk_text"][:512]) for c in chunks]
        scores = reranker.predict(pairs)
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
        chunks.sort(key=lambda c: c.get("rerank_score", 0.0), reverse=True)
    except Exception as e:
        logger.warning(f"Reranking failed: {e}")

    return chunks[:top_k]


async def hybrid_retrieve(
    query: str,
    session=None,
    top_k: Optional[int] = None,
    rerank_top_k: Optional[int] = None,
    source_types: Optional[List[str]] = None,
) -> List[dict]:
    """
    Full hybrid retrieval pipeline:
    1. Vector search
    2. Keyword search
    3. RRF fusion
    4. Cross-encoder reranking
    """
    top_k = top_k or settings.TOP_K
    rerank_top_k = rerank_top_k or settings.RERANK_TOP_K

    return await local_retrieve(query, top_k=rerank_top_k, source_types=source_types)
