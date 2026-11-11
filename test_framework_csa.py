#!/usr/bin/env python3
"""
test_framework_csa.py - SaMD 프레임워크 도구 자체 밸리데이션 테스트 스위트
(ISO 13485 4.1.6, ISO/TR 80002-2 & FDA CSA 준수 입증)

[검증 대상 도구]
- dhf_cli.py (DHFManager, DHFLock, 스키마 검증, 해시체인, 양방향 추적성, 마크다운 렌더러)
- gatekeeper.py (Gatekeeper, AST 시그니처 계약 검증, V-모델 Stage 0~5 Gate)
"""

import os
import sys
import json
import tempfile
import unittest
import multiprocessing
from pathlib import Path

# 테스트 대상 모듈 임포트
from dhf_cli import DHFManager, DHFLock
from gatekeeper import Gatekeeper


def _mp_concurrent_worker(workspace_str: str, worker_idx: int, ops_per_worker: int) -> None:
    """멀티프로세스 동시성 스트레스 테스트용 워커 함수 (별도 OS 프로세스에서 실행)"""
    mgr = DHFManager(Path(workspace_str))
    for step in range(ops_per_worker):
        # 1) 워커별 고유 항목 생성 및 반복 버전업
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
    """프레임워크 도구 자체 밸리데이션 (CSA) 테스트 스위트"""

    def setUp(self):
        # 각 테스트마다 완전히 격리된 임시 워크스페이스 생성
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name)
        self.mgr = DHFManager(self.workspace_root)
        self.mgr.init_store()
        self.gk = Gatekeeper(self.workspace_root)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ==========================================================================
    # TOOL-REQ-01: 동시성 제어 및 파일 잠금
    # ==========================================================================
    def test_tool_req_01_flock_concurrency_lock(self):
        """DHFLock이 원자적 배타 잠금을 올바르게 획득하고 해제하는지 검증"""
        lock_file = self.mgr.lock_file
        with DHFLock(lock_file) as lock:
            self.assertTrue(lock_file.exists())
            self.assertIsNotNone(lock._fd)
        # Lock 컨텍스트 종료 후 파일이 닫혔는지 확인
        self.assertTrue(lock._fd.closed)

    # ==========================================================================
    # TOOL-REQ-02: 엄격한 단일 소유권 (Single Ownership) 강제
    # ==========================================================================
    def test_tool_req_02_strict_single_ownership(self):
        """허가된 소유자만 쓰기 가능하며, 미인가 에이전트의 쓰기 시도는 차단됨을 검증"""
        srs_item = {
            "id": "SRS-001",
            "type": "SRS",
            "version": 1,
            "status": "draft",
            "title": "혈압 이상 경고 기능",
            "description": "수축기 혈압 180 이상 시 경고 발생",
            "traces_to": {"URS-001": 1},
            "req_category": "functional",
            "verification_method": "system_test",
            "measurable_criteria": "경고 알람 1초 이내 발생"
        }

        # 1) 올바른 소유자: 1-A_requirements_author -> 성공
        saved = self.mgr.put_item(
            filename="02_srs.json",
            item=srs_item,
            actor="1-A_requirements_author",
            reason="Initial SRS creation"
        )
        self.assertEqual(saved["id"], "SRS-001")
        self.assertEqual(saved["version"], 1)

        # 2) 미인가 소유자: 2-A_software_architect가 02_srs.json 수정을 시도 -> PermissionError
        srs_item_modified = dict(srs_item)
        srs_item_modified["title"] = "무단 수정된 혈압 경고"
        with self.assertRaises(PermissionError) as ctx:
            self.mgr.put_item(
                filename="02_srs.json",
                item=srs_item_modified,
                actor="2-A_software_architect",
                reason="Unauthorized modification attempt"
            )
        self.assertIn("Ownership Violation", str(ctx.exception))

    # ==========================================================================
    # TOOL-REQ-03: Base Envelope 및 특화 스키마 유효성 검증
    # ==========================================================================
    def test_tool_req_03_schema_envelope_validation(self):
        """Envelope 공통 필드 누락, 접두사 불일치, 특화 필드 누락 차단 검증"""
        # 1) Base Envelope 필수 필드 (예: description 누락)
        bad_item_1 = {
            "id": "URS-001",
            "type": "URS",
            "version": 1,
            "status": "draft",
            "title": "혈압 모니터링",
            # description missing
            "traces_to": {},
            "stakeholder": "clinician",
            "acceptance_criteria": "인수 기준"
        }
        with self.assertRaises(ValueError) as ctx:
            self.mgr.put_item("01_urs.json", bad_item_1, "1-A_requirements_author", "Test")
        self.assertIn("Missing base envelope field 'description'", str(ctx.exception))

        # 2) 접두사 불일치 (01_urs.json에 SRS-001 저장 시도)
        bad_item_2 = {
            "id": "SRS-001",
            "type": "SRS",
            "version": 1,
            "status": "draft",
            "title": "타입 불일치",
            "description": "설명",
            "traces_to": {},
            "stakeholder": "clinician",
            "acceptance_criteria": "인수 기준"
        }
        with self.assertRaises(ValueError) as ctx:
            self.mgr.put_item("01_urs.json", bad_item_2, "1-A_requirements_author", "Test")
        self.assertIn("Prefix/Type Mismatch", str(ctx.exception))

        # 3) 특화 필수 필드 누락 (02_srs.json에 measurable_criteria 누락)
        bad_item_3 = {
            "id": "SRS-001",
            "type": "SRS",
            "version": 1,
            "status": "draft",
            "title": "정량 기준 누락",
            "description": "설명",
            "traces_to": {},
            "req_category": "functional",
            "verification_method": "unit_test"
            # measurable_criteria missing
        }
        with self.assertRaises(ValueError) as ctx:
            self.mgr.put_item("02_srs.json", bad_item_3, "1-A_requirements_author", "Test")
        self.assertIn("Missing specific field 'measurable_criteria'", str(ctx.exception))

    # ==========================================================================
    # TOOL-REQ-04: 버전 자동 증가 & SHA-256 해시 체인 변조 감지
    # ==========================================================================
    def test_tool_req_04_versioning_and_audit_hash_chain(self):
        """버전 자동 증가와 audit_history.jsonl의 해시 체인 무결성 및 변조 탐지 검증"""
        urs_item = {
            "id": "URS-001",
            "type": "URS",
            "version": 1,
            "status": "draft",
            "title": "초기 사용자 요구",
            "description": "버전 1 설명",
            "traces_to": {},
            "stakeholder": "clinician",
            "acceptance_criteria": "인수 기준 v1"
        }

        # 1) v1 등록
        it1 = self.mgr.put_item("01_urs.json", urs_item, "1-A_requirements_author", "Initial draft")
        self.assertEqual(it1["version"], 1)

        # 2) 수정 시 v2 자동 증가
        urs_item_v2 = dict(it1)
        urs_item_v2["description"] = "버전 2 보완된 설명"
        it2 = self.mgr.put_item("01_urs.json", urs_item_v2, "1-A_requirements_author", "Update description")
        self.assertEqual(it2["version"], 2)

        # 3) 해시 체인 무결성 검증 -> 100% PASS
        valid, errors = self.mgr.verify_audit_history()
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)

        # 4) 해시 체인 인위적 변조 (Tampering) 주입 -> 즉시 감지되어야 함
        with open(self.mgr.audit_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 첫 번째 라인의 actor를 몰래 변경
        record_tampered = json.loads(lines[0])
        record_tampered["actor"] = "HACKER_ATTACKER"
        lines[0] = json.dumps(record_tampered) + "\n"
        with open(self.mgr.audit_log_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # 재검증 -> 변조 적발 (FAIL)
        valid_after, errors_after = self.mgr.verify_audit_history()
        self.assertFalse(valid_after)
        self.assertTrue(any("Tampering detected" in e for e in errors_after))

    # ==========================================================================
    # TOOL-REQ-05: 중앙 양방향 추적성 및 Suspect Link 연쇄 전파
    # ==========================================================================
    def test_tool_req_05_traceability_and_suspect_link_propagation(self):
        """상위 버전 변경 시 하위 항목으로 Suspect Link가 연쇄 전파되고, 갱신 시 해소됨을 검증"""
        # URS-001 (v1) 등록
        urs = {
            "id": "URS-001", "type": "URS", "version": 1, "status": "approved",
            "title": "임상 요구", "description": "요구 설명", "traces_to": {},
            "stakeholder": "clinician", "acceptance_criteria": "기준"
        }
        self.mgr.put_item("01_urs.json", urs, "1-A_requirements_author", "Create URS")

        # SRS-001 (v1, traces_to: URS-001@1) 등록
        srs = {
            "id": "SRS-001", "type": "SRS", "version": 1, "status": "approved",
            "title": "SW 요구", "description": "SRS 설명", "traces_to": {"URS-001": 1},
            "req_category": "functional", "verification_method": "unit_test",
            "measurable_criteria": "기준치"
        }
        self.mgr.put_item("02_srs.json", srs, "1-A_requirements_author", "Create SRS")

        # SDS-001 (v1, traces_to: SRS-001@1) 등록
        sds = {
            "id": "SDS-001", "type": "SDS", "version": 1, "status": "approved",
            "title": "상세설계", "description": "함수 설계", "traces_to": {"SRS-001": 1},
            "target_file_path": "src/monitor.py", "unit_type": "function",
            "callable_name": "calc_vital", "callable_signature": "def calc_vital(val: int) -> int",
            "parameters_contract": [{"name": "val", "type": "int"}],
            "return_contract": {"type": "int"}, "exception_contract": [],
            "algorithm_specification": "val * 2"
        }
        self.mgr.put_item("04_sds.json", sds, "2-A_software_architect", "Create SDS")

        # 추적성 확인: 현재 모두 버전이 일치하므로 suspect 없음
        trace = self.mgr.sync_traceability()
        self.assertEqual(len(trace["coverage_summary"]["suspect_links"]), 0)

        # 이제 URS-001을 수정하여 v2로 버전업!
        urs_v2 = dict(urs)
        urs_v2["description"] = "변경된 임상 요구"
        self.mgr.put_item("01_urs.json", urs_v2, "1-A_requirements_author", "Bump URS to v2")

        # 추적성 재동기화 후 확인:
        # SRS-001(직접 참조) 뿐만 아니라 SDS-001(간접 하위)까지 연쇄적으로 suspect 전파되어야 함
        trace_after = self.mgr.sync_traceability()
        suspects = trace_after["coverage_summary"]["suspect_links"]
        self.assertIn("SRS-001", suspects)
        self.assertIn("SDS-001", suspects)

        # SRS-001이 URS-001의 v2를 반영하여 업데이트하면
        srs_v2 = dict(srs)
        srs_v2["traces_to"] = {"URS-001": 2}
        self.mgr.put_item("02_srs.json", srs_v2, "1-A_requirements_author", "Reflect URS v2 in SRS")

        # 이제 SRS-001의 직접 suspect는 해소되지만, SDS-001은 SRS-001이 v2로 올랐으므로 여전히 suspect
        trace_mid = self.mgr.sync_traceability()
        self.assertNotIn("SRS-001", trace_mid["coverage_summary"]["suspect_links"])
        self.assertIn("SDS-001", trace_mid["coverage_summary"]["suspect_links"])

        # SDS-001도 SRS-001@2를 반영하면 모든 suspect 완전 해소!
        sds_v2 = dict(sds)
        sds_v2["traces_to"] = {"SRS-001": 2}
        self.mgr.put_item("04_sds.json", sds_v2, "2-A_software_architect", "Reflect SRS v2 in SDS")

        trace_final = self.mgr.sync_traceability()
        self.assertEqual(len(trace_final["coverage_summary"]["suspect_links"]), 0)

    # ==========================================================================
    # TOOL-REQ-06: 심사관용 규제 보고서 (docs/*.md) 자동 렌더링
    # ==========================================================================
    def test_tool_req_06_markdown_reports_rendering(self):
        """docs/*.md 8개 보고서가 정상 생성되며, VT 수동체크리스트 양식이 올바른지 검증"""
        # VT 시험 항목 등록
        vt_item = {
            "id": "VT-001", "type": "VT", "version": 1, "status": "draft",
            "title": "화면 경고 시각적 확인 시험", "description": "경고등 점등 육안 확인",
            "traces_to": {"URS-001": 1}, "test_level": "VT", "execution_mode": "manual_checklist",
            "is_negative_test": False, "test_file_path": "docs/VT_수동시험체크리스트.md",
            "test_callable_name": "manual_visual_check", "expected_outcome": "빨간색 점멸 확인",
            "last_run_status": "PENDING", "validation_protocol": "환자 화면에서 180초 대기 후 경고등 확인",
            "human_verified_by": "김임상", "human_observation_notes": "육안 확인 대기 중"
        }
        self.mgr.put_item("05_tc.json", vt_item, "4-A_blackbox_tester", "Register VT test")

        rendered = self.mgr.render_markdown_docs()
        self.assertEqual(len(rendered), 8)

        # VT 체크리스트 내용 확인
        vt_doc = self.workspace_root / "docs" / "VT_수동시험체크리스트.md"
        self.assertTrue(vt_doc.exists())
        with open(vt_doc, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("VT-001", content)
        self.assertIn("[ ] PENDING", content)
        self.assertIn("환자 화면에서 180초 대기", content)

    # ==========================================================================
    # TOOL-REQ-07: AST 시그니처 및 코드 품질 검문소 (Gatekeeper AST)
    # ==========================================================================
    def test_tool_req_07_ast_signature_contract_and_code_quality(self):
        """AST 파싱을 통해 시그니처 불일치, TODO 잔존, 빈 함수, 미승인 SOUP를 철저히 차단하는지 검증"""
        src_file = self.workspace_root / "src" / "algorithm.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)

        sds_item = {
            "id": "SDS-001", "type": "SDS", "version": 1, "status": "approved",
            "title": "수축기 혈압 위험 판정 알고리즘", "description": "설계 계약",
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

        # Case 1: 시그니처 불일치 (파라미터 이름이 pressure가 아니라 val임)
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\ndef evaluate_systolic(val: int) -> bool:\n    return val >= 140\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertFalse(passed)
        self.assertTrue(any("Parameter mismatch" in e for e in errors))

        # Case 2: TODO 주석 잔존
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\n# TODO: need review\ndef evaluate_systolic(pressure: int) -> bool:\n    return pressure >= 140\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertFalse(passed)
        self.assertTrue(any("Unfinished code marker" in e for e in errors))

        # Case 3: pass 단독 빈 함수
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\ndef evaluate_systolic(pressure: int) -> bool:\n    pass\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertFalse(passed)
        self.assertTrue(any("contains only 'pass'" in e for e in errors))

        # Case 4: 미승인 SOUP import (03_sad_soup.json에 없는 외부 패키지 import requests)
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\nimport requests\ndef evaluate_systolic(pressure: int) -> bool:\n    return pressure >= 140\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertFalse(passed)
        self.assertTrue(any("Unapproved SOUP import 'requests'" in e for e in errors))

        # Case 5: 정상 완성 코드 -> 100% PASS
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# @traces: SDS-001@1\nimport math\ndef evaluate_systolic(pressure: int) -> bool:\n    return pressure >= 140\n")
        passed, errors = self.gk.check_signatures_and_code_quality()
        self.assertTrue(passed, msg=f"Expected PASS, but got errors: {errors}")

    # ==========================================================================
    # TOOL-REQ-08: V-모델 Stage Gate 기계적 통제
    # ==========================================================================
    def test_tool_req_08_stage_gate_enforcement(self):
        """Stage 0 Gate 검사에서 항목 누락 시 차단되고, 완비 시 100% PASS되는지 검증"""
        # 1) 빈 저장소에서 Stage 0 Gate 검사 -> 차단
        passed, errors = self.gk.check_stage_gate(0)
        self.assertFalse(passed)
        self.assertTrue(any("Stage 0 Failure" in e for e in errors))

        # 2) Stage 0 필수 항목 완비: INT, LIT, REG, SDP 및 감사 판정(PASS)
        int_it = {
            "id": "INT-001", "type": "INT", "version": 1, "status": "approved",
            "title": "혈압 모니터링 기기", "description": "의도된 사용",
            "traces_to": {}, "intended_use": "고혈압 환자 혈압 모니터링",
            "indications_for_use": "성인 고혈압", "target_patient_population": "성인",
            "intended_users": "의료진", "use_environment": "병원",
            "clinical_benefit": "조기 혈압 경고", "device_category": "SaMD",
            "has_ai_ml": False, "has_network": True, "has_gui": True,
            "has_alarm": True, "project_mode": "new"
        }
        self.mgr.put_item("00_intake.json", int_it, "0-0_intake_agent", "INT creation")

        lit_it = {
            "id": "LIT-001", "type": "LIT", "version": 1, "status": "approved",
            "title": "AHA 혈압 가이드라인", "description": "문헌 조사",
            "traces_to": {"INT-001": 1}, "category": "clinical_guideline",
            "source_citation": "AHA 2024", "key_findings": "수축기 140 기준",
            "benchmark_criteria": "정확도 95%", "known_hazards_identified": ["오경보"]
        }
        self.mgr.put_item("00_literature.json", lit_it, "0-A_literature_researcher", "LIT creation")

        reg_it = {
            "id": "REG-001", "type": "REG", "version": 1, "status": "approved",
            "title": "규제 전략 및 등급", "description": "Class B 분류",
            "traces_to": {"INT-001": 1}, "safety_class": "Class B",
            "fda_doc_level": "Basic", "target_regions": ["MFDS", "FDA"],
            "active_profiles": ["alarm_system"], "applicable_standards": ["IEC 62304", "ISO 14971"],
            "regulatory_mandate": "식약처 2등급 인허가 요건 준수"
        }
        self.mgr.put_item("00_regulatory.json", reg_it, "0-B_regulatory_strategist", "REG creation")

        sdp_it = {
            "id": "SDP-001", "type": "SDP", "version": 1, "status": "approved",
            "title": "SW 개발계획서", "description": "V-모델 프로세스",
            "traces_to": {"REG-001": 1}, "project_profile": {"safety_class": "Class B"},
            "plan_category": "lifecycle", "language_and_runtime": "Python 3.13",
            "coding_standards": ["PEP8", "IEC 62304"], "risk_acceptability_rule": "ALARP",
            "min_test_coverage_pct": 80, "workflow_steps": [{"step": 1}]
        }
        self.mgr.put_item("00_sdp_plan.json", sdp_it, "0-C_sdp_planner", "SDP creation")

        aud_it = {
            "id": "AUD-001", "type": "AUD", "version": 1, "status": "approved",
            "title": "Stage 0 감사 완료", "description": "기획 및 규제 전략 적합 판정",
            "traces_to": {"SDP-001": 1}, "stage": "Stage 0",
            "auditor_role": "0-D_stage0_auditor", "verdict": "PASS",
            "target_agent": "0-C_sdp_planner", "target_item_ids": ["SDP-001"],
            "finding_details": "모든 규제 및 기획 요건 적합",
            "remediation_required": "None", "resolution_status": "CLOSED"
        }
        self.mgr.put_item("audit_findings.json", aud_it, "0-D_stage0_auditor", "Stage 0 Audit PASS")

        # 다시 Stage 0 Gate 검사 -> 100% 통과 확인!
        passed_final, errors_final = self.gk.check_stage_gate(0)
        self.assertTrue(passed_final, msg=f"Stage 0 should PASS, but failed with: {errors_final}")

    # ==========================================================================
    # TOOL-REQ-09: CLI 우회 OS 레벨 직접 파일 변조(Direct File Tampering) 탐지 및 차단
    # ==========================================================================
    def test_tool_req_09_direct_os_file_tampering_blocked(self):
        """
        dhf_cli.py를 거치지 않고 OS 레벨에서 store/*.json의 수치/상태를 직접 수정하거나
        항목을 무단 삽입/삭제했을 때 verify_audit_history와 gatekeeper.check_stage_gate가
        이를 100% 적발하고 차단하는지 검증 (21 CFR Part 11 / FDA CSA 무결성)
        """
        # 먼저 Stage 0 정상 구성 및 SRS-001, UT-001 등록
        self.test_tool_req_08_stage_gate_enforcement()

        srs_item = {
            "id": "SRS-001", "type": "SRS", "version": 1, "status": "approved",
            "title": "혈압 경보 임계치", "description": "수축기 180mmHg 초과 시 알람",
            "traces_to": {"URS-001": 1}, "req_category": "safety",
            "verification_method": "system_test",
            "measurable_criteria": "systolic > 180 일 때 1초 이내 경보"
        }
        self.mgr.put_item("02_srs.json", srs_item, "1-A_requirements_author", "Create SRS-001")

        ut_item = {
            "id": "UT-001", "type": "UT", "version": 1, "status": "approved",
            "title": "단위 검증 시험", "description": "초기 실패 상태",
            "traces_to": {"SDS-001": 1}, "test_level": "UT",
            "execution_mode": "automated", "is_negative_test": False,
            "test_file_path": "tests/test_ut.py", "test_callable_name": "test_bp",
            "expected_outcome": "PASS", "last_run_status": "FAIL"
        }
        self.mgr.put_item("05_tc.json", ut_item, "4-A_blackbox_tester", "Create UT-001 with FAIL")

        valid_init, errs_init = self.mgr.verify_audit_history()
        self.assertTrue(valid_init, msg=f"Initial state should be valid: {errs_init}")

        # [공격 1-A] OS 레벨에서 05_tc.json의 last_run_status를 FAIL -> PASS로 몰래 직접 변조
        tc_path = self.workspace_root / "store" / "05_tc.json"
        with open(tc_path, "r", encoding="utf-8") as f:
            tc_raw = f.read()
        with open(tc_path, "w", encoding="utf-8") as f:
            f.write(tc_raw.replace('"last_run_status": "FAIL"', '"last_run_status": "PASS"'))

        valid_tamper1, errs_tamper1 = self.mgr.verify_audit_history()
        self.assertFalse(valid_tamper1)
        self.assertTrue(any("Direct Tampering Detected in '05_tc.json'" in e for e in errs_tamper1))

        # Gatekeeper check_stage_gate 호출 시에도 즉시 감사/스토어 무결성 위반으로 차단되어야 함
        gk_pass1, gk_errs1 = self.gk.check_stage_gate(0)
        self.assertFalse(gk_pass1)
        self.assertTrue(any("Audit & Store Integrity Violation" in e for e in gk_errs1))

        # 05_tc.json 원상 복구 후 정상 확인
        with open(tc_path, "w", encoding="utf-8") as f:
            f.write(tc_raw)
        valid_restored, _ = self.mgr.verify_audit_history()
        self.assertTrue(valid_restored)

        # [공격 1-B] OS 레벨에서 02_srs.json의 정량적 기준치를 직접 변조하고 유령 항목(SRS-999) 무단 삽입
        srs_path = self.workspace_root / "store" / "02_srs.json"
        with open(srs_path, "r", encoding="utf-8") as f:
            srs_data = json.load(f)
        srs_backup = json.dumps(srs_data, indent=2, ensure_ascii=False)

        srs_data["items"][0]["measurable_criteria"] = "systolic > 999 (조작된 수치)"
        rogue_item = dict(srs_data["items"][0])
        rogue_item["id"] = "SRS-999"
        srs_data["items"].append(rogue_item)
        with open(srs_path, "w", encoding="utf-8") as f:
            json.dump(srs_data, f, indent=2, ensure_ascii=False)

        valid_tamper2, errs_tamper2 = self.mgr.verify_audit_history()
        self.assertFalse(valid_tamper2)
        self.assertTrue(any("Item 'SRS-001' current state in store diverges" in e for e in errs_tamper2))
        self.assertTrue(any("Item 'SRS-999' exists in store but has no audit trail record" in e for e in errs_tamper2))

        # [공격 1-C] OS 레벨에서 02_srs.json의 항목을 무단 삭제 (빈 배열로 덮어쓰기)
        with open(srs_path, "w", encoding="utf-8") as f:
            json.dump({"items": []}, f)
        valid_tamper3, errs_tamper3 = self.mgr.verify_audit_history()
        self.assertFalse(valid_tamper3)
        self.assertTrue(any("Item 'SRS-001'" in e and "was unauthorizedly deleted from store" in e for e in errs_tamper3))

        # 원상 복구
        with open(srs_path, "w", encoding="utf-8") as f:
            f.write(srs_backup)
        self.assertTrue(self.mgr.verify_audit_history()[0])

    # ==========================================================================
    # TOOL-REQ-10: 다중 프로세스(10개 병렬 프로세스) 동시 쓰기 레이스 컨디션 스트레스 검증
    # ==========================================================================
    def test_tool_req_10_multiprocess_concurrency_stress(self):
        """
        10개의 독립 OS 프로세스가 동시에 put_item을 경쟁적으로 호출(총 50회 트랜잭션)할 때
        fcntl.flock(DHFLock)이 JSON 파손, Lost Update, 해시 체인 깨짐 없이 100% 직렬화하는지 검증
        """
        urs_item = {
            "id": "URS-001", "type": "URS", "version": 1, "status": "approved",
            "title": "동시성 테스트 상위 요구사항", "description": "기준 항목",
            "traces_to": {}, "stakeholder": "clinician", "acceptance_criteria": "기준"
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

        # 1) 감사 이력 해시 체인 및 store 교차 대조 무결성 100% 검증
        valid, errors = self.mgr.verify_audit_history()
        self.assertTrue(valid, msg=f"Audit history or store corrupted under concurrency: {errors}")

        # 2) 총 트랜잭션 수 확인: 초기 URS-001(1건) + 10개 프로세스 * 5회(50건) = 정확히 51건이어야 함 (Lost Update 0건)
        last_seq, _ = self.mgr.get_last_audit_record()
        self.assertEqual(last_seq, 1 + (num_workers * ops_per_worker))

        # 3) 02_srs.json의 각 워커 항목(SRS-W00 ~ SRS-W09)이 모두 정확히 version == 5에 도달했는지 확인
        with open(self.workspace_root / "store" / "02_srs.json", "r", encoding="utf-8") as f:
            srs_items = json.load(f).get("items", [])
        self.assertEqual(len(srs_items), num_workers)
        for it in srs_items:
            self.assertEqual(it["version"], ops_per_worker)

    # ==========================================================================
    # TOOL-REQ-11: 릴리즈 베이스라인(BL-xxx) 잠금 및 사후 유지보수(PR/CR) 기계적 통제 검증
    # ==========================================================================
    def test_tool_req_11_baseline_and_pr_cr_maintenance_control(self):
        """
        IEC 62304 Clause 6, 8, 9 준수 검증:
        1) BL-001 확정 후 PR/CR 없이 잠긴 항목 수정 시도 -> PermissionError 즉시 차단
        2) PENDING 상태의 CR로 수정 시도 -> PermissionError 차단
        3) APPROVED 상태의 CR 발행 시, 지정되지 않은 항목 수정은 차단하고 영향 항목 및 Suspect Link만 수정 허용
        4) 회귀 테스트(regression_test_ids) 미통과 또는 PR 미종결(OPEN) 시 Stage 5 Gate 차단
        5) PR 종결(CLOSED), 신규 베이스라인(BL-002) 및 릴리즈(REL-002) 등록 시 Stage 5 Gate 통과 및 재잠금 확인
        """
        # Stage 0 기본 세팅
        self.test_tool_req_08_stage_gate_enforcement()

        # V-모델 핵심 산출물 세팅 (URS-001, SRS-001, SRS-002, SAD-001, SDS-001, UT-001, ST-001, VT-001)
        urs = {
            "id": "URS-001", "type": "URS", "version": 1, "status": "approved",
            "title": "임상 요구", "description": "설명", "traces_to": {"INT-001": 1},
            "stakeholder": "clinician", "acceptance_criteria": "기준"
        }
        self.mgr.put_item("01_urs.json", urs, "1-A_requirements_author", "Create URS-001")

        srs1 = {
            "id": "SRS-001", "type": "SRS", "version": 1, "status": "approved",
            "title": "기능 요구 1", "description": "설명 1", "traces_to": {"URS-001": 1},
            "req_category": "functional", "verification_method": "system_test",
            "measurable_criteria": "기준 1"
        }
        self.mgr.put_item("02_srs.json", srs1, "1-A_requirements_author", "Create SRS-001")

        srs2 = {
            "id": "SRS-002", "type": "SRS", "version": 1, "status": "approved",
            "title": "보안 요구 2", "description": "설명 2", "traces_to": {"URS-001": 1},
            "req_category": "security", "verification_method": "system_test",
            "measurable_criteria": "기준 2"
        }
        self.mgr.put_item("02_srs.json", srs2, "1-A_requirements_author", "Create SRS-002")

        sad1 = {
            "id": "SAD-001", "type": "SAD", "version": 1, "status": "approved",
            "title": "모듈 1", "description": "아키텍처", "traces_to": {"SRS-001": 1, "SRS-002": 1},
            "module_name": "CoreMod", "safety_class": "Class B",
            "module_responsibility": "핵심 처리", "public_interfaces": ["run()"],
            "segregation_strategy": "프로세스 격리"
        }
        self.mgr.put_item("03_sad_soup.json", sad1, "2-A_software_architect", "Create SAD-001")

        sds1 = {
            "id": "SDS-001", "type": "SDS", "version": 1, "status": "approved",
            "title": "상세설계 1", "description": "설계", "traces_to": {"SRS-001": 1, "SRS-002": 1},
            "target_file_path": "src/core.py", "unit_type": "function",
            "callable_name": "run", "callable_signature": "def run(x: int) -> int",
            "parameters_contract": [{"name": "x", "type": "int"}],
            "return_contract": {"type": "int"}, "exception_contract": [],
            "algorithm_specification": "return x"
        }
        self.mgr.put_item("04_sds.json", sds1, "2-A_software_architect", "Create SDS-001")

        ut1 = {
            "id": "UT-001", "type": "UT", "version": 1, "status": "approved",
            "title": "단위시험 1", "description": "UT", "traces_to": {"SDS-001": 1},
            "test_level": "UT", "execution_mode": "automated", "is_negative_test": False,
            "test_file_path": "tests/test_ut.py", "test_callable_name": "test_ut",
            "expected_outcome": "PASS", "last_run_status": "PASS"
        }
        self.mgr.put_item("05_tc.json", ut1, "4-A_blackbox_tester", "Create UT-001")

        it1 = {
            "id": "IT-001", "type": "IT", "version": 1, "status": "approved",
            "title": "통합시험 1", "description": "IT", "traces_to": {"SAD-001": 1},
            "test_level": "IT", "execution_mode": "automated", "is_negative_test": False,
            "test_file_path": "tests/test_it.py", "test_callable_name": "test_it",
            "expected_outcome": "PASS", "last_run_status": "PASS"
        }
        self.mgr.put_item("05_tc.json", it1, "4-A_blackbox_tester", "Create IT-001")

        st1 = {
            "id": "ST-001", "type": "ST", "version": 1, "status": "approved",
            "title": "시스템시험 1", "description": "ST", "traces_to": {"SRS-001": 1, "SRS-002": 1},
            "test_level": "ST", "execution_mode": "automated", "is_negative_test": False,
            "test_file_path": "tests/test_st.py", "test_callable_name": "test_st",
            "expected_outcome": "PASS", "last_run_status": "PASS"
        }
        self.mgr.put_item("05_tc.json", st1, "4-A_blackbox_tester", "Create ST-001")

        vt1 = {
            "id": "VT-001", "type": "VT", "version": 1, "status": "approved",
            "title": "밸리데이션 1", "description": "VT", "traces_to": {"URS-001": 1},
            "test_level": "VT", "execution_mode": "manual_checklist", "is_negative_test": False,
            "test_file_path": "docs/VT_수동시험체크리스트.md", "test_callable_name": "manual_vt",
            "expected_outcome": "PASS", "last_run_status": "PASS"
        }
        self.mgr.put_item("05_tc.json", vt1, "4-A_blackbox_tester", "Create VT-001")

        # Release 1.0.0 및 BL-001 생성
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

        # BL-001 확정 전 Stage 5 Gate 실행 -> BL-001 미존재로 차단되어야 함!
        s5_before_bl, s5_errs_before = self.gk.check_stage_gate(5)
        self.assertFalse(s5_before_bl)
        self.assertTrue(any("Stage 5 Baseline Failure" in e for e in s5_errs_before))

        # BL-001 스냅샷 생성 -> Stage 5 Gate 100% PASS!
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
        # 1) BL-001 잠금 후 PR/CR 없이 SRS-001 수정 시도 -> PermissionError 차단!
        # ----------------------------------------------------------------------
        with self.assertRaises(PermissionError) as ctx1:
            self.mgr.put_item("02_srs.json", dict(srs1, description="무단 변경"), "1-A_requirements_author", "Unauthorized edit")
        self.assertIn("Baseline Lock Violation", str(ctx1.exception))

        # ----------------------------------------------------------------------
        # 2) PR-001 및 PENDING 상태의 CR-001 등록 후 수정 시도 -> 여전히 차단!
        # ----------------------------------------------------------------------
        pr1 = {
            "id": "PR-001", "type": "PR", "version": 1, "status": "approved",
            "title": "현장 경계값 오류 보고", "description": "임상 현장 버그 리포트",
            "traces_to": {"REL-001": 1}, "problem_source": "field_feedback",
            "safety_security_impact": "Medium safety impact",
            "investigation_summary": "SRS-001 및 SDS-001 경계 조건 보완 필요",
            "resolution_status": "OPEN"
        }
        self.mgr.put_item("pr_cr_log.json", pr1, "6-A_maintenance_change_analyst", "Create PR-001")

        cr1_pending = {
            "id": "CR-001", "type": "CR", "version": 1, "status": "draft",
            "title": "SRS-001 경계값 수정 변경요청", "description": "변경 요청서",
            "traces_to": {"PR-001": 1}, "change_reason": "PR-001 해결",
            "impacted_item_ids": ["SRS-001"],
            "regression_test_ids": ["UT-001", "ST-001"],
            "approval_status": "PENDING"
        }
        self.mgr.put_item("pr_cr_log.json", cr1_pending, "6-A_maintenance_change_analyst", "Create pending CR-001")

        with self.assertRaises(PermissionError) as ctx2:
            self.mgr.put_item("02_srs.json", dict(srs1, description="승인 전 변경"), "1-A_requirements_author", "Premature edit")
        self.assertIn("Baseline Lock Violation", str(ctx2.exception))

        # ----------------------------------------------------------------------
        # 3) CR-001을 APPROVED로 승인 -> 미지정 항목(SRS-002) 수정은 차단, 지정 항목(SRS-001) 및 Suspect Link만 허용!
        # ----------------------------------------------------------------------
        cr1_approved = dict(cr1_pending, status="approved", approval_status="APPROVED")
        self.mgr.put_item("pr_cr_log.json", cr1_approved, "6-A_maintenance_change_analyst", "Approve CR-001")

        # CR-001의 impacted_item_ids에 없는 SRS-002 수정 시도 -> 차단!
        with self.assertRaises(PermissionError) as ctx3:
            self.mgr.put_item("02_srs.json", dict(srs2, description="범위 외 변경"), "1-A_requirements_author", "Out of scope edit")
        self.assertIn("Baseline Lock Violation", str(ctx3.exception))

        # 지정된 SRS-001 수정 (v1 -> v2) -> 성공!
        srs1_v2 = dict(srs1, description="경계값 보완 완료 (v2)")
        self.mgr.put_item("02_srs.json", srs1_v2, "1-A_requirements_author", "Update SRS-001 per CR-001")

        # SRS-001이 v2가 되었으므로 하위 SAD-001, SDS-001이 Suspect Link로 자동 전환되어 연쇄 수정 허용됨!
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
        # 4) PR-001이 아직 OPEN이고 BL-002/REL-002가 미생성된 상태에서 Stage 5 Gate -> 차단!
        # ----------------------------------------------------------------------
        s5_mid, s5_mid_errs = self.gk.check_stage_gate(5)
        self.assertFalse(s5_mid)
        self.assertTrue(any("Problem Report 'PR-001' has unresolved status 'OPEN'" in e for e in s5_mid_errs))
        self.assertTrue(any("diverges from baseline 'BL-001'" in e for e in s5_mid_errs))

        # ----------------------------------------------------------------------
        # 5) PR-001을 CLOSED로 마감하고, CR-001 동기화 후 BL-002 스냅샷 및 REL-002(v1.0.1) 발행 -> Stage 5 100% PASS!
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

        # BL-002 생성 이후에는 기존 CR-001(v2)도 잠겼으므로 추가 수정 시도 시 다시 차단되는지 확인!
        with self.assertRaises(PermissionError) as ctx4:
            self.mgr.put_item("02_srs.json", dict(srs1_v2, description="BL-002 이후 무단 변경"), "1-A_requirements_author", "Post BL-002 edit")
        self.assertIn("Baseline Lock Violation", str(ctx4.exception))

    # ==========================================================================
    # TOOL-REQ-12: Antigravity 프레임워크 패키징 (.agents/ Rules, Skills, Hooks) 검증
    # ==========================================================================
    def test_tool_req_12_antigravity_agents_packaging_and_hooks(self):
        """
        Step 5 범용 Antigravity 패키징(.agents/rules, .agents/skills, .agents/hooks.json)의
        구조적 무결성 및 PreToolUse/SessionStart 훅의 실제 차단·주입 동작을 검증
        """
        import subprocess

        repo_root = Path(__file__).resolve().parent
        agents_dir = repo_root / ".agents"

        # 1) 필수 Rules 및 AGENTS.md 존재 확인
        self.assertTrue((repo_root / "AGENTS.md").exists())
        self.assertTrue((agents_dir / "rules" / "00_core_governance.md").exists())
        self.assertTrue((agents_dir / "rules" / "01_vmodel_stage_gates.md").exists())

        # 2) 필수 Skills 3종 및 YAML Frontmatter 확인
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

        # 3) hooks.json 구조 확인
        hooks_json_path = agents_dir / "hooks.json"
        self.assertTrue(hooks_json_path.exists())
        hooks_cfg = json.loads(hooks_json_path.read_text(encoding="utf-8"))
        self.assertIn("dhf-store-write-guard", hooks_cfg)
        self.assertIn("samd-session-initializer", hooks_cfg)

        # 4) pre_tool_guard.py 실제 서브프로세스 실행 검증 (store/*.json 직접 수정 차단)
        guard_script = agents_dir / "hooks" / "pre_tool_guard.py"
        self.assertTrue(guard_script.exists())

        # 4-A: store/02_srs.json 직접 edit_file 시도 -> deny 반환 필수
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

        # 4-B: docs/02_SRS_SW요구사항명세서.md 직접 write_file 시도 -> deny 반환 필수
        deny_payload_docs = json.dumps({
            "toolCall": {
                "name": "write_file",
                "args": {
                    "Path": str(repo_root / "projects" / "pathology_slide_qc" / "docs" / "02_SRS_SW요구사항명세서.md")
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

        # 4-C: src/slide_preprocessor.py 정상 소스코드 편집 -> allow 반환 필수
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

        # 5) session_start_banner.py 실제 서브프로세스 실행 검증
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
