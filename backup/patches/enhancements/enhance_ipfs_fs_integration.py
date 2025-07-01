#!/usr/bin/env python3
"""
Enhance IPFS and Filesystem Integration in MCP Tools
This script reinforces the connection between IPFS tools and filesystem features
by ensuring all components are properly integrated.
"""

import os
import sys
import logging
import importlib
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ipfs_fs_integration.log")
    ]
)
logger = logging.getLogger("ipfs-fs-integration")

def ensure_module_available(module_name, optional=False):
    """Check if a module is available and import it"""
    try:
        return importlib.import_module(module_name)
    except ImportError as e:
        if optional:
            logger.warning(f"Optional module {module_name} not available: {e}")
            return None
        else:
            logger.error(f"Required module {module_name} not available: {e}")
            raise

def create_integration_bridge():
    """Create the integration bridge between IPFS and filesystem components"""
    logger.info("Creating integration bridge between IPFS and filesystem components...")

    bridge_content = """#!/usr/bin/env python3
'''
IPFS-FS Integration Bridge
This module connects IPFS tools with filesystem capabilities
'''

import os
import sys
import logging
import importlib
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)

class IPFSFSBridge:
    """Bridge between IPFS and filesystem operations"""

    def __init__(self, base_dir=None):
        """Initialize the bridge with base directory"""
        self.base_dir = base_dir or os.getcwd()
        self.ipfs_client = None
        self.fs_journal = None
        logger.info(f"Initialized IPFS-FS Bridge with base directory: {self.base_dir}")

        # Try to initialize clients
        try:
            from ipfs_kit_py.api import Client
            self.ipfs_client = Client()
            logger.info("Successfully initialized IPFS client")
        except ImportError:
            logger.warning("Could not initialize IPFS client - module not available")

        try:
            from fs_journal_tools import FSJournal
            self.fs_journal = FSJournal(self.base_dir)
            logger.info("Successfully initialized FS Journal")
        except ImportError:
            logger.warning("Could not initialize FS Journal - module not available")

    def sync_to_ipfs(self, path: str, recursive: bool = True) -> Dict[str, Any]:
        """Synchronize local file/directory to IPFS"""
        if not self.ipfs_client:
            raise RuntimeError("IPFS client not available")

        full_path = os.path.join(self.base_dir, path)
        logger.info(f"Syncing to IPFS: {full_path}")

        if os.path.isdir(full_path):
            # Add directory recursively
            result = self.ipfs_client.add(full_path, recursive=recursive)

            # If journal is available, record the sync
            if self.fs_journal:
                self.fs_journal.record_sync(path, result['Hash'], 'to_ipfs')

            return result
        else:
            # Add single file
            with open(full_path, 'rb') as f:
                content = f.read()

            result = self.ipfs_client.add(content)

            # If journal is available, record the sync
            if self.fs_journal:
                self.fs_journal.record_sync(path, result['Hash'], 'to_ipfs')

            return result

    def sync_from_ipfs(self, cid: str, path: str) -> Dict[str, Any]:
        """Get content from IPFS and save to local file/directory"""
        if not self.ipfs_client:
            raise RuntimeError("IPFS client not available")

        full_path = os.path.join(self.base_dir, path)
        logger.info(f"Syncing from IPFS: {cid} to {full_path}")

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Get content from IPFS
        content = self.ipfs_client.cat(cid)

        # Write to file
        with open(full_path, 'wb') as f:
            f.write(content)

        # If journal is available, record the sync
        if self.fs_journal:
            self.fs_journal.record_sync(path, cid, 'from_ipfs')

        return {
            'path': path,
            'cid': cid,
            'size': len(content)
        }

    def get_sync_status(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Get sync status between local filesystem and IPFS"""
        if not self.fs_journal:
            raise RuntimeError("FS Journal not available")

        if path:
            return self.fs_journal.get_sync_status(path)
        else:
            # Get status for all tracked paths
            return self.fs_journal.get_all_sync_status()

