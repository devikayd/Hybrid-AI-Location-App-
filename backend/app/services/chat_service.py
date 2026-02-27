"""
Chat Service - Core Conversational AI Logic

Implements:
1. Intent Detection - Classify user queries
2. Action Execution - Fetch relevant data
3. Response Generation - Create natural language responses

Uses existing services for data and LLM for generation.
"""

import logging
import asyncio
import uuid
import time
import re
from typing import Dict, Any, List, Tuple, Optional
from decimal import Decimal
from datetime import datetime

from app.schemas.chat import (
    IntentType, ChatRequest, ChatResponse, ChatAction,
    ConversationHistory, IntentInfo
)
from app.services.scoring_service import scoring_service
from app.services.crime_service import crime_service
from app.services.events_service import events_service
from app.services.news_service import news_service
from app.services.pois_service import pois_service
from app.services.llm_service import llm_service
from app.services.geocode_service import geocode_service
from app.core.redis import RedisCache
from app.core.config import settings

logger = logging.getLogger(__name__)


class IntentDetector:
    """
    Detects user intent from natural language queries.

    Uses keyword and phrase matching with confidence scoring.
    """

    INTENT_PATTERNS = {
        IntentType.SAFETY_QUERY: {
            "keywords": [
                "safe", "safety", "dangerous", "danger", "crime", "crimes",
                "security", "secure", "unsafe", "risky", "risk", "threat",
                "violent", "violence", "theft", "robbery", "assault"
            ],
            "phrases": [
                "is it safe", "is this safe", "how safe", "safe at night",
                "crime rate", "is the area safe", "should i worry",
                "any danger", "safe to walk", "safe for", "crime statistics"
            ]
        },
        IntentType.EVENT_SEARCH: {
            "keywords": [
                "events", "event", "concerts", "concert", "shows", "show",
                "festival", "festivals", "gig", "gigs", "performance",
                "theatre", "theater", "tickets", "entertainment"
            ],
            "phrases": [
                "events near", "events in", "happening this", "this weekend",
                "tonight", "what's on", "whats on", "upcoming events",
                "any events", "find events"
            ]
        },
        IntentType.POI_SEARCH: {
            "keywords": [
                "restaurant", "restaurants", "hotel", "hotels", "cafe", "cafes",
                "coffee", "shop", "shops", "store", "stores", "hospital",
                "pharmacy", "bank", "atm", "station", "parking", "gym",
                "supermarket", "pub", "bar", "club"
            ],
            "phrases": [
                "find", "looking for", "where is", "where are", "near me",
                "nearby", "closest", "nearest", "recommend", "best",
                "good", "top rated"
            ]
        },
        IntentType.NEWS_QUERY: {
            "keywords": [
                "news", "article", "articles", "headlines", "updates",
                "recent", "latest", "today", "happening"
            ],
            "phrases": [
                "what's new", "whats new", "recent news", "latest news",
                "any news", "news about", "read about", "in the news"
            ]
        },
        IntentType.COMPARISON: {
            "keywords": [
                "compare", "comparison", "versus", "vs", "better", "worse",
                "difference", "between"
            ],
            "phrases": [
                "compare to", "compared to", "which is better",
                "which is safer", "difference between", "vs"
            ]
        },
        IntentType.GENERAL_INFO: {
            "keywords": [
                "about", "overview", "information", "info", "describe",
                "tell", "explain", "summary", "area", "happening", "like"
            ],
            "phrases": [
                "tell me about", "what is", "what's this", "overview of",
                "information about", "describe this", "about this area",
                "what do you know", "what's happening", "whats happening",
                "things to do", "what's it like", "whats it like"
            ]
        },
        IntentType.GREETING: {
            "keywords": [
                "hello", "hi", "hey", "greetings", "morning", "afternoon",
                "evening", "howdy"
            ],
            "phrases": [
                "how are you", "good morning", "good afternoon",
                "good evening", "nice to meet"
            ]
        },
        IntentType.HELP: {
            "keywords": [
                "help", "assist", "support", "guide", "instructions"
            ],
            "phrases": [
                "what can you do", "how do i", "how can i", "help me",
                "what do you know", "your capabilities", "can you"
            ]
        },
        IntentType.TRIP_PLANNING: {
            "keywords": [
                "plan", "itinerary", "sightseeing", "explore", "discover",
                "visit", "tour", "day out", "trip"
            ],
            "phrases": [
                "plan a day", "day trip to", "places to visit", "worth visiting",
                "what should i visit", "suggest places", "plan my day",
                "day trip", "things to do", "places to see", "must see"
            ]
        },
        IntentType.SAFETY_ROUTE: {
            "keywords": [
                "safest", "avoid", "safe walk", "safe route"
            ],
            "phrases": [
                "safe to walk", "safest way to", "is it safe to go",
                "safe route to", "safe to travel", "avoid danger"
            ]
        }
    }

    def detect(self, message: str) -> Tuple[IntentType, float]:
        """
        Detect intent from user message.

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        message_lower = message.lower().strip()
        scores: Dict[IntentType, float] = {}

        for intent, patterns in self.INTENT_PATTERNS.items():
            score = 0.0

            # Check keywords (1 point each)
            for keyword in patterns["keywords"]:
                if re.search(r'\b' + re.escape(keyword) + r'\b', message_lower):
                    score += 1.0

            # Check phrases (2 points each - more specific)
            for phrase in patterns["phrases"]:
                if phrase in message_lower:
                    score += 2.0

            scores[intent] = score

        # Find best match
        if not scores or max(scores.values()) == 0:
            return IntentType.UNKNOWN, 0.0

        best_intent = max(scores, key=scores.get)
        max_score = scores[best_intent]

        # Calculate confidence (normalize to 0-1)
        # 5 points = 100% confidence
        confidence = min(1.0, max_score / 5.0)

        return best_intent, confidence


class ActionExecutor:
    """
    Executes data fetching based on detected intent.

    Maps intents to appropriate service calls.
    Uses parallel fetching for efficiency.
    """

    async def execute(
        self,
        intent: IntentType,
        lat: Optional[float],
        lon: Optional[float],
        radius_km: int = 5,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute data fetching based on intent.

        Returns:
            Dict with fetched data and metadata
        """
        if lat is None or lon is None:
            return {
                "error": "Location required",
                "data_sources": []
            }

        lat_decimal = Decimal(str(lat))
        lon_decimal = Decimal(str(lon))

        try:
            if intent == IntentType.SAFETY_QUERY:
                return await self._fetch_safety_data(lat_decimal, lon_decimal, radius_km)

            elif intent == IntentType.EVENT_SEARCH:
                return await self._fetch_event_data(lat_decimal, lon_decimal, radius_km)

            elif intent == IntentType.POI_SEARCH:
                return await self._fetch_poi_data(lat_decimal, lon_decimal, radius_km, extra_context)

            elif intent == IntentType.NEWS_QUERY:
                return await self._fetch_news_data(lat_decimal, lon_decimal, radius_km)

            elif intent == IntentType.GENERAL_INFO:
                return await self._fetch_all_data(lat_decimal, lon_decimal, radius_km)

            elif intent == IntentType.COMPARISON:
                # Comparison needs special handling with two locations
                return await self._fetch_comparison_data(extra_context)

            elif intent == IntentType.TRIP_PLANNING:
                return await self._fetch_trip_plan(lat_decimal, lon_decimal, extra_context)

            elif intent == IntentType.SAFETY_ROUTE:
                return await self._fetch_safety_data(lat_decimal, lon_decimal, radius_km)

            else:
                return {"data_sources": []}

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return {"error": str(e), "data_sources": []}

    async def _fetch_safety_data(
        self, lat: Decimal, lon: Decimal, radius_km: int
    ) -> Dict[str, Any]:
        """Fetch safety-related data"""
        tasks = [
            scoring_service.calculate_scores(lat, lon, radius_km),
            crime_service.get_crimes(lat, lon, months=12, limit=100),
            news_service.get_news(lat, lon, radius_km=50, limit=20)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "scores": results[0] if not isinstance(results[0], Exception) else None,
            "crimes": results[1] if not isinstance(results[1], Exception) else None,
            "news": results[2] if not isinstance(results[2], Exception) else None,
            "data_sources": ["UK Police API", "Safety Scoring Model", "NewsAPI"]
        }

    async def _fetch_event_data(
        self, lat: Decimal, lon: Decimal, radius_km: int
    ) -> Dict[str, Any]:
        """Fetch event data"""
        try:
            events = await events_service.get_events(
                lat, lon, within_km=radius_km, limit=20
            )
            return {
                "events": events,
                "data_sources": ["Ticketmaster API"]
            }
        except Exception as e:
            logger.error(f"Event fetch failed: {e}")
            return {"events": None, "data_sources": ["Ticketmaster API"]}

    async def _fetch_poi_data(
        self, lat: Decimal, lon: Decimal, radius_km: int,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Fetch POI data"""
        try:
            pois = await pois_service.get_pois(
                lat, lon, radius_km=radius_km, limit=50
            )
            return {
                "pois": pois,
                "data_sources": ["OpenStreetMap Overpass API"]
            }
        except Exception as e:
            logger.error(f"POI fetch failed: {e}")
            return {"pois": None, "data_sources": ["OpenStreetMap Overpass API"]}

    async def _fetch_news_data(
        self, lat: Decimal, lon: Decimal, radius_km: int
    ) -> Dict[str, Any]:
        """Fetch news data"""
        try:
            news = await news_service.get_news(
                lat, lon, radius_km=50, limit=20
            )
            return {
                "news": news,
                "data_sources": ["NewsAPI"]
            }
        except Exception as e:
            logger.error(f"News fetch failed: {e}")
            return {"news": None, "data_sources": ["NewsAPI"]}

    async def _fetch_all_data(
        self, lat: Decimal, lon: Decimal, radius_km: int
    ) -> Dict[str, Any]:
        """Fetch all data for general info"""
        tasks = [
            scoring_service.calculate_scores(lat, lon, radius_km),
            crime_service.get_crimes(lat, lon, months=12, limit=50),
            events_service.get_events(lat, lon, within_km=radius_km, limit=10),
            news_service.get_news(lat, lon, radius_km=50, limit=10),
            pois_service.get_pois(lat, lon, radius_km=radius_km, limit=30)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "scores": results[0] if not isinstance(results[0], Exception) else None,
            "crimes": results[1] if not isinstance(results[1], Exception) else None,
            "events": results[2] if not isinstance(results[2], Exception) else None,
            "news": results[3] if not isinstance(results[3], Exception) else None,
            "pois": results[4] if not isinstance(results[4], Exception) else None,
            "data_sources": [
                "UK Police API", "Safety Scoring Model",
                "Ticketmaster API", "NewsAPI", "OpenStreetMap"
            ]
        }

    async def _fetch_comparison_data(
        self, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fetch data for location comparison"""
        # For now, return placeholder - comparison requires parsing two locations
        return {
            "comparison": "Comparison feature requires two locations",
            "data_sources": []
        }

    async def _fetch_trip_plan(
        self,
        lat: Decimal,
        lon: Decimal,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a day trip itinerary and return it as chat data."""
        try:
            from app.services.trip_planner_service import trip_planner_service
            user_id = (context or {}).get("user_id", "anonymous")
            trip_plan = await trip_planner_service.plan_day_trip(
                lat=lat,
                lon=lon,
                user_id=user_id,
                max_stops=5,
                mode="foot-walking",
            )
            return {
                "trip_plan": trip_plan.model_dump(mode="json"),
                "data_sources": ["OpenStreetMap", "Safety Scoring Model", "OpenRouteService"],
            }
        except Exception as e:
            logger.error(f"Trip plan fetch failed in chat: {e}")
            return {
                "trip_plan": None,
                "error": str(e),
                "data_sources": [],
            }


class ResponseGenerator:
    """
    Generates natural language responses.

    Uses LLM for generation with template fallbacks.
    """

    SYSTEM_PROMPT = """You are a helpful location intelligence assistant for the United Kingdom.
You provide accurate, data-driven insights about locations based on real data from official sources.

Guidelines:
- Keep responses VERY concise (1-2 sentences, 30-50 words maximum)
- Be conversational and natural like a helpful friend
- Never mention data sources, APIs, or technical details
- Use British English spelling
- Get straight to the point"""

    GREETING_RESPONSES = [
        "Hello! I'm your location assistant. I can help you with information about safety, events, restaurants, and more. What would you like to know about this area?",
        "Hi there! I can tell you about local safety, upcoming events, places to eat, and recent news. What are you curious about?",
        "Hey! I'm here to help you explore this location. Ask me about safety, things to do, or places to visit!"
    ]

    HELP_RESPONSE = """I can help you with:

**Safety Information** - "Is this area safe?" "What's the crime rate?"
**Events** - "What's happening nearby?" "Any concerts this weekend?"
**Places** - "Find restaurants near me" "Where's the nearest pharmacy?"
**News** - "Any recent news about this area?"
**General Info** - "Tell me about this neighborhood"

Just ask naturally, and I'll provide data-driven insights!"""

    UNKNOWN_RESPONSE = """I'm not sure I understood that. Try asking about:
- Safety and crime statistics
- Events and entertainment
- Restaurants, shops, or other places
- Recent local news

For example: "Is this area safe?" or "What events are happening nearby?"""

    def __init__(self):
        self.llm_available = settings.LLM_PROVIDER != "none"

    async def generate(
        self,
        intent: IntentType,
        data: Dict[str, Any],
        user_message: str,
        location_name: Optional[str] = None
    ) -> Tuple[str, List[ChatAction]]:
        """
        Generate response based on intent and data.

        Returns:
            Tuple of (response_text, actions)
        """
        actions = []

        # Handle special intents without data
        if intent == IntentType.GREETING:
            import random
            return random.choice(self.GREETING_RESPONSES), actions

        if intent == IntentType.HELP:
            return self.HELP_RESPONSE, actions

        if intent == IntentType.UNKNOWN:
            return self.UNKNOWN_RESPONSE, actions

        # Check for errors
        if "error" in data and data["error"] == "Location required":
            return "I couldn't find a location in your message. Please either:\n\n1. Include a UK location in your question (e.g., 'Is Camden safe?')\n2. Select a location on the map first\n3. Ask a general question without a specific location", actions

        # Build intent-specific prompt and get response
        prompt = self._build_prompt(intent, data, user_message, location_name)

        try:
            if self.llm_available:
                response = await self._generate_with_llm(prompt)
            else:
                response = self._generate_template_response(intent, data)
        except Exception as e:
            logger.warning(f"LLM generation failed, using template: {e}")
            response = self._generate_template_response(intent, data)

        # Add actions based on intent
        actions = self._get_actions_for_intent(intent)

        # For trip planning, embed the actual stops in the action so the
        # frontend can render the itinerary on the map without a second API call
        if intent == IntentType.TRIP_PLANNING and data.get("trip_plan"):
            plan = data["trip_plan"]
            stops = plan.get("stops", [])
            if stops and actions:
                actions[0].params = {
                    "stops": stops,
                    "total_duration_text": plan.get("total_duration_text", ""),
                    "location_name": plan.get("location_name", ""),
                }

        return response, actions

    def _build_prompt(
        self,
        intent: IntentType,
        data: Dict[str, Any],
        user_message: str,
        location_name: Optional[str]
    ) -> str:
        """Build intent-specific prompt for LLM"""
        location_str = location_name or "the selected area"

        if intent == IntentType.SAFETY_QUERY:
            scores = data.get("scores", {})
            crimes = data.get("crimes")
            safety_score = scores.get('safety_score', 0.5)

            crime_info = "No crime data available"
            if crimes and hasattr(crimes, 'total_count'):
                crime_info = f"Around {crimes.total_count} incidents reported in the past year"

            # Convert score to description
            if isinstance(safety_score, (int, float)):
                if safety_score >= 0.8:
                    safety_desc = "very safe"
                elif safety_score >= 0.65:
                    safety_desc = "generally safe"
                elif safety_score >= 0.5:
                    safety_desc = "moderately safe"
                elif safety_score >= 0.35:
                    safety_desc = "has some safety concerns"
                else:
                    safety_desc = "requires extra caution"
            else:
                safety_desc = "moderately safe"

            return f"""User asked: "{user_message}"
Location: {location_str}

Safety Assessment: This area is {safety_desc}
Crime Data: {crime_info}

Respond in 1-2 short sentences (30-40 words max). Be natural and friendly, like texting a friend. No technical terms or data sources."""

        elif intent == IntentType.EVENT_SEARCH:
            events = data.get("events")
            event_count = events.total_count if events and hasattr(events, 'total_count') else 0
            event_list = ""
            if events and hasattr(events, 'events'):
                for e in events.events[:5]:
                    # Extract event name properly - it's a dict with 'text' key
                    if hasattr(e, 'name'):
                        if isinstance(e.name, dict):
                            event_name = e.name.get('text', 'Event')
                        else:
                            event_name = str(e.name)
                    else:
                        event_name = 'Event'
                    event_list += f"\n• {event_name}"

            return f"""User asked: "{user_message}"
Location: {location_str}

Found {event_count} upcoming events
{event_list if event_list else "No events currently scheduled"}

Respond in 1-2 short sentences (30-40 words max). Be enthusiastic if there are events. No data sources."""

        elif intent == IntentType.POI_SEARCH:
            pois = data.get("pois")
            poi_count = pois.total_count if pois and hasattr(pois, 'total_count') else 0

            return f"""User asked: "{user_message}"
Location: {location_str}

Found {poi_count} places in this area

Respond in 1-2 short sentences (30-40 words max). Be helpful and friendly. No data sources."""

        elif intent == IntentType.NEWS_QUERY:
            news = data.get("news")
            article_count = news.total_count if news and hasattr(news, 'total_count') else 0

            return f"""User asked: "{user_message}"
Location: {location_str}

Found {article_count} recent news articles

Respond in 1-2 short sentences (30-40 words max). Be conversational. No data sources."""

        elif intent == IntentType.GENERAL_INFO:
            scores = data.get("scores", {})
            crimes = data.get("crimes")
            events = data.get("events")
            pois = data.get("pois")
            news = data.get("news")

            safety_score = scores.get('safety_score', 0.5)
            crime_count = crimes.total_count if crimes and hasattr(crimes, 'total_count') else 0
            event_count = events.total_count if events and hasattr(events, 'total_count') else 0
            poi_count = pois.total_count if pois and hasattr(pois, 'total_count') else 0

            if isinstance(safety_score, (int, float)) and safety_score >= 0.7:
                safety_desc = "safe"
            elif isinstance(safety_score, (int, float)) and safety_score >= 0.5:
                safety_desc = "moderately safe"
            else:
                safety_desc = "requiring extra caution"

            return f"""User asked: "{user_message}"
Location: {location_str}

Complete Overview:
- Safety: {safety_desc} area ({crime_count} incidents in past year)
- Events: {event_count} upcoming events
- Amenities: {poi_count} places (restaurants, shops, services)

Respond in 2-3 short sentences (40-60 words max). Cover safety, activities, and vibe briefly. Sound like a friendly local. No data sources."""

        return f"User asked: {user_message}\nProvide a helpful response."

    async def _generate_with_llm(self, prompt: str) -> str:
        """Generate response using LLM service"""
        try:
            response = await llm_service.generate_summary(
                prompt,
                max_tokens=100,
                temperature=0.7
            )
            return response
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise

    def _generate_template_response(
        self,
        intent: IntentType,
        data: Dict[str, Any]
    ) -> str:
        """Generate template-based response when LLM is unavailable"""

        if intent == IntentType.SAFETY_QUERY:
            scores = data.get("scores", {})
            safety_score = scores.get("safety_score", 0.5)
            crimes = data.get("crimes")
            crime_count = crimes.total_count if crimes and hasattr(crimes, 'total_count') else 0

            # Convert score to human-readable assessment
            if isinstance(safety_score, str):
                safety_level = "moderately safe"
            elif safety_score >= 0.8:
                safety_level = "very safe"
            elif safety_score >= 0.65:
                safety_level = "generally safe"
            elif safety_score >= 0.5:
                safety_level = "moderately safe"
            elif safety_score >= 0.35:
                safety_level = "has some safety concerns"
            else:
                safety_level = "requires extra caution"

            # Build concise natural response
            if crime_count > 0:
                if crime_count < 50:
                    return f"This area is {safety_level} with low crime levels (around {crime_count} incidents last year). Should be fine with normal precautions!"
                elif crime_count < 150:
                    return f"This area is {safety_level} with moderate crime activity ({crime_count} incidents). Just stay aware of your surroundings."
                else:
                    return f"This area {safety_level} with {crime_count}+ incidents reported. Best to stay alert, especially at night."
            else:
                return f"This area appears to be {safety_level}. Looking good!"

        elif intent == IntentType.EVENT_SEARCH:
            events = data.get("events")
            if events and hasattr(events, 'total_count') and events.total_count > 0:
                # Extract event names properly - name is a dict with 'text' key
                event_names = []
                for e in events.events[:3]:  # Show only top 3
                    if hasattr(e, 'name'):
                        if isinstance(e.name, dict):
                            event_names.append(e.name.get('text', 'Event'))
                        else:
                            event_names.append(str(e.name))
                    else:
                        event_names.append('Event')

                event_list = "\n".join([f"• {name}" for name in event_names])

                if events.total_count == 1:
                    return f"Found 1 event: {event_names[0]}. Check the map for details!"
                elif events.total_count <= 3:
                    return f"{events.total_count} events coming up:\n{event_list}"
                else:
                    return f"{events.total_count} events found! Top picks:\n{event_list}\n\nSee the map for more."
            else:
                return "No upcoming events right now. Check back soon!"

        elif intent == IntentType.POI_SEARCH:
            pois = data.get("pois")
            if pois and hasattr(pois, 'total_count') and pois.total_count > 0:
                if pois.total_count < 10:
                    return f"Found {pois.total_count} places nearby. Check the map for details!"
                elif pois.total_count < 50:
                    return f"Plenty of options! {pois.total_count} places including restaurants, shops, and amenities. See the map."
                else:
                    return f"Vibrant area with {pois.total_count}+ places - cafes, restaurants, shops, and more. Explore the map!"
            else:
                return "Not much info on places here. Might be a quiet area."

        elif intent == IntentType.NEWS_QUERY:
            news = data.get("news")
            if news and hasattr(news, 'total_count') and news.total_count > 0:
                if news.total_count == 1:
                    return f"1 recent news story found. Check the map for details!"
                else:
                    return f"{news.total_count} recent articles about this area. See the news markers on the map."
            else:
                return "No recent news - usually a good sign! Quiet and stable."

        elif intent == IntentType.GENERAL_INFO:
            scores = data.get("scores", {})
            crimes = data.get("crimes")
            events = data.get("events")
            pois = data.get("pois")

            safety_score = scores.get("safety_score", 0.5)
            crime_count = crimes.total_count if crimes and hasattr(crimes, 'total_count') else 0
            event_count = events.total_count if events and hasattr(events, 'total_count') else 0
            poi_count = pois.total_count if pois and hasattr(pois, 'total_count') else 0

            # Safety
            if isinstance(safety_score, (int, float)) and safety_score >= 0.7:
                safety_text = "Safe area"
            elif isinstance(safety_score, (int, float)) and safety_score >= 0.5:
                safety_text = "Moderately safe"
            else:
                safety_text = "Requires caution"

            # Build concise overview
            parts = [safety_text]

            if event_count > 5:
                parts.append(f"{event_count}+ events happening")
            elif event_count > 0:
                parts.append(f"{event_count} events")

            if poi_count > 50:
                parts.append(f"plenty of amenities ({poi_count}+ places)")
            elif poi_count > 10:
                parts.append("good amenities")

            return f"{', '.join(parts)}. Check the map for details!"

        elif intent == IntentType.TRIP_PLANNING:
            plan = data.get("trip_plan")
            if plan and plan.get("stops"):
                stops = plan["stops"]
                names = ", ".join(s["name"] for s in stops[:3])
                total_text = plan.get("total_duration_text", "")
                return (
                    f"Here's a suggested day out with {len(stops)} stops — starting with {names}. "
                    f"{total_text}. Check the map for the full route!"
                )
            return "I couldn't find enough places to visit nearby. Try searching a busier area or town centre."

        elif intent == IntentType.SAFETY_ROUTE:
            scores = data.get("scores", {})
            safety_score = scores.get("safety_score", 5.0) if scores else 5.0
            if isinstance(safety_score, (int, float)):
                if safety_score >= 7:
                    return "The area generally has a good safety rating. It should be fine to walk through — just apply the usual awareness you would in any UK city."
                elif safety_score >= 5:
                    return "The area has a moderate safety rating. Walking during the day is generally fine; at night, stay on well-lit main streets and keep aware of your surroundings."
                else:
                    return "The area has a lower safety rating. Consider travelling with someone, sticking to busier streets, and avoiding late-night walks alone."
            return "Check the crime layer on the map for local incident data before heading out."

        return "I'm not quite sure how to help with that. Could you rephrase your question or ask about safety, events, or places in a specific location?"

    def _get_actions_for_intent(self, intent: IntentType) -> List[ChatAction]:
        """Get frontend actions based on intent"""
        actions = []

        if intent == IntentType.SAFETY_QUERY:
            actions.append(ChatAction(
                type="show_layer",
                target="crimes",
                params={"highlight": True}
            ))

        elif intent == IntentType.EVENT_SEARCH:
            actions.append(ChatAction(
                type="show_layer",
                target="events",
                params={"highlight": True}
            ))

        elif intent == IntentType.POI_SEARCH:
            actions.append(ChatAction(
                type="show_layer",
                target="pois",
                params={"highlight": True}
            ))

        elif intent == IntentType.NEWS_QUERY:
            actions.append(ChatAction(
                type="show_layer",
                target="news",
                params={"highlight": True}
            ))

        elif intent == IntentType.TRIP_PLANNING:
            actions.append(ChatAction(
                type="show_trip_plan",
                target="trip_route",
                params={"highlight": True}
            ))

        elif intent == IntentType.SAFETY_ROUTE:
            actions.append(ChatAction(
                type="show_layer",
                target="crimes",
                params={"highlight": True}
            ))

        return actions


class ChatService:
    """
    Main chat service orchestrating intent detection,
    action execution, and response generation.
    """

    def __init__(self):
        self.intent_detector = IntentDetector()
        self.action_executor = ActionExecutor()
        self.response_generator = ResponseGenerator()
        self.conversations: Dict[str, ConversationHistory] = {}

    async def _extract_and_geocode_location(self, message: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Extract location from message and geocode it.

        Returns:
            (lat, lon, location_name) or (None, None, None) if no location found
        """
        # Common UK cities and areas
        uk_locations = [
            "London", "Manchester", "Birmingham", "Leeds", "Liverpool", "Newcastle", "Sheffield",
            "Bristol", "Edinburgh", "Glasgow", "Cardiff", "Belfast", "Brighton", "Cambridge",
            "Oxford", "Bath", "York", "Canterbury", "Nottingham", "Leicester", "Southampton",
            "Portsmouth", "Reading", "Norwich", "Coventry", "Bradford", "Hull", "Wolverhampton",
            "Plymouth", "Stoke", "Derby", "Aberdeen", "Dundee", "Swansea", "Milton Keynes",
            "Camden", "Shoreditch", "Westminster", "Kensington", "Chelsea", "Hackney", "Islington",
            "Scotland", "Wales", "Cornwall", "Devon", "Yorkshire", "Kent", "Surrey"
        ]

        # Destination mapping — country/region names → their main city for better POI results
        destination_overrides = {
            "scotland": "Edinburgh",
            "wales": "Cardiff",
            "cornwall": "Truro",
            "devon": "Exeter",
            "yorkshire": "York",
            "kent": "Canterbury",
            "surrey": "Guildford",
        }

        message_lower = message.lower()
        found_location = None

        # Check "from X to Y" pattern FIRST to extract the destination, not the origin
        from_to_match = re.search(
            r'\bfrom\s+\w+(?:\s+\w+)?\s+to\s+(\w+(?:\s+\w+)?)', message_lower
        )
        if from_to_match:
            candidate = from_to_match.group(1).strip()
            found_location = destination_overrides.get(candidate.lower(), candidate.title())

        if not found_location:
            # Check for "to <location>" pattern (trip/day trip queries)
            to_match = re.search(
                r'(?:trip|travel|day\s+trip|plan|visit|go|heading|journey)\s+to\s+(\w+(?:\s+\w+)?)',
                message_lower
            )
            if to_match:
                candidate = to_match.group(1).strip()
                found_location = destination_overrides.get(candidate.lower(), candidate.title())

        if not found_location:
            # Scan known UK cities/regions (case-insensitive)
            for location in uk_locations:
                if location.lower() in message_lower:
                    found_location = destination_overrides.get(location.lower(), location)
                    break

        if not found_location:
            # Fallback regex patterns
            location_phrases = [
                r"in (\w+(?:\s+\w+)?)",
                r"at (\w+(?:\s+\w+)?)",
                r"near (\w+(?:\s+\w+)?)",
                r"around (\w+(?:\s+\w+)?)",
                r"about (\w+(?:\s+\w+)?)"
            ]

            for pattern in location_phrases:
                match = re.search(pattern, message_lower)
                if match:
                    potential_location = match.group(1).title()
                    if len(potential_location) > 2:
                        found_location = potential_location
                        break

        if not found_location:
            return None, None, None

        # Geocode the found location
        try:
            logger.info(f"Attempting to geocode extracted location: {found_location}")
            geocode_result = await geocode_service.geocode(found_location, limit=1, countrycodes="gb")

            if geocode_result.results and len(geocode_result.results) > 0:
                result = geocode_result.results[0]
                logger.info(f"Successfully geocoded {found_location} to ({result.lat}, {result.lon})")
                return float(result.lat), float(result.lon), result.display_name
            else:
                logger.warning(f"No geocoding results for {found_location}")
                return None, None, None

        except Exception as e:
            logger.error(f"Geocoding failed for {found_location}: {e}")
            return None, None, None

    async def process_message(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        """
        Process a chat message and return response.

        Main entry point for chat functionality.
        """
        start_time = time.time()

        # Get or create conversation
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Extract location from message if not provided
        lat = request.lat
        lon = request.lon
        location_name = request.location_name

        if lat is None or lon is None:
            logger.info("No coordinates provided, attempting to extract location from message")
            lat, lon, location_name = await self._extract_and_geocode_location(request.message)

            if lat and lon:
                logger.info(f"Extracted and geocoded location: {location_name} ({lat}, {lon})")

        # Detect intent
        intent, confidence = self.intent_detector.detect(request.message)
        logger.info(f"Detected intent: {intent} (confidence: {confidence:.2f})")

        # For trip planning, always try to extract the destination from the message.
        # This overrides the map coordinates so "plan a trip to Scotland" goes to
        # Scotland, not wherever the map is currently centred.
        if intent == IntentType.TRIP_PLANNING:
            extracted_lat, extracted_lon, extracted_name = await self._extract_and_geocode_location(request.message)
            if extracted_lat and extracted_lon:
                lat = extracted_lat
                lon = extracted_lon
                location_name = extracted_name
                logger.info(f"Trip planning: overriding coords with extracted destination: {location_name} ({lat}, {lon})")

        # Execute action to fetch data
        data = await self.action_executor.execute(
            intent=intent,
            lat=lat,
            lon=lon,
            radius_km=5,
            extra_context=request.context
        )

        # Generate response
        response_text, actions = await self.response_generator.generate(
            intent=intent,
            data=data,
            user_message=request.message,
            location_name=request.location_name
        )

        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000

        return ChatResponse(
            response=response_text,
            intent=intent,
            confidence=confidence,
            data_sources=data.get("data_sources", []),
            actions=actions,
            conversation_id=conversation_id,
            processing_time_ms=round(processing_time, 2)
        )

    def get_supported_intents(self) -> List[IntentInfo]:
        """Get list of supported intents with examples"""
        return [
            IntentInfo(
                intent=IntentType.SAFETY_QUERY,
                description="Questions about area safety and crime",
                example_queries=["Is this area safe?", "What's the crime rate?", "Safe at night?"],
                data_sources=["UK Police API", "Safety Scoring Model"]
            ),
            IntentInfo(
                intent=IntentType.EVENT_SEARCH,
                description="Search for events and entertainment",
                example_queries=["What's happening nearby?", "Events this weekend", "Any concerts?"],
                data_sources=["Ticketmaster API"]
            ),
            IntentInfo(
                intent=IntentType.POI_SEARCH,
                description="Find places and amenities",
                example_queries=["Find restaurants", "Hotels near me", "Where's the pharmacy?"],
                data_sources=["OpenStreetMap Overpass API"]
            ),
            IntentInfo(
                intent=IntentType.NEWS_QUERY,
                description="Recent news about the area",
                example_queries=["Any recent news?", "What's happening here?", "Local headlines"],
                data_sources=["NewsAPI"]
            ),
            IntentInfo(
                intent=IntentType.GENERAL_INFO,
                description="General information about the area",
                example_queries=["Tell me about this area", "Overview", "What's this place like?"],
                data_sources=["All data sources"]
            )
        ]


# Service singleton
chat_service = ChatService()
