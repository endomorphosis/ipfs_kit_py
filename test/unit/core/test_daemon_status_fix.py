#!/usr/bin/env python3
import sys
import logging
import time
import json
import inspect
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("daemon_status_test")

# Create a mock ipfs_kit class for testing
class MockIPFSKit:
    def __init__(self):
        self.logger = logging.getLogger("mock_ipfs_kit")

    def check_daemon_status(self):
        """Original implementation without daemon_type parameter."""
        result = {
            "success": True,
            "operation": "check_daemon_status",
            "timestamp": time.time(),
            "daemons": {
                "ipfs": {
                    "running": True,
                    "type": "ipfs_daemon"
                }
            }
        }
        return result

# Create a mock IPFSModel for testing
class MockIPFSModel:
    def __init__(self, ipfs_kit_instance=None):
        self.ipfs_kit = ipfs_kit_instance or MockIPFSKit()
        self.operation_stats = {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0
        }

    def check_daemon_status(self, daemon_type: str = None) -> Dict[str, Any]:
        """
        Check the status of IPFS daemons.

        Args:
            daemon_type: Optional daemon type to check (ipfs, ipfs_cluster_service, etc.)

        Returns:
            Dictionary with daemon status information
        """
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
                sig = inspect.signature(self.ipfs_kit.check_daemon_status)

                # Call without daemon_type parameter if method doesn't accept it
                if len(sig.parameters) > 1:
                    # This means the method takes more than just 'self', likely has daemon_type parameter
                    print(f"Calling with daemon_type: {daemon_type}")
                    daemon_status = self.ipfs_kit.check_daemon_status(daemon_type) if daemon_type else self.ipfs_kit.check_daemon_status()
                else:
                    # Method only takes 'self', doesn't accept daemon_type
                    print("Calling without daemon_type (original method)")
                    daemon_status = self.ipfs_kit.check_daemon_status()

                # Process the response
                if "daemons" in daemon_status:
                    result["daemons"] = daemon_status["daemons"]

                    # If a specific daemon was requested, focus on it
                    if daemon_type and daemon_type in daemon_status["daemons"]:
                        result["daemon_info"] = daemon_status["daemons"][daemon_type]
                        result["running"] = daemon_status["daemons"][daemon_type].get("running", False)
                        result["overall_status"] = "running" if result["running"] else "stopped"
                    else:
                        # Determine overall status from all daemons
                        running_daemons = [d for d in daemon_status["daemons"].values() if d.get("running", False)]
                        result["running_count"] = len(running_daemons)
                        result["daemon_count"] = len(daemon_status["daemons"])
                        result["overall_status"] = "running" if running_daemons else "stopped"

                result["success"] = True

            else:
                # Handle case where check_daemon_status is not available
                result["error"] = "check_daemon_status method not available"

            # Add duration information
            result["duration_ms"] = (time.time() - start_time) * 1000

            # Update operation stats
            self.operation_stats["total_operations"] += 1
            self.operation_stats["success_count"] += 1

        except Exception as e:
            # Handle error
            result["error"] = str(e)
            result["error_type"] = "daemon_status_error"
            result["duration_ms"] = (time.time() - start_time) * 1000

            # Update stats
            self.operation_stats["total_operations"] += 1
            self.operation_stats["failure_count"] += 1

            logger.error(f"Error in check_daemon_status: {e}")

        return result

# Create a test class with the extended check_daemon_status method
class ExtendedMockIPFSKit(MockIPFSKit):
    def check_daemon_status(self, daemon_type=None):
        """Extended implementation with daemon_type parameter."""
        result = {
            "success": True,
            "operation": "check_daemon_status",
            "timestamp": time.time(),
            "daemons": {
                "ipfs": {
                    "running": True,
                    "type": "ipfs_daemon"
                },
                "ipfs_cluster_service": {
                    "running": True,
                    "type": "cluster_service"
                }
            }
        }

        # Filter by daemon_type if specified
        if daemon_type and daemon_type in result["daemons"]:
            filtered_daemons = {daemon_type: result["daemons"][daemon_type]}
            result["daemons"] = filtered_daemons

        return result

# Test function
def test_daemon_status():
    print("\n=== Testing with original IPFSKit (no daemon_type parameter) ===")
    ipfs_kit = MockIPFSKit()
    ipfs_model = MockIPFSModel(ipfs_kit)

    # Test with no daemon_type (this should work)
    print("\nTest 1: No daemon_type parameter")
    result1 = ipfs_model.check_daemon_status()
    print(f"Success: {result1['success']}")
    print(f"Daemons: {json.dumps(result1.get('daemons', {}), indent=2)}")

    # Test with daemon_type (this should not error, even though original doesn't support it)
    print("\nTest 2: With daemon_type parameter (should handle gracefully)")
    result2 = ipfs_model.check_daemon_status("ipfs")
    print(f"Success: {result2['success']}")
    print(f"Daemons: {json.dumps(result2.get('daemons', {}), indent=2)}")

    print("\n=== Testing with extended IPFSKit (supports daemon_type parameter) ===")
    extended_ipfs_kit = ExtendedMockIPFSKit()
    extended_ipfs_model = MockIPFSModel(extended_ipfs_kit)

    # Test with no daemon_type
    print("\nTest 3: No daemon_type parameter with extended IPFSKit")
    result3 = extended_ipfs_model.check_daemon_status()
    print(f"Success: {result3['success']}")
    print(f"Daemons: {json.dumps(result3.get('daemons', {}), indent=2)}")

    # Test with daemon_type
    print("\nTest 4: With daemon_type parameter with extended IPFSKit")
    result4 = extended_ipfs_model.check_daemon_status("ipfs_cluster_service")
    print(f"Success: {result4['success']}")
    print(f"Daemons: {json.dumps(result4.get('daemons', {}), indent=2)}")
    print(f"Daemon info: {json.dumps(result4.get('daemon_info', {}), indent=2)}")

    # Return success if all tests passed
    return all([result1['success'], result2['success'], result3['success'], result4['success']])

if __name__ == "__main__":
    success = test_daemon_status()
    sys.exit(0 if success else 1)
