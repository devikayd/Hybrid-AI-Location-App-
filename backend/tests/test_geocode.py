"""
Geocoding endpoint tests
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from decimal import Decimal

from app.main import app
from app.schemas.geocode import GeocodeResponse, GeocodeResult

client = TestClient(app)


@pytest.mark.asyncio
async def test_geocode_success():
    """Test successful geocoding"""
    mock_response = GeocodeResponse(
        query="London",
        results=[
            GeocodeResult(
                lat=Decimal("51.5074"),
                lon=Decimal("-0.1278"),
                display_name="London, Greater London, England, United Kingdom",
                place_id=12345,
                importance=0.9
            )
        ],
        cached=False,
        source="nominatim"
    )
    
    with patch("app.routers.geocode.geocode_service.geocode") as mock_geocode:
        mock_geocode.return_value = mock_response
        
        response = client.get("/api/v1/geocode?q=London")
        assert response.status_code == 200
        
        data = response.json()
        assert data["query"] == "London"
        assert len(data["results"]) == 1
        assert data["results"][0]["display_name"] == "London, Greater London, England, United Kingdom"


def test_geocode_empty_query():
    """Test geocoding with empty query"""
    response = client.get("/api/v1/geocode?q=")
    assert response.status_code == 422  # Validation error


def test_geocode_invalid_limit():
    """Test geocoding with invalid limit"""
    response = client.get("/api/v1/geocode?q=London&limit=0")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_reverse_geocode_success():
    """Test successful reverse geocoding"""
    mock_result = GeocodeResult(
        lat=Decimal("51.5074"),
        lon=Decimal("-0.1278"),
        display_name="London, Greater London, England, United Kingdom",
        place_id=12345
    )
    
    with patch("app.routers.geocode.geocode_service.reverse_geocode") as mock_reverse:
        mock_reverse.return_value = mock_result
        
        response = client.get("/api/v1/geocode/reverse?lat=51.5074&lon=-0.1278")
        assert response.status_code == 200
        
        data = response.json()
        assert data["lat"] == "51.5074"
        assert data["lon"] == "-0.1278"
        assert "London" in data["display_name"]


@pytest.mark.asyncio
async def test_reverse_geocode_not_found():
    """Test reverse geocoding with no results"""
    with patch("app.routers.geocode.geocode_service.reverse_geocode") as mock_reverse:
        mock_reverse.return_value = None
        
        response = client.get("/api/v1/geocode/reverse?lat=0&lon=0")
        assert response.status_code == 404
        
        data = response.json()
        assert "No address found" in data["detail"]


def test_reverse_geocode_invalid_coordinates():
    """Test reverse geocoding with invalid coordinates"""
    response = client.get("/api/v1/geocode/reverse?lat=91&lon=0")
    assert response.status_code == 422  # Validation error






