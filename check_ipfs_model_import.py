import sys
import os
import traceback
import tempfile

# Define an output file
output_file = os.path.join(tempfile.gettempdir(), "ipfs_model_import_check_output.log")

# Redirect stdout and stderr to the output file
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = sys.stderr = open(output_file, 'w')

try:
    # Add applied_patches to sys.path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    applied_patches_dir = os.path.join(script_dir, "applied_patches")
    if applied_patches_dir not in sys.path:
        sys.path.insert(0, applied_patches_dir) # Insert at the beginning to prioritize

    import ipfs_model_fix
    print("Import successful: ipfs_model_fix")

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
