# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_07 — DICOM Print.

실행: `python run.py tc07`

## 체크리스트 원문 (R-25-774, Checklist 시트 13행)

Precondition: *다른 PC 의 Server 이용 - Print SCP (JDICOM Print Server)*

Step Description: *1. 영상을 선택 후 Print server 로 전송한다.*
Expected Result: *1. Print 성공한다.*
Test Data: `http://<PRINT_SERVER_HOST>:8000/` / `PRINT_SCP` / `<PRINT_SERVER_HOST>` / `11113`

## 판정을 어디서 하는가 — 받은 쪽에서 한다

Expected Result가 "Print 성공한다"뿐이므로, 제품 UI의 Print Queue만 보면 **제품이
"보냈다"고 말한 것을 그대로 믿는 것**이 된다. 이 시험 Print SCP는 수신 필름
목록을 웹 API로 주므로 **받은 쪽에서 확인**한다(`core/printscp.py`).

```
GET /api/scp-status  -> {"running":true,"ae_title":"PRINT_SCP",...}
GET /api/jobs        -> [{"id":70,"calling_ae_title":"BELLALUN","film_size_id":"8INX10IN"},...]
```

`calling_ae_title`로 **VXvue가 보낸 필름만** 가려낸다 — 같은 서버를 Bellalun
자동화와 공유하고 있어(실측: BELLALUN 필름 8건 존재) 전체 목록으로 판정하면
다른 제품의 필름을 자기 결과로 착각한다. 기존 필름을 지우지 않으므로 다른
제품의 시험 자산도 건드리지 않는다.

## 실행 지점 (실측, 2026-08-19)

Print는 두 화면에서 시작할 수 있다.

- **Database 화면 `Print`(30293)** — 목록에서 스터디를 골라 바로 전송.
- **Print 화면(메인 네비 12, `CUIFilmManager`)** — 필름을 구성한 뒤 전송.
  상단 콤보가 평문으로 읽힌다: 서버 `30955`(=`PRINT_SC…`), 필름 크기
  `30956`(=`14INX17I…`), 방향 `30957`(=`Portrait`). 이 값들이 판정의 부가 근거다.

