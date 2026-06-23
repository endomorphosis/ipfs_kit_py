"""Compatibility mock used by fsspec integration tests."""


class MockIPFSFileSystem:
    protocol = "ipfs"

    def __init__(
        self,
        ipfs_path=None,
        socket_path=None,
        role="leecher",
        cache_config=None,
        use_mmap=True,
        enable_metrics=True,
        **kwargs,
    ):
        self.ipfs_path = ipfs_path
        self.socket_path = socket_path
        self.role = role
        self.cache_config = cache_config
        self.use_mmap = use_mmap
        self.enable_metrics = enable_metrics
        self.kwargs = kwargs
