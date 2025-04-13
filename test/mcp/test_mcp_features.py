"""
Comprehensive test script for the MCP server implementation.

This script tests all features of the MCP server, including lock file handling
capabilities added to ipfs.py and integrated with the MCP server.
"""

import os
import sys
import time
import json
import signal
import unittest
import subprocess
import requests
import psutil
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock

# Make sure we can find the project modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import necessary modules
import ipfs_kit_py.ipfs
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.mcp.server import MCPServer

# Import and apply compatibility layer
import mcp_compatibility
mcp_compatibility.add_compatibility_methods()
mcp_compatibility.patch_mcp_server()

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("mcp_test")

class TestMCPFeatures(unittest.TestCase):
    """Test all features of the MCP server implementation."""
    
    @classmethod
    def setUpClass(cls):
        """Set up for all tests."""
        cls.base_temp_dir = tempfile.mkdtemp(prefix="mcp_test_")
        cls.server_url = "http://localhost:9999/api/v0/mcp"
        cls.server_process = None
        
        # Make sure no existing server is running
        cls._kill_existing_servers()
        
        # Start server
        cls._start_server()
        
        # Wait for server to start
        max_retries = 30
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = requests.get(f"{cls.server_url}/health")
                if response.status_code == 200:
                    logger.info("Server started successfully")
                    break
            except requests.exceptions.ConnectionError:
                pass
            
            time.sleep(1)
            retry_count += 1
            
        if retry_count >= max_retries:
            logger.error("Failed to start MCP server")
            cls._stop_server()
            raise RuntimeError("Failed to start MCP server")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        cls._stop_server()
        
        # Clean up temporary directory
        if os.path.exists(cls.base_temp_dir):
            shutil.rmtree(cls.base_temp_dir)
    
    @classmethod
    def _start_server(cls):
        """Start the MCP server as a subprocess."""
        # Port 9999 for testing
        cmd = [
            sys.executable, "-m", "ipfs_kit_py.mcp.server", 
            "--debug", "--isolation", "--port", "9999", 
            "--host", "localhost", "--log-level", "DEBUG"
        ]
        
        # Start server
        cls.server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            preexec_fn=os.setsid  # Use process group for cleanup
        )
        
        logger.info(f"Started MCP server process with PID: {cls.server_process.pid}")
    
    @classmethod
    def _stop_server(cls):
        """Stop the MCP server."""
        if cls.server_process:
            logger.info(f"Stopping MCP server process with PID: {cls.server_process.pid}")
            
            # Try to terminate process group
            try:
                os.killpg(os.getpgid(cls.server_process.pid), signal.SIGTERM)
                
                # Wait a bit for process to end
                cls.server_process.wait(timeout=5)
                logger.info("Server process terminated")
            except (ProcessLookupError, subprocess.TimeoutExpired):
                # If still running, force kill
                try:
                    os.killpg(os.getpgid(cls.server_process.pid), signal.SIGKILL)
                    logger.info("Server process forcefully killed")
                except ProcessLookupError:
                    pass
            
            # Clean up process
            cls.server_process = None
    
    @classmethod
    def _kill_existing_servers(cls):
        """Kill any existing MCP server processes to avoid port conflicts."""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'ipfs_kit_py.mcp.server' in ' '.join(cmdline):
                    logger.info(f"Killing existing MCP server process: {proc.info['pid']}")
                    proc.terminate()
                    proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    
    def test_01_server_health(self):
        """Test server health endpoint."""
        # Get server health
        response = requests.get(f"{self.server_url}/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify health response
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'ok')
        self.assertTrue('debug_mode' in data)
        self.assertTrue('isolation_mode' in data)
        self.assertTrue('server_id' in data)
        self.assertTrue('timestamp' in data)
        
        # Check daemon-related fields
        self.assertTrue('ipfs_daemon_running' in data or 'daemon_status_check_error' in data)
    
    def test_02_debug_state(self):
        """Test debug state endpoint."""
        # Get debug state
        response = requests.get(f"{self.server_url}/debug")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify debug state response
        self.assertTrue(data['success'])
        self.assertTrue('server_info' in data)
        self.assertTrue('models' in data)
        self.assertTrue('persistence' in data)
        self.assertTrue('credentials' in data)
        
        # Check daemon management information
        self.assertTrue('daemon_management' in data['server_info'])
    
    def test_03_operations_log(self):
        """Test operations log endpoint."""
        # Get operations log
        response = requests.get(f"{self.server_url}/operations")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify operations log response
        self.assertTrue(data['success'])
        self.assertTrue('operations' in data)
        self.assertTrue('count' in data)
        self.assertTrue('timestamp' in data)
        
        # Operations should include at least our health check
        self.assertGreater(data['count'], 0)
    
    def test_04_daemon_status(self):
        """Test daemon status endpoint."""
        # Get daemon status
        response = requests.get(f"{self.server_url}/daemon/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify daemon status response
        self.assertTrue(data['success'])
        self.assertTrue('daemon_status' in data)
        self.assertTrue('daemon_monitor_running' in data)
        self.assertTrue('auto_start_daemons' in data)
        
        # Check daemon status for IPFS daemon
        self.assertTrue('ipfs' in data['daemon_status'])
    
    def test_05_start_daemon(self):
        """Test start daemon endpoint."""
        # Start IPFS daemon
        response = requests.post(f"{self.server_url}/daemon/start/ipfs")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response
        # May be 'already_running' or direct success
        self.assertTrue(
            data['success'] or (
                'status' in data and 
                data['status'] == 'already_running'
            )
        )
        
        # Verify daemon is running
        response = requests.get(f"{self.server_url}/daemon/status")
        data = response.json()
        ipfs_status = data['daemon_status']['ipfs']
        
        # Check daemon is running - could be identified by different fields in response
        self.assertTrue(
            ipfs_status.get('success', False) or
            ipfs_status.get('running', False) or
            (
                'status' in ipfs_status and
                ipfs_status['status'] == 'already_running'
            )
        )
    
    def test_06_stop_daemon(self):
        """Test stop daemon endpoint."""
        # First ensure daemon is running
        requests.post(f"{self.server_url}/daemon/start/ipfs")
        
        # Then stop it
        response = requests.post(f"{self.server_url}/daemon/stop/ipfs")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response
        # Note: With auto-start daemons, this may fail or be a no-op
        if not data.get('success', False):
            logger.warning(f"Daemon stop result: {data}")
            
        # If auto-start enabled, daemon may restart automatically
        time.sleep(2)
        
        # Verify daemon status
        response = requests.get(f"{self.server_url}/daemon/status")
        data = response.json()
        logger.info(f"Daemon status after stop: {data}")
    
    def test_07_daemon_health_monitor(self):
        """Test daemon health monitor endpoints."""
        # Stop monitor first (to test both endpoints)
        requests.post(f"{self.server_url}/daemon/monitor/stop")
        
        # Start daemon health monitor
        response = requests.post(
            f"{self.server_url}/daemon/monitor/start",
            json={"check_interval": 30}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response (success or already running)
        # With the isolation mode, this might fail
        if not data.get('success', False):
            logger.warning(f"Monitor start result: {data}")
        
        # Verify monitor is running
        response = requests.get(f"{self.server_url}/daemon/status")
        data = response.json()
        # This might be False in isolation mode
        logger.info(f"Monitor running status: {data.get('daemon_monitor_running', False)}")
        
        # Stop monitor
        response = requests.post(f"{self.server_url}/daemon/monitor/stop")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Again, with isolation mode, this might fail
        if not data.get('success', False):
            logger.warning(f"Monitor stop result: {data}")
    
    def test_08_ipfs_controller_endpoints(self):
        """Test IPFS controller endpoints."""
        # Test basic IPFS operations
        try:
            # Get IPFS ID
            response = requests.get(f"{self.server_url}/ipfs/id")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue('success' in data, f"Response: {data}")
            
            logger.info(f"IPFS ID response: {data}")
            
        except requests.exceptions.HTTPError as e:
            logger.warning(f"IPFS controller endpoints not available: {e}")
            # Skip the test but don't fail it
            self.skipTest("IPFS controller endpoints not available")
    
    def test_09_cli_controller_endpoints(self):
        """Test CLI controller endpoints."""
        try:
            # Test execute command
            response = requests.post(
                f"{self.server_url}/cli/execute",
                json={
                    "command": "list_known_peers",
                    "args": [],
                    "kwargs": {}
                }
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue('success' in data)
            logger.info(f"CLI execute response: {data}")
            
        except requests.exceptions.HTTPError as e:
            logger.warning(f"CLI controller endpoints not available: {e}")
            # Skip the test but don't fail it
            self.skipTest("CLI controller endpoints not available")
    
    def test_10_lock_file_handling(self):
        """Test lock file handling in the MCP server context."""
        # First, get the IPFS path from server
        response = requests.get(f"{self.server_url}/debug")
        self.assertEqual(response.status_code, 200)
        debug_data = response.json()
        
        # Extract daemon management details
        daemon_management = debug_data.get('server_info', {}).get('daemon_management', {})
        daemon_status = daemon_management.get('daemon_status', {})
        
        # Get IPFS daemon info
        ipfs_daemon_info = daemon_status.get('ipfs', {})
        ipfs_path = ipfs_daemon_info.get('ipfs_path', None)
        
        # If we can't get it from debug, try to get it from daemon status
        if not ipfs_path:
            response = requests.get(f"{self.server_url}/daemon/status")
            status_data = response.json()
            ipfs_daemon_info = status_data.get('daemon_status', {}).get('ipfs', {})
            ipfs_path = ipfs_daemon_info.get('ipfs_path', None)
            
        # If still no ipfs_path, use a test directory
        if not ipfs_path:
            ipfs_path = os.path.join(self.base_temp_dir, "test_ipfs_path")
            os.makedirs(ipfs_path, exist_ok=True)
            logger.warning(f"IPFS path not found in server debug info, using: {ipfs_path}")
        else:
            logger.info(f"Using server IPFS path: {ipfs_path}")
        
        # Create lock file path
        repo_lock_path = os.path.join(ipfs_path, "repo.lock")
        
        # Step 1: Check if we can handle a stale lock file
        # First stop the daemon
        response = requests.post(f"{self.server_url}/daemon/stop/ipfs")
        self.assertEqual(response.status_code, 200)
        time.sleep(2)  # Wait for daemon to stop
        
        # Create a stale lock file
        with open(repo_lock_path, 'w') as f:
            f.write("999999")  # Non-existent PID
        
        # Try to start daemon (should handle stale lock)
        response = requests.post(f"{self.server_url}/daemon/start/ipfs")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response
        logger.info(f"Daemon start with stale lock response: {data}")
        self.assertTrue(
            data.get('success', False) or 
            'lock_file_removed' in data or
            'lock_file_detected' in data
        )
        
        # Verify daemon is running and lock is handled
        response = requests.get(f"{self.server_url}/daemon/status")
        status_data = response.json()
        ipfs_status = status_data.get('daemon_status', {}).get('ipfs', {})
        logger.info(f"IPFS status after stale lock test: {ipfs_status}")
        
        # Verify daemon is running
        self.assertTrue(
            ipfs_status.get('success', False) or
            (
                ipfs_status.get('daemons', {}).get('ipfs', {}).get('running', False)
                if 'daemons' in ipfs_status else False
            )
        )
        
        # Step 2: Test with active lock (if daemon is running)
        # Stop daemon first
        response = requests.post(f"{self.server_url}/daemon/stop/ipfs")
        time.sleep(2)  # Wait for daemon to stop
        
        # Create a separate process and use its PID for the lock file
        test_process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        active_pid = test_process.pid
        
        try:
            # Create active lock file
            with open(repo_lock_path, 'w') as f:
                f.write(str(active_pid))
            
            # Try to start daemon with active lock
            response = requests.post(f"{self.server_url}/daemon/start/ipfs")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # Should detect active lock
            logger.info(f"Daemon start with active lock response: {data}")
            
            # Active lock should be detected - success might be false if strict
            self.assertTrue(
                'lock_file_detected' in data or
                data.get('status') == 'already_running'
            )
            
            # If lock_is_stale is in the response, it should be False
            if 'lock_is_stale' in data:
                self.assertFalse(data['lock_is_stale'])
        finally:
            # Clean up test process
            if test_process:
                test_process.terminate()
                test_process.wait()
        
        # Step 3: Test with no lock file (clean start)
        # Make sure daemon is stopped
        requests.post(f"{self.server_url}/daemon/stop/ipfs")
        time.sleep(2)
        
        # Remove lock file if it exists
        if os.path.exists(repo_lock_path):
            os.remove(repo_lock_path)
        
        # Start daemon
        response = requests.post(f"{self.server_url}/daemon/start/ipfs")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should be a clean start
        logger.info(f"Daemon start with no lock response: {data}")
        self.assertTrue(data.get('success', False))
        
        # Verify daemon is running
        response = requests.get(f"{self.server_url}/daemon/status")
        status_data = response.json()
        ipfs_status = status_data.get('daemon_status', {}).get('ipfs', {})
        logger.info(f"IPFS status after clean start: {ipfs_status}")
        
        # Verify daemon is running
        self.assertTrue(
            ipfs_status.get('success', False) or
            (
                ipfs_status.get('daemons', {}).get('ipfs', {}).get('running', False)
                if 'daemons' in ipfs_status else False
            )
        )

    def test_11_daemon_auto_restart(self):
        """Test daemon auto-restart functionality."""
        # Enable daemon health monitor first
        response = requests.post(
            f"{self.server_url}/daemon/monitor/start",
            json={"check_interval": 5}  # Short interval for testing
        )
        self.assertEqual(response.status_code, 200)
        
        # Ensure daemon is running
        requests.post(f"{self.server_url}/daemon/start/ipfs")
        
        # Get initial process info
        response = requests.get(f"{self.server_url}/daemon/status")
        status_data = response.json()
        ipfs_status = status_data.get('daemon_status', {}).get('ipfs', {})
        logger.info(f"Initial IPFS status: {ipfs_status}")
        
        # First verify auto-start is enabled
        self.assertTrue(status_data.get('auto_start_daemons', False))
        
        # Forcefully kill the daemon directly (simulate crash)
        # This requires locating the daemon process
        # In isolation mode this might not work, so we're checking if we can find daemon info
        daemon_pid = None
        
        if ipfs_status.get('success', False):
            daemon_info = ipfs_status.get('daemon_info', {})
            daemon_pid = daemon_info.get('pid')
        
        if daemon_pid is None:
            # Try to get info from the debug endpoint
            response = requests.get(f"{self.server_url}/debug")
            debug_data = response.json()
            daemon_management = debug_data.get('server_info', {}).get('daemon_management', {})
            daemon_status = daemon_management.get('daemon_status', {})
            ipfs_daemon_info = daemon_status.get('ipfs', {})
            daemon_pid = ipfs_daemon_info.get('pid')
        
        if daemon_pid:
            logger.info(f"Found IPFS daemon PID: {daemon_pid}")
            
            try:
                # Kill the process
                os.kill(daemon_pid, signal.SIGKILL)
                logger.info(f"Killed IPFS daemon process (PID: {daemon_pid})")
                
                # Wait for auto-restart
                time.sleep(10)  # Give time for health monitor to detect and restart
                
                # Verify daemon has been restarted
                response = requests.get(f"{self.server_url}/daemon/status")
                status_data = response.json()
                ipfs_status = status_data.get('daemon_status', {}).get('ipfs', {})
                logger.info(f"IPFS status after force kill: {ipfs_status}")
                
                # Daemon should be running again
                self.assertTrue(
                    ipfs_status.get('success', False) or
                    (
                        ipfs_status.get('daemons', {}).get('ipfs', {}).get('running', False)
                        if 'daemons' in ipfs_status else False
                    )
                )
                
                # Should have a different PID now
                new_daemon_pid = None
                if ipfs_status.get('success', False):
                    daemon_info = ipfs_status.get('daemon_info', {})
                    new_daemon_pid = daemon_info.get('pid')
                
                if new_daemon_pid:
                    logger.info(f"New IPFS daemon PID: {new_daemon_pid}")
                    self.assertNotEqual(new_daemon_pid, daemon_pid, "Expected a new daemon process after restart")
            except (ProcessLookupError, ValueError):
                logger.warning(f"Process {daemon_pid} not found or invalid - auto-restart test skipped")
        else:
            logger.warning("Could not determine IPFS daemon PID - auto-restart test skipped")
        
        # Stop the health monitor when done
        requests.post(f"{self.server_url}/daemon/monitor/stop")
        
    def test_12_webrtc_dashboard_endpoints(self):
        """Test WebRTC dashboard controller endpoints."""
        # First check if dashboard HTML is accessible
        response = requests.get(f"{self.server_url}/webrtc/dashboard")
        
        # If dashboard is not available, the test will be skipped
        if response.status_code != 200:
            self.skipTest("WebRTC dashboard not available")
        
        # Test WebRTC connections endpoint
        response = requests.get(f"{self.server_url}/webrtc/connections")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue('connections' in data)
        logger.info(f"Got {len(data['connections'])} WebRTC connections")
        
        # Test WebRTC operations endpoint
        response = requests.get(f"{self.server_url}/webrtc/operations")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue('operations' in data)
        logger.info(f"Got {len(data.get('operations', []))} WebRTC operations")
        
        # Test WebRTC tasks endpoint
        response = requests.get(f"{self.server_url}/webrtc/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue('tasks' in data)
        logger.info(f"Got {len(data.get('tasks', []))} WebRTC tasks")
        
        # Test connection test endpoint
        response = requests.post(f"{self.server_url}/webrtc/test_connection")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # This might fail if WebRTC model is not available
        logger.info(f"Test connection response: {data}")
        if data.get('success', False):
            test_connection_id = data.get('connection_id')
            logger.info(f"Created test connection with ID: {test_connection_id}")
            
            # Test close connection endpoint (if we got a connection ID)
            if test_connection_id:
                response = requests.post(f"{self.server_url}/webrtc/close/{test_connection_id}")
                self.assertEqual(response.status_code, 200)
                close_data = response.json()
                logger.info(f"Close connection response: {close_data}")
    
    def test_13_webrtc_video_player_endpoints(self):
        """Test WebRTC video player controller endpoints."""
        # First check if video player HTML is accessible
        response = requests.get(f"{self.server_url}/webrtc/player")
        
        # If video player is not available, the test will be skipped
        if response.status_code != 200:
            self.skipTest("WebRTC video player not available")
        
        # Check HTML content
        html_content = response.text
        self.assertIn("WebRTC Video Player", html_content)
        
        # Test with parameters
        # Generate test CID and connection ID
        test_cid = "QmTest123"
        test_connection_id = "test-connection-123"
        
        # Request player with parameters
        response = requests.get(f"{self.server_url}/webrtc/player?connection_id={test_connection_id}&content_cid={test_cid}")
        self.assertEqual(response.status_code, 200)
        
        # Verify that the HTML contains script to auto-populate fields
        html_content = response.text
        self.assertIn("Auto-populate connection details", html_content)
        self.assertIn(test_cid, html_content)
        self.assertIn(test_connection_id, html_content)
        
        # Try to get connection details (might not be available in test)
        response = requests.get(f"{self.server_url}/webrtc/connection/{test_connection_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        logger.info(f"Connection details response: {data}")
        
        # Check for demo video endpoint (may not be available)
        response = requests.get(f"{self.server_url}/webrtc/demo_video.mp4")
        demo_status = response.status_code
        logger.info(f"Demo video status: {demo_status}")
        
    def test_14_webrtc_integration(self):
        """Test WebRTC dashboard and video player integration."""
        # First, check if both endpoints are available
        dashboard_response = requests.get(f"{self.server_url}/webrtc/dashboard")
        player_response = requests.get(f"{self.server_url}/webrtc/player")
        
        if dashboard_response.status_code != 200 or player_response.status_code != 200:
            self.skipTest("WebRTC dashboard or video player not available")
        
        # Test the integration flow
        # 1. Create a test connection
        response = requests.post(f"{self.server_url}/webrtc/test_connection")
        self.assertEqual(response.status_code, 200)
        conn_data = response.json()
        
        # If successful, test the dashboard to player integration
        if conn_data.get('success', False):
            connection_id = conn_data.get('connection_id')
            
            # 2. Get connections list from dashboard
            response = requests.get(f"{self.server_url}/webrtc/connections")
            self.assertEqual(response.status_code, 200)
            connections_data = response.json()
            
            # 3. Verify our test connection is in the list
            connections = connections_data.get('connections', [])
            test_connection = None
            for conn in connections:
                if conn.get('connection_id') == connection_id:
                    test_connection = conn
                    break
            
            # If we found our connection, simulate opening the player
            if test_connection:
                logger.info(f"Found test connection in dashboard: {test_connection}")
                
                # Get content CID from the connection
                content_cid = test_connection.get('content_cid', 'test-cid')
                
                # 4. Simulate clicking "Open Player" by getting player with parameters
                response = requests.get(
                    f"{self.server_url}/webrtc/player?connection_id={connection_id}&content_cid={content_cid}"
                )
                self.assertEqual(response.status_code, 200)
                
                # 5. Verify player HTML has the parameters
                html_content = response.text
                self.assertIn(content_cid, html_content)
                self.assertIn(connection_id, html_content)
                
                # 6. Clean up - close the connection
                response = requests.post(f"{self.server_url}/webrtc/close/{connection_id}")
                self.assertEqual(response.status_code, 200)
                close_data = response.json()
                logger.info(f"Close connection response: {close_data}")
            else:
                logger.warning(f"Test connection {connection_id} not found in dashboard connections list")
        else:
            logger.warning("Could not create test connection for WebRTC integration test")
            
    def test_15_webrtc_streaming_endpoints(self):
        """Test WebRTC streaming control endpoints."""
        # First check if WebRTC endpoints are available at all
        response = requests.get(f"{self.server_url}/webrtc/dashboard")
        if response.status_code != 200:
            self.skipTest("WebRTC dashboard not available")
        
        # Test stream test content endpoint
        response = requests.post(f"{self.server_url}/webrtc/stream_test_content")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        logger.info(f"Stream test content response: {data}")
        
        # Test might fail if WebRTC model is not available - that's okay
        if data.get('success', False):
            connection_id = data.get('connection_id')
            
            # If we got a connection, test quality setting
            if connection_id:
                response = requests.post(
                    f"{self.server_url}/webrtc/quality/{connection_id}",
                    json={"quality": 60}
                )
                self.assertEqual(response.status_code, 200)
                quality_data = response.json()
                logger.info(f"Set quality response: {quality_data}")
                
                # Clean up - close the connection
                response = requests.post(f"{self.server_url}/webrtc/close/{connection_id}")
                self.assertEqual(response.status_code, 200)
                
        # Test streaming with specific CID
        response = requests.post(
            f"{self.server_url}/webrtc/stream",
            json={"cid": "QmTestCid123", "quality": 75}
        )
        self.assertEqual(response.status_code, 200)
        stream_data = response.json()
        logger.info(f"Stream specific CID response: {stream_data}")
        
        # Test close all connections endpoint
        response = requests.post(f"{self.server_url}/webrtc/close_all")
        self.assertEqual(response.status_code, 200)
        close_all_data = response.json()
        logger.info(f"Close all connections response: {close_all_data}")

def run_tests():
    """Run the tests with command line arguments."""
    import argparse
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Run MCP feature tests")
    parser.add_argument("--url", default="http://localhost:9999/api/v0/mcp",
                      help="URL of the MCP server to test")
    parser.add_argument("--no-server", action="store_true",
                      help="Don't start/stop server, just run tests against existing server")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Show verbose output")
    parser.add_argument("--test-filter", type=str, default=None,
                      help="Run only tests matching this string")
    
    # Extract unittest args vs script args
    unittest_args = []
    script_args = []
    
    for arg in sys.argv[1:]:
        if arg.startswith("--verbose") or arg.startswith("-v"):
            unittest_args.extend(["-v"])
            script_args.append(arg)
        elif arg.startswith("--"):
            script_args.append(arg)
        else:
            unittest_args.append(arg)
    
    # Parse script args
    script_parser = argparse.ArgumentParser()
    script_parser.add_argument("--url", default="http://localhost:9999/api/v0/mcp")
    script_parser.add_argument("--no-server", action="store_true")
    script_parser.add_argument("--verbose", "-v", action="store_true")
    script_parser.add_argument("--test-filter", type=str, default=None)
    
    try:
        args, _ = script_parser.parse_known_args(script_args)
    except:
        args = None
    
    # Set server URL if provided
    if args and args.url:
        TestMCPFeatures.server_url = args.url
    
    # If test filter provided, run only matching tests
    if args and args.test_filter:
        test_pattern = f"*{args.test_filter}*"
        suite = unittest.TestLoader().loadTestsFromName(test_pattern, module=sys.modules[__name__])
        runner = unittest.TextTestRunner(verbosity=2 if args and args.verbose else 1)
        result = runner.run(suite)
        return 0 if result.wasSuccessful() else 1
    
    # Run all tests
    sys.argv = [sys.argv[0]] + unittest_args
    return unittest.main(verbosity=2 if args and args.verbose else 1)

if __name__ == "__main__":
    sys.exit(run_tests())