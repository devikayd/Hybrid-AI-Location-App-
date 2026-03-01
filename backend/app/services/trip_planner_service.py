"""
Trip Planner Service

Generates a safety-aware day trip itinerary for a given location.

Pipeline:
1. Fetch all events and POIs within 5km of the origin using location_data_service
2. Filter out items that are not worth visiting (no name, low-value category)
3. Rank candidates by: type priority + area safety/popularity + user preference match
4. Order selected stops using nearest-neighbour (greedy TSP approximation)
5. Calculate walking travel times between consecutive stops via routing_service
6. Return assembled TripPlanResponse
"""

import asyncio
import logging
import math
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.redis import route_cache
from app.schemas.trip_planner import TripPlanResponse, TripStop
from app.schemas.user_interaction import LocationItem, LocationDataResponse
from app.services.location_data_service import location_data_service
from app.services.scoring_service import scoring_service
from app.services.routing_service import routing_service

logger = logging.getLogger(__name__)

# POI/event types that are worth visiting as trip stops
VISITABLE_POI_TYPES = {
    "tourism", "historic", "leisure", "arts", "entertainment",
    "sport", "amenity", "natural",
}

# Low-value amenity subtypes to exclude from trip suggestions
EXCLUDED_SUBTYPES = {
    "parking", "parking_space", "parking_entrance", "bicycle_parking",
    "fuel", "atm", "bank", "pharmacy", "post_office", "post_box",
    "waste_basket", "waste_disposal", "recycling", "toilets",
    "bus_station", "taxi", "car_rental", "car_wash",
    "vending_machine", "charging_station",
    "fast_food",  # keep restaurants, exclude fast food chains
}

