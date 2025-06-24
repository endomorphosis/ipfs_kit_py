"""
High-Level API Example for AI/ML Integration with IPFS Kit.

This example demonstrates the usage of the High-Level API for AI/ML integration with IPFS Kit,
including data loading, Langchain/LlamaIndex integration, distributed training, and model deployment.

IMPORTANT:
- This example runs in simulation mode if IPFS daemon is not running.
- Full functionality requires optional dependencies: langchain, llama-index, torch, etc.
- See README_AI_ML.md for detailed installation instructions.
"""

import os
import sys
import json
import time
import uuid
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the High-Level API
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def dataset_workflow():
    """Demonstrate dataset management workflow."""
    logger.info("=== Dataset Management Workflow ===")

    # Initialize API
    api = IPFSSimpleAPI()

    # Create a sample dataset
    logger.info("Creating sample dataset")
    df = pd.DataFrame({
        'feature1': np.random.rand(100),
        'feature2': np.random.rand(100),
        'feature3': np.random.rand(100),
        'target': np.random.randint(0, 2, 100)
    })

    # Save dataset to CSV
    dataset_path = "example_dataset.csv"
    df.to_csv(dataset_path, index=False)

    try:
        # Add dataset to IPFS
        logger.info("Adding dataset to IPFS")
        dataset_result = api.add(dataset_path)

        if not dataset_result.get("success", False):
            # Simulated CID for demo purposes when IPFS is not available
            logger.warning("Failed to add dataset to IPFS, using simulated CID")
            dataset_cid = f"Qm{os.urandom(16).hex()}"
        else:
            dataset_cid = dataset_result.get("cid", f"Qm{os.urandom(16).hex()}")

        logger.info(f"Dataset CID: {dataset_cid}")

        # Create dataset metadata
        metadata = {
            "name": "Example Classification Dataset",
            "description": "A simple dataset for binary classification",
            "features": ["feature1", "feature2", "feature3"],
            "target": "target",
            "rows": 100,
            "columns": 4,
            "created_at": time.time()
        }

        # Register dataset with metadata (using generic add_json for simulation)
        logger.info("Registering dataset with metadata")
        try:
            # In a real implementation, this would use api.ai_register_dataset
            # For now, we'll simulate it using add_json
            metadata["dataset_cid"] = dataset_cid
            register_result = api.add_json(metadata)
            logger.info(f"Dataset metadata added with result: {register_result}")
        except Exception as e:
            logger.warning(f"Failed to register dataset with metadata: {e}")
            register_result = {
                "success": False,
                "error": str(e),
                "simulated_result": {
                    "success": True,
                    "cid": f"Qm{os.urandom(16).hex()}",
                    "dataset_cid": dataset_cid
                }
            }
            logger.info("Using simulated registration result")

        # Create data loader (simulation)
        logger.info("Creating data loader for dataset")
        try:
            # In a real implementation, this would use api.ai_data_loader
            # For now, we'll simulate it
            loader_result = {
                "success": True,
                "dataset_cid": dataset_cid,
                "batch_size": 16,
                "shuffle": True,
                "loader": f"Simulated data loader for {dataset_cid}"
            }
            logger.info(f"Data loader created: {loader_result.get('success', False)}")
        except Exception as e:
            logger.warning(f"Failed to create data loader: {e}")
            loader_result = {"success": False, "error": str(e)}

        # If a framework is available, demonstrate conversion
        try:
            import torch
            logger.info("Creating PyTorch data loader")
            try:
                torch_loader_result = api.ai_data_loader(
                    dataset_cid,
                    batch_size=16,
                    shuffle=True,
                    framework="pytorch"
                )
                logger.info(f"PyTorch data loader created: {torch_loader_result.get('success', False)}")
            except Exception as e:
                logger.warning(f"Failed to create PyTorch data loader: {e}")
        except ImportError:
            logger.info("PyTorch not available, skipping PyTorch data loader example")

    finally:
        # Clean up test file
        if os.path.exists(dataset_path):
            os.remove(dataset_path)


