# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_12 — 카메라/Live View 연동 확인(시마주).

실행: `python run.py tc12`

## 체크리스트 원문 (R-25-774, Checklist 시트)

Precondition: *1.VXvue 라이선스 추가: VXvue Option-Live view /
2.VXSetup 실행 후 Use Live View 체크후 저장* / 패키지 경로
`\\10.1.1.100\...\VX.LIVE.SERVER`

Step Description
```
1. VX.LIVE.SERVER.exe 설치
2. C:\VX.LIVE.SERVER\test_image 폴더 생성, .jpg 파일 저장(DEMO 파일 저장)
3. 뷰어 실행, Live View 버튼 클릭
4. Setting-Integration-Camera-Step Analysis:Yes 설정, 촬영화면에서
   Step 등록 후 live view 화면 확인
5. DICOM 전송 옵션에서 Include Snapshot Image 설정, 영상 전송
```

Expected Result
```
3. 라이브 뷰 화면 오픈, 실시간 카메라 영상 표시(데모영상 display).
4. 분석 지원 Step인 경우 카메라 영상과 촬영할 Step 정보 일치 여부 표시
   — 일치: 초록 테두리 / 불일치: 빨간 테두리+'Not Matched' /
   미지원 Step: 테두리·문구 없음.
5. 촬영 시 썸네일에 카메라 아이콘 표시, 클릭 시 스냅샷 표시,
   Storage Queue에 Image·Snapshot type이 각각 추가/전송.
```

## 이 자동화가 검증하는 것 (2026-08-21 실측)

선행 조건은 automation_scope.json에 이미 기록돼 있다 — VX.LIVE.SERVER
1.1.0.1 설치 + DEMO 트리거 파일 + Live View 옵션 라이선스 적용 +
`<Camera UseLiveView="1"/>`. 이번 세션에 실제로 **Live View 버튼을 눌러
화면이 뜨고 데모 영상이 재생되는 것까지** 라이브로 확인했다(Step3 전체).

- Live View 버튼(`core/workflow.py`의 `Tools` 팝업, 이미 `KNOWN_TOOLS`에
  있음)을 누르면 **VXvue와 다른 프로세스(VX.LIVE.VIEW 계열)가 소유한
  별도 최상위 창**("MainView")이 VXvue의 영상 표시 영역과 정확히 같은
  좌표에 겹쳐 뜬다(실측: 두 rect가 `(10,80)-(1373,1015)`로 동일) —
  임베드가 아니라 오버레이 창이다. 이 창은 `EnumChildWindows`로 자식이
  하나도 열거되지 않는다(자체 렌더링, 표준 컨트롤 없음) — 그래서 Play/
  Stop 버튼은 **이 창의 rect를 기준으로 계산한 상대 좌표**를 클릭한다
  (CLAUDE.md 3절 2순위: 컨트롤은 못 찾아도 창은 속성으로 확정했고, 그
  안의 위치만 좌표로 쓴다 — 고정 화면 좌표를 저장하지 않는다).
- Play를 누르면 실제로 **데모 카메라 영상(검출기 콜리메이터 화면)이
  표시된다** — 캡처 이미지 픽셀 통계(평균 밝기)로 "검은 화면(정지)"과
  "영상 표시(재생)"를 구분해 판정한다(OCR/owner-draw 상태를 못 읽는
  자리라 이 프로젝트의 다른 곳과 같은 원칙 — 다른 근거로 검증).
- 끝나면 Stop -> Live View 토글을 다시 눌러 끈다. 실측: 토글 후
  "MainView" 창이 실제로 사라지는 것으로 정리 여부를 확인한다("눌렀다"가
  아니라 창이 없어졌다는 상태로 판정, CLAUDE.md 3절).

## SKIP하는 것

