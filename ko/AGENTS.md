# 🏥 Antigravity SaMD / 의료기기 SW 개발 멀티에이전트 프레임워크 헌법 (AGENTS.md)

본 워크스페이스(`/root/workspace/samd-dev-framework`)는 **IEC 62304, ISO 14971, ISO 13485(4.1.6), IEC 82304-1, IEC 81001-5-1, ISO/TR 80002-2 및 FDA CSA**를 준수하는 범용 의료기기 소프트웨어(SaMD/SiMD) 개발 프레임워크입니다.

이 워크스페이스에서 활동하는 모든 에이전트(총괄 공장장, 단계별 작성 에이전트, 위험/보안 분석가, 블랙박스 테스터, 독립 감사관)는 아래 **5대 절대 헌법**을 예외 없이 준수해야 합니다.

---

## 1. 5대 절대 헌법 (Core Invariants)

1. **프로젝트 샌드박스 격리 원칙 (Strict Project Isolation)**
   - 프레임워크 루트(`/root/workspace/samd-dev-framework`)에는 오직 프레임워크 코어 엔진(`dhf_cli.py`, `gatekeeper.py`, `test_framework_csa.py`), 마스터 설계서(`BLUEPRINT.md`, `ROADMAP.md`, `SCHEMA_SPEC.md`), 그리고 `.agents/` 설정만 존재해야 합니다.
   - 사용자의 모든 의료기기 개발 의뢰는 반드시 **`projects/<project_slug>/`** 하위 디렉토리에 독립된 샌드박스(`store/`, `docs/`, `src/`, `tests/`)로 격리하여 생성·진행해야 합니다.
   - 모든 CLI 명령 실행 시 반드시 `-p projects/<project_slug>` 옵션을 지정하십시오.

2. **결정론적 CLI 강제 및 직접 파일 변조 금지 (No Direct Store Manipulation)**
   - `projects/<project_slug>/store/*.json`, `audit_history.jsonl`, `traceability.json`, `docs/*.md` 파일을 텍스트 도구(`write_file`, `edit_file`)나 쉘 리다이렉션으로 **직접 수정하는 것은 엄격히 금지**됩니다 (`.agents/hooks/pre_tool_guard.py`에 의해 즉시 차단되며, `verify-history` 교차 대조에서 적발됩니다).
   - 모든 항목의 생성·수정·버전업·렌더링은 오직 **`python3 dhf_cli.py -p projects/<project_slug> ...`**를 통해서만 수행해야 합니다.

3. **단일 소유권 원칙 (Strict Single Ownership) & 피드백 루프**
   - 각 DHF JSON 파일은 [`SCHEMA_SPEC.md`](file:///root/workspace/samd-dev-framework/SCHEMA_SPEC.md)에 정의된 독점 소유자(`actor`)만 수정할 수 있습니다:
     - `00_intake.json`: `0-0_intake_agent`
     - `00_literature.json`: `0-A_literature_researcher`
     - `00_regulatory.json`: `0-B_regulatory_strategist`
     - `00_sdp_plan.json`: `0-C_sdp_planner`, `0_orchestrator`
     - `01_urs.json`, `02_srs.json`: `1-A_requirements_author`
     - `opt_*.json`: `1-E_option_domain_author`
     - `03_sad_soup.json`, `04_sds.json`: `2-A_software_architect`
     - `src/` 소스코드: `3-A_developer`
     - `05_tc.json`, `tests/`: `4-A_blackbox_tester`
     - `06_release.json`: `5-A_release_author`
     - `rmf_safety.json`: `1-B_safety_risk_analyst`, `2-B_dfmea_risk_analyst`, `3-B_code_safety_analyst`, `4-B_residual_risk_evaluator`
     - `rmf_security.json`: `1-C_security_risk_analyst`, `2-C_threat_security_analyst`, `3-B_code_safety_analyst`, `4-B_residual_risk_evaluator`
     - `audit_findings.json`: `0-D_stage0_auditor`, `1-D_stage1_auditor`, `2-D_stage2_auditor`, `3-C_stage3_auditor`, `4-D_stage4_auditor`, `5-B_final_release_auditor`
     - `cm_baselines.json`: `0_orchestrator` (`create-baseline`)
     - `pr_cr_log.json`: `6-A_maintenance_change_analyst`, `4-C_maintenance_change_analyst`
   - 위험 분석가(`1-B`, `1-C`)나 감사관(`*-D`)은 절대 요구사항이나 설계서를 직접 고치지 않고 자신의 출력 파일(`rmf_*.json`, `audit_findings.json`)만 갱신하며, 문서 주인(`1-A`, `2-A`, `3-A`, `4-A`)이 이를 입력으로 읽어서 자신의 문서를 수정(버전 `v+1`)합니다.

4. **블랙박스 V&V 격리 및 AST 시그니처 계약 (Black-box Isolation & AST Contract)**
   - `2-A(아키텍트)`는 `04_sds.json`에 정확한 `target_file_path`, `callable_name`, `callable_signature`, `parameters_contract`, `return_contract`, `exception_contract`를 명시해야 합니다.
   - `3-A(개발자)`는 `src/` 코드 상단에 `# @traces: SDS-xxx@<현재버전>` 주석을 달고 시그니처를 100% 일치시켜야 하며, `TODO`/`FIXME`, `pass` 단독 본문, 미승인 SOUP `import`는 금지됩니다.
   - `4-A(블랙박스 테스터)`는 **`src/` 소스코드를 열람하지 않고** 오직 `04_sds.json` 및 상위 명세서만 보고 테스트 코드를 작성합니다.

5. **단계별 Gatekeeper 검문 및 독립 서브에이전트 감사 (Zero-Trust Independent Audit)**
   - 각 Stage(0~5) 종료 시 반드시 `python3 gatekeeper.py -p projects/<project_slug> check-stage <0~5>`를 통과해야 합니다.
   - 주요 마일스톤 완료 또는 릴리즈/유지보수 완료 시, 작성자의 편향(Context Bias)을 배제하기 위해 반드시 **`invoke_subagent`를 통해 컨텍스트가 분리된 독립 감사관 서브에이전트**를 기동하여 제3자 감사를 수행하고 `PASS`를 확인해야 합니다.

---

## 2. 전문 스킬(Skills) 활용 안내

작업 성격에 따라 `.agents/skills/`에 탑재된 다음 스킬의 `SKILL.md`를 읽고 절차를 따르십시오:
- **`samd-orchestrator`**: 신규 의료기기 개발 의뢰 접수부터 Stage 0~5 전 주기 실행 및 사후 유지보수(PR/CR) 오케스트레이션 절차
- **`samd-dhf-engine`**: `dhf_cli.py` 및 `gatekeeper.py` 상세 CLI 명령어, 18개 JSON 파일 스키마 치트시트, Suspect Link 해소 및 베이스라인 잠금 관리법
- **`samd-independent-auditor`**: 독립 제3자 품질/보안 감사관 및 적대적(Red-Team) 검증 서브에이전트용 표준 감사 런북
