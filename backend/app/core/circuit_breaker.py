"""
Circuit Breaker Pattern Implementation for External API Resilience

This module implements the circuit breaker pattern to protect against cascading failures
when external APIs become unavailable or slow. The circuit breaker has three states:

- CLOSED: Normal operation, requests pass through
- OPEN: API is failing, requests are rejected immediately (fast failure)
- HALF_OPEN: Testing if API has recovered, limited requests allowed

Benefits:
- Fast failure when API is down (no waiting for timeouts)
- Automatic recovery testing
- Prevents resource exhaustion from retrying failed APIs
- Graceful degradation of service
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional, Dict, Any, Callable, TypeVar, Awaitable
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests immediately
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5          # Failures before opening circuit
    recovery_timeout: float = 30.0      # Seconds before testing recovery
    half_open_max_calls: int = 3        # Max calls in half-open state
    success_threshold: int = 2          # Successes needed to close circuit

    # Optional: Different thresholds for different error types
    timeout_weight: float = 1.0         # Weight for timeout errors
    error_weight: float = 1.0           # Weight for other errors


@dataclass
class CircuitBreakerState:
    """Internal state tracking for a circuit breaker"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: float = 0.0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    half_open_calls: int = 0

    # Metrics
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejected: int = 0


class CircuitBreaker:
    """
    Circuit breaker for protecting external API calls.

    Usage:
        breaker = CircuitBreaker("uk_police_api")

        async def fetch_data():
            async with breaker:
                return await make_api_call()

        # Or use as decorator:
        @breaker.protect
        async def fetch_data():
            return await make_api_call()
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state"""
        return self._state.state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)"""
        return self._state.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)"""
        return self._state.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)"""
        return self._state.state == CircuitState.HALF_OPEN

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        return {
            "name": self.name,
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "total_calls": self._state.total_calls,
            "total_failures": self._state.total_failures,
            "total_successes": self._state.total_successes,
            "total_rejected": self._state.total_rejected,
            "last_failure_time": self._state.last_failure_time,
            "last_success_time": self._state.last_success_time,
        }

    async def _check_state(self) -> bool:
        """
        Check if request should be allowed.
        Returns True if request can proceed, False if circuit is open.
        """
        async with self._lock:
            now = time.time()

            if self._state.state == CircuitState.CLOSED:
                return True

            if self._state.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._state.last_failure_time is not None:
                    time_since_failure = now - self._state.last_failure_time
                    if time_since_failure >= self.config.recovery_timeout:
                        # Transition to half-open to test recovery
                        self._state.state = CircuitState.HALF_OPEN
                        self._state.half_open_calls = 0
                        self._state.success_count = 0
                        logger.info(
                            f"Circuit breaker '{self.name}' transitioning to HALF_OPEN "
                            f"after {time_since_failure:.1f}s recovery timeout"
                        )
                        return True

                # Still open, reject request
                self._state.total_rejected += 1
                return False

            if self._state.state == CircuitState.HALF_OPEN:
                # Allow limited requests in half-open state
                if self._state.half_open_calls < self.config.half_open_max_calls:
                    self._state.half_open_calls += 1
                    return True

                # Max half-open calls reached, reject
                self._state.total_rejected += 1
                return False

            return True

    async def _record_success(self):
        """Record a successful API call"""
        async with self._lock:
            self._state.total_calls += 1
            self._state.total_successes += 1
            self._state.last_success_time = time.time()

            if self._state.state == CircuitState.HALF_OPEN:
                self._state.success_count += 1

                # Check if we have enough successes to close the circuit
                if self._state.success_count >= self.config.success_threshold:
                    self._state.state = CircuitState.CLOSED
                    self._state.failure_count = 0
                    self._state.success_count = 0
                    logger.info(
                        f"Circuit breaker '{self.name}' CLOSED after "
                        f"{self._state.success_count} successful recovery calls"
                    )

            elif self._state.state == CircuitState.CLOSED:
                # Decay failure count on success (gradual recovery)
                if self._state.failure_count > 0:
                    self._state.failure_count = max(0, self._state.failure_count - 0.5)

    async def _record_failure(self, is_timeout: bool = False):
        """Record a failed API call"""
        async with self._lock:
            self._state.total_calls += 1
            self._state.total_failures += 1
            self._state.last_failure_time = time.time()

            # Apply weight based on error type
            weight = self.config.timeout_weight if is_timeout else self.config.error_weight
            self._state.failure_count += weight

            if self._state.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                self._state.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' reopened due to failure in HALF_OPEN state"
                )

            elif self._state.state == CircuitState.CLOSED:
                # Check if we've exceeded the failure threshold
                if self._state.failure_count >= self.config.failure_threshold:
                    self._state.state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit breaker '{self.name}' OPENED after "
                        f"{self._state.failure_count:.1f} weighted failures "
                        f"(threshold: {self.config.failure_threshold})"
                    )

    async def __aenter__(self):
        """Context manager entry - check if request is allowed"""
        allowed = await self._check_state()
        if not allowed:
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Request rejected to prevent cascade failure."
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - record success or failure"""
        if exc_type is None:
            await self._record_success()
        else:
            # Check if it's a timeout error
            is_timeout = isinstance(exc_val, (asyncio.TimeoutError,))
            await self._record_failure(is_timeout=is_timeout)

        # Don't suppress exceptions
        return False

    def protect(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """
        Decorator to protect an async function with circuit breaker.

        Usage:
            @breaker.protect
            async def fetch_data():
                return await api_call()
        """
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            async with self:
                return await func(*args, **kwargs)
        return wrapper

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        fallback: Optional[Callable[..., T]] = None,
        **kwargs
    ) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            fallback: Optional fallback function if circuit is open
            **kwargs: Keyword arguments for func

        Returns:
            Result from func or fallback

        Raises:
            CircuitOpenError: If circuit is open and no fallback provided
        """
        try:
            async with self:
                return await func(*args, **kwargs)
        except CircuitOpenError:
            if fallback is not None:
                logger.info(f"Circuit '{self.name}' open, using fallback")
                return fallback(*args, **kwargs)
            raise

    def reset(self):
        """Manually reset the circuit breaker to closed state"""
        self._state = CircuitBreakerState()
        logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected"""
    pass


