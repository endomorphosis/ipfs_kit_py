# AI/ML Distributed Training

`ipfs-kit-py` provides capabilities for coordinating and executing distributed machine learning training tasks across multiple nodes in a cluster. This allows leveraging the combined computational resources (CPU, GPU) of worker nodes for training larger models or accelerating the training process. The core logic is handled by the `DistributedTraining` class within `ai_ml_integration.py`.

## Overview

The distributed training system facilitates tasks like data parallelism or potentially model parallelism (depending on the specific implementation details and framework support) using IPFS for data/model distribution and libp2p/cluster mechanisms for coordination.

**Key Concepts:**

*   **Coordinator Node**: Typically the Master node in the cluster, responsible for:
    *   Defining the training task (model architecture, dataset, hyperparameters).
    *   Discovering available Worker nodes.
    *   Distributing the task configuration, model weights, and data shards to Workers.
    *   Coordinating training rounds (e.g., synchronizing gradients/parameter updates).
    *   Aggregating results (e.g., averaging gradients, selecting best model).
    *   Monitoring worker status and handling failures.
*   **Worker Nodes**: Nodes in the cluster (typically with specific capabilities like GPUs) responsible for:
    *   Registering themselves as available for training tasks.
    *   Receiving task configurations, models, and data from the Coordinator.
    *   Performing local training computations on their assigned data portion.
    *   Sending results (gradients, updated weights, metrics) back to the Coordinator.
    *   Sending heartbeats to indicate liveness.
*   **Task Configuration**: A definition of the training job, including model CID/path, dataset CID/path, training framework (TensorFlow, PyTorch), hyperparameters (learning rate, batch size, epochs), synchronization strategy, etc. Stored potentially as an object on IPFS.
*   **Synchronization**: Mechanism for coordinating updates between workers. Common strategies include:
    *   **Parameter Server**: Workers send gradients to a central server (or the Coordinator) which aggregates them and sends back updated parameters.
    *   **All-Reduce**: Workers exchange gradients directly with each other to compute the average update (often more efficient but requires direct peer communication). The implementation details in `DistributedTraining` would clarify the exact method used.
*   **Data Distribution**: Datasets stored on IPFS are accessed by workers, potentially using the `IPFSDataLoader` for efficient sharding and loading.
*   **Model Distribution**: The initial model is distributed via IPFS, and the final trained model is often stored back on IPFS.

## Implementation (`DistributedTraining`)

The `DistributedTraining` class likely manages:

*   **Task Preparation**: `prepare_distributed_task` - Creates the task configuration object and stores it (e.g., on IPFS).
*   **Coordinator Logic**: `run_distributed_training`, `_start_coordination`, `_coordinate_training`, `_aggregate_parameters`, `_publish_global_model`, `_handle_worker_failure`. Handles the lifecycle of a training job from the coordinator's perspective.
*   **Worker Logic**: `start_worker`, `stop_worker`, `_worker_heartbeat_loop`, `_handle_task_announcement`, `execute_training_task`. Manages the worker's participation in training.
*   **Communication**: Uses the cluster's communication layer (PubSub, RPC) to exchange task announcements, status updates, parameters, and heartbeats.
*   **Framework Integration**: Interacts with specific ML frameworks (TF, PyTorch) to execute the actual training steps (`_execute_training`).

## Configuration

Distributed training settings might be part of the main AI/ML or cluster configuration:

```python
# Example configuration snippet
config = {
    'ai_ml': {
        'distributed_training': {
            'enabled': True,
            'coordinator_role': 'Master', # Role responsible for coordination
            'worker_capability': 'gpu', # Workers must have this capability (optional)
            'sync_strategy': 'parameter_server', # or 'all_reduce' (implementation dependent)
            'pubsub_topic_prefix': '/ipfs-kit/dist-train/',
            'heartbeat_interval_seconds': 30,
            'task_timeout_seconds': 3600 # Timeout for individual worker tasks
        }
        # ... other ai_ml config
    },
    'cluster': {
        # Cluster needs to be enabled and configured
        'enabled': True,
        # ...
    }
    # ... other ipfs-kit-py config
}
```

## Usage Workflow

1.  **Define Task**: User defines the model, dataset, and training parameters.
2.  **Submit Job**: User calls a method like `kit.ai_distributed_training_submit_job(...)` on the coordinator node, providing the task definition.
3.  **Preparation**: The `DistributedTraining` coordinator prepares the task configuration (potentially uploading it to IPFS).
4.  **Worker Discovery**: Coordinator identifies suitable, available worker nodes based on configuration (e.g., capability checks).
5.  **Task Announcement**: Coordinator announces the task via the communication channel (e.g., PubSub).
6.  **Worker Acceptance**: Available workers receive the announcement, download the task config, model, and relevant data shards from IPFS.
7.  **Training Loop**:
    *   Workers perform local training iterations.
    *   Workers send updates (gradients/weights) according to the `sync_strategy`.
    *   Coordinator aggregates updates and sends back new global parameters (if Parameter Server strategy).
    *   Workers update their local models.
    *   Repeat for configured epochs/steps.
8.  **Completion**: Coordinator detects training completion (e.g., epochs reached, convergence criteria met).
9.  **Result Aggregation**: Coordinator aggregates final metrics and potentially selects the best model.
10. **Store Final Model**: The final trained model is saved (e.g., to IPFS via `ModelRegistry`).
11. **Status Check**: User can query the status of the job using `kit.ai_distributed_training_get_status(...)`.

## Benefits

*   **Scalability**: Train models that don't fit on a single machine's memory or require excessive time.
*   **Acceleration**: Reduce training time by parallelizing computation across multiple nodes/GPUs.
*   **Resource Utilization**: Leverage idle resources within the cluster.

## Considerations

*   **Communication Overhead**: Synchronization between workers introduces network latency and overhead. Efficiency depends heavily on the `sync_strategy` and network bandwidth.
*   **Fault Tolerance**: Handling worker failures gracefully (e.g., reassigning work, adjusting aggregation) is complex but crucial. The implementation details of `_handle_worker_failure` are important here.
*   **Framework Compatibility**: Requires tight integration with the specific ML framework being used (TensorFlow, PyTorch).
*   **Data Sharding**: Efficiently splitting and distributing the dataset to workers is key. `IPFSDataLoader` likely plays a role here.
*   **Debugging**: Debugging distributed applications is significantly harder than single-node applications.