def register_integration_tools(mcp_server):
    """Register IPFS-FS integration tools with MCP server"""
    logger.info("Registering IPFS-FS integration tools with MCP server...")

    # Initialize the bridge
    bridge = IPFSFSBridge()

    # Register tools
    @mcp_server.tool("ipfs_fs_bridge_sync")
    def ipfs_fs_bridge_sync(path: str, direction: str = "to_ipfs"):
        """Sync between IPFS and filesystem"""
        logger.info(f"MCP Tool call: ipfs_fs_bridge_sync({path}, {direction})")

        if direction == "to_ipfs":
            return bridge.sync_to_ipfs(path)
        elif direction == "from_ipfs":
            # For from_ipfs direction, we need a CID and local path
            if '/' not in path:
                # Assume it's a CID and use the filename
                cid = path
                local_path = os.path.basename(path)
            else:
                # Split into CID and local path
                parts = path.split('/', 1)
                cid = parts[0]
                local_path = parts[1]

            return bridge.sync_from_ipfs(cid, local_path)
        elif direction == "bidirectional":
            # Bidirectional sync is more complex - check status and sync in both directions
            status = bridge.get_sync_status(path)
            if status['local_modified'] > status['ipfs_modified']:
                return bridge.sync_to_ipfs(path)
            else:
                return bridge.sync_from_ipfs(status['cid'], path)
        else:
            raise ValueError(f"Unknown direction: {direction}")

    @mcp_server.tool("ipfs_fs_bridge_status")
    def ipfs_fs_bridge_status(path: Optional[str] = None):
        """Get bridge status"""
        logger.info(f"MCP Tool call: ipfs_fs_bridge_status({path})")
        return bridge.get_sync_status(path)

    # Register mount/unmount if FUSE is available
    try:
        import fuse

        @mcp_server.tool("ipfs_fs_bridge_mount")
        def ipfs_fs_bridge_mount(cid: str, mount_point: str):
            """Mount IPFS CID to local path"""
            logger.info(f"MCP Tool call: ipfs_fs_bridge_mount({cid}, {mount_point})")

            # Implementation depends on FUSE and IPFS mount capabilities
            # Simplified implementation
            import subprocess

            # Ensure mount point exists
            os.makedirs(mount_point, exist_ok=True)

            # Use ipfs mount command
            cmd = ["ipfs", "mount", "-f", f"{mount_point}={cid}"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"Mount failed: {result.stderr}")

            return {
                'cid': cid,
                'mount_point': mount_point,
                'status': 'mounted'
            }

        @mcp_server.tool("ipfs_fs_bridge_unmount")
        def ipfs_fs_bridge_unmount(mount_point: str):
            """Unmount IPFS from local path"""
            logger.info(f"MCP Tool call: ipfs_fs_bridge_unmount({mount_point})")

            import subprocess

            # Use fusermount to unmount
            cmd = ["fusermount", "-u", mount_point]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"Unmount failed: {result.stderr}")

            return {
                'mount_point': mount_point,
                'status': 'unmounted'
            }

    except ImportError:
        logger.warning("FUSE not available - mount/unmount functionality disabled")

    logger.info("IPFS-FS integration tools registered successfully")

class FSJournal:
    """File System Journal that tracks changes and syncs with IPFS"""

    def __init__(self, base_dir):
        """Initialize the journal with base directory"""
        self.base_dir = base_dir
        self.journal_path = os.path.join(base_dir, '.fs_journal')

        # Ensure journal directory exists
        os.makedirs(self.journal_path, exist_ok=True)
        logger.info(f"Initialized FS Journal with base directory: {base_dir}")

    def record_sync(self, path, cid, direction):
        """Record a sync operation in the journal"""
        import json
        import time

        journal_file = os.path.join(self.journal_path, 'sync_journal.json')

        # Load existing journal if it exists
        if os.path.exists(journal_file):
            with open(journal_file, 'r') as f:
                try:
                    journal = json.load(f)
                except json.JSONDecodeError:
                    journal = {}
        else:
            journal = {}

        # Create entry for path if it doesn't exist
        if path not in journal:
            journal[path] = []

        # Add new entry
        journal[path].append({
            'timestamp': time.time(),
            'cid': cid,
            'direction': direction
        })

        # Write journal back to file
        with open(journal_file, 'w') as f:
            json.dump(journal, f, indent=2)

    def get_sync_status(self, path):
        """Get sync status for a specific path"""
        import json
        import time

        journal_file = os.path.join(self.journal_path, 'sync_journal.json')

        # Check if journal exists
        if not os.path.exists(journal_file):
            return {
                'path': path,
                'tracked': False,
                'status': 'never_synced'
            }

        # Load journal
        with open(journal_file, 'r') as f:
            try:
                journal = json.load(f)
            except json.JSONDecodeError:
                return {
                    'path': path,
                    'tracked': False,
                    'status': 'journal_error'
                }

        # Check if path is tracked
        if path not in journal:
            return {
                'path': path,
                'tracked': False,
                'status': 'not_tracked'
            }

        # Get last sync entry
        entries = journal[path]
        if not entries:
            return {
                'path': path,
                'tracked': True,
                'status': 'no_entries'
            }

        last_entry = entries[-1]

        # Get file modification time
        full_path = os.path.join(self.base_dir, path)
        if os.path.exists(full_path):
            mtime = os.path.getmtime(full_path)
        else:
            mtime = 0

        return {
            'path': path,
            'tracked': True,
            'status': 'tracked',
            'last_sync': last_entry['timestamp'],
            'direction': last_entry['direction'],
            'cid': last_entry['cid'],
            'local_modified': mtime,
            'ipfs_modified': last_entry['timestamp'],
            'needs_sync': mtime > last_entry['timestamp']
        }

    def get_all_sync_status(self):
        """Get sync status for all tracked paths"""
        import json

        journal_file = os.path.join(self.journal_path, 'sync_journal.json')

        # Check if journal exists
        if not os.path.exists(journal_file):
            return {
                'tracked_paths': 0,
                'paths': []
            }

        # Load journal
        with open(journal_file, 'r') as f:
            try:
                journal = json.load(f)
            except json.JSONDecodeError:
                return {
                    'tracked_paths': 0,
                    'paths': [],
                    'error': 'journal_error'
                }

        # Get status for each path
        paths = []
        for path in journal:
            paths.append(self.get_sync_status(path))

        return {
            'tracked_paths': len(paths),
            'paths': paths
        }
