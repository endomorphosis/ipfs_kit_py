#!/usr/bin/env python3
"""
Git VFS Translation Layer for IPFS-Kit

This module provides a translation layer between Git metadata and IPFS-Kit's virtual filesystem.
It handles the mapping between Git's line-based diff system and IPFS-Kit's content-addressed
block storage, maintaining additional VFS metadata alongside Git's native metadata.

Key Features:
- Maps Git commits to VFS snapshots
- Converts Git diff metadata to VFS block change metadata
- Maintains .ipfs_kit folder structure within Git repositories
- Handles HEAD tracking and filesystem mount points
- Preserves VFS metadata during Git operations
- Supports bidirectional translation (Git ↔ VFS)
"""

import os
import json
import hashlib
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

try:
    import git
    from git import Repo, InvalidGitRepositoryError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    git = None
    Repo = None
    InvalidGitRepositoryError = Exception

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

logger = logging.getLogger(__name__)

@dataclass
class VFSFileMetadata:
    """Extended VFS metadata for files beyond Git's tracking."""
    content_hash: str  # IPFS CID or content hash
    size: int
    mime_type: Optional[str] = None
    encoding: Optional[str] = None
    chunk_count: int = 0
    chunk_hashes: List[str] = None
    compression: Optional[str] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    vfs_path: Optional[str] = None
    block_links: List[str] = None  # Links to related content blocks
    tags: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.chunk_hashes is None:
            self.chunk_hashes = []
        if self.block_links is None:
            self.block_links = []
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class VFSSnapshot:
    """VFS representation of a Git commit."""
    commit_hash: str
    vfs_snapshot_id: str
    timestamp: datetime
    author: str
    message: str
    parent_snapshots: List[str]
    file_changes: Dict[str, VFSFileMetadata]
    tree_hash: str  # Root hash of the VFS tree
    car_files: List[str] = None  # Associated CAR files
    
    def __post_init__(self):
        if self.car_files is None:
            self.car_files = []

