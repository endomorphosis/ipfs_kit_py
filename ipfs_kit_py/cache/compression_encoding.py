"""
Compression and encoding optimizations for ParquetCIDCache.

This module provides advanced compression and encoding strategies
for optimizing metadata storage in ParquetCIDCache.
"""

import os
import time
import logging
import json
import hashlib
import zlib
import base64
import binascii
from typing import Dict, List, Set, Tuple, Any, Optional, Union, Callable

import numpy as np

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    from pyarrow.dataset import dataset
    HAVE_PYARROW = True
except ImportError:
    HAVE_PYARROW = False

try:
    import snappy
    HAVE_SNAPPY = True
except ImportError:
    HAVE_SNAPPY = False

try:
    import lz4.frame
    HAVE_LZ4 = True
except ImportError:
    HAVE_LZ4 = False

try:
    import zstandard as zstd
    HAVE_ZSTD = True
except ImportError:
    HAVE_ZSTD = False

logger = logging.getLogger(__name__)

class CompressionProfile:
    """Profile for optimizing compression and encoding settings."""

    def __init__(self, name: str, description: str = None):
        """Initialize a compression profile.

        Args:
            name: Name of the profile
            description: Optional description
        """
        self.name = name
        self.description = description or f"Compression profile: {name}"

        # Default compression settings
        self.compression = "zstd"
        self.compression_level = 3
        self.use_dictionary = True
        self.dictionary_size = 1024 * 1024  # 1MB

        # Default encoding settings
        self.encoding_settings = {
            "string_columns": {
                "encoding": "PLAIN_DICTIONARY",
                "dictionary_page_size_limit": 1024 * 1024  # 1MB
            },
            "int_columns": {
                "encoding": "PLAIN",
            },
            "binary_columns": {
                "encoding": "PLAIN"
            },
            "boolean_columns": {
                "encoding": "RLE"
            },
            "timestamp_columns": {
                "encoding": "PLAIN"
            }
        }

        # Default options for page size and rowgroup size
        self.page_size = 64 * 1024  # 64KB
        self.rowgroup_size = 128 * 1024 * 1024  # 128MB

        # Column-specific settings
        self.column_settings = {}

        # Specialized settings for CID columns
        self.cid_column_settings = {
            "encoding": "PLAIN_DICTIONARY",
            "compression": "zstd",
            "compression_level": 3,
            "dictionary_page_size_limit": 2 * 1024 * 1024  # 2MB for CID dictionaries
        }

        # Flag for optimizing complex nested structures
        self.optimize_nested_structures = True

        # Bloom filter settings
        self.use_bloom_filters = True
        self.bloom_filter_columns = ["cid"]  # Default columns to create bloom filters for

        # Statistics collection
        self.write_statistics = True

        # Memory map option
        self.memory_map = True

    def optimize_for_tier(self, tier: str):
        """Optimize profile for a specific storage tier.

        Args:
            tier: Storage tier name ("memory", "disk", "s3", etc.)

        Returns:
            Self for chaining
        """
        if tier == "memory":
            # For memory tier, prioritize speed over compression ratio
            self.compression = "lz4"
            self.compression_level = 1
            self.page_size = 256 * 1024  # 256KB
            self.rowgroup_size = 256 * 1024 * 1024  # 256MB
            self.dictionary_size = 2 * 1024 * 1024  # 2MB

        elif tier == "disk":
            # For disk tier, balance speed and compression
            self.compression = "zstd"
            self.compression_level = 3
            self.page_size = 64 * 1024  # 64KB
            self.rowgroup_size = 128 * 1024 * 1024  # 128MB

        elif tier == "s3" or tier == "cloud":
            # For cloud storage, prioritize compression ratio
            self.compression = "zstd"
            self.compression_level = 7
            self.page_size = 32 * 1024  # 32KB
            self.rowgroup_size = 64 * 1024 * 1024  # 64MB

        elif tier == "cold" or tier == "archive":
            # For archival storage, maximize compression ratio
            self.compression = "zstd"
            self.compression_level = 19  # Maximum zstd level
            self.page_size = 16 * 1024  # 16KB
            self.rowgroup_size = 32 * 1024 * 1024  # 32MB

            # For very cold storage, we might prefer GZIP for wider compatibility
            if tier == "archive":
                self.compression = "gzip"
                self.compression_level = 9  # Maximum gzip level

        return self

    def optimize_for_workload(self, workload_type: str):
        """Optimize profile for a specific workload type.

        Args:
            workload_type: Type of workload ("read_heavy", "write_heavy",
                         "analytical", "metadata", "mixed")

        Returns:
            Self for chaining
        """
        if workload_type == "read_heavy":
            # For read-heavy workloads, optimize for read speed
            self.use_bloom_filters = True
            self.memory_map = True
            self.write_statistics = True

            # Use lighter compression for faster reads
            if HAVE_LZ4:
                self.compression = "lz4"
                self.compression_level = 1

        elif workload_type == "write_heavy":
            # For write-heavy workloads, optimize for write speed
            self.use_bloom_filters = False
            self.write_statistics = False

            # Use lighter compression for faster writes
            if HAVE_LZ4:
                self.compression = "lz4"
                self.compression_level = 1
            elif HAVE_SNAPPY:
                self.compression = "snappy"

            # Larger page sizes for fewer I/O operations
            self.page_size = 256 * 1024  # 256KB

        elif workload_type == "analytical":
            # For analytical workloads, optimize for query performance
            self.use_bloom_filters = True
            self.write_statistics = True
            self.memory_map = True

            # Column-specific optimizations for analytical queries
            # String columns benefit from dictionary encoding in analytical workloads
            self.encoding_settings["string_columns"]["encoding"] = "PLAIN_DICTIONARY"

            # For numeric columns that will be aggregated, use delta encoding
            self.encoding_settings["int_columns"]["encoding"] = "DELTA_BINARY_PACKED"

        elif workload_type == "metadata":
            # For metadata workloads, optimize for small metadata values
            self.use_dictionary = True
            self.dictionary_size = 2 * 1024 * 1024  # 2MB for metadata

            # Metadata often has repetitive string values, optimize for that
            self.encoding_settings["string_columns"]["encoding"] = "PLAIN_DICTIONARY"

            # Special handling for CID columns which tend to be repetitive
            self.cid_column_settings["encoding"] = "PLAIN_DICTIONARY"

            # For timestamps in metadata, delta encoding works well
            self.encoding_settings["timestamp_columns"]["encoding"] = "DELTA_BINARY_PACKED"

        return self

    def set_column_settings(self, column: str, settings: Dict[str, Any]):
        """Set custom settings for a specific column.

        Args:
            column: Column name
            settings: Dictionary with settings for this column

        Returns:
            Self for chaining
        """
        self.column_settings[column] = settings
        return self

    def adjust_for_schema(self, schema: Any):
        """Adjust compression settings based on the provided schema.

        Args:
            schema: PyArrow schema to optimize for

        Returns:
            Self for chaining
        """
        if not HAVE_PYARROW:
            logger.warning("PyArrow not available. Schema-based optimization skipped.")
            return self

        if not isinstance(schema, pa.Schema):
            logger.warning("Provided schema is not a PyArrow schema. Optimization skipped.")
            return self

        # Analyze schema and adjust settings
        string_columns = []
        int_columns = []
        binary_columns = []
        bool_columns = []
        timestamp_columns = []
        cid_columns = []

        # Categorize columns by type
        for field in schema:
            name = field.name
            typ = field.type

            if pa.types.is_string(typ):
                string_columns.append(name)
                # Check if it looks like a CID column
                if name.lower() == 'cid' or name.endswith('_cid'):
                    cid_columns.append(name)
            elif pa.types.is_integer(typ):
                int_columns.append(name)
            elif pa.types.is_binary(typ):
                binary_columns.append(name)
            elif pa.types.is_boolean(typ):
                bool_columns.append(name)
            elif pa.types.is_timestamp(typ):
                timestamp_columns.append(name)

        # Apply optimized bloom filters for CID columns
        if self.use_bloom_filters and cid_columns:
            self.bloom_filter_columns = cid_columns

        # Set column-specific settings based on type
        for col in string_columns:
            if col not in self.column_settings:
                self.column_settings[col] = self.encoding_settings["string_columns"].copy()

        for col in int_columns:
            if col not in self.column_settings:
                self.column_settings[col] = self.encoding_settings["int_columns"].copy()

        for col in binary_columns:
            if col not in self.column_settings:
                self.column_settings[col] = self.encoding_settings["binary_columns"].copy()

        for col in bool_columns:
            if col not in self.column_settings:
                self.column_settings[col] = self.encoding_settings["boolean_columns"].copy()

        for col in timestamp_columns:
            if col not in self.column_settings:
                self.column_settings[col] = self.encoding_settings["timestamp_columns"].copy()

        # Apply CID-specific optimizations
        for col in cid_columns:
            self.column_settings[col] = self.cid_column_settings.copy()

        return self

    def to_write_args(self) -> Dict[str, Any]:
        """Convert profile to PyArrow parquet write arguments.

        Returns:
            Dictionary of write arguments for pyarrow.parquet.write_table
        """
        if not HAVE_PYARROW:
            logger.warning("PyArrow not available. Using default write arguments.")
            return {}

        args = {
            "compression": self.compression,
            "compression_level": self.compression_level,
            "use_dictionary": self.use_dictionary,
            "write_statistics": self.write_statistics,
            "data_page_size": self.page_size,
            "dictionary_pagesize_limit": self.dictionary_size,
            "row_group_size": self.rowgroup_size
        }

        # Add column encodings if we have any
        if self.column_settings:
            column_properties = {}
            for column, settings in self.column_settings.items():
                column_properties[column] = settings.copy()

            args["column_properties"] = column_properties

        # Add bloom filter settings
        if self.use_bloom_filters and HAVE_PYARROW and hasattr(pq, 'ParquetBloomFilterProperties'):
            bloom_filter_props = pq.ParquetBloomFilterProperties()
            for col in self.bloom_filter_columns:
                bloom_filter_props.add_column(col)
            args["bloom_filter_properties"] = bloom_filter_props

        return args


