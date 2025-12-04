"""
Event data schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime


class EventVenue(BaseModel):
    """Event venue information"""
    id: Optional[str] = Field(None, description="Venue ID")
    name: Optional[str] = Field(None, description="Venue name")
    address: Optional[Dict[str, Any]] = Field(None, description="Venue address")
    latitude: Optional[str] = Field(None, description="Venue latitude")
    longitude: Optional[str] = Field(None, description="Venue longitude")


class EventData(BaseModel):
    """Individual event record"""
    id: str = Field(..., description="Event ID")
    name: Dict[str, str] = Field(..., description="Event name (text)")
    description: Optional[Dict[str, str]] = Field(None, description="Event description")
    start: Optional[Dict[str, str]] = Field(None, description="Event start time")
    end: Optional[Dict[str, str]] = Field(None, description="Event end time")
    url: Optional[str] = Field(None, description="Event URL")
    status: Optional[str] = Field(None, description="Event status")
    currency: Optional[str] = Field(None, description="Currency")
    online_event: Optional[bool] = Field(None, description="Is online event")
    is_free: Optional[bool] = Field(None, description="Is free event")
    venue: Optional[EventVenue] = Field(None, description="Event venue")
    category_id: Optional[str] = Field(None, description="Category ID")
    subcategory_id: Optional[str] = Field(None, description="Subcategory ID")
    format_id: Optional[str] = Field(None, description="Format ID")


class EventResponse(BaseModel):
    """Event data response"""
    lat: Decimal = Field(..., description="Search latitude")
    lon: Decimal = Field(..., description="Search longitude")
    events: List[EventData] = Field(..., description="Event records")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("eventbrite", description="Data source")
    total_count: int = Field(..., description="Total number of events")


class EventSummary(BaseModel):
    """Event summary statistics"""
    lat: Decimal = Field(..., description="Search latitude")
    lon: Decimal = Field(..., description="Search longitude")
    total_events: int = Field(..., description="Total number of events")
    free_events: int = Field(..., description="Number of free events")
    paid_events: int = Field(..., description="Number of paid events")
    online_events: int = Field(..., description="Number of online events")
    categories: Dict[str, int] = Field(..., description="Event counts by category")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("eventbrite", description="Data source")






