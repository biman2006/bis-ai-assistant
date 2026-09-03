"""
Document management API — upload PDFs, add URLs, list/delete documents.
"""

import os
import uuid
from typing import Optional, List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Document
from app.schemas import DocumentResponse, DocumentListResponse, DocumentURLRequest
from app.services.ingestion.document_service import (
    ingest_pdf, ingest_url, delete_document, reindex_document
)
from app.config import settings

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
    source_type: str = Form("BIS"),
    document_type: str = Form("pdf"),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF/TXT document for ingestion into the knowledge base."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB.")

    resolved_title = title or (file.filename or "Uploaded Document").replace(ext, "").strip()

    try:
        if ext == ".pdf":
            doc = await ingest_pdf(
                session=db,
                pdf_bytes=content,
                title=resolved_title,
                source_url=source_url,
                source_type=source_type,
                document_type=document_type,
                description=description,
            )
        else:
            text = content.decode("utf-8", errors="replace")
            from app.services.ingestion.document_service import ingest_text
            doc = await ingest_text(
                session=db,
                text=text,
                title=resolved_title,
                source_url=source_url,
                source_type=source_type,
                document_type=document_type,
                description=description,
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.post("/documents/url", response_model=DocumentResponse)
async def add_url(
    request: DocumentURLRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add a web URL to the knowledge base."""
    try:
        doc = await ingest_url(
            session=db,
            url=str(request.url),
            title=request.title,
            source_type=request.source_type,
            document_type=request.document_type,
            description=request.description,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"URL ingestion failed: {e}")

    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    source_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all documents in the knowledge base."""
    query = select(Document).where(Document.is_active == True)
    if source_type:
        query = query.where(Document.source_type == source_type)

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Paginated results
    query = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    docs = result.scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single document by ID."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.model_validate(doc)


@router.delete("/documents/{document_id}")
async def remove_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a document and all its chunks."""
    deleted = await delete_document(db, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": "Document deleted successfully.", "document_id": document_id}


@router.post("/documents/{document_id}/reindex")
async def reindex_doc(document_id: str, db: AsyncSession = Depends(get_db)):
    """Re-embed all chunks of a document (useful after model change)."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    count = await reindex_document(db, document_id)
    return {"message": f"Re-indexed {count} chunks.", "document_id": document_id}
