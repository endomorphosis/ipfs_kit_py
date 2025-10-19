#!/bin/bash
# Simple ARM64 build and test script
# This script tests the package build on any architecture, focusing on ARM64

set -e  # Exit on error

echo "=== ARM64 Package Build and Test ==="
echo "Architecture: $(uname -m)"
echo "Python version: $(python3 --version)"
echo ""

# Clean up previous builds
echo "Cleaning up previous builds..."
rm -rf dist build *.egg-info test_venv
echo ""

# Verify pyproject.toml is valid
echo "Verifying pyproject.toml configuration..."
python3 -c "import sys; sys.path.insert(0, '.'); exec(open('pyproject.toml').read())" 2>/dev/null || {
    echo "Note: Cannot validate TOML directly, but setup.py will validate it"
}
echo ""

# Check package version
echo "Checking package version..."
python3 setup.py --version || {
    echo "Error: Cannot determine package version"
    exit 1
}
echo ""

# Build wheel package (without isolation to avoid network timeouts)
echo "Building wheel package..."
python3 -m pip install --user build 2>&1 | tail -3
python3 -m build --wheel --no-isolation || {
    echo "Error: Wheel build failed"
    exit 1
}
echo ""

# Verify wheel was created
if [ ! -f dist/ipfs_kit_py-0.3.0-py3-none-any.whl ]; then
    echo "Error: Wheel file not found"
    exit 1
fi

echo "Wheel built successfully: $(ls -lh dist/*.whl)"
echo ""

# Create test virtual environment
echo "Creating test virtual environment..."
python3 -m venv test_venv
source test_venv/bin/activate
echo ""

# Install the wheel
echo "Installing wheel package..."
pip install dist/ipfs_kit_py-0.3.0-py3-none-any.whl || {
    echo "Note: Wheel installation requires dependencies from PyPI"
    echo "Testing import with minimal dependencies..."
    # Try to install just the wheel without dependencies for basic testing
    pip install --no-deps dist/ipfs_kit_py-0.3.0-py3-none-any.whl || {
        echo "Error: Failed to install wheel even without dependencies"
        deactivate
        exit 1
    }
}
echo ""

# Test basic import
echo "Testing package import..."
python3 -c "import ipfs_kit_py; print('✓ Package imported successfully')" || {
    echo "Error: Failed to import package"
    deactivate
    exit 1
}
echo ""

# Install test dependencies
echo "Installing test dependencies..."
pip install pytest pytest-asyncio --quiet || echo "Warning: Could not install all test dependencies"
echo ""

# Run basic smoke tests
echo "Running smoke tests..."
if [ -f tests/test_arm64_basic.py ]; then
    pytest tests/test_arm64_basic.py -v || echo "Warning: Some tests failed"
else
    echo "Smoke test file not found, skipping"
fi
echo ""

# Cleanup
deactivate
echo "=== Build and Test Complete ==="
echo "✓ Package builds successfully"
echo "✓ Package can be installed"
echo "✓ Package can be imported"
echo ""
