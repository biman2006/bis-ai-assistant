"""
Chat API endpoint — runs the full RAG pipeline.
"""

import uuid
from fastapi import APIRouter, HTTPException

from app.schemas import ChatRequest, ChatResponse
from app.services.rag.pipeline import run_rag_pipeline

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
):
    """
    Main chat endpoint — processes a user query through the full RAG pipeline
    and returns a grounded answer with source citations.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    session_id = request.session_id or str(uuid.uuid4())

    response = await run_rag_pipeline(
        query=request.query,
        session_id=session_id,
        language=request.language,
    )
    return response
