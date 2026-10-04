"""
Dashboard Charts Module for IPFS Kit

This module provides chart data generation for dashboards:
- Time-series chart data preparation
- Bar and pie chart data formatting
- Scatter plot data generation
- Line chart data with trends
- Real-time data streaming support
- Chart configuration management
- Export capabilities (JSON, CSV)

Part of Phase 10: Dashboard Enhancements
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json
import csv
from io import StringIO

logger = logging.getLogger(__name__)


@dataclass
class ChartConfig:
    """Chart configuration"""
    chart_id: str
    chart_type: str  # 'line', 'bar', 'pie', 'scatter'
    title: str
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    colors: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataPoint:
    """Single data point"""
    x: Any
    y: float
    label: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class ChartSeries:
    """Chart data series"""
    series_id: str
    name: str
    data_points: List[DataPoint]
    color: Optional[str] = None
    style: Optional[Dict] = None

    @property
    def data(self) -> List[DataPoint]:
        return self.data_points


@dataclass
class ChartData:
    """Complete chart data"""
    chart_id: str
    chart_type: str
    title: str
    series: List[ChartSeries]
    labels: Optional[List[str]] = None
    config: Optional[ChartConfig] = None
    timestamp: datetime = field(default_factory=datetime.now)


class ChartGenerator:
    """
    Generate chart data for dashboards
    
    Provides data preparation for various chart types
    in formats ready for visualization libraries.
    """
    
    def __init__(self):
        """Initialize chart generator"""
        self.default_colors = [
            '#3498db', '#2ecc71', '#e74c3c', '#f39c12',
            '#9b59b6', '#1abc9c', '#34495e', '#e67e22'
        ]
        
        logger.info("Chart Generator initialized")
    
    def generate_line_chart(
        self,
        config: ChartConfig,
        data_source: Dict[str, List[Tuple[Any, float]]],
        smooth: bool = False
    ) -> ChartData:
        """
        Generate line chart data
        
        Args:
            config: Chart configuration
            data_source: Dictionary mapping series names to (x, y) tuples
            smooth: Apply smoothing to lines
            
        Returns:
            ChartData object
        """
        series_list = []
        
        for idx, (series_name, points) in enumerate(data_source.items()):
            color = (config.colors[idx] if idx < len(config.colors)
                    else self.default_colors[idx % len(self.default_colors)])
            
            data_points = [
                DataPoint(x=x, y=y, label=str(x))
                for x, y in points
            ]
            
            series = ChartSeries(
                series_id=f"{config.chart_id}_{series_name}",
                name=series_name,
                data_points=data_points,
                color=color,
                style={'smooth': smooth}
            )
            
            series_list.append(series)
        
        return ChartData(
            chart_id=config.chart_id,
            chart_type='line',
            title=config.title,
            series=series_list,
            config=config
        )
    
    def generate_bar_chart(
        self,
        config: ChartConfig,
        data: Dict[str, float],
        horizontal: bool = False
    ) -> ChartData:
        """
        Generate bar chart data
        
        Args:
            config: Chart configuration
            data: Dictionary mapping labels to values
            horizontal: Create horizontal bars
            
        Returns:
            ChartData object
        """
        labels = list(data.keys())
        values = list(data.values())
        
        data_points = [
            DataPoint(x=label, y=value, label=label)
            for label, value in zip(labels, values)
        ]
        
        color = config.colors[0] if config.colors else self.default_colors[0]
        
        series = ChartSeries(
            series_id=f"{config.chart_id}_bars",
            name=config.title,
            data_points=data_points,
            color=color,
            style={'horizontal': horizontal}
        )
        
        return ChartData(
            chart_id=config.chart_id,
            chart_type='bar',
            title=config.title,
            series=[series],
            labels=labels,
            config=config
        )
    
    def generate_pie_chart(
        self,
        config: ChartConfig,
        data: Dict[str, float],
        show_percentages: bool = True
    ) -> ChartData:
        """
        Generate pie chart data
        
        Args:
            config: Chart configuration
            data: Dictionary mapping labels to values
            show_percentages: Include percentage labels
            
        Returns:
            ChartData object
        """
        labels = list(data.keys())
        values = list(data.values())
        total = sum(values)
        
        data_points = []
        for idx, (label, value) in enumerate(zip(labels, values)):
            percentage = (value / total * 100) if total > 0 else 0
            
            point_label = f"{label} ({percentage:.1f}%)" if show_percentages else label
            
            data_points.append(DataPoint(
                x=label,
                y=value,
                label=point_label,
                metadata={'percentage': percentage}
            ))
        
        # Assign colors
        colors = []
        for idx in range(len(labels)):
            if idx < len(config.colors):
                colors.append(config.colors[idx])
            else:
                colors.append(self.default_colors[idx % len(self.default_colors)])
        
        series = ChartSeries(
            series_id=f"{config.chart_id}_slices",
            name=config.title,
            data_points=data_points,
            style={'colors': colors}
        )
        
        return ChartData(
            chart_id=config.chart_id,
            chart_type='pie',
            title=config.title,
            series=[series],
            labels=labels,
            config=config
        )
    
    def generate_scatter_plot(
        self,
        config: ChartConfig,
        data_source: Dict[str, List[Tuple[float, float]]],
        show_trendline: bool = False
    ) -> ChartData:
        """
        Generate scatter plot data
        
        Args:
            config: Chart configuration
            data_source: Dictionary mapping series names to (x, y) tuples
            show_trendline: Include trend line
            
        Returns:
            ChartData object
        """
        series_list = []
        
        for idx, (series_name, points) in enumerate(data_source.items()):
            color = (config.colors[idx] if idx < len(config.colors)
                    else self.default_colors[idx % len(self.default_colors)])
            
            data_points = [
                DataPoint(x=x, y=y, label=f"({x:.2f}, {y:.2f})")
                for x, y in points
            ]
            
            style = {'show_trendline': show_trendline}
            
            # Calculate trendline if requested
            if show_trendline and len(points) >= 2:
                trendline = self._calculate_trendline(points)
                style['trendline'] = trendline
            
            series = ChartSeries(
                series_id=f"{config.chart_id}_{series_name}",
                name=series_name,
                data_points=data_points,
                color=color,
                style=style
            )
            
            series_list.append(series)
        
        return ChartData(
            chart_id=config.chart_id,
            chart_type='scatter',
            title=config.title,
            series=series_list,
            config=config
        )
    
    def _calculate_trendline(
        self,
        points: List[Tuple[float, float]]
    ) -> Dict[str, float]:
        """Calculate linear trendline (y = mx + b)"""
        n = len(points)
        if n < 2:
            return {'slope': 0, 'intercept': 0}
        
        x_vals = [p[0] for p in points]
        y_vals = [p[1] for p in points]
        
        # Calculate means
        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n
        
        # Calculate slope and intercept
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)
        
        if denominator == 0:
            return {'slope': 0, 'intercept': y_mean}
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        return {'slope': slope, 'intercept': intercept}
    
    def generate_timeseries_chart(
        self,
        config: ChartConfig,
        data_source: Dict[str, List[Tuple[datetime, float]]],
        aggregation: Optional[str] = None
    ) -> ChartData:
        """
        Generate time-series chart data
        
        Args:
            config: Chart configuration
            data_source: Dictionary mapping series names to (datetime, value) tuples
            aggregation: Optional aggregation ('hourly', 'daily', 'weekly')
            
        Returns:
            ChartData object
        """
        # Aggregate if requested
        if aggregation:
            data_source = self._aggregate_timeseries(data_source, aggregation)
        
        # Convert to standard format for line chart
        formatted_data = {}
        for series_name, points in data_source.items():
            formatted_data[series_name] = [
                (dt.isoformat(), value) for dt, value in points
            ]
        
        return self.generate_line_chart(config, formatted_data, smooth=True)
    
    def _aggregate_timeseries(
        self,
        data_source: Dict[str, List[Tuple[datetime, float]]],
        aggregation: str
    ) -> Dict[str, List[Tuple[datetime, float]]]:
        """Aggregate time-series data"""
        aggregated = {}
        
        for series_name, points in data_source.items():
            buckets = defaultdict(list)
            
            for dt, value in points:
                # Determine bucket key
                if aggregation == 'hourly':
                    bucket_key = dt.replace(minute=0, second=0, microsecond=0)
                elif aggregation == 'daily':
                    bucket_key = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                elif aggregation == 'weekly':
                    # Start of week (Monday)
                    days_since_monday = dt.weekday()
                    bucket_key = (dt - timedelta(days=days_since_monday)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                else:
                    bucket_key = dt
                
                buckets[bucket_key].append(value)
            
            # Calculate aggregated values (average)
            aggregated[series_name] = [
                (bucket_key, sum(values) / len(values))
                for bucket_key, values in sorted(buckets.items())
            ]
        
        return aggregated
    
    def generate_multi_series_chart(
        self,
        config: ChartConfig,
        data_sources: List[Tuple[str, Dict[str, List[Tuple[Any, float]]]]],
        chart_type: str = 'line'
    ) -> ChartData:
        """
        Generate chart with multiple data series
        
        Args:
            config: Chart configuration
            data_sources: List of (series_name, data) tuples
            chart_type: Type of chart
            
        Returns:
            ChartData object
        """
        if chart_type == 'line':
            combined_data = {}
            for series_name, data in data_sources:
                for key, points in data.items():
                    combined_key = f"{series_name}_{key}"
                    combined_data[combined_key] = points
            return self.generate_line_chart(config, combined_data)
        else:
            raise ValueError(f"Multi-series not supported for {chart_type}")
    
    def export_to_json(self, chart_data: ChartData) -> str:
        """
        Export chart data to JSON
        
        Args:
            chart_data: Chart data to export
            
        Returns:
            JSON string
        """
        data_dict = {
            'chart_id': chart_data.chart_id,
            'chart_type': chart_data.chart_type,
            'title': chart_data.title,
            'timestamp': chart_data.timestamp.isoformat(),
            'series': []
        }

        if chart_data.config:
            data_dict['config'] = {
                'chart_id': chart_data.config.chart_id,
                'chart_type': chart_data.config.chart_type,
                'title': chart_data.config.title,
                'x_label': chart_data.config.x_label,
                'y_label': chart_data.config.y_label,
                'colors': chart_data.config.colors,
                'options': chart_data.config.options
            }
        
        for series in chart_data.series:
            series_dict = {
                'series_id': series.series_id,
                'name': series.name,
                'color': series.color,
                'style': series.style,
                'data': [
                    {
                        'x': str(dp.x),
                        'y': dp.y,
                        'label': dp.label,
                        'metadata': dp.metadata
                    }
                    for dp in series.data_points
                ]
            }
            data_dict['series'].append(series_dict)
        
        if chart_data.labels:
            data_dict['labels'] = chart_data.labels
        
        return json.dumps(data_dict, indent=2)
    
    def export_to_csv(self, chart_data: ChartData) -> str:
        """
        Export chart data to CSV
        
        Args:
            chart_data: Chart data to export
            
        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        if chart_data.series:
            headers = ['x']
            for series in chart_data.series:
                headers.append(series.name)
            writer.writerow(headers)
            
            # Collect all x values
            x_values = set()
            for series in chart_data.series:
                for dp in series.data_points:
                    x_values.add(str(dp.x))
            
            # Write data rows
            for x in sorted(x_values):
                row = [x]
                for series in chart_data.series:
                    # Find matching data point
                    matching = [dp for dp in series.data_points if str(dp.x) == x]
                    if matching:
                        row.append(matching[0].y)
                    else:
                        row.append('')
                writer.writerow(row)
        
        return output.getvalue()


