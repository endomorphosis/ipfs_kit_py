"""
Arrow-based cluster state management for IPFS distributed coordination.

This module provides a shared, persistent, and efficient state store for
cluster management using Apache Arrow and its Plasma shared memory system.
The state store enables zero-copy IPC across processes and languages,
making it ideal for distributed coordination.
"""

import os
import json
import time
import uuid
import hashlib
import logging
import tempfile
import subprocess
import atexit
import threading
from typing import Dict, List, Optional, Any, Tuple, Set, Union, Callable

# Arrow imports
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow.plasma import ObjectID, connect as plasma_connect

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)

def create_cluster_state_schema():
    """Create Arrow schema for cluster state.
    
    Returns:
        PyArrow schema for the cluster state
    """
    return pa.schema([
        # Cluster metadata
        pa.field('cluster_id', pa.string()),
        pa.field('master_id', pa.string()),
        pa.field('updated_at', pa.timestamp('ms')),
        
        # Node registry (nested table)
        pa.field('nodes', pa.list_(pa.struct([
            pa.field('id', pa.string()),
            pa.field('peer_id', pa.string()),
            pa.field('role', pa.string()),
            pa.field('status', pa.string()),
            pa.field('address', pa.string()),
            pa.field('last_seen', pa.timestamp('ms')),
            pa.field('resources', pa.struct([
                pa.field('cpu_count', pa.int16()),
                pa.field('cpu_usage', pa.float32()),
                pa.field('memory_total', pa.int64()),
                pa.field('memory_available', pa.int64()),
                pa.field('disk_total', pa.int64()),
                pa.field('disk_free', pa.int64()),
                pa.field('gpu_count', pa.int8()),
                pa.field('gpu_available', pa.bool_())
            ])),
            pa.field('tasks', pa.list_(pa.string())),  # List of assigned task IDs
            pa.field('capabilities', pa.list_(pa.string()))
        ]))),
        
        # Task registry (nested table)
        pa.field('tasks', pa.list_(pa.struct([
            pa.field('id', pa.string()),
            pa.field('type', pa.string()),
            pa.field('status', pa.string()),
            pa.field('priority', pa.int8()),
            pa.field('created_at', pa.timestamp('ms')),
            pa.field('updated_at', pa.timestamp('ms')),
            pa.field('assigned_to', pa.string()),
            pa.field('parameters', pa.map_(pa.string(), pa.string())),
            pa.field('result_cid', pa.string())
        ]))),
        
        # Content registry (optimized for discovery)
        pa.field('content', pa.list_(pa.struct([
            pa.field('cid', pa.string()),
            pa.field('size', pa.int64()),
            pa.field('providers', pa.list_(pa.string())),
            pa.field('replication', pa.int8()),
            pa.field('pinned_at', pa.timestamp('ms'))
        ])))
    ])

