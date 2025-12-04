"""
Geocoding schemas
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from decimal import Decimal


class GeocodeRequest(BaseModel):
    """Geocoding request schema"""
    q: str = Field(..., min_length=1, max_length=200, description="Search query")
    limit: Optional[int] = Field(1, ge=1, le=10, description="Maximum number of results")
    countrycodes: Optional[str] = Field("gb", description="Country codes (comma-separated)")
    
    @validator('q')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()


class GeocodeResult(BaseModel):
    """Individual geocoding result"""
    lat: Decimal = Field(..., description="Latitude")
    lon: Decimal = Field(..., description="Longitude")
    display_name: str = Field(..., description="Formatted address")
    place_id: Optional[int] = Field(None, description="OpenStreetMap place ID")
    osm_type: Optional[str] = Field(None, description="OSM object type")
    osm_id: Optional[int] = Field(None, description="OSM object ID")
    importance: Optional[float] = Field(None, description="Location importance score")
    boundingbox: Optional[List[str]] = Field(None, description="Bounding box coordinates")


class GeocodeResponse(BaseModel):
    """Geocoding response schema"""
    query: str = Field(..., description="Original search query")
    results: List[GeocodeResult] = Field(..., description="Geocoding results")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("nominatim", description="Data source")


class GeocodeError(BaseModel):
    """Geocoding error schema"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    query: str = Field(..., description="Original search query")






