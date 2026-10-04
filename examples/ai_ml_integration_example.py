#!/usr/bin/env python3
"""
AI/ML Integration Example with IPFS Kit

This example demonstrates key features of the AI/ML integration capabilities
of IPFS Kit, including:

1. Model Registry - storing and retrieving ML models
2. Dataset Management - handling ML datasets
3. Framework Integration - working with PyTorch and TensorFlow
4. LangChain Integration - using IPFS with LangChain
5. Distributed Training - setting up distributed ML training

Requirements:
- ipfs_kit_py
- torch
- sklearn
- pandas
- numpy
- (optional) tensorflow
- (optional) langchain
"""

import os
import time
import uuid
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.datasets import make_classification

# Import IPFS Kit
from ipfs_kit_py import ipfs_kit
from ipfs_kit_py.ai_ml_integration import (
    ModelRegistry,
    DatasetManager,
    IPFSDataLoader,
    DistributedTraining
)

# Optional imports - these will be used conditionally if available
try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

try:
    from langchain.document_loaders import TextLoader
    from langchain.text_splitter import CharacterTextSplitter
    from langchain.vectorstores import FAISS
    from langchain.embeddings import OpenAIEmbeddings
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


def example_model_registry():
    """Demonstrate ModelRegistry functionality."""
    print("\n===== Model Registry Example =====")
    
    # Initialize IPFS Kit
    kit = ipfs_kit()
    
    # Create model registry
    registry = ModelRegistry(ipfs_client=kit)
    
    # Create a simple scikit-learn model
    X, y = make_classification(n_samples=1000, n_features=20, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate the model
    accuracy = model.score(X_test, y_test)
    print(f"Model trained with accuracy: {accuracy:.4f}")
    
    # Store the model in the registry
    model_info = registry.store_model(
        model=model,
        name="example_classifier",
        version="1.0.0",
        metadata={
            "description": "Example random forest classifier",
            "accuracy": accuracy,
            "features": 20,
            "created_at": time.time()
        }
    )
    
    print(f"Model stored with CID: {model_info['cid']}")
    
    # List available models
    available_models = registry.list_models()
    print("\nAvailable models:")
    for model_name, versions in available_models.items():
        print(f"  Model: {model_name}")
        for version, metadata in versions.items():
            print(f"    Version: {version}, CID: {metadata['cid']}")
    
    # Load model from registry
    loaded_model, metadata = registry.load_model(
        name="example_classifier", 
        version="1.0.0"
    )
    
    # Verify loaded model works correctly
    loaded_accuracy = loaded_model.score(X_test, y_test)
    print(f"\nLoaded model accuracy: {loaded_accuracy:.4f}")
    print(f"Model metadata: {metadata}")
    
    return registry


def example_dataset_management():
    """Demonstrate DatasetManager functionality."""
    print("\n===== Dataset Management Example =====")
    
    # Initialize IPFS Kit
    kit = ipfs_kit()
    
    # Create dataset manager
    dataset_manager = DatasetManager(ipfs_client=kit)
    
    # Create a sample dataset
    X, y = make_classification(n_samples=1000, n_features=20, random_state=42)
    
    # Create a pandas DataFrame
    df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(X.shape[1])])
    df["target"] = y
    
    print(f"Sample dataset shape: {df.shape}")
    print(df.head())
    
    # Store dataset in IPFS
    dataset_info = dataset_manager.store_dataset(
        dataset=df,
        name="example_classification_dataset",
        version="1.0.0",
        format="parquet",  # Convert to parquet for efficiency
        metadata={
            "description": "Example classification dataset with 20 features",
            "rows": len(df),
            "columns": list(df.columns),
            "created_at": time.time()
        }
    )
    
    print(f"\nDataset stored with CID: {dataset_info['cid']}")
    
    # Create train/test splits and store as separate versions
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    
    train_info = dataset_manager.store_dataset(
        dataset=train_df,
        name="example_dataset_train",
        version="1.0.0",
        format="parquet",
        metadata={
            "description": "Training split of example dataset",
            "split": "train",
            "parent_dataset": dataset_info['cid'],
            "rows": len(train_df)
        }
    )
    
    test_info = dataset_manager.store_dataset(
        dataset=test_df,
        name="example_dataset_test",
        version="1.0.0",
        format="parquet",
        metadata={
            "description": "Test split of example dataset",
            "split": "test",
            "parent_dataset": dataset_info['cid'],
            "rows": len(test_df)
        }
    )
    
    print(f"Training dataset stored with CID: {train_info['cid']}")
    print(f"Test dataset stored with CID: {test_info['cid']}")
    
    # List available datasets
    available_datasets = dataset_manager.list_datasets()
    print("\nAvailable datasets:")
    for dataset_name, versions in available_datasets.items():
        print(f"  Dataset: {dataset_name}")
        for version, metadata in versions.items():
            print(f"    Version: {version}, CID: {metadata['cid']}")
    
    # Load dataset from IPFS
    loaded_df, metadata = dataset_manager.load_dataset(
        name="example_classification_dataset",
        version="1.0.0"
    )
    
    print(f"\nLoaded dataset shape: {loaded_df.shape}")
    print(f"Sample of loaded data:")
    print(loaded_df.head())
    print(f"Dataset metadata: {metadata}")
    
    return dataset_manager


