#!/usr/bin/env python3
"""
Direct fix for MCP resource handlers to add missing logger definition
"""

import os
import sys
import logging
import re
import importlib
import inspect
import pkgutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_mcp_resource_handlers():
    """Find the MCP resource handler modules."""
    try:
        import mcp
        mcp_dir = os.path.dirname(mcp.__file__)
        logger.info(f"Found MCP package at {mcp_dir}")

        # Look specifically for resource handler modules
        handler_modules = []
        server_dir = os.path.join(mcp_dir, "server")

        if os.path.exists(server_dir):
            for root, dirs, files in os.walk(server_dir):
                for file in files:
                    if file.endswith('.py') and ('resource' in file.lower() or 'handler' in file.lower()):
                        full_path = os.path.join(root, file)
                        handler_modules.append(full_path)

        logger.info(f"Found {len(handler_modules)} potential resource handler modules")
        return handler_modules
    except ImportError:
        logger.error("Could not import MCP package")
        return []

def fix_direct_resource_handlers():
    """Directly fix the resource handler files."""
    # Find and fix resource handlers in the MCP package
    handler_modules = find_mcp_resource_handlers()

    for module_path in handler_modules:
        try:
            with open(module_path, 'r') as f:
                content = f.read()

            # Create a backup
            backup_path = module_path + '.bak'
            with open(backup_path, 'w') as f:
                f.write(content)

            # Add logger definition if needed
            if 'logger' in content and 'logger = ' not in content:
                lines = content.split('\n')

                # Find import section
                import_line = -1
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        import_line = max(import_line, i)

                if import_line >= 0:
                    # Add logging import if needed
                    if 'import logging' not in content:
                        lines.insert(import_line + 1, 'import logging')
                        import_line += 1

                    # Add logger definition after imports
                    lines.insert(import_line + 1, '# Configure logger')
                    lines.insert(import_line + 2, 'logger = logging.getLogger(__name__)')
                    lines.insert(import_line + 3, '')

                    # Write the modified content
                    modified_content = '\n'.join(lines)
                    with open(module_path, 'w') as f:
                        f.write(modified_content)

                    logger.info(f"Fixed logger definition in {module_path}")
        except Exception as e:
            logger.error(f"Error fixing {module_path}: {e}")

def fix_resource_templates():
    """Fix resource templates in the MCP package."""
    try:
        import mcp
        mcp_dir = os.path.dirname(mcp.__file__)

        # Look for resource template modules
        template_dir = os.path.join(mcp_dir, "server", "templates")
        if not os.path.exists(template_dir):
            template_dir = os.path.join(mcp_dir, "templates")

        if os.path.exists(template_dir):
            for root, dirs, files in os.walk(template_dir):
                for file in files:
                    if file.endswith('.py') and 'resource' in file.lower():
                        module_path = os.path.join(root, file)

                        try:
                            with open(module_path, 'r') as f:
                                content = f.read()

                            # Create a backup
                            backup_path = module_path + '.bak'
                            with open(backup_path, 'w') as f:
                                f.write(content)

                            # Add logger definition if needed
                            if 'logger' in content and 'logger = ' not in content:
                                lines = content.split('\n')

                                # Find import section
                                import_line = -1
                                for i, line in enumerate(lines):
                                    if line.startswith('import ') or line.startswith('from '):
                                        import_line = max(import_line, i)

                                if import_line >= 0:
                                    # Add logging import if needed
                                    if 'import logging' not in content:
                                        lines.insert(import_line + 1, 'import logging')
                                        import_line += 1

                                    # Add logger definition after imports
                                    lines.insert(import_line + 1, '# Configure logger')
                                    lines.insert(import_line + 2, 'logger = logging.getLogger(__name__)')
                                    lines.insert(import_line + 3, '')

                                    # Write the modified content
                                    modified_content = '\n'.join(lines)
                                    with open(module_path, 'w') as f:
                                        f.write(modified_content)

                                    logger.info(f"Fixed logger definition in template {module_path}")
                        except Exception as e:
                            logger.error(f"Error fixing template {module_path}: {e}")
    except Exception as e:
        logger.error(f"Error fixing resource templates: {e}")

