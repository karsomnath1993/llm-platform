from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "LLM Platform"
    app_version: str = "1.5.0"

    ollama_url: str = "http://localhost:11434"
    model_name: str = "qwen3:0.6b"

    redis_url: str = "redis://localhost:6379"

    request_timeout: float = 120.0

    git_commit: str = "unknown"

    class Config:
        env_file = ".env"
        
settings = Settings()