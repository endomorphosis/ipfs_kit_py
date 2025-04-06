import logging
import time
import os
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# Assumes cluster and distributed training are enabled and configured
# on the node running this script (acting as the coordinator/submitter).
config = {
    'ai_ml': {
        'distributed_training': {
            'enabled': True,
            # Add other necessary configs like pubsub topics if not default
        },
        # Model/Dataset registry config might be needed if not default
        'model_registry': {
             'base_path': os.path.expanduser("~/.ipfs_kit/ai_ml/models")
        },
        'dataset_manager': {
             'base_path': os.path.expanduser("~/.ipfs_kit/ai_ml/datasets")
        }
    },
    'cluster': {
        'enabled': True,
        'role': 'Master', # This node needs coordinator privileges
        # Add necessary cluster connection/bootstrap info
    },
    # Add IPFS connection details if needed
    # 'ipfs': { ... }
}

# --- Dummy Data Placeholders ---
# In a real scenario, these would be CIDs of models/datasets already added
# using kit.ai_model_add() or kit.ai_dataset_add()
DUMMY_MODEL_CID = "QmModelCIDPlaceholder"
DUMMY_DATASET_CID = "QmDatasetCIDPlaceholder"

def main():
    logging.info("Initializing IPFSSimpleAPI with Distributed Training enabled.")
    try:
        # Ensure the node running this script is configured as Master/Coordinator
        kit = IPFSSimpleAPI(config=config)
        logging.info("IPFSSimpleAPI initialized.")

        # --- Define Training Task Configuration ---
        # This structure depends on what the DistributedTraining class expects.
        # It typically includes framework, hyperparameters, model/data refs.
        training_task_config = {
            'task_name': 'example_dist_train_job',
            'framework': 'tensorflow', # or 'pytorch'
            'model_cid': DUMMY_MODEL_CID,
            'dataset_cid': DUMMY_DATASET_CID,
            'hyperparameters': {
                'learning_rate': 0.001,
                'batch_size': 64,
                'epochs': 5,
                # Add framework-specific parameters
            },
            'sync_strategy': config.get('ai_ml', {}).get('distributed_training', {}).get('sync_strategy', 'parameter_server'),
            'num_workers_required': 2 # Example: require at least 2 workers
            # Add other necessary fields like output config, validation split, etc.
        }
        logging.info(f"Prepared training task configuration: {training_task_config}")

        # --- Submit Training Job ---
        logging.info("Submitting distributed training job...")
        try:
            submission_result = kit.ai_distributed_training_submit_job(
                task_config=training_task_config
            )
            logging.info(f"Job submission result: {submission_result}")

            if submission_result and submission_result.get('success'):
                task_id = submission_result.get('task_id')
                if task_id:
                    logging.info(f"Training job submitted successfully. Task ID: {task_id}")

                    # --- Check Job Status Periodically ---
                    max_wait_time = 300 # 5 minutes
                    check_interval = 30 # seconds
                    start_time = time.time()
                    final_status = None

                    while time.time() - start_time < max_wait_time:
                        logging.info(f"Checking status for task {task_id}...")
                        status_result = kit.ai_distributed_training_get_status(task_id=task_id)
                        logging.info(f"Status result: {status_result}")

                        if status_result and status_result.get('success'):
                            current_status = status_result.get('status')
                            final_status = current_status # Keep track of the last known status
                            if current_status in ['Completed', 'Failed', 'Cancelled']:
                                logging.info(f"Training job reached final state: {current_status}")
                                break
                            else:
                                logging.info(f"Job status: {current_status}. Waiting {check_interval}s...")
                                time.sleep(check_interval)
                        else:
                            logging.error("Failed to retrieve job status.")
                            time.sleep(check_interval) # Still wait before retrying

                    if final_status not in ['Completed', 'Failed', 'Cancelled']:
                         logging.warning(f"Job did not reach final state within {max_wait_time}s. Last known status: {final_status}")

                    # --- (Optional) Aggregate Results ---
                    # If the job completed successfully, you might aggregate results
                    if final_status == 'Completed':
                         logging.info(f"Attempting to aggregate results for task {task_id}...")
                         aggregation_result = kit.ai_distributed_training_aggregate_results(task_id=task_id)
                         logging.info(f"Aggregation result: {aggregation_result}")
                         if aggregation_result and aggregation_result.get('success'):
                              final_model_cid = aggregation_result.get('final_model_cid')
                              metrics = aggregation_result.get('metrics')
                              logging.info(f"Final Model CID: {final_model_cid}")
                              logging.info(f"Final Metrics: {metrics}")

                else:
                    logging.error("Submission succeeded but no Task ID returned.")
            else:
                logging.error(f"Job submission failed: {submission_result.get('error', 'Unknown error')}")

        except Exception as e:
            logging.error(f"An error occurred during job submission or status check: {e}", exc_info=True)

    except Exception as e:
        logging.error(f"Failed to initialize IPFSSimpleAPI: {e}")
        logging.error("Ensure the cluster, AI/ML features, and IPFS are configured correctly.")

    finally:
        logging.info("Distributed training example finished.")

if __name__ == "__main__":
    # Note: This example requires a running cluster with configured workers
    # capable of handling the specified framework and potentially having
    # the dummy model/dataset CIDs replaced with actual ones.
    main()
