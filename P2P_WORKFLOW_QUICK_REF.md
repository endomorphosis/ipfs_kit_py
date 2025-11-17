# P2P Workflow Quick Reference

Quick reference guide for using the P2P Workflow Management system.

## Installation

```bash
pip install ipfs_kit_py
```

## Quick Start

### 1. Python API

```python
from ipfs_kit_py import P2PWorkflowCoordinator

# Create coordinator
coord = P2PWorkflowCoordinator(peer_id="my-peer")

# Add peers
coord.add_peer("peer-2")
coord.add_peer("peer-3")

# Submit workflow
wf_id = coord.submit_workflow("workflow.yml", priority=3.0)

# Assign to peers
coord.assign_workflows()

# Check status
status = coord.get_workflow_status(wf_id)
```

### 2. CLI

```bash
# Submit workflow
ipfs-kit p2p workflow submit workflow.yml --priority 3.0

# Assign workflows
ipfs-kit p2p workflow assign

# Check status
ipfs-kit p2p workflow status <workflow_id>

# List workflows
ipfs-kit p2p workflow list

# View stats
ipfs-kit p2p stats
```

### 3. MCP Tools

```python
from ipfs_kit_py.mcp.p2p_workflow_tools import P2PWorkflowTools

tools = P2PWorkflowTools()
tools.submit_p2p_workflow(workflow_file="workflow.yml")
tools.assign_p2p_workflows()
tools.get_p2p_stats()
```

## Workflow Tagging

### Tag Locations

Tags can appear in:
1. Workflow name: `name: P2P-Workflow My Task`
2. Workflow labels: `labels: [p2p-workflow]`
3. Job name: `name: My Job (offline-workflow)`
4. Job labels: `labels: [p2p-workflow]`

### Supported Tags

- `p2p-workflow` - Run on P2P network
- `offline-workflow` - No GitHub API needed

### Example

```yaml
name: P2P-Workflow Data Scraping

labels:
  - p2p-workflow
  - data-collection

jobs:
  scrape:
    name: Scrape Data
    steps:
      - run: python scrape.py
```

## Core Concepts

### Merkle Clock
- Cryptographically verifiable event log
- Distributed consensus mechanism
- Each event has: timestamp, peer_id, data, parent_hash, hash

### Hamming Distance
- Determines task assignment
- `distance = hamming(SHA256(clock_head + task), SHA256(peer_id))`
- Minimum distance = assigned peer

### Fibonacci Heap
- Priority queue for scheduling
- O(1) insert, find-min, decrease-key
- O(log n) delete-min
- Handles resource contention

## CLI Commands

### Workflow Management

```bash
# Submit
ipfs-kit p2p workflow submit <file> [--name NAME] [--priority N] [--inputs JSON]

# Assign
ipfs-kit p2p workflow assign

# Status
ipfs-kit p2p workflow status <id>

# List
ipfs-kit p2p workflow list [--status STATUS] [--peer-id ID]

# Update
ipfs-kit p2p workflow update <id> <status> [--result JSON] [--error MSG]
```

### Peer Management

```bash
# Add peer
ipfs-kit p2p peer add <peer_id>

# Remove peer
ipfs-kit p2p peer remove <peer_id>

# List peers
ipfs-kit p2p peer list
```

### Statistics

```bash
# View stats
ipfs-kit p2p stats [--json]
```

## MCP Tools (10 total)

1. `submit_p2p_workflow` - Submit workflow
2. `assign_p2p_workflows` - Assign to peers
3. `get_p2p_workflow_status` - Get status
4. `list_p2p_workflows` - List with filters
5. `update_p2p_workflow_status` - Update status
6. `add_p2p_peer` - Add peer
7. `remove_p2p_peer` - Remove peer
8. `get_p2p_stats` - Get statistics
9. `parse_workflow_tags` - Check P2P eligibility
10. `get_my_p2p_workflows` - Get my workflows

## Priority Levels

```python
1.0   # Critical, time-sensitive
2.0   # High priority
3.0   # Normal priority (default)
4.0   # Low priority
5.0   # Background tasks
6.0+  # Very low priority
```

