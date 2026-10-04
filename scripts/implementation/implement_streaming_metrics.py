#!/usr/bin/env python3
"""
Implementation script for streaming metrics integration.

This script reads the high_level_api.py file, applies the patches from 
streaming_metrics_patch.py, and writes the updated content to a new file.
"""

import os
import re
import sys
import time
from typing import Dict, List, Tuple, Optional

# File paths
HIGH_LEVEL_API_PATH = "ipfs_kit_py/high_level_api.py"
OUTPUT_PATH = "ipfs_kit_py/high_level_api_updated.py"
BACKUP_PATH = f"ipfs_kit_py/high_level_api_{int(time.time())}.py.bak"


def find_method_lines(content: str, method_name: str) -> Tuple[Optional[int], Optional[int]]:
    """Find the start and end line numbers of a method in the content."""
    pattern = rf'def {method_name}\s*\('
    method_matches = re.finditer(pattern, content)
    
    for match in method_matches:
        method_start = match.start()
        
        # Find the opening of method body (first docstring or indented code)
        if '"""' in content[method_start:method_start + 500]:
            # If there's a docstring, find its start
            docstring_start = content.find('"""', method_start)
            if docstring_start > 0:
                # Find the end of the docstring
                docstring_end = content.find('"""', docstring_start + 3)
                if docstring_end > 0:
                    docstring_end += 3  # Include the closing quotes
                    method_body_start = content.find('\n', docstring_end) + 1
                else:
                    # If docstring not closed properly, skip this match
                    continue
        else:
            # If no docstring, find the first indented line
            method_body_start = content.find('\n', method_start) + 1
            while content[method_body_start].isspace():
                method_body_start += 1
        
        # Find where the method ends (first unindented line after method body)
        line_start = method_body_start
        indent_level = None
        
        while line_start < len(content):
            line_end = content.find('\n', line_start)
            if line_end < 0:
                line_end = len(content)
                
            line = content[line_start:line_end]
            
            # Skip empty lines and comments
            if not line.strip() or line.strip().startswith('#'):
                line_start = line_end + 1
                continue
                
            # Determine indentation level if not yet known
            if indent_level is None:
                indent_level = len(line) - len(line.lstrip())
                
            # Check if this line has less indentation than the method body
            current_indent = len(line) - len(line.lstrip())
            if current_indent < indent_level and line.lstrip():
                method_end = line_start
                return method_start, method_end
                
            line_start = line_end + 1
        
        # If we reached end of file
        return method_start, len(content)
    
    return None, None


def extract_method_from_patch(patch_content: str, method_name: str) -> str:
    """Extract a method implementation from the patch content."""
    # Find the method in the patch file
    pattern = rf'def {method_name}\s*\('
    match = re.search(pattern, patch_content)
    if not match:
        return ""
        
    method_start = match.start()
    
    # Find the end of the method definition
    start_quotes = patch_content.rfind('"""', 0, method_start)
    if start_quotes >= 0:
        end_quotes = patch_content.find('"""', method_start)
        if end_quotes > 0:
            end_quotes += 3  # Include the closing quotes
            return patch_content[start_quotes + 3:end_quotes]
    
    return ""

def get_method_definitions(patch_content: str) -> Dict[str, str]:
    """Extract all method definitions from the patch file."""
    methods = {}
    
    # Look for method patterns between triple quotes
    pattern = r'"""(def\s+(\w+)\s*\([^)]*\).*?)"""'
    matches = re.finditer(pattern, patch_content, re.DOTALL)
    
    for match in matches:
        method_body = match.group(1)
        method_name = match.group(2)
        methods[method_name] = method_body
        
    return methods

