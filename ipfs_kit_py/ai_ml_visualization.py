"""
Visualization utilities for AI/ML metrics in IPFS Kit.

This module provides visualization tools for AI/ML metrics collected by the
ai_ml_metrics module. It supports both interactive and static visualizations,
with a focus on training convergence, inference performance, and distributed
training metrics.

Key features:
1. Training metrics visualization (loss curves, accuracy, learning rate)
2. Inference performance visualization (latency distributions, throughput)
3. Distributed training visualizations (worker utilization, coordination overhead)
4. Model and dataset comparison tools
5. Export to various formats (PNG, SVG, HTML, notebook widgets)
"""

import json
import os
import tempfile
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

# Optional imports - visualization components will gracefully degrade if not available
try:
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Check if we're in a Jupyter environment
try:
    from IPython.display import HTML, display

    IN_NOTEBOOK = True
except ImportError:
    IN_NOTEBOOK = False


class AIMLVisualization:
    """
    Visualization tools for AI/ML metrics.

    This class provides methods to create visualizations from metrics collected
    by the AIMLMetrics class. It supports both interactive and static visualizations
    and can export to various formats.
    """

    def __init__(self, metrics=None, theme="light", interactive=True):
        """
        Initialize visualization tools with optional metrics.

        Args:
            metrics: Optional AIMLMetrics instance to visualize
            theme: Visualization theme ('light' or 'dark')
            interactive: Whether to use interactive visualizations when available
        """
        self.metrics = metrics
        self.theme = theme
        self.interactive = interactive and PLOTLY_AVAILABLE

        # Set theme for matplotlib if available
        if MATPLOTLIB_AVAILABLE:
            if theme == "dark":
                plt.style.use("dark_background")
            else:
                plt.style.use("default")

        # Set theme for plotly if available
        self.plotly_template = "plotly_white" if theme == "light" else "plotly_dark"

    def check_visualization_availability(self) -> Dict[str, bool]:
        """
        Check which visualization libraries are available.

        Returns:
            Dictionary with availability status of visualization libraries
        """
        return {
            "matplotlib": MATPLOTLIB_AVAILABLE,
            "plotly": PLOTLY_AVAILABLE,
            "in_notebook": IN_NOTEBOOK,
            "interactive": self.interactive,
            "theme": self.theme,
        }

    def plot_training_metrics(
        self,
        model_id: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8),
        show_plot: bool = True,
    ) -> Any:
        """
        Plot training metrics for a specific model.

        Args:
            model_id: Optional model identifier to visualize
            figsize: Figure size as (width, height) in inches
            show_plot: Whether to display the plot

        Returns:
            Figure object or None if visualization is not available
        """
        if not self.metrics:
            print("No metrics data available. Please provide a metrics instance.")
            return None

        # Get training metrics for the model
        if model_id:
            training_data = self.metrics.get_training_metrics(model_id)
        else:
            # Get all models' training metrics
            all_training = self.metrics.get_training_metrics()
            if not all_training.get("models"):
                print("No training metrics available")
                return None

            # Use the first model if none specified
            model_id = next(iter(all_training["models"].keys()))
            training_data = all_training["models"][model_id]

        if not training_data:
            print(f"No training metrics available for model {model_id}")
            return None

        # Extract data for plotting
        epochs = range(len(training_data.get("loss_progress", {}).get("loss_curve", [])))
        loss_values = training_data.get("loss_progress", {}).get("loss_curve", [])
        # Check if accuracy curve exists, otherwise initialize as empty list
        accuracy_values = training_data.get("loss_progress", {}).get("accuracy_curve", [])
        # Make sure learning_rates has proper length
        learning_rates = training_data.get("learning_rates", [])

        if not epochs or not loss_values:
            print(f"Insufficient training data for model {model_id}")
            return None

        if self.interactive and PLOTLY_AVAILABLE:
            # Create interactive Plotly visualization
            fig = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                subplot_titles=("Training Loss & Accuracy", "Learning Rate"),
                vertical_spacing=0.1,
            )

            # Add loss curve
            fig.add_trace(
                go.Scatter(
                    x=list(epochs),
                    y=loss_values,
                    mode="lines+markers",
                    name="Loss",
                    line=dict(color="#FF5555"),
                ),
                row=1,
                col=1,
            )

            # Add accuracy curve if available
            if accuracy_values:
                fig.add_trace(
                    go.Scatter(
                        x=list(epochs),
                        y=accuracy_values,
                        mode="lines+markers",
                        name="Accuracy",
                        line=dict(color="#55AAFF"),
                        yaxis="y2",
                    ),
                    row=1,
                    col=1,
                )
                # Add secondary y-axis for accuracy
                fig.update_layout(
                    yaxis2=dict(
                        title="Accuracy",
                        overlaying="y",
                        side="right",
                        range=[0, 1] if max(accuracy_values, default=0) <= 1 else None,
                    )
                )

            # Add learning rate if available
            if learning_rates:
                fig.add_trace(
                    go.Scatter(
                        x=list(epochs),
                        y=learning_rates,
                        mode="lines+markers",
                        name="Learning Rate",
                        line=dict(color="#55FF99"),
                    ),
                    row=2,
                    col=1,
                )

            # Update layout
            fig.update_layout(
                title=f"Training Metrics for {model_id}",
                template=self.plotly_template,
                height=600,
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            )

            # Update axes
            fig.update_xaxes(title_text="Epoch", row=2, col=1)
            fig.update_yaxes(title_text="Loss", row=1, col=1)
            fig.update_yaxes(title_text="Learning Rate", row=2, col=1)

            if show_plot and IN_NOTEBOOK:
                display(fig)

            return fig

        elif MATPLOTLIB_AVAILABLE:
            # Create static Matplotlib visualization
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True)

            # Plot loss
            line1 = ax1.plot(epochs, loss_values, "r-", label="Loss")
            ax1.set_ylabel("Loss")
            ax1.grid(True, alpha=0.3)

            # Plot accuracy on secondary axis if available
            if accuracy_values:
                ax1_twin = ax1.twinx()
                line2 = ax1_twin.plot(epochs, accuracy_values, "b-", label="Accuracy")
                ax1_twin.set_ylabel("Accuracy")
                ax1_twin.set_ylim(0, 1 if max(accuracy_values, default=0) <= 1 else None)

                # Combine legends
                lines = line1 + line2
                labels = [l.get_label() for l in lines]
                ax1.legend(lines, labels, loc="upper center", bbox_to_anchor=(0.5, -0.05), ncol=2)
            else:
                ax1.legend()

            # Plot learning rate if available
            if learning_rates:
                ax2.plot(epochs, learning_rates, "g-", label="Learning Rate")
                ax2.set_ylabel("Learning Rate")
                ax2.grid(True, alpha=0.3)
                ax2.legend()

            ax2.set_xlabel("Epoch")

            # Set title
            fig.suptitle(f"Training Metrics for {model_id}")
            plt.tight_layout()

            if show_plot:
                plt.show()

            return fig

        else:
            print("No visualization libraries available. Please install matplotlib or plotly.")
            return None

    def plot_inference_latency(
        self,
        model_id: Optional[str] = None,
        figsize: Tuple[int, int] = (10, 6),
        show_plot: bool = True,
    ) -> Any:
        """
        Plot inference latency distribution for a model.

        Args:
            model_id: Optional model identifier to visualize
            figsize: Figure size as (width, height) in inches
            show_plot: Whether to display the plot

        Returns:
            Figure object or None if visualization is not available
        """
        if not self.metrics:
            print("No metrics data available. Please provide a metrics instance.")
            return None

        # Get inference metrics for the model
        if model_id:
            inference_data = self.metrics.get_inference_metrics(model_id)
        else:
            # Get all models' inference metrics
            all_inference = self.metrics.get_inference_metrics()
            if not all_inference.get("models"):
                print("No inference metrics available")
                return None

            # Use the first model if none specified
            model_id = next(iter(all_inference["models"].keys()))
            inference_data = all_inference["models"][model_id]

        if not inference_data:
            print(f"No inference metrics available for model {model_id}")
            return None

        # Extract latency data for plotting
        latencies = inference_data.get("latency_stats", {})
        latency_values = inference_data.get("raw_latencies", [])

        # If raw latencies aren't available, we can't create a distribution plot
        if not latency_values and not latencies.get("count", 0) > 0:
            print(f"Insufficient latency data for model {model_id}")
            return None

        if self.interactive and PLOTLY_AVAILABLE:
            # Create interactive Plotly visualization
            if latency_values:
                # Convert to milliseconds for better readability
                latency_ms = [l * 1000 for l in latency_values]

                # Create histogram
                fig = px.histogram(
                    x=latency_ms,
                    nbins=min(30, len(latency_ms) // 2 + 1),
                    labels={"x": "Latency (ms)"},
                    title=f"Inference Latency Distribution for {model_id}",
                    template=self.plotly_template,
                )

                # Add vertical lines for statistics
                fig.add_vline(
                    x=latencies.get("mean", 0) * 1000,
                    line_dash="dash",
                    line_color="green",
                    annotation_text="Mean",
                )

                if latencies.get("p95") is not None:
                    fig.add_vline(
                        x=latencies.get("p95") * 1000,
                        line_dash="dash",
                        line_color="red",
                        annotation_text="95th Percentile",
                    )
            else:
                # Create simple bar chart with available statistics
                stats = {
                    "Mean": latencies.get("mean", 0) * 1000,
                    "Median": latencies.get("median", 0) * 1000,
                    "Min": latencies.get("min", 0) * 1000,
                    "Max": latencies.get("max", 0) * 1000,
                    "P95": (
                        latencies.get("p95", 0) * 1000 if latencies.get("p95") is not None else 0
                    ),
                }

                fig = px.bar(
                    x=list(stats.keys()),
                    y=list(stats.values()),
                    labels={"x": "Statistic", "y": "Latency (ms)"},
                    title=f"Inference Latency Statistics for {model_id}",
                    template=self.plotly_template,
                )

            # Update layout
            fig.update_layout(height=400, hovermode="x unified", showlegend=False)

            if show_plot and IN_NOTEBOOK:
                display(fig)

            return fig

        elif MATPLOTLIB_AVAILABLE:
            # Create static Matplotlib visualization
            fig, ax = plt.subplots(figsize=figsize)

            if latency_values:
                # Convert to milliseconds for better readability
                latency_ms = [l * 1000 for l in latency_values]

                # Create histogram
                ax.hist(
                    latency_ms,
                    bins=min(30, len(latency_ms) // 2 + 1),
                    alpha=0.7,
                    color="skyblue",
                    edgecolor="black",
                )

                # Add vertical lines for statistics
                if latencies.get("mean") is not None:
                    ax.axvline(
                        latencies.get("mean") * 1000,
                        color="green",
                        linestyle="dashed",
                        linewidth=1,
                        label=f'Mean: {latencies.get("mean") * 1000:.2f} ms',
                    )

                if latencies.get("p95") is not None:
                    ax.axvline(
                        latencies.get("p95") * 1000,
                        color="red",
                        linestyle="dashed",
                        linewidth=1,
                        label=f'95th %ile: {latencies.get("p95") * 1000:.2f} ms',
                    )

                ax.set_xlabel("Latency (ms)")
                ax.set_ylabel("Frequency")
                ax.legend()
            else:
                # Create simple bar chart with available statistics
                stats = {
                    "Mean": latencies.get("mean", 0) * 1000,
                    "Median": latencies.get("median", 0) * 1000,
                    "Min": latencies.get("min", 0) * 1000,
                    "Max": latencies.get("max", 0) * 1000,
                    "P95": (
                        latencies.get("p95", 0) * 1000 if latencies.get("p95") is not None else 0
                    ),
                }

                ax.bar(list(stats.keys()), list(stats.values()), color="skyblue")
                ax.set_ylabel("Latency (ms)")

                # Add value labels on top of bars
                for i, (key, value) in enumerate(stats.items()):
                    if value > 0:
                        ax.text(
                            i, value + (max(stats.values()) * 0.03), f"{value:.2f}", ha="center"
                        )

            ax.set_title(f"Inference Latency for {model_id}")
            plt.tight_layout()

            if show_plot:
                plt.show()

            return fig

        else:
            print("No visualization libraries available. Please install matplotlib or plotly.")
            return None

    def plot_worker_utilization(
        self, figsize: Tuple[int, int] = (10, 6), show_plot: bool = True
    ) -> Any:
        """
        Plot worker utilization for distributed training.

        Args:
            figsize: Figure size as (width, height) in inches
            show_plot: Whether to display the plot

        Returns:
            Figure object or None if visualization is not available
        """
        if not self.metrics:
            print("No metrics data available. Please provide a metrics instance.")
            return None

        # Get distributed metrics
        distributed_data = self.metrics.get_distributed_metrics()

        if not distributed_data:
            print("No distributed training metrics available")
            return None

        # Extract worker utilization data
        worker_utilization = distributed_data.get("average_worker_utilization", {})

        if not worker_utilization:
            print("No worker utilization data available")
            return None

        # Extract data for plotting
        worker_ids = list(worker_utilization.keys())
        utilization_values = [
            worker_utilization[w] * 100 for w in worker_ids
        ]  # Convert to percentage

        if self.interactive and PLOTLY_AVAILABLE:
            # Create interactive Plotly visualization
            fig = px.bar(
                x=worker_ids,
                y=utilization_values,
                labels={"x": "Worker ID", "y": "Utilization (%)"},
                title="Worker Utilization in Distributed Training",
                template=self.plotly_template,
                color=utilization_values,
                color_continuous_scale=px.colors.sequential.Viridis,
            )

            # Add target line at 80% utilization
            fig.add_hline(
                y=80, line_dash="dash", line_color="red", annotation_text="Target Utilization"
            )

            # Update layout
            fig.update_layout(height=400, coloraxis_showscale=False, hovermode="x")

            # Add text annotations on bars
            for i, value in enumerate(utilization_values):
                fig.add_annotation(
                    x=worker_ids[i], y=value, text=f"{value:.1f}%", showarrow=False, yshift=10
                )

            if show_plot and IN_NOTEBOOK:
                display(fig)

            return fig

        elif MATPLOTLIB_AVAILABLE:
            # Create static Matplotlib visualization
            fig, ax = plt.subplots(figsize=figsize)

            # Create bar chart
            # Corrected color mapping: Apply division element-wise
            normalized_utilization = [u / 100.0 for u in utilization_values]
            bars = ax.bar(
                worker_ids, utilization_values, color=plt.cm.viridis(normalized_utilization)
            )

            # Add target line
            ax.axhline(y=80, color="red", linestyle="--", label="Target Utilization (80%)")

            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height + 1,
                    f"{height:.1f}%",
                    ha="center",
                    va="bottom",
                )

            ax.set_xlabel("Worker ID")
            ax.set_ylabel("Utilization (%)")
            ax.set_ylim(0, max(utilization_values) * 1.15)  # Add some headroom for labels
            ax.set_title("Worker Utilization in Distributed Training")
            ax.legend()

            plt.tight_layout()

            if show_plot:
                plt.show()

            return fig

        else:
            print("No visualization libraries available. Please install matplotlib or plotly.")
            return None

    def plot_dataset_load_times(
        self, figsize: Tuple[int, int] = (10, 6), show_plot: bool = True
    ) -> Any:
        """
        Plot dataset loading times.

        Args:
            figsize: Figure size as (width, height) in inches
            show_plot: Whether to display the plot

        Returns:
            Figure object or None if visualization is not available
        """
        if not self.metrics:
            print("No metrics data available. Please provide a metrics instance.")
            return None

        # Get dataset metrics
        dataset_data = self.metrics.get_dataset_metrics()

        if not dataset_data or not dataset_data.get("datasets"):
            print("No dataset metrics available")
            return None

        # Extract data for plotting
        datasets = []
        load_times = []
        formats = []
        sizes = []

        for dataset_id, data in dataset_data["datasets"].items():
            load_time = data.get("load_time_stats", {}).get("mean")
            if load_time is not None:
                datasets.append(dataset_id)
                load_times.append(load_time)
                formats.append(data.get("format", "unknown"))

                # Get size if available (convert to MB for better comparison)
                size_bytes = data.get("size_bytes")
                size_mb = size_bytes / (1024 * 1024) if size_bytes else None
                sizes.append(size_mb)

        if not datasets:
            print("Insufficient dataset metrics for visualization")
            return None

        if self.interactive and PLOTLY_AVAILABLE:
            # Create interactive Plotly visualization
            if all(s is not None for s in sizes):
                # Use bubble chart to show size relationship
                fig = px.scatter(
                    x=datasets,
                    y=load_times,
                    size=[max(1, s) for s in sizes],  # Ensure minimum bubble size
                    color=formats,
                    labels={
                        "x": "Dataset",
                        "y": "Load Time (s)",
                        "size": "Size (MB)",
                        "color": "Format",
                    },
                    title="Dataset Loading Performance",
                    template=self.plotly_template,
                    hover_data={"size": sizes},
                )
            else:
                # Use bar chart with color for format
                fig = px.bar(
                    x=datasets,
                    y=load_times,
                    color=formats,
                    labels={"x": "Dataset", "y": "Load Time (s)", "color": "Format"},
                    title="Dataset Loading Performance",
                    template=self.plotly_template,
                )

            # Update layout
            fig.update_layout(height=400, hovermode="x")

            if show_plot and IN_NOTEBOOK:
                display(fig)

            return fig

        elif MATPLOTLIB_AVAILABLE:
            # Create static Matplotlib visualization
            fig, ax = plt.subplots(figsize=figsize)

            # Create bar chart
            bars = ax.bar(datasets, load_times)

            # Color bars by format if formats are available
            if formats and len(set(formats)) > 1:
                # Get unique formats
                unique_formats = list(set(formats))
                colors = plt.cm.tab10(range(len(unique_formats)))
                color_map = dict(zip(unique_formats, colors))

                # Apply colors and create legend
                for i, (bar, format_type) in enumerate(zip(bars, formats)):
                    bar.set_color(color_map[format_type])

                # Create legend
                from matplotlib.patches import Patch

                legend_elements = [Patch(facecolor=color_map[f], label=f) for f in unique_formats]
                ax.legend(handles=legend_elements, title="Format")

            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height + 0.1,
                    f"{height:.2f}s",
                    ha="center",
                    va="bottom",
                )

            ax.set_xlabel("Dataset")
            ax.set_ylabel("Load Time (s)")

            # Add some headroom for labels
            ax.set_ylim(0, max(load_times) * 1.15)

            # Rotate x labels if many datasets
            if len(datasets) > 4:
                plt.xticks(rotation=45, ha="right")

            ax.set_title("Dataset Loading Performance")
            
            # Add padding to the figure before calling tight_layout to avoid warnings
            fig.subplots_adjust(top=0.85, bottom=0.15)
            
            # We'll wrap tight_layout in a try/except to avoid warnings
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fig.tight_layout(pad=1.2)
            except Exception:
                # Fall back to basic layout if tight_layout fails
                pass

            if show_plot:
                plt.show()

            return fig

        else:
            print("No visualization libraries available. Please install matplotlib or plotly.")
            return None

    def plot_comprehensive_dashboard(
        self, figsize: Tuple[int, int] = (15, 12), show_plot: bool = True
    ) -> Any:
        """
        Plot a comprehensive dashboard with multiple visualizations.

        Args:
            figsize: Figure size as (width, height) in inches
            show_plot: Whether to display the plot

        Returns:
            Figure object, HTML object, or None if visualization is not available
        """
        if not self.metrics:
            print("No metrics data available. Please provide a metrics instance.")
            return None

        # Get all metrics
        model_metrics = self.metrics.get_model_metrics()
        inference_metrics = self.metrics.get_inference_metrics()
        training_metrics = self.metrics.get_training_metrics()
        dataset_metrics = self.metrics.get_dataset_metrics()
        distributed_metrics = self.metrics.get_distributed_metrics()

        # Check if we have enough data to create a dashboard
        has_model_data = bool(model_metrics.get("models"))
        has_inference_data = bool(inference_metrics.get("models"))
        has_training_data = bool(training_metrics.get("models"))
        has_dataset_data = bool(dataset_metrics.get("datasets"))
        has_distributed_data = bool(distributed_metrics.get("worker_counts", {}).get("mean"))

        if not any(
            [
                has_model_data,
                has_inference_data,
                has_training_data,
                has_dataset_data,
                has_distributed_data,
            ]
        ):
            print("Insufficient metrics data for visualization")
            return None

        if self.interactive and PLOTLY_AVAILABLE:
            # Create interactive Plotly dashboard
            from plotly.subplots import make_subplots

            # Determine dashboard layout based on available data
            row_count = sum(
                [has_training_data, has_inference_data, has_dataset_data, has_distributed_data]
            )

            fig = make_subplots(
                rows=row_count,
                cols=1,
                subplot_titles=self._get_subplot_titles(
                    has_training_data, has_inference_data, has_dataset_data, has_distributed_data
                ),
                vertical_spacing=0.1,
            )

            current_row = 1

            # Add training metrics plot if available
            if has_training_data:
                model_id = next(iter(training_metrics["models"].keys()))
                model_data = training_metrics["models"][model_id]

                # Extract data
                epochs = range(len(model_data.get("loss_progress", {}).get("loss_curve", [])))
                loss_values = model_data.get("loss_progress", {}).get("loss_curve", [])
                accuracy_values = model_data.get("loss_progress", {}).get("accuracy_curve", [])

                if epochs and loss_values:
                    # Add loss curve
                    fig.add_trace(
                        go.Scatter(
                            x=list(epochs),
                            y=loss_values,
                            mode="lines+markers",
                            name="Loss",
                            line=dict(color="#FF5555"),
                        ),
                        row=current_row,
                        col=1,
                    )

                    # Add accuracy curve if available
                    if accuracy_values:
                        fig.add_trace(
                            go.Scatter(
                                x=list(epochs),
                                y=accuracy_values,
                                mode="lines+markers",
                                name="Accuracy",
                                line=dict(color="#55AAFF"),
                            ),
                            row=current_row,
                            col=1,
                        )

                current_row += 1

            # Add inference metrics plot if available
            if has_inference_data:
                model_id = next(iter(inference_metrics["models"].keys()))
                model_data = inference_metrics["models"][model_id]

                # Extract data
                latencies = model_data.get("latency_stats", {})

                # Create simple bar chart with available statistics
                stats = {
                    "Mean": latencies.get("mean", 0) * 1000,
                    "Median": latencies.get("median", 0) * 1000,
                    "Min": latencies.get("min", 0) * 1000,
                    "Max": latencies.get("max", 0) * 1000,
                    "P95": (
                        latencies.get("p95", 0) * 1000 if latencies.get("p95") is not None else 0
                    ),
                }

                fig.add_trace(
                    go.Bar(x=list(stats.keys()), y=list(stats.values()), name="Latency"),
                    row=current_row,
                    col=1,
                )

                current_row += 1

            # Add dataset metrics plot if available
            if has_dataset_data:
                # Extract data
                datasets = []
                load_times = []

                for dataset_id, data in dataset_metrics["datasets"].items():
                    load_time = data.get("load_time_stats", {}).get("mean")
                    if load_time is not None:
                        datasets.append(dataset_id)
                        load_times.append(load_time)

                if datasets and load_times:
                    fig.add_trace(
                        go.Bar(x=datasets, y=load_times, name="Load Time"), row=current_row, col=1
                    )

                current_row += 1

            # Add worker utilization plot if available
            if has_distributed_data:
                # Extract data
                worker_utilization = distributed_metrics.get("average_worker_utilization", {})

                if worker_utilization:
                    worker_ids = list(worker_utilization.keys())
                    utilization_values = [worker_utilization[w] * 100 for w in worker_ids]

                    fig.add_trace(
                        go.Bar(x=worker_ids, y=utilization_values, name="Utilization"),
                        row=current_row,
                        col=1,
                    )

                    # Add target line
                    fig.add_shape(
                        type="line",
                        x0=-0.5,
                        y0=80,
                        x1=len(worker_ids) - 0.5,
                        y1=80,
                        line=dict(color="red", width=2, dash="dash"),
                        row=current_row,
                        col=1,
                    )

            # Update layout
            fig.update_layout(
                title="AI/ML Performance Dashboard",
                template=self.plotly_template,
                height=300 * row_count,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )

            if show_plot and IN_NOTEBOOK:
                display(fig)

            return fig

        elif MATPLOTLIB_AVAILABLE:
            # Create static Matplotlib dashboard
            row_count = sum(
                [has_training_data, has_inference_data, has_dataset_data, has_distributed_data]
            )

            fig, axes = plt.subplots(row_count, 1, figsize=figsize)

            # Handle case with only one subplot
            if row_count == 1:
                axes = [axes]

            current_row = 0

            # Add training metrics plot if available
            if has_training_data:
                ax = axes[current_row]
                model_id = next(iter(training_metrics["models"].keys()))
                model_data = training_metrics["models"][model_id]

                # Extract data
                epochs = range(len(model_data.get("loss_progress", {}).get("loss_curve", [])))
                loss_values = model_data.get("loss_progress", {}).get("loss_curve", [])
                accuracy_values = model_data.get("loss_progress", {}).get("accuracy_curve", [])

                if epochs and loss_values:
                    # Plot loss
                    line1 = ax.plot(epochs, loss_values, "r-", label="Loss")
                    ax.set_ylabel("Loss")

                    # Plot accuracy on secondary axis if available
                    if accuracy_values:
                        ax_twin = ax.twinx()
                        line2 = ax_twin.plot(epochs, accuracy_values, "b-", label="Accuracy")
                        ax_twin.set_ylabel("Accuracy")

                        # Combine legends
                        lines = line1 + line2
                        labels = [l.get_label() for l in lines]
                        ax.legend(lines, labels, loc="upper right")
                    else:
                        ax.legend()

                ax.set_title(f"Training Metrics for {model_id}")
                current_row += 1

            # Add inference metrics plot if available
            if has_inference_data:
                ax = axes[current_row]
                model_id = next(iter(inference_metrics["models"].keys()))
                model_data = inference_metrics["models"][model_id]

                # Extract data
                latencies = model_data.get("latency_stats", {})

                # Create simple bar chart with available statistics
                stats = {
                    "Mean": latencies.get("mean", 0) * 1000,
                    "Median": latencies.get("median", 0) * 1000,
                    "Min": latencies.get("min", 0) * 1000,
                    "Max": latencies.get("max", 0) * 1000,
                    "P95": (
                        latencies.get("p95", 0) * 1000 if latencies.get("p95") is not None else 0
                    ),
                }

                ax.bar(list(stats.keys()), list(stats.values()), color="skyblue")
                ax.set_ylabel("Latency (ms)")

                # Add value labels on top of bars
                for i, (key, value) in enumerate(stats.items()):
                    if value > 0:
                        ax.text(
                            i, value + (max(stats.values()) * 0.03), f"{value:.2f}", ha="center"
                        )

                ax.set_title(f"Inference Latency for {model_id}")
                current_row += 1

            # Add dataset metrics plot if available
            if has_dataset_data:
                ax = axes[current_row]

                # Extract data
                datasets = []
                load_times = []

                for dataset_id, data in dataset_metrics["datasets"].items():
                    load_time = data.get("load_time_stats", {}).get("mean")
                    if load_time is not None:
                        datasets.append(dataset_id)
                        load_times.append(load_time)

                if datasets and load_times:
                    # Create bar chart
                    bars = ax.bar(datasets, load_times, color="green")

                    # Add value labels on top of bars
                    for bar in bars:
                        height = bar.get_height()
                        ax.text(
                            bar.get_x() + bar.get_width() / 2.0,
                            height + 0.1,
                            f"{height:.2f}s",
                            ha="center",
                            va="bottom",
                        )

                    ax.set_ylabel("Load Time (s)")

                    # Rotate x labels if many datasets
                    if len(datasets) > 4:
                        plt.sca(ax)
                        plt.xticks(rotation=45, ha="right")

                    ax.set_title("Dataset Loading Performance")

                current_row += 1

            # Add worker utilization plot if available
            if has_distributed_data:
                ax = axes[current_row]

                # Extract data
                worker_utilization = distributed_metrics.get("average_worker_utilization", {})

                if worker_utilization:
                    worker_ids = list(worker_utilization.keys())
                    utilization_values = [worker_utilization[w] * 100 for w in worker_ids]

                    # Create bar chart
                    bars = ax.bar(
                        worker_ids,
                        utilization_values,
                        color=plt.cm.viridis(utilization_values / 100),
                    )

                    # Add target line
                    ax.axhline(y=80, color="red", linestyle="--", label="Target Utilization (80%)")

                    # Add value labels on top of bars
                    for bar in bars:
                        height = bar.get_height()
                        ax.text(
                            bar.get_x() + bar.get_width() / 2.0,
                            height + 1,
                            f"{height:.1f}%",
                            ha="center",
                            va="bottom",
                        )

                    ax.set_ylabel("Utilization (%)")
                    ax.set_ylim(0, max(utilization_values) * 1.15)
                    ax.set_title("Worker Utilization in Distributed Training")
                    ax.legend()

            plt.tight_layout()
            fig.suptitle("AI/ML Performance Dashboard", fontsize=16, y=1.02)

            if show_plot:
                plt.show()

            return fig

        else:
            print("No visualization libraries available. Please install matplotlib or plotly.")
            return None

    def generate_html_report(self, filename: Optional[str] = None) -> str:
        """
        Generate an HTML report with all metrics visualizations.

        Args:
            filename: Optional filename to save the HTML report

        Returns:
            HTML string containing the report
        """
        if not self.metrics:
            print("No metrics data available. Please provide a metrics instance.")
            return "<p>No metrics data available.</p>"

        if not PLOTLY_AVAILABLE:
            print("Plotly is required for HTML reports. Please install plotly.")
            return "<p>Plotly is required for HTML reports.</p>"

        # Create HTML header with CSS
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI/ML Performance Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: {('#f5f5f5' if self.theme == 'light' else '#2d2d2d')};
                    color: {('#333' if self.theme == 'light' else '#f5f5f5')};
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .section {{
                    background-color: {('#fff' if self.theme == 'light' else '#333')};
                    padding: 20px;
                    margin-bottom: 20px;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                .metrics-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                .metrics-table th, .metrics-table td {{
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid {('#ddd' if self.theme == 'light' else '#555')};
                }}
                .metrics-table th {{
                    background-color: {('#f2f2f2' if self.theme == 'light' else '#444')};
                }}
                .plot-container {{
                    margin-top: 20px;
                }}
                .recommendations {{
                    margin-top: 10px;
                }}
                .recommendation {{
                    padding: 10px;
                    margin-bottom: 10px;
                    border-left: 4px solid #4CAF50;
                    background-color: {('#f9f9f9' if self.theme == 'light' else '#3a3a3a')};
                }}
                .recommendation.high {{
                    border-left-color: #F44336;
                }}
                .recommendation.medium {{
                    border-left-color: #FF9800;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    font-size: 12px;
                    color: {('#777' if self.theme == 'light' else '#aaa')};
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>AI/ML Performance Report</h1>
                    <p>Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
        """

        # Create dashboard section
        html += """
                <div class="section">
                    <h2>Performance Dashboard</h2>
                    <div class="plot-container" id="dashboard-plot">
        """

        # Generate dashboard visualization
        dashboard_fig = self.plot_comprehensive_dashboard(show_plot=False)
        if dashboard_fig:
            dashboard_html = dashboard_fig.to_html(full_html=False, include_plotlyjs="cdn")
            html += dashboard_html
        else:
            html += "<p>No dashboard data available.</p>"

        html += """
                    </div>
                </div>
        """

        # Add model metrics section
        model_metrics = self.metrics.get_model_metrics()
        if model_metrics and model_metrics.get("models"):
            html += """
                <div class="section">
                    <h2>Model Metrics</h2>
                    <table class="metrics-table">
                        <tr>
                            <th>Model ID</th>
                            <th>Framework</th>
                            <th>Size</th>
                            <th>Avg Load Time (s)</th>
                            <th>Min Load Time (s)</th>
                            <th>Max Load Time (s)</th>
                        </tr>
            """

            for model_id, model_data in model_metrics["models"].items():
                load_stats = model_data.get("load_time_stats", {})
                size_bytes = model_data.get("size_bytes")
                size_str = self._format_size(size_bytes) if size_bytes else "N/A"

                html += f"""
                        <tr>
                            <td>{model_id}</td>
                            <td>{model_data.get('framework', 'unknown')}</td>
                            <td>{size_str}</td>
                            <td>{load_stats.get('mean', 'N/A')}</td>
                            <td>{load_stats.get('min', 'N/A')}</td>
                            <td>{load_stats.get('max', 'N/A')}</td>
                        </tr>
                """

            html += """
                    </table>
                """

            # Add training metrics plots for each model
            for model_id in model_metrics["models"].keys():
                training_fig = self.plot_training_metrics(model_id=model_id, show_plot=False)
                if training_fig:
                    html += f"""
                    <h3>Training Metrics for {model_id}</h3>
                    <div class="plot-container" id="training-plot-{model_id}">
                    """
                    training_html = training_fig.to_html(full_html=False, include_plotlyjs="cdn")
                    html += training_html
                    html += """
                    </div>
                    """

            html += """
                </div>
            """

        # Add inference metrics section
        inference_metrics = self.metrics.get_inference_metrics()
        if inference_metrics and inference_metrics.get("models"):
            html += """
                <div class="section">
                    <h2>Inference Metrics</h2>
                    <table class="metrics-table">
                        <tr>
                            <th>Model ID</th>
                            <th>Avg Latency (ms)</th>
                            <th>P95 Latency (ms)</th>
                            <th>Throughput (items/s)</th>
                        </tr>
            """

            for model_id, model_data in inference_metrics["models"].items():
                latency_stats = model_data.get("latency_stats", {})
                throughput_stats = model_data.get("throughput_stats", {})

                avg_latency_ms = (
                    latency_stats.get("mean", 0) * 1000
                    if latency_stats.get("mean") is not None
                    else "N/A"
                )
                p95_latency_ms = (
                    latency_stats.get("p95", 0) * 1000
                    if latency_stats.get("p95") is not None
                    else "N/A"
                )
                throughput = throughput_stats.get("mean", "N/A")

                if isinstance(avg_latency_ms, str):
                    avg_latency_str = avg_latency_ms
                else:
                    avg_latency_str = f"{avg_latency_ms:.2f}"

                if isinstance(p95_latency_ms, str):
                    p95_latency_str = p95_latency_ms
                else:
                    p95_latency_str = f"{p95_latency_ms:.2f}"

                if isinstance(throughput, str):
                    throughput_str = throughput
                else:
                    throughput_str = f"{throughput:.2f}"

                html += f"""
                        <tr>
                            <td>{model_id}</td>
                            <td>{avg_latency_str}</td>
                            <td>{p95_latency_str}</td>
                            <td>{throughput_str}</td>
                        </tr>
                """

            html += """
                    </table>
                """

            # Add latency plots for each model
            for model_id in inference_metrics["models"].keys():
                latency_fig = self.plot_inference_latency(model_id=model_id, show_plot=False)
                if latency_fig:
                    html += f"""
                    <h3>Inference Latency for {model_id}</h3>
                    <div class="plot-container" id="latency-plot-{model_id}">
                    """
                    latency_html = latency_fig.to_html(full_html=False, include_plotlyjs="cdn")
                    html += latency_html
                    html += """
                    </div>
                    """

            html += """
                </div>
            """

        # Add dataset metrics section
        dataset_metrics = self.metrics.get_dataset_metrics()
        if dataset_metrics and dataset_metrics.get("datasets"):
            html += """
                <div class="section">
                    <h2>Dataset Metrics</h2>
                    <table class="metrics-table">
                        <tr>
                            <th>Dataset ID</th>
                            <th>Format</th>
                            <th>Size</th>
                            <th>Avg Load Time (s)</th>
                            <th>Preprocessing Time (s)</th>
                        </tr>
            """

            for dataset_id, dataset_data in dataset_metrics["datasets"].items():
                load_stats = dataset_data.get("load_time_stats", {})
                preprocess_stats = dataset_data.get("preprocessing_time_stats", {})
                size_bytes = dataset_data.get("size_bytes")
                size_str = self._format_size(size_bytes) if size_bytes else "N/A"

                html += f"""
                        <tr>
                            <td>{dataset_id}</td>
                            <td>{dataset_data.get('format', 'unknown')}</td>
                            <td>{size_str}</td>
                            <td>{load_stats.get('mean', 'N/A')}</td>
                            <td>{preprocess_stats.get('mean', 'N/A')}</td>
                        </tr>
                """

            html += """
                    </table>
                """

            # Add dataset load time plot
            dataset_fig = self.plot_dataset_load_times(show_plot=False)
            if dataset_fig:
                html += """
                <h3>Dataset Loading Performance</h3>
                <div class="plot-container" id="dataset-plot">
                """
                dataset_html = dataset_fig.to_html(full_html=False, include_plotlyjs="cdn")
                html += dataset_html
                html += """
                </div>
                """

            html += """
                </div>
            """

        # Add distributed metrics section
        distributed_metrics = self.metrics.get_distributed_metrics()
        if distributed_metrics:
            html += """
                <div class="section">
                    <h2>Distributed Training Metrics</h2>
                    <table class="metrics-table">
                        <tr>
                            <th>Metric</th>
                            <th>Value</th>
                        </tr>
            """

            # Add coordination overhead
            coordination_stats = distributed_metrics.get("coordination_overhead_stats", {})
            if coordination_stats:
                html += f"""
                        <tr>
                            <td>Avg Coordination Overhead (s)</td>
                            <td>{coordination_stats.get('mean', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Total Coordination Time (s)</td>
                            <td>{coordination_stats.get('total', 'N/A')}</td>
                        </tr>
                """

            # Add worker counts
            worker_counts = distributed_metrics.get("worker_counts", {})
            if worker_counts:
                html += f"""
                        <tr>
                            <td>Min Workers</td>
                            <td>{worker_counts.get('min', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Max Workers</td>
                            <td>{worker_counts.get('max', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td>Avg Workers</td>
                            <td>{worker_counts.get('mean', 'N/A')}</td>
                        </tr>
                """

            # Add task distribution times
            task_dist_times = distributed_metrics.get("task_distribution_times", {})
            if task_dist_times:
                html += f"""
                        <tr>
                            <td>Avg Task Distribution Time (s)</td>
                            <td>{task_dist_times.get('mean', 'N/A')}</td>
                        </tr>
                """

            # Add result aggregation times
            result_agg_times = distributed_metrics.get("result_aggregation_times", {})
            if result_agg_times:
                html += f"""
                        <tr>
                            <td>Avg Result Aggregation Time (s)</td>
                            <td>{result_agg_times.get('mean', 'N/A')}</td>
                        </tr>
                """

            html += """
                    </table>
                """

            # Add worker utilization plot
            worker_fig = self.plot_worker_utilization(show_plot=False)
            if worker_fig:
                html += """
                <h3>Worker Utilization</h3>
                <div class="plot-container" id="worker-plot">
                """
                worker_html = worker_fig.to_html(full_html=False, include_plotlyjs="cdn")
                html += worker_html
                html += """
                </div>
                """

            html += """
                </div>
            """

        # Add recommendations section
        recommendations = self.metrics.get_comprehensive_report().get("recommendations", [])
        if recommendations:
            html += """
                <div class="section">
                    <h2>Recommendations</h2>
                    <div class="recommendations">
            """

            for i, rec in enumerate(recommendations, 1):
                severity = rec.get("severity", "low")
                html += f"""
                        <div class="recommendation {severity}">
                            <h3>{i}. {rec.get('message', '')}</h3>
                            <p>{rec.get('details', '')}</p>
                        </div>
                """

            html += """
                    </div>
                </div>
            """

        # Add footer and close HTML
        html += """
                <div class="footer">
                    <p>Generated by IPFS Kit AI/ML Visualization Module</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Save to file if filename provided
        if filename:
            with open(filename, "w") as f:
                f.write(html)
            print(f"HTML report saved to {filename}")

        # Return HTML as string
        return html

    def export_visualizations(
        self, export_dir: str, formats: List[str] = ["png", "html"]
    ) -> Dict[str, Any]:
        """
        Export all visualizations to files.

        Args:
            export_dir: Directory to save exported visualizations
            formats: List of formats to export ('png', 'svg', 'html', 'json')

        Returns:
            Dictionary with export results
        """
        if not self.metrics:
            print("No metrics data available. Please provide a metrics instance.")
            return {"success": False, "error": "No metrics data available", "exported_files": []}

        # Create export directory
        os.makedirs(export_dir, exist_ok=True)

        # Initialize results
        results = {"success": True, "exported_files": [], "errors": []}

        try:
            # Export comprehensive dashboard
            if "html" in formats:
                # Export full HTML report
                html_path = os.path.join(export_dir, "ai_ml_report.html")
                self.generate_html_report(filename=html_path)
                results["exported_files"].append(html_path)

            # Export individual plots
            if any(fmt in formats for fmt in ["png", "svg", "pdf"]):

                if not MATPLOTLIB_AVAILABLE:
                    results["errors"].append(
                        "Matplotlib is required for image exports but not available"
                    )
                else:
                    # Export training metrics
                    training_metrics = self.metrics.get_training_metrics()
                    if training_metrics and training_metrics.get("models"):
                        for model_id in training_metrics["models"].keys():
                            fig = self.plot_training_metrics(model_id=model_id, show_plot=False)
                            if fig:
                                for fmt in formats:
                                    if fmt in ["png", "svg", "pdf"]:
                                        file_path = os.path.join(
                                            export_dir, f"training_{model_id}.{fmt}"
                                        )
                                        fig.savefig(file_path, bbox_inches="tight")
                                        results["exported_files"].append(file_path)

                    # Export inference metrics
                    inference_metrics = self.metrics.get_inference_metrics()
                    if inference_metrics and inference_metrics.get("models"):
                        for model_id in inference_metrics["models"].keys():
                            fig = self.plot_inference_latency(model_id=model_id, show_plot=False)
                            if fig:
                                for fmt in formats:
                                    if fmt in ["png", "svg", "pdf"]:
                                        file_path = os.path.join(
                                            export_dir, f"inference_{model_id}.{fmt}"
                                        )
                                        fig.savefig(file_path, bbox_inches="tight")
                                        results["exported_files"].append(file_path)

                    # Export dataset metrics
                    fig = self.plot_dataset_load_times(show_plot=False)
                    if fig:
                        for fmt in formats:
                            if fmt in ["png", "svg", "pdf"]:
                                file_path = os.path.join(export_dir, f"datasets.{fmt}")
                                fig.savefig(file_path, bbox_inches="tight")
                                results["exported_files"].append(file_path)

                    # Export worker utilization
                    fig = self.plot_worker_utilization(show_plot=False)
                    if fig:
                        for fmt in formats:
                            if fmt in ["png", "svg", "pdf"]:
                                file_path = os.path.join(export_dir, f"worker_utilization.{fmt}")
                                fig.savefig(file_path, bbox_inches="tight")
                                results["exported_files"].append(file_path)

                    # Export dashboard
                    fig = self.plot_comprehensive_dashboard(show_plot=False)
                    if fig:
                        for fmt in formats:
                            if fmt in ["png", "svg", "pdf"]:
                                file_path = os.path.join(export_dir, f"dashboard.{fmt}")
                                fig.savefig(file_path, bbox_inches="tight")
                                results["exported_files"].append(file_path)

            # Export raw metrics as JSON
            if "json" in formats:
                report = self.metrics.get_comprehensive_report()
                json_path = os.path.join(export_dir, "ai_ml_metrics.json")
                with open(json_path, "w") as f:
                    json.dump(report, f, indent=2)
                results["exported_files"].append(json_path)

        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))

        return results

    def _get_subplot_titles(self, has_training, has_inference, has_dataset, has_distributed):
        """Helper to get subplot titles based on available data."""
        titles = []
        if has_training:
            titles.append("Training Metrics")
        if has_inference:
            titles.append("Inference Latency")
        if has_dataset:
            titles.append("Dataset Load Times")
        if has_distributed:
            titles.append("Worker Utilization")
        return titles

    @staticmethod
    def _format_size(size_bytes):
        """Format a byte size value to a human-readable string."""
        if size_bytes is None:
            return "N/A"

        size_bytes = float(size_bytes)

        if size_bytes < 1024:
            return f"{size_bytes:.2f} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes < 1024 * 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024 * 1024):.2f} TB"


def create_visualization(metrics=None, theme="light", interactive=True):
    """
    Factory function to create a visualization instance.

    Args:
        metrics: Optional AIMLMetrics instance to visualize
        theme: Visualization theme ('light' or 'dark')
        interactive: Whether to use interactive visualizations when available

    Returns:
        AIMLVisualization instance
    """
    return AIMLVisualization(metrics=metrics, theme=theme, interactive=interactive)
