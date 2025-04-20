"""
Model Registry Usage Example

This script demonstrates how to use the Model Registry client to:
1. Create and manage models
2. Upload model versions
3. Track performance metrics
4. Configure deployment settings
5. Compare model versions

This example provides a practical guide for working with the Model Registry.

Usage:
    python example_model_registry.py
"""

import os
import sys
import asyncio
import json
import random
import numpy as np
import tempfile
from typing import Dict, Any

# Import the Model Registry client
from ipfs_kit_py.mcp.ai.model_registry.handler import ModelRegistryClient

# Sample model data - this would normally be a real ML model
def create_sample_model_file(size_kb=100, output_path=None):
    """Create a sample model file of the specified size."""
    if output_path is None:
        # Create a temporary file
        fd, output_path = tempfile.mkstemp(suffix='.model')
        os.close(fd)
    
    # Create random data
    data = np.random.bytes(size_kb * 1024)
    
    # Write to file
    with open(output_path, 'wb') as f:
        f.write(data)
    
    return output_path

# Sample metrics data
def generate_metrics():
    """Generate random performance metrics for demo purposes."""
    return {
        "accuracy": round(random.uniform(0.7, 0.99), 4),
        "precision": round(random.uniform(0.7, 0.99), 4),
        "recall": round(random.uniform(0.7, 0.99), 4),
        "f1_score": round(random.uniform(0.7, 0.99), 4),
        "latency_ms": round(random.uniform(5, 100), 2),
        "throughput_qps": round(random.uniform(10, 1000), 2),
        "memory_mb": round(random.uniform(50, 500), 2),
        "custom_metrics": {
            "custom_metric_1": round(random.uniform(0, 1), 4),
            "custom_metric_2": round(random.uniform(0, 1), 4)
        }
    }

# Sample deployment configuration
def generate_deployment_config():
    """Generate sample deployment configuration."""
    return {
        "min_resources": {
            "cpu": "1",
            "memory": "512Mi",
            "gpu": "0"
        },
        "max_resources": {
            "cpu": "2",
            "memory": "2Gi",
            "gpu": "1"
        },
        "scaling_policy": {
            "min_replicas": 1,
            "max_replicas": 5,
            "target_cpu_utilization": 80,
            "target_memory_utilization": 80
        },
        "environment_variables": {
            "MODEL_PRECISION": "fp16",
            "BATCH_SIZE": "32",
            "WORKERS": "2"
        },
        "serving_config": {
            "framework": "torchserve",
            "max_batch_size": 32,
            "batch_timeout_ms": 100,
            "enable_profiling": True
        }
    }

