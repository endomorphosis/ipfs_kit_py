#!/usr/bin/env python3
"""
Distributed Training Example for MCP Server

This example demonstrates how to use the Distributed Training module to train
machine learning models across multiple nodes. It shows the core functionality
of the module:

1. Creating and submitting training jobs
2. Monitoring job progress and metrics
3. Working with hyperparameter optimization
4. Managing model checkpoints
5. Integration with model registry and dataset manager

Usage:
  python distributed_training_example.py [--ray] [--torch-dist]
"""

import os
import sys
import tempfile
import argparse
import logging
import json
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("distributed-training-example")

# Try to import optional dependencies
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("NumPy not available. Some examples will be limited.")

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not available. PyTorch examples will be skipped.")

try:
    from ray import tune
    import ray
    HAS_RAY = True
except ImportError:
    HAS_RAY = False
    logger.warning("Ray not available. Hyperparameter tuning examples will be skipped.")

# Import MCP components
try:
    from ipfs_kit_py.mcp.ai.distributed_training import (
        TrainingJob,
        TrainingJobConfig,
        TrainingJobStore,
        TrainingJobRunner,
        TrainingStatus,
        TrainingJobType,
        FrameworkType,
        ResourceRequirements,
        HyperparameterConfig,
        OptimizationStrategy,
        CheckpointStrategy,
        NodeInfo,
        Checkpoint,
        TrainingMetrics
    )
except ImportError:
    logger.error("Failed to import distributed training modules. Make sure ipfs_kit_py is installed")
    sys.exit(1)

try:
    from ipfs_kit_py.mcp.ai.model_registry import (
        ModelRegistry,
        Model,
        ModelVersion,
        ModelFramework
    )
    HAS_MODEL_REGISTRY = True
except ImportError:
    HAS_MODEL_REGISTRY = False
    logger.warning("Model Registry not available. Some examples will be skipped.")

try:
    from ipfs_kit_py.mcp.ai.dataset_manager import (
        Dataset,
        DatasetVersion,
        DatasetFormat,
        DatasetSplit
    )
    HAS_DATASET_MANAGER = True
except ImportError:
    HAS_DATASET_MANAGER = False
    logger.warning("Dataset Manager not available. Some examples will be skipped.")

# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def create_simple_pytorch_model() -> Optional[str]:
    """Create a simple PyTorch model and save it to a file."""
    if not HAS_TORCH:
        logger.warning("PyTorch not available. Skipping model creation.")
        return None
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Define a simple model
    class SimpleModel(nn.Module):
        def __init__(self):
            super(SimpleModel, self).__init__()
            self.fc1 = nn.Linear(10, 50)
            self.relu = nn.ReLU()
            self.fc2 = nn.Linear(50, 1)
            self.sigmoid = nn.Sigmoid()
        
        def forward(self, x):
            x = self.fc1(x)
            x = self.relu(x)
            x = self.fc2(x)
            x = self.sigmoid(x)
            return x
    
    # Instantiate the model
    model = SimpleModel()
    
    # Save the model
    model_path = os.path.join(temp_dir, "simple_model.pt")
    torch.save(model.state_dict(), model_path)
    
    logger.info(f"Created simple PyTorch model at: {model_path}")
    return model_path

