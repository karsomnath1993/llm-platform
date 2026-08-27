from fastapi import FastAPI, HTTPException

from app.config import settings
from app.models import ChatRequest, ChatResponse
from app.llm_client import OllamaClient
from app.cache import RedisCache


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

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
    }


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    
    cached_response = await cache.get(
        settings.model_name, request.prompt, request.temperature
    )
    
    if cached_response is not None:
        return ChatResponse(response=cached_response, model=settings.model_name)

    try:

        result = await llm_client.generate(
            request.prompt,
            request.temperature,
        )
        
        await cache.set(
            settings.model_name, request.prompt, request.temperature, result
        )

        return ChatResponse(
            response=result,
            model=settings.model_name,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=f"LLM service unavailable: {exc}",
        )