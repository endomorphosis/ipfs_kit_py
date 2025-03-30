import unittest
import os
import tempfile
import time
import shutil
import json
from unittest.mock import patch, MagicMock

# Import module to test directly
import sys
sys.path.append('/home/barberb/ipfs_kit_py')
from ipfs_kit_py.cluster_state_helpers import (
    find_tasks_by_resource_requirements,
    find_available_node_for_task,
    get_task_execution_metrics,
    find_orphaned_content,
    estimate_time_to_completion,
    get_network_topology,
    export_state_to_json
)

class TestNewHelperFunctions(unittest.TestCase):
    """Test the newly added cluster state helper functions."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Create fake state path for testing
        self.state_path = os.path.join(self.test_dir, "cluster_state")
        os.makedirs(self.state_path, exist_ok=True)
        
        # Create fake plasma socket path
        self.plasma_socket = os.path.join(self.state_path, "plasma.sock")
        
        # Create fake metadata file
        metadata = {
            'plasma_socket': self.plasma_socket,
            'object_id': '0123456789abcdef0123',
            'schema': 'mock_schema',
            'version': 1,
            'cluster_id': 'test-cluster'
        }
        
        with open(os.path.join(self.state_path, 'state_metadata.json'), 'w') as f:
            json.dump(metadata, f)
        
        # Create dummy socket file
        with open(self.plasma_socket, 'w') as f:
            f.write('dummy')
        
    def tearDown(self):
        """Clean up after each test."""
        # Remove temporary directory and all contents
        if hasattr(self, 'test_dir') and os.path.exists(self.test_dir):
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
            },
            {
                'id': 'task4',  # No resources
                'type': 'simple'
            }
        ]
        mock_get_tasks.return_value = test_tasks
        
        # Test finding tasks by CPU requirements
        result = find_tasks_by_resource_requirements(
            self.state_path, cpu_cores=4
        )
        
        # Check calls
        mock_get_tasks.assert_called_once_with(self.state_path)
        
        # Check result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], 'task2')
        self.assertEqual(result[1]['id'], 'task3')
        
        # Test finding tasks by GPU requirements
        mock_get_tasks.reset_mock()
        result = find_tasks_by_resource_requirements(
            self.state_path, gpu_cores=1
        )
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['id'], 'task2')
        self.assertEqual(result[1]['id'], 'task3')
        
        # Test finding tasks by memory requirements
        mock_get_tasks.reset_mock()
        result = find_tasks_by_resource_requirements(
            self.state_path, memory_mb=2048
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 'task3')

if __name__ == '__main__':
    unittest.main()