# Lotus Dependency Fix

## Overview

This document outlines the changes made to fix the dependency issues with the Lotus binary in the ipfs_kit_py library. The implementation ensures that required system dependencies for the Lotus binary are automatically detected and installed on the first run of the `lotus_kit` class, without requiring manual intervention.

## Problem Statement

The Lotus binary requires specific system libraries (most notably `libhwloc.so.15`) that may not be present on all systems. When these dependencies are missing, the Lotus binary fails to run, resulting in the `LOTUS_AVAILABLE` flag being set to `False` and forcing the library to run in simulation mode, even when the binary itself is installed.

## Solution Implemented

1. Enhanced `install_lotus.py` with system dependency detection and installation
2. Added automatic invocation of the dependency installer when the `lotus_kit` class is initialized
3. Implemented platform-specific package management for installing required libraries
4. Created a testing script to verify the dependency installation process

### Key Components

#### 1. `_install_system_dependencies` Method in `install_lotus.py`

This method:
- Detects the operating system and distribution
- Identifies package manager-specific requirements
- Checks for missing required system packages
- Installs missing dependencies using the appropriate package manager
- Handles different Linux distributions (Debian, Ubuntu, Fedora, CentOS, Alpine, Arch)
- Provides macOS support using Homebrew

#### 2. `_check_and_install_dependencies` Method in `lotus_kit.py`

This method:
- Is called during initialization of the `lotus_kit` class
- Imports and uses the `install_lotus` module
- Configures and runs the dependency installer
- Updates the global availability flags based on installation results
- Handles errors gracefully with appropriate logging

#### 3. Auto-Initialization in `lotus_kit.__init__`

Modified the `__init__` method to:
- Check for Lotus availability
- Invoke dependency installation if needed (controlled by metadata)
- Update simulation mode based on the availability after installation

#### 4. Testing Script

Created `test_lotus_dependencies.py` to:
- Test the automatic dependency installation
- Verify Lotus availability before and after initialization
- Test the connection to Lotus API
- Display detailed results

## Implementation Details

### System Dependency Installation

The implementation identifies and installs different packages based on the detected operating system:

#### Linux Dependencies

- **Ubuntu/Debian**: `hwloc`, `libhwloc-dev`, `mesa-opencl-icd`, `ocl-icd-opencl-dev`
- **Fedora/CentOS**: `hwloc`, `hwloc-devel`, `opencl-headers`, `ocl-icd-devel`
- **Alpine**: `hwloc`, `hwloc-dev`, `opencl-headers`, `opencl-icd-loader-dev`
- **Arch**: `hwloc`, `opencl-headers`, `opencl-icd-loader`

#### macOS Dependencies

- **Homebrew**: `hwloc`

#### Windows

- No additional system dependencies required (binaries include necessary DLLs)

### Automatic Installation Process

The installation process follows these steps:

1. Detect the operating system and distribution
2. Identify the appropriate package manager
3. Check for missing required packages
4. Update package repositories if needed
5. Install missing packages
6. Verify installation success
7. Update availability flags

## Usage

The dependency installation is automatic by default when creating a `lotus_kit` instance:

```python
from ipfs_kit_py.lotus_kit import lotus_kit

# This will automatically check and install dependencies if needed
kit = lotus_kit()

# Or explicitly control dependency installation
kit = lotus_kit(metadata={
    "install_dependencies": True,  # Enable automatic dependency installation
    "simulation_mode": False       # Try to use real Lotus if available
})

# Check connection to verify Lotus is working
result = kit.check_connection()
print(f"Connection successful: {result.get('success', False)}")
```

## Testing

### Basic Dependency Testing

The basic dependency installation can be tested using the provided `test_lotus_dependencies.py` script:

```bash
python test_lotus_dependencies.py
```

The script will:
1. Show the initial Lotus availability state
2. Create a lotus_kit instance, triggering dependency installation
3. Show the Lotus availability after installation
4. Test connection to the Lotus API
5. Display the connection results

### Comprehensive Functionality Testing

To verify that the Lotus client is truly operational with all dependencies correctly installed, use the comprehensive `test_lotus_client_working.py` script:

```bash
python test_lotus_client_working.py
```

This script performs a thorough verification:
1. Installs dependencies if needed
2. Checks if the Lotus binary is available
3. Starts the Lotus daemon if it's not already running
4. Tests multiple real Lotus operations:
   - Chain head retrieval
   - Wallet listing and balance checking
   - Network peer information
5. Provides detailed success/failure reporting

The script will work in either real mode or simulation mode, allowing you to verify that the Lotus client is operational even if the daemon can't be started for some reason.

## Benefits

1. **Automated Setup**: Eliminates manual dependency installation requirements
2. **Cross-Platform Support**: Works across different Linux distributions, macOS, and Windows
3. **Graceful Degradation**: Falls back to simulation mode when installation fails
4. **Transparent Process**: Provides detailed logging of installation steps
5. **User Control**: Allows disabling automatic installation through metadata

## Conclusion

This implementation ensures that the Lotus binary dependencies are automatically handled when the `lotus_kit` class is first initialized, providing a seamless experience for users while maintaining the ability to operate in simulation mode when necessary. This eliminates one of the main barriers to using the real Lotus daemon for Filecoin operations.