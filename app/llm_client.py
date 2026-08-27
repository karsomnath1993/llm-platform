import httpx

from app.config import settings


class OllamaClient:

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
    ) -> str:

        payload = {
            "model": settings.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        async with httpx.AsyncClient(
            timeout=settings.request_timeout
        ) as client:

            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

            return data["response"]