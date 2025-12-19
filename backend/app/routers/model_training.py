"""
Model Training Router

Endpoints:
- POST /api/v1/models/train: Train models
- POST /api/v1/models/train/safety: Train safety model only
- POST /api/v1/models/train/popularity: Train popularity model only
- GET /api/v1/models/status: Get training status
- GET /api/v1/models/evaluate: Get model evaluation metrics
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel, Field

from app.services.model_training_service import model_training_service

logger = logging.getLogger(__name__)
router = APIRouter()


class TrainingRequest(BaseModel):
    """Request model for model training"""
    test_size: float = Field(0.2, ge=0.1, le=0.5, description="Proportion of data for testing")
    random_state: int = Field(42, description="Random seed for reproducibility")
    min_samples: int = Field(50, ge=10, le=10000, description="Minimum samples required for training")
    model_type: Optional[str] = Field(None, description="Model type: 'safety', 'popularity', or None (both)")


class TrainingResponse(BaseModel):
    """Response model for model training"""
    success: bool
    message: str
    results: Dict[str, Any]


@router.post("/train", response_model=TrainingResponse)
async def train_models(request: TrainingRequest):
    """
    Train XGBoost models
    
    Example:
    ```json
    {
        "test_size": 0.2,
        "random_state": 42,
        "min_samples": 50,
        "model_type": null
    }
    ```
    """
    try:
        logger.info(f"Starting model training (type: {request.model_type or 'both'})")
        
        if request.model_type == "safety":
            result = await model_training_service.train_safety_model(
                test_size=request.test_size,
                random_state=request.random_state,
                min_samples=request.min_samples
            )
            results = {'safety': result}
        elif request.model_type == "popularity":
            result = await model_training_service.train_popularity_model(
                test_size=request.test_size,
                random_state=request.random_state,
                min_samples=request.min_samples
            )
            results = {'popularity': result}
        else:
            # Train both
            training_result = await model_training_service.train_all_models(
                test_size=request.test_size,
                random_state=request.random_state,
                min_samples=request.min_samples
            )
            results = training_result['results']
        
        success = any(r.get('success', False) for r in results.values())
        
        return TrainingResponse(
            success=success,
            message=f"Model training completed: {sum(1 for r in results.values() if r.get('success', False))}/{len(results)} models trained successfully",
            results=results
        )
        
    except ValueError as e:
        # Insufficient data
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Model training failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Model training failed: {str(e)}"
        )


@router.post("/train/safety", response_model=TrainingResponse)
async def train_safety_model(request: TrainingRequest):
    """Train safety model only"""
    request.model_type = "safety"
    return await train_models(request)


@router.post("/train/popularity", response_model=TrainingResponse)
async def train_popularity_model(request: TrainingRequest):
    """Train popularity model only"""
    request.model_type = "popularity"
    return await train_models(request)


@router.get("/status", response_model=Dict[str, Any])
async def get_training_status():
    """
    Get model training status
    """
    try:
        stats = model_training_service.get_training_stats()
        
        # Get latest model paths
        safety_model_path = model_training_service.get_latest_model_path("safety")
        popularity_model_path = model_training_service.get_latest_model_path("popularity")
        
        return {
            'success': True,
            'statistics': stats,
            'models': {
                'safety': {
                    'trained': stats['safety_model_trained'],
                    'version': stats['safety_model_version'],
                    'model_path': safety_model_path,
                    'metrics': stats.get('safety_model_metrics', {})
                },
                'popularity': {
                    'trained': stats['popularity_model_trained'],
                    'version': stats['popularity_model_version'],
                    'model_path': popularity_model_path,
                    'metrics': stats.get('popularity_model_metrics', {})
                }
            }
        }
    except Exception as e:
        logger.error(f"Failed to get training status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get training status: {str(e)}"
        )


@router.get("/evaluate", response_model=Dict[str, Any])
async def get_model_evaluation():
    """
    Get model evaluation metrics
    """
    try:
        stats = model_training_service.get_training_stats()
        
        return {
            'success': True,
            'metrics': {
                'safety': stats.get('safety_model_metrics', {}),
                'popularity': stats.get('popularity_model_metrics', {})
            }
        }
    except Exception as e:
        logger.error(f"Failed to get evaluation metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get evaluation metrics: {str(e)}"
        )



