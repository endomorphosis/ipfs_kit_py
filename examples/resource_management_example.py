import time
import os
import tempfile
import logging
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Configure logging for visibility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Example configuration enabling and customizing resource management
# These thresholds are examples; adjust based on your system and expected load
config = {
    'resource_management': {
        'enabled': True,
        'monitor_interval_seconds': 5, # Check resources every 5 seconds (more frequent for demo)
        'cpu_threshold_high': 75.0,
        'memory_threshold_high': 80.0,
        'disk_threshold_high': 90.0,
        'adaptive_thread_pool': {
            'min_threads': 1,
            'max_threads_factor': 1.0, # Limit threads for demo stability
            'target_queue_latency_ms': 200,
            'adjustment_interval_seconds': 10 # Adjust pool size faster for demo
        },
        'adaptive_cache': {
            'target_memory_usage_factor': 0.5, # Use up to 50% of available memory
            'min_cache_size_mb': 50
        }
    },
    # Add other necessary configurations for IPFS connection if needed
    # 'ipfs': { ... }
}

def main():
    logging.info("Initializing IPFSSimpleAPI with Resource Management enabled.")
    # Ensure IPFS daemon is running or configure API endpoint if needed
    try:
        kit = IPFSSimpleAPI(config=config)
        logging.info("IPFSSimpleAPI initialized.")

        # Resource management runs in the background.
        # The ResourceMonitor will periodically check system stats.
        # The AdaptiveThreadPool and ResourceAdapter will adjust behavior based on monitor feedback.

        # To demonstrate, let's perform some operations that might stress resources
        # (Note: Actual resource stress depends heavily on system specs and IPFS state)

        logging.info("Performing some IPFS operations...")
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".txt") as tmpfile:
                tmpfile.write("This is test content for resource management example.\n" * 1024 * 10) # ~1MB
                temp_file_path = tmpfile.name

            logging.info(f"Adding file {temp_file_path}...")
            add_result = kit.add(temp_file_path)
            cid = add_result.get('Hash') if isinstance(add_result, dict) else None
            logging.info(f"Add result: {add_result}")

            if cid:
                logging.info(f"Getting file {cid} multiple times...")
                for i in range(5):
                    logging.info(f"Attempt {i+1} to get {cid}")
                    content = kit.cat(cid)
                    logging.info(f"Got content of length: {len(content) if content else 0}")
                    time.sleep(1) # Small delay between gets

            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logging.info(f"Removed temporary file: {temp_file_path}")

        except Exception as e:
            logging.error(f"An error occurred during IPFS operations: {e}")

        # Keep the script running for a bit to observe background monitoring (check logs)
        logging.info("Resource management continues in the background.")
        logging.info("Observe logs for potential resource monitoring messages (if configured).")
        logging.info("Stopping in 15 seconds...")
        time.sleep(15)

    except Exception as e:
        logging.error(f"Failed to initialize IPFSSimpleAPI: {e}")
        logging.error("Ensure the IPFS daemon is running or the API is configured correctly.")

    finally:
        # Although not strictly necessary for this example, good practice:
        # if 'kit' in locals() and hasattr(kit, 'stop'): # Assuming a stop method exists
        #     kit.stop()
        logging.info("Example finished.")

if __name__ == "__main__":
    main()
