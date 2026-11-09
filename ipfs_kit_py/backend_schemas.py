"""
Backend Configuration Schemas

This file defines the configuration schemas for each supported backend.
These schemas are used to dynamically generate configuration forms in the dashboard.
"""

SCHEMAS = {
    "s3": {
        "name": "S3",
        "fields": {
            "access_key": {"type": "password", "required": True},
            "secret_key": {"type": "password", "required": True},
            "region": {"type": "text", "required": True},
            "endpoint": {"type": "text", "required": False},
        },
    },
    "huggingface": {
        "name": "HuggingFace",
        "fields": {
            "token": {"type": "password", "required": True},
            "default_org": {"type": "text", "required": False},
            "cache_dir": {"type": "text", "required": False},
        },
    },
    "storacha": {
        "name": "Storacha",
        "fields": {
            "api_key": {"type": "password", "required": True},
            "endpoint": {"type": "text", "required": False},
        },
    },
    "ipfs": {
        "name": "IPFS",
        "fields": {
            "api_endpoint": {"type": "text", "required": True, "default": "/ip4/127.0.0.1/tcp/5001"},
        },
    },
    "filecoin": {
        "name": "Filecoin",
        "fields": {
            "lotus_rpc_url": {"type": "text", "required": True},
            "lotus_token": {"type": "password", "required": True},
        },
    },
    "gdrive": {
        "name": "Google Drive",
        "fields": {
            "credentials_path": {"type": "text", "required": True},
            "default_folder_id": {"type": "text", "required": False},
        },
    },
    "github": {
        "name": "GitHub",
        "fields": {
            "token": {"type": "password", "required": True},
            "default_org": {"type": "text", "required": False},
            "default_repo": {"type": "text", "required": False},
        },
    },
    "ipfs-cluster": {
        "name": "IPFS Cluster",
        "fields": {
            "endpoint": {"type": "text", "required": True},
            "username": {"type": "text", "required": False},
            "password": {"type": "password", "required": False},
        },
    },
    "ipfs-cluster-follow": {
        "name": "IPFS Cluster Follow",
        "fields": {
            "name": {"type": "text", "required": True},
            "template": {"type": "text", "required": False},
            "trusted_peers": {"type": "text", "required": False},
        },
    },
    "lotus": {
        "name": "Lotus",
        "fields": {
            "endpoint": {"type": "text", "required": True},
            "token": {"type": "password", "required": True},
        },
    },
    "lassie": {
        "name": "Lassie",
        "fields": {},
    },
    "arrow": {
        "name": "Arrow",
        "fields": {
            "memory_pool": {"type": "select", "choices": ["system", "jemalloc"], "default": "system"},
            "thread_count": {"type": "number", "required": False},
        },
    },
    "parquet": {
        "name": "Parquet",
        "fields": {
            "storage_path": {"type": "text", "required": True},
            "compression": {"type": "select", "choices": ["snappy", "gzip", "brotli", "lz4"], "default": "snappy"},
            "batch_size": {"type": "number", "default": 10000},
        },
    },
    "sshfs": {
        "name": "SSHFS",
        "fields": {
            "hostname": {"type": "text", "required": True},
            "username": {"type": "text", "required": True},
            "port": {"type": "number", "default": 22},
            "password": {"type": "password", "required": False},
            "private_key": {"type": "text", "required": False},
            "remote_path": {"type": "text", "default": "/tmp/ipfs_kit"},
        },
    },
    "ftp": {
        "name": "FTP",
        "fields": {
            "host": {"type": "text", "required": True},
            "username": {"type": "text", "required": True},
            "password": {"type": "password", "required": True},
            "port": {"type": "number", "default": 21},
            "use_tls": {"type": "checkbox", "default": False},
            "passive": {"type": "checkbox", "default": True},
            "remote_path": {"type": "text", "default": "/"},
        },
    },
}