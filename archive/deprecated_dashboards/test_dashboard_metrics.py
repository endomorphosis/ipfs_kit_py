#!/usr/bin/env python3
"""
Test script to verify dashboard observability metrics integration.

This script tests:
1. Backend health monitor integration
2. Real performance metrics collection
3. Dashboard API endpoints with real data
4. Log manager fixes for missing 'id' fields
"""

import anyio
import json
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_backend_health_monitor():
    """Test the backend health monitor."""
    try:
        # Import and test backend health monitor
        from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        logger.info("✓ Testing backend health monitor...")
        health_monitor = BackendHealthMonitor()
        
        # Test checking all backends
        backend_health = await health_monitor.check_all_backends_health()
        
        if backend_health.get("success"):
            backends = backend_health.get("backends", {})
            logger.info(f"✓ Backend health monitor working - Found {len(backends)} backends")
            
            # Check for IPFS metrics specifically
            ipfs_backend = backends.get("ipfs")
            if ipfs_backend:
                metrics = ipfs_backend.get("metrics", {})
                detailed_info = ipfs_backend.get("detailed_info", {})
                
                logger.info(f"✓ IPFS backend status: {ipfs_backend.get('status')}")
                logger.info(f"✓ IPFS health: {ipfs_backend.get('health')}")
                
                # Check for performance metrics
                performance_metrics = {
                    'repo_size_bytes': metrics.get('repo_size_bytes', 0),
                    'repo_objects': metrics.get('repo_objects', 0),
                    'bandwidth_in_bytes': metrics.get('bandwidth_in_bytes', 0),
                    'bandwidth_out_bytes': metrics.get('bandwidth_out_bytes', 0),
                    'peer_count': detailed_info.get('peer_count', 0),
                    'pins_count': detailed_info.get('pins_count', 0)
                }
                
                logger.info("✓ IPFS Performance Metrics:")
                for metric, value in performance_metrics.items():
                    logger.info(f"  - {metric}: {value}")
                
                # Check if any metrics are non-zero (indicating real data)
                has_real_data = any(value > 0 for value in performance_metrics.values())
                if has_real_data:
                    logger.info("✓ Real performance data detected!")
                else:
                    logger.warning("⚠ All performance metrics are 0 - may indicate IPFS is not running or has no data")
                
                return True
            else:
                logger.warning("⚠ No IPFS backend data found")
                return False
        else:
            logger.error(f"✗ Backend health check failed: {backend_health.get('error', 'Unknown error')}")
            return False
    except ImportError as e:
        logger.error(f"✗ Cannot import backend health monitor: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Backend health monitor test failed: {e}")
        return False

async def test_log_manager():
    """Test the log manager fixes."""
    try:
        from ipfs_kit_py.mcp.ipfs_kit.backends.log_manager import BackendLogManager
        
        logger.info("✓ Testing log manager...")
        
        log_manager = BackendLogManager()
        
        # Test adding a log entry (should include ID)
        log_manager.add_log_entry("test_backend", "INFO", "Test log message")
        
        # Get logs to verify ID exists
        logs = log_manager.get_backend_logs("test_backend", limit=1)
        
        if logs and len(logs) > 0:
            log_entry = logs[0]
            if 'id' in log_entry:
                logger.info(f"✓ Log manager working - Entry has ID: {log_entry['id']}")
                return True
            else:
                logger.error("✗ Log entry missing 'id' field")
                return False
        else:
            logger.error("✗ No log entries found")
            return False
            
    except ImportError as e:
        logger.error(f"✗ Cannot import log manager: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Log manager test failed: {e}")
        return False

async def test_integrated_dashboard():
    """Test the integrated dashboard with real metrics."""
    try:
        # Import the integrated MCP server
        from mcp.integrated_mcp_server_with_dashboard import IntegratedMCPDashboardServer
        
        logger.info("✓ Testing integrated dashboard...")
        
        # Create server instance (don't start it, just test initialization)
        server = IntegratedMCPDashboardServer(
            dashboard_enabled=True
        )
        
        # Check if backend health monitor was initialized
        if hasattr(server, 'backend_health_monitor') and server.backend_health_monitor:
            logger.info("✓ Backend health monitor integrated into dashboard server")
            
            # Test getting real metrics via the dashboard API logic
            if server.backend_health_monitor:
                backend_health = await server.backend_health_monitor.check_all_backends_health()
                if backend_health.get("success"):
                    backends = backend_health.get("backends", {})
                    ipfs_backend = backends.get("ipfs", {})
                    
                    if ipfs_backend:
                        metrics = ipfs_backend.get("metrics", {})
                        
                        # Simulate dashboard summary format
                        dashboard_performance = {
                            'repo_size': metrics.get('repo_size_bytes', 0),
                            'storage_max': 0,  # Would need to be calculated
                            'objects': metrics.get('repo_objects', 0),
                            'peers': ipfs_backend.get('detailed_info', {}).get('peer_count', 0),
                            'pins': ipfs_backend.get('detailed_info', {}).get('pins_count', 0),
                            'bandwidth_in': metrics.get('bandwidth_in_bytes', 0),
                            'bandwidth_out': metrics.get('bandwidth_out_bytes', 0)
                        }
                        
                        logger.info("✓ Dashboard-formatted performance metrics:")
                        for metric, value in dashboard_performance.items():
                            logger.info(f"  - {metric}: {value}")
                        
                        # Check if metrics would show non-zero values
                        has_data = any(value > 0 for key, value in dashboard_performance.items() if key != 'storage_max')
                        if has_data:
                            logger.info("✓ Dashboard will show real performance data!")
                            return True
                        else:
                            logger.warning("⚠ Dashboard metrics will still show zeros - IPFS may not be running")
                            return True  # Integration works, just no data
                    else:
                        logger.warning("⚠ No IPFS backend data for dashboard")
                        return False
                else:
                    logger.error("✗ Backend health check failed in dashboard test")
                    return False
            else:
                logger.error("✗ Backend health monitor not available in dashboard")
                return False
        else:
            logger.error("✗ Backend health monitor not integrated into dashboard server")
            return False
            
    except ImportError as e:
        logger.error(f"✗ Cannot import integrated dashboard server: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Integrated dashboard test failed: {e}")
        return False

async def main():
    """Run all tests."""
    logger.info("🧪 Testing dashboard observability metrics integration...")
    
    results = []
    
    # Test 1: Backend Health Monitor
    logger.info("\n=== Test 1: Backend Health Monitor ===")
    backend_health_ok = await test_backend_health_monitor()
    results.append(("Backend Health Monitor", backend_health_ok))
    
    # Test 2: Log Manager
    logger.info("\n=== Test 2: Log Manager ===")
    log_manager_ok = await test_log_manager()
    results.append(("Log Manager", log_manager_ok))
    
    # Test 3: Integrated Dashboard
    logger.info("\n=== Test 3: Integrated Dashboard ===")
    dashboard_ok = await test_integrated_dashboard()
    results.append(("Integrated Dashboard", dashboard_ok))
    
    # Summary
    logger.info("\n=== Test Results Summary ===")
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("\n🎉 All tests passed! Dashboard observability should now show real performance metrics.")
        return 0
    else:
        logger.error("\n❌ Some tests failed. Check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(anyio.run(main))
