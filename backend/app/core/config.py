"""
Application configuration management
"""

import os
from typing import List, Optional
from pydantic import validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Hybrid AI Location App"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALLOWED_HOSTS: List[str] = ["*"]
    # temporary mychanges
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    # http://127.0.0.1:5173,http://127.0.0.1:3000"
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/dev.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # External APIs
    CONTACT_EMAIL: str = "dev@example.com"
    EVENTBRITE_TOKEN: Optional[str] = None
    NEWSAPI_KEY: Optional[str] = None
    # Ticketmaster (alternative events provider)
    TICKETMASTER_API_KEY: Optional[str] = None
    
    # AI/LLM
    LLM_PROVIDER: str = "none"  # openrouter, openai, anthropic, none
    OPENROUTER_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_MODEL: str = "deepseek/deepseek-chat:free"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # Cache TTL (seconds)
    GEOCODE_CACHE_TTL: int = 604800  # 7 days
    CRIME_CACHE_TTL: int = 3600      # 1 hour
    EVENT_CACHE_TTL: int = 1800      # 30 minutes
    NEWS_CACHE_TTL: int = 900        # 15 minutes
    POI_CACHE_TTL: int = 86400       # 1 day
    
    # External API Timeouts (seconds)
    NOMINATIM_TIMEOUT: int = 10
    POLICE_API_TIMEOUT: int = 15
    EVENTBRITE_TIMEOUT: int = 15
    TICKETMASTER_TIMEOUT: int = 15
    NEWSAPI_TIMEOUT: int = 15
    OVERPASS_TIMEOUT: int = 30  # Increased to 30s to handle slower responses
    
    # External API URLs
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    POLICE_API_BASE_URL: str = "https://data.police.uk/api"
    EVENTBRITE_BASE_URL: str = "https://www.eventbriteapi.com/v3"
    TICKETMASTER_BASE_URL: str = "https://app.ticketmaster.com/discovery/v2"
    NEWSAPI_BASE_URL: str = "https://newsapi.org/v2"
    OVERPASS_BASE_URL: str = "https://overpass-api.de/api"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return self.CORS_ORIGINS
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()






