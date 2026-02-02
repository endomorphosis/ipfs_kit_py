# Auto-Heal Context for Issue #159

## Workflow Failure Information

- **Workflow:** Enhanced Docker Build and Test
- **Run ID:** 21577768348
- **Run URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21577768348
- **Branch:** main
- **Commit:** 546032d6642d9f9fc61e9ecff4733277fb20f0ba

## Failed Jobs

### Job: Build AMD64 Docker Image

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21577768348/job/62168676994

**Failed Steps:**
- Build Docker image (AMD64)

### Job: Build ARM64 Docker Image

**Status:** failure
**URL:** https://github.com/endomorphosis/ipfs_kit_py/actions/runs/21577768348/job/62168677013

**Failed Steps:**
- Build Docker image (ARM64)



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
