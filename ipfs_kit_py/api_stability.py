"""
API Stability Utilities for IPFS Kit.

This module provides decorators and utilities for managing API stability
and version compatibility throughout the IPFS Kit Python codebase.

Usage:
    @stable_api(since="0.1.0")
    def stable_method(param1, param2=None):
        '''This method is stable and won't break compatibility within a major version.'''
        pass

    @beta_api(since="0.1.0")
    def beta_method(param1, param2=None):
        '''This method is nearly stable but may still change in minor versions.'''
        pass

    @experimental_api(since="0.1.0")
    def experimental_method(param1, param2=None):
        '''This method is experimental and may change at any time.'''
        pass

    @deprecated(since="0.1.0", removed_in="1.0.0", alternative="new_method")
    def old_method():
        '''This method is deprecated and will be removed in a future version.'''
        warnings.warn("Use new_method instead", DeprecationWarning, stacklevel=2)
        pass
"""

import functools
import inspect
import warnings
from enum import Enum
from typing import Callable, Dict, Optional, Any, List, Union

# Track API stability metadata for introspection and documentation
API_REGISTRY = {
    "stable": {},
    "beta": {},
    "experimental": {},
    "deprecated": {},
}


class APIStability(Enum):
    """API stability levels for IPFS Kit."""
    STABLE = "stable"
    BETA = "beta"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"


def stable_api(since: str):
    """
    Mark a function or method as a stable API with compatibility guarantees.
    
    Stable APIs will not change within the same major version. This includes:
    - Method signatures will not change
    - Return types will maintain backward compatibility
    - Behavior will remain consistent
    
    Args:
        since: Version when this API became stable (e.g., "0.1.0")
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Store metadata for API introspection
        wrapper.__api_stability__ = APIStability.STABLE
        wrapper.__api_since__ = since
        
        # Add to API registry
        func_id = f"{func.__module__}.{func.__qualname__}"
        API_REGISTRY["stable"][func_id] = {
            "since": since,
            "module": func.__module__,
            "name": func.__qualname__,
            "signature": str(inspect.signature(func)),
            "doc": inspect.getdoc(func),
        }
        
        return wrapper
    return decorator


def beta_api(since: str):
    """
    Mark a function or method as a beta API that is almost stable.
    
    Beta APIs might change in minor version updates, but efforts are made to maintain
    compatibility when possible. Changes to beta APIs will be documented in release notes.
    
    Args:
        since: Version when this API entered beta status (e.g., "0.1.0")
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Store metadata for API introspection
        wrapper.__api_stability__ = APIStability.BETA
        wrapper.__api_since__ = since
        
        # Add to API registry
        func_id = f"{func.__module__}.{func.__qualname__}"
        API_REGISTRY["beta"][func_id] = {
            "since": since,
            "module": func.__module__,
            "name": func.__qualname__,
            "signature": str(inspect.signature(func)),
            "doc": inspect.getdoc(func),
        }
        
        return wrapper
    return decorator


def experimental_api(since: str):
    """
    Mark a function or method as an experimental API with no stability guarantees.
    
    Experimental APIs may change at any time, even in patch versions. They are provided
    for early testing and feedback, and may be substantially revised or removed.
    
    Args:
        since: Version when this API was introduced (e.g., "0.1.0")
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Store metadata for API introspection
        wrapper.__api_stability__ = APIStability.EXPERIMENTAL
        wrapper.__api_since__ = since
        
        # Add to API registry
        func_id = f"{func.__module__}.{func.__qualname__}"
        API_REGISTRY["experimental"][func_id] = {
            "since": since,
            "module": func.__module__,
            "name": func.__qualname__,
            "signature": str(inspect.signature(func)),
            "doc": inspect.getdoc(func),
        }
        
        return wrapper
    return decorator


def deprecated(since: str, removed_in: str, alternative: Optional[str] = None):
    """
    Mark a function or method as deprecated.
    
    Deprecated APIs will raise a DeprecationWarning when used and will be removed
    in a future version. They are maintained temporarily for backward compatibility.
    
    Args:
        since: Version when this API was deprecated (e.g., "0.1.0")
        removed_in: Version when this API will be removed (e.g., "1.0.0")
        alternative: Name of alternative function/method to use instead
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            message = (
                f"{func.__qualname__} is deprecated since {since} "
                f"and will be removed in {removed_in}."
            )
            
            if alternative:
                message += f" Use {alternative} instead."
                
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        
        # Store metadata for API introspection
        wrapper.__api_stability__ = APIStability.DEPRECATED
        wrapper.__api_since__ = since
        wrapper.__api_removed_in__ = removed_in
        wrapper.__api_alternative__ = alternative
        
        # Add to API registry
        func_id = f"{func.__module__}.{func.__qualname__}"
        API_REGISTRY["deprecated"][func_id] = {
            "since": since,
            "removed_in": removed_in,
            "alternative": alternative,
            "module": func.__module__,
            "name": func.__qualname__,
            "signature": str(inspect.signature(func)),
            "doc": inspect.getdoc(func),
        }
        
        return wrapper
    return decorator


