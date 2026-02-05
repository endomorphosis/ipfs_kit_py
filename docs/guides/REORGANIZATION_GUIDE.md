# Root Directory Reorganization Guide

## Overview

The root directory has been reorganized to improve project structure and maintainability. This guide helps you find files that have been relocated.

## Quick Reference

### Shell Scripts

| Old Location | New Location | Purpose |
|--------------|--------------|---------|
| `manage-mcp-service.sh` | `scripts/deployment/manage-mcp-service.sh` | MCP service management |
| `update-mcp-service.sh` | `scripts/deployment/update-mcp-service.sh` | MCP service updates |
| `mcp_unified_config.sh` | `scripts/deployment/mcp_unified_config.sh` | MCP configuration |
| `zero_touch_install.sh` | `scripts/deployment/zero_touch_install.sh` | Installation script |
| `start_mcp_real_apis.sh` | `scripts/server/start_mcp_real_apis.sh` | Start MCP server |
| `QUICK_START_RUNNER.sh` | `scripts/ci/QUICK_START_RUNNER.sh` | Quick start for runners |
| `runner-status.sh` | `scripts/ci/runner-status.sh` | Check runner status |
| `setup-github-runner.sh` | `scripts/ci/setup-github-runner.sh` | Setup GitHub runner |
| `setup-runner-interactive.sh` | `scripts/ci/setup-runner-interactive.sh` | Interactive runner setup |
| `test-arm64-runner.sh` | `scripts/ci/test-arm64-runner.sh` | Test ARM64 runner |
| `test-build-arm64.sh` | `scripts/ci/test-build-arm64.sh` | Build for ARM64 |
| `test-full-dependencies.sh` | `scripts/ci/test-full-dependencies.sh` | Test dependencies |

### Service Files

| Old Location | New Location |
|--------------|--------------|
| `ipfs-kit-mcp.service` | `deployment/systemd/ipfs-kit-mcp.service` |
| `ipfs-kit-mcp-updated.service` | `deployment/systemd/ipfs-kit-mcp-updated.service` |

### Configuration Files

| Old Location | New Location |
|--------------|--------------|
| `playwright.config.js` | `tests/e2e/playwright/playwright.config.js` |
| `playwright.config.ts` | `tests/e2e/playwright/playwright.config.ts` |
| `test_dashboard.html` | `tests/fixtures/test_dashboard.html` |
| `dependency_report.json` | `tests/fixtures/dependency_report.json` |

### Documentation

#### ARM64 Documentation
All `ARM64_*.md` files → `docs/deployment/arm64/`

#### AMD64 Documentation
All `AMD64_*.md` files → `docs/ci-cd/amd64/`

#### Auto-Healing Documentation
All `AUTO_HEALING_*.md` files → `docs/features/auto-healing/`

#### Copilot Documentation
All `COPILOT_*.md` files → `docs/features/copilot/`

#### Docker Documentation
All `DOCKER_*.md` files → `docs/deployment/docker/`

#### Multi-Architecture Documentation
All `MULTI_ARCH_*.md` files → `docs/deployment/multi-arch/`

#### Workflow Documentation
All `WORKFLOW_*.md` files → `docs/ci-cd/`

#### Migration Documentation
All `ANYIO_*.md` files → `docs/migration/`

#### Implementation Documentation
All `*IMPLEMENTATION*.md` and `*SUMMARY*.md` files → `docs/implementation/`

#### Fix Documentation
All `*FIX*.md` files → `docs/fixes/`

#### Other Documentation
- `MONITORING_GUIDE.md` → `docs/features/MONITORING_GUIDE.md`
- `P2P_WORKFLOW_*.md` → `docs/features/`
- `DEPENDENCY_MANAGEMENT.md` → `docs/features/DEPENDENCY_MANAGEMENT.md`
- `ENCRYPTED_CONFIG_*.md` → `docs/features/`
- `CI_CD_*.md` → `docs/ci-cd/`
- `GITHUB_RUNNER_*.md` → `docs/ci-cd/`
- `RUNNER_*.md` → `docs/ci-cd/`
- `MCP_DASHBOARD_*.md` → `docs/features/mcp/`
- `DASHBOARD_*.md` → `docs/features/dashboard/`
- `SYSTEMD_*.md` → `docs/deployment/`

## Updated References

### In Code
- `ipfs_kit_py/mcp/mcp_server_fix.py`: Updated path to `test_dashboard.html`
- `package.json`: Updated paths to playwright config files

### In Documentation
- `README.md`: Updated references to auto-healing guides and installation script
- `docs/implementation/MCP_SYSTEMD_IMPLEMENTATION_SUMMARY.md`: Updated script paths

## Files Remaining in Root (By Design)

These files remain in the root directory as per standard practices:

### Essential Project Files
- `README.md` - Project documentation
- `LICENSE` - License information

### Python Project Files
- `setup.py` - Package setup script
- `pyproject.toml` - Modern Python project configuration
- `requirements.txt` - Python dependencies
- `requirements-gpu.txt` - GPU-specific dependencies
- `pytest.ini` - Test configuration

### Docker Files
- `Dockerfile` - Main Docker image
- `Dockerfile.dev` - Development image
- `Dockerfile.docs` - Documentation image
- `Dockerfile.gpu` - GPU-enabled image
- `Dockerfile.test` - Test image
- `docker-compose.yml` - Docker Compose configuration

### Build & Config Files
- `Makefile` - Build automation
- `package.json` - Node.js dependencies (for E2E tests and CSS)
- `tailwind.config.js` - Tailwind CSS configuration (project-wide)
- `postcss.config.js` - PostCSS configuration (project-wide)

## Benefits of Reorganization

1. **Clearer Structure**: Files are organized by purpose (scripts, docs, deployment, tests)
2. **Easier Navigation**: Related files are grouped together
3. **Better Maintainability**: Easier to find and update files
4. **Standard Practices**: Follows common project organization patterns
5. **Cleaner Root**: Root directory only contains essential project files

## Migration Notes for Developers

### If you have local branches:
1. Rebase or merge from the main branch to get these changes
2. Update any scripts or references that point to old locations
3. Test your workflows to ensure they still work

### If you have external scripts:
Update any external scripts or CI/CD configurations that reference the old file locations using the table above.

### If you're using the installation script:
The new path is `./scripts/deployment/zero_touch_install.sh` instead of `./zero_touch_install.sh`.

### If you're using the MCP service management:
The new path is `./scripts/deployment/manage-mcp-service.sh` instead of `./manage-mcp-service.sh`.

## Questions or Issues?

If you encounter any issues with the reorganization or cannot find a file you need, please:
1. Check this guide first
2. Search the repository using `find` or `grep`
3. Open an issue on GitHub with details about the missing file
