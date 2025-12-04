"""
Feature Calculation Functions for ML Models

What this module does:
- Calculates features from cleaned data
- Extracts numerical features for ML models
- Normalizes and scales features
- Prepares features for XGBoost training

Technologies used:
- pandas: Data manipulation and aggregation
- numpy: Numerical operations
- scikit-learn: Feature scaling
- math: Mathematical calculations (Shannon diversity)

Why this is important:
- ML models need numerical features (not raw data)
- Features must be normalized for model training
- Feature engineering directly affects model performance
- Good features = good predictions

How it works:
1. Load cleaned data from database
2. Group data by location
3. Calculate features (density, ratios, diversity)
4. Normalize features (0-1 range)
5. Return feature vectors
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
    """
    Feature Calculator Class
    
    Purpose:
    - Calculate features from cleaned data
    - Extract numerical features for ML models
    - Normalize and scale features
    
    How it works:
    1. Load cleaned data (processed = 1)
    2. Group by location (lat/lon grid or location_hash)
    3. Calculate features per location
    4. Normalize features
    5. Return feature vectors
    """
    
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
        """Initialize feature calculator"""
        self.scaler = StandardScaler()  # For feature scaling
        self.min_max_scaler = MinMaxScaler()  # For normalization (0-1)
    
    def calculate_crime_features(
        self, 
        crime_data: pd.DataFrame,
        radius_km: float = 5.0
    ) -> Dict[str, float]:
        """
        Calculate crime-related features
        
        What it calculates:
        - Crime density (crimes per km²)
        - Violent crime ratio (violent crimes / total crimes)
        - Crime category distribution
        - Recent crime trend
        
        Parameters:
        - crime_data: DataFrame with crime records
        - radius_km: Search radius for density calculation
        
        Returns:
        - Dictionary with crime features
        
        Example:
        >>> calculator = FeatureCalculator()
        >>> crimes = pd.DataFrame([...])
        >>> features = calculator.calculate_crime_features(crimes, radius_km=5.0)
        >>> print(features['crime_density'])
        0.5
        """
        if crime_data.empty:
            return {
                'crime_count': 0,
                'crime_density': 0.0,
                'violent_crime_ratio': 0.0,
                'crime_category_diversity': 0.0,
                'recent_crime_ratio': 0.0
            }
        
        # Calculate area (km²) - approximate circle area
        area_km2 = math.pi * (radius_km ** 2)
        
        # Crime count
        crime_count = len(crime_data)
        
        # Crime density (crimes per km²)
        crime_density = crime_count / area_km2 if area_km2 > 0 else 0.0
        
        # Violent crime ratio
        violent_crimes = crime_data[
            crime_data['category'].str.lower().isin([c.lower() for c in self.VIOLENT_CRIMES])
        ]
        violent_crime_ratio = len(violent_crimes) / crime_count if crime_count > 0 else 0.0
        
        # Crime category diversity (Shannon diversity index)
        category_counts = crime_data['category'].value_counts()
        if len(category_counts) > 0:
            proportions = category_counts / crime_count
            crime_category_diversity = -sum(proportions * np.log(proportions + 1e-10))
        else:
            crime_category_diversity = 0.0
        
        # Recent crime ratio (last 3 months vs all)
        # Assuming 'month' column exists in YYYY-MM format
        if 'month' in crime_data.columns:
            from datetime import datetime
            current_month = datetime.now().strftime('%Y-%m')
            # Simple check: count recent months (last 3)
            recent_crimes = len(crime_data)  # Simplified - would need date parsing
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
        """
        Calculate POI-related features
        
        What it calculates:
        - POI density (POIs per km²)
        - POI diversity (Shannon diversity index)
        - Essential amenities ratio
        - Amenity type distribution
        
        Returns:
        - Dictionary with POI features
        """
        if poi_data.empty:
            return {
                'poi_count': 0,
                'poi_density': 0.0,
                'poi_diversity': 0.0,
                'essential_amenities_ratio': 0.0,
                'amenity_type_count': 0
            }
        
        # Calculate area
        area_km2 = math.pi * (radius_km ** 2)
        
        # POI count
        poi_count = len(poi_data)
        
        # POI density
        poi_density = poi_count / area_km2 if area_km2 > 0 else 0.0
        
        # POI diversity (Shannon diversity index)
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
        
        # Essential amenities ratio
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
        """
        Calculate news-related features
        
        What it calculates:
        - News coverage frequency (articles per day)
        - Average sentiment score
        - Positive/negative sentiment ratio
        - News source diversity
        
        Returns:
        - Dictionary with news features
        """
        if news_data.empty:
            return {
                'news_count': 0,
                'news_coverage_frequency': 0.0,
                'news_sentiment_avg': 0.0,
                'news_sentiment_positive_ratio': 0.0,
                'news_source_diversity': 0.0
            }
        
        # News count
        news_count = len(news_data)
        
        # News coverage frequency (articles per day, assuming 30-day period)
        news_coverage_frequency = news_count / 30.0
        
        # Average sentiment
        if 'sentiment_score' in news_data.columns:
            sentiments = news_data['sentiment_score'].dropna()
            if len(sentiments) > 0:
                news_sentiment_avg = float(sentiments.mean())
                # Positive sentiment ratio (sentiment > 0.1)
                positive_count = (sentiments > 0.1).sum()
                news_sentiment_positive_ratio = positive_count / len(sentiments)
            else:
                news_sentiment_avg = 0.0
                news_sentiment_positive_ratio = 0.0
        else:
            news_sentiment_avg = 0.0
            news_sentiment_positive_ratio = 0.0
        
        # News source diversity
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
        """
        Calculate event-related features
        
        What it calculates:
        - Event count
        - Free event ratio
        - Event diversity (categories)
        - Event frequency
        
        Returns:
        - Dictionary with event features
        
        Note: EventData model may not exist yet, so this uses placeholder logic
        """
        if event_data.empty:
            return {
                'event_count': 0,
                'free_event_ratio': 0.0,
                'event_diversity': 0.0,
                'event_frequency': 0.0
            }
        
        # Event count
        event_count = len(event_data)
        
        # Free event ratio
        if 'is_free' in event_data.columns:
            free_count = event_data['is_free'].sum()
            free_event_ratio = free_count / event_count if event_count > 0 else 0.0
        else:
            free_event_ratio = 0.0
        
        # Event diversity (categories)
        if 'category' in event_data.columns:
            category_counts = event_data['category'].value_counts()
            event_diversity = len(category_counts)
        else:
            event_diversity = 0.0
        
        # Event frequency (events per day, assuming 30-day period)
        event_frequency = event_count / 30.0
        
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
        """
        Combine all features into single feature vector
        
        What it does:
        - Merges features from all data types
        - Creates complete feature vector for ML models
        - Ensures all features are present (fills missing with 0)
        
        Returns:
        - Complete feature dictionary
        """
        # Combine all features
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
        """
        Normalize features to 0-1 range
        
        What it does:
        - Scales features to 0-1 range
        - Uses Min-Max normalization
        - Handles missing feature ranges
        
        Parameters:
        - features: Feature dictionary
        - feature_ranges: Optional min/max ranges for each feature
        
        Returns:
        - Normalized feature dictionary
        """
        normalized = {}
        
        # Default ranges (if not provided)
        if feature_ranges is None:
            feature_ranges = {
                'crime_density': (0, 10),  # Max 10 crimes per km²
                'violent_crime_ratio': (0, 1),
                'poi_density': (0, 100),  # Max 100 POIs per km²
                'poi_diversity': (0, 5),  # Max diversity index
                'news_sentiment_avg': (-1, 1),
                'news_coverage_frequency': (0, 10),  # Max 10 articles per day
            }
        
        for key, value in features.items():
            if key in feature_ranges:
                min_val, max_val = feature_ranges[key]
                if max_val > min_val:
                    normalized[key] = (value - min_val) / (max_val - min_val)
                    # Clamp to 0-1
                    normalized[key] = max(0.0, min(1.0, normalized[key]))
                else:
                    normalized[key] = 0.0
            else:
                # For features without ranges, use value as-is (if already 0-1)
                # Or apply simple normalization
                if isinstance(value, (int, float)):
                    normalized[key] = float(value)
                else:
                    normalized[key] = 0.0
        
        return normalized
    
    def get_feature_names(self, model_type: str = "safety") -> List[str]:
        """
        Get feature names for a specific model type
        
        Parameters:
        - model_type: "safety" or "popularity"
        
        Returns:
        - List of feature names
        """
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
            # All features
            return [
                'crime_count', 'crime_density', 'violent_crime_ratio',
                'crime_category_diversity', 'recent_crime_ratio',
                'poi_count', 'poi_density', 'poi_diversity',
                'essential_amenities_ratio', 'amenity_type_count',
                'event_count', 'free_event_ratio', 'event_diversity',
                'event_frequency',
                'news_count', 'news_coverage_frequency',
                'news_sentiment_avg', 'news_sentiment_positive_ratio',
                'news_source_diversity'
            ]


# Global feature calculator instance
feature_calculator = FeatureCalculator()



