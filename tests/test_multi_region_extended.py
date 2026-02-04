#!/usr/bin/env python3
"""
Extended tests for Multi-Region Cluster - Fixed to match actual API.
"""

import pytest
import anyio
from unittest.mock import Mock, AsyncMock, MagicMock, patch


class TestMultiRegionClusterExtended:
    """Extended tests for Multi-Region Cluster functionality."""
    
    def test_cluster_initialization(self):
        """Test cluster initialization."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        mock_ipfs = Mock()
        cluster = MultiRegionCluster(ipfs_api=mock_ipfs)
        
        assert cluster.ipfs_api == mock_ipfs
        assert cluster.regions == {}
        assert cluster.routing_strategy == "latency_optimized"
    
    def test_add_region(self):
        """Test adding a region."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        result = cluster.add_region(
            name="us-west-1",
            location="Oregon, USA",
            latency_zone="us-west",
            endpoints=["http://node1:5001", "http://node2:5001"]
        )
        
        assert result is True
        assert "us-west-1" in cluster.regions
        assert cluster.regions["us-west-1"].location == "Oregon, USA"
    
    def test_register_region(self):
        """Test registering a region object."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region
        
        cluster = MultiRegionCluster()
        
        region = Region(
            name="eu-central-1",
            location="Frankfurt, Germany",
            latency_zone="eu-central",
            endpoints=["http://node3:5001"]
        )
        
        result = cluster.register_region(region)
        
        assert result is True
        assert "eu-central-1" in cluster.regions
    
    def test_multiple_regions(self):
        """Test adding multiple regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        cluster.add_region("us-east-1", "Virginia", "us-east", ["http://node2:5001"])
        cluster.add_region("eu-west-1", "Ireland", "eu-west", ["http://node3:5001"])
        
        assert len(cluster.regions) == 3
        assert "us-west-1" in cluster.regions
        assert "us-east-1" in cluster.regions
        assert "eu-west-1" in cluster.regions
    
    @pytest.mark.anyio
    async def test_health_check_single_region(self):
        """Test health check on a single region."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        
        # Mock the endpoint check
        cluster._check_endpoint = AsyncMock(return_value=(True, 0.05))
        
        result = await cluster.health_check("us-west-1")
        
        assert result is not None
        assert "us-west-1" in result
    
    @pytest.mark.anyio
    async def test_health_check_all_regions(self):
        """Test health check on all regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        cluster.add_region("eu-west-1", "Ireland", "eu-west", ["http://node2:5001"])
        
        # Mock the endpoint check
        cluster._check_endpoint = AsyncMock(return_value=(True, 0.05))
        
        result = await cluster.health_check()
        
        assert result is not None
        assert len(result) >= 2
    
    def test_select_region_latency(self):
        """Test region selection by latency."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region, RegionStatus
        
        cluster = MultiRegionCluster()
        
        # Add regions with different latencies
        region1 = Region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        region1.average_latency = 0.05
        region1.status = RegionStatus.HEALTHY
        
        region2 = Region("us-east-1", "Virginia", "us-east", ["http://node2:5001"])
        region2.average_latency = 0.15
        region2.status = RegionStatus.HEALTHY
        
        cluster.register_region(region1)
        cluster.register_region(region2)
        
        result = cluster.select_region(strategy="latency_optimized")
        
        assert result is not None
        assert result.name == "us-west-1"  # Lower latency
    
    def test_select_region_geo_distributed(self):
        """Test region selection for geo distribution."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region, RegionStatus
        
        cluster = MultiRegionCluster()
        
        region1 = Region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        region1.status = RegionStatus.HEALTHY
        region1.used = 1000
        region1.capacity = 10000
        
        cluster.register_region(region1)
        
        result = cluster.select_region(strategy="geo_distributed")
        
        assert result is not None
    
    @pytest.mark.anyio
    async def test_replicate_to_regions(self):
        """Test replicating content to regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region, RegionStatus
        
        cluster = MultiRegionCluster()
        
        region1 = Region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        region1.status = RegionStatus.HEALTHY
        
        region2 = Region("eu-west-1", "Ireland", "eu-west", ["http://node2:5001"])
        region2.status = RegionStatus.HEALTHY
        
        cluster.register_region(region1)
        cluster.register_region(region2)
        
        # Mock replication
        cluster._replicate_to_region = AsyncMock(return_value={"success": True})
        
        result = await cluster.replicate_to_regions(
            cid="QmTest123",
            target_regions=["us-west-1", "eu-west-1"]
        )
        
        assert result is not None
        assert "cid" in result
        assert result["cid"] == "QmTest123"
        assert "regions" in result
        assert len(result["regions"]) == 2
    
    @pytest.mark.anyio
    async def test_get_closest_region(self):
        """Test getting closest region."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region, RegionStatus
        
        cluster = MultiRegionCluster()
        
        region1 = Region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        region1.status = RegionStatus.HEALTHY
        region1.average_latency = 0.05
        
        cluster.register_region(region1)
        
        result = await cluster.get_closest_region()
        
        assert result is not None
        assert result.name == "us-west-1"
    
    @pytest.mark.anyio
    async def test_failover(self):
        """Test failover handling."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region, RegionStatus
        
        cluster = MultiRegionCluster()
        
        region1 = Region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        region1.status = RegionStatus.UNAVAILABLE
        
        region2 = Region("us-east-1", "Virginia", "us-east", ["http://node2:5001"])
        region2.status = RegionStatus.HEALTHY
        
        cluster.register_region(region1)
        cluster.register_region(region2)
        
        result = await cluster.failover("us-west-1")
        
        assert result is not None
        assert "failed_region" in result
        assert result["failed_region"] == "us-west-1"
        assert "backup_regions" in result
        assert result["success"] is True
    
    def test_get_cluster_stats(self):
        """Test getting cluster statistics."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region, RegionStatus
        
        cluster = MultiRegionCluster()
        
        region1 = Region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        region1.status = RegionStatus.HEALTHY
        region1.node_count = 5
        region1.capacity = 10000
        region1.used = 2000
        
        cluster.register_region(region1)
        
        stats = cluster.get_cluster_stats()
        
        assert stats is not None
        assert "total_regions" in stats
        assert stats["total_regions"] == 1
        assert "regions_by_status" in stats
        assert stats["regions_by_status"]["healthy"] == 1
        assert "total_nodes" in stats
        assert stats["total_nodes"] == 5
    
    def test_routing_strategies(self):
        """Test different routing strategies."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        # Test changing routing strategy
        cluster.routing_strategy = "latency_optimized"
        assert cluster.routing_strategy == "latency_optimized"
        
        cluster.routing_strategy = "geo_distributed"
        assert cluster.routing_strategy == "geo_distributed"
        
        cluster.routing_strategy = "cost_optimized"
        assert cluster.routing_strategy == "cost_optimized"
    
    def test_replication_settings(self):
        """Test replication settings."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        cluster.min_replicas_per_region = 3
        cluster.cross_region_replication = False
        
        assert cluster.min_replicas_per_region == 3
        assert cluster.cross_region_replication is False
    
    def test_region_status_tracking(self):
        """Test region status tracking."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region, RegionStatus
        
        cluster = MultiRegionCluster()
        
        region = Region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        region.status = RegionStatus.HEALTHY
        
        cluster.register_region(region)
        
        # Change status
        cluster.regions["us-west-1"].status = RegionStatus.DEGRADED
        assert cluster.regions["us-west-1"].status == RegionStatus.DEGRADED
        
        cluster.regions["us-west-1"].status = RegionStatus.UNAVAILABLE
        assert cluster.regions["us-west-1"].status == RegionStatus.UNAVAILABLE
    
    def test_region_capacity_tracking(self):
        """Test region capacity tracking."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, Region
        
        cluster = MultiRegionCluster()
        
        region = Region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        region.capacity = 100000
        region.used = 25000
        
        cluster.register_region(region)
        
        # Check utilization
        utilization = region.used / region.capacity
        assert utilization == 0.25
    
    def test_multiple_endpoints_per_region(self):
        """Test regions with multiple endpoints."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        endpoints = [
            "http://node1:5001",
            "http://node2:5001",
            "http://node3:5001"
        ]
        
        cluster.add_region("us-west-1", "Oregon", "us-west", endpoints)
        
        region = cluster.regions["us-west-1"]
        assert len(region.endpoints) == 3
    
    @pytest.mark.anyio
    async def test_health_check_timeout(self):
        """Test health check timeout handling."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        
        # Mock timeout
        async def mock_timeout(*args, **kwargs):
            await anyio.sleep(10)  # Simulate long delay
            return (False, 10.0)
        
        cluster._check_endpoint = mock_timeout
        
        # Should handle timeout gracefully - use anyio timeout with proper exception handling
        try:
            with anyio.fail_after(0.1):
                await cluster.health_check("us-west-1")
            assert False, "Should have timed out"
        except TimeoutError:
            pass  # Expected timeout, test passes
    
    def test_latency_zone_grouping(self):
        """Test grouping regions by latency zone."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        cluster.add_region("us-west-2", "California", "us-west", ["http://node2:5001"])
        cluster.add_region("us-east-1", "Virginia", "us-east", ["http://node3:5001"])
        
        # Count regions by latency zone
        zones = {}
        for region in cluster.regions.values():
            if region.latency_zone not in zones:
                zones[region.latency_zone] = 0
            zones[region.latency_zone] += 1
        
        assert zones["us-west"] == 2
        assert zones["us-east"] == 1
    
    @pytest.mark.anyio
    async def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1:5001"])
        
        # Mock health check
        cluster._check_endpoint = AsyncMock(return_value=(True, 0.05))
        
        # Start monitoring (don't actually run it)
        assert cluster.is_monitoring is False
        
        # Just test the flag
        cluster.is_monitoring = True
        assert cluster.is_monitoring is True
        
        cluster.stop_monitoring()
        assert cluster.is_monitoring is False
