# -*- coding: utf-8 -*-
"""리포트 완전성 게이트 — 빈 사용자 필드와 미등록 Step을 실제로 잡는지.

`CLAUDE.md` 9절(리포트 가독성·완전성 영구 기준)의 6번 항목이 이 함수에
의존한다. 게이트가 조용히 통과해 버리면 "사용자용 문장이 비어 있는 리포트"가
그대로 나가는데, 그건 사람이 결과를 판단할 수 없다는 뜻이다.
"""

import unittest

from core import result as result_mod
from core.result import FAIL, MANUAL, PASS, TCResult


def _catalogued_tc_id():
    """문장 사전에 이미 등록된 TC ID 하나(실제 값을 쓴다)."""
    for tc_id in result_mod.TC_PURPOSES:
        return tc_id
    raise AssertionError("TC_PURPOSES가 비어 있다")


class ReportQualityTests(unittest.TestCase):

    def test_미등록_TC_ID를_잡는다(self):
        r = TCResult("TC_존재하지않는_ID", "미등록")
        r.add(1, "아무_Step", PASS, expected="e", actual="a")
        q = result_mod.report_quality([r])
        self.assertFalse(q["readable"])
        self.assertTrue(any("TC_존재하지않는_ID" in x
                            for x in q["uncatalogued_tc_purposes"]))

    def test_미등록_Step_문장을_잡는다(self):
        r = TCResult(_catalogued_tc_id(), "등록된 TC")
        r.add(1, "사전에_없는_아주_희귀한_Step_제목", PASS, expected="e", actual="a")
        q = result_mod.report_quality([r])
        self.assertTrue(q["uncatalogued_steps"],
                        "문장 사전 미등록 Step이 검출되지 않았다")

    def test_잘못된_상태값을_잡는다(self):
        r = TCResult(_catalogued_tc_id(), "등록된 TC")
        r.add(1, "step", "WEIRD", expected="e", actual="a")
        q = result_mod.report_quality([r])
        self.assertFalse(q["readable"])
        self.assertTrue(any("WEIRD" in x for x in q["invalid_statuses"]))

    def test_빈_expected_actual은_합성_건수로_센다(self):
        """빈 값은 `readable`을 깨지 않지만 몇 건인지 반드시 보고된다 —
        추측으로 채우지 않았다는 사실이 리포트에 남아야 한다."""
        r = TCResult(_catalogued_tc_id(), "등록된 TC")
        r.add(1, "step", MANUAL, expected="", actual="", note="확인 불가")
        q = result_mod.report_quality([r])
        self.assertEqual(1, q["synthesized_expected_count"])
        self.assertEqual(1, q["synthesized_actual_count"])

    def test_assert_report_readable은_문제가_있으면_예외를_낸다(self):
        r = TCResult("TC_존재하지않는_ID", "미등록")
        r.add(1, "step", PASS, expected="e", actual="a")
        with self.assertRaises(AssertionError):
            result_mod.assert_report_readable([r])

    def test_사용자용_필드는_어떤_상태에서도_비지_않는다(self):
        """판정 이유·후속 조치는 상태별 설명에서 나오므로 note가 없어도 채워진다."""
        for status in result_mod.STATUSES:
            r = TCResult(_catalogued_tc_id(), "등록된 TC")
            c = r.add(1, "step", status, expected="", actual="", note="")
            for name in ("reader_expected", "reader_actual",
                         "reader_reason", "reader_action"):
                self.assertTrue(str(getattr(c, name)).strip(),
                                "%s가 %s 상태에서 비어 있다" % (name, status))

    def test_blocks_verdict_False는_판정_이유에_명시된다(self):
        """예외로 PASS를 막지 않았다는 사실이 리포트에 드러나야 한다 —
        드러나지 않으면 '왜 SKIP인데 PASS인가'를 설명할 수 없다."""
        r = TCResult(_catalogued_tc_id(), "등록된 TC")
        c = r.add(1, "step", result_mod.SKIP, note="미수행", blocks_verdict=False)
        self.assertIn("PASS를 막지 않는다", c.reader_reason)


class CaveatTests(unittest.TestCase):

    def test_리포트_유의사항이_비어_있지_않다(self):
        """DX 전용 범위 표시(사용자 지시 2026-08-25)가 사라지면 리포트를 읽는
        사람이 MG 미검증을 모르고 넘어간다."""
        self.assertTrue(result_mod.REPORT_CAVEATS)
        self.assertTrue(all(str(x).strip() for x in result_mod.REPORT_CAVEATS))

    def test_문서번호가_체크리스트와_같다(self):
        self.assertEqual("R-25-774", result_mod.DOC_NUMBER)


class WriteReportTests(unittest.TestCase):

    def test_HTML_JSON만_생성되고_유의사항과_원본값이_보존된다(self):
        import json
        import os
        import tempfile
        r = TCResult(_catalogued_tc_id(), "등록된 TC")
        r.add(1, "step", FAIL, expected="e", actual="a", note="n")
        r.finalize()
        with tempfile.TemporaryDirectory() as d:
            paths = result_mod.write_reports([r], d)
            self.assertEqual({"html", "json"}, set(paths))
            for kind in ("html", "json"):
                self.assertIn(kind, paths, "%s 리포트가 생성되지 않았다" % kind)
            self.assertFalse(any(name.endswith((".csv", ".txt"))
                                 for name in os.listdir(d)))
            with open(paths["html"], encoding="utf-8") as f:
                html = f.read()
            with open(paths["json"], encoding="utf-8") as f:
                payload = json.load(f)
        self.assertIn(result_mod.REPORT_CAVEATS[0][:20], html,
                      "HTML 리포트 상단에 범위 유의사항이 없다")
        check = payload["results"][0]["checks"][0]
        self.assertEqual(("e", "a", "n"),
                         (check["expected"], check["actual"], check["note"]))


if __name__ == "__main__":
    unittest.main()
