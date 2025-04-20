"""
Data Lifecycle Management Module for MCP Server

This module provides comprehensive data lifecycle management capabilities for the MCP server,
enabling policy-based data retention, automated archiving, data classification,
compliance enforcement, and cost optimization strategies.

Key features:
1. Policy-based data retention
2. Automated archiving of infrequently accessed data
3. Data classification based on content type and metadata
4. Compliance enforcement for regulations (GDPR, CCPA, etc.)
5. Cost optimization strategies for storage

Part of the MCP Roadmap Phase 3: Enterprise Features (Q1 2026).
"""

import os
import json
import time
import uuid
import logging
import threading
import asyncio
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set, Tuple, Callable, Union
from datetime import datetime, timedelta
import re
import hashlib

# Configure logger
logger = logging.getLogger(__name__)


class RetentionPolicy(str, Enum):
    """Types of retention policies for data."""
    INDEFINITE = "indefinite"  # Keep data indefinitely
    TIME_BASED = "time_based"  # Keep data for a specific period of time
    ACCESS_BASED = "access_based"  # Keep data based on last access time
    HYBRID = "hybrid"  # Combination of time and access based policies
    CUSTOM = "custom"  # Custom policy with user-defined rules


class DataClassification(str, Enum):
    """Classification levels for data."""
    PUBLIC = "public"  # Public data with no restrictions
    INTERNAL = "internal"  # Internal data with limited access
    CONFIDENTIAL = "confidential"  # Confidential data with restricted access
    RESTRICTED = "restricted"  # Highly restricted data
    REGULATED = "regulated"  # Data subject to regulatory requirements
    PERSONAL = "personal"  # Personal identifiable information (PII)
    CUSTOM = "custom"  # Custom classification with user-defined rules


class ArchiveStrategy(str, Enum):
    """Strategies for data archiving."""
    NONE = "none"  # No archiving
    COLD_STORAGE = "cold_storage"  # Move to cold storage
    COMPRESSION = "compression"  # Compress the data
    TIERED = "tiered"  # Move between storage tiers
    CUSTOM = "custom"  # Custom archiving strategy


class ComplianceRegulation(str, Enum):
    """Common compliance regulations."""
    GDPR = "gdpr"  # General Data Protection Regulation
    CCPA = "ccpa"  # California Consumer Privacy Act
    HIPAA = "hipaa"  # Health Insurance Portability and Accountability Act
    PCI_DSS = "pci_dss"  # Payment Card Industry Data Security Standard
    SOX = "sox"  # Sarbanes-Oxley Act
    CUSTOM = "custom"  # Custom compliance regulation


class CostOptimizationStrategy(str, Enum):
    """Strategies for cost optimization."""
    NONE = "none"  # No cost optimization
    STORAGE_TIERING = "storage_tiering"  # Use different storage tiers based on access patterns
    DEDUPLICATION = "deduplication"  # Remove duplicate data
    COMPRESSION = "compression"  # Compress data to reduce storage costs
    LIFECYCLE_RULES = "lifecycle_rules"  # Apply lifecycle rules to automatically move or delete data
    CUSTOM = "custom"  # Custom cost optimization strategy


class RetentionAction(str, Enum):
    """Actions to take when retention period expires."""
    DELETE = "delete"  # Delete the data
    ARCHIVE = "archive"  # Archive the data
    ANONYMIZE = "anonymize"  # Anonymize the data
    NOTIFY = "notify"  # Notify but take no action
    CUSTOM = "custom"  # Custom action


class DataLifecycleState(str, Enum):
    """Possible states in the data lifecycle."""
    ACTIVE = "active"  # Data is actively used and readily accessible
    ARCHIVED = "archived"  # Data is archived but retrievable
    COLD_STORAGE = "cold_storage"  # Data is in cold storage with slower access
    PENDING_DELETION = "pending_deletion"  # Data is marked for deletion
    DELETED = "deleted"  # Data is deleted
    LEGAL_HOLD = "legal_hold"  # Data is on legal hold and cannot be modified or deleted
    ANONYMIZED = "anonymized"  # Data has been anonymized
    CUSTOM = "custom"  # Custom state


@dataclass
class RetentionRule:
    """Rule for data retention."""
    id: str
    name: str
    policy_type: RetentionPolicy
    description: Optional[str] = None
    # Time-based retention parameters
    retention_period_days: Optional[int] = None
    # Access-based retention parameters
    max_inactive_days: Optional[int] = None
    # Action to take when retention period expires
    expiration_action: RetentionAction = RetentionAction.ARCHIVE
    # Custom action function for CUSTOM action
    custom_action: Optional[str] = None
    # Whether this rule can be overridden by legal hold
    allow_legal_hold_override: bool = True
    # Whether this rule is enabled
    enabled: bool = True
    # Creation and update timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    # Tags for the rule
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def is_expired(self, last_modified: datetime, last_accessed: Optional[datetime] = None) -> bool:
        """
        Check if data with the given last modified and last accessed times has expired.
        
        Args:
            last_modified: The last time the data was modified
            last_accessed: The last time the data was accessed
            
        Returns:
            True if the data has expired under this rule, False otherwise
        """
        now = datetime.utcnow()
        
        if self.policy_type == RetentionPolicy.INDEFINITE:
            return False
        
        elif self.policy_type == RetentionPolicy.TIME_BASED:
            if not self.retention_period_days:
                return False
            
            expiration_date = last_modified + timedelta(days=self.retention_period_days)
            return now >= expiration_date
        
        elif self.policy_type == RetentionPolicy.ACCESS_BASED:
            if not self.max_inactive_days or not last_accessed:
                return False
            
            inactivity_limit = timedelta(days=self.max_inactive_days)
            inactive_time = now - last_accessed
            return inactive_time >= inactivity_limit
        
        elif self.policy_type == RetentionPolicy.HYBRID:
            # For hybrid policy, check both time and access based conditions
            time_expired = False
            access_expired = False
            
            if self.retention_period_days:
                expiration_date = last_modified + timedelta(days=self.retention_period_days)
                time_expired = now >= expiration_date
            
            if self.max_inactive_days and last_accessed:
                inactivity_limit = timedelta(days=self.max_inactive_days)
                inactive_time = now - last_accessed
                access_expired = inactive_time >= inactivity_limit
            
            # For hybrid, data has expired if either condition is met
            return time_expired or access_expired
        
        elif self.policy_type == RetentionPolicy.CUSTOM:
            # Custom policies are handled by the policy manager
            return False
        
        return False


