#!/usr/bin/env python3
"""
dhf_cli.py - SaMD Design History File (DHF) 관리 엔진 및 CLI

[주요 기능]
1. OS 수준 파일 잠금 (fcntl.flock): 다중 에이전트 환경 동시 쓰기 충돌 원천 차단
2. 단일 소유권(Single Ownership) 강제: SCHEMA_SPEC.md 2장에 정의된 에이전트별 독점 파일 권한 검사
3. Base Envelope 및 특화 스키마 검증: 필수 필드, ID 접두사, traces_to 형식 검사
4. 원자적 버전 관리 & SHA-256 해시 체인 감사 추적 (audit_history.jsonl): 6하원칙 기록 및 변조 방지
5. 중앙 양방향 추적성 장부 (traceability.json): 역인덱싱 및 상위 변경 시 Suspect Link 연쇄 전파
6. 심사관/인간 열람용 규제 합본 보고서 (docs/*.md) 자동 렌더링
"""

import os
import sys
import json
import fcntl
import hashlib
import re
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set


# ==============================================================================
# 1. 파일별 소유권 및 스키마 규격 매핑 (SCHEMA_SPEC.md 준수)
# ==============================================================================

FILE_OWNERSHIP_MAP: Dict[str, Dict[str, Any]] = {
    "00_intake.json": {
        "owners": ["0-0_intake_agent", "SYSTEM_ENGINE"],
        "prefixes": ["INT"],
        "required_fields": [
            "intended_use", "indications_for_use", "target_patient_population",
            "intended_users", "use_environment", "clinical_benefit",
            "device_category", "has_ai_ml", "has_network", "has_gui",
            "has_alarm", "project_mode"
        ]
    },
    "00_literature.json": {
        "owners": ["0-A_literature_researcher", "SYSTEM_ENGINE"],
        "prefixes": ["LIT"],
        "required_fields": [
            "category", "source_citation", "key_findings",
            "benchmark_criteria", "known_hazards_identified"
        ]
    },
    "00_regulatory.json": {
        "owners": ["0-B_regulatory_strategist", "SYSTEM_ENGINE"],
        "prefixes": ["REG"],
        "required_fields": [
            "safety_class", "fda_doc_level", "target_regions",
            "active_profiles", "applicable_standards", "regulatory_mandate"
        ]
    },
    "00_sdp_plan.json": {
        "owners": ["0-C_sdp_planner", "0_orchestrator", "SYSTEM_ENGINE"],
        "prefixes": ["SDP"],
        "required_fields": [
            "project_profile", "plan_category", "language_and_runtime",
            "coding_standards", "risk_acceptability_rule", "min_test_coverage_pct",
            "workflow_steps"
        ]
    },
    "01_urs.json": {
        "owners": ["1-A_requirements_author", "SYSTEM_ENGINE"],
        "prefixes": ["URS"],
        "required_fields": [
            "stakeholder", "acceptance_criteria"
        ]
    },
    "02_srs.json": {
        "owners": ["1-A_requirements_author", "SYSTEM_ENGINE"],
        "prefixes": ["SRS"],
        "required_fields": [
            "req_category", "verification_method", "measurable_criteria"
        ]
    },
    "opt_ai_spec.json": {
        "owners": ["1-E_option_domain_author", "SYSTEM_ENGINE"],
        "prefixes": ["DAT"],
        "required_fields": [
            "dataset_split_policy", "data_quality_criteria", "model_reproducibility",
            "clinical_metrics_target", "pccp_boundary"
        ]
    },
    "opt_simd_alarm.json": {
        "owners": ["1-E_option_domain_author", "SYSTEM_ENGINE"],
        "prefixes": ["HSI", "ALM"],
        "required_fields_by_prefix": {
            "HSI": [
                "hardware_component", "interface_protocol",
                "timing_and_sampling_spec", "hardware_fault_detection"
            ],
            "ALM": [
                "alarm_priority", "trigger_condition", "visual_indicator_spec",
                "auditory_signal_spec", "pause_or_ack_policy"
            ]
        }
    },
    "opt_usability_gui.json": {
        "owners": ["1-E_option_domain_author", "SYSTEM_ENGINE"],
        "prefixes": ["UE"],
        "required_fields": [
            "user_task_scenario", "potential_use_error",
            "ui_risk_control_design", "evaluation_protocol"
        ]
    },
    "03_sad_soup.json": {
        "owners": ["2-A_software_architect", "SYSTEM_ENGINE"],
        "prefixes": ["SAD", "SOUP"],
        "required_fields_by_prefix": {
            "SAD": [
                "module_name", "safety_class", "module_responsibility",
                "public_interfaces", "segregation_strategy"
            ],
            "SOUP": [
                "package_name", "exact_version", "license",
                "functional_performance_req", "hw_memory_requirements",
                "known_anomalies_and_cve", "risk_control_justification"
            ]
        }
    },
    "04_sds.json": {
        "owners": ["2-A_software_architect", "SYSTEM_ENGINE"],
        "prefixes": ["SDS"],
        "required_fields": [
            "target_file_path", "unit_type", "callable_name",
            "callable_signature", "parameters_contract", "return_contract",
            "exception_contract", "algorithm_specification"
        ]
    },
    "05_tc.json": {
        "owners": ["4-A_blackbox_tester", "SYSTEM_ENGINE"],
        "prefixes": ["UT", "IT", "ST", "VT"],
        "required_fields": [
            "test_level", "execution_mode", "is_negative_test",
            "test_file_path", "test_callable_name", "expected_outcome",
            "last_run_status"
        ]
    },
    "06_release.json": {
        "owners": ["5-A_release_author", "SYSTEM_ENGINE"],
        "prefixes": ["REL"],
        "required_fields": [
            "release_version", "baseline_id", "known_remaining_anomalies",
            "overall_residual_risk_acceptable", "release_environment_spec"
        ]
    },
    "rmf_safety.json": {
        "owners": [
            "1-B_safety_risk_analyst", "2-B_dfmea_risk_analyst",
            "3-B_code_safety_analyst", "4-B_residual_risk_evaluator",
            "SYSTEM_ENGINE"
        ],
        "prefixes": ["HAZ-SAF", "RC-SAF"],
        "required_fields_by_prefix": {
            "HAZ-SAF": [
                "stage_identified", "hazard_category", "harm",
                "initial_severity", "initial_probability", "initial_risk_score",
                "control_required", "residual_severity", "residual_probability",
                "residual_risk_score", "residual_acceptable", "new_hazards_introduced",
                "benefit_risk_justification"
            ],
            "RC-SAF": [
                "control_priority", "priority_justification",
                "control_measure", "verification_status"
            ]
        }
    },
    "rmf_security.json": {
        "owners": [
            "1-C_security_risk_analyst", "2-C_threat_security_analyst",
            "3-B_code_safety_analyst", "4-B_residual_risk_evaluator",
            "SYSTEM_ENGINE"
        ],
        "prefixes": ["HAZ-SEC", "RC-SEC"],
        "required_fields_by_prefix": {
            "HAZ-SEC": [
                "stage_identified", "stride_category", "threat_scenario",
                "patient_safety_impact"
            ],
            "RC-SEC": [
                "security_control_type", "control_measure", "safety_tradeoff_check"
            ]
        }
    },
    "audit_findings.json": {
        "owners": [
            "0-D_stage0_auditor", "1-D_stage1_auditor", "2-D_stage2_auditor",
            "3-C_stage3_auditor", "4-D_stage4_auditor", "5-B_final_release_auditor",
            "SYSTEM_ENGINE"
        ],
        "prefixes": ["AUD"],
        "required_fields": [
            "stage", "auditor_role", "verdict", "target_agent",
            "target_item_ids", "finding_details", "remediation_required",
            "resolution_status"
        ]
    },
    "cm_baselines.json": {
        "owners": ["0_orchestrator", "SYSTEM_ENGINE"],
        "prefixes": ["BL"],
        "required_fields": [
            "baseline_id", "stage_name", "snapshot_commit_or_hash",
            "locked_item_versions", "created_at"
        ]
    },
    "pr_cr_log.json": {
        "owners": [
            "6-A_maintenance_change_analyst", "4-C_maintenance_change_analyst",
            "SYSTEM_ENGINE"
        ],
        "prefixes": ["PR", "CR"],
        "required_fields_by_prefix": {
            "PR": [
                "problem_source", "safety_security_impact",
                "investigation_summary", "resolution_status"
            ],
            "CR": [
                "change_reason", "impacted_item_ids",
                "regression_test_ids", "approval_status"
            ]
        }
    }
}

