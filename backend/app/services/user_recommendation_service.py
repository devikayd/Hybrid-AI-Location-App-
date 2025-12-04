"""
User-Based Recommendation Service - Recommendations based on user interactions
"""

import logging
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from collections import Counter

from app.core.config import settings
from app.schemas.user_interaction import UserRecommendationItem, UserRecommendationsResponse
from app.services.location_data_service import location_data_service
from app.services.user_interaction_service import user_interaction_service
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class UserRecommendationService:
    """Service for generating recommendations based on user interactions"""
    
    async def get_recommendations(
        self,
        user_id: str,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 10,
        limit: int = 20,
        db: Session = None
    ) -> UserRecommendationsResponse:
        """
        Get recommendations based on user's interaction history
        """
        try:
            # Get user preferences from interactions
            user_prefs = await user_interaction_service.get_user_preferences(user_id, db)
            
            if user_prefs["total_interactions"] == 0:
                # No interactions yet, return empty recommendations
                return UserRecommendationsResponse(
                    user_id=user_id,
                    recommendations=[],
                    based_on_interactions=0,
                    total_recommendations=0
                )
            
            # Get all location data
            location_data = await location_data_service.get_location_data(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                user_id=user_id
            )
            
            # Score items based on user preferences
            scored_items = []
            
            # Combine all items
            all_items = location_data.events + location_data.pois + location_data.news + location_data.crimes
            
            for item in all_items:
                # Skip items user has already interacted with
                if item.is_liked or item.is_saved:
                    continue
                
                # Calculate match score based on user preferences
                match_score = self._calculate_match_score(item, user_prefs)
                
                if match_score > 0:  # Only include items with some match
                    relevance_reason = self._generate_relevance_reason(item, user_prefs, match_score)
                    
                    scored_items.append(UserRecommendationItem(
                        id=item.id,
                        type=item.type,
                        title=item.title,
                        description=item.description,
                        lat=item.lat,
                        lon=item.lon,
                        category=item.category,
                        relevance_reason=relevance_reason,
                        match_score=match_score
                    ))
            
            # Sort by match score (highest first)
            scored_items.sort(key=lambda x: x.match_score, reverse=True)
            
            # Limit results
            recommendations = scored_items[:limit]
            
            return UserRecommendationsResponse(
                user_id=user_id,
                recommendations=recommendations,
                based_on_interactions=user_prefs["total_interactions"],
                total_recommendations=len(recommendations)
            )
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            raise AppException(f"Failed to generate recommendations: {str(e)}")
    
    def _calculate_match_score(
        self,
        item,
        user_prefs: dict
    ) -> float:
        """
        Calculate how well an item matches user preferences
        Returns score between 0 and 1
        """
        score = 0.0
        
        # Check type match (40% weight)
        if item.type in user_prefs["preferred_types"]:
            type_count = user_prefs["type_counts"].get(item.type, 0)
            score += 0.4 * min(type_count / 10.0, 1.0)  # Normalize by max interactions
        
        # Check category match (35% weight)
        if item.category and item.category in user_prefs["preferred_categories"]:
            category_count = user_prefs["category_counts"].get(item.category, 0)
            score += 0.35 * min(category_count / 10.0, 1.0)
        
        # Check subtype match (25% weight)
        if item.subtype and item.subtype in user_prefs["preferred_subtypes"]:
            subtype_count = user_prefs["subtype_counts"].get(item.subtype, 0)
            score += 0.25 * min(subtype_count / 10.0, 1.0)
        
        # Boost score if multiple matches
        match_count = sum([
            item.type in user_prefs["preferred_types"],
            item.category in user_prefs["preferred_categories"] if item.category else False,
            item.subtype in user_prefs["preferred_subtypes"] if item.subtype else False
        ])
        
        if match_count >= 2:
            score *= 1.3  # 30% boost for multiple matches
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _generate_relevance_reason(
        self,
        item,
        user_prefs: dict,
        match_score: float
    ) -> str:
        """Generate human-readable reason why item was recommended"""
        reasons = []
        
        if item.type in user_prefs["preferred_types"]:
            count = user_prefs["type_counts"].get(item.type, 0)
            reasons.append(f"You've liked/saved {count} {item.type}(s) before")
        
        if item.category and item.category in user_prefs["preferred_categories"]:
            count = user_prefs["category_counts"].get(item.category, 0)
            reasons.append(f"You've shown interest in {item.category} ({count} times)")
        
        if item.subtype and item.subtype in user_prefs["preferred_subtypes"]:
            count = user_prefs["subtype_counts"].get(item.subtype, 0)
            reasons.append(f"Matches your preference for {item.subtype} items")
        
        if not reasons:
            return "Based on your interaction patterns"
        
        return "; ".join(reasons)


# Service instance
user_recommendation_service = UserRecommendationService()