def model_registry_workflow():
    """Demonstrate model registry workflow."""
    logger.info("=== Model Registry Workflow ===")

    # Initialize API
    api = IPFSSimpleAPI()

    # Create a sample model (we'll use a simple dictionary as a placeholder)
    model = {
        "model_type": "random_forest",
        "hyperparameters": {
            "n_estimators": 100,
            "max_depth": 5,
            "min_samples_split": 2
        },
        "weights": [0.1, 0.2, 0.3, 0.4, 0.5]  # Simplified representation
    }

    # Save model to JSON
    model_path = "example_model.json"
    with open(model_path, 'w') as f:
        json.dump(model, f)

    try:
        # Add model to IPFS
        logger.info("Adding model to IPFS")
        model_result = api.add(model_path)

        if not model_result.get("success", False):
            # Simulated CID for demo purposes when IPFS is not available
            logger.warning("Failed to add model to IPFS, using simulated CID")
            model_cid = f"Qm{os.urandom(16).hex()}"
        else:
            model_cid = model_result.get("cid", f"Qm{os.urandom(16).hex()}")

        logger.info(f"Model CID: {model_cid}")

        # Register model with metadata
        metadata = {
            "name": "Example Classification Model",
            "version": "1.0.0",
            "model_type": "random_forest",
            "framework": "scikit-learn",
            "metrics": {
                "accuracy": 0.85,
                "f1_score": 0.83,
                "precision": 0.84,
                "recall": 0.82
            },
            "created_at": time.time(),
            "model_cid": model_cid  # Include the model CID in metadata
        }

        logger.info("Registering model with metadata")
        try:
            # Try to use the AI-specific method first
            register_result = api.ai_register_model(model_cid, metadata)
            logger.info(f"Model registration result: {register_result}")
        except Exception as e:
            logger.warning(f"Failed to register model with specialized method: {e}")
            # Fall back to generic add_json method for simulation
            try:
                register_result = api.add_json(metadata)
                logger.info(f"Model metadata added with result: {register_result}")
            except Exception as e2:
                logger.warning(f"Failed to register model with generic method: {e2}")
                register_result = {
                    "success": False,
                    "error": str(e2),
                    "simulated_result": {
                        "success": True,
                        "cid": f"Qm{os.urandom(16).hex()}",
                        "model_cid": model_cid
                    }
                }
                logger.info("Using simulated registration result")

        # List models in registry
        logger.info("Listing models in registry")
        try:
            models_result = api.ai_list_models()
            logger.info(f"Models in registry: {models_result}")
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            # Simulate a response with the model we just registered
            models_result = {
                "success": True,
                "models": [
                    {
                        "name": metadata["name"],
                        "version": metadata["version"],
                        "cid": model_cid,
                        "framework": metadata["framework"],
                        "created_at": metadata["created_at"]
                    }
                ],
                "count": 1
            }
            logger.info(f"Using simulated models list: {models_result}")

        # Benchmark model
        logger.info("Benchmarking model")
        try:
            benchmark_result = api.ai_benchmark_model(
                model_cid,
                dataset_cid="QmExampleDatasetCID",  # In a real example, this would be a real CID
                metrics=["accuracy", "f1_score", "latency"]
            )
            logger.info(f"Benchmark result: {benchmark_result}")
        except Exception as e:
            logger.warning(f"Failed to benchmark model: {e}")
            # Create a realistic simulated benchmark result
            benchmark_result = {
                "success": True,
                "model_cid": model_cid,
                "dataset_cid": "QmExampleDatasetCID",
                "metrics": {
                    "accuracy": 0.85,
                    "f1_score": 0.83,
                    "latency_ms": 120
                },
                "benchmark_id": f"bench-{os.urandom(4).hex()}",
                "completed_at": time.time()
            }
            logger.info(f"Using simulated benchmark result: {benchmark_result}")

        # Deploy model
        logger.info("Deploying model")
        try:
            deploy_result = api.ai_deploy_model(
                model_cid,
                endpoint_type="rest",
                resources={"cpu": 1, "memory": "2GB"}
            )
            logger.info(f"Deployment result: {deploy_result}")
        except Exception as e:
            logger.warning(f"Failed to deploy model: {e}")
            # Create a realistic simulated deployment result
            import uuid
            deploy_result = {
                "success": True,
                "model_cid": model_cid,
                "endpoint_id": f"endpoint-{uuid.uuid4()}",
                "endpoint_type": "rest",
                "status": "deploying",
                "url": f"https://api.example.com/models/{model_cid}",
                "created_at": time.time(),
                "estimated_ready_time": time.time() + 60  # Ready in 60 seconds
            }
            logger.info(f"Using simulated deployment result: {deploy_result}")

        # Optimize model
        logger.info("Optimizing model")
        try:
            optimize_result = api.ai_optimize_model(
                model_cid,
                target_platform="cpu",
                optimization_level="O2"
            )
            logger.info(f"Optimization result: {optimize_result}")
        except Exception as e:
            logger.warning(f"Failed to optimize model: {e}")
            # Create a realistic simulated optimization result
            optimize_result = {
                "success": True,
                "original_cid": model_cid,
                "optimized_cid": f"Qm{os.urandom(16).hex()}",
                "target_platform": "cpu",
                "optimization_level": "O2",
                "metrics": {
                    "size_reduction": "45%",
                    "latency_improvement": "30%",
                    "original_size_bytes": 2458000,
                    "optimized_size_bytes": 1351900
                },
                "completed_at": time.time()
            }
            logger.info(f"Using simulated optimization result: {optimize_result}")

    finally:
        # Clean up test file
        if os.path.exists(model_path):
            os.remove(model_path)


