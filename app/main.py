import time
import uuid
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.models import ChatRequest, ChatResponse
from app.llm_client import OllamaClient
from app.cache import RedisCache
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY, CACHE_HITS, CACHE_MISSES
from app.logging_config import setup_logging

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

logger = setup_logging()
llm_client = OllamaClient()
cache = RedisCache()


@app.get("/health/live")
async def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    return {
        "status": "ready",
        "model": settings.model_name,
    }


@app.get("/info")
async def info():
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "model": settings.model_name,
        "git_commit": settings.git_commit,
    }


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    cached_response = await cache.get(
        settings.model_name, request.prompt, request.temperature
    )

    if cached_response is not None:
        latency_ms = round((time.time() - start_time) * 1000, 2)

        CACHE_HITS.inc()
        REQUEST_COUNT.labels(status="success").inc()
        REQUEST_LATENCY.observe(time.time() - start_time)

        logger.info(
            "cache hit",
            extra={
                "request_id": request_id,
                "model": settings.model_name,
                "latency_ms": latency_ms,
                "status": 200,
            },
        )

        return ChatResponse(response=cached_response, model=settings.model_name)

    CACHE_MISSES.inc()

    try:
        result = await llm_client.generate(request.prompt, request.temperature)

        await cache.set(
            settings.model_name, request.prompt, request.temperature, result
        )

        latency_ms = round((time.time() - start_time) * 1000, 2)

        REQUEST_COUNT.labels(status="success").inc()
        REQUEST_LATENCY.observe(time.time() - start_time)

        logger.info(
            "chat request completed",
            extra={
                "request_id": request_id,
                "model": settings.model_name,
                "latency_ms": latency_ms,
                "status": 200,
            },
        )

        return ChatResponse(response=result, model=settings.model_name)

    except Exception as exc:
        latency_ms = round((time.time() - start_time) * 1000, 2)

        REQUEST_COUNT.labels(status="error").inc()
        REQUEST_LATENCY.observe(time.time() - start_time)

        logger.info(
            "chat request failed",
            extra={
                "request_id": request_id,
                "model": settings.model_name,
                "latency_ms": latency_ms,
                "status": 502,
            },
        )

        raise HTTPException(
            status_code=502,
            detail=f"LLM service unavailable: {exc}",
        )