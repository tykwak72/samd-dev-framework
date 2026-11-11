# 📋 SaMD Development Framework Step 1 Technical Specification: Data Schemas & Traceability Standards (SCHEMA_SPEC.md)

This document serves as the Single Source of Truth for **Step 1 (Data Schemas & Traceability Standards)** of the **Antigravity-based SaMD Development Multi-Agent Framework**. Data management tools (`dhf_cli.py`) and automated checkpoints (`gatekeeper.py`) implemented in Step 2 perform mechanical verification based on this specification.

---

## 1. Base Envelope Schema

Every individual item stored in `store/*.json` must contain the 9 common fields below.

```json
{
  "id": "<PREFIX>-<NNN>",
  "type": "<PREFIX>",
  "version": 1,
  "status": "draft",
  "title": "Summary title (string)",
  "description": "Detailed specification content (string)",
  "traces_to": {
    "<UPSTREAM_ID>": 1
  },
  "updated_at": "2026-11-08T16:00:00Z",
  "updated_by": "agent_role_id"
}
```

### Common Field Definitions
- **`id` (string)**: Unique identifier (`<PREFIX>-<NNN>`, e.g., `SRS-001`, `SDS-005`)
- **`type` (string)**: Item type matching identifier prefix
- **`version` (integer)**: Integer incrementing by 1 upon content modification (`1, 2, ...`)
- **`status` (string)**: `"draft"` | `"approved"` | `"deprecated"`
- **`title` (string)**: One-line summary
- **`description` (string)**: Detailed specification text
- **`traces_to` (object)**: Map of direct upstream item IDs referenced and their version at that point (`{"UPSTREAM_ID": version_int}`)
  - Example: `{"URS-001": 1, "RC-SAF-001": 2}`
- **`updated_at` (string)**: ISO-8601 timestamp
- **`updated_by` (string)**: Authoring agent role identifier (e.g., `1-A_requirements_author`)

---

## 2. Single Ownership and Specialized Field Specifications per File

Each file can only be modified by its designated **exclusive owner agent** and possesses unique specialized fields.

### 2.1 Stage 0: Planning & Development Plan
| Filename | Exclusive Owner | Prefix | Specialized Mandatory Field Specifications |
| :--- | :--- | :--- | :--- |
| **`00_intake.json`** | `0-0_intake_agent` | `INT` | • `intended_use` (string)<br>• `indications_for_use` (string)<br>• `target_patient_population` (string)<br>• `intended_users` (string)<br>• `use_environment` (string)<br>• `clinical_benefit` (string)<br>• `device_category` ("SaMD" \| "SiMD")<br>• `has_ai_ml` (bool)<br>• `has_network` (bool)<br>• `has_gui` (bool)<br>• `has_alarm` (bool)<br>• `project_mode` ("new" \| "maintenance") |
| **`00_literature.json`** | `0-A_literature_researcher` | `LIT` | • `category` ("clinical_guideline" \| "algorithm_benchmark" \| "predicate_hazard")<br>• `source_citation` (string)<br>• `key_findings` (string)<br>• `benchmark_criteria` (string)<br>• `known_hazards_identified` (list[string]) |
| **`00_regulatory.json`** | `0-B_regulatory_strategist` | `REG` | • `safety_class` ("Class A" \| "Class B" \| "Class C")<br>• `fda_doc_level` ("Basic" \| "Enhanced")<br>• `target_regions` (list[string])<br>• `active_profiles` (list[string])<br>• `applicable_standards` (list[string])<br>• `regulatory_mandate` (string) |
| **`00_sdp_plan.json`** | `0-C_sdp_planner`<br>`0_orchestrator` | `SDP` | • `project_profile` (object: class/option switch header)<br>• `plan_category` ("lifecycle" \| "tech_stack" \| "risk_matrix" \| "soup_cm" \| "vv_criteria")<br>• `language_and_runtime` (string)<br>• `coding_standards` (list[string])<br>• `risk_acceptability_rule` (string)<br>• `min_test_coverage_pct` (int)<br>• `workflow_steps` (list[object]: execution script bound with dynamic input/output file lists) |

