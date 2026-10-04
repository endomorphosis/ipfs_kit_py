"""
Cost Optimization for Storage Backend Selection

This module implements cost analysis and optimization for selecting
the most cost-effective storage backend for different operations.
"""

import math
import logging
import threading
from typing import Dict, List, Any, Optional, Set

from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class CostOptimizer:
    """
    Cost optimization for storage backends.
    
    This component tracks and predicts costs for different backends
    to enable cost-optimized routing decisions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the cost optimizer.
        
        Args:
            config: Cost optimizer configuration
        """
        self.config = config or {}
        
        # Cost models: backend -> cost model dict
        self.cost_models = self.config.get("cost_models", {})
        
        # Default cost model for new backends
        self.default_cost_model = {
            "storage_cost_per_gb_month": 0.0,  # USD per GB per month
            "retrieval_cost_per_gb": 0.0,      # USD per GB retrieved
            "operation_cost": 0.0,             # USD per operation
            "minimum_storage_duration": 0,     # Minimum duration in seconds
            "size_overhead_factor": 1.0,       # Factor for additional size overhead
        }
        
        # Initialize with realistic default costs if not provided
        if not self.cost_models:
            self._initialize_default_cost_models()
        
        # Lock for thread safety
        self.lock = threading.RLock()
    
    def _initialize_default_cost_models(self):
        """Initialize default cost models with realistic values."""
        # IPFS cost model (estimating IPFS pinning service costs)
        self.cost_models[StorageBackendType.IPFS.value] = {
            "storage_cost_per_gb_month": 0.15,  # $0.15 per GB per month (estimation)
            "retrieval_cost_per_gb": 0.0,       # Free retrieval
            "operation_cost": 0.0001,           # Small cost per operation
            "minimum_storage_duration": 30 * 24 * 60 * 60,  # 30 days minimum
            "size_overhead_factor": 1.05,       # 5% overhead
        }
        
        # S3 cost model (based on AWS S3 standard pricing)
        self.cost_models[StorageBackendType.S3.value] = {
            "storage_cost_per_gb_month": 0.023,  # $0.023 per GB per month
            "retrieval_cost_per_gb": 0.0,        # Free for standard retrievals
            "operation_cost": 0.0004,            # $0.0004 per PUT/COPY/POST/LIST request
            "minimum_storage_duration": 0,       # No minimum duration
            "size_overhead_factor": 1.0,         # No overhead
        }
        
        # Filecoin cost model
        self.cost_models[StorageBackendType.FILECOIN.value] = {
            "storage_cost_per_gb_month": 0.0034,  # Approx $0.0034 per GB per month
            "retrieval_cost_per_gb": 0.01,        # Retrieval fees
            "operation_cost": 0.01,               # Higher operation cost due to blockchain fees
            "minimum_storage_duration": 180 * 24 * 60 * 60,  # 6 months minimum
            "size_overhead_factor": 1.1,          # 10% overhead
        }
        
        # Storacha (Web3.Storage) cost model
        self.cost_models[StorageBackendType.STORACHA.value] = {
            "storage_cost_per_gb_month": 0.25,    # $0.25 per GB per month (estimation)
            "retrieval_cost_per_gb": 0.0,         # Free retrieval
            "operation_cost": 0.0001,             # Small cost per operation
            "minimum_storage_duration": 30 * 24 * 60 * 60,  # 30 days minimum
            "size_overhead_factor": 1.05,         # 5% overhead
        }
        
        # HuggingFace cost model
        self.cost_models[StorageBackendType.HUGGINGFACE.value] = {
            "storage_cost_per_gb_month": 0.07,    # $0.07 per GB per month (estimation)
            "retrieval_cost_per_gb": 0.01,        # Small retrieval fee
            "operation_cost": 0.001,              # Operation cost
            "minimum_storage_duration": 0,        # No minimum duration
            "size_overhead_factor": 1.0,          # No overhead
        }
        
        # Lassie cost model (assuming similar to IPFS)
        self.cost_models[StorageBackendType.LASSIE.value] = {
            "storage_cost_per_gb_month": 0.15,    # $0.15 per GB per month (estimation)
            "retrieval_cost_per_gb": 0.0,         # Free retrieval
            "operation_cost": 0.0001,             # Small cost per operation
            "minimum_storage_duration": 30 * 24 * 60 * 60,  # 30 days minimum
            "size_overhead_factor": 1.05,         # 5% overhead
        }
    
    def get_cost_model(self, backend_type: StorageBackendType) -> Dict[str, float]:
        """
        Get the cost model for a backend.
        
        Args:
            backend_type: Backend type
            
        Returns:
            Cost model dictionary
        """
        with self.lock:
            backend_name = backend_type.value
            
            # Get cost model or create default
            if backend_name not in self.cost_models:
                self.cost_models[backend_name] = self.default_cost_model.copy()
            
            return self.cost_models[backend_name]
    
    def update_cost_model(self, backend_type: StorageBackendType, model: Dict[str, float]):
        """
        Update the cost model for a backend.
        
        Args:
            backend_type: Backend type
            model: Cost model dictionary
        """
        with self.lock:
            backend_name = backend_type.value
            self.cost_models[backend_name] = model
    
    def estimate_storage_cost(
        self,
        backend_type: StorageBackendType,
        size_bytes: int,
        duration_seconds: int = 2592000,  # Default: 30 days
    ) -> float:
        """
        Estimate the cost of storing data.
        
        Args:
            backend_type: Backend type
            size_bytes: Size in bytes
            duration_seconds: Storage duration in seconds
            
        Returns:
            Estimated cost in USD
        """
        cost_model = self.get_cost_model(backend_type)
        
        # Convert size to GB
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Apply size overhead factor
        size_gb *= cost_model.get("size_overhead_factor", 1.0)
        
        # Calculate storage duration in months
        duration_months = duration_seconds / (30 * 24 * 60 * 60)
        
        # Apply minimum storage duration
        min_duration = cost_model.get("minimum_storage_duration", 0)
        if min_duration > 0:
            min_duration_months = min_duration / (30 * 24 * 60 * 60)
            duration_months = max(duration_months, min_duration_months)
        
        # Calculate storage cost
        storage_cost = (
            size_gb *
            duration_months *
            cost_model.get("storage_cost_per_gb_month", 0.0)
        )
        
        # Add operation cost
        storage_cost += cost_model.get("operation_cost", 0.0)
        
        return storage_cost
    
    def estimate_retrieval_cost(
        self,
        backend_type: StorageBackendType,
        size_bytes: int,
    ) -> float:
        """
        Estimate the cost of retrieving data.
        
        Args:
            backend_type: Backend type
            size_bytes: Size in bytes
            
        Returns:
            Estimated cost in USD
        """
        cost_model = self.get_cost_model(backend_type)
        
        # Convert size to GB
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Apply size overhead factor
        size_gb *= cost_model.get("size_overhead_factor", 1.0)
        
        # Calculate retrieval cost
        retrieval_cost = size_gb * cost_model.get("retrieval_cost_per_gb", 0.0)
        
        # Add operation cost
        retrieval_cost += cost_model.get("operation_cost", 0.0)
        
        return retrieval_cost
    
    def get_cost_score(
        self,
        backend_type: StorageBackendType,
        size_bytes: int,
        operation: str = "store",
        duration_seconds: int = 2592000,  # Default: 30 days
    ) -> float:
        """
        Calculate a cost score for a backend.
        
        Args:
            backend_type: Backend type
            size_bytes: Size in bytes
            operation: Operation type (store, retrieve)
            duration_seconds: Storage duration in seconds
            
        Returns:
            Cost score (higher is better = less expensive)
        """
        # Estimate cost
        if operation == "store":
            cost = self.estimate_storage_cost(backend_type, size_bytes, duration_seconds)
        else:
            cost = self.estimate_retrieval_cost(backend_type, size_bytes)
        
        # Convert cost to score (lower cost = higher score)
        # Use exponential function to prefer lower costs
        if cost <= 0:
            return 1.0  # Free backends get perfect score
        
        # Scale cost before applying exponential
        # This controls how sensitive we are to cost differences
        scaled_cost = cost * 10.0
        
        return math.exp(-scaled_cost)
    
    def get_cheapest_backend(
        self,
        backends: List[StorageBackendType],
        size_bytes: int,
        operation: str = "store",
        duration_seconds: int = 2592000,  # Default: 30 days
    ) -> Optional[StorageBackendType]:
        """
        Get the cheapest backend for an operation.
        
        Args:
            backends: List of available backends
            size_bytes: Size in bytes
            operation: Operation type (store, retrieve)
            duration_seconds: Storage duration in seconds
            
        Returns:
            Cheapest backend or None if no backends available
        """
        if not backends:
            return None
        
        # Calculate costs for each backend
        backend_costs = {}
        for backend in backends:
            if operation == "store":
                cost = self.estimate_storage_cost(backend, size_bytes, duration_seconds)
            else:
                cost = self.estimate_retrieval_cost(backend, size_bytes)
            
            backend_costs[backend] = cost
        
        # Find backend with lowest cost
        return min(backend_costs.items(), key=lambda x: x[1])[0]
    
    def get_backend_ranking(
        self,
        backends: List[StorageBackendType],
        size_bytes: int,
        operation: str = "store",
        duration_seconds: int = 2592000,  # Default: 30 days
    ) -> List[Dict[str, Any]]:
        """
        Get backends ranked by cost.
        
        Args:
            backends: List of available backends
            size_bytes: Size in bytes
            operation: Operation type (store, retrieve)
            duration_seconds: Storage duration in seconds
            
        Returns:
            List of backend info dictionaries with cost details
        """
        if not backends:
            return []
        
        # Calculate costs for each backend
        backend_infos = []
        for backend in backends:
            if operation == "store":
                cost = self.estimate_storage_cost(backend, size_bytes, duration_seconds)
                overhead = self.get_cost_model(backend).get("size_overhead_factor", 1.0)
                min_duration = self.get_cost_model(backend).get("minimum_storage_duration", 0)
                
                backend_infos.append({
                    "backend": backend,
                    "backend_name": backend.value,
                    "cost": cost,
                    "operation": operation,
                    "size_bytes": size_bytes,
                    "size_with_overhead": int(size_bytes * overhead),
                    "duration_seconds": max(duration_seconds, min_duration),
                    "cost_components": {
                        "storage": cost - self.get_cost_model(backend).get("operation_cost", 0.0),
                        "operation": self.get_cost_model(backend).get("operation_cost", 0.0)
                    }
                })
            else:
                cost = self.estimate_retrieval_cost(backend, size_bytes)
                overhead = self.get_cost_model(backend).get("size_overhead_factor", 1.0)
                
                backend_infos.append({
                    "backend": backend,
                    "backend_name": backend.value,
                    "cost": cost,
                    "operation": operation,
                    "size_bytes": size_bytes,
                    "size_with_overhead": int(size_bytes * overhead),
                    "cost_components": {
                        "retrieval": cost - self.get_cost_model(backend).get("operation_cost", 0.0),
                        "operation": self.get_cost_model(backend).get("operation_cost", 0.0)
                    }
                })
        
        # Sort by cost (cheapest first)
        backend_infos.sort(key=lambda x: x["cost"])
        
        return backend_infos
    
    def get_all_cost_models(self) -> Dict[str, Dict[str, float]]:
        """
        Get all cost models.
        
        Returns:
            Dictionary of all cost models
        """
        with self.lock:
            return self.cost_models.copy()


# Singleton instance
_instance = None

def get_instance(config: Optional[Dict[str, Any]] = None) -> CostOptimizer:
    """
    Get or create the singleton cost optimizer instance.
    
    Args:
        config: Optional cost optimizer configuration
        
    Returns:
        CostOptimizer instance
    """
    global _instance
    if _instance is None:
        _instance = CostOptimizer(config)
    return _instance