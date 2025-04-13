# IPFS Kit Filesystem Journal

## Overview

The Filesystem Journal in IPFS Kit provides transactional safety for filesystem operations, ensuring data integrity even during unexpected shutdowns or power outages. It works alongside the Write-Ahead Log (WAL) system to provide comprehensive protection for your data.

The filesystem journal records every filesystem operation in a durable log before executing it, allowing for complete recovery after system crashes. Operations are grouped into atomic transactions, ensuring that the filesystem state remains consistent. This is particularly important for distributed systems where multiple clients may be modifying the filesystem simultaneously.

## Key Features

- **Transaction Safety**: Groups file operations into atomic transactions that either complete entirely or roll back
- **Crash Recovery**: Automatically recovers filesystem state after unexpected shutdowns
- **Operation Journaling**: Records all operations (create, delete, write, rename, etc.) before execution
- **Checkpoint Mechanism**: Creates regular snapshots of filesystem state for efficient recovery
- **Path-to-CID Mapping**: Transparently bridges between path-based operations and IPFS's content-addressed storage
- **WAL Integration**: Works alongside the Write-Ahead Log for comprehensive data protection
- **Flexible Configuration**: Customizable journal location, sync interval, and recovery behavior
- **Automatic Recovery**: Automatically attempts recovery on startup to restore a consistent state

## Architecture

### Components

The Filesystem Journal system is composed of several key components:

1. **FilesystemJournalManager**: Core implementation that manages the journal and filesystem operations
   - Tracks and logs operations to the journal
   - Enforces transaction boundaries
   - Handles recovery after crashes
   - Provides operation status tracking

2. **IPFSFilesystemInterface**: Adapter that translates between filesystem operations and IPFS content-addressed storage
   - Maintains a mapping between virtual paths and IPFS CIDs
   - Implements filesystem-like operations (write_file, mkdir, rm, etc.)
   - Handles the translation between path-based and content-based addressing

3. **FilesystemJournalIntegration**: Integration with the high-level API
   - Provides a simple interface for enabling journaling
   - Handles initialization and configuration
   - Integrates with existing WAL if available

4. **TransactionManager**: Manages transaction boundaries
   - Groups operations into atomic transactions
   - Handles commit and rollback operations
   - Ensures consistent filesystem state

### Operation Types

The filesystem journal supports the following operation types:

1. **CREATE**: Creating a new file or directory
2. **DELETE**: Removing a file or directory
3. **WRITE**: Writing to a file
4. **RENAME**: Renaming or moving a file or directory
5. **UPDATE_METADATA**: Updating file metadata (permissions, attributes, etc.)
6. **MOUNT**: Mounting an existing CID at a specific path
7. **UNMOUNT**: Unmounting a CID from a path

### Transaction Flow

The following steps outline how operations flow through the filesystem journal:

1. **Operation Request**: An application or user requests a filesystem operation
2. **Journal Entry**: The operation is recorded in the journal with a unique transaction ID
3. **Operation Execution**: The operation is executed on the actual filesystem
4. **Commit Entry**: A commit record is written to the journal
5. **Checkpoint**: Periodically, the journal creates a checkpoint of the filesystem state

### Recovery Process

When the system starts up after a crash:

1. **Journal Scan**: The journal is scanned to find incomplete transactions
2. **Last Checkpoint**: The system identifies the last valid checkpoint
3. **Replay Operations**: Operations after the checkpoint are replayed
4. **Roll Back Incomplete Transactions**: Incomplete transactions are rolled back
5. **New Checkpoint**: A new checkpoint is created once recovery is complete

## Usage Guide

### Basic Usage with High-Level API

To enable filesystem journaling with the high-level API:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.wal import WAL  # Optional: Import the Write-Ahead Log

# Initialize API
api = IPFSSimpleAPI()

# Optional: Initialize a WAL for additional protection
wal = WAL(base_path="~/.ipfs_kit/wal")
api.wal = wal  # Set the WAL attribute on the API instance

# Enable filesystem journaling
journaled_fs = api.enable_filesystem_journaling(
    journal_base_path="~/.ipfs_kit/journal",
    auto_recovery=True,
    sync_interval=5,  # Sync journal every 5 seconds
    checkpoint_interval=60  # Create checkpoint every 60 seconds
)

