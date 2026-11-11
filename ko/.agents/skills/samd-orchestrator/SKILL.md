---
name: samd-orchestrator
description: >-
  Use this skill when the user requests to develop, plan, or maintain a medical device software (SaMD or SiMD) project following the IEC 62304 V-model lifecycle, ISO 14971 risk management, and FDA CSA governance. Guides the Orchestrator agent through project isolation, Stage 0-5 execution, feedback loops, and independent subagent audits.
---

# 👑 SaMD V-Model Lifecycle Orchestrator Runbook

이 스킬은 사용자의 의료기기 소프트웨어(SaMD/SiMD) 개발 또는 유지보수 의뢰를 접수하여 **Stage 0(기획)부터 Stage 5(릴리즈) 및 Stage 6(사후 유지보수)**까지 전 주기를 지휘하는 총괄 공장장(Orchestrator) 표준 런북입니다.

---

## 1. 신규 프로젝트 격리 초기화 (Step 0)

모든 의료기기 프로젝트는 프레임워크 코어 엔진과 분리된 `projects/<project_slug>/` 폴더에 격리되어야 합니다.

1. 부트스트랩 스크립트를 실행하여 격리 프로젝트 샌드박스를 생성합니다:
   ```bash
   python3 .agents/skills/samd-orchestrator/scripts/bootstrap_project.py --slug <project_slug>
   ```
   (이 스크립트는 `projects/<project_slug>/{store,docs,src,tests}`를 생성하고 `dhf_cli.py init`을 수행합니다.)

---

## 2. Stage 0 ~ Stage 5 V-모델 실행 절차

각 단계의 상세 JSON 스키마와 소유자(`actor`) ID는 `samd-dhf-engine` 스킬의 [schema_and_owners.md](../samd-dhf-engine/references/schema_and_owners.md)를 참조하십시오.

### Stage 0: 의뢰 접수 · 문헌 조사 · 규제 분류 · 개발계획서(SDP)
1. **`0-0_intake_agent`**: 사용자 요구사항에서 빠진 임상 정보(적응증, 환자군, SaMD/SiMD, AI/네트워크/알람 유무)를 확인하여 `00_intake.json`(`INT-001`) 등록.
2. **`0-A_literature_researcher`**: 임상 가이드라인 및 벤치마크 문헌을 조사하여 `00_literature.json`(`LIT-001`, `traces_to: {"INT-001": 1}`) 등록.
3. **`0-B_regulatory_strategist`**: 안전등급(Class A/B/C), 타겟 국가, 적용 표준을 도출하여 `00_regulatory.json`(`REG-001`, `traces_to: {"INT-001": 1}`) 등록.
4. **`0-C_sdp_planner`**: 개발 언어, 커버리지 기준, 워크플로우 단계를 정의하여 `00_sdp_plan.json`(`SDP-001`, `traces_to: {"REG-001": 1}`) 등록.
5. **`0-D_stage0_auditor`**: 적합성 심사 후 `audit_findings.json`(`AUD-001`, `stage: "Stage 0"`, `verdict: "PASS"`) 등록.
6. **검문소 통과**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-stage 0
   ```

### Stage 1: 요구사항 명세(URS/SRS) & 위험·보안 피드백 루프
1. **`1-A_requirements_author` (초안)**: `01_urs.json`(`URS-xxx`) 및 `02_srs.json`(`SRS-xxx` 기능/성능 요구사항 초안) 등록. (활성 옵션이 있으면 `1-E_option_domain_author`가 `opt_*.json` 등록).
2. **`1-B_safety_risk_analyst`**: `rmf_safety.json`에 위해요인(`HAZ-SAF-xxx`)과 안전통제 대책(`RC-SAF-xxx`) 등록. *(절대 `02_srs.json`을 직접 수정하지 않음!)*
3. **`1-C_security_risk_analyst`**: `rmf_security.json`에 보안 위협(`HAZ-SEC-xxx`)과 보안통제 대책(`RC-SEC-xxx`, 안전 상충 검토 포함) 등록.
4. **`1-A_requirements_author` (피드백 반영)**: `RC-SAF-xxx` 및 `RC-SEC-xxx`를 입력으로 읽어 `02_srs.json`에 안전/보안 요구사항을 추가·갱신(`traces_to`에 `RC-*` 연결).
5. **`1-D_stage1_auditor`**: `audit_findings.json`(`stage: "Stage 1"`, `verdict: "PASS"`) 등록.
6. **검문소 통과**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-stage 1
   ```

