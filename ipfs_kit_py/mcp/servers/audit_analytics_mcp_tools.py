"""
Audit Analytics MCP Tools for IPFS Kit

This module provides MCP server tools for advanced audit analytics capabilities:
- Pattern recognition and analysis
- Anomaly detection
- Event correlation
- Timeline reconstruction
- Compliance scoring
- Statistical analysis
- Trend analysis
- Visual report generation

Part of Phase 8: Enhanced Audit Capabilities
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Import the analytics modules
try:
    from ipfs_kit_py.audit_analytics import AuditAnalytics
    from ipfs_kit_py.audit_correlation import EventCorrelator
    from ipfs_kit_py.audit_visualization import AuditVisualizer
    from ipfs_kit_py.mcp.auth.audit_logging import AuditLogger
except ImportError:
    # Fallback for different import paths
    from audit_analytics import AuditAnalytics
    from audit_correlation import EventCorrelator
    from audit_visualization import AuditVisualizer
    from mcp.auth.audit_logging import AuditLogger

logger = logging.getLogger(__name__)

# Global instances (initialized when tools are registered)
_analytics_engine = None
_correlator = None
_visualizer = None
_audit_logger = None


def initialize_audit_analytics(audit_logger: Optional[AuditLogger] = None):
    """
    Initialize the audit analytics components
    
    Args:
        audit_logger: AuditLogger instance (or None to create one)
    """
    global _analytics_engine, _correlator, _visualizer, _audit_logger
    
    if audit_logger is None:
        _audit_logger = AuditLogger()
    else:
        _audit_logger = audit_logger
    
    _analytics_engine = AuditAnalytics(_audit_logger)
    _correlator = EventCorrelator(_audit_logger)
    _visualizer = AuditVisualizer(_analytics_engine, _correlator)
    
    logger.info("Audit analytics tools initialized")


def get_analytics_engine() -> AuditAnalytics:
    """Get or create analytics engine instance"""
    global _analytics_engine
    if _analytics_engine is None:
        initialize_audit_analytics()
    return _analytics_engine


def get_correlator() -> EventCorrelator:
    """Get or create correlator instance"""
    global _correlator
    if _correlator is None:
        initialize_audit_analytics()
    return _correlator


def get_visualizer() -> AuditVisualizer:
    """Get or create visualizer instance"""
    global _visualizer
    if _visualizer is None:
        initialize_audit_analytics()
    return _visualizer


def audit_analytics_get_patterns(
    timeframe_hours: int = 24,
    event_types: Optional[List[str]] = None,
    min_confidence: float = 0.5
) -> Dict[str, Any]:
    """
    Get identified patterns in audit events
    
    Args:
        timeframe_hours: Hours to analyze (default: 24)
        event_types: Optional list of event types to analyze
        min_confidence: Minimum confidence score (0.0-1.0)
    
    Returns:
        Dictionary with patterns found
    """
    try:
        analytics = get_analytics_engine()
        
        # Analyze patterns
        patterns = analytics.analyze_patterns(
            timeframe=timedelta(hours=timeframe_hours),
            event_types=event_types
        )
        
        # Filter by confidence
        filtered_patterns = [
            p for p in patterns
            if p.confidence >= min_confidence
        ]
        
        # Convert to dict format
        result = {
            'success': True,
            'timeframe_hours': timeframe_hours,
            'total_patterns': len(patterns),
            'filtered_patterns': len(filtered_patterns),
            'patterns': [
                {
                    'pattern_type': p.pattern_type,
                    'description': p.description,
                    'confidence': p.confidence,
                    'occurrence_count': p.occurrence_count,
                    'first_seen': p.first_seen.isoformat() if p.first_seen else None,
                    'last_seen': p.last_seen.isoformat() if p.last_seen else None,
                    'events': p.events[:10]  # Limit to first 10 events
                }
                for p in filtered_patterns
            ]
        }
        
        logger.info(f"Found {len(filtered_patterns)} patterns")
        return result
        
    except Exception as e:
        logger.error(f"Error getting patterns: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_detect_anomalies(
    threshold: float = 2.0,
    lookback_days: int = 7,
    min_deviation: float = 1.5
) -> Dict[str, Any]:
    """
    Detect anomalous behavior in audit events
    
    Args:
        threshold: Standard deviation threshold (default: 2.0)
        lookback_days: Days to analyze (default: 7)
        min_deviation: Minimum deviation to report
    
    Returns:
        Dictionary with anomalies found
    """
    try:
        analytics = get_analytics_engine()
        
        # Detect anomalies
        anomalies = analytics.detect_anomalies(
            threshold=threshold,
            lookback_days=lookback_days
        )
        
        # Filter by deviation
        filtered_anomalies = [
            a for a in anomalies
            if a.deviation >= min_deviation
        ]
        
        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        filtered_anomalies.sort(key=lambda x: severity_order.get(x.severity, 4))
        
        result = {
            'success': True,
            'threshold': threshold,
            'lookback_days': lookback_days,
            'total_anomalies': len(anomalies),
            'filtered_anomalies': len(filtered_anomalies),
            'anomalies': [
                {
                    'anomaly_type': a.anomaly_type,
                    'severity': a.severity,
                    'deviation': a.deviation,
                    'description': a.description,
                    'timestamp': a.timestamp.isoformat() if a.timestamp else None,
                    'affected_events': len(a.events),
                    'recommendation': a.recommendation
                }
                for a in filtered_anomalies[:50]  # Limit to top 50
            ]
        }
        
        logger.info(f"Detected {len(filtered_anomalies)} anomalies")
        return result
        
    except Exception as e:
        logger.error(f"Error detecting anomalies: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_correlate_events(
    event_id: str,
    time_window: int = 300,
    max_results: int = 50
) -> Dict[str, Any]:
    """
    Correlate related events within a time window
    
    Args:
        event_id: Reference event ID
        time_window: Time window in seconds (default: 300)
        max_results: Maximum results to return
    
    Returns:
        Dictionary with correlated events
    """
    try:
        correlator = get_correlator()
        
        # Find correlated events
        correlated = correlator.correlate_events(
            event_id=event_id,
            time_window=time_window,
            max_results=max_results
        )
        
        result = {
            'success': True,
            'reference_event_id': event_id,
            'time_window_seconds': time_window,
            'correlated_count': len(correlated),
            'events': [
                {
                    'event_id': e.event_id,
                    'timestamp': e.timestamp.isoformat(),
                    'event_type': e.event_type,
                    'action': e.action,
                    'user_id': e.user_id,
                    'resource': e.resource,
                    'correlation_score': e.correlation_score,
                    'correlation_reason': e.correlation_reason
                }
                for e in correlated
            ]
        }
        
        logger.info(f"Found {len(correlated)} correlated events")
        return result
        
    except Exception as e:
        logger.error(f"Error correlating events: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_reconstruct_timeline(
    operation_id: str,
    include_metadata: bool = False
) -> Dict[str, Any]:
    """
    Reconstruct complete operation timeline
    
    Args:
        operation_id: Operation ID to reconstruct
        include_metadata: Include full event metadata
    
    Returns:
        Dictionary with timeline data
    """
    try:
        correlator = get_correlator()
        
        # Reconstruct timeline
        timeline = correlator.reconstruct_timeline(operation_id)
        
        if timeline is None:
            return {
                'success': False,
                'error': f'No events found for operation {operation_id}'
            }
        
        result = {
            'success': True,
            'operation_id': timeline.operation_id,
            'start_time': timeline.start_time.isoformat(),
            'end_time': timeline.end_time.isoformat(),
            'duration_seconds': timeline.duration_seconds,
            'event_count': timeline.event_count,
            'subsystems': list(timeline.subsystems),
            'summary': timeline.summary,
            'events': [
                {
                    'event_id': e.event_id,
                    'timestamp': e.timestamp.isoformat(),
                    'event_type': e.event_type,
                    'action': e.action,
                    'user_id': e.user_id,
                    'resource': e.resource,
                    'metadata': e.metadata if include_metadata else {}
                }
                for e in timeline.events
            ]
        }
        
        logger.info(f"Reconstructed timeline with {timeline.event_count} events")
        return result
        
    except Exception as e:
        logger.error(f"Error reconstructing timeline: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_analyze_causation(
    effect_event_id: str,
    max_depth: int = 10
) -> Dict[str, Any]:
    """
    Analyze causal chain leading to an event
    
    Args:
        effect_event_id: Effect event ID
        max_depth: Maximum chain depth
    
    Returns:
        Dictionary with causation chain
    """
    try:
        correlator = get_correlator()
        
        # Analyze causation
        chain = correlator.analyze_causation(
            effect_event_id=effect_event_id,
            max_depth=max_depth
        )
        
        if chain is None:
            return {
                'success': False,
                'error': f'Could not analyze causation for event {effect_event_id}'
            }
        
        result = {
            'success': True,
            'effect_event_id': effect_event_id,
            'chain_length': chain.chain_length,
            'confidence': chain.confidence,
            'explanation': chain.explanation,
            'effect_event': {
                'event_id': chain.effect_event.event_id,
                'timestamp': chain.effect_event.timestamp.isoformat(),
                'action': chain.effect_event.action,
                'resource': chain.effect_event.resource
            },
            'cause_events': [
                {
                    'event_id': e.event_id,
                    'timestamp': e.timestamp.isoformat(),
                    'action': e.action,
                    'resource': e.resource,
                    'correlation_score': e.correlation_score
                }
                for e in chain.cause_events
            ]
        }
        
        logger.info(f"Analyzed causation chain with {chain.chain_length} events")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing causation: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_assess_impact(
    event_id: str,
    time_window: int = 600
) -> Dict[str, Any]:
    """
    Assess the impact of an event on the system
    
    Args:
        event_id: Event ID to assess
        time_window: Time window for impact (seconds)
    
    Returns:
        Dictionary with impact assessment
    """
    try:
        correlator = get_correlator()
        
        # Assess impact
        assessment = correlator.assess_impact(
            event_id=event_id,
            time_window=time_window
        )
        
        if assessment is None:
            return {
                'success': False,
                'error': f'Could not assess impact for event {event_id}'
            }
        
        result = {
            'success': True,
            'event_id': assessment.event_id,
            'impact_level': assessment.impact_level,
            'impact_score': assessment.impact_score,
            'affected_resources': assessment.affected_resources,
            'affected_users': list(assessment.affected_users),
            'downstream_event_count': len(assessment.downstream_events),
            'recommendations': assessment.recommendations
        }
        
        logger.info(f"Impact assessment: {assessment.impact_level} ({assessment.impact_score:.2f})")
        return result
        
    except Exception as e:
        logger.error(f"Error assessing impact: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_get_compliance_score(
    policy_rules: List[Dict[str, Any]],
    time_range_days: int = 30
) -> Dict[str, Any]:
    """
    Calculate compliance score based on policies
    
    Args:
        policy_rules: List of policy rule dictionaries
        time_range_days: Time range for analysis
    
    Returns:
        Dictionary with compliance metrics
    """
    try:
        analytics = get_analytics_engine()
        visualizer = get_visualizer()
        
        # Get recent events
        cutoff = datetime.now() - timedelta(days=time_range_days)
        events = _audit_logger.query_events(start_time=cutoff)
        
        # Generate compliance dashboard
        dashboard = visualizer.generate_compliance_dashboard(
            events=events,
            policy_rules=policy_rules,
            time_range_days=time_range_days
        )
        
        result = {
            'success': True,
            'overall_score': dashboard.overall_score,
            'compliance_percentage': dashboard.overall_score * 100,
            'policy_scores': dashboard.policy_scores,
            'total_violations': len(dashboard.violations),
            'violations': dashboard.violations[:20],  # Limit to 20
            'recommendations': dashboard.recommendations,
            'summary': dashboard.summary
        }
        
        logger.info(f"Compliance score: {dashboard.overall_score:.2%}")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating compliance score: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_get_statistics(
    group_by: str = 'event_type',
    time_range_hours: int = 24,
    top_n: int = 10
) -> Dict[str, Any]:
    """
    Get statistical summaries of audit events
    
    Args:
        group_by: Field to group by ('event_type', 'user_id', 'action', 'status')
        time_range_hours: Hours to analyze
        top_n: Number of top results to return
    
    Returns:
        Dictionary with statistics
    """
    try:
        analytics = get_analytics_engine()
        
        # Get statistics
        stats = analytics.generate_statistics(
            group_by=group_by,
            timeframe=timedelta(hours=time_range_hours)
        )
        
        # Sort by count and limit
        sorted_stats = sorted(
            stats.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:top_n]
        
        result = {
            'success': True,
            'group_by': group_by,
            'time_range_hours': time_range_hours,
            'total_groups': len(stats),
            'top_n': top_n,
            'statistics': [
                {
                    'category': cat,
                    'count': data['count'],
                    'percentage': data.get('percentage', 0)
                }
                for cat, data in sorted_stats
            ]
        }
        
        logger.info(f"Generated statistics for {len(stats)} groups")
        return result
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_analyze_trends(
    metric: str = 'event_count',
    period: str = 'daily',
    days: int = 7
) -> Dict[str, Any]:
    """
    Analyze trends over time
    
    Args:
        metric: Metric to analyze ('event_count', 'failed_auth', 'unique_users')
        period: Time period ('hourly', 'daily')
        days: Number of days to analyze
    
    Returns:
        Dictionary with trend data
    """
    try:
        analytics = get_analytics_engine()
        
        # Analyze trends
        trends = analytics.analyze_trends(
            metric=metric,
            period=period,
            lookback_days=days
        )
        
        result = {
            'success': True,
            'metric': metric,
            'period': period,
            'days': days,
            'data_points': len(trends),
            'trends': [
                {
                    'timestamp': t['timestamp'].isoformat() if isinstance(t['timestamp'], datetime) else t['timestamp'],
                    'value': t['value'],
                    'change': t.get('change', 0)
                }
                for t in trends
            ]
        }
        
        logger.info(f"Analyzed {len(trends)} trend data points")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing trends: {e}")
        return {'success': False, 'error': str(e)}


def audit_analytics_generate_report(
    report_type: str,
    time_range_days: int = 7,
    include_charts: bool = True
) -> Dict[str, Any]:
    """
    Generate visual report data
    
    Args:
        report_type: Type of report ('timeline', 'heatmap', 'compliance', 'activity')
        time_range_days: Time range for report
        include_charts: Include chart data
    
    Returns:
        Dictionary with report data
    """
    try:
        visualizer = get_visualizer()
        
        # Get events for time range
        cutoff = datetime.now() - timedelta(days=time_range_days)
        events = _audit_logger.query_events(start_time=cutoff)
        
        if report_type == 'timeline':
            data = visualizer.generate_timeline_data(events)
            report_data = visualizer.export_to_json(data)
        elif report_type == 'heatmap':
            data = visualizer.generate_heatmap_data(events)
            report_data = visualizer.export_to_json(data)
        elif report_type == 'compliance':
            policy_rules = []  # Would come from config
            data = visualizer.generate_compliance_dashboard(events, policy_rules)
            report_data = visualizer.export_to_json(data)
        elif report_type == 'activity':
            report_data = visualizer.generate_activity_summary(
                events,
                time_range=f'{time_range_days}d'
            )
        else:
            return {
                'success': False,
                'error': f'Unknown report type: {report_type}'
            }
        
        result = {
            'success': True,
            'report_type': report_type,
            'time_range_days': time_range_days,
            'events_analyzed': len(events),
            'generated_at': datetime.now().isoformat(),
            'data': report_data
        }
        
        logger.info(f"Generated {report_type} report")
        return result
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return {'success': False, 'error': str(e)}


# Tool registration for MCP server
AUDIT_ANALYTICS_TOOLS = {
    'audit_analytics_get_patterns': audit_analytics_get_patterns,
    'audit_analytics_detect_anomalies': audit_analytics_detect_anomalies,
    'audit_analytics_correlate_events': audit_analytics_correlate_events,
    'audit_analytics_reconstruct_timeline': audit_analytics_reconstruct_timeline,
    'audit_analytics_analyze_causation': audit_analytics_analyze_causation,
    'audit_analytics_assess_impact': audit_analytics_assess_impact,
    'audit_analytics_get_compliance_score': audit_analytics_get_compliance_score,
    'audit_analytics_get_statistics': audit_analytics_get_statistics,
    'audit_analytics_analyze_trends': audit_analytics_analyze_trends,
    'audit_analytics_generate_report': audit_analytics_generate_report,
}
