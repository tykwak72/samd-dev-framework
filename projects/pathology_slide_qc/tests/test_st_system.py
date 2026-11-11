"""
test_st_system.py - 시스템 시험 (IEC 62304 5.7) 및 위험통제 고장유도 시험
# @verifies: SRS-001, RC-SAF-001
"""

import os
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from src.slide_preprocessor import preprocess_pathology_slide


class TestSystemSlidePreprocessor(unittest.TestCase):
    """시스템 수준 기능 검증 및 위험통제 고장유도 검증"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_system_requirements_coverage(self):
        """시스템 레벨 조직 분할 기능 및 반환 스키마 전수 검증 (ST-001: SRS-001 검증)"""
        slide_path = self.test_dir / "system_test_slide.png"
        img = Image.new("RGB", (80, 80), color=(240, 240, 240))
        for x in range(10, 70):
            for y in range(10, 70):
                img.putpixel((x, y), (160, 110, 150))
        img.save(slide_path)

        res = preprocess_pathology_slide(str(slide_path), artifact_threshold=0.20)

        self.assertIn("status", res)
        self.assertIn("tissue_area_px", res)
        self.assertIn("artifact_area_px", res)
        self.assertIn("artifact_ratio", res)
        self.assertIn("is_usable", res)
        self.assertEqual(res["status"], "PASS")

    def test_fault_injection_high_artifact_rejection(self):
        """위험통제 고장유도 시험 (ST-002: RC-SAF-001 검증)
        조직 접힘/기포/마킹 등 artifact가 20%를 초과할 경우 시스템이 반드시
        LOW_QUALITY_REJECT 상태를 반환하고 is_usable=False 처리하는지 검증
        """
        bad_slide_path = self.test_dir / "bad_artifact_slide.png"
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))

        # 전체 유효 조직 2500px 생성
        for x in range(25, 75):
            for y in range(25, 75):
                img.putpixel((x, y), (180, 130, 170))

        # 그 중 35%에 해당하는 900px를 심각한 artifact(접힘/검은 마킹: (20, 20, 20))로 채움
        for x in range(35, 65):
            for y in range(35, 65):
                img.putpixel((x, y), (20, 20, 20))

        img.save(bad_slide_path)

        res = preprocess_pathology_slide(str(bad_slide_path), artifact_threshold=0.20)

        # 안전 통제 검증: artifact 비율이 20%를 초과하여 자동 차단되어야 함
        self.assertGreater(res["artifact_ratio"], 0.20)
        self.assertEqual(res["status"], "LOW_QUALITY_REJECT")
        self.assertFalse(res["is_usable"])

        # v1.0.1 회귀 검증(CR-001): 고채도 청색 병리사 펜 마킹((10, 30, 220))이 20%를 초과하는 슬라이드도 차단되는지 검증
        pen_slide_path = self.test_dir / "colored_pen_artifact_slide.png"
        pen_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        for x in range(25, 75):
            for y in range(25, 75):
                pen_img.putpixel((x, y), (180, 130, 170))
        for x in range(35, 65):
            for y in range(35, 65):
                pen_img.putpixel((x, y), (10, 30, 220))
        pen_img.save(pen_slide_path)

        pen_res = preprocess_pathology_slide(str(pen_slide_path), artifact_threshold=0.20)
        self.assertGreater(pen_res["artifact_ratio"], 0.20)
        self.assertEqual(pen_res["status"], "LOW_QUALITY_REJECT")
        self.assertFalse(pen_res["is_usable"])

    def test_security_negative_file_checks(self):
        """시스템 수준 입력 파일 보안 및 손상 방어 시험 (ST-003: SRS-003, RC-SEC-001 검증)"""
        non_existent = str(self.test_dir / "sys_missing.png")
        with self.assertRaises(FileNotFoundError):
            preprocess_pathology_slide(non_existent)

        corrupted_file = self.test_dir / "sys_corrupted.png"
        with open(corrupted_file, "wb") as f:
            f.write(b"INVALID_WSI_PAYLOAD")
        with self.assertRaises(ValueError):
            preprocess_pathology_slide(str(corrupted_file))


if __name__ == "__main__":
    unittest.main()
