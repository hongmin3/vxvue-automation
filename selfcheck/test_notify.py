# -*- coding: utf-8 -*-
"""종료 알림 — 판정 합산과 줄바꿈.

알림은 판정을 바꾸지 않지만, **틀린 알림은 틀린 판정보다 위험할 수 있다** —
"자동화 완료 — 전부 통과" 창을 보고 FAIL이 있는 회귀를 넘겨 버리면 결함이
그대로 나간다. 그래서 합산 규칙과 문구를 못 박아 둔다.
"""

import io
import unittest

from core import notify


class HeadlineTests(unittest.TestCase):

    def test_판정별_머리말이_구분된다(self):
        heads = {v: notify.headline(v)
                 for v in ("PASS", "FAIL", "MANUAL", "SKIP", "BLOCKED", "ABORTED")}
        self.assertEqual(len(set(heads.values())), len(heads),
                         "판정이 다른데 같은 머리말이 나온다: %s" % heads)

    def test_FAIL은_실패라고_말한다(self):
        self.assertIn("실패", notify.headline("FAIL"))

    def test_PASS만_전부_통과라고_말한다(self):
        self.assertIn("통과", notify.headline("PASS"))
        for v in ("FAIL", "MANUAL", "SKIP", "BLOCKED", "ABORTED"):
            self.assertNotIn("전부 통과", notify.headline(v),
                             "%s인데 '전부 통과'로 보인다" % v)

    def test_모르는_판정은_통과로_속이지_않는다(self):
        self.assertNotIn("전부 통과", notify.headline("무슨판정"))


class BannerTests(unittest.TestCase):

    def _banner(self, verdict, lines):
        buf = io.StringIO()
        notify.banner(verdict, lines, stream=buf)
        return buf.getvalue()

    def test_머리말과_본문이_모두_들어간다(self):
        out = self._banner("FAIL", ["TC 12건", "FAIL: TC_WindowsUpdate_05"])
        self.assertIn("실패", out)
        self.assertIn("TC_WindowsUpdate_05", out)

    def test_긴_경로는_잘리지_않는다(self):
        """중간에서 끊긴 경로는 복사해 쓸 수 없어 알림의 목적을 잃는다."""
        path = (r"C:\Users\2024980\Documents\자동화\VXvue\auto\Reports"
                r"\Result_20260825_153000.txt")
        out = self._banner("PASS", ["리포트: " + path])
        self.assertIn(path, out, "경로가 줄바꿈으로 쪼개졌다")

    def test_짧은_줄은_그대로_나온다(self):
        self.assertIn("소요: 12초", self._banner("PASS", ["소요: 12초"]))

    def test_공백이_있는_긴_한글_줄은_여러_줄로_나뉜다(self):
        """실제 리포트 줄은 전부 공백을 갖는다 — 이쪽이 정상 경로다."""
        long_ko = " ".join(["한글단어"] * 30)
        out = self._banner("PASS", [long_ko])
        self.assertNotIn(long_ko, out, "표시 폭을 넘는 한글 줄이 그대로 나왔다")
        self.assertIn("한글단어", out)

    def test_공백_없는_긴_토큰은_쪼개지_않고_넘치게_둔다(self):
        """계약: 토큰은 절대 쪼개지 않는다(`notify._wrap` docstring).

        경로가 중간에서 끊기면 복사해 쓸 수 없다. 그 대가로 공백 없는 긴
        토큰은 상자 폭을 넘어간다 — 의도한 동작이다.
        """
        blob = "가" * 80
        self.assertIn(blob, self._banner("PASS", [blob]))

    def test_빈_줄이나_None도_예외를_내지_않는다(self):
        """알림이 실패해서 실행 결과를 잃는 일이 없어야 한다."""
        self._banner("PASS", ["", None, 0])
        self._banner(None, None)          # 완전히 잘못된 인자도 조용히 넘어간다


class OverallVerdictTests(unittest.TestCase):
    """`run.py._overall_verdict()` — 여러 TC 판정을 하나로 합친다."""

    def setUp(self):
        import importlib
        self.run = importlib.import_module("run")

    def _combine(self, *verdicts):
        class _R(object):
            def __init__(self, v):
                self.verdict = v
        return self.run._overall_verdict([_R(v) for v in verdicts])

    def test_FAIL이_하나면_전체_FAIL(self):
        self.assertEqual("FAIL", self._combine("PASS", "PASS", "FAIL"))

    def test_FAIL이_BLOCKED보다_우선(self):
        self.assertEqual("FAIL", self._combine("BLOCKED", "FAIL"))

    def test_BLOCKED가_MANUAL보다_우선(self):
        self.assertEqual("BLOCKED", self._combine("MANUAL", "BLOCKED"))

    def test_MANUAL이_SKIP보다_우선(self):
        self.assertEqual("MANUAL", self._combine("SKIP", "MANUAL"))

    def test_SKIP이_PASS보다_우선(self):
        self.assertEqual("SKIP", self._combine("PASS", "SKIP"))

    def test_전부_PASS면_PASS(self):
        self.assertEqual("PASS", self._combine("PASS", "PASS"))

    def test_결과가_없으면_PASS로_속이지_않는다(self):
        self.assertNotEqual("PASS", self._combine())


if __name__ == "__main__":
    unittest.main()
