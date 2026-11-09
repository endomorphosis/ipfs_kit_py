#!/usr/bin/env python3
"""
Demo script showing the enhanced backend configuration and monitoring system.

This demonstrates:
1. ~/.ipfs_kit/ metadata-first approach
2. Unified dashboard API  
3. Backend configuration management
4. Enhanced monitoring with quota/storage stats
"""

import sys
import os
import json
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, '.')

from ipfs_kit_py.metadata_manager import get_metadata_manager
from ipfs_kit_py.mcp_metadata_wrapper import get_metadata_first_mcp


def demo_metadata_first_backend_management():
    """Demonstrate the metadata-first backend management."""
    print("=" * 60)
    print("IPFS Kit Enhanced Backend Configuration Demo")
    print("=" * 60)
    
    # Get the metadata manager
    manager = get_metadata_manager()
    mcp_wrapper = get_metadata_first_mcp()
    
    print(f"✓ Using ~/.ipfs_kit/ directory: {manager.base_dir}")
    print(f"✓ Directory exists: {manager.base_dir.exists()}")
    
    # Demo 1: Add multiple backend configurations
    print("\n--- Demo 1: Adding Backend Configurations ---")
    
    backend_configs = {
        "aws-s3-prod": {
            "type": "s3",
            "enabled": True,
            "endpoint": "https://s3.amazonaws.com",
            "region": "us-east-1",
            "bucket": "production-ipfs",
            "access_key": "${AWS_ACCESS_KEY}",
            "secret_key": "${AWS_SECRET_KEY}",
            "quota_limit": "100GB"
        },
        "huggingface-models": {
            "type": "huggingface",
            "enabled": True,
            "endpoint": "https://huggingface.co",
            "token": "${HUGGING_FACE_TOKEN}",
            "cache_dir": str(manager.cache_dir / "huggingface"),
            "quota_limit": "50GB"
        },
        "local-storage": {
            "type": "filesystem",
            "enabled": True,
            "path": "/data/ipfs-storage",
            "quota_limit": "500GB"
        }
    }
    
    for backend_id, config in backend_configs.items():
        success = manager.set_backend_config(backend_id, config)
        print(f"  ✓ Added {backend_id}: {success}")
    
    # Demo 2: List and inspect backends
    print("\n--- Demo 2: Backend Management ---")
    
    backends = manager.list_backends()
    print(f"Available backends: {backends}")
    
    for backend_id in backends:
        config = manager.get_backend_config(backend_id)
        if config:
            backend_type = config["config"]["type"]
            enabled = config["config"]["enabled"]
            quota = config["config"].get("quota_limit", "No limit")
            print(f"  • {backend_id} ({backend_type}): {'Enabled' if enabled else 'Disabled'}, Quota: {quota}")
    
    # Demo 3: Metadata-first MCP operations
    print("\n--- Demo 3: Metadata-First MCP Operations ---")
    
    # Simulate metadata-first backend retrieval
    print("Testing metadata-first backend retrieval:")
    for backend_id in ["aws-s3-prod", "huggingface-models"]:
        config = mcp_wrapper.get_backend_config_metadata_first(backend_id)
        if config:
            print(f"  ✓ Found {backend_id} in metadata (type: {config['config']['type']})")
        else:
            print(f"  ✗ {backend_id} not found")
    
    # Demo 4: Global settings management
    print("\n--- Demo 4: Global Settings ---")
    
    # Set some global settings
    settings = {
        "monitoring_interval": 60,
        "auto_cleanup_days": 30,
        "default_cache_size": "2GB",
        "log_level": "INFO",
        "dashboard_refresh_rate": 5
    }
    
    for key, value in settings.items():
        manager.set_global_setting(key, value)
        print(f"  ✓ Set {key}: {value}")
    
    # Retrieve and display settings
    all_config = manager.get_all_config()
    print(f"\nCurrent global settings:")
    for key, value in all_config.get("global_settings", {}).items():
        print(f"  • {key}: {value}")
    
    # Demo 5: Simulate backend statistics
    print("\n--- Demo 5: Backend Statistics Simulation ---")
    
    # Store some sample monitoring data
    sample_stats = {
        "aws-s3-prod": {
            "status": "healthy",
            "storage": {
                "used_space": 45 * 1024 * 1024 * 1024,  # 45GB
                "total_space": 100 * 1024 * 1024 * 1024,  # 100GB
                "files_count": 15420,
                "usage_percent": 45
            },
            "quota": {
                "limit": 100 * 1024 * 1024 * 1024,  # 100GB
                "used": 45 * 1024 * 1024 * 1024,   # 45GB
                "remaining": 55 * 1024 * 1024 * 1024,  # 55GB
                "usage_percent": 45
            },
            "performance": {
                "avg_response_time": 0.234,
                "success_rate": 99.8,
                "error_count": 12
            }
        },
        "huggingface-models": {
            "status": "healthy",
            "storage": {
                "used_space": 23 * 1024 * 1024 * 1024,  # 23GB
                "total_space": 50 * 1024 * 1024 * 1024,  # 50GB
                "files_count": 342,
                "usage_percent": 46
            },
            "quota": {
                "limit": 50 * 1024 * 1024 * 1024,  # 50GB
                "used": 23 * 1024 * 1024 * 1024,   # 23GB
                "remaining": 27 * 1024 * 1024 * 1024,  # 27GB
                "usage_percent": 46
            },
            "performance": {
                "avg_response_time": 1.123,
                "success_rate": 97.2,
                "error_count": 48
            }
        }
    }
    
    # Store stats as metadata
    for backend_id, stats in sample_stats.items():
        manager.set_metadata(f"backend_stats_{backend_id}", stats)
        print(f"  ✓ Stored stats for {backend_id}")
    
    # Display formatted stats
    print("\nBackend Statistics:")
    for backend_id, stats in sample_stats.items():
        storage = stats["storage"]
        quota = stats["quota"]
        perf = stats["performance"]
        
        print(f"\n  {backend_id.upper()}:")
        print(f"    Status: {stats['status']}")
        print(f"    Storage: {format_bytes(storage['used_space'])} / {format_bytes(storage['total_space'])} ({storage['usage_percent']}%)")
        print(f"    Files: {storage['files_count']:,}")
        print(f"    Quota: {quota['usage_percent']}% used ({format_bytes(quota['remaining'])} remaining)")
        print(f"    Performance: {perf['avg_response_time']*1000:.0f}ms avg, {perf['success_rate']}% success")
    
    # Demo 6: Show directory structure
    print("\n--- Demo 6: Directory Structure ---")
    print(f"\n~/.ipfs_kit/ structure:")
    show_directory_tree(manager.base_dir)
    
    print("\n" + "=" * 60)
    print("✓ Demo completed successfully!")
    print("✓ Metadata-first MCP approach is working")
    print("✓ Backend configurations are managed in ~/.ipfs_kit/")
    print("✓ Enhanced monitoring data is available")
    print("=" * 60)


def format_bytes(bytes_value):
    """Format bytes in human-readable form."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f}{unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f}PB"


def show_directory_tree(path, prefix="", max_depth=3, current_depth=0):
    """Show directory tree structure."""
    if current_depth >= max_depth:
        return
        
    try:
        items = sorted(path.iterdir())
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            print(f"{prefix}{current_prefix}{item.name}")
            
            if item.is_dir() and current_depth < max_depth - 1:
                extension = "    " if is_last else "│   "
                show_directory_tree(item, prefix + extension, max_depth, current_depth + 1)
            elif item.is_file():
                # Show file size
                size = item.stat().st_size
                print(f"{prefix}{'    ' if is_last else '│   '}    ({format_bytes(size)})")
    except PermissionError:
        print(f"{prefix}    [Permission Denied]")


if __name__ == "__main__":
    demo_metadata_first_backend_management()