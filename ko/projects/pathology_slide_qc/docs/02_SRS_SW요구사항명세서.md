# 📝 SW 요구사항 명세서 (Software Requirements Specification - IEC 62304 5.2)

| ID | 구분 | 제목 | 정량적 판정 기준 (Measurable Criteria) | 검증 방법 | 상위 연결 (URS/RC) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| SRS-001 | functional | 조직 영역 및 Artifact 분할 알고리즘 기능 요구 | 조직 영역 검출 Dice 계수 >= 0.90 달성 | system_test | URS-001@v2 |
| SRS-002 | safety | 저품질 슬라이드 판정 및 차단 안전 요구사항 | artifact_ratio > 0.20 일 때 status == LOW_QUALITY_REJECT 정확도 100% | system_test | URS-001@v2, RC-SAF-001@v4 |
| SRS-003 | security | 입력 이미지 파일 사전 유효성 및 보안 검증 요구사항 | 5GB 초과 파일 및 손상 파일 입력 시 ValueError 즉시 발생 | unit_test | URS-001@v2, RC-SEC-001@v4 |