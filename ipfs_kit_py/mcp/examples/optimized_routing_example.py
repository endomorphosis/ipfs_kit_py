"""
Example usage of the Optimized Data Routing module

This example demonstrates how to:
1. Create an OptimizedRouter instance
2. Register storage backends with metrics
3. Create routing policies for different use cases
4. Make routing decisions for content
5. Analyze backend performance and connectivity
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, List

from ipfs_kit_py.mcp.routing import (
    OptimizedRouter,
    ContentType,
    RoutingStrategy,
    StorageClass,
    GeographicRegion,
    ComplianceType,
    RoutingPolicy,
    RoutingDecision,
    BackendMetrics
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_router_with_backends() -> OptimizedRouter:
    """Initialize a router and register some backends."""
    router = OptimizedRouter()
    
    # Register IPFS backend
    router.register_backend(
        backend_id="ipfs-backend",
        endpoint="http://localhost:5001/api/v0",
        metrics={
            "backend_type": "ipfs",
            "avg_read_latency_ms": 120.0,
            "avg_write_latency_ms": 150.0,
            "avg_throughput_mbps": 25.0,
            "success_rate": 0.99,
            "storage_cost_per_gb_month": 0.0,  # Free
            "read_cost_per_gb": 0.0,  # Free
            "write_cost_per_gb": 0.0,  # Free
            "egress_cost_per_gb": 0.0,  # Free
            "availability_percentage": 98.5,
            "uptime_last_24h": 99.8,
            "region": GeographicRegion.GLOBAL,
            "physical_location": None,
            "current_load_percentage": 30.0,
            "available_capacity_gb": 250.0,
            "supported_compliance": [ComplianceType.PUBLIC]
        }
    )
    
    # Register S3 backend
    router.register_backend(
        backend_id="s3-backend",
        endpoint="https://s3.amazonaws.com",
        metrics={
            "backend_type": "s3",
            "avg_read_latency_ms": 80.0,
            "avg_write_latency_ms": 100.0,
            "avg_throughput_mbps": 50.0,
            "success_rate": 0.999,
            "storage_cost_per_gb_month": 0.023,  # $0.023 per GB per month
            "read_cost_per_gb": 0.0004,  # $0.0004 per GB
            "write_cost_per_gb": 0.005,  # $0.005 per GB
            "egress_cost_per_gb": 0.09,  # $0.09 per GB
            "availability_percentage": 99.99,
            "uptime_last_24h": 100.0,
            "region": GeographicRegion.NORTH_AMERICA,
            "physical_location": "us-east-1",
            "current_load_percentage": 10.0,
            "available_capacity_gb": 5000.0,
            "supported_compliance": [
                ComplianceType.PUBLIC,
                ComplianceType.PROPRIETARY,
                ComplianceType.HIPAA,
                ComplianceType.SOX
            ]
        }
    )
    
    # Register Filecoin backend
    router.register_backend(
        backend_id="filecoin-backend",
        endpoint="https://api.node.glif.io",
        metrics={
            "backend_type": "filecoin",
            "avg_read_latency_ms": 500.0,
            "avg_write_latency_ms": 2000.0,
            "avg_throughput_mbps": 15.0,
            "success_rate": 0.98,
            "storage_cost_per_gb_month": 0.002,  # $0.002 per GB per month (cheaper)
            "read_cost_per_gb": 0.001,  # $0.001 per GB
            "write_cost_per_gb": 0.002,  # $0.002 per GB
            "egress_cost_per_gb": 0.01,  # $0.01 per GB
            "availability_percentage": 99.5,
            "uptime_last_24h": 99.5,
            "region": GeographicRegion.GLOBAL,
            "physical_location": None,
            "current_load_percentage": 5.0,
            "available_capacity_gb": 10000.0,
            "supported_compliance": [
                ComplianceType.PUBLIC,
                ComplianceType.PROPRIETARY
            ]
        }
    )
    
    return router


def create_routing_policies(router: OptimizedRouter) -> None:
    """Create various routing policies for different use cases."""
    
    # Create a cost-optimized policy for archive data
    cost_policy = RoutingPolicy(
        id="cost-optimized",
        name="Cost Optimized Storage",
        description="Optimizes for lowest storage cost, suitable for archival data",
        strategy=RoutingStrategy.COST_OPTIMIZED,
        default_storage_class=StorageClass.COLD,
        cost_optimization_enabled=True,
        performance_optimization_enabled=False,
        content_type_routing={
            ContentType.LARGE_FILE: RoutingStrategy.COST_OPTIMIZED,
            ContentType.VERY_LARGE_FILE: RoutingStrategy.COST_OPTIMIZED,
            ContentType.DIRECTORY: RoutingStrategy.COST_OPTIMIZED,
            ContentType.COLLECTION: RoutingStrategy.COST_OPTIMIZED,
        },
        content_type_storage_class={
            ContentType.LARGE_FILE: StorageClass.COLD,
            ContentType.VERY_LARGE_FILE: StorageClass.ARCHIVE,
            ContentType.DIRECTORY: StorageClass.COLD,
            ContentType.COLLECTION: StorageClass.COLD,
        }
    )
    router.add_policy(cost_policy)
    
    # Create a performance-optimized policy for frequently accessed data
    performance_policy = RoutingPolicy(
        id="performance-optimized",
        name="Performance Optimized Storage",
        description="Optimizes for lowest latency and highest throughput",
        strategy=RoutingStrategy.PERFORMANCE_OPTIMIZED,
        default_storage_class=StorageClass.HOT,
        cost_optimization_enabled=False,
        performance_optimization_enabled=True,
        min_throughput_mbps=25.0,
        max_latency_ms=200.0,
        content_type_routing={
            ContentType.SMALL_FILE: RoutingStrategy.PERFORMANCE_OPTIMIZED,
            ContentType.IMAGE: RoutingStrategy.PERFORMANCE_OPTIMIZED,
            ContentType.VIDEO: RoutingStrategy.PERFORMANCE_OPTIMIZED,
            ContentType.AUDIO: RoutingStrategy.PERFORMANCE_OPTIMIZED,
        },
        content_type_storage_class={
            ContentType.SMALL_FILE: StorageClass.HOT,
            ContentType.IMAGE: StorageClass.HOT,
            ContentType.VIDEO: StorageClass.HOT,
            ContentType.AUDIO: StorageClass.HOT,
        }
    )
    router.add_policy(performance_policy)
    
    # Create a compliance-focused policy for sensitive data
    compliance_policy = RoutingPolicy(
        id="compliance-optimized",
        name="Compliance Optimized Storage",
        description="Optimizes for regulatory compliance requirements",
        strategy=RoutingStrategy.COMPLIANCE_OPTIMIZED,
        default_storage_class=StorageClass.COMPLIANCE,
        geo_compliance_required=True,
        preferred_regions=[
            GeographicRegion.NORTH_AMERICA,
            GeographicRegion.EUROPE
        ],
        content_type_routing={
            ContentType.STRUCTURED_DATA: RoutingStrategy.COMPLIANCE_OPTIMIZED,
            ContentType.TEXT: RoutingStrategy.COMPLIANCE_OPTIMIZED,
        },
        content_type_storage_class={
            ContentType.STRUCTURED_DATA: StorageClass.COMPLIANCE,
            ContentType.TEXT: StorageClass.COMPLIANCE,
        }
    )
    router.add_policy(compliance_policy)
    
    # Create a redundancy-focused policy for critical data
    redundancy_policy = RoutingPolicy(
        id="redundancy-optimized",
        name="Redundancy Optimized Storage",
        description="Optimizes for data durability and availability",
        strategy=RoutingStrategy.REDUNDANCY_OPTIMIZED,
        default_storage_class=StorageClass.HOT,
        replication_factor=3,  # Store 3 copies
        min_availability_percentage=99.999,
    )
    router.add_policy(redundancy_policy)
    
    # Set the default policy
    router.set_default_policy("performance-optimized")


def make_routing_decisions(router: OptimizedRouter) -> None:
    """Demonstrate making routing decisions for different content types."""
    
    # Small image file - should go to a fast backend
    small_image_metadata = {
        "mime_type": "image/jpeg",
        "size_bytes": 500000,  # 500 KB
        "is_directory": False,
        "is_collection": False,
        "is_encrypted": False,
        "access_frequency": "high",
        "compliance_requirements": []
    }
    
    try:
        image_decision = router.get_route_for_content(
            content_id="image1.jpg",
            content_metadata=small_image_metadata,
            operation="store",
            policy_id="performance-optimized"
        )
        
        logger.info(f"Routing decision for image: {image_decision.primary_backend_id}")
        logger.info(f"Decision factors: {image_decision.decision_factors}")
    except Exception as e:
        logger.error(f"Error routing image: {e}")
    
    # Large backup file - should go to a cost-effective backend
    large_backup_metadata = {
        "mime_type": "application/zip",
        "size_bytes": 5000000000,  # 5 GB
        "is_directory": False,
        "is_collection": False,
        "is_encrypted": True,
        "access_frequency": "low",
        "compliance_requirements": []
    }
    
    try:
        backup_decision = router.get_route_for_content(
            content_id="system_backup.zip",
            content_metadata=large_backup_metadata,
            operation="store",
            policy_id="cost-optimized"
        )
        
        logger.info(f"Routing decision for backup: {backup_decision.primary_backend_id}")
        logger.info(f"Decision factors: {backup_decision.decision_factors}")
    except Exception as e:
        logger.error(f"Error routing backup: {e}")
    
    # Financial data - should go to a compliant backend
    financial_data_metadata = {
        "mime_type": "application/json",
        "size_bytes": 2000000,  # 2 MB
        "is_directory": False,
        "is_collection": False,
        "is_encrypted": True,
        "access_frequency": "medium",
        "compliance_requirements": ["sox", "hipaa"]
    }
    
    try:
        financial_decision = router.get_route_for_content(
            content_id="financial_data.json",
            content_metadata=financial_data_metadata,
            operation="store",
            policy_id="compliance-optimized"
        )
        
        logger.info(f"Routing decision for financial data: {financial_decision.primary_backend_id}")
        logger.info(f"Decision factors: {financial_decision.decision_factors}")
    except Exception as e:
        logger.error(f"Error routing financial data: {e}")


def analyze_backend_performance(router: OptimizedRouter) -> None:
    """Analyze backend performance and connectivity."""
    
    # Analyze connectivity to backends
    for backend_id in ["ipfs-backend", "s3-backend", "filecoin-backend"]:
        connectivity = router.analyze_backend_connectivity(backend_id)
        logger.info(f"Connectivity to {backend_id}: {connectivity}")
    
    # Get performance rankings
    metrics_collector = router._metrics_collector
    performance_ranking = metrics_collector.get_backend_performance_ranking()
    logger.info(f"Performance ranking: {performance_ranking}")
    
    # Get cost rankings
    cost_ranking = metrics_collector.get_backend_cost_ranking()
    logger.info(f"Cost ranking: {cost_ranking}")


def main() -> None:
    """Main function to demonstrate the Optimized Router."""
    logger.info("Initializing Optimized Router example...")
    
    # Initialize router with backends
    router = initialize_router_with_backends()
    
    # Create routing policies
    create_routing_policies(router)
    
    # Make routing decisions
    make_routing_decisions(router)
    
    # Analyze backend performance
    analyze_backend_performance(router)
    
    logger.info("Optimized Router example completed.")


if __name__ == "__main__":
    main()
