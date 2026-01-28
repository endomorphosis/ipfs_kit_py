# AMD64 CI/CD Setup Guide

This document describes the AMD64-specific CI/CD workflows added to support self-hosted AMD64 GitHub runners.

## Overview

The AMD64 CI/CD pipeline tests the `ipfs_kit_py` package on AMD64 architecture using both GitHub-hosted and self-hosted runners. This complements the existing ARM64 workflows and ensures compatibility across multiple architectures.

## Workflow Files

### 1. AMD64 CI/CD Pipeline (`amd64-ci.yml`)

**Purpose**: Tests the package on self-hosted AMD64 runners

**Runner Requirements**:
- Self-hosted runner with label: `[self-hosted, amd64]`
- Linux-based operating system (Ubuntu recommended)
- Python 3.8, 3.9, 3.10, or 3.11 installed
- Docker support (for Docker build job)

**Triggers**:
- Push to `main` or `develop` branches
- Pull requests to `main` branch
- Manual workflow dispatch

**Jobs**:
1. **test-amd64**: Runs comprehensive tests across multiple Python versions
   - System dependency installation
   - Python dependency installation
   - Linting and type checking
   - Unit tests
   - Build-from-source capability testing
   - Package installation testing
   - Performance tests

2. **build-docker-amd64**: Builds and tests Docker images for AMD64
   - Depends on successful completion of test-amd64
   - Builds AMD64-specific Docker image
   - Tests the built image
   - Cleans up resources

**Features**:
- Detailed system information logging
- Installation monitoring and logging
- Pre and post-installation verification
- Support for build-from-source fallback
- Comprehensive test coverage reporting
- Docker image building and testing

### 2. Multi-Architecture CI (`multi-arch-ci.yml`)

**Enhancement**: Added native AMD64 testing job

**New Job**: `test-amd64-native`
- Runs on `[self-hosted, amd64]` runners
- Tests Python 3.9, 3.10, and 3.11
- Mirrors the ARM64 native testing approach
- Includes AMD64-specific test scripts

### 3. Existing AMD64 Workflows

The repository already has:
- `amd64-python-package.yml`: GitHub-hosted AMD64 testing
- `amd64-release.yml`: AMD64-specific release pipeline

These continue to work as before and provide testing on GitHub-hosted infrastructure.

## Self-Hosted Runner Setup

### Runner Requirements

To set up a self-hosted AMD64 runner:

1. **Hardware Requirements**:
   - x86_64/AMD64 CPU architecture
   - Minimum 4GB RAM (8GB+ recommended)
   - Minimum 20GB disk space
   - Internet connectivity

2. **Software Requirements**:
   - Linux OS (Ubuntu 20.04+ recommended)
   - Python 3.8+ installed
   - Docker (for Docker build jobs)
   - Git
   - Build tools: gcc, g++, make
   - Go (optional, will be installed by scripts if needed)

3. **Runner Configuration**:
   - Add the runner to your repository
   - Apply the label `amd64` to the runner
   - Optionally apply additional labels like `linux`

### Adding a Runner

1. Go to repository Settings → Actions → Runners
2. Click "New self-hosted runner"
3. Select Linux as the OS
4. Follow the setup instructions
5. When configuring the runner, add the label `amd64`:
   ```bash
   ./config.sh --url https://github.com/endomorphosis/ipfs_kit_py --token YOUR_TOKEN --labels amd64
   ```

6. Start the runner:
   ```bash
   ./run.sh
   ```

## Monitoring and Logging

### AMD64 Monitoring Scripts

The workflow uses dedicated monitoring scripts:

1. **`scripts/ci/monitor_amd64_installation.py`**:
   - Monitors dependency installation progress
   - Logs detailed installation metrics
   - Tracks errors and warnings
   - Generates performance reports

2. **`scripts/ci/verify_amd64_dependencies.py`**:
   - Verifies system dependencies
   - Checks Python package installations
   - Validates build tool availability
   - Reports missing or incompatible dependencies

### Log Files

Logs are stored in `/tmp/amd64_install_logs/` and uploaded as artifacts:
- `apt_update.log`: System package updates
- `build_essential.log`: Build tools installation
- `build_tools.log`: Additional build tools
- `optional_packages.log`: Optional packages
- `pip_upgrade.log`: pip upgrade log
- `wheel_setuptools.log`: wheel and setuptools installation
- `requirements.log`: requirements.txt installation
- `package_install.log`: Package installation in editable mode

### Artifacts

The workflow uploads the following artifacts:
- `amd64-monitoring-logs-{python-version}`: Installation and monitoring logs
- Test results and coverage reports
- Build artifacts (wheels)

## Comparison: ARM64 vs AMD64 Workflows

