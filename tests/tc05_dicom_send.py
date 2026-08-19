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

from core import bunny as bunny_mod
from core import dicomlite
from core import setting as S
from core import workflow as W
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_05"
TC_TITLE = "DICOM 전송 (Send Dose SR = Yes → Image + Dose SR 전송)"

SCREEN = "DICOM - General"

SOP_IMAGE = "1.2.840.10008.5.1.4.1.1.1.1"
SOP_DOSE_SR = "1.2.840.10008.5.1.4.1.1.88.67"

# Setting > DICOM - General 의 "Send Dose SR" 컨트롤 ID는 실측으로 확정해야
# 한다. 확정되지 않은 상태에서 임의의 ID를 누르면 다른 설정을 바꿔 버리므로,
# 값을 모르는 동안은 **누르지 않고** 화면의 컨트롤 구성만 보고한다
# (`VXvue/CLAUDE.md` 3절 — 근거 없는 조작 금지).
SEND_DOSE_SR_CHECK_ID = None


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc05")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    # --- Step 1: Setting > DICOM - General 의 Send Dose SR 확인 ---------
    try:
        found = S.goto_screen(ui, SCREEN)
        vals = S.screen_values(ui, title_text=SCREEN) if found is not None else {}
    except Exception as exc:                              # noqa: BLE001
        found, vals = None, {}
        r.add(step, "Setting > %s 화면 진입" % SCREEN, FAIL, actual=str(exc))
    if found is not None:
        radios = vals.get("unreadable_state_controls") or []
        r.add(step, "Setting > %s 화면에서 Send Dose SR 항목 확인" % SCREEN,
              MANUAL,
              expected="Send Dose SR = Yes",
              actual="화면 진입 성공 / 상태를 읽을 수 없는 컨트롤 %d개" % len(radios),
              note="**Send Dose SR의 컨트롤 ID를 아직 실측으로 확정하지 못했다.** "
                   "이 화면의 라디오/체크박스는 owner-draw라 상태를 표준 API로 읽을 "
                   "수 없고, 어느 컨트롤이 Send Dose SR인지 확정하지 않은 상태에서 "
                   "누르면 다른 설정을 바꿔 버린다(CLAUDE.md 3절 — 근거 없는 조작 "
                   "금지). 따라서 이 Step은 **사람이 화면에서 Yes인지 확인**해야 "
                   "한다. 확정 방법: `python run.py ui-probe`로 이 화면을 덤프하고 "
                   "라벨 위치와 컨트롤 ID를 대조해 config.json에 기록할 것.")
    step += 1

    # --- Step 2: 촬영 → 영상 선택 → Send -------------------------------
    if do_acquire:
        try:
            opened = W.open_mwl_study(ui, cfg,
                                      patient_id=(cfg.get("test_data") or {}).get(
                                          "mwl_patient_id"),
                                      evidence_dir=evidence_dir,
                                      map_procedure_name=map_procedure)
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "전송할 영상 준비 (MWL 오픈 + 촬영)", FAIL, actual=str(exc))
            r.finalize()
            return r
        acq = W.acquire(ui, cfg, evidence_dir=evidence_dir)
        r.add(step, "전송할 영상 준비 (MWL 오픈 + Demo 촬영)",
              PASS if acq["acquired"] else FAIL,
              expected="영상 1장 이상 획득",
              actual="영상 %d → %d장 (%.1f초) / 상태=%r / 처리한 팝업=%s"
                     % (acq["before"], acq["after"], acq["seconds"], acq["state"],
                        acq["dialogs"] or "없음"),
              note="MWL 조회 %s. 촬영 흐름은 TC02와 같은 `core/workflow`를 쓴다."
                   % opened.get("summary", ""))
        if not acq["acquired"]:
            r.finalize()
            return r
    else:
        r.add(step, "전송할 영상 준비", SKIP,
              note="--no-acquire로 실행되어 이미 열려 있는 영상을 사용한다.")
    step += 1

    log_off = bunny_mod.log_size(cfg)
    t0 = time.time() - 5
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

    # --- 수신 확인 -----------------------------------------------------
    res = bunny_mod.wait_for_store(cfg, count=1, timeout=150,
                                   log_offset=log_off, files_newer_than=t0)
    r.add(step, "Storage SCP 수신 확인 (C-STORE Status + 파일)",
          PASS if res["ok"] else FAIL,
          expected="C-STORE 응답 Status 0000h + 수신 파일 1건 이상",
          actual=res["note"],
          note=bunny_mod.precondition_note(cfg))
    step += 1

    # --- 전송된 객체 종류 판정 (이 TC의 핵심) ---------------------------
    classes = {}
    for path in res["files"]:
        tags = dicomlite.read_tags(path, ["SOPClassUID", "Modality", "PatientID"])
        classes.setdefault(tags.get("SOPClassUID") or "(판독 실패)", []).append(
            os.path.basename(path))
        r.attach(path)

    has_image = SOP_IMAGE in classes
    has_dose = SOP_DOSE_SR in classes
    r.add(step, "전송된 객체에 Image가 포함",
          PASS if has_image else FAIL,
          expected="SOP Class %s (Digital X-Ray Image Storage - For Presentation)"
                   % SOP_IMAGE,
          actual="; ".join("%s x%d" % (k, len(v)) for k, v in classes.items())
                 or "수신 객체 없음")
    step += 1

    r.add(step, "전송된 객체에 Dose SR이 포함",
          PASS if has_dose else MANUAL,
          expected="SOP Class %s (X-Ray Radiation Dose SR)" % SOP_DOSE_SR,
          actual="Dose SR 수신 %s" % ("확인됨" if has_dose else "확인되지 않음"),
          note=("확인됨." if has_dose else
                "Dose SR이 수신되지 않았다. **이것만으로 결함이라 단정하지 않는다** — "
                "전제가 두 가지이고 둘 다 이 실행에서 확정되지 않았다: (1) Setting > "
                "DICOM - General 의 'Send Dose SR'이 Yes여야 한다(위 Step에서 사람 "
                "확인 필요로 남겼다), (2) 가상 제너레이터 환경에서 선량 정보가 "
                "생성되어야 Dose SR 객체가 만들어진다. 두 전제를 확인한 뒤 다시 "
                "판정할 것. 체크리스트 Test Data의 '스냅샷 영상'은 Live View "
                "스냅샷이므로 TC12 범위다."))
    step += 1

    if res["log_excerpt"]:
        path = os.path.join(evidence_dir, "bunny_log_excerpt.txt")
        try:
            import io as _io
            _io.open(path, "w", encoding="utf-8", newline="\n").write(res["log_excerpt"])
            r.attach(path)
        except OSError:
            pass

    r.finalize()
    return r
