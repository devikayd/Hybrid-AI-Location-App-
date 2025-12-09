# Data Collection Service for ML Training

import logging
import hashlib
import json
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models import CrimeData, EventData, NewsData, POIData
from app.services.crime_service import crime_service
from app.services.events_service import events_service
from app.services.news_service import news_service
from app.services.pois_service import pois_service
from app.schemas.crime import CrimeData as CrimeSchema
from app.schemas.events import EventData as EventSchema
from app.schemas.news import NewsArticle
from app.schemas.pois import POIData as POISchema

logger = logging.getLogger(__name__)


class DataCollectionService: 
    
    def __init__(self):
        """Initialize the data collection service"""
        self.stats = {
            'crimes_collected': 0,
            'events_collected': 0,
            'news_collected': 0,
            'pois_collected': 0,
            'errors': 0
        }
    
    def _generate_location_hash(self, lat: float, lon: float, precision: int = 6) -> str:      
        # Generate location hash for deduplication   
        # Round coordinates to reduce precision
        rounded_lat = round(float(lat), precision)
        rounded_lon = round(float(lon), precision)
        
        # Create hash
        location_string = f"{rounded_lat},{rounded_lon}"
        return hashlib.sha256(location_string.encode()).hexdigest()
    
    async def collect_crime_data(
        self,
        lat: Decimal,
        lon: Decimal,
        months: int = 12,
        limit: int = 100
    ) -> Dict[str, Any]:
        # Collect and store crime data from UK Police API 
        try:
            # Fetch data from API service
            logger.info(f"Collecting crime data for location: {lat}, {lon}")
            crime_response = await crime_service.get_crimes(
                lat=lat,
                lon=lon,
                months=months,
                limit=limit
            )
            
            # Get database session
            db = next(get_db())
            collected_count = 0
            duplicate_count = 0
            error_count = 0
            
            # Process each crime record
            for crime_schema in crime_response.crimes:
                try:
                    # Extract location from crime data
                    # UK Police API returns location as nested object
                    location = crime_schema.location
                    if location and location.latitude and location.longitude:
                        crime_lat = float(location.latitude)
                        crime_lon = float(location.longitude)
                    else:
                        # Use search center if location not available
                        crime_lat = float(lat)
                        crime_lon = float(lon)
                    
                    # Generate location hash for deduplication
                    location_hash = self._generate_location_hash(crime_lat, crime_lon)
                    
                    # Check if crime already exists (using persistent_id or crime_id)
                    crime_id = crime_schema.persistent_id or crime_schema.id
                    
                    existing_crime = db.query(CrimeData).filter(
                        (CrimeData.crime_id == str(crime_id)) if crime_id else False
                    ).first()
                    
                    if existing_crime:
                        duplicate_count += 1
                        continue
                    
                    # Create database model
                    crime_db = CrimeData(
                        latitude=crime_lat,
                        longitude=crime_lon,
                        category=crime_schema.category or "Unknown",
                        crime_type=crime_schema.category,  # Use category as type
                        month=crime_schema.month or datetime.now().strftime('%Y-%m'),
                        location_subtype=crime_schema.location_type,
                        context=crime_schema.context,
                        crime_id=str(crime_id) if crime_id else None,
                        location_hash=location_hash,
                        processed=0
                    )
                    
                    # Store in database
                    db.add(crime_db)
                    db.commit()
                    collected_count += 1
                    
                except IntegrityError:
                    # Duplicate detected (unique constraint violation)
                    db.rollback()
                    duplicate_count += 1
                    logger.debug(f"Duplicate crime record: {crime_id}")
                    
                except Exception as e:
                    db.rollback()
                    error_count += 1
                    logger.warning(f"Error storing crime record: {e}")
            
            db.close()
            
            # Update statistics
            self.stats['crimes_collected'] += collected_count
            
            logger.info(f"Crime data collection complete: {collected_count} new, {duplicate_count} duplicates, {error_count} errors")
            
            return {
                'collected': collected_count,
                'duplicates': duplicate_count,
                'errors': error_count,
                'total_fetched': len(crime_response.crimes)
            }
            
        except Exception as e:
            logger.error(f"Crime data collection failed: {e}")
            self.stats['errors'] += 1
            return {
                'collected': 0,
                'duplicates': 0,
                'errors': 1,
                'total_fetched': 0
            }
    
    async def collect_event_data(
        self,
        lat: Decimal,
        lon: Decimal,
        within_km: int = 10,
        limit: int = 50
    ) -> Dict[str, Any]:
        # Collect and store event data from Eventbrite API
        try:
            logger.info(f"Collecting event data for location: {lat}, {lon}")
            event_response = await events_service.get_events(
                lat=lat,
                lon=lon,
                within_km=within_km,
                limit=limit
            )
            
            db = next(get_db())
            collected_count = 0
            duplicate_count = 0
            error_count = 0
            
            for event_schema in event_response.events:
                try:
                    # Extract location from event
                    event_lat = float(event_schema.latitude or lat)
                    event_lon = float(event_schema.longitude or lon)
                    
                    # Generate location hash
                    location_hash = self._generate_location_hash(event_lat, event_lon)
                    
                    # Check for duplicates
                    existing_event = db.query(EventData).filter(
                        EventData.event_id == event_schema.id
                    ).first()
                    
                    if existing_event:
                        duplicate_count += 1
                        continue
                    
                    # Create database model
                    event_db = EventData(
                        latitude=event_lat,
                        longitude=event_lon,
                        event_id=event_schema.id,
                        name=event_schema.name or "Untitled Event",
                        description=event_schema.description,
                        category=event_schema.category,
                        subcategory=event_schema.subcategory,
                        format=event_schema.format,
                        is_free=event_schema.is_free or False,
                        price=event_schema.price if event_schema.price else None,
                        currency=event_schema.currency or "GBP",
                        start_time=event_schema.start_time,
                        end_time=event_schema.end_time,
                        venue_name=event_schema.venue_name,
                        venue_address=event_schema.venue_address,
                        url=event_schema.url,
                        image_url=event_schema.image_url,
                        location_hash=location_hash,
                        processed=0
                    )
                    
                    db.add(event_db)
                    db.commit()
                    collected_count += 1
                    
                except IntegrityError:
                    db.rollback()
                    duplicate_count += 1
                    logger.debug(f"Duplicate event record: {event_schema.id}")
                    
                except Exception as e:
                    db.rollback()
                    error_count += 1
                    logger.warning(f"Error storing event record: {e}")
            
            db.close()
            
            self.stats['events_collected'] += collected_count
            
            logger.info(f"Event data collection complete: {collected_count} new, {duplicate_count} duplicates, {error_count} errors")
            
            return {
                'collected': collected_count,
                'duplicates': duplicate_count,
                'errors': error_count,
                'total_fetched': len(event_response.events)
            }
            
        except Exception as e:
            logger.error(f"Event data collection failed: {e}")
            self.stats['errors'] += 1
            return {
                'collected': 0,
                'duplicates': 0,
                'errors': 1,
                'total_fetched': 0
            }
    
    async def collect_news_data(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 50,
        limit: int = 20
    ) -> Dict[str, Any]:
        # Collect and store news data from NewsAPI 
        try:
            logger.info(f"Collecting news data for location: {lat}, {lon}")
            news_response = await news_service.get_news(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=limit
            )
            
            db = next(get_db())
            collected_count = 0
            duplicate_count = 0
            error_count = 0
            
            for article in news_response.articles:
                try:
                    # NewsAPI may not have exact location, use search center
                    article_lat = float(article.latitude or lat) if article.latitude else float(lat)
                    article_lon = float(article.longitude or lon) if article.longitude else float(lon)
                    
                    # Generate location hash
                    location_hash = self._generate_location_hash(article_lat, article_lon)
                    
                    # Check for duplicates (using URL as unique identifier)
                    article_id = article.url or article.title
                    existing_news = db.query(NewsData).filter(
                        NewsData.url == article.url
                    ).first() if article.url else None
                    
                    if existing_news:
                        duplicate_count += 1
                        continue
                    
                    # Create database model
                    news_db = NewsData(
                        latitude=article_lat,
                        longitude=article_lon,
                        article_id=article_id[:100] if article_id else None,  # Limit length
                        title=article.title or "Untitled",
                        description=article.description,
                        content=article.content,
                        source_name=article.source_name,
                        source_id=article.source_id,
                        author=article.author,
                        published_at=article.published_at,
                        url=article.url,
                        image_url=article.image_url,
                        location_hash=location_hash,
                        processed=0 
                    )
                    
                    db.add(news_db)
                    db.commit()
                    collected_count += 1
                    
                except IntegrityError:
                    db.rollback()
                    duplicate_count += 1
                    logger.debug(f"Duplicate news record: {article.url}")
                    
                except Exception as e:
                    db.rollback()
                    error_count += 1
                    logger.warning(f"Error storing news record: {e}")
            
            db.close()
            
            self.stats['news_collected'] += collected_count
            
            logger.info(f"News data collection complete: {collected_count} new, {duplicate_count} duplicates, {error_count} errors")
            
            return {
                'collected': collected_count,
                'duplicates': duplicate_count,
                'errors': error_count,
                'total_fetched': len(news_response.articles)
            }
            
        except Exception as e:
            logger.error(f"News data collection failed: {e}")
            self.stats['errors'] += 1
            return {
                'collected': 0,
                'duplicates': 0,
                'errors': 1,
                'total_fetched': 0
            }
    
    async def collect_poi_data(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 5,
        limit: int = 100
    ) -> Dict[str, Any]:
        # Collect and store POI data from OpenStreetMap
        try:
            logger.info(f"Collecting POI data for location: {lat}, {lon}")
            poi_response = await pois_service.get_pois(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=limit
            )
            
            db = next(get_db())
            collected_count = 0
            duplicate_count = 0
            error_count = 0
            
            for poi_schema in poi_response.pois:
                try:
                    # POI schema uses 'lat' and 'lon' (not 'latitude'/'longitude')
                    poi_lat = float(poi_schema.lat)
                    poi_lon = float(poi_schema.lon)
                    
                    # Generate location hash
                    location_hash = self._generate_location_hash(poi_lat, poi_lon)
                    
                    # Check for duplicates
                    existing_poi = db.query(POIData).filter(
                        POIData.poi_id == str(poi_schema.id)
                    ).first()
                    
                    if existing_poi:
                        duplicate_count += 1
                        continue
                    
                    # Extract fields from tags object
                    tags_obj = poi_schema.tags if poi_schema.tags else None
                    amenity = tags_obj.amenity if tags_obj and hasattr(tags_obj, 'amenity') else None
                    name = tags_obj.name if tags_obj and hasattr(tags_obj, 'name') else None
                    phone = tags_obj.phone if tags_obj and hasattr(tags_obj, 'phone') else None
                    website = tags_obj.website if tags_obj and hasattr(tags_obj, 'website') else None
                    addr_street = tags_obj.addr_street if tags_obj and hasattr(tags_obj, 'addr_street') else None
                    addr_city = tags_obj.addr_city if tags_obj and hasattr(tags_obj, 'addr_city') else None
                    addr_postcode = tags_obj.addr_postcode if tags_obj and hasattr(tags_obj, 'addr_postcode') else None
                    
                    # Build address from components
                    address_parts = [addr_street, addr_city]
                    address = ", ".join([p for p in address_parts if p]) if any(address_parts) else None
                    
                    # Determine if essential amenity
                    is_essential = 1 if amenity in [
                        'hospital', 'pharmacy', 'police', 'fire_station',
                        'school', 'university', 'library'
                    ] else 0
                    
                    # Create database model
                    poi_db = POIData(
                        latitude=poi_lat,
                        longitude=poi_lon,
                        poi_id=str(poi_schema.id),
                        name=name,
                        amenity=amenity,
                        category=None,  # Not in schema, will be set during processing
                        type=poi_schema.type,
                        tags=json.dumps(tags_obj.dict()) if tags_obj else None,
                        address=address,
                        postcode=addr_postcode,
                        phone=phone,
                        website=website,
                        location_hash=location_hash,
                        is_essential=is_essential,
                        processed=0
                    )
                    
                    db.add(poi_db)
                    db.commit()
                    collected_count += 1
                    
                except IntegrityError:
                    db.rollback()
                    duplicate_count += 1
                    logger.debug(f"Duplicate POI record: {poi_schema.id}")
                    
                except Exception as e:
                    db.rollback()
                    error_count += 1
                    logger.warning(f"Error storing POI record: {e}")
            
            db.close()
            
            self.stats['pois_collected'] += collected_count
            
            logger.info(f"POI data collection complete: {collected_count} new, {duplicate_count} duplicates, {error_count} errors")
            
            return {
                'collected': collected_count,
                'duplicates': duplicate_count,
                'errors': error_count,
                'total_fetched': len(poi_response.pois)
            }
            
        except Exception as e:
            logger.error(f"POI data collection failed: {e}")
            self.stats['errors'] += 1
            return {
                'collected': 0,
                'duplicates': 0,
                'errors': 1,
                'total_fetched': 0
            }
    
    async def collect_all_data(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 10,
        months: int = 12,
        limit_per_type: int = 50
    ) -> Dict[str, Any]:
        # Collect all data types for a location
        """ 
        This is the main method for batch data collection.
        It collects crime, event, news, and POI data concurrently.
        """

        import asyncio
        
        logger.info(f"Starting batch data collection for location: {lat}, {lon}")
        
        # Collect all data types concurrently
        results = await asyncio.gather(
            self.collect_crime_data(lat, lon, months, limit_per_type),
            self.collect_event_data(lat, lon, radius_km, limit_per_type),
            self.collect_news_data(lat, lon, radius_km, limit_per_type),
            self.collect_poi_data(lat, lon, radius_km, limit_per_type),
            return_exceptions=True
        )
        
        # Process results
        summary = {
            'crimes': results[0] if not isinstance(results[0], Exception) else {'collected': 0, 'errors': 1},
            'events': results[1] if not isinstance(results[1], Exception) else {'collected': 0, 'errors': 1},
            'news': results[2] if not isinstance(results[2], Exception) else {'collected': 0, 'errors': 1},
            'pois': results[3] if not isinstance(results[3], Exception) else {'collected': 0, 'errors': 1},
            'total_collected': sum(
                r.get('collected', 0) if not isinstance(r, Exception) else 0
                for r in results
            ),
            'total_errors': sum(
                r.get('errors', 0) if not isinstance(r, Exception) else 1
                for r in results
            )
        }
        
        logger.info(f"Batch data collection complete: {summary['total_collected']} total records, {summary['total_errors']} errors")
        
        return summary
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        return self.stats.copy()


# Service instance
data_collection_service = DataCollectionService()

