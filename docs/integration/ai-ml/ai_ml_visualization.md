# AI/ML Visualization Guide

This guide explains how to use the visualization capabilities of IPFS Kit for AI/ML metrics.

## Overview

The `ai_ml_visualization` module provides comprehensive visualization tools for AI/ML metrics collected during training, inference, and distributed processing operations. It is designed to work seamlessly with the metrics collection system provided by the `ai_ml_metrics` module.

Key features:
- Support for both interactive (Plotly) and static (Matplotlib) visualizations
- Graceful degradation when visualization libraries are not available
- Theme support (light/dark) for consistent styling
- Comprehensive dashboard generation
- HTML report generation with CSS styling
- Export capabilities for various formats (PNG, SVG, PDF, HTML, JSON)
- Jupyter notebook integration

## Getting Started

First, import the necessary components:

```python
from ipfs_kit_py.ai_ml_metrics import AIMLMetricsCollector
from ipfs_kit_py.ai_ml_visualization import create_visualization
```

### Basic Usage

```python
# Create a metrics collector to track metrics
metrics = AIMLMetricsCollector()

# Record some metrics during training/inference
with metrics.track_training_epoch(model_id="my_model", epoch=0, num_samples=1000):
    # Simulate training
    metrics.record_metric("my_model/epoch/0/train_loss", 1.5)
    metrics.record_metric("my_model/epoch/0/val_loss", 1.7)
    metrics.record_metric("my_model/epoch/0/train_acc", 0.6)
    metrics.record_metric("my_model/epoch/0/val_acc", 0.55)

# Create a visualization instance
viz = create_visualization(metrics, theme="light", interactive=True)

# Generate a visualization
viz.plot_training_metrics(model_id="my_model")

# Generate an HTML report
viz.generate_html_report("ai_ml_report.html")
```

## Visualization Types

### Training Metrics

Visualizes training metrics like loss, accuracy, and learning rate over epochs:

```python
viz.plot_training_metrics(
    model_id="my_model", 
    figsize=(12, 8),
    show_plot=True
)
```

![Training Metrics Example](../examples/ai_ml_viz_output/training_metrics.png)

### Inference Latency

Visualizes inference latency distribution for model evaluation:

```python
viz.plot_inference_latency(
    model_id="my_model",
    figsize=(10, 6),
    show_plot=True
)
```

### Worker Utilization

Visualizes worker utilization in distributed training:

```python
viz.plot_worker_utilization(
    figsize=(10, 6),
    show_plot=True
)
```

### Dataset Loading Performance

Visualizes dataset loading performance:

```python
viz.plot_dataset_load_times(
    figsize=(10, 6),
    show_plot=True
)
```

### Comprehensive Dashboard

Generate a dashboard with multiple visualizations:

```python
viz.plot_comprehensive_dashboard(
    figsize=(15, 12),
    show_plot=True
)
```

## HTML Reports

Generate an HTML report with all visualizations:

```python
html_report = viz.generate_html_report("ai_ml_report.html")
```

The HTML report includes:
- Summary statistics
- All visualizations with explanations
- Detailed metrics tables
- CSS styling for consistent appearance

## Exporting Visualizations

Export all visualizations to files:

```python
exported_files = viz.export_visualizations(
    export_dir="./outputs",
    formats=["png", "svg", "html", "json"]
)
```

## Interactive vs. Static Visualizations

Choose between interactive (Plotly) and static (Matplotlib) visualizations based on your needs:

```python
# Interactive visualizations
viz_interactive = create_visualization(metrics, interactive=True)

# Static visualizations
viz_static = create_visualization(metrics, interactive=False)
```

Interactive visualizations provide:
- Zoom and pan capabilities
- Tooltips with detailed information
- Dynamic filtering of data
- Web-friendly exports

Static visualizations provide:
- Lighter weight outputs
- Publication-quality figures
- Broader format compatibility
- More customization options

## Theming

Choose between light and dark themes:

```python
# Light theme
viz_light = create_visualization(metrics, theme="light")

# Dark theme
viz_dark = create_visualization(metrics, theme="dark")
```

