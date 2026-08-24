# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_11 — AI 분석(CAD).

실행: `python run.py tc11`

## 체크리스트 원문 (R-25-774, Checklist 시트)

Precondition: *인체용 뷰어* / 샘플 경로 `\\10.1.1.100\...\AI_VUNO_VXCAD\샘플`

Step Description
```
1. 뷰어 신규 설치
2. VXvue Option-AI 라이선스 추가, VXSetup에서 AI 사용 설정
3. XIPL에 VX CAD 라이선스 추가
4. 뷰어 실행
5. 영상 촬영 후 AI Tool 버튼 클릭
6. Request an analysis 선택
```

Expected Result: *5. 신규 설치 후 AI Tool 최초 실행 시 Serialization 진행
(GPU) 'Have to Data load for using. It takes a few minutes' 팝업 → Yes
클릭 시 Serialization 진행 → 완료 후 AI Medical findings tool 창 표시.
6. AI 분석 실시, 결과가 영상 위에 표시됨.*

Test Data: *동물용 뷰어는 기능 미제공 / GPU가 있는 경우에만 Serialization
진행 / Serialization 16분 정도 소요*

## 이 자동화가 검증하는 것과 SKIP하는 것

`automation_scope.json`에 이미 기록된 설계(2026-08-18)대로: 이 PC는 GPU가
없다(Intel Iris Xe 내장 그래픽뿐). 사양서2(260820) p.149-150 VP-616 근거
(2026-08-21 문서 조사) — Serialization은 "GPU 환경에서 처음 연동"할 때만
걸리는 절차이고, CPU 모드(VUNO CXR(CPU))는 정식으로 지원되는 옵션이라
Serialization 없이 분석 화면으로 진입한다. 그래서:

- **자동화 대상**: AI Tool 버튼이 실제로 존재하고 눌리는지, 그 결과
  Operation Manual이 말하는 "AI Medical findings tool" 창이 실제로
  열리는지, 그 창의 구성(Request an analysis 버튼, VP-616이 규정한
  옵션 체크박스 3종)이 사양과 일치하는지 — **UI 흐름과 화면 구조**.
- **SKIP**: "Request an analysis"를 실제로 눌러 분석 결과를 얻는 것.
  GPU 없는 이 환경에서 CPU 모드 분석이 실제로 수행되는지, 얼마나 걸리는지,
  결과가 영상 위에 어떻게 표시되는지는 **결과물 생성 자체를 검증하지
  않는다**(automation_scope.json 기존 방침과 동일 — Bellalun 자동화의
  GPU 의존 케이스와 같은 처리). 잘못 눌러 알 수 없는 대기·오류로 빠지는
  위험을 피하기 위해 이번 세션에서는 누르지 않았다.

## AI Tool 버튼 위치 (실측 2026-08-21)

`core/workflow.py`의 툴 팝업 판독(`read_tool_palette`)은 `section="tools"`
전용으로 검색 영역이 고정돼 있었다(`_PALETTE_SEARCH`) — `section=
"annotation"`(AI Tool이 있는 곳)의 팝업은 화면 위치가 달라 그 영역
밖에서 잘렸다. `read_tool_palette()`에 `search_area` 인자를 추가해
`_palette_area(_section_button(ui, "annotation"))`으로 그 버튼 기준
영역을 계산하도록 고쳤다(이 파일과 `core/workflow.py` 양쪽에서 재사용).