def langchain_workflow():
    """Demonstrate Langchain integration workflow."""
    logger.info("=== Langchain Integration Workflow ===")

    # Initialize API
    api = IPFSSimpleAPI()

    # Check if langchain is available
    try:
        import langchain
        logger.info("Langchain is available")
        langchain_available = True
    except ImportError:
        logger.info("Langchain not available, will use simulation mode")
        langchain_available = False

    # Create sample documents
    docs_dir = "example_docs"
    os.makedirs(docs_dir, exist_ok=True)

    try:
        # Create a few sample text files
        for i in range(3):
            with open(f"{docs_dir}/document_{i}.txt", 'w') as f:
                f.write(f"This is sample document {i} for testing Langchain integration with IPFS Kit.\n")
                f.write(f"It contains information about topic {i} that can be retrieved using LLMs.\n")
                f.write(f"This document discusses various aspects of machine learning and IPFS integration.\n")

        # Add documents to IPFS
        logger.info("Adding documents to IPFS")
        try:
            # Use -r flag for directories via subprocess to avoid API limitations
            import subprocess
            cmd = ["ipfs", "add", "-Q", "-r", "--cid-version=1", docs_dir]
            p = subprocess.run(cmd, capture_output=True, text=True)

            if p.returncode == 0:
                docs_cid = p.stdout.strip()
                docs_result = {"success": True, "cid": docs_cid}
            else:
                # Fall back to standard API with recursive flag if available
                try:
                    docs_result = api.add(docs_dir, recursive=True)
                    if not docs_result.get("success", False):
                        logger.warning("Failed to add documents to IPFS, using simulated CID")
                        docs_cid = f"Qm{os.urandom(16).hex()}"
                    else:
                        docs_cid = docs_result.get("cid", f"Qm{os.urandom(16).hex()}")
                except Exception as e2:
                    logger.warning(f"Error adding documents with API fallback: {e2}")
                    docs_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID
        except Exception as e:
            logger.warning(f"Error adding documents to IPFS: {e}")
            docs_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID

        logger.info(f"Documents added with CID: {docs_cid}")

        # Load documents with Langchain
        logger.info("Loading documents with Langchain")
        try:
            load_result = api.ai_langchain_load_documents(
                docs_cid,
                recursive=True,
                filter_pattern="*.txt"
            )
            logger.info(f"Documents loaded: {load_result.get('success', False)}")
        except Exception as e:
            logger.warning(f"Failed to load documents with Langchain: {e}")
            # Create simulated result
            load_result = {
                "success": True,
                "documents": [
                    {
                        "id": f"doc-{i}",
                        "content": f"This is sample document {i} for testing Langchain integration with IPFS Kit.\n"
                                   f"It contains information about topic {i} that can be retrieved using LLMs.\n"
                                   f"This document discusses various aspects of machine learning and IPFS integration.\n",
                        "metadata": {
                            "source": f"{docs_dir}/document_{i}.txt",
                            "cid": docs_cid,
                            "path": f"{docs_cid}/document_{i}.txt"
                        }
                    } for i in range(3)
                ],
                "count": 3
            }
            logger.info(f"Using simulated document loading result with {len(load_result['documents'])} documents")

        # Create vector store from loaded documents
        if load_result.get('success', False) and 'documents' in load_result:
            logger.info("Creating vector store")
            try:
                vectorstore_result = api.ai_langchain_create_vectorstore(
                    load_result['documents'],
                    embedding_model="fake-embeddings" if not langchain_available else "local:sentence-transformers/all-MiniLM-L6-v2",
                    vector_store_type="faiss"
                )
                logger.info(f"Vector store created: {vectorstore_result.get('success', False)}")
            except Exception as e:
                logger.warning(f"Failed to create vector store: {e}")
                # Create simulated result
                vectorstore_result = {
                    "success": True,
                    "vector_store_type": "faiss",
                    "embedding_dimensions": 384,
                    "document_count": len(load_result['documents']),
                    "vector_store": "Simulated FAISS vector store"
                }
                logger.info("Using simulated vector store result")

            # Store vector index in IPFS (create mock file for simulation)
            index_path = "vector_index.faiss"
            with open(index_path, 'wb') as f:
                f.write(b"MOCK FAISS INDEX")  # Mock data for demo purposes

            logger.info("Adding vector index to IPFS")
            try:
                index_result = api.add(index_path)
                if not index_result.get("success", False):
                    logger.warning("Failed to add vector index to IPFS, using simulated CID")
                    index_cid = f"Qm{os.urandom(16).hex()}"
                else:
                    index_cid = index_result.get("cid", f"Qm{os.urandom(16).hex()}")
            except Exception as e:
                logger.warning(f"Error adding vector index to IPFS: {e}")
                index_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID

            logger.info(f"Vector index added with CID: {index_cid}")

            # Demonstrate a query (simulated)
            logger.info("Performing vector similarity search")
            try:
                search_result = api.ai_langchain_query(
                    vectorstore_cid=index_cid,
                    query="What is machine learning?",
                    top_k=2
                )
                logger.info(f"Search result: {search_result}")
            except Exception as e:
                logger.warning(f"Failed to perform vector search: {e}")
                # Create simulated result
                search_result = {
                    "success": True,
                    "query": "What is machine learning?",
                    "results": [
                        {
                            "content": load_result["documents"][0]["content"],
                            "metadata": load_result["documents"][0]["metadata"],
                            "similarity": 0.87
                        },
                        {
                            "content": load_result["documents"][2]["content"],
                            "metadata": load_result["documents"][2]["metadata"],
                            "similarity": 0.76
                        }
                    ],
                    "count": 2
                }
                logger.info(f"Using simulated search result with {len(search_result['results'])} matches")

            # Clean up index file
            if os.path.exists(index_path):
                os.remove(index_path)

    finally:
        # Clean up test files
        import shutil
        if os.path.exists(docs_dir):
            shutil.rmtree(docs_dir)


