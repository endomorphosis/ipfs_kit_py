"""
Unit tests for P2P Workflow Scheduler

Tests the core functionality of the P2P workflow scheduling system including:
- MerkleClock operations
- FibonacciHeap priority queue
- Hamming distance calculation
- P2PWorkflowScheduler task management
"""

import hashlib
import time
import unittest
from unittest.mock import MagicMock, patch

# Try to import the P2P workflow scheduler
try:
    from ipfs_kit_py.p2p_workflow_scheduler import (
        P2PWorkflowScheduler,
        P2PTask,
        WorkflowTag,
        MerkleClock,
        FibonacciHeap,
        calculate_hamming_distance
    )
    P2P_AVAILABLE = True
except ImportError:
    P2P_AVAILABLE = False


@unittest.skipUnless(P2P_AVAILABLE, "P2P workflow scheduler not available")
class TestMerkleClock(unittest.TestCase):
    """Test MerkleClock functionality"""
    
    def test_initialization(self):
        """Test MerkleClock initialization"""
        clock = MerkleClock(node_id="node1")
        self.assertEqual(clock.node_id, "node1")
        self.assertEqual(clock.vector["node1"], 0)
        self.assertIsNotNone(clock.get_hash())
    
    def test_tick(self):
        """Test clock tick operation"""
        clock = MerkleClock(node_id="node1")
        initial_hash = clock.get_hash()
        
        clock.tick()
        self.assertEqual(clock.vector["node1"], 1)
        self.assertNotEqual(clock.get_hash(), initial_hash)
        
        clock.tick()
        self.assertEqual(clock.vector["node1"], 2)
    
    def test_update(self):
        """Test clock update from another clock"""
        clock1 = MerkleClock(node_id="node1")
        clock2 = MerkleClock(node_id="node2")
        
        clock1.tick()
        clock1.tick()
        clock2.tick()
        
        # Update clock2 with clock1
        clock2.update(clock1)
        
        # clock2 should have max of both vectors plus its own tick
        self.assertGreaterEqual(clock2.vector["node1"], 2)
        self.assertGreater(clock2.vector["node2"], 1)
    
    def test_compare(self):
        """Test clock comparison"""
        clock1 = MerkleClock(node_id="node1")
        clock2 = MerkleClock(node_id="node1")
        
        # Initially equal
        self.assertEqual(clock1.compare(clock2), 0)
        
        # After tick, clock1 > clock2
        clock1.tick()
        self.assertEqual(clock1.compare(clock2), 1)
        self.assertEqual(clock2.compare(clock1), -1)
    
    def test_serialization(self):
        """Test clock serialization and deserialization"""
        clock = MerkleClock(node_id="node1")
        clock.tick()
        clock.tick()
        
        # Serialize
        data = clock.to_dict()
        self.assertEqual(data["node_id"], "node1")
        self.assertEqual(data["vector"]["node1"], 2)
        self.assertIsNotNone(data["merkle_root"])
        
        # Deserialize
        clock2 = MerkleClock.from_dict(data)
        self.assertEqual(clock2.node_id, "node1")
        self.assertEqual(clock2.vector["node1"], 2)
        self.assertEqual(clock2.get_hash(), clock.get_hash())


