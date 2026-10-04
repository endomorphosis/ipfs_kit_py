# GitHub Actions Self-Hosted Runner Setup Guide

This guide will help you set up a GitHub Actions self-hosted runner for your repository.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Setup](#quick-setup)
3. [Manual Setup](#manual-setup)
4. [Runner Management](#runner-management)
5. [Troubleshooting](#troubleshooting)
6. [Security Considerations](#security-considerations)

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended), macOS, or Windows
- **Architecture**: x64, ARM64, or ARM
- **Memory**: At least 2GB RAM (4GB+ recommended)
- **Disk Space**: At least 10GB free space
- **Network**: Stable internet connection

### GitHub Requirements
- Repository with admin access
- Personal Access Token (PAT) with the following scopes:
  - `repo` (Full control of private repositories)
  - `admin:org` (if using organization-level runners)

### Creating a GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a descriptive name (e.g., "Actions Runner Token")
4. Select scopes:
   - ✅ `repo` (all sub-scopes)
   - ✅ `workflow`
   - ✅ `admin:org` → `manage_runners:org` (for organization runners)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again!)

## Quick Setup

### Using the Automated Script

We provide an automated setup script that handles everything:

```bash
# Make the script executable
chmod +x scripts/setup-github-runner.sh

# Run the script
./scripts/setup-github-runner.sh
```

You'll be prompted for:
1. Your GitHub repository (format: `owner/repo`)
2. Your GitHub Personal Access Token

The script will:
- ✅ Detect your system architecture automatically
- ✅ Install required dependencies
- ✅ Download the latest runner package
- ✅ Configure the runner with appropriate labels
- ✅ Install the runner as a systemd service
- ✅ Start the runner automatically

### Environment Variables (Optional)

You can set these environment variables before running the script:

```bash
export GITHUB_REPO="owner/repo"
export GITHUB_TOKEN="your_github_token"
export RUNNER_NAME="my-custom-runner-name"
export RUNNER_LABELS="self-hosted,linux,x64,custom-label"
export RUNNER_VERSION="2.311.0"
export RUNNER_DIR="$HOME/actions-runner"

./scripts/setup-github-runner.sh
```

## Manual Setup

### Step 1: Install Dependencies

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y curl jq libssl-dev libffi-dev

# macOS
brew install curl jq
```

### Step 2: Create Runner Directory

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
```

### Step 3: Download Runner Package

Check the [latest release](https://github.com/actions/runner/releases) and download:

```bash
# For Linux x64
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

# For Linux ARM64
curl -o actions-runner-linux-arm64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-arm64-2.311.0.tar.gz

# Extract
tar xzf ./actions-runner-linux-*.tar.gz
```

### Step 4: Get Registration Token

You need a registration token from GitHub. Two methods:

#### Method A: Via GitHub UI
1. Go to your repository
2. Settings → Actions → Runners → New self-hosted runner
3. Copy the token from the configuration command

#### Method B: Via API
```bash
export GITHUB_REPO="owner/repo"
export GITHUB_TOKEN="your_github_token"

curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$GITHUB_REPO/actions/runners/registration-token
```

### Step 5: Configure the Runner

```bash
./config.sh \
  --url https://github.com/owner/repo \
  --token YOUR_REGISTRATION_TOKEN \
  --name my-runner \
  --labels self-hosted,linux,x64 \
  --unattended
```

### Step 6: Install as Service

```bash
# Install
sudo ./svc.sh install

# Start
sudo ./svc.sh start

# Check status
sudo ./svc.sh status
```

## Runner Management

### Check Runner Status

```bash
# Via systemd
sudo systemctl status actions.runner.*

# Via runner script
cd ~/actions-runner
sudo ./svc.sh status

# View logs
journalctl -u actions.runner.* -f
```

### Start/Stop/Restart Runner

```bash
cd ~/actions-runner

# Stop
sudo ./svc.sh stop

# Start
sudo ./svc.sh start

# Restart
sudo ./svc.sh stop
sudo ./svc.sh start
```

### Remove Runner

```bash
cd ~/actions-runner

# Stop the service
sudo ./svc.sh stop

# Uninstall the service
sudo ./svc.sh uninstall

# Remove the runner from GitHub
./config.sh remove --token YOUR_REMOVAL_TOKEN
```

### Update Runner

```bash
cd ~/actions-runner

# Stop the service
sudo ./svc.sh stop

# Download new version
curl -o actions-runner-linux-x64-NEW_VERSION.tar.gz -L \
  https://github.com/actions/runner/releases/download/vNEW_VERSION/actions-runner-linux-x64-NEW_VERSION.tar.gz

# Extract
tar xzf ./actions-runner-linux-x64-NEW_VERSION.tar.gz

# Start the service
sudo ./svc.sh start
```

## Configuring Workflows to Use Your Runner

Update your workflow files to use the self-hosted runner:

```yaml
jobs:
  my-job:
    # Use specific labels to target your runner
    runs-on: [self-hosted, linux, x64]
    
    # Or use just self-hosted
    runs-on: self-hosted
    
    steps:
      - uses: actions/checkout@v4
      # Your job steps...
```

### Current Repository Configuration

Your `amd64-ci.yml` already uses:
```yaml
runs-on: [self-hosted, amd64]
```

Make sure your runner has the `amd64` label when configuring it.

## Troubleshooting

### Runner Not Appearing in GitHub

1. **Check service status:**
   ```bash
   sudo systemctl status actions.runner.*
   ```

2. **View logs:**
   ```bash
   journalctl -u actions.runner.* -f
   ```

3. **Check network connectivity:**
   ```bash
   curl -I https://github.com
   ```

4. **Verify token permissions:**
   - Ensure your PAT has `repo` and `admin:org` scopes
   - Token might be expired

### Runner Goes Offline

1. **Check if service is running:**
   ```bash
   sudo ./svc.sh status
   ```

2. **Restart the service:**
   ```bash
   sudo ./svc.sh stop
   sudo ./svc.sh start
   ```

3. **Check system resources:**
   ```bash
   df -h          # Disk space
   free -h        # Memory
   top            # CPU usage
   ```

### Jobs Not Picking Up Runner

1. **Verify labels match:**
   - Check runner labels in GitHub UI (Settings → Actions → Runners)
   - Ensure workflow `runs-on` matches runner labels

2. **Check runner capacity:**
   - Runners can only handle one job at a time by default
   - Add more runners for parallel execution

### Permission Errors

```bash
# Fix ownership
sudo chown -R $USER:$USER ~/actions-runner

# Fix permissions
chmod +x ~/actions-runner/*.sh
```

## Security Considerations

### ⚠️ Important Security Notes

1. **Never use self-hosted runners for public repositories**
   - Public repos can run malicious code on your runner
   - Use GitHub-hosted runners for public repos

2. **Isolate runners**
   - Run in a VM or container
   - Don't run on machines with sensitive data

3. **Token Security**
   - Store tokens securely (use environment variables)
   - Rotate tokens regularly
   - Never commit tokens to git

4. **Network Security**
   - Use firewall rules to restrict outbound connections
   - Monitor network traffic

5. **Regular Updates**
   - Keep runner software updated
   - Update system packages regularly

6. **Resource Limits**
   - Set resource limits (CPU, memory, disk)
   - Monitor resource usage

### Recommended Security Setup

```bash
# Create dedicated user for runner
sudo useradd -m -s /bin/bash github-runner

# Install runner as this user
sudo su - github-runner
# ... follow installation steps ...

# Set up resource limits
sudo nano /etc/security/limits.conf
# Add:
# github-runner soft nproc 100
# github-runner hard nproc 200
# github-runner soft nofile 1024
# github-runner hard nofile 2048
```

## Advanced Configuration

### Multiple Runners on Same Machine

```bash
# Runner 1
mkdir -p ~/runner1 && cd ~/runner1
# ... configure with name "runner1" ...

# Runner 2
mkdir -p ~/runner2 && cd ~/runner2
# ... configure with name "runner2" ...
```

### Custom Runner Groups (Organization)

For organization-level runners:

1. Go to Organization Settings → Actions → Runner groups
2. Create a new runner group
3. Assign repositories to the group
4. Configure runner with group token

### Running in Docker

```dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    curl jq libssl-dev libffi-dev sudo

# Add runner user
RUN useradd -m github-runner

# Download and configure runner
USER github-runner
WORKDIR /home/github-runner
RUN mkdir actions-runner && cd actions-runner && \
    curl -o actions-runner.tar.gz -L \
    https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz && \
    tar xzf ./actions-runner.tar.gz

# Configure and run
CMD cd /home/github-runner/actions-runner && \
    ./config.sh --url $GITHUB_URL --token $RUNNER_TOKEN --unattended && \
    ./run.sh
```

## Monitoring and Metrics

### View Runner Metrics

```bash
# CPU and Memory usage
ps aux | grep Runner.Listener

# Disk usage
du -sh ~/actions-runner

# Network activity
sudo nethogs
```

### Log Rotation

```bash
# Set up logrotate
sudo nano /etc/logrotate.d/github-runner

# Add:
/home/*/actions-runner/_diag/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

## Resources

- [Official GitHub Actions Runner Documentation](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Runner Releases](https://github.com/actions/runner/releases)
- [Actions Runner Security](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review runner logs: `journalctl -u actions.runner.* -f`
3. Check GitHub Actions status: https://www.githubstatus.com/
4. Open an issue in the repository

---

**Last Updated**: 2025-10-19
**Runner Version**: 2.311.0 (check for latest version)
