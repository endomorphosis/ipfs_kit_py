"""
Batch Operations Module for IPFS Kit

This module provides efficient bulk processing capabilities:
- Batch operation management
- Parallel/sequential execution
- Progress tracking and callbacks
- Transaction batching
- Queue management
- Error handling and rollback

Part of Phase 9: Performance Optimization
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Callable, List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


class OperationStatus(Enum):
    """Status of a batch operation"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Operation:
    """Represents a batch operation"""
    id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: OperationStatus = OperationStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def duration(self) -> float:
        """Get operation duration in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


@dataclass
class BatchResult:
    """Result of batch execution"""
    total_operations: int
    successful: int
    failed: int
    skipped: int
    total_duration: float
    operations: List[Operation]
    
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_operations == 0:
            return 0.0
        return (self.successful / self.total_operations) * 100


class BatchProcessor:
    """
    Batch operation processor with parallel execution support
    
    Enables efficient bulk processing of operations with:
    - Parallel or sequential execution
    - Progress callbacks
    - Error handling
    - Transaction support
    """
    
    def __init__(
        self,
        max_batch_size: int = 100,
        max_workers: int = 4,
        use_processes: bool = False,
        fail_fast: bool = False
    ):
        """
        Initialize batch processor
        
        Args:
            max_batch_size: Maximum operations per batch
            max_workers: Maximum parallel workers
            use_processes: Use processes instead of threads
            fail_fast: Stop on first error
        """
        self.max_batch_size = max_batch_size
        self.max_workers = max_workers
        self.use_processes = use_processes
        self.fail_fast = fail_fast
        
        self.operations: List[Operation] = []
        self.operation_counter = 0
        self.lock = Lock()
        
        logger.info(f"BatchProcessor initialized (max_batch={max_batch_size}, workers={max_workers})")
    
    def add_operation(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> str:
        """
        Add operation to batch
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Operation ID
        """
        with self.lock:
            if len(self.operations) >= self.max_batch_size:
                raise ValueError(f"Batch is full (max {self.max_batch_size} operations)")
            
            op_id = f"op_{self.operation_counter}"
            self.operation_counter += 1
            
            operation = Operation(
                id=op_id,
                func=func,
                args=args,
                kwargs=kwargs
            )
            
            self.operations.append(operation)
            logger.debug(f"Added operation {op_id}")
            
            return op_id
    
    def execute_batch(
        self,
        parallel: bool = True,
        max_workers: Optional[int] = None
    ) -> BatchResult:
        """
        Execute all batched operations
        
        Args:
            parallel: Execute operations in parallel
            max_workers: Override max workers for this execution
            
        Returns:
            BatchResult with execution details
        """
        if not self.operations:
            logger.warning("No operations to execute")
            return BatchResult(
                total_operations=0,
                successful=0,
                failed=0,
                skipped=0,
                total_duration=0.0,
                operations=[]
            )
        
        start_time = time.time()
        workers = max_workers or self.max_workers
        
        logger.info(f"Executing {len(self.operations)} operations (parallel={parallel})")
        
        if parallel:
            result = self._execute_parallel(workers)
        else:
            result = self._execute_sequential()
        
        total_duration = time.time() - start_time
        
        # Count results
        successful = sum(1 for op in self.operations if op.status == OperationStatus.SUCCESS)
        failed = sum(1 for op in self.operations if op.status == OperationStatus.FAILED)
        skipped = sum(1 for op in self.operations if op.status == OperationStatus.SKIPPED)
        
        batch_result = BatchResult(
            total_operations=len(self.operations),
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_duration=total_duration,
            operations=self.operations.copy()
        )
        
        logger.info(
            f"Batch completed: {successful} successful, {failed} failed, "
            f"{skipped} skipped in {total_duration:.2f}s"
        )
        
        return batch_result
    
    def _execute_sequential(self) -> None:
        """Execute operations sequentially"""
        for operation in self.operations:
            if self.fail_fast and any(
                op.status == OperationStatus.FAILED for op in self.operations
            ):
                operation.status = OperationStatus.SKIPPED
                continue
            
            self._execute_single(operation)
    
    def _execute_parallel(self, max_workers: int) -> None:
        """Execute operations in parallel"""
        executor_class = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        
        with executor_class(max_workers=max_workers) as executor:
            # Submit all operations
            future_to_op = {
                executor.submit(self._execute_single_wrapper, op): op
                for op in self.operations
            }
            
            # Collect results
            for future in as_completed(future_to_op):
                operation = future_to_op[future]
                
                if self.fail_fast and operation.status == OperationStatus.FAILED:
                    # Cancel remaining operations
                    for f in future_to_op:
                        if not f.done():
                            f.cancel()
                    break
    
    def _execute_single_wrapper(self, operation: Operation) -> Operation:
        """Wrapper for parallel execution"""
        self._execute_single(operation)
        return operation
    
    def _execute_single(self, operation: Operation):
        """Execute a single operation"""
        operation.status = OperationStatus.RUNNING
        operation.start_time = time.time()
        
        try:
            result = operation.func(*operation.args, **operation.kwargs)
            operation.result = result
            operation.status = OperationStatus.SUCCESS
            logger.debug(f"Operation {operation.id} succeeded")
        except Exception as e:
            operation.error = e
            operation.status = OperationStatus.FAILED
            logger.error(f"Operation {operation.id} failed: {e}")
        finally:
            operation.end_time = time.time()
    
    def execute_with_callback(
        self,
        callback: Callable[[int, int, Operation], None],
        parallel: bool = True
    ) -> BatchResult:
        """
        Execute with progress callback
        
        Args:
            callback: Function called after each operation (current, total, operation)
            parallel: Execute in parallel
            
        Returns:
            BatchResult with execution details
        """
        if not self.operations:
            return BatchResult(
                total_operations=0,
                successful=0,
                failed=0,
                skipped=0,
                total_duration=0.0,
                operations=[]
            )
        
        start_time = time.time()
        total = len(self.operations)
        
        if parallel:
            self._execute_parallel_with_callback(callback, total)
        else:
            self._execute_sequential_with_callback(callback, total)
        
        total_duration = time.time() - start_time
        
        # Count results
        successful = sum(1 for op in self.operations if op.status == OperationStatus.SUCCESS)
        failed = sum(1 for op in self.operations if op.status == OperationStatus.FAILED)
        skipped = sum(1 for op in self.operations if op.status == OperationStatus.SKIPPED)
        
        return BatchResult(
            total_operations=total,
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_duration=total_duration,
            operations=self.operations.copy()
        )
    
    def _execute_sequential_with_callback(
        self,
        callback: Callable,
        total: int
    ):
        """Execute sequentially with callback"""
        for idx, operation in enumerate(self.operations, 1):
            self._execute_single(operation)
            callback(idx, total, operation)
    
    def _execute_parallel_with_callback(
        self,
        callback: Callable,
        total: int
    ):
        """Execute in parallel with callback"""
        executor_class = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        completed = 0
        
        with executor_class(max_workers=self.max_workers) as executor:
            future_to_op = {
                executor.submit(self._execute_single_wrapper, op): op
                for op in self.operations
            }
            
            for future in as_completed(future_to_op):
                operation = future_to_op[future]
                completed += 1
                callback(completed, total, operation)
    
    def get_results(self) -> List[Any]:
        """
        Get results from all successful operations
        
        Returns:
            List of results
        """
        return [
            op.result
            for op in self.operations
            if op.status == OperationStatus.SUCCESS
        ]
    
    def get_errors(self) -> List[Tuple[str, Exception]]:
        """
        Get errors from failed operations
        
        Returns:
            List of (operation_id, error) tuples
        """
        return [
            (op.id, op.error)
            for op in self.operations
            if op.status == OperationStatus.FAILED and op.error
        ]
    
    def clear(self):
        """Clear all operations"""
        with self.lock:
            self.operations.clear()
            logger.debug("Batch cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get batch statistics
        
        Returns:
            Dictionary with statistics
        """
        if not self.operations:
            return {
                'total_operations': 0,
                'pending': 0,
                'running': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
        
        status_counts = {
            'pending': 0,
            'running': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for op in self.operations:
            if op.status == OperationStatus.PENDING:
                status_counts['pending'] += 1
            elif op.status == OperationStatus.RUNNING:
                status_counts['running'] += 1
            elif op.status == OperationStatus.SUCCESS:
                status_counts['successful'] += 1
            elif op.status == OperationStatus.FAILED:
                status_counts['failed'] += 1
            elif op.status == OperationStatus.SKIPPED:
                status_counts['skipped'] += 1
        
        return {
            'total_operations': len(self.operations),
            **status_counts
        }


class TransactionBatch(BatchProcessor):
    """
    Batch processor with transaction support
    
    All operations succeed or all are rolled back.
    """
    
    def __init__(self, **kwargs):
        """Initialize transaction batch"""
        super().__init__(**kwargs)
        self.rollback_functions: List[Callable] = []
    
    def add_operation(
        self,
        func: Callable,
        rollback_func: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> str:
        """
        Add operation with optional rollback function
        
        Args:
            func: Function to execute
            rollback_func: Function to call on rollback
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Operation ID
        """
        op_id = super().add_operation(func, *args, **kwargs)
        self.rollback_functions.append(rollback_func)
        return op_id
    
    def execute_batch(self, **kwargs) -> BatchResult:
        """
        Execute batch with transaction semantics
        
        If any operation fails, all are rolled back.
        
        Returns:
            BatchResult
        """
        result = super().execute_batch(**kwargs)
        
        # Check if any failed
        if result.failed > 0:
            logger.warning(f"Transaction failed, rolling back {result.successful} operations")
            self._rollback()
            
            # Mark all as failed
            for op in self.operations:
                if op.status == OperationStatus.SUCCESS:
                    op.status = OperationStatus.FAILED
                    op.error = Exception("Rolled back due to transaction failure")
        
        return result
    
    def _rollback(self):
        """Roll back all successful operations"""
        for idx, operation in enumerate(self.operations):
            if operation.status == OperationStatus.SUCCESS:
                rollback_func = self.rollback_functions[idx]
                if rollback_func:
                    try:
                        rollback_func()
                        logger.debug(f"Rolled back operation {operation.id}")
                    except Exception as e:
                        logger.error(f"Rollback failed for {operation.id}: {e}")
