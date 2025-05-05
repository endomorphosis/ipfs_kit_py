"""IPFS MCP Tools Registry - Created from scratch"""

IPFS_TOOLS = [
    # Original IPFS MFS Tools
    {
        "name": "ipfs_files_ls",
        "description": "List files and directories in the IPFS MFS (Mutable File System)",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path within MFS to list (default: /)",
                    "default": "/"
                },
                "long": {
                    "type": "boolean",
                    "description": "Use long listing format (include size, type)",
                    "default": False
                }
            }
        }
    },
    {
        "name": "ipfs_files_mkdir",
        "description": "Create directories in the IPFS MFS (Mutable File System)",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to create within MFS"
                },
                "parents": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist",
                    "default": True
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "ipfs_files_write",
        "description": "Write data to a file in the IPFS MFS (Mutable File System)",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path within MFS to write to"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "create": {
                    "type": "boolean",
                    "description": "Create the file if it doesn't exist",
                    "default": True
                },
                "truncate": {
                    "type": "boolean",
                    "description": "Truncate the file if it already exists",
                    "default": True
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "ipfs_files_read",
        "description": "Read a file from the IPFS MFS (Mutable File System)",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path within MFS to read from"
                },
                "offset": {
                    "type": "integer",
                    "description": "Byte offset to start reading from",
                    "default": 0
                },
                "count": {
                    "type": "integer",
                    "description": "Maximum number of bytes to read",
                    "default": -1
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "ipfs_files_rm",
        "description": "Remove files or directories from the IPFS MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path within MFS to remove"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Recursively remove directories",
                    "default": False
                },
                "force": {
                    "type": "boolean",
                    "description": "Forcibly remove the file/directory",
                    "default": False
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "ipfs_files_stat",
        "description": "Get information about a file or directory in the MFS",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path within MFS to get stats for"
                },
                "with_local": {
                    "type": "boolean",
                    "description": "Compute the amount of the dag that is local",
                    "default": False
                },
                "size": {
                    "type": "boolean",
                    "description": "Compute the total size of the dag",
                    "default": True
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "ipfs_files_cp",
        "description": "Copy files within the IPFS MFS",
        "schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source path (can be an MFS or IPFS path)"
                },
                "dest": {
                    "type": "string",
                    "description": "Destination path within MFS"
                }
            },
            "required": ["source", "dest"]
        }
    },
    {
        "name": "ipfs_files_mv",
        "description": "Move files within the IPFS MFS",
        "schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source path (must be an MFS path)"
                },
                "dest": {
                    "type": "string",
                    "description": "Destination path within MFS"
                }
            },
            "required": ["source", "dest"]
        }
    },
    {
        "name": "ipfs_name_publish",
        "description": "Publish an IPNS name",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "IPFS path to publish"
                },
                "resolve": {
                    "type": "boolean",
                    "description": "Resolve before publishing",
                    "default": True
                },
                "lifetime": {
                    "type": "string",
                    "description": "Time duration that the record will be valid for",
                    "default": "24h"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "ipfs_name_resolve",
        "description": "Resolve an IPNS name",
        "schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The IPNS name to resolve"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Resolve until the result is not an IPNS name",
                    "default": True
                },
                "nocache": {
                    "type": "boolean",
                    "description": "Do not use cached entries",
                    "default": False
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "ipfs_dag_put",
        "description": "Add a DAG node to IPFS",
        "schema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "The data to store as a DAG node"
                },
                "format": {
                    "type": "string",
                    "description": "The format to use for the DAG node",
                    "default": "cbor",
                    "enum": ["cbor", "json", "raw"]
                },
                "input_codec": {
                    "type": "string",
                    "description": "The codec that the input data is encoded with",
                    "default": "json"
                },
                "pin": {
                    "type": "boolean",
                    "description": "Pin this object when adding",
                    "default": False
                }
            },
            "required": ["data"]
        }
    },
    {
        "name": "ipfs_dag_get",
        "description": "Get a DAG node from IPFS",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "The CID of the DAG node to get"
                },
                "path": {
                    "type": "string",
                    "description": "The path within the DAG structure to retrieve",
                    "default": ""
                }
            },
            "required": ["cid"]
        }
    },
    
    # New FS Journal Tools
    {
        "name": "fs_journal_get_history",
        "description": "Get the operation history for a path in the virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to get history for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of history entries to return",
                    "default": 10
                },
                "operation_types": {
                    "type": "array",
                    "description": "Filter by operation types (read, write, etc.)",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "fs_journal_sync",
        "description": "Force synchronization between virtual filesystem and actual storage",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to sync (defaults to entire filesystem)",
                    "default": "/"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to sync recursively",
                    "default": True
                }
            }
        }
    },
    
    # IPFS Bridge Tools
    {
        "name": "ipfs_fs_bridge_status",
        "description": "Get the status of the IPFS-FS bridge",
        "schema": {
            "type": "object",
            "properties": {
                "detailed": {
                    "type": "boolean",
                    "description": "Whether to include detailed information",
                    "default": False
                }
            }
        }
    },
    {
        "name": "ipfs_fs_bridge_sync",
        "description": "Sync between IPFS and virtual filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to sync",
                    "default": "/"
                },
                "direction": {
                    "type": "string",
                    "description": "Sync direction: to_ipfs, from_ipfs, or both",
                    "enum": ["to_ipfs", "from_ipfs", "both"],
                    "default": "both"
                }
            }
        }
    },
    
    # S3 Storage Tools
    {
        "name": "s3_store_file",
        "description": "Store a file to S3 storage",
        "schema": {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "Local path of the file to store"
                },
                "bucket": {
                    "type": "string",
                    "description": "S3 bucket name"
                },
                "key": {
                    "type": "string",
                    "description": "S3 object key"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata for the object"
                }
            },
            "required": ["local_path", "bucket", "key"]
        }
    },
    {
        "name": "s3_retrieve_file",
        "description": "Retrieve a file from S3 storage",
        "schema": {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "Local path to save the file"
                },
                "bucket": {
                    "type": "string",
                    "description": "S3 bucket name"
                },
                "key": {
                    "type": "string",
                    "description": "S3 object key"
                }
            },
            "required": ["local_path", "bucket", "key"]
        }
    },
    
    # Filecoin Storage Tools
    {
        "name": "filecoin_store_file",
        "description": "Store a file to Filecoin storage",
        "schema": {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "Local path of the file to store"
                },
                "replication": {
                    "type": "integer",
                    "description": "Number of replicas to store",
                    "default": 1
                },
                "duration": {
                    "type": "integer",
                    "description": "Storage duration in days",
                    "default": 180
                }
            },
            "required": ["local_path"]
        }
    },
    {
        "name": "filecoin_retrieve_deal",
        "description": "Retrieve a file from Filecoin storage by deal ID",
        "schema": {
            "type": "object",
            "properties": {
                "deal_id": {
                    "type": "string",
                    "description": "Filecoin deal ID"
                },
                "local_path": {
                    "type": "string",
                    "description": "Local path to save the file"
                }
            },
            "required": ["deal_id", "local_path"]
        }
    },
    
    # HuggingFace Integration Tools
    {
        "name": "huggingface_model_load",
        "description": "Load a model from HuggingFace",
        "schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "HuggingFace model ID"
                },
                "task": {
                    "type": "string",
                    "description": "Task type (translation, summarization, etc.)",
                    "default": "text-generation"
                },
                "cache_dir": {
                    "type": "string",
                    "description": "Directory to cache the model"
                }
            },
            "required": ["model_id"]
        }
    },
    {
        "name": "huggingface_model_inference",
        "description": "Run inference on a loaded HuggingFace model",
        "schema": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "HuggingFace model ID"
                },
                "input_text": {
                    "type": "string",
                    "description": "Input text for the model"
                },
                "parameters": {
                    "type": "object",
                    "description": "Additional parameters for the model"
                }
            },
            "required": ["model_id", "input_text"]
        }
    },
    
    # WebRTC Tools
    {
        "name": "webrtc_peer_connect",
        "description": "Connect to another peer via WebRTC",
        "schema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "ID of the peer to connect to"
                },
                "signaling_server": {
                    "type": "string",
                    "description": "Signaling server URL",
                    "default": "wss://signaling.ipfs.io"
                },
                "ice_servers": {
                    "type": "array",
                    "description": "STUN/TURN servers to use",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": ["peer_id"]
        }
    },
    {
        "name": "webrtc_send_data",
        "description": "Send data to a connected WebRTC peer",
        "schema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "ID of the peer to send data to"
                },
                "data": {
                    "type": "string",
                    "description": "Data to send to the peer"
                },
                "data_type": {
                    "type": "string",
                    "description": "Type of data being sent",
                    "enum": ["text", "binary", "json"],
                    "default": "text"
                }
            },
            "required": ["peer_id", "data"]
        }
    },
    
    # Credential Management Tools
    {
        "name": "credential_store",
        "description": "Store a credential for a specific service",
        "schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service the credential is for"
                },
                "credential_type": {
                    "type": "string",
                    "description": "Type of credential",
                    "enum": ["api_key", "oauth_token", "username_password", "jwt", "other"],
                    "default": "api_key"
                },
                "credential_data": {
                    "type": "object",
                    "description": "Credential data"
                },
                "expires_at": {
                    "type": "string",
                    "description": "ISO8601 timestamp when the credential expires (optional)"
                }
            },
            "required": ["service", "credential_data"]
        }
    },
    {
        "name": "credential_retrieve",
        "description": "Retrieve a credential for a specific service",
        "schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service to retrieve credential for"
                },
                "credential_type": {
                    "type": "string",
                    "description": "Type of credential to retrieve",
                    "enum": ["api_key", "oauth_token", "username_password", "jwt", "other"],
                    "default": "api_key"
                }
            },
            "required": ["service"]
        }
    }
