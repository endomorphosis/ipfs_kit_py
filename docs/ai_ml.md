# AI/ML Integration

IPFS Kit provides several features specifically designed to support Machine Learning workflows, leveraging content-addressing for reproducibility, distribution, and efficient data handling.

## Overview

The core AI/ML components are found in `ipfs_kit_py/ai_ml_integration.py` and include:

-   **`ModelRegistry`**: Store, version, and retrieve ML models using IPFS CIDs.
-   **`DatasetManager`**: Manage datasets stored on IPFS, tracking versions and metadata.
-   **`IPFSDataLoader`**: High-performance data loader for PyTorch/TensorFlow using IPFS datasets. ([See Separate Docs](ipfs_dataloader.md))
-   **`LangchainIntegration` / `LlamaIndexIntegration`**: Tools to integrate IPFS content with popular LLM frameworks (details depend on implementation).
-   **`DistributedTraining`**: Utilities to coordinate distributed ML training tasks across an IPFS Kit cluster.

## Enabling AI/ML Features

Initialize `ipfs_kit` with `enable_ai_ml=True` in the metadata:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

kit = ipfs_kit(metadata={"enable_ai_ml": True})

# Access components (if initialization was successful)
if hasattr(kit, 'model_registry'):
    print("Model Registry is available.")
if hasattr(kit, 'dataset_manager'):
    print("Dataset Manager is available.")
if hasattr(kit, 'langchain_integration'):
    print("Langchain Integration is available.")
# etc.
```

## Model Registry

Store and manage ML models using content-addressing.

```python
# Assuming 'kit' is initialized with AI/ML enabled

# --- Storing a Model ---
model_path = "path/to/your/model.pth" # Or .h5, .pb, etc.
model_metadata = {
    "name": "ResNet50-ImageNet",
    "version": "1.2",
    "framework": "PyTorch",
    "accuracy": 0.76,
    "tags": ["image_classification", "resnet"]
}

try:
    store_result = kit.model_registry.add_model(
        model_path=model_path,
        metadata=model_metadata
    )
    if store_result.get("success"):
        model_cid = store_result.get("cid")
        print(f"Stored model '{model_metadata['name']}' v{model_metadata['version']} with CID: {model_cid}")
    else:
        print(f"Failed to store model: {store_result.get('error')}")

    # --- Retrieving a Model ---
    # Retrieve by CID
    get_result = kit.model_registry.get_model(model_cid)
    if get_result.get("success"):
        retrieved_path = get_result.get("local_path")
        retrieved_metadata = get_result.get("metadata")
        print(f"Retrieved model to: {retrieved_path}")
        print(f"Metadata: {retrieved_metadata}")
        # Now load the model using its framework, e.g., torch.load(retrieved_path)
    else:
        print(f"Failed to retrieve model {model_cid}: {get_result.get('error')}")

    # --- Listing Models ---
    list_result = kit.model_registry.list_models(framework="PyTorch", tags=["image_classification"])
    if list_result.get("success"):
        print("\nPyTorch Image Classification Models:")
        for model_info in list_result.get("models", []):
            print(f"- {model_info.get('name')} (v{model_info.get('version')}, CID: {model_info.get('cid')})")

except AttributeError:
    print("Model Registry component not available.")
except Exception as e:
    print(f"An error occurred: {e}")
```

## Dataset Manager

Manage datasets stored on IPFS.

```python
# Assuming 'kit' is initialized with AI/ML enabled

# --- Storing a Dataset ---
# (Dataset creation might involve adding individual samples or a manifest file first)
dataset_cid = "QmYourDatasetManifestCID" # CID of the dataset manifest/structure
dataset_metadata = {
    "name": "MyImageDataset",
    "description": "Dataset for image classification task.",
    "version": "2.0",
    "tags": ["images", "classification", "augmented"],
    "size": 15000 # Number of samples
}

try:
    add_result = kit.dataset_manager.add_dataset(
        dataset_cid=dataset_cid,
        metadata=dataset_metadata
    )
    if add_result.get("success"):
        print(f"Registered dataset '{dataset_metadata['name']}' v{dataset_metadata['version']}")
    else:
        print(f"Failed to register dataset: {add_result.get('error')}")

    # --- Retrieving Dataset Info ---
    get_result = kit.dataset_manager.get_dataset(dataset_cid)
    if get_result.get("success"):
        retrieved_metadata = get_result.get("metadata")
        print(f"\nDataset Info for {dataset_cid}:")
        print(retrieved_metadata)
    else:
        print(f"Failed to get dataset info for {dataset_cid}: {get_result.get('error')}")

    # --- Listing Datasets ---
    list_result = kit.dataset_manager.list_datasets(tags=["images"])
    if list_result.get("success"):
        print("\nImage Datasets:")
        for ds_info in list_result.get("datasets", []):
            print(f"- {ds_info.get('name')} (v{ds_info.get('version')}, CID: {ds_info.get('cid')})")

