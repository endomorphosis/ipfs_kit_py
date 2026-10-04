# PyPI Release Guide for IPFS Kit

This guide provides comprehensive instructions for preparing and publishing IPFS Kit to the Python Package Index (PyPI), allowing users to install it with `pip install ipfs_kit_py`.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Package Structure Preparation](#package-structure-preparation)
3. [Metadata Configuration](#metadata-configuration)
4. [Version Management](#version-management)
5. [Building the Package](#building-the-package)
6. [Testing the Package Locally](#testing-the-package-locally)
7. [Publishing to PyPI](#publishing-to-pypi)
8. [Post-Release Tasks](#post-release-tasks)
9. [Installation Guide for Users](#installation-guide-for-users)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

Before publishing to PyPI, ensure you have the following:

- A PyPI account (register at [https://pypi.org/account/register/](https://pypi.org/account/register/))
- Required Python packages:
  ```bash
  pip install build twine setuptools wheel
  ```
- Access rights to the ipfs_kit_py project on PyPI (for maintainers)

## Package Structure Preparation

The IPFS Kit repository should follow the standard Python package structure:

```
ipfs_kit_py/
├── pyproject.toml        # Modern build system configuration
├── setup.py              # Traditional setup script (optional with pyproject.toml)
├── setup.cfg             # Additional configuration
├── MANIFEST.in           # Specifies additional files to include
├── README.md             # Project description
├── LICENSE               # License file
├── ipfs_kit_py/          # Actual package directory
│   ├── __init__.py       # Package initialization with version
│   ├── ...               # Other modules
├── test/                 # Test directory
└── docs/                 # Documentation
```

### Key File Configurations

#### 1. pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ipfs_kit_py"
version = "1.0.0"  # Update accordingly
authors = [
    {name = "Your Name", email = "your.email@example.com"},
]
description = "A comprehensive Python toolkit for IPFS with tiered storage, advanced networking, and knowledge graph capabilities"
readme = "README.md"
requires-python = ">=3.8"
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Topic :: System :: Distributed Computing",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "requests>=2.28.0",
    "multiformats>=0.1.4",
    "boto3>=1.26.0",
    "aiohttp>=3.8.4",
    "pydantic>=2.0.0",
    "fsspec>=2023.3.0",
    "pyarrow>=12.0.0",
    "fastapi>=0.100.0",
    "uvicorn>=0.22.0",
    "networkx>=3.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.1.0",
    "pylint>=2.17.0",
    "black>=23.3.0",
    "mypy>=1.3.0"
]

ml = [
    "torch>=2.0.0",
    "transformers>=4.30.0",
    "sentence-transformers>=2.2.2",
    "faiss-cpu>=1.7.4"
]

docs = [
    "sphinx>=6.0.0",
    "sphinx-rtd-theme>=1.2.0"
]

[project.urls]
"Homepage" = "https://github.com/yourusername/ipfs_kit_py"
"Bug Tracker" = "https://github.com/yourusername/ipfs_kit_py/issues"

[project.scripts]
ipfs-kit = "ipfs_kit_py.cli:main"
```

#### 2. MANIFEST.in

```
include LICENSE
include README.md
include pyproject.toml
include requirements.txt

recursive-include ipfs_kit_py/bin *
recursive-include docs *.md
recursive-include examples *.py
```

## Metadata Configuration

Ensure the package metadata accurately reflects the project:

1. **Version**: Follow [Semantic Versioning](https://semver.org/)
2. **Description**: Provide a clear, concise summary of the package
3. **Classifiers**: Use appropriate [PyPI classifiers](https://pypi.org/classifiers/)
4. **Dependencies**: List all required packages with version constraints
5. **Optional Dependencies**: Group optional dependencies logically
6. **URLs**: Include links to the project homepage, documentation, and issue tracker

### Version Information

Version should be maintained in a single location, typically in `ipfs_kit_py/__init__.py`:

```python
"""IPFS Kit Python package."""
__version__ = "1.0.0"
```

## Version Management

Follow these versioning practices:

1. **Semantic Versioning**:
   - MAJOR version for incompatible API changes
   - MINOR version for backward-compatible new features
   - PATCH version for backward-compatible bug fixes

2. **Pre-release Versioning**:
   - Alpha releases: `1.0.0a1`, `1.0.0a2`...
   - Beta releases: `1.0.0b1`, `1.0.0b2`...
   - Release candidates: `1.0.0rc1`, `1.0.0rc2`...

3. **Version Bump Process**:
   - Update version in `__init__.py`
   - Update version in `pyproject.toml`
   - Create a git tag for the version
   - Update CHANGELOG.md with release notes

## Building the Package

Build the package distribution files:

```bash
# Navigate to project root
cd /path/to/ipfs_kit_py

# Build source distribution and wheel
python -m build
```

This creates:
- A source distribution (`.tar.gz` file)
- A wheel distribution (`.whl` file) in the `dist/` directory

## Testing the Package Locally

Test the package locally before publishing:

```bash
# Create and activate a test environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install the package locally
pip install dist/ipfs_kit_py-1.0.0-py3-none-any.whl

# Run tests
python -c "import ipfs_kit_py; print(ipfs_kit_py.__version__)"
```

Perform additional validation:

```bash
# Validate package structure
twine check dist/*
```

## Publishing to PyPI

### Test PyPI (Recommended First Step)

Upload to [Test PyPI](https://test.pypi.org/) first to verify everything works:

```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

Test installation from Test PyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ ipfs_kit_py
```

### Production PyPI

Once validated, upload to the official PyPI:

```bash
twine upload dist/*
```

You'll be prompted for your PyPI username and password.

For automation, use API tokens instead of a password:
1. Generate a token at [https://pypi.org/manage/account/token/](https://pypi.org/manage/account/token/)
2. Store it securely in your environment or CI/CD system
3. Use it with twine:
   ```bash
   twine upload dist/* -u __token__ -p pypi-YOUR-TOKEN
   ```

## Post-Release Tasks

After a successful release:

1. **Tag the Release**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Create a GitHub Release**:
   - Go to Releases on GitHub
   - Create a new release using the tag
   - Include release notes from CHANGELOG.md

3. **Update Documentation**:
   - Ensure installation instructions reference the new version
   - Update any version-specific documentation

4. **Announce the Release**:
   - Project communication channels
   - Relevant community forums

## Automating Releases

For a streamlined release process, automate versioning and publishing with GitHub Actions.

### Automated Release Workflow

Create `.github/workflows/release.yml`:

```yaml
name: Create Release

on:
  workflow_dispatch:
    inputs:
      version_type:
        description: 'Version increment type'
        required: true
        default: 'patch'
        type: choice
        options:
        - patch
        - minor
        - major

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Configure Git
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install bump2version
      
      - name: Determine current version
        id: current_version
        run: |
          CURRENT_VERSION=$(grep -Po '(?<=__version__ = ")[^"]*' ipfs_kit_py/__init__.py)
          echo "current_version=$CURRENT_VERSION" >> $GITHUB_OUTPUT
      
      - name: Bump version
        run: |
          bump2version ${{ github.event.inputs.version_type }} --verbose
      
      - name: Get new version
        id: new_version
        run: |
          NEW_VERSION=$(grep -Po '(?<=__version__ = ")[^"]*' ipfs_kit_py/__init__.py)
          echo "new_version=$NEW_VERSION" >> $GITHUB_OUTPUT
      
      - name: Update CHANGELOG
        run: |
          # Get commit messages since last tag
          CHANGES=$(git log --pretty=format:"- %s" $(git describe --tags --abbrev=0)..HEAD)
          
          # Update CHANGELOG.md
          DATE=$(date +%Y-%m-%d)
          TEMP_FILE=$(mktemp)
          cat > $TEMP_FILE << EOF
          # Changelog

          ## ${{ steps.new_version.outputs.new_version }} ($DATE)

          $CHANGES

          EOF
          
          if [ -f CHANGELOG.md ]; then
            tail -n +2 CHANGELOG.md >> $TEMP_FILE
          fi
          
          mv $TEMP_FILE CHANGELOG.md
      
      - name: Commit and push changes
        run: |
          git add ipfs_kit_py/__init__.py pyproject.toml CHANGELOG.md
          git commit -m "Bump version to ${{ steps.new_version.outputs.new_version }}"
          git push
          git tag v${{ steps.new_version.outputs.new_version }}
          git push --tags
      
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: v${{ steps.new_version.outputs.new_version }}
          name: Release v${{ steps.new_version.outputs.new_version }}
          body_path: CHANGELOG.md
          draft: false
          prerelease: false
```

### Automated Publishing Workflow

This workflow builds and publishes the package when a new release is created:

```yaml
name: Build and Publish Package

on:
  release:
    types: [published]

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine wheel
      
      - name: Build package
        run: |
          python -m build
      
      - name: Check package
        run: |
          twine check dist/*
      
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          user: __token__
          password: ${{ secrets.PYPI_API_TOKEN }}
```

### Using the Automated Release Process

With these workflows in place, releasing a new version is as simple as:

1. Go to the "Actions" tab in your GitHub repository
2. Select the "Create Release" workflow
3. Click "Run workflow"
4. Choose the version increment type (patch, minor, or major)
5. Click "Run workflow" again

The workflow will:
1. Bump the version in `__init__.py` and `pyproject.toml`
2. Update the CHANGELOG.md with commit messages since the last tag
3. Commit the changes and create a new git tag
4. Create a GitHub Release
5. Trigger the "Build and Publish Package" workflow, which publishes to PyPI

### Setting Up bump2version

To use the automated release workflow, you need to configure bump2version. Create a `.bumpversion.cfg` file:

```ini
[bumpversion]
current_version = 1.0.0
commit = True
tag = True

[bumpversion:file:ipfs_kit_py/__init__.py]
search = __version__ = "{current_version}"
replace = __version__ = "{new_version}"

[bumpversion:file:pyproject.toml]
search = version = "{current_version}"
replace = version = "{new_version}"
```

This configuration ensures that both `__init__.py` and `pyproject.toml` are updated with the new version.

## Installation Guide for Users

Include the following installation instructions in your README:

### Basic Installation

```bash
pip install ipfs_kit_py
```

### Installation with Optional Dependencies

```bash
# Install with machine learning support
pip install ipfs_kit_py[ml]

# Install with development tools
pip install ipfs_kit_py[dev]

# Install with documentation tools
pip install ipfs_kit_py[docs]

# Install all optional dependencies
pip install ipfs_kit_py[ml,dev,docs]
```

### Verifying Installation

```python
import ipfs_kit_py

# Print version
print(ipfs_kit_py.__version__)

# Initialize IPFS Kit
kit = ipfs_kit_py.ipfs_kit()

# Check health
health_status = kit.check_health()
print(f"IPFS Kit health: {health_status['status']}")
```

## Troubleshooting

### Common Package Installation Issues

1. **Dependency Conflicts**:
   - Use virtual environments to isolate dependencies
   - Consider loosening version constraints if not strictly necessary

2. **Binary Dependencies**:
   - Document system requirements (e.g., OS-specific packages)
   - Provide instructions for installing binary dependencies

3. **Version Mismatch**:
   - Always ensure version numbers are consistent across all files
   - Use `__version__` in `__init__.py` as the single source of truth

4. **Package Not Found After Installation**:
   - Verify the package name in `pyproject.toml` matches the import name
   - Check for namespace package issues

5. **Missing Files in Package**:
   - Verify MANIFEST.in includes all necessary files
   - Test unpacking the source distribution to check contents

### PyPI-Specific Issues

1. **"File already exists" Error**:
   - Cannot upload the same version twice to PyPI
   - Must increment version number for new uploads

2. **Authentication Failures**:
   - Verify username and password
   - Check token expiration and permissions
   - Confirm network connectivity to PyPI

3. **Long Description Rendering**:
   - Ensure README.md follows GitHub-flavored Markdown
   - Use `twine check` to validate before uploading

### Getting Help

If you encounter issues not covered here:

1. Check the [PyPI documentation](https://packaging.python.org/)
2. Search for similar issues on GitHub
3. File a new issue on the IPFS Kit issue tracker