def example_ipfs_dataloader():
    """Demonstrate IPFSDataLoader functionality."""
    print("\n===== IPFS DataLoader Example =====")
    
    # Initialize IPFS Kit
    kit = ipfs_kit()
    
    # Create data loader
    data_loader = IPFSDataLoader(
        ipfs_client=kit,
        batch_size=32,
        shuffle=True,
        prefetch=2
    )
    
    # First we need to store a dataset in IPFS
    dataset_manager = DatasetManager(ipfs_client=kit)
    
    # Create a sample dataset
    X, y = make_classification(n_samples=1000, n_features=20, random_state=42)
    
    # Create a numpy array dataset
    dataset = {"features": X, "labels": y}
    
    # Store dataset in IPFS
    dataset_info = dataset_manager.store_dataset(
        dataset=dataset,
        name="numpy_dataset",
        version="1.0.0",
        format="numpy",
        metadata={
            "description": "NumPy dataset for DataLoader example",
            "samples": X.shape[0],
            "features": X.shape[1]
        }
    )
    
    # Load dataset with the DataLoader
    data_loader.load_dataset(cid=dataset_info['cid'])
    
    # Process a few batches
    print("\nProcessing batches from DataLoader:")
    for i, batch in enumerate(data_loader):
        print(f"Batch {i+1}:")
        print(f"  Features shape: {batch['features'].shape}")
        print(f"  Labels shape: {batch['labels'].shape}")
        
        # Process only 3 batches for this example
        if i >= 2:
            break
    
    # Create framework-specific loaders if available
    if PYTORCH_AVAILABLE:
        print("\nConverting to PyTorch DataLoader:")
        pytorch_dataloader = data_loader.to_pytorch()
        
        # Show a batch from PyTorch DataLoader
        for features, labels in pytorch_dataloader:
            print(f"  PyTorch batch - Features: {features.shape}, Labels: {labels.shape}")
            break
    
    if TENSORFLOW_AVAILABLE:
        print("\nConverting to TensorFlow Dataset:")
        tf_dataset = data_loader.to_tensorflow()
        
        # Show a batch from TensorFlow Dataset
        for features, labels in tf_dataset.take(1):
            print(f"  TensorFlow batch - Features: {features.shape}, Labels: {labels.shape}")
    
    return data_loader


