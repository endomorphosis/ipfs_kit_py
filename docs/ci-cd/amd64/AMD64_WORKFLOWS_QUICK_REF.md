# AMD64 Workflows Quick Reference

Quick reference guide for AMD64 CI/CD workflows in the ipfs_kit_py repository.

## Workflow Files

| Workflow | File | Runner | When It Runs |
|----------|------|--------|--------------|
| AMD64 CI/CD | `amd64-ci.yml` | Self-hosted AMD64 | Push to main/develop, PRs, manual |
| AMD64 Python Package | `amd64-python-package.yml` | GitHub-hosted (ubuntu-latest) | Push/PR to main/develop |
| AMD64 Release | `amd64-release.yml` | GitHub-hosted (ubuntu-latest) | Tagged releases (amd64-v*) |
| Multi-Arch CI (AMD64) | `multi-arch-ci.yml` | Self-hosted AMD64 | Push to main/develop, manual |

## Self-Hosted Runner Setup

### Quick Setup
```bash
# Download and configure runner
./config.sh --url https://github.com/endomorphosis/ipfs_kit_py \
  --token YOUR_TOKEN \
  --labels amd64

# Start the runner
./run.sh
```

### Required Labels
- Primary: `amd64`
- Optional: `self-hosted`, `linux`

## Workflow Job Structure

### amd64-ci.yml Jobs

```
test-amd64 (Python 3.8, 3.9, 3.10, 3.11)
├── System info collection
├── Dependency installation
├── Linting and type checking
├── Unit tests
├── Build-from-source tests
├── Package building
└── Upload artifacts

build-docker-amd64
├── Docker image build (linux/amd64)
├── Image testing
└── Cleanup
```

### multi-arch-ci.yml AMD64 Job

```
test-amd64-native (Python 3.9, 3.10, 3.11)
├── System dependencies
├── Virtual environment setup
├── Package installation
├── Test execution
└── Report generation
```

## Key Features

### Testing
- ✅ Python 3.8, 3.9, 3.10, 3.11 support
- ✅ Linting (flake8, black, isort)
- ✅ Type checking (mypy)
- ✅ Unit tests (pytest)
- ✅ Build-from-source capability
- ✅ Docker image building

### Monitoring
- 📊 Installation progress tracking
- 📝 Detailed logging to `/tmp/amd64_install_logs/`
- 📦 Artifact uploads (logs, test results)
- 📈 Performance metrics

### Build Tools
- gcc, g++, make
- Go (installed on-demand)
- Docker
- Python build tools

## Monitoring Scripts

### monitor_amd64_installation.py
```bash
# Monitors installation process
python scripts/ci/monitor_amd64_installation.py
```

**Purpose**: Track dependency installation, collect metrics, log errors

**Outputs**: 
- JSON metrics in `/tmp/amd64_monitor/`
- Installation logs in `/tmp/amd64_install_logs/`

### verify_amd64_dependencies.py
```bash
# Verify dependencies
python scripts/ci/verify_amd64_dependencies.py
```

**Purpose**: Check system dependencies, validate installations

**Checks**:
- System packages (gcc, make, git)
- Python packages
- Build tools
- Binary compatibility

## Common Commands

### Local Testing
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Run tests
pytest tests/ -v --tb=short

# Check architecture
python -c "import platform; print(f'Arch: {platform.machine()}')"
```

### Docker Testing
```bash
# Build AMD64 image
docker buildx build --platform linux/amd64 -t ipfs-kit-py:amd64 .

# Test image
docker run --rm ipfs-kit-py:amd64 python -c "import ipfs_kit_py"
```

### Manual Workflow Trigger
1. Go to Actions → AMD64 CI/CD Pipeline
2. Click "Run workflow"
3. Select branch
4. Click "Run workflow"

## Log Locations

### Installation Logs
```
/tmp/amd64_install_logs/
├── apt_update.log
├── build_essential.log
├── build_tools.log
├── optional_packages.log
├── pip_upgrade.log
├── wheel_setuptools.log
├── requirements.log
└── package_install.log
```

### Monitoring Data
```
/tmp/amd64_monitor/
├── metrics.json
├── installation_timeline.json
└── system_info.json
```

## Artifacts

| Artifact | Contains |
|----------|----------|
| `amd64-monitoring-logs-{version}` | Installation and monitoring logs |
| `amd64-test-results-{version}` | Test results and coverage |
| `amd64-python-packages` | Built wheel and source distributions |

## Troubleshooting

### Issue: Runner not picking up jobs
**Solution**: 
- Check runner has `amd64` label
- Verify runner is online: Settings → Actions → Runners
- Check runner logs

### Issue: Package manager locks
**Solution**: 
- Workflow waits 300s automatically
- Check for stuck processes: `ps aux | grep apt`
- Manually kill if needed: `sudo killall apt apt-get`

### Issue: Build failures
**Solution**:
- Check build tool logs in artifacts
- Verify gcc/g++/make: `which gcc g++ make`
- Install missing tools: `sudo apt-get install build-essential`

### Issue: Docker build fails
**Solution**:
- Verify Docker running: `docker info`
- Check disk space: `df -h`
- Review Docker logs: `journalctl -u docker`

## Performance Optimization

### Caching
```yaml
- name: Cache pip dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### Parallel Testing
- Multiple Python versions run in parallel
- Matrix strategy splits workload
- Self-hosted runners can run concurrent jobs

### Resource Limits
- CPU: Uses all available cores
- Memory: Configurable per runner
- Timeout: 30 minutes per job (default)

## Integration Points

### With ARM64 Workflows
- Mirrors `arm64-ci.yml` structure
- Uses similar monitoring scripts
- Shared test infrastructure

### With Multi-Arch
- Part of `multi-arch-ci.yml`
- Native testing alongside ARM64
- Combined reporting

### With Release Pipelines
- Can trigger `amd64-release.yml`
- Builds architecture-specific packages
- Creates GitHub releases

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_PATH` | Path additions | Updated by workflow |
| `PYTHON_VERSION` | Python version | Matrix value |

## Best Practices

1. **Test Locally First**: Run tests on AMD64 machine before pushing
2. **Monitor Resources**: Check runner CPU/memory usage
3. **Review Logs**: Always check monitoring logs for warnings
4. **Keep Updated**: Regularly update runner software
5. **Clean Up**: Workflow includes cleanup steps

## Related Documentation

- [AMD64 CI Setup Guide](AMD64_CI_SETUP.md) - Detailed setup instructions
- [ARM64 Quick Reference](../../deployment/arm64/ARM64_MONITORING_QUICK_REF.md) - ARM64 equivalent
- [Multi-Arch Quick Reference](../../deployment/multi-arch/MULTI_ARCH_QUICK_REF.md) - Multi-arch overview
- [Workflow README](../../../.github/workflows/README.md) - All workflows

## Quick Checks

### Is AMD64 runner working?
```bash
# On runner machine
./run.sh status
```

### Is workflow enabled?
- Go to Settings → Actions → Workflows
- Check "AMD64 CI/CD Pipeline" is enabled

### View recent runs
- Actions → AMD64 CI/CD Pipeline
- Check run history and status

## Support

For issues or questions:
1. Check workflow logs and artifacts
2. Review monitoring data
3. Consult [AMD64_CI_SETUP.md](AMD64_CI_SETUP.md)
4. Open issue with labels: `ci/cd`, `amd64`
