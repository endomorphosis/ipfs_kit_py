#!/usr/bin/env python3
"""
WebAssembly Support for IPFS Kit

Provides WebAssembly bindings for IPFS Kit to enable browser-based
and edge computing applications.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Check for WASM dependencies
try:
    import wasmtime
    HAS_WASMTIME = True
except ImportError:
    HAS_WASMTIME = False

try:
    import wasmer
    HAS_WASMER = True
except ImportError:
    HAS_WASMER = False


class WasmIPFSBridge:
    """
    Bridge between Python IPFS Kit and WebAssembly runtime.
    
    Enables IPFS operations to be called from WASM modules and
    allows WASM modules to be stored/retrieved from IPFS.
    """
    
    def __init__(self, ipfs_api=None, runtime: str = "wasmtime"):
        """
        Initialize WASM bridge.
        
        Args:
            ipfs_api: IPFS API instance
            runtime: WASM runtime to use ("wasmtime" or "wasmer")
        """
        self.ipfs_api = ipfs_api
        self.runtime = runtime
        
        # Check for runtime
        if runtime == "wasmtime" and not HAS_WASMTIME:
            raise ImportError("wasmtime is required. Install with: pip install wasmtime")
        elif runtime == "wasmer" and not HAS_WASMER:
            raise ImportError("wasmer is required. Install with: pip install wasmer wasmer-compiler-cranelift")
        
        logger.info(f"WASM bridge initialized with {runtime} runtime")
    
    async def load_wasm_module(self, cid: str) -> Optional[Any]:
        """
        Load a WASM module from IPFS.
        
        Args:
            cid: IPFS CID of the WASM module
            
        Returns:
            Compiled WASM module instance
        """
        try:
            # Get WASM binary from IPFS
            if self.ipfs_api is None:
                raise Exception("IPFS API not initialized")
            
            wasm_bytes = await self.ipfs_api.get(cid)
            
            # Compile WASM module
            if self.runtime == "wasmtime":
                return self._load_wasmtime_module(wasm_bytes)
            elif self.runtime == "wasmer":
                return self._load_wasmer_module(wasm_bytes)
            
            return None
        except Exception as e:
            logger.error(f"Error loading WASM module {cid}: {e}")
            return None
    
    def _load_wasmtime_module(self, wasm_bytes: bytes) -> Any:
        """Load WASM module using Wasmtime."""
        from wasmtime import Store, Module, Instance
        
        store = Store()
        module = Module(store.engine, wasm_bytes)
        instance = Instance(store, module, [])
        
        return instance
    
    def _load_wasmer_module(self, wasm_bytes: bytes) -> Any:
        """Load WASM module using Wasmer."""
        from wasmer import engine, Store, Module, Instance
        from wasmer_compiler_cranelift import Compiler
        
        store = Store(engine.JIT(Compiler))
        module = Module(store, wasm_bytes)
        instance = Instance(module)
        
        return instance
    
    async def store_wasm_module(self, wasm_bytes: bytes, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Store a WASM module in IPFS.
        
        Args:
            wasm_bytes: Compiled WASM binary
            metadata: Optional metadata about the module
            
        Returns:
            CID of stored WASM module
        """
        try:
            if self.ipfs_api is None:
                raise Exception("IPFS API not initialized")
            
            # Store WASM binary
            result = await self.ipfs_api.add(wasm_bytes)
            cid = result['cid']
            
            # Store metadata if provided
            if metadata:
                metadata_cid = await self.ipfs_api.add(metadata)
                logger.info(f"Stored WASM metadata at {metadata_cid}")
            
            logger.info(f"Stored WASM module at {cid}")
            return cid
        except Exception as e:
            logger.error(f"Error storing WASM module: {e}")
            raise
    
    async def execute_wasm_function(self, module: Any, function_name: str, 
                                   args: List[Any] = None) -> Any:
        """
        Execute a function in a WASM module.
        
        Args:
            module: Compiled WASM module instance
            function_name: Name of function to execute
            args: Function arguments
            
        Returns:
            Function result
        """
        try:
            args = args or []
            
            if self.runtime == "wasmtime":
                func = module.exports(module.store)[function_name]
                return func(module.store, *args)
            elif self.runtime == "wasmer":
                func = module.exports.__getattribute__(function_name)
                return func(*args)
            
            return None
        except Exception as e:
            logger.error(f"Error executing WASM function {function_name}: {e}")
            raise
    
    def create_ipfs_imports(self) -> Dict[str, Any]:
        """
        Create IPFS host functions that can be imported by WASM modules.
        
        Returns:
            Dictionary of host functions
        """
        imports = {}
        
        # Add IPFS operations as host functions
        if self.runtime == "wasmtime":
            imports = self._create_wasmtime_imports()
        elif self.runtime == "wasmer":
            imports = self._create_wasmer_imports()
        
        return imports
    
    def _create_wasmtime_imports(self) -> Dict[str, Any]:
        """Create host functions for Wasmtime."""
        from wasmtime import Func, FuncType, ValType
        
        # Define host functions
        def ipfs_add(data_ptr: int, data_len: int) -> int:
            """Host function to add data to IPFS."""
            # Implementation would read from WASM memory and call IPFS API
            return 0
        
        def ipfs_get(cid_ptr: int, cid_len: int) -> int:
            """Host function to get data from IPFS."""
            # Implementation would call IPFS API and write to WASM memory
            return 0
        
        return {
            "ipfs_add": ipfs_add,
            "ipfs_get": ipfs_get
        }
    
    def _create_wasmer_imports(self) -> Dict[str, Any]:
        """Create host functions for Wasmer."""
        from wasmer import Function, FunctionType, Type
        
        # Define host functions
        def ipfs_add(data_ptr: int, data_len: int) -> int:
            """Host function to add data to IPFS."""
            return 0
        
        def ipfs_get(cid_ptr: int, cid_len: int) -> int:
            """Host function to get data from IPFS."""
            return 0
        
        return {
            "ipfs": {
                "add": Function(FunctionType([Type.I32, Type.I32], [Type.I32]), ipfs_add),
                "get": Function(FunctionType([Type.I32, Type.I32], [Type.I32]), ipfs_get)
            }
        }


