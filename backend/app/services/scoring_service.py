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

        # Add temporal features (time-based patterns)
        temporal_features = self._collect_temporal_features()
        features.update(temporal_features)

        # Add spatial features (location context)
        spatial_features = self._collect_spatial_features(float(lat), float(lon))
        features.update(spatial_features)

        return features

    def _collect_temporal_features(self) -> Dict[str, Any]:
        """
        Collect temporal features based on current time.

        These features capture time-based patterns:
        - Safety varies by time of day (night vs day)
        - Popularity varies by day of week (weekend vs weekday)
        - Seasonal patterns affect both scores
        """
        now = datetime.now()

        # Hour of day (0-23)
        hour = now.hour

        # Day of week (0=Monday, 6=Sunday)
        day_of_week = now.weekday()

        # Binary features
        is_weekend = 1 if day_of_week >= 5 else 0
        is_night = 1 if hour < 6 or hour >= 22 else 0
        is_evening = 1 if 18 <= hour < 22 else 0
        is_morning_rush = 1 if 7 <= hour <= 9 else 0
        is_evening_rush = 1 if 17 <= hour <= 19 else 0

        # Time period encoding (cyclical)
        # Using sin/cos for cyclical time features
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)
        day_sin = math.sin(2 * math.pi * day_of_week / 7)
        day_cos = math.cos(2 * math.pi * day_of_week / 7)

        # Month for seasonal patterns
        month = now.month
        month_sin = math.sin(2 * math.pi * month / 12)
        month_cos = math.cos(2 * math.pi * month / 12)

        return {
            "hour_of_day": hour,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_night": is_night,
            "is_evening": is_evening,
            "is_morning_rush": is_morning_rush,
            "is_evening_rush": is_evening_rush,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "day_sin": day_sin,
            "day_cos": day_cos,
            "month_sin": month_sin,
            "month_cos": month_cos
        }

    def _collect_spatial_features(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Collect spatial features based on location.

        These features capture location context:
        - Distance to major city centers
        - Urban vs rural indicators
        - Geographic region characteristics
        """
        # Major UK city centers (lat, lon)
        uk_cities = {
            "london": (51.5074, -0.1278),
            "manchester": (53.4808, -2.2426),
            "birmingham": (52.4862, -1.8904),
            "leeds": (53.8008, -1.5491),
            "glasgow": (55.8642, -4.2518),
            "liverpool": (53.4084, -2.9916),
            "edinburgh": (55.9533, -3.1883),
            "bristol": (51.4545, -2.5879),
            "cardiff": (51.4816, -3.1791),
            "newcastle": (54.9783, -1.6178)
        }

        # Calculate distance to nearest major city
        min_distance = float('inf')
        nearest_city = None

        for city, (city_lat, city_lon) in uk_cities.items():
            distance = self._haversine_distance(lat, lon, city_lat, city_lon)
            if distance < min_distance:
                min_distance = distance
                nearest_city = city

        # Distance to London (capital city effect)
        london_distance = self._haversine_distance(lat, lon, 51.5074, -0.1278)

        # Urban indicator (closer to city = more urban)
        # Using sigmoid-like function: 1 for city center, 0 for rural
        urban_score = 1 / (1 + min_distance / 10)  # 10km half-life

        # Regional indicators based on latitude/longitude
        is_north = 1 if lat > 53.5 else 0  # North of Manchester
        is_scotland = 1 if lat > 55.0 else 0
        is_wales = 1 if lon < -2.5 and lat < 53.0 and lat > 51.3 else 0
        is_london_area = 1 if london_distance < 50 else 0  # Within 50km of London

        # Latitude and longitude as features (normalized)
        # UK roughly spans 50-60 lat, -8 to 2 lon
        lat_normalized = (lat - 50) / 10  # 0-1 range
        lon_normalized = (lon + 8) / 10   # 0-1 range

        return {
            "distance_to_nearest_city_km": round(min_distance, 2),
            "distance_to_london_km": round(london_distance, 2),
            "urban_score": round(urban_score, 4),
            "is_north": is_north,
            "is_scotland": is_scotland,
            "is_wales": is_wales,
            "is_london_area": is_london_area,
            "lat_normalized": round(lat_normalized, 4),
            "lon_normalized": round(lon_normalized, 4),
            "nearest_major_city": nearest_city
        }

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great-circle distance between two points on Earth.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in kilometers

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

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
        """Deterministic safety scoring algorithm with temporal and spatial features"""
        # Base score
        score = 0.5

        # Crime factors (negative impact)
        crime_density = features.get("crime_density", 0)
        violent_ratio = features.get("violent_crime_ratio", 0)
        recent_ratio = features.get("recent_crime_ratio", 0)

        score -= min(0.3, crime_density * 0.1)   # Max 0.3 reduction
        score -= min(0.2, violent_ratio * 0.2)   # Max 0.2 reduction
        score -= min(0.1, recent_ratio * 0.1)    # Max 0.1 reduction

        # POI factors (positive impact)
        essential_ratio = features.get("essential_amenity_ratio", 0)
        score += min(0.2, essential_ratio * 0.2)  # Max 0.2 increase

        # News sentiment (positive impact)
        avg_sentiment = features.get("avg_sentiment", 0)
        score += min(0.1, max(0, avg_sentiment) * 0.1)  # Max 0.1 increase

        # Temporal adjustments
        is_night = features.get("is_night", 0)
        is_weekend = features.get("is_weekend", 0)

        # Safety typically lower at night
        if is_night:
            score -= 0.05  # Slight reduction at night

        # Weekend nights slightly less safe in entertainment areas
        if is_night and is_weekend:
            score -= 0.02

        # Spatial adjustments
        urban_score = features.get("urban_score", 0.5)
        is_london_area = features.get("is_london_area", 0)

        # Urban areas have more police presence but also more crime
        # Net effect is slightly negative for very urban areas
        if urban_score > 0.8:
            score -= 0.03

        # London area adjustment (mixed effect)
        if is_london_area:
            score -= 0.02  # Slightly lower due to higher crime rates

        return max(0.0, min(1.0, score))

    def _deterministic_popularity_score(self, features: Dict[str, Any]) -> float:
        """Deterministic popularity scoring algorithm with temporal and spatial features"""
        # Base score
        score = 0.3

        # Event factors
        total_events = features.get("total_events", 0)
        event_diversity = features.get("event_diversity", 0)
        free_ratio = features.get("free_event_ratio", 0)

        score += min(0.3, total_events * 0.01)     # Max 0.3 increase
        score += min(0.2, event_diversity * 0.05)  # Max 0.2 increase
        score += min(0.1, free_ratio * 0.1)        # Max 0.1 increase

        # POI factors
        total_pois = features.get("total_pois", 0)
        poi_diversity = features.get("poi_diversity", 0)
        essential_ratio = features.get("essential_amenity_ratio", 0)

        score += min(0.2, total_pois * 0.005)     # Max 0.2 increase
        score += min(0.1, poi_diversity * 0.02)   # Max 0.1 increase
        score += min(0.1, essential_ratio * 0.1)  # Max 0.1 increase

        # News factors
        news_frequency = features.get("news_frequency", 0)
        score += min(0.1, news_frequency * 0.1)   # Max 0.1 increase

        # Temporal adjustments
        is_weekend = features.get("is_weekend", 0)
        is_evening = features.get("is_evening", 0)
        is_night = features.get("is_night", 0)

        # Weekends are more popular for leisure
        if is_weekend:
            score += 0.05

        # Evening hours are popular for entertainment
        if is_evening:
            score += 0.03

        # Late night has reduced popularity (most venues closed)
        if is_night:
            score -= 0.05

        # Spatial adjustments
        urban_score = features.get("urban_score", 0.5)
        is_london_area = features.get("is_london_area", 0)
        distance_to_city = features.get("distance_to_nearest_city_km", 50)

        # Urban areas are generally more popular
        score += min(0.1, urban_score * 0.1)

        # London area bonus (tourist destination, more attractions)
        if is_london_area:
            score += 0.05

        # Closer to city centers = more popular
        if distance_to_city < 5:
            score += 0.05
        elif distance_to_city < 15:
            score += 0.02

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
