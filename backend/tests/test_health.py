"""
Health endpoint tests
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app

client = TestClient(app)


def test_status_check():
    """Test basic status check endpoint"""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Hybrid AI Location App API"
    assert "version" in data


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["message"] == "Hybrid AI Location App API"
    assert data["status"] == "running"


def test_api_root_endpoint():
    """Test API root endpoint"""
    response = client.get("/api")
    assert response.status_code == 200
    
    data = response.json()
    assert data["message"] == "Hybrid AI Location App API v1"
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_detailed_status_check():
    """Test detailed status check with Redis"""
    with patch("app.routers.health.get_redis") as mock_redis:
        # Mock Redis connection
        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        response = client.get("/api/v1/status/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "checks" in data
        assert "redis" in data["checks"]
        assert data["checks"]["redis"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_check():
    """Test readiness check endpoint"""
    with patch("app.routers.health.get_redis") as mock_redis:
        # Mock Redis connection
        mock_redis_instance = AsyncMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        response = client.get("/api/v1/status/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"


def test_liveness_check():
    """Test liveness check endpoint"""
    response = client.get("/api/v1/status/live")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "alive"
