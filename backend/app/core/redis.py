"""
Redis configuration and connection management
"""

import redis.asyncio as redis
import json
import logging
from typing import Any, Optional, Union
from datetime import timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis connection
redis_client: Optional[redis.Redis] = None


async def init_redis():
    """Initialize Redis connection"""
    global redis_client
    
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("Redis connection established successfully")
        
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        logger.warning("Running without Redis cache - some features may be slower")
        redis_client = None


async def get_redis() -> Optional[redis.Redis]:
    """Get Redis client instance"""
    if redis_client is None:
        await init_redis()
    return redis_client


class RedisCache:
    """Redis cache manager"""
    
    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            redis = await get_redis()
            if redis is None:
                return None
            value = await redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in cache"""
        try:
            redis = await get_redis()
            if redis is None:
                return False
            ttl = ttl or self.default_ttl
            
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            
            await redis.setex(
                key, 
                ttl, 
                json.dumps(value, default=str)
            )
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            redis = await get_redis()
            if redis is None:
                return False
            await redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            redis = await get_redis()
            if redis is None:
                return False
            return await redis.exists(key) > 0
        except Exception as e:
            logger.warning(f"Cache exists error for key {key}: {e}")
            return False
    
    def generate_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from prefix and parameters"""
        params = "_".join(f"{k}_{v}" for k, v in sorted(kwargs.items()))
        return f"{prefix}:{params}" if params else prefix


# Cache instances for different data types
geocode_cache = RedisCache(default_ttl=settings.GEOCODE_CACHE_TTL)
crime_cache = RedisCache(default_ttl=settings.CRIME_CACHE_TTL)
event_cache = RedisCache(default_ttl=settings.EVENT_CACHE_TTL)
news_cache = RedisCache(default_ttl=settings.NEWS_CACHE_TTL)
poi_cache = RedisCache(default_ttl=settings.POI_CACHE_TTL)