## Workflow Statuses

- `pending` - Submitted, waiting for assignment
- `assigned` - Assigned to peer
- `in_progress` - Currently executing
- `completed` - Successfully completed
- `failed` - Execution failed
- `cancelled` - Manually cancelled

## Common Patterns

### Submit Multiple Workflows

```python
workflows = [
    ("scrape.yml", 3.0),
    ("generate.yml", 1.0),
    ("process.yml", 2.0)
]

for file, priority in workflows:
    coord.submit_workflow(file, priority=priority)

coord.assign_workflows()
```

### Monitor Execution

```python
import time

while True:
    my_workflows = coord.get_my_workflows()
    
    for wf in my_workflows:
        if wf.status == WorkflowStatus.ASSIGNED:
            # Execute workflow
            execute(wf)
            coord.update_workflow_status(
                wf.workflow_id,
                WorkflowStatus.COMPLETED
            )
    
    time.sleep(60)
```

### Error Handling

```python
try:
    result = execute_workflow(workflow)
    coord.update_workflow_status(
        wf_id,
        WorkflowStatus.COMPLETED,
        result=result
    )
except Exception as e:
    coord.update_workflow_status(
        wf_id,
        WorkflowStatus.FAILED,
        error=str(e)
    )
```

## Data Locations

```
~/.ipfs_kit/p2p_workflows/
├── coordinator_state_peer-1.json
├── coordinator_state_peer-2.json
└── coordinator_state_peer-3.json
```

## Environment Variables

```bash
# Set your peer ID
export P2P_PEER_ID="my-unique-peer"

# Data directory (optional)
export P2P_DATA_DIR="~/.ipfs_kit/p2p_workflows"
```

## Troubleshooting

### Workflows Not Assigning

```python
# Check peers
print(coord.peer_list)

# Check clock
print(coord.merkle_clock.logical_clock)

# Manually assign
coord.assign_workflows()
```

### State Not Persisting

```bash
# Check directory
ls -la ~/.ipfs_kit/p2p_workflows/

# Check permissions
chmod 755 ~/.ipfs_kit/p2p_workflows/
```

### Tag Not Detected

```python
# Verify tags
from ipfs_kit_py import P2PWorkflowCoordinator
coord = P2PWorkflowCoordinator(peer_id="test")
metadata = coord.parse_workflow_file("workflow.yml")
print(f"Is P2P: {coord.is_p2p_workflow(metadata)}")
print(f"Tags: {metadata.get('tags')}")
```

## Examples

See `examples/p2p_workflows/` for:
- `scrape_website.yml` - Web scraping
- `generate_code.yml` - Code generation
- `process_dataset.yml` - Data processing

## API Reference

### Classes

- `MerkleClock(peer_id)` - Event log
- `FibonacciHeap()` - Priority queue
- `WorkflowPriorityQueue()` - Workflow queue
- `P2PWorkflowCoordinator(peer_id, data_dir)` - Main coordinator
- `WorkflowStatus` - Status enum
- `WorkflowTask` - Task dataclass

### Functions

- `hamming_distance(hash1, hash2)` - Calculate distance
- `select_task_owner(clock_head, task_hash, peers)` - Select peer
- `create_task_hash(workflow_data)` - Create hash

## Performance

- Merkle clock append: O(1)
- Fibonacci heap insert: O(1)
- Fibonacci heap extract-min: O(log n) amortized
- Task assignment: O(n) where n = number of peers
- State persistence: O(m) where m = number of workflows

## Limits

- No hard limit on workflows
- No hard limit on peers
- State file size grows with history
- Merkle clock can be pruned if needed

## Further Reading

- [Full Guide](P2P_WORKFLOW_GUIDE.md)
- [Examples](examples/p2p_workflows/README.md)
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [IPFS Docs](https://docs.ipfs.tech/)

## Support

- Issues: https://github.com/endomorphosis/ipfs_kit_py/issues
- Discussions: https://github.com/endomorphosis/ipfs_kit_py/discussions
