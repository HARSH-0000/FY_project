from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Configuration
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: Literal["google", "groq"] = "google"
    LLM_MODEL: str = "gemini-1.5-flash"
    
    # Search
    TAVILY_API_KEY: str = ""
    
    # Database
    DATABASE_URL: str = "postgresql://irium:irium_password@localhost:5432/irium_db"
    
    # Application
    APP_ENV: Literal["development", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: str = "pdf,docx,txt"
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
