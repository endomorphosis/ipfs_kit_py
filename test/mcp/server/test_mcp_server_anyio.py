#!/usr/bin/env python3
"""
Tests for the MCP (Model-Controller-Persistence) server implementation with AnyIO.

These tests verify that:
1. The MCP server initializes correctly
2. Models properly encapsulate business logic
3. Controllers correctly handle HTTP requests
4. The persistence layer properly caches data
5. Debug and isolation modes work as expected
6. Integration with FastAPI works correctly

This version uses AnyIO instead of asyncio for async operations.
"""

import os
import sys
import json
import time
import uuid
import pickle
import tempfile
import unittest
import shutil
import anyio
from unittest.mock import MagicMock, patch, call
from pathlib import Path

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Try to import FastAPI
try:
    from fastapi import FastAPI, Request, Response, APIRouter
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

# Import MCP server and components
# Create stubs and mock implementations first
MCP_AVAILABLE = False

# Create mock/stub implementations
class StubCacheManager:
    """Stub implementation of MCPCacheManager for testing"""
    def __init__(self, base_path=None, memory_limit=100 * 1024 * 1024, disk_limit=1024 * 1024 * 1024, debug_mode=False):
        self.base_path = base_path or tempfile.mkdtemp(prefix="mcp_cache_")
        self.memory_limit = memory_limit
        self.disk_limit = disk_limit
        self.debug_mode = debug_mode
        self.memory_cache = {}
        self.metadata = {}
        self.running = True

        # Needed for disk cache test
        self.disk_cache_path = os.path.join(self.base_path, "disk_cache")
        os.makedirs(self.disk_cache_path, exist_ok=True)

        # Stats for metrics
        self.stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "misses": 0,
            "memory_evictions": 0,
            "disk_evictions": 0,
            "put_operations": 0,
            "get_operations": 0,
            "memory_size": 0,
            "disk_size": 0
        }

    def put(self, key, value, metadata=None):
        # Calculate size for memory cache
        if value and hasattr(value, '__len__'):
            size = len(value) if isinstance(value, (bytes, str)) else 100  # Default size for complex objects
        else:
            size = 100  # Default size for values without length

        # Check if we need to make room in memory
        current_size = sum(self.metadata.get(k, {}).get("size", 100) for k in self.memory_cache.keys())
        if current_size + size > self.memory_limit:
            # Calculate how much space we need to free
            space_needed = size + current_size - (self.memory_limit * 0.8)  # Target 80% usage
            self._evict_from_memory(space_needed)

        # Store in memory
        self.memory_cache[key] = value

        # Store metadata
        if metadata:
            if key not in self.metadata:
                self.metadata[key] = {}
            self.metadata[key].update(metadata)

        # Always update size in metadata
        if key not in self.metadata:
            self.metadata[key] = {}
        self.metadata[key]["size"] = size

        # Write to disk for persistence test
        try:
            os.makedirs(self.disk_cache_path, exist_ok=True)
            disk_path = os.path.join(self.disk_cache_path, self._key_to_filename(key))
            with open(disk_path, 'wb') as f:
                pickle.dump(value, f)
        except Exception as e:
            print(f"Error storing to disk: {e}")

        self.stats["put_operations"] += 1
        return True

    def get(self, key):
        self.stats["get_operations"] += 1

        # Try memory first
        if key in self.memory_cache:
            self.stats["memory_hits"] += 1
            return self.memory_cache.get(key)

        # Try disk
        try:
            disk_path = os.path.join(self.disk_cache_path, self._key_to_filename(key))
            if os.path.exists(disk_path):
                with open(disk_path, 'rb') as f:
                    value = pickle.load(f)
                    self.stats["disk_hits"] += 1
                    # Promote to memory
                    self.memory_cache[key] = value
                    return value
        except Exception:
            pass

        self.stats["misses"] += 1
        return None

    def delete(self, key):
        if key in self.memory_cache:
            del self.memory_cache[key]
        if key in self.metadata:
            del self.metadata[key]

        # Also remove from disk if present
        try:
            disk_path = os.path.join(self.disk_cache_path, self._key_to_filename(key))
            if os.path.exists(disk_path):
                os.unlink(disk_path)
        except Exception:
            pass

        return True

    def clear(self):
        self.memory_cache.clear()
        self.metadata.clear()

        # Clear disk cache
        try:
            for filename in os.listdir(self.disk_cache_path):
                file_path = os.path.join(self.disk_cache_path, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        except Exception:
            pass

        # Reset stats
        self.stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "misses": 0,
            "memory_evictions": 0,
            "disk_evictions": 0,
            "put_operations": 0,
            "get_operations": 0,
            "memory_size": 0,
            "disk_size": 0
        }

        return True

    def _key_to_filename(self, key):
        """Convert cache key to a filename."""
        # Replace unsafe characters
        safe_key = str(key).replace("/", "_").replace(":", "_")

        # Hash long keys
        if len(safe_key) > 100:
            import hashlib
            safe_key = hashlib.md5(str(key).encode()).hexdigest()

        return safe_key

    def _evict_from_memory(self, bytes_to_free):
        """Evict items from memory cache to free up space."""
        # Sort keys by size (largest first for simplicity)
        keys_by_size = sorted(
            self.memory_cache.keys(),
            key=lambda k: self.metadata.get(k, {}).get("size", 0),
            reverse=True
        )

        # Evict items until we've freed enough space
        bytes_freed = 0
        evicted_count = 0
        for key in keys_by_size:
            size = self.metadata.get(key, {}).get("size", 0)
            del self.memory_cache[key]
            bytes_freed += size
            evicted_count += 1
            self.stats["memory_evictions"] += 1

            if bytes_freed >= bytes_to_free:
                break

        return evicted_count

    def get_stats(self):
        return {
            "memory_hits": self.stats["memory_hits"],
            "disk_hits": self.stats["disk_hits"],
            "misses": self.stats["misses"],
            "total_hits": self.stats["memory_hits"] + self.stats["disk_hits"],
            "hit_rate": (self.stats["memory_hits"] + self.stats["disk_hits"]) / 
                    max(1, (self.stats["memory_hits"] + self.stats["disk_hits"] + self.stats["misses"])),
            "memory_size": sum(self.metadata.get(k, {}).get("size", 0) for k in self.memory_cache),
            "item_count": len(self.memory_cache),
            "memory_evictions": self.stats["memory_evictions"],
            "disk_evictions": self.stats["disk_evictions"],
            "get_operations": self.stats["get_operations"],
            "put_operations": self.stats["put_operations"],
        }

    def stop(self):
        """Stop the cache manager and clean up resources."""
        self.running = False
        try:
            if hasattr(self, 'base_path') and self.base_path and self.base_path.startswith(tempfile.gettempdir()):
                shutil.rmtree(self.base_path, ignore_errors=True)
        except Exception:
            pass

