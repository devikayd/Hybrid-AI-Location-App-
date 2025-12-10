"""
Script to bootstrap training labels using deterministic scores

This script:
1. Finds all training_data records without labels
2. Calculates deterministic safety/popularity scores
3. Updates records with labels
4. Enables model training

Usage:
    python backend/scripts/bootstrap_training_labels.py
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import asyncio
import json
import logging
from decimal import Decimal
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import TrainingData
from app.services.scoring_service import scoring_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def bootstrap_labels():
    """Bootstrap labels for training data using deterministic scores"""
    
    # Initialize scoring service (for deterministic scoring)
    await scoring_service.initialize_models()
    
    db = next(get_db())
    
    try:
        # Get all training records without labels
        safety_records = db.query(TrainingData).filter(
            TrainingData.model_type == "safety",
            TrainingData.safety_score.is_(None)
        ).all()
        
        popularity_records = db.query(TrainingData).filter(
            TrainingData.model_type == "popularity",
            TrainingData.popularity_score.is_(None)
        ).all()
        
        logger.info(f"Found {len(safety_records)} safety records without labels")
        logger.info(f"Found {len(popularity_records)} popularity records without labels")
        
        # Update safety records
        updated_safety = 0
        for record in safety_records:
            try:
                # Parse features
                features_dict = json.loads(record.features) if isinstance(record.features, str) else record.features
                
                # Calculate deterministic safety score
                safety_score = scoring_service._deterministic_safety_score(features_dict)
                
                # Update record
                record.safety_score = safety_score
                updated_safety += 1
                
            except Exception as e:
                logger.warning(f"Failed to update safety record {record.id}: {e}")
        
        # Update popularity records
        updated_popularity = 0
        for record in popularity_records:
            try:
                # Parse features
                features_dict = json.loads(record.features) if isinstance(record.features, str) else record.features
                
                # Calculate deterministic popularity score
                popularity_score = scoring_service._deterministic_popularity_score(features_dict)
                
                # Update record
                record.popularity_score = popularity_score
                updated_popularity += 1
                
            except Exception as e:
                logger.warning(f"Failed to update popularity record {record.id}: {e}")
        
        # Commit changes
        db.commit()
        
        logger.info(f"✅ Updated {updated_safety} safety records with labels")
        logger.info(f"✅ Updated {updated_popularity} popularity records with labels")
        
        # Check total records with labels
        safety_with_labels = db.query(TrainingData).filter(
            TrainingData.model_type == "safety",
            TrainingData.safety_score.isnot(None)
        ).count()
        
        popularity_with_labels = db.query(TrainingData).filter(
            TrainingData.model_type == "popularity",
            TrainingData.popularity_score.isnot(None)
        ).count()
        
        logger.info(f"\n📊 Summary:")
        logger.info(f"   Safety records with labels: {safety_with_labels}")
        logger.info(f"   Popularity records with labels: {popularity_with_labels}")
        
        if safety_with_labels >= 50 and popularity_with_labels >= 50:
            logger.info(f"\n✅ Ready for training! You have enough labeled data.")
            logger.info(f"   Run: POST /api/v1/models/train")
        else:
            logger.warning(f"\n⚠️  Need more data. Minimum 50 samples required.")
            logger.warning(f"   Safety: {safety_with_labels}/50")
            logger.warning(f"   Popularity: {popularity_with_labels}/50")
        
    except Exception as e:
        logger.error(f"Bootstrap failed: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(bootstrap_labels())