def llama_index_workflow():
    """Demonstrate LlamaIndex integration workflow."""
    logger.info("=== LlamaIndex Integration Workflow ===")

    # Initialize API
    api = IPFSSimpleAPI()

    # Check if llama_index is available
    try:
        import llama_index
        logger.info("LlamaIndex is available")
        llama_index_available = True
    except ImportError:
        logger.info("LlamaIndex not available, will use simulation mode")
        llama_index_available = False

    # Create sample documents
    docs_dir = "example_llama_docs"
    os.makedirs(docs_dir, exist_ok=True)

    try:
        # Create a few sample text files
        for i in range(3):
            with open(f"{docs_dir}/llama_doc_{i}.txt", 'w') as f:
                f.write(f"This is sample document {i} for testing LlamaIndex integration with IPFS Kit.\n")
                f.write(f"It contains information about topic {i} that can be retrieved using LLMs.\n")
                f.write(f"This document discusses various aspects of machine learning and IPFS integration.\n")

        # Add documents to IPFS
        logger.info("Adding documents to IPFS")
        try:
            # Use -r flag for directories via subprocess to avoid API limitations
            import subprocess
            cmd = ["ipfs", "add", "-Q", "-r", "--cid-version=1", docs_dir]
            p = subprocess.run(cmd, capture_output=True, text=True)

            if p.returncode == 0:
                docs_cid = p.stdout.strip()
                docs_result = {"success": True, "cid": docs_cid}
            else:
                # Fall back to standard API with recursive flag if available
                try:
                    docs_result = api.add(docs_dir, recursive=True)
                    if not docs_result.get("success", False):
                        logger.warning("Failed to add documents to IPFS, using simulated CID")
                        docs_cid = f"Qm{os.urandom(16).hex()}"
                    else:
                        docs_cid = docs_result.get("cid", f"Qm{os.urandom(16).hex()}")
                except Exception as e2:
                    logger.warning(f"Error adding documents with API fallback: {e2}")
                    docs_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID
        except Exception as e:
            logger.warning(f"Error adding documents to IPFS: {e}")
            docs_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID

        logger.info(f"Documents added with CID: {docs_cid}")

        # Load documents with LlamaIndex
        logger.info("Loading documents with LlamaIndex")
        try:
            load_result = api.ai_llama_index_load_documents(
                docs_cid,
                recursive=True,
                filter_pattern="*.txt"
            )
            logger.info(f"Documents loaded: {load_result.get('success', False)}")
        except Exception as e:
            logger.warning(f"Failed to load documents with LlamaIndex: {e}")
            # Create simulated result
            load_result = {
                "success": True,
                "documents": [
                    {
                        "id": f"llamadoc-{i}",
                        "content": f"This is sample document {i} for testing LlamaIndex integration with IPFS Kit.\n"
                                   f"It contains information about topic {i} that can be retrieved using LLMs.\n"
                                   f"This document discusses various aspects of machine learning and IPFS integration.\n",
                        "metadata": {
                            "source": f"{docs_dir}/llama_doc_{i}.txt",
                            "cid": docs_cid,
                            "path": f"{docs_cid}/llama_doc_{i}.txt"
                        }
                    } for i in range(3)
                ],
                "count": 3
            }
            logger.info(f"Using simulated document loading result with {len(load_result['documents'])} documents")

        # Create index
        if load_result.get('success', False) and 'documents' in load_result:
            logger.info("Creating LlamaIndex index")
            try:
                index_result = api.ai_llama_index_create_index(
                    load_result['documents'],
                    index_type="vector_store",
                    embed_model="fake-embeddings" if not llama_index_available else "local:sentence-transformers/all-MiniLM-L6-v2"
                )
                logger.info(f"Index created: {index_result.get('success', False)}")
            except Exception as e:
                logger.warning(f"Failed to create LlamaIndex index: {e}")
                # Create simulated result
                index_result = {
                    "success": True,
                    "index_type": "vector_store",
                    "document_count": len(load_result['documents']),
                    "index": "Simulated LlamaIndex vector store index"
                }
                logger.info("Using simulated index creation result")

            # Store index in IPFS (create mock file for simulation)
            index_path = "llama_index.json"
            with open(index_path, 'w') as f:
                f.write(json.dumps({"mock_index": "data"}))  # Mock data for demo purposes

            logger.info("Adding index to IPFS")
            try:
                index_add_result = api.add(index_path)
                if not index_add_result.get("success", False):
                    logger.warning("Failed to add index to IPFS, using simulated CID")
                    index_cid = f"Qm{os.urandom(16).hex()}"
                else:
                    index_cid = index_add_result.get("cid", f"Qm{os.urandom(16).hex()}")
            except Exception as e:
                logger.warning(f"Error adding index to IPFS: {e}")
                index_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID

            logger.info(f"Index added with CID: {index_cid}")

            # Demonstrate a query (simulated)
            logger.info("Performing query with LlamaIndex")
            try:
                query_result = api.ai_llama_index_query(
                    index_cid=index_cid,
                    query="What aspects of machine learning are discussed?",
                    response_mode="compact"
                )
                logger.info(f"Query result: {query_result}")
            except Exception as e:
                logger.warning(f"Failed to perform LlamaIndex query: {e}")
                # Create simulated result
                query_result = {
                    "success": True,
                    "query": "What aspects of machine learning are discussed?",
                    "response": "The documents discuss various aspects of machine learning and IPFS integration across different topics.",
                    "source_nodes": [
                        {
                            "content": load_result["documents"][1]["content"],
                            "metadata": load_result["documents"][1]["metadata"],
                            "score": 0.92
                        },
                        {
                            "content": load_result["documents"][0]["content"],
                            "metadata": load_result["documents"][0]["metadata"],
                            "score": 0.85
                        }
                    ],
                    "response_mode": "compact"
                }
                logger.info(f"Using simulated query result with response: '{query_result['response']}'")

            # Clean up index file
            if os.path.exists(index_path):
                os.remove(index_path)

    finally:
        # Clean up test files
        import shutil
        if os.path.exists(docs_dir):
            shutil.rmtree(docs_dir)


def distributed_training_workflow():
    """Demonstrate distributed training workflow."""
    logger.info("=== Distributed Training Workflow ===")

    # Initialize API
    api = IPFSSimpleAPI()

    # Define a training task
    training_task = {
        "task_type": "model_training",
        "model_type": "neural_network",
        "hyperparameters": {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 10,
            "optimizer": "adam"
        },
        "dataset_cid": "QmExampleDatasetCID",  # In a real example, this would be a real CID
        "framework": "pytorch",
        "model_architecture": {
            "input_dim": 10,
            "hidden_dims": [128, 64],
            "output_dim": 2,
            "activation": "relu"
        }
    }

    # Submit training job
    logger.info("Submitting distributed training job")
    try:
        submit_result = api.ai_distributed_training_submit_job(
            training_task=training_task,
            worker_count=3,
            priority=2
        )
        logger.info(f"Job submission result: {submit_result}")
    except Exception as e:
        logger.warning(f"Failed to submit training job: {e}")
        # Create simulated submission result
        import uuid
        job_id = str(uuid.uuid4())
        submit_result = {
            "success": True,
            "job_id": job_id,
            "worker_count": 3,
            "priority": 2,
            "status": "queued",
            "submitted_at": time.time(),
            "estimated_start_time": time.time() + 5,  # 5 seconds from now
            "task": training_task
        }
        logger.info(f"Using simulated job submission result with job_id: {job_id}")

    if submit_result.get('success', False) and 'job_id' in submit_result:
        job_id = submit_result['job_id']

        # Get job status
        logger.info(f"Getting status for job {job_id}")
        try:
            status_result = api.ai_distributed_training_get_status(job_id)
            logger.info(f"Job status: {status_result}")
        except Exception as e:
            logger.warning(f"Failed to get job status: {e}")
            # Create simulated status result
            status_result = {
                "success": True,
                "job_id": job_id,
                "status": "running",
                "progress": {
                    "total_tasks": 10,
                    "completed_tasks": 4,
                    "percentage": 40,
                    "active_workers": 3
                },
                "metrics": {
                    "current_epoch": 4,
                    "loss": 0.342,
                    "accuracy": 0.78,
                    "elapsed_time_seconds": 120
                },
                "start_time": time.time() - 120,  # Started 2 minutes ago
                "estimated_completion_time": time.time() + 180  # Will complete in 3 minutes
            }
            logger.info(f"Using simulated job status: {status_result['status']} ({status_result['progress']['percentage']}% complete)")

        # Aggregate results
        logger.info(f"Aggregating results for job {job_id}")
        try:
            aggregate_result = api.ai_distributed_training_aggregate_results(job_id)
            logger.info(f"Aggregation result: {aggregate_result}")
        except Exception as e:
            logger.warning(f"Failed to aggregate results: {e}")
            # Create simulated aggregation result
            model_cid = f"Qm{os.urandom(16).hex()}"
            aggregate_result = {
                "success": True,
                "job_id": job_id,
                "model_cid": model_cid,
                "metrics": {
                    "final_loss": 0.12,
                    "final_accuracy": 0.92,
                    "training_time_seconds": 350
                },
                "partial_results": [
                    {
                        "worker_id": f"worker-{i}",
                        "batch_range": f"{i*10}-{(i+1)*10-1}",
                        "metrics": {
                            "loss": 0.12 + (i * 0.01),
                            "accuracy": 0.92 - (i * 0.01)
                        }
                    } for i in range(3)
                ],
                "aggregation_method": "model_averaging",
                "completed_at": time.time()
            }
            logger.info(f"Using simulated aggregation result with model_cid: {model_cid}")

        # Cancel job (only if the job is still running)
        # In simulation, assume the job is still running
        logger.info(f"Canceling job {job_id}")
        try:
            cancel_result = api.ai_distributed_training_cancel_job(job_id)
            logger.info(f"Job cancellation result: {cancel_result}")
        except Exception as e:
            logger.warning(f"Failed to cancel job: {e}")
            # Create simulated cancellation result
            cancel_result = {
                "success": True,
                "job_id": job_id,
                "cancelled_at": time.time(),
                "previous_status": "running",
                "current_status": "cancelled",
                "reason": "User requested cancellation",
                "partial_results_cid": f"Qm{os.urandom(16).hex()}"
            }
            logger.info(f"Using simulated cancellation result: {cancel_result['current_status']}")


