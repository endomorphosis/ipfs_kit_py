#!/usr/bin/env python3
"""
Multi-Region Cluster Support for IPFS Kit

Enables deployment and management of IPFS clusters across multiple
geographic regions with intelligent routing and failover.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class RegionStatus(Enum):
    """Region health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class Region:
    """Represents a geographic region."""
    name: str
    location: str
    latency_zone: str  # e.g., "us-west", "eu-central", "ap-southeast"
    endpoints: List[str]
    status: RegionStatus = RegionStatus.HEALTHY
    last_health_check: float = 0.0
    average_latency: float = 0.0
    node_count: int = 0
    capacity: int = 0  # Storage capacity in bytes
    used: int = 0  # Used storage in bytes


class MultiRegionCluster:
    """
    Multi-region cluster manager.
    
    Manages IPFS nodes across multiple geographic regions with
    intelligent routing, replication, and failover capabilities.
    """
    
    def __init__(self, ipfs_api=None):
        """Initialize multi-region cluster manager."""
        self.ipfs_api = ipfs_api
        
        # Region registry
        self.regions: Dict[str, Region] = {}
        
        # Routing preferences
        self.routing_strategy = "latency_optimized"  # latency_optimized, geo_distributed, cost_optimized
        
        # Replication settings
        self.min_replicas_per_region = 1
        self.cross_region_replication = True
        
        # Health check settings
        self.health_check_interval = 30  # seconds
        self.health_check_timeout = 5  # seconds
        
        # Monitoring
        self.is_monitoring = False
        
        logger.info("Multi-region cluster manager initialized")
    
    def register_region(self, region: Region) -> bool:
        """
        Register a new region.
        
        Args:
            region: Region to register
            
        Returns:
            True if successful
        """
        try:
            self.regions[region.name] = region
            logger.info(f"Registered region: {region.name} ({region.location})")
            return True
        except Exception as e:
            logger.error(f"Error registering region {region.name}: {e}")
            return False
    
    def add_region(self, name: str, location: str, latency_zone: str, 
                   endpoints: List[str]) -> bool:
        """
        Add a new region (convenience method).
        
        Args:
            name: Region name (e.g., "us-west-1")
            location: Human-readable location (e.g., "Oregon, USA")
            latency_zone: Latency zone identifier
            endpoints: List of node endpoints in this region
            
        Returns:
            True if successful
        """
        region = Region(
            name=name,
            location=location,
            latency_zone=latency_zone,
            endpoints=endpoints
        )
        return self.register_region(region)
    
    async def health_check(self, region_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform health check on regions.
        
        Args:
            region_name: Specific region to check, or None for all regions
            
        Returns:
            Health check results
        """
        if region_name:
            regions_to_check = [self.regions.get(region_name)]
            if not regions_to_check[0]:
                return {"error": f"Region {region_name} not found"}
        else:
            regions_to_check = list(self.regions.values())
        
        results = {}
        
        for region in regions_to_check:
            if region is None:
                continue
            
            try:
                start_time = time.time()
                
                # Check each endpoint in the region
                healthy_endpoints = 0
                total_latency = 0.0
                
                for endpoint in region.endpoints:
                    is_healthy, latency = await self._check_endpoint(endpoint)
                    if is_healthy:
                        healthy_endpoints += 1
                        total_latency += latency
                
                # Update region status
                if healthy_endpoints == 0:
                    region.status = RegionStatus.UNAVAILABLE
                elif healthy_endpoints < len(region.endpoints):
                    region.status = RegionStatus.DEGRADED
                else:
                    region.status = RegionStatus.HEALTHY
                
                # Update metrics
                region.last_health_check = time.time()
                if healthy_endpoints > 0:
                    region.average_latency = total_latency / healthy_endpoints
                
                results[region.name] = {
                    "status": region.status.value,
                    "healthy_endpoints": healthy_endpoints,
                    "total_endpoints": len(region.endpoints),
                    "average_latency": region.average_latency,
                    "last_check": region.last_health_check
                }
                
            except Exception as e:
                logger.error(f"Error checking region {region.name}: {e}")
                results[region.name] = {"error": str(e)}
        
        return results
    
    async def _check_endpoint(self, endpoint: str) -> tuple[bool, float]:
        """
        Check if an endpoint is healthy.
        
        Args:
            endpoint: Endpoint URL
            
        Returns:
            Tuple of (is_healthy, latency_ms)
        """
        try:
            start_time = time.time()
            
            # Perform health check (e.g., ping IPFS API)
            # This is a simplified implementation
            await asyncio.sleep(0.01)  # Simulate network check
            
            latency = (time.time() - start_time) * 1000  # Convert to ms
            
            return True, latency
        except Exception as e:
            logger.error(f"Endpoint check failed for {endpoint}: {e}")
            return False, 0.0
    
    def select_region(self, strategy: Optional[str] = None, 
                     exclude_regions: Optional[Set[str]] = None) -> Optional[Region]:
        """
        Select optimal region based on strategy.
        
        Args:
            strategy: Routing strategy to use
            exclude_regions: Set of region names to exclude
            
        Returns:
            Selected region or None
        """
        strategy = strategy or self.routing_strategy
        exclude_regions = exclude_regions or set()
        
        # Filter available regions
        available_regions = [
            r for r in self.regions.values()
            if r.name not in exclude_regions and r.status == RegionStatus.HEALTHY
        ]
        
        if not available_regions:
            # Try degraded regions if no healthy ones
            available_regions = [
                r for r in self.regions.values()
                if r.name not in exclude_regions and r.status == RegionStatus.DEGRADED
            ]
        
        if not available_regions:
            return None
        
        # Apply selection strategy
        if strategy == "latency_optimized":
            return min(available_regions, key=lambda r: r.average_latency)
        elif strategy == "geo_distributed":
            # Select region with lowest usage
            return min(available_regions, key=lambda r: r.used / max(r.capacity, 1))
        elif strategy == "cost_optimized":
            # For now, just round-robin (would need cost data)
            return available_regions[0]
        else:
            return available_regions[0]
    
    async def replicate_to_regions(self, cid: str, target_regions: Optional[List[str]] = None,
                                   min_replicas: int = 2) -> Dict[str, Any]:
        """
        Replicate content across regions.
        
        Args:
            cid: Content identifier
            target_regions: List of target region names (None for auto-select)
            min_replicas: Minimum number of regional replicas
            
        Returns:
            Replication results
        """
        try:
            # Select target regions if not specified
            if target_regions is None:
                target_regions = self._select_replication_regions(min_replicas)
            
            results = {
                "cid": cid,
                "regions": {},
                "success": True
            }
            
            # Replicate to each region
            for region_name in target_regions:
                region = self.regions.get(region_name)
                if not region:
                    logger.warning(f"Region {region_name} not found")
                    continue
                
                try:
                    # Replicate to region
                    region_result = await self._replicate_to_region(cid, region)
                    results["regions"][region_name] = region_result
                    
                    if not region_result.get("success"):
                        results["success"] = False
                        
                except Exception as e:
                    logger.error(f"Error replicating to region {region_name}: {e}")
                    results["regions"][region_name] = {"success": False, "error": str(e)}
                    results["success"] = False
            
            return results
            
        except Exception as e:
            logger.error(f"Error in replicate_to_regions: {e}")
            return {"success": False, "error": str(e)}
    
    def _select_replication_regions(self, count: int) -> List[str]:
        """Select regions for replication based on strategy."""
        # Get healthy regions sorted by different zones
        regions_by_zone: Dict[str, List[Region]] = {}
        
        for region in self.regions.values():
            if region.status == RegionStatus.HEALTHY:
                if region.latency_zone not in regions_by_zone:
                    regions_by_zone[region.latency_zone] = []
                regions_by_zone[region.latency_zone].append(region)
        
        # Select regions from different zones for geographic distribution
        selected = []
        zones = list(regions_by_zone.keys())
        
        for i in range(count):
            if not zones:
                break
            
            zone = zones[i % len(zones)]
            if regions_by_zone[zone]:
                region = regions_by_zone[zone].pop(0)
                selected.append(region.name)
        
        return selected
    
    async def _replicate_to_region(self, cid: str, region: Region) -> Dict[str, Any]:
        """Replicate content to a specific region."""
        try:
            # This would use IPFS cluster pin to specific nodes in the region
            logger.info(f"Replicating {cid} to region {region.name}")
            
            # Simulate replication
            await asyncio.sleep(0.1)
            
            return {
                "success": True,
                "region": region.name,
                "cid": cid,
                "endpoints": region.endpoints
            }
        except Exception as e:
            logger.error(f"Replication error: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_closest_region(self, client_location: Optional[str] = None) -> Optional[Region]:
        """
        Get the closest region to a client.
        
        Args:
            client_location: Client location hint
            
        Returns:
            Closest region
        """
        # Simplified implementation - would use GeoIP or similar
        return self.select_region(strategy="latency_optimized")
    
    async def failover(self, failed_region: str) -> Dict[str, Any]:
        """
        Handle region failover.
        
        Args:
            failed_region: Name of failed region
            
        Returns:
            Failover results
        """
        try:
            region = self.regions.get(failed_region)
            if not region:
                return {"success": False, "error": "Region not found"}
            
            # Mark region as unavailable
            region.status = RegionStatus.UNAVAILABLE
            
            # Select backup regions
            backup_regions = self._select_replication_regions(2)
            backup_regions = [r for r in backup_regions if r != failed_region]
            
            logger.info(f"Failing over from {failed_region} to {backup_regions}")
            
            return {
                "success": True,
                "failed_region": failed_region,
                "backup_regions": backup_regions,
                "action": "Traffic redirected to backup regions"
            }
            
        except Exception as e:
            logger.error(f"Failover error: {e}")
            return {"success": False, "error": str(e)}
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get multi-region cluster statistics."""
        total_nodes = sum(r.node_count for r in self.regions.values())
        total_capacity = sum(r.capacity for r in self.regions.values())
        total_used = sum(r.used for r in self.regions.values())
        
        regions_by_status = {
            "healthy": 0,
            "degraded": 0,
            "unavailable": 0
        }
        
        for region in self.regions.values():
            regions_by_status[region.status.value] += 1
        
        return {
            "total_regions": len(self.regions),
            "regions_by_status": regions_by_status,
            "total_nodes": total_nodes,
            "total_capacity": total_capacity,
            "total_used": total_used,
            "utilization": total_used / total_capacity if total_capacity > 0 else 0.0,
            "regions": {
                name: {
                    "location": r.location,
                    "status": r.status.value,
                    "latency": r.average_latency,
                    "nodes": r.node_count
                }
                for name, r in self.regions.items()
            }
        }
    
    async def start_monitoring(self):
        """Start monitoring regions."""
        self.is_monitoring = True
        logger.info("Started multi-region monitoring")
        
        while self.is_monitoring:
            try:
                await self.health_check()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    def stop_monitoring(self):
        """Stop monitoring regions."""
        self.is_monitoring = False
        logger.info("Stopped multi-region monitoring")


# Convenience function
def create_multi_region_cluster(ipfs_api=None) -> MultiRegionCluster:
    """Create multi-region cluster manager instance."""
    return MultiRegionCluster(ipfs_api=ipfs_api)
