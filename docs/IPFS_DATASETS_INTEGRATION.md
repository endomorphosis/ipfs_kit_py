# IPFS Datasets Integration

This document describes the integration of `ipfs_datasets_py` distributed dataset manipulation services into `ipfs_kit_py`.

## Overview

The IPFS Datasets integration enables local-first and decentralized filesystem operations for managing AI/ML datasets. It provides:

- **Distributed Dataset Storage**: Store datasets in IPFS with content-addressed identifiers (CIDs)
- **Dataset Versioning**: Track dataset versions with full provenance and lineage
- **Event Logging**: Comprehensive logging of all dataset operations
- **Provenance Tracking**: Complete history of dataset transformations and parent versions
- **Graceful Fallbacks**: Works seamlessly even when `ipfs_datasets_py` is not installed (important for CI/CD)

## Architecture

### Core Components

1. **`ipfs_datasets_integration.py`**: Central integration module providing:
   - `DatasetIPFSBackend`: Adapter between ipfs_kit and ipfs_datasets_py
   - `IPFSDatasetsManager`: High-level manager for dataset operations
   - Event and provenance logging
   - Automatic fallback to local operations

2. **`filesystem_journal.py`**: Extended with dataset operation tracking:
   - `store_dataset()`: Store datasets with journal logging
   - `version_dataset()`: Create versioned datasets with provenance
   - `get_dataset_event_log()`: Retrieve dataset operation history
   - `get_dataset_provenance_log()`: Access dataset lineage information

3. **`mcp/ai/dataset_manager.py`**: Enhanced DatasetManager with IPFS backend:
   - `store_dataset_to_ipfs()`: Store datasets to IPFS
   - `load_dataset_from_ipfs()`: Load datasets from IPFS by CID
   - `version_dataset_with_ipfs()`: Version datasets with IPFS provenance

## Installation

### Basic Installation (Local-only)

```bash
pip install -e .
```

### With IPFS Datasets Support

```bash
# If ipfs_datasets_py is available
pip install ipfs_datasets_py  # If publicly available
# OR install from source/custom location

# Then install ipfs_kit_py
pip install -e .[ipfs_datasets]
```

### Optional Dependencies

The integration is added as an optional dependency group in `pyproject.toml`:

```toml
[project.optional-dependencies]
ipfs_datasets = [
    # Marks the integration as available
    # Actual package installation handled separately
]
```

## Usage

### Using the Integration Module Directly

```python
from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager

# Initialize manager (works with or without ipfs_datasets_py)
manager = get_ipfs_datasets_manager(enable=True)

# Check if distributed operations are available
if manager.is_available():
    print("IPFS distributed operations enabled")
else:
    print("Using local-only operations (ipfs_datasets_py not available)")

# Store a dataset
result = manager.store("path/to/dataset.csv", metadata={"version": "1.0"})
print(f"Stored dataset: {result.get('cid', 'local')}")

# Load a dataset by CID
result = manager.load("Qm...", target_path="/tmp/dataset.csv")

# Version a dataset with provenance
result = manager.version(
    dataset_id="my-dataset",
    version="2.0.0",
    parent_version="1.0.0",
    transformations=["normalize", "augment"]
)

# Get event log
events = manager.get_event_log()
for event in events:
    print(f"{event['timestamp']}: {event['operation']} - {event['success']}")

# Get provenance log
provenance = manager.get_provenance_log()
for entry in provenance:
    print(f"Dataset {entry['dataset_id']} v{entry['version']}")
    print(f"  Parent: {entry['parent_version']}")
    print(f"  Transformations: {entry['transformations']}")
```

### Using with FilesystemJournal

```python
from ipfs_kit_py.filesystem_journal import FilesystemJournal

# Initialize journal with IPFS datasets integration
journal = FilesystemJournal(
    base_path="~/.ipfs_kit/journal",
    enable_ipfs_datasets=True,
    ipfs_client=ipfs_client  # Optional IPFS client
)

# Store a dataset (automatically logged in journal)
result = journal.store_dataset(
    "path/to/dataset.csv",
    metadata={"description": "Training data", "version": "1.0"}
)

# Version a dataset with lineage tracking
result = journal.version_dataset(
    dataset_id="training-data",
    version="1.1.0",
    parent_version="1.0.0",
    transformations=["feature_engineering", "outlier_removal"],
    metadata={"notes": "Improved quality"}
)

# Get dataset-specific logs
event_log = journal.get_dataset_event_log()
provenance_log = journal.get_dataset_provenance_log()

# Close journal (handles cleanup)
journal.close()
```

### Using with Enhanced DatasetManager

