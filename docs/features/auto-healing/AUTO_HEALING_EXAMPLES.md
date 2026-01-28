# Auto-Healing Workflow System - Example Scenarios

This document provides concrete examples of how the auto-healing system works in practice.

## Example 1: Missing Dependency

### Initial State
You have a workflow that runs tests:

```yaml
name: Python Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
    - run: pip install pytest
    - run: pytest tests/
```

### Failure Scenario
Someone adds a test that uses `requests` library, but doesn't add it to the dependencies:

```python
# tests/test_api.py
import requests  # Not in dependencies!

def test_api_call():
    response = requests.get('https://api.example.com/status')
    assert response.status_code == 200
```

### Auto-Healing Response

**1. Workflow fails** (30 seconds after push)
```
Error: ModuleNotFoundError: No module named 'requests'
```

**2. Issue created** (1 minute after failure)
```markdown
Title: [Auto-Heal] Workflow Failure: Python Tests

Workflow: Python Tests
Run ID: 1234567890
Conclusion: failure

### Failure Analysis
Identified 1 potential issue(s): missing_dependency

### Failed Jobs
- test: failure

### Error Details
ModuleNotFoundError: No module named 'requests'
File "tests/test_api.py", line 1, in <module>
    import requests
```

**3. PR created** (2 minutes after issue)
```markdown
Title: [Auto-Heal] Fix workflow: Python Tests

## Auto-Generated Workflow Fix

### Changes Made
- Add missing dependency: requests

### Suggested Fix
```yaml
name: Python Tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
    - run: pip install pytest requests  # ← Added 'requests'
    - run: pytest tests/
```

🤖 Note: This PR automatically triggers GitHub Copilot agent review.
```

**4. Human review and merge** (few minutes later)
- Developer reviews the PR
- Verifies the fix is appropriate
- Merges the PR
- Workflow runs successfully ✅

---

## Example 2: Timeout Issue

### Initial State
```yaml
name: Build Docker Image
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10  # Too short!
    steps:
    - uses: actions/checkout@v4
    - run: docker build -t myapp .
    - run: docker push myapp
```

### Failure Scenario
Build takes 15 minutes but timeout is only 10 minutes.

### Auto-Healing Response

**1. Workflow fails**
```
Error: The operation was canceled.
Job timed out after 10 minutes
```

**2. Issue created**
```markdown
Title: [Auto-Heal] Workflow Failure: Build Docker Image

### Failure Analysis
Identified 1 potential issue(s): timeout

### Error Details
Error: The operation was canceled.
Job timed out after 10 minutes
```

**3. PR created**
```markdown
Title: [Auto-Heal] Fix workflow: Build Docker Image

### Changes Made
- Increase job timeout from 10 to 60 minutes

### Suggested Fix
```yaml
name: Build Docker Image
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 60  # ← Increased from 10
    steps:
    - uses: actions/checkout@v4
    - run: docker build -t myapp .
    - run: docker push myapp
```
```

---

## Example 3: ARM64 Optional Job Failure

### Initial State
```yaml
name: Multi-Architecture Tests
on: [push]
jobs:
  test-amd64:
    runs-on: ubuntu-latest
    steps:
    - run: pytest tests/
    
  test-arm64:
    runs-on: [self-hosted, arm64]
    steps:
    - run: pytest tests/
```

### Failure Scenario
ARM64 runner is temporarily offline, causing the entire workflow to fail.

### Auto-Healing Response

**1. Workflow fails**
```
Error: No runner available for label 'arm64'
```

**2. Issue created**
```markdown
Title: [Auto-Heal] Workflow Failure: Multi-Architecture Tests

### Failure Analysis
Identified 1 potential issue(s): runner_unavailable

### Failed Jobs
- test-arm64: failure
```

**3. PR created**
```markdown
Title: [Auto-Heal] Fix workflow: Multi-Architecture Tests

### Changes Made
- Added continue-on-error to optional job: test-arm64

### Suggested Fix
```yaml
name: Multi-Architecture Tests
on: [push]
jobs:
  test-amd64:
    runs-on: ubuntu-latest
    steps:
    - run: pytest tests/
    
  test-arm64:
    runs-on: [self-hosted, arm64]
    continue-on-error: true  # ← Added to prevent pipeline failure
    steps:
    - run: pytest tests/
```

### Testing
The workflow will now succeed even if ARM64 runner is unavailable.
```

---

## Example 4: YAML Syntax Error

### Initial State
Someone edits a workflow and introduces a syntax error:

```yaml
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - run: echo "Hello"
      run: echo "World"  # ← DUPLICATE KEY ERROR!
```

### Auto-Healing Response

**1. Workflow fails**
```
Error: .github/workflows/ci.yml is not valid YAML
duplicate key 'run' on line 8
```

**2. Issue created**
```markdown
Title: [Auto-Heal] Workflow Failure: CI

### Failure Analysis
Identified 1 potential issue(s): yaml_syntax
```

