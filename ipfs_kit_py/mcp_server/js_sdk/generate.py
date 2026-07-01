"""Generate the JavaScript MCP SDK from the canonical Python tool registry.

Emits ipfs-kit-mcp-sdk.js so the dashboard reuses the exact same tool names and
input schemas the Python server exposes — no second hand-maintained tool list.
Run: python -m ipfs_kit_py.mcp_server.js_sdk.generate
"""
from __future__ import annotations

import json
from pathlib import Path

from ..hierarchical_tool_manager import HierarchicalToolManager

TEMPLATE = """// AUTO-GENERATED from ipfs_kit_py.mcp_server tool registry. Do not edit.
// Mirrors the Python tool defs so the dashboard and server share one contract.
export const TOOLS = {tools};

// Unwrap an MCP CallToolResult envelope back to the raw tool payload.
function _unwrapToolResult(result) {{
  if (result && typeof result === "object" && !Array.isArray(result)
      && Array.isArray(result.content) && "structuredContent" in result) {{
    const sc = result.structuredContent;
    if (sc && typeof sc === "object" && !Array.isArray(sc)
        && Object.keys(sc).length === 1 && "result" in sc) return sc.result;
    return sc;
  }}
  return result;
}}

export class IpfsKitMcpClient {{
  // `options.transport` may supply a pluggable transport exposing
  // `async request(jsonRpcRequest) -> jsonRpcResponse` (e.g. MCP++ over libp2p
  // via mcpp-client.js `Libp2pTransport`). When omitted, JSON-RPC is sent over
  // HTTP fetch to `endpoint`.
  constructor(endpoint = "http://127.0.0.1:8004/mcp", options = {{}}) {{
    this.endpoint = endpoint;
    this._id = 0;
    this.transport = (options && options.transport) || null;
  }}
  async _rpc(method, params) {{
    const req = {{ jsonrpc: "2.0", id: ++this._id, method, params }};
    let j;
    if (this.transport) {{
      j = await this.transport.request(req);
    }} else {{
      const res = await fetch(this.endpoint, {{
        method: "POST", headers: {{ "content-type": "application/json" }},
        body: JSON.stringify(req),
      }});
      j = await res.json();
    }}
    if (j && j.error) throw new Error(j.error.message);
    return j ? j.result : undefined;
  }}
  async _callUnwrapped(name, args = {{}}) {{ return _unwrapToolResult(await this._rpc("tools/call", {{ name, arguments: args }})); }}
  listTools() {{ return this._rpc("tools/list", {{}}); }}
  // Accepts a bare name, a dotted `<category>.<tool>` name, or a meta-tool name.
  call(name, args = {{}}) {{ return this._rpc("tools/call", {{ name, arguments: args }}); }}
  // Hierarchical tool facade helpers (meta-tools). Results are unwrapped from
  // the CallToolResult envelope for convenience.
  listCategories(includeCount = true) {{ return this._callUnwrapped("tools_list_categories", {{ include_count: includeCount }}); }}
  listToolsInCategory(category) {{ return this._callUnwrapped("tools_list_tools", {{ category }}); }}
  getToolSchema(nameOrTool) {{ return this._callUnwrapped("tools_get_schema", typeof nameOrTool === "string" ? {{ name: nameOrTool }} : (nameOrTool || {{}})); }}
  dispatch(category, tool, params = {{}}) {{ return this._callUnwrapped("tools_dispatch", {{ category, tool, params }}); }}
}}
"""


SDK_PATH = Path(__file__).parent / "ipfs-kit-mcp-sdk.js"
TS_SDK_PATH = Path(__file__).parent / "ipfs-kit-mcp-sdk.ts"
MANIFEST_PATH = Path(__file__).parent / "tools-manifest.json"

