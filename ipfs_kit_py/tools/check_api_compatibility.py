#!/usr/bin/env python3
"""
Check API compatibility between IPFS Kit versions.

This tool compares the current API with a previous version to detect potential
breaking changes and compatibility issues. It analyzes method signatures, 
return types, and parameter changes to identify changes that might affect users.

Usage:
    python -m ipfs_kit_py.tools.check_api_compatibility --previous=0.1.0 --current=HEAD
    python -m ipfs_kit_py.tools.check_api_compatibility --generate-report
"""

import argparse
import importlib
import inspect
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

# Try to import api_stability module
try:
    from ipfs_kit_py.api_stability import (
        API_REGISTRY, APIStability, get_api_registry, get_stability_metrics
    )
except ImportError:
    print("Error: Could not import api_stability module.")
    print("Please run this tool from the project root with:")
    print("  python -m ipfs_kit_py.tools.check_api_compatibility")
    sys.exit(1)


def get_methods_from_module(module_name: str) -> Dict[str, Dict[str, Any]]:
    """
    Extract methods from a module with their signatures.
    
    Args:
        module_name: Name of the module to analyze
        
    Returns:
        Dictionary mapping method names to their metadata
    """
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        print(f"Error: Could not import module {module_name}")
        return {}
    
    methods = {}
    
    # Get all public methods/functions (no leading underscore)
    for name, obj in inspect.getmembers(module):
        if name.startswith('_'):
            continue
            
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            # Extract metadata
            signature = inspect.signature(obj)
            stability = getattr(obj, "__api_stability__", None)
            since = getattr(obj, "__api_since__", None)
            
            methods[name] = {
                "signature": str(signature),
                "parameters": {
                    param_name: {
                        "kind": str(param.kind),
                        "default": "" if param.default is inspect.Parameter.empty else str(param.default),
                        "annotation": "" if param.annotation is inspect.Parameter.empty else str(param.annotation),
                    }
                    for param_name, param in signature.parameters.items()
                },
                "return_annotation": "" if signature.return_annotation is inspect.Parameter.empty 
                                     else str(signature.return_annotation),
                "stability": str(stability.value) if stability else "unknown",
                "since": since,
                "doc": inspect.getdoc(obj),
            }
        elif inspect.isclass(obj):
            # Get class methods
            for method_name, method_obj in inspect.getmembers(obj):
                if method_name.startswith('_'):
                    continue
                    
                if inspect.isfunction(method_obj) or inspect.ismethod(method_obj):
                    # Extract metadata
                    signature = inspect.signature(method_obj)
                    stability = getattr(method_obj, "__api_stability__", None)
                    since = getattr(method_obj, "__api_since__", None)
                    
                    full_name = f"{name}.{method_name}"
                    methods[full_name] = {
                        "signature": str(signature),
                        "parameters": {
                            param_name: {
                                "kind": str(param.kind),
                                "default": "" if param.default is inspect.Parameter.empty else str(param.default),
                                "annotation": "" if param.annotation is inspect.Parameter.empty else str(param.annotation),
                            }
                            for param_name, param in signature.parameters.items()
                        },
                        "return_annotation": "" if signature.return_annotation is inspect.Parameter.empty 
                                           else str(signature.return_annotation),
                        "stability": str(stability.value) if stability else "unknown",
                        "since": since,
                        "doc": inspect.getdoc(method_obj),
                    }
    
    return methods


def get_all_modules() -> List[str]:
    """
    Get all IPFS Kit modules.
    
    Returns:
        List of module names
    """
    modules = []
    
    # Start with base package
    modules.append("ipfs_kit_py")
    
    # Add core modules
    base_modules = [
        "ipfs_kit_py.ipfs_kit",
        "ipfs_kit_py.high_level_api",
        "ipfs_kit_py.api",
        "ipfs_kit_py.ipfs_fsspec",
        "ipfs_kit_py.tiered_cache",
    ]
    modules.extend(base_modules)
    
    # Add additional modules based on file listing
    kit_dir = Path(__file__).parent.parent  # ipfs_kit_py directory
    for file_path in kit_dir.glob("*.py"):
        if file_path.stem not in ["__init__", "__main__"]:
            module_name = f"ipfs_kit_py.{file_path.stem}"
            if module_name not in modules:
                modules.append(module_name)
    
    return modules


