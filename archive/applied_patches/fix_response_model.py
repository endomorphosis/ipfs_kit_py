#!/usr/bin/env python3
"""
Fix MCP IPFS Controller to handle daemon status response validation.
"""
import os
import time
import logging
import shutil
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix_response_model")

def fix_ipfs_controller():
    """Fix the IPFS controller implementation to handle daemon status response validation."""
    controller_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py"
    
    # Create backup of original file
    timestamp = int(time.time())
    backup_path = f"{controller_path}.bak.{timestamp}"
    shutil.copy2(controller_path, backup_path)
    logger.info(f"Created backup of {controller_path} to {backup_path}")
    
    # Read the original file
    with open(controller_path, 'r') as f:
        content = f.read()
    
    # First add the import for Optional
    if "from typing import Optional" not in content:
        content = content.replace(
            "from typing import Dict, List, Any, Union",
            "from typing import Dict, List, Any, Union, Optional"
        )
    
    # Update response model for daemon status endpoint
    content = content.replace(
        "class DaemonStatusResponse(BaseModel):\n    \"\"\"Response model for daemon status check.\"\"\"\n    success: bool\n    daemon_status: Dict[str, Any]\n    status_code: int",
        "class DaemonStatusResponse(BaseModel):\n    \"\"\"Response model for daemon status check.\"\"\"\n    success: bool\n    daemon_status: Optional[Dict[str, Any]] = None\n    status_code: Optional[int] = None\n    operation: Optional[str] = None\n    operation_id: Optional[str] = None\n    timestamp: Optional[float] = None\n    overall_status: Optional[str] = None\n    daemons: Optional[Dict[str, Any]] = None\n    daemon_type: Optional[str] = None\n    running_count: Optional[int] = None\n    daemon_count: Optional[int] = None\n    duration_ms: Optional[float] = None"
    )
    
    # Write the updated content
    with open(controller_path, 'w') as f:
        f.write(content)
    logger.info("Updated IPFS controller response model")
    
    # Fix the check_daemon_status method
    # Read the updated file
    with open(controller_path, 'r') as f:
        content = f.read()
    
    # Find the check_daemon_status method
    method_pattern = re.compile(r'async def check_daemon_status\([^)]*\).*?return result', re.DOTALL)
    method_match = method_pattern.search(content)
    
    if not method_match:
        logger.warning("Could not find check_daemon_status method in controller")
        return False
    
    # Extract the current method
    current_method = method_match.group(0)
    
    # Create updated method
    updated_method = current_method.replace(
        "return result",
        """# Transform result to match the response model expectations
        # If result doesn't already have daemon_status, add it
        if "daemon_status" not in result:
            result["daemon_status"] = {
                "overall": result.get("overall_status", "unknown"),
                "daemons": result.get("daemons", {})
            }
        
        # Add status code if missing
        if "status_code" not in result:
            result["status_code"] = 200 if result.get("success", False) else 500
            
        return result"""
    )
    
    # Replace the method in the content
    updated_content = content.replace(current_method, updated_method)
    
    # Check if update was successful
    if updated_content != content:
        with open(controller_path, 'w') as f:
            f.write(updated_content)
        logger.info("Successfully updated check_daemon_status method in controller")
        return True
    else:
        logger.warning("No changes made to check_daemon_status method")
        return False

if __name__ == "__main__":
    logger.info("Starting MCP IPFS controller fixes...")
    success = fix_ipfs_controller()
    
    if success:
        logger.info("✅ Fixed IPFS controller response model")
        logger.info("Restart the MCP server to apply changes")
    else:
        logger.error("❌ Failed to fix IPFS controller")