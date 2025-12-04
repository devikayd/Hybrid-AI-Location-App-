"""
Clustering service for hotspot detection using DBSCAN
"""

import logging
from typing import List, Dict, Any, Tuple
from decimal import Decimal
import asyncio
import math

try:
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import StandardScaler
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from app.core.config import settings
from app.core.redis import geocode_cache
from app.schemas.summary import HotspotData, HotspotsResponse
from app.services.crime_service import crime_service
from app.services.events_service import events_service
from app.services.news_service import news_service
from app.services.pois_service import pois_service
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class ClusteringService:
    """Service for detecting hotspots using DBSCAN clustering"""
    
    def __init__(self):
        self.cache_ttl = 1800  # 30 minutes cache for hotspots
    
    async def detect_hotspots(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 5,
        min_samples: int = 3,
        eps_km: float = 0.5
    ) -> HotspotsResponse:
        """
        Detect hotspots using DBSCAN clustering
        """
        # Generate cache key
        cache_key = geocode_cache.generate_key(
            "hotspots",
            lat=str(lat),
            lon=str(lon),
            radius_km=radius_km,
            min_samples=min_samples,
            eps_km=eps_km
        )
        
        # Check cache first
        cached_result = await geocode_cache.get(cache_key)
        if cached_result:
            logger.info(f"Hotspots cache hit for location: {lat}, {lon}")
            return HotspotsResponse(**cached_result)
        
        try:
            # Collect data from all services
            data_points = await self._collect_data_points(lat, lon, radius_km)
            
            if len(data_points) < min_samples:
                # Not enough data points for clustering
                hotspots = []
                geojson = self._create_empty_geojson()
            else:
                # Perform clustering
                hotspots = await self._cluster_data_points(data_points, min_samples, eps_km)
                geojson = self._create_hotspots_geojson(hotspots)
            
            response = HotspotsResponse(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                hotspots=hotspots,
                geojson=geojson,
                cached=False,
                source="dbscan_clustering"
            )
            
            # Cache the result
            await geocode_cache.set(cache_key, response.dict())
            logger.info(f"Hotspots cache set for location: {lat}, {lon}")
            
            return response
            
        except Exception as e:
            logger.error(f"Hotspot detection failed for {lat}, {lon}: {e}")
            raise AppException(f"Hotspot detection failed: {str(e)}")
    
    async def _collect_data_points(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[Dict[str, Any]]:
        """Collect data points from all services"""
        data_points = []
        
        # Collect data concurrently
        tasks = [
            self._collect_crime_points(lat, lon, radius_km),
            self._collect_event_points(lat, lon, radius_km),
            self._collect_news_points(lat, lon, radius_km),
            self._collect_poi_points(lat, lon, radius_km)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                data_points.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Data collection failed: {result}")
        
        return data_points
    
    async def _collect_crime_points(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[Dict[str, Any]]:
        """Collect crime data points"""
        try:
            crime_response = await crime_service.get_crimes(
                lat=lat,
                lon=lon,
                months=12,
                limit=200
            )
            
            points = []
            for crime in crime_response.crimes:
                if crime.location and crime.location.latitude and crime.location.longitude:
                    try:
                        crime_lat = Decimal(crime.location.latitude)
                        crime_lon = Decimal(crime.location.longitude)
                        
                        # Check if within radius
                        distance = self._calculate_distance(lat, lon, crime_lat, crime_lon)
                        if distance <= radius_km:
                            points.append({
                                "lat": float(crime_lat),
                                "lon": float(crime_lon),
                                "type": "crime",
                                "subtype": crime.category,
                                "id": str(crime.id),
                                "title": crime.category,
                                "description": f"Crime: {crime.category}",
                                "weight": 1.0
                            })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid crime coordinates: {e}")
                        continue
            
            return points
        except Exception as e:
            logger.warning(f"Crime points collection failed: {e}")
            return []
    
    async def _collect_event_points(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[Dict[str, Any]]:
        """Collect event data points"""
        try:
            event_response = await events_service.get_events(
                lat=lat,
                lon=lon,
                within_km=radius_km,
                limit=200
            )
            
            points = []
            for event in event_response.events:
                if event.venue and event.venue.latitude and event.venue.longitude:
                    try:
                        event_lat = Decimal(event.venue.latitude)
                        event_lon = Decimal(event.venue.longitude)
                        
                        points.append({
                            "lat": float(event_lat),
                            "lon": float(event_lon),
                            "type": "event",
                            "subtype": "free" if event.is_free else "paid",
                            "id": event.id,
                            "title": event.name.get("text", "Event"),
                            "description": f"Event: {event.name.get('text', 'Event')}",
                            "weight": 1.5 if event.is_free else 1.0
                        })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid event coordinates: {e}")
                        continue
            
            return points
        except Exception as e:
            logger.warning(f"Event points collection failed: {e}")
            return []
    
    async def _collect_news_points(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[Dict[str, Any]]:
        """Collect news data points (using search center as proxy)"""
        try:
            news_response = await news_service.get_news(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=100
            )
            
            points = []
            for i, article in enumerate(news_response.articles):
                # Use search center with small random offset for news articles
                offset_lat = float(lat) + (i % 10 - 5) * 0.001  # Small random offset
                offset_lon = float(lon) + (i % 10 - 5) * 0.001
                
                points.append({
                    "lat": offset_lat,
                    "lon": offset_lon,
                    "type": "news",
                    "subtype": "positive" if article.sentiment and article.sentiment > 0.1 else "negative" if article.sentiment and article.sentiment < -0.1 else "neutral",
                    "id": f"news_{i}",
                    "title": article.title,
                    "description": f"News: {article.title}",
                    "weight": 0.8
                })
            
            return points
        except Exception as e:
            logger.warning(f"News points collection failed: {e}")
            return []
    
    async def _collect_poi_points(self, lat: Decimal, lon: Decimal, radius_km: int) -> List[Dict[str, Any]]:
        """Collect POI data points"""
        try:
            poi_response = await pois_service.get_pois(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=200
            )
            
            points = []
            for poi in poi_response.pois:
                points.append({
                    "lat": float(poi.lat),
                    "lon": float(poi.lon),
                    "type": "poi",
                    "subtype": poi.type,
                    "id": str(poi.id),
                    "title": poi.tags.name or f"{poi.type.title()} POI",
                    "description": f"POI: {poi.tags.name or poi.type}",
                    "weight": 1.2
                })
            
            return points
        except Exception as e:
            logger.warning(f"POI points collection failed: {e}")
            return []
    
    async def _cluster_data_points(
        self, 
        data_points: List[Dict[str, Any]], 
        min_samples: int, 
        eps_km: float
    ) -> List[HotspotData]:
        """Cluster data points using DBSCAN"""
        
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, using simple clustering")
            return self._simple_clustering(data_points, min_samples, eps_km)
        
        try:
            # Prepare data for clustering
            coordinates = np.array([[point["lat"], point["lon"]] for point in data_points])
            
            # Convert eps from km to approximate degrees (rough approximation)
            eps_degrees = eps_km / 111.0  # 1 degree ≈ 111 km
            
            # Apply DBSCAN clustering
            dbscan = DBSCAN(eps=eps_degrees, min_samples=min_samples, metric='euclidean')
            cluster_labels = dbscan.fit_predict(coordinates)
            
            # Process clusters
            hotspots = []
            unique_labels = set(cluster_labels)
            
            for cluster_id in unique_labels:
                if cluster_id == -1:  # Skip noise points
                    continue
                
                # Get points in this cluster
                cluster_points = [data_points[i] for i, label in enumerate(cluster_labels) if label == cluster_id]
                
                if len(cluster_points) >= min_samples:
                    hotspot = self._create_hotspot(cluster_points, cluster_id, eps_km)
                    hotspots.append(hotspot)
            
            return hotspots
            
        except Exception as e:
            logger.warning(f"DBSCAN clustering failed: {e}")
            return self._simple_clustering(data_points, min_samples, eps_km)
    
    def _simple_clustering(
        self, 
        data_points: List[Dict[str, Any]], 
        min_samples: int, 
        eps_km: float
    ) -> List[HotspotData]:
        """Simple clustering fallback when scikit-learn is not available"""
        hotspots = []
        processed = set()
        
        for i, point in enumerate(data_points):
            if i in processed:
                continue
            
            # Find nearby points
            cluster_points = [point]
            cluster_indices = {i}
            
            for j, other_point in enumerate(data_points):
                if j in processed or j == i:
                    continue
                
                distance = self._calculate_distance(
                    Decimal(point["lat"]), Decimal(point["lon"]),
                    Decimal(other_point["lat"]), Decimal(other_point["lon"])
                )
                
                if distance <= eps_km:
                    cluster_points.append(other_point)
                    cluster_indices.add(j)
            
            # Create hotspot if enough points
            if len(cluster_points) >= min_samples:
                hotspot = self._create_hotspot(cluster_points, len(hotspots), eps_km)
                hotspots.append(hotspot)
                processed.update(cluster_indices)
        
        return hotspots
    
    def _create_hotspot(self, cluster_points: List[Dict[str, Any]], cluster_id: int, eps_km: float) -> HotspotData:
        """Create hotspot data from cluster points"""
        # Calculate cluster center
        center_lat = sum(point["lat"] for point in cluster_points) / len(cluster_points)
        center_lon = sum(point["lon"] for point in cluster_points) / len(cluster_points)
        
        # Calculate cluster radius
        max_distance = 0
        for point in cluster_points:
            distance = self._calculate_distance(
                Decimal(center_lat), Decimal(center_lon),
                Decimal(point["lat"]), Decimal(point["lon"])
            )
            max_distance = max(max_distance, distance)
        
        radius_m = max_distance * 1000  # Convert to meters
        
        # Count items by type
        item_types = {}
        total_weight = 0
        
        for point in cluster_points:
            item_type = point["type"]
            item_types[item_type] = item_types.get(item_type, 0) + 1
            total_weight += point["weight"]
        
        # Calculate intensity (weighted density)
        intensity = total_weight / len(cluster_points)
        
        return HotspotData(
            lat=Decimal(str(center_lat)),
            lon=Decimal(str(center_lon)),
            radius_m=radius_m,
            intensity=intensity,
            item_count=len(cluster_points),
            item_types=item_types,
            cluster_id=cluster_id
        )
    
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
    
    def _create_hotspots_geojson(self, hotspots: List[HotspotData]) -> Dict[str, Any]:
        """Create GeoJSON representation of hotspots"""
        features = []
        
        for hotspot in hotspots:
            feature = {
                "type": "Feature",
                "properties": {
                    "cluster_id": hotspot.cluster_id,
                    "intensity": hotspot.intensity,
                    "item_count": hotspot.item_count,
                    "radius_m": hotspot.radius_m,
                    "item_types": hotspot.item_types
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(hotspot.lon), float(hotspot.lat)]
                }
            }
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
    
    def _create_empty_geojson(self) -> Dict[str, Any]:
        """Create empty GeoJSON"""
        return {
            "type": "FeatureCollection",
            "features": []
        }


# Service instance
clustering_service = ClusteringService()






