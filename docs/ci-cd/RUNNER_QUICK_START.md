# GitHub Actions Runner - Quick Start

## 🚀 Fast Setup (5 minutes)

### Step 1: Get Your GitHub Token

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` + `workflow` + `admin:org` (for manage_runners)
4. Copy the token

### Step 2: Run the Setup Script

```bash
cd /home/barberb/ipfs_kit_py
./scripts/setup-github-runner.sh
```

When prompted:
- **Repository**: `endomorphosis/ipfs_kit_py`
- **Token**: Paste your token from Step 1

### Step 3: Verify

Check your runner at:
https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners

## 📋 Current Runner Configuration

Your workflows already use self-hosted runners:

```yaml
runs-on: [self-hosted, amd64]  # amd64-ci.yml
runs-on: [self-hosted, arm64]  # arm64 workflows
```

### Recommended Runner Setup

For your repository, you should set up:

1. **AMD64 Runner** (x86_64)
   - Labels: `self-hosted,linux,x64,amd64`
   - For: AMD64 CI/CD pipeline

2. **ARM64 Runner** (aarch64) - Optional
   - Labels: `self-hosted,linux,arm64`
   - For: ARM64 testing

## 🔧 Common Commands

```bash
# Check status
sudo ~/actions-runner/svc.sh status

# View logs
journalctl -u actions.runner.* -f

# Restart
sudo ~/actions-runner/svc.sh stop
sudo ~/actions-runner/svc.sh start
```

## ⚠️ Important Notes

1. **Security**: Only use for private repos (your repo is private ✓)
2. **Resources**: Ensure sufficient disk space (10GB+)
3. **Network**: Runner needs access to github.com

## 📚 Full Documentation

See the [complete GitHub Actions runner setup guide](../deployment/ci-cd/GITHUB_RUNNER_SETUP.md) for:
- Detailed setup instructions
- Troubleshooting guide
- Security best practices
- Advanced configuration

## 🆘 Troubleshooting

**Runner not showing up?**
```bash
sudo systemctl status actions.runner.*
journalctl -u actions.runner.* -n 50
```

**Jobs not running?**
- Check labels match in workflow file
- Verify runner is online in GitHub UI
- Ensure runner has capacity (not already running a job)

**Permission errors?**
```bash
sudo chown -R $USER:$USER ~/actions-runner
chmod +x ~/actions-runner/*.sh
```

---

Need help? Check the full guide or create an issue!
