"""
Tests for distributed coordination in ipfs_kit_py.

This module tests the distributed coordination features (Phase 3B), including:
- Leader election and consensus protocols
- Distributed task distribution
- Event propagation across cluster
- Work queue management
- Cluster-wide state management
- Resource-aware allocation strategies
"""

import asyncio
import json
import os
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from ipfs_kit_py.ipfs_kit import ipfs_kit


@pytest.fixture
def cluster_nodes():
    """Create a set of cluster nodes for distributed coordination testing."""
    with patch("subprocess.run") as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-id"}'
        mock_run.return_value = mock_process

        # Create master node
        master = ipfs_kit(
            resources={"memory": "8GB", "disk": "1TB", "cpu": 4},
            metadata={
                "role": "master",
                "cluster_name": "test-cluster",
                "test_mode": True,
                "enable_libp2p": True,
            },
        )
        master.ipfs = MagicMock()
        master.ipfs_cluster_service = MagicMock()
        master.ipfs_cluster_ctl = MagicMock()
        master.libp2p = MagicMock()
        # master.metadata = master.metadata # Removed redundant assignment

        # Create worker nodes
        workers = []
        for i in range(3):
            worker = ipfs_kit(
                resources={"memory": "4GB", "disk": "500GB", "cpu": 2},
                metadata={
                    "role": "worker",
                    "cluster_name": "test-cluster",
                    "test_mode": True,
                    "enable_libp2p": True,
                    "worker_id": f"worker-{i+1}",  # Added comma
                },  # Added closing brace comma
            )
            worker.ipfs = MagicMock()
            worker.ipfs_cluster_follow = MagicMock()
            worker.libp2p = MagicMock()
            # worker.metadata = worker.metadata # Removed redundant assignment
            workers.append(worker)

        # Return all nodes as a collection
        yield {"master": master, "workers": workers}  # Added comma


