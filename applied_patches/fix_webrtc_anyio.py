#!/usr/bin/env python3
"""
Fix the WebRTC AnyIO controller's check_dependencies method to handle missing methods.
"""

import os
import sys
import shutil
import logging
import time
import re

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix_webrtc_anyio")

# File path
WEBRTC_CONTROLLER_PATH = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/webrtc_controller_anyio.py"

# Make a backup
def backup_file(file_path):
    if os.path.exists(file_path):
        backup_path = f"{file_path}.bak.{int(time.time())}"
        logger.info(f"Creating backup of {file_path} to {backup_path}")
        shutil.copy2(file_path, backup_path)
        return True
    else:
        logger.error(f"File not found: {file_path}")
        return False

# Fix the check_dependencies method
def fix_check_dependencies():
    logger.info("Fixing WebRTC controller's check_dependencies method...")
    
    if not backup_file(WEBRTC_CONTROLLER_PATH):
        return False
    
    try:
        # Read the file
        with open(WEBRTC_CONTROLLER_PATH, 'r') as f:
            content = f.read()
        
        # Find and update the method
        pattern = r'async def check_dependencies.*?\n    # Add your AnyIO-compatible controller methods here'
        replacement = '''async def check_dependencies(self):
        """
        Check if all required WebRTC dependencies are available.
        
        Returns:
            Dictionary with dependency status information
        """
        logger.debug("Checking WebRTC dependencies")
        
        try:
            # Try to use the anyio-compatible version first
            if hasattr(self.ipfs_model, 'check_webrtc_dependencies_anyio'):
                return await anyio.to_thread.run_sync(self.ipfs_model.check_webrtc_dependencies_anyio)
            
            # Fall back to the sync version
            elif hasattr(self.ipfs_model, 'check_webrtc_dependencies'):
                return await anyio.to_thread.run_sync(self.ipfs_model.check_webrtc_dependencies)
            
            # Create a basic response if no method is available
            else:
                logger.warning("No WebRTC dependency check method available in the model")
                return {
                    "success": False,
                    "webrtc_available": False,
                    "error": "No WebRTC dependency check method available",
                    "dependencies": {
                        "numpy": False,
                        "opencv": False,
                        "av": False,
                        "aiortc": False,
                        "websockets": False,
                        "notifications": False
                    }
                }
        except Exception as e:
            logger.error(f"Error checking WebRTC dependencies: {e}")
            return {
                "success": False,
                "webrtc_available": False,
                "error": f"Error checking dependencies: {str(e)}",
                "error_type": type(e).__name__
            }
            
    # Add your AnyIO-compatible controller methods here'''
        
        # Replace the method
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        # Write the updated content
        with open(WEBRTC_CONTROLLER_PATH, 'w') as f:
            f.write(new_content)
        
        logger.info("✅ Successfully fixed check_dependencies method")
        return True
    
    except Exception as e:
        logger.error(f"Error fixing check_dependencies method: {e}")
        return False

def main():
    logger.info("Running WebRTC AnyIO controller fix...")
    
    # Fix check_dependencies method
    if fix_check_dependencies():
        logger.info("✅ Successfully fixed WebRTC AnyIO controller")
        return 0
    else:
        logger.error("❌ Failed to fix WebRTC AnyIO controller")
        return 1

if __name__ == "__main__":
    sys.exit(main())