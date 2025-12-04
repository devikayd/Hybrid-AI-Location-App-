"""
Feature Engineering Router

What this router does:
- Provides API endpoints for feature engineering
- Extracts features from cleaned data
- Creates training datasets
- Stores features in training_data table

Endpoints:
- POST /api/v1/features/extract: Extract features for a location
- POST /api/v1/features/batch: Extract features for multiple locations
- POST /api/v1/features/from-database: Extract features from all cleaned data
- GET /api/v1/features/stats: Get feature engineering statistics
"""

import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel, Field

from app.services.feature_engineering_service import feature_engineering_service

logger = logging.getLogger(__name__)
router = APIRouter()


class LocationRequest(BaseModel):
    """Request model for single location feature extraction"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")
    radius_km: float = Field(5.0, ge=0.1, le=50.0, description="Search radius in kilometers")
    location_name: Optional[str] = Field(None, description="Optional location name")


class BatchLocationRequest(BaseModel):
    """Request model for batch location feature extraction"""
    locations: List[Dict[str, float]] = Field(..., description="List of {lat, lon} dictionaries")
    radius_km: float = Field(5.0, ge=0.1, le=50.0, description="Search radius in kilometers")
    limit: Optional[int] = Field(None, ge=1, le=1000, description="Maximum locations to process")


class DatabaseExtractionRequest(BaseModel):
    """Request model for database feature extraction"""
    grid_size_km: float = Field(1.0, ge=0.1, le=10.0, description="Spatial grid size in kilometers")
    limit: Optional[int] = Field(None, ge=1, le=10000, description="Maximum locations to process")


class FeatureExtractionResponse(BaseModel):
    """Response model for feature extraction"""
    success: bool
    message: str
    location: Optional[Dict[str, Any]] = None
    features: Optional[Dict[str, float]] = None
    safety_features: Optional[Dict[str, float]] = None
    popularity_features: Optional[Dict[str, float]] = None
    data_quality_score: Optional[float] = None
    missing_features: Optional[List[str]] = None
    training_records_created: Optional[int] = None


class BatchExtractionResponse(BaseModel):
    """Response model for batch feature extraction"""
    success: bool
    message: str
    total_locations: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]]
    statistics: Dict[str, Any]


@router.post("/extract", response_model=FeatureExtractionResponse)
async def extract_features_for_location(
    request: LocationRequest
):
    """
    Extract features for a specific location
    
    What it does:
    1. Loads cleaned data within radius
    2. Calculates features (crime, POI, news, events)
    3. Normalizes features
    4. Stores in training_data table
    
    Parameters:
    - lat, lon: Location coordinates
    - radius_km: Search radius
    - location_name: Optional location name
    
    Returns:
    - Extracted features and metadata
    
    Example:
    ```json
    {
        "lat": 51.5074,
        "lon": -0.1278,
        "radius_km": 5.0,
        "location_name": "London, UK"
    }
    ```
    """
    try:
        logger.info(f"Extracting features for location: {request.lat}, {request.lon}")
        
        result = await feature_engineering_service.extract_features_for_location(
            lat=Decimal(str(request.lat)),
            lon=Decimal(str(request.lon)),
            radius_km=request.radius_km,
            location_name=request.location_name
        )
        
        return FeatureExtractionResponse(
            success=True,
            message="Features extracted successfully",
            location=result['location'],
            features=result['features'],
            safety_features=result['safety_features'],
            popularity_features=result['popularity_features'],
            data_quality_score=result['data_quality_score'],
            missing_features=result['missing_features'],
            training_records_created=result['training_records_created']
        )
        
    except Exception as e:
        logger.error(f"Feature extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Feature extraction failed: {str(e)}"
        )


@router.post("/batch", response_model=BatchExtractionResponse)
async def extract_features_batch(
    request: BatchLocationRequest
):
    """
    Extract features for multiple locations
    
    What it does:
    - Processes multiple locations
    - Extracts features for each
    - Stores in training_data table
    
    Parameters:
    - locations: List of {lat, lon} dictionaries
    - radius_km: Search radius
    - limit: Maximum locations to process
    
    Returns:
    - Batch processing statistics
    
    Example:
    ```json
    {
        "locations": [
            {"lat": 51.5074, "lon": -0.1278},
            {"lat": 40.7128, "lon": -74.0060}
        ],
        "radius_km": 5.0,
        "limit": 100
    }
    ```
    """
    try:
        logger.info(f"Extracting features for {len(request.locations)} locations")
        
        # Convert locations to tuples
        locations = [
            (Decimal(str(loc['lat'])), Decimal(str(loc['lon'])))
            for loc in request.locations
        ]
        
        result = await feature_engineering_service.extract_features_batch(
            locations=locations,
            radius_km=request.radius_km,
            limit=request.limit
        )
        
        return BatchExtractionResponse(
            success=True,
            message=f"Batch feature extraction completed: {result['successful']}/{result['total_locations']} successful",
            total_locations=result['total_locations'],
            successful=result['successful'],
            failed=result['failed'],
            errors=result['errors'],
            statistics=result['statistics']
        )
        
    except Exception as e:
        logger.error(f"Batch feature extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch feature extraction failed: {str(e)}"
        )


@router.post("/from-database", response_model=BatchExtractionResponse)
async def extract_features_from_database(
    request: DatabaseExtractionRequest
):
    """
    Extract features from all cleaned data in database
    
    What it does:
    1. Finds all unique locations in cleaned data
    2. Groups by spatial grid
    3. Extracts features for each grid cell
    4. Stores in training_data table
    
    Parameters:
    - grid_size_km: Size of spatial grid cells (km)
    - limit: Maximum locations to process
    
    Returns:
    - Extraction statistics
    
    Example:
    ```json
    {
        "grid_size_km": 1.0,
        "limit": 1000
    }
    ```
    """
    try:
        logger.info(f"Extracting features from database (grid_size={request.grid_size_km}km)")
        
        result = await feature_engineering_service.extract_features_from_database(
            grid_size_km=request.grid_size_km,
            limit=request.limit
        )
        
        return BatchExtractionResponse(
            success=True,
            message=f"Database feature extraction completed: {result['successful']}/{result['total_locations']} successful",
            total_locations=result['total_locations'],
            successful=result['successful'],
            failed=result['failed'],
            errors=result['errors'],
            statistics=result['statistics']
        )
        
    except Exception as e:
        logger.error(f"Database feature extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database feature extraction failed: {str(e)}"
        )


@router.get("/stats", response_model=Dict[str, Any])
async def get_feature_engineering_stats():
    """
    Get feature engineering statistics
    
    Returns:
    - Current statistics (locations processed, features extracted, etc.)
    """
    try:
        stats = feature_engineering_service.get_stats()
        return {
            'success': True,
            'statistics': stats
        }
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )



