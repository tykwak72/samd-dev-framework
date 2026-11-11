#!/usr/bin/env python3
"""
session_start_banner.py - Antigravity SessionStart Hook for SaMD Framework

When starting a new conversation session, inspects active projects (projects/*)
and DHF hash chain integrity in the workspace, injecting them into initial context (systemMessage).
"""

import sys
import json
from pathlib import Path


def main() -> None:
    try:
        _ = sys.stdin.read()
        hooks_dir = Path(__file__).resolve().parent
        workspace_root = hooks_dir.parent.parent
        projects_dir = workspace_root / "projects"

        project_summaries = []
        if projects_dir.exists() and projects_dir.is_dir():
            sys.path.insert(0, str(workspace_root))
            from dhf_cli import DHFManager

            for proj_path in sorted(projects_dir.iterdir()):
                if proj_path.is_dir() and (proj_path / "store").exists():
                    mgr = DHFManager(workspace_root=proj_path)
                    valid, _ = mgr.verify_audit_history()
                    status_str = "VALID" if valid else "COMPROMISED"
                    project_summaries.append(f"{proj_path.name} (DHF Integrity: {status_str})")

        proj_info = ", ".join(project_summaries) if project_summaries else "None (Run bootstrap_project.py or dhf_cli.py init)"
        banner = (
            f"[SaMD Dev Framework Active] IEC 62304 / ISO 14971 / FDA CSA Governance Enabled. "
            f"Isolated Projects: [{proj_info}]. "
            f"All DHF mutations MUST go through 'dhf_cli.py -p projects/<slug>' and Stage gates through 'gatekeeper.py'."
        )

        output = {
            "injectSteps": [
                {
                    "systemMessage": {
                        "systemMessage": banner
                    }
                }
            ]
        }
        print(json.dumps(output, ensure_ascii=False))
    except Exception:
        print(json.dumps({}))


if __name__ == "__main__":
    main()
