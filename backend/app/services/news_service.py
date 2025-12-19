"""
NewsAPI service for news data
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
import asyncio

from app.core.config import settings
from app.core.redis import news_cache
from app.schemas.news import NewsArticle, NewsResponse, NewsSummary, NewsSource
from app.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)


class NewsService:
    """NewsAPI service for news data"""
    
    def __init__(self):
        self.base_url = settings.NEWSAPI_BASE_URL
        self.timeout = settings.NEWSAPI_TIMEOUT
        self.api_key = settings.NEWSAPI_KEY
    
    async def get_news(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 50,
        query: Optional[str] = None,
        limit: int = 20
    ) -> NewsResponse:
        """
        Get news data for a location with Redis caching
        """
        if not self.api_key:
            raise ExternalAPIException("NewsAPI", "API key not configured")
        
        # Generate cache key
        cache_key = news_cache.generate_key(
            "news",
            lat=str(lat),
            lon=str(lon),
            radius_km=radius_km,
            query=query or "all",
            limit=limit
        )
        
        # Check cache first
        cached_result = await news_cache.get(cache_key)
        if cached_result:
            logger.info(f"News cache hit for location: {lat}, {lon}")
            return NewsResponse(**cached_result)
        
        # Fetch from NewsAPI
        try:
            articles = await self._fetch_news_from_api(lat, lon, radius_km, query, limit)
            
            response = NewsResponse(
                lat=lat,
                lon=lon,
                articles=articles,
                cached=False,
                source="newsapi",
                total_count=len(articles)
            )
            
            # Cache the result
            await news_cache.set(cache_key, response.dict())
            logger.info(f"News cache set for location: {lat}, {lon}")
            
            return response
            
        except Exception as e:
            logger.error(f"News data fetch failed for {lat}, {lon}: {e}")
            raise ExternalAPIException("NewsAPI", str(e))
    
    async def get_news_summary(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int = 50,
        query: Optional[str] = None,
        limit: int = 20
    ) -> NewsSummary:
        """
        Get news summary statistics for a location
        """
        # Generate cache key
        cache_key = news_cache.generate_key(
            "news_summary",
            lat=str(lat),
            lon=str(lon),
            radius_km=radius_km,
            query=query or "all",
            limit=limit
        )
        
        # Check cache first
        cached_result = await news_cache.get(cache_key)
        if cached_result:
            logger.info(f"News summary cache hit for location: {lat}, {lon}")
            return NewsSummary(**cached_result)
        
        # Get news data
        news_response = await self.get_news(lat, lon, radius_km, query, limit)
        
        # Generate summary
        summary = self._generate_summary(news_response)
        
        # Cache the summary
        await news_cache.set(cache_key, summary.dict())
        logger.info(f"News summary cache set for location: {lat}, {lon}")
        
        return summary
    
    async def _fetch_news_from_api(
        self,
        lat: Decimal,
        lon: Decimal,
        radius_km: int,
        query: Optional[str],
        limit: int
    ) -> List[NewsArticle]:
        """Fetch news data from NewsAPI"""
        
        # Try multiple strategies to get news articles
        # Strategy 1: Use query if provided
        # Strategy 2: Use country-based top headlines
        # Strategy 3: Use general UK news query
        
        params = {
            "apiKey": self.api_key,
            "pageSize": min(limit, 100),  # NewsAPI max is 100
            "sortBy": "publishedAt"
        }
        
        # If query provided, use it
        if query:
            params["q"] = query
            params["language"] = "en"
        else:
            # Try country-based headlines first
            params["country"] = "gb"  # UK news
        
        logger.info(f"Fetching news from NewsAPI with params: {params}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/top-headlines",
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                articles_data = data.get("articles", [])
                
                # Log the raw response for debugging
                logger.info(f"NewsAPI response: status={data.get('status')}, totalResults={data.get('totalResults', 0)}, articles={len(articles_data)}")
                
                # If no articles and no query, try with a general UK query as fallback
                if not articles_data and not query:
                    logger.info("No articles from top-headlines, trying with 'UK' query using 'everything' endpoint...")
                    try:
                        fallback_params = {
                            "apiKey": self.api_key,
                            "q": "UK",
                            "language": "en",
                            "pageSize": min(limit, 100),
                            "sortBy": "publishedAt"
                        }
                        fallback_response = await client.get(
                            f"{self.base_url}/everything",  # Use 'everything' endpoint instead
                            params=fallback_params
                        )
                        fallback_response.raise_for_status()
                        fallback_data = fallback_response.json()
                        articles_data = fallback_data.get("articles", [])
                        logger.info(f"Fallback query returned {len(articles_data)} articles")
                    except Exception as fallback_error:
                        logger.warning(f"Fallback query also failed: {fallback_error}")
                
                # Convert to schema
                articles = []
                for item in articles_data[:limit]:
                    try:
                        source_data = item.get("source", {})
                        source = NewsSource(
                            id=source_data.get("id"),
                            name=source_data.get("name", "Unknown")
                        )
                        
                        article = NewsArticle(
                            source=source,
                            author=item.get("author"),
                            title=item.get("title", ""),
                            description=item.get("description"),
                            url=item.get("url", ""),
                            urlToImage=item.get("urlToImage"),
                            publishedAt=item.get("publishedAt", ""),
                            content=item.get("content")
                        )
                        
                        # Calculate basic sentiment
                        article.sentiment = self._calculate_sentiment(article.title, article.description)
                        
                        articles.append(article)
                    except Exception as e:
                        logger.warning(f"Invalid news article: {e}")
                        continue
                
                logger.info(f"Fetched {len(articles)} news articles for location {lat}, {lon}")
                return articles
                
            except httpx.TimeoutException:
                raise ExternalAPIException("NewsAPI", "Request timeout")
            except httpx.HTTPStatusError as e:
                raise ExternalAPIException("NewsAPI", f"HTTP {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                raise ExternalAPIException("NewsAPI", f"Request error: {str(e)}")
    
    def _calculate_sentiment(self, title: str, description: Optional[str]) -> Optional[float]:
        """Calculate basic sentiment score (-1 to 1)"""
        try:
            # Simple keyword-based sentiment
            positive_words = ["good", "great", "excellent", "positive", "success", "win", "gain", "rise", "up"]
            negative_words = ["bad", "terrible", "negative", "fail", "loss", "drop", "down", "crisis", "problem"]
            
            text = (title + " " + (description or "")).lower()
            
            positive_count = sum(1 for word in positive_words if word in text)
            negative_count = sum(1 for word in negative_words if word in text)
            
            total_words = len(text.split())
            if total_words == 0:
                return None
            
            # Simple sentiment score
            sentiment = (positive_count - negative_count) / max(total_words, 1)
            return max(-1, min(1, sentiment))  # Clamp between -1 and 1
            
        except Exception:
            return None
    
    def _generate_summary(self, news_response: NewsResponse) -> NewsSummary:
        """Generate news summary statistics"""
        sources = {}
        sentiments = []
        
        for article in news_response.articles:
            # Count by source
            source_name = article.source.name
            sources[source_name] = sources.get(source_name, 0) + 1
            
            # Collect sentiments
            if article.sentiment is not None:
                sentiments.append(article.sentiment)
        
        # Calculate sentiment statistics
        sentiment_summary = {}
        if sentiments:
            sentiment_summary = {
                "average": sum(sentiments) / len(sentiments),
                "positive_count": sum(1 for s in sentiments if s > 0.1),
                "negative_count": sum(1 for s in sentiments if s < -0.1),
                "neutral_count": sum(1 for s in sentiments if -0.1 <= s <= 0.1)
            }
        
        return NewsSummary(
            lat=news_response.lat,
            lon=news_response.lon,
            total_articles=news_response.total_count,
            sources=sources,
            sentiment_summary=sentiment_summary,
            cached=news_response.cached,
            source=news_response.source
        )


# Service instance
news_service = NewsService()