class WasmModuleRegistry:
    """
    Registry for WASM modules stored in IPFS.
    
    Manages metadata, versioning, and discovery of WASM modules.
    """
    
    def __init__(self, ipfs_api=None):
        """Initialize WASM module registry."""
        self.ipfs_api = ipfs_api
        self.modules = {}
        logger.info("WASM module registry initialized")
    
    async def register_module(self, name: str, cid: str, 
                             metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register a WASM module.
        
        Args:
            name: Module name
            cid: IPFS CID of module
            metadata: Optional metadata
            
        Returns:
            True if successful
        """
        try:
            self.modules[name] = {
                "cid": cid,
                "metadata": metadata or {},
                "registered_at": None  # Would use datetime
            }
            
            logger.info(f"Registered WASM module {name} at {cid}")
            return True
        except Exception as e:
            logger.error(f"Error registering module {name}: {e}")
            return False
    
    async def get_module(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get module information.
        
        Args:
            name: Module name
            
        Returns:
            Module metadata
        """
        return self.modules.get(name)
    
    def list_modules(self) -> List[Dict[str, Any]]:
        """
        List all registered modules.
        
        Returns:
            List of module metadata
        """
        return [
            {"name": name, **info}
            for name, info in self.modules.items()
        ]


# JavaScript/Browser interface generator
class WasmJSBindings:
    """
    Generate JavaScript bindings for browser-based WASM usage.
    """
    
    @staticmethod
    def generate_js_bindings(module_name: str, functions: List[str]) -> str:
        """
        Generate JavaScript wrapper for WASM module.
        
        Args:
            module_name: Name of the WASM module
            functions: List of exported function names
            
        Returns:
            JavaScript code for browser
        """
        js_code = f"""
// Generated JavaScript bindings for {module_name}
class {module_name}WASM {{
    constructor() {{
        this.module = null;
        this.instance = null;
    }}
    
    async load(wasmUrl) {{
        const response = await fetch(wasmUrl);
        const buffer = await response.arrayBuffer();
        
        const wasmModule = await WebAssembly.compile(buffer);
        this.instance = await WebAssembly.instantiate(wasmModule, {{
            ipfs: {{
                add: (ptr, len) => this._ipfsAdd(ptr, len),
                get: (ptr, len) => this._ipfsGet(ptr, len)
            }}
        }});
        
        this.module = this.instance.exports;
    }}
    
    _ipfsAdd(ptr, len) {{
        // IPFS add implementation
        console.log('IPFS add called');
        return 0;
    }}
    
    _ipfsGet(ptr, len) {{
        // IPFS get implementation
        console.log('IPFS get called');
        return 0;
    }}
"""
        
        # Add wrapper for each function
        for func in functions:
            js_code += f"""
    {func}(...args) {{
        if (!this.module) {{
            throw new Error('WASM module not loaded');
        }}
        return this.module.{func}(...args);
    }}
"""
        
        js_code += """
}

// Export for use
export default """ + module_name + """WASM;
"""
        
        return js_code


# Convenience functions
def create_wasm_bridge(ipfs_api=None, runtime: str = "wasmtime") -> WasmIPFSBridge:
    """Create WASM bridge instance."""
    return WasmIPFSBridge(ipfs_api=ipfs_api, runtime=runtime)


def create_wasm_registry(ipfs_api=None) -> WasmModuleRegistry:
    """Create WASM module registry instance."""
    return WasmModuleRegistry(ipfs_api=ipfs_api)
