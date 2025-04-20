#!/usr/bin/env python3
"""
Data Lifecycle Management Example for MCP Server

This example demonstrates how to use the lifecycle management module to implement
policy-based data retention, automated archiving, data classification,
compliance enforcement, and cost optimization strategies.

Key features demonstrated:
1. Creating and managing retention policies
2. Data classification based on content and metadata
3. Automated archiving of infrequently accessed data
4. Compliance monitoring and enforcement
5. Cost optimization through tiered storage

Usage:
  python lifecycle_example.py [--storage-path STORAGE_PATH] [--metadata-path METADATA_PATH]
"""

import os
import json
import time
import uuid
import argparse
import logging
import tempfile
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("lifecycle-example")

# Import lifecycle management components
try:
    from ipfs_kit_py.mcp.enterprise.lifecycle import (
        LifecycleManager, RetentionRule, ClassificationRule, ArchiveRule,
        ComplianceRule, CostOptimizationRule, DataLifecycleMetadata,
        RetentionPolicy, DataClassification, ArchiveStrategy,
        ComplianceRegulation, CostOptimizationStrategy, RetentionAction,
        DataLifecycleState
    )
except ImportError:
    logger.error("Failed to import lifecycle management modules. Make sure ipfs_kit_py is installed")
    import sys
    sys.exit(1)