class EncodingOptimizer:
    """Optimizer for specialized encodings and compression."""

    @staticmethod
    def optimize_cid_storage(cid: str) -> bytes:
        """Apply specialized encoding to CIDs for efficient storage.

        Args:
            cid: Content identifier string

        Returns:
            Optimized binary representation
        """
        # For IPFS CIDs, we can optimize storage by:
        # 1. Recognizing the CID version and encoding it efficiently
        # 2. Storing the multihash type separately from the digest
        # 3. Using binary representation instead of base58/32/16

        # Simple version - just convert base58 to binary
        # For a full implementation, a proper CID library should be used
        try:
            # Check if it's a v0 CID (Qm...)
            if cid.startswith('Qm') and len(cid) == 46:
                # It's likely a base58-encoded CIDv0
                try:
                    from multibase import decode
                    return decode(cid.encode())
                except ImportError:
                    # Fallback if multibase is not available
                    import base58
                    return base58.b58decode(cid)
            else:
                # For other CIDs, just store as is for now
                return cid.encode()
        except Exception as e:
            logger.warning(f"Error optimizing CID storage for {cid}: {e}")
            return cid.encode()

    @staticmethod
    def restore_cid_from_optimized(optimized_data: bytes) -> str:
        """Restore a CID from its optimized representation.

        Args:
            optimized_data: The optimized binary representation

        Returns:
            Original CID string
        """
        try:
            # Detect if this is a raw multihash (v0 CID)
            # CIDv0 starts with 0x12 0x20 (multihash for sha2-256)
            if len(optimized_data) == 34 and optimized_data[0] == 0x12 and optimized_data[1] == 0x20:
                try:
                    from multibase import encode
                    return encode('base58btc', optimized_data).decode()
                except ImportError:
                    # Fallback if multibase is not available
                    import base58
                    return base58.b58encode(optimized_data).decode()
            else:
                # For other formats, just decode as utf-8
                return optimized_data.decode()
        except Exception as e:
            logger.warning(f"Error restoring CID from optimized data: {e}")
            # Last resort - convert to hex
            return binascii.hexlify(optimized_data).decode()

    @staticmethod
    def find_optimal_compression(data: bytes,
                                min_size: int = 1024,
                                methods: List[str] = None) -> Tuple[str, bytes]:
        """Find the optimal compression method for the given data.

        Args:
            data: Data to compress
            min_size: Minimum size to attempt compression
            methods: List of compression methods to try

        Returns:
            Tuple of (method_name, compressed_data)
        """
        if len(data) < min_size:
            return "none", data

        if methods is None:
            methods = []
            # Add available compression methods
            methods.append("zlib")
            if HAVE_SNAPPY:
                methods.append("snappy")
            if HAVE_LZ4:
                methods.append("lz4")
            if HAVE_ZSTD:
                methods.append("zstd")

        results = []

        # Try each compression method
        for method in methods:
            try:
                if method == "zlib":
                    compressed = zlib.compress(data, level=9)
                    results.append((method, compressed, len(compressed)))
                elif method == "snappy" and HAVE_SNAPPY:
                    compressed = snappy.compress(data)
                    results.append((method, compressed, len(compressed)))
                elif method == "lz4" and HAVE_LZ4:
                    compressed = lz4.frame.compress(data)
                    results.append((method, compressed, len(compressed)))
                elif method == "zstd" and HAVE_ZSTD:
                    compressed = zstd.compress(data)
                    results.append((method, compressed, len(compressed)))
            except Exception as e:
                logger.warning(f"Error compressing with {method}: {e}")

        # If no compression worked, return original
        if not results:
            return "none", data

        # Find the smallest result
        results.sort(key=lambda x: x[2])
        best_method, best_compressed, _ = results[0]

        # Only use compression if it actually reduces size
        if len(best_compressed) < len(data):
            return best_method, best_compressed
        else:
            return "none", data

    @staticmethod
    def compress_with_method(data: bytes, method: str) -> bytes:
        """Compress data with a specific method.

        Args:
            data: Data to compress
            method: Compression method to use

        Returns:
            Compressed data
        """
        if method == "none":
            return data
        elif method == "zlib":
            return zlib.compress(data)
        elif method == "snappy" and HAVE_SNAPPY:
            return snappy.compress(data)
        elif method == "lz4" and HAVE_LZ4:
            return lz4.frame.compress(data)
        elif method == "zstd" and HAVE_ZSTD:
            return zstd.compress(data)
        else:
            logger.warning(f"Unsupported compression method: {method}")
            return data

    @staticmethod
    def decompress_with_method(data: bytes, method: str) -> bytes:
        """Decompress data with a specific method.

        Args:
            data: Compressed data
            method: Compression method used

        Returns:
            Decompressed data
        """
        if method == "none":
            return data
        elif method == "zlib":
            return zlib.decompress(data)
        elif method == "snappy" and HAVE_SNAPPY:
            return snappy.decompress(data)
        elif method == "lz4" and HAVE_LZ4:
            return lz4.frame.decompress(data)
        elif method == "zstd" and HAVE_ZSTD:
            return zstd.decompress(data)
        else:
            logger.warning(f"Unsupported decompression method: {method}")
            return data