class RealTimeChartManager:
    """
    Manage real-time chart updates
    
    Provides streaming data support for live dashboards.
    """
    
    def __init__(self, max_points: int = 100):
        """
        Initialize real-time chart manager
        
        Args:
            max_points: Maximum points to keep per series
        """
        self.max_points = max_points
        self.charts: Dict[str, ChartData] = {}
        self.buffers: Dict[str, Dict[str, List[DataPoint]]] = {}
        
        logger.info("Real-Time Chart Manager initialized")
    
    def add_data_point(
        self,
        chart_id: str,
        series_id: str,
        point: DataPoint
    ):
        """
        Add a data point to a real-time chart
        
        Args:
            chart_id: Chart ID
            series_id: Series ID
            point: Data point to add
        """
        if chart_id not in self.buffers:
            self.buffers[chart_id] = {}
        
        if series_id not in self.buffers[chart_id]:
            self.buffers[chart_id][series_id] = []
        
        buffer = self.buffers[chart_id][series_id]
        buffer.append(point)
        
        # Trim if exceeds max
        if len(buffer) > self.max_points:
            buffer.pop(0)
    
    def get_chart_data(self, chart_id: str) -> Dict[str, List[DataPoint]]:
        """Get current chart buffer data."""
        return self.buffers.get(chart_id, {})
    
    def update_chart(
        self,
        chart_id: str,
        config: ChartConfig
    ) -> ChartData:
        """
        Update chart with current buffer data
        
        Args:
            chart_id: Chart ID
            config: Chart configuration
            
        Returns:
            Updated ChartData
        """
        if chart_id not in self.buffers:
            return ChartData(
                chart_id=chart_id,
                chart_type=config.chart_type,
                title=config.title,
                series=[],
                config=config
            )
        
        series_list = []
        for series_id, points in self.buffers[chart_id].items():
            series = ChartSeries(
                series_id=series_id,
                name=series_id,
                data_points=points.copy()
            )
            series_list.append(series)
        
        chart_data = ChartData(
            chart_id=chart_id,
            chart_type=config.chart_type,
            title=config.title,
            series=series_list,
            config=config
        )
        
        self.charts[chart_id] = chart_data
        return chart_data
