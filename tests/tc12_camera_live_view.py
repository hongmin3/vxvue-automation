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

## Step 5(Snapshot 전송)는 서버 수신 SOP Class로 자동 판정한다 (2026-08-30 실측)

`Setting > DICOM - General`의 **Send Camera Snapshot Image**를 Yes로 켠 뒤
촬영·전송하면, Storage SCP에 **DX 영상과 별개로 Secondary Capture 영상이
하나 더** 도착한다(실측): `Modality=XC`, `SOPClassUID=1.2.840.10008.5.1.4.1.1.7`
("Secondary Capture Image Storage"). 원래 DX 영상은 `Modality=DX`,
`SOPClassUID=1.2.840.10008.5.1.4.1.1.1.1`(TC05와 같음)이다. 로컬 Pending
List 창(Storage Queue)을 붙잡는 대신 **서버가 실제로 받은 객체의 종류**로
판정한다 — 클릭이 아니라 수신을 근거로 삼는 이 저장소의 원칙과 같다.

이 설정은 baseline 복원 범위 밖이라(회귀가 되돌리지 않음) 이 TC가 스스로
**켜고(필요하면) 끝에 원래 값으로 되돌린다** — 켜 둔 채로 남기면 이후
TC05~08의 전송에 매번 스냅샷이 추가돼 그쪽 판정에 영향을 줄 수 있다.

## Step 4(Step Analysis 초록/빨강 테두리)는 MANUAL로 남는다

