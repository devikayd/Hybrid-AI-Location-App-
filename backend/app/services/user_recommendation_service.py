"""
User-Based Recommendation Service - Recommendations based on user interactions

Enhanced with:
- Hybrid recommendations (content + collaborative + implicit feedback)
- Diversity-aware re-ranking (MMR)
- Contextual bandits for cold-start exploration
- Implicit feedback weighting (recency decay)
"""

import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from collections import Counter
from datetime import datetime

from app.core.config import settings
from app.schemas.user_interaction import UserRecommendationItem, UserRecommendationsResponse
from app.services.location_data_service import location_data_service
from app.services.user_interaction_service import user_interaction_service
from app.core.exceptions import AppException

# Import recommendation enhancements
try:
    from app.ml.recommendation_enhancements import (
        recommendation_enhancements,
        HybridRecommender,
        ImplicitFeedbackWeighter,
        DiversityReranker,
        get_recommendation_status
    )
    ENHANCEMENTS_AVAILABLE = True
except ImportError:
    ENHANCEMENTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class UserRecommendationService:
    """Service for generating recommendations based on user interactions"""

    def __init__(self):
        self.use_enhancements = ENHANCEMENTS_AVAILABLE
        self._collab_fitted = False

        if self.use_enhancements:
            logger.info("Recommendation enhancements loaded successfully")
        else:
            logger.warning("Recommendation enhancements not available, using basic content-based filtering")

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
            
            # Get all location data
            location_data = await location_data_service.get_location_data(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                user_id=user_id
            )
            
            if user_prefs["total_interactions"] == 0:
                all_items = location_data.events + location_data.pois + location_data.news + location_data.crimes
                
                # Sort by date (most recent first)
                def get_sort_key(item):
                    # Priority: events > news > crimes > pois ,for items without dates
                    type_priority = {"event": 0, "news": 1, "crime": 2, "poi": 3}.get(item.type, 4)
                    
                    if item.date:
                        try:
                            item_date = datetime.fromisoformat(item.date.replace('Z', '+00:00'))
                            return (-item_date.timestamp(), type_priority)
                        except:
                            pass
                    
                    if item.metadata:
                        hours_ahead = item.metadata.get("hours_ahead")
                        hours_ago = item.metadata.get("hours_ago")
                        if hours_ahead is not None:
                            return (-hours_ahead, type_priority)
                        if hours_ago is not None:
                            return (hours_ago, type_priority)
                    # Fallback: use type priority
                    return (999999, type_priority)
                
                sorted_items = sorted(all_items, key=get_sort_key)
                
                # Take top 5 most recent items
                recent_items = sorted_items[:5]
                
                # Convert to recommendation items
                recommendations = []
                for item in recent_items:
                    relevance_reason = f"Recently added {item.type}"
                    if item.date:
                        relevance_reason = f"Recent {item.type}"
                    elif item.metadata:
                        hours_ahead = item.metadata.get("hours_ahead")
                        hours_ago = item.metadata.get("hours_ago")
                        if hours_ahead:
                            relevance_reason = f"Upcoming {item.type}"
                        elif hours_ago:
                            relevance_reason = f"Recent {item.type}"
                    
                    recommendations.append(UserRecommendationItem(
                        id=item.id,
                        type=item.type,
                        title=item.title,
                        description=item.description,
                        lat=item.lat,
                        lon=item.lon,
                        category=item.category,
                        subtype=item.subtype,
                        url=item.url,
                        date=item.date,
                        metadata=item.metadata,
                        relevance_reason=relevance_reason,
                        match_score=0.5
                    ))
                
                return UserRecommendationsResponse(
                    user_id=user_id,
                    recommendations=recommendations,
                    based_on_interactions=0,
                    total_recommendations=len(recommendations)
                )
            
            # Combine all items
            all_items = location_data.events + location_data.pois + location_data.news + location_data.crimes

            # Filter out already interacted items
            candidate_items = [item for item in all_items if not (item.is_liked or item.is_saved)]

            if not candidate_items:
                return UserRecommendationsResponse(
                    user_id=user_id,
                    recommendations=[],
                    based_on_interactions=user_prefs["total_interactions"],
                    total_recommendations=0
                )

            # Use enhanced hybrid recommendations if available
            if self.use_enhancements:
                recommendations = await self._get_hybrid_recommendations(
                    user_id, candidate_items, user_prefs, limit, db
                )
            else:
                recommendations = self._get_content_based_recommendations(
                    candidate_items, user_prefs, limit
                )
            
            # Fallback: If no recommendations found
            # return recent items similar to the 0 interactions
            if len(recommendations) == 0:
                # Filter out items user has already interacted with
                available_items = [item for item in all_items if not (item.is_liked or item.is_saved)]
                
                if available_items:
                    # Sort by date (most recent first)
                    def get_sort_key(item):
                        # Priority: events > news > crimes > pois, for items without dates
                        type_priority = {"event": 0, "news": 1, "crime": 2, "poi": 3}.get(item.type, 4)
                        
                        if item.date:
                            try:
                                item_date = datetime.fromisoformat(item.date.replace('Z', '+00:00'))
                                return (-item_date.timestamp(), type_priority)
                            except:
                                pass
                        
                        if item.metadata:
                            hours_ahead = item.metadata.get("hours_ahead")
                            hours_ago = item.metadata.get("hours_ago")
                            if hours_ahead is not None:
                                return (-hours_ahead, type_priority)
                            if hours_ago is not None:
                                return (hours_ago, type_priority)
                        
                        return (999999, type_priority)
                    
                    sorted_items = sorted(available_items, key=get_sort_key)
                    recent_items = sorted_items[:min(limit, 5)]
                    
                    # Convert to recommendation items
                    recommendations = []
                    for item in recent_items:
                        relevance_reason = f"Recent {item.type} (no matching preferences found)"
                        if item.date:
                            relevance_reason = f"Recent {item.type}"
                        elif item.metadata:
                            hours_ahead = item.metadata.get("hours_ahead")
                            hours_ago = item.metadata.get("hours_ago")
                            if hours_ahead:
                                relevance_reason = f"Upcoming {item.type}"
                            elif hours_ago:
                                relevance_reason = f"Recent {item.type}"
                        
                        recommendations.append(UserRecommendationItem(
                            id=item.id,
                            type=item.type,
                            title=item.title,
                            description=item.description,
                            lat=item.lat,
                            lon=item.lon,
                            category=item.category,
                            subtype=item.subtype,
                            url=item.url,
                            date=item.date,
                            metadata=item.metadata,
                            relevance_reason=relevance_reason,
                            match_score=0.3
                        ))
            
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
            score *= 1.3
        
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

    def _get_content_based_recommendations(
        self,
        candidate_items: List,
        user_prefs: dict,
        limit: int
    ) -> List[UserRecommendationItem]:
        """
        Original content-based filtering (fallback method).
        """
        scored_items = []

        for item in candidate_items:
            match_score = self._calculate_match_score(item, user_prefs)

            if match_score > 0:
                relevance_reason = self._generate_relevance_reason(item, user_prefs, match_score)

                scored_items.append(UserRecommendationItem(
                    id=item.id,
                    type=item.type,
                    title=item.title,
                    description=item.description,
                    lat=item.lat,
                    lon=item.lon,
                    category=item.category,
                    subtype=item.subtype,
                    url=item.url,
                    date=item.date,
                    metadata=item.metadata,
                    relevance_reason=relevance_reason,
                    match_score=match_score
                ))

        # Sort by match score (highest first)
        scored_items.sort(key=lambda x: x.match_score, reverse=True)

        return scored_items[:limit]

    async def _get_hybrid_recommendations(
        self,
        user_id: str,
        candidate_items: List,
        user_prefs: dict,
        limit: int,
        db: Session
    ) -> List[UserRecommendationItem]:
        """
        Enhanced hybrid recommendation combining content, collaborative, and implicit feedback.
        """
        try:
            # Convert items to dicts for hybrid recommender
            item_dicts = self._convert_items_to_dicts(candidate_items)

            # Calculate content-based scores
            content_scores = {}
            for item in candidate_items:
                content_scores[item.id] = self._calculate_match_score(item, user_prefs)

            # Get user's interaction history for implicit feedback
            user_interactions = await self._get_user_interactions(user_id, db)

            # Use hybrid recommender
            recommended_dicts = recommendation_enhancements.recommend(
                user_id=user_id,
                candidate_items=item_dicts,
                content_scores=content_scores,
                user_interactions=user_interactions,
                n_recommendations=limit,
                apply_diversity=True,
                apply_exploration=user_prefs["total_interactions"] < 10
            )

            # Convert back to UserRecommendationItem
            # Create lookup map for original items
            item_lookup = {item.id: item for item in candidate_items}
            recommendations = []

            for rec_dict in recommended_dicts:
                item_id = rec_dict.get('id')
                original_item = item_lookup.get(item_id)

                if not original_item:
                    continue

                hybrid_score = rec_dict.get('_hybrid_score', 0.0)
                explored = rec_dict.get('_explored', False)

                # Generate relevance reason with enhancement info
                base_reason = self._generate_relevance_reason(
                    original_item, user_prefs, hybrid_score
                )

                if explored:
                    relevance_reason = f"Exploring new content: {base_reason}"
                else:
                    relevance_reason = f"Personalized for you: {base_reason}"

                recommendations.append(UserRecommendationItem(
                    id=original_item.id,
                    type=original_item.type,
                    title=original_item.title,
                    description=original_item.description,
                    lat=original_item.lat,
                    lon=original_item.lon,
                    category=original_item.category,
                    subtype=original_item.subtype,
                    url=original_item.url,
                    date=original_item.date,
                    metadata=original_item.metadata,
                    relevance_reason=relevance_reason,
                    match_score=hybrid_score
                ))

            return recommendations

        except Exception as e:
            logger.warning(f"Hybrid recommendation failed, falling back to content-based: {e}")
            return self._get_content_based_recommendations(candidate_items, user_prefs, limit)

    def _convert_items_to_dicts(self, items: List) -> List[Dict[str, Any]]:
        """Convert location items to dicts for hybrid recommender."""
        return [
            {
                'id': item.id,
                'type': item.type,
                'category': item.category,
                'subtype': item.subtype,
                'source': item.metadata.get('source') if item.metadata else None,
                'title': item.title,
                'description': item.description
            }
            for item in items
        ]

    async def _get_user_interactions(self, user_id: str, db: Session) -> List[Dict[str, Any]]:
        """Get user's interaction history for implicit feedback weighting."""
        try:
            interactions = await user_interaction_service.get_user_interactions(user_id, db)

            return [
                {
                    'item_id': interaction.item_id,
                    'interaction_type': interaction.interaction_type,
                    'created_at': interaction.created_at
                }
                for interaction in interactions
            ]
        except Exception as e:
            logger.warning(f"Failed to get user interactions: {e}")
            return []

    async def update_feedback(self, item_id: str, positive: bool):
        """
        Update contextual bandit with user feedback for explore-exploit learning.

        Args:
            item_id: Item that received feedback
            positive: Whether feedback was positive (like/save)
        """
        if self.use_enhancements:
            recommendation_enhancements.update_feedback(item_id, positive)

    def get_enhancement_status(self) -> Dict[str, Any]:
        """Get status of recommendation enhancements."""
        if self.use_enhancements:
            return get_recommendation_status()
        return {
            'available': False,
            'message': 'Recommendation enhancements not loaded'
        }


# Service instance
user_recommendation_service = UserRecommendationService()


