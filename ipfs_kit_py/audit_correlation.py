"""
Event Correlation Module for IPFS Kit Audit System

This module provides advanced event correlation capabilities including:
- Timeline reconstruction for operations
- Causation analysis to identify event chains
- Impact assessment for audit events
- Related event detection across subsystems

Part of Phase 8: Enhanced Audit Capabilities
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CorrelatedEvent:
    """Represents a correlated audit event"""
    event_id: str
    timestamp: datetime
    event_type: str
    user_id: Optional[str]
    action: str
    resource: Optional[str]
    correlation_score: float  # 0.0 to 1.0
    correlation_reason: str
    metadata: Dict


@dataclass
class Timeline:
    """Represents a reconstructed timeline of related events"""
    operation_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    events: List[CorrelatedEvent]
    event_count: int
    subsystems: Set[str]
    summary: str


@dataclass
class CausationChain:
    """Represents a chain of causally related events"""
    effect_event: CorrelatedEvent
    cause_events: List[CorrelatedEvent]
    chain_length: int
    confidence: float
    explanation: str


@dataclass
class ImpactAssessment:
    """Represents the impact assessment of an event"""
    event_id: str
    impact_level: str  # "low", "medium", "high", "critical"
    affected_resources: List[str]
    affected_users: Set[str]
    downstream_events: List[CorrelatedEvent]
    impact_score: float  # 0.0 to 1.0
    recommendations: List[str]


class EventCorrelator:
    """
    Correlates related audit events and reconstructs timelines
    
    This class provides sophisticated event correlation capabilities
    including timeline reconstruction, causation analysis, and impact
    assessment for audit events.
    """
    
    def __init__(self, audit_logger, config: Optional[Dict] = None):
        """
        Initialize the event correlator
        
        Args:
            audit_logger: AuditLogger instance
            config: Configuration dictionary
        """
        self.audit_logger = audit_logger
        self.config = config or {}
        
        # Configuration parameters
        self.default_time_window = self.config.get('default_time_window', 300)  # 5 minutes
        self.correlation_threshold = self.config.get('correlation_threshold', 0.5)
        self.max_chain_depth = self.config.get('max_chain_depth', 10)
        
        logger.info("EventCorrelator initialized")
    
    def correlate_events(
        self, 
        event_id: str, 
        time_window: Optional[int] = None,
        max_results: int = 100
    ) -> List[CorrelatedEvent]:
        """
        Find related events within a time window
        
        Args:
            event_id: The reference event ID
            time_window: Time window in seconds (default: from config)
            max_results: Maximum number of results to return
            
        Returns:
            List of correlated events with correlation scores
        """
        if time_window is None:
            time_window = self.default_time_window
        
        # Get the reference event
        try:
            ref_event = self._get_event_by_id(event_id)
            if not ref_event:
                logger.warning(f"Reference event {event_id} not found")
                return []
        except Exception as e:
            logger.error(f"Error getting reference event: {e}")
            return []
        
        ref_time = ref_event['timestamp']
        ref_user = ref_event.get('user_id')
        ref_resource = ref_event.get('resource')
        ref_action = ref_event.get('action')
        
        # Define time range
        start_time = ref_time - timedelta(seconds=time_window)
        end_time = ref_time + timedelta(seconds=time_window)
        
        # Query events in time window
        try:
            events = self.audit_logger.query_events(
                start_time=start_time,
                end_time=end_time
            )
        except Exception as e:
            logger.error(f"Error querying events: {e}")
            return []
        
        # Calculate correlations
        correlated = []
        for event in events:
            if event.get('event_id') == event_id:
                continue  # Skip the reference event itself
            
            score, reason = self._calculate_correlation_score(
                ref_event, event, ref_user, ref_resource, ref_action
            )
            
            if score >= self.correlation_threshold:
                correlated.append(CorrelatedEvent(
                    event_id=event.get('event_id', ''),
                    timestamp=event['timestamp'],
                    event_type=event.get('event_type', ''),
                    user_id=event.get('user_id'),
                    action=event.get('action', ''),
                    resource=event.get('resource'),
                    correlation_score=score,
                    correlation_reason=reason,
                    metadata=event.get('metadata', {})
                ))
        
        # Sort by correlation score (descending) and limit
        correlated.sort(key=lambda x: x.correlation_score, reverse=True)
        return correlated[:max_results]
    
    def _calculate_correlation_score(
        self, 
        ref_event: Dict, 
        event: Dict,
        ref_user: Optional[str],
        ref_resource: Optional[str],
        ref_action: str
    ) -> Tuple[float, str]:
        """Calculate correlation score between two events"""
        score = 0.0
        reasons = []
        
        # Same user correlation
        if ref_user and event.get('user_id') == ref_user:
            score += 0.4
            reasons.append("same user")
        
        # Same resource correlation
        if ref_resource and event.get('resource') == ref_resource:
            score += 0.3
            reasons.append("same resource")
        
        # Related action correlation
        event_action = event.get('action', '')
        if self._are_actions_related(ref_action, event_action):
            score += 0.2
            reasons.append("related actions")
        
        # Session correlation (if session IDs present)
        ref_session = ref_event.get('metadata', {}).get('session_id')
        event_session = event.get('metadata', {}).get('session_id')
        if ref_session and event_session == ref_session:
            score += 0.3
            reasons.append("same session")
        
        # Transaction ID correlation
        ref_txn = ref_event.get('metadata', {}).get('transaction_id')
        event_txn = event.get('metadata', {}).get('transaction_id')
        if ref_txn and event_txn == ref_txn:
            score += 0.5
            reasons.append("same transaction")
        
        # Operation ID correlation
        ref_op = ref_event.get('metadata', {}).get('operation_id')
        event_op = event.get('metadata', {}).get('operation_id')
        if ref_op and event_op == ref_op:
            score += 0.6
            reasons.append("same operation")
        
        # Cap score at 1.0
        score = min(score, 1.0)
        
        reason = ", ".join(reasons) if reasons else "time proximity"
        return score, reason
    
    def _are_actions_related(self, action1: str, action2: str) -> bool:
        """Determine if two actions are related"""
        # Define related action pairs
        related_pairs = [
            ('create', 'upload'),
            ('read', 'download'),
            ('update', 'modify'),
            ('delete', 'remove'),
            ('authenticate', 'login'),
            ('authorize', 'access'),
        ]
        
        action1_lower = action1.lower()
        action2_lower = action2.lower()
        
        for a, b in related_pairs:
            if (action1_lower == a and action2_lower == b) or \
               (action1_lower == b and action2_lower == a):
                return True
        
        return False
    
    def reconstruct_timeline(
        self, 
        operation_id: str,
        include_subsystems: bool = True
    ) -> Optional[Timeline]:
        """
        Reconstruct complete operation timeline
        
        Args:
            operation_id: The operation ID to reconstruct
            include_subsystems: Include events from all subsystems
            
        Returns:
            Timeline object with all related events
        """
        try:
            # Query all events with this operation_id
            events = self.audit_logger.query_events(
                filters={'metadata.operation_id': operation_id}
            )
            
            if not events:
                logger.warning(f"No events found for operation {operation_id}")
                return None
            
            # Sort events by timestamp
            events.sort(key=lambda x: x['timestamp'])
            
            # Convert to CorrelatedEvent objects
            correlated_events = []
            subsystems = set()
            
            for event in events:
                correlated_events.append(CorrelatedEvent(
                    event_id=event.get('event_id', ''),
                    timestamp=event['timestamp'],
                    event_type=event.get('event_type', ''),
                    user_id=event.get('user_id'),
                    action=event.get('action', ''),
                    resource=event.get('resource'),
                    correlation_score=1.0,  # All events in same operation
                    correlation_reason="same operation ID",
                    metadata=event.get('metadata', {})
                ))
                
                # Track subsystems
                subsystem = event.get('metadata', {}).get('subsystem')
                if subsystem:
                    subsystems.add(subsystem)
            
            # Calculate timeline metrics
            start_time = events[0]['timestamp']
            end_time = events[-1]['timestamp']
            duration = (end_time - start_time).total_seconds()
            
            # Generate summary
            summary = self._generate_timeline_summary(correlated_events)
            
            return Timeline(
                operation_id=operation_id,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                events=correlated_events,
                event_count=len(correlated_events),
                subsystems=subsystems,
                summary=summary
            )
            
        except Exception as e:
            logger.error(f"Error reconstructing timeline: {e}")
            return None
    
    def _generate_timeline_summary(self, events: List[CorrelatedEvent]) -> str:
        """Generate a human-readable summary of the timeline"""
        if not events:
            return "Empty timeline"
        
        action_counts = defaultdict(int)
        for event in events:
            action_counts[event.action] += 1
        
        # Get most common actions
        top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        action_str = ", ".join([f"{action} ({count})" for action, count in top_actions])
        
        return f"{len(events)} events: {action_str}"
    
    def analyze_causation(
        self, 
        effect_event_id: str,
        max_depth: Optional[int] = None
    ) -> Optional[CausationChain]:
        """
        Identify causal chain leading to an event
        
        Args:
            effect_event_id: The effect event ID
            max_depth: Maximum chain depth (default: from config)
            
        Returns:
            CausationChain object with causal events
        """
        if max_depth is None:
            max_depth = self.max_chain_depth
        
        try:
            # Get the effect event
            effect_event = self._get_event_by_id(effect_event_id)
            if not effect_event:
                logger.warning(f"Effect event {effect_event_id} not found")
                return None
            
            # Build effect event object
            effect = CorrelatedEvent(
                event_id=effect_event.get('event_id', ''),
                timestamp=effect_event['timestamp'],
                event_type=effect_event.get('event_type', ''),
                user_id=effect_event.get('user_id'),
                action=effect_event.get('action', ''),
                resource=effect_event.get('resource'),
                correlation_score=1.0,
                correlation_reason="effect event",
                metadata=effect_event.get('metadata', {})
            )
            
            # Find preceding events (potential causes)
            cause_events = []
            current_time = effect_event['timestamp']
            
            for depth in range(1, max_depth + 1):
                # Look back in increasingly larger windows
                lookback_seconds = depth * 60  # 1 min, 2 min, 3 min, etc.
                start_time = current_time - timedelta(seconds=lookback_seconds)
                
                # Get events in this window
                events = self.audit_logger.query_events(
                    start_time=start_time,
                    end_time=current_time
                )
                
                # Filter for causal candidates
                for event in events:
                    if event['timestamp'] < effect_event['timestamp']:
                        # Check if this could be a cause
                        if self._is_potential_cause(event, effect_event):
                            cause_events.append(CorrelatedEvent(
                                event_id=event.get('event_id', ''),
                                timestamp=event['timestamp'],
                                event_type=event.get('event_type', ''),
                                user_id=event.get('user_id'),
                                action=event.get('action', ''),
                                resource=event.get('resource'),
                                correlation_score=self._calculate_causation_score(event, effect_event),
                                correlation_reason="potential cause",
                                metadata=event.get('metadata', {})
                            ))
                
                if cause_events:
                    break  # Found causes, stop looking
            
            # Sort by timestamp (earliest first)
            cause_events.sort(key=lambda x: x.timestamp)
            
            # Calculate confidence
            confidence = self._calculate_chain_confidence(cause_events, effect)
            
            # Generate explanation
            explanation = self._generate_causation_explanation(cause_events, effect)
            
            return CausationChain(
                effect_event=effect,
                cause_events=cause_events,
                chain_length=len(cause_events),
                confidence=confidence,
                explanation=explanation
            )
            
        except Exception as e:
            logger.error(f"Error analyzing causation: {e}")
            return None
    
    def _is_potential_cause(self, event: Dict, effect_event: Dict) -> bool:
        """Determine if an event could be a cause of the effect"""
        # Same user
        if event.get('user_id') == effect_event.get('user_id'):
            return True
        
        # Same resource
        if event.get('resource') == effect_event.get('resource'):
            return True
        
        # Same operation
        if event.get('metadata', {}).get('operation_id') == \
           effect_event.get('metadata', {}).get('operation_id'):
            return True
        
        # Error event followed by failure
        if 'error' in event.get('event_type', '').lower() and \
           'fail' in effect_event.get('action', '').lower():
            return True
        
        return False
    
    def _calculate_causation_score(self, cause_event: Dict, effect_event: Dict) -> float:
        """Calculate how likely this event caused the effect"""
        score = 0.0
        
        # Time proximity (closer = higher score)
        time_diff = (effect_event['timestamp'] - cause_event['timestamp']).total_seconds()
        if time_diff < 10:
            score += 0.4
        elif time_diff < 60:
            score += 0.3
        elif time_diff < 300:
            score += 0.2
        
        # Same operation/transaction
        if cause_event.get('metadata', {}).get('operation_id') == \
           effect_event.get('metadata', {}).get('operation_id'):
            score += 0.4
        
        # Error-failure pattern
        if 'error' in cause_event.get('event_type', '').lower() and \
           'fail' in effect_event.get('action', '').lower():
            score += 0.3
        
        return min(score, 1.0)
    
    def _calculate_chain_confidence(
        self, 
        causes: List[CorrelatedEvent], 
        effect: CorrelatedEvent
    ) -> float:
        """Calculate confidence in the causation chain"""
        if not causes:
            return 0.0
        
        # Average correlation scores
        avg_score = sum(c.correlation_score for c in causes) / len(causes)
        
        # Adjust for chain length (shorter = more confident)
        length_factor = 1.0 / (1.0 + len(causes) * 0.1)
        
        return min(avg_score * length_factor, 1.0)
    
    def _generate_causation_explanation(
        self, 
        causes: List[CorrelatedEvent], 
        effect: CorrelatedEvent
    ) -> str:
        """Generate human-readable explanation of causation"""
        if not causes:
            return "No clear causal chain identified"
        
        explanations = []
        for cause in causes:
            time_str = cause.timestamp.strftime("%H:%M:%S")
            explanations.append(f"{time_str}: {cause.action} on {cause.resource or 'system'}")
        
        return " → ".join(explanations) + f" → {effect.action}"
    
    def assess_impact(
        self, 
        event_id: str,
        time_window: int = 600
    ) -> Optional[ImpactAssessment]:
        """
        Assess the impact of an event on the system
        
        Args:
            event_id: The event ID to assess
            time_window: Time window for impact assessment (seconds)
            
        Returns:
            ImpactAssessment object with impact details
        """
        try:
            # Get the event
            event = self._get_event_by_id(event_id)
            if not event:
                logger.warning(f"Event {event_id} not found")
                return None
            
            # Get downstream events (events that followed)
            downstream = self.correlate_events(
                event_id, 
                time_window=time_window
            )
            
            # Filter for events that came after
            event_time = event['timestamp']
            downstream = [e for e in downstream if e.timestamp > event_time]
            
            # Identify affected resources and users
            affected_resources = set()
            affected_users = set()
            
            for e in downstream:
                if e.resource:
                    affected_resources.add(e.resource)
                if e.user_id:
                    affected_users.add(e.user_id)
            
            # Calculate impact score
            impact_score = self._calculate_impact_score(event, downstream)
            
            # Determine impact level
            impact_level = self._determine_impact_level(impact_score, downstream)
            
            # Generate recommendations
            recommendations = self._generate_impact_recommendations(
                event, downstream, impact_level
            )
            
            return ImpactAssessment(
                event_id=event_id,
                impact_level=impact_level,
                affected_resources=list(affected_resources),
                affected_users=affected_users,
                downstream_events=downstream,
                impact_score=impact_score,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error assessing impact: {e}")
            return None
    
    def _calculate_impact_score(
        self, 
        event: Dict, 
        downstream: List[CorrelatedEvent]
    ) -> float:
        """Calculate numerical impact score"""
        score = 0.0
        
        # Number of downstream events
        score += min(len(downstream) * 0.1, 0.4)
        
        # Presence of error events
        error_count = sum(1 for e in downstream if 'error' in e.event_type.lower())
        score += min(error_count * 0.15, 0.3)
        
        # Event type severity
        if 'error' in event.get('event_type', '').lower():
            score += 0.2
        if 'security' in event.get('event_type', '').lower():
            score += 0.3
        
        return min(score, 1.0)
    
    def _determine_impact_level(
        self, 
        score: float, 
        downstream: List[CorrelatedEvent]
    ) -> str:
        """Determine impact level from score"""
        if score >= 0.8:
            return "critical"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        else:
            return "low"
    
    def _generate_impact_recommendations(
        self, 
        event: Dict, 
        downstream: List[CorrelatedEvent],
        impact_level: str
    ) -> List[str]:
        """Generate recommendations based on impact"""
        recommendations = []
        
        if impact_level in ("critical", "high"):
            recommendations.append("Immediate investigation recommended")
            recommendations.append("Consider enabling additional monitoring")
        
        error_count = sum(1 for e in downstream if 'error' in e.event_type.lower())
        if error_count > 0:
            recommendations.append(f"Review {error_count} error events in downstream chain")
        
        if 'security' in event.get('event_type', '').lower():
            recommendations.append("Security review recommended")
            recommendations.append("Check for unauthorized access attempts")
        
        if not recommendations:
            recommendations.append("No immediate action required")
        
        return recommendations
    
    def _get_event_by_id(self, event_id: str) -> Optional[Dict]:
        """Get a single event by ID"""
        try:
            events = self.audit_logger.query_events(
                filters={'event_id': event_id},
                limit=1
            )
            return events[0] if events else None
        except Exception as e:
            logger.error(f"Error getting event {event_id}: {e}")
            return None
