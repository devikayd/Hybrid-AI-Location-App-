"""
Geocoding service using Nominatim API
"""

import httpx
import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal
import asyncio

from app.core.config import settings
from app.core.redis import geocode_cache
from app.schemas.geocode import GeocodeResult, GeocodeResponse
from app.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)


class GeocodeService:
    """Geocoding service using Nominatim API"""
    
    def __init__(self):
        self.base_url = settings.NOMINATIM_BASE_URL
        self.timeout = settings.NOMINATIM_TIMEOUT
        self.contact_email = settings.CONTACT_EMAIL
    
    async def geocode(
        self, 
        query: str, 
        limit: int = 1, 
        countrycodes: str = "gb"
    ) -> GeocodeResponse:
        """
        Geocode a query using Nominatim API with Redis caching
        """
        # Generate cache key
        cache_key = geocode_cache.generate_key(
            "geocode",
            query=query.lower().strip(),
            limit=limit,
            countrycodes=countrycodes
        )
        
        # Check cache first
        cached_result = await geocode_cache.get(cache_key)
        if cached_result:
            logger.info(f"Geocoding cache hit for query: {query}")
            return GeocodeResponse(**cached_result)
        
        # Fetch from Nominatim API
        try:
            results = await self._fetch_from_nominatim(query, limit, countrycodes)
            
            response = GeocodeResponse(
                query=query,
                results=results,
                cached=False,
                source="nominatim"
            )
            
            # Cache the result
            await geocode_cache.set(cache_key, response.dict())
            logger.info(f"Geocoding cache set for query: {query}")
            
            return response
            
        except Exception as e:
            logger.error(f"Geocoding failed for query '{query}': {e}")
            raise ExternalAPIException("Nominatim", str(e))
    
    async def _fetch_from_nominatim(
        self, 
        query: str, 
        limit: int, 
        countrycodes: str
    ) -> List[GeocodeResult]:
        """Fetch geocoding results from Nominatim API"""
        
        params = {
            "q": query,
            "format": "json",
            "limit": limit,
            "countrycodes": countrycodes,
            "addressdetails": 1,
            "extratags": 1,
            "email": self.contact_email,
            "dedupe": 1
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/search",
                    params=params,
                    headers={
                        "User-Agent": f"{settings.APP_NAME}/{settings.VERSION} ({self.contact_email})"
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                if not data:
                    logger.warning(f"No results found for query: {query}")
                    return []
                
                # Convert to our schema
                results = []
                for item in data:
                    try:
                        result = GeocodeResult(
                            lat=Decimal(str(item["lat"])),
                            lon=Decimal(str(item["lon"])),
                            display_name=item["display_name"],
                            place_id=item.get("place_id"),
                            osm_type=item.get("osm_type"),
                            osm_id=item.get("osm_id"),
                            importance=item.get("importance"),
                            boundingbox=item.get("boundingbox")
                        )
                        results.append(result)
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Invalid geocoding result: {e}")
                        continue
                
                logger.info(f"Geocoding successful for query '{query}': {len(results)} results")
                return results
                
            except httpx.TimeoutException:
                raise ExternalAPIException("Nominatim", "Request timeout")
            except httpx.HTTPStatusError as e:
                raise ExternalAPIException("Nominatim", f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                raise ExternalAPIException("Nominatim", f"Request error: {str(e)}")
    
    async def reverse_geocode(
        self, 
        lat: Decimal, 
        lon: Decimal
    ) -> Optional[GeocodeResult]:
        """
        Reverse geocode coordinates to address
        """
        cache_key = geocode_cache.generate_key(
            "reverse_geocode",
            lat=str(lat),
            lon=str(lon)
        )
        
        # Check cache
        cached_result = await geocode_cache.get(cache_key)
        if cached_result:
            return GeocodeResult(**cached_result)
        
        params = {
            "lat": str(lat),
            "lon": str(lon),
            "format": "json",
            "addressdetails": 1,
            "email": self.contact_email
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/reverse",
                    params=params,
                    headers={
                        "User-Agent": f"{settings.APP_NAME}/{settings.VERSION} ({self.contact_email})"
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                if not data:
                    return None
                
                result = GeocodeResult(
                    lat=Decimal(str(data["lat"])),
                    lon=Decimal(str(data["lon"])),
                    display_name=data["display_name"],
                    place_id=data.get("place_id"),
                    osm_type=data.get("osm_type"),
                    osm_id=data.get("osm_id"),
                    importance=data.get("importance"),
                    boundingbox=data.get("boundingbox")
                )
                
                # Cache the result
                await geocode_cache.set(cache_key, result.dict())
                
                return result
                
            except Exception as e:
                logger.error(f"Reverse geocoding failed for {lat}, {lon}: {e}")
                raise ExternalAPIException("Nominatim", str(e))


# Service instance
geocode_service = GeocodeService()






