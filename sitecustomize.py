"""Ensure local repo packages take precedence in tests.

Python automatically imports sitecustomize if it is on sys.path.
We prepend the repo root so the local `mcp` package is preferred
over any third-party package with the same name.
"""

from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent
repo_root_str = str(repo_root)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

# If a third-party `mcp` was already imported, drop it so local imports resolve.
mod = sys.modules.get("mcp")
if mod is not None:
    mod_path = getattr(mod, "__file__", "") or ""
    if repo_root_str not in mod_path:
        sys.modules.pop("mcp", None)
