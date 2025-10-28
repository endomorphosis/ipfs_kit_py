# Known Issues and Troubleshooting

This document describes known issues with the GitHub Actions workflows and their workarounds.

## GitHub Actions Cache Service Intermittent Failures

### Symptom

Docker builds may fail with errors like:

```
ERROR: failed to solve: failed to parse error response 400: 
<h2>Our services aren't available right now</h2>
<p>We're working to restore all services as soon as possible. Please check back soon.</p>
```

### Root Cause

This is an intermittent issue with GitHub's Actions cache service (backed by Azure Blob Storage). When the cache service experiences downtime or degraded performance, it returns HTML error pages instead of proper API responses, causing Docker buildx to fail.

### Impact

- Builds fail during the cache export phase, even if the actual build was successful
- This is particularly visible during `cache-to` operations in Docker builds
- The issue is transient and typically resolves itself

### Workarounds Implemented

The workflow has been configured with `ignore-error=true` on cache operations:

```yaml
cache-to: type=gha,mode=max,scope=amd64,ignore-error=true
```

This tells Docker buildx to:
1. Attempt to save the build cache to GitHub Actions cache
2. If the cache save fails, log a warning but continue
3. The build still succeeds even if caching fails.

### Additional Mitigation Strategies

If you continue to experience cache-related failures:

1. **Retry the workflow**: Click "Re-run jobs" in the GitHub Actions UI
2. **Check GitHub Status**: Visit https://www.githubstatus.com/ to see if there are known issues with Actions cache
3. **Disable caching temporarily**: If urgent, you can remove the cache parameters from `.github/workflows/docker-enhanced-test.yml`:
   - Remove line: `cache-from: type=gha,scope=amd64` (or `scope=arm64` for ARM64)
   - Remove line: `cache-to: type=gha,mode=max,scope=amd64,ignore-error=true` (or `scope=arm64` for ARM64)
4. **Use local cache**: For self-hosted runners, consider using `type=local` instead of `type=gha`

### Long-term Solutions

GitHub is aware of these intermittent cache service issues. Monitor:
- [GitHub Actions Status Page](https://www.githubstatus.com/)
- [GitHub Actions Community Discussions](https://github.com/orgs/community/discussions/categories/actions-and-packages)

## Self-Hosted Runner Permission Issues

### Symptom

ARM64 or AMD64 builds fail with:

```
sudo: a terminal is required to read the password; either use the -S option 
to read from standard input or configure an askpass helper
sudo: a password is required
```

### Root Cause

The workflow attempted to modify Docker group permissions using `sudo`, but:
1. Self-hosted runners don't have passwordless sudo configured
2. GitHub Actions workflows don't provide interactive terminals
3. Docker permissions should be configured at the runner level, not in workflows

### Solution

Configure Docker permissions during runner setup. See `.github/SELF_HOSTED_RUNNER_SETUP.md` for detailed instructions.

Quick fix:

```bash
# On the runner machine
sudo usermod -aG docker <runner-username>
sudo systemctl restart actions.runner.*
```

## Docker Buildx Multi-platform Build Issues

### Symptom

Builds fail when attempting to build for multiple platforms simultaneously.

### Root Cause

Buildx requires QEMU for cross-platform builds, which may not be configured on all self-hosted runners.

### Solution

Each architecture should use native self-hosted runners:
- AMD64 builds run on `[self-hosted, amd64]` runners
- ARM64 builds run on `[self-hosted, arm64]` runners

This avoids the need for QEMU emulation and provides faster, more reliable builds.

## Workflow File or Dockerfile Missing

### Symptom

Workflow runs fail with "file not found" errors for:
- `.github/workflows/docker-enhanced-test.yml`
- `docker/Dockerfile.enhanced`

### Root Cause

These files exist on the `known_good` branch but may not be present on other branches.

### Solution

These files have been added to the current branch. If working on a new branch:

```bash
git checkout known_good -- .github/workflows/docker-enhanced-test.yml
git checkout known_good -- docker/Dockerfile.enhanced
git commit -m "Add Docker enhanced test workflow and Dockerfile"
```

## Getting Help

If you encounter issues not covered here:

1. Check the [GitHub Actions documentation](https://docs.github.com/en/actions)
2. Review recent workflow run logs in the Actions tab
3. Search for similar issues in the repository's issue tracker
4. Open a new issue with:
   - Workflow run URL
   - Error messages
   - Runner configuration details

## Monitoring Workflow Health

### Useful Commands

Check workflow status:
```bash
gh workflow list
gh run list --workflow="Enhanced Docker Build and Test"
```

View logs for a specific run:
```bash
gh run view <run-id> --log
```

### Success Criteria

A healthy workflow run should:
- ✅ Complete AMD64 build
- ✅ Complete ARM64 build (or skip for PRs without 'test-arm64' label)
- ✅ Pass all Lotus dependency tests
- ✅ Pass container startup tests
- ✅ Show no package manager operations during container startup
- ⚠️ Cache operations may fail but builds should still succeed
