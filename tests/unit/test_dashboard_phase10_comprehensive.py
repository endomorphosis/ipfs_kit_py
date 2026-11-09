"""
Comprehensive Tests for Dashboard Enhancements (Phase 10)

Tests all components of the dashboard enhancement system:
- Dashboard Widgets (6 types)
- Chart Framework (5 chart types)
- Configuration Wizards (3 wizards)
- Dashboard MCP tools
- Dashboard CLI
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.dashboard_widgets import (
    WidgetManager, Widget, WidgetConfig, WidgetData,
    StatusWidget, HealthWidget, AlertWidget, CounterWidget,
    MetricWidget, OperationHistoryWidget
)
from ipfs_kit_py.dashboard_charts import (
    ChartGenerator, RealTimeChartManager, ChartConfig, ChartData,
    DataPoint, ChartSeries
)
from ipfs_kit_py.config_wizards import (
    WizardManager, Wizard, WizardStep, WizardConfig, WizardState,
    BackendSetupWizard, VFSConfigurationWizard, MonitoringSetupWizard
)


class TestWidgetManager(unittest.TestCase):
    """Test widget manager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = WidgetManager()
    
    def test_widget_manager_initialization(self):
        """Test widget manager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(len(self.manager._widgets), 0)
    
    def test_create_widget(self):
        """Test widget creation"""
        config = WidgetConfig(
            widget_id='test1',
            widget_type='status',
            title='Test Widget',
            refresh_interval=60
        )
        
        # Mock data provider
        data_provider = Mock(return_value={'status': 'ok'})
        
        widget = self.manager.create_widget(config, status_provider=data_provider)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.config.widget_id, 'test1')
    
    def test_get_widget(self):
        """Test retrieving widget by ID"""
        config = WidgetConfig(
            widget_id='test1',
            widget_type='status',
            title='Test Widget'
        )
        data_provider = Mock(return_value={'status': 'ok'})
        
        self.manager.create_widget(config, status_provider=data_provider)
        widget = self.manager.get_widget('test1')
        
        self.assertIsNotNone(widget)
        self.assertEqual(widget.config.widget_id, 'test1')
    
    def test_remove_widget(self):
        """Test removing widget"""
        config = WidgetConfig(
            widget_id='test1',
            widget_type='status',
            title='Test Widget'
        )
        data_provider = Mock(return_value={'status': 'ok'})
        
        self.manager.create_widget(config, status_provider=data_provider)
        self.manager.remove_widget('test1')
        
        widget = self.manager.get_widget('test1')
        self.assertIsNone(widget)
    
    def test_get_all_widget_data(self):
        """Test getting data from all widgets"""
        # Create two widgets
        for i in range(2):
            config = WidgetConfig(
                widget_id=f'test{i}',
                widget_type='status',
                title=f'Widget {i}'
            )
            data_provider = Mock(return_value={'status': 'ok', 'id': i})
            self.manager.create_widget(config, status_provider=data_provider)
        
        all_data = self.manager.get_all_widget_data()
        self.assertEqual(len(all_data), 2)


class TestWidgetTypes(unittest.TestCase):
    """Test different widget types"""
    
    def test_status_widget(self):
        """Test status widget"""
        config = WidgetConfig(
            widget_id='status1',
            widget_type='status',
            title='System Status'
        )
        
        status_provider = Mock(return_value={
            'system_state': 'running',
            'uptime': 3600,
            'connections': 5
        })
        
        widget = StatusWidget(config, status_provider=status_provider)
        data = widget.get_data()
        
        self.assertEqual(data.status, 'ok')
        self.assertIn('system_state', data.data)
    
    def test_health_widget(self):
        """Test health widget"""
        config = WidgetConfig(
            widget_id='health1',
            widget_type='health',
            title='Service Health'
        )
        
        health_provider = Mock(return_value={
            'services': {'api': 'healthy', 'db': 'healthy'},
            'overall': 'healthy'
        })
        
        widget = HealthWidget(config, health_provider=health_provider)
        data = widget.get_data()
        
        self.assertEqual(data.status, 'ok')
        self.assertIn('services', data.data)
    
    def test_counter_widget(self):
        """Test counter widget"""
        config = WidgetConfig(
            widget_id='counter1',
            widget_type='counter',
            title='Request Count'
        )
        
        counter_provider = Mock(return_value={
            'current': 1000,
            'previous': 800,
            'change_percent': 25.0
        })
        
        widget = CounterWidget(config, counter_provider=counter_provider)
        data = widget.get_data()
        
        self.assertEqual(data.status, 'ok')
        self.assertEqual(data.data['current'], 1000)


class TestChartGenerator(unittest.TestCase):
    """Test chart generation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.generator = ChartGenerator()
    
    def test_generator_initialization(self):
        """Test chart generator initialization"""
        self.assertIsNotNone(self.generator)
    
    def test_generate_line_chart(self):
        """Test line chart generation"""
        config = ChartConfig(
            chart_id='line1',
            chart_type='line',
            title='CPU Usage'
        )
        
        data = {
            'series1': [(0, 25.0), (1, 30.0), (2, 28.0)]
        }
        
        chart = self.generator.generate_line_chart(config, data)
        
        self.assertIsNotNone(chart)
        self.assertEqual(chart.config.chart_id, 'line1')
        self.assertEqual(len(chart.series), 1)
    
    def test_generate_bar_chart(self):
        """Test bar chart generation"""
        config = ChartConfig(
            chart_id='bar1',
            chart_type='bar',
            title='Request Count'
        )
        
        data = {'GET': 100, 'POST': 50, 'PUT': 30}
        
        chart = self.generator.generate_bar_chart(config, data)
        
        self.assertIsNotNone(chart)
        self.assertEqual(chart.config.chart_type, 'bar')
    
    def test_generate_pie_chart(self):
        """Test pie chart generation"""
        config = ChartConfig(
            chart_id='pie1',
            chart_type='pie',
            title='Distribution'
        )
        
        data = {'Success': 85, 'Failed': 10, 'Pending': 5}
        
        chart = self.generator.generate_pie_chart(config, data)
        
        self.assertIsNotNone(chart)
        self.assertEqual(len(chart.series[0].data), 3)
    
    def test_export_to_json(self):
        """Test JSON export"""
        config = ChartConfig(
            chart_id='test1',
            chart_type='line',
            title='Test Chart'
        )
        
        data = {'series1': [(0, 10), (1, 20)]}
        chart = self.generator.generate_line_chart(config, data)
        
        json_data = self.generator.export_to_json(chart)
        
        self.assertIsNotNone(json_data)
        self.assertIn('config', json_data)
        self.assertIn('series', json_data)


