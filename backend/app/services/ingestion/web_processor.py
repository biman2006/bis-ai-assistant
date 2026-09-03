"""
Web page processor — fetches and extracts text from BIS web pages.
Uses httpx (async) + BeautifulSoup for HTML parsing.
"""

from __future__ import annotations
import hashlib
import logging
import re
from typing import Optional, List
from urllib.parse import urlparse

from app.services.ingestion.chunker import chunk_text, TextChunk

logger = logging.getLogger(__name__)

# Tags that typically contain body content
CONTENT_TAGS = ["article", "main", "section", "div", "p", "li", "td", "th"]
# Tags to remove entirely
REMOVE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]


def _clean_html_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


def extract_page_title(soup) -> str:
    """Try to extract the most meaningful title from a BIS page."""
    for sel in ["h1", "title", "h2"]:
        tag = soup.find(sel)
        if tag:
            return tag.get_text(strip=True)[:256]
    return "BIS Page"


async def fetch_and_process_url(
    url: str,
    document_title: Optional[str] = None,
    source_type: str = "BIS",
    extra_metadata: Optional[dict] = None,
    timeout: int = 30,
) -> tuple[List[TextChunk], dict, str]:
    """
    Fetch a URL and extract text content for ingestion.

    Returns:
        chunks: list of TextChunk
        page_meta: dict with title, url, etc.
        checksum: sha256 of raw HTML
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("httpx and beautifulsoup4 are required.")

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BIS-AI-Assistant/1.0; +https://bis.gov.in)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
        except httpx.HTTPError as e:
            raise ConnectionError(f"Failed to fetch {url}: {e}") from e

    checksum = hashlib.sha256(html.encode()).hexdigest()
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(REMOVE_TAGS):
        tag.decompose()

    title = document_title or extract_page_title(soup)

    # Try to get main content area
    main = (
        soup.find("main") or
        soup.find("div", {"id": re.compile(r"content|main", re.I)}) or
        soup.find("div", {"class": re.compile(r"content|main|page", re.I)}) or
        soup.body
    )

    if main is None:
        main = soup

    text = _clean_html_text(main.get_text(separator="\n", strip=True))

    if len(text) < 50:
        raise ValueError(f"Insufficient text content extracted from {url}")

    extra_metadata = extra_metadata or {}
    base_metadata = {
        "source_url": url,
        "source_type": source_type,
        "document_title": title,
        **extra_metadata,
    }

    chunks = chunk_text(text, base_metadata=base_metadata)

    page_meta = {
        "title": title,
        "url": url,
        "domain": urlparse(url).netloc,
        "text_length": len(text),
        "chunk_count": len(chunks),
    }

    logger.info(f"Web page processed: {url} → {len(chunks)} chunks")
    return chunks, page_meta, checksum


def process_raw_text(
    text: str,
    title: str,
    source_url: Optional[str] = None,
    source_type: str = "BIS",
    extra_metadata: Optional[dict] = None,
) -> tuple[List[TextChunk], dict, str]:
    """Process arbitrary text (for seeding)."""
    checksum = hashlib.sha256(text.encode()).hexdigest()
    extra_metadata = extra_metadata or {}
    base_metadata = {
        "source_url": source_url,
        "source_type": source_type,
        "document_title": title,
        **extra_metadata,
    }
    chunks = chunk_text(text, base_metadata=base_metadata)
    meta = {"title": title, "url": source_url, "text_length": len(text), "chunk_count": len(chunks)}
    return chunks, meta, checksum
