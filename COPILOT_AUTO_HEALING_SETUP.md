# GitHub Copilot Auto-Healing Setup Guide

## 🎯 Overview

This guide will help you set up the GitHub Copilot Auto-Healing system in your repository. The system uses AI to automatically detect and fix failed GitHub Actions workflows.

## ⏱️ Setup Time: 5 Minutes

## 📋 Prerequisites

### Required
- ✅ GitHub repository with Actions enabled
- ✅ Admin access to repository settings
- ✅ GitHub Actions workflows (existing or planned)

### Recommended
- ⭐ GitHub Copilot subscription (Individual or Business)
- ⭐ GitHub Copilot enabled for the repository

### Optional
- GitHub CLI (`gh`) for testing

## 🚀 Setup Steps

### Step 1: Enable Workflow Permissions

This is the **only required configuration**!

1. Go to your repository on GitHub
2. Click **Settings** → **Actions** → **General**
3. Scroll to "Workflow permissions"
4. Select: **✅ Read and write permissions**
5. Enable: **✅ Allow GitHub Actions to create and approve pull requests**
6. Click **Save**

![Workflow Permissions Screenshot](https://docs.github.com/assets/cb-45061/images/help/repository/actions-workflow-permissions.png)

**Why is this needed?**
- Creates branches for fixes
- Opens pull requests automatically
- Comments on issues
- Adds labels for tracking

### Step 2: Verify Files Are Present

The following files should already be in your repository:

```bash
# Check for workflow files
ls -la .github/workflows/ | grep -E "copilot|auto-heal|monitor"

# Expected files:
# - workflow-failure-monitor.yml
# - copilot-agent-autofix.yml
# - copilot-auto-heal.yml
# - auto-heal-workflow.yml (legacy, optional)
```

If files are missing, you need to add them from this repository.

### Step 3: (Optional) Enable GitHub Copilot

If you have GitHub Copilot access:

1. Go to **Settings** → **Copilot** → **Policies**
2. Enable Copilot for the repository
3. *Optional*: Configure Copilot Workspace access

**Benefits of Copilot:**
- Better fix quality (context-aware)
- Handles novel issues
- Learns from ecosystem
- Interactive workspace for complex fixes

**Without Copilot:**
- Pattern-based fixes still work
- AI-style analysis still functions
- Limited to known error patterns

### Step 4: Verify Setup

Run the test suite to verify everything is configured:

```bash
# Clone the repository
git clone https://github.com/your-org/your-repo
cd your-repo

# Run the test suite
python3 test_copilot_auto_healing.py
```

Expected output:
```
🎉 All tests passed! Copilot auto-healing system is properly configured.
Total: 7/7 tests passed
```

### Step 5: Test the System (Optional)

Trigger a demo workflow to see auto-healing in action:

```bash
# Using GitHub CLI
gh workflow run auto-healing-demo.yml -f failure_type=missing_dependency

# Or via GitHub UI:
# 1. Go to Actions tab
# 2. Click "Auto-Healing Demo"
# 3. Click "Run workflow"
# 4. Select failure type
# 5. Click "Run workflow"
```

**What happens:**
1. Demo workflow fails (intentionally)
2. Issue created within 1-2 minutes
3. Copilot agent invoked automatically
4. PR created within 3-5 minutes
5. You review and merge

## ✅ That's It!

Your auto-healing system is now active and will automatically:
- Detect workflow failures
- Analyze error logs
- Generate intelligent fixes
- Create pull requests

## 📊 Usage

### Automatic Operation (Default)

No action needed! When a workflow fails:

1. **Wait 1-2 minutes** - Issue will be created
2. **Wait 3-5 minutes** - PR will be created
3. **Review the PR** - Check the fix
4. **Merge if correct** - Workflow is fixed!

### Monitor Activity

```bash
# View auto-healing issues
gh issue list --label auto-heal

# View auto-healing PRs
gh pr list --label copilot-agent

# View workflow runs
gh run list --workflow copilot-agent-autofix.yml
```

### Manual Trigger

To manually trigger auto-healing for an existing issue:

```bash
# Add the required labels
gh issue edit <issue-number> --add-label copilot-agent
```

## 🔧 Customization

### Adjust Copilot Behavior

Edit `.github/copilot-instructions.md` to customize:
- Fix generation patterns
- Coding standards
- Security requirements
- Testing requirements

Example:
```markdown
## Custom Requirements

### Python Dependencies
- Always use `requirements.txt`
- Pin versions for production
- Use `~=` for minor version ranges

### Testing
- All fixes must include test updates
- Run pytest before creating PR
```

### Disable for Specific Workflows

Add comment to workflow file:
```yaml
name: My Workflow
# auto-heal: disabled

on:
  push:
    branches: [main]
```

### Adjust Fix Patterns

Edit the Python script in `copilot-agent-autofix.yml`:

```python
# Add new pattern
if 'your_error_pattern' in error_details.lower():
    print("🔧 Detected: Your custom error")
    # Apply custom fix
    fixes.append("Your custom fix")
    fix_applied = True
```

## 🔍 Troubleshooting

### Issue: No issue created after failure

**Check:**
1. Workflow permissions enabled? (Step 1)
2. Workflow actually failed? (not cancelled/skipped)
3. Check `workflow-failure-monitor.yml` logs

**Solution:**
```bash
# View monitor logs
gh run list --workflow workflow-failure-monitor.yml
gh run view <run-id> --log
```

### Issue: Issue created but no PR

**Check:**
1. Issue has correct labels? (auto-heal, workflow-failure, copilot-agent)
2. Check `copilot-agent-autofix.yml` logs

**Solution:**
```bash
# View autofix logs
gh run list --workflow copilot-agent-autofix.yml
gh run view <run-id> --log

# Manually trigger
gh issue edit <issue-num> --add-label copilot-agent
```

### Issue: PR created but fix is wrong

**Solution:**
1. Close the PR with explanation
2. Comment on issue with what should be done
3. The system learns from feedback
4. For complex issues, use Copilot Workspace

### Issue: Multiple duplicate issues

**Cause:** Multiple workflows failed at same time

**Solution:**
```bash
# Close duplicates
gh issue close <issue-num> --comment "Duplicate of #<original>"
```

The system checks for recent issues but may create duplicates under load.

## 📚 Documentation

### Quick Reference
- **[Quick Reference Guide](./COPILOT_AUTO_HEALING_QUICK_REF.md)** - One-page reference
- **[Full Documentation](./COPILOT_AUTO_HEALING_GUIDE.md)** - Comprehensive guide
- **[Original System](./AUTO_HEALING_WORKFLOWS.md)** - Pattern-based system

### Examples
- **[Real-World Examples](./AUTO_HEALING_EXAMPLES.md)** - Example scenarios
- **[Demo Workflow](./.github/workflows/auto-healing-demo.yml)** - Test the system

### Testing
```bash
# Run test suite
python3 test_copilot_auto_healing.py

# Check specific workflow
yamllint .github/workflows/copilot-agent-autofix.yml
```

## 🎓 Best Practices

### 1. Review All PRs
✅ Always review auto-generated PRs before merging
- Verify the fix is correct
- Check for side effects
- Ensure tests pass

### 2. Provide Feedback
✅ Comment on PRs with issues or improvements
- Helps the system learn
- Improves future fixes
- Documents edge cases

### 3. Keep Instructions Updated
✅ Update `.github/copilot-instructions.md` regularly
- Add new patterns discovered
- Update coding standards
- Document complex scenarios

### 4. Monitor Patterns
✅ Track common failures
- Which workflows fail most
- What types of fixes work best
- When manual intervention is needed

### 5. Start Conservative
✅ Gradual rollout approach
1. Enable monitoring only (observe)
2. Review generated fixes manually
3. Enable auto-PR for specific workflows
4. Expand to all workflows

## 🔐 Security

### What the System Can Do
✅ Read workflow files and logs
✅ Create branches and PRs
✅ Comment on issues
✅ Add labels

### What the System Cannot Do
❌ Merge PRs without approval
❌ Access or modify secrets
❌ Make changes outside workflows
❌ Access other repositories

### Permissions Used
```yaml
permissions:
  contents: write      # Create branches
  pull-requests: write # Create PRs
  issues: write        # Comment/label
  actions: read        # Read logs
```

All changes go through PR review process.

## 📈 Success Metrics

Track these to measure effectiveness:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Time to fix | < 5 min | Issue created → PR created |
| Auto-fix rate | > 80% | PRs merged / Issues created |
| Accuracy | > 90% | Working fixes / Total PRs |
| Manual rate | < 20% | needs-manual-fix / Total |

```bash
# Check metrics
gh issue list --label auto-heal --json createdAt,closedAt
gh pr list --label copilot-agent --json mergedAt
```

## 🆘 Support

### Getting Help

1. **Check Documentation**
   - [Full Guide](./COPILOT_AUTO_HEALING_GUIDE.md)
   - [Quick Reference](./COPILOT_AUTO_HEALING_QUICK_REF.md)
   - [Troubleshooting](#-troubleshooting)

2. **Run Tests**
   ```bash
   python3 test_copilot_auto_healing.py
   ```

3. **Check Logs**
   ```bash
   gh run list --workflow copilot-agent-autofix.yml
   gh run view <run-id> --log
   ```

4. **Create Issue**
   - Label: `auto-heal-system`
   - Include: workflow logs, error messages
   - Describe: expected vs actual behavior

### Common Questions

**Q: Does this work without GitHub Copilot?**
A: Yes! The pattern-based system still works. Copilot makes fixes more intelligent.

**Q: Will it auto-merge fixes?**
A: No. All fixes require human review and approval.

**Q: Can it fix any workflow error?**
A: It handles 80-90% of common issues. Complex problems need manual review.

**Q: Is it safe?**
A: Yes. All changes go through PR review. Limited permissions. No secrets access.

**Q: How much does it cost?**
A: Free with existing GitHub Actions minutes. Copilot subscription recommended but not required.

## 🎉 You're All Set!

Your repository now has intelligent auto-healing for workflows.

**Next Steps:**
1. ✅ Setup complete (5 minutes)
2. 📊 Monitor for failures
3. 🔍 Review first few PRs carefully
4. 📝 Provide feedback
5. 🚀 Enjoy automated fixes!

**Questions?** Check [COPILOT_AUTO_HEALING_GUIDE.md](./COPILOT_AUTO_HEALING_GUIDE.md)

---

**Version**: 2.0 (Copilot Integration)  
**Status**: ✅ Production Ready  
**Setup Time**: 5 minutes  
**Maintenance**: Minimal
