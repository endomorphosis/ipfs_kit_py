# GitHub Actions Self-Hosted Runner Setup for ARM64 Nvidia DGX

This guide helps you set up a GitHub Actions self-hosted runner on your ARM64 Nvidia DGX Spark GB10 computer to enable CI/CD workflows for ARM64 architecture testing.

## 🚀 Quick Setup

### Step 1: Configure the Runner

The runner files are already downloaded and extracted in `~/actions-runner/`. To configure:

```bash
cd ~/actions-runner
./setup-runner.sh
```

This script will:
1. Guide you through getting a registration token from GitHub
2. Configure the runner with appropriate labels (arm64, dgx, nvidia, spark)
3. Optionally install it as a systemd service

### Step 2: Get GitHub Registration Token

1. Go to: https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners
2. Click "New self-hosted runner"
3. Select "Linux" and "ARM64"
4. Copy the token from the configuration command
5. Paste it when prompted by the setup script

### Step 3: Manage the Runner

Use the runner manager script for easy management:

```bash
# Check status
runner-manager status

# Start/stop/restart
runner-manager start
runner-manager stop
runner-manager restart

# View logs
runner-manager logs

# Install as service
runner-manager install

# Update runner
runner-manager update
```

## 📁 Files Created

### GitHub Actions Workflows
- `.github/workflows/arm64-ci.yml` - Dedicated ARM64 testing pipeline
- `.github/workflows/multi-arch-ci.yml` - Multi-architecture testing (x86 + ARM64)

### Runner Management Scripts
- `~/actions-runner/setup-runner.sh` - Initial setup script
- `~/actions-runner/runner-manager.sh` - Runner management utilities
- `/usr/local/bin/runner-manager` - Global symlink for runner management

## 🔧 Runner Configuration

**Runner Name**: `arm64-dgx-spark`
**Labels**: `arm64`, `dgx`, `nvidia`, `spark`, `self-hosted`
**Repository**: `endomorphosis/ipfs_kit_py`

## 📋 Workflow Features

### ARM64-Specific CI Pipeline (`arm64-ci.yml`)
- ✅ Multi-Python version testing (3.8, 3.9, 3.10, 3.11)
- ✅ System information display (architecture, CPU, memory, GPU)
- ✅ Code linting and formatting checks
- ✅ Type checking with MyPy
- ✅ Unit tests with coverage reporting
- ✅ Package installation testing
- ✅ Docker ARM64 build testing
- ✅ Performance benchmarking

### Multi-Architecture CI (`multi-arch-ci.yml`)
- ✅ Parallel testing on both x86-64 (GitHub-hosted) and ARM64 (self-hosted)
- ✅ Conditional ARM64 testing (triggered on push or PR with 'test-arm64' label)
- ✅ Compatibility report generation

## 🎯 Using the Runner in Workflows

To target your self-hosted ARM64 runner, use:

```yaml
runs-on: [self-hosted, arm64, dgx]
```

Or for more specific targeting:
```yaml
runs-on: [self-hosted, arm64, nvidia, spark]
```

## 🔍 Monitoring

### Check Runner Status
```bash
runner-manager status
```

### View Logs
```bash
runner-manager logs
# or follow in real-time:
sudo journalctl -u actions.runner.endomorphosis-ipfs_kit_py.arm64-dgx-spark.service -f
```

### GitHub Web Interface
Monitor runner activity at:
https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners

## 🛠 Troubleshooting

### Runner Not Appearing Online
1. Check service status: `runner-manager status`
2. Check logs: `runner-manager logs`
3. Restart service: `runner-manager restart`

### Configuration Issues
```bash
runner-manager config  # Reconfigure runner
```

### Update Runner
```bash
runner-manager update  # Update to latest version
```

### Remove Runner
```bash
cd ~/actions-runner
sudo ./svc.sh stop
./config.sh remove
```

## 🧪 Testing the Setup

1. **Push a commit** to the main branch to trigger workflows
2. **Create a PR** and add the `test-arm64` label to trigger ARM64 testing
3. **Check Actions tab** in your GitHub repository to see results

## 💡 Benefits

- ✅ **Native ARM64 Testing**: Validate compatibility on actual ARM64 hardware
- ✅ **GPU Acceleration**: Leverage Nvidia GPU capabilities for AI/ML workloads  
- ✅ **Performance Benchmarking**: Test real-world performance on target hardware
- ✅ **Cost Effective**: Use your own hardware instead of cloud runners
- ✅ **Full Control**: Customize environment and dependencies as needed

## 🔗 Next Steps

1. **Customize workflows** in `.github/workflows/` for your specific needs
2. **Add performance benchmarks** for critical code paths
3. **Configure notifications** for build failures
4. **Add deployment steps** for ARM64 releases
5. **Set up artifact storage** for build outputs

## 📞 Support

For issues with the runner setup, check the logs and GitHub Actions documentation:
- https://docs.github.com/en/actions/hosting-your-own-runners
- https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners