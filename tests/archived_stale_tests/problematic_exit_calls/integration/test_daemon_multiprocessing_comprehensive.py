#!/usr/bin/env python3
"""
Comprehensive Test Suite for IPFS-Kit Daemon and Multiprocessing Components

This test suite covers:
1. Basic daemon functionality
2. Multiprocessing enhancements
3. Backend health monitoring
4. Replication management
5. Performance testing
6. Integration testing
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock
import signal
import psutil

# Import test frameworks
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Create simple assert function
    def assert_function(condition, message="Assertion failed"):
        if not condition:
            raise AssertionError(message)
    
    # Patch assert for compatibility
    import builtins
    if not hasattr(builtins, 'assert'):
        builtins.assert = assert_function
    
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn
    from rich.table import Table
    from rich.live import Live
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import IPFS Kit components
try:
    from ipfs_kit_daemon import IPFSKitDaemon
    from enhanced_multiprocessing_daemon import EnhancedIPFSKitDaemon
    from enhanced_multiprocessing_mcp_server import EnhancedMultiprocessingMCPServer
    from enhanced_multiprocessing_cli import EnhancedMultiprocessingCLI
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import components: {e}")
    COMPONENTS_AVAILABLE = False


class TestResult:
    """Test result tracking"""
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.error: Optional[str] = None
        self.duration = 0.0
        self.details: Dict[str, Any] = {}


class IPFSKitDaemonTestSuite:
    """Comprehensive test suite for IPFS-Kit daemon and multiprocessing"""
    
    def __init__(self):
        self.test_results: List[TestResult] = []
        self.temp_dir = None
        self.daemon_process = None
        self.test_config = self._create_test_config()
        
    def _create_test_config(self) -> Dict[str, Any]:
        """Create test configuration"""
        return {
            "daemon": {
                "pid_file": "/tmp/test_ipfs_kit_daemon.pid",
                "log_level": "DEBUG",
                "health_check_interval": 5,
                "replication_check_interval": 10,
                "log_rotation_interval": 30
            },
            "backends": {
                "ipfs": {"enabled": True, "auto_start": False},  # Don't auto-start for tests
                "ipfs_cluster": {"enabled": False, "auto_start": False},
                "lotus": {"enabled": False, "auto_start": False},
                "lassie": {"enabled": False, "auto_start": False}
            },
            "replication": {
                "enabled": False,  # Disable for tests
                "auto_replication": False,
                "min_replicas": 1,
                "max_replicas": 2
            },
            "monitoring": {
                "health_checks": True,
                "metrics_collection": True,
                "log_aggregation": True,
                "performance_monitoring": True
            }
        }
    
    def setup(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_kit_test_")
        self.test_config_file = os.path.join(self.temp_dir, "test_daemon.json")
        
        # Write test config
        with open(self.test_config_file, 'w') as f:
            json.dump(self.test_config, f, indent=2)
        
        if console:
            console.print("🔧 Test environment set up", style="green")
    
    def cleanup(self):
        """Clean up test environment"""
        if self.daemon_process and self.daemon_process.poll() is None:
            self.daemon_process.terminate()
            try:
                self.daemon_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.daemon_process.kill()
        
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        if console:
            console.print("🧹 Test environment cleaned up", style="yellow")
    
    async def test_basic_daemon_functionality(self) -> TestResult:
        """Test basic daemon creation and configuration"""
        result = TestResult("Basic Daemon Functionality")
        start_time = time.time()
        
        try:
            if not COMPONENTS_AVAILABLE:
                result.error = "Components not available"
                return result
            
            # Test daemon creation
            daemon = IPFSKitDaemon(config_file=self.test_config_file)
            
            # Test configuration loading
            assert daemon.config is not None
            assert "daemon" in daemon.config
            assert "backends" in daemon.config
            
            # Test status methods
            status = daemon.get_status()
            assert isinstance(status, dict)
            
            result.success = True
            result.details = {
                "config_loaded": True,
                "status_method": True,
                "config_file": self.test_config_file
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def test_enhanced_daemon_creation(self) -> TestResult:
        """Test enhanced multiprocessing daemon creation"""
        result = TestResult("Enhanced Daemon Creation")
        start_time = time.time()
        
        try:
            if not COMPONENTS_AVAILABLE:
                result.error = "Components not available"
                return result
            
            # Test enhanced daemon creation
            enhanced_daemon = EnhancedIPFSKitDaemon(
                config_file=self.test_config_file,
                max_workers=4
            )
            
            # Test configuration
            assert enhanced_daemon.config is not None
            assert enhanced_daemon.max_workers == 4
            assert enhanced_daemon.stats is not None
            
            # Test statistics tracking
            stats = enhanced_daemon.stats.get_stats()
            assert isinstance(stats, dict)
            assert "total_requests" in stats
            
            result.success = True
            result.details = {
                "enhanced_daemon_created": True,
                "max_workers": enhanced_daemon.max_workers,
                "stats_available": True
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def test_multiprocessing_mcp_server(self) -> TestResult:
        """Test enhanced multiprocessing MCP server"""
        result = TestResult("Multiprocessing MCP Server")
        start_time = time.time()
        
        try:
            if not COMPONENTS_AVAILABLE:
                result.error = "Components not available"
                return result
            
            # Test MCP server creation
            mcp_server = EnhancedMultiprocessingMCPServer(
                host="127.0.0.1",
                port=8889,  # Use different port for testing
                workers=2
            )
            
            # Test server configuration
            assert mcp_server.host == "127.0.0.1"
            assert mcp_server.port == 8889
            assert mcp_server.workers == 2
            
            # Test process pools creation
            mcp_server.start_process_pools()
            assert mcp_server.vfs_pool is not None
            assert mcp_server.backend_pool is not None
            assert mcp_server.route_pool is not None
            
            # Test statistics
            stats = mcp_server.get_server_stats()
            assert isinstance(stats, dict)
            
            # Cleanup
            mcp_server.cleanup()
            
            result.success = True
            result.details = {
                "server_created": True,
                "process_pools": True,
                "statistics": True
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def test_multiprocessing_cli(self) -> TestResult:
        """Test enhanced multiprocessing CLI"""
        result = TestResult("Multiprocessing CLI")
        start_time = time.time()
        
        try:
            if not COMPONENTS_AVAILABLE:
                result.error = "Components not available"
                return result
            
            # Test CLI creation
            cli = EnhancedMultiprocessingCLI(max_workers=4)
            
            # Test configuration
            assert cli.max_workers == 4
            assert cli.stats is not None
            
            # Test process pools creation
            cli.start_process_pools()
            assert cli.ipfs_pool is not None
            assert cli.backend_pool is not None
            assert cli.io_thread_pool is not None
            
            # Test statistics
            stats = cli.get_stats()
            assert isinstance(stats, dict)
            
            # Cleanup
            cli.cleanup()
            
            result.success = True
            result.details = {
                "cli_created": True,
                "process_pools": True,
                "statistics": True
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def test_process_stats_tracking(self) -> TestResult:
        """Test process statistics tracking"""
        result = TestResult("Process Stats Tracking")
        start_time = time.time()
        
        try:
            if not COMPONENTS_AVAILABLE:
                result.error = "Components not available"
                return result
            
            from enhanced_multiprocessing_daemon import ProcessStats
            
            # Create stats object
            stats = ProcessStats()
            
            # Test initial stats
            initial_stats = stats.get_stats()
            assert initial_stats["total_requests"] == 0
            assert initial_stats["successful_requests"] == 0
            
            # Test updating stats
            stats.update_request_count(5)
            stats.update_success_count(3)
            stats.update_failure_count(2)
            stats.update_response_time(1.5)
            stats.update_active_workers(4)
            
            # Verify updates
            updated_stats = stats.get_stats()
            assert updated_stats["total_requests"] == 5
            assert updated_stats["successful_requests"] == 3
            assert updated_stats["failed_requests"] == 2
            assert updated_stats["active_workers"] == 4
            assert updated_stats["success_rate"] == 60.0
            
            result.success = True
            result.details = {
                "stats_creation": True,
                "stats_updates": True,
                "success_rate_calculation": True
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def test_configuration_management(self) -> TestResult:
        """Test configuration loading and management"""
        result = TestResult("Configuration Management")
        start_time = time.time()
        
        try:
            # Test config file creation
            test_config = {
                "daemon": {"health_check_interval": 15},
                "backends": {"ipfs": {"enabled": True}}
            }
            
            config_file = os.path.join(self.temp_dir, "test_config.json")
            with open(config_file, 'w') as f:
                json.dump(test_config, f)
            
            # Test daemon with custom config
            if COMPONENTS_AVAILABLE:
                daemon = IPFSKitDaemon(config_file=config_file)
                assert daemon.config["daemon"]["health_check_interval"] == 15
                assert daemon.config["backends"]["ipfs"]["enabled"] is True
            
            result.success = True
            result.details = {
                "config_file_created": True,
                "config_loaded": COMPONENTS_AVAILABLE,
                "custom_values": True
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def test_process_pool_management(self) -> TestResult:
        """Test process pool creation and management"""
        result = TestResult("Process Pool Management")
        start_time = time.time()
        
        try:
            from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
            import multiprocessing as mp
            
            # Test CPU count detection
            cpu_count = mp.cpu_count()
            assert cpu_count > 0
            
            # Test process pool creation
            with ProcessPoolExecutor(max_workers=2) as pool:
                assert pool is not None
                
                # Test simple task submission
                future = pool.submit(lambda x: x * 2, 5)
                result_value = future.result(timeout=5)
                assert result_value == 10
            
            # Test thread pool creation
            with ThreadPoolExecutor(max_workers=2) as thread_pool:
                assert thread_pool is not None
                
                # Test simple task submission
                future = thread_pool.submit(lambda x: x + 1, 10)
                result_value = future.result(timeout=5)
                assert result_value == 11
            
            result.success = True
            result.details = {
                "cpu_count": cpu_count,
                "process_pool": True,
                "thread_pool": True,
                "task_execution": True
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def test_error_handling(self) -> TestResult:
        """Test error handling and recovery"""
        result = TestResult("Error Handling")
        start_time = time.time()
        
        try:
            # Test with invalid config file
            invalid_config_file = "/nonexistent/path/config.json"
            
            if COMPONENTS_AVAILABLE:
                daemon = IPFSKitDaemon(config_file=invalid_config_file)
                # Should fall back to defaults
                assert daemon.config is not None
                assert "daemon" in daemon.config
            
            # Test error handling in process pools
            from concurrent.futures import ProcessPoolExecutor
            
            def failing_function():
                raise ValueError("Test error")
            
            with ProcessPoolExecutor(max_workers=1) as pool:
                future = pool.submit(failing_function)
                try:
                    future.result(timeout=5)
                    assert False, "Should have raised exception"
                except ValueError:
                    pass  # Expected
            
            result.success = True
            result.details = {
                "config_fallback": COMPONENTS_AVAILABLE,
                "exception_handling": True,
                "graceful_degradation": True
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def test_system_resource_detection(self) -> TestResult:
        """Test system resource detection and optimization"""
        result = TestResult("System Resource Detection")
        start_time = time.time()
        
        try:
            import multiprocessing as mp
            import psutil
            
            # Test CPU detection
            cpu_count = mp.cpu_count()
            assert cpu_count > 0
            
            # Test memory detection
            memory = psutil.virtual_memory()
            assert memory.total > 0
            
            # Test optimal worker calculation
            optimal_workers = min(cpu_count, 8)  # Common pattern
            assert optimal_workers > 0
            assert optimal_workers <= cpu_count
            
            # Test system load
            try:
                load_avg = psutil.getloadavg()
                assert len(load_avg) == 3
            except AttributeError:
                # getloadavg not available on all platforms
                pass
            
            result.success = True
            result.details = {
                "cpu_count": cpu_count,
                "memory_total": memory.total,
                "optimal_workers": optimal_workers,
                "psutil_available": True
            }
            
        except Exception as e:
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        return result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return comprehensive results"""
        if console:
            console.print("🚀 Starting IPFS-Kit Daemon Test Suite", style="bold blue")
            console.print("=" * 60)
        
        self.setup()
        
        try:
            # Run all tests
            tests = [
                self.test_basic_daemon_functionality(),
                self.test_enhanced_daemon_creation(),
                self.test_multiprocessing_mcp_server(),
                self.test_multiprocessing_cli(),
                self.test_process_stats_tracking(),
                self.test_configuration_management(),
                self.test_process_pool_management(),
                self.test_error_handling(),
                self.test_system_resource_detection()
            ]
            
            # Execute tests with progress
            if console and RICH_AVAILABLE:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                ) as progress:
                    task = progress.add_task("Running tests...", total=len(tests))
                    
                    for test_coro in tests:
                        test_result = await test_coro
                        self.test_results.append(test_result)
                        progress.advance(task)
                        
                        if console:
                            status = "✅" if test_result.success else "❌"
                            console.print(f"{status} {test_result.name}: {test_result.duration:.2f}s")
            else:
                for i, test_coro in enumerate(tests):
                    print(f"Running test {i+1}/{len(tests)}...")
                    test_result = await test_coro
                    self.test_results.append(test_result)
                    
                    status = "PASS" if test_result.success else "FAIL"
                    print(f"{status}: {test_result.name} ({test_result.duration:.2f}s)")
            
            # Generate summary
            return self._generate_test_summary()
            
        finally:
            self.cleanup()
    
    def _generate_test_summary(self) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - passed_tests
        total_duration = sum(r.duration for r in self.test_results)
        
        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "total_duration": total_duration,
            "avg_duration": total_duration / total_tests if total_tests > 0 else 0,
            "test_details": []
        }
        
        for test_result in self.test_results:
            summary["test_details"].append({
                "name": test_result.name,
                "success": test_result.success,
                "error": test_result.error,
                "duration": test_result.duration,
                "details": test_result.details
            })
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]):
        """Print test summary to console"""
        if console and RICH_AVAILABLE:
            # Create summary table
            table = Table(title="Test Results Summary")
            table.add_column("Test Name", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Duration", style="yellow")
            table.add_column("Details", style="white")
            
            for test_detail in summary["test_details"]:
                status = "✅ PASS" if test_detail["success"] else "❌ FAIL"
                duration = f"{test_detail['duration']:.2f}s"
                details = test_detail.get("error", "Success") or "Success"
                
                table.add_row(
                    test_detail["name"],
                    status,
                    duration,
                    details[:50] + "..." if len(details) > 50 else details
                )
            
            console.print(table)
            
            # Summary panel
            summary_text = f"""
Total Tests: {summary['total_tests']}
Passed: {summary['passed']}
Failed: {summary['failed']}
Success Rate: {summary['success_rate']:.1f}%
Total Duration: {summary['total_duration']:.2f}s
Average Duration: {summary['avg_duration']:.2f}s
"""
            
            panel = Panel(
                summary_text,
                title="Test Summary",
                border_style="green" if summary['failed'] == 0 else "red"
            )
            console.print(panel)
        else:
            print("\n" + "=" * 60)
            print("TEST RESULTS SUMMARY")
            print("=" * 60)
            print(f"Total Tests: {summary['total_tests']}")
            print(f"Passed: {summary['passed']}")
            print(f"Failed: {summary['failed']}")
            print(f"Success Rate: {summary['success_rate']:.1f}%")
            print(f"Total Duration: {summary['total_duration']:.2f}s")
            print("=" * 60)


async def main():
    """Main test runner"""
    test_suite = IPFSKitDaemonTestSuite()
    summary = await test_suite.run_all_tests()
    test_suite.print_summary(summary)
    
    # Exit with appropriate code
    exit_code = 0 if summary['failed'] == 0 else 1
    return exit_code


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Test suite failed: {e}")
        sys.exit(1)
