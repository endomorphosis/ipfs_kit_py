#!/usr/bin/env python3
"""
Tests for P2P Workflow Management System

This module tests the core functionality of the peer-to-peer workflow
coordination system, including:
- Merkle clock for distributed consensus
- Fibonacci heap for priority scheduling
- Workflow coordinator for P2P task assignment
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ipfs_kit_py.merkle_clock import (
    MerkleClock,
    MerkleClockNode,
    hamming_distance,
    select_task_owner,
    create_task_hash
)

from ipfs_kit_py.fibonacci_heap import (
    FibonacciHeap,
    WorkflowPriorityQueue
)

from ipfs_kit_py.p2p_workflow_coordinator import (
    P2PWorkflowCoordinator,
    WorkflowStatus,
    WorkflowTask
)


class TestMerkleClock(unittest.TestCase):
    """Test Merkle clock functionality."""
    
    def test_create_clock(self):
        """Test creating a new Merkle clock."""
        clock = MerkleClock(peer_id="test-peer")
        self.assertEqual(clock.peer_id, "test-peer")
        self.assertEqual(clock.logical_clock, 0)
        self.assertIsNone(clock.head_hash)
    
    def test_append_event(self):
        """Test appending events to the clock."""
        clock = MerkleClock(peer_id="test-peer")
        
        node1 = clock.append({"event": "test1"})
        self.assertEqual(clock.logical_clock, 1)
        self.assertIsNotNone(node1.hash)
        self.assertIsNone(node1.parent_hash)
        
        node2 = clock.append({"event": "test2"})
        self.assertEqual(clock.logical_clock, 2)
        self.assertEqual(node2.parent_hash, node1.hash)
    
    def test_verify_chain(self):
        """Test chain verification."""
        clock = MerkleClock(peer_id="test-peer")
        clock.append({"event": "test1"})
        clock.append({"event": "test2"})
        clock.append({"event": "test3"})
        
        self.assertTrue(clock.verify_chain())
    
    def test_get_head(self):
        """Test getting the head of the clock."""
        clock = MerkleClock(peer_id="test-peer")
        self.assertIsNone(clock.get_head())
        
        node = clock.append({"event": "test"})
        head = clock.get_head()
        self.assertEqual(head.hash, node.hash)
    
    def test_serialization(self):
        """Test serializing and deserializing the clock."""
        clock = MerkleClock(peer_id="test-peer")
        clock.append({"event": "test1"})
        clock.append({"event": "test2"})
        
        # Serialize
        data = clock.to_dict()
        
        # Deserialize
        new_clock = MerkleClock.from_dict(data)
        self.assertEqual(new_clock.peer_id, clock.peer_id)
        self.assertEqual(new_clock.logical_clock, clock.logical_clock)
        self.assertEqual(len(new_clock.nodes), len(clock.nodes))


class TestHammingDistance(unittest.TestCase):
    """Test Hamming distance calculation."""
    
    def test_hamming_distance_same(self):
        """Test Hamming distance of identical strings."""
        dist = hamming_distance("abc123", "abc123")
        self.assertEqual(dist, 0)
    
    def test_hamming_distance_different(self):
        """Test Hamming distance of different strings."""
        dist = hamming_distance("abc123", "xyz789")
        self.assertEqual(dist, 6)
    
    def test_hamming_distance_partial(self):
        """Test Hamming distance of partially different strings."""
        dist = hamming_distance("abc", "axc")
        self.assertEqual(dist, 1)
    
    def test_select_task_owner(self):
        """Test task owner selection based on Hamming distance."""
        peers = ["peer-1", "peer-2", "peer-3"]
        merkle_head = "abc123"
        task_hash = "def456"
        
        selected_peer, distance = select_task_owner(merkle_head, task_hash, peers)
        self.assertIn(selected_peer, peers)
        self.assertIsInstance(distance, int)
        self.assertGreaterEqual(distance, 0)


class TestFibonacciHeap(unittest.TestCase):
    """Test Fibonacci heap functionality."""
    
    def test_create_heap(self):
        """Test creating an empty heap."""
        heap = FibonacciHeap()
        self.assertTrue(heap.is_empty())
        self.assertEqual(heap.size(), 0)
    
    def test_insert(self):
        """Test inserting items into the heap."""
        heap = FibonacciHeap()
        
        heap.insert(5.0, "task-5")
        heap.insert(3.0, "task-3")
        heap.insert(7.0, "task-7")
        
        self.assertFalse(heap.is_empty())
        self.assertEqual(heap.size(), 3)
    
    def test_find_min(self):
        """Test finding minimum without removing."""
        heap = FibonacciHeap()
        
        heap.insert(5.0, "task-5")
        heap.insert(3.0, "task-3")
        heap.insert(7.0, "task-7")
        
        min_value = heap.find_min()
        self.assertEqual(min_value, "task-3")
        self.assertEqual(heap.size(), 3)  # Size unchanged
    
    def test_extract_min(self):
        """Test extracting minimum."""
        heap = FibonacciHeap()
        
        heap.insert(5.0, "task-5")
        heap.insert(3.0, "task-3")
        heap.insert(7.0, "task-7")
        
        min_value = heap.extract_min()
        self.assertEqual(min_value, "task-3")
        self.assertEqual(heap.size(), 2)
        
        # Next minimum should be 5.0
        next_min = heap.extract_min()
        self.assertEqual(next_min, "task-5")
    
    def test_priority_order(self):
        """Test that items are extracted in priority order."""
        heap = FibonacciHeap()
        
        values = [("task-5", 5.0), ("task-1", 1.0), ("task-3", 3.0), ("task-7", 7.0)]
        for task, priority in values:
            heap.insert(priority, task)
        
        # Extract all and verify order
        extracted = []
        while not heap.is_empty():
            extracted.append(heap.extract_min())
        
        expected = ["task-1", "task-3", "task-5", "task-7"]
        self.assertEqual(extracted, expected)


class TestWorkflowPriorityQueue(unittest.TestCase):
    """Test workflow priority queue."""
    
    def test_create_queue(self):
        """Test creating a new queue."""
        queue = WorkflowPriorityQueue()
        self.assertTrue(queue.is_empty())
        self.assertEqual(queue.size(), 0)
    
    def test_add_workflow(self):
        """Test adding workflows to the queue."""
        queue = WorkflowPriorityQueue()
        
        queue.add_workflow("wf-1", priority=5.0, workflow_data={"name": "workflow-1"})
        queue.add_workflow("wf-2", priority=3.0, workflow_data={"name": "workflow-2"})
        
        self.assertEqual(queue.size(), 2)
    
    def test_get_next_workflow(self):
        """Test getting workflows in priority order."""
        queue = WorkflowPriorityQueue()
        
        queue.add_workflow("wf-high", priority=1.0, workflow_data={"name": "high-priority"})
        queue.add_workflow("wf-low", priority=5.0, workflow_data={"name": "low-priority"})
        queue.add_workflow("wf-med", priority=3.0, workflow_data={"name": "medium-priority"})
        
        # Should get high priority first
        next_wf = queue.get_next_workflow()
        self.assertEqual(next_wf["name"], "high-priority")
        
        # Then medium priority
        next_wf = queue.get_next_workflow()
        self.assertEqual(next_wf["name"], "medium-priority")


class TestP2PWorkflowCoordinator(unittest.TestCase):
    """Test P2P workflow coordinator."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.coordinator = P2PWorkflowCoordinator(
            peer_id="test-peer",
            data_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_coordinator(self):
        """Test creating a coordinator."""
        self.assertEqual(self.coordinator.peer_id, "test-peer")
        self.assertEqual(len(self.coordinator.workflows), 0)
    
    def test_submit_workflow(self):
        """Test submitting a workflow."""
        workflow_id = self.coordinator.submit_workflow(
            workflow_file="test.yml",
            name="Test Workflow",
            priority=3.0
        )
        
        self.assertIsNotNone(workflow_id)
        self.assertIn(workflow_id, self.coordinator.workflows)
        
        task = self.coordinator.workflows[workflow_id]
        self.assertEqual(task.name, "Test Workflow")
        self.assertEqual(task.priority, 3.0)
        self.assertEqual(task.status, WorkflowStatus.PENDING)
    
    def test_add_peer(self):
        """Test adding peers."""
        self.coordinator.add_peer("peer-2")
        self.coordinator.add_peer("peer-3")
        
        self.assertIn("peer-2", self.coordinator.peer_list)
        self.assertIn("peer-3", self.coordinator.peer_list)
    
    def test_assign_workflows(self):
        """Test assigning workflows to peers."""
        # Add some peers
        self.coordinator.add_peer("peer-2")
        self.coordinator.add_peer("peer-3")
        
        # Submit workflows
        wf1 = self.coordinator.submit_workflow("test1.yml", name="Workflow 1")
        wf2 = self.coordinator.submit_workflow("test2.yml", name="Workflow 2")
        
        # Assign workflows
        assigned = self.coordinator.assign_workflows()
        
        self.assertEqual(len(assigned), 2)
        self.assertIn(wf1, assigned)
        self.assertIn(wf2, assigned)
        
        # Check that workflows have been assigned
        task1 = self.coordinator.workflows[wf1]
        task2 = self.coordinator.workflows[wf2]
        
        self.assertEqual(task1.status, WorkflowStatus.ASSIGNED)
        self.assertEqual(task2.status, WorkflowStatus.ASSIGNED)
        self.assertIsNotNone(task1.assigned_peer)
        self.assertIsNotNone(task2.assigned_peer)
    
    def test_update_workflow_status(self):
        """Test updating workflow status."""
        workflow_id = self.coordinator.submit_workflow("test.yml", name="Test")
        
        # Update to in progress
        success = self.coordinator.update_workflow_status(
            workflow_id,
            WorkflowStatus.IN_PROGRESS
        )
        self.assertTrue(success)
        
        task = self.coordinator.workflows[workflow_id]
        self.assertEqual(task.status, WorkflowStatus.IN_PROGRESS)
        self.assertIsNotNone(task.started_at)
    
    def test_get_workflow_status(self):
        """Test getting workflow status."""
        workflow_id = self.coordinator.submit_workflow("test.yml", name="Test")
        
        status = self.coordinator.get_workflow_status(workflow_id)
        self.assertIsNotNone(status)
        self.assertEqual(status["workflow_id"], workflow_id)
        self.assertEqual(status["name"], "Test")
    
    def test_list_workflows(self):
        """Test listing workflows."""
        wf1 = self.coordinator.submit_workflow("test1.yml", name="Workflow 1")
        wf2 = self.coordinator.submit_workflow("test2.yml", name="Workflow 2")
        
        workflows = self.coordinator.list_workflows()
        self.assertEqual(len(workflows), 2)
        
        # Test status filter
        self.coordinator.update_workflow_status(wf1, WorkflowStatus.IN_PROGRESS)
        in_progress = self.coordinator.list_workflows(status=WorkflowStatus.IN_PROGRESS)
        self.assertEqual(len(in_progress), 1)
        self.assertEqual(in_progress[0]["workflow_id"], wf1)
    
    def test_get_stats(self):
        """Test getting coordinator statistics."""
        self.coordinator.submit_workflow("test1.yml", name="Workflow 1")
        self.coordinator.submit_workflow("test2.yml", name="Workflow 2")
        self.coordinator.add_peer("peer-2")
        
        stats = self.coordinator.get_stats()
        
        self.assertEqual(stats["peer_id"], "test-peer")
        self.assertEqual(stats["total_workflows"], 2)
        self.assertEqual(stats["peer_count"], 2)  # test-peer + peer-2
        self.assertIn("status_counts", stats)
    
    def test_persistence(self):
        """Test that coordinator state persists."""
        # Submit a workflow
        workflow_id = self.coordinator.submit_workflow("test.yml", name="Test")
        self.coordinator.add_peer("peer-2")
        
        # Create a new coordinator with same data dir
        new_coordinator = P2PWorkflowCoordinator(
            peer_id="test-peer",
            data_dir=self.temp_dir
        )
        
        # Check that state was loaded
        self.assertIn(workflow_id, new_coordinator.workflows)
        self.assertIn("peer-2", new_coordinator.peer_list)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMerkleClock))
    suite.addTests(loader.loadTestsFromTestCase(TestHammingDistance))
    suite.addTests(loader.loadTestsFromTestCase(TestFibonacciHeap))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkflowPriorityQueue))
    suite.addTests(loader.loadTestsFromTestCase(TestP2PWorkflowCoordinator))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
