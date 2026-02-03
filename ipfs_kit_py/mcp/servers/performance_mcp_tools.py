"""
Performance MCP Tools for IPFS Kit

This module provides MCP server tools for performance optimization:
- Cache management and statistics
- Batch operation execution
- Performance metrics and monitoring
- Bottleneck detection
- Resource usage tracking

Part of Phase 9: Performance Optimization
"""

import logging
from typing import Dict, List, Optional, Any, Callable

# Import performance modules
try:
    from ipfs_kit_py.cache_manager import CacheManager
    from ipfs_kit_py.batch_operations import BatchProcessor, TransactionBatch
    from ipfs_kit_py.performance_monitor import PerformanceMonitor
except ImportError:
    from cache_manager import CacheManager
    from batch_operations import BatchProcessor, TransactionBatch
    from performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)

# Global instances (initialized when tools are registered)
_cache_manager = None
_batch_processor = None
_performance_monitor = None


def initialize_performance_tools(
    cache_config: Optional[Dict] = None,
    batch_config: Optional[Dict] = None,
    monitor_config: Optional[Dict] = None
):
    """
    Initialize performance optimization components
    
    Args:
        cache_config: Cache manager configuration
        batch_config: Batch processor configuration
        monitor_config: Performance monitor configuration
    """
    global _cache_manager, _batch_processor, _performance_monitor
    
    cache_config = cache_config or {}
    batch_config = batch_config or {}
    monitor_config = monitor_config or {}
    
    _cache_manager = CacheManager(**cache_config)
    _batch_processor = BatchProcessor(**batch_config)
    _performance_monitor = PerformanceMonitor(**monitor_config)
    
    logger.info("Performance tools initialized")


