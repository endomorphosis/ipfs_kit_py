#!/usr/bin/env python3
"""
Unified Tool Registry System for IPFS Kit MCP Integration

This module provides a comprehensive tool registry with:
- Standardized tool definition format
- Automatic tool discovery and registration
- Version compatibility checking
- Dynamic tool loading/unloading
"""

import json
import logging
import inspect
import importlib.util # Explicitly import importlib.util
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
from enum import Enum

# Setup logging
logger = logging.getLogger(__name__)

class ToolStatus(Enum):
    """Tool status enumeration"""
    REGISTERED = "registered"
    LOADED = "loaded"
    ERROR = "error"
    DISABLED = "disabled"

class ToolCategory(Enum):
    """Tool category enumeration"""
    IPFS_CORE = "ipfs_core"
    IPFS_ADVANCED = "ipfs_advanced"
    IPFS_MFS = "ipfs_mfs"
    VFS = "vfs"
    MULTI_BACKEND = "multi_backend"
    INTEGRATION = "integration"
    SYSTEM = "system"

@dataclass
class ToolSchema:
    """Standardized tool definition format"""
    name: str
    category: ToolCategory
    description: str
    parameters: Dict[str, Any]
    returns: Dict[str, Any]
    version: str
    dependencies: List[str]
    handler: Optional[Callable] = None
    status: ToolStatus = ToolStatus.REGISTERED
    module_path: Optional[str] = None
    last_updated: Optional[str] = None
    checksum: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert enums to strings
        data['category'] = self.category.value
        data['status'] = self.status.value
        # Remove non-serializable handler
        data.pop('handler', None)
        return data

    def calculate_checksum(self) -> str:
        """Calculate checksum for tool definition"""
        tool_str = f"{self.name}{self.description}{json.dumps(self.parameters, sort_keys=True)}{self.version}"
        return hashlib.md5(tool_str.encode()).hexdigest()