### 2.2 Stage 1: Requirements Specification
| Filename | Exclusive Owner | Prefix | Specialized Mandatory Field Specifications |
| :--- | :--- | :--- | :--- |
| **`01_urs.json`** | `1-A_requirements_author` | `URS` | • `stakeholder` ("clinician" \| "patient" \| "operator" \| "regulator")<br>• `acceptance_criteria` (string) |
| **`02_srs.json`** | `1-A_requirements_author` | `SRS` | • `req_category` ("functional" \| "performance" \| "safety" \| "security" \| "usability" \| "interface" \| "ai_data")<br>• `verification_method` ("system_test" \| "integration_test" \| "unit_test" \| "inspection")<br>• `measurable_criteria` (string: quantitative/testable criteria) |
| **`opt_ai_spec.json`**<br>*(Option: ai_ml)* | `1-E_option_domain_author` | `DAT` | • `dataset_split_policy` (string: train/val/test data split criteria)<br>• `data_quality_criteria` (string: ISO/IEC 5259 integrity/representativeness requirements)<br>• `model_reproducibility` (string: seed/hyperparameter management)<br>• `clinical_metrics_target` (dict: e.g. `{"sensitivity_min": 0.95}`)<br>• `pccp_boundary` (string: pre-determined change control plan boundary) |
| **`opt_simd_alarm.json`**<br>*(Option: SiMD/Alarm)* | `1-E_option_domain_author` | `HSI`<br>`ALM` | • **HSI**: `hardware_component`, `interface_protocol`, `timing_and_sampling_spec`, `hardware_fault_detection`<br>• **ALM**: `alarm_priority` ("High" \| "Medium" \| "Low"), `trigger_condition`, `visual_indicator_spec`, `auditory_signal_spec`, `pause_or_ack_policy` |
| **`opt_usability_gui.json`**<br>*(Option: In-depth GUI)* | `1-E_option_domain_author` | `UE` | • `user_task_scenario` (string)<br>• `potential_use_error` (string)<br>• `ui_risk_control_design` (string)<br>• `evaluation_protocol` (string: formative/summative evaluation pass criteria) |

### 2.3 Stage 2: Architecture & Detailed Design
| Filename | Exclusive Owner | Prefix | Specialized Mandatory Field Specifications |
| :--- | :--- | :--- | :--- |
| **`03_sad_soup.json`** | `2-A_software_architect` | `SAD`<br>`SOUP` | • **SAD**: `module_name`, `safety_class` (Class A/B/C), `module_responsibility`, `public_interfaces` (list), `segregation_strategy`<br>• **SOUP**: `package_name`, `exact_version`, `license`, `functional_performance_req`, `hw_memory_requirements`, `known_anomalies_and_cve`, `risk_control_justification` |
| **`04_sds.json`** | `2-A_software_architect` | `SDS` | **[Strict Signature Contracts for Black-Box Testing]**<br>• `target_file_path` (string: e.g. `"src/vital_monitor.py"`)<br>• `unit_type` ("function" \| "class" \| "method")<br>• `callable_name` (string: e.g. `"evaluate_blood_pressure"`)<br>• `callable_signature` (string: e.g. `"def evaluate_blood_pressure(systolic: float, diastolic: float) -> dict"` )<br>• `parameters_contract` (list[dict]: `[{"name": "...", "type": "...", "unit": "...", "valid_range": [...]}]`)<br>• `return_contract` (dict: `{"type": "...", "required_keys": [...]}`)<br>• `exception_contract` (list[dict]: `[{"exception_type": "ValueError", "condition": "..."}]`)<br>• `algorithm_specification` (string) |

