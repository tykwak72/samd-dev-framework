#!/usr/bin/env python3
"""
pre_tool_guard.py - Antigravity PreToolUse Lifecycle Hook for SaMD DHF Integrity

ISO 13485 (4.1.6 / 4.2.4) & FDA 21 CFR Part 11 / CSA 준수를 위해,
AI 에이전트가 write_file 또는 edit_file 도구로 store/*.json, audit_history.jsonl,
또는 자동 생성되는 docs/*.md 규제 보고서를 직접 수정(CLI 우회)하려는 시도를
기계적으로 가로채어 차단(deny)합니다.
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
    "VT_수동시험체크리스트",
    "99_RTM_",
)


def check_path_violation(target_path_str: str) -> str:
    """
    차단 대상 경로인지 검사하여 차단 사유 반환 (정상일 경우 빈 문자열 반환)
    """
    if not target_path_str:
        return ""

    try:
        norm_path = Path(target_path_str).resolve().as_posix()
    except Exception:
        norm_path = target_path_str.replace("\\", "/")

    # 임시 디렉토리(/tmp/) 내의 단위 테스트 파일 조작은 허용
    if norm_path.startswith("/tmp/") or "/tmp/" in norm_path:
        return ""

    parts = [p for p in norm_path.split("/") if p]
    if not parts:
        return ""

    filename = parts[-1]
    parent_dir = parts[-2] if len(parts) >= 2 else ""

    # 1. store/ 디렉토리 내부의 JSON, JSONL, lock 파일 직접 쓰기/편집 차단
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

    # 2. docs/ 디렉토리 내부의 자동 렌더링 규제 보고서 직접 쓰기/편집 차단
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
        # 훅 파싱 오류 시 에이전트 루프 중단을 막기 위해 기본 allow 반환
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
