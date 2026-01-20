"""
Health check endpoints
"""

from fastapi import APIRouter
from typing import Dict, Any
import asyncio
import logging

from app.core.redis import get_redis
from app.core.config import settings
from app.core.circuit_breaker import get_circuit_breaker_metrics

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def status_check() -> Dict[str, Any]:
    """
    Basic status check endpoint
    """
    return {
        "status": "ok",
        "service": "Hybrid AI Location App API",
        "version": settings.VERSION
    }


@router.get("/status/detailed")
async def detailed_status_check() -> Dict[str, Any]:
    """
    Detailed status check with upstream service status
    """
    health_status = {
        "status": "ok",
        "service": "Hybrid AI Location App API",
        "version": settings.VERSION,
        "checks": {}
    }
    
    # Check Redis connection
    try:
        redis = await get_redis()
        await asyncio.wait_for(redis.ping(), timeout=5.0)
        health_status["checks"]["redis"] = {
            "status": "healthy",
            "message": "Redis connection successful"
        }
    except asyncio.TimeoutError:
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "message": "Redis connection timeout"
        }
        health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Check external API configurations
    llm_provider = settings.LLM_PROVIDER.lower()
    llm_configured = False
    if llm_provider == "openrouter":
        llm_configured = bool(settings.OPENROUTER_API_KEY)

    api_configs = {
        "eventbrite": settings.EVENTBRITE_TOKEN is not None,
        "newsapi": settings.NEWSAPI_KEY is not None,
        "llm": llm_provider != "none" and llm_configured,
        "llm_provider": settings.LLM_PROVIDER,
    }
    
    health_status["checks"]["external_apis"] = {
        "status": "healthy" if all(api_configs.values()) else "degraded",
        "configurations": api_configs
    }

    # Check circuit breakers
    circuit_breaker_metrics = get_circuit_breaker_metrics()
    circuit_breaker_status = "healthy"
    open_circuits = []
    for name, metrics in circuit_breaker_metrics.items():
        if metrics.get("state") == "open":
            circuit_breaker_status = "degraded"
            open_circuits.append(name)

    health_status["checks"]["circuit_breakers"] = {
        "status": circuit_breaker_status,
        "open_circuits": open_circuits,
        "metrics": circuit_breaker_metrics
    }

    # Overall status determination
    if health_status["status"] == "ok":
        unhealthy_checks = [
            check for check in health_status["checks"].values()
            if check.get("status") == "unhealthy"
        ]
        if unhealthy_checks:
            health_status["status"] = "degraded"
    
    return health_status