def create_training_script() -> Optional[str]:
    """Create a simple training script."""
    if not HAS_TORCH:
        logger.warning("PyTorch not available. Skipping script creation.")
        return None
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Define a simple training script
    script_content = """#!/usr/bin/env python3
import os
import sys
import argparse
import logging
import json
import torch
import torch.nn as nn
import torch.optim as optim
import torch.utils.data as data
import numpy as np
from torch.utils.tensorboard import SummaryWriter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("training-script")

class SimpleModel(nn.Module):
    def __init__(self):
        super(SimpleModel, self).__init__()
        self.fc1 = nn.Linear(10, 50)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(50, 1)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        x = self.sigmoid(x)
        return x

def generate_data(num_samples=1000):
    # Generate random data
    X = np.random.randn(num_samples, 10).astype(np.float32)
    # Generate binary labels
    w = np.random.randn(10).astype(np.float32)
    y = (np.matmul(X, w) > 0).astype(np.float32).reshape(-1, 1)
    return X, y

def train(args):
    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    # Generate synthetic data
    X_train, y_train = generate_data(args.train_samples)
    X_val, y_val = generate_data(args.val_samples)
    
    # Create data loaders
    train_dataset = data.TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    val_dataset = data.TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))
    
    train_loader = data.DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=args.workers
    )
    val_loader = data.DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.workers
    )
    
    # Create model
    model = SimpleModel().to(device)
    
    # Load pre-trained weights if provided
    if args.model_path and os.path.exists(args.model_path):
        logger.info(f"Loading model from {args.model_path}")
        model.load_state_dict(torch.load(args.model_path))
    
    # Loss function and optimizer
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=args.learning_rate)
    
    # Set up TensorBoard
    writer = SummaryWriter(args.output_dir)
    
    # Checkpointing
    os.makedirs(args.checkpoint_dir, exist_ok=True)
    best_val_loss = float('inf')
    
    # Training loop
    for epoch in range(args.epochs):
        # Training phase
        model.train()
        train_loss = 0.0
        correct = 0
        total = 0
        
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            
            # Zero the parameter gradients
            optimizer.zero_grad()
            
            # Forward pass
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            
            # Backward pass and optimize
            loss.backward()
            optimizer.step()
            
            # Statistics
            train_loss += loss.item()
            predicted = (outputs > 0.5).float()
            total += targets.size(0)
            correct += (predicted == targets).sum().item()
        
        train_loss = train_loss / len(train_loader)
        train_acc = correct / total
        
        # Validation phase
        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                
                # Forward pass
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                
                # Statistics
                val_loss += loss.item()
                predicted = (outputs > 0.5).float()
                total += targets.size(0)
                correct += (predicted == targets).sum().item()
        
        val_loss = val_loss / len(val_loader)
        val_acc = correct / total
        
        # Log metrics
        logger.info(f"Epoch {epoch+1}/{args.epochs} - "
                   f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}, "
                   f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")
        
        # Write to TensorBoard
        writer.add_scalar('Loss/train', train_loss, epoch)
        writer.add_scalar('Loss/validation', val_loss, epoch)
        writer.add_scalar('Accuracy/train', train_acc, epoch)
        writer.add_scalar('Accuracy/validation', val_acc, epoch)
        
        # Save checkpoint
        is_best = val_loss < best_val_loss
        best_val_loss = min(val_loss, best_val_loss)
        
        checkpoint = {
            'epoch': epoch + 1,
            'state_dict': model.state_dict(),
            'optimizer': optimizer.state_dict(),
            'best_val_loss': best_val_loss,
            'train_loss': train_loss,
            'train_acc': train_acc,
            'val_loss': val_loss,
            'val_acc': val_acc
        }
        
        # Save regular checkpoint
        checkpoint_path = os.path.join(args.checkpoint_dir, f"checkpoint_epoch_{epoch+1}.pt")
        torch.save(checkpoint, checkpoint_path)
        
        # Save best checkpoint
        if is_best:
            best_model_path = os.path.join(args.checkpoint_dir, "best_model.pt")
            torch.save(checkpoint, best_model_path)
        
        # Write metrics to a file that can be consumed by the MCP server
        metrics = {
            'current_epoch': epoch + 1,
            'total_epochs': args.epochs,
            'progress_percentage': (epoch + 1) / args.epochs * 100,
            'training_loss': train_loss,
            'validation_loss': val_loss,
            'training_accuracy': train_acc,
            'validation_accuracy': val_acc,
            'learning_rate': args.learning_rate
        }
        
        with open(os.path.join(args.output_dir, "metrics.json"), 'w') as f:
            json.dump(metrics, f)
    
    logger.info("Training complete!")
    writer.close()

def main():
    parser = argparse.ArgumentParser(description="Simple training script")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--learning-rate", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--train-samples", type=int, default=1000, help="Number of training samples")
    parser.add_argument("--val-samples", type=int, default=200, help="Number of validation samples")
    parser.add_argument("--workers", type=int, default=2, help="Number of data loader workers")
    parser.add_argument("--model-path", type=str, default=None, help="Path to pre-trained model")
    parser.add_argument("--output-dir", type=str, default="./output", help="Output directory")
    parser.add_argument("--checkpoint-dir", type=str, default="./checkpoints", help="Checkpoint directory")
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Start training
    train(args)

if __name__ == "__main__":
    main()
"""
    
    # Write the script to a file
    script_path = os.path.join(temp_dir, "train.py")
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make the script executable
    os.chmod(script_path, 0o755)
    
    logger.info(f"Created training script at: {script_path}")
    return script_path

