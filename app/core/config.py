from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "Socialix AI Agent Office Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database & Supabase (PostgreSQL)
    # Default to sqlite for local testing/demo if postgres url is not yet provided,
    # but designed natively for Supabase PostgreSQL (asyncpg / psycopg).
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        description="Supabase PostgreSQL connection string (asyncpg driver)"
    )
    POSTGRES_SYNC_URL: Optional[str] = Field(
        default=None,
        description="Sync PostgreSQL URL for LangGraph checkpointer (psycopg driver)"
    )
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # Security & JWT
    SECRET_KEY: str = "socialix-super-secret-production-key-change-in-prod"
    AGENT_SERVICE_JWT_SECRET: str = "socialix-agent-jwt-secret-shared-with-bff"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Google Gemini LLM
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_PRO_MODEL: str = "gemini-1.5-pro"
    GEMINI_FLASH_MODEL: str = "gemini-1.5-flash"

    # LangSmith Observability
    LANGSMITH_API_KEY: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGSMITH_TRACING: bool = True
    LANGCHAIN_TRACING_V2: bool = True
    LANGSMITH_PROJECT: str = "socialix-agents-dev"
    LANGCHAIN_PROJECT: str = "socialix-agents-dev"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    # Social Gateway Integrations (Make.com Webhook / Postiz / Blotato / Meta)
    SOCIAL_WEBHOOK_URL: Optional[str] = None
    META_PAGE_ACCESS_TOKEN: Optional[str] = None
    META_INSTAGRAM_ACCOUNT_ID: Optional[str] = None
    POSTIZ_API_KEY: Optional[str] = None
    POSTIZ_BASE_URL: str = "https://my-postiz.onrender.com"
    BLOTATO_API_KEY: Optional[str] = None
    BLOTATO_BASE_URL: str = "https://api.blotato.com/v1"
    BLOTATO_WEBHOOK_SECRET: Optional[str] = None
    IMAGEKIT_PUBLIC_KEY: Optional[str] = None
    IMAGEKIT_PRIVATE_KEY: Optional[str] = None
    IMAGEKIT_URL_ENDPOINT: Optional[str] = None
    E2B_API_KEY: Optional[str] = None

    # Agent Limits & Quotas
    MAX_GRAPH_STEPS: int = 25
    RUN_TIMEOUT_SECONDS: int = 600
    MAX_POSTS_PER_RUN: int = 10
    MAX_REVISIONS_PER_POST: int = 2

    # CORS Origins (includes deployed UI & local dev)
    CORS_ORIGINS: List[str] = [
        "https://socialmedia-ashen-iota.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "*"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("DATABASE_URL", mode="before")
    def assemble_db_connection(cls, v: Optional[str]) -> str:
        if not v:
            return "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
        # If user provides a standard postgres:// or postgresql:// URI, adapt for asyncpg
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
