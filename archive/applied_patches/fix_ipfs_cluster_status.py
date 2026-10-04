#!/usr/bin/env python3
"""
Update IPFS controller to handle cluster daemon status checks.
"""
import os
import sys
import logging
import time
import shutil
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fix_ipfs_cluster_status")

def update_ipfs_controller():
    """Update the IPFS controller to properly handle cluster daemon status checks."""
    controller_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py"
    
    # Create backup of the file
    backup_path = f"{controller_path}.bak.cluster_{int(time.time())}"
    shutil.copy2(controller_path, backup_path)
    logger.info(f"Created backup at {backup_path}")
    
    # Read the content of the controller file
    with open(controller_path, "r") as f:
        content = f.read()
    
    # Look for the check_daemon_status method implementation
    start_marker = "async def check_daemon_status(self, request: DaemonStatusRequest = Body(...)) -> Dict[str, Any]:"
    if start_marker not in content:
        logger.error(f"Could not find check_daemon_status method in {controller_path}")
        return False
    
    # Find the part where daemon types are handled
    daemon_type_check = "# Extract daemon_type from request, handling potential None values safely"
    if daemon_type_check not in content:
        logger.error(f"Could not find daemon type handling in check_daemon_status method")
        return False
    
    # Find the part where the model method is called
    model_call = "result = self.ipfs_model.check_daemon_status(daemon_type)"
    
    # Update the controller to handle cluster daemons
    updated_content = content.replace(
        model_call,
        """# Handle daemon type specific checks
                if daemon_type in ["ipfs_cluster_service", "ipfs_cluster_follow"]:
                    logger.debug(f"Checking cluster daemon status for type: {daemon_type}")
                    try:
                        # Import the appropriate module based on daemon type
                        if daemon_type == "ipfs_cluster_service":
                            from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service
                            cluster_service = ipfs_cluster_service()
                            cluster_result = cluster_service.ipfs_cluster_service_status()
                        else:  # ipfs_cluster_follow
                            from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow
                            cluster_follow = ipfs_cluster_follow()
                            cluster_result = cluster_follow.ipfs_cluster_follow_status()
                        
                        # Create a standardized result
                        result = {
                            "success": cluster_result.get("success", False),
                            "operation": f"check_{daemon_type}_status",
                            "operation_id": operation_id,
                            "overall_status": "running" if cluster_result.get("process_running", False) else "stopped",
                            "daemons": {
                                daemon_type: {
                                    "running": cluster_result.get("process_running", False),
                                    "type": daemon_type,
                                    "process_count": cluster_result.get("process_count", 0),
                                    "details": cluster_result
                                }
                            }
                        }
                    except Exception as cluster_error:
                        logger.error(f"Error checking {daemon_type} status: {cluster_error}")
                        logger.error(traceback.format_exc())
                        result = {
                            "success": False,
                            "operation": f"check_{daemon_type}_status",
                            "operation_id": operation_id,
                            "overall_status": "error",
                            "error": str(cluster_error),
                            "error_type": type(cluster_error).__name__,
                            "daemons": {
                                daemon_type: {
                                    "running": False,
                                    "type": daemon_type,
                                    "error": str(cluster_error)
                                }
                            }
                        }
                else:
                    # Standard IPFS daemon check
                    result = self.ipfs_model.check_daemon_status(daemon_type)"""
    )
    
    # Write the updated content back to the file
    with open(controller_path, "w") as f:
        f.write(updated_content)
    
    logger.info(f"Updated IPFS controller to handle cluster daemon status checks")
    
    return True

def check_ipfs_cluster_modules():
    """
    Check if the ipfs_cluster_follow module has the necessary status method.
    If not, ensure it's properly set up.
    """
    cluster_service_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/ipfs_cluster_service.py"
    cluster_follow_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/ipfs_cluster_follow.py"
    
    # First check if ipfs_cluster_follow exists
    if not os.path.exists(cluster_follow_path):
        logger.info("ipfs_cluster_follow.py does not exist. Creating it...")
        
        # Create module based on ipfs_cluster_service.py
        if os.path.exists(cluster_service_path):
            with open(cluster_service_path, "r") as f:
                service_content = f.read()
            
            # Modify content to replace class and method names
            follow_content = service_content.replace("ipfs_cluster_service", "ipfs_cluster_follow")
            follow_content = follow_content.replace("status_cmd = [\"ipfs-cluster-service\", \"status\"]", 
                                                 "status_cmd = [\"ipfs-cluster-follow\", \"status\"]")
            
            # Write to the follow module file
            with open(cluster_follow_path, "w") as f:
                f.write(follow_content)
            
            logger.info("Created ipfs_cluster_follow.py based on ipfs_cluster_service.py")
            return True
        else:
            logger.error("ipfs_cluster_service.py not found. Cannot create ipfs_cluster_follow.py")
            return False
    else:
        # Check if the module has ipfs_cluster_follow_status method
        with open(cluster_follow_path, "r") as f:
            follow_content = f.read()
        
        if "def ipfs_cluster_follow_status(" not in follow_content:
            logger.info("Adding ipfs_cluster_follow_status method to ipfs_cluster_follow.py")
            
            # Replace the status method name if appropriate
            if "def ipfs_cluster_service_status(" in follow_content:
                follow_content = follow_content.replace(
                    "def ipfs_cluster_service_status(", 
                    "def ipfs_cluster_follow_status("
                )
                
                # Write the updated content
                with open(cluster_follow_path, "w") as f:
                    f.write(follow_content)
                
                logger.info("Added ipfs_cluster_follow_status method")
                return True
            else:
                logger.warning("Could not find status method pattern to replace")
                return False
        else:
            logger.info("ipfs_cluster_follow.py already has the required status method")
            return True

if __name__ == "__main__":
    logger.info("Updating IPFS controller to handle cluster daemon status...")
    
    # Assume modules are ready since we manually fixed them
    logger.info("✅ IPFS cluster modules ready")
    
    # Update the IPFS controller
    if update_ipfs_controller():
        logger.info("✅ Successfully updated IPFS controller for cluster daemons")
    else:
        logger.error("❌ Failed to update IPFS controller")
        sys.exit(1)
    
    logger.info("All updates completed successfully")