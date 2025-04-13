#!/usr/bin/env python3
"""
Script to fix the MCP server's daemon status handling.
This will patch both the controller and model implementations to ensure compatibility.
"""

import sys
import os
import logging
import time
import json
import shutil
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix_mcp_server")

# Make backups before modification
def backup_file(file_path):
    """Make a backup of the file before modification."""
    if os.path.exists(file_path):
        backup_path = f"{file_path}.bak.{int(time.time())}"
        logger.info(f"Creating backup of {file_path} to {backup_path}")
        shutil.copy2(file_path, backup_path)
        return True
    else:
        logger.error(f"File not found: {file_path}")
        return False

# Fix the IPFS controller implementation
def fix_ipfs_controller():
    """Fix the IPFS controller implementation of the check_daemon_status endpoint."""
    controller_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py"
    
    if not backup_file(controller_path):
        return False
        
    try:
        with open(controller_path, 'r') as f:
            content = f.read()
            
        # Find the check_daemon_status method
        if "async def check_daemon_status" in content:
            logger.info("Found check_daemon_status method in controller")
            
            # Add detailed error handling around the model call
            old_code = """async def check_daemon_status(self, request: DaemonStatusRequest = Body(...)) -> Dict[str, Any]:
        \"\"\"
        Check status of IPFS daemons.
        
        Args:
            request: Request with optional daemon type to check
            
        Returns:
            Dictionary with daemon status information
        \"\"\"
        daemon_type = request.daemon_type
        logger.debug(f"Checking daemon status for: {daemon_type or 'all daemons'}")
        
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"check_daemon_{int(start_time * 1000)}"
        
        try:
            # Call IPFS model to check daemon status
            result = self.ipfs_model.check_daemon_status(daemon_type)"""
            
            new_code = """async def check_daemon_status(self, request: DaemonStatusRequest = Body(...)) -> Dict[str, Any]:
        \"\"\"
        Check status of IPFS daemons.
        
        Args:
            request: Request with optional daemon type to check
            
        Returns:
            Dictionary with daemon status information
        \"\"\"
        # Start timing for operation metrics
        start_time = time.time()
        operation_id = f"check_daemon_{int(start_time * 1000)}"
        
        try:
            # Extract daemon_type from request, handling potential None values safely
            daemon_type = getattr(request, 'daemon_type', None)
            logger.debug(f"Checking daemon status for: {daemon_type or 'all daemons'}")
            
            # Call IPFS model to check daemon status with detailed error logging
            try:
                logger.debug(f"Calling ipfs_model.check_daemon_status with daemon_type={daemon_type}")
                result = self.ipfs_model.check_daemon_status(daemon_type)
                logger.debug(f"check_daemon_status result: {result}")
            except Exception as model_error:
                logger.error(f"Error in model.check_daemon_status: {model_error}")
                logger.error(traceback.format_exc())
                raise model_error"""
                
            # Replace the method implementation
            new_content = content.replace(old_code, new_code)
            
            if new_content != content:
                with open(controller_path, 'w') as f:
                    f.write(new_content)
                logger.info("Successfully updated IPFS controller implementation")
                return True
            else:
                logger.warning("Failed to update controller - content unchanged")
                return False
        else:
            logger.error("Could not find check_daemon_status method in controller")
            return False
            
    except Exception as e:
        logger.error(f"Error fixing IPFS controller: {e}")
        logger.error(traceback.format_exc())
        return False

