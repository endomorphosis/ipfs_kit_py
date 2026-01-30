# Auto-Heal Context for Issue #144

## Workflow Failure Information

- **Workflow:** Enhanced Docker Build and Test
- **Run ID:** 21529088374
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21529088374
- **Branch:** main
- **Commit:** 14e49b3ee0cb58c719a75000496b44da3627957b

## Failed Jobs

### Job: Build ARM64 Docker Image

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21529088374/job/62040207292

**Failed Steps:**
- Build Docker image (ARM64)

### Job: Build AMD64 Docker Image

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21529088374/job/62040207319

**Failed Steps:**
- Build Docker image (AMD64)



## Task

Please fix the workflow failure by:
1. Analyzing the error logs above
2. Identifying the root cause
3. Making minimal, targeted changes to fix the issue
4. Ensuring the fix doesn't break existing functionality

## Files to Review

- `.github/workflows/` directory for workflow YAML files
- Related source code if the failure is in application tests
- Dependencies and configuration files

Follow the guidelines in `.github/copilot-instructions.md`