Step4(Step Analysis 초록/빨강 테두리 판정), Step5(Include Snapshot
Image 옵션 + Storage Queue의 Image/Snapshot 건수 확인)는 **아직
실측하지 않았다** — Setting > Integration > Camera 화면의 Step Analysis
옵션 컨트롤 ID, Storage Queue 판독 방법이 확정되지 않아 이번 세션에서는
건드리지 않고 MANUAL로 남긴다(다음 과제, HANDOFF.md 참고).
"""

import os
import time
import ctypes
import ctypes.wintypes as wt

from core import workflow as W
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_12"
TC_TITLE = "카메라/Live View — Live View 버튼 -> 데모 영상 표시 확인"

LIVE_VIEW_TOOL = "Live View"
_LIVE_VIEW_WINDOW_TITLE = "MainView"

# 실측(2026-08-21): Play/Stop은 이 오버레이 창 안에서 표준 컨트롤 없이
# 자체 렌더링된다. 캡처로 확인한 상대 위치(창 rect 기준 오프셋)로만 쓴다
# — 절대 화면 좌표를 저장하지 않고 매번 찾은 창의 rect에 더한다.
_PLAY_OFFSET = (36, 98)
_STOP_OFFSET = (98, 98)
_VIDEO_SAMPLE_RECT_OFFSET = (20, 130, 700, 400)   # 창 rect 기준, 영상이 그려지는 영역


def _find_window_by_title(title):
    user32 = ctypes.windll.user32
    result = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value == title and user32.IsWindowVisible(hwnd):
            rect = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            result.append((hwnd, (rect.left, rect.top, rect.right, rect.bottom)))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return result


def _mean_brightness(rect):
    from PIL import ImageGrab
    img = ImageGrab.grab(bbox=rect, all_screens=True).convert("L")
    hist = img.histogram()
    total = sum(hist)
    if not total:
        return 0.0
    return sum(i * c for i, c in enumerate(hist)) / total


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc12")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    # --- Step 1: DEMO 트리거 파일 (Precondition) --------------------------
    live_cfg = cfg.get("live_server") or {}
    demo_flag = live_cfg.get("demo_flag_file") or ""
    demo_ok = bool(demo_flag) and os.path.exists(demo_flag)
    r.add(step, "VX.LIVE.SERVER DEMO 모드 트리거 파일 확인", PASS if demo_ok else MANUAL,
          expected=demo_flag or "config.json live_server.demo_flag_file",
          actual="존재" if demo_ok else "확인 불가")
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
            r.add(step, "카메라 확인용 영상 준비 (MWL 오픈 + Demo 촬영)", FAIL, actual=str(exc))
            r.finalize()
            return r
        acq = flow["acquire"] or {}
        r.add(step, "카메라 확인용 영상 준비 (MWL 오픈 + Demo 촬영)",
              PASS if acq.get("acquired") else FAIL,
              expected="영상 1장 이상 획득",
              actual="INSTANCE %s → %s / %.1f초"
                     % (acq.get("instances_before"), acq.get("instances_after"),
                        acq.get("seconds", 0)))
        if not acq.get("acquired"):
            r.finalize()
            return r
    else:
        r.add(step, "카메라 확인용 영상 준비", SKIP,
              note="--no-acquire로 실행되어 이미 열려 있는 영상을 사용한다.")
    step += 1

    in_viewer = W.viewer_mode(ui, cfg)
    r.assert_true(step, "Viewer 모드 전환(Tools 패널 노출)", in_viewer,
                  expected="Tools 섹션 ≡ 노출", actual="전환 성공" if in_viewer else "전환 실패")
    if not in_viewer:
        r.finalize()
        return r
    step += 1

    # --- Step 3: Live View 버튼 -> 오버레이 창 -----------------------------
    before_windows = {h for h, _ in _find_window_by_title(_LIVE_VIEW_WINDOW_TITLE)}
    click = W.click_tool(ui, cfg, name=LIVE_VIEW_TOOL, section="tools",
                         evidence_dir=evidence_dir, settle=2.0)
    r.assert_true(step, "Tools 팝업에서 'Live View' 버튼 존재·클릭",
                  click.get("ok"),
                  expected="팔레트에서 'Live View' 발견 후 클릭",
                  actual="클릭함(좌표 %s)" % (click.get("point"),) if click.get("ok")
                  else "찾지 못함(읽힌 툴: %s)" % (", ".join(click.get("available") or []) or "없음"))
    if not click.get("ok"):
        r.finalize()
        return r
    step += 1

    time.sleep(1.0)
    windows = _find_window_by_title(_LIVE_VIEW_WINDOW_TITLE)
    new_windows = [(h, rect) for h, rect in windows if h not in before_windows]
    r.assert_true(step, "Live View 오버레이 창('%s') 표시" % _LIVE_VIEW_WINDOW_TITLE,
                  bool(new_windows),
                  expected="Operation Manual 9.13절 근거 — Live View 클릭 시 라이브 뷰 화면 오픈",
                  actual=("표시됨(rect=%s)" % (new_windows[0][1],) if new_windows
                          else "나타나지 않음"))
    if not new_windows:
        r.finalize()
        return r
    step += 1

    _hwnd, win_rect = new_windows[0]
    video_rect = (win_rect[0] + _VIDEO_SAMPLE_RECT_OFFSET[0],
                 win_rect[1] + _VIDEO_SAMPLE_RECT_OFFSET[1],
                 win_rect[0] + _VIDEO_SAMPLE_RECT_OFFSET[2],
                 win_rect[1] + _VIDEO_SAMPLE_RECT_OFFSET[3])
    idle_brightness = _mean_brightness(video_rect)

    play_point = (win_rect[0] + _PLAY_OFFSET[0], win_rect[1] + _PLAY_OFFSET[1])
    stop_point = (win_rect[0] + _STOP_OFFSET[0], win_rect[1] + _STOP_OFFSET[1])
    ui.click(play_point, settle=1.5)
    time.sleep(1.5)
    playing_brightness = _mean_brightness(video_rect)

    from PIL import ImageGrab
    ImageGrab.grab(bbox=video_rect, all_screens=True).save(
        os.path.join(evidence_dir, "live_view_video_area.png"))

    r.assert_true(step, "Play 클릭 -> 데모 영상 표시(픽셀 밝기 변화)",
                  playing_brightness > idle_brightness + 5,
                  expected="정지 상태(검은 화면)보다 재생 중 밝기가 뚜렷하게 높아야 함"
                           "(Test Data 근거 — .jpg 데모 영상을 표시)",
                  actual="정지 밝기=%.1f -> 재생 밝기=%.1f" % (idle_brightness, playing_brightness))
    step += 1

    ui.click(stop_point, settle=1.0)

    r.manual(step, "Step Analysis(초록/빨강 테두리) 및 Snapshot/Storage Queue 확인",
             "Setting > Integration > Camera의 Step Analysis 옵션 컨트롤 ID, DICOM 전송 "
             "Include Snapshot Image 옵션, Storage Queue의 Image/Snapshot 건수 판독 방법을 "
             "이번 세션에서 실측하지 못해 범위에서 제외했다(체크리스트 Step4~5). 다음 과제로 "
             "HANDOFF.md에 남긴다.")
    step += 1

    off = W.click_tool(ui, cfg, name=LIVE_VIEW_TOOL, section="tools",
                       evidence_dir=evidence_dir, settle=2.0)
    time.sleep(1.0)
    still_open = bool(_find_window_by_title(_LIVE_VIEW_WINDOW_TITLE))
    r.assert_true(step, "Live View 토글 off -> 오버레이 창 닫힘", not still_open,
                  expected="토글 후 '%s' 창이 사라져야 함" % _LIVE_VIEW_WINDOW_TITLE,
                  actual="닫힘 확인" if not still_open else "여전히 열려 있음 — 사람 확인 필요",
                  note="off 클릭 결과: %s" % off.get("ok"))

    return r.finalize()
