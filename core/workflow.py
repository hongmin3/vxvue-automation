# -*- coding: utf-8 -*-
r"""촬영·전송 워크플로 — TC02/04/05/06/07/08의 공통 인프라.

Registration에서 MWL 처방을 열어 촬영하고, 그 영상을 Send / Print / Export
하는 흐름을 한 곳에 모았다. **여러 TC가 같은 앞부분을 밟기 때문에** 각 TC
모듈이 이 흐름을 따로 구현하면 곧 어긋난다.

## 실측으로 확정한 것 (2026-08-19)

전부 이 세션에서 실제로 화면을 열고 눌러 확인한 값이다. 다른 제품(Bellalun)의
ID를 가져오지 않았다(`CLAUDE.md` 3절).

### 화면 전환 · 목록

| 대상 | 값 |
|---|---|
| 메인 네비 TabItem | Tab `31197` 아래 `8`=Registration `9`=Exposure `10`=Database `11`=Viewer `12`=Print `13`=Setting `14`=Exit |
| Registration 상단 탭 | `31201`=Scheduled `31202`=Unscheduled `31203`=Reserved |
| Registration 결과 목록 / SPS 목록 | `31119` / `31120` |
| 결과 요약 Static | `30013` — `"Range: 2026-08-19 ~ 2026-08-19, Result: 2 / 2"` 로 **평문 판독 가능** |
| Database 목록 | `31191` |
| 촬영 상태 | `31093` `AcquisitionState` — owner-draw라 캡처+OCR로 읽는다. 실측 문구: `"Not Exposure mode"`(검사 없음) / `"Ready"`(촬영 준비 완료) |

### Registration > Scheduled 버튼 (탭마다 구성이 다르다)

`30371`=Start `30391`=Emerg. `30291`=Reject / `30378`=Multi-Study `30361`=Send
`30328`=Reserve. **Reserved 탭에서는 같은 위치의 ID가 다르다**(`30298`=Edit,
`30301`=Export 등) — 탭을 바꾼 뒤 ID를 그대로 재사용하면 다른 버튼을 누른다.

### Study 등록 시 뜨는 팝업 — 사양서1 p.37~38 `VP-460`

Start를 누르면 **맵핑되지 않은 Procedure Code가 있을 때** 확인 팝업이 먼저 뜬다.

```
Info: "Some procedures are not existing. Do you want to register them?"
      [Yes] [No] [Cancel]
```

사양서1 p.38 원문: *"Yes : Procedure Mapping 창 팝업 / No : Procedure Mapping
하지 않고 Exposure Mode 로 전환 / Cancel : Study 등록을 취소"*

자동화는 **매핑하지 않는 쪽(No)** 을 택한다. 매핑은 제품 설정(Procedure ↔ Code)을
바꾸는 조작이고, 이 시험대의 XIPL은 Bellalun과 설치를 공유하므로 함부로 건드리면
다른 제품 자동화에 영향이 간다. 매핑 창이 이미 떠 있으면 제목줄 닫기 버튼
(`ctrl_id=-4`)으로 닫는다 — 실측 결과 그렇게 닫아도 Study 등록은 진행되고
Exposure Mode로 전환된다.

### 촬영

`config.json`의 `viewer.demo_exposure_key`(=`F2`)를 누른다. 실측: 약 25초 뒤
흉부 영상이 획득되고 썸네일에 `1-1 Chest PA`가 생긴다. 상단 Tool 레일의
`Change`(30474)/`Send`(30294)가 활성화된다.

**촬영 직후 `Error: "Image process parameter file does not exist."` 팝업이 떴다**
(실측). XIPL 서버 로그 근거:

```
[SERVER] Loading base parameter : Chest PA_normal_H.hs8
[SERVER] Parameter file not found
```

파일 자체는 `C:\XIPL\PARAMETER\VXvue\Chest PA_normal_H.hs8`로 **존재한다.**
즉 XIPL 서버가 보는 파라미터 경로가 그 하위 폴더를 가리키지 않는 **환경 구성
문제**로 보인다(Bellalun과 XIPL 설치를 공유해 루트에 `*.pim`을 두는 구성이다).
이 자동화는 이 사실을 판정에 그대로 남기고 **설정을 임의로 바꾸지 않는다** —
`Setting > Integration > XIPL`의 파라미터 경로는 다른 제품에 영향을 주므로
사용자 확인이 필요하다(`NEXT_TASK.md`에 남김).

### Tool 레일 (Exposure, 좌 → 우)

`30360`=Select `30284`=Rect. `30390`=Zoom `30338`=Pan `30357`=CW `30356`=CCW
`30354`=R `30327`=L `30290`=Reject `30435`=Retake `30474`=Change `30294`=Send

### Database 버튼

1행 `30334`=New `30318`=Insert `30298`=Edit `30332`=Move Img `30337`=Open
`30292`=Reject `30275`=Close `30300`=Export `30315`=Import
2행 `30373`=Stitch `30294`=Send `30295`=Multi-Send `30293`=Print `30372`=Statistics
`30378`=Multi-Study `30348`=QXLink `30471`=Report `30473`=Compare

`Send`가 Exposure와 Database에서 **같은 ID(30294)** 다 — 기능별로 ID가 일관된다.

### Send 확인 팝업 (실측)

```
Send: "Do you want to send all images of the selected study?"
      [All Images] [Selected] [Cancel]
```

`27002`=All Images `27001`=Selected `27000`=Cancel. (`27003`은 같은 대화상자에
있으나 화면에 보이지 않는다 — 누르지 않는다.)
"""

import os
import re
import time

from . import dialogs

# --- 실측 컨트롤 ID ---------------------------------------------------
NAV_TAB_CONTAINER = 31197
NAV = {"registration": 8, "exposure": 9, "database": 10, "viewer": 11,
       "print": 12, "setting": 13, "exit": 14}

REG_TAB = {"scheduled": 31201, "unscheduled": 31202, "reserved": 31203}
REG_RESULT_LIST = 31119
REG_SPS_LIST = 31120
RESULT_SUMMARY_STATIC = 30013
REG_SEARCH_BUTTON = 30689
REG_DEFAULT_BUTTON = 30935
# 검색 조건 프리셋 스플릿 버튼(= REG_DEFAULT_BUTTON, `TextSplitButton`).
# 실측 2026-08-21: 자식이 둘이다 — `1`은 라벨(누르면 그 프리셋을 바로 적용),
# `2`는 드롭다운 화살표. 화살표를 누르면 `ItemList`라는 **별도 최상위 창**이
# 뜨고 그 안에 항목 버튼 둘이 있다(각각 캡처+OCR로 라벨 확정).
REG_PRESET_ARROW_CHILD = 2
REG_PRESET = {"default": 30940, "clear": 30941}

# Scheduled 탭 전용 (탭마다 구성이 다르다 — docstring 참고)
SCHEDULED_START = 30371
SCHEDULED_RESERVE = 30328
SCHEDULED_REJECT = 30291

ACQ_STATE = 31093

DB_LIST = 31191
DB_BUTTON = {"new": 30334, "insert": 30318, "edit": 30298, "move_img": 30332,
             "open": 30337, "reject": 30292, "close": 30275, "export": 30300,
             "import": 30315, "stitch": 30373, "send": 30294,
             "multi_send": 30295, "print": 30293, "statistics": 30372,
             "multi_study": 30378, "qxlink": 30348, "report": 30471,
             "compare": 30473}

TOOL = {"select": 30360, "rect": 30284, "zoom": 30390, "pan": 30338,
        "cw": 30357, "ccw": 30356, "r": 30354, "l": 30327,
        "reject": 30290, "retake": 30435, "change": 30474, "send": 30294}

SEND_SCOPE = {"all": 27002, "selected": 27001, "cancel": 27000}

THUMBNAIL_PANEL = 30887
DIALOG_CLOSE_X = -4          # 제목줄 닫기 버튼(Procedure Mapping 등)

# Print 화면
PRINT_SERVER_COMBO = 30955
PRINT_FILM_SIZE_COMBO = 30956
PRINT_ORIENTATION_COMBO = 30957

# 촬영 직후 뜨는, 판정을 바꾸지 않는(=환경 문제로 확인된) 팝업 문구
KNOWN_ACQUIRE_WARNINGS = ("image process parameter file does not exist",)


class WorkflowError(RuntimeError):
    pass


# --- 기본 조작 ---------------------------------------------------------
def by_id(ui, ctrl_id, depth=8):
    return [c for c in ui.controls(max_depth=depth) if c.ctrl_id == ctrl_id]


def dialog_message(ui, dlg, cfg=None):
    """팝업 문구를 읽는다(표준 API -> OCR fallback). `core/dialogs.read()` 위임."""
    return dialogs.read(ui, dlg, cfg).get("message", "")


def pending_dialogs(ui, max_iters=4, timeout=3, evidence_dir=None, cfg=None):
    """조작을 막는 팝업을 걷어내고 **처리 기록**을 돌려준다.

    실제 판독·분류·처리는 `core/dialogs.py`가 한다 — 이 저장소의 팝업 처리
    경로는 그 모듈 하나다(사용자 지적, 2026-08-20: 같은 대응이 여러 곳에
    땜질돼 있었고 팝업을 분류하지 않고 닫았다).

    반환값은 `DialogRecord` 리스트다. `record.blocking`이 True인 것(오류·경고·
    모르는 팝업)은 **판정에 반영해야 한다** — 성공 알림과 같이 취급해 조용히
    넘기면 오류가 사라진다. 확인 팝업(`QUESTION`)은 닫지 않고 남겨 두므로,
    사양을 아는 호출부가 직접 눌러야 한다(`start_study()`가 사양서1 p.38을
    근거로 "No"를 택하는 것처럼).
    """
    return dialogs.clear_blocking(ui, cfg, evidence_dir=evidence_dir,
                                  max_iters=max_iters)


def dialog_texts(records):
    """기록 리스트를 예전 반환형(문구 리스트)으로 바꾼다.

    기존 호출부가 문구 리스트를 기대하고 있어 호환용으로 남긴다. 새 코드는
    `DialogRecord`를 그대로 쓰고 `record.blocking`을 판정에 반영할 것.
    """
    out = []
    for r in records or []:
        if isinstance(r, str):
            out.append(r)
        else:
            out.append(("%s: %s" % (r.title, r.message)).strip(": ")
                       or "(문구 미노출)")
    return out


def goto(ui, name, settle=2.5, clear_dialogs=True):
    """메인 네비(우측 세로 탭)로 화면을 전환한다.

    전환 전에 떠 있는 팝업을 정리한다(`pending_dialogs` docstring 참고) —
    팝업이 남아 있으면 탭 클릭이 조용히 무시된다.
    """
    from .ui import children
    if name not in NAV:
        raise WorkflowError("알 수 없는 화면: %s" % name)
    if clear_dialogs:
        pending_dialogs(ui)
    tabs = by_id(ui, NAV_TAB_CONTAINER)
    if not tabs:
        raise WorkflowError("메인 네비 Tab(%d)을 찾지 못했습니다." % NAV_TAB_CONTAINER)
    items = [c for c in children(tabs[0].hwnd, 2) if c.text.strip() == "TabItem"]
    target = next((c for c in items if c.ctrl_id == NAV[name]), None)
    if target is None:
        raise WorkflowError("%s TabItem(id %d)을 찾지 못했습니다." % (name, NAV[name]))
    ui.click(target, settle=settle)
    return True


def list_rows(ui, list_id):
    """목록(ListCtrl)의 실제 행. 빈 행은 hidden이라 보이는 ListItem이 곧 데이터다."""
    from .ui import children
    rows = []
    for lc in by_id(ui, list_id):
        for c in children(lc.hwnd, 2):
            if c.text.strip() == "ListItem" and c.visible:
                rows.append(c)
    rows.sort(key=lambda c: c.rect[1])
    return rows


def click_row(ui, row_ctrl, settle=1.2):
    """행을 클릭한다. 좌표는 방금 찾은 컨트롤의 rect에서 계산한다."""
    l, t, r, b = row_ctrl.rect
    ui.click((l + 100, (t + b) // 2), settle=settle)
    return True


def result_summary(ui):
    """`Result: n / n` 요약 문구. 평문으로 읽힌다(실측)."""
    hits = by_id(ui, RESULT_SUMMARY_STATIC)
    for c in hits:
        text = (ui.get_text(c) or "").strip()
        if text:
            return text
    return ""


def acquisition_state(ui, cfg=None):
    """촬영 상태(`AcquisitionState`)를 캡처+OCR로 읽는다.

    owner-draw라 `GetWindowText`로는 컨트롤 이름(`AcquisitionState`)만 나온다.
    실측 문구: `"Not Exposure mode"`(검사 미등록) / `"Ready"`(촬영 준비 완료).
    """
    hits = by_id(ui, ACQ_STATE)
    if not hits:
        return ""
    try:
        import pytesseract
        from PIL import ImageGrab
    except ImportError:
        return ""
    exe = ((cfg or {}).get("xipl") or {}).get("tesseract_exe") \
        or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
    img = ImageGrab.grab(bbox=hits[0].rect, all_screens=True)
    img = img.resize((img.width * 3, img.height * 3))
    return pytesseract.image_to_string(img, config="--psm 7").strip()


def is_ready(ui, cfg=None):
    return "ready" in acquisition_state(ui, cfg).lower()


def thumbnail_count(ui):
    """썸네일 패널의 영상 개수(획득한 영상 수).

    실측: 패널(30887) > `ItemWnd` 아래에 영상 1장당 `ScrollWnd` 하나가 생긴다.
    """
    from .ui import children
    for panel in by_id(ui, THUMBNAIL_PANEL):
        wnd = next((k for k in children(panel.hwnd, 3)
                    if k.text.strip() == "ItemWnd"), None)
        if wnd is None:
            continue
        return len([k for k in children(wnd.hwnd, 2)
                    if k.visible and k.size[0] > 60 and k.size[1] > 60])
    return 0


def step_items(ui):
    """썸네일 패널의 Step 항목 컨트롤 목록(위 -> 아래).

    항목 하나가 등록된 Step 하나다. 촬영이 끝난 항목에는 영상 미리보기가
    들어가고, 아직 촬영하지 않은 항목은 라벨만 있는 빈 박스다(실측).
    """
    from .ui import children
    for panel in by_id(ui, THUMBNAIL_PANEL):
        wnd = next((k for k in children(panel.hwnd, 3)
                    if k.text.strip() == "ItemWnd"), None)
        if wnd is None:
            continue
        items = [k for k in children(wnd.hwnd, 2)
                 if k.visible and k.size[0] > 60 and k.size[1] > 60]
        items.sort(key=lambda k: k.rect[1])
        return items
    return []


def unshot_step_items(ui, dominant_threshold=0.45):
    """**아직 촬영하지 않은** Step 항목만 돌려준다.

    ## 왜 필요한가 (실측 2026-08-20)

    F2는 **지금 선택된 Step**을 촬영한다. 이미 촬영이 끝난 항목이 선택돼 있으면
    아무 일도 일어나지 않는다 — 실측에서 Chest PA를 촬영한 뒤 AP를 등록하고 F2를
    눌렀는데, 선택이 첫(촬영 완료) 항목에 남아 있어 130초를 기다렸다가
    `SERIES` 증가 없이 실패했다. "촬영했는데 실패"가 아니라 **촬영을 시작조차
    하지 않은 것**이다.

    촬영 여부는 항목 캡처의 빈 정도(`core/screen.blankness()`)로 구분한다 —
    영상이 들어간 항목은 픽셀이 다양하고, 라벨만 있는 빈 박스는 대부분 단색이다.
    """
    from . import screen as screen_mod
    out = []
    for item in step_items(ui):
        try:
            # blankness()는 (is_blank, stddev, dominant_ratio)를 돌려준다.
            # 영상이 들어간 항목은 픽셀이 다양해 dominant_ratio가 낮고, 라벨만
            # 있는 빈 박스는 배경색 하나가 대부분을 차지해 높다.
            _is_blank, _std, dominant = screen_mod.blankness(_grab(item.rect))
        except Exception:                                # noqa: BLE001
            dominant = None
        if dominant is None or dominant >= dominant_threshold:
            out.append(item)
    return out


def _grab(rect):
    from PIL import ImageGrab
    return ImageGrab.grab(bbox=rect, all_screens=True)


def select_unshot_step(ui, settle=1.2):
    """촬영하지 않은 Step 중 첫 번째를 선택한다.

    반환: {"ok": bool, "selected": rect, "unshot": n, "total": n}
    """
    items = step_items(ui)
    unshot = unshot_step_items(ui)
    if not unshot:
        return {"ok": False, "selected": None, "unshot": 0, "total": len(items)}
    ui.click(unshot[0], settle=settle)
    return {"ok": True, "selected": unshot[0].rect, "unshot": len(unshot),
            "total": len(items)}


def select_first_image(ui, settle=1.2):
    """썸네일의 첫 영상을 선택한다. 선택 전에는 Send가 동작하지 않는다."""
    from .ui import children
    for panel in by_id(ui, THUMBNAIL_PANEL):
        wnd = next((k for k in children(panel.hwnd, 3)
                    if k.text.strip() == "ItemWnd"), None)
        if wnd is None:
            continue
        items = sorted([k for k in children(wnd.hwnd, 2)
                        if k.visible and k.size[0] > 60 and k.size[1] > 60],
                       key=lambda k: k.rect[1])
        if items:
            ui.click(items[0], settle=settle)
            return True
    return False


# --- MWL 처방 열기 -----------------------------------------------------
def registration_tab(ui, which="scheduled", settle=2.0, timeout=15, poll=1.0):
    """Registration 상단 탭(Scheduled/Unscheduled/Reserved)으로 전환한다.

    **화면 전환 직후에는 탭 컨트롤이 아직 안 그려져 있을 수 있다**(실측
    2026-08-20: `goto("registration")` 직후 `31201`을 못 찾아 TC04가 첫 Step에서
    실패했다. 같은 코드가 TC02에서는 통과했다 — 즉 타이밍 문제다). 그래서
    나타날 때까지 상한을 두고 기다리고, 팝업이 클릭을 막고 있는지도 확인한다.
    """
    end = time.time() + timeout
    tried_dialogs = False
    while time.time() < end:
        hits = by_id(ui, REG_TAB[which])
        if hits:
            ui.click(hits[0], settle=settle)
            return True
        if not tried_dialogs and dialogs.present(ui):
            # 팝업이 떠 있으면 화면 전환 자체가 무시된다.
            pending_dialogs(ui, cfg=None)
            goto(ui, "registration", clear_dialogs=False)
            tried_dialogs = True
        time.sleep(poll)
    raise WorkflowError(
        "Registration %s 탭(%d)이 %d초 안에 나타나지 않았습니다. Registration "
        "화면으로 전환되지 않았거나 팝업이 클릭을 막고 있을 수 있습니다."
        % (which, REG_TAB[which], timeout))


def search(ui, settle=3.0):
    hits = by_id(ui, REG_SEARCH_BUTTON)
    if not hits:
        raise WorkflowError("Search 버튼(%d)을 찾지 못했습니다." % REG_SEARCH_BUTTON)
    ui.click(hits[0], settle=settle)
    return result_summary(ui)


def query_mwl(ui, cfg):
    """Registration > Scheduled에서 MWL을 조회하고 목록 행을 돌려준다.

    반환: (요약 문구, [행 컨트롤...])
    """
    goto(ui, "registration")
    time.sleep(1.0)
    registration_tab(ui, "scheduled")
    summary = search(ui)
    time.sleep(1.0)
    # owner-draw 목록은 값이 열 폭을 넘으면 `...`로 줄인다. 잘린 값을 그대로
    # OCR하지 않고, 표준 헤더의 해당 열 경계를 마우스로 늘린 뒤 다시 읽는다.
    expand_truncated_columns(ui, REG_RESULT_LIST, cfg)
    return summary or result_summary(ui), list_rows(ui, REG_RESULT_LIST)


def row_cell_text(ui, row_ctrl, cfg=None, scale=3):
    """행 전체를 캡처+OCR해 한 줄 텍스트로 돌려준다.

    목록 셀은 owner-draw라 표준 API로 읽을 수 없다(TC13/TC14와 같은 한계).
    값 대조는 이 OCR 결과와 **DB / MWL API 값**을 함께 본다.
    """
    try:
        import pytesseract
        from PIL import ImageGrab
    except ImportError:
        return ""
    exe = ((cfg or {}).get("xipl") or {}).get("tesseract_exe") \
        or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
    img = ImageGrab.grab(bbox=row_ctrl.rect, all_screens=True)
    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale))
    return pytesseract.image_to_string(img, config="--psm 7").strip()


