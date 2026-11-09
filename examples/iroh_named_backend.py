"""Create and inspect a validated named Iroh backend without starting it."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from ipfs_kit_py.backend_manager import BackendManager


def main() -> None:
    root = Path(os.environ.get("IPFS_KIT_PATH", "~/.ipfs_kit")).expanduser()
    example = Path(__file__).resolve().parents[1] / "config" / "iroh-backend.example.yaml"
    document = yaml.safe_load(example.read_text(encoding="utf-8"))
    manager = BackendManager(root)
    result = manager.create_backend(
        document.pop("name"), document.pop("type"), config=document
    )
    if "error" in result and result.get("code") != "backend_exists":
        raise SystemExit(result["error"])

    # Manager output is safe for logs: credential record identifiers are
    # redacted. The opaque references remain intact in the owner-only YAML.
    print(json.dumps(manager.get_backend_info("team_archive"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
