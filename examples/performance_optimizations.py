#!/usr/bin/env python
"""
Performance optimization implementation for ipfs_kit_py.

This script implements optimizations identified by the performance_profiling.py
tool. It includes improvements for caching, high-level API overhead reduction,
and chunked upload implementations.
"""

import os
import sys
import json
import time
import functools
from pathlib import Path

# Add parent directory to path to import ipfs_kit_py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from ipfs_kit_py import ipfs_kit
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
except ImportError as e:
    print(f"Error importing ipfs_kit_py: {e}")
    sys.exit(1)


class PerformanceOptimizer:
    """Implements performance optimizations for ipfs_kit_py."""
    
    def __init__(self, profile_results_path=None):
        """Initialize with optional profiling results.
        
        Args:
            profile_results_path: Path to profiling results JSON file
        """
        self.profile_results = None
        if profile_results_path and os.path.exists(profile_results_path):
            with open(profile_results_path, 'r') as f:
                self.profile_results = json.load(f)
        
        # Initialize IPFS Kit
        self.kit = ipfs_kit()
        
        # Paths to modify
        self.high_level_api_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'ipfs_kit_py', 'high_level_api.py'
        )
        self.ipfs_fsspec_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'ipfs_kit_py', 'ipfs_fsspec.py'
        )
        self.ipfs_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'ipfs_kit_py', 'ipfs.py'
        )
        
        # Check if files exist
        if not os.path.exists(self.high_level_api_path):
            print(f"Warning: high_level_api.py not found at {self.high_level_api_path}")
        if not os.path.exists(self.ipfs_fsspec_path):
            print(f"Warning: ipfs_fsspec.py not found at {self.ipfs_fsspec_path}")
        if not os.path.exists(self.ipfs_py_path):
            print(f"Warning: ipfs.py not found at {self.ipfs_py_path}")
    
    def analyze_profiling_results(self):
        """Analyze profiling results and identify optimization opportunities."""
        if not self.profile_results:
            print("No profiling results available. Skipping analysis.")
            return None
        
        optimizations = {
            "high_level_api": {
                "needed": False,
                "reason": None,
                "overhead": 0
            },
            "cache": {
                "needed": False,
                "reason": None,
                "hit_rate": 0
            },
            "chunked_upload": {
                "needed": False,
                "reason": None,
                "threshold_size": 0
            }
        }
        
        # Check for high-level API overhead
        if "tests" in self.profile_results and "api_operations" in self.profile_results["tests"]:
            api_results = self.profile_results["tests"]["api_operations"]
            
            for op_name in ["node_id", "version"]:
                if op_name in api_results:
                    op_results = api_results[op_name]
                    low_level_times = [r["low_level_api"]["elapsed"] for r in op_results 
                                      if r["low_level_api"]["success"]]
                    high_level_times = [r["high_level_api"]["elapsed"] for r in op_results 
                                       if r["high_level_api"]["success"]]
                    
                    if low_level_times and high_level_times:
                        import numpy as np
                        overhead = (np.mean(high_level_times) - np.mean(low_level_times)) / np.mean(low_level_times) * 100
                        
                        if overhead > 50 and overhead > optimizations["high_level_api"]["overhead"]:
                            optimizations["high_level_api"]["needed"] = True
                            optimizations["high_level_api"]["reason"] = f"{op_name} operation has {overhead:.1f}% overhead"
                            optimizations["high_level_api"]["overhead"] = overhead
        
        # Check for cache optimization needs
        if "tests" in self.profile_results and "tiered_cache" in self.profile_results["tests"]:
            cache_results = self.profile_results["tests"]["tiered_cache"]
            
            if cache_results and "repeated_access" in cache_results:
                rep_results = cache_results["repeated_access"]
                if rep_results and "stats" in rep_results[-1]:
                    last_stats = rep_results[-1]["stats"]
                    if "memory_hits" in last_stats and "disk_hits" in last_stats and "misses" in last_stats:
                        total = last_stats["memory_hits"] + last_stats["disk_hits"] + last_stats["misses"]
                        if total > 0:
                            memory_hit_rate = last_stats["memory_hits"] / total * 100
                            if memory_hit_rate < 70:  # Less than 70% memory hit rate for repeated access
                                optimizations["cache"]["needed"] = True
                                optimizations["cache"]["reason"] = f"Memory hit rate is only {memory_hit_rate:.1f}%"
                                optimizations["cache"]["hit_rate"] = memory_hit_rate
        
        # Check for chunked upload needs
        if "tests" in self.profile_results and "add_operation" in self.profile_results["tests"]:
            add_results = self.profile_results["tests"]["add_operation"]
            
            slow_size = None
            for size, size_results in add_results.items():
                import numpy as np
                low_level_times = [r["low_level_api"]["elapsed"] for r in size_results 
                                  if r["low_level_api"]["success"]]
                
                if low_level_times and int(size) > 100000 and np.mean(low_level_times) > 1.0:
                    # Large files taking >1s
                    slow_size = int(size)
                    break
            
            if slow_size:
                optimizations["chunked_upload"]["needed"] = True
                optimizations["chunked_upload"]["reason"] = f"Files > {slow_size} bytes take >1s to upload"
                optimizations["chunked_upload"]["threshold_size"] = slow_size
        
        return optimizations
    
    def optimize_high_level_api(self):
        """Optimize high-level API to reduce overhead."""
        print("\nOptimizing high-level API...")
        
        if not os.path.exists(self.high_level_api_path):
            print("Error: high_level_api.py not found")
            return False
        
        with open(self.high_level_api_path, 'r') as f:
            original_code = f.read()
        
        # Modifications to make:
        # 1. Add caching decorator for frequent methods
        # 2. Optimize error handling paths
        
        modified_code = original_code
        
        # Check if caching imports are already present
        if "import functools" not in modified_code:
            import_section_end = modified_code.find("import ")
            import_section_end = modified_code.find("\n", import_section_end)
            modified_code = modified_code[:import_section_end + 1] + "import functools\n" + modified_code[import_section_end + 1:]
        
        # Add caching decorator if not already present
        if "def cache_result" not in modified_code:
            class_definition = modified_code.find("class IPFSSimpleAPI")
            insert_point = modified_code.find("\n", class_definition)
            
            cache_decorator = """
    # Performance optimization: Cache method results
    def cache_result(func):
        """Caching decorator for frequently used methods."""
        cache = {}
        
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Create a key based on function name and arguments
            key = (func.__name__, args, frozenset(kwargs.items()))
            
            # Check if result is in cache
            if key in cache:
                return cache[key]
            
            # Call the original function
            result = func(self, *args, **kwargs)
            
            # Cache the result
            cache[key] = result
            
            # Limit cache size to 100 items (LRU could be implemented for more sophistication)
            if len(cache) > 100:
                # Simple approach: clear the whole cache when it gets too big
                # A more sophisticated approach would use LRU eviction
                oldest_key = next(iter(cache))
                del cache[oldest_key]
                
            return result
        
        return wrapper
"""
            modified_code = modified_code[:insert_point + 1] + cache_decorator + modified_code[insert_point + 1:]
        
        # Add caching to frequently used methods
        methods_to_cache = ["get_node_id", "get_version"]
        for method in methods_to_cache:
            method_def = f"def {method}("
            if method_def in modified_code and f"@cache_result\n    def {method}(" not in modified_code:
                method_point = modified_code.find(method_def)
                indent_point = modified_code.rfind("\n", 0, method_point)
                modified_code = (modified_code[:indent_point + 1] + 
                                "    @cache_result\n" + 
                                modified_code[indent_point + 1:])
        
        # Optimize validation in methods by simplifying error handling
        # This is more complex and would need careful inspection of each method
        # For now, we'll focus on adding the caching mechanism
        
        # Save the modified code
        with open(self.high_level_api_path, 'w') as f:
            f.write(modified_code)
        
        print("Added result caching to high-level API methods")
        return True
    
    def optimize_cache_configuration(self):
        """Optimize cache configuration in ipfs_fsspec.py."""
        print("\nOptimizing cache configuration...")
        
        if not os.path.exists(self.ipfs_fsspec_path):
            print("Error: ipfs_fsspec.py not found")
            return False
        
        with open(self.ipfs_fsspec_path, 'r') as f:
            original_code = f.read()
        
        modified_code = original_code
        
        # Find default cache configuration
        default_config_pattern = "self.config = config or {"
        default_config_pos = modified_code.find(default_config_pattern)
        
        if default_config_pos >= 0:
            # Increase memory cache size (looking for 'memory_cache_size': line)
            memory_size_pattern = "'memory_cache_size':"
            memory_size_pos = modified_code.find(memory_size_pattern, default_config_pos)
            
            if memory_size_pos >= 0:
                # Find the end of the line
                line_end = modified_code.find(",", memory_size_pos)
                if line_end >= 0:
                    # Extract current value
                    current_value = modified_code[memory_size_pos + len(memory_size_pattern):line_end].strip()
                    
                    # Parse the value (could be something like 100 * 1024 * 1024)
                    # For safety, we'll just double whatever is there
                    new_value = f"2 * ({current_value})"
                    
                    # Replace with new value
                    modified_code = (modified_code[:memory_size_pos + len(memory_size_pattern)] + 
                                    f" {new_value}" + 
                                    modified_code[line_end:])
                    
                    print(f"Increased memory cache size from {current_value} to {new_value}")
        
        # Optimize ARC algorithm parameters if present
        arc_class_pattern = "class ARCache"
        arc_class_pos = modified_code.find(arc_class_pattern)
        
        if arc_class_pos >= 0:
            # Find the target parameter in __init__ if it exists
            target_pattern = "self.target ="
            target_pos = modified_code.find(target_pattern, arc_class_pos)
            
            if target_pos >= 0:
                # Find the end of the line
                line_end = modified_code.find("\n", target_pos)
                if line_end >= 0:
                    # Adjust target parameter to be more aggressive in keeping items
                    modified_code = (modified_code[:target_pos] + 
                                    "self.target = 0.8  # Increased from 0.5 for better hit rates" + 
                                    modified_code[line_end:])
                    
                    print("Optimized ARC algorithm parameters for better hit rates")
        
        # Save the modified code
        with open(self.ipfs_fsspec_path, 'w') as f:
            f.write(modified_code)
        
        return True
    
    def implement_chunked_upload(self):
        """Implement chunked upload for large files."""
        print("\nImplementing chunked upload for large files...")
        
        if not os.path.exists(self.ipfs_py_path):
            print("Error: ipfs.py not found")
            return False
        
        with open(self.ipfs_py_path, 'r') as f:
            original_code = f.read()
        
        modified_code = original_code
        
        # Add imports if needed
        if "import tempfile" not in modified_code:
            import_section_end = modified_code.find("import ")
            import_section_end = modified_code.find("\n", import_section_end)
            modified_code = modified_code[:import_section_end + 1] + "import tempfile\n" + modified_code[import_section_end + 1:]
        
        # Check if chunked upload method already exists
        if "def ipfs_add_chunked" not in modified_code:
            # Find a good place to insert the new method - after ipfs_add function
            ipfs_add_pos = modified_code.find("def ipfs_add(")
            if ipfs_add_pos < 0:
                print("Could not find ipfs_add function to add chunked version")
                return False
            
            # Find the end of the ipfs_add function
            next_def_pos = modified_code.find("def ", ipfs_add_pos + 1)
            if next_def_pos < 0:
                next_def_pos = len(modified_code)
            
            # Create the chunked upload function
            chunked_upload_method = """
    def ipfs_add_chunked(self, content=None, chunk_size=1024*1024, resources=None, metadata=None):
        """Add content to IPFS using chunked uploading for better performance with large files.
        
        Args:
            content: Binary content to add to IPFS
            chunk_size: Size of chunks in bytes (default: 1MB)
            resources: Dictionary containing request-specific resource limits
            metadata: Additional metadata for the operation
            
        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "ipfs_add_chunked",
            "timestamp": time.time()
        }
        
        if metadata is None:
            metadata = {}
        
        if content is None:
            result["error"] = "No content provided"
            result["error_type"] = "validation_error"
            return result
            
        try:
            # Create a temporary directory for chunks
            with tempfile.TemporaryDirectory() as temp_dir:
                chunk_files = []
                
                # Split content into chunks
                total_chunks = (len(content) + chunk_size - 1) // chunk_size
                
                for i in range(total_chunks):
                    chunk = content[i * chunk_size:min((i + 1) * chunk_size, len(content))]
                    chunk_path = os.path.join(temp_dir, f"chunk_{i:05d}")
                    
                    with open(chunk_path, 'wb') as f:
                        f.write(chunk)
                    
                    chunk_files.append(chunk_path)
                
                # Add each chunk to IPFS
                chunk_cids = []
                for chunk_path in chunk_files:
                    chunk_result = self.ipfs_add_file(chunk_path, resources=resources, metadata=metadata)
                    if not chunk_result.get("success", False):
                        result["error"] = f"Failed to add chunk: {chunk_result.get('error', 'Unknown error')}"
                        result["error_type"] = "chunk_add_error"
                        return result
                    
                    chunk_cids.append(chunk_result["Hash"])
                
                # Create a file with the list of chunk CIDs
                links_path = os.path.join(temp_dir, "links.txt")
                with open(links_path, 'w') as f:
                    for cid in chunk_cids:
                        f.write(f"{cid}\\n")
                
                # Add the links file to IPFS
                links_result = self.ipfs_add_file(links_path, resources=resources, metadata=metadata)
                if not links_result.get("success", False):
                    result["error"] = f"Failed to add links file: {links_result.get('error', 'Unknown error')}"
                    result["error_type"] = "links_add_error"
                    return result
                
                # Success - return the CID of the links file
                result["success"] = True
                result["Hash"] = links_result["Hash"]
                result["Size"] = len(content)
                result["chunks"] = len(chunk_cids)
                result["chunk_cids"] = chunk_cids
                
        except Exception as e:
            result["error"] = f"Chunked upload failed: {str(e)}"
            result["error_type"] = "chunked_upload_error"
            
        return result
        
    def ipfs_cat_chunked(self, cid, resources=None, metadata=None):
        """Retrieve chunked content from IPFS.
        
        Args:
            cid: Content ID of the links file
            resources: Dictionary containing request-specific resource limits
            metadata: Additional metadata for the operation
            
        Returns:
            Dictionary with operation result containing the reassembled content
        """
        result = {
            "success": False,
            "operation": "ipfs_cat_chunked",
            "timestamp": time.time()
        }
        
        if metadata is None:
            metadata = {}
        
        try:
            # Get the links file
            links_result = self.ipfs_cat(cid, resources=resources, metadata=metadata)
            if not isinstance(links_result, bytes):
                result["error"] = "Failed to retrieve links file"
                result["error_type"] = "links_retrieve_error"
                return result
            
            # Parse the links file to get the chunk CIDs
            chunk_cids = links_result.decode('utf-8').strip().split('\\n')
            
            # Retrieve each chunk
            chunks = []
            for chunk_cid in chunk_cids:
                chunk_result = self.ipfs_cat(chunk_cid, resources=resources, metadata=metadata)
                if not isinstance(chunk_result, bytes):
                    result["error"] = f"Failed to retrieve chunk {chunk_cid}"
                    result["error_type"] = "chunk_retrieve_error"
                    return result
                
                chunks.append(chunk_result)
            
            # Reassemble the content
            content = b''.join(chunks)
            
            # Success
            result["success"] = True
            result["content"] = content
            result["size"] = len(content)
            result["chunks"] = len(chunks)
            
            return content
            
        except Exception as e:
            result["error"] = f"Chunked retrieval failed: {str(e)}"
            result["error_type"] = "chunked_retrieval_error"
            
        return result
