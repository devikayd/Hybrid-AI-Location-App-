"""
Scoring model improvements — spatial CV, Optuna hyperparameter tuning, and model ensemble.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Iterator, Any
from datetime import datetime

from sklearn.model_selection import BaseCrossValidator, cross_val_score, KFold
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except (ImportError, OSError):
    LIGHTGBM_AVAILABLE = False

try:
    from catboost import CatBoostRegressor
    CATBOOST_AVAILABLE = True
except (ImportError, OSError):
    CATBOOST_AVAILABLE = False

logger = logging.getLogger(__name__)


class SpatialBlockCV(BaseCrossValidator):
    """Splits data geographically to prevent spatial leakage in CV evaluation."""

    def __init__(self, n_splits: int = 5, buffer_ratio: float = 0.0):
        self.n_splits = n_splits
        self.buffer_ratio = buffer_ratio

    def split(self, X: np.ndarray, y: np.ndarray = None,
              groups: np.ndarray = None) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """Generate spatial block splits."""

        n_samples = X.shape[0] if hasattr(X, 'shape') else len(X)

        # Extract spatial values for blocking
        if isinstance(X, pd.DataFrame):
            if 'latitude' in X.columns:
                block_values = X['latitude'].values
            else:
                block_values = X.iloc[:, 0].values
        elif hasattr(X, 'shape') and len(X.shape) > 1 and X.shape[1] >= 1:
            block_values = X[:, 0]
        else:
            block_values = np.arange(n_samples)

        val_min, val_max = float(block_values.min()), float(block_values.max())
        val_range = val_max - val_min

        # Handle edge case: all same value
        if val_range < 1e-10:
            indices = np.arange(n_samples)
            np.random.seed(42)
            np.random.shuffle(indices)
            fold_size = n_samples // self.n_splits

            for i in range(self.n_splits):
                start = i * fold_size
                end = start + fold_size if i < self.n_splits - 1 else n_samples
                test_idx = indices[start:end]
                train_idx = np.concatenate([indices[:start], indices[end:]])
                if len(train_idx) > 0 and len(test_idx) > 0:
                    yield train_idx, test_idx
            return

        block_size = val_range / self.n_splits

        # Assign each point to a block
        block_ids = np.floor((block_values - val_min) / (block_size + 1e-10)).astype(int)
        block_ids = np.clip(block_ids, 0, self.n_splits - 1)

        # Generate folds
        for fold_idx in range(self.n_splits):
            test_mask = block_ids == fold_idx
            train_mask = ~test_mask

            # Apply buffer zone if specified
            if self.buffer_ratio > 0:
                buffer_size = block_size * self.buffer_ratio
                fold_min = val_min + fold_idx * block_size
                fold_max = fold_min + block_size

                for i in range(n_samples):
                    if train_mask[i]:
                        val = block_values[i]
                        if val > (fold_min - buffer_size) and val < (fold_max + buffer_size):
                            train_mask[i] = False

            train_idx = np.where(train_mask)[0]
            test_idx = np.where(test_mask)[0]

            if len(train_idx) > 0 and len(test_idx) > 0:
                yield train_idx, test_idx

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits


def compare_cv_methods(
    model,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5
) -> Dict[str, Any]:
    """Compares standard random CV vs spatial CV to show the leakage gap."""
    # Standard CV - often gives inflated scores
    standard_cv = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    standard_scores = cross_val_score(model, X, y, cv=standard_cv, scoring='r2', n_jobs=-1)

    # Spatial CV - gives realistic scores
    spatial_cv = SpatialBlockCV(n_splits=n_splits)
    spatial_scores = cross_val_score(model, X, y, cv=spatial_cv, scoring='r2', n_jobs=-1)

    gap = float(standard_scores.mean() - spatial_scores.mean())

    return {
        'standard_cv': {
            'mean': float(standard_scores.mean()),
            'std': float(standard_scores.std()),
            'scores': [float(s) for s in standard_scores]
        },
        'spatial_cv': {
            'mean': float(spatial_scores.mean()),
            'std': float(spatial_scores.std()),
            'scores': [float(s) for s in spatial_scores]
        },
        'performance_gap': gap,
        'gap_percentage': float(gap / abs(standard_scores.mean()) * 100) if standard_scores.mean() != 0 else 0,
        'recommendation': 'Use spatial_cv for honest evaluation' if gap > 0.05 else 'Minimal spatial leakage'
    }


class HyperparameterTuner:
    """Bayesian hyperparameter tuning via Optuna."""

    def __init__(self, use_spatial_cv: bool = True, n_splits: int = 5):
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna not installed. Run: pip install optuna")

        self.use_spatial_cv = use_spatial_cv
        self.n_splits = n_splits
        self.best_params = None
        self.best_score = None
        self.study = None

    def _get_cv(self) -> BaseCrossValidator:
        if self.use_spatial_cv:
            return SpatialBlockCV(n_splits=self.n_splits)
        return KFold(n_splits=self.n_splits, shuffle=True, random_state=42)

    def tune_xgboost(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_trials: int = 50,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        if not XGBOOST_AVAILABLE:
            raise ImportError("XGBoost not available")

        cv = self._get_cv()

        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'random_state': 42,
                'n_jobs': -1
            }

            model = xgb.XGBRegressor(**params)

            try:
                scores = cross_val_score(model, X, y, cv=cv, scoring='r2', n_jobs=-1)
                return float(scores.mean())
            except Exception as e:
                logger.warning(f"Trial failed: {e}")
                return float('-inf')

        # Create and run study
        sampler = TPESampler(seed=42)
        self.study = optuna.create_study(direction='maximize', sampler=sampler)
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        logger.info(f"Starting XGBoost hyperparameter tuning ({n_trials} trials)...")
        self.study.optimize(objective, n_trials=n_trials, timeout=timeout)

        self.best_params = self.study.best_params
        self.best_score = self.study.best_value

        logger.info(f"Tuning complete. Best R²: {self.best_score:.4f}")

        return {
            'best_params': self.best_params,
            'best_score': float(self.best_score),
            'n_trials_completed': len(self.study.trials),
            'optimization_history': [float(t.value) for t in self.study.trials if t.value is not None]
        }

    def tune_lightgbm(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_trials: int = 50,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Tune LightGBM hyperparameters."""
        if not LIGHTGBM_AVAILABLE:
            raise ImportError("LightGBM not installed. Run: pip install lightgbm")

        cv = self._get_cv()

        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'max_depth': trial.suggest_int('max_depth', 3, 12),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
                'num_leaves': trial.suggest_int('num_leaves', 20, 150),
                'random_state': 42,
                'n_jobs': -1,
                'verbose': -1
            }

            model = lgb.LGBMRegressor(**params)

            try:
                scores = cross_val_score(model, X, y, cv=cv, scoring='r2', n_jobs=-1)
                return float(scores.mean())
            except Exception:
                return float('-inf')

        sampler = TPESampler(seed=42)
        self.study = optuna.create_study(direction='maximize', sampler=sampler)
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        logger.info(f"Starting LightGBM hyperparameter tuning ({n_trials} trials)...")
        self.study.optimize(objective, n_trials=n_trials, timeout=timeout)

        self.best_params = self.study.best_params
        self.best_score = self.study.best_value

        return {
            'best_params': self.best_params,
            'best_score': float(self.best_score),
            'n_trials_completed': len(self.study.trials)
        }

    def get_tuned_model(self, model_type: str = 'xgboost'):
        """Get model instance with tuned parameters."""
        if self.best_params is None:
            raise ValueError("No tuning results. Run tune_xgboost() or tune_lightgbm() first.")

        params = self.best_params.copy()
        params['random_state'] = 42
        params['n_jobs'] = -1

        if model_type == 'xgboost':
            return xgb.XGBRegressor(**params)
        elif model_type == 'lightgbm':
            params['verbose'] = -1
            return lgb.LGBMRegressor(**params)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")


