# GitHub Copilot Instructions for Workflow Fixes

This file provides instructions for GitHub Copilot when working on workflow failure fixes in this repository.

## Repository Context

This is the `ipfs_kit_py` repository - a Python toolkit for IPFS with high-level API, cluster management, tiered storage, and AI/ML integration.

### Key Technologies
- Python 3.12+
- GitHub Actions for CI/CD
- Docker for containerization
- Pytest for testing
- Multiple workflow configurations

## When Fixing Workflow Failures

### Step 1: Analyze the Failure Context

1. **Read the failure context file**: Look in `.github/workflow-failures/` for the specific failure details
2. **Identify the failed workflow**: Note the workflow name, job names, and step names
3. **Review error messages**: Parse error messages to understand root cause
4. **Check workflow logs**: Review any downloaded logs for additional context

### Step 2: Locate the Problem

Common locations to check:

- **Workflow files**: `.github/workflows/*.yml` - Check YAML syntax, steps, permissions
- **Dependencies**: `requirements.txt`, `pyproject.toml` - Check version compatibility
- **Test files**: `test/`, `tests/` - Check for test-specific issues
- **Configuration**: `setup.py`, `setup.cfg`, `tox.ini` - Check build/test config
- **Scripts**: `scripts/`, `bin/` - Check any custom scripts called by workflows

### Step 3: Determine Fix Strategy

Based on failure type:

#### Dependency Failures
```yaml
Failed Step: Install dependencies
Error: Could not find a version...
```
**Fix**: Update package versions in requirements files
- Check for version conflicts
- Update to compatible versions
- Verify dependencies are available in PyPI

#### Test Failures
```yaml
Failed Step: Test with pytest
Error: FAILED test_foo.py::test_bar
```
**Fix**: Fix the failing test or code
- Review the test assertion
- Check if code behavior changed
- Update test or fix code logic
- Ensure test is still valid

#### Syntax Errors
```yaml
Error: Invalid workflow file
```
**Fix**: Correct YAML syntax
- Check indentation (use 2 spaces)
- Validate YAML structure
- Ensure proper quoting
- Verify action versions exist

#### Permission Errors
```yaml
Error: Resource not accessible by integration
```
**Fix**: Add required permissions
```yaml
permissions:
  contents: write
  pull-requests: write
```

#### Build Failures
```yaml
Failed Step: Build the package
```
**Fix**: Address build configuration
- Check `setup.py` and `pyproject.toml`
- Verify all files are included
- Check for missing dependencies

### Step 4: Implement Minimal Fix

**Critical Guidelines:**
- Make the **smallest possible change** to fix the issue
- Don't refactor or improve unrelated code
- Don't add new features while fixing
- Focus only on the specific failure
- Preserve existing functionality

### Step 5: Verify the Fix

Before committing:
1. **Syntax Check**: Validate YAML files with `yamllint` or similar
2. **Dependency Check**: Verify packages exist and versions are correct
3. **Test Locally**: If possible, run tests locally to verify
4. **Review Impact**: Ensure fix doesn't break other workflows

### Step 6: Document Changes

In your commit message, include:
```
Fix workflow failure: [workflow name]

- Brief description of what failed
- Root cause analysis
- Changes made to fix
- Issue reference: #[issue_number]
```

## Common Patterns in This Repository

### Python Package Workflows
- Uses Python 3.12
- Installs with `pip install .[dev]`
- Tests with `pytest`
- Lints with `black` and `isort`
- Builds with `python -m build`

### Docker Workflows
- Multi-stage builds
- ARM64 and AMD64 support
- Security scanning with Trivy
- Pushes to GHCR

### Dependency Management
- `pyproject.toml` is the source of truth
- `requirements.txt` may exist for compatibility
- Uses `pip-tools` for compilation
- Security checks with `safety`

## Project-Specific Considerations

### Testing
- Test files in `test/` and `tests/` directories
- Uses `pytest` as test runner
- Some tests may require IPFS daemon
- Linting is currently set to `continue-on-error: true`

