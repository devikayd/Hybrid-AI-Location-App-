"""
Training Data Model for storing ML training datasets

Why this model?
- Stores processed training data with features and labels
- Enables model training with historical data
- Tracks feature extraction results
- Supports model versioning and evaluation

Technology: SQLAlchemy ORM
- Stores feature vectors for ML models
- Tracks labels (safety/popularity scores)
- Supports model versioning
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from sqlalchemy.sql import func
from app.core.database import Base


class TrainingData(Base):
    """
    Training Data Model
    
    Stores processed training data with features and labels
    Used for:
    - Training XGBoost models (safety, popularity)
    - Feature storage and versioning
    - Model evaluation datasets
    - Tracking training data quality
    """
    
    __tablename__ = "training_data"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Location data
    latitude = Column(Float, nullable=False, index=True, comment="Location latitude")
    longitude = Column(Float, nullable=False, index=True, comment="Location longitude")
    location_name = Column(String(200), nullable=True, comment="Location name (e.g., 'London, UK')")
    
    # Model type
    model_type = Column(String(50), nullable=False, index=True, comment="Model type: 'safety' or 'popularity'")
    
    # Features (stored as JSON)
    features = Column(Text, nullable=False, comment="Feature vector (JSON)")
    """
    Features structure:
    {
        "crime_density": 0.5,
        "violent_crime_ratio": 0.2,
        "event_count": 10,
        "free_event_ratio": 0.6,
        "poi_diversity": 0.8,
        "essential_amenities_ratio": 0.4,
        "news_sentiment_avg": 0.3,
        "news_coverage_frequency": 5,
        ...
    }
    """
    
    # Labels (ground truth scores)
    safety_score = Column(Float, nullable=True, comment="Ground truth safety score (0-1)")
    popularity_score = Column(Float, nullable=True, comment="Ground truth popularity score (0-1)")
    
    # Data source tracking
    data_sources = Column(Text, nullable=True, comment="Data sources used (JSON array)")
    feature_version = Column(String(20), nullable=True, comment="Feature engineering version")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="When this training data was created")
    used_for_training = Column(Integer, default=0, comment="Flag: 1 if used in model training")
    model_version = Column(String(20), nullable=True, comment="Model version trained with this data")
    
    # Quality metrics
    data_quality_score = Column(Float, nullable=True, comment="Data quality score (0-1)")
    missing_features = Column(Text, nullable=True, comment="Missing features list (JSON array)")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_training_location', 'latitude', 'longitude'),
        Index('idx_training_model_type', 'model_type'),
        Index('idx_training_used', 'used_for_training'),
        Index('idx_training_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<TrainingData(id={self.id}, model_type={self.model_type}, lat={self.latitude}, lon={self.longitude})>"
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        import json
        return {
            'id': self.id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'location_name': self.location_name,
            'model_type': self.model_type,
            'features': json.loads(self.features) if self.features else {},
            'safety_score': self.safety_score,
            'popularity_score': self.popularity_score,
            'feature_version': self.feature_version,
            'data_quality_score': self.data_quality_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }




