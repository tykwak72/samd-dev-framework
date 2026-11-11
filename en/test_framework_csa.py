#!/usr/bin/env python3
"""
test_framework_csa.py - SaMD Framework Tool Self-Validation Test Suite
(Demonstrating compliance with ISO 13485 4.1.6, ISO/TR 80002-2 & FDA CSA)

[Target Tools for Verification]
- dhf_cli.py (DHFManager, DHFLock, schema validation, hash chain, bidirectional traceability, markdown renderer)
- gatekeeper.py (Gatekeeper, AST signature contract validation, V-model Stage 0~5 Gates)
"""

import os
import sys
import json
import tempfile
import unittest
import multiprocessing
from pathlib import Path

# Import modules under test
from dhf_cli import DHFManager, DHFLock
from gatekeeper import Gatekeeper


def _mp_concurrent_worker(workspace_str: str, worker_idx: int, ops_per_worker: int) -> None:
    """Worker function for multi-process concurrency stress testing (executed in separate OS processes)"""
    mgr = DHFManager(Path(workspace_str))
    for step in range(ops_per_worker):
        # 1) Generate unique item per worker and iterate version increments
        own_id = f"SRS-W{worker_idx:02d}"
        own_item = {
            "id": own_id,
            "type": "SRS",
            "version": 1,
            "status": "approved",
            "title": f"Worker {worker_idx} Requirement (step {step})",
            "description": f"Concurrent write step {step} by worker {worker_idx}",
            "traces_to": {"URS-001": 1},
            "req_category": "functional",
            "verification_method": "unit_test",
            "measurable_criteria": f"Step {step} criteria"
        }
        mgr.put_item(
            filename="02_srs.json",
            item=own_item,
            actor="1-A_requirements_author",
            reason=f"Worker {worker_idx} step {step} update"
        )


