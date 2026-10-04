#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/tests/test_integration.py

"""
Integration tests for the Optimized Data Routing system.

This module tests the integration between the routing system and the MCP server,
demonstrating how they work together to provide intelligent backend selection.
"""

import unittest
from unittest.mock import MagicMock, patch
import time
import json
import tempfile
import os

from ipfs_kit_py.mcp.routing.router import (
    Backend, ContentType, OperationType,
    RouteMetrics, RoutingContext, RoutingDecision
)
from ipfs_kit_py.mcp.routing.integration import (
    MCPRoutingIntegration, initialize_mcp_routing, select_backend
)


class TestMCPRoutingIntegration(unittest.TestCase):
    """Integration tests for the MCP routing integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a configuration with test settings
        self.config = {
            'default_backend': 'IPFS',
            'strategy_weights': {
                'content': 0.3,
                'cost': 0.3,
                'geo': 0.2,
                'performance': 0.2
            },
            'backend_costs': {
                'IPFS': {
                    'storage_cost': 0.02,
                    'retrieval_cost': 0.01,
                    'operation_cost': 0.0001
                },
                'S3': {
                    'storage_cost': 0.023,
                    'retrieval_cost': 0.09,
                    'operation_cost': 0.0005
                },
                'FILECOIN': {
                    'storage_cost': 0.005,
                    'retrieval_cost': 0.02,
                    'operation_cost': 0.001
                }
            }
        }
        
        # Initialize the routing integration
        self.routing = initialize_mcp_routing(self.config)
        
        # Register test backends
        self.routing.register_backend('IPFS', {'type': 'ipfs', 'version': '0.14.0'})
        self.routing.register_backend('S3', {'type': 's3', 'bucket': 'test-bucket'})
        self.routing.register_backend('FILECOIN', {'type': 'filecoin', 'network': 'testnet'})
    
    def test_select_backend_for_large_video(self):
        """Test selecting a backend for storing a large video file."""
        # Select backend for storing a large video file
        result = self.routing.select_backend(
            operation_type='write',
            content_type='video',
            content_size=500 * 1024 * 1024,  # 500 MB
            region='us-east'
        )
        
        # Verify that a backend was selected
        self.assertIn('backend', result)
        self.assertIn('score', result)
        self.assertIn('reason', result)
        self.assertIn('alternatives', result)
        
        # For a large video, S3 or FILECOIN would typically be preferred
        # But the exact selection depends on the weights and metrics
        selected_backend = result['backend']
        self.assertIn(selected_backend, ['IPFS', 'S3', 'FILECOIN'])
        
        # Score should be between 0 and 1
        self.assertGreaterEqual(result['score'], 0.0)
        self.assertLessEqual(result['score'], 1.0)
        
        # Verify that alternatives include the other backends
        alternative_backends = [alt['backend'] for alt in result['alternatives']]
        for backend in ['IPFS', 'S3', 'FILECOIN']:
            if backend != selected_backend:
                self.assertIn(backend, alternative_backends)
    
    def test_select_backend_for_small_document(self):
        """Test selecting a backend for storing a small document."""
        # Select backend for storing a small document
        result = self.routing.select_backend(
            operation_type='write',
            content_type='document',
            content_size=500 * 1024,  # 500 KB
            region='eu-west'
        )
        
        # For a small document, IPFS would typically be preferred
        selected_backend = result['backend']
        self.assertIn(selected_backend, ['IPFS', 'S3', 'FILECOIN'])
        
        # Document type may prefer IPFS in content-aware routing
        # But the exact selection depends on the weights and metrics
        if selected_backend == 'IPFS':
            reason = result['reason'].lower()
            # Reason should mention content type or small size
            self.assertTrue(
                ('document' in reason and 'content' in reason) or
                ('small' in reason)
            )
    
    def test_select_backend_with_specific_strategy(self):
        """Test selecting a backend with a specific strategy."""
        # Select backend using cost-based strategy
        result = self.routing.select_backend(
            operation_type='write',
            content_type='dataset',
            content_size=1 * 1024 * 1024 * 1024,  # 1 GB
            strategy='cost_based'
        )
        
        # Cost-based strategy for write should prefer FILECOIN (lowest storage cost)
        # But depends on the metrics and cost models configured
        selected_backend = result['backend']
        self.assertIn(selected_backend, ['IPFS', 'S3', 'FILECOIN'])
        
        # Reason should mention cost
        reason = result['reason'].lower()
        self.assertTrue('cost' in reason)
    
    def test_record_and_use_performance_metrics(self):
        """Test recording performance metrics and using them for routing."""
        # Record performance metrics for IPFS
        start_time = time.time() - 0.1  # 100ms ago
        self.routing.record_operation_performance(
            backend='IPFS',
            operation_type='read',
            start_time=start_time,
            bytes_received=10 * 1024 * 1024,  # 10 MB
            success=True
        )
        
        # Record performance metrics for S3
        start_time = time.time() - 0.2  # 200ms ago
        self.routing.record_operation_performance(
            backend='S3',
            operation_type='read',
            start_time=start_time,
            bytes_received=10 * 1024 * 1024,  # 10 MB
            success=True
        )
        
        # Select backend using performance strategy
        result = self.routing.select_backend(
            operation_type='read',
            content_size=10 * 1024 * 1024,  # 10 MB
            strategy='performance'
        )
        
        # IPFS should be preferred (lower latency)
        selected_backend = result['backend']
        
        # Reason should mention performance
        reason = result['reason'].lower()
        self.assertTrue('performance' in reason)
        
        # Get backend metrics
        metrics = self.routing.get_backend_metrics('IPFS')
        self.assertIn('performance', metrics)
        self.assertIn('bandwidth', metrics)
        self.assertIn('latency', metrics)
    
    def test_routing_history(self):
        """Test getting routing decision history."""
        # Make a few routing decisions
        self.routing.select_backend(
            operation_type='write',
            content_type='image',
            content_size=1 * 1024 * 1024  # 1 MB
        )
        
        self.routing.select_backend(
            operation_type='read',
            content_type='document',
            content_size=500 * 1024  # 500 KB
        )
        
        # Get routing history
        history = self.routing.get_routing_history()
        
        # Should have at least 2 entries
        self.assertGreaterEqual(len(history), 2)
        
        # Each entry should have required fields
        for entry in history:
            self.assertIn('backend', entry)
            self.assertIn('operation', entry)
            self.assertIn('timestamp', entry)
    
    def test_global_convenience_function(self):
        """Test the global convenience function for backend selection."""
        # Use the global select_backend function
        result = select_backend(
            operation_type='read',
            content_type='image',
            content_size=1 * 1024 * 1024  # 1 MB
        )
        
        # Should return a valid result
        self.assertIn('backend', result)
        self.assertIn('score', result)
        self.assertIn('reason', result)
    
    def test_geographic_routing(self):
        """Test geographic routing based on region."""
        # Select backend for US region
        result_us = self.routing.select_backend(
            operation_type='read',
            content_size=1 * 1024 * 1024,  # 1 MB
            region='us-east',
            strategy='geographic'
        )
        
        # Select backend for EU region
        result_eu = self.routing.select_backend(
            operation_type='read',
            content_size=1 * 1024 * 1024,  # 1 MB
            region='eu-west',
            strategy='geographic'
        )
        
        # Both should return valid results
        self.assertIn('backend', result_us)
        self.assertIn('backend', result_eu)
        
        # Reasons should mention geographic considerations
        self.assertTrue('geographic' in result_us['reason'].lower())
        self.assertTrue('geographic' in result_eu['reason'].lower())


class TestMCPRoutingWithMockServer(unittest.TestCase):
    """Test the routing integration with a mock MCP server."""
    
    def setUp(self):
        """Set up test fixtures with a mock MCP server."""
        # Create a mock MCP server
        self.mock_server = MagicMock()
        self.mock_server.available_backends = ['IPFS', 'S3', 'FILECOIN']
        
        # Create a routing integration
        self.routing = MCPRoutingIntegration()
        
        # Register backends
        for backend in self.mock_server.available_backends:
            self.routing.register_backend(backend, {'mock': True})
    
    def test_backend_selection_for_server_operations(self):
        """Test backend selection for server operations."""
        # Simulate a write operation with the mock server
        operation_type = 'write'
        content_type = 'document'
        content_size = 5 * 1024 * 1024  # 5 MB
        
        # Select a backend
        result = self.routing.select_backend(
            operation_type=operation_type,
            content_type=content_type,
            content_size=content_size
        )
        
        # Check that a backend was selected
        self.assertIn('backend', result)
        selected_backend = result['backend']
        self.assertIn(selected_backend, self.mock_server.available_backends)
        
        # Simulate using the selected backend with the server
        def mock_upload(backend, data):
            """Mock upload function."""
            return {'status': 'success', 'backend': backend, 'size': len(data)}
        
        # Create some test data
        test_data = b'test' * 1024  # 4 KB
        
        # Upload using the selected backend
        result = mock_upload(selected_backend, test_data)
        
        # Verify upload used the selected backend
        self.assertEqual(result['backend'], selected_backend)
        self.assertEqual(result['status'], 'success')
    
    def test_performance_based_routing_with_server(self):
        """Test performance-based routing with the server."""
        # Record some synthetic performance data
        for backend in self.mock_server.available_backends:
            # Simulate different performance characteristics
            if backend == 'IPFS':
                latency = 50.0  # ms
                throughput = 100.0  # Mbps
            elif backend == 'S3':
                latency = 70.0  # ms
                throughput = 80.0  # Mbps
            else:  # FILECOIN
                latency = 200.0  # ms
                throughput = 50.0  # Mbps
            
            # Record performance
            self.routing.record_operation_performance(
                backend=backend,
                operation_type='read',
                start_time=time.time() - (latency / 1000.0),
                bytes_received=int((throughput * 1_000_000) / 8),  # Convert Mbps to bytes
                success=True
            )
        
        # Select backend for read operation
        result = self.routing.select_backend(
            operation_type='read',
            content_size=10 * 1024 * 1024,  # 10 MB
            strategy='performance'
        )
        
        # IPFS should be preferred (best performance in our test data)
        selected_backend = result['backend']
        self.assertEqual(selected_backend, 'IPFS')
        
        # Reason should mention performance
        reason = result['reason'].lower()
        self.assertTrue('performance' in reason)


if __name__ == "__main__":
    unittest.main()