def model_deployment_workflow():
    """Demonstrate model deployment workflow."""
    logger.info("=== Model Deployment Workflow ===")

    # Initialize API
    api = IPFSSimpleAPI()

    # Create a simple model (placeholder for this example)
    model = {
        "name": "example_model",
        "version": "1.0.0",
        "architecture": {
            "type": "resnet",
            "layers": [64, 128, 256],
            "activation": "relu"
        },
        "weights": [0.1, 0.2, 0.3]  # Simplified for example
    }

    # Save to JSON file
    model_path = "deployment_model.json"
    with open(model_path, "w") as f:
        json.dump(model, f)

    try:
        # Add model to IPFS
        logger.info("Adding model to IPFS")
        try:
            add_result = api.add(model_path)
            if not add_result.get("success", False):
                logger.warning("Failed to add model to IPFS, using simulated CID")
                model_cid = f"Qm{os.urandom(16).hex()}"
            else:
                model_cid = add_result.get("cid", f"Qm{os.urandom(16).hex()}")
        except Exception as e:
            logger.warning(f"Error adding model to IPFS: {e}")
            model_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID

        logger.info(f"Model added with CID: {model_cid}")

        # Deploy model
        logger.info("Deploying model to inference endpoint")
        try:
            deploy_result = api.ai_deploy_model(
                model_cid,
                endpoint_type="rest",
                resources={"cpu": 1, "memory": "1GB"},
                scaling={"min_replicas": 1, "max_replicas": 3}
            )
            logger.info(f"Deployment result: {deploy_result}")
        except Exception as e:
            logger.warning(f"Failed to deploy model: {e}")
            # Create simulated deployment result
            import uuid
            endpoint_id = f"endpoint-{uuid.uuid4()}"
            deploy_result = {
                "success": True,
                "model_cid": model_cid,
                "endpoint_id": endpoint_id,
                "endpoint_type": "rest",
                "status": "deploying",
                "url": f"https://api.example.com/models/{model_cid}",
                "resources": {"cpu": 1, "memory": "1GB"},
                "scaling": {"min_replicas": 1, "max_replicas": 3},
                "created_at": time.time(),
                "estimated_ready_time": time.time() + 60  # Ready in 60 seconds
            }
            logger.info(f"Using simulated deployment result with endpoint_id: {endpoint_id}")

        if deploy_result.get("success", False) and "endpoint_id" in deploy_result:
            endpoint_id = deploy_result["endpoint_id"]

            # Get endpoint status
            logger.info(f"Getting status for endpoint {endpoint_id}")
            try:
                status_result = api.ai_get_endpoint_status(endpoint_id)
                logger.info(f"Endpoint status: {status_result}")
            except Exception as e:
                logger.warning(f"Failed to get endpoint status: {e}")
                # Create simulated status result
                status_result = {
                    "success": True,
                    "endpoint_id": endpoint_id,
                    "status": "ready",  # Assume it's already ready for this example
                    "url": deploy_result.get("url", f"https://api.example.com/models/{model_cid}"),
                    "metrics": {
                        "requests_per_second": 0,
                        "average_latency_ms": 0,
                        "success_rate": 1.0
                    },
                    "resources": {
                        "cpu_usage": "5%",
                        "memory_usage": "256MB",
                        "replicas": 1
                    },
                    "last_updated": time.time()
                }
                logger.info(f"Using simulated endpoint status: {status_result['status']}")

            # Simulate a test inference request
            logger.info("Testing inference endpoint with sample data")
            try:
                test_data = {"inputs": [1.0, 2.0, 3.0, 4.0, 5.0]}
                inference_result = api.ai_test_inference(
                    endpoint_id=endpoint_id,
                    data=test_data
                )
                logger.info(f"Inference result: {inference_result}")
            except Exception as e:
                logger.warning(f"Failed to test inference endpoint: {e}")
                # Create simulated inference result
                inference_result = {
                    "success": True,
                    "predictions": [0.78, 0.22],
                    "latency_ms": 42,
                    "model_version": model["version"]
                }
                logger.info(f"Using simulated inference result: {inference_result['predictions']}")

            # Optimize model for inference
            logger.info("Optimizing model for inference")
            try:
                optimize_result = api.ai_optimize_model(
                    model_cid,
                    target_platform="cpu",
                    optimization_level="O2",
                    quantization=True
                )
                logger.info(f"Optimization result: {optimize_result}")
            except Exception as e:
                logger.warning(f"Failed to optimize model: {e}")
                # Create simulated optimization result
                optimized_model_cid = f"Qm{os.urandom(16).hex()}"
                optimize_result = {
                    "success": True,
                    "original_cid": model_cid,
                    "optimized_cid": optimized_model_cid,
                    "target_platform": "cpu",
                    "optimization_level": "O2",
                    "quantization": True,
                    "metrics": {
                        "size_reduction": "65%",
                        "latency_improvement": "70%",
                        "original_size_bytes": 2458000,
                        "optimized_size_bytes": 859300,
                        "memory_footprint_reduction": "72%"
                    },
                    "completed_at": time.time()
                }
                logger.info(f"Using simulated optimization result with optimized_cid: {optimized_model_cid}")

            # Update deployment with optimized model
            logger.info("Updating deployment with optimized model")
            try:
                update_result = api.ai_update_deployment(
                    endpoint_id=endpoint_id,
                    model_cid=optimize_result.get("optimized_cid", optimized_model_cid)
                )
                logger.info(f"Deployment update result: {update_result}")
            except Exception as e:
                logger.warning(f"Failed to update deployment: {e}")
                # Create simulated update result
                update_result = {
                    "success": True,
                    "endpoint_id": endpoint_id,
                    "previous_model_cid": model_cid,
                    "new_model_cid": optimize_result.get("optimized_cid", optimized_model_cid),
                    "status": "updating",
                    "updated_at": time.time(),
                    "estimated_completion_time": time.time() + 30  # 30 seconds to update
                }
                logger.info(f"Using simulated deployment update result: {update_result['status']}")

    finally:
        # Clean up test file
        if os.path.exists(model_path):
            os.remove(model_path)