"""

    # Write the bridge module
    with open("ipfs_mcp_fs_integration.py", "w") as f:
        f.write(bridge_content)

    logger.info("✅ Created IPFS-FS integration bridge at ipfs_mcp_fs_integration.py")

    # Create the journal tools module
    journal_content = """#!/usr/bin/env python3
'''
Filesystem Journal Tools for IPFS MCP Integration
'''

import os
import sys
import logging
import json
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class FSJournal:
    """File System Journal that tracks changes and syncs with IPFS"""

    def __init__(self, base_dir=None):
        """Initialize the journal with base directory"""
        self.base_dir = base_dir or os.getcwd()
        self.journal_path = os.path.join(self.base_dir, '.fs_journal')

        # Ensure journal directory exists
        os.makedirs(self.journal_path, exist_ok=True)
        logger.info(f"Initialized FS Journal with base directory: {self.base_dir}")

    def record_sync(self, path, cid, direction):
        """Record a sync operation in the journal"""
        journal_file = os.path.join(self.journal_path, 'sync_journal.json')

        # Load existing journal if it exists
        if os.path.exists(journal_file):
            with open(journal_file, 'r') as f:
                try:
                    journal = json.load(f)
                except json.JSONDecodeError:
                    journal = {}
        else:
            journal = {}

        # Create entry for path if it doesn't exist
        if path not in journal:
            journal[path] = []

        # Add new entry
        journal[path].append({
            'timestamp': time.time(),
            'cid': cid,
            'direction': direction
        })

        # Write journal back to file
        with open(journal_file, 'w') as f:
            json.dump(journal, f, indent=2)

        return {
            'path': path,
            'cid': cid,
            'direction': direction,
            'status': 'recorded'
        }

    def get_history(self, path, limit=50):
        """Get history for a specific path"""
        journal_file = os.path.join(self.journal_path, 'sync_journal.json')

        # Check if journal exists
        if not os.path.exists(journal_file):
            return {
                'path': path,
                'entries': []
            }

        # Load journal
        with open(journal_file, 'r') as f:
            try:
                journal = json.load(f)
            except json.JSONDecodeError:
                return {
                    'path': path,
                    'entries': [],
                    'error': 'journal_error'
                }

        # Check if path is tracked
        if path not in journal:
            return {
                'path': path,
                'entries': []
            }

        # Get entries, limited to specified limit
        entries = journal[path][-limit:]

        return {
            'path': path,
            'entries': entries,
            'total': len(journal[path])
        }

    def sync_path(self, path, recursive=True):
        """Synchronize path to journal"""
        try:
            from ipfs_kit_py.api import Client
            ipfs_client = Client()
        except ImportError:
            return {
                'path': path,
                'error': 'ipfs_client_not_available'
            }

        full_path = os.path.join(self.base_dir, path)

        # Check if path exists
        if not os.path.exists(full_path):
            return {
                'path': path,
                'error': 'path_not_found'
            }

        # Add to IPFS
        if os.path.isdir(full_path):
            # For directories
            if recursive:
                result = ipfs_client.add(full_path, recursive=True)
            else:
                result = ipfs_client.add(full_path, recursive=False)
        else:
            # For files
            with open(full_path, 'rb') as f:
                content = f.read()
            result = ipfs_client.add(content)

        # Record in journal
        self.record_sync(path, result['Hash'], 'to_ipfs')

        return {
            'path': path,
            'cid': result['Hash'],
            'size': result.get('Size', 0)
        }

    def revert(self, path, version=0):
        """Revert to a previous version"""
        journal_file = os.path.join(self.journal_path, 'sync_journal.json')

        # Check if journal exists
        if not os.path.exists(journal_file):
            return {
                'path': path,
                'error': 'journal_not_found'
            }

        # Load journal
        with open(journal_file, 'r') as f:
            try:
                journal = json.load(f)
            except json.JSONDecodeError:
                return {
                    'path': path,
                    'error': 'journal_error'
                }

        # Check if path is tracked
        if path not in journal:
            return {
                'path': path,
                'error': 'path_not_tracked'
            }

        # Get entries
        entries = journal[path]
        if not entries:
            return {
                'path': path,
                'error': 'no_entries'
            }

        # Determine which version to revert to
        if version == 0:
            # Last version
            version_entry = entries[-1]
        elif version > 0 and version <= len(entries):
            # Specific version (1-based indexing)
            version_entry = entries[version-1]
        else:
            return {
                'path': path,
                'error': 'invalid_version',
                'available_versions': len(entries)
            }

        try:
            from ipfs_kit_py.api import Client
            ipfs_client = Client()
        except ImportError:
            return {
                'path': path,
                'error': 'ipfs_client_not_available'
            }

        # Get content from IPFS
        cid = version_entry['cid']
        content = ipfs_client.cat(cid)

        # Write to file
        full_path = os.path.join(self.base_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, 'wb') as f:
            f.write(content)

        # Record revert in journal
        self.record_sync(path, cid, 'revert')

        return {
            'path': path,
            'reverted_to_cid': cid,
            'reverted_to_version': version if version > 0 else len(entries)
        }

    def list_versions(self, path):
        """List available versions for a path"""
        journal_file = os.path.join(self.journal_path, 'sync_journal.json')

        # Check if journal exists
        if not os.path.exists(journal_file):
            return {
                'path': path,
                'versions': []
            }

        # Load journal
        with open(journal_file, 'r') as f:
            try:
                journal = json.load(f)
            except json.JSONDecodeError:
                return {
                    'path': path,
                    'versions': [],
                    'error': 'journal_error'
                }

        # Check if path is tracked
        if path not in journal:
            return {
                'path': path,
                'versions': []
            }

        # Convert entries to version list
        entries = journal[path]
        versions = []

        for i, entry in enumerate(entries):
            versions.append({
                'version': i + 1,  # 1-based indexing
                'timestamp': entry['timestamp'],
                'cid': entry['cid'],
                'direction': entry['direction']
            })

        return {
            'path': path,
            'versions': versions,
            'total': len(versions)
        }