`Setting > Integration - Camera`의 Step Analysis 옵션 컨트롤 ID(Yes=31368/
No=31369)는 확정했지만, **이 테두리를 보여주는 Live View 진입 경로를 찾지
못했다**(2026-08-30 실측). 이 코드베이스가 아는 유일한 Live View 진입
경로(Viewer 모드 -> Tools ≡ -> Live View)는 **그 Step에 이미 촬영된 영상이
있어야만** 열린다 — Step을 등록만 하고 아직 촬영(F2)하지 않은 상태에서는
Viewer 모드의 Tools 패널 전체가 비활성화돼 Live View 버튼 자체가 없다.
체크리스트가 말하는 "촬영할 Step 정보와 카메라 영상 비교"는 촬영 **전**
포지셔닝 중에 봐야 하는 것으로 보이는데, 이 화면 조작 경로로는 그 시점에
도달할 수 없었다(물리 촬영 콘솔 쪽에 별도 진입점이 있을 가능성은 남아
있다). 그래서 Step Analysis 옵션 자체는 건드리지 않고 이 Step만 MANUAL로
남긴다.
"""

import os
import time
import ctypes
import ctypes.wintypes as wt

from core import dicomlite
from core import setting as S
from core import storagescp as store_mod
from core import workflow as W
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

GENERAL_SCREEN_TITLE = "DICOM - General"
#: 실측 2026-08-30: 이 화면의 Send Camera Snapshot Image 행은 좌=No/우=Yes다
#: (Step Analysis 행과 반대 배치라 위치를 가정하지 말 것 — 코드에서는 그냥
#: 확정된 ID를 그대로 쓴다).
CAMERA_SNAPSHOT_YES_ID = 31427
CAMERA_SNAPSHOT_NO_ID = 31428

#: `Setting > Integration - Camera`의 Step Analysis 라디오(실측 2026-08-30).
#: 이 TC는 이 옵션을 켜지 않는다 — 아래 Step 4 MANUAL 사유 참고.
STEP_ANALYSIS_YES_ID = 31368
STEP_ANALYSIS_NO_ID = 31369

#: Storage SCP가 스냅샷을 받으면 나오는 SOP Class(Secondary Capture Image
#: Storage). DX 본영상은 TC05와 같은 `1.2.840.10008.5.1.4.1.1.1.1`.
SOP_SECONDARY_CAPTURE = "1.2.840.10008.5.1.4.1.1.7"

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


#: Live View 오버레이 창이 닫히기를 기다리는 상한(초).
OVERLAY_CLOSE_WAIT_SECONDS = 12.0


def _wait_window_gone(title, timeout=OVERLAY_CLOSE_WAIT_SECONDS, poll=0.5):
    """그 제목의 창이 사라질 때까지 기다린다. 사라졌으면 걸린 초, 아니면 None."""
    started = time.time()
    while True:
        if not _find_window_by_title(title):
            return time.time() - started
        if time.time() - started >= timeout:
            return None
        time.sleep(poll)


#: 재생 판정 기준 — 정지 상태보다 이만큼 밝아져야 "영상이 표시됐다"로 본다.
PLAY_BRIGHTNESS_MARGIN = 5.0
#: Play를 누른 뒤 첫 프레임이 그려지기를 기다리는 상한(초).
PLAY_WAIT_SECONDS = 20.0


def _wait_brightness_rise(rect, baseline, margin=PLAY_BRIGHTNESS_MARGIN,
                          timeout=PLAY_WAIT_SECONDS, poll=0.8):
    """밝기가 기준보다 `margin` 이상 올라갈 때까지 기다린다.

    2026-08-28 전체 회귀에서 이 Step이 `정지 49.0 -> 재생 49.0`으로 FAIL이었다.
    같은 코드가 09:40 실행에서는 `49.0 -> 202.3`으로 PASS였다 — 즉 재생이 안 되는
    것이 아니라 **첫 프레임이 그려지기 전에 한 번 재고 끝냈다.** 데모 영상은
    다른 프로세스(VX.LIVE.VIEW)가 그리므로 시작 시점이 실행마다 흔들린다.

    한 번 재고 끝내는 대신 상한까지 폴링하고, **가장 밝았던 값**을 돌려준다 —
    영상이 흐르는 중이라 프레임마다 밝기가 달라져, 마지막 한 장이 우연히 어두운
    프레임일 수 있다. 이 TC의 다른 판정(TC04 캡처 안정화)과 같은 처리다.

    반환: (판정에 쓸 밝기, 올라가기까지 걸린 초 또는 None, 관측한 표본 수)
    """
    started = time.time()
    best = _mean_brightness(rect)
    samples = 1
    if best > baseline + margin:
        return best, 0.0, samples
    while time.time() - started < timeout:
        time.sleep(poll)
        now = _mean_brightness(rect)
        samples += 1
        if now > best:
            best = now
        if now > baseline + margin:
            return best, time.time() - started, samples
    return best, None, samples


def _camera_snapshot_checked(ui):
    """`Setting > DICOM - General`의 Send Camera Snapshot Image가 지금 Yes인가.

    반환: True/False, 또는 화면·컨트롤을 못 찾으면 None.
    """
    if not S.open_setting(ui):
        return None
    if S.goto_screen(ui, GENERAL_SCREEN_TITLE) is None:
        return None
    ctrls = S.content_controls(ui, min_size=4, include_offscreen=True)
    yes_ctrl = next((c for c in ctrls if c.ctrl_id == CAMERA_SNAPSHOT_YES_ID), None)
    if yes_ctrl is None:
        return None
    return S.checkbox_checked(ui, yes_ctrl)


def _set_camera_snapshot(ui, want_yes):
    """Send Camera Snapshot Image를 `want_yes`로 맞추고 Update한다.

    이미 원하는 값이면 아무것도 누르지 않는다. 반환: (성공했는가, Update 팝업 문구).
    """
    if not S.open_setting(ui):
        return False, "Setting 화면 진입 실패"
    if S.goto_screen(ui, GENERAL_SCREEN_TITLE) is None:
        return False, "%s 화면을 찾지 못함" % GENERAL_SCREEN_TITLE
    ctrls = S.content_controls(ui, min_size=4, include_offscreen=True)
    want_id = CAMERA_SNAPSHOT_YES_ID if want_yes else CAMERA_SNAPSHOT_NO_ID
    want_ctrl = next((c for c in ctrls if c.ctrl_id == want_id), None)
    if want_ctrl is None:
        return False, "라디오 컨트롤(%d)을 찾지 못함" % want_id
    if S.checkbox_checked(ui, want_ctrl):
        return True, "이미 %s였다" % ("Yes" if want_yes else "No")
    ui.click(want_ctrl, settle=1.0)
    msg = S.update(ui)
    now_ok = S.checkbox_checked(ui, want_ctrl)
    return bool(now_ok), msg or "(Update 팝업 없음)"


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

    # --- Snapshot 전송 확인을 위해 미리 켠다 (촬영 전에 켜야 한다, 2026-08-30
    # 실측 — 이 값은 baseline 복원으로 되돌아오지 않으므로 이 TC가 끝에서
    # 원래 값으로 되돌린다) -----------------------------------------------
    snapshot_before = _camera_snapshot_checked(ui)
    snapshot_restore_needed = do_acquire and snapshot_before is False
    if do_acquire and snapshot_before is not True:
        _set_camera_snapshot(ui, True)

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

    why = {}
    in_viewer = W.viewer_mode(ui, cfg, why=why)
    r.assert_true(step, "Viewer 모드 전환(Tools 패널 노출)", in_viewer,
                  expected="Tools 섹션 ≡ 노출",
                  actual=("전환 성공" if in_viewer
                          else "전환 실패 — %s" % why.get("reason", "사유 미기록")))
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
    # `expect_hwnd`로 **이 오버레이 창이 실제로 그 좌표를 차지하고 있는지**
    # 확인시킨다. MainView는 VXvue가 아니라 VX.LIVE.VIEW의 창이라, 좌표만
    # 넘기면 드라이버가 "우리 창이 아니다"까지만 알고 의도와 사고를 구분하지
    # 못한다(`core/ui.VXvueUi._aim`).
    ui.click(play_point, settle=1.5, expect_hwnd=_hwnd)
    playing_brightness, rose_after, samples = _wait_brightness_rise(
        video_rect, idle_brightness)

    from PIL import ImageGrab
    ImageGrab.grab(bbox=video_rect, all_screens=True).save(
        os.path.join(evidence_dir, "live_view_video_area.png"))

    r.assert_true(step, "Play 클릭 -> 데모 영상 표시(픽셀 밝기 변화)",
                  playing_brightness > idle_brightness + PLAY_BRIGHTNESS_MARGIN,
                  expected="정지 상태(검은 화면)보다 재생 중 밝기가 뚜렷하게 높아야 함"
                           "(Test Data 근거 — .jpg 데모 영상을 표시)",
                  actual="정지 밝기=%.1f -> 재생 밝기=%.1f (%s / 표본 %d회)"
                         % (idle_brightness, playing_brightness,
                            "%.1f초 만에 올라옴" % rose_after if rose_after is not None
                            else "%.0f초 동안 올라오지 않음" % PLAY_WAIT_SECONDS,
                            samples),
                  note="데모 영상은 다른 프로세스(VX.LIVE.VIEW)가 그리므로 첫 프레임이 "
                       "나오는 시점이 실행마다 흔들린다. 한 번 재고 끝내면 재생이 "
                       "정상인데도 실패로 적힌다(2026-08-28 회귀 실측: 같은 코드가 "
                       "09:40에는 49.0->202.3, 13:59에는 49.0->49.0). 그래서 상한까지 "
                       "폴링하고 관측한 최대 밝기로 판정한다.")
    step += 1

    ui.click(stop_point, settle=1.0, expect_hwnd=_hwnd)

    r.manual(step, "Step Analysis(초록/빨강 테두리) 확인",
             "Setting > Integration - Camera의 Step Analysis 옵션 컨트롤 ID(Yes=%d/"
             "No=%d)는 확정했지만, 이 테두리가 나오는 Live View 진입 경로를 찾지 "
             "못했다(2026-08-30 실측 — 모듈 docstring 참고). 이 코드베이스가 아는 "
             "유일한 경로(Viewer 모드 -> Tools ≡ -> Live View)는 그 Step에 이미 "
             "촬영된 영상이 있어야만 열려서, 촬영 전 포지셔닝 중 테두리를 "
             "재현하지 못했다."
             % (STEP_ANALYSIS_YES_ID, STEP_ANALYSIS_NO_ID))
    step += 1

    off = W.click_tool(ui, cfg, name=LIVE_VIEW_TOOL, section="tools",
                       evidence_dir=evidence_dir, settle=2.0)
    # 창이 사라지는 것도 **다른 프로세스**(VX.LIVE.VIEW)가 하는 일이라 즉시가
    # 아니다. 1초만 재고 판정하면 정상 종료 중인 창을 "안 닫혔다"로 적는다
    # (2026-08-28 실측). 상한까지 폴링한다 — Step 6의 재생 판정과 같은 이유다.
    closed_after = _wait_window_gone(_LIVE_VIEW_WINDOW_TITLE)
    still_open = closed_after is None
    r.assert_true(step, "Live View 토글 off -> 오버레이 창 닫힘", not still_open,
                  expected="토글 후 '%s' 창이 사라져야 함" % _LIVE_VIEW_WINDOW_TITLE,
                  actual=("%.1f초 만에 닫힘 확인" % closed_after if not still_open
                          else "%.0f초를 기다려도 여전히 열려 있음 — 사람 확인 필요"
                               % OVERLAY_CLOSE_WAIT_SECONDS),
                  note="off 클릭 결과: %s" % off.get("ok"))
    step += 1

    # --- Snapshot 전송 확인 (체크리스트 Step 5, 2026-08-30 실측) -------------
    # 판정 근거는 클릭이 아니라 **Storage SCP가 실제로 받은 객체 종류**다 —
    # Secondary Capture(스냅샷)가 DX 본영상과 별개 객체로 도착해야 한다.
    if do_acquire and acq.get("acquired"):
        store_mark = store_mod.mark(cfg)
        W.select_first_image(ui)
        sent = W.send(ui, scope="all")
        res = store_mod.wait_for_store(
            cfg, store_mark, count=2, timeout=90,
            patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"))
        classes = []
        for path in res.get("files") or []:
            tags = dicomlite.read_tags(path, ["SOPClassUID", "Modality"])
            classes.append(tags.get("SOPClassUID") or "(판독 실패)")
        has_snapshot = SOP_SECONDARY_CAPTURE in classes
        r.add(step, "Send Camera Snapshot Image 전송 -> Storage SCP 수신 확인",
              PASS if (res.get("ok") and has_snapshot) else FAIL,
              expected="DX 본영상과 별개로 Secondary Capture(SOPClassUID=%s) 객체가 "
                       "도착해야 함" % SOP_SECONDARY_CAPTURE,
              actual="Send 팝업=%s / 수신 객체 SOPClassUID=%s / %s"
                     % (sent.get("dialog"), classes or "없음", res.get("note")),
              note="Modality=XC로도 확인 가능(실측). 이 판정은 '보냈다'가 아니라 "
                   "'서버가 실제로 받았다'를 근거로 한다.")
        step += 1
    else:
        r.add(step, "Send Camera Snapshot Image 전송 -> Storage SCP 수신 확인", SKIP,
              note="촬영을 하지 않았거나(--no-acquire) 촬영이 실패해 보낼 영상이 없다.")
        step += 1

    # --- 정리: Send Camera Snapshot Image를 원래 값으로 되돌린다 ------------
    if snapshot_restore_needed:
        restored_ok, restore_msg = _set_camera_snapshot(ui, False)
        r.add(step, "시험 후 정리 — Send Camera Snapshot Image 원복",
              PASS if restored_ok else MANUAL,
              expected="원래 값(No)으로 복귀",
              actual=restore_msg,
              note="이 설정은 baseline 복원으로 되돌아오지 않아, 켜 둔 채로 남기면 "
                   "이후 TC05~08의 전송에도 스냅샷이 계속 추가된다.")
        step += 1

    return r.finalize()