def vector_search_workflow():
    """Demonstrate vector search workflow."""
    logger.info("=== Vector Search Workflow ===")

    # Initialize API
    api = IPFSSimpleAPI()

    # Create sample documents
    docs_dir = "vector_search_docs"
    os.makedirs(docs_dir, exist_ok=True)

    try:
        # Create a few sample text files
        for i in range(5):
            with open(f"{docs_dir}/document_{i}.txt", "w") as f:
                f.write(f"This is document {i} about topic {i % 3}.\n")
                f.write(f"It contains information that might be relevant to search queries.\n")
                f.write(f"Keywords: topic{i % 3}, example, document{i}\n")

        # Add documents to IPFS
        logger.info("Adding documents to IPFS")
        try:
            # Use -r flag for directories via subprocess to avoid API limitations
            import subprocess
            cmd = ["ipfs", "add", "-Q", "-r", "--cid-version=1", docs_dir]
            p = subprocess.run(cmd, capture_output=True, text=True)

            if p.returncode == 0:
                docs_cid = p.stdout.strip()
                docs_result = {"success": True, "cid": docs_cid}
            else:
                # Fall back to standard API with recursive flag if available
                try:
                    docs_result = api.add(docs_dir, recursive=True)
                    if not docs_result.get("success", False):
                        logger.warning("Failed to add documents to IPFS, using simulated CID")
                        docs_cid = f"Qm{os.urandom(16).hex()}"
                    else:
                        docs_cid = docs_result.get("cid", f"Qm{os.urandom(16).hex()}")
                except Exception as e2:
                    logger.warning(f"Error adding documents with API fallback: {e2}")
                    docs_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID
        except Exception as e:
            logger.warning(f"Error adding documents to IPFS: {e}")
            docs_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID

        logger.info(f"Documents added with CID: {docs_cid}")

        # Create vector embeddings using langchain
        logger.info("Creating vector embeddings")

        # Check if langchain is available for more realistic example
        try:
            import langchain
            logger.info("Using langchain for embedding generation")
            is_langchain_available = True
        except ImportError:
            logger.info("Langchain not available, using simulated embeddings")
            is_langchain_available = False

        # Try to generate embeddings
        try:
            if is_langchain_available:
                # Use langchain integration
                embedding_result = api.ai_langchain_create_embeddings(
                    docs_cid,
                    embedding_model="fake-embeddings",  # Replace with real model in actual implementation
                    recursive=True,
                    filter_pattern="*.txt"
                )
            else:
                # Can't use langchain, try generic embedding method
                embedding_result = api.ai_create_embeddings(
                    docs_cid,
                    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                    recursive=True,
                    filter_pattern="*.txt"
                )
        except Exception as e:
            logger.warning(f"Failed to create embeddings: {e}")
            # Create simulated embedding result
            embedding_cid = f"Qm{os.urandom(16).hex()}"
            embedding_result = {
                "success": True,
                "cid": embedding_cid,
                "embedding_count": 5,
                "dimensions": 384,
                "embedding_model": "simulated-embeddings",
                "documents": [f"{docs_cid}/document_{i}.txt" for i in range(5)],
                "index_type": "hnsw"
            }
            logger.info("Using simulated embedding result")

        logger.info(f"Embedding result: {embedding_result}")

        # Create a vector index from the embeddings
        logger.info("Creating vector search index")
        try:
            index_result = api.ai_create_vector_index(
                embedding_cid=embedding_result.get("cid", embedding_cid),
                index_type="hnsw",
                params={"M": 16, "efConstruction": 200}
            )
            logger.info(f"Vector index creation result: {index_result}")
        except Exception as e:
            logger.warning(f"Failed to create vector index: {e}")
            # Create simulated index result
            index_cid = f"Qm{os.urandom(16).hex()}"
            index_result = {
                "success": True,
                "cid": index_cid,
                "index_type": "hnsw",
                "dimensions": embedding_result.get("dimensions", 384),
                "vector_count": embedding_result.get("embedding_count", 5),
                "parameters": {"M": 16, "efConstruction": 200, "efSearch": 50},
                "metadata": {
                    "embedding_model": embedding_result.get("embedding_model", "simulated-embeddings"),
                    "documents_cid": docs_cid
                }
            }
            logger.info("Using simulated vector index result")

        # Perform vector search
        logger.info("Performing vector search")
        query = "information about topic1"
        try:
            search_result = api.ai_vector_search(
                query=query,
                vector_index_cid=index_result.get("cid", index_cid),
                top_k=3,
                similarity_threshold=0.7
            )
            logger.info(f"Search results: {search_result}")
        except Exception as e:
            logger.warning(f"Failed to perform vector search: {e}")
            # Create simulated search results
            search_result = {
                "success": True,
                "query": query,
                "results": [
                    {
                        "content": f"This is document {i} about topic {i % 3}.\n"
                                   f"It contains information that might be relevant to search queries.\n"
                                   f"Keywords: topic{i % 3}, example, document{i}\n",
                        "similarity": 0.92 - (i * 0.05),
                        "metadata": {
                            "source": f"{docs_dir}/document_{i}.txt",
                            "cid": f"{docs_cid}/document_{i}.txt"
                        }
                    } for i in [1, 4, 0]  # Simulated result order by relevance
                ],
                "total_vectors_searched": embedding_result.get("embedding_count", 5),
                "search_time_ms": 8
            }
            logger.info(f"Using simulated search results with {len(search_result['results'])} matches")

        # Demonstrate hybrid search (combining vector and keyword search)
        logger.info("Performing hybrid search (vector + keyword)")
        try:
            hybrid_result = api.ai_hybrid_search(
                query=query,
                vector_index_cid=index_result.get("cid", index_cid),
                keyword_weight=0.3,
                vector_weight=0.7,
                top_k=3
            )
            logger.info(f"Hybrid search results: {hybrid_result}")
        except Exception as e:
            logger.warning(f"Failed to perform hybrid search: {e}")
            # Create simulated hybrid search results
            hybrid_result = {
                "success": True,
                "query": query,
                "results": [
                    {
                        "content": f"This is document {i} about topic {i % 3}.\n"
                                   f"It contains information that might be relevant to search queries.\n"
                                   f"Keywords: topic{i % 3}, example, document{i}\n",
                        "vector_score": 0.89 - (i * 0.03),
                        "keyword_score": 0.76 - (i * 0.06),
                        "combined_score": 0.85 - (i * 0.04),
                        "metadata": {
                            "source": f"{docs_dir}/document_{i}.txt",
                            "cid": f"{docs_cid}/document_{i}.txt"
                        }
                    } for i in [1, 0, 4]  # Different order from pure vector search
                ],
                "weights": {"vector": 0.7, "keyword": 0.3},
                "search_time_ms": 12
            }
            logger.info(f"Using simulated hybrid search results with {len(hybrid_result['results'])} matches")

    finally:
        # Clean up test files
        import shutil
        if os.path.exists(docs_dir):
            shutil.rmtree(docs_dir)


