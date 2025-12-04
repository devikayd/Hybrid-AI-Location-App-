"""
User Interaction endpoints - Like/Save functionality
"""

from fastapi import APIRouter, Body, HTTPException, Depends, Query
from typing import Optional, List
import logging

from app.services.user_interaction_service import user_interaction_service
from app.schemas.user_interaction import InteractionRequest, InteractionResponse
from app.models.user_interaction import UserInteraction
from app.core.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/interaction", response_model=InteractionResponse)
async def add_interaction(
    user_id: str = Query(..., description="User identifier"),
    interaction: InteractionRequest = Body(..., description="Interaction details"),
    db: Session = Depends(get_db)
) -> InteractionResponse:
    """
    Add or toggle a user interaction (like or save)
    
    - **user_id**: User identifier (can be session ID for academic purposes)
    - **interaction**: Interaction details (item_id, item_type, interaction_type: 'like' or 'save')
    
    If interaction already exists, it will be toggled (liked -> unliked, saved -> unsaved)
    """
    try:
        if interaction.interaction_type not in ["like", "save"]:
            raise HTTPException(
                status_code=400,
                detail="interaction_type must be 'like' or 'save'"
            )
        
        result = await user_interaction_service.add_interaction(
            user_id=user_id,
            interaction_request=interaction,
            db=db
        )
        
        logger.info(f"Interaction {interaction.interaction_type} added for user {user_id}, item {interaction.item_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Interaction error for user {user_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Interaction service temporarily unavailable: {str(e)}"
        )


@router.get("/interactions", response_model=List[dict])
async def get_user_interactions(
    user_id: str = Query(..., description="User identifier"),
    interaction_type: Optional[str] = Query(None, description="Filter by interaction type: 'like' or 'save'"),
    item_type: Optional[str] = Query(None, description="Filter by item type: 'event', 'poi', 'news', 'crime'"),
    db: Session = Depends(get_db)
) -> List[dict]:
    """
    Get all user interactions (likes and saves)
    
    - **user_id**: User identifier
    - **interaction_type**: Optional filter by 'like' or 'save'
    - **item_type**: Optional filter by item type
    """
    try:
        interactions = await user_interaction_service.get_user_interactions(
            user_id=user_id,
            db=db,
            interaction_type=interaction_type,
            item_type=item_type
        )
        
        return [interaction.to_dict() for interaction in interactions]
        
    except Exception as e:
        logger.error(f"Error getting interactions for user {user_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to get interactions: {str(e)}"
        )


@router.get("/preferences", response_model=dict)
async def get_user_preferences(
    user_id: str = Query(..., description="User identifier"),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get user preferences based on interaction history
    
    Returns preferred types, categories, and subtypes based on user's likes/saves
    """
    try:
        preferences = await user_interaction_service.get_user_preferences(user_id, db)
        return preferences
        
    except Exception as e:
        logger.error(f"Error getting preferences for user {user_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to get preferences: {str(e)}"
        )