BASE_ENVELOPE_FIELDS = [
    "id", "type", "version", "status", "title",
    "description", "traces_to", "updated_at", "updated_by"
]

# 베이스라인 확정(BL-xxx) 이후 수정 시 반드시 승인된 CR-xxx 통제를 받아야 하는 V-모델 핵심 산출물 파일
BASELINE_LOCKED_FILES: Set[str] = {
    "01_urs.json", "02_srs.json", "03_sad_soup.json", "04_sds.json",
    "05_tc.json", "rmf_safety.json", "rmf_security.json",
    "opt_ai_spec.json", "opt_simd_alarm.json", "opt_usability_gui.json"
}


# ==============================================================================
# 2. 동시성 제어용 파일 잠금 컨텍스트 (프로세스 내 재진입 안전 + 비절단 잠금)
# ==============================================================================

class DHFLock:
    """fcntl.flock 기반의 프로세스 간 원자적 배타적 잠금 관리자 (동일 PID 재진입 데드락 방지 포함)"""
    _active_locks: Dict[Tuple[int, str], List[Any]] = {}

    def __init__(self, lock_file_path: Path):
        self.lock_file_path = lock_file_path
        self._fd = None
        self._key: Optional[Tuple[int, str]] = None

    def __enter__(self):
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        resolved = str(self.lock_file_path.resolve())
        pid = os.getpid()
        self._key = (pid, resolved)

        if self._key in DHFLock._active_locks:
            entry = DHFLock._active_locks[self._key]
            entry[1] += 1
            self._fd = entry[0]
            return self

        # "a+" 모드를 사용하여 LOCK_EX 획득 전 파일 절단(truncate) 경쟁 조건을 원천 차단
        self._fd = open(self.lock_file_path, "a+", encoding="utf-8")
        fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX)
        DHFLock._active_locks[self._key] = [self._fd, 1]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._key and self._key in DHFLock._active_locks:
            entry = DHFLock._active_locks[self._key]
            entry[1] -= 1
            if entry[1] <= 0:
                fd = entry[0]
                del DHFLock._active_locks[self._key]
                try:
                    fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
                    fd.close()
                except Exception:
                    pass


# ==============================================================================
# 3. DHF Core 관리자 클래스
# ==============================================================================

