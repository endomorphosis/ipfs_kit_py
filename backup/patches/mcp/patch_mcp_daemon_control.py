# Apply runtime patch to MCP server to enable manual daemon control
import types
import logging
import time

logger = logging.getLogger(__name__)

def apply_daemon_control_patch():
    # Apply runtime patch to enable manual daemon control.
    try:
        from ipfs_kit_py.mcp.server_anyio import MCPServer

        # Original start_daemon method has a check that prevents manual control
        original_start_daemon = MCPServer.start_daemon

        # Create a new implementation that bypasses the check
        async def patched_start_daemon(self, daemon_type: str):
            # Patched version that allows manual daemon control.
            # Validate daemon type
            valid_types = ['ipfs', 'ipfs_cluster_service', 'ipfs_cluster_follow']
            if daemon_type not in valid_types:
                return {
                    "success": False,
                    "error": f"Invalid daemon type: {daemon_type}. Must be one of: {', '.join(valid_types)}",
                    "error_type": "InvalidDaemonType"
                }

            # Try to start the daemon directly using our helper functions
            if daemon_type == 'ipfs':
                from fix_mcp_daemons import start_ipfs_daemon
                result = start_ipfs_daemon()
                return {
                    "success": result,
                    "message": "IPFS daemon started successfully" if result else "Failed to start IPFS daemon",
                    "timestamp": time.time()
                }
            elif daemon_type == 'ipfs_cluster_service':
                from fix_mcp_daemons import start_ipfs_cluster_service
                result = start_ipfs_cluster_service()
                return {
                    "success": result,
                    "message": "IPFS Cluster service started successfully" if result else "Failed to start IPFS Cluster service",
                    "timestamp": time.time()
                }
            elif daemon_type == 'lotus':
                from fix_mcp_daemons import start_lotus_daemon
                result = start_lotus_daemon()
                return {
                    "success": result,
                    "message": "Lotus daemon started successfully" if result else "Failed to start Lotus daemon",
                    "timestamp": time.time()
                }
            else:
                return {
                    "success": False,
                    "error": f"Daemon type not implemented: {daemon_type}",
                    "error_type": "NotImplemented"
                }

        # Replace the method
        MCPServer.start_daemon = patched_start_daemon
        logger.info("Successfully patched MCPServer.start_daemon to enable manual daemon control")
        return True
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to patch daemon control: {e}")
        return False

# Apply the patch when this module is imported
apply_daemon_control_patch()
