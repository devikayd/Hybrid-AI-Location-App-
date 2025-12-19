"""
Crime data endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from decimal import Decimal
import logging

from app.services.crime_service import crime_service
from app.schemas.crime import CrimeResponse, CrimeSummary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/crime", response_model=CrimeResponse)
async def get_crimes(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    months: int = Query(12, ge=1, le=24, description="Number of months to look back"),
    category: Optional[str] = Query(None, description="Crime category filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of crimes to return")
) -> CrimeResponse:

    try:
        result = await crime_service.get_crimes(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            months=months,
            category=category,
            limit=limit
        )
        
        logger.info(f"Crime data retrieved for {lat}, {lon}: {result.total_count} crimes")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Crime data error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Crime data service temporarily unavailable: {str(e)}"
        )


@router.get("/crime/summary", response_model=CrimeSummary)
async def get_crime_summary(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    months: int = Query(12, ge=1, le=24, description="Number of months to look back"),
    category: Optional[str] = Query(None, description="Crime category filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of crimes to analyze")
) -> CrimeSummary:

    try:
        result = await crime_service.get_crime_summary(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            months=months,
            category=category,
            limit=limit
        )
        
        logger.info(f"Crime summary retrieved for {lat}, {lon}: {result.total_crimes} total crimes")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Crime summary error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Crime summary service temporarily unavailable: {str(e)}"
        )






