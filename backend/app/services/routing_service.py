"""
Routing Service — OpenRouteService (ORS) API wrapper

Calculates travel time and distance between two geographic points.
Falls back to a Haversine-based estimate if ORS is unavailable.
"""

import asyncio
import logging
import math
from decimal import Decimal
from typing import Optional

import httpx

from app.core.config import settings
from app.core.circuit_breaker import ors_breaker, CircuitOpenError
from app.core.redis import route_cache

logger = logging.getLogger(__name__)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in kilometres between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _format_duration(seconds: int) -> str:
    """Convert seconds into a human-readable string, e.g. '12 min walk'."""
    if seconds < 60:
        return f"{seconds} sec"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}min" if mins else f"{hours}h"


def _haversine_estimate(lat1: float, lon1: float, lat2: float, lon2: float, mode: str) -> dict:
    """
    Estimate travel time using straight-line distance when ORS is unavailable.
    Walking speed: 5 km/h  |  Driving speed: 40 km/h (urban estimate)
    """
    dist_km = _haversine_km(lat1, lon1, lat2, lon2)
    speed_kmh = 5.0 if "foot" in mode else 40.0
    duration_sec = int((dist_km / speed_kmh) * 3600)
    mode_word = "walk" if "foot" in mode else "drive"
    return {
        "duration_seconds": duration_sec,
        "distance_metres": round(dist_km * 1000, 1),
        "duration_text": f"{_format_duration(duration_sec)} {mode_word} (est.)",
        "estimated": True,
    }


class RoutingService:
    """
    Wraps the OpenRouteService Directions API to calculate travel time
    and distance between two points.

    Falls back to a Haversine straight-line estimate when:
    - ORS API key is not configured
    - ORS circuit breaker is open
    - ORS returns an error

    Responses are cached in Redis for 30 minutes to avoid repeated
    API calls for the same origin/destination pair.
    """

    def __init__(self):
        self.base_url = settings.ORS_BASE_URL
        self.api_key = settings.ORS_API_KEY
        self.timeout = settings.ORS_TIMEOUT

    async def get_travel_time(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        mode: str = "foot-walking",
    ) -> dict:
        """
        Return travel time and distance between two points.

        Args:
            origin_lat/lon: Starting coordinates
            dest_lat/lon: Destination coordinates
            mode: ORS profile — 'foot-walking', 'driving-car', 'cycling-regular'

        Returns:
            {duration_seconds, distance_metres, duration_text, estimated}
        """
        # Round to 4 decimal places for stable cache keys (~11m precision)
        o_lat = round(float(origin_lat), 4)
        o_lon = round(float(origin_lon), 4)
        d_lat = round(float(dest_lat), 4)
        d_lon = round(float(dest_lon), 4)

        cache_key = route_cache.generate_key(
            "travel", o_lat=o_lat, o_lon=o_lon, d_lat=d_lat, d_lon=d_lon, mode=mode
        )

        cached = await route_cache.get(cache_key)
        if cached:
            logger.debug(f"Route cache hit: {o_lat},{o_lon} → {d_lat},{d_lon}")
            return cached

        result = await self._fetch_from_ors(o_lat, o_lon, d_lat, d_lon, mode)
        await route_cache.set(cache_key, result)
        return result

    async def get_multi_stop_times(
        self,
        stops: list[dict],
        mode: str = "foot-walking",
    ) -> list[dict]:
        """
        Calculate travel times for consecutive stop pairs in parallel.

        Args:
            stops: List of {'lat': float, 'lon': float} dicts (ordered)
            mode: Travel mode

        Returns:
            List of travel time dicts, one per consecutive pair.
            First element is always None (no travel to reach first stop).
        """
        if len(stops) < 2:
            return [None] * len(stops)

        tasks = []
        for i in range(1, len(stops)):
            prev, curr = stops[i - 1], stops[i]
            tasks.append(
                self.get_travel_time(
                    prev["lat"], prev["lon"],
                    curr["lat"], curr["lon"],
                    mode,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        travel_times = [None]  # first stop has no travel time
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Route calculation failed for a stop pair: {r}")
                travel_times.append(None)
            else:
                travel_times.append(r)
        return travel_times

    async def _fetch_from_ors(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
        mode: str,
    ) -> dict:
        """Call ORS Directions API, falling back to Haversine on any error."""
        if not self.api_key:
            logger.debug("ORS API key not configured — using Haversine estimate")
            return _haversine_estimate(lat1, lon1, lat2, lon2, mode)

        try:
            async with ors_breaker:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/v2/directions/{mode}",
                        json={
                            "coordinates": [[lon1, lat1], [lon2, lat2]],
                            "units": "m",
                        },
                        headers={
                            "Authorization": self.api_key,
                            "Content-Type": "application/json",
                        },
                    )
                    response.raise_for_status()
                    data = response.json()

            route = data["routes"][0]["summary"]
            duration_sec = int(route["duration"])
            distance_m = round(route["distance"], 1)
            mode_word = "walk" if "foot" in mode else "drive"
            return {
                "duration_seconds": duration_sec,
                "distance_metres": distance_m,
                "duration_text": f"{_format_duration(duration_sec)} {mode_word}",
                "estimated": False,
            }

        except CircuitOpenError:
            logger.warning("ORS circuit open — using Haversine estimate")
            return _haversine_estimate(lat1, lon1, lat2, lon2, mode)
        except httpx.TimeoutException:
            logger.warning("ORS request timed out — using Haversine estimate")
            return _haversine_estimate(lat1, lon1, lat2, lon2, mode)
        except Exception as e:
            logger.warning(f"ORS request failed ({e}) — using Haversine estimate")
            return _haversine_estimate(lat1, lon1, lat2, lon2, mode)


routing_service = RoutingService()
