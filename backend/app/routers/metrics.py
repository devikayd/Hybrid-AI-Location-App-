"""
Metrics API endpoints for evaluation and monitoring

Provides endpoints to:
- View system performance metrics
- View ML model evaluation metrics
- Export metrics for analysis
- Reset metrics
"""

from fastapi import APIRouter, Query
from typing import Dict, Any, Optional
import logging

from app.core.metrics import metrics_collector
from app.core.circuit_breaker import get_circuit_breaker_metrics

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/metrics")
async def get_all_metrics() -> Dict[str, Any]:
    """
    Get all collected metrics including:
    - System uptime
    - Request latencies per endpoint
    - Cache hit/miss rates
    - External API success rates
    - Circuit breaker events
    - ML model evaluation metrics
    """
    all_metrics = metrics_collector.get_all_metrics()

    # Add circuit breaker state from the circuit breaker module
    all_metrics["circuit_breaker_states"] = get_circuit_breaker_metrics()

    return all_metrics


@router.get("/metrics/summary")
async def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a summary of key metrics for quick overview.

    Returns:
    - Response time P50/P95
    - Cache hit rate
    - API success rate
    - Total requests served
    """
    return {
        "summary": metrics_collector.get_summary(),
        "targets": {
            "response_time_p50_target_ms": 2000,
            "response_time_p95_target_ms": 5000,
            "cache_hit_rate_target_percent": 80,
            "api_success_rate_target_percent": 99
        }
    }


@router.get("/metrics/requests")
async def get_request_metrics() -> Dict[str, Any]:
    """
    Get detailed request latency metrics per endpoint.

    Returns P50, P95, P99, mean, min, max for each endpoint.
    """
    return {
        "endpoints": metrics_collector.get_request_metrics(),
        "description": "Latency values in milliseconds"
    }


@router.get("/metrics/cache")
async def get_cache_metrics() -> Dict[str, Any]:
    """
    Get cache performance metrics.

    Returns hit/miss counts and hit rate percentage for each cache type.
    """
    return {
        "caches": metrics_collector.get_cache_metrics(),
        "target_hit_rate_percent": 80
    }


@router.get("/metrics/apis")
async def get_api_metrics() -> Dict[str, Any]:
    """
    Get external API performance metrics.

    Returns success/failure counts, success rate, and latency stats for each API.
    """
    return {
        "apis": metrics_collector.get_api_metrics(),
        "target_success_rate_percent": 99
    }


@router.get("/metrics/ml")
async def get_ml_metrics() -> Dict[str, Any]:
    """
    Get ML model evaluation metrics.

    Returns R², RMSE, F1-score, etc. for each evaluated model.
    """
    return {
        "models": metrics_collector.get_ml_metrics(),
        "targets": {
            "safety_scoring": {"r2": 0.80, "rmse": "< 0.15"},
            "popularity_scoring": {"r2": 0.75, "rmse": "< 0.20"},
            "sentiment_analysis": {"f1": 0.75},
            "recommendations": {"precision_at_10": 0.45, "diversity": 0.80}
        }
    }


@router.post("/metrics/reset")
async def reset_metrics() -> Dict[str, str]:
    """
    Reset all collected metrics.

    Use this to start fresh measurements.
    """
    metrics_collector.reset()
    return {"status": "ok", "message": "All metrics have been reset"}


@router.get("/metrics/export")
async def export_metrics(
    format: str = Query("json", description="Export format: json or csv")
) -> Dict[str, Any]:
    """
    Export metrics for external analysis.

    Supports JSON format (CSV could be added if needed).
    """
    all_metrics = metrics_collector.get_all_metrics()

    if format == "csv":
        # For now, return a message about CSV support
        return {
            "message": "CSV export not yet implemented",
            "suggestion": "Use JSON format and convert externally"
        }

    return {
        "format": "json",
        "data": all_metrics,
        "export_timestamp": metrics_collector.get_all_metrics()["system"]["start_time"]
    }


@router.post("/metrics/evaluate-ml")
async def run_ml_evaluation(
    simulated: bool = Query(True, description="Use simulated metrics for demo")
) -> Dict[str, Any]:
    """
    Run ML model evaluation and store results.

    Set simulated=True (default) to use pre-computed metrics for demonstration.
    Set simulated=False to run actual evaluation (requires training data).
    """
    try:
        if simulated:
            from app.ml.model_evaluation import run_simulated_evaluation
            results = run_simulated_evaluation()
            return {
                "status": "ok",
                "message": "Simulated ML evaluation completed",
                "results": results
            }
        else:
            return {
                "status": "warning",
                "message": "Real evaluation requires training data. Use simulated=True for demo.",
                "results": {}
            }
    except Exception as e:
        logger.error(f"ML evaluation failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "results": {}
        }
