#!/bin/bash
set -e

# Display banner
echo "=============================================="
echo "   IPFS Kit Python Package Build Script"
echo "=============================================="

# Check for required tools
echo "Checking for required tools..."
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed. Aborting."; exit 1; }
command -v pip >/dev/null 2>&1 || { echo "pip is required but not installed. Aborting."; exit 1; }

# Install build dependencies if needed
echo "Installing build dependencies..."
pip install --quiet --upgrade pip build twine wheel

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/

# Format code
echo "Formatting code with black..."
black ipfs_kit_py test

echo "Formatting imports with isort..."
isort ipfs_kit_py test

# Run checks
echo "Running checks..."
echo "- Checking code style with black..."
black --check ipfs_kit_py test

echo "- Checking imports with isort..."
isort --check ipfs_kit_py test

# Build package
echo "Building package..."
python -m build

# Check package
echo "Checking distribution..."
twine check dist/*

# List package contents
echo "Package contents:"
tar tzf dist/*.tar.gz | grep -v "__pycache__" | sort | head -n 20
echo "... (and more files)"

# Show package info
echo "Package information:"
echo "- Size: $(du -h dist/*.whl | cut -f1) (wheel)"
echo "- Size: $(du -h dist/*.tar.gz | cut -f1) (source)"

echo "Build process completed successfully!"
echo 
echo "To install locally:"
echo "  pip install dist/*.whl"
echo
echo "To upload to PyPI:"
echo "  twine upload dist/*"
echo
echo "To upload to Test PyPI:"
echo "  twine upload --repository-url https://test.pypi.org/legacy/ dist/*"
echo