def fix_directly_in_mcp_module():
    """Monkey patch the MCP module to ensure logger is defined in critical places."""
    try:
        import mcp

        # Create a simple function to add to the module
        def ensure_logger(module_name):
            """Ensure logger is defined in the module."""
            import logging
            import sys

            if module_name in sys.modules:
                module = sys.modules[module_name]
                if not hasattr(module, 'logger'):
                    # Use setattr to modify module attributes
                    setattr(module, 'logger', logging.getLogger(module_name))
                    return getattr(module, 'logger')
                return module.logger
            return None

        # Add to key modules
        modules_to_patch = [
            'mcp.server.lowlevel.server',
            'mcp.server.lowlevel.resource',
            'mcp.server.lowlevel.handler',
            'mcp.server.fastmcp'
        ]

        for module_name in modules_to_patch:
            try:
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                else:
                    module = importlib.import_module(module_name)

                # Use setattr to add attributes to the module
                if not hasattr(module, 'ensure_logger'):
                    # Create a closure that binds the module
                    def make_ensure_logger(mod):
                        def _ensure_logger():
                            if not hasattr(mod, 'logger'):
                                setattr(mod, 'logger', logging.getLogger(mod.__name__))
                            return getattr(mod, 'logger')
                        return _ensure_logger

                    # Set the attribute using setattr
                    setattr(module, 'ensure_logger', make_ensure_logger(module))

                # Add logger if not present
                if not hasattr(module, 'logger'):
                    setattr(module, 'logger', logging.getLogger(module_name))
                    logger.info(f"Added logger to module {module_name}")
            except ImportError:
                logger.warning(f"Could not import module {module_name}")
            except Exception as e:
                logger.error(f"Error patching module {module_name}: {e}")

        logger.info("Completed direct module patching")
    except ImportError:
        logger.error("Could not import MCP module for direct patching")

def create_wrapper_module():
    """Create a wrapper module that adds loggers to resource modules."""
    wrapper_path = "ensure_mcp_loggers.py"

    content = """#!/usr/bin/env python3
\"\"\"
Wrapper module to ensure loggers are defined in MCP resource handlers
\"\"\"

import sys
import logging
import importlib
import types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def patch_module(module_name):
    \"\"\"Patch a module to ensure logger is defined.\"\"\"
    try:
        # Import the module
        if module_name in sys.modules:
            module = sys.modules[module_name]
        else:
            module = importlib.import_module(module_name)

        # Add logger if not present
        if not hasattr(module, 'logger'):
            module.logger = logging.getLogger(module_name)
            logger.info(f"Added logger to module {module_name}")

        # Return the patched module
        return module
    except ImportError:
        logger.warning(f"Could not import module {module_name}")
        return None
    except Exception as e:
        logger.error(f"Error patching module {module_name}: {e}")
        return None

def patch_all_mcp_resources():
    \"\"\"Patch all MCP resource modules.\"\"\"
    modules_to_patch = [
        'mcp.server.lowlevel.server',
        'mcp.server.lowlevel.resource',
        'mcp.server.lowlevel.handler',
        'mcp.server.fastmcp'
    ]

    for module_name in modules_to_patch:
        patch_module(module_name)

    logger.info("Completed MCP resource module patching")

if __name__ == "__main__":
    patch_all_mcp_resources()
"""

    with open(wrapper_path, 'w') as f:
        f.write(content)

    # Make executable
    os.chmod(wrapper_path, 0o755)

    logger.info(f"Created wrapper module at {wrapper_path}")
    return wrapper_path

def main():
    """Main function."""
    logger.info("Starting direct fix for MCP resource handlers")

    # Fix resource handlers directly
    fix_direct_resource_handlers()

    # Fix resource templates
    fix_resource_templates()

    # Try to fix directly in the MCP module
    fix_directly_in_mcp_module()

    # Create wrapper module
    wrapper_path = create_wrapper_module()

    logger.info(f"Resource handler fixes complete. Use {wrapper_path} to ensure loggers are defined at runtime.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
