# -*- coding: utf-8 -*-
"""PC마다 달라지는 USB 드라이브 문자 선택 규칙."""

import unittest
from unittest import mock

from core import media


class MediaDestinationTests(unittest.TestCase):

    @mock.patch("core.media.removable_roots", return_value=["E:\\"])
    def test_설정된_USB가_있으면_그대로_쓴다(self, _roots):
        path, note = media.resolve_destination(r"E:\VXvue_QA_Export")
        self.assertEqual(r"E:\VXvue_QA_Export", path)
        self.assertIn("설정된", note)

    @mock.patch("core.media.removable_roots", return_value=["D:\\"])
    def test_E설정을_현재_D_USB로_자동_대체한다(self, _roots):
        path, note = media.resolve_destination(r"E:\VXvue_QA_Export")
        self.assertEqual(r"D:\VXvue_QA_Export", path)
        self.assertIn("자동 대체", note)

    @mock.patch("core.media.removable_roots", return_value=[])
    def test_USB가_없으면_경로를_추측하지_않는다(self, _roots):
        path, note = media.resolve_destination(r"E:\VXvue_QA_Export")
        self.assertIsNone(path)
        self.assertIn("없음", note)

    @mock.patch("core.media.removable_roots", return_value=["D:\\", "F:\\"])
    def test_USB가_여러개면_임의로_고르지_않는다(self, _roots):
        path, note = media.resolve_destination(r"E:\VXvue_QA_Export")
        self.assertIsNone(path)
        self.assertIn("여러 개", note)


if __name__ == "__main__":
    unittest.main()
