# Installation Guide

This guide covers the installation of `ipfs-kit-py` and its dependencies, including the underlying IPFS binaries and cluster tools if needed.

## Prerequisites

*   **Python**: Version 3.8 or higher.
*   **pip**: Python package installer.
*   **Optional (for full functionality)**:
    *   Build tools (gcc, make, etc.) if installing dependencies that require compilation.
    *   Access to the internet to download packages and binaries.

## Installing `ipfs-kit-py` Library

The core Python library can be installed using pip:

```bash
# Minimal installation (core functionality)
pip install ipfs-kit-py

# Installation with AI/ML features (requires more dependencies)
pip install ipfs-kit-py[ai_ml]

# Installation with FSSpec support
pip install ipfs-kit-py[fsspec]

# Full installation with all optional dependencies
pip install ipfs-kit-py[full]
```

Choose the installation option that best suits your needs. `[full]` is recommended if you plan to use clustering, AI/ML, and other advanced features.

## Installing IPFS Binaries (Optional but Recommended)

While `ipfs-kit-py` can connect to an existing IPFS daemon or API endpoint, it often works best with a locally managed IPFS installation. The library includes a utility script to help install the necessary Go IPFS binaries (`ipfs`, `ipfs-cluster-service`, `ipfs-cluster-ctl`, `ipfs-cluster-follow`, `ipget`).

**Using the Installation Script:**

The `install_ipfs.py` script (runnable via a helper command or directly) automates the download and setup of these binaries.

```bash
# Option 1: Using the provided helper script (if available in PATH after install)
# (Command name might vary)
# ipfs-kit-install --install-all

# Option 2: Running the script directly
# Find the script location within your Python environment's site-packages
# e.g., python -c "import ipfs_kit_py; print(ipfs_kit_py.__path__)"
# Then navigate to that directory and run:
# python install_ipfs.py --install-all

# To install specific components:
# python install_ipfs.py --install ipfs --install ipfs-cluster-service

# To specify installation directory (default is often ~/.ipfs-kit/bin):
# python install_ipfs.py --install-all --bin-path /usr/local/bin

# To uninstall:
# python install_ipfs.py --uninstall-all
```

**Manual Installation:**

Alternatively, you can install the Go IPFS binaries manually:

1.  **Go IPFS (Kubo)**: Download from the [IPFS Distributions](https://dist.ipfs.tech/#kubo) page. Choose the appropriate binary for your OS/architecture. Extract and place the `ipfs` executable in your system's PATH.
2.  **IPFS Cluster**: Download from the [IPFS Cluster Distributions](https://dist.ipfs.tech/#ipfs-cluster-service) page. Download `ipfs-cluster-service` and `ipfs-cluster-ctl`. Extract and place them in your PATH.
3.  **(Optional) ipget**: Download from its [releases page](https://github.com/ipfs/ipget/releases).

After manual installation, ensure the binaries are executable and located in a directory included in your system's `PATH` environment variable.

## Initializing IPFS Repository

If you installed the `ipfs` binary, you need to initialize the IPFS repository (usually stored in `~/.ipfs`):

```bash
ipfs init
```

This command creates the necessary configuration files and keys for your IPFS node.

## Configuration

`ipfs-kit-py` can be configured via:

1.  **Configuration Files**: A primary configuration file (e.g., `config.yaml` or `config.json`) passed during `IPFSSimpleAPI` or `IPFSKit` initialization.
2.  **Environment Variables**: Certain settings might be configurable via environment variables (check specific component documentation).
3.  **Programmatic Arguments**: Passing keyword arguments during class initialization.

Refer to the documentation for specific components (e.g., `Tiered Cache`, `Cluster Management`, `AI/ML Integration`) for detailed configuration options. A basic configuration might involve specifying the IPFS API endpoint if not using the default local daemon:

```python
# Example programmatic configuration
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

config = {
    'ipfs': {
        'api_host': '127.0.0.1',
        'api_port': 5001
        # Add other settings like timeouts, retries etc.
    }
    # Add configurations for other components like cache, cluster, ai_ml...
}

kit = IPFSSimpleAPI(config=config)
```

## Verifying Installation

1.  **Python Library**:
    ```python
    import ipfs_kit_py
    print(f"ipfs-kit-py version: {ipfs_kit_py.__version__}")
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    try:
        kit = IPFSSimpleAPI()
        print("IPFS Kit initialized successfully.")
        # Optional: Check connection to IPFS daemon
        version_info = kit.ipfs_version() # Assuming an ipfs_version method exists
        print(f"Connected to IPFS version: {version_info}")
    except Exception as e:
        print(f"Error initializing IPFS Kit or connecting to daemon: {e}")
    ```
2.  **IPFS Binaries**:
    ```bash
    ipfs --version
    ipfs-cluster-service --version
    ipfs-cluster-ctl --version
    ```
    Run `ipfs daemon` in a separate terminal to start the local node.

You should now have a working `ipfs-kit-py` installation. Refer to other documentation sections for configuring and using specific features.
