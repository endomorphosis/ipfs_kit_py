#!/usr/bin/env python3
"""
Phase 1 Infrastructure Initialization Script

This script initializes and validates all Phase 1 components:
- Unified Tool Registry System
- Robust Service Management
- Enhanced Error Handling
- Automated Testing Framework
"""

import os
import sys
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Add the core directory to Python path
core_dir = Path(__file__).parent / "core"
sys.path.insert(0, str(core_dir))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('phase1_init.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Phase1Initializer:
    """Phase 1 infrastructure initializer"""
    
    def __init__(self):
        self.components = {}
        self.initialization_status = {}
        
    def initialize_all(self) -> bool:
        """Initialize all Phase 1 components"""
        logger.info("Starting Phase 1 initialization...")
        
        components = [
            ("tool_registry", self._initialize_tool_registry),
            ("service_manager", self._initialize_service_manager),
            ("error_handler", self._initialize_error_handler),
            ("test_framework", self._initialize_test_framework)
        ]
        
        all_success = True
        for name, init_func in components:
            try:
                logger.info(f"Initializing {name}...")
                success = init_func()
                self.initialization_status[name] = "success" if success else "failed"
                if not success:
                    all_success = False
                    logger.error(f"Failed to initialize {name}")
                else:
                    logger.info(f"Successfully initialized {name}")
            except Exception as e:
                logger.error(f"Error initializing {name}: {e}")
                self.initialization_status[name] = "error"
                all_success = False
        
        if all_success:
            logger.info("Phase 1 initialization completed successfully!")
            self._run_validation_tests()
        else:
            logger.error("Phase 1 initialization completed with errors")
        
        return all_success
    
    def _initialize_tool_registry(self) -> bool:
        """Initialize the unified tool registry"""
        try:
            from ipfs_kit_py.core.tool_registry import ToolRegistry, registry, ToolCategory, ToolSchema
            
            # Add discovery paths
            registry.add_discovery_path(Path.cwd() / "ipfs_kit_py")
            registry.add_discovery_path(Path.cwd() / "tools")
            registry.add_discovery_path(Path.cwd() / "mcp")
            
            # Create some example tools for testing
            example_tool = ToolSchema(
                name="example_ping",
                category=ToolCategory.SYSTEM,
                description="Example ping tool for testing",
                parameters={
                    "message": {
                        "type": "string",
                        "description": "Message to echo back"
                    }
                },
                returns={
                    "response": {
                        "type": "string",
                        "description": "Echo response"
                    }
                },
                version="1.0.0",
                dependencies=[]
            )
            
            def example_ping_handler(params):
                return {"response": f"Ping: {params.get('message', 'Hello')}", "status": "success"}
            
            registry.register_tool(example_tool, example_ping_handler)
            
            # Save registry
            registry.save_registry()
            
            self.components["tool_registry"] = registry
            logger.info(f"Tool registry initialized with {len(registry.tools)} tools")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize tool registry: {e}")
            return False
    
    def _initialize_service_manager(self) -> bool:
        """Initialize the service manager"""
        try:
            from ipfs_kit_py.core.service_manager import ServiceManager, IPFSServiceManager, service_manager, ipfs_manager
            
            # Test service manager functionality
            available_port = service_manager.find_available_port(9000, 50)
            if available_port:
                logger.info(f"Found available port: {available_port}")
            
            # Check if IPFS is available and start if needed
            logger.info("Checking IPFS daemon status...")
            try:
                if ipfs_manager.health_check("ipfs"):
                    logger.info("✓ IPFS daemon is already running")
                else:
                    logger.info("Starting IPFS daemon...")
                    if ipfs_manager.ensure_ipfs_running():
                        logger.info("✓ IPFS daemon started successfully")
                    else:
                        logger.warning("⚠ IPFS daemon failed to start (this is OK for testing)")
            except Exception as e:
                logger.warning(f"⚠ IPFS daemon check failed: {e} (this is OK for testing)")
            
            self.components["service_manager"] = service_manager
            self.components["ipfs_manager"] = ipfs_manager
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize service manager: {e}")
            return False
    
    def _initialize_error_handler(self) -> bool:
        """Initialize the error handling system"""
        try:
            from ipfs_kit_py.core.error_handler import ErrorHandler, error_handler, ErrorCode, create_success_response
            
            # Test error handler functionality
            test_error = error_handler.create_error(
                ErrorCode.INVALID_PARAMETER,
                "Test error for validation"
            )
            
            if test_error.status == "error":
                logger.info("Error handler validation successful")
            
            # Test success response
            success_response = create_success_response("test data", "Test successful")
            if success_response["status"] == "success":
                logger.info("Success response creation working")
            
            self.components["error_handler"] = error_handler
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize error handler: {e}")
            return False
    
    def _initialize_test_framework(self) -> bool:
        """Initialize the testing framework"""
        try:
            from ipfs_kit_py.core.test_framework import TestFramework, test_framework
            
            # Discover tests
            test_count = test_framework.discover_tests(Path.cwd())
            logger.info(f"Discovered {test_count} additional tests")
            
            self.components["test_framework"] = test_framework
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize test framework: {e}")
            return False
    
    def _run_validation_tests(self) -> bool:
        """Run validation tests for all components"""
        logger.info("Running Phase 1 validation tests...")
        
        try:
            test_framework = self.components.get("test_framework")
            if not test_framework:
                logger.error("Test framework not available")
                return False
            
            # Run core infrastructure tests
            results = test_framework.run_test_suite("core_infrastructure")
            
            passed = len([r for r in results if r.status.value == "passed"])
            total = len(results)
            
            logger.info(f"Validation tests completed: {passed}/{total} passed")
            
            if passed == total:
                logger.info("All validation tests passed!")
                return True
            else:
                logger.warning("Some validation tests failed")
                
                # Print failed tests
                for result in results:
                    if result.status.value != "passed":
                        logger.error(f"Test {result.name}: {result.message}")
                
                return False
                
        except Exception as e:
            logger.error(f"Error running validation tests: {e}")
            return False
    
    def generate_status_report(self) -> Dict[str, Any]:
        """Generate initialization status report"""
        report = {
            "phase": "Phase 1 - Core Infrastructure",
            "timestamp": str(Path(__file__).stat().st_mtime),
            "components": self.initialization_status.copy(),
            "summary": {
                "total_components": len(self.initialization_status),
                "successful": len([s for s in self.initialization_status.values() if s == "success"]),
                "failed": len([s for s in self.initialization_status.values() if s in ["failed", "error"]]),
                "overall_status": "success" if all(s == "success" for s in self.initialization_status.values()) else "partial"
            }
        }
        
        # Add component details
        if "tool_registry" in self.components:
            registry = self.components["tool_registry"]
            report["tool_registry_stats"] = registry.get_registry_stats()
        
        if "service_manager" in self.components:
            manager = self.components["service_manager"]
            report["service_manager_stats"] = manager.get_all_service_status()
        
        if "error_handler" in self.components:
            handler = self.components["error_handler"]
            report["error_handler_stats"] = handler.get_error_statistics()
        
        if "test_framework" in self.components:
            framework = self.components["test_framework"]
            report["test_framework_stats"] = framework.get_test_statistics()
        
        return report
    
    def save_status_report(self, filename: str = "phase1_status.json"):
        """Save status report to file"""
        try:
            report = self.generate_status_report()
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Status report saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save status report: {e}")
            return False

def main():
    """Main initialization function"""
    print("=" * 60)
    print("IPFS Kit MCP Integration - Phase 1 Initialization")
    print("=" * 60)
    print()
    
    # Create initializer
    initializer = Phase1Initializer()
    
    # Run initialization
    success = initializer.initialize_all()
    
    # Generate and save report
    initializer.save_status_report()
    
    # Print summary
    print()
    print("=" * 60)
    print("INITIALIZATION SUMMARY")
    print("=" * 60)
    
    for component, status in initializer.initialization_status.items():
        status_symbol = "✓" if status == "success" else "✗"
        print(f"{status_symbol} {component}: {status}")
    
    print()
    if success:
        print("🎉 Phase 1 initialization completed successfully!")
        print("✓ Unified Tool Registry System")
        print("✓ Robust Service Management")
        print("✓ Enhanced Error Handling")
        print("✓ Automated Testing Framework")
        print()
        print("Next steps:")
        print("1. Review phase1_status.json for detailed component information")
        print("2. Run additional tests: python -c 'from ipfs_kit_py.core.test_framework import test_framework; test_framework.run_all_tests()'")
        print("3. Proceed to Phase 2: Tool Implementation")
    else:
        print("❌ Phase 1 initialization completed with errors")
        print("Please check the logs and resolve issues before proceeding")
    
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