def _header_item_rects(ui, list_id):
    """SysHeader32의 열 사각형을 화면 좌표로 읽는다.

    Header 메시지는 대상 프로세스 메모리의 RECT 포인터를 요구하므로 작은 원격
    버퍼를 사용한다. 값을 읽기만 하며 제품 데이터는 변경하지 않는다.
    """
    import ctypes
    from ctypes import wintypes
    from .ui import children

    lists = by_id(ui, list_id)
    if not lists:
        return None, []
    header = next((c for c in children(lists[0].hwnd, 2)
                   if c.cls == "SysHeader32" and c.visible), None)
    if header is None:
        return None, []

    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    HDM_GETITEMCOUNT, HDM_GETITEMRECT = 0x1200, 0x1207
    # 전역 SendMessageW 시그니처를 바꾸면 core.ui의 WM_GETTEXT 버퍼 호출이
    # 깨지므로 이 함수 전용 래퍼를 사용한다.
    send_message = ctypes.WINFUNCTYPE(
        wintypes.LPARAM, wintypes.HWND, wintypes.UINT,
        wintypes.WPARAM, wintypes.LPARAM)(("SendMessageW", u32))
    count = int(send_message(header.hwnd, HDM_GETITEMCOUNT, 0, 0))
    if count <= 0:
        return header, []

    PROCESS_VM_OPERATION = 0x0008
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    MEM_COMMIT, MEM_RELEASE, PAGE_READWRITE = 0x1000, 0x8000, 0x04
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                   ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k32.VirtualAllocEx.restype = ctypes.c_void_p
    k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.POINTER(ctypes.c_size_t)]
    k32.ReadProcessMemory.restype = wintypes.BOOL
    k32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                  ctypes.c_size_t, wintypes.DWORD]
    k32.VirtualFreeEx.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    proc = k32.OpenProcess(PROCESS_VM_OPERATION | PROCESS_VM_READ |
                           PROCESS_VM_WRITE | PROCESS_QUERY_LIMITED_INFORMATION,
                           False, ui.pid)
    if not proc:
        return header, []
    remote = None
    try:
        remote = k32.VirtualAllocEx(proc, None, ctypes.sizeof(wintypes.RECT),
                                    MEM_COMMIT, PAGE_READWRITE)
        if not remote:
            return header, []
        out = []
        for idx in range(count):
            ok = send_message(header.hwnd, HDM_GETITEMRECT, idx, remote)
            if not ok:
                continue
            rect = wintypes.RECT()
            read = ctypes.c_size_t()
            if not k32.ReadProcessMemory(proc, remote, ctypes.byref(rect),
                                         ctypes.sizeof(rect), ctypes.byref(read)):
                continue
            out.append((idx, (header.rect[0] + rect.left, header.rect[1] + rect.top,
                              header.rect[0] + rect.right, header.rect[1] + rect.bottom)))
        return header, out
    finally:
        if remote:
            k32.VirtualFreeEx(proc, remote, 0, MEM_RELEASE)
        k32.CloseHandle(proc)


_EXPANDED_LIST_COLUMNS = set()


def expand_truncated_columns(ui, list_id, cfg=None, extra=140, max_rows=5):
    """`...`로 잘린 owner-draw 목록 열을 찾아 헤더 경계를 드래그해 넓힌다.

    Patient ID에만 한정하지 않는다. 보이는 각 셀을 따로 OCR해 줄임표가 있는 열을
    모두 찾고, 현재 SysHeader32의 실제 경계를 기준으로 확장한다. 같은 화면에서
    무한히 넓어지지 않도록 목록/프로세스당 한 번만 수행한다.
    """
    import re
    try:
        import pytesseract
        from PIL import ImageGrab
    except ImportError:
        return {"changed": [], "reason": "OCR unavailable"}

    key = (ui.pid, list_id)
    if key in _EXPANDED_LIST_COLUMNS:
        return {"changed": [], "reason": "already checked"}

    exe = ((cfg or {}).get("xipl") or {}).get("tesseract_exe") \
        or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe

    header, rects = _header_item_rects(ui, list_id)
    rows = list_rows(ui, list_id)[:max_rows]
    if header is None or not rects or not rows:
        return {"changed": [], "reason": "header/rows unavailable"}

    clipped = set()
    # 셀마다 Tesseract를 호출하면 열×행 수만큼 수십 초가 든다. 보이는 목록 전체를
    # 한 번만 OCR하고, 줄임표 토큰의 X 중심을 헤더 열 사각형에 매핑한다.
    left = min(r[0] for _i, r in rects)
    right = max(r[2] for _i, r in rects)
    top = min(r.rect[1] for r in rows)
    bottom = max(r.rect[3] for r in rows)
    scale = 3
    try:
        img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        img = img.resize((img.width * scale, img.height * scale))
        data = pytesseract.image_to_data(img, config="--psm 6",
                                         output_type=pytesseract.Output.DICT)
        for i, raw in enumerate(data.get("text", [])):
            if not re.search(r"\.{2,}|…", raw or ""):
                continue
            cx = left + (data["left"][i] + data["width"][i] // 2) // scale
            hit = next((idx for idx, rect in rects if rect[0] <= cx < rect[2]), None)
            if hit is not None:
                clipped.add(hit)
    except Exception:                                    # noqa: BLE001
        return {"changed": [], "reason": "OCR failed"}

    changed = []
    # 오른쪽 열부터 처리하면 앞 열 확장으로 뒤쪽 경계가 이동하는 영향을 줄인다.
    for idx in sorted(clipped, reverse=True):
        _header, current = _header_item_rects(ui, list_id)
        item = next((r for i, r in current if i == idx), None)
        if item is None:
            continue
        x, y = item[2] - 1, (item[1] + item[3]) // 2
        # 화면 밖 경계는 스크롤 없이 안전하게 잡을 수 없으므로 건너뛴다.
        if not (header.rect[0] + 4 <= x <= header.rect[2] - 4):
            continue
        ui.drag((x, y), (x + extra, y), duration=0.45, settle=0.4)
        changed.append(idx)
    _EXPANDED_LIST_COLUMNS.add(key)
    return {"changed": sorted(changed), "reason": "ellipsis detected" if clipped else "none"}


def find_row(ui, list_id, needle, cfg=None):
    """OCR로 `needle`(예: 환자 ID의 앞부분)이 들어간 행을 찾는다."""
    want = str(needle or "").upper().replace(" ", "")
    for row in list_rows(ui, list_id):
        text = row_cell_text(ui, row, cfg).upper().replace(" ", "")
        if want and want[:12] in text:
            return row, text
    return None, ""


def start_study(ui, cfg, timeout=40, evidence_dir=None, map_procedure_name=None):
    """선택한 Scheduled 행의 Study를 등록하고 Exposure Mode로 전환한다.

    사양서1 p.37~38 `VP-460`. 맵핑되지 않은 Procedure Code가 있으면 확인 팝업이
    먼저 뜨고, 자동화는 **매핑하지 않는 쪽**을 택한다(docstring 참고).

    반환: {"clicked": bool, "dialogs": [...], "state": 촬영 상태, "ready": bool}
    """
    info = {"clicked": False, "dialogs": [], "state": "", "ready": False,
            "mapping": None}
    hits = by_id(ui, SCHEDULED_START)
    if not hits:
        raise WorkflowError("Start 버튼(%d)을 찾지 못했습니다. Scheduled 탭인지 "
                            "확인하십시오." % SCHEDULED_START)
    ui.click(hits[0], settle=3.0)
    info["clicked"] = True

    end = time.time() + timeout
    while time.time() < end:
        d = ui.dialog()
        if d is None:
            break
        title = (d.text or "").strip()
        info["dialogs"].append(title or "(제목 없음)")
        handled = _handle_start_dialog(ui, d, evidence_dir, len(info["dialogs"]),
                                       cfg=cfg, info=info,
                                       map_procedure_name=map_procedure_name)
        if not handled:
            break
        time.sleep(1.2)

    info["state"] = acquisition_state(ui, cfg)
    info["ready"] = "ready" in info["state"].lower()
    return info


def _handle_start_dialog(ui, dlg, evidence_dir, index, cfg=None, info=None,
                         map_procedure_name=None):
    """Start 후 뜨는 대화상자를 사양대로 처리한다."""
    from .ui import children
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        try:
            ui.capture_dialog(dlg, os.path.join(evidence_dir,
                                                "start_dlg_%d.png" % index))
        except Exception:                                # noqa: BLE001
            pass

    kids = list(children(dlg.hwnd, 3))
    # 1) Procedure Mapping 창: 제목줄 닫기(-4)로 닫는다 — 매핑하지 않는다.
    closer = [c for c in kids if c.ctrl_id == DIALOG_CLOSE_X]
    is_mapping = any(c.ctrl_id in (PROCMAP_OK, PROCMAP_MAPPING, PROCMAP_NEW,
                                   PROCMAP_COPY_FROM) for c in kids)
    if is_mapping:
        if map_procedure_name:
            result = map_procedure(ui, cfg or {}, map_procedure_name, evidence_dir)
            if info is not None:
                info["mapping"] = result
            if result.get("mapped"):
                return True
            # 매핑에 실패하면 설정을 어정쩡하게 남기지 않고 창을 닫는다.
        if closer:
            ui.click(closer[0], settle=1.5)
            return True

    # 2) Yes/No/Cancel Info 팝업: "No"(매핑하지 않고 Exposure Mode로 전환).
    #    버튼 라벨을 표준 API로 못 읽으므로 가로 위치로 가운데(=No)를 고른다.
    buttons = sorted([c for c in kids
                      if c.text.strip() in ("TextButton", "Button")
                      and c.size[0] >= 40 and c.size[1] >= 18],
                     key=lambda c: c.rect[0])
    if len(buttons) == 3:
        ui.click(buttons[1], settle=1.5)                 # 가운데 = No
        return True
    if buttons:
        ui.dismiss_dialog(timeout=2)
        return True
    return False


# Procedure Mapping 자동화 활성화 플래그.
# 2026-08-19 실측 사고로 기본 False — `map_procedure()` docstring 참고.
ENABLE_PROCEDURE_MAPPING = False

# Procedure Mapping 창 (실측 2026-08-19)
PROCMAP_SEARCH_EDIT = 30143
PROCMAP_PROC_LIST = 31107
PROCMAP_NEW = 30646
PROCMAP_COPY_FROM = 30648
PROCMAP_MAPPING = 30647
PROCMAP_OK = 30642

# Print 화면 (실측 2026-08-19 — 캡처로 라벨 확인)
PRINT_BUTTON = 30718            # "Print"
PRINT_AND_CLOSE_BUTTON = 30719  # "Print & Close"


def map_procedure(ui, cfg, procedure_name=None, evidence_dir=None):
    """Procedure Mapping 창에서 MWL Procedure Code를 기존 Procedure에 매핑한다.

    **제품 설정을 바꾸는 조작이다** — 기본으로 수행하지 않고, 호출부가 명시적으로
    선택할 때만 쓴다(`run.py tc02 --map-procedure` 등).

    ## 왜 필요한가 (실측으로 확인한 연쇄 영향, 2026-08-19)

    매핑을 생략하면(사양서1 p.38의 "No") Study는 등록되고 촬영도 되지만 **Step이
    등록되지 않는다.** 그 결과 셋이 따라온다.

    1. 영상처리 파라미터가 지정되지 않아 촬영 직후
       `Error: Image process parameter file does not exist.`가 뜬다.
    2. 검사가 완료 처리되지 않아(`STUDY.StudyStatus=1`) **Database 목록에 나타나지
       않는다** — Operation Manual 3.6(p.41)은 Database가 "완료된 검사"를 조회하는
       화면이라고 명시한다.
    3. Database에서 스터디를 고를 수 없으므로 Print(30293)·Export(30300) 대상을
       지정할 수 없다 — TC07/TC08이 여기서 막힌다.

    즉 TC04/05/07/08의 정상 흐름을 검증하려면 매핑이 전제다.

    ## 창 구조 (실측)

    ```
    Procedure Mapping            (제목줄 닫기 = ctrl_id -4)
      Code List      : 매핑되지 않은 Procedure Code (예: RP_VX_AU… / CHEST PA)
      Procedure      : Search Edit 30143 + 목록 31107 (Name / Code)
      Step List      : 선택한 Procedure의 Step
      [New 30646] [Copy From 30648] [Mapping 30647]        [OK 30642]
    ```

    사양서1 p.38 원문: *"Mapping 버튼을 클릭하여 이미 존재하는 Procedure에
    매핑한다. Mapping 후 Procedure 목록을 갱신한다. 이미 매핑 되어 있으면 아래의
    메시지가 발생한다. Yes: overwrite No: 취소 … Ok 버튼 클릭 시 환자 등록을
    진행하고 매핑 되어 있는 Procedure의 Step을 등록한다."*

    즉 **Mapping → OK** 순서를 지켜야 Step까지 등록된다.

    ## 지금은 비활성화되어 있다 (실측 사고, 2026-08-19)

    이 함수를 라이브로 처음 돌렸을 때 **Mapping(30647)이 아니라 New(30646) 경로가
    타졌다.** 그 결과 "New Procedure" 창이 열리고 Add가 눌려
    `TB_PROCEDURE`에 새 Procedure가 만들어졌다.

    ```
    ProcedureKey=267  Name='Inserted:RP_VX_AUTO_001'
    Code='RP_VX_AUTO_001'  Description='CHEST PA'   (PROCSTEP에 Step 없음)
    ```

    제품 설정을 오염시키는 동작이므로 **원인을 확정하기 전에는 실행하지 않는다.**
    `ENABLE_PROCEDURE_MAPPING = False`인 동안 이 함수는 아무것도 누르지 않고
    "왜 하지 않았는지"만 돌려준다.

    다시 켜기 전에 확인할 것:

    1. 검색 Edit(30143)에 입력한 뒤 목록(31107)이 실제로 좁혀지는지 — 좁혀지지
       않으면 첫 행이 기대한 Procedure가 아니다.
    2. `children()`으로 잡은 버튼 hwnd가 검색·클릭 뒤에도 유효한지(창 내용이
       바뀌면 stale이 된다) — 매번 다시 열거해야 한다.
    3. Mapping(30647)과 New(30646)의 rect를 클릭 직전에 다시 읽어 대조.
    4. 정리 방법: 267번 Procedure는 `python run.py run-regression
       --reset-baseline`으로 DB를 클린 시점으로 되돌리면 사라진다. DB에서 직접
       DELETE 하지 않는다(이 저장소는 DB 조회 전용이 원칙이다).

    반환: {"mapped": bool, "procedure": 검색어, "dialogs": [...], "note": ...}
    """
    from .ui import children

    want = procedure_name or ((cfg.get("test_data") or {}).get("procedure_name")
                              or "Chest PA")
    out = {"mapped": False, "procedure": want, "dialogs": [], "note": ""}

    if not ENABLE_PROCEDURE_MAPPING:
        out["note"] = (
            "Procedure Mapping 자동화는 현재 비활성화되어 있다(ENABLE_PROCEDURE_"
            "MAPPING=False). 2026-08-19 실측에서 이 함수가 Mapping이 아니라 New "
            "경로를 타 TB_PROCEDURE에 'Inserted:RP_VX_AUTO_001'(ProcedureKey=267, "
            "Step 없음)을 만들어 제품 설정을 오염시켰다. 버튼 지목을 실측으로 다시 "
            "확정하기 전에는 실행하지 않는다 — 자세한 내용은 이 함수의 docstring "
            "참고. 매핑이 필요한 TC(04/05/07/08의 완전 흐름)는 사람이 화면에서 "
            "매핑한 뒤 실행할 것.")
        return out

    dlg = ui.dialog()
    if dlg is None:
        out["note"] = "Procedure Mapping 창이 열려 있지 않다."
        return out
    kids = list(children(dlg.hwnd, 3))
    if not any(c.ctrl_id == PROCMAP_MAPPING for c in kids):
        out["note"] = ("떠 있는 대화상자가 Procedure Mapping 창이 아니다"
                       "(Mapping 버튼 %d 없음)." % PROCMAP_MAPPING)
        return out

    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        try:
            ui.capture_dialog(dlg, os.path.join(evidence_dir, "procmap_before.png"))
        except Exception:                                # noqa: BLE001
            pass

    # 1) Procedure 이름으로 검색해 목록을 좁힌다.
    search = [c for c in kids if c.ctrl_id == PROCMAP_SEARCH_EDIT and c.cls == "Edit"]
    if search:
        ui.type_text(search[0], want, clear=True, settle=1.2)
        time.sleep(1.0)

    # 2) 목록 첫 행을 선택한다. 검색으로 좁혔으므로 첫 행이 대상이다.
    #    (좁히지 못했으면 아래에서 이름을 OCR로 확인한다.)
    rows = []
    for lc in [c for c in children(dlg.hwnd, 4) if c.ctrl_id == PROCMAP_PROC_LIST]:
        rows = sorted([k for k in children(lc.hwnd, 2)
                       if k.text.strip() == "ListItem" and k.visible],
                      key=lambda k: k.rect[1])
    if not rows:
        out["note"] = "Procedure 목록(%d)에서 행을 찾지 못했다." % PROCMAP_PROC_LIST
        return out
    picked = rows[0]
    picked_text = row_cell_text(ui, picked, cfg)
    click_row(ui, picked)
    time.sleep(0.8)

    if want.replace(" ", "").upper() not in picked_text.replace(" ", "").upper():
        out["note"] = ("검색 결과 첫 행이 기대한 Procedure가 아니다"
                       "(검색=%r / 첫 행 OCR=%r). 매핑하지 않고 중단한다 — 엉뚱한 "
                       "Procedure에 매핑하면 되돌리기 어렵다." % (want, picked_text))
        return out

    # 3) Mapping -> 확인 팝업(overwrite Yes/No) 처리
    btn = [c for c in kids if c.ctrl_id == PROCMAP_MAPPING]
    ui.click(btn[0], settle=1.8)
    for _ in range(3):
        d2 = ui.dialog()
        if d2 is None or d2.hwnd == dlg.hwnd:
            break
        msg = dialog_message(ui, d2, cfg)
        out["dialogs"].append(msg or "(문구 미노출)")
        # 사양서1 p.38: "이미 매핑 되어 있으면 … Yes: overwrite / No: 취소"
        # 시험 처방의 코드이므로 overwrite(Yes = 첫 버튼)를 택한다.
        sub = sorted([c for c in children(d2.hwnd, 3)
                      if c.text.strip() in ("TextButton", "Button")
                      and c.size[0] >= 40], key=lambda c: c.rect[0])
        if sub:
            ui.click(sub[0], settle=1.5)
        else:
            ui.dismiss_dialog(timeout=2)
        time.sleep(0.8)

    # 4) OK -> 환자 등록 + 매핑된 Procedure의 Step 등록
    ok = [c for c in children(dlg.hwnd, 3) if c.ctrl_id == PROCMAP_OK]
    if ok:
        ui.click(ok[0], settle=2.5)
        out["mapped"] = True
    else:
        out["note"] = "OK 버튼(%d)을 찾지 못했다." % PROCMAP_OK

    out["dialogs"] += pending_dialogs(ui, evidence_dir=evidence_dir, cfg=cfg)
    out["note"] += " 매핑 대상 Procedure: %r" % picked_text
    return out


def open_mwl_study(ui, cfg, patient_id=None, evidence_dir=None,
                   map_procedure_name=None):
    """MWL 조회 → 대상 처방 선택 → Study 등록까지 한 번에 수행한다.

    patient_id를 주면 그 처방을 OCR로 찾아 선택한다(없으면 첫 행).
    반환: {"summary","row_text","start","rows"}
    """
    summary, rows = query_mwl(ui, cfg)
    if not rows:
        raise WorkflowError("MWL 조회 결과가 없습니다(요약: %r). "
                            "`python run.py mwl-ensure`로 처방을 먼저 보장하십시오."
                            % summary)
    row, row_text = (None, "")
    if patient_id:
        row, row_text = find_row(ui, REG_RESULT_LIST, patient_id, cfg)
        # Patient ID 열은 폭이 좁아 `VXVUE_MWL...`처럼 줄임표로 표시된다.
        # 그 경우 전체 ID 비교는 구조적으로 실패하므로, 같은 시험 처방의
        # Accession Number(화면에 온전히 노출됨)를 보조 키로 사용한다.
        accession = (cfg.get("test_data") or {}).get("mwl_accession")
        if row is None and accession:
            row, row_text = find_row(ui, REG_RESULT_LIST, accession, cfg)
        if row is None:
            raise WorkflowError(
                "요청한 MWL 환자 ID %r(보조 Accession=%r)을 목록에서 찾지 "
                "못했습니다. 다른 환자의 "
                "첫 행으로 대체하지 않습니다. `python run.py mwl-ensure`로 시험 "
                "처방을 보장한 뒤 다시 실행하십시오." % (patient_id, accession))
    if row is None:
        row = rows[0]
        row_text = row_cell_text(ui, row, cfg)
    click_row(ui, row)
    start = start_study(ui, cfg, evidence_dir=evidence_dir,
                        map_procedure_name=map_procedure_name)
    return {"summary": summary, "row_text": row_text, "start": start,
            "rows": len(rows)}


# --- Exposure 인체도 — Projection / Step 선택 --------------------------
#
# ## 용어 (사용자 정정, 2026-08-20)
#
#   General          카테고리. 상단 띠에 표시되고 좌우 화살표로 바꾼다.
#                    **사용자 기준은 항상 General**이므로 다르면 되돌린다.
#   Chest, Skull ... **Projection**. 인체도 위에 그려진 라벨(파란 점이 클릭 지점).
#   PA, AP, LAT      **Step**. Projection을 고르면 우측에 네모 박스로 나타난다.
#
# 사용자 원문: "chest가 projection이고 옆에 네모 박스로 뜨는 PA AP LAT 가 step이야."
#
# DB는 이 둘을 나눠 저장한다 — `STEP` 테이블의 `BodypartCodeKey`(Chest 쪽)와
# `ProjectionCodeKey`(PA 쪽). **DB 컬럼명과 화면 용어가 엇갈리므로** 이 모듈은
# 화면·사용자 용어를 따르고, DB를 조회할 때만 컬럼명을 그대로 쓴다.
# 실측 2026-08-20. `CUIBodypartDlg`(#32770) 안에 다음이 있다.
#   30398  ◀ 카테고리 이전      30399  ▶ 카테고리 다음
#   27000  Projection 버튼 1    27001  Projection 버튼 2
#   30838/30839  하단 좌우 이동(Projection 페이지)
# 카테고리 이름("General")은 상단 띠에 그려지고 **OCR로 읽힌다.**
BODYPART_DLG_TEXT = "CUIBodypartDlg"
CATEGORY_PREV_BUTTON = 30398
CATEGORY_NEXT_BUTTON = 30399
STEP_BUTTON_IDS = (27000, 27001, 27002, 27003)
STEP_PAGE_PREV = 30838
STEP_PAGE_NEXT = 30839

# 사용자 지시(2026-08-20): "나는 제너럴이 기준이야."
DEFAULT_CATEGORY = "General"

# General 카테고리의 부위 목록(실측 2026-08-20, 화면 세로 순서).
# **OCR 결과를 이 목록과 대조**해 오인식을 걸러낸다 — 목록에 없는 문자열은
# 부위로 취급하지 않는다.
GENERAL_PROJECTIONS = (
    "Full-body", "Skull", "C-spine", "Shoulder", "Chest", "Humerus",
    "Full-spine", "T-spine", "Elbow", "Forearm", "L-spine", "Abdomen",
    "Wrist", "Hand", "Pelvis", "Hip", "Femur", "Knee", "Long-bone",
    "Tibia", "Ankle", "Foot",
)

# 라벨 판독 임계값. 부위 라벨은 **밝은 뼈 그림 위에 흰 글자**로 겹쳐 그려져
# 있어 그냥 OCR하면 절반도 못 읽는다(실측: 22개 중 10개). 흰 글자만 남기는
# 이진화를 거치면 21개까지 읽힌다 — 임계값별 실측:
#   200 -> 10/22   215 -> 8/22   230 -> 19/22   **245 -> 21/22**
_LABEL_THRESHOLD = 245
_LABEL_SCALE = 3

# 선택된(파란) 라벨을 잡는 기준: B 채널이 R 채널보다 이만큼 크면 파란 글자.
_BLUE_MARGIN = 60

# 라벨 왼쪽의 파란 점이 실제 클릭 지점이다(실측: 라벨 왼쪽 끝에서 약 9px).
_DOT_OFFSET = 9


def _norm_label(text):
    import re as _re
    return _re.sub(r"[^a-z]", "", str(text or "").lower())


def bodypart_dialog(ui):
    """`CUIBodypartDlg` 컨트롤. Exposure 화면이 아니면 None.

    **전체 컨트롤 트리를 열거하지 않는다** — 크로스 프로세스 조회가 수백 번
    발생해 한 번에 수 분이 걸린다(실측: `ui.controls(max_depth=8)`가 7분
    타임아웃). 메인 창의 얕은 자식만 본다.
    """
    from .ui import children
    main = ui.main_window()
    if main is None:
        return None
    for c in children(main.hwnd, 3):
        if (c.cls == "#32770" and c.text.strip() == BODYPART_DLG_TEXT
                and c.visible and c.size[0] > 200):
            return c
    return None


def _tess(cfg):
    try:
        import pytesseract
    except ImportError:
        return None
    exe = ((cfg or {}).get("xipl") or {}).get("tesseract_exe") \
        or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
    return pytesseract


def category_name(ui, cfg=None):
    """지금 선택된 부위 카테고리 이름(예: `"General"`). 못 읽으면 빈 문자열.

    카테고리 제목은 좌우 화살표 사이 상단 띠에 그려진다 — 컨트롤이 아니라
    그림이므로 OCR로 읽는다.
    """
    from PIL import ImageGrab
    tess = _tess(cfg)
    dlg = bodypart_dialog(ui)
    if dlg is None or tess is None:
        return ""
    l, t, r, _b = dlg.rect
    # 화살표(좌 55px, 우 55px) 사이 띠만 잡는다.
    band = (l + 70, t + 2, r - 180, t + 58)
    img = ImageGrab.grab(bbox=band, all_screens=True)
    img = img.resize((img.width * 3, img.height * 3))
    return " ".join(tess.image_to_string(img, config="--psm 7").split())


def ensure_category(ui, cfg=None, want=DEFAULT_CATEGORY, max_steps=8):
    """부위 카테고리를 `want`로 맞춘다(기본 `General`).

    사용자 지시(2026-08-20): **"나는 제너럴이 기준이야"** — 다른 카테고리가
    선택돼 있으면 상단 화살표로 이동한다. 한 방향으로만 돌면 목록 끝에서 멈출
    수 있으므로, 절반은 오른쪽(▶) 절반은 왼쪽(◀)으로 시도한다.

    반환: {"ok": bool, "category": 최종 카테고리, "steps": 누른 횟수,
           "seen": 지나온 카테고리 목록}
    """
    want_n = _norm_label(want)
    seen = []
    now = category_name(ui, cfg)
    seen.append(now)
    if want_n and want_n in _norm_label(now):
        return {"ok": True, "category": now, "steps": 0, "seen": seen}

    dlg = bodypart_dialog(ui)
    if dlg is None:
        return {"ok": False, "category": now, "steps": 0, "seen": seen}

    from .ui import children
    kids = list(children(dlg.hwnd, 2))
    nxt = next((c for c in kids if c.ctrl_id == CATEGORY_NEXT_BUTTON), None)
    prv = next((c for c in kids if c.ctrl_id == CATEGORY_PREV_BUTTON), None)

    for i in range(max_steps):
        btn = nxt if i < max_steps // 2 else prv
        if btn is None:
            break
        ui.click(btn, settle=1.0)
        now = category_name(ui, cfg)
        seen.append(now)
        if want_n and want_n in _norm_label(now):
            return {"ok": True, "category": now, "steps": i + 1, "seen": seen}
    return {"ok": False, "category": now, "steps": max_steps, "seen": seen}


def _label_mask(rgb):
    """부위 라벨만 남긴 이진 이미지(글자=검정, 배경=흰색)를 만든다.

    두 가지를 함께 잡아야 한다.

    1. **선택되지 않은 라벨은 흰 글자**다. 밝은 뼈 그림 위에 겹쳐 있어 그냥
       OCR하면 22개 중 10개만 읽힌다. 명도가 임계값을 넘는 픽셀만 남기면
       21개까지 읽힌다(실측: 200→10, 215→8, 230→19, 245→21).
    2. **선택된 라벨은 파란 글자**다(실측 2026-08-20: Chest를 고르자 파랗게
       바뀌었다). 파란색은 명도가 흰색보다 낮아 1번 기준에서 빠지고, 그래서
       "이미 선택된 항목을 다시 찾지 못하는" 증상이 났다. 파란 글자는
       **B 채널이 R 채널보다 크게 높다**는 특징으로 따로 잡는다.

    두 마스크를 합치면 선택 여부와 무관하게 모든 라벨을 읽는다.
    """
    from PIL import ImageChops
    r, g, b = rgb.convert("RGB").split()
    value = rgb.convert("HSV").split()[2]
    white = value.point(lambda v: 255 if v > _LABEL_THRESHOLD else 0)
    blue = ImageChops.subtract(b, r).point(
        lambda v: 255 if v > _BLUE_MARGIN else 0)
    both = ImageChops.lighter(white, blue)
    # OCR은 검은 글자/흰 배경을 잘 읽는다.
    return both.point(lambda v: 0 if v else 255)


# `projection_positions()`가 마지막 판독에서 남긴 설명(소거로 정한 항목 등).
# 호출부가 판정 note에 그대로 실어 **어떻게 정했는지 리포트에 남긴다.**
last_positions_note = ""

# 마지막 판독에서 **선택된 상태(파란 글자)**로 확인된 Projection 이름.
last_selected_projection = None

# 파란 점 검출 기준(실측 2026-08-20). 라벨마다 왼쪽에 작은 파란 점이 있고
# 그것이 클릭 지점이다. 점은 배경(어두운 회색)이든 뼈 그림(밝은 회색)이든
# **B가 R보다 확실히 크다** — 글자와 달리 배경 밝기에 흔들리지 않는다.
_DOT_BR_MARGIN = 45       # B - R 이 이보다 크면 파란 픽셀
_DOT_MIN_BLUE = 90        # 그리고 B 자체가 이만큼은 밝아야 한다
_DOT_AREA = (20, 120)     # 점 하나의 픽셀 수
_DOT_SIDE = (4, 14)       # 점의 가로·세로 길이
_DOT_FILL = 0.55          # 외접 사각형 대비 채움률(동그란지)
_DOT_GAP = 3              # 이 거리 안의 파란 픽셀은 같은 점으로 묶는다
_LABEL_STRIP = (5, 150, 13)   # 점 기준 글자 영역: 오른쪽 5~150px, 위아래 13px
_LABEL_K = (0.6, 1.0, 1.4)    # 국소 임계값 계수(평균 + k*표준편차)
_LABEL_MATCH_MIN = 0.72       # 정답지와의 최소 유사도
_BLUE_TEXT_MARGIN = 45        # 선택된 라벨(파란 글자) 판별: B - R


def _park_cursor(ui, dlg, settle=0.25):
    """커서를 인체도 밖으로 옮긴다. 호버 강조를 지우기 위한 것이다.

    라벨은 커서가 얹히면 색이 바뀌므로(사용자 확인 2026-08-20) 그 상태로
    캡처하면 그 라벨 하나만 다른 색으로 읽힌다. 옮길 곳은 인체도 오른쪽 바깥
    — 클릭하지 않으므로 그곳의 컨트롤 상태를 바꾸지 않는다.
    """
    l, t, r, b = dlg.rect
    try:
        ui.move_cursor((r + 40, t + 8))
    except AttributeError:
        from .ui import u32
        u32.SetCursorPos(int(r + 40), int(t + 8))
    time.sleep(settle)


def _blue_dots(img):
    """인체도 캡처에서 라벨 왼쪽 파란 점의 중심 좌표를 찾는다(이미지 좌표).

    글자를 읽기 전에 **점을 먼저 찾는 것**이 핵심이다. 글자는 색과 배경에 따라
    읽히기도 하고 안 읽히기도 하지만(아래 `projection_positions` docstring
    참고), 점은 항상 같은 파란색이므로 배경·선택 상태와 무관하게 잡힌다 —
    실측: 22개 라벨에 점 22개 정확히 검출.

    점들은 서로 충분히 떨어져 있어(가장 가까운 쌍도 20px 이상) 파란 픽셀을
    가까운 것끼리 묶는 것만으로 나뉜다. 픽셀을 하나씩 훑는 연결 성분 탐색은
    같은 결과에 76초가 걸렸다(실측) — numpy로 좌표만 뽑아 묶는다.
    """
    import numpy as np
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    red, _green, blue = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    ys, xs = np.where((blue - red > _DOT_BR_MARGIN) & (blue > _DOT_MIN_BLUE))
    if len(xs) == 0:
        return []

    # 가까운 픽셀끼리 묶는다. 비교 기준은 그 묶음의 **외접 사각형**이다 —
    # 마지막에 넣은 픽셀만 보면 한 점이 여러 조각으로 쪼개진다(행 단위로 훑기
    # 때문에 다음 행의 첫 픽셀이 이전 행 마지막 픽셀에서 멀다).
    clusters = []
    for x, y in sorted(zip(xs.tolist(), ys.tolist()), key=lambda p: (p[1], p[0])):
        for c in clusters:
            if (c["l"] - _DOT_GAP <= x <= c["r"] + _DOT_GAP
                    and c["t"] - _DOT_GAP <= y <= c["b"] + _DOT_GAP):
                c["xs"].append(x)
                c["ys"].append(y)
                c["l"], c["r"] = min(c["l"], x), max(c["r"], x)
                c["t"], c["b"] = min(c["t"], y), max(c["b"], y)
                break
        else:
            clusters.append({"xs": [x], "ys": [y],
                             "l": x, "r": x, "t": y, "b": y})

    dots = []
    for c in clusters:
        w = max(c["xs"]) - min(c["xs"]) + 1
        h = max(c["ys"]) - min(c["ys"]) + 1
        n = len(c["xs"])
        if not _DOT_AREA[0] <= n <= _DOT_AREA[1]:
            continue
        if not (_DOT_SIDE[0] <= w <= _DOT_SIDE[1]
                and _DOT_SIDE[0] <= h <= _DOT_SIDE[1]):
            continue
        if abs(w - h) > 4 or n / float(w * h) < _DOT_FILL:
            continue                           # 점이 아니라 파란 계열 그림
        dots.append((int(sum(c["xs"]) / n), int(sum(c["ys"]) / n)))
    return sorted(dots, key=lambda d: (d[1], d[0]))


def _label_masks(tile):
    """글자 조각을 여러 방식으로 이진화해 후보 이미지들을 돌려준다.

    **글자색을 가정하지 않는다**(사용자 지적, 2026-08-20: *"Chest가 아니라 다른
    라벨이 글자색이 다를 수도 있는데 이런 것도 예외처리가 되는 거야?"*).
    이 화면의 라벨은 최소 세 가지로 나타난다.

    - 어두운 배경 위 **흰 글자** → 배경보다 밝다
    - 밝은 뼈 그림 위 **흰 글자** → 밝기 차가 작다(국소 대비가 필요하다)
    - **선택된 라벨은 파란 글자** → 배경보다 밝지 않을 수 있다

    그래서 "밝은 쪽"만 보지 않고 **밝은 쪽 / 파란 쪽 / 어두운 쪽**을 모두
    시도한다. 어느 것이 맞는지는 읽어 보고 정답지와의 유사도로 판단한다 —
    색을 미리 정해 두면 그 가정이 깨지는 순간 라벨을 통째로 놓친다.
    """
    import numpy as np
    from PIL import Image
    rgb = np.asarray(tile.convert("RGB")).astype(np.float32)
    gray = np.asarray(tile.convert("L")).astype(np.float32)
    out = []
    for k in _LABEL_K:                                    # 밝은 글자
        out.append(gray > (gray.mean() + k * gray.std()))
    blue_diff = rgb[:, :, 2] - rgb[:, :, 0]               # 파란 글자
    if blue_diff.std() > 3:
        out.append(blue_diff > (blue_diff.mean() + 1.0 * blue_diff.std()))
    out.append(gray < (gray.mean() - 1.0 * gray.std()))   # 어두운 글자
    imgs = []
    for mask in out:
        if mask.sum() < 10 or mask.sum() > mask.size * 0.6:
            continue
        imgs.append(Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)))
    return imgs


