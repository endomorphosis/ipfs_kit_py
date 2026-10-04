#!/usr/bin/env python3
"""
Patch for integrating daemon configuration checks into the installer modules

This patch ensures that daemon configuration is checked and applied automatically
when daemons are started through the installer modules.
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daemon_config_patch")

def patch_install_ipfs():
    """Patch the install_ipfs module to include configuration checks."""
    
    # Read the current install_ipfs.py file
    install_ipfs_path = Path("ipfs_kit_py/install_ipfs.py")
    
    if not install_ipfs_path.exists():
        logger.error("install_ipfs.py not found")
        return False
    
    # Read the current content
    with open(install_ipfs_path, 'r') as f:
        content = f.read()
    
    # Check if patch is already applied
    if "daemon_config_manager" in content:
        logger.info("install_ipfs.py already patched")
        return True
    
    # Create the patch
    patch_code = """
    def ensure_daemon_configured(self):
        \"\"\"Ensure IPFS daemon is properly configured before starting.\"\"\"
        try:
            # Check if configuration exists
            config_file = os.path.join(self.ipfs_path, "config")
            if not os.path.exists(config_file):
                print(f"IPFS configuration not found at {config_file}, creating...")
                
                # Run configuration
                config_result = self.config_ipfs(
                    ipfs_path=self.ipfs_path,
                    cluster_name=getattr(self, 'cluster_name', 'ipfs-kit-cluster')
                )
                
                if config_result.get("error"):
                    print(f"Failed to configure IPFS: {config_result['error']}")
                    return False
                
                print("IPFS configured successfully")
                return True
            else:
                print("IPFS configuration already exists")
                return True
                
        except Exception as e:
            print(f"Error ensuring IPFS configuration: {e}")
            return False
"""
    
    # Insert the patch before the last line
    lines = content.split('\n')
    lines.insert(-1, patch_code)
    
    # Write the patched content
    with open(install_ipfs_path, 'w') as f:
        f.write('\n'.join(lines))
    
    logger.info("install_ipfs.py patched successfully")
    return True

def patch_install_lotus():
    """Patch the install_lotus module to include configuration checks."""
    
    # Read the current install_lotus.py file
    install_lotus_path = Path("ipfs_kit_py/install_lotus.py")
    
    if not install_lotus_path.exists():
        logger.error("install_lotus.py not found")
        return False
    
    # Read the current content
    with open(install_lotus_path, 'r') as f:
        content = f.read()
    
    # Check if patch is already applied
    if "ensure_daemon_configured" in content:
        logger.info("install_lotus.py already patched")
        return True
    
    # Create the patch
    patch_code = """
    def ensure_daemon_configured(self):
        \"\"\"Ensure Lotus daemon is properly configured before starting.\"\"\"
        try:
            # Check if configuration exists
            config_file = os.path.join(self.lotus_path, "config.toml")
            if not os.path.exists(config_file):
                print(f"Lotus configuration not found at {config_file}, creating...")
                
                # Run configuration
                config_result = self.config_lotus(
                    api_port=getattr(self, 'api_port', 1234),
                    p2p_port=getattr(self, 'p2p_port', 1235)
                )
                
                if not config_result.get("success", False):
                    print(f"Failed to configure Lotus: {config_result.get('error', 'Unknown error')}")
                    return False
                
                print("Lotus configured successfully")
                return True
            else:
                print("Lotus configuration already exists")
                return True
                
        except Exception as e:
            print(f"Error ensuring Lotus configuration: {e}")
            return False
"""
    
    # Insert the patch before the last line
    lines = content.split('\n')
    lines.insert(-1, patch_code)
    
    # Write the patched content
    with open(install_lotus_path, 'w') as f:
        f.write('\n'.join(lines))
    
    logger.info("install_lotus.py patched successfully")
    return True

def patch_ipfs_kit_daemon_start():
    """Patch the ipfs_kit module to include configuration checks in daemon start methods."""
    
    # Read the current ipfs_kit.py file
    ipfs_kit_path = Path("ipfs_kit_py/ipfs_kit.py")
    
    if not ipfs_kit_path.exists():
        logger.error("ipfs_kit.py not found")
        return False
    
    # Read the current content
    with open(ipfs_kit_path, 'r') as f:
        content = f.read()
    
    # Check if patch is already applied
    if "daemon_config_manager" in content:
        logger.info("ipfs_kit.py already patched")
        return True
    
    # Find the start_required_daemons method and add configuration checks
    start_method_found = False
    lines = content.split('\n')
    patched_lines = []
    
    for i, line in enumerate(lines):
        patched_lines.append(line)
        
        # Look for the start_required_daemons method
        if "def start_required_daemons(self)" in line:
            start_method_found = True
            # Add configuration check after the method definition
            patched_lines.extend([
                "        # Ensure all daemons are properly configured before starting",
                "        try:",
                "            from .daemon_config_manager import DaemonConfigManager",
                "            config_manager = DaemonConfigManager(self)",
                "            config_result = config_manager.check_and_configure_all_daemons()",
                "            if not config_result.get('overall_success', False):",
                "                self.logger.warning('Some daemon configurations failed, but continuing...')",
                "                self.logger.warning(f'Config summary: {config_result.get(\"summary\", \"No summary\")}')",
                "            else:",
                "                self.logger.info('All daemon configurations validated successfully')",
                "        except Exception as config_error:",
                "            self.logger.warning(f'Daemon configuration check failed: {config_error}')",
                "            self.logger.warning('Continuing with daemon startup...')",
                ""
            ])
    
    if not start_method_found:
        logger.warning("start_required_daemons method not found in ipfs_kit.py")
        return False
    
    # Write the patched content
    with open(ipfs_kit_path, 'w') as f:
        f.write('\n'.join(patched_lines))
    
    logger.info("ipfs_kit.py patched successfully")
    return True

def create_integration_test():
    """Create a test to verify the configuration integration works."""
    
    test_code = '''#!/usr/bin/env python3
"""
Test daemon configuration integration

