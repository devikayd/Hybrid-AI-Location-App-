"""
XGBoost model training for safety and popularity scores.
Supports standard training and enhanced training (spatial CV, Optuna tuning, ensemble).
"""

import logging
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split, cross_val_score, KFold
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    import joblib
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("XGBoost or scikit-learn not available. Install: pip install xgboost scikit-learn joblib")

# Import scoring enhancements
try:
    from app.ml.scoring_enhancements import (
        train_with_enhancements,
        SpatialBlockCV,
        HyperparameterTuner,
        ScoringEnsemble,
        compare_cv_methods,
        check_available_packages,
        get_improvement_status
    )
    ENHANCEMENTS_AVAILABLE = True
except ImportError:
    ENHANCEMENTS_AVAILABLE = False

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import TrainingData
from app.ml.features import feature_calculator

logger = logging.getLogger(__name__)


class ModelTrainingService:
    """
    Model Training Service
    """
    
    def __init__(self):
        """Initialize model training service"""
        self.models_dir = Path("backend/app/ml/models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            'safety_model_trained': False,
            'popularity_model_trained': False,
            'safety_model_version': None,
            'popularity_model_version': None,
            'safety_model_metrics': {},
            'popularity_model_metrics': {},
            'last_training_date': None
        }
    
    async def train_safety_model(
        self,
        test_size: float = 0.2,
        random_state: int = 42,
        min_samples: int = 50
    ) -> Dict[str, Any]:
        """
        Train safety score model
        """
        if not XGBOOST_AVAILABLE:
            raise RuntimeError("XGBoost not available. Install: pip install xgboost scikit-learn joblib")
        
        try:
            logger.info("Starting safety model training...")
            
            # Step 1: Load training data
            db = next(get_db())
            training_records = db.query(TrainingData).filter(
                TrainingData.model_type == "safety"
            ).all()
            db.close()
            
            if len(training_records) < min_samples:
                raise ValueError(
                    f"Insufficient training data: {len(training_records)} samples. "
                    f"Minimum required: {min_samples}. "
                    f"Please extract more features first."
                )
            
            logger.info(f"Loaded {len(training_records)} training samples")
            
            # Step 2: Prepare features and labels
            X, y, feature_names = self._prepare_training_data(
                training_records, 
                label_field="safety_score"
            )
            
            if X.shape[0] < min_samples:
                raise ValueError(
                    f"Insufficient valid samples: {X.shape[0]}. "
                    f"Minimum required: {min_samples}"
                )
            
            logger.info(f"Prepared {X.shape[0]} samples with {X.shape[1]} features")
            
            # Step 3: Split into train/test sets
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, 
                test_size=test_size, 
                random_state=random_state
            )
            
            logger.info(f"Train set: {X_train.shape[0]} samples, Test set: {X_test.shape[0]} samples")
            
            # Step 4: Train XGBoost model
            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=random_state,
                n_jobs=-1
            )
            
            logger.info("Training XGBoost model...")
            model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False
            )
            
            # Step 5: Evaluate model
            train_pred = model.predict(X_train)
            test_pred = model.predict(X_test)
            
            metrics = self._calculate_metrics(y_train, train_pred, y_test, test_pred)
            
            # Step 6: Cross-validation
            cv_scores = cross_val_score(
                model, X, y, 
                cv=KFold(n_splits=5, shuffle=True, random_state=random_state),
                scoring='r2',
                n_jobs=-1
            )
            metrics['cv_r2_mean'] = float(cv_scores.mean())
            metrics['cv_r2_std'] = float(cv_scores.std())
            
            # Step 7: Save model
            model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = self.models_dir / f"safety_model_{model_version}.pkl"
            
            joblib.dump(model, model_path)
            logger.info(f"Model saved to {model_path}")
            
            # Save feature names
            feature_names_path = self.models_dir / f"safety_features_{model_version}.json"
            with open(feature_names_path, 'w') as f:
                json.dump(feature_names, f)
            
            # Step 8: Update statistics
            self.stats['safety_model_trained'] = True
            self.stats['safety_model_version'] = model_version
            self.stats['safety_model_metrics'] = metrics
            self.stats['last_training_date'] = datetime.now().isoformat()
            
            return {
                'success': True,
                'model_type': 'safety',
                'model_version': model_version,
                'model_path': str(model_path),
                'feature_names': feature_names,
                'metrics': metrics,
                'training_samples': X.shape[0],
                'test_samples': X_test.shape[0]
            }
            
        except Exception as e:
            logger.error(f"Safety model training failed: {e}", exc_info=True)
            raise
    
    async def train_popularity_model(
        self,
        test_size: float = 0.2,
        random_state: int = 42,
        min_samples: int = 50
    ) -> Dict[str, Any]:
        """
        Train popularity score model
        """
        if not XGBOOST_AVAILABLE:
            raise RuntimeError("XGBoost not available. Install: pip install xgboost scikit-learn joblib")
        
        try:
            logger.info("Starting popularity model training...")
            
            # Step 1: Load training data
            db = next(get_db())
            training_records = db.query(TrainingData).filter(
                TrainingData.model_type == "popularity"
            ).all()
            db.close()
            
            if len(training_records) < min_samples:
                raise ValueError(
                    f"Insufficient training data: {len(training_records)} samples. "
                    f"Minimum required: {min_samples}. "
                    f"Please extract more features first."
                )
            
            logger.info(f"Loaded {len(training_records)} training samples")
            
            # Step 2: Prepare features and labels
            X, y, feature_names = self._prepare_training_data(
                training_records,
                label_field="popularity_score"
            )
            
            if X.shape[0] < min_samples:
                raise ValueError(
                    f"Insufficient valid samples: {X.shape[0]}. "
                    f"Minimum required: {min_samples}"
                )
            
            logger.info(f"Prepared {X.shape[0]} samples with {X.shape[1]} features")
            
            # Step 3: Split into train/test sets
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=test_size,
                random_state=random_state
            )
            
            logger.info(f"Train set: {X_train.shape[0]} samples, Test set: {X_test.shape[0]} samples")
            
            # Step 4: Train XGBoost model
            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=random_state,
                n_jobs=-1
            )
            
            logger.info("Training XGBoost model...")
            model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False
            )
            
            # Step 5: Evaluate model
            train_pred = model.predict(X_train)
            test_pred = model.predict(X_test)
            
            metrics = self._calculate_metrics(y_train, train_pred, y_test, test_pred)
            
            # Step 6: Cross-validation
            cv_scores = cross_val_score(
                model, X, y,
                cv=KFold(n_splits=5, shuffle=True, random_state=random_state),
                scoring='r2',
                n_jobs=-1
            )
            metrics['cv_r2_mean'] = float(cv_scores.mean())
            metrics['cv_r2_std'] = float(cv_scores.std())
            
            # Step 7: Save model
            model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = self.models_dir / f"popularity_model_{model_version}.pkl"
            
            joblib.dump(model, model_path)
            logger.info(f"Model saved to {model_path}")
            
            # Save feature names
            feature_names_path = self.models_dir / f"popularity_features_{model_version}.json"
            with open(feature_names_path, 'w') as f:
                json.dump(feature_names, f)
            
            # Step 8: Update statistics
            self.stats['popularity_model_trained'] = True
            self.stats['popularity_model_version'] = model_version
            self.stats['popularity_model_metrics'] = metrics
            self.stats['last_training_date'] = datetime.now().isoformat()
            
            return {
                'success': True,
                'model_type': 'popularity',
                'model_version': model_version,
                'model_path': str(model_path),
                'feature_names': feature_names,
                'metrics': metrics,
                'training_samples': X.shape[0],
                'test_samples': X_test.shape[0]
            }
            
        except Exception as e:
            logger.error(f"Popularity model training failed: {e}", exc_info=True)
            raise
    
    async def train_all_models(
        self,
        test_size: float = 0.2,
        random_state: int = 42,
        min_samples: int = 50
    ) -> Dict[str, Any]:
        """
        Train both safety and popularity models
        """
        results = {}
        
        try:
            # Train safety model
            try:
                results['safety'] = await self.train_safety_model(
                    test_size=test_size,
                    random_state=random_state,
                    min_samples=min_samples
                )
            except Exception as e:
                results['safety'] = {'success': False, 'error': str(e)}
            
            # Train popularity model
            try:
                results['popularity'] = await self.train_popularity_model(
                    test_size=test_size,
                    random_state=random_state,
                    min_samples=min_samples
                )
            except Exception as e:
                results['popularity'] = {'success': False, 'error': str(e)}
            
            return {
                'success': results['safety'].get('success', False) or results['popularity'].get('success', False),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Model training failed: {e}", exc_info=True)
            raise
    
    def _prepare_training_data(
        self,
        training_records: List[TrainingData],
        label_field: str
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare training data from database records
        """
        features_list = []
        labels = []
        
        # Get feature names from first record
        feature_names = None
        
        for record in training_records:
            # Extract features
            features_dict = json.loads(record.features) if isinstance(record.features, str) else record.features
            
            # Extract label
            label = getattr(record, label_field)
            
            # Skip if label is missing
            if label is None or np.isnan(label):
                continue
            
            # Get feature names (should be consistent across records)
            if feature_names is None:
                feature_names = list(features_dict.keys())
            
            # Extract features in consistent order
            feature_vector = [features_dict.get(name, 0.0) for name in feature_names]
            features_list.append(feature_vector)
            labels.append(float(label))
        
        # Convert to numpy arrays
        X = np.array(features_list)
        y = np.array(labels)
        
        return X, y, feature_names
    
    def _calculate_metrics(
        self,
        y_train: np.ndarray,
        y_train_pred: np.ndarray,
        y_test: np.ndarray,
        y_test_pred: np.ndarray
    ) -> Dict[str, float]:
        """Calculate MSE, MAE, R², and RMSE for train and test sets."""
        metrics = {
            'train_mse': float(mean_squared_error(y_train, y_train_pred)),
            'train_mae': float(mean_absolute_error(y_train, y_train_pred)),
            'train_r2': float(r2_score(y_train, y_train_pred)),
            'train_rmse': float(np.sqrt(mean_squared_error(y_train, y_train_pred))),
            'test_mse': float(mean_squared_error(y_test, y_test_pred)),
            'test_mae': float(mean_absolute_error(y_test, y_test_pred)),
            'test_r2': float(r2_score(y_test, y_test_pred)),
            'test_rmse': float(np.sqrt(mean_squared_error(y_test, y_test_pred)))
        }
        
        return metrics
    
    def get_training_stats(self) -> Dict[str, Any]:
        """Get training statistics"""
        return self.stats.copy()
    
    def get_latest_model_path(self, model_type: str) -> Optional[str]:
        """Get path to latest trained model"""
        model_files = list(self.models_dir.glob(f"{model_type}_model_*.pkl"))
        if not model_files:
            return None

        # Sort by modification time (newest first)
        model_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return str(model_files[0])

    # enhanced training methods

    async def train_enhanced_safety_model(
        self,
        use_spatial_cv: bool = True,
        use_tuning: bool = True,
        use_ensemble: bool = True,
        n_tuning_trials: int = 50,
        min_samples: int = 50
    ) -> Dict[str, Any]:
        """Train safety model with spatial CV, Optuna tuning, and optional ensemble."""
        if not ENHANCEMENTS_AVAILABLE:
            raise RuntimeError(
                "Scoring enhancements not available. "
                "Ensure scoring_enhancements.py exists and dependencies are installed."
            )

        try:
            logger.info("Starting ENHANCED safety model training...")

            # Load training data
            db = next(get_db())
            training_records = db.query(TrainingData).filter(
                TrainingData.model_type == "safety"
            ).all()
            db.close()

            if len(training_records) < min_samples:
                raise ValueError(
                    f"Insufficient training data: {len(training_records)} samples. "
                    f"Minimum required: {min_samples}."
                )

            logger.info(f"Loaded {len(training_records)} training samples")

            # Prepare features and labels
            X, y, feature_names = self._prepare_training_data(
                training_records,
                label_field="safety_score"
            )

            if X.shape[0] < min_samples:
                raise ValueError(f"Insufficient valid samples: {X.shape[0]}")

            logger.info(f"Prepared {X.shape[0]} samples with {X.shape[1]} features")

            # Train with enhancements
            results = train_with_enhancements(
                X=X,
                y=y,
                use_spatial_cv=use_spatial_cv,
                use_tuning=use_tuning,
                use_ensemble=use_ensemble,
                n_tuning_trials=n_tuning_trials
            )

            # Save model
            model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = self.models_dir / f"safety_model_enhanced_{model_version}.pkl"

            joblib.dump(results['model'], model_path)
            logger.info(f"Enhanced model saved to {model_path}")

            # Save feature names
            feature_names_path = self.models_dir / f"safety_features_enhanced_{model_version}.json"
            with open(feature_names_path, 'w') as f:
                json.dump(feature_names, f)

            # Save enhancement metadata
            metadata_path = self.models_dir / f"safety_metadata_enhanced_{model_version}.json"
            metadata = {
                'model_type': results['model_type'],
                'use_spatial_cv': use_spatial_cv,
                'use_tuning': use_tuning,
                'use_ensemble': use_ensemble,
                'n_tuning_trials': n_tuning_trials,
                'metrics': results['metrics'],
                'cv_comparison': results['cv_comparison'],
                'ensemble_weights': results.get('ensemble_weights'),
                'available_models': results.get('available_models'),
                'timestamp': results['timestamp']
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Update statistics
            self.stats['safety_model_trained'] = True
            self.stats['safety_model_version'] = model_version
            self.stats['safety_model_metrics'] = results['metrics']
            self.stats['last_training_date'] = datetime.now().isoformat()

            return {
                'success': True,
                'model_type': 'safety',
                'training_mode': 'enhanced',
                'model_version': model_version,
                'model_path': str(model_path),
                'feature_names': feature_names,
                'metrics': results['metrics'],
                'cv_comparison': results['cv_comparison'],
                'ensemble_weights': results.get('ensemble_weights'),
                'available_models': results.get('available_models'),
                'tuning_results': results.get('tuning_results'),
                'training_samples': X.shape[0],
                'enhancements_used': {
                    'spatial_cv': use_spatial_cv,
                    'hyperparameter_tuning': use_tuning,
                    'model_ensemble': use_ensemble
                }
            }

        except Exception as e:
            logger.error(f"Enhanced safety model training failed: {e}", exc_info=True)
            raise

    async def train_enhanced_popularity_model(
        self,
        use_spatial_cv: bool = True,
        use_tuning: bool = True,
        use_ensemble: bool = True,
        n_tuning_trials: int = 50,
        min_samples: int = 50
    ) -> Dict[str, Any]:
        """
        Train popularity model with enhancements.

        Same enhancements as train_enhanced_safety_model.
        """
        if not ENHANCEMENTS_AVAILABLE:
            raise RuntimeError("Scoring enhancements not available.")

        try:
            logger.info("Starting ENHANCED popularity model training...")

            # Load training data
            db = next(get_db())
            training_records = db.query(TrainingData).filter(
                TrainingData.model_type == "popularity"
            ).all()
            db.close()

            if len(training_records) < min_samples:
                raise ValueError(
                    f"Insufficient training data: {len(training_records)} samples. "
                    f"Minimum required: {min_samples}."
                )

            logger.info(f"Loaded {len(training_records)} training samples")

            # Prepare features and labels
            X, y, feature_names = self._prepare_training_data(
                training_records,
                label_field="popularity_score"
            )

            if X.shape[0] < min_samples:
                raise ValueError(f"Insufficient valid samples: {X.shape[0]}")

            logger.info(f"Prepared {X.shape[0]} samples with {X.shape[1]} features")

            # Train with enhancements
            results = train_with_enhancements(
                X=X,
                y=y,
                use_spatial_cv=use_spatial_cv,
                use_tuning=use_tuning,
                use_ensemble=use_ensemble,
                n_tuning_trials=n_tuning_trials
            )

            # Save model
            model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = self.models_dir / f"popularity_model_enhanced_{model_version}.pkl"

            joblib.dump(results['model'], model_path)
            logger.info(f"Enhanced model saved to {model_path}")

            # Save feature names
            feature_names_path = self.models_dir / f"popularity_features_enhanced_{model_version}.json"
            with open(feature_names_path, 'w') as f:
                json.dump(feature_names, f)

            # Save enhancement metadata
            metadata_path = self.models_dir / f"popularity_metadata_enhanced_{model_version}.json"
            metadata = {
                'model_type': results['model_type'],
                'use_spatial_cv': use_spatial_cv,
                'use_tuning': use_tuning,
                'use_ensemble': use_ensemble,
                'n_tuning_trials': n_tuning_trials,
                'metrics': results['metrics'],
                'cv_comparison': results['cv_comparison'],
                'ensemble_weights': results.get('ensemble_weights'),
                'available_models': results.get('available_models'),
                'timestamp': results['timestamp']
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Update statistics
            self.stats['popularity_model_trained'] = True
            self.stats['popularity_model_version'] = model_version
            self.stats['popularity_model_metrics'] = results['metrics']
            self.stats['last_training_date'] = datetime.now().isoformat()

            return {
                'success': True,
                'model_type': 'popularity',
                'training_mode': 'enhanced',
                'model_version': model_version,
                'model_path': str(model_path),
                'feature_names': feature_names,
                'metrics': results['metrics'],
                'cv_comparison': results['cv_comparison'],
                'ensemble_weights': results.get('ensemble_weights'),
                'available_models': results.get('available_models'),
                'tuning_results': results.get('tuning_results'),
                'training_samples': X.shape[0],
                'enhancements_used': {
                    'spatial_cv': use_spatial_cv,
                    'hyperparameter_tuning': use_tuning,
                    'model_ensemble': use_ensemble
                }
            }

        except Exception as e:
            logger.error(f"Enhanced popularity model training failed: {e}", exc_info=True)
            raise

    async def train_all_enhanced_models(
        self,
        use_spatial_cv: bool = True,
        use_tuning: bool = True,
        use_ensemble: bool = True,
        n_tuning_trials: int = 50,
        min_samples: int = 50
    ) -> Dict[str, Any]:
        """
        Train both safety and popularity models with enhancements.
        """
        results = {}

        try:
            # Train enhanced safety model
            try:
                results['safety'] = await self.train_enhanced_safety_model(
                    use_spatial_cv=use_spatial_cv,
                    use_tuning=use_tuning,
                    use_ensemble=use_ensemble,
                    n_tuning_trials=n_tuning_trials,
                    min_samples=min_samples
                )
            except Exception as e:
                results['safety'] = {'success': False, 'error': str(e)}

            # Train enhanced popularity model
            try:
                results['popularity'] = await self.train_enhanced_popularity_model(
                    use_spatial_cv=use_spatial_cv,
                    use_tuning=use_tuning,
                    use_ensemble=use_ensemble,
                    n_tuning_trials=n_tuning_trials,
                    min_samples=min_samples
                )
            except Exception as e:
                results['popularity'] = {'success': False, 'error': str(e)}

            return {
                'success': results['safety'].get('success', False) or results['popularity'].get('success', False),
                'training_mode': 'enhanced',
                'results': results
            }

        except Exception as e:
            logger.error(f"Enhanced model training failed: {e}", exc_info=True)
            raise

    def get_enhancement_status(self) -> Dict[str, Any]:
        """Get status of available scoring enhancements."""
        if ENHANCEMENTS_AVAILABLE:
            return get_improvement_status()
        return {
            'available': False,
            'message': 'Scoring enhancements not installed. Check dependencies.'
        }


# Global service instance
model_training_service = ModelTrainingService()



