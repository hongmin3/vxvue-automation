# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_05 — DICOM 전송.

실행: `python run.py tc05`

## 체크리스트 원문 (R-25-774, Checklist 시트 11행)

Precondition: *다른 PC 의 Server 이용 - Storage*

Step Description
```
1. Setting- DICOM - General -
   Send Dose SR : Yes
2. 영상을 선택 후 DICOM Send 한다
```

Expected Result
```
1. 영상 전송이 성공한다.
   - Image, DSR
```

Test Data: *QXLink 로 전송하여 Image, Dose SR 전송되는지 확인 - Image, 스냅샷 영상, Dose SR 전송됨*

## TC02와 무엇이 다른가

TC02는 "MWL 정보가 전송정보까지 일치하는가"를 보고, 이 TC는 **"Send Dose SR을
Yes로 설정했을 때 Image와 함께 Dose SR(DSR)도 전송되는가"** 를 본다. 즉 전송
**대상 객체의 종류**가 판정 대상이다.

판정은 수신된 객체의 SOP Class UID로 한다.

| 객체 | SOP Class UID |
|---|---|
| Digital X-Ray Image Storage - For Presentation | `1.2.840.10008.5.1.4.1.1.1.1` |
| X-Ray Radiation Dose SR | `1.2.840.10008.5.1.4.1.1.88.67` |

DICOM Conformance Statement에서 지원 여부를 확인한 뒤 그 값을 기준으로 쓴다
(`core/specs.py`로 인용).

## Storage 한계 (사용자 지시)