def _read_label(img, dot, tess, candidates):
    """점 오른쪽 글자를 읽어 정답지에서 가장 비슷한 이름을 고른다.

    반환: (이름 또는 None, 유사도, 원문 OCR)

    이진화는 `_label_masks()`가 만든 후보 전부를 시도하고, 정답지와 가장
    비슷하게 읽힌 결과를 택한다. **글자색을 가정하지 않기 위한 것이다.**
    """
    import difflib
    cx, cy = dot
    right, span, half = _LABEL_STRIP
    tile = img.crop((min(img.width, cx + right), max(0, cy - half),
                     min(img.width, cx + span), min(img.height, cy + half)))
    if tile.width < 8 or tile.height < 6:
        return None, 0.0, ""
    best = (None, 0.0, "")
    for binary in _label_masks(tile):
        big = binary.resize((binary.width * 4, binary.height * 4))
        text = " ".join(tess.image_to_string(big, config="--psm 7").split())
        norm = _norm_label(text)
        if len(norm) < 3:
            continue
        for name in candidates:
            ratio = difflib.SequenceMatcher(None, norm, _norm_label(name)).ratio()
            if ratio > best[1]:
                best = (name, ratio, text)
        if best[1] >= 0.95:                    # 충분히 확실하면 더 시도하지 않는다
            break
    return best


