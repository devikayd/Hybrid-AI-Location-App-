"""
Safety and popularity scoring endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from decimal import Decimal
import logging

from app.services.scoring_service import scoring_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scores")
async def calculate_scores(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(5, ge=1, le=50, description="Search radius in kilometers")
):
    """
    Calculate safety and popularity scores for a location

    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-50)
    
    Returns safety score (0-1), popularity score (0-1), overall score, and
    detailed feature analysis used for scoring.
    """
    try:
        result = await scoring_service.calculate_scores(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km
        )
        
        logger.info(f"Scores calculated for {lat}, {lon}: safety={result['safety_score']:.2f}, popularity={result['popularity_score']:.2f}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Score calculation error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Scoring service temporarily unavailable: {str(e)}"
        )