class GitVFSTranslator:
    """
    Translation layer between Git repositories and IPFS-Kit VFS.
    
    This class manages the bidirectional mapping between Git's version control
    system and IPFS-Kit's content-addressed virtual filesystem.
    """
    
    def __init__(self, repo_path: Union[str, Path], vfs_manager=None):
        """
        Initialize the Git VFS Translator.
        
        Args:
            repo_path: Path to the Git repository
            vfs_manager: Optional VFS manager instance
        """
        self.repo_path = Path(repo_path)
        self.vfs_manager = vfs_manager
        self.ipfs_kit_dir = self.repo_path / '.ipfs_kit'
        self.vfs_metadata_dir = self.ipfs_kit_dir / 'vfs_metadata'
        self.snapshots_dir = self.vfs_metadata_dir / 'snapshots'
        self.index_file = self.vfs_metadata_dir / 'vfs_index.json'
        self.head_file = self.vfs_metadata_dir / 'VFS_HEAD'
        
        # Initialize Git repo
        if GIT_AVAILABLE:
            try:
                self.git_repo = Repo(self.repo_path)
            except InvalidGitRepositoryError:
                self.git_repo = None
                logger.warning(f"Not a Git repository: {repo_path}")
        else:
            self.git_repo = None
            logger.warning("GitPython not available")
        
        # Initialize VFS metadata structure
        self._ensure_vfs_metadata_structure()
    
    def _ensure_vfs_metadata_structure(self):
        """Ensure the VFS metadata directory structure exists."""
        self.vfs_metadata_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(exist_ok=True)
        
        # Initialize index file if it doesn't exist
        if not self.index_file.exists():
            self._create_initial_index()
        
        # Initialize HEAD file if it doesn't exist
        if not self.head_file.exists():
            self._initialize_vfs_head()
    
    def _create_initial_index(self):
        """Create initial VFS index file."""
        initial_index = {
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'snapshots': {},
            'filesystem_mounts': {},
            'content_map': {},  # Maps Git blobs to VFS content hashes
            'metadata_schema_version': '1.0.0'
        }
        
        with open(self.index_file, 'w') as f:
            json.dump(initial_index, f, indent=2)
    
    def _initialize_vfs_head(self):
        """Initialize VFS HEAD pointer."""
        if self.git_repo and self.git_repo.head.is_valid():
            current_commit = self.git_repo.head.commit.hexsha
            vfs_snapshot_id = self._generate_vfs_snapshot_id(current_commit)
        else:
            vfs_snapshot_id = "initial"
        
        with open(self.head_file, 'w') as f:
            f.write(vfs_snapshot_id)
    
    def _generate_vfs_snapshot_id(self, git_commit_hash: str) -> str:
        """Generate VFS snapshot ID from Git commit hash."""
        # Create a deterministic VFS snapshot ID
        combined = f"vfs_{git_commit_hash}_{int(datetime.now().timestamp())}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def analyze_git_metadata(self) -> Dict[str, Any]:
        """
        Analyze Git repository metadata and structure.
        
        Returns:
            Dict containing Git repository analysis
        """
        analysis = {
            'repository_info': {},
            'branch_info': {},
            'commit_history': [],
            'file_changes': {},
            'submodules': [],
            'vfs_compatibility': {}
        }
        
        if not self.git_repo:
            analysis['error'] = "Git repository not available"
            return analysis
        
        try:
            # Repository information
            analysis['repository_info'] = {
                'path': str(self.repo_path),
                'bare': self.git_repo.bare,
                'active_branch': self.git_repo.active_branch.name if not self.git_repo.head.is_detached else None,
                'head_commit': self.git_repo.head.commit.hexsha,
                'total_commits': sum(1 for _ in self.git_repo.iter_commits()),
                'remotes': [remote.name for remote in self.git_repo.remotes],
                'tags': [tag.name for tag in self.git_repo.tags]
            }
            
            # Branch information
            analysis['branch_info'] = {
                branch.name: {
                    'commit': branch.commit.hexsha,
                    'last_modified': branch.commit.committed_date
                }
                for branch in self.git_repo.branches
            }
            
            # Recent commit history (last 10)
            for commit in list(self.git_repo.iter_commits(max_count=10)):
                commit_info = {
                    'hash': commit.hexsha,
                    'author': str(commit.author),
                    'authored_date': commit.authored_date,
                    'committed_date': commit.committed_date,
                    'message': commit.message.strip(),
                    'changed_files': len(commit.stats.files),
                    'insertions': commit.stats.total['insertions'],
                    'deletions': commit.stats.total['deletions']
                }
                analysis['commit_history'].append(commit_info)
            
            # Analyze file changes in recent commits
            analysis['file_changes'] = self._analyze_file_changes()
            
            # Check for submodules
            if hasattr(self.git_repo, 'submodules'):
                analysis['submodules'] = [
                    {
                        'name': submodule.name,
                        'path': submodule.path,
                        'url': submodule.url,
                        'hexsha': submodule.hexsha
                    }
                    for submodule in self.git_repo.submodules
                ]
            
            # VFS compatibility analysis
            analysis['vfs_compatibility'] = self._analyze_vfs_compatibility()
            
        except Exception as e:
            logger.error(f"Error analyzing Git metadata: {e}")
            analysis['error'] = str(e)
        
        return analysis
    
    def _analyze_file_changes(self) -> Dict[str, Any]:
        """Analyze file changes across recent commits."""
        changes = {
            'frequently_modified': defaultdict(int),
            'file_types': defaultdict(int),
            'large_files': [],
            'binary_files': []
        }
        
        try:
            # Analyze last 20 commits for patterns
            for commit in list(self.git_repo.iter_commits(max_count=20)):
                for file_path in commit.stats.files:
                    changes['frequently_modified'][file_path] += 1
                    
                    # File type analysis
                    file_ext = Path(file_path).suffix.lower()
                    changes['file_types'][file_ext or 'no_extension'] += 1
                    
                    # Check file size in current state
                    try:
                        current_file = self.repo_path / file_path
                        if current_file.exists():
                            size = current_file.stat().st_size
                            if size > 1024 * 1024:  # Files > 1MB
                                changes['large_files'].append({
                                    'path': file_path,
                                    'size': size
                                })
                            
                            # Simple binary detection
                            if self._is_likely_binary(current_file):
                                changes['binary_files'].append(file_path)
                    except Exception:
                        pass
            
            # Convert defaultdicts to regular dicts for JSON serialization
            changes['frequently_modified'] = dict(changes['frequently_modified'])
            changes['file_types'] = dict(changes['file_types'])
            
        except Exception as e:
            logger.error(f"Error analyzing file changes: {e}")
            changes['error'] = str(e)
        
        return changes
    
    def _is_likely_binary(self, file_path: Path) -> bool:
        """Simple binary file detection."""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\x00' in chunk
        except Exception:
            return False
    
    def _analyze_vfs_compatibility(self) -> Dict[str, Any]:
        """Analyze repository compatibility with VFS system."""
        compatibility = {
            'has_ipfs_kit_folder': self.ipfs_kit_dir.exists(),
            'vfs_metadata_present': self.vfs_metadata_dir.exists(),
            'supported_file_types': [],
            'unsupported_patterns': [],
            'recommendations': []
        }
        
        # Check for existing VFS structures
        if self.ipfs_kit_dir.exists():
            vfs_files = list(self.ipfs_kit_dir.rglob('*'))
            compatibility['vfs_files_count'] = len(vfs_files)
            compatibility['has_car_files'] = any(f.suffix == '.car' for f in vfs_files)
            compatibility['has_index_files'] = any('index' in f.name for f in vfs_files)
        
        # Analyze file types for VFS compatibility
        supported_extensions = {'.txt', '.md', '.json', '.yaml', '.yml', '.py', '.js', '.html', '.css'}
        binary_extensions = {'.jpg', '.png', '.pdf', '.zip', '.tar', '.gz', '.bin'}
        
        for file_path in self.repo_path.rglob('*'):
            if file_path.is_file() and not file_path.is_relative_to(self.repo_path / '.git'):
                ext = file_path.suffix.lower()
                if ext in supported_extensions:
                    compatibility['supported_file_types'].append(str(file_path.relative_to(self.repo_path)))
                elif ext in binary_extensions:
                    compatibility['unsupported_patterns'].append(str(file_path.relative_to(self.repo_path)))
        
        # Generate recommendations
        if not compatibility['has_ipfs_kit_folder']:
            compatibility['recommendations'].append("Initialize .ipfs_kit folder for VFS integration")
        
        if len(compatibility['unsupported_patterns']) > len(compatibility['supported_file_types']):
            compatibility['recommendations'].append("Repository contains many binary files - consider selective VFS integration")
        
        return compatibility
    
    def create_vfs_snapshot_from_commit(self, commit_hash: str) -> VFSSnapshot:
        """
        Create a VFS snapshot from a Git commit.
        
        Args:
            commit_hash: Git commit hash
            
        Returns:
            VFSSnapshot object
        """
        if not self.git_repo:
            raise ValueError("Git repository not available")
        
        try:
            commit = self.git_repo.commit(commit_hash)
            vfs_snapshot_id = self._generate_vfs_snapshot_id(commit_hash)
            
            # Analyze file changes in this commit
            file_changes = {}
            
            if commit.parents:  # Not initial commit
                diff = commit.parents[0].diff(commit)
                for diff_item in diff:
                    if diff_item.a_path:  # File was modified or deleted
                        file_metadata = self._create_file_metadata(diff_item.a_path, commit)
                        file_changes[diff_item.a_path] = file_metadata
                    
                    if diff_item.b_path and diff_item.b_path != diff_item.a_path:  # File was renamed/moved
                        file_metadata = self._create_file_metadata(diff_item.b_path, commit)
                        file_changes[diff_item.b_path] = file_metadata
            else:
                # Initial commit - all files are new
                for item in commit.tree.traverse():
                    if item.type == 'blob':  # It's a file
                        file_metadata = self._create_file_metadata(item.path, commit)
                        file_changes[item.path] = file_metadata
            
            # Create VFS snapshot
            snapshot = VFSSnapshot(
                commit_hash=commit_hash,
                vfs_snapshot_id=vfs_snapshot_id,
                timestamp=datetime.fromtimestamp(commit.committed_date),
                author=str(commit.author),
                message=commit.message.strip(),
                parent_snapshots=[self._generate_vfs_snapshot_id(p.hexsha) for p in commit.parents],
                file_changes=file_changes,
                tree_hash=commit.tree.hexsha
            )
            
            # Save snapshot to disk
            self._save_vfs_snapshot(snapshot)
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error creating VFS snapshot from commit {commit_hash}: {e}")
            raise
    
    def _create_file_metadata(self, file_path: str, commit) -> VFSFileMetadata:
        """Create VFS file metadata from Git file information."""
        try:
            # Get file blob from commit
            blob = commit.tree[file_path]
            content = blob.data_stream.read()
            
            # Calculate content hash (using IPFS-style hashing would be ideal)
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Determine MIME type (simple detection)
            mime_type = self._detect_mime_type(file_path, content)
            
            # Create metadata
            metadata = VFSFileMetadata(
                content_hash=content_hash,
                size=blob.size,
                mime_type=mime_type,
                encoding='utf-8' if self._is_text_file(content) else 'binary',
                created_at=datetime.fromtimestamp(commit.committed_date),
                modified_at=datetime.fromtimestamp(commit.committed_date),
                vfs_path=file_path,
                metadata={
                    'git_blob_hash': blob.hexsha,
                    'git_mode': oct(blob.mode),
                    'commit_hash': commit.hexsha
                }
            )
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error creating file metadata for {file_path}: {e}")
            # Return minimal metadata on error
            return VFSFileMetadata(
                content_hash="unknown",
                size=0,
                vfs_path=file_path,
                metadata={'error': str(e)}
            )
    
    def _detect_mime_type(self, file_path: str, content: bytes) -> str:
        """Simple MIME type detection."""
        ext = Path(file_path).suffix.lower()
        
        mime_map = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.json': 'application/json',
            '.yaml': 'application/yaml',
            '.yml': 'application/yaml',
            '.py': 'text/x-python',
            '.js': 'application/javascript',
            '.html': 'text/html',
            '.css': 'text/css',
            '.xml': 'application/xml',
            '.jpg': 'image/jpeg',
            '.png': 'image/png',
            '.pdf': 'application/pdf'
        }
        
        return mime_map.get(ext, 'application/octet-stream')
    
    def _is_text_file(self, content: bytes) -> bool:
        """Determine if content is text or binary."""
        try:
            content.decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False
    
    def _save_vfs_snapshot(self, snapshot: VFSSnapshot):
        """Save VFS snapshot to disk."""
        snapshot_file = self.snapshots_dir / f"{snapshot.vfs_snapshot_id}.json"
        
        # Convert snapshot to JSON-serializable format
        snapshot_data = asdict(snapshot)
        
        # Handle datetime serialization
        if isinstance(snapshot_data['timestamp'], datetime):
            snapshot_data['timestamp'] = snapshot_data['timestamp'].isoformat()
        
        # Handle file metadata serialization
        for file_path, metadata in snapshot_data['file_changes'].items():
            if isinstance(metadata['created_at'], datetime):
                metadata['created_at'] = metadata['created_at'].isoformat()
            if isinstance(metadata['modified_at'], datetime):
                metadata['modified_at'] = metadata['modified_at'].isoformat()
        
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot_data, f, indent=2)
        
        # Update index
        self._update_index_with_snapshot(snapshot)
    
    def _update_index_with_snapshot(self, snapshot: VFSSnapshot):
        """Update VFS index with new snapshot."""
        try:
            with open(self.index_file, 'r') as f:
                index = json.load(f)
            
            # Add snapshot to index
            index['snapshots'][snapshot.vfs_snapshot_id] = {
                'commit_hash': snapshot.commit_hash,
                'timestamp': snapshot.timestamp.isoformat() if isinstance(snapshot.timestamp, datetime) else snapshot.timestamp,
                'author': snapshot.author,
                'message': snapshot.message,
                'file_count': len(snapshot.file_changes)
            }
            
            # Update content map
            for file_path, metadata in snapshot.file_changes.items():
                index['content_map'][metadata.content_hash] = {
                    'file_path': file_path,
                    'snapshot_id': snapshot.vfs_snapshot_id,
                    'size': metadata.size,
                    'mime_type': metadata.mime_type
                }
            
            index['last_updated'] = datetime.now().isoformat()
            
            with open(self.index_file, 'w') as f:
                json.dump(index, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating index: {e}")
    
    def get_vfs_head(self) -> str:
        """Get current VFS HEAD snapshot ID."""
        try:
            with open(self.head_file, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return "initial"
    
    def set_vfs_head(self, snapshot_id: str):
        """Set VFS HEAD to specific snapshot."""
        with open(self.head_file, 'w') as f:
            f.write(snapshot_id)
    
    def sync_git_to_vfs(self) -> Dict[str, Any]:
        """
        Synchronize Git repository state to VFS.
        
        Creates VFS snapshots for recent Git commits that don't have them yet.
        """
        if not self.git_repo:
            return {'error': 'Git repository not available'}
        
        result = {
            'snapshots_created': 0,
            'snapshots_updated': 0,
            'errors': []
        }
        
        try:
            # Load existing index
            with open(self.index_file, 'r') as f:
                index = json.load(f)
            
            existing_commits = {snap_data['commit_hash'] for snap_data in index['snapshots'].values()}
            
            # Process recent commits (last 50)
            for commit in list(self.git_repo.iter_commits(max_count=50)):
                if commit.hexsha not in existing_commits:
                    try:
                        snapshot = self.create_vfs_snapshot_from_commit(commit.hexsha)
                        result['snapshots_created'] += 1
                        logger.info(f"Created VFS snapshot for commit {commit.hexsha[:8]}")
                    except Exception as e:
                        error_msg = f"Failed to create snapshot for {commit.hexsha[:8]}: {e}"
                        result['errors'].append(error_msg)
                        logger.error(error_msg)
            
            # Update VFS HEAD to current Git HEAD
            if self.git_repo.head.is_valid():
                current_commit = self.git_repo.head.commit.hexsha
                vfs_snapshot_id = self._generate_vfs_snapshot_id(current_commit)
                self.set_vfs_head(vfs_snapshot_id)
            
        except Exception as e:
            result['errors'].append(f"Sync error: {e}")
            logger.error(f"Git to VFS sync error: {e}")
        
        return result
    
    def export_vfs_metadata(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Export VFS metadata for external use or backup.
        
        Args:
            output_path: Optional path for export file
            
        Returns:
            Export result information
        """
        if output_path is None:
            output_path = self.repo_path / f"vfs_export_{int(datetime.now().timestamp())}.json"
        
        try:
            # Collect all VFS metadata
            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'repository_path': str(self.repo_path),
                'vfs_head': self.get_vfs_head(),
                'snapshots': {},
                'index': {}
            }
            
            # Load index
            if self.index_file.exists():
                with open(self.index_file, 'r') as f:
                    export_data['index'] = json.load(f)
            
            # Load all snapshots
            for snapshot_file in self.snapshots_dir.glob('*.json'):
                with open(snapshot_file, 'r') as f:
                    snapshot_data = json.load(f)
                    export_data['snapshots'][snapshot_file.stem] = snapshot_data
            
            # Write export file
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            return {
                'success': True,
                'export_path': str(output_path),
                'snapshots_exported': len(export_data['snapshots']),
                'file_size': output_path.stat().st_size
            }
            
        except Exception as e:
            logger.error(f"Export error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