async def main():
    """Run the example workflow."""
    
    # Create a client
    client = ModelRegistryClient(api_url="http://localhost:5000")
    
    try:
        # Step 1: Create a model
        print("Creating model...")
        model = await client.create_model(
            name="Example Classification Model",
            description="A model for demonstrating the Model Registry",
            model_type="classification",
            team="Data Science",
            project="Model Registry Demo",
            metadata={
                "domain": "example",
                "architecture": "resnet",
                "input_shape": [3, 224, 224],
                "output_shape": [1000]
            },
            tags=["demo", "example", "classification"]
        )
        
        model_id = model["id"]
        print(f"Created model with ID: {model_id}")
        print(f"Model details: {json.dumps(model, indent=2)}")
        
        # Step 2: Upload initial model version
        print("\nUploading initial model version...")
        model_path = create_sample_model_file(size_kb=500)
        
        v1 = await client.upload_model_version(
            model_id=model_id,
            version="0.1.0",
            model_path=model_path,
            format="pytorch",
            description="Initial model version",
            commit_message="Initial training run",
            framework="pytorch",
            framework_version="1.9.0",
            metadata={
                "training_dataset": "example_dataset_v1",
                "epochs": 10,
                "batch_size": 32,
                "optimizer": "Adam",
                "learning_rate": 0.001
            },
            tags=["initial", "development"]
        )
        
        version1_id = v1["id"]
        print(f"Uploaded version 0.1.0 with ID: {version1_id}")
        
        # Step 3: Add metrics for the initial version
        print("\nAdding performance metrics...")
        metrics1 = generate_metrics()
        success = await client.update_metrics(
            model_id=model_id,
            version_id=version1_id,
            metrics=metrics1
        )
        
        if success:
            print(f"Added metrics to version 0.1.0:")
            print(f"Accuracy: {metrics1['accuracy']}")
            print(f"F1 Score: {metrics1['f1_score']}")
            print(f"Latency: {metrics1['latency_ms']} ms")
        
        # Step 4: Upload an improved model version
        print("\nUploading improved model version...")
        model_path2 = create_sample_model_file(size_kb=550)
        
        v2 = await client.upload_model_version(
            model_id=model_id,
            version="0.2.0",
            model_path=model_path2,
            format="pytorch",
            description="Improved model with more training",
            commit_message="Increased epochs and tuned hyperparameters",
            framework="pytorch",
            framework_version="1.9.0",
            parent_version=version1_id,
            metadata={
                "training_dataset": "example_dataset_v1",
                "epochs": 20,
                "batch_size": 64,
                "optimizer": "Adam",
                "learning_rate": 0.0005
            },
            tags=["improved", "development"]
        )
        
        version2_id = v2["id"]
        print(f"Uploaded version 0.2.0 with ID: {version2_id}")
        
        # Step 5: Add improved metrics for the second version
        print("\nAdding improved performance metrics...")
        # Make metrics slightly better than v1
        metrics2 = generate_metrics()
        metrics2["accuracy"] = round(min(metrics1["accuracy"] * 1.05, 0.99), 4)
        metrics2["f1_score"] = round(min(metrics1["f1_score"] * 1.05, 0.99), 4)
        metrics2["latency_ms"] = round(metrics1["latency_ms"] * 0.9, 2)  # Lower is better
        
        success = await client.update_metrics(
            model_id=model_id,
            version_id=version2_id,
            metrics=metrics2
        )
        
        if success:
            print(f"Added metrics to version 0.2.0:")
            print(f"Accuracy: {metrics2['accuracy']} ({(metrics2['accuracy']-metrics1['accuracy'])*100:+.2f}%)")
            print(f"F1 Score: {metrics2['f1_score']} ({(metrics2['f1_score']-metrics1['f1_score'])*100:+.2f}%)")
            print(f"Latency: {metrics2['latency_ms']} ms ({(metrics2['latency_ms']-metrics1['latency_ms']):+.2f} ms)")
        
        # Step 6: Add deployment configuration to the improved version
        print("\nAdding deployment configuration...")
        deploy_config = generate_deployment_config()
        success = await client.update_deployment_config(
            model_id=model_id,
            version_id=version2_id,
            config=deploy_config
        )
        
        if success:
            print(f"Added deployment configuration to version 0.2.0")
            print(f"Resources: CPU={deploy_config['min_resources']['cpu']}-{deploy_config['max_resources']['cpu']}, Memory={deploy_config['min_resources']['memory']}-{deploy_config['max_resources']['memory']}")
            print(f"Scaling: {deploy_config['scaling_policy']['min_replicas']}-{deploy_config['scaling_policy']['max_replicas']} replicas")
        
        # Step 7: Set the improved version as production
        print("\nSetting version 0.2.0 as production...")
        success = await client.set_production_version(model_id, version2_id)
        
        if success:
            print(f"Set version 0.2.0 as production version")
        
        # Step 8: Compare versions
        print("\nComparing model versions...")
        comparison = await client.compare_versions(version1_id, version2_id)
        
        if "metrics_comparison" in comparison:
            print("\nMetrics Comparison:")
            metrics_comp = comparison["metrics_comparison"]
            for metric, values in metrics_comp.items():
                if isinstance(values, dict) and "v1" in values and "v2" in values:
                    v1_val = values["v1"]
                    v2_val = values["v2"]
                    if isinstance(v1_val, (int, float)) and isinstance(v2_val, (int, float)):
                        diff = values.get("diff", v2_val - v1_val)
                        pct = values.get("pct_change", (diff / v1_val) * 100 if v1_val != 0 else float('inf'))
                        print(f"  {metric}: {v1_val:.4f} → {v2_val:.4f} ({pct:+.2f}%)")
        
        # Step 9: List all versions
        print("\nListing all versions:")
        versions = await client.list_versions(model_id)
        for v in versions:
            print(f"  - {v['version']} ({v['id']}): {v['status']}")
        
        # Step 10: Get the production version
        print("\nGetting production version:")
        prod_version = await client.get_production_version(model_id)
        print(f"Production version: {prod_version['version']} (ID: {prod_version['id']})")
        
        # Clean up temporary files
        try:
            os.remove(model_path)
            os.remove(model_path2)
        except:
            pass
        
        print("\nExample completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    finally:
        # Close client session
        if hasattr(client, 'session') and client.session:
            await client.session.close()

if __name__ == "__main__":
    asyncio.run(main())