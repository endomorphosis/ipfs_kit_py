import unittest
import sys
import os
import tempfile
import time
import shutil
import json
from unittest.mock import patch, MagicMock

# We need to import just the cluster_state_helpers module without importing
# the entire package that has dependency issues
sys.path.insert(0, '/home/barberb/ipfs_kit_py')

# Manually mock the module dependencies before importing
mock_pyarrow = MagicMock()
mock_pyarrow.__version__ = "12.0.0"  # Mock a version number
sys.modules['pyarrow'] = mock_pyarrow
sys.modules['pyarrow.plasma'] = MagicMock()

# Mock pandas
mock_pandas = MagicMock()
mock_pandas.DataFrame = MagicMock
mock_pandas.Series = MagicMock
mock_pandas.__version__ = "2.0.0"
sys.modules['pandas'] = mock_pandas

# Mock sklearn
sys.modules['sklearn'] = MagicMock()

# Now import the helper functions directly
from ipfs_kit_py.cluster_state_helpers import (
    find_tasks_by_resource_requirements,
    find_available_node_for_task,
    get_task_execution_metrics,
    find_orphaned_content,
    estimate_time_to_completion,
    get_network_topology,
    export_state_to_json,
    get_node_by_id,
    find_tasks_by_node
)

class TestHelperFunctions(unittest.TestCase):
    """Test the cluster state helper functions."""
    
    def setUp(self):
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.test_dir, "cluster_state")
    
    def tearDown(self):
        # Remove temporary directory and all contents
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('ipfs_kit_py.cluster_state_helpers.get_all_tasks')
    def test_find_tasks_by_resource_requirements(self, mock_get_tasks):
        """Test finding tasks by resource requirements."""
        # Mock the tasks
        test_tasks = [
            {
                'id': 'task1', 
                'resources': {
                    'cpu_cores': 2, 
                    'gpu_cores': 0, 
                    'memory_mb': 512
                }
            },
            {
                'id': 'task2', 
                'resources': {
                    'cpu_cores': 4, 
                    'gpu_cores': 1, 
                    'memory_mb': 1024
                }
            },
            {
                'id': 'task3', 
                'resources': {
                    'cpu_cores': 8, 
                    'gpu_cores': 2, 
                    'memory_mb': 4096
                }
            }
        ]
        mock_get_tasks.return_value = test_tasks
        
        # Test finding tasks by CPU requirements
        result = find_tasks_by_resource_requirements(
            self.state_path, cpu_cores=4
        )
        
        # Check result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], 'task2')
        self.assertEqual(result[1]['id'], 'task3')

    @patch('ipfs_kit_py.cluster_state_helpers.get_all_content')
    @patch('ipfs_kit_py.cluster_state_helpers.get_all_tasks')
    def test_find_orphaned_content(self, mock_get_tasks, mock_get_content):
        """Test finding orphaned content."""
        # Create test content
        test_content = [
            {'cid': 'cid1', 'size': 1024},
            {'cid': 'cid2', 'size': 2048},
            {'cid': 'cid3', 'size': 4096},
            {'cid': 'cid4', 'size': 8192},
            {'cid': 'cid5', 'size': 16384}
        ]
        mock_get_content.return_value = test_content
        
        # Create test tasks with references to some content
        test_tasks = [
            {'id': 'task1', 'input_cid': 'cid1', 'output_cid': 'cid2'},
            {'id': 'task2', 'input_cids': ['cid3']},
            {'id': 'task3', 'status': 'completed', 'output_cids': ['cid4']}
        ]
        mock_get_tasks.return_value = test_tasks
        
        # Test finding orphaned content
        result = find_orphaned_content(self.state_path)

        # Expect cid2 and cid5 to be orphaned
        self.assertEqual(len(result), 2)
        orphaned_cids = {item['cid'] for item in result}
        self.assertIn('cid2', orphaned_cids)
        self.assertIn('cid5', orphaned_cids)

    @patch('ipfs_kit_py.cluster_state_helpers.get_task_by_id')
    @patch('ipfs_kit_py.cluster_state_helpers.get_all_tasks')
    def test_estimate_time_to_completion(self, mock_get_all_tasks, mock_get_task):
        """Test estimating time to completion for a task."""
        # Create a test task
        now = time.time()
        test_task = {
            'id': 'task1',
            'type': 'process',
            'status': 'running',
            'started_at': now - 50  # Started 50 seconds ago
        }
        mock_get_task.return_value = test_task
        
        # Create historical tasks of the same type
        test_all_tasks = [
            {
                'id': 'historical1',
                'type': 'process',
                'status': 'completed',
                'started_at': now - 500,
                'completed_at': now - 400  # Took 100 seconds
            },
            {
                'id': 'historical2',
                'type': 'process',
                'status': 'completed',
                'started_at': now - 300,
                'completed_at': now - 180  # Took 120 seconds
            },
            {
                'id': 'historical3',
                'type': 'process',
                'status': 'completed',
                'started_at': now - 200,
                'completed_at': now - 120  # Took 80 seconds
            }
        ]
        mock_get_all_tasks.return_value = test_all_tasks
        
        # Test estimating time to completion
        result = estimate_time_to_completion(self.state_path, 'task1')
        
        # Average execution time is (100 + 120 + 80) / 3 = 100 seconds
        # Task has been running for 50 seconds, so expected remaining is 50 seconds
        self.assertAlmostEqual(result, 50, delta=1)

    @patch('ipfs_kit_py.cluster_state_helpers.get_all_nodes')
    def test_get_network_topology(self, mock_get_nodes):
        """Test getting network topology."""
        # Create test nodes
        test_nodes = [
            {
                'id': 'node1',
                'role': 'master',
                'status': 'online',
                'peers': ['node2', 'node3'],
                'resources': {
                    'cpu_count': 8,
                    'memory_total': 16 * 1024 * 1024 * 1024,
                    'gpu_count': 0
                }
            },
            {
                'id': 'node2',
                'role': 'worker',
                'status': 'online',
                'peers': ['node1', 'node3'],
                'resources': {
                    'cpu_count': 4,
                    'memory_total': 8 * 1024 * 1024 * 1024,
                    'gpu_count': 2
                }
            },
            {
                'id': 'node3',
                'role': 'worker',
                'status': 'offline',
                'peers': ['node1', 'node2'],
                'resources': {
                    'cpu_count': 4,
                    'memory_total': 8 * 1024 * 1024 * 1024,
                    'gpu_count': 0
                }
            }
        ]
        mock_get_nodes.return_value = test_nodes
        
        # Test getting topology
        result = get_network_topology(self.state_path)
        
        # Check result format and content
        self.assertEqual(len(result["nodes"]), 3)
        self.assertEqual(result["nodes"][0]["id"], 'node1')
        self.assertEqual(result["nodes"][0]["role"], 'master')
        
        # Check connections
        self.assertEqual(len(result["connections"]), 3)

if __name__ == '__main__':
    unittest.main()
