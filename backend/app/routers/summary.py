"""
Summary and analytics endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from decimal import Decimal
import logging

from app.services.summary_service import summary_service
from app.schemas.summary import LocationSummary, SummarizeRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/summarise", response_model=LocationSummary)
async def summarize_location(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(5, ge=1, le=50, description="Search radius in kilometers"),
    include_crimes: bool = Query(True, description="Include crime data in summary"),
    include_events: bool = Query(True, description="Include event data in summary"),
    include_news: bool = Query(True, description="Include news data in summary"),
    include_pois: bool = Query(True, description="Include POI data in summary"),
    max_items_per_type: int = Query(50, ge=1, le=200, description="Maximum items per data type")
) -> LocationSummary:
    """
    Generate a comprehensive location summary
    
    Combines crime, event, news, and POI data into a narrative summary
    with sentiment analysis and keyword extraction.
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-50)
    - **include_crimes**: Include crime data in summary
    - **include_events**: Include event data in summary
    - **include_news**: Include news data in summary
    - **include_pois**: Include POI data in summary
    - **max_items_per_type**: Maximum items to analyze per data type (1-200)
    
    Returns a narrative summary with statistics, sentiment analysis,
    and extracted keywords for the specified location.
    """
    try:
        request = SummarizeRequest(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km,
            include_crimes=include_crimes,
            include_events=include_events,
            include_news=include_news,
            include_pois=include_pois,
            max_items_per_type=max_items_per_type
        )
        
        result = await summary_service.generate_summary(request)
        
        logger.info(f"Location summary generated for {lat}, {lon}: {len(result.narrative)} chars")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary generation error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Summary service temporarily unavailable: {str(e)}"
        )