def apply_metrics_patches():
    """Apply the streaming metrics patches to high_level_api.py."""
    # Backup the original file
    with open(HIGH_LEVEL_API_PATH, 'r') as f:
        original_content = f.read()
        
    with open(BACKUP_PATH, 'w') as f:
        f.write(original_content)
        
    # Load the patch file
    with open('streaming_metrics_patch.py', 'r') as f:
        patch_content = f.read()
        
    # Extract method implementations from patch
    method_patches = get_method_definitions(patch_content)
    
    # Update the content
    updated_content = original_content
    
    # Add metrics initialization to __init__
    init_patch = extract_method_from_patch(patch_content, "__init__")
    if init_patch:
        init_start, init_end = find_method_lines(updated_content, "__init__")
        if init_start is not None and init_end is not None:
            # Find the end of the initialization code
            init_body_end = updated_content.find("# Ensure ipfs_add_file method is available", init_start, init_end)
            if init_body_end > 0:
                # Insert metrics initialization before the ipfs_add_file method check
                metrics_init = """
        # Initialize metrics tracking
        self.enable_metrics = kwargs.get("enable_metrics", True)
        if self.enable_metrics:
            from ipfs_kit_py.performance_metrics import PerformanceMetrics
            self.metrics = PerformanceMetrics()
        else:
            self.metrics = None
"""
                updated_content = (
                    updated_content[:init_body_end] + 
                    metrics_init + 
                    updated_content[init_body_end:]
                )
    
    # Add track_streaming_operation method
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
    
    # Find a good location to insert the track_streaming_operation method
    # Let's add it after the cat method
    cat_start, cat_end = find_method_lines(updated_content, "cat")
    if cat_start is not None and cat_end is not None:
        updated_content = updated_content[:cat_end] + track_method + updated_content[cat_end:]
    
    # Update the streaming methods
    streaming_methods = [
        "stream_media",
        "stream_media_async",
        "handle_websocket_media_stream",
        "handle_websocket_upload_stream",
        "handle_websocket_bidirectional_stream",
        "stream_to_ipfs"
    ]
    
    for method_name in streaming_methods:
        method_start, method_end = find_method_lines(updated_content, method_name)
        if method_start is not None and method_end is not None:
            # Extract the method docstring
            docstring_start = updated_content.find('"""', method_start)
            docstring_end = updated_content.find('"""', docstring_start + 3) + 3
            docstring = updated_content[docstring_start:docstring_end]
            
            # Get the method parameters from original method
            def_line_end = updated_content.find(':', method_start)
            def_line = updated_content[method_start:def_line_end+1]
            
            # Create the updated method implementation
            # This is a simplification - in a real implementation, you'd need
            # to analyze the current code and merge in the metrics tracking
            if method_name == "stream_media":
                updated_method = def_line + docstring + """
        # Start tracking metrics
        start_time = time.time()
        total_bytes = 0
        chunk_count = 0
        
        try:
            # Get content
            content = self.cat(path, **kwargs)
            
            if content is None:
                return
                
            # Apply range if specified
            if start_byte is not None or end_byte is not None:
                start = start_byte or 0
                end = end_byte or len(content)
                content = content[start:end]
                
            # Stream content in chunks
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i+chunk_size]
                total_bytes += len(chunk)
                chunk_count += 1
                yield chunk
                
        finally:
            # Track streaming metrics when completed
            duration = time.time() - start_time
            if self.enable_metrics and hasattr(self, 'metrics') and self.metrics:
                self.track_streaming_operation(
                    stream_type="http",
                    direction="outbound",
                    size_bytes=total_bytes,
                    duration_seconds=duration,
                    path=path,
                    chunk_count=chunk_count,
                    chunk_size=chunk_size
                )
"""
                # Replace the current method implementation
                updated_content = updated_content[:method_start] + updated_method + updated_content[method_end:]
    
    # Write the updated content to a new file
    with open(OUTPUT_PATH, 'w') as f:
        f.write(updated_content)
        
    print(f"Updated high_level_api.py with streaming metrics integration")
    print(f"Original file backed up to {BACKUP_PATH}")
    print(f"Updated file written to {OUTPUT_PATH}")
    print()
    print("To apply the changes, run:")
    print(f"  cp {OUTPUT_PATH} {HIGH_LEVEL_API_PATH}")

if __name__ == "__main__":
    apply_metrics_patches()