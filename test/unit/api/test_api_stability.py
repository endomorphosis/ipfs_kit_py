#!/usr/bin/env python3
"""
Test script to verify API stability decorators are properly applied.
"""

# Directly import to avoid dependency issues
from ipfs_kit_py.api_stability import API_REGISTRY

def print_stability_summary():
    """Print a summary of API stability decorators."""
    print("\n=== API Stability Summary ===\n")

    total_apis = sum(len(apis) for apis in API_REGISTRY.values())
    print(f"Total decorated APIs: {total_apis}")

    for stability_level, apis in API_REGISTRY.items():
        if apis:
            print(f"\n{stability_level.upper()} APIs ({len(apis)}):")
            for func_id, metadata in apis.items():
                print(f"  - {metadata['name']} (since {metadata['since']})")

if __name__ == "__main__":
    print_stability_summary()
