"""
Intent classifier — rule-based with extensible LLM fallback interface.
Categorises user queries into 13 BIS-specific intent categories.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple
from app.schemas import IntentCategory
import logging

logger = logging.getLogger(__name__)

# ── Keyword patterns per intent ───────────────────────────────────────────────

INTENT_PATTERNS: dict[IntentCategory, list[str]] = {
    IntentCategory.QCO: [
        r"\bqco\b", r"quality control order", r"compulsory certification",
        r"mandatory for", r"enforcement date", r"notification date",
        r"notified product", r"qcos",
    ],
    IntentCategory.MANDATORY_CERTIFICATION: [
        r"\bmandatory\b", r"is .+ mandatory", r"compulsory",
        r"required by law", r"certification required",
        r"must be certified", r"need to certify",
    ],
    IntentCategory.LICENCE: [
        r"\blicen[sc]e\b", r"apply for.*bis", r"bis licen[sc]e",
        r"get.*certified", r"obtain.*licen[sc]e", r"licen[sc]ing",
        r"application.*bis", r"apply.*bis",
    ],
    IntentCategory.CERTIFICATION_PROCESS: [
        r"certification process", r"how.*certif", r"steps.*certif",
        r"scheme.*(i|iv|1|4)", r"factory.*assessment",
        r"surveillance", r"conformity assessment",
        r"testing requirement", r"scheme of inspection",
    ],
    IntentCategory.STANDARD_SEARCH: [
        r"\bis[\s\-]?\d+", r"indian standard", r"is number",
        r"find.*standard", r"which standard",
        r"standard.*number", r"standard for",
    ],
    IntentCategory.PRODUCT_STANDARD: [
        r"i manufacture", r"my product", r"which.*standard.*product",
        r"product.*standard", r"applicable standard",
        r"standard.*appli", r"for.*product",
    ],
    IntentCategory.BIS_MARK: [
        r"bis mark", r"isi mark", r"hallmark",
        r"certification mark", r"bis logo",
        r"verify.*bis", r"check.*bis.*mark",
    ],
    IntentCategory.CONSUMER_QUERY: [
        r"as a consumer", r"consumer", r"buy", r"purchased",
        r"fake.*bis", r"genuine.*bis", r"how to check",
        r"product.*safe", r"counterfeit",
    ],
    IntentCategory.MANUFACTURER_QUERY: [
        r"manufacturer", r"as a manufacturer",
        r"my factory", r"production", r"testing lab",
        r"lab.*requirement", r"factory.*setup",
    ],
    IntentCategory.DOCUMENT_SEARCH: [
        r"document", r"pdf", r"download", r"guidelines?",
        r"manual", r"circular", r"notification",
        r"gazette", r"regulation",
    ],
    IntentCategory.REGULATORY_QUERY: [
        r"bis act", r"bis rules?", r"regulation",
        r"legal.*requirement", r"law.*bis",
        r"conformity.*regulation", r"penalty", r"fine",
    ],
    IntentCategory.GENERAL_BIS: [
        r"what is bis", r"about bis", r"bureau of indian standards",
        r"bis services", r"bis portal",
        r"bis history", r"bis headquarter",
    ],
}


def classify_intent(query: str) -> Tuple[IntentCategory, float]:
    """
    Classify query intent using rule-based pattern matching.
    Returns (intent, confidence) where confidence is 0–1.
    """
    query_lower = query.lower().strip()

    scores: dict[IntentCategory, int] = {}
    for intent, patterns in INTENT_PATTERNS.items():
        count = sum(1 for p in patterns if re.search(p, query_lower))
        if count > 0:
            scores[intent] = count

    if not scores:
        return IntentCategory.UNKNOWN, 0.3

    best = max(scores, key=lambda k: scores[k])
    total_matches = sum(scores.values())
    confidence = min(0.95, 0.5 + (scores[best] / max(total_matches, 1)) * 0.45)

    logger.debug(f"Intent '{query[:60]}' → {best} (conf={confidence:.2f})")
    return best, round(confidence, 3)


def extract_entities(query: str) -> dict:
    """
    Extract BIS-specific entities from the query.
    Returns a dict with keys: is_number, product, qco_reference.
    """
    entities: dict = {}
    query_lower = query.lower()

    # IS number (e.g. IS 1234, IS-1234:2020, IS 4985)
    is_match = re.search(r"is[\s\-]?(\d{3,5})(?:[\s:]*(\d{4}))?", query_lower)
    if is_match:
        year_part = f":{is_match.group(2)}" if is_match.group(2) else ""
        entities["is_number"] = f"IS {is_match.group(1)}{year_part}"

    # QCO reference
    qco_match = re.search(r"qco[\s\-]?(?:no\.?\s*)?(\d+)", query_lower)
    if qco_match:
        entities["qco_reference"] = qco_match.group(0)

    # Product extraction — look for "for X" / "of X" / "I manufacture X" patterns
    product_patterns = [
        r"(?:for|of|manufacture[ds]?|making|produce[ds]?|product[:\s]+)\s+([a-z][a-z\s\-]{2,40}?)(?:\?|$|\.|,|\band\b)",
        r"(?:standard|certification|certif\w+)\s+(?:for|of)\s+([a-z][a-z\s\-]{2,40}?)(?:\?|$|\.|,)",
    ]
    for pat in product_patterns:
        m = re.search(pat, query_lower)
        if m:
            product = m.group(1).strip().rstrip(".,?")
            if len(product) > 2 and product not in ("all", "any", "the", "this", "a"):
                entities["product"] = product
                break

    return entities
