# -*- coding: utf-8 -*-
"""원격 Storage SCP 수신 판정 — 백엔드 선택과 **반환 형식 계약**.

반환 형식을 여기서 검사하는 이유: TC는 `res["log_excerpt"]`를 증거 파일로
첨부한다. 원격 경로가 그 키를 빼먹으면 **전송과 수신은 다 성공한 뒤 리포트를
쓰기 직전에** `KeyError`로 죽는다(2026-08-26 실제 발생 — 회귀 1회분을 날렸다).
제품을 켜야만 드러나는 종류의 오류라 정적으로 못 잡는다.
"""

import unittest
from unittest import mock

from core import storagescp


REMOTE_CFG = {
    "dicom": {
        "storage_server_url": "http://10.13.0.222:5003",
        "servers_to_register": [
            {"kind": "Storage", "name": "STORAGE_SCP", "ae_title": "STORAGE_SCP",
             "ip": "10.13.0.222", "port": 11116},
        ],
        "bunny": {"app_path": r"C:\Bunny\Bunny.exe",
                  "receive_dir": r"C:\Bunny\Receive"},
    }
}

LOCAL_CFG = {
    "dicom": {
        "storage_server_url": "http://10.13.0.222:5003",
        "servers_to_register": [
            {"kind": "Storage", "name": "BUNNY_TEST", "ae_title": "Bunny",
             "ip": "10.13.0.114", "port": 3000},
        ],
        "bunny": {"app_path": r"C:\Bunny\Bunny.exe",
                  "receive_dir": r"C:\Bunny\Receive"},
    }
}

STUDY = {"study_instance_uid": "1.2.3.4", "patient_id": "VXVUE_260826_153015",
         "modalities": "DX", "series_count": 1, "instance_count": 1,
         "last_received_at": "2026-08-26T06:34:49Z"}

#: 두 백엔드가 반드시 채워야 하는 키.
CONTRACT = ("ok", "files", "note", "log_excerpt", "backend")


class BackendSelectionTests(unittest.TestCase):

    def test_원격_Storage는_로컬_Bunny로_보지_않는다(self):
        self.assertFalse(storagescp.uses_local_bunny(REMOTE_CFG))

    def test_로컬_Bunny_설정은_옛_경로로_위임한다(self):
        self.assertTrue(storagescp.uses_local_bunny(LOCAL_CFG))

    def test_웹_API_주소가_없으면_원격_판정을_시도하지_않는다(self):
        cfg = {"dicom": dict(REMOTE_CFG["dicom"], storage_server_url="")}
        self.assertTrue(storagescp.uses_local_bunny(cfg))

    def test_Storage_항목이_없어도_죽지_않는다(self):
        self.assertEqual({}, storagescp.storage_spec({"dicom": {}}))


class ResultContractTests(unittest.TestCase):
    """어느 갈래로 빠져나가도 TC가 읽는 키가 다 있어야 한다."""

    def _check(self, res):
        for key in CONTRACT:
            self.assertIn(key, res, "반환 형식에 %r이 없다 — TC가 리포트 직전에 "
                                    "KeyError로 죽는다" % key)
        self.assertIsInstance(res["files"], list)
        self.assertIsInstance(res["log_excerpt"], str)
        self.assertTrue(res["note"].strip(), "note가 비면 리포트에 근거가 남지 않는다")

    def test_웹_주소가_없으면_실패로_보고하되_형식을_지킨다(self):
        cfg = {"dicom": dict(REMOTE_CFG["dicom"], storage_server_url="")}
        # uses_local_bunny를 거치지 않도록 baseline으로 원격 갈래를 지정한다.
        with mock.patch.object(storagescp, "uses_local_bunny", return_value=False):
            res = storagescp.wait_for_store(cfg, {"backend": "storagescp"})
        self.assertFalse(res["ok"])
        self._check(res)

    def test_Patient_ID가_없으면_남의_스터디를_세지_않고_멈춘다(self):
        with mock.patch.object(storagescp, "uses_local_bunny", return_value=False):
            res = storagescp.wait_for_store(REMOTE_CFG, {"backend": "storagescp"},
                                            patient_id=None)
        self.assertFalse(res["ok"])
        self.assertIn("Patient ID", res["note"])
        self._check(res)

    def test_스터디를_못_찾으면_시간과_이유를_남긴다(self):
        fake = mock.Mock()
        fake.studies_of.return_value = []
        with mock.patch.object(storagescp, "uses_local_bunny", return_value=False), \
             mock.patch.object(storagescp, "server", return_value=fake):
            res = storagescp.wait_for_store(REMOTE_CFG, {"backend": "storagescp"},
                                            timeout=0, poll=0,
                                            patient_id="VXVUE_없는환자")
        self.assertFalse(res["ok"])
        self.assertIn("찾지 못했다", res["note"])
        self._check(res)

    def test_수신_성공이면_객체_경로와_근거를_함께_준다(self):
        fake = mock.Mock()
        fake.studies_of.return_value = [STUDY]
        fake.download_study.return_value = [r"C:\work\1.2.3.4.1.dcm"]
        with mock.patch.object(storagescp, "uses_local_bunny", return_value=False), \
             mock.patch.object(storagescp, "server", return_value=fake):
            res = storagescp.wait_for_store(REMOTE_CFG, {"backend": "storagescp"},
                                            poll=0, patient_id=STUDY["patient_id"])
        self.assertTrue(res["ok"])
        self.assertEqual(1, len(res["files"]))
        self.assertEqual(STUDY, res["study"])
        self._check(res)
        # 근거 텍스트에 서버가 준 레코드가 그대로 들어가야 사람이 대조할 수 있다.
        self.assertIn(STUDY["study_instance_uid"], res["log_excerpt"])
        self.assertIn("DX", res["log_excerpt"])

    def test_다운로드가_실패하면_수신_사실과_실패를_모두_남긴다(self):
        fake = mock.Mock()
        fake.studies_of.return_value = [STUDY]
        fake.download_study.side_effect = OSError("경로가 너무 김")
        with mock.patch.object(storagescp, "uses_local_bunny", return_value=False), \
             mock.patch.object(storagescp, "server", return_value=fake):
            res = storagescp.wait_for_store(REMOTE_CFG, {"backend": "storagescp"},
                                            poll=0, patient_id=STUDY["patient_id"])
        self.assertFalse(res["ok"])
        self.assertIn("스터디는 수신됐으나", res["note"])
        self._check(res)


class PreconditionNoteTests(unittest.TestCase):

    def test_원격이면_Precondition_충족을_명시한다(self):
        note = storagescp.precondition_note(REMOTE_CFG)
        self.assertIn("다른 PC", note)
        self.assertIn("STORAGE_SCP", note)

    def test_로컬이면_옛_고지문을_그대로_쓴다(self):
        with mock.patch("core.bunny.precondition_note", return_value="로컬 고지문"):
            self.assertEqual("로컬 고지문", storagescp.precondition_note(LOCAL_CFG))


if __name__ == "__main__":
    unittest.main()