**3. PR created**
```markdown
Title: [Auto-Heal] Fix workflow: CI

### Changes Made
- Fix YAML syntax error: duplicate 'run' key

### Suggested Fix
```yaml
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - run: echo "Hello"
    - run: echo "World"  # ← Fixed: Proper list item
```
```

---

## Example 5: Complex Issue (Manual Intervention Required)

### Initial State
```yaml
name: Deploy to Production
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - run: ./deploy.sh
```

### Failure Scenario
The deployment fails due to a logic error in the deploy script:

```bash
#!/bin/bash
# deploy.sh
kubectl apply -f deployment.yml
if [ $? -ne 0 ]; then
  echo "Deployment failed!"
  exit 1
fi
```

The deployment YAML has a configuration error.

### Auto-Healing Response

**1. Workflow fails**
```
Error: deployment.apps "myapp" is forbidden: 
User "system:serviceaccount:default:default" cannot update
resource "deployments" in API group "apps"
```

**2. Issue created**
```markdown
Title: [Auto-Heal] Workflow Failure: Deploy to Production

### Failure Analysis
Identified 1 potential issue(s): permission_error
```

**3. PR created (but with caveat)**
```markdown
Title: [Auto-Heal] Fix workflow: Deploy to Production

⚠️ The auto-healing system could not generate an automatic fix 
for this workflow failure.

**Reason:** Permission errors require manual security configuration

**Manual intervention required:** 
1. Check Kubernetes RBAC permissions
2. Update ServiceAccount permissions
3. Verify deployment.yml configuration

This issue requires human review of:
- Kubernetes cluster permissions
- ServiceAccount configuration
- Security policies
```

**4. Human intervention**
- Developer reviews the issue
- Fixes the ServiceAccount permissions
- Updates the deployment configuration
- Closes the issue manually

---

## Timeline Visualization

```
Typical Auto-Healing Timeline
═════════════════════════════════════════════════════════════

t+0s    │ Developer pushes code with bug
        │
t+30s   │ ❌ Workflow fails
        │
t+1m    │ 🔍 Failure Monitor detects issue
        │ 📝 Issue #42 created
        │
t+2m    │ 🔧 Auto-Heal workflow triggers
        │ 📊 Analyzes logs
        │ 💡 Generates fix
        │
t+3m    │ 🚀 PR #43 opened
        │ 🤖 Copilot review triggered (if enabled)
        │
t+5m    │ 👀 Developer notified
        │
t+10m   │ ✅ Developer reviews & approves
        │ 🎉 PR merged
        │
t+11m   │ ✨ Workflow runs successfully
        │
═════════════════════════════════════════════════════════════
Total time from failure to fix: ~11 minutes
(vs hours or days for manual investigation and fix)
```

---

## Success Metrics

After implementing auto-healing, you can track:

### Before Auto-Healing
- Average time to fix: **4-24 hours**
- Developer intervention: **Required for every failure**
- Workflow failures: **Block development**

### After Auto-Healing
- Average time to fix: **5-15 minutes**
- Developer intervention: **Only for review and approval**
- Workflow failures: **Automatically resolved or escalated**

### Example Metrics (First Month)

```
Auto-Healing System Report
══════════════════════════════════════════════════════

Total Failures Detected:        47
Issues Created:                 47
PRs Generated:                  42
PRs Automatically Fixed:        38 (90%)
Manual Intervention Required:    4 (10%)

Average Resolution Time:        12 minutes
Developer Time Saved:          ~140 hours
Build Pipeline Uptime:         97% → 99.5%

Common Fixed Issues:
  - Missing dependencies:       18 (43%)
  - Timeout issues:             12 (29%)
  - Optional job failures:       8 (19%)
  - Other:                       4 (9%)
```

---

## Best Practices from Real Usage

### DO ✅
- Review auto-generated PRs before merging
- Provide feedback in PR comments
- Keep workflows simple and modular
- Add descriptive error messages
- Document complex workflows

### DON'T ❌
- Blindly merge auto-heal PRs without review
- Ignore patterns of repeated failures
- Over-complicate workflows
- Disable auto-healing without trying it
- Expect 100% automatic fixes (aim for 80-90%)

---

## Real User Testimonials (Hypothetical)

> "We went from spending 2-3 hours per week fixing workflow issues to just reviewing PRs for 15 minutes. The auto-healing system pays for itself in the first week!"
> — *DevOps Team Lead*

> "I love coming back from lunch to find that the workflow I broke is already fixed with a PR waiting for my review."
> — *Senior Developer*

> "The system caught a timeout issue we didn't even know existed. It increased our build timeout and everything started working better."
> — *Platform Engineer*

---

For more information, see:
- [Full Documentation](./AUTO_HEALING_WORKFLOWS.md)
- [Quick Start Guide](./AUTO_HEALING_QUICK_START.md)
