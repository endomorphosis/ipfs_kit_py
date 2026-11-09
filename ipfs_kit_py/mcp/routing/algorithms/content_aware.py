#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/algorithms/content_aware.py

"""
Content-Aware Routing Strategy.

This module provides a routing strategy that selects the optimal backend based
on the type and characteristics of the content being stored or retrieved.
"""

import logging
from typing import Dict, List, Optional, Tuple

from ..router import (
    Backend, ContentType, OperationType,
    RouteMetrics, RoutingContext, RoutingDecision, RoutingStrategy
)
from ..metrics import ContentTypeAnalyzer

logger = logging.getLogger(__name__)

# Default content type to backend mappings
DEFAULT_CONTENT_MAPPINGS = {
    ContentType.IMAGE: {
        OperationType.READ: ['IPFS', 'S3', 'STORACHA'],
        OperationType.WRITE: ['IPFS', 'S3']
    },
    ContentType.VIDEO: {
        OperationType.READ: ['IPFS', 'S3'],
        OperationType.WRITE: ['S3', 'IPFS']
    },
    ContentType.AUDIO: {
        OperationType.READ: ['IPFS', 'S3'],
        OperationType.WRITE: ['IPFS', 'S3']
    },
    ContentType.DOCUMENT: {
        OperationType.READ: ['IPFS', 'STORACHA'],
        OperationType.WRITE: ['IPFS', 'STORACHA']
    },
    ContentType.DATASET: {
        OperationType.READ: ['HUGGINGFACE', 'S3', 'FILECOIN'],
        OperationType.WRITE: ['HUGGINGFACE', 'S3', 'FILECOIN']
    },
    ContentType.MODEL: {
        OperationType.READ: ['HUGGINGFACE', 'S3'],
        OperationType.WRITE: ['HUGGINGFACE', 'S3']
    },
    ContentType.ARCHIVE: {
        OperationType.READ: ['FILECOIN', 'S3'],
        OperationType.WRITE: ['FILECOIN', 'S3']
    },
    ContentType.BINARY: {
        OperationType.READ: ['IPFS', 'S3'],
        OperationType.WRITE: ['IPFS', 'S3']
    },
    ContentType.UNKNOWN: {
        OperationType.READ: ['IPFS', 'S3', 'STORACHA'],
        OperationType.WRITE: ['IPFS', 'S3']
    }
}

# Size-based routing thresholds (in bytes)
SIZE_THRESHOLDS = {
    'small': 1024 * 1024,  # 1 MB
    'medium': 100 * 1024 * 1024,  # 100 MB
    'large': 1024 * 1024 * 1024,  # 1 GB
    'very_large': 10 * 1024 * 1024 * 1024  # 10 GB
}

# Size-specific backend preferences
SIZE_PREFERENCES = {
    'small': ['IPFS', 'S3', 'STORACHA'],
    'medium': ['IPFS', 'S3', 'STORACHA'],
    'large': ['S3', 'FILECOIN', 'IPFS'],
    'very_large': ['FILECOIN', 'S3', 'HUGGINGFACE'],
    'extreme': ['FILECOIN', 'S3']
}


