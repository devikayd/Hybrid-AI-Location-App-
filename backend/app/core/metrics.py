"""
Metrics Collection Module for Evaluation

This module provides comprehensive metrics collection for:
1. System Performance: Response times, cache hits, API success rates
2. ML Model Evaluation: R², RMSE, F1-Score, Precision@K

Metrics are stored in-memory and can be exported via the /metrics endpoint.
"""

import time
import logging
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class LatencyStats:
    """Statistics for latency measurements"""
    values: List[float] = field(default_factory=list)
    max_samples: int = 1000  # Keep last 1000 samples

    def add(self, value: float):
        """Add a latency value in seconds"""
        self.values.append(value)
        # Keep only recent samples
        if len(self.values) > self.max_samples:
            self.values = self.values[-self.max_samples:]

    def percentile(self, p: float) -> Optional[float]:
        """Calculate percentile (0-100)"""
        if not self.values:
            return None
        sorted_values = sorted(self.values)
        index = int(len(sorted_values) * p / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]

    def mean(self) -> Optional[float]:
        """Calculate mean latency"""
        if not self.values:
            return None
        return statistics.mean(self.values)

    def get_stats(self) -> Dict[str, Any]:
        """Get all statistics"""
        if not self.values:
            return {"count": 0, "p50": None, "p95": None, "p99": None, "mean": None}
        return {
            "count": len(self.values),
            "p50": round(self.percentile(50) * 1000, 2),  # Convert to ms
            "p95": round(self.percentile(95) * 1000, 2),
            "p99": round(self.percentile(99) * 1000, 2),
            "mean": round(self.mean() * 1000, 2),
            "min": round(min(self.values) * 1000, 2),
            "max": round(max(self.values) * 1000, 2),
        }


