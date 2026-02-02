# CI/CD Automation - Quick Reference Guide

**Quick Links**: [Full Integration Plan](CI_CD_AUTOMATION_INTEGRATION_PLAN.md) | [VS Code Tasks](#vs-code-tasks) | [Workflows](#automation-workflows)

---

## 🎯 What This Automation Does

### The Problem
- Manual workflow failure investigation takes time
- Creating fix PRs is repetitive
- PR reviews require constant attention
- Developers spend time on routine fixes

### The Solution
**Fully automated CI/CD failure handling**:
1. 🔍 **Auto-detect** workflow failures
2. 📝 **Auto-create** detailed issues with logs
3. 🔀 **Auto-generate** draft PRs
4. 🤖 **Auto-fix** via GitHub Copilot
5. ✅ **Human review** only at the end

---

## 🚀 How It Works (Simple View)

```
Workflow Fails ───▶ Issue Created ───▶ Draft PR Created ───▶ Copilot Fixes ───▶ You Review & Merge
   (Auto)              (Auto)              (Auto)               (Auto)            (Manual)
```

**You only need to**:
- Review the final PR
- Merge if it looks good
- That's it! ✨

---

## 📋 Components Overview

### 1. Auto-Healing System
**What**: Monitors all workflows and auto-responds to failures  
**File**: `.github/workflows/copilot-agent-autofix.yml`  
**Features**:
- Monitors 47+ workflows
- Downloads and analyzes failure logs
- Creates issues with error details
- Generates draft PRs
- Invokes Copilot for fixes

**Example Issue Created**:
```
Title: Fix: Docker Build - Missing Dependency

**Workflow**: Docker Build and Test
**Run ID**: 12345678
**Branch**: main
**Error Type**: ModuleNotFoundError
**Confidence**: 90%

### Error Details
ModuleNotFoundError: No module named 'pytest-asyncio'

### Fix Proposal
Add pytest-asyncio to requirements.txt

### Logs
[Full logs attached]
```

### 2. Issue-to-Draft-PR
**What**: Converts any issue into a draft PR with Copilot integration  
**File**: `.github/workflows/issue-to-draft-pr.yml`  
**Features**:
- Works with manual issues
- Works with auto-generated issues
- Prevents duplicate PRs
- Rate limiting (10 PRs/hour max)

**Example PR Created**:
```
Title: Fix: Docker Build - Missing Dependency

Fixes #123

This PR was automatically created to address the workflow failure.
See the linked issue for full analysis.

@copilot /fix - Please implement the fix as described
```

### 3. PR Review Automation
**What**: Auto-assigns PRs to Copilot for review and completion  
**File**: `.github/workflows/pr-copilot-reviewer.yml`  
**Features**:
- Analyzes PR changes
- Assigns to Copilot
- Monitors progress
- Notifies when ready

### 4. VS Code Tasks
**What**: One-click commands for common development tasks  
**File**: `.vscode/tasks.json`  
**Features**: 50+ tasks for:
- Testing (unit, integration, specific modules)
- Docker operations
- MCP/IPFS operations
- Code quality checks
- Auto-healing operations

---

## 🎬 Workflows Available from ipfs_datasets_py

| Workflow | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `copilot-agent-autofix.yml` | Main auto-healing system | HIGH | ✅ Can adapt |
| `issue-to-draft-pr.yml` | Issue → PR automation | HIGH | ✅ Can adapt |
| `pr-copilot-reviewer.yml` | Auto PR review | MEDIUM | ✅ Can adapt |
| `pr-completion-monitor.yml` | Track PR progress | MEDIUM | ✅ Can adapt |
| `update-autohealing-list.yml` | Auto-update workflow list | LOW | ✅ Can adapt |
| `close-stale-draft-prs.yml` | Clean up old PRs | LOW | ✅ Can adapt |
| `workflow-health-check.yml` | Monitor CI/CD health | LOW | ✅ Can adapt |

---

## 🛠 VS Code Tasks

### Task Categories

#### 1. Testing Tasks
```
- Run All Tests
- Run Unit Tests
- Run Integration Tests
- Run Specific Test File
- Run Tests with Coverage
- Run MCP Tests
- Run Dashboard Tests
- Run Docker Tests
```

#### 2. Development Tasks
```
- Install Dependencies
- Start Dev Server
- Build Project
- Watch Mode
- Clean Build
```

#### 3. Docker Tasks
```
- Build Docker Image
- Start Docker Services
- Stop Docker Services
- View Docker Logs
- Clean Docker
```

#### 4. Code Quality Tasks
```
- Lint Code
- Format Code
- Type Check
- Check Imports
- Check Compilation
- Audit Docstrings
```

#### 5. Automation Tasks
```
- Trigger Auto-Healing
- Analyze Workflow Failure
- Create Issue from Failure
- Update Workflow List
- Check Workflow Health
```

#### 6. MCP/IPFS Tasks
```
- Start MCP Server
- Test MCP Endpoints
- Start IPFS Daemon
- Test IPFS Operations
- Start Dashboard
- Test Dashboard
```

### Example: Run a VS Code Task

**In VS Code**:
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Tasks: Run Task"
3. Select task from list
4. Task runs in integrated terminal

**Common Tasks**:
- `Install Dependencies` - Install Python packages
- `Run All Tests` - Run full test suite
- `Start Dev Server` - Start development server
- `Trigger Auto-Healing` - Manually trigger auto-healing for a workflow

---

## ⚙️ Configuration

### Auto-Healing Config
**File**: `.github/workflows/workflow-auto-fix-config.yml`

**Key Settings**:
```yaml
auto_healing:
  enabled: true           # Enable/disable system
  min_confidence: 70      # Minimum confidence for auto-PR (0-100)
  
rate_limits:
  max_prs_per_hour: 10    # Prevent spam
  max_issues_per_hour: 20

excluded_workflows:       # Workflows to skip
  - "Copilot Agent Auto-Healing"
  
error_patterns:           # Recognized error types
  missing_dependency:
    pattern: "ModuleNotFoundError"
    confidence: 90
    fix_type: "add_dependency"
```

### Supported Error Types

| Error Type | Detection Pattern | Confidence | Auto-Fix |
|------------|-------------------|------------|----------|
| Missing Dependency | `ModuleNotFoundError`, `ImportError` | 90% | ✅ Yes |
| Syntax Error | `SyntaxError`, `IndentationError` | 85% | ✅ Yes |
| Timeout | `timeout`, `timed out` | 75% | ✅ Yes |
| Docker Build Fail | `docker build.*failed` | 80% | ✅ Yes |
| Permission Denied | `Permission denied` | 70% | ⚠️ Manual review |

---

## 📊 Monitoring

### Check Auto-Healing Activity

**Issues**:
```bash
# View auto-generated issues
gh issue list --label auto-healing,workflow-failure
```

**PRs**:
```bash
# View automated PRs
gh pr list --label automated-fix,copilot-ready
```

**Workflows**:
```bash
# Check auto-healing workflow runs
gh run list --workflow="copilot-agent-autofix.yml"
```

### Metrics to Track

1. **Automation Rate**
   - How many failures get auto-analyzed?
   - How many get auto-fixed?

2. **Success Rate**
   - How many auto-generated PRs are merged?
   - How many fixes actually work?

3. **Time Savings**
   - Time from failure to fix
   - Developer time saved

---

## 🔧 Common Operations

### Manually Trigger Auto-Healing

```bash
gh workflow run copilot-agent-autofix.yml \
  --field workflow_name="Docker Build" \
  --field run_id="12345678"
```

### Create PR from Issue

```bash
gh workflow run issue-to-draft-pr.yml \
  --field issue_number="123"
```

### Check Workflow Health

```bash
gh workflow run workflow-health-check.yml
```

---

## 🚨 Troubleshooting

### Issue Not Created for Workflow Failure

**Possible Causes**:
1. Workflow is in excluded list
2. Already processed (duplicate)
3. Not a failure (cancelled/skipped)

**How to Check**:
```bash
# View auto-healing logs
gh run list --workflow="copilot-agent-autofix.yml" --limit 5
gh run view <run-id> --log
```

### Copilot Not Responding to PR

**Possible Causes**:
1. @copilot not mentioned
2. PR not in draft state
3. Missing copilot-ready label

**How to Fix**:
1. Ensure PR has comment: `@copilot /fix`
2. Ensure PR is draft
3. Add `copilot-ready` label

### Too Many Automated PRs

**How to Fix**:
1. Adjust rate limit in config
2. Add workflows to exclusion list
3. Increase confidence threshold

---

## 📚 Additional Resources

### Documentation
- [Full Integration Plan](CI_CD_AUTOMATION_INTEGRATION_PLAN.md) - Complete technical details
- [Auto-Healing Guide](https://github.com/endomorphosis/ipfs_datasets_py/blob/main/.github/workflows/AUTO_HEALING_GUIDE.md) - From source repo
- [Architecture](https://github.com/endomorphosis/ipfs_datasets_py/blob/main/.github/workflows/ARCHITECTURE.md) - System design

### Source Repository
- [ipfs_datasets_py](https://github.com/endomorphosis/ipfs_datasets_py) - Source of automation
- [Workflows](https://github.com/endomorphosis/ipfs_datasets_py/tree/main/.github/workflows) - Original workflows
- [VS Code Tasks](https://github.com/endomorphosis/ipfs_datasets_py/blob/main/.vscode/tasks.json) - Original tasks

---

## ✅ Integration Checklist

### Phase 1: Foundation
- [ ] Review integration plan
- [ ] Create `.github/scripts/` directory
- [ ] Copy Python scripts
- [ ] Create config file
- [ ] Test scripts locally

### Phase 2: Auto-Healing
- [ ] Update `copilot-agent-autofix.yml`
- [ ] Add workflow triggers
- [ ] Test with sample failure
- [ ] Verify issue creation
- [ ] Verify PR creation

### Phase 3: Issue-to-PR
- [ ] Create `issue-to-draft-pr.yml`
- [ ] Test with manual issue
- [ ] Test duplicate detection
- [ ] Test rate limiting

### Phase 4: PR Review
- [ ] Create `pr-copilot-reviewer.yml`
- [ ] Test PR assignment
- [ ] Monitor Copilot integration

### Phase 5: VS Code
- [ ] Create `.vscode/tasks.json`
- [ ] Adapt tasks for ipfs_kit_py
- [ ] Test in VS Code
- [ ] Add debug configurations

### Phase 6: Documentation
- [ ] Write user guides
- [ ] Update README
- [ ] Create video tutorial (optional)

---

## 🎓 Best Practices

### Do's ✅
- Review all auto-generated PRs before merging
- Monitor auto-healing metrics
- Update exclusion list for critical workflows
- Keep workflow list current
- Test fixes in staging first

### Don'ts ❌
- Don't blindly merge automated PRs
- Don't disable duplicate detection
- Don't ignore rate limits
- Don't skip human review
- Don't forget to update docs

---

## 🔐 Security Considerations

### Permissions Required
```yaml
contents: write      # Create branches, commit files
pull-requests: write # Create and manage PRs
issues: write        # Create and manage issues
actions: read        # Read workflow runs and logs
```

### Security Best Practices
1. Review automated changes
2. Validate fix proposals
3. Check for secrets in logs
4. Monitor for malicious patterns
5. Regular security audits

---

## 📞 Support

### Need Help?
1. Check [Troubleshooting](#troubleshooting)
2. Review [Full Integration Plan](CI_CD_AUTOMATION_INTEGRATION_PLAN.md)
3. Check GitHub Actions logs
4. Open issue for assistance

### Useful Commands
```bash
# View recent workflow failures
gh run list --status=failure --limit 10

# View auto-healing activity
gh issue list --label auto-healing

# Check PR status
gh pr list --label automated-fix

# View workflow logs
gh run view <run-id> --log

# Manually trigger workflow
gh workflow run <workflow-name>
```

---

**Version**: 1.0  
**Last Updated**: 2026-01-29  
**Status**: Reference Guide Complete
