"""
User Interaction Model for storing user likes and saves

Why this model?
- Tracks user interactions (likes, saves) with location data
- Enables personalized recommendations based on user preferences
- Stores interaction history for collaborative filtering
- Supports user interest-based recommendation system

Technology: SQLAlchemy ORM
- Stores user interactions with items (events, POIs, news, crimes)
- Tracks interaction types (like, save)
- Supports recommendation generation based on user history
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class UserInteraction(Base):
    """
    User Interaction Model
    
    Stores user interactions (likes, saves) with location-based items
    Used for:
    - Tracking user preferences
    - Generating personalized recommendations
    - Collaborative filtering
    - User interest analysis
    """
    
    __tablename__ = "user_interactions"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # User identification (for academic purposes, can use session ID or simple user ID)
    user_id = Column(String(100), nullable=False, index=True, comment="User identifier (session ID or user ID)")
    
    # Item identification
    item_id = Column(String(200), nullable=False, index=True, comment="Item identifier (e.g., 'event_12345', 'poi_67890')")
    item_type = Column(String(50), nullable=False, index=True, comment="Item type: 'event', 'poi', 'news', 'crime'")
    
    # Interaction details
    interaction_type = Column(String(20), nullable=False, index=True, comment="Interaction type: 'like' or 'save'")
    is_active = Column(Boolean, default=True, nullable=False, comment="True if interaction is active, False if removed")
    
    # Item metadata (stored for quick access without joining)
    item_title = Column(String(500), nullable=True, comment="Item title/name")
    item_category = Column(String(100), nullable=True, index=True, comment="Item category")
    item_subtype = Column(String(100), nullable=True, comment="Item subtype (e.g., 'free' for events, 'restaurant' for POIs)")
    
    # Location data
    latitude = Column(Float, nullable=True, index=True, comment="Item location latitude")
    longitude = Column(Float, nullable=True, index=True, comment="Item location longitude")
    location_name = Column(String(200), nullable=True, comment="Location name (postcode or place name)")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="When interaction was created")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="When interaction was last updated")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_user_interaction_user', 'user_id', 'is_active'),
        Index('idx_user_interaction_item', 'item_id', 'item_type'),
        Index('idx_user_interaction_type', 'interaction_type', 'is_active'),
        Index('idx_user_interaction_category', 'item_category', 'item_type'),
        Index('idx_user_interaction_location', 'latitude', 'longitude'),
        Index('idx_user_interaction_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<UserInteraction(id={self.id}, user_id={self.user_id}, item_type={self.item_type}, interaction_type={self.interaction_type})>"
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'item_id': self.item_id,
            'item_type': self.item_type,
            'interaction_type': self.interaction_type,
            'is_active': self.is_active,
            'item_title': self.item_title,
            'item_category': self.item_category,
            'item_subtype': self.item_subtype,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'location_name': self.location_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


