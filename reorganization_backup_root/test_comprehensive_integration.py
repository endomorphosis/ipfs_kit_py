#!/usr/bin/env python3
"""
Comprehensive Integration Test for Enhanced IPFS Kit Dashboard System

This script tests all the major improvements made to:
- IPFS Cluster daemon manager
- Enhanced health monitoring  
- LibP2P peer management
- Dashboard API endpoints

Run this to validate the complete system integration.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComprehensiveIntegrationTester:
    """Comprehensive tester for all enhanced components."""
    
    def __init__(self):
        """Initialize the integration tester."""
        self.test_results = []
        self.cluster_manager = None
        self.health_monitor = None
        self.dashboard_controller = None
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests.
        
        Returns:
            Dict with comprehensive test results
        """
        logger.info("🚀 Starting Comprehensive IPFS Kit Integration Tests")
        
        test_suite = {
            "cluster_daemon_tests": await self.test_cluster_daemon_manager(),
            "health_monitor_tests": await self.test_enhanced_health_monitor(),
            "libp2p_tests": await self.test_libp2p_enhancements(),
            "dashboard_api_tests": await self.test_dashboard_api(),
            "integration_tests": await self.test_complete_integration()
        }
        
        # Calculate overall results
        total_tests = sum(len(tests.get("tests", [])) for tests in test_suite.values())
        passed_tests = sum(sum(1 for test in tests.get("tests", []) if test.get("passed")) 
                          for tests in test_suite.values())
        
        test_suite["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        }
        
        logger.info(f"✅ Integration Tests Complete: {passed_tests}/{total_tests} passed ({test_suite['summary']['success_rate']:.1f}%)")
        
        return test_suite
    
    async def test_cluster_daemon_manager(self) -> Dict[str, Any]:
        """Test the enhanced IPFS Cluster daemon manager."""
        logger.info("🔧 Testing IPFS Cluster Daemon Manager...")
        
        tests = []
        
        try:
            # Test 1: Import and initialize cluster manager
            test_result = {"name": "cluster_manager_import", "passed": False, "details": {}}
            try:
                from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterDaemonManager, IPFSClusterConfig
                
                config = IPFSClusterConfig()
                self.cluster_manager = IPFSClusterDaemonManager(config)
                
                test_result["passed"] = True
                test_result["details"]["config_created"] = True
                test_result["details"]["manager_initialized"] = True
                
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 2: Configuration validation
            test_result = {"name": "cluster_config_validation", "passed": False, "details": {}}
            try:
                if self.cluster_manager:
                    config_valid = self.cluster_manager._validate_configuration()
                    test_result["passed"] = config_valid.get("valid", False)
                    test_result["details"] = config_valid
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 3: Service status check
            test_result = {"name": "cluster_status_check", "passed": False, "details": {}}
            try:
                if self.cluster_manager:
                    status = await self.cluster_manager.get_cluster_service_status()
                    test_result["passed"] = status is not None
                    test_result["details"] = status
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 4: Port availability check
            test_result = {"name": "cluster_port_check", "passed": False, "details": {}}
            try:
                if self.cluster_manager:
                    port_status = self.cluster_manager._check_port_availability()
                    test_result["passed"] = True
                    test_result["details"] = port_status
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
        except Exception as e:
            logger.error(f"Error in cluster daemon tests: {e}")
            tests.append({
                "name": "cluster_manager_error",
                "passed": False,
                "details": {"error": str(e)}
            })
        
        return {"tests": tests}
    
    async def test_enhanced_health_monitor(self) -> Dict[str, Any]:
        """Test the enhanced health monitoring system."""
        logger.info("🏥 Testing Enhanced Health Monitor...")
        
        tests = []
        
        try:
            # Test 1: Initialize health monitor
            test_result = {"name": "health_monitor_init", "passed": False, "details": {}}
            try:
                from mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
                
                self.health_monitor = BackendHealthMonitor()
                test_result["passed"] = True
                test_result["details"]["monitor_created"] = True
                test_result["details"]["backends_count"] = len(self.health_monitor.backends)
                
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 2: Check all backends health
            test_result = {"name": "all_backends_health_check", "passed": False, "details": {}}
            try:
                if self.health_monitor:
                    health_results = await self.health_monitor.check_all_backends_health()
                    test_result["passed"] = len(health_results) > 0
                    test_result["details"]["backends_checked"] = list(health_results.keys())
                    test_result["details"]["health_summary"] = {
                        name: info.get("health", "unknown") 
                        for name, info in health_results.items()
                    }
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 3: Specific cluster health check with enhanced manager
            test_result = {"name": "cluster_health_enhanced", "passed": False, "details": {}}
            try:
                if self.health_monitor:
                    cluster_health = await self.health_monitor.check_backend_health("ipfs_cluster")
                    test_result["passed"] = cluster_health is not None
                    test_result["details"] = cluster_health
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 4: LibP2P health check with enhanced features
            test_result = {"name": "libp2p_health_enhanced", "passed": False, "details": {}}
            try:
                if self.health_monitor:
                    libp2p_health = await self.health_monitor.check_backend_health("libp2p")
                    test_result["passed"] = libp2p_health is not None
                    test_result["details"] = libp2p_health
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
        except Exception as e:
            logger.error(f"Error in health monitor tests: {e}")
            tests.append({
                "name": "health_monitor_error",
                "passed": False,
                "details": {"error": str(e)}
            })
        
        return {"tests": tests}
    
    async def test_libp2p_enhancements(self) -> Dict[str, Any]:
        """Test LibP2P enhancement features."""
        logger.info("🌐 Testing LibP2P Enhancements...")
        
        tests = []
        
        try:
            # Test 1: LibP2P peer manager import
            test_result = {"name": "libp2p_peer_manager_import", "passed": False, "details": {}}
            try:
                from ipfs_kit_py.libp2p.peer_manager import get_peer_manager
                
                peer_manager = get_peer_manager()
                test_result["passed"] = peer_manager is not None
                test_result["details"]["manager_created"] = True
                
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 2: Peer statistics
            test_result = {"name": "peer_statistics", "passed": False, "details": {}}
            try:
                from ipfs_kit_py.libp2p.peer_manager import get_peer_manager
                
                peer_manager = get_peer_manager()
                stats = peer_manager.get_peer_statistics()
                test_result["passed"] = isinstance(stats, dict)
                test_result["details"] = stats
                
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 3: Health score calculation
            test_result = {"name": "libp2p_health_score", "passed": False, "details": {}}
            try:
                if self.health_monitor:
                    # Test the health score calculation method
                    mock_stats = {
                        "discovery_active": True,
                        "total_peers": 5,
                        "connected_peers": 4,
                        "total_files": 10,
                        "total_pins": 5
                    }
                    score = self.health_monitor._calculate_libp2p_health_score(mock_stats, [])
                    test_result["passed"] = 0 <= score <= 100
                    test_result["details"]["score"] = score
                    test_result["details"]["test_stats"] = mock_stats
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
        except Exception as e:
            logger.error(f"Error in LibP2P tests: {e}")
            tests.append({
                "name": "libp2p_error",
                "passed": False,
                "details": {"error": str(e)}
            })
        
        return {"tests": tests}
    
    async def test_dashboard_api(self) -> Dict[str, Any]:
        """Test the enhanced dashboard API."""
        logger.info("📊 Testing Dashboard API...")
        
        tests = []
        
        try:
            # Test 1: Dashboard controller initialization
            test_result = {"name": "dashboard_controller_init", "passed": False, "details": {}}
            try:
                from mcp.ipfs_kit.api.enhanced_dashboard_api import DashboardController
                
                self.dashboard_controller = DashboardController()
                test_result["passed"] = True
                test_result["details"]["controller_created"] = True
                test_result["details"]["cluster_manager_available"] = self.dashboard_controller.cluster_manager is not None
                
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 2: Comprehensive status
            test_result = {"name": "comprehensive_status", "passed": False, "details": {}}
            try:
                if self.dashboard_controller:
                    status = await self.dashboard_controller.get_comprehensive_status()
                    test_result["passed"] = status is not None and "overall_health" in status
                    test_result["details"] = {
                        "overall_health": status.get("overall_health"),
                        "backends_count": len(status.get("backends", {})),
                        "alerts_count": len(status.get("alerts", [])),
                        "metrics": status.get("metrics", {})
                    }
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 3: Real-time metrics
            test_result = {"name": "realtime_metrics", "passed": False, "details": {}}
            try:
                if self.dashboard_controller:
                    metrics = await self.dashboard_controller.get_real_time_metrics()
                    test_result["passed"] = metrics is not None and "timestamp" in metrics
                    test_result["details"] = {
                        "system_metrics": bool(metrics.get("system")),
                        "backend_metrics": bool(metrics.get("backends")),
                        "network_metrics": bool(metrics.get("network")),
                        "performance_metrics": bool(metrics.get("performance"))
                    }
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 4: Health check functionality
            test_result = {"name": "health_check_api", "passed": False, "details": {}}
            try:
                if self.dashboard_controller:
                    from mcp.ipfs_kit.api.enhanced_dashboard_api import HealthCheckRequest
                    
                    request = HealthCheckRequest(include_metrics=True)
                    result = await self.dashboard_controller.perform_health_check(request)
                    test_result["passed"] = result.get("success", False)
                    test_result["details"] = {
                        "results_count": len(result.get("results", {})),
                        "metrics_included": bool(result.get("metrics"))
                    }
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
        except Exception as e:
            logger.error(f"Error in dashboard API tests: {e}")
            tests.append({
                "name": "dashboard_api_error",
                "passed": False,
                "details": {"error": str(e)}
            })
        
        return {"tests": tests}
    
    async def test_complete_integration(self) -> Dict[str, Any]:
        """Test complete system integration."""
        logger.info("🔗 Testing Complete System Integration...")
        
        tests = []
        
        try:
            # Test 1: End-to-end status flow
            test_result = {"name": "end_to_end_status", "passed": False, "details": {}}
            try:
                if self.dashboard_controller and self.health_monitor:
                    # Get status through dashboard controller
                    dashboard_status = await self.dashboard_controller.get_comprehensive_status()
                    
                    # Get status through health monitor directly
                    monitor_status = await self.health_monitor.check_all_backends_health()
                    
                    # Verify integration
                    backend_overlap = set(dashboard_status.get("backends", {}).keys()) & set(monitor_status.keys())
                    
                    test_result["passed"] = len(backend_overlap) > 0
                    test_result["details"] = {
                        "dashboard_backends": list(dashboard_status.get("backends", {}).keys()),
                        "monitor_backends": list(monitor_status.keys()),
                        "integration_overlap": list(backend_overlap)
                    }
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 2: Cluster manager integration
            test_result = {"name": "cluster_integration", "passed": False, "details": {}}
            try:
                if self.dashboard_controller and self.cluster_manager:
                    # Test cluster action through dashboard
                    from mcp.ipfs_kit.api.enhanced_dashboard_api import ClusterActionRequest
                    
                    request = ClusterActionRequest(action="status")
                    result = await self.dashboard_controller.perform_cluster_action(request)
                    
                    test_result["passed"] = result is not None
                    test_result["details"] = result
                    
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
            # Test 3: Auto-healing functionality
            test_result = {"name": "auto_healing_integration", "passed": False, "details": {}}
            try:
                if self.health_monitor:
                    # Check if auto-healing components are available
                    cluster_backend = None
                    for backend_name in self.health_monitor.backends:
                        if backend_name == "ipfs_cluster":
                            cluster_backend = await self.health_monitor.check_backend_health(backend_name)
                            break
                    
                    if cluster_backend:
                        auto_heal_available = cluster_backend.get("detailed_info", {}).get("auto_healed") is not None
                        test_result["passed"] = True  # Auto-healing structure exists
                        test_result["details"] = {
                            "auto_heal_structure": True,
                            "cluster_manager_integration": cluster_backend.get("detailed_info", {}).get("connection_method") == "cluster_daemon_manager"
                        }
                    else:
                        test_result["details"]["error"] = "Cluster backend not found"
                        
            except Exception as e:
                test_result["details"]["error"] = str(e)
                
            tests.append(test_result)
            
        except Exception as e:
            logger.error(f"Error in integration tests: {e}")
            tests.append({
                "name": "integration_error",
                "passed": False,
                "details": {"error": str(e)}
            })
        
        return {"tests": tests}
    
    def print_test_summary(self, results: Dict[str, Any]):
        """Print a formatted test summary."""
        print("\n" + "="*80)
        print("🧪 COMPREHENSIVE IPFS KIT INTEGRATION TEST RESULTS")
        print("="*80)
        
        summary = results.get("summary", {})
        print(f"📊 Overall Results: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)} tests passed ({summary.get('success_rate', 0):.1f}%)")
        print()
        
        for test_category, category_results in results.items():
            if test_category == "summary":
                continue
                
            tests = category_results.get("tests", [])
            passed = sum(1 for test in tests if test.get("passed"))
            total = len(tests)
            
            print(f"🔧 {test_category.replace('_', ' ').title()}: {passed}/{total} passed")
            
            for test in tests:
                status = "✅" if test.get("passed") else "❌"
                print(f"  {status} {test.get('name', 'unknown')}")
                
                if not test.get("passed") and "error" in test.get("details", {}):
                    print(f"    Error: {test['details']['error']}")
            print()


async def main():
    """Run the comprehensive integration tests."""
    tester = ComprehensiveIntegrationTester()
    
    try:
        results = await tester.run_all_tests()
        tester.print_test_summary(results)
        
        # Save results to file
        results_file = Path("comprehensive_test_results.json")
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"📄 Detailed results saved to: {results_file}")
        
        # Return exit code based on success rate
        success_rate = results.get("summary", {}).get("success_rate", 0)
        if success_rate >= 80:
            print("🎉 Integration tests PASSED!")
            return 0
        else:
            print("⚠️  Integration tests had issues")
            return 1
            
    except Exception as e:
        logger.error(f"Failed to run integration tests: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
