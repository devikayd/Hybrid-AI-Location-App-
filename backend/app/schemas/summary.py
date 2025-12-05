"""
Summary and analytics schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime


class LocationSummary(BaseModel):
    """Location summary data"""
    lat: Decimal = Field(..., description="Latitude")
    lon: Decimal = Field(..., description="Longitude")
    radius_km: int = Field(..., description="Search radius in kilometers")
    
    # Data counts
    crime_count: int = Field(0, description="Number of crimes")
    event_count: int = Field(0, description="Number of events")
    news_count: int = Field(0, description="Number of news articles")
    poi_count: int = Field(0, description="Number of POIs")
    
    # Summary statistics
    crime_categories: Dict[str, int] = Field(default_factory=dict, description="Crime counts by category")
    event_types: Dict[str, int] = Field(default_factory=dict, description="Event counts by type")
    news_sentiment: Dict[str, float] = Field(default_factory=dict, description="News sentiment scores")
    poi_amenities: Dict[str, int] = Field(default_factory=dict, description="POI counts by amenity")
    
    # Generated narrative
    narrative: str = Field(..., description="Generated location summary")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("ai_summary", description="Summary generation method")


class SummarizeRequest(BaseModel):
    """Summarization request schema"""
    lat: Decimal = Field(..., ge=-90, le=90, description="Latitude")
    lon: Decimal = Field(..., ge=-180, le=180, description="Longitude")
    radius_km: int = Field(5, ge=1, le=50, description="Search radius in kilometers")
    include_crimes: bool = Field(True, description="Include crime data")
    include_events: bool = Field(True, description="Include event data")
    include_news: bool = Field(True, description="Include news data")
    include_pois: bool = Field(True, description="Include POI data")
    max_items_per_type: int = Field(50, ge=1, le=200, description="Maximum items per data type")


class RecommendationItem(BaseModel):
    """Recommendation item"""
    id: str = Field(..., description="Item identifier")
    type: str = Field(..., description="Item type (crime, event, news, poi)")
    title: str = Field(..., description="Item title")
    description: Optional[str] = Field(None, description="Item description")
    lat: Decimal = Field(..., description="Item latitude")
    lon: Decimal = Field(..., description="Item longitude")
    distance_km: float = Field(..., description="Distance from search center")
    relevance_score: float = Field(..., description="Relevance score (0-1)")
    recency_score: float = Field(..., description="Recency score (0-1)")
    category_score: float = Field(..., description="Category preference score (0-1)")


class RecommendationsResponse(BaseModel):
    """Recommendations response schema"""
    lat: Decimal = Field(..., description="Search center latitude")
    lon: Decimal = Field(..., description="Search center longitude")
    recommendations: List[RecommendationItem] = Field(..., description="Recommended items")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("rule_based", description="Recommendation method")






