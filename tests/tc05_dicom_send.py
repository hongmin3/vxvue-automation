# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_05 — DX DICOM 영상 전송.

실행: ``python run.py tc05``

이 프로젝트의 검증 범위는 DX(일반촬영)뿐이다. 사용자 지시(2026-08-26)로
MG와 MG에 종속된 Dose SR 조건은 판정·수동 확인·SKIP 항목 어디에도 넣지 않는다.
따라서 이 TC는 다른 PC의 Storage SCP에 **이번 DX 영상이 정상 전송됐는지**만
수신측 API와 DICOM SOP Class로 판정한다.
"""

import os

from core import dicomlite
from core import storagescp as store_mod
from core import workflow as W
from core.result import FAIL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_05"
TC_TITLE = "DICOM 전송 (DX Image → 원격 Storage SCP)"

SOP_IMAGE = "1.2.840.10008.5.1.4.1.1.1.1"


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc05")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    if do_acquire:
        try:
            flow = W.open_and_acquire(
                ui, cfg,
                patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"),
                projection=projection, step=exam_step,
                evidence_dir=evidence_dir, map_procedure_name=map_procedure)
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "전송할 DX 영상 준비 (MWL + Step + 촬영)", FAIL,
                  actual=str(exc))
            return r.finalize()
        opened = flow["opened"]
        acq = flow["acquire"] or {
            "acquired": False, "before": 0, "after": 0, "seconds": 0,
            "state": "", "dialogs": [], "note": "Step 등록 실패로 촬영하지 않았다"}
        r.add(step, "전송할 DX 영상 준비 (MWL 오픈 + Demo 촬영)",
              PASS if acq["acquired"] else FAIL,
              expected="DX 영상 1장 이상 획득",
              actual="영상 %d → %d장 (%.1f초) / 상태=%r / 처리한 팝업=%s"
                     % (acq["before"], acq["after"], acq["seconds"], acq["state"],
                        acq["dialogs"] or "없음"),
              note="MWL 조회 %s." % opened.get("summary", ""))
        if not acq["acquired"]:
            return r.finalize()
    else:
        r.add(step, "전송할 DX 영상 준비", SKIP,
              note="--no-acquire로 실행되어 이미 열려 있는 영상을 사용한다.")
    step += 1

    store_mark = store_mod.mark(cfg)
    W.select_first_image(ui)
    sent = W.send(ui, scope="all")
    r.add(step, "DICOM Send 실행 (All Images)",
          PASS if sent.get("dialog") else FAIL,
          expected="전송 범위 팝업에서 All Images 선택",
          actual="팝업 표시=%s / 누른 버튼 id=%s"
                 % (sent.get("dialog"), sent.get("clicked")))
    step += 1

    res = store_mod.wait_for_store(
        cfg, store_mark, count=1, timeout=150,
        patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"))
    r.add(step, "Storage SCP 수신 확인 (C-STORE Status + 파일)",
          PASS if res["ok"] else FAIL,
          expected=("C-STORE 응답 Status 0000h + 수신 파일 1건 이상"
                    if res.get("backend") == "bunny" else
                    "원격 Storage SCP에 이번 Patient ID의 객체 1건 이상"),
          actual=res["note"], note=store_mod.precondition_note(cfg))
    step += 1

    classes = {}
    modalities = set()
    for path in res["files"]:
        tags = dicomlite.read_tags(path, ["SOPClassUID", "Modality", "PatientID"])
        classes.setdefault(tags.get("SOPClassUID") or "(판독 실패)", []).append(
            os.path.basename(path))
        if tags.get("Modality"):
            modalities.add(tags["Modality"])
        r.attach(path)

    has_image = SOP_IMAGE in classes
    is_dx = "DX" in modalities
    r.add(step, "전송된 객체에 DX Image가 포함",
          PASS if (has_image and is_dx) else FAIL,
          expected="Modality=DX + SOP Class %s" % SOP_IMAGE,
          actual="Modality=%s / %s" % (
              ",".join(sorted(modalities)) or "판독 실패",
              "; ".join("%s x%d" % (k, len(v)) for k, v in classes.items())
              or "수신 객체 없음"),
          note="수신 측 DICOM 태그로 전송 성공을 판정한다.")

    if res.get("log_excerpt"):
        path = os.path.join(
            evidence_dir,
            "bunny_log_excerpt.txt" if res.get("backend") == "bunny"
            else "storage_scp_receipt.txt")
        try:
            import io
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(res["log_excerpt"])
            r.attach(path)
        except OSError:
            pass

    return r.finalize()