# Now you can perform filesystem operations with journaling
journaled_fs.create_directory("/virtual_fs", metadata={"description": "Root directory for virtual filesystem"})
journaled_fs.create_directory("/virtual_fs/documents", metadata={"category": "documents", "created_at": time.time()})

# Create a file with content and metadata
journaled_fs.create_file(
    "/virtual_fs/documents/example.txt",
    "This is example content".encode('utf-8'),
    metadata={"type": "text", "size": 23}
)

journaled_fs.create_directory("/virtual_fs/images")

# Rename a file (atomic operation)
journaled_fs.rename("/virtual_fs/documents/example.txt", "/virtual_fs/images/moved_example.txt")

# Update file metadata
journaled_fs.update_metadata(
    "/virtual_fs/images/moved_example.txt",
    {"description": "Example file that was moved", "version": "1.0"}
)

# Mount an existing CID at a specific path
example_cid = "QmExample123456"
journaled_fs.mount(
    "/virtual_fs/mounted_content",
    example_cid,
    is_directory=False,
    metadata={"source": "external", "imported_at": time.time()}
)

# Delete a file
journaled_fs.delete("/virtual_fs/images/moved_example.txt")

# Create a checkpoint to persist operations
journaled_fs.create_checkpoint()

# Get journal statistics
stats = journaled_fs.get_journal_stats()
print(f"Journal statistics: {stats}")

# Properly close the journal when done
journaled_fs.close()
```

### Using Transactions

For operations that need to be atomic, you can explicitly use transactions:

```python
# Start a transaction
with journaled_fs.transaction() as txn:
    # All these operations will be in the same transaction
    txn.create_directory("/virtual_fs/project")
    txn.write_file("/virtual_fs/project/readme.md", "# Project Documentation")
    txn.write_file("/virtual_fs/project/config.json", '{"version": "1.0"}')
    
    # If any operation fails, the entire transaction will be rolled back
    # When the 'with' block exits, the transaction is committed if successful
```

You can also manage transactions manually:

```python
# Start a transaction
transaction = journaled_fs.begin_transaction()

try:
    # Perform operations
    journaled_fs.create_directory("/virtual_fs/data", transaction=transaction)
    journaled_fs.write_file("/virtual_fs/data/file1.txt", "Content 1", transaction=transaction)
    journaled_fs.write_file("/virtual_fs/data/file2.txt", "Content 2", transaction=transaction)
    
    # Commit the transaction
    journaled_fs.commit_transaction(transaction)
except Exception as e:
    # If an error occurs, roll back the transaction
    journaled_fs.rollback_transaction(transaction)
    raise e
```

### Recovery After Crashes

The filesystem journal automatically handles recovery after crashes:

```python
# If the application crashes or the system loses power,
# the next time you create a journaled filesystem, recovery happens automatically:
journaled_fs = api.enable_filesystem_journaling(
    journal_base_path="~/.ipfs_kit/journal",
    auto_recovery=True
)

# You can also trigger recovery manually
journaled_fs.recover()

# Or check the recovery status
recovery_info = journaled_fs.get_recovery_info()
print(f"Last recovery: {recovery_info['last_recovery_time']}")
print(f"Recovered operations: {recovery_info['recovered_operations']}")
print(f"Failed operations: {recovery_info['failed_operations']}")
```

### Complete Example: fs_journal_example.py

IPFS Kit includes a comprehensive example that demonstrates the filesystem journal functionality in action. You can find this example at `/examples/fs_journal_example.py`.

The example demonstrates:

1. Creating a journaled filesystem with WAL integration
2. Building a complex virtual filesystem structure with directories and files
3. Performing various filesystem operations (create, rename, update metadata, delete)
4. Viewing the virtual filesystem state and path-to-CID mappings
5. Creating checkpoints to persist the journal state
6. Simulating an unexpected shutdown and recovery
7. Verifying the recovered filesystem state

To run the example:

```bash
# Run the example script
python -m ipfs_kit_py.examples.fs_journal_example
```

This example is an excellent way to understand how the filesystem journal works in practice and how it handles recovery scenarios. It uses a temporary directory for the journal so it won't affect your existing IPFS configuration.

### Mounting IPFS Content

The filesystem journal allows you to mount IPFS content by CID:

```python
# Mount content by CID
cid = "QmSomeContentIdentifier"
journaled_fs.mount("/virtual_fs/ipfs_content", cid)

