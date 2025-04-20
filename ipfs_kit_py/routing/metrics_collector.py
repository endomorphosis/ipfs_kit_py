"""
Metrics Collection and Analysis for Routing System

This module provides metrics collection, storage, and analysis capabilities
for the optimized data routing system, tracking performance, success rates,
and other key metrics to inform routing decisions.
"""

import os
import json
import time
import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path

from .config_manager import get_data_dir

# Configure logging
logger = logging.getLogger(__name__)


class RoutingMetricsDatabase:
    """
    SQLite database for storing routing metrics.
    
    This class handles storage and retrieval of routing metrics,
    providing persistence and analysis capabilities.
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        retention_days: int = 7
    ):
        """
        Initialize the routing metrics database.
        
        Args:
            db_path: Path to SQLite database file
            retention_days: Number of days to retain metrics
        """
        # Set database path
        if db_path:
            self.db_path = db_path
        else:
            data_dir = get_data_dir()
            self.db_path = os.path.join(data_dir, "routing_metrics.db")
        
        # Set retention period
        self.retention_days = retention_days
        
        # Initialize database
        self.db = None
        self._initialize_db()
        
        logger.debug(f"Routing metrics database initialized at {self.db_path}")
    
    def _initialize_db(self) -> None:
        """Initialize the database schema."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Connect to database
            self.db = sqlite3.connect(self.db_path)
            
            # Create tables
            cursor = self.db.cursor()
            
            # Routing decisions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS routing_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    backend_id TEXT NOT NULL,
                    content_type TEXT,
                    content_size INTEGER,
                    strategy TEXT,
                    priority TEXT,
                    score REAL,
                    factors TEXT
                )
            """)
            
            # Routing outcomes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS routing_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    backend_id TEXT NOT NULL,
                    content_type TEXT,
                    content_size INTEGER,
                    success INTEGER NOT NULL,
                    duration_ms INTEGER,
                    error TEXT
                )
            """)
            
            # Backend metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backend_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    backend_id TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_routing_decisions_timestamp
                ON routing_decisions(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_routing_decisions_backend
                ON routing_decisions(backend_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_routing_outcomes_timestamp
                ON routing_outcomes(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_routing_outcomes_backend
                ON routing_outcomes(backend_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backend_metrics_timestamp
                ON backend_metrics(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backend_metrics_backend
                ON backend_metrics(backend_id, metric_name)
            """)
            
            self.db.commit()
            logger.debug("Database schema initialized")
            
            # Clean up old data
            self._cleanup_old_data()
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}", exc_info=True)
            if self.db:
                self.db.close()
                self.db = None
            raise
    
    def _cleanup_old_data(self) -> None:
        """Clean up data older than retention period."""
        if not self.db:
            return
        
        try:
            # Calculate cutoff timestamp
            cutoff = int(time.time()) - (self.retention_days * 86400)
            
            # Delete old data
            cursor = self.db.cursor()
            cursor.execute(
                "DELETE FROM routing_decisions WHERE timestamp < ?",
                (cutoff,)
            )
            cursor.execute(
                "DELETE FROM routing_outcomes WHERE timestamp < ?",
                (cutoff,)
            )
            cursor.execute(
                "DELETE FROM backend_metrics WHERE timestamp < ?",
                (cutoff,)
            )
            
            self.db.commit()
            logger.debug(f"Cleaned up data older than {self.retention_days} days")
            
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}", exc_info=True)
    
    def record_routing_decision(
        self,
        backend_id: str,
        content_type: Optional[str] = None,
        content_size: Optional[int] = None,
        strategy: Optional[str] = None,
        priority: Optional[str] = None,
        score: Optional[float] = None,
        factors: Optional[Dict[str, float]] = None,
        timestamp: Optional[int] = None
    ) -> None:
        """
        Record a routing decision.
        
        Args:
            backend_id: Selected backend ID
            content_type: Content MIME type
            content_size: Content size in bytes
            strategy: Routing strategy
            priority: Routing priority
            score: Backend score
            factors: Factor scores
            timestamp: Optional timestamp (default: current time)
        """
        if not self.db:
            logger.warning("Database not available, cannot record routing decision")
            return
        
        try:
            # Use current time if timestamp not provided
            if timestamp is None:
                timestamp = int(time.time())
            
            # Convert factors to JSON
            factors_json = json.dumps(factors) if factors else None
            
            # Insert into database
            cursor = self.db.cursor()
            cursor.execute(
                """
                INSERT INTO routing_decisions
                (timestamp, backend_id, content_type, content_size, strategy, priority, score, factors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, backend_id, content_type, content_size, strategy, priority, score, factors_json)
            )
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error recording routing decision: {e}", exc_info=True)
    
    def record_routing_outcome(
        self,
        backend_id: str,
        success: bool,
        content_type: Optional[str] = None,
        content_size: Optional[int] = None,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None,
        timestamp: Optional[int] = None
    ) -> None:
        """
        Record a routing outcome.
        
        Args:
            backend_id: Backend that was used
            success: Whether the operation was successful
            content_type: Content MIME type
            content_size: Content size in bytes
            duration_ms: Operation duration in milliseconds
            error: Error message (if not successful)
            timestamp: Optional timestamp (default: current time)
        """
        if not self.db:
            logger.warning("Database not available, cannot record routing outcome")
            return
        
        try:
            # Use current time if timestamp not provided
            if timestamp is None:
                timestamp = int(time.time())
            
            # Insert into database
            cursor = self.db.cursor()
            cursor.execute(
                """
                INSERT INTO routing_outcomes
                (timestamp, backend_id, content_type, content_size, success, duration_ms, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, backend_id, content_type, content_size, 1 if success else 0, duration_ms, error)
            )
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error recording routing outcome: {e}", exc_info=True)
    
    def record_backend_metric(
        self,
        backend_id: str,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        timestamp: Optional[int] = None
    ) -> None:
        """
        Record a backend metric.
        
        Args:
            backend_id: Backend ID
            metric_type: Metric type (e.g., performance, cost, reliability)
            metric_name: Metric name
            metric_value: Metric value
            timestamp: Optional timestamp (default: current time)
        """
        if not self.db:
            logger.warning("Database not available, cannot record backend metric")
            return
        
        try:
            # Use current time if timestamp not provided
            if timestamp is None:
                timestamp = int(time.time())
            
            # Insert into database
            cursor = self.db.cursor()
            cursor.execute(
                """
                INSERT INTO backend_metrics
                (timestamp, backend_id, metric_type, metric_name, metric_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, backend_id, metric_type, metric_name, metric_value)
            )
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error recording backend metric: {e}", exc_info=True)
    
    def get_backend_success_rates(
        self,
        time_window_hours: int = 24,
        content_type: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get success rates for each backend.
        
        Args:
            time_window_hours: Time window in hours
            content_type: Optional content type filter
            
        Returns:
            Dictionary mapping backend ID to success rate (0.0-1.0)
        """
        if not self.db:
            logger.warning("Database not available, cannot get backend success rates")
            return {}
        
        try:
            # Calculate cutoff timestamp
            cutoff = int(time.time()) - (time_window_hours * 3600)
            
            # Build query
            query = """
                SELECT backend_id, COUNT(*) as total, SUM(success) as successes
                FROM routing_outcomes
                WHERE timestamp >= ?
            """
            params = [cutoff]
            
            # Add content type filter if provided
            if content_type:
                query += " AND content_type = ?"
                params.append(content_type)
            
            # Group by backend
            query += " GROUP BY backend_id"
            
            # Execute query
            cursor = self.db.cursor()
            cursor.execute(query, params)
            
            # Calculate success rates
            success_rates = {}
            for backend_id, total, successes in cursor.fetchall():
                if total > 0:
                    success_rates[backend_id] = successes / total
                else:
                    success_rates[backend_id] = 0.0
            
            return success_rates
            
        except Exception as e:
            logger.error(f"Error getting backend success rates: {e}", exc_info=True)
            return {}
    
    def get_backend_metrics(
        self,
        metric_type: str,
        metric_name: str,
        time_window_hours: int = 24
    ) -> Dict[str, List[Tuple[int, float]]]:
        """
        Get metrics for each backend.
        
        Args:
            metric_type: Metric type
            metric_name: Metric name
            time_window_hours: Time window in hours
            
        Returns:
            Dictionary mapping backend ID to list of (timestamp, value) tuples
        """
        if not self.db:
            logger.warning("Database not available, cannot get backend metrics")
            return {}
        
        try:
            # Calculate cutoff timestamp
            cutoff = int(time.time()) - (time_window_hours * 3600)
            
            # Execute query
            cursor = self.db.cursor()
            cursor.execute(
                """
                SELECT backend_id, timestamp, metric_value
                FROM backend_metrics
                WHERE metric_type = ? AND metric_name = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (metric_type, metric_name, cutoff)
            )
            
            # Organize results by backend
            metrics = {}
            for backend_id, timestamp, value in cursor.fetchall():
                if backend_id not in metrics:
                    metrics[backend_id] = []
                metrics[backend_id].append((timestamp, value))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting backend metrics: {e}", exc_info=True)
            return {}
    
    def get_backend_latency_stats(
        self,
        time_window_hours: int = 24
    ) -> Dict[str, Dict[str, float]]:
        """
        Get latency statistics for each backend.
        
        Args:
            time_window_hours: Time window in hours
            
        Returns:
            Dictionary mapping backend ID to latency statistics
        """
        if not self.db:
            logger.warning("Database not available, cannot get backend latency stats")
            return {}
        
        try:
            # Calculate cutoff timestamp
            cutoff = int(time.time()) - (time_window_hours * 3600)
            
            # Execute query
            cursor = self.db.cursor()
            cursor.execute(
                """
                SELECT backend_id, AVG(duration_ms) as avg_latency, MIN(duration_ms) as min_latency,
                       MAX(duration_ms) as max_latency
                FROM routing_outcomes
                WHERE timestamp >= ? AND duration_ms IS NOT NULL
                GROUP BY backend_id
                """,
                (cutoff,)
            )
            
            # Organize results
            latency_stats = {}
            for backend_id, avg_latency, min_latency, max_latency in cursor.fetchall():
                latency_stats[backend_id] = {
                    "avg_latency_ms": avg_latency,
                    "min_latency_ms": min_latency,
                    "max_latency_ms": max_latency
                }
            
            return latency_stats
            
        except Exception as e:
            logger.error(f"Error getting backend latency stats: {e}", exc_info=True)
            return {}
    
    def get_content_type_backend_distribution(
        self,
        time_window_hours: int = 24
    ) -> Dict[str, Dict[str, int]]:
        """
        Get distribution of backends used for each content type.
        
        Args:
            time_window_hours: Time window in hours
            
        Returns:
            Dictionary mapping content type to dict of backend counts
        """
        if not self.db:
            logger.warning("Database not available, cannot get content type distribution")
            return {}
        
        try:
            # Calculate cutoff timestamp
            cutoff = int(time.time()) - (time_window_hours * 3600)
            
            # Execute query
            cursor = self.db.cursor()
            cursor.execute(
                """
                SELECT content_type, backend_id, COUNT(*) as count
                FROM routing_decisions
                WHERE timestamp >= ? AND content_type IS NOT NULL
                GROUP BY content_type, backend_id
                """,
                (cutoff,)
            )
            
            # Organize results
            distribution = {}
            for content_type, backend_id, count in cursor.fetchall():
                if content_type not in distribution:
                    distribution[content_type] = {}
                distribution[content_type][backend_id] = count
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error getting content type distribution: {e}", exc_info=True)
            return {}
    
    def get_backend_usage_stats(
        self,
        time_window_hours: int = 24
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get usage statistics for each backend.
        
        Args:
            time_window_hours: Time window in hours
            
        Returns:
            Dictionary mapping backend ID to usage statistics
        """
        if not self.db:
            logger.warning("Database not available, cannot get backend usage stats")
            return {}
        
        try:
            # Calculate cutoff timestamp
            cutoff = int(time.time()) - (time_window_hours * 3600)
            
            # Execute query for decisions
            cursor = self.db.cursor()
            cursor.execute(
                """
                SELECT backend_id, COUNT(*) as decisions, AVG(score) as avg_score
                FROM routing_decisions
                WHERE timestamp >= ?
                GROUP BY backend_id
                """,
                (cutoff,)
            )
            
            # Initialize results
            usage_stats = {}
            for backend_id, decisions, avg_score in cursor.fetchall():
                usage_stats[backend_id] = {
                    "decisions": decisions,
                    "avg_score": avg_score if avg_score is not None else 0.0,
                    "outcomes": 0,
                    "successes": 0,
                    "total_size_bytes": 0
                }
            
            # Execute query for outcomes
            cursor.execute(
                """
                SELECT backend_id, COUNT(*) as outcomes, SUM(success) as successes,
                       SUM(content_size) as total_size
                FROM routing_outcomes
                WHERE timestamp >= ?
                GROUP BY backend_id
                """,
                (cutoff,)
            )
            
            # Update results with outcome data
            for backend_id, outcomes, successes, total_size in cursor.fetchall():
                if backend_id not in usage_stats:
                    usage_stats[backend_id] = {
                        "decisions": 0,
                        "avg_score": 0.0
                    }
                
                usage_stats[backend_id]["outcomes"] = outcomes
                usage_stats[backend_id]["successes"] = successes
                usage_stats[backend_id]["total_size_bytes"] = total_size if total_size is not None else 0
            
            # Calculate additional statistics
            for backend_id, stats in usage_stats.items():
                if stats["outcomes"] > 0:
                    stats["success_rate"] = stats["successes"] / stats["outcomes"]
                else:
                    stats["success_rate"] = 0.0
                
                if stats["decisions"] > 0:
                    stats["outcome_rate"] = stats["outcomes"] / stats["decisions"]
                else:
                    stats["outcome_rate"] = 0.0
            
            return usage_stats
            
        except Exception as e:
            logger.error(f"Error getting backend usage stats: {e}", exc_info=True)
            return {}
    
    def close(self) -> None:
        """Close the database connection."""
        if self.db:
            self.db.close()
            self.db = None
            logger.debug("Database connection closed")


class RoutingMetricsCollector:
    """
    Collector for routing metrics.
    
    This class collects various metrics related to routing performance,
    backend behavior, and content characteristics.
    """
    
    def __init__(
        self,
        metrics_db: Optional[RoutingMetricsDatabase] = None,
        collection_interval: int = 300  # 5 minutes
    ):
        """
        Initialize the metrics collector.
        
        Args:
            metrics_db: Optional metrics database
            collection_interval: Collection interval in seconds
        """
        # Set metrics database
        self.metrics_db = metrics_db or RoutingMetricsDatabase()
        
        # Set collection interval
        self.collection_interval = collection_interval
        
        # Initialize state
        self.running = False
        self.collection_task = None
        
        logger.debug("Routing metrics collector initialized")
    
    async def start(self) -> None:
        """Start metrics collection."""
        if self.running:
            return
        
        self.running = True
        self.collection_task = asyncio.create_task(self._collect_metrics_loop())
        logger.info(f"Started metrics collection with interval {self.collection_interval}s")
    
    async def stop(self) -> None:
        """Stop metrics collection."""
        if not self.running:
            return
        
        self.running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
            self.collection_task = None
        
        logger.info("Stopped metrics collection")
    
    async def _collect_metrics_loop(self) -> None:
        """Continuously collect metrics at the specified interval."""
        while self.running:
            try:
                # Collect metrics
                await self._collect_metrics()
                
                # Wait for next collection
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a bit before retrying
    
    async def _collect_metrics(self) -> None:
        """Collect a set of routing metrics."""
        try:
            backends = await self._get_backends()
            timestamp = int(time.time())
            
            # Collect backend-specific metrics
            for backend_id in backends:
                # Collect performance metrics
                latency = await self._measure_backend_latency(backend_id)
                if latency is not None:
                    self.metrics_db.record_backend_metric(
                        backend_id=backend_id,
                        metric_type="performance",
                        metric_name="latency_ms",
                        metric_value=latency,
                        timestamp=timestamp
                    )
                
                # Collect availability metrics
                available = await self._check_backend_availability(backend_id)
                self.metrics_db.record_backend_metric(
                    backend_id=backend_id,
                    metric_type="reliability",
                    metric_name="available",
                    metric_value=1.0 if available else 0.0,
                    timestamp=timestamp
                )
                
                # Collect cost metrics (if available)
                cost = await self._get_backend_cost(backend_id)
                if cost is not None:
                    self.metrics_db.record_backend_metric(
                        backend_id=backend_id,
                        metric_type="cost",
                        metric_name="storage_cost_per_gb",
                        metric_value=cost,
                        timestamp=timestamp
                    )
                
                # Collect capacity metrics (if available)
                capacity = await self._get_backend_capacity(backend_id)
                if capacity is not None:
                    self.metrics_db.record_backend_metric(
                        backend_id=backend_id,
                        metric_type="capacity",
                        metric_name="available_gb",
                        metric_value=capacity,
                        timestamp=timestamp
                    )
            
            logger.debug(f"Collected metrics for {len(backends)} backends")
            
        except Exception as e:
            logger.error(f"Error in metrics collection: {e}", exc_info=True)
    
    async def _get_backends(self) -> List[str]:
        """
        Get list of backends to collect metrics for.
        
        Returns:
            List of backend IDs
        """
        # This would normally use the backend manager, but for now we'll
        # use a static list of common backends
        return ["ipfs", "filecoin", "s3", "local"]
    
    async def _measure_backend_latency(self, backend_id: str) -> Optional[float]:
        """
        Measure latency for a backend.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            Latency in milliseconds, or None if measurement failed
        """
        # This would normally measure actual latency, but for now we'll
        # simulate based on backend type
        try:
            # Simulate latency based on backend type
            if backend_id == "local":
                return 5.0 + (random.random() * 5.0)
            elif backend_id == "ipfs":
                return 50.0 + (random.random() * 100.0)
            elif backend_id == "s3":
                return 30.0 + (random.random() * 50.0)
            elif backend_id == "filecoin":
                return 200.0 + (random.random() * 300.0)
            else:
                return 100.0 + (random.random() * 100.0)
        except Exception as e:
            logger.warning(f"Error measuring latency for {backend_id}: {e}")
            return None
    
    async def _check_backend_availability(self, backend_id: str) -> bool:
        """
        Check if a backend is available.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            True if backend is available, False otherwise
        """
        # This would normally check actual availability, but for now we'll
        # simulate based on backend type with high reliability
        try:
            # Simulate availability based on backend type
            if backend_id == "local":
                return random.random() > 0.01  # 99% available
            elif backend_id == "ipfs":
                return random.random() > 0.05  # 95% available
            elif backend_id == "s3":
                return random.random() > 0.02  # 98% available
            elif backend_id == "filecoin":
                return random.random() > 0.1  # 90% available
            else:
                return random.random() > 0.2  # 80% available
        except Exception as e:
            logger.warning(f"Error checking availability for {backend_id}: {e}")
            return False
    
    async def _get_backend_cost(self, backend_id: str) -> Optional[float]:
        """
        Get storage cost for a backend.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            Storage cost per GB, or None if not available
        """
        # This would normally get actual cost information, but for now we'll
        # use static values
        try:
            # Return cost based on backend type
            if backend_id == "local":
                return 0.0
            elif backend_id == "ipfs":
                return 0.0
            elif backend_id == "s3":
                return 0.023
            elif backend_id == "filecoin":
                return 0.00002
            else:
                return None
        except Exception as e:
            logger.warning(f"Error getting cost for {backend_id}: {e}")
            return None
    
    async def _get_backend_capacity(self, backend_id: str) -> Optional[float]:
        """
        Get available capacity for a backend.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            Available capacity in GB, or None if not available
        """
        # This would normally get actual capacity information, but for now we'll
        # simulate based on backend type
        try:
            # Simulate capacity based on backend type
            if backend_id == "local":
                return 100.0 + (random.random() * 100.0)
            elif backend_id == "ipfs":
                return 1000.0 + (random.random() * 1000.0)
            elif backend_id == "s3":
                return 10000.0 + (random.random() * 10000.0)
            elif backend_id == "filecoin":
                return 5000.0 + (random.random() * 5000.0)
            else:
                return None
        except Exception as e:
            logger.warning(f"Error getting capacity for {backend_id}: {e}")
            return None


# Add missing imports
import random