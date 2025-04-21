"""
Performance Optimization extension for MCP server (core implementation).

This module provides essential performance enhancements specified in the MCP roadmap
Q2 2025 priorities, focusing on the most critical features.

Features:
- Request load balancing across backends
- Simple caching system
- Basic connection management
"""

import os
import time
import json
import logging
import asyncio
import random
import hashlib
from typing import Dict, List, Any, Optional
from fastapi import (
from pydantic import BaseModel

APIRouter,
    Request,
    Response)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
CONFIG_FILE = "performance_config.json"
CACHE_DIR = "cache"
STATS_FILE = "performance_stats.json"

# Directory for performance optimization files
PERF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf_data")
os.makedirs(PERF_DIR, exist_ok=True)
CACHE_PATH = os.path.join(PERF_DIR, CACHE_DIR)
os.makedirs(CACHE_PATH, exist_ok=True)

# Full paths
CONFIG_PATH = os.path.join(PERF_DIR, CONFIG_FILE)
STATS_PATH = os.path.join(PERF_DIR, STATS_FILE)

# Storage backend attributes - will be populated from the MCP server
storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "huggingface": {"available": False, "simulation": True},
    "s3": {"available": False, "simulation": True},
    "filecoin": {"available": False, "simulation": True},
    "storacha": {"available": False, "simulation": True},
    "lassie": {"available": False, "simulation": True},
}

# Default performance configuration
DEFAULT_CONFIG = {
    "caching": {
        "enabled": True,
        "max_cache_size_mb": 1024,
        "default_ttl_seconds": 3600,
    },
    "load_balancing": {
        "enabled": True,
        "strategy": "adaptive",  # adaptive, round_robin, least_connections, weighted
        "backend_weights": {
            "ipfs": 10,
            "s3": 10,
            "filecoin": 5,
            "storacha": 8,
            "huggingface": 8,
            "lassie": 8,
        },
    },
    "connection_management": {"enabled": True, "max_connections_per_backend": 20},
}

# Default performance statistics
DEFAULT_STATS = {
    "caching": {"hits": 0, "misses": 0, "size_bytes": 0, "entries": 0},
    "load_balancing": {"requests_per_backend": {}, "errors_per_backend": {}},
    "uptime_seconds": 0,
    "start_time": time.time(),
}

# Runtime variables
config = DEFAULT_CONFIG.copy()
stats = DEFAULT_STATS.copy()
cache_entries = {}
backend_stats = {}
active_connections = {}


# Data models
class CacheConfig(BaseModel):
    """Cache configuration."""
    enabled: bool = True
    max_cache_size_mb: int = 1024
    default_ttl_seconds: int = 3600


class LoadBalancingConfig(BaseModel):
    """Load balancing configuration."""
    enabled: bool = True
    strategy: str = "adaptive"
    backend_weights: Dict[str, int] = {}


class ConnectionConfig(BaseModel):
    """Connection management configuration."""
    enabled: bool = True
    max_connections_per_backend: int = 20


class PerformanceStats(BaseModel):
    """Performance statistics."""
    cache_hits: int
    cache_misses: int
    cache_hit_ratio: float
    cache_size_mb: float
    cache_entries: int
    requests_per_backend: Dict[str, int]
    errors_per_backend: Dict[str, int]
    uptime_seconds: int


# Initialization functions
def initialize_config():
    """Initialize configuration from file or defaults."""
    global config
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            logger.info(f"Loaded performance configuration from {CONFIG_PATH}")
        else:
            config = DEFAULT_CONFIG.copy()
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Created default performance configuration in {CONFIG_PATH}")
    except Exception as e:
        logger.error(f"Error initializing performance configuration: {e}")
        config = DEFAULT_CONFIG.copy()


