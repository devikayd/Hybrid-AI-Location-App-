"""
News data endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from decimal import Decimal
import logging

from app.services.news_service import news_service
from app.schemas.news import NewsResponse, NewsSummary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/news", response_model=NewsResponse)
async def get_news(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(50, ge=1, le=500, description="Search radius in kilometers"),
    q: Optional[str] = Query(None, max_length=100, description="Search query for news"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of articles to return")
) -> NewsResponse:
    """
    Get news data for a specific location
    Retrieves news data from NewsAPI for UK news sources.
    Results are cached for 15 minutes to improve performance.
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-500)
    - **q**: Optional search query for news articles
    - **limit**: Maximum number of articles to return (1-100)
    """
    try:
        result = await news_service.get_news(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km,
            query=q,
            limit=limit
        )
        
        logger.info(f"News data retrieved for {lat}, {lon}: {result.total_count} articles")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"News data error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"News data service temporarily unavailable: {str(e)}"
        )


@router.get("/news/summary", response_model=NewsSummary)
async def get_news_summary(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(50, ge=1, le=500, description="Search radius in kilometers"),
    q: Optional[str] = Query(None, max_length=100, description="Search query for news"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of articles to analyze")
) -> NewsSummary:
    """
    Get news summary statistics for a location
    
    Provides aggregated statistics about news in the area, including:
    - Total article count
    - Articles by source
    - Sentiment analysis summary
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-500)
    - **q**: Optional search query for news articles
    - **limit**: Maximum number of articles to analyze (1-100)
    """
    try:
        result = await news_service.get_news_summary(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km,
            query=q,
            limit=limit
        )
        
        logger.info(f"News summary retrieved for {lat}, {lon}: {result.total_articles} total articles")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"News summary error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"News summary service temporarily unavailable: {str(e)}"
        )






