import asyncio
import sys

# Safe patch for asyncio that avoids using 'async' as an attribute name
def patch_asyncio():
    # Check if we need to patch
    if hasattr(asyncio, 'events'):
        events = asyncio.events
        
        # Save the original attribute if it exists using getattr to avoid syntax errors
        if hasattr(events, '_orig_async'):
            return False  # Already patched
            
        # Store original value safely using getattr
        if hasattr(events, 'async'):
            orig_async = getattr(events, 'async')
            # Save the original value safely
            setattr(events, '_orig_async', orig_async)
            # Delete the problematic attribute
            delattr(events, 'async')
            
            # Add our safe version
            setattr(events, 'async_', orig_async)
            return True
    return False

# Apply the patch
patch_result = patch_asyncio()
if patch_result:
    print("Successfully applied asyncio compatibility patch")
else:
    print("Asyncio compatibility patch not needed or already applied")