### Build Process
- Uses `setuptools` build backend
- Package name: `ipfs_kit_py`
- Currently at version 0.2.0
- Requires Python >= 3.12

### CI/CD Structure
- Main branch: `main` or `master`
- Feature branches follow conventional naming
- PRs require tests to pass (except lint)
- Automated publishing to PyPI on tags

## Workflow-Specific Guidance

### workflow.yml / python-package.yml
Standard Python package testing and building:
- Setup Python 3.12
- Install dependencies with pip
- Run pytest for tests
- Run black/isort for linting (non-blocking)
- Build package with build module
- Publish to PyPI on tags

### docker.yml / docker-build.yml
Docker image building:
- Multi-platform builds (arm64, amd64)
- Push to GitHub Container Registry
- Security scanning
- May have resource constraints

### dependencies.yml
Automated dependency updates:
- Runs weekly on Monday
- Creates PRs for updates
- Includes security scanning

## Error Message Reference

### Common Error Patterns

| Error Pattern | Likely Cause | Fix Location |
|--------------|--------------|--------------|
| `ModuleNotFoundError` | Missing dependency | `pyproject.toml` |
| `Invalid workflow file` | YAML syntax error | `.github/workflows/*.yml` |
| `Resource not accessible` | Permission issue | Add `permissions:` block |
| `Test failed` | Code or test issue | Test files or source code |
| `command not found` | Missing tool | Add to workflow `run:` step |
| `version not found` | Wrong package version | Update version specifier |

## Code Style Guidelines

When fixing code (not workflows):
- Follow existing code style
- Use black for formatting (if changing Python)
- Use isort for imports (if changing Python)
- Don't change more than necessary

## Testing Guidelines

When fixing tests:
- Understand what the test validates
- Don't weaken test assertions without good reason
- Consider if requirements changed
- Check if test data or fixtures need updating

## Security Considerations

When fixing workflows:
- Don't add secrets to code
- Use `${{ secrets.SECRET_NAME }}` for sensitive data
- Minimize permissions (principle of least privilege)
- Avoid `actions/checkout@v1` (use v3 or v4)
- Pin action versions for security

## Performance Considerations

- Workflow runs cost resources
- Cache dependencies when possible
- Avoid redundant steps
- Use conditions to skip unnecessary jobs

## Examples of Good Fixes

### Example 1: Fix Dependency Version
```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -30,7 +30,7 @@
 dependencies = [
     "requests>=2.28.0",
     "psutil>=5.9.0",
-    "pyyaml>=6.0",
+    "pyyaml>=6.0.1",
     "base58>=2.1.1",
 ]
```

### Example 2: Fix Workflow Syntax
```diff
--- a/.github/workflows/test.yml
+++ b/.github/workflows/test.yml
@@ -15,7 +15,7 @@
     - name: Install dependencies
       run: |
         python -m pip install --upgrade pip
-        python -m pip install .[dev
+        python -m pip install .[dev]
```

### Example 3: Add Missing Permission
```diff
--- a/.github/workflows/publish.yml
+++ b/.github/workflows/publish.yml
@@ -3,6 +3,9 @@
 on:
   push:
     tags: ['v*']
+
+permissions:
+  contents: read
+  id-token: write
```

## What NOT to Do

❌ Don't refactor code while fixing a workflow failure
❌ Don't add new features or improvements
❌ Don't change test expectations without understanding why they fail
❌ Don't disable tests permanently (use `continue-on-error` temporarily if needed)
❌ Don't commit commented-out code
❌ Don't change multiple unrelated things in one fix

## Getting Help

If a fix is complex or unclear:
1. Ask for clarification in the issue/PR
2. Request human review before implementing
3. Provide analysis of the failure in a comment
4. Suggest alternative approaches

## Success Criteria

A successful workflow fix:
✅ Resolves the specific failure
✅ Doesn't break other workflows
✅ Makes minimal changes
✅ Is well-documented
✅ Passes all required checks
✅ Follows repository conventions

---

Remember: The goal is to fix the specific workflow failure with minimal, targeted changes. When in doubt, ask for guidance rather than making broad changes.