def register_fs_journal_tools(mcp_server):
    """Register FS Journal tools with MCP server"""
    logger.info("Registering FS Journal tools...")

    # Initialize the journal
    journal = FSJournal()

    # Register tools
    @mcp_server.tool("fs_journal_get_history")
    def fs_journal_get_history(path, limit=50):
        """Get history of file changes"""
        logger.info(f"MCP Tool call: fs_journal_get_history({path}, {limit})")
        return journal.get_history(path, limit)

    @mcp_server.tool("fs_journal_sync")
    def fs_journal_sync(path, recursive=True):
        """Synchronize changes to journal"""
        logger.info(f"MCP Tool call: fs_journal_sync({path}, {recursive})")
        return journal.sync_path(path, recursive)

    @mcp_server.tool("fs_journal_revert")
    def fs_journal_revert(path, version=0):
        """Revert to previous version"""
        logger.info(f"MCP Tool call: fs_journal_revert({path}, {version})")
        return journal.revert(path, version)

    @mcp_server.tool("fs_journal_list_versions")
    def fs_journal_list_versions(path):
        """List available versions"""
        logger.info(f"MCP Tool call: fs_journal_list_versions({path})")
        return journal.list_versions(path)

    logger.info("✅ Successfully registered FS Journal tools with MCP server")
"""

    # Write the journal tools module
    with open("fs_journal_tools.py", "w") as f:
        f.write(journal_content)

    logger.info("✅ Created FS Journal tools at fs_journal_tools.py")

    # Create the multi-backend FS module
    multi_backend_content = """#!/usr/bin/env python3
