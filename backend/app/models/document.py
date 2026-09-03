"""
SQLAlchemy ORM models for all database tables.
"""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List
import uuid

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, Date,
    ForeignKey, JSON, Enum as SAEnum, Index, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from pgvector.sqlalchemy import Vector
import enum

from app.database import Base
from app.config import settings


# ── Enums ─────────────────────────────────────────────────────────────────────

class SourceType(str, enum.Enum):
    BIS = "BIS"
    GOVERNMENT = "GOVERNMENT"
    GAZETTE = "GAZETTE"
    MINISTRY = "MINISTRY"
    OTHER = "OTHER"


class DocumentType(str, enum.Enum):
    WEBPAGE = "webpage"
    PDF = "pdf"
    GUIDANCE = "guidance"
    FAQ = "faq"
    ACT = "act"
    REGULATION = "regulation"
    NOTIFICATION = "notification"
    STANDARD = "standard"
    OTHER = "other"


class StandardStatus(str, enum.Enum):
    CURRENT = "current"
    WITHDRAWN = "withdrawn"
    UNDER_REVISION = "under_revision"
    DRAFT = "draft"
    UNKNOWN = "unknown"


class QCOStatus(str, enum.Enum):
    NOTIFIED = "notified"
    EFFECTIVE = "effective"
    UPCOMING = "upcoming"
    AMENDED = "amended"
    UNKNOWN = "unknown"


class CertificationStatus(str, enum.Enum):
    MANDATORY = "mandatory"
    VOLUNTARY = "voluntary"
    UNKNOWN = "unknown"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ── Documents ─────────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType), default=SourceType.OTHER)
    organization: Mapped[Optional[str]] = mapped_column(String(256), default="BIS")
    document_type: Mapped[DocumentType] = mapped_column(SAEnum(DocumentType), default=DocumentType.OTHER)
    published_date: Mapped[Optional[date]] = mapped_column(Date)
    last_verified: Mapped[Optional[date]] = mapped_column(Date)
    language: Mapped[str] = mapped_column(String(16), default="en")
    checksum: Mapped[Optional[str]] = mapped_column(String(64))  # sha256 for dedup
    file_path: Mapped[Optional[str]] = mapped_column(String(1024))
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    chunks: Mapped[List["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_documents_source_url", "source_url"),
        Index("ix_documents_source_type", "source_type"),
        Index("ix_documents_checksum", "checksum"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    section_title: Mapped[Optional[str]] = mapped_column(String(512))
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(settings.EMBEDDING_DIM))
    # Full-text search vector
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)
    # Rich metadata as JSON
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_embedding", "embedding", postgresql_using="ivfflat",
              postgresql_with={"lists": 100}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )


# ── Standards ─────────────────────────────────────────────────────────────────

class Standard(Base):
    __tablename__ = "standards"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    is_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    product: Mapped[Optional[str]] = mapped_column(String(512))
    scope: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[StandardStatus] = mapped_column(SAEnum(StandardStatus), default=StandardStatus.UNKNOWN)
    publication_date: Mapped[Optional[date]] = mapped_column(Date)
    revision: Mapped[Optional[str]] = mapped_column(String(64))
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    last_verified: Mapped[Optional[date]] = mapped_column(Date)
    related_qco: Mapped[Optional[str]] = mapped_column(String(256))
    certification_status: Mapped[CertificationStatus] = mapped_column(SAEnum(CertificationStatus), default=CertificationStatus.UNKNOWN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_standards_is_number", "is_number"),
        Index("ix_standards_product", "product"),
    )


# ── QCOs ─────────────────────────────────────────────────────────────────────

class QCO(Base):
    __tablename__ = "qcos"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    qco_title: Mapped[str] = mapped_column(String(1024), nullable=False)
    product: Mapped[Optional[str]] = mapped_column(String(512))
    is_number: Mapped[Optional[str]] = mapped_column(String(256))
    notification_date: Mapped[Optional[date]] = mapped_column(Date)
    effective_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[QCOStatus] = mapped_column(SAEnum(QCOStatus), default=QCOStatus.UNKNOWN)
    ministry: Mapped[Optional[str]] = mapped_column(String(256))
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    gazette_number: Mapped[Optional[str]] = mapped_column(String(128))
    last_verified: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_qcos_product", "product"),
        Index("ix_qcos_is_number", "is_number"),
        Index("ix_qcos_status", "status"),
    )


# ── Products ─────────────────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_name: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(256))
    is_number: Mapped[Optional[str]] = mapped_column(String(256))
    mandatory_status: Mapped[CertificationStatus] = mapped_column(SAEnum(CertificationStatus), default=CertificationStatus.UNKNOWN)
    qco_reference: Mapped[Optional[str]] = mapped_column(String(512))
    source_url: Mapped[Optional[str]] = mapped_column(String(2048))
    last_verified: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_products_product_name", "product_name"),
        Index("ix_products_category", "category"),
    )


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_chat_sessions_session_id", "session_id"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(64))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    sources: Mapped[Optional[dict]] = mapped_column(JSON)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("ix_chat_messages_session_id", "session_id"),
    )


# ── Query Logs ────────────────────────────────────────────────────────────────

class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    query: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(64))
    retrieval_count: Mapped[int] = mapped_column(Integer, default=0)
    top_sources: Mapped[Optional[list]] = mapped_column(JSON)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    llm_used: Mapped[Optional[str]] = mapped_column(String(128))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
