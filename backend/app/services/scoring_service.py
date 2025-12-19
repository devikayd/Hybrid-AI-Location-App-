"""
Safety and popularity scoring service with XGBoost and deterministic fallback
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import asyncio
from datetime import datetime, timedelta
import math
from pathlib import Path

try:
    import xgboost as xgb
    import numpy as np
    import joblib
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

from app.core.config import settings
from app.core.redis import geocode_cache
from app.services.crime_service import crime_service
from app.services.events_service import events_service
from app.services.news_service import news_service
from app.services.pois_service import pois_service
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def _convert_numpy_types(obj: Any) -> Any:
    """Convert numpy types to native Python types for JSON serialization"""
    if XGBOOST_AVAILABLE:
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
    if isinstance(obj, dict):
        return {k: _convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    return obj


class ScoringService:
    """Service for safety and popularity scoring"""
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour cache for scores
        self.safety_model = None
        self.popularity_model = None
        self.safety_feature_names = None
        self.popularity_feature_names = None
        self._models_initialized = False
        self.models_dir = Path("backend/app/ml/models")
    
    async def initialize_models(self):
        """Initialize XGBoost models by loading from disk"""
        if self._models_initialized:
            return
        
        if XGBOOST_AVAILABLE:
            try:
                # Try to load trained models from disk
                self.safety_model, self.safety_feature_names = self._load_model("safety")
                self.popularity_model, self.popularity_feature_names = self._load_model("popularity")
                
                if self.safety_model or self.popularity_model:
                    logger.info("XGBoost models loaded from disk")
                else:
                    logger.warning("No trained models found. Using rule-based fallback.")
            except Exception as e:
                logger.warning(f"XGBoost model loading failed: {e}. Using rule-based fallback.")
                self.safety_model = None
                self.popularity_model = None
        
        self._models_initialized = True
    
    def _load_model(self, model_type: str):
        """Load trained model from disk"""
        if not XGBOOST_AVAILABLE:
            return None, None
        
        try:
            # Find latest model file
            model_files = list(self.models_dir.glob(f"{model_type}_model_*.pkl"))
            if not model_files:
                return None, None
            
            # Sort by modification time
            model_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            model_path = model_files[0]
            
            # Load model
            model = joblib.load(model_path)
            logger.info(f"Loaded {model_type} model from {model_path}")
            
            # Load feature names
            import json
            feature_files = list(self.models_dir.glob(f"{model_type}_features_*.json"))
            if feature_files:
                feature_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                with open(feature_files[0], 'r') as f:
                    feature_names = json.load(f)
                return model, feature_names
            
            return model, None
            
        except Exception as e:
            logger.warning(f"Failed to load {model_type} model: {e}")
            return None, None
    
    async def calculate_scores(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 5
    ) -> Dict[str, Any]:
        """
        Calculate safety and popularity scores for a location
        """
        # Generate cache key
        cache_key = geocode_cache.generate_key(
            "scores",
            lat=str(lat),
            lon=str(lon),
            radius_km=radius_km
        )
        
        # Check cache first
        cached_result = await geocode_cache.get(cache_key)
        if cached_result:
            logger.info(f"Scores cache hit for location: {lat}, {lon}")
            return cached_result
        
        try:
            # Initialize models
            await self.initialize_models()
            
            # Collect features
            features = await self._collect_features(lat, lon, radius_km)
            
            # Calculate scores
            safety_score = await self._calculate_safety_score(features)
            popularity_score = await self._calculate_popularity_score(features)
            
            # Ensure scores are native Python floats (not numpy types)
            safety_score = float(safety_score)
            popularity_score = float(popularity_score)
            
            # Calculate overall score
            overall_score = float(safety_score * 0.6 + popularity_score * 0.4)
            
            result = {
                "lat": float(lat),
                "lon": float(lon),
                "radius_km": radius_km,
                "safety_score": safety_score,
                "popularity_score": popularity_score,
                "overall_score": overall_score,
                "features": features,
                "cached": False,
                "source": "xgboost" if XGBOOST_AVAILABLE else "deterministic",
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Convert any numpy types to native Python types for JSON serialization
            result = _convert_numpy_types(result)
            
            # Cache the result
            await geocode_cache.set(cache_key, result)
            logger.info(f"Scores cache set for location: {lat}, {lon}")
            
            return result
            
        except Exception as e:
            logger.error(f"Score calculation failed for {lat}, {lon}: {e}")
            raise AppException(f"Score calculation failed: {str(e)}")
    
    async def _collect_features(self, lat: Decimal, lon: Decimal, radius_km: int) -> Dict[str, Any]:
        """Collect features for scoring"""
        features = {}
        
        # Collect data concurrently
        tasks = [
            self._collect_crime_features(lat, lon, radius_km),
            self._collect_event_features(lat, lon, radius_km),
            self._collect_news_features(lat, lon, radius_km),
            self._collect_poi_features(lat, lon, radius_km)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict):
                features.update(result)
            elif isinstance(result, Exception):
                logger.warning(f"Feature collection failed: {result}")
        
        return features
    
    async def _collect_crime_features(self, lat: Decimal, lon: Decimal, radius_km: int) -> Dict[str, Any]:
        """Collect crime-related features"""
        try:
            crime_response = await crime_service.get_crimes(
                lat=lat,
                lon=lon,
                months=12,
                limit=200
            )
            
            total_crimes = crime_response.total_count
            
            # Calculate crime density
            area_km2 = math.pi * (radius_km ** 2)
            crime_density = total_crimes / area_km2 if area_km2 > 0 else 0
            
            # Analyze crime severity
            violent_crimes = sum(1 for crime in crime_response.crimes 
                               if crime.category in ["violent-crime", "robbery", "burglary"])
            violent_crime_ratio = violent_crimes / total_crimes if total_crimes > 0 else 0
            
            # Recent crime trend
            recent_crimes = sum(1 for crime in crime_response.crimes 
                              if self._is_recent_crime(crime.date, months=3))
            recent_crime_ratio = recent_crimes / total_crimes if total_crimes > 0 else 0
            
            return {
                "total_crimes": total_crimes,
                "crime_density": crime_density,
                "violent_crime_ratio": violent_crime_ratio,
                "recent_crime_ratio": recent_crime_ratio
            }
        except Exception as e:
            logger.warning(f"Crime features collection failed: {e}")
            return {
                "total_crimes": 0,
                "crime_density": 0,
                "violent_crime_ratio": 0,
                "recent_crime_ratio": 0
            }
    
    async def _collect_event_features(self, lat: Decimal, lon: Decimal, radius_km: int) -> Dict[str, Any]:
        """Collect event-related features"""
        try:
            event_response = await events_service.get_events(
                lat=lat,
                lon=lon,
                within_km=radius_km,
                limit=200
            )
            
            total_events = event_response.total_count
            free_events = sum(1 for event in event_response.events if event.is_free)
            free_event_ratio = free_events / total_events if total_events > 0 else 0
            
            # Event diversity
            categories = set()
            for event in event_response.events:
                if event.category_id:
                    categories.add(event.category_id)
            event_diversity = len(categories)
            
            return {
                "total_events": total_events,
                "free_event_ratio": free_event_ratio,
                "event_diversity": event_diversity
            }
        except Exception as e:
            logger.warning(f"Event features collection failed: {e}")
            return {
                "total_events": 0,
                "free_event_ratio": 0,
                "event_diversity": 0
            }
    
    async def _collect_news_features(self, lat: Decimal, lon: Decimal, radius_km: int) -> Dict[str, Any]:
        """Collect news-related features"""
        try:
            news_response = await news_service.get_news(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=100
            )
            
            total_articles = news_response.total_count
            
            # Sentiment analysis
            sentiments = [article.sentiment for article in news_response.articles if article.sentiment is not None]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
            
            # News coverage frequency
            news_frequency = total_articles / 30 
            
            return {
                "total_articles": total_articles,
                "avg_sentiment": avg_sentiment,
                "news_frequency": news_frequency
            }
        except Exception as e:
            logger.warning(f"News features collection failed: {e}")
            return {
                "total_articles": 0,
                "avg_sentiment": 0,
                "news_frequency": 0
            }
    
    async def _collect_poi_features(self, lat: Decimal, lon: Decimal, radius_km: int) -> Dict[str, Any]:
        """Collect POI-related features"""
        try:
            poi_response = await pois_service.get_pois(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=200
            )
            
            total_pois = poi_response.total_count
            
            # POI diversity
            amenities = set()
            for poi in poi_response.pois:
                if poi.tags.amenity:
                    amenities.add(poi.tags.amenity)
            poi_diversity = len(amenities)
            
            # Essential amenities
            essential_amenities = {"restaurant", "cafe", "shop", "supermarket", "fuel", "bank", "pharmacy"}
            essential_count = sum(1 for poi in poi_response.pois 
                                if poi.tags.amenity in essential_amenities)
            essential_ratio = essential_count / total_pois if total_pois > 0 else 0
            
            return {
                "total_pois": total_pois,
                "poi_diversity": poi_diversity,
                "essential_amenity_ratio": essential_ratio
            }
        except Exception as e:
            logger.warning(f"POI features collection failed: {e}")
            return {
                "total_pois": 0,
                "poi_diversity": 0,
                "essential_amenity_ratio": 0
            }
    
    async def _calculate_safety_score(self, features: Dict[str, Any]) -> float:
        """Calculate safety score using XGBoost or deterministic method"""
        if self.safety_model and XGBOOST_AVAILABLE:
            try:
                # Prepare features for XGBoost model using feature names from trained model
                if self.safety_feature_names:
                    # Use feature names from trained model
                    feature_vector = np.array([
                        features.get(name, 0.0) for name in self.safety_feature_names
                    ]).reshape(1, -1)
                else:
                    # Fallback to default feature order
                    feature_vector = np.array([
                        features.get("crime_count", 0),
                        features.get("crime_density", 0),
                        features.get("violent_crime_ratio", 0),
                        features.get("crime_category_diversity", 0),
                        features.get("recent_crime_ratio", 0),
                        features.get("poi_count", 0),
                        features.get("poi_density", 0),
                        features.get("essential_amenities_ratio", 0),
                        features.get("news_count", 0),
                        features.get("news_sentiment_avg", 0),
                        features.get("news_sentiment_positive_ratio", 0)
                    ]).reshape(1, -1)
                
                score = self.safety_model.predict(feature_vector)[0]
                # Convert numpy types to native Python float for JSON serialization
                score = float(score)
                return max(0.0, min(1.0, score))  # Clamp between 0 and 1
            except Exception as e:
                logger.warning(f"XGBoost safety scoring failed: {e}")
        
        # Deterministic fallback
        return self._deterministic_safety_score(features)
    
    async def _calculate_popularity_score(self, features: Dict[str, Any]) -> float:
        """Calculate popularity score using XGBoost or deterministic method"""
        if self.popularity_model and XGBOOST_AVAILABLE:
            try:
                # Prepare features for XGBoost model using feature names from trained model
                if self.popularity_feature_names:
                    # Use feature names from trained model
                    feature_vector = np.array([
                        features.get(name, 0.0) for name in self.popularity_feature_names
                    ]).reshape(1, -1)
                else:
                    # Fallback to default feature order
                    feature_vector = np.array([
                        features.get("event_count", 0),
                        features.get("free_event_ratio", 0),
                        features.get("event_diversity", 0),
                        features.get("event_frequency", 0),
                        features.get("poi_count", 0),
                        features.get("poi_density", 0),
                        features.get("poi_diversity", 0),
                        features.get("amenity_type_count", 0),
                        features.get("news_count", 0),
                        features.get("news_coverage_frequency", 0),
                        features.get("news_source_diversity", 0)
                    ]).reshape(1, -1)
                
                score = self.popularity_model.predict(feature_vector)[0]
                # Convert numpy types to native Python float for JSON serialization
                score = float(score)
                return max(0.0, min(1.0, score))  # Clamp between 0 and 1
            except Exception as e:
                logger.warning(f"XGBoost popularity scoring failed: {e}")
        
        # Deterministic fallback
        return self._deterministic_popularity_score(features)
    
    def _deterministic_safety_score(self, features: Dict[str, Any]) -> float:
        """Deterministic safety scoring algorithm"""
        # Base score
        score = 0.5
        
        # Crime factors
        crime_density = features.get("crime_density", 0)
        violent_ratio = features.get("violent_crime_ratio", 0)
        recent_ratio = features.get("recent_crime_ratio", 0)
        
        # Reduce score based on crime factors
        score -= min(0.3, crime_density * 0.1)  # Max 0.3 reduction
        score -= min(0.2, violent_ratio * 0.2)   # Max 0.2 reduction
        score -= min(0.1, recent_ratio * 0.1)   # Max 0.1 reduction
        
        # POI factors (positive impact)
        essential_ratio = features.get("essential_amenity_ratio", 0)
        score += min(0.2, essential_ratio * 0.2)  # Max 0.2 increase
        
        # News sentiment (positive impact)
        avg_sentiment = features.get("avg_sentiment", 0)
        score += min(0.1, max(0, avg_sentiment) * 0.1)  # Max 0.1 increase
        
        return max(0.0, min(1.0, score))
    
    def _deterministic_popularity_score(self, features: Dict[str, Any]) -> float:
        """Deterministic popularity scoring algorithm"""
        # Base score
        score = 0.3
        
        # Event factors
        total_events = features.get("total_events", 0)
        event_diversity = features.get("event_diversity", 0)
        free_ratio = features.get("free_event_ratio", 0)
        
        score += min(0.3, total_events * 0.01)      # Max 0.3 increase
        score += min(0.2, event_diversity * 0.05)  # Max 0.2 increase
        score += min(0.1, free_ratio * 0.1)         # Max 0.1 increase
        
        # POI factors
        total_pois = features.get("total_pois", 0)
        poi_diversity = features.get("poi_diversity", 0)
        essential_ratio = features.get("essential_amenity_ratio", 0)
        
        score += min(0.2, total_pois * 0.005)      # Max 0.2 increase
        score += min(0.1, poi_diversity * 0.02)   # Max 0.1 increase
        score += min(0.1, essential_ratio * 0.1)  # Max 0.1 increase
        
        # News factors
        news_frequency = features.get("news_frequency", 0)
        score += min(0.1, news_frequency * 0.1)    # Max 0.1 increase
        
        return max(0.0, min(1.0, score))
    
    def _is_recent_crime(self, crime_date: str, months: int = 3) -> bool:
        """Check if crime is within recent months"""
        try:
            # Parse crime date (format: "2023-12")
            year, month = map(int, crime_date.split("-"))
            crime_datetime = datetime(year, month, 1)
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=months * 30)
            
            return crime_datetime >= cutoff_date
        except Exception:
            return False


# Service instance
scoring_service = ScoringService()