TS_TEMPLATE = """// AUTO-GENERATED from ipfs_kit_py.mcp_server tool registry. Do not edit.
// Typed mirror of the Python tool defs so SwissKnife shares one contract.
export const TOOLS = {tools} as const;

export type ToolName = keyof typeof TOOLS;

export interface RpcResult {{ status?: string; [k: string]: unknown; }}

/** Pluggable transport (e.g. MCP++ over libp2p). */
export interface McpTransport {{
  request(req: {{ jsonrpc: string; id: number; method: string; params: Record<string, unknown> }}): Promise<any>;
}}

function _unwrapToolResult(result: any): any {{
  if (result && typeof result === "object" && !Array.isArray(result)
      && Array.isArray(result.content) && "structuredContent" in result) {{
    const sc = result.structuredContent;
    if (sc && typeof sc === "object" && !Array.isArray(sc)
        && Object.keys(sc).length === 1 && "result" in sc) return sc.result;
    return sc;
  }}
  return result;
}}

export class IpfsKitMcpClient {{
  endpoint: string;
  transport: McpTransport | null;
  private _id = 0;
  constructor(endpoint = "http://127.0.0.1:8004/mcp", options: {{ transport?: McpTransport }} = {{}}) {{
    this.endpoint = endpoint;
    this.transport = options.transport ?? null;
  }}
  private async _rpc(method: string, params: Record<string, unknown>): Promise<any> {{
    const req = {{ jsonrpc: "2.0", id: ++this._id, method, params }};
    let j: any;
    if (this.transport) {{
      j = await this.transport.request(req);
    }} else {{
      const res = await fetch(this.endpoint, {{
        method: "POST", headers: {{ "content-type": "application/json" }},
        body: JSON.stringify(req),
      }});
      j = await res.json();
    }}
    if (j && j.error) throw new Error(j.error.message);
    return j ? j.result : undefined;
  }}
  private async _callUnwrapped(name: string, args: Record<string, unknown> = {{}}): Promise<any> {{
    return _unwrapToolResult(await this._rpc("tools/call", {{ name, arguments: args }}));
  }}
  listTools(): Promise<{{ tools: unknown[] }}> {{ return this._rpc("tools/list", {{}}); }}
  /** Accepts a bare name, a dotted `<category>.<tool>` name, or a meta-tool name. */
  call(name: ToolName | string, args: Record<string, unknown> = {{}}): Promise<RpcResult> {{
    return this._rpc("tools/call", {{ name, arguments: args }});
  }}
  // Hierarchical tool facade helpers (meta-tools), unwrapped for convenience.
  listCategories(includeCount = true): Promise<any> {{ return this._callUnwrapped("tools_list_categories", {{ include_count: includeCount }}); }}
  listToolsInCategory(category: string): Promise<any> {{ return this._callUnwrapped("tools_list_tools", {{ category }}); }}
  getToolSchema(nameOrTool: string | Record<string, unknown>): Promise<any> {{
    return this._callUnwrapped("tools_get_schema", typeof nameOrTool === "string" ? {{ name: nameOrTool }} : (nameOrTool || {{}}));
  }}
  dispatch(category: string, tool: string, params: Record<string, unknown> = {{}}): Promise<any> {{
    return this._callUnwrapped("tools_dispatch", {{ category, tool, params }});
  }}
}}
"""


def render() -> str:
    tm = HierarchicalToolManager()
    tools = {s["name"]: {"category": s["category"], "inputSchema": s["inputSchema"],
                         "description": s["description"]} for s in tm.all_tool_schemas()}
    return TEMPLATE.format(tools=json.dumps(tools, indent=2))


def render_ts() -> str:
    tm = HierarchicalToolManager()
    tools = {s["name"]: {"category": s["category"], "inputSchema": s["inputSchema"],
                         "description": s["description"]} for s in tm.all_tool_schemas()}
    return TS_TEMPLATE.format(tools=json.dumps(tools, indent=2))


def render_manifest() -> str:
    tm = HierarchicalToolManager()
    return json.dumps({"version": "0.1.0", "tools": tm.all_tool_schemas()}, indent=2)


def main() -> None:
    SDK_PATH.write_text(render())
    TS_SDK_PATH.write_text(render_ts())
    # Emit a JSON manifest too, so non-JS consumers (e.g. the swissknife
    # dashboard descriptor pack) read the identical tool registry.
    MANIFEST_PATH.write_text(render_manifest())
    print(f"wrote {SDK_PATH} + .ts + tools-manifest.json")


if __name__ == "__main__":
    main()
