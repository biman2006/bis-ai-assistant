"""Search endpoints backed by the local BIS knowledge base."""

from fastapi import APIRouter, Query

from app.schemas import (
    ChunkSearchResult, QCOResponse, QCOSearchResponse, SearchRequest,
    SearchResponse, StandardResponse, StandardSearchResponse,
)
from app.services.retrieval.local_knowledge import local_retrieve, local_standard_search

router = APIRouter()


@router.get("/standards/search", response_model=StandardSearchResponse)
async def search_standards(q: str = Query(..., min_length=1), limit: int = Query(default=10, ge=1, le=50)):
    results = [StandardResponse.model_validate(item) for item in local_standard_search(q, limit)]
    return StandardSearchResponse(results=results, total=len(results), query=q)


@router.get("/qcos/search", response_model=QCOSearchResponse)
async def search_qcos(q: str = Query(..., min_length=1), limit: int = Query(default=10, ge=1, le=50)):
    results = []
    if any(term in q.lower() for term in ("qco", "quality control", "mandatory")):
        results.append(QCOResponse(
            id="bis-qco", qco_title="Quality Control Orders (QCOs)",
            product="Specified products under government notification",
            status="unknown", source_url="https://www.bis.gov.in/",
        ))
    return QCOSearchResponse(results=results[:limit], total=len(results), query=q)


@router.post("/search", response_model=SearchResponse)
async def semantic_search(request: SearchRequest):
    chunks = await local_retrieve(request.query, top_k=request.top_k, source_types=request.source_types)
    results = [ChunkSearchResult(
        chunk_id=chunk["chunk_id"], document_id=chunk["document_id"],
        document_title=chunk["document_title"], chunk_text=chunk["chunk_text"],
        source_url=chunk.get("source_url"), source_type=chunk.get("source_type", "BIS"),
        score=chunk.get("final_score", 0.0), page_number=chunk.get("page_number"),
        section_title=chunk.get("section_title"), metadata=chunk.get("metadata", {}),
    ) for chunk in chunks]
    return SearchResponse(results=results, total=len(results), query=request.query)
