# Command-Line Interface (CLI) Reference

`ipfs-kit-py` provides a command-line interface (CLI) for interacting with its core functionalities and managing IPFS operations directly from the terminal. The CLI is implemented in `cli.py`.

## Installation

If you installed `ipfs-kit-py` using pip, the CLI command (e.g., `ipfs-kit`) should be available in your PATH.

```bash
# Verify installation
ipfs-kit --version
```

If the command is not found, you might need to ensure your Python scripts directory is in your PATH or invoke it via `python -m ipfs_kit_py.cli`.

## Usage

The general usage pattern is:

```bash
ipfs-kit [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS] [ARGUMENTS...]
```

**Global Options:**

*   `--config PATH`: Path to a configuration file.
*   `--profile NAME`: Use a specific configuration profile.
*   `--api URL`: Specify the IPFS API endpoint URL (e.g., `http://127.0.0.1:5001`).
*   `--timeout SECONDS`: Set the API timeout in seconds.
*   `--verbose` or `-v`: Enable verbose output.
*   `--format {json|text|table}`: Set the output format (default: text).
*   `--no-color`: Disable colored output.
*   `--version`: Show version information.
*   `--help` or `-h`: Show help message.

## Commands

This reference assumes the CLI command is `ipfs-kit`.

### Core IPFS Commands

These commands mirror standard IPFS operations.

*   **`ipfs-kit add <path>...`**: Add file(s) or directory to IPFS.
    *   Options:
        *   `-r, --recursive`: Add directory recursively.
        *   `-p, --pin`: Pin added content (default: true).
        *   `-w, --wrap-with-directory`: Wrap files with a directory.
        *   `--cid-version INT`: CID version to use (0 or 1).
        *   `--progress`: Show progress bar.
*   **`ipfs-kit cat <cid>`**: Display IPFS object data.
*   **`ipfs-kit get <cid> [output_path]`**: Download IPFS objects.
    *   Options:
        *   `-o, --output PATH`: Specify output directory/file.
        *   `-a, --archive`: Output as TAR archive.
        *   `-C, --compress`: Compress output with Gzip.
*   **`ipfs-kit ls <cid>`**: List directory contents for UnixFS objects.
    *   Options:
        *   `-l, --long`: Use long listing format.
        *   `-s, --size`: Show object sizes.
*   **`ipfs-kit pin add <cid>...`**: Pin objects to local storage.
    *   Options:
        *   `-r, --recursive`: Pin recursively (default: true).
*   **`ipfs-kit pin rm <cid>...`**: Remove pinned objects from local storage.
    *   Options:
        *   `-r, --recursive`: Unpin recursively (default: true).
*   **`ipfs-kit pin ls`**: List objects pinned to local storage.
    *   Options:
        *   `--type {all|recursive|direct|indirect}`: Filter by pin type.
        *   `-q, --quiet`: Output only CIDs.
*   **`ipfs-kit id [peer_id]`**: Show IPFS node identity info.
*   **`ipfs-kit version`**: Show IPFS version information.
*   **`ipfs-kit swarm peers`**: List peers connected to the node.
*   **`ipfs-kit swarm connect <address>`**: Open connection to a given address.
*   **`ipfs-kit swarm disconnect <address>`**: Close connection to a given address.
*   **`ipfs-kit name publish <ipfs_path>`**: Publish object to IPNS.
    *   Options:
        *   `--key NAME`: Name of the key to publish to (default: self).
        *   `--lifetime DURATION`: Time duration the record is valid (default: 24h).
        *   `--ttl DURATION`: Time duration the record is cached (default: 1h).
*   **`ipfs-kit name resolve <ipns_name>`**: Resolve IPNS names.
    *   Options:
        *   `-r, --recursive`: Resolve recursively (default: true).

### Cluster Commands (Requires Cluster Setup)

*   **`ipfs-kit cluster add <path>...`**: Add file/directory to the cluster.
    *   Options: *(Similar to `add`)*
    *   `--replication-min INT`: Minimum replication factor.
    *   `--replication-max INT`: Maximum replication factor.
