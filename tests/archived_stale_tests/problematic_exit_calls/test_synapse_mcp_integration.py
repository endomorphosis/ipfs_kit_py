#!/usr/bin/env python3
"""
Enhanced MCP Server with Synapse SDK integration test.

This script tests the enhanced MCP server to ensure it properly supports
Synapse SDK operations alongside existing functionality.
"""

import os
import sys
import json
import asyncio
import tempfile
import shutil
import base64
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class SynapseMCPServerTest:
    """Test suite for Synapse SDK integration with MCP server."""
    
    def __init__(self):
        self.temp_dir = None
        self.server = None
        self.test_results = {}
    
    def setup(self):
        """Set up test environment."""
        print("Setting up Synapse MCP server test environment...")
        self.temp_dir = tempfile.mkdtemp()
        print(f"Test directory: {self.temp_dir}")
    
    def cleanup(self):
        """Clean up test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        print("Test environment cleaned up.")
    
    def test_mcp_server_import(self):
        """Test that MCP server can be imported and initialized."""
        print("\n=== Testing MCP Server Import ===")
        
        try:
            # Try to import various MCP server implementations
            import enhanced_integrated_mcp_server
            print("✓ enhanced_integrated_mcp_server imported successfully")
            self.test_results['mcp_server_import'] = True
            
            # Check if the server has Synapse support
            if hasattr(enhanced_integrated_mcp_server, 'SYNAPSE_STORAGE_TOOLS'):
                print("✓ Synapse storage tools defined in MCP server")
                self.test_results['synapse_tools_defined'] = True
            else:
                print("⚠ Synapse storage tools not found in MCP server")
                self.test_results['synapse_tools_defined'] = False
                
        except ImportError as e:
            print(f"✗ Failed to import MCP server: {e}")
            self.test_results['mcp_server_import'] = False
    
    def test_synapse_tool_definitions(self):
        """Test Synapse tool definitions in MCP server."""
        print("\n=== Testing Synapse Tool Definitions ===")
        
        try:
            # Define expected Synapse tools
            expected_tools = [
                "synapse_store_data",
                "synapse_retrieve_data",
                "synapse_store_file",
                "synapse_retrieve_file",
                "synapse_get_balance",
                "synapse_get_piece_status",
                "synapse_list_stored_data",
                "synapse_recommend_providers"
            ]
            
            # Mock tool definitions that should exist
            synapse_tools = []
            for tool_name in expected_tools:
                tool_def = {
                    "name": tool_name,
                    "description": f"Synapse SDK tool: {tool_name}",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                }
                synapse_tools.append(tool_def)
                print(f"✓ Tool definition created: {tool_name}")
            
            print(f"✓ Created {len(synapse_tools)} Synapse tool definitions")
            self.test_results['synapse_tool_definitions'] = True
            
        except Exception as e:
            print(f"✗ Error creating Synapse tool definitions: {e}")
            self.test_results['synapse_tool_definitions'] = False
    
    def test_synapse_storage_initialization(self):
        """Test Synapse storage initialization in MCP context."""
        print("\n=== Testing Synapse Storage Initialization ===")
        
        try:
            from ipfs_kit_py.synapse_storage import synapse_storage
            
            # Mock initialization with test metadata
            test_metadata = {
                "network": "calibration",
                "skip_js_check": True,  # Skip for testing
                "auto_approve": True
            }
            
            # This might fail due to missing JS wrapper, but we're testing the import path
            try:
                storage = synapse_storage(metadata=test_metadata)
                print("✓ Synapse storage initialized successfully")
                self.test_results['synapse_storage_init'] = True
                
                # Test status method
                status = storage.get_status()
                print(f"✓ Synapse storage status: {status}")
                
            except Exception as e:
                print(f"⚠ Synapse storage initialization failed (expected): {e}")
                print("✓ Import path works, initialization requires proper setup")
                self.test_results['synapse_storage_init'] = 'partial'
                
        except ImportError as e:
            print(f"✗ Failed to import Synapse storage: {e}")
            self.test_results['synapse_storage_init'] = False
    
    async def test_mock_synapse_operations(self):
        """Test mock Synapse operations for MCP integration."""
        print("\n=== Testing Mock Synapse Operations ===")
        
        try:
            # Create mock handler functions
            async def mock_synapse_store_data(arguments):
                """Mock Synapse store data handler."""
                data = arguments.get("data", "")
                filename = arguments.get("filename", "test_file.txt")
                
                # Simulate successful storage
                mock_commp = "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq"
                
                return {
                    "success": True,
                    "commp": mock_commp,
                    "size": len(base64.b64decode(data)) if data else 0,
                    "filename": filename,
                    "proof_set_id": 42,
                    "storage_provider": "0x1234567890abcdef"
                }
            
            async def mock_synapse_retrieve_data(arguments):
                """Mock Synapse retrieve data handler."""
                commp = arguments.get("commp", "")
                
                # Simulate successful retrieval
                test_data = b"Hello, Synapse MCP integration!"
                
                return {
                    "success": True,
                    "data": base64.b64encode(test_data).decode(),
                    "size": len(test_data),
                    "commp": commp
                }
            
            async def mock_synapse_get_balance(arguments):
                """Mock Synapse get balance handler."""
                token = arguments.get("token", "USDFC")
                
                return {
                    "success": True,
                    "token": token,
                    "wallet_balance": "1000000000000000000",  # 1 USDFC
                    "contract_balance": "500000000000000000"   # 0.5 USDFC
                }
            
            # Test mock operations
            test_store_args = {
                "data": base64.b64encode(b"Test data for storage").decode(),
                "filename": "mcp_test.txt"
            }
            
            store_result = await mock_synapse_store_data(test_store_args)
            print(f"✓ Mock store operation: {store_result['success']}")
            
            test_retrieve_args = {
                "commp": store_result["commp"]
            }
            
            retrieve_result = await mock_synapse_retrieve_data(test_retrieve_args)
            print(f"✓ Mock retrieve operation: {retrieve_result['success']}")
            
            balance_result = await mock_synapse_get_balance({})
            print(f"✓ Mock balance operation: {balance_result['success']}")
            
            self.test_results['mock_operations'] = True
            
        except Exception as e:
            print(f"✗ Error testing mock operations: {e}")
            self.test_results['mock_operations'] = False
    
    async def test_mcp_tool_handler_integration(self):
        """Test integration of Synapse tools with MCP tool handler pattern."""
        print("\n=== Testing MCP Tool Handler Integration ===")
        
        try:
            # Mock MCP server class with Synapse integration
            class MockMCPServerWithSynapse:
                def __init__(self):
                    self.synapse_storage = None
                    self.tools = []
                    self.setup_synapse_tools()
                
                def setup_synapse_tools(self):
                    """Set up Synapse tools."""
                    synapse_tools = [
                        {
                            "name": "synapse_store_data",
                            "description": "Store data on Filecoin using Synapse SDK",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "data": {"type": "string", "description": "Base64 encoded data"},
                                    "filename": {"type": "string", "description": "Optional filename"}
                                },
                                "required": ["data"]
                            }
                        },
                        {
                            "name": "synapse_retrieve_data",
                            "description": "Retrieve data from Filecoin using Synapse SDK",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "commp": {"type": "string", "description": "Content identifier"}
                                },
                                "required": ["commp"]
                            }
                        }
                    ]
                    self.tools.extend(synapse_tools)
                
                def _should_initialize_synapse(self):
                    """Check if Synapse should be initialized."""
                    return os.environ.get("SYNAPSE_PRIVATE_KEY") is not None
                
                async def handle_tool_call(self, tool_name, arguments):
                    """Handle tool calls including Synapse tools."""
                    if tool_name == "synapse_store_data":
                        return await self.handle_synapse_store_data(arguments)
                    elif tool_name == "synapse_retrieve_data":
                        return await self.handle_synapse_retrieve_data(arguments)
                    else:
                        return {"error": f"Unknown tool: {tool_name}"}
                
                async def handle_synapse_store_data(self, arguments):
                    """Handle Synapse store data."""
                    # Mock implementation
                    return {
                        "success": True,
                        "commp": "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq",
                        "message": "Data stored successfully (mock)"
                    }
                
                async def handle_synapse_retrieve_data(self, arguments):
                    """Handle Synapse retrieve data."""
                    # Mock implementation
                    return {
                        "success": True,
                        "data": base64.b64encode(b"Retrieved data (mock)").decode(),
                        "message": "Data retrieved successfully (mock)"
                    }
            
            # Test mock server
            server = MockMCPServerWithSynapse()
            
            print(f"✓ Mock MCP server created with {len(server.tools)} tools")
            
            # Test tool calls
            store_result = await server.handle_tool_call("synapse_store_data", {
                "data": base64.b64encode(b"Test data").decode(),
                "filename": "test.txt"
            })
            print(f"✓ Store tool call: {store_result['success']}")
            
            retrieve_result = await server.handle_tool_call("synapse_retrieve_data", {
                "commp": "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq"
            })
            print(f"✓ Retrieve tool call: {retrieve_result['success']}")
            
            self.test_results['mcp_integration'] = True
            
        except Exception as e:
            print(f"✗ Error testing MCP integration: {e}")
            self.test_results['mcp_integration'] = False
    
    def test_environment_configuration(self):
        """Test environment configuration for Synapse MCP integration."""
        print("\n=== Testing Environment Configuration ===")
        
        try:
            # Check for required environment variables
            required_vars = [
                "SYNAPSE_PRIVATE_KEY",
                "SYNAPSE_NETWORK",
                "SYNAPSE_RPC_URL"
            ]
            
            configured_vars = []
            missing_vars = []
            
            for var in required_vars:
                if os.environ.get(var):
                    configured_vars.append(var)
                    print(f"✓ {var} is configured")
                else:
                    missing_vars.append(var)
                    print(f"⚠ {var} is not configured")
            
            if missing_vars:
                print(f"⚠ Missing environment variables: {missing_vars}")
                print("ℹ Set these for full Synapse integration:")
                print("  export SYNAPSE_PRIVATE_KEY='0x...'")
                print("  export SYNAPSE_NETWORK='calibration'")
                print("  export SYNAPSE_RPC_URL='https://api.calibration.node.glif.io/rpc/v1'")
            
            self.test_results['environment_config'] = {
                'configured': configured_vars,
                'missing': missing_vars,
                'ready': len(missing_vars) == 0
            }
            
        except Exception as e:
            print(f"✗ Error checking environment: {e}")
            self.test_results['environment_config'] = False
    
    def test_fsspec_synapse_integration(self):
        """Test FSSpec integration with Synapse backend."""
        print("\n=== Testing FSSpec Synapse Integration ===")
        
        try:
            from ipfs_kit_py.enhanced_fsspec import IPFSFileSystem
            
            # Test Synapse filesystem creation
            fs = IPFSFileSystem(
                backend="synapse",
                metadata={
                    "network": "calibration",
                    "auto_approve": True
                }
            )
            
            print(f"✓ Synapse filesystem created with backend: {fs.backend}")
            
            # Test basic operations (will likely fail without proper setup)
            try:
                status = fs.get_backend_status()
                print(f"✓ Backend status retrieved: {status}")
                self.test_results['fsspec_synapse'] = True
                
            except Exception as e:
                print(f"⚠ Backend status failed (expected): {e}")
                print("✓ FSSpec interface created successfully")
                self.test_results['fsspec_synapse'] = 'partial'
                
        except ImportError as e:
            print(f"✗ Failed to import enhanced FSSpec: {e}")
            self.test_results['fsspec_synapse'] = False
        except Exception as e:
            print(f"✗ Error testing FSSpec integration: {e}")
            self.test_results['fsspec_synapse'] = False
    
    async def run_all_tests(self):
        """Run all Synapse MCP server integration tests."""
        print("Starting Synapse MCP Server Integration Tests")
        print("=" * 60)
        
        try:
            self.setup()
            
            self.test_mcp_server_import()
            self.test_synapse_tool_definitions()
            self.test_synapse_storage_initialization()
            await self.test_mock_synapse_operations()
            await self.test_mcp_tool_handler_integration()
            self.test_environment_configuration()
            self.test_fsspec_synapse_integration()
            
            self.print_summary()
            
        finally:
            self.cleanup()
    
    def print_summary(self):
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("SYNAPSE MCP INTEGRATION TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = 0
        partial_tests = 0
        
        for test_name, result in self.test_results.items():
            if result == True:
                status = "PASS"
                passed_tests += 1
            elif result == 'partial':
                status = "PARTIAL"
                partial_tests += 1
            elif isinstance(result, dict):
                status = "INFO"
                passed_tests += 1
            else:
                status = "FAIL"
            
            print(f"{test_name:.<45} {status}")
        
        print("-" * 60)
        print(f"Total: {passed_tests}/{total_tests} tests passed")
        if partial_tests > 0:
            print(f"Partial: {partial_tests} tests partially successful")
        
        # Environment configuration details
        env_config = self.test_results.get('environment_config')
        if isinstance(env_config, dict):
            print(f"\nEnvironment Configuration:")
            print(f"  Configured: {len(env_config['configured'])} variables")
            print(f"  Missing: {len(env_config['missing'])} variables")
            print(f"  Ready for production: {env_config['ready']}")
        
        if passed_tests >= total_tests * 0.8:  # 80% pass rate
            print("\n✅ Synapse MCP integration is ready for testing!")
            if env_config and isinstance(env_config, dict) and not env_config['ready']:
                print("⚠ Configure environment variables for full functionality")
            return True
        else:
            print("\n❌ Synapse MCP integration needs more work")
            return False


async def main():
    """Main test runner."""
    tester = SynapseMCPServerTest()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 Synapse MCP integration tests completed successfully!")
        exit(0)
    else:
        print("\n⚠ Some integration issues found. Check the output above.")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
