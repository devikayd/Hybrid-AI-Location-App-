"""
Points of Interest (POI) data schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal


class POITags(BaseModel):
    """POI tags/metadata"""
    name: Optional[str] = Field(None, description="POI name")
    amenity: Optional[str] = Field(None, description="Amenity type")
    tourism: Optional[str] = Field(None, description="Tourism type")
    shop: Optional[str] = Field(None, description="Shop type")
    cuisine: Optional[str] = Field(None, description="Cuisine type")
    opening_hours: Optional[str] = Field(None, description="Opening hours")
    phone: Optional[str] = Field(None, description="Phone number")
    website: Optional[str] = Field(None, description="Website URL")
    wheelchair: Optional[str] = Field(None, description="Wheelchair accessibility")
    addr_street: Optional[str] = Field(None, description="Street address")
    addr_city: Optional[str] = Field(None, description="City")
    addr_postcode: Optional[str] = Field(None, description="Postcode")


class POIData(BaseModel):
    """Individual POI record"""
    id: int = Field(..., description="POI ID")
    lat: Decimal = Field(..., description="Latitude")
    lon: Decimal = Field(..., description="Longitude")
    type: str = Field(..., description="POI type")
    tags: POITags = Field(..., description="POI metadata")
    distance: Optional[float] = Field(None, description="Distance from search center (km)")


class POIResponse(BaseModel):
    """POI data response"""
    lat: Decimal = Field(..., description="Search latitude")
    lon: Decimal = Field(..., description="Search longitude")
    pois: List[POIData] = Field(..., description="POI records")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("overpass", description="Data source")
    total_count: int = Field(..., description="Total number of POIs")


class POISummary(BaseModel):
    """POI summary statistics"""
    lat: Decimal = Field(..., description="Search latitude")
    lon: Decimal = Field(..., description="Search longitude")
    total_pois: int = Field(..., description="Total number of POIs")
    types: Dict[str, int] = Field(..., description="POI counts by type")
    amenities: Dict[str, int] = Field(..., description="POI counts by amenity")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("overpass", description="Data source")






