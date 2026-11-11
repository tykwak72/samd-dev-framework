#!/usr/bin/env python3
"""
gatekeeper.py - SaMD V-모델 자동 검문소 및 정적 분석 / 테스트 검증 엔진

[주요 기능]
1. V-모델 Stage 0~5 Gate 전수 기계적 검증 (SCHEMA_SPEC.md 4항 및 IEC 62304 / ISO 14971 준수)
2. Python AST 기반 시그니처 계약 검증: 04_sds.json과 src/ 소스코드 간의 100% 일치 검사
3. 부실 구현 차단: 빈 함수, pass 단독 본문, TODO/FIXME 주석, 03_sad_soup.json 미승인 SOUP import 적발
4. V-모델 4계층 독립 블랙박스 테스트 러너 및 last_run_status 집계
"""

import os
import sys
import ast
import json
import re
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

from dhf_cli import DHFManager, DHFLock, BASELINE_LOCKED_FILES

# 파이썬 표준 라이브러리 화이트리스트 (SOUP 등록 불필요)
PYTHON_STDLIB_MODULES: Set[str] = {
    "sys", "os", "math", "json", "re", "typing", "datetime", "pathlib",
    "hashlib", "fcntl", "argparse", "subprocess", "collections", "itertools",
    "functools", "abc", "copy", "time", "random", "logging", "uuid", "io",
    "shutil", "tempfile", "threading", "multiprocessing", "queue", "socket",
    "select", "selectors", "asyncio", "dataclasses", "enum", "warnings",
    "contextlib", "unittest", "inspect", "ast", "tokenize", "traceback",
    "weakref", "gc", "types", "operator", "decimal", "fractions", "numbers",
    "cmath", "bisect", "heapq", "array", "struct", "codecs", "unicodedata"
}