class TestFrameworkCSAValidation(unittest.TestCase):
    """Framework Tool Self-Validation (CSA) Test Suite"""

    def setUp(self):
        # Create fully isolated temporary workspace for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.mgr = DHFManager(self.workspace_root)
        self.mgr.init_store()
        self.gk = Gatekeeper(self.workspace_root)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ==========================================================================
    # TOOL-REQ-01: Concurrency Control and File Locking
    # ==========================================================================
    def test_tool_req_01_flock_concurrency_lock(self):
        """Verify that DHFLock properly acquires and releases atomic exclusive locks"""
        lock_file = self.mgr.lock_file
        with DHFLock(lock_file) as lock:
            self.assertTrue(lock_file.exists())
            self.assertIsNotNone(lock._fd)
        # Verify file is closed after exiting Lock context
        self.assertTrue(lock._fd.closed)

    # ==========================================================================
    # TOOL-REQ-02: Strict Single Ownership Enforcement
    # ==========================================================================
    def test_tool_req_02_strict_single_ownership(self):
        """Verify only authorized owners can write, and unauthorized agent write attempts are blocked"""
        srs_item = {
            "id": "SRS-001",
            "type": "SRS",
            "version": 1,
            "status": "draft",
            "title": "Blood Pressure Anomaly Warning Function",
            "description": "Trigger alert when systolic blood pressure is 180 or higher",
            "traces_to": {"URS-001": 1},
            "req_category": "functional",
            "verification_method": "system_test",
            "measurable_criteria": "Trigger warning alarm within 1 second"
        }

        # 1) Authorized owner: 1-A_requirements_author -> Success
        saved = self.mgr.put_item(
            filename="02_srs.json",
            item=srs_item,
            actor="1-A_requirements_author",
            reason="Initial SRS creation"
        )
        self.assertEqual(saved["id"], "SRS-001")
        self.assertEqual(saved["version"], 1)

        # 2) Unauthorized owner: 2-A_software_architect attempts to edit 02_srs.json -> PermissionError
        srs_item_modified = dict(srs_item)
        srs_item_modified["title"] = "Unauthorizedly modified blood pressure alert"
        with self.assertRaises(PermissionError) as ctx:
            self.mgr.put_item(
                filename="02_srs.json",
                item=srs_item_modified,
                actor="2-A_software_architect",
                reason="Unauthorized modification attempt"
            )
        self.assertIn("Ownership Violation", str(ctx.exception))

    # ==========================================================================
    # TOOL-REQ-03: Base Envelope and Specialized Schema Validation
    # ==========================================================================
    def test_tool_req_03_schema_envelope_validation(self):
        """Verify blocking of missing Envelope common fields, prefix mismatch, and missing specialized fields"""
        # 1) Base Envelope mandatory fields (e.g., missing description)
        bad_item_1 = {
            "id": "URS-001",
            "type": "URS",
            "version": 1,
            "status": "draft",
            "title": "Blood Pressure Monitoring",
            # description missing
            "traces_to": {},
            "stakeholder": "clinician",
            "acceptance_criteria": "Acceptance criteria"
        }
        with self.assertRaises(ValueError) as ctx:
            self.mgr.put_item("01_urs.json", bad_item_1, "1-A_requirements_author", "Test")
        self.assertIn("Missing base envelope field 'description'", str(ctx.exception))

        # 2) Prefix mismatch (Attempting to save SRS-001 into 01_urs.json)
        bad_item_2 = {
            "id": "SRS-001",
            "type": "SRS",
            "version": 1,
            "status": "draft",
            "title": "Type Mismatch",
            "description": "Description",
            "traces_to": {},
            "stakeholder": "clinician",
            "acceptance_criteria": "Acceptance criteria"
        }
        with self.assertRaises(ValueError) as ctx:
            self.mgr.put_item("01_urs.json", bad_item_2, "1-A_requirements_author", "Test")
        self.assertIn("Prefix/Type Mismatch", str(ctx.exception))

        # 3) Missing specialized mandatory field (missing measurable_criteria in 02_srs.json)
        bad_item_3 = {
            "id": "SRS-001",
            "type": "SRS",
            "version": 1,
            "status": "draft",
            "title": "Missing Measurable Criteria",
            "description": "Description",
            "traces_to": {},
            "req_category": "functional",
            "verification_method": "unit_test"
            # measurable_criteria missing
        }
        with self.assertRaises(ValueError) as ctx:
            self.mgr.put_item("02_srs.json", bad_item_3, "1-A_requirements_author", "Test")
        self.assertIn("Missing specific field 'measurable_criteria'", str(ctx.exception))

    # ==========================================================================
    # TOOL-REQ-04: Automatic Version Increment & SHA-256 Hash Chain Tampering Detection
    # ==========================================================================
    def test_tool_req_04_versioning_and_audit_hash_chain(self):
        """Verify automatic version increment and audit_history.jsonl hash chain integrity & tampering detection"""
        urs_item = {
            "id": "URS-001",
            "type": "URS",
            "version": 1,
            "status": "draft",
            "title": "Initial User Requirement",
            "description": "Version 1 description",
            "traces_to": {},
            "stakeholder": "clinician",
            "acceptance_criteria": "Acceptance criteria v1"
        }

        # 1) Register v1
        it1 = self.mgr.put_item("01_urs.json", urs_item, "1-A_requirements_author", "Initial draft")
        self.assertEqual(it1["version"], 1)

        # 2) Automatic v2 increment upon update
        urs_item_v2 = dict(it1)
        urs_item_v2["description"] = "Version 2 refined description"
        it2 = self.mgr.put_item("01_urs.json", urs_item_v2, "1-A_requirements_author", "Update description")
        self.assertEqual(it2["version"], 2)

        # 3) Hash chain integrity verification -> 100% PASS
        valid, errors = self.mgr.verify_audit_history()
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)

        # 4) Inject artificial tampering into hash chain -> Must be detected immediately
        with open(self.mgr.audit_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Secretly modify actor in the first line
        record_tampered = json.loads(lines[0])
        record_tampered["actor"] = "HACKER_ATTACKER"
        lines[0] = json.dumps(record_tampered) + "\n"
        with open(self.mgr.audit_log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Re-verify -> Tampering detected (FAIL)
        valid_after, errors_after = self.mgr.verify_audit_history()
        self.assertFalse(valid_after)
        self.assertTrue(any("Tampering detected" in e for e in errors_after))

    # ==========================================================================
    # TOOL-REQ-05: Central Bidirectional Traceability and Cascading Suspect Link Propagation
    # ==========================================================================
    def test_tool_req_05_traceability_and_suspect_link_propagation(self):
        """Verify cascading Suspect Link propagation upon upstream version update, and clearance upon update"""
        # Register URS-001 (v1)
        urs = {
            "id": "URS-001", "type": "URS", "version": 1, "status": "approved",
            "title": "Clinical Requirement", "description": "Requirement description", "traces_to": {}, 
            "stakeholder": "clinician", "acceptance_criteria": "Criteria"
        }
        self.mgr.put_item("01_urs.json", urs, "1-A_requirements_author", "Create URS")

        # Register SRS-001 (v1, traces_to: URS-001@1)
        srs = {
            "id": "SRS-001", "type": "SRS", "version": 1, "status": "approved",
            "title": "SW Requirement", "description": "SRS description", "traces_to": {"URS-001": 1},
            "req_category": "functional", "verification_method": "unit_test",
            "measurable_criteria": "Threshold"
        }
        self.mgr.put_item("02_srs.json", srs, "1-A_requirements_author", "Create SRS")

        # Register SDS-001 (v1, traces_to: SRS-001@1)
        sds = {
            "id": "SDS-001", "type": "SDS", "version": 1, "status": "approved",
            "title": "Detailed Design", "description": "Function design", "traces_to": {"SRS-001": 1},
            "target_file_path": "src/monitor.py", "unit_type": "function",
            "callable_name": "calc_vital", "callable_signature": "def calc_vital(val: int) -> int",
            "parameters_contract": [{"name": "val", "type": "int"}],
            "return_contract": {"type": "int"}, "exception_contract": [],
            "algorithm_specification": "val * 2"
        }
        self.mgr.put_item("04_sds.json", sds, "2-A_software_architect", "Create SDS")

        # Traceability check: No suspect links because all versions match
        trace = self.mgr.sync_traceability()
        self.assertEqual(len(trace["coverage_summary"]["suspect_links"]), 0)

        # Now update URS-001 to v2!
        urs_v2 = dict(urs)
        urs_v2["description"] = "Modified clinical requirement"
        self.mgr.put_item("01_urs.json", urs_v2, "1-A_requirements_author", "Bump URS to v2")

        # Verify after re-synchronizing traceability:
        # Suspect link must cascade to both direct child (SRS-001) and indirect child (SDS-001)
        trace_after = self.mgr.sync_traceability()
        suspects = trace_after["coverage_summary"]["suspect_links"]
        self.assertIn("SRS-001", suspects)
        self.assertIn("SDS-001", suspects)

        # When SRS-001 is updated reflecting URS-001 v2
        srs_v2 = dict(srs)
        srs_v2["traces_to"] = {"URS-001": 2}
        self.mgr.put_item("02_srs.json", srs_v2, "1-A_requirements_author", "Reflect URS v2 in SRS")

        # Direct suspect on SRS-001 is resolved, but SDS-001 remains suspect as SRS-001 bumped to v2
        trace_mid = self.mgr.sync_traceability()
        self.assertNotIn("SRS-001", trace_mid["coverage_summary"]["suspect_links"])
        self.assertIn("SDS-001", trace_mid["coverage_summary"]["suspect_links"])

        # When SDS-001 also reflects SRS-001@2, all suspects are completely cleared!
        sds_v2 = dict(sds)
        sds_v2["traces_to"] = {"SRS-001": 2}
        self.mgr.put_item("04_sds.json", sds_v2, "2-A_software_architect", "Reflect SRS v2 in SDS")

        trace_final = self.mgr.sync_traceability()
        self.assertEqual(len(trace_final["coverage_summary"]["suspect_links"]), 0)

    # ==========================================================================
    # TOOL-REQ-06: Automatic Rendering of Regulatory Reports (docs/*.md) for Auditors
    # ==========================================================================
    def test_tool_req_06_markdown_reports_rendering(self):
        """Verify docs/*.md 8 reports are generated properly, and VT manual checklist format is correct"""
        # Register VT test item
        vt_item = {
            "id": "VT-001", "type": "VT", "version": 1, "status": "draft",
            "title": "Screen Alert Visual Inspection Test", "description": "Visual check of warning light activation",
            "traces_to": {"URS-001": 1}, "test_level": "VT", "execution_mode": "manual_checklist",
            "is_negative_test": False, "test_file_path": "docs/VT_Manual_Test_Checklist.md",
            "test_callable_name": "manual_visual_check", "expected_outcome": "Verify red flashing",
            "last_run_status": "PENDING", "validation_protocol": "Check warning light after waiting 180 seconds on patient screen",
            "human_verified_by": "Clinical Reviewer", "human_observation_notes": "Awaiting visual inspection"
        }
        self.mgr.put_item("05_tc.json", vt_item, "4-A_blackbox_tester", "Register VT test")

        rendered = self.mgr.render_markdown_docs()
        self.assertEqual(len(rendered), 8)

        # Verify VT checklist content
        vt_doc = self.workspace_root / "docs" / "VT_Manual_Test_Checklist.md"
        self.assertTrue(vt_doc.exists())
        with open(vt_doc, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("VT-001", content)
        self.assertIn("[ ] PENDING", content)
        self.assertIn("Check warning light after waiting 180 seconds", content)

    # ==========================================================================
    # TOOL-REQ-07: AST Signature and Code Quality Checkpoint (Gatekeeper AST)
    # ==========================================================================
    def test_tool_req_07_ast_signature_contract_and_code_quality(self):
        """Verify AST parsing thoroughly blocks signature mismatch, leftover TODOs, empty functions, and unapproved SOUP"""
        src_file = self.workspace_root / "src" / "algorithm.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)

        sds_item = {
            "id": "SDS-001", "type": "SDS", "version": 1, "status": "approved",
            "title": "Systolic Blood Pressure Risk Evaluation Algorithm", "description": "Design contract",
            "traces_to": {"SRS-001": 1},
            "target_file_path": "src/algorithm.py",
            "unit_type": "function",
            "callable_name": "evaluate_systolic",
            "callable_signature": "def evaluate_systolic(pressure: int) -> bool",
            "parameters_contract": [{"name": "pressure", "type": "int"}],
            "return_contract": {"type": "bool"},
            "exception_contract": [],
            "algorithm_specification": "return pressure >= 140"
        }
        self.mgr.put_item("04_sds.json", sds_item, "2-A_software_architect", "Register SDS")

        # Case 1: Signature mismatch (Parameter name is val instead of pressure)
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\ndef evaluate_systolic(val: int) -> bool:\n    return val >= 140\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertFalse(passed)
        self.assertTrue(any("Parameter mismatch" in e for e in errors))

        # Case 2: Leftover TODO comment
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\n# TODO: need review\ndef evaluate_systolic(pressure: int) -> bool:\n    return pressure >= 140\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertFalse(passed)
        self.assertTrue(any("Unfinished code marker" in e for e in errors))

        # Case 3: Empty function with standalone pass
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\ndef evaluate_systolic(pressure: int) -> bool:\n    pass\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertFalse(passed)
        self.assertTrue(any("contains only 'pass'" in e for e in errors))

        # Case 4: Unapproved SOUP import (External package import requests not in 03_sad_soup.json)
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\nimport requests\ndef evaluate_systolic(pressure: int) -> bool:\n    return pressure >= 140\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertFalse(passed)
        self.assertTrue(any("Unapproved SOUP import 'requests'" in e for e in errors))

        # Case 5: Proper complete code -> 100% PASS
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\nimport math\ndef evaluate_systolic(pressure: int) -> bool:\n    return pressure >= 140\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertTrue(passed, msg=f"Expected PASS, but got errors: {errors}")

    # ==========================================================================
    # TOOL-REQ-08: V-Model Stage Gate Mechanical Enforcement
    # ==========================================================================
    def test_tool_req_08_stage_gate_enforcement(self):
        """Verify Stage 0 Gate blocks on missing items and passes 100% when fully equipped"""
        # 1) Stage 0 Gate check on empty repository -> Blocked
        passed, errors = self.gk.check_stage_gate(0)
        self.assertFalse(passed)
        self.assertTrue(any("Stage 0 Failure" in e for e in errors))

        # 2) Fully equip Stage 0 mandatory items: INT, LIT, REG, SDP and audit verdict (PASS)
        int_it = {
            "id": "INT-001", "type": "INT", "version": 1, "status": "approved",
            "title": "Blood Pressure Monitoring Device", "description": "Intended Use",
            "traces_to": {}, "intended_use": "Hypertension patient blood pressure monitoring",
            "indications_for_use": "Adult hypertension", "target_patient_population": "Adults",
            "intended_users": "Clinical staff", "use_environment": "Hospital",
            "clinical_benefit": "Early blood pressure alert", "device_category": "SaMD",
            "has_ai_ml": False, "has_network": True, "has_gui": True,
            "has_alarm": True, "project_mode": "new"
        }
        self.mgr.put_item("00_intake.json", int_it, "0-0_intake_agent", "INT creation")

        lit_it = {
            "id": "LIT-001", "type": "LIT", "version": 1, "status": "approved",
            "title": "AHA Blood Pressure Guidelines", "description": "Literature search",
            "traces_to": {"INT-001": 1}, "category": "clinical_guideline",
            "source_citation": "AHA 2024", "key_findings": "Systolic 140 threshold",
            "benchmark_criteria": "Accuracy 95%", "known_hazards_identified": ["False alarm"]
        }
        self.mgr.put_item("00_literature.json", lit_it, "0-A_literature_researcher", "LIT creation")

        reg_it = {
            "id": "REG-001", "type": "REG", "version": 1, "status": "approved",
            "title": "Regulatory Strategy and Classification", "description": "Class B Classification",
            "traces_to": {"INT-001": 1}, "safety_class": "Class B",
            "fda_doc_level": "Basic", "target_regions": ["MFDS", "FDA"],
            "active_profiles": ["alarm_system"], "applicable_standards": ["IEC 62304", "ISO 14971"],
            "regulatory_mandate": "Compliance with Class II regulatory requirements"
        }
        self.mgr.put_item("00_regulatory.json", reg_it, "0-B_regulatory_strategist", "REG creation")

        sdp_it = {
            "id": "SDP-001", "type": "SDP", "version": 1, "status": "approved",
            "title": "SW Development Plan", "description": "V-Model process",
            "traces_to": {"REG-001": 1}, "project_profile": {"safety_class": "Class B"},
            "plan_category": "lifecycle", "language_and_runtime": "Python 3.13",
            "coding_standards": ["PEP8", "IEC 62304"], "risk_acceptability_rule": "ALARP",
            "min_test_coverage_pct": 80, "workflow_steps": [{"step": 1}]
        }
        self.mgr.put_item("00_sdp_plan.json", sdp_it, "0-C_sdp_planner", "SDP creation")

        aud_it = {
            "id": "AUD-001", "type": "AUD", "version": 1, "status": "approved",
            "title": "Stage 0 Audit Completed", "description": "Planning and regulatory strategy conformity verdict",
            "traces_to": {"SDP-001": 1}, "stage": "Stage 0",
            "auditor_role": "0-D_stage0_auditor", "verdict": "PASS",
            "target_agent": "0-C_sdp_planner", "target_item_ids": ["SDP-001"],
            "finding_details": "All regulatory and planning requirements compliant",
            "remediation_required": "None", "resolution_status": "CLOSED"
        }
        self.mgr.put_item("audit_findings.json", aud_it, "0-D_stage0_auditor", "Stage 0 Audit PASS")

        # Re-run Stage 0 Gate check -> Verify 100% pass!
        passed_final, errors_final = self.gk.check_stage_gate(0)
        self.assertTrue(passed_final, msg=f"Stage 0 should PASS, but failed with: {errors_final}")

    # ==========================================================================
    # TOOL-REQ-09: Detection and Prevention of OS-Level Direct File Tampering (CLI Bypass)
    # ==========================================================================
    def test_tool_req_09_direct_os_file_tampering_blocked(self):
        """
        Verify verify_audit_history and gatekeeper.check_stage_gate detect and block 100%
        when store/*.json values/statuses are modified directly or items are inserted/deleted
        unauthorizedly at OS level bypassing dhf_cli.py (21 CFR Part 11 / FDA CSA Integrity)
        """
        # First establish Stage 0 normal setup and register SRS-001, UT-001
        self.test_tool_req_08_stage_gate_enforcement()

        srs_item = {
            "id": "SRS-001", "type": "SRS", "version": 1, "status": "approved",
            "title": "Blood Pressure Alarm Threshold", "description": "Alarm when systolic > 180mmHg",
            "traces_to": {"URS-001": 1}, "req_category": "safety",
            "verification_method": "system_test",
            "measurable_criteria": "Alarm within 1 second when systolic > 180"
        }
        self.mgr.put_item("02_srs.json", srs_item, "1-A_requirements_author", "Create SRS-001")

        ut_item = {
            "id": "UT-001", "type": "UT", "version": 1, "status": "approved",
            "title": "Unit Verification Test", "description": "Initial failure state",
            "traces_to": {"SDS-001": 1}, "test_level": "UT",
            "execution_mode": "automated", "is_negative_test": False,
            "test_file_path": "tests/test_ut.py", "test_callable_name": "test_bp",
            "expected_outcome": "PASS", "last_run_status": "FAIL"
        }
        self.mgr.put_item("05_tc.json", ut_item, "4-A_blackbox_tester", "Create UT-001 with FAIL")

        valid_init, errs_init = self.mgr.verify_audit_history()
        self.assertTrue(valid_init, msg=f"Initial state should be valid: {errs_init}")

        # [Attack 1-A] Secretly tamper last_run_status from FAIL to PASS directly in 05_tc.json at OS level
        tc_path = self.workspace_root / "store" / "05_tc.json"
        with open(tc_path, "r", encoding="utf-8") as f:
            tc_raw = f.read()
        with open(tc_path, "w", encoding="utf-8") as f:
            f.write(tc_raw.replace('"last_run_status": "FAIL"', '"last_run_status": "PASS"'))

        valid_tamper1, errs_tamper1 = self.mgr.verify_audit_history()
        self.assertFalse(valid_tamper1)
        self.assertTrue(any("Direct Tampering Detected in '05_tc.json'" in e for e in errs_tamper1))

        # Gatekeeper check_stage_gate must also immediately block with audit/store integrity violation
        gk_pass1, gk_errs1 = self.gk.check_stage_gate(0)
        self.assertFalse(gk_pass1)
        self.assertTrue(any("Audit & Store Integrity Violation" in e for e in gk_errs1))

        # Verify normal state after restoring 05_tc.json
        with open(tc_path, "w", encoding="utf-8") as f:
            f.write(tc_raw)
        valid_restored, _ = self.mgr.verify_audit_history()
        self.assertTrue(valid_restored)

        # [Attack 1-B] Directly tamper measurable threshold in 02_srs.json and inject ghost item (SRS-999) at OS level
        srs_path = self.workspace_root / "store" / "02_srs.json"
        with open(srs_path, "r", encoding="utf-8") as f:
            srs_data = json.load(f)
        srs_backup = json.dumps(srs_data, indent=2, ensure_ascii=False)

        srs_data["items"][0]["measurable_criteria"] = "systolic > 999 (tampered value)"
        rogue_item = dict(srs_data["items"][0])
        rogue_item["id"] = "SRS-999"
        srs_data["items"].append(rogue_item)
        with open(srs_path, "w", encoding="utf-8") as f:
            json.dump(srs_data, f, indent=2, ensure_ascii=False)

        valid_tamper2, errs_tamper2 = self.mgr.verify_audit_history()
        self.assertFalse(valid_tamper2)
        self.assertTrue(any("Item 'SRS-001' current state in store diverges" in e for e in errs_tamper2))
        self.assertTrue(any("Item 'SRS-999' exists in store but has no audit trail record" in e for e in errs_tamper2))

        # [Attack 1-C] Unauthorized deletion of items from 02_srs.json at OS level (overwrite with empty array)
        with open(srs_path, "w", encoding="utf-8") as f:
            json.dump({"items": []}, f)
        valid_tamper3, errs_tamper3 = self.mgr.verify_audit_history()
        self.assertFalse(valid_tamper3)
        self.assertTrue(any("Item 'SRS-001'" in e and "was unauthorizedly deleted from store" in e for e in errs_tamper3))

        # Restore original state
        with open(srs_path, "w", encoding="utf-8") as f:
            f.write(srs_backup)
        self.assertTrue(self.mgr.verify_audit_history()[0])

    # ==========================================================================
    # TOOL-REQ-10: Multi-process (10 parallel processes) Concurrent Write Race Condition Stress Verification
    # ==========================================================================
    def test_tool_req_10_multiprocess_concurrency_stress(self):
        """
        Verify fcntl.flock (DHFLock) serializes 100% without JSON corruption, Lost Updates, or hash chain breaks
        when 10 independent OS processes call put_item concurrently and competitively (50 transactions total)
        """
        urs_item = {
            "id": "URS-001", "type": "URS", "version": 1, "status": "approved",
            "title": "Concurrency Test Upstream Requirement", "description": "Baseline item",
            "traces_to": {}, "stakeholder": "clinician", "acceptance_criteria": "Criteria"
        }
        self.mgr.put_item("01_urs.json", urs_item, "1-A_requirements_author", "Init URS-001")

        num_workers = 10
        ops_per_worker = 5
        processes = []

        for w_idx in range(num_workers):
            p = multiprocessing.Process(
                target=_mp_concurrent_worker,
                args=(str(self.workspace_root), w_idx, ops_per_worker)
            )
            processes.append(p)

        for p in processes:
            p.start()

        for p in processes:
            p.join(timeout=30)
            self.assertEqual(p.exitcode, 0, msg=f"Worker process exited with non-zero code: {p.exitcode}")

        # 1) Verify audit history hash chain and store cross-check integrity 100%
        valid, errors = self.mgr.verify_audit_history()
        self.assertTrue(valid, msg=f"Audit history or store corrupted under concurrency: {errors}")

        # 2) Confirm total transactions: Initial URS-001 (1) + 10 processes * 5 runs (50) = exactly 51 (0 Lost Updates)
        last_seq, _ = self.mgr.get_last_audit_record()
        self.assertEqual(last_seq, 1 + (num_workers * ops_per_worker))

        # 3) Confirm all worker items (SRS-W00 ~ SRS-W09) in 02_srs.json reached exactly version == 5
        with open(self.workspace_root / "store" / "02_srs.json", "r", encoding="utf-8") as f:
            srs_items = json.load(f).get("items", [])
        self.assertEqual(len(srs_items), num_workers)
        for it in srs_items:
            self.assertEqual(it["version"], ops_per_worker)

    # ==========================================================================
    # TOOL-REQ-11: Release Baseline (BL-xxx) Lock and Post-Release Maintenance (PR/CR) Mechanical Control Verification
    # ==========================================================================
    def test_tool_req_11_baseline_and_pr_cr_maintenance_control(self):
        """
        Verify compliance with IEC 62304 Clauses 6, 8, 9:
        1) Attempt modification of locked items post-BL-001 without PR/CR -> PermissionError immediately blocked
        2) Attempt modification with PENDING CR -> Blocked by PermissionError
        3) When APPROVED CR issued, modification of unlisted items is blocked while impacted items and Suspect Links are allowed
        4) Stage 5 Gate blocked if regression tests (regression_test_ids) fail or PR unresolved (OPEN)
        5) Verify Stage 5 Gate pass and re-locking upon PR closure (CLOSED) and registration of new baseline (BL-002) and release (REL-002)
        """
        # Stage 0 base setup
        self.test_tool_req_08_stage_gate_enforcement()

        # V-model core deliverables setup (URS-001, SRS-001, SRS-002, SAD-001, SDS-001, UT-001, ST-001, VT-001)
        urs = {
            "id": "URS-001", "type": "URS", "version": 1, "status": "approved",
            "title": "Clinical Requirement", "description": "Description", "traces_to": {"INT-001": 1},
            "stakeholder": "clinician", "acceptance_criteria": "Criteria"
        }
        self.mgr.put_item("01_urs.json", urs, "1-A_requirements_author", "Create URS-001")

        srs1 = {
            "id": "SRS-001", "type": "SRS", "version": 1, "status": "approved",
            "title": "Functional Requirement 1", "description": "Description 1", "traces_to": {"URS-001": 1},
            "req_category": "functional", "verification_method": "system_test",
            "measurable_criteria": "Criteria 1"
        }
        self.mgr.put_item("02_srs.json", srs1, "1-A_requirements_author", "Create SRS-001")

        srs2 = {
            "id": "SRS-002", "type": "SRS", "version": 1, "status": "approved",
            "title": "Security Requirement 2", "description": "Description 2", "traces_to": {"URS-001": 1},
            "req_category": "security", "verification_method": "system_test",
            "measurable_criteria": "Criteria 2"
        }
        self.mgr.put_item("02_srs.json", srs2, "1-A_requirements_author", "Create SRS-002")

        sad1 = {
            "id": "SAD-001", "type": "SAD", "version": 1, "status": "approved",
            "title": "Module 1", "description": "Architecture", "traces_to": {"SRS-001": 1, "SRS-002": 1},
            "module_name": "CoreMod", "safety_class": "Class B",
            "module_responsibility": "Core processing", "public_interfaces": ["run()"],
            "segregation_strategy": "Process isolation"
        }
        self.mgr.put_item("03_sad_soup.json", sad1, "2-A_software_architect", "Create SAD-001")

        sds1 = {
            "id": "SDS-001", "type": "SDS", "version": 1, "status": "approved",
            "title": "Detailed Design 1", "description": "Design", "traces_to": {"SRS-001": 1, "SRS-002": 1},
            "target_file_path": "src/core.py", "unit_type": "function",
            "callable_name": "run", "callable_signature": "def run(x: int) -> int",
            "parameters_contract": [{"name": "x", "type": "int"}],
            "return_contract": {"type": "int"}, "exception_contract": [],
            "algorithm_specification": "return x"
        }
        self.mgr.put_item("04_sds.json", sds1, "2-A_software_architect", "Create SDS-001")

        ut1 = {
            "id": "UT-001", "type": "UT", "version": 1, "status": "approved",
            "title": "Unit Test 1", "description": "UT", "traces_to": {"SDS-001": 1},
            "test_level": "UT", "execution_mode": "automated", "is_negative_test": False,
            "test_file_path": "tests/test_ut.py", "test_callable_name": "test_ut",
            "expected_outcome": "PASS", "last_run_status": "PASS"
        }
        self.mgr.put_item("05_tc.json", ut1, "4-A_blackbox_tester", "Create UT-001")

        it1 = {
            "id": "IT-001", "type": "IT", "version": 1, "status": "approved",
            "title": "Integration Test 1", "description": "IT", "traces_to": {"SAD-001": 1},
            "test_level": "IT", "execution_mode": "automated", "is_negative_test": False,
            "test_file_path": "tests/test_it.py", "test_callable_name": "test_it",
            "expected_outcome": "PASS", "last_run_status": "PASS"
        }
        self.mgr.put_item("05_tc.json", it1, "4-A_blackbox_tester", "Create IT-001")

        st1 = {
            "id": "ST-001", "type": "ST", "version": 1, "status": "approved",
            "title": "System Test 1", "description": "ST", "traces_to": {"SRS-001": 1, "SRS-002": 1},
            "test_level": "ST", "execution_mode": "automated", "is_negative_test": False,
            "test_file_path": "tests/test_st.py", "test_callable_name": "test_st",
            "expected_outcome": "PASS", "last_run_status": "PASS"
        }
        self.mgr.put_item("05_tc.json", st1, "4-A_blackbox_tester", "Create ST-001")

        vt1 = {
            "id": "VT-001", "type": "VT", "version": 1, "status": "approved",
            "title": "Validation 1", "description": "VT", "traces_to": {"URS-001": 1},
            "test_level": "VT", "execution_mode": "manual_checklist", "is_negative_test": False,
            "test_file_path": "docs/VT_Manual_Test_Checklist.md", "test_callable_name": "manual_vt",
            "expected_outcome": "PASS", "last_run_status": "PASS"
        }
        self.mgr.put_item("05_tc.json", vt1, "4-A_blackbox_tester", "Create VT-001")

        # Create Release 1.0.0 and BL-001
        rel1 = {
            "id": "REL-001", "type": "REL", "version": 1, "status": "approved",
            "title": "Release 1.0.0", "description": "Initial Release",
            "traces_to": {"VT-001": 1}, "release_version": "1.0.0",
            "baseline_id": "BL-001", "known_remaining_anomalies": [],
            "overall_residual_risk_acceptable": True, "release_environment_spec": {"os": "Linux"}
        }
        self.mgr.put_item("06_release.json", rel1, "5-A_release_author", "Create REL-001")

        aud5 = {
            "id": "AUD-005", "type": "AUD", "version": 1, "status": "approved",
            "title": "Stage 5 Audit PASS", "description": "Release 1.0.0 approved",
            "traces_to": {"REL-001": 1}, "stage": "Stage 5",
            "auditor_role": "5-B_final_release_auditor", "verdict": "PASS",
            "target_agent": "5-A_release_author", "target_item_ids": ["REL-001"],
            "finding_details": "All passed", "remediation_required": "None",
            "resolution_status": "CLOSED"
        }
        self.mgr.put_item("audit_findings.json", aud5, "5-B_final_release_auditor", "Create AUD-005")

        # Run Stage 5 Gate prior to BL-001 finalization -> Must be blocked due to missing BL-001!
        s5_before_bl, s5_errs_before = self.gk.check_stage_gate(5)
        self.assertFalse(s5_before_bl)
        self.assertTrue(any("Stage 5 Baseline Failure" in e for e in s5_errs_before))

        # Create BL-001 snapshot -> Stage 5 Gate 100% PASS!
        self.mgr.create_baseline(
            baseline_id="BL-001",
            stage_name="Release 1.0.0",
            actor="0_orchestrator",
            reason="Lock baseline BL-001 for v1.0.0",
            traces_to={"REL-001": 1}
        )
        s5_after_bl, s5_errs_after = self.gk.check_stage_gate(5)
        self.assertTrue(s5_after_bl, msg=f"Stage 5 should pass with BL-001: {s5_errs_after}")

        # ----------------------------------------------------------------------
        # 1) Attempt to modify SRS-001 without PR/CR post-BL-001 lock -> Blocked by PermissionError!
        # ----------------------------------------------------------------------
        with self.assertRaises(PermissionError) as ctx1:
            self.mgr.put_item("02_srs.json", dict(srs1, description="Unauthorized change"), "1-A_requirements_author", "Unauthorized edit")
        self.assertIn("Baseline Lock Violation", str(ctx1.exception))

        # ----------------------------------------------------------------------
        # 2) Register PR-001 and PENDING CR-001 and attempt update -> Still blocked!
        # ----------------------------------------------------------------------
        pr1 = {
            "id": "PR-001", "type": "PR", "version": 1, "status": "approved",
            "title": "Field Boundary Value Error Report", "description": "Clinical field bug report",
            "traces_to": {"REL-001": 1}, "problem_source": "field_feedback",
            "safety_security_impact": "Medium safety impact",
            "investigation_summary": "Need to refine boundary conditions in SRS-001 and SDS-001",
            "resolution_status": "OPEN"
        }
        self.mgr.put_item("pr_cr_log.json", pr1, "6-A_maintenance_change_analyst", "Create PR-001")

        cr1_pending = {
            "id": "CR-001", "type": "CR", "version": 1, "status": "draft",
            "title": "SRS-001 Boundary Value Fix Change Request", "description": "Change Request",
            "traces_to": {"PR-001": 1}, "change_reason": "Resolution of PR-001",
            "impacted_item_ids": ["SRS-001"],
            "regression_test_ids": ["UT-001", "ST-001"],
            "approval_status": "PENDING"
        }
        self.mgr.put_item("pr_cr_log.json", cr1_pending, "6-A_maintenance_change_analyst", "Create pending CR-001")

        with self.assertRaises(PermissionError) as ctx2:
            self.mgr.put_item("02_srs.json", dict(srs1, description="Pre-approval change"), "1-A_requirements_author", "Premature edit")
        self.assertIn("Baseline Lock Violation", str(ctx2.exception))

        # ----------------------------------------------------------------------
        # 3) Approve CR-001 to APPROVED -> Unlisted item (SRS-002) blocked, designated item (SRS-001) & Suspect Links allowed!
        # ----------------------------------------------------------------------
        cr1_approved = dict(cr1_pending, status="approved", approval_status="APPROVED")
        self.mgr.put_item("pr_cr_log.json", cr1_approved, "6-A_maintenance_change_analyst", "Approve CR-001")

        # Attempt to modify SRS-002 not in CR-001 impacted_item_ids -> Blocked!
        with self.assertRaises(PermissionError) as ctx3:
            self.mgr.put_item("02_srs.json", dict(srs2, description="Out of scope change"), "1-A_requirements_author", "Out of scope edit")
        self.assertIn("Baseline Lock Violation", str(ctx3.exception))

        # Modify designated SRS-001 (v1 -> v2) -> Success!
        srs1_v2 = dict(srs1, description="Boundary values refined (v2)")
        self.mgr.put_item("02_srs.json", srs1_v2, "1-A_requirements_author", "Update SRS-001 per CR-001")

        # As SRS-001 is now v2, downstream SAD-001 and SDS-001 become Suspect Links, allowing cascading edits!
        sad1_v2 = dict(sad1, traces_to={"SRS-001": 2, "SRS-002": 1})
        self.mgr.put_item("03_sad_soup.json", sad1_v2, "2-A_software_architect", "Sync SAD-001 to SRS-001@v2")

        sds1_v2 = dict(sds1, traces_to={"SRS-001": 2, "SRS-002": 1})
        self.mgr.put_item("04_sds.json", sds1_v2, "2-A_software_architect", "Sync SDS-001 to SRS-001@v2")

        ut1_v2 = dict(ut1, traces_to={"SDS-001": 2}, last_run_status="PASS")
        self.mgr.put_item("05_tc.json", ut1_v2, "4-A_blackbox_tester", "Re-verify UT-001")

        it1_v2 = dict(it1, traces_to={"SAD-001": 2}, last_run_status="PASS")
        self.mgr.put_item("05_tc.json", it1_v2, "4-A_blackbox_tester", "Re-verify IT-001")

        st1_v2 = dict(st1, traces_to={"SRS-001": 2, "SRS-002": 1}, last_run_status="PASS")
        self.mgr.put_item("05_tc.json", st1_v2, "4-A_blackbox_tester", "Re-verify ST-001")

        # ----------------------------------------------------------------------
        # 4) Stage 5 Gate while PR-001 is still OPEN and BL-002/REL-002 not created -> Blocked!
        # ----------------------------------------------------------------------
        s5_mid, s5_mid_errs = self.gk.check_stage_gate(5)
        self.assertFalse(s5_mid)
        self.assertTrue(any("Problem Report 'PR-001' has unresolved status 'OPEN'" in e for e in s5_mid_errs))
        self.assertTrue(any("diverges from baseline 'BL-001'" in e for e in s5_mid_errs))

        # ----------------------------------------------------------------------
        # 5) Close PR-001 to CLOSED, sync CR-001, take BL-002 snapshot, and issue REL-002 (v1.0.1) -> Stage 5 100% PASS!
        # ----------------------------------------------------------------------
        pr1_closed = dict(pr1, resolution_status="CLOSED")
        self.mgr.put_item("pr_cr_log.json", pr1_closed, "6-A_maintenance_change_analyst", "Close PR-001 after regression PASS")

        cr1_synced = dict(cr1_approved, traces_to={"PR-001": 2})
        self.mgr.put_item("pr_cr_log.json", cr1_synced, "6-A_maintenance_change_analyst", "Sync CR-001 to closed PR-001@v2")

        rel2 = {
            "id": "REL-002", "type": "REL", "version": 1, "status": "approved",
            "title": "Release 1.0.1", "description": "Maintenance Release v1.0.1",
            "traces_to": {"VT-001": 1, "CR-001": 3}, "release_version": "1.0.1",
            "baseline_id": "BL-002", "known_remaining_anomalies": [],
            "overall_residual_risk_acceptable": True, "release_environment_spec": {"os": "Linux"}
        }
        self.mgr.put_item("06_release.json", rel2, "5-A_release_author", "Create REL-002 for v1.0.1")

        aud5_v2 = dict(aud5, traces_to={"REL-002": 1}, target_item_ids=["REL-002"])
        self.mgr.put_item("audit_findings.json", aud5_v2, "5-B_final_release_auditor", "Audit REL-002 PASS")

        self.mgr.create_baseline(
            baseline_id="BL-002",
            stage_name="Release 1.0.1",
            actor="0_orchestrator",
            reason="Lock baseline BL-002 for v1.0.1",
            traces_to={"REL-002": 1}
        )

        s5_final, s5_final_errs = self.gk.check_stage_gate(5)
        self.assertTrue(s5_final, msg=f"Stage 5 should PASS after v1.0.1 maintenance completion: {s5_final_errs}")

        # Verify additional modification attempts are blocked post-BL-002 as existing CR-001 (v2) is also locked!
        with self.assertRaises(PermissionError) as ctx4:
            self.mgr.put_item("02_srs.json", dict(srs1_v2, description="Unauthorized change post-BL-002"), "1-A_requirements_author", "Post BL-002 edit")
        self.assertIn("Baseline Lock Violation", str(ctx4.exception))

    # ==========================================================================
    # TOOL-REQ-12: Antigravity Framework Packaging (.agents/ Rules, Skills, Hooks) Verification
    # ==========================================================================
    def test_tool_req_12_antigravity_agents_packaging_and_hooks(self):
        """
        Verify structural integrity of Step 5 general Antigravity packaging (.agents/rules, .agents/skills, .agents/hooks.json)
        and actual blocking/injection behavior of PreToolUse/SessionStart hooks
        """
        import subprocess

        repo_root = Path(__file__).resolve().parent
        agents_dir = repo_root / ".agents"

        # 1) Verify existence of mandatory Rules and AGENTS.md
        self.assertTrue((repo_root / "AGENTS.md").exists())
        self.assertTrue((agents_dir / "rules" / "00_core_governance.md").exists())
        self.assertTrue((agents_dir / "rules" / "01_vmodel_stage_gates.md").exists())

        # 2) Verify 3 mandatory Skills and YAML Frontmatter
        expected_skills = [
            "samd-orchestrator",
            "samd-dhf-engine",
            "samd-independent-auditor",
        ]
        for skill_name in expected_skills:
            skill_md = agents_dir / "skills" / skill_name / "SKILL.md"
            self.assertTrue(skill_md.exists(), msg=f"Missing skill: {skill_md}")
            text = skill_md.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), msg=f"Missing YAML frontmatter in {skill_md}")
            self.assertIn(f"name: {skill_name}", text)
            self.assertIn("description:", text)

        # 3) Verify hooks.json structure
        hooks_json_path = agents_dir / "hooks.json"
        self.assertTrue(hooks_json_path.exists())
        hooks_cfg = json.loads(hooks_json_path.read_text(encoding="utf-8"))
        self.assertIn("dhf-store-write-guard", hooks_cfg)
        self.assertIn("samd-session-initializer", hooks_cfg)

        # 4) Verify pre_tool_guard.py actual subprocess execution (block direct store/*.json modification)
        guard_script = agents_dir / "hooks" / "pre_tool_guard.py"
        self.assertTrue(guard_script.exists())

        # 4-A: Direct edit_file on store/02_srs.json -> Must return deny
        deny_payload_store = json.dumps({
            "toolCall": {
                "name": "edit_file",
                "args": {
                    "Path": str(repo_root / "projects" / "pathology_slide_qc" / "store" / "02_srs.json")
                }
            }
        })
        res_deny_1 = subprocess.run(
            [sys.executable, str(guard_script)],
            input=deny_payload_store,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(agents_dir),
            check=True
        )
        out_deny_1 = json.loads(res_deny_1.stdout.strip())
        self.assertEqual(out_deny_1.get("decision"), "deny")
        self.assertIn("ISO 13485", out_deny_1.get("reason", ""))

        # 4-B: Direct write_file on docs/02_SRS_Software_Requirements_Specification.md -> Must return deny
        deny_payload_docs = json.dumps({
            "toolCall": {
                "name": "write_file",
                "args": {
                    "Path": str(repo_root / "projects" / "pathology_slide_qc" / "docs" / "02_SRS_Software_Requirements_Specification.md")
                }
            }
        })
        res_deny_2 = subprocess.run(
            [sys.executable, str(guard_script)],
            input=deny_payload_docs,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(agents_dir),
            check=True
        )
        out_deny_2 = json.loads(res_deny_2.stdout.strip())
        self.assertEqual(out_deny_2.get("decision"), "deny")

        # 4-C: Normal source code editing on src/slide_preprocessor.py -> Must return allow
        allow_payload_src = json.dumps({
            "toolCall": {
                "name": "edit_file",
                "args": {
                    "Path": str(repo_root / "projects" / "pathology_slide_qc" / "src" / "slide_preprocessor.py")
                }
            }
        })
        res_allow = subprocess.run(
            [sys.executable, str(guard_script)],
            input=allow_payload_src,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(agents_dir),
            check=True
        )
        out_allow = json.loads(res_allow.stdout.strip())
        self.assertEqual(out_allow.get("decision"), "allow")

        # 5) Verify session_start_banner.py actual subprocess execution
        banner_script = agents_dir / "hooks" / "session_start_banner.py"
        res_banner = subprocess.run(
            [sys.executable, str(banner_script)],
            input="{}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(agents_dir),
            check=True
        )
        out_banner = json.loads(res_banner.stdout.strip())
        self.assertIn("injectSteps", out_banner)
        sys_msg = out_banner["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("SaMD Dev Framework Active", sys_msg)


if __name__ == "__main__":
    unittest.main()
