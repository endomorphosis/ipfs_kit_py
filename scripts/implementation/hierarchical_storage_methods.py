"""
Hierarchical storage management methods to be added to IPFSFileSystem.

These methods implement tiered storage management, content integrity verification,
replication policies, and tier health monitoring.
"""

def _verify_content_integrity(self, cid):
    """
    Verify content integrity across storage tiers.
    
    This method checks that the content stored in different tiers is identical
    and matches the expected hash.
    
    Args:
        cid: Content identifier to verify
        
    Returns:
        Dictionary with verification results
    """
    result = {
        "success": True,
        "operation": "verify_content_integrity",
        "cid": cid,
        "timestamp": time.time(),
        "verified_tiers": 0,
        "corrupted_tiers": []
    }
    
    # Get tiers that should contain this content
    tiers = self._get_content_tiers(cid)
    if not tiers:
        result["success"] = False
        result["error"] = f"Content {cid} not found in any tier"
        return result
    
    # Get content from first tier as reference
    reference_tier = tiers[0]
    try:
        reference_content = self._get_from_tier(cid, reference_tier)
        reference_hash = self._compute_hash(reference_content)
    except Exception as e:
        result["success"] = False
        result["error"] = f"Failed to get reference content from {reference_tier}: {str(e)}"
        return result
    
    # Check content in each tier
    result["verified_tiers"] = 1  # Count reference tier
    
    for tier in tiers[1:]:
        try:
            tier_content = self._get_from_tier(cid, tier)
            tier_hash = self._compute_hash(tier_content)
            
            if tier_hash != reference_hash:
                # Content mismatch detected
                result["corrupted_tiers"].append({
                    "tier": tier,
                    "expected_hash": reference_hash,
                    "actual_hash": tier_hash
                })
                result["success"] = False
            else:
                result["verified_tiers"] += 1
                
        except Exception as e:
            logger.warning(f"Failed to verify content in tier {tier}: {e}")
            # Don't count this as corruption, just a retrieval failure
            result["retrieval_errors"] = result.get("retrieval_errors", [])
            result["retrieval_errors"].append({
                "tier": tier,
                "error": str(e)
            })
    
    # Log the verification result
    if result["success"]:
        logger.info(f"Content {cid} integrity verified across {result['verified_tiers']} tiers")
    else:
        logger.warning(f"Content {cid} integrity check failed: {len(result['corrupted_tiers'])} corrupted tiers")
    
    return result

def _compute_hash(self, content):
    """
    Compute hash for content integrity verification.
    
    Args:
        content: Binary content to hash
        
    Returns:
        Content hash as string
    """
    import hashlib
    return hashlib.sha256(content).hexdigest()

def _get_content_tiers(self, cid):
    """
    Get the tiers that should contain a given content.
    
    Args:
        cid: Content identifier
        
    Returns:
        List of tier names
    """
    # Check each tier to see if it contains the content
    tiers = []
    
    # Check memory cache
    if hasattr(self, 'cache') and hasattr(self.cache, 'memory_cache'):
        if cid in self.cache.memory_cache:
            tiers.append("memory")
    
    # Check disk cache
    if hasattr(self, 'cache') and hasattr(self.cache, 'disk_cache'):
        if cid in self.cache.disk_cache.index:
            tiers.append("disk")
    
    # Check IPFS
    try:
        # Just check if content exists without downloading
        self.info(f"ipfs://{cid}")
        tiers.append("ipfs_local")
    except Exception:
        pass
    
    # Check IPFS cluster if available
    if hasattr(self, 'ipfs_cluster') and self.ipfs_cluster:
        try:
            # Check if content is pinned in cluster
            pin_info = self.ipfs_cluster.pin_ls(cid)
            if pin_info.get("success", False):
                tiers.append("ipfs_cluster")
        except Exception:
            pass
    
    return tiers

