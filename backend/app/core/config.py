from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    
    # Adding basic settings for the app
    APP_NAME: str = "Hybrid AI Location App"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/dev.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # External APIs
    CONTACT_EMAIL: str = "dev@example.com"
    EVENTBRITE_TOKEN: Optional[str] = None
    NEWSAPI_KEY: Optional[str] = None
    TICKETMASTER_API_KEY: Optional[str] = None
    
    # AI/LLM
    LLM_PROVIDER: str = "none"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    LLM_MODEL: str = "deepseek/deepseek-chat:free"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # Cache TTL (seconds)
    GEOCODE_CACHE_TTL: int = 604800  # 7 days
    CRIME_CACHE_TTL: int = 3600      # 1 hour
    EVENT_CACHE_TTL: int = 1800      # 30 minutes
    NEWS_CACHE_TTL: int = 900        # 15 minutes
    POI_CACHE_TTL: int = 86400       # 1 day
    
    # Real-time Data Filtering (for location data panel)
    # NOTE: The system now uses CASCADING FALLBACK for crimes and news:
    # - Crimes: Tries 7 days → 30 days → 60 days (shows first available)
    # - News: Tries 24 hours → 7 days → 14 days (shows first available)
    # These settings are kept for backward compatibility but cascading fallback takes precedence
    
    # Crimes: UK Police API provides monthly aggregated data (typically 1-2 months old)
    # Cascading fallback ensures data is shown even if older than expected
    CRIME_RECENT_DAYS: int = 90  # Legacy setting (cascading fallback: 7→30→60 days)
    # News: NewsAPI can provide very recent articles
    # Cascading fallback ensures data is shown even if older than expected
    NEWS_RECENT_HOURS: int = 168  # Legacy setting (cascading fallback: 24h→7d→14d)
    # Events: Show upcoming events and recent past
    EVENT_RECENT_HOURS: int = 24  # Show events from last N hours
    EVENT_FUTURE_HOURS: int = 168  # Show events in next N hours (7 days)
    
    # External API Timeouts (seconds)
    NOMINATIM_TIMEOUT: int = 10
    POLICE_API_TIMEOUT: int = 15
    TICKETMASTER_TIMEOUT: int = 15
    NEWSAPI_TIMEOUT: int = 15
    EVENTBRITE_TIMEOUT: int = 15
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
        return self.CORS_ORIGINS if isinstance(self.CORS_ORIGINS, list) else []
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()