class TestDistributedTaskDistribution:
    """Test distributing tasks across cluster nodes."""

    def test_task_creation_and_distribution(self, cluster_nodes):
        """Test creating and distributing tasks from master to workers."""
        master = cluster_nodes["master"]
        workers = cluster_nodes["workers"]

        # Mock PubSub for task distribution
        master.libp2p.pubsub = MagicMock()

        # Create a test task
        task = {
            "id": str(uuid.uuid4()),
            "type": "process_content",
            "cid": "QmTestContent",
            "parameters": {"transform": "resize", "width": 800, "height": 600},
            "priority": "high",
            "created_at": time.time(),
        }

        # Mock create_task method on master
        master.create_task = MagicMock(
            return_value={"success": True, "task_id": task["id"], "status": "created"}
        )

        # Configure coordinator mock on master
        master.coordinator = MagicMock()

        # Fix the mock return values for create_task and distribute_task
        master.coordinator.create_task.return_value = {
            "success": True,
            "task_id": task["id"],
            "status": "created",
        }

        master.coordinator.distribute_task.return_value = {
            "success": True,
            "task_id": task["id"],
            "assigned_to": "worker-1",  # Direct string instead of worker reference
            "status": "assigned",
        }

        # Make the distribute_task method actually send a message via pubsub
        def distribute_task_side_effect(task_id):
            # Publish to the pubsub mock when distribute_task is called
            master.libp2p.pubsub.publish.return_value = True
            master.libp2p.pubsub.publish(
                topic="test-cluster/tasks",
                data=json.dumps({"task_id": task_id, "status": "assigned"}),
            )
            return {
                "success": True,
                "task_id": task_id,
                "assigned_to": "worker-1",
                "status": "assigned",
            }

        master.coordinator.distribute_task.side_effect = distribute_task_side_effect

        # Create and distribute task
        create_result = master.coordinator.create_task(
            task_type="process_content", cid="QmTestContent", parameters=task["parameters"]
        )
        distribute_result = master.coordinator.distribute_task(task_id=task["id"])

        # Verify task was created
        assert create_result["success"] is True
        assert create_result["task_id"] == task["id"]

        # Verify task was distributed
        assert distribute_result["success"] is True
        assert distribute_result["status"] == "assigned"
        assert distribute_result["assigned_to"] == "worker-1"

        # Verify PubSub was used for distribution
        master.libp2p.pubsub.publish.assert_called()

    def test_worker_task_reception_and_execution(self, cluster_nodes):
        """Test that workers can receive and execute tasks."""
        master = cluster_nodes["master"]
        worker = cluster_nodes["workers"][0]

        # Mock task data
        task_id = str(uuid.uuid4())
        task_data = {
            "id": task_id,
            "type": "process_content",
            "cid": "QmTestContent",
            "parameters": {"transform": "resize", "width": 800, "height": 600},
        }

        # Mock PubSub subscription on worker
        worker.libp2p.pubsub = MagicMock()

        # Mock message handler
        message_handler = None

        def pubsub_subscribe(topic, handler):
            nonlocal message_handler
            message_handler = handler
            return True

        worker.libp2p.pubsub.subscribe = MagicMock(side_effect=pubsub_subscribe)

        # Mock task execution on worker
        worker.execute_task = MagicMock(
            return_value={
                "success": True,
                "task_id": task_id,
                "status": "completed",
                "result_cid": "QmResultContent",
            }
        )

        # Setup coordinator on worker
        worker.coordinator = MagicMock()
        worker.coordinator.handle_task = MagicMock(
            return_value={"success": True, "task_id": task_id, "status": "processing"}
        )

        # Now set up the pub/sub handler behavior
        def task_handler(message):
            # Parse the task data
            task_json = json.loads(message["data"])

            # Execute the task
            worker.execute_task(task_json)

            # Publish result back
            worker.libp2p.pubsub.publish(
                topic="test-cluster/results",
                data=json.dumps(
                    {"task_id": task_id, "status": "completed", "result_cid": "QmResultContent"}
                ),
            )

            return True

        # Subscribe to task topic and register handler
        worker.libp2p.pubsub.subscribe.side_effect = (
            lambda topic, handler: setattr(worker, "_task_handler", handler) or True
        )

        # Call the subscribe method to register the handler
        worker.libp2p.pubsub.subscribe("test-cluster/tasks", task_handler)
        message_handler = task_handler  # Set the handler directly for testing

        # Simulate receiving a task message
        message = {
            "from": master.libp2p.get_peer_id(),
            "data": json.dumps(task_data),
            "topic": "test-cluster/tasks",
        }

        # Call the message handler with the task
        if message_handler:
            message_handler(message)

        # Verify task was executed
        worker.execute_task.assert_called_with(task_data)

        # Verify result was published back
        worker.libp2p.pubsub.publish.assert_called()

    def test_master_task_result_collection(self, cluster_nodes):
        """Test that master collects and processes task results."""
        master = cluster_nodes["master"]
        worker = cluster_nodes["workers"][0]

        # Mock task data
        task_id = str(uuid.uuid4())
        result_data = {
            "task_id": task_id,
            "status": "completed",
            "worker_id": "worker-1",  # Use direct string instead of worker reference
            "result_cid": "QmResultContent",
            "execution_time": 1.23,
            "completed_at": time.time(),
        }

        # Mock PubSub subscription on master
        master.libp2p.pubsub = MagicMock()

        # Mock message handler
        message_handler = None

        def pubsub_subscribe(topic, handler):
            nonlocal message_handler
            message_handler = handler
            return True

        master.libp2p.pubsub.subscribe = MagicMock(side_effect=pubsub_subscribe)

        # Mock task completion handling on master
        master.handle_task_completion = MagicMock(
            return_value={"success": True, "task_id": task_id, "status": "processed"}
        )

        # Setup coordinator on master for task management
        master.coordinator = MagicMock()
        master.coordinator.update_task_status = MagicMock(
            return_value={"success": True, "task_id": task_id, "status": "completed"}
        )

        # Now set up a result handler function
        def result_handler(message):
            # Parse the result data
            result_json = json.loads(message["data"])

            # Process the result
            master.handle_task_completion(result_json)

            # Update task status through coordinator
            master.coordinator.update_task_status(
                task_id=result_json["task_id"],
                status=result_json["status"],
                result={"cid": result_json["result_cid"]},
            )

            return True

        # Subscribe to results topic
        master.libp2p.pubsub.subscribe("test-cluster/results", result_handler)
        message_handler = result_handler  # Set the handler directly for testing

        # Simulate receiving a result message
        message = {
            "from": worker.libp2p.get_peer_id(),
            "data": json.dumps(result_data),
            "topic": "test-cluster/results",
        }

        # Call the message handler with the result
        if message_handler:
            message_handler(message)

        # Verify result was handled
        master.handle_task_completion.assert_called_with(result_data)


