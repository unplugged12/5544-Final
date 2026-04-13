"""Application settings loaded from environment / .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM provider keys
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Provider selection
    PRIMARY_PROVIDER: str = "openai"
    FALLBACK_PROVIDER: str = "anthropic"

    # Model names
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # Data stores (defaults match Docker container paths via docker-compose volume mount)
    SQLITE_PATH: str = "/app/data/copilot.db"
    CHROMA_PERSIST_DIR: str = "/app/data/chroma"
    CHROMA_COLLECTION: str = "knowledge_base"

    # Embedding
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    TOP_K_RESULTS: int = 5

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
