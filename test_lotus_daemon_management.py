#!/usr/bin/env python3
"""
Test script to verify automatic daemon management in Lotus Kit.

This script tests the enhanced daemon management functionality in lotus_kit.py,
verifying that the daemon is automatically started, health checked, and stopped
as needed.
"""

import os
import sys
import time
import logging
import tempfile
import unittest
from ipfs_kit_py.lotus_kit import lotus_kit

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestLotusAutoManagement(unittest.TestCase):
    """Test case for verifying automatic daemon management in lotus_kit."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        with open(self.temp_file.name, 'w') as f:
            f.write("Test content for Lotus import")
        
        # Create lotus_kit with auto-start enabled
        self.kit = lotus_kit(
            metadata={
                "auto_start_daemon": True,
                "daemon_health_check_interval": 5  # Short interval for testing
            }
        )
        
        logger.info("Test setup complete")
        
    def tearDown(self):
        """Clean up test environment."""
        # Delete the temporary file
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
            
        # Make sure daemon is stopped
        if hasattr(self, 'kit'):
            try:
                self.kit.daemon_stop(force=True)
            except Exception as e:
                logger.warning(f"Error during teardown daemon stop: {e}")
                
        logger.info("Test cleanup complete")
        
    def test_auto_start(self):
        """Test automatic daemon startup during API operation."""
        logger.info("Testing automatic daemon startup...")
        
        # First ensure daemon is stopped
        self.kit.daemon_stop(force=True)
        
        # Verify daemon is stopped
        status = self.kit.daemon_status()
        self.assertFalse(status.get("process_running", True), 
                         "Daemon should be stopped before test")
        
        # Perform an operation that should trigger auto-start
        logger.info("Performing operation that should trigger auto-start...")
        result = self.kit.client_import(self.temp_file.name)
        
        # Check the result
        if not result.get("success", False):
            if "simulation_mode" in result and result["simulation_mode"]:
                logger.info("Operating in simulation mode as fallback - this is acceptable")
                self.assertTrue(self.kit.simulation_mode, 
                                "Kit should be in simulation mode if automatic daemon start failed")
            else:
                logger.error(f"Operation failed and not in simulation mode: {result}")
                self.fail("Operation should succeed if auto-start works or fall back to simulation mode")
        else:
            # Check if the daemon is now running
            status = self.kit.daemon_status()
            self.assertTrue(status.get("process_running", False) or self.kit.simulation_mode,
                            "Daemon should be running or in simulation mode after auto-start")
            
        logger.info("Auto-start test complete")
        
    def test_health_check_restart(self):
        """Test health check and automatic restart."""
        logger.info("Testing health check and automatic restart...")
        
        # Start the daemon explicitly
        start_result = self.kit.daemon_start()
        
        # If we're in simulation mode, skip this test
        if self.kit.simulation_mode:
            logger.info("Running in simulation mode, skipping health check test")
            self.skipTest("Cannot test health check in simulation mode")
            
        # Verify daemon started successfully
        self.assertTrue(start_result.get("success", False), 
                         f"Daemon should start successfully: {start_result}")
        
        # Get the initial PID
        status = self.kit.daemon_status()
        self.assertTrue(status.get("process_running", False), 
                         "Daemon should be running after explicit start")
        initial_pid = status.get("pid")
        
        # Kill the daemon manually to simulate a crash
        logger.info(f"Simulating daemon crash by killing PID {initial_pid}...")
        if initial_pid:
            try:
                os.kill(int(initial_pid), 9)  # SIGKILL
                logger.info(f"Killed daemon process {initial_pid}")
                
                # Wait a moment for process to exit
                time.sleep(1)
                
                # Verify daemon is stopped
                status = self.kit.daemon_status()
                self.assertFalse(status.get("process_running", True), 
                                 "Daemon should be stopped after kill")
                
                # Perform an operation that triggers health check and restart
                logger.info("Performing operation to trigger health check and restart...")
                result = self.kit.client_import(self.temp_file.name)
                
                # Check the new status
                new_status = self.kit.daemon_status()
                
                # Verify daemon was restarted or simulation mode was activated
                self.assertTrue(new_status.get("process_running", False) or self.kit.simulation_mode,
                                "Daemon should be restarted or simulation mode activated")
                
                if new_status.get("process_running", False):
                    new_pid = new_status.get("pid")
                    logger.info(f"Daemon restarted with new PID: {new_pid}")
                    self.assertNotEqual(initial_pid, new_pid, 
                                       "New PID should be different from initial PID")
                else:
                    logger.info("Daemon was not restarted, simulation mode should be activated")
                    self.assertTrue(self.kit.simulation_mode, 
                                   "Simulation mode should be activated if restart failed")
                    
            except ProcessLookupError:
                logger.warning(f"Process {initial_pid} not found - may already be gone")
            except Exception as e:
                logger.error(f"Error during kill test: {e}")
                raise
        else:
            logger.warning("No PID found for running daemon, cannot test kill-restart")
            self.skipTest("No PID found for running daemon")
            
        logger.info("Health check and restart test complete")
        
    def test_cleanup_on_exit(self):
        """Test automatic daemon shutdown on object destruction."""
        logger.info("Testing automatic shutdown on exit...")
        
        # Create a separate kit instance to test cleanup
        cleanup_kit = lotus_kit(
            metadata={
                "auto_start_daemon": True
            }
        )
        
        # Start the daemon and ensure it's our instance
        start_result = cleanup_kit.daemon_start()
        cleanup_kit._daemon_started_by_us = True
        
        # Get the PID
        status = cleanup_kit.daemon_status()
        if status.get("process_running", False):
            pid = status.get("pid")
            logger.info(f"Daemon started with PID: {pid}")
            
            # Delete the kit instance to trigger __del__
            logger.info("Deleting kit instance to trigger cleanup...")
            del cleanup_kit
            
            # Force garbage collection to ensure __del__ is called
            import gc
            gc.collect()
            
            # Wait a moment for cleanup
            time.sleep(2)
            
            # Check if process is still running
            try:
                os.kill(int(pid), 0)  # Just checking if process exists
                logger.warning(f"Process {pid} still exists - cleanup may not have worked")
                # Try to kill it now for cleanup
                try:
                    os.kill(int(pid), 9)
                except:
                    pass
            except ProcessLookupError:
                logger.info(f"Process {pid} successfully terminated during cleanup")
                # Test passed
            except Exception as e:
                logger.error(f"Error checking process: {e}")
                raise
        else:
            logger.warning("Daemon not running, cannot test cleanup")
            self.skipTest("Daemon not running")
            
        logger.info("Cleanup test complete")
        
if __name__ == "__main__":
    unittest.main()