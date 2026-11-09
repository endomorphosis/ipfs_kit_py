import logging
import os
import time
import random
# Assuming access to internal components for demonstration
try:
    from ipfs_kit_py.cluster_dynamic_roles import ClusterDynamicRoles
    # Need a mock kit instance to pass to ClusterDynamicRoles
    class MockIPFSKit:
        def __init__(self, config):
            self.config = config
            self.role = config.get('cluster', {}).get('role', 'leecher') # Initial role
            self.peer_id = config.get('cluster', {}).get('node_id', 'test_node')
            # Mock other methods if needed by ClusterDynamicRoles
            self.cluster_manager = None # Add mock cluster manager if needed

        def get_config_value(self, keys, default=None):
            val = self.config
            try:
                for key in keys:
                    val = val[key]
                return val
            except (KeyError, TypeError):
                return default

        # Add mock methods called by ClusterDynamicRoles (e.g., for changing config, restarting services)
        def update_config(self, key_path, value):
             log.info(f"MOCK: Updating config {key_path} to {value}")
             # Update self.config simulation
             d = self.config
             for key in key_path[:-1]:
                 d = d.setdefault(key, {})
             d[key_path[-1]] = value
             # Update internal role if changed
             if key_path == ['cluster', 'role']:
                 self.role = value

        def restart_component(self, component_name):
             log.info(f"MOCK: Restarting component {component_name}")

        def announce_role_change(self, new_role):
             log.info(f"MOCK: Announcing role change to {new_role}")

except ImportError:
    logging.error("Required classes not found. Ensure cluster features are installed/available.")
    class ClusterDynamicRoles: pass
    class MockIPFSKit: pass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("DynamicRolesExample")

# --- Configuration ---
# Example config enabling dynamic roles with defined requirements
config = {
    'cluster': {
        'node_id': 'dynamic_node_1',
        'role': 'leecher', # Start as leecher
        'dynamic_roles': {
            'enabled': True,
            'check_interval_seconds': 10, # Check frequently for demo
            'requirements': {
                'worker': {
                    'min_cpu_cores': 2,
                    'min_memory_gb': 1, # Lowered for easier simulation
                    'min_disk_gb': 5,   # Lowered for easier simulation
                    'min_bandwidth_mbps': 5,
                },
                'master': {
                    'min_cpu_cores': 4,
                    'min_memory_gb': 2, # Lowered for easier simulation
                    'min_disk_gb': 2,
                    'min_bandwidth_mbps': 10,
                    'min_network_stability': 0.8
                }
            },
            'prefer_upgrade': True
        }
        # Add other cluster config if needed by mocked methods
    }
}

# --- Resource Simulation ---
# Simulate changing resource availability
simulated_resources = {
    'cpu_cores': 1,
    'memory_gb': 0.5,
    'disk_gb': 10,
    'bandwidth_mbps': 20,
    'network_stability': 0.9,
    'gpu_available': False
}

def update_simulated_resources():
    """Randomly increase resources over time to trigger upgrades."""
    simulated_resources['cpu_cores'] = min(8, simulated_resources['cpu_cores'] + random.choice([0, 1, 1, 2]))
    simulated_resources['memory_gb'] = min(16, simulated_resources['memory_gb'] + random.choice([0, 0.5, 0.5, 1]))
    simulated_resources['disk_gb'] = max(1, simulated_resources['disk_gb'] - random.choice([0, 0, 1])) # Simulate usage
    log.info(f"Simulated resources updated: CPU={simulated_resources['cpu_cores']}, Mem={simulated_resources['memory_gb']}GB")

# --- Mock Resource Detection ---
# Override methods in ClusterDynamicRoles to use simulated values
class MockableClusterDynamicRoles(ClusterDynamicRoles):
    def detect_available_resources(self) -> dict:
        # Return our simulated values instead of checking the actual system
        log.debug("Using simulated resource detection.")
        return {
            'cpu_cores': simulated_resources['cpu_cores'],
            'memory_total_gb': simulated_resources['memory_gb'],
            'disk_available_gb': simulated_resources['disk_gb'],
            'estimated_bandwidth_mbps': simulated_resources['bandwidth_mbps'],
            'network_stability': simulated_resources['network_stability'],
            'gpu_available': simulated_resources['gpu_available']
        }

    # Override other detection methods if they are called directly
    def _estimate_bandwidth(self) -> int:
        return simulated_resources['bandwidth_mbps']

    def _detect_gpu(self) -> bool:
        return simulated_resources['gpu_available']

    def _assess_network_stability(self) -> float:
        return simulated_resources['network_stability']

# --- Main Example Logic ---
def main():
    log.info("Demonstrating Cluster Dynamic Roles.")

    # Create mock kit instance
    mock_kit = MockIPFSKit(config)

    try:
        # Initialize Dynamic Roles manager
        dynamic_roles = MockableClusterDynamicRoles(ipfs_kit_instance=mock_kit)
        log.info(f"Initialized. Current role: {mock_kit.role}")

        # Simulate running the check periodically
        max_checks = 5
        for i in range(max_checks):
            log.info(f"\n--- Dynamic Role Check {i+1}/{max_checks} ---")
            current_role_before = mock_kit.role
            log.info(f"Current Role (Before Check): {current_role_before}")
            log.info(f"Current Simulated Resources: {simulated_resources}")

            # Manually trigger the check (in real app, this runs on a timer)
            result = dynamic_roles.check_and_update_role()
            log.info(f"Check Result: {result}")

            current_role_after = mock_kit.role # Role might have been updated by change_role
            log.info(f"Current Role (After Check): {current_role_after}")

            if current_role_before != current_role_after:
                log.info(f"ROLE CHANGED from {current_role_before} to {current_role_after}!")
            elif result.get("optimal_role") != current_role_before:
                 log.info(f"Role did not change, but optimal role is {result.get('optimal_role')}. Reason: {result.get('reason')}")
            else:
                 log.info("Role remains optimal.")


            # Update simulated resources for the next check
            if i < max_checks - 1:
                 update_simulated_resources()
                 log.info("Waiting for next check interval...")
                 time.sleep(config['cluster']['dynamic_roles']['check_interval_seconds'])


    except Exception as e:
        log.error(f"An error occurred during the dynamic roles example: {e}", exc_info=True)

    finally:
        log.info("\nDynamic roles example finished.")

if __name__ == "__main__":
    main()
