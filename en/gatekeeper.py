#!/usr/bin/env python3
"""
gatekeeper.py - SaMD V-Model Automated Checkpoint and Static Analysis / Test Verification Engine

[Key Capabilities]
1. Comprehensive mechanical verification of V-model Stage 0~5 Gates (SCHEMA_SPEC.md Section 4, IEC 62304 / ISO 14971 compliance)
2. Python AST-based signature contract verification: 100% compliance check between 04_sds.json and src/ source code
3. Defect prevention: Detect empty functions, standalone pass bodies, TODO/FIXME comments, and unapproved SOUP imports not in 03_sad_soup.json
4. V-model 4-tier independent black-box test runner and last_run_status aggregation
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

# Python standard library whitelist (No SOUP registration required)
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
    """SaMD V-Model Quality and Safety Gatekeeper Engine"""

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
        # Always scan store/*.json in real time to recalculate Suspect Links and Broken Links (Prevent stale cache bypass)
        return self.mgr.sync_traceability()

    # ==========================================================================
    # 1. AST-based source code static analysis & signature contract verification
    # ==========================================================================

    def check_signatures_and_code_quality(self) -> Tuple[bool, List[str]]:
        """
        Cross-verify 04_sds.json detailed design (SDS) contracts against src/ source code:
        1. target_file_path existence
        2. @traces: SDS-xxx comment existence
        3. AST parsing and function/class/method signature (parameter list) match check
        4. Block standalone pass, empty function bodies, TODO/FIXME
        5. Block external 3rd-party package imports unregistered in 03_sad_soup.json
        """
        errors: List[str] = []
        sds_items = self._load_store("04_sds.json")
        soup_items = self._load_store("03_sad_soup.json")

        if not sds_items:
            return False, ["No SDS specifications found in 04_sds.json"]

        # Extract approved SOUP list
        approved_soups: Set[str] = set()
        # Helper mapping distribution package names <-> Python import module names
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

        # Cache: AST and text of already parsed source files
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

            # Load file and parse AST
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

                # 1) Inspect TODO / FIXME
                for lno, line in enumerate(lines, start=1):
                    if re.search(r"#.*(TODO|FIXME|TBD|XXX)", line, re.IGNORECASE):
                        errors.append(f"[{rel_path}:{lno}] Unfinished code marker detected: '{line.strip()}'")

                # 2) Inspect SOUP imports
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            root_pkg = alias.name.split(".")[0]
                            if root_pkg not in PYTHON_STDLIB_MODULES and root_pkg.lower() not in approved_soups:
                                # Local module check (Python files within src directory)
                                if not (self.src_dir / f"{root_pkg}.py").exists() and not (self.src_dir / root_pkg).is_dir():
                                    errors.append(f"[{rel_path}:{node.lineno}] Unapproved SOUP import '{root_pkg}' not found in 03_sad_soup.json")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            root_pkg = node.module.split(".")[0]
                            if root_pkg not in PYTHON_STDLIB_MODULES and root_pkg.lower() not in approved_soups:
                                if not (self.src_dir / f"{root_pkg}.py").exists() and not (self.src_dir / root_pkg).is_dir():
                                    errors.append(f"[{rel_path}:{node.lineno}] Unapproved SOUP import '{root_pkg}' not found in 03_sad_soup.json")

            tree, source_text, lines = parsed_files[rel_path]

            # 3) @traces: SDS-xxx traceability comment and version match check
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

            # 4) Search AST function / class and verify signature match
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

            # Validate parameters and body if function / method
            if isinstance(target_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Compare parameter names (excluding self, cls)
                actual_args = [a.arg for a in target_node.args.args if a.arg not in ("self", "cls")]
                expected_args = [p["name"] for p in params_contract if "name" in p]

                if actual_args != expected_args:
                    errors.append(
                        f"[{sds_id}] Parameter mismatch in '{callable_name}': "
                        f"Expected {expected_args}, but found {actual_args} in AST"
                    )

                # Inspect empty function / standalone pass
                body = target_node.body
                # If docstring exists, the first statement is Expr(Constant(str))
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
                    # Block standalone NotImplementedError
                    exc = effective_body[0].exc
                    if isinstance(exc, ast.Call) and getattr(exc.func, "id", None) == "NotImplementedError":
                        errors.append(f"[{sds_id}:{target_node.lineno}] Function '{callable_name}' raises NotImplementedError without real implementation.")

        return len(errors) == 0, errors

    def _has_test_callable_in_ast(self, rel_path: str, callable_name: str) -> bool:
        """Verify via AST whether the actual test_callable_name function/method is defined in the specified test file"""
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
        Mechanical verification of IEC 62304 Clause 6 (Maintenance), Clause 8 (Configuration/Baseline), Clause 9 (Problem Resolution PR/CR):
        1. If locked items version incremented post-initial baseline (BL-001) or project_mode == 'maintenance',
           PR-xxx and APPROVED CR-xxx must exist in pr_cr_log.json.
        2. All CR-xxx must trace (traces_to) a valid PR-xxx, impacted_item_ids and regression_test_ids must be
           valid, and all specified regression tests (regression_test_ids) must PASS in Stage 4/5.
        3. In Stage 5, BL-xxx referenced by REL-xxx must actually exist in cm_baselines.json, and locked_item_versions
           recorded in latest REL's BL-xxx must match 100% of current V-model deliverable versions.
           Additionally, all PR-xxx must be CLOSED or DEFERRED (mandatory inclusion in release doc known_remaining_anomalies).
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

        # Detect if changes occurred post-baseline
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

        # Verify baseline integrity and PR closure at Stage 5 release
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

                # Verify PR resolution status and registration of deferred anomalies in 06_release.json
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
    # 2. V-Model Stage Gate Validator
    # ==========================================================================

    def check_stage_gate(self, stage: int) -> Tuple[bool, List[str]]:
        """
        Comprehensive verification of V-Model Gate rules according to Stage number (0~5)
        """
        errors: List[str] = []

        # 0. Common mandatory integrity checkpoint: Cross-verify hash chain and direct store/*.json tampering (21 CFR Part 11 / FDA CSA)
        audit_ok, audit_errors = self.mgr.verify_audit_history()
        if not audit_ok:
            for ae in audit_errors:
                errors.append(f"Audit & Store Integrity Violation: {ae}")

        trace_data = self._load_traceability()
        links = trace_data.get("links", {})
        cov = trace_data.get("coverage_summary", {})

        # Common prerequisite: Fail if broken_links or Suspect Links exist
        broken_links = cov.get("broken_links", [])
        if broken_links:
            for bl in broken_links:
                errors.append(f"Broken Link: Item '{bl.get('item_id')}' points to non-existent upstream '{bl.get('broken_upstream_id')}'")

        suspect_links = cov.get("suspect_links", [])
        if suspect_links:
            for sl in suspect_links:
                reasons = links.get(sl, {}).get("suspect_reasons", [])
                errors.append(f"Suspect Link: Item '{sl}' requires review/re-verification. Reasons: {', '.join(reasons)}")

        # Verify maintenance (PR/CR) and baseline (BL) rules
        maint_errors = self._check_maintenance_and_baselines(stage, links, cov)
        errors.extend(maint_errors)

        # Helper to verify audit verdicts
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
        # Stage 0 Gate: Planning, Literature, Regulatory, SDP
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

            # Verify INT -> LIT & REG links
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

            # Verify REG -> SDP link
            for it in reg_items:
                rid = it["id"]
                node = links.get(rid, {})
                down = node.get("downward", {})
                has_sdp = any(d.startswith("SDP-") for d in down)
                if not has_sdp:
                    errors.append(f"Stage 0 Traceability: REG item '{rid}' is not referenced by any SDP item")

            verify_stage_audit("Stage 0")

        # ----------------------------------------------------------------------
        # Stage 1 Gate: URS, SRS, Risk Management (PHA/Initial Security)
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
        # Stage 2 Gate: Architecture (SAD/SOUP) and Detailed Design (SDS Signature Contracts)
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

            # SDS Contract Completeness
            for sds in sds_items:
                sid = sds["id"]
                for req_f in ["target_file_path", "callable_signature", "parameters_contract", "exception_contract"]:
                    if req_f not in sds:
                        errors.append(f"Stage 2 Contract Violation: SDS '{sid}' missing '{req_f}'")

            verify_stage_audit("Stage 2")

        # ----------------------------------------------------------------------
        # Stage 3 Gate: Source Code Unit Implementation & AST Contract Verification
        # ----------------------------------------------------------------------
        elif stage == 3:
            sds_items = self._load_store("04_sds.json")
            if not sds_items:
                errors.append("Stage 3 Failure: No SDS items found to verify code against.")

            # AST Signature and Code Quality Check
            ast_ok, ast_errors = self.check_signatures_and_code_quality()
            if not ast_ok:
                errors.extend([f"Stage 3 Code Contract: {e}" for e in ast_errors])

            verify_stage_audit("Stage 3")

        # ----------------------------------------------------------------------
        # Stage 4 Gate: V-Model 4-Tier Independent Verification & Residual Risk Closure
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

            # 1) Unit Verification (UT): ∀ SDS => ∃ UT (PASS)
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

            # 2) Integration Testing (IT): ∀ SAD => ∃ IT (PASS)
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

            # 3) System Testing (ST): ∀ SRS => ∃ ST (PASS)
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

            # 4) Risk Control Fault-Injection Testing (Negative Test)
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

            # 5) User Validation (VT): ∀ URS => ∃ VT (PASS)
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

            # 6) Verify existence of actual test file and function (test_callable_name) in AST for automated test cases
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

            # 7) Confirm final residual risk closure
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
        # Stage 5 Gate: Final SW Release
        # ----------------------------------------------------------------------
        elif stage == 5:
            rel_items = self._load_store("06_release.json")
            if not rel_items:
                errors.append("Stage 5 Failure: No REL items found in 06_release.json")
            else:
                for rel in rel_items:
                    if not rel.get("overall_residual_risk_acceptable", False):
                        errors.append(f"Stage 5 Release: REL '{rel['id']}' overall residual risk is not acceptable")

            # Check unresolved audit findings
            for aud in audits:
                status = aud.get("resolution_status", "OPEN")
                if status not in ("CLOSED", "DEFERRED"):
                    errors.append(f"Stage 5 Release: Audit finding '{aud.get('id')}' is still in status '{status}'")

            verify_stage_audit("Stage 5")

        else:
            errors.append(f"Unknown Stage number: {stage}. Must be between 0 and 5.")

        return len(errors) == 0, errors

    # ==========================================================================
    # 3. Black-Box Test Execution & 05_tc.json Aggregation
    # ==========================================================================

    def run_blackbox_tests(self, mask_source: bool = True) -> Dict[str, Any]:
        """
        Execute tests in tests/ via pytest/unittest, and
        mechanically update last_run_status of items registered in 05_tc.json
        """
        tc_items = self._load_store("05_tc.json")
        if not tc_items:
            return {"total": 0, "passed": 0, "failed": 0, "details": "No test cases registered"}

        results = {}
        # Execute pytest if tests directory exists
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
                        # Mask source code paths and detailed lines
                        out = re.sub(r'File ".*src/.*", line \d+, in .*', '[MASKED_SOURCE_STACKTRACE]', out)

                    # Determine success per file
                    results[tf.name] = {
                        "returncode": res.returncode,
                        "output": out
                    }

        # Update status of each item in 05_tc.json (cross-verifying actual AST function existence)
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
                # Manual checklist (manual_checklist) etc.
                if old_status == "PASS":
                    new_status = "PASS"
                    passed_count += 1
                else:
                    new_status = "PENDING"

            if old_status != new_status:
                tc["last_run_status"] = new_status
                # Update via DHF put_item call
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
# CLI Interface
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
