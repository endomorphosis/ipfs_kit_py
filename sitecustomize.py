"""Ensure local repo packages take precedence in tests.

Python automatically imports sitecustomize if it is on sys.path.
We prepend the repo root so the local `mcp` package is preferred
over any third-party package with the same name.
"""

from __future__ import annotations

import sys
import os
import types
from pathlib import Path


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _bootstrap_symai_engines() -> None:
    if not _truthy(os.environ.get("IPFS_DATASETS_PY_SYMAI_SITEBOOT")):
        return

    # Keep this best-effort and lazy to avoid affecting normal imports.
    try:
        import symai  # noqa: F401
        from symai.functional import EngineRepository
    except Exception:
        return

    use_codex = _truthy(os.environ.get("IPFS_DATASETS_PY_USE_CODEX_FOR_SYMAI"))
    model_value = os.environ.get("NEUROSYMBOLIC_ENGINE_MODEL", "")
    if str(model_value).startswith("codex:"):
        use_codex = True

    if use_codex:
        try:
            from ipfs_datasets_py.utils.symai_codex_engine import CodexExecNeurosymbolicEngine

            EngineRepository.register(
                "neurosymbolic",
                CodexExecNeurosymbolicEngine(),
                allow_engine_override=True,
            )
        except Exception:
            # Never fail interpreter startup due to registration issues.
            return

    if _truthy(os.environ.get("IPFS_DATASETS_PY_USE_SYMAI_ENGINE_ROUTER")):
        try:
            from ipfs_datasets_py.utils.symai_ipfs_engine import register_ipfs_symai_engines

            register_ipfs_symai_engines()
        except Exception:
            return

repo_root = Path(__file__).resolve().parent.parent
repo_root_str = str(repo_root)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

_bootstrap_symai_engines()

# If a third-party `mcp` was already imported, drop it so local imports resolve.
mod = sys.modules.get("mcp")
if mod is not None:
    mod_path = getattr(mod, "__file__", "") or ""
    if repo_root_str not in mod_path:
        sys.modules.pop("mcp", None)

# Provide a lightweight stub for legacy MCP imports during pytest to avoid
# slow, dependency-heavy imports in subprocess-based tests.
if os.environ.get("PYTEST_CURRENT_TEST"):
    stub_name = "enhanced_mcp_server_with_daemon_mgmt"
    if stub_name not in sys.modules:
        stub = types.ModuleType(stub_name)

        class GraphRAGSearchEngine:  # type: ignore
            def __init__(self, *args, **kwargs):
                self._indexed = []

            def get_search_stats(self):
                return {
                    "vector_search_available": False,
                    "graph_search_available": False,
                    "sparql_available": False,
                    "total_indexed_content": len(self._indexed),
                    "knowledge_graph_nodes": 0,
                    "knowledge_graph_edges": 0,
                    "rdf_triples": 0,
                }

            async def index_content(self, **kwargs):
                self._indexed.append(kwargs)
                return {"success": True, "indexed": len(self._indexed)}

            async def text_search(self, *args, **kwargs):
                return {"success": False, "error": "text_search not implemented", "results": []}

        stub.GraphRAGSearchEngine = GraphRAGSearchEngine
        sys.modules[stub_name] = stub
