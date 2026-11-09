#!/usr/bin/env python3
"""
This test script is the properly named version of the original:
run_mcp_partition_test.py

It has been moved to the appropriate test directory for better organization.
"""

# Original content follows:

#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
DEPRECATED: This script has been replaced by network_simulator.py

This file is kept for backward compatibility. Please use the unified network simulator instead,
which provides comprehensive network testing capabilities:

    python network_simulator.py --scenario full_partition

The network simulator supports multiple scenarios including full partition, partial partition,
asymmetric partition, and more options.
"""

import sys
import os
import subprocess
import warnings

def main():
    """Run the network partition test using the new network_simulator."""
    # Show deprecation warning
    warnings.warn(
        "run_mcp_partition_test.py is deprecated and will be removed in a future version. "
        "Please use network_simulator.py instead.",
        DeprecationWarning, stacklevel=2
    )
    
    print("Running network partition test using the new network_simulator module...")
    
    # Check if network_simulator.py exists
    network_simulator_path = os.path.join(os.path.dirname(__file__), "network_simulator.py")
    if not os.path.exists(network_simulator_path):
        print("ERROR: network_simulator.py not found. Please make sure it's in the same directory.")
        return 1
    
    # Build command for full partition scenario
    cmd = [
        sys.executable,
        network_simulator_path,
        "--scenario", "full_partition",
        "--nodes", "3",
        "--duration", "60",
        "--verbose"
    ]
    
    # Run network_simulator
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print("\nStopping network test...")
        return 0
    except Exception as e:
        print(f"Error running network test: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())