"""
Feature calculation for ML models — crime, POI, news, and event features.
"""

import logging
import json
import math
from typing import Dict, Any, List, Optional
from decimal import Decimal
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler

logger = logging.getLogger(__name__)


class FeatureCalculator:
    """Calculates and normalizes features from cleaned location data for ML models."""

    # Essential amenities for safety scoring
    ESSENTIAL_AMENITIES = {
        'hospital', 'pharmacy', 'police', 'fire_station',
        'school', 'university', 'library', 'post_office',
        'bank', 'atm', 'supermarket', 'fuel'
    }

    # Violent crime categories
    VIOLENT_CRIMES = {
        'violent-crime', 'robbery', 'assault', 'weapons',
        'homicide', 'murder', 'manslaughter'
    }

    def __init__(self):
        self.scaler = StandardScaler()
        self.min_max_scaler = MinMaxScaler()

    def calculate_crime_features(
        self,
        crime_data: pd.DataFrame,
        radius_km: float = 5.0
    ) -> Dict[str, float]:
        if crime_data.empty:
            return {
                'crime_count': 0,
                'crime_density': 0.0,
                'violent_crime_ratio': 0.0,
                'crime_category_diversity': 0.0,
                'recent_crime_ratio': 0.0
            }

        area_km2 = math.pi * (radius_km ** 2)
        crime_count = len(crime_data)
        crime_density = crime_count / area_km2 if area_km2 > 0 else 0.0

        violent_crimes = crime_data[
            crime_data['category'].str.lower().isin([c.lower() for c in self.VIOLENT_CRIMES])
        ]
        violent_crime_ratio = len(violent_crimes) / crime_count if crime_count > 0 else 0.0

        # Shannon diversity index for crime categories
        category_counts = crime_data['category'].value_counts()
        if len(category_counts) > 0:
            proportions = category_counts / crime_count
            crime_category_diversity = -sum(proportions * np.log(proportions + 1e-10))
        else:
            crime_category_diversity = 0.0

        if 'month' in crime_data.columns:
            from datetime import datetime
            current_month = datetime.now().strftime('%Y-%m')
            recent_crimes = len(crime_data)  # simplified
            recent_crime_ratio = recent_crimes / crime_count if crime_count > 0 else 0.0
        else:
            recent_crime_ratio = 0.0

        return {
            'crime_count': int(crime_count),
            'crime_density': float(crime_density),
            'violent_crime_ratio': float(violent_crime_ratio),
            'crime_category_diversity': float(crime_category_diversity),
            'recent_crime_ratio': float(recent_crime_ratio)
        }

    def calculate_poi_features(
        self,
        poi_data: pd.DataFrame,
        radius_km: float = 5.0
    ) -> Dict[str, float]:
        if poi_data.empty:
            return {
                'poi_count': 0,
                'poi_density': 0.0,
                'poi_diversity': 0.0,
                'essential_amenities_ratio': 0.0,
                'amenity_type_count': 0
            }

        area_km2 = math.pi * (radius_km ** 2)
        poi_count = len(poi_data)
        poi_density = poi_count / area_km2 if area_km2 > 0 else 0.0

        if 'amenity' in poi_data.columns:
            amenity_counts = poi_data['amenity'].value_counts()
            if len(amenity_counts) > 0:
                proportions = amenity_counts / poi_count
                poi_diversity = -sum(proportions * np.log(proportions + 1e-10))
            else:
                poi_diversity = 0.0
            amenity_type_count = len(amenity_counts)
        else:
            poi_diversity = 0.0
            amenity_type_count = 0

        if 'amenity' in poi_data.columns:
            essential_count = poi_data[
                poi_data['amenity'].str.lower().isin([a.lower() for a in self.ESSENTIAL_AMENITIES])
            ].shape[0]
            essential_amenities_ratio = essential_count / poi_count if poi_count > 0 else 0.0
        else:
            essential_amenities_ratio = 0.0

        return {
            'poi_count': int(poi_count),
            'poi_density': float(poi_density),
            'poi_diversity': float(poi_diversity),
            'essential_amenities_ratio': float(essential_amenities_ratio),
            'amenity_type_count': int(amenity_type_count)
        }

    def calculate_news_features(
        self,
        news_data: pd.DataFrame
    ) -> Dict[str, float]:
        if news_data.empty:
            return {
                'news_count': 0,
                'news_coverage_frequency': 0.0,
                'news_sentiment_avg': 0.0,
                'news_sentiment_positive_ratio': 0.0,
                'news_source_diversity': 0.0
            }

        news_count = len(news_data)
        news_coverage_frequency = news_count / 30.0  # articles per day over 30-day window

        if 'sentiment_score' in news_data.columns:
            sentiments = news_data['sentiment_score'].dropna()
            if len(sentiments) > 0:
                news_sentiment_avg = float(sentiments.mean())
                positive_count = (sentiments > 0.1).sum()
                news_sentiment_positive_ratio = positive_count / len(sentiments)
            else:
                news_sentiment_avg = 0.0
                news_sentiment_positive_ratio = 0.0
        else:
            news_sentiment_avg = 0.0
            news_sentiment_positive_ratio = 0.0

        if 'source_name' in news_data.columns:
            source_counts = news_data['source_name'].value_counts()
            if len(source_counts) > 0:
                proportions = source_counts / news_count
                news_source_diversity = -sum(proportions * np.log(proportions + 1e-10))
            else:
                news_source_diversity = 0.0
        else:
            news_source_diversity = 0.0

        return {
            'news_count': int(news_count),
            'news_coverage_frequency': float(news_coverage_frequency),
            'news_sentiment_avg': float(news_sentiment_avg),
            'news_sentiment_positive_ratio': float(news_sentiment_positive_ratio),
            'news_source_diversity': float(news_source_diversity)
        }

    def calculate_event_features(
        self,
        event_data: pd.DataFrame
    ) -> Dict[str, float]:
        if event_data.empty:
            return {
                'event_count': 0,
                'free_event_ratio': 0.0,
                'event_diversity': 0.0,
                'event_frequency': 0.0
            }

        event_count = len(event_data)

        if 'is_free' in event_data.columns:
            free_count = event_data['is_free'].sum()
            free_event_ratio = free_count / event_count if event_count > 0 else 0.0
        else:
            free_event_ratio = 0.0

        if 'category' in event_data.columns:
            category_counts = event_data['category'].value_counts()
            event_diversity = len(category_counts)
        else:
            event_diversity = 0.0

        event_frequency = event_count / 30.0  # events per day over 30-day window

        return {
            'event_count': int(event_count),
            'free_event_ratio': float(free_event_ratio),
            'event_diversity': int(event_diversity),
            'event_frequency': float(event_frequency)
        }

    def combine_features(
        self,
        crime_features: Dict[str, float],
        poi_features: Dict[str, float],
        news_features: Dict[str, float],
        event_features: Dict[str, float]
    ) -> Dict[str, float]:
        combined = {}
        combined.update(crime_features)
        combined.update(poi_features)
        combined.update(news_features)
        combined.update(event_features)
        return combined

    def normalize_features(
        self,
        features: Dict[str, float],
        feature_ranges: Optional[Dict[str, tuple]] = None
    ) -> Dict[str, float]:
        """Min-max normalize features to 0-1. Uses default ranges if none provided."""
        normalized = {}

        if feature_ranges is None:
            feature_ranges = {
                'crime_density': (0, 10),
                'violent_crime_ratio': (0, 1),
                'poi_density': (0, 100),
                'poi_diversity': (0, 5),
                'news_sentiment_avg': (-1, 1),
                'news_coverage_frequency': (0, 10),
            }

        for key, value in features.items():
            if key in feature_ranges:
                min_val, max_val = feature_ranges[key]
                if max_val > min_val:
                    normalized[key] = max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
                else:
                    normalized[key] = 0.0
            else:
                normalized[key] = float(value) if isinstance(value, (int, float)) else 0.0

        return normalized

    def get_feature_names(self, model_type: str = "safety") -> List[str]:
        if model_type == "safety":
            return [
                'crime_count',
                'crime_density',
                'violent_crime_ratio',
                'crime_category_diversity',
                'recent_crime_ratio',
                'poi_count',
                'poi_density',
                'essential_amenities_ratio',
                'news_count',
                'news_sentiment_avg',
                'news_sentiment_positive_ratio'
            ]
        elif model_type == "popularity":
            return [
                'event_count',
                'free_event_ratio',
                'event_diversity',
                'event_frequency',
                'poi_count',
                'poi_density',
                'poi_diversity',
                'amenity_type_count',
                'news_count',
                'news_coverage_frequency',
                'news_source_diversity'
            ]
        else:
            return [
                'crime_count', 'crime_density', 'violent_crime_ratio',
                'crime_category_diversity', 'recent_crime_ratio',
                'poi_count', 'poi_density', 'poi_diversity',
                'essential_amenities_ratio', 'amenity_type_count',
                'news_count', 'news_coverage_frequency', 'news_source_diversity',
                'event_count', 'free_event_ratio', 'event_diversity', 'event_frequency'
            ]


feature_calculator = FeatureCalculator()
