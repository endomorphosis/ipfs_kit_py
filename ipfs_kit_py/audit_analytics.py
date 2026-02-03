#!/usr/bin/env python3
# ipfs_kit_py/audit_analytics.py

"""
Audit Analytics Engine for IPFS Kit

This module provides advanced analytical capabilities for audit data, including:
- Pattern recognition and classification
- Anomaly detection using statistical methods
- Compliance scoring against security policies
- Trend analysis over time
- Statistical summaries and aggregations

Part of Phase 8: Enhanced Audit Capabilities
"""

import json
import logging
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
import time

try:
    from ipfs_kit_py.mcp.auth.audit_logging import AuditLogger, AuditEvent, AuditEventType
except ImportError:
    from mcp.auth.audit_logging import AuditLogger, AuditEvent, AuditEventType

logger = logging.getLogger(__name__)


@dataclass
class Pattern:
    """Represents a detected pattern in audit events"""
    pattern_type: str
    description: str
    occurrences: int
    first_seen: float
    last_seen: float
    confidence: float  # 0.0 to 1.0
    affected_users: List[str] = field(default_factory=list)
    sample_events: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pattern to dictionary"""
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "confidence": self.confidence,
            "affected_users": self.affected_users,
            "sample_events": self.sample_events[:5]  # Limit samples
        }


@dataclass
class Anomaly:
    """Represents a detected anomaly in audit events"""
    anomaly_type: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    timestamp: float
    event_id: Optional[str] = None
    affected_user: Optional[str] = None
    deviation_score: float = 0.0  # How many standard deviations from normal
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert anomaly to dictionary"""
        return {
            "anomaly_type": self.anomaly_type,
            "description": self.description,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "affected_user": self.affected_user,
            "deviation_score": self.deviation_score,
            "details": self.details
        }


