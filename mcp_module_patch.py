#!/usr/bin/env python3
"""
MCP Server Module Patch

This script applies compatibility patches to MCP server code to ensure
all modules and dependencies work correctly.
"""

import os
import sys
import re
import logging
import argparse
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("patching.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("patching")

# Patches to apply
PATCHES = [
    {
        "name": "Fix import paths",
        "description": "Ensure all import paths are correct",
        "pattern": r"from\s+(\w+(?:\.\w+)*)\s+import",
        "check": lambda match: not importlib.util.find_spec(match.group(1)),
        "apply": lambda content, match: fix_import_path(content, match)
    },
    {
        "name": "Fix model providers",
        "description": "Ensure model providers are properly registered",
        "pattern": r"model_registry\s*=\s*\{[^}]*\}",
        "check": lambda match: True,  # Always apply this patch
        "apply": lambda content, match: ensure_model_providers(content, match)
    },
    {
        "name": "Fix JSONRPCHandler",
        "description": "Fix JSON-RPC handler for robust error recovery",
        "pattern": r"class\s+JSONRPCHandler",
        "check": lambda match: "def handle_jsonrpc_error" not in match.string,
        "apply": lambda content, match: add_error_handler(content, match)
    },
    {
        "name": "Fix logging configuration",
        "description": "Ensure logging is properly configured",
        "pattern": r"import\s+logging",
        "check": lambda match: "basicConfig" not in match.string,
        "apply": lambda content, match: add_logging_config(content, match)
    }
]

def fix_import_path(content: str, match: re.Match) -> str:
    """Fix import path for a module."""
    module_path = match.group(1)
    
    # Try various path transformations
    potential_paths = [
        f"ipfs_kit_py.{module_path}",
        f"mcp.{module_path}",
        f"ipfs_kit_py.mcp.{module_path}"
    ]
    
    for path in potential_paths:
        if importlib.util.find_spec(path):
            logger.info(f"Fixing import path: {module_path} -> {path}")
            fixed_content = content.replace(
                f"from {module_path} import",
                f"from {path} import"
            )
            return fixed_content
    
    logger.warning(f"Could not fix import path for {module_path}")
    return content

def ensure_model_providers(content: str, match: re.Match) -> str:
    """Ensure all required model providers are included."""
    model_registry_text = match.group(0)
    
    required_providers = [
        "openai", "anthropic", "cohere", "google", "meta", "aws", "azure",
        "huggingface", "stability", "deepmind", "mistral", "together",
        "replicate"
    ]
    
    # Count how many required providers are missing
    missing_providers = []
    for provider in required_providers:
        if f'"{provider}"' not in model_registry_text and f"'{provider}'" not in model_registry_text:
            missing_providers.append(provider)
    
    if not missing_providers:
        logger.info("All required model providers are present")
        return content
    
    logger.info(f"Adding missing model providers: {', '.join(missing_providers)}")
    
    # Create a modified registry that includes all providers
    # First, find the end of the registry
    registry_end = content.find("}", match.start()) + 1
    
    # Add missing providers
    provider_entries = []
    for provider in missing_providers:
        provider_entries.append(f"""
    "{provider}_dummy_model": {{
        "id": "{provider}_dummy_model",
        "name": "{provider.capitalize()} Dummy Model",
        "provider": "{provider}",
        "type": "text",
        "max_tokens": 4096,
        "supports_streaming": True
    }}"""
        )
    
    # Insert the new entries before the closing brace
    if provider_entries:
        fixed_content = content[:registry_end-1] + ",".join(provider_entries) + content[registry_end-1:]
        return fixed_content
    
    return content

def add_error_handler(content: str, match: re.Match) -> str:
    """Add error handler to JSONRPCHandler class."""
    if "handle_jsonrpc_error" in content:
        logger.info("Error handler already exists")
        return content
    
    logger.info("Adding error handler to JSONRPCHandler")
    
    # Find the end of the JSONRPCHandler class
    class_start = match.start()
    
    # Find the next class definition
    next_class = re.search(r"class\s+\w+", content[class_start+1:])
    if next_class:
        class_end = class_start + 1 + next_class.start()
    else:
        # No next class, assume it goes to the end of the file
        class_end = len(content)
    
    # Add the error handler method
    error_handler = """
    def handle_jsonrpc_error(self, error_code, error_message, request_id=None):
        \"\"\"Handle JSON-RPC errors.\"\"\"
        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": error_code,
                "message": error_message
            }
        }
        
        if request_id is not None:
            response["id"] = request_id
        
        return response
"""
    
    # Insert the error handler before the end of the class
    fixed_content = content[:class_end] + error_handler + content[class_end:]
    return fixed_content

def add_logging_config(content: str, match: re.Match) -> str:
    """Add logging configuration if missing."""
    if "basicConfig" in content:
        logger.info("Logging configuration already exists")
        return content
    
    logger.info("Adding logging configuration")
    
    # Find a good place to insert logging configuration
    # Try to insert after the imports
    import_section_end = 0
    for line_match in re.finditer(r"^(?:import|from)\s+.*$", content, re.MULTILINE):
        import_section_end = max(import_section_end, line_match.end())
    
    if import_section_end > 0:
        logging_config = """

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mcp_server")

"""
        fixed_content = content[:import_section_end] + logging_config + content[import_section_end:]
        return fixed_content
    
    return content

def apply_patches(file_path: str) -> bool:
    """Apply all patches to a file."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        patched = False
        
        for patch in PATCHES:
            logger.info(f"Checking for {patch['name']}...")
            
            for match in re.finditer(patch["pattern"], content, re.DOTALL):
                if patch["check"](match):
                    logger.info(f"Applying patch: {patch['description']}")
                    content = patch["apply"](content, match)
                    patched = True
        
        if patched:
            # Create backup
            backup_path = f"{file_path}.bak.patch"
            logger.info(f"Creating backup: {backup_path}")
            with open(backup_path, 'w') as f:
                f.write(original_content)
            
            # Write patched content
            logger.info(f"Writing patched file: {file_path}")
            with open(file_path, 'w') as f:
                f.write(content)
            
            return True
        else:
            logger.info("No patches needed to be applied")
            return True
    
    except Exception as e:
        logger.error(f"Error applying patches: {e}")
        return False

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Apply compatibility patches to MCP server code")
    parser.add_argument('--file', required=True, help="File to patch")
    parser.add_argument('--force', action='store_true', help="Force apply patches even if not needed")
    args = parser.parse_args()
    
    logger.info(f"Starting patching process for {args.file}")
    
    if apply_patches(args.file):
        logger.info("Patching completed successfully")
        return 0
    else:
        logger.error("Patching failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
