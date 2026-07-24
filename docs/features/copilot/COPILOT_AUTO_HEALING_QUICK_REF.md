# Copilot Auto-Healing Quick Reference

## 🚀 Quick Start

### For Repository Admins

1. **Enable Permissions** (Settings → Actions → General):
   - ✅ Read and write permissions
   - ✅ Allow GitHub Actions to create PRs

2. **That's it!** The system is ready to use.

### For Developers

**When a workflow fails:**
1. Wait 2-3 minutes
2. Check Issues tab for auto-heal issue
3. Check PRs tab for Copilot-generated fix
4. Review and merge the PR

## 📋 Key Commands

```bash
# View auto-healing activity
gh issue list --label auto-heal
gh pr list --label copilot-agent

# Manually trigger for an issue
gh issue edit <issue-number> --add-label copilot-agent

# View workflow logs
gh run list --workflow copilot-agent-autofix.yml
gh run view <run-id> --log

# Test the system
python3 test_copilot_auto_healing.py
```

## 🏷️ Important Labels

- `auto-heal` - Enables auto-healing
- `workflow-failure` - Marks workflow failure
- `copilot-agent` - Triggers Copilot agent
- `copilot-invoked` - Copilot is working
- `needs-manual-fix` - Skips auto-healing

## 🔄 Workflow Triggers

### Automatic (Default)
```
Workflow Fails → Issue Created → Copilot Fixes → PR Created
```

### Manual Trigger
```bash
# Add labels to existing issue
gh issue edit <issue-num> --add-label auto-heal,workflow-failure,copilot-agent
```

### Using Copilot Workspace
```
1. Issue created with workspace link
2. Click "Open in Copilot Workspace"
3. Ask Copilot to fix the issue
4. Review and apply suggestions
5. Create PR from workspace
```

## 📁 Key Files

```
.github/
├── workflows/
│   ├── workflow-failure-monitor.yml    # Detects failures
│   ├── copilot-agent-autofix.yml      # AI-powered fixes
│   └── copilot-auto-heal.yml          # Workspace integration
└── copilot-instructions.md             # Copilot guidance

COPILOT_AUTO_HEALING_GUIDE.md          # Full documentation
test_copilot_auto_healing.py           # Test suite
```

## 🔧 Common Fixes Applied

| Error Type | Fix Applied |
|------------|-------------|
| Missing dependency | Add pip/npm install |
| Timeout | Increase timeout-minutes |
| YAML syntax | Fix indentation/structure |
| Permissions | Add required permissions |
| Command not found | Add installation step |
| File not found | Fix path or add checkout |

## ⚙️ Configuration

### Customize Copilot Behavior
Edit `.github/copilot-instructions.md`

### Disable for Specific Workflows
Add to workflow file:
```yaml
# auto-heal: disabled
```

### Adjust Fix Patterns
Edit `copilot-agent-autofix.yml` Python script

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| No issue created | Check workflow-failure-monitor logs |
| No PR created | Verify labels on issue |
| Wrong fix | Close PR, comment with feedback |
| Multiple PRs | Check for duplicate issues |

## 📊 Success Metrics

Track these to measure effectiveness:
- Time from failure to PR (target: <5 min)
- Auto-fix merge rate (target: >80%)
- Manual intervention rate (target: <20%)

## 🔗 Quick Links

- [Full Guide](./COPILOT_AUTO_HEALING_GUIDE.md) - Comprehensive documentation
- [Original Auto-Healing](../auto-healing/AUTO_HEALING_WORKFLOWS.md) - Pattern-based system
- [Quick Start](../auto-healing/AUTO_HEALING_QUICK_START.md) - 5-minute setup
- [Examples](../auto-healing/AUTO_HEALING_EXAMPLES.md) - Real-world scenarios

## 💡 Tips

1. **Review All PRs** - Even auto-generated ones need human review
2. **Provide Feedback** - Comment on PRs to improve the system
3. **Use Workspace** - For complex issues, use Copilot Workspace
4. **Monitor Patterns** - Track common failures and update fix logic
5. **Start Conservative** - Begin with review-only mode

## 🎯 Best Practices

✅ **Do:**
- Review all auto-generated PRs before merging
- Provide feedback on incorrect fixes
- Keep Copilot instructions updated
- Monitor auto-healing success rate
- Use workspace for complex fixes

❌ **Don't:**
- Auto-merge without review
- Ignore failed auto-heal attempts
- Disable without understanding why
- Skip testing after merge
- Forget to update documentation

## 📞 Support

1. **Check Logs**: `gh run view --log`
2. **Run Tests**: `python3 test_copilot_auto_healing.py`
3. **Review Docs**: See COPILOT_AUTO_HEALING_GUIDE.md
4. **Create Issue**: Label with `auto-heal-system`

---

**Version**: 2.0 (Copilot Integration)  
**Status**: ✅ Production Ready  
**Last Updated**: October 2025