def _blue_text_labels(img, tess, candidates):
    """**파란 글자**로 그려진 라벨을 찾는다(= 지금 선택된 Projection).

    실측(2026-08-20): Projection을 선택하면 그 라벨만 표시가 바뀐다.

    | | 선택 안 됨 | 선택됨 |
    |---|---|---|
    | 점 | 파란 점 | **흰 점** |
    | 글자 | 흰 글자 | **파란 글자** |

    그래서 `_blue_dots()`는 선택된 항목을 놓친다 — 점이 파랗지 않다. 대신
    **글자가 파랗다**는 것을 이용해 찾는다. 선택은 한 번에 하나뿐이므로
    (호버 색 변화와 달리 선택은 배타적이다) 이 경로로 찾을 라벨도 하나다.

    반환: {이름: (이미지 x, 이미지 y)} — 좌표는 라벨 왼쪽 점 위치로 환산한 값.
    """
    import difflib
    import numpy as np
    from PIL import Image
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    red, _green, blue = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mask = (blue - red > _BLUE_TEXT_MARGIN)
    if mask.sum() < 30:
        return {}
    binary = Image.fromarray(np.where(mask, 0, 255).astype(np.uint8))
    big = binary.resize((binary.width * _LABEL_SCALE, binary.height * _LABEL_SCALE))
    data = tess.image_to_data(big, output_type=tess.Output.DICT)
    out = {}
    for i, raw in enumerate(data["text"]):
        norm = _norm_label(raw)
        if len(norm) < 3:
            continue
        best, ratio = None, 0.0
        for name in candidates:
            score = difflib.SequenceMatcher(None, norm, _norm_label(name)).ratio()
            if score > ratio:
                best, ratio = name, score
        if best is None or ratio < _LABEL_MATCH_MIN or best in out:
            continue
        left = data["left"][i] // _LABEL_SCALE
        cy = (data["top"][i] + data["height"][i] // 2) // _LABEL_SCALE
        out[best] = (max(0, left - _DOT_OFFSET), cy)
    return out


def projection_positions(ui, cfg=None, known=GENERAL_PROJECTIONS):
    """인체도의 Projection 라벨과 **클릭 지점**을 돌려준다.

    반환: {"Chest": (x, y), ...}  — (x, y)는 라벨 왼쪽 파란 점의 화면 좌표.

    ## 왜 OCR인가

    Projection 라벨은 컨트롤이 아니라 **인체도 그림 위에 그려진 텍스트**다.
    표준 Win32 API로 읽을 수 없어 `CLAUDE.md` 3절의 2순위(속성으로 못 찾을 때만
    위치)에 해당한다. 다만 **좌표를 코드에 박지 않는다** — 실행 시점에
    `CUIBodypartDlg`의 실제 rect를 기준으로 캡처하고, 찾아낸 위치에서 클릭
    지점을 계산한다.

    ## 전역 임계값이 왜 실패했나 (실측 2026-08-20)

    처음에는 "밝기 > 245인 픽셀만 글자"로 이진화했다. 그러면 **어두운 배경 위
    라벨만 읽히고 밝은 뼈 그림 위 라벨은 통째로 놓친다** — 글자와 배경의 밝기가
    비슷해 임계값으로 갈라지지 않는다. 실제로 회귀에서 22개 중 13개만 읽혔고
    `Chest`가 그중에 없어서(갈비뼈 위에 있다) TC04/05/07/08이 **Step 등록
    실패로 연쇄 FAIL**했다. 앞선 실행에서는 우연히 통과했는데, 그때는 Chest가
    선택된 상태(파란 글자)여서 다른 마스크에 걸렸던 것이다.

    ## 지금 방식 — 점을 먼저 찾고, 정답지로 소거한다

    1. **파란 점을 찾는다.** 점은 색으로 구분되므로 배경 밝기와 무관하다
       (실측: 22개 라벨에 점 22개 정확히 검출).
    2. 점마다 오른쪽 글자를 **국소 대비**로 이진화해 읽고, 정답지와 유사도
       (difflib)로 대조한다 — 실측 21/22.
    3. **남은 것이 하나씩이면 그 둘을 잇는다.** 라벨 후보 목록이 완전하고
       (`GENERAL_PROJECTIONS`, 실측), 점 개수가 라벨 개수와 같으므로, 21개를
       확정하면 남은 라벨 1개와 남은 점 1개는 **추측이 아니라 결정된다.**
       소거로 정한 항목은 반환값과 별도로 `last_positions_note`에 남긴다.

    소거는 개수가 정확히 일치할 때만 한다. 하나라도 어긋나면 그 항목은 버린다 —
    잘못 이어 붙이면 엉뚱한 부위를 촬영하게 되고, 그것은 판독 실패보다 나쁘다.
    """
    from PIL import ImageGrab
    global last_positions_note
    last_positions_note = ""
    tess = _tess(cfg)
    dlg = bodypart_dialog(ui)
    if dlg is None or tess is None:
        return {}
    l, t, r_edge, b = dlg.rect
    # **캡처 전에 마우스를 인체도 밖으로 치운다.** 사용자 확인(2026-08-20):
    # *"마우스를 가까이했을 때 색깔이 바뀌는 거라 2개 이상이 색깔이 달라질 일이
    # 없어."* 즉 색이 다른 라벨은 **커서가 얹힌 것 하나뿐**이다. 커서를 치우면
    # 22개가 모두 같은 색으로 그려지므로 판독이 안정된다(실측: 커서가 Chest에
    # 얹힌 상태에서 21/22, 치우면 22/22).
    _park_cursor(ui, dlg)
    # 인체도 영역: 카테고리 띠(상단 55px) 아래, Projection 버튼(우측) 왼쪽.
    box = (l, t + 55, l + 590, b - 10)
    img = ImageGrab.grab(bbox=box, all_screens=True)

    dots = _blue_dots(img)
    remaining = list(known)
    out, matched_dots = {}, set()
    for dot in dots:
        name, ratio, _text = _read_label(img, dot, tess, remaining)
        if name is None or ratio < _LABEL_MATCH_MIN:
            continue
        out[name] = (box[0] + dot[0], box[1] + dot[1])
        matched_dots.add(dot)
        remaining.remove(name)

    # 점으로 못 찾은 라벨이 있으면 **선택된 항목일 수 있다** — 그 경우 점이
    # 흰색이라 위 경로에 걸리지 않는다. 파란 글자로 다시 찾는다.
    global last_selected_projection
    last_selected_projection = None
    notes = []
    if remaining:
        picked = _blue_text_labels(img, tess, remaining)
        for name, (dx, dy) in picked.items():
            out[name] = (box[0] + dx, box[1] + dy)
            remaining.remove(name)
            last_selected_projection = name
        if picked:
            notes.append("%s 는 **선택된 상태(파란 글자)**로 찾았다"
                         % ", ".join(sorted(picked)))

    spare = [d for d in dots if d not in matched_dots]
    if len(remaining) == 1 and len(spare) == 1:
        name = remaining[0]
        out[name] = (box[0] + spare[0][0], box[1] + spare[0][1])
        notes.append("%s 는 글자를 읽지 못해 **소거로 확정**했다(라벨 %d개 중 "
                     "%d개를 읽고, 남은 라벨 1개와 남은 점 1개가 일대일로 "
                     "결정됨). 커서가 얹힌 라벨은 색이 바뀌는데 그것은 한 번에 "
                     "하나뿐이므로(사용자 확인) 이 소거는 안전하다."
                     % (name, len(known), len(known) - 1))
    elif remaining and spare:
        notes.append("읽지 못한 라벨 %d개(%s), 이름을 붙이지 못한 점 %d개. "
                     "개수가 일대일이 아니라 소거하지 않았다 — 잘못 이어 붙이면 "
                     "엉뚱한 부위를 촬영한다."
                     % (len(remaining), ", ".join(remaining), len(spare)))
    elif remaining:
        notes.append("읽지 못한 라벨 %d개(%s). 대응할 점이 없어 소거하지 않았다."
                     % (len(remaining), ", ".join(remaining)))
    last_positions_note = " / ".join(notes)
    return out


def select_projection(ui, cfg=None, name="Chest", settle=1.5):
    """인체도에서 부위를 선택한다.

    반환: {"ok": bool, "name": 요청한 부위, "point": 클릭 지점,
           "available": 읽어낸 부위 목록}
    """
    positions = projection_positions(ui, cfg)
    want_n = _norm_label(name)
    hit = None
    for key, pos in positions.items():
        if _norm_label(key) == want_n:
            hit = (key, pos)
            break
    if hit is None:
        return {"ok": False, "name": name, "point": None,
                "available": sorted(positions)}
    # **이미 선택된 부위면 다시 누르지 않는다.** 같은 항목을 다시 누를 때 제품이
    # 무엇을 하는지(유지인지 해제인지) 확정하지 않았으므로, 확인되지 않은 조작을
    # 하지 않는다(CLAUDE.md 3절). 선택 여부는 판독에서 이미 안다 — 선택된 라벨은
    # 파란 글자로 그려지고 점이 흰색이다(실측).
    already = (last_selected_projection is not None
               and _norm_label(last_selected_projection) == _norm_label(hit[0]))
    if not already:
        ui.click(hit[1], settle=settle)
    # 클릭 뒤 Step 박스가 나타났는지로 선택 성공을 확인한다 — 라벨을 눌렀다는
    # 사실만으로 인정하지 않는다. Projection을 고르면 우측에 Step(PA/AP/LAT)이
    # 나타나는 것이 제품 동작이다(실측).
    steps = step_buttons(ui, cfg)
    shown = [b["label"] for b in steps]

    # **정답지로 교차검증한다.** 라벨 판독이 틀렸거나(비슷한 이름끼리 혼동:
    # C-spine / T-spine / L-spine, Full-body / Full-spine) 소거가 어긋났으면
    # 엉뚱한 부위를 고른 것이므로, 나타난 Step 목록이 그 부위의 정답지와
    # 맞는지 본다. 사용자 지적(2026-08-20)대로 라벨 글자색이 부위마다 다를 수
    # 있어 판독을 100% 신뢰할 수 없기 때문에, **눌러 본 결과로 확인한다.**
    verified, note = None, ""
    truth = (known_projection_steps(cfg) or {}) if cfg else {}
    expect = truth.get(hit[0]) or truth.get(name)
    if expect and shown:
        want = set(_norm_label(x) for x in expect)
        got = set(_norm_label(x) for x in shown if x)
        overlap = len(want & got)
        verified = overlap > 0
        if not verified:
            note = ("선택한 부위의 Step 목록이 정답지와 맞지 않는다 — 다른 "
                    "부위를 눌렀을 수 있다. 기대(%s)=%s / 화면=%s"
                    % (hit[0], ", ".join(expect), ", ".join(shown) or "없음"))
        elif overlap < len(want):
            note = ("Step 일부만 일치한다. 기대=%s / 화면=%s"
                    % (", ".join(expect), ", ".join(shown)))
    elif not shown:
        verified = False
        note = "Projection을 눌렀지만 Step 박스가 나타나지 않았다."
    if already:
        note = (note + " / " if note else "") + ("이미 선택된 부위여서 다시 "
                                                 "누르지 않았다.")
    if last_positions_note:
        note = (note + " / " if note else "") + last_positions_note

    return {"ok": bool(verified) if verified is not None else True,
            "name": hit[0], "point": hit[1], "steps_shown": shown,
            "verified": verified, "note": note,
            "available": sorted(positions)}


def known_projection_steps(cfg, projections=None):
    """**Projection -> Step 목록의 정답지**를 XIPL 파라미터 파일명에서 얻는다.

    사용자 제안(2026-08-20): *"라벨을 지금 UI로 읽는것도 괜찮은데 DB나 다른
    데이터베이스 폴더 내에서 읽는 방법도 있지않아? 교차검증하는 방식은 어렵나?"*

    ## 왜 파일명이 정답지인가

    XIPL 파라미터 폴더의 파일명이 `{Projection} {Step}_{강도}_H.hs8` 형식이다
    (실측 2026-08-20, 135개 조합).

    ```
    Chest PA_normal_H.hs8      -> Chest / PA
    Chest AP_normal_H.hs8      -> Chest / AP
    Chest Lat_normal_H.hs8     -> Chest / Lat
    C-spine Open mouth_...     -> C-spine / Open mouth
    ```

    이 목록이 **OCR 오인식을 교정하는 근거**가 된다. 실측에서 Step 박스의
    `LAT`이 OCR로 `Li`로 읽혔는데, 정답지에 `Chest`의 Step이 `AP/Lat/PA`뿐임을
    알면 그 버튼이 `Lat`이라고 확정할 수 있다.

    DB의 `BODYPARTCODE`/`PROJECTIONCODE`도 확인했지만 그쪽은 **DICOM 표준 코드**
    (`Abdomen`, `frontal`, `antero-posterior` …)여서 화면 라벨(`Chest`, `PA`)과
    직접 대응하지 않는다. 그래서 파일명을 쓴다.

    반환: {"Chest": ["AP", "Lat", "PA"], ...}  (Step은 알파벳 순)
    """
    import glob as _glob
    root = ((cfg or {}).get("xipl") or {}).get("parameter_dir")         or os.path.join("C:" + os.sep, "XIPL", "PARAMETER")
    known = list(projections or GENERAL_PROJECTIONS)
    # 긴 이름을 먼저 대조한다("Full-spine"이 "Full-body"보다 먼저 잘리지 않게).
    known.sort(key=len, reverse=True)
    out = {}
    for path in _glob.glob(os.path.join(root, "*_normal_H.hs8")):
        stem = os.path.basename(path)[:-len("_normal_H.hs8")]
        for proj in known:
            if stem.lower().startswith(proj.lower() + " "):
                step = stem[len(proj):].strip()
                if step:
                    out.setdefault(proj, set()).add(step)
                break
    return dict((k, sorted(v)) for k, v in out.items())


def step_buttons(ui, cfg=None):
    """지금 표시된 Projection 버튼과 그 라벨.

    반환: [{"ctrl_id", "rect", "label"}] — 라벨은 owner-draw라 OCR로 읽는다.
    부위를 선택하지 않으면 비어 있다(실측).
    """
    from PIL import ImageGrab
    from .ui import children
    tess = _tess(cfg)
    dlg = bodypart_dialog(ui)
    if dlg is None:
        return []
    out = []
    for c in children(dlg.hwnd, 2):
        if c.ctrl_id not in STEP_BUTTON_IDS or not c.visible:
            continue
        if c.size[0] < 60 or c.size[1] < 30:
            continue
        label = ""
        if tess is not None:
            img = ImageGrab.grab(bbox=c.rect, all_screens=True)
            # 인체도 라벨과 같은 이진화를 적용한다 — Step 박스의 글자도 배경
            # 대비가 낮아 그냥 OCR하면 빈 값이 나온다(실측 2026-08-20: LAT가
            # 빈 문자열로 읽혀 `select_step("LAT")`이 실패했다).
            plain = img.resize((img.width * 3, img.height * 3))
            label = " ".join(tess.image_to_string(plain).split())
            if not label:
                # 빈 값일 때만 이진화로 한 번 더 시도한다. **이진화를 먼저
                # 적용하면 오히려 나빠진다**(실측 2026-08-20: PA/AP가 'lis',
                # 'Al?'로 깨졌다) — 선택된 버튼은 배경이 밝아 글자와 대비가
                # 역전되기 때문이다. 그래서 원본 OCR을 우선한다.
                mask = _label_mask(img)
                big = mask.resize((mask.width * 3, mask.height * 3))
                label = " ".join(
                    tess.image_to_string(big, config="--psm 7").split())
        out.append({"ctrl_id": c.ctrl_id, "rect": c.rect, "label": label,
                    "control": c})
    out.sort(key=lambda d: d["rect"][1])
    return out


def select_step(ui, cfg=None, name=None, index=0, settle=2.0,
                projection=None):
    """Projection을 선택해 Step을 등록한다.

    `name`을 주면 그 라벨과 부분 일치하는 버튼을, 없으면 `index`번째를 누른다.
    반환: {"ok", "label", "ctrl_id", "available"}
    """
    buttons = step_buttons(ui, cfg)
    if not buttons:
        return {"ok": False, "label": None, "ctrl_id": None, "available": []}
    target = None
    if name:
        want = _norm_label(name)
        for btn in buttons:
            lab = _norm_label(btn["label"])
            if want and lab and (want == lab or want in lab or lab in want):
                target = btn
                break

    # OCR이 놓친 경우, **정답지(XIPL 파라미터 파일명)로 교정**한다.
    # 예: Chest의 Step은 AP/Lat/PA뿐이므로, OCR이 'Li'로 읽은 버튼은 Lat이다.
    if target is None and name and projection:
        catalog = known_projection_steps(cfg).get(projection, [])
        want_c = next((c for c in catalog if _norm_label(c) == _norm_label(name)), None)
        if want_c:
            # 정답지에 있는 Step이다. OCR 라벨과 가장 비슷한 버튼을 고른다 —
            # 첫 글자가 같고 길이가 비슷한 것을 우선한다.
            best, best_score = None, -1
            for btn in buttons:
                lab = _norm_label(btn["label"])
                if not lab:
                    continue
                score = 0
                w = _norm_label(want_c)
                if lab[0] == w[0]:
                    score += 2
                score += sum(1 for ch in set(lab) if ch in w)
                if score > best_score:
                    best, best_score = btn, score
            if best is not None and best_score >= 2:
                target = best
                target = dict(target)
                target["label"] = "%s (OCR %r 를 정답지로 교정)" % (
                    want_c, best["label"])
                target["control"] = best["control"]
                target["ctrl_id"] = best["ctrl_id"]

    if target is None:
        if name:
            # **OCR이 짧은 라벨을 놓치는 경우가 있다**(실측 2026-08-20: `LAT`이
            # `Li`로 읽혀 이름 매칭이 실패했다. `PA`/`AP`는 정확했다). 이름으로
            # 못 찾으면 **추측해서 아무 버튼이나 누르지 않고** 실패로 남기고
            # 읽어낸 라벨 목록을 함께 돌려준다 — 호출부가 index로 지정하거나
            # 사람이 확인할 수 있게 하는 것이 엉뚱한 Step을 등록하는 것보다 낫다.
            return {"ok": False, "label": None, "ctrl_id": None,
                    "requested": name,
                    "available": [b["label"] for b in buttons]}
        target = buttons[min(index, len(buttons) - 1)]
    ui.click(target["control"], settle=settle)
    return {"ok": True, "label": target["label"], "ctrl_id": target["ctrl_id"],
            "available": [b["label"] for b in buttons]}


def instance_count(cfg, patient_id=None):
    """DB `INSTANCE` 행 수. **촬영이 실제로 일어났는지의 1차 근거**다.

    ## 왜 SERIES가 아니라 INSTANCE인가 (실측 2026-08-20)

    처음에는 `SERIES` 행 수로 판정했는데, **같은 검사에서 두 번째 Step을 촬영하면
    SERIES는 늘지 않는다.** DICOM 구조가 Study > Series > Instance이고 제품은 한
    검사의 영상들을 한 Series에 담기 때문이다. 실측:

    ```
    InstanceKey=13  SeriesKey=13  InstanceNumber=1  ContentTime=084929
    InstanceKey=14  SeriesKey=13  InstanceNumber=2  ContentTime=090716
    ```

    SERIES는 13개로 그대로였고 INSTANCE가 13 -> 14로 늘었다. 그래서 SERIES로
    판정하면 "촬영했는데 실패"로 오판정한다.

    썸네일 항목 수도 쓸 수 없다 — Step을 등록하면 촬영 전에도 항목이 생긴다.
    """
    from .db import VXvueDb
    db = VXvueDb(cfg.get("sql_server", chr(46) + chr(92) + "CHAMELEON"),
                 cfg.get("database", "DRF"))
    if patient_id:
        sql = ("SELECT COUNT(*) AS n FROM INSTANCE i "
               "JOIN SERIES se ON i.SeriesKey = se.SeriesKey "
               "JOIN STUDY st ON se.StudyKey = st.StudyKey "
               "JOIN PATIENT p ON st.PatientKey = p.PatientKey "
               "WHERE i.DeleteStatus = 0 AND p.PatientId = '%s'"
               % str(patient_id).replace("'", "''"))
    else:
        sql = "SELECT COUNT(*) AS n FROM INSTANCE WHERE DeleteStatus = 0"
    try:
        rows = db.query(sql)
        return rows[0]["n"] if rows else None
    except Exception:                                    # noqa: BLE001
        return None


def add_step(ui, cfg=None, projection="Chest", step="PA",
             category=DEFAULT_CATEGORY, evidence_dir=None):
    """인체도에서 부위·Projection을 골라 촬영 Step을 등록한다.

    사용자 지시(2026-08-20): F2를 그냥 누르지 말고 **원하는 Step을 등록한 뒤**
    촬영한다. Step이 등록되면 그 Step에 대응하는 영상처리 파라미터가 지정되고
    (촬영 직후 파라미터 오류가 사라진다), 검사가 완료 처리될 수 있어 Database
    목록에도 나타난다 — MWL Procedure Mapping을 생략해도 이 경로로 Step을
    확보할 수 있다.

    반환: {
      "ok": bool, "category": ensure_category 결과,
      "bodypart": select_bodypart 결과, "projection": select_projection 결과,
      "steps_before": n, "steps_after": n, "dialogs": [DialogRecord...]
    }
    """
    out = {"ok": False, "category": None, "projection": None, "step": None,
           "steps_before": None, "steps_after": None, "dialogs": []}

    out["dialogs"] += dialogs.clear_blocking(ui, cfg, evidence_dir=evidence_dir)

    out["steps_before"] = step_count(ui)
    out["category"] = ensure_category(ui, cfg, category)
    if not out["category"]["ok"]:
        return out

    # 인체도에서 Projection(Chest 등)을 고른다.
    out["projection"] = select_projection(ui, cfg, projection)
    if not out["projection"]["ok"]:
        return out

    # 그 옆에 나타난 네모 박스에서 Step(PA/AP/LAT)을 고른다.
    out["step"] = select_step(ui, cfg, step, projection=projection)
    if not out["step"]["ok"]:
        return out

    out["dialogs"] += dialogs.clear_blocking(ui, cfg, evidence_dir=evidence_dir)
    out["steps_after"] = step_count(ui)
    # Step 항목이 실제로 늘었는지로 판정한다 — 버튼을 눌렀다는 사실만으로
    # 등록을 인정하지 않는다(비활성 버튼을 눌러도 클릭은 조용히 성공한다).
    # 이미 같은 Step이 있으면 늘지 않을 수 있어, 그 경우 Step 선택 성공으로
    # 대체 판정하고 `grew`로 구분한다.
    grew = (out["steps_after"] or 0) > (out["steps_before"] or 0)
    out["grew"] = grew
    out["ok"] = bool(grew or (out["step"] or {}).get("ok"))
    return out


def step_count(ui):
    """등록된 Step 수. 우측 썸네일 패널의 항목 수와 같다.

    **실측(2026-08-20): Step을 등록하면 촬영 전에도 썸네일 패널에 항목이
    생긴다.** Chest + PA를 고르자 "Chest PA" 항목이 나타났고 영상은 없었다.
    그래서 이 값은 "등록된 Step 수"이며 **촬영 여부를 말해 주지 않는다** —
    촬영 성공 판정은 `series_count()`(DB)로 한다.
    """
    return thumbnail_count(ui)


def series_count(cfg, patient_id=None):
    """DB `SERIES` 행 수. **촬영이 실제로 일어났는지의 근거**다.

    실측(2026-08-20): 촬영하면 `SERIES`에 행이 생긴다(`SeriesKey / StudyKey /
    SeriesDate / SeriesTime / Modality=DX / ProtocolName=CHEST`). 썸네일 항목
    수는 Step 등록만으로도 늘어나므로 촬영 판정에 쓸 수 없다.
    """
    from .db import VXvueDb
    db = VXvueDb(cfg.get("sql_server", chr(46)+chr(92)+"CHAMELEON"), cfg.get("database", "DRF"))
    if patient_id:
        sql = ("SELECT COUNT(*) AS n FROM SERIES se "
               "JOIN STUDY st ON se.StudyKey = st.StudyKey "
               "JOIN PATIENT p ON st.PatientKey = p.PatientKey "
               "WHERE se.DeleteStatus = 0 AND p.PatientId = '%s'"
               % str(patient_id).replace("'", "''"))
    else:
        sql = "SELECT COUNT(*) AS n FROM SERIES WHERE DeleteStatus = 0"
    try:
        rows = db.query(sql)
        return rows[0]["n"] if rows else None
    except Exception:                                    # noqa: BLE001
        return None


# --- 촬영 -------------------------------------------------------------
def acquire(ui, cfg, timeout=90, poll=3.0, evidence_dir=None):
    """Demo(가상) 촬영을 1회 수행하고 영상이 생겼는지 확인한다.

    반환: {
      "key": 누른 키, "before": 촬영 전 영상 수, "after": 촬영 후 영상 수,
      "acquired": bool, "seconds": 소요, "state": 촬영 상태,
      "dialogs": [DialogRecord...], "known_warning": bool,
      "instances_before": n, "instances_after": n
    }

    **판정 근거는 DB `INSTANCE` 행 수 증가**다. 썸네일 항목 수는 Step 등록만으로도
    늘어나고, `SERIES`는 같은 검사의 두 번째 촬영에서 늘지 않는다(실측 2026-08-20
    — `instance_count()` docstring 참고). DB를 읽을 수 없는 환경에서만 썸네일
    증가로 대체 판정한다.

    `known_warning`은 뜬 팝업이 이미 원인을 확인한 환경 문제
    (`Image process parameter file does not exist` — docstring 참고)일 때 True다.
    그 경우에도 **팝업이 떴다는 사실 자체는 결과에 남긴다.**
    """
    key = (cfg.get("viewer") or {}).get("demo_exposure_key", "F2")
    before = thumbnail_count(ui)
    state0 = acquisition_state(ui, cfg)
    # **촬영 판정의 1차 근거는 DB `INSTANCE` 행 수다.**(`instance_count()`
    # docstring 참고) 썸네일 항목 수로는 판정할 수 없다 — Step을 등록하면 촬영
    # 전에도 항목이 생기므로(실측 2026-08-20) 이미 늘어난 상태에서는 증가를
    # 감지하지 못하고 제한 시간을 그대로 소진한다(109초 걸린 실측이 그 경우였다).
    # SERIES도 쓸 수 없다 — 같은 검사의 두 번째 촬영은 같은 Series에 담긴다.
    patient_id = (cfg.get("test_data") or {}).get("mwl_patient_id")
    series0 = instance_count(cfg, patient_id)
    out = {"key": key, "before": before, "after": before, "acquired": False,
           "seconds": 0, "state": state0, "dialogs": [], "known_warning": False,
           "instances_before": series0, "instances_after": series0,
           "step_selection": None, "note": ""}

    # **촬영 전에 미촬영 Step을 선택하고 Ready를 확인한다.**
    # F2는 선택된 Step을 촬영하므로, 이미 촬영이 끝난 항목이 선택돼 있으면
    # 아무 일도 일어나지 않는다(실측 2026-08-20 — 130초 대기 후 실패).
    picked = select_unshot_step(ui)
    out["step_selection"] = picked
    if not picked["ok"] and picked["total"]:
        out["note"] = ("촬영할 Step이 없다 — 등록된 %d개가 모두 촬영 완료 상태다. "
                       "새 Step을 등록한 뒤(add_step) 촬영할 것."
                       % picked["total"])
        out["state"] = acquisition_state(ui, cfg)
        return out

    state_now = acquisition_state(ui, cfg)
    out["state"] = state_now
    if "ready" not in state_now.lower():
        out["note"] = ("촬영 준비 상태가 아니다(AcquisitionState=%r). 미등록 상태에서 "
                       "%s를 눌러도 영상이 생기지 않아 '촬영했는데 실패'로 오판정되므로 "
                       "누르지 않는다." % (state_now, key))
        return out

    ui.activate()
    time.sleep(0.5)
    ui.key(key, settle=1.0)
    started = time.time()

    end = started + timeout
    while time.time() < end:
        time.sleep(poll)
        d = ui.dialog()
        if d is not None:
            msg = dialog_message(ui, d, cfg)
            title = (d.text or "").strip()
            if evidence_dir:
                os.makedirs(evidence_dir, exist_ok=True)
                try:
                    ui.capture_dialog(dlg=d, path=os.path.join(
                        evidence_dir, "acquire_dlg_%d.png" % (len(out["dialogs"]) + 1)))
                except Exception:                        # noqa: BLE001
                    pass
            text = ("%s: %s" % (title, msg)).strip(": ")
            out["dialogs"].append(text)
            if any(w in (msg or "").lower() or w in title.lower()
                   for w in KNOWN_ACQUIRE_WARNINGS):
                out["known_warning"] = True
            ui.dismiss_dialog(timeout=3)
            continue
        # DB에 시리즈가 생겼는지로 판정한다(1차 근거).
        series_now = instance_count(cfg, patient_id)
        if series0 is not None and series_now is not None and series_now > series0:
            out["instances_after"] = series_now
            out["after"] = thumbnail_count(ui)
            out["acquired"] = True
            break
        # DB를 못 읽는 환경이면 썸네일 증가로 대체 판정한다.
        now = thumbnail_count(ui)
        if series0 is None and now > before:
            out["after"] = now
            out["acquired"] = True
            break

    out["seconds"] = round(time.time() - started, 1)

    # 영상이 생긴 뒤에도 팝업이 늦게 뜨는 일이 있다(실측: Image Processing 오류가
    # 썸네일 생성보다 몇 초 늦게 떴고, 그것을 닫지 않은 채 다음 화면으로
    # 넘어가려 해서 이후 조작이 전부 무시됐다). 그래서 마지막에 한 번 더 훑고,
    # 닫은 문구를 결과에 합친다.
    time.sleep(2.0)
    late = pending_dialogs(ui, evidence_dir=evidence_dir, cfg=cfg)
    for text in late:
        out["dialogs"].append(text)
        if any(w in text.lower() for w in KNOWN_ACQUIRE_WARNINGS):
            out["known_warning"] = True

    out["after"] = max(out["after"], thumbnail_count(ui))
    final_series = instance_count(cfg, patient_id)
    out["instances_after"] = final_series
    if series0 is not None and final_series is not None:
        out["acquired"] = final_series > series0
    else:
        out["acquired"] = out["after"] > before
    out["state"] = acquisition_state(ui, cfg)
    return out


def open_and_acquire(ui, cfg, patient_id=None, projection="Chest", step="PA",
                    evidence_dir=None, map_procedure_name=None):
    """MWL 처방을 열고 **Step을 등록한 뒤** 촬영한다 — TC 공용 진입점.

    사용자 지시(2026-08-20): *"촬영모드에서 너 그냥 f2 클릭으로 촬영을
    시작하는데 왼쪽에 사람 모양에서 bodypart-projection - step을 잘 선택해서
    원하는 step을 등록 후 촬영까지 수행해줘."*

    순서: MWL 조회·Study 등록 -> `General` 카테고리 확인 -> Projection(Chest)
    -> Step(PA) -> 미촬영 Step 선택 -> F2 촬영 -> DB `INSTANCE` 증가 확인.

    Step을 등록하고 촬영하면 그 Step에 대응하는 영상처리 파라미터가 지정되므로,
    Step 없이 촬영했을 때 나던 `Image process parameter file does not exist`
    오류가 발생하지 않는다(실측 2026-08-20).

    반환: {"opened": open_mwl_study 결과, "step": add_step 결과,
           "acquire": acquire 결과, "ok": bool}
    """
    out = {"opened": None, "step": None, "acquire": None, "ok": False}
    out["opened"] = open_mwl_study(ui, cfg, patient_id=patient_id,
                                   evidence_dir=evidence_dir,
                                   map_procedure_name=map_procedure_name)
    if not out["opened"]["start"]["ready"]:
        return out
    goto(ui, "exposure")
    time.sleep(1.0)
    if not ensure_exposure_mode(ui, cfg):
        raise WorkflowError(
            "촬영 화면이 Viewer 최대화 상태에서 Exposure 최소화 상태로 복귀하지 "
            "않았습니다. 우측 상단 최대/최소 버튼(%d)과 인체도 표시를 확인하십시오."
            % VIEWER_MINMAX_BUTTON)
    out["step"] = add_step(ui, cfg, projection=projection, step=step,
                           evidence_dir=evidence_dir)
    if not out["step"]["ok"]:
        return out
    out["acquire"] = acquire(ui, cfg, evidence_dir=evidence_dir)
    out["ok"] = bool(out["acquire"]["acquired"])
    return out


# --- 확장 툴 팔레트 (Viewer 모드 Tools ≡) ------------------------------
#
# ## 진입 경로 (사용자 안내 + 실측, 2026-08-20)
#
# 1. Exposure 화면 우측 상단 **최대/최소 버튼**(`CUIMinMaxDlg` 안의 `30330`)을
#    누르면 Viewer 모드로 바뀌고 우측에 도구 패널이 나타난다.
# 2. 패널은 네 섹션(Manipulation / Layout / Annotation / Tools)이고, 각 섹션
#    헤더 우측의 **≡ 버튼**을 누르면 그 섹션의 **전체 툴 팝업**이 열린다.
#    실측 ID: `30400` Manipulation · `30401` Layout · `30402` Annotation ·
#    **`30403` Tools**.
#
# ## 팝업은 약 2.1초 뒤 스스로 닫힌다 (실측)
#
# 사용자 제보로 확인했다. 0.1초 간격으로 팝업 영역 밝기를 재서 측정한 결과:
#
# ```
# 0.32s  열림       (밝기 20.8 -> 71.0)
# 2.42s  닫힘       (밝기 71.0 -> 20.8)
# => 유지 약 2.09초
# ```
#
# **그 안에 컨트롤 트리를 열거할 수 없다** — `children(main, 3)` 한 번이 8.13초
# 걸렸다(실측). 그래서 이 모듈은
#
#   (1) **관찰**: ≡ 를 누르고 **즉시 캡처**(0.39초)해서 OCR로 라벨 위치를 읽고,
#   (2) **조작**: ≡ 를 다시 누르고 **곧바로 그 좌표를 클릭**한다.
#
# 좌표는 캡처에서 그때그때 계산하므로 코드에 박히지 않는다(`CLAUDE.md` 3절의
# 2순위 — 속성으로 못 찾을 때만 위치를 쓰고, 하드코딩은 하지 않는다).
#
# ## 팝업에 있는 툴 (실측 5열 x 6행)
#
# ```
# Multi-Send  Ext.Save   Stitch     Raw        XIPL
# Retake      Move Img   Copy       Target E.I None
# None        Orientation Up        Down       PS Image
# Proc.       Get Img    Full View  Reset      Change
# Guide       LPI        Undo       Redo       Edit
# Extra Tool  Soft Tissue Live View Compare    Save Pro...
# ```
#
# TC와의 대응: **`Proc.`** = TC04 Step 2의 Image Process, **`XIPL`** = TC04
# Step 3, **`Extra Tool`** = TC06, **`Live View`** = TC12.
VIEWER_MINMAX_BUTTON = 30330
VIEWER_RESTORE_BUTTON = 30331
SECTION_MENU = {"manipulation": 30400, "layout": 30401,
                "annotation": 30402, "tools": 30403}

# 팝업이 그려지는 영역(넉넉히 잡는다 — OCR이 그 안에서 라벨을 찾는다).
# ≡ 버튼 위치를 기준으로 계산하므로 화면 구성이 바뀌어도 따라간다.
_PALETTE_OFFSET = (-612, 2)      # ≡ rect 좌상단 기준 팝업 좌상단
_PALETTE_SIZE = (360, 440)

# 팝업이 열려 있는 동안만 조작할 수 있다(실측 2.09초). 여유를 두고 쓴다.
PALETTE_OPEN_DELAY = 0.35        # 열리기까지
PALETTE_HOLD_SECONDS = 1.6       # 안전하게 조작 가능한 시간

_PALETTE_CACHE = {}                   # (pid, section) -> {label: (x, y)}


def restore_exposure_layout(ui, cfg=None, settle=2.5):
    """Viewer 최대화 레이아웃이면 우측 상단 네모 버튼으로 최소화해 복귀한다."""
    from .ui import children
    main = ui.main_window()
    if main is None:
        return False
    tools = [c for c in children(main.hwnd, 6)
             if c.ctrl_id == SECTION_MENU["tools"] and c.visible]
    if not tools:
        return True
    # **방향이 다른 두 버튼을 섞어 쓰면 안 된다**(사용자 확인 2026-08-20):
    # `30331`이 Viewer→Exposure 복귀, `30330`이 그 반대다. 둘을 한 목록에 담아
    # 먼저 열거된 것을 누르면 열거 순서에 따라 반대 방향을 눌러 최대화가 유지된다.
    # 그래서 복귀 버튼을 먼저 찾고, 없을 때만 토글 버튼으로 되돌린다.
    found = [c for c in children(main.hwnd, 4)
             if c.ctrl_id in (VIEWER_RESTORE_BUTTON, VIEWER_MINMAX_BUTTON)
             and c.visible and c.size[0] > 40]
    hits = ([c for c in found if c.ctrl_id == VIEWER_RESTORE_BUTTON]
            or [c for c in found if c.ctrl_id == VIEWER_MINMAX_BUTTON])
    if not hits:
        return False
    dialogs.clear_blocking(ui, cfg)
    ui.click(hits[0], settle=settle)
    main = ui.main_window()
    return bool(main and not [c for c in children(main.hwnd, 6)
                              if c.ctrl_id == SECTION_MENU["tools"] and c.visible])


def ensure_exposure_mode(ui, cfg=None, timeout=12):
    """Step 등록 가능한 촬영 레이아웃(인체도 표시)을 보장한다.

    이전 TC가 Viewer 최대화 상태를 남기면 Exposure 탭으로 이동해도 인체도가
    가려진다. 현재 Tools 패널 노출로 최대화를 판별하고 네모 버튼으로 복귀한 뒤,
    `CUIBodypartDlg`가 실제 나타났을 때만 성공으로 인정한다.
    """
    if bodypart_dialog(ui) is not None:
        return True
    restore_exposure_layout(ui, cfg)
    end = time.time() + timeout
    while time.time() < end:
        if bodypart_dialog(ui) is not None:
            return True
        time.sleep(0.5)
    return False


def viewer_mode(ui, cfg=None, settle=2.5):
    """Exposure 화면을 Viewer 모드(우측 도구 패널)로 전환한다.

    이미 그 모드면 아무것도 하지 않는다 — 토글이라 다시 누르면 되돌아간다.
    판별: Tools 섹션 ≡(`30403`)가 보이면 이미 Viewer 모드다.
    """
    from .ui import children
    main = ui.main_window()
    if main is None:
        return False
    if [c for c in children(main.hwnd, 6)
            if c.ctrl_id == SECTION_MENU["tools"] and c.visible]:
        return True
    dialogs.clear_blocking(ui, cfg)
    hits = [c for c in children(main.hwnd, 4)
            if c.ctrl_id == VIEWER_MINMAX_BUTTON and c.visible and c.size[0] > 40]
    if not hits:
        return False
    ui.click(hits[0], settle=settle)
    return bool([c for c in children(main.hwnd, 6)
                 if c.ctrl_id == SECTION_MENU["tools"] and c.visible])


def _section_button(ui, section="tools"):
    from .ui import children
    main = ui.main_window()
    if main is None:
        return None
    cid = SECTION_MENU[section]
    hits = [c for c in children(main.hwnd, 6) if c.ctrl_id == cid and c.visible]
    return hits[0] if hits else None


def _palette_area(button):
    l, t, _r, _b = button.rect
    x = l + _PALETTE_OFFSET[0]
    y = t + _PALETTE_OFFSET[1]
    return (x, y, x + _PALETTE_SIZE[0], y + _PALETTE_SIZE[1])


# **툴 개수는 고정이 아니다.** 사용자 확인(2026-08-20): *"이 이미지에서 나타나는
# tool 갯수도 라이선스나 옵션 설정 이런거에 따라 달라질 수 있어."* 그래서 격자
# 크기(5x6 등)를 가정하지 않는다 — 팝업 영역을 찾아 그 안의 라벨을 읽고, 읽힌
# 것만 다룬다. 필요한 툴이 없으면 "이 환경에는 노출되지 않았다"로 보고한다.
#
# 팝업 영역은 밝기로 자동 검출한다. 팝업은 배경(영상 표시 영역)보다 밝아서
# 경계가 뚜렷하다 — 실측 밝기 평균 71.0 대 20.8.
_PALETTE_SEARCH = (1100, 540, 1600, 1020)   # 이 안에서 팝업을 찾는다
_PALETTE_BRIGHT = 45                        # 이보다 밝으면 팝업 픽셀로 본다
_PALETTE_MIN_SIZE = (150, 150)


def _detect_palette_box(shot, origin):
    """캡처에서 팝업 경계를 찾는다. 반환: 화면 좌표 (l, t, r, b) 또는 None.

    팝업이 배경보다 밝다는 성질만 쓴다 — 격자나 크기를 가정하지 않으므로
    툴 개수가 환경에 따라 달라져도 그대로 동작한다.
    """
    import numpy as np
    gray = np.asarray(shot.convert("L"), dtype=np.uint8)
    mask = gray > _PALETTE_BRIGHT
    rows = np.where(mask.sum(axis=1) > mask.shape[1] * 0.25)[0]
    cols = np.where(mask.sum(axis=0) > mask.shape[0] * 0.25)[0]
    if rows.size < _PALETTE_MIN_SIZE[1] or cols.size < _PALETTE_MIN_SIZE[0]:
        return None
    t, b = int(rows[0]), int(rows[-1])
    l, r = int(cols[0]), int(cols[-1])
    return (origin[0] + l, origin[1] + t, origin[0] + r, origin[1] + b)


# 라벨 판독은 **여러 OCR 패스의 결과를 합친다.** 한 조합으로는 일부를 놓친다
# (실측 2026-08-20, 캡처 파일로 튜닝: scale=3+이진화 21/28, scale=4+그레이 22/28,
# 합치면 거의 전부). 라벨 글자가 8px 정도라 확대 배율과 전처리에 민감하다.
_OCR_PASSES = ((3, True), (4, False), (4, True))

# 이 화면에 나올 수 있는 툴 이름(실측 2026-08-20). **개수는 환경마다 다르다** —
# 사용자 확인: 라이선스·옵션 설정에 따라 노출되는 툴이 달라진다. 그래서 이
# 목록은 **OCR 오인식을 걸러내는 후보 사전**일 뿐이고, 목록에 있어도 화면에
# 없으면 "이 환경에 노출되지 않았다"로 보고한다(없는 자리를 추측해 누르지 않는다).
KNOWN_TOOLS = (
    "Multi-Send", "Ext.Save", "Stitch", "Raw", "XIPL",
    "Retake", "Move Img", "Copy", "Target E.I", "None",
    "Orientation", "Up", "Down", "PS Image",
    "Proc.", "Get Img", "Full View", "Reset", "Change",
    "Guide", "LPI", "Undo", "Redo", "Edit",
    "Extra Tool", "Soft Tissue", "Live View", "Compare", "Save Pro",
    "Send", "Print", "Reject", "Suspend", "Close", "Close All",
)


def read_tool_palette(ui, cfg=None, section="tools", evidence_dir=None,
                      refresh=False):
    """툴 팝업을 열고 **즉시 캡처**해 라벨 -> 클릭 좌표를 읽는다.

    반환: {"XIPL": (x, y), "Proc.": (x, y), ...}

    ## 왜 캡처인가

    팝업은 약 2.1초 뒤 스스로 닫히고(실측: 0.32s 열림 -> 2.42s 닫힘), 그 안에
    컨트롤 트리를 열거할 수 없다(`children(main, 3)` 한 번이 8.13초). 그래서
    **팝업이 열린 동안 캡처만** 하고(0.39초) OCR은 닫힌 뒤에 여유롭게 한다.

    ## 왜 격자를 가정하지 않는가

    사용자 확인(2026-08-20): **툴 개수는 라이선스·옵션 설정에 따라 달라진다.**
    그래서 팝업 영역만 밝기로 검출하고, 그 안에서 읽힌 라벨만 다룬다. 필요한
    툴이 없으면 그 사실을 보고한다.

    ## 판독 방식

    라벨 글자가 8px 정도로 작아 확대 배율과 전처리에 민감하다. 한 조합으로는
    28개 중 20개 안팎만 읽힌다(실측). 그래서 `_OCR_PASSES`의 여러 조합으로
    읽어 **결과를 합치고**, `KNOWN_TOOLS`와 대조해 오인식을 걸러낸다.

    좌표는 매번 캡처에서 계산하므로 코드에 박히지 않는다(`CLAUDE.md` 3절 2순위).
    """
    from PIL import Image, ImageGrab
    key = (ui.pid, section)
    if not refresh and _PALETTE_CACHE.get(key):
        return _PALETTE_CACHE[key]

    tess = _tess(cfg)
    btn = _section_button(ui, section)
    if btn is None or tess is None:
        return {}

    ui.click(btn, settle=0.05)
    time.sleep(PALETTE_OPEN_DELAY)
    shot = ImageGrab.grab(bbox=_PALETTE_SEARCH, all_screens=True)   # 열린 동안
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        try:
            shot.save(os.path.join(evidence_dir, "tool_palette_%s.png" % section))
        except Exception:                                    # noqa: BLE001
            pass

    box = _detect_palette_box(shot, (_PALETTE_SEARCH[0], _PALETTE_SEARCH[1]))
    if box is None:
        return {}
    crop = shot.crop((box[0] - _PALETTE_SEARCH[0], box[1] - _PALETTE_SEARCH[1],
                      box[2] - _PALETTE_SEARCH[0], box[3] - _PALETTE_SEARCH[1]))

    want = dict((_norm_label(t), t) for t in KNOWN_TOOLS if _norm_label(t))
    found = {}
    for scale, binarize in _OCR_PASSES:
        im = crop.convert("L")
        if binarize:
            im = im.point(lambda v: 0 if v > 150 else 255)
        big = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
        data = tess.image_to_data(big, output_type=tess.Output.DICT)
        for i, raw in enumerate(data["text"]):
            norm = _norm_label(raw)
            if len(norm) < 2:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1
            if conf < 30:
                continue
            match = None
            for k, orig in want.items():
                if k == norm or (len(norm) >= 4 and (norm in k or k in norm)):
                    match = orig
                    break
            if match is None or match in found:
                continue
            cx = box[0] + (data["left"][i] + data["width"][i] // 2) // scale
            cy = box[1] + (data["top"][i] + data["height"][i] // 2) // scale
            # 라벨은 아이콘 아래에 그려진다 — 클릭 지점은 그 위 아이콘 중앙.
            found[match] = (cx, cy - 20)
    _PALETTE_CACHE[key] = found
    return found


def click_tool(ui, cfg=None, name="XIPL", section="tools", evidence_dir=None,
               settle=2.5):
    """확장 툴 팝업에서 툴 하나를 누른다.

    팝업이 약 2.1초만 열려 있으므로(실측), **좌표를 미리 확보해 두고** 팝업을
    열자마자 클릭한다. 좌표가 없으면 먼저 `read_tool_palette()`로 읽는다.

    반환: {"ok": bool, "name": 요청, "matched": 실제 라벨, "point": (x,y),
           "available": [읽어낸 라벨...]}
    """
    palette = read_tool_palette(ui, cfg, section, evidence_dir)
    if not palette:
        return {"ok": False, "name": name, "matched": None, "point": None,
                "available": []}

    want = _norm_label(name)
    matched, point = None, None
    for label, pos in palette.items():
        lab = _norm_label(label)
        if lab and (lab == want or want in lab or lab in want):
            matched, point = label, pos
            break
    if point is None:
        return {"ok": False, "name": name, "matched": None, "point": None,
                "available": sorted(palette)}

    btn = _section_button(ui, section)
    if btn is None:
        return {"ok": False, "name": name, "matched": matched, "point": point,
                "available": sorted(palette)}
    # 팝업을 열고 **곧바로** 클릭한다 — 2.1초 창을 놓치면 클릭이 화면 뒤쪽
    # (영상 영역)으로 들어간다.
    ui.click(btn, settle=0.05)
    time.sleep(PALETTE_OPEN_DELAY)
    ui.click(point, settle=settle)
    return {"ok": True, "name": name, "matched": matched, "point": point,
            "available": sorted(palette)}


def confirm_scope_popup(ui, scope="all", dialog_timeout=8, settle=2.0):
    """이미 띄워 놓은 'Do you want to send/print all images...' 팝업에서

    범위 버튼(All Images/Selected/Cancel, `27002`/`27001`/`27000`)을 누른다.
    Send와 Print 확인 팝업이 문구만 다르고 버튼 ID 구성은 같다(실측
    2026-08-21 — Database > Print를 눌러서 뜨는 팝업의 자식을 그 자리에서
    덤프해 확인했다). 팝업을 직접 트리거하지 않는 호출부(`send()`처럼 버튼을
    누르는 쪽이 아니라, Database 목록 액션 등으로 이미 팝업이 뜬 뒤)에서 쓴다.

    반환: {"scope","clicked","dialog":bool}
    """
    from .ui import children
    if scope not in SEND_SCOPE:
        raise WorkflowError("알 수 없는 확인 범위: %s" % scope)
    want = SEND_SCOPE[scope]
    end = time.time() + dialog_timeout
    while time.time() < end:
        d = ui.dialog()
        if d is not None:
            btn = [c for c in children(d.hwnd, 3) if c.ctrl_id == want]
            if btn:
                ui.click(btn[0], settle=settle)
                return {"scope": scope, "clicked": want, "dialog": True}
        time.sleep(0.5)
    return {"scope": scope, "clicked": None, "dialog": False}


# --- 전송 -------------------------------------------------------------
def send(ui, scope="all", settle=2.5, dialog_timeout=8, attempts=3):
    """선택한 영상을 DICOM Storage로 전송한다.

    Send 버튼은 Exposure/Database에서 같은 ID(30294)다. 전송 범위 팝업
    (All Images / Selected / Cancel)까지 처리한다.

    **영상을 먼저 선택해야 한다** — 선택 전에는 Send가 비활성이라 눌러도 팝업이
    뜨지 않는다. `select_first_image()`를 먼저 호출할 것.

    반환: {"scope","clicked","dialog":bool}
    """
    if scope not in SEND_SCOPE:
        raise WorkflowError("알 수 없는 전송 범위: %s" % scope)
    for _ in range(attempts):
        hits = by_id(ui, TOOL["send"])
        if not hits:
            raise WorkflowError("Send 버튼(%d)을 찾지 못했습니다." % TOOL["send"])
        ui.click(hits[0], settle=settle)
        result = confirm_scope_popup(ui, scope=scope, dialog_timeout=dialog_timeout)
        if result["dialog"]:
            return result
    return {"scope": scope, "clicked": None, "dialog": False}


def finish_print(ui, button="print", timeout=8, settle=2.5):
    """Film Manager(`CUIFilmManager`) 화면에서 실제 전송 버튼을 누른다.

    **Database > Print는 곧바로 전송하지 않는다** — 확인 팝업(`confirm_scope_popup`)을
    누르면 필름 구성 화면(CUIFilmManager)으로 전환될 뿐이고, 그 화면의
    Print(`30718`) 또는 Print & Close(`30719`)를 다시 눌러야 Print SCP로 실제
    전송된다(실측 2026-08-21: 이 두 번째 클릭 없이는 확인 팝업까지 다 눌러도
    수신 쪽에 필름이 0건이었다). 두 버튼 모두 표준 API로 라벨을 읽을 수 없어
    캡처+OCR로 `30718`='Print', `30719`='Print & Close'를 확정했다(2026-08-19).

    반환: {"clicked": ctrl_id 또는 None}
    """
    want = PRINT_BUTTON if button == "print" else PRINT_AND_CLOSE_BUTTON
    end = time.time() + timeout
    while time.time() < end:
        hits = by_id(ui, want)
        if hits:
            ui.click(hits[0], settle=settle)
            return {"clicked": want}
        time.sleep(0.5)
    return {"clicked": None}


# --- Print Overlay (Setting > DICOM - Print Overlay / DICOM - Print) -----
#
# 체크리스트 원문에는 없지만 사양서4(260820) p.100-108 `VP-714`("07-80-80 Print
# Overlay")·사양서5(260820) p.94-97 `VP-786`("10-20-70 Print")에 실존하는 기능이라
# 사용자 지시로 TC07에 추가했다(2026-08-21). 실측으로 확정한 것:
#
# 1. `Setting > DICOM - Print Overlay` 화면에 **별도의 SCP List**(`31158`)가
#    있고, Add(`30440`)를 누르면 기본 이름 "Print Overlay"인 새 프로파일이
#    바로 추가된다(별도 팝업 없음). Overlay Name(`30190`)을 실제 등록된 Print
#    SCP 이름과 **똑같이** 지어야 그 SCP에 연결할 수 있다(아래 3번).
# 2. Layout Composition의 Top/Bottom 행에서 배치를 고르면(`30859`=Top 단일
#    영역, `30869`=Bottom 단일 영역) 그 아래 Top Left/Top Right/Bottom Left/
#    Bottom Right 4개 목록(`31159`~`31162`)이 활성화된다. 가운데 "Item"
#    마스터 목록(`31163`, 총 30여 개, 스크롤 필요)에서 항목을 선택하고 화살표
#    버튼으로 옮긴다 — 화살표는 구역마다 (추가, 제거) 쌍으로 `30755`/`30756`
#    (Top Left), `30757`/`30758`(Top Right), `30759`/`30760`(Bottom Left),
#    `30761`/`30762`(Bottom Right)이다(실측 확정 — 대칭이라고 추측한 최초
#    배정은 Top Right·Bottom Right가 반대였다).
# 3. **이 화면에서 설정하고 Update하는 것만으로는 실제 인쇄물에 반영되지
#    않는다**(사용자 제보, 2026-08-21 실측으로 재현). `Setting > DICOM -
#    Print`(SCP 등록 화면)에서 그 SCP 행을 선택하면 상세 패널에 "Overlay"
#    콤보(`30942`, y=496으로 화면의 다른 동일 ID 콤보와 구분)가 있고 기본값이
#    "None"이다 — 이 콤보에서 위에서 만든 프로파일 이름을 **선택하고
#    Update**해야 그 SCP로 보내는 필름에 실제로 그려진다. 두 화면 다 저장한
#    뒤 Print SCP 서버의 `/api/jobs/<id>/preview`(JPEG, 문서화되지 않은
#    엔드포인트지만 `/api/jobs/<id>` 응답의 `preview_url` 필드로 실존 확인)로
#    받은 필름을 OCR해 실제 픽셀 반영을 확인했다(`core/printscp.py`).
# 4. 항목 이름과 필름에 실제로 그려지는 라벨은 다르다 — 예: "Exposure Index"는
#    `E.I. : 1115`, "Exposure Date"는 `DOI : 2026-08-21`, "Accession Number"는
#    `Acc. No : ...`로 그려진다. "Dose kVp"는 라벨 없이 값만("50") 그려져
#    OCR 근거로 쓰기엔 모호하고, "Institutional Name"은 이 시험 데이터가 그
#    값을 비워 둬서 아무것도 그려지지 않았다(빈 값은 렌더링하지 않는 것으로
#    보인다) — 그래서 판정에는 값이 항상 채워지는 나머지만 쓴다.
PRINT_OVERLAY_ITEM_LIST_ID = 31163
PRINT_OVERLAY_SLOT_LIST = {"top_left": 31159, "top_right": 31160,
                          "bottom_left": 31161, "bottom_right": 31162}
PRINT_OVERLAY_ADD_ARROW = {"top_left": 30755, "top_right": 30757,
                           "bottom_left": 30759, "bottom_right": 30761}
PRINT_OVERLAY_REMOVE_ARROW = {"top_left": 30756, "top_right": 30758,
                              "bottom_left": 30760, "bottom_right": 30762}
PRINT_OVERLAY_TOP_LAYOUT_SINGLE = 30859
PRINT_OVERLAY_BOTTOM_LAYOUT_SINGLE = 30869
PRINT_OVERLAY_NAME_EDIT = 30190
PRINT_OVERLAY_ADD_BUTTON = 30440
PRINT_OVERLAY_SCP_LIST_ID = 31158

# 6개, 4개 구역에 고르게 분배 — 사양서 예시(`(TC) R-20-643...` Upgrade 시트
# 105행 "Print Overlay" 실제 TC)에 나오는 항목 풀에서 뽑았다(사용자 지시,
# 2026-08-21: "대표적인 것들을 TC 등을 참고해서 6개 정도"). 처음에는
# Institutional Name을 bottom_right에 넣었으나 이 시험 데이터의 Institution
# Name 값이 비어 있어 필름에 아무것도 그려지지 않았다(실측) — 사용자 지시로
# 항상 값이 채워지는 Dose mAs로 바꿨다("Institution Name 말고 Dose mAs로
# 바꿔주라 그럼 잘 나올꺼야").
PRINT_OVERLAY_DEFAULT_ITEMS = [
    ("Dose kVp", "top_left"),
    ("Exposure Index", "top_left"),
    ("Exposure Date", "top_right"),
    ("Accession Number", "bottom_left"),
    ("Performing Physician", "bottom_left"),
    ("Dose mAs", "bottom_right"),
]
# 필름 OCR 판정에 쓰는 것 — 라벨이 뚜렷해 OCR로 확실히 대조할 수 있는 것만
# 쓴다. Dose kVp/Dose mAs는 라벨 없이 맨값("50", "1")만 그려져(실측) 다른
# 곳의 숫자와 혼동될 수 있어 판정 문자열로는 쓰지 않는다 — 레이아웃에는
# 남겨 두되(6개 항목 배치 확인 목적) 자동 판정은 이 4개로 좁힌다.
PRINT_OVERLAY_CHECK_TEXTS = ("E.I.", "DOI", "Acc. No", "Performing Physician")

DICOM_PRINT_SCP_LIST_ID = 31133
DICOM_PRINT_NAME_EDIT = 30090
DICOM_PRINT_OVERLAY_COMBO_ID = 30942
DICOM_PRINT_OVERLAY_COMBO_Y = 496


def _tess_ready():
    import pytesseract
    exe = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
    return pytesseract


def _ocr_row_text(row_ctrl, scale=3):
    from PIL import ImageGrab
    pytesseract = _tess_ready()
    img = ImageGrab.grab(bbox=row_ctrl.rect, all_screens=True)
    big = img.resize((img.width * scale, img.height * scale))
    return pytesseract.image_to_string(big).strip()


def _overlay_norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _overlay_row_has(item_name, row_text):
    """목록 행의 OCR 텍스트가 `item_name` 항목을 가리키는지.

    **잘린 라벨을 인정하는 것이 핵심이다.** 이 화면의 목록은 칸 폭에 맞춰
    라벨을 말줄임표로 잘라 그린다(실측 2026-08-21: `Accession Number` →
    `Accession Num...`, `Performing Physician` → `Performing Ph...`). 그래서
    "항목명이 행 텍스트 안에 들어 있는가"만 보면 **화면에 항목이 실제로 있는데도
    없다고 판정한다** — 2026-08-21 TC07 Step 4가 MANUAL로 떨어지고, 이미 배치된
    항목을 매번 다시 추가하려 들다 엉뚱한 항목(`Exposure Time`)이 끼어든 원인이
    바로 이것이었다. 그래서 방향을 뒤집어 **행 텍스트가 항목명의 앞부분인
    경우**도 같은 항목으로 본다.

    잘린 조각이 짧으면 다른 항목과 우연히 겹칠 수 있으므로(`Exposure...`는
    Date/Index/Time 셋 다의 앞부분이다) 4글자 미만 조각은 근거로 쓰지 않는다.
    그 이상이어도 같은 접두를 가진 항목을 함께 계획에 넣으면 구분되지 않는다 —
    현재 계획(`PRINT_OVERLAY_DEFAULT_ITEMS`)에는 그런 쌍이 없고, 실측 화면에서
    잘려 보이는 항목은 `Accession Num...`/`Performing Ph...` 둘뿐이다.
    """
    a = _overlay_norm(item_name)
    b = _overlay_norm(row_text)
    if not a or not b:
        return False
    if a in b:
        return True
    return len(b) >= 4 and a.startswith(b)


def _overlay_slot_has(item_name, row_texts):
    return any(_overlay_row_has(item_name, t) for t in (row_texts or []))


def print_overlay_slot_rows(ui, slot):
    from . import setting as S
    lc = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_SLOT_LIST[slot]][0]
    return S.list_rows(ui, lc)


def _print_overlay_move_selected(ui, slot, settle=0.8):
    from . import setting as S
    arrow = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_ADD_ARROW[slot]][0]
    ui.click(arrow, settle=settle)


def _print_overlay_remove_selected(ui, slot, settle=0.8):
    from . import setting as S
    arrow = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_REMOVE_ARROW[slot]][0]
    ui.click(arrow, settle=settle)