class ColumnAnalyzer:
    """Analyzer for column data characteristics to inform encoding choices."""

    @staticmethod
    def analyze_column(data: List[Any], name: str = None) -> Dict[str, Any]:
        """Analyze column data to determine optimal encoding.

        Args:
            data: List of values in the column
            name: Optional column name

        Returns:
            Dictionary with analysis results
        """
        if not data:
            return {"column": name, "count": 0, "recommended_encoding": "PLAIN"}

        # Determine the data type
        sample = data[0]
        data_type = type(sample).__name__

        # Count total and unique values
        count = len(data)

        try:
            # Handle different data types
            if isinstance(sample, (str, bytes)):
                unique_count = len(set(data))
                cardinality_ratio = unique_count / count
                avg_length = sum(len(x) for x in data) / count

                # Check for CID-like strings
                cid_like = False
                if isinstance(sample, str) and name and ('cid' in name.lower()):
                    # Check if values match CID pattern (Qm... or similar)
                    if all(x.startswith(('Qm', 'ba', 'z')) for x in data[:100]):
                        cid_like = True

                # Recommend encoding based on cardinality
                if cardinality_ratio < 0.3:
                    # Low cardinality - dictionary encoding is efficient
                    encoding = "PLAIN_DICTIONARY"
                elif avg_length > 100:
                    # Long strings - consider compression
                    encoding = "PLAIN"
                else:
                    encoding = "PLAIN"

                # Special treatment for CID-like columns
                if cid_like:
                    encoding = "PLAIN_DICTIONARY"

                return {
                    "column": name,
                    "count": count,
                    "unique_count": unique_count,
                    "cardinality_ratio": cardinality_ratio,
                    "avg_length": avg_length,
                    "is_cid_like": cid_like,
                    "recommended_encoding": encoding,
                    "data_type": data_type
                }

            elif isinstance(sample, (int, float)):
                unique_count = len(set(data))
                cardinality_ratio = unique_count / count

                # Calculate basic statistics
                values = np.array(data)
                min_val = np.min(values)
                max_val = np.max(values)
                mean_val = np.mean(values)
                range_val = max_val - min_val

                # Determine if values are sequential or clustered
                sequential = False
                if isinstance(sample, int) and range_val <= 2 * count:
                    # Check for more or less sequential values
                    sorted_vals = sorted(values)
                    gaps = np.diff(sorted_vals)
                    avg_gap = np.mean(gaps)
                    if avg_gap < 10:  # Small average gap suggests sequentiality
                        sequential = True

                # Recommend encoding based on data characteristics
                if isinstance(sample, int):
                    if sequential:
                        encoding = "DELTA_BINARY_PACKED"
                    elif cardinality_ratio < 0.3:
                        encoding = "PLAIN_DICTIONARY"
                    else:
                        encoding = "PLAIN"
                else:  # float
                    encoding = "PLAIN"

                return {
                    "column": name,
                    "count": count,
                    "unique_count": unique_count,
                    "cardinality_ratio": cardinality_ratio,
                    "min": min_val,
                    "max": max_val,
                    "mean": mean_val,
                    "range": range_val,
                    "is_sequential": sequential,
                    "recommended_encoding": encoding,
                    "data_type": data_type
                }

            elif isinstance(sample, bool):
                # Boolean columns are best encoded with RLE
                true_count = sum(1 for x in data if x)
                false_count = count - true_count

                return {
                    "column": name,
                    "count": count,
                    "true_count": true_count,
                    "false_count": false_count,
                    "true_ratio": true_count / count if count > 0 else 0,
                    "recommended_encoding": "RLE",
                    "data_type": data_type
                }

            else:
                # For other types, just use PLAIN encoding
                return {
                    "column": name,
                    "count": count,
                    "data_type": data_type,
                    "recommended_encoding": "PLAIN"
                }

        except Exception as e:
            logger.warning(f"Error analyzing column {name}: {e}")
            return {
                "column": name,
                "count": count,
                "error": str(e),
                "recommended_encoding": "PLAIN",
                "data_type": data_type
            }


