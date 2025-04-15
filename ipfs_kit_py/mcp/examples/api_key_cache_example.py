#!/usr/bin/env python3
"""
Enhanced API Key Cache Example

This example demonstrates how to use the enhanced API key caching system
to improve performance for API key validation in MCP Server.

Key features demonstrated:
1. Setting up the enhanced API key cache
2. Patching the auth service for seamless integration
3. Using the cache in FastAPI endpoints
4. Cache monitoring and performance analysis
5. Different integration approaches

Usage:
  python api_key_cache_example.py
"""

import asyncio
import time
import json
import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("api-key-cache-example")

# Try importing FastAPI for the web server example
try:
    from fastapi import FastAPI, Depends, Header, HTTPException, Request
    from fastapi.responses import JSONResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    logger.warning("FastAPI not available. Web server example will be skipped.")
    FASTAPI_AVAILABLE = False

# Try importing Redis for the distributed cache example
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    logger.warning("Redis not available. Distributed cache example will be skipped.")
    REDIS_AVAILABLE = False

# Import our cache implementation
from ipfs_kit_py.mcp.auth.enhanced_api_key_cache import EnhancedApiKeyCache, CachePolicy
from ipfs_kit_py.mcp.auth.api_key_cache_integration import (
    ApiKeyCacheService, 
    patch_auth_service,
    require_api_key,
    create_api_key_validation_middleware,
    get_api_key_cache_service
)

# --------------------------------
# Mock Authentication Service
# --------------------------------
class MockAuthService:
    """Mock authentication service for demonstration purposes."""
    
    def __init__(self):
        """Initialize the mock auth service with some test API keys."""
        # Simulate a database of API keys
        self.api_keys = {
            "ipfk_test1": {
                "id": "key1",
                "key": "ipfk_test1",
                "user_id": "user1",
                "name": "Test Key 1",
                "active": True,
                "scopes": ["read", "write"],
                "permissions": ["storage:read", "storage:write"],
                "created_at": time.time() - 86400,  # 1 day ago
                "expires_at": time.time() + 86400,  # Expires in 1 day
                "last_used": None,
                "allowed_ips": ["127.0.0.1", "192.168.0.0/16"]
            },
            "ipfk_test2": {
                "id": "key2",
                "key": "ipfk_test2",
                "user_id": "user2",
                "name": "Test Key 2",
                "active": True,
                "scopes": ["read"],
                "permissions": ["storage:read"],
                "created_at": time.time() - 172800,  # 2 days ago
                "expires_at": None,  # Never expires
                "last_used": None,
                "allowed_ips": []
            },
            "ipfk_inactive": {
                "id": "key3",
                "key": "ipfk_inactive",
                "user_id": "user1",
                "name": "Inactive Key",
                "active": False,
                "scopes": ["read", "write"],
                "permissions": ["storage:read", "storage:write"],
                "created_at": time.time() - 86400,
                "expires_at": None,
                "last_used": None,
                "allowed_ips": []
            },
            "ipfk_expired": {
                "id": "key4",
                "key": "ipfk_expired",
                "user_id": "user2",
                "name": "Expired Key",
                "active": True,
                "scopes": ["read"],
                "permissions": ["storage:read"],
                "created_at": time.time() - 172800,
                "expires_at": time.time() - 86400,  # Expired 1 day ago
                "last_used": None,
                "allowed_ips": []
            }
        }
        
        # Invalidation hooks for cache integration
        self._invalidation_hooks = []
    
    async def verify_api_key(self, api_key: str, ip_address: Optional[str] = None) -> tuple:
        """
        Verify an API key - simulates database lookup.
        
        Args:
            api_key: API key to verify
            ip_address: Optional client IP address
            
        Returns:
            Tuple of (valid, key_data, error_message)
        """
        # Simulate database lookup latency (100-300ms)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Check if key exists
        if api_key not in self.api_keys:
            return False, None, "Invalid API key"
        
        key_data = self.api_keys[api_key]
        
        # Check if key is active
        if not key_data["active"]:
            return False, None, "API key is inactive"
        
        # Check expiration
        expiration = key_data.get("expires_at")
        if expiration and time.time() > expiration:
            return False, None, "API key has expired"
        
        # Check IP restrictions
        if ip_address and key_data.get("allowed_ips"):
            # Simple IP check for demonstration
            if key_data["allowed_ips"] and ip_address not in key_data["allowed_ips"]:
                return False, None, "Client IP not allowed"
        
        # Update last used time
        key_data["last_used"] = time.time()
        
        return True, key_data, None
    
    async def update_api_key_last_used(self, key_id: str) -> None:
        """Update the last used timestamp for an API key."""
        # Find the key by ID
        for key, data in self.api_keys.items():
            if data["id"] == key_id:
                data["last_used"] = time.time()
                break
    
    def register_key_invalidation_hook(self, hook_function):
        """Register a function to be called when an API key is invalidated."""
        self._invalidation_hooks.append(hook_function)
    
    def invalidate_key(self, key_id: str) -> None:
        """Invalidate an API key."""
        # Notify all registered hooks
        for hook in self._invalidation_hooks:
            hook(key_id)
    
    def create_key(self, key_data: dict) -> dict:
        """Create a new API key."""
        if "key" not in key_data:
            key_data["key"] = f"ipfk_{random.randbytes(16).hex()}"
        
        if "id" not in key_data:
            key_data["id"] = f"key{len(self.api_keys) + 1}"
        
        if "created_at" not in key_data:
            key_data["created_at"] = time.time()
        
        self.api_keys[key_data["key"]] = key_data
        return key_data

