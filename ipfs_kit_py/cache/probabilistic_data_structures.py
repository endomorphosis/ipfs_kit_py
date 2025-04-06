#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Probabilistic data structures for memory-efficient operations on large datasets.

This module provides several memory-efficient data structures that provide approximate
answers with high accuracy:

1. BloomFilter: Space-efficient probabilistic data structure for set membership testing
   with no false negatives (but possible false positives)

2. HyperLogLog: Algorithm for cardinality estimation (counting unique elements)
   with minimal memory requirements

3. CountMinSketch: Probabilistic data structure for frequency estimation of elements
   in a data stream with sublinear space complexity

4. CuckooFilter: Space-efficient alternative to Bloom filters with support for deletion
   and better false positive rates at high occupancy

5. MinHash: Technique for quickly estimating similarity between sets
   using hash-based sampling

These data structures are particularly useful for large datasets where exact structures
would be too memory-intensive, but approximate answers are acceptable.
"""

import hashlib
import math
import array
import random
import struct
import heapq
import mmh3  # MurmurHash3 for high-quality hashing
import numpy as np
from enum import Enum, auto
from typing import List, Set, Dict, Tuple, Optional, Any, Union, Callable
from bitarray import bitarray  # Efficient bit array implementation

# For type annotations
from numpy.typing import NDArray


class HashFunction(Enum):
    """Hash function options for probabilistic data structures."""
    MURMUR3_32 = auto()     # MurmurHash3 (32-bit) - fast, good distribution
    MURMUR3_128 = auto()    # MurmurHash3 (128-bit) - more collision-resistant
    SHA1 = auto()           # SHA-1 - cryptographic quality but slower
    MD5 = auto()            # MD5 - medium speed and quality
    XXHASH = auto()         # xxHash - very fast non-cryptographic hash
    SIPHASH = auto()        # SipHash - keyed cryptographic function, DoS resistant


class BloomFilter:
    """
    Space-efficient probabilistic data structure for set membership testing.
    
    A Bloom filter allows testing whether an element is a member of a set with
    no false negatives but possible false positives.
    
    Attributes:
        size (int): Size of the bit array
        hash_count (int): Number of hash functions to use
        bit_array (bitarray): Bit array for storing membership information
        count (int): Number of elements added to the filter
    """
    
    def __init__(self, capacity: int, false_positive_rate: float = 0.01, 
                 hash_function: HashFunction = HashFunction.MURMUR3_32):
        """
        Initialize a BloomFilter.
        
        Args:
            capacity: Expected number of elements to be inserted
            false_positive_rate: Desired false positive rate (e.g., 0.01 for 1%)
            hash_function: Hash function to use (default: MURMUR3_32)
        """
        # Calculate optimal bit array size (m) and hash function count (k)
        # m = -n*ln(p)/(ln(2)^2) where n is capacity and p is false positive rate
        self.size = self._calculate_optimal_size(capacity, false_positive_rate)
        # k = (m/n)*ln(2) where m is bit array size and n is capacity
        self.hash_count = self._calculate_optimal_hash_count(self.size, capacity)
        
        # Initialize bit array
        self.bit_array = bitarray(self.size)
        self.bit_array.setall(0)
        
        self.count = 0
        self.capacity = capacity
        self.hash_function = hash_function
        
        # Create hash function wrapper based on selected algorithm
        self._hash_func = self._create_hash_function(hash_function)
    
    def _calculate_optimal_size(self, capacity: int, false_positive_rate: float) -> int:
        """Calculate optimal bit array size based on capacity and desired false positive rate."""
        size = -capacity * math.log(false_positive_rate) / (math.log(2) ** 2)
        return math.ceil(size)
    
    def _calculate_optimal_hash_count(self, size: int, capacity: int) -> int:
        """Calculate optimal number of hash functions based on bit array size and capacity."""
        hash_count = (size / capacity) * math.log(2)
        return max(1, math.ceil(hash_count))
    
    def _create_hash_function(self, hash_function: HashFunction) -> Callable:
        """Create hash function wrapper based on selected algorithm."""
        if hash_function == HashFunction.MURMUR3_32:
            return lambda key, seed: mmh3.hash(str(key), seed) % self.size
        elif hash_function == HashFunction.MURMUR3_128:
            return lambda key, seed: mmh3.hash128(str(key), seed) % self.size
        elif hash_function == HashFunction.SHA1:
            return lambda key, seed: int(hashlib.sha1(f"{seed}:{key}".encode()).hexdigest(), 16) % self.size
        elif hash_function == HashFunction.MD5:
            return lambda key, seed: int(hashlib.md5(f"{seed}:{key}".encode()).hexdigest(), 16) % self.size
        else:
            # Default to MurmurHash3 (32-bit)
            return lambda key, seed: mmh3.hash(str(key), seed) % self.size
    
    def add(self, item: Any) -> bool:
        """
        Add an item to the Bloom filter.
        
        Args:
            item: Item to add to the filter
            
        Returns:
            bool: True if item was not present before (probably), False if it was
                 (note: false positives are possible)
        """
        # Check if already in filter
        already_present = True
        
        # Calculate hash values and set bits
        for i in range(self.hash_count):
            bit_index = self._hash_func(item, i)
            if not self.bit_array[bit_index]:
                already_present = False
            self.bit_array[bit_index] = 1
        
        # Update count if item was likely not present before
        if not already_present:
            self.count += 1
            
        return not already_present
    
    def contains(self, item: Any) -> bool:
        """
        Check if an item is in the Bloom filter.
        
        Args:
            item: Item to check
            
        Returns:
            bool: True if item is possibly in the filter, False if definitely not in the filter
        """
        for i in range(self.hash_count):
            bit_index = self._hash_func(item, i)
            if not self.bit_array[bit_index]:
                return False
        return True
    
    def __contains__(self, item: Any) -> bool:
        """Enable 'in' operator for checking membership."""
        return self.contains(item)
    
    def union(self, other: 'BloomFilter') -> 'BloomFilter':
        """
        Create a new Bloom filter that is the union of this filter and another.
        
        Args:
            other: Another BloomFilter with the same parameters
            
        Returns:
            BloomFilter: A new filter representing the union
            
        Raises:
            ValueError: If the filters have incompatible parameters
        """
        if self.size != other.size or self.hash_count != other.hash_count:
            raise ValueError("Bloom filters must have the same parameters for union operation")
        
        result = BloomFilter(self.capacity)
        result.size = self.size
        result.hash_count = self.hash_count
        result.bit_array = self.bit_array | other.bit_array
        result.count = self.count + other.count  # Approximate as there may be overlap
        
        return result
    
    def intersection(self, other: 'BloomFilter') -> 'BloomFilter':
        """
        Create a new Bloom filter that is the intersection of this filter and another.
        
        Note: This is an approximation as Bloom filters have false positives.
        
        Args:
            other: Another BloomFilter with the same parameters
            
        Returns:
            BloomFilter: A new filter representing the approximate intersection
            
        Raises:
            ValueError: If the filters have incompatible parameters
        """
        if self.size != other.size or self.hash_count != other.hash_count:
            raise ValueError("Bloom filters must have the same parameters for intersection operation")
        
        result = BloomFilter(self.capacity)
        result.size = self.size
        result.hash_count = self.hash_count
        result.bit_array = self.bit_array & other.bit_array
        result.count = min(self.count, other.count)  # Approximation
        
        return result
    
    def estimated_false_positive_rate(self) -> float:
        """
        Calculate the current estimated false positive rate of the filter.
        
        Returns:
            float: Estimated false positive probability
        """
        # p = (1 - e^(-k*n/m))^k
        # where k is hash count, n is element count, m is bit array size
        if self.count == 0:
            return 0.0
        
        # Calculate fill ratio (probability a specific bit is set to 1)
        fill_ratio = 1 - math.exp(-self.hash_count * self.count / self.size)
        
        # False positive probability is the fill ratio raised to the power of hash count
        return fill_ratio ** self.hash_count
    
    def reset(self) -> None:
        """Reset the Bloom filter to its initial empty state."""
        self.bit_array.setall(0)
        self.count = 0
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the Bloom filter.
        
        Returns:
            Dict with filter parameters and statistics
        """
        return {
            'size': self.size,
            'hash_count': self.hash_count,
            'capacity': self.capacity,
            'count': self.count,
            'bit_array_fill_ratio': sum(self.bit_array) / self.size,
            'estimated_false_positive_rate': self.estimated_false_positive_rate(),
            'memory_usage_bytes': self.bit_array.buffer_info()[1] * 8,  # Convert bits to bytes
            'hash_function': self.hash_function.name
        }


