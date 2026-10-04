#!/usr/bin/env python3
"""Script to remove duplicate function definitions in libp2p_model.py."""

import re

# Load the file content
file_path = "ipfs_kit_py/mcp/models/libp2p_model.py"
with open(file_path, "r") as f:
    content = f.read()

# List of function names to check for duplicates
duplicate_funcs = [
    "close_all_webrtc_connections",
    "is_available",
    "discover_peers",
    "connect_peer",
    "find_content",
    "retrieve_content",
    "get_content",
    "announce_content",
    "get_connected_peers",
    "get_peer_info",
    "reset",
    "start",
    "stop",
    "dht_find_peer",
    "dht_provide",
    "dht_find_providers",
    "pubsub_publish",
    "pubsub_subscribe",
    "pubsub_unsubscribe",
    "pubsub_get_topics",
    "pubsub_get_peers",
    "register_message_handler",
    "unregister_message_handler",
    "list_message_handlers",
    "peer_info"
]

# For each duplicate function, keep only the first occurrence
for func_name in duplicate_funcs:
    # Find all occurrences of the function definition
    pattern = r"(\s+)(async )?def {}\(".format(re.escape(func_name))
    matches = list(re.finditer(pattern, content))

    if len(matches) <= 1:
        continue  # No duplicates found

    # Keep the first occurrence, comment out others
    for match in matches[1:]:
        # Find the function body start position
        start_pos = match.start()

        # Find the function body end position (next def at same indentation level)
        indent = match.group(1)
        next_def_pattern = r"\n{}(async )?def ".format(re.escape(indent))
        next_matches = list(re.finditer(next_def_pattern, content[start_pos:]))

        if next_matches:
            end_pos = start_pos + next_matches[0].start()
        else:
            # If no next function, check for class end or file end
            end_pos = len(content)

        # Extract the function and create a commented version
        func_text = content[start_pos:end_pos]
        commented_text = "\n".join([f"# {line}" for line in func_text.split("\n")])

        # Replace in content
        content = content[:start_pos] + commented_text + content[end_pos:]

# Write the modified content back to the file
with open(file_path, "w") as f:
    f.write(content)

print(f"Removed duplicate function definitions in {file_path}")