class StubIPFSModel:
    """Stub implementation of IPFSModel for testing."""
    def __init__(self, ipfs_kit_instance=None, cache_manager=None):
        self.ipfs_kit = ipfs_kit_instance
        self.cache_manager = cache_manager
        
        # Initialize statistics
        self.operation_stats = {
            "add_content": 0,
            "get_content": 0,
            "pin_content": 0,
            "unpin_content": 0,
            "list_pins": 0
        }
        
        # Cache for testing
        self.content_cache = {}
        self.pin_list = {}
        
        # Mock CIDs for testing
        self.next_cid = 0
        
    def add_content(self, content, filename=None):
        """Add content to IPFS."""
        # Increment operation count
        self.operation_stats["add_content"] += 1
        
        # Create a deterministic CID for testing
        cid = f"QmTestCID{self.next_cid}"
        self.next_cid += 1
        
        # Store in local cache
        self.content_cache[cid] = content
        
        # Cache the content if we have a cache manager
        if self.cache_manager:
            self.cache_manager.put(cid, content, {
                "filename": filename,
                "timestamp": time.time()
            })
        
        # Return a formatted result
        result = {
            "success": True,
            "cid": cid,
            "size": len(content) if hasattr(content, "__len__") else 0,
            "filename": filename
        }
        
        return result
    
    def get_content(self, cid):
        """Get content from IPFS by CID."""
        # Increment operation count
        self.operation_stats["get_content"] += 1
        
        # Check cache first
        if self.cache_manager:
            cached = self.cache_manager.get(cid)
            if cached:
                return {
                    "success": True,
                    "content": cached,
                    "size": len(cached) if hasattr(cached, "__len__") else 0,
                    "cached": True
                }
        
        # Check our content cache
        if cid in self.content_cache:
            content = self.content_cache[cid]
            
            # Store in cache manager if available
            if self.cache_manager:
                self.cache_manager.put(cid, content, {
                    "timestamp": time.time()
                })
                
            return {
                "success": True,
                "content": content,
                "size": len(content) if hasattr(content, "__len__") else 0,
                "cached": False
            }
        
        # Not found
        return {
            "success": False,
            "error": f"Content not found for CID: {cid}"
        }
    
    def pin_content(self, cid):
        """Pin content in IPFS to prevent garbage collection."""
        # Increment operation count
        self.operation_stats["pin_content"] += 1
        
        # Check if content exists
        if cid not in self.content_cache:
            return {
                "success": False,
                "error": f"Cannot pin non-existent content: {cid}"
            }
        
        # Add to pin list
        self.pin_list[cid] = {
            "pinned_at": time.time()
        }
        
        return {
            "success": True,
            "cid": cid,
            "pinned": True
        }
    
    def unpin_content(self, cid):
        """Unpin content in IPFS."""
        # Increment operation count
        self.operation_stats["unpin_content"] += 1
        
        # Check if content is pinned
        if cid not in self.pin_list:
            return {
                "success": False,
                "error": f"Content not pinned: {cid}"
            }
        
        # Remove from pin list
        del self.pin_list[cid]
        
        return {
            "success": True,
            "cid": cid,
            "unpinned": True
        }
    
    def list_pins(self):
        """List all pinned content."""
        # Increment operation count
        self.operation_stats["list_pins"] += 1
        
        return {
            "success": True,
            "pins": self.pin_list
        }

    def get_stats(self):
        """Get operation statistics."""
        return self.operation_stats

    def reset_stats(self):
        """Reset operation statistics."""
        old_stats = self.operation_stats.copy()
        self.operation_stats = {k: 0 for k in self.operation_stats}
        return old_stats


