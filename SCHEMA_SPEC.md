# 📋 SaMD 개발 프레임워크 Step 1 기술 명세서: 데이터 스키마 및 추적성 규격 (SCHEMA_SPEC.md)

본 문서는 **Antigravity 기반 SaMD 개발 멀티에이전트 프레임워크**의 **Step 1(데이터 스키마 및 추적성 규격)**의 기준 문서(Single Source of Truth)입니다. Step 2에서 구현될 데이터 관리 도구(`dhf_cli.py`) 및 자동 검문소(`gatekeeper.py`)는 본 규격을 기준으로 기계적 검증을 수행합니다.

---

## 1. 기본 레코드 규격 (Base Envelope Schema)

`store/*.json`에 저장되는 모든 개별 항목(Item)은 아래 공통 9대 필드를 반드시 포함합니다.

```json
{
  "id": "<PREFIX>-<NNN>",
  "type": "<PREFIX>",
  "version": 1,
  "status": "draft",
  "title": "요약 제목 (문자열)",
  "description": "상세 명세 내용 (문자열)",
  "traces_to": {
    "<UPSTREAM_ID>": 1
  },
  "updated_at": "2026-11-08T16:00:00Z",
  "updated_by": "에이전트_역할_ID"
}
```

### 공통 필드 정의
- **`id` (string)**: 고유 식별자 (`<PREFIX>-<NNN>`, 예: `SRS-001`, `SDS-005`)
- **`type` (string)**: 식별자 접두사와 일치하는 항목 유형
- **`version` (integer)**: 내용 변경 시 1씩 증가하는 정수 (`1, 2, ...`)
- **`status` (string)**: `"draft"` | `"approved"` | `"deprecated"`
- **`title` (string)**: 한 줄 요약
- **`description` (string)**: 정밀 명세 본문
- **`traces_to` (object)**: 참조하는 직전 상위 항목 ID 및 해당 시점의 버전 맵 (`{"상위ID": 버전정수}`)
  - 예: `{"URS-001": 1, "RC-SAF-001": 2}`
- **`updated_at` (string)**: ISO-8601 타임스탬프
- **`updated_by` (string)**: 작성 에이전트 역할 식별자 (예: `1-A_requirements_author`)

---

## 2. 파일별 단일 소유권(Single Ownership) 및 특화 필드 규격

각 파일은 오직 지정된 **독점 소유자 에이전트**만 수정할 수 있으며, 고유한 특화 필드를 가집니다.

### 2.1 Stage 0: 기획 및 개발계획서
| 파일명 | 독점 소유자 | 접두사 | 특화 필수 필드 규격 |
| :--- | :--- | :--- | :--- |
| **`00_intake.json`** | `0-0_intake_agent` | `INT` | • `intended_use` (string)<br>• `indications_for_use` (string)<br>• `target_patient_population` (string)<br>• `intended_users` (string)<br>• `use_environment` (string)<br>• `clinical_benefit` (string)<br>• `device_category` ("SaMD" \| "SiMD")<br>• `has_ai_ml` (bool)<br>• `has_network` (bool)<br>• `has_gui` (bool)<br>• `has_alarm` (bool)<br>• `project_mode` ("new" \| "maintenance") |
| **`00_literature.json`** | `0-A_literature_researcher` | `LIT` | • `category` ("clinical_guideline" \| "algorithm_benchmark" \| "predicate_hazard")<br>• `source_citation` (string)<br>• `key_findings` (string)<br>• `benchmark_criteria` (string)<br>• `known_hazards_identified` (list[string]) |
| **`00_regulatory.json`** | `0-B_regulatory_strategist` | `REG` | • `safety_class` ("Class A" \| "Class B" \| "Class C")<br>• `fda_doc_level` ("Basic" \| "Enhanced")<br>• `target_regions` (list[string])<br>• `active_profiles` (list[string])<br>• `applicable_standards` (list[string])<br>• `regulatory_mandate` (string) |
| **`00_sdp_plan.json`** | `0-C_sdp_planner`<br>`0_orchestrator` | `SDP` | • `project_profile` (object: 등급/옵션스위치 헤더)<br>• `plan_category` ("lifecycle" \| "tech_stack" \| "risk_matrix" \| "soup_cm" \| "vv_criteria")<br>• `language_and_runtime` (string)<br>• `coding_standards` (list[string])<br>• `risk_acceptability_rule` (string)<br>• `min_test_coverage_pct` (int)<br>• `workflow_steps` (list[object]: 동적 입출력 파일 목록이 바인딩된 실행 대본) |