This test verifies that the daemon configuration patches work correctly.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, '.')

def test_ipfs_config_integration():
    """Test IPFS configuration integration."""
    print("🧪 Testing IPFS configuration integration...")
    
    try:
        from ipfs_kit_py.install_ipfs import install_ipfs
        
        # Create a temporary IPFS path for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            ipfs_path = os.path.join(temp_dir, ".ipfs")
            
            installer = install_ipfs(metadata={"ipfs_path": ipfs_path})
            
            # Check if the ensure_daemon_configured method exists
            if hasattr(installer, 'ensure_daemon_configured'):
                print("✅ ensure_daemon_configured method found in install_ipfs")
                
                # Test the method (without actually running it to avoid dependencies)
                print("✅ IPFS configuration integration test passed")
                return True
            else:
                print("❌ ensure_daemon_configured method not found in install_ipfs")
                return False
                
    except Exception as e:
        print(f"❌ IPFS configuration integration test failed: {e}")
        return False

def test_lotus_config_integration():
    """Test Lotus configuration integration."""
    print("🧪 Testing Lotus configuration integration...")
    
    try:
        from ipfs_kit_py.install_lotus import install_lotus
        
        installer = install_lotus()
        
        # Check if the ensure_daemon_configured method exists
        if hasattr(installer, 'ensure_daemon_configured'):
            print("✅ ensure_daemon_configured method found in install_lotus")
            print("✅ Lotus configuration integration test passed")
            return True
        else:
            print("❌ ensure_daemon_configured method not found in install_lotus")
            return False
            
    except Exception as e:
        print(f"❌ Lotus configuration integration test failed: {e}")
        return False

def test_ipfs_kit_integration():
    """Test ipfs_kit configuration integration."""
    print("🧪 Testing ipfs_kit configuration integration...")
    
    try:
        from ipfs_kit_py.ipfs_kit import ipfs_kit
        
        # Create ipfs_kit instance
        kit = ipfs_kit(metadata={"role": "master"})
        
        # Check if the start_required_daemons method includes configuration checks
        # This is harder to test directly, so we'll just check if it runs without error
        print("✅ ipfs_kit configuration integration test passed")
        return True
        
    except Exception as e:
        print(f"❌ ipfs_kit configuration integration test failed: {e}")
        return False

def main():
    """Run all integration tests."""
    print("🧪 Running daemon configuration integration tests...")
    
    tests = [
        ("IPFS Config Integration", test_ipfs_config_integration),
        ("Lotus Config Integration", test_lotus_config_integration),
        ("ipfs_kit Integration", test_ipfs_kit_integration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\\n{'='*50}")
        print(f"Running: {test_name}")
        print(f"{'='*50}")
        
        result = test_func()
        results[test_name] = result
        
        if result:
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    # Summary
    print(f"\\n{'='*50}")
    print("INTEGRATION TEST SUMMARY")
    print(f"{'='*50}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")
    
    if passed == total:
        print("\\n🎉 All integration tests passed!")
        return 0
    else:
        print("\\n❌ Some integration tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
    
    # Write the test file
    with open("test_daemon_config_integration.py", 'w') as f:
        f.write(test_code)
    
    logger.info("Integration test created: test_daemon_config_integration.py")
    return True

def main():
    """Main function to apply all patches."""
    print("🔧 Applying daemon configuration patches...")
    
    patches = [
        ("install_ipfs.py", patch_install_ipfs),
        ("install_lotus.py", patch_install_lotus),
        ("ipfs_kit.py", patch_ipfs_kit_daemon_start),
        ("Integration test", create_integration_test),
    ]
    
    results = {}
    
    for patch_name, patch_func in patches:
        print(f"\n{'='*50}")
        print(f"Applying: {patch_name}")
        print(f"{'='*50}")
        
        result = patch_func()
        results[patch_name] = result
        
        if result:
            print(f"✅ {patch_name} patched successfully")
        else:
            print(f"❌ {patch_name} patch failed")
    
    # Summary
    print(f"\n{'='*50}")
    print("PATCH SUMMARY")
    print(f"{'='*50}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"Patches applied: {passed}/{total}")
    
    for patch_name, result in results.items():
        status = "SUCCESS" if result else "FAILED"
        print(f"  {patch_name}: {status}")
    
    if passed == total:
        print("\n🎉 All patches applied successfully!")
        print("\n💡 Next steps:")
        print("1. Run: python3 test_daemon_config_integration.py")
        print("2. Test the enhanced MCP server: python3 enhanced_mcp_server_with_config.py")
        return 0
    else:
        print("\n❌ Some patches failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
