"""
Events service for Ticketmaster and Eventbrite APIs
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime

from app.core.config import settings
from app.core.redis import event_cache
from app.schemas.events import EventData, EventResponse, EventSummary, EventVenue
from app.core.exceptions import ExternalAPIException
from app.core.circuit_breaker import ticketmaster_breaker, eventbrite_breaker, CircuitOpenError

logger = logging.getLogger(__name__)


class EventsService:
    """Events service for Ticketmaster and Eventbrite APIs"""
    
    def __init__(self):
        self.ticketmaster_base_url = settings.TICKETMASTER_BASE_URL
        self.eventbrite_base_url = settings.EVENTBRITE_BASE_URL
        self.timeout = settings.TICKETMASTER_TIMEOUT
        self.ticketmaster_api_key = settings.TICKETMASTER_API_KEY
        self.eventbrite_token = settings.EVENTBRITE_TOKEN
    
    async def get_events(
        self,
        lat: Decimal,
        lon: Decimal,
        within_km: int = 10,
        query: Optional[str] = None,
        limit: int = 50
    ) -> EventResponse:
        """
        Get events data for a location with Redis caching
        Uses Ticketmaster
        """
        # Generate cache key
        cache_key = event_cache.generate_key(
            "events",
            lat=str(lat),
            lon=str(lon),
            within_km=within_km,
            query=query or "all",
            limit=limit
        )
        
        # Check cache first
        cached_result = await event_cache.get(cache_key)
        if cached_result:
            logger.info(f"Events cache hit for location: {lat}, {lon}")
            return EventResponse(**cached_result)
        
        # Try Ticketmaster first, then Eventbrite
        events = []
        source = "none"
        
        if self.ticketmaster_api_key:
            try:
                events = await self._fetch_events_from_ticketmaster(lat, lon, within_km, query, limit)
                source = "ticketmaster"
                logger.info(f"Fetched {len(events)} events from Ticketmaster")
            except Exception as e:
                logger.warning(f"Ticketmaster fetch failed: {e}")
        
        # Fallback to Eventbrite
        if not events and self.eventbrite_token:
            try:
                events = await self._fetch_events_from_eventbrite(lat, lon, within_km, query, limit)
                source = "eventbrite"
                logger.info(f"Fetched {len(events)} events from Eventbrite")
            except Exception as e:
                logger.warning(f"Eventbrite fetch failed: {e}")
        
        if not events:
            if not self.ticketmaster_api_key and not self.eventbrite_token:
                raise ExternalAPIException("Events", "No API keys configured for Ticketmaster or Eventbrite")
            raise ExternalAPIException("Events", "Failed to fetch events from both providers")
        
        response = EventResponse(
            lat=lat,
            lon=lon,
            events=events,
            cached=False,
            source=source,
            total_count=len(events)
        )
        
        # Cache the result
        await event_cache.set(cache_key, response.dict())
        logger.info(f"Events cache set for location: {lat}, {lon}")
        
        return response
    
    async def get_event_summary(
        self,
        lat: Decimal,
        lon: Decimal,
        within_km: int = 10,
        query: Optional[str] = None,
        limit: int = 50
    ) -> EventSummary:
        """Get event summary statistics for a location"""
        # Get events first
        event_response = await self.get_events(lat, lon, within_km, query, limit)
        
        # Calculate summary statistics
        total_events = len(event_response.events)
        free_events = sum(1 for e in event_response.events if e.is_free)
        paid_events = total_events - free_events
        online_events = sum(1 for e in event_response.events if e.online_event)
        
        # Count by category
        categories: Dict[str, int] = {}
        for event in event_response.events:
            cat = event.category_id or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1
        
        return EventSummary(
            lat=lat,
            lon=lon,
            total_events=total_events,
            free_events=free_events,
            paid_events=paid_events,
            online_events=online_events,
            categories=categories,
            cached=event_response.cached,
            source=event_response.source
        )
    
    async def _fetch_events_from_ticketmaster(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int,
        query: Optional[str],
        limit: int
    ) -> List[EventData]:
        """Fetch events from Ticketmaster Discovery API"""
        # Convert km to miles (Ticketmaster uses miles)
        radius_miles = int(radius_km * 0.621371)
        
        params = {
            "apikey": self.ticketmaster_api_key,
            "latlong": f"{lat},{lon}",
            "radius": radius_miles,
            "unit": "miles",
            "size": min(limit, 200),
            "sort": "date,asc"
        }
        
        if query:
            params["keyword"] = query

        # Check circuit breaker before making request
        if ticketmaster_breaker.is_open:
            logger.warning("Circuit breaker open for Ticketmaster API")
            raise ExternalAPIException("Ticketmaster", "Circuit breaker open - API temporarily unavailable")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Use circuit breaker to protect the API call
                async with ticketmaster_breaker:
                    response = await client.get(
                        f"{self.ticketmaster_base_url}/events.json",
                        params=params
                    )
                    response.raise_for_status()

                data = response.json()
                embedded = data.get("_embedded", {})
                events_data = embedded.get("events", [])

                # Convert to our schema
                events = []
                for item in events_data[:limit]:
                    try:
                        event = self._convert_ticketmaster_to_event(item)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"Invalid Ticketmaster event: {e}")
                        continue

                return events

            except CircuitOpenError:
                raise ExternalAPIException("Ticketmaster", "Circuit breaker rejected request")
            except httpx.TimeoutException:
                raise ExternalAPIException("Ticketmaster", "Request timeout")
            except httpx.HTTPStatusError as e:
                raise ExternalAPIException("Ticketmaster", f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                raise ExternalAPIException("Ticketmaster", f"Request error: {str(e)}")
    
    async def _fetch_events_from_eventbrite(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int,
        query: Optional[str],
        limit: int
    ) -> List[EventData]:
        """Fetch events from Eventbrite API (legacy fallback)"""
        # Convert km to meters for Eventbrite
        radius_m = radius_km * 1000
        
        headers = {
            "Authorization": f"Bearer {self.eventbrite_token}"
        }
        
        params = {
            "location.latitude": str(lat),
            "location.longitude": str(lon),
            "location.within": f"{radius_m}m",
            "expand": "venue,category",
            "status": "live"
        }
        
        if query:
            params["q"] = query

        # Check circuit breaker before making request
        if eventbrite_breaker.is_open:
            logger.warning("Circuit breaker open for Eventbrite API")
            return []  # Return empty instead of raising to allow fallback

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Use circuit breaker to protect the API call
                async with eventbrite_breaker:
                    # Eventbrite search endpoint is not be available
                    response = await client.get(
                        f"{self.eventbrite_base_url}/events/search/",
                        headers=headers,
                        params=params
                    )

                    if response.status_code == 404:
                        logger.warning("Eventbrite search endpoint not available (404)")
                        return []

                    response.raise_for_status()

                data = response.json()
                events_data = data.get("events", [])

                # Convert to our schema
                events = []
                for item in events_data[:limit]:
                    try:
                        event = self._convert_eventbrite_to_event(item)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"Invalid Eventbrite event: {e}")
                        continue

                return events

            except CircuitOpenError:
                logger.warning("Circuit breaker rejected Eventbrite request")
                return []
            except httpx.TimeoutException:
                raise ExternalAPIException("Eventbrite", "Request timeout")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning("Eventbrite API endpoint not available")
                    return []
                raise ExternalAPIException("Eventbrite", f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                raise ExternalAPIException("Eventbrite", f"Request error: {str(e)}")
    
    def _convert_ticketmaster_to_event(self, item: Dict[str, Any]) -> Optional[EventData]:
        """Convert Ticketmaster event to EventData schema"""
        try:
            event_id = item.get("id", "")
            name = item.get("name", "")
            url = item.get("url", "")
            
            # Dates
            dates = item.get("dates", {})
            start_date = dates.get("start", {})
            end_date = dates.get("end", {})
            
            # Venue
            venues = item.get("_embedded", {}).get("venues", [])
            venue = None
            if venues:
                v = venues[0]
                location = v.get("location", {})
                venue = EventVenue(
                    id=v.get("id"),
                    name=v.get("name"),
                    latitude=str(location.get("latitude", "")),
                    longitude=str(location.get("longitude", "")),
                    address=v.get("address", {})
                )
            
            # Pricing
            price_ranges = item.get("priceRanges", [])
            is_free = False
            if price_ranges:
                min_price = price_ranges[0].get("min", 0)
                is_free = min_price == 0
            else:
                # Check if there's a "free" classification
                classifications = item.get("classifications", [])
                for cls in classifications:
                    if cls.get("segment", {}).get("name", "").lower() == "free":
                        is_free = True
                        break
            
            # Categories - Ticketmaster provides segment names directly
            classifications = item.get("classifications", [])
            category_id = None
            category_name = None
            if classifications:
                segment = classifications[0].get("segment", {})
                category_id = segment.get("id")
                category_name = segment.get("name")  # Ticketmaster provides readable name
            
            return EventData(
                id=event_id,
                name={"text": name},
                description={"text": item.get("info", "")} if item.get("info") else None,
                start={"utc": start_date.get("dateTime", "")} if start_date.get("dateTime") else None,
                end={"utc": end_date.get("dateTime", "")} if end_date.get("dateTime") else None,
                url=url,
                status=item.get("status", {}).get("code", ""),
                currency=price_ranges[0].get("currency", "USD") if price_ranges else None,
                online_event=False,  # Ticketmaster doesn't clearly indicate online events
                is_free=is_free,
                venue=venue,
                category_id=category_name if category_name else (str(category_id) if category_id else None),  # Use name if available, otherwise ID
                subcategory_id=None,
                format_id=None
            )
        except Exception as e:
            logger.error(f"Error converting Ticketmaster event: {e}")
            return None
    
    def _convert_eventbrite_to_event(self, item: Dict[str, Any]) -> Optional[EventData]:
        """Convert Eventbrite event to EventData schema"""
        try:
            return EventData(
                id=item.get("id", ""),
                name={"text": item.get("name", {}).get("text", "")},
                description=item.get("description"),
                start=item.get("start"),
                end=item.get("end"),
                url=item.get("url"),
                status=item.get("status"),
                currency=item.get("currency"),
                online_event=item.get("online_event", False),
                is_free=item.get("is_free", False),
                venue=EventVenue(**item.get("venue", {})) if item.get("venue") else None,
                category_id=item.get("category_id"),
                subcategory_id=item.get("subcategory_id"),
                format_id=item.get("format_id")
            )
        except Exception as e:
            logger.error(f"Error converting Eventbrite event: {e}")
            return None


# Global service instance
events_service = EventsService()




