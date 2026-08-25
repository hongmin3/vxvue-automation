# -*- coding: utf-8 -*-
"""정적 검사 자체를 검사한다.

두 가지를 본다.

1. **지금 저장소가 실제로 통과하는가** — 통과하지 않으면 그게 곧 결함이다.
2. **검사가 물리는가** — 정규식이 아무것도 못 찾아 빈 집합끼리 비교하는 바람에
   "문제 0건"이 나오는 것을 막는다. 일부러 어긋난 값을 넣어 검사가 실제로
   문제를 잡는지 확인한다. (이 자동화가 가장 경계하는 실패 형태 — 확인 못 한
   것이 "차이 없음"으로 보이는 것 — 을 검사 계층에도 적용한 것이다.)
"""

import unittest

from selfcheck import static_checks as sc


class RepositoryIsConsistentTests(unittest.TestCase):
    """지금 저장소 상태 그대로 통과해야 하는 검사들."""

    def test_모든_정적검사_통과(self):
        problems = []
        for name, found in sc.run_all():
            problems.extend("%s: %s" % (name, p) for p in found)
        self.assertEqual([], problems, "\n" + "\n".join(problems))

    def test_파서가_실제로_값을_읽었다(self):
        """빈 결과끼리 비교해서 통과한 것이 아님을 보장한다."""
        self.assertGreaterEqual(len(sc.tc_ids_in_tests()), 10)
        self.assertGreaterEqual(len(sc.implemented_map()), 10)
        self.assertGreaterEqual(len(sc.scope_entries()), 10)
        self.assertGreaterEqual(len(sc.labels()), 10)


class ChecksActuallyBiteTests(unittest.TestCase):
    """일부러 어긋난 값을 넣어 각 검사가 문제를 잡는지 확인한다."""

    def setUp(self):
        self._saved = {name: getattr(sc, name) for name in
                       ("tc_ids_in_tests", "implemented_map",
                        "scope_entries", "labels")}

    def tearDown(self):
        for name, fn in self._saved.items():
            setattr(sc, name, fn)

    def test_TC_ID_미선언을_잡는다(self):
        sc.tc_ids_in_tests = lambda: {"tc99_thing.py": None}
        self.assertTrue(sc.check_tc_id_declared())

    def test_파일명_번호_불일치를_잡는다(self):
        sc.tc_ids_in_tests = lambda: {"tc02_thing.py": "TC_WindowsUpdate_07"}
        self.assertTrue(sc.check_filename_matches_tc_id())

    def test_번호_없는_파일은_파일명_검사에서_제외된다(self):
        sc.tc_ids_in_tests = lambda: {
            "tc_setting_export_import.py": "TC_Setting_ExportImport"}
        self.assertEqual([], sc.check_filename_matches_tc_id())

    def test_IMPLEMENTED가_없는_모듈을_가리키면_잡는다(self):
        sc.tc_ids_in_tests = lambda: {"tc02_a.py": "TC_WindowsUpdate_02"}
        sc.implemented_map = lambda: {"TC_WindowsUpdate_02": "tests.없는모듈"}
        self.assertTrue(sc.check_implemented_points_at_right_module())

    def test_IMPLEMENTED_키와_모듈_TC_ID가_다르면_잡는다(self):
        """가장 발견이 늦는 오류 — 실행은 성공하는데 리포트의 TC ID가 다르다."""
        sc.tc_ids_in_tests = lambda: {"tc02_a.py": "TC_WindowsUpdate_03"}
        sc.implemented_map = lambda: {"TC_WindowsUpdate_02": "tests.tc02_a"}
        found = sc.check_implemented_points_at_right_module()
        self.assertTrue(found)
        self.assertIn("TC_WindowsUpdate_03", found[0])

    def test_scope에_구현_TC가_빠지면_잡는다(self):
        sc.implemented_map = lambda: {"TC_WindowsUpdate_02": "tests.tc02_a"}
        sc.scope_entries = lambda: [{"tc_id": "TC_WindowsUpdate_03",
                                     "level": "FULL", "reason": "r"}]
        self.assertTrue(sc.check_scope_covers_implemented())

    def test_reason_없는_scope를_잡는다(self):
        sc.scope_entries = lambda: [{"tc_id": "X", "level": "FULL", "reason": ""}]
        self.assertTrue(sc.check_scope_has_reason())

    def test_level_없는_scope를_잡는다(self):
        sc.scope_entries = lambda: [{"tc_id": "X", "level": "", "reason": "r"}]
        self.assertTrue(sc.check_scope_has_reason())

    def test_알_수_없는_level을_잡는다(self):
        sc.scope_entries = lambda: [{"tc_id": "X", "level": "거의됨", "reason": "r"}]
        self.assertTrue(sc.check_scope_levels_known())

    def test_scope_중복을_잡는다(self):
        sc.scope_entries = lambda: [{"tc_id": "X", "level": "FULL", "reason": "r"},
                                    {"tc_id": "X", "level": "FULL", "reason": "r"}]
        self.assertTrue(sc.check_scope_ids_unique())

    def test_라벨_누락을_잡는다(self):
        sc.scope_entries = lambda: [{"tc_id": "X", "level": "FULL", "reason": "r"}]
        sc.labels = lambda: {}
        self.assertTrue(sc.check_labels_cover_scope())

    def test_시험목적_누락을_잡는다(self):
        sc.implemented_map = lambda: {"TC_존재하지않는_ID": "tests.tc02_a"}
        sc.tc_ids_in_tests = lambda: {}
        self.assertTrue(sc.check_purposes_cover_implemented())


if __name__ == "__main__":
    unittest.main()