def demonstrate_rule_creation(lifecycle_manager: LifecycleManager):
    """Demonstrate creating various rules for lifecycle management."""
    logger.info("\n=== Rule Creation Demonstration ===\n")
    
    # 1. Create retention rules
    logger.info("Creating retention rules...")
    
    # Default indefinite retention rule (keep data forever)
    default_rule_id = lifecycle_manager.create_retention_rule(
        name="Default Retention",
        policy_type=RetentionPolicy.INDEFINITE,
        description="Default rule that keeps data indefinitely"
    )
    logger.info(f"Created default indefinite retention rule: {default_rule_id}")
    
    # Short-term retention rule (30 days)
    short_term_rule_id = lifecycle_manager.create_retention_rule(
        name="Short-term Retention",
        policy_type=RetentionPolicy.TIME_BASED,
        description="Short-term retention for temporary data",
        retention_period_days=30,
        expiration_action=RetentionAction.DELETE
    )
    logger.info(f"Created short-term retention rule: {short_term_rule_id}")
    
    # Medium-term retention rule (1 year)
    medium_term_rule_id = lifecycle_manager.create_retention_rule(
        name="Medium-term Retention",
        policy_type=RetentionPolicy.TIME_BASED,
        description="Medium-term retention for business data",
        retention_period_days=365,
        expiration_action=RetentionAction.ARCHIVE
    )
    logger.info(f"Created medium-term retention rule: {medium_term_rule_id}")
    
    # Long-term retention rule (7 years)
    long_term_rule_id = lifecycle_manager.create_retention_rule(
        name="Long-term Retention",
        policy_type=RetentionPolicy.TIME_BASED,
        description="Long-term retention for records",
        retention_period_days=365 * 7,
        expiration_action=RetentionAction.ARCHIVE
    )
    logger.info(f"Created long-term retention rule: {long_term_rule_id}")
    
    # Access-based retention rule (delete after 90 days of inactivity)
    access_rule_id = lifecycle_manager.create_retention_rule(
        name="Inactivity-based Retention",
        policy_type=RetentionPolicy.ACCESS_BASED,
        description="Delete data after 90 days of inactivity",
        max_inactive_days=90,
        expiration_action=RetentionAction.DELETE
    )
    logger.info(f"Created access-based retention rule: {access_rule_id}")
    
    # Hybrid retention rule (keep for at least 1 year, but delete after 180 days of inactivity)
    hybrid_rule_id = lifecycle_manager.create_retention_rule(
        name="Hybrid Retention",
        policy_type=RetentionPolicy.HYBRID,
        description="Keep for at least 1 year, but delete after 180 days of inactivity",
        retention_period_days=365,
        max_inactive_days=180,
        expiration_action=RetentionAction.DELETE
    )
    logger.info(f"Created hybrid retention rule: {hybrid_rule_id}")
    
    # 2. Create classification rules
    logger.info("\nCreating classification rules...")
    
    # Public data rule
    public_rule = ClassificationRule(
        id=str(uuid.uuid4()),
        name="Public Data",
        classification=DataClassification.PUBLIC,
        description="Data that can be shared publicly",
        # Match content with words like "public" or "open"
        content_patterns=["\\bpublic\\b", "\\bopen\\b", "\\bshare\\b"],
        # Match metadata with public flags
        metadata_patterns={"visibility": "public", "access_level": "public"},
        # High priority to ensure public data is correctly classified
        priority=100
    )
    lifecycle_manager.classification_rules[public_rule.id] = public_rule
    logger.info(f"Created public data classification rule: {public_rule.id}")
    
    # Internal data rule
    internal_rule = ClassificationRule(
        id=str(uuid.uuid4()),
        name="Internal Data",
        classification=DataClassification.INTERNAL,
        description="Data for internal use only",
        # Match content with words like "internal" or "staff"
        content_patterns=["\\binternal\\b", "\\bstaff\\b", "\\bemployee\\b"],
        # Match metadata with internal flags
        metadata_patterns={"visibility": "internal", "access_level": "internal"},
        # Medium priority
        priority=50
    )
    lifecycle_manager.classification_rules[internal_rule.id] = internal_rule
    logger.info(f"Created internal data classification rule: {internal_rule.id}")
    
    # Confidential data rule
    confidential_rule = ClassificationRule(
        id=str(uuid.uuid4()),
        name="Confidential Data",
        classification=DataClassification.CONFIDENTIAL,
        description="Confidential business data",
        # Match content with words like "confidential" or "proprietary"
        content_patterns=["\\bconfidential\\b", "\\bproprietary\\b", "\\bsensitive\\b"],
        # Match metadata with confidential flags
        metadata_patterns={"confidentiality": "high", "access_level": "restricted"},
        # Higher priority than internal
        priority=75
    )
    lifecycle_manager.classification_rules[confidential_rule.id] = confidential_rule
    logger.info(f"Created confidential data classification rule: {confidential_rule.id}")
    
    # PII data rule
    pii_rule = ClassificationRule(
        id=str(uuid.uuid4()),
        name="Personal Data",
        classification=DataClassification.PERSONAL,
        description="Personal identifiable information",
        # Match content that might contain PII
        content_patterns=[
            "\\bssn\\b", "\\bsocial security\\b", "\\bpassport\\b", 
            "\\bcredit card\\b", "\\bbirthday\\b", "\\baddress\\b"
        ],
        # Highest priority to ensure PII is properly classified
        priority=200,
        # Associated compliance regulations
        compliance_regulations=[ComplianceRegulation.GDPR, ComplianceRegulation.CCPA]
    )
    lifecycle_manager.classification_rules[pii_rule.id] = pii_rule
    logger.info(f"Created PII data classification rule: {pii_rule.id}")
    
    # 3. Create archive rules
    logger.info("\nCreating archive rules...")
    
    # General archiving rule (archive after 1 year)
    general_archive_rule = ArchiveRule(
        id=str(uuid.uuid4()),
        name="General Archiving",
        strategy=ArchiveStrategy.COLD_STORAGE,
        description="Archive data after 1 year",
        min_age_days=365,
        target_backend="archive-storage"
    )
    lifecycle_manager.archive_rules[general_archive_rule.id] = general_archive_rule
    logger.info(f"Created general archive rule: {general_archive_rule.id}")
    
    # Low-access archiving rule (archive after 10 accesses and 30 days)
    low_access_archive_rule = ArchiveRule(
        id=str(uuid.uuid4()),
        name="Low-access Archiving",
        strategy=ArchiveStrategy.COLD_STORAGE,
        description="Archive data with low access patterns",
        min_age_days=30,
        max_accesses=10,
        target_backend="archive-storage"
    )
    lifecycle_manager.archive_rules[low_access_archive_rule.id] = low_access_archive_rule
    logger.info(f"Created low-access archive rule: {low_access_archive_rule.id}")
    
    # Compression archive rule (compress data after 60 days)
    compression_archive_rule = ArchiveRule(
        id=str(uuid.uuid4()),
        name="Compression Archiving",
        strategy=ArchiveStrategy.COMPRESSION,
        description="Compress data after 60 days",
        min_age_days=60,
        compression_format="gzip",
        compression_level=9
    )
    lifecycle_manager.archive_rules[compression_archive_rule.id] = compression_archive_rule
    logger.info(f"Created compression archive rule: {compression_archive_rule.id}")
    
    # 4. Create compliance rules
    logger.info("\nCreating compliance rules...")
    
    # GDPR compliance rule
    gdpr_rule = ComplianceRule(
        id=str(uuid.uuid4()),
        name="GDPR Compliance",
        regulation=ComplianceRegulation.GDPR,
        description="General Data Protection Regulation compliance",
        # Applies to personal data classifications
        applies_to_classifications=[DataClassification.PERSONAL],
        # GDPR allows reasonable retention but requires eventual deletion
        max_retention_days=365 * 5,  # 5 years max
        # Geographical restrictions to EU
        geographical_restrictions=["eu-west-1", "eu-central-1", "eu-north-1"],
        # Security requirements
        requires_secure_deletion=True,
        requires_deletion_certificate=True,
        # Access tracking for right to access
        requires_access_logging=True,
        # High priority
        priority=100
    )
    lifecycle_manager.compliance_rules[gdpr_rule.id] = gdpr_rule
    logger.info(f"Created GDPR compliance rule: {gdpr_rule.id}")
    
    # HIPAA compliance rule
    hipaa_rule = ComplianceRule(
        id=str(uuid.uuid4()),
        name="HIPAA Compliance",
        regulation=ComplianceRegulation.HIPAA,
        description="Health Insurance Portability and Accountability Act compliance",
        # Applies to regulated health data
        applies_to_classifications=[DataClassification.REGULATED],
        # HIPAA requires 6 year minimum retention
        min_retention_days=365 * 6,
        # Security requirements
        requires_secure_deletion=True,
        requires_access_logging=True,
        # High priority
        priority=150
    )
    lifecycle_manager.compliance_rules[hipaa_rule.id] = hipaa_rule
    logger.info(f"Created HIPAA compliance rule: {hipaa_rule.id}")
    
    # 5. Create cost optimization rules
    logger.info("\nCreating cost optimization rules...")
    
    # Tiered storage rule (move large infrequently accessed data to cheaper storage)
    tiered_storage_rule = CostOptimizationRule(
        id=str(uuid.uuid4()),
        name="Tiered Storage Optimization",
        strategy=CostOptimizationStrategy.STORAGE_TIERING,
        description="Move large, infrequently accessed data to cheaper storage",
        min_size_bytes=1024 * 1024 * 10,  # 10 MB
        min_age_days=30,
        max_access_frequency=0.1,  # Less than 1 access per 10 days
        target_backend="economy-storage"
    )
    lifecycle_manager.cost_optimization_rules[tiered_storage_rule.id] = tiered_storage_rule
    logger.info(f"Created tiered storage rule: {tiered_storage_rule.id}")
    
    # Deduplication rule
    deduplication_rule = CostOptimizationRule(
        id=str(uuid.uuid4()),
        name="Deduplication Optimization",
        strategy=CostOptimizationStrategy.DEDUPLICATION,
        description="Deduplicate content to save storage space",
        min_size_bytes=1024 * 1024,  # 1 MB
        min_age_days=7
    )
    lifecycle_manager.cost_optimization_rules[deduplication_rule.id] = deduplication_rule
    logger.info(f"Created deduplication rule: {deduplication_rule.id}")
    
    # Compression rule
    compression_rule = CostOptimizationRule(
        id=str(uuid.uuid4()),
        name="Compression Optimization",
        strategy=CostOptimizationStrategy.COMPRESSION,
        description="Compress content to save storage space",
        min_size_bytes=1024 * 1024 * 5,  # 5 MB
        min_age_days=14
    )
    lifecycle_manager.cost_optimization_rules[compression_rule.id] = compression_rule
    logger.info(f"Created compression rule: {compression_rule.id}")
    
    # 6. List all rules
    logger.info("\nListing all rules:")
    
    logger.info(f"Retention rules: {len(lifecycle_manager.retention_rules)}")
    for rule_id, rule in lifecycle_manager.retention_rules.items():
        logger.info(f"  - {rule.name}: {rule.policy_type}")
    
    logger.info(f"Classification rules: {len(lifecycle_manager.classification_rules)}")
    for rule_id, rule in lifecycle_manager.classification_rules.items():
        logger.info(f"  - {rule.name}: {rule.classification}")
    
    logger.info(f"Archive rules: {len(lifecycle_manager.archive_rules)}")
    for rule_id, rule in lifecycle_manager.archive_rules.items():
        logger.info(f"  - {rule.name}: {rule.strategy}")
    
    logger.info(f"Compliance rules: {len(lifecycle_manager.compliance_rules)}")
    for rule_id, rule in lifecycle_manager.compliance_rules.items():
        logger.info(f"  - {rule.name}: {rule.regulation}")
    
    logger.info(f"Cost optimization rules: {len(lifecycle_manager.cost_optimization_rules)}")
    for rule_id, rule in lifecycle_manager.cost_optimization_rules.items():
        logger.info(f"  - {rule.name}: {rule.strategy}")