class MetricsCollector:
    """
    Central metrics collector for the application.

    Collects:
    - Request latencies per endpoint
    - Cache hit/miss rates
    - External API success/failure rates
    - Circuit breaker events
    - ML model evaluation metrics
    """

    def __init__(self):
        # Request latencies by endpoint
        self.request_latencies: Dict[str, LatencyStats] = defaultdict(LatencyStats)

        # Cache metrics
        self.cache_hits: Dict[str, int] = defaultdict(int)
        self.cache_misses: Dict[str, int] = defaultdict(int)

        # API metrics
        self.api_calls: Dict[str, int] = defaultdict(int)
        self.api_successes: Dict[str, int] = defaultdict(int)
        self.api_failures: Dict[str, int] = defaultdict(int)
        self.api_latencies: Dict[str, LatencyStats] = defaultdict(LatencyStats)

        # Circuit breaker events
        self.circuit_breaker_opens: Dict[str, int] = defaultdict(int)
        self.circuit_breaker_closes: Dict[str, int] = defaultdict(int)

        # ML Model metrics (set by evaluation scripts)
        self.ml_metrics: Dict[str, Dict[str, float]] = {}

        # Timestamps
        self.start_time = datetime.now()
        self.last_reset = datetime.now()

    # ==================== Request Metrics ====================

    def record_request(self, endpoint: str, latency_seconds: float):
        """Record a request latency"""
        self.request_latencies[endpoint].add(latency_seconds)

    def get_request_metrics(self) -> Dict[str, Any]:
        """Get request metrics for all endpoints"""
        return {
            endpoint: stats.get_stats()
            for endpoint, stats in self.request_latencies.items()
        }

    # ==================== Cache Metrics ====================

    def record_cache_hit(self, cache_type: str):
        """Record a cache hit"""
        self.cache_hits[cache_type] += 1

    def record_cache_miss(self, cache_type: str):
        """Record a cache miss"""
        self.cache_misses[cache_type] += 1

    def get_cache_metrics(self) -> Dict[str, Any]:
        """Get cache hit/miss metrics"""
        all_types = set(self.cache_hits.keys()) | set(self.cache_misses.keys())
        metrics = {}

        for cache_type in all_types:
            hits = self.cache_hits.get(cache_type, 0)
            misses = self.cache_misses.get(cache_type, 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0

            metrics[cache_type] = {
                "hits": hits,
                "misses": misses,
                "total": total,
                "hit_rate_percent": round(hit_rate, 2)
            }

        # Calculate overall
        total_hits = sum(self.cache_hits.values())
        total_misses = sum(self.cache_misses.values())
        total_all = total_hits + total_misses
        overall_hit_rate = (total_hits / total_all * 100) if total_all > 0 else 0

        metrics["_overall"] = {
            "hits": total_hits,
            "misses": total_misses,
            "total": total_all,
            "hit_rate_percent": round(overall_hit_rate, 2)
        }

        return metrics

    # ==================== API Metrics ====================

    def record_api_call(self, api_name: str, success: bool, latency_seconds: float):
        """Record an external API call"""
        self.api_calls[api_name] += 1
        self.api_latencies[api_name].add(latency_seconds)

        if success:
            self.api_successes[api_name] += 1
        else:
            self.api_failures[api_name] += 1

    def get_api_metrics(self) -> Dict[str, Any]:
        """Get external API metrics"""
        metrics = {}

        for api_name in self.api_calls.keys():
            calls = self.api_calls[api_name]
            successes = self.api_successes.get(api_name, 0)
            failures = self.api_failures.get(api_name, 0)
            success_rate = (successes / calls * 100) if calls > 0 else 0

            metrics[api_name] = {
                "total_calls": calls,
                "successes": successes,
                "failures": failures,
                "success_rate_percent": round(success_rate, 2),
                "latency": self.api_latencies[api_name].get_stats()
            }

        return metrics

    # ==================== Circuit Breaker Metrics ====================

    def record_circuit_open(self, api_name: str):
        """Record circuit breaker opening"""
        self.circuit_breaker_opens[api_name] += 1

    def record_circuit_close(self, api_name: str):
        """Record circuit breaker closing"""
        self.circuit_breaker_closes[api_name] += 1

    def get_circuit_breaker_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker event counts"""
        all_apis = set(self.circuit_breaker_opens.keys()) | set(self.circuit_breaker_closes.keys())
        return {
            api: {
                "opens": self.circuit_breaker_opens.get(api, 0),
                "closes": self.circuit_breaker_closes.get(api, 0)
            }
            for api in all_apis
        }

    # ==================== ML Model Metrics ====================

    def set_ml_metrics(self, model_name: str, metrics: Dict[str, float]):
        """Set ML model evaluation metrics"""
        self.ml_metrics[model_name] = {
            **metrics,
            "evaluated_at": datetime.now().isoformat()
        }

    def get_ml_metrics(self) -> Dict[str, Any]:
        """Get ML model metrics"""
        return self.ml_metrics

    # ==================== Summary ====================

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics"""
        uptime = datetime.now() - self.start_time

        return {
            "system": {
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_human": str(uptime).split('.')[0],
                "start_time": self.start_time.isoformat(),
                "last_reset": self.last_reset.isoformat()
            },
            "requests": self.get_request_metrics(),
            "cache": self.get_cache_metrics(),
            "external_apis": self.get_api_metrics(),
            "circuit_breakers": self.get_circuit_breaker_metrics(),
            "ml_models": self.get_ml_metrics()
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of key metrics for quick overview"""
        cache_metrics = self.get_cache_metrics()
        api_metrics = self.get_api_metrics()

        # Calculate overall API success rate
        total_api_calls = sum(m.get("total_calls", 0) for m in api_metrics.values())
        total_api_successes = sum(m.get("successes", 0) for m in api_metrics.values())
        overall_api_success = (total_api_successes / total_api_calls * 100) if total_api_calls > 0 else 0

        # Get location-data endpoint latency (main endpoint)
        location_data_latency = self.request_latencies.get("/api/v1/location-data", LatencyStats()).get_stats()

        return {
            "response_time_p50_ms": location_data_latency.get("p50"),
            "response_time_p95_ms": location_data_latency.get("p95"),
            "cache_hit_rate_percent": cache_metrics.get("_overall", {}).get("hit_rate_percent", 0),
            "api_success_rate_percent": round(overall_api_success, 2),
            "total_requests": sum(s.values[0] if s.values else 0 for s in self.request_latencies.values()),
            "ml_models_evaluated": len(self.ml_metrics)
        }

    def reset(self):
        """Reset all metrics"""
        self.__init__()
        self.last_reset = datetime.now()
        logger.info("Metrics reset")


# Global metrics collector instance
metrics_collector = MetricsCollector()


# ==================== Decorators ====================

def track_latency(endpoint: str):
    """Decorator to track endpoint latency"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                latency = time.time() - start
                metrics_collector.record_request(endpoint, latency)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                latency = time.time() - start
                metrics_collector.record_request(endpoint, latency)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_api_call(api_name: str):
    """Decorator to track external API calls"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                latency = time.time() - start
                metrics_collector.record_api_call(api_name, success, latency)

        return async_wrapper

    return decorator
