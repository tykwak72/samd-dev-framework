# 🛡️ 통합 위험 및 사이버보안 관리 보고서 (ISO 14971 & IEC 81001-5-1)

## 1. 안전 위험 관리 (Safety Hazard & Risk Control)
| ID | 유형 | 위해/통제 내용 | 초기위험 (S/P/R) | 잔여위험 (S/P/R) | 허용 여부 | 상위/하위 연결 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| HAZ-SAF-001 | HAZARD | 위음성으로 인한 악성 종양 환자의 치료 시기 상실 및 사망 초래 | 4/3/12 | 2/1/2 | True | SRS-001@v3 |
| RC-SAF-001 | CONTROL (1_inherent_safety) | if artifact_ratio > 0.20: return status=LOW_QUALITY_REJECT | - | - | DESIGNED | HAZ-SAF-001@v4 |

## 2. 사이버보안 위협 모델링 및 통제 (Cybersecurity)
| ID | STRIDE / 유형 | 위협 시나리오 / 통제 대책 | 환자 안전 영향 | 안전 상충 검토 (Safety Trade-off) |
| :--- | :--- | :--- | :--- | :--- |
| HAZ-SEC-001 | Denial of Service | 손상된 헤더를 가진 거대 이미지 로딩 시 OOM 충돌 | 응급 환자 검체 분석 불가 | - |
| RC-SEC-001 | CONTROL (input_validation) | 파일 크기 및 확장자/헤더 사전 검증 후 안전 로더 호출 | - | 0.05초 사전 검사 지연은 임상 긴급성에 전혀 영향 없음 |