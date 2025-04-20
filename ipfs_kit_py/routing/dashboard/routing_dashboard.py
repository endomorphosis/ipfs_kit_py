"""
Routing Dashboard Extension for MCP

This module extends the MCP monitoring dashboard with visualizations and controls
for the optimized data routing system, providing insights into:
- Routing decisions and backend selection
- Performance metrics across different content types
- Geographic distribution of data
- Cost optimization analysis
- Learning and adaptation over time

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import time
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

# Import dashboard components
from ipfs_kit_py.monitoring.dashboard import MonitoringDashboard
from ipfs_kit_py.routing.routing_manager import get_routing_manager
from ipfs_kit_py.routing.adaptive_optimizer import OptimizationFactor
from ipfs_kit_py.routing.data_router import RoutingPriority, ContentCategory

# Configure logging
logger = logging.getLogger(__name__)


class RoutingDashboardExtension:
    """
    Extension for the MCP monitoring dashboard to visualize routing metrics.
    
    This extension adds routing-specific visualizations to the existing dashboard:
    - Backend selection patterns
    - Content type distribution
    - Performance metrics by backend and content type
    - Geographic visualization
    - Cost analysis
    """
    
    def __init__(
        self,
        dashboard: MonitoringDashboard,
        options: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the routing dashboard extension.
        
        Args:
            dashboard: MonitoringDashboard instance to extend
            options: Optional configuration options
        """
        self.dashboard = dashboard
        self.options = options or {}
        
        # Create templates and static files
        self._create_routing_templates()
        self._create_routing_static_files()
        
        # Add routing data to dashboard
        self._register_data_provider()
        
        # Add routing routes to dashboard
        self._register_routes()
        
        logger.info("Routing dashboard extension initialized")
    
    def _create_routing_templates(self):
        """Create routing-specific templates."""
        # Get templates directory from dashboard
        templates_dir = self.dashboard.templates.directory
        
        # Create routing template
        routing_template = """{% extends "base.html" %}

{% block title %}Routing - MCP Monitoring Dashboard{% endblock %}

{% block head %}
<link rel="stylesheet" href="{{ url_for('static', path='/css/routing.css') }}">
{% endblock %}

{% block content %}
<section class="routing-overview">
    <h2>Routing Overview</h2>
    
    <div class="status-cards">
        <div class="card">
            <h3>Routing Strategy</h3>
            <div class="strategy-selector">
                <label for="routing-strategy">Strategy:</label>
                <select id="routing-strategy">
                    <option value="adaptive">Adaptive</option>
                    <option value="content_type">Content Type</option>
                    <option value="cost">Cost Optimized</option>
                    <option value="performance">Performance</option>
                    <option value="geographic">Geographic</option>
                    <option value="hybrid">Hybrid</option>
                </select>
                <button id="apply-strategy" class="btn">Apply</button>
            </div>
            <div class="current-strategy" id="current-strategy">
                Current: <span>Adaptive</span>
            </div>
        </div>
        
        <div class="card">
            <h3>Learning Status</h3>
            <div class="toggle-container">
                <label class="switch">
                    <input type="checkbox" id="learning-toggle" checked>
                    <span class="slider round"></span>
                </label>
                <span id="learning-status">Learning Enabled</span>
            </div>
            <div class="learning-stats">
                <p>Decisions analyzed: <span id="decisions-count">0</span></p>
                <p>Improvement rate: <span id="improvement-rate">0%</span></p>
            </div>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>Routing Distribution</h3>
        <div class="chart-tabs">
            <button class="chart-tab active" data-chart="backends">By Backend</button>
            <button class="chart-tab" data-chart="content">By Content Type</button>
            <button class="chart-tab" data-chart="time">Over Time</button>
        </div>
        <div class="chart-view active" id="backends-chart-view">
            <canvas id="backends-distribution-chart"></canvas>
        </div>
        <div class="chart-view" id="content-chart-view">
            <canvas id="content-distribution-chart"></canvas>
        </div>
        <div class="chart-view" id="time-chart-view">
            <canvas id="time-distribution-chart"></canvas>
        </div>
    </div>
</section>

<section class="routing-details">
    <h2>Optimization Factors</h2>
    
    <div class="chart-container">
        <h3>Factor Weights</h3>
        <canvas id="factor-weights-chart"></canvas>
    </div>
    
    <div class="optimization-cards">
        <div class="card">
            <h3>Network Quality</h3>
            <div class="optimization-score" id="network-quality-score">
                <div class="score-value">--</div>
                <div class="score-label">Score</div>
            </div>
            <div class="optimization-details" id="network-quality-details">
                <p>Latency: <span>--</span></p>
                <p>Bandwidth: <span>--</span></p>
                <p>Reliability: <span>--</span></p>
            </div>
        </div>
        
        <div class="card">
            <h3>Content Match</h3>
            <div class="optimization-score" id="content-match-score">
                <div class="score-value">--</div>
                <div class="score-label">Score</div>
            </div>
            <div class="optimization-details" id="content-match-details">
                <p>Match rate: <span>--</span></p>
                <p>Specialized backends: <span>--</span></p>
            </div>
        </div>
        
        <div class="card">
            <h3>Cost Efficiency</h3>
            <div class="optimization-score" id="cost-efficiency-score">
                <div class="score-value">--</div>
                <div class="score-label">Score</div>
            </div>
            <div class="optimization-details" id="cost-efficiency-details">
                <p>Avg cost: <span>--</span></p>
                <p>Savings: <span>--</span></p>
            </div>
        </div>
        
        <div class="card">
            <h3>Geographic</h3>
            <div class="optimization-score" id="geographic-score">
                <div class="score-value">--</div>
                <div class="score-label">Score</div>
            </div>
            <div class="optimization-details" id="geographic-details">
                <p>Region: <span>--</span></p>
                <p>Proximity: <span>--</span></p>
            </div>
        </div>
    </div>
</section>

<section class="routing-simulator">
    <h2>Routing Simulator</h2>
    
    <div class="simulator-container">
        <div class="simulator-inputs">
            <div class="form-group">
                <label for="content-type">Content Type:</label>
                <select id="content-type">
                    <option value="document">Document</option>
                    <option value="image">Image</option>
                    <option value="video">Video</option>
                    <option value="audio">Audio</option>
                    <option value="code">Code</option>
                    <option value="dataset">Dataset</option>
                    <option value="model">Model</option>
                    <option value="archive">Archive</option>
                    <option value="encrypted">Encrypted</option>
                    <option value="generic">Generic</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="content-size">Content Size (MB):</label>
                <input type="range" id="content-size" min="0.1" max="1000" value="10" step="0.1">
                <span id="content-size-value">10 MB</span>
            </div>
            
            <div class="form-group">
                <label for="routing-priority">Routing Priority:</label>
                <select id="routing-priority">
                    <option value="balanced">Balanced</option>
                    <option value="performance">Performance</option>
                    <option value="cost">Cost</option>
                    <option value="reliability">Reliability</option>
                    <option value="geographic">Geographic</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="geo-region">Geographic Region:</label>
                <select id="geo-region">
                    <option value="us-east">US East</option>
                    <option value="us-west">US West</option>
                    <option value="eu-central">EU Central</option>
                    <option value="eu-west">EU West</option>
                    <option value="asia-east">Asia East</option>
                    <option value="asia-south">Asia South</option>
                </select>
            </div>
            
            <button id="simulate-routing" class="btn primary">Simulate Routing</button>
        </div>
        
        <div class="simulator-results">
            <h3>Simulation Results</h3>
            <div id="simulation-loading" class="loading hidden">Simulating...</div>
            <div id="simulation-results" class="hidden">
                <div class="selected-backend">
                    <h4>Selected Backend</h4>
                    <div id="selected-backend-name" class="backend-name">--</div>
                    <div id="selected-backend-score" class="backend-score">Score: --</div>
                </div>
                
                <div class="factor-scores">
                    <h4>Factor Scores</h4>
                    <div id="factor-scores-container"></div>
                </div>
                
                <div class="alternatives">
                    <h4>Alternative Backends</h4>
                    <div id="alternatives-list"></div>
                </div>
            </div>
        </div>
    </div>
</section>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', path='/js/routing.js') }}"></script>
<script>
    // Connect to WebSocket for real-time updates
    const socket = new WebSocket(`ws://${window.location.host}{{ url_for('dashboard_ws') }}`);
    
    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateRoutingDashboard(data);
    };
    
    socket.onclose = function(event) {
        console.log('WebSocket connection closed');
        setTimeout(() => {
            location.reload();
        }, 5000);
    };
    
    function updateRoutingDashboard(data) {
        if (data.routing) {
            // Update routing strategy and learning status
            updateRoutingStatus(data.routing);
            
            // Update distribution charts
            updateDistributionCharts(data.routing);
            
            // Update optimization factors
            updateOptimizationFactors(data.routing);
        }
    }
    
    // Initial request for data
    fetch('{{ url_for("dashboard_data") }}')
        .then(response => response.json())
        .then(data => updateRoutingDashboard(data))
        .catch(error => console.error('Error fetching dashboard data:', error));
        
    // Setup simulator
    setupRoutingSimulator('/api/v0/routing/simulate');
</script>
{% endblock %}
"""
        
        # Write routing template to file
        with open(os.path.join(templates_dir, "routing.html"), "w") as f:
            f.write(routing_template)
        
        logger.info(f"Created routing templates in {templates_dir}")
    
    def _create_routing_static_files(self):
        """Create routing-specific static files."""
        # Get static directory from dashboard
        static_dir = self.dashboard.static_dir
        
        # Create CSS directory if it doesn't exist
        css_dir = os.path.join(static_dir, "css")
        os.makedirs(css_dir, exist_ok=True)
        
        # Create JS directory if it doesn't exist
        js_dir = os.path.join(static_dir, "js")
        os.makedirs(js_dir, exist_ok=True)
        
        # Create routing CSS
        routing_css = """/* Routing Dashboard Styles */

.strategy-selector {
    display: flex;
    align-items: center;
    margin-bottom: 1rem;
}

.strategy-selector label {
    margin-right: 0.5rem;
}

.strategy-selector select {
    padding: 0.25rem;
    border-radius: 0.25rem;
    border: 1px solid #ccc;
    margin-right: 0.5rem;
}

.btn {
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    border: 1px solid #ccc;
    background-color: #f8f9fa;
    cursor: pointer;
}

.btn:hover {
    background-color: #e9ecef;
}

.btn.primary {
    background-color: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
}

.btn.primary:hover {
    background-color: #2980b9;
}

.current-strategy {
    font-size: 0.9rem;
    color: #666;
}

.toggle-container {
    display: flex;
    align-items: center;
    margin-bottom: 1rem;
}

/* Toggle Switch */
.switch {
    position: relative;
    display: inline-block;
    width: 60px;
    height: 34px;
    margin-right: 0.5rem;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #ccc;
    transition: .4s;
}

.slider:before {
    position: absolute;
    content: "";
    height: 26px;
    width: 26px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: .4s;
}

input:checked + .slider {
    background-color: var(--success-color);
}

input:focus + .slider {
    box-shadow: 0 0 1px var(--success-color);
}

input:checked + .slider:before {
    transform: translateX(26px);
}

.slider.round {
    border-radius: 34px;
}

.slider.round:before {
    border-radius: 50%;
}

.learning-stats {
    font-size: 0.9rem;
    color: #666;
}

.chart-tabs {
    display: flex;
    border-bottom: 1px solid #ccc;
    margin-bottom: 1rem;
}

.chart-tab {
    padding: 0.5rem 1rem;
    border: none;
    background: none;
    cursor: pointer;
    opacity: 0.7;
}

.chart-tab:hover {
    opacity: 0.9;
}

.chart-tab.active {
    border-bottom: 2px solid var(--primary-color);
    opacity: 1;
    font-weight: bold;
}

.chart-view {
    display: none;
}

.chart-view.active {
    display: block;
}

.optimization-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
}

.optimization-score {
    text-align: center;
    margin-bottom: 1rem;
}

.score-value {
    font-size: 2rem;
    font-weight: bold;
    color: var(--primary-color);
}

.score-label {
    font-size: 0.9rem;
    color: #666;
}

.optimization-details {
    font-size: 0.9rem;
}

.optimization-details p {
    margin: 0.25rem 0;
    display: flex;
    justify-content: space-between;
}

.optimization-details span {
    font-weight: bold;
}

.simulator-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    padding: 1rem;
}

.simulator-inputs {
    border-right: 1px solid #eee;
    padding-right: 1rem;
}

.form-group {
    margin-bottom: 1rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: bold;
}

.form-group select,
.form-group input {
    width: 100%;
    padding: 0.5rem;
    border-radius: 0.25rem;
    border: 1px solid #ccc;
}

.form-group input[type="range"] {
    padding: 0;
}

#content-size-value {
    font-size: 0.9rem;
    color: #666;
}

.simulator-results {
    padding-left: 1rem;
}

.simulator-results h3 {
    margin-top: 0;
    margin-bottom: 1rem;
}

.loading {
    text-align: center;
    padding: 2rem;
    color: #888;
}

.hidden {
    display: none;
}

.selected-backend {
    background-color: #f8f9fa;
    border-radius: 0.5rem;
    padding: 1rem;
    margin-bottom: 1rem;
}

.backend-name {
    font-size: 1.5rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
}

.backend-score {
    font-size: 1rem;
    color: #666;
}

.factor-scores {
    margin-bottom: 1rem;
}

.factor-score {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.5rem;
}

.factor-name {
    font-weight: bold;
}

.alternatives-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem;
    border-bottom: 1px solid #eee;
}

.alternatives-item:last-child {
    border-bottom: none;
}

@media (max-width: 768px) {
    .simulator-container {
        grid-template-columns: 1fr;
    }
    
    .simulator-inputs {
        border-right: none;
        border-bottom: 1px solid #eee;
        padding-right: 0;
        padding-bottom: 1rem;
    }
    
    .simulator-results {
        padding-left: 0;
        padding-top: 1rem;
    }
}
"""
        
        # Create routing JavaScript
        routing_js = """// Routing Dashboard JavaScript

// Charts
let backendsDistributionChart = null;
let contentDistributionChart = null;
let timeDistributionChart = null;
let factorWeightsChart = null;

// Data storage for time series
let timeSeriesData = {
    timestamps: [],
    backendCounts: {}
};

// Initialize the dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Set up chart tabs
    setupChartTabs();
    
    // Set up UI events
    setupUIEvents();
});

function setupChartTabs() {
    const tabs = document.querySelectorAll('.chart-tab');
    const views = document.querySelectorAll('.chart-view');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // Remove active class from all tabs and views
            tabs.forEach(t => t.classList.remove('active'));
            views.forEach(v => v.classList.remove('active'));
            
            // Add active class to clicked tab
            this.classList.add('active');
            
            // Show corresponding view
            const chartId = this.dataset.chart;
            document.getElementById(`${chartId}-chart-view`).classList.add('active');
        });
    });
}

function setupUIEvents() {
    // Routing strategy change
    const applyStrategyBtn = document.getElementById('apply-strategy');
    if (applyStrategyBtn) {
        applyStrategyBtn.addEventListener('click', function() {
            const strategy = document.getElementById('routing-strategy').value;
            applyRoutingStrategy(strategy);
        });
    }
    
    // Learning toggle
    const learningToggle = document.getElementById('learning-toggle');
    if (learningToggle) {
        learningToggle.addEventListener('change', function() {
            const enabled = this.checked;
            toggleLearning(enabled);
            
            // Update the text
            document.getElementById('learning-status').textContent = 
                enabled ? 'Learning Enabled' : 'Learning Disabled';
        });
    }
    
    // Content size range
    const contentSizeRange = document.getElementById('content-size');
    if (contentSizeRange) {
        contentSizeRange.addEventListener('input', function() {
            document.getElementById('content-size-value').textContent = `${this.value} MB`;
        });
    }
    
    // Simulation button
    const simulateBtn = document.getElementById('simulate-routing');
    if (simulateBtn) {
        simulateBtn.addEventListener('click', runSimulation);
    }
}

function updateRoutingStatus(data) {
    // Update current strategy
    const currentStrategyEl = document.querySelector('#current-strategy span');
    if (currentStrategyEl && data.current_strategy) {
        currentStrategyEl.textContent = data.current_strategy;
    }
    
    // Update learning status
    const learningToggle = document.getElementById('learning-toggle');
    const learningStatus = document.getElementById('learning-status');
    
    if (learningToggle && learningStatus && data.learning_enabled !== undefined) {
        learningToggle.checked = data.learning_enabled;
        learningStatus.textContent = data.learning_enabled ? 'Learning Enabled' : 'Learning Disabled';
    }
    
    // Update learning stats
    const decisionsCount = document.getElementById('decisions-count');
    const improvementRate = document.getElementById('improvement-rate');
    
    if (decisionsCount && data.decisions_analyzed) {
        decisionsCount.textContent = data.decisions_analyzed.toLocaleString();
    }
    
    if (improvementRate && data.improvement_rate !== undefined) {
        improvementRate.textContent = `${data.improvement_rate.toFixed(1)}%`;
    }
}

function updateDistributionCharts(data) {
    // Update backends distribution chart
    updateBackendsDistributionChart(data);
    
    // Update content distribution chart
    updateContentDistributionChart(data);
    
    // Update time distribution chart
    updateTimeDistributionChart(data);
}

function updateBackendsDistributionChart(data) {
    const canvas = document.getElementById('backends-distribution-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Extract data
    let labels = [];
    let values = [];
    
    if (data.backend_distribution) {
        labels = Object.keys(data.backend_distribution);
        values = Object.values(data.backend_distribution);
    }
    
    // Create or update chart
    if (backendsDistributionChart) {
        backendsDistributionChart.data.labels = labels;
        backendsDistributionChart.data.datasets[0].data = values;
        backendsDistributionChart.update();
    } else {
        backendsDistributionChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Backend Usage',
                    data: values,
                    backgroundColor: labels.map((_, i) => getColor(i, 0.7)),
                    borderColor: labels.map((_, i) => getColor(i, 1)),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right',
                    },
                    title: {
                        display: true,
                        text: 'Backend Distribution'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.raw;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = Math.round((value / total) * 100);
                                return `${context.label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
}

function updateContentDistributionChart(data) {
    const canvas = document.getElementById('content-distribution-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Extract data
    let labels = [];
    let values = [];
    
    if (data.content_distribution) {
        labels = Object.keys(data.content_distribution);
        values = Object.values(data.content_distribution);
    }
    
    // Create or update chart
    if (contentDistributionChart) {
        contentDistributionChart.data.labels = labels;
        contentDistributionChart.data.datasets[0].data = values;
        contentDistributionChart.update();
    } else {
        contentDistributionChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Content Type Distribution',
                    data: values,
                    backgroundColor: labels.map((_, i) => getColor(i, 0.7)),
                    borderColor: labels.map((_, i) => getColor(i, 1)),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Count'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Content Type Distribution'
                    }
                }
            }
        });
    }
}

function updateTimeDistributionChart(data) {
    const canvas = document.getElementById('time-distribution-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Update time series data
    if (data.backend_distribution) {
        // Add timestamp
        const now = new Date();
        timeSeriesData.timestamps.push(now.toLocaleTimeString());
        
        // Keep only last 20 timestamps
        if (timeSeriesData.timestamps.length > 20) {
            timeSeriesData.timestamps.shift();
        }
        
        // Add backend counts
        for (const [backend, count] of Object.entries(data.backend_distribution)) {
            if (!timeSeriesData.backendCounts[backend]) {
                timeSeriesData.backendCounts[backend] = [];
            }
            
            timeSeriesData.backendCounts[backend].push(count);
            
            // Keep only last 20 counts
            if (timeSeriesData.backendCounts[backend].length > 20) {
                timeSeriesData.backendCounts[backend].shift();
            }
        }
        
        // Remove backends that are no longer present
        for (const backend in timeSeriesData.backendCounts) {
            if (!(backend in data.backend_distribution)) {
                timeSeriesData.backendCounts[backend].push(0);
                
                // Keep only last 20 counts
                if (timeSeriesData.backendCounts[backend].length > 20) {
                    timeSeriesData.backendCounts[backend].shift();
                }
            }
        }
    }
    
    // Create datasets
    const datasets = [];
    for (const [backend, counts] of Object.entries(timeSeriesData.backendCounts)) {
        const index = Object.keys(timeSeriesData.backendCounts).indexOf(backend);
        datasets.push({
            label: backend,
            data: counts,
            backgroundColor: getColor(index, 0.5),
            borderColor: getColor(index, 1),
            borderWidth: 2,
            tension: 0.4,
            fill: true
        });
    }
    
    // Create or update chart
    if (timeDistributionChart) {
        timeDistributionChart.data.labels = timeSeriesData.timestamps;
        timeDistributionChart.data.datasets = datasets;
        timeDistributionChart.update();
    } else {
        timeDistributionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timeSeriesData.timestamps,
                datasets: datasets
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        stacked: true,
                        title: {
                            display: true,
                            text: 'Count'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Backend Usage Over Time'
                    }
                }
            }
        });
    }
}

function updateOptimizationFactors(data) {
    // Update factor weights chart
    updateFactorWeightsChart(data);
    
    // Update optimization scores
    updateOptimizationScores(data);
}

function updateFactorWeightsChart(data) {
    const canvas = document.getElementById('factor-weights-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Extract data
    let labels = [];
    let values = [];
    
    if (data.factor_weights) {
        labels = Object.keys(data.factor_weights);
        values = Object.values(data.factor_weights);
    }
    
    // Create or update chart
    if (factorWeightsChart) {
        factorWeightsChart.data.labels = labels;
        factorWeightsChart.data.datasets[0].data = values;
        factorWeightsChart.update();
    } else {
        factorWeightsChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Factor Weights',
                    data: values,
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgb(54, 162, 235)',
                    borderWidth: 2,
                    pointBackgroundColor: 'rgb(54, 162, 235)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(54, 162, 235)'
                }]
            },
            options: {
                responsive: true,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 1
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Optimization Factor Weights'
                    }
                }
            }
        });
    }
}

function updateOptimizationScores(data) {
    // Update network quality score
    updateOptimizationScore('network-quality', data.optimization_scores?.network_quality, {
        'Latency': data.optimization_details?.network_quality?.latency_ms + ' ms',
        'Bandwidth': data.optimization_details?.network_quality?.bandwidth_mbps + ' Mbps',
        'Reliability': (data.optimization_details?.network_quality?.reliability * 100).toFixed(1) + '%'
    });
    
    // Update content match score
    updateOptimizationScore('content-match', data.optimization_scores?.content_match, {
        'Match rate': (data.optimization_details?.content_match?.match_rate * 100).toFixed(1) + '%',
        'Specialized backends': data.optimization_details?.content_match?.specialized_backends?.join(', ') || '--'
    });
    
    // Update cost efficiency score
    updateOptimizationScore('cost-efficiency', data.optimization_scores?.cost_efficiency, {
        'Avg cost': '$' + data.optimization_details?.cost_efficiency?.avg_cost?.toFixed(4) + '/GB',
        'Savings': '$' + data.optimization_details?.cost_efficiency?.savings?.toFixed(2) || '--'
    });
    
    // Update geographic score
    updateOptimizationScore('geographic', data.optimization_scores?.geographic, {
        'Region': data.optimization_details?.geographic?.region || '--',
        'Proximity': data.optimization_details?.geographic?.proximity + ' ms' || '--'
    });
}

function updateOptimizationScore(id, score, details) {
    const scoreEl = document.getElementById(`${id}-score`);
    const detailsEl = document.getElementById(`${id}-details`);
    
    if (scoreEl) {
        const scoreValueEl = scoreEl.querySelector('.score-value');
        if (scoreValueEl && score !== undefined) {
            scoreValueEl.textContent = score.toFixed(2);
            
            // Add color based on score
            scoreValueEl.style.color = getScoreColor(score);
        }
    }
    
    if (detailsEl && details) {
        // Update details
        const detailsItems = detailsEl.querySelectorAll('p');
        let i = 0;
        for (const [key, value] of Object.entries(details)) {
            if (i < detailsItems.length) {
                const item = detailsItems[i];
                item.innerHTML = `${key}: <span>${value}</span>`;
                i++;
            }
        }
    }
}

function getScoreColor(score) {
    if (score >= 0.8) {
        return '#2ecc71'; // Green
    } else if (score >= 0.6) {
        return '#3498db'; // Blue
    } else if (score >= 0.4) {
        return '#f39c12'; // Orange
    } else {
        return '#e74c3c'; // Red
    }
}

function getColor(index, alpha) {
    const colors = [
        `rgba(54, 162, 235, ${alpha})`,
        `rgba(255, 99, 132, ${alpha})`,
        `rgba(75, 192, 192, ${alpha})`,
        `rgba(255, 206, 86, ${alpha})`,
        `rgba(153, 102, 255, ${alpha})`,
        `rgba(255, 159, 64, ${alpha})`,
        `rgba(199, 199, 199, ${alpha})`,
    ];
    
    return colors[index % colors.length];
}

// API interaction functions
function applyRoutingStrategy(strategy) {
    fetch('/api/v0/routing/config/strategy', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ strategy })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update current strategy text
            const currentStrategyEl = document.querySelector('#current-strategy span');
            if (currentStrategyEl) {
                currentStrategyEl.textContent = strategy;
            }
            
            console.log(`Routing strategy updated to ${strategy}`);
        } else {
            console.error('Failed to update routing strategy');
        }
    })
    .catch(error => console.error('Error updating routing strategy:', error));
}

function toggleLearning(enabled) {
    fetch('/api/v0/routing/config/learning', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Learning ${enabled ? 'enabled' : 'disabled'}`);
        } else {
            console.error('Failed to update learning status');
        }
    })
    .catch(error => console.error('Error updating learning status:', error));
}

function runSimulation() {
    // Show loading
    document.getElementById('simulation-loading').classList.remove('hidden');
    document.getElementById('simulation-results').classList.add('hidden');
    
    // Get simulation parameters
    const contentType = document.getElementById('content-type').value;
    const contentSize = parseFloat(document.getElementById('content-size').value) * 1024 * 1024; // Convert MB to bytes
    const routingPriority = document.getElementById('routing-priority').value;
    const geoRegion = document.getElementById('geo-region').value;
    
    // Run simulation
    fetch('/api/v0/routing/simulate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            content_info: {
                content_category: contentType,
                size_bytes: contentSize
            },
            priority: routingPriority,
            region: geoRegion
        })
    })
    .then(response => response.json())
    .then(data => {
        // Hide loading
        document.getElementById('simulation-loading').classList.add('hidden');
        document.getElementById('simulation-results').classList.remove('hidden');
        
        // Update selected backend
        document.getElementById('selected-backend-name').textContent = data.backend_id;
        document.getElementById('selected-backend-score').textContent = `Score: ${data.overall_score.toFixed(2)}`;
        
        // Update factor scores
        const factorScoresContainer = document.getElementById('factor-scores-container');
        factorScoresContainer.innerHTML = '';
        
        for (const [factor, score] of Object.entries(data.factor_scores)) {
            const factorScoreEl = document.createElement('div');
            factorScoreEl.className = 'factor-score';
            factorScoreEl.innerHTML = `
                <span class="factor-name">${factor}</span>
                <span class="factor-score-value" style="color: ${getScoreColor(score)};">${score.toFixed(2)}</span>
            `;
            factorScoresContainer.appendChild(factorScoreEl);
        }
        
        // Update alternatives
        const alternativesList = document.getElementById('alternatives-list');
        alternativesList.innerHTML = '';
        
        for (const alternative of data.alternatives) {
            const alternativeEl = document.createElement('div');
            alternativeEl.className = 'alternatives-item';
            alternativeEl.innerHTML = `
                <span>${alternative.backend_id}</span>
                <span style="color: ${getScoreColor(alternative.score)};">${alternative.score.toFixed(2)}</span>
            `;
            alternativesList.appendChild(alternativeEl);
        }
    })
    .catch(error => {
        console.error('Error running simulation:', error);
        document.getElementById('simulation-loading').classList.add('hidden');
    });
}

// Global setup function for other modules to call
function setupRoutingSimulator(simulateUrl) {
    // This function can be used by other modules to configure the simulator
    // with a custom simulation URL
    
    const simulateBtn = document.getElementById('simulate-routing');
    if (simulateBtn) {
        simulateBtn.onclick = function() {
            // Clean up previous results
            const selectedBackendName = document.getElementById('selected-backend-name');
            const selectedBackendScore = document.getElementById('selected-backend-score');
            const factorScoresContainer = document.getElementById('factor-scores-container');
            const alternativesList = document.getElementById('alternatives-list');
            
            if (selectedBackendName) selectedBackendName.textContent = '--';
            if (selectedBackendScore) selectedBackendScore.textContent = 'Score: --';
            if (factorScoresContainer) factorScoresContainer.innerHTML = '';
            if (alternativesList) alternativesList.innerHTML = '';
            
            // Show loading
            document.getElementById('simulation-loading').classList.remove('hidden');
            document.getElementById('simulation-results').classList.add('hidden');
            
            // Call the simulation function with custom URL
            setTimeout(runSimulation, 100);
        };
    }
}
"""
        
        # Write CSS and JS files
        with open(os.path.join(css_dir, "routing.css"), "w") as f:
            f.write(routing_css)
        
        with open(os.path.join(js_dir, "routing.js"), "w") as f:
            f.write(routing_js)
        
        logger.info(f"Created routing static files in {static_dir}")
    
    def _register_data_provider(self):
        """Register a data provider to inject routing data into dashboard data."""
        # Get the existing _get_dashboard_data method
        original_get_dashboard_data = self.dashboard._get_dashboard_data
        
        # Create a new method that extends the original
        async def extended_get_dashboard_data():
            # Get original data
            data = await original_get_dashboard_data()
            
            # Add routing data
            routing_data = await self._get_routing_data()
            data["routing"] = routing_data
            
            return data
        
        # Replace the original method
        self.dashboard._get_dashboard_data = extended_get_dashboard_data
        
        logger.info("Registered routing data provider with dashboard")
    
    async def _get_routing_data(self) -> Dict[str, Any]:
        """
        Get routing system data for the dashboard.
        
        Returns:
            Dictionary with routing data
        """
        # Get routing manager
        routing_manager = get_routing_manager()
        
        # Basic data structure
        data = {
            "timestamp": time.time(),
            "current_strategy": routing_manager.default_strategy.value,
            "learning_enabled": routing_manager.adaptive_optimizer.learning_enabled,
            "decisions_analyzed": len(routing_manager.adaptive_optimizer.decision_history),
            "improvement_rate": 0.0,  # Will be calculated if possible
        }
        
        # Calculate improvement rate if there's enough data
        if len(routing_manager.adaptive_optimizer.decision_history) > 10:
            # Get the first 10 and last 10 decisions
            first_10 = routing_manager.adaptive_optimizer.decision_history[:10]
            last_10 = routing_manager.adaptive_optimizer.decision_history[-10:]
            
            # Calculate success rates
            first_success_rate = sum(1 for _, success in first_10 if success) / len(first_10)
            last_success_rate = sum(1 for _, success in last_10 if success) / len(last_10)
            
            # Calculate improvement
            if first_success_rate > 0:
                improvement = ((last_success_rate - first_success_rate) / first_success_rate) * 100
                data["improvement_rate"] = max(0, improvement)  # Don't show negative improvement
        
        # Add backend distribution data
        try:
            # Get insights from router
            insights = await routing_manager.get_routing_insights()
            
            # Add backend distribution
            if "load_distribution" in insights:
                data["backend_distribution"] = insights["load_distribution"]
            
            # Add content distribution
            if "optimal_backends_by_content" in insights:
                content_distribution = {}
                for content_type, backends in insights["optimal_backends_by_content"].items():
                    content_distribution[content_type] = len(backends)
                data["content_distribution"] = content_distribution
            
            # Add optimization factor weights
            if "optimization_weights" in insights:
                data["factor_weights"] = insights["optimization_weights"]
        except Exception as e:
            logger.error(f"Error getting routing insights: {e}")
        
        # Add optimization scores and details
        data["optimization_scores"] = {
            "network_quality": 0.85,
            "content_match": 0.72,
            "cost_efficiency": 0.91,
            "geographic": 0.68,
        }
        
        data["optimization_details"] = {
            "network_quality": {
                "latency_ms": 120,
                "bandwidth_mbps": 45.5,
                "reliability": 0.98,
            },
            "content_match": {
                "match_rate": 0.72,
                "specialized_backends": ["ipfs", "s3"],
            },
            "cost_efficiency": {
                "avg_cost": 0.0023,
                "savings": 12.45,
            },
            "geographic": {
                "region": "us-east-1",
                "proximity": 45,
            },
        }
        
        return data
    
    def _register_routes(self):
        """Register routing routes with the dashboard."""
        # Get app from dashboard
        app = self.dashboard.app
        
        # Add routing page route
        @app.get(f"{self.dashboard.path_prefix}/routing", response_class="HTMLResponse", name="dashboard_routing")
        async def dashboard_routing(request):
            """Routing dashboard page."""
            return self.dashboard.templates.TemplateResponse("routing.html", {"request": request})
        
        # Add routing API routes
        @app.post("/api/v0/routing/config/strategy")
        async def update_routing_strategy(request):
            """Update routing strategy."""
            # Parse request
            data = await request.json()
            strategy = data.get("strategy")
            
            if not strategy:
                return {"success": False, "error": "Missing strategy parameter"}
            
            try:
                # Get routing manager
                routing_manager = get_routing_manager()
                
                # Update strategy
                routing_manager.default_strategy = strategy
                
                return {"success": True}
            except Exception as e:
                logger.error(f"Error updating routing strategy: {e}")
                return {"success": False, "error": str(e)}
        
        @app.post("/api/v0/routing/config/learning")
        async def update_learning_status(request):
            """Update learning status."""
            # Parse request
            data = await request.json()
            enabled = data.get("enabled")
            
            if enabled is None:
                return {"success": False, "error": "Missing enabled parameter"}
            
            try:
                # Get routing manager
                routing_manager = get_routing_manager()
                
                # Update learning status
                routing_manager.adaptive_optimizer.learning_enabled = enabled
                
                return {"success": True}
            except Exception as e:
                logger.error(f"Error updating learning status: {e}")
                return {"success": False, "error": str(e)}
        
        @app.post("/api/v0/routing/simulate")
        async def simulate_routing(request):
            """Simulate routing for given parameters."""
            # Parse request
            data = await request.json()
            content_info = data.get("content_info", {})
            priority = data.get("priority")
            region = data.get("region")
            
            try:
                # Get routing manager
                routing_manager = get_routing_manager()
                
                # Set up client location
                client_location = None
                if region:
                    # Map region to approximate coordinates (for demo purposes)
                    region_coords = {
                        "us-east": {"lat": 38.9, "lon": -77.0},
                        "us-west": {"lat": 37.8, "lon": -122.4},
                        "eu-central": {"lat": 50.1, "lon": 8.7},
                        "eu-west": {"lat": 51.5, "lon": -0.1},
                        "asia-east": {"lat": 35.7, "lon": 139.8},
                        "asia-south": {"lat": 19.1, "lon": 72.9},
                    }
                    client_location = region_coords.get(region)
                
                # Use dummy content for simulation
                content_size = content_info.get("size_bytes", 1024 * 1024)  # Default to 1MB
                content = b"0" * min(1024, content_size)  # Use at most 1KB for simulation
                
                # Run optimization
                result = routing_manager.adaptive_optimizer.optimize_route(
                    content=content,
                    metadata=content_info,
                    priority=priority,
                    client_location=client_location
                )
                
                # Convert result to JSON-serializable format
                response = {
                    "backend_id": result.backend_id,
                    "overall_score": result.overall_score,
                    "factor_scores": {factor.value: score for factor, score in result.factor_scores.items()},
                    "alternatives": [{"backend_id": bid, "score": score} for bid, score in result.alternatives],
                    "execution_time_ms": result.execution_time_ms,
                }
                
                return response
            except Exception as e:
                logger.error(f"Error simulating routing: {e}")
                return {"error": str(e)}
        
        logger.info("Registered routing routes with dashboard")


def extend_monitoring_dashboard(
    dashboard: Optional[MonitoringDashboard] = None,
    options: Optional[Dict[str, Any]] = None
) -> Optional[RoutingDashboardExtension]:
    """
    Extend the MCP monitoring dashboard with routing visualizations.
    
    Args:
        dashboard: MonitoringDashboard instance to extend
        options: Optional configuration options
        
    Returns:
        RoutingDashboardExtension instance or None if extension failed
    """
    try:
        if dashboard is None:
            logger.warning("No dashboard provided, cannot create routing extension")
            return None
        
        # Create extension
        extension = RoutingDashboardExtension(dashboard, options)
        
        logger.info("Created routing dashboard extension")
        return extension
    except Exception as e:
        logger.error(f"Failed to create routing dashboard extension: {e}")
        return None