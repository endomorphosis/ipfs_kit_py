// AUTO-GENERATED from ipfs_kit_py.mcp_server tool registry. Do not edit.
// Typed mirror of the Python tool defs so SwissKnife shares one contract.
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
} as const;

export type ToolName = keyof typeof TOOLS;

export interface RpcResult { status?: string; [k: string]: unknown; }

/** Pluggable transport (e.g. MCP++ over libp2p). */
export interface McpTransport {
  request(req: { jsonrpc: string; id: number; method: string; params: Record<string, unknown> }): Promise<any>;
}

function _unwrapToolResult(result: any): any {
  if (result && typeof result === "object" && !Array.isArray(result)
      && Array.isArray(result.content) && "structuredContent" in result) {
    const sc = result.structuredContent;
    if (sc && typeof sc === "object" && !Array.isArray(sc)
        && Object.keys(sc).length === 1 && "result" in sc) return sc.result;
    return sc;
  }
  return result;
}

export class IpfsKitMcpClient {
  endpoint: string;
  transport: McpTransport | null;
  private _id = 0;
  constructor(endpoint = "http://127.0.0.1:8004/mcp", options: { transport?: McpTransport } = {}) {
    this.endpoint = endpoint;
    this.transport = options.transport ?? null;
  }
  private async _rpc(method: string, params: Record<string, unknown>): Promise<any> {
    const req = { jsonrpc: "2.0", id: ++this._id, method, params };
    let j: any;
    if (this.transport) {
      j = await this.transport.request(req);
    } else {
      const res = await fetch(this.endpoint, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify(req),
      });
      j = await res.json();
    }
    if (j && j.error) throw new Error(j.error.message);
    return j ? j.result : undefined;
  }
  private async _callUnwrapped(name: string, args: Record<string, unknown> = {}): Promise<any> {
    return _unwrapToolResult(await this._rpc("tools/call", { name, arguments: args }));
  }
  listTools(): Promise<{ tools: unknown[] }> { return this._rpc("tools/list", {}); }
  /** Accepts a bare name, a dotted `<category>.<tool>` name, or a meta-tool name. */
  call(name: ToolName | string, args: Record<string, unknown> = {}): Promise<RpcResult> {
    return this._rpc("tools/call", { name, arguments: args });
  }
  // Hierarchical tool facade helpers (meta-tools), unwrapped for convenience.
  listCategories(includeCount = true): Promise<any> { return this._callUnwrapped("tools_list_categories", { include_count: includeCount }); }
  listToolsInCategory(category: string): Promise<any> { return this._callUnwrapped("tools_list_tools", { category }); }
  getToolSchema(nameOrTool: string | Record<string, unknown>): Promise<any> {
    return this._callUnwrapped("tools_get_schema", typeof nameOrTool === "string" ? { name: nameOrTool } : (nameOrTool || {}));
  }
  dispatch(category: string, tool: string, params: Record<string, unknown> = {}): Promise<any> {
    return this._callUnwrapped("tools_dispatch", { category, tool, params });
  }
}