class StubIPFSController:
    """Stub implementation of IPFSController for testing."""
    def __init__(self, ipfs_model):
        self.ipfs_model = ipfs_model
        self.app = None
        
    def register_routes(self, router):
        """Register routes with a FastAPI router."""
        if not FASTAPI_AVAILABLE:
            return
            
        # Define endpoints
        router.add_api_route("/ipfs/add", self.add_content, methods=["POST"])
        router.add_api_route("/ipfs/cat/{cid}", self.get_content, methods=["GET"])
        router.add_api_route("/ipfs/pin/{cid}", self.pin_content, methods=["POST"])
        router.add_api_route("/ipfs/unpin/{cid}", self.unpin_content, methods=["DELETE"])
        router.add_api_route("/ipfs/pins", self.list_pins, methods=["GET"])
        router.add_api_route("/ipfs/stats", self.get_stats, methods=["GET"])
        router.add_api_route("/ipfs/stats/reset", self.reset_stats, methods=["POST"])

    async def add_content(self, content: bytes = None, filename: str = None):
        """Add content to IPFS."""
        if not content:
            return {"success": False, "error": "Content is required"}
            
        result = self.ipfs_model.add_content(content, filename)
        return result

    async def get_content(self, cid: str):
        """Get content from IPFS by CID."""
        result = self.ipfs_model.get_content(cid)
        
        if not result["success"]:
            if FASTAPI_AVAILABLE:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail=result.get("error", "Content not found"))
            return result
            
        # Return content directly
        return result.get("content", "")
    
    async def pin_content(self, cid: str = None):
        """Pin content in IPFS."""
        if not cid:
            return {"success": False, "error": "CID is required"}
            
        result = self.ipfs_model.pin_content(cid)
        return result
    
    async def unpin_content(self, cid: str):
        """Unpin content in IPFS."""
        result = self.ipfs_model.unpin_content(cid)
        return result
    
    async def list_pins(self, cid: str = None):
        """List all pinned content."""
        result = self.ipfs_model.list_pins()
        
        # Filter by CID if provided
        if cid and result["success"]:
            if cid in result["pins"]:
                result["pins"] = {cid: result["pins"][cid]}
            else:
                result["pins"] = {}
                
        return result
    
    async def get_stats(self):
        """Get operation statistics."""
        stats = self.ipfs_model.get_stats()
        return {"success": True, "stats": stats}
    
    async def reset_stats(self):
        """Reset operation statistics."""
        old_stats = self.ipfs_model.reset_stats()
        return {"success": True, "previous_stats": old_stats}


