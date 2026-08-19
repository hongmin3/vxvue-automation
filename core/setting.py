# -*- coding: utf-8 -*-
"""Setting 화면 탐색기 — TC_WindowsUpdate_14의 엔진.

## 왜 좌표 캘리브레이션이 필요 없었나

앞선 설계(3.5절)에서는 Bellalun `bellalunSetting.py`처럼 좌표를 캘리브레이션해
OCR로 메뉴를 읽어야 할 것으로 봤다. 실측해 보니 **더 나은 방법이 있었다.**

1. 좌측 메뉴 항목은 커스텀 owner-draw라 `GetWindowText`로 라벨을 읽을 수 없지만,
   `MenuList`(30894) > `ItemList` > `ItemWnd` 아래의 자식 윈도우로 존재하며
   **소분류는 `StepItem`, 대분류는 `ScrollWnd`** 로 클래스가 나뉜다.
   각각 컨트롤 ID가 순번대로 고정돼 있어 좌표 없이 개체를 지목할 수 있다.
2. 화면을 전환하면 상단 제목 `Static`(ID 20000, 폭이 넓은 것)이
   `" Integration - Extra Tool"` 처럼 **평문으로 읽힌다.**

즉 "클릭 → 제목을 읽어 무엇이 열렸는지 확인"이 가능하므로, 메뉴 라벨 지도를
하드코딩하지 않고 **실행 시점에 스스로 만들어낸다.** 해상도·테마·언어가 바뀌어도
좌표를 다시 재지 않아도 된다. 캡처 비교(SSIM)는 화면 내용 검증에만 쓴다.

## 접근 방식의 한계

대분류는 **아코디언이 아니라 토글**이다(System과 Integration이 동시에 펼쳐진
상태를 실측 확인). 여러 개가 동시에 펼쳐질 수 있어 소분류의 화면 좌표는 매 순간
달라진다 — 항상 다시 열거하고, 보이는 영역 밖이면 스크롤해서 끌어온 뒤
클릭한다. 좌표를 저장해 재사용하지 않는다.

또 **대분류(ScrollWnd)는 컨트롤 ID가 전부 1**이라 ID로 지목할 수 없다. 세로
순서 인덱스(0~9)로 식별한다. 소분류(StepItem)만 ID가 1~55로 고유하다.
"""

import time

MENU_LIST_ID = 30894
TITLE_STATIC_ID = 20000
UPDATE_BUTTON_ID = 30641

# Setting 좌하단 버튼 (2026-08-18 실측)
EXPORT_BUTTON_ID = 30300
IMPORT_BUTTON_ID = 30685

# 설정 본문 영역(좌측 메뉴 제외)
CONTENT_BBOX = (275, 60, 1872, 1015)

# 우측 메인 네비 TabItem (위 -> 아래로 고정)
NAV_TAB_CONTAINER = 31197
NAV_SETTING = 13

# ItemWnd에서 항목이 실제로 보이는 세로 구간(바깥이면 스크롤이 필요하다).
# 항목 높이가 50이므로 여백을 크게 잡으면 맨 위/맨 아래 항목이 영원히
# '보이지 않음'으로 판정돼 스크롤만 반복하다 실패한다(실측).
VIEW_MARGIN = 8


class SettingError(RuntimeError):
    pass


_ITEM_WND_CACHE = {}


def _item_wnd(ui, refresh=False):
    """좌측 메뉴의 ItemWnd 컨트롤. hwnd를 캐시한다.

    전체 컨트롤 트리 열거는 크로스 프로세스 SendMessage가 수백 번 발생해
    한 번에 수 초가 걸린다. 스크롤 루프마다 이걸 다시 하면 화면 하나 여는 데
    수십 초가 걸려 순회가 사실상 불가능해진다(실측). 그래서 hwnd를 캐시하고
    창이 살아 있는지만 확인한다.
    """
    import ctypes
    from .ui import Control, children, _class_of, _rect_of, _text_of

    u32 = ctypes.windll.user32
    pid = ui.pid
    hwnd = None if refresh else _ITEM_WND_CACHE.get(pid)
    if hwnd and u32.IsWindow(hwnd) and u32.IsWindowVisible(hwnd):
        return Control(hwnd, u32.GetDlgCtrlID(hwnd), _class_of(hwnd),
                       _text_of(hwnd), _rect_of(hwnd), True, 0)

    menus = [c for c in ui.controls(max_depth=8) if c.ctrl_id == MENU_LIST_ID]
    if not menus:
        _ITEM_WND_CACHE.pop(pid, None)
        return None
    for c in children(menus[0].hwnd, 3):
        if c.text.strip() == "ItemWnd":
            _ITEM_WND_CACHE[pid] = c.hwnd
            return c
    return None


def open_setting(ui, timeout=15):
    """우측 세로 탭에서 Setting 화면으로 이동한다."""
    if _item_wnd(ui) is not None:
        return True
    tabs = [c for c in ui.controls(max_depth=8) if c.ctrl_id == NAV_TAB_CONTAINER]
    if not tabs:
        raise SettingError("우측 네비 Tab(%d)을 찾지 못했습니다." % NAV_TAB_CONTAINER)
    from .ui import children
    items = [c for c in children(tabs[0].hwnd, 2) if c.text.strip() == "TabItem"]
    target = next((c for c in items if c.ctrl_id == NAV_SETTING), None)
    if target is None:
        raise SettingError("Setting TabItem(id %d)을 찾지 못했습니다." % NAV_SETTING)
    ui.click(target, settle=1.5)
    end = time.time() + timeout
    while time.time() < end:
        if _item_wnd(ui) is not None:
            return True
        time.sleep(0.5)
    return False