def extract_current_api() -> Dict[str, Dict[str, Any]]:
    """
    Extract API information from the current codebase.
    
    Returns:
        Dictionary mapping module names to their method metadata
    """
    modules = get_all_modules()
    api_info = {}
    
    for module_name in modules:
        methods = get_methods_from_module(module_name)
        if methods:
            api_info[module_name] = methods
    
    return api_info


def checkout_version(version: str) -> bool:
    """
    Checkout a specific version using git.
    
    Args:
        version: Version tag or commit hash to checkout
        
    Returns:
        True if checkout was successful, False otherwise
    """
    current_branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        universal_newlines=True
    ).strip()
    
    try:
        # Stash any changes
        subprocess.check_call(["git", "stash", "-u"], stdout=subprocess.DEVNULL)
        
        # Checkout version
        subprocess.check_call(
            ["git", "checkout", version],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        print(f"Error: Failed to checkout version {version}")
        return False
    finally:
        # Restore original branch
        subprocess.check_call(
            ["git", "checkout", current_branch],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Pop stashed changes
        try:
            subprocess.check_call(
                ["git", "stash", "pop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            # No stash to pop
            pass


def extract_api_from_version(version: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Extract API information from a specific version.
    
    Args:
        version: Version tag or commit hash
        
    Returns:
        Dictionary mapping module names to their method metadata, or None if extraction failed
    """
    # Save current API info
    current_api = extract_current_api()
    
    # Checkout version
    if not checkout_version(version):
        return None
    
    try:
        # Extract API from checked-out version
        version_api = extract_current_api()
        return version_api
    except Exception as e:
        print(f"Error extracting API from version {version}: {e}")
        return None
    finally:
        # Restore current API
        checkout_version("HEAD")


def compare_apis(previous_api: Dict[str, Dict[str, Any]], 
                current_api: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare two API versions to detect breaking changes.
    
    Args:
        previous_api: API information from previous version
        current_api: API information from current version
        
    Returns:
        Dictionary with compatibility analysis results
    """
    result = {
        "breaking_changes": [],
        "new_methods": [],
        "removed_methods": [],
        "changed_methods": [],
        "deprecated_methods": [],
        "signature_changes": [],
    }
    
    # Find all methods in both APIs
    previous_methods = set()
    current_methods = set()
    
    for module, methods in previous_api.items():
        for method in methods:
            previous_methods.add(f"{module}.{method}")
            
    for module, methods in current_api.items():
        for method in methods:
            current_methods.add(f"{module}.{method}")
    
    # Find new and removed methods
    result["new_methods"] = sorted(list(current_methods - previous_methods))
    result["removed_methods"] = sorted(list(previous_methods - current_methods))
    
    # Check for breaking changes in removed methods
    for method in result["removed_methods"]:
        module, method_name = method.rsplit(".", 1)
        
        if module in previous_api and method_name in previous_api[module]:
            method_info = previous_api[module][method_name]
            
            # Only consider stable APIs as breaking changes when removed
            if method_info.get("stability") == "stable":
                result["breaking_changes"].append({
                    "type": "method_removed",
                    "method": method,
                    "stability": method_info.get("stability", "unknown"),
                    "since": method_info.get("since"),
                })
    
    # Check for signature changes in common methods
    common_methods = sorted(list(previous_methods.intersection(current_methods)))
    
    for method in common_methods:
        module, method_name = method.rsplit(".", 1)
        
        if (module in previous_api and method_name in previous_api[module] and
            module in current_api and method_name in current_api[module]):
            
            prev_info = previous_api[module][method_name]
            curr_info = current_api[module][method_name]
            
            # Check if method is now deprecated
            if (prev_info.get("stability") != "deprecated" and 
                curr_info.get("stability") == "deprecated"):
                result["deprecated_methods"].append({
                    "method": method,
                    "previous_stability": prev_info.get("stability", "unknown"),
                    "since": curr_info.get("since"),
                })
            
            # Check for signature changes
            if prev_info["signature"] != curr_info["signature"]:
                result["signature_changes"].append({
                    "method": method,
                    "previous_signature": prev_info["signature"],
                    "current_signature": curr_info["signature"],
                    "stability": curr_info.get("stability", "unknown"),
                })
                
                # Analyze parameter changes
                prev_params = prev_info["parameters"]
                curr_params = curr_info["parameters"]
                
                # Check for removed parameters
                removed_params = set(prev_params.keys()) - set(curr_params.keys())
                if removed_params:
                    # Check if all removed params had defaults (not breaking)
                    breaking_removals = []
                    for param in removed_params:
                        if prev_params[param]["default"] == "":  # No default
                            breaking_removals.append(param)
                    
                    if breaking_removals and curr_info.get("stability") == "stable":
                        result["breaking_changes"].append({
                            "type": "required_params_removed",
                            "method": method,
                            "removed_params": list(breaking_removals),
                            "stability": curr_info.get("stability", "unknown"),
                        })
                
                # Check for added required parameters (breaking change)
                added_params = set(curr_params.keys()) - set(prev_params.keys())
                breaking_additions = []
                for param in added_params:
                    if curr_params[param]["default"] == "":  # No default
                        breaking_additions.append(param)
                
                if breaking_additions and curr_info.get("stability") == "stable":
                    result["breaking_changes"].append({
                        "type": "required_params_added",
                        "method": method,
                        "added_params": breaking_additions,
                        "stability": curr_info.get("stability", "unknown"),
                    })
                
                # Check for changed parameter defaults or types
                common_params = set(prev_params.keys()).intersection(set(curr_params.keys()))
                for param in common_params:
                    # Check if default changed
                    if prev_params[param]["default"] != curr_params[param]["default"]:
                        result["changed_methods"].append({
                            "method": method,
                            "change_type": "default_changed",
                            "param": param,
                            "previous_default": prev_params[param]["default"],
                            "current_default": curr_params[param]["default"],
                            "stability": curr_info.get("stability", "unknown"),
                        })
                    
                    # Check if type annotation changed
                    if prev_params[param]["annotation"] != curr_params[param]["annotation"]:
                        result["changed_methods"].append({
                            "method": method,
                            "change_type": "type_changed",
                            "param": param,
                            "previous_type": prev_params[param]["annotation"],
                            "current_type": curr_params[param]["annotation"],
                            "stability": curr_info.get("stability", "unknown"),
                        })
                
                # Check if return type changed
                if prev_info["return_annotation"] != curr_info["return_annotation"]:
                    result["changed_methods"].append({
                        "method": method,
                        "change_type": "return_type_changed",
                        "previous_type": prev_info["return_annotation"],
                        "current_type": curr_info["return_annotation"],
                        "stability": curr_info.get("stability", "unknown"),
                    })
    
    # Summarize results
    result["summary"] = {
        "new_methods_count": len(result["new_methods"]),
        "removed_methods_count": len(result["removed_methods"]),
        "changed_methods_count": len(result["changed_methods"]),
        "deprecated_methods_count": len(result["deprecated_methods"]),
        "breaking_changes_count": len(result["breaking_changes"]),
    }
    
    return result


def generate_compatibility_report(comparison: Dict[str, Any]) -> str:
    """
    Generate a markdown compatibility report.
    
    Args:
        comparison: Comparison results from compare_apis
        
    Returns:
        Markdown-formatted report
    """
    summary = comparison["summary"]
    
    md = ["# IPFS Kit API Compatibility Report\n"]
    
    # Summary section
    md.append("## Summary\n")
    md.append(f"- New methods: {summary['new_methods_count']}")
    md.append(f"- Removed methods: {summary['removed_methods_count']}")
    md.append(f"- Changed methods: {summary['changed_methods_count']}")
    md.append(f"- Deprecated methods: {summary['deprecated_methods_count']}")
    md.append(f"- Breaking changes: {summary['breaking_changes_count']}")
    md.append("")
    
    # Breaking changes
    if comparison["breaking_changes"]:
        md.append("## Breaking Changes\n")
        md.append("The following changes may break existing code:\n")
        
        for change in comparison["breaking_changes"]:
            md.append(f"### {change['method']}\n")
            
            if change["type"] == "method_removed":
                md.append(f"**REMOVED**: This method has been removed from the API.\n")
                md.append(f"- Stability: {change['stability']}")
                md.append(f"- Since: {change['since']}")
            
            elif change["type"] == "required_params_added":
                md.append(f"**REQUIRED PARAMETERS ADDED**: New required parameters will break existing calls.\n")
                md.append(f"- Added required parameters: {', '.join(change['added_params'])}")
                md.append(f"- Stability: {change['stability']}")
            
            elif change["type"] == "required_params_removed":
                md.append(f"**REQUIRED PARAMETERS REMOVED**: Previously required parameters were removed.\n")
                md.append(f"- Removed required parameters: {', '.join(change['removed_params'])}")
                md.append(f"- Stability: {change['stability']}")
            
            md.append("")
    
    # Changed methods
    if comparison["changed_methods"]:
        md.append("## Changed Methods\n")
        
        # Group changes by method
        changes_by_method = {}
        for change in comparison["changed_methods"]:
            method = change["method"]
            if method not in changes_by_method:
                changes_by_method[method] = []
            changes_by_method[method].append(change)
        
        for method, changes in changes_by_method.items():
            md.append(f"### {method}\n")
            
            for change in changes:
                if change["change_type"] == "default_changed":
                    md.append(f"**DEFAULT CHANGED**: Parameter `{change['param']}` default changed")
                    md.append(f"- Previous default: `{change['previous_default']}`")
                    md.append(f"- New default: `{change['current_default']}`")
                    md.append(f"- Stability: {change['stability']}")
                
                elif change["change_type"] == "type_changed":
                    md.append(f"**TYPE CHANGED**: Parameter `{change['param']}` type changed")
                    md.append(f"- Previous type: `{change['previous_type']}`")
                    md.append(f"- New type: `{change['current_type']}`")
                    md.append(f"- Stability: {change['stability']}")
                
                elif change["change_type"] == "return_type_changed":
                    md.append(f"**RETURN TYPE CHANGED**: Method return type changed")
                    md.append(f"- Previous return type: `{change['previous_type']}`")
                    md.append(f"- New return type: `{change['current_type']}`")
                    md.append(f"- Stability: {change['stability']}")
                
                md.append("")
    
    # New methods
    if comparison["new_methods"]:
        md.append("## New Methods\n")
        md.append("The following methods have been added:\n")
        
        for method in comparison["new_methods"]:
            md.append(f"- `{method}`")
        
        md.append("")
    
    # Removed methods
    if comparison["removed_methods"]:
        md.append("## Removed Methods\n")
        md.append("The following methods have been removed:\n")
        
        for method in comparison["removed_methods"]:
            md.append(f"- `{method}`")
        
        md.append("")
    
    # Deprecated methods
    if comparison["deprecated_methods"]:
        md.append("## Deprecated Methods\n")
        md.append("The following methods have been deprecated:\n")
        
        for method in comparison["deprecated_methods"]:
            md.append(f"- `{method['method']}` (previously {method['previous_stability']}, deprecated since {method['since']})")
        
        md.append("")
    
    return "\n".join(md)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Check API compatibility between IPFS Kit versions")
    parser.add_argument("--previous", default="v0.1.0", help="Previous version to compare (tag, branch, or commit)")
    parser.add_argument("--current", default="HEAD", help="Current version to compare (tag, branch, or commit)")
    parser.add_argument("--generate-report", action="store_true", help="Generate Markdown compatibility report")
    parser.add_argument("--save-report", action="store_true", help="Save report to file")
    args = parser.parse_args()
    
    print(f"Checking API compatibility between {args.previous} and {args.current}...")
    
    # Extract API from previous version
    print(f"Extracting API from {args.previous}...")
    previous_api = extract_api_from_version(args.previous)
    
    if not previous_api:
        print(f"Error: Failed to extract API from {args.previous}")
        sys.exit(1)
    
    # Extract API from current version
    print(f"Extracting API from {args.current}...")
    current_api = extract_current_api()
    
    # Compare APIs
    print("Comparing APIs...")
    comparison = compare_apis(previous_api, current_api)
    
    # Print summary
    summary = comparison["summary"]
    print("\nAPI Compatibility Summary:")
    print(f"- New methods: {summary['new_methods_count']}")
    print(f"- Removed methods: {summary['removed_methods_count']}")
    print(f"- Changed methods: {summary['changed_methods_count']}")
    print(f"- Deprecated methods: {summary['deprecated_methods_count']}")
    print(f"- Breaking changes: {summary['breaking_changes_count']}")
    
    # Show breaking changes
    if comparison["breaking_changes"]:
        print("\nBreaking Changes:")
        for change in comparison["breaking_changes"]:
            print(f"- {change['method']} ({change['type']})")
    
    # Generate report if requested
    if args.generate_report or args.save_report:
        report = generate_compatibility_report(comparison)
        
        if args.save_report:
            report_path = f"api_compatibility_report_{args.previous}_to_{args.current}.md"
            with open(report_path, "w") as f:
                f.write(report)
            print(f"\nReport saved to {report_path}")
        else:
            print("\n" + report)
    
    # Exit with error code if breaking changes exist
    if comparison["breaking_changes"]:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()