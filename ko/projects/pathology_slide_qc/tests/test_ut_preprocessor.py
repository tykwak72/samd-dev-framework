"""
test_ut_preprocessor.py - 단위 검증 (IEC 62304 5.5) 및 사이버보안 고장유도 시험
# @verifies: SDS-001, RC-SEC-001
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

# 타겟 모듈 임포트
from src.slide_preprocessor import preprocess_pathology_slide


class TestUnitSlidePreprocessor(unittest.TestCase):
    """단위 수준 기능 검증 및 보안 경계값 검증"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_preprocess_normal_slide(self):
        """정상 H&E 슬라이드 이미지에 대한 단위 검증 (UT-001)"""
        slide_path = self.test_dir / "normal_slide.png"
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        for x in range(20, 80):
            for y in range(20, 80):
                img.putpixel((x, y), (180, 120, 160))
        img.save(slide_path)

        result = preprocess_pathology_slide(str(slide_path), artifact_threshold=0.20)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["is_usable"])
        self.assertGreater(result["tissue_area_px"], 0)
        self.assertLessEqual(result["artifact_ratio"], 0.20)

    def test_security_negative_file_checks(self):
        """사이버보안 고장유도 음성 시험 (UT-002: RC-SEC-001 검증)"""
        # 1. 미존재 파일
        non_existent = str(self.test_dir / "missing.png")
        with self.assertRaises(FileNotFoundError):
            preprocess_pathology_slide(non_existent)

        # 2. 0바이트 손상 파일
        empty_file = self.test_dir / "corrupted_empty.png"
        empty_file.touch()
        with self.assertRaises(ValueError):
            preprocess_pathology_slide(str(empty_file))

        # 3. 비정상 바이너리 헤더 손상 파일
        corrupted_file = self.test_dir / "corrupted_header.png"
        with open(corrupted_file, "wb") as f:
            f.write(b"NOT_A_VALID_IMAGE_HEADER_FAKE_DATA")
        with self.assertRaises(ValueError):
            preprocess_pathology_slide(str(corrupted_file))


if __name__ == "__main__":
    unittest.main()