def example_pytorch_integration():
    """Demonstrate PyTorch integration."""
    if not PYTORCH_AVAILABLE:
        print("\n===== PyTorch Integration Example =====")
        print("PyTorch not available. Skipping this example.")
        return None
    
    print("\n===== PyTorch Integration Example =====")
    
    # Initialize IPFS Kit
    kit = ipfs_kit()
    
    # Create model registry
    registry = ModelRegistry(ipfs_client=kit)
    
    # Define a simple PyTorch model
    class SimpleNN(nn.Module):
        def __init__(self, input_dim=20, hidden_dim=64, output_dim=2):
            super().__init__()
            self.layer1 = nn.Linear(input_dim, hidden_dim)
            self.activation = nn.ReLU()
            self.layer2 = nn.Linear(hidden_dim, output_dim)
            
        def forward(self, x):
            x = self.layer1(x)
            x = self.activation(x)
            x = self.layer2(x)
            return x
    
    # Create a PyTorch model
    model = SimpleNN()
    print(f"Created PyTorch model: {model}")
    
    # Store the model in the registry
    model_info = registry.store_model(
        model=model,
        name="pytorch_example",
        version="1.0.0",
        metadata={
            "description": "Simple PyTorch neural network",
            "framework": "pytorch",
            "input_dim": 20,
            "hidden_dim": 64,
            "output_dim": 2,
            "created_at": time.time()
        }
    )
    
    print(f"PyTorch model stored with CID: {model_info['cid']}")
    
    # Load the model from registry
    loaded_model, metadata = registry.load_model(
        name="pytorch_example",
        version="1.0.0"
    )
    
    print(f"\nLoaded PyTorch model: {loaded_model}")
    print(f"Model metadata: {metadata}")
    
    # Create sample input to verify model works
    sample_input = torch.randn(4, 20)  # batch of 4, 20 features
    output = loaded_model(sample_input)
    
    print(f"\nModel prediction shape on sample input: {output.shape}")
    print(f"Model output: {output}")
    
    return registry


def example_langchain_integration():
    """Demonstrate LangChain integration."""
    if not LANGCHAIN_AVAILABLE:
        print("\n===== LangChain Integration Example =====")
        print("LangChain not available. Skipping this example.")
        return None
        
    # Check for OpenAI API key, required for embeddings
    if "OPENAI_API_KEY" not in os.environ:
        print("\n===== LangChain Integration Example =====")
        print("OpenAI API key not found in environment variables.")
        print("Please set OPENAI_API_KEY to run this example.")
        return None
    
    print("\n===== LangChain Integration Example =====")
    
    # Initialize IPFS Kit
    kit = ipfs_kit()
    
    # Import LangChain integration
    from ipfs_kit_py.ai_ml_integration import LangchainIntegration
    
    # Create LangChain integration
    langchain_integration = LangchainIntegration(ipfs_client=kit)
    
    # Create a simple document
    document_content = """
    IPFS is a distributed system for storing and accessing files, websites, applications, and data.
    
    What is IPFS?
    IPFS is a distributed system for storing and accessing files, websites, applications, and data.
    
    What does that mean? Let's say you're doing some research on aardvarks. You might start by visiting the Wikipedia page on aardvarks at:
    https://en.wikipedia.org/wiki/Aardvark
    
    When you put that URL in your browser, your computer asks one of Wikipedia's computers, which might be somewhere on the other side of the world, for the aardvark page.
    
    However, that's not the only option for meeting your aardvark needs! There's a mirror of Wikipedia stored on IPFS, and you could use that instead. If you use IPFS, your computer asks your neighbors if they have the aardvark page. If your neighbors don't have the aardvark page, they ask their neighbors, and their neighbors ask their neighbors, until someone responds with the page.
    
    IPFS makes this possible by building a distributed network of people who help store and deliver content.
    """
    
    # Create a temporary file for the document
    doc_path = "/tmp/ipfs_doc.txt"
    with open(doc_path, "w") as f:
        f.write(document_content)
    
    # Load documents with LangChain
    documents = langchain_integration.load_documents(file_path=doc_path)
    print(f"Loaded {len(documents)} documents")
    
    # Split documents into chunks
    text_splitter = CharacterTextSplitter(chunk_size=250, chunk_overlap=50)
    split_docs = text_splitter.split_documents(documents)
    print(f"Split into {len(split_docs)} chunks")
    
    # Create embeddings and vector store
    embeddings = OpenAIEmbeddings()
    vector_store = langchain_integration.create_vector_store(
        documents=split_docs,
        embedding=embeddings
    )
    
    print("Created vector store")
    
    # Store vector store in IPFS
    vector_store_info = langchain_integration.store_vector_store(
        vector_store=vector_store,
        name="ipfs_docs_vector_store",
        version="1.0.0",
        metadata={
            "description": "Example vector store for IPFS documentation",
            "document_count": len(split_docs),
            "created_at": time.time()
        }
    )
    
    print(f"Vector store stored with CID: {vector_store_info['cid']}")
    
    # Load vector store from IPFS
    loaded_vector_store = langchain_integration.load_vector_store(
        name="ipfs_docs_vector_store",
        version="1.0.0",
        embedding=embeddings
    )
    
    # Search the vector store
    query = "How does IPFS differ from traditional web browsing?"
    search_results = loaded_vector_store.similarity_search(query, k=2)
    
    print(f"\nSearch results for query: '{query}'")
    for i, doc in enumerate(search_results):
        print(f"\nResult {i+1}:")
        print(doc.page_content)
    
    return langchain_integration