이 자동화는 **Print 화면의 설정을 먼저 읽어 근거로 남기고**, 전송은 촬영 직후
Exposure/Database 중 영상을 고를 수 있는 쪽에서 수행한다.
"""

import os
import time

from core import printscp
from core import workflow as W
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_07"
TC_TITLE = "DICOM Print (영상 선택 → Print server 전송 → 수신 필름 확인)"


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc07")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    ae = (cfg.get("dicom") or {}).get("local_ae_title", "VXVUE")
    url = (cfg.get("dicom") or {}).get("print_server_url")
    server = printscp.PrintServer(url) if url else None

    # --- Step 1: Print SCP 가동 확인 (Precondition) ---------------------
    if server is None:
        r.add(step, "Print SCP 가동 확인", MANUAL,
              note="config.json의 dicom.print_server_url이 비어 있어 수신 확인을 "
                   "할 수 없다. 이 값이 없으면 '보냈다'까지만 확인되고 'Print "
                   "성공'은 판정할 수 없다.")
        before_ids = set()
    else:
        running, detail = server.running()
        r.add(step, "Print SCP 가동 확인 (Precondition)",
              PASS if running else FAIL,
              expected="SCP running=true", actual=detail,
              note="체크리스트 Precondition의 'Print SCP (JDICOM Print Server)'에 "
                   "해당한다. 가동하지 않으면 이후 전송 판정이 무의미하다.")
        if not running:
            r.finalize()
            return r
        before = server.jobs_from(ae)
        before_ids = set(str(j.get("id")) for j in before)
        r.add(step + 1, "전송 전 기준선 — %s가 보낸 기존 필름" % ae, PASS,
              actual="기존 %d건 (id %s)" % (len(before), sorted(before_ids) or "없음"),
              note="기존 필름을 **지우지 않고** id로 걸러낸다 — 같은 시험 서버를 "
                   "Bellalun 자동화와 공유하므로 다른 제품의 자산을 건드리지 않는다.")
        step += 1
    step += 1

    # --- Step 2: Print 화면 설정 읽기 (부가 근거) -----------------------
    try:
        W.goto(ui, "print")
        time.sleep(1.5)
        combos = {}
        for name, cid in (("서버", W.PRINT_SERVER_COMBO),
                          ("필름 크기", W.PRINT_FILM_SIZE_COMBO),
                          ("방향", W.PRINT_ORIENTATION_COMBO)):
            hits = W.by_id(ui, cid)
            combos[name] = (hits[0].text or "").strip() if hits else "(컨트롤 없음)"
        r.add(step, "Print 화면의 전송 설정 확인",
              PASS if combos.get("서버", "").upper().startswith("PRINT") else MANUAL,
              expected="서버 콤보가 등록된 Print SCP를 가리킨다",
              actual=" / ".join("%s=%s" % (k, v) for k, v in combos.items()),
              note="Print 화면(CUIFilmManager)의 상단 콤보는 평문으로 읽힌다(실측) — "
                   "컨트롤 30955/30956/30957. 콤보 텍스트가 잘려 표시되므로 "
                   "(`PRINT_SC…`) 접두만 대조한다.")
    except Exception as exc:                              # noqa: BLE001
        r.add(step, "Print 화면의 전송 설정 확인", MANUAL, actual=str(exc))
    step += 1

    # --- Step 3: 전송할 영상 준비 --------------------------------------
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
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "전송할 영상 준비 (MWL 오픈 + 촬영)", FAIL, actual=str(exc))
            r.finalize()
            return r
        r.add(step, "전송할 영상 준비 (MWL 오픈 + Demo 촬영)",
              PASS if acq["acquired"] else FAIL,
              expected="영상 1장 이상 획득",
              actual="영상 %d → %d장 (%.1f초) / 처리한 팝업=%s"
                     % (acq["before"], acq["after"], acq["seconds"],
                        acq["dialogs"] or "없음"))
        if not acq["acquired"]:
            r.finalize()
            return r
    else:
        r.add(step, "전송할 영상 준비", SKIP,
              note="--no-acquire로 실행되어 이미 열려 있는 영상을 사용한다.")
    step += 1

    # --- Step 4: Print 전송 -------------------------------------------
    W.select_first_image(ui)
    printed = _click_print(ui, cfg, evidence_dir)
    r.add(step, "Print 실행",
          PASS if printed["clicked"] else FAIL,
          expected="Print 버튼 클릭 및 확인 팝업 처리",
          actual="누른 지점=%s / 처리한 팝업=%s"
                 % (printed["where"], printed["dialogs"] or "없음"),
          note=printed.get("note", ""))
    step += 1

    # --- Step 5: 수신 필름 확인 (핵심 판정) -----------------------------
    if server is None:
        r.add(step, "Print SCP 수신 필름 확인", MANUAL,
              note="Print 서버 URL이 없어 수신을 확인할 수 없다.")
    else:
        fresh, detail = server.wait_for_job(ae, exclude_ids=before_ids, timeout=120)
        r.add(step, "Print SCP가 %s의 신규 필름을 수신" % ae,
              PASS if fresh else FAIL,
              expected="Calling AE=%s 필름 1건 이상 신규 수신" % ae,
              actual=detail,
              note="제품 UI의 Queue가 아니라 **받은 쪽 서버의 필름 목록**으로 "
                   "판정한다 — 'Print 성공'의 유일한 객관적 근거다. "
                   + printscp_note(cfg))
        if fresh:
            r.add(step + 1, "수신 필름의 속성", PASS,
                  actual="; ".join("id=%s size=%s at=%s"
                                   % (j.get("id"), j.get("film_size_id"),
                                      j.get("received_at")) for j in fresh))
            step += 1
    step += 1

    r.finalize()
    return r


def printscp_note(cfg):
    ip = None
    for spec in ((cfg.get("dicom") or {}).get("servers_to_register") or []):
        if spec.get("kind") == "Print":
            ip = "%s %s:%s" % (spec.get("ae_title"), spec.get("ip"), spec.get("port"))
    return ("Print SCP는 체크리스트 Precondition대로 **다른 PC**(%s)에 있다 — "
            "Storage와 달리 이 조건은 충족한다." % (ip or "config 확인 필요"))


def _click_print(ui, cfg, evidence_dir):
    """Print를 실행한다. Database 화면의 Print(30293)를 우선 시도한다.

    **Database > Print는 두 번의 확인이 필요하다**(실측 2026-08-21, 이전
    버전은 첫 번째만 처리해 '클릭은 했지만 아무것도 전송되지 않는' 거짓양성이
    났다).

    1. Print(30293)를 누르면 'Do you want to print all images of the selected
       study?' 확인 팝업이 뜬다 — Send 팝업과 같은 버튼 ID(`27002`/27001/27000)를
       쓴다(실측: 팝업의 자식 컨트롤을 그 자리에서 덤프해 확인).
    2. 그 팝업에서 All Images(27002)를 누르면 필름 구성 화면(CUIFilmManager)으로
       전환되는데, **여기서 Print(`30718`)를 다시 눌러야** Print SCP로 실제
       전송된다. 이 두 번째 클릭 없이는 필름 구성만 되고 수신 쪽에는 아무것도
       도착하지 않는다(실측: Print SCP 필름 0건 → 30718 클릭 후 2건 수신 확인).
    """
    out = {"clicked": False, "where": "", "dialogs": [], "note": ""}

    # Database 화면에 목록이 있으면 그쪽에서(스터디 단위 전송)
    try:
        W.database_search(ui)
        rows = W.list_rows(ui, W.DB_LIST)
        if rows:
            W.click_row(ui, rows[0])
            W.db_button(ui, "print")
            confirm = W.confirm_scope_popup(ui, scope="all")
            finish = W.finish_print(ui, button="print")
            out.update(clicked=bool(finish["clicked"]),
                       where="Database > Print(30293) -> 확인 팝업(%s) -> "
                             "Film Manager Print(%s)"
                             % (confirm["clicked"], finish["clicked"]))
            if not confirm["dialog"]:
                out["note"] += " 확인 팝업이 나타나지 않았다."
            if not finish["clicked"]:
                out["note"] += " Film Manager의 Print(30718)를 찾지 못했다."
    except Exception as exc:                              # noqa: BLE001
        out["note"] = "Database 경로 실패: %s" % exc

    if not out["clicked"]:
        # Database 목록이 비어 있으면(TC02에서 확인한 '완료된 검사만 표시' 제약)
        # Print 화면에서 곧바로 전송한다(이 화면은 확인 팝업 없이 30718/30719가
        # 최종 전송 버튼이다 — 위 Database 경로와 같은 화면으로 수렴한다).
        try:
            W.goto(ui, "print")
            time.sleep(1.5)
            finish = W.finish_print(ui, button="print")
            if finish["clicked"]:
                out.update(clicked=True,
                           where="Print 화면 Print(%d)" % finish["clicked"])
                out["note"] += (" Database 목록이 비어 Print 화면에서 직접 실행했다"
                                "(30718='Print', 30719='Print & Close' — "
                                "캡처+OCR로 확정, 2026-08-19/21).")
        except Exception as exc:                          # noqa: BLE001
            out["note"] += " Print 화면 경로 실패: %s" % exc

    out["dialogs"] = W.pending_dialogs(ui, evidence_dir=evidence_dir, cfg=cfg)
    return out
