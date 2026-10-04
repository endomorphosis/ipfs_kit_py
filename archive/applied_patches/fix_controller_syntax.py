#!/usr/bin/env python3
"""Fix syntax error in IPFS controller file."""
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fix_controller_syntax")

def fix_syntax_error():
    """Fix syntax error in IPFSController."""
    controller_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py"

    # Read the entire file
    with open(controller_path, "r") as f:
        content = f.read()

    # Find the check_daemon_status method
    start_index = content.find("async def check_daemon_status")
    if start_index == -1:
        logger.error("Could not find check_daemon_status method")
        return False

    # Find the end of the method
    next_method = content.find("async def", start_index + 1)
    if next_method == -1:
        # If there's no next method, use the end of the file
        method_content = content[start_index:]
    else:
        method_content = content[start_index:next_method]

    # Check if there's a try without a matching except
    if "try:" in method_content and "except" not in method_content:
        logger.info("Found try without except - adding except block")
        # Add the missing except block
        fixed_content = content.replace(
            "                result[\"status_code\"] = 200 if result.get(\"success\", False) else 500",
            """                result["status_code"] = 200 if result.get("success", False) else 500
                
                return result
        except Exception as e:
            # Handle any exceptions that occur during processing
            logger.error(f"Error checking daemon status: {str(e)}")
            result = {
                "success": False,
                "operation": "check_daemon_status",
                "error": str(e),
                "error_type": type(e).__name__,
                "daemon_status": {"overall": "unknown"},
                "status_code": 500
            }
            return result"""
        )
        
        # Write the fixed content back to the file
        with open(controller_path, "w") as f:
            f.write(fixed_content)
        
        logger.info("Successfully fixed syntax error in controller")
        return True
    else:
        logger.warning("Could not identify the syntax issue")
        return False

if __name__ == "__main__":
    logger.info("Starting controller syntax fix...")
    success = fix_syntax_error()
    if success:
        logger.info("✅ Syntax error fixed successfully")
    else:
        logger.error("❌ Failed to fix syntax error")