def get_cache_manager() -> CacheManager:
    """Get or create cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        initialize_performance_tools()
    return _cache_manager


def get_batch_processor() -> BatchProcessor:
    """Get or create batch processor instance"""
    global _batch_processor
    if _batch_processor is None:
        initialize_performance_tools()
    return _batch_processor


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        initialize_performance_tools()
    return _performance_monitor


def performance_get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics
    
    Returns:
        Dictionary with cache statistics
    """
    try:
        cache = get_cache_manager()
        stats = cache.get_statistics()
        
        return {
            'success': True,
            'statistics': stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {'success': False, 'error': str(e)}


def performance_clear_cache(tier: str = 'all') -> Dict[str, Any]:
    """
    Clear cache
    
    Args:
        tier: Cache tier to clear ('memory', 'disk', 'all')
    
    Returns:
        Success status
    """
    try:
        cache = get_cache_manager()
        cache.clear(tier=tier)
        
        return {
            'success': True,
            'tier': tier,
            'message': f'Cache cleared: {tier}'
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return {'success': False, 'error': str(e)}


def performance_invalidate_cache(pattern: str) -> Dict[str, Any]:
    """
    Invalidate cache entries matching pattern
    
    Args:
        pattern: Pattern to match (supports * wildcard)
    
    Returns:
        Number of entries invalidated
    """
    try:
        cache = get_cache_manager()
        cache.invalidate_pattern(pattern)
        stats = cache.get_statistics()
        
        return {
            'success': True,
            'pattern': pattern,
            'invalidations': stats['invalidations'],
            'message': f"Invalidated cache entries matching '{pattern}'"
        }
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        return {'success': False, 'error': str(e)}


def performance_get_metrics(
    operation_name: Optional[str] = None,
    timeframe: str = '1h'
) -> Dict[str, Any]:
    """
    Get performance metrics
    
    Args:
        operation_name: Filter by operation name (None = all)
        timeframe: Time window ('1h', '24h', '7d', 'all')
    
    Returns:
        Performance metrics
    """
    try:
        monitor = get_performance_monitor()
        metrics = monitor.get_metrics(
            operation_name=operation_name,
            timeframe=timeframe
        )
        
        return {
            'success': True,
            'metrics': metrics
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return {'success': False, 'error': str(e)}


def performance_get_bottlenecks(
    cpu_threshold: float = 80.0,
    memory_threshold: float = 80.0,
    slow_operation_factor: float = 2.0
) -> Dict[str, Any]:
    """
    Detect performance bottlenecks
    
    Args:
        cpu_threshold: CPU usage threshold percentage
        memory_threshold: Memory usage threshold percentage
        slow_operation_factor: Multiplier for slow operation detection
    
    Returns:
        List of identified bottlenecks
    """
    try:
        monitor = get_performance_monitor()
        bottlenecks = monitor.detect_bottlenecks(
            cpu_threshold=cpu_threshold,
            memory_threshold=memory_threshold,
            slow_operation_factor=slow_operation_factor
        )
        
        bottleneck_list = [
            {
                'type': b.bottleneck_type,
                'severity': b.severity,
                'description': b.description,
                'metric_value': b.metric_value,
                'threshold': b.threshold,
                'recommendation': b.recommendation
            }
            for b in bottlenecks
        ]
        
        return {
            'success': True,
            'count': len(bottlenecks),
            'bottlenecks': bottleneck_list
        }
    except Exception as e:
        logger.error(f"Error detecting bottlenecks: {e}")
        return {'success': False, 'error': str(e)}


def performance_get_resource_usage() -> Dict[str, Any]:
    """
    Get current resource usage
    
    Returns:
        Resource usage metrics
    """
    try:
        monitor = get_performance_monitor()
        usage = monitor.get_resource_usage()
        
        if 'error' in usage:
            return {
                'success': False,
                'error': usage['error']
            }
        
        return {
            'success': True,
            'usage': usage
        }
    except Exception as e:
        logger.error(f"Error getting resource usage: {e}")
        return {'success': False, 'error': str(e)}


def performance_set_baseline(operation_name: str) -> Dict[str, Any]:
    """
    Set performance baseline for regression detection
    
    Args:
        operation_name: Operation to set baseline for
    
    Returns:
        Success status
    """
    try:
        monitor = get_performance_monitor()
        monitor.set_baseline(operation_name)
        
        return {
            'success': True,
            'operation_name': operation_name,
            'message': f"Baseline set for '{operation_name}'"
        }
    except Exception as e:
        logger.error(f"Error setting baseline: {e}")
        return {'success': False, 'error': str(e)}


def performance_start_operation(operation_name: str) -> Dict[str, Any]:
    """
    Start timing an operation
    
    Args:
        operation_name: Name of the operation
    
    Returns:
        Operation ID for tracking
    """
    try:
        monitor = get_performance_monitor()
        op_id = monitor.start_operation(operation_name)
        
        return {
            'success': True,
            'operation_id': op_id,
            'operation_name': operation_name
        }
    except Exception as e:
        logger.error(f"Error starting operation: {e}")
        return {'success': False, 'error': str(e)}


def performance_end_operation(
    operation_id: str,
    success: bool = True,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    End timing an operation
    
    Args:
        operation_id: ID from start_operation
        success: Whether operation succeeded
        error: Optional error message
    
    Returns:
        Success status
    """
    try:
        monitor = get_performance_monitor()
        monitor.end_operation(operation_id, success=success, error=error)
        
        return {
            'success': True,
            'operation_id': operation_id,
            'operation_success': success
        }
    except Exception as e:
        logger.error(f"Error ending operation: {e}")
        return {'success': False, 'error': str(e)}


def performance_get_monitor_stats() -> Dict[str, Any]:
    """
    Get performance monitor statistics
    
    Returns:
        Monitor statistics
    """
    try:
        monitor = get_performance_monitor()
        stats = monitor.get_statistics()
        
        return {
            'success': True,
            'statistics': stats
        }
    except Exception as e:
        logger.error(f"Error getting monitor stats: {e}")
        return {'success': False, 'error': str(e)}


def performance_get_batch_stats() -> Dict[str, Any]:
    """
    Get batch processor statistics
    
    Returns:
        Batch statistics
    """
    try:
        processor = get_batch_processor()
        stats = processor.get_statistics()
        
        return {
            'success': True,
            'statistics': stats
        }
    except Exception as e:
        logger.error(f"Error getting batch stats: {e}")
        return {'success': False, 'error': str(e)}


def performance_reset_cache_stats() -> Dict[str, Any]:
    """
    Reset cache statistics
    
    Returns:
        Success status
    """
    try:
        cache = get_cache_manager()
        cache.reset_statistics()
        
        return {
            'success': True,
            'message': 'Cache statistics reset'
        }
    except Exception as e:
        logger.error(f"Error resetting cache stats: {e}")
        return {'success': False, 'error': str(e)}


def performance_get_summary() -> Dict[str, Any]:
    """
    Get comprehensive performance summary
    
    Returns:
        Summary of all performance components
    """
    try:
        cache = get_cache_manager()
        monitor = get_performance_monitor()
        processor = get_batch_processor()
        
        cache_stats = cache.get_statistics()
        monitor_stats = monitor.get_statistics()
        batch_stats = processor.get_statistics()
        resource_usage = monitor.get_resource_usage()
        
        return {
            'success': True,
            'cache': cache_stats,
            'monitor': monitor_stats,
            'batch': batch_stats,
            'resources': resource_usage
        }
    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        return {'success': False, 'error': str(e)}


# Tool registration for MCP server
PERFORMANCE_TOOLS = {
    'performance_get_cache_stats': performance_get_cache_stats,
    'performance_clear_cache': performance_clear_cache,
    'performance_invalidate_cache': performance_invalidate_cache,
    'performance_get_metrics': performance_get_metrics,
    'performance_get_bottlenecks': performance_get_bottlenecks,
    'performance_get_resource_usage': performance_get_resource_usage,
    'performance_set_baseline': performance_set_baseline,
    'performance_start_operation': performance_start_operation,
    'performance_end_operation': performance_end_operation,
    'performance_get_monitor_stats': performance_get_monitor_stats,
    'performance_get_batch_stats': performance_get_batch_stats,
    'performance_reset_cache_stats': performance_reset_cache_stats,
    'performance_get_summary': performance_get_summary,
}
