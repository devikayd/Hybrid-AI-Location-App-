"""
Database models for historical data storage and ML training
"""

from app.models.crime_data import CrimeData
from app.models.event_data import EventData
from app.models.news_data import NewsData
from app.models.poi_data import POIData
from app.models.training_data import TrainingData
from app.models.user_interaction import UserInteraction

__all__ = [
    "CrimeData",
    "EventData",
    "NewsData",
    "POIData",
    "TrainingData",
    "UserInteraction",
]


