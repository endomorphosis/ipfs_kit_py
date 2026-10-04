#!/usr/bin/env python3
import shutil
from pathlib import Path
import argparse
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
DOCS_DASHBOARD_DIR = DOCS_DIR / "dashboard"
ARCHIVE_TMP_DIR = ROOT / "archive" / "tmp_root"
ARCHIVE_MISC_DIR = ROOT / "archive" / "root_misc"

MD_TO_DASHBOARD = re.compile(r"^(ENHANCED_|DASHBOARD_|MCP_START_|DASHBOARD_JS_FIX|DASHBOARD_STANDALONE|DASHBOARD_FEATURE|DASHBOARD_IMPLEMENTATION|ENHANCED_MCP)", re.I)

def plan_moves():
    moves = []

    # 1) Markdown docs in root
    for f in ROOT.glob("*.md"):
        # Skip top-level README if you want it to stay
        if f.name.lower() == "readme.md":
            continue
        target_dir = DOCS_DASHBOARD_DIR if MD_TO_DASHBOARD.match(f.name) else DOCS_DIR
        moves.append((f, target_dir / f.name))

    # 2) Temp scratch files
    for pattern in ["*.tmp", ".tmp_*", "*.fixed"]:
        for f in ROOT.glob(pattern):
            moves.append((f, ARCHIVE_TMP_DIR / f.name))

    # 3) Stray JS/python helpers in root (archive them)
    for f in [ROOT / "app_generated.js",
              ROOT / "analyze_root_organization.py"]:
        if f.exists():
            moves.append((f, ARCHIVE_MISC_DIR / f.name))

    return moves

def ensure_dirs(paths):
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)

def do_move(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))

def main():
    parser = argparse.ArgumentParser(description="Reorganize loose root files safely.")
    parser.add_argument("--apply", action="store_true", help="Perform moves (default is dry-run)")
    args = parser.parse_args()

    moves = plan_moves()
    targets = {dst.parent for _, dst in moves}
    ensure_dirs(targets)

    print("Planned moves:")
    for src, dst in moves:
        print(f"  - {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")

    if not args.apply:
        print("\nDry-run complete. Re-run with --apply to perform moves.")
        return 0

    for src, dst in moves:
        if not src.exists():
            print(f"SKIP (missing): {src}")
            continue
        print(f"MOVE: {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
        do_move(src, dst)

    print("\nReorganization complete.")
    return 0

if __name__ == "__main__":
    sys.exit(main())