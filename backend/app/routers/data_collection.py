"""
Data Collection API endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field
import logging

from app.services.data_collection_service import data_collection_service

logger = logging.getLogger(__name__)
router = APIRouter()


class CollectionRequest(BaseModel):
    """Request model for data collection"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude (-90 to 90)")
    lon: float = Field(..., ge=-180, le=180, description="Longitude (-180 to 180)")
    radius_km: int = Field(10, ge=1, le=50, description="Search radius in kilometers")
    months: int = Field(12, ge=1, le=36, description="Historical months for crime data")
    limit_per_type: int = Field(50, ge=1, le=200, description="Maximum records per data type")
    collect_crimes: bool = Field(True, description="Collect crime data")
    collect_events: bool = Field(True, description="Collect event data")
    collect_news: bool = Field(True, description="Collect news data")
    collect_pois: bool = Field(True, description="Collect POI data")


class CollectionResponse(BaseModel):
    """Response model for data collection"""
    success: bool = Field(..., description="Whether collection was successful")
    message: str = Field(..., description="Status message")
    statistics: dict = Field(..., description="Collection statistics")


@router.post("/collect", response_model=CollectionResponse)
async def collect_data(request: CollectionRequest):
    """
    Collect data for a location
    
    This endpoint triggers data collection from all configured APIs
    and stores the results in the database for ML training.
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-50)
    - **months**: Historical months for crime data (1-36)
    - **limit_per_type**: Maximum records per data type (1-200)
    - **collect_crimes**: Whether to collect crime data
    - **collect_events**: Whether to collect event data
    - **collect_news**: Whether to collect news data
    - **collect_pois**: Whether to collect POI data
    
    Returns collection statistics including:
    - Number of records collected
    - Number of duplicates skipped
    - Number of errors encountered
    """
    try:
        lat = Decimal(str(request.lat))
        lon = Decimal(str(request.lon))
        
        statistics = {}
        
        # Collect data based on flags
        if request.collect_crimes:
            statistics['crimes'] = await data_collection_service.collect_crime_data(
                lat=lat,
                lon=lon,
                months=request.months,
                limit=request.limit_per_type
            )
        
        if request.collect_events:
            statistics['events'] = await data_collection_service.collect_event_data(
                lat=lat,
                lon=lon,
                within_km=request.radius_km,
                limit=request.limit_per_type
            )
        
        if request.collect_news:
            statistics['news'] = await data_collection_service.collect_news_data(
                lat=lat,
                lon=lon,
                radius_km=request.radius_km,
                limit=request.limit_per_type
            )
        
        if request.collect_pois:
            statistics['pois'] = await data_collection_service.collect_poi_data(
                lat=lat,
                lon=lon,
                radius_km=request.radius_km,
                limit=request.limit_per_type
            )
        
        # Calculate totals
        total_collected = sum(
            stats.get('collected', 0) for stats in statistics.values()
        )
        total_errors = sum(
            stats.get('errors', 0) for stats in statistics.values()
        )
        
        statistics['total'] = {
            'collected': total_collected,
            'errors': total_errors
        }
        
        logger.info(f"Data collection completed for {lat}, {lon}: {total_collected} records collected")
        
        return CollectionResponse(
            success=True,
            message=f"Data collection completed: {total_collected} records collected",
            statistics=statistics
        )
        
    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Data collection failed: {str(e)}"
        )


@router.post("/collect/all", response_model=CollectionResponse)
async def collect_all_data(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(10, ge=1, le=50, description="Search radius in kilometers"),
    months: int = Query(12, ge=1, le=36, description="Historical months for crime data"),
    limit_per_type: int = Query(50, ge=1, le=200, description="Maximum records per data type")
):

    try:
        lat_decimal = Decimal(str(lat))
        lon_decimal = Decimal(str(lon))
        
        statistics = await data_collection_service.collect_all_data(
            lat=lat_decimal,
            lon=lon_decimal,
            radius_km=radius_km,
            months=months,
            limit_per_type=limit_per_type
        )
        
        logger.info(f"Batch data collection completed for {lat}, {lon}")
        
        return CollectionResponse(
            success=True,
            message=f"Batch collection completed: {statistics.get('total_collected', 0)} records collected",
            statistics=statistics
        )
        
    except Exception as e:
        logger.error(f"Batch data collection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch data collection failed: {str(e)}"
        )


@router.get("/stats")
async def get_collection_stats():
    """
    Get data collection statistics
    """
    try:
        stats = data_collection_service.get_stats()
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get collection stats: {str(e)}"
        )