class Gatekeeper:
    """SaMD V-모델 품질 및 안전 검문소 엔진"""

    def __init__(self, workspace_root: Optional[Path] = None):
        if workspace_root is None:
            self.workspace_root = Path.cwd().resolve()
        else:
            self.workspace_root = Path(workspace_root).resolve()

        self.mgr = DHFManager(self.workspace_root)
        self.store_dir = self.mgr.store_dir
        self.src_dir = self.workspace_root / "src"
        self.tests_dir = self.workspace_root / "tests"

    def _load_store(self, filename: str) -> List[Dict[str, Any]]:
        fp = self.store_dir / filename
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    return json.load(f).get("items", [])
            except Exception:
                return []
        return []

    def _load_traceability(self) -> Dict[str, Any]:
        # 항상 실시간으로 store/*.json을 스캔하여 Suspect Link 및 Broken Link를 재계산함 (Stale 캐시 우회 차단)
        return self.mgr.sync_traceability()

    # ==========================================================================
    # 1. AST 기반 소스코드 정적 분석 & 시그니처 계약 검증
    # ==========================================================================

    def check_signatures_and_code_quality(self) -> Tuple[bool, List[str]]:
        """
        04_sds.json의 상세설계(SDS) 계약과 src/ 소스코드를 대조 검증:
        1. target_file_path 존재 여부
        2. @traces: SDS-xxx 주석 존재 여부
        3. AST 파싱 및 함수/클래스/메서드 시그니처(파라미터 목록) 일치 검사
        4. pass 단독, 빈 함수 본문, TODO/FIXME 차단
        5. 03_sad_soup.json에 미등록된 외부 3rd-party 패키지 import 차단
        """
        errors: List[str] = []
        sds_items = self._load_store("04_sds.json")
        soup_items = self._load_store("03_sad_soup.json")

        if not sds_items:
            return False, ["No SDS specifications found in 04_sds.json"]

        # 승인된 SOUP 목록 추출
        approved_soups: Set[str] = set()
        # 배포 패키지명 <-> 파이썬 import 모듈명 매핑 헬퍼
        PKG_TO_IMPORT_ALIAS = {
            "pillow": ["pil"],
            "opencv-python": ["cv2"],
            "scikit-learn": ["sklearn"],
            "pyyaml": ["yaml"]
        }
        for item in soup_items:
            if item.get("type") == "SOUP" and "package_name" in item:
                pkg_name = item["package_name"].lower()
                approved_soups.add(pkg_name)
                for alias in PKG_TO_IMPORT_ALIAS.get(pkg_name, []):
                    approved_soups.add(alias)

        # 캐시: 이미 파싱한 소스 파일의 AST 및 텍스트
        parsed_files: Dict[str, Tuple[ast.AST, str, List[str]]] = {}

        for sds in sds_items:
            sds_id = sds["id"]
            rel_path = sds.get("target_file_path")
            callable_name = sds.get("callable_name")
            unit_type = sds.get("unit_type", "function")
            params_contract = sds.get("parameters_contract", [])

            if not rel_path:
                errors.append(f"[{sds_id}] Missing 'target_file_path' in SDS specification.")
                continue

            file_path = self.workspace_root / rel_path
            if not file_path.exists():
                errors.append(f"[{sds_id}] Target file not found on disk: '{rel_path}'")
                continue

            # 파일 로드 및 AST 파싱
            if rel_path not in parsed_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        source_text = f.read()
                    tree = ast.parse(source_text, filename=str(file_path))
                    lines = source_text.splitlines()
                    parsed_files[rel_path] = (tree, source_text, lines)
                except SyntaxError as se:
                    errors.append(f"[{rel_path}] Python syntax error: {se}")
                    continue
                except Exception as e:
                    errors.append(f"[{rel_path}] Failed to read or parse file: {e}")
                    continue

                # 1) TODO / FIXME 검사
                for lno, line in enumerate(lines, start=1):
                    if re.search(r"#.*(TODO|FIXME|TBD|XXX)", line, re.IGNORECASE):
                        errors.append(f"[{rel_path}:{lno}] Unfinished code marker detected: '{line.strip()}'")

                # 2) SOUP import 검사
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            root_pkg = alias.name.split(".")[0]
                            if root_pkg not in PYTHON_STDLIB_MODULES and root_pkg.lower() not in approved_soups:
                                # 로컬 모듈 체크 (src 디렉터리 내 파이썬 파일)
                                if not (self.src_dir / f"{root_pkg}.py").exists() and not (self.src_dir / root_pkg).is_dir():
                                    errors.append(f"[{rel_path}:{node.lineno}] Unapproved SOUP import '{root_pkg}' not found in 03_sad_soup.json")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            root_pkg = node.module.split(".")[0]
                            if root_pkg not in PYTHON_STDLIB_MODULES and root_pkg.lower() not in approved_soups:
                                if not (self.src_dir / f"{root_pkg}.py").exists() and not (self.src_dir / root_pkg).is_dir():
                                    errors.append(f"[{rel_path}:{node.lineno}] Unapproved SOUP import '{root_pkg}' not found in 03_sad_soup.json")

            tree, source_text, lines = parsed_files[rel_path]

            # 3) @traces: SDS-xxx 추적성 주석 및 버전 일치 검사
            trace_pattern = re.compile(rf"#\s*@traces:\s*{re.escape(sds_id)}(?:@v?(\d+))?\b")
            trace_match = trace_pattern.search(source_text)
            if not trace_match:
                errors.append(f"[{sds_id}] Missing '# @traces: {sds_id}' comment in '{rel_path}'")
            elif trace_match.group(1) is not None:
                code_trace_ver = int(trace_match.group(1))
                sds_ver = sds.get("version", 1)
                if code_trace_ver != sds_ver:
                    errors.append(
                        f"[{sds_id}] Code trace version mismatch in '{rel_path}': "
                        f"found '@traces: {sds_id}@{code_trace_ver}', expected current SDS version {sds_ver}"
                    )

            # 4) AST 함수 / 클래스 탐색 및 시그니처 일치 검증
            target_node = None
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == callable_name:
                        target_node = node
                        break
                elif isinstance(node, ast.ClassDef):
                    if unit_type == "class" and node.name == callable_name:
                        target_node = node
                        break

            if not target_node:
                errors.append(f"[{sds_id}] Callable '{callable_name}' not found in AST of '{rel_path}'")
                continue

            # 함수 / 메서드인 경우 파라미터 및 본문 검증
            if isinstance(target_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 파라미터 이름 비교 (self, cls 제외)
                actual_args = [a.arg for a in target_node.args.args if a.arg not in ("self", "cls")]
                expected_args = [p["name"] for p in params_contract if "name" in p]

                if actual_args != expected_args:
                    errors.append(
                        f"[{sds_id}] Parameter mismatch in '{callable_name}': "
                        f"Expected {expected_args}, but found {actual_args} in AST"
                    )

                # 빈 함수 / pass 단독 검사
                body = target_node.body
                # 만약 docstring이 있다면 첫 번째 문장은 Expr(Constant(str))임
                effective_body = []
                for stmt in body:
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                        continue
                    effective_body.append(stmt)

                if not effective_body:
                    errors.append(f"[{sds_id}:{target_node.lineno}] Function '{callable_name}' has empty implementation (docstring only).")
                elif len(effective_body) == 1 and isinstance(effective_body[0], ast.Pass):
                    errors.append(f"[{sds_id}:{target_node.lineno}] Function '{callable_name}' contains only 'pass' statement.")
                elif len(effective_body) == 1 and isinstance(effective_body[0], ast.Raise):
                    # NotImplementedError 단독 차단
                    exc = effective_body[0].exc
                    if isinstance(exc, ast.Call) and getattr(exc.func, "id", None) == "NotImplementedError":
                        errors.append(f"[{sds_id}:{target_node.lineno}] Function '{callable_name}' raises NotImplementedError without real implementation.")

        return len(errors) == 0, errors

    def _has_test_callable_in_ast(self, rel_path: str, callable_name: str) -> bool:
        """지정된 테스트 파일 내에 실제 test_callable_name 함수/메서드가 정의되어 있는지 AST로 검증"""
        fp = self.workspace_root / rel_path
        if not fp.exists():
            return False
        try:
            with open(fp, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(fp))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name:
                    return True
        except Exception:
            return False
        return False

    def _check_maintenance_and_baselines(
        self,
        stage: int,
        links: Dict[str, Any],
        cov: Dict[str, Any]
    ) -> List[str]:
        """
        IEC 62304 Clause 6(유지보수), Clause 8(형상관리/베이스라인), Clause 9(문제해결 PR/CR) 기계적 검증:
        1. 최초 베이스라인(BL-001) 이후 잠긴 항목의 버전이 증가했거나 project_mode=='maintenance'인 경우
           반드시 pr_cr_log.json에 PR-xxx 및 APPROVED 상태의 CR-xxx가 존재해야 함.
        2. 모든 CR-xxx는 유효한 PR-xxx를 추적(traces_to)해야 하며, impacted_item_ids 및 regression_test_ids가
           유효해야 하고, Stage 4/5에서는 지정된 모든 회귀시험(regression_test_ids)이 PASS여야 함.
        3. Stage 5에서는 REL-xxx가 참조하는 BL-xxx가 cm_baselines.json에 실제 존재해야 하며,
           최신 REL의 BL-xxx에 기록된 locked_item_versions가 현재 모든 V-모델 산출물 버전과 100% 일치해야 함.
           또한 모든 PR-xxx는 CLOSED이거나 DEFERRED(릴리즈 문서의 known_remaining_anomalies에 등재 필수)여야 함.
        """
        errors: List[str] = []
        baselines = self._load_store("cm_baselines.json")
        pr_cr_items = self._load_store("pr_cr_log.json")
        intake_items = self._load_store("00_intake.json")
        tc_items = self._load_store("05_tc.json")
        tc_map = {it["id"]: it for it in tc_items}

        pr_items = [it for it in pr_cr_items if it.get("type") == "PR"]
        cr_items = [it for it in pr_cr_items if it.get("type") == "CR"]
        pr_map = {it["id"]: it for it in pr_items}

        # 베이스라인 이후 변경 발생 여부 감지
        has_post_baseline_changes = False
        if baselines:
            first_locked = baselines[0].get("locked_item_versions", {})
            for iid, node in links.items():
                if node.get("store_file") in BASELINE_LOCKED_FILES:
                    if node.get("current_version", 1) > first_locked.get(iid, node.get("current_version", 1)):
                        has_post_baseline_changes = True
                        break

        is_maintenance_mode = (
            any(it.get("project_mode") == "maintenance" for it in intake_items)
            or has_post_baseline_changes
            or len(pr_cr_items) > 0
            or len(baselines) > 1
        )

        if is_maintenance_mode:
            if not pr_items:
                errors.append(
                    "Maintenance Control Failure (IEC 62304 Clause 6/9): Post-baseline change or maintenance mode "
                    "detected, but no Problem Report (PR-xxx) found in pr_cr_log.json"
                )
            if not cr_items:
                errors.append(
                    "Maintenance Control Failure (IEC 62304 Clause 6/8.2): Post-baseline change or maintenance mode "
                    "detected, but no Change Request (CR-xxx) found in pr_cr_log.json"
                )

            for cr in cr_items:
                cr_id = cr["id"]
                traces = cr.get("traces_to", {})
                if not any(up_id in pr_map for up_id in traces.keys()):
                    errors.append(
                        f"Maintenance Control Failure: Change Request '{cr_id}' does not trace to any valid "
                        f"Problem Report (PR-xxx) in pr_cr_log.json"
                    )

                if cr.get("approval_status") != "APPROVED":
                    errors.append(
                        f"Maintenance Control Failure: Change Request '{cr_id}' approval_status is "
                        f"'{cr.get('approval_status')}' (must be 'APPROVED')"
                    )

                impacted = cr.get("impacted_item_ids", [])
                if not impacted or not isinstance(impacted, list):
                    errors.append(f"Maintenance Control Failure: CR '{cr_id}' must specify non-empty 'impacted_item_ids'")
                else:
                    for imp_id in impacted:
                        if imp_id not in links:
                            errors.append(
                                f"Maintenance Control Failure: CR '{cr_id}' references non-existent impacted item '{imp_id}'"
                            )

                reg_tests = cr.get("regression_test_ids", [])
                if not reg_tests or not isinstance(reg_tests, list):
                    errors.append(f"Maintenance Control Failure: CR '{cr_id}' must specify non-empty 'regression_test_ids'")
                elif stage in (4, 5):
                    for rtid in reg_tests:
                        rtc = tc_map.get(rtid)
                        if not rtc:
                            errors.append(
                                f"Maintenance Regression Failure: Regression test '{rtid}' in '{cr_id}' not found in 05_tc.json"
                            )
                        elif rtc.get("last_run_status") != "PASS":
                            errors.append(
                                f"Maintenance Regression Failure: Regression test '{rtid}' in '{cr_id}' "
                                f"status is '{rtc.get('last_run_status')}' (must be PASS)"
                            )

        # Stage 5 릴리즈 시점의 베이스라인 무결성 및 PR 종결 검증
        if stage == 5:
            uncovered = cov.get("uncovered_items", [])
            for unc in uncovered:
                errors.append(f"Stage 5 Traceability: Uncovered/Orphan item detected: {unc}")

            bl_map = {b["id"]: b for b in baselines}
            if not baselines:
                errors.append("Stage 5 Baseline Failure (IEC 62304 Clause 8.1): No baselines (BL-xxx) found in cm_baselines.json")

            rel_items = self._load_store("06_release.json")
            for rel in rel_items:
                ref_bl_id = rel.get("baseline_id")
                if not ref_bl_id or ref_bl_id not in bl_map:
                    errors.append(
                        f"Stage 5 Baseline Failure: Release '{rel['id']}' references baseline_id '{ref_bl_id}' "
                        f"which does not exist in cm_baselines.json"
                    )

            if rel_items:
                latest_rel = rel_items[-1]
                latest_bl_id = latest_rel.get("baseline_id")
                if latest_bl_id in bl_map:
                    latest_bl = bl_map[latest_bl_id]
                    locked_vers = latest_bl.get("locked_item_versions", {})
                    for iid, node in links.items():
                        if node.get("store_file") in BASELINE_LOCKED_FILES:
                            cur_ver = node.get("current_version", 1)
                            if iid not in locked_vers:
                                errors.append(
                                    f"Stage 5 Baseline Failure: Active item '{iid}' (v{cur_ver}) is missing from "
                                    f"baseline '{latest_bl_id}' locked_item_versions"
                                )
                            elif locked_vers[iid] != cur_ver:
                                errors.append(
                                    f"Stage 5 Baseline Failure: Item '{iid}' current version (v{cur_ver}) diverges "
                                    f"from baseline '{latest_bl_id}' locked version (v{locked_vers[iid]})"
                                )

                # PR 종결 상태 및 보류(DEFERRED) 결함의 06_release.json 등재 여부 검증
                anomalies = latest_rel.get("known_remaining_anomalies", [])
                documented_pr_ids = {
                    (a.get("id") or a.get("pr_id"))
                    for a in anomalies if isinstance(a, dict)
                }
                for pr in pr_items:
                    pr_id = pr["id"]
                    res_status = pr.get("resolution_status", "OPEN")
                    if res_status not in ("CLOSED", "DEFERRED"):
                        errors.append(
                            f"Stage 5 Maintenance Failure (IEC 62304 Clause 9.8): Problem Report '{pr_id}' "
                            f"has unresolved status '{res_status}' (must be CLOSED or DEFERRED)"
                        )
                    elif res_status == "DEFERRED" and pr_id not in documented_pr_ids:
                        errors.append(
                            f"Stage 5 Maintenance Failure (IEC 62304 Clause 5.8): Deferred Problem Report '{pr_id}' "
                            f"is not documented in '{latest_rel['id']}' known_remaining_anomalies"
                        )

        return errors

    # ==========================================================================
    # 2. V-모델 Stage Gate 검증기
    # ==========================================================================

    def check_stage_gate(self, stage: int) -> Tuple[bool, List[str]]:
        """
        Stage 번호(0~5)에 따른 V-모델 Gate 규칙 전수 검사
        """
        errors: List[str] = []

        # 0. 공통 필수 무결성 검문: 해시 체인 및 store/*.json 직접 변조 교차 검증 (21 CFR Part 11 / FDA CSA)
        audit_ok, audit_errors = self.mgr.verify_audit_history()
        if not audit_ok:
            for ae in audit_errors:
                errors.append(f"Audit & Store Integrity Violation: {ae}")

        trace_data = self._load_traceability()
        links = trace_data.get("links", {})
        cov = trace_data.get("coverage_summary", {})

        # 공통 전제조건: 깨진 링크(broken_links) 및 Suspect Link 존재 시 탈락
        broken_links = cov.get("broken_links", [])
        if broken_links:
            for bl in broken_links:
                errors.append(f"Broken Link: Item '{bl.get('item_id')}' points to non-existent upstream '{bl.get('broken_upstream_id')}'")

        suspect_links = cov.get("suspect_links", [])
        if suspect_links:
            for sl in suspect_links:
                reasons = links.get(sl, {}).get("suspect_reasons", [])
                errors.append(f"Suspect Link: Item '{sl}' requires review/re-verification. Reasons: {', '.join(reasons)}")

        # 유지보수(PR/CR) 및 베이스라인(BL) 규칙 검증
        maint_errors = self._check_maintenance_and_baselines(stage, links, cov)
        errors.extend(maint_errors)

        # 감사 판정 확인 헬퍼
        audits = self._load_store("audit_findings.json")
        def verify_stage_audit(stage_label: str) -> None:
            stage_audits = [a for a in audits if a.get("stage") == stage_label]
            if not stage_audits:
                errors.append(f"Missing mandatory audit finding for '{stage_label}' in audit_findings.json")
                return
            for a in stage_audits:
                if a.get("verdict") != "PASS":
                    errors.append(f"Audit finding '{a.get('id')}' for '{stage_label}' has verdict '{a.get('verdict')}': {a.get('finding_details')}")

        # ----------------------------------------------------------------------
        # Stage 0 Gate: 기획, 문헌, 규제, 수행계획
        # ----------------------------------------------------------------------
        if stage == 0:
            int_items = self._load_store("00_intake.json")
            lit_items = self._load_store("00_literature.json")
            reg_items = self._load_store("00_regulatory.json")
            sdp_items = self._load_store("00_sdp_plan.json")

            if not int_items:
                errors.append("Stage 0 Failure: No INT (Intake) items found in 00_intake.json")
            if not lit_items:
                errors.append("Stage 0 Failure: No LIT (Literature) items found in 00_literature.json")
            if not reg_items:
                errors.append("Stage 0 Failure: No REG (Regulatory) items found in 00_regulatory.json")
            if not sdp_items:
                errors.append("Stage 0 Failure: No SDP (Project Plan) items found in 00_sdp_plan.json")

            # INT -> LIT & REG 연결 확인
            for it in int_items:
                iid = it["id"]
                node = links.get(iid, {})
                down = node.get("downward", {})
                has_lit = any(d.startswith("LIT-") for d in down)
                has_reg = any(d.startswith("REG-") for d in down)
                if not has_lit:
                    errors.append(f"Stage 0 Traceability: INT item '{iid}' has no downward link to LIT")
                if not has_reg:
                    errors.append(f"Stage 0 Traceability: INT item '{iid}' has no downward link to REG")

            # REG -> SDP 연결 확인
            for it in reg_items:
                rid = it["id"]
                node = links.get(rid, {})
                down = node.get("downward", {})
                has_sdp = any(d.startswith("SDP-") for d in down)
                if not has_sdp:
                    errors.append(f"Stage 0 Traceability: REG item '{rid}' is not referenced by any SDP item")

            verify_stage_audit("Stage 0")

        # ----------------------------------------------------------------------
        # Stage 1 Gate: URS, SRS, 위험관리 (PHA/초기보안)
        # ----------------------------------------------------------------------
        elif stage == 1:
            int_items = self._load_store("00_intake.json")
            urs_items = self._load_store("01_urs.json")
            srs_items = self._load_store("02_srs.json")
            haz_saf = [it for it in self._load_store("rmf_safety.json") if it.get("type") == "HAZ-SAF"]
            rc_saf = [it for it in self._load_store("rmf_safety.json") if it.get("type") == "RC-SAF"]
            haz_sec = [it for it in self._load_store("rmf_security.json") if it.get("type") == "HAZ-SEC"]
            rc_sec = [it for it in self._load_store("rmf_security.json") if it.get("type") == "RC-SEC"]

            if not urs_items:
                errors.append("Stage 1 Failure: No URS items found in 01_urs.json")
            if not srs_items:
                errors.append("Stage 1 Failure: No SRS items found in 02_srs.json")

            # INT -> URS
            for it in int_items:
                iid = it["id"]
                down = links.get(iid, {}).get("downward", {})
                if not any(d.startswith("URS-") for d in down):
                    errors.append(f"Stage 1 Traceability: INT '{iid}' has no downward URS requirement")

            # URS -> SRS
            for it in urs_items:
                uid = it["id"]
                down = links.get(uid, {}).get("downward", {})
                if not any(d.startswith("SRS-") for d in down):
                    errors.append(f"Stage 1 Traceability: URS '{uid}' has no downward SRS requirement")

            # HAZ-SAF (control_required=True) -> RC-SAF -> SRS
            for haz in haz_saf:
                hid = haz["id"]
                if haz.get("control_required", True):
                    down = links.get(hid, {}).get("downward", {})
                    rc_links = [d for d in down if d.startswith("RC-SAF-")]
                    if not rc_links:
                        errors.append(f"Stage 1 Safety Risk: HAZ '{hid}' requires control but has no RC-SAF link")
                    else:
                        for rc_id in rc_links:
                            rc_down = links.get(rc_id, {}).get("downward", {})
                            if not any(d.startswith("SRS-") for d in rc_down):
                                errors.append(f"Stage 1 Traceability: Risk Control '{rc_id}' is not implemented in any SRS requirement")

            # HAZ-SEC -> RC-SEC -> SRS
            for haz in haz_sec:
                hid = haz["id"]
                down = links.get(hid, {}).get("downward", {})
                rc_links = [d for d in down if d.startswith("RC-SEC-")]
                if not rc_links:
                    errors.append(f"Stage 1 Security Threat: HAZ '{hid}' has no RC-SEC security control link")
                else:
                    for rc_id in rc_links:
                        rc_down = links.get(rc_id, {}).get("downward", {})
                        if not any(d.startswith("SRS-") for d in rc_down):
                            errors.append(f"Stage 1 Traceability: Security Control '{rc_id}' is not implemented in any SRS requirement")

            verify_stage_audit("Stage 1")

        # ----------------------------------------------------------------------
        # Stage 2 Gate: 아키텍처(SAD/SOUP) 및 상세설계(SDS 시그니처 계약)
        # ----------------------------------------------------------------------
        elif stage == 2:
            srs_items = self._load_store("02_srs.json")
            sad_items = [it for it in self._load_store("03_sad_soup.json") if it.get("type") == "SAD"]
            sds_items = self._load_store("04_sds.json")

            if not sad_items:
                errors.append("Stage 2 Failure: No SAD items found in 03_sad_soup.json")
            if not sds_items:
                errors.append("Stage 2 Failure: No SDS items found in 04_sds.json")

            # SRS -> SAD and SRS -> SDS
            for srs in srs_items:
                sid = srs["id"]
                down = links.get(sid, {}).get("downward", {})
                has_sad = any(d.startswith("SAD-") for d in down)
                has_sds = any(d.startswith("SDS-") for d in down)
                if not has_sad:
                    errors.append(f"Stage 2 Traceability: SRS '{sid}' has no downward SAD module")
                if not has_sds:
                    errors.append(f"Stage 2 Traceability: SRS '{sid}' has no downward SDS detail design")

            # SDS 계약 완결성
            for sds in sds_items:
                sid = sds["id"]
                for req_f in ["target_file_path", "callable_signature", "parameters_contract", "exception_contract"]:
                    if req_f not in sds:
                        errors.append(f"Stage 2 Contract Violation: SDS '{sid}' missing '{req_f}'")

            verify_stage_audit("Stage 2")

        # ----------------------------------------------------------------------
        # Stage 3 Gate: 소스코드 단위 구현 및 AST 계약 검증
        # ----------------------------------------------------------------------
        elif stage == 3:
            sds_items = self._load_store("04_sds.json")
            if not sds_items:
                errors.append("Stage 3 Failure: No SDS items found to verify code against.")

            # AST 시그니처 및 코드 품질 검사
            ast_ok, ast_errors = self.check_signatures_and_code_quality()
            if not ast_ok:
                errors.extend([f"Stage 3 Code Contract: {e}" for e in ast_errors])

            verify_stage_audit("Stage 3")

        # ----------------------------------------------------------------------
        # Stage 4 Gate: V-모델 4계층 독립 검증 및 잔여위험 마감
        # ----------------------------------------------------------------------
        elif stage == 4:
            sds_items = self._load_store("04_sds.json")
            sad_items = [it for it in self._load_store("03_sad_soup.json") if it.get("type") == "SAD"]
            srs_items = self._load_store("02_srs.json")
            urs_items = self._load_store("01_urs.json")
            rc_saf = [it for it in self._load_store("rmf_safety.json") if it.get("type") == "RC-SAF"]
            rc_sec = [it for it in self._load_store("rmf_security.json") if it.get("type") == "RC-SEC"]
            tc_items = self._load_store("05_tc.json")
            tc_map = {it["id"]: it for it in tc_items}

            # 1) 단위 검증 (UT): ∀ SDS => ∃ UT (PASS)
            for sds in sds_items:
                sid = sds["id"]
                down = links.get(sid, {}).get("downward", {})
                ut_ids = [d for d in down if d.startswith("UT-")]
                if not ut_ids:
                    errors.append(f"Stage 4 V&V: SDS '{sid}' has no Unit Test (UT) verification")
                else:
                    for ut_id in ut_ids:
                        tc = tc_map.get(ut_id)
                        if not tc or tc.get("last_run_status") != "PASS":
                            errors.append(f"Stage 4 V&V: Unit Test '{ut_id}' for '{sid}' status is not PASS (status={tc.get('last_run_status') if tc else 'NOT_FOUND'})")

            # 2) 통합 시험 (IT): ∀ SAD => ∃ IT (PASS)
            for sad in sad_items:
                sid = sad["id"]
                down = links.get(sid, {}).get("downward", {})
                it_ids = [d for d in down if d.startswith("IT-")]
                if not it_ids:
                    errors.append(f"Stage 4 V&V: SAD module '{sid}' has no Integration Test (IT)")
                else:
                    for it_id in it_ids:
                        tc = tc_map.get(it_id)
                        if not tc or tc.get("last_run_status") != "PASS":
                            errors.append(f"Stage 4 V&V: Integration Test '{it_id}' for '{sid}' status is not PASS")

            # 3) 시스템 시험 (ST): ∀ SRS => ∃ ST (PASS)
            for srs in srs_items:
                sid = srs["id"]
                down = links.get(sid, {}).get("downward", {})
                st_ids = [d for d in down if d.startswith("ST-")]
                if not st_ids:
                    errors.append(f"Stage 4 V&V: SRS '{sid}' has no System Test (ST)")
                else:
                    for st_id in st_ids:
                        tc = tc_map.get(st_id)
                        if not tc or tc.get("last_run_status") != "PASS":
                            errors.append(f"Stage 4 V&V: System Test '{st_id}' for '{sid}' status is not PASS")

            # 4) 위험통제 고장유도 시험 (Negative Test)
            for rc in (rc_saf + rc_sec):
                rc_id = rc["id"]
                down = links.get(rc_id, {}).get("downward", {})
                test_ids = [d for d in down if d.startswith(("UT-", "IT-", "ST-", "VT-"))]
                has_negative_pass = False
                for tid in test_ids:
                    tc = tc_map.get(tid)
                    if tc and tc.get("is_negative_test") and tc.get("last_run_status") == "PASS":
                        has_negative_pass = True
                        break
                if not has_negative_pass:
                    errors.append(f"Stage 4 V&V: Risk Control '{rc_id}' has no passing negative/fault-injection test")

            # 5) 사용자 밸리데이션 (VT): ∀ URS => ∃ VT (PASS)
            for urs in urs_items:
                uid = urs["id"]
                down = links.get(uid, {}).get("downward", {})
                vt_ids = [d for d in down if d.startswith("VT-")]
                if not vt_ids:
                    errors.append(f"Stage 4 V&V: URS '{uid}' has no Validation Test (VT)")
                else:
                    for vt_id in vt_ids:
                        tc = tc_map.get(vt_id)
                        if not tc or tc.get("last_run_status") != "PASS":
                            errors.append(f"Stage 4 V&V: Validation Test '{vt_id}' for '{uid}' status is not PASS")

            # 6) 자동화 테스트 케이스(automated)의 실제 테스트 파일 및 함수(test_callable_name) AST 존재 검증
            if self.tests_dir.exists():
                for tc in tc_items:
                    if tc.get("execution_mode") == "automated":
                        t_rel = tc.get("test_file_path", "")
                        t_call = tc.get("test_callable_name", "")
                        if not self._has_test_callable_in_ast(t_rel, t_call):
                            errors.append(
                                f"Stage 4 V&V: Automated test '{tc['id']}' callable '{t_call}' "
                                f"not found in AST of '{t_rel}'"
                            )

            # 7) 잔여위험 최종 마감 확인
            haz_saf = [it for it in self._load_store("rmf_safety.json") if it.get("type") == "HAZ-SAF"]
            for haz in haz_saf:
                if not haz.get("residual_acceptable", False):
                    errors.append(f"Stage 4 Residual Risk: HAZ '{haz['id']}' residual risk is NOT marked acceptable")

            haz_sec = [it for it in self._load_store("rmf_security.json") if it.get("type") == "HAZ-SEC"]
            for haz in haz_sec:
                if not haz.get("residual_acceptable", False):
                    errors.append(f"Stage 4 Residual Risk: Security threat '{haz['id']}' residual risk is NOT marked acceptable")

            verify_stage_audit("Stage 4")

        # ----------------------------------------------------------------------
        # Stage 5 Gate: 최종 SW 릴리즈
        # ----------------------------------------------------------------------
        elif stage == 5:
            rel_items = self._load_store("06_release.json")
            if not rel_items:
                errors.append("Stage 5 Failure: No REL items found in 06_release.json")
            else:
                for rel in rel_items:
                    if not rel.get("overall_residual_risk_acceptable", False):
                        errors.append(f"Stage 5 Release: REL '{rel['id']}' overall residual risk is not acceptable")

            # 미해결 감사 결함 검사
            for aud in audits:
                status = aud.get("resolution_status", "OPEN")
                if status not in ("CLOSED", "DEFERRED"):
                    errors.append(f"Stage 5 Release: Audit finding '{aud.get('id')}' is still in status '{status}'")

            verify_stage_audit("Stage 5")

        else:
            errors.append(f"Unknown Stage number: {stage}. Must be between 0 and 5.")

        return len(errors) == 0, errors

    # ==========================================================================
    # 3. 블랙박스 테스트 실행 및 05_tc.json 집계
    # ==========================================================================

    def run_blackbox_tests(self, mask_source: bool = True) -> Dict[str, Any]:
        """
        tests/ 내 테스트를 pytest/unittest로 실행하고,
        05_tc.json에 등록된 항목들의 last_run_status를 기계적으로 업데이트
        """
        tc_items = self._load_store("05_tc.json")
        if not tc_items:
            return {"total": 0, "passed": 0, "failed": 0, "details": "No test cases registered"}

        results = {}
        # tests 디렉터리가 존재하는 경우 pytest 실행
        if self.tests_dir.exists():
            test_files = list(self.tests_dir.glob("test_*.py"))
            if test_files:
                env = os.environ.copy()
                env["PYTHONPATH"] = str(self.workspace_root) + os.pathsep + env.get("PYTHONPATH", "")
                for tf in test_files:
                    cmd = [sys.executable, "-m", "pytest", str(tf), "-q", "--tb=short"]
                    res = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=str(self.workspace_root),
                        env=env
                    )
                    out = res.stdout + res.stderr
                    if mask_source:
                        # 소스코드 경로 및 상세 줄 숨기기
                        out = re.sub(r'File ".*src/.*", line \d+, in .*', '[MASKED_SOURCE_STACKTRACE]', out)

                    # 각 파일별 성공 여부 판단
                    results[tf.name] = {
                        "returncode": res.returncode,
                        "output": out
                    }

        # 05_tc.json의 각 항목 상태 갱신 (실제 AST 함수 존재 여부까지 교차 검증)
        passed_count = 0
        failed_count = 0
        for tc in tc_items:
            rel_path = tc.get("test_file_path", "")
            callable_name = tc.get("test_callable_name", "")
            exec_mode = tc.get("execution_mode", "automated")
            base_fn = Path(rel_path).name
            old_status = tc.get("last_run_status")
            if exec_mode == "automated" and base_fn in results:
                has_callable = self._has_test_callable_in_ast(rel_path, callable_name)
                if results[base_fn]["returncode"] == 0 and has_callable:
                    new_status = "PASS"
                    passed_count += 1
                else:
                    new_status = "FAIL"
                    failed_count += 1
            else:
                # 수동 체크리스트(manual_checklist) 등
                if old_status == "PASS":
                    new_status = "PASS"
                    passed_count += 1
                else:
                    new_status = "PENDING"

            if old_status != new_status:
                tc["last_run_status"] = new_status
                # DHF put_item 호출을 통해 갱신
                self.mgr.put_item(
                    filename="05_tc.json",
                    item=tc,
                    actor="4-A_blackbox_tester",
                    reason=f"Automated test execution result update: {new_status}"
                )

        return {
            "total": len(tc_items),
            "passed": passed_count,
            "failed": failed_count,
            "results": results
        }


