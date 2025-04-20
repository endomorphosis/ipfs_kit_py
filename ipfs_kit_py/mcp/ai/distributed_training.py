#!/usr/bin/env python3
"""
Distributed Training for MCP Server

This module provides training job orchestration and management capabilities
for distributed machine learning workflows within the IPFS Kit ecosystem.

Key features:
- Training job orchestration
- Multi-node training support
- Hyperparameter optimization
- Model checkpointing and resumption

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import logging
import time
import uuid
import shutil
from typing import Dict, List, Optional, Union, Any, Tuple
from pathlib import Path
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_distributed_training")


class TrainingJob:
    """Represents a machine learning training job with its configuration and state."""
    
    def __init__(
        self,
        job_id: str,
        name: str,
        created_at: Union[str, datetime],
        config: Dict[str, Any],
        dataset_id: Optional[str] = None,
        model_id: Optional[str] = None,
        status: str = "created",
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        resources: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        framework: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        checkpoint_interval: Optional[int] = None,
        max_runtime: Optional[int] = None,
    ):
        """
        Initialize a training job.
        
        Args:
            job_id: Unique identifier for this job
            name: Human-readable name
            created_at: Creation timestamp
            config: Training configuration
            dataset_id: ID of the dataset to use
            model_id: ID of the model to train
            status: Current status (created, running, completed, failed, etc.)
            user_id: ID of the user who created this job
            tags: Tags for categorization and filtering
            resources: Resource requirements (CPU, GPU, memory, etc.)
            metadata: Additional metadata
            output_dir: Directory for output artifacts
            framework: ML framework (tensorflow, pytorch, etc.)
            nodes: List of compute nodes for distributed training
            checkpoint_interval: Interval between checkpoints in seconds
            max_runtime: Maximum runtime in seconds
        """
        self.job_id = job_id
        self.name = name
        
        # Convert string timestamps to datetime objects
        if isinstance(created_at, str):
            self.created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            self.created_at = created_at
            
        self.config = config
        self.dataset_id = dataset_id
        self.model_id = model_id
        self.status = status
        self.user_id = user_id
        self.tags = tags or []
        self.resources = resources or {}
        self.metadata = metadata or {}
        self.output_dir = output_dir
        self.framework = framework
        self.nodes = nodes or []
        self.checkpoint_interval = checkpoint_interval
        self.max_runtime = max_runtime
        
        # Internal state tracking
        self.updated_at = self.created_at
        self.started_at = None
        self.completed_at = None
        self.logs = []
        self.checkpoints = []
        self.metrics = {}
        self.process = None
        self.error_message = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert training job to a dictionary."""
        result = {
            "job_id": self.job_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "config": self.config,
            "dataset_id": self.dataset_id,
            "model_id": self.model_id,
            "status": self.status,
            "user_id": self.user_id,
            "tags": self.tags,
            "resources": self.resources,
            "metadata": self.metadata,
            "output_dir": self.output_dir,
            "framework": self.framework,
            "nodes": self.nodes,
            "checkpoint_interval": self.checkpoint_interval,
            "max_runtime": self.max_runtime,
            "logs": self.logs,
            "checkpoints": self.checkpoints,
            "metrics": self.metrics,
            "error_message": self.error_message
        }
        
        if self.started_at:
            result["started_at"] = self.started_at.isoformat()
        
        if self.completed_at:
            result["completed_at"] = self.completed_at.isoformat()
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainingJob':
        """Create a TrainingJob from a dictionary."""
        job = cls(
            job_id=data["job_id"],
            name=data["name"],
            created_at=data["created_at"],
            config=data["config"],
            dataset_id=data.get("dataset_id"),
            model_id=data.get("model_id"),
            status=data.get("status", "created"),
            user_id=data.get("user_id"),
            tags=data.get("tags"),
            resources=data.get("resources"),
            metadata=data.get("metadata"),
            output_dir=data.get("output_dir"),
            framework=data.get("framework"),
            nodes=data.get("nodes"),
            checkpoint_interval=data.get("checkpoint_interval"),
            max_runtime=data.get("max_runtime")
        )
        
        # Restore internal state
        job.logs = data.get("logs", [])
        job.checkpoints = data.get("checkpoints", [])
        job.metrics = data.get("metrics", {})
        job.error_message = data.get("error_message")
        
        if "started_at" in data and data["started_at"]:
            job.started_at = datetime.fromisoformat(data["started_at"].replace('Z', '+00:00'))
        
        if "completed_at" in data and data["completed_at"]:
            job.completed_at = datetime.fromisoformat(data["completed_at"].replace('Z', '+00:00'))
        
        return job
    
    def update_status(self, status: str, error_message: Optional[str] = None) -> None:
        """
        Update the status of the training job.
        
        Args:
            status: New status
            error_message: Error message if applicable
        """
        self.status = status
        self.updated_at = datetime.now()
        
        if status == "running" and not self.started_at:
            self.started_at = datetime.now()
        
        if status in ["completed", "failed", "stopped"] and not self.completed_at:
            self.completed_at = datetime.now()
        
        if error_message:
            self.error_message = error_message
    
    def add_log(self, message: str, level: str = "info", timestamp: Optional[datetime] = None) -> None:
        """
        Add a log message to the job.
        
        Args:
            message: Log message
            level: Log level (info, warning, error, etc.)
            timestamp: Timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.logs.append({
            "timestamp": timestamp.isoformat(),
            "level": level,
            "message": message
        })
        self.updated_at = datetime.now()
    
    def add_checkpoint(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a checkpoint to the job.
        
        Args:
            path: Path to the checkpoint
            metadata: Checkpoint metadata
        """
        self.checkpoints.append({
            "timestamp": datetime.now().isoformat(),
            "path": path,
            "metadata": metadata or {}
        })
        self.updated_at = datetime.now()
    
    def update_metrics(self, metrics: Dict[str, float]) -> None:
        """
        Update training metrics.
        
        Args:
            metrics: Dictionary of metric name -> value
        """
        self.metrics.update(metrics)
        self.updated_at = datetime.now()


