"""
Dashboard Widgets Module for IPFS Kit

This module provides a comprehensive widget system for dashboards:
- Widget base class and framework
- Status widgets (server health, operation counts)
- Health monitoring widgets
- Alert notification widgets
- Counter and metric widgets
- Real-time data updates
- Widget configuration and persistence

Part of Phase 10: Dashboard Enhancements
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


@dataclass
class WidgetConfig:
    """Widget configuration"""
    widget_id: str
    widget_type: str
    title: str
    refresh_interval: int = 60  # seconds
    position: Dict[str, int] = field(default_factory=lambda: {'x': 0, 'y': 0})
    size: Dict[str, int] = field(default_factory=lambda: {'width': 1, 'height': 1})
    config_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WidgetData:
    """Widget data response"""
    widget_id: str
    widget_type: str
    timestamp: datetime
    data: Dict[str, Any]
    status: str  # 'ok', 'warning', 'error'
    message: Optional[str] = None


class Widget(ABC):
    """
    Base widget class
    
    All dashboard widgets inherit from this class and implement
    the get_data() method to provide their specific data.
    """
    
    def __init__(self, config: WidgetConfig):
        """
        Initialize widget
        
        Args:
            config: Widget configuration
        """
        self.config = config
        self.last_update = None
        self.cached_data = None
        
        logger.info(f"Widget initialized: {config.widget_id} ({config.widget_type})")
    
    @abstractmethod
    def get_data(self) -> WidgetData:
        """
        Get widget data
        
        Must be implemented by subclasses.
        
        Returns:
            WidgetData with current widget information
        """
        pass
    
    def update(self) -> WidgetData:
        """
        Update widget data
        
        Returns:
            WidgetData with updated information
        """
        try:
            data = self.get_data()
            self.last_update = datetime.now()
            self.cached_data = data
            return data
        except Exception as e:
            logger.error(f"Error updating widget {self.config.widget_id}: {e}")
            return WidgetData(
                widget_id=self.config.widget_id,
                widget_type=self.config.widget_type,
                timestamp=datetime.now(),
                data={},
                status='error',
                message=str(e)
            )
    
    def get_cached_data(self) -> Optional[WidgetData]:
        """Get cached data without refresh"""
        return self.cached_data
    
    def should_refresh(self) -> bool:
        """Check if widget should be refreshed"""
        if self.last_update is None:
            return True
        
        elapsed = (datetime.now() - self.last_update).total_seconds()
        return elapsed >= self.config.refresh_interval
    
    def render_config(self) -> Dict[str, Any]:
        """
        Get widget configuration for rendering
        
        Returns:
            Dictionary with widget configuration
        """
        return {
            'widget_id': self.config.widget_id,
            'widget_type': self.config.widget_type,
            'title': self.config.title,
            'refresh_interval': self.config.refresh_interval,
            'position': self.config.position,
            'size': self.config.size,
            'config_data': self.config.config_data
        }


class StatusWidget(Widget):
    """
    System status widget
    
    Displays overall system status including:
    - System state (running/stopped/error)
    - Uptime
    - Active connections
    - Resource usage summary
    """
    
    def __init__(self, config: WidgetConfig, status_provider: Optional[Callable] = None):
        """
        Initialize status widget
        
        Args:
            config: Widget configuration
            status_provider: Function that returns system status
        """
        super().__init__(config)
        self.status_provider = status_provider or self._default_status_provider
    
    def _default_status_provider(self) -> Dict[str, Any]:
        """Default status provider"""
        return {
            'state': 'running',
            'uptime_seconds': 3600,
            'active_connections': 5,
            'cpu_percent': 25.0,
            'memory_percent': 40.0
        }
    
    def get_data(self) -> WidgetData:
        """Get status widget data"""
        status = self.status_provider()
        
        # Determine overall status
        cpu = status.get('cpu_percent', 0)
        memory = status.get('memory_percent', 0)
        
        if cpu > 90 or memory > 90:
            overall_status = 'error'
            message = 'High resource usage'
        elif cpu > 75 or memory > 75:
            overall_status = 'warning'
            message = 'Elevated resource usage'
        else:
            overall_status = 'ok'
            message = 'System operating normally'
        
        return WidgetData(
            widget_id=self.config.widget_id,
            widget_type=self.config.widget_type,
            timestamp=datetime.now(),
            data=status,
            status=overall_status,
            message=message
        )


class HealthWidget(Widget):
    """
    System health widget
    
    Displays system health metrics:
    - Service health checks
    - Component status
    - Error rates
    - Response times
    """
    
    def __init__(self, config: WidgetConfig, health_checker: Optional[Callable] = None, health_provider: Optional[Callable] = None):
        """
        Initialize health widget
        
        Args:
            config: Widget configuration
            health_checker: Function that returns health metrics
        """
        super().__init__(config)
        if health_provider is not None and health_checker is None:
            health_checker = health_provider
        if health_checker is not None and not callable(health_checker):
            health_checker = None
        self.health_checker = health_checker or self._default_health_checker
    
    def _default_health_checker(self) -> Dict[str, Any]:
        """Default health checker"""
        return {
            'services': {
                'api': {'status': 'healthy', 'response_time_ms': 10},
                'storage': {'status': 'healthy', 'response_time_ms': 5},
                'cache': {'status': 'healthy', 'response_time_ms': 1}
            },
            'error_rate': 0.01,
            'avg_response_time_ms': 15
        }
    
    def get_data(self) -> WidgetData:
        """Get health widget data"""
        health = self.health_checker()
        
        # Determine health status
        services = health.get('services', {})
        unhealthy = []
        for name, info in services.items():
            if isinstance(info, dict):
                status = info.get('status')
            else:
                status = info
            if status != 'healthy':
                unhealthy.append(name)
        
        error_rate = health.get('error_rate', 0)
        
        if unhealthy:
            overall_status = 'error'
            message = f"Unhealthy services: {', '.join(unhealthy)}"
        elif error_rate > 0.05:
            overall_status = 'warning'
            message = f"High error rate: {error_rate:.1%}"
        else:
            overall_status = 'ok'
            message = 'All services healthy'
        
        return WidgetData(
            widget_id=self.config.widget_id,
            widget_type=self.config.widget_type,
            timestamp=datetime.now(),
            data=health,
            status=overall_status,
            message=message
        )


class AlertWidget(Widget):
    """
    Alert notification widget
    
    Displays recent alerts and notifications:
    - Error alerts
    - Warning notifications
    - Info messages
    - Alert counts by severity
    """
    
    def __init__(self, config: WidgetConfig, alert_provider: Optional[Callable] = None):
        """
        Initialize alert widget
        
        Args:
            config: Widget configuration
            alert_provider: Function that returns alerts
        """
        super().__init__(config)
        self.alert_provider = alert_provider or self._default_alert_provider
        self.max_alerts = config.config_data.get('max_alerts', 10)
    
    def _default_alert_provider(self) -> List[Dict[str, Any]]:
        """Default alert provider"""
        return []
    
    def get_data(self) -> WidgetData:
        """Get alert widget data"""
        alerts = self.alert_provider()
        
        # Limit alerts
        recent_alerts = alerts[:self.max_alerts]
        
        # Count by severity
        severity_counts = {'error': 0, 'warning': 0, 'info': 0}
        for alert in alerts:
            severity = alert.get('severity', 'info')
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        # Determine widget status
        if severity_counts['error'] > 0:
            overall_status = 'error'
            message = f"{severity_counts['error']} error alerts"
        elif severity_counts['warning'] > 0:
            overall_status = 'warning'
            message = f"{severity_counts['warning']} warnings"
        else:
            overall_status = 'ok'
            message = 'No alerts'
        
        return WidgetData(
            widget_id=self.config.widget_id,
            widget_type=self.config.widget_type,
            timestamp=datetime.now(),
            data={
                'alerts': recent_alerts,
                'severity_counts': severity_counts,
                'total_alerts': len(alerts)
            },
            status=overall_status,
            message=message
        )


class CounterWidget(Widget):
    """
    Counter widget
    
    Displays numerical metrics:
    - Total counts
    - Rates (per second, per minute)
    - Comparisons to previous periods
    """
    
    def __init__(self, config: WidgetConfig, counter_provider: Optional[Callable] = None):
        """
        Initialize counter widget
        
        Args:
            config: Widget configuration
            counter_provider: Function that returns counter value
        """
        super().__init__(config)
        self.counter_provider = counter_provider or self._default_counter_provider
        self.metric_name = config.config_data.get('metric_name', 'count')
    
    def _default_counter_provider(self) -> Dict[str, Any]:
        """Default counter provider"""
        return {
            'current': 100,
            'previous': 90,
            'rate_per_minute': 1.5
        }
    
    def get_data(self) -> WidgetData:
        """Get counter widget data"""
        counter_data = self.counter_provider()
        
        current = counter_data.get('current', 0)
        previous = counter_data.get('previous', 0)
        
        # Calculate change
        if previous > 0:
            change_percent = ((current - previous) / previous) * 100
        else:
            change_percent = 0
        
        counter_data['change_percent'] = change_percent
        counter_data['trend'] = 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable'
        
        return WidgetData(
            widget_id=self.config.widget_id,
            widget_type=self.config.widget_type,
            timestamp=datetime.now(),
            data=counter_data,
            status='ok',
            message=f"{self.metric_name}: {current}"
        )


class MetricWidget(Widget):
    """
    Metric widget
    
    Displays detailed metrics:
    - Current value
    - Min/max/average
    - Thresholds and alerts
    """
    
    def __init__(self, config: WidgetConfig, metric_provider: Optional[Callable] = None):
        """
        Initialize metric widget
        
        Args:
            config: Widget configuration
            metric_provider: Function that returns metric data
        """
        super().__init__(config)
        self.metric_provider = metric_provider or self._default_metric_provider
        self.thresholds = config.config_data.get('thresholds', {
            'warning': 75,
            'error': 90
        })
    
    def _default_metric_provider(self) -> Dict[str, Any]:
        """Default metric provider"""
        return {
            'current': 50,
            'min': 0,
            'max': 100,
            'average': 45,
            'unit': '%'
        }
    
    def get_data(self) -> WidgetData:
        """Get metric widget data"""
        metric_data = self.metric_provider()
        
        current = metric_data.get('current', 0)
        
        # Check thresholds
        if current >= self.thresholds.get('error', 100):
            overall_status = 'error'
            message = f"Critical: {current}{metric_data.get('unit', '')}"
        elif current >= self.thresholds.get('warning', 100):
            overall_status = 'warning'
            message = f"Warning: {current}{metric_data.get('unit', '')}"
        else:
            overall_status = 'ok'
            message = f"Normal: {current}{metric_data.get('unit', '')}"
        
        return WidgetData(
            widget_id=self.config.widget_id,
            widget_type=self.config.widget_type,
            timestamp=datetime.now(),
            data=metric_data,
            status=overall_status,
            message=message
        )


class OperationHistoryWidget(Widget):
    """
    Operation history widget
    
    Displays recent operations:
    - Operation list
    - Status (success/failed)
    - Duration
    - Timestamps
    """
    
    def __init__(self, config: WidgetConfig, history_provider: Optional[Callable] = None):
        """
        Initialize operation history widget
        
        Args:
            config: Widget configuration
            history_provider: Function that returns operation history
        """
        super().__init__(config)
        self.history_provider = history_provider or self._default_history_provider
        self.max_operations = config.config_data.get('max_operations', 20)
    
    def _default_history_provider(self) -> List[Dict[str, Any]]:
        """Default history provider"""
        return []
    
    def get_data(self) -> WidgetData:
        """Get operation history widget data"""
        operations = self.history_provider()
        
        # Limit operations
        recent_ops = operations[:self.max_operations]
        
        # Count by status
        status_counts = {'success': 0, 'failed': 0}
        for op in operations:
            status = op.get('status', 'unknown')
            if status in status_counts:
                status_counts[status] += 1
        
        return WidgetData(
            widget_id=self.config.widget_id,
            widget_type=self.config.widget_type,
            timestamp=datetime.now(),
            data={
                'operations': recent_ops,
                'status_counts': status_counts,
                'total_operations': len(operations)
            },
            status='ok',
            message=f"{len(recent_ops)} recent operations"
        )


class WidgetManager:
    """
    Manages dashboard widgets
    
    Provides centralized widget management:
    - Widget registration
    - Widget updates
    - Widget configuration
    - Widget lifecycle
    """
    
    def __init__(self):
        """Initialize widget manager"""
        self.widgets: Dict[str, Widget] = {}
        self._widgets = self.widgets
        self.widget_types: Dict[str, type] = {
            'status': StatusWidget,
            'health': HealthWidget,
            'alert': AlertWidget,
            'counter': CounterWidget,
            'metric': MetricWidget,
            'operation_history': OperationHistoryWidget
        }
        
        logger.info("Widget Manager initialized")
    
    def register_widget_type(self, type_name: str, widget_class: type):
        """
        Register a custom widget type
        
        Args:
            type_name: Name of the widget type
            widget_class: Widget class
        """
        self.widget_types[type_name] = widget_class
        logger.info(f"Registered widget type: {type_name}")
    
    def create_widget(
        self,
        config: WidgetConfig,
        **kwargs
    ) -> Widget:
        """
        Create a widget
        
        Args:
            config: Widget configuration
            **kwargs: Additional arguments for widget constructor
            
        Returns:
            Created widget instance
        """
        widget_class = self.widget_types.get(config.widget_type)
        if not widget_class:
            raise ValueError(f"Unknown widget type: {config.widget_type}")
        
        widget = widget_class(config, **kwargs)
        self.widgets[config.widget_id] = widget
        
        logger.info(f"Created widget: {config.widget_id}")
        return widget
    
    def get_widget(self, widget_id: str) -> Optional[Widget]:
        """Get widget by ID"""
        return self.widgets.get(widget_id)
    
    def remove_widget(self, widget_id: str) -> bool:
        """Remove widget"""
        if widget_id in self.widgets:
            del self.widgets[widget_id]
            logger.info(f"Removed widget: {widget_id}")
            return True
        return False
    
    def update_all_widgets(self) -> Dict[str, WidgetData]:
        """
        Update all widgets that need refresh
        
        Returns:
            Dictionary mapping widget IDs to their data
        """
        results = {}
        for widget_id, widget in self.widgets.items():
            if widget.should_refresh():
                results[widget_id] = widget.update()
        
        return results
    
    def get_all_widget_data(self, force_refresh: bool = False) -> Dict[str, WidgetData]:
        """
        Get data from all widgets
        
        Args:
            force_refresh: Force refresh even if not needed
            
        Returns:
            Dictionary mapping widget IDs to their data
        """
        results = {}
        for widget_id, widget in self.widgets.items():
            if force_refresh or widget.should_refresh():
                results[widget_id] = widget.update()
            else:
                cached = widget.get_cached_data()
                if cached:
                    results[widget_id] = cached
        
        return results
    
    def get_widget_configurations(self) -> List[Dict[str, Any]]:
        """Get all widget configurations"""
        return [widget.render_config() for widget in self.widgets.values()]
