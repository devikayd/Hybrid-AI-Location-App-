"""
Geocoding endpoints
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
import logging

from app.services.geocode_service import geocode_service
from app.schemas.geocode import GeocodeRequest, GeocodeResponse, GeocodeError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/geocode", response_model=GeocodeResponse)
async def geocode(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: Optional[int] = Query(1, ge=1, le=10, description="Maximum number of results"),
    countrycodes: Optional[str] = Query("gb", description="Country codes (comma-separated)")
) -> GeocodeResponse:
    """
    Geocode a location query using Nominatim API
    
    This endpoint searches for locations by name, postcode, or address
    and returns coordinates and formatted address information.
    
    - **q**: Search query (place name, postcode, address)
    - **limit**: Maximum number of results to return (1-10)
    - **countrycodes**: Country codes to limit search (default: gb for UK)
    
    Results are cached for 7 days to improve performance and reduce API calls.
    """
    try:
        # Validate query
        if not q.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Perform geocoding
        result = await geocode_service.geocode(
            query=q.strip(),
            limit=limit,
            countrycodes=countrycodes
        )
        
        logger.info(f"Geocoding successful for query: {q}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Geocoding error for query '{q}': {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Geocoding service temporarily unavailable: {str(e)}"
        )


@router.get("/geocode/reverse")
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude")
):
    """
    Reverse geocode coordinates to address
    
    Convert latitude and longitude coordinates to a human-readable address.
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    """
    try:
        from decimal import Decimal
        
        result = await geocode_service.reverse_geocode(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon))
        )
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="No address found for the given coordinates"
            )
        
        logger.info(f"Reverse geocoding successful for {lat}, {lon}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reverse geocoding error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Reverse geocoding service temporarily unavailable: {str(e)}"
        )






