#!/usr/bin/env python3
'''
Update the __init__.py file to include import hooks.

This script adds an import statement for the hooks module to the
ipfs_kit_py/libp2p/__init__.py file to ensure hooks are loaded.
'''

import os
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_init_file():
    '''Update the __init__.py file to include import hooks.'''
    # Find the __init__.py file
    init_file = os.path.join(os.path.dirname(__file__), "ipfs_kit_py", "libp2p", "__init__.py")

    if not os.path.exists(init_file):
        logger.error(f"__init__.py file not found at {init_file}")
        return False

    # Read the current content
    with open(init_file, 'r') as f:
        content = f.read()

    # Check if hooks import already exists
    if "import ipfs_kit_py.libp2p.hooks" in content:
        logger.info("Hooks import already exists in __init__.py")
        return True

    # Add the import statement after other imports
    import_pattern = r'(import\s+.*?\n\n)'

    if re.search(import_pattern, content, re.DOTALL):
        # Add after the last import block
        new_content = re.sub(
            import_pattern,
            r'\1# Import hooks to automatically apply protocol extensions\nimport ipfs_kit_py.libp2p.hooks\n\n',
            content,
            count=1,
            flags=re.DOTALL
        )
    else:
        # Add at the beginning of the file
        new_content = "# Import hooks to automatically apply protocol extensions\nimport ipfs_kit_py.libp2p.hooks\n\n" + content

    # Write the updated content
    with open(init_file, 'w') as f:
        f.write(new_content)

    logger.info(f"Updated {init_file} with hooks import")
    return True

if __name__ == "__main__":
    update_init_file()
