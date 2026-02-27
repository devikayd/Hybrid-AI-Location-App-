"""
Pydantic schemas for the Trip Planner feature.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal


class TripStop(BaseModel):
    """A single stop in a day trip itinerary."""

    stop_index: int = Field(..., description="Position in itinerary (1 = first stop)")
    name: str = Field(..., description="Name of the place")
    type: str = Field(..., description="Item type: 'event', 'poi'")
    category: str = Field(..., description="Category of the stop (e.g. 'museum', 'park')")
    lat: Decimal = Field(..., description="Latitude of the stop")
    lon: Decimal = Field(..., description="Longitude of the stop")
    safety_score: float = Field(..., description="Area safety score (0–10)")
    popularity_score: float = Field(..., description="Area popularity score (0–10)")
    description: Optional[str] = Field(None, description="Short description of the place")
    travel_time_from_previous: Optional[int] = Field(
        None, description="Travel time from the previous stop in seconds"
    )
    travel_time_text: Optional[str] = Field(
        None, description="Human-readable travel time, e.g. '12 min walk'"
    )
    distance_from_previous: Optional[float] = Field(
        None, description="Distance from previous stop in metres"
    )
    url: Optional[str] = Field(None, description="Link to more information about this place")


class TripPlanResponse(BaseModel):
    """Full day trip itinerary response."""

    origin_lat: Decimal = Field(..., description="Latitude of the trip origin/search centre")
    origin_lon: Decimal = Field(..., description="Longitude of the trip origin/search centre")
    location_name: str = Field(..., description="Human-readable name of the area")
    stops: List[TripStop] = Field(..., description="Ordered list of places to visit")
    total_duration_seconds: int = Field(
        ..., description="Total walking time between all stops in seconds"
    )
    total_duration_text: str = Field(
        ..., description="Human-readable total walking time, e.g. '42 min total walking'"
    )
    travel_mode: str = Field(..., description="Travel mode used for routing")
    cached: bool = Field(False, description="Whether this result was served from cache")
    total_stops: int = Field(..., description="Number of stops in the itinerary")


class TripPlanRequest(BaseModel):
    """Request body for the trip planner endpoint."""

    lat: float = Field(..., ge=-90, le=90, description="Latitude of the search centre")
    lon: float = Field(..., ge=-180, le=180, description="Longitude of the search centre")
    user_id: str = Field(..., description="User identifier for personalised ranking")
    max_stops: int = Field(5, ge=2, le=8, description="Maximum number of stops to include")
    mode: str = Field(
        "foot-walking",
        description="Travel mode: 'foot-walking', 'driving-car', 'cycling-regular'",
    )
