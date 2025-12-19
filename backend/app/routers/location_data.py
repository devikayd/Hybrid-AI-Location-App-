"""
Location Data endpoints - Get all data for a location
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
from decimal import Decimal
import logging
from sqlalchemy.orm import Session

from app.services.location_data_service import location_data_service
from app.schemas.user_interaction import LocationDataResponse
from app.core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/location-data", response_model=LocationDataResponse)
async def get_location_data(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(10, ge=1, le=50, description="Search radius in kilometers"),
    user_id: Optional[str] = Query(None, description="User ID for personalized results (optional)"),
    db: Session = Depends(get_db)
) -> LocationDataResponse:
    """
    Get all data for a location (events, POIs, news, crimes)
    Returns a comprehensive list of all location-based items
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-50)
    - **user_id**: Optional user ID to show liked/saved status
    """
    try:
        result = await location_data_service.get_location_data(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km,
            user_id=None  # Don't pass user_id here, we'll add status separately
        )
        
        # Add user interaction status if user_id provided
        if user_id:
            await location_data_service.add_user_interaction_status(result, user_id, db)
        
        logger.info(f"Location data retrieved for {lat}, {lon}: {result.total_items} items")
        return result
        
    except Exception as e:
        logger.error(f"Location data error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Location data service temporarily unavailable: {str(e)}"
        )

