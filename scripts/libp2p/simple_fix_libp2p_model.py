#!/usr/bin/env python3
"""
Simple fix for the LibP2PModel class to resolve coroutine never awaited warnings.
"""

import os
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_fixes():
    """Apply fixes to the libp2p_model.py file."""
    try:
        # Target file path
        file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/libp2p_model.py'

        # Read the file
        with open(file_path, 'r') as file:
            lines = file.readlines()

        # Fixed content
        fixed_lines = []
        i = 0

        # Add class logger at class definition
        while i < len(lines):
            line = lines[i]

            # Add class logger after class definition
            if line.strip() == 'class LibP2PModel:':
                fixed_lines.append(line)
                fixed_lines.append('    # Class logger\n')
                fixed_lines.append('    logger = logging.getLogger(__name__)\n')
            # Fix async is_available method
            elif line.strip() == 'async def is_available(self) -> bool:':
                # Collect the entire method definition
                method_lines = [line]
                j = i + 1
                while j < len(lines) and (lines[j].startswith(' ' * 8) or not lines[j].strip()):
                    method_lines.append(lines[j])
                    j += 1

                # Check if this is the problematic method
                if any('await anyio.to_thread.run_sync(LibP2PModel._is_available_sync, self)' in l for l in method_lines):
                    # Replace with fixed version
                    fixed_lines.append('    async def is_available(self) -> bool:\n')
                    fixed_lines.append('        """\n')
                    fixed_lines.append('        Async version of is_available for use with async controllers.\n')
                    fixed_lines.append('        \n')
                    fixed_lines.append('        Returns:\n')
                    fixed_lines.append('            bool: True if libp2p is available, False otherwise\n')
                    fixed_lines.append('        """\n')
                    fixed_lines.append('        # Use anyio to run the synchronous version in a thread\n')
                    fixed_lines.append('        import anyio\n')
                    fixed_lines.append('        return await anyio.to_thread.run_sync(lambda: self._is_available_sync())\n')

                    # Skip the original method lines
                    i = j - 1
                else:
                    # Keep the method as is
                    fixed_lines.extend(method_lines)
                    i = j - 1
            # Fix get_health async method
            elif line.strip() == 'async def get_health(self) -> Dict[str, Any]:':
                # Collect the entire method definition
                method_lines = [line]
                j = i + 1
                while j < len(lines) and (lines[j].startswith(' ' * 8) or not lines[j].strip()):
                    method_lines.append(lines[j])
                    j += 1

                # Check if this is the problematic method
                if any('await anyio.to_thread.run_sync(LibP2PModel.get_health, self)' in l for l in method_lines):
                    # Replace with fixed version
                    fixed_lines.append('    async def get_health(self) -> Dict[str, Any]:\n')
                    fixed_lines.append('        """\n')
                    fixed_lines.append('        Async version of get_health for use with async controllers.\n')
                    fixed_lines.append('        \n')
                    fixed_lines.append('        Returns:\n')
                    fixed_lines.append('            Dict containing health status information\n')
                    fixed_lines.append('        """\n')
                    fixed_lines.append('        # Use anyio to run the synchronous version in a thread\n')
                    fixed_lines.append('        import anyio\n')
                    fixed_lines.append('        return await anyio.to_thread.run_sync(lambda: self.get_health())\n')

                    # Skip the original method lines
                    i = j - 1
                else:
                    # Keep the method as is
                    fixed_lines.extend(method_lines)
                    i = j - 1
            # Fix register_message_handler async method
            elif line.strip().startswith('async def register_message_handler'):
                # Replace with fixed version
                fixed_lines.append('    async def register_message_handler(self, handler_id: str, protocol_id: str, description: Optional[str] = None) -> Dict[str, Any]:\n')
                fixed_lines.append('        """\n')
                fixed_lines.append('        Async version of register_message_handler for use with async controllers.\n')
                fixed_lines.append('        \n')
                fixed_lines.append('        Args:\n')
                fixed_lines.append('            handler_id: Unique identifier for the handler\n')
                fixed_lines.append('            protocol_id: Protocol ID to handle\n')
                fixed_lines.append('            description: Optional description of the handler\n')
                fixed_lines.append('            \n')
                fixed_lines.append('        Returns:\n')
                fixed_lines.append('            Dict with registration status\n')
                fixed_lines.append('        """\n')
                fixed_lines.append('        # Create a dummy handler function\n')
                fixed_lines.append('        def dummy_handler(message):\n')
                fixed_lines.append('            pass\n')
                fixed_lines.append('        \n')
                fixed_lines.append('        # Use anyio to run the synchronous version in a thread\n')
                fixed_lines.append('        import anyio\n')
                fixed_lines.append('        return await anyio.to_thread.run_sync(lambda: self.register_message_handler(protocol_id, dummy_handler, handler_id))\n')

                # Skip the rest of the original method
                while i < len(lines) and (lines[i].startswith(' ' * 8) or not lines[i].strip()):
                    i += 1
                i -= 1
            else:
                fixed_lines.append(line)

            i += 1

        # Write the fixed content back to the file
        with open(file_path, 'w') as file:
            file.writelines(fixed_lines)

        logger.info(f"Successfully applied fixes to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error applying fixes: {e}")
        return False

if __name__ == "__main__":
    success = apply_fixes()
    if success:
        print("Successfully applied fixes to LibP2PModel class!")
        print("This resolves the issues with async methods.")
    else:
        print("Failed to apply fixes. See logs for details.")
        sys.exit(1)
