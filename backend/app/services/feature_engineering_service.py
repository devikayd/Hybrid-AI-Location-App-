"""
Feature Engineering Service

What this service does:
- Extracts features from cleaned data
- Calculates numerical features for ML models
- Normalizes and scales features
- Stores features in training_data table
- Prepares data for XGBoost model training

Technologies used:
- pandas: Data manipulation and aggregation
- numpy: Numerical operations
- scikit-learn: Feature scaling
- SQLAlchemy: Database operations
- Feature calculator: Feature calculation functions

Why this is important:
- ML models need numerical features (not raw data)
- Feature engineering is critical for model performance
- Good features = good predictions
- Enables model training

How it works:
1. Load cleaned data from database (processed = 1)
2. Group data by location (lat/lon grid)
3. Calculate features per location
4. Normalize features (0-1 range)
5. Store in training_data table
"""

import logging
import json
import math
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.core.database import get_db
from app.models import CrimeData, NewsData, POIData, TrainingData
from app.ml.features import feature_calculator
from app.services.geocode_service import geocode_service

logger = logging.getLogger(__name__)


class FeatureEngineeringService:
    """
    Feature Engineering Service
    
    Purpose:
    - Extract features from cleaned data
    - Create training datasets for ML models
    - Store features in training_data table
    
    How it works:
    1. Load cleaned data (processed = 1)
    2. Group by location (spatial grid)
    3. Calculate features per location
    4. Normalize features
    5. Store in database
    """
    
    def __init__(self):
        """Initialize feature engineering service"""
        self.stats = {
            'locations_processed': 0,
            'features_extracted': 0,
            'training_records_created': 0,
            'errors': 0
        }
        self.feature_version = "v1.0"  # Feature engineering version
    
    async def extract_features_for_location(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: float = 5.0,
        location_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract features for a specific location
        
        What it does:
        1. Load cleaned data within radius
        2. Calculate features (crime, POI, news, events)
        3. Normalize features
        4. Store in training_data table
        
        Parameters:
        - lat, lon: Location coordinates
        - radius_km: Search radius
        - location_name: Optional location name
        
        Returns:
        - Dictionary with extracted features and metadata
        
        Example:
        >>> service = FeatureEngineeringService()
        >>> result = await service.extract_features_for_location(
        ...     lat=Decimal("51.5074"),
        ...     lon=Decimal("-0.1278"),
        ...     radius_km=5.0
        ... )
        >>> print(result['features']['crime_density'])
        0.5
        """
        db = None
        try:
            logger.info(f"Extracting features for location: {lat}, {lon}")
            
            # Get database session
            db = next(get_db())
            
            # Step 1: Load cleaned data within radius
            crime_data = self._load_crime_data(db, lat, lon, radius_km)
            poi_data = self._load_poi_data(db, lat, lon, radius_km)
            news_data = self._load_news_data(db, lat, lon, radius_km)
            event_data = self._load_event_data(db, lat, lon, radius_km)  # May be empty if model doesn't exist
            
            # Step 2: Calculate features
            crime_features = feature_calculator.calculate_crime_features(
                crime_data, radius_km
            )
            poi_features = feature_calculator.calculate_poi_features(
                poi_data, radius_km
            )
            news_features = feature_calculator.calculate_news_features(
                news_data
            )
            event_features = feature_calculator.calculate_event_features(
                event_data
            )
            
            # Step 3: Combine features
            combined_features = feature_calculator.combine_features(
                crime_features,
                poi_features,
                news_features,
                event_features
            )
            
            # Step 4: Normalize features
            normalized_features = feature_calculator.normalize_features(
                combined_features
            )
            
            # Step 5: Get location name if not provided
            if not location_name:
                try:
                    # Add timeout to geocoding to prevent hanging
                    import asyncio
                    geocode_result = await asyncio.wait_for(
                        geocode_service.reverse_geocode(lat, lon),
                        timeout=5.0  # 5 second timeout
                    )
                    location_name = geocode_result.display_name if geocode_result else None
                except (Exception, asyncio.TimeoutError):
                    location_name = f"{lat}, {lon}"
            
            # Step 6: Calculate data quality score
            data_quality_score = self._calculate_data_quality_score(
                crime_data, poi_data, news_data, event_data
            )
            
            # Step 7: Check for missing features
            missing_features = self._check_missing_features(normalized_features)
            
            # Step 8: Store in training_data table (for both safety and popularity models)
            training_records = []
            
            # Safety model features
            safety_features = self._select_features_for_model(
                normalized_features, "safety"
            )
            safety_record = self._create_training_record(
                db, lat, lon, location_name, "safety", safety_features,
                data_quality_score, missing_features
            )
            if safety_record:
                training_records.append(safety_record)
            
            # Popularity model features
            popularity_features = self._select_features_for_model(
                normalized_features, "popularity"
            )
            popularity_record = self._create_training_record(
                db, lat, lon, location_name, "popularity", popularity_features,
                data_quality_score, missing_features
            )
            if popularity_record:
                training_records.append(popularity_record)
            
            if db:
                db.close()
            
            # Update statistics
            self.stats['locations_processed'] += 1
            self.stats['features_extracted'] += len(normalized_features)
            self.stats['training_records_created'] += len(training_records)
            
            return {
                'location': {
                    'lat': float(lat),
                    'lon': float(lon),
                    'name': location_name
                },
                'features': normalized_features,
                'safety_features': safety_features,
                'popularity_features': popularity_features,
                'data_quality_score': data_quality_score,
                'missing_features': missing_features,
                'training_records_created': len(training_records)
            }
            
        except Exception as e:
            logger.error(f"Feature extraction failed for {lat}, {lon}: {e}", exc_info=True)
            self.stats['errors'] += 1
            if db:
                try:
                    db.rollback()
                    db.close()
                except:
                    pass
            raise
    
    async def extract_features_batch(
        self,
        locations: List[Tuple[Decimal, Decimal]],
        radius_km: float = 5.0,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract features for multiple locations
        
        What it does:
        - Processes multiple locations
        - Extracts features for each
        - Stores in training_data table
        
        Parameters:
        - locations: List of (lat, lon) tuples
        - radius_km: Search radius
        - limit: Maximum locations to process
        
        Returns:
        - Dictionary with batch processing statistics
        """
        try:
            logger.info(f"Starting batch feature extraction for {len(locations)} locations")
            
            if limit:
                locations = locations[:limit]
            
            results = []
            errors = []
            
            for lat, lon in locations:
                try:
                    result = await self.extract_features_for_location(
                        lat, lon, radius_km
                    )
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Feature extraction failed for {lat}, {lon}: {e}")
                    errors.append({'lat': float(lat), 'lon': float(lon), 'error': str(e)})
            
            return {
                'total_locations': len(locations),
                'successful': len(results),
                'failed': len(errors),
                'errors': errors[:10],  # First 10 errors
                'statistics': self.stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Batch feature extraction failed: {e}", exc_info=True)
            raise
    
    async def extract_features_from_database(
        self,
        grid_size_km: float = 1.0,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract features from all cleaned data in database
        
        What it does:
        1. Find all unique locations in cleaned data
        2. Group by spatial grid
        3. Extract features for each grid cell
        4. Store in training_data table
        
        Parameters:
        - grid_size_km: Size of spatial grid cells (km)
        - limit: Maximum locations to process
        
        Returns:
        - Dictionary with extraction statistics
        """
        db = None
        try:
            logger.info(f"Extracting features from database (grid_size={grid_size_km}km)")
            
            db = next(get_db())
            
            # Step 1: Find unique locations from cleaned data
            locations = self._find_unique_locations(db, grid_size_km)
            
            # Close the outer session before processing locations
            # (each location will create its own session)
            if db:
                db.close()
                db = None
            
            if limit:
                locations = locations[:limit]
            
            logger.info(f"Found {len(locations)} unique locations")
            
            # Step 2: Extract features for each location
            results = []
            errors = []
            
            for lat, lon in locations:
                try:
                    result = await self.extract_features_for_location(
                        Decimal(str(lat)),
                        Decimal(str(lon)),
                        radius_km=grid_size_km * 2  # Use 2x grid size as radius
                    )
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Feature extraction failed for {lat}, {lon}: {e}")
                    errors.append({'lat': lat, 'lon': lon, 'error': str(e)})
            
            return {
                'total_locations': len(locations),
                'successful': len(results),
                'failed': len(errors),
                'errors': errors[:10],
                'statistics': self.stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Database feature extraction failed: {e}", exc_info=True)
            if db:
                try:
                    db.close()
                except:
                    pass
            raise
    
    def _load_crime_data(
        self,
        db: Session,
        lat: Decimal,
        lon: Decimal,
        radius_km: float
    ) -> pd.DataFrame:
        """Load cleaned crime data within radius"""
        try:
            # Calculate bounding box (approximate)
            lat_deg = float(lat)
            lon_deg = float(lon)
            
            # Approximate: 1 degree ≈ 111 km
            lat_offset = radius_km / 111.0
            lon_offset = radius_km / (111.0 * abs(math.cos(math.radians(lat_deg))))
            
            # Query cleaned crime data
            crimes = db.query(CrimeData).filter(
                and_(
                    CrimeData.processed == 1,  # Only cleaned data
                    CrimeData.latitude >= lat_deg - lat_offset,
                    CrimeData.latitude <= lat_deg + lat_offset,
                    CrimeData.longitude >= lon_deg - lon_offset,
                    CrimeData.longitude <= lon_deg + lon_offset
                )
            ).all()
            
            # Convert to DataFrame
            data = []
            for crime in crimes:
                data.append({
                    'latitude': crime.latitude,
                    'longitude': crime.longitude,
                    'category': crime.category,
                    'crime_type': crime.crime_type,
                    'month': crime.month
                })
            
            return pd.DataFrame(data)
            
        except Exception as e:
            logger.warning(f"Failed to load crime data: {e}")
            return pd.DataFrame()
    
    def _load_poi_data(
        self,
        db: Session,
        lat: Decimal,
        lon: Decimal,
        radius_km: float
    ) -> pd.DataFrame:
        """Load cleaned POI data within radius"""
        try:
            lat_deg = float(lat)
            lon_deg = float(lon)
            
            lat_offset = radius_km / 111.0
            lon_offset = radius_km / (111.0 * abs(math.cos(math.radians(lat_deg))))
            
            pois = db.query(POIData).filter(
                and_(
                    POIData.processed == 1,  # Only cleaned data
                    POIData.latitude >= lat_deg - lat_offset,
                    POIData.latitude <= lat_deg + lat_offset,
                    POIData.longitude >= lon_deg - lon_offset,
                    POIData.longitude <= lon_deg + lon_offset
                )
            ).all()
            
            data = []
            for poi in pois:
                data.append({
                    'latitude': poi.latitude,
                    'longitude': poi.longitude,
                    'amenity': poi.amenity,
                    'category': poi.category,
                    'is_essential': poi.is_essential
                })
            
            return pd.DataFrame(data)
            
        except Exception as e:
            logger.warning(f"Failed to load POI data: {e}")
            return pd.DataFrame()
    
    def _load_news_data(
        self,
        db: Session,
        lat: Decimal,
        lon: Decimal,
        radius_km: float
    ) -> pd.DataFrame:
        """Load cleaned news data within radius"""
        try:
            lat_deg = float(lat)
            lon_deg = float(lon)
            
            lat_offset = radius_km / 111.0
            lon_offset = radius_km / (111.0 * abs(math.cos(math.radians(lat_deg))))
            
            news_items = db.query(NewsData).filter(
                and_(
                    NewsData.processed == 1,  # Only cleaned data
                    NewsData.latitude.isnot(None),
                    NewsData.latitude >= lat_deg - lat_offset,
                    NewsData.latitude <= lat_deg + lat_offset,
                    NewsData.longitude >= lon_deg - lon_offset,
                    NewsData.longitude <= lon_deg + lon_offset
                )
            ).all()
            
            data = []
            for news in news_items:
                data.append({
                    'latitude': news.latitude,
                    'longitude': news.longitude,
                    'sentiment_score': news.sentiment_score,
                    'source_name': news.source_name,
                    'published_at': news.published_at
                })
            
            return pd.DataFrame(data)
            
        except Exception as e:
            logger.warning(f"Failed to load news data: {e}")
            return pd.DataFrame()
    
    def _load_event_data(
        self,
        db: Session,
        lat: Decimal,
        lon: Decimal,
        radius_km: float
    ) -> pd.DataFrame:
        """Load cleaned event data within radius"""
        try:
            # Note: EventData model may not exist yet
            # This is a placeholder for when EventData is created
            from app.models import EventData
            
            lat_deg = float(lat)
            lon_deg = float(lon)
            
            lat_offset = radius_km / 111.0
            lon_offset = radius_km / (111.0 * abs(math.cos(math.radians(lat_deg))))
            
            events = db.query(EventData).filter(
                and_(
                    EventData.processed == 1,
                    EventData.latitude >= lat_deg - lat_offset,
                    EventData.latitude <= lat_deg + lat_offset,
                    EventData.longitude >= lon_deg - lon_offset,
                    EventData.longitude <= lon_deg + lon_offset
                )
            ).all()
            
            data = []
            for event in events:
                data.append({
                    'latitude': event.latitude,
                    'longitude': event.longitude,
                    'is_free': getattr(event, 'is_free', False),
                    'category': getattr(event, 'category', None)
                })
            
            return pd.DataFrame(data)
            
        except ImportError:
            # EventData model doesn't exist yet
            logger.debug("EventData model not available, skipping event features")
            return pd.DataFrame()
        except Exception as e:
            logger.warning(f"Failed to load event data: {e}")
            return pd.DataFrame()
    
    def _find_unique_locations(
        self,
        db: Session,
        grid_size_km: float
    ) -> List[Tuple[float, float]]:
        """
        Find unique locations from cleaned data
        
        What it does:
        - Groups data by spatial grid
        - Returns grid cell centers as locations
        
        Returns:
        - List of (lat, lon) tuples
        """
        locations = set()
        
        # Get unique locations from crime data
        crimes = db.query(
            func.round(CrimeData.latitude, 3).label('lat'),
            func.round(CrimeData.longitude, 3).label('lon')
        ).filter(
            CrimeData.processed == 1
        ).distinct().all()
        
        for row in crimes:
            locations.add((float(row.lat), float(row.lon)))
        
        # Get unique locations from POI data
        pois = db.query(
            func.round(POIData.latitude, 3).label('lat'),
            func.round(POIData.longitude, 3).label('lon')
        ).filter(
            POIData.processed == 1
        ).distinct().all()
        
        for row in pois:
            locations.add((float(row.lat), float(row.lon)))
        
        # Get unique locations from news data
        news_items = db.query(
            func.round(NewsData.latitude, 3).label('lat'),
            func.round(NewsData.longitude, 3).label('lon')
        ).filter(
            and_(
                NewsData.processed == 1,
                NewsData.latitude.isnot(None)
            )
        ).distinct().all()
        
        for row in news_items:
            locations.add((float(row.lat), float(row.lon)))
        
        return list(locations)
    
    def _select_features_for_model(
        self,
        features: Dict[str, float],
        model_type: str
    ) -> Dict[str, float]:
        """Select relevant features for specific model type"""
        feature_names = feature_calculator.get_feature_names(model_type)
        return {k: v for k, v in features.items() if k in feature_names}
    
    def _calculate_data_quality_score(
        self,
        crime_data: pd.DataFrame,
        poi_data: pd.DataFrame,
        news_data: pd.DataFrame,
        event_data: pd.DataFrame
    ) -> float:
        """
        Calculate data quality score (0-1)
        
        What it checks:
        - Data availability (do we have data?)
        - Data completeness (are fields filled?)
        - Data diversity (multiple sources)
        
        Returns:
        - Quality score (0-1)
        """
        scores = []
        
        # Crime data quality
        if not crime_data.empty:
            scores.append(0.3)  # Has crime data
        
        # POI data quality
        if not poi_data.empty:
            scores.append(0.3)  # Has POI data
        
        # News data quality
        if not news_data.empty:
            scores.append(0.2)  # Has news data
        
        # Event data quality
        if not event_data.empty:
            scores.append(0.2)  # Has event data
        
        # Calculate average
        quality_score = sum(scores) if scores else 0.0
        
        return min(1.0, quality_score)
    
    def _check_missing_features(
        self,
        features: Dict[str, float]
    ) -> List[str]:
        """Check for missing or zero features"""
        missing = []
        for key, value in features.items():
            if value == 0.0 or value is None:
                missing.append(key)
        return missing
    
    def _create_training_record(
        self,
        db: Session,
        lat: Decimal,
        lon: Decimal,
        location_name: Optional[str],
        model_type: str,
        features: Dict[str, float],
        data_quality_score: float,
        missing_features: List[str]
    ) -> Optional[TrainingData]:
        """Create and store training data record"""
        try:
            # Check if record already exists
            existing = db.query(TrainingData).filter(
                and_(
                    TrainingData.latitude == float(lat),
                    TrainingData.longitude == float(lon),
                    TrainingData.model_type == model_type,
                    TrainingData.feature_version == self.feature_version
                )
            ).first()
            
            if existing:
                # Update existing record
                existing.features = json.dumps(features)
                existing.data_quality_score = data_quality_score
                existing.missing_features = json.dumps(missing_features)
                db.commit()
                return existing
            
            # Create new record
            training_record = TrainingData(
                latitude=float(lat),
                longitude=float(lon),
                location_name=location_name,
                model_type=model_type,
                features=json.dumps(features),
                feature_version=self.feature_version,
                data_quality_score=data_quality_score,
                missing_features=json.dumps(missing_features),
                used_for_training=0  # Not yet used for training
            )
            
            db.add(training_record)
            db.commit()
            
            return training_record
            
        except Exception as e:
            logger.warning(f"Failed to create training record: {e}")
            db.rollback()
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get feature engineering statistics"""
        return self.stats.copy()


# Global service instance
feature_engineering_service = FeatureEngineeringService()