class DHFManager:
    """SaMD DHF 데이터 저장소 총괄 관리 엔진"""

    def __init__(self, workspace_root: Optional[Path] = None):
        if workspace_root is None:
            self.workspace_root = Path.cwd().resolve()
        else:
            self.workspace_root = Path(workspace_root).resolve()

        self.store_dir = self.workspace_root / "store"
        self.docs_dir = self.workspace_root / "docs"
        self.lock_file = self.store_dir / ".dhf.lock"
        self.audit_log_path = self.store_dir / "audit_history.jsonl"
        self.traceability_path = self.store_dir / "traceability.json"

    def init_store(self, force: bool = False):
        """저장소 폴더 및 표준 빈 JSON 파일들 초기화"""
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        with DHFLock(self.lock_file):
            for filename in FILE_OWNERSHIP_MAP.keys():
                filepath = self.store_dir / filename
                if not filepath.exists() or force:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump({"items": []}, f, indent=2, ensure_ascii=False)

            if not self.audit_log_path.exists() or force:
                with open(self.audit_log_path, "w", encoding="utf-8") as f:
                    pass

            if not self.traceability_path.exists() or force:
                empty_trace = {
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "links": {},
                    "coverage_summary": {
                        "total_items": 0,
                        "uncovered_items": [],
                        "broken_links": [],
                        "suspect_links": []
                    }
                }
                with open(self.traceability_path, "w", encoding="utf-8") as f:
                    json.dump(empty_trace, f, indent=2, ensure_ascii=False)

    # --------------------------------------------------------------------------
    # 스키마 및 소유권 유효성 검사
    # --------------------------------------------------------------------------

    def validate_ownership(self, filename: str, actor: str) -> None:
        """에이전트가 해당 파일에 대한 쓰기 권한이 있는지 검증"""
        meta = FILE_OWNERSHIP_MAP.get(filename)
        if not meta:
            raise ValueError(f"Unknown DHF store file: {filename}")
        if actor not in meta["owners"]:
            raise PermissionError(
                f"Ownership Violation: Actor '{actor}' is NOT authorized to modify '{filename}'. "
                f"Authorized owners are: {meta['owners']}"
            )

    def validate_item_schema(self, filename: str, item: Dict[str, Any]) -> None:
        """기본 Envelope 및 특화 필드 유효성 검증"""
        # 1. Base Envelope 필수 필드 확인
        for field in BASE_ENVELOPE_FIELDS:
            if field not in item:
                raise ValueError(f"Schema Violation in '{filename}': Missing base envelope field '{field}' in item {item.get('id')}")

        item_id = item["id"]
        item_type = item["type"]
        meta = FILE_OWNERSHIP_MAP[filename]

        # 2. 접두사 일치 확인
        prefixes = meta["prefixes"]
        matched_prefix = None
        for p in prefixes:
            if item_id.startswith(f"{p}-") and item_type == p:
                matched_prefix = p
                break

        if not matched_prefix:
            raise ValueError(
                f"Prefix/Type Mismatch in '{filename}': Item ID '{item_id}' with type '{item_type}' "
                f"does not match allowed prefixes {prefixes}"
            )

        # 3. traces_to 형식 검증 (dict of str -> int)
        traces_to = item.get("traces_to", {})
        if not isinstance(traces_to, dict):
            raise ValueError(f"Schema Violation in '{filename}': 'traces_to' must be a dictionary in item '{item_id}'")
        for k, v in traces_to.items():
            if not isinstance(k, str) or not isinstance(v, int):
                raise ValueError(
                    f"Schema Violation in '{filename}': 'traces_to' key must be str and value must be int version. "
                    f"Got {k}: {v} in item '{item_id}'"
                )

        # 4. 특화 필수 필드 확인
        if "required_fields" in meta:
            for rf in meta["required_fields"]:
                if rf not in item:
                    raise ValueError(f"Schema Violation in '{filename}': Missing specific field '{rf}' in item '{item_id}'")
        elif "required_fields_by_prefix" in meta:
            reqs = meta["required_fields_by_prefix"].get(matched_prefix, [])
            for rf in reqs:
                if rf not in item:
                    raise ValueError(f"Schema Violation in '{filename}': Missing specific field '{rf}' for prefix '{matched_prefix}' in item '{item_id}'")

    # --------------------------------------------------------------------------
    # 해시 체인 감사 추적 (Audit History)
    # --------------------------------------------------------------------------

    def get_last_audit_record(self) -> Tuple[int, str]:
        """audit_history.jsonl의 마지막 seq와 state_hash 반환"""
        if not self.audit_log_path.exists():
            return 0, "0" * 64

        last_seq = 0
        last_hash = "0" * 64
        with open(self.audit_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        last_seq = rec.get("seq", last_seq)
                        last_hash = rec.get("state_hash", last_hash)
                    except Exception:
                        pass
        return last_seq, last_hash

    def append_audit_log(
        self,
        actor: str,
        action: str,
        target_id: str,
        target_file: str,
        version: int,
        reason: str,
        snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """새 감사 로그를 계산하여 해시 체인에 추가"""
        last_seq, last_hash = self.get_last_audit_record()
        new_seq = last_seq + 1
        now_ts = datetime.now(timezone.utc).isoformat()

        # 해시 산출을 위한 canonical 페이로드
        hash_payload = (
            f"{new_seq}:{now_ts}:{actor}:{action}:{target_id}:{version}:"
            f"{reason}:{last_hash}:{json.dumps(snapshot, sort_keys=True, ensure_ascii=False)}"
        )
        state_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

        record = {
            "seq": new_seq,
            "timestamp": now_ts,
            "actor": actor,
            "action": action,
            "target_id": target_id,
            "target_file": target_file,
            "version": version,
            "reason": reason,
            "snapshot": snapshot,
            "prev_hash": last_hash,
            "state_hash": state_hash
        }

        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record

    def verify_audit_history(self) -> Tuple[bool, List[str]]:
        """
        감사 이력의 해시 체인 무결성, 순차성 및 실제 store/*.json 현재 상태와의
        1:1 교차 대조(Cross-check) 전수 검증 (21 CFR Part 11 / FDA CSA 준수)
        """
        errors = []
        with DHFLock(self.lock_file):
            expected_prev = "0" * 64
            expected_seq = 1
            latest_snapshots: Dict[Tuple[str, str], Dict[str, Any]] = {}
            latest_seqs: Dict[Tuple[str, str], int] = {}

            if self.audit_log_path.exists():
                with open(self.audit_log_path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except Exception as e:
                            errors.append(f"Line {line_no}: Invalid JSON ({e})")
                            continue

                        seq = rec.get("seq")
                        prev_hash = rec.get("prev_hash")
                        state_hash = rec.get("state_hash")
                        t_file = rec.get("target_file")
                        t_id = rec.get("target_id")
                        action = rec.get("action")
                        snapshot = rec.get("snapshot")

                        if seq != expected_seq:
                            errors.append(f"Line {line_no}: Sequence mismatch. Expected {expected_seq}, got {seq}")

                        if prev_hash != expected_prev:
                            errors.append(f"Line {line_no}: Prev hash mismatch. Expected {expected_prev}, got {prev_hash}")

                        # 재계산 검증
                        hash_payload = (
                            f"{seq}:{rec.get('timestamp')}:{rec.get('actor')}:{action}:"
                            f"{t_id}:{rec.get('version')}:{rec.get('reason')}:"
                            f"{prev_hash}:{json.dumps(snapshot, sort_keys=True, ensure_ascii=False)}"
                        )
                        computed_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()
                        if computed_hash != state_hash:
                            errors.append(f"Line {line_no}: Tampering detected! Computed hash {computed_hash} != stored {state_hash}")

                        if t_file and t_id:
                            if action == "DELETE":
                                latest_snapshots.pop((t_file, t_id), None)
                                latest_seqs.pop((t_file, t_id), None)
                            elif isinstance(snapshot, dict):
                                latest_snapshots[(t_file, t_id)] = snapshot
                                latest_seqs[(t_file, t_id)] = seq

                        expected_prev = state_hash
                        if isinstance(seq, int):
                            expected_seq = seq + 1

            # store/*.json의 실제 현재 상태와 audit_history.jsonl 최신 스냅샷 1:1 교차 대조
            store_seen_keys: Set[Tuple[str, str]] = set()
            for filename in FILE_OWNERSHIP_MAP.keys():
                filepath = self.store_dir / filename
                if not filepath.exists():
                    continue
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    items = data.get("items")
                    if not isinstance(items, list):
                        errors.append(f"Direct Tampering Detected in '{filename}': Missing or invalid 'items' list")
                        continue
                except Exception as e:
                    errors.append(f"Direct Tampering Detected in '{filename}': Corrupted JSON ({e})")
                    continue

                for item in items:
                    if not isinstance(item, dict) or "id" not in item:
                        errors.append(f"Direct Tampering Detected in '{filename}': Malformed item object without 'id'")
                        continue
                    iid = item["id"]
                    key = (filename, iid)
                    store_seen_keys.add(key)

                    if key not in latest_snapshots:
                        errors.append(
                            f"Direct Tampering Detected in '{filename}': Item '{iid}' exists in store "
                            f"but has no audit trail record in audit_history.jsonl"
                        )
                    else:
                        store_canon = json.dumps(item, sort_keys=True, ensure_ascii=False)
                        audit_canon = json.dumps(latest_snapshots[key], sort_keys=True, ensure_ascii=False)
                        if store_canon != audit_canon:
                            errors.append(
                                f"Direct Tampering Detected in '{filename}': Item '{iid}' current state in store "
                                f"diverges from latest audit_history.jsonl snapshot (seq={latest_seqs[key]})"
                            )

            # 감사 로그에는 존재하나 store/*.json에서 무단 삭제된 항목 적발
            for (t_file, t_id), seq_no in latest_seqs.items():
                if (t_file, t_id) not in store_seen_keys:
                    errors.append(
                        f"Direct Tampering Detected in '{t_file}': Item '{t_id}' (last seq={seq_no}) "
                        f"was unauthorizedly deleted from store"
                    )

        return len(errors) == 0, errors

    # --------------------------------------------------------------------------
    # 베이스라인 잠금 및 유지보수 변경통제 검증 (IEC 62304 Clause 6, 8, 9)
    # --------------------------------------------------------------------------

    def _validate_baseline_lock(
        self,
        filename: str,
        target_id: str,
        actor: str,
        reason: str
    ) -> None:
        """
        cm_baselines.json에 확정된 베이스라인(BL-xxx)이 존재할 경우,
        승인된 변경요청서(CR-xxx) 및 문제보고서(PR-xxx) 없이는 잠긴 산출물 수정을 원천 차단함.
        """
        if filename not in BASELINE_LOCKED_FILES or actor == "SYSTEM_ENGINE":
            return

        bl_path = self.store_dir / "cm_baselines.json"
        if not bl_path.exists():
            return

        try:
            with open(bl_path, "r", encoding="utf-8") as f:
                baselines = json.load(f).get("items", [])
        except Exception:
            baselines = []

        if not baselines:
            return

        latest_bl = baselines[-1]
        bl_id = latest_bl.get("id", "BL-UNKNOWN")
        locked_vers: Dict[str, int] = latest_bl.get("locked_item_versions", {})

        pr_cr_path = self.store_dir / "pr_cr_log.json"
        pr_cr_items: List[Dict[str, Any]] = []
        if pr_cr_path.exists():
            try:
                with open(pr_cr_path, "r", encoding="utf-8") as f:
                    pr_cr_items = json.load(f).get("items", [])
            except Exception:
                pr_cr_items = []

        pr_map = {it["id"]: it for it in pr_cr_items if it.get("type") == "PR"}
        active_approved_crs = []
        for it in pr_cr_items:
            if it.get("type") == "CR" and it.get("approval_status") == "APPROVED":
                cr_id = it.get("id", "")
                cr_ver = it.get("version", 1)
                # 최신 베이스라인 이후에 신규 발행되었거나 갱신된 CR만 유효한 잠금 해제 권한을 가짐
                if cr_ver > locked_vers.get(cr_id, 0):
                    traces = it.get("traces_to", {})
                    if any(up_id in pr_map for up_id in traces.keys()):
                        active_approved_crs.append(it)

        if not active_approved_crs:
            raise PermissionError(
                f"Baseline Lock Violation: Store is locked by baseline '{bl_id}'. "
                f"Modifying '{filename}' ('{target_id}') requires an active APPROVED Change Request (CR-xxx) "
                f"linked to a Problem Report (PR-xxx) in pr_cr_log.json."
            )

        if target_id in locked_vers:
            authorized_ids: Set[str] = set()
            for cr in active_approved_crs:
                authorized_ids.update(cr.get("impacted_item_ids", []))
                authorized_ids.update(cr.get("regression_test_ids", []))

            # 상위 항목 변경으로 인해 Suspect Link로 전파된 하위 항목도 연쇄 갱신 허용
            if self.traceability_path.exists():
                try:
                    with open(self.traceability_path, "r", encoding="utf-8") as f:
                        trace_doc = json.load(f)
                    suspects = trace_doc.get("coverage_summary", {}).get("suspect_links", [])
                    authorized_ids.update(suspects)
                except Exception:
                    pass

            is_auto_test_run = (
                filename == "05_tc.json" and reason.startswith("Automated test execution result update:")
            )
            if target_id not in authorized_ids and not is_auto_test_run:
                raise PermissionError(
                    f"Baseline Lock Violation: Item '{target_id}' in '{filename}' is locked by baseline '{bl_id}' "
                    f"and is not authorized by any active APPROVED CR (impacted_item_ids / regression_test_ids) "
                    f"or suspect link propagation."
                )

    def create_baseline(
        self,
        baseline_id: str,
        stage_name: str,
        actor: str = "0_orchestrator",
        reason: str = "Establish configuration baseline snapshot",
        traces_to: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        현재 store/ 내 모든 활성 항목들의 버전을 스냅샷으로 캡처하여 cm_baselines.json에 등록함 (IEC 62304 Clause 8.1)
        """
        with DHFLock(self.lock_file):
            locked_item_versions: Dict[str, int] = {}
            for fn in FILE_OWNERSHIP_MAP.keys():
                if fn == "cm_baselines.json":
                    continue
                fp = self.store_dir / fn
                if fp.exists():
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            items = json.load(f).get("items", [])
                        for it in items:
                            if "id" in it and "version" in it:
                                locked_item_versions[it["id"]] = it["version"]
                    except Exception:
                        pass

            _, last_hash = self.get_last_audit_record()
            snapshot_payload = f"{last_hash}:{json.dumps(locked_item_versions, sort_keys=True, ensure_ascii=False)}"
            snapshot_hash = hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()

            bl_item = {
                "id": baseline_id,
                "type": "BL",
                "version": 1,
                "status": "approved",
                "title": f"{stage_name} 형상관리 베이스라인 ({baseline_id})",
                "description": f"{stage_name} 시점의 전 DHF 항목 버전 잠금 및 해시 스냅샷",
                "traces_to": traces_to or {},
                "baseline_id": baseline_id,
                "stage_name": stage_name,
                "snapshot_commit_or_hash": snapshot_hash,
                "locked_item_versions": locked_item_versions,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            return self.put_item(
                filename="cm_baselines.json",
                item=bl_item,
                actor=actor,
                reason=reason
            )

    # --------------------------------------------------------------------------
    # 항목 등록 / 수정 (Upsert & Versioning)
    # --------------------------------------------------------------------------

    def put_item(
        self,
        filename: str,
        item: Dict[str, Any],
        actor: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        항목을 store/filename에 등록 또는 수정.
        - 단일 소유권 검사
        - 베이스라인 잠금 및 PR/CR 변경통제 검사
        - 스키마 검사
        - 기존 항목 존재 시 버전 자동 증가 (v+1)
        - audit_history.jsonl에 해시 체인 기록
        - traceability.json 및 Suspect Link 자동 갱신
        """
        with DHFLock(self.lock_file):
            self.validate_ownership(filename, actor)

            filepath = self.store_dir / filename
            if not filepath.exists():
                self.init_store()

            target_id = item.get("id", "")
            self._validate_baseline_lock(filename, target_id, actor, reason)

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            items: List[Dict[str, Any]] = data.get("items", [])
            target_id = item["id"]

            existing_idx = None
            old_item = None
            for idx, existing in enumerate(items):
                if existing.get("id") == target_id:
                    existing_idx = idx
                    old_item = existing
                    break

            now_iso = datetime.now(timezone.utc).isoformat()
            item["updated_at"] = now_iso
            item["updated_by"] = actor

            if existing_idx is not None:
                # Update: 버전 자동 증가
                old_ver = old_item.get("version", 1)
                new_ver = old_ver + 1
                item["version"] = new_ver
                action = "UPDATE"
                self.validate_item_schema(filename, item)
                items[existing_idx] = item
            else:
                # Create: 버전 1 강제
                if "version" not in item or item["version"] <= 0:
                    item["version"] = 1
                action = "CREATE"
                self.validate_item_schema(filename, item)
                items.append(item)

            # 저장
            data["items"] = items
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # 감사 로그 기록
            self.append_audit_log(
                actor=actor,
                action=action,
                target_id=target_id,
                target_file=filename,
                version=item["version"],
                reason=reason,
                snapshot=item
            )

            # 양방향 추적성 및 Suspect Link 갱신
            self.sync_traceability()

            return item

    def get_item(self, target_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """ID로 store 전체를 검색하여 (filename, item) 반환"""
        with DHFLock(self.lock_file):
            for filename in FILE_OWNERSHIP_MAP.keys():
                filepath = self.store_dir / filename
                if filepath.exists():
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        for item in data.get("items", []):
                            if item.get("id") == target_id:
                                return filename, item
                    except Exception:
                        pass
        return None

    # --------------------------------------------------------------------------
    # 중앙 양방향 추적성 장부 동기화 및 Suspect Link 계산
    # --------------------------------------------------------------------------

    def sync_traceability(self) -> Dict[str, Any]:
        """
        store/ 내 모든 항목을 스캔하여 양방향 링크(upward/downward)를 구축하고,
        상위 항목의 버전이 변경되었으나 하위 traces_to가 미반영된 경우
        is_suspect=True를 연쇄적으로 전파함.
        """
        all_items: Dict[str, Dict[str, Any]] = {}
        file_map: Dict[str, str] = {}

        # 1. 모든 항목 수집 (이전 릴리즈/베이스라인 아카이브 항목 식별 포함)
        historical_snapshot_ids: Set[str] = set()
        for filename in FILE_OWNERSHIP_MAP.keys():
            filepath = self.store_dir / filename
            if not filepath.exists():
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items_list = data.get("items", [])
                if filename in ("06_release.json", "cm_baselines.json") and len(items_list) > 1:
                    for hist_it in items_list[:-1]:
                        if "id" in hist_it:
                            historical_snapshot_ids.add(hist_it["id"])
                for it in items_list:
                    iid = it.get("id")
                    if iid:
                        all_items[iid] = it
                        file_map[iid] = filename
            except Exception:
                pass

        # 2. 양방향 인덱싱 초기화
        links: Dict[str, Dict[str, Any]] = {}
        for iid, it in all_items.items():
            links[iid] = {
                "item_type": it.get("type"),
                "current_version": it.get("version", 1),
                "store_file": file_map[iid],
                "upward": dict(it.get("traces_to", {})),
                "downward": {},
                "is_suspect": False,
                "suspect_reasons": []
            }

        # 3. downward 역인덱싱 계산
        broken_links: List[Dict[str, Any]] = []
        for iid, node in links.items():
            for up_id, req_ver in node["upward"].items():
                if up_id in links:
                    links[up_id]["downward"][iid] = req_ver
                else:
                    broken_links.append({
                        "item_id": iid,
                        "broken_upstream_id": up_id,
                        "specified_version": req_ver
                    })

        # 4. 직접 Suspect Link 계산 (1차 감지 - 과거 릴리즈/베이스라인 스냅샷 제외)
        for iid, node in links.items():
            if iid in historical_snapshot_ids:
                continue
            for up_id, req_ver in node["upward"].items():
                if up_id in links:
                    actual_up_ver = links[up_id]["current_version"]
                    if req_ver != actual_up_ver:
                        node["is_suspect"] = True
                        reason = f"Upstream '{up_id}' version mismatch: pointing to v{req_ver}, but current is v{actual_up_ver}"
                        if reason not in node["suspect_reasons"]:
                            node["suspect_reasons"].append(reason)

        # 5. Suspect Link 연쇄 전파 (Downward Ripple Effect)
        # 만약 상위 항목이 suspect이면, 그 하위 항목들도 연쇄적으로 영향을 받음
        changed = True
        while changed:
            changed = False
            for iid, node in links.items():
                if node["is_suspect"]:
                    for down_id in node["downward"].keys():
                        if down_id in links and down_id not in historical_snapshot_ids:
                            down_node = links[down_id]
                            reason = f"Indirect ripple: Upstream '{iid}' is marked SUSPECT"
                            if not down_node["is_suspect"] or reason not in down_node["suspect_reasons"]:
                                down_node["is_suspect"] = True
                                if reason not in down_node["suspect_reasons"]:
                                    down_node["suspect_reasons"].append(reason)
                                changed = True

        # 6. 고아(Uncovered) 항목 판별
        # INT, SDP, LIT, REG 등 최상위/프로파일 항목을 제외하고,
        # 상위 upward가 비어있거나 downward가 비어있는 항목 식별
        uncovered_items: List[str] = []
        for iid, node in links.items():
            itype = node["item_type"]
            # 중간 단계 항목(URS, SRS, SAD, SDS, RC, HAZ) 중 연결고리가 아예 없는 경우
            if itype in ["SRS", "SAD", "SDS", "UT", "IT", "ST", "VT", "RC-SAF", "RC-SEC"]:
                if len(node["upward"]) == 0:
                    uncovered_items.append(f"{iid} (No upstream traces_to)")
            if itype in ["URS", "SRS", "SAD", "SDS"]:
                if len(node["downward"]) == 0:
                    uncovered_items.append(f"{iid} (No downstream implementation/verification)")

        suspect_items = [iid for iid, n in links.items() if n["is_suspect"]]

        trace_doc = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "links": links,
            "coverage_summary": {
                "total_items": len(links),
                "uncovered_items": uncovered_items,
                "broken_links": broken_links,
                "suspect_links": suspect_items
            }
        }

        with open(self.traceability_path, "w", encoding="utf-8") as f:
            json.dump(trace_doc, f, indent=2, ensure_ascii=False)

        return trace_doc

    # --------------------------------------------------------------------------
    # 규제 합본 보고서 (docs/*.md) 자동 렌더링
    # --------------------------------------------------------------------------

    def render_markdown_docs(self) -> List[str]:
        """store/*.json 및 traceability.json으로부터 심사관용 Markdown 문서 일괄 생성"""
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        rendered_files = []

        def load_store(fn: str) -> List[Dict[str, Any]]:
            fp = self.store_dir / fn
            if fp.exists():
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        return json.load(f).get("items", [])
                except Exception:
                    return []
            return []

        # 1. 00_SDP_프로젝트수행계획서.md
        intake_items = load_store("00_intake.json")
        lit_items = load_store("00_literature.json")
        reg_items = load_store("00_regulatory.json")
        sdp_items = load_store("00_sdp_plan.json")

        sdp_md = ["# 🏥 프로젝트 수행계획서 (Software Development Plan)\n"]
        sdp_md.append("## 1. 개발 의뢰 및 의도된 사용 (Intake & Intended Use)")
        for it in intake_items:
            sdp_md.append(f"### [{it['id']}] {it['title']} (v{it['version']})")
            sdp_md.append(f"- **의도된 사용**: {it.get('intended_use')}")
            sdp_md.append(f"- **적응증**: {it.get('indications_for_use')}")
            sdp_md.append(f"- **환자군/사용자**: {it.get('target_patient_population')} / {it.get('intended_users')}")
            sdp_md.append(f"- **기기 분류**: {it.get('device_category')} (AI: {it.get('has_ai_ml')}, Network: {it.get('has_network')})")
            sdp_md.append(f"- **임상 유익성**: {it.get('clinical_benefit')}\n")

        sdp_md.append("## 2. 규제 전략 및 안전 등급 분류 (Regulatory)")
        for it in reg_items:
            sdp_md.append(f"- **안전등급**: {it.get('safety_class')} (FDA: {it.get('fda_doc_level')})")
            sdp_md.append(f"- **타겟 국가**: {', '.join(it.get('target_regions', []))}")
            sdp_md.append(f"- **적용 표준**: {', '.join(it.get('applicable_standards', []))}\n")

        sdp_md.append("## 3. SW 개발 계획 및 검증 기준 (SDP Plan)")
        for it in sdp_items:
            sdp_md.append(f"### [{it['id']}] {it['title']}")
            sdp_md.append(f"- **카테고리**: {it.get('plan_category')}")
            sdp_md.append(f"- **개발 언어/환경**: {it.get('language_and_runtime')}")
            sdp_md.append(f"- **최소 테스트 커버리지**: {it.get('min_test_coverage_pct')}%")
            sdp_md.append(f"- **내용**: {it.get('description')}\n")

        fp_sdp = self.docs_dir / "00_SDP_프로젝트수행계획서.md"
        with open(fp_sdp, "w", encoding="utf-8") as f:
            f.write("\n".join(sdp_md))
        rendered_files.append(str(fp_sdp))

        # 2. 01_URS_사용자요구사항명세서.md
        urs_items = load_store("01_urs.json")
        urs_md = ["# 📋 사용자 요구사항 명세서 (User Requirement Specification)\n"]
        urs_md.append("| ID | 제목 | 이해관계자 | 인수 기준 (Acceptance Criteria) | 버전 | 상위 연결 |")
        urs_md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for it in urs_items:
            up = ", ".join([f"{k}@v{v}" for k, v in it.get("traces_to", {}).items()])
            urs_md.append(f"| {it['id']} | {it['title']} | {it.get('stakeholder')} | {it.get('acceptance_criteria')} | v{it['version']} | {up} |")
        fp_urs = self.docs_dir / "01_URS_사용자요구사항명세서.md"
        with open(fp_urs, "w", encoding="utf-8") as f:
            f.write("\n".join(urs_md))
        rendered_files.append(str(fp_urs))

        # 3. 02_SRS_SW요구사항명세서.md
        srs_items = load_store("02_srs.json")
        srs_md = ["# 📝 SW 요구사항 명세서 (Software Requirements Specification - IEC 62304 5.2)\n"]
        srs_md.append("| ID | 구분 | 제목 | 정량적 판정 기준 (Measurable Criteria) | 검증 방법 | 상위 연결 (URS/RC) |")
        srs_md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for it in srs_items:
            up = ", ".join([f"{k}@v{v}" for k, v in it.get("traces_to", {}).items()])
            srs_md.append(f"| {it['id']} | {it.get('req_category')} | {it['title']} | {it.get('measurable_criteria')} | {it.get('verification_method')} | {up} |")
        fp_srs = self.docs_dir / "02_SRS_SW요구사항명세서.md"
        with open(fp_srs, "w", encoding="utf-8") as f:
            f.write("\n".join(srs_md))
        rendered_files.append(str(fp_srs))

        # 4. 03_RMF_통합위험및보안관리보고서.md
        saf_items = load_store("rmf_safety.json")
        sec_items = load_store("rmf_security.json")
        rmf_md = ["# 🛡️ 통합 위험 및 사이버보안 관리 보고서 (ISO 14971 & IEC 81001-5-1)\n"]
        rmf_md.append("## 1. 안전 위험 관리 (Safety Hazard & Risk Control)")
        rmf_md.append("| ID | 유형 | 위해/통제 내용 | 초기위험 (S/P/R) | 잔여위험 (S/P/R) | 허용 여부 | 상위/하위 연결 |")
        rmf_md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for it in saf_items:
            up = ", ".join([f"{k}@v{v}" for k, v in it.get("traces_to", {}).items()])
            if it["type"] == "HAZ-SAF":
                init_r = f"{it.get('initial_severity')}/{it.get('initial_probability')}/{it.get('initial_risk_score')}"
                res_r = f"{it.get('residual_severity')}/{it.get('residual_probability')}/{it.get('residual_risk_score')}"
                rmf_md.append(f"| {it['id']} | HAZARD | {it.get('harm')} | {init_r} | {res_r} | {it.get('residual_acceptable')} | {up} |")
            else:
                rmf_md.append(f"| {it['id']} | CONTROL ({it.get('control_priority')}) | {it.get('control_measure')} | - | - | {it.get('verification_status')} | {up} |")

        rmf_md.append("\n## 2. 사이버보안 위협 모델링 및 통제 (Cybersecurity)")
        rmf_md.append("| ID | STRIDE / 유형 | 위협 시나리오 / 통제 대책 | 환자 안전 영향 | 안전 상충 검토 (Safety Trade-off) |")
        rmf_md.append("| :--- | :--- | :--- | :--- | :--- |")
        for it in sec_items:
            if it["type"] == "HAZ-SEC":
                rmf_md.append(f"| {it['id']} | {it.get('stride_category')} | {it.get('threat_scenario')} | {it.get('patient_safety_impact')} | - |")
            else:
                rmf_md.append(f"| {it['id']} | CONTROL ({it.get('security_control_type')}) | {it.get('control_measure')} | - | {it.get('safety_tradeoff_check')} |")

        fp_rmf = self.docs_dir / "03_RMF_통합위험및보안관리보고서.md"
        with open(fp_rmf, "w", encoding="utf-8") as f:
            f.write("\n".join(rmf_md))
        rendered_files.append(str(fp_rmf))

        # 5. 04_SAD_SDS_설계명세서.md
        sad_items = load_store("03_sad_soup.json")
        sds_items = load_store("04_sds.json")
        arch_md = ["# 🏗️ SW 아키텍처 및 상세설계 명세서 (IEC 62304 5.3 & 5.4)\n"]
        arch_md.append("## 1. 아키텍처 모듈 및 SOUP 목록")
        for it in sad_items:
            if it["type"] == "SAD":
                arch_md.append(f"### [모듈] {it['id']}: {it.get('module_name')} (Class: {it.get('safety_class')})")
                arch_md.append(f"- **책임**: {it.get('module_responsibility')}")
                arch_md.append(f"- **격리 전략**: {it.get('segregation_strategy')}\n")
            else:
                arch_md.append(f"### [SOUP] {it['id']}: {it.get('package_name')} ({it.get('exact_version')})")
                arch_md.append(f"- **라이선스**: {it.get('license')}")
                arch_md.append(f"- **위험 통제 정당화**: {it.get('risk_control_justification')}\n")

        arch_md.append("## 2. 상세 설계 및 함수 시그니처 계약 (SDS)")
        for it in sds_items:
            arch_md.append(f"### [{it['id']}] {it.get('callable_name')} ({it.get('target_file_path')})")
            arch_md.append(f"- **시그니처**: `{it.get('callable_signature')}`")
            arch_md.append(f"- **파라미터 계약**: `{json.dumps(it.get('parameters_contract', []), ensure_ascii=False)}`")
            arch_md.append(f"- **예외 계약**: `{json.dumps(it.get('exception_contract', []), ensure_ascii=False)}`")
            arch_md.append(f"- **알고리즘 명세**: {it.get('algorithm_specification')}\n")

        fp_arch = self.docs_dir / "04_SAD_SDS_설계명세서.md"
        with open(fp_arch, "w", encoding="utf-8") as f:
            f.write("\n".join(arch_md))
        rendered_files.append(str(fp_arch))

        # 6. 05_VNV_검증결과보고서.md
        tc_items = load_store("05_tc.json")
        rel_items = load_store("06_release.json")
        bl_items = load_store("cm_baselines.json")
        pr_cr_items = load_store("pr_cr_log.json")

        vnv_md = ["# 🧪 SW 검증 결과 및 릴리즈/유지보수 보고서 (V&V, Release & Maintenance - IEC 62304 5.5~5.8, 6, 8, 9)\n"]
        vnv_md.append("## 1. V-모델 4계층 시험 결과 (UT / IT / ST / VT)")
        vnv_md.append("| ID | 계층 (Level) | 테스트 명칭 | 대상 파일 | 음성/고장유도 | 실행 상태 | 상위 검증 대상 |")
        vnv_md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for it in tc_items:
            up = ", ".join([f"{k}@v{v}" for k, v in it.get("traces_to", {}).items()])
            vnv_md.append(f"| {it['id']} | {it.get('test_level')} | {it['title']} | {it.get('test_file_path')} | {it.get('is_negative_test')} | **{it.get('last_run_status')}** | {up} |")

        vnv_md.append("\n## 2. 형상관리 베이스라인 이력 (Configuration Baselines - Clause 8.1)")
        vnv_md.append("| Baseline ID | 단계/버전명 | 스냅샷 해시 | 잠금 항목 수 | 생성 시각 |")
        vnv_md.append("| :--- | :--- | :--- | :--- | :--- |")
        for bl in bl_items:
            locked_cnt = len(bl.get("locked_item_versions", {}))
            vnv_md.append(f"| {bl['id']} | {bl.get('stage_name')} | `{str(bl.get('snapshot_commit_or_hash'))[:16]}...` | {locked_cnt}개 | {bl.get('created_at')} |")

        vnv_md.append("\n## 3. 문제해결 및 변경통제 이력 (PR / CR Log - Clause 6, 8.2, 9)")
        vnv_md.append("| ID | 유형 | 제목 | 영향 항목 / 원인 | 회귀시험 / 상태 | 상위 연결 |")
        vnv_md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for pc in pr_cr_items:
            up = ", ".join([f"{k}@v{v}" for k, v in pc.get("traces_to", {}).items()]) or "-"
            if pc.get("type") == "PR":
                vnv_md.append(f"| {pc['id']} | PR | {pc['title']} | {pc.get('problem_source')} ({pc.get('safety_security_impact')}) | **{pc.get('resolution_status')}** | {up} |")
            else:
                imp = ", ".join(pc.get("impacted_item_ids", []))
                reg = ", ".join(pc.get("regression_test_ids", []))
                vnv_md.append(f"| {pc['id']} | CR | {pc['title']} | 영향: {imp} | 회귀: {reg} (**{pc.get('approval_status')}**) | {up} |")

        vnv_md.append("\n## 4. 공식 SW 릴리즈 이력 (Software Releases - Clause 5.8)")
        vnv_md.append("| ID | 릴리즈 버전 | 기준선 (Baseline) | 잔여위험 허용 | 잔여 결함 수 |")
        vnv_md.append("| :--- | :--- | :--- | :--- | :--- |")
        for rel in rel_items:
            anom_cnt = len(rel.get("known_remaining_anomalies", []))
            vnv_md.append(f"| {rel['id']} | **v{rel.get('release_version')}** | {rel.get('baseline_id')} | {rel.get('overall_residual_risk_acceptable')} | {anom_cnt}건 |")

        fp_vnv = self.docs_dir / "05_VNV_검증결과보고서.md"
        with open(fp_vnv, "w", encoding="utf-8") as f:
            f.write("\n".join(vnv_md))
        rendered_files.append(str(fp_vnv))

        # 7. VT_수동시험체크리스트.md (인간 친화적 체크리스트)
        vt_items = [it for it in tc_items if it.get("test_level") == "VT" or it.get("execution_mode") == "manual_checklist"]
        vt_md = [
            "# 📋 사용자 밸리데이션(VT) 및 수동 시험 체크리스트\n",
            "> 본 문서는 사람이 직접 화면을 조작하거나 임상 시나리오를 확인할 수 있도록 작성된 간편 체크리스트입니다.\n",
            "> 사용자가 체크하거나 결과를 알려주면 4-A 테스터 에이전트가 정식 DHF로 대행 기록합니다.\n\n",
            "| ID | 시험 항목 | 시험 절차 및 확인 기준 (Protocol) | 판정 (Pass/Fail) | 서명/일자 | 비고 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        if not vt_items:
            vt_md.append("| - | 등록된 수동/VT 시험 항목 없음 | - | - | - | - |")
        else:
            for it in vt_items:
                protocol = it.get("validation_protocol") or it.get("description", "")
                status = it.get("last_run_status", "PENDING")
                checked = "[x] PASS" if status == "PASS" else "[ ] PENDING"
                vt_md.append(f"| {it['id']} | {it['title']} | {protocol} | {checked} | {it.get('human_verified_by', '')} | {it.get('human_observation_notes', '')} |")

        fp_vt = self.docs_dir / "VT_수동시험체크리스트.md"
        with open(fp_vt, "w", encoding="utf-8") as f:
            f.write("\n".join(vt_md))
        rendered_files.append(str(fp_vt))

        # 8. 99_RTM_양방향추적성매트릭스.md
        trace_path = self.traceability_path
        rtm_md = ["# 🔗 양방향 추적성 매트릭스 (Requirements Traceability Matrix - RTM)\n"]
        if trace_path.exists():
            with open(trace_path, "r", encoding="utf-8") as f:
                trace_data = json.load(f)
            links = trace_data.get("links", {})
            cov = trace_data.get("coverage_summary", {})

            rtm_md.append("## 1. 커버리지 요약")
            rtm_md.append(f"- **총 관리 항목 수**: {cov.get('total_items', 0)}개")
            rtm_md.append(f"- **고아(Uncovered) 항목**: {len(cov.get('uncovered_items', []))}개")
            rtm_md.append(f"- **깨진 연결(Broken Links)**: {len(cov.get('broken_links', []))}개")
            rtm_md.append(f"- **재검토 필요(Suspect Links)**: {len(cov.get('suspect_links', []))}개\n")

            rtm_md.append("## 2. 항목별 상·하위 양방향 연결 현황")
            rtm_md.append("| 항목 ID | 유형 | 버전 | 상위 연결 (Upward) | 하위 연결 (Downward) | Suspect 상태 | 사유 |")
            rtm_md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for iid, n in sorted(links.items()):
                up_s = "<br>".join([f"{k}@v{v}" for k, v in n.get("upward", {}).items()]) or "-"
                down_s = "<br>".join([f"{k}@v{v}" for k, v in n.get("downward", {}).items()]) or "-"
                sus_s = "⚠️ **SUSPECT**" if n.get("is_suspect") else "✅ 정상"
                reasons = "<br>".join(n.get("suspect_reasons", [])) or "-"
                rtm_md.append(f"| {iid} | {n.get('item_type')} | v{n.get('current_version')} | {up_s} | {down_s} | {sus_s} | {reasons} |")

        fp_rtm = self.docs_dir / "99_RTM_양방향추적성매트릭스.md"
        with open(fp_rtm, "w", encoding="utf-8") as f:
            f.write("\n".join(rtm_md))
        rendered_files.append(str(fp_rtm))

        return rendered_files


# ==============================================================================
# 4. CLI 인터페이스
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="SaMD DHF CLI Management Tool")
    parser.add_argument(
        "--project-dir", "-p",
        default=None,
        help="Target project directory (default: current working directory)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize DHF store and docs structure")
    p_init.add_argument("--force", action="store_true", help="Force reinitialize")

    # put
    p_put = subparsers.add_parser("put", help="Insert or update an item in DHF store")
    p_put.add_argument("--file", required=True, help="Target store filename (e.g. 02_srs.json)")
    p_put.add_argument("--actor", required=True, help="Agent role identifier")
    p_put.add_argument("--reason", required=True, help="Reason for change")
    p_put.add_argument("--item-json", required=True, help="JSON string or path to JSON file of item")

    # get
    p_get = subparsers.add_parser("get", help="Retrieve an item by ID")
    p_get.add_argument("--id", required=True, help="Item ID (e.g. SRS-001)")

    # sync-trace
    subparsers.add_parser("sync-trace", help="Synchronize traceability.json and suspect links")

    # verify-history
    subparsers.add_parser("verify-history", help="Verify hash chain integrity of audit_history.jsonl")

    # render-docs
    subparsers.add_parser("render-docs", help="Render Markdown reports into docs/")

    # create-baseline
    p_bl = subparsers.add_parser("create-baseline", help="Create a configuration baseline snapshot in cm_baselines.json")
    p_bl.add_argument("--id", required=True, help="Baseline ID (e.g. BL-001)")
    p_bl.add_argument("--stage-name", required=True, help="Stage or release name (e.g. 'Release 1.0.0')")
    p_bl.add_argument("--actor", default="0_orchestrator", help="Actor role (default: 0_orchestrator)")
    p_bl.add_argument("--reason", default="Establish configuration baseline snapshot", help="Reason for baseline")
    p_bl.add_argument("--traces-to", default="{}", help="JSON object of traces_to (optional)")

    args = parser.parse_args()
    proj_path = Path(args.project_dir).resolve() if args.project_dir else None
    mgr = DHFManager(workspace_root=proj_path)

    if args.command == "init":
        mgr.init_store(force=args.force)
        print("DHF store initialized successfully.")

    elif args.command == "put":
        # item_json이 파일 경로인지 확인
        if os.path.exists(args.item_json):
            with open(args.item_json, "r", encoding="utf-8") as f:
                item_obj = json.load(f)
        else:
            item_obj = json.loads(args.item_json)

        res = mgr.put_item(
            filename=args.file,
            item=item_obj,
            actor=args.actor,
            reason=args.reason
        )
        print(f"Item '{res['id']}' (v{res['version']}) successfully saved into '{args.file}'.")

    elif args.command == "get":
        res = mgr.get_item(args.id)
        if res:
            fn, item = res
            print(f"Found in '{fn}':")
            print(json.dumps(item, indent=2, ensure_ascii=False))
        else:
            print(f"Item '{args.id}' not found.")
            sys.exit(1)

    elif args.command == "sync-trace":
        res = mgr.sync_traceability()
        cov = res["coverage_summary"]
        print(f"Traceability synced: {cov['total_items']} items, {len(cov['suspect_links'])} suspect links.")

    elif args.command == "verify-history":
        valid, errors = mgr.verify_audit_history()
        if valid:
            print("Audit history hash chain integrity: 100% VALID.")
        else:
            print("Audit history hash chain integrity: COMPROMISED!")
            for err in errors:
                print(f"  - {err}")
            sys.exit(2)

    elif args.command == "render-docs":
        files = mgr.render_markdown_docs()
        print(f"Successfully rendered {len(files)} docs:")
        for fn in files:
            print(f"  - {fn}")

    elif args.command == "create-baseline":
        traces_obj = json.loads(args.traces_to) if args.traces_to else {}
        bl = mgr.create_baseline(
            baseline_id=args.id,
            stage_name=args.stage_name,
            actor=args.actor,
            reason=args.reason,
            traces_to=traces_obj
        )
        print(f"Baseline '{bl['id']}' created successfully (locked {len(bl['locked_item_versions'])} items).")


if __name__ == "__main__":
    main()