### Stage 2: 아키텍처(SAD/SOUP) & 상세설계(SDS 시그니처 계약)
1. **`2-A_software_architect`**:
   - `03_sad_soup.json`에 모듈 아키텍처(`SAD-xxx`) 및 외부 패키지(`SOUP-xxx`) 등록.
   - `04_sds.json`에 블랙박스 시험용 엄격한 시그니처 계약(`SDS-xxx`: `target_file_path`, `callable_name`, `callable_signature`, `parameters_contract`, `return_contract`, `exception_contract`) 등록.
2. 필요 시 `2-B_dfmea_risk_analyst` / `2-C_threat_security_analyst`가 설계 결함 위험을 추가 도출하고 `1-A` $\rightarrow$ `2-A` 순으로 피드백 반영.
3. **`2-D_stage2_auditor`**: `audit_findings.json`(`stage: "Stage 2"`, `verdict: "PASS"`) 등록.
4. **검문소 통과**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-stage 2
   ```

### Stage 3: 소스코드 단위 구현 & AST 계약 검증
1. **`3-A_developer`**: `projects/<project_slug>/src/` 내에 `04_sds.json` 계약과 100% 일치하는 파이썬 코드를 구현합니다.
   - 반드시 함수 상단에 `# @traces: SDS-xxx@<최신버전>` 주석을 포함해야 합니다.
   - `TODO`, `FIXME`, `pass` 단독 본문, 미승인 SOUP `import`는 즉시 차단됩니다.
2. **AST 시그니처 검문**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-signatures
   ```
3. **`3-C_stage3_auditor`**: `audit_findings.json`(`stage: "Stage 3"`, `verdict: "PASS"`) 등록 후 `check-stage 3` 통과.

### Stage 4: V-모델 4계층 독립 검증(UT/IT/ST/VT) & 잔여위험 마감
1. **`4-A_blackbox_tester`**: `src/` 코드를 열람하지 않고 명세서(`04_sds`, `03_sad_soup`, `02_srs`, `01_urs`, `rmf_*`)만 보고 `05_tc.json`에 테스트 명세(`UT`, `IT`, `ST`, `VT` 및 `RC` 대상 `is_negative_test: true` 고장유도 시험)를 등록하고 `projects/<project_slug>/tests/test_*.py`를 작성합니다.
   - 주의: `05_tc.json`의 `test_callable_name`은 실제 `tests/test_*.py` AST 내 함수명과 정확히 일치해야 합니다.
2. **블랙박스 테스트 실행**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> run-tests
   ```
3. **`4-B_residual_risk_evaluator`**: 모든 테스트 `PASS` 확인 후 `rmf_safety.json` 및 `rmf_security.json`의 잔여위험(`residual_acceptable: true`)을 최종 마감합니다. (이로 인해 하위 항목이 Suspect가 되면 `RC` $\rightarrow$ `SRS` $\rightarrow$ `SAD/SDS` (`src/` `@traces` 버전 포함) $\rightarrow$ `TC` 순으로 버전을 동기화합니다.)
4. **`4-D_stage4_auditor`**: `audit_findings.json`(`stage: "Stage 4"`, `verdict: "PASS"`) 등록 후 `check-stage 4` 통과.

### Stage 5: 최종 SW 릴리즈 & 베이스라인 스냅샷 잠금
1. **`5-A_release_author`**: `06_release.json`에 `REL-xxx`(`baseline_id: "BL-xxx"`, `overall_residual_risk_acceptable: true`) 등록.
2. **`5-B_final_release_auditor`**: `audit_findings.json`(`stage: "Stage 5"`, `verdict: "PASS"`) 등록.
3. **`0_orchestrator` (베이스라인 생성)**:
   ```bash
   python3 dhf_cli.py -p projects/<project_slug> create-baseline --id BL-001 --stage "Stage 5 Release v1.0.0" --reason "Official Release Baseline"
   ```
4. **최종 Gate 검문 및 규제 보고서 렌더링**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-stage 5
   python3 dhf_cli.py -p projects/<project_slug> render-docs
   python3 dhf_cli.py -p projects/<project_slug> verify-history
   ```

---

## 3. 독립 제3자 감사관 서브에이전트 호출 (필수)

Stage 2 완료 시점 및 Stage 5 최종 릴리즈(또는 유지보수 릴리즈) 완료 시점에는 반드시 `invoke_subagent`를 호출하여 컨텍스트가 분리된 독립 감사관에게 `samd-independent-auditor` 스킬 기반의 전수 감사를 수행시키고 결과를 보고하십시오.
