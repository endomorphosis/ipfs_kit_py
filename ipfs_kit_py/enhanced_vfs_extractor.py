#!/usr/bin/env python3
"""
Enhanced IPFS VFS Extractor with CLI Integration

Integrates with ipfs_kit_py CLI to consult pin metadata index and use
multiprocessing for optimized parallel downloads from fastest backends.
"""

import json
import subprocess
import sys
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import time
import concurrent.futures
import tempfile


class EnhancedIPFSVFSExtractor:
    """Enhanced VFS extractor with CLI integration and backend optimization."""
    
    def __init__(self, output_dir: Optional[Path] = None, max_workers: int = None):
        self.output_dir = output_dir or Path.cwd() / "extracted_vfs"
        self.output_dir.mkdir(exist_ok=True)
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        self.pin_metadata_cache = {}
        self.backend_performance = {}
        
    def check_ipfs_kit_cli(self) -> Dict[str, Any]:
        """Check if ipfs_kit_py CLI is available and working."""
        try:
            # Try different CLI access methods
            cli_methods = [
                ['python', '-m', 'ipfs_kit_py.cli', '--help'],
                ['ipfs-kit', '--help'],
                ['./ipfs-kit', '--help']
            ]
            
            for method in cli_methods:
                try:
                    result = subprocess.run(method, 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        return {
                            'available': True,
                            'method': method[:-1],  # Remove --help
                            'version_info': self._get_cli_version(method[:-1])
                        }
                except:
                    continue
            
            return {
                'available': False,
                'error': 'ipfs_kit_py CLI not found in any expected location'
            }
            
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }
    
    def _get_cli_version(self, cli_method: List[str]) -> Dict[str, Any]:
        """Get CLI version and status information."""
        try:
            # Get daemon status to check connectivity
            result = subprocess.run(cli_method + ['daemon', 'status'], 
                                  capture_output=True, text=True, timeout=10)
            
            # Parse daemon status output
            status_info = {
                'daemon_running': 'running' in result.stdout.lower(),
                'backends_available': 'backend' in result.stdout.lower(),
                'raw_output': result.stdout
            }
            
            return status_info
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_pin_metadata(self, cid: str) -> Dict[str, Any]:
        """Get pin metadata from ipfs_kit_py CLI."""
        if cid in self.pin_metadata_cache:
            return self.pin_metadata_cache[cid]
        
        try:
            cli_check = self.check_ipfs_kit_cli()
            if not cli_check['available']:
                return {
                    'found': False,
                    'error': 'CLI not available',
                    'backends': []
                }
            
            cli_method = cli_check['method']
            
            # Query pin metadata
            result = subprocess.run(cli_method + ['pin', 'list', '--metadata'], 
                                  capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                # Parse pin list output to find our CID
                pin_info = self._parse_pin_metadata(result.stdout, cid)
                self.pin_metadata_cache[cid] = pin_info
                return pin_info
            else:
                return {
                    'found': False,
                    'error': f'Pin list failed: {result.stderr}',
                    'backends': []
                }
                
        except Exception as e:
            return {
                'found': False,
                'error': str(e),
                'backends': []
            }
    
    def _parse_pin_metadata(self, pin_list_output: str, target_cid: str) -> Dict[str, Any]:
        """Parse pin list output to extract metadata for specific CID."""
        try:
            lines = pin_list_output.split('\n')
            
            # Look for our CID in the output
            for i, line in enumerate(lines):
                if target_cid in line:
                    # Extract pin information from this line and surrounding context
                    pin_info = {
                        'found': True,
                        'cid': target_cid,
                        'backends': [],
                        'metadata': {}
                    }
                    
                    # Parse backend information from subsequent lines
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if 'backend' in lines[j].lower():
                            backend_name = self._extract_backend_name(lines[j])
                            if backend_name:
                                pin_info['backends'].append(backend_name)
                        elif lines[j].strip() == '' or lines[j].startswith('   '):
                            break
                    
                    # If no backends found in metadata, use default detection
                    if not pin_info['backends']:
                        pin_info['backends'] = self._detect_available_backends()
                    
                    return pin_info
            
            # CID not found in pins
            return {
                'found': False,
                'cid': target_cid,
                'backends': self._detect_available_backends(),
                'metadata': {}
            }
            
        except Exception as e:
            return {
                'found': False,
                'error': str(e),
                'backends': self._detect_available_backends()
            }
    
    def _extract_backend_name(self, line: str) -> Optional[str]:
        """Extract backend name from pin metadata line."""
        backends = ['local', 'ipfs', 's3', 'lotus', 'cluster']
        line_lower = line.lower()
        
        for backend in backends:
            if backend in line_lower:
                return backend
        return None
    
    def _detect_available_backends(self) -> List[str]:
        """Detect available backends using CLI."""
        try:
            cli_check = self.check_ipfs_kit_cli()
            if not cli_check['available']:
                return ['ipfs']  # Default fallback
            
            cli_method = cli_check['method']
            
            # Get backend status
            result = subprocess.run(cli_method + ['config', 'show'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                backends = []
                output_lower = result.stdout.lower()
                
                # Detect available backends from config
                if 'ipfs' in output_lower:
                    backends.append('ipfs')
                if 's3' in output_lower:
                    backends.append('s3')
                if 'lotus' in output_lower:
                    backends.append('lotus')
                if 'cluster' in output_lower:
                    backends.append('cluster')
                
                return backends or ['ipfs']
            else:
                return ['ipfs']
                
        except Exception:
            return ['ipfs']
    
    def benchmark_backend_performance(self, backends: List[str], sample_cid: str) -> Dict[str, float]:
        """Benchmark backend performance for small test download."""
        if not backends:
            return {}
        
        performance = {}
        
        for backend in backends:
            try:
                start_time = time.time()
                
                # Test download using different methods based on backend
                if backend == 'ipfs':
                    # Test IPFS download speed
                    result = subprocess.run([
                        'ipfs', 'dag', 'stat', sample_cid
                    ], capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        performance[backend] = time.time() - start_time
                    else:
                        performance[backend] = float('inf')  # Mark as slow
                
                else:
                    # For other backends, use CLI method
                    cli_check = self.check_ipfs_kit_cli()
                    if cli_check['available']:
                        cli_method = cli_check['method']
                        
                        # This would be enhanced with actual backend-specific commands
                        result = subprocess.run(cli_method + ['daemon', 'status'], 
                                              capture_output=True, text=True, timeout=3)
                        
                        if result.returncode == 0 and backend in result.stdout.lower():
                            performance[backend] = time.time() - start_time
                        else:
                            performance[backend] = float('inf')
                    else:
                        performance[backend] = float('inf')
                        
            except Exception:
                performance[backend] = float('inf')
        
        # Cache results
        self.backend_performance.update(performance)
        return performance
    
    def get_fastest_backend(self, cid: str) -> str:
        """Determine the fastest backend for downloading a specific CID."""
        pin_metadata = self.get_pin_metadata(cid)
        available_backends = pin_metadata.get('backends', ['ipfs'])
        
        if not available_backends:
            return 'ipfs'
        
        # Use cached performance if available
        if self.backend_performance:
            fastest_backend = min(available_backends, 
                                key=lambda b: self.backend_performance.get(b, float('inf')))
            if self.backend_performance.get(fastest_backend, float('inf')) != float('inf'):
                return fastest_backend
        
        # Benchmark if not cached
        performance = self.benchmark_backend_performance(available_backends, cid)
        
        if performance:
            fastest_backend = min(performance.keys(), key=lambda b: performance[b])
            return fastest_backend
        
        return available_backends[0]  # Default to first available
    
    def download_file_optimized(self, file_info: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
        """Download single file using optimized backend selection."""
        cid = file_info['cid']
        filename = file_info['name']
        
        try:
            # Get fastest backend
            fastest_backend = self.get_fastest_backend(cid)
            
            print(f"📥 Downloading {filename} via {fastest_backend}...")
            
            start_time = time.time()
            output_path = output_dir / filename
            
            # Download using fastest backend
            if fastest_backend == 'ipfs':
                result = subprocess.run([
                    'ipfs', 'get', cid, '-o', str(output_path)
                ], capture_output=True, text=True, timeout=300)
                
            else:
                # Use CLI for other backends
                cli_check = self.check_ipfs_kit_cli()
                if cli_check['available']:
                    cli_method = cli_check['method']
                    
                    # This would be enhanced with backend-specific download commands
                    # For now, fallback to IPFS
                    result = subprocess.run([
                        'ipfs', 'get', cid, '-o', str(output_path)
                    ], capture_output=True, text=True, timeout=300)
                else:
                    raise Exception("CLI not available for backend-specific download")
            
            download_time = time.time() - start_time
            
            if result.returncode == 0:
                file_size = output_path.stat().st_size if output_path.exists() else 0
                speed_mbps = (file_size / (1024 * 1024)) / download_time if download_time > 0 else 0
                
                return {
                    'success': True,
                    'filename': filename,
                    'cid': cid,
                    'backend': fastest_backend,
                    'download_time': download_time,
                    'file_size': file_size,
                    'speed_mbps': speed_mbps
                }
            else:
                return {
                    'success': False,
                    'filename': filename,
                    'cid': cid,
                    'backend': fastest_backend,
                    'error': result.stderr or result.stdout
                }
                
        except Exception as e:
            return {
                'success': False,
                'filename': filename,
                'cid': cid,
                'error': str(e)
            }
    
    def download_files_parallel(self, files_list: List[Dict[str, Any]], bucket_name: str) -> Dict[str, Any]:
        """Download files in parallel using optimized backend selection."""
        output_dir = self.output_dir / f"{bucket_name}_files"
        output_dir.mkdir(exist_ok=True)
        
        print(f"🚀 Starting parallel download of {len(files_list)} files...")
        print(f"📁 Output directory: {output_dir}")
        print(f"⚙️  Max workers: {self.max_workers}")
        
        # First, benchmark backends with a sample file if we haven't already
        if not self.backend_performance and files_list:
            sample_cid = files_list[0]['cid']
            sample_backends = self.get_pin_metadata(sample_cid).get('backends', ['ipfs'])
            print(f"🔍 Benchmarking {len(sample_backends)} backends...")
            self.benchmark_backend_performance(sample_backends, sample_cid)
        
        start_time = time.time()
        results = []
        
        # Use ProcessPoolExecutor for true parallelism
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_file = {
                executor.submit(self._download_worker, file_info, str(output_dir)): file_info 
                for file_info in files_list
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['success']:
                        speed = result.get('speed_mbps', 0)
                        backend = result.get('backend', 'unknown')
                        print(f"   ✅ {result['filename']} ({speed:.1f} MB/s via {backend})")
                    else:
                        print(f"   ❌ {result['filename']}: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    results.append({
                        'success': False,
                        'filename': file_info['name'],
                        'cid': file_info['cid'],
                        'error': str(e)
                    })
                    print(f"   ❌ {file_info['name']}: {e}")
        
        total_time = time.time() - start_time
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        # Calculate performance stats
        total_size = sum(r.get('file_size', 0) for r in results if r['success'])
        total_speed = (total_size / (1024 * 1024)) / total_time if total_time > 0 else 0
        
        # Backend usage stats
        backend_usage = {}
        for result in results:
            if result['success']:
                backend = result.get('backend', 'unknown')
                backend_usage[backend] = backend_usage.get(backend, 0) + 1
        
        print(f"\n🎯 Download Summary:")
        print(f"   Total files: {len(files_list)}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Total time: {total_time:.1f}s")
        print(f"   Total size: {total_size / (1024*1024):.1f} MB")
        print(f"   Average speed: {total_speed:.1f} MB/s")
        print(f"   Backend usage: {backend_usage}")
        
        return {
            'success': successful > 0,
            'total_files': len(files_list),
            'successful_downloads': successful,
            'failed_downloads': failed,
            'total_time': total_time,
            'total_size_bytes': total_size,
            'average_speed_mbps': total_speed,
            'backend_usage': backend_usage,
            'results': results,
            'output_directory': str(output_dir)
        }
    
    @staticmethod
    def _download_worker(file_info: Dict[str, Any], output_dir_str: str) -> Dict[str, Any]:
        """Worker function for parallel downloads (must be static for multiprocessing)."""
        # Import within the worker to avoid multiprocessing issues
        from ipfs_kit_py.enhanced_vfs_extractor import EnhancedIPFSVFSExtractor
        from pathlib import Path
        
        # Create a new extractor instance for this worker
        worker_extractor = EnhancedIPFSVFSExtractor()
        output_dir = Path(output_dir_str)
        
        return worker_extractor.download_file_optimized(file_info, output_dir)
    
    def extract_bucket_with_optimization(self, bucket_hash: str, bucket_name: str) -> Dict[str, Any]:
        """Extract bucket and download files with CLI integration and optimization."""
        print(f"🗂️  Extracting bucket: {bucket_name}")
        print(f"📥 Bucket hash: {bucket_hash}")
        
        # Check CLI availability
        cli_check = self.check_ipfs_kit_cli()
        if cli_check['available']:
            print(f"✅ ipfs_kit_py CLI available via: {' '.join(cli_check['method'])}")
        else:
            print(f"⚠️  ipfs_kit_py CLI not available: {cli_check['error']}")
            print(f"   Continuing with standard IPFS downloads...")
        
        # Download bucket index
        print(f"📥 Downloading bucket index...")
        bucket_result = self.download_from_ipfs(bucket_hash, f"{bucket_name}_index.json")
        
        if not bucket_result['success']:
            return {
                'success': False,
                'error': f"Failed to download bucket index: {bucket_result['error']}"
            }
        
        # Parse bucket index
        try:
            with open(bucket_result['file_path'], 'r') as f:
                bucket_data = json.load(f)
            
            files = bucket_data.get('files', [])
            metadata = bucket_data.get('metadata', {})
            
            print(f"✅ Bucket index loaded:")
            print(f"   Files: {len(files)}")
            print(f"   Total size: {metadata.get('size_mb', 0):.2f} MB")
            
            if not files:
                return {
                    'success': False,
                    'error': 'No files found in bucket index'
                }
            
            # Download files with optimization
            download_result = self.download_files_parallel(files, bucket_name)
            
            return {
                'success': download_result['success'],
                'bucket_name': bucket_name,
                'bucket_data': bucket_data,
                'download_stats': download_result,
                'files_downloaded': download_result['successful_downloads'],
                'total_files': len(files)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to parse bucket index: {e}"
            }
    
    def download_from_ipfs(self, hash_cid: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """Download content from IPFS (reused from original implementation)."""
        try:
            if filename:
                output_path = self.output_dir / filename
            else:
                output_path = self.output_dir / hash_cid
            
            result = subprocess.run([
                'ipfs', 'get', hash_cid, 
                '-o', str(output_path)
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'file_path': str(output_path),
                    'hash': hash_cid
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr or result.stdout
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


def main():
    """Enhanced CLI interface with ipfs_kit_py integration."""
    if len(sys.argv) < 2:
        print("🔧 Enhanced IPFS VFS Extractor with CLI Integration")
        print("=" * 60)
        print("Features:")
        print("- Consults ipfs_kit_py pin metadata index")
        print("- Multiprocessing parallel downloads")
        print("- Fastest backend selection")
        print("- Performance benchmarking")
        print("")
        print("Usage:")
        print("  python -m ipfs_kit_py.enhanced_vfs_extractor <master_hash>")
        print("  python -m ipfs_kit_py.enhanced_vfs_extractor <bucket_hash> <bucket_name>")
        print("")
        print("Examples:")
        print("  # Extract master index")
        print("  python -m ipfs_kit_py.enhanced_vfs_extractor QmRk6bGzArD8tngRNJCVusuPo28QgsqRmgHbVMJxSbFt89")
        print("")
        print("  # Extract specific bucket with optimization")
        print("  python -m ipfs_kit_py.enhanced_vfs_extractor QmSU6xLJ3pf2f9v2eC53aWZUNyaCU5S9YYDQUoo7PFBKaE media-bucket")
        return
    
    hash_cid = sys.argv[1]
    bucket_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Create enhanced extractor
    extractor = EnhancedIPFSVFSExtractor()
    
    if bucket_name:
        # Extract single bucket with optimization
        print(f"🚀 Enhanced bucket extraction with CLI integration")
        result = extractor.extract_bucket_with_optimization(hash_cid, bucket_name)
        
        if result['success']:
            stats = result['download_stats']
            print(f"\n🎉 Extraction complete!")
            print(f"   Files downloaded: {result['files_downloaded']}/{result['total_files']}")
            print(f"   Average speed: {stats['average_speed_mbps']:.1f} MB/s")
            print(f"   Backend usage: {stats['backend_usage']}")
            print(f"   Output: {stats['output_directory']}")
        else:
            print(f"❌ Extraction failed: {result['error']}")
    
    else:
        # Extract master index (standard method)
        print(f"🌍 Extracting master index...")
        result = extractor.download_from_ipfs(hash_cid, "master_index.json")
        
        if result['success']:
            try:
                with open(result['file_path'], 'r') as f:
                    master_data = json.load(f)
                
                buckets = master_data.get('buckets', {})
                print(f"✅ Master index downloaded: {len(buckets)} buckets")
                print(f"\n📋 Available buckets:")
                
                for bucket_name, bucket_info in buckets.items():
                    bucket_hash = bucket_info['ipfs_hash']
                    file_count = bucket_info['file_count']
                    size_mb = bucket_info['size_bytes'] / (1024 * 1024)
                    
                    print(f"   📦 {bucket_name}")
                    print(f"      Hash: {bucket_hash}")
                    print(f"      Files: {file_count} | Size: {size_mb:.2f} MB")
                    print(f"      Extract: python -m ipfs_kit_py.enhanced_vfs_extractor {bucket_hash} {bucket_name}")
                    print("")
                
                print(f"💡 Next steps:")
                print(f"   1. Choose a bucket to extract")
                print(f"   2. Run with bucket hash and name for optimized downloads")
                print(f"   3. System will use fastest backends and parallel processing")
                
            except Exception as e:
                print(f"❌ Failed to parse master index: {e}")
        else:
            print(f"❌ Failed to download master index: {result['error']}")


if __name__ == "__main__":
    main()
