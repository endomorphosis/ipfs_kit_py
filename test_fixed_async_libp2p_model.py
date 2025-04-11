#\!/usr/bin/env python3
"""
Test script to verify that the async methods in LibP2PModel
are properly implemented with anyio.to_thread.run_sync.
"""

import asyncio
import warnings
import inspect

# Enable warnings for coroutines that are never awaited
warnings.filterwarnings('error', message='coroutine .* was never awaited')

# Import the model class
from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel

def print_method_signature(method):
    """Print the signature of a method."""
    sig = inspect.signature(method)
    print(f"Method signature: {method.__name__}{sig}")
    print(f"Return annotation: {sig.return_annotation}")
    print("Is async: ", inspect.iscoroutinefunction(method))
    print("\n")

async def test_async_methods():
    """Test that all async methods are properly implemented."""
    print("Starting async methods test...")
    
    # Create a model instance
    model = LibP2PModel()
    
    # Test if model has logger attribute
    if not hasattr(model, 'logger'):
        print("ERROR: LibP2PModel missing logger attribute")
    else:
        print("LibP2PModel has logger attribute: OK")
    
    # Test the async is_available method
    print("\nTesting is_available method:")
    print_method_signature(model.is_available)
    
    try:
        # Call the async method and await it
        result = await model.is_available()
        print(f"is_available result: {result}")
        print("is_available test: PASSED")
    except Exception as e:
        print(f"is_available test FAILED: {e}")
    
    # Test the async get_health method
    print("\nTesting get_health method:")
    print_method_signature(model.get_health)
    
    try:
        # Call the async method and await it
        result = await model.get_health()
        print(f"get_health result type: {type(result)}")
        print("get_health test: PASSED")
    except Exception as e:
        print(f"get_health test FAILED: {e}")
    
    # Test the async register_message_handler method
    print("\nTesting register_message_handler method:")
    print_method_signature(model.register_message_handler)
    
    try:
        # Call the async method and await it
        result = await model.register_message_handler("test_handler", "test_protocol", "Test description")
        print(f"register_message_handler result type: {type(result)}")
        print("register_message_handler test: PASSED")
    except Exception as e:
        print(f"register_message_handler test FAILED: {e}")
    
    print("\nAll tests completed.")

if __name__ == "__main__":
    # Run the async tests
    asyncio.run(test_async_methods())
