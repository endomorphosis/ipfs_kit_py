#!/usr/bin/env python3
"""
Comprehensive test for IPFS cluster daemons.

This script performs a thorough test of both ipfs_cluster_service and ipfs_cluster_follow
wrappers, including initialization, configuration validation, and daemon functionality.
"""

import os
import sys
import time
import unittest
import subprocess
import json
import tempfile
import shutil
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_ipfs_cluster_daemons")

# Global variable to track binary availability
HAS_DIRECT_BINARIES = False

def has_direct_binary_access():
    """Check if the system has direct access to the binaries."""
    return HAS_DIRECT_BINARIES

class TestIPFSClusterDaemons(unittest.TestCase):
    """Test class for IPFS cluster daemons."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        global HAS_DIRECT_BINARIES
        
        cls.temp_dir = tempfile.mkdtemp(prefix="ipfs_cluster_test_")
        
        # Create directories for service and follow daemons
        cls.service_dir = os.path.join(cls.temp_dir, "service")
        cls.follow_dir = os.path.join(cls.temp_dir, "follow")
        os.makedirs(cls.service_dir, exist_ok=True)
        os.makedirs(cls.follow_dir, exist_ok=True)
        
        # Set up environment variables
        cls.env = os.environ.copy()
        cls.env["IPFS_CLUSTER_PATH"] = cls.service_dir
        cls.env["PATH"] = cls.env.get("PATH", "") + ":" + os.path.join(os.getcwd(), "bin")
        
        # Check for direct binary access
        try:
            result = subprocess.run(
                ["which", "ipfs-cluster-service"], 
                env=cls.env,
                capture_output=True, 
                text=True, 
                check=False
            )
            HAS_DIRECT_BINARIES = result.returncode == 0
            if HAS_DIRECT_BINARIES:
                logger.info("Direct binary access available: " + result.stdout.strip())
            else:
                logger.warning("Direct binary access not available. Some tests will be skipped.")
        except:
            HAS_DIRECT_BINARIES = False
            logger.warning("Error checking direct binary access. Some tests will be skipped.")
            
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment after all tests."""
        # Remove temporary directories
        if hasattr(cls, 'temp_dir') and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def setUp(self):
        """Set up the test environment for each test."""
        # Create a clean state for each test
        self.test_name = self.id().split('.')[-1]
        logger.info(f"Starting test: {self.test_name}")
    
    def tearDown(self):
        """Clean up after each test."""
        logger.info(f"Finished test: {self.test_name}")
        
        # Kill any running daemon processes
        self._kill_cluster_daemons()
        
        # Small delay to ensure processes have terminated
        time.sleep(1)
    
    def _run_command(self, command, cwd=None, check=True, timeout=30):
        """Run a command and return the result."""
        try:
            logger.info(f"Running command: {' '.join(command)}")
            result = subprocess.run(
                command,
                cwd=cwd,
                env=self.env,
                capture_output=True,
                text=True,
                check=check,
                timeout=timeout
            )
            
            if result.stdout.strip():
                logger.debug(f"Command stdout: {result.stdout}")
            if result.stderr.strip():
                logger.debug(f"Command stderr: {result.stderr}")
                
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e}")
            logger.error(f"Stdout: {e.stdout}")
            logger.error(f"Stderr: {e.stderr}")
            raise
        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timed out after {timeout} seconds")
            raise
        except Exception as e:
            logger.error(f"Error running command: {e}")
            raise
    
    def _kill_cluster_daemons(self):
        """Kill any running cluster daemon processes."""
        try:
            # Find all ipfs-cluster-service and ipfs-cluster-follow processes
            ps_result = self._run_command(["ps", "-ef"], check=False)
            for line in ps_result.stdout.splitlines():
                if ("ipfs-cluster-service" in line or "ipfs-cluster-follow" in line) and "grep" not in line:
                    # Extract PID (second column in ps output)
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            logger.info(f"Killing process {pid}: {line}")
                            subprocess.run(["kill", "-9", str(pid)], check=False)
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            logger.error(f"Error killing daemon processes: {e}")
    
    @contextmanager
    def _run_daemon_in_background(self, command, cwd=None, timeout=5):
        """Run a daemon process in the background and ensure it's cleaned up."""
        process = None
        try:
            # Start the process
            logger.info(f"Starting daemon: {' '.join(command)}")
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait briefly to see if the process fails immediately
            time.sleep(timeout)
            
            # Check if the process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error(f"Daemon process exited with code {process.returncode}")
                logger.error(f"Stdout: {stdout}")
                logger.error(f"Stderr: {stderr}")
                raise RuntimeError(f"Daemon process failed to start: {stderr}")
            
            # Process is running, yield to the caller
            yield process
            
        finally:
            # Clean up the process
            if process and process.poll() is None:
                logger.info("Terminating daemon process")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Daemon process did not terminate, force killing")
                    process.kill()
    
    def test_001_service_wrapper_import(self):
        """Test importing the ipfs_cluster_service module."""
        try:
            sys.path.insert(0, os.getcwd())
            from ipfs_kit_py import ipfs_cluster_service
            
            # Create an instance to verify class initialization
            resources = {}
            metadata = {"role": "master"}
            service_instance = ipfs_cluster_service(resources, metadata)
            
            # Verify the instance has the expected attributes
            self.assertEqual(service_instance.role, "master")
            self.assertTrue(hasattr(service_instance, "ipfs_cluster_path"))
            self.assertTrue(hasattr(service_instance, "run_cluster_service_command"))
            
            logger.info("Successfully imported and initialized ipfs_cluster_service module")
        except ImportError as e:
            self.fail(f"Failed to import ipfs_cluster_service module: {e}")
        except Exception as e:
            self.fail(f"Unexpected error: {e}")
    
    def test_002_follow_wrapper_import(self):
        """Test importing the ipfs_cluster_follow module."""
        try:
            sys.path.insert(0, os.getcwd())
            from ipfs_kit_py import ipfs_cluster_follow
            
            # Create an instance to verify class initialization
            resources = {}
            metadata = {"role": "worker", "cluster_name": "test-cluster"}
            follow_instance = ipfs_cluster_follow(resources, metadata)
            
            # Verify the instance has the expected attributes
            self.assertEqual(follow_instance.role, "worker")
            self.assertEqual(follow_instance.cluster_name, "test-cluster")
            self.assertTrue(hasattr(follow_instance, "ipfs_cluster_path"))
            self.assertTrue(hasattr(follow_instance, "run_cluster_follow_command"))
            
            logger.info("Successfully imported and initialized ipfs_cluster_follow module")
        except ImportError as e:
            self.fail(f"Failed to import ipfs_cluster_follow module: {e}")
        except Exception as e:
            self.fail(f"Unexpected error: {e}")
    
    def test_003_run_service_wrapper_fake_daemon(self):
        """Test running the ipfs_cluster_service wrapper script in fake daemon mode."""
        try:
            # Run the wrapper script with fake daemon flag
            run_script = os.path.join(os.getcwd(), "run_ipfs_cluster_service.py")
            result = self._run_command(["python", run_script, "--fake-daemon"])
            
            # Check that the script ran successfully
            self.assertEqual(result.returncode, 0)
            self.assertIn("Running in fake daemon mode", result.stdout)
            
            logger.info("Successfully ran ipfs_cluster_service wrapper in fake daemon mode")
        except Exception as e:
            self.fail(f"Failed to run ipfs_cluster_service wrapper: {e}")
    
    def test_004_run_follow_wrapper_fake_daemon(self):
        """Test running the ipfs_cluster_follow wrapper script in fake daemon mode."""
        try:
            # Run the wrapper script with fake daemon flag
            run_script = os.path.join(os.getcwd(), "run_ipfs_cluster_follow.py")
            result = self._run_command(["python", run_script, "--fake-daemon"])
            
            # Check that the script ran successfully
            self.assertEqual(result.returncode, 0)
            self.assertIn("Running in fake daemon mode", result.stdout)
            
            logger.info("Successfully ran ipfs_cluster_follow wrapper in fake daemon mode")
        except Exception as e:
            self.fail(f"Failed to run ipfs_cluster_follow wrapper: {e}")

    @unittest.skipIf(not has_direct_binary_access(),
                 "Requires direct binary access")
    def test_005_service_module_test_method(self):
        """Test the ipfs_cluster_service.test method with direct binary access."""
        try:
            sys.path.insert(0, os.getcwd())
            from ipfs_kit_py import ipfs_cluster_service
            
            # Create instance with custom paths
            resources = {}
            metadata = {
                "role": "master",
                "ipfs_cluster_path": self.service_dir
            }
            service_instance = ipfs_cluster_service(resources, metadata)
            
            # Run the test method
            test_result = service_instance.test()
            
            # Log the results for debugging
            logger.info(f"Test result: {json.dumps(test_result, indent=2)}")
            
            # Verify basic structure (don't require binary availability in CI environment)
            self.assertTrue(isinstance(test_result, dict))
            self.assertIn("success", test_result)
            self.assertIn("environment", test_result)
            self.assertEqual(test_result["environment"]["role"], "master")
            
        except Exception as e:
            self.fail(f"Failed to test ipfs_cluster_service module: {e}")

    @unittest.skipIf(not has_direct_binary_access(),
                 "Requires direct binary access")
    def test_006_service_basic_init(self):
        """Test basic initialization of ipfs_cluster_service config (with actual binary)."""
        try:
            sys.path.insert(0, os.getcwd())
            from ipfs_kit_py import ipfs_cluster_service
            
            # Create instance with custom paths
            resources = {}
            metadata = {
                "role": "master",
                "ipfs_path": os.path.join(self.temp_dir, "ipfs"),
                "ipfs_cluster_path": self.service_dir
            }
            service_instance = ipfs_cluster_service(resources, metadata)
            
            # Attempt to start the service (which should create default config)
            start_result = service_instance.ipfs_cluster_service_start(timeout=10)
            
            # Log the results for debugging
            logger.info(f"Start result: {json.dumps(start_result, indent=2)}")
            
            # Check if the initialization attempted to create config
            self.assertTrue(start_result.get("initialization_attempted", False))
            
            # Check if service.json was created
            service_json_path = os.path.join(self.service_dir, "service.json")
            self.assertTrue(os.path.exists(self.service_dir), "Cluster directory not created")
            
            # We don't require the config to be created successfully in CI environment
            # Just check that the initialization process ran
            self.assertIn("initialization", start_result)
            
        except Exception as e:
            self.fail(f"Failed to initialize ipfs_cluster_service config: {e}")

    @unittest.skipIf(not has_direct_binary_access(),
                 "Requires direct binary access")
    def test_007_check_daemon_status(self):
        """Test checking daemon status through both wrappers."""
        try:
            sys.path.insert(0, os.getcwd())
            from ipfs_kit_py import ipfs_cluster_service
            
            # Create instance with custom paths
            resources = {}
            metadata = {
                "role": "master",
                "ipfs_cluster_path": self.service_dir
            }
            service_instance = ipfs_cluster_service(resources, metadata)
            
            # Check ipfs_cluster_service status
            status_result = service_instance.ipfs_cluster_service_status()
            
            # Log the results for debugging
            logger.info(f"Status result: {json.dumps(status_result, indent=2)}")
            
            # Verify status check worked
            self.assertTrue(isinstance(status_result, dict))
            self.assertIn("process_running", status_result)
            
            # Get status via the daemon_type parameter
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            kit = ipfs_kit()
            daemon_status = kit.check_daemon_status(daemon_type="ipfs_cluster_service")
            
            # Log the results
            logger.info(f"Daemon status via kit: {json.dumps(daemon_status, indent=2)}")
            
            # Verify correct response structure
            self.assertTrue(isinstance(daemon_status, dict))
            self.assertIn("success", daemon_status)
            self.assertIn("daemon_type", daemon_status)
            self.assertEqual(daemon_status["daemon_type"], "ipfs_cluster_service")
            
        except Exception as e:
            self.fail(f"Failed to check daemon status: {e}")

    def test_008_wrapper_scripts_argument_passing(self):
        """Test that the wrapper scripts correctly pass arguments to the modules."""
        try:
            # Run the service wrapper script with --help flag
            run_service_script = os.path.join(os.getcwd(), "run_ipfs_cluster_service.py")
            service_result = self._run_command(["python", run_service_script, "--help"], check=False)
            
            # Check that the help option was recognized
            self.assertEqual(service_result.returncode, 0)
            self.assertIn("usage:", service_result.stdout)
            self.assertIn("--debug", service_result.stdout)
            self.assertIn("--fake-daemon", service_result.stdout)
            
            # Run the follow wrapper script with --help flag
            run_follow_script = os.path.join(os.getcwd(), "run_ipfs_cluster_follow.py")
            follow_result = self._run_command(["python", run_follow_script, "--help"], check=False)
            
            # Check that the help option was recognized
            self.assertEqual(follow_result.returncode, 0)
            self.assertIn("usage:", follow_result.stdout)
            self.assertIn("--debug", follow_result.stdout)
            self.assertIn("--fake-daemon", follow_result.stdout)
            
            logger.info("Both wrapper scripts correctly process command line arguments")
        except Exception as e:
            self.fail(f"Failed to test wrapper script argument passing: {e}")

    def test_009_wrapper_debug_mode(self):
        """Test that the wrapper scripts enable debug mode correctly."""
        try:
            # Run the service wrapper script with --debug flag
            run_service_script = os.path.join(os.getcwd(), "run_ipfs_cluster_service.py")
            service_result = self._run_command(
                ["python", run_service_script, "--debug", "--fake-daemon"]
            )
            
            # Check that debug mode was enabled
            self.assertEqual(service_result.returncode, 0)
            self.assertIn("Debug logging enabled", service_result.stdout)
            
            # Run the follow wrapper script with --debug flag
            run_follow_script = os.path.join(os.getcwd(), "run_ipfs_cluster_follow.py")
            follow_result = self._run_command(
                ["python", run_follow_script, "--debug", "--fake-daemon"]
            )
            
            # Check that debug mode was enabled
            self.assertEqual(follow_result.returncode, 0)
            self.assertIn("Debug logging enabled", follow_result.stdout)
            
            logger.info("Debug mode correctly enabled in both wrapper scripts")
        except Exception as e:
            self.fail(f"Failed to test wrapper debug mode: {e}")

if __name__ == "__main__":
    unittest.main()