'''
Multi-Backend Filesystem Integration for IPFS MCP
'''

import os
import sys
import logging
import json
import importlib
from typing import Dict, List, Any, Optional, Union, BinaryIO

logger = logging.getLogger(__name__)

class MultiBackendFS:
    """Multi-Backend Filesystem that integrates multiple storage systems"""

    def __init__(self, base_dir=None):
        """Initialize the multi-backend filesystem"""
        self.base_dir = base_dir or os.getcwd()
        self.backends = {}
        self.format_handlers = {}

        # Register default backends
        self._register_default_backends()

        # Register format handlers
        self._register_format_handlers()

        logger.info(f"Initialized Multi-Backend Filesystem with base directory: {self.base_dir}")

    def _register_default_backends(self):
        """Register default backends"""
        # Local filesystem backend
        self.backends['local'] = {
            'name': 'Local Filesystem',
            'description': 'Local filesystem storage',
            'get': self._local_get,
            'put': self._local_put,
            'list': self._local_list,
            'available': True
        }

        # IPFS backend
        try:
            from ipfs_kit_py.api import Client
            ipfs_client = Client()

            self.backends['ipfs'] = {
                'name': 'IPFS',
                'description': 'InterPlanetary File System',
                'get': self._ipfs_get,
                'put': self._ipfs_put,
                'list': self._ipfs_list,
                'client': ipfs_client,
                'available': True
            }
        except ImportError:
            self.backends['ipfs'] = {
                'name': 'IPFS',
                'description': 'InterPlanetary File System',
                'available': False,
                'error': 'Module not available'
            }

        # Try to register other backends
        # Filecoin
        try:
            from ipfs_kit_py.mcp.controllers.filecoin_controller import FilecoinController

            self.backends['filecoin'] = {
                'name': 'Filecoin',
                'description': 'Filecoin decentralized storage',
                'get': self._filecoin_get,
                'put': self._filecoin_put,
                'list': self._filecoin_list,
                'controller': FilecoinController(),
                'available': True
            }
        except ImportError:
            self.backends['filecoin'] = {
                'name': 'Filecoin',
                'description': 'Filecoin decentralized storage',
                'available': False,
                'error': 'Module not available'
            }

    def _register_format_handlers(self):
        """Register format handlers for different data formats"""
        # JSON handler
        self.format_handlers['json'] = {
            'name': 'JSON',
            'description': 'JSON data format',
            'serialize': self._json_serialize,
            'deserialize': self._json_deserialize,
            'available': True
        }

        logger.info("Registered format handler for json")

        # Try to register other format handlers
        # Parquet
        try:
            import pyarrow.parquet as pq
            import pyarrow as pa

            self.format_handlers['parquet'] = {
                'name': 'Parquet',
                'description': 'Apache Parquet columnar data format',
                'serialize': self._parquet_serialize,
                'deserialize': self._parquet_deserialize,
                'available': True
            }

            logger.info("Registered format handler for parquet")
        except ImportError:
            self.format_handlers['parquet'] = {
                'name': 'Parquet',
                'description': 'Apache Parquet columnar data format',
                'available': False,
                'error': 'Module not available'
            }

        # Arrow
        try:
            import pyarrow as pa

            self.format_handlers['arrow'] = {
                'name': 'Arrow',
                'description': 'Apache Arrow columnar data format',
                'serialize': self._arrow_serialize,
                'deserialize': self._arrow_deserialize,
                'available': True
            }

            logger.info("Registered format handler for arrow")
        except ImportError:
            self.format_handlers['arrow'] = {
                'name': 'Arrow',
                'description': 'Apache Arrow columnar data format',
                'available': False,
                'error': 'Module not available'
            }

        if 'parquet' in self.format_handlers and self.format_handlers['parquet']['available'] and \
           'arrow' in self.format_handlers and self.format_handlers['arrow']['available']:
            logger.info("Registered Parquet and Arrow format handlers")

    # Backend implementations
    def _local_get(self, path, **kwargs):
        """Get file from local filesystem"""
        full_path = os.path.join(self.base_dir, path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Path not found: {full_path}")

        with open(full_path, 'rb') as f:
            content = f.read()

        return content

    def _local_put(self, path, content, **kwargs):
        """Put file to local filesystem"""
        full_path = os.path.join(self.base_dir, path)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Write content
        with open(full_path, 'wb') as f:
            if isinstance(content, str):
                f.write(content.encode('utf-8'))
            else:
                f.write(content)

        return {
            'path': path,