# --------------------------------
# Performance Testing Functions
# --------------------------------
async def benchmark_standard_validation(auth_service, iterations=1000):
    """Benchmark standard API key validation without caching."""
    logger.info(f"Starting standard validation benchmark ({iterations} iterations)...")
    
    start_time = time.time()
    valid_count = 0
    
    for _ in range(iterations):
        # Mix of valid and invalid keys
        key = random.choice(["ipfk_test1", "ipfk_test2", "ipfk_invalid", "ipfk_inactive", "ipfk_expired"])
        valid, _, _ = await auth_service.verify_api_key(key)
        if valid:
            valid_count += 1
    
    duration = time.time() - start_time
    avg_ms = (duration / iterations) * 1000
    
    logger.info(f"Standard validation: {iterations} validations in {duration:.2f}s ({avg_ms:.2f}ms avg)")
    logger.info(f"Valid keys: {valid_count}, Invalid keys: {iterations - valid_count}")
    
    return {"duration": duration, "avg_ms": avg_ms, "valid_count": valid_count}

async def benchmark_cached_validation(cache_service, iterations=1000):
    """Benchmark API key validation with caching."""
    logger.info(f"Starting cached validation benchmark ({iterations} iterations)...")
    
    # First pass to warm up the cache
    for _ in range(10):
        key = random.choice(["ipfk_test1", "ipfk_test2", "ipfk_invalid", "ipfk_inactive", "ipfk_expired"])
        await cache_service.validate_api_key(key)
    
    # Benchmark
    start_time = time.time()
    valid_count = 0
    
    for _ in range(iterations):
        # Mix of valid and invalid keys
        key = random.choice(["ipfk_test1", "ipfk_test2", "ipfk_invalid", "ipfk_inactive", "ipfk_expired"])
        valid, _, _ = await cache_service.validate_api_key(key)
        if valid:
            valid_count += 1
    
    duration = time.time() - start_time
    avg_ms = (duration / iterations) * 1000
    
    logger.info(f"Cached validation: {iterations} validations in {duration:.2f}s ({avg_ms:.2f}ms avg)")
    logger.info(f"Valid keys: {valid_count}, Invalid keys: {iterations - valid_count}")
    
    # Get cache stats
    stats = cache_service.get_cache_stats()
    logger.info(f"Cache stats: {stats}")
    
    return {"duration": duration, "avg_ms": avg_ms, "valid_count": valid_count, "stats": stats}