class ArrowClusterState:
    """Arrow-based cluster state with shared memory access.
    
    This class provides a shared, persistent state store for cluster management
    using Apache Arrow for zero-copy IPC and Plasma for shared memory access.
    It enables multiple processes to access and update the cluster state
    efficiently.
    """
    
    def __init__(self, cluster_id: str, node_id: str, 
                 state_path: Optional[str] = None,
                 memory_size: int = 1000000000,  # 1GB default
                 enable_persistence: bool = True):
        """Initialize cluster state with Arrow and shared memory.
        
        Args:
            cluster_id: Unique identifier for this cluster
            node_id: ID of this node (for master identification)
            state_path: Path to directory for persistent state storage
            memory_size: Size of the Plasma store in bytes (default: 1GB)
            enable_persistence: Whether to persist state to disk
        """
        self.cluster_id = cluster_id
        self.node_id = node_id
        self.state_path = state_path or os.path.expanduser("~/.ipfs_cluster_state")
        self.memory_size = memory_size
        self.enable_persistence = enable_persistence
        
        # Ensure state directory exists
        os.makedirs(self.state_path, exist_ok=True)
        
        # Create schema and initialize empty state
        self.schema = create_cluster_state_schema()
        self._initialize_empty_state()
        
        # Set up the shared memory mechanism
        self.plasma_socket = os.path.join(self.state_path, "plasma.sock")
        self.plasma_client = None
        self.plasma_process = None
        self.current_object_id = None
        
        # Load state from disk if available
        if enable_persistence and not self._load_from_disk():
            logger.info("No existing state found. Starting with empty state.")
            
        # Set up shared memory (using Plasma store for Arrow C Data Interface)
        self._setup_shared_memory()
        
        # Register state sync mechanism
        self._state_version = 0
        self._state_lock = threading.RLock()
        
        # Register cleanup on exit
        atexit.register(self._cleanup)
    
    def _initialize_empty_state(self):
        """Initialize an empty cluster state table."""
        # Create empty arrays for each field in the schema
        arrays = []
        for field in self.schema:
            arrays.append(pa.array([], type=field.type))
            
        # Create an empty table with the schema
        self.state_table = pa.Table.from_arrays(arrays, schema=self.schema)
    
    def _setup_shared_memory(self):
        """Set up shared memory using Arrow Plasma store."""
        try:
            # Try to connect to existing plasma store
            logger.debug(f"Trying to connect to existing plasma store at {self.plasma_socket}")
            self.plasma_client = plasma_connect(self.plasma_socket)
            logger.info(f"Connected to existing plasma store at {self.plasma_socket}")
        except Exception as e:
            logger.debug(f"Failed to connect to existing plasma store: {e}")
            # Start a new plasma store if connection fails
            self._start_plasma_store()
            
        # Initial export to shared memory
        self._export_to_shared_memory()
    
    def _start_plasma_store(self):
        """Start a plasma store process for shared memory."""
        logger.info(f"Starting plasma store with {self.memory_size} bytes at {self.plasma_socket}")
        try:
            # Create a command for the plasma_store executable
            cmd = [
                "plasma_store",
                "-m", str(self.memory_size),
                "-s", self.plasma_socket
            ]
            
            # Start the process in the background
            self.plasma_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a moment for the process to start
            time.sleep(1)
            
            # Check if the process started successfully
            if self.plasma_process.poll() is not None:
                # Process exited immediately
                stdout, stderr = self.plasma_process.communicate()
                logger.error(f"Failed to start plasma store: {stderr.decode()}")
                raise RuntimeError(f"Plasma store failed to start: {stderr.decode()}")
            
            # Try to connect to the store
            self.plasma_client = plasma_connect(self.plasma_socket)
            logger.info("Successfully connected to newly started plasma store")
            
        except Exception as e:
            logger.error(f"Error starting plasma store: {e}")
            # Clean up if the process was started
            if self.plasma_process and self.plasma_process.poll() is None:
                self.plasma_process.terminate()
                self.plasma_process = None
            raise
    
    def _cleanup(self):
        """Clean up resources when the object is destroyed."""
        logger.debug("Cleaning up Arrow cluster state resources")
        
        try:
            # Final state persistence if enabled
            if self.enable_persistence:
                self._save_to_disk()
        except Exception as e:
            logger.error(f"Error saving final state to disk: {e}")
            
        # Clean up plasma process if we started it
        if self.plasma_process and self.plasma_process.poll() is None:
            try:
                logger.debug("Terminating plasma store process")
                self.plasma_process.terminate()
                self.plasma_process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error terminating plasma process: {e}")
    
    def _export_to_shared_memory(self):
        """Export the current state table to shared memory.
        
        Returns:
            ObjectID of the exported table in plasma store
        """
        if not self.plasma_client:
            logger.error("Cannot export to shared memory: plasma client not initialized")
            return None
            
        try:
            # Create object ID based on cluster ID and version
            self._state_version += 1
            id_string = f"{self.cluster_id}_{self._state_version}_{int(time.time()*1000)}"
            object_id_bytes = hashlib.md5(id_string.encode()).digest()[:20]
            object_id = ObjectID(object_id_bytes)
            
            # Calculate size needed for the table
            data_size = self.state_table.nbytes + 10000  # Add buffer for safety
            
            # Create the object
            buffer = self.plasma_client.create(object_id, data_size)
            
            # Write the table to the buffer
            writer = pa.RecordBatchStreamWriter(pa.FixedSizeBufferWriter(buffer), self.state_table.schema)
            writer.write_table(self.state_table)
            writer.close()
            
            # Seal the object to make it available to other processes
            self.plasma_client.seal(object_id)
            
            # Store the current object ID
            self.current_object_id = object_id
            
            # Write metadata file for other processes
            self._write_metadata()
            
            logger.debug(f"Exported state to shared memory with object ID: {object_id.binary().hex()}")
            return object_id
            
        except Exception as e:
            logger.error(f"Error exporting state to shared memory: {e}")
            return None
    
    def _write_metadata(self):
        """Write metadata file for external process access."""
        if not self.current_object_id:
            return
            
        metadata = {
            'object_id': self.current_object_id.binary().hex(),
            'plasma_socket': self.plasma_socket,
            'schema': self.schema.to_string(),
            'updated_at': time.time(),
            'version': self._state_version,
            'cluster_id': self.cluster_id
        }
        
        # First write to a temporary file and then rename to avoid partial reads
        temp_file = os.path.join(self.state_path, f'.state_metadata.{uuid.uuid4()}.json')
        try:
            with open(temp_file, 'w') as f:
                json.dump(metadata, f)
                
            target_file = os.path.join(self.state_path, 'state_metadata.json')
            os.rename(temp_file, target_file)
            
        except Exception as e:
            logger.error(f"Error writing metadata file: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    def _save_to_disk(self):
        """Save the current state to disk for persistence."""
        if not self.enable_persistence:
            return
            
        try:
            # Save current state as parquet file
            parquet_path = os.path.join(self.state_path, f"state_{self.cluster_id}.parquet")
            pq.write_table(self.state_table, parquet_path, compression='zstd')
            
            # Save a checkpoint with timestamp for historical tracking
            timestamp = int(time.time())
            checkpoint_dir = os.path.join(self.state_path, 'checkpoints')
            os.makedirs(checkpoint_dir, exist_ok=True)
            
            # Limit number of checkpoints to keep
            checkpoints = sorted([
                f for f in os.listdir(checkpoint_dir) 
                if f.startswith(f"state_{self.cluster_id}_")
            ])
            
            # Remove old checkpoints if we have too many
            max_checkpoints = 10
            if len(checkpoints) >= max_checkpoints:
                for old_checkpoint in checkpoints[:-max_checkpoints + 1]:
                    try:
                        os.remove(os.path.join(checkpoint_dir, old_checkpoint))
                    except:
                        pass
            
            # Save new checkpoint
            checkpoint_path = os.path.join(
                checkpoint_dir, 
                f"state_{self.cluster_id}_{timestamp}.parquet"
            )
            pq.write_table(self.state_table, checkpoint_path, compression='zstd')
            
            logger.debug(f"Saved state to disk: {parquet_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving state to disk: {e}")
            return False
    
    def _load_from_disk(self):
        """Load the most recent state from disk.
        
        Returns:
            Boolean indicating whether state was successfully loaded
        """
        if not self.enable_persistence:
            return False
            
        parquet_path = os.path.join(self.state_path, f"state_{self.cluster_id}.parquet")
        if not os.path.exists(parquet_path):
            return False
            
        try:
            # Load the table from parquet file
            self.state_table = pq.read_table(parquet_path)
            logger.info(f"Loaded state from disk: {parquet_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading state from disk: {e}")
            return False
    
    def update_state(self, update_function: Callable[[pa.Table], pa.Table]):
        """Update the state atomically using a provided function.
        
        This method ensures that state updates are atomic and consistent by:
        1. Acquiring a lock to prevent concurrent updates
        2. Applying the update function to get a new state
        3. Exporting the new state to shared memory
        4. Saving the state to disk for persistence
        
        Args:
            update_function: Function that takes the current state table and returns
                             a modified state table
                             
        Returns:
            Boolean indicating whether the update was successful
        """
        with self._state_lock:
            try:
                # Get current state
                current_state = self.state_table
                
                # Apply the update function to get new state
                new_state = update_function(current_state)
                
                # Validate that the update function returned a valid table with the right schema
                if not isinstance(new_state, pa.Table):
                    logger.error("Update function did not return a PyArrow Table")
                    return False
                    
                if not new_state.schema.equals(self.schema):
                    logger.error("Update function returned a table with incompatible schema")
                    return False
                
                # Replace the current state
                self.state_table = new_state
                
                # Export to shared memory
                self._export_to_shared_memory()
                
                # Save to disk for persistence
                if self.enable_persistence:
                    self._save_to_disk()
                    
                return True
                
            except Exception as e:
                logger.error(f"Error updating state: {e}")
                return False
    
    def get_state(self):
        """Get a copy of the current state table.
        
        Returns:
            PyArrow Table with the current state
        """
        with self._state_lock:
            return self.state_table
    
    def get_node_info(self, node_id):
        """Get information about a specific node.
        
        Args:
            node_id: ID of the node to get information for
            
        Returns:
            Dictionary with node information or None if not found
        """
        state = self.get_state()
        
        # Check if state is empty
        if state.num_rows == 0:
            return None
            
        # Convert to pandas for easier nested data handling if available
        if PANDAS_AVAILABLE:
            try:
                df = state.to_pandas()
                if len(df) == 0:
                    return None
                    
                nodes = df.iloc[0]['nodes']
                for node in nodes:
                    if node['id'] == node_id:
                        return node
                        
                return None
                
            except Exception as e:
                logger.error(f"Error converting to pandas: {e}")
                
        # Fallback to PyArrow API
        try:
            # Get the first row
            row = state.slice(0, 1)
            
            # Get the nodes column
            nodes_column = row.column('nodes')
            
            # Get the nodes list from the first row
            nodes_list = nodes_column[0].as_py()
            
            # Find the node with matching ID
            for node in nodes_list:
                if node['id'] == node_id:
                    return node
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting node info: {e}")
            return None
    
    def get_task_info(self, task_id):
        """Get information about a specific task.
        
        Args:
            task_id: ID of the task to get information for
            
        Returns:
            Dictionary with task information or None if not found
        """
        state = self.get_state()
        
        # Check if state is empty
        if state.num_rows == 0:
            return None
            
        # Convert to pandas for easier nested data handling if available
        if PANDAS_AVAILABLE:
            try:
                df = state.to_pandas()
                if len(df) == 0:
                    return None
                    
                tasks = df.iloc[0]['tasks']
                for task in tasks:
                    if task['id'] == task_id:
                        return task
                        
                return None
                
            except Exception as e:
                logger.error(f"Error converting to pandas: {e}")
                
        # Fallback to PyArrow API
        try:
            # Get the first row
            row = state.slice(0, 1)
            
            # Get the tasks column
            tasks_column = row.column('tasks')
            
            # Get the tasks list from the first row
            tasks_list = tasks_column[0].as_py()
            
            # Find the task with matching ID
            for task in tasks_list:
                if task['id'] == task_id:
                    return task
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting task info: {e}")
            return None
    
    def update_node(self, node_id, **kwargs):
        """Update properties of a specific node.
        
        Args:
            node_id: ID of the node to update
            **kwargs: Node properties to update
            
        Returns:
            Boolean indicating whether the update was successful
        """
        def update_function(current_state):
            # Return current state if empty
            if current_state.num_rows == 0:
                logger.warning("Cannot update node: state is empty")
                return current_state
                
            # Convert to pandas for easier manipulation if available
            if PANDAS_AVAILABLE:
                try:
                    df = current_state.to_pandas()
                    if len(df) == 0:
                        return current_state
                        
                    # Update the node in the nodes list
                    nodes = df.iloc[0]['nodes']
                    for i, node in enumerate(nodes):
                        if node['id'] == node_id:
                            # Update node properties
                            for key, value in kwargs.items():
                                nodes[i][key] = value
                                
                            # Update updated_at timestamp
                            df.iloc[0]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                            
                            # Return updated state
                            return pa.Table.from_pandas(df, schema=current_state.schema)
                            
                    logger.warning(f"Node {node_id} not found in state")
                    return current_state
                    
                except Exception as e:
                    logger.error(f"Error updating node with pandas: {e}")
                    return current_state
            
            # Fallback to PyArrow API (more complex)
            try:
                # Return current state for now
                # In a real implementation, you would need to:
                # 1. Extract the nodes array from the state
                # 2. Find the node with the matching ID
                # 3. Update the properties
                # 4. Create a new state table with the updated nodes
                logger.warning("PyArrow API node update not implemented")
                return current_state
                
            except Exception as e:
                logger.error(f"Error updating node: {e}")
                return current_state
                
        return self.update_state(update_function)
    
    def add_node(self, node_id, peer_id, role, address='', resources=None, capabilities=None):
        """Add a new node to the cluster state.
        
        Args:
            node_id: Unique identifier for the node
            peer_id: IPFS peer ID of the node
            role: Role of the node ("master", "worker", or "leecher")
            address: Network address of the node
            resources: Dictionary of node resources
            capabilities: List of node capabilities
            
        Returns:
            Boolean indicating whether the node was added successfully
        """
        # Set default values
        if resources is None:
            resources = {
                'cpu_count': 1,
                'cpu_usage': 0.0,
                'memory_total': 0,
                'memory_available': 0,
                'disk_total': 0,
                'disk_free': 0,
                'gpu_count': 0,
                'gpu_available': False
            }
            
        if capabilities is None:
            capabilities = []
            
        def update_function(current_state):
            # If state is empty, initialize with this node
            if current_state.num_rows == 0:
                # Create initial state with this node
                node_data = {
                    'id': node_id,
                    'peer_id': peer_id,
                    'role': role,
                    'status': 'online',
                    'address': address,
                    'last_seen': pa.scalar(time.time() * 1000).cast(pa.timestamp('ms')),
                    'resources': resources,
                    'tasks': [],
                    'capabilities': capabilities
                }
                
                data = {
                    'cluster_id': [self.cluster_id],
                    'master_id': [node_id if role == 'master' else ''],
                    'updated_at': [pa.scalar(time.time() * 1000).cast(pa.timestamp('ms'))],
                    'nodes': [[node_data]],
                    'tasks': [[]],
                    'content': [[]]
                }
                
                return pa.Table.from_pydict(data, schema=current_state.schema)
            
            # Convert to pandas for easier manipulation if available
            if PANDAS_AVAILABLE:
                try:
                    df = current_state.to_pandas()
                    
                    # Prepare node data
                    node_data = {
                        'id': node_id,
                        'peer_id': peer_id,
                        'role': role,
                        'status': 'online',
                        'address': address,
                        'last_seen': pd.Timestamp(time.time() * 1000, unit='ms'),
                        'resources': resources,
                        'tasks': [],
                        'capabilities': capabilities
                    }
                    
                    # Check if node already exists
                    nodes = df.iloc[0]['nodes']
                    for i, node in enumerate(nodes):
                        if node['id'] == node_id:
                            # Update existing node
                            logger.debug(f"Updating existing node {node_id}")
                            nodes[i] = node_data
                            df.iloc[0]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                            return pa.Table.from_pandas(df, schema=current_state.schema)
                    
                    # Add new node
                    logger.debug(f"Adding new node {node_id}")
                    nodes.append(node_data)
                    df.iloc[0]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                    
                    # If this is a master node and master_id is empty, set it
                    if role == 'master' and (not df.iloc[0]['master_id'] or df.iloc[0]['master_id'] == ''):
                        df.iloc[0]['master_id'] = node_id
                        
                    return pa.Table.from_pandas(df, schema=current_state.schema)
                    
                except Exception as e:
                    logger.error(f"Error adding node with pandas: {e}")
                    return current_state
            
            # Fallback to PyArrow API (more complex)
            logger.warning("PyArrow API node addition not implemented")
            return current_state
            
        return self.update_state(update_function)
    
    def add_task(self, task_id, task_type, parameters=None, priority=0):
        """Add a new task to the cluster state.
        
        Args:
            task_id: Unique identifier for the task
            task_type: Type of the task
            parameters: Dictionary of task parameters
            priority: Task priority (0-9, higher is more important)
            
        Returns:
            Boolean indicating whether the task was added successfully
        """
        if parameters is None:
            parameters = {}
            
        # Convert parameters to string map for storage
        string_params = {}
        for k, v in parameters.items():
            string_params[str(k)] = str(v)
            
        def update_function(current_state):
            # If state is empty, we can't add tasks
            if current_state.num_rows == 0:
                logger.warning("Cannot add task: state is empty")
                return current_state
                
            # Convert to pandas for easier manipulation if available
            if PANDAS_AVAILABLE:
                try:
                    df = current_state.to_pandas()
                    
                    # Prepare task data
                    task_data = {
                        'id': task_id,
                        'type': task_type,
                        'status': 'pending',
                        'priority': priority,
                        'created_at': pd.Timestamp(time.time() * 1000, unit='ms'),
                        'updated_at': pd.Timestamp(time.time() * 1000, unit='ms'),
                        'assigned_to': '',
                        'parameters': string_params,
                        'result_cid': ''
                    }
                    
                    # Check if task already exists
                    tasks = df.iloc[0]['tasks']
                    for i, task in enumerate(tasks):
                        if task['id'] == task_id:
                            # Update existing task
                            logger.debug(f"Updating existing task {task_id}")
                            tasks[i] = task_data
                            df.iloc[0]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                            return pa.Table.from_pandas(df, schema=current_state.schema)
                    
                    # Add new task
                    logger.debug(f"Adding new task {task_id}")
                    tasks.append(task_data)
                    df.iloc[0]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                    return pa.Table.from_pandas(df, schema=current_state.schema)
                    
                except Exception as e:
                    logger.error(f"Error adding task with pandas: {e}")
                    return current_state
            
            # Fallback to PyArrow API (more complex)
            logger.warning("PyArrow API task addition not implemented")
            return current_state
            
        return self.update_state(update_function)
    
    def update_task(self, task_id, **kwargs):
        """Update properties of a specific task.
        
        Args:
            task_id: ID of the task to update
            **kwargs: Task properties to update
            
        Returns:
            Boolean indicating whether the update was successful
        """
        def update_function(current_state):
            # Return current state if empty
            if current_state.num_rows == 0:
                logger.warning("Cannot update task: state is empty")
                return current_state
                
            # Convert to pandas for easier manipulation if available
            if PANDAS_AVAILABLE:
                try:
                    df = current_state.to_pandas()
                    if len(df) == 0:
                        return current_state
                        
                    # Update the task in the tasks list
                    tasks = df.iloc[0]['tasks']
                    for i, task in enumerate(tasks):
                        if task['id'] == task_id:
                            # Update task properties
                            for key, value in kwargs.items():
                                tasks[i][key] = value
                                
                            # Update updated_at timestamp for both task and state
                            tasks[i]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                            df.iloc[0]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                            
                            # Return updated state
                            return pa.Table.from_pandas(df, schema=current_state.schema)
                            
                    logger.warning(f"Task {task_id} not found in state")
                    return current_state
                    
                except Exception as e:
                    logger.error(f"Error updating task with pandas: {e}")
                    return current_state
            
            # Fallback to PyArrow API (more complex)
            logger.warning("PyArrow API task update not implemented")
            return current_state
                
        return self.update_state(update_function)
    
    def assign_task(self, task_id, node_id):
        """Assign a task to a specific node.
        
        This updates both the task's assigned_to field and adds the task
        to the node's tasks list.
        
        Args:
            task_id: ID of the task to assign
            node_id: ID of the node to assign the task to
            
        Returns:
            Boolean indicating whether the assignment was successful
        """
        def update_function(current_state):
            # Return current state if empty
            if current_state.num_rows == 0:
                logger.warning("Cannot assign task: state is empty")
                return current_state
                
            # Convert to pandas for easier manipulation if available
            if PANDAS_AVAILABLE:
                try:
                    df = current_state.to_pandas()
                    if len(df) == 0:
                        return current_state
                        
                    # Find the task
                    task_found = False
                    tasks = df.iloc[0]['tasks']
                    for i, task in enumerate(tasks):
                        if task['id'] == task_id:
                            # Update task assignment
                            tasks[i]['assigned_to'] = node_id
                            tasks[i]['status'] = 'assigned'
                            tasks[i]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                            task_found = True
                            break
                            
                    if not task_found:
                        logger.warning(f"Task {task_id} not found in state")
                        return current_state
                        
                    # Find the node
                    node_found = False
                    nodes = df.iloc[0]['nodes']
                    for i, node in enumerate(nodes):
                        if node['id'] == node_id:
                            # Add task to node's task list if not already there
                            if task_id not in node['tasks']:
                                node['tasks'].append(task_id)
                            node_found = True
                            break
                            
                    if not node_found:
                        logger.warning(f"Node {node_id} not found in state")
                        return current_state
                        
                    # Update state timestamp
                    df.iloc[0]['updated_at'] = pd.Timestamp(time.time() * 1000, unit='ms')
                    
                    # Return updated state
                    return pa.Table.from_pandas(df, schema=current_state.schema)
                    
                except Exception as e:
                    logger.error(f"Error assigning task with pandas: {e}")
                    return current_state
            
            # Fallback to PyArrow API (more complex)
            logger.warning("PyArrow API task assignment not implemented")
            return current_state
                
        return self.update_state(update_function)
    
    def get_metadata_for_external_access(self):
        """Get state metadata information for external process access.
        
        Returns:
            Dictionary with metadata for external access
        """
        if not self.current_object_id:
            return {
                "error": "No current state available",
                "state_path": self.state_path
            }
            
        return {
            'object_id': self.current_object_id.binary().hex(),
            'plasma_socket': self.plasma_socket,
            'schema': self.schema.to_string(),
            'updated_at': time.time(),
            'version': self._state_version,
            'cluster_id': self.cluster_id
        }
    
    @staticmethod
    def access_from_external_process(state_path):
        """Access the cluster state from another process.
        
        This static method allows external processes to access the state
        without needing to instantiate a full ArrowClusterState object.
        
        Args:
            state_path: Path to the cluster state directory
            
        Returns:
            PyArrow Table with the current cluster state, or None if not available
        """
        try:
            # Read metadata file to get plasma socket and object ID
            metadata_path = os.path.join(state_path, 'state_metadata.json')
            if not os.path.exists(metadata_path):
                logger.error(f"State metadata file not found at {metadata_path}")
                return None
                
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                
            # Get plasma socket
            plasma_socket = metadata.get('plasma_socket')
            if not plasma_socket or not os.path.exists(plasma_socket):
                logger.error(f"Plasma socket not found at {plasma_socket}")
                return None
                
            # Get object ID
            object_id_hex = metadata.get('object_id')
            if not object_id_hex:
                logger.error("Object ID not found in metadata")
                return None
                
            # Connect to plasma store
            plasma_client = plasma_connect(plasma_socket)
            
            # Get object ID
            object_id = ObjectID(bytes.fromhex(object_id_hex))
            
            # Get the object from plasma store
            if not plasma_client.contains(object_id):
                logger.error(f"Object {object_id_hex} not found in plasma store")
                return None
                
            # Get the buffer and read the table
            buffer = plasma_client.get(object_id)
            reader = pa.RecordBatchStreamReader(buffer)
            
            # Return the table
            return reader.read_all()
            
        except Exception as e:
            logger.error(f"Error accessing cluster state: {e}")
            return None