class CompressionProfileSelector:
    """Selector for optimal compression profiles based on data characteristics."""

    def __init__(self):
        """Initialize the profile selector."""
        # Create standard profiles
        self.profiles = {
            "default": CompressionProfile("default", "Default balanced profile"),
            "memory_optimized": CompressionProfile("memory_optimized").optimize_for_tier("memory"),
            "disk_optimized": CompressionProfile("disk_optimized").optimize_for_tier("disk"),
            "cloud_optimized": CompressionProfile("cloud_optimized").optimize_for_tier("cloud"),
            "archive_optimized": CompressionProfile("archive_optimized").optimize_for_tier("archive"),
            "read_heavy": CompressionProfile("read_heavy").optimize_for_workload("read_heavy"),
            "write_heavy": CompressionProfile("write_heavy").optimize_for_workload("write_heavy"),
            "analytical": CompressionProfile("analytical").optimize_for_workload("analytical"),
            "metadata": CompressionProfile("metadata").optimize_for_workload("metadata")
        }

        # Create hybrid profiles
        self.profiles["balanced_memory"] = CompressionProfile("balanced_memory")
        self.profiles["balanced_memory"].optimize_for_tier("memory").optimize_for_workload("mixed")

        self.profiles["balanced_disk"] = CompressionProfile("balanced_disk")
        self.profiles["balanced_disk"].optimize_for_tier("disk").optimize_for_workload("mixed")

        self.profiles["cold_analytical"] = CompressionProfile("cold_analytical")
        self.profiles["cold_analytical"].optimize_for_tier("cold").optimize_for_workload("analytical")

    def get_profile(self, name: str) -> CompressionProfile:
        """Get a profile by name.

        Args:
            name: Profile name

        Returns:
            CompressionProfile instance
        """
        if name in self.profiles:
            return self.profiles[name]
        else:
            logger.warning(f"Profile {name} not found. Using default.")
            return self.profiles["default"]

    def select_profile_for_data(self, data: Dict[str, List[Any]],
                              tier: str = "disk",
                              workload: str = "mixed") -> CompressionProfile:
        """Automatically select the best profile based on data characteristics.

        Args:
            data: Dictionary mapping column names to value lists
            tier: Storage tier ("memory", "disk", "cloud", "cold")
            workload: Workload type ("read_heavy", "write_heavy", "analytical", "mixed")

        Returns:
            Selected CompressionProfile instance
        """
        # Analyze column characteristics
        column_analyses = {}
        for column, values in data.items():
            column_analyses[column] = ColumnAnalyzer.analyze_column(values, column)

        # Determine if this is a metadata-heavy workload
        metadata_count = 0
        for col, analysis in column_analyses.items():
            if analysis.get("is_cid_like", False):
                metadata_count += 1
            if "metadata" in col.lower() or "meta" in col.lower():
                metadata_count += 1
            if analysis.get("data_type") == "str" and analysis.get("cardinality_ratio", 1.0) < 0.2:
                metadata_count += 1

        # Start with a tier-based profile
        if tier == "memory":
            profile_name = "memory_optimized"
        elif tier == "disk":
            profile_name = "disk_optimized"
        elif tier == "cloud":
            profile_name = "cloud_optimized"
        elif tier == "cold" or tier == "archive":
            profile_name = "archive_optimized"
        else:
            profile_name = "default"

        # Refine based on workload
        if metadata_count >= len(data) // 3:
            # If a third or more columns look like metadata, use metadata profile
            if workload == "analytical":
                profile_name = "cold_analytical" if tier == "cold" else "analytical"
            else:
                profile_name = "metadata"
        elif workload == "read_heavy":
            profile_name = "read_heavy"
        elif workload == "write_heavy":
            profile_name = "write_heavy"
        elif workload == "analytical":
            profile_name = "analytical"

        # Get the profile
        profile = self.get_profile(profile_name)

        # Customize with column-specific settings
        for column, analysis in column_analyses.items():
            recommended_encoding = analysis.get("recommended_encoding")
            if recommended_encoding:
                # Create column-specific settings
                if analysis.get("is_cid_like", False):
                    # Use CID optimized settings
                    profile.set_column_settings(column, profile.cid_column_settings.copy())
                else:
                    # Use encoding based on analysis
                    profile.set_column_settings(column, {
                        "encoding": recommended_encoding
                    })

        return profile


