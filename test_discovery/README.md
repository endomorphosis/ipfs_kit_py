# MCP Discovery Protocol Tests

This directory contains tests for the MCP (Model-Controller-Persistence) Discovery Protocol, which enables servers to discover and collaborate with each other in distributed environments.

## Test Structure

The tests are organized in the following way:

- **Basic Tests**: Simple connectivity and discovery tests
- **Enhanced Tests**: More complex scenarios including network partitions
- **Mock Implementation**: Simulated network and server implementation

## Network Partition Test Suite

This suite contains specialized tests that simulate various network partition scenarios to ensure the MCP Discovery Protocol can handle real-world network failures.

### Available Network Partition Tests

1. **Basic Network Partition**: Simple partition between two groups of servers
2. **Asymmetric Network Partition**: Network partition where connectivity is not symmetric
3. **Intermittent Connectivity**: Random connection drops and restorations
4. **Time-based Recovery**: Network partitions that heal based on time
5. **Cascading Network Failures**: Progressive failures that spread across the system

### Running Network Partition Tests

#### Run All Network Partition Tests

To run all network partition tests and generate a combined report:

```
./run_all_network_partition_tests.py
```

This will execute all tests and save results to `network_partition_test_report.json`.

#### View Test Results

To view test results in a readable format:

```
./view_network_partition_report.py
```

#### Run Individual Tests

To run specific tests:

1. Run just the cascading network failures test:
   ```
   ./run_mcp_cascading_failures_test.py
   ```

2. Run a specific test using the enhanced test runner:
   ```
   ./run_enhanced_test.py test_cascading_network_failures
   ```

## Test Implementation Details

### Mock Network

The tests use a `MockNetwork` class that simulates network connectivity between nodes:

- Nodes can be added and removed from the network
- Connections between nodes can be modified
- Network partitions can be simulated and resolved

### Test Scenarios

1. **Cascading Network Failures Test**:
   - Simulates progressive network degradation
   - Tests server behavior during spreading failures
   - Verifies recovery capabilities
   - Includes six distinct test phases:
     1. Initial full connectivity
     2. First failure (isolated node)
     3. Cascading failure (network partition)
     4. Progressive node failures within groups
     5. Partial recovery process
     6. Full recovery process

## Extending the Tests

To add a new network partition test:

1. Add your test method to `enhanced_mcp_discovery_test.py`
2. Create a runner script for your test if needed
3. Add your test to the `PARTITION_TESTS` list in `run_all_network_partition_tests.py`