class ToolRegistry:
    """Unified tool registry with discovery and management capabilities"""
    
    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or Path("tools_registry.json")
        self.tools: Dict[str, ToolSchema] = {}
        self.handlers: Dict[str, Callable] = {}
        self.discovery_paths: List[Path] = []
        
        # Load existing registry
        self.load_registry()
    
    def add_discovery_path(self, path: Union[str, Path]) -> None:
        """Add path for automatic tool discovery"""
        path = Path(path)
        if path.exists() and path not in self.discovery_paths:
            self.discovery_paths.append(path)
            logger.info(f"Added discovery path: {path}")
    
    def register_tool(self, tool: ToolSchema, handler: Optional[Callable] = None) -> bool:
        """Register a tool with the registry"""
        try:
            # Validate tool
            if not self._validate_tool(tool):
                return False
            
            # Calculate checksum
            tool.checksum = tool.calculate_checksum()
            
            # Store tool
            self.tools[tool.name] = tool
            
            # Store handler if provided
            if handler:
                self.handlers[tool.name] = handler
                tool.handler = handler
                tool.status = ToolStatus.LOADED
            
            logger.info(f"Registered tool: {tool.name} ({tool.category.value})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register tool {tool.name}: {e}")
            return False
    
    def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool from the registry"""
        try:
            if tool_name in self.tools:
                del self.tools[tool_name]
                if tool_name in self.handlers:
                    del self.handlers[tool_name]
                logger.info(f"Unregistered tool: {tool_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to unregister tool {tool_name}: {e}")
            return False
    
    def get_tool(self, tool_name: str) -> Optional[ToolSchema]:
        """Get tool definition by name"""
        return self.tools.get(tool_name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[ToolSchema]:
        """Get all tools in a specific category"""
        return [tool for tool in self.tools.values() if tool.category == category]
    
    def list_tools(self, status_filter: Optional[ToolStatus] = None) -> List[str]:
        """List all registered tools, optionally filtered by status"""
        if status_filter:
            return [name for name, tool in self.tools.items() if tool.status == status_filter]
        return list(self.tools.keys())
    
    def discover_tools(self) -> int:
        """Automatically discover and register tools from discovery paths"""
        discovered_count = 0
        
        for path in self.discovery_paths:
            try:
                discovered_count += self._discover_from_path(path)
            except Exception as e:
                logger.error(f"Error discovering tools from {path}: {e}")
        
        logger.info(f"Discovered {discovered_count} tools")
        return discovered_count
    
    def _discover_from_path(self, path: Path) -> int:
        """Discover tools from a specific path"""
        count = 0
        
        # Look for Python files
        for py_file in path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
                
            try:
                # Import module
                module_name = py_file.stem
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for tool definitions
                    count += self._extract_tools_from_module(module, str(py_file))
                    
            except Exception as e:
                logger.warning(f"Failed to import {py_file}: {e}")
        
        return count
    
    def _extract_tools_from_module(self, module, module_path: str) -> int:
        """Extract tool definitions from a module"""
        count = 0
        
        # Look for functions with tool metadata
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and hasattr(obj, '_tool_meta'):
                try:
                    meta = obj._tool_meta # type: ignore
                    tool = ToolSchema(
                        name=meta.get('name', name),
                        category=ToolCategory(meta.get('category', 'system')),
                        description=meta.get('description', ''),
                        parameters=meta.get('parameters', {}),
                        returns=meta.get('returns', {}),
                        version=meta.get('version', '1.0.0'),
                        dependencies=meta.get('dependencies', []),
                        module_path=module_path,
                        handler=obj
                    )
                    
                    if self.register_tool(tool, obj):
                        count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to extract tool {name}: {e}")
        
        return count
    
    def _validate_tool(self, tool: ToolSchema) -> bool:
        """Validate tool definition"""
        if not tool.name:
            logger.error("Tool name is required")
            return False
        
        if not tool.description:
            logger.error(f"Tool {tool.name} requires description")
            return False
        
        if not isinstance(tool.parameters, dict):
            logger.error(f"Tool {tool.name} parameters must be a dictionary")
            return False
        
        return True
    
    def check_dependencies(self, tool_name: str) -> Dict[str, bool]:
        """Check if tool dependencies are available"""
        tool = self.get_tool(tool_name)
        if not tool:
            return {}
        
        status = {}
        for dep in tool.dependencies:
            try:
                importlib.import_module(dep)
                status[dep] = True
            except ImportError:
                status[dep] = False
        
        return status
    
    def load_handler(self, tool_name: str) -> bool:
        """Dynamically load tool handler"""
        tool = self.get_tool(tool_name)
        if not tool or not tool.module_path:
            return False
        
        try:
            # Import module
            spec = importlib.util.spec_from_file_location(tool_name, tool.module_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find handler function
                handler = getattr(module, f"handle_{tool_name}", None)
                if handler:
                    self.handlers[tool_name] = handler
                    tool.handler = handler
                    tool.status = ToolStatus.LOADED
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to load handler for {tool_name}: {e}")
            tool.status = ToolStatus.ERROR
        
        return False
    
    def unload_handler(self, tool_name: str) -> bool:
        """Unload tool handler"""
        if tool_name in self.handlers:
            del self.handlers[tool_name]
            tool = self.get_tool(tool_name)
            if tool:
                tool.handler = None
                tool.status = ToolStatus.REGISTERED
            return True
        return False
    
    def save_registry(self) -> bool:
        """Save registry to file"""
        try:
            registry_data = {
                'tools': {name: tool.to_dict() for name, tool in self.tools.items()},
                'discovery_paths': [str(path) for path in self.discovery_paths]
            }
            
            with open(self.registry_path, 'w') as f:
                json.dump(registry_data, f, indent=2)
            
            logger.info(f"Saved registry to {self.registry_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
            return False
    
    def load_registry(self) -> bool:
        """Load registry from file"""
        try:
            if not self.registry_path.exists():
                return True  # Empty registry is OK
            
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
            
            # Load tools
            for name, tool_data in data.get('tools', {}).items():
                tool = ToolSchema(
                    name=tool_data['name'],
                    category=ToolCategory(tool_data['category']),
                    description=tool_data['description'],
                    parameters=tool_data['parameters'],
                    returns=tool_data['returns'],
                    version=tool_data['version'],
                    dependencies=tool_data['dependencies'],
                    status=ToolStatus(tool_data.get('status', 'registered')),
                    module_path=tool_data.get('module_path'),
                    last_updated=tool_data.get('last_updated'),
                    checksum=tool_data.get('checksum')
                )
                self.tools[name] = tool
            
            # Load discovery paths
            for path_str in data.get('discovery_paths', []):
                self.add_discovery_path(Path(path_str))
            
            logger.info(f"Loaded {len(self.tools)} tools from registry")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            return False
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        stats = {
            'total_tools': len(self.tools),
            'loaded_tools': len([t for t in self.tools.values() if t.status == ToolStatus.LOADED]),
            'error_tools': len([t for t in self.tools.values() if t.status == ToolStatus.ERROR]),
            'categories': {},
            'discovery_paths': len(self.discovery_paths)
        }
        
        # Count by category
        for tool in self.tools.values():
            category = tool.category.value
            stats['categories'][category] = stats['categories'].get(category, 0) + 1
        
        return stats

# Decorator for marking functions as tools
def tool(name: Optional[str] = None, category: str = "system", description: str = "", 
         parameters: Optional[Dict[str, Any]] = None, returns: Optional[Dict[str, Any]] = None,
         version: str = "1.0.0", dependencies: Optional[List[str]] = None):
    """Decorator to mark functions as MCP tools"""
    def decorator(func):
        func._tool_meta = { # type: ignore
            'name': name or func.__name__,
            'category': category,
            'description': description or func.__doc__ or '',
            'parameters': parameters if parameters is not None else {},
            'returns': returns if returns is not None else {},
            'version': version,
            'dependencies': dependencies if dependencies is not None else []
        }
        return func
    return decorator

# Global registry instance
registry = ToolRegistry()
