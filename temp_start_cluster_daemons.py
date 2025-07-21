import sys
import os
import json
import traceback
import asyncio
import subprocess
import time

# Add the parent directory of ipfs_kit_py to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'ipfs_kit_py')))

from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service
from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow

async def start_daemons():
    results = {}

    # Ensure ipfs_cluster_service is stopped and lock file is removed
    cluster_lock_path = os.path.expanduser("~/.ipfs-cluster/cluster.lock")
    try:
        # Attempt to stop any running ipfs-cluster-service processes
        subprocess.run(["pkill", "-f", "ipfs-cluster-service"], timeout=5, check=False)
        time.sleep(2) # Give it a moment to stop
        if os.path.exists(cluster_lock_path):
            os.remove(cluster_lock_path)
            print(f"Removed stale IPFS Cluster lock file: {cluster_lock_path}")
    except Exception as e:
        print(f"Error during pre-start cleanup for IPFS Cluster Service: {e}")

    # Start ipfs_cluster_service
    try:
        service_instance = ipfs_cluster_service()
        start_result = service_instance.ipfs_cluster_service_start()
        results['ipfs_cluster_service_start'] = start_result
    except Exception as e:
        results['ipfs_cluster_service_start'] = {'error': str(e), 'traceback': traceback.format_exc()}

    # Start ipfs_cluster_follow
    try:
        # ipfs_cluster_follow requires a cluster_name during initialization
        # Assuming a default cluster name or one can be passed
        follow_instance = ipfs_cluster_follow(metadata={'cluster_name': 'test_cluster'})
        
        # Initialize if not already initialized, capture detailed output
        init_result = follow_instance.ipfs_follow_init(cluster_name='test_cluster', bootstrap_peer='/ip4/127.0.0.1/tcp/9096/p2p/12D3KooWSipNgSzxfHJLBUVBwxih8yYzFzJ6e5WrrUVPbNRBgXXu') # Placeholder bootstrap peer
        if not init_result.get("success"):
            print(f"Warning: IPFS Cluster Follow initialization failed: {init_result.get("error", "Unknown error")}")
            if "command_result" in init_result and "stderr" in init_result["command_result"]:
                print(f"IPFS Cluster Follow Init Stderr: {init_result["command_result"]["stderr"]}")

        start_result = follow_instance.ipfs_follow_start(cluster_name='test_cluster')
        results['ipfs_cluster_follow_start'] = start_result
    except Exception as e:
        results['ipfs_cluster_follow_start'] = {'error': str(e), 'traceback': traceback.format_exc()}
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(start_daemons())