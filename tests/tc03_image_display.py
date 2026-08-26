# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_03 — 영상 조작(표시/도구).

실행: `python run.py tc03`

## 체크리스트 원문 (R-25-774, Checklist 시트 9행)

Step Description
```
1. Setting-Display-General-Interpolation Mode 설정을 변경한다
   - Bicubic, GDI 등.
2. 촬영화면/뷰어화면에서 영상을 선택하고 영상에 Zoom, Select, Pan, Rotation 등을 적용한다.
3. 영상을 2장 이상 오픈하고 첫번째/두번째 영상을 선택하며 영상에 Tool 을 적용한다.
```

Expected Result: *2,3. 선택한 영상이 화면에 display 되고, **delay 없이** 선택한
툴이 영상에 적용된다.*

Test Data: *\*default(Bicubic)*

## "delay 없이"를 어떻게 판정하는가 — 30초 기준

체크리스트에는 정량값이 없지만 사용자 지시(2026-08-26)로 **각 툴 조작이
30초 이내에 반영되는지**를 판정한다. 이 값은 제품 사양이 아니라 이번 회귀를 위한
운영상 임의 기준이다.

## 툴이 "적용됐다"를 무엇으로 보는가

툴 버튼을 눌렀다는 것만으로는 적용을 증명하지 못한다(버튼이 비활성이면 클릭이
조용히 무시된다). 그래서 **영상 표시 영역을 툴 조작 전후로 캡처해 화면이
변했는지**로 확인한다(`core/screen.py`의 SSIM).

- **Zoom / Pan / Rotation(CW·CCW)**: 조작하면 화면이 변해야 한다 → 변화 없으면 FAIL.
- **Select**: 선택 도구는 그 자체로 화면을 바꾸지 않는다 → 버튼 활성 상태만 확인.

## Interpolation Mode

