"""
slide_preprocessor.py - 디지털 병리 WSI 조직 영역 검출 및 품질관리 전처리 컴포넌트

IEC 62304 Class B 규격 준수 구현
"""

import os
from pathlib import Path
from typing import Dict, Any
from PIL import Image

# 최대 허용 파일 크기 (5GB = 5 * 1024 * 1024 * 1024 bytes)
MAX_ALLOWED_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024

# 슬라이드 배경(유리) 밝기 임계값 (H&E 배경은 220 이상의 밝은 백색에 가까움)
BACKGROUND_BRIGHTNESS_THRESHOLD = 220

# 조직 접힘/기포/마킹 등 artifact 판정용 색상/밝기 기준치
# 기포(어둡거나 굴절 테두리), 접힘(과도하게 짙은 농도 40 이하)
ARTIFACT_DENSE_THRESHOLD = 40

# 병리사 유색 펜 마킹(청색/녹색 잉크 등 비조직 고채도 마킹) 채도 임계값 (v1.0.1 PR-001/CR-001 반영)
PEN_INK_SATURATION_THRESHOLD = 120


# @traces: SDS-001@4
def preprocess_pathology_slide(image_path: str, artifact_threshold: float = 0.20) -> dict:
    """
    디지털 병리 슬라이드 이미지를 전처리하여 조직 영역 및 artifact 영역을 분할하고,
    artifact 비율에 따라 슬라이드 품질 적합성 상태를 판정함.

    Parameters:
        image_path (str): 입력 슬라이드 이미지 파일 경로
        artifact_threshold (float): 저품질 판정 기준 artifact 비율 (기본값 0.20 = 20%)

    Returns:
        dict: {
            "status": "PASS" | "LOW_QUALITY_REJECT",
            "tissue_area_px": int,
            "artifact_area_px": int,
            "artifact_ratio": float,
            "is_usable": bool
        }

    Raises:
        FileNotFoundError: 파일이 디스크에 존재하지 않을 때
        ValueError: 파일 크기가 5GB를 초과하거나 손상/비정상 파일일 때
    """
    target_path = Path(image_path)

    # 1. 파일 존재 여부 검증 (SRS-003 보안 요구사항)
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"Slide image not found at path: {image_path}")

    # 2. 파일 크기 상한 검증 (SRS-003 / RC-SEC-001 DoS 방어)
    file_size = target_path.stat().st_size
    if file_size <= 0:
        raise ValueError(f"Empty or corrupted slide file (size 0 bytes): {image_path}")
    if file_size > MAX_ALLOWED_FILE_SIZE_BYTES:
        raise ValueError(f"Slide file size ({file_size} bytes) exceeds maximum limit (5GB)")

    # 3. 이미지 디코딩 및 무결성 검증 (SOUP-001 Pillow 활용)
    try:
        with Image.open(target_path) as img:
            img.verify()
    except Exception as exc:
        raise ValueError(f"Corrupted or invalid image header in '{image_path}': {exc}") from exc

    try:
        with Image.open(target_path) as img:
            rgb_img = img.convert("RGB")
            width, height = rgb_img.size
            pixels = list(rgb_img.getdata())
    except Exception as exc:
        raise ValueError(f"Failed to decode image raster data in '{image_path}': {exc}") from exc

    total_pixels = width * height
    if total_pixels == 0:
        raise ValueError(f"Image has invalid dimensions: {width}x{height}")

    # 4. 조직 분할 및 Artifact 영역 검출 (SRS-001 알고리즘)
    # H&E 염색: 배경(밝음), 생체조직(중간 보라/분홍), Artifact(접힘은 매우 어두움, 기포는 불균일)
    tissue_area_px = 0
    artifact_area_px = 0

    for r, g, b in pixels:
        brightness = (r + g + b) // 3
        # 배경(유리 슬라이드) 배제
        if brightness >= BACKGROUND_BRIGHTNESS_THRESHOLD:
            continue

        # 유효 생체 조직 검출
        tissue_area_px += 1

        # 접힘(Folded tissue) 또는 과도한 마킹/기포 등 artifact 검출
        # v1.0.1 (CR-001): 고채도 청색/녹색 병리사 펜 마킹(Pen Ink) 검출 조건 추가
        color_spread = max(r, g, b) - min(r, g, b)
        is_colored_pen_ink = (
            color_spread >= PEN_INK_SATURATION_THRESHOLD and (b > r + 40 or g > r + 40)
        )
        if brightness <= ARTIFACT_DENSE_THRESHOLD or is_colored_pen_ink:
            artifact_area_px += 1

    # 유효 조직 면적이 전혀 없는 빈 슬라이드 처리
    if tissue_area_px == 0:
        artifact_ratio = 1.0
        status = "LOW_QUALITY_REJECT"
        is_usable = False
    else:
        # artifact 비율 계산 (SRS-002)
        artifact_ratio = round(artifact_area_px / tissue_area_px, 4)

        # 5. 슬라이드 품질 적합성 판정 (RC-SAF-001 / SRS-002 안전 통제 대책)
        if artifact_ratio > artifact_threshold:
            status = "LOW_QUALITY_REJECT"
            is_usable = False
        else:
            status = "PASS"
            is_usable = True

    return {
        "status": status,
        "tissue_area_px": tissue_area_px,
        "artifact_area_px": artifact_area_px,
        "artifact_ratio": artifact_ratio,
        "is_usable": is_usable
    }
