# 🧪 SW 검증 결과 및 릴리즈/유지보수 보고서 (V&V, Release & Maintenance - IEC 62304 5.5~5.8, 6, 8, 9)

## 1. V-모델 4계층 시험 결과 (UT / IT / ST / VT)
| ID | 계층 (Level) | 테스트 명칭 | 대상 파일 | 음성/고장유도 | 실행 상태 | 상위 검증 대상 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| UT-001 | UT | 정상 병리 슬라이드 조직 분할 및 PASS 상태 검증 | tests/test_ut_preprocessor.py | False | **PASS** | SDS-001@v4 |
| UT-002 | UT | 비정상/손상/미존재 파일 입력 시 보안 예외 처리 검증 | tests/test_ut_preprocessor.py | True | **PASS** | RC-SEC-001@v4 |
| IT-001 | IT | SlidePreprocessor 모듈과 Pillow 디코더 인터페이스 연동 검증 | tests/test_it_integration.py | False | **PASS** | SAD-001@v4 |
| ST-001 | ST | 전체 슬라이드 조직 영역 분할 및 정량 성능 검증 | tests/test_st_system.py | False | **PASS** | SRS-001@v3 |
| ST-002 | ST | Artifact 20% 초과 저품질 슬라이드 강제 차단 고장유도 시험 | tests/test_st_system.py | True | **PASS** | SRS-002@v5, RC-SAF-001@v4 |
| VT-001 | VT | 병리전문의 사용적합성 및 임상 유효성 밸리데이션 | docs/VT_수동시험체크리스트.md | False | **PASS** | URS-001@v2 |
| ST-003 | ST | 입력 파일 보안 및 손상 방어 시스템 시험 | tests/test_st_system.py | True | **PASS** | SRS-003@v5, RC-SEC-001@v4 |

## 2. 형상관리 베이스라인 이력 (Configuration Baselines - Clause 8.1)
| Baseline ID | 단계/버전명 | 스냅샷 해시 | 잠금 항목 수 | 생성 시각 |
| :--- | :--- | :--- | :--- | :--- |
| BL-001 | Release 1.0.0 | `aee90f38845b87db...` | 29개 | 2026-11-09T14:45:06.496235+00:00 |
| BL-002 | Release 1.0.1 | `cd394738675fc322...` | 32개 | 2026-11-09T14:48:33.489036+00:00 |

## 3. 문제해결 및 변경통제 이력 (PR / CR Log - Clause 6, 8.2, 9)
| ID | 유형 | 제목 | 영향 항목 / 원인 | 회귀시험 / 상태 | 상위 연결 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| PR-001 | PR | 고채도 청색/녹색 병리사 펜 마킹 영역 미배제 현장 문제 보고 | clinical_field_feedback (펜 마킹이 조직 면적에 포함될 경우 실제 유효 조직 대비 artifact 비율 왜곡 우려 (안전성 영향 있음)) | **CLOSED** | REL-001@v2 |
| CR-001 | CR | RGB 채도 기반 유색 펜 마킹 Artifact 검출 알고리즘 추가 변경요청 | 영향: SRS-001, SAD-001, SDS-001 | 회귀: UT-001, UT-002, IT-001, ST-001, ST-002, ST-003, VT-001 (**APPROVED**) | PR-001@v2 |

## 4. 공식 SW 릴리즈 이력 (Software Releases - Clause 5.8)
| ID | 릴리즈 버전 | 기준선 (Baseline) | 잔여위험 허용 | 잔여 결함 수 |
| :--- | :--- | :--- | :--- | :--- |
| REL-001 | **v1.0.0** | BL-001 | True | 0건 |
| REL-002 | **v1.0.1** | BL-002 | True | 0건 |