_TITLE_CACHE = {}


def title(ui, refresh=False):
    """상단 화면 제목. 예) 'Integration - Extra Tool'.

    화면을 열 때마다 호출되므로 hwnd를 캐시한다. 제목 Static은 ID 20000이
    여러 개라, 상단(y<70)에 있고 폭이 넓은(>800) 것으로 특정한다.
    """
    import ctypes
    from .ui import _rect_of, _text_of

    u32 = ctypes.windll.user32
    pid = ui.pid
    hwnd = None if refresh else _TITLE_CACHE.get(pid)
    if hwnd and u32.IsWindow(hwnd):
        text = _text_of(hwnd).strip()
        if text:
            return text

    best = None
    for c in ui.controls(max_depth=6):
        if c.cls != "Static" or c.ctrl_id != TITLE_STATIC_ID:
            continue
        l, t, r, b = c.rect
        if t < 70 and (r - l) > 800 and c.text.strip():
            best = c
    if best is None:
        return None
    _TITLE_CACHE[pid] = best.hwnd
    return best.text.strip()


def menu_items(ui):
    """(대분류, 소분류) 컨트롤 목록을 화면 세로 순서로 반환한다.

    보이지 않는(접힌 대분류에 속한) 소분류도 포함된다 — 호출부가 `visible`로
    걸러 쓴다.
    """
    from .ui import children
    wnd = _item_wnd(ui)
    if wnd is None:
        raise SettingError("Setting 화면이 아닙니다(ItemWnd 없음).")
    majors, minors = [], []
    for c in children(wnd.hwnd, 1):        # 항목은 ItemWnd의 직속 자식이다
        label = c.text.strip()
        if label == "ScrollWnd":
            majors.append(c)
        elif label == "StepItem":
            minors.append(c)
    majors.sort(key=lambda c: c.rect[1])
    minors.sort(key=lambda c: c.rect[1])
    return majors, minors


def _visible_band(ui):
    wnd = _item_wnd(ui)
    l, t, r, b = wnd.rect
    return t + VIEW_MARGIN, b - VIEW_MARGIN


def _locate(ui, key, is_major):
    """현재 열거 결과에서 대상 컨트롤을 찾는다.

    소분류는 컨트롤 ID가 1~55로 고유하지만, **대분류(ScrollWnd)는 전부 ID가 1**
    이라 ID로 지목할 수 없다(실측). 대분류는 세로 순서 인덱스로 식별한다 —
    펼침/접힘에 따라 좌표는 변해도 10개의 상대 순서는 변하지 않는다.
    """
    majors, minors = menu_items(ui)
    if is_major:
        return majors[key] if 0 <= key < len(majors) else None
    return next((c for c in minors if c.ctrl_id == key), None)


