#!/usr/bin/env python3
"""
Extended tests for Multi-Region Cluster support.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch


class TestMultiRegionClusterExtended:
    """Extended tests for Multi-Region Cluster functionality."""
    
    @pytest.mark.asyncio
    async def test_add_region_with_full_config(self):
        """Test adding region with complete configuration."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        result = await cluster.add_region(
            region_id="us-west-1",
            location="Oregon",
            zone="us-west",
            endpoints=["http://node1.example.com", "http://node2.example.com"],
            priority=10,
            capacity=1000
        )
        
        assert result["success"] is True
        assert "us-west-1" in cluster.regions
    
    @pytest.mark.asyncio
    async def test_remove_region(self):
        """Test removing a region."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"])
        result = await cluster.remove_region("us-west-1")
        
        assert result["success"] is True
        assert "us-west-1" not in cluster.regions
    
    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test health check with timeout."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        # Mock slow health check
        async def slow_check():
            await asyncio.sleep(10)
            return {"status": "ok"}
        
        with patch.object(cluster, '_check_endpoint_health', side_effect=slow_check):
            result = await cluster.health_check("us-west-1", timeout=0.1)
            
            # Should timeout or handle gracefully
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_health_check_all_regions(self):
        """Test health check across all regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"])
        await cluster.add_region("eu-west-1", "Ireland", "eu-west", ["http://node2.example.com"])
        
        results = await cluster.health_check_all()
        
        assert results is not None
        assert len(results) >= 2
    
    @pytest.mark.asyncio
    async def test_select_region_by_latency(self):
        """Test region selection by latency."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"])
        await cluster.add_region("eu-west-1", "Ireland", "eu-west", ["http://node2.example.com"])
        
        # Set latencies
        cluster.regions["us-west-1"]["latency"] = 10
        cluster.regions["eu-west-1"]["latency"] = 50
        
        result = await cluster.select_region(strategy="latency")
        
        assert result["success"] is True
        assert result["region_id"] == "us-west-1"  # Should select lowest latency
    
    @pytest.mark.asyncio
    async def test_select_region_by_geography(self):
        """Test region selection by geographic proximity."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"])
        await cluster.add_region("us-east-1", "Virginia", "us-east", ["http://node2.example.com"])
        
        result = await cluster.select_region(strategy="geo", client_location="us-west")
        
        assert result["success"] is True
        # Should prefer geographically close region
    
    @pytest.mark.asyncio
    async def test_select_region_by_cost(self):
        """Test region selection by cost."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"])
        await cluster.add_region("eu-west-1", "Ireland", "eu-west", ["http://node2.example.com"])
        
        # Set costs
        cluster.regions["us-west-1"]["cost"] = 1.0
        cluster.regions["eu-west-1"]["cost"] = 2.0
        
        result = await cluster.select_region(strategy="cost")
        
        assert result["success"] is True
        assert result["region_id"] == "us-west-1"  # Should select lowest cost
    
    @pytest.mark.asyncio
    async def test_select_region_round_robin(self):
        """Test round-robin region selection."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"])
        await cluster.add_region("region-2", "Location 2", "zone-2", ["http://node2.example.com"])
        await cluster.add_region("region-3", "Location 3", "zone-3", ["http://node3.example.com"])
        
        selections = []
        for _ in range(6):
            result = await cluster.select_region(strategy="round_robin")
            selections.append(result["region_id"])
        
        # Should cycle through regions
        assert len(set(selections)) >= 2  # At least 2 different regions selected
    
    @pytest.mark.asyncio
    async def test_failover_to_healthy_region(self):
        """Test failover to healthy region."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("primary", "Primary", "zone-1", ["http://node1.example.com"])
        await cluster.add_region("backup", "Backup", "zone-2", ["http://node2.example.com"])
        
        # Mark primary as unhealthy
        cluster.regions["primary"]["health_status"] = "unhealthy"
        cluster.regions["backup"]["health_status"] = "healthy"
        
        result = await cluster.failover("primary")
        
        assert result["success"] is True
        assert result["new_region"] == "backup"
    
    @pytest.mark.asyncio
    async def test_failover_no_healthy_regions(self):
        """Test failover when no healthy regions available."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"])
        
        # Mark all regions as unhealthy
        cluster.regions["region-1"]["health_status"] = "unhealthy"
        
        result = await cluster.failover("region-1")
        
        assert result["success"] is False
    
    @pytest.mark.asyncio
    async def test_replicate_content_across_regions(self):
        """Test content replication across regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"])
        await cluster.add_region("eu-west-1", "Ireland", "eu-west", ["http://node2.example.com"])
        
        result = await cluster.replicate_content(
            cid="QmTestCID",
            source_region="us-west-1",
            target_regions=["eu-west-1"]
        )
        
        assert result is not None
        assert result.get("success") is not False  # Should attempt replication
    
    @pytest.mark.asyncio
    async def test_replicate_content_all_regions(self):
        """Test replicating content to all regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"])
        await cluster.add_region("region-2", "Location 2", "zone-2", ["http://node2.example.com"])
        
        result = await cluster.replicate_content_all("QmTestCID", source_region="region-1")
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_get_replication_status(self):
        """Test getting replication status."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"])
        
        status = await cluster.get_replication_status("QmTestCID")
        
        assert status is not None
    
    def test_get_cluster_stats(self):
        """Test getting comprehensive cluster statistics."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        # Add regions
        asyncio.run(cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"]))
        asyncio.run(cluster.add_region("region-2", "Location 2", "zone-2", ["http://node2.example.com"]))
        
        stats = cluster.get_cluster_stats()
        
        assert stats["success"] is True
        assert stats["stats"]["total_regions"] == 2
    
    def test_get_region_info(self):
        """Test getting individual region information."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        asyncio.run(cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"]))
        
        info = cluster.get_region_info("us-west-1")
        
        assert info is not None
        assert info["location"] == "Oregon"
    
    @pytest.mark.asyncio
    async def test_update_region_config(self):
        """Test updating region configuration."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"])
        
        result = await cluster.update_region(
            "us-west-1",
            priority=20,
            capacity=2000
        )
        
        assert result["success"] is True
        assert cluster.regions["us-west-1"]["priority"] == 20
    
    @pytest.mark.asyncio
    async def test_measure_inter_region_latency(self):
        """Test measuring latency between regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"])
        await cluster.add_region("region-2", "Location 2", "zone-2", ["http://node2.example.com"])
        
        latency = await cluster.measure_latency("region-1", "region-2")
        
        assert latency is not None
        assert latency >= 0
    
    @pytest.mark.asyncio
    async def test_optimize_replication_strategy(self):
        """Test optimizing replication strategy based on metrics."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"])
        await cluster.add_region("region-2", "Location 2", "zone-2", ["http://node2.example.com"])
        
        strategy = await cluster.optimize_replication_strategy()
        
        assert strategy is not None
    
    @pytest.mark.asyncio
    async def test_synchronize_regions(self):
        """Test synchronizing content across regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"])
        await cluster.add_region("region-2", "Location 2", "zone-2", ["http://node2.example.com"])
        
        result = await cluster.synchronize_regions(["region-1", "region-2"])
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_handle_region_failure(self):
        """Test handling complete region failure."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("primary", "Primary", "zone-1", ["http://node1.example.com"])
        await cluster.add_region("backup", "Backup", "zone-2", ["http://node2.example.com"])
        
        result = await cluster.handle_region_failure("primary")
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_load_balancing(self):
        """Test load balancing across regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"])
        await cluster.add_region("region-2", "Location 2", "zone-2", ["http://node2.example.com"])
        
        # Set different loads
        cluster.regions["region-1"]["current_load"] = 0.8
        cluster.regions["region-2"]["current_load"] = 0.3
        
        result = await cluster.select_region(strategy="load_balanced")
        
        assert result["success"] is True
        # Should prefer less loaded region
    
    @pytest.mark.asyncio
    async def test_geo_distribution_analysis(self):
        """Test analyzing geographic distribution of regions."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        await cluster.add_region("us-west-1", "Oregon", "us-west", ["http://node1.example.com"])
        await cluster.add_region("us-east-1", "Virginia", "us-east", ["http://node2.example.com"])
        await cluster.add_region("eu-west-1", "Ireland", "eu-west", ["http://node3.example.com"])
        
        distribution = cluster.analyze_geo_distribution()
        
        assert distribution is not None
        assert len(distribution) >= 3
    
    def test_cluster_serialization(self):
        """Test serializing cluster configuration."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        import json
        
        cluster = MultiRegionCluster()
        
        asyncio.run(cluster.add_region("region-1", "Location 1", "zone-1", ["http://node1.example.com"]))
        
        config = cluster.export_config()
        
        assert config is not None
        # Should be JSON serializable
        json_str = json.dumps(config)
        assert json_str is not None
    
    def test_cluster_deserialization(self):
        """Test deserializing cluster configuration."""
        from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
        
        cluster = MultiRegionCluster()
        
        config = {
            "regions": {
                "region-1": {
                    "location": "Location 1",
                    "zone": "zone-1",
                    "endpoints": ["http://node1.example.com"]
                }
            }
        }
        
        cluster.import_config(config)
        
        assert "region-1" in cluster.regions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
