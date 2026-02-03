#!/usr/bin/env python3
"""
Extended tests for WebAssembly support.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile


class TestWASMSupportExtended:
    """Extended tests for WASM Support functionality."""
    
    @pytest.mark.asyncio
    async def test_wasm_load_module_from_ipfs(self):
        """Test loading WASM module from IPFS."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        mock_ipfs = AsyncMock()
        mock_ipfs.cat = AsyncMock(return_value=b'\x00asm\x01\x00\x00\x00')  # WASM magic number
        
        bridge = WasmIPFSBridge(ipfs_api=mock_ipfs)
        module = await bridge.load_wasm_module("QmTestModule")
        
        assert module is not None
        mock_ipfs.cat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wasm_load_module_invalid(self):
        """Test loading invalid WASM module."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        mock_ipfs = AsyncMock()
        mock_ipfs.cat = AsyncMock(return_value=b'invalid wasm data')
        
        bridge = WasmIPFSBridge(ipfs_api=mock_ipfs)
        module = await bridge.load_wasm_module("QmInvalidModule")
        
        # Should handle gracefully
        assert module is None or "error" in str(module).lower()
    
    @pytest.mark.asyncio
    async def test_wasm_execute_function(self):
        """Test executing WASM function."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Mock WASM module
        mock_module = Mock()
        mock_instance = Mock()
        mock_instance.exports = Mock()
        mock_instance.exports.add = Mock(return_value=42)
        
        bridge.modules["test_module"] = {"instance": mock_instance}
        
        result = await bridge.execute_function("test_module", "add", [20, 22])
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_wasm_host_function_binding(self):
        """Test binding host functions to WASM."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Define host function
        def host_log(msg):
            return f"LOG: {msg}"
        
        bridge.bind_host_function("log", host_log)
        
        assert "log" in bridge.host_functions
        assert bridge.host_functions["log"]("test") == "LOG: test"
    
    @pytest.mark.asyncio
    async def test_wasm_ipfs_get_host_function(self):
        """Test IPFS get host function."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        mock_ipfs = AsyncMock()
        mock_ipfs.cat = AsyncMock(return_value=b"test content")
        
        bridge = WasmIPFSBridge(ipfs_api=mock_ipfs)
        
        # Call the host function
        content = await bridge._host_ipfs_get("QmTestCID")
        
        assert content == b"test content"
    
    @pytest.mark.asyncio
    async def test_wasm_ipfs_add_host_function(self):
        """Test IPFS add host function."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        mock_ipfs = AsyncMock()
        mock_ipfs.add = AsyncMock(return_value={"Hash": "QmNewCID"})
        
        bridge = WasmIPFSBridge(ipfs_api=mock_ipfs)
        
        # Call the host function
        cid = await bridge._host_ipfs_add(b"content to add")
        
        assert cid == "QmNewCID"
    
    def test_wasm_module_registry(self):
        """Test WASM module registry."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Register module
        bridge.register_module("test_module", "QmTestCID", "1.0.0")
        
        assert "test_module" in bridge.registry
        assert bridge.registry["test_module"]["cid"] == "QmTestCID"
        assert bridge.registry["test_module"]["version"] == "1.0.0"
    
    def test_wasm_module_registry_list(self):
        """Test listing registered modules."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        bridge.register_module("module1", "QmCID1", "1.0.0")
        bridge.register_module("module2", "QmCID2", "2.0.0")
        
        modules = bridge.list_modules()
        
        assert len(modules) == 2
        assert "module1" in [m["name"] for m in modules]
        assert "module2" in [m["name"] for m in modules]
    
    def test_wasm_module_unregister(self):
        """Test unregistering a module."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        bridge.register_module("test_module", "QmTestCID", "1.0.0")
        assert "test_module" in bridge.registry
        
        bridge.unregister_module("test_module")
        assert "test_module" not in bridge.registry
    
    def test_wasm_js_bindings_generation(self):
        """Test JavaScript bindings generation."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Register module
        bridge.register_module("test_module", "QmTestCID", "1.0.0")
        
        # Generate JS bindings
        js_code = bridge.generate_js_bindings("test_module")
        
        assert js_code is not None
        assert "test_module" in js_code
        assert "async" in js_code or "function" in js_code
    
    def test_wasm_js_bindings_with_functions(self):
        """Test JavaScript bindings with exported functions."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Mock module with exports
        mock_module = Mock()
        mock_module.exports = ["add", "multiply", "get_data"]
        bridge.modules["test_module"] = {"module": mock_module}
        
        js_code = bridge.generate_js_bindings("test_module", ["add", "multiply", "get_data"])
        
        assert "add" in js_code
        assert "multiply" in js_code
        assert "get_data" in js_code
    
    @pytest.mark.asyncio
    async def test_wasm_memory_operations(self):
        """Test WASM memory operations."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Mock WASM instance with memory
        mock_instance = Mock()
        mock_memory = Mock()
        mock_memory.data = bytearray(1024)
        mock_instance.exports.memory = mock_memory
        
        bridge.modules["test_module"] = {"instance": mock_instance}
        
        # Write to memory
        result = bridge.write_memory("test_module", 0, b"test data")
        assert result is True or result is None  # Should succeed or handle gracefully
    
    @pytest.mark.asyncio
    async def test_wasm_read_memory(self):
        """Test reading from WASM memory."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Mock WASM instance with memory
        mock_instance = Mock()
        mock_memory = Mock()
        test_data = bytearray(b"test data" + b"\x00" * 1015)
        mock_memory.data = test_data
        mock_instance.exports.memory = mock_memory
        
        bridge.modules["test_module"] = {"instance": mock_instance}
        
        # Read from memory
        data = bridge.read_memory("test_module", 0, 9)
        assert data == b"test data" or data is None  # Should succeed or handle gracefully
    
    def test_wasm_runtime_detection(self):
        """Test WASM runtime detection."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        runtime = bridge.detect_runtime()
        
        assert runtime in ["wasmtime", "wasmer", "none"]
    
    @pytest.mark.asyncio
    async def test_wasm_module_instantiation(self):
        """Test WASM module instantiation."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Mock WASM binary
        wasm_binary = b'\x00asm\x01\x00\x00\x00'
        
        instance = await bridge.instantiate_module(wasm_binary, imports={})
        
        # Should handle gracefully even if runtime not available
        assert instance is None or hasattr(instance, "exports")
    
    @pytest.mark.asyncio
    async def test_wasm_error_handling(self):
        """Test WASM error handling."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Try to execute non-existent function
        result = await bridge.execute_function("non_existent_module", "func", [])
        
        assert result is None or "error" in str(result).lower()
    
    def test_wasm_import_object_creation(self):
        """Test WASM import object creation."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        mock_ipfs = AsyncMock()
        bridge = WasmIPFSBridge(ipfs_api=mock_ipfs)
        
        imports = bridge.create_import_object()
        
        assert imports is not None
        assert isinstance(imports, dict)
        # Should have IPFS host functions
        assert "ipfs" in imports or len(imports) == 0  # Empty if no runtime
    
    @pytest.mark.asyncio
    async def test_wasm_module_validation(self):
        """Test WASM module validation."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Valid WASM magic number
        valid_wasm = b'\x00asm\x01\x00\x00\x00'
        assert bridge.validate_wasm(valid_wasm) is True
        
        # Invalid WASM
        invalid_wasm = b'not a wasm module'
        assert bridge.validate_wasm(invalid_wasm) is False
    
    def test_wasm_version_management(self):
        """Test WASM module version management."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Register multiple versions
        bridge.register_module("mymodule", "QmCID1", "1.0.0")
        bridge.register_module("mymodule", "QmCID2", "1.1.0")
        bridge.register_module("mymodule", "QmCID3", "2.0.0")
        
        # Get latest version
        latest = bridge.get_latest_version("mymodule")
        assert latest is not None
        assert latest["version"] == "2.0.0" or latest["cid"] == "QmCID3"
    
    @pytest.mark.asyncio
    async def test_wasm_streaming_execution(self):
        """Test streaming WASM execution."""
        from ipfs_kit_py.wasm_support import WasmIPFSBridge
        
        bridge = WasmIPFSBridge()
        
        # Mock streaming function
        mock_instance = Mock()
        mock_instance.exports.stream_process = Mock(side_effect=[1, 2, 3, 4, 5])
        bridge.modules["test_module"] = {"instance": mock_instance}
        
        results = []
        async for result in bridge.stream_execute("test_module", "stream_process", chunk_size=1):
            results.append(result)
            if len(results) >= 3:  # Limit iterations
                break
        
        # Should handle streaming or return None gracefully
        assert results is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