```python
from ipfs_kit_py.mcp.ai.dataset_manager import DatasetManager

# Initialize with IPFS backend
manager = DatasetManager(
    enable_ipfs_backend=True,
    ipfs_client=ipfs_client  # Optional
)

# Create a dataset
dataset = manager.create_dataset(
    name="training-data",
    description="Image classification training set",
    domain="computer_vision"
)

# Store dataset files to IPFS
result = manager.store_dataset_to_ipfs(
    "path/to/dataset.tar.gz",
    metadata={"dataset_id": dataset.id}
)

if result['success'] and result.get('distributed'):
    print(f"Dataset stored to IPFS with CID: {result['cid']}")
else:
    print(f"Dataset stored locally: {result['local_path']}")

# Load from IPFS
result = manager.load_dataset_from_ipfs(
    "Qm...",  # CID
    target_path="/tmp/dataset"
)

# Version with provenance
result = manager.version_dataset_with_ipfs(
    dataset_id=dataset.id,
    version="2.0.0",
    parent_version="1.0.0",
    transformations=["augmentation", "balancing"]
)
```

## Graceful Degradation

The integration is designed to work seamlessly whether or not `ipfs_datasets_py` is installed:

### When ipfs_datasets_py is Available

- Full distributed dataset operations
- CID-based content addressing
- IPFS storage and retrieval
- Distributed provenance tracking

### When ipfs_datasets_py is NOT Available

- Automatic fallback to local operations
- All APIs remain functional
- Operations logged locally
- No errors or failures
- CI/CD pipelines continue to work

### Example Fallback Behavior

```python
# This code works identically with or without ipfs_datasets_py
manager = get_ipfs_datasets_manager(enable=True)

result = manager.store("dataset.csv")

# With ipfs_datasets_py:
# {
#     "success": True,
#     "cid": "QmXxx...",
#     "distributed": True,
#     "local_path": "/path/to/dataset.csv"
# }

# Without ipfs_datasets_py:
# {
#     "success": True,
#     "local_path": "/path/to/dataset.csv",
#     "distributed": False,
#     "message": "ipfs_datasets not available, using local storage"
# }
```

## Testing

Comprehensive tests are included in `tests/test_ipfs_datasets_integration.py`:

```bash
# Run all integration tests
python tests/test_ipfs_datasets_integration.py

# Tests cover:
# - Integration module functionality
# - Fallback behavior without ipfs_datasets_py
# - Filesystem journal integration
# - Event and provenance logging
# - CI/CD scenarios
```

## Configuration

### Environment Variables

```bash
# Optional: Specify custom dataset storage path
export IPFS_DATASETS_PATH="~/.ipfs_datasets"

# Optional: Enable debug logging
export IPFS_KIT_LOG_LEVEL="DEBUG"
```

### Programmatic Configuration

```python
from ipfs_kit_py.ipfs_datasets_integration import DatasetIPFSBackend

backend = DatasetIPFSBackend(
    base_path="~/.custom_datasets",  # Custom storage path
    enable_distributed=True           # Enable distributed mode
)
```

## Metadata Schema

### Event Log Schema

```python
{
    "operation": "store",              # Operation type
    "path": "/path/to/dataset.csv",    # Dataset path
    "timestamp": "2024-01-28T...",     # ISO timestamp
    "success": True,                   # Success flag
    "cid": "Qm..."                     # CID (if distributed)
}
```

### Provenance Log Schema

```python
{
    "dataset_id": "my-dataset",
    "version": "2.0.0",
    "parent_version": "1.0.0",
    "transformations": [
        "normalize",
        "augment"
    ],
    "timestamp": "2024-01-28T...",
    "cid": "Qm..."                     # CID (if distributed)
}
```

## Best Practices

1. **Always Check Availability**: Check `is_available()` before assuming distributed operations
2. **Provide Metadata**: Include rich metadata for better tracking and discovery
3. **Use Versioning**: Create versions for significant dataset changes
4. **Track Provenance**: Document transformations and parent versions
5. **Handle Both Modes**: Write code that works with both distributed and local modes
6. **Clean Up**: Close journals and managers when done

## Troubleshooting

### "ipfs_datasets_py not available"

This is normal if the package isn't installed. The system automatically falls back to local operations.

### Import Errors

If you see import errors, ensure your Python environment is correctly set up:

```bash
python -c "from ipfs_kit_py.ipfs_datasets_integration import IPFS_DATASETS_AVAILABLE; print(IPFS_DATASETS_AVAILABLE)"
```

### Journal Errors During Tests

Warning messages about journal write errors during test cleanup are normal and can be ignored - they occur because temporary directories are cleaned up before journal sync completes.

## Future Enhancements

Planned improvements include:

- [ ] Integration with ipfs_kit main class
- [ ] CLI commands for dataset operations
- [ ] Web UI for dataset management
- [ ] Advanced provenance queries
- [ ] Dataset deduplication
- [ ] Automatic dataset migration

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass
2. Code follows existing patterns
3. Fallback behavior is preserved
4. Documentation is updated

## License

This integration follows the same license as ipfs_kit_py (AGPL-3.0-or-later).