class ContentAwareRouter(RoutingStrategy):
    """
    Routing strategy that selects backends based on content characteristics.
    
    This strategy considers:
    - Content type (image, video, document, etc.)
    - Content size
    - Operation type (read, write, etc.)
    """
    
    def __init__(self, content_analyzer: Optional[ContentTypeAnalyzer] = None,
                content_mappings: Optional[Dict] = None,
                size_thresholds: Optional[Dict] = None,
                size_preferences: Optional[Dict] = None):
        """
        Initialize the content-aware router.
        
        Args:
            content_analyzer: Optional content type analyzer
            content_mappings: Optional content type to backend mappings
            size_thresholds: Optional size thresholds
            size_preferences: Optional size-based preferences
        """
        self.content_analyzer = content_analyzer
        self.content_mappings = content_mappings or DEFAULT_CONTENT_MAPPINGS
        self.size_thresholds = size_thresholds or SIZE_THRESHOLDS
        self.size_preferences = size_preferences or SIZE_PREFERENCES
    
    def select_backend(self, context: RoutingContext,
                     available_backends: List[Backend],
                     metrics: Dict[Backend, RouteMetrics]) -> RoutingDecision:
        """
        Select a backend based on content characteristics.
        
        Args:
            context: Routing context
            available_backends: List of available backends
            metrics: Metrics for each backend
            
        Returns:
            RoutingDecision: The routing decision
        """
        if not available_backends:
            raise ValueError("No backends available for content-aware routing")
        
        # Determine content type
        content_type = context.content_type
        if content_type is None:
            # Try to analyze content type if analyzer is available
            if self.content_analyzer and 'content' in context.metadata:
                content = context.metadata.get('content')
                content_type = self.content_analyzer.analyze_content_type(content)
            
            # Default to unknown if still None
            if content_type is None:
                content_type = ContentType.UNKNOWN
        
        # Determine operation type
        operation = context.operation
        
        # Determine size category
        size_category = self._determine_size_category(context.content_size_bytes)
        
        # Get preferred backends based on content type and operation
        content_preferred = self._get_preferred_backends_for_content(content_type, operation)
        
        # Get preferred backends based on size
        size_preferred = self._get_preferred_backends_for_size(size_category)
        
        # Combine preferences with weighting
        ranked_backends = self._rank_backends(
            content_preferred, size_preferred, available_backends
        )
        
        # Select the best available backend
        selected_backend, score = self._select_best_backend(ranked_backends, available_backends)
        
        # Create metrics for the decision
        decision_metrics = RouteMetrics(
            content_type=content_type,
            content_size_bytes=context.content_size_bytes
        )
        
        # Add backend-specific metrics if available
        if selected_backend in metrics:
            decision_metrics = metrics[selected_backend]
        
        # Create the routing decision
        alternatives = [(b, s) for b, s in ranked_backends if b != selected_backend]
        reason = f"Selected {selected_backend} based on content type {content_type.value}, " \
                 f"operation {operation.value}, and size category {size_category}"
        
        return RoutingDecision(
            backend=selected_backend,
            score=score,
            reason=reason,
            metrics=decision_metrics,
            alternatives=alternatives,
            context=context
        )
    
    def _determine_size_category(self, size_bytes: Optional[int]) -> str:
        """
        Determine the size category for a given size in bytes.
        
        Args:
            size_bytes: Size in bytes, or None
            
        Returns:
            str: Size category (small, medium, large, very_large, extreme)
        """
        if size_bytes is None:
            return 'medium'  # Default to medium if size is unknown
        
        if size_bytes < self.size_thresholds['small']:
            return 'small'
        elif size_bytes < self.size_thresholds['medium']:
            return 'medium'
        elif size_bytes < self.size_thresholds['large']:
            return 'large'
        elif size_bytes < self.size_thresholds['very_large']:
            return 'very_large'
        else:
            return 'extreme'
    
    def _get_preferred_backends_for_content(self, 
                                         content_type: ContentType,
                                         operation: OperationType) -> List[Backend]:
        """
        Get preferred backends for a content type and operation.
        
        Args:
            content_type: Content type
            operation: Operation type
            
        Returns:
            List[Backend]: List of preferred backends in order
        """
        # Get mapping for this content type
        type_mapping = self.content_mappings.get(content_type, self.content_mappings[ContentType.UNKNOWN])
        
        # Get preferred backends for this operation
        if operation in type_mapping:
            return type_mapping[operation]
        
        # Fall back to read operation if the specific operation isn't defined
        if OperationType.READ in type_mapping:
            return type_mapping[OperationType.READ]
        
        # Default to empty list if no mapping is found
        return []
    
    def _get_preferred_backends_for_size(self, size_category: str) -> List[Backend]:
        """
        Get preferred backends for a size category.
        
        Args:
            size_category: Size category
            
        Returns:
            List[Backend]: List of preferred backends in order
        """
        return self.size_preferences.get(size_category, self.size_preferences['medium'])
    
    def _rank_backends(self, content_preferred: List[Backend],
                    size_preferred: List[Backend],
                    available_backends: List[Backend]) -> List[Tuple[Backend, float]]:
        """
        Rank backends based on content and size preferences.
        
        Args:
            content_preferred: Content-based preferred backends
            size_preferred: Size-based preferred backends
            available_backends: Available backends
            
        Returns:
            List[Tuple[Backend, float]]: Ranked backends with scores
        """
        # Initialize scores
        scores = {backend: 0.0 for backend in available_backends}
        
        # Score based on content preference (higher weight)
        for i, backend in enumerate(content_preferred):
            if backend in scores:
                # Score based on position (higher is better)
                position_score = 1.0 - (i / max(1, len(content_preferred)))
                scores[backend] += 0.7 * position_score
        
        # Score based on size preference
        for i, backend in enumerate(size_preferred):
            if backend in scores:
                # Score based on position (higher is better)
                position_score = 1.0 - (i / max(1, len(size_preferred)))
                scores[backend] += 0.3 * position_score
        
        # Create ranked list
        ranked = [(backend, score) for backend, score in scores.items()]
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        return ranked
    
    def _select_best_backend(self, ranked_backends: List[Tuple[Backend, float]],
                          available_backends: List[Backend]) -> Tuple[Backend, float]:
        """
        Select the best backend from the ranked list.
        
        Args:
            ranked_backends: Ranked backends with scores
            available_backends: Available backends
            
        Returns:
            Tuple[Backend, float]: Selected backend and its score
            
        Raises:
            ValueError: If no backend is available
        """
        # Filter to only available backends
        available_ranked = [(b, s) for b, s in ranked_backends if b in available_backends]
        
        if not available_ranked:
            # If no ranked backends are available, use the first available backend
            if available_backends:
                return available_backends[0], 0.0
            raise ValueError("No backends available for selection")
        
        # Return the highest-ranked backend
        return available_ranked[0]