"""
POI (Point of Interest) Data Model for storing historical POI data from OpenStreetMap

Why this model?
- Stores historical POI data for ML training
- Enables feature extraction (amenity density, types)
- Supports both safety and popularity score models
- Tracks POI diversity per location

Technology: SQLAlchemy ORM
- Stores OpenStreetMap POI data
- Supports categorization and tagging
- Tracks location data for spatial analysis
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base


class POIData(Base):
    """
    POI Data Model
    
    Stores individual POI records from OpenStreetMap
    Used for:
    - Calculating POI density per location
    - Training safety score models (essential amenities)
    - Training popularity score models (diversity)
    - Feature engineering for ML models
    """
    
    __tablename__ = "poi_data"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Location data
    latitude = Column(Float, nullable=False, index=True, comment="POI location latitude")
    longitude = Column(Float, nullable=False, index=True, comment="POI location longitude")
    
    # POI details
    poi_id = Column(String(100), nullable=True, unique=True, index=True, comment="OpenStreetMap node ID")
    name = Column(String(500), nullable=True, comment="POI name")
    
    # POI categorization
    amenity = Column(String(100), nullable=True, index=True, comment="Amenity type (e.g., 'restaurant', 'hospital')")
    category = Column(String(100), nullable=True, index=True, comment="POI category")
    type = Column(String(50), nullable=True, index=True, comment="POI type")
    
    # Additional metadata (stored as JSON-like string)
    tags = Column(Text, nullable=True, comment="Additional OSM tags (JSON)")
    
    # Address information
    address = Column(Text, nullable=True, comment="Full address")
    postcode = Column(String(20), nullable=True, index=True, comment="Postcode")
    
    # Contact information (if available)
    phone = Column(String(50), nullable=True, comment="Phone number")
    website = Column(String(500), nullable=True, comment="Website URL")
    
    # Metadata for ML training
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="When this data was collected")
    processed = Column(Integer, default=0, comment="Processing flag: 0=raw, 1=processed")
    
    # Computed fields
    location_hash = Column(String(64), nullable=True, index=True, comment="Hash of lat/lon for deduplication")
    is_essential = Column(Integer, default=0, comment="Flag: 1 if essential amenity (hospital, pharmacy, etc.)")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_poi_location', 'latitude', 'longitude'),
        Index('idx_poi_amenity_category', 'amenity', 'category'),
        Index('idx_poi_essential', 'is_essential'),
        Index('idx_poi_collected', 'collected_at'),
    )
    
    def __repr__(self):
        return f"<POIData(id={self.id}, name={self.name}, amenity={self.amenity})>"
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'poi_id': self.poi_id,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'amenity': self.amenity,
            'category': self.category,
            'type': self.type,
            'address': self.address,
            'postcode': self.postcode,
            'is_essential': self.is_essential,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None,
        }