| Aspect | ARM64 (`arm64-ci.yml`) | AMD64 (`amd64-ci.yml`) |
|--------|------------------------|------------------------|
| Runner Label | `[self-hosted, arm64, dgx]` | `[self-hosted, amd64]` |
| Python Versions | 3.8, 3.9, 3.10, 3.11 | 3.8, 3.9, 3.10, 3.11 |
| Monitoring Script | `monitor_arm64_installation.py` | `monitor_amd64_installation.py` |
| Verify Script | `verify_arm64_dependencies.py` | `verify_amd64_dependencies.py` |
| Docker Platform | `linux/arm64` | `linux/amd64` |
| Test Script | `test_arm64_basic.py` | `test_amd64_basic.py` |

Both workflows follow the same structure and testing methodology, ensuring consistent behavior across architectures.

## Testing Strategy

### Test Levels

1. **Syntax Checks**: flake8 for Python syntax errors
2. **Type Checking**: mypy for type annotations
3. **Code Formatting**: black and isort checks
4. **Import Tests**: Verify core package imports
5. **Unit Tests**: Run test suite excluding integration tests
6. **Binary Tests**: Check for architecture-specific binaries
7. **Build Tests**: Verify build-from-source capability
8. **Package Tests**: Build and install wheel packages
9. **Performance Tests**: Basic performance validation

### Architecture-Specific Tests

AMD64-specific tests verify:
- Binary compatibility (x86_64 architecture)
- IPFS and Lotus installer functionality
- Build-from-source support
- External dependency installation
- Docker image builds

## Integration with Multi-Arch CI

The `multi-arch-ci.yml` workflow now includes:

1. **QEMU-based testing**: Tests on amd64, arm64, armv7 using emulation
2. **Native ARM64 testing**: Uses self-hosted ARM64 runners
3. **Native AMD64 testing**: Uses self-hosted AMD64 runners (NEW)
4. **Experimental RISC-V**: Manual testing support

This provides comprehensive coverage across:
- Multiple architectures
- Multiple Python versions
- Both emulated and native environments

## Usage Examples

### Running AMD64 CI Manually

1. Go to Actions tab in GitHub
2. Select "AMD64 CI/CD Pipeline" workflow
3. Click "Run workflow"
4. Select branch and click "Run workflow"

### Debugging Failed AMD64 Builds

1. Check the workflow run logs
2. Download the `amd64-monitoring-logs-{version}` artifacts
3. Review the installation logs in `/tmp/amd64_install_logs/`
4. Check for errors in the monitoring reports
5. Look for architecture-specific issues in binary checks

### Local Testing

To test locally on an AMD64 machine:

```bash
# Clone the repository
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Run tests
pytest tests/ -v

# Run AMD64-specific checks
python -c "import platform; print(f'Architecture: {platform.machine()}')"
```

## Troubleshooting

### Common Issues

1. **Runner not picking up jobs**:
   - Verify the runner has the `amd64` label
   - Check runner status in repository settings
   - Ensure runner is online and listening

2. **Package manager locks**:
   - The workflow includes automatic lock waiting (300s timeout)
   - If persistent, check for stuck apt processes on the runner

3. **Build tool failures**:
   - Verify gcc, g++, make are installed
   - Check Go installation if building from source
   - Review build tool logs in artifacts

4. **Docker build failures**:
   - Ensure Docker is installed and running on the runner
   - Check Docker permissions for the runner user
   - Verify sufficient disk space

### Support Scripts

The repository includes helper scripts:
- `test-build-amd64.sh`: Local AMD64 build testing (if created)
- `test-full-dependencies.sh`: Full dependency testing

## Future Enhancements

Planned improvements for AMD64 workflows:

1. GPU-specific testing for AMD64 + CUDA
2. Performance benchmarking across architectures
3. Automated performance regression detection
4. Cross-compilation testing
5. Additional AMD64 runner pool for parallel testing

## Related Documentation

- [ARM64 Build Summary](ARM64_BUILD_SUMMARY.md)
- [ARM64 Testing Guide](ARM64_TESTING.md)
- [Multi-Architecture Quick Reference](MULTI_ARCH_QUICK_REF.md)
- [Workflow README](.github/workflows/README.md)
- [CI/CD Monitoring](scripts/ci/WORKFLOW_MONITORING.md)

## Contributing

When adding new features or tests that may be architecture-specific:

1. Test on both AMD64 and ARM64 workflows
2. Update monitoring scripts if needed
3. Document architecture-specific behavior
4. Add appropriate conditional logic for architecture differences
5. Update this documentation

## Questions and Support

For questions about AMD64 CI/CD setup:
- Review workflow logs and artifacts
- Check the monitoring scripts in `scripts/ci/`
- Refer to the ARM64 documentation for parallel examples
- Open an issue with `ci/cd` and `amd64` labels
