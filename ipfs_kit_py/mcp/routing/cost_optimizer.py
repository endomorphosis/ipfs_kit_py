"""
Cost-Based Routing Module for MCP Server

This module enhances the Optimized Data Routing feature with cost optimization:
- Cost prediction and modeling for different backends
- Budget-aware storage allocation
- Cost-optimized backend selection
- Usage-based pricing analysis
- Cost/performance trade-off optimization

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import logging
import time
import math
import json
import os
from enum import Enum
from typing import Dict, List, Tuple, Set, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import random

# Configure logging
logger = logging.getLogger("mcp.routing.cost")


class CostModelType(Enum):
    """Types of cost models for storage backends."""
    FLAT_RATE = "flat_rate"             # Fixed cost regardless of usage
    TIERED = "tiered"                   # Tiered pricing based on usage levels
    USAGE_BASED = "usage_based"         # Cost based on actual usage
    TIME_BASED = "time_based"           # Cost varies based on time (e.g., monthly)
    REGION_SPECIFIC = "region_specific" # Different costs in different regions
    HYBRID = "hybrid"                   # Combination of multiple cost factors
    CUSTOM = "custom"                   # Custom pricing model


class CostComponent(Enum):
    """Cost components for storage backends."""
    STORAGE = "storage"             # Cost of data storage
    BANDWIDTH_IN = "bandwidth_in"   # Cost of data ingress
    BANDWIDTH_OUT = "bandwidth_out" # Cost of data egress
    OPERATIONS = "operations"       # Cost of operations (API calls, etc.)
    PROCESSING = "processing"       # Cost of data processing
    MINIMUM = "minimum"             # Minimum cost (e.g., minimum monthly payment)
    OTHER = "other"                 # Other costs


@dataclass
class StorageCost:
    """Storage cost for a specific backend."""
    backend_id: str
    cost_per_gb_month: float = 0.0
    cost_per_million_ops: float = 0.0
    bandwidth_in_cost_per_gb: float = 0.0
    bandwidth_out_cost_per_gb: float = 0.0
    minimum_cost: float = 0.0
    cost_model_type: CostModelType = CostModelType.USAGE_BASED
    region_id: Optional[str] = None
    currency: str = "USD"
    tiered_pricing: Optional[Dict[str, Any]] = None
    custom_pricing: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "backend_id": self.backend_id,
            "cost_per_gb_month": self.cost_per_gb_month,
            "cost_per_million_ops": self.cost_per_million_ops,
            "bandwidth_in_cost_per_gb": self.bandwidth_in_cost_per_gb,
            "bandwidth_out_cost_per_gb": self.bandwidth_out_cost_per_gb,
            "minimum_cost": self.minimum_cost,
            "cost_model_type": self.cost_model_type.value,
            "currency": self.currency
        }
        
        if self.region_id:
            result["region_id"] = self.region_id
        
        if self.tiered_pricing:
            result["tiered_pricing"] = self.tiered_pricing
        
        if self.custom_pricing:
            result["custom_pricing"] = self.custom_pricing
        
        return result


@dataclass
class UsageEstimate:
    """Estimated usage for cost calculation."""
    storage_gb_months: float = 0.0
    operations_count: int = 0
    bandwidth_in_gb: float = 0.0
    bandwidth_out_gb: float = 0.0
    duration_months: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "storage_gb_months": self.storage_gb_months,
            "operations_count": self.operations_count,
            "bandwidth_in_gb": self.bandwidth_in_gb,
            "bandwidth_out_gb": self.bandwidth_out_gb,
            "duration_months": self.duration_months
        }


@dataclass
class CostEstimate:
    """Cost estimate for a specific backend."""
    backend_id: str
    total_cost: float
    component_costs: Dict[CostComponent, float]
    usage: UsageEstimate
    currency: str = "USD"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "backend_id": self.backend_id,
            "total_cost": self.total_cost,
            "component_costs": {
                component.value: cost
                for component, cost in self.component_costs.items()
            },
            "usage": self.usage.to_dict(),
            "currency": self.currency
        }


class CostOptimizer:
    """
    Cost optimization for storage backend selection.
    
    This class provides cost estimation and optimization capabilities
    for selecting the most cost-effective storage backend based on
    expected usage patterns.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the cost optimizer.
        
        Args:
            config_path: Path to cost configuration
        """
        # Backend cost models
        self.backend_costs: Dict[str, Dict[str, StorageCost]] = {}  # backend_id -> region_id -> StorageCost
        
        # Default (regionless) costs
        self.default_costs: Dict[str, StorageCost] = {}  # backend_id -> StorageCost
        
        # Budget constraints
        self.budget_constraints: Dict[str, float] = {}  # component -> budget
        
        # Price history for trending
        self.price_history: Dict[str, Dict[str, List[Tuple[datetime, float]]]] = {}  # backend_id -> component -> [(timestamp, price)]
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Load configuration
        if config_path:
            self.load_config(config_path)
        else:
            # Try default locations
            default_paths = [
                os.path.join(os.path.dirname(__file__), "cost_config.json"),
                os.path.join(os.path.expanduser("~"), ".ipfs_kit", "cost_config.json"),
                "/etc/ipfs_kit/cost_config.json"
            ]
            
            for path in default_paths:
                if os.path.exists(path):
                    self.load_config(path)
                    break
        
        logger.info(f"Cost Optimizer initialized with {len(self.default_costs)} backends")
    
    def load_config(self, config_path: str) -> bool:
        """
        Load cost configuration from file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            True if configuration was loaded successfully
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Load backend costs
            if "backend_costs" in config:
                for backend_id, cost_data in config["backend_costs"].items():
                    # Handle region-specific costs
                    if "regions" in cost_data:
                        for region_id, region_cost_data in cost_data["regions"].items():
                            self.set_backend_cost(
                                backend_id=backend_id,
                                cost_data=region_cost_data,
                                region_id=region_id
                            )
                    
                    # Handle default costs (no region)
                    self.set_backend_cost(
                        backend_id=backend_id,
                        cost_data=cost_data
                    )
            
            # Load budget constraints
            if "budget_constraints" in config:
                for component, budget in config["budget_constraints"].items():
                    try:
                        cost_component = CostComponent(component)
                        self.budget_constraints[cost_component] = float(budget)
                    except ValueError:
                        logger.warning(f"Invalid cost component: {component}")
            
            # Load price history
            if "price_history" in config:
                for backend_id, history_data in config["price_history"].items():
                    self.price_history[backend_id] = {}
                    
                    for component, prices in history_data.items():
                        try:
                            cost_component = CostComponent(component)
                            self.price_history[backend_id][cost_component] = []
                            
                            for price_data in prices:
                                timestamp = datetime.fromisoformat(price_data["timestamp"])
                                price = float(price_data["price"])
                                self.price_history[backend_id][cost_component].append((timestamp, price))
                        except ValueError:
                            logger.warning(f"Invalid cost component: {component}")
            
            logger.info(f"Loaded cost configuration from {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading cost configuration: {e}")
            return False
    
    def set_backend_cost(self, 
                       backend_id: str, 
                       cost_data: Dict[str, Any],
                       region_id: Optional[str] = None) -> bool:
        """
        Set cost model for a backend.
        
        Args:
            backend_id: Backend identifier
            cost_data: Cost data dictionary
            region_id: Optional region identifier
            
        Returns:
            True if cost model was set successfully
        """
        try:
            # Determine cost model type
            cost_model_type = CostModelType.USAGE_BASED
            if "cost_model_type" in cost_data:
                try:
                    cost_model_type = CostModelType(cost_data["cost_model_type"])
                except ValueError:
                    logger.warning(f"Invalid cost model type: {cost_data['cost_model_type']}")
            
            # Create storage cost
            storage_cost = StorageCost(
                backend_id=backend_id,
                cost_per_gb_month=float(cost_data.get("cost_per_gb_month", 0.0)),
                cost_per_million_ops=float(cost_data.get("cost_per_million_ops", 0.0)),
                bandwidth_in_cost_per_gb=float(cost_data.get("bandwidth_in_cost_per_gb", 0.0)),
                bandwidth_out_cost_per_gb=float(cost_data.get("bandwidth_out_cost_per_gb", 0.0)),
                minimum_cost=float(cost_data.get("minimum_cost", 0.0)),
                cost_model_type=cost_model_type,
                region_id=region_id,
                currency=cost_data.get("currency", "USD"),
                tiered_pricing=cost_data.get("tiered_pricing"),
                custom_pricing=cost_data.get("custom_pricing")
            )
            
            with self.lock:
                if region_id:
                    # Store region-specific cost
                    if backend_id not in self.backend_costs:
                        self.backend_costs[backend_id] = {}
                    
                    self.backend_costs[backend_id][region_id] = storage_cost
                else:
                    # Store default cost
                    self.default_costs[backend_id] = storage_cost
            
            logger.info(f"Set cost model for backend {backend_id}{' in region ' + region_id if region_id else ''}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting backend cost: {e}")
            return False
    
    def get_backend_cost(self, 
                       backend_id: str, 
                       region_id: Optional[str] = None) -> Optional[StorageCost]:
        """
        Get cost model for a backend.
        
        Args:
            backend_id: Backend identifier
            region_id: Optional region identifier
            
        Returns:
            StorageCost or None if not found
        """
        with self.lock:
            # Check for region-specific cost
            if region_id and backend_id in self.backend_costs and region_id in self.backend_costs[backend_id]:
                return self.backend_costs[backend_id][region_id]
            
            # Fall back to default cost
            return self.default_costs.get(backend_id)
    
    def estimate_cost(self, 
                    backend_id: str, 
                    usage: UsageEstimate,
                    region_id: Optional[str] = None) -> Optional[CostEstimate]:
        """
        Estimate cost for a backend.
        
        Args:
            backend_id: Backend identifier
            usage: Usage estimate
            region_id: Optional region identifier
            
        Returns:
            CostEstimate or None if cost model not found
        """
        # Get cost model
        cost_model = self.get_backend_cost(backend_id, region_id)
        if not cost_model:
            return None
        
        # Calculate component costs
        component_costs = {}
        
        # Storage cost
        storage_cost = usage.storage_gb_months * cost_model.cost_per_gb_month
        component_costs[CostComponent.STORAGE] = storage_cost
        
        # Operations cost
        operations_cost = (usage.operations_count / 1000000) * cost_model.cost_per_million_ops
        component_costs[CostComponent.OPERATIONS] = operations_cost
        
        # Bandwidth costs
        bandwidth_in_cost = usage.bandwidth_in_gb * cost_model.bandwidth_in_cost_per_gb
        bandwidth_out_cost = usage.bandwidth_out_gb * cost_model.bandwidth_out_cost_per_gb
        component_costs[CostComponent.BANDWIDTH_IN] = bandwidth_in_cost
        component_costs[CostComponent.BANDWIDTH_OUT] = bandwidth_out_cost
        
        # Handle tiered pricing if applicable
        if cost_model.cost_model_type == CostModelType.TIERED and cost_model.tiered_pricing:
            # Recalculate with tiered pricing
            # This is a simplified implementation; a real one would be more complex
            tiered_costs = self._calculate_tiered_costs(cost_model.tiered_pricing, usage)
            component_costs.update(tiered_costs)
        
        # Calculate total cost
        total_cost = sum(component_costs.values())
        
        # Apply minimum cost if necessary
        if total_cost < cost_model.minimum_cost:
            component_costs[CostComponent.MINIMUM] = cost_model.minimum_cost - total_cost
            total_cost = cost_model.minimum_cost
        
        # Create cost estimate
        return CostEstimate(
            backend_id=backend_id,
            total_cost=total_cost,
            component_costs=component_costs,
            usage=usage,
            currency=cost_model.currency
        )
    
    def _calculate_tiered_costs(self, 
                              tiered_pricing: Dict[str, Any],
                              usage: UsageEstimate) -> Dict[CostComponent, float]:
        """
        Calculate costs using tiered pricing.
        
        Args:
            tiered_pricing: Tiered pricing configuration
            usage: Usage estimate
            
        Returns:
            Dictionary of component costs
        """
        # This is a simplified implementation
        # A real implementation would handle each tier and component separately
        
        component_costs = {}
        
        # Handle storage tiers
        if "storage" in tiered_pricing:
            tiers = tiered_pricing["storage"]
            storage_cost = self._calculate_tiered_component_cost(
                tiers, usage.storage_gb_months
            )
            component_costs[CostComponent.STORAGE] = storage_cost
        
        # Handle bandwidth tiers
        if "bandwidth_out" in tiered_pricing:
            tiers = tiered_pricing["bandwidth_out"]
            bandwidth_cost = self._calculate_tiered_component_cost(
                tiers, usage.bandwidth_out_gb
            )
            component_costs[CostComponent.BANDWIDTH_OUT] = bandwidth_cost
        
        # Handle operations tiers
        if "operations" in tiered_pricing:
            tiers = tiered_pricing["operations"]
            operations_cost = self._calculate_tiered_component_cost(
                tiers, usage.operations_count / 1000000  # Convert to millions
            )
            component_costs[CostComponent.OPERATIONS] = operations_cost
        
        return component_costs
    
    def _calculate_tiered_component_cost(self, 
                                       tiers: List[Dict[str, Any]],
                                       usage_amount: float) -> float:
        """
        Calculate cost for a component using tiered pricing.
        
        Args:
            tiers: List of tier dictionaries (threshold, price)
            usage_amount: Amount of usage
            
        Returns:
            Cost for the component
        """
        # Sort tiers by threshold
        sorted_tiers = sorted(tiers, key=lambda t: float(t["threshold"]))
        
        # Calculate cost
        cost = 0.0
        remaining_usage = usage_amount
        
        for i, tier in enumerate(sorted_tiers):
            threshold = float(tier["threshold"])
            price = float(tier["price"])
            
            if i == len(sorted_tiers) - 1:
                # Last tier, apply to all remaining usage
                cost += remaining_usage * price
                break
            
            next_threshold = float(sorted_tiers[i + 1]["threshold"])
            tier_usage = min(remaining_usage, next_threshold - threshold)
            
            if tier_usage <= 0:
                continue
                
            cost += tier_usage * price
            remaining_usage -= tier_usage
            
            if remaining_usage <= 0:
                break
        
        return cost
    
    def select_cheapest_backend(self, 
                              usage: UsageEstimate,
                              available_backends: List[str],
                              region_id: Optional[str] = None) -> Optional[Tuple[str, CostEstimate]]:
        """
        Select the cheapest backend for given usage.
        
        Args:
            usage: Usage estimate
            available_backends: List of available backends
            region_id: Optional region identifier
            
        Returns:
            Tuple of (backend_id, cost_estimate) or None if no suitable backend found
        """
        if not available_backends:
            return None
        
        # Estimate costs for all available backends
        backend_costs = []
        
        for backend_id in available_backends:
            cost_estimate = self.estimate_cost(backend_id, usage, region_id)
            if cost_estimate:
                backend_costs.append((backend_id, cost_estimate))
        
        if not backend_costs:
            return None
        
        # Sort by total cost
        backend_costs.sort(key=lambda x: x[1].total_cost)
        
        # Return cheapest backend
        return backend_costs[0]
    
    def select_cost_optimized_backend(self, 
                                    usage: UsageEstimate,
                                    available_backends: List[str],
                                    region_id: Optional[str] = None,
                                    budget: Optional[float] = None) -> Optional[Tuple[str, CostEstimate]]:
        """
        Select a cost-optimized backend based on usage and budget.
        
        Args:
            usage: Usage estimate
            available_backends: List of available backends
            region_id: Optional region identifier
            budget: Optional budget constraint
            
        Returns:
            Tuple of (backend_id, cost_estimate) or None if no suitable backend found
        """
        if not available_backends:
            return None
        
        # Estimate costs for all available backends
        backend_costs = []
        
        for backend_id in available_backends:
            cost_estimate = self.estimate_cost(backend_id, usage, region_id)
            if cost_estimate:
                backend_costs.append((backend_id, cost_estimate))
        
        if not backend_costs:
            return None
        
        # Filter by budget if specified
        if budget is not None:
            backend_costs = [
                (backend_id, cost_estimate)
                for backend_id, cost_estimate in backend_costs
                if cost_estimate.total_cost <= budget
            ]
            
            if not backend_costs:
                return None
        
        # Sort by total cost
        backend_costs.sort(key=lambda x: x[1].total_cost)
        
        # Return cheapest backend
        return backend_costs[0]
    
    def estimate_multi_backend_cost(self, 
                                  backend_usage: Dict[str, UsageEstimate],
                                  region_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Estimate cost for multiple backends.
        
        Args:
            backend_usage: Dictionary of backend_id -> usage estimate
            region_id: Optional region identifier
            
        Returns:
            Dictionary with cost estimates
        """
        # Estimate costs for each backend
        backend_costs = {}
        total_cost = 0.0
        
        for backend_id, usage in backend_usage.items():
            cost_estimate = self.estimate_cost(backend_id, usage, region_id)
            if cost_estimate:
                backend_costs[backend_id] = cost_estimate
                total_cost += cost_estimate.total_cost
        
        # Create summary
        return {
            "backend_costs": {
                backend_id: cost_estimate.to_dict()
                for backend_id, cost_estimate in backend_costs.items()
            },
            "total_cost": total_cost,
            "currency": next(iter(backend_costs.values())).currency if backend_costs else "USD"
        }
    
    def create_usage_estimate(self, 
                            size_bytes: int,
                            duration_days: int = 30,
                            operation_count: int = 0,
                            download_ratio: float = 0.1) -> UsageEstimate:
        """
        Create a usage estimate based on content size and expected usage.
        
        Args:
            size_bytes: Size of content in bytes
            duration_days: Expected storage duration in days
            operation_count: Expected number of operations
            download_ratio: Expected ratio of content to be downloaded
            
        Returns:
            UsageEstimate
        """
        # Convert size to GB
        size_gb = size_bytes / (1024 * 1024 * 1024)
        
        # Calculate storage in GB-months
        storage_gb_months = size_gb * (duration_days / 30)
        
        # Calculate bandwidth
        bandwidth_in_gb = size_gb  # Upload once
        bandwidth_out_gb = size_gb * download_ratio  # Download a portion
        
        # Create usage estimate
        return UsageEstimate(
            storage_gb_months=storage_gb_months,
            operations_count=operation_count,
            bandwidth_in_gb=bandwidth_in_gb,
            bandwidth_out_gb=bandwidth_out_gb,
            duration_months=duration_days / 30
        )
    
    def predict_future_cost(self, 
                          backend_id: str,
                          usage: UsageEstimate,
                          months_ahead: int = 1,
                          region_id: Optional[str] = None) -> Optional[CostEstimate]:
        """
        Predict future cost based on price trends.
        
        Args:
            backend_id: Backend identifier
            usage: Usage estimate
            months_ahead: Months to predict ahead
            region_id: Optional region identifier
            
        Returns:
            Predicted CostEstimate or None if prediction not possible
        """
        # Get current cost
        current_cost = self.estimate_cost(backend_id, usage, region_id)
        if not current_cost:
            return None
        
        # If no price history, return current cost
        if (backend_id not in self.price_history or 
            not self.price_history[backend_id]):
            return current_cost
        
        # Predict future cost based on trends
        predicted_components = {}
        
        for component, current_cost_value in current_cost.component_costs.items():
            # Check if we have history for this component
            if component not in self.price_history[backend_id]:
                predicted_components[component] = current_cost_value
                continue
            
            # Get price history
            history = self.price_history[backend_id][component]
            
            if len(history) < 2:
                predicted_components[component] = current_cost_value
                continue
            
            # Calculate trend
            newest_timestamp, newest_price = history[-1]
            oldest_timestamp, oldest_price = history[0]
            
            time_diff = (newest_timestamp - oldest_timestamp).days / 30  # Convert to months
            
            if time_diff <= 0:
                predicted_components[component] = current_cost_value
                continue
            
            price_diff = newest_price - oldest_price
            monthly_change = price_diff / time_diff
            
            # Predict future price
            predicted_price = newest_price + (monthly_change * months_ahead)
            
            # Calculate predicted cost
            if newest_price > 0:
                change_ratio = predicted_price / newest_price
                predicted_components[component] = current_cost_value * change_ratio
            else:
                predicted_components[component] = current_cost_value
        
        # Calculate total predicted cost
        total_predicted_cost = sum(predicted_components.values())
        
        # Create predicted cost estimate
        return CostEstimate(
            backend_id=backend_id,
            total_cost=total_predicted_cost,
            component_costs=predicted_components,
            usage=usage,
            currency=current_cost.currency
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the cost optimizer state to a dictionary."""
        with self.lock:
            return {
                "default_costs": {
                    backend_id: cost.to_dict()
                    for backend_id, cost in self.default_costs.items()
                },
                "backend_costs": {
                    backend_id: {
                        region_id: cost.to_dict()
                        for region_id, cost in regions.items()
                    }
                    for backend_id, regions in self.backend_costs.items()
                },
                "budget_constraints": {
                    component.value: budget
                    for component, budget in self.budget_constraints.items()
                }
            }


# Default cost optimizer
_cost_optimizer = None

def get_cost_optimizer() -> CostOptimizer:
    """Get or create the default cost optimizer instance."""
    global _cost_optimizer
    if _cost_optimizer is None:
        _cost_optimizer = CostOptimizer()
    return _cost_optimizer