# --------------------------------
# FastAPI Example
# --------------------------------
def create_fastapi_app(auth_service):
    """Create a FastAPI application with API key caching."""
    if not FASTAPI_AVAILABLE:
        logger.error("FastAPI is not available. Cannot create app.")
        return None
    
    app = FastAPI(title="API Key Cache Example", version="1.0.0")
    
    # Create and configure the API key cache service
    cache_service = ApiKeyCacheService(
        auth_service=auth_service,
        cache_size=1000,
        ttl_seconds=3600,
        enable_metrics=True,
        enable_rate_limiting=True,
        max_requests_per_minute=60
    )
    
    # Add middleware for API key validation
    app.middleware("http")(create_api_key_validation_middleware(cache_service))
    
    # Define some example endpoints
    @app.get("/")
    async def root():
        """Public endpoint that doesn't require an API key."""
        return {"message": "Welcome to the API Key Cache Example"}
    
    @app.get("/secure")
    async def secure_endpoint(request: Request):
        """Secure endpoint that requires an API key."""
        # API key validation is handled by middleware
        # If execution reaches here, the API key is valid
        key_data = getattr(request.state, "api_key_data", {})
        return {
            "message": "Successfully accessed secure endpoint",
            "key_id": key_data.get("id"),
            "user_id": key_data.get("user_id"),
            "scopes": key_data.get("scopes")
        }
    
    @app.get("/admin")
    @require_api_key(cache_service, required_permissions=["admin"])
    async def admin_endpoint(request: Request):
        """Admin endpoint that requires specific permissions."""
        return {"message": "Admin access granted"}
    
    @app.get("/write")
    @require_api_key(cache_service, required_scopes=["write"])
    async def write_endpoint(request: Request):
        """Endpoint that requires write scope."""
        return {"message": "Write access granted"}
    
    @app.get("/read")
    @require_api_key(cache_service, required_scopes=["read"])
    async def read_endpoint(request: Request):
        """Endpoint that requires read scope."""
        return {"message": "Read access granted"}
    
    @app.get("/cache/stats")
    async def cache_stats():
        """Get cache statistics."""
        return cache_service.get_cache_stats()
    
    @app.post("/cache/invalidate/{key_id}")
    async def invalidate_key(key_id: str):
        """Invalidate a cached API key."""
        auth_service.invalidate_key(key_id)
        return {"message": f"Invalidated key {key_id}"}
    
    @app.post("/cache/invalidate_all")
    async def invalidate_all():
        """Invalidate all cached API keys."""
        cache_service.invalidate_all()
        return {"message": "Invalidated all keys"}
    
    return app

# --------------------------------
# Example Use Case: Distributed Cache with Redis
# --------------------------------
async def demonstrate_distributed_cache():
    """Demonstrate using the cache with Redis for distributed deployments."""
    if not REDIS_AVAILABLE:
        logger.warning("Redis not available. Skipping distributed cache example.")
        return
    
    logger.info("Demonstrating distributed cache with Redis...")
    
    # Create a Redis client
    redis_client = redis.Redis(host="localhost", port=6379, db=0)
    
    try:
        # Check if Redis is available
        redis_client.ping()
        
        # Create auth service
        auth_service = MockAuthService()
        
        # Create cache service with Redis
        cache_service = ApiKeyCacheService(
            auth_service=auth_service,
            cache_size=1000,
            ttl_seconds=3600,
            redis_client=redis_client,
            enable_metrics=True
        )
        
        # Test caching - Node 1
        logger.info("Node 1: First validation (not cached)")
        start = time.time()
        valid1, data1, _ = await cache_service.validate_api_key("ipfk_test1")
        duration1 = time.time() - start
        
        logger.info(f"Node 1: First validation took {duration1*1000:.2f}ms, valid={valid1}")
        
        # Simulate validation from another node
        logger.info("Node 2: Validate same key (should hit Redis cache)")
        
        # Create a separate cache service (simulating another node)
        node2_cache = ApiKeyCacheService(
            auth_service=auth_service,
            cache_size=1000,
            ttl_seconds=3600,
            redis_client=redis_client,
            enable_metrics=True
        )
        
        start = time.time()
        valid2, data2, _ = await node2_cache.validate_api_key("ipfk_test1")
        duration2 = time.time() - start
        
        logger.info(f"Node 2: Validation took {duration2*1000:.2f}ms, valid={valid2}")
        logger.info(f"Node 2: Cache performance improvement: {duration1/duration2:.1f}x faster")
        
        # Demonstrate invalidation across nodes
        logger.info("Node 1: Invalidating key...")
        auth_service.invalidate_key("key1")
        
        # Check that it's invalidated on both nodes
        logger.info("Node 2: Checking if key is invalidated...")
        cache_hit, _ = node2_cache.cache.get(node2_cache.cache.hash_token("ipfk_test1"))
        logger.info(f"Node 2: Key in cache: {cache_hit}")
        
        # Show Redis keys
        logger.info("Redis keys:")
        for key in redis_client.keys("mcp:apikey:*"):
            logger.info(f"  {key}")
        
    except redis.exceptions.ConnectionError:
        logger.error("Could not connect to Redis. Is it running?")
    
    finally:
        redis_client.close()

