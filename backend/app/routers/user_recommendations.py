"""
User-Based Recommendations endpoints - Recommendations based on user interactions
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
from decimal import Decimal
import logging

from app.services.user_recommendation_service import user_recommendation_service
from app.schemas.user_interaction import UserRecommendationsResponse
from app.core.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/user-recommendations", response_model=UserRecommendationsResponse)
async def get_user_recommendations(
    user_id: str = Query(..., description="User identifier"),
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(10, ge=1, le=50, description="Search radius in kilometers"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of recommendations"),
    db: Session = Depends(get_db)
) -> UserRecommendationsResponse:
    """
    Get personalized recommendations based on user's interaction history
    """
    try:
        result = await user_recommendation_service.get_recommendations(
            user_id=user_id,
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km,
            limit=limit,
            db=db
        )
        
        logger.info(f"User recommendations generated for {user_id}: {result.total_recommendations} items")
        return result
        
    except Exception as e:
        logger.error(f"User recommendations error for {user_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Recommendations service temporarily unavailable: {str(e)}"
        )