# Priority score by POI/event category (higher = shown first)
CATEGORY_PRIORITY: dict[str, int] = {
    "tourism": 10,
    "attraction": 10,
    "museum": 9,
    "historic": 9,
    "monument": 9,
    "gallery": 8,
    "arts_centre": 8,
    "theatre": 8,
    "cinema": 7,
    "leisure": 7,
    "park": 7,
    "nature_reserve": 7,
    "viewpoint": 7,
    "event": 6,
    "entertainment": 6,
    "sport": 5,
    "restaurant": 4,
    "cafe": 4,
    "pub": 3,
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class TripPlannerService:
    """
    Builds a safety-aware day trip itinerary for a given UK location.

    Reuses:
    - location_data_service — for fetching nearby POIs and events
    - scoring_service — for area-level safety and popularity scores
    - routing_service — for walking travel times between stops
    """

    SEARCH_RADIUS_KM = 5

    async def plan_day_trip(
        self,
        lat: Decimal,
        lon: Decimal,
        user_id: str,
        max_stops: int = 5,
        mode: str = "foot-walking",
        db: Optional[Session] = None,
    ) -> TripPlanResponse:
        """
        Generate a day trip itinerary around the given location.

        Args:
            lat/lon: Centre of the search area
            user_id: Used to personalise stop ranking (optional)
            max_stops: Maximum number of stops (2–8)
            mode: Travel mode for routing (default: foot-walking)
            db: Optional database session for preference lookup

        Returns:
            TripPlanResponse with ordered stops and travel times
        """
        cache_key = route_cache.generate_key(
            "trip_plan",
            lat=str(round(float(lat), 3)),
            lon=str(round(float(lon), 3)),
            max_stops=max_stops,
            mode=mode,
        )

        cached = await route_cache.get(cache_key)
        if cached:
            logger.info(f"Trip plan cache hit for {lat},{lon}")
            return TripPlanResponse(**cached)

        # Fetch location data and area scores in parallel
        location_data_task = location_data_service.get_location_data(
            lat, lon, radius_km=self.SEARCH_RADIUS_KM, user_id=user_id
        )
        scores_task = scoring_service.calculate_scores(lat, lon, radius_km=self.SEARCH_RADIUS_KM)

        location_data, area_scores = await asyncio.gather(
            location_data_task, scores_task, return_exceptions=True
        )

        if isinstance(location_data, Exception):
            logger.error(f"Failed to fetch location data: {location_data}")
            location_data = LocationDataResponse(
                lat=lat, lon=lon, events=[], pois=[], news=[], crimes=[], total_items=0
            )

        if isinstance(area_scores, Exception):
            logger.warning(f"Failed to fetch area scores, using defaults: {area_scores}")
            area_scores = {"safety_score": 5.0, "popularity_score": 5.0}

        safety_score = float(area_scores.get("safety_score", 5.0))
        popularity_score = float(area_scores.get("popularity_score", 5.0))
        location_name = getattr(location_data, "location_name", None) or "this area"

        # Build candidate pool from events and POIs only
        candidates = self._get_candidates(location_data)

        if not candidates:
            logger.warning(f"No visitable candidates found near {lat},{lon}")
            return TripPlanResponse(
                origin_lat=lat,
                origin_lon=lon,
                location_name=location_name,
                stops=[],
                total_duration_seconds=0,
                total_duration_text="No stops found",
                travel_mode=mode,
                cached=False,
                total_stops=0,
            )

        # Get user preferences if available
        user_prefs = await self._get_user_prefs(user_id, db)

        # Rank and select top stops
        selected = self._rank_and_select(
            candidates, safety_score, popularity_score, user_prefs, max_stops
        )

        # Order stops by nearest-neighbour starting from origin
        ordered = self._nearest_neighbour_order(selected, float(lat), float(lon))

        # Calculate travel times between consecutive stops
        stop_coords = [{"lat": float(s.lat), "lon": float(s.lon)} for s in ordered]
        travel_times = await routing_service.get_multi_stop_times(stop_coords, mode)

        # Assemble final itinerary
        stops = self._build_stops(ordered, travel_times, safety_score, popularity_score)

        total_seconds = sum(
            (t["duration_seconds"] for t in travel_times if t is not None), 0
        )
        total_text = self._format_total_duration(total_seconds)

        response = TripPlanResponse(
            origin_lat=lat,
            origin_lon=lon,
            location_name=location_name,
            stops=stops,
            total_duration_seconds=total_seconds,
            total_duration_text=total_text,
            travel_mode=mode,
            cached=False,
            total_stops=len(stops),
        )

        await route_cache.set(cache_key, response.model_dump(mode="json"))
        logger.info(f"Trip plan generated: {len(stops)} stops near {lat},{lon}")
        return response

    # private helpers

    def _get_candidates(self, location_data: LocationDataResponse) -> list[LocationItem]:
        """
        Return POIs and events that are worth visiting.
        Excludes crime reports, news articles, unnamed items, and low-value amenities.
        """
        candidates: list[LocationItem] = []

        for item in location_data.pois:
            if not item.title or item.title.lower() in {"unknown", "none", ""}:
                continue
            subtype = (item.subtype or "").lower()
            if subtype in EXCLUDED_SUBTYPES:
                continue
            candidates.append(item)

        for item in location_data.events:
            if not item.title or item.title.lower() in {"unknown", "none", ""}:
                continue
            candidates.append(item)

        return candidates

    def _rank_and_select(
        self,
        candidates: list[LocationItem],
        safety_score: float,
        popularity_score: float,
        user_prefs: dict,
        max_stops: int,
    ) -> list[LocationItem]:
        """
        Score each candidate and return the top `max_stops` items.

        Score = category_priority (0–10)
              + (popularity_score / 10) * 3
              + preference_bonus (0 or 1)
        """
        scored = []
        for item in candidates:
            cat = (item.category or item.subtype or item.type or "").lower()
            type_score = CATEGORY_PRIORITY.get(cat, 2)

            pop_bonus = (popularity_score / 10.0) * 3.0

            pref_bonus = 0.0
            if item.type in user_prefs.get("preferred_types", []):
                pref_bonus += 1.0
            if item.category and item.category in user_prefs.get("preferred_categories", []):
                pref_bonus += 0.5

            total = type_score + pop_bonus + pref_bonus
            scored.append((total, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate by proximity — avoid two stops within 50m of each other
        selected: list[LocationItem] = []
        for _, item in scored:
            if len(selected) >= max_stops:
                break
            too_close = any(
                _haversine_km(
                    float(item.lat), float(item.lon),
                    float(s.lat), float(s.lon)
                ) < 0.05
                for s in selected
            )
            if not too_close:
                selected.append(item)

        return selected

    def _nearest_neighbour_order(
        self,
        items: list[LocationItem],
        origin_lat: float,
        origin_lon: float,
    ) -> list[LocationItem]:
        """
        Order stops using nearest-neighbour heuristic starting from origin.
        Each step picks the closest unvisited stop.
        """
        if not items:
            return []

        unvisited = list(items)
        ordered: list[LocationItem] = []
        cur_lat, cur_lon = origin_lat, origin_lon

        while unvisited:
            nearest = min(
                unvisited,
                key=lambda s: _haversine_km(cur_lat, cur_lon, float(s.lat), float(s.lon)),
            )
            ordered.append(nearest)
            unvisited.remove(nearest)
            cur_lat, cur_lon = float(nearest.lat), float(nearest.lon)

        return ordered

    def _build_stops(
        self,
        ordered: list[LocationItem],
        travel_times: list[Optional[dict]],
        area_safety: float,
        area_popularity: float,
    ) -> list[TripStop]:
        """Assemble TripStop objects from ordered items and travel time data."""
        stops: list[TripStop] = []
        for i, item in enumerate(ordered):
            tt = travel_times[i]
            stops.append(
                TripStop(
                    stop_index=i + 1,
                    name=item.title,
                    type=item.type,
                    category=item.category or item.subtype or item.type,
                    lat=item.lat,
                    lon=item.lon,
                    safety_score=round(area_safety, 1),
                    popularity_score=round(area_popularity, 1),
                    description=item.description,
                    travel_time_from_previous=tt["duration_seconds"] if tt else None,
                    travel_time_text=tt["duration_text"] if tt else None,
                    distance_from_previous=tt["distance_metres"] if tt else None,
                    url=item.url,
                )
            )
        return stops

    @staticmethod
    def _format_total_duration(total_seconds: int) -> str:
        if total_seconds == 0:
            return "No travel time calculated"
        minutes = round(total_seconds / 60)
        if minutes < 60:
            return f"{minutes} min total walking"
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}min total walking" if mins else f"{hours}h total walking"

    async def _get_user_prefs(self, user_id: str, db: Optional[Session]) -> dict:
        """Load user preferences if a DB session is available."""
        if not db or not user_id:
            return {"preferred_types": [], "preferred_categories": [], "preferred_subtypes": []}
        try:
            from app.services.user_interaction_service import user_interaction_service
            return await user_interaction_service.get_user_preferences(user_id, db)
        except Exception as e:
            logger.warning(f"Could not load user preferences for trip planner: {e}")
            return {"preferred_types": [], "preferred_categories": [], "preferred_subtypes": []}


trip_planner_service = TripPlannerService()