### 2.2 Stage 1: 요구사항 명세
| 파일명 | 독점 소유자 | 접두사 | 특화 필수 필드 규격 |
| :--- | :--- | :--- | :--- |
| **`01_urs.json`** | `1-A_requirements_author` | `URS` | • `stakeholder` ("clinician" \| "patient" \| "operator" \| "regulator")<br>• `acceptance_criteria` (string) |
| **`02_srs.json`** | `1-A_requirements_author` | `SRS` | • `req_category` ("functional" \| "performance" \| "safety" \| "security" \| "usability" \| "interface" \| "ai_data")<br>• `verification_method` ("system_test" \| "integration_test" \| "unit_test" \| "inspection")<br>• `measurable_criteria` (string: 정량적/시험 가능한 판정 기준) |
| **`opt_ai_spec.json`**<br>*(옵션: ai_ml)* | `1-E_option_domain_author` | `DAT` | • `dataset_split_policy` (string: 학습/검증/시험 데이터 분리 기준)<br>• `data_quality_criteria` (string: ISO/IEC 5259 무결성/대표성 요건)<br>• `model_reproducibility` (string: 시드/하이퍼파라미터 관리)<br>• `clinical_metrics_target` (dict: e.g. `{"sensitivity_min": 0.95}`)<br>• `pccp_boundary` (string: 사전변경관리 경계) |
| **`opt_simd_alarm.json`**<br>*(옵션: SiMD/알람)* | `1-E_option_domain_author` | `HSI`<br>`ALM` | • **HSI**: `hardware_component`, `interface_protocol`, `timing_and_sampling_spec`, `hardware_fault_detection`<br>• **ALM**: `alarm_priority` ("High" \| "Medium" \| "Low"), `trigger_condition`, `visual_indicator_spec`, `auditory_signal_spec`, `pause_or_ack_policy` |
| **`opt_usability_gui.json`**<br>*(옵션: GUI 심화)* | `1-E_option_domain_author` | `UE` | • `user_task_scenario` (string)<br>• `potential_use_error` (string)<br>• `ui_risk_control_design` (string)<br>• `evaluation_protocol` (string: 형성/총괄평가 판정 기준) |

### 2.3 Stage 2: 아키텍처 및 상세설계
| 파일명 | 독점 소유자 | 접두사 | 특화 필수 필드 규격 |
| :--- | :--- | :--- | :--- |
| **`03_sad_soup.json`** | `2-A_software_architect` | `SAD`<br>`SOUP` | • **SAD**: `module_name`, `safety_class` (Class A/B/C), `module_responsibility`, `public_interfaces` (list), `segregation_strategy`<br>• **SOUP**: `package_name`, `exact_version`, `license`, `functional_performance_req`, `hw_memory_requirements`, `known_anomalies_and_cve`, `risk_control_justification` |
| **`04_sds.json`** | `2-A_software_architect` | `SDS` | **[블랙박스 시험을 위한 엄격한 시그니처 계약]**<br>• `target_file_path` (string: e.g. `"src/vital_monitor.py"`)<br>• `unit_type` ("function" \| "class" \| "method")<br>• `callable_name` (string: e.g. `"evaluate_blood_pressure"`)<br>• `callable_signature` (string: e.g. `"def evaluate_blood_pressure(systolic: float, diastolic: float) -> dict"` )<br>• `parameters_contract` (list[dict]: `[{"name": "...", "type": "...", "unit": "...", "valid_range": [...]}]`)<br>• `return_contract` (dict: `{"type": "...", "required_keys": [...]}`)<br>• `exception_contract` (list[dict]: `[{"exception_type": "ValueError", "condition": "..."}]`)<br>• `algorithm_specification` (string) |

