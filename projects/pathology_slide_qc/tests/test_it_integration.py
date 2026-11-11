"""
test_it_integration.py - 모듈 통합 시험 (IEC 62304 5.6)
# @verifies: SAD-001, SOUP-001
"""

import os
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from src.slide_preprocessor import preprocess_pathology_slide


class TestIntegrationSlidePreprocessor(unittest.TestCase):
    """SlidePreprocessor 아키텍처 모듈과 Pillow 라이브러리 연동 검증 (IT-001)"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_slide_preprocessor_pipeline(self):
        """다양한 형식(PNG, TIFF)의 슬라이드 디코딩 및 인터페이스 연동 검증"""
        # TIFF 슬라이드 생성
        tiff_path = self.test_dir / "sample_slide.tiff"
        img = Image.new("RGB", (120, 120), color=(250, 250, 250))
        for x in range(30, 90):
            for y in range(30, 90):
                img.putpixel((x, y), (170, 100, 150))
        img.save(tiff_path, format="TIFF")

        res = preprocess_pathology_slide(str(tiff_path), artifact_threshold=0.20)

        # 결과 검증
        self.assertEqual(res["status"], "PASS")
        self.assertTrue(res["is_usable"])
        self.assertGreater(res["tissue_area_px"], 3000)
        self.assertEqual(res["artifact_area_px"], 0)
        self.assertEqual(res["artifact_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
