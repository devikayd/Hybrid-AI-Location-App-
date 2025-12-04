"""
Points of Interest (POI) data endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from decimal import Decimal
import logging

from app.services.pois_service import pois_service
from app.schemas.pois import POIResponse, POISummary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/pois", response_model=POIResponse)
async def get_pois(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(5, ge=1, le=50, description="Search radius in kilometers"),
    types: Optional[str] = Query(None, description="Comma-separated POI types to include"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of POIs to return")
) -> POIResponse:
    """
    Get Points of Interest (POI) data for a specific location
    
    Retrieves POI data from OpenStreetMap via Overpass API for the specified coordinates.
    Results are cached for 1 day to improve performance.
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-50)
    - **types**: Comma-separated POI types (amenity, tourism, shop values)
    - **limit**: Maximum number of POIs to return (1-500)
    
    Common POI types include:
    - **Amenities**: restaurant, cafe, bar, pub, hospital, pharmacy, bank, atm, fuel, school, university, library, museum, theatre, cinema, hotel
    - **Tourism**: attraction, museum, gallery, zoo, theme_park
    - **Shops**: supermarket, convenience, clothes, electronics, books
    
    Returns POIs with metadata including name, address, opening hours, and accessibility information.
    """
    try:
        result = await pois_service.get_pois(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km,
            types=types,
            limit=limit
        )
        
        logger.info(f"POI data retrieved for {lat}, {lon}: {result.total_count} POIs")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POI data error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"POI data service temporarily unavailable: {str(e)}"
        )


@router.get("/pois/summary", response_model=POISummary)
async def get_poi_summary(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(5, ge=1, le=50, description="Search radius in kilometers"),
    types: Optional[str] = Query(None, description="Comma-separated POI types to include"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of POIs to analyze")
) -> POISummary:
    """
    Get POI summary statistics for a location
    
    Provides aggregated statistics about POIs in the area, including:
    - Total POI count
    - POIs by type
    - POIs by amenity category
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-50)
    - **types**: Comma-separated POI types (amenity, tourism, shop values)
    - **limit**: Maximum number of POIs to analyze (1-500)
    """
    try:
        result = await pois_service.get_poi_summary(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km,
            types=types,
            limit=limit
        )
        
        logger.info(f"POI summary retrieved for {lat}, {lon}: {result.total_pois} total POIs")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POI summary error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"POI summary service temporarily unavailable: {str(e)}"
        )