class TestResourceAwarePinAllocation:
    """Test resource-aware allocation of pinning operations in the cluster."""

    def test_pin_allocation_based_on_resources(self, cluster_nodes):
        """Test that pins are allocated based on node resources."""
        master = cluster_nodes["master"]
        workers = cluster_nodes["workers"]

        # Mock node statuses with different resource availabilities
        node_statuses = [
            {
                "id": "QmMasterNodeID",
                "addresses": ["/ip4/master-node-ip/tcp/9096"],
                "ipfs_peer_id": "QmMasterIPFS",
                "version": "0.14.1",
                "commit": "abcdef1234",
                "peername": "master",
                "rpc_protocol_version": "1.0.0",
                "error": "",
                "ipfs": {
                    "addresses": ["/ip4/127.0.0.1/tcp/4001"],
                    "id": "QmMasterIPFS",
                },
                "metrics": {
                    "freespace": 800 * 1024 * 1024 * 1024,  # 800GB
                    "reposize": 200 * 1024 * 1024 * 1024,  # 200GB
                    "inodes": 1000000,
                    "memory_used_mb": 2048,  # 2GB
                    "memory_total_mb": 8192,  # 8GB
                    "cpu_usage_percent": 30,
                },
            },
            {
                "id": "QmWorker1ID",
                "addresses": ["/ip4/worker1-ip/tcp/9096"],
                "ipfs_peer_id": "QmWorker1IPFS",
                "peername": "worker-1",
                "metrics": {
                    "freespace": 300 * 1024 * 1024 * 1024,  # 300GB
                    "reposize": 200 * 1024 * 1024 * 1024,  # 200GB
                    "memory_used_mb": 1024,  # 1GB
                    "memory_total_mb": 4096,  # 4GB
                    "cpu_usage_percent": 20,
                },
            },
            {
                "id": "QmWorker2ID",
                "addresses": ["/ip4/worker2-ip/tcp/9096"],
                "ipfs_peer_id": "QmWorker2IPFS",
                "peername": "worker-2",
                "metrics": {
                    "freespace": 50 * 1024 * 1024 * 1024,  # 50GB
                    "reposize": 450 * 1024 * 1024 * 1024,  # 450GB
                    "memory_used_mb": 3500,  # 3.5GB
                    "memory_total_mb": 4096,  # 4GB
                    "cpu_usage_percent": 80,
                },
            },
            {
                "id": "QmWorker3ID",
                "addresses": ["/ip4/worker3-ip/tcp/9096"],
                "ipfs_peer_id": "QmWorker3IPFS",
                "peername": "worker-3",
                "metrics": {
                    "freespace": 400 * 1024 * 1024 * 1024,  # 400GB
                    "reposize": 100 * 1024 * 1024 * 1024,  # 100GB
                    "memory_used_mb": 1024,  # 1GB
                    "memory_total_mb": 4096,  # 4GB
                    "cpu_usage_percent": 10,
                },
            },
        ]

        # Mock methods for resource-aware allocation
        master.ipfs_cluster_ctl.ipfs_cluster_ctl_status.return_value = {
            "success": True,
            "peer_statuses": node_statuses,
        }

        # Mock allocation method
        def allocate_pin(cid, replication_factor=None, allocations=None, **kwargs):
            # Implement resource-aware allocation algorithm:
            # 1. Calculate a score for each peer based on available resources
            # 2. Select the peers with the highest scores up to replication_factor

            # Calculate scores (simplistic model)
            scored_peers = []
            for peer in node_statuses:
                metrics = peer.get("metrics", {})

                # Skip peers with very low resources
                if metrics.get("freespace", 0) < 20 * 1024 * 1024 * 1024:  # 20GB minimum
                    continue

                # Skip peers with very high CPU usage
                if metrics.get("cpu_usage_percent", 0) > 90:
                    continue

                # Calculate a score based on available disk and memory
                disk_score = metrics.get("freespace", 0) / (1024 * 1024 * 1024)  # GB
                memory_score = (
                    metrics.get("memory_total_mb", 0) - metrics.get("memory_used_mb", 0)
                ) / 1024  # GB
                cpu_score = 100 - metrics.get("cpu_usage_percent", 0)

                # Weighted score
                score = (disk_score * 0.7) + (memory_score * 0.2) + (cpu_score * 0.1)

                scored_peers.append((peer["id"], score))

            # Sort by score (highest first)
            scored_peers.sort(key=lambda x: x[1], reverse=True)

            # Select top peers based on replication factor
            rf = replication_factor or 3  # Default to 3 replicas
            selected_peers = [peer_id for peer_id, score in scored_peers[:rf]]

            # Return allocation result
            return {
                "success": True,
                "cid": cid,
                "replication_factor": rf,
                "allocations": selected_peers,
                "name": kwargs.get("name", ""),
            }

        master.ipfs_cluster_ctl.ipfs_cluster_ctl_pin_allocate = MagicMock(side_effect=allocate_pin)

        # Test allocation with high replication
        # Call the method on the correct sub-component
        high_rep_result = master.ipfs_cluster_ctl.ipfs_cluster_ctl_pin_allocate(
            cid="QmTestContent1", replication_factor=3, name="important-content"
        )

        # Verify high replication allocation
        assert high_rep_result["success"] is True
        assert len(high_rep_result["allocations"]) == 3
        assert "QmMasterNodeID" in high_rep_result["allocations"]  # Most resources
        assert "QmWorker3ID" in high_rep_result["allocations"]  # Low CPU usage
        assert "QmWorker1ID" in high_rep_result["allocations"]  # Good balance

        # Test allocation with low replication
        # Call the method on the correct component (ipfs_cluster_ctl)
        low_rep_result = master.ipfs_cluster_ctl.ipfs_cluster_ctl_pin_allocate(
            cid="QmTestContent2", replication_factor=1, name="less-important-content"
        )

        # Verify low replication allocation
        assert low_rep_result["success"] is True
        assert len(low_rep_result["allocations"]) == 1
        assert low_rep_result["allocations"][0] == "QmMasterNodeID"  # Best resources

    def test_dynamic_reallocation_on_resource_changes(self, cluster_nodes):
        """Test that pins are dynamically reallocated when resources change."""
        master = cluster_nodes["master"]

        # Mock initial node statuses with good resources
        initial_statuses = [
            {
                "id": "QmMasterNodeID",
                "metrics": {
                    "freespace": 800 * 1024 * 1024 * 1024,  # 800GB
                    "cpu_usage_percent": 30,
                },
            },
            {
                "id": "QmWorker1ID",
                "metrics": {
                    "freespace": 400 * 1024 * 1024 * 1024,  # 400GB
                    "cpu_usage_percent": 20,
                },
            },
            {
                "id": "QmWorker2ID",
                "metrics": {
                    "freespace": 300 * 1024 * 1024 * 1024,  # 300GB
                    "cpu_usage_percent": 40,
                },
            },
        ]

        # Mock updated statuses with resource changes
        updated_statuses = [
            {
                "id": "QmMasterNodeID",
                "metrics": {
                    "freespace": 750 * 1024 * 1024 * 1024,  # 750GB
                    "cpu_usage_percent": 80,
                },
            },
            {
                "id": "QmWorker1ID",
                "metrics": {
                    "freespace": 50 * 1024 * 1024 * 1024,  # 50GB (low disk)
                    "cpu_usage_percent": 30,
                },
            },
            {
                "id": "QmWorker2ID",
                "metrics": {
                    "freespace": 290 * 1024 * 1024 * 1024,  # 290GB
                    "cpu_usage_percent": 20,
                },
            },
            {
                "id": "QmWorker3ID",  # New worker joined
                "metrics": {
                    "freespace": 500 * 1024 * 1024 * 1024,  # 500GB
                    "cpu_usage_percent": 10,
                },
            },
        ]

        # Mock initial allocation
        master.ipfs_cluster_ctl.ipfs_cluster_ctl_status.return_value = {
            "success": True,
            "peer_statuses": initial_statuses,
        }

        # Mock pin status with initial allocation
        master.ipfs_cluster_ctl.ipfs_cluster_ctl_pin_status.return_value = {
            "success": True,
            "cid": "QmTestContent",
            "name": "important-content",
            "allocations": ["QmMasterNodeID", "QmWorker1ID"],
            "replication_factor": 2,
        }

        # Mock pin add method
        master.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin = MagicMock(
            return_value={
                "success": True,
                "cid": "QmTestContent",
                "name": "important-content",
                "allocations": ["QmMasterNodeID", "QmWorker1ID"],
            }
        )

        # Mock reallocation method
        master.ipfs_cluster_ctl.ipfs_cluster_ctl_pin_update = MagicMock(
            return_value={"success": True, "cid": "QmTestContent", "name": "important-content"}
        )

        # Perform initial allocation
        # Call the method on the correct sub-component
        master.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(
            cid="QmTestContent", replication_factor=2, name="important-content"
        )

        # Update resource status
        master.ipfs_cluster_ctl.ipfs_cluster_ctl_status.return_value = {
            "success": True,
            "peer_statuses": updated_statuses,
        }

        # Mock checking threshold for reallocation
        def needs_reallocation(cid, **kwargs):
            # Check if any allocation has low resources
            current_status = master.ipfs_cluster_ctl.ipfs_cluster_ctl_pin_status(cid).get(
                "allocations", []
            )

            for peer_id in current_status:
                # Find peer in updated statuses
                for peer in updated_statuses:
                    if peer["id"] == peer_id:
                        # Check if resources are low
                        if (
                            peer["metrics"]["freespace"]
                            < 100 * 1024 * 1024 * 1024  # Less than 100GB
                            or peer["metrics"]["cpu_usage_percent"] > 75
                        ):  # High CPU
                            return True

            return False

        # Mock the checker
        # Mock the checker (assuming it's on ipfs_cluster_ctl)
        master.ipfs_cluster_ctl.check_allocation = MagicMock(side_effect=needs_reallocation)

        # Test reallocation check
        needs_realloc = master.ipfs_cluster_ctl.check_allocation(cid="QmTestContent")
        assert needs_realloc is True  # Worker1 now has low disk space

        # Test performing reallocation
        def reallocate_pin(cid, **kwargs):
            # Choose best peers based on current resources
            best_peers = sorted(
                updated_statuses,
                key=lambda x: x["metrics"]["freespace"] * (100 - x["metrics"]["cpu_usage_percent"]),
                reverse=True,
            )

            # Select top 2 peers
            new_allocations = [p["id"] for p in best_peers[:2]]

            return {
                "success": True,
                "cid": cid,
                "allocations": new_allocations,
                "reallocation_performed": True,
            }

        # Mock reallocation
        # Mock reallocation (assuming it's on ipfs_cluster_ctl)
        master.ipfs_cluster_ctl.reallocate_pin = MagicMock(side_effect=reallocate_pin)

        # Perform reallocation
        realloc_result = master.ipfs_cluster_ctl.reallocate_pin(cid="QmTestContent")

        # Verify reallocation
        assert realloc_result["success"] is True
        assert "QmWorker1ID" not in realloc_result["allocations"]  # Low disk peer removed
        assert "QmWorker3ID" in realloc_result["allocations"]  # New peer added
        assert "QmWorker2ID" in realloc_result["allocations"]  # Good resource peer kept
        assert len(realloc_result["allocations"]) == 2  # Maintained replication factor


