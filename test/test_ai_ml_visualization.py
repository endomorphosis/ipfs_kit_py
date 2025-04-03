#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the AI/ML visualization module.

These tests verify that the visualization components work correctly,
including graceful degradation when visualization libraries are not available.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Attempt to import visualization libraries, but allow tests to run without them
try:
    import matplotlib

    matplotlib.use("Agg")  # Use non-interactive backend for testing
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Import the modules to test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ipfs_kit_py.ai_ml_metrics import AIMLMetricsCollector
from ipfs_kit_py.ai_ml_visualization import (
    AIMLVisualization,
    check_visualization_libraries,
    create_visualization,
)


class TestAIMLVisualization(unittest.TestCase):
    """Test case for the AIML Visualization module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a metrics collector with some test data
        self.metrics = AIMLMetricsCollector()

        # Add sample metrics
        model_id = "test_model"

        # Training metrics
        for epoch in range(5):
            self.metrics.record_metric(f"{model_id}/epoch/{epoch}/train_loss", 1.0 - epoch * 0.2)
            self.metrics.record_metric(f"{model_id}/epoch/{epoch}/val_loss", 1.2 - epoch * 0.15)
            self.metrics.record_metric(f"{model_id}/epoch/{epoch}/train_acc", 0.6 + epoch * 0.08)
            self.metrics.record_metric(f"{model_id}/epoch/{epoch}/val_acc", 0.55 + epoch * 0.07)
            self.metrics.record_metric(
                f"{model_id}/epoch/{epoch}/learning_rate", 0.01 * (0.9**epoch)
            )

        # Inference metrics
        for i in range(10):
            self.metrics.record_metric(f"{model_id}/inference/latency_ms", 20 + i * 3)
            self.metrics.record_metric(f"{model_id}/inference/memory_mb", 1000 + i * 50)

        # Worker metrics
        for worker_id in range(3):
            for i in range(10):
                self.metrics.record_metric(
                    f"workers/worker-{worker_id}/utilization", 0.5 + i * 0.05
                )
                self.metrics.record_metric(f"workers/worker-{worker_id}/memory_mb", 2000 + i * 100)
                self.metrics.record_metric(f"workers/worker-{worker_id}/active_tasks", 5 + i)

        # Dataset metrics
        for dataset in ["train", "val", "test"]:
            for i in range(5):
                self.metrics.record_metric(f"datasets/{dataset}/load_time_ms", 50 + i * 10)

        # Create visualization object
        self.viz = create_visualization(self.metrics, theme="light", interactive=True)

        # Create temp directory for output files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()

    def test_initialization(self):
        """Test visualization initialization."""
        # Test with metrics
        viz1 = AIMLVisualization(metrics=self.metrics)
        self.assertEqual(viz1.metrics, self.metrics)

        # Test without metrics
        viz2 = AIMLVisualization()
        self.assertIsNone(viz2.metrics)

        # Test with metrics setter
        viz2.metrics = self.metrics
        self.assertEqual(viz2.metrics, self.metrics)

        # Test theme setting
        viz3 = AIMLVisualization(theme="dark")
        self.assertEqual(viz3.theme, "dark")

        # Test interactive setting
        viz4 = AIMLVisualization(interactive=False)
        self.assertFalse(viz4.interactive)

    def test_library_detection(self):
        """Test visualization library detection."""
        libraries = check_visualization_libraries()
        self.assertIsInstance(libraries, dict)
        self.assertIn("matplotlib", libraries)
        self.assertIn("plotly", libraries)
        self.assertIn("pandas", libraries)
        self.assertIn("jupyter", libraries)

    @unittest.skipIf(not MATPLOTLIB_AVAILABLE, "Matplotlib not available")
    def test_plot_training_metrics(self):
        """Test training metrics visualization with Matplotlib."""
        # Create a visualization with static plots
        viz = create_visualization(self.metrics, interactive=False)

        # Plot training metrics
        fig = viz.plot_training_metrics(model_id="test_model", show_plot=False)

        # Check that we got a figure back
        self.assertIsNotNone(fig)

        # Test export
        output_path = self.output_dir / "training_metrics.png"
        viz.export_plot(fig, str(output_path))
        self.assertTrue(output_path.exists())

    @unittest.skipIf(not PLOTLY_AVAILABLE, "Plotly not available")
    def test_plot_training_metrics_interactive(self):
        """Test interactive training metrics visualization with Plotly."""
        # Create a visualization with interactive plots
        viz = create_visualization(self.metrics, interactive=True)

        # Plot training metrics
        fig = viz.plot_training_metrics(model_id="test_model", show_plot=False)

        # Check that we got a figure back
        self.assertIsNotNone(fig)

        # Test export
        output_path = self.output_dir / "training_metrics_interactive.html"
        viz.export_plot(fig, str(output_path))
        self.assertTrue(output_path.exists())

    @unittest.skipIf(not MATPLOTLIB_AVAILABLE, "Matplotlib not available")
    def test_plot_inference_latency(self):
        """Test inference latency visualization."""
        # Plot inference latency
        fig = self.viz.plot_inference_latency(model_id="test_model", show_plot=False)

        # Check that we got a figure back
        self.assertIsNotNone(fig)

        # Test export
        output_path = self.output_dir / "inference_latency.png"
        self.viz.export_plot(fig, str(output_path))
        self.assertTrue(output_path.exists())

    @unittest.skipIf(not MATPLOTLIB_AVAILABLE, "Matplotlib not available")
    def test_plot_worker_utilization(self):
        """Test worker utilization visualization."""
        # Plot worker utilization
        fig = self.viz.plot_worker_utilization(show_plot=False)

        # Check that we got a figure back
        self.assertIsNotNone(fig)

        # Test export
        output_path = self.output_dir / "worker_utilization.png"
        self.viz.export_plot(fig, str(output_path))
        self.assertTrue(output_path.exists())

    @unittest.skipIf(not MATPLOTLIB_AVAILABLE, "Matplotlib not available")
    def test_plot_dataset_load_times(self):
        """Test dataset load times visualization."""
        # Plot dataset load times
        fig = self.viz.plot_dataset_load_times(show_plot=False)

        # Check that we got a figure back
        self.assertIsNotNone(fig)

        # Test export
        output_path = self.output_dir / "dataset_load_times.png"
        self.viz.export_plot(fig, str(output_path))
        self.assertTrue(output_path.exists())

    @unittest.skipIf(not MATPLOTLIB_AVAILABLE, "Matplotlib not available")
    def test_plot_comprehensive_dashboard(self):
        """Test comprehensive dashboard visualization."""
        # Plot comprehensive dashboard
        fig = self.viz.plot_comprehensive_dashboard(show_plot=False)

        # Check that we got a figure back
        self.assertIsNotNone(fig)

        # Test export
        output_path = self.output_dir / "comprehensive_dashboard.png"
        self.viz.export_plot(fig, str(output_path))
        self.assertTrue(output_path.exists())

    def test_generate_html_report(self):
        """Test HTML report generation."""
        # Generate HTML report
        output_path = self.output_dir / "report.html"
        html = self.viz.generate_html_report(str(output_path))

        # Check that we got HTML back
        self.assertIsInstance(html, str)
        self.assertIn("<html", html)

        # Check that the file was created
        self.assertTrue(output_path.exists())

        # Check content
        with open(output_path, "r") as f:
            content = f.read()
            self.assertIn("<html", content)
            self.assertIn("AI/ML Performance Report", content)

    def test_export_visualizations(self):
        """Test exporting all visualizations."""
        # Export all visualizations
        result = self.viz.export_visualizations(
            str(self.output_dir), formats=["png", "html", "json"]
        )

        # Check that we got a result dictionary
        self.assertIsInstance(result, dict)

        # Check that files were created
        for viz_type, files in result.items():
            for file_path in files:
                self.assertTrue(os.path.exists(file_path))

    @patch("ipfs_kit_py.ai_ml_visualization.MATPLOTLIB_AVAILABLE", False)
    @patch("ipfs_kit_py.ai_ml_visualization.PLOTLY_AVAILABLE", False)
    def test_graceful_degradation(self):
        """Test graceful degradation when visualization libraries are not available."""
        # Create visualization with both libraries mocked as unavailable
        viz = create_visualization(self.metrics)

        # Attempt to plot
        result = viz.plot_training_metrics(model_id="test_model", show_plot=False)

        # Check that we got a text representation back
        self.assertIsInstance(result, str)
        self.assertIn("Text-based summary", result)

    def test_factory_function(self):
        """Test the visualization factory function."""
        # Create a visualization with the factory function
        viz = create_visualization(metrics=self.metrics, theme="dark", interactive=False)

        # Check that we got the right object
        self.assertIsInstance(viz, AIMLVisualization)
        self.assertEqual(viz.metrics, self.metrics)
        self.assertEqual(viz.theme, "dark")
        self.assertFalse(viz.interactive)


if __name__ == "__main__":
    unittest.main()