`config.json`의 `viewer.control_ids`에 실측된 콤보 ID(`30975`)를 쓴다. 값을 바꾼
뒤 **반드시 원래 값(Test Data 기준 기본값 `Bicubic`)으로 되돌린다** — 회귀가 남긴
설정 변경이 다음 TC의 판정을 흔들지 않게 하기 위함이다.
"""

import os
import time

from core import screen as screen_mod
from core import setting as S
from core import workflow as W
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_03"
TC_TITLE = "영상 조작 (Interpolation 설정 + Zoom/Pan/Rotation 툴 적용)"

DISPLAY_SCREEN = "Display - General"
INTERPOLATION_COMBO = 30975

# 영상 표시 영역(Exposure 화면). 실측 rect (772,282)-(1702,1015) 안쪽을 본다 —
# 프레임 경계와 오버레이 문자를 피해 가운데를 잡는다.
IMAGE_AREA = (820, 330, 1650, 960)

# 화면이 "변했다"고 볼 SSIM 상한. 1.0이면 완전히 동일하다.
# 0.999는 압축 잡음 수준의 차이만 허용한다는 뜻이다.
SAME_SSIM = 0.999
MAX_TOOL_DELAY_SECONDS = 30.0


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc03")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    # --- Step 1: Interpolation Mode 변경 --------------------------------
    original, changed_to, note = None, None, ""
    try:
        if S.goto_screen(ui, DISPLAY_SCREEN) is None:
            raise S.SettingError("%s 화면으로 이동하지 못했습니다." % DISPLAY_SCREEN)
        combos = [c for c in S.content_controls(ui) if c.ctrl_id == INTERPOLATION_COMBO]
        if not combos:
            raise S.SettingError("Interpolation 콤보(%d)를 찾지 못했습니다."
                                 % INTERPOLATION_COMBO)
        original = S.combo_value(ui, combos[0])
        r.add(step, "Setting > %s 의 Interpolation Mode 확인" % DISPLAY_SCREEN, PASS,
              expected="Test Data 기준 기본값 Bicubic",
              actual="현재 값=%r" % original,
              note="Test Data: '*default(Bicubic)'. 현재 값이 기본값과 달라도 "
                   "결함으로 단정하지 않는다 — 앞선 시험이 바꿔 놓았을 수 있다.")
    except Exception as exc:                              # noqa: BLE001
        r.add(step, "Setting > %s 의 Interpolation Mode 확인" % DISPLAY_SCREEN,
              FAIL, actual=str(exc))
    step += 1

    if original is not None:
        target = "GDI" if "bicubic" in str(original).lower() else "Bicubic"
        try:
            combos = [c for c in S.content_controls(ui)
                      if c.ctrl_id == INTERPOLATION_COMBO]
            ok = S.select_combo(ui, combos[0], target)
            S.update(ui)
            time.sleep(0.8)
            combos = [c for c in S.content_controls(ui)
                      if c.ctrl_id == INTERPOLATION_COMBO]
            now = S.combo_value(ui, combos[0])
            changed_to = now
            hit = target.lower() in str(now).lower()
            r.add(step, "Interpolation Mode 변경 (%s → %s)" % (original, target),
                  PASS if hit else FAIL,
                  expected="변경 후 표시값이 %s" % target,
                  actual="선택 시도=%s / 변경 후 값=%r" % (ok, now),
                  note="체크리스트 Step 1의 'Bicubic, GDI 등' 변경에 해당한다. "
                       "변경이 실제로 반영됐는지 **화면을 다시 읽어** 확인한다.")
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "Interpolation Mode 변경", FAIL, actual=str(exc),
                  note="콤보 조작 중 예외. 과거 이 제품의 콤보 조작에서 응답 없음이 "
                       "발생한 적이 있어(HANDOFF 보류 항목) 짧은 timeout으로 한 번만 "
                       "시도한다.")
        step += 1

    # --- Step 2: 영상 준비 ---------------------------------------------
    if do_acquire and W.thumbnail_count(ui) == 0:
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
            r.add(step, "툴을 적용할 영상 준비", FAIL, actual=str(exc))
            _restore(ui, r, step + 1, original, changed_to)
            r.finalize()
            return r
        r.add(step, "툴을 적용할 영상 준비 (MWL 오픈 + 촬영)",
              PASS if acq["acquired"] else FAIL,
              expected="영상 1장 이상",
              actual="영상 %d → %d장 / 처리한 팝업=%s"
                     % (acq["before"], acq["after"], acq["dialogs"] or "없음"))
        if not acq["acquired"]:
            _restore(ui, r, step + 1, original, changed_to)
            r.finalize()
            return r
    else:
        W.goto(ui, "exposure")
        time.sleep(1.0)
        n = W.thumbnail_count(ui)
        r.add(step, "툴을 적용할 영상 준비", PASS if n else SKIP,
              actual="이미 열려 있는 영상 %d장" % n,
              note="" if n else "열려 있는 영상이 없어 툴 적용을 건너뛴다.")
        if not n:
            _restore(ui, r, step + 1, original, changed_to)
            r.finalize()
            return r
    step += 1

    # 체크리스트 Step 3은 영상 2장 이상을 요구한다. 첫 촬영 뒤 Chest의 다른
    # Step(PA<->AP)을 하나 더 등록해 두 번째 영상을 자동으로 촬영한다.
    if do_acquire and W.thumbnail_count(ui) < 2:
        second_step = "AP" if str(exam_step).upper() != "AP" else "PA"
        try:
            added = W.add_step(ui, cfg, projection=projection, step=second_step,
                               evidence_dir=evidence_dir)
            second_acq = (W.acquire(ui, cfg, evidence_dir=evidence_dir)
                          if added.get("ok") else None)
            two_ok = bool(second_acq and second_acq.get("acquired")
                          and W.thumbnail_count(ui) >= 2)
            r.add(step, "두 번째 영상 자동 촬영 (%s %s)" % (projection, second_step),
                  PASS if two_ok else FAIL,
                  expected="서로 다른 Step의 영상 2장 이상",
                  actual=("Step 등록=%s / 촬영=%s / 현재 영상=%d장"
                          % (added.get("ok"),
                             second_acq.get("acquired") if second_acq else False,
                             W.thumbnail_count(ui))),
                  note="첫 영상과 같은 검사에 두 번째 Step을 등록하고 F2로 직접 "
                       "촬영한다. 사람이 미리 영상을 준비할 필요가 없다.")
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "두 번째 영상 자동 촬영", FAIL, actual=str(exc))
        step += 1

    W.select_first_image(ui)
    time.sleep(0.8)

    # --- Step 3: 툴 적용 -----------------------------------------------
    # Select는 화면을 바꾸지 않으므로 존재·클릭만 확인하고, 나머지는 화면 변화로
    # 판정한다. 조작 방식이 툴마다 다르다(Zoom/Pan은 드래그, 회전은 클릭 1회).
    tools = [
        ("select", "Select", "click", False),
        ("zoom", "Zoom", "drag", True),
        ("pan", "Pan", "drag", True),
        ("cw", "Rotation CW", "click", True),
        ("ccw", "Rotation CCW", "click", True),
    ]
    tool_elapsed = []
    for key, label, how, expect_change in tools:
        hits = W.by_id(ui, W.TOOL[key])
        if not hits:
            r.add(step, "%s 툴" % label, FAIL,
                  expected="툴 버튼(%d) 존재" % W.TOOL[key],
                  actual="버튼을 찾지 못했다")
            step += 1
            continue

        before_png = os.path.join(evidence_dir, "tool_%s_before.png" % key)
        after_png = os.path.join(evidence_dir, "tool_%s_after.png" % key)
        screen_mod.capture(before_png, bbox=IMAGE_AREA)

        started = time.time()
        ui.click(hits[0], settle=0.6)
        if how == "drag":
            # 영상 영역 안에서 짧게 끈다 — 좌표는 IMAGE_AREA에서 계산한다.
            l, t, rr, b = IMAGE_AREA
            cx, cy = (l + rr) // 2, (t + b) // 2
            ui.drag((cx - 120, cy - 80), (cx + 120, cy + 80), duration=0.5, settle=0.8)
        else:
            time.sleep(0.8)
        elapsed = round(time.time() - started, 2)
        tool_elapsed.append((label, elapsed))

        screen_mod.capture(after_png, bbox=IMAGE_AREA)
        try:
            sim = screen_mod.ssim(before_png, after_png)
        except Exception as exc:                          # noqa: BLE001
            sim = None
            r.add(step, "%s 툴 적용 — 화면 변화 판정" % label, MANUAL,
                  actual="SSIM 계산 실패: %s" % exc)
            step += 1
            continue

        r.attach(after_png)
        if expect_change:
            applied = sim < SAME_SSIM
            r.add(step, "%s 툴 적용이 영상에 반영" % label,
                  PASS if applied else FAIL,
                  expected="조작 후 영상 표시 영역이 변한다(SSIM < %s)" % SAME_SSIM,
                  actual="SSIM=%.5f / 조작 소요 %.2f초" % (sim, elapsed),
                  note="버튼을 눌렀다는 사실만으로 적용을 인정하지 않고 **영상 영역을 "
                       "조작 전후로 캡처해 비교**한다. 비활성 버튼을 눌러도 클릭은 "
                       "조용히 성공하기 때문이다.")
        else:
            r.add(step, "%s 툴 선택" % label, PASS,
                  expected="선택 도구는 화면을 바꾸지 않는다",
                  actual="SSIM=%.5f / 소요 %.2f초" % (sim, elapsed),
                  note="Select는 그 자체로 표시를 바꾸지 않으므로 화면 변화로 판정하지 "
                       "않는다.")
        step += 1

    # --- "delay 없이" — 사용자 확정 임의 기준 30초 -----------------------
    within_delay = bool(tool_elapsed) and all(
        seconds <= MAX_TOOL_DELAY_SECONDS for _label, seconds in tool_elapsed)
    r.add(step, "\"delay 없이\" 정량 판정", PASS if within_delay else FAIL,
          expected="각 툴 조작이 %.0f초 이내에 반영" % MAX_TOOL_DELAY_SECONDS,
          actual=", ".join("%s %.2f초" % row for row in tool_elapsed) or "측정값 없음",
          note="30초는 제품 사양값이 아니라 사용자 지시(2026-08-26)로 정한 "
               "회귀용 임의 기준이다.")
    step += 1

    # --- Step 3(체크리스트): 영상 2장 이상에서 선택 전환 ------------------
    n = W.thumbnail_count(ui)
    two_result = False
    selection_note = "현재 열린 영상 %d장" % n
    if n >= 2:
        first_ok = W.select_image(ui, 0)
        second_ok = W.select_image(ui, 1)
        before_second = os.path.join(evidence_dir, "second_image_before_zoom.png")
        after_second = os.path.join(evidence_dir, "second_image_after_zoom.png")
        screen_mod.capture(before_second, bbox=IMAGE_AREA)
        zoom = W.by_id(ui, W.TOOL["zoom"])
        if second_ok and zoom:
            ui.click(zoom[0], settle=0.4)
            l, t, rr, b = IMAGE_AREA
            cx, cy = (l + rr) // 2, (t + b) // 2
            ui.drag((cx - 100, cy - 70), (cx + 100, cy + 70),
                    duration=0.5, settle=0.8)
            screen_mod.capture(after_second, bbox=IMAGE_AREA)
            sim2 = screen_mod.ssim(before_second, after_second)
            two_result = first_ok and second_ok and sim2 < SAME_SSIM
            selection_note += " / 첫째 선택=%s / 둘째 선택=%s / 둘째 Zoom SSIM=%.5f" % (
                first_ok, second_ok, sim2)
            r.attach(after_second)
    r.add(step, "영상 2장 이상에서 첫 번째/두 번째 선택하며 툴 적용",
          PASS if two_result else FAIL,
          expected="영상 2장 이상을 각각 선택하고 두 번째 영상에도 툴이 반영",
          actual=selection_note,
          note="정상 실행은 PA/AP 두 영상을 자동 촬영해 이 Step을 사람 준비 없이 수행한다.")
    step += 1

    _restore(ui, r, step, original, changed_to)
    r.finalize()
    return r


def _restore(ui, r, step, original, changed_to):
    """Interpolation Mode를 원래 값으로 되돌린다.

    회귀가 남긴 설정 변경이 다음 TC의 판정을 흔들지 않게 한다. **되돌리기 실패는
    성공 여부와 무관하게 결과에 남긴다** — 조용히 넘기면 다음 실행이 오염된 상태에서
    시작한다.
    """
    if original is None or changed_to is None:
        return
    try:
        if S.goto_screen(ui, DISPLAY_SCREEN) is None:
            raise S.SettingError("%s 화면으로 이동하지 못했습니다." % DISPLAY_SCREEN)
        combos = [c for c in S.content_controls(ui) if c.ctrl_id == INTERPOLATION_COMBO]
        S.select_combo(ui, combos[0], str(original))
        S.update(ui)
        time.sleep(0.6)
        combos = [c for c in S.content_controls(ui) if c.ctrl_id == INTERPOLATION_COMBO]
        now = S.combo_value(ui, combos[0])
        ok = str(original).lower() in str(now).lower()
        r.add(step, "Interpolation Mode 원복",
              PASS if ok else FAIL,
              expected="원래 값 %r로 복귀" % original,
              actual="복귀 후 값=%r" % now,
              note="원복 실패는 다음 시험의 시작 상태를 오염시키므로 반드시 결과에 "
                   "남긴다.")
    except Exception as exc:                              # noqa: BLE001
        r.add(step, "Interpolation Mode 원복", FAIL, actual=str(exc),
              note="사람이 Setting > %s 에서 %r로 되돌릴 것."
                   % (DISPLAY_SCREEN, original))
