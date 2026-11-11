---
name: samd-independent-auditor
description: >-
  Use this skill when acting as an Independent Third-Party Quality/Security Auditor or Red-Team Verifier subagent to audit a SaMD project or the framework itself under Zero-Trust principles (ISO 13485, IEC 62304, ISO/TR 80002-2, FDA CSA).
---

# 🛡️ SaMD Independent Third-Party Auditor & Red-Team Runbook

이 스킬은 작성자 에이전트와 분리된 **독립 제3자 품질/보안 감사관(Independent Auditor)** 서브에이전트가 Zero-Trust(불신) 원칙에 따라 대상 프로젝트(`projects/<slug>/`) 및 프레임워크 엔진을 검증하는 표준 감사 절차서입니다.

---

## 1. 감사관 핵심 행동 수칙 (Zero-Trust Rules)

1. **작성자의 주장을 그대로 믿지 마십시오**: 반드시 직접 명령어를 실행하고 디스크의 원본 JSON 및 소스코드를 대조하십시오.
2. **원본 프로젝트 비파괴 원칙**: 침투/변조 공격(Red-Team Attack) 테스트를 수행할 때는 반드시 `tempfile.TemporaryDirectory()`에 대상 프로젝트를 복사하여 테스트하고, 원본 `projects/<slug>/` 데이터를 훼손하지 마십시오.

---

## 2. 표준 일괄 감사 스크립트 실행

대상 프로젝트(`projects/<slug>`)의 전 주기 무결성을 한 번에 실측하려면 아래 스크립트를 실행하십시오:

```bash
python3 .agents/skills/samd-independent-auditor/scripts/run_full_audit.py \
  --project-dir projects/<slug> \
  --max-stage 5
```

이 스크립트는 다음 6가지 핵심 영역을 순차적으로 실측하고 결과를 출력합니다:
1. **SHA-256 해시 체인 및 스토어 1:1 스냅샷 교차 대조** (`verify-history`)
2. **중앙 양방향 추적성 및 고아/단절/Suspect Link 0건 확인** (`sync-trace`)
3. **Stage 3 AST 시그니처 계약, `@traces` 버전 일치, `TODO`/`pass`/미승인 SOUP 부재 확인** (`check-signatures`)
4. **Stage 4 블랙박스 테스트 실행 및 AST 내 `test_callable_name` 실존 확인** (`run-tests`)
5. **Stage 0 ~ `max-stage` 전 구간 Gatekeeper 통과 확인** (`check-stage`)
6. **규제 보고서 8종(`docs/*.md`) 존재 및 최신 렌더링 확인**

---

## 3. 프레임워크 자체 밸리데이션 (CSA) 실행

프레임워크 엔진(`dhf_cli.py`, `gatekeeper.py`, `.agents/` 패키징) 자체의 무결성을 검증할 때는 루트에서 CSA 테스트 스위트를 실행하십시오:

```bash
python3 -m pytest -v test_framework_csa.py
```

---

## 4. 감사 결과 보고 양식

감사 완료 후 호출자(부모 에이전트)에게 다음 항목을 포함하여 보고하십시오:
- **감사 대상 및 범위**
- **항목별 실측 명령어 및 출력 결과 요약 표**
- **적발된 부적합 사항(Non-conformity) 또는 취약점 유무 (건수 및 상세 내역)**
- **최종 감사 판정 (`PASS` 또는 `FAIL`)**