@dataclass
class ComplianceScore:
    """Represents a compliance score calculation"""
    score: float  # 0.0 to 100.0
    total_events: int
    compliant_events: int
    non_compliant_events: int
    policy_violations: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert score to dictionary"""
        return {
            "score": self.score,
            "total_events": self.total_events,
            "compliant_events": self.compliant_events,
            "non_compliant_events": self.non_compliant_events,
            "policy_violations": self.policy_violations,
            "recommendations": self.recommendations
        }


class AuditAnalytics:
    """
    Advanced analytics engine for audit data.
    
    Provides capabilities for pattern recognition, anomaly detection,
    compliance scoring, and trend analysis.
    """
    
    def __init__(self, audit_logger: AuditLogger, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the audit analytics engine.
        
        Args:
            audit_logger: The audit logger instance to analyze
            config: Optional configuration dict with settings like:
                - anomaly_threshold: Std deviations for anomaly (default: 2.0)
                - min_pattern_occurrences: Min occurrences to be pattern (default: 3)
                - analysis_window_hours: Hours to analyze (default: 24)
        """
        self.audit_logger = audit_logger
        self.config = config or {}
        self.anomaly_threshold = self.config.get('anomaly_threshold', 2.0)
        self.min_pattern_occurrences = self.config.get('min_pattern_occurrences', 3)
        self.analysis_window_hours = self.config.get('analysis_window_hours', 24)
        
        logger.info(f"Initialized AuditAnalytics with threshold={self.anomaly_threshold}, "
                   f"min_patterns={self.min_pattern_occurrences}")
    
    def analyze_patterns(self, 
                        timeframe: Optional[Union[int, timedelta]] = None, 
                        event_types: Optional[List[str]] = None) -> List[Pattern]:
        """
        Identify patterns in audit events.
        
        Args:
            timeframe: Hours to analyze (None = use default)
            event_types: List of event types to analyze (None = all)
            
        Returns:
            List of detected patterns
        """
        if timeframe is None:
            timeframe_hours = self.analysis_window_hours
        elif isinstance(timeframe, timedelta):
            timeframe_hours = timeframe.total_seconds() / 3600
        else:
            timeframe_hours = timeframe

        start_time = time.time() - (timeframe_hours * 3600)
        
        # Get events from audit logger
        events = self._get_events_since(start_time, event_types)
        
        if not events:
            logger.info("No events found for pattern analysis")
            return []
        
        patterns = []
        
        # Pattern 1: Repeated failed authentications
        failed_auth_pattern = self._detect_failed_auth_pattern(events)
        if failed_auth_pattern:
            patterns.append(failed_auth_pattern)
        
        # Pattern 2: Unusual access times
        unusual_time_pattern = self._detect_unusual_time_pattern(events)
        if unusual_time_pattern:
            patterns.append(unusual_time_pattern)
        
        # Pattern 3: Sequence patterns (e.g., always followed by)
        sequence_patterns = self._detect_sequence_patterns(events)
        patterns.extend(sequence_patterns)
        
        # Pattern 4: Frequency anomalies
        frequency_patterns = self._detect_frequency_patterns(events)
        patterns.extend(frequency_patterns)
        
        logger.info(f"Detected {len(patterns)} patterns in {len(events)} events")
        return patterns
    
    def detect_anomalies(self, 
                        threshold: Optional[float] = None, 
                        lookback_days: int = 7) -> List[Anomaly]:
        """
        Detect anomalous behavior in audit events.
        
        Args:
            threshold: Std deviation threshold (None = use default)
            lookback_days: Days of historical data to analyze
            
        Returns:
            List of detected anomalies
        """
        threshold = threshold or self.anomaly_threshold
        start_time = time.time() - (lookback_days * 24 * 3600)
        
        events = self._get_events_since(start_time)
        
        if len(events) < 10:
            logger.warning("Insufficient events for anomaly detection")
            return []
        
        anomalies = []
        
        # Anomaly 1: Unusual event frequency
        freq_anomalies = self._detect_frequency_anomalies(events, threshold)
        anomalies.extend(freq_anomalies)
        
        # Anomaly 2: Unusual user behavior
        user_anomalies = self._detect_user_anomalies(events, threshold)
        anomalies.extend(user_anomalies)
        
        # Anomaly 3: Suspicious event combinations
        combo_anomalies = self._detect_suspicious_combinations(events)
        anomalies.extend(combo_anomalies)
        
        # Anomaly 4: Geographic anomalies (if IP data available)
        geo_anomalies = self._detect_geographic_anomalies(events)
        anomalies.extend(geo_anomalies)
        
        logger.info(f"Detected {len(anomalies)} anomalies")
        return anomalies
    
    def calculate_compliance_score(self, 
                                   policy_rules: Union[Dict[str, Any], List[Any]],
                                   events: Optional[List[Any]] = None) -> ComplianceScore:
        """
        Calculate compliance score based on policy rules.
        
        Args:
            policy_rules: Dict of policy rules to check:
                {
                    "require_mfa": True,
                    "max_failed_logins": 3,
                    "require_audit_all_access": True,
                    "forbidden_actions": ["delete_user"],
                    ...
                }
                
        Returns:
            ComplianceScore object
        """
        normalized_score = False
        if isinstance(policy_rules, list):
            events_list = policy_rules
            policy_rules = events or {}
            normalized_score = True
        else:
            events_list = events if events is not None else self._get_events_since(time.time() - (24 * 3600))
        
        if not events_list:
            return ComplianceScore(
                score=1.0 if normalized_score else 100.0,
                total_events=0,
                compliant_events=0,
                non_compliant_events=0
            )
        
        violations = []
        compliant = 0
        non_compliant = 0
        
        for event in events_list:
            event_data = event if isinstance(event, dict) else event.to_dict()
            is_compliant, violation = self._check_event_compliance(event_data, policy_rules)
            
            if is_compliant:
                compliant += 1
            else:
                non_compliant += 1
                if violation:
                    violations.append(violation)
        
        total = len(events_list)
        if normalized_score:
            score = (compliant / total) if total > 0 else 1.0
        else:
            score = (compliant / total * 100) if total > 0 else 100.0
        
        recommendations = self._generate_recommendations(violations, policy_rules)
        
        return ComplianceScore(
            score=score,
            total_events=total,
            compliant_events=compliant,
            non_compliant_events=non_compliant,
            policy_violations=violations[:20],  # Limit to 20 samples
            recommendations=recommendations
        )

    def get_compliance_score(self, policy_rules: Dict[str, Any]) -> ComplianceScore:
        """Compatibility wrapper for compliance scoring."""
        return self.calculate_compliance_score(policy_rules)
    
    def generate_statistics(self, 
                           group_by: str = 'event_type',
                           timeframe: Optional[Union[int, timedelta]] = None) -> Dict[str, Any]:
        """
        Generate statistical summaries of audit events.
        
        Args:
            group_by: Field to group by ('event_type', 'user_id', 'action', 'status')
            timeframe: Hours to analyze (None = 24)
            
        Returns:
            Dict with statistical summaries
        """
        if timeframe is None:
            timeframe_hours = 24
        elif isinstance(timeframe, timedelta):
            timeframe_hours = timeframe.total_seconds() / 3600
        else:
            timeframe_hours = timeframe
        start_time = time.time() - (timeframe_hours * 3600)
        events = self._get_events_since(start_time)
        
        if not events:
            return {"error": "No events found", "count": 0}
        
        # Group events
        grouped = defaultdict(list)
        for event in events:
            event_data = event if isinstance(event, dict) else event.to_dict()
            key = event_data.get(group_by, 'unknown')
            grouped[key].append(event_data)
        
        # Generate statistics for each group
        stats = {
            "total_events": len(events),
            "timeframe_hours": timeframe_hours,
            "group_by": group_by,
            "groups": {}
        }
        
        for key, group_events in grouped.items():
            stats["groups"][key] = {
                "count": len(group_events),
                "percentage": len(group_events) / len(events) * 100,
                "first_occurrence": min(e.get('timestamp', 0) for e in group_events),
                "last_occurrence": max(e.get('timestamp', 0) for e in group_events),
                "unique_users": len(set(e.get('user_id') for e in group_events if e.get('user_id')))
            }
        
        return stats
    
    def analyze_trends(self, 
                      metric: str = 'event_count', 
                      period: str = 'hourly',
                      days: int = 7,
                      lookback_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Analyze trends over time.
        
        Args:
            metric: Metric to analyze ('event_count', 'failed_auth', 'unique_users')
            period: Time period ('hourly', 'daily')
            days: Number of days to analyze
            
        Returns:
            Dict with trend analysis
        """
        days = lookback_days or days
        start_time = time.time() - (days * 24 * 3600)
        events = self._get_events_since(start_time)
        
        if not events:
            return []
        
        # Calculate period size in seconds
        period_seconds = 3600 if period == 'hourly' else 86400
        
        # Group events by period
        periods = defaultdict(list)
        for event in events:
            event_data = event if isinstance(event, dict) else event.to_dict()
            timestamp = self._normalize_timestamp(event_data.get('timestamp', 0))
            period_key = int(timestamp / period_seconds) * period_seconds
            periods[period_key].append(event_data)
        
        # Calculate metric for each period
        trend_data = []
        for period_key in sorted(periods.keys()):
            period_events = periods[period_key]
            value = self._calculate_metric(period_events, metric)
            trend_data.append({
                "timestamp": period_key,
                "value": value,
                "event_count": len(period_events)
            })
        
        return trend_data
    
    # Helper methods
    
    def _get_events_since(self, 
                         start_time: Union[float, datetime, timedelta], 
                         event_types: Optional[List[str]] = None) -> List[Any]:
        """Get events since a specific time"""
        try:
            if isinstance(start_time, timedelta):
                start_ts = time.time() - start_time.total_seconds()
            elif isinstance(start_time, datetime):
                start_ts = start_time.timestamp()
            else:
                start_ts = float(start_time)

            # Query audit logger for events
            events = self.audit_logger.query_events(
                start_time=start_ts,
                event_types=event_types
            )
            return events
        except Exception as e:
            logger.error(f"Error querying events: {e}")
            return []

    def _normalize_timestamp(self, value: Any) -> float:
        """Normalize timestamp to float epoch seconds."""
        if isinstance(value, datetime):
            return value.timestamp()
        try:
            return float(value)
        except Exception:
            return 0.0
    
    def _detect_failed_auth_pattern(self, events: List[Any]) -> Optional[Pattern]:
        """Detect repeated failed authentication attempts"""
        failed_auth = [
            e if isinstance(e, dict) else e.to_dict() 
            for e in events 
            if (e if isinstance(e, dict) else e.to_dict()).get('event_type') == 'authentication'
            and (e if isinstance(e, dict) else e.to_dict()).get('status') == 'failed'
        ]
        
        if len(failed_auth) >= self.min_pattern_occurrences:
            user_failures = Counter(e.get('user_id') for e in failed_auth)
            affected = [u for u, c in user_failures.items() if c >= 3]
            
            if affected:
                return Pattern(
                    pattern_type="repeated_failed_auth",
                    description=f"Repeated failed authentication attempts detected",
                    occurrences=len(failed_auth),
                    first_seen=min(self._normalize_timestamp(e.get('timestamp', 0)) for e in failed_auth),
                    last_seen=max(self._normalize_timestamp(e.get('timestamp', 0)) for e in failed_auth),
                    confidence=min(1.0, len(affected) / 5.0),
                    affected_users=affected,
                    sample_events=failed_auth[:3]
                )
        return None
    
    def _detect_unusual_time_pattern(self, events: List[Any]) -> Optional[Pattern]:
        """Detect access during unusual hours"""
        unusual_events = []
        for event in events:
            event_data = event if isinstance(event, dict) else event.to_dict()
            timestamp = self._normalize_timestamp(event_data.get('timestamp', 0))
            hour = datetime.fromtimestamp(timestamp).hour
            
            # Define unusual hours (10 PM to 6 AM)
            if hour >= 22 or hour <= 6:
                unusual_events.append(event_data)
        
        if len(unusual_events) >= self.min_pattern_occurrences:
            return Pattern(
                pattern_type="unusual_access_time",
                description="Access during unusual hours (10 PM - 6 AM)",
                occurrences=len(unusual_events),
                first_seen=min(self._normalize_timestamp(e.get('timestamp', 0)) for e in unusual_events),
                last_seen=max(self._normalize_timestamp(e.get('timestamp', 0)) for e in unusual_events),
                confidence=min(1.0, len(unusual_events) / 10.0),
                affected_users=list(set(e.get('user_id') for e in unusual_events if e.get('user_id'))),
                sample_events=unusual_events[:3]
            )
        return None
    
    def _detect_sequence_patterns(self, events: List[Any]) -> List[Pattern]:
        """Detect common event sequences"""
        # This is a simplified implementation
        # In production, you'd use more sophisticated sequence mining algorithms
        return []
    
    def _detect_frequency_patterns(self, events: List[Any]) -> List[Pattern]:
        """Detect unusual frequency patterns"""
        if len(events) < 10:
            return []
        
        # Group by action
        action_counts = Counter()
        for event in events:
            event_data = event if isinstance(event, dict) else event.to_dict()
            action = event_data.get('action', 'unknown')
            action_counts[action] += 1
        
        # Find high-frequency actions
        patterns = []
        total_events = len(events)
        for action, count in action_counts.most_common(3):
            if count >= self.min_pattern_occurrences:
                patterns.append(Pattern(
                    pattern_type="high_frequency_action",
                    description=f"High frequency of action: {action}",
                    occurrences=count,
                    first_seen=min(
                        (e if isinstance(e, dict) else e.to_dict()).get('timestamp', 0)
                        for e in events
                        if (e if isinstance(e, dict) else e.to_dict()).get('action') == action
                    ),
                    last_seen=max(
                        (e if isinstance(e, dict) else e.to_dict()).get('timestamp', 0)
                        for e in events
                        if (e if isinstance(e, dict) else e.to_dict()).get('action') == action
                    ),
                    confidence=min(1.0, count / total_events * 5.0),
                    affected_users=[],
                    sample_events=[]
                ))
        
        return patterns
    
    def _detect_frequency_anomalies(self, events: List[Any], threshold: float) -> List[Anomaly]:
        """Detect anomalies in event frequency"""
        if len(events) < 20:
            return []
        
        # Calculate hourly event counts
        hourly_counts = defaultdict(int)
        for event in events:
            event_data = event if isinstance(event, dict) else event.to_dict()
            timestamp = event_data.get('timestamp', 0)
            hour_key = int(timestamp / 3600)
            hourly_counts[hour_key] += 1
        
        counts = list(hourly_counts.values())
        if len(counts) < 2:
            return []
        
        mean_count = statistics.mean(counts)
        try:
            stdev_count = statistics.stdev(counts)
        except statistics.StatisticsError:
            stdev_count = 0
        
        if stdev_count == 0:
            return []
        
        anomalies = []
        for hour_key, count in hourly_counts.items():
            deviation = abs(count - mean_count) / stdev_count
            if deviation > threshold:
                severity = "critical" if deviation > 3.0 else "high" if deviation > 2.5 else "medium"
                anomalies.append(Anomaly(
                    anomaly_type="unusual_event_frequency",
                    description=f"Unusual event frequency: {count} events (mean: {mean_count:.1f})",
                    severity=severity,
                    timestamp=hour_key * 3600,
                    deviation_score=deviation,
                    details={"count": count, "mean": mean_count, "stdev": stdev_count}
                ))
        
        return anomalies
    
    def _detect_user_anomalies(self, events: List[Any], threshold: float) -> List[Anomaly]:
        """Detect anomalous user behavior"""
        user_events = defaultdict(list)
        for event in events:
            event_data = event if isinstance(e, dict) else event.to_dict()
            user_id = event_data.get('user_id')
            if user_id:
                user_events[user_id].append(event_data)
        
        anomalies = []
        # Check for users with unusually high activity
        event_counts = [len(evts) for evts in user_events.values()]
        if len(event_counts) < 2:
            return []
        
        mean_activity = statistics.mean(event_counts)
        try:
            stdev_activity = statistics.stdev(event_counts)
        except statistics.StatisticsError:
            stdev_activity = 0
        
        if stdev_activity == 0:
            return []
        
        for user_id, user_evts in user_events.items():
            deviation = abs(len(user_evts) - mean_activity) / stdev_activity
            if deviation > threshold:
                anomalies.append(Anomaly(
                    anomaly_type="unusual_user_activity",
                    description=f"User {user_id} has unusual activity level",
                    severity="high" if deviation > 2.5 else "medium",
                    timestamp=user_evts[-1].get('timestamp', 0),
                    affected_user=user_id,
                    deviation_score=deviation,
                    details={"event_count": len(user_evts), "mean": mean_activity}
                ))
        
        return anomalies
    
    def _detect_suspicious_combinations(self, events: List[Any]) -> List[Anomaly]:
        """Detect suspicious event combinations"""
        # Simplified implementation - look for privilege escalation patterns
        return []
    
    def _detect_geographic_anomalies(self, events: List[Any]) -> List[Anomaly]:
        """Detect geographic anomalies based on IP addresses"""
        # Simplified implementation - would need IP geolocation data
        return []
    
    def _check_event_compliance(self, 
                                event: Dict[str, Any], 
                                policy_rules: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if an event is compliant with policy rules"""
        # Check forbidden actions
        forbidden = policy_rules.get('forbidden_actions', [])
        if event.get('action') in forbidden:
            return False, {
                "event_id": event.get('request_id'),
                "violation": "forbidden_action",
                "action": event.get('action'),
                "timestamp": event.get('timestamp')
            }
        
        # Check required audit for sensitive actions
        if policy_rules.get('require_audit_all_access', False):
            if not event.get('timestamp'):  # Simplified check
                return False, {
                    "event_id": event.get('request_id'),
                    "violation": "missing_audit",
                    "action": event.get('action')
                }
        
        return True, None
    
    def _generate_recommendations(self, 
                                 violations: List[Dict[str, Any]], 
                                 policy_rules: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on violations"""
        recommendations = []
        
        violation_types = Counter(v.get('violation') for v in violations)
        
        if violation_types.get('forbidden_action', 0) > 0:
            recommendations.append(
                "Review and restrict access to forbidden actions"
            )
        
        if violation_types.get('missing_audit', 0) > 0:
            recommendations.append(
                "Ensure all sensitive operations are properly audited"
            )
        
        if len(violations) > len(policy_rules) * 2:
            recommendations.append(
                "Consider reviewing and updating security policies"
            )
        
        return recommendations
    
    def _calculate_metric(self, events: List[Dict[str, Any]], metric: str) -> float:
        """Calculate specific metric for events"""
        if metric == 'event_count':
            return len(events)
        elif metric == 'failed_auth':
            return sum(
                1 for e in events 
                if e.get('event_type') == 'authentication' and e.get('status') == 'failed'
            )
        elif metric == 'unique_users':
            return len(set(e.get('user_id') for e in events if e.get('user_id')))
        else:
            return len(events)