def demonstrate_content_lifecycle(lifecycle_manager: LifecycleManager, temp_dir: str):
    """Demonstrate content lifecycle management."""
    logger.info("\n=== Content Lifecycle Demonstration ===\n")
    
    # 1. Register content for lifecycle management
    logger.info("Registering content...")
    
    # Public document
    public_doc_id = str(uuid.uuid4())
    public_doc_path = os.path.join(temp_dir, "public_document.txt")
    with open(public_doc_path, 'w') as f:
        f.write("This is a public document that can be shared openly with anyone.\n")
        f.write("It contains information that is suitable for public consumption.\n")
    
    public_doc_metadata = lifecycle_manager.register_content(
        content_id=public_doc_id,
        size_bytes=os.path.getsize(public_doc_path),
        backend="primary-storage",
        metadata={"type": "document", "visibility": "public"},
        path=public_doc_path
    )
    logger.info(f"Registered public document: {public_doc_id}")
    logger.info(f"  Classification: {public_doc_metadata.classification}")
    
    # Re-classify with content data (should match the public rule)
    with open(public_doc_path, 'rb') as f:
        content_data = f.read()
        classification = lifecycle_manager._classify_content(
            content=content_data,
            metadata={"type": "document", "visibility": "public"},
            path=public_doc_path
        )
        logger.info(f"  Content-based classification: {classification}")
    
    # Internal document
    internal_doc_id = str(uuid.uuid4())
    internal_doc_path = os.path.join(temp_dir, "internal_document.txt")
    with open(internal_doc_path, 'w') as f:
        f.write("INTERNAL USE ONLY\n")
        f.write("This document contains information for staff members only.\n")
        f.write("It should not be shared outside the organization.\n")
    
    internal_doc_metadata = lifecycle_manager.register_content(
        content_id=internal_doc_id,
        size_bytes=os.path.getsize(internal_doc_path),
        backend="primary-storage",
        metadata={"type": "document", "visibility": "internal"},
        path=internal_doc_path
    )
    logger.info(f"Registered internal document: {internal_doc_id}")
    logger.info(f"  Classification: {internal_doc_metadata.classification}")
    
    # Confidential document
    confidential_doc_id = str(uuid.uuid4())
    confidential_doc_path = os.path.join(temp_dir, "confidential_document.txt")
    with open(confidential_doc_path, 'w') as f:
        f.write("CONFIDENTIAL\n")
        f.write("This document contains proprietary and sensitive business information.\n")
        f.write("Do not distribute without appropriate authorization.\n")
    
    confidential_doc_metadata = lifecycle_manager.register_content(
        content_id=confidential_doc_id,
        size_bytes=os.path.getsize(confidential_doc_path),
        backend="primary-storage",
        metadata={"type": "document", "confidentiality": "high"},
        path=confidential_doc_path
    )
    logger.info(f"Registered confidential document: {confidential_doc_id}")
    logger.info(f"  Classification: {confidential_doc_metadata.classification}")
    
    # PII document
    pii_doc_id = str(uuid.uuid4())
    pii_doc_path = os.path.join(temp_dir, "personal_data.txt")
    with open(pii_doc_path, 'w') as f:
        f.write("PERSONAL INFORMATION\n")
        f.write("Name: John Doe\n")
        f.write("Social Security Number: 123-45-6789\n")
        f.write("Address: 123 Main Street, Anytown, USA\n")
        f.write("Credit Card: 4111-1111-1111-1111\n")
        f.write("Birthday: January 1, 1980\n")
    
    pii_doc_metadata = lifecycle_manager.register_content(
        content_id=pii_doc_id,
        size_bytes=os.path.getsize(pii_doc_path),
        backend="primary-storage",
        metadata={"type": "personal_data"},
        path=pii_doc_path
    )
    logger.info(f"Registered PII document: {pii_doc_id}")
    logger.info(f"  Classification: {pii_doc_metadata.classification}")
    
    # 2. Record access to content
    logger.info("\nRecording content access...")
    
    # Public document gets accessed frequently
    for i in range(20):
        lifecycle_manager.record_access(
            content_id=public_doc_id,
            user_id=f"user{i % 5}",
            operation="read",
            client_ip="192.168.1.100"
        )
    logger.info(f"Recorded 20 accesses to public document")
    
    # Internal document gets moderate access
    for i in range(5):
        lifecycle_manager.record_access(
            content_id=internal_doc_id,
            user_id=f"user{i % 3}",
            operation="read",
            client_ip="192.168.1.101"
        )
    logger.info(f"Recorded 5 accesses to internal document")
    
    # Confidential document gets limited access
    lifecycle_manager.record_access(
        content_id=confidential_doc_id,
        user_id="admin",
        operation="read",
        client_ip="192.168.1.102"
    )
    logger.info(f"Recorded 1 access to confidential document")
    
    # PII document gets audited access
    lifecycle_manager.record_access(
        content_id=pii_doc_id,
        user_id="data_officer",
        operation="read",
        client_ip="192.168.1.103",
        access_metadata={"reason": "GDPR subject access request", "authorized_by": "Legal"}
    )
    logger.info(f"Recorded audited access to PII document")
    
    # 3. Demonstrate legal hold
    logger.info("\nDemonstrating legal hold...")
    
    # Place legal hold on confidential document
    lifecycle_manager.place_legal_hold(
        content_id=confidential_doc_id,
        reason="Pending litigation - Case #12345"
    )
    logger.info(f"Placed legal hold on confidential document")
    
    # Verify we can't delete content on legal hold
    try:
        result = lifecycle_manager.delete_content(content_id=confidential_doc_id)
        logger.info(f"Attempted to delete content on legal hold: {'succeeded' if result else 'failed'}")
    except Exception as e:
        logger.error(f"Error attempting to delete content on legal hold: {e}")
    
    # Release legal hold
    lifecycle_manager.release_legal_hold(content_id=confidential_doc_id)
    logger.info(f"Released legal hold on confidential document")
    
    # 4. Demonstrate secure deletion
    logger.info("\nDemonstrating secure deletion...")
    
    # Create temporary content
    temp_content_id = str(uuid.uuid4())
    lifecycle_manager.register_content(
        content_id=temp_content_id,
        size_bytes=1024,
        backend="primary-storage",
        metadata={"type": "temporary", "delete_after": "30 days"}
    )
    logger.info(f"Registered temporary content: {temp_content_id}")
    
    # Delete content securely
    lifecycle_manager.delete_content(content_id=temp_content_id, secure=True)
    logger.info(f"Securely deleted temporary content")
    
    # Verify deletion
    temp_metadata = lifecycle_manager.metadata.get(temp_content_id)
    if temp_metadata:
        logger.info(f"  New state: {temp_metadata.current_state}")
        logger.info(f"  Deletion certificate: {temp_metadata.deletion_certificate is not None}")
    
    # 5. Demonstrate lifecycle policy effects
    logger.info("\nDemonstrating lifecycle policy effects...")
    
    # Simulate time passing for different content types
    now = datetime.utcnow()
    
    # Simulate old low-access content for archiving
    old_content_id = str(uuid.uuid4())
    one_year_ago = (now - timedelta(days=366)).isoformat()
    lifecycle_manager.register_content(
        content_id=old_content_id,
        size_bytes=1024 * 1024 * 100,  # 100 MB
        backend="primary-storage",
        metadata={"type": "archive_candidate"}
    )
    # Manually update timestamps to simulate old content
    old_metadata = lifecycle_manager.metadata[old_content_id]
    old_metadata.create_date = one_year_ago
    old_metadata.last_modified = one_year_ago
    old_metadata.last_accessed = one_year_ago
    logger.info(f"Registered simulated old content: {old_content_id}")
    
    # Simulate applying archive rules
    lifecycle_manager._apply_archiving_rules_sync(old_content_id)
    logger.info(f"  New state after archiving rules: {lifecycle_manager.metadata[old_content_id].current_state}")
    
    # Simulate very old content for retention policy expiration
    expired_content_id = str(uuid.uuid4())
    eight_years_ago = (now - timedelta(days=365 * 8)).isoformat()
    lifecycle_manager.register_content(
        content_id=expired_content_id,
        size_bytes=1024 * 1024,  # 1 MB
        backend="archive-storage",
        metadata={"type": "old_record"}
    )
    # Manually update timestamps to simulate very old content
    expired_metadata = lifecycle_manager.metadata[expired_content_id]
    expired_metadata.create_date = eight_years_ago
    expired_metadata.last_modified = eight_years_ago
    expired_metadata.last_accessed = eight_years_ago
    # Apply specific retention rule
    for rule_id, rule in lifecycle_manager.retention_rules.items():
        if rule.name == "Long-term Retention":
            expired_metadata.retention_rule_id = rule_id
            break
    logger.info(f"Registered simulated expired content: {expired_content_id}")
    
    # Simulate applying retention policies
    lifecycle_manager._enforce_retention_policies_sync(expired_content_id)
    logger.info(f"  New state after retention policies: {lifecycle_manager.metadata[expired_content_id].current_state}")
    
    # 6. View access logs
    logger.info("\nViewing access logs:")
    
    for content_id, logs in lifecycle_manager.access_logs.items():
        if logs:
            content_type = lifecycle_manager.metadata[content_id].custom_attributes.get("type", "unknown")
            classification = lifecycle_manager.metadata[content_id].classification or "unclassified"
            logger.info(f"Access logs for {content_id} ({content_type}, {classification}):")
            logger.info(f"  Total accesses: {len(logs)}")
            logger.info(f"  First access: {logs[0].timestamp}")
            logger.info(f"  Last access: {logs[-1].timestamp}")
            
            # Show unique users
            users = set(log.user_id for log in logs if log.user_id)
            logger.info(f"  Unique users: {', '.join(users) if users else 'None'}")


