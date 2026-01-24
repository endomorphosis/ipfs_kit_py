#!/usr/bin/env python3
"""
GitHub Kit - Interface to GitHub repositories as virtual filesystem buckets

This module treats GitHub repositories as buckets in the virtual filesystem,
with the username serving as the peerID for local "forks" of content.
Provides seamless integration between GitHub repos and IPFS-Kit's VFS.

Key Concepts:
- GitHub repos = VFS buckets
- Username = peerID for local content forks  
- Dataset/ML model repos labeled appropriately in VFS
- Seamless transition between GitHub and local IPFS storage
- Git VFS translation layer for metadata mapping
"""

import os
import json
import anyio
import subprocess
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import tempfile
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not available - some features will be limited")

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    logger.warning("GitPython not available - clone operations will use subprocess")

# Import Git VFS translator
try:
    from .git_vfs_translator import GitVFSTranslator, VFSSnapshot
    GIT_VFS_AVAILABLE = True
except ImportError:
    GIT_VFS_AVAILABLE = False
    logger.warning("Git VFS translator not available - advanced Git integration disabled")

class GitHubKit:
    """
    GitHub repository interface for IPFS-Kit virtual filesystem.
    
    Treats GitHub repositories as buckets with the following mapping:
    - Repository -> VFS Bucket
    - Username -> PeerID for local forks
    - Dataset/Model repos -> Labeled in VFS accordingly
    - Git metadata -> VFS snapshots and content addressing
    """
    
    def __init__(self, token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize GitHub kit.
        
        Args:
            token: GitHub personal access token
            cache_dir: Local cache directory for repositories
        """
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.cache_dir = Path(cache_dir or os.path.expanduser('~/.ipfs_kit/github_cache'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.api_base = "https://api.github.com"
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ipfs-kit-github/1.0'
        }
        
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Dict:
        """Make authenticated request to GitHub API."""
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library not available - cannot make API calls")
        
        url = f"{self.api_base}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            raise
    
    async def authenticate(self, token: str) -> Dict[str, Any]:
        """
        Authenticate with GitHub and store token.
        
        Args:
            token: GitHub personal access token
            
        Returns:
            User information
        """
        self.token = token
        self.headers['Authorization'] = f'token {token}'
        
        # Test authentication by getting user info
        try:
            user_info = self._make_request('/user')
            
            # Store token securely
            token_file = self.cache_dir / '.github_token'
            token_file.write_text(token)
            token_file.chmod(0o600)  # Read-write for owner only
            
            logger.info(f"✅ Authenticated as {user_info['login']}")
            return user_info
        
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            raise
    
    async def list_repositories(self, user: Optional[str] = None, 
                              repo_type: str = 'owner', 
                              limit: int = 100) -> List[Dict[str, Any]]:
        """
        List GitHub repositories as VFS buckets.
        
        Args:
            user: GitHub username (default: authenticated user)
            repo_type: Repository type ('all', 'owner', 'member')
            limit: Maximum number of repositories to return
            
        Returns:
            List of repository information with VFS bucket metadata
        """
        try:
            if user:
                # List public repos for specified user
                endpoint = f'/users/{user}/repos'
                params = {'per_page': min(limit, 100)}
            else:
                # List repos for authenticated user
                endpoint = '/user/repos'
                params = {'type': repo_type, 'per_page': min(limit, 100)}
            
            # Add query parameters to endpoint
            param_str = '&'.join([f'{k}={v}' for k, v in params.items()])
            endpoint += f'?{param_str}'
            
            repos = self._make_request(endpoint)
            
            # Enhance with VFS bucket metadata
            enhanced_repos = []
            for repo in repos:
                enhanced_repo = self._enhance_repo_with_vfs_metadata(repo)
                enhanced_repos.append(enhanced_repo)
            
            return enhanced_repos
        
        except Exception as e:
            logger.error(f"❌ Failed to list repositories: {e}")
            raise
    
    def _enhance_repo_with_vfs_metadata(self, repo: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance repository data with VFS bucket metadata.
        
        Args:
            repo: Raw GitHub repository data
            
        Returns:
            Repository data enhanced with VFS metadata
        """
        enhanced = repo.copy()
        
        # VFS bucket mapping
        enhanced['vfs'] = {
            'bucket_name': f"{repo['owner']['login']}/{repo['name']}",
            'peer_id': repo['owner']['login'],  # Username as peerID for local forks
            'bucket_type': self._classify_repository(repo),
            'is_fork': repo.get('fork', False),
            'original_repo': repo.get('parent', {}).get('full_name') if repo.get('fork') else None,
            'ipfs_compatible': True,
            'storage_backend': 'github',
            'local_cache_path': str(self.cache_dir / repo['owner']['login'] / repo['name']),
            'clone_url': repo['clone_url'],
            'ssh_url': repo['ssh_url'],
            'size_mb': round(repo.get('size', 0) / 1024, 2)  # Convert KB to MB
        }
        
        # Add content classification for datasets/models
        enhanced['vfs']['content_labels'] = self._classify_content(repo)
        
        return enhanced
    
    def _classify_repository(self, repo: Dict[str, Any]) -> str:
        """
        Classify repository type for VFS bucket categorization.
        
        Args:
            repo: GitHub repository data
            
        Returns:
            Repository classification
        """
        name = repo['name'].lower()
        description = (repo.get('description') or '').lower()
        topics = repo.get('topics', [])
        
        # Dataset indicators
        dataset_indicators = ['dataset', 'data', 'corpus', 'benchmark', 'collection']
        if any(indicator in name or indicator in description for indicator in dataset_indicators):
            return 'dataset'
        if any(topic in ['dataset', 'data', 'machine-learning-dataset'] for topic in topics):
            return 'dataset'
        
        # Model indicators
        model_indicators = ['model', 'pytorch', 'tensorflow', 'transformer', 'bert', 'gpt']
        if any(indicator in name or indicator in description for indicator in model_indicators):
            return 'model'
        if any(topic in ['model', 'machine-learning', 'deep-learning', 'ai'] for topic in topics):
            return 'model'
        
        # Code repository
        return 'code'
    
    def _classify_content(self, repo: Dict[str, Any]) -> List[str]:
        """
        Generate content labels for VFS integration.
        
        Args:
            repo: GitHub repository data
            
        Returns:
            List of content labels
        """
        labels = []
        
        # Language labels
        if repo.get('language'):
            labels.append(f"lang:{repo['language'].lower()}")
        
        # Topic labels
        for topic in repo.get('topics', []):
            labels.append(f"topic:{topic}")
        
        # Size labels
        size_kb = repo.get('size', 0)
        if size_kb > 1000000:  # > 1GB
            labels.append('size:large')
        elif size_kb > 100000:  # > 100MB
            labels.append('size:medium')
        else:
            labels.append('size:small')
        
        # Activity labels
        if repo.get('updated_at'):
            from datetime import datetime, timedelta
            try:
                updated = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
                if updated > datetime.now().replace(tzinfo=updated.tzinfo) - timedelta(days=30):
                    labels.append('activity:recent')
                elif updated > datetime.now().replace(tzinfo=updated.tzinfo) - timedelta(days=365):
                    labels.append('activity:moderate')
                else:
                    labels.append('activity:old')
            except:
                pass
        
        return labels
    
    async def clone_repository(self, repo: str, local_path: Optional[str] = None, 
                             branch: str = 'main') -> Dict[str, Any]:
        """
        Clone repository locally for VFS integration.
        
        Args:
            repo: Repository name (owner/repo)
            local_path: Local path to clone to
            branch: Branch to clone
            
        Returns:
            Clone operation result
        """
        try:
            if not local_path:
                owner, name = repo.split('/')
                local_path = str(self.cache_dir / owner / name)
            
            local_path = Path(local_path)
            
            # Remove existing directory if it exists
            if local_path.exists():
                shutil.rmtree(local_path)
            
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use GitPython if available, otherwise subprocess
            if GIT_AVAILABLE:
                clone_url = f"https://github.com/{repo}.git"
                if self.token:
                    clone_url = f"https://{self.token}@github.com/{repo}.git"
                
                git_repo = git.Repo.clone_from(clone_url, local_path, branch=branch)
                
                result = {
                    'success': True,
                    'local_path': str(local_path),
                    'repo': repo,
                    'branch': branch,
                    'commit': git_repo.head.commit.hexsha,
                    'method': 'gitpython'
                }
            else:
                # Fallback to subprocess
                clone_url = f"https://github.com/{repo}.git"
                cmd = ['git', 'clone', '-b', branch, clone_url, str(local_path)]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    result = {
                        'success': True,
                        'local_path': str(local_path),
                        'repo': repo,
                        'branch': branch,
                        'method': 'subprocess'
                    }
                else:
                    raise RuntimeError(f"Git clone failed: {stderr.decode()}")
            
            # Create VFS bucket metadata
            await self._create_vfs_metadata(local_path, repo, branch)
            
            logger.info(f"✅ Cloned {repo} to {local_path}")
            return result
        
        except Exception as e:
            logger.error(f"❌ Failed to clone {repo}: {e}")
            raise
    
    async def _create_vfs_metadata(self, local_path: Path, repo: str, branch: str):
        """Create VFS metadata for cloned repository."""
        metadata = {
            'bucket_type': 'github_repo',
            'repo': repo,
            'branch': branch,
            'peer_id': repo.split('/')[0],  # Username as peerID
            'storage_backend': 'github',
            'clone_timestamp': str(asyncio.get_event_loop().time()),
            'vfs_labels': self._generate_vfs_labels(local_path)
        }
        
        metadata_file = local_path / '.ipfs_kit_metadata.json'
        metadata_file.write_text(json.dumps(metadata, indent=2))
    
    def _generate_vfs_labels(self, repo_path: Path) -> List[str]:
        """Generate VFS labels based on repository content."""
        labels = []
        
        # Check for common ML/data files
        ml_files = [
            'requirements.txt', 'environment.yml', 'Pipfile',
            'model.py', 'train.py', 'dataset.py', 'data.py',
            '*.pkl', '*.pt', '*.pth', '*.h5', '*.onnx',
            '*.csv', '*.json', '*.parquet', '*.arrow'
        ]
        
        for pattern in ml_files:
            if list(repo_path.glob(pattern)) or list(repo_path.glob(f'**/{pattern}')):
                if 'model' in pattern or 'train' in pattern or pattern.endswith(('.pt', '.pth', '.h5', '.onnx')):
                    labels.append('content:model')
                elif 'data' in pattern or pattern.endswith(('.csv', '.json', '.parquet', '.arrow')):
                    labels.append('content:dataset')
                elif pattern in ['requirements.txt', 'environment.yml']:
                    labels.append('content:code')
        
        # Check directory structure
        common_dirs = ['data', 'dataset', 'models', 'src', 'scripts', 'notebooks']
        for dir_name in common_dirs:
            if (repo_path / dir_name).exists():
                labels.append(f'structure:{dir_name}')
        
        return labels
    
    async def list_files(self, repo: str, path: str = '', branch: str = 'main') -> List[Dict[str, Any]]:
        """
        List files in repository (as VFS bucket contents).
        
        Args:
            repo: Repository name (owner/repo)
            path: Path within repository
            branch: Branch to list
            
        Returns:
            List of files with VFS metadata
        """
        try:
            endpoint = f'/repos/{repo}/contents/{path}'
            if branch != 'main':
                endpoint += f'?ref={branch}'
            
            contents = self._make_request(endpoint)
            
            # Ensure contents is a list
            if not isinstance(contents, list):
                contents = [contents]
            
            # Enhance with VFS metadata
            enhanced_files = []
            for item in contents:
                enhanced_item = item.copy()
                enhanced_item['vfs'] = {
                    'bucket': repo,
                    'path': item['path'],
                    'type': item['type'],  # file, dir
                    'size_bytes': item.get('size', 0),
                    'download_url': item.get('download_url'),
                    'git_url': item.get('git_url'),
                    'ipfs_hash': None,  # Can be populated after IPFS add
                    'peer_id': repo.split('/')[0]
                }
                enhanced_files.append(enhanced_item)
            
            return enhanced_files
        
        except Exception as e:
            logger.error(f"❌ Failed to list files in {repo}/{path}: {e}")
            raise
    
    async def upload_file(self, repo: str, local_file: str, remote_path: str,
                         message: Optional[str] = None, branch: str = 'main') -> Dict[str, Any]:
        """
        Upload file to repository.
        
        Args:
            repo: Repository name (owner/repo)
            local_file: Local file path
            remote_path: Remote path in repository
            message: Commit message
            branch: Branch to upload to
            
        Returns:
            Upload result
        """
        try:
            import base64
            
            # Read local file
            with open(local_file, 'rb') as f:
                content = f.read()
            
            # Encode content
            encoded_content = base64.b64encode(content).decode('utf-8')
            
            # Prepare commit data
            commit_data = {
                'message': message or f'Upload {os.path.basename(local_file)}',
                'content': encoded_content,
                'branch': branch
            }
            
            # Check if file exists (for updates)
            try:
                existing = self._make_request(f'/repos/{repo}/contents/{remote_path}?ref={branch}')
                commit_data['sha'] = existing['sha']
            except:
                pass  # File doesn't exist, creating new
            
            # Upload file
            result = self._make_request(f'/repos/{repo}/contents/{remote_path}', 'PUT', commit_data)
            
            logger.info(f"✅ Uploaded {local_file} to {repo}/{remote_path}")
            return result
        
        except Exception as e:
            logger.error(f"❌ Failed to upload {local_file} to {repo}: {e}")
            raise
    
    async def download_file(self, repo: str, remote_path: str, local_file: str,
                           branch: str = 'main') -> Dict[str, Any]:
        """
        Download file from repository.
        
        Args:
            repo: Repository name (owner/repo)
            remote_path: Remote path in repository
            local_file: Local file path to save
            branch: Branch to download from
            
        Returns:
            Download result
        """
        try:
            # Get file information
            endpoint = f'/repos/{repo}/contents/{remote_path}'
            if branch != 'main':
                endpoint += f'?ref={branch}'
            
            file_info = self._make_request(endpoint)
            
            if file_info['type'] != 'file':
                raise ValueError(f"Path {remote_path} is not a file")
            
            # Download file content
            if file_info.get('download_url'):
                response = requests.get(file_info['download_url'])
                response.raise_for_status()
                
                # Ensure local directory exists
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                
                # Write file
                with open(local_file, 'wb') as f:
                    f.write(response.content)
                
                result = {
                    'success': True,
                    'local_file': local_file,
                    'remote_path': remote_path,
                    'repo': repo,
                    'branch': branch,
                    'size_bytes': len(response.content)
                }
                
                logger.info(f"✅ Downloaded {repo}/{remote_path} to {local_file}")
                return result
            else:
                raise RuntimeError("No download URL available")
        
        except Exception as e:
            logger.error(f"❌ Failed to download {repo}/{remote_path}: {e}")
            raise
    
    async def get_repository_info(self, repo: str) -> Dict[str, Any]:
        """
        Get repository information with VFS metadata.
        
        Args:
            repo: Repository name (owner/repo)
            
        Returns:
            Repository information enhanced with VFS data
        """
        try:
            repo_info = self._make_request(f'/repos/{repo}')
            enhanced_info = self._enhance_repo_with_vfs_metadata(repo_info)
            return enhanced_info
        
        except Exception as e:
            logger.error(f"❌ Failed to get repository info for {repo}: {e}")
            raise
    
    async def sync_to_ipfs(self, repo: str, ipfs_client = None) -> Dict[str, Any]:
        """
        Sync repository content to IPFS for hybrid storage.
        
        Args:
            repo: Repository name (owner/repo)
            ipfs_client: IPFS client instance
            
        Returns:
            Sync result with IPFS hashes
        """
        try:
            # This would integrate with IPFS-Kit's IPFS client
            # For now, return placeholder
            result = {
                'success': True,
                'repo': repo,
                'ipfs_hash': 'QmPlaceholder...',
                'sync_timestamp': str(asyncio.get_event_loop().time()),
                'message': 'IPFS sync functionality would be implemented here'
            }
            
            logger.info(f"✅ Would sync {repo} to IPFS")
            return result
        
        except Exception as e:
            logger.error(f"❌ Failed to sync {repo} to IPFS: {e}")
            raise
    
    async def create_git_vfs_translator(self, local_repo_path: Union[str, Path]) -> Optional['GitVFSTranslator']:
        """
        Create a Git VFS translator for a local repository.
        
        Args:
            local_repo_path: Path to local Git repository
            
        Returns:
            GitVFSTranslator instance or None if not available
        """
        if not GIT_VFS_AVAILABLE:
            logger.error("Git VFS translator not available")
            return None
        
        try:
            translator = GitVFSTranslator(local_repo_path, vfs_manager=None)
            return translator
        except Exception as e:
            logger.error(f"Failed to create Git VFS translator: {e}")
            return None
    
    async def analyze_repository_git_metadata(self, repo_info: Dict[str, Any], local_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Analyze Git metadata for a GitHub repository and create VFS mapping.
        
        Args:
            repo_info: Repository information from GitHub API
            local_path: Optional local repository path
            
        Returns:
            Analysis results with VFS translation information
        """
        analysis = {
            'repository': repo_info['full_name'],
            'vfs_bucket': repo_info['name'],
            'peer_id': repo_info['owner']['login'],
            'git_analysis': {},
            'vfs_translation': {},
            'content_addressing': {}
        }
        
        try:
            # If we have a local copy, analyze Git metadata
            if local_path and local_path.exists():
                translator = await self.create_git_vfs_translator(local_path)
                if translator:
                    # Analyze Git metadata
                    analysis['git_analysis'] = translator.analyze_git_metadata()
                    
                    # Sync Git to VFS
                    sync_result = translator.sync_git_to_vfs()
                    analysis['vfs_translation']['sync_result'] = sync_result
                    
                    # Get VFS snapshots count
                    if translator.index_file.exists():
                        with open(translator.index_file, 'r') as f:
                            index_data = json.load(f)
                            analysis['vfs_translation']['snapshots_count'] = len(index_data.get('snapshots', {}))
                            analysis['vfs_translation']['content_map_size'] = len(index_data.get('content_map', {}))
                    
                    # Export VFS metadata for analysis
                    export_result = translator.export_vfs_metadata()
                    if export_result['success']:
                        analysis['vfs_translation']['export_path'] = export_result['export_path']
                        analysis['vfs_translation']['export_size'] = export_result['file_size']
            
            # Add GitHub-specific VFS metadata
            analysis['content_addressing'] = {
                'github_repo_hash': self._calculate_repo_hash(repo_info),
                'default_branch': repo_info.get('default_branch', 'main'),
                'clone_url': repo_info['clone_url'],
                'vfs_mount_point': f"/vfs/github/{repo_info['owner']['login']}/{repo_info['name']}",
                'content_type': self._detect_repo_content_type(repo_info),
                'estimated_vfs_blocks': self._estimate_vfs_blocks(repo_info)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing repository Git metadata: {e}")
            analysis['error'] = str(e)
            return analysis
    
    def _calculate_repo_hash(self, repo_info: Dict[str, Any]) -> str:
        """Calculate a content-addressable hash for the repository."""
        import hashlib
        
        # Create reproducible hash from key repository attributes
        repo_data = {
            'full_name': repo_info['full_name'],
            'created_at': repo_info['created_at'],
            'updated_at': repo_info['updated_at'],
            'default_branch': repo_info.get('default_branch', 'main'),
            'language': repo_info.get('language'),
            'size': repo_info.get('size', 0)
        }
        
        repo_string = json.dumps(repo_data, sort_keys=True)
        return hashlib.sha256(repo_string.encode()).hexdigest()[:16]
    
    def _detect_repo_content_type(self, repo_info: Dict[str, Any]) -> str:
        """Detect the type of content in the repository for VFS labeling."""
        name = repo_info['name'].lower()
        description = (repo_info.get('description') or '').lower()
        topics = [topic.lower() for topic in repo_info.get('topics', [])]
        language = (repo_info.get('language') or '').lower()
        
        # Check for ML/AI content
        ml_indicators = ['model', 'dataset', 'ml', 'ai', 'neural', 'deep-learning', 'machine-learning', 'tensorflow', 'pytorch', 'huggingface']
        if any(indicator in name or indicator in description for indicator in ml_indicators) or any(indicator in topics for indicator in ml_indicators):
            return 'ml_content'
        
        # Check for data content
        data_indicators = ['data', 'dataset', 'csv', 'json', 'parquet', 'analytics']
        if any(indicator in name or indicator in description for indicator in data_indicators) or any(indicator in topics for indicator in data_indicators):
            return 'data_content'
        
        # Check for documentation
        doc_indicators = ['docs', 'documentation', 'wiki', 'guide', 'tutorial']
        if any(indicator in name or indicator in description for indicator in doc_indicators) or any(indicator in topics for indicator in doc_indicators):
            return 'documentation'
        
        # Check for configuration
        config_indicators = ['config', 'dotfiles', 'settings', 'template']
        if any(indicator in name or indicator in description for indicator in config_indicators) or any(indicator in topics for indicator in config_indicators):
            return 'configuration'
        
        # Default to source code
        return 'source_code'
    
    def _estimate_vfs_blocks(self, repo_info: Dict[str, Any]) -> int:
        """Estimate number of VFS blocks based on repository size."""
        size_kb = repo_info.get('size', 0)  # GitHub reports size in KB
        
        # Rough estimation: assume average block size of 256KB
        # This is very approximate and would need refinement
        estimated_blocks = max(1, size_kb // 256)
        
        return estimated_blocks
    
    async def setup_vfs_translation_for_repo(self, repo_name: str, local_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Set up VFS translation layer for a GitHub repository.
        
        Args:
            repo_name: Repository name (owner/repo format)
            local_path: Optional local repository path
            
        Returns:
            Setup result information
        """
        result = {
            'repository': repo_name,
            'vfs_setup': False,
            'translation_active': False,
            'setup_details': {}
        }
        
        try:
            # Get repository information
            repo_info = self._make_request(f'/repos/{repo_name}')
            
            # Determine local path
            if not local_path:
                local_path = self.cache_dir / repo_info['owner']['login'] / repo_info['name']
            
            # Clone or update repository if needed
            if not local_path.exists():
                clone_result = await self.clone_repository(repo_name, str(local_path))
                if not clone_result['success']:
                    result['error'] = f"Failed to clone repository: {clone_result.get('error')}"
                    return result
            
            # Create Git VFS translator
            translator = await self.create_git_vfs_translator(local_path)
            if not translator:
                result['error'] = "Failed to create Git VFS translator"
                return result
            
            # Analyze and set up VFS translation
            analysis = await self.analyze_repository_git_metadata(repo_info, local_path)
            result['setup_details']['analysis'] = analysis
            
            # Sync Git metadata to VFS
            if 'git_analysis' in analysis and not analysis['git_analysis'].get('error'):
                sync_result = translator.sync_git_to_vfs()
                result['setup_details']['sync_result'] = sync_result
                result['translation_active'] = sync_result.get('snapshots_created', 0) > 0 or sync_result.get('snapshots_updated', 0) > 0
            
            # Mark VFS setup as complete
            result['vfs_setup'] = True
            result['local_path'] = str(local_path)
            result['vfs_metadata_path'] = str(translator.vfs_metadata_dir)
            
            logger.info(f"✅ VFS translation set up for {repo_name}")
            
        except Exception as e:
            logger.error(f"Error setting up VFS translation for {repo_name}: {e}")
            result['error'] = str(e)
        
        return result

# Convenience functions for CLI integration
async def github_login(token: str) -> GitHubKit:
    """Authenticate with GitHub and return kit instance."""
    kit = GitHubKit(token)
    await kit.authenticate(token)
    return kit

async def github_list_repos(user: Optional[str] = None, repo_type: str = 'owner', 
                           limit: int = 100, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """List GitHub repositories as VFS buckets."""
    kit = GitHubKit(token)
    return await kit.list_repositories(user, repo_type, limit)

async def github_clone_repo(repo: str, local_path: Optional[str] = None, 
                           branch: str = 'main', token: Optional[str] = None) -> Dict[str, Any]:
    """Clone GitHub repository locally."""
    kit = GitHubKit(token)
    return await kit.clone_repository(repo, local_path, branch)

async def github_list_files(repo: str, path: str = '', branch: str = 'main', 
                           token: Optional[str] = None) -> List[Dict[str, Any]]:
    """List files in GitHub repository."""
    kit = GitHubKit(token)
    return await kit.list_files(repo, path, branch)

if __name__ == "__main__":
    import sys
    
    async def main():
        """Example usage of GitHub kit."""
        if len(sys.argv) < 2:
            print("Usage: python github_kit.py <command> [args...]")
            print("Commands: list, clone, files")
            return
        
        command = sys.argv[1]
        
        if command == 'list':
            repos = await github_list_repos(limit=5)
            for repo in repos:
                vfs = repo['vfs']
                print(f"📁 {vfs['bucket_name']} ({vfs['bucket_type']}) - {vfs['peer_id']}")
                print(f"   Labels: {', '.join(vfs['content_labels'])}")
                print()
        
        elif command == 'clone' and len(sys.argv) > 2:
            repo = sys.argv[2]
            result = await github_clone_repo(repo)
            print(f"✅ Cloned to: {result['local_path']}")
        
        elif command == 'files' and len(sys.argv) > 2:
            repo = sys.argv[2]
            files = await github_list_files(repo)
            for file in files:
                vfs = file['vfs']
                print(f"📄 {vfs['path']} ({vfs['type']}) - {vfs['size_bytes']} bytes")
        
        else:
            print("Invalid command or missing arguments")
    
    asyncio.run(main())
