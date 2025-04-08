# WebRTC Dependency Fix

## Problem Description

The WebRTC streaming functionality in `ipfs_kit_py` was causing import errors when optional dependencies (av, cv2, aiortc) were not installed. These import errors were breaking the ability to use the entire package even when WebRTC functionality wasn't needed.

## Solution Approach

The fix implements a more robust dependency handling approach that:

1. **Granular Dependency Checking**: Checks for each dependency individually (av, cv2, numpy, aiortc)
2. **Conditional Class Definitions**: Only defines implementation classes when dependencies are available
3. **Stub Implementations**: Provides stub implementations that raise informative errors when used
4. **Proper Import Error Handling**: Ensures the module can be imported even when dependencies are missing
5. **Improved Error Messages**: Provides clear instructions for installing missing dependencies

## Files Modified

1. **webrtc_streaming.py**: 
   - Added individual dependency availability flags 
   - Implemented conditional class definitions
   - Added proper stub implementations
   - Improved error messages

2. **high_level_api.py**:
   - Fixed import handling for WebRTC components
   - Added proper stub implementation for handle_webrtc_signaling
   - Added explicit flags for dependency status

## Testing

A dedicated test script (`test_webrtc_fix.py`) was created to verify that:

1. The WebRTC module can be imported without errors
2. The dependency availability flags correctly reflect system state
3. Stub implementations properly raise ImportError when used
4. high_level_api can be imported without dependency errors

This approach allows the codebase to work correctly regardless of whether the optional WebRTC dependencies are installed, while still providing helpful error messages when users attempt to use functionality that requires the missing dependencies.

## Installation Instructions

To use the WebRTC streaming functionality, install with:

```bash
pip install ipfs_kit_py[webrtc]
```

This will install the required dependencies:
- av (PyAV for media handling)
- opencv-python (OpenCV for video processing)
- numpy (for numerical operations)
- aiortc (for WebRTC implementation)

## Future Improvements

For even more robust dependency handling, consider:

1. Adding a proper entry in `setup.py` for the WebRTC extra requirements
2. Implementing lazy imports for more efficient loading
3. Adding functionality level checks rather than just import checks
4. Creating a dependency status endpoint in the API for better diagnostics

## Test Integration Fix

We've also fixed an issue with the WebRTC tests being skipped when running through pytest, even though dependencies were available. 

### Problem with Test Skipping

The tests in `test_webrtc_streaming.py` were being skipped despite:
- WebRTC dependencies being available
- Explicitly setting `_can_test_webrtc = True` in the test file

This was happening because:
1. Pytest import collection behaves differently than direct file execution
2. Syntax errors in `cluster_state_helpers.py` were preventing imports from working properly during test setup

### Solution Implemented

We made several fixes to ensure WebRTC tests can run consistently:

1. **Fixed Syntax Errors**: Fixed critical syntax errors in `cluster_state_helpers.py` that prevented the module from importing correctly

2. **Test File Improvements**: Modified `test_webrtc_streaming.py` to better handle both direct execution and pytest collection with these changes:

   a. **Context Detection**: Added detection of pytest vs. direct execution contexts
   ```python
   # Check if we're in a pytest context or direct import
   import sys
   _in_pytest = any('pytest' in arg for arg in sys.argv) or 'pytest' in sys.modules
   ```

   b. **Advanced Dependency Verification**: Now we check actual functionality, not just imports
   ```python
   # Try creating test instances to verify all dependencies
   if HAVE_WEBRTC:
       test_manager = WebRTCStreamingManager(ipfs_api=None)
       _can_test_webrtc = True
   ```

   c. **Environment Variable Override**: Added flags to force-enable tests
   ```python
   # Check if FORCE_WEBRTC_TESTS environment variable is set
   import os
   if os.environ.get('FORCE_WEBRTC_TESTS') == '1':
       _can_test_webrtc = True
   ```

### Running WebRTC Tests

To force WebRTC tests to run regardless of dependency detection:

```bash
# Run WebRTC tests with core dependencies
FORCE_WEBRTC_TESTS=1 python -m pytest test/test_webrtc_streaming.py

# Run notification tests that require additional dependencies
FORCE_NOTIFICATION_TESTS=1 python -m pytest test/test_webrtc_streaming.py

# Run all WebRTC tests
FORCE_WEBRTC_TESTS=1 FORCE_NOTIFICATION_TESTS=1 python -m pytest test/test_webrtc_streaming.py
```

This fix ensures consistent test behavior regardless of how the tests are run, while preserving the ability to skip tests when dependencies truly aren't available.