"""
Content Type Analyzer for Optimized Data Routing

This module analyzes content types and characteristics to make 
intelligent routing decisions for different kinds of content.
"""

import os
import mimetypes
import logging
from typing import Dict, Any, Optional, Set, List

from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class ContentTypeAnalyzer:
    """
    Analyzes content to determine optimal storage strategies.
    
    This component examines content type, structure, and characteristics
    to inform intelligent routing decisions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the content type analyzer.
        
        Args:
            config: Analyzer configuration
        """
        self.config = config or {}
        
        # Content type mappings: regex pattern -> backend preference
        self.content_type_mappings = self.config.get("content_type_mappings", {})
        
        # Content type scoring: backend -> content type -> score
        self.content_type_scores = self.config.get("content_type_scores", {})
        
        # Default scores for general categories
        self.default_category_scores = {
            "image": {
                StorageBackendType.IPFS.value: 0.9,
                StorageBackendType.S3.value: 0.8,
                StorageBackendType.STORACHA.value: 0.7,
                StorageBackendType.FILECOIN.value: 0.5,
                StorageBackendType.HUGGINGFACE.value: 0.6,
                StorageBackendType.LASSIE.value: 0.7,
            },
            "video": {
                StorageBackendType.IPFS.value: 0.7,
                StorageBackendType.S3.value: 0.9,
                StorageBackendType.STORACHA.value: 0.6,
                StorageBackendType.FILECOIN.value: 0.8,
                StorageBackendType.HUGGINGFACE.value: 0.4,
                StorageBackendType.LASSIE.value: 0.6,
            },
            "audio": {
                StorageBackendType.IPFS.value: 0.8,
                StorageBackendType.S3.value: 0.8,
                StorageBackendType.STORACHA.value: 0.7,
                StorageBackendType.FILECOIN.value: 0.7,
                StorageBackendType.HUGGINGFACE.value: 0.5,
                StorageBackendType.LASSIE.value: 0.6,
            },
            "document": {
                StorageBackendType.IPFS.value: 0.9,
                StorageBackendType.S3.value: 0.8,
                StorageBackendType.STORACHA.value: 0.8,
                StorageBackendType.FILECOIN.value: 0.6,
                StorageBackendType.HUGGINGFACE.value: 0.7,
                StorageBackendType.LASSIE.value: 0.8,
            },
            "model": {
                StorageBackendType.IPFS.value: 0.7,
                StorageBackendType.S3.value: 0.8,
                StorageBackendType.STORACHA.value: 0.6,
                StorageBackendType.FILECOIN.value: 0.5,
                StorageBackendType.HUGGINGFACE.value: 0.9,
                StorageBackendType.LASSIE.value: 0.6,
            },
            "archive": {
                StorageBackendType.IPFS.value: 0.7,
                StorageBackendType.S3.value: 0.8,
                StorageBackendType.STORACHA.value: 0.7,
                StorageBackendType.FILECOIN.value: 0.9,
                StorageBackendType.HUGGINGFACE.value: 0.5,
                StorageBackendType.LASSIE.value: 0.6,
            },
            "text": {
                StorageBackendType.IPFS.value: 0.9,
                StorageBackendType.S3.value: 0.7,
                StorageBackendType.STORACHA.value: 0.8,
                StorageBackendType.FILECOIN.value: 0.6,
                StorageBackendType.HUGGINGFACE.value: 0.8,
                StorageBackendType.LASSIE.value: 0.7,
            },
            "dataset": {
                StorageBackendType.IPFS.value: 0.7,
                StorageBackendType.S3.value: 0.8,
                StorageBackendType.STORACHA.value: 0.7,
                StorageBackendType.FILECOIN.value: 0.8,
                StorageBackendType.HUGGINGFACE.value: 0.9,
                StorageBackendType.LASSIE.value: 0.6,
            },
            "application": {
                StorageBackendType.IPFS.value: 0.8,
                StorageBackendType.S3.value: 0.8,
                StorageBackendType.STORACHA.value: 0.7,
                StorageBackendType.FILECOIN.value: 0.6,
                StorageBackendType.HUGGINGFACE.value: 0.6,
                StorageBackendType.LASSIE.value: 0.7,
            },
            "other": {
                StorageBackendType.IPFS.value: 0.8,
                StorageBackendType.S3.value: 0.8,
                StorageBackendType.STORACHA.value: 0.7,
                StorageBackendType.FILECOIN.value: 0.7,
                StorageBackendType.HUGGINGFACE.value: 0.6,
                StorageBackendType.LASSIE.value: 0.7,
            },
        }
        
        # Initialize MIME type to category mapping
        self.mime_to_category = {
            # Images
            "image/": "image",
            # Videos
            "video/": "video",
            # Audio
            "audio/": "audio",
            # Documents
            "application/pdf": "document",
            "application/msword": "document",
            "application/vnd.openxmlformats-officedocument": "document",
            "application/vnd.ms-excel": "document",
            "application/vnd.ms-powerpoint": "document",
            "application/rtf": "document",
            "text/plain": "document",
            "text/html": "document",
            "text/markdown": "document",
            # Archives
            "application/zip": "archive",
            "application/x-rar-compressed": "archive",
            "application/x-tar": "archive",
            "application/gzip": "archive",
            "application/x-7z-compressed": "archive",
            # Models
            "application/octet-stream": "model",
            "application/x-hdf5": "model",
            "application/x-pytorch": "model",
            "application/x-tensorflow": "model",
            # Datasets
            "application/json": "dataset",
            "text/csv": "dataset",
            "application/x-parquet": "dataset",
            "application/x-arrow": "dataset",
            # Applications
            "application/x-executable": "application",
            "application/x-msdos-program": "application",
            "application/java-archive": "application",
            # Text
            "text/": "text",
        }
        
        # Initialize extension to category mapping
        self.extension_to_category = {
            # Images
            ".jpg": "image",
            ".jpeg": "image",
            ".png": "image",
            ".gif": "image",
            ".svg": "image",
            ".webp": "image",
            ".bmp": "image",
            ".tiff": "image",
            ".tif": "image",
            # Videos
            ".mp4": "video",
            ".avi": "video",
            ".mov": "video",
            ".mkv": "video",
            ".webm": "video",
            ".flv": "video",
            ".wmv": "video",
            ".m4v": "video",
            # Audio
            ".mp3": "audio",
            ".wav": "audio",
            ".ogg": "audio",
            ".flac": "audio",
            ".aac": "audio",
            ".m4a": "audio",
            ".wma": "audio",
            # Documents
            ".pdf": "document",
            ".doc": "document",
            ".docx": "document",
            ".xls": "document",
            ".xlsx": "document",
            ".ppt": "document",
            ".pptx": "document",
            ".odt": "document",
            ".rtf": "document",
            # Archives
            ".zip": "archive",
            ".rar": "archive",
            ".tar": "archive",
            ".gz": "archive",
            ".7z": "archive",
            ".bz2": "archive",
            ".xz": "archive",
            # Models
            ".pt": "model",
            ".pth": "model",
            ".h5": "model",
            ".pb": "model",
            ".onnx": "model",
            ".tflite": "model",
            ".mlmodel": "model",
            ".joblib": "model",
            ".pickle": "model",
            ".pkl": "model",
            # Datasets
            ".json": "dataset",
            ".csv": "dataset",
            ".parquet": "dataset",
            ".arrow": "dataset",
            ".jsonl": "dataset",
            ".tsv": "dataset",
            ".feather": "dataset",
            # Applications
            ".exe": "application",
            ".dll": "application",
            ".so": "application",
            ".jar": "application",
            ".py": "application",
            ".js": "application",
            ".php": "application",
            ".rb": "application",
            # Text
            ".txt": "text",
            ".md": "text",
            ".rst": "text",
            ".log": "text",
        }
        
        # Ensure mimetypes are initialized
        mimetypes.init()
    
    def get_content_category(self, content_type: Optional[str] = None, filename: Optional[str] = None) -> str:
        """
        Determine the content category based on MIME type and/or filename.
        
        Args:
            content_type: MIME type
            filename: Filename
            
        Returns:
            Content category
        """
        # Try to determine from content type first
        if content_type:
            for mime_prefix, category in self.mime_to_category.items():
                if content_type.startswith(mime_prefix):
                    return category
        
        # If no match or no content type, try filename
        if filename:
            # Get extension
            ext = os.path.splitext(filename)[1].lower()
            
            # Check direct extension mapping
            if ext in self.extension_to_category:
                return self.extension_to_category[ext]
            
            # If extension not in our map but we have a filename, try to get mime type
            if not content_type:
                guessed_type = mimetypes.guess_type(filename)[0]
                if guessed_type:
                    for mime_prefix, category in self.mime_to_category.items():
                        if guessed_type.startswith(mime_prefix):
                            return category
        
        # If all else fails, return "other"
        return "other"
    
    def get_content_type_score(self, backend_type: StorageBackendType, content_type: Optional[str] = None, filename: Optional[str] = None) -> float:
        """
        Calculate a content type score for a backend.
        
        Args:
            backend_type: Backend type
            content_type: MIME type
            filename: Filename
            
        Returns:
            Content type score (higher is better)
        """
        backend_name = backend_type.value
        
        # Determine content category
        category = self.get_content_category(content_type, filename)
        
        # Check if we have a specific score for this content type
        if backend_name in self.content_type_scores:
            backend_scores = self.content_type_scores[backend_name]
            
            # Try exact content type match
            if content_type and content_type in backend_scores:
                return backend_scores[content_type]
            
            # Try category match
            if category in backend_scores:
                return backend_scores[category]
        
        # Fall back to default category scores
        if category in self.default_category_scores:
            category_scores = self.default_category_scores[category]
            if backend_name in category_scores:
                return category_scores[backend_name]
        
        # If no match, return neutral score
        return 0.5
    
    def get_recommended_backends(self, content_type: Optional[str] = None, filename: Optional[str] = None, 
                                threshold: float = 0.7) -> List[StorageBackendType]:
        """
        Get recommended backends for a content type.
        
        Args:
            content_type: MIME type
            filename: Filename
            threshold: Minimum score threshold
            
        Returns:
            List of recommended backends
        """
        category = self.get_content_category(content_type, filename)
        recommendations = []
        
        if category in self.default_category_scores:
            category_scores = self.default_category_scores[category]
            
            for backend_name, score in category_scores.items():
                if score >= threshold:
                    try:
                        backend = StorageBackendType.from_string(backend_name)
                        recommendations.append(backend)
                    except ValueError:
                        # Invalid backend name
                        pass
        
        return recommendations
    
    def get_size_recommendations(self, size: int) -> Dict[str, List[StorageBackendType]]:
        """
        Get backend recommendations based on content size.
        
        Args:
            size: Content size in bytes
            
        Returns:
            Dictionary mapping size categories to recommended backends
        """
        recommendations = {
            "small": [],    # < 1MB
            "medium": [],   # 1MB - 100MB
            "large": [],    # 100MB - 1GB
            "very_large": []  # > 1GB
        }
        
        # Small files (< 1MB)
        if size < 1024 * 1024:
            recommendations["small"] = [
                StorageBackendType.IPFS,
                StorageBackendType.S3,
                StorageBackendType.STORACHA
            ]
        
        # Medium files (1MB - 100MB)
        elif size < 100 * 1024 * 1024:
            recommendations["medium"] = [
                StorageBackendType.IPFS,
                StorageBackendType.S3,
                StorageBackendType.STORACHA,
                StorageBackendType.HUGGINGFACE
            ]
        
        # Large files (100MB - 1GB)
        elif size < 1024 * 1024 * 1024:
            recommendations["large"] = [
                StorageBackendType.S3,
                StorageBackendType.FILECOIN,
                StorageBackendType.LASSIE
            ]
        
        # Very large files (> 1GB)
        else:
            recommendations["very_large"] = [
                StorageBackendType.FILECOIN,
                StorageBackendType.S3
            ]
        
        return recommendations


# Singleton instance
_instance = None

def get_instance(config: Optional[Dict[str, Any]] = None) -> ContentTypeAnalyzer:
    """
    Get or create the singleton content type analyzer instance.
    
    Args:
        config: Optional analyzer configuration
        
    Returns:
        ContentTypeAnalyzer instance
    """
    global _instance
    if _instance is None:
        _instance = ContentTypeAnalyzer(config)
    return _instance