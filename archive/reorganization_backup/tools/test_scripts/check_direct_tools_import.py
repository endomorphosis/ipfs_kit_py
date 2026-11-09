import sys
import os
import traceback
import tempfile

# Define an output file
output_file = os.path.join(tempfile.gettempdir(), "direct_tools_import_check_output.log")

# Redirect stdout and stderr to the output file
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = sys.stderr = open(output_file, 'w')

try:
    # Add the current directory to sys.path to ensure fixed_direct_ipfs_tools is found
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir) # Insert at the beginning to prioritize

    import fixed_direct_ipfs_tools
    print("Import successful: fixed_direct_ipfs_tools")

except ImportError as e:
    print(f"ImportError: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"Error during import: {e}")
    traceback.print_exc()
finally:
    # Restore stdout and stderr
    sys.stdout.close()
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    print(f"Output written to {output_file}") # Print the location of the output file
