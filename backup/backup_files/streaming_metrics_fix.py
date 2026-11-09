"""
Focused fix to add metrics tracking to the high-level API.

This script adds metrics initialization to the IPFSSimpleAPI class
without modifying the streaming methods, which will be done separately.
"""

import re

# Path to high_level_api.py
API_FILE = "ipfs_kit_py/high_level_api.py"
OUTPUT_FILE = "ipfs_kit_py/high_level_api_fixed.py"

# Read the file
with open(API_FILE, 'r') as f:
    content = f.read()

# Find the __init__ method
init_match = re.search(r'def __init__\s*\(self.*?\).*?(?=\n\s*def)', content, re.DOTALL)

if init_match:
    init_method = init_match.group(0)

    # Find the position to insert metrics initialization (before ipfs_add_file check)
    insert_pos = init_method.find("# Ensure ipfs_add_file method is available")

    if insert_pos > 0:
        # Create the updated init method with metrics initialization
        updated_init = (
            init_method[:insert_pos] +
            "\n        # Initialize metrics tracking\n"
            "        self.enable_metrics = kwargs.get('enable_metrics', True)\n"
            "        if self.enable_metrics:\n"
            "            from ipfs_kit_py.performance_metrics import PerformanceMetrics\n"
            "            self.metrics = PerformanceMetrics()\n"
            "        else:\n"
            "            self.metrics = None\n\n" +
            init_method[insert_pos:]
        )

        # Update the content
        content = content.replace(init_method, updated_init)

        # Add the track_streaming_operation method after the cat method
        cat_match = re.search(r'def cat\s*\(.*?\).*?(?=\n\s*def)', content, re.DOTALL)
        if cat_match:
            cat_method = cat_match.group(0)
            cat_end = content.find(cat_method) + len(cat_method)

            # Add the track_streaming_operation method
            track_method = """
    def track_streaming_operation(self, stream_type, direction, size_bytes, duration_seconds, path=None,
                               chunk_count=None, chunk_size=None, correlation_id=None):
        '''Track streaming operation metrics if metrics are enabled.'''
        if not self.enable_metrics or not hasattr(self, 'metrics') or not self.metrics:
            return None

        return self.metrics.track_streaming_operation(
            stream_type=stream_type,
            direction=direction,
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
            path=path,
            chunk_count=chunk_count,
            chunk_size=chunk_size,
            correlation_id=correlation_id
        )
"""

            # Insert the track_streaming_operation method
            content = content[:cat_end] + track_method + content[cat_end:]

            # Write the updated content to a new file
            with open(OUTPUT_FILE, 'w') as f:
                f.write(content)

            print(f"Updated high_level_api.py with metrics initialization and tracking method")
            print(f"Written to {OUTPUT_FILE}")
            print()
            print("To apply the changes, run:")
            print(f"  cp {OUTPUT_FILE} {API_FILE}")
        else:
            print("Could not find cat method in high_level_api.py")
    else:
        print("Could not find insertion point in __init__ method")
else:
    print("Could not find __init__ method in high_level_api.py")
