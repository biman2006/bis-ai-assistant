"""
RAG Pipeline — orchestrates the full retrieval-augmented generation flow:
query preprocessing → intent classification → hybrid retrieval → LLM generation.
"""

from __future__ import annotations
import logging
import time
import uuid
from typing import List, Optional, Tuple

from app.config import settings
from app.schemas import ChatResponse, SourceSchema, IntentCategory, ConfidenceLevel, ProductInfoSchema
from app.services.classification.intent_classifier import classify_intent, extract_entities
from app.services.retrieval.hybrid_retrieval import hybrid_retrieve
from app.services.llm.provider import llm
from app.services.llm.prompts import build_system_prompt, build_context_from_chunks

logger = logging.getLogger(__name__)


def _compute_confidence(chunks: List[dict], intent: IntentCategory) -> Tuple[float, ConfidenceLevel, str]:
    """Compute confidence score from retrieval quality."""
    if not chunks:
        return 0.0, ConfidenceLevel.NONE, "No relevant passage was found in the indexed documents."

    top_score = chunks[0].get("final_score", 0.0)
    avg_score = sum(c.get("final_score", 0.0) for c in chunks) / len(chunks)
    query_coverage = len(chunks[0].get("matched_terms", []))
    exact_bonus = 0.1 if chunks[0].get("exact_match") else 0.0
    evidence_bonus = 0.1 if chunks[0].get("metadata", {}).get("verified") else 0.0

    # Weight by number of distinct sources
    distinct_sources = len(set(c["document_id"] for c in chunks))
    source_bonus = min(0.1, distinct_sources * 0.025)

    confidence = min(0.98, top_score * 0.5 + avg_score * 0.2 + source_bonus + exact_bonus + evidence_bonus)

    if confidence >= settings.HIGH_CONFIDENCE_THRESHOLD:
        level = ConfidenceLevel.HIGH
    elif confidence >= settings.LOW_CONFIDENCE_THRESHOLD:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW

    reason = f"Top passage matched {query_coverage} query terms"
    if chunks[0].get("exact_match"):
        reason += " and included an exact phrase"
    if evidence_bonus:
        reason += "; the source is marked verified"
    return round(confidence, 3), level, reason + "."


def _build_sources(chunks: List[dict]) -> List[SourceSchema]:
    """Build deduplicated source list from retrieved chunks."""
    seen_urls: set = set()
    seen_doc_ids: set = set()
    sources: List[SourceSchema] = []

    for chunk in chunks:
        doc_id = chunk.get("document_id", "")
        url = chunk.get("source_url", "")

        # Deduplicate by document
        if doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)

        metadata = chunk.get("metadata", {})
        sources.append(SourceSchema(
            title=chunk.get("document_title", "BIS Document"),
            url=url or metadata.get("source_url"),
            source_type=chunk.get("source_type", "BIS"),
            page=chunk.get("page_number"),
            section=chunk.get("section_title"),
            is_number=metadata.get("is_number") or (
                metadata.get("is_numbers", [None])[0] if metadata.get("is_numbers") else None
            ),
            last_verified=metadata.get("last_verified"),
            chunk_id=chunk.get("chunk_id"),
            relevance_score=round(chunk.get("final_score", 0.0), 3),
        ))

    return sources[:6]  # Cap at 6 sources