### 2.4 Stage 4 & 5: V-Model 4-Tier Independent Verification & Release
| Filename | Exclusive Owner | Prefix | Specialized Mandatory Field Specifications |
| :--- | :--- | :--- | :--- |
| **`05_tc.json`** | `4-A_blackbox_tester` | `UT`<br>`IT`<br>`ST`<br>`VT` | • `test_level` ("UT" \| "IT" \| "ST" \| "VT")<br>• `execution_mode` ("automated" \| "manual_checklist")<br>• `is_negative_test` (bool: fault-injection/boundary-value/penetration test)<br>• `test_file_path` (string: e.g. `"tests/test_ut_vital.py"`)<br>• `test_callable_name` (string)<br>• `expected_outcome` (string)<br>• `last_run_status` ("PENDING" \| "PASS" \| "FAIL")<br>• *(For VT manual tests)* `validation_protocol`, `human_verified_by`, `human_observation_notes` |
| **`06_release.json`** | `5-A_release_author` | `REL` | • `release_version` (string: e.g. `"1.0.0"`)<br>• `baseline_id` (string: referenced `BL-xxx`)<br>• `known_remaining_anomalies` (list[dict]: unresolved residual defects and safety justifications)<br>• `overall_residual_risk_acceptable` (bool)<br>• `release_environment_spec` (dict) |

### 2.5 Continuous Parallel Processes (Risk Management, Audit, Configuration Management, Maintenance)
| Filename | Exclusive Owner | Prefix | Specialized Mandatory Field Specifications |
| :--- | :--- | :--- | :--- |
| **`rmf_safety.json`** | `1-B`, `2-B`, `3-B`, `4-B` | `HAZ-SAF`<br>`RC-SAF` | • **HAZ-SAF**: `stage_identified`, `hazard_category`, `harm`, `initial_severity` (1~5), `initial_probability` (1~5), `initial_risk_score`, `control_required` (bool), `residual_severity`, `residual_probability`, `residual_risk_score`, `residual_acceptable` (bool), `new_hazards_introduced` (bool), `benefit_risk_justification`<br>• **RC-SAF**: `control_priority` ("1_inherent_safety" \| "2_protective_measure" \| "3_information_for_safety"), `priority_justification`, `control_measure`, `verification_status` |
| **`rmf_security.json`** | `1-C`, `2-C`, `3-B`, `4-B` | `HAZ-SEC`<br>`RC-SEC` | • **HAZ-SEC**: `stage_identified`, `stride_category`, `threat_scenario`, `patient_safety_impact`, initial/residual severity and probability scores<br>• **RC-SEC**: `security_control_type`, `control_measure`, `safety_tradeoff_check` (verify emergency clinical non-impediment) |
| **`audit_findings.json`** | Auditor (`*-D`, `3-C`, `5-B`) | `AUD` | • `stage`, `auditor_role`, `verdict` ("PASS" \| "REJECT"), `target_agent`, `target_item_ids`, `finding_details`, `remediation_required`, `resolution_status` |
| **`cm_baselines.json`** | `0_orchestrator`, `SYSTEM_ENGINE` | `BL` | • `baseline_id`, `stage_name`, `snapshot_commit_or_hash`, `locked_item_versions` (dict: `{"ID": version}`), `created_at` |
| **`pr_cr_log.json`** | `6-A_maintenance_change_analyst` | `PR`<br>`CR` | • **PR**: `problem_source`, `safety_security_impact`, `investigation_summary`, `resolution_status`<br>• **CR**: `change_reason`, `impacted_item_ids` (list), `regression_test_ids` (list), `approval_status` *(Activated only during post-release maintenance)* |

---

## 3. Central Bidirectional Traceability Ledger (`traceability.json`) Specification

Based on unidirectional `traces_to` pointers of individual files, this central bidirectional mapping structure is atomically updated and verified by the Python management engine.