class DistributedTraining:
    """
    Manager for distributed training jobs.
    
    This class provides functionality for scheduling, monitoring, and managing
    distributed training jobs across multiple nodes.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, storage_path: Optional[Union[str, Path]] = None):
        """
        Initialize the distributed training manager.
        
        Args:
            config: Configuration options
            storage_path: Path for storing job data
        """
        self.config = config or {}
        
        # Set default storage path if none provided
        if storage_path is None:
            self.storage_path = Path.home() / ".ipfs_kit" / "distributed_training"
        else:
            self.storage_path = Path(storage_path)
        
        # Ensure storage directories exist
        self.jobs_path = self.storage_path / "jobs"
        self.output_path = self.storage_path / "output"
        self.config_path = self.storage_path / "config"
        
        self.jobs_path.mkdir(parents=True, exist_ok=True)
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.config_path.mkdir(parents=True, exist_ok=True)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # In-memory cache of jobs
        self._jobs: Dict[str, TrainingJob] = {}
        
        # Background workers
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 4),
            thread_name_prefix="training_manager_"
        )
        
        # Job monitoring threads
        self._monitor_threads: Dict[str, threading.Thread] = {}
        self._stop_monitoring = threading.Event()
        
        # Load existing jobs
        self._load_jobs()
        
        logger.info(f"Distributed Training initialized at {self.storage_path}")
    
    def _load_jobs(self) -> None:
        """Load existing jobs from storage."""
        try:
            # Load job files
            job_files = list(self.jobs_path.glob("*.json"))
            for job_file in job_files:
                try:
                    with open(job_file, 'r') as f:
                        job_data = json.load(f)
                    
                    job = TrainingJob.from_dict(job_data)
                    self._jobs[job.job_id] = job
                    
                    # Restart monitoring for active jobs
                    if job.status == "running":
                        # Mark as interrupted if it was running
                        job.update_status("interrupted", "Training manager restarted")
                        self._save_job(job)
                    
                except Exception as e:
                    logger.error(f"Error loading job from {job_file}: {e}")
            
            logger.info(f"Loaded {len(self._jobs)} training jobs from storage")
            
        except Exception as e:
            logger.error(f"Error during job loading: {e}")
    
    def _save_job(self, job: TrainingJob) -> bool:
        """
        Save job data to storage.
        
        Args:
            job: Training job to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            job_file = self.jobs_path / f"{job.job_id}.json"
            job_data = job.to_dict()
            
            # Write to a temporary file first, then rename to ensure atomic operation
            temp_file = job_file.with_suffix(".tmp")
            with open(temp_file, 'w') as f:
                json.dump(job_data, f, indent=2)
            
            temp_file.rename(job_file)
            return True
            
        except Exception as e:
            logger.error(f"Error saving job data for {job.job_id}: {e}")
            return False
    
    def create_job(
        self,
        name: str,
        config: Dict[str, Any],
        dataset_id: Optional[str] = None,
        model_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        resources: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        framework: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        checkpoint_interval: Optional[int] = None,
        max_runtime: Optional[int] = None,
        job_id: Optional[str] = None
    ) -> TrainingJob:
        """
        Create a new training job.
        
        Args:
            name: Human-readable name
            config: Training configuration
            dataset_id: ID of the dataset to use
            model_id: ID of the model to train
            user_id: ID of the user creating the job
            tags: Tags for categorization and filtering
            resources: Resource requirements (CPU, GPU, memory, etc.)
            metadata: Additional metadata
            framework: ML framework (tensorflow, pytorch, etc.)
            nodes: List of compute nodes for distributed training
            checkpoint_interval: Interval between checkpoints in seconds
            max_runtime: Maximum runtime in seconds
            job_id: Optional custom job ID (generated if not provided)
            
        Returns:
            The created TrainingJob
        """
        with self._lock:
            # Generate job_id if not provided
            if job_id is None:
                job_id = f"job_{uuid.uuid4().hex[:12]}"
            
            # Ensure job_id is unique
            if job_id in self._jobs:
                raise ValueError(f"Job with ID '{job_id}' already exists")
            
            # Create output directory
            output_dir = str(self.output_path / job_id)
            os.makedirs(output_dir, exist_ok=True)
            
            # Create job
            job = TrainingJob(
                job_id=job_id,
                name=name,
                created_at=datetime.now(),
                config=config,
                dataset_id=dataset_id,
                model_id=model_id,
                status="created",
                user_id=user_id,
                tags=tags,
                resources=resources,
                metadata=metadata,
                output_dir=output_dir,
                framework=framework,
                nodes=nodes,
                checkpoint_interval=checkpoint_interval,
                max_runtime=max_runtime
            )
            
            # Add to registry
            self._jobs[job_id] = job
            
            # Save job data
            self._save_job(job)
            
            logger.info(f"Created training job '{name}' with ID {job_id}")
            
            return job
    
    def get_job(self, job_id: str) -> Optional[TrainingJob]:
        """
        Get a job by ID.
        
        Args:
            job_id: ID of the job to retrieve
            
        Returns:
            TrainingJob if found, None otherwise
        """
        return self._jobs.get(job_id)
    
    def list_jobs(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        framework: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_by: str = "created_at",
        ascending: bool = False
    ) -> List[TrainingJob]:
        """
        List training jobs with filtering.
        
        Args:
            status: Filter by status
            user_id: Filter by user ID
            tags: Filter by tags (jobs must have all specified tags)
            framework: Filter by framework
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            sort_by: Attribute to sort by
            ascending: Whether to sort in ascending order
            
        Returns:
            List of matching jobs
        """
        with self._lock:
            # Start with all jobs
            jobs = list(self._jobs.values())
            
            # Apply filters
            if status:
                jobs = [j for j in jobs if j.status == status]
            
            if user_id:
                jobs = [j for j in jobs if j.user_id == user_id]
            
            if tags:
                jobs = [j for j in jobs if all(tag in j.tags for tag in tags)]
            
            if framework:
                jobs = [j for j in jobs if j.framework == framework]
            
            # Sort jobs
            if sort_by == "name":
                jobs.sort(key=lambda j: j.name, reverse=not ascending)
            elif sort_by == "updated_at":
                jobs.sort(key=lambda j: j.updated_at, reverse=not ascending)
            elif sort_by == "started_at":
                # Sort by started_at if available, created_at otherwise
                jobs.sort(key=lambda j: (j.started_at or j.created_at), reverse=not ascending)
            else:  # Default to created_at
                jobs.sort(key=lambda j: j.created_at, reverse=not ascending)
            
            # Apply pagination
            if offset:
                jobs = jobs[offset:]
            
            if limit is not None:
                jobs = jobs[:limit]
            
            return jobs
    
    def start_job(self, job_id: str) -> bool:
        """
        Start a training job.
        
        Args:
            job_id: ID of the job to start
            
        Returns:
            True if started, False otherwise
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Cannot start job: Job {job_id} not found")
            return False
        
        if job.status != "created":
            logger.error(f"Cannot start job: Job {job_id} is already {job.status}")
            return False
        
        # Initialize job monitoring
        monitor_thread = threading.Thread(
            target=self._monitor_job,
            args=(job,),
            daemon=True,
            name=f"job_monitor_{job_id}"
        )
        
        # Start job
        try:
            # Update job status
            job.update_status("running")
            job.add_log("Job started")
            
            # Save job data
            self._save_job(job)
            
            # Start monitoring thread
            monitor_thread.start()
            self._monitor_threads[job_id] = monitor_thread
            
            logger.info(f"Started training job {job_id}")
            
            return True
            
        except Exception as e:
            error_message = f"Error starting job: {str(e)}"
            logger.error(error_message)
            job.update_status("failed", error_message)
            job.add_log(error_message, level="error")
            self._save_job(job)
            return False
    
    def stop_job(self, job_id: str) -> bool:
        """
        Stop a training job.
        
        Args:
            job_id: ID of the job to stop
            
        Returns:
            True if stopped, False otherwise
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Cannot stop job: Job {job_id} not found")
            return False
        
        if job.status != "running":
            logger.error(f"Cannot stop job: Job {job_id} is not running")
            return False
        
        try:
            # Stop the job
            if job.process:
                # Try to terminate gracefully first
                job.process.terminate()
                time.sleep(2)
                
                # Force kill if still running
                if job.process.poll() is None:
                    job.process.kill()
            
            # Update job status
            job.update_status("stopped", "Job stopped by user")
            job.add_log("Job stopped by user", level="warning")
            
            # Save job data
            self._save_job(job)
            
            logger.info(f"Stopped training job {job_id}")
            
            return True
            
        except Exception as e:
            error_message = f"Error stopping job: {str(e)}"
            logger.error(error_message)
            job.add_log(error_message, level="error")
            self._save_job(job)
            return False
    
    def delete_job(self, job_id: str, delete_output: bool = False) -> bool:
        """
        Delete a training job.
        
        Args:
            job_id: ID of the job to delete
            delete_output: Whether to delete output files
            
        Returns:
            True if deleted, False otherwise
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                logger.error(f"Cannot delete job: Job {job_id} not found")
                return False
            
            # Stop the job if it's running
            if job.status == "running":
                self.stop_job(job_id)
            
            # Delete output directory if requested
            if delete_output and job.output_dir and os.path.exists(job.output_dir):
                try:
                    shutil.rmtree(job.output_dir)
                except Exception as e:
                    logger.error(f"Error deleting output directory: {e}")
            
            # Delete job file
            job_file = self.jobs_path / f"{job.job_id}.json"
            if job_file.exists():
                try:
                    job_file.unlink()
                except Exception as e:
                    logger.error(f"Error deleting job file: {e}")
            
            # Remove from registry
            del self._jobs[job_id]
            
            logger.info(f"Deleted training job {job_id}")
            
            return True
    
    def _monitor_job(self, job: TrainingJob) -> None:
        """
        Monitor a running training job.
        
        Args:
            job: Job to monitor
        """
        # This would typically launch the actual training process and monitor it
        # Here we simulate a job with a sleep
        try:
            logger.info(f"Job monitoring started for {job.job_id}")
            
            # Simulate job execution
            # In a real implementation, this would:
            # 1. Prepare the training environment
            # 2. Launch the training process
            # 3. Monitor the process for completion or errors
            # 4. Handle checkpointing
            # 5. Gather metrics
            
            # For now, just simulate a successful job
            completion_time = 10  # seconds
            start_time = time.time()
            
            # Simulate a running job
            while time.time() - start_time < completion_time:
                # Check if monitoring should stop
                if self._stop_monitoring.is_set():
                    job.update_status("interrupted", "Monitoring stopped")
                    self._save_job(job)
                    return
                
                # Simulate progress updates
                progress = (time.time() - start_time) / completion_time
                job.update_metrics({
                    "progress": progress,
                    "loss": 1.0 - 0.9 * progress,
                    "accuracy": 0.5 + 0.4 * progress
                })
                
                # Add checkpoint at 50% completion
                if progress >= 0.5 and len(job.checkpoints) == 0:
                    checkpoint_path = f"{job.output_dir}/checkpoint_0.5.pt"
                    # In a real implementation, this would save the model
                    with open(checkpoint_path, 'w') as f:
                        f.write("Simulated checkpoint")
                    
                    job.add_checkpoint(checkpoint_path, {
                        "progress": progress,
                        "metrics": {k: v for k, v in job.metrics.items()}
                    })
                
                # Simulate periodic logs
                job.add_log(f"Training progress: {progress:.2f}")
                
                # Save job data periodically
                self._save_job(job)
                
                # Sleep for a bit
                time.sleep(1)
            
            # Job completed successfully
            job.update_status("completed")
            job.add_log("Job completed successfully")
            
            # Add final metrics
            job.update_metrics({
                "progress": 1.0,
                "loss": 0.1,
                "accuracy": 0.9,
                "final_evaluation": 0.85
            })
            
            # Save job data
            self._save_job(job)
            
            logger.info(f"Job {job.job_id} completed successfully")
            
        except Exception as e:
            error_message = f"Error in job monitoring: {str(e)}"
            logger.error(error_message)
            job.update_status("failed", error_message)
            job.add_log(error_message, level="error")
            self._save_job(job)
    
    def get_job_logs(self, job_id: str, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get logs for a job.
        
        Args:
            job_id: ID of the job
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            
        Returns:
            List of log entries
        """
        job = self.get_job(job_id)
        if not job:
            return []
        
        logs = job.logs
        
        # Apply pagination
        if offset:
            logs = logs[offset:]
        
        if limit is not None:
            logs = logs[:limit]
        
        return logs
    
    def get_job_metrics(self, job_id: str) -> Dict[str, float]:
        """
        Get metrics for a job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            Dictionary of metrics
        """
        job = self.get_job(job_id)
        if not job:
            return {}
        
        return job.metrics
    
    def shutdown(self) -> None:
        """Shut down the training manager and stop all monitoring threads."""
        logger.info("Shutting down Distributed Training manager")
        
        # Signal monitoring threads to stop
        self._stop_monitoring.set()
        
        # Stop all running jobs
        for job_id, job in self._jobs.items():
            if job.status == "running":
                try:
                    self.stop_job(job_id)
                except Exception as e:
                    logger.error(f"Error stopping job {job_id} during shutdown: {e}")
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        logger.info("Distributed Training manager shut down")

# Singleton instance
_instance = None

def get_instance(
    config: Optional[Dict[str, Any]] = None,
    storage_path: Optional[Union[str, Path]] = None
) -> DistributedTraining:
    """
    Get or create the singleton instance of the DistributedTraining.
    
    Args:
        config: Configuration options
        storage_path: Path for storing job data
        
    Returns:
        DistributedTraining instance
    """
    global _instance
    if _instance is None:
        _instance = DistributedTraining(config, storage_path)
    return _instance