@dataclass
class ClassificationRule:
    """Rule for data classification."""
    id: str
    name: str
    classification: DataClassification
    description: Optional[str] = None
    # Pattern matchers for automatic classification
    content_patterns: List[str] = field(default_factory=list)
    metadata_patterns: Dict[str, str] = field(default_factory=dict)
    path_patterns: List[str] = field(default_factory=list)
    # Compliance regulations this classification relates to
    compliance_regulations: List[ComplianceRegulation] = field(default_factory=list)
    # Whether this rule is enabled
    enabled: bool = True
    # Priority of this rule (higher number means higher priority)
    priority: int = 0
    # Creation and update timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    # Tags for the rule
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def matches(self, content: Optional[bytes] = None, metadata: Optional[Dict[str, Any]] = None, 
               path: Optional[str] = None) -> bool:
        """
        Check if the given content, metadata, and path match this rule.
        
        Args:
            content: The content to check
            metadata: The metadata to check
            path: The path to check
            
        Returns:
            True if the rule matches, False otherwise
        """
        if not self.enabled:
            return False
        
        # Check content patterns
        if content and self.content_patterns:
            content_str = content.decode('utf-8', errors='ignore')
            for pattern in self.content_patterns:
                if re.search(pattern, content_str):
                    return True
        
        # Check metadata patterns
        if metadata and self.metadata_patterns:
            for key, pattern in self.metadata_patterns.items():
                if key in metadata:
                    metadata_value = str(metadata[key])
                    if re.search(pattern, metadata_value):
                        return True
        
        # Check path patterns
        if path and self.path_patterns:
            for pattern in self.path_patterns:
                if re.search(pattern, path):
                    return True
        
        return False


@dataclass
class ArchiveRule:
    """Rule for data archiving."""
    id: str
    name: str
    strategy: ArchiveStrategy
    description: Optional[str] = None
    # Conditions for archiving
    min_age_days: Optional[int] = None
    max_accesses: Optional[int] = None
    min_inactive_days: Optional[int] = None
    # Target storage backend for archived data
    target_backend: Optional[str] = None
    # Specific settings for COMPRESSION strategy
    compression_format: Optional[str] = None
    compression_level: Optional[int] = None
    # Whether this rule is enabled
    enabled: bool = True
    # Priority of this rule (higher number means higher priority)
    priority: int = 0
    # Creation and update timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    # Tags for the rule
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def should_archive(self, creation_date: datetime, last_accessed: Optional[datetime] = None, 
                      access_count: int = 0) -> bool:
        """
        Check if data with the given properties should be archived.
        
        Args:
            creation_date: When the data was created
            last_accessed: When the data was last accessed
            access_count: How many times the data has been accessed
            
        Returns:
            True if the data should be archived, False otherwise
        """
        if not self.enabled or self.strategy == ArchiveStrategy.NONE:
            return False
        
        now = datetime.utcnow()
        
        # Check age condition
        if self.min_age_days is not None:
            age_days = (now - creation_date).days
            if age_days < self.min_age_days:
                return False
        
        # Check access count condition
        if self.max_accesses is not None:
            if access_count <= self.max_accesses:
                return False
        
        # Check inactivity condition
        if self.min_inactive_days is not None and last_accessed is not None:
            inactive_days = (now - last_accessed).days
            if inactive_days < self.min_inactive_days:
                return False
        
        # All conditions passed, should archive
        return True


