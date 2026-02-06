# GitHub Actions Runner Scripts Guide

Complete suite of scripts for managing GitHub Actions self-hosted runners on your AMD64 machine.

## 📦 Available Scripts

### 1. **setup-github-runner.sh** - Main Installation Script

Sets up a single GitHub Actions runner on your machine.

```bash
./scripts/setup-github-runner.sh
```

**What it does:**
- ✅ Detects your system architecture (AMD64/ARM64)
- ✅ Downloads the latest runner package
- ✅ Configures runner with appropriate labels (`self-hosted,linux,x64,amd64`)
- ✅ Installs as a systemd service
- ✅ Automatically starts the runner

**Required:**
- GitHub Personal Access Token with `repo` and `workflow` scopes

**Interactive prompts:**
- GitHub token (if not set via `GITHUB_TOKEN` env var)
- Confirmation of settings

---

### 2. **setup-multiple-runners.sh** - Multiple Runner Setup

Create multiple runner instances on the same machine for parallel job execution.

```bash
./scripts/setup-multiple-runners.sh
```

**What it does:**
- ✅ Creates 1-5 runner instances
- ✅ Each runner has a unique name
- ✅ All runners are configured and started automatically
- ✅ Useful for running multiple CI/CD jobs simultaneously

**Use case:** If you have workflows that trigger frequently, multiple runners can handle them in parallel.

---

### 3. **list-runners.sh** - View All Runners

List all runners (local and GitHub registered).

```bash
./scripts/list-runners.sh
```

**Shows:**
- Local runner information
- Service status (running/stopped)
- All runners registered in GitHub (if token provided)
- Runner details (ID, OS, status, busy state, labels)

**With GitHub token:**
```bash
GITHUB_TOKEN="your_token" ./scripts/list-runners.sh
```

---

### 4. **monitor-runner.sh** - Monitor Runner Status

Real-time monitoring of your runner with multiple modes.

```bash
./scripts/monitor-runner.sh
```

**Monitoring modes:**
1. **One-time status check** - Quick snapshot
2. **Live log monitoring** - Real-time logs (like `tail -f`)
3. **Continuous monitoring** - Refreshes every 5 seconds

**Shows:**
- Runner information
- Service status
- System resources (CPU, memory, disk)
- Active workflow jobs
- Recent logs

---

### 5. **restart-runner.sh** - Restart Runner

Safely restart the runner service.

```bash
./scripts/restart-runner.sh
```

**Use when:**
- Runner becomes unresponsive
- After system updates
- Configuration changes require restart

---

### 6. **remove-runner.sh** - Remove Runner

Completely remove a runner from your system and GitHub.

```bash
./scripts/remove-runner.sh
```

**What it does:**
- ✅ Stops the runner service
- ✅ Uninstalls the systemd service
- ✅ Removes runner from GitHub (if token provided)
- ✅ Deletes runner directory

**With GitHub token (automatic removal):**
```bash
GITHUB_TOKEN="your_token" ./scripts/remove-runner.sh
```

**Without token:** Script will prompt you to manually remove from GitHub UI.

---

## 🚀 Quick Start Guide

### First Time Setup

1. **Get your GitHub token:**
   ```bash
   # Go to: https://github.com/settings/tokens
   # Create token with: repo, workflow scopes
   ```

2. **Set environment variable (optional but recommended):**
   ```bash
   export GITHUB_TOKEN="ghp_your_token_here"
   ```

3. **Run the setup:**
   ```bash
   ./scripts/setup-github-runner.sh
   ```

4. **Verify it's working:**
   ```bash
   ./scripts/list-runners.sh
   ```

### Daily Operations

**Check runner status:**
```bash
./scripts/monitor-runner.sh
# Choose option 1 for quick check
```

**View live logs:**
```bash
./scripts/monitor-runner.sh
# Choose option 2 for live logs
```

**Restart if needed:**
```bash
./scripts/restart-runner.sh
```

---

## 🔧 Environment Variables

All scripts support these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | Your GitHub PAT | (prompted if not set) |
| `GITHUB_REPO` | Repository to register runner | `endomorphosis/ipfs_kit_py` |
| `RUNNER_DIR` | Runner installation directory | `$HOME/actions-runner` |
| `RUNNER_NAME` | Custom runner name | `hostname-arch-runner` |
| `RUNNER_LABELS` | Custom labels | `self-hosted,linux,x64,amd64` |
| `RUNNER_VERSION` | Runner version | `2.311.0` |

**Example with custom settings:**
```bash
export GITHUB_TOKEN="your_token"
export RUNNER_NAME="my-build-server"
export RUNNER_LABELS="self-hosted,linux,x64,amd64,build,fast"

./scripts/setup-github-runner.sh
```

