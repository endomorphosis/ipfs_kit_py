# Automated Documentation Maintenance Workflow

## Overview

The automated documentation maintenance workflow keeps the project documentation up-to-date by:
- Extracting docstrings from Python modules
- Generating module structure documentation
- Maintaining dependency lists
- Indexing usage examples
- Creating agent-friendly integration guides

## Schedule

The workflow runs automatically:
- **Weekly**: Every Monday at 9:00 AM UTC
- **Manual**: Can be triggered on-demand

## Generated Documentation

The workflow generates the following files in `docs/api_generated/`:

1. **`module_structure.md`**: Complete module structure with classes, functions, and docstrings
2. **`dependencies.md`**: All project dependencies extracted from `pyproject.toml`
3. **`examples_index.md`**: Index of all example files and test patterns
4. **`AGENT_GUIDE.md`**: Quick reference for programming agents
5. **`doc_status.md`**: Documentation coverage metrics

## Manual Trigger

To manually trigger the workflow:

1. Go to the [Actions tab](https://github.com/endomorphosis/ipfs_kit_py/actions)
2. Select "Automated Documentation Maintenance" workflow
3. Click "Run workflow"
4. Choose the update type (optional):
   - `full` - Complete documentation update (default)
   - `api-only` - Only API documentation
   - `structure-only` - Only module structure

## Workflow Process

1. **Checkout**: Clone the repository with full history
2. **Setup**: Install Python 3.12 and required tools
3. **Extract**: Analyze Python modules and extract docstrings
4. **Generate**: Create markdown documentation files
5. **Check**: Detect if any changes were made
6. **PR**: If changes detected, create a pull request

## Review Process

When the workflow creates a PR:

1. Review the changes in the generated documentation
2. Verify accuracy and completeness
3. Merge if changes look correct
4. The documentation will be available immediately

## Improving Documentation

To improve the automated documentation:

1. **Add docstrings** to your Python modules:
   ```python
   def my_function():
       """
       Brief description of the function.
       
       More details about what it does.
       """
       pass
   ```

2. **Document classes**:
   ```python
   class MyClass:
       """
       Brief description of the class.
       
       This class provides functionality for...
       """
       pass
   ```

3. **Add examples** in the `examples/` directory

4. **Write tests** that demonstrate usage patterns

## Configuration

The workflow configuration is in:
```
.github/workflows/auto-doc-maintenance.yml
```

Key settings:
- **Schedule**: `cron: '0 9 * * 1'` (Monday 9 AM UTC)
- **Python version**: 3.12
- **Tools**: pdoc3, pydoc-markdown, sphinx

## Troubleshooting

### No PR Created

If the workflow runs but no PR is created:
- No documentation changes were detected
- Check the workflow run logs for details

### Workflow Fails

If the workflow fails:
1. Check the [Actions tab](https://github.com/endomorphosis/ipfs_kit_py/actions) for error logs
2. Common issues:
   - Syntax errors in Python files (logged but non-blocking)
   - Missing dependencies (should be rare)
   - Permission issues (check repository settings)

### Generated Documentation Issues

If generated documentation has issues:
1. Check the source docstrings for accuracy
2. Verify Python file syntax
3. Update the extraction script in the workflow if needed

## For Programming Agents

Programming agents can:
- Read the generated `AGENT_GUIDE.md` for quick reference
- Use `module_structure.md` to understand the codebase
- Reference `examples_index.md` for usage patterns
- Check `dependencies.md` for required packages

The documentation is structured to be easily parseable and contains:
- Clear section headers
- Code examples
- Module hierarchy
- Function signatures

## Maintenance

The workflow is designed to be low-maintenance:
- Runs automatically without intervention
- Creates PRs for review (doesn't auto-merge)
- Handles errors gracefully
- Logs all operations

To modify the workflow:
1. Edit `.github/workflows/auto-doc-maintenance.yml`
2. Test locally first (run the Python scripts manually)
3. Commit and push changes
4. Trigger manually to test

## Benefits

This automated approach provides:
- **Consistency**: Documentation always reflects current code
- **Completeness**: All modules documented systematically
- **Freshness**: Weekly updates catch changes
- **Efficiency**: No manual documentation maintenance needed
- **Agent-friendly**: Structured for programmatic consumption
