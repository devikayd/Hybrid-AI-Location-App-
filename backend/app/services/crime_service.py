"""
UK Police API service for crime data
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import asyncio

from app.core.config import settings
from app.core.redis import crime_cache
from app.schemas.crime import CrimeData, CrimeResponse, CrimeSummary
from app.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)


class CrimeService:
    """UK Police API service for crime data"""
    
    def __init__(self):
        self.base_url = settings.POLICE_API_BASE_URL
        self.timeout = settings.POLICE_API_TIMEOUT
    
    async def get_crimes(
        self,
        lat: Decimal,
        lon: Decimal,
        months: int = 12,
        category: Optional[str] = None,
        limit: int = 100
    ) -> CrimeResponse:
        """
        Get crime data for a location with Redis caching
        """
        # Generate cache key
        cache_key = crime_cache.generate_key(
            "crimes",
            lat=str(lat),
            lon=str(lon),
            months=months,
            category=category or "all",
            limit=limit
        )
        
        # Check cache first
        cached_result = await crime_cache.get(cache_key)
        if cached_result:
            logger.info(f"Crime cache hit for location: {lat}, {lon}")
            return CrimeResponse(**cached_result)
        
        # Fetch from UK Police API
        try:
            crimes = await self._fetch_crimes_from_api(lat, lon, months, category, limit)
            
            response = CrimeResponse(
                lat=lat,
                lon=lon,
                crimes=crimes,
                cached=False,
                source="uk_police",
                total_count=len(crimes)
            )
            
            # Cache the result
            await crime_cache.set(cache_key, response.dict())
            logger.info(f"Crime cache set for location: {lat}, {lon}")
            
            return response
            
        except Exception as e:
            logger.error(f"Crime data fetch failed for {lat}, {lon}: {e}")
            raise ExternalAPIException("UK Police", str(e))
    
    async def get_crime_summary(
        self,
        lat: Decimal,
        lon: Decimal,
        months: int = 12,
        category: Optional[str] = None,
        limit: int = 100
    ) -> CrimeSummary:
        """
        Get crime summary statistics for a location
        """
        # Generate cache key
        cache_key = crime_cache.generate_key(
            "crime_summary",
            lat=str(lat),
            lon=str(lon),
            months=months,
            category=category or "all",
            limit=limit
        )
        
        # Check cache first
        cached_result = await crime_cache.get(cache_key)
        if cached_result:
            logger.info(f"Crime summary cache hit for location: {lat}, {lon}")
            return CrimeSummary(**cached_result)
        
        # Get crime data
        crime_response = await self.get_crimes(lat, lon, months, category, limit)
        
        # Generate summary
        summary = self._generate_summary(crime_response)
        
        # Cache the summary
        await crime_cache.set(cache_key, summary.dict())
        logger.info(f"Crime summary cache set for location: {lat}, {lon}")
        
        return summary
    
    async def _fetch_crimes_from_api(
        self,
        lat: Decimal,
        lon: Decimal,
        months: int,
        category: Optional[str],
        limit: int
    ) -> List[CrimeData]:
        """Fetch crime data from UK Police API"""
        
        # Generate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        params = {
            "lat": str(lat),
            "lng": str(lon),
            "date": f"{start_date.strftime('%Y-%m')}"
        }
        
        if category:
            params["category"] = category
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/crimes-street/all-crime",
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Convert to our schema and limit results
                crimes = []
                for item in data[:limit]:
                    try:
                        crime = CrimeData(
                            id=item.get("id", 0),
                            category=item.get("category", "Unknown"),
                            location_type=item.get("location_type"),
                            location=item.get("location"),
                            context=item.get("context"),
                            outcome_status=item.get("outcome_status"),
                            persistent_id=item.get("persistent_id"),
                            date=item.get("date", ""),
                            month=item.get("month", "")
                        )
                        crimes.append(crime)
                    except Exception as e:
                        logger.warning(f"Invalid crime data: {e}")
                        continue
                
                logger.info(f"Fetched {len(crimes)} crimes for location {lat}, {lon}")
                return crimes
                
            except httpx.TimeoutException:
                raise ExternalAPIException("UK Police", "Request timeout")
            except httpx.HTTPStatusError as e:
                raise ExternalAPIException("UK Police", f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                raise ExternalAPIException("UK Police", f"Request error: {str(e)}")
    
    def _generate_summary(self, crime_response: CrimeResponse) -> CrimeSummary:
        """Generate crime summary statistics"""
        categories = {}
        months = {}
        
        for crime in crime_response.crimes:
            # Count by category
            category = crime.category
            categories[category] = categories.get(category, 0) + 1
            
            # Count by month
            month = crime.month
            months[month] = months.get(month, 0) + 1
        
        return CrimeSummary(
            lat=crime_response.lat,
            lon=crime_response.lon,
            total_crimes=crime_response.total_count,
            categories=categories,
            months=months,
            cached=crime_response.cached,
            source=crime_response.source
        )


# Service instance
crime_service = CrimeService()






