// AUTO-GENERATED from ipfs_kit_py.mcp_server tool registry. Do not edit.
// Mirrors the Python tool defs so the dashboard and server share one contract.
export const TOOLS = {
  "ipfs_add": {
    "category": "ipfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string"
        },
        "recursive": {
          "type": "boolean",
          "default": false
        }
      },
      "required": [
        "file_path"
      ]
    },
    "description": "Add a file to IPFS and return its CID"
  },
  "ipfs_cat": {
    "category": "ipfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "cid": {
          "type": "string"
        }
      },
      "required": [
        "cid"
      ]
    },
    "description": "Retrieve content from IPFS by CID"
  },
  "ipfs_ls": {
    "category": "ipfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        }
      },
      "required": [
        "path"
      ]
    },
    "description": "List entries under an IPFS path"
  },
  "pin_add": {
    "category": "pin_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "cid": {
          "type": "string"
        },
        "recursive": {
          "type": "boolean",
          "default": true
        }
      },
      "required": [
        "cid"
      ]
    },
    "description": "Pin a CID to the local node"
  },
  "pin_ls": {
    "category": "pin_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "List pinned CIDs"
  },
  "pin_rm": {
    "category": "pin_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "cid": {
          "type": "string"
        },
        "recursive": {
          "type": "boolean",
          "default": true
        }
      },
      "required": [
        "cid"
      ]
    },
    "description": "Unpin a CID from the local node"
  },
  "get_pinset": {
    "category": "pin_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "Get full pinset (local + cluster)"
  },
  "dag_get": {
    "category": "dag_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "cid": {
          "type": "string"
        }
      },
      "required": [
        "cid"
      ]
    },
    "description": "Get a DAG node by CID"
  },
  "dag_put": {
    "category": "dag_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "data": {
          "type": "object"
        }
      },
      "required": [
        "data"
      ]
    },
    "description": "Put a DAG node, returns CID"
  },
  "files_ls": {
    "category": "mfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "default": "/"
        },
        "long": {
          "type": "boolean",
          "default": false
        }
      }
    },
    "description": "List an MFS directory"
  },
  "files_mkdir": {
    "category": "mfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        },
        "parents": {
          "type": "boolean",
          "default": false
        }
      },
      "required": [
        "path"
      ]
    },
    "description": "Make an MFS directory"
  },
  "files_stat": {
    "category": "mfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        }
      },
      "required": [
        "path"
      ]
    },
    "description": "Stat an MFS path"
  },
  "files_write": {
    "category": "mfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        },
        "content": {
          "type": "string"
        }
      },
      "required": [
        "path",
        "content"
      ]
    },
    "description": "Write content to an MFS path"
  },
  "files_read": {
    "category": "mfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        }
      },
      "required": [
        "path"
      ]
    },
    "description": "Read content from an MFS path"
  },
  "files_rm": {
    "category": "mfs_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        }
      },
      "required": [
        "path"
      ]
    },
    "description": "Remove an MFS path"
  },
  "node_id": {
    "category": "swarm_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "Get local node identity"
  },
  "swarm_peers": {
    "category": "swarm_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "List connected swarm peers"
  },
  "name_publish": {
    "category": "name_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string"
        }
      },
      "required": [
        "path"
      ]
    },
    "description": "Publish a path to IPNS"
  },
  "name_resolve": {
    "category": "name_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "Resolve an IPNS name to a path"
  },
  "create_car": {
    "category": "car_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "roots": {
          "type": "string"
        }
      },
      "required": [
        "roots"
      ]
    },
    "description": "Create a CAR archive from roots"
  },
  "cluster_status": {
    "category": "cluster_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "Get IPFS cluster status"
  },
  "block_put": {
    "category": "block_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "data": {
          "type": "string"
        }
      },
      "required": [
        "data"
      ]
    },
    "description": "Store a raw block and return its CID"
  },
  "block_get": {
    "category": "block_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "cid": {
          "type": "string"
        }
      },
      "required": [
        "cid"
      ]
    },
    "description": "Fetch a raw block by CID"
  },
  "block_stat": {
    "category": "block_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "cid": {
          "type": "string"
        }
      },
      "required": [
        "cid"
      ]
    },
    "description": "Report size of a raw block"
  },
  "bitswap_stat": {
    "category": "bitswap_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "Show bitswap exchange statistics"
  },
  "bitswap_wantlist": {
    "category": "bitswap_tools",
    "inputSchema": {
      "type": "object",
      "properties": {
        "peer": {
          "type": "string",
          "default": null
        }
      }
    },
    "description": "Show blocks currently on the wantlist"
  },
  "stats_bw": {
    "category": "stats_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "Report node bandwidth statistics"
  },
  "stats_repo": {
    "category": "stats_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "Report local repo statistics"
  }
};

export class IpfsKitMcpClient {
  constructor(endpoint = "http://127.0.0.1:8004/mcp") { this.endpoint = endpoint; this._id = 0; }
  async _rpc(method, params) {
    const res = await fetch(this.endpoint, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: ++this._id, method, params }),
    });
    const j = await res.json();
    if (j.error) throw new Error(j.error.message);
    return j.result;
  }
  listTools() { return this._rpc("tools/list", {}); }
  call(name, args = {}) { return this._rpc("tools/call", { name, arguments: args }); }
}