def scroll_into_view(ui, key, is_major=False, max_steps=16):
    """지정 항목이 보이는 영역에 오도록 스크롤하고 그 컨트롤을 반환한다.

    스크롤하면 rect가 바뀌므로 매번 다시 열거한다. 찾지 못하면 None.
    """
    wnd = _item_wnd(ui)
    anchor = ((wnd.rect[0] + wnd.rect[2]) // 2, (wnd.rect[1] + wnd.rect[3]) // 2)
    top, bottom = _visible_band(ui)

    last_y = None
    for _ in range(max_steps + 1):
        target = _locate(ui, key, is_major)
        if target is None:
            return None
        y = (target.rect[1] + target.rect[3]) // 2
        if top <= y <= bottom and target.visible:
            return target
        if y == last_y:
            # 스크롤해도 위치가 그대로면 더 갈 곳이 없다. 무한 반복을 막는다.
            return None
        last_y = y
        # 한 번에 많이 굴려 반복 횟수를 줄인다. 55개 화면을 도는 시험에서는
        # 스크롤 대기가 전체 실행 시간의 상당 부분을 차지한다(실측).
        ui.wheel(anchor, -5 if y > bottom else 5, settle=0.12)
    return None


def click_item(ui, key, is_major=False, settle=0.4):
    """메뉴 항목을 클릭한다. 클릭한 컨트롤을 반환(못 찾으면 None)."""
    target = scroll_into_view(ui, key, is_major)
    if target is None:
        return None
    ui.click(target, settle=settle)
    return target


def visible_minor_ids(ui):
    """지금 펼쳐져 화면에 노출된 소분류의 컨트롤 ID 집합."""
    _, minors = menu_items(ui)
    return set(c.ctrl_id for c in minors if c.visible)


def toggle_major(ui, index, settle=0.5):
    """대분류를 토글한다(펼침 <-> 접힘).

    이 메뉴는 아코디언이 아니라 **토글**이다 — System과 Integration이 동시에
    펼쳐진 상태를 실측으로 확인했다. 따라서 한 대분류를 펼쳐도 다른 대분류가
    저절로 접히지 않는다.
    """
    return click_item(ui, index, is_major=True, settle=settle)


def collapse_all(ui, rounds=2):
    """모든 대분류를 접어 기준 상태를 만든다.

    펼쳐진 것이 하나도 없으면 소분류가 전부 hidden이 된다. 이 상태에서
    하나씩 펼쳐야 '어느 소분류가 어느 대분류의 자식인지'를 확정할 수 있다.
    """
    for _ in range(rounds):
        majors, _ = menu_items(ui)
        for i in range(len(majors)):
            if not visible_minor_ids(ui):
                return True
            before = visible_minor_ids(ui)
            toggle_major(ui, i, settle=0.6)
            if len(visible_minor_ids(ui)) > len(before):
                # 잘못 펼쳤으면 곧바로 되돌린다.
                toggle_major(ui, i, settle=0.6)
    return not visible_minor_ids(ui)


def open_screen(ui, minor_id, timeout=10, stable_reads=2, poll=0.12):
    """소분류 화면을 연다. 열린 화면 제목을 반환한다(실패 시 None).

    전환 완료 신호를 두 가지로 본다.

    1. 상단 제목이 바뀌고 그 값이 연속 `stable_reads`회 같게 읽힘.
       제목이 바뀌자마자 반환하면 **갱신 중인 문자열을 읽는다** —
       'DICOM - Storage'를 'DICOM - Stor'로 잘라 읽은 사례가 있었다.
    2. 본문 대화상자(`#32770`)의 hwnd가 바뀜.
       이미 그 화면이 열려 있던 상태에서 같은 항목을 다시 클릭하면 제목이
       변하지 않아 1번만으로는 매번 제한 시간(10초)을 소진한다. 실제로 화면
       하나 여는 데 13초가 걸리는 원인이었다(실측).
    """
    before_title = title(ui)
    dlg = content_dialog(ui)
    before_hwnd = dlg.hwnd if dlg else None

    if click_item(ui, minor_id) is None:
        return None

    end = time.time() + timeout
    last, streak = None, 0
    while time.time() < end:
        cur = content_dialog(ui)
        if before_hwnd is not None and cur is not None and cur.hwnd != before_hwnd:
            # 본문이 교체됐다. 제목이 안정화될 짧은 여유만 주고 읽는다.
            time.sleep(poll * 2)
            return title(ui)
        now = title(ui)
        if now and now != before_title:
            if now == last:
                streak += 1
                if streak >= stable_reads:
                    return now
            else:
                last, streak = now, 1
        time.sleep(poll)
    return last or title(ui)


def walk(ui, on_screen=None):
    """대분류를 하나씩 펼쳐 그 아래 소분류를 전부 열어본다.

    `on_screen(major_index, minor_index, minor_ctrl_id, screen_title)`가 있으면
    각 화면에서 호출된다(캡처·검증용).

    반환: [{'major': i, 'minor': j, 'ctrl_id': id, 'title': '...'}, ...]
    이 결과가 곧 Setting 트리 지도이며, 하드코딩한 목록이 아니라 실행 시점에
    제품이 실제로 보여준 것이다. 체크리스트/매뉴얼과 대조하면 화면 누락도 잡힌다.
    """
    visited = []
    collapse_all(ui)

    majors, _ = menu_items(ui)
    for mi in range(len(majors)):
        before = visible_minor_ids(ui)
        if toggle_major(ui, mi) is None:
            visited.append({"major": mi, "minor": None, "ctrl_id": None,
                            "title": None, "error": "대분류를 화면에 띄우지 못함"})
            continue
        time.sleep(0.4)
        after = visible_minor_ids(ui)
        child_ids = sorted(after - before)
        if not child_ids:
            visited.append({"major": mi, "minor": None, "ctrl_id": None,
                            "title": None, "error": "펼친 뒤에도 소분류가 없음"})
            continue

        for mj, minor_id in enumerate(child_ids):
            scr = open_screen(ui, minor_id)
            row = {"major": mi, "minor": mj, "ctrl_id": minor_id, "title": scr}
            if scr is None:
                row["error"] = "화면 전환 실패"
            visited.append(row)
            if on_screen is not None:
                on_screen(mi, mj, minor_id, scr)
            time.sleep(0.2)

        toggle_major(ui, mi)          # 다음 대분류를 깨끗하게 판별하기 위해 접는다
        time.sleep(0.3)
    return visited


# --- Update / Export / Import ----------------------------------------
def update(ui, ack_timeout=8, evidence_path=None):
    """현재 화면의 Update 버튼을 누르고 Info 팝업까지 닫는다.

    Update 뒤에 뜨는 모달 Info 팝업을 닫기 전에는 이후 모든 클릭이 조용히
    무시된다(VXvue 고유 함정). 팝업 문구를 반환한다.
    """
    btns = [c for c in ui.controls(max_depth=6) if c.ctrl_id == UPDATE_BUTTON_ID]
    if not btns:
        return None
    return ui.click_and_ack(btns[0], settle=0.8, ack_timeout=ack_timeout,
                            evidence_path=evidence_path)


_FRAME_CACHE = {}


def _frame_wnd(ui, refresh=False):
    """`CVieworksFrameWnd` 컨트롤. 화면 구성요소를 싸게 찾기 위한 기준점이다.

    이 창의 **직속 자식**만 보면 좌측 메뉴(MenuList) / Update 버튼 / 상단 제목 /
    본문 대화상자를 모두 얻을 수 있다. 매번 전체 컨트롤 트리를 훑으면
    크로스 프로세스 호출이 수백 번 발생해 화면 하나당 수 초가 더 붙는다(실측).
    """
    import ctypes
    from .ui import Control, children, _class_of, _rect_of, _text_of

    u32 = ctypes.windll.user32
    pid = ui.pid
    hwnd = None if refresh else _FRAME_CACHE.get(pid)
    if hwnd and u32.IsWindow(hwnd) and u32.IsWindowVisible(hwnd):
        return Control(hwnd, u32.GetDlgCtrlID(hwnd), _class_of(hwnd),
                       _text_of(hwnd), _rect_of(hwnd), True, 0)

    for win in ui.windows():
        for c in children(win.hwnd, 2):
            if c.text.strip() == "CVieworksFrameWnd":
                _FRAME_CACHE[pid] = c.hwnd
                return c
    return None


def content_dialog(ui):
    """설정 본문을 담은 자식 대화상자(`#32770`).

    소분류를 바꾸면 이 대화상자가 새로 만들어지므로 캐시하지 않고 매번 찾는다.
    프레임 창의 직속 자식만 보므로 비용은 작다.
    """
    from .ui import children
    frame = _frame_wnd(ui)
    if frame is None:
        return None
    best, best_area = None, 0
    for c in children(frame.hwnd, 1):
        if c.cls != "#32770" or not c.visible:
            continue
        l, t, r, b = c.rect
        area = (r - l) * (b - t)
        if area > best_area:
            best, best_area = c, area
    return best


def content_controls(ui, min_size=8, include_offscreen=True):
    """설정 본문의 컨트롤 목록.

    본문 대화상자의 자식을 직접 열거하므로 **스크롤로 화면 밖에 나가 있는
    컨트롤도 포함된다**(rect가 뷰포트 밖인 상태로 잡힌다). 화면에 실제로
    보이는 것만 원하면 `include_offscreen=False`.
    """
    from .ui import children
    dlg = content_dialog(ui)
    if dlg is None:
        return []
    vl, vt, vr, vb = dlg.rect
    out = []
    for c in children(dlg.hwnd, 4):
        if not c.visible:
            continue
        w, h = c.size
        if w < min_size or h < min_size:
            continue
        if not include_offscreen:
            l, t, r, b = c.rect
            if b <= vt or t >= vb or r <= vl or l >= vr:
                continue
        out.append(c)
    return out


def in_viewport(ctrl, viewport, margin=2):
    """컨트롤이 뷰포트 안에 온전히 들어와 있는지."""
    l, t, r, b = ctrl.rect
    vl, vt, vr, vb = viewport
    return (t >= vt - margin and b <= vb + margin
            and l >= vl - margin and r <= vr + margin)


def scrollable_extent(ui, controls=None):
    """본문이 뷰포트를 넘어가는 정도(픽셀). 0이면 스크롤이 필요 없다.

    `controls`를 넘기면 컨트롤을 다시 열거하지 않는다(호출부가 이미 갖고 있을 때).
    """
    dlg = content_dialog(ui)
    if dlg is None:
        return 0
    vl, vt, vr, vb = dlg.rect
    over = 0
    for c in (controls if controls is not None else content_controls(ui)):
        l, t, r, b = c.rect
        over = max(over, b - vb, vt - t)
    return max(over, 0)


def scroll_to_top(ui, steps=8, notches=6):
    """본문을 맨 위로 올린다. 화면마다 시작 위치를 같게 맞추기 위한 것."""
    dlg = content_dialog(ui)
    if dlg is None:
        return False
    anchor = ((dlg.rect[0] + dlg.rect[2]) // 2, (dlg.rect[1] + dlg.rect[3]) // 2)
    for _ in range(steps):
        ui.wheel(anchor, notches, settle=0.06)
    return True


def scroll_down(ui, notches=-4, settle=0.18):
    dlg = content_dialog(ui)
    if dlg is None:
        return False
    anchor = ((dlg.rect[0] + dlg.rect[2]) // 2, (dlg.rect[1] + dlg.rect[3]) // 2)
    ui.wheel(anchor, notches, settle=settle)
    return True


def _file_dialog_submit(ui, path, timeout=20):
    """표준 '열기'/'다른 이름으로 저장' 대화상자에 경로를 넣고 확정한다.

    파일명 Edit은 컨트롤 ID 1148, 확정 버튼은 ID 1이다(실측). 경로를 직접
    타이핑하므로 폴더 탐색이 필요 없다.
    """
    import os
    from .ui import children

    dlg = ui.wait_dialog(timeout=timeout)
    if dlg is None:
        return False, "파일 대화상자가 나타나지 않았습니다."

    edits = [c for c in children(dlg.hwnd, 4) if c.cls == "Edit"]
    if not edits:
        return False, "파일명 입력 컨트롤(1148)을 찾지 못했습니다."

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    ui.type_text(edits[0], os.path.abspath(path), clear=True)
    time.sleep(0.4)
    ui.raw_key(0x0D)                       # Enter
    time.sleep(1.0)

    # 덮어쓰기 확인 등 후속 확인 대화상자를 닫는다.
    follow = ui.dialog()
    if follow is not None and follow.hwnd != dlg.hwnd:
        text = ui.dialog_text(follow)
        buttons = ui.dialog_buttons(follow)
        if buttons:
            ui.click(buttons[0], settle=0.6)
        return True, "후속 대화상자 처리: %s" % (text or "(문구 없음)")
    return True, ""


def export_settings(ui, path, timeout=180, poll=2.0):
    """Setting Export를 실행해 지정 경로에 `.vxs`를 만든다.

    반환: (실제 생성된 경로 또는 None, 메모)
    제품이 어차피 파일명 뒤에 `.vxs`를 자동으로 붙이므로(사용자 확인
    2026-08-19), 호출부는 `path`에 확장자를 붙이지 않고 넘기는 것을 권한다
    — 직접 `.vxs`를 붙이면 오히려 이중으로 남을 수 있다. 이 함수는 `path`
    그대로와 `path + ".vxs"` 둘 다 확인해 실제로 만들어진 파일을 찾는다.
    """
    import glob
    import os

    btns = [c for c in ui.controls(max_depth=6) if c.ctrl_id == EXPORT_BUTTON_ID]
    if not btns:
        return None, "Export 버튼(%d)을 찾지 못했습니다." % EXPORT_BUTTON_ID

    ui.click(btns[0], settle=1.5)
    ok, note = _file_dialog_submit(ui, path)
    if not ok:
        return None, note

    # 진행 대화상자("Export Setting...")가 사라지고 파일이 생길 때까지 기다린다.
    target = os.path.abspath(path)
    candidates = [target, target + ".vxs"]
    end = time.time() + timeout
    last_size = -1
    finished = False
    while time.time() < end:
        found = next((p for p in candidates if os.path.exists(p)), None)
        if found:
            size = os.path.getsize(found)
            if size > 0 and size == last_size and ui.dialog() is None:
                finished = True
                break
            last_size = size
        time.sleep(poll)

    found = next((p for p in candidates if os.path.exists(p)), None)
    if not finished:
        return found, (note + " (제한 시간 내 완료 확인 실패)").strip()

    # 진행 대화상자가 사라진 직후 완료 확인 Info 팝업이 뒤이어 뜬다(실측
    # 2026-08-19). 이 팝업을 닫지 않으면 이후 모든 클릭이 무시되므로
    # (core/ui.dismiss_info 문서 참고), Export를 성공으로 보기 전에 반드시
    # 닫는다. 팝업이 없으면 곧바로 넘어간다(timeout 내 None 반환).
    ack = ui.dismiss_info(timeout=6)
    if ack:
        note = (note + " / 완료 팝업: %s" % ack).strip(" /")
    return found, note


def import_settings(ui, path, confirm=False, timeout=300, poll=2.0):
    """Setting Import를 실행한다. **파괴적 조작이다.**

    `.vxs` 안에는 DRF DB 전체 백업(`Data.bak`)이 들어 있어 Import는 export 시점의
    DB로 되돌린다 — export 이후 생성된 환자·검사가 사라진다. 그래서
    `confirm=True` 없이는 실행하지 않는다. 호출부는 반드시 사전 백업
    (`core/dbreset.backup()`)을 남긴 뒤 호출할 것.

    반환: (성공 여부, 메모). Import 후 제품이 종료·재시작을 요구할 수 있으므로
    호출부가 재기동과 로그인을 처리해야 한다.
    """
    import os

    if not confirm:
        raise SettingError(
            "Import는 명시적 승인이 필요합니다. import_settings(..., confirm=True). "
            "이 조작은 DB 전체를 export 시점으로 되돌립니다.")
    if not os.path.exists(path):
        return False, "가져올 파일이 없습니다: %s" % path

    btns = [c for c in ui.controls(max_depth=6) if c.ctrl_id == IMPORT_BUTTON_ID]
    if not btns:
        return False, "Import 버튼(%d)을 찾지 못했습니다." % IMPORT_BUTTON_ID

    ui.click(btns[0], settle=1.5)
    ok, note = _file_dialog_submit(ui, path)
    if not ok:
        return False, note

    # 진행/완료/재시작 안내 대화상자를 순차로 닫는다. 프로세스가 스스로
    # 종료될 수도 있으므로 pid 유실도 정상 종료로 본다.
    messages = []
    end = time.time() + timeout
    while time.time() < end:
        if not ui.pid:
            messages.append("Import 후 VXvue가 종료됨")
            break
        dlg = ui.dialog()
        if dlg is not None:
            text = ui.dialog_text(dlg)
            buttons = ui.dialog_buttons(dlg)
            if buttons:
                ui.click(buttons[0], settle=1.0)
                messages.append(text or "(문구 없음)")
            else:
                time.sleep(poll)
                continue
        else:
            # 대화상자가 없고 Setting 화면이 살아 있으면 완료로 본다.
            if _item_wnd(ui, refresh=True) is not None and messages:
                break
        time.sleep(poll)

    return True, " / ".join([note] + messages).strip(" /")


# --- 스크롤 순회 / 목록 상세 순회 -------------------------------------
def _page_signature(image_path):
    """캡처를 축소·회색화해 서명으로 만든다. 스크롤이 더 되는지 판별용."""
    import hashlib
    from PIL import Image
    with Image.open(image_path) as im:
        small = im.convert("L").resize((96, 60))
        return hashlib.sha1(small.tobytes()).hexdigest()


def page_through(ui, capture_fn, max_pages=14, notches=-4):
    """본문을 맨 위부터 끝까지 스크롤하며 매 페이지를 캡처한다.

    `capture_fn(page_index, viewport_rect)` -> 캡처 파일 경로.

    스크롤이 더 되는지는 **컨트롤 위치**로 판단한다(픽셀 서명으로 하면
    스크롤바 썸네일만 움직여도 다음 페이지로 오해해, 119px만 넘치는 화면에서
    6장이 찍혔다 — 실측). 위치가 하나도 변하지 않으면 끝까지 내려온 것이다.

    반환: dict(
      pages=[캡처 경로...],
      seen=set(뷰포트에 온전히 노출된 컨트롤 hwnd),
      controls=[판정 대상 컨트롤...],
      oversized=[뷰포트보다 커서 애초에 온전히 담길 수 없는 컨트롤...],
      total_controls=본문 컨트롤 총 개수,
      hit_limit=최대 페이지 상한에 걸렸는지,
      overflow_px=본문이 뷰포트를 넘어간 정도)

    보이는 부분만 캡처하면 스크롤 아래 설정이 검증되지 않는다. 그래서
    **모든 컨트롤이 스크롤 중 최소 한 번 뷰포트에 온전히 들어왔는지**를 함께
    기록한다 — 이것이 "설정을 전부 확인했다"의 실질적 근거다.
    """
    scroll_to_top(ui)
    dlg = content_dialog(ui)
    if dlg is None:
        return {"pages": [], "seen": set(), "controls": [], "oversized": [],
                "total_controls": 0, "hit_limit": False, "overflow_px": 0}

    all_controls = content_controls(ui)
    vw = dlg.rect[2] - dlg.rect[0]
    vh = dlg.rect[3] - dlg.rect[1]
    # 뷰포트보다 큰 컨트롤(주로 GroupBox 컨테이너)은 어떤 스크롤 위치에서도
    # 온전히 담길 수 없다. 판정 대상에서 분리해 따로 보고한다.
    oversized = [c for c in all_controls
                 if c.size[0] > vw or c.size[1] > vh]
    controls = [c for c in all_controls if c not in oversized]
    overflow = scrollable_extent(ui, all_controls)

    pages, seen = [], set()
    prev_layout = None
    hit_limit = True

    for i in range(max_pages):
        cur_dlg = content_dialog(ui) or dlg
        layout = tuple(sorted((c.hwnd, c.rect[1]) for c in content_controls(ui)))
        if layout == prev_layout:
            hit_limit = False
            break
        prev_layout = layout

        pages.append(capture_fn(i, cur_dlg.rect))
        for c in content_controls(ui):
            if in_viewport(c, cur_dlg.rect):
                seen.add(c.hwnd)

        if overflow <= 0:
            hit_limit = False
            break
        scroll_down(ui, notches=notches)

    return {"pages": pages, "seen": seen, "controls": controls,
            "oversized": oversized, "total_controls": len(all_controls),
            "hit_limit": hit_limit, "overflow_px": overflow}


def list_ctrls(ui, min_height=40):
    """본문의 목록 컨트롤(ListCtrl). 화면 위->아래, 좌->우 순서로 반환한다.

    면적 기준으로 고르면 안 된다 — DICOM 화면에는 비어 있는 큰 목록(Verification
    로그 등)이 함께 있어서, 가장 큰 것을 고르면 **빈 영역을 클릭하다 끝난다**
    (실측으로 확인된 실패). 대신 모든 목록을 순서대로 돌면서 `list_rows()`로
    실제 행이 있는 것만 다룬다.
    """
    out = [c for c in content_controls(ui)
           if c.text.strip() == "ListCtrl" and c.size[1] >= min_height]
    out.sort(key=lambda c: (c.rect[1], c.rect[0]))
    return out


def list_rows(ui, list_ctrl):
    """목록의 **실제 행** 목록.

    행은 `ListItem`이라는 자식 윈도우로 존재하고, **데이터가 없는 행은 hidden**
    이다(실측: SCP 목록에 서버가 1개면 ListItem 1번만 visible, 2~7번은 hidden).
    따라서 좌표를 추정할 필요가 없다 — 보이는 ListItem이 곧 실제 행이고, 그
    rect가 정확한 클릭 지점이다.
    """
    from .ui import children
    rows = []
    for c in children(list_ctrl.hwnd, 1):
        if c.text.strip() == "ListItem" and c.visible:
            rows.append(c)
    rows.sort(key=lambda c: c.rect[1])
    return rows


def list_row_slots(ui, list_ctrl):
    """행 슬롯 총 개수(보이는 것 + hidden). 목록이 꽉 찼는지 판단에 쓴다."""
    from .ui import children
    return len([c for c in children(list_ctrl.hwnd, 1)
                if c.text.strip() == "ListItem"])


def list_scrollbar(ui, list_ctrl):
    """목록 자체의 스크롤바(크기가 0이면 스크롤 불필요)."""
    from .ui import children
    for c in children(list_ctrl.hwnd, 1):
        if c.text.strip() == "Scroll" and c.size[0] > 0 and c.size[1] > 0:
            return c
    return None


def row_click_point(ui, row_ctrl):
    """행을 클릭할 좌표.

    행 안에 CheckBox 자식이 있으면 그 오른쪽을 클릭한다. 체크박스를 그대로
    누르면 **설정을 바꿔버린다**(Tag Mapping / Overlay Item 등의 목록이 그렇다).
    """
    from .ui import children
    l, t, r, b = row_ctrl.rect
    y = (t + b) // 2
    x = l + 80
    for kid in children(row_ctrl.hwnd, 1):
        if kid.text.strip() == "CheckBox" and kid.visible:
            x = max(x, kid.rect[2] + 24)
    return (min(x, r - 6), y)


def scroll_list(ui, list_ctrl, notches=-3, settle=0.25):
    """목록 내부를 스크롤한다(목록 위에 커서를 두고 굴린다)."""
    l, t, r, b = list_ctrl.rect
    ui.wheel(((l + r) // 2, (t + b) // 2), notches, settle=settle)


def scroll_list_to_top(ui, list_ctrl, steps=10):
    for _ in range(steps):
        scroll_list(ui, list_ctrl, notches=4, settle=0.08)


def iter_list_rows(ui, list_ctrl, on_row, max_pages=12):
    """목록의 모든 행을 순회하며 `on_row(page, index, row_ctrl)`를 호출한다.

    행이 화면보다 많으면 목록을 스크롤해 끝까지 내려간다. 종료 판정은
    "스크롤해도 행 배치가 그대로인가"로 하며, 행 개체가 재활용되는 가상 목록도
    다룰 수 있도록 스크롤 전후의 첫 행 위치·개수를 함께 본다.

    반환: 처리한 행 수
    """
    scroll_list_to_top(ui, list_ctrl)
    handled = 0
    slots = list_row_slots(ui, list_ctrl)
    scrollbar = list_scrollbar(ui, list_ctrl)

    for page in range(max_pages):
        rows = list_rows(ui, list_ctrl)
        if not rows:
            break
        for idx, row in enumerate(rows):
            on_row(page, idx, row)
            handled += 1

        # 목록이 꽉 차 있지 않으면 더 볼 행이 없다.
        if len(rows) < slots or scrollbar is None:
            break
        before = (len(rows), rows[0].rect[1], rows[-1].rect[1])
        scroll_list(ui, list_ctrl, notches=-len(rows))
        after_rows = list_rows(ui, list_ctrl)
        if not after_rows:
            break
        after = (len(after_rows), after_rows[0].rect[1], after_rows[-1].rect[1])
        if before == after:
            # 위치가 그대로면 더 내려갈 곳이 없다. 다만 가상 목록은 내용만
            # 바뀌므로, 스크롤바 유무와 페이지 상한으로 무한 루프를 막는다.
            break
    return handled


def scp_detail_fields(ui):
    """DICOM SCP 상세 입력값을 읽는다.

    사용자 확인(2026-08-18): DICOM 서버 설정은 **SCP 목록의 항목을 클릭해야
    상세 정보가 나타난다.** 클릭 후 이 함수로 Edit 값을 읽어 DB `AE_LIST`의
    실제 등록값과 대조하면, 캡처 비교보다 강한 판정 근거가 된다.

    반환: {"edits": [(ctrl_id, 값), ...], "texts": [값...]}
    화면마다 필드 구성이 달라 컨트롤 ID를 고정하지 않고 전부 읽어 온다.
    """
    edits = []
    for c in content_controls(ui):
        if c.cls == "Edit":
            edits.append((c.ctrl_id, ui.get_text(c)))
    edits.sort(key=lambda x: x[0])
    return {"edits": edits, "texts": [v for _, v in edits if v]}


# --- 화면별 값 추출 (테마/폰트 비의존) --------------------------------
COMBO_VALUE_CHILD_ID = 3     # 커스텀 콤보의 숨은 Edit (실측)
DECORATION_TEXTS = ("GroupBox", "IconButton", "TransparentBackIconButton",
                    "ScrollWnd", "Scroll", "ItemWnd", "ItemList", "Slider",
                    "TextSplitButton")


def combo_value(ui, control):
    """커스텀 콤보의 실제 표시값.

    부모 컨트롤의 텍스트는 폭에 맞춰 **잘려 있다**(예: 'ScreenLUT' -> 'ScreenLU').
    숨은 자식 `Edit`에 전체 값이 들어 있어 그것을 우선한다(Bellalun에서 검증된
    패턴이며 VXvue에서도 동일함을 실측 확인).
    """
    from .ui import children
    for kid in children(control.hwnd, 1):
        if kid.cls == "Edit" and kid.text:
            return kid.text
    return control.text


def screen_values(ui, title_text=None):
    """현재 Setting 화면의 **값만** 뽑아 JSON 친화적 dict로 반환한다.

    테마·폰트가 바뀌면 색상·창 크기·폰트가 달라지지만 설정 값과 옵션은 같다
    (사용자 확인, 2026-08-18). 그래서 좌표·크기·픽셀을 일절 담지 않고 값만
    담는다. 이 구조가 테마에 영향받지 않는 판정 근거가 된다.

    읽을 수 있는 것과 읽을 수 없는 것을 정직하게 구분해 담는다.

    | 종류 | 읽기 | 방법 |
    |---|---|---|
    | Edit | 가능 | `WM_GETTEXT` |
    | 콤보 | 가능 | 숨은 자식 Edit의 값(부모 텍스트는 잘림) |
    | 라벨(Static) | 가능 | `WM_GETTEXT` |
    | **체크박스/라디오** | **불가** | 커스텀 owner-draw라 `BM_GETCHECK`가 항상 0 |

    체크박스 상태는 UI에서 읽을 수 없으므로 **컨트롤 ID 목록만** 남기고, 실제
    on/off 값은 DB 스냅샷(`core/config_snapshot.py`)으로 검증한다. 픽셀을 찍어
    체크 여부를 판정하는 방법은 테마에 종속되므로 쓰지 않는다.
    """
    values = {"title": title_text or title(ui),
              "edits": {}, "combos": {}, "labels": [],
              "unreadable_state_controls": [], "buttons": []}

    for c in content_controls(ui):
        text = c.text.strip()
        if c.cls == "Edit":
            values["edits"].setdefault(str(c.ctrl_id), ui.get_text(c))
        elif c.cls == "Static":
            if text:
                values["labels"].append(text)
        elif text == "CheckBox":
            values["unreadable_state_controls"].append(
                {"id": c.ctrl_id, "kind": "CheckBox"})
        elif text in ("TextButton",):
            values["buttons"].append(c.ctrl_id)
        elif text in DECORATION_TEXTS or c.ctrl_id in (1, 2, 3):
            continue
        elif c.cls.startswith("AfxWnd"):
            # 남은 AfxWnd 중 자식 Edit을 가진 것은 콤보로 본다.
            val = combo_value(ui, c)
            if val and val != text:
                values["combos"].setdefault(str(c.ctrl_id), val)
            elif val:
                values["combos"].setdefault(str(c.ctrl_id), val)

    values["labels"] = sorted(set(values["labels"]))
    values["buttons"] = sorted(set(values["buttons"]))
    values["unreadable_state_controls"].sort(key=lambda x: x["id"])
    return values


def diff_all_screen_values(baseline, current):
    """두 `{화면 제목: screen_values(...)}` 사전을 비교한다.

    TC14(화면 순회)와 Setting Export/Import 회귀가 함께 쓴다. 둘의 차이는
    "이 차이를 FAIL로 볼 것인가"에 있을 뿐, 무엇이 다른지 찾는 로직은 같다
    (2026-08-19 정리: 값 완전 일치 판정은 Export/Import TC의 책임이고, TC14는
    같은 비교 결과를 '확인 필요' 참고 정보로만 쓴다).

    반환: dict(missing=[화면...], added=[화면...],
              struct_diffs=[옵션 자체가 생기거나 없어진 항목...],
              value_diffs=[같은 옵션인데 표시 텍스트가 다른 항목...])
    """
    missing = sorted(set(baseline) - set(current))
    added = sorted(set(current) - set(baseline))
    struct_diffs, value_diffs = [], []
    for title in sorted(set(baseline) & set(current)):
        b, c = baseline[title], current[title]
        for kind in ("edits", "combos"):
            bd, cd = b.get(kind) or {}, c.get(kind) or {}
            for key in sorted(set(bd) | set(cd)):
                if key not in bd or key not in cd:
                    struct_diffs.append("%s / %s[%s]: %s"
                                        % (title, kind, key,
                                           "새 옵션" if key not in bd else "옵션 없어짐"))
                elif bd.get(key) != cd.get(key):
                    value_diffs.append("%s / %s[%s]: %r -> %r"
                                       % (title, kind, key, bd.get(key), cd.get(key)))
        if sorted(b.get("labels") or []) != sorted(c.get("labels") or []):
            only_b = sorted(set(b.get("labels") or []) - set(c.get("labels") or []))
            only_c = sorted(set(c.get("labels") or []) - set(b.get("labels") or []))
            struct_diffs.append("%s / labels: 기준에만 %s / 현재에만 %s"
                                % (title, only_b[:5], only_c[:5]))
        bids = [x["id"] for x in b.get("unreadable_state_controls") or []]
        cids = [x["id"] for x in c.get("unreadable_state_controls") or []]
        if sorted(bids) != sorted(cids):
            struct_diffs.append("%s / 체크박스 구성: %s -> %s" % (title, bids, cids))
    return {"missing": missing, "added": added,
            "struct_diffs": struct_diffs, "value_diffs": value_diffs}


def capture_all_screen_values(ui):
    """Setting 전체를 순회하며 화면별 표시값(`screen_values`)만 모은다.

    캡처·스크롤 없이 값만 필요할 때 쓴다(Setting Export/Import 회귀의 S0/S2
    UI 표시값 비교). `content_controls()`는 스크롤 밖 컨트롤도 포함하므로
    스크롤하지 않아도 값 자체는 빠짐없이 읽힌다.
    """
    out = {}

    def on_screen(_mi, _mj, _ctrl_id, scr_title):
        if scr_title:
            out[scr_title] = screen_values(ui, scr_title)

    walk(ui, on_screen=on_screen)
    return out
