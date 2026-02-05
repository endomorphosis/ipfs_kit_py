# Auto-Healing Quick Start Guide

Get started with the IPFS-Kit auto-healing feature in 5 minutes.

## 1. Get Your GitHub Token

Create a GitHub Personal Access Token:

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name like "IPFS-Kit Auto-Heal"
4. Select scopes: `repo` (all repo permissions)
5. Click "Generate token"
6. **Copy the token** (you won't see it again!)

## 2. Set Environment Variables

```bash
export IPFS_KIT_AUTO_HEAL=true
export GITHUB_TOKEN=ghp_your_token_here
export GITHUB_REPOSITORY=your-username/your-repo
```

Add these to your `~/.bashrc` or `~/.zshrc` to make them permanent.

## 3. Enable Auto-Healing

```bash
ipfs-kit autoheal enable
```

## 4. Verify Configuration

```bash
ipfs-kit autoheal status
```

You should see:
```
Auto-Healing Status:
  Enabled: Yes
  Configured: Yes
  Repository: your-username/your-repo
  GitHub Token: Set
  Auto-create issues: Yes
```

## 5. Test It!

Trigger an intentional error to see auto-healing in action:

```bash
# This will fail if IPFS isn't running
ipfs-kit daemon status
```

If an error occurs, you'll see:
```
⚠️  An error occurred and has been automatically reported.
📋 Issue created: https://github.com/your-username/your-repo/issues/123
🤖 The auto-healing system will attempt to fix this error.
```

## 6. Check the Issue

1. Go to the issue URL shown
2. See the full error report with stack trace
3. Wait for the auto-heal workflow to run
4. Review the automatically created PR with the fix!

## That's It!

Your CLI is now self-healing. Errors will automatically:
- Create GitHub issues
- Generate fixes
- Create pull requests
- Invoke GitHub Copilot when needed

## Next Steps

- Read the [full documentation](AUTO_HEALING.md)
- Customize configuration: `ipfs-kit autoheal config`
- Review auto-generated PRs and merge the fixes

## Troubleshooting

**Not working?** Check:

```bash
# 1. Verify environment variables
echo $IPFS_KIT_AUTO_HEAL
echo $GITHUB_TOKEN
echo $GITHUB_REPOSITORY

# 2. Check configuration
ipfs-kit autoheal status --json

# 3. Test GitHub API access
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user
```

Need help? [Open an issue](https://github.com/endomorphosis/ipfs_kit_py/issues)!