@unittest.skipUnless(P2P_AVAILABLE, "P2P workflow scheduler not available")
class TestFibonacciHeap(unittest.TestCase):
    """Test FibonacciHeap functionality"""
    
    def test_initialization(self):
        """Test heap initialization"""
        heap = FibonacciHeap()
        self.assertTrue(heap.is_empty())
        self.assertEqual(heap.size(), 0)
    
    def test_insert(self):
        """Test heap insertion"""
        heap = FibonacciHeap()
        
        heap.insert(5, "task5")
        self.assertFalse(heap.is_empty())
        self.assertEqual(heap.size(), 1)
        
        heap.insert(3, "task3")
        heap.insert(7, "task7")
        self.assertEqual(heap.size(), 3)
    
    def test_get_min(self):
        """Test getting minimum without removal"""
        heap = FibonacciHeap()
        
        heap.insert(5, "task5")
        heap.insert(3, "task3")
        heap.insert(7, "task7")
        
        min_item = heap.get_min()
        self.assertIsNotNone(min_item)
        self.assertEqual(min_item[0], 3)
        self.assertEqual(min_item[1], "task3")
        self.assertEqual(heap.size(), 3)  # Size unchanged
    
    def test_extract_min(self):
        """Test extracting minimum"""
        heap = FibonacciHeap()
        
        heap.insert(5, "task5")
        heap.insert(3, "task3")
        heap.insert(7, "task7")
        heap.insert(1, "task1")
        
        # Extract in order
        min1 = heap.extract_min()
        self.assertEqual(min1[0], 1)
        self.assertEqual(heap.size(), 3)
        
        min2 = heap.extract_min()
        self.assertEqual(min2[0], 3)
        self.assertEqual(heap.size(), 2)
        
        min3 = heap.extract_min()
        self.assertEqual(min3[0], 5)
        self.assertEqual(heap.size(), 1)
        
        min4 = heap.extract_min()
        self.assertEqual(min4[0], 7)
        self.assertEqual(heap.size(), 0)
        
        # Empty heap
        self.assertIsNone(heap.extract_min())
    
    def test_priority_order(self):
        """Test that items are extracted in priority order"""
        heap = FibonacciHeap()
        
        # Insert in random order
        priorities = [10, 3, 15, 1, 7, 12, 5]
        for p in priorities:
            heap.insert(p, f"task{p}")
        
        # Extract and verify order
        extracted = []
        while not heap.is_empty():
            key, data = heap.extract_min()
            extracted.append(key)
        
        self.assertEqual(extracted, sorted(priorities))


@unittest.skipUnless(P2P_AVAILABLE, "P2P workflow scheduler not available")
class TestHammingDistance(unittest.TestCase):
    """Test hamming distance calculation"""
    
    def test_identical_hashes(self):
        """Test hamming distance between identical hashes"""
        hash1 = "abc123"
        hash2 = "abc123"
        distance = calculate_hamming_distance(hash1, hash2)
        self.assertEqual(distance, 0)
    
    def test_different_hashes(self):
        """Test hamming distance between different hashes"""
        hash1 = "0000"
        hash2 = "ffff"
        distance = calculate_hamming_distance(hash1, hash2)
        # All bits different: 4 hex digits * 4 bits = 16 bits
        self.assertEqual(distance, 16)
    
    def test_partial_difference(self):
        """Test hamming distance with partial differences"""
        hash1 = "0001"
        hash2 = "0000"
        distance = calculate_hamming_distance(hash1, hash2)
        # Only last bit different
        self.assertEqual(distance, 1)


@unittest.skipUnless(P2P_AVAILABLE, "P2P workflow scheduler not available")
class TestP2PTask(unittest.TestCase):
    """Test P2PTask functionality"""
    
    def test_initialization(self):
        """Test task initialization"""
        task = P2PTask(
            task_id="task1",
            workflow_id="workflow1",
            name="Test Task",
            tags=[WorkflowTag.P2P_ELIGIBLE],
            priority=5,
            created_at=time.time()
        )
        
        self.assertEqual(task.task_id, "task1")
        self.assertEqual(task.workflow_id, "workflow1")
        self.assertEqual(task.name, "Test Task")
        self.assertEqual(task.priority, 5)
        self.assertIsNotNone(task.task_hash)
    
    def test_task_hash_generation(self):
        """Test that task hash is generated correctly"""
        task1 = P2PTask(
            task_id="task1",
            workflow_id="workflow1",
            name="Test",
            tags=[],
            priority=5,
            created_at=time.time()
        )
        
        task2 = P2PTask(
            task_id="task1",
            workflow_id="workflow1",
            name="Test",
            tags=[],
            priority=5,
            created_at=time.time()
        )
        
        # Same task_id and workflow_id should produce same hash
        self.assertEqual(task1.task_hash, task2.task_hash)
        
        task3 = P2PTask(
            task_id="task2",
            workflow_id="workflow1",
            name="Test",
            tags=[],
            priority=5,
            created_at=time.time()
        )
        
        # Different task_id should produce different hash
        self.assertNotEqual(task1.task_hash, task3.task_hash)