# --------------------------------
# Main Example Function
# --------------------------------
async def run_example():
    """Run the example to demonstrate API key caching."""
    logger.info("Starting API Key Cache Example")
    
    # Create a mock auth service
    auth_service = MockAuthService()
    
    # Benchmark standard validation (without cache)
    standard_results = await benchmark_standard_validation(auth_service)
    
    # Creating the API key cache
    logger.info("Creating enhanced API key cache")
    cache_service = ApiKeyCacheService(
        auth_service=auth_service,
        cache_size=1000, 
        ttl_seconds=3600,
        negative_ttl=300,
        enable_metrics=True,
        enable_rate_limiting=False
    )
    
    # Benchmark cached validation
    cached_results = await benchmark_cached_validation(cache_service)
    
    # Calculate improvement
    speedup = standard_results["avg_ms"] / cached_results["avg_ms"]
    logger.info(f"Performance improvement with cache: {speedup:.1f}x faster")
    
    # Demonstrate key scopes/permissions validation
    logger.info("\nDemonstrating API key validation with scopes and permissions:")
    
    # Test with read scope
    valid, data, error = await cache_service.validate_api_key(
        "ipfk_test1", 
        required_scopes=["read"]
    )
    logger.info(f"Key with read scope: valid={valid}, error={error}")
    
    # Test with write scope (should fail for ipfk_test2)
    valid, data, error = await cache_service.validate_api_key(
        "ipfk_test2", 
        required_scopes=["write"]
    )
    logger.info(f"Key without write scope: valid={valid}, error={error}")
    
    # Demonstrate IP restrictions
    logger.info("\nDemonstrating IP restrictions:")
    valid, data, error = await cache_service.validate_api_key(
        "ipfk_test1", 
        ip_address="10.0.0.1"  # Not in allowed IPs
    )
    logger.info(f"Key with IP restriction: valid={valid}, error={error}")
    
    valid, data, error = await cache_service.validate_api_key(
        "ipfk_test1", 
        ip_address="192.168.1.1"  # Matches 192.168.0.0/16
    )
    logger.info(f"Key with matching IP: valid={valid}, error={error}")
    
    # Demonstrate service patching approach
    logger.info("\nDemonstrating auth service patching approach:")
    
    # Create a new mock auth service
    new_auth_service = MockAuthService()
    
    # Time verification without patching
    start = time.time()
    await new_auth_service.verify_api_key("ipfk_test1")
    original_duration = time.time() - start
    logger.info(f"Original verification: {original_duration*1000:.2f}ms")
    
    # Patch the service
    patched_service = patch_auth_service(new_auth_service)
    
    # Time verification after patching
    start = time.time()
    await patched_service.verify_api_key("ipfk_test1")
    patched_duration = time.time() - start
    logger.info(f"First patched verification: {patched_duration*1000:.2f}ms")
    
    # Second verification should be cached
    start = time.time()
    await patched_service.verify_api_key("ipfk_test1")
    cached_duration = time.time() - start
    logger.info(f"Second patched verification (cached): {cached_duration*1000:.2f}ms")
    logger.info(f"Improvement after caching: {original_duration/cached_duration:.1f}x faster")
    
    # Show cache stats
    logger.info("\nCache statistics:")
    stats = patched_service.api_key_cache.get_cache_stats()
    logger.info(json.dumps(stats, indent=2))
    
    # Demonstrate distributed cache if Redis is available
    await demonstrate_distributed_cache()

# --------------------------------
# FastAPI Server Example
# --------------------------------
def run_fastapi_example():
    """Run a FastAPI server with API key caching."""
    if not FASTAPI_AVAILABLE:
        logger.error("FastAPI is not available. Cannot run web server example.")
        return
    
    # Create a mock auth service
    auth_service = MockAuthService()
    
    # Create the FastAPI app
    app = create_fastapi_app(auth_service)
    
    # Run the server
    logger.info("\nStarting FastAPI server with API key caching...")
    logger.info("Try accessing endpoints with these API keys:")
    logger.info("  - X-API-Key: ipfk_test1 (has read+write scopes)")
    logger.info("  - X-API-Key: ipfk_test2 (has read scope only)")
    logger.info("  - X-API-Key: ipfk_invalid (invalid key)")
    logger.info("  - X-API-Key: ipfk_inactive (inactive key)")
    logger.info("  - X-API-Key: ipfk_expired (expired key)")
    logger.info("\nAvailable endpoints:")
    logger.info("  - GET / (public)")
    logger.info("  - GET /secure (requires valid API key)")
    logger.info("  - GET /admin (requires admin permission)")
    logger.info("  - GET /write (requires write scope)")
    logger.info("  - GET /read (requires read scope)")
    logger.info("  - GET /cache/stats (view cache statistics)")
    logger.info("  - POST /cache/invalidate/{key_id} (invalidate key)")
    logger.info("  - POST /cache/invalidate_all (invalidate all keys)")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)

# --------------------------------
# Main Entry Point
# --------------------------------
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--server":
        # Run FastAPI server example
        run_fastapi_example()
    else:
        # Run async example
        asyncio.run(run_example())
        
        # Inform about server option
        if FASTAPI_AVAILABLE:
            print("\nRun with --server flag to start a FastAPI server demonstration:")
            print("  python api_key_cache_example.py --server")
