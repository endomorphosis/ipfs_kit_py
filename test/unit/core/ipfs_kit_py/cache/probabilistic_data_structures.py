"""
Probabilistic data structures for memory-efficient storage and lookups.

This module implements various probabilistic data structures like
Bloom filters, Count-Min Sketches, and HyperLogLog for efficient
approximate counting, membership testing, and cardinality estimation.
"""

import math
import hashlib
import struct
import random
from typing import List, Set, Any, Optional, Tuple, Union, Dict, Callable

class BloomFilter:
    """
    Bloom filter for probabilistic set membership testing.

    A Bloom filter is a space-efficient probabilistic data structure
    that is used to test whether an element is a member of a set.
    False positives are possible, but false negatives are not.
    """

    def __init__(self, capacity: int, error_rate: float = 0.01):
        """
        Initialize a Bloom filter with the given capacity and error rate.

        Args:
            capacity: Expected number of elements to be inserted
            error_rate: Desired false positive rate (0 < error_rate < 1)
        """
        self.capacity = capacity
        self.error_rate = error_rate

        # Calculate optimal bit array size and number of hash functions
        self.size = self._get_size(capacity, error_rate)
        self.hash_count = self._get_hash_count(self.size, capacity)

        # Initialize bit array (represented as a bytearray)
        self.bit_array = bytearray(math.ceil(self.size / 8))

        # Count of items added
        self.count = 0

    def _get_size(self, capacity: int, error_rate: float) -> int:
        """Calculate optimal bit array size based on capacity and error rate."""
        return int(-capacity * math.log(error_rate) / (math.log(2) ** 2))

    def _get_hash_count(self, size: int, capacity: int) -> int:
        """Calculate optimal number of hash functions."""
        return max(1, int(size / capacity * math.log(2)))

    def _get_hash_values(self, item: Any) -> List[int]:
        """Generate hash values for an item."""
        # Convert item to bytes if it's not already
        if not isinstance(item, bytes):
            item_bytes = str(item).encode('utf-8')
        else:
            item_bytes = item

        # Use two hash functions to generate k hash values
        h1 = int.from_bytes(hashlib.md5(item_bytes).digest()[:4], byteorder='little')
        h2 = int.from_bytes(hashlib.sha1(item_bytes).digest()[:4], byteorder='little')

        return [(h1 + i * h2) % self.size for i in range(self.hash_count)]

    def add(self, item: Any) -> None:
        """Add an item to the Bloom filter."""
        for bit_pos in self._get_hash_values(item):
            # Set the bit at bit_pos to 1
            byte_pos = bit_pos // 8
            bit_offset = bit_pos % 8
            self.bit_array[byte_pos] |= (1 << bit_offset)

        self.count += 1

    def __contains__(self, item: Any) -> bool:
        """Check if an item might be in the Bloom filter."""
        for bit_pos in self._get_hash_values(item):
            byte_pos = bit_pos // 8
            bit_offset = bit_pos % 8
            if not (self.bit_array[byte_pos] & (1 << bit_offset)):
                return False
        return True

    def __len__(self) -> int:
        """Get the approximate count of items added."""
        return self.count


class HyperLogLog:
    """
    HyperLogLog for efficient cardinality estimation of multisets.

    HyperLogLog is an algorithm for the count-distinct problem, approximating
    the number of distinct elements in a multiset with very low memory usage.
    """

    def __init__(self, precision: int = 14):
        """
        Initialize a HyperLogLog counter.

        Args:
            precision: The precision parameter (4 <= precision <= 16)
        """
        if precision < 4 or precision > 16:
            raise ValueError("Precision must be between 4 and 16")

        self.precision = precision
        self.m = 1 << precision  # Number of registers
        self.registers = bytearray(self.m)  # Initialize registers to 0
        self.alpha = self._get_alpha(self.m)

    def _get_alpha(self, m: int) -> float:
        """Get the alpha constant based on the number of registers."""
        if m == 16:
            return 0.673
        elif m == 32:
            return 0.697
        elif m == 64:
            return 0.709
        else:
            return 0.7213 / (1 + 1.079 / m)

    def add(self, item: Any) -> None:
        """Add an item to the HyperLogLog counter."""
        # Convert item to bytes if it's not already
        if not isinstance(item, bytes):
            item_bytes = str(item).encode('utf-8')
        else:
            item_bytes = item

        # Compute hash
        h = int.from_bytes(hashlib.md5(item_bytes).digest(), byteorder='little')

        # Use the first p bits as the register index
        register_idx = h & (self.m - 1)

        # Count the number of leading zeros in the rest of the bits
        w = h >> self.precision
        leading_zeros = min(32, 1 + (w == 0 and 32 or math.floor(math.log2(w))))

        # Update register if new value is larger
        self.registers[register_idx] = max(self.registers[register_idx], leading_zeros)

    def count(self) -> float:
        """Estimate the cardinality."""
        # Compute the harmonic mean of registers
        sum_inv = 0
        for val in self.registers:
            sum_inv += 2 ** -val

        # Apply correction factor
        estimate = self.alpha * (self.m ** 2) / sum_inv

        # Small range correction
        if estimate <= 2.5 * self.m:
            # Count number of empty registers
            zeros = self.registers.count(0)
            if zeros > 0:
                return self.m * math.log(self.m / zeros)

        # Large range correction (not implemented)

        return estimate


class CountMinSketch:
    """
    Count-Min Sketch for approximate frequency estimation.

    Count-Min Sketch is a probabilistic data structure for approximate
    frequency estimation of elements in a stream with sublinear space.
    """

    def __init__(self, width: int = 1000, depth: int = 5):
        """
        Initialize a Count-Min Sketch.

        Args:
            width: Number of counters per hash function
            depth: Number of hash functions
        """
        self.width = width
        self.depth = depth
        self.counters = [[0 for _ in range(width)] for _ in range(depth)]
        self.hash_seeds = [random.randint(0, 999999) for _ in range(depth)]

    def _get_hash_values(self, item: Any) -> List[int]:
        """Generate hash values for an item."""
        # Convert item to bytes if it's not already
        if not isinstance(item, bytes):
            item_bytes = str(item).encode('utf-8')
        else:
            item_bytes = item

        # Use different seeds for each hash function
        return [
            (int.from_bytes(hashlib.md5(item_bytes + str(seed).encode()).digest()[:4], byteorder='little') % self.width)
            for seed in self.hash_seeds
        ]

    def add(self, item: Any, count: int = 1) -> None:
        """Add an item to the Count-Min Sketch with the given count."""
        for i, h in enumerate(self._get_hash_values(item)):
            self.counters[i][h] += count

    def estimate(self, item: Any) -> int:
        """Estimate the frequency of an item."""
        return min(self.counters[i][h] for i, h in enumerate(self._get_hash_values(item)))

    def merge(self, other: 'CountMinSketch') -> 'CountMinSketch':
        """Merge with another Count-Min Sketch."""
        if self.width != other.width or self.depth != other.depth:
            raise ValueError("Cannot merge Count-Min Sketches with different dimensions")

        result = CountMinSketch(self.width, self.depth)
        for i in range(self.depth):
            for j in range(self.width):
                result.counters[i][j] = self.counters[i][j] + other.counters[i][j]

        result.hash_seeds = self.hash_seeds  # Use the same hash seeds
        return result
