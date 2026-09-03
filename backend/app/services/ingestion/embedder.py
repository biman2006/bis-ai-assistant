"""
Embedding service — wraps SentenceTransformers for chunk and query embedding.
Supports caching to avoid re-embedding identical text.
"""

from __future__ import annotations
import hashlib
import logging
from typing import List, Optional
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_cache: dict[str, List[float]] = {}


def _get_model():
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE)
        logger.info("Embedding model loaded.")
    return _model


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def embed_text(text: str) -> List[float]:
    """Embed a single text string. Uses in-memory cache."""
    key = _cache_key(text)
    if key in _cache:
        return _cache[key]
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True).tolist()
    _cache[key] = vec
    return vec


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts efficiently."""
    model = _get_model()
    results: List[Optional[List[float]]] = [None] * len(texts)
    uncached_indices: List[int] = []
    uncached_texts: List[str] = []

    for i, text in enumerate(texts):
        key = _cache_key(text)
        if key in _cache:
            results[i] = _cache[key]
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if uncached_texts:
        vecs = model.encode(
            uncached_texts,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=len(uncached_texts) > 10,
        ).tolist()
        for idx, vec in zip(uncached_indices, vecs):
            key = _cache_key(texts[idx])
            _cache[key] = vec
            results[idx] = vec

    return results  # type: ignore


def get_embedding_dim() -> int:
    """Return dimensionality of the current model."""
    model = _get_model()
    return model.get_sentence_embedding_dimension()