# Global registry of circuit breakers for each API
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get or create a circuit breaker for an API.

    Args:
        name: Unique name for the API (e.g., "uk_police", "ticketmaster")
        config: Optional configuration override

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """Get all registered circuit breakers"""
    return _circuit_breakers.copy()


def get_circuit_breaker_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics from all circuit breakers"""
    return {name: cb.get_metrics() for name, cb in _circuit_breakers.items()}


# Pre-configured circuit breakers for external APIs
# These can be imported and used directly by services

uk_police_breaker = get_circuit_breaker(
    "uk_police",
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        half_open_max_calls=2,
        success_threshold=2
    )
)

ticketmaster_breaker = get_circuit_breaker(
    "ticketmaster",
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        half_open_max_calls=2,
        success_threshold=2
    )
)

eventbrite_breaker = get_circuit_breaker(
    "eventbrite",
    CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=60.0,  # Longer recovery for Eventbrite
        half_open_max_calls=1,
        success_threshold=1
    )
)

newsapi_breaker = get_circuit_breaker(
    "newsapi",
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        half_open_max_calls=2,
        success_threshold=2
    )
)

overpass_breaker = get_circuit_breaker(
    "overpass",
    CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=60.0,  # Longer recovery for Overpass (often slow)
        half_open_max_calls=1,
        success_threshold=1,
        timeout_weight=0.5  # Timeouts are common for Overpass, weight less
    )
)

ors_breaker = get_circuit_breaker(
    "openrouteservice",
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        half_open_max_calls=2,
        success_threshold=2
    )
)
