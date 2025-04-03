#!/usr/bin/env python3
"""
Comprehensive Testing Script for ipfs_kit_py

This script tests key components of the ipfs_kit_py library
with detailed error reporting to help diagnose issues.
"""

import os
import sys
import json
import time
import traceback
import importlib
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Configure basic logging
import logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ipfs_kit_tester")

def section_header(title):
    """Print a section header for better readability."""
    line = "=" * 80
    print(f"\n{line}\n{title.center(80)}\n{line}\n")

def test_component(component_name, function, *args, **kwargs):
    """Test a specific component and report results."""
    print(f"\n--- Testing {component_name} ---")
    start_time = time.time()
    try:
        result = function(*args, **kwargs)
        duration = time.time() - start_time
        print(f"✅ SUCCESS ({duration:.2f}s)")
        return result
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ ERROR ({duration:.2f}s): {str(e)}")
        traceback.print_exc()
        return None
    
def main():
    """Run the comprehensive test suite."""
    section_header("IPFS Kit Python Comprehensive Test")
    
    results = {
        "timestamp": time.time(),
        "success": False,
        "components_tested": 0,
        "components_passed": 0,
        "details": {}
    }
    
    # Test 1: Import Core Libraries
    section_header("Testing Core Imports")
    
    # Track components for testing
    components = {}
    
    # Test importing ipfs_kit
    try:
        from ipfs_kit_py import ipfs_kit
        components["ipfs_kit"] = ipfs_kit
        print("✅ Successfully imported ipfs_kit")
        results["details"]["import_ipfs_kit"] = {"success": True}
    except Exception as e:
        print(f"❌ Error importing ipfs_kit: {e}")
        traceback.print_exc()
        results["details"]["import_ipfs_kit"] = {"success": False, "error": str(e)}
        
    # Test importing high_level_api (most recent feature)
    try:
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        components["IPFSSimpleAPI"] = IPFSSimpleAPI
        print("✅ Successfully imported IPFSSimpleAPI")
        results["details"]["import_high_level_api"] = {"success": True}
    except Exception as e:
        print(f"❌ Error importing IPFSSimpleAPI: {e}")
        traceback.print_exc()
        results["details"]["import_high_level_api"] = {"success": False, "error": str(e)}
        
    # Test importing AI/ML integration
    try:
        from ipfs_kit_py import ai_ml_integration
        components["ai_ml_integration"] = ai_ml_integration
        print("✅ Successfully imported ai_ml_integration")
        results["details"]["import_ai_ml_integration"] = {"success": True}
    except Exception as e:
        print(f"❌ Error importing ai_ml_integration: {e}")
        traceback.print_exc()
        results["details"]["import_ai_ml_integration"] = {"success": False, "error": str(e)}
        
    # Test 2: Initialize Basic Components
    section_header("Testing Component Initialization")
    
    # Initialize ipfs_kit
    try:
        kit = components["ipfs_kit"](metadata={"role": "leecher"})
        print(f"✅ Successfully initialized ipfs_kit with role: leecher")
        results["details"]["init_ipfs_kit"] = {"success": True}
        
        # Test IPFSSimpleAPI initialization if available
        if "IPFSSimpleAPI" in components:
            try:
                api = components["IPFSSimpleAPI"]()
                print(f"✅ Successfully initialized IPFSSimpleAPI with role: {api.config.get('role', 'unknown')}")
                results["details"]["init_high_level_api"] = {"success": True}
            except Exception as e:
                print(f"❌ Error initializing IPFSSimpleAPI: {e}")
                traceback.print_exc()
                results["details"]["init_high_level_api"] = {"success": False, "error": str(e)}
    except Exception as e:
        print(f"❌ Error initializing ipfs_kit: {e}")
        traceback.print_exc()
        results["details"]["init_ipfs_kit"] = {"success": False, "error": str(e)}
        
    # Test 3: Basic IPFS Operations
    section_header("Testing Basic IPFS Operations")
    try:
        # Check if IPFS service is running
        ready_result = kit.ipfs_kit_ready()
        print(f"IPFS Ready Result: {ready_result}")
        results["details"]["ipfs_ready"] = ready_result
        
        if ready_result.get("ipfs_ready", False):
            # Test adding content
            test_content = b"Test content for IPFS Kit comprehensive testing"
            add_result = kit.ipfs.ipfs_add(test_content)
            print(f"Add Result: {add_result}")
            results["details"]["ipfs_add"] = add_result
            
            if add_result.get("success", False):
                cid = add_result.get("cid")
                
                # Test retrieving content
                get_result = kit.ipfs.ipfs_cat(cid)
                print(f"Get Result: {get_result[:100]}...")  # Show first 100 bytes
                results["details"]["ipfs_cat"] = {"success": True, "content_match": get_result == test_content}
                
                # Test pinning content
                pin_result = kit.ipfs.ipfs_pin_add(cid)
                print(f"Pin Result: {pin_result}")
                results["details"]["ipfs_pin"] = pin_result
                
                # Test listing pins
                pin_ls_result = kit.ipfs.ipfs_pin_ls()
                print(f"Pin List Result: {pin_ls_result}")
                results["details"]["ipfs_pin_ls"] = pin_ls_result
                
                # Test unpinning content
                unpin_result = kit.ipfs.ipfs_pin_rm(cid)
                print(f"Unpin Result: {unpin_result}")
                results["details"]["ipfs_unpin"] = unpin_result
        else:
            print("❌ IPFS service is not running, skipping basic operations tests")
    except Exception as e:
        print(f"❌ Error during basic IPFS operations: {e}")
        traceback.print_exc()
        results["details"]["basic_operations"] = {"success": False, "error": str(e)}
        
    # Test 4: High-Level API (if available)
    if "IPFSSimpleAPI" in components and "init_high_level_api" in results["details"] and results["details"]["init_high_level_api"].get("success", False):
        section_header("Testing High-Level API")
        try:
            api = components["IPFSSimpleAPI"]()
            
            # Test adding content
            test_content = b"Test content for High-Level API testing"
            add_result = test_component("api.add", api.add, test_content)
            results["details"]["high_level_add"] = add_result
            
            if add_result and add_result.get("success", False):
                cid = add_result.get("cid")
                
                # Test retrieving content
                get_result = test_component("api.get", api.get, cid)
                results["details"]["high_level_get"] = {"success": True if get_result else False}
                
                # Test pinning content
                pin_result = test_component("api.pin", api.pin, cid)
                results["details"]["high_level_pin"] = pin_result
                
                # Test listing pins
                pins_result = test_component("api.list_pins", api.list_pins)
                results["details"]["high_level_list_pins"] = pins_result
                
                # Test unpinning content
                unpin_result = test_component("api.unpin", api.unpin, cid)
                results["details"]["high_level_unpin"] = unpin_result
                
            # Test configuration handling
            save_config_result = test_component("api.save_config", api.save_config, "/tmp/test_config.yaml")
            results["details"]["high_level_save_config"] = save_config_result
            
        except Exception as e:
            print(f"❌ Error during High-Level API testing: {e}")
            traceback.print_exc()
            results["details"]["high_level_api_tests"] = {"success": False, "error": str(e)}
        
    # Test 5: AI/ML Integration (if available)
    if "ai_ml_integration" in components:
        section_header("Testing AI/ML Integration")
        try:
            # Check if ModelRegistry is available
            if hasattr(components["ai_ml_integration"], "ModelRegistry"):
                print("✅ ModelRegistry component is available")
                results["details"]["ai_ml_model_registry"] = {"success": True}
            else:
                print("❌ ModelRegistry component is not available")
                results["details"]["ai_ml_model_registry"] = {"success": False}
                
            # Check if DatasetManager is available
            if hasattr(components["ai_ml_integration"], "DatasetManager"):
                print("✅ DatasetManager component is available")
                results["details"]["ai_ml_dataset_manager"] = {"success": True}
            else:
                print("❌ DatasetManager component is not available")
                results["details"]["ai_ml_dataset_manager"] = {"success": False}
                
            # Check if LangchainIntegration is available
            if hasattr(components["ai_ml_integration"], "LangchainIntegration"):
                print("✅ LangchainIntegration component is available")
                results["details"]["ai_ml_langchain"] = {"success": True}
            else:
                print("❌ LangchainIntegration component is not available")
                results["details"]["ai_ml_langchain"] = {"success": False}
                
            # Check if LlamaIndexIntegration is available
            if hasattr(components["ai_ml_integration"], "LlamaIndexIntegration"):
                print("✅ LlamaIndexIntegration component is available")
                results["details"]["ai_ml_llamaindex"] = {"success": True}
            else:
                print("❌ LlamaIndexIntegration component is not available")
                results["details"]["ai_ml_llamaindex"] = {"success": False}
                
            # Check if DistributedTraining is available
            if hasattr(components["ai_ml_integration"], "DistributedTraining"):
                print("✅ DistributedTraining component is available")
                results["details"]["ai_ml_distributed_training"] = {"success": True}
            else:
                print("❌ DistributedTraining component is not available")
                results["details"]["ai_ml_distributed_training"] = {"success": False}
                
        except Exception as e:
            print(f"❌ Error during AI/ML Integration testing: {e}")
            traceback.print_exc()
            results["details"]["ai_ml_integration_tests"] = {"success": False, "error": str(e)}
            
    # Calculate overall results
    components_tested = len(results["details"])
    components_passed = sum(1 for detail in results["details"].values() 
                          if isinstance(detail, dict) and detail.get("success", False))
    
    results["components_tested"] = components_tested
    results["components_passed"] = components_passed
    results["success"] = components_passed > 0 and components_passed == components_tested
    
    # Final summary
    section_header("Testing Summary")
    print(f"Components Tested: {components_tested}")
    print(f"Components Passed: {components_passed}")
    print(f"Overall Success: {'✅ Yes' if results['success'] else '❌ No'}")
    
    # Write results to file
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results written to test_results.json")
    
    return results

if __name__ == "__main__":
    main()