def _apply_archiving_rules_sync(lifecycle_manager: LifecycleManager, content_id: str):
    """Helper method to synchronously apply archiving rules to a specific content item."""
    metadata = lifecycle_manager.metadata.get(content_id)
    if not metadata:
        return
    
    # Skip content that's not in ACTIVE state
    if metadata.current_state != DataLifecycleState.ACTIVE:
        return
    
    # Skip content on legal hold
    if metadata.legal_hold:
        return
    
    # Find applicable archive rule
    rule = None
    
    if metadata.archive_rule_id:
        # Use assigned rule if it exists and is enabled
        rule_id = metadata.archive_rule_id
        if rule_id in lifecycle_manager.archive_rules:
            rule = lifecycle_manager.archive_rules[rule_id]
            if not rule.enabled:
                rule = None
    
    # If no rule assigned or rule not found, find best match
    if not rule:
        # Get all enabled archive rules
        enabled_rules = [r for r in lifecycle_manager.archive_rules.values() if r.enabled]
        
        # Sort by priority (highest first)
        enabled_rules.sort(key=lambda r: r.priority, reverse=True)
        
        for candidate_rule in enabled_rules:
            # For now, assign first enabled rule
            rule = candidate_rule
            metadata.archive_rule_id = rule.id
            break
    
    # Skip if no rule found
    if not rule:
        logger.debug(f"No archive rule found for content {content_id}")
        return
    
    # Check if content should be archived
    creation_date = datetime.fromisoformat(metadata.create_date)
    last_accessed = datetime.fromisoformat(metadata.last_accessed) if metadata.last_accessed else None
    
    if rule.should_archive(creation_date, last_accessed, metadata.access_count):
        logger.info(f"Content {content_id} should be archived under rule {rule.id}")
        
        # Update metadata
        metadata.current_state = DataLifecycleState.ARCHIVED
        metadata.last_modified = datetime.utcnow().isoformat()
        
        return True
    
    return False


