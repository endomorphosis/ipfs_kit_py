"""
Extension methods for IPFS Kit to provide cluster management functionality.

This module extends the ipfs_kit class with methods for cluster management,
task handling, configuration management, and metrics collection.
"""

import logging
import time
from typing import Any, Callable, Dict, Optional

# Configure logger
logger = logging.getLogger(__name__)

# Import error handling utilities
try:
    from .error import IPFSError, IPFSValidationError, create_result_dict, handle_error
except ImportError:
    # Fallback implementation if error module is not available
    def handle_error(result, error):
        result["success"] = False
        result["error"] = str(error)
        logger.error(f"Error: {str(error)}")
        return result

    def create_result_dict(operation, correlation_id=None):
        result = {"success": False, "operation": operation, "timestamp": time.time()}
        if correlation_id:
            result["correlation_id"] = correlation_id
        return result

    class IPFSError(Exception):
        """Base class for IPFS errors."""

        pass

    class IPFSValidationError(IPFSError):
        """Error raised when validation fails."""

        pass


# Extension methods
def register_task_handler(self, task_type, handler_func, **kwargs):
    """Register a handler function for a specific task type.

    This allows nodes to handle specific types of distributed tasks.
    When a task of this type is submitted to the cluster, nodes with
    matching handlers will be eligible to process it.

    Args:
        task_type: Type of task to handle (e.g., "image_processing", "data_analysis")
        handler_func: Function to call when task is received
                    Should accept a payload dict and return a result dict
        **kwargs: Additional arguments like correlation_id

    Returns:
        Result dictionary indicating successful registration
    """
    operation = "register_task_handler"
    correlation_id = kwargs.get("correlation_id")
    result = create_result_dict(operation, correlation_id)

    try:
        # Check if cluster management is available
        if not hasattr(self, "cluster_manager") or self.cluster_manager is None:
            return handle_error(result, IPFSError("Cluster management is not enabled"))

        # Validate handler function
        if not callable(handler_func):
            return handle_error(result, ValueError("Handler function must be callable"))

        # Validate task_type
        if not task_type or not isinstance(task_type, str):
            return handle_error(result, IPFSValidationError("Task type must be a non-empty string"))

        # Register the handler
        registration_success = self.cluster_manager.register_task_handler(
            task_type=task_type, handler_func=handler_func
        )

        if not registration_success:
            return handle_error(result, IPFSError("Failed to register task handler"))

        result["success"] = True
        result["message"] = f"Successfully registered handler for task type '{task_type}'"
        result["task_type"] = task_type
        return result

    except Exception as e:
        return handle_error(result, e)


def propose_config_change(self, key, value, **kwargs):
    """Propose a configuration change to the cluster.

    This initiates a consensus process where nodes vote on the change.
    The change will only be applied if a majority of nodes approve.

    Args:
        key: Configuration key to change
        value: New value to set
        **kwargs: Additional arguments like correlation_id

    Returns:
        Result dictionary with proposal status and ID
    """
    operation = "propose_config_change"
    correlation_id = kwargs.get("correlation_id")
    result = create_result_dict(operation, correlation_id)

    try:
        # Check if cluster management is available
        if not hasattr(self, "cluster_manager") or self.cluster_manager is None:
            return handle_error(result, IPFSError("Cluster management is not enabled"))

        # Validate key
        if not key or not isinstance(key, str):
            return handle_error(
                result, IPFSValidationError("Configuration key must be a non-empty string")
            )

        # Submit proposal
        proposal_result = self.cluster_manager.propose_configuration_change(key=key, value=value)

        # Update result with proposal information
        result.update(proposal_result)

        # Ensure we have a success field
        if "success" not in result:
            result["success"] = True

        # Add key and value to the result
        result["config_key"] = key
        result["config_value"] = str(value)

        return result

    except Exception as e:
        return handle_error(result, e)


def get_cluster_metrics(self, include_members=True, include_history=False, **kwargs):
    """Get comprehensive metrics about the cluster.

    Retrieves performance metrics, resource utilization, task statistics,
    and other operational data for the cluster and its nodes.

    Args:
        include_members: Whether to include metrics for all member nodes
        include_history: Whether to include historical metrics (time series)
        **kwargs: Additional arguments like correlation_id

    Returns:
        Result dictionary with various performance metrics
    """
    operation = "get_cluster_metrics"
    correlation_id = kwargs.get("correlation_id")
    result = create_result_dict(operation, correlation_id)

    try:
        # Check if cluster management is available
        if not hasattr(self, "cluster_manager") or self.cluster_manager is None:
            return handle_error(result, IPFSError("Cluster management is not enabled"))

        # Get metrics from cluster manager
        metrics_result = self.cluster_manager.get_cluster_metrics(
            include_members=include_members, include_history=include_history
        )

        # Add metrics to result
        result.update({k: v for k, v in metrics_result.items() if k != "success"})
        result["success"] = True
        result["timestamp"] = time.time()

        return result

    except Exception as e:
        return handle_error(result, e)


# Function to extend ipfs_kit with these methods
def extend_ipfs_kit(cls):
    """Extend the ipfs_kit class with cluster management methods."""
    setattr(cls, "register_task_handler", register_task_handler)
    setattr(cls, "propose_config_change", propose_config_change)
    setattr(cls, "get_cluster_metrics", get_cluster_metrics)
    return cls
