#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Example script demonstrating how to use the AI/ML visualization capabilities
of IPFS Kit.

This example:
1. Creates a sample metrics dataset
2. Initializes the visualization module
3. Generates various visualization types
4. Creates a comprehensive dashboard
5. Exports visualizations to multiple formats
6. Generates an HTML report
"""

import os
import time
import random
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Import IPFS Kit components
from ipfs_kit_py.ai_ml_metrics import AIMLMetricsCollector
from ipfs_kit_py.ai_ml_visualization import create_visualization, AIMLVisualization

def generate_sample_metrics():
    """Generate sample AI/ML metrics for demonstration purposes."""
    metrics = AIMLMetricsCollector()

    # Generate sample model IDs
    model_ids = ["resnet50", "bert-base", "gpt2-small"]

    # Generate training metrics
    for model_id in model_ids:
        # Simulate training epochs
        num_epochs = 10
        for epoch in range(num_epochs):
            # Generate decreasing loss curve
            base_loss = 2.0 * (1 - epoch / num_epochs)
            train_loss = base_loss + random.uniform(-0.1, 0.1)
            val_loss = base_loss * 1.2 + random.uniform(-0.2, 0.2)

            # Generate increasing accuracy curve
            base_acc = 0.5 + 0.4 * (epoch / num_epochs)
            train_acc = base_acc + random.uniform(-0.05, 0.05)
            val_acc = base_acc - 0.1 + random.uniform(-0.05, 0.05)

            # Track epoch metrics
            with metrics.track_training_epoch(model_id, epoch, 1000):
                # Simulate epoch processing time
                time.sleep(0.1)

                # Record metrics
                metrics.record_metric(f"{model_id}/epoch/{epoch}/train_loss", train_loss)
                metrics.record_metric(f"{model_id}/epoch/{epoch}/val_loss", val_loss)
                metrics.record_metric(f"{model_id}/epoch/{epoch}/train_acc", train_acc)
                metrics.record_metric(f"{model_id}/epoch/{epoch}/val_acc", val_acc)
                metrics.record_metric(f"{model_id}/epoch/{epoch}/learning_rate", 0.01 * (0.9 ** epoch))

    # Generate inference metrics
    for model_id in model_ids:
        # Simulate multiple inference batches
        for i in range(50):
            batch_size = random.choice([1, 2, 4, 8, 16])

            # Track inference metrics
            with metrics.track_inference(model_id, batch_size):
                # Simulate inference time with some randomness
                latency_base = {"resnet50": 0.02, "bert-base": 0.05, "gpt2-small": 0.08}
                time.sleep(latency_base[model_id] * batch_size / 8 + random.uniform(0, 0.01))

                # Simulate memory usage
                metrics.record_metric(f"{model_id}/inference/memory_mb",
                                     1000 + random.uniform(-50, 50))

    # Generate worker utilization metrics
    worker_ids = ["worker-1", "worker-2", "worker-3", "worker-4"]
    start_time = datetime.now() - timedelta(hours=1)

    for minute in range(60):
        timestamp = start_time + timedelta(minutes=minute)
        for worker_id in worker_ids:
            # Simulate worker utilization percentage with realistic patterns
            base_util = 0.5 + 0.3 * np.sin(minute / 10)
            utilization = min(0.95, max(0.1, base_util + random.uniform(-0.1, 0.1)))

            metrics.record_metric(f"workers/{worker_id}/utilization",
                                 utilization,
                                 timestamp=timestamp.timestamp())

            # Simulate worker memory usage
            memory_usage = 2000 + 500 * utilization + random.uniform(-100, 100)
            metrics.record_metric(f"workers/{worker_id}/memory_mb",
                                 memory_usage,
                                 timestamp=timestamp.timestamp())

            # Simulate worker task count
            task_count = int(10 * utilization) + random.randint(-2, 2)
            metrics.record_metric(f"workers/{worker_id}/active_tasks",
                                 max(0, task_count),
                                 timestamp=timestamp.timestamp())

    # Generate dataset loading metrics
    datasets = ["imagenet", "coco", "squad"]
    for dataset in datasets:
        for i in range(20):
            # Track dataset loading
            with metrics.track_dataset_loading(dataset, batch_size=32):
                # Simulate loading time with some randomness
                load_time_base = {"imagenet": 0.2, "coco": 0.15, "squad": 0.1}
                time.sleep(load_time_base[dataset] + random.uniform(0, 0.05))

    return metrics

def main():
    """Main function to demonstrate visualization capabilities."""
    print("Generating sample AI/ML metrics...")
    metrics = generate_sample_metrics()

    print("Creating visualization instance...")
    # Create visualization with both interactive and static options
    viz_interactive = create_visualization(metrics, theme="light", interactive=True)
    viz_static = create_visualization(metrics, theme="dark", interactive=False)

    # Create output directory for exports
    export_dir = Path("./ai_ml_viz_output")
    export_dir.mkdir(exist_ok=True)

    print("Generating training metrics visualizations...")
    # Generate and show training visualizations
    viz_interactive.plot_training_metrics(model_id="resnet50", show_plot=True)

    print("Generating inference latency visualizations...")
    # Generate and show inference visualizations
    viz_interactive.plot_inference_latency(model_id="bert-base", show_plot=True)

    print("Generating worker utilization visualizations...")
    # Generate and show worker visualizations
    viz_interactive.plot_worker_utilization(show_plot=True)

    print("Generating dataset loading visualizations...")
    # Generate and show dataset visualizations
    viz_interactive.plot_dataset_load_times(show_plot=True)

    print("Generating comprehensive dashboard...")
    # Generate a comprehensive dashboard
    viz_interactive.plot_comprehensive_dashboard(show_plot=True)

    print(f"Exporting visualizations to {export_dir}...")
    # Export visualizations to multiple formats
    exported_files = viz_static.export_visualizations(
        str(export_dir),
        formats=["png", "svg", "html", "json"]
    )

    # Print exported files
    for viz_type, files in exported_files.items():
        print(f"- {viz_type}:")
        for file in files:
            print(f"  - {os.path.basename(file)}")

    print("Generating HTML report...")
    # Generate an HTML report
    report_path = export_dir / "ai_ml_performance_report.html"
    html_report = viz_interactive.generate_html_report(str(report_path))
    print(f"HTML report saved to: {report_path}")

    print("\nVisualization example complete!")
    print(f"All outputs saved to: {export_dir}")

    return 0

if __name__ == "__main__":
    main()
