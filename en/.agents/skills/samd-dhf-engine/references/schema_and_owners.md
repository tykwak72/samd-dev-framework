# 📋 Exclusive Owners (Actor) and Schema Cheat Sheet for 18 DHF Files

## 1. Common Base Envelope 9 Mandatory Fields (Common to All Items)
Every item JSON must include the 9 fields below (although `updated_at`, `updated_by`, and `version` are automatically set/incremented by the engine when calling `put_item`, including them as base keys is recommended):
```json
{
  "id": "<PREFIX>-<NNN>",
  "type": "<PREFIX>",
  "version": 1,
  "status": "approved",
  "title": "Item summary title",
  "description": "Detailed specification content",
  "traces_to": {"<UPSTREAM_ID>": 1},
  "updated_at": "2026-11-09T00:00:00Z",
  "updated_by": "<actor_id>"
}
```

---

## 2. Exclusive Owner (`--actor`) and Mandatory Specialized Fields per File

| Filename | Authorized `--actor` ID | Prefix (`type`) | Mandatory Specialized Fields (`required_fields`) |
| :--- | :--- | :---: | :--- |
| **`00_intake.json`** | `0-0_intake_agent` | `INT` | `intended_use`, `indications_for_use`, `target_patient_population`, `intended_users`, `use_environment`, `clinical_benefit`, `device_category` ("SaMD"\|"SiMD"), `has_ai_ml` (bool), `has_network` (bool), `has_gui` (bool), `has_alarm` (bool), `project_mode` ("new"\|"maintenance") |
| **`00_literature.json`** | `0-A_literature_researcher` | `LIT` | `category`, `source_citation`, `key_findings`, `benchmark_criteria`, `known_hazards_identified` (list) |
| **`00_regulatory.json`** | `0-B_regulatory_strategist` | `REG` | `safety_class` ("Class A"\|"Class B"\|"Class C"), `fda_doc_level`, `target_regions` (list), `active_profiles` (list), `applicable_standards` (list), `regulatory_mandate` |
| **`00_sdp_plan.json`** | `0-C_sdp_planner`<br>`0_orchestrator` | `SDP` | `project_profile` (dict), `plan_category`, `language_and_runtime`, `coding_standards` (list), `risk_acceptability_rule`, `min_test_coverage_pct` (int), `workflow_steps` (list) |
| **`01_urs.json`** | `1-A_requirements_author` | `URS` | `stakeholder`, `acceptance_criteria` |
| **`02_srs.json`** | `1-A_requirements_author` | `SRS` | `req_category`, `verification_method`, `measurable_criteria` |
| **`opt_ai_spec.json`** | `1-E_option_domain_author` | `DAT` | `dataset_split_policy`, `data_quality_criteria`, `model_reproducibility`, `clinical_metrics_target` (dict), `pccp_boundary` |
| **`opt_simd_alarm.json`** | `1-E_option_domain_author` | `HSI`<br>`ALM` | • **HSI**: `hardware_component`, `interface_protocol`, `timing_and_sampling_spec`, `hardware_fault_detection`<br>• **ALM**: `alarm_priority`, `trigger_condition`, `visual_indicator_spec`, `auditory_signal_spec`, `pause_or_ack_policy` |
| **`opt_usability_gui.json`** | `1-E_option_domain_author` | `UE` | `user_task_scenario`, `potential_use_error`, `ui_risk_control_design`, `evaluation_protocol` |
| **`03_sad_soup.json`** | `2-A_software_architect` | `SAD`<br>`SOUP` | • **SAD**: `module_name`, `safety_class`, `module_responsibility`, `public_interfaces` (list), `segregation_strategy`<br>• **SOUP**: `package_name`, `exact_version`, `license`, `functional_performance_req`, `hw_memory_requirements`, `known_anomalies_and_cve`, `risk_control_justification` |
| **`04_sds.json`** | `2-A_software_architect` | `SDS` | `target_file_path`, `unit_type` ("function"\|"class"\|"method"), `callable_name`, `callable_signature`, `parameters_contract` (`[{"name": "..."}]`), `return_contract` (dict), `exception_contract` (list), `algorithm_specification` |
| **`05_tc.json`** | `4-A_blackbox_tester` | `UT`, `IT`, `ST`, `VT` | `test_level` ("UT"\|"IT"\|"ST"\|"VT"), `execution_mode` ("automated"\|"manual_checklist"), `is_negative_test` (bool), `test_file_path`, `test_callable_name`, `expected_outcome`, `last_run_status` ("PENDING"\|"PASS"\|"FAIL") |
| **`06_release.json`** | `5-A_release_author` | `REL` | `release_version`, `baseline_id` ("BL-xxx"), `known_remaining_anomalies` (list), `overall_residual_risk_acceptable` (bool), `release_environment_spec` (dict) |
| **`rmf_safety.json`** | `1-B_safety_risk_analyst`<br>`2-B_dfmea_risk_analyst`<br>`3-B_code_safety_analyst`<br>`4-B_residual_risk_evaluator` | `HAZ-SAF`<br>`RC-SAF` | • **HAZ-SAF**: `stage_identified`, `hazard_category`, `harm`, `initial_severity`, `initial_probability`, `initial_risk_score`, `control_required` (bool), `residual_severity`, `residual_probability`, `residual_risk_score`, `residual_acceptable` (bool), `new_hazards_introduced` (bool), `benefit_risk_justification`<br>• **RC-SAF**: `control_priority`, `priority_justification`, `control_measure`, `verification_status` |
| **`rmf_security.json`** | `1-C_security_risk_analyst`<br>`2-C_threat_security_analyst`<br>`3-B_code_safety_analyst`<br>`4-B_residual_risk_evaluator` | `HAZ-SEC`<br>`RC-SEC` | • **HAZ-SEC**: `stage_identified`, `stride_category`, `threat_scenario`, `patient_safety_impact`, `residual_acceptable` (Stage 4 closure requires True)<br>• **RC-SEC**: `security_control_type`, `control_measure`, `safety_tradeoff_check` |
| **`audit_findings.json`** | `0-D_stage0_auditor`<br>`1-D_stage1_auditor`<br>`2-D_stage2_auditor`<br>`3-C_stage3_auditor`<br>`4-D_stage4_auditor`<br>`5-B_final_release_auditor` | `AUD` | `stage` ("Stage 0" ~ "Stage 5"), `auditor_role`, `verdict` ("PASS"\|"REJECT"), `target_agent`, `target_item_ids` (list), `finding_details`, `remediation_required`, `resolution_status` ("OPEN"\|"CLOSED"\|"DEFERRED") |
| **`cm_baselines.json`** | `0_orchestrator` | `BL` | Automatically generated via `create-baseline` command (`baseline_id`, `stage_name`, `snapshot_commit_or_hash`, `locked_item_versions`, `created_at`) |
| **`pr_cr_log.json`** | `6-A_maintenance_change_analyst`<br>`4-C_maintenance_change_analyst` | `PR`<br>`CR` | • **PR**: `problem_source`, `safety_security_impact`, `investigation_summary`, `resolution_status` ("OPEN"\|"CLOSED"\|"DEFERRED")<br>• **CR**: `change_reason`, `impacted_item_ids` (list), `regression_test_ids` (list), `approval_status` ("PENDING"\|"APPROVED"\|"REJECTED") |

> [!NOTE]
> `SYSTEM_ENGINE` is an internal system-reserved account dedicated to DHF store initialization (`init`) and CSA self-validation testing (`test_framework_csa.py`), possessing system registration authority across all 18 files.
