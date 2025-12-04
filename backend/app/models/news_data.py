"""
News Data Model for storing historical news data from NewsAPI

Why this model?
- Stores historical news data for ML training
- Enables sentiment analysis and NLP features
- Tracks news coverage patterns per location
- Supports both safety and popularity score models

Technology: SQLAlchemy ORM + NLP processing
- Stores news articles with metadata
- Supports full-text search
- Tracks publication dates for trend analysis
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base


class NewsData(Base):
    """
    News Data Model
    
    Stores individual news articles from NewsAPI
    Used for:
    - Sentiment analysis for safety scoring
    - News coverage frequency for popularity
    - NLP feature extraction (keywords, entities)
    - Training ML models with text features
    """
    
    __tablename__ = "news_data"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Location data (if available)
    latitude = Column(Float, nullable=True, index=True, comment="News location latitude (if geo-tagged)")
    longitude = Column(Float, nullable=True, index=True, comment="News location longitude (if geo-tagged)")
    
    # News article details
    article_id = Column(String(100), nullable=True, unique=True, index=True, comment="Unique article identifier")
    title = Column(String(500), nullable=False, comment="Article title")
    description = Column(Text, nullable=True, comment="Article description/summary")
    content = Column(Text, nullable=True, comment="Full article content (if available)")
    
    # Source information
    source_name = Column(String(200), nullable=True, index=True, comment="News source name")
    source_id = Column(String(100), nullable=True, comment="News source ID")
    author = Column(String(200), nullable=True, comment="Article author")
    
    # Publication metadata
    published_at = Column(DateTime(timezone=True), nullable=True, index=True, comment="Publication date/time")
    url = Column(String(500), nullable=True, comment="Article URL")
    image_url = Column(String(500), nullable=True, comment="Article image URL")
    
    # NLP features (populated during processing)
    sentiment_score = Column(Float, nullable=True, comment="Sentiment score (-1 to 1, from VADER)")
    keywords = Column(Text, nullable=True, comment="Extracted keywords (JSON array)")
    entities = Column(Text, nullable=True, comment="Named entities (JSON array)")
    
    # Metadata for ML training
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="When this data was collected")
    processed = Column(Integer, default=0, comment="Processing flag: 0=raw, 1=NLP processed")
    
    # Computed fields
    location_hash = Column(String(64), nullable=True, index=True, comment="Hash of lat/lon for deduplication")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_news_location', 'latitude', 'longitude'),
        Index('idx_news_source_published', 'source_name', 'published_at'),
        Index('idx_news_sentiment', 'sentiment_score'),
        Index('idx_news_collected', 'collected_at'),
    )
    
    def __repr__(self):
        return f"<NewsData(id={self.id}, title={self.title[:50]}, sentiment={self.sentiment_score})>"
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'article_id': self.article_id,
            'title': self.title,
            'description': self.description,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'source_name': self.source_name,
            'author': self.author,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'url': self.url,
            'sentiment_score': self.sentiment_score,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None,
        }