def _enforce_retention_policies_sync(lifecycle_manager: LifecycleManager, content_id: str):
    """Helper method to synchronously enforce retention policies for a specific content item."""
    metadata = lifecycle_manager.metadata.get(content_id)
    if not metadata:
        return
    
    # Skip content on legal hold
    if metadata.legal_hold:
        return
    
    # Find applicable retention rule
    rule = None
    
    if metadata.retention_rule_id:
        # Use assigned rule if it exists and is enabled
        rule_id = metadata.retention_rule_id
        if rule_id in lifecycle_manager.retention_rules:
            rule = lifecycle_manager.retention_rules[rule_id]
            if not rule.enabled:
                rule = None
    
    # If no rule assigned or rule not found, find best match
    if not rule:
        # Get all enabled retention rules
        enabled_rules = [r for r in lifecycle_manager.retention_rules.values() if r.enabled]
        
        for candidate_rule in sorted(enabled_rules, key=lambda r: r.name):
            # Skip rules that don't apply
            if not candidate_rule.enabled:
                continue
            
            # For now, assign first enabled rule
            rule = candidate_rule
            metadata.retention_rule_id = rule.id
            break
    
    # Skip if no rule found
    if not rule:
        logger.debug(f"No retention rule found for content {content_id}")
        return
    
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
        
        return True
    
    return False


