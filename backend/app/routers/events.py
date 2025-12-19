"""
Event data endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from decimal import Decimal
import logging

from app.services.events_service import events_service
from app.schemas.events import EventResponse, EventSummary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events", response_model=EventResponse)
async def get_events(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    within_km: int = Query(10, ge=1, le=100, description="Search radius in kilometers"),
    q: Optional[str] = Query(None, max_length=100, description="Search query for events"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of events to return")
) -> EventResponse:
    """
    Get event data for a specific location
    """
    try:
        result = await events_service.get_events(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            within_km=within_km,
            query=q,
            limit=limit
        )
        
        logger.info(f"Event data retrieved for {lat}, {lon}: {result.total_count} events")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Event data error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Event data service temporarily unavailable: {str(e)}"
        )


@router.get("/events/summary", response_model=EventSummary)
async def get_event_summary(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    within_km: int = Query(10, ge=1, le=100, description="Search radius in kilometers"),
    q: Optional[str] = Query(None, max_length=100, description="Search query for events"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of events to analyze")
) -> EventSummary:
    """
    Get event summary statistics for a location
    """
    try:
        result = await events_service.get_event_summary(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            within_km=within_km,
            query=q,
            limit=limit
        )
        
        logger.info(f"Event summary retrieved for {lat}, {lon}: {result.total_events} total events")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Event summary error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Event summary service temporarily unavailable: {str(e)}"
        )