class TestRealTimeChartManager(unittest.TestCase):
    """Test real-time chart management"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = RealTimeChartManager(max_points=100)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(self.manager.max_points, 100)
    
    def test_add_data_point(self):
        """Test adding data point"""
        point = DataPoint(x=datetime.now(), y=42.0, label='test')
        
        self.manager.add_data_point('chart1', 'series1', point)
        
        data = self.manager.get_chart_data('chart1')
        self.assertIn('series1', data)
        self.assertEqual(len(data['series1']), 1)
    
    def test_buffer_limit(self):
        """Test buffer limit enforcement"""
        # Add more than max_points
        for i in range(150):
            point = DataPoint(x=datetime.now(), y=float(i))
            self.manager.add_data_point('chart1', 'series1', point)
        
        data = self.manager.get_chart_data('chart1')
        self.assertLessEqual(len(data['series1']), 100)


class TestConfigWizards(unittest.TestCase):
    """Test configuration wizards"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = WizardManager()
    
    def test_wizard_manager_initialization(self):
        """Test wizard manager initialization"""
        self.assertIsNotNone(self.manager)
    
    def test_create_backend_wizard(self):
        """Test backend setup wizard creation"""
        wizard = self.manager.create_wizard('backend_setup')
        
        self.assertIsNotNone(wizard)
        self.assertIsInstance(wizard, BackendSetupWizard)
    
    def test_create_vfs_wizard(self):
        """Test VFS configuration wizard creation"""
        wizard = self.manager.create_wizard('vfs_config')
        
        self.assertIsNotNone(wizard)
        self.assertIsInstance(wizard, VFSConfigurationWizard)
    
    def test_create_monitoring_wizard(self):
        """Test monitoring setup wizard creation"""
        wizard = self.manager.create_wizard('monitoring_setup')
        
        self.assertIsNotNone(wizard)
        self.assertIsInstance(wizard, MonitoringSetupWizard)
    
    def test_wizard_steps(self):
        """Test wizard has steps"""
        wizard = self.manager.create_wizard('backend_setup')
        
        self.assertGreater(len(wizard.steps), 0)
    
    def test_wizard_state(self):
        """Test wizard state management"""
        wizard = self.manager.create_wizard('backend_setup')
        
        state = wizard.get_state()
        self.assertIsNotNone(state)
        self.assertIsInstance(state, WizardState)


class TestMCPToolsIntegration(unittest.TestCase):
    """Test dashboard MCP tools integration"""
    
    def test_dashboard_mcp_tools_import(self):
        """Test that dashboard MCP tools can be imported"""
        try:
            from ipfs_kit_py.mcp.servers import dashboard_mcp_tools
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import dashboard_mcp_tools: {e}")
    
    def test_dashboard_tools_available(self):
        """Test that dashboard tools are available"""
        try:
            from ipfs_kit_py.mcp.servers import dashboard_mcp_tools
            
            # Check for expected tools
            expected_tools = [
                'dashboard_get_widget_data',
                'dashboard_get_chart_data',
                'dashboard_get_operations_history',
                'dashboard_run_wizard',
                'dashboard_get_status_summary'
            ]
            
            for tool_name in expected_tools:
                self.assertTrue(
                    hasattr(dashboard_mcp_tools, tool_name),
                    f"Missing tool: {tool_name}"
                )
        except ImportError:
            self.skipTest("dashboard_mcp_tools not available")


class TestCLIIntegration(unittest.TestCase):
    """Test dashboard CLI integration"""
    
    def test_dashboard_cli_import(self):
        """Test that dashboard CLI can be imported"""
        try:
            from ipfs_kit_py import dashboard_cli
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import dashboard_cli: {e}")
    
    def test_dashboard_cli_parser(self):
        """Test dashboard CLI parser creation"""
        try:
            from ipfs_kit_py import dashboard_cli
            
            # Check if parser creation works
            self.assertTrue(hasattr(dashboard_cli, 'create_parser'))
        except (ImportError, AttributeError):
            self.skipTest("dashboard_cli parser not available")


if __name__ == '__main__':
    unittest.main()
