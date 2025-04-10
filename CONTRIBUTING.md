# Contributing to ipfs_kit_py

Thank you for your interest in contributing to the ipfs_kit_py project! This module aims to provide a comprehensive Python interface to IPFS, IPFS Cluster, and related technologies. Your contributions help make this project better for everyone.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
  - [Code Contributions](#code-contributions)
  - [Documentation](#documentation)
  - [Testing](#testing)
- [Style Guidelines](#style-guidelines)
  - [Python Code Style](#python-code-style)
  - [Documentation Style](#documentation-style)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)
- [Release Process](#release-process)
- [Community](#community)

## Code of Conduct

This project follows a standard code of conduct to ensure a welcoming and inclusive environment for all contributors. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

To get started with contributing to ipfs_kit_py:

1. Fork the repository on GitHub
2. Clone your fork to your local machine
3. Set up the development environment (see [Development Environment](#development-environment))
4. Create a new branch for your changes
5. Make your changes
6. Run tests to ensure your changes work as expected
7. Submit a pull request

## Development Environment

### Required Dependencies

- Python >=3.8
- IPFS daemon (Kubo >=0.18.0 recommended)
- IPFS Cluster tools (optional, for distributed features)

### Setup Instructions

1. Clone the repository with submodules:
   ```bash
   git clone --recurse-submodules https://github.com/YourUsername/ipfs_kit_py.git
   cd ipfs_kit_py
   ```
   
   If you forgot to include `--recurse-submodules`, you can initialize and update the submodules after cloning:
   ```bash
   git submodule init
   git submodule update
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Verify installation:
   ```bash
   python -m test.test
   ```

## How to Contribute

### Reporting Bugs

When reporting bugs, please include:

- A clear, descriptive title
- Steps to reproduce the issue
- Expected behavior vs. actual behavior
- System information (OS, Python version, IPFS version)
- Any relevant logs or error messages

Use the GitHub issue tracker to report bugs.

### Suggesting Enhancements

For enhancement suggestions:

- Describe the enhancement clearly and concisely
- Explain why this enhancement would be useful
- Provide examples of how the feature would be used
- If possible, outline how the enhancement might be implemented

### Code Contributions

1. Check existing issues and pull requests to avoid duplication
2. For significant changes, open an issue for discussion first
3. Follow the [Style Guidelines](#style-guidelines)
4. Write tests for new features
5. Update documentation as needed
6. Submit a pull request with a clear description of your changes

### Documentation

Documentation improvements are always welcome. Please follow these guidelines:

- Keep documentation simple and accessible
- Use clear examples
- Follow the [Documentation Style](#documentation-style)
- Update API documentation when changing interfaces

### Testing

All contributions should maintain or improve test coverage:

- Write unit tests for new features
- Ensure existing tests pass with your changes
- Follow the testing patterns established in the project

## Style Guidelines

### Python Code Style

- Follow PEP 8 conventions
- Use 4-space indentation
- Keep lines under 100 characters
- Use docstrings for all public functions, classes, and methods
- Use type hints for function parameters and return values

#### Standard Error Handling Approach

Follow the established error handling pattern in the codebase:

```python
def perform_operation(self, arg1, arg2):
    """Perform some IPFS operation with standardized result handling."""
    result = {
        "success": False,
        "operation": "perform_operation",
        "timestamp": time.time()
    }
    
    try:
        # Perform actual operation
        response = self.ipfs.some_method(arg1, arg2)
        
        # Process successful response
        result["success"] = True
        result["cid"] = response.get("Hash")
        result["size"] = response.get("Size")
        
    except requests.exceptions.ConnectionError as e:
        # Network-related errors
        result["error"] = f"IPFS daemon connection failed: {str(e)}"
        result["error_type"] = "connection_error"
        result["recoverable"] = True
        self.logger.error(f"Connection error in {result['operation']}: {e}")
        
    except Exception as e:
        # Catch-all for unexpected errors
        result["error"] = f"Unexpected error: {str(e)}"
        result["error_type"] = "unknown_error"
        result["recoverable"] = False
        # Include stack trace in logs but not in result
        self.logger.exception(f"Unexpected error in {result['operation']}")
        
    return result
```

### Documentation Style

- Address readers in the second person ("you" instead of "we" or "I")
- Use clear, concise language
- Include practical examples
- Keep titles in sentence case (capitalize first word only)
- Use American English spelling

## Pull Request Process

1. Create a descriptive pull request that explains your changes
2. Ensure all tests pass and code style checks succeed
3. Update relevant documentation
4. Link any related issues
5. Wait for review from maintainers
6. Address any requested changes
7. Once approved, your PR will be merged

## Project Structure

Understanding the project structure helps when making contributions:

```
ipfs_kit_py/            # Main package directory
  ├── __init__.py       # Package initialization
  ├── ipfs_kit.py       # Main orchestrator class
  ├── ipfs.py           # Low-level IPFS (Kubo) operations
  ├── ipfs_multiformats.py  # CID and multihash handling
  ├── ipfs_fsspec.py    # FSSpec filesystem implementation for IPFS
  ├── s3_kit.py         # S3-compatible storage operations
  ├── storacha_kit.py   # Web3.Storage integration
  ├── ipfs_cluster_service.py  # Cluster service management (master role)
  ├── ipfs_cluster_ctl.py      # Cluster control operations
  ├── ipfs_cluster_follow.py   # Follower mode operations (worker role)
  ├── high_level_api.py # High-level API for common operations
  ├── api.py            # FastAPI server implementation
  ├── tiered_cache.py   # Multi-tier caching system
  ├── ai_ml_integration.py # AI/ML framework integration
  └── arrow_metadata_index.py  # Arrow-based indexing
test/                   # Test directory
  ├── __init__.py
  ├── test.py           # Test runner
  └── test_*.py         # Individual test files
docs/                   # Documentation (includes git submodules)
examples/               # Example usage patterns
py-ipld-car/            # IPLD CAR implementation (git submodule)
py-ipld-dag-pb/         # IPLD DAG-PB implementation (git submodule)
py-ipld-unixfs/         # IPLD UnixFS implementation (git submodule)
```

### Working with Git Submodules

This project uses git submodules for documentation repositories and IPLD implementations. When working with these components:

1. **Documentation Changes**: The `docs/` directory contains several submodules for external documentation repositories. If you need to modify documentation:
   - For project-specific documentation, modify files directly in `docs/`
   - For changes to submodule documentation, create a PR in the original repository
   - See the [SUBMODULES_SETUP.md](SUBMODULES_SETUP.md) file for details on all submodules

2. **IPLD Implementation Changes**: The `py-ipld-*` directories are submodules for IPLD implementations. To modify these:
   - Create PRs directly to the original repositories
   - Update the submodule references in this repository after changes are merged

3. **Submodule Updates**: To update a submodule to the latest version:
   ```bash
   # Update a specific submodule
   git submodule update --remote docs/ipfs-docs
   
   # Update all submodules
   git submodule update --remote
   
   # Commit the updates
   git add docs/ipfs-docs
   git commit -m "Update ipfs-docs submodule to latest version"
   ```

4. **Adding New Submodules**: If you need to add a new submodule:
   ```bash
   git submodule add https://github.com/example/repo.git path/to/submodule
   git commit -m "Add new submodule"
   ```

For more details on working with submodules, refer to [SUBMODULES_SETUP.md](SUBMODULES_SETUP.md).

## Release Process

The project follows semantic versioning. The release process is as follows:

1. Version bump in `setup.py` and other relevant files
2. Update CHANGELOG.md with all significant changes
3. Create a release tag
4. Build and publish to PyPI

## Community

Join the community discussions:

- GitHub Issues: For bug reports and feature requests
- GitHub Discussions: For general questions and community interactions

Thank you for contributing to ipfs_kit_py!