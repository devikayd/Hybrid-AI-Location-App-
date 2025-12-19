"""
Robust HTTP client with retry logic and graceful degradation
"""

import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, Union
from functools import wraps
import random

logger = logging.getLogger(__name__)


class RetryConfig:
    """Retry configuration"""
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_status_codes: set = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_status_codes = retryable_status_codes or {500, 502, 503, 504, 429}


class RobustHTTPClient:
    """HTTP client with retry logic and graceful degradation"""
    
    def __init__(
        self,
        timeout: float = 30.0,
        retry_config: Optional[RetryConfig] = None,
        default_headers: Optional[Dict[str, str]] = None
    ):
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self.default_headers = default_headers or {}
    
    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[str, bytes]] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic
        """
        # Merge headers
        request_headers = {**self.default_headers, **(headers or {})}
        
        # Prepare request
        request_kwargs = {
            "method": method,
            "url": url,
            "params": params,
            "headers": request_headers,
            "timeout": self.timeout,
            **kwargs
        }
        
        if json is not None:
            request_kwargs["json"] = json
        elif data is not None:
            request_kwargs["data"] = data
        
        # Execute with retries
        last_exception = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(**request_kwargs)
                    
                    if self._should_retry(response, attempt):
                        if attempt < self.retry_config.max_retries:
                            delay = self._calculate_delay(attempt)
                            logger.warning(
                                f"Request failed (attempt {attempt + 1}/{self.retry_config.max_retries + 1}): "
                                f"{response.status_code} {response.reason_phrase}. Retrying in {delay:.2f}s"
                            )
                            await asyncio.sleep(delay)
                            continue
                    
                    return response
                    
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                last_exception = e
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Network error (attempt {attempt + 1}/{self.retry_config.max_retries + 1}): "
                        f"{str(e)}. Retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Max retries exceeded for {method} {url}: {str(e)}")
                    raise
        
        if last_exception:
            raise last_exception
        else:
            raise httpx.HTTPError("All retry attempts failed")
    
    def _should_retry(self, response: httpx.Response, attempt: int) -> bool:
        """Determine if request should be retried"""
        if attempt >= self.retry_config.max_retries:
            return False
        
        return response.status_code in self.retry_config.retryable_status_codes
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for next retry attempt"""
        delay = self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt)
        delay = min(delay, self.retry_config.max_delay)
        
        if self.retry_config.jitter:
            # Add random jitter to prevent thundering herd
            jitter = random.uniform(0.1, 0.3) * delay
            delay += jitter
        
        return delay
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET request with retry logic"""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST request with retry logic"""
        return await self.request("POST", url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> httpx.Response:
        """PUT request with retry logic"""
        return await self.request("PUT", url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """DELETE request with retry logic"""
        return await self.request("DELETE", url, **kwargs)


def with_graceful_degradation(
    fallback_value: Any = None,
    log_error: bool = True,
    service_name: str = "Unknown"
):
    """
    Decorator for graceful degradation when external services fail
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"{service_name} service error: {str(e)}")
                
                if fallback_value is not None:
                    logger.info(f"Using fallback value for {service_name}")
                    return fallback_value
                else:
                    raise
        
        return wrapper
    return decorator


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    service_name: str = "Unknown"
):
    """
    Simple circuit breaker pattern implementation
    """
    class CircuitBreaker:
        def __init__(self):
            self.failure_count = 0
            self.last_failure_time = None
            self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
        def can_execute(self) -> bool:
            if self.state == "CLOSED":
                return True
            
            if self.state == "OPEN":
                if (self.last_failure_time and 
                    asyncio.get_event_loop().time() - self.last_failure_time > recovery_timeout):
                    self.state = "HALF_OPEN"
                    return True
                return False
            
            if self.state == "HALF_OPEN":
                return True
            
            return False
        
        def record_success(self):
            self.failure_count = 0
            self.state = "CLOSED"
        
        def record_failure(self):
            self.failure_count += 1
            self.last_failure_time = asyncio.get_event_loop().time()
            
            if self.failure_count >= failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker OPEN for {service_name}")
    
    circuit_breaker = CircuitBreaker()
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not circuit_breaker.can_execute():
                raise Exception(f"Circuit breaker OPEN for {service_name}")
            
            try:
                result = await func(*args, **kwargs)
                circuit_breaker.record_success()
                return result
            except Exception as e:
                circuit_breaker.record_failure()
                raise
        
        return wrapper
    return decorator


# Default HTTP client instances
def create_service_client(
    service_name: str,
    timeout: float = 30.0,
    retry_config: Optional[RetryConfig] = None
) -> RobustHTTPClient:
    """Create a service-specific HTTP client"""
    
    default_headers = {
        "User-Agent": f"Hybrid-AI-Location-App/1.0.0 ({service_name})",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }
    
    return RobustHTTPClient(
        timeout=timeout,
        retry_config=retry_config,
        default_headers=default_headers
    )






