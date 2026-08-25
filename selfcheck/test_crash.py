# -*- coding: utf-8 -*-
"""`crash.find_dumps()` — 예전 덤프를 이번 크래시로 오인하지 않는지.

이 필터가 틀리면 두 방향으로 잘못된다.
- `since`가 너무 느슨하면 **몇 달 전 다른 프로세스의 덤프**를 근거로 정상
  종료를 "크래시"라고 보고한다. 이 PC에는 실제로 2026-08-18 `XIPL.SERVER.exe`
  덤프 2건이 남아 있어 실현 가능한 오류다.
- 너무 엄격하면 진짜 크래시를 놓쳐 "원인 불명"으로 내려가고, 리포트에 진짜
  원인이 남지 않는다.

실제 파일시스템을 쓰되 임시 폴더 안에서만 만들고 지운다 — `%LOCALAPPDATA%\\
CrashDumps`의 실제 덤프는 건드리지 않는다(제품 크래시 증거이므로).
"""

import os
import tempfile
import unittest

from core import crash as crash_mod


class FindDumpsTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = crash_mod.CRASH_DUMP_DIR
        crash_mod.CRASH_DUMP_DIR = self._tmp.name

    def tearDown(self):
        crash_mod.CRASH_DUMP_DIR = self._saved
        self._tmp.cleanup()

    def _dump(self, name, mtime):
        path = os.path.join(self._tmp.name, name)
        with open(path, "wb") as f:
            f.write(b"x")
        os.utime(path, (mtime, mtime))
        return path

    def test_해당_프로세스의_덤프만_찾는다(self):
        self._dump("VXvue.exe.111.dmp", 1000)
        self._dump("XIPL.SERVER.exe.222.dmp", 1000)
        found = crash_mod.find_dumps("VXvue")
        self.assertEqual(1, len(found))
        self.assertTrue(found[0].endswith("VXvue.exe.111.dmp"))

    def test_since보다_오래된_덤프는_제외한다(self):
        self._dump("VXvue.exe.111.dmp", 1000)          # TC 시작 전에 이미 있던 것
        self._dump("VXvue.exe.222.dmp", 3000)          # 이번 TC 중에 생긴 것
        found = crash_mod.find_dumps("VXvue", since=2000)
        self.assertEqual(1, len(found))
        self.assertTrue(found[0].endswith("VXvue.exe.222.dmp"))

    def test_since와_같은_시각의_덤프는_포함한다(self):
        """경계값 — TC 시작과 같은 초에 생긴 덤프를 놓치지 않는다."""
        self._dump("VXvue.exe.111.dmp", 2000)
        self.assertEqual(1, len(crash_mod.find_dumps("VXvue", since=2000)))

    def test_오래된_것부터_정렬되고_마지막이_가장_최근(self):
        """`_check_crash()`가 `dumps[-1]`을 리포트에 적으므로 순서가 중요하다."""
        self._dump("VXvue.exe.111.dmp", 1000)
        self._dump("VXvue.exe.333.dmp", 3000)
        self._dump("VXvue.exe.222.dmp", 2000)
        found = crash_mod.find_dumps("VXvue")
        self.assertTrue(found[-1].endswith("VXvue.exe.333.dmp"))

    def test_덤프가_없으면_빈_목록(self):
        """빈 목록은 '원인 불명'으로 내려가는 신호다 — 예외가 아니어야 한다."""
        self.assertEqual([], crash_mod.find_dumps("VXvue"))

    def test_폴더가_아예_없어도_예외가_아니다(self):
        crash_mod.CRASH_DUMP_DIR = os.path.join(self._tmp.name, "없는폴더")
        self.assertEqual([], crash_mod.find_dumps("VXvue"))


if __name__ == "__main__":
    unittest.main()
