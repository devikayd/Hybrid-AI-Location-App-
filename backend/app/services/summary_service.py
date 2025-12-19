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
        
        # Build narrative sections
        sections = []
        
        # Introduction
        sections.append(f"This area around {location_name} (within {request.radius_km}km) shows the following characteristics:")
        
        # Crime section
        if request.include_crimes and data["crimes"]["count"] > 0:
            crime_text = self._format_crime_section(data["crimes"])
            sections.append(crime_text)
        
        # Event section
        if request.include_events and data["events"]["count"] > 0:
            event_text = self._format_event_section(data["events"])
            sections.append(event_text)
        
        # News section
        if request.include_news and data["news"]["count"] > 0:
            news_text = self._format_news_section(data["news"])
            sections.append(news_text)
        
        # POI section
        if request.include_pois and data["pois"]["count"] > 0:
            poi_text = self._format_poi_section(data["pois"])
            sections.append(poi_text)
        
        # Combine sections
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
            return "The area has no recent crime reports."
        
        text = f"Crime activity shows {count} incidents in the past 12 months. "
        
        if categories:
            top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
            category_text = ", ".join([f"{cat} ({count})" for cat, count in top_categories])
            text += f"Most common crime types: {category_text}."
        
        return text
    
    def _format_event_section(self, event_data: Dict[str, Any]) -> str:
        """Format event data into narrative text"""
        count = event_data["count"]
        types = event_data["types"]
        
        if count == 0:
            return "No upcoming events found in this area."
        
        text = f"There are {count} upcoming events in the area. "
        
        if types:
            free_count = types.get("free", 0)
            paid_count = types.get("paid", 0)
            if free_count > 0 and paid_count > 0:
                text += f"Events include {free_count} free and {paid_count} paid events."
            elif free_count > 0:
                text += f"All {free_count} events are free to attend."
            else:
                text += f"All {paid_count} events require payment."
        
        return text
    
    def _format_news_section(self, news_data: Dict[str, Any]) -> str:
        """Format news data into narrative text"""
        count = news_data["count"]
        sentiment = news_data["sentiment"]
        
        if count == 0:
            return "No recent news coverage found for this area."
        
        text = f"Recent news coverage includes {count} articles. "
        
        if sentiment:
            avg_sentiment = sentiment["average"]
            if avg_sentiment > 0.1:
                text += "Overall sentiment is positive."
            elif avg_sentiment < -0.1:
                text += "Overall sentiment is negative."
            else:
                text += "Overall sentiment is neutral."
        
        return text
    
    def _format_poi_section(self, poi_data: Dict[str, Any]) -> str:
        """Format POI data into narrative text"""
        count = poi_data["count"]
        amenities = poi_data["amenities"]
        
        if count == 0:
            return "No notable points of interest found in this area."
        
        text = f"The area features {count} points of interest. "
        
        if amenities:
            top_amenities = sorted(amenities.items(), key=lambda x: x[1], reverse=True)[:3]
            amenity_text = ", ".join([f"{amenity} ({count})" for amenity, count in top_amenities])
            text += f"Most common amenities: {amenity_text}."
        
        return text
    
    def _build_llm_prompt(self, narrative: str, data: Dict[str, Any], request: SummarizeRequest) -> str:
        """Build structured prompt for LLM consumption."""
        return (
            "You are a location intelligence analyst. Using the data provided, generate a concise, data-driven, and helpful summary.\n\n"
            f"Location coordinates: ({request.lat}, {request.lon}) within a {request.radius_km}km radius.\n"
            "Aggregate data snapshot:\n"
            f"- Crimes: {data['crimes']['count']} incidents; categories: {data['crimes']['categories']}\n"
            f"- Events: {data['events']['count']} upcoming; types: {data['events']['types']}\n"
            f"- News: {data['news']['count']} articles; sentiment summary: {data['news']['sentiment']}\n"
            f"- Points of Interest: {data['pois']['count']} items; amenities: {data['pois']['amenities']}\n\n"
            "Initial narrative synthesis:\n"
            f"{narrative}\n\n"
            "Task:\n"
            "1. Summarize the safety context (crime data).\n"
            "2. Highlight key attractions or activities (events, POIs).\n"
            "3. Mention notable recent developments (news sentiment/topics).\n"
            "4. Provide an overall assessment that would help someone visiting or moving to the area.\n"
            "Keep the tone professional, objective, and human-like. Limit the response to 2-3 paragraphs."
        )

    async def _ai_summarize(self, text: str, data: Dict[str, Any], request: SummarizeRequest) -> str:
        """AI-powered summarization using configured LLM provider with fallback."""
        try:
            await llm_service.initialize()

            prompt = self._build_llm_prompt(text, data, request)
            summary = await llm_service.generate_summary(prompt)

            if summary:
                return summary
        except Exception as exc:
            logger.warning(f"LLM summarization failed: {exc}")
        
        # Fallback to extractive summarization
        return await nlp_service.summarize_text(text, max_sentences=3)


# Service instance
summary_service = SummaryService()






