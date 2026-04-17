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

    # Chat feature
    CHAT_MODEL_MAX_TOKENS: int = 300
    CHAT_INPUT_MAX_CHARS: int = 1500
    CHAT_HISTORY_MAX_TURNS: int = 6
    CHAT_HISTORY_TTL_MINUTES: int = 15
    CHAT_ALLOWED_URL_DOMAINS: str = "discord.com"
    CHAT_DAILY_TOKEN_BUDGET: int = 200000

    # Chat-specific retrieval knobs. Kept separate from TOP_K_RESULTS (used by
    # FAQ/moddraft) so chat can tune for a shorter 60-word reply without
    # widening the FAQ retrieval budget. Score threshold is Chroma cosine
    # distance — chunks with distance ABOVE this are dropped so unrelated
    # questions return no context instead of noise the model can hallucinate
    # a grounded-sounding answer from.
    CHAT_TOP_K: int = 3
    CHAT_RETRIEVAL_SCORE_THRESHOLD: float = 0.7
    CHAT_REFERENCE_CHUNK_MAX_CHARS: int = 500

    # Observability (PR 7) — both must be overridden in production deployments.
    # The sentinel value "REPLACE_ME_WITH_SECRET" is intentional: it causes the
    # metrics endpoint to return 503 in any environment that hasn't been properly
    # configured, preventing silent operation with a weak default.
    CHAT_LOG_HMAC_SECRET: str = "REPLACE_ME_WITH_SECRET"
    CHAT_ADMIN_TOKEN: str = "REPLACE_ME_WITH_ADMIN_TOKEN"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