@unittest.skipUnless(P2P_AVAILABLE, "P2P workflow scheduler not available")
class TestP2PWorkflowScheduler(unittest.TestCase):
    """Test P2PWorkflowScheduler functionality"""
    
    def setUp(self):
        """Set up test scheduler"""
        self.scheduler = P2PWorkflowScheduler(peer_id="test-peer-1")
    
    def test_initialization(self):
        """Test scheduler initialization"""
        self.assertEqual(self.scheduler.peer_id, "test-peer-1")
        self.assertIsNotNone(self.scheduler.peer_id_hash)
        self.assertEqual(len(self.scheduler.pending_tasks), 0)
        self.assertEqual(len(self.scheduler.assigned_tasks), 0)
        self.assertEqual(len(self.scheduler.completed_tasks), 0)
    
    def test_should_bypass_github(self):
        """Test GitHub bypass detection"""
        # P2P_ONLY should bypass
        self.assertTrue(
            self.scheduler.should_bypass_github([WorkflowTag.P2P_ONLY])
        )
        
        # P2P_ELIGIBLE should bypass
        self.assertTrue(
            self.scheduler.should_bypass_github([WorkflowTag.P2P_ELIGIBLE])
        )
        
        # GITHUB_API should not bypass
        self.assertFalse(
            self.scheduler.should_bypass_github([WorkflowTag.GITHUB_API])
        )
        
        # UNIT_TEST should not bypass
        self.assertFalse(
            self.scheduler.should_bypass_github([WorkflowTag.UNIT_TEST])
        )
    
    def test_is_p2p_only(self):
        """Test P2P only detection"""
        self.assertTrue(
            self.scheduler.is_p2p_only([WorkflowTag.P2P_ONLY])
        )
        
        self.assertFalse(
            self.scheduler.is_p2p_only([WorkflowTag.P2P_ELIGIBLE])
        )
    
    def test_submit_task(self):
        """Test task submission"""
        task = P2PTask(
            task_id="task1",
            workflow_id="workflow1",
            name="Test Task",
            tags=[WorkflowTag.CODE_GENERATION],
            priority=7,
            created_at=time.time()
        )
        
        success = self.scheduler.submit_task(task)
        self.assertTrue(success)
        self.assertEqual(len(self.scheduler.pending_tasks), 1)
        self.assertIn("task1", self.scheduler.pending_tasks)
        
        # Duplicate submission should fail
        success = self.scheduler.submit_task(task)
        self.assertFalse(success)
    
    def test_get_next_task_single_peer(self):
        """Test getting next task with single peer"""
        task = P2PTask(
            task_id="task1",
            workflow_id="workflow1",
            name="Test Task",
            tags=[WorkflowTag.WEB_SCRAPING],
            priority=5,
            created_at=time.time()
        )
        
        self.scheduler.submit_task(task)
        
        next_task = self.scheduler.get_next_task()
        self.assertIsNotNone(next_task)
        self.assertEqual(next_task.task_id, "task1")
        self.assertEqual(len(self.scheduler.assigned_tasks), 1)
        self.assertEqual(len(self.scheduler.pending_tasks), 0)
    
    def test_priority_ordering(self):
        """Test that tasks are processed in priority order"""
        tasks = [
            P2PTask("task1", "wf1", "Low", [WorkflowTag.P2P_ELIGIBLE], 3, time.time()),
            P2PTask("task2", "wf1", "High", [WorkflowTag.P2P_ELIGIBLE], 9, time.time()),
            P2PTask("task3", "wf1", "Med", [WorkflowTag.P2P_ELIGIBLE], 5, time.time()),
        ]
        
        for task in tasks:
            self.scheduler.submit_task(task)
        
        # Should get highest priority first (9)
        next_task = self.scheduler.get_next_task()
        self.assertEqual(next_task.task_id, "task2")
        self.assertEqual(next_task.priority, 9)
        
        # Then medium priority (5)
        next_task = self.scheduler.get_next_task()
        self.assertEqual(next_task.task_id, "task3")
        self.assertEqual(next_task.priority, 5)
        
        # Finally low priority (3)
        next_task = self.scheduler.get_next_task()
        self.assertEqual(next_task.task_id, "task1")
        self.assertEqual(next_task.priority, 3)
    
    def test_mark_task_complete(self):
        """Test marking task as complete"""
        task = P2PTask(
            task_id="task1",
            workflow_id="workflow1",
            name="Test Task",
            tags=[WorkflowTag.DATA_PROCESSING],
            priority=5,
            created_at=time.time()
        )
        
        self.scheduler.submit_task(task)
        next_task = self.scheduler.get_next_task()
        
        success = self.scheduler.mark_task_complete("task1")
        self.assertTrue(success)
        self.assertEqual(len(self.scheduler.completed_tasks), 1)
        self.assertEqual(len(self.scheduler.assigned_tasks), 0)
        
        # Marking again should fail
        success = self.scheduler.mark_task_complete("task1")
        self.assertFalse(success)
    
    def test_update_peer_state(self):
        """Test updating peer state"""
        peer_clock = MerkleClock(node_id="peer2")
        peer_clock.tick()
        
        self.scheduler.update_peer_state("peer2", peer_clock)
        
        self.assertIn("peer2", self.scheduler.known_peers)
        self.assertEqual(
            self.scheduler.known_peers["peer2"]["peer_id"],
            "peer2"
        )
    
    def test_get_status(self):
        """Test getting scheduler status"""
        status = self.scheduler.get_status()
        
        self.assertIn("peer_id", status)
        self.assertIn("merkle_clock", status)
        self.assertIn("pending_tasks", status)
        self.assertIn("assigned_tasks", status)
        self.assertIn("completed_tasks", status)
        self.assertIn("queue_size", status)
        self.assertIn("known_peers", status)
        
        self.assertEqual(status["peer_id"], "test-peer-1")
        self.assertEqual(status["pending_tasks"], 0)
        self.assertEqual(status["assigned_tasks"], 0)
        self.assertEqual(status["completed_tasks"], 0)
    
    def test_determine_task_owner(self):
        """Test task owner determination"""
        # Add a peer
        peer_clock = MerkleClock(node_id="peer2")
        self.scheduler.update_peer_state("peer2", peer_clock)
        
        task = P2PTask(
            task_id="task1",
            workflow_id="workflow1",
            name="Test Task",
            tags=[WorkflowTag.P2P_ELIGIBLE],
            priority=5,
            created_at=time.time()
        )
        
        owner = self.scheduler.determine_task_owner(task)
        
        # Owner should be one of the known peers
        self.assertIn(owner, ["test-peer-1", "peer2"])


@unittest.skipUnless(P2P_AVAILABLE, "P2P workflow scheduler not available")
class TestWorkflowTags(unittest.TestCase):
    """Test WorkflowTag enum"""
    
    def test_tag_values(self):
        """Test that tag values are correct"""
        self.assertEqual(WorkflowTag.GITHUB_API.value, "github-api")
        self.assertEqual(WorkflowTag.P2P_ELIGIBLE.value, "p2p-eligible")
        self.assertEqual(WorkflowTag.P2P_ONLY.value, "p2p-only")
        self.assertEqual(WorkflowTag.UNIT_TEST.value, "unit-test")
        self.assertEqual(WorkflowTag.CODE_GENERATION.value, "code-generation")
        self.assertEqual(WorkflowTag.WEB_SCRAPING.value, "web-scraping")
        self.assertEqual(WorkflowTag.DATA_PROCESSING.value, "data-processing")


if __name__ == "__main__":
    unittest.main()
