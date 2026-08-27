import hashlib
import json

import redis.asyncio as redis

from app.config import settings

class RedisCache:
    def __init__(self):
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
        
    def _make_key(self, model: str, prompt: str, temperature: float) -> str:
        raw = f"{model}:{prompt}:{temperature}"
        return "chat:" + hashlib.sha256(raw.encode()).hexdigest()
    
    async def get(self, model: str, prompt: str, temperature: float) -> str | None:
        key = self._make_key(model, prompt, temperature)
        cached = await self.client.get(key)
        if cached is None:
            return None
        return json.loads(cached)["response"]

    async def set(self, model: str, prompt: str, temperature: float, response: str, ttl: int = 300):
        key = self._make_key(model, prompt, temperature)
        value = json.dumps({"response": response})
        await self.client.set(key, value, ex=ttl)