# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_06 — Extra Tool 전송 (SBSC).

실행: `python run.py tc06`

## 체크리스트 원문 (R-25-774, Checklist 시트 12행, `work/work_tc06_checklist.txt`로
UTF-8 재추출해 확인)

Precondition: *다른 PC 의 Server 이용 - Extra Tool*

Step Description
```
1. 촬영화면에서 SBSC 를 ON 후 촬영한다.
2. 툴의 Extra Tool 버튼을 눌러 전송한다.
3. XIPL Server Log를 확인하여 SBSC 미적용하여 processing 을 다시 한후에
   전송이 되는지 확인한다.
4. 뷰어모드로 영상을 오픈 후 SBSC 적용된 영상을 선택하여 Extra Tool 버튼을
   누른다.
```

Expected Result
```
3.4. Extra Tool 에 설정한 SCP 로 전송 성공한다.
- Extra Tool 의 Remove SBSC 옵션 켜고 전송 시 SBSC 적용하지 않은 영상이
  전송되는것을 확인
```

Test Data: *Remove SBSC 옵션 설정 후 툴의 Extra Tool 을 선택하여 전송하면
XIPL Server Log 에 PureGrid.Apply="0" 이 전송됨*

## 서버 정보는 하드코딩하지 않는다 (사용자 지시, 2026-08-24)

전송 대상(AE Title/IP/Port)은 `config.json`의 `extra_tool.server`에서만
읽는다. 지금은 Storage SCP(Bunny)와 같은 값이지만, 이 자동화가 나중에 Dose SR
검증 등으로 Bunny 대신 다른 서버를 쓰게 되더라도 Extra Tool 대상은
`dicom.servers_to_register`와 무관하게 독립적으로 바꿀 수 있어야 한다.

## "SBSC를 ON 후 촬영" ≠ Image Process 화면에서 SBSC 체크

실측(2026-08-25): 이 회귀가 쓰는 데모/가상 촬영 경로(F2, 파라미터 파일
"Chest PA_normal_H.hs8")의 Image Process 창에는 SBSC 체크박스 자체가 없다
(Contrast/Sharpness/Brightness/Process/Post LUT만 있음, TC04가 이미 이
창의 파라미터 컨트롤을 미실측으로 남겨 둔 것과 같은 한계). 그래서 이 TC는
체크리스트 원문이 실제로 요구하는 것 — **Extra Tool 화면의 Remove SBSC(=
S.B.S.C., `core.extra_tool.SBSC_CHECK_ID`) 옵션을 켠 상태에서 전송하면 XIPL
Server Log에 `PureGrid.Apply="0"`이 남는다** — 만 판정한다.

**한계**: 이 캡처 경로는 애초에 `PureGrid.Apply="0"`으로 처리되어 있어(그
자체가 정상 캡처 로그에도 이미 찍힌다), 이 TC의 로그 확인이 "SBSC가 켜진
영상에서 강제로 꺼졌다"는 전환(1→0)까지 증명하지는 못한다. Image Process
화면에서 SBSC를 켤 수 있는 절차·파라미터 파일이 확인되면 그때 이 한계를
보완할 것 — 지금은 확인되지 않은 것을 추측해 조작하지 않는다(`CLAUDE.md` 3절).

## 수신 판정: Bunny(로컬) 또는 Storage SCP 웹 API(원격)

2026-08-27 사용자 지시로 Extra Tool 대상을 Storage와 같은 원격 서버
(`STORAGE_SCP`, 10.13.0.222:11116)로 옮겼다. `core.extra_tool.uses_local_bunny()`가
`extra_tool.server`만 보고 로컬/원격을 가른다(`dicom.servers_to_register`의
Storage 항목과는 독립 — 둘이 나중에 다시 달라져도 이 판단은 그것과 무관하다).
원격이면 `core.storagescp`의 웹 API 폴링(`mark()`/`wait_for_store()`)을
`force_backend="storagescp"`로 재사용한다 — Extra Tool 대상이 물리적으로
Storage SCP와 같은 서버이므로 같은 웹 API에서 이번 실행의 Patient ID로
스터디를 찾을 수 있다. 로컬 Bunny로 남아 있다면(과거 구성) 기존
`core.bunny` 경로를 그대로 쓴다 — "다른 PC 의 Server" Precondition과의
차이는 `precondition_note()`가 판정 note에 남긴다.