OCR로 "AI Tool" 라벨 자체를 안정적으로 못 읽는 문제도 실측했다(8px 라벨 +
아이콘 조합이라 "Extra Tool" 등으로 오인식). 그래서 좌우로 **표준 API로
안정적으로 읽히는 두 라벨(Ellipse/Circle/Delete)의 실제 좌표로 격자
칸 너비를 구해 AI Tool(3번째 칸) 위치를 보간**한다 — 이 팝업이 5칸
고정 그리드라는 것은 이미 화면 캡처로 실측 확인했으므로(2026-08-21),
"구조는 속성으로 확정한 뒤 그 안에서 위치를 계산"하는 CLAUDE.md 3절
2순위 규칙에 맞는다(고정 좌표를 저장해두지 않고, 매번 다시 읽은
Ellipse/Circle/Delete 좌표로 다시 계산한다).
"""

import os
import time

from core import license as license_mod
from core import workflow as W
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_11"
TC_TITLE = "AI 분석(CAD) — AI Tool 버튼 -> AI Medical findings tool 창 확인"

ANNOTATION_SECTION = "annotation"
AI_TOOL_DIALOG_TITLE = "AI Medical findings tool"
REQUEST_ANALYSIS_BUTTON_ID = 30736
# VP-616(사양서2 p.150-152) 옵션 3종 — 실측(2026-08-21)으로 라벨과 ID까지 확인.
AI_OPTION_CHECKBOXES = {
    31509: "Insert findings name",
    31510: "Insert probability text",
    31512: "Copy original image",
}
AI_CLOSE_ICON_ID = -4


def _find_ai_tool_point(ui, cfg, evidence_dir):
    """annotation 팝업에서 Ellipse/Circle/Delete 좌표로 AI Tool(3번째 칸) 위치를 보간한다."""
    btn = W._section_button(ui, ANNOTATION_SECTION)
    if btn is None:
        return None, None, "annotation 섹션 ≡ 버튼을 찾지 못함"
    area = W._palette_area(btn)
    palette = W.read_tool_palette(ui, cfg, section=ANNOTATION_SECTION,
                                  evidence_dir=evidence_dir, refresh=True,
                                  search_area=area)
    if "AI Tool" in palette:
        return btn, palette["AI Tool"], "OCR로 직접 읽음: %s" % sorted(palette)
    ellipse, circle, delete = palette.get("Ellipse"), palette.get("Circle"), palette.get("Delete")
    if not (ellipse and circle and delete):
        return None, None, "보간에 필요한 기준 라벨(Ellipse/Circle/Delete)을 못 읽음(읽힌 것: %s)" % sorted(palette)
    step = (delete[0] - circle[0]) / 3.0
    point = (circle[0] + step, (circle[1] + delete[1]) / 2.0)
    return btn, point, ("직접 매칭 실패(읽힌 라벨: %s) — Ellipse=%s/Circle=%s/Delete=%s 기준 "
                        "3번째 칸으로 보간: %s" % (sorted(palette), ellipse, circle, delete, point))


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc11")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    # --- Step 1: VXvue 본체 CAD 라이선스 (Precondition) ------------------
    data_dir = cfg.get("data_dir") or ""
    files = license_mod.license_files(data_dir) if data_dir else []
    cad_present = any(True for f in files)  # 종류 판별은 VXvue_License가 이미 함
    r.add(step, "VXvue Option(Computer Aided Detection) 라이선스 (Precondition)",
          PASS if files else MANUAL,
          expected="사양서5 p.63~64 VP-770 — AI Engine 사용 위해 필요",
          actual="라이선스 파일 %d개 확인" % len(files) if files else "확인 불가(data_dir 미설정)",
          note="종류별 상세 대조(Demo/CAD/LiveView)는 VXvue_License 항목이 담당한다. "
               "이 Step은 이 TC 단독 실행 시에도 선행 조건이 충족됐는지 참고로만 본다.")
    step += 1

    # --- Step 2: 촬영 ------------------------------------------------------
    if do_acquire:
        try:
            flow = W.open_and_acquire(
                ui, cfg,
                patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"),
                projection=projection, step=exam_step,
                evidence_dir=evidence_dir, map_procedure_name=map_procedure)
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "AI 분석용 영상 준비 (MWL 오픈 + Demo 촬영)", FAIL, actual=str(exc))
            r.finalize()
            return r
        acq = flow["acquire"] or {}
        r.add(step, "AI 분석용 영상 준비 (MWL 오픈 + Demo 촬영)",
              PASS if acq.get("acquired") else FAIL,
              expected="영상 1장 이상 획득",
              actual="INSTANCE %s → %s / %.1f초"
                     % (acq.get("instances_before"), acq.get("instances_after"),
                        acq.get("seconds", 0)))
        if not acq.get("acquired"):
            r.finalize()
            return r
    else:
        r.add(step, "AI 분석용 영상 준비", SKIP,
              note="--no-acquire로 실행되어 이미 열려 있는 영상을 사용한다.")
    step += 1

    in_viewer = W.viewer_mode(ui, cfg)
    r.assert_true(step, "Viewer 모드 전환(Tools 패널 노출)", in_viewer,
                  expected="Tools 섹션 ≡ 노출", actual="전환 성공" if in_viewer else "전환 실패")
    if not in_viewer:
        r.finalize()
        return r
    step += 1

    # --- Step 3: AI Tool 버튼 클릭 -> AI Medical findings tool 창 ---------
    btn, point, note = _find_ai_tool_point(ui, cfg, evidence_dir)
    if point is None:
        r.add(step, "annotation 팝업에서 AI Tool 위치 확인", MANUAL,
              expected="AI Tool 버튼 좌표 확보", actual=note)
        r.finalize()
        return r
    r.add(step, "annotation 팝업에서 AI Tool 위치 확인", PASS,
          expected="AI Tool 버튼 좌표 확보(사양서2 p.150 VP-616)", actual=note)
    step += 1

    from core.ui import children

    # 실측(2026-08-21): 이 창을 코드가 못 찾고 끝내면(예외·타임아웃) 창이
    # 열린 채로 남아 **다음 실행의 화면 전환을 막는다**(실측: Registration
    # 탭 전환 15초 타임아웃으로 재현됨) — 그래서 여기서부터는 무슨 일이
    # 있어도 `finally`에서 닫기를 시도한다. `core/dialogs.py`의 범용
    # 팝업 정리(QUESTION으로 분류돼 아무 버튼이나 눌림)에 맡기면 이 창은
    # 실제로 닫히지 않는다(실측 확인) — 이 파일이 직접 책임진다.
    dlg = None
    try:
        # 실측(2026-08-24): 같은 좌표·같은 settle로 클릭해도 간헐적으로 창이
        # 안 뜨는 사례가 있었다 — 원인은 `read_tool_palette()`(위 Step에서
        # `_find_ai_tool_point()`가 호출) 자체 docstring에 이미 적혀 있었다:
        # "팝업은 약 2.1초 뒤 스스로 닫힌다"(0.32s 열림 → 2.42s 닫힘). 그
        # 팝업이 아직 열려 있는 상태에서 여기서 `ui.click(btn, ...)`을 또
        # 누르면 **토글로 오히려 팝업이 닫혀버리고**, 뒤이은 `click(point)`은
        # 빈 화면(영상 표시 영역)을 누르는 셀이 된다 — OCR/보간 처리 속도가
        # 매번 달라 팝업이 아직 열려 있을 때도, 이미 닫혔을 때도 있어
        # 간헐적으로 재현됐다. **팝업이 확실히 닫힌 뒤 다시 여는 것**으로
        # 이 경쟁 상태를 없앤다(추측이 아니라 팝업 자체의 실측 수명 2.42초
        # 근거). 그래도 안 뜨면 최대 3회까지 재시도한다.
        MAX_ATTEMPTS = 3
        attempts = 0
        for attempts in range(1, MAX_ATTEMPTS + 1):
            if attempts > 1:
                _, retry_point, _ = _find_ai_tool_point(ui, cfg, evidence_dir)
                if retry_point is None:
                    break
                point = retry_point
            time.sleep(2.5)  # 팝업이 스스로 닫히는 걸 확실히 기다린 뒤 다시 연다
            ui.click(btn, settle=0.05)
            time.sleep(W.PALETTE_OPEN_DELAY)
            ui.click(point, settle=2.5)

            # `ui.dialog_text()`는 창 제목이 아니라 **내부 Static 라벨**(예:
            # "Dog Normal Variation ...", "VHS: ")을 이어붙인 값을 돌려준다 —
            # 창 제목과 비교하면 항상 어긋난다(실측). `ui.dialog(title=...)`가
            # 창의 `text`(=제목, `_text_of(hwnd)`)로 직접 거른다.
            end = time.time() + 8
            while time.time() < end:
                d = ui.dialog(title=AI_TOOL_DIALOG_TITLE)
                if d is not None:
                    dlg = d
                    break
                time.sleep(0.4)
            if dlg is not None:
                break
        r.assert_true(step, "AI Tool 클릭 -> 'AI Medical findings tool' 창 표시", dlg is not None,
                      expected="Operation Manual 근거 — AI Tool 클릭 시 이 창이 뜬다",
                      actual=("표시됨(%d번째 시도)" % attempts) if dlg is not None
                             else "%d회 재시도(각 8초 대기)에도 나타나지 않음" % MAX_ATTEMPTS,
                      note=("" if attempts == 1 else
                            "1회차에 뜨지 않아 재시도했다 — 같은 좌표/설정으로 클릭이 "
                            "간헐적으로 반응하지 않는 사례를 진단 스크립트로 재현한 바 "
                            "있다(2026-08-24). 여러 번 재현되면 원인을 더 조사할 것."))
        step += 1

        if dlg is not None:
            kids = children(dlg.hwnd, 5)
            req_btn = next((c for c in kids if c.ctrl_id == REQUEST_ANALYSIS_BUTTON_ID and c.visible), None)
            r.assert_true(step, "'Request an analysis' 버튼 존재", req_btn is not None,
                          expected="체크리스트 Step6 근거", actual="존재" if req_btn is not None else "찾지 못함")
            step += 1

            found_opts = [label for cid, label in AI_OPTION_CHECKBOXES.items()
                         if any(c.ctrl_id == cid and c.visible for c in kids)]
            r.assert_true(step, "AI 결과 표시 옵션 체크박스 3종 확인",
                          len(found_opts) == len(AI_OPTION_CHECKBOXES),
                          expected="사양서2 p.150-152 VP-616: %s" % ", ".join(AI_OPTION_CHECKBOXES.values()),
                          actual="확인됨: %s" % (", ".join(found_opts) or "없음"))
            step += 1

            r.manual(step, "'Request an analysis' 실행 및 분석 결과 검증",
                     "이 PC는 GPU가 없다(Intel Iris Xe 내장 그래픽만) — automation_scope.json "
                     "기존 방침대로 결과물 생성 자체는 검증하지 않고 SKIP한다. 사양서2 p.149-150 "
                     "VP-616 근거: Serialization은 'GPU 환경에서 처음 연동'할 때만 걸리는 절차이고 "
                     "CPU 모드(VUNO CXR(CPU))는 정식 지원 옵션이라 이론상 Serialization 팝업 없이 "
                     "분석이 가능하지만, 내장 GPU가 사양서상 'GPU 환경'으로 인정되는지는 문서상 "
                     "확인되지 않는다 — 실제로 눌러 어떤 대기·오류가 나는지는 사람이 판단할 것.")
            step += 1
    finally:
        # 못 찾았어도(늦게 뜨는 경우 실측됨) 한 번 더 찾아서 닫는다.
        target = dlg or ui.dialog(title=AI_TOOL_DIALOG_TITLE)
        if target is not None:
            close_icon = next((c for c in children(target.hwnd, 1)
                               if c.ctrl_id == AI_CLOSE_ICON_ID), None)
            if close_icon is not None:
                ui.click(close_icon, settle=1.0)
        closed = ui.dialog(title=AI_TOOL_DIALOG_TITLE) is None
        r.assert_true(step, "AI Tool 창 닫기", closed,
                      expected="창 닫힘",
                      actual="닫힘 확인" if closed else "닫히지 않음 — 사람 확인 필요")

    return r.finalize()