def initialize_stats():
    """Initialize performance statistics from file or defaults."""
    global stats
    try:
        if os.path.exists(STATS_PATH):
            with open(STATS_PATH, "r") as f:
                stats = json.load(f)
            logger.info(f"Loaded performance statistics from {STATS_PATH}")
        else:
            stats = DEFAULT_STATS.copy()
            stats["start_time"] = time.time()
            with open(STATS_PATH, "w") as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Created default performance statistics in {STATS_PATH}")
    except Exception as e:
        logger.error(f"Error initializing performance statistics: {e}")
        stats = DEFAULT_STATS.copy()
        stats["start_time"] = time.time()


def initialize_backend_stats():
    """Initialize backend statistics."""
    global backend_stats
    for backend in storage_backends:
        if storage_backends[backend]["available"]:
            backend_stats[backend] = {
                "latency_history": [],  # List of recent latency measurements
                "error_count": 0,  # Count of errors
                "request_count": 0,  # Count of requests
                "last_used": 0,  # Timestamp of last use
            }
    logger.info(f"Initialized backend statistics for {len(backend_stats)} backends")


def initialize_active_connections():
    """Initialize active connections tracking."""
    global active_connections
    for backend in storage_backends:
        if storage_backends[backend]["available"]:
            active_connections[backend] = 0
    logger.info(f"Initialized active connections tracking for {len(active_connections)} backends")


