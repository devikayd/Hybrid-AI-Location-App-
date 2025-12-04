"""
Data Cleaning API endpoints

Purpose:
- Provides API endpoints for triggering data cleaning
- Supports cleaning individual data types or all data
- Returns cleaning statistics

Technology:
- FastAPI: REST API framework
- Pydantic: Request/response validation
- Async/await: Non-blocking data cleaning
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field
import logging

from app.services.data_cleaning_service import data_cleaning_service

logger = logging.getLogger(__name__)
router = APIRouter()


class CleaningRequest(BaseModel):
    """Request model for data cleaning"""
    limit_per_type: Optional[int] = Field(None, ge=1, le=10000, description="Maximum records per data type to clean")
    dry_run: bool = Field(False, description="If True, don't save changes (just report)")
    clean_crimes: bool = Field(True, description="Clean crime data")
    clean_news: bool = Field(True, description="Clean news data")
    clean_pois: bool = Field(True, description="Clean POI data")


class CleaningResponse(BaseModel):
    """Response model for data cleaning"""
    success: bool = Field(..., description="Whether cleaning was successful")
    message: str = Field(..., description="Status message")
    statistics: dict = Field(..., description="Cleaning statistics")


@router.post("/clean", response_model=CleaningResponse)
async def clean_data(request: CleaningRequest):
    """
    Clean all data types
    
    What it does:
    - Cleans crime, news, and POI data
    - Removes duplicates
    - Handles missing values
    - Normalizes formats
    - Validates data quality
    
    Parameters:
    - limit_per_type: Maximum records per type to clean (None = all)
    - dry_run: If True, don't save changes (just report)
    - clean_crimes: Clean crime data
    - clean_news: Clean news data
    - clean_pois: Clean POI data
    
    Returns:
    - Cleaning statistics for each data type
    """
    try:
        logger.info(f"Starting data cleaning (limit={request.limit_per_type}, dry_run={request.dry_run})")
        
        # Clean each data type
        results = {}
        
        if request.clean_crimes:
            crime_result = await data_cleaning_service.clean_crime_data(
                limit=request.limit_per_type,
                dry_run=request.dry_run
            )
            results['crimes'] = crime_result
        
        if request.clean_news:
            news_result = await data_cleaning_service.clean_news_data(
                limit=request.limit_per_type,
                dry_run=request.dry_run
            )
            results['news'] = news_result
        
        if request.clean_pois:
            poi_result = await data_cleaning_service.clean_poi_data(
                limit=request.limit_per_type,
                dry_run=request.dry_run
            )
            results['pois'] = poi_result
        
        # Calculate totals
        total_cleaned = sum(r.get('cleaned_records', 0) for r in results.values())
        total_duplicates = sum(r.get('duplicates_removed', 0) for r in results.values())
        total_invalid = sum(r.get('invalid_records_flagged', 0) for r in results.values())
        
        return CleaningResponse(
            success=True,
            message=f"Data cleaning complete: {total_cleaned} records cleaned, {total_duplicates} duplicates removed, {total_invalid} invalid records flagged",
            statistics={
                'results': results,
                'total_cleaned': total_cleaned,
                'total_duplicates_removed': total_duplicates,
                'total_invalid_flagged': total_invalid,
                'dry_run': request.dry_run
            }
        )
        
    except Exception as e:
        logger.error(f"Data cleaning failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Data cleaning failed: {str(e)}"
        )


@router.post("/clean/crimes", response_model=CleaningResponse)
async def clean_crime_data(
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Maximum records to clean"),
    dry_run: bool = Query(False, description="If True, don't save changes")
):
    """
    Clean crime data only
    
    What it does:
    - Removes duplicate crime records
    - Handles missing values
    - Normalizes formats
    - Validates data quality
    
    Returns:
    - Crime data cleaning statistics
    """
    try:
        result = await data_cleaning_service.clean_crime_data(limit=limit, dry_run=dry_run)
        
        return CleaningResponse(
            success=True,
            message=f"Crime data cleaning complete: {result['cleaned_records']} records cleaned",
            statistics=result
        )
        
    except Exception as e:
        logger.error(f"Crime data cleaning failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Crime data cleaning failed: {str(e)}"
        )


@router.post("/clean/news", response_model=CleaningResponse)
async def clean_news_data(
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Maximum records to clean"),
    dry_run: bool = Query(False, description="If True, don't save changes")
):
    """
    Clean news data only
    
    Returns:
    - News data cleaning statistics
    """
    try:
        result = await data_cleaning_service.clean_news_data(limit=limit, dry_run=dry_run)
        
        return CleaningResponse(
            success=True,
            message=f"News data cleaning complete: {result['cleaned_records']} records cleaned",
            statistics=result
        )
        
    except Exception as e:
        logger.error(f"News data cleaning failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"News data cleaning failed: {str(e)}"
        )


@router.post("/clean/pois", response_model=CleaningResponse)
async def clean_poi_data(
    limit: Optional[int] = Query(None, ge=1, le=10000, description="Maximum records to clean"),
    dry_run: bool = Query(False, description="If True, don't save changes")
):
    """
    Clean POI data only
    
    Returns:
    - POI data cleaning statistics
    """
    try:
        result = await data_cleaning_service.clean_poi_data(limit=limit, dry_run=dry_run)
        
        return CleaningResponse(
            success=True,
            message=f"POI data cleaning complete: {result['cleaned_records']} records cleaned",
            statistics=result
        )
        
    except Exception as e:
        logger.error(f"POI data cleaning failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"POI data cleaning failed: {str(e)}"
        )


@router.get("/clean/stats")
async def get_cleaning_stats():
    """
    Get data cleaning statistics
    
    Returns:
    - Overall cleaning statistics
    """
    try:
        stats = data_cleaning_service.get_stats()
        
        return {
            'success': True,
            'statistics': stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get cleaning stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cleaning stats: {str(e)}"
        )