# ==============================================================================
# CLI 인터페이스
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="SaMD Gatekeeper & AST Contract Verification Engine")
    parser.add_argument(
        "--project-dir", "-p",
        default=None,
        help="Target project directory (default: current working directory)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check-stage
    p_stage = subparsers.add_parser("check-stage", help="Check V-model Stage Gate compliance")
    p_stage.add_argument("stage", type=int, choices=[0, 1, 2, 3, 4, 5], help="Stage number (0 to 5)")

    # check-signatures
    subparsers.add_parser("check-signatures", help="Perform AST contract and code quality checks on src/")

    # run-tests
    p_test = subparsers.add_parser("run-tests", help="Execute blackbox tests and update 05_tc.json")
    p_test.add_argument("--unmask", action="store_true", help="Do not mask source code traces")

    args = parser.parse_args()
    proj_path = Path(args.project_dir).resolve() if args.project_dir else None
    gk = Gatekeeper(workspace_root=proj_path)

    if args.command == "check-stage":
        passed, errors = gk.check_stage_gate(args.stage)
        if passed:
            print(f"🎉 Stage {args.stage} Gate Check: 100% PASSED!")
        else:
            print(f"❌ Stage {args.stage} Gate Check: FAILED with {len(errors)} violations:")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)

    elif args.command == "check-signatures":
        passed, errors = gk.check_signatures_and_code_quality()
        if passed:
            print("🎉 AST Signature & Code Quality Check: 100% PASSED!")
        else:
            print(f"❌ AST Signature Check: FAILED with {len(errors)} issues:")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)

    elif args.command == "run-tests":
        res = gk.run_blackbox_tests(mask_source=not args.unmask)
        print(f"Blackbox tests executed: Total={res['total']}, Passed={res['passed']}, Failed={res['failed']}")
        if res['failed'] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