# List mounted content
files = journaled_fs.list_directory("/virtual_fs/ipfs_content")
print(f"Files in mounted directory: {files}")

# Read a file from the mounted content
content = journaled_fs.read_file("/virtual_fs/ipfs_content/example.txt")
print(f"File content: {content}")

# Unmount when done
journaled_fs.unmount("/virtual_fs/ipfs_content")
```

## Configuration

### Journaling Configuration

You can customize the filesystem journal behavior with these configuration options:

```python
journal_config = {
    # Basic configuration
    "journal_base_path": "~/.ipfs_kit/journal",  # Base directory for journal files
    "auto_recovery": True,                       # Automatically recover on startup
    
    # Performance tuning
    "sync_interval": 5,                          # Seconds between journal syncs to disk
    "checkpoint_interval": 60,                   # Seconds between checkpoints
    "max_journal_size": 1000,                    # Maximum entries before forcing checkpoint
    
    # Recovery options
    "max_recovery_attempts": 3,                  # Maximum number of recovery attempts
    "recovery_timeout": 300,                     # Recovery timeout in seconds
    
    # Advanced settings
    "journal_compaction_threshold": 10000,       # Entry threshold for journal compaction
    "preserve_incomplete_transactions": True,    # Keep incomplete transaction data for debugging
    "detailed_operation_logging": True           # Log detailed operation information
}

# Create journaled filesystem with custom configuration
journaled_fs = api.enable_filesystem_journaling(**journal_config)
```

### Using Environment Variables

You can also configure the filesystem journal using environment variables:

```bash
# Basic configuration
export IPFS_KIT_JOURNAL_PATH=~/.ipfs_kit/journal
export IPFS_KIT_JOURNAL_AUTO_RECOVERY=true

# Performance tuning
export IPFS_KIT_JOURNAL_SYNC_INTERVAL=5
export IPFS_KIT_JOURNAL_CHECKPOINT_INTERVAL=60
export IPFS_KIT_JOURNAL_MAX_SIZE=1000

# Recovery options
export IPFS_KIT_JOURNAL_MAX_RECOVERY_ATTEMPTS=3
export IPFS_KIT_JOURNAL_RECOVERY_TIMEOUT=300
```

## Advanced Topics

### Virtual Filesystem Structure

The filesystem journal maintains a virtual filesystem structure:

```
/virtual_fs/                 # Root of the virtual filesystem
  ├── documents/             # Regular directory
  │   ├── file1.txt          # Regular file
  │   └── file2.md           # Regular file
  ├── images/                # Another directory
  │   └── photo.jpg          # Image file
  └── ipfs_mounts/           # Directory containing mounted IPFS content
      └── QmContentHash/     # Directory mounted from IPFS CID
          ├── file1.txt      # File within mounted IPFS content
          └── subdir/        # Subdirectory within mounted IPFS content
