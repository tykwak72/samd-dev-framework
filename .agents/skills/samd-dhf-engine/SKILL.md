---
name: samd-dhf-engine
description: >-
  Use this skill when interacting with dhf_cli.py or gatekeeper.py to create/update DHF items, resolve Suspect Links, manage configuration baselines (BL-xxx), or execute post-release maintenance (PR-xxx / CR-xxx). Provides CLI commands and references the complete 18-file schema and single-ownership mapping.
---

# ⚙️ SaMD DHF CLI & Gatekeeper Engine Skill

이 스킬은 `dhf_cli.py`와 `gatekeeper.py`를 사용하여 DHF 항목을 안전하게 등록·수정하고, 추적성(Suspect Link) 및 베이스라인 잠금(`BL-xxx`)·유지보수(`PR/CR`)를 관리하는 기술 매뉴얼입니다.

상세 파일별 독점 소유자(`actor`) ID와 필수 스키마 필드는 반드시 [references/schema_and_owners.md](references/schema_and_owners.md)를 확인하십시오.

---

## 1. `dhf_cli.py` 핵심 명령어

모든 명령은 `-p projects/<project_slug>` 옵션을 포함해야 합니다.

### 1.1 항목 등록 및 수정 (`put`)
```bash
python3 dhf_cli.py -p projects/<slug> put \
  --file <store_filename.json> \
  --actor <authorized_actor_role> \
  --reason "<변경 사유>" \
  --item-json '<JSON_문자열_또는_임시JSON파일경로>'
```
- **주의**: 이미 존재하는 `id`를 `put`하면 엔진이 자동으로 `version`을 `old_version + 1`로 증가시키고 `audit_history.jsonl`에 SHA-256 해시 체인을 기록하며 `traceability.json`을 즉시 동기화합니다.

### 1.2 항목 조회 (`get`)
```bash
python3 dhf_cli.py -p projects/<slug> get --id <ITEM_ID>
```

### 1.3 양방향 추적성 동기화 및 Suspect Link 확인 (`sync-trace`)
```bash
python3 dhf_cli.py -p projects/<slug> sync-trace
```

### 1.4 베이스라인 스냅샷 생성 및 잠금 (`create-baseline`)
```bash
python3 dhf_cli.py -p projects/<slug> create-baseline \
  --id BL-001 \
  --stage "Stage 5 Release v1.0.0" \
  --actor 0_orchestrator \
  --reason "Lock baseline for Release v1.0.0"
```

### 1.5 감사 해시 체인 및 스토어 1:1 교차 검증 (`verify-history`)
```bash
python3 dhf_cli.py -p projects/<slug> verify-history
```

### 1.6 심사관용 마크다운 보고서 8종 렌더링 (`render-docs`)
```bash
python3 dhf_cli.py -p projects/<slug> render-docs
```

---

## 2. `gatekeeper.py` 핵심 명령어

```bash
# Stage 0 ~ 5 Gate 검문소 실행
python3 gatekeeper.py -p projects/<slug> check-stage <0|1|2|3|4|5>

# Stage 3 소스코드 AST 시그니처 및 품질(TODO, pass, 미승인 SOUP) 검사
python3 gatekeeper.py -p projects/<slug> check-signatures

# Stage 4 독립 블랙박스 테스트 실행 및 05_tc.json 결과 업데이트
python3 gatekeeper.py -p projects/<slug> run-tests
```

---

## 3. 사후 유지보수 및 변경관리 (IEC 62304 Clause 6, 8.2, 9) 절차

`create-baseline`으로 베이스라인(`BL-001`)이 생성된 후에는 `01_urs.json` ~ `05_tc.json`, `rmf_*.json`이 모두 잠깁니다(`Baseline Lock`).
릴리즈 후 결함 수정이나 변경을 수행하려면 반드시 아래 순서를 따르십시오:

1. **문제보고서(`PR-xxx`) 발행**:
   - 소유자: `6-A_maintenance_change_analyst` (또는 `4-C_maintenance_change_analyst`)
   - 파일: `pr_cr_log.json`
   - 필수 상태: `"resolution_status": "OPEN"`, `"traces_to": {"REL-001": <ver>}`
2. **변경요청서(`CR-xxx`) 발행 및 승인**:
   - 소유자: `6-A_maintenance_change_analyst`
   - 파일: `pr_cr_log.json`
   - 필수 설정:
     - `"traces_to": {"PR-001": <ver>}`
     - `"approval_status": "APPROVED"`
     - `"impacted_item_ids": ["SRS-001", "SAD-001", "SDS-001", ...]` (직접 수정할 항목 ID 목록)
     - `"regression_test_ids": ["UT-001", "ST-001", ...]` (수행할 회귀 테스트 ID 목록)
3. **영향 범위 항목 및 소스코드 수정**:
   - 각 문서 소유자가 `impacted_item_ids` 및 연쇄 발생한 `Suspect Link` 항목들을 상위$\rightarrow$하위 순서로 갱신.
   - `src/` 코드의 `# @traces: SDS-xxx@<신규버전>` 주석도 최신 SDS 버전과 일치하도록 업데이트.
4. **회귀 테스트 실행 및 재감사**:
   - `gatekeeper.py run-tests` 실행 (`regression_test_ids` 전수 `PASS` 필수).
   - 영향을 받은 Stage 감사(`AUD-xxx`) 갱신.
5. **`PR-xxx` 마감 및 신규 릴리즈/베이스라인 확정**:
   - `PR-xxx`의 `resolution_status`를 `"CLOSED"`로 업데이트하고 `CR-xxx`의 `traces_to`를 최신 `PR-xxx` 버전으로 동기화.
   - `06_release.json`에 신규 `REL-002`(`baseline_id: "BL-002"`) 등록 및 Stage 5 감사(`AUD-xxx`) 승인.
   - `create-baseline --id BL-002` 실행하여 재잠금 후 `check-stage 5` 및 `render-docs` 실행.
