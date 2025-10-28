# Self-Hosted Runner Setup Guide

This guide provides instructions for setting up self-hosted GitHub Actions runners with proper Docker permissions for the IPFS Kit project.

## Prerequisites

- Ubuntu 20.04+ or Debian-based Linux distribution
- Docker installed
- GitHub Actions runner installed and configured

## Docker Permissions Configuration

### Issue

The GitHub Actions workflow requires Docker access without sudo. By default, Docker commands require root privileges, which causes workflow failures when trying to use Docker.

### Solution

Configure Docker to allow non-root users (specifically the runner user) to execute Docker commands:

1. **Add the runner user to the docker group:**

   ```bash
   sudo usermod -aG docker $USER
   ```

   Replace `$USER` with the actual username running the GitHub Actions runner (e.g., `runner`, `github-runner`, or your specific runner username).

2. **Verify the docker group exists:**

   ```bash
   getent group docker
   ```

   If the group doesn't exist, create it first:

   ```bash
   sudo groupadd docker
   ```

3. **Apply the group changes:**

   For the changes to take effect, you need to either:
   
   - **Option A: Restart the GitHub Actions runner service** (recommended):
     ```bash
     sudo systemctl restart actions.runner.*
     ```
   
   - **Option B: Log out and log back in** (if running runner interactively)
   
   - **Option C: Use newgrp** (temporary, for testing):
     ```bash
     newgrp docker
     ```

4. **Verify Docker access without sudo:**

   Test that the runner user can execute Docker commands:

   ```bash
   docker version
   docker ps
   ```

   These commands should work without requiring `sudo`.

## Additional Configuration

### Runner Labels

Ensure your self-hosted runners are labeled correctly:

- **AMD64 runners**: Should have labels `self-hosted, amd64`
- **ARM64 runners**: Should have labels `self-hosted, arm64, dgx` (or appropriate architecture-specific label)

You can set labels during runner registration or update them later in the GitHub repository settings.

### Docker Buildx

The workflow uses Docker Buildx for multi-platform builds. Buildx should be included with Docker 19.03+ but verify it's enabled:

```bash
docker buildx version
```

If needed, enable experimental features in Docker:

```bash
# Edit /etc/docker/daemon.json
{
  "experimental": true
}

# Restart Docker
sudo systemctl restart docker
```

## Troubleshooting

### "permission denied" errors

If you still see Docker permission errors:

1. Verify the user is in the docker group:
   ```bash
   groups $USER
   ```

2. Check Docker socket permissions:
   ```bash
   ls -la /var/run/docker.sock
   ```
   
   The socket should be owned by `root:docker` with permissions `660` or `666`.

3. If needed, manually set socket permissions:
   ```bash
   sudo chmod 666 /var/run/docker.sock
   ```

### Runner service not restarting

Find your specific runner service name:

```bash
sudo systemctl list-units --type=service | grep runner
```

Then restart the specific service:

```bash
sudo systemctl restart actions.runner.<org>-<repo>.<runner-name>.service
```

## Security Considerations

- Adding a user to the docker group grants effective root access, as Docker containers can be run with root privileges
- Ensure your self-hosted runners are in a secure environment
- Consider using rootless Docker for enhanced security: https://docs.docker.com/engine/security/rootless/

## References

- [Docker Post-Installation Steps](https://docs.docker.com/engine/install/linux-postinstall/)
- [GitHub Actions Self-Hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Docker Buildx Documentation](https://docs.docker.com/buildx/working-with-buildx/)