---

## 📊 Understanding Runner Labels

Your AMD64 runner is automatically configured with these labels:
- `self-hosted` - Identifies as self-hosted (not GitHub-hosted)
- `linux` - Linux operating system
- `x64` - x86_64 architecture
- `amd64` - AMD64 specific (matches your workflows)

**How workflows use these:**
```yaml
jobs:
  my-job:
    runs-on: [self-hosted, amd64]  # Uses your runner
```

---

## 🎯 Workflow Integration

After setup, your workflows will automatically use the runner:

### Current Workflows That Will Use Your Runner

1. **`amd64-ci.yml`** - AMD64 CI/CD Pipeline
   - Runs on: `[self-hosted, amd64]` ✅
   
2. **`multi-arch-ci.yml`** - Multi-Architecture CI/CD
   - Job: `test-amd64-native`
   - Runs on: `[self-hosted, amd64]` ✅

### Test Your Runner

Push a commit or manually trigger the workflow:
```bash
# From GitHub UI:
# Actions → AMD64 CI/CD Pipeline → Run workflow

# Or push to your branch:
git push origin main
```

---

## 🔍 Troubleshooting

### Runner Not Showing in GitHub

1. **Check if service is running:**
   ```bash
   sudo ~/actions-runner/svc.sh status
   ```

2. **Check logs:**
   ```bash
   journalctl -u actions.runner.* -n 50
   ```

3. **Restart runner:**
   ```bash
   ./scripts/restart-runner.sh
   ```

### Jobs Not Picking Up Runner

1. **Verify labels match:**
   ```bash
   ./scripts/list-runners.sh
   ```
   
2. **Check runner capacity:**
   - Runners handle ONE job at a time
   - Set up multiple runners if needed:
   ```bash
   ./scripts/setup-multiple-runners.sh
   ```

### Runner Goes Offline

**Common causes:**
- System reboot (service should auto-start)
- Network issues
- Disk space full

**Fix:**
```bash
# Check disk space
df -h

# Restart runner
./scripts/restart-runner.sh

# Check status
./scripts/monitor-runner.sh
```

### Permission Errors

```bash
# Fix ownership
sudo chown -R $USER:$USER ~/actions-runner

# Fix script permissions
chmod +x ~/actions-runner/*.sh
```

---

## 🔐 Security Best Practices

1. **Token Management:**
   ```bash
   # Store token in environment (don't commit!)
   echo 'export GITHUB_TOKEN="your_token"' >> ~/.bashrc
   source ~/.bashrc
   
   # Or use a secret manager
   ```

2. **Runner Isolation:**
   - Don't run on machines with sensitive data
   - Use dedicated build machines when possible
   - Monitor resource usage

3. **Regular Updates:**
   ```bash
   # Runner will auto-update, but check occasionally
   cd ~/actions-runner
   ./config.sh --version
   ```

4. **Monitor Activity:**
   ```bash
   # Regular monitoring
   ./scripts/monitor-runner.sh
   ```

---

## 📚 Additional Resources

### GitHub Documentation
- [Self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Runner security](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)

### Repository Documentation
- [Full Setup Guide](docs/GITHUB_RUNNER_SETUP.md) - Comprehensive documentation
- [Quick Start](RUNNER_QUICK_START.md) - 5-minute setup guide
- [Workflow Status Report](WORKFLOW_STATUS_REPORT.md) - Current workflow analysis

### Support
- View runners: https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners
- Check workflow runs: https://github.com/endomorphosis/ipfs_kit_py/actions

---

## 📝 Script Maintenance

All scripts are located in `scripts/` directory:

```
scripts/
├── setup-github-runner.sh       # Main setup
├── setup-multiple-runners.sh    # Multiple runners
├── list-runners.sh              # List runners
├── monitor-runner.sh            # Monitor status
├── restart-runner.sh            # Restart runner
└── remove-runner.sh             # Remove runner
```

**Keep scripts updated:**
```bash
# Scripts are in git, just pull updates
git pull origin main

# Make sure they're executable
chmod +x scripts/*.sh
```

---

## 🎉 Quick Reference

```bash
# Setup new runner
./scripts/setup-github-runner.sh

# Check status
./scripts/list-runners.sh

# Monitor
./scripts/monitor-runner.sh

# Restart
./scripts/restart-runner.sh

# Remove
./scripts/remove-runner.sh

# Multiple runners
./scripts/setup-multiple-runners.sh
```

---

**Questions?** Check the full documentation in `docs/GITHUB_RUNNER_SETUP.md`