# Save functions
def save_config():
    """Save configuration to file."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")


def save_stats():
    """Save performance statistics to file."""
    try:
        # Update uptime
        stats["uptime_seconds"] = time.time() - stats["start_time"]

        with open(STATS_PATH, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving statistics: {e}")


# Core functionality
def get_cache_key(path: str, params: Dict = None) -> str:
    """Generate a cache key from request path and params."""
    key = path
    if params:
        # Sort params to ensure consistent keys
        sorted_params = sorted(params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        key += "?" + param_str
    return hashlib.md5(key.encode()).hexdigest()


async def get_from_cache(key: str) -> Optional[Dict[str, Any]]:
    """Get content from cache if available and not expired."""
    if not config["caching"]["enabled"] or key not in cache_entries:
        stats["caching"]["misses"] += 1
        return None

    try:
        entry = cache_entries[key]

        # Check if entry has expired
        if entry.get("expires_at", 0) < time.time():
            # Remove expired entry
            del cache_entries[key]

            # Try to delete the cache file
            file_path = os.path.join(CACHE_PATH, entry.get("filename", ""))
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing expired cache file: {e}")

            # Update stats
            stats["caching"]["misses"] += 1
            stats["caching"]["entries"] -= 1
            stats["caching"]["size_bytes"] -= entry.get("size", 0)

            return None

        # Read content from file
        file_path = os.path.join(CACHE_PATH, entry.get("filename", ""))
        if not os.path.exists(file_path):
            # File is missing, remove entry
            del cache_entries[key]
            stats["caching"]["misses"] += 1
            stats["caching"]["entries"] -= 1
            stats["caching"]["size_bytes"] -= entry.get("size", 0)
            return None

        with open(file_path, "rb") as f:
            content = f.read()

        # Update hit stats
        stats["caching"]["hits"] += 1

        return {
            "content": content,
            "content_type": entry.get("content_type", "application/octet-stream"),
            "size": len(content),
        }
    except Exception as e:
        logger.error(f"Error retrieving from cache: {e}")
        stats["caching"]["misses"] += 1
        return None


async def store_in_cache(key: str, content: bytes, content_type: str) -> bool:
    """Store content in cache."""
    if not config["caching"]["enabled"]:
        return False

    try:
        # Check cache size limit
        max_size_bytes = config["caching"]["max_cache_size_mb"] * 1024 * 1024
        if stats["caching"]["size_bytes"] + len(content) > max_size_bytes:
            # Simple cache eviction - remove oldest entries
            await prune_cache()

            # Check if we still have space
            if stats["caching"]["size_bytes"] + len(content) > max_size_bytes:
                return False

        # Generate a filename for the cache entry
        filename = f"cache_{key}_{int(time.time())}"
        file_path = os.path.join(CACHE_PATH, filename)

        # Write content to file
        with open(file_path, "wb") as f:
            f.write(content)

        # Create cache entry
        ttl = config["caching"]["default_ttl_seconds"]

        cache_entries[key] = {
            "filename": filename,
            "content_type": content_type,
            "size": len(content),
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
        }

        # Update stats
        stats["caching"]["entries"] += 1
        stats["caching"]["size_bytes"] += len(content)

        return True
    except Exception as e:
        logger.error(f"Error storing in cache: {e}")
        return False


async def prune_cache() -> int:
    """Remove old cache entries to free up space."""
    try:
        # Sort entries by creation time (oldest first)
        sorted_entries = sorted(cache_entries.items(), key=lambda x: x[1].get("created_at", 0))

        # Target removing 25% of cache
        target_count = max(1, len(sorted_entries) // 4)
        removed_count = 0
        freed_bytes = 0

        for key, entry in sorted_entries[:target_count]:
            # Remove entry
            del cache_entries[key]

            # Track stats
            freed_bytes += entry.get("size", 0)
            removed_count += 1

            # Delete cache file
            file_path = os.path.join(CACHE_PATH, entry.get("filename", ""))
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing cache file: {e}")

        # Update stats
        stats["caching"]["entries"] -= removed_count
        stats["caching"]["size_bytes"] -= freed_bytes

        logger.info(
            f"Pruned {removed_count} cache entries, freed {freed_bytes / (1024 * 1024):.2f} MB"
        )
        return removed_count
    except Exception as e:
        logger.error(f"Error pruning cache: {e}")
        return 0


def update_backend_stats(backend: str, latency_ms: float, success: bool = True):
    """Update backend statistics."""
    if backend not in backend_stats:
        backend_stats[backend] = {
            "latency_history": [],
            "error_count": 0,
            "request_count": 0,
            "last_used": 0,
        }

    # Update request count
    backend_stats[backend]["request_count"] += 1

    # Update global stats
    if backend not in stats["load_balancing"]["requests_per_backend"]:
        stats["load_balancing"]["requests_per_backend"][backend] = 0
    stats["load_balancing"]["requests_per_backend"][backend] += 1

    if success:
        # Update latency history (keep last 50 measurements)
        backend_stats[backend]["latency_history"].append(latency_ms)
        if len(backend_stats[backend]["latency_history"]) > 50:
            backend_stats[backend]["latency_history"] = backend_stats[backend]["latency_history"][
                -50:
            ]
    else:
        # Update error count
        backend_stats[backend]["error_count"] += 1

        # Update global error stats
        if backend not in stats["load_balancing"]["errors_per_backend"]:
            stats["load_balancing"]["errors_per_backend"][backend] = 0
        stats["load_balancing"]["errors_per_backend"][backend] += 1

    # Update last used timestamp
    backend_stats[backend]["last_used"] = time.time()


def select_backend(available_backends: List[str] = None) -> str:
    """Select a backend based on the configured strategy."""
    if not config["load_balancing"]["enabled"]:
        # If disabled, return first available backend
        for backend in storage_backends:
            if storage_backends[backend]["available"]:
                return backend
        return None

    # Get list of available backends
    if available_backends is None:
        available_backends = [b for b in storage_backends if storage_backends[b]["available"]]

    if not available_backends:
        return None

    # Use appropriate strategy
    strategy = config["load_balancing"]["strategy"]

    if strategy == "round_robin":
        # Simple round-robin
        # Use the global stats dictionary
        global stats
        counts = stats["load_balancing"].get("requests_per_backend", {})
        return min(available_backends, key=lambda b: counts.get(b, 0))

    elif strategy == "least_connections":
        # Choose backend with fewest active connections
        return min(available_backends, key=lambda b: active_connections.get(b, 0))

    elif strategy == "weighted":
        # Use configured weights
        weights = config["load_balancing"]["backend_weights"]
        weighted_backends = [(b, weights.get(b, 5)) for b in available_backends]

        # Simple weighted random selection
        total_weight = sum(w for _, w in weighted_backends)
        r = random.uniform(0, total_weight)
        current = 0
        for backend, weight in weighted_backends:
            current += weight
            if r <= current:
                return backend

        # Fallback
        return available_backends[0]

    else:  # "adaptive" (default)
        scores = {}

        for backend in available_backends:
            # Start with base weight
            base_weight = config["load_balancing"]["backend_weights"].get(backend, 5)

            # Calculate score based on stats
            if backend in backend_stats:
                stats = backend_stats[backend]

                # Factor 1: Average latency (lower is better)
                latency_score = 10
                if stats["latency_history"]:
                    avg_latency = sum(stats["latency_history"]) / len(stats["latency_history"])
                    # Scale: 0-100ms -> 10-0 points
                    latency_score = max(0, 10 - avg_latency / 10)

                # Factor 2: Error rate (lower is better)
                error_score = 10
                if stats["request_count"] > 0:
                    error_rate = stats["error_count"] / stats["request_count"]
                    # Scale: 0-10% -> 10-0 points
                    error_score = max(0, 10 - error_rate * 100)

                # Combine factors
                scores[backend] = (base_weight + latency_score + error_score) / 3
            else:
                # No stats yet, use base weight
                scores[backend] = base_weight

        # Choose backend with highest score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

        # Fallback to first available
        return available_backends[0]


def track_connection(backend: str, increment: bool = True):
    """Track active connections to a backend."""
    if backend not in active_connections:
        active_connections[backend] = 0

    if increment:
        active_connections[backend] += 1
    else:
        active_connections[backend] = max(0, active_connections[backend] - 1)


# Create router
def create_performance_router(api_prefix: str) -> APIRouter:
    """Create FastAPI router for performance endpoints."""
    router = APIRouter(prefix=f"{api_prefix}/performance", tags=["performance"])

    @router.get("/status")
    async def get_performance_status():
        """Get performance optimization status."""
        # Calculate cache hit ratio
        hits = stats["caching"]["hits"]
        misses = stats["caching"]["misses"]
        hit_ratio = hits / (hits + misses) if (hits + misses) > 0 else 0

        # Calculate uptime
        uptime = int(time.time() - stats["start_time"])

        return {
            "success": True,
            "uptime_seconds": uptime,
            "caching": {
                "enabled": config["caching"]["enabled"],
                "hits": hits,
                "misses": misses,
                "hit_ratio": hit_ratio,
                "size_mb": stats["caching"]["size_bytes"] / (1024 * 1024),
                "entries": stats["caching"]["entries"],
            },
            "load_balancing": {
                "enabled": config["load_balancing"]["enabled"],
                "strategy": config["load_balancing"]["strategy"],
                "active_backends": len(,
                    [b for b in storage_backends if storage_backends[b]["available"]]
                ),
            },
            "connection_management": {
                "enabled": config["connection_management"]["enabled"],
                "total_active_connections": sum(active_connections.values()),
            },
        }

    @router.get("/config")
    async def get_performance_config():
        """Get performance configuration."""
        return {"success": True, "config": config}

    @router.put("/config/caching")
    async def update_caching_config(cache_config: CacheConfig):
        """Update caching configuration."""
        config["caching"]["enabled"] = cache_config.enabled
        config["caching"]["max_cache_size_mb"] = cache_config.max_cache_size_mb
        config["caching"]["default_ttl_seconds"] = cache_config.default_ttl_seconds

        save_config()

        return {"success": True, "message": "Caching configuration updated"}

    @router.put("/config/load_balancing")
    async def update_load_balancing_config(lb_config: LoadBalancingConfig):
        """Update load balancing configuration."""
        config["load_balancing"]["enabled"] = lb_config.enabled
        config["load_balancing"]["strategy"] = lb_config.strategy

        # Update weights if provided
        if lb_config.backend_weights:
            config["load_balancing"]["backend_weights"] = lb_config.backend_weights

        save_config()

        return {"success": True, "message": "Load balancing configuration updated"}

    @router.put("/config/connection")
    async def update_connection_config(conn_config: ConnectionConfig):
        """Update connection management configuration."""
        config["connection_management"]["enabled"] = conn_config.enabled
        config["connection_management"][
            "max_connections_per_backend"
        ] = conn_config.max_connections_per_backend

        save_config()

        return {
            "success": True,
            "message": "Connection management configuration updated",
        }

    @router.get("/cache/entries")
    async def list_cache_entries(limit: int = 100, offset: int = 0):
        """List cache entries."""
        entries = list(cache_entries.items())

        # Sort by creation time (newest first)
        entries.sort(key=lambda x: x[1].get("created_at", 0), reverse=True)

        # Apply pagination
        paginated = entries[offset : offset + limit]

        return {
            "success": True,
            "entries": [,
                {
                    "key": key,
                    "content_type": entry.get("content_type"),
                    "size_bytes": entry.get("size"),
                    "created_at": entry.get("created_at"),
                    "expires_at": entry.get("expires_at"),
                }
                for key, entry in paginated
            ],
            "total": len(entries),
            "offset": offset,
            "limit": limit,
        }

    @router.delete("/cache/clear")
    async def clear_cache():
        """Clear all cache entries."""
        try:
            # Count entries before clearing
            entry_count = len(cache_entries)
            total_size = stats["caching"]["size_bytes"]

            # Delete all cache files
            for entry in cache_entries.values():
                file_path = os.path.join(CACHE_PATH, entry.get("filename", ""))
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error removing cache file: {e}")

            # Clear cache entries
            cache_entries.clear()

            # Reset stats
            stats["caching"]["entries"] = 0
            stats["caching"]["size_bytes"] = 0

            return {
                "success": True,
                "message": f"Cleared {entry_count} cache entries ({total_size / (1024 * 1024):.2f} MB)",
            }
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return {"success": False, "error": str(e)}

    @router.get("/backends/status")
    async def get_backend_status():
        """Get status of all backends with performance metrics."""
        backend_status = {}

        for backend, info in storage_backends.items():
            if not info["available"]:
                backend_status[backend] = {"available": False}
                continue

            stats_info = backend_stats.get(backend, {})

            # Calculate average latency
            latency_history = stats_info.get("latency_history", [])
            avg_latency = sum(latency_history) / len(latency_history) if latency_history else 0

            # Calculate error rate
            request_count = stats_info.get("request_count", 0)
            error_count = stats_info.get("error_count", 0)
            error_rate = error_count / request_count if request_count > 0 else 0

            backend_status[backend] = {
                "available": True,
                "active_connections": active_connections.get(backend, 0),
                "avg_latency_ms": avg_latency,
                "error_rate": error_rate,
                "request_count": request_count,
                "last_used": stats_info.get("last_used", 0),
            }

        return {
            "success": True,
            "backends": backend_status,
            "load_balancing_strategy": config["load_balancing"]["strategy"],
        }

    @router.post("/backends/reset_stats")
    async def reset_backend_stats():
        """Reset backend performance statistics."""
        global backend_stats

        # Reinitialize backend stats
        initialize_backend_stats()

        # Reset load balancing stats in global stats
        stats["load_balancing"]["requests_per_backend"] = {}
        stats["load_balancing"]["errors_per_backend"] = {}

        return {"success": True, "message": "Backend statistics reset successfully"}

    return router


# Simple middleware
async def cache_middleware(request: Request, call_next):
    """Middleware for caching responses."""
    if not config["caching"]["enabled"] or request.method != "GET":
        return await call_next(request)

    try:
        # Create cache key from path and query params
        cache_key = get_cache_key(str(request.url.path), dict(request.query_params))

        # Try to get from cache
        cached = await get_from_cache(cache_key)

        if cached:
            # Return cached response
            content = cached["content"]
            content_type = cached["content_type"]

            response = Response(content=content, media_type=content_type)

            # Add cache header
            response.headers["X-Cache"] = "HIT"

            return response

        # Cache miss, proceed with request
        response = await call_next(request)

        # Add cache header
        response.headers["X-Cache"] = "MISS"

        # Only cache successful responses
        if response.status_code == 200:
            # Get response content and content type
            content_type = response.headers.get("content-type", "application/octet-stream")

            # Only cache certain content types
            cacheable_types = [
                "text/",
                "application/json",
                "image/",
                "application/octet-stream",
            ]
            is_cacheable = any(content_type.startswith(t) for t in cacheable_types)

            if is_cacheable:
                # Get response body
                body = b""

                # Read response body
                async for chunk in response.body_iterator:
                    body += chunk

                # Store in cache
                await store_in_cache(cache_key, body, content_type)

                # Create new response with same content
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=content_type,
                )

        return response
    except Exception as e:
        logger.error(f"Error in cache middleware: {e}")
        return await call_next(request)


async def load_balancing_middleware(request: Request, call_next):
    """Middleware for tracking backend usage."""
    response = await call_next(request)

    try:
        # Extract backend from path if possible
        path = request.url.path
        backend = None

        for b in storage_backends:
            if f"/{b}/" in path:
                backend = b
                break

        if backend and storage_backends.get(backend, {}).get("available", False):
            # Record backend usage
            latency_ms = response.headers.get("X-Response-Time-MS")
            if latency_ms:
                try:
                    latency = float(latency_ms)
                    update_backend_stats(backend, latency, success=(response.status_code < 500))
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error in load balancing middleware: {e}")

    return response


async def connection_middleware(request: Request, call_next):
    """Middleware for connection tracking."""
    # Extract backend from path if possible
    path = request.url.path
    backend = None

    for b in storage_backends:
        if f"/{b}/" in path:
            backend = b
            break

    if backend and storage_backends.get(backend, {}).get("available", False):
        # Track connection
        track_connection(backend, True)

        try:
            # Process request
            response = await call_next(request)
            return response
        finally:
            # Release connection
            track_connection(backend, False)
    else:
        # Process request normally
        return await call_next(request)


# Register middleware
def register_middlewares(app):
    """Register performance middlewares with the app."""
    # Add middlewares in order
    app.middleware("http")(connection_middleware)
    app.middleware("http")(load_balancing_middleware)
    app.middleware("http")(cache_middleware)


# Periodic tasks
async def periodic_stats_save():
    """Periodically save statistics."""
    while True:
        try:
            save_stats()
            await asyncio.sleep(60)  # Save every minute
        except Exception as e:
            logger.error(f"Error in periodic stats save: {e}")
            await asyncio.sleep(60)


# Start background tasks
def start_background_tasks(app):
    """Start background tasks for the performance extension."""
    @app.on_event("startup")
    async def startup_event():
        # Start periodic stats save
        asyncio.create_task(periodic_stats_save())

    @app.on_event("shutdown")
    async def shutdown_event():
        # Save final stats
        save_stats()


# Update storage backends status
def update_performance_status(storage_backends_info: Dict[str, Any]) -> None:
    """Update the reference to storage backends status."""
    global storage_backends
    storage_backends = storage_backends_info

    # Reset active connections for backends that are no longer available
    for backend in list(active_connections.keys()):
        if backend not in storage_backends or not storage_backends[backend]["available"]:
            active_connections[backend] = 0


# Initialize
def initialize():
    """Initialize the performance optimization system."""
    initialize_config()
    initialize_stats()
    initialize_backend_stats()
    initialize_active_connections()
    logger.info("Performance optimization system initialized")


# Call initialization
initialize()
