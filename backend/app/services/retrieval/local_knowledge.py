"""Small built-in BIS knowledge base used when database storage is disabled."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional


BUILTIN_CHUNKS = [
    {
        "chunk_id": "bis-overview",
        "document_id": "bis-overview",
        "document_title": "BIS Overview - Bureau of Indian Standards",
        "source_url": "https://www.bis.gov.in/",
        "source_type": "BIS",
        "chunk_text": "The Bureau of Indian Standards (BIS) is India's National Standards Body, established under the BIS Act, 2016. Its functions include formulating Indian Standards, product certification, hallmarking, laboratory testing, and consumer awareness.",
        "metadata": {},
    },
    {
        "chunk_id": "bis-certification",
        "document_id": "bis-certification",
        "document_title": "BIS Product Certification Overview",
        "source_url": "https://www.bis.gov.in/product-certification/product-certification-faq/?lang=en",
        "source_type": "BIS",
        "chunk_text": "BIS product certification allows a manufacturer to use the BIS Standard Mark (ISI Mark) when the product conforms to the relevant Indian Standard. Certification is generally voluntary unless a Quality Control Order makes it mandatory for a specific product.",
        "metadata": {},
    },
    {
        "chunk_id": "bis-process",
        "document_id": "bis-process",
        "document_title": "BIS Certification Process for Manufacturers",
        "source_url": "https://www.bis.gov.in/product-certification/product-certification-process/?lang=en",
        "source_type": "BIS",
        "chunk_text": "Manufacturers should identify the applicable Indian Standard, assess manufacturing and testing capability, prepare quality procedures, apply through the BIS online portal, complete the BIS assessment, and maintain conformity through surveillance.",
        "metadata": {},
    },
    {
        "chunk_id": "bis-qco",
        "document_id": "bis-qco",
        "document_title": "Quality Control Orders (QCOs)",
        "source_url": "https://www.bis.gov.in/",
        "source_type": "BIS",
        "chunk_text": "A Quality Control Order (QCO) is a Central Government notification that makes BIS certification mandatory for specified products. Once effective, covered products generally cannot be manufactured, sold, or imported without the required BIS certification and mark. Check the current notification and effective date on the official BIS portal.",
        "metadata": {},
    },
    {
        "chunk_id": "bis-standards",
        "document_id": "bis-standards",
        "document_title": "BIS Standards Portal",
        "source_url": "https://standards.bis.gov.in/",
        "source_type": "BIS",
        "chunk_text": "Indian Standards, including IS numbers and their scopes, can be searched on the BIS Standards Portal. The applicable standard depends on the product and its intended use, so manufacturers should verify the current standard before applying.",
        "metadata": {},
    },
    {
        "chunk_id": "bis-led-lamps",
        "document_id": "bis-led-lamps",
        "document_title": "BIS LED Lamps and Fixtures Guidance",
        "source_url": "https://www.bis.gov.in/product-certification/products-under-compulsory-certification/",
        "source_type": "BIS",
        "chunk_text": "For an electric bulb, first determine whether the product is a self-ballasted LED lamp or another lighting product and identify the current applicable Indian Standard. IS 16102 is listed in the BIS knowledge base for LED lamps and fixtures. The manufacturer should verify the current product scope and whether a Quality Control Order makes certification mandatory, then apply through the BIS product certification process with the required manufacturing, testing, and quality information.",
        "metadata": {"is_number": "IS 16102", "product": "LED lamps and fixtures", "verified": True},
    },
]


PDF_DIRECTORY = Path(__file__).resolve().parents[4] / "frontend"
PDF_PATHS = (
    PDF_DIRECTORY / "bis_rag_knowledge_dataset_modified.pdf",
    PDF_DIRECTORY / "Gazette-Notification.pdf",
    PDF_DIRECTORY / "BIS-CA-6th-Amendment-Regulations-2021-Gazette.pdf",
    PDF_DIRECTORY / "BIS-CA-4th-Amendment-Regulations-2021-Gazette.pdf",
)


def _load_pdf_chunks() -> List[dict]:
    """Extract searchable, page-aware passages from the supplied knowledge PDF."""
    try:
        import pymupdf as fitz

        chunks = []
        for pdf_path in PDF_PATHS:
            if not pdf_path.exists():
                continue
            document = fitz.open(pdf_path)
            filename = pdf_path.name.lower()
            is_amendment = "amendment" in filename
            amendment_number = "4th" if "4th" in filename else "6th"
            is_gazette = filename.startswith("gazette")
            document_id = (
                f"bis-ca-{amendment_number}-amendment-regulations-2021"
                if is_amendment
                else "bis-gazette-notification" if is_gazette else "bis-rag-knowledge-dataset"
            )
            document_title = (
                f"BIS {amendment_number} Amendment Regulations Gazette"
                if is_amendment
                else "BIS Gazette Notification" if is_gazette else "BIS RAG Knowledge Dataset"
            )
            source_type = "GAZETTE AMENDMENT" if is_amendment else "GAZETTE" if is_gazette else "BIS DATASET"
            for page_number, page in enumerate(document, start=1):
                text = re.sub(r"\s+", " ", page.get_text()).strip()
                if not text:
                    continue
                words = text.split()
                for offset in range(0, len(words), 220):
                    passage = " ".join(words[offset:offset + 260]).strip()
                    if len(passage) < 80:
                        continue
                    chunk_number = len(chunks) + 1
                    chunks.append({
                        "chunk_id": f"{document_id}-p{page_number}-{chunk_number}",
                        "document_id": document_id,
                        "document_title": document_title,
                        "source_url": None,
                        "source_type": source_type,
                        "page_number": page_number,
                        "chunk_text": passage,
                        "metadata": {"page": page_number, "source_file": pdf_path.name},
                    })
        if chunks:
            return chunks + BUILTIN_CHUNKS
    except Exception:
        pass
    return BUILTIN_CHUNKS


CHUNKS = _load_pdf_chunks()

STANDARDS = [
    {"id": "is-269", "is_number": "IS 269", "title": "Ordinary Portland Cement", "product": "Cement", "status": "current", "source_url": "https://standards.bis.gov.in/"},
    {"id": "is-1786", "is_number": "IS 1786", "title": "High Strength Deformed Steel Bars and Wires for Concrete Reinforcement", "product": "TMT Steel Bars", "status": "current", "source_url": "https://standards.bis.gov.in/"},
    {"id": "is-14543", "is_number": "IS 14543", "title": "Packaged Natural Mineral Water", "product": "Packaged Drinking Water", "status": "current", "source_url": "https://standards.bis.gov.in/"},
    {"id": "is-4151", "is_number": "IS 4151", "title": "Protective Helmets for Two Wheeler Riders", "product": "Two-Wheeler Helmet", "status": "current", "source_url": "https://standards.bis.gov.in/"},
    {"id": "is-16102", "is_number": "IS 16102", "title": "Self-ballasted LED Lamps for General Lighting Services", "product": "LED Lamps", "status": "current", "source_url": "https://standards.bis.gov.in/"},
]


def _terms(value: str) -> set[str]:
    stopwords = {"the", "and", "for", "how", "can", "you", "get", "want", "make", "with", "from", "this", "that", "are"}
    terms = {term for term in re.findall(r"[a-z0-9]+", value.lower()) if len(term) > 2 and term not in stopwords}
    aliases = {
        "bulb": {"led", "lamp", "lighting"},
        "electric": {"electrical", "led"},
        "approval": {"certification", "licence", "license"},
    }
    for term in list(terms):
        terms.update(aliases.get(term, set()))
    return terms


async def local_retrieve(query: str, top_k: int = 5, source_types: Optional[List[str]] = None) -> List[dict]:
    query_terms = {term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 2}
    expanded_query_terms = _terms(query)
    query_normalized = " ".join(query.lower().split())
    allowed = {value.upper() for value in source_types} if source_types else None
    ranked = []
    for chunk in CHUNKS:
        if allowed and chunk["source_type"].upper() not in allowed:
            continue
        searchable_text = f'{chunk["document_title"]} {chunk["chunk_text"]}'
        matched_terms = expanded_query_terms & _terms(searchable_text)
        matched_user_terms = query_terms & _terms(searchable_text)
        exact_phrase = query_normalized in searchable_text.lower()
        score = len(matched_user_terms) / max(len(query_terms), 1)
        if exact_phrase:
            score = min(1.0, score + 0.25)
        if score >= 0.08:
            result = dict(chunk)
            result["matched_terms"] = sorted(matched_terms)
            result["exact_match"] = exact_phrase
            result["keyword_score"] = round(score, 4)
            result["vector_score"] = round(score, 4)
            result["final_score"] = round(score, 4)
            ranked.append(result)
    ranked.sort(key=lambda item: item["final_score"], reverse=True)
    return ranked[:top_k]


def local_standard_search(query: str, limit: int = 10) -> List[dict]:
    terms = _terms(query)
    results = [item for item in STANDARDS if terms & _terms(" ".join(str(value) for value in item.values()))]
    return results[:limit]