```json
{
  "last_updated": "2026-11-08T16:00:00Z",
  "links": {
    "SRS-001": {
      "item_type": "SRS",
      "current_version": 1,
      "store_file": "02_srs.json",
      "upward": {
        "URS-001": 1,
        "RC-SAF-001": 1
      },
      "downward": {
        "SDS-001": 1,
        "ST-001": 1
      },
      "is_suspect": false,
      "suspect_reasons": []
    }
  },
  "coverage_summary": {
    "total_items": 45,
    "uncovered_items": [],
    "broken_links": [],
    "suspect_links": []
  }
}
```

### Suspect Link (Change Impact) Detection Mechanism
- When the version of upstream item `URS-001` increments `1` $\rightarrow$ `2`:
  - The engine sets `is_suspect` to `true` for all downstream links (`SRS-001`) referencing `URS-001` in `traceability.json` and records the reason (`"Upstream URS-001 bumped to v2"`).
  - Impact cascades down not only to `SRS-001` but also to downstream `SDS-001` and `ST-001`.
  - Passing checkpoints is blocked until all `is_suspect` items are re-examined against the new version and version numbers match.

---

## 4. V-Model 1:1 Symmetrical Verification & Stage Gate Pass Rules

The automated checkpoint (`gatekeeper.py`) mechanically inspects all rules below upon concluding each Stage:

1. **Stage 0 Gate**:
   - $\forall \text{INT} \implies \exists \text{LIT} \land \exists \text{REG}$
   - $\forall \text{REG} \implies \exists \text{SDP}$ (All regulatory requirements reflected in development plan)
2. **Stage 1 Gate**:
   - $\forall \text{INT} \implies \exists \text{URS}$
   - $\forall \text{URS} \implies \exists \text{SRS}$
   - $\forall \text{HAZ-SAF (control\_required=True)} \implies \exists \text{RC-SAF} \implies \exists \text{SRS}$
   - $\forall \text{HAZ-SEC (control\_required=True)} \implies \exists \text{RC-SEC} \implies \exists \text{SRS}$
3. **Stage 2 Gate**:
   - $\forall \text{SRS} \implies \exists \text{SAD} \land \exists \text{SDS}$
   - $\forall \text{SDS}$ must fully equip valid `target_file_path`, `callable_signature`, `parameters_contract`, `exception_contract`.
4. **Stage 3 Gate**:
   - $\forall \text{SDS} \implies \exists \text{Source Code in src/ with @traces: SDS-xxx@ver}$
   - Python AST parser verification: Actual function/class names and parameter signatures in source code must match contracts in `04_sds.json` 100% (blocked on mismatch).
   - Immediate rejection if `TODO`, `pass`, or empty function bodies exist.
   - Immediate rejection if unapproved external package `import`s not in `03_sad_soup.json` are detected.
5. **Stage 4 Gate (V-Model 4-Tier Symmetrical Verification)**:
   - **Unit Verification (`UT`)**: $\forall \text{SDS} \implies \exists \text{UT} \land (\text{Result} == \text{PASS})$ (IEC 62304 Clause 5.5)
   - **Integration Testing (`IT`)**: $\forall \text{SAD} \implies \exists \text{IT} \land (\text{Result} == \text{PASS})$ (IEC 62304 Clause 5.6)
   - **System Testing (`ST`)**: $\forall \text{SRS} \implies \exists \text{ST} \land (\text{Result} == \text{PASS})$ (IEC 62304 Clause 5.7)
   - **Risk Control Fault Injection Testing**: $\forall (\text{RC-SAF}, \text{RC-SEC}) \implies \exists \text{Test with (is\_negative\_test=True)} \land (\text{Result} == \text{PASS})$
   - **User Validation (`VT`)**: $\forall \text{URS} \implies \exists \text{VT} \land (\text{Result} == \text{PASS})$ (IEC 82304-1)
6. **Stage 5 Gate (Release)**:
   - `traceability.json` has `uncovered_items == []` and `suspect_links == []`
   - All defects resolved (`CLOSED`), or for unresolved defects (`DEFERRED`), safety justification completed and registered in `06_release.json`.
