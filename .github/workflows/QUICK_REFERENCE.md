# Workflow Auto-Fix System - Quick Reference

## 🚀 Quick Start

### When a Workflow Fails

The system automatically:
1. ✅ Creates an issue with details
2. ✅ Creates a draft PR with context
3. ✅ Prepares for GitHub Copilot integration

### Using GitHub Copilot to Fix

#### Method 1: Copilot Workspace (Recommended)
```
1. Find the auto-created draft PR
2. Open it in GitHub Copilot Workspace
3. Ask: "Please analyze the workflow failure and implement a fix"
4. Review and commit the changes
```

#### Method 2: Issue Comment
```
1. Find the auto-created issue
2. Comment: @copilot /fix-workflow
3. Follow the instructions provided
4. Open the PR in Copilot Workspace
```

### Manual Fix
```
1. Find the draft PR
2. Review .github/workflow-failures/ for context
3. Implement the fix
4. Push to the PR branch
5. Mark PR as ready for review
```

## 🧪 Testing the System

Run the test workflow:
```
1. Go to Actions tab
2. Select "Test Workflow Auto-Fix System"
3. Click "Run workflow"
4. Choose a failure type
5. Observe the auto-fix system in action
```

## 📋 Common Scenarios

### Dependency Failure
**Issue**: Package version conflict
**Fix**: Update `pyproject.toml` or `requirements.txt`
**Prompt**: "Fix the dependency version conflict in [file]"

### Test Failure
**Issue**: Unit test fails
**Fix**: Fix code or test logic
**Prompt**: "Analyze and fix the failing test in [file]"

### Syntax Error
**Issue**: YAML syntax error in workflow
**Fix**: Correct indentation or structure
**Prompt**: "Fix the YAML syntax error in [workflow file]"

### Permission Error
**Issue**: Missing workflow permissions
**Fix**: Add required permissions block
**Prompt**: "Add the necessary permissions to [workflow file]"

## 🔍 Finding Auto-Generated Items

### Issues
- Label: `workflow-failure`
- Label: `auto-fix-eligible`
- Title: `[Auto-Fix] Workflow Failed: [name]`

### Pull Requests
- Label: `auto-fix`
- Label: `workflow-failure`
- Status: Draft
- Title: `[Auto-Fix] Fix workflow failure: [name]`

### Branches
- Pattern: `auto-fix/workflow-[run-id]`

## 💡 Best Practices

1. **Review First**: Always review auto-generated context before fixing
2. **Minimal Changes**: Make the smallest change that fixes the issue
3. **Test Locally**: When possible, test fixes before pushing
4. **Document**: Update PR description with what was changed
5. **Close Loop**: Verify the fix actually resolves the failure

## 🛠️ Troubleshooting

### Issue/PR Not Created
- Check workflow permissions
- Verify GITHUB_TOKEN has necessary scopes
- Review workflow run logs

### Copilot Not Responding
- Ensure GitHub Copilot is enabled
- Check you used exact trigger phrase: `@copilot /fix-workflow`
- Verify PR has context files

### Fix Doesn't Work
- Review original failure more carefully
- Check if external factors are involved
- Consider manual implementation

## 📚 Documentation

- **Full Documentation**: [WORKFLOW_AUTOFIX.md](WORKFLOW_AUTOFIX.md)
- **Workflow Files**: [README.md](README.md)
- **Copilot Instructions**: [/.github/copilot-instructions.md](../copilot-instructions.md)

## 🤝 Getting Help

- Create an issue with label `workflow-failure`
- Ask in PR comments
- Check existing issues for similar problems

## 📊 Workflow Statuses

| Status | Meaning |
|--------|---------|
| ✅ Success | No action needed |
| ❌ Failure | Auto-fix triggered |
| 🔄 In Progress | Being fixed |
| ✔️ Fixed | PR merged |

## ⚙️ Configuration Files

| File | Purpose |
|------|---------|
| `workflow-failure-autofix.yml` | Main auto-fix workflow |
| `copilot-auto-fix.yml` | Copilot trigger workflow |
| `copilot-instructions.md` | Instructions for Copilot |
| `WORKFLOW_AUTOFIX.md` | Full documentation |

---

**Need more details?** See [WORKFLOW_AUTOFIX.md](WORKFLOW_AUTOFIX.md) for comprehensive documentation.
