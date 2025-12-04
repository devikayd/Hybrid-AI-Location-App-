"""
Location Data Service - Aggregates all data for a location
"""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
import asyncio

from app.core.config import settings
from app.core.redis import geocode_cache
from app.schemas.user_interaction import LocationItem, LocationDataResponse
from app.services.crime_service import crime_service
from app.services.events_service import events_service
from app.services.news_service import news_service
from app.services.pois_service import pois_service
from app.services.user_interaction_service import user_interaction_service
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class LocationDataService:
    """Service for aggregating all location data (events, POIs, news, crimes)"""
    
    def __init__(self):
        self.cache_ttl = 1800  # 30 minutes cache
    
    async def get_location_data(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 10,
        user_id: Optional[str] = None
    ) -> LocationDataResponse:
        """
        Get all data for a location (events, POIs, news, crimes)
        """
        # Generate cache key
        cache_key = geocode_cache.generate_key(
            "location_data",
            lat=str(lat),
            lon=str(lon),
            radius_km=radius_km
        )
        
        # Check cache first
        cached_result = await geocode_cache.get(cache_key)
        if cached_result:
            logger.info(f"Location data cache hit for: {lat}, {lon}")
            location_data = LocationDataResponse(**cached_result)
        else:
            # Collect all data concurrently
            events, pois, news, crimes = await self._collect_all_data(lat, lon, radius_km)
            
            location_data = LocationDataResponse(
                lat=lat,
                lon=lon,
                events=events,
                pois=pois,
                news=news,
                crimes=crimes,
                total_items=len(events) + len(pois) + len(news) + len(crimes),
                cached=False
            )
            
            # Cache the result
            await geocode_cache.set(cache_key, location_data.dict(), ttl=self.cache_ttl)
        
        # Note: User interaction status will be added by the router using database session
        
        return location_data
    
    async def _collect_all_data(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int
    ) -> tuple[List[LocationItem], List[LocationItem], List[LocationItem], List[LocationItem]]:
        """Collect all data types concurrently with timeout protection"""
        
        # Set individual timeouts for each API call to prevent hanging
        async def collect_with_timeout(coro, timeout_seconds, api_name):
            try:
                return await asyncio.wait_for(coro, timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning(f"{api_name} collection timed out after {timeout_seconds}s")
                return []
            except Exception as e:
                logger.warning(f"{api_name} collection failed: {e}")
                return []
        
        # Collect with individual timeouts (faster APIs get shorter timeouts)
        # Reduced POI timeout to prevent long waits - POIs are nice-to-have, not critical
        tasks = [
            collect_with_timeout(self._collect_events(lat, lon, radius_km), 10.0, "Events"),
            collect_with_timeout(self._collect_pois(lat, lon, radius_km), 15.0, "POIs"),  # Reduced from 25s to 15s
            collect_with_timeout(self._collect_news(lat, lon, radius_km), 10.0, "News"),
            collect_with_timeout(self._collect_crimes(lat, lon, radius_km), 10.0, "Crimes")
        ]
        
        logger.info(f"Starting data collection for {lat}, {lon} with timeouts: Events=10s, POIs=15s, News=10s, Crimes=10s")
        
        # Run all tasks concurrently - they'll timeout individually
        import time
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time
        
        # Extract results (already handled exceptions in collect_with_timeout)
        events = results[0] if not isinstance(results[0], Exception) else []
        pois = results[1] if not isinstance(results[1], Exception) else []
        news = results[2] if not isinstance(results[2], Exception) else []
        crimes = results[3] if not isinstance(results[3], Exception) else []
        
        logger.info(f"Collected data in {elapsed_time:.2f}s: {len(events)} events, {len(pois)} pois, {len(news)} news, {len(crimes)} crimes")
        
        return events, pois, news, crimes
    
    async def _collect_events(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[LocationItem]:
        """Collect event items"""
        try:
            event_response = await events_service.get_events(
                lat=lat,
                lon=lon,
                within_km=radius_km,
                limit=100
            )
            
            items = []
            for event in event_response.events:
                if event.venue and event.venue.latitude and event.venue.longitude:
                    items.append(LocationItem(
                        id=f"event_{event.id}",
                        type="event",
                        title=event.name.get("text", "Event") if isinstance(event.name, dict) else str(event.name),
                        description=event.description.get("text", "") if isinstance(event.description, dict) else (str(event.description) if event.description else ""),
                        lat=Decimal(str(event.venue.latitude)),
                        lon=Decimal(str(event.venue.longitude)),
                        category=event.category_id or "general",
                        subtype="free" if event.is_free else "paid",
                        distance_km=None,  # Will be calculated if needed
                        date=event.start.get("utc", "") if isinstance(event.start, dict) else "",
                        url=event.url,
                        metadata={
                            "is_free": event.is_free,
                            "venue_name": event.venue.name if event.venue else None
                        }
                    ))
            
            return items
        except Exception as e:
            logger.error(f"Error collecting events: {e}")
            return []
    
    async def _collect_pois(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[LocationItem]:
        """Collect POI items"""
        try:
            poi_response = await pois_service.get_pois(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=100
            )
            
            items = []
            for poi in poi_response.pois:
                # Extract website URL if available
                website_url = poi.tags.website
                # Ensure URL has protocol
                if website_url and not website_url.startswith(('http://', 'https://')):
                    website_url = f"https://{website_url}"
                
                items.append(LocationItem(
                    id=f"poi_{poi.id}",
                    type="poi",
                    title=poi.tags.name or f"{poi.type.title()} POI",
                    description=f"{poi.type.title()} - {poi.tags.addr_street or 'Location'}",
                    lat=Decimal(str(poi.lat)),
                    lon=Decimal(str(poi.lon)),
                    category=poi.tags.amenity or poi.type,
                    subtype=poi.type,
                    distance_km=poi.distance or None,
                    date=None,
                    url=website_url,  # Use website as URL
                    metadata={
                        "amenity": poi.tags.amenity,
                        "opening_hours": poi.tags.opening_hours,
                        "phone": poi.tags.phone,
                        "website": poi.tags.website
                    }
                ))
            
            return items
        except Exception as e:
            logger.error(f"Error collecting POIs: {e}")
            return []
    
    async def _collect_news(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[LocationItem]:
        """Collect news items"""
        try:
            news_response = await news_service.get_news(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=50
            )
            
            items = []
            for i, article in enumerate(news_response.articles):
                # Use search center with small offset for news
                offset_lat = float(lat) + (i % 10 - 5) * 0.001
                offset_lon = float(lon) + (i % 10 - 5) * 0.001
                
                sentiment = article.sentiment if article.sentiment else 0.0
                subtype = "positive" if sentiment > 0.1 else "negative" if sentiment < -0.1 else "neutral"
                
                items.append(LocationItem(
                    id=f"news_{i}",
                    type="news",
                    title=article.title,
                    description=article.description or "",
                    lat=Decimal(str(offset_lat)),
                    lon=Decimal(str(offset_lon)),
                    category="news",
                    subtype=subtype,
                    distance_km=0.1,  # Approximate
                    date=article.publishedAt,
                    url=article.url,
                    metadata={
                        "sentiment": sentiment,
                        "source": article.source.name if article.source else None
                    }
                ))
            
            return items
        except Exception as e:
            logger.error(f"Error collecting news: {e}")
            return []
    
    async def _collect_crimes(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[LocationItem]:
        """Collect crime items"""
        try:
            crime_response = await crime_service.get_crimes(
                lat=lat,
                lon=lon,
                months=6,
                limit=50
            )
            
            items = []
            for crime in crime_response.crimes:
                if crime.location and crime.location.latitude and crime.location.longitude:
                    # Generate URL to UK Police website for this location
                    crime_url = f"https://www.police.uk/pu/your-area/?q={crime.location.latitude},{crime.location.longitude}"
                    
                    items.append(LocationItem(
                        id=f"crime_{crime.id}",
                        type="crime",
                        title=f"Crime Alert: {crime.category}",
                        description=f"Recent {crime.category} incident reported",
                        lat=Decimal(str(crime.location.latitude)),
                        lon=Decimal(str(crime.location.longitude)),
                        category=crime.category,
                        subtype=crime.category,
                        distance_km=None,
                        date=crime.date,
                        url=crime_url,  # Add URL for crime location on UK Police website
                        metadata={
                            "crime_type": crime.category,
                            "month": crime.month if hasattr(crime, 'month') else None,
                            "persistent_id": crime.persistent_id if hasattr(crime, 'persistent_id') else None
                        }
                    ))
            
            return items
        except Exception as e:
            logger.error(f"Error collecting crimes: {e}")
            return []
    
    async def add_user_interaction_status(
        self,
        location_data: LocationDataResponse,
        user_id: str,
        db
    ):
        """Add liked/saved status to items based on user interactions"""
        # Get all item IDs
        all_items = location_data.events + location_data.pois + location_data.news + location_data.crimes
        item_ids = [item.id for item in all_items]
        
        if not item_ids:
            return
        
        # Get user interactions for these items
        interactions = await user_interaction_service.get_user_interactions_for_items(user_id, item_ids, db)
        
        # Create lookup dictionaries
        liked_items = {interaction.item_id for interaction in interactions if interaction.interaction_type == "like" and interaction.is_active}
        saved_items = {interaction.item_id for interaction in interactions if interaction.interaction_type == "save" and interaction.is_active}
        
        # Update items with interaction status
        for item in all_items:
            item.is_liked = item.id in liked_items
            item.is_saved = item.id in saved_items


# Service instance
location_data_service = LocationDataService()