def _ocr_lines_with_rows(rows, scale=3):
    """행 목록 영역을 한 번에 OCR해 `[(줄 텍스트, 그 줄이 놓인 행)]`을 돌려준다.

    **줄 번호와 행 번호를 인덱스로 맞추지 않는다.** 이전 구현은 OCR이 돌려준
    n번째 줄이 n번째 행이라고 가정했는데, 빈 줄이 하나 끼거나 두 줄이 합쳐지면
    그 뒤가 전부 한 칸씩 밀려 **엉뚱한 행을 클릭한다**(실측 2026-08-21: 계획에
    없던 `Exposure Time`이 Bottom Left에 들어갔다). 그래서 단어 단위 좌표
    (`image_to_data`)로 각 줄의 화면상 y 중심을 구하고, 그 y를 품는 행을
    rect로 찾아 짝지운다 — CLAUDE.md 3절의 "좌표를 저장해 재사용하지 않고,
    방금 찾은 컨트롤의 실제 rect에서 계산한다"와 같은 방식이다.
    """
    from PIL import ImageGrab
    pytesseract = _tess_ready()
    if not rows:
        return [], None
    x1 = min(r.rect[0] for r in rows); y1 = min(r.rect[1] for r in rows)
    x2 = max(r.rect[2] for r in rows); y2 = max(r.rect[3] for r in rows)
    img = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
    big = img.resize((img.width * scale, img.height * scale))
    data = pytesseract.image_to_data(big, output_type=pytesseract.Output.DICT)
    groups = {}
    for i, word in enumerate(data.get("text", [])):
        if not (word or "").strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        g = groups.setdefault(key, {"words": [], "top": [], "bottom": []})
        g["words"].append(word.strip())
        g["top"].append(data["top"][i])
        g["bottom"].append(data["top"][i] + data["height"][i])
    out = []
    for g in groups.values():
        text = " ".join(g["words"])
        y_mid = y1 + (min(g["top"]) + max(g["bottom"])) / 2.0 / scale
        row = next((r for r in rows if r.rect[1] <= y_mid <= r.rect[3]), None)
        if row is not None:
            out.append((text, row))
    out.sort(key=lambda p: p[1].rect[1])
    return out, img