class ParquetCompressionManager:
    """Manager for optimizing Parquet compression and encoding."""

    def __init__(self):
        """Initialize the compression manager."""
        self.profile_selector = CompressionProfileSelector()
        self.encoding_optimizer = EncodingOptimizer()
        self.current_profile = self.profile_selector.get_profile("default")

    def select_profile(self, name: str) -> CompressionProfile:
        """Select a compression profile by name.

        Args:
            name: Profile name

        Returns:
            Selected profile
        """
        self.current_profile = self.profile_selector.get_profile(name)
        return self.current_profile

    def optimize_write_options(self, table_or_schema: Any, tier: str = "disk",
                              workload: str = "mixed") -> Dict[str, Any]:
        """Optimize write options for a given table or schema.

        Args:
            table_or_schema: PyArrow Table or Schema to optimize for
            tier: Storage tier
            workload: Workload type

        Returns:
            Dictionary of optimized write arguments
        """
        if not HAVE_PYARROW:
            logger.warning("PyArrow not available. Using default write options.")
            return {}

        # Extract schema from table if needed
        schema = None
        if isinstance(table_or_schema, pa.Table):
            schema = table_or_schema.schema
        elif isinstance(table_or_schema, pa.Schema):
            schema = table_or_schema

        # Adjust profile for schema
        if schema:
            self.current_profile.adjust_for_schema(schema)

        # Adjust for tier and workload
        self.current_profile.optimize_for_tier(tier)
        self.current_profile.optimize_for_workload(workload)

        # Generate write args
        return self.current_profile.to_write_args()

    def analyze_dataset(self, file_path: str) -> Dict[str, Any]:
        """Analyze an existing Parquet dataset for optimization opportunities.

        Args:
            file_path: Path to Parquet file or directory

        Returns:
            Dictionary with analysis results
        """
        if not HAVE_PYARROW:
            return {"error": "PyArrow not available"}

        try:
            # Load dataset metadata
            ds = dataset(file_path, format="parquet")
            schema = ds.schema

            # Read actual column data for a sample
            table = ds.head(1000)  # Sample first 1000 rows

            # Analyze each column
            column_analyses = {}
            for column in table.column_names:
                values = table[column].to_pylist()
                column_analyses[column] = ColumnAnalyzer.analyze_column(values, column)

            # Get file metadata
            if os.path.isfile(file_path):
                metadata = pq.read_metadata(file_path)
                file_size = os.path.getsize(file_path)
                row_count = metadata.num_rows
                row_group_count = metadata.num_row_groups

                # Get compression and encoding info
                compression_info = {}
                encoding_info = {}

                for i in range(metadata.num_columns):
                    col_path = metadata.column_path_at_index(i)
                    col_name = ".".join(col_path)
                    compression_info[col_name] = metadata.column(i).compression

                    # Get encodings for each column (if available)
                    if hasattr(metadata.column(i), 'encodings'):
                        encoding_info[col_name] = metadata.column(i).encodings
            else:
                # Directory of parquet files
                file_size = sum(os.path.getsize(os.path.join(file_path, f))
                                for f in os.listdir(file_path)
                                if f.endswith('.parquet'))
                row_count = "Unknown (multiple files)"
                row_group_count = "Unknown (multiple files)"
                compression_info = {}
                encoding_info = {}

            # Generate optimization recommendations
            recommendations = self._generate_recommendations(
                column_analyses, compression_info, encoding_info)

            return {
                "file_path": file_path,
                "file_size": file_size,
                "row_count": row_count,
                "row_group_count": row_group_count,
                "schema": schema,
                "compression_info": compression_info,
                "encoding_info": encoding_info,
                "column_analyses": column_analyses,
                "recommendations": recommendations
            }

        except Exception as e:
            logger.error(f"Error analyzing dataset: {e}")
            return {"error": str(e)}

    def _generate_recommendations(self, column_analyses, compression_info, encoding_info):
        """Generate optimization recommendations based on analysis.

        Args:
            column_analyses: Analyses of column data
            compression_info: Current compression settings
            encoding_info: Current encoding settings

        Returns:
            Dictionary with recommendations
        """
        recommendations = {
            "compression": {},
            "encoding": {},
            "general": []
        }

        # Identify suboptimal compression
        for col, info in compression_info.items():
            analysis = column_analyses.get(col, {})
            data_type = analysis.get("data_type", "unknown")

            if data_type == "str":
                if analysis.get("is_cid_like", False) and info != "zstd":
                    recommendations["compression"][col] = "zstd"
                elif analysis.get("cardinality_ratio", 1.0) < 0.2 and info != "zstd":
                    recommendations["compression"][col] = "zstd"
            elif data_type == "int" and analysis.get("is_sequential", False) and info != "lz4":
                recommendations["compression"][col] = "lz4"

        # Identify suboptimal encoding
        for col, info in encoding_info.items():
            analysis = column_analyses.get(col, {})
            recommended = analysis.get("recommended_encoding")

            if recommended and recommended not in info:
                recommendations["encoding"][col] = recommended

        # General recommendations
        if not encoding_info or not compression_info:
            recommendations["general"].append(
                "No detailed compression/encoding info available. "
                "Rewrite with optimized settings for best performance."
            )

        # Check for small row groups
        if isinstance(compression_info, dict) and len(compression_info) > 0:
            recommendations["general"].append(
                "Consider using larger row groups for better compression "
                "and reduced metadata overhead."
            )

        # Check for high-cardinality columns using dictionary encoding
        high_card_dict_cols = []
        for col, analysis in column_analyses.items():
            if (analysis.get("cardinality_ratio", 0) > 0.7 and
                col in encoding_info and
                "DICTIONARY" in str(encoding_info[col])):
                high_card_dict_cols.append(col)

        if high_card_dict_cols:
            recommendations["general"].append(
                f"Columns with high cardinality using dictionary encoding: "
                f"{', '.join(high_card_dict_cols)}. Consider using PLAIN encoding instead."
            )

        # Check for CID columns not using specialized encoding
        cid_cols = [col for col, analysis in column_analyses.items()
                   if analysis.get("is_cid_like", False)]

        if cid_cols:
            recommendations["general"].append(
                f"CID-like columns detected: {', '.join(cid_cols)}. "
                f"Consider using specialized CID encoding for optimal storage."
            )

        return recommendations

    def optimize_dataset(self, input_path: str, output_path: str, profile_name: str = None,
                        tier: str = "disk", workload: str = "mixed") -> Dict[str, Any]:
        """Rewrite a dataset with optimized compression and encoding.

        Args:
            input_path: Path to input Parquet file
            output_path: Path to output optimized file
            profile_name: Name of compression profile to use
            tier: Storage tier to optimize for
            workload: Workload type to optimize for

        Returns:
            Dictionary with optimization results
        """
        if not HAVE_PYARROW:
            return {"error": "PyArrow not available"}

        try:
            # Select profile
            if profile_name:
                self.select_profile(profile_name)

            # Load data
            input_size = os.path.getsize(input_path)
            table = pq.read_table(input_path)

            # Get optimized write options
            write_options = self.optimize_write_options(table, tier, workload)

            # Write optimized file
            pq.write_table(table, output_path, **write_options)
            output_size = os.path.getsize(output_path)

            # Calculate compression ratio
            compression_ratio = input_size / output_size if output_size > 0 else 1.0

            # Return results
            return {
                "success": True,
                "input_path": input_path,
                "output_path": output_path,
                "input_size": input_size,
                "output_size": output_size,
                "compression_ratio": compression_ratio,
                "profile_used": self.current_profile.name,
                "write_options": write_options
            }

        except Exception as e:
            logger.error(f"Error optimizing dataset: {e}")
            return {"error": str(e), "success": False}


# Create global instances for convenience
compression_profiles = CompressionProfileSelector()
parquet_compression = ParquetCompressionManager()
