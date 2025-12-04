# Crime Data Model for storing historical crime data from UK Police API


from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base


class CrimeData(Base):
    
    __tablename__ = "crime_data"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Location data (from UK Police API)
    latitude = Column(Float, nullable=False, index=True, comment="Crime location latitude")
    longitude = Column(Float, nullable=False, index=True, comment="Crime location longitude")
    
    # Crime details
    category = Column(String(100), nullable=False, index=True, comment="Crime category (e.g., 'burglary', 'violent-crime')")
    crime_type = Column(String(100), nullable=True, comment="Specific crime type")
    
    # UK Police API specific fields
    month = Column(String(7), nullable=False, index=True, comment="Month in YYYY-MM format")
    location_subtype = Column(String(100), nullable=True, comment="Location subtype")
    context = Column(Text, nullable=True, comment="Additional context")
    
    # UK Police API ID
    crime_id = Column(String(100), nullable=True, unique=True, index=True, comment="UK Police API crime ID")
    
    # Metadata for ML training
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="When this data was collected")
    processed = Column(Integer, default=0, comment="Processing flag: 0=raw, 1=processed")
    
    # Computed fields (populated during feature engineering)
    location_hash = Column(String(64), nullable=True, index=True, comment="Hash of lat/lon for deduplication")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_crime_location', 'latitude', 'longitude'),
        Index('idx_crime_category_month', 'category', 'month'),
        Index('idx_crime_collected', 'collected_at'),
    )
    
    def __repr__(self):
        return f"<CrimeData(id={self.id}, category={self.category}, lat={self.latitude}, lon={self.longitude})>"
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'category': self.category,
            'crime_type': self.crime_type,
            'month': self.month,
            'location_subtype': self.location_subtype,
            'crime_id': self.crime_id,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None,
        }