def example_distributed_training():
    """Demonstrate distributed training setup."""
    print("\n===== Distributed Training Example =====")
    
    # Initialize IPFS Kit with cluster manager
    kit = ipfs_kit(role="master")
    
    # The actual cluster manager would be available in a real setup
    # For this example, we'll simulate its presence
    try:
        cluster_manager = kit.get_cluster_manager()
        print("Got real cluster manager")
    except:
        print("Using simulated cluster manager for example")
        cluster_manager = None
    
    # Create distributed training manager
    training = DistributedTraining(
        ipfs_client=kit,
        cluster_manager=cluster_manager
    )
    
    # Define a training task
    training_task = {
        "name": "mnist_classification",
        "model_type": "pytorch" if PYTORCH_AVAILABLE else "sklearn",
        "model_architecture": "simple_cnn" if PYTORCH_AVAILABLE else "random_forest",
        "dataset": "mnist",
        "hyperparameters": {
            "learning_rate": 0.001 if PYTORCH_AVAILABLE else None,
            "batch_size": 64 if PYTORCH_AVAILABLE else None,
            "epochs": 5 if PYTORCH_AVAILABLE else None,
            "n_estimators": 100 if not PYTORCH_AVAILABLE else None
        },
        "optimizer": "adam" if PYTORCH_AVAILABLE else None
    }
    
    # Submit training job (simulated in this example)
    print(f"\nSubmitting training job with configuration:")
    for key, value in training_task.items():
        print(f"  {key}: {value}")
    
    # In a real scenario, this would distribute the task to worker nodes
    job_id = str(uuid.uuid4())
    print(f"\nJob submitted with ID: {job_id}")
    
    # Simulate job status updates
    for progress in [10, 25, 50, 75, 100]:
        status = {
            "job_id": job_id,
            "status": "in_progress" if progress < 100 else "completed",
            "progress": progress,
            "current_epoch": progress // 20 if PYTORCH_AVAILABLE else None,
            "metrics": {
                "accuracy": 0.5 + (progress / 200),  # Simulated increasing accuracy
                "loss": 1.0 - (progress / 150)  # Simulated decreasing loss
            }
        }
        
        print(f"\nJob status update:")
        print(f"  Progress: {status['progress']}%")
        print(f"  Status: {status['status']}")
        if status['metrics']:
            print(f"  Current accuracy: {status['metrics']['accuracy']:.4f}")
            if PYTORCH_AVAILABLE:
                print(f"  Current loss: {status['metrics']['loss']:.4f}")
                
        if progress < 100:
            print("  Waiting for next update...")
            time.sleep(1)  # Just for demonstration purposes
    
    # Simulate final result with model CID
    result_cid = "QmSimulatedModelCID" + str(uuid.uuid4())[:8]
    print(f"\nTraining completed. Model stored with CID: {result_cid}")
    
    # In a real scenario, you would load the model from this CID
    print(f"Model can be loaded using: registry.load_model(cid='{result_cid}')")
    
    return training


def run_all_examples():
    """Run all examples sequentially."""
    print("Running IPFS Kit AI/ML Integration Examples")
    print("==========================================")
    
    example_model_registry()
    example_dataset_management()
    example_ipfs_dataloader()
    
    if PYTORCH_AVAILABLE:
        example_pytorch_integration()
    
    if LANGCHAIN_AVAILABLE and "OPENAI_API_KEY" in os.environ:
        example_langchain_integration()
    
    example_distributed_training()
    
    print("\n==========================================")
    print("All examples completed successfully!")


if __name__ == "__main__":
    run_all_examples()