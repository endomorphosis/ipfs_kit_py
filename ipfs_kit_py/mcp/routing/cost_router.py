"""
Cost-Based Routing Module for Optimized Data Routing

This module enhances the data routing system with cost optimization capabilities:
- Cost-based routing algorithms to optimize for price vs performance
- Storage cost modeling for different backend providers
- Retrieval cost estimation and optimization
- Budget-aware routing decisions
- Cost prediction and analysis tools

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import asyncio
import json
import math
import time
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)


class CostOptimizationStrategy(Enum):
    """Strategy for cost optimization."""
    LOWEST_COST = "lowest_cost"  # Optimize for lowest absolute cost
    BEST_VALUE = "best_value"    # Balance cost vs performance
    PERFORMANCE = "performance"  # Prioritize performance, with cost as secondary factor
    BUDGET = "budget"            # Stay within budget constraints
    CUSTOM = "custom"            # Custom optimization strategy


@dataclass
class StorageCostModel:
    """Cost model for a storage backend."""
    backend_id: str
    
    # Storage costs (per GB per month)
    storage_cost_per_gb_month: float = 0.0
    min_storage_cost: float = 0.0  # Minimum cost regardless of size
    
    # Retrieval costs
    retrieval_cost_per_gb: float = 0.0
    retrieval_cost_per_request: float = 0.0
    
    # API costs
    api_cost_per_request: float = 0.0
    
    # Free tier limits
    free_storage_gb: float = 0.0
    free_retrieval_gb: float = 0.0
    free_requests_per_month: int = 0
    
    # Contract terms
    min_duration_months: int = 0
    
    # Egress/Bandwidth costs
    egress_cost_per_gb: float = 0.0
    
    # Processing costs
    processing_cost_per_request: float = 0.0
    
    # Tiered pricing flag
    has_tiered_pricing: bool = False
    
    # Region-specific multiplier
    region_cost_multiplier: Dict[str, float] = field(default_factory=dict)
    
    # Last updated
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "backend_id": self.backend_id,
            "storage_cost": {
                "per_gb_month": self.storage_cost_per_gb_month,
                "min_cost": self.min_storage_cost
            },
            "retrieval_cost": {
                "per_gb": self.retrieval_cost_per_gb,
                "per_request": self.retrieval_cost_per_request
            },
            "api_cost_per_request": self.api_cost_per_request,
            "free_tier": {
                "storage_gb": self.free_storage_gb,
                "retrieval_gb": self.free_retrieval_gb,
                "requests_per_month": self.free_requests_per_month
            },
            "min_duration_months": self.min_duration_months,
            "egress_cost_per_gb": self.egress_cost_per_gb,
            "processing_cost_per_request": self.processing_cost_per_request,
            "has_tiered_pricing": self.has_tiered_pricing,
            "region_cost_multiplier": self.region_cost_multiplier,
            "last_updated": self.last_updated.isoformat()
        }


@dataclass
class CostEstimate:
    """Cost estimate for a storage operation."""
    backend_id: str
    operation_type: str  # "store", "retrieve", "maintain"
    
    # Estimated costs
    storage_cost: float = 0.0
    retrieval_cost: float = 0.0
    api_cost: float = 0.0
    egress_cost: float = 0.0
    processing_cost: float = 0.0
    
    # Total cost
    total_cost: float = 0.0
    
    # Size and duration factors
    size_bytes: int = 0
    duration_months: float = 1.0
    
    # Confidence level (0.0-1.0)
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "backend_id": self.backend_id,
            "operation_type": self.operation_type,
            "costs": {
                "storage": self.storage_cost,
                "retrieval": self.retrieval_cost,
                "api": self.api_cost,
                "egress": self.egress_cost,
                "processing": self.processing_cost,
                "total": self.total_cost
            },
            "factors": {
                "size_bytes": self.size_bytes,
                "duration_months": self.duration_months
            },
            "confidence": self.confidence
        }


@dataclass
class BudgetConstraint:
    """Budget constraint for routing decisions."""
    max_storage_cost_per_month: float = float("inf")
    max_retrieval_cost_per_gb: float = float("inf")
    max_cost_per_operation: float = float("inf")
    
    # Performance requirements under budget constraints
    min_performance_score: float = 0.0  # Minimum acceptable performance score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_storage_cost_per_month": self.max_storage_cost_per_month if self.max_storage_cost_per_month != float("inf") else None,
            "max_retrieval_cost_per_gb": self.max_retrieval_cost_per_gb if self.max_retrieval_cost_per_gb != float("inf") else None,
            "max_cost_per_operation": self.max_cost_per_operation if self.max_cost_per_operation != float("inf") else None,
            "min_performance_score": self.min_performance_score
        }


class CostRouter:
    """
    Router that optimizes backend selection based on cost factors.
    
    This class implements cost-based optimization for content routing,
    selecting backends that minimize cost while meeting performance requirements.
    """
    
    def __init__(self):
        """Initialize the cost router."""
        self.cost_models: Dict[str, StorageCostModel] = {}
        self.default_strategy = CostOptimizationStrategy.BEST_VALUE
        self.budget_constraint: Optional[BudgetConstraint] = None
        
        # Performance scores for backends (0.0-1.0, higher is better)
        self.performance_scores: Dict[str, float] = {}
        
        # Initialize with default cost models
        self._initialize_default_cost_models()
    
    def _initialize_default_cost_models(self) -> None:
        """Initialize with default cost models for common backends."""
        # IPFS cost model
        ipfs_model = StorageCostModel(
            backend_id="ipfs",
            storage_cost_per_gb_month=0.5,  # Assuming average IPFS pinning service cost
            retrieval_cost_per_gb=0.05,
            api_cost_per_request=0.0001,
            free_storage_gb=1.0,
            free_retrieval_gb=10.0,
            free_requests_per_month=1000,
            has_tiered_pricing=True
        )
        
        # Filecoin cost model
        filecoin_model = StorageCostModel(
            backend_id="filecoin",
            storage_cost_per_gb_month=0.18,  # Filecoin is generally cheaper for longer-term storage
            min_storage_cost=0.05,  # Minimum deal size has a cost floor
            retrieval_cost_per_gb=0.08,  # Retrievals can be more expensive due to deal mechanics
            min_duration_months=6,  # Filecoin typically has minimum deal durations
            has_tiered_pricing=True
        )
        
        # S3 cost model
        s3_model = StorageCostModel(
            backend_id="s3",
            storage_cost_per_gb_month=0.023,  # Standard S3 storage
            retrieval_cost_per_gb=0.0,        # No direct retrieval cost
            retrieval_cost_per_request=0.0004, # GET request cost
            api_cost_per_request=0.0005,      # PUT, COPY, POST request cost
            free_storage_gb=5.0,              # Free tier
            free_requests_per_month=2000,
            egress_cost_per_gb=0.09,          # Outbound data transfer
            has_tiered_pricing=True,
            region_cost_multiplier={          # Some regions are more expensive
                "us-east-1": 1.0,             # Base multiplier
                "eu-west-1": 1.1,             # 10% more expensive
                "ap-northeast-1": 1.2         # 20% more expensive
            }
        )
        
        # Storacha (hypothetical distributed storage service) cost model
        storacha_model = StorageCostModel(
            backend_id="storacha",
            storage_cost_per_gb_month=0.3,
            retrieval_cost_per_gb=0.02,
            api_cost_per_request=0.0002,
            free_storage_gb=2.0,
            free_retrieval_gb=5.0,
            has_tiered_pricing=False
        )
        
        # HuggingFace cost model
        huggingface_model = StorageCostModel(
            backend_id="huggingface",
            storage_cost_per_gb_month=0.4,     # Higher cost for specialized ML model storage
            retrieval_cost_per_gb=0.1,
            processing_cost_per_request=0.001, # Higher processing costs for ML model hosting
            has_tiered_pricing=True
        )
        
        # Lassie (IPFS retrieval tool) cost model
        lassie_model = StorageCostModel(
            backend_id="lassie",
            storage_cost_per_gb_month=0.0,     # No storage, retrieval service only
            retrieval_cost_per_gb=0.08,
            api_cost_per_request=0.001,
            has_tiered_pricing=False
        )
        
        # Add models to the dictionary
        self.cost_models = {
            "ipfs": ipfs_model,
            "filecoin": filecoin_model,
            "s3": s3_model,
            "storacha": storacha_model,
            "huggingface": huggingface_model,
            "lassie": lassie_model
        }
        
        # Initialize performance scores (simulated)
        self.performance_scores = {
            "ipfs": 0.75,       # Good general performance
            "filecoin": 0.65,   # Lower performance, better for archival
            "s3": 0.9,          # High performance
            "storacha": 0.8,    # Good performance
            "huggingface": 0.85, # Good for ML models
            "lassie": 0.7       # Moderate performance
        }
    
    def set_cost_model(self, model: StorageCostModel) -> None:
        """
        Set or update the cost model for a backend.
        
        Args:
            model: Storage cost model
        """
        self.cost_models[model.backend_id] = model
    
    def get_cost_model(self, backend_id: str) -> Optional[StorageCostModel]:
        """
        Get the cost model for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            StorageCostModel or None if not found
        """
        return self.cost_models.get(backend_id)
    
    def set_performance_score(self, backend_id: str, score: float) -> None:
        """
        Set the performance score for a backend.
        
        Args:
            backend_id: Backend identifier
            score: Performance score (0.0-1.0, higher is better)
        """
        self.performance_scores[backend_id] = max(0.0, min(1.0, score))
    
    def get_performance_score(self, backend_id: str) -> float:
        """
        Get the performance score for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Performance score (0.0-1.0)
        """
        return self.performance_scores.get(backend_id, 0.5)  # Default to average if unknown
    
    def set_budget_constraint(self, constraint: BudgetConstraint) -> None:
        """
        Set a budget constraint for routing decisions.
        
        Args:
            constraint: Budget constraint
        """
        self.budget_constraint = constraint
    
    def clear_budget_constraint(self) -> None:
        """Clear any budget constraint."""
        self.budget_constraint = None
    
    def estimate_storage_cost(
        self,
        backend_id: str,
        size_bytes: int,
        duration_months: float = 1.0,
        region_id: Optional[str] = None
    ) -> CostEstimate:
        """
        Estimate the cost to store content on a backend.
        
        Args:
            backend_id: Backend identifier
            size_bytes: Size in bytes
            duration_months: Storage duration in months
            region_id: Optional region identifier
            
        Returns:
            CostEstimate object
        """
        model = self.cost_models.get(backend_id)
        if not model:
            # Return default estimate if no model found
            return CostEstimate(
                backend_id=backend_id,
                operation_type="store",
                size_bytes=size_bytes,
                duration_months=duration_months,
                confidence=0.5
            )
        
        # Calculate base storage cost
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Apply free tier if applicable
        effective_size_gb = max(0.0, size_gb - model.free_storage_gb)
        
        # Calculate costs
        storage_cost = effective_size_gb * model.storage_cost_per_gb_month * duration_months
        
        # Apply minimum cost if applicable
        storage_cost = max(storage_cost, model.min_storage_cost)
        
        # API cost for storage operation
        api_cost = model.api_cost_per_request
        
        # Processing cost
        processing_cost = model.processing_cost_per_request
        
        # Apply region-specific multiplier if applicable
        if region_id and region_id in model.region_cost_multiplier:
            multiplier = model.region_cost_multiplier[region_id]
            storage_cost *= multiplier
            api_cost *= multiplier
            processing_cost *= multiplier
        
        # Calculate total cost
        total_cost = storage_cost + api_cost + processing_cost
        
        # Create and return estimate
        estimate = CostEstimate(
            backend_id=backend_id,
            operation_type="store",
            storage_cost=storage_cost,
            api_cost=api_cost,
            processing_cost=processing_cost,
            total_cost=total_cost,
            size_bytes=size_bytes,
            duration_months=duration_months,
            confidence=0.9  # High confidence for storage estimates
        )
        
        return estimate
    
    def estimate_retrieval_cost(
        self,
        backend_id: str,
        size_bytes: int,
        num_requests: int = 1,
        region_id: Optional[str] = None
    ) -> CostEstimate:
        """
        Estimate the cost to retrieve content from a backend.
        
        Args:
            backend_id: Backend identifier
            size_bytes: Size in bytes
            num_requests: Number of retrieval requests
            region_id: Optional region identifier
            
        Returns:
            CostEstimate object
        """
        model = self.cost_models.get(backend_id)
        if not model:
            # Return default estimate if no model found
            return CostEstimate(
                backend_id=backend_id,
                operation_type="retrieve",
                size_bytes=size_bytes,
                confidence=0.5
            )
        
        # Calculate base retrieval cost
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Apply free tier if applicable
        effective_size_gb = max(0.0, size_gb - model.free_retrieval_gb)
        effective_requests = max(0, num_requests - model.free_requests_per_month)
        
        # Calculate costs
        retrieval_cost = (effective_size_gb * model.retrieval_cost_per_gb) + (effective_requests * model.retrieval_cost_per_request)
        
        # API cost for retrieval operations
        api_cost = effective_requests * model.api_cost_per_request
        
        # Egress/bandwidth cost
        egress_cost = effective_size_gb * model.egress_cost_per_gb
        
        # Processing cost
        processing_cost = effective_requests * model.processing_cost_per_request
        
        # Apply region-specific multiplier if applicable
        if region_id and region_id in model.region_cost_multiplier:
            multiplier = model.region_cost_multiplier[region_id]
            retrieval_cost *= multiplier
            api_cost *= multiplier
            egress_cost *= multiplier
            processing_cost *= multiplier
        
        # Calculate total cost
        total_cost = retrieval_cost + api_cost + egress_cost + processing_cost
        
        # Create and return estimate
        estimate = CostEstimate(
            backend_id=backend_id,
            operation_type="retrieve",
            retrieval_cost=retrieval_cost,
            api_cost=api_cost,
            egress_cost=egress_cost,
            processing_cost=processing_cost,
            total_cost=total_cost,
            size_bytes=size_bytes,
            confidence=0.8  # Good confidence for retrieval estimates
        )
        
        return estimate
    
    def estimate_maintenance_cost(
        self,
        backend_id: str,
        size_bytes: int,
        duration_months: float = 1.0,
        region_id: Optional[str] = None
    ) -> CostEstimate:
        """
        Estimate the cost to maintain content on a backend over time.
        
        Args:
            backend_id: Backend identifier
            size_bytes: Size in bytes
            duration_months: Maintenance duration in months
            region_id: Optional region identifier
            
        Returns:
            CostEstimate object
        """
        model = self.cost_models.get(backend_id)
        if not model:
            # Return default estimate if no model found
            return CostEstimate(
                backend_id=backend_id,
                operation_type="maintain",
                size_bytes=size_bytes,
                duration_months=duration_months,
                confidence=0.5
            )
        
        # Maintenance is essentially just storage cost over time for most backends
        storage_estimate = self.estimate_storage_cost(
            backend_id=backend_id,
            size_bytes=size_bytes,
            duration_months=duration_months,
            region_id=region_id
        )
        
        # For some backends like Filecoin, there might be additional renewal costs
        # but we'll keep it simple for now
        
        # Create maintenance estimate based on storage estimate
        estimate = CostEstimate(
            backend_id=backend_id,
            operation_type="maintain",
            storage_cost=storage_estimate.storage_cost,
            api_cost=0.0,  # No additional API costs for maintenance
            total_cost=storage_estimate.storage_cost,  # Total is just storage for maintenance
            size_bytes=size_bytes,
            duration_months=duration_months,
            confidence=storage_estimate.confidence
        )
        
        return estimate
    
    def estimate_total_cost(
        self,
        backend_id: str,
        size_bytes: int,
        duration_months: float = 1.0,
        num_retrievals: int = 1,
        region_id: Optional[str] = None
    ) -> CostEstimate:
        """
        Estimate the total cost for storing and retrieving content.
        
        Args:
            backend_id: Backend identifier
            size_bytes: Size in bytes
            duration_months: Storage duration in months
            num_retrievals: Expected number of retrievals
            region_id: Optional region identifier
            
        Returns:
            CostEstimate object
        """
        # Get individual estimates
        storage_estimate = self.estimate_storage_cost(
            backend_id=backend_id,
            size_bytes=size_bytes,
            duration_months=duration_months,
            region_id=region_id
        )
        
        retrieval_estimate = self.estimate_retrieval_cost(
            backend_id=backend_id,
            size_bytes=size_bytes,
            num_requests=num_retrievals,
            region_id=region_id
        )
        
        # Combine costs
        total_estimate = CostEstimate(
            backend_id=backend_id,
            operation_type="total",
            storage_cost=storage_estimate.storage_cost,
            retrieval_cost=retrieval_estimate.retrieval_cost,
            api_cost=storage_estimate.api_cost + retrieval_estimate.api_cost,
            egress_cost=retrieval_estimate.egress_cost,
            processing_cost=storage_estimate.processing_cost + retrieval_estimate.processing_cost,
            size_bytes=size_bytes,
            duration_months=duration_months,
            confidence=min(storage_estimate.confidence, retrieval_estimate.confidence)
        )
        
        # Calculate total
        total_estimate.total_cost = (
            total_estimate.storage_cost +
            total_estimate.retrieval_cost +
            total_estimate.api_cost +
            total_estimate.egress_cost +
            total_estimate.processing_cost
        )
        
        return total_estimate
    
    def select_backend_by_cost(
        self,
        size_bytes: int,
        available_backends: Optional[List[str]] = None,
        duration_months: float = 1.0,
        num_retrievals: int = 1,
        strategy: Optional[CostOptimizationStrategy] = None,
        min_performance_score: float = 0.0,
        region_id: Optional[str] = None
    ) -> Tuple[str, CostEstimate]:
        """
        Select the optimal backend based on cost.
        
        Args:
            size_bytes: Size in bytes
            available_backends: Optional list of available backends
            duration_months: Storage duration in months
            num_retrievals: Expected number of retrievals
            strategy: Cost optimization strategy
            min_performance_score: Minimum required performance score
            region_id: Optional region identifier
            
        Returns:
            Tuple of (selected_backend_id, cost_estimate)
        """
        # Use default strategy if not specified
        if strategy is None:
            strategy = self.default_strategy
        
        # Get available backends
        if available_backends is None:
            available_backends = list(self.cost_models.keys())
        
        # Filter backends by cost models
        backends_with_models = [
            backend_id for backend_id in available_backends
            if backend_id in self.cost_models
        ]
        
        # If no backends with models, return default
        if not backends_with_models:
            if available_backends:
                return available_backends[0], CostEstimate(
                    backend_id=available_backends[0],
                    operation_type="total",
                    size_bytes=size_bytes,
                    duration_months=duration_months,
                    confidence=0.5
                )
            return "ipfs", CostEstimate(
                backend_id="ipfs",
                operation_type="total",
                size_bytes=size_bytes,
                duration_months=duration_months,
                confidence=0.5
            )
        
        # Apply budget constraints if set
        if self.budget_constraint:
            min_performance_score = max(min_performance_score, self.budget_constraint.min_performance_score)
        
        # Calculate estimates for each backend
        backend_estimates = {}
        for backend_id in backends_with_models:
            # Check if backend meets minimum performance requirement
            if self.get_performance_score(backend_id) < min_performance_score:
                continue
                
            # Get cost estimate
            estimate = self.estimate_total_cost(
                backend_id=backend_id,
                size_bytes=size_bytes,
                duration_months=duration_months,
                num_retrievals=num_retrievals,
                region_id=region_id
            )
            
            # Apply budget constraints if set
            if self.budget_constraint:
                if estimate.storage_cost > self.budget_constraint.max_storage_cost_per_month * duration_months:
                    continue
                
                if size_bytes > 0 and (estimate.retrieval_cost / (size_bytes / (1024*1024*1024))) > self.budget_constraint.max_retrieval_cost_per_gb:
                    continue
                    
                if estimate.total_cost > self.budget_constraint.max_cost_per_operation:
                    continue
            
            backend_estimates[backend_id] = estimate
        
        # If no backends meet criteria, relax constraints and try again
        if not backend_estimates:
            # Try again without performance requirements
            return self.select_backend_by_cost(
                size_bytes=size_bytes,
                available_backends=available_backends,
                duration_months=duration_months,
                num_retrievals=num_retrievals,
                strategy=strategy,
                min_performance_score=0.0,  # No minimum performance
                region_id=region_id
            )
        
        # Select backend based on strategy
        if strategy == CostOptimizationStrategy.LOWEST_COST:
            # Select lowest total cost
            selected_backend = min(
                backend_estimates.items(),
                key=lambda x: x[1].total_cost
            )[0]
            
        elif strategy == CostOptimizationStrategy.PERFORMANCE:
            # Select highest performance that meets budget constraints
            performance_scores = {
                backend_id: self.get_performance_score(backend_id)
                for backend_id in backend_estimates
            }
            
            selected_backend = max(
                performance_scores.items(),
                key=lambda x: x[1]
            )[0]
            
        elif strategy == CostOptimizationStrategy.BUDGET:
            # Select lowest cost within budget constraints
            selected_backend = min(
                backend_estimates.items(),
                key=lambda x: x[1].total_cost
            )[0]
            
        elif strategy == CostOptimizationStrategy.BEST_VALUE:
            # Calculate value score (performance / cost)
            value_scores = {}
            
            for backend_id, estimate in backend_estimates.items():
                performance = self.get_performance_score(backend_id)
                
                # Avoid division by zero
                if estimate.total_cost <= 0:
                    value_scores[backend_id] = performance * 100  # Arbitrary high value
                else:
                    # Value is performance per dollar
                    value_scores[backend_id] = performance / estimate.total_cost
            
            # Select highest value
            if value_scores:
                selected_backend = max(
                    value_scores.items(),
                    key=lambda x: x[1]
                )[0]
            else:
                # Fallback to lowest cost
                selected_backend = min(
                    backend_estimates.items(),
                    key=lambda x: x[1].total_cost
                )[0]
        
        else:  # CUSTOM or unknown
            # Default to best value
            return self.select_backend_by_cost(
                size_bytes=size_bytes,
                available_backends=available_backends,
                duration_months=duration_months,
                num_retrievals=num_retrievals,
                strategy=CostOptimizationStrategy.BEST_VALUE,
                min_performance_score=min_performance_score,
                region_id=region_id
            )
        
        return selected_backend, backend_estimates[selected_backend]
    
    def rank_backends_by_value(
        self,
        size_bytes: int,
        available_backends: Optional[List[str]] = None,
        duration_months: float = 1.0,
        num_retrievals: int = 1,
        region_id: Optional[str] = None
    ) -> List[Tuple[str, float, CostEstimate]]:
        """
        Rank backends by value (performance/cost).
        
        Args:
            size_bytes: Size in bytes
            available_backends: Optional list of available backends
            duration_months: Storage duration in months
            num_retrievals: Expected number of retrievals
            region_id: Optional region identifier
            
        Returns:
            List of (backend_id, value_score, cost_estimate) tuples sorted by value
        """
        # Get available backends
        if available_backends is None:
            available_backends = list(self.cost_models.keys())
        
        # Calculate value scores for each backend
        value_scores = []
        
        for backend_id in available_backends:
            if backend_id not in self.cost_models:
                continue
                
            # Get cost estimate
            estimate = self.estimate_total_cost(
                backend_id=backend_id,
                size_bytes=size_bytes,
                duration_months=duration_months,
                num_retrievals=num_retrievals,
                region_id=region_id
            )
            
            # Get performance score
            performance = self.get_performance_score(backend_id)
            
            # Calculate value (performance / cost)
            if estimate.total_cost <= 0:
                value = performance * 100  # Arbitrary high value for free services
            else:
                value = performance / estimate.total_cost
            
            value_scores.append((backend_id, value, estimate))
        
        # Sort by value (higher is better)
        return sorted(value_scores, key=lambda x: x[1], reverse=True)
    
    def compare_backend_costs(
        self,
        size_bytes: int,
        backend_ids: List[str],
        duration_months: float = 1.0,
        num_retrievals: int = 1,
        region_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare costs across multiple backends.
        
        Args:
            size_bytes: Size in bytes
            backend_ids: List of backend identifiers to compare
            duration_months: Storage duration in months
            num_retrievals: Expected number of retrievals
            region_id: Optional region identifier
            
        Returns:
            Dict mapping backend IDs to comparison data
        """
        results = {}
        
        # Generate estimates for each backend
        for backend_id in backend_ids:
            # Skip backends without cost models
            if backend_id not in self.cost_models:
                continue
                
            # Get cost estimate
            estimate = self.estimate_total_cost(
                backend_id=backend_id,
                size_bytes=size_bytes,
                duration_months=duration_months,
                num_retrievals=num_retrievals,
                region_id=region_id
            )
            
            # Get performance score
            performance = self.get_performance_score(backend_id)
            
            # Calculate value score
            if estimate.total_cost <= 0:
                value_score = performance * 100  # Arbitrary high value for free services
            else:
                value_score = performance / estimate.total_cost
            
            # Add to results
            results[backend_id] = {
                "cost_estimate": estimate.to_dict(),
                "performance_score": performance,
                "value_score": value_score
            }
        
        # Calculate rankings
        if results:
            # Rank by total cost (lower is better)
            cost_ranking = sorted(
                results.keys(),
                key=lambda backend_id: results[backend_id]["cost_estimate"]["costs"]["total"]
            )
            
            # Rank by performance (higher is better)
            performance_ranking = sorted(
                results.keys(),
                key=lambda backend_id: results[backend_id]["performance_score"],
                reverse=True
            )
            
            # Rank by value (higher is better)
            value_ranking = sorted(
                results.keys(),
                key=lambda backend_id: results[backend_id]["value_score"],
                reverse=True
            )
            
            # Add rankings to results
            for backend_id in results:
                results[backend_id]["rankings"] = {
                    "cost_rank": cost_ranking.index(backend_id) + 1,
                    "performance_rank": performance_ranking.index(backend_id) + 1,
                    "value_rank": value_ranking.index(backend_id) + 1
                }
        
        return results
    
    def estimate_cost_savings(
        self,
        source_backend_id: str,
        target_backend_id: str,
        size_bytes: int,
        duration_months: float = 12.0,
        num_retrievals: int = 10,
        region_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estimate cost savings from moving content between backends.
        
        Args:
            source_backend_id: Source backend identifier
            target_backend_id: Target backend identifier
            size_bytes: Size in bytes
            duration_months: Storage duration in months
            num_retrievals: Expected number of retrievals
            region_id: Optional region identifier
            
        Returns:
            Dict with cost savings analysis
        """
        # Get cost estimates for source and target backends
        source_estimate = self.estimate_total_cost(
            backend_id=source_backend_id,
            size_bytes=size_bytes,
            duration_months=duration_months,
            num_retrievals=num_retrievals,
            region_id=region_id
        )
        
        target_estimate = self.estimate_total_cost(
            backend_id=target_backend_id,
            size_bytes=size_bytes,
            duration_months=duration_months,
            num_retrievals=num_retrievals,
            region_id=region_id
        )
        
        # Calculate savings
        savings = source_estimate.total_cost - target_estimate.total_cost
        savings_percent = (savings / source_estimate.total_cost) * 100 if source_estimate.total_cost > 0 else 0
        
        # Calculate migration cost (estimate as one retrieval from source + one storage to target)
        migration_retrieval = self.estimate_retrieval_cost(
            backend_id=source_backend_id,
            size_bytes=size_bytes,
            num_requests=1,
            region_id=region_id
        )
        
        migration_storage = self.estimate_storage_cost(
            backend_id=target_backend_id,
            size_bytes=size_bytes,
            duration_months=0.0,  # Just the initial storage operation
            region_id=region_id
        )
        
        migration_cost = migration_retrieval.total_cost + migration_storage.total_cost
        
        # Calculate net savings
        net_savings = savings - migration_cost
        
        # Calculate performance impact
        source_performance = self.get_performance_score(source_backend_id)
        target_performance = self.get_performance_score(target_backend_id)
        performance_change = target_performance - source_performance
        performance_change_percent = (performance_change / source_performance) * 100 if source_performance > 0 else 0
        
        # Calculate break-even point (in months)
        break_even_months = 0.0
        if savings > 0:
            # Monthly savings
            monthly_savings = savings / duration_months
            
            # Break-even point
            if monthly_savings > 0:
                break_even_months = migration_cost / monthly_savings
        
        # Create result
        result = {
            "source_backend": source_backend_id,
            "target_backend": target_backend_id,
            "content_size_bytes": size_bytes,
            "content_size_gb": size_bytes / (1024 * 1024 * 1024),
            "duration_months": duration_months,
            "num_retrievals": num_retrievals,
            "costs": {
                "source_total": source_estimate.total_cost,
                "target_total": target_estimate.total_cost,
                "migration_cost": migration_cost
            },
            "savings": {
                "gross_savings": savings,
                "savings_percent": savings_percent,
                "net_savings": net_savings
            },
            "performance": {
                "source_score": source_performance,
                "target_score": target_performance,
                "change": performance_change,
                "change_percent": performance_change_percent
            },
            "break_even": {
                "months": break_even_months if break_even_months > 0 else None,
                "years": break_even_months / 12 if break_even_months > 0 else None
            },
            "recommendation": {
                "should_migrate": net_savings > 0,
                "reason": ""
            }
        }
        
        # Add recommendation reason
        if net_savings <= 0:
            result["recommendation"]["reason"] = "Migration costs exceed savings"
        elif performance_change < 0 and abs(performance_change_percent) > 10:
            result["recommendation"]["reason"] = "Performance degradation exceeds 10%"
        elif break_even_months > duration_months:
            result["recommendation"]["reason"] = "Break-even point exceeds planned storage duration"
        else:
            result["recommendation"]["reason"] = "Migration provides cost savings with acceptable performance"
        
        return result
    
    def optimize_multi_backend_storage(
        self,
        size_bytes: int,
        duration_months: float = 12.0,
        num_retrievals: int = 10,
        available_backends: Optional[List[str]] = None,
        min_redundancy: int = 1,
        max_backends: int = 2,
        region_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Optimize storage across multiple backends for redundancy and cost-effectiveness.
        
        Args:
            size_bytes: Size in bytes
            duration_months: Storage duration in months
            num_retrievals: Expected number of retrievals
            available_backends: Optional list of available backends
            min_redundancy: Minimum number of backends for redundancy
            max_backends: Maximum number of backends to use
            region_id: Optional region identifier
            
        Returns:
            Dict with multi-backend optimization results
        """
        # Get available backends
        if available_backends is None:
            available_backends = list(self.cost_models.keys())
        
        # Ensure min_redundancy <= max_backends
        min_redundancy = min(min_redundancy, max_backends)
        
        # Rank backends by value
        ranked_backends = self.rank_backends_by_value(
            size_bytes=size_bytes,
            available_backends=available_backends,
            duration_months=duration_months,
            num_retrievals=num_retrievals,
            region_id=region_id
        )
        
        # Ensure we have enough backends
        if len(ranked_backends) < min_redundancy:
            # Not enough backends for desired redundancy
            return {
                "success": False,
                "error": f"Not enough backends available for desired redundancy ({len(ranked_backends)} < {min_redundancy})"
            }
        
        # Select top backends up to max_backends
        selected_backends = ranked_backends[:max_backends]
        
        # Calculate total cost
        total_cost = sum(estimate.total_cost for _, _, estimate in selected_backends)
        
        # Calculate weighted performance score
        # (backends with higher value scores contribute more to the overall performance)
        total_value = sum(value for _, value, _ in selected_backends)
        weighted_performance = 0.0
        
        if total_value > 0:
            for backend_id, value, _ in selected_backends:
                performance = self.get_performance_score(backend_id)
                weight = value / total_value
                weighted_performance += performance * weight
        
        # Create result
        result = {
            "success": True,
            "content_size_bytes": size_bytes,
            "content_size_gb": size_bytes / (1024 * 1024 * 1024),
            "duration_months": duration_months,
            "num_retrievals": num_retrievals,
            "redundancy": len(selected_backends),
            "selected_backends": [
                {
                    "backend_id": backend_id,
                    "value_score": value,
                    "performance_score": self.get_performance_score(backend_id),
                    "cost_estimate": estimate.to_dict()
                }
                for backend_id, value, estimate in selected_backends
            ],
            "total_cost": total_cost,
            "weighted_performance": weighted_performance
        }
        
        return result
    
    def get_all_cost_models(self) -> Dict[str, StorageCostModel]:
        """
        Get all cost models.
        
        Returns:
            Dict mapping backend IDs to StorageCostModel objects
        """
        return self.cost_models.copy()


# Factory function to create a cost router
def create_cost_router() -> CostRouter:
    """
    Create a cost router.
    
    Returns:
        CostRouter instance
    """
    return CostRouter()