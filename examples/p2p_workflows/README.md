# P2P Workflow Examples

This directory contains example GitHub Actions workflows that are tagged for peer-to-peer execution across the IPFS network.

## Workflow Files

### 1. scrape_website.yml

**Purpose**: Web scraping workflow that collects data from websites

**Tags**: `p2p-workflow`, `offline-workflow`, `data-collection`

**Features**:
- Scheduled daily execution
- Configurable URL and scraping depth
- Uploads results to IPFS
- No GitHub API dependency

**Usage**:
```bash
ipfs-kit p2p workflow submit examples/p2p_workflows/scrape_website.yml \
  --name "Daily Scraping" \
  --priority 3.0 \
  --inputs '{"url": "https://example.com", "depth": "2"}'
```

### 2. generate_code.yml

**Purpose**: Code generation from OpenAPI specifications

**Tags**: `offline-workflow`, `code-generation`, `high-compute`

**Features**:
- Generates code from OpenAPI specs
- Multiple language support
- Automatic testing of generated code
- IPFS storage of generated artifacts

**Usage**:
```bash
ipfs-kit p2p workflow submit examples/p2p_workflows/generate_code.yml \
  --name "API Client Generation" \
  --priority 1.0 \
  --inputs '{"template": "api-client", "language": "python", "spec_url": "https://api.example.com/openapi.yaml"}'
```

### 3. process_dataset.yml

**Purpose**: Heavy data processing and transformation

**Tags**: `p2p-workflow`, `data-processing`, `high-memory`

**Features**:
- Retrieves datasets from IPFS
- Multiple processing types (transform, aggregate, analyze)
- Generates analysis reports
- Stores results back to IPFS

**Usage**:
```bash
ipfs-kit p2p workflow submit examples/p2p_workflows/process_dataset.yml \
  --name "Dataset Processing" \
  --priority 2.0 \
  --inputs '{"dataset_cid": "QmXyz...", "processing_type": "transform"}'
```

## Tagging Conventions

### Primary Tags

- **`p2p-workflow`**: Workflow should be executed on P2P network
- **`offline-workflow`**: Workflow can run completely offline without GitHub API

### Secondary Tags (Optional)

- **`data-collection`**: Workflow collects or scrapes data
- **`code-generation`**: Workflow generates code
- **`data-processing`**: Workflow processes large datasets
- **`high-compute`**: Workflow requires significant CPU
- **`high-memory`**: Workflow requires significant RAM

### Where Tags Can Appear

Tags can be specified in multiple locations within a workflow file:

1. **Workflow Name**:
   ```yaml
   name: P2P-Workflow My Task
   ```

2. **Workflow Labels**:
   ```yaml
   labels:
     - p2p-workflow
     - data-processing
   ```

3. **Job Name**:
   ```yaml
   jobs:
     my_job:
       name: My Task (offline-workflow)
   ```

4. **Job Labels**:
   ```yaml
   jobs:
     my_job:
       labels:
         - p2p-workflow
   ```

## Testing Workflows Locally

Before submitting to the P2P network, test workflows locally:

```bash
# Parse and validate workflow tags
python -c "
from ipfs_kit_py import P2PWorkflowCoordinator
coordinator = P2PWorkflowCoordinator(peer_id='test')
metadata = coordinator.parse_workflow_file('examples/p2p_workflows/scrape_website.yml')
print(f'Is P2P workflow: {coordinator.is_p2p_workflow(metadata)}')
print(f'Tags: {metadata.get(\"tags\")}')
"
```

## Creating Your Own P2P Workflows

### Template

```yaml
name: P2P-Workflow Your Workflow Name

on:
  # Your triggers
  workflow_dispatch:

labels:
  - p2p-workflow  # Required for P2P execution
  - your-other-tags

jobs:
  your_job:
    name: Your Job Name
    runs-on: ubuntu-latest
    
    steps:
      - name: Your steps
        run: |
          # Your workflow logic
          # Avoid GitHub API calls
          # Store results in IPFS when possible
```

### Best Practices

1. **Avoid GitHub API**: Don't use actions that require GitHub API access
2. **Use IPFS for Storage**: Store large outputs in IPFS instead of artifacts
3. **Self-Contained**: Include all dependencies in the workflow
4. **Resource Tags**: Tag workflows with resource requirements
5. **Error Handling**: Include proper error handling and logging
6. **Idempotent**: Make workflows safe to re-run

### Anti-Patterns

❌ **Don't do this**:
```yaml
- name: Create GitHub issue
  uses: actions/github-script@v6
  # This requires GitHub API!
```

✅ **Do this instead**:
```yaml
- name: Store results
  run: |
    ipfs add results.json
    # Store in distributed filesystem
```

## Workflow Lifecycle

1. **Submission**: Workflow submitted to P2P network
   ```bash
   ipfs-kit p2p workflow submit workflow.yml
   ```

2. **Assignment**: Coordinator assigns to peer using merkle clock + hamming distance
   ```bash
   ipfs-kit p2p workflow assign
   ```

3. **Execution**: Assigned peer executes the workflow

4. **Status Updates**: Peer updates status as workflow progresses
   ```bash
   ipfs-kit p2p workflow update <id> in_progress
   ipfs-kit p2p workflow update <id> completed --result '{...}'
   ```

5. **Completion**: Results stored and accessible via IPFS

## Monitoring

### Check Workflow Status

```bash
# Get specific workflow
ipfs-kit p2p workflow status <workflow_id>

# List all workflows
ipfs-kit p2p workflow list

# List by status
ipfs-kit p2p workflow list --status pending
ipfs-kit p2p workflow list --status in_progress
ipfs-kit p2p workflow list --status completed

# List by peer
ipfs-kit p2p workflow list --peer-id peer-1
```

### View Statistics

```bash
# Overall stats
ipfs-kit p2p stats

# JSON output for automation
ipfs-kit p2p stats --json
```

## Troubleshooting

### Workflow Not Being Assigned

**Problem**: Workflow stays in PENDING state

**Solutions**:
1. Check peer list: `ipfs-kit p2p peer list`
2. Manually assign: `ipfs-kit p2p workflow assign`
3. Check workflow tags are correct

### Execution Failures

**Problem**: Workflow fails during execution

**Solutions**:
1. Check workflow logs
2. Test workflow locally first
3. Ensure all dependencies are included
4. Verify IPFS connectivity

### Tag Not Detected

**Problem**: Workflow not recognized as P2P

**Solutions**:
1. Verify tag spelling (`p2p-workflow` or `offline-workflow`)
2. Check tag placement (workflow name, labels, job name, or job labels)
3. Use parse tool to verify:
   ```bash
   python -c "
   from ipfs_kit_py.mcp.p2p_workflow_tools import P2PWorkflowTools
   tools = P2PWorkflowTools()
   result = tools.parse_workflow_tags('workflow.yml')
   print(result)
   "
   ```

## Contributing

To add new example workflows:

1. Create workflow file with proper tags
2. Add description to this README
3. Test locally before submitting
4. Include usage examples

## Further Reading

- [P2P Workflow Guide](../../P2P_WORKFLOW_GUIDE.md)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [IPFS Documentation](https://docs.ipfs.tech/)