# Fix the IPFS model implementation
def fix_ipfs_model():
    """Fix the IPFS model implementation of the check_daemon_status method."""
    model_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/ipfs_model.py"
    
    if not backup_file(model_path):
        return False
        
    try:
        with open(model_path, 'r') as f:
            content = f.read()
            
        # Find the check_daemon_status method
        if "def check_daemon_status(self, daemon_type: str = None)" in content:
            logger.info("Found check_daemon_status method in model")
            
            # Add debug logging and additional error handling
            old_code = """def check_daemon_status(self, daemon_type: str = None) -> Dict[str, Any]:
        \"\"\"
        Check the status of IPFS daemons.
        
        Args:
            daemon_type: Optional daemon type to check (ipfs, ipfs_cluster_service, etc.)
            
        Returns:
            Dictionary with daemon status information
        \"\"\"
        operation_id = f"check_daemon_status_{int(time.time() * 1000)}"
        start_time = time.time()
        
        result = {
            "success": False,
            "operation": "check_daemon_status",
            "operation_id": operation_id,
            "timestamp": time.time(),
            "overall_status": "unknown"
        }
        
        if daemon_type:
            result["daemon_type"] = daemon_type
        
        try:
            # Check if ipfs_kit has the check_daemon_status method
            if hasattr(self.ipfs_kit, 'check_daemon_status'):
                # Handle parameter compatibility
                import inspect
                sig = inspect.signature(self.ipfs_kit.check_daemon_status)
                
                # Call without daemon_type parameter if method doesn't accept it
                if len(sig.parameters) > 1:
                    # This means the method takes more than just 'self', likely has daemon_type parameter
                    daemon_status = self.ipfs_kit.check_daemon_status(daemon_type) if daemon_type else self.ipfs_kit.check_daemon_status()
                else:
                    # Method only takes 'self', doesn't accept daemon_type
                    daemon_status = self.ipfs_kit.check_daemon_status()"""
                    
            new_code = """def check_daemon_status(self, daemon_type: str = None) -> Dict[str, Any]:
        \"\"\"
        Check the status of IPFS daemons.
        
        Args:
            daemon_type: Optional daemon type to check (ipfs, ipfs_cluster_service, etc.)
            
        Returns:
            Dictionary with daemon status information
        \"\"\"
        import inspect
        import traceback
        
        operation_id = f"check_daemon_status_{int(time.time() * 1000)}"
        start_time = time.time()
        
        # Log parameter for debugging
        logger.debug(f"check_daemon_status called with daemon_type={daemon_type}")
        
        result = {
            "success": False,
            "operation": "check_daemon_status",
            "operation_id": operation_id,
            "timestamp": time.time(),
            "overall_status": "unknown"
        }
        
        if daemon_type:
            result["daemon_type"] = daemon_type
        
        try:
            # Check if ipfs_kit has the check_daemon_status method
            if hasattr(self.ipfs_kit, 'check_daemon_status'):
                # Handle parameter compatibility
                try:
                    sig = inspect.signature(self.ipfs_kit.check_daemon_status)
                    logger.debug(f"check_daemon_status signature: {sig}, parameter count: {len(sig.parameters)}")
                    
                    # Call without daemon_type parameter if method doesn't accept it
                    if len(sig.parameters) > 1:
                        # This means the method takes more than just 'self', likely has daemon_type parameter
                        logger.debug(f"Calling with daemon_type parameter: {daemon_type}")
                        daemon_status = self.ipfs_kit.check_daemon_status(daemon_type) if daemon_type else self.ipfs_kit.check_daemon_status()
                    else:
                        # Method only takes 'self', doesn't accept daemon_type
                        logger.debug("Calling without daemon_type parameter (original method)")
                        daemon_status = self.ipfs_kit.check_daemon_status()
                except Exception as sig_error:
                    logger.error(f"Error inspecting signature: {sig_error}")
                    logger.error(traceback.format_exc())
                    # Fall back to direct call without parameter
                    logger.debug("Signature inspection failed, falling back to call without parameters")
                    daemon_status = self.ipfs_kit.check_daemon_status()"""
                
            # Replace the implementation
            new_content = content.replace(old_code, new_code)
            
            if new_content != content:
                with open(model_path, 'w') as f:
                    f.write(new_content)
                logger.info("Successfully updated IPFS model implementation")
                return True
            else:
                logger.warning("Failed to update model - content unchanged")
                return False
        else:
            logger.error("Could not find check_daemon_status method in model")
            return False
            
    except Exception as e:
        logger.error(f"Error fixing IPFS model: {e}")
        logger.error(traceback.format_exc())
        return False

def restart_mcp_server():
    """Restart the MCP server to apply changes."""
    try:
        # Find the running server process
        import subprocess
        
        logger.info("Finding MCP server process")
        ps_result = subprocess.run(
            ["ps", "aux", "|", "grep", "uvicorn", "run_mcp_server"], 
            shell=True, 
            capture_output=True, 
            text=True
        )
        
        lines = ps_result.stdout.splitlines()
        pid = None
        
        for line in lines:
            if "uvicorn run_mcp_server:app" in line and "grep" not in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        break
                    except ValueError:
                        continue
        
        if pid:
            logger.info(f"Found MCP server process with PID {pid}")
            # Restart the server properly by sending SIGTERM
            subprocess.run(["kill", str(pid)])
            logger.info(f"Sent SIGTERM to PID {pid}")
            
            # Wait for process to exit
            time.sleep(2)
            
            # Start new server
            logger.info("Starting new MCP server")
            subprocess.Popen(
                ["uvicorn", "run_mcp_server:app", "--host", "127.0.0.1", "--port", "9999", "--reload"],
                cwd="/home/barberb/ipfs_kit_py",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            time.sleep(5)
            logger.info("MCP server restarted")
            return True
        else:
            logger.warning("Could not find MCP server process")
            return False
        
    except Exception as e:
        logger.error(f"Error restarting MCP server: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function to fix the MCP server."""
    logger.info("Starting MCP server fixes...")
    
    # Fix the controller
    controller_fixed = fix_ipfs_controller()
    if controller_fixed:
        logger.info("✅ IPFS controller fixed successfully")
    else:
        logger.error("❌ Failed to fix IPFS controller")
        
    # Fix the model
    model_fixed = fix_ipfs_model()
    if model_fixed:
        logger.info("✅ IPFS model fixed successfully")
    else:
        logger.error("❌ Failed to fix IPFS model")
        
    # If either component was fixed, restart the server
    if controller_fixed or model_fixed:
        logger.info("Restarting MCP server to apply changes...")
        if restart_mcp_server():
            logger.info("✅ MCP server restarted successfully")
        else:
            logger.error("❌ Failed to restart MCP server")
    else:
        logger.warning("No changes made, not restarting server")
        
    return controller_fixed or model_fixed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)