class HyperLogLog:
    """
    Probabilistic algorithm for cardinality estimation.
    
    HyperLogLog estimates the number of distinct elements in a multiset
    using minimal memory. It provides accuracy within a few percent while
    using orders of magnitude less memory than exact counting.
    
    Attributes:
        m (int): Number of registers (must be a power of 2)
        p (int): Precision parameter (log2 of number of registers)
        registers (array): Array of register values
        alpha (float): Bias correction factor
    """
    
    def __init__(self, precision: int = 14, hash_function: HashFunction = HashFunction.MURMUR3_32):
        """
        Initialize a HyperLogLog estimator.
        
        Args:
            precision: Precision parameter (p), determines number of registers (2^p)
                      Valid range: 4-16 (default: 14, giving 16384 registers and ~1% error)
            hash_function: Hash function to use
        """
        if not 4 <= precision <= 16:
            raise ValueError("Precision must be between 4 and 16")
        
        self.p = precision
        self.m = 1 << precision  # Number of registers = 2^precision
        
        # Initialize registers with zeros
        self.registers = array.array('B', [0] * self.m)
        
        # Set alpha based on m (bias correction)
        if self.m == 16:
            self.alpha = 0.673
        elif self.m == 32:
            self.alpha = 0.697
        elif self.m == 64:
            self.alpha = 0.709
        else:
            self.alpha = 0.7213 / (1.0 + 1.079 / self.m)
        
        # Create hash function wrapper based on selected algorithm
        self.hash_function = hash_function
        self._hash_func = self._create_hash_function(hash_function)
    
    def _create_hash_function(self, hash_function: HashFunction) -> Callable:
        """Create hash function wrapper based on selected algorithm."""
        if hash_function == HashFunction.MURMUR3_32:
            return lambda key: mmh3.hash(str(key), 42)
        elif hash_function == HashFunction.MURMUR3_128:
            return lambda key: mmh3.hash128(str(key), 42)
        elif hash_function == HashFunction.SHA1:
            return lambda key: int(hashlib.sha1(str(key).encode()).hexdigest(), 16)
        elif hash_function == HashFunction.MD5:
            return lambda key: int(hashlib.md5(str(key).encode()).hexdigest(), 16)
        else:
            # Default to MurmurHash3 (32-bit)
            return lambda key: mmh3.hash(str(key), 42)
    
    def add(self, item: Any) -> None:
        """
        Add an item to the estimator.
        
        Args:
            item: Item to add
        """
        # Get hash value for the item
        x = self._hash_func(item)
        
        # Determine register index using p least significant bits
        j = x & (self.m - 1)
        
        # Count leading zeros in the remaining bits (shifted right by p bits)
        w = x >> self.p
        
        # Calculate rank (position of the leftmost 1-bit) + 1
        # Add 1 because we're counting from the right, starting from 1
        rank = 1
        while (w & 1) == 0 and rank <= 32:
            w >>= 1
            rank += 1
        
        # Update register if new rank is larger
        self.registers[j] = max(self.registers[j], rank)
    
    def count(self) -> int:
        """
        Estimate the cardinality (number of unique items).
        
        Returns:
            int: Estimated cardinality
        """
        # Compute the harmonic mean of register values
        z = sum(1.0 / (1 << r) for r in self.registers)
        estimator = self.alpha * (self.m ** 2) / z
        
        # Apply corrections for small and large cardinalities
        if estimator <= 2.5 * self.m:  # Small range correction
            # Count number of registers equal to 0
            v = self.registers.count(0)
            if v != 0:  # If there are empty registers
                return int(round(self.m * math.log(self.m / v)))
        
        # Large range correction (not needed with reasonable precision values)
        # if estimator > (1/30) * 2**32:
        #     return int(round(-2**32 * math.log(1 - estimator/2**32)))
        
        return int(round(estimator))
    
    def merge(self, other: 'HyperLogLog') -> 'HyperLogLog':
        """
        Merge another HyperLogLog estimator into this one.
        
        Args:
            other: Another HyperLogLog with the same precision
            
        Returns:
            HyperLogLog: Self after merging
            
        Raises:
            ValueError: If the precision parameters don't match
        """
        if self.p != other.p:
            raise ValueError("HyperLogLog precision must match for merging")
        
        # Take the maximum of each register
        for i in range(self.m):
            self.registers[i] = max(self.registers[i], other.registers[i])
        
        return self
    
    def reset(self) -> None:
        """Reset the estimator to its initial empty state."""
        for i in range(self.m):
            self.registers[i] = 0
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the HyperLogLog estimator.
        
        Returns:
            Dict with estimator parameters and statistics
        """
        return {
            'precision': self.p,
            'registers': self.m,
            'estimated_cardinality': self.count(),
            'alpha': self.alpha,
            'standard_error': 1.04 / math.sqrt(self.m),
            'memory_usage_bytes': self.m,  # Each register uses 1 byte
            'hash_function': self.hash_function.name
        }


class CountMinSketch:
    """
    Probabilistic data structure for frequency estimation in data streams.
    
    Count-Min Sketch enables estimation of item frequencies with sublinear space
    complexity. It provides an upper bound on the frequency count that is within
    error bounds with high probability.
    
    Attributes:
        width (int): Number of counters per hash function
        depth (int): Number of hash functions
        counters (List[array]): 2D array of counters
        hash_functions (List[Callable]): List of hash functions
    """
    
    def __init__(self, width: int = 1000, depth: int = 5, 
                hash_function: HashFunction = HashFunction.MURMUR3_32):
        """
        Initialize a Count-Min Sketch.
        
        Args:
            width: Number of counters per hash function (larger -> lower error)
            depth: Number of hash functions (more -> better probability guarantees)
            hash_function: Base hash function to use
        """
        self.width = width
        self.depth = depth
        
        # Initialize counter arrays
        self.counters = [array.array('L', [0] * width) for _ in range(depth)]
        
        # Create hash functions with different seeds
        self.hash_function = hash_function
        self.hash_functions = [
            self._create_hash_function(hash_function, i) for i in range(depth)
        ]
        
        # Track total items added for scaling heavy hitters
        self.total_items = 0
    
    def _create_hash_function(self, hash_function: HashFunction, seed: int) -> Callable:
        """Create hash function with specified algorithm and seed."""
        if hash_function == HashFunction.MURMUR3_32:
            return lambda key: mmh3.hash(str(key), seed) % self.width
        elif hash_function == HashFunction.MURMUR3_128:
            return lambda key: mmh3.hash128(str(key), seed) % self.width
        elif hash_function == HashFunction.SHA1:
            return lambda key: int(hashlib.sha1(f"{seed}:{key}".encode()).hexdigest(), 16) % self.width
        elif hash_function == HashFunction.MD5:
            return lambda key: int(hashlib.md5(f"{seed}:{key}".encode()).hexdigest(), 16) % self.width
        else:
            # Default to MurmurHash3 (32-bit)
            return lambda key: mmh3.hash(str(key), seed) % self.width
    
    def add(self, item: Any, count: int = 1) -> None:
        """
        Add an item to the sketch with a given count.
        
        Args:
            item: Item to add
            count: Count to add (default: 1)
        """
        for i, hash_func in enumerate(self.hash_functions):
            index = hash_func(item)
            self.counters[i][index] += count
        
        self.total_items += count
    
    def estimate_count(self, item: Any) -> int:
        """
        Estimate the frequency of an item.
        
        Args:
            item: Item to estimate
            
        Returns:
            int: Estimated frequency (upper bound with high probability)
        """
        return min(self.counters[i][hash_func(item)] 
                  for i, hash_func in enumerate(self.hash_functions))
    
    def estimate_relative_frequency(self, item: Any) -> float:
        """
        Estimate the relative frequency of an item (estimated count / total items).
        
        Args:
            item: Item to estimate
            
        Returns:
            float: Estimated relative frequency
        """
        if self.total_items == 0:
            return 0.0
        return self.estimate_count(item) / self.total_items
    
    def merge(self, other: 'CountMinSketch') -> 'CountMinSketch':
        """
        Merge another Count-Min Sketch into this one.
        
        Args:
            other: Another Count-Min Sketch with the same parameters
            
        Returns:
            CountMinSketch: Self after merging
            
        Raises:
            ValueError: If the sketches have incompatible parameters
        """
        if self.width != other.width or self.depth != other.depth:
            raise ValueError("Count-Min Sketches must have the same dimensions for merging")
        
        # Add counters element-wise
        for i in range(self.depth):
            for j in range(self.width):
                self.counters[i][j] += other.counters[i][j]
        
        self.total_items += other.total_items
        return self
    
    def find_heavy_hitters(self, threshold: float = 0.01) -> Dict[Any, int]:
        """
        Find heavy hitter items that exceed a threshold of the total count.
        
        Args:
            threshold: Relative frequency threshold (e.g., 0.01 for 1%)
            
        Returns:
            Dict mapping items to their estimated counts
        
        Note: This is a naive implementation that requires testing all possible items.
              In practice, you would only check items you've seen before or implement
              a more efficient algorithm like SpaceSaving or Count Sketch for this purpose.
        """
        # This is a placeholder implementation that would require tracking items
        # A real implementation would track candidate items as they're added
        raise NotImplementedError(
            "Efficiently finding heavy hitters requires tracking items as they're added. "
            "Use a specialized data structure like SpaceSaving or CountSketch for this purpose."
        )
    
    def reset(self) -> None:
        """Reset the sketch to its initial empty state."""
        for row in self.counters:
            for i in range(self.width):
                row[i] = 0
        self.total_items = 0
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the Count-Min Sketch.
        
        Returns:
            Dict with sketch parameters and statistics
        """
        # Calculate error bounds
        delta = math.exp(-self.depth)  # Probability of failure
        epsilon = 2.0 / self.width  # Error factor
        
        return {
            'width': self.width,
            'depth': self.depth,
            'total_items': self.total_items,
            'error_bound': epsilon * self.total_items,  # Absolute error
            'error_rate': epsilon,  # Relative error
            'failure_probability': delta,
            'memory_usage_bytes': self.depth * self.width * 8,  # 8 bytes per counter (unsigned long)
            'hash_function': self.hash_function.name
        }