def knowledge_graph_workflow():
    """Demonstrate knowledge graph workflow."""
    logger.info("=== Knowledge Graph Workflow ===")

    # Initialize API
    api = IPFSSimpleAPI()

    # Create entity data
    entities = [
        {"id": "entity1", "type": "Person", "name": "John Doe", "age": 30},
        {"id": "entity2", "type": "Company", "name": "Acme Corp", "industry": "Technology"},
        {"id": "entity3", "type": "Product", "name": "Widget X", "price": 99.99},
        {"id": "entity4", "type": "Person", "name": "Jane Smith", "age": 28}
    ]

    # Create relationships data
    relationships = [
        {"from": "entity1", "to": "entity2", "type": "WORKS_FOR", "since": 2020},
        {"from": "entity2", "to": "entity3", "type": "PRODUCES", "quantity": 1000},
        {"from": "entity4", "to": "entity2", "type": "WORKS_FOR", "since": 2019},
        {"from": "entity1", "to": "entity4", "type": "KNOWS", "strength": 0.8}
    ]

    # Save to JSON files
    entities_path = "knowledge_graph_entities.json"
    with open(entities_path, "w") as f:
        json.dump(entities, f)

    relationships_path = "knowledge_graph_relationships.json"
    with open(relationships_path, "w") as f:
        json.dump(relationships, f)

    try:
        # Add entities to IPFS
        logger.info("Adding entities to IPFS")
        try:
            entities_result = api.add(entities_path)
            if not entities_result.get("success", False):
                logger.warning("Failed to add entities to IPFS, using simulated CID")
                entities_cid = f"Qm{os.urandom(16).hex()}"
            else:
                entities_cid = entities_result.get("cid", f"Qm{os.urandom(16).hex()}")
        except Exception as e:
            logger.warning(f"Error adding entities to IPFS: {e}")
            entities_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID

        logger.info(f"Entities added with CID: {entities_cid}")

        # Add relationships to IPFS
        logger.info("Adding relationships to IPFS")
        try:
            relationships_result = api.add(relationships_path)
            if not relationships_result.get("success", False):
                logger.warning("Failed to add relationships to IPFS, using simulated CID")
                relationships_cid = f"Qm{os.urandom(16).hex()}"
            else:
                relationships_cid = relationships_result.get("cid", f"Qm{os.urandom(16).hex()}")
        except Exception as e:
            logger.warning(f"Error adding relationships to IPFS: {e}")
            relationships_cid = f"Qm{os.urandom(16).hex()}"  # Simulated CID

        logger.info(f"Relationships added with CID: {relationships_cid}")

        # Create knowledge graph
        logger.info("Creating knowledge graph")
        try:
            graph_result = api.ai_create_knowledge_graph(
                entities_cid=entities_cid,
                relationships_cid=relationships_cid,
                graph_name="Example Knowledge Graph"
            )
            logger.info(f"Knowledge graph creation result: {graph_result}")
        except Exception as e:
            logger.warning(f"Failed to create knowledge graph: {e}")
            # Create simulated graph result
            graph_cid = f"Qm{os.urandom(16).hex()}"
            graph_result = {
                "success": True,
                "graph_cid": graph_cid,
                "graph_name": "Example Knowledge Graph",
                "entity_count": len(entities),
                "relationship_count": len(relationships),
                "created_at": time.time(),
                "stats": {
                    "node_types": {"Person": 2, "Company": 1, "Product": 1},
                    "relationship_types": {"WORKS_FOR": 2, "PRODUCES": 1, "KNOWS": 1}
                }
            }
            logger.info(f"Using simulated knowledge graph creation result with graph_cid: {graph_cid}")

        if graph_result.get("success", False) and "graph_cid" in graph_result:
            graph_cid = graph_result["graph_cid"]

            # Query the knowledge graph
            logger.info("Querying knowledge graph")
            try:
                query_result = api.ai_query_knowledge_graph(
                    graph_cid=graph_cid,
                    query="MATCH (p:Person)-[r:WORKS_FOR]->(c:Company) RETURN p, r, c",
                    query_type="cypher"
                )
                logger.info(f"Query result: {query_result}")
            except Exception as e:
                logger.warning(f"Failed to query knowledge graph: {e}")
                # Create simulated query result
                query_result = {
                    "success": True,
                    "query": "MATCH (p:Person)-[r:WORKS_FOR]->(c:Company) RETURN p, r, c",
                    "query_type": "cypher",
                    "results": [
                        {
                            "p": entities[0],  # John Doe
                            "r": relationships[0],  # WORKS_FOR since 2020
                            "c": entities[1]   # Acme Corp
                        },
                        {
                            "p": entities[3],  # Jane Smith
                            "r": relationships[2],  # WORKS_FOR since 2019
                            "c": entities[1]   # Acme Corp
                        }
                    ],
                    "execution_time_ms": 8
                }
                logger.info(f"Using simulated query result with {len(query_result['results'])} matches")

            # Calculate node metrics
            logger.info("Calculating graph metrics")
            try:
                metrics_result = api.ai_calculate_graph_metrics(
                    graph_cid=graph_cid,
                    metrics=["centrality", "clustering_coefficient"]
                )
                logger.info(f"Metrics result: {metrics_result}")
            except Exception as e:
                logger.warning(f"Failed to calculate graph metrics: {e}")
                # Create simulated metrics result
                metrics_result = {
                    "success": True,
                    "graph_cid": graph_cid,
                    "metrics": {
                        "centrality": {
                            "entity1": 0.67,  # John Doe
                            "entity2": 1.0,   # Acme Corp (highest centrality)
                            "entity3": 0.33,  # Widget X
                            "entity4": 0.67   # Jane Smith
                        },
                        "clustering_coefficient": {
                            "entity1": 0.33,
                            "entity2": 0,
                            "entity3": 0,
                            "entity4": 0.5
                        },
                        "average_path_length": 1.67,
                        "graph_density": 0.33
                    },
                    "calculation_time_ms": 15
                }
                logger.info("Using simulated graph metrics result")

            # Demonstrate graph expansion with external data (simulated)
            logger.info("Expanding knowledge graph with external data")
            try:
                expansion_result = api.ai_expand_knowledge_graph(
                    graph_cid=graph_cid,
                    seed_entity="entity2",  # Acme Corp
                    data_source="external",
                    expansion_type="competitors",
                    max_entities=3
                )
                logger.info(f"Graph expansion result: {expansion_result}")
            except Exception as e:
                logger.warning(f"Failed to expand knowledge graph: {e}")
                # Create simulated expansion result
                new_graph_cid = f"Qm{os.urandom(16).hex()}"
                expansion_result = {
                    "success": True,
                    "original_graph_cid": graph_cid,
                    "expanded_graph_cid": new_graph_cid,
                    "added_entities": [
                        {"id": "entity5", "type": "Company", "name": "TechCorp", "industry": "Technology"},
                        {"id": "entity6", "type": "Company", "name": "Innovex", "industry": "Technology"},
                        {"id": "entity7", "type": "Person", "name": "Alice Johnson", "age": 42}
                    ],
                    "added_relationships": [
                        {"from": "entity2", "to": "entity5", "type": "COMPETES_WITH", "market_overlap": 0.7},
                        {"from": "entity2", "to": "entity6", "type": "COMPETES_WITH", "market_overlap": 0.4},
                        {"from": "entity7", "to": "entity5", "type": "WORKS_FOR", "since": 2018, "position": "CEO"}
                    ],
                    "expansion_source": "external",
                    "entity_count": 7,  # Original 4 + 3 new ones
                    "relationship_count": 7  # Original 4 + 3 new ones
                }
                logger.info(f"Using simulated graph expansion result with new graph_cid: {new_graph_cid}")

    finally:
        # Clean up test files
        if os.path.exists(entities_path):
            os.remove(entities_path)
        if os.path.exists(relationships_path):
            os.remove(relationships_path)


