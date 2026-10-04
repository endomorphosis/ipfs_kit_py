#\!/usr/bin/env python3
"""
Script to fix async methods in LibP2PModel class.
This script updates all async methods to properly use anyio.to_thread.run_sync
with helper functions to avoid recursive calls and parameter issues.
"""

import re
import os
import tempfile
import shutil

# Path to the file we want to fix
file_path = "ipfs_kit_py/mcp/models/libp2p_model.py"

# Make a backup of the original file
backup_path = f"{file_path}.bak"
shutil.copy2(file_path, backup_path)
print(f"Created backup at {backup_path}")

# Read the file content
with open(file_path, 'r') as f:
    content = f.read()

# Define a pattern to match async methods with lambda
# This pattern looks for async methods that use lambda in anyio.to_thread.run_sync
pattern = r'async def (\w+)\((self(?:,\s*[^)]+)?)\)(?:\s*->\s*([^:]+))?:\s*"""([^"]*)"""\s*#[^\n]*\s*import anyio\s*return await anyio\.to_thread\.run_sync\(lambda:[^)]+\)'

# Define a replacement template
def replacement(match):
    method_name = match.group(1)
    parameters = match.group(2)
    return_type = match.group(3) or "Dict[str, Any]"
    docstring = match.group(4)
    
    # Parse parameters
    param_list = []
    if ',' in parameters:
        # Split the parameters and remove 'self'
        param_list = [p.strip() for p in parameters.split(',')[1:]]
    
    # Extract parameter names (without type hints or default values)
    param_names = []
    for param in param_list:
        # Extract just the parameter name (before : or =)
        name = param.split(':')[0].split('=')[0].strip()
        param_names.append(name)
    
    # Build the helper function definition
    helper_function = f"""
    async def {method_name}({parameters}) -> {return_type}:
        \"\"\"
{docstring}
        \"\"\"
        # Define a helper function to avoid parameter issues
        def _{method_name}_sync():
            return LibP2PModel.{method_name}(self{', ' + ', '.join(param_names) if param_names else ''})
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_{method_name}_sync)"""
    
    return helper_function

# Apply the fixes
content_fixed = re.sub(pattern, replacement, content)

# Fix the register_message_handler method specifically
register_handler_pattern = r'async def register_message_handler\(self, handler_id: str, protocol_id: str, description: Optional\[str\] = None\) -> Dict\[str, Any\]:[^}]+?return await anyio\.to_thread\.run_sync\(lambda: self\.register_message_handler\([^)]+\)\)'

register_handler_replacement = """
    async def register_message_handler(self, handler_id: str, protocol_id: str, description: Optional[str] = None) -> Dict[str, Any]:
        \"\"\"
        Async version of register_message_handler for use with async controllers.
        
        Args:
            handler_id: Unique identifier for the handler
            protocol_id: Protocol ID to handle
            description: Optional description of the handler
            
        Returns:
            Dict with registration status
        \"\"\"
        # Create a dummy handler function
        def dummy_handler(message):
            pass
        
        # Define a helper function to avoid parameter issues
        def _register_message_handler_sync():
            return LibP2PModel.register_message_handler(self, protocol_id, dummy_handler, handler_id)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_register_message_handler_sync)"""

content_fixed = re.sub(register_handler_pattern, register_handler_replacement, content_fixed)

# Fix the pubsub_publish method to remove extra self
pubsub_publish_pattern = r'return await anyio\.to_thread\.run_sync\(lambda: self\.pubsub_publish\(\, topic, message\)\)'
pubsub_publish_replacement = r'return await anyio.to_thread.run_sync(lambda: self.pubsub_publish(topic, message))'
content_fixed = re.sub(pubsub_publish_pattern, pubsub_publish_replacement, content_fixed)

# Fix the pubsub_subscribe method to remove extra self
pubsub_subscribe_pattern = r'return await anyio\.to_thread\.run_sync\(lambda: self\.pubsub_subscribe\(\, topic, handler_id\)\)'
pubsub_subscribe_replacement = r'return await anyio.to_thread.run_sync(lambda: self.pubsub_subscribe(topic, handler_id))'
content_fixed = re.sub(pubsub_subscribe_pattern, pubsub_subscribe_replacement, content_fixed)

# Fix the pubsub_unsubscribe method to remove extra self
pubsub_unsubscribe_pattern = r'return await anyio\.to_thread\.run_sync\(lambda: self\.pubsub_unsubscribe\(\, topic, handler_id\)\)'
pubsub_unsubscribe_replacement = r'return await anyio.to_thread.run_sync(lambda: self.pubsub_unsubscribe(topic, handler_id))'
content_fixed = re.sub(pubsub_unsubscribe_pattern, pubsub_unsubscribe_replacement, content_fixed)

# Fix the pubsub_get_peers method to remove extra self
pubsub_get_peers_pattern = r'return await anyio\.to_thread\.run_sync\(lambda: self\.pubsub_get_peers\(\, topic\)\)'
pubsub_get_peers_replacement = r'return await anyio.to_thread.run_sync(lambda: self.pubsub_get_peers(topic))'
content_fixed = re.sub(pubsub_get_peers_pattern, pubsub_get_peers_replacement, content_fixed)

# Write the fixed content to a temporary file first
with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
    tmp.write(content_fixed)
    temp_name = tmp.name

# If the write was successful, replace the original file
shutil.move(temp_name, file_path)
print(f"Fixed async methods in {file_path}")

# Also fix the sync method calling itself
with open(file_path, 'r') as f:
    content = f.read()

# Fix self-calling methods
get_health_pattern = r'def _get_health_sync\(\):\s*return LibP2PModel\.get_health\(self\)'
get_health_replacement = r'def _get_health_sync():\n            # Call the original method directly to avoid recursion\n            original_method = LibP2PModel.get_health.__func__\n            return original_method(self)'
content = re.sub(get_health_pattern, get_health_replacement, content)

# Write the fixed content back
with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
    tmp.write(content)
    temp_name = tmp.name

# If the write was successful, replace the original file
shutil.move(temp_name, file_path)
print(f"Fixed self-referential method issues in {file_path}")

print("All async methods have been fixed\!")