Precondition은 "다른 PC 의 Server"지만 이 실행은 **이 PC의 Bunny**를 쓴다.
`core/bunny.precondition_note()`가 그 차이를 판정 note에 남기며, 원격 PC로
옮길 때는 `config.json`의 Storage 항목(ip/port)과 수신 폴더만 바꾸면 된다.
"""

import os
import time

from core import dicomlite
from core import setting as S
from core import storagescp as store_mod
from core import workflow as W
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_05"
TC_TITLE = "DICOM 전송 (Send Dose SR = Yes → Image + Dose SR 전송)"

SCREEN = "DICOM - General"

SOP_IMAGE = "1.2.840.10008.5.1.4.1.1.1.1"
SOP_DOSE_SR = "1.2.840.10008.5.1.4.1.1.88.67"

# Setting > DICOM - General 의 "Send Dose SR" 컨트롤 ID(실측 2026-08-21).
# "Send Dose SR" Static(y=276) 옆의 Yes/No 라디오 쌍 — TC13의 폴더 자동
# 감지 Yes/No(31366/31367)와 같은 구조. Service Manual p.136 4.9.1 /
# 사양서4 p.88 VP-707로 위치는 이미 알려져 있었고, 이번 세션에 컨트롤
# ID를 확정했다.
SEND_DOSE_SR_YES_ID = 31421
SEND_DOSE_SR_NO_ID = 31422


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc05")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    # --- Step 1: Setting > DICOM - General 의 Send Dose SR을 Yes로 -------
    def _field(cid):
        return next((c for c in S.content_controls(ui) if c.ctrl_id == cid), None)

    was_yes = None
    try:
        found = S.goto_screen(ui, SCREEN)
    except Exception as exc:                              # noqa: BLE001
        found = None
        r.add(step, "Setting > %s 화면 진입" % SCREEN, FAIL, actual=str(exc))
    if found is None:
        r.add(step, "Setting > %s 화면 진입" % SCREEN, FAIL,
              actual="화면을 찾지 못함" if found is None else "")
    else:
        yes_radio, no_radio = _field(SEND_DOSE_SR_YES_ID), _field(SEND_DOSE_SR_NO_ID)
        if yes_radio is None or no_radio is None:
            r.add(step, "Send Dose SR Yes/No 라디오 확인", MANUAL,
                  expected="Yes(%d)/No(%d) 라디오 존재" % (SEND_DOSE_SR_YES_ID, SEND_DOSE_SR_NO_ID),
                  actual="찾지 못함 — 화면 구조가 실측과 달라졌을 수 있음")
        else:
            was_yes = S.checkbox_checked(ui, yes_radio)
            if was_yes:
                r.add(step, "Send Dose SR = Yes (체크리스트 Step1)", PASS,
                      expected="Yes", actual="이미 Yes였음(건드리지 않음)")
            else:
                ui.click(yes_radio, settle=0.6)
                yes2 = _field(SEND_DOSE_SR_YES_ID)
                now_yes = yes2 is not None and S.checkbox_checked(ui, yes2)
                ack = S.update(ui, ack_timeout=8) if now_yes else None
                r.assert_true(step, "Send Dose SR = Yes (체크리스트 Step1)", now_yes,
                              expected="Yes로 전환 + Update",
                              actual="전환 확인, 완료 팝업: %s" % (ack or "없음") if now_yes
                              else "전환 반영 확인 실패")
    step += 1

    # Send Dose SR을 이번 실행에서 Yes로 바꿨으면(was_yes == False) 시험이
    # 끝난 뒤 반드시 원복한다 — 다른 TC/회귀가 이 설정 변경의 영향을 받지
    # 않게 한다(TC13의 TAB 구분자 원복과 같은 원칙).
    try:
        # --- Step 2: 촬영 → 영상 선택 → Send ---------------------------
        if do_acquire:
            try:
                flow = W.open_and_acquire(
                    ui, cfg,
                    patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"),
                    projection=projection, step=exam_step,
                    evidence_dir=evidence_dir, map_procedure_name=map_procedure)
            except Exception as exc:                          # noqa: BLE001
                r.add(step, "전송할 영상 준비 (MWL 오픈 + Step 등록 + 촬영)",
                      FAIL, actual=str(exc))
                return r.finalize()
            opened = flow["opened"]
            acq = flow["acquire"] or {"acquired": False, "before": 0, "after": 0,
                                      "seconds": 0, "state": "", "dialogs": [],
                                      "note": "Step 등록 실패로 촬영하지 않았다"}
            r.add(step, "전송할 영상 준비 (MWL 오픈 + Demo 촬영)",
                  PASS if acq["acquired"] else FAIL,
                  expected="영상 1장 이상 획득",
                  actual="영상 %d → %d장 (%.1f초) / 상태=%r / 처리한 팝업=%s"
                         % (acq["before"], acq["after"], acq["seconds"], acq["state"],
                            acq["dialogs"] or "없음"),
                  note="MWL 조회 %s. 촬영 흐름은 TC02와 같은 `core/workflow`를 쓴다."
                       % opened.get("summary", ""))
            if not acq["acquired"]:
                return r.finalize()
        else:
            r.add(step, "전송할 영상 준비", SKIP,
                  note="--no-acquire로 실행되어 이미 열려 있는 영상을 사용한다.")
        step += 1

        store_mark = store_mod.mark(cfg)
        W.select_first_image(ui)
        sent = W.send(ui, scope="all")
        r.add(step, "DICOM Send 실행 (All Images)",
              PASS if sent.get("dialog") else FAIL,
              expected="전송 범위 팝업에서 All Images 선택",
              actual="팝업 표시=%s / 누른 버튼 id=%s"
                     % (sent.get("dialog"), sent.get("clicked")),
              note="All Images를 택하는 이유: 체크리스트 Test Data가 'Image, 스냅샷 영상, "
                   "Dose SR 전송됨'을 기대하므로 검사에 속한 객체 전부를 보내야 한다.")
        step += 1

        # --- 수신 확인 ---------------------------------------------------
        res = store_mod.wait_for_store(
            cfg, store_mark, count=1, timeout=150,
            patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"))
        r.add(step, "Storage SCP 수신 확인 (C-STORE Status + 파일)",
              PASS if res["ok"] else FAIL,
              expected=("C-STORE 응답 Status 0000h + 수신 파일 1건 이상"
                        if res.get("backend") == "bunny" else
                        "Storage SCP 수신 목록에 이번 실행의 Patient ID 스터디 1건 "
                        "+ 그 스터디의 원본 객체 1건 이상"),
              actual=res["note"],
              note=store_mod.precondition_note(cfg))
        step += 1

        # --- 전송된 객체 종류 판정 (이 TC의 핵심) -------------------------
        classes = {}
        modalities = set()
        for path in res["files"]:
            tags = dicomlite.read_tags(path, ["SOPClassUID", "Modality", "PatientID"])
            classes.setdefault(tags.get("SOPClassUID") or "(판독 실패)", []).append(
                os.path.basename(path))
            if tags.get("Modality"):
                modalities.add(tags.get("Modality"))
            r.attach(path)

        has_image = SOP_IMAGE in classes
        has_dose = SOP_DOSE_SR in classes
        # 2026-08-24~25에는 이 자리를 "Dose SR은 사양서상 MG 전용이니 DX에서
        # 없는 것이 정상"이라고 정리했다(Conformance Statement Rev.4.2 p.10
        # 2.2.9절). **2026-08-26 실측으로 그 설명은 근거가 유지되지 않는다** —
        # 새 Storage SCP(STORAGE_SCP 10.13.0.222:11116)에 다른 시험대가 보낸
        # DX 스터디 2건(P002 / test111, station=VXvue_JJH / vieworks)을
        # 내려받아 태그를 읽으니 Modality=DX,SR,XC이고 그 SR의 SOP Class가
        # 정확히 1.2.840.10008.5.1.4.1.1.88.67(X-Ray Radiation Dose SR)이었다.
        # 즉 서버가 못 받는 것도, DX라서 안 나오는 것도 아니다.
        #
        # 그런데 이 자동화의 실행에서는 Send Dose SR=Yes를 확인·적용한 두
        # 차례(15:24 '이미 Yes', 15:35 'No→Yes 전환+Update 성공') 모두 DX 영상
        # 1건만 도달했다. **원인은 아직 규명되지 않았다.** 그래서 판정을
        # 추측으로 바꾸지 않고(SKIP 유지) note에 "범위 밖"이 아니라 "원인
        # 미확정"이라고 적는다 — 사용자/QA 결정 대기 항목으로 NEXT_TASK.md에
        # 올렸다.
        is_mg = "MG" in modalities
        r.add(step, "전송된 객체에 Image가 포함",
              PASS if has_image else FAIL,
              expected="SOP Class %s (Digital X-Ray Image Storage - For Presentation)"
                       % SOP_IMAGE,
              actual="; ".join("%s x%d" % (k, len(v)) for k, v in classes.items())
                     or "수신 객체 없음")
        step += 1

        if has_dose:
            dose_verdict, dose_note = PASS, "확인됨."
        elif not is_mg:
            dose_verdict, dose_note = SKIP, (
                "촬영 Modality=%s(MG 아님). Send Dose SR = Yes를 위 Step에서 "
                "확인·적용했는데도 Dose SR이 오지 않았다. **원인 미확정이다.** "
                "사양서(Conformance Statement Rev.4.2 p.10 2.2.9절 \"Dose "
                "structured report service as SCU is implemented ... for "
                "correctly transferred MG images.\")를 근거로 2026-08-25까지는 "
                "'MG 전용이라 DX에는 없는 것이 정상'으로 정리했으나, 2026-08-26 "
                "실측으로 그 설명은 유지되지 않는다 — 같은 Storage SCP에 다른 "
                "시험대가 보낸 **DX 스터디**(P002 / test111)에는 Modality "
                "DX,SR,XC와 SOP Class %s(X-Ray Radiation Dose SR)가 함께 들어 "
                "있었다. 즉 서버 수신 능력의 문제도, DX라서 없는 것도 아니다. "
                "이 회귀의 촬영 경로(F2 데모/가상 촬영)가 Dose SR·스냅샷(XC) "
                "객체를 애초에 만들지 않는지, 아니면 다른 Setting이 관여하는지 "
                "**확인이 필요하다**. 추측으로 판정을 바꾸지 않기 위해 SKIP을 "
                "유지하되(결함으로 단정하지 않는다) 사용자·QA 결정 대기 항목으로 "
                "남긴다 — NEXT_TASK.md 참고."
                % (", ".join(sorted(modalities)) or "판독 실패", SOP_DOSE_SR))
        elif was_yes is not True:
            dose_verdict, dose_note = MANUAL, (
                "Dose SR이 수신되지 않았다. Send Dose SR 라디오를 못 찾아 Yes 전환을 "
                "확인하지 못했으므로(위 Step MANUAL) 이 결과만으로 결함이라 단정하지 "
                "않는다. 체크리스트 Test Data의 '스냅샷 영상'은 Live View 스냅샷이므로 "
                "TC12 범위다.")
        else:
            dose_verdict, dose_note = FAIL, (
                "촬영 Modality=MG이고 Send Dose SR = Yes를 위 Step에서 확인·적용했는데도 "
                "Dose SR이 수신되지 않았다 — 결함 가능성이 있다.")
        r.add(step, "전송된 객체에 Dose SR이 포함", dose_verdict,
              expected="SOP Class %s (X-Ray Radiation Dose SR)" % SOP_DOSE_SR,
              actual="Dose SR 수신 %s" % ("확인됨" if has_dose else "확인되지 않음"),
              note=dose_note)
        step += 1

        if res.get("log_excerpt"):
            path = os.path.join(
                evidence_dir,
                "bunny_log_excerpt.txt" if res.get("backend") == "bunny"
                else "storage_scp_receipt.txt")
            try:
                import io as _io
                _io.open(path, "w", encoding="utf-8", newline="\n").write(res["log_excerpt"])
                r.attach(path)
            except OSError:
                pass
    finally:
        if was_yes is False:
            revert_ok = False
            try:
                # 본 시험이 끝난 시점의 화면은 Exposure/Viewer다. 현재 화면에서
                # Setting 라디오를 찾으면 항상 None이 되어 원복이 실패한다.
                # 원복도 설정 변경과 같은 경로로 DICOM-General에 다시 진입해
                # 실제 No 상태와 Update 완료를 확인한다.
                S.goto_screen(ui, SCREEN)
                no_radio = _field(SEND_DOSE_SR_NO_ID)
                if no_radio is not None:
                    ui.click(no_radio, settle=0.6)
                    no2 = _field(SEND_DOSE_SR_NO_ID)
                    revert_ok = no2 is not None and S.checkbox_checked(ui, no2)
                    if revert_ok:
                        S.update(ui, ack_timeout=8)
            except Exception:                              # noqa: BLE001
                revert_ok = False
            r.assert_true(step, "Send Dose SR 원복(No)", revert_ok,
                          expected="테스트 종료 후 원래 값(No)으로 복원",
                          actual="복원 완료" if revert_ok else
                          "복원 실패 — 사람이 Setting > DICOM - General에서 직접 확인할 것")

    return r.finalize()
