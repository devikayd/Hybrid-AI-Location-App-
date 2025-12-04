"""
Hotspots clustering endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from decimal import Decimal
import logging

from app.services.clustering_service import clustering_service
from app.schemas.summary import HotspotsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/hotspots", response_model=HotspotsResponse)
async def detect_hotspots(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius_km: int = Query(5, ge=1, le=50, description="Search radius in kilometers"),
    min_samples: int = Query(3, ge=2, le=20, description="Minimum samples per cluster"),
    eps_km: float = Query(0.5, ge=0.1, le=2.0, description="Maximum distance between cluster points (km)")
) -> HotspotsResponse:
    """
    Detect hotspots using DBSCAN clustering
    
    Analyzes crime, event, news, and POI data to identify areas of high activity
    using density-based clustering. Returns both hotspot data and GeoJSON format.
    
    - **lat**: Latitude (-90 to 90)
    - **lon**: Longitude (-180 to 180)
    - **radius_km**: Search radius in kilometers (1-50)
    - **min_samples**: Minimum samples per cluster (2-20)
    - **eps_km**: Maximum distance between cluster points in kilometers (0.1-2.0)
    
    Returns clustered hotspots with intensity scores, item counts, and GeoJSON
    representation suitable for map visualization.
    """
    try:
        result = await clustering_service.detect_hotspots(
            lat=Decimal(str(lat)),
            lon=Decimal(str(lon)),
            radius_km=radius_km,
            min_samples=min_samples,
            eps_km=eps_km
        )
        
        logger.info(f"Hotspots detected for {lat}, {lon}: {len(result.hotspots)} clusters")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hotspot detection error for {lat}, {lon}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Hotspot detection service temporarily unavailable: {str(e)}"
        )