"""
            
            modified_code = modified_code[:next_def_pos] + chunked_upload_method + modified_code[next_def_pos:]
            
            print("Added chunked upload implementation for large files")
        else:
            print("Chunked upload implementation already exists")
        
        # Modify ipfs_add method to use chunked upload for large files
        ipfs_add_pos = modified_code.find("def ipfs_add(")
        if ipfs_add_pos >= 0:
            # Find function body
            function_body_start = modified_code.find(":", ipfs_add_pos)
            function_body_start = modified_code.find("\n", function_body_start)
            
            # Determine indentation level
            indentation = ""
            for char in modified_code[function_body_start + 1:]:
                if char.isspace():
                    indentation += char
                else:
                    break
            
            # Find a good place to insert the size check - after input validation, before subprocess call
            result_init_pattern = "result = {"
            result_init_pos = modified_code.find(result_init_pattern, function_body_start)
            
            if result_init_pos >= 0:
                # Find the end of result initialization
                result_init_end = modified_code.find("}", result_init_pos)
                result_init_end = modified_code.find("\n", result_init_end)
                
                # Insert size check and redirection to chunked method
                threshold_size = 1024 * 1024  # 1MB default threshold
                if self.profile_results and "chunked_upload" in self.analyze_profiling_results():
                    opts = self.analyze_profiling_results()["chunked_upload"]
                    if opts["needed"] and opts["threshold_size"] > 0:
                        threshold_size = opts["threshold_size"]
                
                chunked_redirect = f"""
{indentation}# Performance optimization: Use chunked upload for large files
{indentation}if content and len(content) > {threshold_size}:
{indentation}    return self.ipfs_add_chunked(content=content, resources=resources, metadata=metadata)
"""
                
                modified_code = (modified_code[:result_init_end + 1] + 
                                chunked_redirect + 
                                modified_code[result_init_end + 1:])
                
                print(f"Added automatic redirection to chunked upload for files > {threshold_size} bytes")
        
        # Save the modified code
        with open(self.ipfs_py_path, 'w') as f:
            f.write(modified_code)
        
        return True
    
    def apply_all_optimizations(self):
        """Apply all performance optimizations."""
        print("\n===== Applying Performance Optimizations =====")
        
        # Analyze profiling results if available
        optimizations = self.analyze_profiling_results()
        if optimizations:
            print("\nOptimization opportunities identified:")
            for category, details in optimizations.items():
                if details["needed"]:
                    print(f"- {category}: {details['reason']}")
        
        # Apply optimizations
        high_level_result = self.optimize_high_level_api()
        cache_result = self.optimize_cache_configuration()
        chunked_result = self.implement_chunked_upload()
        
        success_count = sum([high_level_result, cache_result, chunked_result])
        print(f"\n{success_count} optimizations applied successfully")
        
        print("\n===== Performance Optimization Complete =====")
        print("Run the performance profiling tool again to measure improvements")


def main():
    """Main entry point for the optimization script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Apply performance optimizations to ipfs_kit_py")
    parser.add_argument(
        "--profile-results", 
        help="Path to profiling results JSON file"
    )
    
    args = parser.parse_args()
    
    optimizer = PerformanceOptimizer(profile_results_path=args.profile_results)
    optimizer.apply_all_optimizations()


if __name__ == "__main__":
    main()