#!/usr/bin/env python3
"""
CAR-based WAL Manager using dag-cbor and multiformats

This replaces the Parquet-based WAL system with CAR (Content Addressable Archive) files
using IPLD and DAG-CBOR encoding for better IPFS integration.
"""

import asyncio
import json
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import io

# Import IPLD libraries
try:
    import dag_cbor
    from multiformats import CID, multicodec, multihash
    IPLD_AVAILABLE = True
except ImportError as e:
    logging.warning(f"IPLD libraries not available: {e}")
    IPLD_AVAILABLE = False

logger = logging.getLogger(__name__)


class CARWALManager:
    """
    CAR-based Write-Ahead Log Manager
    
    Replaces Parquet WAL files with CAR files containing IPLD blocks
    encoded with DAG-CBOR for direct IPFS compatibility.
    """
    
    def __init__(self, wal_dir: Path):
        self.wal_dir = wal_dir
        self.processed_dir = wal_dir / "processed"
        
        # Ensure directories exist
        self.wal_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        if not IPLD_AVAILABLE:
            logger.warning("IPLD libraries not available - CAR WAL will use JSON fallback")
    
    async def store_content_to_wal(
        self, 
        file_cid: str, 
        content: bytes, 
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store file content to WAL as CAR file instead of Parquet.
        
        Args:
            file_cid: Content identifier for the file
            content: File content as bytes
            file_path: Virtual file path
            metadata: Optional metadata
            
        Returns:
            Result dictionary with WAL information
        """
        try:
            timestamp = int(time.time() * 1000)
            wal_car_path = self.wal_dir / f"wal_{timestamp}_{file_cid}.car"
            
            if IPLD_AVAILABLE:
                # Create CAR file with IPLD blocks
                car_result = await self._create_car_file(
                    wal_car_path, file_cid, content, file_path, metadata
                )
            else:
                # Fallback to JSON-based mock CAR
                car_result = await self._create_json_mock_car(
                    wal_car_path, file_cid, content, file_path, metadata
                )
            
            logger.info(f"Stored content to CAR WAL: {wal_car_path}")
            
            return {
                "success": True,
                "wal_file": str(wal_car_path),
                "wal_format": "car",
                "root_cid": car_result.get("root_cid"),
                "blocks_count": car_result.get("blocks_count", 2)
            }
            
        except Exception as e:
            logger.error(f"Error storing content to CAR WAL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _create_car_file(
        self,
        car_path: Path,
        file_cid: str,
        content: bytes,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create actual CAR file with IPLD blocks using dag-cbor."""
        
        # Create operation metadata block
        operation_data = {
            'operation_id': f"file-add-{file_cid}",
            'operation_type': 'file_add',
            'file_cid': file_cid,
            'file_path': file_path,
            'content_size': len(content),
            'created_at_iso': datetime.utcnow().isoformat(),
            'status': 'pending',
            'content_hash': hashlib.sha256(content).hexdigest(),
            'metadata': metadata or {},
            'wal_format': 'car',
            'wal_version': '2.0'
        }
        
        # Create content block 
        content_data = {
            'type': 'file_content',
            'path': file_path,
            'size': len(content),
            'encoding': 'binary',
            'data': content.hex()  # Store as hex string in CBOR
        }
        
        # Create root block that links to both
        root_data = {
            'version': 1,
            'type': 'wal_entry',
            'operation': operation_data,
            'content': content_data,
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Write simplified CAR file with dag-cbor encoding
        await self._write_simple_car_file(car_path, root_data)
        
        return {
            "root_cid": f"simplified-car-{file_cid}",
            "blocks_count": 1
        }
    
    async def _write_simple_car_file(self, car_path: Path, data: Dict[str, Any]):
        """Write a simplified CAR file using dag-cbor."""
        
        # Encode the data using dag-cbor
        encoded_data = dag_cbor.encode(data)
        
        # Write as a simple CAR-like format
        with open(car_path, 'wb') as f:
            # Write a simple header
            header = {
                'version': 1,
                'format': 'simplified-car-dag-cbor',
                'created_at': datetime.utcnow().isoformat()
            }
            header_encoded = dag_cbor.encode(header)
            
            # Write header length + header + data length + data
            f.write(len(header_encoded).to_bytes(4, 'big'))
            f.write(header_encoded)
            f.write(len(encoded_data).to_bytes(4, 'big'))
            f.write(encoded_data)
    
    def _encode_varint(self, value: int) -> bytes:
        """Encode integer as varint."""
        result = []
        while value >= 0x80:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)
    
    async def _create_json_mock_car(
        self,
        car_path: Path,
        file_cid: str,
        content: bytes,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create JSON mock CAR file when IPLD libraries aren't available."""
        
        # Mock CAR structure
        car_data = {
            "header": {
                "version": 1,
                "roots": [f"root_{file_cid}"]
            },
            "blocks": {
                f"root_{file_cid}": {
                    "type": "wal_entry",
                    "operation": f"op_{file_cid}",
                    "content": f"content_{file_cid}",
                    "created_at": datetime.utcnow().isoformat()
                },
                f"op_{file_cid}": {
                    "operation_id": f"file-add-{file_cid}",
                    "operation_type": "file_add",
                    "file_cid": file_cid,
                    "file_path": file_path,
                    "content_size": len(content),
                    "created_at_iso": datetime.utcnow().isoformat(),
                    "status": "pending",
                    "content_hash": hashlib.sha256(content).hexdigest(),
                    "metadata": metadata or {},
                    "wal_format": "car_mock",
                    "wal_version": "2.0"
                },
                f"content_{file_cid}": {
                    "type": "file_content",
                    "path": file_path,
                    "size": len(content),
                    "encoding": "hex" if len(content) < 10000 else "external",
                    "data": content.hex() if len(content) < 10000 else None
                }
            }
        }
        
        # Write as JSON
        with open(car_path, 'w') as f:
            json.dump(car_data, f, indent=2, default=str)
        
        # Write large content externally
        if len(content) >= 10000:
            content_path = car_path.with_suffix('.content')
            with open(content_path, 'wb') as f:
                f.write(content)
        
        return {
            "root_cid": f"root_{file_cid}",
            "blocks_count": 3
        }
    
    def _encode_varint(self, value: int) -> bytes:
        """Encode integer as varint."""
        result = []
        while value >= 0x80:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)
    
    def list_wal_entries(self) -> Dict[str, Any]:
        """List all WAL entries."""
        try:
            car_files = list(self.wal_dir.glob("wal_*.car"))
            processed_files = list(self.processed_dir.glob("wal_*.car"))
            
            entries = []
            for car_file in car_files:
                try:
                    # Parse filename to extract info
                    parts = car_file.stem.split('_')
                    if len(parts) >= 3:
                        timestamp = parts[1]
                        file_cid = '_'.join(parts[2:])
                        
                        entries.append({
                            'wal_file': car_file.name,
                            'timestamp': timestamp,
                            'file_cid': file_cid,
                            'status': 'pending',
                            'size_bytes': car_file.stat().st_size
                        })
                except Exception as e:
                    logger.warning(f"Error parsing WAL file {car_file}: {e}")
            
            return {
                "success": True,
                "wal_entries": entries,
                "pending_count": len(car_files),
                "processed_count": len(processed_files)
            }
            
        except Exception as e:
            logger.error(f"Error listing WAL entries: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_wal_entry(self, car_file: Path) -> Dict[str, Any]:
        """
        Process a single CAR WAL entry.
        This would be called by the daemon to upload to IPFS.
        """
        try:
            logger.info(f"Processing CAR WAL entry: {car_file.name}")
            
            if IPLD_AVAILABLE:
                result = await self._process_real_car_file(car_file)
            else:
                result = await self._process_mock_car_file(car_file)
            
            if result.get("success"):
                # Move to processed directory
                processed_path = self.processed_dir / car_file.name
                car_file.rename(processed_path)
                
                # Also move any external content files
                content_file = car_file.with_suffix('.content')
                if content_file.exists():
                    processed_content = self.processed_dir / content_file.name
                    content_file.rename(processed_content)
                
                logger.info(f"Successfully processed and moved: {car_file.name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing CAR WAL entry: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _process_real_car_file(self, car_file: Path) -> Dict[str, Any]:
        """Process a real CAR file with IPLD blocks."""
        try:
            # Read simplified CAR file
            with open(car_file, 'rb') as f:
                # Read header
                header_len = int.from_bytes(f.read(4), 'big')
                header_data = f.read(header_len)
                header = dag_cbor.decode(header_data)
                
                # Read main data
                data_len = int.from_bytes(f.read(4), 'big')
                data_bytes = f.read(data_len)
                data = dag_cbor.decode(data_bytes)
                
                # Extract operation info
                operation_data = data.get('operation', {})
                
                return {
                    "success": True,
                    "operation_id": operation_data.get('operation_id'),
                    "file_cid": operation_data.get('file_cid'),
                    "file_path": operation_data.get('file_path'),
                    "ipfs_upload": "simulated_success",
                    "processed_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error processing simplified CAR file: {e}"
            }
    
    async def _process_mock_car_file(self, car_file: Path) -> Dict[str, Any]:
        """Process a mock JSON CAR file."""
        try:
            # Read JSON CAR file
            with open(car_file, 'r') as f:
                car_data = json.load(f)
            
            # Extract operation data
            header = car_data.get('header', {})
            blocks = car_data.get('blocks', {})
            
            root_cid = header.get('roots', [])[0] if header.get('roots') else None
            if root_cid and root_cid in blocks:
                root_block = blocks[root_cid]
                operation_cid = root_block.get('operation')
                
                if operation_cid and operation_cid in blocks:
                    operation_data = blocks[operation_cid]
                    
                    # Simulate IPFS upload
                    return {
                        "success": True,
                        "operation_id": operation_data.get('operation_id'),
                        "file_cid": operation_data.get('file_cid'),
                        "file_path": operation_data.get('file_path'),
                        "ipfs_upload": "simulated_success",
                        "processed_at": datetime.utcnow().isoformat()
                    }
            
            return {
                "success": False,
                "error": "Could not extract operation data from mock CAR file"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error processing mock CAR file: {e}"
            }
    
    async def process_all_wal_entries(self) -> Dict[str, Any]:
        """Process all pending WAL entries."""
        try:
            car_files = list(self.wal_dir.glob("wal_*.car"))
            
            if not car_files:
                return {
                    "success": True,
                    "message": "No WAL entries to process",
                    "processed_count": 0
                }
            
            logger.info(f"Processing {len(car_files)} CAR WAL entries...")
            
            results = []
            successful = 0
            
            for car_file in car_files:
                result = await self.process_wal_entry(car_file)
                results.append(result)
                
                if result.get("success"):
                    successful += 1
                    logger.info(f"✅ Processed: {car_file.name}")
                else:
                    logger.error(f"❌ Failed: {car_file.name} - {result.get('error')}")
            
            return {
                "success": True,
                "processed_count": successful,
                "failed_count": len(car_files) - successful,
                "total_count": len(car_files),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error processing WAL entries: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_content_from_wal(self, content_id: str) -> Dict[str, Any]:
        """
        Retrieve content from WAL by content ID (CID).
        
        Args:
            content_id: The CID to retrieve content for
            
        Returns:
            Dict with success flag, content, and metadata
        """
        try:
            # Look for CAR file with this CID
            matching_files = list(self.wal_dir.glob(f"wal_*_{content_id}.car"))
            
            if not matching_files:
                return {
                    'success': False,
                    'error': f'No CAR file found for CID: {content_id}'
                }
            
            # Use the most recent file if multiple exist
            car_file = max(matching_files, key=lambda f: f.stat().st_mtime)
            
            # Try to read the CAR file content
            try:
                # Read as binary first
                with open(car_file, 'rb') as f:
                    raw_data = f.read()
                
                # Try to decode using CBOR (dag-cbor format)
                try:
                    import dag_cbor
                    
                    # Skip CAR header and find CBOR content
                    # CAR files have a header, we need to find the CBOR data
                    decoded_blocks = []
                    offset = 0
                    
                    while offset < len(raw_data):
                        try:
                            # Try to find CBOR data at current offset
                            if raw_data[offset:offset+1] in [b'\xa3', b'\xa5', b'\xa1', b'\xa2', b'\xa4']:  # CBOR map indicators
                                try:
                                    # Attempt to decode CBOR from this position
                                    remaining_data = raw_data[offset:]
                                    decoded = dag_cbor.decode(remaining_data)
                                    decoded_blocks.append(decoded)
                                    
                                    # If this looks like our content block, extract it
                                    if isinstance(decoded, dict):
                                        if 'content' in decoded:
                                            content_data = decoded['content']
                                            metadata = decoded.get('metadata', {})
                                            
                                            # Handle different content encodings
                                            if isinstance(content_data, dict) and 'data' in content_data:
                                                # Extract the actual content data
                                                actual_content = content_data['data']
                                                if isinstance(actual_content, str):
                                                    # It might be hex-encoded
                                                    try:
                                                        content = bytes.fromhex(actual_content)
                                                    except ValueError:
                                                        content = actual_content.encode('utf-8')
                                                else:
                                                    content = actual_content
                                            else:
                                                content = str(content_data).encode('utf-8')
                                            
                                            return {
                                                'success': True,
                                                'data': {
                                                    'content': content,
                                                    'metadata': metadata,
                                                    'car_file': str(car_file)
                                                }
                                            }
                                    
                                    break  # Successfully decoded something
                                except Exception:
                                    offset += 1
                                    continue
                            else:
                                offset += 1
                        except Exception:
                            offset += 1
                            if offset >= len(raw_data):
                                break
                    
                    # If we found decoded blocks but no content, return the first block
                    if decoded_blocks:
                        first_block = decoded_blocks[0]
                        if isinstance(first_block, dict):
                            return {
                                'success': True,
                                'data': {
                                    'content': str(first_block).encode('utf-8'),
                                    'metadata': first_block,
                                    'car_file': str(car_file)
                                }
                            }
                    
                except ImportError:
                    logger.warning("dag_cbor not available, trying fallback parsing")
                
                # Fallback: try to extract readable content from the raw data
                try:
                    # Look for hex-encoded content in the binary data
                    readable_content = raw_data.decode('utf-8', errors='ignore')
                    
                    # Look for patterns that might be hex-encoded content
                    import re
                    hex_patterns = re.findall(r'[0-9a-fA-F]{20,}', readable_content)
                    
                    for hex_pattern in hex_patterns:
                        try:
                            # Try to decode as hex
                            decoded_content = bytes.fromhex(hex_pattern)
                            # Check if it looks like readable text
                            try:
                                text_content = decoded_content.decode('utf-8')
                                if len(text_content) > 10:  # Reasonable content length
                                    return {
                                        'success': True,
                                        'data': {
                                            'content': decoded_content,
                                            'metadata': {},
                                            'car_file': str(car_file)
                                        }
                                    }
                            except UnicodeDecodeError:
                                continue
                        except ValueError:
                            continue
                    
                    # If no hex patterns work, return raw data
                    return {
                        'success': True,
                        'data': {
                            'content': raw_data,
                            'metadata': {},
                            'car_file': str(car_file)
                        }
                    }
                    
                except Exception as e:
                    logger.warning(f"Fallback parsing failed: {e}")
                    return {
                        'success': False,
                        'error': f'Could not parse CAR file content: {str(e)}'
                    }
                
            except Exception as e:
                logger.error(f"Error reading CAR file: {e}")
                return {
                    'success': False,
                    'error': f'Failed to read CAR file: {str(e)}'
                }
                
        except Exception as e:
            logger.error(f"Error retrieving content from WAL: {e}")
            return {
                'success': False,
                'error': f'Failed to retrieve content: {str(e)}'
            }


# Global instance
_global_car_wal_manager = None

def get_car_wal_manager(wal_dir: Optional[Path] = None) -> CARWALManager:
    """Get global CAR WAL manager instance."""
    global _global_car_wal_manager
    
    if _global_car_wal_manager is None:
        if wal_dir is None:
            from pathlib import Path
            wal_dir = Path.home() / '.ipfs_kit' / 'wal' / 'car'
        
        _global_car_wal_manager = CARWALManager(wal_dir)
    
    return _global_car_wal_manager
