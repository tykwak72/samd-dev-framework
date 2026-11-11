#!/usr/bin/env python3
"""
bootstrap_project.py - Bootstrap script for isolated SaMD project sandbox initialization

Usage:
  python3 .agents/skills/samd-orchestrator/scripts/bootstrap_project.py --slug <project_slug>
"""

import sys
import re
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap an isolated SaMD project sandbox")
    parser.add_argument("--slug", required=True, help="Project directory slug (e.g., ecg_arrhythmia_detector)")
    parser.add_argument("--force", action="store_true", help="Re-initialize DHF store even if it exists")
    args = parser.parse_args()

    if not re.match(r"^[a-zA-Z0-9_-]+$", args.slug):
        print(f"Error: Invalid project slug '{args.slug}'. Use alphanumeric, underscore, or hyphen.", file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parent.parent.parent.parent
    sys.path.insert(0, str(workspace_root))

    from dhf_cli import DHFManager

    project_dir = workspace_root / "projects" / args.slug
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)

    # Generate __init__.py (guarantee package import)
    for sub in ("src", "tests"):
        init_py = project_dir / sub / "__init__.py"
        if not init_py.exists():
            init_py.write_text("", encoding="utf-8")

    mgr = DHFManager(workspace_root=project_dir)
    mgr.init_store(force=args.force)

    print(f"Successfully bootstrapped isolated SaMD project at: {project_dir}")
    print(f"  - Store : {project_dir / 'store'}")
    print(f"  - Docs  : {project_dir / 'docs'}")
    print(f"  - Src   : {project_dir / 'src'}")
    print(f"  - Tests : {project_dir / 'tests'}")


if __name__ == "__main__":
    main()
