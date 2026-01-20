"""
Summary service for combining location data into narratives
"""

import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
import asyncio

from app.core.config import settings
from app.core.redis import geocode_cache
from app.schemas.summary import LocationSummary, SummarizeRequest
from app.services.nlp_service import nlp_service
from app.services.geocode_service import geocode_service
from app.services.crime_service import crime_service
from app.services.events_service import events_service
from app.services.news_service import news_service
from app.services.pois_service import pois_service
from app.services.llm_service import llm_service
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class SummaryService:
    """Service for generating location summaries"""
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour cache for summaries
    
    async def generate_summary(self, request: SummarizeRequest) -> LocationSummary:
        """
        Generate a comprehensive location summary
        """
        # Generate cache key
        cache_key = geocode_cache.generate_key(
            "summary",
            lat=str(request.lat),
            lon=str(request.lon),
            radius_km=request.radius_km,
            include_crimes=request.include_crimes,
            include_events=request.include_events,
            include_news=request.include_news,
            include_pois=request.include_pois,
            max_items=request.max_items_per_type
        )
        
        # Check cache first
        cached_result = await geocode_cache.get(cache_key)
        if cached_result:
            logger.info(f"Summary cache hit for location: {request.lat}, {request.lon}")
            return LocationSummary(**cached_result)
        
        try:
            # Initialize NLP service
            await nlp_service.initialize()
            
            # Collect data from all services
            data = await self._collect_location_data(request)
            
            # Generate narrative
            narrative = await self._generate_narrative(data, request)
            
            # Extract keywords
            keywords = await nlp_service.extract_keywords(narrative, max_keywords=10)
            
            # Create summary
            summary = LocationSummary(
                lat=request.lat,
                lon=request.lon,
                radius_km=request.radius_km,
                crime_count=data["crimes"]["count"],
                event_count=data["events"]["count"],
                news_count=data["news"]["count"],
                poi_count=data["pois"]["count"],
                crime_categories=data["crimes"]["categories"],
                event_types=data["events"]["types"],
                news_sentiment=data["news"]["sentiment"],
                poi_amenities=data["pois"]["amenities"],
                narrative=narrative,
                keywords=keywords,
                cached=False,
                source="ai_summary"
            )
            
            # Cache the result
            await geocode_cache.set(cache_key, summary.dict())
            logger.info(f"Summary cache set for location: {request.lat}, {request.lon}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Summary generation failed for {request.lat}, {request.lon}: {e}")
            raise AppException(f"Summary generation failed: {str(e)}")
    
    async def _collect_location_data(self, request: SummarizeRequest) -> Dict[str, Any]:
        """Collect data from all services"""
        data = {
            "crimes": {"count": 0, "categories": {}, "items": []},
            "events": {"count": 0, "types": {}, "items": []},
            "news": {"count": 0, "sentiment": {}, "items": []},
            "pois": {"count": 0, "amenities": {}, "items": []}
        }
        
        # Collect data concurrently
        tasks = []
        
        if request.include_crimes:
            tasks.append(self._collect_crime_data(request, data))
        
        if request.include_events:
            tasks.append(self._collect_event_data(request, data))
        
        if request.include_news:
            tasks.append(self._collect_news_data(request, data))
        
        if request.include_pois:
            tasks.append(self._collect_poi_data(request, data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        return data
    
    async def _collect_crime_data(self, request: SummarizeRequest, data: Dict[str, Any]):
        """Collect crime data"""
        try:
            crime_response = await crime_service.get_crimes(
                lat=request.lat,
                lon=request.lon,
                months=12,
                limit=request.max_items_per_type
            )
            
            data["crimes"]["count"] = crime_response.total_count
            data["crimes"]["items"] = crime_response.crimes
            
            # Count by category
            for crime in crime_response.crimes:
                category = crime.category
                data["crimes"]["categories"][category] = data["crimes"]["categories"].get(category, 0) + 1
                
        except Exception as e:
            logger.warning(f"Crime data collection failed: {e}")
    
    async def _collect_event_data(self, request: SummarizeRequest, data: Dict[str, Any]):
        """Collect event data"""
        try:
            event_response = await events_service.get_events(
                lat=request.lat,
                lon=request.lon,
                within_km=request.radius_km,
                limit=request.max_items_per_type
            )
            
            data["events"]["count"] = event_response.total_count
            data["events"]["items"] = event_response.events
            
            # Count by type
            for event in event_response.events:
                event_type = "free" if event.is_free else "paid"
                data["events"]["types"][event_type] = data["events"]["types"].get(event_type, 0) + 1
                
        except Exception as e:
            logger.warning(f"Event data collection failed: {e}")
    
    async def _collect_news_data(self, request: SummarizeRequest, data: Dict[str, Any]):
        """Collect news data"""
        try:
            news_response = await news_service.get_news(
                lat=request.lat,
                lon=request.lon,
                radius_km=request.radius_km,
                limit=request.max_items_per_type
            )
            
            data["news"]["count"] = news_response.total_count
            data["news"]["items"] = news_response.articles
            
            # Calculate sentiment
            sentiments = []
            for article in news_response.articles:
                if article.sentiment is not None:
                    sentiments.append(article.sentiment)
            
            if sentiments:
                data["news"]["sentiment"] = {
                    "average": sum(sentiments) / len(sentiments),
                    "positive_count": sum(1 for s in sentiments if s > 0.1),
                    "negative_count": sum(1 for s in sentiments if s < -0.1),
                    "neutral_count": sum(1 for s in sentiments if -0.1 <= s <= 0.1)
                }
                
        except Exception as e:
            logger.warning(f"News data collection failed: {e}")
    
    async def _collect_poi_data(self, request: SummarizeRequest, data: Dict[str, Any]):
        """Collect POI data"""
        try:
            poi_response = await pois_service.get_pois(
                lat=request.lat,
                lon=request.lon,
                radius_km=request.radius_km,
                limit=request.max_items_per_type
            )
            
            data["pois"]["count"] = poi_response.total_count
            data["pois"]["items"] = poi_response.pois
            
            # Count by amenity
            for poi in poi_response.pois:
                amenity = poi.tags.amenity or "other"
                data["pois"]["amenities"][amenity] = data["pois"]["amenities"].get(amenity, 0) + 1
                
        except Exception as e:
            logger.warning(f"POI data collection failed: {e}")
    
    async def _generate_narrative(self, data: Dict[str, Any], request: SummarizeRequest) -> str:
        """Generate narrative text from collected data"""
        
        # Get location name
        location_name = await self._get_location_name(request.lat, request.lon)
        
        # Build detailed narrative sections
        sections = []

        # Introduction
        crime_count = data["crimes"]["count"]
        poi_count = data["pois"]["count"]

        if poi_count > 100:
            intro = f"{location_name} is a vibrant, bustling area with plenty to offer."
        elif poi_count > 50:
            intro = f"{location_name} is an active neighborhood with good amenities."
        elif poi_count > 20:
            intro = f"{location_name} is a moderate-sized area with essential services."
        else:
            intro = f"{location_name} is a quieter, more residential area."

        sections.append(intro)

        # Crime section (most important - safety first)
        if request.include_crimes:
            crime_text = self._format_crime_section(data["crimes"])
            sections.append(crime_text)

        # Event section (what's happening)
        if request.include_events:
            event_text = self._format_event_section(data["events"])
            sections.append(event_text)

        # POI section (amenities and facilities)
        if request.include_pois:
            poi_text = self._format_poi_section(data["pois"])
            sections.append(poi_text)

        # Combine sections into comprehensive narrative
        if not sections:
            narrative = f"No detailed information available for {location_name} at this time."
        else:
            narrative = " ".join(sections)
        
        # Try AI summarization if available
        if settings.LLM_PROVIDER.lower() != "none":
            try:
                narrative = await self._ai_summarize(narrative, data, request)
            except Exception as e:
                logger.warning(f"AI summarization failed, using rule-based: {e}")
        
        return narrative
    
    async def _get_location_name(self, lat: Decimal, lon: Decimal) -> str:
        """Get location name for the coordinates"""
        try:
            result = await geocode_service.reverse_geocode(lat, lon)
            if result:
                # Extract city/town name from display_name
                parts = result.display_name.split(", ")
                if len(parts) > 1:
                    return parts[0]
                return result.display_name
        except Exception as e:
            logger.warning(f"Location name lookup failed: {e}")
        
        return f"coordinates {lat}, {lon}"
    
    def _format_crime_section(self, crime_data: Dict[str, Any]) -> str:
        """Format crime data into narrative text"""
        count = crime_data["count"]
        categories = crime_data["categories"]

        if count == 0:
            return "Safety is excellent with virtually no crime reported. You can explore confidently at any time."
        elif count < 50:
            safety_text = f"This is a safe area with only {count} incidents reported in the past year. "
            if categories:
                top_crime = max(categories.items(), key=lambda x: x[1])[0]
                safety_text += f"Most common issues are {top_crime}, but overall it's very secure."
            return safety_text
        elif count < 150:
            safety_text = f"The area has moderate crime levels with {count} incidents. "
            if categories:
                top_crime = max(categories.items(), key=lambda x: x[1])[0]
                safety_text += f"Main concern is {top_crime}. Stay aware of your surroundings, especially in the evening."
            else:
                safety_text += "Normal city precautions are recommended, particularly at night."
            return safety_text
        else:
            # High crime area - detailed precautions
            safety_text = f"Crime is elevated with {count}+ incidents in the past year. "
            if categories:
                top_crimes = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:2]
                crime_types = " and ".join([cat for cat, _ in top_crimes])
                safety_text += f"Main issues include {crime_types}. "
            safety_text += "Important precautions: avoid walking alone at night, stick to well-lit main streets, keep valuables out of sight, and consider using taxis after dark."
            return safety_text
    
    def _format_event_section(self, event_data: Dict[str, Any]) -> str:
        """Format event data into narrative text"""
        count = event_data["count"]
        items = event_data["items"]

        if count == 0:
            return "There are no major events scheduled at the moment."

        # Try to get event names
        event_names = []
        for event in items[:2]:  # Get up to 2 event names
            if hasattr(event, 'name'):
                if isinstance(event.name, dict):
                    name = event.name.get('text', '')
                    if name:
                        event_names.append(name)
                else:
                    event_names.append(str(event.name))

        if count == 1:
            if event_names:
                return f"There's an exciting upcoming event: {event_names[0]}. Check it out on the map for more details!"
            else:
                return "There's 1 upcoming event in the area."
        elif count <= 5:
            if event_names:
                return f"There are {count} upcoming events including {event_names[0]}. Great time to visit!"
            else:
                return f"There are {count} upcoming events and activities in the area."
        else:
            if event_names:
                return f"This is a happening spot with {count}+ events! Notable ones include {event_names[0]} and many more. Check the events layer for the full lineup."
            else:
                return f"Lots to do here - {count}+ events and activities are scheduled. It's a vibrant, active area!"
    
    def _format_news_section(self, news_data: Dict[str, Any]) -> str:
        """Format news data into narrative text"""
        count = news_data["count"]

        if count == 0:
            return "Quiet news - no recent coverage."
        elif count <= 5:
            return f"{count} recent news articles."
        else:
            return f"In the news recently ({count} articles)."
    
    def _format_poi_section(self, poi_data: Dict[str, Any]) -> str:
        """Format POI data into narrative text"""
        count = poi_data["count"]
        amenities = poi_data["amenities"]

        if count == 0:
            return "This is a quiet area with limited commercial amenities. You may need to travel to nearby areas for shopping and dining."
        elif count < 20:
            return f"It's a quieter, more residential area with {count} local amenities covering basic needs."
        elif count < 50:
            amenity_text = f"The area has {count} places nearby including restaurants, cafes, and shops. "
            if amenities:
                top_amenity = max(amenities.items(), key=lambda x: x[1])[0]
                amenity_text += f"You'll find several {top_amenity} options."
            return amenity_text
        else:
            amenity_text = f"This is a vibrant, well-serviced area with {count}+ places! "
            if amenities:
                top_amenities = sorted(amenities.items(), key=lambda x: x[1], reverse=True)[:3]
                amenity_names = ", ".join([amenity for amenity, _ in top_amenities])
                amenity_text += f"Popular amenities include {amenity_names}, plus plenty of restaurants, cafes, shops, and services. Everything you need is within walking distance!"
            else:
                amenity_text += "You'll find restaurants, cafes, shops, and all essential services within walking distance."
            return amenity_text
    
    def _build_llm_prompt(self, narrative: str, data: Dict[str, Any], request: SummarizeRequest) -> str:
        """Build structured prompt for LLM consumption."""
        crime_count = data['crimes']['count']
        event_count = data['events']['count']
        poi_count = data['pois']['count']

        # Get top crime categories if available
        crime_details = ""
        if data['crimes']['categories']:
            top_crimes = sorted(data['crimes']['categories'].items(), key=lambda x: x[1], reverse=True)[:2]
            crime_details = f"Top crime types: {', '.join([cat for cat, _ in top_crimes])}"

        # Get event samples if available
        event_details = ""
        if data['events']['items']:
            event_names = []
            for event in data['events']['items'][:2]:
                if hasattr(event, 'name'):
                    if isinstance(event.name, dict):
                        event_names.append(event.name.get('text', ''))
                    else:
                        event_names.append(str(event.name))
            if event_names:
                event_details = f"Notable events: {', '.join(event_names)}"

        return (
            "You are a knowledgeable local guide. Create a detailed, informative summary in 4-5 sentences (100-120 words).\n\n"
            f"Location data within {request.radius_km}km:\n"
            f"- Crimes: {crime_count} incidents in past year. {crime_details}\n"
            f"- Events: {event_count} upcoming. {event_details}\n"
            f"- Places: {poi_count} points of interest\n"
            f"- News: {data['news']['count']} recent articles\n\n"
            "Instructions:\n"
            "1. Start with a brief introduction about the area's character\n"
            "2. Provide safety assessment - if crime is high (>150 incidents), include practical precautions (stay alert at night, avoid isolated areas, stick to main streets)\n"
            "3. Highlight major events or activities happening in the area\n"
            "4. Mention amenities and what makes the area interesting\n"
            "5. End with overall recommendation for visitors\n\n"
            "Write in a friendly, conversational tone like giving advice to a friend. Be honest about safety concerns while being helpful. "
            "Use natural language, avoid technical jargon."
        )

    async def _ai_summarize(self, text: str, data: Dict[str, Any], request: SummarizeRequest) -> str:
        """AI-powered summarization using configured LLM provider with fallback."""
        try:
            await llm_service.initialize()

            prompt = self._build_llm_prompt(text, data, request)
            summary = await llm_service.generate_summary(prompt, max_tokens=200)

            if summary:
                return summary
        except Exception as exc:
            logger.warning(f"LLM summarization failed: {exc}")

        # Fallback to template-based detailed summary
        return self._generate_fallback_summary(data, request)

    def _generate_fallback_summary(self, data: Dict[str, Any], request: SummarizeRequest) -> str:
        """Generate detailed template-based summary when AI is unavailable"""
        crime_count = data['crimes']['count']
        event_count = data['events']['count']
        poi_count = data['pois']['count']
        news_count = data['news']['count']

        summary_parts = []

        # 1. Area character introduction
        if poi_count > 100:
            summary_parts.append("This is a vibrant, bustling area with plenty to offer.")
        elif poi_count > 50:
            summary_parts.append("This is an active neighborhood with good amenities.")
        elif poi_count > 20:
            summary_parts.append("This is a moderate-sized area with essential services.")
        else:
            summary_parts.append("This is a quieter, more residential area.")

        # 2. Safety assessment with precautions
        if crime_count == 0:
            summary_parts.append("It's very safe with virtually no crime reported - you can feel comfortable exploring any time of day.")
        elif crime_count < 50:
            summary_parts.append(f"Safety is good with only {crime_count} incidents reported in the past year. Normal city precautions apply.")
        elif crime_count < 150:
            summary_parts.append(f"The area has moderate crime levels ({crime_count} incidents). Stay aware of your surroundings, especially in the evening.")
        else:
            # High crime - include detailed precautions
            crime_categories = data['crimes']['categories']
            if crime_categories:
                top_crime = max(crime_categories.items(), key=lambda x: x[1])[0]
                summary_parts.append(
                    f"Crime is higher here with {crime_count}+ incidents, mainly {top_crime}. "
                    f"Important precautions: avoid walking alone at night, stick to well-lit main streets, "
                    f"keep valuables out of sight, and stay alert in crowded areas. Consider using taxis after dark."
                )
            else:
                summary_parts.append(
                    f"Crime levels are elevated with {crime_count}+ incidents. "
                    f"Exercise caution: stay on main streets, avoid isolated areas especially at night, "
                    f"and keep your belongings secure."
                )

        # 3. Events and activities
        if event_count > 0:
            event_items = data['events']['items']
            if event_items and len(event_items) > 0:
                # Get first major event name
                first_event = event_items[0]
                event_name = ""
                if hasattr(first_event, 'name'):
                    if isinstance(first_event.name, dict):
                        event_name = first_event.name.get('text', '')
                    else:
                        event_name = str(first_event.name)

                if event_name and event_count == 1:
                    summary_parts.append(f"There's an upcoming event: {event_name}.")
                elif event_name and event_count <= 5:
                    summary_parts.append(f"There are {event_count} upcoming events including {event_name}.")
                elif event_count > 5:
                    if event_name:
                        summary_parts.append(f"Lots happening - {event_count}+ events including {event_name} and many more!")
                    else:
                        summary_parts.append(f"It's an active area with {event_count}+ upcoming events and activities.")
            else:
                if event_count > 10:
                    summary_parts.append(f"There's plenty to do with {event_count}+ events and activities happening.")
                else:
                    summary_parts.append(f"There are {event_count} events coming up in the area.")

        # 4. Amenities
        if poi_count > 100:
            summary_parts.append(f"You'll find over {poi_count} restaurants, cafes, shops, and services - everything you need is within reach.")
        elif poi_count > 50:
            summary_parts.append(f"The area has {poi_count}+ places including restaurants, shops, and essential amenities.")
        elif poi_count > 20:
            summary_parts.append(f"There are {poi_count} local amenities to cover your basic needs.")

        # 5. Overall recommendation
        if crime_count < 50 and poi_count > 50:
            summary_parts.append("Great spot for visitors and residents alike!")
        elif crime_count < 100 and event_count > 5:
            summary_parts.append("Worth a visit, especially if you're interested in local events and culture.")
        elif crime_count >= 150:
            summary_parts.append("If visiting, stay vigilant and plan your routes carefully.")
        else:
            summary_parts.append("A decent area to explore with proper awareness.")

        return " ".join(summary_parts)


# Service instance
summary_service = SummaryService()






