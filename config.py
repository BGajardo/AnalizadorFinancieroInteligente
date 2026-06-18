from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    
    DATABASE_URL: str

    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_URL: str      = "http://localhost:11434/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str    = "qwen3:8b"

    class Config:
        env_file = ".env"

settings = Settings()