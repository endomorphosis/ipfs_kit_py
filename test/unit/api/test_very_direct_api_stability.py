#!/usr/bin/env python3
"""
Very direct test of API stability by importing the module file directly.
"""
import sys
import os
import importlib.util

# Get the absolute path to the api_stability.py file
api_stability_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "ipfs_kit_py",
    "api_stability.py"
)

high_level_api_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "ipfs_kit_py",
    "high_level_api.py"
)

# Load the modules directly
spec = importlib.util.spec_from_file_location("api_stability", api_stability_path)
api_stability = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_stability)

# Load the high-level API to register decorated methods
try:
    print("Attempting to load high_level_api.py...")
    spec2 = importlib.util.spec_from_file_location("high_level_api", high_level_api_path)
    high_level_api = importlib.util.module_from_spec(spec2)
    sys.modules["high_level_api"] = high_level_api
    spec2.loader.exec_module(high_level_api)
    print("Successfully loaded high_level_api.py")
except Exception as e:
    print(f"Error loading high_level_api.py: {e}")

def print_stability_summary():
    """Print a summary of API stability decorators."""
    print("\n=== API Stability Summary ===\n")

    total_apis = sum(len(apis) for apis in api_stability.API_REGISTRY.values())
    print(f"Total decorated APIs: {total_apis}")

    for stability_level, apis in api_stability.API_REGISTRY.items():
        if apis:
            print(f"\n{stability_level.upper()} APIs ({len(apis)}):")
            for func_id, metadata in sorted(apis.items()):
                print(f"  - {metadata['name']} (since {metadata['since']})")

if __name__ == "__main__":
    print_stability_summary()
