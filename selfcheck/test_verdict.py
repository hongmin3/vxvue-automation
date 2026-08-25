# -*- coding: utf-8 -*-
"""`TCResult.verdict` 판정 규칙 — 사용자가 확정한 규칙을 그대로 못 박는다.

각 테스트 이름 뒤의 근거는 `core/result.py`의 주석과 `CLAUDE.md` 3절에 있는
사용자 확정 사항이다. 규칙을 바꾸려면 **여기 테스트를 먼저 고쳐야 한다** —
그게 이 파일의 목적이다(코드만 고쳐서 판정 기준이 조용히 바뀌는 것을 막는다).
"""

import unittest

from core.result import (BLOCKED, FAIL, MANUAL, PASS, SKIP, STATUSES, TCResult)


def _tc(*steps):
    """(status, blocks_verdict) 목록으로 TCResult를 만든다."""
    r = TCResult("TC_TEST", "판정 규칙 검사")
    for i, item in enumerate(steps, 1):
        status, blocks = item if isinstance(item, tuple) else (item, True)
        r.add(i, "step%d" % i, status, expected="e", actual="a",
              blocks_verdict=blocks)
    return r


class VerdictTests(unittest.TestCase):

    def test_fail_하나면_전체_FAIL(self):
        """FAIL이 하나라도 있으면 나머지가 전부 PASS여도 FAIL이다.

        크래시 감지가 이 규칙에 의존한다 — `regression._check_crash()`는 이미
        기록된 Step들이 PASS/MANUAL이어도 FAIL Step 하나를 덧붙여 그 TC를
        FAIL로 확정한다.
        """
        self.assertEqual(FAIL, _tc(PASS, PASS, FAIL).verdict)

    def test_fail이_blocks_verdict_False여도_FAIL(self):
        """`blocks_verdict=False` 예외는 MANUAL/SKIP/BLOCKED에만 적용된다.

        FAIL을 PASS를 막지 않는 항목으로 만들 수 있으면 결함을 숨길 수 있게
        되므로, FAIL은 이 플래그와 무관하게 항상 전체를 FAIL로 만든다.
        """
        self.assertEqual(FAIL, _tc(PASS, (FAIL, False)).verdict)

    def test_전부_PASS면_PASS(self):
        self.assertEqual(PASS, _tc(PASS, PASS).verdict)

    def test_PASS와_MANUAL이_섞이면_MANUAL(self):
        self.assertEqual(MANUAL, _tc(PASS, MANUAL).verdict)

    def test_SKIP도_PASS를_막는다(self):
        """"완전 자동화"는 모든 Step이 PASS/FAIL인 상태다(사용자 확정 2026-08-20).

        SKIP 1건이라도 있으면 그 TC는 완전 자동화된 것이 아니므로 PASS가 아니다.
        """
        self.assertEqual(MANUAL, _tc(PASS, SKIP).verdict)

    def test_BLOCKED도_PASS를_막는다(self):
        self.assertEqual(MANUAL, _tc(PASS, BLOCKED).verdict)

    def test_blocks_verdict_False인_SKIP은_PASS를_막지_않는다(self):
        """사용자 확정 예외(2026-08-21) — TC14의 `--deep` 미수행 Step 1건.

        체크리스트 원문 범위는 가벼운 모드로 이미 충족되고 `--deep`은 그 위의
        정밀 검증이라, 미수행이 PASS를 막을 이유가 아니다.
        """
        self.assertEqual(PASS, _tc(PASS, (SKIP, False)).verdict)

    def test_blocks_verdict_False인_MANUAL_BLOCKED도_막지_않는다(self):
        self.assertEqual(PASS, _tc(PASS, (MANUAL, False), (BLOCKED, False)).verdict)

    def test_PASS가_0이고_BLOCKED가_있으면_BLOCKED(self):
        """선행조건이 없어 아무것도 못 한 경우를 MANUAL과 구분한다."""
        self.assertEqual(BLOCKED, _tc(BLOCKED, MANUAL).verdict)

    def test_PASS가_0이고_SKIP만_있으면_SKIP(self):
        self.assertEqual(SKIP, _tc(SKIP, SKIP).verdict)

    def test_PASS가_0이고_MANUAL만_있으면_MANUAL(self):
        self.assertEqual(MANUAL, _tc(MANUAL).verdict)

    def test_Step이_없으면_MANUAL(self):
        """아무 Step도 기록하지 못한 TC를 PASS로 흘려보내지 않는다."""
        self.assertEqual(MANUAL, _tc().verdict)

    def test_PASS가_0일_때_BLOCKED가_SKIP보다_우선(self):
        self.assertEqual(BLOCKED, _tc(SKIP, BLOCKED).verdict)


class CountsTests(unittest.TestCase):

    def test_counts는_모든_상태_키를_갖는다(self):
        """리포트 합계가 상태 하나를 빠뜨리지 않게 보장한다."""
        c = _tc(PASS, FAIL).counts
        self.assertEqual(set(STATUSES), set(c))
        self.assertEqual(1, c[PASS])
        self.assertEqual(1, c[FAIL])
        self.assertEqual(0, c[SKIP])

    def test_add는_Step마다_timing을_남긴다(self):
        r = _tc(PASS, PASS, FAIL)
        steps = [t for t in r.timings if t["kind"] == "step"]
        self.assertEqual(3, len(steps))
        self.assertEqual([PASS, PASS, FAIL], [t["outcome"] for t in steps])

    def test_finalize는_처음_값을_유지한다(self):
        """두 번 불려도 완료 시각이 밀리지 않는다 — 크래시 처리 경로가
        `finalize(r.completed)`로 다시 부른다."""
        r = _tc(PASS).finalize()
        first = r.completed
        r.finalize()
        self.assertEqual(first, r.completed)


if __name__ == "__main__":
    unittest.main()
