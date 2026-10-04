# P2P Workflow Management Guide

## Overview

The P2P (Peer-to-Peer) Workflow Management system enables GitHub Actions workflows to be executed across a distributed IPFS network, completely bypassing the GitHub API. This system is designed for workflows that:

- Generate new code or perform compute-intensive tasks
- Scrape websites or collect data
- Don't require GitHub's infrastructure
- Should run periodically without hammering GitHub's API

## Key Concepts

### 1. Merkle Clock

A **Merkle Clock** combines Merkle Trees (for cryptographic consistency) with logical clocks (for causal ordering) to maintain a tamper-resistant, distributed log of events.

- Each event is cryptographically hashed
- Events form a chain with parent-child relationships
- All peers can verify the integrity of the event history
- Enables distributed consensus on task assignments

### 2. Hamming Distance

**Hamming Distance** is used to deterministically assign tasks to peers:

```
Combined Hash = SHA256(merkle_clock_head + task_hash)
Peer Hash = SHA256(peer_id)
Distance = hamming_distance(Combined Hash, Peer Hash)
```

The peer with the **minimum** Hamming distance is assigned the task. This ensures:
- Deterministic assignment (all peers agree)
- Even distribution of work
- Fault tolerance (if a peer fails, reassignment occurs)

### 3. Fibonacci Heap

A **Fibonacci Heap** provides efficient priority queue operations for workflow scheduling:

- **O(1)** insert, find-min, decrease-key
- **O(log n)** delete-min (amortized)
- Ideal for dynamic priority scheduling
- Handles resource contention gracefully

## Workflow Tagging

### Marking Workflows for P2P Execution

To mark a workflow for P2P execution, add one of these tags to your workflow file:

```yaml
name: P2P-Workflow Data Scraping
# Tag in workflow name

on:
  schedule:
    - cron: '0 0 * * *'

labels:
  - p2p-workflow  # Explicit label

jobs:
  scrape:
    name: Scrape Website (offline-workflow)
    runs-on: ubuntu-latest
    steps:
      - name: Scrape data
        run: python scrape.py
```

**Supported Tags:**
- `p2p-workflow` - Workflow should run on P2P network
- `offline-workflow` - Workflow runs offline, no GitHub API needed

Tags can appear in:
- Workflow `name`
- Workflow `labels`
- Job `name`
- Job `labels`

## Installation

### As a Python Package

```bash
pip install ipfs_kit_py

# Or from source
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py
pip install -e .
```

### Using in Code

```python
from ipfs_kit_py import (
    P2PWorkflowCoordinator,
    WorkflowStatus,
    MerkleClock,
    FibonacciHeap
)

# Create coordinator
coordinator = P2PWorkflowCoordinator(peer_id="my-peer")

# Add peers to network
coordinator.add_peer("peer-2")
coordinator.add_peer("peer-3")

# Submit a workflow
workflow_id = coordinator.submit_workflow(
    workflow_file=".github/workflows/scrape.yml",
    name="Daily Scraping",
    priority=3.0  # Lower = higher priority
)

# Assign workflows to peers
assigned = coordinator.assign_workflows()

# Check status
status = coordinator.get_workflow_status(workflow_id)
print(f"Workflow status: {status['status']}")

# Update status when complete
coordinator.update_workflow_status(
    workflow_id,
    WorkflowStatus.COMPLETED,
    result={"items_scraped": 1000}
)
```

## CLI Usage

### Setup

The CLI is available as `ipfs-kit p2p`:

```bash
# Set your peer ID
export P2P_PEER_ID="my-unique-peer-id"

# Or it will default to 'cli-peer'
```

### Commands

#### Submit a Workflow

```bash
# Basic submission
ipfs-kit p2p workflow submit .github/workflows/scrape.yml

# With options
ipfs-kit p2p workflow submit .github/workflows/generate.yml \
  --name "Code Generation Task" \
  --priority 1.0 \
  --inputs '{"repo": "owner/name", "branch": "main"}'

# JSON output
ipfs-kit p2p workflow submit workflow.yml --json
```

#### Assign Workflows

```bash
# Assign all pending workflows to peers
ipfs-kit p2p workflow assign

# JSON output
ipfs-kit p2p workflow assign --json
```

#### Check Workflow Status

```bash
# Get status of a specific workflow
ipfs-kit p2p workflow status abc123def456

# JSON output
ipfs-kit p2p workflow status abc123def456 --json
```

