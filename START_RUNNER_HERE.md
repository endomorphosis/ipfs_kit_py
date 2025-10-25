# 🚀 Quick Start: Set Up Your GitHub Actions Runner

## ⚡ Fastest Way (Single Command)

```bash
./scripts/setup-github-runner.sh
```

You'll be prompted for your GitHub Personal Access Token (PAT).

---

## 📋 Step-by-Step

### 1. Get Your GitHub Token

Go to: https://github.com/settings/tokens

- Click "Generate new token (classic)"
- Name it: `GitHub Actions Runner`
- Select scopes: ✅ `repo` + ✅ `workflow`
- Click "Generate token"
- **Copy the token** (you won't see it again!)

### 2. Run the Setup Script

```bash
cd /home/barberb/ipfs_kit_py
./scripts/setup-github-runner.sh
```

When prompted, paste your token.

### 3. Verify It's Running

```bash
./scripts/list-runners.sh
```

Or check GitHub: https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners

---

## ✅ What This Does

Your runner will be configured with:
- **Name**: `workstation-x86_64-runner` (or similar)
- **Labels**: `self-hosted`, `linux`, `x64`, `amd64`
- **Installed as**: systemd service (auto-starts on reboot)

This matches your workflows:
- `amd64-ci.yml` - Will now run! ✅
- `multi-arch-ci.yml` - AMD64 jobs will now run! ✅

---

## 🎯 After Setup

### Check Status
```bash
./scripts/monitor-runner.sh
# Choose option 1 for quick check
```

### View Live Logs
```bash
./scripts/monitor-runner.sh
# Choose option 2 for live logs
```

### Restart If Needed
```bash
./scripts/restart-runner.sh
```

---

## 🔧 Advanced Options

### Set Up Multiple Runners (for parallel jobs)
```bash
./scripts/setup-multiple-runners.sh
```

### Custom Configuration
```bash
export RUNNER_NAME="my-fast-builder"
export RUNNER_LABELS="self-hosted,linux,x64,amd64,fast,ssd"
./scripts/setup-github-runner.sh
```

---

## 📚 Full Documentation

- **Script Guide**: [RUNNER_SCRIPTS_GUIDE.md](RUNNER_SCRIPTS_GUIDE.md)
- **Complete Setup**: [docs/GITHUB_RUNNER_SETUP.md](docs/GITHUB_RUNNER_SETUP.md)
- **Quick Reference**: [RUNNER_QUICK_START.md](RUNNER_QUICK_START.md)

---

## 🆘 Troubleshooting

**Runner not showing in GitHub?**
```bash
sudo ~/actions-runner/svc.sh status
journalctl -u actions.runner.* -n 50
```

**Need to remove it?**
```bash
./scripts/remove-runner.sh
```

---

**Ready? Run this now:**
```bash
./scripts/setup-github-runner.sh
```