## Environment Detection

The visualization module automatically detects:
- Available visualization libraries
- Jupyter notebook environment
- Interactive shell capabilities

This allows for graceful degradation when visualization libraries are not available, providing text-based alternatives when necessary.

## Advanced Usage

### Custom Visualizations

Create custom visualizations by combining existing capabilities:

```python
import matplotlib.pyplot as plt

# Get the figure and axis from the visualization module
fig, ax = plt.subplots(figsize=(10, 6))

# Plot training metrics
viz.plot_training_metrics(model_id="my_model", show_plot=False)

# Add custom annotations
ax.annotate("Important event", xy=(3, 0.8), xytext=(4, 0.9),
            arrowprops=dict(facecolor='black', shrink=0.05))

# Show the plot
plt.show()
```

### Integration with Other Tools

The visualization module works well with other data analysis tools:

```python
import pandas as pd

# Convert metrics to pandas DataFrames
metrics_df = viz.get_metrics_dataframe(model_id="my_model")

# Perform custom analysis
rolling_avg = metrics_df['train_loss'].rolling(window=3).mean()

# Use results in visualizations
import matplotlib.pyplot as plt
plt.figure(figsize=(10, 6))
plt.plot(metrics_df.index, rolling_avg, label="Rolling Average Loss")
plt.legend()
plt.show()
```

## Advanced Custom Visualizations

You can integrate the visualization outputs with your own data analysis workflows. For example, you may want to combine the visualizations with additional data analysis:

```python
import pandas as pd
import matplotlib.pyplot as plt

# Convert collected metrics into a DataFrame
metrics_df = viz.get_metrics_dataframe(model_id="my_model")

# Compute rolling average for training loss
rolling_avg = metrics_df['train_loss'].rolling(window=3).mean()

# Plot the rolling average
plt.figure(figsize=(10,6))
plt.plot(rolling_avg, label="Rolling Average Train Loss")
plt.title("Customized Analysis of Training Loss")
plt.xlabel("Epoch")
plt.ylabel("Train Loss")
plt.legend()
plt.show()
```

This example demonstrates how visualization outputs can be customized beyond the built-in plots by integrating with libraries like pandas and matplotlib.

## Practical Examples

For complete examples demonstrating AI/ML visualization, see:
- `examples/ai_ml_visualization_example.py` - Comprehensive example of all visualization capabilities
- `examples/ai_ml_integration_example.py` - Example of visualization integrated with the full AI/ML workflow

## API Reference

### AIMLVisualization Class

```python
class AIMLVisualization:
    """Visualization tools for AI/ML metrics.

    This class provides methods for generating various visualizations
    related to AI/ML metrics, such as training metrics, inference latency,
    worker utilization, and dataset load times.
    """
    
    def __init__(self, metrics=None, theme="light", interactive=True):
        """Initialize visualization tools with optional metrics."""
    
    def plot_training_metrics(self, model_id=None, figsize=(12, 8), show_plot=True):
        """Plot training metrics for a specific model."""
    
    def plot_inference_latency(self, model_id=None, figsize=(10, 6), show_plot=True):
        """Plot inference latency distribution for a model."""
    
    def plot_worker_utilization(self, figsize=(10, 6), show_plot=True):
        """Plot worker utilization for distributed training."""
    
    def plot_dataset_load_times(self, figsize=(10, 6), show_plot=True):
        """Plot dataset loading times."""
    
    def plot_comprehensive_dashboard(self, figsize=(15, 12), show_plot=True):
        """Plot a comprehensive dashboard with multiple visualizations."""
    
    def generate_html_report(self, filename=None):
        """Generate an HTML report with all metrics visualizations."""
    
    def export_visualizations(self, export_dir, formats=['png', 'html']):
        """Export all visualizations to files."""
    
    def export_plot(self, fig, filename):
        """Export a single plot to a file."""
```

### Factory Function
# AI/ML Visualization Guide

This guide explains how to use the visualization capabilities of IPFS Kit for AI/ML metrics.

## Overview

