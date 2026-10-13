from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Configuration
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: Literal["google", "groq"] = "google"
    LLM_MODEL: str = "gemini-3.6-flash"
    
    # Search
    TAVILY_API_KEY: str = ""
    
    # Database
    DATABASE_URL: str = "postgresql://irium:irium_password@localhost:5432/irium_db"
    
    # Application
    APP_ENV: Literal["development", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: str = "pdf,png,jpg,jpeg,webp,docx,txt"
    MAX_DOCUMENT_PAGES: int = 100
    
    # Research Configuration
    MAX_RETRIES: int = 2
    SEARCH_MAX_RESULTS: int = 10
    
    # Authentication
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # PII Detection and Protection
    PII_DETECTION_ENABLED: bool = True
    PII_POLICY: Literal["REDACT", "BLOCK", "MASK", "LOG_ONLY"] = "REDACT"
    
    # Redis and Caching Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    CACHE_DEFAULT_TTL: int = 3600
    CACHE_STABLE_TTL: int = 86400
    CACHE_VOLATILE_TTL: int = 300

    # Rate Limiting & Concurrency Controls
    LLM_GLOBAL_CONCURRENCY: int = 2
    LLM_REQUESTS_PER_MINUTE: int = 25
    LLM_MAX_RETRY_ATTEMPTS: int = 2
    LLM_BACKOFF_BASE_SECONDS: float = 1.5

    # Per-Request Budget Limits
    BUDGET_MAX_LLM_CALLS: int = 10 # Increased from 5 to accommodate COMPLEX route (router + planner + 2-3 readers + writer + optional critic)
    BUDGET_MAX_TOOL_EXECUTIONS: int = 3
    BUDGET_MAX_RETRIES: int = 2
    BUDGET_MAX_GRAPH_ITERATIONS: int = 2
    BUDGET_TIMEOUT_SECONDS: float = 30.0

    # Groq Model Assignments
    GROQ_MODEL_COMPLEX: str = "openai/gpt-oss-120b"
    GROQ_MODEL_STANDARD: str = "openai/gpt-oss-20b"
    GROQ_MODEL_ALTERNATIVE: str = "qwen/qwen3.8-27b"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
