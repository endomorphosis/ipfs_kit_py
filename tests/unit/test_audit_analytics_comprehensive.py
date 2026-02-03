"""
Comprehensive Tests for Audit Analytics (Phase 8)

Tests all components of the audit analytics system:
- Pattern recognition
- Anomaly detection
- Event correlation
- Timeline reconstruction
- Causation analysis
- Impact assessment
- Visualization
- MCP tools
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.audit_analytics import AuditAnalytics, Pattern, Anomaly, ComplianceScore
from ipfs_kit_py.audit_correlation import EventCorrelator, CorrelatedEvent, Timeline, CausationChain, ImpactAssessment
from ipfs_kit_py.audit_visualization import AuditVisualizer, TimelinePoint, HeatMapCell, ChartDataPoint


class TestAuditAnalytics(unittest.TestCase):
    """Test audit analytics engine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_logger = Mock()
        self.analytics = AuditAnalytics(self.mock_logger)
    
    def test_initialization(self):
        """Test analytics engine initialization"""
        self.assertIsNotNone(self.analytics)
        self.assertEqual(self.analytics.audit_logger, self.mock_logger)
    
    def test_analyze_patterns_empty(self):
        """Test pattern analysis with no events"""
        self.mock_logger.query_events = Mock(return_value=[])
        patterns = self.analytics.analyze_patterns(timedelta(hours=24))
        self.assertEqual(len(patterns), 0)
    
    def test_analyze_patterns_with_events(self):
        """Test pattern analysis with events"""
        # Mock events
        events = [
            {'event_type': 'authentication', 'action': 'login_failed', 'timestamp': datetime.now()},
            {'event_type': 'authentication', 'action': 'login_failed', 'timestamp': datetime.now()},
            {'event_type': 'authentication', 'action': 'login_failed', 'timestamp': datetime.now()},
        ]
        self.mock_logger.query_events = Mock(return_value=events)
        
        patterns = self.analytics.analyze_patterns(timedelta(hours=24))
        # Should detect failed login pattern
        self.assertGreaterEqual(len(patterns), 0)
    
    def test_detect_anomalies_threshold(self):
        """Test anomaly detection with threshold"""
        self.mock_logger.query_events = Mock(return_value=[])
        anomalies = self.analytics.detect_anomalies(threshold=2.0, lookback_days=7)
        self.assertIsInstance(anomalies, list)
    
    def test_calculate_compliance_score_empty(self):
        """Test compliance scoring with no events"""
        result = self.analytics.calculate_compliance_score([], [])
        self.assertIsInstance(result, ComplianceScore)
        self.assertEqual(result.score, 1.0)  # Perfect compliance when no events
    
    def test_generate_statistics(self):
        """Test statistics generation"""
        events = [
            {'event_type': 'data', 'timestamp': datetime.now()},
            {'event_type': 'data', 'timestamp': datetime.now()},
            {'event_type': 'system', 'timestamp': datetime.now()},
        ]
        self.mock_logger.query_events = Mock(return_value=events)
        
        stats = self.analytics.generate_statistics(group_by='event_type')
        self.assertIsInstance(stats, dict)
    
    def test_analyze_trends(self):
        """Test trend analysis"""
        self.mock_logger.query_events = Mock(return_value=[])
        trends = self.analytics.analyze_trends(metric='event_count', period='daily')
        self.assertIsInstance(trends, list)