#### List Workflows

```bash
# List all workflows
ipfs-kit p2p workflow list

# Filter by status
ipfs-kit p2p workflow list --status pending
ipfs-kit p2p workflow list --status in_progress
ipfs-kit p2p workflow list --status completed

# Filter by peer
ipfs-kit p2p workflow list --peer-id peer-2

# JSON output
ipfs-kit p2p workflow list --json
```

#### Update Workflow Status

```bash
# Update status
ipfs-kit p2p workflow update abc123def456 in_progress

# Complete with result
ipfs-kit p2p workflow update abc123def456 completed \
  --result '{"success": true, "data": "..."}'

# Failed with error
ipfs-kit p2p workflow update abc123def456 failed \
  --error "Connection timeout"
```

#### Manage Peers

```bash
# Add a peer
ipfs-kit p2p peer add peer-alpha

# Remove a peer
ipfs-kit p2p peer remove peer-beta

# List all peers
ipfs-kit p2p peer list
```

#### View Statistics

```bash
# Show coordinator stats
ipfs-kit p2p stats

# JSON output
ipfs-kit p2p stats --json
```

## MCP Server Integration

### Available Tools

The P2P Workflow system exposes 10 MCP tools:

1. **`submit_p2p_workflow`** - Submit a workflow for P2P execution
2. **`assign_p2p_workflows`** - Assign pending workflows using merkle clock
3. **`get_p2p_workflow_status`** - Get workflow status
4. **`list_p2p_workflows`** - List workflows with filtering
5. **`update_p2p_workflow_status`** - Update workflow status
6. **`add_p2p_peer`** - Add peer to network
7. **`remove_p2p_peer`** - Remove peer from network
8. **`get_p2p_stats`** - Get coordinator statistics
9. **`parse_workflow_tags`** - Check if workflow is P2P-eligible
10. **`get_my_p2p_workflows`** - Get workflows assigned to this peer

### Using MCP Tools

```python
from ipfs_kit_py.mcp.p2p_workflow_tools import P2PWorkflowTools

# Create tools instance
tools = P2PWorkflowTools()

# Submit workflow
result = tools.submit_p2p_workflow(
    workflow_file=".github/workflows/scrape.yml",
    name="Daily Scraping",
    priority=3.0
)

# Assign workflows
result = tools.assign_p2p_workflows()

# Get status
result = tools.get_p2p_workflow_status(workflow_id="abc123")

# Get stats
result = tools.get_p2p_stats()
```

### MCP Server Registration

To register these tools in an MCP server:

```python
from ipfs_kit_py.mcp.p2p_workflow_tools import MCP_TOOLS, P2PWorkflowTools

# Create tools instance
p2p_tools = P2PWorkflowTools()

# Register with MCP server
for tool_def in MCP_TOOLS:
    mcp_server.register_tool(
        name=tool_def["name"],
        description=tool_def["description"],
        inputSchema=tool_def["inputSchema"],
        handler=getattr(p2p_tools, tool_def["name"])
    )
```

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Workflow Submission                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Parse Workflow Tags   │
              │  (p2p-workflow?)       │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Add to Priority      │
              │  Queue (Fibonacci     │
              │  Heap)                │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Record in Merkle     │
              │  Clock                │
              └───────────┬───────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Task Assignment                           │
├─────────────────────────────────────────────────────────────┤
│  1. Get Merkle Clock head hash                              │
│  2. Hash task details                                        │
│  3. For each peer:                                           │
│     - Hash peer ID                                           │
│     - Calculate Hamming distance                            │
│  4. Assign to peer with minimum distance                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Peer Executes        │
              │  Workflow             │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Update Status &      │
              │  Results              │
              └───────────────────────┘
```

### State Management

All coordinator state is persisted to `~/.ipfs_kit/p2p_workflows/`:

```
~/.ipfs_kit/p2p_workflows/
├── coordinator_state_peer-1.json
├── coordinator_state_peer-2.json
└── coordinator_state_peer-3.json
```

Each state file contains:
- Peer list
- Merkle clock history
- Workflow queue
- Workflow statuses

### Merkle Clock Structure

```
Node 0 (Root)
├── hash: SHA256(timestamp + peer_id + data)
├── parent_hash: null
├── logical_clock: 1
└── data: {event: "workflow_submitted", ...}
    │
    └─► Node 1
        ├── hash: SHA256(...)
        ├── parent_hash: Node 0 hash
        ├── logical_clock: 2
        └── data: {event: "workflow_assigned", ...}
            │
            └─► Node 2
                ├── hash: SHA256(...)
                ├── parent_hash: Node 1 hash
                ├── logical_clock: 3
                └── data: {event: "workflow_completed", ...}
