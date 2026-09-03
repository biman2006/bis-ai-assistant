"""
Pydantic schemas for request/response validation.
"""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class IntentCategory(str, Enum):
    GENERAL_BIS = "GENERAL_BIS"
    STANDARD_SEARCH = "STANDARD_SEARCH"
    PRODUCT_STANDARD = "PRODUCT_STANDARD"
    MANDATORY_CERTIFICATION = "MANDATORY_CERTIFICATION"
    QCO = "QCO"
    CERTIFICATION_PROCESS = "CERTIFICATION_PROCESS"
    LICENCE = "LICENCE"
    BIS_MARK = "BIS_MARK"
    CONSUMER_QUERY = "CONSUMER_QUERY"
    MANUFACTURER_QUERY = "MANUFACTURER_QUERY"
    DOCUMENT_SEARCH = "DOCUMENT_SEARCH"
    REGULATORY_QUERY = "REGULATORY_QUERY"
    UNKNOWN = "UNKNOWN"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


# ── Source / Citation ─────────────────────────────────────────────────────────

class SourceSchema(BaseModel):
    title: str
    url: Optional[str] = None
    source_type: str = "BIS"
    page: Optional[int] = None
    section: Optional[str] = None
    is_number: Optional[str] = None
    last_verified: Optional[str] = None
    chunk_id: Optional[str] = None
    relevance_score: Optional[float] = None


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    language: str = Field(default="en", pattern="^(en|hi|bn)$")
    stream: bool = False


class ProductInfoSchema(BaseModel):
    """Structured product -> standard -> QCO breakdown."""
    product: Optional[str] = None
    applicable_standard: Optional[str] = None
    standard_title: Optional[str] = None
    certification_scheme: Optional[str] = None
    qco_status: Optional[str] = None
    mandatory_status: Optional[str] = None
    effective_date: Optional[str] = None
    next_steps: Optional[List[str]] = None
    source_url: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    confidence_reason: Optional[str] = None
    intent: IntentCategory
    sources: List[SourceSchema] = []
    retrieved_chunks: int = 0
    disclaimer: str = "Information is based on available official BIS sources. Verify current requirements before compliance decisions."
    session_id: Optional[str] = None
    latency_ms: Optional[int] = None
    product_info: Optional[ProductInfoSchema] = None


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    source_url: Optional[str] = None
    source_type: str = "BIS"
    organization: Optional[str] = "BIS"
    document_type: str = "other"
    description: Optional[str] = None
    language: str = "en"


class DocumentCreate(DocumentBase):
    pass


class DocumentURLRequest(BaseModel):
    url: str
    title: Optional[str] = None
    source_type: str = "BIS"
    document_type: str = "webpage"
    description: Optional[str] = None


class DocumentResponse(DocumentBase):
    id: str
    chunk_count: int = 0
    is_active: bool = True
    last_verified: Optional[date] = None
    published_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    file_path: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


# ── Standards ─────────────────────────────────────────────────────────────────

class StandardResponse(BaseModel):
    id: str
    is_number: str
    title: str
    product: Optional[str] = None
    scope: Optional[str] = None
    status: str = "unknown"
    publication_date: Optional[date] = None
    revision: Optional[str] = None
    source_url: Optional[str] = None
    last_verified: Optional[date] = None
    certification_status: str = "unknown"
    related_qco: Optional[str] = None

    class Config:
        from_attributes = True


class StandardSearchResponse(BaseModel):
    results: List[StandardResponse]
    total: int
    query: str


# ── QCOs ─────────────────────────────────────────────────────────────────────

class QCOResponse(BaseModel):
    id: str
    qco_title: str
    product: Optional[str] = None
    is_number: Optional[str] = None
    notification_date: Optional[date] = None
    effective_date: Optional[date] = None
    status: str = "unknown"
    ministry: Optional[str] = None
    source_url: Optional[str] = None
    last_verified: Optional[date] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class QCOSearchResponse(BaseModel):
    results: List[QCOResponse]
    total: int
    query: str


# ── Search ────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    source_types: Optional[List[str]] = None


class ChunkSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    chunk_text: str
    source_url: Optional[str]
    source_type: str
    score: float
    page_number: Optional[int]
    section_title: Optional[str]
    metadata: Dict[str, Any] = {}


class SearchResponse(BaseModel):
    results: List[ChunkSearchResult]
    total: int
    query: str


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    embedding_model: str
    llm_provider: str
    llm_configured: bool
    timestamp: datetime