except AttributeError:
    print("Dataset Manager component not available.")
except Exception as e:
    print(f"An error occurred: {e}")

```

## IPFS Data Loader

Provides an efficient way to load data from IPFS datasets for training. See the dedicated documentation for details: [IPFS DataLoader Docs](ipfs_dataloader.md).

## Langchain / LlamaIndex Integration

These components provide tools to bridge IPFS content with Large Language Model (LLM) frameworks. Common functionalities might include:

-   Creating vector stores from documents stored on IPFS.
-   Loading documents directly from IPFS CIDs.
-   Using IPFS as a storage backend for indexes or chat history.

*Note: The specific methods depend heavily on the implementation in `ai_ml_integration.py`. Check the module's docstrings or source code for available functions.*

```python
# Conceptual Example (check actual implementation for methods)

# Assuming 'kit' is initialized with AI/ML enabled

# --- Langchain Example ---
try:
    if hasattr(kit, 'langchain_integration'):
        # Check if Langchain is installed
        if kit.langchain_integration.langchain_check_availability().get("available"):
            # Create a document loader for an IPFS directory
            # loader = kit.langchain_integration.langchain_create_document_loader(
            #     cid="QmDirectoryCID", loader_type="IPFSDirectory"
            # )
            # docs = loader.load()

            # Create a vector store using IPFS content
            # vectorstore = kit.langchain_integration.langchain_create_vectorstore(
            #     documents=docs, embedding_function=my_embeddings, store_type="faiss_ipfs"
            # )
            pass # Placeholder for actual usage
    else:
        print("Langchain Integration not available.")

except AttributeError:
    print("Langchain Integration component not available.")
except Exception as e:
    print(f"An error occurred with Langchain integration: {e}")


# --- LlamaIndex Example ---
try:
    if hasattr(kit, 'llama_index_integration'):
         # Check if LlamaIndex is installed
        if kit.llama_index_integration.llamaindex_check_availability().get("available"):
            # Create a reader for an IPFS file
            # reader = kit.llama_index_integration.llamaindex_create_document_reader(
            #     cid="QmFileCID", reader_type="IPFSFile"
            # )
            # documents = reader.load_data()

            # Create storage context potentially using IPFS
            # storage_context = kit.llama_index_integration.llamaindex_create_storage_context(
            #     persist_dir="ipfs://QmIndexStorageCID" # Conceptual path
            # )
            pass # Placeholder for actual usage
    else:
        print("LlamaIndex Integration not available.")

except AttributeError:
    print("LlamaIndex Integration component not available.")
except Exception as e:
    print(f"An error occurred with LlamaIndex integration: {e}")
```

## Distributed Training

Coordinate training tasks across an IPFS Kit cluster. This typically involves the `ClusterManager` for task submission and worker nodes executing the training.

```python
# --- Master Node ---
# Assuming 'kit_master' is initialized with role='master' and cluster management enabled

training_payload = {
    "model_cid": "QmBaseModelCID",
    "dataset_cid": "QmTrainingDataCID",
    "hyperparameters": {"epochs": 3, "learning_rate": 0.01},
    "output_prefix": "trained_model_split"
}

try:
    if hasattr(kit_master, 'distributed_training'):
        # Prepare task (might split data or config)
        prep_result = kit_master.distributed_training.prepare_distributed_task(
            task_type="pytorch_training",
            payload=training_payload,
            num_workers=2 # Example: split for 2 workers
        )

        if prep_result.get("success"):
            # Submit individual tasks to the cluster manager
            for subtask_payload in prep_result.get("subtasks", []):
                 submit_result = kit_master.submit_cluster_task(
                     task_type="pytorch_training_worker", # Specific worker task type
                     payload=subtask_payload
                 )
                 # Track submitted task IDs...
        else:
            print(f"Failed to prepare distributed task: {prep_result.get('error')}")

        # Later... aggregate results (conceptual)
        # completed_task_ids = [...]
        # aggregate_result = kit_master.distributed_training.aggregate_training_results(
        #     original_task_id=prep_result.get("original_task_id"),
        #     completed_subtask_ids=completed_task_ids
        # )
        # final_model_cid = aggregate_result.get("final_model_cid")

except AttributeError:
    print("Distributed Training component not available.")
except Exception as e:
    print(f"An error occurred during distributed training setup: {e}")


# --- Worker Node ---
# Workers would need a registered task handler for "pytorch_training_worker"
# This handler would use the payload (e.g., data split CID, model CID, hypers)
# to load data via IPFSDataLoader, train a partial model, and store the result back to IPFS.
```

This integration allows leveraging the distributed nature of IPFS and the cluster management features for large-scale ML tasks.
