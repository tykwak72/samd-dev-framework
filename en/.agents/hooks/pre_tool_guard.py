#!/usr/bin/env python3
"""
pre_tool_guard.py - Antigravity PreToolUse Lifecycle Hook for SaMD DHF Integrity

To comply with ISO 13485 (4.1.6 / 4.2.4) & FDA 21 CFR Part 11 / CSA,
mechanically intercepts and denies attempts by AI agents to directly modify
(bypass the CLI) store/*.json, audit_history.jsonl, or automatically generated
docs/*.md regulatory reports using write_file or edit_file tools.
"""

import sys
import json
import re
from pathlib import Path

PROTECTED_DOC_PREFIXES = (
    "00_SDP_",
    "01_URS_",
    "02_SRS_",
    "03_RMF_",
    "04_SAD_SDS_",
    "05_VNV_",
    "VT_Manual_Test_Checklist",
    "99_RTM_",
)


def check_path_violation(target_path_str: str) -> str:
    """
    Checks if the target path is a blocked path and returns the reason (returns empty string if valid)
    """
    if not target_path_str:
        return ""

    try:
        norm_path = Path(target_path_str).resolve().as_posix()
    except Exception:
        norm_path = target_path_str.replace("\\", "/")

    # Allow unit test file manipulation within temporary directory (/tmp/)
    if norm_path.startswith("/tmp/") or "/tmp/" in norm_path:
        return ""

    parts = [p for p in norm_path.split("/") if p]
    if not parts:
        return ""

    filename = parts[-1]
    parent_dir = parts[-2] if len(parts) >= 2 else ""

    # 1. Block direct writing/editing of JSON, JSONL, and lock files inside store/ directory
    if parent_dir == "store" and (
        filename.endswith(".json")
        or filename.endswith(".jsonl")
        or filename == ".dhf.lock"
    ):
        return (
            f"[ISO 13485 & 21 CFR Part 11 Guard] Direct modification of DHF store file '{filename}' "
            f"via write_file/edit_file is strictly prohibited. "
            f"You MUST use 'python3 dhf_cli.py -p <project_dir> put ...' or 'create-baseline' "
            f"to preserve SHA-256 hash chain integrity and Single Ownership enforcement."
        )

    # 2. Block direct writing/editing of automatically rendered regulatory reports inside docs/ directory
    if parent_dir == "docs" and filename.endswith(".md"):
        if filename.startswith(PROTECTED_DOC_PREFIXES):
            return (
                f"[ISO 13485 Document Control Guard] Direct modification of rendered regulatory report '{filename}' "
                f"is prohibited. Update the source DHF items via 'dhf_cli.py put' and run "
                f"'python3 dhf_cli.py -p <project_dir> render-docs'."
            )

    return ""


def main() -> None:
    try:
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print(json.dumps({"decision": "allow"}))
            return

        payload = json.loads(raw_input)
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {}) or {}

        if tool_name in ("write_file", "edit_file"):
            target_path = args.get("Path") or args.get("path") or ""
            violation_reason = check_path_violation(target_path)
            if violation_reason:
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": violation_reason,
                        },
                        ensure_ascii=False,
                    )
                )
                return

        print(json.dumps({"decision": "allow"}))
    except Exception:
        # Return default allow to prevent agent loop interruption on hook parse error
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
