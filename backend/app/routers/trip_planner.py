"""
Trip Planner Router

Exposes POST /api/v1/trip-plan which generates a safety-aware day trip
itinerary for a given UK location.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.trip_planner import TripPlanRequest, TripPlanResponse
from app.services.trip_planner_service import trip_planner_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/trip-plan", response_model=TripPlanResponse)
async def plan_day_trip(
    request: TripPlanRequest,
    db: Session = Depends(get_db),
) -> TripPlanResponse:
    """
    Generate a safety-aware day trip itinerary.

    Given a location (lat/lon), the system selects up to `max_stops` places
    worth visiting, orders them using a nearest-neighbour algorithm to
    minimise total travel time, and returns walking time between each stop.

    Safety and popularity scores are factored into stop selection so that
    the itinerary prioritises well-rated, active areas.
    """
    try:
        result = await trip_planner_service.plan_day_trip(
            lat=Decimal(str(request.lat)),
            lon=Decimal(str(request.lon)),
            user_id=request.user_id,
            max_stops=request.max_stops,
            mode=request.mode,
            db=db,
        )
        logger.info(
            f"Trip plan generated: {result.total_stops} stops near "
            f"{request.lat},{request.lon} for user {request.user_id}"
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trip plan failed for {request.lat},{request.lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Trip planner temporarily unavailable: {str(e)}",
        )