def _print_overlay_add_items(ui, ordered_targets, max_scrolls=14):
    """(항목명, 구역) 목록을 마스터 Item 목록(`31163`)에서 찾아 옮긴다.

    목록이 위→아래 고정 순서라 매 항목마다 맨 위로 되돌아가지 않고, 스크롤을
    계속 내려가는 **단일 패스**로 찾는다(맨 위부터 매번 다시 훑으면 항목당
    약 15초, 6개면 1.5분 — 실측으로 느려서 바꿨다). 목록 전체를 한 번에
    OCR하되 줄과 행은 `_ocr_lines_with_rows()`로 **좌표로** 짝짓는다.

    반환: {항목명: 옮김 성공 여부}
    """
    from . import setting as S
    remaining = list(ordered_targets)
    done = {}
    item_list = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_ITEM_LIST_ID][0]
    S.scroll_list_to_top(ui, item_list)
    seen_sigs = set()
    for _ in range(max_scrolls):
        if not remaining:
            break
        item_list = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_ITEM_LIST_ID][0]
        rows = S.list_rows(ui, item_list)
        if not rows:
            break
        pairs, img = _ocr_lines_with_rows(rows)
        if img is None:
            break
        sig = hash(img.tobytes())
        if sig in seen_sigs:
            break
        seen_sigs.add(sig)
        still = []
        for target, slot in remaining:
            matched_row = next((row for text, row in pairs
                                if _overlay_row_has(target, text)), None)
            if matched_row is not None:
                ui.click(S.row_click_point(ui, matched_row), settle=0.4)
                _print_overlay_move_selected(ui, slot)
                time.sleep(0.4)
                done[target] = True
            else:
                still.append((target, slot))
        remaining = still
        if remaining:
            item_list = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_ITEM_LIST_ID][0]
            S.scroll_list(ui, item_list, notches=-3, settle=0.25)
    for target, _slot in remaining:
        done[target] = False
    return done


def _print_overlay_strip_extras(ui, items_plan, max_removals=12):
    """계획에 없는 항목을 각 구역에서 빼낸다.

    필름에 그려지는 내용을 계획과 정확히 일치시키기 위한 것이다 — 남아 있으면
    이전 실행의 잔재가 그대로 인쇄돼 Step 9의 판정 근거가 흐려진다(실측
    2026-08-21: 잘못 끼어든 `Exposure Time`이 필름에 `TOI : 12:58:34`로
    그려졌다). 이 프로파일은 자동화가 만들고 관리하는 것이므로(SCP 이름과 같은
    이름) 계획 외 항목을 제거해도 사용자가 손으로 만든 설정을 건드리지 않는다.

    반환: {구역: [빼낸 항목 텍스트]}
    """
    from . import setting as S
    removed = {}
    for slot in PRINT_OVERLAY_SLOT_LIST:
        planned = [name for name, s in items_plan if s == slot]
        for _ in range(max_removals):             # 무한 루프 방지 상한
            extra = None
            for row in print_overlay_slot_rows(ui, slot):
                text = _ocr_row_text(row)
                if not any(_overlay_row_has(name, text) for name in planned):
                    extra = (row, text)
                    break
            if extra is None:
                break
            ui.click(S.row_click_point(ui, extra[0]), settle=0.4)
            _print_overlay_remove_selected(ui, slot)
            removed.setdefault(slot, []).append(extra[1] or "(빈 텍스트)")
    return removed


