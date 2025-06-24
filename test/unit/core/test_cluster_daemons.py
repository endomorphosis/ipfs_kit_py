"""Test direct operation of IPFS cluster daemons."""
import os
import time
import subprocess
import sys
from contextlib import contextmanager

@contextmanager
def pause_daemon_after_test(daemon_name):
    """Context manager to ensure daemon is stopped after test."""
    print(f"\n====== Testing {daemon_name} ======")
    try:
        yield
    finally:
        # Kill any running daemon processes after test
        print(f"\nStopping any running {daemon_name} processes...")
        try:
            subprocess.run(['pkill', '-f', daemon_name], check=False)
        except Exception as e:
            print(f"Error stopping processes: {e}")

def run_command(command, check=True, timeout=30):
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            command,
            check=check,
            timeout=timeout,
            capture_output=True,
            text=True
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds"
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "returncode": e.returncode,
            "stdout": e.stdout,
            "stderr": e.stderr,
            "error": f"Command failed with return code {e.returncode}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error executing command: {str(e)}"
        }

def check_process_running(name):
    """Check if a process with the given name is running."""
    result = run_command(['pgrep', '-f', name], check=False)
    return result["success"] and result["stdout"].strip() != ""

def test_ipfs_cluster_service():
    """Test IPFS Cluster Service daemon."""
    with pause_daemon_after_test("ipfs_cluster_service"):
        # Check if executable exists
        script_path = os.path.abspath("/home/barberb/ipfs_kit_py/run_ipfs_cluster_service.py")
        if not os.path.exists(script_path):
            print(f"❌ Error: Could not find {script_path}")
            return False

        # Try importing the module to see if it has any errors
        print("Importing ipfs_cluster_service module...")
        try:
            import ipfs_kit_py.ipfs_cluster_service as ipfs_cluster_service
            print("✅ Successfully imported ipfs_cluster_service module")
        except Exception as e:
            print(f"❌ Error importing ipfs_cluster_service: {e}")
            return False

        # Check if already running
        if check_process_running("ipfs_cluster_service"):
            print("ipfs_cluster_service is already running. Stopping it first...")
            run_command(["pkill", "-f", "ipfs_cluster_service"], check=False)
            time.sleep(2)

        # Try starting the daemon in the background
        print("Starting ipfs_cluster_service daemon...")
        result = run_command([sys.executable, script_path, '--debug', '--fake-daemon'], check=False)

        if not result["success"]:
            print(f"❌ Failed to start ipfs_cluster_service:")
            print(f"Return code: {result['returncode']}")
            print(f"Stderr: {result['stderr']}")
            return False

        # Give it a moment to start
        time.sleep(2)

        # Check if it's running
        if check_process_running("ipfs_cluster_service"):
            print("✅ ipfs_cluster_service daemon started successfully")
            return True
        else:
            print("❌ ipfs_cluster_service daemon failed to start or terminated immediately")
            return False

def test_ipfs_cluster_follow():
    """Test IPFS Cluster Follow daemon."""
    with pause_daemon_after_test("ipfs_cluster_follow"):
        # Check if executable exists
        script_path = os.path.abspath("/home/barberb/ipfs_kit_py/run_ipfs_cluster_follow.py")
        if not os.path.exists(script_path):
            print(f"❌ Error: Could not find {script_path}")
            return False

        # Try importing the module to see if it has any errors
        print("Importing ipfs_cluster_follow module...")
        try:
            import ipfs_kit_py.ipfs_cluster_follow as ipfs_cluster_follow
            print("✅ Successfully imported ipfs_cluster_follow module")
        except Exception as e:
            print(f"❌ Error importing ipfs_cluster_follow: {e}")
            return False

        # Check if already running
        if check_process_running("ipfs_cluster_follow"):
            print("ipfs_cluster_follow is already running. Stopping it first...")
            run_command(["pkill", "-f", "ipfs_cluster_follow"], check=False)
            time.sleep(2)

        # Try starting the daemon in the background
        print("Starting ipfs_cluster_follow daemon...")
        result = run_command([sys.executable, script_path, '--debug', '--fake-daemon'], check=False)

        if not result["success"]:
            print(f"❌ Failed to start ipfs_cluster_follow:")
            print(f"Return code: {result['returncode']}")
            print(f"Stderr: {result['stderr']}")
            return False

        # Give it a moment to start
        time.sleep(2)

        # Check if it's running
        if check_process_running("ipfs_cluster_follow"):
            print("✅ ipfs_cluster_follow daemon started successfully")
            return True
        else:
            print("❌ ipfs_cluster_follow daemon failed to start or terminated immediately")
            return False

if __name__ == "__main__":
    # Test IPFS Cluster Service
    test_ipfs_cluster_service()

    # Test IPFS Cluster Follow
    test_ipfs_cluster_follow()
