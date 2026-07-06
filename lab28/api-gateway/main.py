from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

import httpx
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

try:
    from langsmith import traceable
except Exception:
    def traceable(*_args: Any, **_kwargs: Any):
        def decorator(func):
            return func
        return decorator

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("lab28.api_gateway")

app = FastAPI(title="Lab28 AI Platform API Gateway", version="1.0.0")
Instrumentator().instrument(app).expose(app)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
VLLM_TUNNEL_URL = (os.getenv("VLLM_TUNNEL_URL") or os.getenv("VLLM_URL") or "").rstrip("/")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4")
ENABLE_LLM_FALLBACK = os.getenv("ENABLE_LLM_FALLBACK", "true").lower() == "true"
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "1.2"))


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    embedding: Optional[list[float]] = None


class ChatResponse(BaseModel):
    answer: str
    latency_ms: float
    model: str
    fallback_used: bool = False
    context_items: int = 0
    error: Optional[str] = None


def normalize_embedding(embedding: Optional[list[float]]) -> list[float]:
    if not embedding:
        return [0.0] * 384
    vector = [float(x) for x in embedding[:384]]
    if len(vector) < 384:
        vector.extend([0.0] * (384 - len(vector)))
    return vector


async def vector_search(embedding: list[float]) -> tuple[list[dict[str, Any]], Optional[str]]:
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/documents/points/search",
                json={"vector": embedding, "limit": 3, "with_payload": True},
            )
        if response.status_code == 404:
            return [], "qdrant collection not found"
        response.raise_for_status()
        return response.json().get("result", []), None
    except Exception as exc:
        logger.warning("Vector search degraded: %s", exc)
        return [], str(exc)


def fallback_answer(query: str, context: list[dict[str, Any]], reason: str) -> str:
    return (
        "Fallback response from Lab28 API Gateway. "
        "Remote vLLM is unavailable or too slow, so the platform returned a safe local response. "
        f"Query: {query}. Context items: {len(context)}. Reason: {reason}."
    )


async def call_vllm_or_fallback(query: str, context: list[dict[str, Any]]) -> tuple[str, str, bool, Optional[str]]:
    if not VLLM_TUNNEL_URL:
        reason = "VLLM_TUNNEL_URL is not configured"
        if ENABLE_LLM_FALLBACK:
            return fallback_answer(query, context, reason), "fallback-local", True, reason
        raise RuntimeError(reason)

    prompt = (
        "You are the Lab28 platform assistant. Answer concisely using the retrieved context when useful.\n\n"
        f"Context: {context}\n\nQuery: {query}"
    )
    payload = {
        "model": VLLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 256,
    }

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{VLLM_TUNNEL_URL}/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
        return answer, data.get("model", VLLM_MODEL), False, None
    except Exception as exc:
        reason = str(exc)
        logger.warning("vLLM degraded: %s", reason)
        if ENABLE_LLM_FALLBACK:
            return fallback_answer(query, context, reason), "fallback-local", True, reason
        raise


@traceable(name="lab28_chat_pipeline", run_type="chain")
async def run_chat_pipeline(payload: ChatRequest) -> ChatResponse:
    started = time.time()
    embedding = normalize_embedding(payload.embedding)
    context, vector_error = await vector_search(embedding)
    answer, model, fallback_used, llm_error = await call_vllm_or_fallback(payload.query, context)
    latency_ms = round((time.time() - started) * 1000, 2)
    return ChatResponse(
        answer=answer,
        latency_ms=latency_ms,
        model=model,
        fallback_used=fallback_used,
        context_items=len(context),
        error=llm_error or vector_error,
    )


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    return await run_chat_pipeline(payload)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, Any]:
    return {
        "status": "ready",
        "qdrant_url": QDRANT_URL,
        "vllm_configured": bool(VLLM_TUNNEL_URL),
        "fallback_enabled": ENABLE_LLM_FALLBACK,
        "langsmith_project": os.getenv("LANGCHAIN_PROJECT", "lab28-platform"),
    }
