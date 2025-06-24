#!/usr/bin/env python3
"""
Direct Test for IPFS Model Fixes

This script directly tests the IPFS model fixes without starting the full MCP server.
It verifies that our direct method patching approach works correctly.
"""

import sys
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_test")

def main():
    """Test IPFS model fixes directly."""
    logger.info("Starting direct test of IPFS model fixes...")

    # Step 1: Import the IPFS model
    try:
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        logger.info("Successfully imported IPFSModel")
    except ImportError as e:
        logger.error(f"Failed to import IPFSModel: {e}")
        return False

    # Step 2: Apply our fixes
    try:
        from ipfs_kit_py.mcp.models.ipfs_model_fix import fix_ipfs_model

        # Apply the fixes to the IPFSModel class
        fix_ipfs_model(IPFSModel)
        logger.info("Successfully applied fixes to IPFSModel")
    except ImportError as e:
        logger.error(f"Failed to import fix_ipfs_model: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to apply fixes to IPFSModel: {e}")
        return False

    # Step 3: Create an instance of the model
    try:
        ipfs_model = IPFSModel()
        logger.info("Successfully created IPFSModel instance")
    except Exception as e:
        logger.error(f"Failed to create IPFSModel instance: {e}")
        return False

    # Step 4: Call patched methods and show results
    test_methods = {
        'add_content': {
            'args': ["This is a test content"],
            'kwargs': {}
        },
        'pin_add': {
            'args': ["QmTest123"],
            'kwargs': {}
        },
        'pin_ls': {
            'args': [],
            'kwargs': {}
        },
        'cat': {
            'args': ["QmTest123"],
            'kwargs': {}
        },
        'storage_transfer': {
            'args': ["ipfs", "filecoin", "QmTest123"],
            'kwargs': {}
        }
    }

    success = True

    for method_name, call_info in test_methods.items():
        try:
            if hasattr(ipfs_model, method_name):
                method = getattr(ipfs_model, method_name)
                result = method(*call_info['args'], **call_info['kwargs'])

                # Pretty print the result
                result_str = json.dumps(result, indent=2)
                logger.info(f"Successfully called {method_name}:\n{result_str}")
            else:
                logger.error(f"Method {method_name} not found on IPFSModel")
                success = False
        except Exception as e:
            logger.error(f"Error calling {method_name}: {e}")
            success = False

    if success:
        logger.info("All method calls succeeded!")
    else:
        logger.warning("Some method calls failed!")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
