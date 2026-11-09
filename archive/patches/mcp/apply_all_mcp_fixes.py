#!/usr/bin/env python3
"""
Master script to apply all MCP server refactoring fixes.

This script runs all the necessary patches in the correct order to fix the issues
that arose after the MCP server refactoring.
"""

import os
import subprocess
import sys
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure we're working from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

# Define the scripts to run in order
SCRIPTS = [
    # First organize patches
    Path("patches/organize_patches.py"),
    
    # Fix initialization files
    Path("patches/mcp/fix_init_files.py"),
    
    # Ensure controllers are properly implemented
    Path("patches/mcp/ensure_controllers.py"),
    
    # Fix server bridge for compatibility
    Path("patches/mcp/fix_server_bridge.py"),
    
    # Migrate tests to proper locations
    Path("patches/mcp/migrate_tests.py"),
    
    # Apply specific MCP fixes
    Path("patches/mcp/fix_mcp_server_refactoring.py"),
]

def run_script(script_path):
    """Run a script and handle any errors."""
    full_path = PROJECT_ROOT / script_path
    
    if not full_path.exists():
        logger.warning(f"Script not found: {full_path}")
        return False
    
    try:
        logger.info(f"Running: {script_path}")
        result = subprocess.run([sys.executable, str(full_path)], 
                                check=True, 
                                capture_output=True, 
                                text=True)
        logger.info(f"Output: {result.stdout}")
        
        if result.stderr:
            logger.warning(f"Stderr: {result.stderr}")
        
        return True
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running {script_path}: {e}")
        logger.error(f"Output: {e.stdout}")
        logger.error(f"Error: {e.stderr}")
        return False

def apply_all_patches():
    """Apply all patches in the correct order."""
    logger.info("Starting MCP server refactoring fixes...")
    
    success_count = 0
    failure_count = 0
    
    for script in SCRIPTS:
        if run_script(script):
            success_count += 1
        else:
            failure_count += 1
            
    logger.info(f"Completed running {len(SCRIPTS)} scripts.")
    logger.info(f"Successful: {success_count}, Failed: {failure_count}")
    
    return failure_count == 0

if __name__ == "__main__":
    try:
        if apply_all_patches():
            logger.info("All MCP server refactoring fixes applied successfully!")
            sys.exit(0)
        else:
            logger.error("Some patches failed to apply.")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Unhandled error applying patches: {e}")
        sys.exit(1)