def create_mock_dataset() -> Dict[str, Any]:
    """Create a mock dataset for training."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Create train data
    train_data = np.random.randn(1000, 10).astype(np.float32)
    train_labels = (np.random.rand(1000) > 0.5).astype(np.float32).reshape(-1, 1)
    
    # Create validation data
    val_data = np.random.randn(200, 10).astype(np.float32)
    val_labels = (np.random.rand(200) > 0.5).astype(np.float32).reshape(-1, 1)
    
    # Create test data
    test_data = np.random.randn(200, 10).astype(np.float32)
    test_labels = (np.random.rand(200) > 0.5).astype(np.float32).reshape(-1, 1)
    
    # Save data to files
    if HAS_NUMPY:
        train_path = os.path.join(temp_dir, "train_data.npz")
        val_path = os.path.join(temp_dir, "val_data.npz")
        test_path = os.path.join(temp_dir, "test_data.npz")
        
        np.savez(train_path, data=train_data, labels=train_labels)
        np.savez(val_path, data=val_data, labels=val_labels)
        np.savez(test_path, data=test_data, labels=test_labels)
    else:
        # Simplified version if NumPy is not available
        train_path = os.path.join(temp_dir, "train_data.txt")
        val_path = os.path.join(temp_dir, "val_data.txt")
        test_path = os.path.join(temp_dir, "test_data.txt")
        
        with open(train_path, 'w') as f:
            f.write("Mock training data")
        
        with open(val_path, 'w') as f:
            f.write("Mock validation data")
        
        with open(test_path, 'w') as f:
            f.write("Mock test data")
    
    logger.info(f"Created mock dataset at: {temp_dir}")
    
    return {
        "directory": temp_dir,
        "train_path": train_path,
        "val_path": val_path,
        "test_path": test_path
    }

# ------------------------------------------------------------
# Example Functions
# ------------------------------------------------------------

def demonstrate_basic_job_submission(job_store: TrainingJobStore, job_runner: TrainingJobRunner):
    """Demonstrate basic training job submission and monitoring."""
    logger.info("=== Basic Training Job Submission Demonstration ===")
    
    # Create a job configuration
    model_path = create_simple_pytorch_model()
    script_path = create_training_script()
    
    if not model_path or not script_path:
        logger.warning("Could not create model or script. Skipping demonstration.")
        return
    
    # Create resource requirements
    resources = ResourceRequirements(
        cpu_cores=4,
        cpu_memory_gb=8.0,
        gpu_count=1,
        gpu_type="NVIDIA T4" if HAS_TORCH else None,
        disk_space_gb=10.0
    )
    
    # Create job configuration
    job_config = TrainingJobConfig(
        name="Simple PyTorch Training",
        description="A simple PyTorch training job for demonstration",
        job_type=TrainingJobType.SINGLE_NODE,
        framework=FrameworkType.PYTORCH,
        script_path=script_path,
        resources=resources,
        hyperparameters={
            "batch_size": 32,
            "epochs": 10,
            "learning_rate": 0.001,
            "train_samples": 1000,
            "val_samples": 200,
            "workers": 2,
            "model_path": model_path
        },
        checkpoint_strategy=CheckpointStrategy.BEST_ONLY
    )
    
    # Create the training job
    job_id = str(uuid.uuid4())
    job = TrainingJob(
        id=job_id,
        user_id="demo-user",
        config=job_config
    )
    
    # Set up a local node
    node = NodeInfo(
        id=str(uuid.uuid4()),
        hostname=socket.gethostname(),
        ip_address="127.0.0.1",
        is_chief=True,
        resources=resources
    )
    job.nodes.append(node)
    job.chief_node_id = node.id
    
    # Submit the job
    job = job_runner.submit_job(job)
    logger.info(f"Submitted job: {job.id}")
    
    # In a real scenario, the job would be picked up by the job runner
    # For demonstration, we'll manually update the job status
    job = job_store.update_job_status(job.id, TrainingStatus.INITIALIZING, "Setting up training environment")
    if not job:
        logger.error("Failed to update job status")
        return
    
    logger.info(f"Job status: {job.status} - {job.status_message}")
    
    # Simulate job start
    time.sleep(1)
    job = job_store.update_job_status(job.id, TrainingStatus.RUNNING, "Training in progress")
    logger.info(f"Job status: {job.status} - {job.status_message}")
    
    # Simulate training progress updates
    for epoch in range(10):
        # Update metrics
        metrics = {
            "current_epoch": epoch + 1,
            "total_epochs": 10,
            "progress_percentage": (epoch + 1) / 10 * 100,
            "training_loss": 0.5 - 0.04 * epoch,
            "validation_loss": 0.6 - 0.05 * epoch,
            "training_accuracy": 0.7 + 0.02 * epoch,
            "validation_accuracy": 0.65 + 0.02 * epoch,
            "learning_rate": 0.001,
            "epoch_duration_seconds": 2.5,
            "time_remaining_seconds": (10 - epoch - 1) * 2.5
        }
        
        job = job_store.update_job_metrics(job.id, metrics)
        
        # Add a checkpoint every few epochs
        if (epoch + 1) % 3 == 0 or epoch == 9:
            checkpoint = Checkpoint(
                id=str(uuid.uuid4()),
                job_id=job.id,
                path=f"checkpoints/checkpoint_epoch_{epoch+1}.pt",
                epoch=epoch + 1,
                metrics={
                    "loss": metrics["validation_loss"],
                    "accuracy": metrics["validation_accuracy"]
                },
                is_best=epoch == 9  # Last checkpoint is best for this demo
            )
            
            job = job_store.add_job_checkpoint(job.id, checkpoint)
            logger.info(f"Added checkpoint for epoch {epoch+1}")
        
        logger.info(f"Epoch {epoch+1}/10 - "
                  f"Train Loss: {metrics['training_loss']:.4f}, "
                  f"Val Loss: {metrics['validation_loss']:.4f}, "
                  f"Progress: {metrics['progress_percentage']:.1f}%")
        
        time.sleep(0.5)  # Simulate time passing between epochs
    
    # Job completed
    job = job_store.update_job_status(job.id, TrainingStatus.COMPLETED, "Training completed successfully")
    logger.info(f"Job status: {job.status} - {job.status_message}")
    
    # Get the final metrics
    logger.info("Final training metrics:")
    for key, value in job.metrics.to_dict().items():
        if value is not None and key != "custom_metrics":
            logger.info(f"  {key}: {value}")
    
    # Get the best checkpoint
    best_checkpoint = job.get_best_checkpoint()
    if best_checkpoint:
        logger.info(f"Best checkpoint: {best_checkpoint.path} (Epoch {best_checkpoint.epoch})")
        for metric_name, metric_value in best_checkpoint.metrics.items():
            logger.info(f"  {metric_name}: {metric_value:.4f}")
    
    logger.info("Basic job submission demonstration completed!")
    return job.id

def demonstrate_hyperparameter_tuning(job_store: TrainingJobStore, job_runner: TrainingJobRunner):
    """Demonstrate hyperparameter tuning with Ray Tune."""
    if not HAS_RAY:
        logger.warning("Ray not available. Skipping hyperparameter tuning demonstration.")
        return
    
    logger.info("\n=== Hyperparameter Tuning Demonstration ===")
    
    # Create a job configuration
    script_path = create_training_script()
    
    if not script_path:
        logger.warning("Could not create script. Skipping demonstration.")
        return
    
    # Create hyperparameter configuration
    hp_config = HyperparameterConfig(
        param_space={
            "batch_size": [16, 32, 64],
            "learning_rate": [0.0001, 0.001, 0.01],
            "epochs": 5  # Fixed for faster tuning
        },
        strategy=OptimizationStrategy.GRID_SEARCH,
        metric_name="val_loss",
        mode="min",
        num_trials=9,  # All combinations
        max_concurrent_trials=3
    )
    
    # Create job configuration
    job_config = TrainingJobConfig(
        name="PyTorch Hyperparameter Tuning",
        description="Grid search for optimal hyperparameters",
        job_type=TrainingJobType.HYPERPARAMETER_TUNING,
        framework=FrameworkType.PYTORCH,
        script_path=script_path,
        resources=ResourceRequirements(
            cpu_cores=4,
            cpu_memory_gb=8.0,
            gpu_count=1 if HAS_TORCH else 0
        ),
        hyperparameter_tuning=hp_config
    )
    
    # Create the training job
    job_id = str(uuid.uuid4())
    job = TrainingJob(
        id=job_id,
        user_id="demo-user",
        config=job_config
    )
    
    # Submit the job
    job = job_runner.submit_job(job)
    logger.info(f"Submitted hyperparameter tuning job: {job.id}")
    
    # Simulate job status updates
    job = job_store.update_job_status(job.id, TrainingStatus.INITIALIZING, "Setting up Ray Tune")
    time.sleep(1)
    job = job_store.update_job_status(job.id, TrainingStatus.RUNNING, "Running hyperparameter search")
    
    # Simulate tuning progress
    for trial in range(9):
        # Determine hyperparameters for this trial
        batch_size = [16, 32, 64][trial % 3]
        lr = [0.0001, 0.001, 0.01][trial // 3]
        
        logger.info(f"Trial {trial+1}/9 - batch_size={batch_size}, learning_rate={lr}")
        
        # Simulate model training with these hyperparameters
        val_loss = 0.5 - 0.1 * (np.log10(lr) + 7) - 0.05 * (np.log2(batch_size) - 4)
        val_loss += np.random.normal(0, 0.02)  # Add some noise
        
        # Update metrics
        metrics = {
            "current_trial": trial + 1,
            "total_trials": 9,
            "progress_percentage": (trial + 1) / 9 * 100,
            "custom_metrics": {
                f"trial_{trial+1}_batch_size": batch_size,
                f"trial_{trial+1}_learning_rate": lr,
                f"trial_{trial+1}_val_loss": val_loss,
            }
        }
        
        job = job_store.update_job_metrics(job.id, metrics)
        time.sleep(0.5)
    
    # Simulate completion and best hyperparameters
    best_hyperparams = {
        "batch_size": 32,
        "learning_rate": 0.001,
        "epochs": 5
    }
    
    # Update job with best hyperparameters
    job = job_store.get_job(job.id)
    job.best_hyperparameters = best_hyperparams
    job.tuning_results = {
        "best_val_loss": 0.35,
        "best_trial": 4,
        "num_trials_completed": 9
    }
    job_store.save_job(job)
    
    # Job completed
    job = job_store.update_job_status(job.id, TrainingStatus.COMPLETED, "Hyperparameter search completed")
    logger.info(f"Job status: {job.status} - {job.status_message}")
    
    # Show best hyperparameters
    logger.info("Best hyperparameters found:")
    for param, value in job.best_hyperparameters.items():
        logger.info(f"  {param}: {value}")
    
    logger.info("Hyperparameter tuning demonstration completed!")
    return job.id

def demonstrate_distributed_training(job_store: TrainingJobStore, job_runner: TrainingJobRunner):
    """Demonstrate multi-node distributed training."""
    if not HAS_TORCH:
        logger.warning("PyTorch not available. Skipping distributed training demonstration.")
        return
    
    logger.info("\n=== Multi-node Distributed Training Demonstration ===")
    
    # Create a job configuration for multi-node PyTorch training
    script_path = create_training_script()
    
    if not script_path:
        logger.warning("Could not create script. Skipping demonstration.")
        return
    
    # Create job configuration
    job_config = TrainingJobConfig(
        name="Distributed PyTorch Training",
        description="Training across multiple nodes using PyTorch DDP",
        job_type=TrainingJobType.DISTRIBUTED_DATA_PARALLEL,
        framework=FrameworkType.PYTORCH,
        script_path=script_path,
        hyperparameters={
            "batch_size": 32,
            "epochs": 10,
            "learning_rate": 0.001
        },
        resources=ResourceRequirements(
            cpu_cores=4,
            cpu_memory_gb=8.0,
            gpu_count=1
        ),
        node_count=4,
        distributed_strategy="ddp",
        communication_backend="nccl"
    )
    
    # Create the training job
    job_id = str(uuid.uuid4())
    job = TrainingJob(
        id=job_id,
        user_id="demo-user",
        config=job_config
    )
    
    # Set up nodes
    for i in range(4):
        node = NodeInfo(
            id=str(uuid.uuid4()),
            hostname=f"node-{i}",
            ip_address=f"192.168.1.{i+10}",
            is_chief=(i == 0),  # First node is chief
            resources=ResourceRequirements(
                cpu_cores=4,
                cpu_memory_gb=8.0,
                gpu_count=1
            ),
            port=29500,
            rank=i,
            world_size=4
        )
        job.nodes.append(node)
        
        if i == 0:
            job.chief_node_id = node.id
    
    # Submit the job
    job = job_runner.submit_job(job)
    logger.info(f"Submitted distributed training job: {job.id}")
    
    # Simulate job status updates
    job = job_store.update_job_status(job.id, TrainingStatus.INITIALIZING, "Setting up distributed environment")
    
    # Simulate node initialization
    for i, node in enumerate(job.nodes):
        logger.info(f"Initializing node {i+1}/4: {node.hostname} (Rank {node.rank})")
        node.status = "initializing"
        node.started_at = datetime.utcnow().isoformat()
        time.sleep(0.2)
    
    job_store.save_job(job)
    time.sleep(1)
    
    # Start training
    job = job_store.update_job_status(job.id, TrainingStatus.RUNNING, "Distributed training in progress")
    
    # Update node status
    for node in job.nodes:
        node.status = "running"
        node.update_heartbeat()
    
    job_store.save_job(job)
    
    # Simulate training progress
    for epoch in range(10):
        # Different nodes may progress at slightly different rates in real scenarios
        for i, node in enumerate(job.nodes):
            node.cpu_utilization = 80 + np.random.randint(-5, 5)
            node.gpu_utilization = 90 + np.random.randint(-8, 8)
            node.memory_utilization = 70 + np.random.randint(-10, 10)
            node.update_heartbeat()
        
        # Update overall metrics
        metrics = {
            "current_epoch": epoch + 1,
            "total_epochs": 10,
            "progress_percentage": (epoch + 1) / 10 * 100,
            "training_loss": 0.5 - 0.04 * epoch,
            "validation_loss": 0.6 - 0.05 * epoch,
            "training_accuracy": 0.7 + 0.02 * epoch,
            "validation_accuracy": 0.65 + 0.02 * epoch,
            "learning_rate": 0.001
        }
        
        job = job_store.update_job_metrics(job.id, metrics)
        
        logger.info(f"Epoch {epoch+1}/10 - "
                  f"Train Loss: {metrics['training_loss']:.4f}, "
                  f"Val Loss: {metrics['validation_loss']:.4f}")
        
        time.sleep(0.5)  # Simulate time passing between epochs
    
    # Job completed
    job = job_store.update_job_status(job.id, TrainingStatus.COMPLETED, "Distributed training completed successfully")
    logger.info(f"Job status: {job.status} - {job.status_message}")
    
    logger.info("Distributed training demonstration completed!")
    return job.id


def demonstrate_model_registry_integration(job_store: TrainingJobStore,
                                          job_runner: TrainingJobRunner,
                                          model_registry: Optional[ModelRegistry] = None):
    """Demonstrate integration with model registry."""
    if not HAS_MODEL_REGISTRY or model_registry is None:
        logger.warning("Model Registry not available. Skipping demonstration.")
        return
    
    logger.info("\n=== Model Registry Integration Demonstration ===")
    
    # Create a model in the registry
    model = model_registry.create_model(
        name="Example Classification Model",
        description="Binary classification model created for demonstration",
        owner="MCP Team",
        task_type="binary_classification",
        tags=["demo", "pytorch", "binary_classification"]
    )
    logger.info(f"Created model in registry: {model.id} - {model.name}")
    
    # Submit a training job
    model_path = create_simple_pytorch_model()
    script_path = create_training_script()
    
    if not model_path or not script_path:
        logger.warning("Could not create model or script. Skipping demonstration.")
        return
    
    # Create job configuration
    job_config = TrainingJobConfig(
        name=f"Training for {model.name}",
        description="Training job linked to model registry",
        job_type=TrainingJobType.SINGLE_NODE,
        framework=FrameworkType.PYTORCH,
        script_path=script_path,
        resources=ResourceRequirements(
            cpu_cores=4,
            cpu_memory_gb=8.0,
            gpu_count=1 if HAS_TORCH else 0
        ),
        hyperparameters={
            "batch_size": 32,
            "epochs": 10,
            "learning_rate": 0.001
        },
        model_registry_id=model.id
    )
    
    # Create the training job
    job_id = str(uuid.uuid4())
    job = TrainingJob(
        id=job_id,
        user_id="demo-user",
        config=job_config
    )
    
    # Submit the job
    job = job_runner.submit_job(job)
    logger.info(f"Submitted job: {job.id} (linked to model {model.id})")
    
    # Simulate training progress
    job = job_store.update_job_status(job.id, TrainingStatus.INITIALIZING, "Initializing")
    time.sleep(0.5)
    job = job_store.update_job_status(job.id, TrainingStatus.RUNNING, "Training in progress")
    
    # Simulate a few epochs of training
    for epoch in range(5):
        metrics = {
            "current_epoch": epoch + 1,
            "total_epochs": 5,
            "progress_percentage": (epoch + 1) / 5 * 100,
            "training_loss": 0.5 - 0.08 * epoch,
            "validation_loss": 0.6 - 0.09 * epoch,
            "training_accuracy": 0.7 + 0.05 * epoch,
            "validation_accuracy": 0.65 + 0.05 * epoch
        }
        
        job = job_store.update_job_metrics(job.id, metrics)
        time.sleep(0.3)
    
    # Job completed
    job = job_store.update_job_status(job.id, TrainingStatus.COMPLETED, "Training completed successfully")
    
    # Create a model version in the registry based on the training job
    model_version = model_registry.create_model_version(
        model_id=model.id,
        version="v1",
        name="Initial version",
        description=f"Trained with job {job.id}",
        framework=ModelFramework.PYTORCH
    )
    
    # Update the model version with metrics from the training job
    model_version = model_registry.update_model_version(
        model_id=model.id,
        version_id=model_version.id,
        metrics={
            "accuracy": job.metrics.validation_accuracy,
            "loss": job.metrics.validation_loss
        },
        metadata={
            "training_job_id": job.id,
            "trained_by": job.user_id,
            "training_duration": job.duration_seconds
        }
    )
    
    logger.info(f"Created model version: {model_version.id} - {model_version.version}")
    logger.info(f"  Metrics: accuracy={model_version.metrics.accuracy:.4f}, loss={model_version.metrics.loss:.4f}")
    
    logger.info("Model registry integration demonstration completed!")
    return model.id


def main():
    """Run the distributed training examples."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Distributed Training Examples")
    parser.add_argument("--ray", action="store_true", help="Run hyperparameter tuning example with Ray")
    parser.add_argument("--torch-dist", action="store_true", help="Run distributed training example with PyTorch")
    args = parser.parse_args()
    
    # Create in-memory job store
    job_store = TrainingJobStore()
    
    # Create job runner
    job_runner = TrainingJobRunner(job_store)
    
    try:
        # Basic job submission example
        job_id = demonstrate_basic_job_submission(job_store, job_runner)
        
        # Hyperparameter tuning example
        if args.ray and HAS_RAY:
            hp_job_id = demonstrate_hyperparameter_tuning(job_store, job_runner)
        
        # Distributed training example
        if args.torch_dist and HAS_TORCH:
            dist_job_id = demonstrate_distributed_training(job_store, job_runner)
        
        # Model registry integration example
        if HAS_MODEL_REGISTRY:
            try:
                from ipfs_kit_py.mcp.ai.model_registry import (
                    ModelRegistry,
                    JSONFileMetadataStore,
                    FileSystemModelStorage
                )
                
                # Create a model registry with in-memory storage
                base_dir = tempfile.mkdtemp()
                metadata_store = JSONFileMetadataStore(os.path.join(base_dir, "metadata"))
                model_storage = FileSystemModelStorage(os.path.join(base_dir, "storage"))
                model_registry = ModelRegistry(metadata_store, model_storage)
                
                demonstrate_model_registry_integration(job_store, job_runner, model_registry)
            except ImportError:
                logger.warning("Could not import model registry components. Skipping registry integration demo.")
        
        logger.info("\nAll distributed training examples completed!")
    
    except Exception as e:
        logger.error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    import socket  # Required for hostname in NodeInfo
    sys.exit(main())