```

Each path in this virtual filesystem maps to either:
1. A CID for standalone files
2. A CID for a directory structure
3. A mounted CID from IPFS

### Path-to-CID Mapping

The filesystem journal maintains a mapping between paths and CIDs:

```python
# Example of the path-to-CID mapping
path_to_cid = {
    "/virtual_fs": "QmRootDirectoryCID",
    "/virtual_fs/documents": "QmDocumentsDirCID",
    "/virtual_fs/documents/file1.txt": "QmFile1CID",
    "/virtual_fs/documents/file2.md": "QmFile2CID",
    "/virtual_fs/images": "QmImagesDirCID",
    "/virtual_fs/images/photo.jpg": "QmPhotoCID",
    "/virtual_fs/ipfs_mounts/QmContentHash": "QmContentHash"  # Direct mapping for mounts
}
```

This mapping is stored in the journal and recovered after crashes to maintain the virtual filesystem structure.

### Journal Structure

The journal is stored as a series of files:

1. **journal.log**: The active journal file containing recent operations
2. **checkpoints/**: Directory containing filesystem state checkpoints
3. **transactions/**: Directory containing active transaction data
4. **recovery/**: Directory containing recovery information

### Integration with Write-Ahead Log

The filesystem journal works alongside the Write-Ahead Log (WAL) system:

| Feature | Filesystem Journal | Write-Ahead Log |
|---------|-------------------|-----------------|
| **Purpose** | Transaction safety for filesystem operations | Durability for storage operations |
| **Granularity** | File-level operations | Backend-level operations |
| **Recovery** | Rebuilds consistent filesystem state | Retries failed storage operations |
| **Integration** | Works with virtual filesystem paths | Works with storage backends |
| **Atomicity** | Groups operations into transactions | Individual operation atomicity |

When both systems are enabled, they provide complementary protection:
1. The WAL ensures that storage operations eventually complete
2. The filesystem journal ensures that filesystem state remains consistent

```python
# Enable both WAL and filesystem journaling
api = IPFSSimpleAPI(enable_wal=True)
journaled_fs = api.enable_filesystem_journaling()

# Now operations benefit from both protection systems
# WAL ensures the add operation eventually completes
result = api.add("/path/to/file.txt")

# Filesystem journal ensures the directory structure remains consistent
journaled_fs.create_directory("/virtual_fs/imported")
journaled_fs.mount("/virtual_fs/imported/file.txt", result["cid"])
```

### Performance Considerations

The filesystem journal adds some overhead to filesystem operations. Here are some performance considerations:

1. **Journal Sync Interval**: Increasing the sync interval improves performance but increases potential data loss during crashes
2. **Checkpoint Interval**: More frequent checkpoints speed up recovery but add overhead during normal operation
3. **Transaction Size**: Larger transactions provide better atomicity but use more memory
4. **Journal Location**: Placing the journal on a fast SSD improves performance
5. **Selective Journaling**: Consider journaling only critical operations when performance is a priority

### Custom Error Handling

You can implement custom error handling for journal operations:

```python
def custom_error_handler(operation, error):
    """Custom error handler for journal operations."""
    print(f"Error during operation {operation['type']} on {operation['path']}: {error}")
    
    # Determine if the operation should be retried
    if isinstance(error, (IOError, ConnectionError)):
        return True  # Retry the operation
    else:
        return False  # Don't retry

# Configure journal with custom error handler
journaled_fs = api.enable_filesystem_journaling(
    error_handler=custom_error_handler
)
```

## Examples

### Basic Virtual Filesystem Operations

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
import json

# Initialize API and enable filesystem journaling
api = IPFSSimpleAPI()
journaled_fs = api.enable_filesystem_journaling()

# Create a directory structure
journaled_fs.create_directory("/virtual_fs")
journaled_fs.create_directory("/virtual_fs/documents")
journaled_fs.create_directory("/virtual_fs/images")
journaled_fs.create_directory("/virtual_fs/data")

# Write some files
journaled_fs.write_file("/virtual_fs/documents/readme.md", "# Project Documentation\n\nThis is a test project.")
journaled_fs.write_file("/virtual_fs/documents/notes.txt", "Important notes about the project.")
journaled_fs.write_file("/virtual_fs/data/config.json", json.dumps({"version": "1.0", "debug": False}))

# List directories
root_contents = journaled_fs.list_directory("/virtual_fs")
print(f"Root contents: {root_contents}")

docs_contents = journaled_fs.list_directory("/virtual_fs/documents")
print(f"Documents contents: {docs_contents}")

# Read files
readme_content = journaled_fs.read_file("/virtual_fs/documents/readme.md")
print(f"README content: {readme_content}")

config_content = journaled_fs.read_file("/virtual_fs/data/config.json")
config = json.loads(config_content)
print(f"Configuration: {config}")

# Rename and move files
journaled_fs.move("/virtual_fs/documents/notes.txt", "/virtual_fs/documents/project_notes.txt")
journaled_fs.move("/virtual_fs/data/config.json", "/virtual_fs/config.json")

# Delete files and directories
journaled_fs.delete("/virtual_fs/documents/project_notes.txt")
journaled_fs.delete("/virtual_fs/images", recursive=True)
```

