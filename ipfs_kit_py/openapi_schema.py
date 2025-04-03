"""
OpenAPI schema for the IPFS Kit API.

This module defines the OpenAPI schema for the REST API server,
providing a structured definition of all available endpoints,
request and response formats, and data models.
"""

# Define the OpenAPI schema as a dictionary
openapi_schema = {
    "openapi": "3.0.3",
    "info": {
        "title": "IPFS Kit API",
        "description": "API for interacting with IPFS (InterPlanetary File System) through IPFS Kit",
        "version": "0.1.1",
        "contact": {
            "name": "IPFS Kit Team",
            "email": "info@example.com",
            "url": "https://github.com/endomorphosis/ipfs_kit_py"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    },
    "servers": [
        {
            "url": "http://localhost:8000",
            "description": "Local development server"
        }
    ],
    "paths": {
        "/health": {
            "get": {
                "summary": "Check server health",
                "description": "Returns health status and version information",
                "operationId": "checkHealth",
                "tags": ["System"],
                "responses": {
                    "200": {
                        "description": "Health status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "ok"
                                        },
                                        "version": {
                                            "type": "string",
                                            "example": "0.1.1"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/{method_name}": {
            "post": {
                "summary": "Call any API method dynamically",
                "description": "Invokes any method in the IPFSSimpleAPI by name",
                "operationId": "callMethodByName",
                "tags": ["Generic"],
                "parameters": [
                    {
                        "name": "method_name",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string"
                        },
                        "description": "Name of the method to call"
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "args": {
                                        "type": "array",
                                        "items": {
                                            "type": "object"
                                        },
                                        "description": "Positional arguments"
                                    },
                                    "kwargs": {
                                        "type": "object",
                                        "additionalProperties": True,
                                        "description": "Keyword arguments"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Method response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean"
                                        }
                                    },
                                    "additionalProperties": True
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/add": {
            "post": {
                "summary": "Add content to IPFS",
                "description": "Adds a file or data to IPFS and returns its CID",
                "operationId": "addContent",
                "tags": ["Content"],
                "requestBody": {
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "File to add to IPFS"
                                    },
                                    "pin": {
                                        "type": "boolean",
                                        "default": True,
                                        "description": "Whether to pin the content"
                                    },
                                    "wrap_with_directory": {
                                        "type": "boolean",
                                        "default": False,
                                        "description": "Whether to wrap the file in a directory"
                                    }
                                },
                                "required": ["file"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Add operation result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "cid": {
                                            "type": "string",
                                            "example": "QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM"
                                        },
                                        "name": {
                                            "type": "string",
                                            "example": "example.txt"
                                        },
                                        "size": {
                                            "type": "integer",
                                            "example": 1024
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/cat": {
            "get": {
                "summary": "Retrieve content by CID",
                "description": "Fetches content from IPFS by its Content Identifier",
                "operationId": "getContent",
                "tags": ["Content"],
                "parameters": [
                    {
                        "name": "arg",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string"
                        },
                        "description": "The CID of the content to retrieve"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Content data",
                        "content": {
                            "*/*": {
                                "schema": {
                                    "type": "string",
                                    "format": "binary"
                                }
                            }
                        }
                    },
                    "404": {
                        "description": "Content not found",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/ls": {
            "get": {
                "summary": "List directory contents",
                "description": "Lists the contents of an IPFS directory by its CID",
                "operationId": "listDirectory",
                "tags": ["Content"],
                "parameters": [
                    {
                        "name": "arg",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string"
                        },
                        "description": "The CID of the directory to list"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Directory listing",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "entries": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {
                                                        "type": "string",
                                                        "example": "example.txt"
                                                    },
                                                    "type": {
                                                        "type": "string",
                                                        "example": "file"
                                                    },
                                                    "size": {
                                                        "type": "integer",
                                                        "example": 1024
                                                    },
                                                    "cid": {
                                                        "type": "string",
                                                        "example": "QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM"
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "404": {
                        "description": "Directory not found",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/pin/add": {
            "post": {
                "summary": "Pin content",
                "description": "Pins content to the local IPFS node to prevent garbage collection",
                "operationId": "pinContent",
                "tags": ["Pin"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "cid": {
                                        "type": "string",
                                        "description": "CID of content to pin"
                                    },
                                    "recursive": {
                                        "type": "boolean",
                                        "default": True,
                                        "description": "Pin recursively"
                                    }
                                },
                                "required": ["cid"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Pin operation result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "pins": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "example": ["QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM"]
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/pin/rm": {
            "post": {
                "summary": "Unpin content",
                "description": "Unpins content from the local IPFS node",
                "operationId": "unpinContent",
                "tags": ["Pin"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "cid": {
                                        "type": "string",
                                        "description": "CID of content to unpin"
                                    },
                                    "recursive": {
                                        "type": "boolean",
                                        "default": True,
                                        "description": "Unpin recursively"
                                    }
                                },
                                "required": ["cid"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Unpin operation result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "pins": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "example": ["QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM"]
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/pin/ls": {
            "get": {
                "summary": "List pinned content",
                "description": "Lists content pinned to the local IPFS node",
                "operationId": "listPins",
                "tags": ["Pin"],
                "parameters": [
                    {
                        "name": "type",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "enum": ["all", "direct", "recursive", "indirect"],
                            "default": "all"
                        },
                        "description": "Type of pins to list"
                    },
                    {
                        "name": "quiet",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean",
                            "default": False
                        },
                        "description": "Return only pin hashes"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of pins",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "pins": {
                                            "type": "object",
                                            "additionalProperties": {
                                                "type": "object",
                                                "properties": {
                                                    "type": {
                                                        "type": "string",
                                                        "example": "recursive"
                                                    }
                                                }
                                            },
                                            "example": {
                                                "QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM": {
                                                    "type": "recursive"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/name/publish": {
            "post": {
                "summary": "Publish to IPNS",
                "description": "Publishes an IPFS path to IPNS with the node's key",
                "operationId": "publishToIPNS",
                "tags": ["IPNS"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "path": {
                                        "type": "string",
                                        "description": "IPFS path to publish",
                                        "example": "/ipfs/QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM"
                                    },
                                    "key": {
                                        "type": "string",
                                        "description": "Name of the key to use",
                                        "default": "self"
                                    },
                                    "lifetime": {
                                        "type": "string",
                                        "description": "Time duration that the record will be valid",
                                        "default": "24h"
                                    },
                                    "ttl": {
                                        "type": "string",
                                        "description": "Time duration for caching the record",
                                        "default": "1h"
                                    }
                                },
                                "required": ["path"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Publish operation result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "name": {
                                            "type": "string",
                                            "example": "QmYCvbfNbCwFR45HiNP45rwJgvatpiW38D961L5qAhUM5Y"
                                        },
                                        "value": {
                                            "type": "string",
                                            "example": "/ipfs/QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/name/resolve": {
            "get": {
                "summary": "Resolve IPNS name",
                "description": "Resolves an IPNS name to its corresponding IPFS path",
                "operationId": "resolveIPNS",
                "tags": ["IPNS"],
                "parameters": [
                    {
                        "name": "arg",
                        "in": "query",
                        "required": True,
                        "schema": {
                            "type": "string"
                        },
                        "description": "The IPNS name to resolve",
                        "example": "/ipns/QmYCvbfNbCwFR45HiNP45rwJgvatpiW38D961L5qAhUM5Y"
                    },
                    {
                        "name": "recursive",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean",
                            "default": True
                        },
                        "description": "Resolve recursively"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Resolution result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "path": {
                                            "type": "string",
                                            "example": "/ipfs/QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/id": {
            "get": {
                "summary": "Get node identity",
                "description": "Returns the identity of the local IPFS node",
                "operationId": "getNodeIdentity",
                "tags": ["Node"],
                "responses": {
                    "200": {
                        "description": "Node identity information",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "id": {
                                            "type": "string",
                                            "example": "QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"
                                        },
                                        "addresses": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "example": [
                                                "/ip4/127.0.0.1/tcp/4001/p2p/QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"
                                            ]
                                        },
                                        "agent_version": {
                                            "type": "string",
                                            "example": "kubo/0.18.0"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/swarm/peers": {
            "get": {
                "summary": "List connected peers",
                "description": "Lists peers connected to the local IPFS node",
                "operationId": "listPeers",
                "tags": ["Node"],
                "parameters": [
                    {
                        "name": "verbose",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean",
                            "default": False
                        },
                        "description": "Display all extra information"
                    },
                    {
                        "name": "latency",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean",
                            "default": False
                        },
                        "description": "Display information about latency"
                    },
                    {
                        "name": "direction",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "boolean",
                            "default": False
                        },
                        "description": "Display information about connection direction"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of peers",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "peers": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "peer": {
                                                        "type": "string"
                                                    },
                                                    "addr": {
                                                        "type": "string"
                                                    },
                                                    "latency": {
                                                        "type": "string"
                                                    },
                                                    "direction": {
                                                        "type": "string"
                                                    }
                                                }
                                            }
                                        },
                                        "count": {
                                            "type": "integer",
                                            "example": 42
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/swarm/connect": {
            "post": {
                "summary": "Connect to peer",
                "description": "Connects to a peer by its multiaddress",
                "operationId": "connectToPeer",
                "tags": ["Node"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "addr": {
                                        "type": "string",
                                        "description": "Multiaddress of peer to connect to",
                                        "example": "/ip4/1.2.3.4/tcp/4001/p2p/QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"
                                    }
                                },
                                "required": ["addr"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Connection result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "added": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "example": [
                                                "/ip4/1.2.3.4/tcp/4001/p2p/QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/cluster/peers": {
            "get": {
                "summary": "List cluster peers",
                "description": "Lists peers in the IPFS cluster (master/worker role only)",
                "operationId": "listClusterPeers",
                "tags": ["Cluster"],
                "responses": {
                    "200": {
                        "description": "List of cluster peers",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "peers": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {
                                                        "type": "string"
                                                    },
                                                    "addresses": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "string"
                                                        }
                                                    },
                                                    "role": {
                                                        "type": "string",
                                                        "enum": ["master", "worker", "leecher"]
                                                    }
                                                }
                                            }
                                        },
                                        "count": {
                                            "type": "integer",
                                            "example": 5
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    },
                    "403": {
                        "description": "Permission denied - requires master or worker role",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/cluster/pin/add": {
            "post": {
                "summary": "Pin content to cluster",
                "description": "Pins content across the IPFS cluster (master/worker role only)",
                "operationId": "pinToCluster",
                "tags": ["Cluster"],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "cid": {
                                        "type": "string",
                                        "description": "CID of content to pin"
                                    },
                                    "replication_factor": {
                                        "type": "integer",
                                        "default": 1,
                                        "description": "Number of nodes to replicate across"
                                    },
                                    "name": {
                                        "type": "string",
                                        "description": "Optional name for the pinned content"
                                    }
                                },
                                "required": ["cid"]
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Cluster pin operation result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "cid": {
                                            "type": "string",
                                            "example": "QmXG8yk8UJjMT6qtE2zSxzz3U7z5jSYRgVWLCUFqAVnByM"
                                        },
                                        "peers": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            },
                                            "example": ["12D3KooWA1b3VJmnwdzJZKcQpjxgd1RD9wr5QzvYx1XdkypQJV5d"]
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    },
                    "403": {
                        "description": "Permission denied - requires master or worker role",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/v0/cluster/status": {
            "get": {
                "summary": "Get cluster pin status",
                "description": "Gets the status of pins in the IPFS cluster (master/worker role only)",
                "operationId": "getClusterStatus",
                "tags": ["Cluster"],
                "parameters": [
                    {
                        "name": "arg",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string"
                        },
                        "description": "CID to check status for (all pins if not specified)"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Cluster pin status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True
                                        },
                                        "status": {
                                            "type": "object",
                                            "additionalProperties": {
                                                "type": "object",
                                                "properties": {
                                                    "cid": {
                                                        "type": "string"
                                                    },
                                                    "name": {
                                                        "type": "string"
                                                    },
                                                    "status": {
                                                        "type": "string",
                                                        "enum": ["pinned", "pinning", "unpinned", "queued", "failed"]
                                                    },
                                                    "peer_map": {
                                                        "type": "object",
                                                        "additionalProperties": {
                                                            "type": "object",
                                                            "properties": {
                                                                "status": {
                                                                    "type": "string"
                                                                },
                                                                "timestamp": {
                                                                    "type": "string"
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Error response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    },
                    "403": {
                        "description": "Permission denied - requires master or worker role",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ErrorResponse"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/metrics": {
            "get": {
                "summary": "Get Prometheus metrics",
                "description": "Returns metrics in Prometheus format for monitoring",
                "operationId": "getMetrics",
                "tags": ["System"],
                "responses": {
                    "200": {
                        "description": "Prometheus metrics",
                        "content": {
                            "text/plain": {
                                "schema": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": False
                    },
                    "error": {
                        "type": "string",
                        "example": "Detailed error message"
                    },
                    "error_type": {
                        "type": "string",
                        "example": "IPFSError"
                    },
                    "status_code": {
                        "type": "integer",
                        "example": 400
                    }
                }
            }
        },
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key"
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer"
            },
            "BasicAuth": {
                "type": "http",
                "scheme": "basic"
            }
        }
    },
    "security": [
        {
            "ApiKeyAuth": []
        },
        {
            "BearerAuth": []
        },
        {
            "BasicAuth": []
        }
    ],
    "tags": [
        {
            "name": "System",
            "description": "System-level operations"
        },
        {
            "name": "Generic",
            "description": "Generic API operations"
        },
        {
            "name": "Content",
            "description": "Content management operations"
        },
        {
            "name": "Pin",
            "description": "Pin management operations"
        },
        {
            "name": "IPNS",
            "description": "IPNS operations"
        },
        {
            "name": "Node",
            "description": "IPFS node operations"
        },
        {
            "name": "Cluster",
            "description": "IPFS cluster operations"
        }
    ]
}

# Function to get the OpenAPI schema
def get_openapi_schema():
    """
    Returns the OpenAPI schema for the REST API server.
    
    Returns:
        dict: OpenAPI schema dictionary
    """
    return openapi_schema