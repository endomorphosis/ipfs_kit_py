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
  "cluster_status": {
    "category": "cluster_tools",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "description": "Get IPFS cluster status"
  }
};

export class IpfsKitMcpClient {
  constructor(endpoint = "http://127.0.0.1:8004") { this.endpoint = endpoint; this._id = 0; }
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