def get_api_stability(func) -> Optional[APIStability]:
    """Get the stability level of an API function or method."""
    return getattr(func, "__api_stability__", None)


def is_stable_api(func) -> bool:
    """Check if a function or method is a stable API."""
    return get_api_stability(func) == APIStability.STABLE


def is_beta_api(func) -> bool:
    """Check if a function or method is a beta API."""
    return get_api_stability(func) == APIStability.BETA


def is_experimental_api(func) -> bool:
    """Check if a function or method is an experimental API."""
    return get_api_stability(func) == APIStability.EXPERIMENTAL


def is_deprecated_api(func) -> bool:
    """Check if a function or method is a deprecated API."""
    return get_api_stability(func) == APIStability.DEPRECATED


def get_api_registry() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Get the complete API registry.
    
    Returns:
        Dictionary containing all registered API functions and their metadata,
        organized by stability level (stable, beta, experimental, deprecated).
    """
    return API_REGISTRY


def get_stability_metrics() -> Dict[str, int]:
    """
    Get metrics on API stability.
    
    Returns:
        Dictionary with counts of APIs by stability level.
    """
    return {
        "stable": len(API_REGISTRY["stable"]),
        "beta": len(API_REGISTRY["beta"]),
        "experimental": len(API_REGISTRY["experimental"]),
        "deprecated": len(API_REGISTRY["deprecated"]),
        "total": sum(len(apis) for apis in API_REGISTRY.values()),
    }


def generate_api_stability_report() -> Dict[str, Any]:
    """
    Generate a comprehensive report on API stability.
    
    Returns:
        Dictionary containing detailed information about all APIs,
        organized by stability level, with counts and detailed listings.
    """
    metrics = get_stability_metrics()
    
    # Organize methods by module
    modules = {}
    
    for stability in API_REGISTRY:
        for func_id, metadata in API_REGISTRY[stability].items():
            module = metadata["module"]
            
            if module not in modules:
                modules[module] = {
                    "stable": [],
                    "beta": [],
                    "experimental": [],
                    "deprecated": [],
                }
                
            modules[module][stability].append(metadata)
    
    # Compute stability percentage by module
    module_metrics = {}
    for module, data in modules.items():
        total = sum(len(apis) for apis in data.values())
        if total > 0:
            module_metrics[module] = {
                "total": total,
                "stable": len(data["stable"]),
                "beta": len(data["beta"]),
                "experimental": len(data["experimental"]),
                "deprecated": len(data["deprecated"]),
                "stability_score": (len(data["stable"]) * 100) / total,
            }
    
    return {
        "metrics": metrics,
        "modules": modules,
        "module_metrics": module_metrics,
    }


def print_api_stability_report():
    """Print a formatted API stability report to the console."""
    report = generate_api_stability_report()
    metrics = report["metrics"]
    module_metrics = report["module_metrics"]
    
    print("\n=== IPFS Kit API Stability Report ===\n")
    
    print(f"Total APIs: {metrics['total']}")
    print(f"  Stable: {metrics['stable']} ({metrics['stable']*100/metrics['total']:.1f}%)")
    print(f"  Beta: {metrics['beta']} ({metrics['beta']*100/metrics['total']:.1f}%)")
    print(f"  Experimental: {metrics['experimental']} ({metrics['experimental']*100/metrics['total']:.1f}%)")
    print(f"  Deprecated: {metrics['deprecated']} ({metrics['deprecated']*100/metrics['total']:.1f}%)")
    
    print("\nModule Stability Scores:")
    for module, data in sorted(module_metrics.items(), key=lambda x: x[1]["stability_score"], reverse=True):
        print(f"  {module}: {data['stability_score']:.1f}% stable ({data['stable']}/{data['total']} methods)")


def list_api_by_stability(stability: str) -> List[Dict[str, Any]]:
    """
    List all APIs with the specified stability level.
    
    Args:
        stability: Stability level ("stable", "beta", "experimental", "deprecated")
        
    Returns:
        List of API metadata dictionaries
    """
    if stability not in API_REGISTRY:
        raise ValueError(f"Invalid stability level: {stability}")
        
    return list(API_REGISTRY[stability].values())


def generate_markdown_api_docs() -> str:
    """
    Generate Markdown documentation of all APIs organized by stability level.
    
    Returns:
        Markdown string with formatted API documentation
    """
    report = generate_api_stability_report()
    modules = report["modules"]
    
    md = ["# IPFS Kit API Reference\n"]
    md.append("This document lists all API methods by stability level.\n")
    
    # Sort modules by name
    sorted_modules = sorted(modules.keys())
    
    # Add table of contents
    md.append("## Table of Contents\n")
    for module in sorted_modules:
        md.append(f"- [{module}](#{module.replace('.', '').lower()})")
    md.append("\n")
    
    # Generate documentation for each module
    for module in sorted_modules:
        md.append(f"## {module}\n")
        
        # Add stable APIs
        if modules[module]["stable"]:
            md.append("### Stable APIs\n")
            md.append("These APIs are stable and won't change within the same major version.\n")
            
            for api in sorted(modules[module]["stable"], key=lambda x: x["name"]):
                md.append(f"#### `{api['name']}{api['signature']}`\n")
                
                if api["doc"]:
                    md.append(f"{api['doc']}\n")
                    
                md.append(f"*Stable since: {api['since']}*\n\n")
        
        # Add beta APIs
        if modules[module]["beta"]:
            md.append("### Beta APIs\n")
            md.append("These APIs are nearly stable but may change in minor version updates.\n")
            
            for api in sorted(modules[module]["beta"], key=lambda x: x["name"]):
                md.append(f"#### `{api['name']}{api['signature']}`\n")
                
                if api["doc"]:
                    md.append(f"{api['doc']}\n")
                    
                md.append(f"*Beta since: {api['since']}*\n\n")
        
        # Add experimental APIs
        if modules[module]["experimental"]:
            md.append("### Experimental APIs\n")
            md.append("These APIs are experimental and may change at any time.\n")
            
            for api in sorted(modules[module]["experimental"], key=lambda x: x["name"]):
                md.append(f"#### `{api['name']}{api['signature']}`\n")
                
                if api["doc"]:
                    md.append(f"{api['doc']}\n")
                    
                md.append(f"*Experimental since: {api['since']}*\n\n")
        
        # Add deprecated APIs
        if modules[module]["deprecated"]:
            md.append("### Deprecated APIs\n")
            md.append("These APIs are deprecated and will be removed in a future version.\n")
            
            for api in sorted(modules[module]["deprecated"], key=lambda x: x["name"]):
                md.append(f"#### `{api['name']}{api['signature']}`\n")
                
                if api["doc"]:
                    md.append(f"{api['doc']}\n")
                    
                md.append(f"*Deprecated since: {api['since']}*\n")
                md.append(f"*Will be removed in: {api['removed_in']}*\n")
                
                if api["alternative"]:
                    md.append(f"*Use {api['alternative']} instead*\n\n")
                else:
                    md.append("\n")
    
    return "\n".join(md)