**재전송(Step4) 확인은 건수가 아니라 최종 수신 시각으로 한다.** 실측
(2026-08-27): 같은 영상을 다시 보내면 같은 SOP Instance UID라 서버가 기존
객체를 갱신 처리하고 `instance_count`가 늘지 않는다 — "건수가 1차보다 많아야
한다"는 첫 시도는 이 때문에 오탐 FAIL을 냈다. `core.storagescp.wait_for_resend()`가
`last_received_at` 갱신으로 판정한다.
"""

import os
import time

from core import bunny as bunny_mod
from core import extra_tool as ET
from core import storagescp as store_mod
from core import workflow as W
from core import xipl
from core.db import DbError, VXvueDb
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult


def _mark(cfg):
    backend = "bunny" if ET.uses_local_bunny(cfg) else "storagescp"
    return store_mod.mark(cfg, force_backend=backend)


def _wait_for_store(cfg, baseline, **kwargs):
    return store_mod.wait_for_store(cfg, baseline, **kwargs)


def _precondition_note(cfg):
    if ET.uses_local_bunny(cfg):
        return bunny_mod.precondition_note(cfg)
    spec = (cfg.get("extra_tool") or {}).get("server") or {}
    return ("체크리스트 Precondition의 '다른 PC 의 Server 이용 - Extra Tool'을 "
            "충족한다 — 이 실행은 다른 PC의 사내 공용 시험 서버(%s %s:%s, "
            "Storage SCP와 같은 서버)를 Extra Tool 대상으로 썼고, 수신은 그 서버의 "
            "웹 API로 받은 쪽에서 확인했다(사용자 지시, 2026-08-27)."
            % (spec.get("ae_title"), spec.get("ip"), spec.get("port")))

TC_ID = "TC_WindowsUpdate_06"
TC_TITLE = "Extra Tool 전송 (Remove SBSC 옵션 → XIPL 재처리 → 전송)"


def _ae_row(db, ae_title, port):
    try:
        rows = db.ae_list(kind="AI_STATION")
    except DbError as exc:
        return None, "DB 조회 실패: %s" % exc
    for row in rows:
        if row.get("Title") == ae_title and row.get("Port") == port:
            return row, None
    return None, "AE_LIST(AI_STATION)에서 Title=%s Port=%s 행을 찾지 못함" % (ae_title, port)


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc06")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    server = (cfg.get("extra_tool") or {}).get("server") or {}
    ae_title, ip, port = server.get("ae_title"), server.get("ip"), server.get("port")
    if not all((ae_title, ip, port)):
        r.add(step, "Extra Tool 대상 서버 설정 확인", FAIL,
              expected="config.json의 extra_tool.server(ae_title/ip/port)",
              actual="설정 누락: %r" % server)
        return r.finalize()

    db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
    want_id = (cfg.get("test_data") or {}).get("mwl_patient_id")

    # --- Step 1: Extra Tool 대상 서버 등록 + Remove SBSC(S.B.S.C.) 켜기 ----
    try:
        ok, note = ET.configure(ui, ae_title, ip, port)
    except Exception as exc:                              # noqa: BLE001
        ok, note = False, str(exc)
    row, row_note = (None, None)
    if ok:
        row, row_note = _ae_row(db, ae_title, port)
    r.add(step, "Extra Tool 대상 서버 등록 (Setting > Integration > Extra Tool)",
          PASS if ok and row else FAIL,
          expected="AE Title=%s IP=%s Port=%s 로 Update, DB(AE_LIST)에서 확인"
                   % (ae_title, ip, port),
          actual="화면 Update: %s / DB 확인: %s" % (note, row or row_note),
          note="서버 정보는 config.json의 extra_tool.server만 쓴다(하드코딩 금지, "
               "사용자 지시 2026-08-24).")
    step += 1
    if not (ok and row):
        return r.finalize()

    try:
        sok, snote = ET.set_sbsc(ui, True)
    except Exception as exc:                              # noqa: BLE001
        sok, snote = False, str(exc)
    row2, row2_note = (None, None)
    if sok:
        row2, row2_note = _ae_row(db, ae_title, port)
    remove_sbsc_on = bool(row2 and row2.get("RemoveSBSC") == 1)
    r.add(step, "Remove SBSC(S.B.S.C., 31523) 옵션 켜기",
          PASS if sok and remove_sbsc_on else FAIL,
          expected="체크 후 Update, DB AE_LIST.RemoveSBSC = 1",
          actual="화면 Update: %s / DB RemoveSBSC=%s"
                 % (snote, (row2 or {}).get("RemoveSBSC", row2_note)))
    step += 1
    if not remove_sbsc_on:
        return r.finalize()

    # --- Step 2: 촬영 → 영상 선택 → Extra Tool 전송 ------------------------
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
        acq = flow["acquire"] or {"acquired": False, "before": 0, "after": 0,
                                  "seconds": 0, "state": "", "dialogs": [],
                                  "note": "Step 등록 실패로 촬영하지 않았다"}
        r.add(step, "전송할 영상 준비 (MWL 오픈 + Demo 촬영, 체크리스트 Step1)",
              PASS if acq["acquired"] else FAIL,
              expected="영상 1장 이상 획득 (SBSC는 Extra Tool의 Remove SBSC 옵션으로 검증)",
              actual="영상 %d → %d장 (%.1f초) / 상태=%r"
                     % (acq["before"], acq["after"], acq["seconds"], acq["state"]),
              note="이 데모 캡처 경로의 Image Process 창에는 SBSC 체크박스가 없다"
                   "(모듈 docstring 참고) — Extra Tool 쪽 옵션으로만 검증한다.")
        step += 1
        if not acq["acquired"]:
            return r.finalize()
    else:
        r.add(step, "전송할 영상 준비", SKIP,
              note="--no-acquire로 실행되어 이미 열려 있는 영상을 사용한다.")
        step += 1

    vm = W.viewer_mode(ui, cfg)
    W.select_first_image(ui)
    mark1 = _mark(cfg)
    t0 = time.time() - 5
    xipl_cfg = cfg.get("xipl") or {}
    xipl_log_dir = xipl_cfg.get("server_log_dir")
    xipl_marker = xipl_cfg.get("puregrid_marker", 'PureGrid.Apply="0"')
    xipl_since = None
    if xipl_log_dir:
        from datetime import datetime
        xipl_since = datetime.fromtimestamp(t0)

    clicked = W.click_tool(ui, cfg, name="Extra Tool", section="tools",
                           evidence_dir=evidence_dir)
    r.add(step, "툴 팔레트에서 Extra Tool 클릭 (체크리스트 Step2)",
          PASS if clicked.get("ok") else FAIL,
          expected="Viewer 모드 Tools 팔레트에서 'Extra Tool' 라벨을 찾아 클릭",
          actual="Viewer 모드=%s / 매칭=%s / 클릭 지점=%s / 읽어낸 툴 %d개"
                 % (vm, clicked.get("matched"), clicked.get("point"),
                    len(clicked.get("available") or [])),
          note="팔레트에 없으면: %s" % (", ".join(clicked.get("available") or []) or "없음"))
    step += 1
    if not clicked.get("ok"):
        return r.finalize()

    # --- Step 3: 수신 확인 + XIPL Server Log의 PureGrid.Apply="0" 확인 -----
    res = _wait_for_store(cfg, mark1, count=1, timeout=90, patient_id=want_id)
    for path in res["files"]:
        r.attach(path)
    r.add(step, "Extra Tool 대상 SCP 수신 확인 (C-STORE Status + 파일, 체크리스트 Step2 결과)",
          PASS if res["ok"] else FAIL,
          expected="C-STORE 응답 Status 0000h + 수신 파일 1건 이상",
          actual=res["note"],
          note=_precondition_note(cfg))
    step += 1

    if xipl_log_dir:
        marks = xipl.find_marker(xipl_log_dir, xipl_marker, since=xipl_since)
        r.add(step, 'XIPL Server Log에서 %s 확인 (체크리스트 Step3)' % xipl_marker,
              PASS if marks else MANUAL,
              expected="전송 전후 XIPL Server Log에 %s 기록" % xipl_marker,
              actual="발견 %d줄%s" % (len(marks), (": " + marks[-1][:200]) if marks else ""),
              note="이 캡처 경로는 기본 처리부터 PureGrid.Apply=\"0\"이라(모듈 docstring "
                   "한계 참고), 이 확인은 '전송 전 재처리에서도 SBSC 미적용값이 로그에 "
                   "남는다'는 체크리스트 문구는 만족하지만 on→off 전환까지 증명하지는 "
                   "않는다.")
    else:
        r.add(step, "XIPL Server Log 확인", MANUAL,
              expected="config.json xipl.server_log_dir 설정",
              actual="설정 없음")
    step += 1

    # --- Step 4: 뷰어모드에서 기존 영상 선택 → Extra Tool 재클릭 -----------
    mark2 = _mark(cfg)
    W.select_first_image(ui)
    clicked2 = W.click_tool(ui, cfg, name="Extra Tool", section="tools",
                            evidence_dir=evidence_dir)
    r.add(step, "뷰어모드에서 기존 영상 선택 후 Extra Tool 재클릭 (체크리스트 Step4)",
          PASS if clicked2.get("ok") else FAIL,
          expected="이미 열려 있는(SBSC 처리된) 영상을 다시 선택해 Extra Tool 전송",
          actual="매칭=%s / 클릭 지점=%s" % (clicked2.get("matched"), clicked2.get("point")))
    step += 1
    if clicked2.get("ok"):
        if ET.uses_local_bunny(cfg):
            res2 = _wait_for_store(cfg, mark2, count=1, timeout=90, patient_id=want_id)
        else:
            prior_ts = ((res or {}).get("study") or {}).get("last_received_at")
            res2 = store_mod.wait_for_resend(cfg, want_id, prior_ts, timeout=90)
        for path in res2["files"]:
            r.attach(path)
        r.add(step, "재전송 수신 확인 (체크리스트 Step4 결과)",
              PASS if res2["ok"] else FAIL,
              expected="C-STORE 응답 Status 0000h + 수신 파일 1건 이상",
              actual=res2["note"])
        step += 1

    return r.finalize()
