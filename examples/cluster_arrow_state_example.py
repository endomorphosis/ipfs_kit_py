import logging
import os
import pyarrow as pa
import pandas as pd # Often used with Arrow data

# Import the helper functions
from ipfs_kit_py import cluster_state_helpers
# We might need ArrowClusterState to create dummy data if needed for the example
from ipfs_kit_py.cluster_state import ArrowClusterState, create_cluster_state_schema

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# Define the path where the cluster state is expected to be persisted
# This path should match the 'persist_path' in the cluster configuration
DEFAULT_STATE_PATH = os.path.expanduser("~/.ipfs_kit/cluster_state/current_state.arrow") # Example path

# --- Helper Function to Create Dummy State (for standalone example execution) ---
def create_dummy_state_if_not_exists(state_path):
    """Creates a simple dummy Arrow state file if one doesn't exist."""
    state_dir = os.path.dirname(state_path)
    if not os.path.exists(state_path):
        logging.warning(f"State file not found at {state_path}. Creating dummy state for example.")
        os.makedirs(state_dir, exist_ok=True)
        try:
            # Create a minimal ArrowClusterState instance just to save an empty/basic table
            # Note: This requires pyarrow to be installed.
            schema = create_cluster_state_schema() # Get the schema
            # Create empty table based on schema
            empty_table = pa.Table.from_pylist([], schema=schema)

            # Add some dummy data (adjust schema fields as needed based on current implementation)
            dummy_nodes = [
                {'node_id': 'node1', 'peer_id': 'peer1_id', 'role': 'Master', 'address': '/ip4/127.0.0.1/tcp/4001', 'status': 'Online', 'last_heartbeat': pd.Timestamp.now(tz='UTC'), 'resources': {'cpu': 0.5, 'memory_gb': 4.0}, 'capabilities': ['storage'], 'tasks_assigned': 1},
                {'node_id': 'node2', 'peer_id': 'peer2_id', 'role': 'Worker', 'address': '/ip4/192.168.1.10/tcp/4001', 'status': 'Online', 'last_heartbeat': pd.Timestamp.now(tz='UTC'), 'resources': {'cpu': 0.8, 'memory_gb': 8.0}, 'capabilities': ['storage', 'gpu'], 'tasks_assigned': 0},
            ]
            dummy_tasks = [
                 {'task_id': 'task1', 'task_type': 'pin', 'status': 'Running', 'parameters': {'cid': 'QmABC...'}, 'priority': 1, 'assigned_node_id': 'node1', 'submit_time': pd.Timestamp.now(tz='UTC'), 'start_time': pd.Timestamp.now(tz='UTC'), 'end_time': None, 'result_cid': None, 'error_message': None},
                 {'task_id': 'task2', 'task_type': 'process', 'status': 'Pending', 'parameters': {'input_cid': 'QmXYZ...'}, 'priority': 0, 'assigned_node_id': None, 'submit_time': pd.Timestamp.now(tz='UTC'), 'start_time': None, 'end_time': None, 'result_cid': None, 'error_message': None},
            ]

            # Create tables (adjust based on actual schema structure)
            # This assumes state is one table. If multiple tables (nodes, tasks), adjust accordingly.
            # For simplicity, let's assume a single table structure for the dummy data creation.
            # A more robust dummy creation would inspect the schema from create_cluster_state_schema()
            # For now, we'll just save an empty table as a placeholder if schema is complex.
            table_to_save = empty_table # Start with empty based on schema

            # Persist the dummy table
            with pa.OSFile(state_path, 'wb') as sink:
                 with pa.ipc.new_file(sink, schema=table_to_save.schema) as writer:
                     writer.write_table(table_to_save)
            logging.info(f"Dummy state file created at {state_path}")

        except Exception as e:
            logging.error(f"Failed to create dummy state file: {e}", exc_info=True)
            return False
    return True

# --- Main Example Logic ---
def main(state_path=DEFAULT_STATE_PATH):
    logging.info(f"Attempting to query cluster state from: {state_path}")

    if not create_dummy_state_if_not_exists(state_path):
         logging.error("Could not ensure state file exists. Aborting example.")
         return

    # Use helper functions to query the state
    try:
        logging.info("\n--- Querying Nodes ---")
        all_nodes = cluster_state_helpers.get_all_nodes(state_path)
        if all_nodes is not None:
            logging.info(f"Found {len(all_nodes)} nodes:")
            for node in all_nodes:
                logging.info(f"  - Node ID: {node.get('node_id')}, Role: {node.get('role')}, Status: {node.get('status')}")
        else:
            logging.warning("Could not retrieve node information (state file might be empty or invalid).")

        logging.info("\n--- Querying Tasks ---")
        all_tasks = cluster_state_helpers.get_all_tasks(state_path)
        if all_tasks is not None:
            logging.info(f"Found {len(all_tasks)} tasks:")
            for task in all_tasks:
                 logging.info(f"  - Task ID: {task.get('task_id')}, Type: {task.get('task_type')}, Status: {task.get('status')}")

            # Example: Find pending tasks
            pending_tasks = cluster_state_helpers.find_tasks_by_status(state_path, 'Pending')
            logging.info(f"\nFound {len(pending_tasks)} Pending tasks:")
            for task in pending_tasks:
                 logging.info(f"  - Task ID: {task.get('task_id')}")

            # Example: Get a specific task
            task_id_to_find = "task1" # Use an ID from dummy data if applicable
            specific_task = cluster_state_helpers.get_task_by_id(state_path, task_id_to_find)
            if specific_task:
                logging.info(f"\nDetails for Task '{task_id_to_find}': {specific_task}")
            else:
                logging.info(f"\nTask '{task_id_to_find}' not found.")
        else:
            logging.warning("Could not retrieve task information.")


        logging.info("\n--- Querying Cluster Status Summary ---")
        summary = cluster_state_helpers.get_cluster_status_summary(state_path)
        if summary:
            logging.info(f"Cluster Summary: {summary}")
        else:
            logging.warning("Could not generate cluster summary.")

        # Example: Get state as Pandas DataFrames (requires pandas installed)
        try:
            state_dfs = cluster_state_helpers.get_cluster_state_as_pandas(state_path)
            if state_dfs:
                logging.info("\n--- State as Pandas DataFrames ---")
                for name, df in state_dfs.items():
                    logging.info(f"\nDataFrame '{name}':")
                    logging.info(df.head()) # Print first few rows
            else:
                 logging.warning("Could not get state as Pandas DataFrames.")
        except ImportError:
            logging.warning("Pandas library not installed. Skipping DataFrame example.")
        except Exception as e:
             logging.error(f"Error getting state as Pandas: {e}")


    except FileNotFoundError:
        logging.error(f"State file not found at {state_path}. Ensure the cluster is running or the path is correct.")
    except Exception as e:
        logging.error(f"An error occurred while querying the state: {e}", exc_info=True)

    logging.info("\nCluster Arrow state example finished.")

if __name__ == "__main__":
    # You can optionally pass a different state path via command line argument
    # import sys
    # path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STATE_PATH
    main()
