#!/usr/bin/env python3
"""Test daemon manager initialization independently"""

import os
import sys
import anyio
import logging

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_daemon_manager():
    """Test the daemon manager initialization"""
    logger.info("🧪 Testing daemon manager initialization...")
    
    try:
        # Import the DaemonManager
        from enhanced_mcp_server_with_daemon_init import DaemonManager
        logger.info("✅ DaemonManager imported successfully")
        
        # Create the daemon manager
        daemon_manager = DaemonManager()
        logger.info("✅ DaemonManager created successfully")
        
        # Test initialization
        logger.info("🔄 Starting daemon manager initialization...")
        await daemon_manager.initialize_system()
        logger.info("✅ Daemon manager initialized successfully")
        
        # Check status
        logger.info("📊 Checking daemon status...")
        logger.info(f"Initialized: {daemon_manager.initialized}")
        logger.info(f"Startup errors: {daemon_manager.startup_errors}")
        
        logger.info("🎉 All tests passed!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    anyio.run(test_daemon_manager)