def _check_replication_policy(self, cid, content=None):
    """
    Check and apply content replication policy across tiers.
    
    Content with high value or importance (as determined by heat score)
    is replicated across multiple tiers for redundancy.
    
    Args:
        cid: Content identifier
        content: Content data (optional, to avoid re-fetching)
        
    Returns:
        Dictionary with replication results
    """
    result = {
        "success": True,
        "operation": "check_replication_policy",
        "cid": cid,
        "timestamp": time.time(),
        "replicated_to": []
    }
    
    # Get current tiers that have this content
    current_tiers = self._get_content_tiers(cid)
    result["current_tiers"] = current_tiers
    
    # Skip if no replication policy is defined
    if not hasattr(self, 'cache_config') or not self.cache_config.get('replication_policy'):
        return result
    
    # Get heat score to determine content value
    heat_score = 0
    if hasattr(self, 'cache') and hasattr(self.cache, 'get_heat_score'):
        heat_score = self.cache.get_heat_score(cid)
    elif hasattr(self, 'cache') and hasattr(self.cache, 'access_stats'):
        heat_score = self.cache.access_stats.get(cid, {}).get('heat_score', 0)
    
    # Get content if not provided
    if content is None:
        try:
            content = self.cat(f"ipfs://{cid}")
        except Exception as e:
            result["success"] = False
            result["error"] = f"Failed to retrieve content: {str(e)}"
            return result
    
    # Apply replication policy based on heat score
    policy = self.cache_config.get('replication_policy', 'high_value')
    
    if policy == 'high_value' and heat_score > 5.0:
        # Highly valued content should be replicated to multiple tiers
        target_tiers = ['ipfs_local', 'ipfs_cluster']
        
        for tier in target_tiers:
            if tier not in current_tiers:
                try:
                    self._put_in_tier(cid, content, tier)
                    result["replicated_to"].append(tier)
                except Exception as e:
                    logger.warning(f"Failed to replicate {cid} to {tier}: {e}")
    
    elif policy == 'all':
        # Replicate everything to all tiers
        target_tiers = ['memory', 'disk', 'ipfs_local', 'ipfs_cluster']
        
        for tier in target_tiers:
            if tier not in current_tiers:
                try:
                    self._put_in_tier(cid, content, tier)
                    result["replicated_to"].append(tier)
                except Exception as e:
                    logger.warning(f"Failed to replicate {cid} to {tier}: {e}")
    
    # Log replication results
    if result["replicated_to"]:
        logger.info(f"Replicated content {cid} to additional tiers: {result['replicated_to']}")
    
    return result

def _put_in_tier(self, cid, content, tier):
    """
    Put content in a specific storage tier.
    
    Args:
        cid: Content identifier
        content: Content data
        tier: Target tier name
        
    Returns:
        True if successful, False otherwise
    """
    if tier == "memory":
        if hasattr(self, 'cache') and hasattr(self.cache, 'memory_cache'):
            return self.cache.memory_cache.put(cid, content)
    
    elif tier == "disk":
        if hasattr(self, 'cache') and hasattr(self.cache, 'disk_cache'):
            return self.cache.disk_cache.put(cid, content)
    
    elif tier == "ipfs_local":
        # Add to local IPFS
        result = self.ipfs_py.add(content)
        if result.get("success", False):
            # Pin to ensure persistence
            self.ipfs_py.pin_add(cid)
            return True
    
    elif tier == "ipfs_cluster":
        if hasattr(self, 'ipfs_cluster') and self.ipfs_cluster:
            # Make sure content is in IPFS first
            if "ipfs_local" not in self._get_content_tiers(cid):
                self._put_in_tier(cid, content, "ipfs_local")
            
            # Pin to cluster
            result = self.ipfs_cluster.pin_add(cid)
            return result.get("success", False)
    
    return False

