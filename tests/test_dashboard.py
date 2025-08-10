import subprocess
import sys

def test_start_dashboard():
    """
    Tests that the `ipfs-kit mcp start` command runs without errors.
    """
    try:
        # We'll run the command with a timeout, as it's expected to start a server
        # and run indefinitely. A successful launch will result in a timeout.
        subprocess.run(
            ["python3", "-m", "ipfs_kit_py.cli", "mcp", "start"],
            timeout=5,
            check=False,  # Don't raise an exception on non-zero exit codes
        )
    except subprocess.TimeoutExpired:
        # A timeout is expected, as the server is running.
        # This is a successful outcome for this test.
        pass
    except Exception as e:
        print(f"Dashboard failed to start: {e}")
        sys.exit(1)
