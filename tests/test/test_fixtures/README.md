# Test Fixtures for ipfs_kit_py

**Note:** The test fixtures were successfully integrated with the test files. The tests have been designed to gracefully handle missing dependencies by using try/except import blocks and unittest.skipIf decorators. If required dependencies like `base58` or `multiaddr` are not available, the tests that depend on them will be skipped rather than failing.

This directory contains specialized test fixtures for the ipfs_kit_py codebase. These fixtures provide reusable testing components that make tests more robust, maintainable, and easier to write.

## Available Fixtures

### 1. Arrow Cluster State Fixtures

`arrow_cluster_test_fixtures.py` provides:

- `ArrowMockHelper`: Helper class for creating properly mocked PyArrow objects
- `ArrowClusterStateFixture`: Base test fixture for Arrow-based cluster state testing
- `NodeFixture`: Factory for creating test node data
- `TaskFixture`: Factory for creating test task data

These fixtures address the challenges of testing with immutable PyArrow objects like Schema and Table, providing convenient methods to create mock objects that behave like the real ones.

Example usage:
```python
# Create a worker node for testing
worker_node = NodeFixture.create_worker_node(node_id="worker1", online=True)

# Create a training task for testing
task = TaskFixture.create_training_task(status="pending")

# Create a mock Arrow table
mock_table = ArrowMockHelper.create_mock_table()
```

### 2. libp2p Network Testing Fixtures

`libp2p_test_fixtures.py` provides:

- `SimulatedNode`: Simulated node implementation for testing peer connections
- `NetworkSimulator`: Network simulator for testing P2P networks
- `MockLibp2pPeer`: Mock implementation of IPFSLibp2pPeer for testing
- `NetworkScenario`: Factories for creating network test scenarios

These fixtures enable comprehensive testing of peer-to-peer networking functionality without requiring actual network connections.

Example usage:
```python
# Create a network simulator
network = NetworkSimulator()

# Create a test scenario
scenario = NetworkScenario.create_small_network_scenario(network)

# Access nodes from the scenario
master_node = scenario.get_node_by_role("master")
worker_nodes = scenario.get_nodes_by_role("worker")

# Test content exchange
content_cid = "QmTestFile"
content_data = b"Test content"
master_node.store_content(content_cid, content_data)
```

### 3. AI/ML Integration Fixtures

`ai_ml_test_fixtures.py` provides:

- `MockMLModel`, `MockSklearnModel`, `MockPyTorchModel`, `MockTensorflowModel`: Mock ML model implementations
- `MockDataset`: Mock dataset implementation
- `ModelScenario`, `DatasetScenario`: Scenario factories for ML testing

These fixtures enable testing of AI/ML integration features without requiring actual ML frameworks, significantly speeding up tests and reducing dependencies.

Example usage:
```python
# Create a mock machine learning model
model = MockPyTorchModel()

# Create a training scenario
scenario = ModelScenario.create_pytorch_training_scenario(ipfs_client)
trained_model = scenario.train_model()

# Create a dataset scenario
dataset_scenario = DatasetScenario.create_tabular_dataset_scenario()
dataset_path = dataset_scenario.get_dataset_path()
```

## Using Fixtures in Tests

When using these fixtures in tests, follow these practices:

1. **Import with try/except**: Handle cases where fixtures might not be available
   ```python
   try:
       from test.test_fixtures.arrow_cluster_test_fixtures import ArrowMockHelper
       FIXTURES_AVAILABLE = True
   except ImportError:
       FIXTURES_AVAILABLE = False
   ```

2. **Skip tests if fixtures are unavailable**:
   ```python
   @unittest.skipIf(not FIXTURES_AVAILABLE, "Test fixtures not available")
   class TestWithFixtures(unittest.TestCase):
       # Test cases using fixtures
   ```

3. **Create realistic test data**: Use the factory methods to create test data that closely resembles real data
   ```python
   # Create a master node and three worker nodes for a realistic cluster
   nodes = [
       NodeFixture.create_master_node("master1"),
       NodeFixture.create_worker_node("worker1"),
       NodeFixture.create_worker_node("worker2"),
       NodeFixture.create_worker_node("worker3", online=False)  # One offline worker
   ]
   ```

4. **Use scenarios for complex test setups**: For complex testing scenarios, use the scenario classes
   ```python
   # Create a complete network scenario
   scenario = NetworkScenario.create_small_network_scenario(network)
   
   # Run tests with the scenario
   master_node = scenario.get_node_by_role("master")
   worker_nodes = scenario.get_nodes_by_role("worker")
   ```

## Extending Fixtures

When adding new fixtures:

1. Add them to the appropriate fixture file based on their purpose
2. Keep fixtures focused on a specific testing need
3. Include factory methods for common testing scenarios
4. Document the fixture and provide usage examples
5. Update this README.md with information about the new fixture

By using these test fixtures, we can improve test reliability, reduce code duplication, and make tests more maintainable.