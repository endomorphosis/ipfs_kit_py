"""
Intelligent cache management with predictive eviction and dynamic tiering.

This module implements advanced caching strategies that go beyond traditional LRU/ARC
approaches, using machine learning and statistical techniques to predict content access
patterns and optimize cache management decisions.
"""

import time
import logging
import math
import pickle
import os
import json
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable
from datetime import datetime, timedelta
import threading
import heapq

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import pyarrow as pa

# Setup logging
logger = logging.getLogger(__name__)


class AccessPattern:
    """Represents a tracked access pattern for a content item."""

    def __init__(self, cid: str, initial_access_time: float = None):
        """Initialize an access pattern tracker.

        Args:
            cid: Content identifier
            initial_access_time: First access timestamp
        """
        self.cid = cid
        self.first_access = initial_access_time or time.time()
        self.last_access = self.first_access
        self.access_count = 1
        self.access_times: List[float] = [self.first_access]
        self.intervals: List[float] = []  # Time between successive accesses

        # Daily access patterns (hour -> count)
        self.hourly_pattern = [0] * 24
        current_hour = datetime.fromtimestamp(self.first_access).hour
        self.hourly_pattern[current_hour] += 1

        # Weekly access patterns (day -> count, 0=Monday)
        self.daily_pattern = [0] * 7
        current_day = datetime.fromtimestamp(self.first_access).weekday()
        self.daily_pattern[current_day] += 1

        # Content features
        self.size_bytes: Optional[int] = None
        self.content_type: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

        # Derived metrics (updated on-demand)
        self._heat_score: Optional[float] = None
        self._periodicity: Optional[float] = None
        self._next_access_prediction: Optional[float] = None
        self._retention_score: Optional[float] = None

    def record_access(self, timestamp: float = None) -> None:
        """Record a new access to this content.

        Args:
            timestamp: Access timestamp (current time if not provided)
        """
        now = timestamp or time.time()

        # Update basic stats
        self.access_count += 1

        # Compute interval from last access
        if self.access_times:
            interval = now - self.last_access
            self.intervals.append(interval)

        # Update time tracking
        self.last_access = now
        self.access_times.append(now)

        # Update hourly and daily patterns
        dt = datetime.fromtimestamp(now)
        self.hourly_pattern[dt.hour] += 1
        self.daily_pattern[dt.weekday()] += 1

        # Reset derived metrics to force recalculation
        self._heat_score = None
        self._periodicity = None
        self._next_access_prediction = None
        self._retention_score = None

    def update_metadata(self, size_bytes: Optional[int] = None,
                        content_type: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update content metadata.

        Args:
            size_bytes: Content size in bytes
            content_type: Content MIME type
            metadata: Additional metadata dictionary
        """
        if size_bytes is not None:
            self.size_bytes = size_bytes

        if content_type is not None:
            self.content_type = content_type

        if metadata:
            self.metadata.update(metadata)

        # Reset derived metrics
        self._retention_score = None

    @property
    def heat_score(self) -> float:
        """Calculate a heat score based on recency and frequency.

        Returns:
            Floating point heat score (higher is hotter)
        """
        if self._heat_score is not None:
            return self._heat_score

        # Base score using frequency and recency
        recency_factor = 1.0 / (1.0 + (time.time() - self.last_access) / 3600)  # Decay by hour
        frequency_factor = math.log1p(self.access_count)

        # Age factor (older but consistently accessed content has more value)
        age_hours = (time.time() - self.first_access) / 3600
        age_factor = math.log1p(age_hours) / 10.0  # Normalize to reasonable range

        # Periodicity bonus (if accessed at regular intervals)
        periodicity_bonus = 0.0
        if self.periodicity > 0:
            periodicity_bonus = min(0.5, 1.0 / (1.0 + self.periodicity))

        # Combine factors
        self._heat_score = (
            (0.4 * recency_factor) +
            (0.4 * frequency_factor) +
            (0.1 * age_factor) +
            (0.1 * periodicity_bonus)
        )

        return self._heat_score

    @property
    def periodicity(self) -> float:
        """Calculate how periodic the access pattern is.

        Returns:
            Score where lower values indicate more regular access patterns
        """
        if self._periodicity is not None:
            return self._periodicity

        # Need at least 3 accesses to detect patterns
        if len(self.intervals) < 2:
            self._periodicity = float('inf')
            return self._periodicity

        # Calculate variance in the intervals
        mean_interval = sum(self.intervals) / len(self.intervals)
        variance = sum((i - mean_interval) ** 2 for i in self.intervals) / len(self.intervals)

        # Coefficient of variation (standard deviation / mean)
        if mean_interval > 0:
            self._periodicity = math.sqrt(variance) / mean_interval
        else:
            self._periodicity = float('inf')

        return self._periodicity

    @property
    def next_access_prediction(self) -> float:
        """Predict the next access time based on patterns.

        Returns:
            Unix timestamp of predicted next access
        """
        if self._next_access_prediction is not None:
            return self._next_access_prediction

        # Simple prediction for now - average interval
        if self.intervals:
            avg_interval = sum(self.intervals) / len(self.intervals)
            self._next_access_prediction = self.last_access + avg_interval
        else:
            # No history - default to 24 hours from last access
            self._next_access_prediction = self.last_access + 86400

        return self._next_access_prediction

    @property
    def retention_score(self) -> float:
        """Calculate how important it is to retain this content.

        Returns:
            Score from 0 to 1 where higher values indicate more importance
        """
        if self._retention_score is not None:
            return self._retention_score

        # Start with heat score
        base_score = self.heat_score

        # Size penalty (larger content has higher cost to retain)
        size_penalty = 0.0
        if self.size_bytes:
            # Log scale to reduce impact of very large files
            size_mb = self.size_bytes / (1024 * 1024)
            size_penalty = min(0.3, math.log1p(size_mb) / 20.0)

        # Content type bonus (certain types may be more valuable)
        type_bonus = 0.0
        if self.content_type:
            # Higher priority for common web assets, models, and structured data
            priority_types = {
                'application/json': 0.1,
                'application/x-parquet': 0.2,
                'application/x-arrow': 0.2,
                'application/octet-stream': 0.05,
                'image/': 0.05,
                'model/': 0.2,
                'text/html': 0.1
            }

            for prefix, bonus in priority_types.items():
                if self.content_type.startswith(prefix):
                    type_bonus = bonus
                    break

        # Metadata-based bonus
        metadata_bonus = 0.0
        if 'importance' in self.metadata:
            metadata_bonus = min(0.2, float(self.metadata['importance']) / 10.0)

        # Combine all factors
        self._retention_score = max(0.0, min(1.0,
            base_score - size_penalty + type_bonus + metadata_bonus
        ))

        return self._retention_score

    def to_feature_vector(self) -> List[float]:
        """Convert the access pattern to a feature vector for ML models.

        Returns:
            List of numerical features for the access pattern
        """
        # Create feature vector
        features = [
            self.access_count,
            time.time() - self.first_access,  # Age
            time.time() - self.last_access,   # Recency
            self.heat_score,
            self.periodicity if not math.isinf(self.periodicity) else 0.0,
            sum(self.hourly_pattern) / max(1, sum(self.hourly_pattern)),  # Hour entropy
            sum(self.daily_pattern) / max(1, sum(self.daily_pattern)),    # Day entropy
            self.size_bytes if self.size_bytes else 0,
            self.retention_score
        ]

        # Add hourly pattern (normalized)
        hourly_sum = sum(self.hourly_pattern) or 1
        features.extend([h / hourly_sum for h in self.hourly_pattern])

        # Add daily pattern (normalized)
        daily_sum = sum(self.daily_pattern) or 1
        features.extend([d / daily_sum for d in self.daily_pattern])

        return features

    def to_dict(self) -> Dict[str, Any]:
        """Convert access pattern to dictionary for serialization.

        Returns:
            Dictionary representation of the access pattern
        """
        return {
            'cid': self.cid,
            'first_access': self.first_access,
            'last_access': self.last_access,
            'access_count': self.access_count,
            'access_times': self.access_times,
            'intervals': self.intervals,
            'hourly_pattern': self.hourly_pattern,
            'daily_pattern': self.daily_pattern,
            'size_bytes': self.size_bytes,
            'content_type': self.content_type,
            'metadata': self.metadata,
            'heat_score': self.heat_score,
            'periodicity': self.periodicity,
            'next_access_prediction': self.next_access_prediction,
            'retention_score': self.retention_score
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccessPattern':
        """Create an access pattern from a dictionary.

        Args:
            data: Dictionary representation of access pattern

        Returns:
            Reconstructed AccessPattern instance
        """
        pattern = cls(data['cid'], data['first_access'])
        pattern.last_access = data['last_access']
        pattern.access_count = data['access_count']
        pattern.access_times = data['access_times']
        pattern.intervals = data['intervals']
        pattern.hourly_pattern = data['hourly_pattern']
        pattern.daily_pattern = data['daily_pattern']
        pattern.size_bytes = data['size_bytes']
        pattern.content_type = data['content_type']
        pattern.metadata = data['metadata']
        pattern._heat_score = data.get('heat_score')
        pattern._periodicity = data.get('periodicity')
        pattern._next_access_prediction = data.get('next_access_prediction')
        pattern._retention_score = data.get('retention_score')
        return pattern


class PredictiveModel:
    """Machine learning model for predicting cache access patterns."""

    def __init__(self, model_type: str = 'retention', model_path: Optional[str] = None):
        """Initialize the predictive model.

        Args:
            model_type: Type of prediction ('retention', 'next_access', or 'reaccess')
            model_path: Optional path to pre-trained model
        """
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.last_training_time = 0
        self.min_training_samples = 100
        self.trained = False

        # Load pre-trained model if provided
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

    def train(self, access_patterns: Dict[str, AccessPattern], force: bool = False) -> bool:
        """Train the predictive model on access patterns.

        Args:
            access_patterns: Dictionary of CID -> AccessPattern
            force: Whether to force training even with few samples

        Returns:
            Boolean indicating if training was performed
        """
        # Check if we have enough data
        if len(access_patterns) < self.min_training_samples and not force:
            logger.info(f"Not enough samples to train model ({len(access_patterns)})")
            return False

        # Prepare training data
        X = []
        y = []

        for cid, pattern in access_patterns.items():
            # Extract features
            features = pattern.to_feature_vector()

            # Set target variable based on model type
            if self.model_type == 'retention':
                # Predict retention score
                target = pattern.retention_score
            elif self.model_type == 'next_access':
                # Predict time until next access (in hours)
                time_until_next = max(0, pattern.next_access_prediction - time.time()) / 3600
                target = min(168, time_until_next)  # Cap at 1 week
            elif self.model_type == 'reaccess':
                # Binary classification: will it be accessed again within 24 hours?
                will_access_soon = pattern.next_access_prediction < (time.time() + 86400)
                target = 1.0 if will_access_soon else 0.0
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")

            X.append(features)
            y.append(target)

        if not X:
            logger.warning("No valid training samples")
            return False

        # Convert to numpy arrays
        X = np.array(X)
        y = np.array(y)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Initialize the model based on type
        if self.model_type == 'reaccess':
            # Classification problem
            self.model = RandomForestClassifier(
                n_estimators=50,
                max_depth=10,
                min_samples_split=5,
                random_state=42
            )
        else:
            # Regression problem
            self.model = RandomForestRegressor(
                n_estimators=50,
                max_depth=10,
                min_samples_split=5,
                random_state=42
            )

        # Train the model
        self.model.fit(X_scaled, y)
        self.last_training_time = time.time()
        self.trained = True

        logger.info(f"Trained {self.model_type} model on {len(X)} samples")

        # For feature importance analysis
        if hasattr(self.model, 'feature_importances_'):
            logger.debug("Top features by importance:")
            for i, importance in enumerate(self.model.feature_importances_):
                if importance > 0.02:  # Only show significant features
                    feature_idx = i
                    logger.debug(f"Feature {feature_idx}: {importance:.4f}")

        return True

    def predict(self, pattern: AccessPattern) -> float:
        """Make a prediction for the given access pattern.

        Args:
            pattern: Access pattern to predict for

        Returns:
            Prediction value (interpretation depends on model_type)
        """
        if not self.trained or self.model is None:
            # Fall back to heuristic if model not trained
            if self.model_type == 'retention':
                return pattern.retention_score
            elif self.model_type == 'next_access':
                return max(0, pattern.next_access_prediction - time.time()) / 3600
            elif self.model_type == 'reaccess':
                return 1.0 if pattern.next_access_prediction < (time.time() + 86400) else 0.0

        # Extract features
        features = np.array([pattern.to_feature_vector()])

        # Scale features
        features_scaled = self.scaler.transform(features)

        # Make prediction
        return self.model.predict(features_scaled)[0]

    def batch_predict(self, patterns: List[AccessPattern]) -> List[float]:
        """Make predictions for multiple access patterns.

        Args:
            patterns: List of access patterns to predict for

        Returns:
            List of prediction values
        """
        if not self.trained or self.model is None or not patterns:
            # Fall back to individual predictions
            return [self.predict(p) for p in patterns]

        # Extract features
        features = np.array([p.to_feature_vector() for p in patterns])

        # Scale features
        features_scaled = self.scaler.transform(features)

        # Make predictions
        return self.model.predict(features_scaled).tolist()

    def save_model(self, model_path: str) -> bool:
        """Save the trained model to disk.

        Args:
            model_path: Path to save the model

        Returns:
            Boolean indicating success
        """
        if not self.trained or self.model is None:
            logger.warning("Cannot save untrained model")
            return False

        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(model_path), exist_ok=True)

            # Save model data
            model_data = {
                'model_type': self.model_type,
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'last_training_time': self.last_training_time,
                'trained': self.trained
            }

            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)

            logger.info(f"Saved model to {model_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    def load_model(self, model_path: str) -> bool:
        """Load a trained model from disk.

        Args:
            model_path: Path to the saved model

        Returns:
            Boolean indicating success
        """
        try:
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)

            self.model_type = model_data['model_type']
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.last_training_time = model_data['last_training_time']
            self.trained = model_data['trained']

            logger.info(f"Loaded {self.model_type} model from {model_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False


class IntelligentCacheManager:
    """Manager for intelligent cache operations with predictive eviction."""

    def __init__(self,
                 base_path: str = None,
                 memory_tier_size: int = 1024 * 1024 * 100,  # 100MB
                 ssd_tier_size: int = 1024 * 1024 * 1024,    # 1GB
                 hdd_tier_size: int = 1024 * 1024 * 1024 * 10,  # 10GB
                 training_interval: int = 3600,  # 1 hour
                 min_observations: int = 50,
                 enable_predictive_prefetch: bool = True,
                 enable_auto_rebalance: bool = True,
                 auto_train: bool = True):
        """Initialize the intelligent cache manager.

        Args:
            base_path: Base path for storing models and data
            memory_tier_size: Size limit for memory tier in bytes
            ssd_tier_size: Size limit for SSD tier in bytes
            hdd_tier_size: Size limit for HDD tier in bytes
            training_interval: How often to train models (seconds)
            min_observations: Minimum observations before predictions
            enable_predictive_prefetch: Whether to prefetch content
            enable_auto_rebalance: Whether to auto-rebalance tiers
            auto_train: Whether to train models automatically
        """
        self.base_path = base_path or os.path.expanduser("~/.ipfs_kit/cache")
        os.makedirs(self.base_path, exist_ok=True)

        # Configure tier sizes
        self.tier_sizes = {
            'memory': memory_tier_size,
            'ssd': ssd_tier_size,
            'hdd': hdd_tier_size
        }

        # Access pattern tracking
        self.access_patterns: Dict[str, AccessPattern] = {}
        self.pattern_lock = threading.RLock()

        # Predictive models
        self.models = {
            'retention': PredictiveModel('retention'),
            'next_access': PredictiveModel('next_access'),
            'reaccess': PredictiveModel('reaccess')
        }

        # Load existing models if available
        self._load_models()

        # Configuration
        self.training_interval = training_interval
        self.min_observations = min_observations
        self.enable_predictive_prefetch = enable_predictive_prefetch
        self.enable_auto_rebalance = enable_auto_rebalance
        self.auto_train = auto_train
        self.last_training_time = 0
        self.last_rebalance_time = 0

        # Current tier usage
        self.tier_usage = {
            'memory': 0,
            'ssd': 0,
            'hdd': 0
        }

        # Content size tracking
        self.content_sizes: Dict[str, int] = {}

        # Start background threads if needed
        if auto_train:
            self._start_auto_train_thread()

        if enable_auto_rebalance:
            self._start_rebalance_thread()

        logger.info(f"IntelligentCacheManager initialized with {len(self.access_patterns)} "
                    f"tracked patterns")

    def _load_models(self) -> None:
        """Load predictive models from disk."""
        model_dir = os.path.join(self.base_path, "models")
        os.makedirs(model_dir, exist_ok=True)

        for model_type in self.models:
            model_path = os.path.join(model_dir, f"{model_type}_model.pkl")
            if os.path.exists(model_path):
                self.models[model_type].load_model(model_path)

    def _save_models(self) -> None:
        """Save predictive models to disk."""
        model_dir = os.path.join(self.base_path, "models")
        os.makedirs(model_dir, exist_ok=True)

        for model_type, model in self.models.items():
            model_path = os.path.join(model_dir, f"{model_type}_model.pkl")
            model.save_model(model_path)

    def _load_access_patterns(self) -> None:
        """Load access pattern data from disk."""
        pattern_path = os.path.join(self.base_path, "access_patterns.json")
        if not os.path.exists(pattern_path):
            return

        try:
            with open(pattern_path, 'r') as f:
                patterns_data = json.load(f)

            with self.pattern_lock:
                self.access_patterns = {}
                for cid, data in patterns_data.items():
                    self.access_patterns[cid] = AccessPattern.from_dict(data)

            logger.info(f"Loaded {len(self.access_patterns)} access patterns")

        except Exception as e:
            logger.error(f"Error loading access patterns: {e}")

    def _save_access_patterns(self) -> None:
        """Save access pattern data to disk."""
        pattern_path = os.path.join(self.base_path, "access_patterns.json")

        try:
            os.makedirs(os.path.dirname(pattern_path), exist_ok=True)

            with self.pattern_lock:
                patterns_data = {cid: pattern.to_dict()
                                for cid, pattern in self.access_patterns.items()}

            with open(pattern_path, 'w') as f:
                json.dump(patterns_data, f)

            logger.info(f"Saved {len(self.access_patterns)} access patterns")

        except Exception as e:
            logger.error(f"Error saving access patterns: {e}")

    def _start_auto_train_thread(self) -> None:
        """Start background thread for automatic model training."""
        def training_thread():
            while True:
                # Check if it's time to train
                if time.time() - self.last_training_time > self.training_interval:
                    # Check if we have enough patterns
                    with self.pattern_lock:
                        pattern_count = len(self.access_patterns)

                    if pattern_count >= self.min_observations:
                        logger.info(f"Auto-training models with {pattern_count} patterns")
                        self.train_models()
                        self._save_models()

                # Sleep before next check
                time.sleep(300)  # Check every 5 minutes

        thread = threading.Thread(target=training_thread, daemon=True)
        thread.start()
        logger.info("Started auto-training thread")

    def _start_rebalance_thread(self) -> None:
        """Start background thread for automatic tier rebalancing."""
        def rebalance_thread():
            while True:
                # Check if it's time to rebalance (every 15 minutes)
                if time.time() - self.last_rebalance_time > 900:
                    logger.info("Auto-rebalancing cache tiers")
                    self.rebalance_tiers()
                    self.last_rebalance_time = time.time()

                # Sleep before next check
                time.sleep(300)  # Check every 5 minutes

        thread = threading.Thread(target=rebalance_thread, daemon=True)
        thread.start()
        logger.info("Started tier rebalancing thread")

    def record_access(self, cid: str, size_bytes: Optional[int] = None,
                     content_type: Optional[str] = None,
                     tier: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a content access for pattern learning.

        Args:
            cid: Content identifier
            size_bytes: Content size in bytes
            content_type: Content MIME type
            tier: Cache tier where content is stored
            metadata: Additional metadata about the content
        """
        timestamp = time.time()

        with self.pattern_lock:
            if cid in self.access_patterns:
                # Update existing pattern
                pattern = self.access_patterns[cid]
                pattern.record_access(timestamp)

                # Update metadata if provided
                if size_bytes is not None or content_type is not None or metadata:
                    pattern.update_metadata(size_bytes, content_type, metadata)
            else:
                # Create new pattern
                pattern = AccessPattern(cid, timestamp)
                if size_bytes is not None or content_type is not None or metadata:
                    pattern.update_metadata(size_bytes, content_type, metadata)
                self.access_patterns[cid] = pattern

            # Update content size tracking
            if size_bytes is not None:
                self.content_sizes[cid] = size_bytes

                # Update tier usage if tier is provided
                if tier and tier in self.tier_usage:
                    # Remove old size if it exists
                    old_size = self.content_sizes.get(cid, 0)
                    self.tier_usage[tier] += size_bytes - old_size

    def train_models(self, force: bool = False) -> Dict[str, bool]:
        """Train all predictive models.

        Args:
            force: Whether to force training even with few samples

        Returns:
            Dictionary of model_type -> training success
        """
        results = {}

        with self.pattern_lock:
            access_patterns = self.access_patterns.copy()

        for model_type, model in self.models.items():
            results[model_type] = model.train(access_patterns, force)

        self.last_training_time = time.time()
        return results

    def predict_next_access(self, cid: str) -> float:
        """Predict time until next access (in hours).

        Args:
            cid: Content identifier

        Returns:
            Predicted hours until next access
        """
        with self.pattern_lock:
            if cid not in self.access_patterns:
                return float('inf')

            pattern = self.access_patterns[cid]

        if self.models['next_access'].trained:
            hours = self.models['next_access'].predict(pattern)
            return max(0.0, hours)
        else:
            # Fall back to heuristic
            next_access_time = pattern.next_access_prediction
            hours_until = max(0, (next_access_time - time.time()) / 3600)
            return hours_until

    def predict_retention_score(self, cid: str) -> float:
        """Predict importance score for retaining this content.

        Args:
            cid: Content identifier

        Returns:
            Retention score from 0 to 1
        """
        with self.pattern_lock:
            if cid not in self.access_patterns:
                return 0.0

            pattern = self.access_patterns[cid]

        if self.models['retention'].trained:
            score = self.models['retention'].predict(pattern)
            return max(0.0, min(1.0, score))
        else:
            # Fall back to heuristic
            return pattern.retention_score

    def predict_reaccess_probability(self, cid: str) -> float:
        """Predict probability of reaccess within 24 hours.

        Args:
            cid: Content identifier

        Returns:
            Probability from 0 to 1
        """
        with self.pattern_lock:
            if cid not in self.access_patterns:
                return 0.0

            pattern = self.access_patterns[cid]

        if self.models['reaccess'].trained:
            prob = self.models['reaccess'].predict(pattern)
            return max(0.0, min(1.0, prob))
        else:
            # Fall back to heuristic
            next_access_time = pattern.next_access_prediction
            will_access_soon = next_access_time < (time.time() + 86400)
            return 1.0 if will_access_soon else 0.0

    def get_optimal_tier(self, cid: str) -> str:
        """Determine the optimal cache tier for this content.

        Args:
            cid: Content identifier

        Returns:
            Tier name ('memory', 'ssd', 'hdd')
        """
        # Get predictions
        retention_score = self.predict_retention_score(cid)
        hours_until_next = self.predict_next_access(cid)
        reaccess_prob = self.predict_reaccess_probability(cid)

        # Get content size
        size_bytes = self.content_sizes.get(cid, 0)

        # Decision logic
        if hours_until_next < 1 or reaccess_prob > 0.8:
            # Very likely to be accessed soon - memory tier
            # But consider size constraints
            if size_bytes > self.tier_sizes['memory'] / 10:
                # Too large for memory
                return 'ssd'
            return 'memory'
        elif hours_until_next < 24 or reaccess_prob > 0.5:
            # Likely to be accessed within a day - SSD tier
            return 'ssd'
        else:
            # Less likely to be accessed soon - HDD tier
            return 'hdd'

    def get_eviction_candidates(self, tier: str,
                              required_space: int) -> List[Tuple[str, float]]:
        """Get ordered list of content IDs to evict from a tier.

        Args:
            tier: Cache tier to evict from
            required_space: Amount of space needed in bytes

        Returns:
            List of (cid, score) tuples, lowest scores first (most evictable)
        """
        with self.pattern_lock:
            # Filter patterns by those in the specified tier
            tier_cids = [cid for cid in self.access_patterns
                         if cid in self.content_sizes]

        if not tier_cids:
            return []

        # Get retention scores for all content
        eviction_scores = []
        for cid in tier_cids:
            size = self.content_sizes.get(cid, 0)
            if size <= 0:
                continue

            # Get inverse of retention score (lower = more evictable)
            retention = self.predict_retention_score(cid)
            eviction_score = 1.0 - retention

            # Boost score for items not likely to be accessed soon
            hours_until_next = self.predict_next_access(cid)
            if hours_until_next > 24:
                eviction_score += 0.2

            # Priority to smaller files when scores are similar
            # This avoids evicting one large file when we could keep more smaller ones
            size_factor = math.log1p(size) / 30  # Normalize size impact
            adjusted_score = eviction_score + size_factor

            eviction_scores.append((cid, adjusted_score, size))

        # Sort by score (lowest retention score first)
        eviction_scores.sort(key=lambda x: x[1])

        # Return the necessary CIDs to free up required space
        result = []
        cumulative_space = 0

        for cid, score, size in eviction_scores:
            result.append((cid, score))
            cumulative_space += size
            if cumulative_space >= required_space:
                break

        return result

    def get_prefetch_candidates(self) -> List[Tuple[str, float]]:
        """Get list of content IDs that should be prefetched to faster tiers.

        Returns:
            List of (cid, score) tuples, highest scores first (most valuable)
        """
        if not self.enable_predictive_prefetch:
            return []

        with self.pattern_lock:
            patterns = list(self.access_patterns.values())

        if not patterns:
            return []

        # Calculate prefetch scores
        prefetch_scores = []
        for pattern in patterns:
            cid = pattern.cid

            # Skip if already in memory tier
            if self.get_current_tier(cid) == 'memory':
                continue

            # Calculate prefetch score
            reaccess_prob = self.predict_reaccess_probability(cid)
            hours_until_next = self.predict_next_access(cid)

            # We want to prefetch content that will be accessed soon
            # and has high probability of access
            if hours_until_next > 48 or reaccess_prob < 0.3:
                continue

            # Score based on access probability and timing
            # Higher score = more important to prefetch
            time_factor = 1.0 / (1.0 + hours_until_next / 12)  # Decays with time
            prefetch_score = reaccess_prob * time_factor

            size = self.content_sizes.get(cid, 0)
            if size > 0:
                prefetch_scores.append((cid, prefetch_score, size))

        # Sort by score (highest first)
        prefetch_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top candidates (limited by available memory)
        available_memory = self.tier_sizes['memory'] - self.tier_usage['memory']
        available_memory = max(0, available_memory)

        result = []
        cumulative_space = 0

        for cid, score, size in prefetch_scores:
            if cumulative_space + size > available_memory:
                # Skip if this would exceed available space
                continue

            result.append((cid, score))
            cumulative_space += size

        return result

    def rebalance_tiers(self) -> Dict[str, Any]:
        """Rebalance content across cache tiers based on predictions.

        Returns:
            Statistics about the rebalancing operation
        """
        stats = {
            'memory_tier': {
                'before': self.tier_usage['memory'],
                'after': 0,
                'moved_in': 0,
                'moved_out': 0,
                'evicted': 0
            },
            'ssd_tier': {
                'before': self.tier_usage['ssd'],
                'after': 0,
                'moved_in': 0,
                'moved_out': 0,
                'evicted': 0
            },
            'hdd_tier': {
                'before': self.tier_usage['hdd'],
                'after': 0,
                'moved_in': 0,
                'moved_out': 0,
                'evicted': 0
            },
            'operations': []
        }

        # Phase 1: Identify content that should move to faster tiers
        prefetch_candidates = self.get_prefetch_candidates()

        # Phase 2: Identify content that should move to slower tiers
        with self.pattern_lock:
            all_cids = list(self.access_patterns.keys())

        promotion_moves = []  # (cid, from_tier, to_tier)
        demotion_moves = []   # (cid, from_tier, to_tier)

        for cid in all_cids:
            current_tier = self.get_current_tier(cid)
            optimal_tier = self.get_optimal_tier(cid)

            if current_tier != optimal_tier:
                size = self.content_sizes.get(cid, 0)
                if size <= 0:
                    continue

                # Check if this is a promotion or demotion
                tiers = ['hdd', 'ssd', 'memory']  # Ordered by speed
                current_idx = tiers.index(current_tier) if current_tier in tiers else 0
                optimal_idx = tiers.index(optimal_tier) if optimal_tier in tiers else 0

                if optimal_idx > current_idx:
                    # Promotion to faster tier
                    promotion_moves.append((cid, current_tier, optimal_tier, size))
                else:
                    # Demotion to slower tier
                    demotion_moves.append((cid, current_tier, optimal_tier, size))

        # Phase 3: Execute moves, starting with demotions to free up space
        # First, execute demotions
        for cid, from_tier, to_tier, size in demotion_moves:
            # Record the operation
            stats['operations'].append({
                'cid': cid,
                'operation': 'demote',
                'from_tier': from_tier,
                'to_tier': to_tier,
                'size': size
            })

            # Update tier usage
            if from_tier in self.tier_usage and to_tier in self.tier_usage:
                self.tier_usage[from_tier] -= size
                self.tier_usage[to_tier] += size

                stats[f'{from_tier}_tier']['moved_out'] += size
                stats[f'{to_tier}_tier']['moved_in'] += size

        # Then, execute promotions, but only if there's enough space
        for cid, from_tier, to_tier, size in promotion_moves:
            # Check if there's enough space in the target tier
            if self.tier_usage[to_tier] + size > self.tier_sizes[to_tier]:
                # Not enough space, try to evict
                required_space = size - (self.tier_sizes[to_tier] - self.tier_usage[to_tier])
                eviction_candidates = self.get_eviction_candidates(to_tier, required_space)

                # Calculate space that can be freed
                can_free = sum(self.content_sizes.get(c[0], 0) for c in eviction_candidates)

                if can_free < required_space:
                    # Not enough space even with eviction
                    continue

                # Execute evictions
                for evict_cid, _ in eviction_candidates:
                    evict_size = self.content_sizes.get(evict_cid, 0)

                    # Record the operation
                    stats['operations'].append({
                        'cid': evict_cid,
                        'operation': 'evict',
                        'from_tier': to_tier,
                        'size': evict_size
                    })

                    # Update tier usage
                    self.tier_usage[to_tier] -= evict_size
                    stats[f'{to_tier}_tier']['evicted'] += evict_size

                    # Stop if we've freed enough space
                    required_space -= evict_size
                    if required_space <= 0:
                        break

            # Now execute the promotion
            stats['operations'].append({
                'cid': cid,
                'operation': 'promote',
                'from_tier': from_tier,
                'to_tier': to_tier,
                'size': size
            })

            # Update tier usage
            if from_tier in self.tier_usage and to_tier in self.tier_usage:
                self.tier_usage[from_tier] -= size
                self.tier_usage[to_tier] += size

                stats[f'{from_tier}_tier']['moved_out'] += size
                stats[f'{to_tier}_tier']['moved_in'] += size

        # Update final tier usage
        for tier in self.tier_usage:
            stats[f'{tier}_tier']['after'] = self.tier_usage[tier]

        # Record rebalance time
        self.last_rebalance_time = time.time()

        return stats

    def get_current_tier(self, cid: str) -> Optional[str]:
        """Get the current tier where a CID is stored.

        This method should be overridden by subclasses to determine where content
        is actually stored. This base implementation returns a placeholder.

        Args:
            cid: Content identifier

        Returns:
            Tier name or None if not present
        """
        # Placeholder implementation - should be overridden by subclasses
        # In real implementation, this would check each tier's actual content
        with self.pattern_lock:
            if cid not in self.access_patterns:
                return None

            # This is just a placeholder - actual implementation would check
            # tiers for presence of the content
            return 'memory'  # Placeholder

    def get_access_stats(self) -> Dict[str, Any]:
        """Get statistics about tracked access patterns.

        Returns:
            Dictionary with access statistics
        """
        with self.pattern_lock:
            pattern_count = len(self.access_patterns)
            total_access_count = sum(p.access_count for p in self.access_patterns.values())

            # Calculate tier utilization
            tier_utilization = {
                tier: 100 * self.tier_usage[tier] / max(1, self.tier_sizes[tier])
                for tier in self.tier_usage
            }

            # Count items by optimal tier
            optimal_tier_counts = {'memory': 0, 'ssd': 0, 'hdd': 0}
            for cid in self.access_patterns:
                optimal_tier = self.get_optimal_tier(cid)
                optimal_tier_counts[optimal_tier] = optimal_tier_counts.get(optimal_tier, 0) + 1

            # Retention score distribution
            retention_scores = [self.predict_retention_score(cid) for cid in self.access_patterns]
            avg_retention = sum(retention_scores) / max(1, len(retention_scores))

            # Reaccess probability distribution
            reaccess_probs = [self.predict_reaccess_probability(cid) for cid in self.access_patterns]
            avg_reaccess_prob = sum(reaccess_probs) / max(1, len(reaccess_probs))

            # Next access timing
            next_access_hours = [self.predict_next_access(cid) for cid in self.access_patterns]
            avg_next_access = sum(next_access_hours) / max(1, len(next_access_hours))

            return {
                'pattern_count': pattern_count,
                'total_access_count': total_access_count,
                'avg_access_per_pattern': total_access_count / max(1, pattern_count),
                'tier_utilization': tier_utilization,
                'optimal_tier_counts': optimal_tier_counts,
                'avg_retention_score': avg_retention,
                'avg_reaccess_probability': avg_reaccess_prob,
                'avg_hours_until_next_access': avg_next_access,
                'models_trained': {
                    name: model.trained for name, model in self.models.items()
                },
                'last_training_time': self.last_training_time,
                'last_rebalance_time': self.last_rebalance_time
            }

    def cleanup(self) -> None:
        """Clean up resources and save state before shutdown."""
        logger.info("Saving cache state before shutdown")
        self._save_access_patterns()
        self._save_models()
        logger.info("Cache state saved")


class IntelligentCacheStrategyProvider:
    """Provider for different intelligent caching strategies."""

    def __init__(self, cache_manager: IntelligentCacheManager):
        """Initialize the strategy provider.

        Args:
            cache_manager: Intelligent cache manager instance
        """
        self.cache_manager = cache_manager

    def get_ml_based_strategy(self) -> Callable[[str], float]:
        """Get a machine-learning based eviction strategy.

        Returns:
            Function that scores CIDs for eviction (lower = more evictable)
        """
        if not self.cache_manager.models['retention'].trained:
            return self.get_heuristic_strategy()

        def ml_strategy(cid: str) -> float:
            """Machine learning based eviction strategy."""
            # Use retention score as eviction priority (higher = less evictable)
            return self.cache_manager.predict_retention_score(cid)

        return ml_strategy

    def get_heuristic_strategy(self) -> Callable[[str], float]:
        """Get a heuristic-based eviction strategy.

        Returns:
            Function that scores CIDs for eviction (lower = more evictable)
        """
        def heuristic_strategy(cid: str) -> float:
            """Heuristic-based eviction strategy."""
            with self.cache_manager.pattern_lock:
                if cid not in self.cache_manager.access_patterns:
                    return 0.0  # Very evictable

                pattern = self.cache_manager.access_patterns[cid]
                return pattern.heat_score

        return heuristic_strategy

    def get_lru_strategy(self) -> Callable[[str], float]:
        """Get a Least-Recently-Used eviction strategy.

        Returns:
            Function that scores CIDs for eviction (lower = more evictable)
        """
        current_time = time.time()

        def lru_strategy(cid: str) -> float:
            """LRU eviction strategy."""
            with self.cache_manager.pattern_lock:
                if cid not in self.cache_manager.access_patterns:
                    return 0.0  # Very evictable

                pattern = self.cache_manager.access_patterns[cid]
                # Higher score = more recently used = less evictable
                return 1.0 / (1.0 + (current_time - pattern.last_access) / 3600)

        return lru_strategy

    def get_lfu_strategy(self) -> Callable[[str], float]:
        """Get a Least-Frequently-Used eviction strategy.

        Returns:
            Function that scores CIDs for eviction (lower = more evictable)
        """
        def lfu_strategy(cid: str) -> float:
            """LFU eviction strategy."""
            with self.cache_manager.pattern_lock:
                if cid not in self.cache_manager.access_patterns:
                    return 0.0  # Very evictable

                pattern = self.cache_manager.access_patterns[cid]
                # Higher score = more frequently used = less evictable
                return math.log1p(pattern.access_count)

        return lfu_strategy

    def get_size_aware_strategy(self) -> Callable[[str], float]:
        """Get a size-aware eviction strategy.

        Returns:
            Function that scores CIDs for eviction (lower = more evictable)
        """
        def size_aware_strategy(cid: str) -> float:
            """Size-aware eviction strategy (prefer to keep smaller items)."""
            with self.cache_manager.pattern_lock:
                if cid not in self.cache_manager.access_patterns:
                    return 0.0  # Very evictable

                pattern = self.cache_manager.access_patterns[cid]
                size = pattern.size_bytes or 1

                # Base score using pattern heat
                heat = pattern.heat_score

                # Size penalty (larger files are more evictable)
                size_mb = size / (1024 * 1024)
                size_factor = math.log1p(size_mb) / 20.0

                # Higher score = less evictable
                return max(0.0, heat - size_factor)

        return size_aware_strategy

    def get_retention_optimized_strategy(self) -> Callable[[str], float]:
        """Get a strategy optimized for long-term content retention.

        Returns:
            Function that scores CIDs for eviction (lower = more evictable)
        """
        def retention_strategy(cid: str) -> float:
            """Retention-optimized eviction strategy."""
            # Use either ML-based prediction or pattern-based heuristic
            if self.cache_manager.models['retention'].trained:
                return self.cache_manager.predict_retention_score(cid)
            else:
                with self.cache_manager.pattern_lock:
                    if cid not in self.cache_manager.access_patterns:
                        return 0.0

                    pattern = self.cache_manager.access_patterns[cid]
                    return pattern.retention_score

        return retention_strategy

    def get_latency_optimized_strategy(self) -> Callable[[str], float]:
        """Get a strategy optimized for low-latency access to hot content.

        Returns:
            Function that scores CIDs for eviction (lower = more evictable)
        """
        def latency_strategy(cid: str) -> float:
            """Latency-optimized eviction strategy."""
            # Prioritize content likely to be accessed soon
            reaccess_prob = self.cache_manager.predict_reaccess_probability(cid)
            hours_until_next = self.cache_manager.predict_next_access(cid)

            # Convert hours to a score factor (lower hours = higher score)
            time_factor = 1.0 / (1.0 + hours_until_next / 6)  # 6-hour half-life

            # Combine probability and timing
            # Higher score = less evictable
            return reaccess_prob * time_factor

        return latency_strategy

    def get_balanced_strategy(self) -> Callable[[str], float]:
        """Get a balanced eviction strategy combining multiple factors.

        Returns:
            Function that scores CIDs for eviction (lower = more evictable)
        """
        def balanced_strategy(cid: str) -> float:
            """Balanced eviction strategy combining multiple factors."""
            retention = self.cache_manager.predict_retention_score(cid)
            reaccess_prob = self.cache_manager.predict_reaccess_probability(cid)
            hours_until_next = self.cache_manager.predict_next_access(cid)

            # Get content size
            size_bytes = self.cache_manager.content_sizes.get(cid, 0)
            size_mb = size_bytes / (1024 * 1024) if size_bytes > 0 else 0

            # Time factor (decay with increasing hours)
            time_factor = 1.0 / (1.0 + hours_until_next / 12)  # 12-hour half-life

            # Size penalty
            size_penalty = min(0.3, math.log1p(size_mb) / 20.0)

            # Combine factors with weights
            score = (
                (0.3 * retention) +           # Long-term importance
                (0.4 * reaccess_prob * time_factor) +  # Short-term access likelihood
                (0.3 * (1.0 - size_penalty))  # Size consideration
            )

            return max(0.0, min(1.0, score))

        return balanced_strategy
