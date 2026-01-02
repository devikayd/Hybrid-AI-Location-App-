"""
Chat service for processing user queries with location context
"""

import logging
import re
import json
import asyncio
import uuid
from typing import Dict, Any, List, Tuple, Optional
from decimal import Decimal

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatContext,
    MapContext,
    UiAction,
    Citation,
    MarkerData,
    SetViewportAction,
    FitBoundsAction,
    HighlightResultsAction,
    ClearHighlightsAction,
    RefreshDataAction,
    SetFiltersAction,
)
from app.services.crime_service import crime_service
from app.services.events_service import events_service
from app.services.news_service import news_service
from app.services.pois_service import pois_service
from app.services.llm_service import llm_service
from app.services.geocode_service import geocode_service
from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class ChatService:
    """Service for processing chat queries with location context"""

    def __init__(self):
        self.max_context_items = 50
        self.default_radius_km = 5.0

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """
        Process a chat request and return response with UI actions
        """
        try:
            # Generate conversation ID if not provided
            conversation_id = request.conversation_id or str(uuid.uuid4())[:8]

            # Calculate radius from bbox
            radius_km = self._calculate_radius_from_bbox(request.context.map)

            # Collect location context
            context_data = await self._collect_context(request.context.map, radius_km)

            # Get location name
            location_name = await self._get_location_name(
                request.context.map.center.lat,
                request.context.map.center.lng
            )

            # Check if LLM is available
            llm_available = settings.LLM_PROVIDER.lower() not in ["none", ""]

            if llm_available:
                try:
                    # Build LLM prompt
                    prompt = self._build_prompt(
                        message=request.message,
                        location_name=location_name,
                        context=context_data,
                        map_context=request.context.map
                    )

                    # Call LLM
                    await llm_service.initialize()
                    raw_response = await llm_service.generate_summary(
                        prompt=prompt,
                        max_tokens=1000,
                        temperature=0.7
                    )

                    # Parse response to extract text and actions
                    assistant_text, ui_actions = self._parse_llm_response(raw_response)
                except Exception as e:
                    logger.warning(f"LLM call failed, using fallback: {e}")
                    assistant_text, ui_actions = self._generate_fallback_response(
                        request.message, location_name, context_data
                    )
            else:
                # Use rule-based fallback when LLM is disabled
                logger.info("LLM disabled, using fallback response")
                assistant_text, ui_actions = self._generate_fallback_response(
                    request.message, location_name, context_data
                )

            # Extract citations from context
            citations = self._extract_citations(context_data, assistant_text)

            return ChatResponse(
                assistant_text=assistant_text,
                ui_actions=ui_actions,
                citations=citations if citations else None,
                markers=None,
                cards=None,
                conversation_id=conversation_id
            )

        except Exception as e:
            import traceback
            logger.error(f"Chat processing failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return graceful error response
            return ChatResponse(
                assistant_text=f"I'm sorry, I encountered an issue processing your request. Please try again.",
                ui_actions=[],
                conversation_id=request.conversation_id or str(uuid.uuid4())[:8]
            )

    def _generate_fallback_response(
        self,
        message: str,
        location_name: str,
        context: Dict[str, Any]
    ) -> Tuple[str, List[UiAction]]:
        """Generate a rule-based response when LLM is not available"""
        message_lower = message.lower()
        ui_actions: List[UiAction] = []

        # Format crime categories
        crime_cats = sorted(context["crimes"]["categories"].items(), key=lambda x: -x[1])[:3]
        crime_text = ", ".join([f"{cat} ({count})" for cat, count in crime_cats]) if crime_cats else "no data"

        # Format POI amenities
        poi_amenities = sorted(context["pois"]["amenities"].items(), key=lambda x: -x[1])[:3]
        poi_text = ", ".join([f"{amenity} ({count})" for amenity, count in poi_amenities]) if poi_amenities else "various places"

        # Check for safety/crime related questions
        if any(word in message_lower for word in ["safe", "safety", "crime", "dangerous", "secure"]):
            crime_count = context["crimes"]["count"]
            if crime_count == 0:
                response = f"Based on available data for {location_name}, there are no recorded crime incidents in the past 12 months. This appears to be a relatively safe area."
            elif crime_count < 50:
                response = f"In {location_name}, there have been {crime_count} recorded incidents in the past 12 months. The most common types are: {crime_text}. This is a moderate level of activity for the area."
            else:
                response = f"In {location_name}, there have been {crime_count} recorded incidents in the past 12 months. Top categories: {crime_text}. Exercise normal precautions in this area."

        # Check for restaurant/food related questions
        elif any(word in message_lower for word in ["restaurant", "food", "eat", "dining", "cafe", "coffee"]):
            restaurants = [p for p in context["pois"]["items"] if p.tags and p.tags.amenity in ["restaurant", "cafe", "fast_food", "bar", "pub"]]
            if restaurants:
                names = [(p.tags.name if p.tags and p.tags.name else p.tags.amenity) for p in restaurants[:5]]
                response = f"Near {location_name}, I found {len(restaurants)} dining options. Some places include: {', '.join(filter(None, names))}."
                # Add highlight action for restaurants
                poi_ids = [f"poi_{p.id}" for p in restaurants[:5]]
                if poi_ids:
                    ui_actions.append(HighlightResultsAction(payload={"ids": poi_ids}))
            else:
                response = f"I couldn't find specific restaurant data for {location_name}. The area has {context['pois']['count']} points of interest including: {poi_text}."

        # Check for events
        elif any(word in message_lower for word in ["event", "happening", "concert", "show", "activity", "things to do"]):
            event_count = context["events"]["count"]
            if event_count > 0:
                event_names = context["events"]["names"][:3]
                response = f"There are {event_count} upcoming events near {location_name}. Some highlights: {', '.join(event_names) if event_names else 'various local events'}."
            else:
                response = f"I don't have information about upcoming events near {location_name} at the moment. Try checking local event listings."

        # Check for POI/attractions
        elif any(word in message_lower for word in ["attraction", "visit", "see", "tourist", "interesting", "nearby", "around"]):
            poi_count = context["pois"]["count"]
            response = f"Around {location_name}, there are {poi_count} points of interest. Top categories: {poi_text}."

        # Check for news
        elif any(word in message_lower for word in ["news", "happening", "recent", "update"]):
            news_count = context["news"]["count"]
            sentiment = context["news"]["sentiment"]
            if news_count > 0:
                response = f"There are {news_count} recent news articles about {location_name}. Overall sentiment is {sentiment}."
            else:
                response = f"No recent news coverage found for {location_name}."

        # Default response
        else:
            response = f"Here's what I know about {location_name}:\n\n"
            response += f"• Crime: {context['crimes']['count']} incidents recorded ({crime_text})\n"
            response += f"• Events: {context['events']['count']} upcoming\n"
            response += f"• Places: {context['pois']['count']} points of interest ({poi_text})\n"
            response += f"• News: {context['news']['count']} recent articles (sentiment: {context['news']['sentiment']})\n\n"
            response += "Feel free to ask about safety, restaurants, events, or attractions!"

        return response, ui_actions

    def _calculate_radius_from_bbox(self, map_context: MapContext) -> float:
        """Calculate approximate radius from bounding box"""
        west, south, east, north = map_context.bbox
        # Approximate radius as half the diagonal
        lat_diff = abs(north - south)
        lng_diff = abs(east - west)
        # Rough conversion: 1 degree lat ≈ 111km
        radius_km = max(lat_diff * 111 / 2, lng_diff * 111 * 0.7 / 2)
        return min(max(radius_km, 1.0), 50.0)  # Clamp between 1-50km

    async def _collect_context(self, map_context: MapContext, radius_km: float) -> Dict[str, Any]:
        """Collect context data from all services concurrently"""
        lat = Decimal(str(map_context.center.lat))
        lng = Decimal(str(map_context.center.lng))

        context = {
            "crimes": {"count": 0, "items": [], "categories": {}},
            "events": {"count": 0, "items": [], "names": []},
            "news": {"count": 0, "items": [], "sentiment": "neutral"},
            "pois": {"count": 0, "items": [], "amenities": {}}
        }

        # Collect data concurrently
        tasks = [
            self._collect_crimes(lat, lng, context),
            self._collect_events(lat, lng, radius_km, context),
            self._collect_news(lat, lng, radius_km, context),
            self._collect_pois(lat, lng, radius_km, context),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        return context

    async def _collect_crimes(self, lat: Decimal, lon: Decimal, context: Dict[str, Any]):
        """Collect crime data"""
        try:
            response = await crime_service.get_crimes(
                lat=lat,
                lon=lon,
                months=12,
                limit=self.max_context_items
            )
            context["crimes"]["count"] = response.total_count
            context["crimes"]["items"] = response.crimes[:20]  # Limit for prompt

            # Count categories
            for crime in response.crimes:
                cat = crime.category
                context["crimes"]["categories"][cat] = context["crimes"]["categories"].get(cat, 0) + 1

        except Exception as e:
            logger.warning(f"Failed to collect crimes: {e}")

    async def _collect_events(self, lat: Decimal, lon: Decimal, radius_km: float, context: Dict[str, Any]):
        """Collect event data"""
        try:
            response = await events_service.get_events(
                lat=lat,
                lon=lon,
                within_km=radius_km,
                limit=self.max_context_items
            )
            context["events"]["count"] = response.total_count
            context["events"]["items"] = response.events[:15]
            # Event name is a dict like {"text": "Event Name"}, extract the string
            context["events"]["names"] = [
                e.name.get("text", str(e.name)) if isinstance(e.name, dict) else str(e.name)
                for e in response.events[:10]
            ]

        except Exception as e:
            logger.warning(f"Failed to collect events: {e}")

    async def _collect_news(self, lat: Decimal, lon: Decimal, radius_km: float, context: Dict[str, Any]):
        """Collect news data"""
        try:
            response = await news_service.get_news(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=30
            )
            context["news"]["count"] = response.total_count
            context["news"]["items"] = response.articles[:10]

            # Calculate average sentiment
            sentiments = [a.sentiment for a in response.articles if a.sentiment is not None]
            if sentiments:
                avg = sum(sentiments) / len(sentiments)
                context["news"]["sentiment"] = "positive" if avg > 0.1 else "negative" if avg < -0.1 else "neutral"

        except Exception as e:
            logger.warning(f"Failed to collect news: {e}")

    async def _collect_pois(self, lat: Decimal, lon: Decimal, radius_km: float, context: Dict[str, Any]):
        """Collect POI data"""
        try:
            response = await pois_service.get_pois(
                lat=lat,
                lon=lon,
                radius_km=radius_km,
                limit=self.max_context_items
            )
            context["pois"]["count"] = response.total_count
            context["pois"]["items"] = response.pois[:20]

            # Count amenities
            for poi in response.pois:
                if poi.tags and poi.tags.amenity:
                    amenity = poi.tags.amenity
                    context["pois"]["amenities"][amenity] = context["pois"]["amenities"].get(amenity, 0) + 1

        except Exception as e:
            logger.warning(f"Failed to collect POIs: {e}")

    async def _get_location_name(self, lat: float, lng: float) -> str:
        """Get human-readable location name"""
        try:
            result = await geocode_service.reverse_geocode(Decimal(str(lat)), Decimal(str(lng)))
            if result:
                parts = result.display_name.split(", ")
                return parts[0] if parts else result.display_name
        except Exception as e:
            logger.warning(f"Failed to get location name: {e}")
        return f"({lat:.4f}, {lng:.4f})"

    def _build_prompt(
        self,
        message: str,
        location_name: str,
        context: Dict[str, Any],
        map_context: MapContext
    ) -> str:
        """Build the LLM prompt with context and instructions"""

        # Format crime categories
        crime_cats = ", ".join([
            f"{cat} ({count})"
            for cat, count in sorted(context["crimes"]["categories"].items(), key=lambda x: -x[1])[:5]
        ]) or "none recorded"

        # Format POI amenities
        poi_amenities = ", ".join([
            f"{amenity} ({count})"
            for amenity, count in sorted(context["pois"]["amenities"].items(), key=lambda x: -x[1])[:5]
        ]) or "various"

        # Format event names
        event_names = ", ".join(context["events"]["names"][:5]) or "none upcoming"

        # Build POI list for potential highlighting
        poi_list = []
        for poi in context["pois"]["items"][:10]:
            poi_id = f"poi_{poi.id}"
            name = (poi.tags.name if poi.tags and poi.tags.name else None) or (poi.tags.amenity if poi.tags else "Unknown")
            poi_list.append(f"- {name} (id: {poi_id})")

        prompt = f"""You are a helpful location assistant for a map application showing data about {location_name}.

CURRENT LOCATION CONTEXT:
- Center: {map_context.center.lat:.4f}, {map_context.center.lng:.4f}
- Zoom level: {map_context.zoom}

DATA SUMMARY:
- Crimes: {context['crimes']['count']} incidents in past 12 months
  Top categories: {crime_cats}
- Events: {context['events']['count']} upcoming
  Examples: {event_names}
- News: {context['news']['count']} recent articles (sentiment: {context['news']['sentiment']})
- Points of Interest: {context['pois']['count']} places
  Top amenities: {poi_amenities}

AVAILABLE POIs (for highlighting):
{chr(10).join(poi_list) if poi_list else "No specific POIs to highlight"}

USER QUESTION: {message}

INSTRUCTIONS:
1. Answer the user's question based on the location context above
2. Be helpful, concise, and factual
3. If relevant, you can suggest UI actions by including a JSON block like this:

```json
{{"type": "HIGHLIGHT_RESULTS", "payload": {{"ids": ["poi_123", "poi_456"]}}}}
```

Available actions:
- SET_VIEWPORT: Navigate map - {{"type": "SET_VIEWPORT", "payload": {{"lat": 51.5, "lng": -0.1, "zoom": 15}}}}
- HIGHLIGHT_RESULTS: Highlight items - {{"type": "HIGHLIGHT_RESULTS", "payload": {{"ids": ["poi_123"]}}}}
- FIT_BOUNDS: Fit to area - {{"type": "FIT_BOUNDS", "payload": {{"bbox": [-0.2, 51.4, -0.1, 51.6]}}}}
- REFRESH_DATA: Reload data - {{"type": "REFRESH_DATA", "payload": {{"radius_km": 5}}}}

Only include actions if they would genuinely help the user. Most responses don't need actions.

Respond naturally without mentioning the technical details of actions."""

        return prompt

    def _parse_llm_response(self, raw_response: str) -> Tuple[str, List[UiAction]]:
        """Parse LLM response to extract text and UI actions"""
        ui_actions: List[UiAction] = []

        # Extract JSON blocks from response
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        json_matches = re.findall(json_pattern, raw_response)

        # Remove JSON blocks from text
        clean_text = re.sub(json_pattern, '', raw_response).strip()

        # Also try to find inline JSON objects for actions
        inline_pattern = r'\{"type"\s*:\s*"(SET_VIEWPORT|FIT_BOUNDS|HIGHLIGHT_RESULTS|CLEAR_HIGHLIGHTS|REFRESH_DATA|SET_FILTERS)"[^}]+\}'
        inline_matches = re.findall(inline_pattern, raw_response)

        # Parse JSON blocks
        for json_str in json_matches:
            try:
                action_data = json.loads(json_str.strip())
                action = self._create_action(action_data)
                if action:
                    ui_actions.append(action)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse action JSON: {e}")

        # Parse inline JSON
        for match in re.finditer(r'\{[^{}]*"type"\s*:\s*"[A-Z_]+"[^{}]*\}', raw_response):
            try:
                action_data = json.loads(match.group())
                action = self._create_action(action_data)
                if action and action not in ui_actions:
                    ui_actions.append(action)
            except (json.JSONDecodeError, ValueError):
                pass

        # Clean up text - remove any remaining action references
        clean_text = re.sub(r'\{[^{}]*"type"\s*:\s*"[A-Z_]+"[^{}]*\}', '', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        return clean_text, ui_actions

    def _create_action(self, action_data: Dict[str, Any]) -> Optional[UiAction]:
        """Create a typed action from raw data"""
        try:
            action_type = action_data.get("type")
            payload = action_data.get("payload", {})

            if action_type == "SET_VIEWPORT":
                return SetViewportAction(payload=payload)
            elif action_type == "FIT_BOUNDS":
                return FitBoundsAction(payload=payload)
            elif action_type == "HIGHLIGHT_RESULTS":
                return HighlightResultsAction(payload=payload)
            elif action_type == "CLEAR_HIGHLIGHTS":
                return ClearHighlightsAction()
            elif action_type == "REFRESH_DATA":
                return RefreshDataAction(payload=payload)
            elif action_type == "SET_FILTERS":
                return SetFiltersAction(payload=payload)
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return None

        except Exception as e:
            logger.warning(f"Failed to create action: {e}")
            return None

    def _extract_citations(self, context: Dict[str, Any], response_text: str) -> List[Citation]:
        """Extract relevant citations from context based on response"""
        citations = []

        # Check if response mentions crimes
        if "crime" in response_text.lower() and context["crimes"]["items"]:
            for crime in context["crimes"]["items"][:3]:
                citations.append(Citation(
                    id=f"crime_{crime.id}" if hasattr(crime, 'id') else f"crime_{id(crime)}",
                    type="crime",
                    title=crime.category,
                    snippet=f"{crime.category} - {crime.month}" if hasattr(crime, 'month') else crime.category
                ))

        # Check if response mentions events
        if "event" in response_text.lower() and context["events"]["items"]:
            for event in context["events"]["items"][:3]:
                # Event name is a dict like {"text": "Event Name"}
                event_name = event.name.get("text", str(event.name)) if isinstance(event.name, dict) else str(event.name) if event.name else None
                citations.append(Citation(
                    id=f"event_{event.id}" if hasattr(event, 'id') else f"event_{id(event)}",
                    type="event",
                    title=event_name,
                    snippet=event_name[:100] if event_name else None
                ))

        # Check if response mentions POIs/restaurants/cafes etc
        poi_keywords = ["restaurant", "cafe", "shop", "store", "place", "poi", "attraction"]
        if any(kw in response_text.lower() for kw in poi_keywords) and context["pois"]["items"]:
            for poi in context["pois"]["items"][:3]:
                citations.append(Citation(
                    id=f"poi_{poi.id}",
                    type="poi",
                    title=(poi.tags.name if poi.tags and poi.tags.name else None) or "Point of Interest",
                    snippet=poi.tags.amenity if poi.tags and poi.tags.amenity else None
                ))

        return citations[:5]  # Limit to 5 citations


# Service instance
chat_service = ChatService()
