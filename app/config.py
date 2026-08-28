"""Application configuration settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LinkedIn session credentials
    # Obtained from logged-in browser session cookies
    LINKEDIN_LI_AT: Optional[str] = None
    LINKEDIN_JSESSIONID: Optional[str] = None
    LINKEDIN_COOKIE_STR: Optional[str] = None

    # Application settings
    APP_NAME: str = "LinkedIn Profile Scraper API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Optional API key for protecting this hosted API (if set, callers must provide X-API-Key header)
    API_KEY: Optional[str] = None

    # Caching settings
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 900  # 15 minutes
    CACHE_MAXSIZE: int = 256

    # Network timeouts and retry
    REQUEST_TIMEOUT_SECONDS: float = 20.0
    MAX_RETRIES: int = 2

    # User agent mimicking modern desktop browser
    DEFAULT_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )


settings = Settings()