class CuckooFilter:
    """
    Space-efficient probabilistic data structure for set membership testing with deletion support.
    
    Cuckoo filters provide similar functionality to Bloom filters but also support deletion and
    have better performance when the filter is highly occupied. They use cuckoo hashing to resolve
    collisions by relocating entries.
    
    Attributes:
        size (int): Size of the bucket array
        bucket_size (int): Number of entries per bucket
        buckets (List[List]): 2D array of buckets containing fingerprints
        count (int): Number of items in the filter
    """
    
    def __init__(self, capacity: int, bucket_size: int = 4, 
                fingerprint_size: int = 8, max_relocations: int = 500,
                hash_function: HashFunction = HashFunction.MURMUR3_32):
        """
        Initialize a Cuckoo filter.
        
        Args:
            capacity: Expected number of items to be inserted
            bucket_size: Number of entries per bucket (default: 4)
            fingerprint_size: Size of fingerprint in bits (default: 8)
            max_relocations: Maximum number of evictions before insertion fails (default: 500)
            hash_function: Hash function to use for fingerprinting and indexing
        """
        # Calculate appropriate number of buckets
        # We aim for a load factor (items / slots) of about 0.95 or less
        self.bucket_size = bucket_size
        num_buckets = math.ceil(capacity / (bucket_size * 0.95))
        # Round to power of 2 for more efficient calculation
        self.size = 1 << (num_buckets - 1).bit_length()
        
        self.fingerprint_size = fingerprint_size
        self.max_fingerprint = (1 << fingerprint_size) - 1
        self.max_relocations = max_relocations
        
        # Initialize buckets
        self.buckets = [[] for _ in range(self.size)]
        self.count = 0
        
        self.hash_function = hash_function
        self._hash_func = self._create_hash_function(hash_function)
    
    def _create_hash_function(self, hash_function: HashFunction) -> Callable:
        """Create hash function wrapper based on selected algorithm."""
        if hash_function == HashFunction.MURMUR3_32:
            return lambda key: mmh3.hash(str(key), 42)
        elif hash_function == HashFunction.MURMUR3_128:
            return lambda key: mmh3.hash128(str(key), 42)
        elif hash_function == HashFunction.SHA1:
            return lambda key: int(hashlib.sha1(str(key).encode()).hexdigest(), 16)
        elif hash_function == HashFunction.MD5:
            return lambda key: int(hashlib.md5(str(key).encode()).hexdigest(), 16)
        else:
            # Default to MurmurHash3 (32-bit)
            return lambda key: mmh3.hash(str(key), 42)
    
    def _get_fingerprint(self, item: Any) -> int:
        """Generate a fingerprint for an item."""
        # Use the hash function to generate a fingerprint
        hash_val = self._hash_func(item)
        # Ensure it's not 0 (reserved value for empty slots)
        fingerprint = (hash_val & self.max_fingerprint) or 1
        return fingerprint
    
    def _get_indices(self, item: Any, fingerprint: Optional[int] = None) -> Tuple[int, int]:
        """
        Get the two possible bucket indices for an item and its fingerprint.
        
        Args:
            item: The item to hash
            fingerprint: Optional pre-computed fingerprint
            
        Returns:
            Tuple of two bucket indices where the item could be stored
        """
        # If fingerprint is not provided, generate it
        if fingerprint is None:
            fingerprint = self._get_fingerprint(item)
        
        # Calculate first index
        hash_val = self._hash_func(item)
        idx1 = hash_val % self.size
        
        # Calculate second index using fingerprint
        idx2 = (idx1 ^ (fingerprint * 0x5bd1e995)) % self.size
        
        return idx1, idx2
    
    def add(self, item: Any) -> bool:
        """
        Add an item to the filter.
        
        Args:
            item: Item to add
            
        Returns:
            bool: True if item was added successfully, False if filter is too full
        """
        fingerprint = self._get_fingerprint(item)
        i1, i2 = self._get_indices(item, fingerprint)
        
        # Try to insert into either bucket if not full
        if len(self.buckets[i1]) < self.bucket_size:
            self.buckets[i1].append(fingerprint)
            self.count += 1
            return True
        
        if len(self.buckets[i2]) < self.bucket_size:
            self.buckets[i2].append(fingerprint)
            self.count += 1
            return True
        
        # Both buckets are full, use cuckoo hashing to relocate entries
        # Randomly select a bucket to evict from
        i = random.choice([i1, i2])
        for n in range(self.max_relocations):
            # Randomly select an entry to evict
            j = random.randrange(len(self.buckets[i]))
            victim_fingerprint = self.buckets[i][j]
            
            # Remove the victim
            self.buckets[i].pop(j)
            
            # Insert the current fingerprint
            self.buckets[i].append(fingerprint)
            
            # Find the alternate location for the victim
            i1, i2 = i, (i ^ (victim_fingerprint * 0x5bd1e995)) % self.size
            if len(self.buckets[i2]) < self.bucket_size:
                self.buckets[i2].append(victim_fingerprint)
                self.count += 1
                return True
            
            # Evict from the alternate location next
            i = i2
            fingerprint = victim_fingerprint
        
        # Too many relocations, filter is too full
        # In a real implementation, we might resize the filter here
        return False
    
    def contains(self, item: Any) -> bool:
        """
        Check if an item is in the filter.
        
        Args:
            item: Item to check
            
        Returns:
            bool: True if item is possibly in the filter, False if definitely not in the filter
        """
        fingerprint = self._get_fingerprint(item)
        i1, i2 = self._get_indices(item, fingerprint)
        
        return fingerprint in self.buckets[i1] or fingerprint in self.buckets[i2]
    
    def __contains__(self, item: Any) -> bool:
        """Enable 'in' operator for checking membership."""
        return self.contains(item)
    
    def remove(self, item: Any) -> bool:
        """
        Remove an item from the filter.
        
        Args:
            item: Item to remove
            
        Returns:
            bool: True if item was found and removed, False otherwise
        """
        fingerprint = self._get_fingerprint(item)
        i1, i2 = self._get_indices(item, fingerprint)
        
        # Try to remove from first bucket
        if fingerprint in self.buckets[i1]:
            self.buckets[i1].remove(fingerprint)
            self.count -= 1
            return True
        
        # Try to remove from second bucket
        if fingerprint in self.buckets[i2]:
            self.buckets[i2].remove(fingerprint)
            self.count -= 1
            return True
        
        # Item not found
        return False
    
    def reset(self) -> None:
        """Reset the filter to its initial empty state."""
        self.buckets = [[] for _ in range(self.size)]
        self.count = 0
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the Cuckoo filter.
        
        Returns:
            Dict with filter parameters and statistics
        """
        total_slots = self.size * self.bucket_size
        load_factor = self.count / total_slots if total_slots > 0 else 0
        
        # Estimate false positive rate: 2ϵ where ϵ ≈ 2^(-f) and f is fingerprint size in bits
        false_positive_rate = 2 * (2 ** -self.fingerprint_size)
        
        return {
            'size': self.size,
            'bucket_size': self.bucket_size,
            'fingerprint_size': self.fingerprint_size,
            'count': self.count,
            'total_slots': total_slots,
            'load_factor': load_factor,
            'estimated_false_positive_rate': false_positive_rate,
            'memory_usage_bytes': sum(len(bucket) for bucket in self.buckets) * (self.fingerprint_size // 8),
            'hash_function': self.hash_function.name
        }


class MinHash:
    """
    Technique for quickly estimating the Jaccard similarity between sets.
    
    MinHash creates a signature for each set by selecting the minimum hash
    values from a collection of hash functions. The similarity between sets
    can be estimated by comparing their signatures.
    
    Attributes:
        num_perm (int): Number of permutations (hash functions)
        seed (int): Random seed for hash functions
        hash_functions (List[Callable]): List of hash functions
    """
    
    def __init__(self, num_perm: int = 128, seed: int = 42,
                hash_function: HashFunction = HashFunction.MURMUR3_32):
        """
        Initialize a MinHash object.
        
        Args:
            num_perm: Number of permutations/hash functions (more -> higher accuracy)
            seed: Random seed for hash function initialization
            hash_function: Hash function to use
        """
        self.num_perm = num_perm
        self.seed = seed
        self.hash_function = hash_function
        
        # Initialize hash functions with different seeds
        self.hash_functions = [
            self._create_hash_function(hash_function, seed + i) for i in range(num_perm)
        ]
        
        # Initialize signature with max values
        self.signature = [float('inf')] * num_perm
    
    def _create_hash_function(self, hash_function: HashFunction, seed: int) -> Callable:
        """Create hash function with specified algorithm and seed."""
        if hash_function == HashFunction.MURMUR3_32:
            return lambda key: mmh3.hash(str(key), seed)
        elif hash_function == HashFunction.MURMUR3_128:
            return lambda key: mmh3.hash128(str(key), seed)
        elif hash_function == HashFunction.SHA1:
            return lambda key: int(hashlib.sha1(f"{seed}:{key}".encode()).hexdigest(), 16)
        elif hash_function == HashFunction.MD5:
            return lambda key: int(hashlib.md5(f"{seed}:{key}".encode()).hexdigest(), 16)
        else:
            # Default to MurmurHash3 (32-bit)
            return lambda key: mmh3.hash(str(key), seed)
    
    def update(self, items: Union[Set, List, Tuple]) -> None:
        """
        Update the signature with a set of items.
        
        Args:
            items: Collection of items to hash
        """
        for item in items:
            for i, hash_func in enumerate(self.hash_functions):
                hash_val = hash_func(item)
                self.signature[i] = min(self.signature[i], hash_val)
    
    def jaccard(self, other: 'MinHash') -> float:
        """
        Estimate Jaccard similarity with another MinHash.
        
        Args:
            other: Another MinHash object
            
        Returns:
            float: Estimated Jaccard similarity [0.0, 1.0]
            
        Raises:
            ValueError: If the MinHash objects have different number of permutations
        """
        if self.num_perm != other.num_perm:
            raise ValueError("MinHash objects must have the same number of permutations")
        
        # Count how many signature elements match
        matches = sum(s1 == s2 for s1, s2 in zip(self.signature, other.signature))
        
        # Jaccard similarity ≈ proportion of matching signature elements
        return matches / self.num_perm
    
    def merge(self, other: 'MinHash') -> 'MinHash':
        """
        Merge another MinHash into this one (union operation).
        
        Args:
            other: Another MinHash object
            
        Returns:
            MinHash: Self after merging
            
        Raises:
            ValueError: If the MinHash objects have different number of permutations
        """
        if self.num_perm != other.num_perm:
            raise ValueError("MinHash objects must have the same number of permutations")
        
        # For union, take the minimum value for each signature position
        for i in range(self.num_perm):
            self.signature[i] = min(self.signature[i], other.signature[i])
        
        return self
    
    def reset(self) -> None:
        """Reset the signature to its initial state."""
        self.signature = [float('inf')] * self.num_perm
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the MinHash.
        
        Returns:
            Dict with parameters and statistics
        """
        # Standard error of Jaccard similarity estimate is 1/sqrt(num_perm)
        std_error = 1.0 / math.sqrt(self.num_perm)
        
        return {
            'num_permutations': self.num_perm,
            'seed': self.seed,
            'standard_error': std_error,
            'memory_usage_bytes': self.num_perm * 8,  # 8 bytes per signature int (64-bit)
            'hash_function': self.hash_function.name
        }


