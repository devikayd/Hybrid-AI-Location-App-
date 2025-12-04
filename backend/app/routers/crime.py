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
    """
    Get crime data for a specific location
    
    Retrieves crime data from the UK Police API for the specified coordinates.
    Results are cached for 1 hour to improve performance.
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **months**: Number of months to look back (1-24)
    - **category**: Optional crime category filter
    - **limit**: Maximum number of crimes to return (1-1000)
    
    Common crime categories include:
    - anti-social-behaviour
    - burglary
    - criminal-damage-arson
    - drugs
    - other-theft
    - public-order
    - robbery
    - shoplifting
    - theft-from-the-person
    - vehicle-crime
    - violent-crime
    """
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
    """
    Get crime summary statistics for a location
    
    Provides aggregated statistics about crimes in the area, including:
    - Total crime count
    - Crimes by category
    - Crimes by month
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **months**: Number of months to look back (1-24)
    - **category**: Optional crime category filter
    - **limit**: Maximum number of crimes to analyze (1-1000)
    """
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