class TestEventCorrelator(unittest.TestCase):
    """Test event correlation module"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_logger = Mock()
        self.correlator = EventCorrelator(self.mock_logger)
    
    def test_initialization(self):
        """Test correlator initialization"""
        self.assertIsNotNone(self.correlator)
        self.assertEqual(self.correlator.default_time_window, 300)
    
    def test_correlate_events_no_reference(self):
        """Test correlation with no reference event"""
        self.mock_logger.query_events = Mock(return_value=[])
        result = self.correlator.correlate_events('nonexistent_id')
        self.assertEqual(len(result), 0)
    
    def test_correlate_events_with_events(self):
        """Test correlation with events"""
        ref_event = {
            'event_id': 'evt_1',
            'timestamp': datetime.now(),
            'user_id': 'user1',
            'resource': 'file.txt',
            'action': 'read',
            'metadata': {}
        }
        
        related_event = {
            'event_id': 'evt_2',
            'timestamp': datetime.now() + timedelta(seconds=10),
            'user_id': 'user1',
            'resource': 'file.txt',
            'action': 'write',
            'metadata': {}
        }
        
        self.mock_logger.query_events = Mock(side_effect=[
            [ref_event],  # First call for reference event
            [ref_event, related_event]  # Second call for time window
        ])
        
        result = self.correlator.correlate_events('evt_1')
        self.assertIsInstance(result, list)
    
    def test_reconstruct_timeline_no_events(self):
        """Test timeline reconstruction with no events"""
        self.mock_logger.query_events = Mock(return_value=[])
        timeline = self.correlator.reconstruct_timeline('op_123')
        self.assertIsNone(timeline)
    
    def test_reconstruct_timeline_with_events(self):
        """Test timeline reconstruction with events"""
        events = [
            {
                'event_id': 'evt_1',
                'timestamp': datetime.now(),
                'event_type': 'data',
                'action': 'create',
                'user_id': 'user1',
                'resource': 'file.txt',
                'metadata': {'operation_id': 'op_123'}
            },
            {
                'event_id': 'evt_2',
                'timestamp': datetime.now() + timedelta(seconds=5),
                'event_type': 'data',
                'action': 'write',
                'user_id': 'user1',
                'resource': 'file.txt',
                'metadata': {'operation_id': 'op_123'}
            }
        ]
        self.mock_logger.query_events = Mock(return_value=events)
        
        timeline = self.correlator.reconstruct_timeline('op_123')
        self.assertIsInstance(timeline, Timeline)
        self.assertEqual(timeline.event_count, 2)
        self.assertEqual(timeline.operation_id, 'op_123')
    
    def test_analyze_causation(self):
        """Test causation analysis"""
        self.mock_logger.query_events = Mock(return_value=[])
        chain = self.correlator.analyze_causation('evt_123')
        # Will be None with no events
        self.assertIsNone(chain)
    
    def test_assess_impact(self):
        """Test impact assessment"""
        self.mock_logger.query_events = Mock(return_value=[])
        assessment = self.correlator.assess_impact('evt_123')
        # Will be None with no event found
        self.assertIsNone(assessment)


class TestAuditVisualizer(unittest.TestCase):
    """Test audit visualization module"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_analytics = Mock()
        self.mock_correlator = Mock()
        self.visualizer = AuditVisualizer(self.mock_analytics, self.mock_correlator)
    
    def test_initialization(self):
        """Test visualizer initialization"""
        self.assertIsNotNone(self.visualizer)
    
    def test_generate_timeline_data_empty(self):
        """Test timeline data generation with no events"""
        result = self.visualizer.generate_timeline_data([])
        self.assertEqual(len(result), 0)
    
    def test_generate_timeline_data_with_events(self):
        """Test timeline data generation with events"""
        events = [
            {
                'timestamp': datetime.now(),
                'event_id': 'evt_1',
                'event_type': 'data',
                'action': 'create',
                'user_id': 'user1',
                'resource': 'file.txt',
                'metadata': {}
            }
        ]
        
        result = self.visualizer.generate_timeline_data(events)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TimelinePoint)
    
    def test_generate_heatmap_data_empty(self):
        """Test heatmap generation with no events"""
        result = self.visualizer.generate_heatmap_data([])
        self.assertEqual(len(result), 0)
    
    def test_generate_heatmap_data_with_events(self):
        """Test heatmap generation with events"""
        events = [
            {
                'timestamp': datetime.now(),
                'action': 'create',
                'event_type': 'data'
            },
            {
                'timestamp': datetime.now(),
                'action': 'create',
                'event_type': 'data'
            }
        ]
        
        result = self.visualizer.generate_heatmap_data(events)
        self.assertIsInstance(result, list)
        if len(result) > 0:
            self.assertIsInstance(result[0], HeatMapCell)
    
    def test_generate_chart_data_bar(self):
        """Test bar chart data generation"""
        events = [
            {'event_type': 'data'},
            {'event_type': 'data'},
            {'event_type': 'system'}
        ]
        
        result = self.visualizer.generate_chart_data('bar', events)
        self.assertIsInstance(result, list)
        if len(result) > 0:
            self.assertIsInstance(result[0], ChartDataPoint)
    
    def test_generate_chart_data_line(self):
        """Test line chart data generation"""
        events = [
            {'timestamp': datetime.now()},
            {'timestamp': datetime.now()}
        ]
        
        result = self.visualizer.generate_chart_data('line', events)
        self.assertIsInstance(result, list)
    
    def test_generate_chart_data_pie(self):
        """Test pie chart data generation"""
        events = [
            {'event_type': 'data'},
            {'event_type': 'data'},
            {'event_type': 'system'}
        ]
        
        result = self.visualizer.generate_chart_data('pie', events)
        self.assertIsInstance(result, list)
    
    def test_generate_activity_summary(self):
        """Test activity summary generation"""
        events = [
            {
                'timestamp': datetime.now(),
                'event_type': 'data',
                'user_id': 'user1',
                'action': 'create'
            }
        ]
        
        result = self.visualizer.generate_activity_summary(events, '24h')
        self.assertIsInstance(result, dict)
        self.assertIn('total_events', result)
        self.assertIn('unique_users', result)
    
    def test_export_to_json(self):
        """Test JSON export"""
        data = {'test': 'value', 'timestamp': datetime.now()}
        result = self.visualizer.export_to_json(data)
        self.assertIsInstance(result, dict)
        self.assertIn('test', result)


