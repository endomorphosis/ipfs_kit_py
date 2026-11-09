#!/usr/bin/env python3
"""
IPFS Upload Manager

Handles uploading CAR files to IPFS and managing the uploaded content.
"""

import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class IPFSUploadManager:
    """Manages uploading CAR files to IPFS."""
    
    def __init__(self, ipfs_api_url: str = "http://127.0.0.1:5001"):
        self.ipfs_api_url = ipfs_api_url.rstrip('/')
        self.base_path = Path.home() / ".ipfs_kit"
        self.cars_dir = self.base_path / "cars"
        self.uploads_log = self.base_path / "ipfs_uploads.json"
        
    def check_ipfs_connection(self) -> Dict[str, Any]:
        """Check if IPFS daemon is running and accessible."""
        try:
            # Try IPFS API
            response = requests.get(f"{self.ipfs_api_url}/api/v0/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                return {
                    'connected': True,
                    'method': 'api',
                    'version': version_info.get('Version', 'unknown'),
                    'api_url': self.ipfs_api_url
                }
        except:
            pass
        
        # Try IPFS CLI
        try:
            result = subprocess.run(['ipfs', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip().split()[-1] if result.stdout else 'unknown'
                return {
                    'connected': True,
                    'method': 'cli',
                    'version': version,
                    'api_url': None
                }
        except:
            pass
        
        return {
            'connected': False,
            'method': None,
            'error': 'IPFS daemon not accessible via API or CLI'
        }
    
    def upload_car_file_api(self, car_path: Path) -> Dict[str, Any]:
        """Upload CAR file using IPFS HTTP API."""
        try:
            with open(car_path, 'rb') as f:
                files = {'file': f}
                
                # Upload CAR file to IPFS
                response = requests.post(
                    f"{self.ipfs_api_url}/api/v0/dag/import",
                    files=files,
                    params={'pin-roots': 'true'},
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Parse response
                    lines = response.text.strip().split('\n')
                    uploaded_cids = []
                    
                    for line in lines:
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if 'Root' in data and 'Cid' in data['Root']:
                                    uploaded_cids.append(data['Root']['Cid']['/'])
                            except:
                                pass
                    
                    return {
                        'success': True,
                        'method': 'api',
                        'cids': uploaded_cids,
                        'root_cid': uploaded_cids[0] if uploaded_cids else None,
                        'response': response.text
                    }
                else:
                    return {
                        'success': False,
                        'method': 'api',
                        'error': f'Upload failed: {response.status_code} - {response.text}'
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'method': 'api',
                'error': str(e)
            }
    
    def upload_car_file_cli(self, car_path: Path) -> Dict[str, Any]:
        """Upload CAR file using IPFS CLI."""
        try:
            # Use ipfs dag import
            result = subprocess.run([
                'ipfs', 'dag', 'import', 
                '--pin-roots=true', 
                str(car_path)
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Parse output for CIDs
                uploaded_cids = []
                for line in result.stdout.split('\n'):
                    if 'imported' in line.lower() and 'root' in line.lower():
                        # Extract CID from output
                        parts = line.split()
                        for part in parts:
                            if part.startswith('ba') or part.startswith('Qm'):
                                uploaded_cids.append(part)
                                break
                
                return {
                    'success': True,
                    'method': 'cli',
                    'cids': uploaded_cids,
                    'root_cid': uploaded_cids[0] if uploaded_cids else None,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                return {
                    'success': False,
                    'method': 'cli',
                    'error': f'CLI upload failed: {result.stderr or result.stdout}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'method': 'cli',
                'error': str(e)
            }
    
    def upload_car_file(self, car_path: Path) -> Dict[str, Any]:
        """Upload CAR file to IPFS using best available method."""
        if not car_path.exists():
            return {
                'success': False,
                'error': f'CAR file not found: {car_path}'
            }
        
        # Check IPFS connection
        connection = self.check_ipfs_connection()
        if not connection['connected']:
            return {
                'success': False,
                'error': connection['error']
            }
        
        # Try upload based on available method
        if connection['method'] == 'api':
            result = self.upload_car_file_api(car_path)
        else:
            result = self.upload_car_file_cli(car_path)
        
        # Log successful upload
        if result['success']:
            self.log_upload(car_path, result)
        
        return result
    
    def log_upload(self, car_path: Path, upload_result: Dict[str, Any]) -> None:
        """Log successful upload to tracking file."""
        try:
            # Load existing log
            if self.uploads_log.exists():
                with open(self.uploads_log, 'r') as f:
                    log_data = json.load(f)
            else:
                log_data = {'uploads': []}
            
            # Add new upload
            upload_entry = {
                'car_filename': car_path.name,
                'car_path': str(car_path),
                'car_size_bytes': car_path.stat().st_size,
                'uploaded_at': datetime.now().isoformat(),
                'ipfs_cids': upload_result.get('cids', []),
                'root_cid': upload_result.get('root_cid'),
                'upload_method': upload_result.get('method'),
                'success': True
            }
            
            log_data['uploads'].append(upload_entry)
            
            # Save log
            with open(self.uploads_log, 'w') as f:
                json.dump(log_data, f, indent=2)
                
        except Exception as e:
            print(f"⚠️  Failed to log upload: {e}")
    
    def get_upload_history(self) -> List[Dict[str, Any]]:
        """Get history of uploaded CAR files."""
        try:
            if not self.uploads_log.exists():
                return []
            
            with open(self.uploads_log, 'r') as f:
                log_data = json.load(f)
            
            uploads = log_data.get('uploads', [])
            # Sort by upload time (newest first)
            uploads.sort(key=lambda x: x['uploaded_at'], reverse=True)
            return uploads
            
        except Exception as e:
            print(f"⚠️  Failed to read upload history: {e}")
            return []
    
    def verify_ipfs_content(self, cid: str) -> Dict[str, Any]:
        """Verify that content exists in IPFS."""
        try:
            # Check via API first
            try:
                response = requests.post(
                    f"{self.ipfs_api_url}/api/v0/dag/stat",
                    params={'arg': cid},
                    timeout=10
                )
                
                if response.status_code == 200:
                    stat_data = response.json()
                    return {
                        'exists': True,
                        'method': 'api',
                        'size': stat_data.get('Size', 0),
                        'num_links': stat_data.get('NumLinks', 0)
                    }
            except:
                pass
            
            # Fallback to CLI
            result = subprocess.run([
                'ipfs', 'dag', 'stat', cid
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {
                    'exists': True,
                    'method': 'cli',
                    'output': result.stdout
                }
            else:
                return {
                    'exists': False,
                    'error': result.stderr or 'Content not found'
                }
                
        except Exception as e:
            return {
                'exists': False,
                'error': str(e)
            }


def create_ipfs_upload_manager():
    """Create and return an IPFS upload manager instance."""
    return IPFSUploadManager()


if __name__ == "__main__":
    # Test IPFS upload manager
    manager = IPFSUploadManager()
    
    print("🌐 Testing IPFS Upload Manager")
    print("=" * 50)
    
    # Check IPFS connection
    connection = manager.check_ipfs_connection()
    print(f"IPFS Connection: {connection}")
    
    if connection['connected']:
        print(f"✅ IPFS available via {connection['method']}")
        print(f"   Version: {connection['version']}")
    else:
        print(f"❌ IPFS not available: {connection['error']}")
    
    # Show upload history
    history = manager.get_upload_history()
    if history:
        print(f"\n📜 Upload History ({len(history)} uploads):")
        for upload in history[:3]:  # Show last 3
            print(f"   {upload['car_filename']} -> {upload['root_cid']}")
    else:
        print("\n📜 No upload history found")
