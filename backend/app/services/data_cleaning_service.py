"""
Data Cleaning and Preprocessing Service
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.database import get_db
from app.models import CrimeData, NewsData, POIData, TrainingData
from app.utils.data_validators import data_validator

logger = logging.getLogger(__name__)


class DataCleaningService:
    """
    Data Cleaning Service

    """
    
    def __init__(self):
        """Initialize cleaning service"""
        self.stats = {
            'crimes_cleaned': 0,
            'news_cleaned': 0,
            'pois_cleaned': 0,
            'duplicates_removed': 0,
            'missing_values_handled': 0,
            'invalid_records_flagged': 0,
            'errors': 0
        }
    
    async def clean_crime_data(
        self,
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean crime data
        """
        db = None
        try:
            logger.info(f"Starting crime data cleaning (limit={limit}, dry_run={dry_run})")
            
            # Load raw data from database
            db = next(get_db())
            query = db.query(CrimeData).filter(CrimeData.processed == 0)
            
            if limit:
                query = query.limit(limit)
            
            crimes = query.all()
            total_records = len(crimes)
            
            if total_records == 0:
                logger.info("No raw crime data to clean")
                if db:
                    db.close()
                return {
                    'total_records': 0,
                    'duplicates_removed': 0,
                    'missing_values_handled': 0,
                    'invalid_records_flagged': 0,
                    'cleaned_records': 0
                }
            
            logger.info(f"Loaded {total_records} raw crime records")
            
            # Convert to pandas DataFrame (for easy manipulation)
            # Why pandas? Makes data cleaning operations much easier
            data = []
            for crime in crimes:
                data.append({
                    'id': crime.id,
                    'latitude': crime.latitude,
                    'longitude': crime.longitude,
                    'category': crime.category,
                    'crime_type': crime.crime_type,
                    'month': crime.month,
                    'location_subtype': crime.location_subtype,
                    'context': crime.context,
                    'crime_id': crime.crime_id,
                    'location_hash': crime.location_hash,
                    'collected_at': crime.collected_at
                })
            
            df = pd.DataFrame(data)
            logger.info(f"Converted to DataFrame: {len(df)} rows, {len(df.columns)} columns")
            
            # Remove duplicates
            # Strategy: Keep first occurrence, remove duplicates by:
            # - crime_id (if present)
            # - location_hash + category + month (if crime_id missing)
            initial_count = len(df)
            
            # Remove duplicates by crime_id (most reliable)
            df = df.drop_duplicates(subset=['crime_id'], keep='first')
            duplicates_by_id = initial_count - len(df)
            
            # Remove duplicates by location_hash + category + month
            initial_count = len(df)
            df = df.drop_duplicates(subset=['location_hash', 'category', 'month'], keep='first')
            duplicates_by_hash = initial_count - len(df)
            
            total_duplicates = duplicates_by_id + duplicates_by_hash
            logger.info(f"Removed {total_duplicates} duplicate records ({duplicates_by_id} by ID, {duplicates_by_hash} by hash)")
            
            # Handle missing values
            missing_before = df.isnull().sum().sum()
            
            # Fill missing crime_type with category
            df['crime_type'] = df['crime_type'].fillna(df['category'])
            
            # Fill missing location_subtype with "Unknown"
            df['location_subtype'] = df['location_subtype'].fillna('Unknown')
            
            # Fill missing context with empty string
            df['context'] = df['context'].fillna('')
            
            # Drop records with missing critical fields (coordinates, category, month)
            critical_missing = df[df[['latitude', 'longitude', 'category', 'month']].isnull().any(axis=1)]
            df = df.dropna(subset=['latitude', 'longitude', 'category', 'month'])
            
            missing_handled = missing_before - df.isnull().sum().sum()
            logger.info(f"Handled {missing_handled} missing values, dropped {len(critical_missing)} records with critical missing fields")
            
            # Normalize formats
            # Normalize category (lowercase, strip whitespace)
            df['category'] = df['category'].str.lower().str.strip()
            
            # Normalize month format (ensure YYYY-MM)
            # Handle None values first
            df['month'] = df['month'].fillna('').astype(str)
            df['month'] = df['month'].apply(self._normalize_month)
            # Fill any None results with current month
            df['month'] = df['month'].fillna(datetime.now().strftime('%Y-%m'))
            
            # Normalize coordinates (round to 6 decimal places)
            df['latitude'] = df['latitude'].round(6)
            df['longitude'] = df['longitude'].round(6)
            
            logger.info("Normalized data formats")
            
            # Validate data quality
            invalid_records = []
            for idx, row in df.iterrows():
                crime_dict = row.to_dict()
                is_valid, errors = data_validator.validate_crime_data(crime_dict)
                if not is_valid:
                    invalid_records.append({
                        'id': crime_dict.get('id'),
                        'errors': errors
                    })
            
            if invalid_records:
                logger.warning(f"Found {len(invalid_records)} invalid records")
                # Flag invalid records (set processed = -1 for review)
                invalid_ids = [r['id'] for r in invalid_records]
                if not dry_run:
                    db.query(CrimeData).filter(CrimeData.id.in_(invalid_ids)).update(
                        {'processed': -1}, synchronize_session=False
                    )
                    db.commit()
            
            # Mark cleaned records as processed
            cleaned_ids = df['id'].tolist()
            if not dry_run:
                db.query(CrimeData).filter(CrimeData.id.in_(cleaned_ids)).update(
                    {'processed': 1}, synchronize_session=False
                )
                db.commit()
                logger.info(f"Marked {len(cleaned_ids)} records as processed")
            
            if db:
                db.close()
            
            # Update statistics
            self.stats['crimes_cleaned'] += len(cleaned_ids)
            self.stats['duplicates_removed'] += total_duplicates
            self.stats['missing_values_handled'] += missing_handled
            self.stats['invalid_records_flagged'] += len(invalid_records)
            
            return {
                'total_records': total_records,
                'duplicates_removed': total_duplicates,
                'missing_values_handled': missing_handled,
                'invalid_records_flagged': len(invalid_records),
                'cleaned_records': len(cleaned_ids),
                'invalid_records': invalid_records[:10]  # First 10 for review
            }
            
        except Exception as e:
            logger.error(f"Crime data cleaning failed: {e}", exc_info=True)
            self.stats['errors'] += 1
            if db:
                try:
                    db.rollback()
                    db.close()
                except:
                    pass
            raise
    
    async def clean_news_data(
        self,
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean news data
        """
        db = None
        try:
            logger.info(f"Starting news data cleaning (limit={limit}, dry_run={dry_run})")
            
            # Load raw data
            db = next(get_db())
            query = db.query(NewsData).filter(NewsData.processed == 0)
            
            if limit:
                query = query.limit(limit)
            
            news_items = query.all()
            total_records = len(news_items)
            
            if total_records == 0:
                if db:
                    db.close()
                return {
                    'total_records': 0,
                    'duplicates_removed': 0,
                    'missing_values_handled': 0,
                    'invalid_records_flagged': 0,
                    'cleaned_records': 0
                }
            
            # Convert to DataFrame
            data = []
            for news in news_items:
                data.append({
                    'id': news.id,
                    'article_id': news.article_id,
                    'title': news.title,
                    'description': news.description,
                    'content': news.content,
                    'latitude': news.latitude,
                    'longitude': news.longitude,
                    'source_name': news.source_name,
                    'published_at': news.published_at,
                    'sentiment_score': news.sentiment_score,
                    'collected_at': news.collected_at
                })
            
            df = pd.DataFrame(data)
            
            # Remove duplicates by article_id
            initial_count = len(df)
            df = df.drop_duplicates(subset=['article_id'], keep='first')
            duplicates_removed = initial_count - len(df)
            
            # Handle missing values
            missing_before = df.isnull().sum().sum()
            
            # Fill missing description with empty string
            df['description'] = df['description'].fillna('')
            
            # Fill missing content with description
            df['content'] = df['content'].fillna(df['description'])
            
            # Fill missing source_name with "Unknown"
            df['source_name'] = df['source_name'].fillna('Unknown')
            
            # Drop records with missing title (critical field)
            df = df.dropna(subset=['title'])
            
            missing_handled = missing_before - df.isnull().sum().sum()
            
            # Normalize text fields
            df['title'] = df['title'].str.strip()
            df['description'] = df['description'].str.strip()
            df['source_name'] = df['source_name'].str.strip()
            
            # Validate data quality
            invalid_records = []
            for idx, row in df.iterrows():
                news_dict = row.to_dict()
                is_valid, errors = data_validator.validate_news_data(news_dict)
                if not is_valid:
                    invalid_records.append({
                        'id': news_dict.get('id'),
                        'errors': errors
                    })
            
            # Flag invalid records
            if invalid_records and not dry_run:
                invalid_ids = [r['id'] for r in invalid_records]
                db.query(NewsData).filter(NewsData.id.in_(invalid_ids)).update(
                    {'processed': -1}, synchronize_session=False
                )
                db.commit()
            
            # Mark as processed
            cleaned_ids = df['id'].tolist()
            if not dry_run:
                db.query(NewsData).filter(NewsData.id.in_(cleaned_ids)).update(
                    {'processed': 1}, synchronize_session=False
                )
                db.commit()
            
            if db:
                db.close()
            
            self.stats['news_cleaned'] += len(cleaned_ids)
            self.stats['duplicates_removed'] += duplicates_removed
            self.stats['missing_values_handled'] += missing_handled
            self.stats['invalid_records_flagged'] += len(invalid_records)
            
            return {
                'total_records': total_records,
                'duplicates_removed': duplicates_removed,
                'missing_values_handled': missing_handled,
                'invalid_records_flagged': len(invalid_records),
                'cleaned_records': len(cleaned_ids)
            }
            
        except Exception as e:
            logger.error(f"News data cleaning failed: {e}", exc_info=True)
            self.stats['errors'] += 1
            if db:
                try:
                    db.rollback()
                    db.close()
                except:
                    pass
            raise
    
    async def clean_poi_data(
        self,
        limit: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean POI data
        """
        db = None
        try:
            logger.info(f"Starting POI data cleaning (limit={limit}, dry_run={dry_run})")
            
            # Load raw data
            db = next(get_db())
            query = db.query(POIData).filter(POIData.processed == 0)
            
            if limit:
                query = query.limit(limit)
            
            pois = query.all()
            total_records = len(pois)
            
            if total_records == 0:
                if db:
                    db.close()
                return {
                    'total_records': 0,
                    'duplicates_removed': 0,
                    'missing_values_handled': 0,
                    'invalid_records_flagged': 0,
                    'cleaned_records': 0
                }
            
            # Convert to DataFrame
            data = []
            for poi in pois:
                data.append({
                    'id': poi.id,
                    'poi_id': poi.poi_id,
                    'latitude': poi.latitude,
                    'longitude': poi.longitude,
                    'name': poi.name,
                    'amenity': poi.amenity,
                    'category': poi.category,
                    'type': poi.type,
                    'location_hash': poi.location_hash,
                    'is_essential': poi.is_essential,
                    'collected_at': poi.collected_at
                })
            
            df = pd.DataFrame(data)
            
            # Remove duplicates
            initial_count = len(df)
            df = df.drop_duplicates(subset=['poi_id'], keep='first')
            duplicates_by_id = initial_count - len(df)
            
            initial_count = len(df)
            df = df.drop_duplicates(subset=['location_hash', 'amenity'], keep='first')
            duplicates_by_hash = initial_count - len(df)
            
            total_duplicates = duplicates_by_id + duplicates_by_hash
            
            # Handle missing values
            missing_before = df.isnull().sum().sum()
            
            # Fill missing name with amenity or "Unknown"
            df['name'] = df['name'].fillna(df['amenity']).fillna('Unknown')
            
            # Fill missing amenity with "other"
            df['amenity'] = df['amenity'].fillna('other')
            
            # Drop records with missing coordinates
            df = df.dropna(subset=['latitude', 'longitude'])
            
            missing_handled = missing_before - df.isnull().sum().sum()
            
            # Normalize formats
            df['amenity'] = df['amenity'].str.lower().str.strip()
            df['name'] = df['name'].str.strip()
            df['latitude'] = df['latitude'].round(6)
            df['longitude'] = df['longitude'].round(6)
            
            # Validate data quality
            invalid_records = []
            for idx, row in df.iterrows():
                poi_dict = row.to_dict()
                is_valid, errors = data_validator.validate_poi_data(poi_dict)
                if not is_valid:
                    invalid_records.append({
                        'id': poi_dict.get('id'),
                        'errors': errors
                    })
            
            # Flag invalid records
            if invalid_records and not dry_run:
                invalid_ids = [r['id'] for r in invalid_records]
                db.query(POIData).filter(POIData.id.in_(invalid_ids)).update(
                    {'processed': -1}, synchronize_session=False
                )
                db.commit()
            
            # Mark as processed
            cleaned_ids = df['id'].tolist()
            if not dry_run:
                db.query(POIData).filter(POIData.id.in_(cleaned_ids)).update(
                    {'processed': 1}, synchronize_session=False
                )
                db.commit()
            
            if db:
                db.close()
            
            self.stats['pois_cleaned'] += len(cleaned_ids)
            self.stats['duplicates_removed'] += total_duplicates
            self.stats['missing_values_handled'] += missing_handled
            self.stats['invalid_records_flagged'] += len(invalid_records)
            
            return {
                'total_records': total_records,
                'duplicates_removed': total_duplicates,
                'missing_values_handled': missing_handled,
                'invalid_records_flagged': len(invalid_records),
                'cleaned_records': len(cleaned_ids)
            }
            
        except Exception as e:
            logger.error(f"POI data cleaning failed: {e}", exc_info=True)
            self.stats['errors'] += 1
            if db:
                try:
                    db.rollback()
                    db.close()
                except:
                    pass
            raise
    
    async def clean_all_data(
        self,
        limit_per_type: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean all data types
        """
        try:
            logger.info(f"Starting full data cleaning (limit_per_type={limit_per_type}, dry_run={dry_run})")
            
            # Clean each data type
            crime_result = await self.clean_crime_data(limit=limit_per_type, dry_run=dry_run)
            news_result = await self.clean_news_data(limit=limit_per_type, dry_run=dry_run)
            poi_result = await self.clean_poi_data(limit=limit_per_type, dry_run=dry_run)
            
            return {
                'crimes': crime_result,
                'news': news_result,
                'pois': poi_result,
                'total_cleaned': (
                    crime_result['cleaned_records'] +
                    news_result['cleaned_records'] +
                    poi_result['cleaned_records']
                ),
                'total_duplicates_removed': (
                    crime_result['duplicates_removed'] +
                    news_result['duplicates_removed'] +
                    poi_result['duplicates_removed']
                ),
                'total_invalid_flagged': (
                    crime_result['invalid_records_flagged'] +
                    news_result['invalid_records_flagged'] +
                    poi_result['invalid_records_flagged']
                )
            }
            
        except Exception as e:
            logger.error(f"Full data cleaning failed: {e}", exc_info=True)
            raise
    
    def _normalize_month(self, month_str: str) -> str:
        """
        Normalize month format to YYYY-MM
        """
        if not month_str or str(month_str).strip() == '' or str(month_str).lower() == 'nan':
            return datetime.now().strftime('%Y-%m')
        
        month_str = str(month_str).strip()
        
        # Try parsing different formats
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m', '%Y/%m']:
            try:
                dt = datetime.strptime(month_str, fmt)
                return dt.strftime('%Y-%m')
            except (ValueError, TypeError):
                continue
        
        # Fallback: try to extract YYYY-MM from string
        if len(month_str) >= 7:
            return month_str[:7]
        
        # Last resort: return current month
        return datetime.now().strftime('%Y-%m')
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cleaning statistics"""
        return self.stats.copy()


# Global service instance
data_cleaning_service = DataCleaningService()


