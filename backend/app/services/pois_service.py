"""
Overpass API service for Points of Interest (POI) data
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
import math
import asyncio

from app.core.config import settings
from app.core.redis import poi_cache
from app.schemas.pois import POIData, POIResponse, POISummary, POITags
from app.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)


class POIsService:
    """Overpass API service for POI data"""
    
    def __init__(self):
        self.base_url = settings.OVERPASS_BASE_URL
        self.timeout = settings.OVERPASS_TIMEOUT
    
    async def get_pois(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 5,
        types: Optional[str] = None,
        limit: int = 100
    ) -> POIResponse:
        """
        Get POI data for a location with Redis caching
        """
        # Generate cache key
        cache_key = poi_cache.generate_key(
            "pois",
            lat=str(lat),
            lon=str(lon),
            radius_km=radius_km,
            types=types or "all",
            limit=limit
        )
        
        # Check cache first
        cached_result = await poi_cache.get(cache_key)
        if cached_result:
            logger.info(f"POI cache hit for location: {lat}, {lon}")
            return POIResponse(**cached_result)
        
        # Fetch from Overpass API
        try:
            pois = await self._fetch_pois_from_api(lat, lon, radius_km, types, limit)
            
            response = POIResponse(
                lat=lat,
                lon=lon,
                pois=pois,
                cached=False,
                source="overpass",
                total_count=len(pois)
            )
            
            # Cache the result
            await poi_cache.set(cache_key, response.dict())
            logger.info(f"POI cache set for location: {lat}, {lon}")
            
            return response
            
        except Exception as e:
            logger.error(f"POI data fetch failed for {lat}, {lon}: {e}")
            # Return empty response instead of raising exception to allow other APIs to work
            logger.warning(f"Returning empty POI list due to error - other APIs will continue")
            return POIResponse(
                lat=lat,
                lon=lon,
                pois=[],
                cached=False,
                source="overpass",
                total_count=0
            )
    
    async def get_poi_summary(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 5,
        types: Optional[str] = None,
        limit: int = 100
    ) -> POISummary:
        """
        Get POI summary statistics for a location
        """
        # Generate cache key
        cache_key = poi_cache.generate_key(
            "poi_summary",
            lat=str(lat),
            lon=str(lon),
            radius_km=radius_km,
            types=types or "all",
            limit=limit
        )
        
        # Check cache first
        cached_result = await poi_cache.get(cache_key)
        if cached_result:
            logger.info(f"POI summary cache hit for location: {lat}, {lon}")
            return POISummary(**cached_result)
        
        # Get POI data
        poi_response = await self.get_pois(lat, lon, radius_km, types, limit)
        
        # Generate summary
        summary = self._generate_summary(poi_response)
        
        # Cache the summary
        await poi_cache.set(cache_key, summary.dict())
        logger.info(f"POI summary cache set for location: {lat}, {lon}")
        
        return summary
    
    async def _fetch_pois_from_api(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int,
        types: Optional[str],
        limit: int
    ) -> List[POIData]:
        """Fetch POI data from Overpass API with retry logic and optimized queries"""
        
        # Reduce radius if too large to prevent timeout (max 5km for complex queries)
        effective_radius_km = min(radius_km, 5)
        radius_m = effective_radius_km * 1000
        
        # Try multiple Overpass instances for better reliability
        overpass_instances = [
            "https://overpass-api.de/api",  # Primary
            "https://overpass.openstreetmap.ru/api",  # Alternative 1
            "https://overpass.kumi.systems/api",  # Alternative 2
        ]
        
        last_error = None
        
        for instance_url in overpass_instances:
            try:
                # Build optimized Overpass QL query
        query = self._build_overpass_query(lat, lon, radius_m, types)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                            f"{instance_url}/interpreter",
                    data=query,
                    headers={"Content-Type": "text/plain"}
                )
                response.raise_for_status()
                
                data = response.json()
                elements = data.get("elements", [])
                
                # Convert to our schema and limit results
                pois = []
                for element in elements[:limit]:
                    try:
                        poi = self._convert_element_to_poi(element, lat, lon)
                        if poi:
                            pois.append(poi)
                    except Exception as e:
                        logger.warning(f"Invalid POI element: {e}")
                        continue
                
                        logger.info(f"Fetched {len(pois)} POIs from {instance_url} for location {lat}, {lon}")
                return pois
                
            except httpx.TimeoutException:
                        logger.warning(f"Timeout from {instance_url}, trying next instance...")
                        last_error = ExternalAPIException("Overpass", f"Request timeout from {instance_url}")
                        continue
            except httpx.HTTPStatusError as e:
                        if e.response.status_code == 504:
                            logger.warning(f"504 Gateway Timeout from {instance_url}, trying next instance...")
                            last_error = ExternalAPIException("Overpass", f"HTTP 504 Gateway Timeout from {instance_url}")
                            continue
                        else:
                raise ExternalAPIException("Overpass", f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                        logger.warning(f"Request error from {instance_url}: {e}, trying next instance...")
                        last_error = ExternalAPIException("Overpass", f"Request error: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Error with {instance_url}: {e}")
                last_error = e
                continue
        
        # If all instances failed, try a simplified query as fallback
        logger.info("All Overpass instances failed, trying simplified query...")
        try:
            return await self._fetch_pois_simplified(lat, lon, radius_m, limit)
        except Exception as fallback_error:
            logger.error(f"Simplified query also failed: {fallback_error}")
            if last_error:
                raise last_error
            raise ExternalAPIException("Overpass", "All Overpass instances failed")
    
    async def _fetch_pois_simplified(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_m: int,
        limit: int
    ) -> List[POIData]:
        """Fetch POIs with a very simple query - only essential types"""
        # Very simple query with only most common POI types
        simple_query = f"""
        [out:json][timeout:10];
        (
          node["amenity"~"^(restaurant|cafe|bar|pub|hospital|pharmacy|bank|atm)$"](around:{radius_m},{lat},{lon});
          node["tourism"="attraction"](around:{radius_m},{lat},{lon});
        );
        out center meta;
        """
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.base_url}/interpreter",
                data=simple_query,
                headers={"Content-Type": "text/plain"}
            )
            response.raise_for_status()
            
            data = response.json()
            elements = data.get("elements", [])
            
            pois = []
            for element in elements[:limit]:
                try:
                    poi = self._convert_element_to_poi(element, lat, lon)
                    if poi:
                        pois.append(poi)
                except Exception as e:
                    logger.warning(f"Invalid POI element: {e}")
                    continue
            
            logger.info(f"Fetched {len(pois)} POIs with simplified query")
            return pois
    
    def _build_overpass_query(self, lat: Decimal, lon: Decimal, radius_m: int, types: Optional[str]) -> str:
        """Build Overpass QL query - simplified to reduce timeout risk"""
        
        # Reduced POI types to prevent timeouts - focus on most common types
        if not types:
            # Priority order: Tourist attractions, Amenities, Essential amenities, Shops
            # Priority 1: Tourist attractions
            tourism_types = [
                "attraction", "museum", "gallery", "zoo", "theme_park",
                "viewpoint", "monument", "memorial", "artwork", "castle"
            ]
            
            # Priority 2 & 3: Amenities (includes essential and non-essential)
            amenity_types = [
                "restaurant", "cafe", "bar", "pub", "fast_food",
                "cinema", "theatre", "library", "community_centre",
                "hospital", "pharmacy", "bank", "atm", "fuel",
                "police", "fire_station", "post_office",
                "school", "university", "college", "kindergarten",
                "hotel", "hostel", "guesthouse"
            ]
            
            # Priority 4: Shops
            shop_types = [
                "supermarket", "convenience", "clothes", "electronics",
                "books", "bakery", "butcher", "florist", "jewelry"
            ]
        else:
            amenity_types = types.split(",")[:10]  # Limit to 10 types max
            tourism_types = []
            shop_types = []
        
        # Build the query - use union to combine results efficiently
        # Priority order: Tourist attractions first, then amenities, then shops
        query_parts = []
        
        # Priority 1: Tourism POIs (tourist attractions) - fetch more of these
        for tourism in tourism_types[:10]:  # Max 10 tourism types
            query_parts.append(f'node["tourism"="{tourism.strip()}"](around:{radius_m},{lat},{lon});')
        
        # Priority 2 & 3: Amenity POIs (includes essential and non-essential)
        for amenity in amenity_types[:15]:  # Max 15 amenity types
            query_parts.append(f'node["amenity"="{amenity.strip()}"](around:{radius_m},{lat},{lon});')
        
        # Priority 4: Shop POIs
        for shop in shop_types[:8]:  # Max 8 shop types
            query_parts.append(f'node["shop"="{shop.strip()}"](around:{radius_m},{lat},{lon});')
        
        # Combine all queries - use union for efficiency and limit total query size
        # Limit total query parts to prevent timeout (increased to 25 for more POI types)
        if len(query_parts) > 25:
            query_parts = query_parts[:25]
            logger.warning(f"Query too complex, limiting to 25 POI types to prevent timeout")
        
        # Use shorter timeout in query itself
        query = f"""
        [out:json][timeout:10];
        (
            {''.join(query_parts)}
        );
        out center meta;
        """
        
        return query.strip()
    
    def _convert_element_to_poi(self, element: Dict[str, Any], center_lat: Decimal, center_lon: Decimal) -> Optional[POIData]:
        """Convert Overpass element to POI data"""
        try:
            # Get coordinates
            lat = Decimal(str(element.get("lat", 0)))
            lon = Decimal(str(element.get("lon", 0)))
            
            if lat == 0 and lon == 0:
                return None
            
            # Calculate distance from center
            distance = self._calculate_distance(center_lat, center_lon, lat, lon)
            
            # Get tags
            tags_data = element.get("tags", {})
            tags = POITags(
                name=tags_data.get("name"),
                amenity=tags_data.get("amenity"),
                tourism=tags_data.get("tourism"),
                shop=tags_data.get("shop"),
                cuisine=tags_data.get("cuisine"),
                opening_hours=tags_data.get("opening_hours"),
                phone=tags_data.get("phone"),
                website=tags_data.get("website"),
                wheelchair=tags_data.get("wheelchair"),
                addr_street=tags_data.get("addr:street"),
                addr_city=tags_data.get("addr:city"),
                addr_postcode=tags_data.get("addr:postcode")
            )
            
            # Determine POI type
            poi_type = tags.amenity or tags.tourism or tags.shop or "other"
            
            return POIData(
                id=element.get("id", 0),
                lat=lat,
                lon=lon,
                type=poi_type,
                tags=tags,
                distance=distance
            )
            
        except Exception as e:
            logger.warning(f"Error converting POI element: {e}")
            return None
    
    def _calculate_distance(self, lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
        """Calculate distance between two points in kilometers"""
        try:
            # Haversine formula
            R = 6371  # Earth's radius in kilometers
            
            lat1_rad = math.radians(float(lat1))
            lon1_rad = math.radians(float(lon1))
            lat2_rad = math.radians(float(lat2))
            lon2_rad = math.radians(float(lon2))
            
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            
            a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            
            return R * c
        except Exception:
            return 0.0
    
    def _generate_summary(self, poi_response: POIResponse) -> POISummary:
        """Generate POI summary statistics"""
        types = {}
        amenities = {}
        
        for poi in poi_response.pois:
            # Count by type
            poi_type = poi.type
            types[poi_type] = types.get(poi_type, 0) + 1
            
            # Count by amenity
            amenity = poi.tags.amenity
            if amenity:
                amenities[amenity] = amenities.get(amenity, 0) + 1
        
        return POISummary(
            lat=poi_response.lat,
            lon=poi_response.lon,
            total_pois=poi_response.total_count,
            types=types,
            amenities=amenities,
            cached=poi_response.cached,
            source=poi_response.source
        )


# Service instance
pois_service = POIsService()






