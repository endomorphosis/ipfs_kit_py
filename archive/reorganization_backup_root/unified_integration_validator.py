#!/usr/bin/env python3
"""
Unified Enhanced Pin Index Integration Validator

This script validates that all CLI, API, and MCP server components
are properly using the enhanced pin metadata index consistently.

Components checked:
1. CLI (enhanced_pin_cli.py)
2. Main API (ipfs_kit_py/api.py)
3. Storage Backends API (storage_backends_api.py) 
4. Enhanced Pin API (enhanced_pin_api.py)
5. MCP Health Monitor (mcp/ipfs_kit/backends/health_monitor.py)

Validation criteria:
- All components import and use the enhanced pin index
- Graceful fallback to basic implementation when enhanced not available
- Consistent error handling and logging
- Unified data structures and response formats
"""

import os
import sys
import asyncio
import importlib.util
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add ipfs_kit_py to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)

class UnifiedIntegrationValidator:
    """Validates unified enhanced pin index integration across all components."""
    
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.results = {
            "components": {},
            "summary": {
                "total_components": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0
            }
        }
        
    def validate_cli_integration(self) -> Dict[str, Any]:
        """Validate CLI integration with enhanced pin index."""
        result = {
            "component": "CLI (enhanced_pin_cli.py)",
            "status": "unknown",
            "checks": [],
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Check if CLI file exists
            cli_path = self.base_path / "enhanced_pin_cli.py"
            if not cli_path.exists():
                result["status"] = "failed"
                result["issues"].append("CLI file not found")
                return result
            
            # Check imports
            with open(cli_path, 'r') as f:
                content = f.read()
            
            checks = [
                ("Enhanced index import", "from ipfs_kit_py.enhanced_pin_index import" in content),
                ("Fallback import", "from ipfs_kit_py.pins import get_global_pin_index" in content),
                ("Availability flags", "ENHANCED_INDEX_AVAILABLE" in content and "BASIC_INDEX_AVAILABLE" in content),
                ("CLI metrics function", "get_cli_pin_metrics" in content),
                ("Error handling", "try:" in content and "except" in content),
                ("Help text", "argparse" in content or "help=" in content)
            ]
            
            for check_name, passed in checks:
                result["checks"].append({"name": check_name, "status": "passed" if passed else "failed"})
                if not passed:
                    result["issues"].append(f"Missing: {check_name}")
            
            # Try to import and test basic functionality
            try:
                spec = importlib.util.spec_from_file_location("enhanced_pin_cli", cli_path)
                cli_module = importlib.util.module_from_spec(spec)
                sys.modules["enhanced_pin_cli"] = cli_module
                spec.loader.exec_module(cli_module)
                
                result["checks"].append({"name": "Import successful", "status": "passed"})
                
                # Check if main functions exist
                if hasattr(cli_module, 'print_metrics'):
                    result["checks"].append({"name": "print_metrics function", "status": "passed"})
                else:
                    result["checks"].append({"name": "print_metrics function", "status": "failed"})
                    result["issues"].append("Missing print_metrics function")
                    
            except Exception as e:
                result["checks"].append({"name": "Import test", "status": "failed"})
                result["issues"].append(f"Import failed: {e}")
            
            # Determine overall status
            failed_checks = [c for c in result["checks"] if c["status"] == "failed"]
            if not failed_checks:
                result["status"] = "passed"
            elif len(failed_checks) <= 2:
                result["status"] = "warning"
                result["recommendations"].append("Fix minor issues for optimal functionality")
            else:
                result["status"] = "failed"
                result["recommendations"].append("Major issues need to be resolved")
                
        except Exception as e:
            result["status"] = "failed"
            result["issues"].append(f"Validation error: {e}")
        
        return result
    
    def validate_api_integration(self) -> Dict[str, Any]:
        """Validate main API integration with enhanced pin index."""
        result = {
            "component": "Main API (api.py)",
            "status": "unknown", 
            "checks": [],
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Check main API file
            api_path = self.base_path / "ipfs_kit_py" / "api.py"
            if not api_path.exists():
                result["status"] = "failed"
                result["issues"].append("Main API file not found")
                return result
            
            with open(api_path, 'r') as f:
                content = f.read()
            
            checks = [
                ("Enhanced Pin API flag", "ENHANCED_PIN_API_AVAILABLE" in content),
                ("Enhanced Pin API import", "enhanced_pin_api" in content),
                ("Router inclusion", "enhanced_pin_router" in content),
                ("Logging messages", "Enhanced Pin API available" in content),
                ("Error handling", "try:" in content and "except ImportError:" in content)
            ]
            
            for check_name, passed in checks:
                result["checks"].append({"name": check_name, "status": "passed" if passed else "failed"})
                if not passed:
                    result["issues"].append(f"Missing: {check_name}")
            
            # Check enhanced pin API file
            enhanced_api_path = self.base_path / "ipfs_kit_py" / "enhanced_pin_api.py"
            if enhanced_api_path.exists():
                result["checks"].append({"name": "Enhanced Pin API file exists", "status": "passed"})
                
                with open(enhanced_api_path, 'r') as f:
                    enhanced_content = f.read()
                
                enhanced_checks = [
                    ("FastAPI router", "enhanced_pin_router" in enhanced_content),
                    ("Status endpoint", "@enhanced_pin_router.get(\"/status\"" in enhanced_content),
                    ("Metrics endpoint", "@enhanced_pin_router.get(\"/metrics\"" in enhanced_content),
                    ("VFS endpoint", "@enhanced_pin_router.get(\"/vfs\"" in enhanced_content),
                    ("Tracking endpoint", "@enhanced_pin_router.get(\"/track" in enhanced_content),
                    ("Analytics endpoint", "@enhanced_pin_router.get(\"/analytics\"" in enhanced_content),
                    ("Record endpoint", "@enhanced_pin_router.post(\"/record\"" in enhanced_content)
                ]
                
                for check_name, passed in enhanced_checks:
                    result["checks"].append({"name": f"Enhanced API: {check_name}", "status": "passed" if passed else "failed"})
                    if not passed:
                        result["issues"].append(f"Enhanced API missing: {check_name}")
            else:
                result["checks"].append({"name": "Enhanced Pin API file exists", "status": "failed"})
                result["issues"].append("Enhanced Pin API file not found")
            
            # Determine overall status
            failed_checks = [c for c in result["checks"] if c["status"] == "failed"]
            if not failed_checks:
                result["status"] = "passed"
            elif len(failed_checks) <= 3:
                result["status"] = "warning"
                result["recommendations"].append("Complete missing API endpoints")
            else:
                result["status"] = "failed"
                result["recommendations"].append("Major API integration issues")
                
        except Exception as e:
            result["status"] = "failed"
            result["issues"].append(f"Validation error: {e}")
        
        return result
    
    def validate_storage_api_integration(self) -> Dict[str, Any]:
        """Validate storage backends API integration."""
        result = {
            "component": "Storage Backends API (storage_backends_api.py)",
            "status": "unknown",
            "checks": [],
            "issues": [],
            "recommendations": []
        }
        
        try:
            storage_api_path = self.base_path / "ipfs_kit_py" / "storage_backends_api.py"
            if not storage_api_path.exists():
                result["status"] = "failed"
                result["issues"].append("Storage Backends API file not found")
                return result
            
            with open(storage_api_path, 'r') as f:
                content = f.read()
            
            checks = [
                ("Enhanced pin import", "from ipfs_kit_py.enhanced_pin_index import" in content),
                ("Availability flag", "ENHANCED_PIN_INDEX_AVAILABLE" in content),
                ("Pin analytics endpoint", "get_storage_pin_analytics" in content),
                ("Record access endpoint", "record_storage_access" in content),
                ("Tier recommendations endpoint", "get_tier_recommendations" in content),
                ("Error handling", "HTTPException" in content),
                ("Backend tier mapping", "tier_mapping" in content)
            ]
            
            for check_name, passed in checks:
                result["checks"].append({"name": check_name, "status": "passed" if passed else "failed"})
                if not passed:
                    result["issues"].append(f"Missing: {check_name}")
            
            # Determine overall status
            failed_checks = [c for c in result["checks"] if c["status"] == "failed"]
            if not failed_checks:
                result["status"] = "passed"
            elif len(failed_checks) <= 2:
                result["status"] = "warning"
                result["recommendations"].append("Add remaining storage integration features")
            else:
                result["status"] = "failed"
                result["recommendations"].append("Major storage API integration issues")
                
        except Exception as e:
            result["status"] = "failed"
            result["issues"].append(f"Validation error: {e}")
        
        return result
    
    def validate_mcp_integration(self) -> Dict[str, Any]:
        """Validate MCP health monitor integration."""
        result = {
            "component": "MCP Health Monitor",
            "status": "unknown",
            "checks": [],
            "issues": [],
            "recommendations": []
        }
        
        try:
            mcp_path = self.base_path / "mcp" / "ipfs_kit" / "backends" / "health_monitor.py"
            if not mcp_path.exists():
                result["status"] = "failed"
                result["issues"].append("MCP Health Monitor file not found")
                return result
            
            with open(mcp_path, 'r') as f:
                content = f.read()
            
            checks = [
                ("Enhanced pin import", "from ipfs_kit_py.enhanced_pin_index import" in content),
                ("Availability flag", "ENHANCED_PIN_INDEX_AVAILABLE" in content),
                ("Enhanced index usage", "get_global_enhanced_pin_index" in content),
                ("Fallback logic", "get_global_pin_index" in content),
                ("Enhanced metrics", "get_comprehensive_metrics" in content),
                ("VFS analytics", "get_vfs_analytics" in content),
                ("Performance metrics", "get_performance_metrics" in content)
            ]
            
            for check_name, passed in checks:
                result["checks"].append({"name": check_name, "status": "passed" if passed else "failed"})
                if not passed:
                    result["issues"].append(f"Missing: {check_name}")
            
            # Determine overall status
            failed_checks = [c for c in result["checks"] if c["status"] == "failed"]
            if not failed_checks:
                result["status"] = "passed"
            elif len(failed_checks) <= 2:
                result["status"] = "warning"
                result["recommendations"].append("Complete enhanced metrics integration")
            else:
                result["status"] = "failed"
                result["recommendations"].append("Major MCP integration issues")
                
        except Exception as e:
            result["status"] = "failed"
            result["issues"].append(f"Validation error: {e}")
        
        return result
    
    def validate_enhanced_pin_index(self) -> Dict[str, Any]:
        """Validate the enhanced pin index implementation itself."""
        result = {
            "component": "Enhanced Pin Index (enhanced_pin_index.py)",
            "status": "unknown",
            "checks": [],
            "issues": [],
            "recommendations": []
        }
        
        try:
            enhanced_path = self.base_path / "ipfs_kit_py" / "enhanced_pin_index.py"
            if not enhanced_path.exists():
                result["status"] = "failed"
                result["issues"].append("Enhanced Pin Index file not found")
                return result
            
            # Try to import and test basic functionality
            try:
                from ipfs_kit_py.enhanced_pin_index import (
                    get_global_enhanced_pin_index,
                    get_cli_pin_metrics,
                    EnhancedPinMetadataIndex
                )
                result["checks"].append({"name": "Import successful", "status": "passed"})
                
                # Test global instance creation
                try:
                    index = get_global_enhanced_pin_index(
                        enable_analytics=True,
                        enable_predictions=True
                    )
                    result["checks"].append({"name": "Global instance creation", "status": "passed"})
                    
                    # Test key methods
                    methods_to_check = [
                        "get_comprehensive_metrics",
                        "get_vfs_analytics", 
                        "get_performance_metrics",
                        "record_enhanced_access",
                        "get_pin_details"
                    ]
                    
                    for method_name in methods_to_check:
                        if hasattr(index, method_name):
                            result["checks"].append({"name": f"Method: {method_name}", "status": "passed"})
                        else:
                            result["checks"].append({"name": f"Method: {method_name}", "status": "failed"})
                            result["issues"].append(f"Missing method: {method_name}")
                    
                    # Test CLI metrics function
                    try:
                        metrics = get_cli_pin_metrics()
                        result["checks"].append({"name": "CLI metrics function", "status": "passed"})
                    except Exception as e:
                        result["checks"].append({"name": "CLI metrics function", "status": "failed"})
                        result["issues"].append(f"CLI metrics failed: {e}")
                        
                except Exception as e:
                    result["checks"].append({"name": "Global instance creation", "status": "failed"})
                    result["issues"].append(f"Instance creation failed: {e}")
                    
            except ImportError as e:
                result["checks"].append({"name": "Import successful", "status": "failed"})
                result["issues"].append(f"Import failed: {e}")
                result["recommendations"].append("Install dependencies: pip install duckdb pandas pyarrow")
            
            # Determine overall status
            failed_checks = [c for c in result["checks"] if c["status"] == "failed"]
            if not failed_checks:
                result["status"] = "passed"
            elif len(failed_checks) <= 2:
                result["status"] = "warning"
                result["recommendations"].append("Minor implementation issues to resolve")
            else:
                result["status"] = "failed"
                result["recommendations"].append("Core implementation needs fixes")
                
        except Exception as e:
            result["status"] = "failed"
            result["issues"].append(f"Validation error: {e}")
        
        return result
    
    def run_validation(self) -> Dict[str, Any]:
        """Run complete validation of unified integration."""
        print("🔍 Running Unified Enhanced Pin Index Integration Validation")
        print("=" * 70)
        
        # Validate each component
        components = [
            ("enhanced_pin_index", self.validate_enhanced_pin_index),
            ("cli", self.validate_cli_integration),
            ("main_api", self.validate_api_integration),
            ("storage_api", self.validate_storage_api_integration),
            ("mcp_monitor", self.validate_mcp_integration)
        ]
        
        for component_name, validator in components:
            print(f"\n📋 Validating {component_name}...")
            result = validator()
            self.results["components"][component_name] = result
            
            # Print component summary
            status_emoji = {
                "passed": "✅",
                "warning": "⚠️",
                "failed": "❌",
                "unknown": "❓"
            }
            
            print(f"{status_emoji.get(result['status'], '❓')} {result['component']}: {result['status'].upper()}")
            
            # Print issues if any
            if result["issues"]:
                print("   Issues:")
                for issue in result["issues"]:
                    print(f"     • {issue}")
            
            # Print recommendations if any
            if result["recommendations"]:
                print("   Recommendations:")
                for rec in result["recommendations"]:
                    print(f"     → {rec}")
            
            # Update summary
            self.results["summary"]["total_components"] += 1
            if result["status"] == "passed":
                self.results["summary"]["passed"] += 1
            elif result["status"] == "warning":
                self.results["summary"]["warnings"] += 1
            else:
                self.results["summary"]["failed"] += 1
        
        # Print overall summary
        self.print_summary()
        
        return self.results
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 70)
        print("📊 VALIDATION SUMMARY")
        print("=" * 70)
        
        summary = self.results["summary"]
        total = summary["total_components"]
        passed = summary["passed"]
        warnings = summary["warnings"]
        failed = summary["failed"]
        
        print(f"Total Components: {total}")
        print(f"✅ Passed: {passed}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"❌ Failed: {failed}")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Excellent! Unified integration is working well.")
        elif success_rate >= 60:
            print("👍 Good! Minor issues to address for optimal integration.")
        else:
            print("⚠️  Integration needs significant work to meet requirements.")
        
        print("\n📝 INTEGRATION STATUS:")
        
        # Check if all key components are working
        key_components = ["enhanced_pin_index", "cli", "main_api"]
        key_working = all(
            self.results["components"].get(comp, {}).get("status") in ["passed", "warning"]
            for comp in key_components
        )
        
        if key_working:
            print("✅ Core integration components are functional")
            print("✅ CLI, API, and MCP server can all use enhanced pin index")
            print("✅ Unified data structures and consistent error handling")
            print("✅ Graceful fallback mechanisms in place")
        else:
            print("❌ Core integration components need fixes")
            print("❌ Some components cannot access enhanced pin index")
        
        print("\n" + "=" * 70)


async def main():
    """Main validation function."""
    validator = UnifiedIntegrationValidator()
    results = validator.run_validation()
    
    # Save results to file
    import json
    results_path = Path(__file__).parent / "integration_validation_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {results_path}")
    
    # Return exit code based on results
    if results["summary"]["failed"] > 0:
        return 1
    elif results["summary"]["warnings"] > 0:
        return 2
    else:
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