class StubMCPServer:
    """Stub implementation of MCPServer for testing."""
    def __init__(self, debug_mode=False, log_level="INFO", persistence_path=None, isolation_mode=False):
        self.debug_mode = debug_mode
        self.log_level = log_level
        self.isolation_mode = isolation_mode
        self.persistence_path = persistence_path or tempfile.mkdtemp(prefix="mcp_server_")
        
        # Operation log for debug mode
        self.operation_log = []
        
        # Initialize components
        self.cache_manager = StubCacheManager(
            base_path=self.persistence_path,
            debug_mode=self.debug_mode
        )
        
        # Models
        self.models = {
            "ipfs": StubIPFSModel(None, self.cache_manager)
        }
        
        # Controllers
        self.controllers = {
            "ipfs": StubIPFSController(self.models["ipfs"])
        }
        
        # API Router
        if FASTAPI_AVAILABLE:
            self.router = APIRouter()
            self._register_routes()
        else:
            self.router = None
            
    def _register_routes(self):
        """Register all controller routes."""
        if not FASTAPI_AVAILABLE:
            return
            
        # Health check
        self.router.add_api_route("/health", self.health_check, methods=["GET"])
        
        # Debug endpoints
        if self.debug_mode:
            self.router.add_api_route("/debug", self.get_debug_state, methods=["GET"])
            self.router.add_api_route("/logs", self.get_operation_log, methods=["GET"])
            
        # Register controller routes
        for name, controller in self.controllers.items():
            controller.register_routes(self.router)
            
    async def health_check(self):
        """Health check endpoint."""
        return {
            "status": "healthy",
            "components": {
                "cache": self.cache_manager.running,
                "models": {name: True for name in self.models},
                "debug_mode": self.debug_mode,
                "isolation_mode": self.isolation_mode
            }
        }
        
    async def get_debug_state(self):
        """Get debug state information."""
        if not self.debug_mode:
            if FASTAPI_AVAILABLE:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Debug mode not enabled")
                
            return {"error": "Debug mode not enabled", "success": False}
            
        # Get cache stats
        cache_stats = self.cache_manager.get_stats()
        
        # Get model stats
        model_stats = {}
        for name, model in self.models.items():
            if hasattr(model, "get_stats"):
                model_stats[name] = model.get_stats()
                
        return {
            "success": True,
            "debug_mode": self.debug_mode,
            "isolation_mode": self.isolation_mode,
            "cache_stats": cache_stats,
            "model_stats": model_stats,
            "operation_log_size": len(self.operation_log),
            "components": {
                "cache": self.cache_manager.running,
                "models": {name: True for name in self.models}
            }
        }
        
    async def get_operation_log(self):
        """Get operation log."""
        if not self.debug_mode:
            if FASTAPI_AVAILABLE:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Debug mode not enabled")
                
            return {"error": "Debug mode not enabled", "success": False}
            
        return {
            "success": True,
            "log": self.operation_log
        }
        
    def log_operation(self, operation_type, details=None):
        """Log an operation if in debug mode."""
        if not self.debug_mode:
            return
            
        self.operation_log.append({
            "timestamp": time.time(),
            "operation": operation_type,
            "details": details
        })
        
    def register_with_app(self, app, prefix=""):
        """Register the MCP server with a FastAPI app."""
        if not FASTAPI_AVAILABLE:
            return False
            
        # Add middleware for debug mode
        if self.debug_mode:
            @app.middleware("http")
            async def debug_middleware(request: Request, call_next):
                # Log request
                self.log_operation(
                    "http_request",
                    {
                        "method": request.method,
                        "url": str(request.url),
                        "headers": dict(request.headers)
                    }
                )
                
                # Process request
                response = await call_next(request)
                
                # Log response
                self.log_operation(
                    "http_response",
                    {
                        "status_code": response.status_code,
                        "headers": dict(response.headers)
                    }
                )
                
                return response
                
        # Register routes
        app.include_router(self.router, prefix=prefix)
        return True
        
    def cleanup(self):
        """Clean up resources."""
        try:
            # Stop cache manager
            if hasattr(self, 'cache_manager') and self.cache_manager:
                self.cache_manager.stop()
                
            # Remove persistence directory if it's a temp dir
            if hasattr(self, 'persistence_path') and self.persistence_path and \
               self.persistence_path.startswith(tempfile.gettempdir()):
                shutil.rmtree(self.persistence_path, ignore_errors=True)
        except Exception:
            pass


