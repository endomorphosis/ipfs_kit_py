# ARM64 CI/CD Testing

This document describes the ARM64 testing infrastructure for ipfs_kit_py.

## Overview

The ARM64 CI/CD pipeline validates that the package builds correctly and tests pass on ARM64 architecture, which is increasingly important for:
- Apple Silicon (M1/M2/M3) Macs
- ARM-based cloud instances (AWS Graviton, etc.)
- NVIDIA ARM-based systems (DGX, Jetson)
- Raspberry Pi and other ARM development boards

## Self-Hosted Runner Setup

The ARM64 CI runs on a self-hosted GitHub Actions runner configured on an NVIDIA DGX Spark GB10 system.

### Runner Labels
- `self-hosted`
- `arm64`
- `dgx`

## Workflow Configuration

The ARM64 workflow (`.github/workflows/arm64-ci.yml`) includes:

### Key Features
1. **Multi-Python Version Testing**: Tests against Python 3.8, 3.9, 3.10, and 3.11
2. **Network Resilience**: Uses increased timeouts and retries for pip operations
3. **Build Isolation Bypass**: Uses `--no-isolation` flag to avoid network timeout issues
4. **Comprehensive Testing**:
   - Linting (flake8)
   - Type checking (mypy)
   - Code formatting (black, isort)
   - Unit tests with coverage
   - Package installation verification
   - Import validation

### Build Process

The workflow builds the package using:
```bash
python -m build --wheel --no-isolation
```

This approach:
- Avoids network timeouts in isolated build environments
- Works reliably on self-hosted runners
- Produces a wheel package for testing

## Local Testing

### Quick Test Script

A standalone test script is provided: `test-build-arm64.sh`

Run it with:
```bash
./test-build-arm64.sh
```

This script:
1. Validates the pyproject.toml configuration
2. Builds a wheel package
3. Creates a test virtual environment
4. Installs the wheel
5. Tests package import
6. Runs smoke tests

### Smoke Tests

Basic smoke tests are in `tests/test_arm64_basic.py`:
- Python version validation
- Architecture detection
- Package import verification
- Version checking
- Core module availability

Run smoke tests:
```bash
pytest tests/test_arm64_basic.py -v
```

## Troubleshooting

### Network Timeouts

If you encounter network timeouts during package installation:

1. **Increase pip timeout**:
   ```bash
   pip install --timeout=300 --retries=5 <package>
   ```

2. **Use local wheel**:
   ```bash
   python -m build --wheel --no-isolation
   pip install dist/*.whl
   ```

3. **Install without dependencies** (for testing):
   ```bash
   pip install --no-deps dist/*.whl
   ```

### Build Failures

Common issues and solutions:

1. **pyproject.toml validation error**:
   - Ensure license field uses correct format: `license = {text = "AGPL-3.0-or-later"}`
   - Validate with: `python setup.py --version`

2. **Missing build dependencies**:
   - Install build tools: `pip install build wheel setuptools`
   - Use system packages: `sudo apt-get install build-essential python3-dev`

3. **Large wheel size**:
   - The wheel is ~287MB due to included data files and templates
   - This is expected for this package

## Performance Considerations

ARM64 systems may have different performance characteristics:
- Different CPU architecture affects computation speed
- Memory bandwidth differences
- GPU acceleration (on systems like NVIDIA Jetson/DGX)

The workflow includes a performance test placeholder for ARM64-specific benchmarks.

## Integration with Main CI/CD

The ARM64 pipeline runs:
- On pushes to `main` and `develop` branches
- On pull requests to `main`

It runs in parallel with x86_64 CI to ensure cross-platform compatibility.

## Future Improvements

Potential enhancements:
1. Add ARM64-specific performance benchmarks
2. Test GPU acceleration on ARM64 (CUDA on Jetson/DGX)
3. Add Docker image building for ARM64
4. Cross-compilation testing
5. Add tests for platform-specific features

## Monitoring

GitHub Actions provides:
- Build logs for each step
- Test coverage reports (uploaded to Codecov)
- Job summaries with system information
- Artifact storage for build outputs

Check the Actions tab in GitHub for detailed results.