### Integrating with IPFS Content

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize API
api = IPFSSimpleAPI()
journaled_fs = api.enable_filesystem_journaling()

# Add a file to IPFS
result = api.add("example.txt")
cid = result["cid"]
print(f"Added file to IPFS with CID: {cid}")

# Mount the file in our virtual filesystem
journaled_fs.create_directory("/virtual_fs/ipfs_files")
journaled_fs.mount("/virtual_fs/ipfs_files/example.txt", cid)

# Add a directory to IPFS
result = api.add("example_dir", recursive=True)
dir_cid = result["cid"]
print(f"Added directory to IPFS with CID: {dir_cid}")

# Mount the directory in our virtual filesystem
journaled_fs.mount("/virtual_fs/ipfs_dirs/example", dir_cid)

# List the mounted directory
dir_contents = journaled_fs.list_directory("/virtual_fs/ipfs_dirs/example")
print(f"Mounted directory contents: {dir_contents}")

# Read a file from the mounted directory
if dir_contents:
    first_file = dir_contents[0]
    content = journaled_fs.read_file(f"/virtual_fs/ipfs_dirs/example/{first_file}")
    print(f"File content from mounted directory: {content}")
```

### Transaction-Based File Operations

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
import json

# Initialize API
api = IPFSSimpleAPI()
journaled_fs = api.enable_filesystem_journaling()

# Prepare sample project structure using a transaction
with journaled_fs.transaction(name="create_project") as txn:
    # Create directory structure
    txn.create_directory("/virtual_fs/project")
    txn.create_directory("/virtual_fs/project/src")
    txn.create_directory("/virtual_fs/project/docs")
    txn.create_directory("/virtual_fs/project/tests")
    
    # Add some files
    txn.write_file("/virtual_fs/project/README.md", "# Sample Project\n\nThis is a test project.")
    txn.write_file("/virtual_fs/project/src/main.py", "def main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()")
    txn.write_file("/virtual_fs/project/tests/test_main.py", "def test_main():\n    assert True")
    
    # Add configuration
    config = {
        "name": "sample-project",
        "version": "0.1.0",
        "dependencies": [
            "pytest>=7.0.0"
        ]
    }
    txn.write_file("/virtual_fs/project/pyproject.toml", json.dumps(config, indent=2))

# List the project structure
project_contents = journaled_fs.list_directory("/virtual_fs/project")
print(f"Project contents: {project_contents}")

src_contents = journaled_fs.list_directory("/virtual_fs/project/src")
print(f"Source contents: {src_contents}")

# Read the main.py file
main_content = journaled_fs.read_file("/virtual_fs/project/src/main.py")
print(f"Main file content:\n{main_content}")

# Update the project in a new transaction
with journaled_fs.transaction(name="update_project") as txn:
    # Update README
    readme_content = journaled_fs.read_file("/virtual_fs/project/README.md")
    updated_readme = readme_content + "\n\n## Installation\n\n```\npip install sample-project\n```"
    txn.write_file("/virtual_fs/project/README.md", updated_readme)
    
    # Add new file
    txn.write_file("/virtual_fs/project/CHANGELOG.md", "# Changelog\n\n## 0.1.0\n\n- Initial release")
    
    # Update configuration
    config_content = journaled_fs.read_file("/virtual_fs/project/pyproject.toml")
    config = json.loads(config_content)
    config["description"] = "A sample project for demonstrating filesystem journaling"
    txn.write_file("/virtual_fs/project/pyproject.toml", json.dumps(config, indent=2))
```

### Integration with WAL for Comprehensive Data Protection

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
import time

# Initialize API with WAL enabled
api = IPFSSimpleAPI(enable_wal=True)

# Enable filesystem journaling
journaled_fs = api.enable_filesystem_journaling()

# Create directory structure
journaled_fs.create_directory("/virtual_fs/data_protection_demo")