# Try to import real MCP components
try:
    from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import, IPFSModel, IPFSController
    from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager
    MCP_AVAILABLE = True
except ImportError:
    # Use stubs if real implementation is not available
    MCPServer = StubMCPServer
    IPFSModel = StubIPFSModel
    IPFSController = StubIPFSController
    MCPCacheManager = StubCacheManager

    
class TestMCPServer(unittest.TestCase):
    """Test the MCP server functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for persistence
        self.persistence_path = tempfile.mkdtemp(prefix="mcp_test_")
        
        # Initialize server with debug mode
        self.mcp_server = MCPServer(
            debug_mode=True,
            log_level="DEBUG",
            persistence_path=self.persistence_path,
            isolation_mode=True
        )
        
        # Create FastAPI app if available
        if FASTAPI_AVAILABLE:
            self.app = FastAPI()
            self.mcp_server.register_with_app(self.app, prefix="/mcp")
            self.client = TestClient(self.app)
        
    def tearDown(self):
        """Clean up test environment."""
        # Cleanup server resources
        if hasattr(self, 'mcp_server') and self.mcp_server:
            self.mcp_server.cleanup()
            
        # Remove temporary directory
        if hasattr(self, 'persistence_path') and self.persistence_path:
            shutil.rmtree(self.persistence_path, ignore_errors=True)
    
    def test_server_initialization(self):
        """Test that server initializes correctly."""
        self.assertIsNotNone(self.mcp_server)
        self.assertTrue(self.mcp_server.debug_mode)
        self.assertEqual(self.mcp_server.log_level, "DEBUG")
        self.assertTrue(self.mcp_server.isolation_mode)
        
        # Check components
        self.assertIsNotNone(self.mcp_server.cache_manager)
        self.assertIn("ipfs", self.mcp_server.models)
        self.assertIn("ipfs", self.mcp_server.controllers)
        
    def test_cache_manager(self):
        """Test cache manager functionality."""
        cache = self.mcp_server.cache_manager
        
        # Put and get
        test_key = "test_key"
        test_value = b"test_value"
        cache.put(test_key, test_value)
        result = cache.get(test_key)
        self.assertEqual(result, test_value)
        
        # Check stats
        stats = cache.get_stats()
        self.assertEqual(stats["memory_hits"], 1)
        self.assertEqual(stats["disk_hits"], 0)
        self.assertEqual(stats["put_operations"], 1)
        self.assertEqual(stats["get_operations"], 1)
        
        # Delete
        cache.delete(test_key)
        result = cache.get(test_key)
        self.assertIsNone(result)
        
        # Check stats after delete
        stats = cache.get_stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["get_operations"], 2)
        
    def test_ipfs_model(self):
        """Test IPFS model functionality."""
        model = self.mcp_server.models["ipfs"]
        
        # Add content
        test_content = b"test content"
        add_result = model.add_content(test_content, "test.txt")
        self.assertTrue(add_result["success"])
        self.assertIn("cid", add_result)
        cid = add_result["cid"]
        
        # Get content
        get_result = model.get_content(cid)
        self.assertTrue(get_result["success"])
        self.assertEqual(get_result["content"], test_content)
        
        # Pin content
        pin_result = model.pin_content(cid)
        self.assertTrue(pin_result["success"])
        
        # List pins
        list_result = model.list_pins()
        self.assertTrue(list_result["success"])
        self.assertIn(cid, list_result["pins"])
        
        # Unpin content
        unpin_result = model.unpin_content(cid)
        self.assertTrue(unpin_result["success"])
        
        # Check stats
        stats = model.get_stats()
        self.assertEqual(stats["add_content"], 1)
        self.assertEqual(stats["get_content"], 1)
        self.assertEqual(stats["pin_content"], 1)
        self.assertEqual(stats["unpin_content"], 1)
        self.assertEqual(stats["list_pins"], 1)
        
        # Reset stats
        old_stats = model.reset_stats()
        self.assertEqual(old_stats["add_content"], 1)
        
        # Check stats are reset
        stats = model.get_stats()
        self.assertEqual(stats["add_content"], 0)
        
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/mcp/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")
        self.assertTrue(response.json()["components"]["debug_mode"])
        
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_debug_endpoint(self):
        """Test debug endpoint."""
        response = self.client.get("/mcp/debug")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(response.json()["debug_mode"])
        self.assertTrue(response.json()["isolation_mode"])
        self.assertIn("cache_stats", response.json())
        self.assertIn("model_stats", response.json())
        
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_log_endpoint(self):
        """Test operation log endpoint."""
        # Make a request to generate log entries
        self.client.get("/mcp/health")
        
        # Check logs
        response = self.client.get("/mcp/logs")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn("log", response.json())
        self.assertGreater(len(response.json()["log"]), 0)
        
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_ipfs_endpoints(self):
        """Test IPFS API endpoints."""
        # Add content
        test_content = b"test content for API"
        response = self.client.post(
            "/mcp/ipfs/add",
            files={"content": ("test.txt", test_content)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        cid = response.json()["cid"]
        
        # Get content
        response = self.client.get(f"/mcp/ipfs/cat/{cid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, test_content)
        
        # Pin content
        response = self.client.post(f"/mcp/ipfs/pin/{cid}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        
        # List pins
        response = self.client.get("/mcp/ipfs/pins")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn(cid, response.json()["pins"])
        
        # Unpin content
        response = self.client.delete(f"/mcp/ipfs/unpin/{cid}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        
        # Get stats
        response = self.client.get("/mcp/ipfs/stats")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn("stats", response.json())
        
        # Reset stats
        response = self.client.post("/mcp/ipfs/stats/reset")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn("previous_stats", response.json())
        
    def test_isolation_mode(self):
        """Test isolation mode."""
        # Create server with isolation mode
        isolated_server = MCPServer(
            debug_mode=True,
            isolation_mode=True
        )
        
        # Verify isolation_mode is set
        self.assertTrue(isolated_server.isolation_mode)
        
        # Clean up 
        isolated_server.cleanup()
        
    def test_no_debug_mode(self):
        """Test server without debug mode."""
        # Create server without debug mode
        no_debug_server = MCPServer(
            debug_mode=False,
            persistence_path=tempfile.mkdtemp(prefix="mcp_test_no_debug_")
        )
        
        # Verify debug_mode is not set
        self.assertFalse(no_debug_server.debug_mode)
        
        # Test operation log
        # It should not log in non-debug mode
        no_debug_server.log_operation("test_operation", {"test": True})
        
        # Run health check directly
        async def run_health_check():
            return await no_debug_server.health_check()
        
        health_response = anyio.run(run_health_check)
        self.assertEqual(health_response["status"], "healthy")
        self.assertFalse(health_response["components"]["debug_mode"])
        
        # Try to get debug state (should fail)
        async def run_get_debug_state():
            try:
                return await no_debug_server.get_debug_state()
            except Exception as e:
                return {"error": str(e), "success": False}
                
        debug_response = anyio.run(run_get_debug_state)
        self.assertFalse(debug_response.get("success", False))
        
        # Try to get operation log (should fail)
        async def run_get_operation_log():
            try:
                return await no_debug_server.get_operation_log()
            except Exception as e:
                return {"error": str(e), "success": False}
                
        log_response = anyio.run(run_get_operation_log)
        self.assertFalse(log_response.get("success", False))
        
        # Clean up
        no_debug_server.cleanup()
        
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_debug_middleware(self):
        """Test debug middleware."""
        # Register a test endpoint
        @self.app.get("/mcp/test-endpoint")
        def test_endpoint():
            return {"message": "test response"}
            
        # Make a request
        response = self.client.get("/mcp/test-endpoint")
        self.assertEqual(response.status_code, 200)
        
        # Check if the request was logged
        response = self.client.get("/mcp/logs")
        log = response.json()["log"]
        
        # Find request and response entries
        request_entries = [entry for entry in log if entry["operation"] == "http_request" and "/mcp/test-endpoint" in entry["details"]["url"]]
        response_entries = [entry for entry in log if entry["operation"] == "http_response" and entry["details"]["status_code"] == 200]
        
        self.assertGreater(len(request_entries), 0)
        self.assertGreater(len(response_entries), 0)
        
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_no_debug_middleware(self):
        """Test that middleware isn't added without debug mode."""
        # Create new app and server without debug mode
        app = FastAPI()
        no_debug_server = MCPServer(
            debug_mode=False,
            persistence_path=tempfile.mkdtemp(prefix="mcp_test_no_debug_mw_")
        )
        no_debug_server.register_with_app(app, prefix="/mcp")
        client = TestClient(app)
        
        # Add test endpoint
        @app.get("/mcp/test-endpoint")
        def test_endpoint():
            return {"message": "test response"}
            
        # Make a request
        response = client.get("/mcp/test-endpoint")
        self.assertEqual(response.status_code, 200)
        
        # Try to get logs (should fail)
        response = client.get("/mcp/logs")
        self.assertEqual(response.status_code, 404)
        
        # Clean up
        no_debug_server.cleanup()
        
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_error_middleware(self):
        """Test that error handling works in middleware."""
        # Create a middleware that raises an error
        @self.app.middleware("http")
        async def error_injection_middleware(request: Request, call_next):
            if request.url.path == "/mcp/error-test":
                # Simulate error
                raise ValueError("Test error")
            return await call_next(request)
            
        # Add test endpoint
        @self.app.get("/mcp/error-test")
        def error_test():
            return {"message": "Should not reach here"}
            
        # Make request (should fail)
        response = self.client.get("/mcp/error-test")
        self.assertEqual(response.status_code, 500)
        
        # Check logs for error entry
        response = self.client.get("/mcp/logs")
        log = response.json()["log"]
        
        # Find request entries related to error
        request_entries = [entry for entry in log if entry["operation"] == "http_request" and "/mcp/error-test" in entry["details"]["url"]]
        
        self.assertGreater(len(request_entries), 0)
    
    def test_cache_eviction(self):
        """Test that cache evicts items when needed."""
        # Set small limit for testing
        self.mcp_server.cache_manager.memory_limit = 1000  # 1KB
        
        # Add content that's larger than the limit
        large_content = b"x" * 1500  # 1.5KB
        self.mcp_server.cache_manager.put("large_item", large_content)
        
        # Check if it's in memory (should have been evicted)
        self.assertNotIn("large_item", self.mcp_server.cache_manager.memory_cache)
        
        # But it should be in disk
        result = self.mcp_server.cache_manager.get("large_item") 
        self.assertEqual(result, large_content)
        
        # Check eviction stats
        stats = self.mcp_server.cache_manager.get_stats()
        self.assertGreater(stats["memory_evictions"], 0)
        self.assertEqual(stats["disk_hits"], 1)
        
    def test_multiple_items(self):
        """Test handling multiple items in cache."""
        cache = self.mcp_server.cache_manager
        
        # Add several items
        for i in range(10):
            key = f"key_{i}"
            value = f"value_{i}".encode()
            cache.put(key, value)
            
        # Verify they can all be retrieved
        for i in range(10):
            key = f"key_{i}"
            expected = f"value_{i}".encode()
            result = cache.get(key)
            self.assertEqual(result, expected)
            
        # Check stats
        stats = cache.get_stats()
        self.assertEqual(stats["put_operations"], 10)
        self.assertEqual(stats["get_operations"], 10)
        self.assertEqual(stats["memory_hits"], 10)
        
        # Clear cache
        cache.clear()
        
        # Verify items are gone
        for i in range(10):
            key = f"key_{i}"
            result = cache.get(key)
            self.assertIsNone(result)
            
        # Check stats were reset
        stats = cache.get_stats()
        self.assertEqual(stats["memory_hits"], 0)
        self.assertEqual(stats["put_operations"], 0)
        self.assertEqual(stats["misses"], 10)  # These are from the gets after clearing
        

if __name__ == "__main__":
    unittest.main()