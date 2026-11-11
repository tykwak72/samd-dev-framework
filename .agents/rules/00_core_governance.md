# SaMD DHF 데이터 무결성 및 단일 소유권 통제 규칙 (Core Governance Rule)

## 1. DHF Store 및 Docs 직접 수정 절대 금지
- `store/*.json`, `store/audit_history.jsonl`, `store/traceability.json`, `docs/*.md`는 SHA-256 해시 체인과 1:1 스냅샷 교차 대조(`verify_audit_history`)로 보호됩니다.
- `write_file`, `edit_file` 도구 또는 쉘 스크립트(`cat >`, `sed -i`, `python -c "json.dump(...)"`)를 사용하여 `store/` 내부 파일을 직접 덮어쓰지 마십시오.
- 반드시 아래 공식 CLI 또는 `DHFManager` API만 사용하십시오:
  - 초기화: `python3 dhf_cli.py -p projects/<slug> init`
  - 등록/수정: `python3 dhf_cli.py -p projects/<slug> put --file <filename> --actor <role_id> --reason "<사유>" --item-json '<json_or_path>'`
  - 베이스라인 스냅샷: `python3 dhf_cli.py -p projects/<slug> create-baseline --id BL-xxx --stage "Stage 5" --reason "<사유>"`
  - 추적성 동기화: `python3 dhf_cli.py -p projects/<slug> sync-trace`
  - 해시체인 & 스토어 교차 검증: `python3 dhf_cli.py -p projects/<slug> verify-history`
  - 규제 문서 렌더링: `python3 dhf_cli.py -p projects/<slug> render-docs`

## 2. Suspect Link (변경 영향도) 즉시 해소 원칙
- 상위 항목(예: `URS-001`)이 수정되어 버전(`v+1`)이 올라가면, 하위 참조 항목(`SRS`, `SAD`, `SDS`, `TC`, `HAZ/RC`, `AUD`)에 연쇄적으로 `is_suspect: true`가 전파됩니다.
- `suspect_links`가 단 1건이라도 남아 있으면 모든 Stage Gate가 차단됩니다.
- 변경 발생 시 반드시 영향받는 하위 문서들의 소유자 에이전트가 차례대로 새 상위 버전을 검토하고 `traces_to`의 버전 번호를 최신으로 갱신하여 `suspect_links == []` 상태를 복구해야 합니다.

## 3. 베이스라인 잠금 및 사후 유지보수(PR/CR) 통제 (IEC 62304 Clause 6, 8, 9)
- 최초 릴리즈(`REL-001`) 및 베이스라인(`BL-001`) 확정 이후에는 모든 핵심 DHF 산출물이 자동으로 잠깁니다(`Baseline Lock`).
- 릴리즈 이후 버그 수정이나 기능 업그레이드가 필요한 경우:
  1. `6-A_maintenance_change_analyst`가 `pr_cr_log.json`에 문제보고서(`PR-xxx`, `resolution_status: "OPEN"`)를 먼저 등록합니다.
  2. 이어서 `pr_cr_log.json`에 변경요청서(`CR-xxx`, `traces_to: {"PR-xxx": ver}`, `approval_status: "APPROVED"`, `impacted_item_ids: [...]`, `regression_test_ids: [...]`)를 등록해야만 잠금이 해제됩니다.
  3. 수정 및 회귀 테스트(`regression_test_ids` 전수 `PASS`) 완료 후, `PR-xxx`를 `"CLOSED"`로 갱신하고 신규 릴리즈(`REL-xxx`) 및 신규 베이스라인(`BL-xxx`)을 생성하여 재잠금합니다.