@dataclass
class ComplianceRule:
    """Rule for compliance enforcement."""
    id: str
    name: str
    regulation: ComplianceRegulation
    description: Optional[str] = None
    # Data subject to this rule
    applies_to_classifications: List[DataClassification] = field(default_factory=list)
    # Data retention requirements
    max_retention_days: Optional[int] = None
    min_retention_days: Optional[int] = None
    # Whether data can be moved outside specific regions
    geographical_restrictions: List[str] = field(default_factory=list)
    # Requirements for data deletion
    requires_secure_deletion: bool = False
    requires_deletion_certificate: bool = False
    # Whether data access must be logged
    requires_access_logging: bool = False
    # Whether this rule is enabled
    enabled: bool = True
    # Priority of this rule (higher number means higher priority)
    priority: int = 0
    # Creation and update timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    # Tags for the rule
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def is_compliant(self, classification: DataClassification, 
                    creation_date: datetime, 
                    current_region: Optional[str] = None,
                    has_access_logging: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Check if data with the given properties is compliant with this rule.
        
        Args:
            classification: The data classification
            creation_date: When the data was created
            current_region: The current region where the data is stored
            has_access_logging: Whether access logging is enabled for this data
            
        Returns:
            A tuple of (is_compliant, reason) where reason is None if compliant
        """
        if not self.enabled:
            return True, None
        
        # Check if the rule applies to this classification
        if self.applies_to_classifications and classification not in self.applies_to_classifications:
            return True, None
        
        now = datetime.utcnow()
        
        # Check retention limits
        age_days = (now - creation_date).days
        
        if self.min_retention_days is not None and age_days < self.min_retention_days:
            # Data hasn't been kept long enough
            return False, f"Data must be retained for at least {self.min_retention_days} days (current age: {age_days} days)"
        
        if self.max_retention_days is not None and age_days > self.max_retention_days:
            # Data has been kept too long
            return False, f"Data must not be retained for more than {self.max_retention_days} days (current age: {age_days} days)"
        
        # Check geographical restrictions
        if self.geographical_restrictions and current_region:
            if current_region not in self.geographical_restrictions:
                return False, f"Data must be stored in one of these regions: {', '.join(self.geographical_restrictions)}"
        
        # Check access logging requirement
        if self.requires_access_logging and not has_access_logging:
            return False, "Access logging is required for this data"
        
        # All checks passed
        return True, None


@dataclass
class CostOptimizationRule:
    """Rule for cost optimization."""
    id: str
    name: str
    strategy: CostOptimizationStrategy
    description: Optional[str] = None
    # Conditions for applying this rule
    min_size_bytes: Optional[int] = None
    min_age_days: Optional[int] = None
    max_access_frequency: Optional[float] = None  # Average accesses per day
    # Target storage backend
    target_backend: Optional[str] = None
    # Whether this rule is enabled
    enabled: bool = True
    # Priority of this rule (higher number means higher priority)
    priority: int = 0
    # Creation and update timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    # Tags for the rule
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def should_optimize(self, size_bytes: int, creation_date: datetime, 
                       access_count: int = 0, days_tracked: int = 1) -> bool:
        """
        Check if data with the given properties should be optimized.
        
        Args:
            size_bytes: Size of the data in bytes
            creation_date: When the data was created
            access_count: How many times the data has been accessed
            days_tracked: Number of days the access count has been tracked
            
        Returns:
            True if the data should be optimized, False otherwise
        """
        if not self.enabled or self.strategy == CostOptimizationStrategy.NONE:
            return False
        
        now = datetime.utcnow()
        
        # Check size condition
        if self.min_size_bytes is not None and size_bytes < self.min_size_bytes:
            return False
        
        # Check age condition
        if self.min_age_days is not None:
            age_days = (now - creation_date).days
            if age_days < self.min_age_days:
                return False
        
        # Check access frequency condition
        if self.max_access_frequency is not None:
            # Calculate average accesses per day
            if days_tracked <= 0:
                days_tracked = 1
            access_frequency = access_count / days_tracked
            if access_frequency > self.max_access_frequency:
                return False
        
        # All conditions passed, should optimize
        return True


@dataclass
class AccessLogEntry:
    """Entry in the access log."""
    id: str
    content_id: str
    timestamp: str
    user_id: Optional[str] = None
    operation: str = "read"
    success: bool = True
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class DataLifecycleMetadata:
    """Metadata for data lifecycle management."""
    content_id: str
    current_state: DataLifecycleState = DataLifecycleState.ACTIVE
    classification: Optional[DataClassification] = None
    create_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_accessed: Optional[str] = None
    access_count: int = 0
    size_bytes: int = 0
    original_backend: Optional[str] = None
    current_backend: Optional[str] = None
    retention_rule_id: Optional[str] = None
    archive_rule_id: Optional[str] = None
    compliance_rule_ids: List[str] = field(default_factory=list)
    cost_optimization_rule_id: Optional[str] = None
    expiration_date: Optional[str] = None
    legal_hold: bool = False
    legal_hold_reason: Optional[str] = None
    deletion_certificate: Optional[str] = None
    custom_attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataLifecycleMetadata':
        """Create from dictionary."""
        return cls(**data)


class LifecycleManager:
    """
    Manager for data lifecycle.
    
    This class is responsible for:
    - Managing retention rules
    - Managing classification rules
    - Managing archive rules
    - Managing compliance rules
    - Managing cost optimization rules
    - Tracking data lifecycle metadata
    - Enforcing rules on data
    - Generating reports and analytics
    """
    
    def __init__(self, storage_manager=None, metadata_db_path: Optional[str] = None):
        """
        Initialize the lifecycle manager.
        
        Args:
            storage_manager: Optional storage manager to use for backend operations
            metadata_db_path: Path to the metadata database file
        """
        self.storage_manager = storage_manager
        
        # Rule collections
        self.retention_rules: Dict[str, RetentionRule] = {}
        self.classification_rules: Dict[str, ClassificationRule] = {}
        self.archive_rules: Dict[str, ArchiveRule] = {}
        self.compliance_rules: Dict[str, ComplianceRule] = {}
        self.cost_optimization_rules: Dict[str, CostOptimizationRule] = {}
        
        # Metadata storage
        self.metadata_db_path = metadata_db_path or "lifecycle_metadata.json"
        self.metadata: Dict[str, DataLifecycleMetadata] = {}
        self.access_logs: Dict[str, List[AccessLogEntry]] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load metadata from database if it exists
        self._load_metadata()
        
        # Background task references
        self._background_tasks = []
        
        logger.info("Initialized lifecycle manager")
    
    def start(self):
        """Start the lifecycle manager and its background tasks."""
        # Start background tasks in a separate thread
        threading.Thread(target=self._start_background_tasks, daemon=True).start()
        logger.info("Started lifecycle manager background tasks")
    
    def stop(self):
        """Stop the lifecycle manager and its background tasks."""
        # Stop background tasks
        self._stop_background_tasks()
        
        # Save metadata
        self._save_metadata()
        
        logger.info("Stopped lifecycle manager")
    
    def _start_background_tasks(self):
        """Start background tasks."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start background tasks
        tasks = [
            self._retention_enforcement_task(),
            self._archiving_task(),
            self._cost_optimization_task(),
            self._compliance_check_task(),
            self._metadata_save_task()
        ]
        
        self._background_tasks = [loop.create_task(task) for task in tasks]
        
        try:
            loop.run_forever()
        except Exception as e:
            logger.error(f"Error in background tasks: {e}")
        finally:
            loop.close()
    
    def _stop_background_tasks(self):
        """Stop background tasks."""
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        self._background_tasks = []
    
    def _load_metadata(self):
        """Load metadata from database."""
        try:
            if os.path.exists(self.metadata_db_path):
                with open(self.metadata_db_path, 'r') as f:
                    data = json.load(f)
                    
                    # Load metadata
                    metadata_dict = data.get("metadata", {})
                    self.metadata = {
                        content_id: DataLifecycleMetadata.from_dict(metadata_data)
                        for content_id, metadata_data in metadata_dict.items()
                    }
                    
                    # Load access logs
                    access_logs_dict = data.get("access_logs", {})
                    self.access_logs = {
                        content_id: [AccessLogEntry(**entry_data) for entry_data in entries]
                        for content_id, entries in access_logs_dict.items()
                    }
                    
                    # Load rules
                    retention_rules_dict = data.get("retention_rules", {})
                    self.retention_rules = {
                        rule_id: RetentionRule(**rule_data)
                        for rule_id, rule_data in retention_rules_dict.items()
                    }
                    
                    classification_rules_dict = data.get("classification_rules", {})
                    self.classification_rules = {
                        rule_id: ClassificationRule(**rule_data)
                        for rule_id, rule_data in classification_rules_dict.items()
                    }
                    
                    archive_rules_dict = data.get("archive_rules", {})
                    self.archive_rules = {
                        rule_id: ArchiveRule(**rule_data)
                        for rule_id, rule_data in archive_rules_dict.items()
                    }
                    
                    compliance_rules_dict = data.get("compliance_rules", {})
                    self.compliance_rules = {
                        rule_id: ComplianceRule(**rule_data)
                        for rule_id, rule_data in compliance_rules_dict.items()
                    }
                    
                    cost_optimization_rules_dict = data.get("cost_optimization_rules", {})
                    self.cost_optimization_rules = {
                        rule_id: CostOptimizationRule(**rule_data)
                        for rule_id, rule_data in cost_optimization_rules_dict.items()
                    }
                
                logger.info(f"Loaded metadata from {self.metadata_db_path}")
                logger.info(f"Loaded {len(self.metadata)} content entries and {len(self.access_logs)} access logs")
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
    
    def _save_metadata(self):
        """Save metadata to database."""
        try:
            with self._lock:
                data = {
                    "metadata": {
                        content_id: metadata.to_dict()
                        for content_id, metadata in self.metadata.items()
                    },
                    "access_logs": {
                        content_id: [entry.to_dict() for entry in entries]
                        for content_id, entries in self.access_logs.items()
                    },
                    "retention_rules": {
                        rule_id: rule.to_dict()
                        for rule_id, rule in self.retention_rules.items()
                    },
                    "classification_rules": {
                        rule_id: rule.to_dict()
                        for rule_id, rule in self.classification_rules.items()
                    },
                    "archive_rules": {
                        rule_id: rule.to_dict()
                        for rule_id, rule in self.archive_rules.items()
                    },
                    "compliance_rules": {
                        rule_id: rule.to_dict()
                        for rule_id, rule in self.compliance_rules.items()
                    },
                    "cost_optimization_rules": {
                        rule_id: rule.to_dict()
                        for rule_id, rule in self.cost_optimization_rules.items()
                    }
                }
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(os.path.abspath(self.metadata_db_path)), exist_ok=True)
                
                with open(self.metadata_db_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.info(f"Saved metadata to {self.metadata_db_path}")
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
    async def _metadata_save_task(self):
        """Background task to periodically save metadata."""
        while True:
            try:
                self._save_metadata()
            except Exception as e:
                logger.error(f"Error in metadata save task: {e}")
            
            # Wait for next save
            await asyncio.sleep(300)  # Save every 5 minutes
    
    async def _retention_enforcement_task(self):
        """Background task to enforce retention policies."""
        while True:
            try:
                await self._enforce_retention_policies()
            except Exception as e:
                logger.error(f"Error in retention enforcement task: {e}")
            
            # Wait for next enforcement
            await asyncio.sleep(3600)  # Run every hour
    
    async def _archiving_task(self):
        """Background task to archive data."""
        while True:
            try:
                await self._apply_archiving_rules()
            except Exception as e:
                logger.error(f"Error in archiving task: {e}")
            
            # Wait for next archiving run
            await asyncio.sleep(7200)  # Run every 2 hours
    
    async def _cost_optimization_task(self):
        """Background task to optimize costs."""
        while True:
            try:
                await self._apply_cost_optimization_rules()
            except Exception as e:
                logger.error(f"Error in cost optimization task: {e}")
            
            # Wait for next optimization run
            await asyncio.sleep(86400)  # Run once per day
    
    async def _compliance_check_task(self):
        """Background task to check compliance."""
        while True:
            try:
                await self._check_compliance()
            except Exception as e:
                logger.error(f"Error in compliance check task: {e}")
            
            # Wait for next compliance check
            await asyncio.sleep(43200)  # Run twice per day
    
    async def _enforce_retention_policies(self):
        """Enforce retention policies on all content."""
        logger.info("Starting retention policy enforcement")
        
        with self._lock:
            # Get all enabled retention rules
            enabled_rules = [rule for rule in self.retention_rules.values() if rule.enabled]
            
            # Process each content item
            for content_id, metadata in list(self.metadata.items()):
                # Skip content on legal hold
                if metadata.legal_hold:
                    continue
                
                # Find applicable retention rule
                rule = None
                
                if metadata.retention_rule_id:
                    # Use assigned rule if it exists and is enabled
                    rule_id = metadata.retention_rule_id
                    if rule_id in self.retention_rules:
                        rule = self.retention_rules[rule_id]
                        if not rule.enabled:
                            rule = None
                
                # If no rule assigned or rule not found, find best match
                if not rule:
                    for candidate_rule in sorted(enabled_rules, key=lambda r: r.name):
                        # Skip rules that don't apply
                        if not candidate_rule.enabled:
                            continue
                        
                        # For now, assign first enabled rule
                        # In a real implementation, you would use more sophisticated matching
                        rule = candidate_rule
                        metadata.retention_rule_id = rule.id
                        break
                
                # Skip if no rule found
                if not rule:
                    logger.debug(f"No retention rule found for content {content_id}")
                    continue
                
                # Check if content has expired
                last_modified = datetime.fromisoformat(metadata.last_modified)
                last_accessed = datetime.fromisoformat(metadata.last_accessed) if metadata.last_accessed else None
                
                if rule.is_expired(last_modified, last_accessed):
                    logger.info(f"Content {content_id} has expired under rule {rule.id}")
                    
                    # Take action based on rule
                    if rule.expiration_action == RetentionAction.DELETE:
                        logger.info(f"Deleting content {content_id}")
                        metadata.current_state = DataLifecycleState.PENDING_DELETION
                        # In a real implementation, you would delete the content from storage
                        
                    elif rule.expiration_action == RetentionAction.ARCHIVE:
                        logger.info(f"Archiving content {content_id}")
                        metadata.current_state = DataLifecycleState.ARCHIVED
                        # In a real implementation, you would move the content to archive storage
                        
                    elif rule.expiration_action == RetentionAction.ANONYMIZE:
                        logger.info(f"Anonymizing content {content_id}")
                        metadata.current_state = DataLifecycleState.ANONYMIZED
                        # In a real implementation, you would anonymize the content
                        
                    elif rule.expiration_action == RetentionAction.NOTIFY:
                        logger.info(f"Notifying about expired content {content_id}")
                        # In a real implementation, you would send a notification
                        
                    elif rule.expiration_action == RetentionAction.CUSTOM:
                        logger.info(f"Applying custom action to content {content_id}")
                        # In a real implementation, you would apply a custom action
                    
                    # Update metadata
                    metadata.last_modified = datetime.utcnow().isoformat()
        
        logger.info("Completed retention policy enforcement")
    
    async def _apply_archiving_rules(self):
        """Apply archiving rules to eligible content."""
        logger.info("Starting archiving task")
        
        with self._lock:
            # Get all enabled archive rules
            enabled_rules = [rule for rule in self.archive_rules.values() if rule.enabled]
            
            # Sort by priority (highest first)
            enabled_rules.sort(key=lambda r: r.priority, reverse=True)
            
            # Process each content item
            for content_id, metadata in list(self.metadata.items()):
                # Skip content that's not in ACTIVE state
                if metadata.current_state != DataLifecycleState.ACTIVE:
                    continue
                
                # Skip content on legal hold
                if metadata.legal_hold:
                    continue
                
                # Find applicable archive rule
                rule = None
                
                if metadata.archive_rule_id:
                    # Use assigned rule if it exists and is enabled
                    rule_id = metadata.archive_rule_id
                    if rule_id in self.archive_rules:
                        rule = self.archive_rules[rule_id]
                        if not rule.enabled:
                            rule = None
                
                # If no rule assigned or rule not found, find best match
                if not rule:
                    for candidate_rule in enabled_rules:
                        # For now, assign first enabled rule
                        # In a real implementation, you would use more sophisticated matching
                        rule = candidate_rule
                        metadata.archive_rule_id = rule.id
                        break
                
                # Skip if no rule found
                if not rule:
                    logger.debug(f"No archive rule found for content {content_id}")
                    continue
                
                # Check if content should be archived
                creation_date = datetime.fromisoformat(metadata.create_date)
                last_accessed = datetime.fromisoformat(metadata.last_accessed) if metadata.last_accessed else None
                
                if rule.should_archive(creation_date, last_accessed, metadata.access_count):
                    logger.info(f"Content {content_id} should be archived under rule {rule.id}")
                    
                    # Take action based on archive strategy
                    if rule.strategy == ArchiveStrategy.COLD_STORAGE:
                        logger.info(f"Moving content {content_id} to cold storage")
                        metadata.current_state = DataLifecycleState.COLD_STORAGE
                        
                        # In a real implementation, you would move the content to cold storage
                        if self.storage_manager and rule.target_backend:
                            # Example of how you might use the storage manager
                            # This is just a placeholder and would need to be implemented
                            # based on your storage manager's API
                            try:
                                # Get the content from current backend
                                # content = await self.storage_manager.get_content(content_id)
                                
                                # Upload to target backend
                                # await self.storage_manager.upload_to_backend(
                                #    rule.target_backend, content_id, content)
                                
                                # Update metadata
                                metadata.current_backend = rule.target_backend
                            except Exception as e:
                                logger.error(f"Error moving content {content_id} to cold storage: {e}")
                    
                    elif rule.strategy == ArchiveStrategy.COMPRESSION:
                        logger.info(f"Compressing content {content_id}")
                        
                        # In a real implementation, you would compress the content
                        # Example:
                        # if self.storage_manager:
                        #    try:
                        #        content = await self.storage_manager.get_content(content_id)
                        #        compressed_content = self._compress_content(
                        #            content, rule.compression_format, rule.compression_level)
                        #        await self.storage_manager.update_content(content_id, compressed_content)
                        #    except Exception as e:
                        #        logger.error(f"Error compressing content {content_id}: {e}")
                    
                    elif rule.strategy == ArchiveStrategy.TIERED:
                        logger.info(f"Moving content {content_id} to tiered storage")
                        
                        # In a real implementation, you would move the content to tiered storage
                        # This would be similar to the cold storage implementation
                    
                    elif rule.strategy == ArchiveStrategy.CUSTOM:
                        logger.info(f"Applying custom archiving to content {content_id}")
                        
                        # In a real implementation, you would apply a custom archiving strategy
                    
                    # Update metadata
                    metadata.current_state = DataLifecycleState.ARCHIVED
                    metadata.last_modified = datetime.utcnow().isoformat()
        
        logger.info("Completed archiving task")
    
    async def _apply_cost_optimization_rules(self):
        """Apply cost optimization rules to eligible content."""
        logger.info("Starting cost optimization task")
        
        with self._lock:
            # Get all enabled cost optimization rules
            enabled_rules = [rule for rule in self.cost_optimization_rules.values() if rule.enabled]
            
            # Sort by priority (highest first)
            enabled_rules.sort(key=lambda r: r.priority, reverse=True)
            
            # Process each content item
            for content_id, metadata in list(self.metadata.items()):
                # Skip content that's not in ACTIVE or ARCHIVED state
                if metadata.current_state not in [DataLifecycleState.ACTIVE, DataLifecycleState.ARCHIVED]:
                    continue
                
                # Skip content on legal hold
                if metadata.legal_hold:
                    continue
                
                # Find applicable cost optimization rule
                rule = None
                
                if metadata.cost_optimization_rule_id:
                    # Use assigned rule if it exists and is enabled
                    rule_id = metadata.cost_optimization_rule_id
                    if rule_id in self.cost_optimization_rules:
                        rule = self.cost_optimization_rules[rule_id]
                        if not rule.enabled:
                            rule = None
                
                # If no rule assigned or rule not found, find best match
                if not rule:
                    for candidate_rule in enabled_rules:
                        # For now, assign first enabled rule
                        rule = candidate_rule
                        metadata.cost_optimization_rule_id = rule.id
                        break
                
                # Skip if no rule found
                if not rule:
                    logger.debug(f"No cost optimization rule found for content {content_id}")
                    continue
                
                # Check if content should be optimized
                creation_date = datetime.fromisoformat(metadata.create_date)
                
                # Calculate days tracked
                days_tracked = 1
                if metadata.last_accessed:
                    last_accessed = datetime.fromisoformat(metadata.last_accessed)
                    days_tracked = max(1, (datetime.utcnow() - creation_date).days)
                
                if rule.should_optimize(metadata.size_bytes, creation_date, 
                                      metadata.access_count, days_tracked):
                    logger.info(f"Content {content_id} should be optimized under rule {rule.id}")
                    
                    # Take action based on optimization strategy
                    if rule.strategy == CostOptimizationStrategy.STORAGE_TIERING:
                        logger.info(f"Applying storage tiering to content {content_id}")
                        
                        # In a real implementation, you would move the content to appropriate tier
                        if self.storage_manager and rule.target_backend:
                            try:
                                # Similar to archiving, you would move content to target backend
                                pass
                            except Exception as e:
                                logger.error(f"Error applying storage tiering to {content_id}: {e}")
                    
                    elif rule.strategy == CostOptimizationStrategy.DEDUPLICATION:
                        logger.info(f"Applying deduplication to content {content_id}")
                        
                        # In a real implementation, you would check for duplicates and deduplicate
                    
                    elif rule.strategy == CostOptimizationStrategy.COMPRESSION:
                        logger.info(f"Applying compression to content {content_id}")
                        
                        # In a real implementation, you would compress the content
                    
                    elif rule.strategy == CostOptimizationStrategy.LIFECYCLE_RULES:
                        logger.info(f"Applying lifecycle rules to content {content_id}")
                        
                        # In a real implementation, you would apply lifecycle rules
                    
                    elif rule.strategy == CostOptimizationStrategy.CUSTOM:
                        logger.info(f"Applying custom cost optimization to content {content_id}")
                        
                        # In a real implementation, you would apply a custom optimization strategy
                    
                    # Update metadata
                    metadata.last_modified = datetime.utcnow().isoformat()
        
        logger.info("Completed cost optimization task")
    
    async def _check_compliance(self):
        """Check compliance of all content with applicable rules."""
        logger.info("Starting compliance check")
        
        with self._lock:
            # Get all enabled compliance rules
            enabled_rules = [rule for rule in self.compliance_rules.values() if rule.enabled]
            
            # Process each content item
            for content_id, metadata in list(self.metadata.items()):
                # Skip content that's already deleted
                if metadata.current_state == DataLifecycleState.DELETED:
                    continue
                
                # Skip compliance check if no classification
                if not metadata.classification:
                    continue
                
                # Check if content has access logs
                has_access_logs = content_id in self.access_logs and len(self.access_logs[content_id]) > 0
                
                # For each rule, check compliance
                for rule in enabled_rules:
                    # Check if rule applies to this content
                    if rule.applies_to_classifications and metadata.classification not in rule.applies_to_classifications:
                        continue
                    
                    # Check compliance
                    creation_date = datetime.fromisoformat(metadata.create_date)
                    is_compliant, reason = rule.is_compliant(
                        metadata.classification,
                        creation_date,
                        metadata.current_backend,
                        has_access_logs
                    )
                    
                    if not is_compliant:
                        logger.warning(f"Content {content_id} is not compliant with rule {rule.id}: {reason}")
                        
                        # In a real implementation, you would take action based on compliance failure
                        # For example, notifying administrators, moving content to compliant storage, etc.
                        
                        # Just for this example, we'll add the rule ID to the content's compliance rules
                        if rule.id not in metadata.compliance_rule_ids:
                            metadata.compliance_rule_ids.append(rule.id)
                            metadata.last_modified = datetime.utcnow().isoformat()
        
        logger.info("Completed compliance check")
    
    # API methods for rule management
    
    def create_retention_rule(self, name: str, policy_type: RetentionPolicy, **kwargs) -> str:
        """
        Create a new retention rule.
        
        Args:
            name: Name of the rule
            policy_type: Type of retention policy
            **kwargs: Additional parameters for the rule
            
        Returns:
            ID of the created rule
        """
        with self._lock:
            rule_id = str(uuid.uuid4())
            rule = RetentionRule(id=rule_id, name=name, policy_type=policy_type, **kwargs)
            self.retention_rules[rule_id] = rule
            self._save_metadata()
            logger.info(f"Created retention rule {rule_id}: {name}")
            return rule_id
    
    def get_retention_rule(self, rule_id: str) -> Optional[RetentionRule]:
        """
        Get a retention rule by ID.
        
        Args:
            rule_id: ID of the rule to get
            
        Returns:
            The rule or None if not found
        """
        with self._lock:
            return self.retention_rules.get(rule_id)
    
    def update_retention_rule(self, rule_id: str, **kwargs) -> bool:
        """
        Update a retention rule.
        
        Args:
            rule_id: ID of the rule to update
            **kwargs: Parameters to update
            
        Returns:
            True if rule was updated, False if not found
        """
        with self._lock:
            rule = self.retention_rules.get(rule_id)
            if not rule:
                return False
            
            # Update rule parameters
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            
            # Update timestamp
            rule.updated_at = datetime.utcnow().isoformat()
            
            self._save_metadata()
            logger.info(f"Updated retention rule {rule_id}")
            return True
    
    def delete_retention_rule(self, rule_id: str) -> bool:
        """
        Delete a retention rule.
        
        Args:
            rule_id: ID of the rule to delete
            
        Returns:
            True if rule was deleted, False if not found
        """
        with self._lock:
            if rule_id not in self.retention_rules:
                return False
            
            # Remove rule
            del self.retention_rules[rule_id]
            
            # Remove references to this rule in content metadata
            for metadata in self.metadata.values():
                if metadata.retention_rule_id == rule_id:
                    metadata.retention_rule_id = None
            
            self._save_metadata()
            logger.info(f"Deleted retention rule {rule_id}")
            return True
    
    def list_retention_rules(self, enabled_only: bool = False) -> List[RetentionRule]:
        """
        List all retention rules.
        
        Args:
            enabled_only: Whether to only include enabled rules
            
        Returns:
            List of retention rules
        """
        with self._lock:
            if enabled_only:
                return [rule for rule in self.retention_rules.values() if rule.enabled]
            else:
                return list(self.retention_rules.values())
    
    # Similar methods for other rule types would be defined here
    # (classification_rules, archive_rules, compliance_rules, cost_optimization_rules)
    # ...

    # Content lifecycle management methods
    
    def register_content(self, content_id: str, size_bytes: int, 
                        backend: str, metadata: Optional[Dict[str, Any]] = None,
                        content_data: Optional[bytes] = None,
                        path: Optional[str] = None) -> DataLifecycleMetadata:
        """
        Register content for lifecycle management.
        
        Args:
            content_id: ID of the content
            size_bytes: Size of the content in bytes
            backend: Backend where the content is stored
            metadata: Optional metadata about the content
            content_data: Optional content data for classification
            path: Optional path of the content
            
        Returns:
            Lifecycle metadata for the content
        """
        with self._lock:
            # Create lifecycle metadata
            lifecycle_metadata = DataLifecycleMetadata(
                content_id=content_id,
                size_bytes=size_bytes,
                original_backend=backend,
                current_backend=backend,
                create_date=datetime.utcnow().isoformat(),
                last_modified=datetime.utcnow().isoformat(),
                current_state=DataLifecycleState.ACTIVE,
                custom_attributes=metadata or {}
            )
            
            # Try to classify the content
            if content_data or metadata or path:
                classification = self._classify_content(content_data, metadata, path)
                if classification:
                    lifecycle_metadata.classification = classification
            
            # Store metadata
            self.metadata[content_id] = lifecycle_metadata
            
            # Initialize access logs
            if content_id not in self.access_logs:
                self.access_logs[content_id] = []
            
            self._save_metadata()
            logger.info(f"Registered content {content_id} for lifecycle management")
            
            return lifecycle_metadata
    
    def record_access(self, content_id: str, user_id: Optional[str] = None,
                     operation: str = "read", success: bool = True,
                     client_ip: Optional[str] = None, 
                     user_agent: Optional[str] = None,
                     request_id: Optional[str] = None,
                     access_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Record an access to content.
        
        Args:
            content_id: ID of the content
            user_id: ID of the user who accessed the content
            operation: Type of operation
            success: Whether the operation was successful
            client_ip: IP address of the client
            user_agent: User agent of the client
            request_id: ID of the request
            access_metadata: Additional metadata about the access
            
        Returns:
            True if access was recorded, False if content not found
        """
        with self._lock:
            # Check if content exists
            if content_id not in self.metadata:
                logger.warning(f"Cannot record access for unknown content {content_id}")
                return False
            
            # Get content metadata
            metadata = self.metadata[content_id]
            
            # Create access log entry
            entry = AccessLogEntry(
                id=str(uuid.uuid4()),
                content_id=content_id,
                timestamp=datetime.utcnow().isoformat(),
                user_id=user_id,
                operation=operation,
                success=success,
                client_ip=client_ip,
                user_agent=user_agent,
                request_id=request_id,
                metadata=access_metadata or {}
            )
            
            # Add to access logs
            if content_id not in self.access_logs:
                self.access_logs[content_id] = []
            
            self.access_logs[content_id].append(entry)
            
            # Update content metadata
            metadata.access_count += 1
            metadata.last_accessed = entry.timestamp
            
            self._save_metadata()
            logger.debug(f"Recorded {operation} access to content {content_id}")
            
            return True
    
    def place_legal_hold(self, content_id: str, reason: str) -> bool:
        """
        Place a legal hold on content.
        
        Args:
            content_id: ID of the content to place on hold
            reason: Reason for the legal hold
            
        Returns:
            True if hold was placed, False if content not found
        """
        with self._lock:
            # Check if content exists
            if content_id not in self.metadata:
                logger.warning(f"Cannot place legal hold on unknown content {content_id}")
                return False
            
            # Get content metadata
            metadata = self.metadata[content_id]
            
            # Place hold
            metadata.legal_hold = True
            metadata.legal_hold_reason = reason
            metadata.last_modified = datetime.utcnow().isoformat()
            
            self._save_metadata()
            logger.info(f"Placed legal hold on content {content_id}: {reason}")
            
            return True
    
    def release_legal_hold(self, content_id: str) -> bool:
        """
        Release a legal hold on content.
        
        Args:
            content_id: ID of the content to release
            
        Returns:
            True if hold was released, False if content not found or not on hold
        """
        with self._lock:
            # Check if content exists
            if content_id not in self.metadata:
                logger.warning(f"Cannot release legal hold on unknown content {content_id}")
                return False
            
            # Get content metadata
            metadata = self.metadata[content_id]
            
            # Check if on hold
            if not metadata.legal_hold:
                logger.warning(f"Content {content_id} is not on legal hold")
                return False
            
            # Release hold
            metadata.legal_hold = False
            metadata.legal_hold_reason = None
            metadata.last_modified = datetime.utcnow().isoformat()
            
            self._save_metadata()
            logger.info(f"Released legal hold on content {content_id}")
            
            return True
    
    def delete_content(self, content_id: str, secure: bool = False) -> bool:
        """
        Delete content.
        
        Args:
            content_id: ID of the content to delete
            secure: Whether to perform secure deletion
            
        Returns:
            True if content was deleted, False if not found or on legal hold
        """
        with self._lock:
            # Check if content exists
            if content_id not in self.metadata:
                logger.warning(f"Cannot delete unknown content {content_id}")
                return False
            
            # Get content metadata
            metadata = self.metadata[content_id]
            
            # Check if on legal hold
            if metadata.legal_hold:
                logger.warning(f"Cannot delete content {content_id} on legal hold")
                return False
            
            # Delete content
            if secure:
                logger.info(f"Performing secure deletion of content {content_id}")
                # In a real implementation, you would perform secure deletion
                # This might involve multiple overwrites of the data
                
                # Generate deletion certificate
                deletion_certificate = self._generate_deletion_certificate(content_id)
                metadata.deletion_certificate = deletion_certificate
            else:
                logger.info(f"Deleting content {content_id}")
                # In a real implementation, you would delete the content
            
            # Update metadata
            metadata.current_state = DataLifecycleState.DELETED
            metadata.last_modified = datetime.utcnow().isoformat()
            
            self._save_metadata()
            return True
    
    def _classify_content(self, content: Optional[bytes], 
                         metadata: Optional[Dict[str, Any]], 
                         path: Optional[str]) -> Optional[DataClassification]:
        """
        Classify content based on content, metadata, and path.
        
        Args:
            content: Content data
            metadata: Content metadata
            path: Content path
            
        Returns:
            Classification or None if not classified
        """
        # Get all enabled classification rules
        enabled_rules = [rule for rule in self.classification_rules.values() if rule.enabled]
        
        # Sort by priority (highest first)
        enabled_rules.sort(key=lambda r: r.priority, reverse=True)
        
        # Try to match a rule
        for rule in enabled_rules:
            if rule.matches(content, metadata, path):
                logger.info(f"Content classified as {rule.classification} by rule {rule.id}")
                return rule.classification
        
        # No matching rule
        return None
    
    def _generate_deletion_certificate(self, content_id: str) -> str:
        """
        Generate a deletion certificate for content.
        
        Args:
            content_id: ID of the content
            
        Returns:
            Deletion certificate as a string
        """
        metadata = self.metadata[content_id]
        
        # Create certificate data
        certificate_data = {
            "content_id": content_id,
            "deletion_time": datetime.utcnow().isoformat(),
            "classification": metadata.classification,
            "size_bytes": metadata.size_bytes,
            "create_date": metadata.create_date,
            "last_modified": metadata.last_modified,
            "original_backend": metadata.original_backend,
            "current_backend": metadata.current_backend
        }
        
        # Generate certificate ID using hash of data
        certificate_json = json.dumps(certificate_data, sort_keys=True)
        certificate_hash = hashlib.sha256(certificate_json.encode()).hexdigest()
        
        # Add ID to certificate
        certificate_data["certificate_id"] = certificate_hash
        
        # Return formatted certificate
        return json.dumps(certificate_data, indent=2)
