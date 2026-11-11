# IEC 62304 V-모델 Stage 0~5 Gate 합격 기준 규칙 (V-Model Stage Gates Rule)

모든 프로젝트(`projects/<slug>/`)는 각 Stage 완료 시 `python3 gatekeeper.py -p projects/<slug> check-stage <0~5>`를 실행하여 아래 기준을 100% 통과해야 다음 단계로 진행할 수 있습니다.

## 1. 공통 Gate 관문 (전 Stage 필수)
- `verify_audit_history()` == `True` (SHA-256 해시 체인 및 `store/*.json` 1:1 스냅샷 무결성 100% 일치)
- `broken_links == []` (존재하지 않는 상위 ID 참조 0건)
- `suspect_links == []` (상위 버전 변경 후 미검토된 하위 항목 0건)

## 2. 단계별 대칭 검증 기준
- **Stage 0 Gate (기획 & 수행계획)**:
  - `INT` $\rightarrow$ `LIT` 및 `REG` 하향 연결 완비
  - `REG` $\rightarrow$ `SDP` 하향 연결 완비
  - `audit_findings.json` 내 `stage == "Stage 0"` 감사 판정 `verdict == "PASS"`
- **Stage 1 Gate (요구사항 & 초기 위험/보안 분석)**:
  - `INT` $\rightarrow$ `URS` $\rightarrow$ `SRS` 하향 연결 완비
  - 모든 `HAZ-SAF`(`control_required=True`) $\rightarrow$ `RC-SAF` $\rightarrow$ `SRS` 반영 완료
  - 모든 `HAZ-SEC` $\rightarrow$ `RC-SEC` $\rightarrow$ `SRS` 반영 완료
  - `stage == "Stage 1"` 감사 판정 `PASS`
- **Stage 2 Gate (아키텍처 & 상세설계 시그니처 계약)**:
  - 모든 `SRS` $\rightarrow$ `SAD` 및 `SDS` 하향 연결 완비
  - 모든 `SDS`에 `target_file_path`, `callable_name`, `callable_signature`, `parameters_contract`, `return_contract`, `exception_contract` 완비
  - `stage == "Stage 2"` 감사 판정 `PASS`
- **Stage 3 Gate (소스코드 단위 구현 & AST 검증)**:
  - `gatekeeper.py check-signatures` 통과 필수
  - `src/` 코드 내 `# @traces: SDS-xxx@<최신버전>` 주석의 정확한 버전 일치
  - Python AST 파싱 기준 함수/클래스명 및 파라미터 순서·이름 100% 일치
  - `TODO`/`FIXME`/`TBD`/`XXX` 주석 0건, 빈 함수/`pass` 단독/`NotImplementedError` 0건
  - `03_sad_soup.json`에 등록되지 않은 외부 서드파티 패키지 `import` 0건
  - `stage == "Stage 3"` 감사 판정 `PASS`
- **Stage 4 Gate (V-모델 4계층 독립 검증 & 잔여위험 마감)**:
  - `05_tc.json`에 등록된 모든 자동화 테스트의 `test_callable_name`이 실제 `tests/*.py` AST 내에 존재하고 실행 결과 `PASS`
  - 4계층 대칭 커버리지: $\forall \text{SDS} \Rightarrow \text{UT(PASS)}$, $\forall \text{SAD} \Rightarrow \text{IT(PASS)}$, $\forall \text{SRS} \Rightarrow \text{ST(PASS)}$, $\forall \text{URS} \Rightarrow \text{VT(PASS)}$
  - 위험통제 고장유도 시험: $\forall (\text{RC-SAF}, \text{RC-SEC}) \Rightarrow \text{Negative Test (is\_negative\_test=True, PASS)}$
  - 모든 `HAZ-SAF`, `HAZ-SEC`의 잔여위험 허용(`residual_acceptable == True`) 마감
  - `stage == "Stage 4"` 감사 판정 `PASS`
- **Stage 5 Gate (최종 SW 릴리즈 & 베이스라인 잠금)**:
  - `uncovered_items == []` (고아 항목 0건)
  - `06_release.json` 내 최신 `REL-xxx`의 `overall_residual_risk_acceptable == True`
  - 최신 `REL-xxx`가 참조하는 `baseline_id`(`BL-xxx`)가 `cm_baselines.json`에 실존하고 모든 활성 항목의 최신 버전과 100% 일치
  - 모든 `AUD-xxx` 및 `PR-xxx`가 `CLOSED` (또는 `DEFERRED` 시 `known_remaining_anomalies`에 안전성 정당화 등재)
  - `stage == "Stage 5"` 감사 판정 `PASS`
