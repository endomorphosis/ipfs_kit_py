
import sys
import os
import json

# Add the parent directory of ipfs_kit_py to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'ipfs_kit_py')))

from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service
from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow

def run_tests():
    results = {}

    # Test ipfs_cluster_service
    try:
        service_instance = ipfs_cluster_service()
        service_test_result = service_instance.test()
        results['ipfs_cluster_service'] = service_test_result
    except Exception as e:
        results['ipfs_cluster_service'] = {'error': str(e), 'traceback': traceback.format_exc()}

    # Test ipfs_cluster_follow
    try:
        # ipfs_cluster_follow requires a cluster_name during initialization
        follow_instance = ipfs_cluster_follow(metadata={'cluster_name': 'test_cluster'})
        follow_test_result = follow_instance.ipfs_cluster_follow_status() # Using status to check if binary is found
        results['ipfs_cluster_follow'] = follow_test_result
    except Exception as e:
        results['ipfs_cluster_follow'] = {'error': str(e), 'traceback': traceback.format_exc()}
    
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    import traceback
    run_tests()
