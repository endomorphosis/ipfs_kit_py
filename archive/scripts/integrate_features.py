#!/usr/bin/env python3
"""
Feature Integration for MCP Server

This script integrates features from various experimental implementations into
the final MCP server implementation, focusing on restoring the 53+ model support.
"""

import os
import sys
import json
import logging
import importlib
import traceback
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("integrate_features.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("integrate-features")

# Default paths and settings
DEFAULT_OUTPUT_FILE = "fixed_final_mcp_server.py"
DEFAULT_BACKUP_DIR = "backup_files"

# Source files to extract features from
FEATURE_SOURCES = [
    "final_mcp_server.py",
    "enhanced_mcp_server_fixed.py",
    "direct_mcp_server.py",
    "vfs_mcp_server.py",
    "fixed_final_mcp_server.py"
]

def backup_file(file_path: str, backup_dir: str = DEFAULT_BACKUP_DIR):
    """Create a backup of the given file."""
    if not os.path.exists(file_path):
        logger.warning(f"File does not exist, no backup needed: {file_path}")
        return False
    
    # Create backup directory if it doesn't exist
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Get the filename
    filename = os.path.basename(file_path)
    
    # Create a timestamped backup name
    import time
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{filename}.{timestamp}.bak"
    
    # Full path to the backup file
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Copy the file
    import shutil
    shutil.copy2(file_path, backup_path)
    
    logger.info(f"Backed up {file_path} to {backup_path}")
    return True

def extract_model_code(source_file: str) -> Dict[str, str]:
    """Extract model-related code from the source file."""
    if not os.path.exists(source_file):
        logger.warning(f"Source file not found: {source_file}")
        return {}
    
    with open(source_file, 'r') as f:
        content = f.read()
    
    # Dictionary to store extracted code
    extracted = {}
    
    # Look for model-related code patterns
    model_patterns = [
        # Model class definitions
        {
            "pattern": r"class\s+(\w+Model).*?:.*?(def __init__.*?)(?=\n\s*class|\n\s*def|\Z)",
            "key_prefix": "model_class_",
            "multiline": True
        },
        # Model initialization
        {
            "pattern": r"(def\s+(?:init|initialize|setup)_models.*?:.*?)(?=\n\s*def|\Z)",
            "key_prefix": "model_init_",
            "multiline": True
        },
        # Model registration
        {
            "pattern": r"(def\s+(?:register|add)_models.*?:.*?)(?=\n\s*def|\Z)",
            "key_prefix": "model_reg_",
            "multiline": True
        },
        # Model lists or dictionaries
        {
            "pattern": r"((?:AVAILABLE_MODELS|MODEL_CONFIGS|models)\s*=\s*\{[^}]*\})",
            "key_prefix": "model_dict_",
            "multiline": True
        }
    ]
    
    import re
    for pattern_info in model_patterns:
        pattern = pattern_info["pattern"]
        key_prefix = pattern_info["key_prefix"]
        multiline = pattern_info.get("multiline", False)
        
        # Find all matches
        flags = re.DOTALL if multiline else 0
        matches = re.finditer(pattern, content, flags)
        
        # Process each match
        for i, match in enumerate(matches):
            if key_prefix == "model_class_":
                # For model classes, use the class name as part of the key
                class_name = match.group(1)
                key = f"{key_prefix}{class_name}"
            else:
                # For other patterns, use index number
                key = f"{key_prefix}{i}"
            
            # Get the full matched text (either full match or specific group)
            if key_prefix == "model_class_":
                extracted_code = match.group(0)  # Full match for classes
            elif key_prefix == "model_dict_":
                extracted_code = match.group(1)  # Just the dictionary
            else:
                extracted_code = match.group(1)  # First group for functions
            
            extracted[key] = extracted_code
    
    logger.info(f"Extracted {len(extracted)} model-related code blocks from {source_file}")
    return extracted

def extract_jsonrpc_code(source_file: str) -> Dict[str, str]:
    """Extract JSON-RPC related code from the source file."""
    if not os.path.exists(source_file):
        logger.warning(f"Source file not found: {source_file}")
        return {}
    
    with open(source_file, 'r') as f:
        content = f.read()
    
    # Dictionary to store extracted code
    extracted = {}
    
    # Look for JSON-RPC related code patterns
    jsonrpc_patterns = [
        # Dispatcher initialization
        {
            "pattern": r"(jsonrpc_dispatcher\s*=.*?Dispatcher\(\).*?)",
            "key_prefix": "jsonrpc_init_",
            "multiline": True
        },
        # JSON-RPC handler functions
        {
            "pattern": r"(async\s+def\s+handle_jsonrpc.*?:.*?)(?=\n\s*async\s+def|\n\s*def|\Z)",
            "key_prefix": "jsonrpc_handler_",
            "multiline": True
        },
        # JSON-RPC method registration
        {
            "pattern": r"(@jsonrpc_dispatcher\.add_method.*?def\s+(\w+).*?:.*?)(?=\n\s*@|\n\s*def|\Z)",
            "key_prefix": "jsonrpc_method_",
            "multiline": True
        },
        # JSON-RPC setup functions
        {
            "pattern": r"(def\s+setup_jsonrpc.*?:.*?)(?=\n\s*def|\Z)",
            "key_prefix": "jsonrpc_setup_",
            "multiline": True
        }
    ]
    
    import re
    for pattern_info in jsonrpc_patterns:
        pattern = pattern_info["pattern"]
        key_prefix = pattern_info["key_prefix"]
        multiline = pattern_info.get("multiline", False)
        
        # Find all matches
        flags = re.DOTALL if multiline else 0
        matches = re.finditer(pattern, content, flags)
        
        # Process each match
        for i, match in enumerate(matches):
            if key_prefix == "jsonrpc_method_":
                # For methods, use the method name as part of the key
                method_name = match.group(2)
                key = f"{key_prefix}{method_name}"
            else:
                # For other patterns, use index number
                key = f"{key_prefix}{i}"
            
            # Get the full matched text
            extracted_code = match.group(1)
            
            extracted[key] = extracted_code
    
    logger.info(f"Extracted {len(extracted)} JSON-RPC related code blocks from {source_file}")
    return extracted

def extract_tool_registration_code(source_file: str) -> Dict[str, str]:
    """Extract tool registration related code from the source file."""
    if not os.path.exists(source_file):
        logger.warning(f"Source file not found: {source_file}")
        return {}
    
    with open(source_file, 'r') as f:
        content = f.read()
    
    # Dictionary to store extracted code
    extracted = {}
    
    # Look for tool registration related code patterns
    tool_patterns = [
        # Tool registration functions
        {
            "pattern": r"(def\s+register_(?:all_|ipfs_|vfs_|)tools.*?:.*?)(?=\n\s*def|\Z)",
            "key_prefix": "tool_reg_func_",
            "multiline": True
        },
        # Tool decorator usage
        {
            "pattern": r"(@(?:server\.tool|register_tool).*?def\s+(\w+).*?:.*?)(?=\n\s*@|\n\s*def|\Z)",
            "key_prefix": "tool_decorator_",
            "multiline": True
        },
        # Tool imports
        {
            "pattern": r"(import\s+[^;]+?(?:tools|tool).*?(?:\n|$))",
            "key_prefix": "tool_import_",
            "multiline": False
        }
    ]
    
    import re
    for pattern_info in tool_patterns:
        pattern = pattern_info["pattern"]
        key_prefix = pattern_info["key_prefix"]
        multiline = pattern_info.get("multiline", False)
        
        # Find all matches
        flags = re.DOTALL if multiline else 0
        matches = re.finditer(pattern, content, flags)
        
        # Process each match
        for i, match in enumerate(matches):
            if key_prefix == "tool_decorator_":
                # For tool decorators, use the function name as part of the key
                func_name = match.group(2)
                key = f"{key_prefix}{func_name}"
            else:
                # For other patterns, use index number
                key = f"{key_prefix}{i}"
            
            # Get the full matched text
            extracted_code = match.group(1)
            
            extracted[key] = extracted_code
    
    logger.info(f"Extracted {len(extracted)} tool registration related code blocks from {source_file}")
    return extracted

def extract_missing_features(source_files: List[str]) -> Dict[str, Dict[str, str]]:
    """Extract missing features from the source files."""
    # Dictionary to store all extracted features
    all_features = {
        "models": {},
        "jsonrpc": {},
        "tools": {}
    }
    
    # Process each source file
    for source_file in source_files:
        if not os.path.exists(source_file):
            logger.warning(f"Source file not found: {source_file}")
            continue
        
        logger.info(f"Extracting features from {source_file}")
        
        # Extract model code
        model_code = extract_model_code(source_file)
        all_features["models"].update(model_code)
        
        # Extract JSON-RPC code
        jsonrpc_code = extract_jsonrpc_code(source_file)
        all_features["jsonrpc"].update(jsonrpc_code)
        
        # Extract tool registration code
        tool_code = extract_tool_registration_code(source_file)
        all_features["tools"].update(tool_code)
    
    logger.info(f"Extracted a total of {len(all_features['models'])} model features, "
                f"{len(all_features['jsonrpc'])} JSON-RPC features, and "
                f"{len(all_features['tools'])} tool registration features")
    
    return all_features

def integrate_features(target_file: str, features: Dict[str, Dict[str, str]], output_file: str):
    """Integrate the extracted features into the target file."""
    if not os.path.exists(target_file):
        logger.error(f"Target file not found: {target_file}")
        return False
    
    # Read the target file
    with open(target_file, 'r') as f:
        content = f.read()
    
    # Create a backup of the target file
    backup_file(target_file)
    
    logger.info(f"Integrating features into {target_file}")
    
    # Track modifications
    modifications = []
    
    # Integrate model code
    if features["models"]:
        logger.info(f"Integrating {len(features['models'])} model features")
        
        # Look for appropriate insertion points
        import re
        
        # For model class definitions, insert before the first function definition after imports
        model_class_insertion_point = re.search(r"(# Tool registration functions|def\s+\w+.*?:)", content)
        if model_class_insertion_point:
            pos = model_class_insertion_point.start()
            
            # Insert model class definitions
            model_classes = "\n\n# Model Classes\n"
            for key, code in features["models"].items():
                if key.startswith("model_class_"):
                    model_classes += f"\n{code}\n"
            
            content = content[:pos] + model_classes + content[pos:]
            modifications.append("Added model class definitions")
        
        # For model initialization, insert in the main function
        model_init_insertion_point = re.search(r"def\s+main.*?\(.*?\).*?:", content)
        if model_init_insertion_point:
            # Find the appropriate indent level
            indent_match = re.search(r"(\s+)logger\.info", content[model_init_insertion_point.end():])
            if indent_match:
                indent = indent_match.group(1)
                
                # Search for a good insertion point within the main function
                init_pos = content.find("# Register all tools", model_init_insertion_point.end())
                if init_pos == -1:
                    init_pos = content.find("if not register_all_tools()", model_init_insertion_point.end())
                
                if init_pos != -1:
                    # Insert model initialization code
                    model_init_code = f"\n{indent}# Initialize and register models\n"
                    for key, code in features["models"].items():
                        if key.startswith("model_init_") or key.startswith("model_reg_"):
                            # Adjust indentation
                            indented_code = "\n".join(f"{indent}{line}" for line in code.split("\n"))
                            model_init_code += f"\n{indented_code}\n"
                    
                    content = content[:init_pos] + model_init_code + content[init_pos:]
                    modifications.append("Added model initialization code")
    
    # Integrate JSON-RPC code
    if features["jsonrpc"]:
        logger.info(f"Integrating {len(features['jsonrpc'])} JSON-RPC features")
        
        import re
        
        # Find the JSON-RPC setup function
        jsonrpc_setup_match = re.search(r"def\s+setup_jsonrpc.*?:.*?return\s+(?:True|False)", content, re.DOTALL)
        if jsonrpc_setup_match:
            # Replace the JSON-RPC setup function with a more comprehensive one
            for key, code in features["jsonrpc"].items():
                if key.startswith("jsonrpc_setup_"):
                    content = content[:jsonrpc_setup_match.start()] + code + content[jsonrpc_setup_match.end():]
                    modifications.append("Enhanced JSON-RPC setup function")
                    break
        
        # Add any missing JSON-RPC methods
        jsonrpc_method_match = re.search(r"@jsonrpc_dispatcher\.add_method.*?def\s+\w+.*?:", content, re.DOTALL)
        if jsonrpc_method_match:
            method_pos = content.find("logger.info(\"JSON-RPC dispatcher initialized successfully\")", jsonrpc_method_match.end())
            if method_pos != -1:
                # Add missing JSON-RPC methods before the success log
                jsonrpc_methods = "\n"
                for key, code in features["jsonrpc"].items():
                    if key.startswith("jsonrpc_method_") and key not in content:
                        jsonrpc_methods += f"\n{code}\n"
                
                if len(jsonrpc_methods) > 1:  # More than just the initial newline
                    content = content[:method_pos] + jsonrpc_methods + content[method_pos:]
                    modifications.append("Added missing JSON-RPC methods")
        
        # Enhance the JSON-RPC handler function
        jsonrpc_handler_match = re.search(r"async\s+def\s+handle_jsonrpc.*?:", content, re.DOTALL)
        if jsonrpc_handler_match:
            for key, code in features["jsonrpc"].items():
                if key.startswith("jsonrpc_handler_") and "dispatch" in code and "to_dict" in code:
                    # Find the end of the function
                    handler_end = content.find("\n\n", jsonrpc_handler_match.end())
                    if handler_end != -1:
                        content = content[:jsonrpc_handler_match.start()] + code + content[handler_end:]
                        modifications.append("Enhanced JSON-RPC handler function")
                        break
    
    # Integrate tool registration code
    if features["tools"]:
        logger.info(f"Integrating {len(features['tools'])} tool registration features")
        
        import re
        
        # Find the tool registration function
        tool_reg_match = re.search(r"def\s+register_all_tools.*?:.*?return\s+(?:True|False)", content, re.DOTALL)
        if tool_reg_match:
            # Enhance the tool registration function
            for key, code in features["tools"].items():
                if key.startswith("tool_reg_func_") and "register_all_tools" in code:
                    if len(code.split("\n")) > len(content[tool_reg_match.start():tool_reg_match.end()].split("\n")):
                        content = content[:tool_reg_match.start()] + code + content[tool_reg_match.end():]
                        modifications.append("Enhanced tool registration function")
                        break
    
    # Add model initialization and lists at global level if missing
    if "AVAILABLE_MODELS" not in content and any(key.startswith("model_dict_") for key in features["models"]):
        # Find an appropriate insertion point near the beginning of the file
        import re
        global_vars_pos = re.search(r"# Global state", content)
        if global_vars_pos:
            pos = global_vars_pos.end()
            
            # Insert model-related global variables
            model_globals = "\n\n# Model registry and configuration\n"
            for key, code in features["models"].items():
                if key.startswith("model_dict_"):
                    model_globals += f"{code}\n\n"
            
            content = content[:pos] + model_globals + content[pos:]
            modifications.append("Added model registry and configuration globals")
    
    # Add list_models method to JSON-RPC if missing
    if "list_models" not in content and "AVAILABLE_MODELS" in content:
        import re
        # Find a position after ping method but before JSON-RPC success message
        list_models_pos = re.search(r"@jsonrpc_dispatcher\.add_method.*?def\s+ping.*?return\s+\{.*?\}", content, re.DOTALL)
        if list_models_pos:
            pos = list_models_pos.end()
            
            # Create a list_models method
            list_models_code = """
        
        @jsonrpc_dispatcher.add_method
        async def list_models(**kwargs):
            # List available models and their configurations
            if "AVAILABLE_MODELS" in globals():
                return AVAILABLE_MODELS
            else:
                return {"error": "No models available"}
        """
            
            content = content[:pos] + list_models_code + content[pos:]
            modifications.append("Added list_models method to JSON-RPC")
    
    # Write the modified content to the output file
    with open(output_file, 'w') as f:
        f.write(content)
    
    logger.info(f"Integrated features into {output_file}")
    logger.info(f"Modifications: {', '.join(modifications)}")
    
    return True

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Integrate features from various MCP implementations")
    parser.add_argument("--sources", nargs="+", default=FEATURE_SOURCES,
                        help="Source files to extract features from")
    parser.add_argument("--target", default="fixed_final_mcp_server.py",
                        help="Target file to integrate features into")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_FILE,
                        help="Output file to write the integrated code to")
    parser.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR,
                        help="Directory to store backup files")
    args = parser.parse_args()
    
    logger.info(f"Starting feature integration")
    logger.info(f"Sources: {', '.join(args.sources)}")
    logger.info(f"Target: {args.target}")
    logger.info(f"Output: {args.output}")
    
    # Extract missing features from source files
    features = extract_missing_features(args.sources)
    
    # Integrate features into the target file
    result = integrate_features(args.target, features, args.output)
    
    if result:
        logger.info(f"Feature integration completed successfully")
        return 0
    else:
        logger.error(f"Feature integration failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
