#!/usr/bin/env python3
"""
Unit tests for the macOS Lotus monitor functionality.

This file tests the integration between lotus_kit and the macOS monitoring tool.
"""

import os
import sys
import unittest
import platform
from unittest.mock import patch, MagicMock

# Add parent directory to path for test imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.lotus_kit import lotus_kit


class TestLotusMacOSMonitor(unittest.TestCase):
    """Test the macOS Lotus monitor functionality."""

    def setUp(self):
        """Set up test environment."""
        # Skip tests if not running on macOS
        if platform.system() != 'Darwin':
            self.skipTest("Tests only applicable on macOS")
        
        # Create a mocked lotus_kit instance for testing
        with patch('ipfs_kit_py.lotus_kit.import_module') as mock_import:
            # Create mock module and classes
            self.mock_monitor_module = MagicMock()
            self.mock_monitor_class = MagicMock()
            self.mock_monitor = MagicMock()
            
            # Configure mock monitor to return appropriate values
            self.mock_monitor.start_monitoring.return_value = {
                "success": True,
                "status": "running",
                "pid": 12345
            }
            
            self.mock_monitor.stop_monitoring.return_value = {
                "success": True,
                "message": "Monitor stopped successfully"
            }
            
            self.mock_monitor.get_status.return_value = {
                "success": True,
                "status": "running",
                "running": True,
                "daemon_health": "healthy",
                "last_check_time": "2023-07-05T12:34:56"
            }
            
            self.mock_monitor.optimize.return_value = {
                "success": True,
                "message": "Optimization completed",
                "optimizations": {
                    "memory": {
                        "KeepAlive": "Enhanced",
                        "LimitLoadToSessionType": "Background"
                    },
                    "cpu": {
                        "ProcessType": "Background",
                        "Nice": 10
                    }
                }
            }
            
            self.mock_monitor.generate_report.return_value = {
                "success": True,
                "report_path": "/tmp/lotus_report.json",
                "summary": {
                    "period": "day",
                    "restart_count": 0,
                    "avg_cpu": 5.2,
                    "avg_memory": 256.7,
                    "max_memory": 512.0
                }
            }
            
            # Set up the mock module
            self.mock_monitor_module.LotusMonitor.return_value = self.mock_monitor
            
            # Configure import_module to return our mock
            def side_effect(name):
                if name.endswith('lotus_macos_monitor'):
                    return self.mock_monitor_module
                return MagicMock()
                
            mock_import.side_effect = side_effect
            
            # Create lotus_kit instance with our mocked modules
            self.kit = lotus_kit(metadata={
                "monitor_config": {
                    "interval": 30,
                    "auto_restart": True,
                    "max_memory": 2048
                }
            })
            
            # Replace the actual monitor with our mock
            self.kit._monitor = self.mock_monitor

    def test_monitor_start(self):
        """Test monitor_start functionality."""
        result = self.kit.monitor_start(interval=45)
        
        # Verify the mock was called correctly
        self.mock_monitor.start_monitoring.assert_called_once()
        self.assertTrue('interval' in self.mock_monitor.start_monitoring.call_args[1])
        self.assertEqual(self.mock_monitor.start_monitoring.call_args[1]['interval'], 45)
        
        # Verify the returned result
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("status"), "running")
        self.assertEqual(result.get("pid"), 12345)

    def test_monitor_stop(self):
        """Test monitor_stop functionality."""
        result = self.kit.monitor_stop()
        
        # Verify the mock was called correctly
        self.mock_monitor.stop_monitoring.assert_called_once()
        
        # Verify the returned result
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("message"), "Monitor stopped successfully")

    def test_monitor_status(self):
        """Test monitor_status functionality."""
        # Test basic status
        result = self.kit.monitor_status()
        
        # Verify the mock was called correctly
        self.mock_monitor.get_status.assert_called_once()
        
        # Verify the returned result
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("status"), "running")
        self.assertEqual(result.get("daemon_health"), "healthy")
        
        # Reset mock and test detailed status
        self.mock_monitor.get_status.reset_mock()
        
        # Configure mock to return detailed metrics
        detailed_result = {
            "success": True,
            "status": "running",
            "running": True,
            "daemon_health": "healthy",
            "metrics": {
                "cpu_percent": 5.2,
                "memory_percent": 12.5,
                "disk_percent": 45.8,
                "uptime": 3600,
                "peer_count": 15
            }
        }
        self.mock_monitor.get_status.return_value = detailed_result
        
        # Get detailed status
        result = self.kit.monitor_status(detailed=True)
        
        # Verify the mock was called correctly with detailed parameter
        self.mock_monitor.get_status.assert_called_once_with(detailed=True)
        
        # Verify the returned result includes metrics
        self.assertTrue(result.get("success"))
        self.assertTrue("metrics" in result)
        self.assertEqual(result["metrics"]["cpu_percent"], 5.2)
        self.assertEqual(result["metrics"]["peer_count"], 15)

    def test_monitor_optimize(self):
        """Test monitor_optimize functionality."""
        result = self.kit.monitor_optimize(targets=["memory", "cpu"])
        
        # Verify the mock was called correctly
        self.mock_monitor.optimize.assert_called_once()
        self.assertTrue('targets' in self.mock_monitor.optimize.call_args[1])
        self.assertEqual(self.mock_monitor.optimize.call_args[1]['targets'], ["memory", "cpu"])
        
        # Verify the returned result
        self.assertTrue(result.get("success"))
        self.assertTrue("optimizations" in result)
        self.assertTrue("memory" in result["optimizations"])
        self.assertTrue("cpu" in result["optimizations"])
        self.assertEqual(result["optimizations"]["memory"]["KeepAlive"], "Enhanced")
        self.assertEqual(result["optimizations"]["cpu"]["Nice"], 10)

    def test_monitor_report(self):
        """Test monitor_report functionality."""
        result = self.kit.monitor_report(
            format="json",
            period="day",
            output_path="/tmp/report.json"
        )
        
        # Verify the mock was called correctly
        self.mock_monitor.generate_report.assert_called_once()
        self.assertTrue('format' in self.mock_monitor.generate_report.call_args[1])
        self.assertTrue('period' in self.mock_monitor.generate_report.call_args[1])
        self.assertTrue('output_path' in self.mock_monitor.generate_report.call_args[1])
        
        # Verify the returned result
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("report_path"), "/tmp/lotus_report.json")
        self.assertTrue("summary" in result)
        self.assertEqual(result["summary"]["avg_cpu"], 5.2)
        self.assertEqual(result["summary"]["restart_count"], 0)


if __name__ == '__main__':
    unittest.main()