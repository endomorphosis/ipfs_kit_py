"""
Utility functions for IPFS Kit cluster management.
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Try to import GPU support
try:
    import pynvml

    HAS_GPU_SUPPORT = True
except ImportError:
    HAS_GPU_SUPPORT = False


def get_gpu_info():
    """Get information about available GPUs.

    Attempts to detect NVIDIA GPUs using pynvml if available.

    Returns:
        Dictionary with GPU information or None if not available
    """
    if not HAS_GPU_SUPPORT:
        return None

    try:
        # Initialize NVML
        pynvml.nvmlInit()

        # Get device count
        device_count = pynvml.nvmlDeviceGetCount()

        if device_count == 0:
            return None

        # Get information for each device
        gpu_info = {"gpu_count": device_count, "gpu_available": True, "gpu_devices": []}

        total_memory = 0
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            name = (
                pynvml.nvmlDeviceGetName(handle).decode("utf-8")
                if isinstance(pynvml.nvmlDeviceGetName(handle), bytes)
                else pynvml.nvmlDeviceGetName(handle)
            )

            device_info = {
                "name": name,
                "memory_total": info.total,
                "memory_free": info.free,
                "memory_used": info.used,
            }

            gpu_info["gpu_devices"].append(device_info)
            total_memory += info.total

        gpu_info["gpu_memory_total"] = total_memory

        # Shutdown NVML
        pynvml.nvmlShutdown()

        return gpu_info

    except Exception as e:
        logger.debug(f"Error getting GPU information: {str(e)}")
        return None
