"""
Event data model for storing Eventbrite results used in ML pipelines.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.core.database import Base


class EventData(Base):
    __tablename__ = "event_data"

    id = Column(Integer, primary_key=True, index=True)

    # Source identifiers
    event_id = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique Eventbrite event ID",
    )

    # Location
    latitude = Column(
        Float,
        nullable=False,
        index=True,
        comment="Event latitude (derived from venue or search center)",
    )
    longitude = Column(
        Float,
        nullable=False,
        index=True,
        comment="Event longitude (derived from venue or search center)",
    )

    # Core metadata
    name = Column(String(255), nullable=False, comment="Event title")
    description = Column(Text, nullable=True, comment="Event description text")
    category = Column(String(100), nullable=True, comment="Top-level category")
    subcategory = Column(String(100), nullable=True, comment="Event subcategory")
    format = Column(String(100), nullable=True, comment="Event format (e.g., seminar)")

    # Pricing
    is_free = Column(Boolean, default=False, nullable=False, comment="Flag if event is free")
    price = Column(Float, nullable=True, comment="Ticket price (major units)")
    currency = Column(String(10), nullable=True, comment="Currency code (e.g., GBP)")

    # Timing (stored as ISO strings for now)
    start_time = Column(String(64), nullable=True, comment="Event start timestamp (ISO)")
    end_time = Column(String(64), nullable=True, comment="Event end timestamp (ISO)")

    # Venue and media
    venue_name = Column(String(255), nullable=True, comment="Venue name")
    venue_address = Column(Text, nullable=True, comment="Full venue address")
    url = Column(String(500), nullable=True, comment="Public landing page")
    image_url = Column(String(500), nullable=True, comment="Hero or poster image URL")

    # Processing metadata
    location_hash = Column(
        String(64),
        nullable=True,
        index=True,
        comment="Spatial hash used for deduplication",
    )
    processed = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Processing flag: 0=raw, 1=cleaned, -1=invalid",
    )
    collected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when record was ingested",
    )

    __table_args__ = (
        Index("idx_event_location", "latitude", "longitude"),
        Index("idx_event_category", "category"),
        Index("idx_event_start_time", "start_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<EventData(id={self.id}, event_id={self.event_id}, "
            f"lat={self.latitude}, lon={self.longitude})>"
        )

    def to_dict(self) -> dict:
        """Serialize model for JSON responses."""
        return {
            "id": self.id,
            "event_id": self.event_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "category": self.category,
            "subcategory": self.subcategory,
            "format": self.format,
            "is_free": self.is_free,
            "price": self.price,
            "currency": self.currency,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "venue_name": self.venue_name,
            "venue_address": self.venue_address,
            "url": self.url,
            "image_url": self.image_url,
            "processed": self.processed,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
        }



