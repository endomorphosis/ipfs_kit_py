#!/usr/bin/env python3
"""
Automated Testing Framework for IPFS Kit MCP Integration

This module provides comprehensive testing capabilities including:
- Unit tests for core components
- Integration tests
- Performance testing
- Automated test discovery
- Test reporting and metrics
"""

import unittest
import anyio
import inspect
import time
import json
import logging
import traceback
import importlib.util
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
import subprocess

# Setup logging
logger = logging.getLogger(__name__)

class TestStatus(Enum):
    """Test execution status"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"

class TestCategory(Enum):
    """Test category classification"""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SMOKE = "smoke"
    STRESS = "stress"

@dataclass
class TestResult:
    """Test execution result"""
    name: str
    category: TestCategory
    status: TestStatus
    duration: float
    message: str = ""
    error: Optional[str] = None
    assertions: int = 0
    setup_time: float = 0.0
    teardown_time: float = 0.0

@dataclass
class TestSuite:
    """Test suite definition"""
    name: str
    tests: List[Callable]
    setup: Optional[Callable] = None
    teardown: Optional[Callable] = None
    category: TestCategory = TestCategory.UNIT

class TestFramework:
    """Comprehensive testing framework"""
    
    def __init__(self):
        self.test_suites: Dict[str, TestSuite] = {}
        self.test_results: List[TestResult] = []
        self.test_modules: List[str] = []
        self.setup_functions: List[Callable] = []
        self.teardown_functions: List[Callable] = []
        
    def register_test_suite(self, suite: TestSuite) -> bool:
        """Register a test suite"""
        try:
            self.test_suites[suite.name] = suite
            logger.info(f"Registered test suite: {suite.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to register test suite {suite.name}: {e}")
            return False
    
    def discover_tests(self, test_path: Path) -> int:
        """Automatically discover test modules and functions"""
        discovered_count = 0
        
        try:
            for py_file in test_path.rglob("test_*.py"):
                module_name = py_file.stem
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Extract test functions
                    tests = []
                    for name, obj in module.__dict__.items():
                        if name.startswith('test_') and callable(obj):
                            tests.append(obj)
                    
                    if tests:
                        # Create test suite
                        suite = TestSuite(
                            name=module_name,
                            tests=tests,
                            setup=getattr(module, 'setUp', None),
                            teardown=getattr(module, 'tearDown', None)
                        )
                        
                        if self.register_test_suite(suite):
                            discovered_count += len(tests)
                            
        except Exception as e:
            logger.error(f"Error discovering tests from {test_path}: {e}")
        
        logger.info(f"Discovered {discovered_count} tests")
        return discovered_count
    
    def run_test_suite(self, suite_name: str) -> List[TestResult]:
        """Run a specific test suite"""
        if suite_name not in self.test_suites:
            logger.error(f"Test suite {suite_name} not found")
            return []
        
        suite = self.test_suites[suite_name]
        results = []
        
        logger.info(f"Running test suite: {suite_name}")
        
        # Run suite setup
        setup_time = 0.0
        if suite.setup:
            start_time = time.time()
            try:
                suite.setup()
                setup_time = time.time() - start_time
            except Exception as e:
                logger.error(f"Suite setup failed for {suite_name}: {e}")
                return results
        
        # Run individual tests
        for test_func in suite.tests:
            result = self._run_single_test(test_func, suite.category, setup_time)
            results.append(result)
            self.test_results.append(result)
        
        # Run suite teardown
        teardown_time = 0.0
        if suite.teardown:
            start_time = time.time()
            try:
                suite.teardown()
                teardown_time = time.time() - start_time
            except Exception as e:
                logger.error(f"Suite teardown failed for {suite_name}: {e}")
        
        # Update teardown time for all tests
        for result in results:
            result.teardown_time = teardown_time
        
        return results
    
    def run_all_tests(self, category_filter: Optional[TestCategory] = None) -> List[TestResult]:
        """Run all registered test suites"""
        all_results = []
        
        for suite_name, suite in self.test_suites.items():
            if category_filter and suite.category != category_filter:
                continue
                
            results = self.run_test_suite(suite_name)
            all_results.extend(results)
        
        return all_results
    
    def _run_single_test(self, test_func: Callable, category: TestCategory, setup_time: float) -> TestResult:
        """Run a single test function"""
        test_name = test_func.__name__
        start_time = time.time()
        
        try:
            # Execute test
            if inspect.iscoroutinefunction(test_func):
                anyio.run(test_func)
            else:
                test_func()
            
            duration = time.time() - start_time
            
            return TestResult(
                name=test_name,
                category=category,
                status=TestStatus.PASSED,
                duration=duration,
                setup_time=setup_time,
                message="Test passed successfully"
            )
            
        except AssertionError as e:
            duration = time.time() - start_time
            return TestResult(
                name=test_name,
                category=category,
                status=TestStatus.FAILED,
                duration=duration,
                setup_time=setup_time,
                message=str(e),
                error=traceback.format_exc()
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name=test_name,
                category=category,
                status=TestStatus.ERROR,
                duration=duration,
                setup_time=setup_time,
                message=str(e),
                error=traceback.format_exc()
            )
    
    def generate_report(self, format: str = "json") -> str:
        """Generate test report"""
        if format == "json":
            return self._generate_json_report()
        elif format == "html":
            return self._generate_html_report()
        else:
            return self._generate_text_report()
    
    def _generate_json_report(self) -> str:
        """Generate JSON test report"""
        stats = self.get_test_statistics()
        
        report = {
            "summary": stats,
            "results": [
                {
                    "name": result.name,
                    "category": result.category.value,
                    "status": result.status.value,
                    "duration": result.duration,
                    "message": result.message,
                    "error": result.error,
                    "setup_time": result.setup_time,
                    "teardown_time": result.teardown_time
                }
                for result in self.test_results
            ]
        }
        
        return json.dumps(report, indent=2)
    
    def _generate_text_report(self) -> str:
        """Generate text test report"""
        stats = self.get_test_statistics()
        
        report = []
        report.append("=" * 60)
        report.append("TEST EXECUTION REPORT")
        report.append("=" * 60)
        report.append(f"Total Tests: {stats['total_tests']}")
        report.append(f"Passed: {stats['passed']}")
        report.append(f"Failed: {stats['failed']}")
        report.append(f"Errors: {stats['errors']}")
        report.append(f"Success Rate: {stats['success_rate']:.1f}%")
        report.append(f"Total Duration: {stats['total_duration']:.2f}s")
        report.append("")
        
        # Group by status
        for status in TestStatus:
            status_results = [r for r in self.test_results if r.status == status]
            if status_results:
                report.append(f"{status.value.upper()} TESTS:")
                report.append("-" * 40)
                for result in status_results:
                    report.append(f"  {result.name} ({result.duration:.2f}s)")
                    if result.message:
                        report.append(f"    {result.message}")
                report.append("")
        
        return "\n".join(report)
    
    def _generate_html_report(self) -> str:
        """Generate HTML test report"""
        stats = self.get_test_statistics()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                .passed {{ color: #28a745; }}
                .failed {{ color: #dc3545; }}
                .error {{ color: #fd7e14; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Test Execution Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p>Total Tests: {stats['total_tests']}</p>
                <p class="passed">Passed: {stats['passed']}</p>
                <p class="failed">Failed: {stats['failed']}</p>
                <p class="error">Errors: {stats['errors']}</p>
                <p>Success Rate: {stats['success_rate']:.1f}%</p>
                <p>Total Duration: {stats['total_duration']:.2f}s</p>
            </div>
            
            <h2>Test Results</h2>
            <table>
                <tr>
                    <th>Test Name</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Message</th>
                </tr>
        """
        
        for result in self.test_results:
            status_class = result.status.value
            html += f"""
                <tr>
                    <td>{result.name}</td>
                    <td>{result.category.value}</td>
                    <td class="{status_class}">{result.status.value}</td>
                    <td>{result.duration:.2f}s</td>
                    <td>{result.message}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html
    
    def get_test_statistics(self) -> Dict[str, Any]:
        """Get test execution statistics"""
        total = len(self.test_results)
        passed = len([r for r in self.test_results if r.status == TestStatus.PASSED])
        failed = len([r for r in self.test_results if r.status == TestStatus.FAILED])
        errors = len([r for r in self.test_results if r.status == TestStatus.ERROR])
        skipped = len([r for r in self.test_results if r.status == TestStatus.SKIPPED])
        
        success_rate = (passed / total * 100) if total > 0 else 0
        total_duration = sum(r.duration for r in self.test_results)
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "success_rate": success_rate,
            "total_duration": total_duration,
            "average_duration": total_duration / total if total > 0 else 0
        }
    
    def clear_results(self):
        """Clear all test results"""
        self.test_results.clear()

# Core infrastructure tests
class CoreInfrastructureTests:
    """Test suite for core infrastructure components"""
    
    @staticmethod
    def test_tool_registry_creation():
        """Test tool registry initialization"""
        from .tool_registry import ToolRegistry, ToolCategory, ToolSchema
        
        registry = ToolRegistry()
        assert registry is not None
        assert len(registry.tools) == 0
        logger.info("Tool registry creation test passed")
    
    @staticmethod
    def test_tool_registration():
        """Test tool registration functionality"""
        from .tool_registry import ToolRegistry, ToolCategory, ToolSchema, ToolStatus
        
        registry = ToolRegistry()
        
        # Create test tool
        tool = ToolSchema(
            name="test_tool",
            category=ToolCategory.SYSTEM,
            description="Test tool for validation",
            parameters={"param1": {"type": "string"}},
            returns={"result": {"type": "string"}},
            version="1.0.0",
            dependencies=[]
        )
        
        # Register tool
        success = registry.register_tool(tool)
        assert success is True
        assert "test_tool" in registry.tools
        assert registry.tools["test_tool"].status == ToolStatus.REGISTERED
        
        logger.info("Tool registration test passed")
    
    @staticmethod
    def test_service_manager_creation():
        """Test service manager initialization"""
        from .service_manager import ServiceManager
        
        manager = ServiceManager()
        assert manager is not None
        assert len(manager.services) == 0
        
        logger.info("Service manager creation test passed")
    
    @staticmethod
    def test_error_handler_creation():
        """Test error handler initialization"""
        from .error_handler import ErrorHandler, ErrorCode, create_success_response
        
        handler = ErrorHandler()
        assert handler is not None
        
        # Test success response
        response = create_success_response("test data")
        assert response["status"] == "success"
        assert response["data"] == "test data"
        
        # Test error creation
        error = handler.create_error(ErrorCode.INVALID_PARAMETER, "Test error")
        assert error.status == "error"
        assert error.error_code == ErrorCode.INVALID_PARAMETER.value
        
        logger.info("Error handler creation test passed")
    
    @staticmethod
    def test_port_availability():
        """Test port availability checking"""
        from .service_manager import ServiceManager
        
        manager = ServiceManager()
        
        # Test port finding
        port = manager.find_available_port(9000, 10)
        assert port is not None
        assert 9000 <= port < 9010
        
        logger.info("Port availability test passed")

# Performance tests
class PerformanceTests:
    """Performance testing suite"""
    
    @staticmethod
    def test_tool_registry_performance():
        """Test tool registry performance with many tools"""
        from .tool_registry import ToolRegistry, ToolCategory, ToolSchema
        
        registry = ToolRegistry()
        start_time = time.time()
        
        # Register 100 tools
        for i in range(100):
            tool = ToolSchema(
                name=f"test_tool_{i}",
                category=ToolCategory.SYSTEM,
                description=f"Test tool {i}",
                parameters={},
                returns={},
                version="1.0.0",
                dependencies=[]
            )
            registry.register_tool(tool)
        
        duration = time.time() - start_time
        assert duration < 1.0  # Should complete in under 1 second
        assert len(registry.tools) == 100
        
        logger.info(f"Tool registry performance test passed ({duration:.3f}s)")

# Integration tests
class IntegrationTests:
    """Integration testing suite"""
    
    @staticmethod
    def test_service_error_integration():
        """Test integration between service manager and error handler"""
        from .service_manager import ServiceManager, ServiceConfig
        from .error_handler import ErrorHandler, ErrorCode
        
        manager = ServiceManager()
        handler = ErrorHandler()
        
        # Try to start non-existent service
        config = ServiceConfig(
            name="fake_service",
            command=["fake_command_that_does_not_exist"]
        )
        
        manager.register_service(config)
        success = manager.start_service("fake_service")
        
        # Should fail gracefully
        assert success is False
        
        logger.info("Service-error integration test passed")

# Create test suites
def create_test_suites() -> List[TestSuite]:
    """Create all test suites"""
    suites = []
    
    # Core infrastructure tests
    core_tests = TestSuite(
        name="core_infrastructure",
        tests=[
            CoreInfrastructureTests.test_tool_registry_creation,
            CoreInfrastructureTests.test_tool_registration,
            CoreInfrastructureTests.test_service_manager_creation,
            CoreInfrastructureTests.test_error_handler_creation,
            CoreInfrastructureTests.test_port_availability
        ],
        category=TestCategory.UNIT
    )
    suites.append(core_tests)
    
    # Performance tests
    perf_tests = TestSuite(
        name="performance",
        tests=[
            PerformanceTests.test_tool_registry_performance
        ],
        category=TestCategory.PERFORMANCE
    )
    suites.append(perf_tests)
    
    # Integration tests
    integration_tests = TestSuite(
        name="integration",
        tests=[
            IntegrationTests.test_service_error_integration
        ],
        category=TestCategory.INTEGRATION
    )
    suites.append(integration_tests)
    
    return suites

# Global test framework instance
test_framework = TestFramework()

# Register default test suites
for suite in create_test_suites():
    test_framework.register_test_suite(suite)