```

## Examples

### Example 1: Simple Scraping Workflow

```python
from ipfs_kit_py import P2PWorkflowCoordinator

# Initialize coordinator
coordinator = P2PWorkflowCoordinator(peer_id="scraper-1")

# Add peer nodes
coordinator.add_peer("scraper-2")
coordinator.add_peer("scraper-3")

# Submit scraping tasks
sites = ["example.com", "test.com", "demo.org"]
for site in sites:
    coordinator.submit_workflow(
        workflow_file=".github/workflows/scrape.yml",
        name=f"Scrape {site}",
        inputs={"url": site},
        priority=2.0
    )

# Assign tasks to peers
assigned = coordinator.assign_workflows()
print(f"Assigned {len(assigned)} workflows")

# Get my assigned workflows
my_workflows = coordinator.get_my_workflows()
for workflow in my_workflows:
    print(f"Processing: {workflow.name}")
    # ... execute workflow ...
    coordinator.update_workflow_status(
        workflow.workflow_id,
        WorkflowStatus.COMPLETED,
        result={"url": workflow.inputs["url"], "items": 100}
    )
```

### Example 2: Code Generation with Priority

```python
coordinator = P2PWorkflowCoordinator(peer_id="codegen-1")

# High priority: API client generation
coordinator.submit_workflow(
    workflow_file=".github/workflows/generate_api.yml",
    name="Generate API Client",
    priority=1.0  # Highest priority
)

# Medium priority: Documentation
coordinator.submit_workflow(
    workflow_file=".github/workflows/generate_docs.yml",
    name="Generate Documentation",
    priority=3.0
)

# Low priority: Test generation
coordinator.submit_workflow(
    workflow_file=".github/workflows/generate_tests.yml",
    name="Generate Tests",
    priority=5.0
)

# Workflows will be processed in priority order
coordinator.assign_workflows()
```

### Example 3: Monitoring with MCP Tools

```python
from ipfs_kit_py.mcp.p2p_workflow_tools import P2PWorkflowTools

tools = P2PWorkflowTools()

# Get overall statistics
stats = tools.get_p2p_stats()
print(f"Total workflows: {stats['total_workflows']}")
print(f"Queue size: {stats['queue_size']}")
print(f"Peer count: {stats['peer_count']}")

# List pending workflows
pending = tools.list_p2p_workflows(status="pending")
print(f"Pending: {pending['count']}")

# List in-progress workflows
in_progress = tools.list_p2p_workflows(status="in_progress")
for wf in in_progress['workflows']:
    print(f"  {wf['name']} - {wf['assigned_peer']}")

# Check if workflow file is P2P-eligible
result = tools.parse_workflow_tags(
    workflow_file=".github/workflows/my_workflow.yml"
)
if result['is_p2p']:
    print("Workflow is tagged for P2P execution")
```

## Best Practices

### 1. Peer Naming

Use descriptive, unique peer IDs:

```python
# Good
coordinator = P2PWorkflowCoordinator(peer_id="codegen-server-us-east-1")

# Bad
coordinator = P2PWorkflowCoordinator(peer_id="peer1")
```

### 2. Priority Assignment

Use a consistent priority scheme:

- `1.0` - Critical, time-sensitive tasks
- `2.0-3.0` - Normal priority
- `4.0-5.0` - Low priority, background tasks
- `6.0+` - Very low priority

### 3. Error Handling

Always handle workflow failures:

```python
try:
    # Execute workflow
    result = execute_workflow(workflow)
    coordinator.update_workflow_status(
        workflow_id,
        WorkflowStatus.COMPLETED,
        result=result
    )
except Exception as e:
    coordinator.update_workflow_status(
        workflow_id,
        WorkflowStatus.FAILED,
        error=str(e)
    )
```

### 4. State Persistence

Let the coordinator handle state:

```python
# Coordinator automatically saves state
coordinator.submit_workflow(...)
coordinator.assign_workflows()
# State is persisted to disk

# On restart, state is automatically loaded
new_coordinator = P2PWorkflowCoordinator(
    peer_id="same-peer-id"  # Uses same state file
)
```

### 5. Resource Management

Use Fibonacci heap priority for resource contention:

```python
# When resources are limited, high-priority tasks run first
coordinator.submit_workflow(
    workflow_file="critical.yml",
    priority=1.0  # Will run first
)

