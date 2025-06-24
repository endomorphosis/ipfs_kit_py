#!/usr/bin/env python3
"""
MCP API Documentation Generator

This script generates comprehensive API documentation for the MCP server,
including endpoints, parameters, and example requests/responses.
"""

import os
import sys
import json
import inspect
import re
import logging
import argparse
from typing import Dict, Any, List, Set, Optional, Union, Tuple
import importlib
import importlib.util
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Output formats
FORMAT_MARKDOWN = "markdown"
FORMAT_JSON = "json"
FORMAT_HTML = "html"

# Documentation template for markdown
MARKDOWN_TEMPLATE = """# MCP Server API Documentation

## Overview

The Model-Controller-Persistence (MCP) server provides a unified API for interacting with IPFS and various storage backends.
This document provides comprehensive documentation for all available endpoints.

## Base URL

All API endpoints are prefixed with: `/api/v0`

## Authentication

{auth_section}

## API Endpoints

{endpoints_section}

## Models

{models_section}

## Error Codes

{error_codes_section}

## Examples

{examples_section}

---

Documentation generated: {generation_time}
"""

# HTML Template (basic)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Server API Documentation</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2, h3, h4 {
            color: #0066cc;
            margin-top: 1.5em;
        }
        code {
            background-color: #f5f5f5;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: monospace;
        }
        pre {
            background-color: #f5f5f5;
            padding: 16px;
            border-radius: 5px;
            overflow-x: auto;
        }
        pre code {
            background-color: transparent;
            padding: 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        .method {
            display: inline-block;
            padding: 3px 6px;
            border-radius: 3px;
            font-weight: bold;
            margin-right: 8px;
        }
        .method-get {
            background-color: #61affe;
            color: white;
        }
        .method-post {
            background-color: #49cc90;
            color: white;
        }
        .method-put {
            background-color: #fca130;
            color: white;
        }
        .method-delete {
            background-color: #f93e3e;
            color: white;
        }
        .endpoint {
            margin-bottom: 40px;
            border-bottom: 1px solid #eee;
            padding-bottom: 20px;
        }
        .description {
            margin-bottom: 16px;
        }
        .parameters {
            margin-bottom: 16px;
        }
        .example {
            margin-top: 16px;
        }
        .nav {
            position: sticky;
            top: 0;
            background-color: white;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
            margin-bottom: 20px;
        }
        .nav ul {
            list-style-type: none;
            padding: 0;
            display: flex;
            flex-wrap: wrap;
        }
        .nav ul li {
            margin-right: 16px;
            margin-bottom: 8px;
        }
        .nav a {
            text-decoration: none;
            color: #0066cc;
        }
        .nav a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>MCP Server API Documentation</h1>

    <div class="nav">
        <ul>
            <li><a href="#overview">Overview</a></li>
            <li><a href="#authentication">Authentication</a></li>
            <li><a href="#endpoints">API Endpoints</a></li>
            <li><a href="#models">Models</a></li>
            <li><a href="#errors">Error Codes</a></li>
            <li><a href="#examples">Examples</a></li>
        </ul>
    </div>

    <h2 id="overview">Overview</h2>
    <p>The Model-Controller-Persistence (MCP) server provides a unified API for interacting with IPFS and various storage backends.
    This document provides comprehensive documentation for all available endpoints.</p>

    <h2>Base URL</h2>
    <p>All API endpoints are prefixed with: <code>/api/v0</code></p>

    <h2 id="authentication">Authentication</h2>
    {auth_section}

    <h2 id="endpoints">API Endpoints</h2>
    {endpoints_section}

    <h2 id="models">Models</h2>
    {models_section}

    <h2 id="errors">Error Codes</h2>
    {error_codes_section}

    <h2 id="examples">Examples</h2>
    {examples_section}

    <hr>
    <footer>
        <p>Documentation generated: {generation_time}</p>
    </footer>
</body>
</html>
"""

def find_mcp_server_files() -> List[str]:
    """
    Find all MCP server implementation files.

    Returns:
        List of file paths
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Files to search
    server_files = []

    # Look for main server files
    server_patterns = ["*mcp_server*.py", "enhanced_mcp_server.py", "fixed_mcp_server.py", "run_server.py"]
    for pattern in server_patterns:
        server_files.extend([str(f) for f in Path(root_dir).glob(pattern)])

    # Look for extension files
    ext_dir = os.path.join(root_dir, "mcp_extensions")
    if os.path.exists(ext_dir):
        for ext_file in Path(ext_dir).glob("*_extension.py"):
            server_files.append(str(ext_file))

    # Look for specific module files
    module_patterns = ["mcp_*.py", "*_storage.py"]
    for pattern in module_patterns:
        server_files.extend([str(f) for f in Path(root_dir).glob(pattern)])

    return server_files

def extract_routes_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract API routes from a Python file.

    Args:
        file_path: Path to the Python file

    Returns:
        List of route information dictionaries
    """
    with open(file_path, 'r') as f:
        content = f.read()

    # Extract route definitions
    routes = []

    # Pattern for router.get/post/put/delete
    router_pattern = r'@router\.(get|post|put|delete)\([\'"]([^\'"]+)[\'"](.*?)\)\s*\n\s*async\s+def\s+([a-zA-Z0-9_]+)'
    router_matches = re.finditer(router_pattern, content, re.DOTALL)

    for match in router_matches:
        method, path, params, func_name = match.groups()

        # Extract docstring for the function
        func_pattern = f"async def {func_name}(.*?):(.*?)(?=\\n\\s*@|\\n\\s*def|$)"
        func_match = re.search(func_pattern, content, re.DOTALL)

        docstring = ""
        if func_match:
            func_body = func_match.group(2)
            doc_match = re.search(r'"""(.*?)"""', func_body, re.DOTALL)
            if doc_match:
                docstring = doc_match.group(1).strip()

        # Extract parameters from function signature
        param_list = []
        if func_match:
            func_sig = func_match.group(1)
            param_matches = re.finditer(r'([a-zA-Z0-9_]+)(?:\s*:\s*([a-zA-Z0-9_\[\]]+))?(?:\s*=\s*([^,)]+))?', func_sig)

            for param_match in param_matches:
                param_name, param_type, param_default = param_match.groups()
                if param_name != 'self' and param_name != 'cls':
                    param_list.append({
                        'name': param_name,
                        'type': param_type,
                        'default': param_default
                    })

        routes.append({
            'method': method.upper(),
            'path': path,
            'function': func_name,
            'docstring': docstring,
            'parameters': param_list,
            'file': os.path.basename(file_path)
        })

    # Pattern for app.get/post/put/delete
    app_pattern = r'@app\.(get|post|put|delete)\([\'"]([^\'"]+)[\'"](.*?)\)\s*\n\s*async\s+def\s+([a-zA-Z0-9_]+)'
    app_matches = re.finditer(app_pattern, content, re.DOTALL)

    for match in app_matches:
        method, path, params, func_name = match.groups()

        # Extract docstring for the function
        func_pattern = f"async def {func_name}(.*?):(.*?)(?=\\n\\s*@|\\n\\s*def|$)"
        func_match = re.search(func_pattern, content, re.DOTALL)

        docstring = ""
        if func_match:
            func_body = func_match.group(2)
            doc_match = re.search(r'"""(.*?)"""', func_body, re.DOTALL)
            if doc_match:
                docstring = doc_match.group(1).strip()

        # Extract parameters from function signature
        param_list = []
        if func_match:
            func_sig = func_match.group(1)
            param_matches = re.finditer(r'([a-zA-Z0-9_]+)(?:\s*:\s*([a-zA-Z0-9_\[\]]+))?(?:\s*=\s*([^,)]+))?', func_sig)

            for param_match in param_matches:
                param_name, param_type, param_default = param_match.groups()
                if param_name != 'self' and param_name != 'cls':
                    param_list.append({
                        'name': param_name,
                        'type': param_type,
                        'default': param_default
                    })

        routes.append({
            'method': method.upper(),
            'path': path,
            'function': func_name,
            'docstring': docstring,
            'parameters': param_list,
            'file': os.path.basename(file_path)
        })

    return routes

def extract_all_routes() -> List[Dict[str, Any]]:
    """
    Extract all API routes from MCP server files.

    Returns:
        List of route information dictionaries
    """
    all_routes = []
    server_files = find_mcp_server_files()

    for file_path in server_files:
        try:
            routes = extract_routes_from_file(file_path)
            all_routes.extend(routes)
        except Exception as e:
            logger.warning(f"Error processing file {file_path}: {e}")

    return all_routes

def extract_models() -> List[Dict[str, Any]]:
    """
    Extract Pydantic model definitions from MCP server files.

    Returns:
        List of model information dictionaries
    """
    models = []
    server_files = find_mcp_server_files()

    for file_path in server_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Look for class definitions that inherit from BaseModel
            model_pattern = r'class\s+([a-zA-Z0-9_]+)\s*\(\s*BaseModel\s*\):(.*?)(?=\n\s*class|\n\s*def|\n\s*@|$)'
            model_matches = re.finditer(model_pattern, content, re.DOTALL)

            for match in model_matches:
                model_name, model_body = match.groups()

                # Extract docstring
                docstring = ""
                doc_match = re.search(r'"""(.*?)"""', model_body, re.DOTALL)
                if doc_match:
                    docstring = doc_match.group(1).strip()

                # Extract fields
                fields = []
                field_pattern = r'([a-zA-Z0-9_]+)(?:\s*:\s*([a-zA-Z0-9_\[\]\"\'., ={}]+))?(?:\s*=\s*([^#\n]+))?'
                field_matches = re.finditer(field_pattern, model_body)

                for field_match in field_matches:
                    field_name, field_type, field_default = field_match.groups()

                    # Skip non-field attributes
                    if field_name.startswith('__') or field_name in ['Config', 'schema_extra']:
                        continue

                    # Clean up types and defaults
                    if field_type:
                        field_type = field_type.strip()

                    if field_default:
                        field_default = field_default.strip()

                    fields.append({
                        'name': field_name,
                        'type': field_type,
                        'default': field_default
                    })

                models.append({
                    'name': model_name,
                    'docstring': docstring,
                    'fields': fields,
                    'file': os.path.basename(file_path)
                })

        except Exception as e:
            logger.warning(f"Error extracting models from {file_path}: {e}")

    return models

def extract_error_codes() -> List[Dict[str, Any]]:
    """
    Extract error codes from error handling module.

    Returns:
        List of error code information dictionaries
    """
    error_codes = []

    # Look for mcp_error_handling.py
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    error_file = os.path.join(root_dir, "mcp_error_handling.py")

    if not os.path.exists(error_file):
        logger.warning(f"Error handling file not found: {error_file}")
        return error_codes

    try:
        with open(error_file, 'r') as f:
            content = f.read()

        # Extract ERROR_CODES dictionary
        error_codes_pattern = r'ERROR_CODES\s*=\s*{(.*?)}'
        error_codes_match = re.search(error_codes_pattern, content, re.DOTALL)

        if not error_codes_match:
            logger.warning("ERROR_CODES dictionary not found in error handling file")
            return error_codes

        error_codes_str = error_codes_match.group(1)

        # Extract individual error codes
        code_pattern = r'"([A-Z_]+)":\s*{(.*?)}'
        code_matches = re.finditer(code_pattern, error_codes_str, re.DOTALL)

        for match in code_matches:
            code, props = match.groups()

            # Extract properties
            status_match = re.search(r'"status_code":\s*([^,}]+)', props)
            message_match = re.search(r'"message":\s*"([^"]+)"', props)
            suggestion_match = re.search(r'"suggestion":\s*"([^"]+)"', props)

            status_code = status_match.group(1) if status_match else "unknown"
            message = message_match.group(1) if message_match else ""
            suggestion = suggestion_match.group(1) if suggestion_match else ""

            error_codes.append({
                'code': code,
                'status_code': status_code,
                'message': message,
                'suggestion': suggestion
            })

    except Exception as e:
        logger.warning(f"Error extracting error codes: {e}")

    return error_codes

def generate_examples() -> List[Dict[str, Any]]:
    """
    Generate example requests and responses for API endpoints.

    Returns:
        List of example information dictionaries
    """
    examples = []

    # Look for examples directory
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    examples_dir = os.path.join(root_dir, "examples")

    if not os.path.exists(examples_dir):
        logger.warning(f"Examples directory not found: {examples_dir}")

        # Generate basic examples for common endpoints
        examples.append({
            'title': 'Add a file to IPFS',
            'endpoint': '/api/v0/ipfs/add',
            'method': 'POST',
            'request': {
                'type': 'multipart/form-data',
                'data': {
                    'file': '(binary file content)'
                }
            },
            'response': {
                'success': True,
                'cid': 'QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx',
                'size': 1234,
                'name': 'example.txt'
            },
            'curl': 'curl -X POST -F "file=@example.txt" http://localhost:9997/api/v0/ipfs/add'
        })

        examples.append({
            'title': 'Retrieve content from IPFS',
            'endpoint': '/api/v0/ipfs/cat/{cid}',
            'method': 'GET',
            'request': {
                'path_params': {
                    'cid': 'QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx'
                }
            },
            'response': '(binary content)',
            'curl': 'curl http://localhost:9997/api/v0/ipfs/cat/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx'
        })

        examples.append({
            'title': 'Check server health',
            'endpoint': '/api/v0/health',
            'method': 'GET',
            'response': {
                'success': True,
                'status': 'healthy',
                'timestamp': 1650000000.0,
                'ipfs_daemon_running': True,
                'controllers': {
                    'ipfs': True,
                    'storage': True
                },
                'storage_backends': {
                    'ipfs': {'available': True},
                    'local': {'available': True},
                    'huggingface': {'available': True},
                    's3': {'available': True},
                    'filecoin': {'available': True},
                    'storacha': {'available': True},
                    'lassie': {'available': True}
                }
            },
            'curl': 'curl http://localhost:9997/api/v0/health'
        })

        return examples

    # Read example files
    for example_file in os.listdir(examples_dir):
        if example_file.endswith('.json'):
            try:
                with open(os.path.join(examples_dir, example_file), 'r') as f:
                    example_data = json.load(f)
                    examples.append(example_data)
            except Exception as e:
                logger.warning(f"Error reading example file {example_file}: {e}")

    return examples

def format_routes_markdown(routes: List[Dict[str, Any]], api_prefix: str = '/api/v0') -> str:
    """
    Format API routes as Markdown.

    Args:
        routes: List of route information dictionaries
        api_prefix: API prefix to prepend to routes

    Returns:
        Markdown string
    """
    # Group routes by category
    categories = {}

    for route in routes:
        path = route['path']
        parts = path.strip('/').split('/')

        if len(parts) > 0:
            category = parts[0]
        else:
            category = 'general'

        if category not in categories:
            categories[category] = []

        categories[category].append(route)

    # Sort categories and routes
    sorted_categories = sorted(categories.keys())

    # Format as Markdown
    markdown = ""

    for category in sorted_categories:
        markdown += f"### {category.capitalize()} Endpoints\n\n"

        for route in sorted(categories[category], key=lambda r: r['path']):
            full_path = f"{api_prefix}{route['path']}"
            markdown += f"#### `{route['method']}` {full_path}\n\n"

            if route['docstring']:
                markdown += f"{route['docstring']}\n\n"

            # Add parameters
            if route['parameters']:
                markdown += "**Parameters:**\n\n"
                markdown += "| Name | Type | Description | Required |\n"
                markdown += "|------|------|-------------|----------|\n"

                for param in route['parameters']:
                    # Skip self and request
                    if param['name'] in ['self', 'request']:
                        continue

                    param_type = param['type'] or "Any"
                    required = "Yes" if param['default'] is None else "No"

                    # Extract description from docstring
                    description = ""
                    if route['docstring']:
                        param_doc_match = re.search(rf"{param['name']}:\s*(.*?)(?=\n\s*\w+:|$)", route['docstring'], re.DOTALL)
                        if param_doc_match:
                            description = param_doc_match.group(1).strip()

                    markdown += f"| `{param['name']}` | `{param_type}` | {description} | {required} |\n"

                markdown += "\n"

            # Add source file info
            markdown += f"*Source file: `{route['file']}`*\n\n"
            markdown += "---\n\n"

    return markdown

def format_routes_html(routes: List[Dict[str, Any]], api_prefix: str = '/api/v0') -> str:
    """
    Format API routes as HTML.

    Args:
        routes: List of route information dictionaries
        api_prefix: API prefix to prepend to routes

    Returns:
        HTML string
    """
    # Group routes by category
    categories = {}

    for route in routes:
        path = route['path']
        parts = path.strip('/').split('/')

        if len(parts) > 0:
            category = parts[0]
        else:
            category = 'general'

        if category not in categories:
            categories[category] = []

        categories[category].append(route)

    # Sort categories and routes
    sorted_categories = sorted(categories.keys())

    # Format as HTML
    html = ""

    for category in sorted_categories:
        html += f'<h3 id="category-{category}">{category.capitalize()} Endpoints</h3>\n\n'

        for route in sorted(categories[category], key=lambda r: r['path']):
            full_path = f"{api_prefix}{route['path']}"

            method_class = f"method-{route['method'].lower()}"
            endpoint_id = f"endpoint-{category}-{route['function']}"

            html += f'<div class="endpoint" id="{endpoint_id}">\n'
            html += f'  <h4><span class="method {method_class}">{route["method"]}</span> {full_path}</h4>\n\n'

            if route['docstring']:
                html += f'  <div class="description">{route["docstring"]}</div>\n\n'

            # Add parameters
            if route['parameters']:
                html += '  <div class="parameters">\n'
                html += '    <h5>Parameters:</h5>\n'
                html += '    <table>\n'
                html += '      <tr><th>Name</th><th>Type</th><th>Description</th><th>Required</th></tr>\n'

                for param in route['parameters']:
                    # Skip self and request
                    if param['name'] in ['self', 'request']:
                        continue

                    param_type = param['type'] or "Any"
                    required = "Yes" if param['default'] is None else "No"

                    # Extract description from docstring
                    description = ""
                    if route['docstring']:
                        param_doc_match = re.search(rf"{param['name']}:\s*(.*?)(?=\n\s*\w+:|$)", route['docstring'], re.DOTALL)
                        if param_doc_match:
                            description = param_doc_match.group(1).strip()

                    html += f'      <tr><td><code>{param["name"]}</code></td><td><code>{param_type}</code></td><td>{description}</td><td>{required}</td></tr>\n'

                html += '    </table>\n'
                html += '  </div>\n\n'

            # Add source file info
            html += f'  <div class="source">Source file: <code>{route["file"]}</code></div>\n'
            html += '</div>\n\n'

    return html

def format_models_markdown(models: List[Dict[str, Any]]) -> str:
    """
    Format data models as Markdown.

    Args:
        models: List of model information dictionaries

    Returns:
        Markdown string
    """
    markdown = ""

    for model in sorted(models, key=lambda m: m['name']):
        markdown += f"### {model['name']}\n\n"

        if model['docstring']:
            markdown += f"{model['docstring']}\n\n"

        # Add fields
        if model['fields']:
            markdown += "**Fields:**\n\n"
            markdown += "| Name | Type | Default | Description |\n"
            markdown += "|------|------|---------|-------------|\n"

            for field in model['fields']:
                field_type = field['type'] or "Any"
                default = field['default'] or "Required"

                # Extract description from docstring
                description = ""
                if model['docstring']:
                    field_doc_match = re.search(rf"{field['name']}:\s*(.*?)(?=\n\s*\w+:|$)", model['docstring'], re.DOTALL)
                    if field_doc_match:
                        description = field_doc_match.group(1).strip()

                markdown += f"| `{field['name']}` | `{field_type}` | {default} | {description} |\n"

            markdown += "\n"

        # Add source file info
        markdown += f"*Source file: `{model['file']}`*\n\n"
        markdown += "---\n\n"

    return markdown

def format_models_html(models: List[Dict[str, Any]]) -> str:
    """
    Format data models as HTML.

    Args:
        models: List of model information dictionaries

    Returns:
        HTML string
    """
    html = ""

    for model in sorted(models, key=lambda m: m['name']):
        model_id = f"model-{model['name']}"

        html += f'<div class="model" id="{model_id}">\n'
        html += f'  <h3>{model["name"]}</h3>\n\n'

        if model['docstring']:
            html += f'  <div class="description">{model["docstring"]}</div>\n\n'

        # Add fields
        if model['fields']:
            html += '  <div class="fields">\n'
            html += '    <h4>Fields:</h4>\n'
            html += '    <table>\n'
            html += '      <tr><th>Name</th><th>Type</th><th>Default</th><th>Description</th></tr>\n'

            for field in model['fields']:
                field_type = field['type'] or "Any"
                default = field['default'] or "Required"

                # Extract description from docstring
                description = ""
                if model['docstring']:
                    field_doc_match = re.search(rf"{field['name']}:\s*(.*?)(?=\n\s*\w+:|$)", model['docstring'], re.DOTALL)
                    if field_doc_match:
                        description = field_doc_match.group(1).strip()

                html += f'      <tr><td><code>{field["name"]}</code></td><td><code>{field_type}</code></td><td>{default}</td><td>{description}</td></tr>\n'

            html += '    </table>\n'
            html += '  </div>\n\n'

        # Add source file info
        html += f'  <div class="source">Source file: <code>{model["file"]}</code></div>\n'
        html += '</div>\n\n'

    return html

def format_error_codes_markdown(error_codes: List[Dict[str, Any]]) -> str:
    """
    Format error codes as Markdown.

    Args:
        error_codes: List of error code information dictionaries

    Returns:
        Markdown string
    """
    markdown = "| Code | Status Code | Message | Suggestion |\n"
    markdown += "|------|------------|---------|------------|\n"

    for error in sorted(error_codes, key=lambda e: e['code']):
        markdown += f"| `{error['code']}` | {error['status_code']} | {error['message']} | {error['suggestion']} |\n"

    return markdown

def format_error_codes_html(error_codes: List[Dict[str, Any]]) -> str:
    """
    Format error codes as HTML.

    Args:
        error_codes: List of error code information dictionaries

    Returns:
        HTML string
    """
    html = '<div class="error-codes">\n'
    html += '  <table>\n'
    html += '    <tr><th>Code</th><th>Status Code</th><th>Message</th><th>Suggestion</th></tr>\n'

    for error in sorted(error_codes, key=lambda e: e['code']):
        html += f'    <tr><td><code>{error["code"]}</code></td><td>{error["status_code"]}</td><td>{error["message"]}</td><td>{error["suggestion"]}</td></tr>\n'

    html += '  </table>\n'
    html += '</div>\n'

    return html

def format_examples_markdown(examples: List[Dict[str, Any]]) -> str:
    """
    Format API examples as Markdown.

    Args:
        examples: List of example information dictionaries

    Returns:
        Markdown string
    """
    markdown = ""

    for i, example in enumerate(examples):
        markdown += f"### Example {i+1}: {example['title']}\n\n"
        markdown += f"**Endpoint:** `{example['method']}` {example['endpoint']}\n\n"

        # Request
        markdown += "**Request:**\n\n"

        if 'curl' in example:
            markdown += f"```bash\n{example['curl']}\n```\n\n"

        if 'request' in example:
            request = example['request']

            if 'type' in request:
                markdown += f"Content-Type: `{request['type']}`\n\n"

            if 'path_params' in request:
                markdown += "Path Parameters:\n```json\n"
                markdown += json.dumps(request['path_params'], indent=2)
                markdown += "\n```\n\n"

            if 'query_params' in request:
                markdown += "Query Parameters:\n```json\n"
                markdown += json.dumps(request['query_params'], indent=2)
                markdown += "\n```\n\n"

            if 'headers' in request:
                markdown += "Headers:\n```json\n"
                markdown += json.dumps(request['headers'], indent=2)
                markdown += "\n```\n\n"

            if 'data' in request:
                markdown += "Body:\n```json\n"
                markdown += json.dumps(request['data'], indent=2)
                markdown += "\n```\n\n"

        # Response
        markdown += "**Response:**\n\n"

        if isinstance(example['response'], dict):
            markdown += "```json\n"
            markdown += json.dumps(example['response'], indent=2)
            markdown += "\n```\n\n"
        else:
            markdown += f"```\n{example['response']}\n```\n\n"

        markdown += "---\n\n"

    return markdown

def format_examples_html(examples: List[Dict[str, Any]]) -> str:
    """
    Format API examples as HTML.

    Args:
        examples: List of example information dictionaries

    Returns:
        HTML string
    """
    html = ""

    for i, example in enumerate(examples):
        example_id = f"example-{i+1}"

        html += f'<div class="example" id="{example_id}">\n'
        html += f'  <h3>Example {i+1}: {example["title"]}</h3>\n\n'
        html += f'  <p><strong>Endpoint:</strong> <span class="method method-{example["method"].lower()}">{example["method"]}</span> {example["endpoint"]}</p>\n\n'

        # Request
        html += '  <div class="request">\n'
        html += '    <h4>Request:</h4>\n\n'

        if 'curl' in example:
            html += f'    <pre><code class="language-bash">{example["curl"]}</code></pre>\n\n'

        if 'request' in example:
            request = example['request']

            if 'type' in request:
                html += f'    <p>Content-Type: <code>{request["type"]}</code></p>\n\n'

            if 'path_params' in request:
                html += '    <p>Path Parameters:</p>\n'
                html += f'    <pre><code class="language-json">{json.dumps(request["path_params"], indent=2)}</code></pre>\n\n'

            if 'query_params' in request:
                html += '    <p>Query Parameters:</p>\n'
                html += f'    <pre><code class="language-json">{json.dumps(request["query_params"], indent=2)}</code></pre>\n\n'

            if 'headers' in request:
                html += '    <p>Headers:</p>\n'
                html += f'    <pre><code class="language-json">{json.dumps(request["headers"], indent=2)}</code></pre>\n\n'

            if 'data' in request:
                html += '    <p>Body:</p>\n'
                html += f'    <pre><code class="language-json">{json.dumps(request["data"], indent=2)}</code></pre>\n\n'

        html += '  </div>\n\n'

        # Response
        html += '  <div class="response">\n'
        html += '    <h4>Response:</h4>\n\n'

        if isinstance(example['response'], dict):
            html += f'    <pre><code class="language-json">{json.dumps(example["response"], indent=2)}</code></pre>\n\n'
        else:
            html += f'    <pre><code>{example["response"]}</code></pre>\n\n'

        html += '  </div>\n'
        html += '</div>\n\n'

    return html

def generate_documentation(output_path: str, format: str = FORMAT_MARKDOWN) -> None:
    """
    Generate comprehensive API documentation.

    Args:
        output_path: Path to write documentation file
        format: Output format (markdown, json, or html)
    """
    logger.info("Extracting API routes...")
    routes = extract_all_routes()
    logger.info(f"Found {len(routes)} API routes")

    logger.info("Extracting data models...")
    models = extract_models()
    logger.info(f"Found {len(models)} data models")

    logger.info("Extracting error codes...")
    error_codes = extract_error_codes()
    logger.info(f"Found {len(error_codes)} error codes")

    logger.info("Generating examples...")
    examples = generate_examples()
    logger.info(f"Generated {len(examples)} examples")

    # Generate documentation in the requested format
    if format == FORMAT_JSON:
        # Export as JSON
        doc_data = {
            "routes": routes,
            "models": models,
            "error_codes": error_codes,
            "examples": examples,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(output_path, 'w') as f:
            json.dump(doc_data, f, indent=2)

        logger.info(f"JSON documentation written to {output_path}")

    elif format == FORMAT_HTML:
        # Generate HTML
        import datetime

        # Format sections
        endpoints_html = format_routes_html(routes)
        models_html = format_models_html(models)
        error_codes_html = format_error_codes_html(error_codes)
        examples_html = format_examples_html(examples)

        # Basic auth section
        auth_html = """
        <p>Authentication is not required for most endpoints. However, some storage backends may require API keys to be configured on the server.</p>
        """

        # Fill template
        html_doc = HTML_TEMPLATE.format(
            auth_section=auth_html,
            endpoints_section=endpoints_html,
            models_section=models_html,
            error_codes_section=error_codes_html,
            examples_section=examples_html,
            generation_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        with open(output_path, 'w') as f:
            f.write(html_doc)

        logger.info(f"HTML documentation written to {output_path}")

    else:  # Default to Markdown
        # Generate Markdown
        import datetime

        # Format sections
        endpoints_md = format_routes_markdown(routes)
        models_md = format_models_markdown(models)
        error_codes_md = format_error_codes_markdown(error_codes)
        examples_md = format_examples_markdown(examples)

        # Basic auth section
        auth_md = """
Authentication is not required for most endpoints. However, some storage backends may require API keys to be configured on the server.
"""

        # Fill template
        md_doc = MARKDOWN_TEMPLATE.format(
            auth_section=auth_md,
            endpoints_section=endpoints_md,
            models_section=models_md,
            error_codes_section=error_codes_md,
            examples_section=examples_md,
            generation_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        with open(output_path, 'w') as f:
            f.write(md_doc)

        logger.info(f"Markdown documentation written to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate MCP API documentation")
    parser.add_argument("--output", "-o", default="docs/api_documentation.md", help="Output file path")
    parser.add_argument("--format", "-f", choices=[FORMAT_MARKDOWN, FORMAT_JSON, FORMAT_HTML], default=FORMAT_MARKDOWN,
                        help="Output format")

    args = parser.parse_args()

    generate_documentation(args.output, args.format)