def check_ipfs_available():
    """Check if IPFS daemon is available and running."""
    try:
        # Initialize API
        api = IPFSSimpleAPI()

        # Try a simple operation
        version_result = api("get_version")
        if version_result and version_result.get("success", False):
            return True
        return False
    except Exception:
        return False


def main():
    """Run the AI/ML integration examples."""
    logger.info("Starting High-Level API AI/ML Integration Example")

    # Check if IPFS daemon is available
    if not check_ipfs_available():
        logger.warning("=============================================")
        logger.warning("IPFS daemon is not available or not running.")
        logger.warning("This example will run in simulation mode.")
        logger.warning("To run with real IPFS, start the IPFS daemon:")
        logger.warning("    ipfs daemon")
        logger.warning("=============================================")
        logger.warning("Continuing with simulated responses...")

        # For demo purposes, we'll continue with simulated operations
        # In a real application, you might want to exit here

    try:
        # Run dataset workflow
        dataset_workflow()
    except Exception as e:
        logger.error(f"Error in dataset workflow: {e}")

    try:
        # Run model registry workflow
        model_registry_workflow()
    except Exception as e:
        logger.error(f"Error in model registry workflow: {e}")

    try:
        # Run Langchain integration workflow
        langchain_workflow()
    except Exception as e:
        logger.error(f"Error in Langchain workflow: {e}")

    try:
        # Run LlamaIndex integration workflow
        llama_index_workflow()
    except Exception as e:
        logger.error(f"Error in LlamaIndex workflow: {e}")

    try:
        # Run distributed training workflow
        distributed_training_workflow()
    except Exception as e:
        logger.error(f"Error in distributed training workflow: {e}")

    try:
        # Run model deployment workflow
        model_deployment_workflow()
    except Exception as e:
        logger.error(f"Error in model deployment workflow: {e}")

    try:
        # Run vector search workflow
        vector_search_workflow()
    except Exception as e:
        logger.error(f"Error in vector search workflow: {e}")

    try:
        # Run knowledge graph workflow
        knowledge_graph_workflow()
    except Exception as e:
        logger.error(f"Error in knowledge graph workflow: {e}")

    logger.info("AI/ML integration examples completed")


if __name__ == "__main__":
    main()