def main():
    """Run the lifecycle management example."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Data Lifecycle Management Example")
    parser.add_argument(
        "--storage-path", 
        help="Path for the storage files",
        default=os.path.join(tempfile.gettempdir(), "lifecycle_example_storage")
    )
    parser.add_argument(
        "--metadata-path", 
        help="Path for the metadata database",
        default=os.path.join(tempfile.gettempdir(), "lifecycle_metadata.json")
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose logging"
    )
    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("lifecycle-example").setLevel(logging.DEBUG)
    
    # Create storage path if it doesn't exist
    os.makedirs(args.storage_path, exist_ok=True)
    
    # Initialize the lifecycle manager
    lifecycle_manager = LifecycleManager(metadata_db_path=args.metadata_path)
    
    try:
        # Start the lifecycle manager
        logger.info("Starting lifecycle manager...")
        lifecycle_manager.start()
        
        # Demonstrate rule creation
        demonstrate_rule_creation(lifecycle_manager)
        
        # Demonstrate content lifecycle
        demonstrate_content_lifecycle(lifecycle_manager, args.storage_path)
        
        logger.info("\nLifecycle management example completed successfully!")
        logger.info(f"Metadata database saved to: {args.metadata_path}")
        logger.info(f"Example content stored in: {args.storage_path}")
        
    except KeyboardInterrupt:
        logger.info("Example interrupted by user")
    except Exception as e:
        logger.error(f"Error running example: {e}", exc_info=True)
    finally:
        # Stop the lifecycle manager
        logger.info("Stopping lifecycle manager...")
        lifecycle_manager.stop()


if __name__ == "__main__":
    main()