The `ai_ml_visualization` module provides comprehensive visualization tools for AI/ML metrics collected during training, inference, and distributed processing operations. It is designed to work seamlessly with the metrics collection system provided by the `ai_ml_metrics` module.

Key features:
- Support for both interactive (Plotly) and static (Matplotlib) visualizations
- Graceful degradation when visualization libraries are not available
- Theme support (light/dark) for consistent styling
- Comprehensive dashboard generation
- HTML report generation with CSS styling
- Export capabilities for various formats (PNG, SVG, PDF, HTML, JSON)
- Jupyter notebook integration

## Getting Started

First, import the necessary components:

```python
from ipfs_kit_py.ai_ml_metrics import AIMLMetricsCollector
from ipfs_kit_py.ai_ml_visualization import create_visualization
```

### Basic Usage

```python
# Create a metrics collector to track metrics
metrics = AIMLMetricsCollector()

# Record some metrics during training/inference
with metrics.track_training_epoch(model_id="my_model", epoch=0, num_samples=1000):
    # Simulate training
    metrics.record_metric("my_model/epoch/0/train_loss", 1.5)
    metrics.record_metric("my_model/epoch/0/val_loss", 1.7)
    metrics.record_metric("my_model/epoch/0/train_acc", 0.6)
    metrics.record_metric("my_model/epoch/0/val_acc", 0.55)

# Create a visualization instance
viz = create_visualization(metrics, theme="light", interactive=True)

# Generate a visualization
viz.plot_training_metrics(model_id="my_model")

# Generate an HTML report
viz.generate_html_report("ai_ml_report.html")
```

## Visualization Types

### Training Metrics

Visualizes training metrics like loss, accuracy, and learning rate over epochs:

```python
viz.plot_training_metrics(
    model_id="my_model", 
    figsize=(12, 8),
    show_plot=True
)
```

![Training Metrics Example](../examples/ai_ml_viz_output/training_metrics.png)

### Inference Latency

Visualizes inference latency distribution for model evaluation:

```python
viz.plot_inference_latency(
    model_id="my_model",
    figsize=(10, 6),
    show_plot=True
)
```

### Worker Utilization

Visualizes worker utilization in distributed training:

```python
viz.plot_worker_utilization(
    figsize=(10, 6),
    show_plot=True
)
```

### Dataset Loading Performance

Visualizes dataset loading performance:

```python
viz.plot_dataset_load_times(
    figsize=(10, 6),
    show_plot=True
)
```

### Comprehensive Dashboard

Generate a dashboard with multiple visualizations:

```python
viz.plot_comprehensive_dashboard(
    figsize=(15, 12),
    show_plot=True
)
```

## HTML Reports

Generate an HTML report with all visualizations:

```python
html_report = viz.generate_html_report("ai_ml_report.html")
```

The HTML report includes:
- Summary statistics
- All visualizations with explanations
- Detailed metrics tables
- CSS styling for consistent appearance

## Exporting Visualizations

Export all visualizations to files:

```python
exported_files = viz.export_visualizations(
    export_dir="./outputs",
    formats=["png", "svg", "html", "json"]
)
```

## Interactive vs. Static Visualizations

Choose between interactive (Plotly) and static (Matplotlib) visualizations based on your needs:

```python
# Interactive visualizations
viz_interactive = create_visualization(metrics, interactive=True)

# Static visualizations
viz_static = create_visualization(metrics, interactive=False)
```

Interactive visualizations provide:
- Zoom and pan capabilities
- Tooltips with detailed information
- Dynamic filtering of data
- Web-friendly exports

Static visualizations provide:
- Lighter weight outputs
- Publication-quality figures
- Broader format compatibility
- More customization options

## Theming

Choose between light and dark themes:

```python
# Light theme
viz_light = create_visualization(metrics, theme="light")

# Dark theme
viz_dark = create_visualization(metrics, theme="dark")
```

## Environment Detection

The visualization module automatically detects:
- Available visualization libraries
- Jupyter notebook environment
- Interactive shell capabilities

This allows for graceful degradation when visualization libraries are not available, providing text-based alternatives when necessary.
