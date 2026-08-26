# -*- coding: utf-8 -*-
"""baseline 복원 전 파일 점유 프로세스 종료 목록."""

import os
import unittest

from core import dbreset


class BaselineProcessTests(unittest.TestCase):

    def test_LiveView_로그_작성자를_종료대상에_포함한다(self):
        self.assertIn("VX.LIVE.VIEW", dbreset.APP_PROCESSES)

    def test_현재_DB백업_하위폴더를_복원제외한다(self):
        self.assertIn(os.path.join("Database", "Bak"),
                      dbreset.FOLDER_RESTORE_EXCLUDE_DIRS)

    def test_DB백업_출력경로를_생략할수없다(self):
        with self.assertRaises(dbreset.DbResetError):
            dbreset.backup()


if __name__ == "__main__":
    unittest.main()