coordinator.submit_workflow(
    workflow_file="background.yml",
    priority=9.0  # Will run when resources available
)
```

## Troubleshooting

### Workflows Not Being Assigned

**Problem**: Workflows remain in PENDING state

**Solutions**:
1. Check that peers are added:
   ```python
   print(coordinator.peer_list)
   ```

2. Ensure merkle clock has entries:
   ```python
   print(coordinator.merkle_clock.logical_clock)
   ```

3. Manually trigger assignment:
   ```python
   coordinator.assign_workflows()
   ```

### State Not Persisting

**Problem**: State lost between sessions

**Solutions**:
1. Check data directory exists:
   ```python
   print(coordinator.data_dir)
   ```

2. Verify write permissions:
   ```bash
   ls -la ~/.ipfs_kit/p2p_workflows/
   ```

3. Check for errors in logs:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Hamming Distance Always Same

**Problem**: Same peer always gets assigned

**Solutions**:
1. Use more diverse peer IDs
2. Ensure merkle clock is advancing:
   ```python
   coordinator.merkle_clock.append({"event": "heartbeat"})
   ```

3. Add more peers to increase distribution

## API Reference

### MerkleClock

```python
clock = MerkleClock(peer_id="peer-1")

# Append event
node = clock.append({"event": "test", "data": "..."})

# Get head
head = clock.get_head()

# Verify chain
is_valid = clock.verify_chain()

# Serialize
data = clock.to_dict()
new_clock = MerkleClock.from_dict(data)

# Merge clocks
clock.merge(other_clock)
```

### FibonacciHeap

```python
heap = FibonacciHeap()

# Insert
node = heap.insert(key=5.0, value="task-5")

# Find minimum
min_value = heap.find_min()

# Extract minimum
min_value = heap.extract_min()

# Decrease key
heap.decrease_key(node, new_key=3.0)

# Merge heaps
heap.merge(other_heap)
```

### WorkflowPriorityQueue

```python
queue = WorkflowPriorityQueue()

# Add workflow
queue.add_workflow(
    workflow_id="wf-1",
    priority=3.0,
    workflow_data={"name": "Task 1"}
)

# Get next
workflow = queue.get_next_workflow()

# Peek without removing
workflow = queue.peek_next()

# Update priority
queue.update_priority("wf-1", new_priority=1.0)
```

### P2PWorkflowCoordinator

```python
coordinator = P2PWorkflowCoordinator(
    peer_id="peer-1",
    data_dir="~/.ipfs_kit/p2p_workflows"
)

# Submit workflow
workflow_id = coordinator.submit_workflow(
    workflow_file="workflow.yml",
    name="My Workflow",
    inputs={"key": "value"},
    priority=3.0
)

# Assign workflows
assigned = coordinator.assign_workflows()

# Update status
coordinator.update_workflow_status(
    workflow_id,
    WorkflowStatus.COMPLETED,
    result={"output": "..."}
)

# Get status
status = coordinator.get_workflow_status(workflow_id)

# List workflows
workflows = coordinator.list_workflows(
    status=WorkflowStatus.PENDING,
    peer_id="peer-2"
)

# Manage peers
coordinator.add_peer("peer-2")
coordinator.remove_peer("peer-3")

# Get stats
stats = coordinator.get_stats()
```

## Contributing

Contributions are welcome! Areas for improvement:

1. **Network Synchronization**: Automatic peer discovery and clock syncing
2. **Workflow Execution**: Built-in workflow runner for common tasks
3. **Monitoring Dashboard**: Web UI for tracking workflows
4. **Load Balancing**: Dynamic peer weighting based on resources
5. **Fault Tolerance**: Automatic reassignment on peer failure

## License

This project is licensed under AGPL-3.0-or-later. See LICENSE file for details.

## References

- **IPFS Accelerate**: https://github.com/endomorphosis/ipfs_accelerate_py
- **Merkle Trees**: https://en.wikipedia.org/wiki/Merkle_tree
- **Logical Clocks**: https://en.wikipedia.org/wiki/Logical_clock
- **Fibonacci Heap**: https://en.wikipedia.org/wiki/Fibonacci_heap
- **Hamming Distance**: https://en.wikipedia.org/wiki/Hamming_distance
