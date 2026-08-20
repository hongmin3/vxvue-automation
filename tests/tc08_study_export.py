# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_08 — Study Export.

실행: `python run.py tc08`

## 체크리스트 원문 (R-25-774, Checklist 시트 14행)

Precondition: *CD/USB*

Step Description
```
1. 스터디를 선택하고 외부 저장 매체로 Export 를 한다.
   - CD
   - USB
2. CD/USB 에 Export 된 스터디를 선택 후 뷰어로 import 한다.
```

Expected Result
```
1. Study Export 가 성공한다.
   export 된 영상 오픈하여 확인
2. 뷰어로 import 성공한다.
```

Test Data: *CD로 Export 한 후 CD 안의 QXlink portable viewer 가 정상 실행되는지 확인할것.*

Comment(원본에 기록된 이력): *Win11: CD Export 함 / Win10 : USB Export함 /
**Win11 #21049 Study Export 시 에러 발생 하면서 Export 안됨***

## 알려진 결함 #21049 — 이 TC의 회귀 목적

체크리스트 Comment에 **Win11에서 Study Export 시 에러가 발생하며 Export되지
않는다(#21049)** 는 이력이 남아 있다. 이 시험대는 Windows 11이므로 **이 TC는
그 결함의 재발 여부를 확인하는 회귀 케이스**다. 그래서 Export 실패를 단순
FAIL로 끝내지 않고, **에러 문구를 캡처·OCR로 남겨 #21049와 대조할 수 있게** 한다.

## 매체 처리 — E 드라이브 기준 (사용자 지시)

물리 CD 굽기와 USB 삽입은 사람이 해야 하므로 자동화할 수 없다. 사용자 지시
(2026-08-19): **"TC08번은 지금 E드라이브로 수행해주면 좋을것 같아. 앞으로도
E드라이브를 기준으로 수행되도록 해주면 될것 같아."**

그래서 `config.json`의 `export.dest_dir`(기본 `E:\VXvue_QA_Export`)로 Export
하고, 그 산출물을 검증한다. 대상 경로를 코드에 박지 않으므로 나중에 실제 USB
드라이브 문자로 바꾸면 그대로 동작한다.

검증 내용은 매체 종류와 무관하게 동일하다.

| 확인 | 방법 |
|---|---|
| Export 실행됨 | Export Manager 창이 열리고 Start가 눌린다 |
| 산출물 생성 | 대상 폴더에 파일이 생긴다 |
| **영상이 진짜인가** | `core/dicomlite`로 DICOM 태그를 읽어 환자정보 대조 |
| Portable viewer | `QXLink` 실행 파일 포함 여부(존재 확인까지 — 실행은 MANUAL) |
| 역방향 Import | Database `Import`(30315)로 되읽기 |

"export 된 영상 오픈하여 확인"이라는 Expected Result를 **뷰어로 열어 보는 대신
파일 태그를 직접 읽어** 확인한다 — 사람이 눈으로 보는 것보다 대조 항목이 명확하고
증적으로 남는다.

## Export Manager는 별도 프로세스다 (실측)

`C:\Program Files\Vxvue\VX.EXPORT.MANAGER.exe`가 별도 최상위 창으로 뜬다
(Bellalun의 `EXPORT.MANAGER`와 같은 구조). VXvue 프로세스에 붙은 드라이버로는
이 창의 컨트롤이 보이지 않으므로 `VXvueUi("VX.EXPORT.MANAGER")`로 따로 붙는다.
**이 창의 컨트롤 ID는 아직 실측하지 못했다** — 그래서 이 TC는 창이 떴는지까지
확인하고, 그 안의 조작은 실측 후 구현하도록 남긴다(추측한 ID를 누르면 엉뚱한
설정을 바꾼다).
"""

import os
import time

from core import dicomlite
from core import workflow as W
from core.result import BLOCKED, FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_08"
TC_TITLE = "Study Export (외부 저장 매체 Export → 산출물 검증 → 역방향 Import)"

KNOWN_DEFECT = "#21049 (Win11에서 Study Export 시 에러 발생하며 Export 안 됨)"


def _export_cfg(cfg):
    ex = cfg.get("export") or {}
    return (ex.get("dest_dir") or r"E:\VXvue_QA_Export",
            ex.get("process_name") or "VX.EXPORT.MANAGER",
            ex.get("exe") or r"C:\Program Files\Vxvue\VX.EXPORT.MANAGER.exe")


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc08")
    os.makedirs(evidence_dir, exist_ok=True)
    dest, proc_name, exe = _export_cfg(cfg)
    step = 1

    # --- Step 0: 대상 매체(드라이브) 준비 -------------------------------
    drive = os.path.splitdrive(dest)[0] or dest[:2]
    drive_ok = os.path.isdir(drive + os.sep)
    if not drive_ok:
        r.add(step, "Export 대상 드라이브 확인", BLOCKED,
              expected="%s 사용 가능" % drive, actual="드라이브를 찾을 수 없음",
              note="사용자 지시로 E 드라이브를 기준으로 수행한다. 드라이브가 없으면 "
                   "Export를 시도할 수 없다 — config.json의 export.dest_dir을 실제 "
                   "매체 경로로 바꾼 뒤 다시 실행할 것.")
        r.finalize()
        return r
    before = set()
    try:
        os.makedirs(dest, exist_ok=True)
        before = set(_walk(dest))
    except OSError as exc:
        r.add(step, "Export 대상 폴더 준비", FAIL, actual=str(exc))
        r.finalize()
        return r
    r.add(step, "Export 대상 준비 (%s)" % dest, PASS,
          expected="대상 폴더 사용 가능",
          actual="기존 파일 %d개" % len(before),
          note="체크리스트 Precondition은 CD/USB지만 물리 매체 굽기·삽입은 사람이 "
               "해야 하므로 **E 드라이브를 기준으로 수행**한다(사용자 지시, "
               "2026-08-19). 실제 USB로 바꿀 때는 config.json의 export.dest_dir만 "
               "고치면 된다 — 경로를 코드에 박지 않았다. 기존 파일 목록을 먼저 떠 "
               "이번 Export 산출물만 가려낸다.")
    step += 1

    # --- Step 1: Export 대상 스터디 준비 -------------------------------
    if do_acquire:
        try:
            flow = W.open_and_acquire(
                ui, cfg,
                patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"),
                projection=projection, step=exam_step,
                evidence_dir=evidence_dir, map_procedure_name=map_procedure)
            acq = flow["acquire"] or {"acquired": False, "before": 0, "after": 0,
                                      "seconds": 0, "dialogs": [],
                                      "note": "Step 등록 실패로 촬영하지 않았다"}
            W.close_study(ui, cfg, evidence_dir=evidence_dir)
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "Export 대상 스터디 준비", FAIL, actual=str(exc))
            r.finalize()
            return r
        r.add(step, "Export 대상 스터디 준비 (MWL 오픈 + 촬영 + Close)",
              PASS if acq["acquired"] else FAIL,
              expected="영상 1장 이상 획득 후 검사 종료",
              actual="영상 %d → %d장 / 처리한 팝업=%s"
                     % (acq["before"], acq["after"], acq["dialogs"] or "없음"))
        if not acq["acquired"]:
            r.finalize()
            return r
    else:
        r.add(step, "Export 대상 스터디 준비", SKIP,
              note="--no-acquire로 실행되어 기존 스터디를 사용한다.")
    step += 1

    # --- Step 2: Database에서 스터디 선택 ------------------------------
    summary = W.database_search(ui)
    rows = W.list_rows(ui, W.DB_LIST)
    if not rows:
        r.add(step, "Database에서 Export 대상 스터디 선택", BLOCKED,
              expected="Database 목록에서 스터디 선택",
              actual="%s / 목록 행 0개" % summary,
              note="Export는 Database 목록에서 대상을 골라야 실행할 수 있는데 목록이 "
                   "비어 있다. TC02에서 확인한 것과 같은 원인이다 — Operation Manual "
                   "3.6(p.41)에 따르면 Database는 **완료된 검사**만 표시하고, "
                   "Procedure Mapping을 하지 않으면 Step이 등록되지 않아 검사가 "
                   "완료 처리되지 않는다(STUDY.StudyStatus=1로 남는다). "
                   "**따라서 이 TC를 끝까지 수행하려면 Procedure Mapping이 선행돼야 "
                   "한다** — 매핑 자동화는 2026-08-19 사고로 비활성화되어 있어"
                   "(core/workflow.map_procedure docstring) 사람이 화면에서 매핑한 "
                   "뒤 실행해야 한다. Export 자체를 검증하지 못했으므로 알려진 결함 "
                   "%s의 재발 여부도 이번 실행으로는 판단할 수 없다." % KNOWN_DEFECT)
        r.finalize()
        return r
    W.click_row(ui, rows[0])
    r.add(step, "Database에서 Export 대상 스터디 선택", PASS,
          actual="%s / 첫 행 선택" % summary)
    step += 1

    # --- Step 3: Export 실행 -------------------------------------------
    try:
        W.db_button(ui, "export", settle=3.0)
    except Exception as exc:                              # noqa: BLE001
        r.add(step, "Export 실행 (Database > Export)", FAIL, actual=str(exc))
        r.finalize()
        return r

    popups = W.pending_dialogs(ui, evidence_dir=evidence_dir, cfg=cfg)
    mgr_up, mgr_note = _wait_manager(proc_name, timeout=25)
    # **팝업을 분류해서 본다** — 성공 알림과 오류를 같이 취급하면 #21049 재발을
    # 놓친다(core/dialogs.py). blocking=True인 것만 결함 신호로 센다.
    defect_hit = [d for d in popups if d.blocking]
    r.add(step, "Export 실행 — Export Manager 창 표시",
          PASS if mgr_up else (FAIL if defect_hit else MANUAL),
          expected="%s 창이 열린다" % proc_name,
          actual="%s / Export 클릭 직후 팝업=%s"
                 % (mgr_note, [str(d) for d in popups] or "없음"),
          note=("Export Manager는 별도 최상위 프로세스다(실측: %s). "
                % exe)
               + ("**에러 팝업이 떴다 — 알려진 결함 %s의 재발 가능성이 있다.** "
                  "팝업 문구를 증적으로 남겼으니 원본 이슈와 대조할 것."
                  % KNOWN_DEFECT if defect_hit else
                  "체크리스트 Comment의 알려진 결함 %s는 이번 실행에서 에러 팝업으로 "
                  "재현되지 않았다." % KNOWN_DEFECT))
    step += 1

    if not mgr_up:
        r.add(step, "Export 산출물 검증", BLOCKED,
              note="Export Manager 창이 열리지 않아 이후 단계를 수행할 수 없다.")
        r.finalize()
        return r

    # --- Step 4: Export Manager 조작 (실측 미완료) -----------------------
    r.add(step, "Export Manager에서 대상 경로·형식 지정 및 Start", MANUAL,
          expected="대상=%s / DICOM 형식 / Start" % dest,
          actual="창은 떴으나 자동 조작하지 않았다",
          note="**이 창의 컨트롤 ID를 아직 실측하지 못했다.** 추측한 ID를 누르면 "
               "형식·익명화·Portable viewer 포함 여부 등 엉뚱한 설정을 바꾼다"
               "(CLAUDE.md 3절 — 근거 없는 조작 금지). 확정 방법: 이 창이 떠 있는 "
               "상태에서 `python run.py ui-probe`를 돌려 컨트롤 트리를 덤프하고 "
               "캡처와 대조해 config.json에 기록할 것. Bellalun의 "
               "`core/export_manager.py`가 같은 구조(별도 프로세스 + 경로 Edit + "
               "형식/옵션 체크박스 + Start)를 다루므로 설계는 그대로 옮길 수 있다 — "
               "**컨트롤 ID만 VXvue에서 새로 실측하면 된다.**")
    step += 1

    # --- Step 5: 산출물 검증 (Start를 사람이 눌렀을 때를 위해 남긴다) ----
    added = [p for p in _walk(dest) if p not in before]
    dicoms = []
    for path in added:
        try:
            with open(path, "rb") as f:
                if f.read(132)[128:132] == b"DICM":
                    dicoms.append(path)
        except OSError:
            continue
    r.add(step, "Export 산출물 생성 확인",
          PASS if added else MANUAL,
          expected="대상 폴더에 파일이 생성된다",
          actual="신규 파일 %d개 (DICOM %d개)" % (len(added), len(dicoms)),
          note="Start를 자동으로 누르지 않았으므로 이번 실행에서는 보통 0개다. "
               "사람이 Export Manager에서 Start를 누른 뒤 `--no-acquire`로 다시 "
               "실행하면 이 Step부터 검증된다.")
    step += 1

    if dicoms:
        want_id = (cfg.get("test_data") or {}).get("mwl_patient_id")
        tags = dicomlite.read_tags(dicoms[0], ["PatientID", "PatientName",
                                               "AccessionNumber", "Modality",
                                               "SOPClassUID"])
        ok = not want_id or str(tags.get("PatientID") or "") == want_id
        r.add(step, "Export된 영상의 DICOM 태그 확인 (\"export 된 영상 오픈하여 확인\")",
              PASS if ok else FAIL,
              expected="PatientID=%s" % want_id,
              actual=" / ".join("%s=%s" % (k, v) for k, v in tags.items()
                                if not k.startswith("_")),
              note="Expected Result의 'export 된 영상 오픈하여 확인'을 뷰어로 여는 "
                   "대신 파일 태그를 직접 읽어 확인한다 — 대조 항목이 명확하고 "
                   "증적으로 남는다.")
        r.attach(dicoms[0])
        step += 1

        qx = [p for p in added if "qxlink" in os.path.basename(p).lower()]
        r.add(step, "Portable viewer(QXLink) 포함 확인",
              PASS if qx else MANUAL,
              expected="Export 산출물에 QXLink portable viewer 포함",
              actual="%d개: %s" % (len(qx), [os.path.basename(p) for p in qx[:3]]),
              note="체크리스트 Test Data: 'CD 안의 QXlink portable viewer 가 정상 "
                   "실행되는지 확인할것.' — **실행 여부는 사람이 확인해야 한다**"
                   "(외부 실행 파일을 자동으로 띄우지 않는다). 자동화는 포함 여부까지 "
                   "확인한다. Export Manager의 'Portable Viewer' 옵션을 켜야 "
                   "포함되므로, 포함되지 않았다면 그 옵션 상태를 함께 확인할 것.")
        step += 1

    # --- Step 6: 역방향 Import (Expected Result 2) ----------------------
    r.add(step, "Export된 스터디를 뷰어로 Import", MANUAL,
          expected="Database > Import(30315)로 되읽기 성공",
          actual="수행하지 않음",
          note="Import는 **DB에 데이터를 추가하는 조작**이라 자동 승인 없이 "
               "실행하지 않는다. Export 산출물이 확보된 뒤 사람이 승인하거나 "
               "별도 옵션으로 수행하도록 남긴다. 버튼은 실측 확인됨"
               "(Database 화면 Import=30315).")

    r.finalize()
    return r


def _walk(root):
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            out.append(os.path.join(dirpath, name))
    return out


def _wait_manager(process_name, timeout=25, poll=1.0):
    """Export Manager 창이 뜰 때까지 기다린다."""
    from core.ui import VXvueUi
    end = time.time() + timeout
    while time.time() < end:
        mgr = VXvueUi(process_name)
        if mgr.pid and mgr.main_window():
            return True, "창 확인 (PID %s)" % mgr.pid
        time.sleep(poll)
    return False, "%d초 안에 %s 창이 열리지 않았다" % (timeout, process_name)