class TopK:
    """
    Data structure for tracking top-k frequent elements in a data stream.
    
    Uses a Count-Min Sketch for frequency estimation and a heap to track top elements.
    
    Attributes:
        k (int): Number of top elements to track
        sketch (CountMinSketch): Sketch for frequency estimation
        top_items (List[Tuple]): Heap of (count, item) pairs
        item_set (Set): Set of items currently in the heap
    """
    
    def __init__(self, k: int = 10, width: int = 1000, depth: int = 5,
                hash_function: HashFunction = HashFunction.MURMUR3_32):
        """
        Initialize a Top-K tracker.
        
        Args:
            k: Number of top elements to track
            width: Width of the underlying Count-Min Sketch
            depth: Depth of the underlying Count-Min Sketch
            hash_function: Hash function to use
        """
        self.k = k
        self.sketch = CountMinSketch(width, depth, hash_function)
        self.top_items = []  # Min heap
        self.item_set = set()  # Set of items in the heap
    
    def add(self, item: Any, count: int = 1) -> None:
        """
        Add an item to the stream.
        
        Args:
            item: Item to add
            count: Count to add (default: 1)
        """
        # Update the sketch
        self.sketch.add(item, count)
        
        # Get updated count
        estimated_count = self.sketch.estimate_count(item)
        
        # Check if item is already in the heap
        if item in self.item_set:
            # Find and update the item
            for i, (old_count, old_item) in enumerate(self.top_items):
                if old_item == item:
                    # Remove old entry
                    self.top_items[i] = self.top_items[-1]
                    self.top_items.pop()
                    heapq.heapify(self.top_items)
                    break
            
            # Add updated entry
            heapq.heappush(self.top_items, (estimated_count, item))
            
        elif len(self.top_items) < self.k:
            # Heap not full, add new item
            heapq.heappush(self.top_items, (estimated_count, item))
            self.item_set.add(item)
            
        elif estimated_count > self.top_items[0][0]:
            # Replace smallest item in heap
            smallest_count, smallest_item = heapq.heappop(self.top_items)
            self.item_set.remove(smallest_item)
            
            heapq.heappush(self.top_items, (estimated_count, item))
            self.item_set.add(item)
    
    def get_top_k(self) -> List[Tuple[Any, int]]:
        """
        Get the current top-k items with their estimated frequencies.
        
        Returns:
            List of (item, count) pairs sorted by count (descending)
        """
        # Return items with counts, sorted by count in descending order
        return [(item, count) for count, item in sorted(self.top_items, reverse=True)]
    
    def reset(self) -> None:
        """Reset the tracker to its initial empty state."""
        self.sketch.reset()
        self.top_items = []
        self.item_set = set()
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the Top-K tracker.
        
        Returns:
            Dict with parameters and statistics
        """
        return {
            'k': self.k,
            'items_tracked': len(self.top_items),
            'sketch_info': self.sketch.get_info(),
            'memory_usage_bytes': len(self.top_items) * 16 + len(self.item_set) * 8,  # Rough estimate
        }


class ProbabilisticDataStructureManager:
    """
    Manager class for creating and managing probabilistic data structures.
    
    This class provides a unified interface for creating various probabilistic
    data structures with appropriate parameters based on the intended use case.
    
    Available data structures:
    - BloomFilter: For membership testing
    - HyperLogLog: For cardinality estimation
    - CountMinSketch: For frequency estimation
    - CuckooFilter: For membership testing with deletion support
    - MinHash: For similarity estimation
    - TopK: For tracking most frequent elements
    """
    
    def __init__(self):
        """Initialize the manager."""
        self.structures = {}
    
    def create_bloom_filter(self, name: str, capacity: int, 
                          false_positive_rate: float = 0.01) -> BloomFilter:
        """
        Create a Bloom filter with the given parameters.
        
        Args:
            name: Name to identify this structure in the manager
            capacity: Expected number of elements
            false_positive_rate: Desired false positive rate (default: 0.01)
            
        Returns:
            BloomFilter: Newly created Bloom filter
        """
        bf = BloomFilter(capacity, false_positive_rate)
        self.structures[name] = bf
        return bf
    
    def create_hyperloglog(self, name: str, precision: int = 14) -> HyperLogLog:
        """
        Create a HyperLogLog estimator.
        
        Args:
            name: Name to identify this structure in the manager
            precision: Precision parameter (4-16, default: 14)
            
        Returns:
            HyperLogLog: Newly created HyperLogLog estimator
        """
        hll = HyperLogLog(precision)
        self.structures[name] = hll
        return hll
    
    def create_count_min_sketch(self, name: str, width: int = 1000, 
                               depth: int = 5) -> CountMinSketch:
        """
        Create a Count-Min Sketch.
        
        Args:
            name: Name to identify this structure in the manager
            width: Number of counters per hash function (default: 1000)
            depth: Number of hash functions (default: 5)
            
        Returns:
            CountMinSketch: Newly created Count-Min Sketch
        """
        cms = CountMinSketch(width, depth)
        self.structures[name] = cms
        return cms
    
    def create_cuckoo_filter(self, name: str, capacity: int, 
                           bucket_size: int = 4) -> CuckooFilter:
        """
        Create a Cuckoo filter.
        
        Args:
            name: Name to identify this structure in the manager
            capacity: Expected number of elements
            bucket_size: Number of entries per bucket (default: 4)
            
        Returns:
            CuckooFilter: Newly created Cuckoo filter
        """
        cf = CuckooFilter(capacity, bucket_size)
        self.structures[name] = cf
        return cf
    
    def create_minhash(self, name: str, num_perm: int = 128) -> MinHash:
        """
        Create a MinHash for similarity estimation.
        
        Args:
            name: Name to identify this structure in the manager
            num_perm: Number of permutations (default: 128)
            
        Returns:
            MinHash: Newly created MinHash
        """
        mh = MinHash(num_perm)
        self.structures[name] = mh
        return mh
    
    def create_topk(self, name: str, k: int = 10, 
                   width: int = 1000, depth: int = 5) -> TopK:
        """
        Create a Top-K tracker.
        
        Args:
            name: Name to identify this structure in the manager
            k: Number of top elements to track (default: 10)
            width: Width of underlying Count-Min Sketch (default: 1000)
            depth: Depth of underlying Count-Min Sketch (default: 5)
            
        Returns:
            TopK: Newly created Top-K tracker
        """
        topk = TopK(k, width, depth)
        self.structures[name] = topk
        return topk
    
    def get(self, name: str) -> Any:
        """
        Get a previously created data structure by name.
        
        Args:
            name: Name of the structure to retrieve
            
        Returns:
            The requested data structure
            
        Raises:
            KeyError: If no structure with the given name exists
        """
        if name not in self.structures:
            raise KeyError(f"No data structure named '{name}' exists")
        return self.structures[name]
    
    def remove(self, name: str) -> None:
        """
        Remove a data structure from the manager.
        
        Args:
            name: Name of the structure to remove
            
        Raises:
            KeyError: If no structure with the given name exists
        """
        if name not in self.structures:
            raise KeyError(f"No data structure named '{name}' exists")
        del self.structures[name]
    
    def get_all_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all managed data structures.
        
        Returns:
            Dict mapping structure names to their info dictionaries
        """
        return {name: struct.get_info() for name, struct in self.structures.items()}
    
    def reset_all(self) -> None:
        """Reset all managed data structures to their initial states."""
        for struct in self.structures.values():
            struct.reset()