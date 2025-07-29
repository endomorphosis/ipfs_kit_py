#!/usr/bin/env python3
"""
IPFS VFS Index Extractor

Tool for recipients to extract and use VFS indexes from IPFS.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class IPFSVFSExtractor:
    """Extract and process VFS indexes from IPFS."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path.cwd() / "extracted_vfs"
        self.output_dir.mkdir(exist_ok=True)
    
    def check_ipfs(self) -> bool:
        """Check if IPFS is available."""
        try:
            result = subprocess.run(['ipfs', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def download_from_ipfs(self, hash_cid: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """Download content from IPFS."""
        try:
            if filename:
                output_path = self.output_dir / filename
            else:
                output_path = self.output_dir / hash_cid
            
            # Download using IPFS
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
    
    def extract_master_index(self, master_hash: str) -> Dict[str, Any]:
        """Extract master VFS index."""
        if not self.check_ipfs():
            return {
                'success': False,
                'error': 'IPFS not available'
            }
        
        print(f"📥 Downloading master index: {master_hash}")
        
        # Download master index
        result = self.download_from_ipfs(master_hash, "master_index.json")
        
        if not result['success']:
            return {
                'success': False,
                'error': f"Failed to download master index: {result['error']}"
            }
        
        # Parse master index
        try:
            with open(result['file_path'], 'r') as f:
                master_data = json.load(f)
            
            buckets = master_data.get('buckets', {})
            summary = master_data.get('summary', {})
            
            print(f"✅ Master index downloaded:")
            print(f"   Buckets: {len(buckets)}")
            print(f"   Total files: {summary.get('total_files', 0)}")
            print(f"   Total size: {summary.get('total_size_mb', 0):.2f} MB")
            
            return {
                'success': True,
                'master_data': master_data,
                'buckets': buckets,
                'file_path': result['file_path']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to parse master index: {e}"
            }
    
    def extract_bucket_index(self, bucket_hash: str, bucket_name: Optional[str] = None) -> Dict[str, Any]:
        """Extract individual bucket index."""
        filename = f"{bucket_name}_index.json" if bucket_name else None
        
        print(f"📥 Downloading bucket index: {bucket_hash}")
        
        # Download bucket index
        result = self.download_from_ipfs(bucket_hash, filename)
        
        if not result['success']:
            return {
                'success': False,
                'error': f"Failed to download bucket index: {result['error']}"
            }
        
        # Parse bucket index
        try:
            with open(result['file_path'], 'r') as f:
                bucket_data = json.load(f)
            
            files = bucket_data.get('files', [])
            metadata = bucket_data.get('metadata', {})
            bucket_name = bucket_data.get('bucket_name', 'unknown')
            
            print(f"✅ Bucket index downloaded: {bucket_name}")
            print(f"   Files: {len(files)}")
            print(f"   Total size: {metadata.get('size_mb', 0):.2f} MB")
            
            return {
                'success': True,
                'bucket_data': bucket_data,
                'files': files,
                'bucket_name': bucket_name,
                'file_path': result['file_path']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to parse bucket index: {e}"
            }
    
    def list_files_for_download(self, bucket_index_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List files available for download from bucket index."""
        if not bucket_index_result['success']:
            return []
        
        files = bucket_index_result['files']
        download_list = []
        
        print(f"\n📋 Files available for download:")
        print(f"   Bucket: {bucket_index_result['bucket_name']}")
        print("")
        
        for i, file_info in enumerate(files, 1):
            name = file_info['name']
            cid = file_info['cid']
            size_mb = file_info['size_bytes'] / (1024 * 1024)
            mime_type = file_info.get('mime_type', 'unknown')
            
            print(f"   {i}. {name}")
            print(f"      CID: {cid}")
            print(f"      Size: {size_mb:.2f} MB")
            print(f"      Type: {mime_type}")
            print(f"      Download: ipfs get {cid}")
            print("")
            
            download_list.append({
                'name': name,
                'cid': cid,
                'size_bytes': file_info['size_bytes'],
                'mime_type': mime_type
            })
        
        return download_list
    
    def generate_download_scripts(self, download_list: List[Dict[str, Any]], bucket_name: str) -> Dict[str, str]:
        """Generate download scripts for parallel downloading."""
        
        # Bash script for parallel downloads
        bash_script = f"""#!/bin/bash
# Parallel download script for {bucket_name}
# Generated by IPFS VFS Extractor

echo "🚀 Downloading {len(download_list)} files from {bucket_name}..."

# Create output directory
mkdir -p "{bucket_name}_files"
cd "{bucket_name}_files"

# Download files in parallel
"""
        
        for file_info in download_list:
            name = file_info['name']
            cid = file_info['cid']
            bash_script += f"""
echo "📥 Downloading {name}..."
ipfs get {cid} -o "{name}" &
"""
        
        bash_script += """
# Wait for all downloads to complete
wait

echo "✅ All downloads complete!"
echo "📁 Files saved in $(pwd)"
ls -lh
"""
        
        # Python script for parallel downloads
        python_script = f"""#!/usr/bin/env python3
# Python parallel download script for {bucket_name}
# Generated by IPFS VFS Extractor

import subprocess
import concurrent.futures
import os
from pathlib import Path

def download_file(file_info):
    name = file_info['name']
    cid = file_info['cid']
    
    print(f"📥 Downloading {{name}}...")
    
    try:
        result = subprocess.run([
            'ipfs', 'get', cid, '-o', name
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ Downloaded {{name}}")
            return {{'success': True, 'name': name}}
        else:
            print(f"❌ Failed to download {{name}}: {{result.stderr}}")
            return {{'success': False, 'name': name, 'error': result.stderr}}
            
    except Exception as e:
        print(f"❌ Error downloading {{name}}: {{e}}")
        return {{'success': False, 'name': name, 'error': str(e)}}

def main():
    # File list
    files = {download_list}
    
    # Create output directory
    Path("{bucket_name}_files").mkdir(exist_ok=True)
    os.chdir("{bucket_name}_files")
    
    print(f"🚀 Downloading {{len(files)}} files from {bucket_name}...")
    
    # Download files in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(download_file, file_info) for file_info in files]
        
        results = []
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    # Summary
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    print(f"\\n🎯 Download Summary:")
    print(f"   Successful: {{successful}}")
    print(f"   Failed: {{failed}}")
    print(f"   Total: {{len(results)}}")
    
    if failed > 0:
        print(f"\\n❌ Failed downloads:")
        for r in results:
            if not r['success']:
                print(f"   {{r['name']}}: {{r.get('error', 'Unknown error')}}")

if __name__ == "__main__":
    main()
"""
        
        return {
            'bash_script': bash_script,
            'python_script': python_script
        }
    
    def save_download_scripts(self, scripts: Dict[str, str], bucket_name: str) -> Dict[str, str]:
        """Save download scripts to files."""
        bash_path = self.output_dir / f"download_{bucket_name}.sh"
        python_path = self.output_dir / f"download_{bucket_name}.py"
        
        # Save bash script
        with open(bash_path, 'w') as f:
            f.write(scripts['bash_script'])
        bash_path.chmod(0o755)  # Make executable
        
        # Save python script
        with open(python_path, 'w') as f:
            f.write(scripts['python_script'])
        python_path.chmod(0o755)  # Make executable
        
        return {
            'bash_script_path': str(bash_path),
            'python_script_path': str(python_path)
        }


def main():
    """CLI interface for VFS extraction."""
    if len(sys.argv) < 2:
        print("🔧 IPFS VFS Index Extractor")
        print("=" * 40)
        print("Usage:")
        print("  python ipfs_vfs_extractor.py <master_hash>")
        print("  python ipfs_vfs_extractor.py <bucket_hash> [bucket_name]")
        print("")
        print("Examples:")
        print("  # Extract master index and all buckets")
        print("  python ipfs_vfs_extractor.py QmRk6bGzArD8tngRNJCVusuPo28QgsqRmgHbVMJxSbFt89")
        print("")
        print("  # Extract specific bucket")
        print("  python ipfs_vfs_extractor.py QmSU6xLJ3pf2f9v2eC53aWZUNyaCU5S9YYDQUoo7PFBKaE media-bucket")
        return
    
    hash_cid = sys.argv[1]
    bucket_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    extractor = IPFSVFSExtractor()
    
    if bucket_name:
        # Extract single bucket
        print(f"🗂️  Extracting bucket index: {bucket_name}")
        result = extractor.extract_bucket_index(hash_cid, bucket_name)
        
        if result['success']:
            download_list = extractor.list_files_for_download(result)
            
            if download_list:
                scripts = extractor.generate_download_scripts(download_list, bucket_name)
                script_paths = extractor.save_download_scripts(scripts, bucket_name)
                
                print(f"📜 Download scripts generated:")
                print(f"   Bash: {script_paths['bash_script_path']}")
                print(f"   Python: {script_paths['python_script_path']}")
                print(f"\n🚀 Run scripts to download all files in parallel!")
        else:
            print(f"❌ Failed: {result['error']}")
    
    else:
        # Extract master index
        print(f"🌍 Extracting master index...")
        master_result = extractor.extract_master_index(hash_cid)
        
        if master_result['success']:
            buckets = master_result['buckets']
            
            print(f"\n📋 Available buckets:")
            for bucket_name, bucket_info in buckets.items():
                bucket_hash = bucket_info['ipfs_hash']
                file_count = bucket_info['file_count']
                size_mb = bucket_info['size_bytes'] / (1024 * 1024)
                
                print(f"   📦 {bucket_name}")
                print(f"      Hash: {bucket_hash}")
                print(f"      Files: {file_count} | Size: {size_mb:.2f} MB")
                print(f"      Extract: python ipfs_vfs_extractor.py {bucket_hash} {bucket_name}")
                print("")
            
            print(f"💡 Next steps:")
            print(f"   1. Choose a bucket to extract")
            print(f"   2. Run: python ipfs_vfs_extractor.py <bucket_hash> <bucket_name>")
            print(f"   3. Use generated scripts for parallel downloads")
        else:
            print(f"❌ Failed: {master_result['error']}")


if __name__ == "__main__":
    main()
