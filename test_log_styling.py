#!/usr/bin/env python3
"""
Test script to generate log entries with different severity levels
to test the enhanced log styling in the dashboard.
"""

import requests
import time
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_log_styling():
    """Generate various log entries to test CSS styling."""
    
    print("🧪 Testing Enhanced Log Styling")
    print("=" * 50)
    
    # Generate logs with different severity levels
    logger.debug("This is a DEBUG message for testing purposes")
    logger.info("Starting health check for test backend")
    logger.warning("Health check completed - Status: unconfigured, Health: unhealthy")
    logger.error("FILE: not found - Critical configuration missing")
    logger.critical("CRITICAL ERROR: System component failure detected!")
    
    time.sleep(1)
    
    # Generate more diverse log entries
    logger.info("✅ Vector search engine initialized successfully")
    logger.warning("⚠️ Some vector collections are empty")
    logger.error("❌ Failed to connect to knowledge graph database")
    logger.info("📊 Processing 1,234 documents in vector index")
    logger.warning("🔍 Search query timeout after 30 seconds")
    logger.error("💥 Memory allocation failed for large vector batch")
    
    print("\n📊 Log entries generated with different severity levels:")
    print("  🔵 DEBUG - System debugging information")
    print("  🟢 INFO - General information messages") 
    print("  🟡 WARNING - Warning conditions")
    print("  🔴 ERROR - Error conditions")
    print("  🟣 CRITICAL - Critical error conditions")
    
    print("\n🌐 Dashboard should now show:")
    print("  • Color-coded log entries with enhanced styling")
    print("  • Fixed bottom stats bar with counts")
    print("  • Proper spacing and visual hierarchy")
    print("\n📍 Open dashboard at: http://127.0.0.1:8765")
    print("📍 Navigate to 'Logs' tab to see the styling")

if __name__ == "__main__":
    test_log_styling()
