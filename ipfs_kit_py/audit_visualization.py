"""
Audit Visualization Module for IPFS Kit

This module provides data preparation and visualization capabilities for audit data:
- Timeline visualization data preparation
- Heat map generation for activity patterns
- Compliance dashboard metrics
- Various chart data formats

Part of Phase 8: Enhanced Audit Capabilities
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TimelinePoint:
    """Represents a point on a timeline visualization"""
    timestamp: datetime
    event_id: str
    event_type: str
    action: str
    user_id: Optional[str]
    resource: Optional[str]
    status: str
    label: str
    metadata: Dict


@dataclass
class HeatMapCell:
    """Represents a cell in a heat map"""
    row: int  # Time bucket (hour/day)
    column: int  # Category bucket (user/resource/action)
    value: float  # Activity level
    label: str
    tooltip: str


@dataclass
class ChartDataPoint:
    """Generic data point for charts"""
    x: Any
    y: float
    label: str
    category: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class ComplianceDashboardData:
    """Data for compliance dashboard"""
    overall_score: float
    policy_scores: Dict[str, float]
    violations: List[Dict]
    trends: List[ChartDataPoint]
    recommendations: List[str]
    summary: Dict[str, Any]


class AuditVisualizer:
    """
    Generate visualization data for audit reports
    
    This class prepares audit data in formats suitable for various
    visualization types including timelines, heat maps, charts, and dashboards.
    """
    
    def __init__(self, analytics_engine=None, correlator=None):
        """
        Initialize the audit visualizer
        
        Args:
            analytics_engine: AuditAnalytics instance (optional)
            correlator: EventCorrelator instance (optional)
        """
        self.analytics = analytics_engine
        self.correlator = correlator
        
        logger.info("AuditVisualizer initialized")
    
    def generate_timeline_data(
        self, 
        events: List[Dict],
        group_by: Optional[str] = None,
        include_metadata: bool = True
    ) -> List[TimelinePoint]:
        """
        Prepare data for timeline visualization
        
        Args:
            events: List of audit events
            group_by: Optional field to group events by
            include_metadata: Whether to include full metadata
            
        Returns:
            List of TimelinePoint objects ready for visualization
        """
        timeline_points = []
        
        for event in events:
            # Create label based on event
            label = self._generate_event_label(event)
            
            # Determine status
            status = self._determine_event_status(event)
            
            # Create timeline point
            point = TimelinePoint(
                timestamp=event.get('timestamp', datetime.now()),
                event_id=event.get('event_id', ''),
                event_type=event.get('event_type', 'unknown'),
                action=event.get('action', ''),
                user_id=event.get('user_id'),
                resource=event.get('resource'),
                status=status,
                label=label,
                metadata=event.get('metadata', {}) if include_metadata else {}
            )
            
            timeline_points.append(point)
        
        # Sort by timestamp
        timeline_points.sort(key=lambda x: x.timestamp)
        
        # If grouping requested, add grouping info
        if group_by and group_by in ['user_id', 'resource', 'event_type']:
            self._add_grouping_info(timeline_points, group_by)
        
        logger.info(f"Generated {len(timeline_points)} timeline points")
        return timeline_points
    
    def _generate_event_label(self, event: Dict) -> str:
        """Generate a human-readable label for an event"""
        action = event.get('action', 'action')
        resource = event.get('resource', 'resource')
        user = event.get('user_id', 'user')
        
        # Truncate long values
        resource = resource[:30] + '...' if len(resource) > 30 else resource
        user = user[:20] + '...' if len(user) > 20 else user
        
        return f"{user}: {action} {resource}"
    
    def _determine_event_status(self, event: Dict) -> str:
        """Determine visual status of event (success, error, warning, info)"""
        event_type = event.get('event_type', '').lower()
        action = event.get('action', '').lower()
        
        if 'error' in event_type or 'fail' in action:
            return 'error'
        elif 'warning' in event_type or 'unauthorized' in action:
            return 'warning'
        elif 'success' in event_type or 'complete' in action:
            return 'success'
        else:
            return 'info'
    
    def _add_grouping_info(self, points: List[TimelinePoint], group_by: str):
        """Add grouping information to timeline points (modifies in place)"""
        # This could be used to add swim lanes or color coding
        # For now, just log the grouping
        groups = set()
        for point in points:
            if group_by == 'user_id':
                groups.add(point.user_id)
            elif group_by == 'resource':
                groups.add(point.resource)
            elif group_by == 'event_type':
                groups.add(point.event_type)
        
        logger.debug(f"Timeline grouped by {group_by}: {len(groups)} groups")
    
    def generate_heatmap_data(
        self,
        events: List[Dict],
        metric: str = 'count',
        granularity: str = 'hourly',
        category_field: str = 'action'
    ) -> List[HeatMapCell]:
        """
        Generate heat map data for activity patterns
        
        Args:
            events: List of audit events
            metric: Metric to visualize ('count', 'unique_users', 'errors')
            granularity: Time granularity ('hourly', 'daily', 'weekly')
            category_field: Field to use for columns ('action', 'event_type', 'user_id')
            
        Returns:
            List of HeatMapCell objects
        """
        if not events:
            return []
        
        # Determine time buckets
        time_buckets = self._create_time_buckets(events, granularity)
        
        # Get unique categories
        categories = self._get_unique_categories(events, category_field)
        category_to_col = {cat: idx for idx, cat in enumerate(sorted(categories))}
        
        # Build heat map data
        heat_data = defaultdict(lambda: defaultdict(int))
        
        for event in events:
            # Determine time bucket
            bucket = self._get_time_bucket(event.get('timestamp'), granularity)
            
            # Determine category
            category = event.get(category_field, 'unknown')
            
            # Increment or calculate metric
            if metric == 'count':
                heat_data[bucket][category] += 1
            elif metric == 'errors':
                if 'error' in event.get('event_type', '').lower():
                    heat_data[bucket][category] += 1
            elif metric == 'unique_users':
                # This is simplified; proper implementation would track sets
                heat_data[bucket][category] += 1
        
        # Convert to HeatMapCell objects
        cells = []
        bucket_to_row = {bucket: idx for idx, bucket in enumerate(sorted(time_buckets))}
        
        for bucket, categories_dict in heat_data.items():
            row = bucket_to_row[bucket]
            for category, value in categories_dict.items():
                col = category_to_col.get(category, 0)
                
                cells.append(HeatMapCell(
                    row=row,
                    column=col,
                    value=float(value),
                    label=f"{bucket}-{category}",
                    tooltip=f"{category} at {bucket}: {value} {metric}"
                ))
        
        logger.info(f"Generated {len(cells)} heat map cells")
        return cells
    
    def _create_time_buckets(self, events: List[Dict], granularity: str) -> set:
        """Create set of time buckets"""
        buckets = set()
        for event in events:
            timestamp = event.get('timestamp')
            if timestamp:
                bucket = self._get_time_bucket(timestamp, granularity)
                buckets.add(bucket)
        return buckets
    
    def _get_time_bucket(self, timestamp: datetime, granularity: str) -> str:
        """Get time bucket label for a timestamp"""
        if granularity == 'hourly':
            return timestamp.strftime('%Y-%m-%d %H:00')
        elif granularity == 'daily':
            return timestamp.strftime('%Y-%m-%d')
        elif granularity == 'weekly':
            # Week number
            return timestamp.strftime('%Y-W%U')
        else:
            return timestamp.strftime('%Y-%m-%d')
    
    def _get_unique_categories(self, events: List[Dict], field: str) -> set:
        """Get unique values for a field"""
        categories = set()
        for event in events:
            value = event.get(field, 'unknown')
            if value:
                categories.add(value)
        return categories
    
    def generate_compliance_dashboard(
        self,
        events: List[Dict],
        policy_rules: List[Dict],
        time_range_days: int = 30
    ) -> ComplianceDashboardData:
        """
        Generate compliance dashboard data
        
        Args:
            events: List of audit events
            policy_rules: List of compliance policy rules
            time_range_days: Time range for trend analysis
            
        Returns:
            ComplianceDashboardData object
        """
        # Calculate overall compliance score
        if self.analytics:
            compliance_result = self.analytics.calculate_compliance_score(
                events, policy_rules
            )
            overall_score = compliance_result.score
            violations = compliance_result.violations
            recommendations = compliance_result.recommendations
            policy_scores = compliance_result.policy_scores
        else:
            # Fallback if no analytics engine
            overall_score = 1.0
            violations = []
            recommendations = ["Analytics engine not available"]
            policy_scores = {}
        
        # Generate trend data
        trends = self._generate_compliance_trends(events, time_range_days)
        
        # Generate summary statistics
        summary = {
            'total_events': len(events),
            'total_violations': len(violations),
            'compliance_percentage': overall_score * 100,
            'policies_evaluated': len(policy_rules),
            'time_range_days': time_range_days,
            'last_updated': datetime.now().isoformat()
        }
        
        return ComplianceDashboardData(
            overall_score=overall_score,
            policy_scores=policy_scores,
            violations=violations,
            trends=trends,
            recommendations=recommendations,
            summary=summary
        )
    
    def _generate_compliance_trends(
        self, 
        events: List[Dict], 
        days: int
    ) -> List[ChartDataPoint]:
        """Generate compliance trend data over time"""
        if not events:
            return []
        
        # Group events by day
        daily_events = defaultdict(list)
        cutoff = datetime.now() - timedelta(days=days)
        
        for event in events:
            timestamp = event.get('timestamp')
            if timestamp and timestamp >= cutoff:
                day = timestamp.strftime('%Y-%m-%d')
                daily_events[day].append(event)
        
        # Calculate daily compliance (simplified)
        trends = []
        for day in sorted(daily_events.keys()):
            day_events = daily_events[day]
            error_count = sum(1 for e in day_events if 'error' in e.get('event_type', '').lower())
            compliance = 1.0 - (error_count / len(day_events) if day_events else 0)
            
            trends.append(ChartDataPoint(
                x=day,
                y=compliance * 100,
                label=f"Day {day}",
                category='compliance'
            ))
        
        return trends
    
    def generate_chart_data(
        self,
        chart_type: str,
        events: List[Dict],
        options: Optional[Dict] = None
    ) -> List[ChartDataPoint]:
        """
        Generate data for specific chart type
        
        Args:
            chart_type: Type of chart ('bar', 'line', 'pie', 'scatter')
            events: List of audit events
            options: Chart-specific options
            
        Returns:
            List of ChartDataPoint objects
        """
        options = options or {}
        
        if chart_type == 'bar':
            return self._generate_bar_chart_data(events, options)
        elif chart_type == 'line':
            return self._generate_line_chart_data(events, options)
        elif chart_type == 'pie':
            return self._generate_pie_chart_data(events, options)
        elif chart_type == 'scatter':
            return self._generate_scatter_chart_data(events, options)
        else:
            logger.warning(f"Unknown chart type: {chart_type}")
            return []
    
    def _generate_bar_chart_data(
        self, 
        events: List[Dict], 
        options: Dict
    ) -> List[ChartDataPoint]:
        """Generate bar chart data (counts by category)"""
        group_by = options.get('group_by', 'event_type')
        
        # Count events by category
        counts = Counter()
        for event in events:
            category = event.get(group_by, 'unknown')
            counts[category] += 1
        
        # Convert to data points
        data_points = []
        for category, count in counts.most_common():
            data_points.append(ChartDataPoint(
                x=category,
                y=float(count),
                label=f"{category}: {count}",
                category=group_by
            ))
        
        return data_points
    
    def _generate_line_chart_data(
        self, 
        events: List[Dict], 
        options: Dict
    ) -> List[ChartDataPoint]:
        """Generate line chart data (trends over time)"""
        granularity = options.get('granularity', 'daily')
        metric = options.get('metric', 'count')
        
        # Group by time bucket
        time_buckets = defaultdict(int)
        for event in events:
            timestamp = event.get('timestamp')
            if timestamp:
                bucket = self._get_time_bucket(timestamp, granularity)
                time_buckets[bucket] += 1
        
        # Convert to data points
        data_points = []
        for bucket in sorted(time_buckets.keys()):
            count = time_buckets[bucket]
            data_points.append(ChartDataPoint(
                x=bucket,
                y=float(count),
                label=f"{bucket}: {count}",
                category=metric
            ))
        
        return data_points
    
    def _generate_pie_chart_data(
        self, 
        events: List[Dict], 
        options: Dict
    ) -> List[ChartDataPoint]:
        """Generate pie chart data (distribution)"""
        group_by = options.get('group_by', 'event_type')
        
        # Count events by category
        counts = Counter()
        for event in events:
            category = event.get(group_by, 'unknown')
            counts[category] += 1
        
        total = sum(counts.values())
        
        # Convert to percentages
        data_points = []
        for category, count in counts.most_common():
            percentage = (count / total * 100) if total > 0 else 0
            data_points.append(ChartDataPoint(
                x=category,
                y=percentage,
                label=f"{category}: {percentage:.1f}%",
                category=group_by,
                metadata={'count': count, 'total': total}
            ))
        
        return data_points
    
    def _generate_scatter_chart_data(
        self, 
        events: List[Dict], 
        options: Dict
    ) -> List[ChartDataPoint]:
        """Generate scatter chart data (correlation analysis)"""
        x_field = options.get('x_field', 'timestamp')
        y_field = options.get('y_field', 'duration')
        
        data_points = []
        for event in events:
            x_val = event.get(x_field)
            y_val = event.get(y_field)
            
            if x_val is not None and y_val is not None:
                # Convert timestamp to numeric if needed
                if isinstance(x_val, datetime):
                    x_val = x_val.timestamp()
                
                data_points.append(ChartDataPoint(
                    x=x_val,
                    y=float(y_val),
                    label=event.get('event_id', 'event'),
                    category=event.get('event_type', 'unknown'),
                    metadata=event.get('metadata', {})
                ))
        
        return data_points
    
    def generate_activity_summary(
        self,
        events: List[Dict],
        time_range: str = '24h'
    ) -> Dict[str, Any]:
        """
        Generate activity summary for dashboard widgets
        
        Args:
            events: List of audit events
            time_range: Time range for summary ('1h', '24h', '7d', '30d')
            
        Returns:
            Dictionary with summary metrics
        """
        # Parse time range
        hours = self._parse_time_range(time_range)
        cutoff = datetime.now() - timedelta(hours=hours)
        
        # Filter events to time range
        recent_events = [e for e in events if e.get('timestamp', datetime.min) >= cutoff]
        
        # Calculate metrics
        total_events = len(recent_events)
        unique_users = len(set(e.get('user_id') for e in recent_events if e.get('user_id')))
        error_events = sum(1 for e in recent_events if 'error' in e.get('event_type', '').lower())
        
        # Event type distribution
        event_types = Counter(e.get('event_type', 'unknown') for e in recent_events)
        
        # Top users
        user_counts = Counter(e.get('user_id') for e in recent_events if e.get('user_id'))
        top_users = [{'user': u, 'count': c} for u, c in user_counts.most_common(5)]
        
        # Top actions
        action_counts = Counter(e.get('action') for e in recent_events if e.get('action'))
        top_actions = [{'action': a, 'count': c} for a, c in action_counts.most_common(5)]
        
        return {
            'time_range': time_range,
            'total_events': total_events,
            'unique_users': unique_users,
            'error_events': error_events,
            'error_rate': (error_events / total_events * 100) if total_events > 0 else 0,
            'event_types': dict(event_types),
            'top_users': top_users,
            'top_actions': top_actions,
            'timestamp': datetime.now().isoformat()
        }
    
    def _parse_time_range(self, time_range: str) -> int:
        """Parse time range string to hours"""
        if time_range.endswith('h'):
            return int(time_range[:-1])
        elif time_range.endswith('d'):
            return int(time_range[:-1]) * 24
        elif time_range.endswith('w'):
            return int(time_range[:-1]) * 24 * 7
        else:
            return 24  # Default to 24 hours
    
    def export_to_json(self, data: Any) -> Dict:
        """
        Export visualization data to JSON-serializable format
        
        Args:
            data: Any visualization data object
            
        Returns:
            JSON-serializable dictionary
        """
        if isinstance(data, (TimelinePoint, HeatMapCell, ChartDataPoint, ComplianceDashboardData)):
            result = asdict(data)
            # Convert datetime objects to ISO strings
            return self._convert_datetimes_to_iso(result)
        elif isinstance(data, list):
            return [self.export_to_json(item) for item in data]
        elif isinstance(data, dict):
            return self._convert_datetimes_to_iso(data)
        else:
            return data
    
    def _convert_datetimes_to_iso(self, obj: Any) -> Any:
        """Recursively convert datetime objects to ISO strings"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._convert_datetimes_to_iso(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_datetimes_to_iso(item) for item in obj]
        else:
            return obj