class ScoringEnsemble:
    """Weighted ensemble of XGBoost, LightGBM, and CatBoost — weights based on spatial CV score."""

    def __init__(self, use_tuning: bool = False, n_tuning_trials: int = 30):
        self.use_tuning = use_tuning
        self.n_tuning_trials = n_tuning_trials
        self.models = {}
        self.weights = {}
        self.is_fitted = False

    def _create_default_models(self) -> Dict[str, Any]:
        """Create base models with default parameters."""
        models = {}

        if XGBOOST_AVAILABLE:
            models['xgboost'] = xgb.XGBRegressor(
                n_estimators=100, max_depth=6, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8,
                random_state=42, n_jobs=-1
            )

        if LIGHTGBM_AVAILABLE:
            models['lightgbm'] = lgb.LGBMRegressor(
                n_estimators=100, max_depth=6, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8,
                random_state=42, n_jobs=-1, verbose=-1
            )

        if CATBOOST_AVAILABLE:
            models['catboost'] = CatBoostRegressor(
                iterations=100, depth=6, learning_rate=0.1,
                random_state=42, verbose=0
            )

        return models

    def fit(self, X: np.ndarray, y: np.ndarray) -> 'ScoringEnsemble':
        logger.info("Fitting ensemble models...")

        # Create models (with or without tuning)
        if self.use_tuning and OPTUNA_AVAILABLE:
            self._fit_with_tuning(X, y)
        else:
            self.models = self._create_default_models()

        if not self.models:
            raise RuntimeError("No models available. Install xgboost, lightgbm, or catboost.")

        # Fit each model and calculate CV-based weights
        spatial_cv = SpatialBlockCV(n_splits=5)

        for name, model in self.models.items():
            logger.info(f"  Fitting {name}...")
            model.fit(X, y)

            try:
                scores = cross_val_score(model, X, y, cv=spatial_cv, scoring='r2', n_jobs=-1)
                cv_score = float(scores.mean())
                self.weights[name] = max(0.1, cv_score)  # Minimum weight
                logger.info(f"    {name} spatial CV R²: {cv_score:.4f}")
            except Exception as e:
                logger.warning(f"    CV failed for {name}: {e}")
                self.weights[name] = 0.5

        # Normalize weights to sum to 1
        total = sum(self.weights.values())
        self.weights = {k: v / total for k, v in self.weights.items()}

        self.is_fitted = True
        logger.info(f"Ensemble complete. Weights: {self.weights}")

        return self

    def _fit_with_tuning(self, X: np.ndarray, y: np.ndarray):
        """Fit models with hyperparameter tuning."""
        tuner = HyperparameterTuner(use_spatial_cv=True)

        if XGBOOST_AVAILABLE:
            try:
                logger.info("  Tuning XGBoost...")
                tuner.tune_xgboost(X, y, n_trials=self.n_tuning_trials)
                self.models['xgboost'] = tuner.get_tuned_model('xgboost')
            except Exception as e:
                logger.warning(f"  XGBoost tuning failed: {e}, using defaults")
                self.models['xgboost'] = xgb.XGBRegressor(
                    n_estimators=100, max_depth=6, random_state=42, n_jobs=-1
                )

        if LIGHTGBM_AVAILABLE:
            try:
                logger.info("  Tuning LightGBM...")
                tuner.tune_lightgbm(X, y, n_trials=self.n_tuning_trials)
                self.models['lightgbm'] = tuner.get_tuned_model('lightgbm')
            except Exception as e:
                logger.warning(f"  LightGBM tuning failed: {e}, using defaults")
                self.models['lightgbm'] = lgb.LGBMRegressor(
                    n_estimators=100, max_depth=6, random_state=42, n_jobs=-1, verbose=-1
                )

        if CATBOOST_AVAILABLE:
            # CatBoost with defaults (tuning more complex)
            self.models['catboost'] = CatBoostRegressor(
                iterations=100, depth=6, learning_rate=0.1,
                random_state=42, verbose=0
            )

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make weighted ensemble predictions."""
        if not self.is_fitted:
            raise ValueError("Ensemble not fitted. Call fit() first.")

        predictions = []
        weights = []

        for name, model in self.models.items():
            pred = model.predict(X)
            predictions.append(pred)
            weights.append(self.weights[name])

        predictions = np.array(predictions)
        weights = np.array(weights)

        return np.average(predictions, axis=0, weights=weights)

    def predict_with_uncertainty(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Returns (mean_prediction, std_across_models) for uncertainty estimates."""
        if not self.is_fitted:
            raise ValueError("Ensemble not fitted.")

        predictions = np.array([m.predict(X) for m in self.models.values()])

        return predictions.mean(axis=0), predictions.std(axis=0)

    def get_individual_predictions(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """Get predictions from each individual model."""
        if not self.is_fitted:
            raise ValueError("Ensemble not fitted.")

        return {name: model.predict(X) for name, model in self.models.items()}

    def get_feature_importance(self) -> Dict[str, List[float]]:
        """Get feature importance from each model."""
        if not self.is_fitted:
            raise ValueError("Ensemble not fitted.")

        importances = {}

        for name, model in self.models.items():
            if hasattr(model, 'feature_importances_'):
                importances[name] = [float(x) for x in model.feature_importances_]
            elif hasattr(model, 'get_feature_importance'):
                importances[name] = [float(x) for x in model.get_feature_importance()]

        return importances


def train_with_enhancements(
    X: np.ndarray,
    y: np.ndarray,
    use_spatial_cv: bool = True,
    use_tuning: bool = True,
    use_ensemble: bool = True,
    n_tuning_trials: int = 50
) -> Dict[str, Any]:
    """Main training entry point — runs spatial CV, optional Optuna tuning, and ensemble."""
    results = {
        'model': None,
        'model_type': None,
        'metrics': {},
        'cv_comparison': None,
        'tuning_results': None,
        'ensemble_weights': None,
        'timestamp': datetime.now().isoformat()
    }

    logger.info("=" * 50)
    logger.info("Starting Enhanced Model Training")
    logger.info("=" * 50)
    logger.info(f"  Samples: {X.shape[0]}, Features: {X.shape[1]}")
    logger.info(f"  Spatial CV: {use_spatial_cv}")
    logger.info(f"  Tuning: {use_tuning} ({n_tuning_trials} trials)")
    logger.info(f"  Ensemble: {use_ensemble}")

    # Choose training approach
    if use_ensemble:
        logger.info("\n[1/3] Training Ensemble Model...")
        ensemble = ScoringEnsemble(
            use_tuning=use_tuning,
            n_tuning_trials=n_tuning_trials
        )
        ensemble.fit(X, y)

        results['model'] = ensemble
        results['model_type'] = 'ensemble'
        results['ensemble_weights'] = ensemble.weights
        results['available_models'] = list(ensemble.models.keys())

        # Training metrics
        predictions = ensemble.predict(X)

    else:
        # Single model
        if use_tuning and OPTUNA_AVAILABLE:
            logger.info("\n[1/3] Tuning XGBoost Model...")
            tuner = HyperparameterTuner(use_spatial_cv=use_spatial_cv)
            tuning_results = tuner.tune_xgboost(X, y, n_trials=n_tuning_trials)
            model = tuner.get_tuned_model('xgboost')
            results['tuning_results'] = tuning_results
        else:
            logger.info("\n[1/3] Training Default XGBoost Model...")
            model = xgb.XGBRegressor(
                n_estimators=100, max_depth=6, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8,
                random_state=42, n_jobs=-1
            )

        model.fit(X, y)
        results['model'] = model
        results['model_type'] = 'xgboost'

        predictions = model.predict(X)

    # Calculate training metrics
    results['metrics']['train_r2'] = float(r2_score(y, predictions))
    results['metrics']['train_rmse'] = float(np.sqrt(mean_squared_error(y, predictions)))
    results['metrics']['train_mae'] = float(mean_absolute_error(y, predictions))

    # Compare CV methods
    logger.info("\n[2/3] Comparing Cross-Validation Methods...")
    base_model = xgb.XGBRegressor(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
    cv_comparison = compare_cv_methods(base_model, X, y, n_splits=5)
    results['cv_comparison'] = cv_comparison

    results['metrics']['standard_cv_r2'] = cv_comparison['standard_cv']['mean']
    results['metrics']['spatial_cv_r2'] = cv_comparison['spatial_cv']['mean']
    results['metrics']['cv_gap'] = cv_comparison['performance_gap']

    # Summary
    logger.info("\n[3/3] Training Complete!")
    logger.info("=" * 50)
    logger.info("RESULTS SUMMARY:")
    logger.info(f"  Model Type: {results['model_type']}")
    logger.info(f"  Train R²: {results['metrics']['train_r2']:.4f}")
    logger.info(f"  Train RMSE: {results['metrics']['train_rmse']:.4f}")
    logger.info(f"  Standard CV R²: {cv_comparison['standard_cv']['mean']:.4f}")
    logger.info(f"  Spatial CV R²: {cv_comparison['spatial_cv']['mean']:.4f}")
    logger.info(f"  CV Gap: {cv_comparison['performance_gap']:.4f} ({cv_comparison['gap_percentage']:.1f}%)")

    if results['ensemble_weights']:
        logger.info(f"  Ensemble Weights: {results['ensemble_weights']}")

    logger.info("=" * 50)

    return results


def check_available_packages() -> Dict[str, bool]:
    """Returns which optional ML packages are installed."""
    return {
        'xgboost': XGBOOST_AVAILABLE,
        'optuna': OPTUNA_AVAILABLE,
        'lightgbm': LIGHTGBM_AVAILABLE,
        'catboost': CATBOOST_AVAILABLE
    }


def get_improvement_status() -> Dict[str, Any]:
    """Get status of all improvements."""
    packages = check_available_packages()

    return {
        'spatial_cv': {
            'available': True,
            'description': 'Spatial cross-validation for honest evaluation'
        },
        'hyperparameter_tuning': {
            'available': packages['optuna'],
            'description': 'Optuna Bayesian optimization for hyperparameters',
            'install': 'pip install optuna' if not packages['optuna'] else None
        },
        'ensemble': {
            'available': packages['xgboost'],
            'models': {
                'xgboost': packages['xgboost'],
                'lightgbm': packages['lightgbm'],
                'catboost': packages['catboost']
            },
            'description': 'Multi-model ensemble for robust predictions'
        }
    }