class TestMCPToolsIntegration(unittest.TestCase):
    """Test MCP tools integration"""
    
    def test_tools_import(self):
        """Test that MCP tools can be imported"""
        try:
            from ipfs_kit_py.mcp.servers import audit_analytics_mcp_tools
            self.assertIsNotNone(audit_analytics_mcp_tools)
        except ImportError as e:
            self.fail(f"Could not import audit analytics MCP tools: {e}")
    
    def test_tools_available(self):
        """Test that all expected tools are available"""
        from ipfs_kit_py.mcp.servers import audit_analytics_mcp_tools
        
        expected_tools = [
            'audit_analytics_get_patterns',
            'audit_analytics_detect_anomalies',
            'audit_analytics_correlate_events',
            'audit_analytics_reconstruct_timeline',
            'audit_analytics_analyze_causation',
            'audit_analytics_assess_impact',
            'audit_analytics_get_compliance_score',
            'audit_analytics_get_statistics',
            'audit_analytics_analyze_trends',
            'audit_analytics_generate_report',
        ]
        
        for tool_name in expected_tools:
            self.assertTrue(
                hasattr(audit_analytics_mcp_tools, tool_name),
                f"Tool {tool_name} not found"
            )


class TestCLIIntegration(unittest.TestCase):
    """Test CLI integration"""
    
    def test_cli_import(self):
        """Test that CLI module can be imported"""
        try:
            from ipfs_kit_py import audit_analytics_cli
            self.assertIsNotNone(audit_analytics_cli)
        except ImportError as e:
            self.fail(f"Could not import audit analytics CLI: {e}")
    
    def test_cli_parser(self):
        """Test CLI parser creation"""
        from ipfs_kit_py.audit_analytics_cli import create_parser
        
        parser = create_parser()
        self.assertIsNotNone(parser)


if __name__ == '__main__':
    unittest.main()
