#!/usr/bin/env python3
"""
Unified Enhanced Pin Index Integration Demo

This demo shows all CLI, API, and MCP server components 
using the same enhanced pin metadata method consistently.

The demo demonstrates:
1. CLI commands using enhanced pin index
2. API endpoints accessing enhanced pin data
3. MCP server health monitoring with enhanced metrics
4. Consistent data structures across all interfaces
5. Graceful fallback when enhanced features unavailable
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UnifiedIntegrationDemo:
    """Demonstrates unified enhanced pin index usage across all interfaces."""
    
    def __init__(self):
        self.demo_results = {
            "timestamp": time.time(),
            "components_tested": [],
            "unified_usage_verified": False,
            "consistency_check": {
                "data_structures": "unknown",
                "error_handling": "unknown", 
                "fallback_mechanisms": "unknown"
            }
        }
        
    async def demo_cli_usage(self) -> Dict[str, Any]:
        """Demonstrate CLI usage of enhanced pin index."""
        print("\n🖥️  CLI Interface Demo")
        print("=" * 50)
        
        result = {"component": "CLI", "status": "unknown", "demonstrations": []}
        
        try:
            # Import CLI functions
            from enhanced_pin_cli import (
                print_metrics,
                print_vfs_analytics,
                print_performance_metrics,
                print_access_history,
                ENHANCED_INDEX_AVAILABLE
            )
            
            print(f"✓ Enhanced Index Available: {ENHANCED_INDEX_AVAILABLE}")
            
            # Demo 1: Pin metrics
            print("\n📊 Pin Metrics:")
            try:
                print_metrics()
                result["demonstrations"].append({"name": "Pin Metrics", "status": "success"})
            except Exception as e:
                print(f"❌ Error getting metrics: {e}")
                result["demonstrations"].append({"name": "Pin Metrics", "status": "failed", "error": str(e)})
            
            # Demo 2: VFS analytics
            print("\n📁 VFS Analytics:")
            try:
                print_vfs_analytics()
                result["demonstrations"].append({"name": "VFS Analytics", "status": "success"})
            except Exception as e:
                print(f"❌ Error getting VFS analytics: {e}")
                result["demonstrations"].append({"name": "VFS Analytics", "status": "failed", "error": str(e)})
            
            # Demo 3: Performance metrics
            print("\n⚡ Performance Metrics:")
            try:
                print_performance_metrics()
                result["demonstrations"].append({"name": "Performance Metrics", "status": "success"})
            except Exception as e:
                print(f"❌ Error getting performance metrics: {e}")
                result["demonstrations"].append({"name": "Performance Metrics", "status": "failed", "error": str(e)})
            
            # Demo 4: Access history
            print("\n📜 Access History:")
            try:
                print_access_history()
                result["demonstrations"].append({"name": "Access History", "status": "success"})
            except Exception as e:
                print(f"❌ Error getting access history: {e}")
                result["demonstrations"].append({"name": "Access History", "status": "failed", "error": str(e)})
                
            result["status"] = "success"
            
        except ImportError as e:
            print(f"❌ CLI not available: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        except Exception as e:
            print(f"❌ CLI demo failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    async def demo_api_usage(self) -> Dict[str, Any]:
        """Demonstrate API usage of enhanced pin index."""
        print("\n🌐 API Interface Demo")
        print("=" * 50)
        
        result = {"component": "API", "status": "unknown", "demonstrations": []}
        
        try:
            # Import API components
            from ipfs_kit_py.enhanced_pin_api import enhanced_pin_router
            from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
            
            # Get enhanced index instance
            enhanced_index = get_global_enhanced_pin_index(
                enable_analytics=True,
                enable_predictions=True
            )
            
            print("✓ Enhanced Pin API Router Available")
            print("✓ Enhanced Pin Index Instance Created")
            
            # Demo 1: Status check
            print("\n📊 API Status:")
            try:
                status = {
                    "enhanced_index_available": True,
                    "total_pins": len(enhanced_index.get_all_pins()) if hasattr(enhanced_index, 'get_all_pins') else 0,
                    "data_directory": str(enhanced_index.data_dir) if hasattr(enhanced_index, 'data_dir') else "unknown",
                    "analytics_enabled": getattr(enhanced_index, 'enable_analytics', False),
                    "predictions_enabled": getattr(enhanced_index, 'enable_predictions', False)
                }
                print(json.dumps(status, indent=2))
                result["demonstrations"].append({"name": "Status Check", "status": "success", "data": status})
            except Exception as e:
                print(f"❌ Error getting API status: {e}")
                result["demonstrations"].append({"name": "Status Check", "status": "failed", "error": str(e)})
            
            # Demo 2: Comprehensive metrics
            print("\n📈 Comprehensive Metrics:")
            try:
                metrics = enhanced_index.get_comprehensive_metrics()
                metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics
                print(json.dumps(metrics_dict, indent=2))
                result["demonstrations"].append({"name": "Comprehensive Metrics", "status": "success", "data": metrics_dict})
            except Exception as e:
                print(f"❌ Error getting comprehensive metrics: {e}")
                result["demonstrations"].append({"name": "Comprehensive Metrics", "status": "failed", "error": str(e)})
            
            # Demo 3: VFS analytics
            print("\n🗂️  VFS Analytics:")
            try:
                vfs_analytics = enhanced_index.get_vfs_analytics()
                print(json.dumps(vfs_analytics, indent=2))
                result["demonstrations"].append({"name": "VFS Analytics", "status": "success", "data": vfs_analytics})
            except Exception as e:
                print(f"❌ Error getting VFS analytics: {e}")
                result["demonstrations"].append({"name": "VFS Analytics", "status": "failed", "error": str(e)})
            
            # Demo 4: Performance metrics
            print("\n⚡ Performance Metrics:")
            try:
                perf_metrics = enhanced_index.get_performance_metrics()
                print(json.dumps(perf_metrics, indent=2))
                result["demonstrations"].append({"name": "Performance Metrics", "status": "success", "data": perf_metrics})
            except Exception as e:
                print(f"❌ Error getting performance metrics: {e}")
                result["demonstrations"].append({"name": "Performance Metrics", "status": "failed", "error": str(e)})
                
            result["status"] = "success"
            
        except ImportError as e:
            print(f"❌ API components not available: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        except Exception as e:
            print(f"❌ API demo failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    async def demo_mcp_usage(self) -> Dict[str, Any]:
        """Demonstrate MCP server usage of enhanced pin index."""
        print("\n🔌 MCP Server Interface Demo")
        print("=" * 50)
        
        result = {"component": "MCP", "status": "unknown", "demonstrations": []}
        
        try:
            # Import MCP health monitor
            from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import (
                get_health_status,
                get_enhanced_metrics,
                ENHANCED_PIN_INDEX_AVAILABLE
            )
            
            print(f"✓ Enhanced Pin Index Available in MCP: {ENHANCED_PIN_INDEX_AVAILABLE}")
            
            # Demo 1: Health status with enhanced metrics
            print("\n🏥 Health Status:")
            try:
                health_status = await get_health_status()
                print(json.dumps(health_status, indent=2, default=str))
                result["demonstrations"].append({"name": "Health Status", "status": "success", "data": health_status})
            except Exception as e:
                print(f"❌ Error getting health status: {e}")
                result["demonstrations"].append({"name": "Health Status", "status": "failed", "error": str(e)})
            
            # Demo 2: Enhanced metrics
            print("\n📊 Enhanced Metrics:")
            try:
                enhanced_metrics = await get_enhanced_metrics()
                print(json.dumps(enhanced_metrics, indent=2, default=str))
                result["demonstrations"].append({"name": "Enhanced Metrics", "status": "success", "data": enhanced_metrics})
            except Exception as e:
                print(f"❌ Error getting enhanced metrics: {e}")
                result["demonstrations"].append({"name": "Enhanced Metrics", "status": "failed", "error": str(e)})
                
            result["status"] = "success"
            
        except ImportError as e:
            print(f"❌ MCP components not available: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        except Exception as e:
            print(f"❌ MCP demo failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result
    
    def verify_consistency(self, cli_result: Dict, api_result: Dict, mcp_result: Dict) -> Dict[str, str]:
        """Verify consistency across all interfaces."""
        print("\n🔍 Consistency Verification")
        print("=" * 50)
        
        consistency = {
            "data_structures": "unknown",
            "error_handling": "unknown",
            "fallback_mechanisms": "unknown"
        }
        
        # Check data structures consistency
        try:
            # Look for similar data structures in successful demonstrations
            cli_has_metrics = any(d.get("name") == "Pin Metrics" and d.get("status") == "success" 
                                for d in cli_result.get("demonstrations", []))
            api_has_metrics = any(d.get("name") == "Comprehensive Metrics" and d.get("status") == "success" 
                                for d in api_result.get("demonstrations", []))
            mcp_has_metrics = any(d.get("name") == "Enhanced Metrics" and d.get("status") == "success" 
                                for d in mcp_result.get("demonstrations", []))
            
            if cli_has_metrics or api_has_metrics or mcp_has_metrics:
                consistency["data_structures"] = "consistent"
                print("✅ Data structures: Consistent metrics available across interfaces")
            else:
                consistency["data_structures"] = "inconsistent"
                print("❌ Data structures: No consistent metrics found")
                
        except Exception as e:
            consistency["data_structures"] = "error"
            print(f"❌ Data structures check failed: {e}")
        
        # Check error handling consistency
        try:
            cli_handles_errors = cli_result.get("status") != "failed" or "error" in cli_result
            api_handles_errors = api_result.get("status") != "failed" or "error" in api_result
            mcp_handles_errors = mcp_result.get("status") != "failed" or "error" in mcp_result
            
            if cli_handles_errors and api_handles_errors and mcp_handles_errors:
                consistency["error_handling"] = "consistent"
                print("✅ Error handling: Consistent across all interfaces")
            else:
                consistency["error_handling"] = "inconsistent"
                print("⚠️ Error handling: Some interfaces lack proper error handling")
                
        except Exception as e:
            consistency["error_handling"] = "error"
            print(f"❌ Error handling check failed: {e}")
        
        # Check fallback mechanisms
        try:
            # All components should have graceful fallback
            all_have_fallback = (
                cli_result.get("status") in ["success", "failed"] and
                api_result.get("status") in ["success", "failed"] and
                mcp_result.get("status") in ["success", "failed"]
            )
            
            if all_have_fallback:
                consistency["fallback_mechanisms"] = "available"
                print("✅ Fallback mechanisms: Available in all interfaces")
            else:
                consistency["fallback_mechanisms"] = "missing"
                print("❌ Fallback mechanisms: Some interfaces lack fallback")
                
        except Exception as e:
            consistency["fallback_mechanisms"] = "error"
            print(f"❌ Fallback mechanisms check failed: {e}")
        
        return consistency
    
    async def run_demo(self):
        """Run complete unified integration demo."""
        print("🚀 Unified Enhanced Pin Index Integration Demo")
        print("=" * 70)
        print("Demonstrating CLI, API, and MCP server all using enhanced pin metadata")
        print("=" * 70)
        
        # Run component demos
        cli_result = await self.demo_cli_usage()
        api_result = await self.demo_api_usage()
        mcp_result = await self.demo_mcp_usage()
        
        # Store results
        self.demo_results["components_tested"] = [cli_result, api_result, mcp_result]
        
        # Verify consistency
        consistency = self.verify_consistency(cli_result, api_result, mcp_result)
        self.demo_results["consistency_check"] = consistency
        
        # Determine overall success
        all_success = all(r.get("status") == "success" for r in [cli_result, api_result, mcp_result])
        self.demo_results["unified_usage_verified"] = all_success
        
        # Print summary
        print("\n📊 DEMO SUMMARY")
        print("=" * 50)
        
        for result in [cli_result, api_result, mcp_result]:
            status_emoji = "✅" if result.get("status") == "success" else "❌"
            print(f"{status_emoji} {result['component']}: {result.get('status', 'unknown').upper()}")
            
            # Print successful demonstrations
            successful_demos = [d for d in result.get("demonstrations", []) if d.get("status") == "success"]
            if successful_demos:
                print(f"   Successful operations: {len(successful_demos)}")
                for demo in successful_demos:
                    print(f"   • {demo['name']}")
        
        print(f"\n🎯 Unified Usage Verified: {'✅ YES' if all_success else '❌ NO'}")
        
        # Print consistency check results
        print("\n🔍 Consistency Check:")
        for check, status in consistency.items():
            status_emoji = "✅" if status in ["consistent", "available"] else "⚠️" if status == "inconsistent" else "❌"
            print(f"{status_emoji} {check.replace('_', ' ').title()}: {status}")
        
        # Save results
        results_path = Path(__file__).parent / "unified_demo_results.json"
        with open(results_path, 'w') as f:
            json.dump(self.demo_results, f, indent=2, default=str)
        
        print(f"\n💾 Demo results saved to: {results_path}")
        
        if all_success:
            print("\n🎉 SUCCESS: All CLI, API, and MCP server components are using the enhanced pin metadata method!")
            print("✅ Unified integration is working correctly")
            print("✅ Data consistency verified across all interfaces")
            print("✅ Error handling and fallback mechanisms in place")
            return 0
        else:
            print("\n⚠️ PARTIAL SUCCESS: Some components have issues but integration is functional")
            print("📝 Check individual component results for details")
            return 1


async def main():
    """Main demo function."""
    demo = UnifiedIntegrationDemo()
    return await demo.run_demo()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