def ensure_print_overlay_profile(ui, cfg, scp_name, items_plan=None, evidence_dir=None):
    """`Setting > DICOM - Print Overlay`에 `scp_name`과 같은 이름의 프로파일을
    보장하고, 4개 구역(Top Left/Right, Bottom Left/Right)에 `items_plan`
    항목이 이미 배치돼 있으면 건드리지 않고, 없으면 배치한 뒤 Update한다.
    계획에 없는 항목이 섞여 있으면 빼낸다(`_print_overlay_strip_extras`).

    반환: {"ok", "created", "items_before", "items_after", "removed", "note"}
    """
    from . import setting as S
    items_plan = items_plan or PRINT_OVERLAY_DEFAULT_ITEMS
    if S.goto_screen(ui, "DICOM - Print Overlay") is None:
        return {"ok": False, "note": "DICOM - Print Overlay 화면을 찾지 못했다."}

    rows = S.list_rows(ui, [c for c in S.content_controls(ui)
                            if c.ctrl_id == PRINT_OVERLAY_SCP_LIST_ID][0])
    target_row = None
    for row in rows:
        ui.click(S.row_click_point(ui, row), settle=0.6)
        name_edit = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_NAME_EDIT][0]
        if (ui.get_text(name_edit) or "").strip() == scp_name:
            target_row = row
            break
    created = False
    if target_row is None:
        add_btn = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_ADD_BUTTON][0]
        ui.click(add_btn, settle=1.2)
        name_edit = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_NAME_EDIT][0]
        ui.type_text(name_edit, scp_name, settle=0.3)
        created = True

    before = dict((slot, [_ocr_row_text(r) for r in print_overlay_slot_rows(ui, slot)])
                 for slot in PRINT_OVERLAY_SLOT_LIST)
    planned_ok = all(_overlay_slot_has(name, before.get(slot, []))
                     for name, slot in items_plan)
    extras_exist = any(
        not any(_overlay_row_has(name, t) for name, s in items_plan if s == slot)
        for slot in PRINT_OVERLAY_SLOT_LIST for t in before.get(slot, []))
    if planned_ok and not extras_exist and not created:
        return {"ok": True, "created": False, "items_before": before, "items_after": before,
                "removed": {},
                "note": "프로파일 '%s'에 계획한 %d개 항목만 이미 배치돼 있어 건드리지 않았다."
                        % (scp_name, len(items_plan))}

    top_layout = [c for c in S.content_controls(ui) if c.ctrl_id == PRINT_OVERLAY_TOP_LAYOUT_SINGLE][0]
    ui.click(top_layout, settle=0.8)
    bottom_layout = [c for c in S.content_controls(ui)
                     if c.ctrl_id == PRINT_OVERLAY_BOTTOM_LAYOUT_SINGLE][0]
    ui.click(bottom_layout, settle=0.8)

    removed = _print_overlay_strip_extras(ui, items_plan)
    missing = [(name, slot) for name, slot in items_plan
              if not _overlay_slot_has(name, before.get(slot, []))]
    added = _print_overlay_add_items(ui, missing) if missing else {}

    after = dict((slot, [_ocr_row_text(r) for r in print_overlay_slot_rows(ui, slot)])
                for slot in PRINT_OVERLAY_SLOT_LIST)
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        try:
            from . import setting as S2
            from PIL import ImageGrab
            dlg = S2.content_dialog(ui)
            ImageGrab.grab(bbox=dlg.rect, all_screens=True).save(
                os.path.join(evidence_dir, "print_overlay_profile.png"))
        except Exception:                                    # noqa: BLE001
            pass

    ack = S.update(ui, ack_timeout=8)
    ok = all(_overlay_slot_has(name, after.get(slot, []))
             for name, slot in items_plan)
    return {"ok": ok, "created": created, "items_before": before, "items_after": after,
            "added": added, "removed": removed, "update_ack": ack,
            "note": "프로파일 '%s' %s / 배치=%s / 제거=%s / Update: %s"
                   % (scp_name, "새로 생성" if created else "기존 재사용",
                      ", ".join("%s:%s" % (k, "OK" if v else "실패")
                                for k, v in added.items()) or "없음(이미 배치됨)",
                      ", ".join("%s:%s" % (k, v) for k, v in removed.items()) or "없음",
                      ack or "(문구 없음)")}


def link_print_overlay_to_scp(ui, cfg, scp_name, overlay_name):
    """`Setting > DICOM - Print`에서 `scp_name` SCP를 선택해 Overlay 콤보를
    `overlay_name`으로 지정하고 Update한다. 이미 그 값이면 건드리지 않는다.

    실측(2026-08-21, 사용자 제보): Print Overlay 화면에서 프로파일을 만들고
    Update만 해서는 실제 인쇄물에 반영되지 않는다 — 이 화면의 Overlay 콤보로
    SCP와 프로파일을 명시적으로 연결해야 한다.

    반환: {"ok", "already", "note"}
    """
    from . import setting as S
    from .ui import children
    if S.goto_screen(ui, "DICOM - Print") is None:
        return {"ok": False, "note": "DICOM - Print 화면을 찾지 못했다."}

    rows = S.list_rows(ui, [c for c in S.content_controls(ui)
                            if c.ctrl_id == DICOM_PRINT_SCP_LIST_ID][0])
    matched = None
    for row in rows:
        ui.click(S.row_click_point(ui, row), settle=0.6)
        name_edit = [c for c in S.content_controls(ui) if c.ctrl_id == DICOM_PRINT_NAME_EDIT][0]
        if (ui.get_text(name_edit) or "").strip() == scp_name:
            matched = row
            break
    if matched is None:
        return {"ok": False, "note": "SCP 목록에서 '%s'를 찾지 못했다." % scp_name}

    combo = next((c for c in S.content_controls(ui)
                 if c.ctrl_id == DICOM_PRINT_OVERLAY_COMBO_ID
                 and c.rect[1] == DICOM_PRINT_OVERLAY_COMBO_Y), None)
    if combo is None:
        return {"ok": False, "note": "Overlay 콤보(%d)를 찾지 못했다." % DICOM_PRINT_OVERLAY_COMBO_ID}
    current = (combo.text or "").strip()
    if current == overlay_name or current == overlay_name[:len(current)]:
        # 콤보 텍스트가 폭에 맞춰 잘려 표시될 수 있어(실측 'PRINT_SC') 접두 일치도 인정한다.
        if overlay_name.startswith(current) and len(current) >= 6:
            return {"ok": True, "already": True,
                    "note": "Overlay 콤보가 이미 '%s'로 연결되어 있었다." % current}

    arrow = next((c for c in children(combo.hwnd, 2) if c.ctrl_id == 1), None)
    if arrow is None:
        return {"ok": False, "note": "Overlay 콤보의 드롭다운 화살표를 찾지 못했다."}
    ui.click(arrow, settle=0.8)

    from PIL import ImageGrab
    pytesseract = _tess_ready()
    region = (combo.rect[0], combo.rect[1], combo.rect[2], combo.rect[1] + 150)
    img = ImageGrab.grab(bbox=region, all_screens=True)
    big = img.resize((img.width * 3, img.height * 3))
    data = pytesseract.image_to_data(big, output_type=pytesseract.Output.DICT)
    point = None
    for i, txt in enumerate(data.get("text", [])):
        if txt.strip() == overlay_name:
            cx = region[0] + (data["left"][i] + data["width"][i] / 2) / 3
            cy = region[1] + (data["top"][i] + data["height"][i] / 2) / 3
            point = (cx, cy)
            break
    if point is None:
        ui.key("ESC", settle=0.3)
        return {"ok": False, "note": "드롭다운에서 '%s' 항목을 OCR로 찾지 못했다." % overlay_name}
    ui.click(point, settle=1.0)
    ack = S.update(ui, ack_timeout=8)
    return {"ok": True, "already": False,
            "note": "Overlay 콤보를 '%s'로 연결. Update: %s" % (overlay_name, ack or "(문구 없음)")}


def db_button(ui, name, settle=2.5):
    """Database 화면의 버튼을 누른다."""
    if name not in DB_BUTTON:
        raise WorkflowError("알 수 없는 Database 버튼: %s" % name)
    hits = by_id(ui, DB_BUTTON[name])
    if not hits:
        raise WorkflowError("Database %s 버튼(%d)을 찾지 못했습니다."
                            % (name, DB_BUTTON[name]))
    ui.click(hits[0], settle=settle)
    return True


_RESULT_COUNT_RX = re.compile(r"Result:\s*(\d+)\s*/\s*(\d+)")


def _result_total(summary):
    m = _RESULT_COUNT_RX.search(summary or "")
    return int(m.group(2)) if m else 0


def select_search_preset(ui, which="clear", settle=1.0, timeout=6):
    """검색 조건 프리셋 스플릿 버튼(`30935`)에서 Default/Clear를 고른다.

    사용자 지시(2026-08-21): *"검색할 때 default를 clear로 바꾸고 search를 누르게
    해줘."* `Clear`는 조회 조건(날짜 범위 등)을 비워 **전체 범위로 조회**하게
    한다 — Import로 들어온 스터디처럼 검사일이 오늘이 아닐 수 있는 건을 날짜
    필터가 걸러 버리는 것을 막는다. Clear는 결과 목록도 비우므로 **반드시 그
    뒤에 Search를 눌러야** 한다(실측 2026-08-21).

    항목 창은 제목이 `ItemList`인 별도 최상위 창이라 제목이 아니라 **그 안에
    목표 항목 ID가 있는지**로 창을 확정한다(CLAUDE.md 속성 우선 원칙).

    반환: {"ok", "which", "note"}
    """
    from .ui import children, top_windows
    if which not in REG_PRESET:
        raise WorkflowError("알 수 없는 검색 프리셋: %s" % which)
    want = REG_PRESET[which]
    splits = [c for c in by_id(ui, REG_DEFAULT_BUTTON) if c.visible]
    if not splits:
        return {"ok": False, "which": which,
                "note": "프리셋 스플릿 버튼(%d)을 찾지 못했다." % REG_DEFAULT_BUTTON}
    arrow = next((c for c in children(splits[0].hwnd, 3)
                  if c.ctrl_id == REG_PRESET_ARROW_CHILD and c.visible), None)
    if arrow is None:
        return {"ok": False, "which": which,
                "note": "프리셋 드롭다운 화살표(자식 %d)를 찾지 못했다."
                        % REG_PRESET_ARROW_CHILD}
    ui.click(arrow, settle=settle)

    end = time.time() + timeout
    item = None
    while time.time() < end:
        for win in top_windows(ui.pid):
            hit = [c for c in children(win.hwnd, 3)
                   if c.ctrl_id == want and c.visible]
            if hit:
                item = hit[0]
                break
        if item is not None:
            break
        time.sleep(0.3)
    if item is None:
        ui.raw_key(0x1B, settle=0.3)          # 열린 메뉴는 닫아 둔다
        return {"ok": False, "which": which,
                "note": "프리셋 항목(%d, %s)이 %d초 안에 나타나지 않았다."
                        % (want, which, timeout)}
    ui.click(item, settle=settle)
    return {"ok": True, "which": which,
            "note": "검색 프리셋을 '%s'(%d)로 지정했다." % (which, want)}


def database_search(ui, settle=3.0, retries=4, retry_wait=3.0, preset="clear"):
    """Database 화면에서 조회를 실행하고 요약 문구를 돌려준다.

    Search 버튼은 Registration과 같은 ID(`30689`)다(실측). 검사를 Close한 직후에는
    목록이 자동으로 갱신되지 않아 `Result: 0 / 0`이 남아 있다 — 조회하지 않으면
    "촬영했는데 Database에 없다"는 잘못된 판정이 난다.

    **한 번 조회해도 비어 있을 수 있다**(실측 2026-08-21: TC02가 Close 직후 조회한
    결과는 `Result: 0 / 0`이었는데, 같은 스터디를 몇 분 뒤 다시 열면 `6 / 6`으로
    정상 표시됐다 — 제품 내부 인덱싱이 Close보다 늦게 끝나는 지연으로 보인다).
    그래서 결과가 비어 있으면 Search를 다시 눌러 재시도한다. 그래도 계속 비어
    있으면 그 자체가 판정 대상이므로 무한 재시도하지 않고 마지막 결과를 그대로
    반환한다.
    """
    goto(ui, "database")
    time.sleep(1.0)
    if preset:
        select_search_preset(ui, preset)
    hits = by_id(ui, REG_SEARCH_BUTTON)
    summary = ""
    for attempt in range(max(1, retries)):
        if hits:
            ui.click(hits[0], settle=settle)
        time.sleep(1.0)
        summary = result_summary(ui)
        if _result_total(summary) > 0:
            break
        if attempt < retries - 1:
            time.sleep(retry_wait)
    return summary


# --- Database > Import (Import Study 창) ------------------------------
# 실측 2026-08-21 (TC08 Step 2 "Export된 스터디를 뷰어로 import한다" 자동화).
#
# 이 창을 찾는 방법이 특별하다 — **제목이 빈 최상위 팝업**이다. 제목("Import
# Study")을 owner-draw로 그리기 때문에 (1) 메인 윈도우의 자식 트리에 없고
# (2) 제목으로 창을 거를 수도 없다. 그래서 `core.ui.top_windows()`로 프로세스의
# 최상위 창을 훑어 **필요한 컨트롤 ID를 모두 가진 창**을 이 창으로 확정한다
# (CLAUDE.md 3절 속성 우선 원칙 — 좌표나 제목에 기대지 않는다). 이걸 몰라서
# 메인 창 자식 트리와 "제목 있는 창"만 뒤지다 두 번 헛돌았다.
#
# | 컨트롤 | ID | 확인 |
# |---|---|---|
# | Location Edit | `30116` | 표시 전용 — **타이핑이 들어가지 않는다**(실측) |
# | Browse `...` | `30515` | 표준 `SHBrowseForFolder`("폴더 찾아보기")를 띄운다 |
# | 스터디 목록 | `31118` | Patient Name/ID/Acc. No./Birth Date/Age/Sex/Study Date Time |
# | Import | `30685` | 누르면 범위 확인 팝업(Print/Export와 같은 27002/27001/27000) |
# | Close | `30467` | |
#
# 경로 지정은 `...`밖에 없다. Location Edit에 `type_text()`로 써 넣어도 값이
# 그대로였다(Export Manager의 경로 Edit과 같은 성질). 그 트리를 OCR로 읽으면
# 한글 노드가 깨지고 영문도 `VXvue1 (E:)` → `VXvuel (E)`로 읽혀 **엉뚱한
# 노드(`VXvue1.0.11.015(SMZ)`)를 선택하는 사고가 실제로 났다.** 그래서
# `core/shelltree.py`로 `TVM_*` 메시지를 보내 노드 라벨을 정확히 읽는다.
#
# 성공 근거는 셋을 함께 본다(실측 확인):
#  1. Import 후 `Info` 팝업 문구 `Succeed to import the studies.`
#  2. 목록 각 열의 값이 Export한 정보와 일치 (`core/listgrid.py`, 사용자 지시)
#  3. Database 조회 건수 증가 (32 → 33)
IMPORT_LOCATION_EDIT = 30116
IMPORT_BROWSE_BUTTON = 30515
IMPORT_STUDY_LIST = 31118
IMPORT_START_BUTTON = 30685
IMPORT_CLOSE_BUTTON = 30467
IMPORT_INFO_OK = 27000
IMPORT_DIALOG_IDS = (IMPORT_LOCATION_EDIT, IMPORT_BROWSE_BUTTON, IMPORT_STUDY_LIST)
IMPORT_SUCCESS_WORDS = ("succeed", "success")
# 진행 표시 팝업은 **결과가 아니다.** 실측 2026-08-21: Import를 누르면
# `Importing files 1/1 ...` 팝업이 먼저 뜨고, 그것이 사라진 뒤에야
# `Info: Succeed to import the studies.`가 뜬다. 앞의 것을 결과로 읽어
# TC08 Step 10이 잘못 FAIL 났다(Result_20260821_145739).
IMPORT_PROGRESS_WORDS = ("importing", "please wait", "progress")
IMPORT_FAILURE_WORDS = ("fail", "error", "cannot", "unable")
BROWSE_DIALOG_TITLE = "폴더 찾아보기"
BROWSE_TREE_CLASS = "SysTreeView32"
BROWSE_OK_ID = 1
BROWSE_CANCEL_ID = 2


def find_import_dialog(ui, timeout=20, poll=0.5):
    """Import Study 창을 **컨트롤 구성으로** 찾는다(제목·좌표에 의존하지 않음)."""
    from .ui import children, top_windows
    end = time.time() + timeout
    while True:
        for win in top_windows(ui.pid):
            ids = {c.ctrl_id for c in children(win.hwnd, 4)}
            if all(n in ids for n in IMPORT_DIALOG_IDS):
                return win
        if time.time() >= end:
            return None
        time.sleep(poll)


def _in_dialog(dlg, ctrl_id):
    from .ui import children
    return [c for c in children(dlg.hwnd, 4)
            if c.ctrl_id == ctrl_id and c.visible]


def import_dialog_rows(dlg):
    """Import Study 목록의 실제 행(`ListItem`)."""
    from .ui import children
    out = []
    for lc in _in_dialog(dlg, IMPORT_STUDY_LIST):
        for c in children(lc.hwnd, 3):
            if c.text.strip() == "ListItem" and c.visible:
                out.append(c)
    return sorted(out, key=lambda c: c.rect[1])


def _find_drive_node(tree, letter, shallow_timeout=2.0):
    """`(X:)`로 끝나는 트리 노드를 찾는다.

    이동식 드라이브는 바탕 화면 루트에 바로 보이지만(실측: `VXvue1 (E:)`),
    내장 드라이브는 `내 PC` 아래에 있다. 로케일에 따라 그 노드 이름이 달라지므로
    이름을 가정하지 않고 **루트 → 루트의 자식 한 단계**까지만 훑는다.
    """
    tag = "(%s:)" % letter.rstrip(":").upper()
    root = tree.root()
    tree.expand_and_wait(root)
    hit, label = tree.find_child(root, lambda s: s.upper().endswith(tag))
    if hit:
        return hit, [label]
    for hitem, label in tree.children(root):
        if not tree.expand_and_wait(hitem, timeout=shallow_timeout):
            continue
        sub, sublabel = tree.find_child(hitem, lambda s: s.upper().endswith(tag))
        if sub:
            return sub, [label, sublabel]
    return None, []


def set_import_location(ui, dlg, dest, timeout=20):
    """Import Study의 Location을 `dest` 폴더로 맞춘다.

    반환: {"ok", "already", "location", "trail", "note"}
    """
    from .shelltree import ShellTree
    from .ui import children, top_windows

    edits = _in_dialog(dlg, IMPORT_LOCATION_EDIT)
    current = (ui.get_text(edits[0]) if edits else "") or ""
    want = os.path.normcase(os.path.normpath(dest))
    if current and os.path.normcase(os.path.normpath(current)) == want:
        return {"ok": True, "already": True, "location": current, "trail": [],
                "note": "Location이 이미 %s였다(건드리지 않음)." % current}

    btns = _in_dialog(dlg, IMPORT_BROWSE_BUTTON)
    if not btns:
        return {"ok": False, "already": False, "location": current, "trail": [],
                "note": "Browse 버튼(%d)을 찾지 못했다." % IMPORT_BROWSE_BUTTON}
    ui.click(btns[0], settle=1.5)

    end = time.time() + timeout
    browse = None
    while time.time() < end:
        browse = next((w for w in top_windows(ui.pid)
                       if (w.text or "").strip() == BROWSE_DIALOG_TITLE), None)
        if browse is not None:
            break
        time.sleep(0.4)
    if browse is None:
        return {"ok": False, "already": False, "location": current, "trail": [],
                "note": "'%s' 창이 %d초 안에 뜨지 않았다."
                        % (BROWSE_DIALOG_TITLE, timeout)}

    def _cancel_browse():
        hit = [c for c in children(browse.hwnd, 4)
               if c.ctrl_id == BROWSE_CANCEL_ID and c.visible]
        if hit:
            ui.click(hit[0], settle=0.8)

    tree_ctrl = next((c for c in children(browse.hwnd, 6)
                      if c.cls == BROWSE_TREE_CLASS and c.visible), None)
    if tree_ctrl is None:
        _cancel_browse()
        return {"ok": False, "already": False, "location": current, "trail": [],
                "note": "폴더 트리(%s)를 찾지 못했다." % BROWSE_TREE_CLASS}

    drive, tail = os.path.splitdrive(os.path.normpath(dest))
    parts = [p for p in tail.split(os.sep) if p]
    with ShellTree(tree_ctrl.hwnd) as tree:
        node, trail = _find_drive_node(tree, drive or dest[:2])
        if node is None:
            _cancel_browse()
            return {"ok": False, "already": False, "location": current,
                    "trail": trail,
                    "note": "트리에서 드라이브 %s 노드를 찾지 못했다." % drive}
        for part in parts:
            want_label = part.strip().casefold()
            found = label = None
            if tree.expand_and_wait(node):
                found, label = tree.find_child(
                    node, lambda s, w=want_label: s.strip().casefold() == w)
            if found is None:
                _cancel_browse()
                return {"ok": False, "already": False, "location": current,
                        "trail": trail,
                        "note": ("트리에서 '%s' 폴더를 찾지 못했다(지나온 경로 %s). "
                                 "없는 폴더를 새로 만들지 않는다." % (part, trail))}
            trail.append(label)
            node = found
        tree.select(node)

    ok_btn = next((c for c in children(browse.hwnd, 4)
                   if c.ctrl_id == BROWSE_OK_ID and c.visible), None)
    if ok_btn is None:
        _cancel_browse()
        return {"ok": False, "already": False, "location": current, "trail": trail,
                "note": "폴더 찾아보기의 확인 버튼을 찾지 못했다."}
    ui.click(ok_btn, settle=1.5)

    end = time.time() + timeout
    now = current
    while time.time() < end:
        edits = _in_dialog(dlg, IMPORT_LOCATION_EDIT)
        now = (ui.get_text(edits[0]) if edits else "") or ""
        if now and os.path.normcase(os.path.normpath(now)) == want:
            break
        time.sleep(0.4)
    ok = bool(now) and os.path.normcase(os.path.normpath(now)) == want
    return {"ok": ok, "already": False, "location": now, "trail": trail,
            "note": "트리 경로 %s → Location=%r" % (trail, now)}


