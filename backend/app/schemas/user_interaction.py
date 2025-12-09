"""
Schemas for user interaction endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class LocationItem(BaseModel):
    """Schema for a location-based item (event, POI, news, crime)"""
    id: str = Field(..., description="Item identifier")
    type: str = Field(..., description="Item type: 'event', 'poi', 'news', 'crime'")
    title: str = Field(..., description="Item title/name")
    description: Optional[str] = Field(None, description="Item description")
    lat: Decimal = Field(..., description="Item latitude")
    lon: Decimal = Field(..., description="Item longitude")
    category: Optional[str] = Field(None, description="Item category")
    subtype: Optional[str] = Field(None, description="Item subtype")
    distance_km: Optional[float] = Field(None, description="Distance from search center in km")
    date: Optional[str] = Field(None, description="Item date")
    url: Optional[str] = Field(None, description="Item URL")
    metadata: Optional[dict] = Field(None, description="Additional item metadata")
    is_liked: bool = Field(False, description="Whether user has liked this item")
    is_saved: bool = Field(False, description="Whether user has saved this item")


class LocationDataResponse(BaseModel):
    """Response schema for location data endpoint"""
    lat: Decimal = Field(..., description="Search center latitude")
    lon: Decimal = Field(..., description="Search center longitude")
    location_name: Optional[str] = Field(None, description="Location name")
    events: List[LocationItem] = Field(default_factory=list, description="Events in location")
    pois: List[LocationItem] = Field(default_factory=list, description="POIs in location")
    news: List[LocationItem] = Field(default_factory=list, description="News articles in location")
    crimes: List[LocationItem] = Field(default_factory=list, description="Crimes in location")
    total_items: int = Field(..., description="Total number of items")
    cached: bool = Field(False, description="Whether result was cached")


class InteractionRequest(BaseModel):
    """Request schema for like/save interaction"""
    item_id: str = Field(..., description="Item identifier")
    item_type: str = Field(..., description="Item type: 'event', 'poi', 'news', 'crime'")
    interaction_type: str = Field(..., description="Interaction type: 'like' or 'save'")
    item_title: Optional[str] = Field(None, description="Item title")
    item_category: Optional[str] = Field(None, description="Item category")
    item_subtype: Optional[str] = Field(None, description="Item subtype")
    lat: Optional[Decimal] = Field(None, description="Item latitude")
    lon: Optional[Decimal] = Field(None, description="Item longitude")
    location_name: Optional[str] = Field(None, description="Location name")


class InteractionResponse(BaseModel):
    """Response schema for interaction endpoint"""
    success: bool = Field(..., description="Whether interaction was successful")
    message: str = Field(..., description="Response message")
    interaction_id: Optional[int] = Field(None, description="Interaction ID")
    is_active: bool = Field(..., description="Whether interaction is active")


class UserRecommendationItem(BaseModel):
    """Schema for recommendation item based on user interactions"""
    id: str = Field(..., description="Item identifier")
    type: str = Field(..., description="Item type")
    title: str = Field(..., description="Item title")
    description: Optional[str] = Field(None, description="Item description")
    lat: Decimal = Field(..., description="Item latitude")
    lon: Decimal = Field(..., description="Item longitude")
    category: Optional[str] = Field(None, description="Item category")
    subtype: Optional[str] = Field(None, description="Item subtype")
    url: Optional[str] = Field(None, description="Item URL")
    date: Optional[str] = Field(None, description="Item date")
    metadata: Optional[dict] = Field(None, description="Additional item metadata")
    relevance_reason: str = Field(..., description="Why this item was recommended")
    match_score: float = Field(..., description="Match score based on user interests (0-1)")


class UserRecommendationsResponse(BaseModel):
    """Response schema for user-based recommendations"""
    user_id: str = Field(..., description="User identifier")
    recommendations: List[UserRecommendationItem] = Field(default_factory=list, description="Recommended items")
    based_on_interactions: int = Field(..., description="Number of interactions used for recommendations")
    total_recommendations: int = Field(..., description="Total number of recommendations")


