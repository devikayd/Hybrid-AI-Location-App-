"""
User Interaction Service - Manages user likes and saves
"""

import logging
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.models.user_interaction import UserInteraction
from app.schemas.user_interaction import InteractionRequest, InteractionResponse
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class UserInteractionService:
    """Service for managing user interactions (likes, saves)"""
    
    async def add_interaction(
        self,
        user_id: str,
        interaction_request: InteractionRequest,
        db: Session
    ) -> InteractionResponse:
        """
        Add or toggle a user interaction (like/save)
        """
        try:
            # Check if interaction already exists
            existing = db.query(UserInteraction).filter(
                and_(
                    UserInteraction.user_id == user_id,
                    UserInteraction.item_id == interaction_request.item_id,
                    UserInteraction.item_type == interaction_request.item_type,
                    UserInteraction.interaction_type == interaction_request.interaction_type
                )
            ).first()
            
            if existing:
                # Toggle: if active, deactivate; if inactive, activate
                existing.is_active = not existing.is_active
                db.commit()
                db.refresh(existing)
                
                return InteractionResponse(
                    success=True,
                    message=f"Interaction {'activated' if existing.is_active else 'deactivated'}",
                    interaction_id=existing.id,
                    is_active=existing.is_active
                )
            else:
                # Create new interaction
                new_interaction = UserInteraction(
                    user_id=user_id,
                    item_id=interaction_request.item_id,
                    item_type=interaction_request.item_type,
                    interaction_type=interaction_request.interaction_type,
                    item_title=interaction_request.item_title,
                    item_category=interaction_request.item_category,
                    item_subtype=interaction_request.item_subtype,
                    latitude=float(interaction_request.lat) if interaction_request.lat else None,
                    longitude=float(interaction_request.lon) if interaction_request.lon else None,
                    location_name=interaction_request.location_name,
                    is_active=True
                )
                
                db.add(new_interaction)
                db.commit()
                db.refresh(new_interaction)
                
                return InteractionResponse(
                    success=True,
                    message="Interaction added successfully",
                    interaction_id=new_interaction.id,
                    is_active=True
                )
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding interaction: {e}")
            raise AppException(f"Failed to add interaction: {str(e)}")
    
    async def get_user_interactions(
        self,
        user_id: str,
        db: Session,
        interaction_type: Optional[str] = None,
        item_type: Optional[str] = None
    ) -> List[UserInteraction]:
        """
        Get all user interactions, optionally filtered by type
        """
        try:
            query = db.query(UserInteraction).filter(
                and_(
                    UserInteraction.user_id == user_id,
                    UserInteraction.is_active == True
                )
            )
            
            if interaction_type:
                query = query.filter(UserInteraction.interaction_type == interaction_type)
            
            if item_type:
                query = query.filter(UserInteraction.item_type == item_type)
            
            return query.order_by(UserInteraction.created_at.desc()).all()
            
        except Exception as e:
            logger.error(f"Error getting user interactions: {e}")
            raise AppException(f"Failed to get interactions: {str(e)}")
    
    async def get_user_interactions_for_items(
        self,
        user_id: str,
        item_ids: List[str],
        db: Session
    ) -> List[UserInteraction]:
        """
        Get user interactions for specific items (used for checking liked/saved status)
        """
        try:
            interactions = db.query(UserInteraction).filter(
                and_(
                    UserInteraction.user_id == user_id,
                    UserInteraction.item_id.in_(item_ids),
                    UserInteraction.is_active == True
                )
            ).all()
            
            return interactions
                
        except Exception as e:
            logger.error(f"Error getting interactions for items: {e}")
            return []
    
    async def get_user_preferences(
        self,
        user_id: str,
        db: Session
    ) -> dict:
        """
        Analyze user interactions to determine preferences
        Returns: dict with preferred categories, types, subtypes
        """
        try:
            interactions = await self.get_user_interactions(user_id, db)
            
            if not interactions:
                return {
                    "preferred_types": [],
                    "preferred_categories": [],
                    "preferred_subtypes": [],
                    "total_interactions": 0
                }
            
            # Count interactions by type, category, subtype
            type_counts = {}
            category_counts = {}
            subtype_counts = {}
            
            for interaction in interactions:
                # Count types
                if interaction.item_type:
                    type_counts[interaction.item_type] = type_counts.get(interaction.item_type, 0) + 1
                
                # Count categories
                if interaction.item_category:
                    category_counts[interaction.item_category] = category_counts.get(interaction.item_category, 0) + 1
                
                # Count subtypes
                if interaction.item_subtype:
                    subtype_counts[interaction.item_subtype] = subtype_counts.get(interaction.item_subtype, 0) + 1
            
            preferred_types = [t for t, count in type_counts.items() if count >= 2]
            preferred_categories = [c for c, count in category_counts.items() if count >= 2]
            preferred_subtypes = [s for s, count in subtype_counts.items() if count >= 2]
            
            return {
                "preferred_types": preferred_types,
                "preferred_categories": preferred_categories,
                "preferred_subtypes": preferred_subtypes,
                "total_interactions": len(interactions),
                "type_counts": type_counts,
                "category_counts": category_counts,
                "subtype_counts": subtype_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {
                "preferred_types": [],
                "preferred_categories": [],
                "preferred_subtypes": [],
                "total_interactions": 0
            }


# Service instance
user_interaction_service = UserInteractionService()

