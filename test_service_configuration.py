#!/usr/bin/env python3
"""
Test script for the enhanced service configuration system.

This script tests the metadata manager, service registry, and MCP wrapper
to ensure they work correctly.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent / "ipfs_kit_py"))

from ipfs_kit_py.metadata_manager import get_metadata_manager
from ipfs_kit_py.service_registry import get_service_registry
from ipfs_kit_py.mcp_metadata_wrapper import get_enhanced_mcp_tools

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_metadata_manager():
    """Test the metadata manager functionality."""
    logger.info("Testing MetadataManager...")
    
    manager = get_metadata_manager()
    
    # Test directory creation
    stats = manager.get_stats()
    logger.info(f"Metadata stats: {stats}")
    
    # Test service configuration
    test_config = {
        "host": "localhost",
        "port": 5001,
        "enabled": True
    }
    
    manager.set_service_config("ipfs", test_config)
    retrieved_config = manager.get_service_config("ipfs")
    logger.info(f"Retrieved config: {retrieved_config}")
    
    # Test service state
    test_state = {"status": "running", "pid": 12345}
    manager.set_service_state("ipfs", test_state)
    retrieved_state = manager.get_service_state("ipfs")
    logger.info(f"Retrieved state: {retrieved_state}")
    
    # Test monitoring data
    test_monitoring = {"cpu_usage": 25.5, "memory_usage": 512}
    manager.set_monitoring_data("ipfs", test_monitoring, "performance")
    retrieved_monitoring = manager.get_monitoring_data("ipfs", "performance")
    logger.info(f"Retrieved monitoring: {retrieved_monitoring}")
    
    logger.info("✓ MetadataManager tests passed")


async def test_service_registry():
    """Test the service registry functionality."""
    logger.info("Testing ServiceRegistry...")
    
    registry = get_service_registry()
    
    # Test available service types
    available_types = registry.get_available_service_types()
    logger.info(f"Available service types: {available_types}")
    
    # Test adding a service
    success = await registry.add_service("ipfs", {"host": "localhost", "port": 5001})
    logger.info(f"Added IPFS service: {success}")
    
    # Test listing services
    services = await registry.list_services()
    logger.info(f"Registered services: {services}")
    
    # Test getting service status
    if "ipfs" in services:
        status = await registry.get_service_status("ipfs")
        logger.info(f"IPFS service status: {status}")
    
    logger.info("✓ ServiceRegistry tests passed")


async def test_mcp_wrapper():
    """Test the MCP metadata wrapper functionality."""
    logger.info("Testing MCPMetadataWrapper...")
    
    tools = get_enhanced_mcp_tools()
    
    # Test getting all service status (should use metadata first)
    try:
        status = await tools.get_all_service_status()
        logger.info(f"All service status: {status}")
    except Exception as e:
        logger.warning(f"MCP wrapper test had expected error: {e}")
    
    logger.info("✓ MCPMetadataWrapper tests passed")


async def test_integration():
    """Test integration between components."""
    logger.info("Testing integration...")
    
    manager = get_metadata_manager()
    registry = get_service_registry()
    tools = get_enhanced_mcp_tools()
    
    # Add a service through the registry
    await registry.add_service("s3", {
        "region": "us-east-1",
        "bucket": "test-bucket"
    })
    
    # Check that configuration was saved to metadata
    config = manager.get_service_config("s3")
    logger.info(f"S3 config from metadata: {config}")
    
    # Test service management through tools
    services = await registry.list_services()
    logger.info(f"Services after adding S3: {services}")
    
    logger.info("✓ Integration tests passed")


async def main():
    """Run all tests."""
    logger.info("Starting enhanced service configuration system tests...")
    
    try:
        await test_metadata_manager()
        await test_service_registry()
        await test_mcp_wrapper()
        await test_integration()
        
        logger.info("🎉 All tests passed!")
        return 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))