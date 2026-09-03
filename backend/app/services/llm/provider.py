"""
LLM provider abstraction — supports OpenAI-compatible APIs.
"""

from __future__ import annotations
import logging
import re
from abc import ABC, abstractmethod
from typing import List, Optional, AsyncGenerator

from app.config import settings

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: List[dict], **kwargs) -> str:
        ...

    @abstractmethod
    async def stream(self, messages: List[dict], **kwargs) -> AsyncGenerator[str, None]:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...


class OpenAICompatibleProvider(BaseLLMProvider):
    """Works with OpenAI, Groq, Together, Mistral, Ollama — any OpenAI-compatible API."""

    def __init__(self):
        try:
            from openai import AsyncOpenAI
            kwargs = {"api_key": settings.LLM_API_KEY or "dummy"}
            if settings.LLM_BASE_URL:
                kwargs["base_url"] = settings.LLM_BASE_URL
            elif settings.LLM_PROVIDER == "groq":
                kwargs["base_url"] = "https://api.groq.com/openai/v1"
            elif settings.LLM_PROVIDER == "ollama":
                kwargs["base_url"] = settings.LLM_BASE_URL or "http://localhost:11434/v1"
            self._client = AsyncOpenAI(**kwargs)
            self._available = True
        except ImportError:
            logger.warning("openai package not found. LLM disabled.")
            self._client = None
            self._available = False

    @property
    def model_name(self) -> str:
        return settings.LLM_MODEL

    @property
    def available(self) -> bool:
        return self._available and bool(settings.LLM_API_KEY)

    async def complete(self, messages: List[dict], **kwargs) -> str:
        if not self.available:
            raise RuntimeError("LLM not configured.")
        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", settings.LLM_MAX_TOKENS),
                temperature=kwargs.get("temperature", settings.LLM_TEMPERATURE),
                timeout=settings.LLM_TIMEOUT,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM completion error: {e}")
            raise

    async def stream(self, messages: List[dict], **kwargs) -> AsyncGenerator[str, None]:
        if not self.available:
            yield "LLM not configured."
            return
        try:
            stream = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", settings.LLM_MAX_TOKENS),
                temperature=kwargs.get("temperature", settings.LLM_TEMPERATURE),
                stream=True,
                timeout=settings.LLM_TIMEOUT,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            yield f"\n\n[Error generating response: {e}]"


class FallbackProvider(BaseLLMProvider):
    """Returns retrieval-only responses when no LLM is configured."""

    @property
    def model_name(self) -> str:
        return "retrieval-only"

    async def complete(self, messages: List[dict], **kwargs) -> str:
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        context_marker = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        context_section = system_msg.rsplit("RETRIEVED CONTEXT", 1)[-1]
        context_parts = context_section.split(context_marker)
        context = context_parts[1].strip() if len(context_parts) > 1 else ""
        context = context.split(context_marker, 1)[0].strip()
        passages = re.split(r"\[Source \d+\][^\n]*\n", context)
        passages = [passage.strip() for passage in passages if passage.strip()]
        query_terms = set(re.findall(r"[a-z0-9]+", user_msg.lower()))
        passages.sort(key=lambda passage: len(query_terms & set(re.findall(r"[a-z0-9]+", passage.lower()))), reverse=True)
        passages = passages[:1]
        sentences = []
        for passage in passages:
            for sentence in re.split(r"(?<=[.!?])\s+", passage):
                sentence_terms = set(re.findall(r"[a-z0-9]+", sentence.lower()))
                score = len(query_terms & sentence_terms)
                if score:
                    sentences.append((score, sentence.strip()))
        sentences.sort(key=lambda item: item[0], reverse=True)
        answer = " ".join(sentence for _, sentence in sentences[:3])[:1000]
        answer = re.sub(r"^(?:URL|Source\s*&\s*Link):\s*\S+\s*", "", answer, flags=re.IGNORECASE)
        if not answer:
            answer = "I could not find a relevant answer in the supplied BIS knowledge documents."
        source_matches = re.findall(r"\[Source \d+\] ([^\n]+)", context)
        sources = "; ".join(source_matches[:2]) or "Supplied BIS knowledge documents"
        return (
            f"**Direct Answer:** {answer}\n\n"
            f"**Evidence:** The answer is based only on the most relevant indexed passage.\n\n"
            "**Applicable Standard or Regulation:** See the cited passage; verify the current official notification.\n\n"
            "**Practical Next Step:** Review the cited document and confirm the current requirement on the official BIS portal.\n\n"
            f"**Sources:** {sources}"
        )

    async def stream(self, messages: List[dict], **kwargs) -> AsyncGenerator[str, None]:
        result = await self.complete(messages, **kwargs)
        yield result


def get_llm_provider() -> BaseLLMProvider:
    """Factory — returns the best available provider."""
    provider = OpenAICompatibleProvider()
    if provider.available:
        logger.info(f"LLM provider: {settings.LLM_PROVIDER} ({settings.LLM_MODEL})")
        return provider
    logger.warning("No LLM API key configured. Using retrieval-only fallback.")
    return FallbackProvider()


# Singleton
_provider: Optional[BaseLLMProvider] = None


def llm() -> BaseLLMProvider:
    global _provider
    if _provider is None:
        _provider = get_llm_provider()
    return _provider