def _get_from_tier(self, cid, tier):
    """
    Get content from a specific storage tier.
    
    Args:
        cid: Content identifier
        tier: Source tier name
        
    Returns:
        Content data if found, None otherwise
    """
    if tier == "memory":
        if hasattr(self, 'cache') and hasattr(self.cache, 'memory_cache'):
            return self.cache.memory_cache.get(cid)
    
    elif tier == "disk":
        if hasattr(self, 'cache') and hasattr(self.cache, 'disk_cache'):
            return self.cache.disk_cache.get(cid)
    
    elif tier == "ipfs_local":
        # Get from local IPFS
        try:
            return self.ipfs_py.cat(cid)
        except Exception:
            return None
    
    elif tier == "ipfs_cluster":
        if hasattr(self, 'ipfs_cluster') and self.ipfs_cluster:
            # Redirect to ipfs local since cluster doesn't directly serve content
            return self._get_from_tier(cid, "ipfs_local")
    
    return None

def _migrate_to_tier(self, cid, source_tier, target_tier):
    """
    Migrate content from one tier to another.
    
    Args:
        cid: Content identifier
        source_tier: Source tier name
        target_tier: Target tier name
        
    Returns:
        Dictionary with migration results
    """
    result = {
        "success": False,
        "operation": "migrate_to_tier",
        "cid": cid,
        "source_tier": source_tier,
        "target_tier": target_tier,
        "timestamp": time.time()
    }
    
    # Get content from source tier
    content = self._get_from_tier(cid, source_tier)
    if content is None:
        result["error"] = f"Content not found in source tier {source_tier}"
        return result
    
    # Put content in target tier
    target_result = self._put_in_tier(cid, content, target_tier)
    if not target_result:
        result["error"] = f"Failed to put content in target tier {target_tier}"
        return result
    
    # For demotion (moving to lower tier), we can remove from higher tier to save space
    if self._get_tier_priority(source_tier) < self._get_tier_priority(target_tier):
        # This is a demotion (e.g., memory->disk), we can remove from source
        self._remove_from_tier(cid, source_tier)
        result["removed_from_source"] = True
    
    result["success"] = True
    logger.info(f"Migrated content {cid} from {source_tier} to {target_tier}")
    return result

def _remove_from_tier(self, cid, tier):
    """
    Remove content from a specific tier.
    
    Args:
        cid: Content identifier
        tier: Tier to remove from
        
    Returns:
        True if successful, False otherwise
    """
    if tier == "memory":
        if hasattr(self, 'cache') and hasattr(self.cache, 'memory_cache'):
            # Just access the key to trigger AR cache management
            self.cache.memory_cache.evict(cid)
            return True
    
    elif tier == "disk":
        if hasattr(self, 'cache') and hasattr(self.cache, 'disk_cache'):
            # TODO: Implement disk cache removal method
            return False
    
    elif tier == "ipfs_local":
        # Unpin from local IPFS
        try:
            result = self.ipfs_py.pin_rm(cid)
            return result.get("success", False)
        except Exception:
            return False
    
    elif tier == "ipfs_cluster":
        if hasattr(self, 'ipfs_cluster') and self.ipfs_cluster:
            try:
                result = self.ipfs_cluster.pin_rm(cid)
                return result.get("success", False)
            except Exception:
                return False
    
    return False

def _get_tier_priority(self, tier):
    """
    Get numeric priority value for a tier (lower is faster/higher priority).
    
    Args:
        tier: Tier name
        
    Returns:
        Priority value (lower is higher priority)
    """
    tier_priorities = {
        "memory": 1,
        "disk": 2,
        "ipfs_local": 3,
        "ipfs_cluster": 4
    }
    
    # Handle custom tier configuration if available
    if hasattr(self, 'cache_config') and 'tiers' in self.cache_config:
        tier_config = self.cache_config['tiers']
        if tier in tier_config and 'priority' in tier_config[tier]:
            return tier_config[tier]['priority']
    
    # Return default priority or very low priority if unknown
    return tier_priorities.get(tier, 999)

