"""
Crime data schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class CrimeLocation(BaseModel):
    """Crime location information"""
    latitude: Optional[str] = Field(None, description="Latitude")
    longitude: Optional[str] = Field(None, description="Longitude")
    street: Optional[dict] = Field(None, description="Street information")
    id: Optional[int] = Field(None, description="Location ID")


class CrimeOutcome(BaseModel):
    """Crime outcome information"""
    category: Optional[str] = Field(None, description="Outcome category")
    date: Optional[str] = Field(None, description="Outcome date")


class CrimeData(BaseModel):
    """Individual crime record"""
    id: int = Field(..., description="Crime ID")
    category: str = Field(..., description="Crime category")
    location_type: Optional[str] = Field(None, description="Location type")
    location: Optional[CrimeLocation] = Field(None, description="Location details")
    context: Optional[str] = Field(None, description="Additional context")
    outcome_status: Optional[CrimeOutcome] = Field(None, description="Outcome status")
    persistent_id: Optional[str] = Field(None, description="Persistent ID")
    date: str = Field(..., description="Crime date")
    month: str = Field(..., description="Crime month")


class CrimeResponse(BaseModel):
    """Crime data response"""
    lat: Decimal = Field(..., description="Search latitude")
    lon: Decimal = Field(..., description="Search longitude")
    crimes: List[CrimeData] = Field(..., description="Crime records")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("uk_police", description="Data source")
    total_count: int = Field(..., description="Total number of crimes")


class CrimeSummary(BaseModel):
    """Crime summary statistics"""
    lat: Decimal = Field(..., description="Search latitude")
    lon: Decimal = Field(..., description="Search longitude")
    total_crimes: int = Field(..., description="Total number of crimes")
    categories: dict = Field(..., description="Crime counts by category")
    months: dict = Field(..., description="Crime counts by month")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("uk_police", description="Data source")






