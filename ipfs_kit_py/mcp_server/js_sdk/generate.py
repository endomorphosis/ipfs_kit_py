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

export class IpfsKitMcpClient {{
  constructor(endpoint = "http://127.0.0.1:8004") {{ this.endpoint = endpoint; this._id = 0; }}
  async _rpc(method, params) {{
    const res = await fetch(this.endpoint, {{
      method: "POST", headers: {{ "content-type": "application/json" }},
      body: JSON.stringify({{ jsonrpc: "2.0", id: ++this._id, method, params }}),
    }});
    const j = await res.json();
    if (j.error) throw new Error(j.error.message);
    return j.result;
  }}
  listTools() {{ return this._rpc("tools/list", {{}}); }}
  call(name, args = {{}}) {{ return this._rpc("tools/call", {{ name, arguments: args }}); }}
}}
"""


SDK_PATH = Path(__file__).parent / "ipfs-kit-mcp-sdk.js"
MANIFEST_PATH = Path(__file__).parent / "tools-manifest.json"


def render() -> str:
    tm = HierarchicalToolManager()
    tools = {s["name"]: {"category": s["category"], "inputSchema": s["inputSchema"],
                         "description": s["description"]} for s in tm.all_tool_schemas()}
    return TEMPLATE.format(tools=json.dumps(tools, indent=2))


def render_manifest() -> str:
    tm = HierarchicalToolManager()
    return json.dumps({"version": "0.1.0", "tools": tm.all_tool_schemas()}, indent=2)


def main() -> None:
    SDK_PATH.write_text(render())
    # Emit a JSON manifest too, so non-JS consumers (e.g. the swissknife
    # dashboard descriptor pack) read the identical tool registry.
    MANIFEST_PATH.write_text(render_manifest())
    print(f"wrote {SDK_PATH} + tools-manifest.json")


if __name__ == "__main__":
    main()