def _check_tier_health(self, tier):
    """
    Check the health of a storage tier.
    
    Args:
        tier: Tier name to check
        
    Returns:
        True if tier is healthy, False otherwise
    """
    if tier == "memory":
        # Memory is always considered healthy unless critically low on system memory
        import psutil
        mem = psutil.virtual_memory()
        return mem.available > 100 * 1024 * 1024  # At least 100MB available
    
    elif tier == "disk":
        if hasattr(self, 'cache') and hasattr(self.cache, 'disk_cache'):
            # Check if disk has enough free space
            try:
                cache_dir = self.cache.disk_cache.directory
                disk_usage = shutil.disk_usage(cache_dir)
                return disk_usage.free > 100 * 1024 * 1024  # At least 100MB available
            except Exception:
                return False
    
    elif tier == "ipfs_local":
        # Check if IPFS daemon is responsive
        try:
            version = self.ipfs_py.version()
            return version.get("success", False)
        except Exception:
            return False
    
    elif tier == "ipfs_cluster":
        if hasattr(self, 'ipfs_cluster') and self.ipfs_cluster:
            try:
                # Check if cluster is responsive
                version = self.ipfs_cluster.version()
                return version.get("success", False)
            except Exception:
                return False
        return False
    
    # Unknown tier
    return False

def _check_for_demotions(self):
    """
    Check content for potential demotion to lower tiers.
    
    This method identifies content that hasn't been accessed recently
    and can be moved to lower-priority tiers to free up space in
    higher-priority tiers.
    
    Returns:
        Dictionary with demotion results
    """
    result = {
        "success": True,
        "operation": "check_for_demotions",
        "timestamp": time.time(),
        "demoted_items": [],
        "errors": []
    }
    
    # Skip if no demotion parameters defined
    if not hasattr(self, 'cache_config') or 'demotion_threshold' not in self.cache_config:
        return result
    
    # Threshold in days for demotion
    demotion_days = self.cache_config.get('demotion_threshold', 30)
    demotion_seconds = demotion_days * 24 * 3600
    
    current_time = time.time()
    
    # Go through memory cache
    if hasattr(self, 'cache') and hasattr(self.cache, 'memory_cache'):
        # Look at access stats
        for cid, stats in self.cache.access_stats.items():
            if cid in self.cache.memory_cache:
                last_access = stats.get('last_access', 0)
                
                # Check if item hasn't been accessed recently
                if current_time - last_access > demotion_seconds:
                    try:
                        # Migrate from memory to disk
                        migrate_result = self._migrate_to_tier(cid, "memory", "disk")
                        if migrate_result.get("success", False):
                            result["demoted_items"].append({
                                "cid": cid,
                                "from_tier": "memory",
                                "to_tier": "disk",
                                "last_access_days": (current_time - last_access) / 86400
                            })
                    except Exception as e:
                        result["errors"].append({
                            "cid": cid,
                            "error": str(e)
                        })
    
    # Go through disk cache for potential demotion to IPFS
    if hasattr(self, 'cache') and hasattr(self.cache, 'disk_cache'):
        for cid, entry in self.cache.disk_cache.index.items():
            last_access = entry.get('last_access', 0)
            
            # Check if item hasn't been accessed recently
            if current_time - last_access > demotion_seconds * 2:  # More conservative for disk->IPFS
                try:
                    # Migrate from disk to IPFS local
                    migrate_result = self._migrate_to_tier(cid, "disk", "ipfs_local")
                    if migrate_result.get("success", False):
                        result["demoted_items"].append({
                            "cid": cid,
                            "from_tier": "disk",
                            "to_tier": "ipfs_local",
                            "last_access_days": (current_time - last_access) / 86400
                        })
                except Exception as e:
                    result["errors"].append({
                        "cid": cid,
                        "error": str(e)
                    })
    
    # Log demotion results
    if result["demoted_items"]:
        logger.info(f"Demoted {len(result['demoted_items'])} items to lower tiers")
    
    return result