*   **`ipfs-kit cluster pin add <cid>...`**: Pin CIDs to the cluster.
    *   Options: *(Similar to `pin add`)*
    *   `--replication-min INT`, `--replication-max INT`
*   **`ipfs-kit cluster pin rm <cid>...`**: Unpin CIDs from the cluster.
*   **`ipfs-kit cluster pin ls`**: List CIDs pinned to the cluster.
*   **`ipfs-kit cluster status [cid]`**: Show status of cluster pins.
*   **`ipfs-kit cluster peers ls`**: List peers in the cluster.
*   **`ipfs-kit cluster health`**: Show cluster health information.

### AI/ML Commands (Requires `ai_ml` extra)

*   **`ipfs-kit ai model add <path> --name NAME --framework FRAMEWORK [options]`**: Add a model file/directory.
    *   Requires `--name` and `--framework`.
    *   Options: `--version VERSION`, `--metadata KEY=VALUE...`, `--tags TAG...`
*   **`ipfs-kit ai model get <name_or_cid> [output_path]`**: Download a model.
    *   Options: `--version VERSION`
*   **`ipfs-kit ai model list`**: List registered models.
    *   Options: `--framework FRAMEWORK`, `--tags TAG...`
*   **`ipfs-kit ai dataset add <path> --name NAME [options]`**: Add a dataset file/directory.
    *   Requires `--name`.
    *   Options: `--version VERSION`, `--format FORMAT`, `--metadata KEY=VALUE...`, `--tags TAG...`
*   **`ipfs-kit ai dataset get <name_or_cid> [output_path]`**: Download a dataset.
    *   Options: `--version VERSION`
*   **`ipfs-kit ai dataset list`**: List registered datasets.
    *   Options: `--format FORMAT`, `--tags TAG...`
*   **`ipfs-kit ai search <query>`**: Search for models/datasets.
    *   Options: `--type {model|dataset|all}`, `--framework FRAMEWORK`, `--format FORMAT`, `--tags TAG...`, `--limit INT`

### Write-Ahead Log (WAL) Commands (If WAL is enabled)

*   **`ipfs-kit wal status`**: Show WAL status and statistics.
*   **`ipfs-kit wal list [status]`**: List WAL operations (optionally filter by status: pending, processing, completed, failed).
*   **`ipfs-kit wal get <operation_id>`**: Get details of a specific WAL operation.
*   **`ipfs-kit wal retry <operation_id>`**: Retry a failed WAL operation.
*   **`ipfs-kit wal cleanup [--max-age DAYS]`**: Clean up old completed/failed WAL entries.

### Other Commands

*   **`ipfs-kit config get <key>`**: Get a configuration value.
*   **`ipfs-kit config set <key> <value>`**: Set a configuration value.
*   **`ipfs-kit config show`**: Show the current configuration.
*   **`ipfs-kit daemon`**: Start the IPFS Kit daemon (if applicable, might manage underlying IPFS/Cluster).
*   **`ipfs-kit install`**: Helper commands for installing dependencies (see `docs/installation_guide.md`).

## Output Formatting

Use the `--format` global option to control output:

*   **`text` (default)**: Human-readable text output, often using tables.
*   **`json`**: Machine-readable JSON output.
*   **`table`**: Explicitly request table format (useful if default changes).

## Examples

```bash
# Add a directory recursively and pin it
ipfs-kit add -r -p ./my_project

# Cat the content of a file
ipfs-kit cat QmXyZ...

# List pinned items quietly (only CIDs)
ipfs-kit pin ls -q

# List cluster peers
ipfs-kit cluster peers ls

# Add an AI model
ipfs-kit ai model add ./my_model.pt --name my-pytorch-model --framework pytorch --version 1.1 --tags vision --metadata accuracy=0.92

# List pending WAL operations in JSON format
ipfs-kit wal list pending --format json
```

This reference provides an overview. For detailed options for each command, use the `--help` flag:

```bash
ipfs-kit --help
ipfs-kit add --help
ipfs-kit ai model add --help
