"""
VFS Journal Manager for tracking virtual filesystem operations.
Provides detailed logging and filtering of filesystem activities across backends.
"""

import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VFSJournalManager:
    """Manages VFS operation journaling and provides filtering capabilities."""
    
    def __init__(self, log_dir: str = "/tmp/ipfs_kit_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # In-memory journal storage for quick access
        self.journal_entries = deque(maxlen=10000)  # Store up to 10k entries
        self.backend_journals = defaultdict(lambda: deque(maxlen=1000))  # Per-backend journals
        
        # Journal categories
        self.operation_types = {
            "file_operations": ["create", "read", "write", "delete", "move", "copy"],
            "directory_operations": ["mkdir", "rmdir", "list", "scan"],
            "metadata_operations": ["stat", "chmod", "chown", "touch"],
            "cache_operations": ["cache_hit", "cache_miss", "cache_write", "cache_evict"],
            "sync_operations": ["sync_start", "sync_complete", "sync_error"],
            "search_operations": ["search", "index", "query"]
        }
        
        # Setup journal file
        self.journal_file = self.log_dir / "vfs_journal.jsonl"
        
        logger.info("✓ VFS Journal Manager initialized")
    
    def add_journal_entry(self, backend: str, operation_type: str, operation: str, 
                         path: str, status: str = "success", details: Optional[Dict] = None):
        """Add a journal entry for a VFS operation."""
        timestamp = datetime.now()
        
        entry = {
            "id": f"vfs_{int(time.time() * 1000000)}",
            "timestamp": timestamp.isoformat(),
            "backend": backend,
            "operation_type": operation_type,
            "operation": operation,
            "path": path,
            "status": status,
            "details": details or {},
            "formatted_time": timestamp.strftime("%H:%M:%S"),
            "formatted_date": timestamp.strftime("%Y-%m-%d"),
            "size": details.get("size") if details else None,
            "duration_ms": details.get("duration_ms") if details else None
        }
        
        # Add to memory storage
        self.journal_entries.append(entry)
        self.backend_journals[backend].append(entry)
        
        # Write to journal file
        try:
            with open(self.journal_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write journal entry: {e}")
    
    def get_journal_entries(self, 
                           backend: Optional[str] = None,
                           operation_type: Optional[str] = None,
                           status: Optional[str] = None,
                           search_term: Optional[str] = None,
                           limit: int = 100,
                           hours: Optional[int] = None) -> List[Dict]:
        """Get filtered journal entries."""
        
        # Start with all entries or backend-specific entries
        if backend:
            entries = list(self.backend_journals.get(backend, []))
        else:
            entries = list(self.journal_entries)
        
        # Apply time filter
        if hours:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            entries = [e for e in entries if datetime.fromisoformat(e['timestamp']) >= cutoff_time]
        
        # Apply filters
        if operation_type:
            entries = [e for e in entries if e['operation_type'] == operation_type]
        
        if status:
            entries = [e for e in entries if e['status'] == status]
        
        if search_term:
            search_lower = search_term.lower()
            entries = [e for e in entries if 
                      search_lower in e['path'].lower() or 
                      search_lower in e['operation'].lower() or
                      search_lower in e.get('details', {}).get('description', '').lower()]
        
        # Sort by timestamp (most recent first) and limit
        entries.sort(key=lambda x: x['timestamp'], reverse=True)
        return entries[:limit]
    
    def get_backend_statistics(self) -> Dict[str, Any]:
        """Get statistics for all backends."""
        stats = {
            "total_entries": len(self.journal_entries),
            "backends": {},
            "operation_types": defaultdict(int),
            "status_summary": defaultdict(int),
            "recent_activity": self._get_recent_activity()
        }
        
        # Per-backend statistics
        for backend, entries in self.backend_journals.items():
            backend_stats = {
                "total_operations": len(entries),
                "operation_types": defaultdict(int),
                "status_counts": defaultdict(int),
                "recent_operations": 0,
                "last_activity": None
            }
            
            # Calculate recent activity (last hour)
            recent_cutoff = datetime.now() - timedelta(hours=1)
            
            for entry in entries:
                backend_stats["operation_types"][entry["operation_type"]] += 1
                backend_stats["status_counts"][entry["status"]] += 1
                stats["operation_types"][entry["operation_type"]] += 1
                stats["status_summary"][entry["status"]] += 1
                
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if entry_time >= recent_cutoff:
                    backend_stats["recent_operations"] += 1
                
                if not backend_stats["last_activity"] or entry["timestamp"] > backend_stats["last_activity"]:
                    backend_stats["last_activity"] = entry["timestamp"]
            
            # Convert defaultdicts to regular dicts
            backend_stats["operation_types"] = dict(backend_stats["operation_types"])
            backend_stats["status_counts"] = dict(backend_stats["status_counts"])
            
            stats["backends"][backend] = backend_stats
        
        # Convert defaultdicts to regular dicts
        stats["operation_types"] = dict(stats["operation_types"])
        stats["status_summary"] = dict(stats["status_summary"])
        
        return stats
    
    def _get_recent_activity(self) -> Dict[str, int]:
        """Get recent activity counts."""
        now = datetime.now()
        activity = {
            "last_hour": 0,
            "last_24h": 0,
            "last_week": 0
        }
        
        for entry in self.journal_entries:
            entry_time = datetime.fromisoformat(entry["timestamp"])
            time_diff = now - entry_time
            
            if time_diff <= timedelta(hours=1):
                activity["last_hour"] += 1
            if time_diff <= timedelta(days=1):
                activity["last_24h"] += 1
            if time_diff <= timedelta(weeks=1):
                activity["last_week"] += 1
        
        return activity
    
    def get_operation_timeline(self, backend: Optional[str] = None, hours: int = 24) -> List[Dict]:
        """Get operation timeline for visualization."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if backend:
            entries = [e for e in self.backend_journals.get(backend, []) 
                      if datetime.fromisoformat(e['timestamp']) >= cutoff_time]
        else:
            entries = [e for e in self.journal_entries 
                      if datetime.fromisoformat(e['timestamp']) >= cutoff_time]
        
        # Group by hour
        timeline = defaultdict(lambda: defaultdict(int))
        
        for entry in entries:
            entry_time = datetime.fromisoformat(entry["timestamp"])
            hour_key = entry_time.strftime("%Y-%m-%d %H:00")
            timeline[hour_key][entry["operation_type"]] += 1
            timeline[hour_key]["total"] += 1
        
        # Convert to list format
        result = []
        for hour, operations in sorted(timeline.items()):
            result.append({
                "time": hour,
                "operations": dict(operations)
            })
        
        return result
    
    def clear_journal(self, backend: Optional[str] = None):
        """Clear journal entries."""
        if backend:
            self.backend_journals[backend].clear()
            logger.info(f"Cleared VFS journal for backend: {backend}")
        else:
            self.journal_entries.clear()
            self.backend_journals.clear()
            logger.info("Cleared all VFS journal entries")
    
    def export_journal(self, backend: Optional[str] = None, 
                      format: str = "json", hours: Optional[int] = None) -> str:
        """Export journal entries to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Get entries to export
        if backend:
            filename = f"vfs_journal_{backend}_{timestamp}.{format}"
            entries = list(self.backend_journals.get(backend, []))
        else:
            filename = f"vfs_journal_all_{timestamp}.{format}"
            entries = list(self.journal_entries)
        
        # Apply time filter if specified
        if hours:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            entries = [e for e in entries if datetime.fromisoformat(e['timestamp']) >= cutoff_time]
        
        export_path = self.log_dir / filename
        
        try:
            if format == "json":
                with open(export_path, 'w') as f:
                    json.dump(entries, f, indent=2)
            elif format == "csv":
                import csv
                with open(export_path, 'w', newline='') as f:
                    if entries:
                        writer = csv.DictWriter(f, fieldnames=entries[0].keys())
                        writer.writeheader()
                        writer.writerows(entries)
            
            logger.info(f"Exported VFS journal to: {export_path}")
            return str(export_path)
            
        except Exception as e:
            logger.error(f"Failed to export VFS journal: {e}")
            raise
