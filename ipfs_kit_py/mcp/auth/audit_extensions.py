"""
Audit Extensions for MCP Server

This module extends the basic audit logging functionality with advanced features:
- Log event categorization and filtering
- Log export and retention policies
- Security alerting integration
- Log integrity verification

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import json
import asyncio
import time
import os
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from pathlib import Path

from ipfs_kit_py.mcp.auth.audit import AuditLogger, get_instance as get_audit_logger

logger = logging.getLogger(__name__)

# Security event patterns to monitor
SECURITY_EVENTS = {
    "high": [
        {"action": "login", "status": "failure", "count": 5, "window": 300},  # 5 failed logins in 5 minutes
        {"action": "backend_access_denied", "count": 3, "window": 60},  # 3 denied accesses in 1 minute
        {"action": "api_key_revoked", "count": 1, "window": 60},  # Any key revocation
        {"action": "user_role_changed", "count": 1, "window": 60, "roles": ["admin"]},  # Admin role changes
    ],
    "medium": [
        {"action": "login", "status": "failure", "count": 3, "window": 300},  # 3 failed logins in 5 minutes
        {"action": "user_created", "count": 5, "window": 300},  # Unusual user creation rate
        {"action": "api_key_created", "count": 5, "window": 300},  # Unusual API key creation rate
    ],
    "low": [
        {"action": "login", "status": "success", "from_new_ip": True, "count": 1, "window": 86400},  # Login from new IP
        {"action": "config_changed", "count": 1, "window": 3600},  # Configuration changes
    ],
}


class AuditExtensions:
    """
    Extensions to the core AuditLogger for enhanced security monitoring.
    """
    
    def __init__(self, audit_logger: AuditLogger):
        """
        Initialize audit extensions with a reference to the main audit logger.
        
        Args:
            audit_logger: Main audit logger instance
        """
        self.audit_logger = audit_logger
        
        # Event counters for pattern detection
        self._event_counters: Dict[str, List[float]] = {}
        
        # User IP tracking
        self._user_ips: Dict[str, Set[str]] = {}
        
        # Log integrity tracking
        self._last_log_hash: Optional[str] = None
        self._integrity_logs: List[Dict[str, Any]] = []
        
        # Alert subscribers
        self._alert_subscribers: List[callable] = []
        
        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        
        logger.info("Audit extensions initialized")
    
    async def start(self):
        """Start the audit extensions background tasks."""
        # Start log integrity verification task
        integrity_task = asyncio.create_task(self._verify_log_integrity_task())
        self._background_tasks.append(integrity_task)
        
        # Start log retention task
        retention_task = asyncio.create_task(self._enforce_retention_policy_task())
        self._background_tasks.append(retention_task)
        
        logger.info("Audit extensions background tasks started")
    
    async def stop(self):
        """Stop the audit extensions background tasks."""
        # Signal tasks to shut down
        self._shutdown_event.set()
        
        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        logger.info("Audit extensions background tasks stopped")
    
    async def process_log_event(self, event: Dict[str, Any]):
        """
        Process an audit log event for security pattern detection.
        
        Args:
            event: Audit log event
        """
        # Update event counters for pattern detection
        action = event.get("action")
        if action:
            counter_key = action
            if "status" in event:
                counter_key = f"{action}:{event['status']}"
            
            if counter_key not in self._event_counters:
                self._event_counters[counter_key] = []
            
            # Add current timestamp
            self._event_counters[counter_key].append(time.time())
            
            # Clean up old timestamps
            self._cleanup_counters(counter_key)
        
        # Track user IPs for detecting new login locations
        if event.get("action") == "login" and event.get("status") == "success":
            user_id = event.get("user_id")
            ip_address = event.get("ip_address")
            
            if user_id and ip_address:
                if user_id not in self._user_ips:
                    self._user_ips[user_id] = set()
                
                # Check if this is a new IP
                is_new_ip = ip_address not in self._user_ips[user_id]
                
                # Add the IP to the user's set
                self._user_ips[user_id].add(ip_address)
                
                # If this is a new IP, log it and potentially alert
                if is_new_ip:
                    event["from_new_ip"] = True
                    await self.audit_logger.log_event(
                        action="login_from_new_ip",
                        user_id=user_id,
                        username=event.get("username"),
                        ip_address=ip_address,
                        status="success",
                        details={
                            "ip_address": ip_address,
                            "previous_ips": list(self._user_ips[user_id] - {ip_address})
                        },
                        priority="medium"
                    )
        
        # Check for security patterns
        await self._check_security_patterns(event)
        
        # Update log integrity chain
        await self._update_log_integrity(event)
    
    def _cleanup_counters(self, counter_key: str, max_age: int = 86400):
        """
        Clean up old timestamps from event counters.
        
        Args:
            counter_key: Counter key to clean up
            max_age: Maximum age of timestamps to keep (in seconds)
        """
        if counter_key in self._event_counters:
            now = time.time()
            self._event_counters[counter_key] = [
                ts for ts in self._event_counters[counter_key]
                if now - ts <= max_age
            ]
    
    async def _check_security_patterns(self, event: Dict[str, Any]):
        """
        Check if the event matches any security alert patterns.
        
        Args:
            event: Audit log event
        """
        # Check all severity levels
        for severity, patterns in SECURITY_EVENTS.items():
            for pattern in patterns:
                # First check if the basic action/status match
                if pattern.get("action") != event.get("action"):
                    continue
                
                if "status" in pattern and pattern["status"] != event.get("status"):
                    continue
                
                if "from_new_ip" in pattern and pattern["from_new_ip"] != event.get("from_new_ip", False):
                    continue
                
                if "roles" in pattern:
                    # For role-related events, check if any of the specified roles are involved
                    role_match = False
                    if "details" in event and "roles" in event["details"]:
                        for role in pattern["roles"]:
                            if role in event["details"]["roles"]:
                                role_match = True
                                break
                    if not role_match:
                        continue
                
                # Now check the event count within the time window
                counter_key = event.get("action")
                if "status" in event:
                    counter_key = f"{counter_key}:{event['status']}"
                
                if counter_key in self._event_counters:
                    now = time.time()
                    window_start = now - pattern.get("window", 300)
                    
                    # Count events in the window
                    events_in_window = sum(
                        1 for ts in self._event_counters[counter_key]
                        if ts >= window_start
                    )
                    
                    # If count threshold is reached, trigger alert
                    if events_in_window >= pattern.get("count", 1):
                        await self._trigger_security_alert(
                            severity=severity,
                            event=event,
                            pattern=pattern,
                            count=events_in_window
                        )
    
    async def _trigger_security_alert(
        self,
        severity: str,
        event: Dict[str, Any],
        pattern: Dict[str, Any],
        count: int
    ):
        """
        Trigger a security alert based on a detected pattern.
        
        Args:
            severity: Alert severity (high, medium, low)
            event: Triggering audit log event
            pattern: Security pattern that was matched
            count: Number of events that triggered the alert
        """
        # Create alert details
        alert = {
            "timestamp": time.time(),
            "severity": severity,
            "trigger_event": event,
            "pattern_matched": pattern,
            "event_count": count,
            "time_window_seconds": pattern.get("window", 300),
        }
        
        # Log the security alert
        await self.audit_logger.log_event(
            action="security_alert",
            user_id=event.get("user_id"),
            username=event.get("username"),
            status="alert",
            details=alert,
            priority=severity
        )
        
        # Notify all subscribers
        for subscriber in self._alert_subscribers:
            try:
                await subscriber(alert)
            except Exception as e:
                logger.error(f"Error notifying security alert subscriber: {e}")
    
    async def _update_log_integrity(self, event: Dict[str, Any]):
        """
        Update the log integrity chain with a new event.
        
        This creates a hash chain that can be used to verify log integrity.
        
        Args:
            event: Audit log event
        """
        # Create event string
        event_str = json.dumps(event, sort_keys=True)
        
        # Calculate hash including previous hash if available
        hash_input = event_str
        if self._last_log_hash:
            hash_input = f"{self._last_log_hash}:{hash_input}"
        
        # Calculate new hash
        new_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        # Update last hash
        self._last_log_hash = new_hash
        
        # Store integrity log entry
        integrity_entry = {
            "event_id": event.get("id"),
            "timestamp": event.get("timestamp"),
            "hash": new_hash,
            "previous_hash": self._last_log_hash if self._last_log_hash != new_hash else None,
        }
        
        self._integrity_logs.append(integrity_entry)
        
        # Keep only the last 1000 integrity logs in memory
        if len(self._integrity_logs) > 1000:
            self._integrity_logs = self._integrity_logs[-1000:]
    
    async def _verify_log_integrity_task(self):
        """
        Background task for regular log integrity verification.
        """
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Verify log integrity once per hour
                    await self._verify_log_integrity()
                    
                    # Wait for the next check or until shutdown
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=3600  # 1 hour
                        )
                    except asyncio.TimeoutError:
                        # Normal timeout, continue with next verification
                        pass
                    
                except Exception as e:
                    logger.error(f"Error in log integrity verification: {e}")
                    # Wait a bit before trying again
                    await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Log integrity verification task cancelled")
    
    async def _verify_log_integrity(self):
        """
        Verify the integrity of the audit log.
        
        This rebuilds the hash chain and checks for any discrepancies.
        """
        logger.info("Verifying audit log integrity")
        
        # Get audit logs from storage
        logs = await self.audit_logger.query_logs(
            start_time=datetime.utcnow() - timedelta(days=1),
            limit=10000,
            ascending=True  # Get in chronological order
        )
        
        if not logs:
            logger.info("No logs to verify")
            return
        
        # Rebuild hash chain
        calculated_hash = None
        integrity_violations = []
        
        for i, log in enumerate(logs):
            # Skip non-standard logs
            if not isinstance(log, dict) or "id" not in log:
                continue
            
            # Create event string
            event_str = json.dumps(log, sort_keys=True)
            
            # Calculate hash
            hash_input = event_str
            if calculated_hash:
                hash_input = f"{calculated_hash}:{hash_input}"
            
            new_hash = hashlib.sha256(hash_input.encode()).hexdigest()
            
            # Check if this log has a stored integrity hash
            stored_hash = None
            for integrity_log in self._integrity_logs:
                if integrity_log.get("event_id") == log.get("id"):
                    stored_hash = integrity_log.get("hash")
                    break
            
            # If we have a stored hash, compare with calculated
            if stored_hash and stored_hash != new_hash:
                integrity_violations.append({
                    "event_id": log.get("id"),
                    "timestamp": log.get("timestamp"),
                    "calculated_hash": new_hash,
                    "stored_hash": stored_hash,
                    "index": i,
                })
            
            # Update calculated hash for next iteration
            calculated_hash = new_hash
        
        # Report any violations
        if integrity_violations:
            logger.warning(f"Detected {len(integrity_violations)} audit log integrity violations")
            
            # Log the integrity violation
            await self.audit_logger.log_event(
                action="audit_log_integrity_violation",
                status="warning",
                details={
                    "violations_count": len(integrity_violations),
                    "first_violation": integrity_violations[0],
                    "violations": integrity_violations[:10]  # Include up to 10 violations
                },
                priority="high"
            )
            
            # Trigger security alert
            await self._trigger_security_alert(
                severity="high",
                event={
                    "action": "audit_log_integrity_violation",
                    "timestamp": time.time(),
                },
                pattern={"action": "audit_log_integrity_violation", "count": 1, "window": 86400},
                count=len(integrity_violations)
            )
        else:
            logger.info("Audit log integrity verified successfully")
    
    async def _enforce_retention_policy_task(self):
        """
        Background task for enforcing log retention policy.
        """
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Enforce retention policy once per day
                    await self._enforce_retention_policy()
                    
                    # Wait for the next check or until shutdown
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=86400  # 24 hours
                        )
                    except asyncio.TimeoutError:
                        # Normal timeout, continue with next verification
                        pass
                    
                except Exception as e:
                    logger.error(f"Error enforcing log retention policy: {e}")
                    # Wait a bit before trying again
                    await asyncio.sleep(300)
        except asyncio.CancelledError:
            logger.info("Log retention policy task cancelled")
    
    async def _enforce_retention_policy(self):
        """Enforce the log retention policy."""
        logger.info("Enforcing audit log retention policy")
        
        # Get retention period from configuration
        retention_days = 90  # Default to 90 days
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_date.timestamp()
        
        # Export logs before deleting (if export is enabled)
        # await self._export_logs_before_deletion(cutoff_timestamp)
        
        # Delete old logs
        deleted_count = await self.audit_logger.delete_logs_before(cutoff_timestamp)
        
        logger.info(f"Deleted {deleted_count} logs older than {cutoff_date.isoformat()}")
    
    def register_alert_subscriber(self, subscriber: callable):
        """
        Register a subscriber for security alerts.
        
        Args:
            subscriber: Async callable that takes an alert dictionary
        """
        self._alert_subscribers.append(subscriber)
        logger.info(f"Registered new security alert subscriber, total subscribers: {len(self._alert_subscribers)}")
    
    def unregister_alert_subscriber(self, subscriber: callable):
        """
        Unregister a subscriber from security alerts.
        
        Args:
            subscriber: Previously registered subscriber
        """
        if subscriber in self._alert_subscribers:
            self._alert_subscribers.remove(subscriber)
            logger.info(f"Unregistered security alert subscriber, remaining subscribers: {len(self._alert_subscribers)}")


# Global extensions instance
_audit_extensions = None


def get_audit_extensions() -> AuditExtensions:
    """
    Get the singleton audit extensions instance.
    
    Returns:
        AuditExtensions instance
    """
    global _audit_extensions
    return _audit_extensions


def extend_audit_logger():
    """
    Extend the audit logger with advanced features.
    
    This function:
    1. Gets the existing audit logger
    2. Creates extensions for it
    3. Patches the log_event method to trigger extension processing
    """
    global _audit_extensions
    
    # Get the audit logger
    audit_logger = get_audit_logger()
    if not audit_logger:
        logger.error("Cannot extend audit logger: Audit logger not initialized")
        return
    
    # Create extensions if needed
    if _audit_extensions is None:
        _audit_extensions = AuditExtensions(audit_logger)
    
    # Store the original log_event method
    original_log_event = audit_logger.log_event
    
    # Define the patched method
    async def patched_log_event(*args, **kwargs):
        # Call the original method first
        result = await original_log_event(*args, **kwargs)
        
        # Get the event that was just logged
        event = None
        if len(args) >= 1 and isinstance(args[0], dict):
            event = args[0]
        elif kwargs.get("action"):
            # Reconstruct the event from kwargs
            event = {
                key: value for key, value in kwargs.items()
                if key in ["action", "user_id", "username", "ip_address", "target", "status", "details", "priority"]
            }
            event["id"] = result  # The result of log_event should be the event ID
            event["timestamp"] = time.time()
        
        # Process the event with extensions
        if event:
            await _audit_extensions.process_log_event(event)
        
        return result
    
    # Patch the method
    audit_logger.log_event = patched_log_event
    
    # Start the extensions background tasks
    asyncio.create_task(_audit_extensions.start())
    
    logger.info("Audit logger extended with advanced features")
    
    return _audit_extensions