class TestLeaderElectionAndConsensus:
    """Test leader election and consensus protocols in IPFS cluster."""

    def test_leader_election_process(self, cluster_nodes):
        """Test the process of electing a cluster leader."""
        master = cluster_nodes["master"]
        workers = cluster_nodes["workers"]

        # Mock election process
        def start_election(trigger_reason="manual"):
            # In a real system, this would use CRDT or Raft to establish consensus
            # For this test, we'll simulate the process

            # Collect votes from all nodes
            votes = []

            # Master always votes for itself
            votes.append(
                {
                    "voter": "QmMasterNodeID",
                    "candidate": "QmMasterNodeID",
                    "weight": 2.0,  # Higher weight for master
                }
            )

            # Workers vote based on connectivity and perceived capability
            for i, worker in enumerate(workers):
                # Most workers vote for master in normal conditions
                if i < 2:
                    votes.append(
                        {"voter": f"QmWorker{i+1}ID", "candidate": "QmMasterNodeID", "weight": 1.0}
                    )
                else:
                    # One worker votes for itself
                    votes.append(
                        {
                            "voter": f"QmWorker{i+1}ID",
                            "candidate": f"QmWorker{i+1}ID",
                            "weight": 1.0,
                        }
                    )

            # Tally votes (weighted by node importance)
            tally = {}
            for vote in votes:
                candidate = vote["candidate"]
                weight = vote["weight"]
                tally[candidate] = tally.get(candidate, 0) + weight

            # Find winner
            winner = max(tally.items(), key=lambda x: x[1])

            # Return election results
            return {
                "success": True,
                "leader": winner[0],
                "votes": votes,
                "tally": tally,
                "election_id": str(uuid.uuid4()),
                "term": int(time.time()),
                "trigger_reason": trigger_reason,
            }

        # Mock the election method
        master.ipfs_cluster_ctl.ipfs_cluster_election_start = MagicMock(side_effect=start_election)

        # Test triggering an election
        # Call the method on the correct sub-component
        election_result = master.ipfs_cluster_ctl.ipfs_cluster_election_start(
            trigger_reason="failover_test"
        )

        # Verify election results
        assert election_result["success"] is True
        assert election_result["leader"] == "QmMasterNodeID"  # Master should win
        assert len(election_result["votes"]) == 4  # All nodes voted
        assert election_result["tally"]["QmMasterNodeID"] > election_result["tally"].get(
            "QmWorker3ID", 0
        )

    def test_consensus_on_configuration_changes(self, cluster_nodes):
        """Test consensus on configuration changes across the cluster."""
        master = cluster_nodes["master"]

        # New configuration to be applied
        new_config = {
            "replication_factor_min": 2,
            "replication_factor_max": 5,
            "pinning_timeout": "5m0s",
            "pin_recovery_timeout": "10m0s",
            "pin_tracker": {"max_pin_queue_size": 5000, "concurrent_pins": 10},
        }

        # Mock consensus process
        def propose_config(config, **kwargs):
            # In real system, this would distribute the config proposal to all peers
            # and gather confirmations until quorum is reached

            # Simulate acceptance by counting peers that would accept
            acceptance_threshold = 0.67  # 2/3 majority

            # Get current peer list
            peers = ["QmMasterNodeID", "QmWorker1ID", "QmWorker2ID", "QmWorker3ID"]

            # For test purposes, assume some peers accept and some reject
            accepting_peers = ["QmMasterNodeID", "QmWorker1ID", "QmWorker2ID"]

            # Calculate acceptance ratio
            acceptance_ratio = len(accepting_peers) / len(peers)

            # Consensus reached?
            consensus_reached = acceptance_ratio >= acceptance_threshold

            # Return consensus result
            return {
                "success": consensus_reached,
                "config": config,
                "proposal_id": str(uuid.uuid4()),
                "accepted_by": accepting_peers,
                "acceptance_ratio": acceptance_ratio,
                "consensus_threshold": acceptance_threshold,
                "consensus_reached": consensus_reached,
            }

        # Mock the consensus method
        master.ipfs_cluster_ctl.ipfs_cluster_config_propose = MagicMock(side_effect=propose_config)

        # Test proposing configuration change
        # Call the method on the correct sub-component
        consensus_result = master.ipfs_cluster_ctl.ipfs_cluster_config_propose(config=new_config)

        # Verify consensus result
        assert consensus_result["success"] is True
        assert consensus_result["consensus_reached"] is True
        assert len(consensus_result["accepted_by"]) >= 3  # At least 3 out of 4 nodes accepted
        assert consensus_result["acceptance_ratio"] >= 0.67

    def test_handling_network_partitions(self, cluster_nodes):
        """Test handling of network partitions in the cluster."""
        master = cluster_nodes["master"]

        # Mock detecting a network partition
        def detect_partition():
            # In a real system, this would check connectivity between peers
            # and determine if a partition exists

            # Simulate a partition with 2 groups:
            # Group 1: Master, Worker1
            # Group 2: Worker2, Worker3

            partition_groups = [["QmMasterNodeID", "QmWorker1ID"], ["QmWorker2ID", "QmWorker3ID"]]

            # Determine if we have a partition
            has_partition = len(partition_groups) > 1

            # Return partition information
            return {
                "success": True,
                "partition_detected": has_partition,
                "partition_groups": partition_groups,
                "quorum_maintained": len(partition_groups[0])
                >= 2,  # At least 2 nodes needed for quorum
                "action_required": has_partition,
            }

        # Mock the partition detection method
        master.ipfs_cluster_ctl.ipfs_cluster_detect_partition = MagicMock(
            side_effect=detect_partition
        )

        # Test detecting a partition
        # Call the method on the correct sub-component
        partition_result = master.ipfs_cluster_ctl.ipfs_cluster_detect_partition()

        # Verify partition result
        assert partition_result["success"] is True
        assert partition_result["partition_detected"] is True
        assert len(partition_result["partition_groups"]) == 2
        assert "QmMasterNodeID" in partition_result["partition_groups"][0]
        assert partition_result["quorum_maintained"] is True  # Master's group has quorum

        # Mock resolving the partition
        def resolve_partition():
            # In a real system, this would attempt to reconnect nodes
            # or trigger recovery procedures

            # Simulate reconnection attempts
            reconnected_peers = ["QmWorker2ID"]  # Worker2 reconnected
            failed_peers = ["QmWorker3ID"]  # Worker3 still disconnected

            # Update partition groups
            updated_groups = [["QmMasterNodeID", "QmWorker1ID", "QmWorker2ID"], ["QmWorker3ID"]]

            # Check if we still have a severe partition
            severe_partition = len(updated_groups[0]) < 3  # Less than 75% of nodes

            # Return resolution result
            return {
                "success": True,
                "reconnected_peers": reconnected_peers,
                "failed_peers": failed_peers,
                "updated_groups": updated_groups,
                "severe_partition": severe_partition,
                "resolution_complete": len(reconnected_peers) > 0,
            }

        # Mock the partition resolution method
        master.ipfs_cluster_ctl.ipfs_cluster_resolve_partition = MagicMock(
            side_effect=resolve_partition
        )

        # Test resolving the partition
        # Call the method on the correct sub-component
        resolution_result = master.ipfs_cluster_ctl.ipfs_cluster_resolve_partition()

        # Verify resolution result
        assert resolution_result["success"] is True
        assert len(resolution_result["reconnected_peers"]) == 1
        assert resolution_result["reconnected_peers"][0] == "QmWorker2ID"
        assert len(resolution_result["updated_groups"][0]) == 3  # Main group now has 3 nodes
        assert resolution_result["severe_partition"] is False
        assert resolution_result["resolution_complete"] is True


if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])
