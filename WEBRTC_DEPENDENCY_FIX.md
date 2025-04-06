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