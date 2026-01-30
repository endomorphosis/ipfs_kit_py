# GitHub Actions Auto-Healing Scripts

This directory contains Python scripts for automated workflow failure analysis and fix generation.

## Scripts

### 1. analyze_workflow_failure.py

Analyzes GitHub Actions workflow failures to identify root causes and suggest fixes.

**Usage:**
```bash
python3 analyze_workflow_failure.py \
  --run-id <workflow_run_id> \
  --workflow-name "Workflow Name" \
  --logs-dir /path/to/logs \
  --output /path/to/analysis.json
```

**Features:**
- Parses workflow logs and identifies error patterns
- Supports 9 error types (dependencies, timeouts, Docker, etc.)
- Calculates confidence scores (0-100%)
- Generates fix recommendations
- Extracts affected files

**Output:**
JSON file containing:
- Error type and fix type
- Root cause analysis
- Confidence score
- Captured values (e.g., missing package names)
- Recommendations
- Log snippets

### 2. generate_workflow_fix.py

Generates fix proposals based on failure analysis.

**Usage:**
```bash
python3 generate_workflow_fix.py \
  --analysis /path/to/analysis.json \
  --workflow-name "Workflow Name" \
  --output /path/to/fix-proposal.json
```

**Features:**
- Creates detailed fix proposals
- Generates PR title and description
- Suggests specific code changes
- Determines branch name
- Adds appropriate labels

**Output:**
JSON file containing:
- Branch name
- PR title and description
- List of proposed fixes
- Analysis summary
- Labels to apply

### 3. generate_workflow_list.py

Scans the workflows directory and generates a list of workflow names.

**Usage:**
```bash
# YAML format (for workflow files)
python3 generate_workflow_list.py yaml

# JSON format
python3 generate_workflow_list.py json

# Count workflows
python3 generate_workflow_list.py count

# Plain list
python3 generate_workflow_list.py list
```

**Features:**
- Scans `.github/workflows/*.yml` and `*.yaml` files
- Extracts workflow names from YAML
- Excludes auto-healing workflows
- Supports multiple output formats

**Output:**
List of workflow names in specified format

### 4. update_autofix_workflow_list.py

Updates the workflow_run trigger in copilot-agent-autofix.yml automatically.

**Usage:**
```bash
python3 update_autofix_workflow_list.py
```

**Features:**
- Scans for all workflows
- Updates copilot-agent-autofix.yml
- Maintains exclusion list
- Validates YAML syntax

**Output:**
Updates the workflow file in-place

## Error Patterns Detected

| Pattern | Confidence | Fix Type | Auto-PR |
|---------|-----------|----------|---------|
| Missing Dependency | 90% | add_dependency | ✅ |
| Syntax Error | 85% | fix_syntax | ❌ |
| Test Failure | 70% | fix_test | ❌ |
| Timeout | 95% | increase_timeout | ✅ |
| Permission Error | 80% | fix_permissions | ❌ |
| Network Error | 75% | add_retry | ✅ |
| Docker Error | 85% | fix_docker | ✅ |
| Resource Exhaustion | 90% | increase_resources | ✅ |
| Missing Env Variable | 95% | add_env_variable | ❌ |

## Configuration

The automation scripts use built-in pattern matching and configuration. Error patterns, confidence scores, and fix generation logic are defined directly in the Python scripts:

- **analyze_workflow_failure.py**: Contains error pattern definitions with regex matching and confidence calculation
- **generate_workflow_fix.py**: Contains fix generation logic and templates

While `.github/workflows/workflow-auto-fix-config.yml` exists as a reference configuration file showing the error pattern schema, the scripts currently use hard-coded patterns for simplicity. Future versions may load this configuration file dynamically.

**Current Approach:**
- **Error patterns**: Hard-coded in analyze_workflow_failure.py
- **Rate limits**: Not currently enforced (future feature)
- **Excluded workflows**: Defined in generate_workflow_list.py
- **PR/Issue templates**: Generated in generate_workflow_fix.py

## Dependencies

```bash
pip install PyYAML requests PyGithub
```

## Testing

Test the scripts locally:

```bash
# Test workflow list generation
python3 .github/scripts/generate_workflow_list.py count

# Test with sample logs
mkdir -p /tmp/test-logs
echo "ERROR: ModuleNotFoundError: No module named 'pytest'" > /tmp/test-logs/test.log

python3 .github/scripts/analyze_workflow_failure.py \
  --run-id 12345 \
  --workflow-name "Test Workflow" \
  --logs-dir /tmp/test-logs \
  --output /tmp/analysis.json

cat /tmp/analysis.json
```

## Integration

These scripts are used by:
- `.github/workflows/copilot-agent-autofix-enhanced.yml` - Main auto-healing workflow

## Maintenance

**Update workflow list:**
```bash
python3 .github/scripts/update_autofix_workflow_list.py
```

Run this command whenever you:
- Add new workflows
- Rename existing workflows
- Want to refresh the monitored list

## Troubleshooting

**Script fails with "No module named 'yaml'":**
```bash
pip install PyYAML
```

**Workflow list is empty:**
- Check that workflows exist in `.github/workflows/`
- Ensure workflows have `name:` field in YAML

**Analysis confidence is low:**
- Add more error patterns to the configuration
- Improve log content with more details
- Check that logs contain error messages

## Contributing

When adding new error patterns:

1. Add pattern to `FAILURE_PATTERNS` in `analyze_workflow_failure.py`
2. Add fix generator in `generate_workflow_fix.py`
3. Update configuration in `workflow-auto-fix-config.yml`
4. Test with sample logs
5. Update this README

## License

Same as parent repository (AGPL-3.0)
