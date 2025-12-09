"""
Location Data Service - Aggregates all data for a location
"""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
import asyncio
from datetime import datetime, timedelta, timezone

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
        # Real-time filtering: configurable via settings
        # Events
        self.event_recent_hours = settings.EVENT_RECENT_HOURS  # Show events from last N hours
        self.event_future_hours = settings.EVENT_FUTURE_HOURS  # Show events in next N hours
        # Crimes: UK Police API provides monthly aggregated data
        # For near real-time, use 1-7 days (shows only most recent crimes)
        self.crime_recent_days = settings.CRIME_RECENT_DAYS  # Show crimes from last N days
        # News: NewsAPI can provide very recent articles
        # For near real-time, use 1-24 hours (shows only latest news)
        self.news_recent_hours = settings.NEWS_RECENT_HOURS  # Show news from last N hours
    
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
            
            # Filter to show only real-time/recent incidents
            # Events: Use cascading fallback (24h past/7d future -> 7d past/14d future -> 14d past/30d future)
            events = self._filter_events_with_fallback(events)
            # News: Use cascading fallback (24 hours -> 7 days -> 14 days)
            news = self._filter_news_with_fallback(news)
            # Crimes: Use cascading fallback (7 days -> 30 days -> 60 days)
            crimes = self._filter_crimes_with_fallback(crimes)
            # POIs don't have dates, so keep all of them (they're static locations)
            
            # Sort by recency (most recent first)
            events = self._sort_by_recency(events)
            news = self._sort_by_recency(news)
            crimes = self._sort_by_recency(crimes)
            
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
                        category=event.category_id or "General",
                        subtype="free" if event.is_free else "paid",
                        distance_km=None,  # Will be calculated if needed
                        date=event.start.get("utc", "") if isinstance(event.start, dict) else "",
                        url=event.url,
                        metadata={
                            "is_free": event.is_free,
                            "venue_name": event.venue.name if event.venue else None,
                            "category_id": event.category_id  # Keep original ID in metadata for reference
                        }
                    ))
            
            return items
        except Exception as e:
            logger.error(f"Error collecting events: {e}")
            return []
    
    async def _collect_pois(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[LocationItem]:
        """Collect POI items with priority sorting"""
        try:
            poi_response = await pois_service.get_pois(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=200  # Get more to sort from
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
                        "tourism": poi.tags.tourism,
                        "shop": poi.tags.shop,
                        "opening_hours": poi.tags.opening_hours,
                        "phone": poi.tags.phone,
                        "website": poi.tags.website
                    }
                ))
            
            # Sort POIs by priority: Tourist attractions > Amenities > Essential amenities > Shops
            sorted_items = self._sort_pois_by_priority(items)
            
            return sorted_items
        except Exception as e:
            logger.error(f"Error collecting POIs: {e}")
            return []
    
    def _sort_pois_by_priority(self, pois: List[LocationItem]) -> List[LocationItem]:
        """
        Sort POIs by priority:
        1. Tourist attractions (tourism tag)
        2. Amenities (amenity tag, non-essential)
        3. Essential amenities (hospitals, pharmacies, banks, etc.)
        4. Shops (shop tag)
        """
        # Define essential amenities
        essential_amenities = {
            "hospital", "pharmacy", "bank", "atm", "fuel", "police", 
            "fire_station", "post_office", "school", "university"
        }
        
        def get_priority(poi: LocationItem) -> int:
            """Get priority number (lower = higher priority)"""
            metadata = poi.metadata or {}
            tourism = metadata.get("tourism")
            amenity = metadata.get("amenity")
            shop = metadata.get("shop")
            
            # Priority 1: Tourist attractions
            if tourism:
                return 1
            
            # Priority 2: Essential amenities
            if amenity and amenity in essential_amenities:
                return 2
            
            # Priority 3: Other amenities (non-essential)
            if amenity:
                return 3
            
            # Priority 4: Shops
            if shop:
                return 4
            
            # Priority 5: Everything else
            return 5
        
        # Sort by priority, then by distance (closer first)
        sorted_pois = sorted(
            pois,
            key=lambda poi: (
                get_priority(poi),
                poi.distance_km if poi.distance_km is not None else float('inf')
            )
        )
        
        logger.info(f"Sorted {len(sorted_pois)} POIs by priority: Tourist attractions > Essential amenities > Amenities > Shops")
        return sorted_pois
    
    async def _collect_news(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[LocationItem]:
        """Collect news items (recent news)"""
        try:
            # Get more news to filter from (we'll filter to last 7 days)
            news_response = await news_service.get_news(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=100  # Get more to filter from
            )
            
            logger.info(f"Collected {len(news_response.articles)} news articles from API for location {lat}, {lon}")
            
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
            
            logger.info(f"Created {len(items)} news LocationItems from {len(news_response.articles)} articles")
            return items
        except Exception as e:
            logger.error(f"Error collecting news for {lat}, {lon}: {e}", exc_info=True)
            return []
    
    def _filter_events_with_fallback(self, items: List[LocationItem]) -> List[LocationItem]:
        """
        Filter events with cascading fallback for FUTURE events only:
        - Past events: Fixed at last 24 hours (no cascading)
        - Future events: Cascading fallback (7 days -> 14 days -> 30 days)
        
        This ensures users see recent past events and upcoming events, expanding future window if needed.
        """
        if not items:
            return []
        
        # Past window is fixed at 24 hours, only cascade future window
        past_hours = 24  # Fixed: only show events from last 24 hours
        future_windows = [168, 336, 720]  # 7 days, 14 days, 30 days future
        
        for future_hours in future_windows:
            filtered = self._filter_events_by_window(items, past_hours, future_hours)
            if len(filtered) > 0:
                logger.info(f"Event filtering: Found {len(filtered)} events using {past_hours}h past / {future_hours}h future window (from {len(items)} total)")
                return filtered
            else:
                logger.debug(f"Event filtering: No events found in {past_hours}h past / {future_hours}h future window, trying next future window...")
        
        # If all windows return 0, log warning and return empty
        logger.warning(f"Event filtering: No events found in {past_hours}h past / up to {future_windows[-1]}h future from {len(items)} total events")
        return []
    
    def _filter_events_by_window(self, items: List[LocationItem], past_hours: int, future_hours: int) -> List[LocationItem]:
        """Filter events to show only those within the specified past/future window"""
        if not items:
            return []
        
        now = datetime.now(timezone.utc)
        past_cutoff = now - timedelta(hours=past_hours)
        future_cutoff = now + timedelta(hours=future_hours)
        filtered = []
        
        for item in items:
            if not item.date:
                continue
            
            try:
                item_date = self._parse_date(item.date)
                if not item_date:
                    continue
                
                if past_cutoff <= item_date <= future_cutoff:
                    hours_ago = (now - item_date).total_seconds() / 3600 if item_date < now else None
                    hours_ahead = (item_date - now).total_seconds() / 3600 if item_date > now else None
                    
                    if not item.metadata:
                        item.metadata = {}
                    item.metadata["hours_ago"] = hours_ago
                    item.metadata["hours_ahead"] = hours_ahead
                    filtered.append(item)
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse event date: {item.date} - {e}")
                continue
        
        return filtered
    
    def _filter_crimes_with_fallback(self, items: List[LocationItem]) -> List[LocationItem]:
        """
        Filter crimes with cascading fallback:
        1. Try last 7 days (most recent)
        2. If no results, try last 30 days
        3. If still no results, try last 60 days (2 months)
        
        This ensures users always see crime data if available, even if it's not super recent.
        UK Police API provides monthly aggregated data (typically 1-2 months old), so this
        fallback ensures we show available data.
        """
        if not items:
            return []
        
        # Try progressively wider time windows
        fallback_windows = [7, 30, 60]  # days
        
        for days in fallback_windows:
            filtered = self._filter_crimes_by_days(items, days)
            if len(filtered) > 0:
                logger.info(f"Crime filtering: Found {len(filtered)} crimes using {days}-day window (from {len(items)} total)")
                return filtered
            else:
                logger.debug(f"Crime filtering: No crimes found in last {days} days, trying next window...")
        
        # If all windows return 0, log warning and return empty
        logger.warning(f"Crime filtering: No crimes found in any time window (7, 30, or 60 days) from {len(items)} total crimes")
        return []
    
    def _filter_news_with_fallback(self, items: List[LocationItem]) -> List[LocationItem]:
        """
        Filter news with cascading fallback:
        1. Try last 24 hours (most recent)
        2. If no results, try last 7 days (168 hours)
        3. If still no results, try last 14 days (336 hours)
        
        This ensures users always see news data if available.
        """
        if not items:
            return []
        
        # Try progressively wider time windows (in hours)
        fallback_windows = [24, 168, 336]  # hours (1 day, 7 days, 14 days)
        
        for hours in fallback_windows:
            filtered = self._filter_news_by_hours(items, hours)
            if len(filtered) > 0:
                logger.info(f"News filtering: Found {len(filtered)} news articles using {hours}-hour window ({hours//24} days, from {len(items)} total)")
                return filtered
            else:
                logger.debug(f"News filtering: No news found in last {hours} hours ({hours//24} days), trying next window...")
        
        # If all windows return 0, log warning and return empty
        logger.warning(f"News filtering: No news found in any time window (24h, 7d, or 14d) from {len(items)} total articles")
        return []
    
    def _filter_news_by_hours(self, items: List[LocationItem], hours: int) -> List[LocationItem]:
        """Filter news to show only those from last N hours"""
        if not items:
            return []
        
        now = datetime.now(timezone.utc)
        news_past_cutoff = now - timedelta(hours=hours)
        filtered = []
        
        for item in items:
            if not item.date:
                continue
            
            try:
                item_date = self._parse_date(item.date)
                if not item_date:
                    continue
                
                if news_past_cutoff <= item_date <= now:
                    hours_ago = (now - item_date).total_seconds() / 3600
                    
                    if not item.metadata:
                        item.metadata = {}
                    item.metadata["hours_ago"] = hours_ago
                    filtered.append(item)
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse news date: {item.date} - {e}")
                continue
        
        return filtered
    
    def _filter_crimes_by_days(self, items: List[LocationItem], days: int) -> List[LocationItem]:
        """Filter crimes to show only those from last N days"""
        if not items:
            return []
        
        now = datetime.now(timezone.utc)
        crime_past_cutoff = now - timedelta(days=days)
        filtered = []
        
        for item in items:
            if not item.date:
                continue
            
            try:
                item_date = self._parse_date(item.date)
                if not item_date:
                    continue
                
                if crime_past_cutoff <= item_date <= now:
                    days_ago = (now - item_date).total_seconds() / 86400
                    
                    if not item.metadata:
                        item.metadata = {}
                    item.metadata["days_ago"] = days_ago
                    item.metadata["hours_ago"] = days_ago * 24
                    filtered.append(item)
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse crime date: {item.date} - {e}")
                continue
        
        return filtered
    
    def _filter_realtime_items(self, items: List[LocationItem], item_type: str) -> List[LocationItem]:
        """
        Filter items to show only real-time/recent incidents
        For events: show upcoming events (within configured hours) or recent past (last N hours)
        For news: filter by published date (last N hours - configurable)
        For crimes: filter by crime date (last N days - configurable)
        
        Note: UK Police API provides monthly aggregated data, so "real-time" for crimes
        is limited to the most recent month. For near real-time, use 1-7 days.
        """
        if not items:
            return []
        
        now = datetime.now(timezone.utc)
        future_cutoff = now + timedelta(hours=self.event_future_hours)
        filtered = []
        
        for item in items:
            if not item.date:
                # If no date, skip it (except for POIs which we handle separately)
                continue
            
            try:
                # Parse date string to datetime
                item_date = self._parse_date(item.date)
                
                if not item_date:
                    logger.debug(f"Could not parse date for {item_type} item {item.id}: {item.date}")
                    continue
                
                # For events: show upcoming (next N hours) or recent past (last N hours)
                if item_type == "event":
                    event_past_cutoff = now - timedelta(hours=self.event_recent_hours)
                    hours_ago = (now - item_date).total_seconds() / 3600 if item_date < now else None
                    hours_ahead = (item_date - now).total_seconds() / 3600 if item_date > now else None
                    
                    # Debug logging for first few items
                    if len(filtered) < 3:
                        logger.debug(f"Event filtering: date={item.date}, parsed={item_date}, hours_ago={hours_ago}, hours_ahead={hours_ahead}, past_cutoff={event_past_cutoff}, future_cutoff={future_cutoff}, within_range={event_past_cutoff <= item_date <= future_cutoff}")
                    
                    if (event_past_cutoff <= item_date <= future_cutoff):
                        # Add recency metadata
                        if not item.metadata:
                            item.metadata = {}
                        item.metadata["hours_ago"] = hours_ago
                        item.metadata["hours_ahead"] = hours_ahead
                        filtered.append(item)
                    elif len(filtered) < 3:
                        logger.debug(f"Event filtered out: date={item.date}, hours_ago={hours_ago}, hours_ahead={hours_ahead}, outside range [{event_past_cutoff}, {future_cutoff}]")
                # For crimes: show crimes from last N days (configurable)
                # UK Police API provides monthly aggregated data
                # The date represents the month, so we compare month-to-month
                elif item_type == "crime":
                    crime_past_cutoff = now - timedelta(days=self.crime_recent_days)
                    
                    # For monthly aggregated data, if the crime month is within the cutoff period, include it
                    # Since crimes are aggregated by month, we check if the month falls within our window
                    if crime_past_cutoff <= item_date <= now:
                        # Add recency metadata
                        days_ago = (now - item_date).total_seconds() / 86400
                        
                        # Debug logging for first few items
                        if len(filtered) < 3:
                            logger.debug(f"Crime filtering: date={item.date}, parsed={item_date}, days_ago={days_ago:.1f}, cutoff_days={self.crime_recent_days}, within_range={crime_past_cutoff <= item_date <= now}")
                        
                        if not item.metadata:
                            item.metadata = {}
                        item.metadata["days_ago"] = days_ago
                        item.metadata["hours_ago"] = days_ago * 24
                        filtered.append(item)
                    elif len(filtered) < 3:
                        days_ago = (now - item_date).total_seconds() / 86400
                        logger.debug(f"Crime filtered out: {days_ago:.1f} days ago (cutoff: {self.crime_recent_days} days), date={item.date}")
                # For news: show news from last N hours (configurable)
                # NewsAPI can provide very recent articles, so hours-based filtering works well
                elif item_type == "news":
                    news_past_cutoff = now - timedelta(hours=self.news_recent_hours)
                    hours_ago = (now - item_date).total_seconds() / 3600
                    
                    # Debug logging for first few items
                    if len(filtered) < 3:
                        logger.debug(f"News item date check: date={item.date}, parsed={item_date}, hours_ago={hours_ago:.1f}, cutoff={news_past_cutoff}, within_range={news_past_cutoff <= item_date <= now}")
                    
                    if news_past_cutoff <= item_date <= now:
                        # Add recency metadata
                        if not item.metadata:
                            item.metadata = {}
                        item.metadata["hours_ago"] = hours_ago
                        filtered.append(item)
                    elif len(filtered) < 3:
                        logger.debug(f"News item filtered out: {hours_ago:.1f} hours ago (cutoff: {self.news_recent_hours} hours)")
                        
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse date for {item_type} item {item.id}: {item.date} - {e}")
                # If date parsing fails, skip the item
                continue
        
        if item_type == "crime":
            if len(filtered) == 0 and len(items) > 0:
                # Log sample dates and parsed dates if all filtered out
                sample_dates = []
                sample_parsed = []
                for item in items[:5]:
                    if item.date:
                        sample_dates.append(item.date)
                        parsed = self._parse_date(item.date)
                        if parsed:
                            days_ago = (datetime.now(timezone.utc) - parsed).total_seconds() / 86400
                            sample_parsed.append(f"{item.date} -> {parsed.date()} ({days_ago:.1f} days ago)")
                        else:
                            sample_parsed.append(f"{item.date} -> FAILED TO PARSE")
                logger.warning(f"Filtered {item_type}: {len(items)} -> {len(filtered)} items (last {self.crime_recent_days} days). Sample dates: {sample_dates[:3]}. Parsed: {sample_parsed[:3]}")
            else:
                logger.info(f"Filtered {item_type}: {len(items)} -> {len(filtered)} items (last {self.crime_recent_days} days)")
        elif item_type == "news":
            if len(filtered) == 0 and len(items) > 0:
                # Log sample dates if all filtered out
                sample_dates = [item.date for item in items[:3] if item.date]
                logger.warning(f"Filtered {item_type}: {len(items)} -> {len(filtered)} items (last {self.news_recent_hours} hours). Sample dates: {sample_dates}")
            else:
                logger.info(f"Filtered {item_type}: {len(items)} -> {len(filtered)} items (last {self.news_recent_hours} hours)")
        elif item_type == "event":
            if len(filtered) == 0 and len(items) > 0:
                # Log sample dates if all filtered out
                sample_dates = []
                sample_parsed = []
                for item in items[:5]:
                    if item.date:
                        sample_dates.append(item.date)
                        parsed = self._parse_date(item.date)
                        if parsed:
                            hours_ago = (datetime.now(timezone.utc) - parsed).total_seconds() / 3600 if parsed < datetime.now(timezone.utc) else None
                            hours_ahead = (parsed - datetime.now(timezone.utc)).total_seconds() / 3600 if parsed > datetime.now(timezone.utc) else None
                            sample_parsed.append(f"{item.date} -> {parsed} (ago: {hours_ago:.1f}h, ahead: {hours_ahead:.1f}h)" if hours_ago else f"{item.date} -> {parsed} (ahead: {hours_ahead:.1f}h)")
                        else:
                            sample_parsed.append(f"{item.date} -> FAILED TO PARSE")
                logger.warning(f"Filtered {item_type}: {len(items)} -> {len(filtered)} items (past {self.event_recent_hours}h, future {self.event_future_hours}h). Sample dates: {sample_dates[:3]}. Parsed: {sample_parsed[:3]}")
            else:
                logger.info(f"Filtered {item_type}: {len(items)} -> {len(filtered)} items (past {self.event_recent_hours}h, future {self.event_future_hours}h)")
        return filtered
    
    def _sort_by_recency(self, items: List[LocationItem]) -> List[LocationItem]:
        """Sort items by recency (most recent first)"""
        if not items:
            return []
        
        def get_sort_key(item: LocationItem) -> float:
            """Get sort key: lower = more recent"""
            if not item.date:
                return float('inf')  # Items without dates go to end
            
            try:
                item_date = self._parse_date(item.date)
                if not item_date:
                    return float('inf')
                
                now = datetime.now(timezone.utc)
                # For future events, use negative hours (so they come after recent past)
                if item_date > now:
                    hours_ahead = (item_date - now).total_seconds() / 3600
                    return -hours_ahead  # Negative for future events
                else:
                    hours_ago = (now - item_date).total_seconds() / 3600
                    return hours_ago  # Positive for past events
            except:
                return float('inf')
        
        return sorted(items, key=get_sort_key)
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse various date formats to datetime"""
        if not date_str:
            return None
        
        # Common ISO 8601 formats (including UK Police API formats)
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",      # 2024-01-15T10:30:00+00:00
            "%Y-%m-%dT%H:%M:%S.%f%z",   # 2024-01-15T10:30:00.123456+00:00
            "%Y-%m-%dT%H:%M:%SZ",       # 2024-01-15T10:30:00Z
            "%Y-%m-%dT%H:%M:%S.%fZ",    # 2024-01-15T10:30:00.123456Z
            "%Y-%m-%dT%H:%M:%S",        # 2024-01-15T10:30:00
            "%Y-%m-%d %H:%M:%S",        # 2024-01-15 10:30:00
            "%Y-%m-%d",                 # 2024-01-15
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # If no timezone info, assume UTC
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except ValueError:
                continue
        
        # Try parsing as ISO format with dateutil (if available) - handles more edge cases
        try:
            from dateutil import parser
            parsed = parser.parse(date_str)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (ImportError, ValueError, TypeError) as e:
            logger.debug(f"dateutil parser failed for date '{date_str}': {e}")
            pass
        
        # Last attempt: try to parse as YYYY-MM (month format from UK Police API)
        try:
            if len(date_str) == 7 and date_str[4] == '-':  # YYYY-MM format
                year, month = map(int, date_str.split('-'))
                parsed = datetime(year, month, 1, tzinfo=timezone.utc)
                return parsed
        except (ValueError, TypeError):
            pass
        
        logger.warning(f"Could not parse date string: '{date_str}'")
        return None
    
    async def _collect_crimes(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[LocationItem]:
        """Collect crime items"""
        try:
            # Get crimes from last 3 months (we'll filter to configured days)
            # UK Police API provides monthly aggregated data (typically 1-2 months old)
            # Request 3 months to ensure we have enough data to filter from
            crime_response = await crime_service.get_crimes(
                lat=lat,
                lon=lon,
                months=3,  # Get 3 months of data (UK Police data is typically 1-2 months old)
                limit=200  # Get more to filter from
            )
            
            logger.info(f"Collected {len(crime_response.crimes)} crimes from API for location {lat}, {lon}")
            
            items = []
            for crime in crime_response.crimes:
                if crime.location and crime.location.latitude and crime.location.longitude:
                    # Generate URL to UK Police website for this location
                    crime_url = f"https://www.police.uk/pu/your-area/?q={crime.location.latitude},{crime.location.longitude}"
                    
                    # UK Police API provides monthly aggregated data
                    # Use the 'month' field (YYYY-MM) to create a proper date for filtering
                    # Set date to first day of the month for consistent filtering
                    crime_date = crime.date
                    if crime.month:
                        try:
                            # Parse month (YYYY-MM) and set to first day of month
                            year, month = map(int, crime.month.split('-'))
                            crime_date = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
                        except (ValueError, AttributeError):
                            # Fallback to original date if month parsing fails
                            pass
                    
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
                        date=crime_date,
                        url=crime_url,  # Add URL for crime location on UK Police website
                        metadata={
                            "crime_type": crime.category,
                            "month": crime.month if hasattr(crime, 'month') else None,
                            "persistent_id": crime.persistent_id if hasattr(crime, 'persistent_id') else None,
                            "original_date": crime.date  # Keep original for reference
                        }
                    ))
            
            logger.info(f"Created {len(items)} crime LocationItems from {len(crime_response.crimes)} crimes")
            return items
        except Exception as e:
            logger.error(f"Error collecting crimes for {lat}, {lon}: {e}", exc_info=True)
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