def _build_product_info(entities: dict, chunks: List[dict]) -> Optional[ProductInfoSchema]:
    """Build structured product → standard → QCO info if applicable."""
    product = entities.get("product")
    is_number = entities.get("is_number")

    if not product and not is_number:
        return None

    # Try to extract from chunks
    standard_title = None
    qco_status = None
    mandatory_status = None
    effective_date = None
    source_url = None

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        text = chunk.get("chunk_text", "").lower()

        if not standard_title and meta.get("is_numbers"):
            is_nums = meta["is_numbers"]
            if is_nums:
                standard_title = f"Refer to {', '.join(is_nums)}"

        if "mandatory" in text or "compulsory" in text:
            mandatory_status = "Mandatory (via QCO)"
        elif "voluntary" in text:
            mandatory_status = "Voluntary"

        if "qco" in text or "quality control order" in text:
            qco_status = "QCO applicable (verify current status at bis.gov.in)"

        if not source_url and chunk.get("source_url"):
            source_url = chunk["source_url"]

    if not any([standard_title, qco_status, mandatory_status]):
        return None

    return ProductInfoSchema(
        product=product,
        applicable_standard=is_number or "Search at standards.bis.gov.in",
        standard_title=standard_title,
        certification_scheme="BIS Product Certification",
        qco_status=qco_status or "Check bis.gov.in/upcoming-qcos",
        mandatory_status=mandatory_status or "Verify at bis.gov.in",
        effective_date=effective_date,
        next_steps=[
            "Identify the applicable Indian Standard at standards.bis.gov.in",
            "Check if your product falls under a QCO at bis.gov.in",
            "Apply for BIS licence through the BIS online portal",
            "Ensure manufacturing premises meet BIS requirements",
        ],
        source_url=source_url,
    )


INSUFFICIENT_CONTEXT_RESPONSE = """I could not find sufficient information in the available BIS knowledge base to answer this question confidently.

For accurate and up-to-date information, I recommend:
- **BIS Official Portal**: https://www.bis.gov.in/
- **BIS Standards Portal**: https://standards.bis.gov.in/
- **Products under Compulsory Certification**: https://www.bis.gov.in/product-certification/products-under-compulsory-certification/
- **BIS Contact**: +91-11-23236626

Please try a more specific query — for example, include the product name, IS number, or specific BIS service you need."""


async def run_rag_pipeline(
    query: str,
    session=None,
    session_id: Optional[str] = None,
    language: str = "en",
) -> ChatResponse:
    """
    Full RAG pipeline execution.
    """
    start_time = time.monotonic()
    session_id = session_id or str(uuid.uuid4())

    # Step 1: Intent classification + entity extraction
    intent, intent_confidence = classify_intent(query)
    entities = extract_entities(query)

    logger.info(f"Query: '{query[:80]}' | Intent: {intent} | Entities: {entities}")

    # Step 2: Hybrid retrieval
    try:
        chunks = await hybrid_retrieve(
            session=session,
            query=query,
            top_k=settings.TOP_K,
            rerank_top_k=settings.RERANK_TOP_K,
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        chunks = []

    # Step 3: Confidence scoring
    confidence, confidence_level, confidence_reason = _compute_confidence(chunks, intent)

    # Step 4: Build sources
    sources = _build_sources(chunks)

    # Step 5: LLM generation
    answer = ""
    if not chunks:
        answer = INSUFFICIENT_CONTEXT_RESPONSE
        confidence = 0.0
        confidence_level = ConfidenceLevel.NONE
        confidence_reason = "No relevant passage was found in the indexed documents."
    else:
        context = build_context_from_chunks(chunks[:settings.RERANK_TOP_K])
        system_prompt = build_system_prompt(context, language)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        try:
            llm_provider = llm()
            answer = await llm_provider.complete(messages)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            from app.services.llm.provider import FallbackProvider
            answer = await FallbackProvider().complete(messages)

    # Step 6: Product info (for manufacturer queries)
    product_info = None
    if intent in (IntentCategory.PRODUCT_STANDARD, IntentCategory.MANUFACTURER_QUERY, IntentCategory.MANDATORY_CERTIFICATION):
        product_info = _build_product_info(entities, chunks)

    # Step 7: Log query
    latency_ms = int((time.monotonic() - start_time) * 1000)
    return ChatResponse(
        answer=answer,
        confidence=confidence,
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
        intent=intent,
        sources=sources,
        retrieved_chunks=len(chunks),
        session_id=session_id,
        latency_ms=latency_ms,
        product_info=product_info,
    )