def _close_import_dialog(ui, dlg, attempts=3, timeout=8):
    """Close(30467)로 창을 닫고 **정말 닫혔는지 확인한다.**

    사용자 제보(2026-08-21): *"import 후 실제 close 할 때도 (Close) 버튼을 눌러
    close 하면 database 탭에서 다시 검색하면 검색이 될 거야."* — 창을 닫은 뒤
    **Database에서 다시 조회해야** 들어온 스터디가 목록에 보인다.

    그리고 같은 날 또 하나: *"지금 import study 창이 켜져 있어서 네가 클릭한 다른
    버튼들이 다 먹히지 않았어. 임포트가 성공하면 일단 이 창을 닫아야지."* 실제로
    그 사고가 났다(Result_20260821_145739) — 이 창이 모달로 남아 있는 동안 Close와
    Database 조회 클릭이 조용히 무시돼서 "건수 70 → 70"이라는 **의미 없는 판정
    근거**가 리포트에 남았다. 그래서 여기서는 눌러 보고 끝내지 않고 **창이 사라진
    것을 확인**하며, 안 닫히면 제목줄 닫기(`-4`)까지 시도한다.

    반환: True면 창이 사라진 것을 확인했다.
    """
    for attempt in range(attempts):
        target = IMPORT_CLOSE_BUTTON if attempt < attempts - 1 else DIALOG_CLOSE_X
        btns = _in_dialog(dlg, target)
        if btns:
            ui.click(btns[0], settle=1.2)
        end = time.time() + timeout
        while time.time() < end:
            if find_import_dialog(ui, timeout=0) is None:
                return True
            time.sleep(0.5)
    return find_import_dialog(ui, timeout=0) is None


def _shot_rect(ctrl, evidence_dir, name):
    try:
        from PIL import ImageGrab
        os.makedirs(evidence_dir, exist_ok=True)
        ImageGrab.grab(bbox=ctrl.rect, all_screens=True).save(
            os.path.join(evidence_dir, name))
        return True
    except Exception:                                     # noqa: BLE001
        return False


def import_studies(ui, cfg, dest, expected=None, scope="selected",
                   evidence_dir=None, settle=2.0, info_timeout=90):
    """Database > Import로 `dest` 폴더의 스터디를 되읽는다.

    `expected`가 있으면 Import Study 목록의 **각 열 값을 그 기대값과 대조**한다
    (`core/listgrid.compare_row`, 사용자 지시 2026-08-21: "각 열의 정보가 export
    한 정보와 동일하게 나오면 될 것 같은데"). 열이 좁아 값이 잘려 보이면 그 열의
    경계선을 드래그해 넓혀 읽고 원래 폭으로 되돌린다.

    반환: {"ok", "location", "rows", "row_values", "match", "scope_clicked",
           "info", "db_before", "db_after", "note"}
    """
    from . import dialogs as D
    from .listgrid import ListGrid, compare_row
    from .ui import children

    out = {"ok": False, "location": None, "rows": 0, "row_values": None,
           "match": None, "scope_clicked": None, "info": "", "progress": [],
           "closed": False, "db_before": None, "db_after": None, "note": ""}

    out["db_before"] = _result_total(database_search(ui))

    db_button(ui, "import", settle=3.0)
    dlg = find_import_dialog(ui)
    if dlg is None:
        out["note"] = ("Import Study 창을 찾지 못했다(필요 컨트롤 %s를 모두 가진 "
                       "최상위 창 없음)." % (IMPORT_DIALOG_IDS,))
        return out

    loc = set_import_location(ui, dlg, dest)
    out["location"] = loc.get("location")
    if not loc.get("ok"):
        out["note"] = "Location 지정 실패: %s" % loc.get("note")
        out["closed"] = _close_import_dialog(ui, dlg)
        return out

    rows = []
    end = time.time() + 20
    while time.time() < end:
        rows = import_dialog_rows(dlg)
        if rows:
            break
        time.sleep(0.5)
    out["rows"] = len(rows)
    if not rows:
        out["note"] = ("Location=%s 에서 가져올 스터디를 찾지 못했다. VXvue는 "
                       "**자기 IMG 형식만** 가져올 수 있다(Operation Manual 8.14) "
                       "— Export 산출물에 IMG가 있는지 먼저 볼 것." % out["location"])
        out["closed"] = _close_import_dialog(ui, dlg)
        return out

    # --- 목록 각 열을 읽어 Export 정보와 대조 --------------------------
    target = rows[0]
    grid = None
    lcs = _in_dialog(dlg, IMPORT_STUDY_LIST)
    if lcs:
        try:
            grid = ListGrid(ui, lcs[0])
        except Exception as exc:                          # noqa: BLE001
            out["note"] = "목록 헤더를 읽지 못했다: %s" % exc
    if grid is not None:
        want_cols = set((expected or {}).keys()) or None
        values = grid.read_row(target, widen=True, want=want_cols)
        out["row_values"] = dict(values)
        if expected:
            out["match"] = compare_row(values, expected)
            # 행이 여럿이면 기대값과 맞는 행을 찾아 고른다.
            if not out["match"]["ok"] and len(rows) > 1:
                cols = grid.columns()
                for row in rows[1:]:
                    vals = grid.read_row(row, columns=cols, widen=True,
                                         want=want_cols)
                    cmp2 = compare_row(vals, expected)
                    if cmp2["ok"]:
                        target, out["row_values"], out["match"] = row, dict(vals), cmp2
                        break

    ui.click((target.rect[0] + 60,
              (target.rect[1] + target.rect[3]) // 2), settle=0.8)
    if evidence_dir:
        _shot_rect(dlg, evidence_dir, "import_dialog.png")

    start = _in_dialog(dlg, IMPORT_START_BUTTON)
    if not start:
        out["note"] = "Import 버튼(%d)을 찾지 못했다." % IMPORT_START_BUTTON
        out["closed"] = _close_import_dialog(ui, dlg)
        return out
    ui.click(start[0], settle=settle)

    scope_res = confirm_scope_popup(ui, scope=scope)
    out["scope_clicked"] = scope_res.get("clicked")

    info_text, progress_seen = "", []
    end = time.time() + info_timeout
    while time.time() < end:
        d = ui.dialog()
        if d is None:
            time.sleep(0.5)
            continue
        info = D.read(ui, d, cfg)
        text = ("%s: %s" % (info.get("title"),
                            info.get("message"))).strip(": ")
        low = text.lower()
        terminal = any(w in low for w in
                       IMPORT_SUCCESS_WORDS + IMPORT_FAILURE_WORDS)
        if not terminal and any(w in low for w in IMPORT_PROGRESS_WORDS):
            # 진행 표시다 — 닫지 않고 사라질 때까지 기다린다.
            if text not in progress_seen:
                progress_seen.append(text)
            time.sleep(1.0)
            continue
        info_text = text
        if evidence_dir:
            _shot_rect(d, evidence_dir, "import_result_popup.png")
        ok_btn = [c for c in children(d.hwnd, 3)
                  if c.ctrl_id == IMPORT_INFO_OK]
        if ok_btn:
            ui.click(ok_btn[0], settle=1.2)
        break
    out["info"] = info_text
    out["progress"] = progress_seen

    out["closed"] = _close_import_dialog(ui, dlg)
    if out["closed"]:
        # 창이 사라진 뒤에야 조회 클릭이 먹는다(위 docstring의 사고 참고).
        out["db_after"] = _result_total(database_search(ui))

    low = info_text.lower()
    said_ok = any(w in low for w in IMPORT_SUCCESS_WORDS)
    said_bad = any(w in low for w in IMPORT_FAILURE_WORDS)
    grew = (out["db_after"] or 0) > (out["db_before"] or 0)
    cols_ok = out["match"]["ok"] if out.get("match") else True
    out["ok"] = bool(said_ok and not said_bad and cols_ok and out.get("closed"))
    bits = ["결과 팝업=%r" % (info_text or "(없음)"),
            "진행 표시=%s" % (progress_seen or "없음")]
    if out.get("closed"):
        bits.append("Import Study 창 닫힘 확인 / Database 건수 %s → %s%s"
                    % (out["db_before"], out["db_after"],
                       "" if grew else " (증가 없음)"))
    else:
        bits.append("**Import Study 창이 닫히지 않았다** — 이 창이 모달로 남으면 "
                    "이후 클릭이 무시되므로 Database 재조회 결과를 판정 근거로 "
                    "쓰지 않는다(건수 확인 생략)")
    if out.get("match") is not None:
        m = out["match"]
        bits.append("열 대조 일치=%s / 잘림부분일치=%s / 불일치=%s / 없는열=%s"
                    % (sorted(m["matched"]), sorted(m["partial"]),
                       dict(m["mismatched"]), m["missing"]))
    if not grew and said_ok:
        bits.append("팝업은 성공이라 했는데 목록 건수가 늘지 않았다 — 같은 "
                    "스터디를 덮어썼을 수 있어 확인이 필요하다")
    out["note"] = " / ".join(bits)
    return out


# 상단 스터디 탭. 열린 검사 하나가 NaviBarItem 하나다. **ctrl_id로 범위를
# 가정하지 않는다** — 2026-08-20에는 검사 4개가 31213~31216으로 연속이었지만,
# 2026-08-21 실측(검사 1개)에서는 31274 하나였다. ID가 순번이 아니라 세션마다
# 달라지는 값이므로, 대신 **클래스 텍스트('NaviBarItem')로 찾는다**(CLAUDE.md
# 속성 우선 원칙). 이 버그로 열린 검사가 하나만 있을 때 `open_study_tabs()`가
# 0개로 잘못 보고해 정리가 되지 않은 채 다음 TC로 넘어갈 수 있었다.
#
# **컨테이너 ID(31200)는 스터디 탭 바만의 것이 아니다** — 같은 ID를 Registration
# 화면 자체의 Scheduled/Unscheduled/Reserved 탭도 쓴다(실측 2026-08-21). 두
# 컨테이너를 트리에서 항상 함께 발견되고 상황에 따라 하나만 보인다(visible).
# 구분 기준(실측): 스터디 탭 바는 환자 배너 오른쪽에서 시작해 `rect[0]`이
# 약 270 — Registration 자체 탭은 `rect[0]=0`부터 전체 폭이다. `.visible`과
# `rect[0]`을 함께 봐야 두 컨테이너가 섞이지 않는다.
STUDY_TAB_CONTAINER = 31200


def open_study_tabs(ui):
    """지금 열려 있는 스터디 탭 목록(왼쪽 -> 오른쪽).

    반환: [{"ctrl_id", "rect", "close_point"}]  — close_point는 그 탭의 X 좌표.
    """
    from .ui import children
    main = ui.main_window()
    if main is None:
        return []
    out = []
    for cont in [c for c in children(main.hwnd, 2)
                 if c.ctrl_id == STUDY_TAB_CONTAINER and c.visible
                 and c.rect[0] > 200 and c.size[0] > 400]:
        for tab in children(cont.hwnd, 2):
            if tab.text.strip() != "NaviBarItem":
                continue
            if not tab.visible or tab.size[0] < 100:
                continue
            # 탭 안의 작은 IconButton이 닫기(X)다. 없으면 탭 우측 상단을 쓴다.
            closer = None
            for k in children(tab.hwnd, 2):
                w, h = k.size
                if 10 <= w <= 30 and 10 <= h <= 30:
                    closer = k
                    break
            l, t, r, _b = tab.rect
            point = closer.center if closer is not None else (r - 14, t + 14)
            out.append({"ctrl_id": tab.ctrl_id, "rect": tab.rect,
                        "close_point": point})
    out.sort(key=lambda d: d["rect"][0])
    # 같은 탭이 컨테이너 중복으로 두 번 잡히는 일이 있어 ctrl_id로 중복을 없앤다.
    seen, uniq = set(), []
    for d in out:
        if d["ctrl_id"] in seen:
            continue
        seen.add(d["ctrl_id"])
        uniq.append(d)
    return uniq


CLOSE_ALL_BUTTON = 30274   # OCR 확정: "Close All" — 항상 보이는 툴바(더보기 팔레트 아님)
CLOSE_BUTTON = 30275       # OCR 확정: "Close"


def _handle_close_confirm_popups(ui, cfg, out, max_iters=3):
    """닫기 뒤에 뜨는 확인 팝업을 처리한다(QUESTION은 첫 버튼 = 닫기)."""
    from .ui import children as _children
    for _ in range(max_iters):
        d = ui.dialog()
        if d is None:
            break
        info = dialogs.read(ui, d, cfg)
        kind = dialogs.classify(info)
        rec = dialogs.DialogRecord(info["title"], info["message"], kind,
                                   "handled_by_close_all")
        out["dialogs"].append(rec)
        if kind == dialogs.QUESTION:
            btns = sorted([c for c in _children(d.hwnd, 3)
                           if c.text.strip() in ("TextButton", "Button")
                           and c.size[0] >= 40 and c.visible],
                          key=lambda c: c.rect[0])
            if btns:
                ui.click(btns[0], settle=1.2)       # 첫 버튼 = 닫기
            else:
                ui.dismiss_dialog(timeout=2)
        else:
            ui.dismiss_dialog(timeout=2)
        time.sleep(0.5)


def close_all_studies(ui, cfg=None, max_iters=12, evidence_dir=None):
    """열려 있는 모든 검사를 닫는다 — **시험이 끝나면 반드시 호출한다.**

    사용자 지시(2026-08-20): *"지금 테스트중이라고 해도 열려있는 스터디가 너무
    많거든? 이걸 잘 닫을 수 있도록 해줘, 테스트가 끝나면."* 사용자 지시
    (2026-08-21): *"촬영화면을 열고 테스트한 다음에는 꼭 그 촬영 스터디를
    닫아줘 — Tool의 Close All을 쓰면 될 것 같아."*

    열린 검사가 쌓이면 (1) 다음 시험이 어느 검사를 보고 있는지 불분명해지고,
    (2) 촬영 대상 Step 선택이 엉키고, (3) 사람이 화면을 봤을 때 시험 흔적과
    실제 상태를 구분하기 어렵다.

    **1차: Close All 툴(`30274`).** Viewer 최대화 레이아웃(우측 도구 패널)의
    항상 보이는 툴바에 있다 — Tools ≡ 더보기 팔레트 안이 아니다(실측
    2026-08-21, 사용자 지적으로 위치 정정). 열린 검사가 1개여도 활성화돼
    있고(실측), 팝업 없이 한 번에 전부 닫힌다. Exposure 화면이면 먼저
    `viewer_mode()`로 전환한다.

    **2차 백업: 탭을 하나씩 닫기.** Close All 버튼을 못 찾거나 눌러도 탭이
    남으면, 각 스터디 탭의 닫기(X)를 오른쪽부터 누르고 뜨는 확인 팝업을
    처리한다. Operation Manual 6.8(p.99): *"촬영 예정인 Step이 남아 있는
    경우, 검사를 닫거나 보류하는 것을 선택할 수 있습니다."* — 시험 정리
    목적이므로 **닫기**를 택한다(팝업의 첫 버튼). 보류를 택하면 검사가 그대로
    남아 목적을 달성하지 못한다.

    반환: {"closed": n, "remaining": n, "dialogs": [DialogRecord...], "method": str}
    """
    out = {"closed": 0, "remaining": 0, "dialogs": [], "method": ""}
    # 스터디 탭 바는 Registration 목록 화면에서는 렌더링되지 않는다(실측
    # 2026-08-21) — 그 화면에 있는 상태로 확인하면 스터디가 열려 있어도
    # `open_study_tabs()`가 0개로 보인다. Exposure로 옮겨 확인한다.
    goto(ui, "exposure")
    time.sleep(0.5)
    before = open_study_tabs(ui)
    if not before:
        return out

    if viewer_mode(ui, cfg):
        hits = by_id(ui, CLOSE_ALL_BUTTON)
        if hits:
            ui.click(hits[0], settle=1.5)
            _handle_close_confirm_popups(ui, cfg, out)
            after = open_study_tabs(ui)
            out["closed"] += len(before) - len(after)
            out["method"] = "close_all_button"

    for _ in range(max_iters):
        tabs = open_study_tabs(ui)
        if not tabs:
            break
        ui.click(tabs[-1]["close_point"], settle=1.5)   # 오른쪽부터 닫는다
        _handle_close_confirm_popups(ui, cfg, out)
        after = open_study_tabs(ui)
        if len(after) >= len(tabs):
            break                                       # 더 못 닫는다
        out["closed"] += len(tabs) - len(after)
        out["method"] = (out["method"] + "+tab_close").lstrip("+")
    out["remaining"] = len(open_study_tabs(ui))
    return out


def close_study(ui, cfg, settle=3.0, evidence_dir=None, verify=True):
    """열려 있는 검사를 닫는다(Database 화면의 Close) — **닫혔는지 확인한다.**

    체크리스트 TC02 Step 4: "스터디를 Close 하고 Database 에서 스터디 정보를
    확인한다." Close 후 뜨는 확인 팝업까지 처리한다.

    ## 왜 확인이 필요한가 (실측 2026-08-21)

    사용자 제보: *"지금 클로즈 버튼을 헛으로 눌렀고, 실제 스터디가 close 되지 않아
    데이터베이스에 저장되지 않음."* 실제로 그 사고가 났다
    (`Result_20260821_150508`): 이 함수는 버튼을 눌렀다는 사실만 돌려줬고 TC08은
    그것을 성공으로 받아들였다. 그런데 검사는 닫히지 않았고 — 그래서 **DB에
    커밋되지 않아** 뒤따르는 Step 3이 목록에서 *이전 실행의 오래된 스터디*를 골라
    Export했다. TC 마지막 정리 단계가 `닫음 2개`로 뒤늦게 치운 것이 그 증거다.

    그래서 이제 **열린 검사 탭 수를 앞뒤로 세어** 실제로 줄었는지 확인하고, 줄지
    않았으면 이미 검증된 경로(`close_all_studies()` — Close All 툴 + 탭 닫기
    백업)로 확실히 닫는다. 어느 경로로 닫혔는지 `method`에 남긴다.

    반환: {"clicked", "dialogs", "state", "pre_dialogs", "tabs_before",
           "tabs_after", "closed", "method", "ok"}
    """
    out = {"clicked": False, "dialogs": [], "state": "", "pre_dialogs": [],
           "tabs_before": 0, "tabs_after": 0, "closed": 0, "method": "",
           "ok": False}
    out["pre_dialogs"] = pending_dialogs(ui, evidence_dir=evidence_dir, cfg=cfg)
    # 스터디 탭 바는 Registration 화면에서는 렌더링되지 않는다(실측) — Exposure에서 센다.
    goto(ui, "exposure")
    time.sleep(0.5)
    out["tabs_before"] = len(open_study_tabs(ui))
    goto(ui, "database")
    time.sleep(1.5)
    # 화면이 실제로 Database로 바뀌었는지 확인한다 — 팝업이 남아 있으면 클릭이
    # 무시되므로, 버튼을 못 찾은 것이 아니라 "화면이 안 바뀐 것"일 수 있다.
    if not by_id(ui, DB_BUTTON["close"]):
        out["pre_dialogs"] += pending_dialogs(ui, evidence_dir=evidence_dir, cfg=cfg)
        goto(ui, "database", clear_dialogs=False)
        time.sleep(1.5)
    try:
        out["clicked"] = db_button(ui, "close", settle=settle)
    except WorkflowError as exc:
        out["error"] = "%s (닫은 선행 팝업: %s)" % (exc, out["pre_dialogs"] or "없음")
        return out
    for i in range(4):
        d = ui.dialog()
        if d is None:
            break
        out["dialogs"].append((d.text or "").strip() or "(제목 없음)")
        if evidence_dir:
            os.makedirs(evidence_dir, exist_ok=True)
            try:
                ui.capture_dialog(d, os.path.join(evidence_dir,
                                                  "close_dlg_%d.png" % (i + 1)))
            except Exception:                            # noqa: BLE001
                pass
        ui.dismiss_dialog(timeout=3)
        time.sleep(0.8)

    goto(ui, "exposure")
    time.sleep(0.5)
    after = len(open_study_tabs(ui))
    out["method"] = "database_close"
    if verify and out["tabs_before"] and after >= out["tabs_before"]:
        # 눌렀지만 닫히지 않았다 — 검증된 경로로 확실히 닫는다.
        fb = close_all_studies(ui, cfg, evidence_dir=evidence_dir)
        out["fallback"] = fb
        out["dialogs"] += [str(d) for d in (fb.get("dialogs") or [])]
        after = len(open_study_tabs(ui))
        out["method"] = ("database_close(무효) → %s"
                         % (fb.get("method") or "close_all_studies"))
    out["tabs_after"] = after
    out["closed"] = max(0, out["tabs_before"] - after)
    # 닫을 것이 없었으면(0개) 그대로 성공으로 본다 — 이미 닫힌 상태다.
    out["ok"] = (out["tabs_before"] == 0) or (after < out["tabs_before"])
    out["state"] = acquisition_state(ui, cfg)
    return out