### 2.4 Stage 4 & 5: V-모델 4계층 독립 검증 및 릴리즈
| 파일명 | 독점 소유자 | 접두사 | 특화 필수 필드 규격 |
| :--- | :--- | :--- | :--- |
| **`05_tc.json`** | `4-A_blackbox_tester` | `UT`<br>`IT`<br>`ST`<br>`VT` | • `test_level` ("UT" \| "IT" \| "ST" \| "VT")<br>• `execution_mode` ("automated" \| "manual_checklist")<br>• `is_negative_test` (bool: 고장유도/경계값/침투 시험 여부)<br>• `test_file_path` (string: e.g. `"tests/test_ut_vital.py"`)<br>• `test_callable_name` (string)<br>• `expected_outcome` (string)<br>• `last_run_status` ("PENDING" \| "PASS" \| "FAIL")<br>• *(VT 수동시험 시)* `validation_protocol`, `human_verified_by`, `human_observation_notes` |
| **`06_release.json`** | `5-A_release_author` | `REL` | • `release_version` (string: e.g. `"1.0.0"`)<br>• `baseline_id` (string: 참조 `BL-xxx`)<br>• `known_remaining_anomalies` (list[dict]: 미해결 잔여 결함 및 안전성 정당화 사유)<br>• `overall_residual_risk_acceptable` (bool)<br>• `release_environment_spec` (dict) |

### 2.5 상시 병행 프로세스 (위험관리, 감사, 형상관리, 유지보수)
| 파일명 | 독점 소유자 | 접두사 | 특화 필수 필드 규격 |
| :--- | :--- | :--- | :--- |
| **`rmf_safety.json`** | `1-B`, `2-B`, `3-B`, `4-B` | `HAZ-SAF`<br>`RC-SAF` | • **HAZ-SAF**: `stage_identified`, `hazard_category`, `harm`, `initial_severity` (1~5), `initial_probability` (1~5), `initial_risk_score`, `control_required` (bool), `residual_severity`, `residual_probability`, `residual_risk_score`, `residual_acceptable` (bool), `new_hazards_introduced` (bool), `benefit_risk_justification`<br>• **RC-SAF**: `control_priority` ("1_inherent_safety" \| "2_protective_measure" \| "3_information_for_safety"), `priority_justification`, `control_measure`, `verification_status` |
| **`rmf_security.json`** | `1-C`, `2-C`, `3-B`, `4-B` | `HAZ-SEC`<br>`RC-SEC` | • **HAZ-SEC**: `stage_identified`, `stride_category`, `threat_scenario`, `patient_safety_impact`, 초기/잔여 심각도 및 가능성 점수<br>• **RC-SEC**: `security_control_type`, `control_measure`, `safety_tradeoff_check` (응급 임상 방해 여부 확인) |
| **`audit_findings.json`** | 감사관 (`*-D`, `3-C`, `5-B`) | `AUD` | • `stage`, `auditor_role`, `verdict` ("PASS" \| "REJECT"), `target_agent`, `target_item_ids`, `finding_details`, `remediation_required`, `resolution_status` |
| **`cm_baselines.json`** | `0_orchestrator`, `SYSTEM_ENGINE` | `BL` | • `baseline_id`, `stage_name`, `snapshot_commit_or_hash`, `locked_item_versions` (dict: `{"ID": version}`), `created_at` |
| **`pr_cr_log.json`** | `6-A_maintenance_change_analyst` | `PR`<br>`CR` | • **PR**: `problem_source`, `safety_security_impact`, `investigation_summary`, `resolution_status`<br>• **CR**: `change_reason`, `impacted_item_ids` (list), `regression_test_ids` (list), `approval_status` *(오직 릴리즈 후 유지보수 시에만 가동)* |

---

## 3. 중앙 양방향 추적성 장부 (`traceability.json`) 규격

개별 파일의 `traces_to` 단방향 포인터를 기반으로, 파이썬 관리 엔진이 원자적으로 갱신하고 검증하는 중앙 양방향 매핑 구조입니다.

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

