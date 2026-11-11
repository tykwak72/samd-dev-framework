#!/usr/bin/env python3
"""
dhf_cli.py - SaMD Design History File (DHF) Management Engine & CLI

[Key Capabilities]
1. OS-level file locking (fcntl.flock): Fundamentally prevents multi-agent write collisions
2. Strict Single Ownership enforcement: Inspects exclusive file permissions per agent defined in SCHEMA_SPEC.md Chapter 2
3. Base Envelope & specialized schema validation: Verifies mandatory fields, ID prefixes, and traces_to formats
4. Atomic versioning & SHA-256 hash chain audit trail (audit_history.jsonl): 5W1H logging and tamper-proofing
5. Central bidirectional traceability ledger (traceability.json): Reverse indexing and cascading Suspect Link propagation upon upstream changes
6. Automated rendering of regulatory consolidated reports (docs/*.md) for auditor/human inspection
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
# 1. File ownership and schema specification mapping (Compliance with SCHEMA_SPEC.md)
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

# V-model core deliverable files requiring approved CR-xxx control when modified post-baseline (BL-xxx)
BASELINE_LOCKED_FILES: Set[str] = {
    "01_urs.json", "02_srs.json", "03_sad_soup.json", "04_sds.json",
    "05_tc.json", "rmf_safety.json", "rmf_security.json",
    "opt_ai_spec.json", "opt_simd_alarm.json", "opt_usability_gui.json"
}


# ==============================================================================
# 2. File lock context for concurrency control (reentrant-safe within process + non-truncating lock)
# ==============================================================================

class DHFLock:
    """fcntl.flock-based inter-process atomic exclusive lock manager (including deadlock prevention for reentrant PID)"""
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

        # Use "a+" mode to fundamentally prevent truncation race conditions prior to acquiring LOCK_EX
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
# 3. DHF Core Manager Class
# ==============================================================================

class DHFManager:
    """SaMD DHF Data Repository Core Management Engine"""

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
        """Initialize store directory and standard empty JSON files"""
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
    # Schema and ownership validation
    # --------------------------------------------------------------------------

    def validate_ownership(self, filename: str, actor: str) -> None:
        """Verify whether the agent possesses write permissions for the specified file"""
        meta = FILE_OWNERSHIP_MAP.get(filename)
        if not meta:
            raise ValueError(f"Unknown DHF store file: {filename}")
        if actor not in meta["owners"]:
            raise PermissionError(
                f"Ownership Violation: Actor '{actor}' is NOT authorized to modify '{filename}'. "
                f"Authorized owners are: {meta['owners']}"
            )

    def validate_item_schema(self, filename: str, item: Dict[str, Any]) -> None:
        """Validate base envelope and specialized fields"""
        # 1. Verify Base Envelope mandatory fields
        for field in BASE_ENVELOPE_FIELDS:
            if field not in item:
                raise ValueError(f"Schema Violation in '{filename}': Missing base envelope field '{field}' in item {item.get('id')}")

        item_id = item["id"]
        item_type = item["type"]
        meta = FILE_OWNERSHIP_MAP[filename]

        # 2. Verify prefix match
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

        # 3. Validate traces_to format (dict of str -> int)
        traces_to = item.get("traces_to", {})
        if not isinstance(traces_to, dict):
            raise ValueError(f"Schema Violation in '{filename}': 'traces_to' must be a dictionary in item '{item_id}'")
        for k, v in traces_to.items():
            if not isinstance(k, str) or not isinstance(v, int):
                raise ValueError(
                    f"Schema Violation in '{filename}': 'traces_to' key must be str and value must be int version. "
                    f"Got {k}: {v} in item '{item_id}'"
                )

        # 4. Verify specialized mandatory fields
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
    # Hash chain audit trail (Audit History)
    # --------------------------------------------------------------------------

    def get_last_audit_record(self) -> Tuple[int, str]:
        """Return the last seq and state_hash from audit_history.jsonl"""
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
        """Compute new audit log and append to hash chain"""
        last_seq, last_hash = self.get_last_audit_record()
        new_seq = last_seq + 1
        now_ts = datetime.now(timezone.utc).isoformat()

        # Canonical payload for hash computation
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
        Comprehensive 1:1 cross-check verification of audit history hash chain integrity,
        sequence continuity, and actual store/*.json current state (21 CFR Part 11 / FDA CSA compliance)
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

                        # Re-computation verification
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

            # 1:1 cross-check between store/*.json actual current state and audit_history.jsonl latest snapshot
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

            # Detect items existing in audit log but unauthorizedly deleted from store/*.json
            for (t_file, t_id), seq_no in latest_seqs.items():
                if (t_file, t_id) not in store_seen_keys:
                    errors.append(
                        f"Direct Tampering Detected in '{t_file}': Item '{t_id}' (last seq={seq_no}) "
                        f"was unauthorizedly deleted from store"
                    )

        return len(errors) == 0, errors

    # --------------------------------------------------------------------------
    # Baseline lock and maintenance change control verification (IEC 62304 Clauses 6, 8, 9)
    # --------------------------------------------------------------------------

    def _validate_baseline_lock(
        self,
        filename: str,
        target_id: str,
        actor: str,
        reason: str
    ) -> None:
        """
        When a locked baseline (BL-xxx) exists in cm_baselines.json,
        fundamentally blocks modification of locked deliverables without an approved Change Request (CR-xxx) and Problem Report (PR-xxx).
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
                # Only CRs issued or updated post-latest baseline carry valid unlocking authority
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

            # Allow cascading updates for downstream items propagated as Suspect Links due to upstream changes
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
        Capture snapshots of all active item versions in store/ and register into cm_baselines.json (IEC 62304 Clause 8.1)
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
                "title": f"{stage_name} Configuration Baseline ({baseline_id})",
                "description": f"Version lock and hash snapshot of all DHF items at {stage_name}",
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
    # Item Registration / Modification (Upsert & Versioning)
    # --------------------------------------------------------------------------

    def put_item(
        self,
        filename: str,
        item: Dict[str, Any],
        actor: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Register or modify item in store/filename.
        - Single ownership check
        - Baseline lock and PR/CR change control check
        - Schema validation
        - Automatic version increment (v+1) if existing item present
        - Record hash chain in audit_history.jsonl
        - Automatically synchronize traceability.json and Suspect Links
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
                # Update: Automatic version increment
                old_ver = old_item.get("version", 1)
                new_ver = old_ver + 1
                item["version"] = new_ver
                action = "UPDATE"
                self.validate_item_schema(filename, item)
                items[existing_idx] = item
            else:
                # Create: Enforce version 1
                if "version" not in item or item["version"] <= 0:
                    item["version"] = 1
                action = "CREATE"
                self.validate_item_schema(filename, item)
                items.append(item)

            # Save
            data["items"] = items
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Record audit log
            self.append_audit_log(
                actor=actor,
                action=action,
                target_id=target_id,
                target_file=filename,
                version=item["version"],
                reason=reason,
                snapshot=item
            )

            # Synchronize bidirectional traceability and Suspect Links
            self.sync_traceability()

            return item

    def get_item(self, target_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Search entire store by ID and return (filename, item)"""
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
    # Synchronize central bidirectional traceability ledger and calculate Suspect Links
    # --------------------------------------------------------------------------

    def sync_traceability(self) -> Dict[str, Any]:
        """
        Scan all items in store/ to construct bidirectional links (upward/downward),
        and cascade is_suspect=True when an upstream item version increments
        but downstream traces_to has not been updated.
        """
        all_items: Dict[str, Dict[str, Any]] = {}
        file_map: Dict[str, str] = {}

        # 1. Collect all items (including identification of prior release/baseline archive items)
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

        # 2. Initialize bidirectional indexing
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

        # 3. Compute downward reverse indexing
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

        # 4. Compute direct Suspect Links (primary detection - excluding past release/baseline snapshots)
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

        # 5. Cascade Suspect Links (Downward Ripple Effect)
        # If an upstream item is suspect, its downstream items are also affected transitively
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

        # 6. Identify orphan (uncovered) items
        # Excluding top-level/profile items like INT, SDP, LIT, REG,
        # identify items where upward is empty or downward is empty
        uncovered_items: List[str] = []
        for iid, node in links.items():
            itype = node["item_type"]
            # Middle-tier items (URS, SRS, SAD, SDS, RC, HAZ) with no links whatsoever
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
    # Regulatory consolidated reports (docs/*.md) automatic rendering
    # --------------------------------------------------------------------------

    def render_markdown_docs(self) -> List[str]:
        """Batch generate auditor Markdown documents from store/*.json and traceability.json"""
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

        # 1. 00_SDP_Project_Plan.md
        intake_items = load_store("00_intake.json")
        lit_items = load_store("00_literature.json")
        reg_items = load_store("00_regulatory.json")
        sdp_items = load_store("00_sdp_plan.json")

        sdp_md = ["# 🏥 Software Development Plan (SDP)\n"]
        sdp_md.append("## 1. Intake & Intended Use")
        for it in intake_items:
            sdp_md.append(f"### [{it['id']}] {it['title']} (v{it['version']})")
            sdp_md.append(f"- **Intended Use**: {it.get('intended_use')}")
            sdp_md.append(f"- **Indications for Use**: {it.get('indications_for_use')}")
            sdp_md.append(f"- **Patient Population / Users**: {it.get('target_patient_population')} / {it.get('intended_users')}")
            sdp_md.append(f"- **Device Category**: {it.get('device_category')} (AI: {it.get('has_ai_ml')}, Network: {it.get('has_network')})")
            sdp_md.append(f"- **Clinical Benefit**: {it.get('clinical_benefit')}\n")

        sdp_md.append("## 2. Regulatory Strategy & Safety Classification (Regulatory)")
        for it in reg_items:
            sdp_md.append(f"- **Safety Class**: {it.get('safety_class')} (FDA: {it.get('fda_doc_level')})")
            sdp_md.append(f"- **Target Regions**: {', '.join(it.get('target_regions', []))}")
            sdp_md.append(f"- **Applicable Standards**: {', '.join(it.get('applicable_standards', []))}\n")

        sdp_md.append("## 3. SW Development Plan & Verification Criteria (SDP Plan)")
        for it in sdp_items:
            sdp_md.append(f"### [{it['id']}] {it['title']}")
            sdp_md.append(f"- **Category**: {it.get('plan_category')}")
            sdp_md.append(f"- **Development Language / Environment**: {it.get('language_and_runtime')}")
            sdp_md.append(f"- **Minimum Test Coverage**: {it.get('min_test_coverage_pct')}%")
            sdp_md.append(f"- **Description**: {it.get('description')}\n")

        fp_sdp = self.docs_dir / "00_SDP_Project_Plan.md"
        with open(fp_sdp, "w", encoding="utf-8") as f:
            f.write("\n".join(sdp_md))
        rendered_files.append(str(fp_sdp))

        # 2. 01_URS_User_Requirements_Specification.md
        urs_items = load_store("01_urs.json")
        urs_md = ["# 📋 User Requirements Specification (URS)\n"]
        urs_md.append("| ID | Title | Stakeholder | Acceptance Criteria | Version | Upward Traces |")
        urs_md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for it in urs_items:
            up = ", ".join([f"{k}@v{v}" for k, v in it.get("traces_to", {}).items()])
            urs_md.append(f"| {it['id']} | {it['title']} | {it.get('stakeholder')} | {it.get('acceptance_criteria')} | v{it['version']} | {up} |")
        fp_urs = self.docs_dir / "01_URS_User_Requirements_Specification.md"
        with open(fp_urs, "w", encoding="utf-8") as f:
            f.write("\n".join(urs_md))
        rendered_files.append(str(fp_urs))

        # 3. 02_SRS_Software_Requirements_Specification.md
        srs_items = load_store("02_srs.json")
        srs_md = ["# 📝 Software Requirements Specification (SRS - IEC 62304 5.2)\n"]
        srs_md.append("| ID | Category | Title | Measurable Criteria | Verification Method | Upward Traces (URS/RC) |")
        srs_md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for it in srs_items:
            up = ", ".join([f"{k}@v{v}" for k, v in it.get("traces_to", {}).items()])
            srs_md.append(f"| {it['id']} | {it.get('req_category')} | {it['title']} | {it.get('measurable_criteria')} | {it.get('verification_method')} | {up} |")
        fp_srs = self.docs_dir / "02_SRS_Software_Requirements_Specification.md"
        with open(fp_srs, "w", encoding="utf-8") as f:
            f.write("\n".join(srs_md))
        rendered_files.append(str(fp_srs))

        # 4. 03_RMF_Integrated_Risk_and_Security_Report.md
        saf_items = load_store("rmf_safety.json")
        sec_items = load_store("rmf_security.json")
        rmf_md = ["# 🛡️ Integrated Risk and Cybersecurity Management Report (ISO 14971 & IEC 81001-5-1)\n"]
        rmf_md.append("## 1. Safety Risk Management (Safety Hazard & Risk Control)")
        rmf_md.append("| ID | Type | Hazard / Control Measure | Initial Risk (S/P/R) | Residual Risk (S/P/R) | Acceptable | Upward/Downward Links |")
        rmf_md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for it in saf_items:
            up = ", ".join([f"{k}@v{v}" for k, v in it.get("traces_to", {}).items()])
            if it["type"] == "HAZ-SAF":
                init_r = f"{it.get('initial_severity')}/{it.get('initial_probability')}/{it.get('initial_risk_score')}"
                res_r = f"{it.get('residual_severity')}/{it.get('residual_probability')}/{it.get('residual_risk_score')}"
                rmf_md.append(f"| {it['id']} | HAZARD | {it.get('harm')} | {init_r} | {res_r} | {it.get('residual_acceptable')} | {up} |")
            else:
                rmf_md.append(f"| {it['id']} | CONTROL ({it.get('control_priority')}) | {it.get('control_measure')} | - | - | {it.get('verification_status')} | {up} |")

        rmf_md.append("\n## 2. Cybersecurity Threat Modeling & Controls (Cybersecurity)")
        rmf_md.append("| ID | STRIDE / Type | Threat Scenario / Control Measure | Patient Safety Impact | Safety Trade-off Review |")
        rmf_md.append("| :--- | :--- | :--- | :--- | :--- |")
        for it in sec_items:
            if it["type"] == "HAZ-SEC":
                rmf_md.append(f"| {it['id']} | {it.get('stride_category')} | {it.get('threat_scenario')} | {it.get('patient_safety_impact')} | - |")
            else:
                rmf_md.append(f"| {it['id']} | CONTROL ({it.get('security_control_type')}) | {it.get('control_measure')} | - | {it.get('safety_tradeoff_check')} |")

        fp_rmf = self.docs_dir / "03_RMF_Integrated_Risk_and_Security_Report.md"
        with open(fp_rmf, "w", encoding="utf-8") as f:
            f.write("\n".join(rmf_md))
        rendered_files.append(str(fp_rmf))

        # 5. 04_SAD_SDS_Design_Specification.md
        sad_items = load_store("03_sad_soup.json")
        sds_items = load_store("04_sds.json")
        arch_md = ["# 🏗️ SW Architecture & Detailed Design Specification (IEC 62304 5.3 & 5.4)\n"]
        arch_md.append("## 1. Architecture Modules & SOUP List")
        for it in sad_items:
            if it["type"] == "SAD":
                arch_md.append(f"### [Module] {it['id']}: {it.get('module_name')} (Class: {it.get('safety_class')})")
                arch_md.append(f"- **Responsibility**: {it.get('module_responsibility')}")
                arch_md.append(f"- **Segregation Strategy**: {it.get('segregation_strategy')}\n")
            else:
                arch_md.append(f"### [SOUP] {it['id']}: {it.get('package_name')} ({it.get('exact_version')})")
                arch_md.append(f"- **License**: {it.get('license')}")
                arch_md.append(f"- **Risk Control Justification**: {it.get('risk_control_justification')}\n")

        arch_md.append("## 2. Detailed Design & Function Signature Contracts (SDS)")
        for it in sds_items:
            arch_md.append(f"### [{it['id']}] {it.get('callable_name')} ({it.get('target_file_path')})")
            arch_md.append(f"- **Signature**: `{it.get('callable_signature')}`")
            arch_md.append(f"- **Parameters Contract**: `{json.dumps(it.get('parameters_contract', []), ensure_ascii=False)}`")
            arch_md.append(f"- **Exception Contract**: `{json.dumps(it.get('exception_contract', []), ensure_ascii=False)}`")
            arch_md.append(f"- **Algorithm Specification**: {it.get('algorithm_specification')}\n")

        fp_arch = self.docs_dir / "04_SAD_SDS_Design_Specification.md"
        with open(fp_arch, "w", encoding="utf-8") as f:
            f.write("\n".join(arch_md))
        rendered_files.append(str(fp_arch))

        # 6. 05_VNV_Verification_Report.md
        tc_items = load_store("05_tc.json")
        rel_items = load_store("06_release.json")
        bl_items = load_store("cm_baselines.json")
        pr_cr_items = load_store("pr_cr_log.json")

        vnv_md = ["# 🧪 SW Verification Results & Release/Maintenance Report (V&V, Release & Maintenance - IEC 62304 5.5~5.8, 6, 8, 9)\n"]
        vnv_md.append("## 1. V-Model 4-Tier Test Results (UT / IT / ST / VT)")
        vnv_md.append("| ID | Level | Test Name | Target File | Negative/Fault-Injection | Execution Status | Upward Verification Target |")
        vnv_md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for it in tc_items:
            up = ", ".join([f"{k}@v{v}" for k, v in it.get("traces_to", {}).items()])
            vnv_md.append(f"| {it['id']} | {it.get('test_level')} | {it['title']} | {it.get('test_file_path')} | {it.get('is_negative_test')} | **{it.get('last_run_status')}** | {up} |")

        vnv_md.append("\n## 2. Configuration Baseline History (Configuration Baselines - Clause 8.1)")
        vnv_md.append("| Baseline ID | Stage/Version Name | Snapshot Hash | Locked Items Count | Created At |")
        vnv_md.append("| :--- | :--- | :--- | :--- | :--- |")
        for bl in bl_items:
            locked_cnt = len(bl.get("locked_item_versions", {}))
            vnv_md.append(f"| {bl['id']} | {bl.get('stage_name')} | `{str(bl.get('snapshot_commit_or_hash'))[:16]}...` | {locked_cnt} items | {bl.get('created_at')} |")

        vnv_md.append("\n## 3. Problem Resolution & Change Control History (PR / CR Log - Clause 6, 8.2, 9)")
        vnv_md.append("| ID | Type | Title | Impacted Items / Cause | Regression Tests / Status | Upward Link |")
        vnv_md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for pc in pr_cr_items:
            up = ", ".join([f"{k}@v{v}" for k, v in pc.get("traces_to", {}).items()]) or "-"
            if pc.get("type") == "PR":
                vnv_md.append(f"| {pc['id']} | PR | {pc['title']} | {pc.get('problem_source')} ({pc.get('safety_security_impact')}) | **{pc.get('resolution_status')}** | {up} |")
            else:
                imp = ", ".join(pc.get("impacted_item_ids", []))
                reg = ", ".join(pc.get("regression_test_ids", []))
                vnv_md.append(f"| {pc['id']} | CR | {pc['title']} | Impact: {imp} | Regression: {reg} (**{pc.get('approval_status')}**) | {up} |")

        vnv_md.append("\n## 4. Official SW Release History (Software Releases - Clause 5.8)")
        vnv_md.append("| ID | Release Version | Baseline | Residual Risk Acceptable | Remaining Anomalies Count |")
        vnv_md.append("| :--- | :--- | :--- | :--- | :--- |")
        for rel in rel_items:
            anom_cnt = len(rel.get("known_remaining_anomalies", []))
            vnv_md.append(f"| {rel['id']} | **v{rel.get('release_version')}** | {rel.get('baseline_id')} | {rel.get('overall_residual_risk_acceptable')} | {anom_cnt} items |")

        fp_vnv = self.docs_dir / "05_VNV_Verification_Report.md"
        with open(fp_vnv, "w", encoding="utf-8") as f:
            f.write("\n".join(vnv_md))
        rendered_files.append(str(fp_vnv))

        # 7. VT_Manual_Test_Checklist.md (Human-friendly checklist)
        vt_items = [it for it in tc_items if it.get("test_level") == "VT" or it.get("execution_mode") == "manual_checklist"]
        vt_md = [
            "# 📋 User Validation (VT) and Manual Test Checklist\n",
            "> This document is a simple checklist designed for humans to directly operate screens or verify clinical scenarios.\n",
            "> When users check items or report results, the 4-A tester agent records them into formal DHF on their behalf.\n\n",
            "| ID | Test Item | Test Procedure and Verification Criteria (Protocol) | Verdict (Pass/Fail) | Signature/Date | Notes |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        if not vt_items:
            vt_md.append("| - | No registered manual/VT test items | - | - | - | - |")
        else:
            for it in vt_items:
                protocol = it.get("validation_protocol") or it.get("description", "")
                status = it.get("last_run_status", "PENDING")
                checked = "[x] PASS" if status == "PASS" else "[ ] PENDING"
                vt_md.append(f"| {it['id']} | {it['title']} | {protocol} | {checked} | {it.get('human_verified_by', '')} | {it.get('human_observation_notes', '')} |")

        fp_vt = self.docs_dir / "VT_Manual_Test_Checklist.md"
        with open(fp_vt, "w", encoding="utf-8") as f:
            f.write("\n".join(vt_md))
        rendered_files.append(str(fp_vt))

        # 8. 99_RTM_Traceability_Matrix.md
        trace_path = self.traceability_path
        rtm_md = ["# 🔗 Requirements Traceability Matrix (RTM)\n"]
        if trace_path.exists():
            with open(trace_path, "r", encoding="utf-8") as f:
                trace_data = json.load(f)
            links = trace_data.get("links", {})
            cov = trace_data.get("coverage_summary", {})

            rtm_md.append("## 1. Coverage Summary")
            rtm_md.append(f"- **Total Managed Items**: {cov.get('total_items', 0)} items")
            rtm_md.append(f"- **Orphan (Uncovered) Items**: {len(cov.get('uncovered_items', []))} items")
            rtm_md.append(f"- **Broken Links**: {len(cov.get('broken_links', []))} items")
            rtm_md.append(f"- **Re-review Required (Suspect Links)**: {len(cov.get('suspect_links', []))} items\n")

            rtm_md.append("## 2. Upward/Downward Bidirectional Link Status per Item")
            rtm_md.append("| Item ID | Type | Version | Upward Links | Downward Links | Suspect Status | Rationale |")
            rtm_md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for iid, n in sorted(links.items()):
                up_s = "<br>".join([f"{k}@v{v}" for k, v in n.get("upward", {}).items()]) or "-"
                down_s = "<br>".join([f"{k}@v{v}" for k, v in n.get("downward", {}).items()]) or "-"
                sus_s = "⚠️ **SUSPECT**" if n.get("is_suspect") else "✅ Normal"
                reasons = "<br>".join(n.get("suspect_reasons", [])) or "-"
                rtm_md.append(f"| {iid} | {n.get('item_type')} | v{n.get('current_version')} | {up_s} | {down_s} | {sus_s} | {reasons} |")

        fp_rtm = self.docs_dir / "99_RTM_Traceability_Matrix.md"
        with open(fp_rtm, "w", encoding="utf-8") as f:
            f.write("\n".join(rtm_md))
        rendered_files.append(str(fp_rtm))

        return rendered_files


# ==============================================================================
# 4. CLI Interface
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
        # Check if item_json is a file path
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
