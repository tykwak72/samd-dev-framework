# 🏗️ SW 아키텍처 및 상세설계 명세서 (IEC 62304 5.3 & 5.4)

## 1. 아키텍처 모듈 및 SOUP 목록
### [모듈] SAD-001: SlidePreprocessor (Class: Class B)
- **책임**: 입력 검증, 조직 마스킹, artifact 비율 산출, 품질 판정 결과 객체 반환
- **격리 전략**: 후속 암 진단 AI 모델 파이프라인과 API 경계로 분리하여 저품질 슬라이드 유입 원천 차단

### [SOUP] SOUP-001: Pillow (10.2.0)
- **라이선스**: HPND
- **위험 통제 정당화**: SRS-003에 정의된 파일 크기 상한 검사로 버퍼오버플로 사전 차단

## 2. 상세 설계 및 함수 시그니처 계약 (SDS)
### [SDS-001] preprocess_pathology_slide (src/slide_preprocessor.py)
- **시그니처**: `def preprocess_pathology_slide(image_path: str, artifact_threshold: float = 0.20) -> dict`
- **파라미터 계약**: `[{"name": "image_path", "type": "str"}, {"name": "artifact_threshold", "type": "float"}]`
- **예외 계약**: `[{"exception_type": "FileNotFoundError", "condition": "파일 미존재 시"}, {"exception_type": "ValueError", "condition": "파일 크기 5GB 초과 또는 손상 시"}]`
- **알고리즘 명세**: 1. 파일 사전검증 -> 2. 이미지 로드 -> 3. 조직 분할 마스크 -> 4. 고농도 접힘 및 RGB 고채도 유색 펜마킹 artifact 마스크 -> 5. 비율 계산 -> 6. status 결정
