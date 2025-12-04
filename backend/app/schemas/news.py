"""
News data schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal


class NewsSource(BaseModel):
    """News source information"""
    id: Optional[str] = Field(None, description="Source ID")
    name: str = Field(..., description="Source name")


class NewsArticle(BaseModel):
    """Individual news article"""
    source: NewsSource = Field(..., description="News source")
    author: Optional[str] = Field(None, description="Article author")
    title: str = Field(..., description="Article title")
    description: Optional[str] = Field(None, description="Article description")
    url: str = Field(..., description="Article URL")
    urlToImage: Optional[str] = Field(None, description="Article image URL")
    publishedAt: str = Field(..., description="Publication date")
    content: Optional[str] = Field(None, description="Article content")
    sentiment: Optional[float] = Field(None, description="Sentiment score (-1 to 1)")


class NewsResponse(BaseModel):
    """News data response"""
    lat: Decimal = Field(..., description="Search latitude")
    lon: Decimal = Field(..., description="Search longitude")
    articles: List[NewsArticle] = Field(..., description="News articles")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("newsapi", description="Data source")
    total_count: int = Field(..., description="Total number of articles")


class NewsSummary(BaseModel):
    """News summary statistics"""
    lat: Decimal = Field(..., description="Search latitude")
    lon: Decimal = Field(..., description="Search longitude")
    total_articles: int = Field(..., description="Total number of articles")
    sources: Dict[str, int] = Field(..., description="Article counts by source")
    sentiment_summary: Dict[str, float] = Field(..., description="Sentiment statistics")
    cached: bool = Field(False, description="Whether result was served from cache")
    source: str = Field("newsapi", description="Data source")






