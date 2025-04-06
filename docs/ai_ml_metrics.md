# AI/ML Specific Metrics Tracking

Beyond general performance monitoring, `ipfs-kit-py` provides a dedicated class, `AIMLMetrics`, within the `ai_ml_metrics.py` module for tracking metrics specifically relevant to AI/ML workflows. This allows for more granular insights into model training, inference, dataset handling, and distributed operations.

## Overview

The `AIMLMetrics` class offers context managers and methods tailored to common AI/ML stages. It collects data points like durations, counts, memory usage (if enabled), and framework-specific details, enabling detailed analysis of AI/ML pipeline performance.

**Key Features:**

*   **Targeted Tracking**: Context managers for specific operations like model loading, inference, training epochs, dataset loading, and preprocessing.
*   **Distributed Training Metrics**: Functions to track distributed tasks, worker utilization, and communication times.
*   **Comprehensive Reporting**: Methods to retrieve aggregated metrics for models, inference, training, datasets, and distributed components.
*   **Analysis & Recommendations**: Generates analysis summaries and potential optimization recommendations based on collected AI/ML metrics.
*   **Formatted Reports**: Can generate reports in Markdown or plain text.

## Implementation (`AIMLMetrics`)

*   **Initialization**: Can be initialized standalone or potentially integrated within the main `IPFSSimpleAPI` or `AIMLIntegration` classes.
*   **Context Managers**: Provides `with` statement contexts (e.g., `track_inference`, `track_training_epoch`) that automatically measure duration and potentially other system stats during the block.
*   **Manual Recording**: Methods like `record_training_stats`, `record_worker_utilization` allow manual logging of specific metrics.
*   **Data Aggregation**: Internally aggregates collected data points (latencies, counts, sizes, etc.).
*   **Retrieval Methods**: Functions like `get_model_metrics`, `get_inference_metrics`, `get_training_metrics`, `get_dataset_metrics`, `get_distributed_metrics` return structured dictionaries of aggregated statistics (average, min, max, p95, counts, etc.).
*   **Reporting**: `get_comprehensive_report` combines all metrics, analysis, and recommendations. `generate_formatted_report` creates human-readable output.

## Configuration

Configuration might occur during `AIMLMetrics` initialization or potentially via the main `ipfs-kit-py` config under an `ai_ml.metrics` key:

```python
# Example configuration snippet within main config
config = {
    'ai_ml': {
        'metrics': {
            'enabled': True,
            'track_memory_usage': True, # Track memory during operations (can add overhead)
            'history_size': 5000, # Max number of raw events to keep
            'analysis_percentiles': [50, 90, 95, 99] # Percentiles to calculate in reports
        }
        # ... other ai_ml config
    }
    # ... other ipfs-kit-py config
}

# Or direct initialization
from ipfs_kit_py.ai_ml_metrics import AIMLMetrics
ai_metrics = AIMLMetrics(track_memory=True, history_size=5000)
```

## Usage Examples

```python
from ipfs_kit_py.ai_ml_metrics import AIMLMetrics
import time
import random

# Initialize
ai_metrics = AIMLMetrics(track_memory=True)

# --- Track Model Loading ---
model_id = "resnet50-v1"
with ai_metrics.track_model_load(model_id=model_id, source="ipfs", framework="pytorch"):
    print(f"Simulating loading model {model_id}...")
    time.sleep(random.uniform(0.5, 1.5))
    # model = load_actual_model()
print("Model loading tracked.")

# --- Track Inference ---
num_inferences = 10
batch_size = 8
for i in range(num_inferences):
    with ai_metrics.track_inference(model_id=model_id, batch_size=batch_size):
        # print(f"Simulating inference batch {i+1}...")
        time.sleep(random.uniform(0.05, 0.2))
        # results = model.predict(input_batch)
print(f"{num_inferences} inference operations tracked.")

# --- Track Training Epoch ---
num_epochs = 3
samples_per_epoch = 1000
for epoch in range(num_epochs):
    with ai_metrics.track_training_epoch(model_id=model_id, epoch=epoch, num_samples=samples_per_epoch):
        print(f"Simulating training epoch {epoch}...")
        # Simulate training steps
        time.sleep(random.uniform(2.0, 5.0))
        # Record specific stats manually if needed
        ai_metrics.record_training_stats(
            model_id=model_id,
            epoch=epoch,
            metrics={'train_loss': random.uniform(0.1, 0.5), 'val_accuracy': random.uniform(0.8, 0.95)}
        )
print(f"{num_epochs} training epochs tracked.")

# --- Track Dataset Operation ---
dataset_id = "imagenet-subset-v2"
with ai_metrics.track_dataset_load(dataset_id=dataset_id, source="ipfs", format="parquet"):
    print(f"Simulating loading dataset {dataset_id}...")
    time.sleep(random.uniform(1.0, 3.0))
    # dataset = load_actual_dataset()
print("Dataset loading tracked.")

# --- Get Metrics ---
print("\n--- Model Metrics ---")
print(ai_metrics.get_model_metrics(model_id=model_id))

print("\n--- Inference Metrics ---")
print(ai_metrics.get_inference_metrics(model_id=model_id))

print("\n--- Training Metrics ---")
print(ai_metrics.get_training_metrics(model_id=model_id))

print("\n--- Dataset Metrics ---")
print(ai_metrics.get_dataset_metrics(dataset_id=dataset_id))

# --- Generate Report ---
print("\n--- Comprehensive Report ---")
report_data = ai_metrics.get_comprehensive_report()
# print(report_data) # Can be large

print("\n--- Formatted Markdown Report ---")
markdown_report = ai_metrics.generate_formatted_report(format="markdown")
print(markdown_report)

# Example report might include:
# - Summary statistics for each category (load times, inference latency, epoch duration)
# - Analysis (e.g., "Inference latency P95 is high", "Training epoch duration increased")
# - Recommendations (e.g., "Consider optimizing model loading", "Investigate epoch 2 performance")
```

## Benefits

*   **AI/ML Focus**: Provides metrics directly relevant to optimizing AI/ML workflows.
*   **Granularity**: Tracks specific stages like loading, inference, training epochs separately.
*   **Actionable Insights**: Reports include analysis and recommendations tailored to AI/ML performance.
*   **Framework Agnostic**: Designed to work across different ML frameworks.

## Relationship to General `PerformanceMetrics`

While `PerformanceMetrics` tracks general system and operation performance (latency, bandwidth, cache hits), `AIMLMetrics` focuses specifically on the stages and characteristics of AI/ML tasks. They can be used together: `PerformanceMetrics` might track the underlying IPFS `cat` operation latency when a model is loaded, while `AIMLMetrics` tracks the overall `track_model_load` duration, including deserialization and framework initialization.
