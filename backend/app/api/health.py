"""
Health check endpoint.
"""

from datetime import datetime
from fastapi import APIRouter

from app.config import settings
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        database="disabled (local knowledge base)",
        embedding_model=settings.EMBEDDING_MODEL,
        llm_provider=settings.LLM_PROVIDER,
        llm_configured=bool(settings.LLM_API_KEY),
        timestamp=datetime.utcnow(),
    )