# Add a file to IPFS with WAL protection
text_content = "This is content that will be protected by both WAL and filesystem journaling."
result = api.add(text_content)
operation_id = result["operation_id"]
cid = result["cid"]

print(f"Added content to IPFS: {cid}")
print(f"WAL operation ID: {operation_id}")

# Wait for the WAL operation to complete
wal_status = api.wait_for_operation(operation_id)
print(f"WAL operation status: {wal_status}")

# Mount the file in the virtual filesystem with journaling protection
with journaled_fs.transaction(name="mount_protected_file") as txn:
    txn.mount("/virtual_fs/data_protection_demo/protected_file.txt", cid)
    txn.update_metadata(
        "/virtual_fs/data_protection_demo/protected_file.txt",
        {
            "description": "File protected by WAL and journaling",
            "added_at": time.time(),
            "protection": "dual-layer"
        }
    )

# Read back the file to verify
content = journaled_fs.read_file("/virtual_fs/data_protection_demo/protected_file.txt")
print(f"Read back content: {content}")

# Get file metadata
metadata = journaled_fs.get_metadata("/virtual_fs/data_protection_demo/protected_file.txt")
print(f"File metadata: {metadata}")
```

### Recovering from a Simulated Crash

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
import time

# Initialize API
api = IPFSSimpleAPI()
journaled_fs = api.enable_filesystem_journaling(
    journal_base_path="/tmp/crash_recovery_journal"
)

# Create some content
journaled_fs.create_directory("/virtual_fs/before_crash")
journaled_fs.write_file("/virtual_fs/before_crash/file1.txt", "File created before crash")

# Start a transaction but don't commit it (to simulate a crash during transaction)
transaction = journaled_fs.begin_transaction()
journaled_fs.create_directory("/virtual_fs/during_crash", transaction=transaction)
journaled_fs.write_file("/virtual_fs/during_crash/file2.txt", "File created during crash", transaction=transaction)

print("Transaction started but not committed (simulating crash)")

# Don't commit the transaction to simulate a crash
# journaled_fs.commit_transaction(transaction)

# Shutdown current journaled filesystem (simulate application restart after crash)
journaled_fs = None
api = None
time.sleep(1)  # Small delay to simulate restart

print("Restarting with recovery...")

# Create new instance that will trigger recovery
new_api = IPFSSimpleAPI()
recovered_fs = new_api.enable_filesystem_journaling(
    journal_base_path="/tmp/crash_recovery_journal",
    auto_recovery=True
)

# Check recovery status
recovery_info = recovered_fs.get_recovery_info()
print(f"Recovery information: {recovery_info}")

# Verify pre-crash content is still there
try:
    files = recovered_fs.list_directory("/virtual_fs/before_crash")
    print(f"Files from before crash: {files}")
    content = recovered_fs.read_file("/virtual_fs/before_crash/file1.txt")
    print(f"Content from before crash: {content}")
except Exception as e:
    print(f"Error accessing pre-crash content: {e}")

# Verify incomplete transaction was rolled back
try:
    files = recovered_fs.list_directory("/virtual_fs/during_crash")
    print(f"Files from incomplete transaction: {files}")
except Exception as e:
    print(f"As expected, incomplete transaction was rolled back: {e}")

# Create new content after recovery
recovered_fs.create_directory("/virtual_fs/after_recovery")
recovered_fs.write_file("/virtual_fs/after_recovery/file3.txt", "File created after recovery")

# List all content to verify filesystem state
try:
    all_dirs = recovered_fs.list_directory("/virtual_fs")
    print(f"All directories after recovery: {all_dirs}")
except Exception as e:
    print(f"Error listing root directory: {e}")
```

## Related Documentation

- [Write-Ahead Log (WAL)](write_ahead_log.md): Comprehensive documentation on the Write-Ahead Log system
- [High-Level API](high_level_api.md): Details on using the high-level API
- [Error Handling](error_handling.md): Information on error handling in IPFS Kit
- [IPFS Content Addressing](ipfs_content_addressing.md): Understanding IPFS content addressing
- [Distributed Coordination](distributed_coordination.md): Coordinating filesystem operations across distributed nodes

**Note:** IPFS Cluster specific storage logic is not yet implemented.