,

    # ipfs_pubsub_publish
    {
        "name": "ipfs_pubsub_publish",
        "description": "Publish messages to an IPFS pubsub topic",
        "schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to publish to"
                },
                "message": {
                    "type": "string",
                    "description": "The message content to publish"
                }
            },
            "required": [
                "topic",
                "message"
            ]
        }
    },

    # ipfs_pubsub_subscribe
    {
        "name": "ipfs_pubsub_subscribe",
        "description": "Subscribe to messages on an IPFS pubsub topic",
        "schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to subscribe to"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (0 for no timeout)",
                    "default": 30
                }
            },
            "required": [
                "topic"
            ]
        }
    },

    # ipfs_dht_findpeer
    {
        "name": "ipfs_dht_findpeer",
        "description": "Find a peer in the IPFS DHT",
        "schema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "The peer ID to find"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 30
                }
            },
            "required": [
                "peer_id"
            ]
        }
    },

    # ipfs_dht_findprovs
    {
        "name": "ipfs_dht_findprovs",
        "description": "Find providers for a given CID in the IPFS DHT",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "The CID to find providers for"
                },
                "num_providers": {
                    "type": "integer",
                    "description": "Maximum number of providers to find",
                    "default": 20
                }
            },
            "required": [
                "cid"
            ]
        }
    },

    # ipfs_cluster_pin
    {
        "name": "ipfs_cluster_pin",
        "description": "Pin a CID across the IPFS cluster",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "The CID to pin in the cluster"
                },
                "name": {
                    "type": "string",
                    "description": "Optional name for the pinned item"
                },
                "replication_factor": {
                    "type": "integer",
                    "description": "Number of nodes to replicate the pin to",
                    "default": -1
                }
            },
            "required": [
                "cid"
            ]
        }
    },

    # ipfs_cluster_status
    {
        "name": "ipfs_cluster_status",
        "description": "Get the status of a CID in the IPFS cluster",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "The CID to check status for"
                },
                "local": {
                    "type": "boolean",
                    "description": "Show only local information",
                    "default": False
                }
            },
            "required": [
                "cid"
            ]
        }
    },

    # ipfs_cluster_peers
    {
        "name": "ipfs_cluster_peers",
        "description": "List peers in the IPFS cluster",
        "schema": {
            "type": "object",
            "properties": {}
        }
    },

    # lassie_fetch
    {
        "name": "lassie_fetch",
        "description": "Fetch content using Lassie content retrieval from Filecoin and IPFS",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "The CID to fetch"
                },
                "output_path": {
                    "type": "string",
                    "description": "Local path to save the fetched content"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 300
                },
                "include_ipni": {
                    "type": "boolean",
                    "description": "Include IPNI indexers in retrieval",
                    "default": True
                }
            },
            "required": [
                "cid",
                "output_path"
            ]
        }
    },

    # lassie_fetch_with_providers
    {
        "name": "lassie_fetch_with_providers",
        "description": "Fetch content using Lassie with specific providers",
        "schema": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "The CID to fetch"
                },
                "providers": {
                    "type": "array",
                    "description": "List of provider addresses",
                    "items": {
                        "type": "string"
                    }
                },
                "output_path": {
                    "type": "string",
                    "description": "Local path to save the fetched content"
                }
            },
            "required": [
                "cid",
                "providers",
                "output_path"
            ]
        }
    },

    # ai_model_register
    {
        "name": "ai_model_register",
        "description": "Register an AI model with IPFS and metadata",
        "schema": {
            "type": "object",
            "properties": {
                "model_path": {
                    "type": "string",
                    "description": "Path to the model file or directory"
                },
                "model_name": {
                    "type": "string",
                    "description": "Name of the model"
                },
                "model_type": {
                    "type": "string",
                    "description": "Type of model (classification, segmentation, etc.)"
                },
                "version": {
                    "type": "string",
                    "description": "Model version",
                    "default": "1.0.0"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional model metadata"
                }
            },
            "required": [
                "model_path",
                "model_name",
                "model_type"
            ]
        }
    },

    # ai_dataset_register
    {
        "name": "ai_dataset_register",
        "description": "Register a dataset with IPFS and metadata",
        "schema": {
            "type": "object",
            "properties": {
                "dataset_path": {
                    "type": "string",
                    "description": "Path to the dataset file or directory"
                },
                "dataset_name": {
                    "type": "string",
                    "description": "Name of the dataset"
                },
                "dataset_type": {
                    "type": "string",
                    "description": "Type of dataset (images, text, etc.)"
                },
                "version": {
                    "type": "string",
                    "description": "Dataset version",
                    "default": "1.0.0"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional dataset metadata"
                }
            },
            "required": [
                "dataset_path",
                "dataset_name",
                "dataset_type"
            ]
        }
    },

    # search_content
    {
        "name": "search_content",
        "description": "Search indexed content across IPFS and storage backends",
        "schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "content_types": {
                    "type": "array",
                    "description": "Content types to search for",
                    "items": {
                        "type": "string",
                        "enum": [
                            "document",
                            "image",
                            "video",
                            "audio",
                            "code",
                            "all"
                        ]
                    },
                    "default": [
                        "all"
                    ]
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 50
                }
            },
            "required": [
                "query"
            ]
        }
    },

    # storacha_store
    {
        "name": "storacha_store",
        "description": "Store content using Storacha distributed storage",
        "schema": {
            "type": "object",
            "properties": {
                "content_path": {
                    "type": "string",
                    "description": "Path to the content to store"
                },
                "replication": {
                    "type": "integer",
                    "description": "Replication factor",
                    "default": 3
                },
                "encryption": {
                    "type": "boolean",
                    "description": "Whether to encrypt the content",
                    "default": True
                }
            },
            "required": [
                "content_path"
            ]
        }
    },

    # storacha_retrieve
    {
        "name": "storacha_retrieve",
        "description": "Retrieve content from Storacha distributed storage",
        "schema": {
            "type": "object",
            "properties": {
                "content_id": {
                    "type": "string",
                    "description": "Storacha content ID"
                },
                "output_path": {
                    "type": "string",
                    "description": "Path to save the retrieved content"
                }
            },
            "required": [
                "content_id",
                "output_path"
            ]
        }
    },

    # multi_backend_add_backend
    {
        "name": "multi_backend_add_backend",
        "description": "Add a new storage backend to the multi-backend filesystem",
        "schema": {
            "type": "object",
            "properties": {
                "backend_type": {
                    "type": "string",
                    "description": "Type of backend",
                    "enum": [
                        "ipfs",
                        "filecoin",
                        "s3",
                        "storacha",
                        "huggingface",
                        "ipfs_cluster",
                        "local"
                    ]
                },
                "backend_name": {
                    "type": "string",
                    "description": "Name for the backend"
                },
                "mount_point": {
                    "type": "string",
                    "description": "Virtual filesystem mount point",
                    "default": "/"
                },
                "config": {
                    "type": "object",
                    "description": "Backend-specific configuration"
                }
            },
            "required": [
                "backend_type",
                "backend_name"
            ]
        }
    },

    # multi_backend_list_backends
    {
        "name": "multi_backend_list_backends",
        "description": "List all configured storage backends",
        "schema": {
            "type": "object",
            "properties": {
                "include_status": {
                    "type": "boolean",
                    "description": "Include status information",
                    "default": True
                },
                "include_stats": {
                    "type": "boolean",
                    "description": "Include usage statistics",
                    "default": False
                }
            }
        }
    },

    # streaming_create_stream
    {
        "name": "streaming_create_stream",
        "description": "Create a new data stream",
        "schema": {
            "type": "object",
            "properties": {
                "stream_name": {
                    "type": "string",
                    "description": "Name for the stream"
                },
                "stream_type": {
                    "type": "string",
                    "description": "Type of stream",
                    "enum": [
                        "pubsub",
                        "unidir",
                        "bidir"
                    ],
                    "default": "pubsub"
                },
                "metadata": {
                    "type": "object",
                    "description": "Stream metadata"
                }
            },
            "required": [
                "stream_name"
            ]
        }
    },

    # streaming_publish
    {
        "name": "streaming_publish",
        "description": "Publish data to a stream",
        "schema": {
            "type": "object",
            "properties": {
                "stream_name": {
                    "type": "string",
                    "description": "Name of the stream"
                },
                "data": {
                    "type": "string",
                    "description": "Data to publish"
                },
                "content_type": {
                    "type": "string",
                    "description": "Content type of the data",
                    "default": "text/plain"
                }
            },
            "required": [
                "stream_name",
                "data"
            ]
        }
    },

    # monitoring_get_metrics
    {
        "name": "monitoring_get_metrics",
        "description": "Get monitoring metrics",
        "schema": {
            "type": "object",
            "properties": {
                "metric_type": {
                    "type": "string",
                    "description": "Type of metrics to retrieve",
                    "enum": [
                        "system",
                        "ipfs",
                        "filecoin",
                        "storage",
                        "all"
                    ],
                    "default": "all"
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range for metrics",
                    "enum": [
                        "1h",
                        "24h",
                        "7d",
                        "30d"
                    ],
                    "default": "24h"
                }
            }
        }
    },

    # monitoring_create_alert
    {
        "name": "monitoring_create_alert",
        "description": "Create a monitoring alert",
        "schema": {
            "type": "object",
            "properties": {
                "alert_name": {
                    "type": "string",
                    "description": "Name for the alert"
                },
                "metric": {
                    "type": "string",
                    "description": "Metric to monitor"
                },
                "condition": {
                    "type": "string",
                    "description": "Alert condition (e.g., '> 90%')"
                },
                "notification_channel": {
                    "type": "string",
                    "description": "Channel for notifications",
                    "enum": [
                        "email",
                        "slack",
                        "webhook",
                        "console"
                    ],
                    "default": "console"
                },
                "notification_config": {
                    "type": "object",
                    "description": "Channel-specific configuration"
                }
            },
            "required": [
                "alert_name",
                "metric",
                "condition"
            ]
        }
    }]

def get_ipfs_tools():
    """Get all IPFS tool definitions"""
    return IPFS_TOOLS