### Suspect Link (변경 영향) 탐지 메커니즘
- 상위 항목 `URS-001`의 버전이 `1` $\rightarrow$ `2`로 갱신되면:
  - 엔진은 `traceability.json`에서 `URS-001`을 참조하는 모든 하위 링크(`SRS-001`)의 `is_suspect`를 `true`로 설정하고 사유(`"Upstream URS-001 bumped to v2"`)를 기록합니다.
  - `SRS-001`뿐만 아니라 그 하위의 `SDS-001`, `ST-001`까지 영향도가 연쇄 전파됩니다.
  - 모든 `is_suspect` 항목이 새 버전에 맞춰 재검토되어 버전 번호가 일치되기 전까지 검문소 통과가 차단됩니다.

---

## 4. V-모델 1:1 대칭 검증 및 Stage Gate 합격 규칙

자동 검문소(`gatekeeper.py`)는 각 Stage 종료 시 아래 규칙을 기계적으로 전수 검사합니다:

1. **Stage 0 Gate**:
   - $\forall \text{INT} \implies \exists \text{LIT} \land \exists \text{REG}$
   - $\forall \text{REG} \implies \exists \text{SDP}$ (모든 규제 요구사항이 개발계획에 반영)
2. **Stage 1 Gate**:
   - $\forall \text{INT} \implies \exists \text{URS}$
   - $\forall \text{URS} \implies \exists \text{SRS}$
   - $\forall \text{HAZ-SAF (control\_required=True)} \implies \exists \text{RC-SAF} \implies \exists \text{SRS}$
   - $\forall \text{HAZ-SEC (control\_required=True)} \implies \exists \text{RC-SEC} \implies \exists \text{SRS}$
3. **Stage 2 Gate**:
   - $\forall \text{SRS} \implies \exists \text{SAD} \land \exists \text{SDS}$
   - $\forall \text{SDS}$는 유효한 `target_file_path`, `callable_signature`, `parameters_contract`, `exception_contract`를 완비해야 함.
4. **Stage 3 Gate**:
   - $\forall \text{SDS} \implies \exists \text{Source Code in src/ with @traces: SDS-xxx@ver}$
   - 파이썬 AST 파서 검증: 소스코드의 실제 함수/클래스명 및 매개변수 시그니처가 `04_sds.json`의 계약과 100% 일치해야 함 (불일치 시 차단).
   - `TODO`, `pass`, 빈 함수 몸체 존재 시 즉시 탈락.
   - `03_sad_soup.json`에 승인되지 않은 외부 패키지 `import` 적발 시 즉시 탈락.
5. **Stage 4 Gate (V-모델 4계층 대칭 검증)**:
   - **단위 검증 (`UT`)**: $\forall \text{SDS} \implies \exists \text{UT} \land (\text{Result} == \text{PASS})$ (IEC 62304 5.5절)
   - **통합 시험 (`IT`)**: $\forall \text{SAD} \implies \exists \text{IT} \land (\text{Result} == \text{PASS})$ (IEC 62304 5.6절)
   - **시스템 시험 (`ST`)**: $\forall \text{SRS} \implies \exists \text{ST} \land (\text{Result} == \text{PASS})$ (IEC 62304 5.7절)
   - **위험통제 고장유도 시험**: $\forall (\text{RC-SAF}, \text{RC-SEC}) \implies \exists \text{Test with (is\_negative\_test=True)} \land (\text{Result} == \text{PASS})$
   - **사용자 밸리데이션 (`VT`)**: $\forall \text{URS} \implies \exists \text{VT} \land (\text{Result} == \text{PASS})$ (IEC 82304-1)
6. **Stage 5 Gate (릴리즈)**:
   - `traceability.json` 내 `uncovered_items == []` 및 `suspect_links == []`
   - 모든 결함이 해결되었거나(`CLOSED`), 미해결 결함(`DEFERRED`)의 경우 안전성 정당화가 완료되어 `06_release.json`에 등재 완료됨.
