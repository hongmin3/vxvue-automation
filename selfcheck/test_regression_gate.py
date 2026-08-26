# -*- coding: utf-8 -*-
"""Phase 3 DICOM 연결 실패가 Phase 4 진입을 막는 게이트."""

import unittest
from unittest import mock

from core import regression


class DicomServerGateTests(unittest.TestCase):

    def _run(self, rows, specs=None):
        cfg = {"dicom": {"servers_to_register": specs or [
            {"kind": "MWL", "name": "MWL"},
            {"kind": "Storage", "name": "BUNNY"},
            {"kind": "Print", "name": "PRINT"},
        ]}}
        with mock.patch("core.db.VXvueDb"), mock.patch(
                "core.dicom_settings.ensure_registered", return_value=rows):
            return regression._run_dicom_registration(cfg, object())

    def test_모든_필수서버가_성공해야_통과한다(self):
        rows = [{"kind": k, "name": k, "registered": True, "echo_ok": True}
                for k in ("MWL", "Storage", "Print")]
        result, servers_ok = self._run(rows)
        self.assertTrue(servers_ok)
        self.assertEqual("PASS", result.verdict)

    def test_Storage_Echo실패도_전체게이트를_닫는다(self):
        rows = [
            {"kind": "MWL", "name": "MWL", "registered": True, "echo_ok": True},
            {"kind": "Storage", "name": "BUNNY", "registered": True, "echo_ok": False},
            {"kind": "Print", "name": "PRINT", "registered": True, "echo_ok": True},
        ]
        result, servers_ok = self._run(rows)
        self.assertFalse(servers_ok)
        self.assertEqual("FAIL", result.verdict)

    def test_처리결과_누락도_전체게이트를_닫는다(self):
        rows = [
            {"kind": "MWL", "name": "MWL", "registered": True, "echo_ok": True},
            {"kind": "Storage", "name": "BUNNY", "registered": True, "echo_ok": True},
        ]
        result, servers_ok = self._run(rows)
        self.assertFalse(servers_ok)
        self.assertEqual("FAIL", result.verdict)


if __name__ == "__main__":
    unittest.main()
