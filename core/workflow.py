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
import time

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
    """대화상자 문구를 읽는다. 표준 API로 안 읽히면 캡처+OCR로 읽는다.

    실측(2026-08-19): 촬영 뒤 뜨는 `Error` 팝업은 본문이 owner-draw라
    `ui.dialog_text()`가 빈 값을 돌려준다. 그 결과 "확인되지 않은 팝업"으로
    FAIL이 났는데, 실제 문구는 이미 원인을 규명한
    `Image process parameter file does not exist.` 였다. **문구를 못 읽는 것과
    모르는 팝업인 것은 다르다** — OCR로 한 번 더 시도한 뒤에 판단한다.
    """
    text = (ui.dialog_text(dlg) or "").strip()
    if text and text != "(문구 미노출)":
        return text
    try:
        import pytesseract
        from PIL import ImageGrab
    except ImportError:
        return text
    exe = ((cfg or {}).get("xipl") or {}).get("tesseract_exe") \
        or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
    try:
        img = ImageGrab.grab(bbox=dlg.rect, all_screens=True)
        img = img.resize((img.width * 2, img.height * 2))
        ocr = pytesseract.image_to_string(img).strip()
    except Exception:                                    # noqa: BLE001
        return text
    return " ".join(ocr.split()) or text


def pending_dialogs(ui, max_iters=4, timeout=3, evidence_dir=None, cfg=None):
    """지금 떠 있는 모달 팝업을 닫고 그 문구를 돌려준다.

    **VXvue는 모달 팝업이 떠 있으면 이후 클릭을 조용히 무시한다**(HANDOFF 4절).
    실측(2026-08-19): 촬영 뒤 뜬 `Error: Image process parameter file does not
    exist.`를 닫지 않은 상태에서 `goto("database")`를 호출했더니 화면이 바뀌지
    않았고, 그 결과 "Database Close 버튼을 찾지 못했다"는 **엉뚱한 원인**으로
    FAIL이 났다. 그래서 화면을 전환하기 전에 항상 이 함수를 통과시킨다.

    닫은 문구는 삼키지 않고 반환한다 — 팝업이 떴다는 사실 자체가 판정 대상일
    수 있다.
    """
    closed = []
    for i in range(max_iters):
        d = ui.dialog()
        if d is None:
            break
        title = (d.text or "").strip()
        msg = dialog_message(ui, d, cfg)
        if evidence_dir:
            os.makedirs(evidence_dir, exist_ok=True)
            try:
                ui.capture_dialog(d, os.path.join(evidence_dir,
                                                  "pending_%d.png" % (i + 1)))
            except Exception:                            # noqa: BLE001
                pass
        closed.append(("%s: %s" % (title, msg)).strip(": ") or "(문구 미노출)")
        before_hwnd = d.hwnd
        ui.dismiss_dialog(timeout=timeout)
        time.sleep(0.6)

        # dismiss_dialog가 못 닫는 창이 있다(실측 2026-08-19: "New Procedure"
        # 창은 Cancel이 없고 Add/Delete/OK만 있어 닫히지 않았고, 그 창이 남은
        # 채로 이후 모든 조작이 조용히 무시돼 TC03이 원인 불명으로 실패했다).
        # 그럴 때는 제목줄 닫기 버튼(ctrl_id -4)으로 닫는다 — **아무 버튼이나
        # 누르지 않는다**(Add를 누르면 설정이 바뀐다).
        still = ui.dialog()
        if still is not None and still.hwnd == before_hwnd:
            from .ui import children as _children
            closer = [c for c in _children(still.hwnd, 2)
                      if c.ctrl_id == DIALOG_CLOSE_X]
            if closer:
                ui.click(closer[0], settle=1.2)
                time.sleep(0.6)
            else:
                # 그래도 안 닫히면 무한 루프를 만들지 않고 사실만 남긴다.
                closed.append("(닫지 못한 창: %s — 사람이 닫아야 한다)"
                              % (title or "제목 없음"))
                break
    return closed


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
def registration_tab(ui, which="scheduled", settle=2.0):
    hits = by_id(ui, REG_TAB[which])
    if not hits:
        raise WorkflowError("Registration %s 탭(%d)을 찾지 못했습니다."
                            % (which, REG_TAB[which]))
    ui.click(hits[0], settle=settle)
    return True


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
    registration_tab(ui, "scheduled")
    summary = search(ui)
    time.sleep(1.0)
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
    if row is None:
        row = rows[0]
        row_text = row_cell_text(ui, row, cfg)
    click_row(ui, row)
    start = start_study(ui, cfg, evidence_dir=evidence_dir,
                        map_procedure_name=map_procedure_name)
    return {"summary": summary, "row_text": row_text, "start": start,
            "rows": len(rows)}


# --- 촬영 -------------------------------------------------------------
def acquire(ui, cfg, timeout=90, poll=3.0, evidence_dir=None):
    """Demo(가상) 촬영을 1회 수행하고 영상이 생겼는지 확인한다.

    반환: {
      "key": 누른 키, "before": 촬영 전 영상 수, "after": 촬영 후 영상 수,
      "acquired": bool, "seconds": 소요, "state": 촬영 상태,
      "dialogs": [뜬 팝업 문구...], "known_warning": bool
    }

    `known_warning`은 뜬 팝업이 이미 원인을 확인한 환경 문제
    (`Image process parameter file does not exist` — docstring 참고)일 때 True다.
    그 경우에도 **팝업이 떴다는 사실 자체는 결과에 남긴다.**
    """
    key = (cfg.get("viewer") or {}).get("demo_exposure_key", "F2")
    before = thumbnail_count(ui)
    state0 = acquisition_state(ui, cfg)
    out = {"key": key, "before": before, "after": before, "acquired": False,
           "seconds": 0, "state": state0, "dialogs": [], "known_warning": False}

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
        now = thumbnail_count(ui)
        if now > before:
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
    out["acquired"] = out["after"] > before
    out["state"] = acquisition_state(ui, cfg)
    return out


# --- 전송 -------------------------------------------------------------
def send(ui, scope="all", settle=2.5, dialog_timeout=8, attempts=3):
    """선택한 영상을 DICOM Storage로 전송한다.

    Send 버튼은 Exposure/Database에서 같은 ID(30294)다. 전송 범위 팝업
    (All Images / Selected / Cancel)까지 처리한다.

    **영상을 먼저 선택해야 한다** — 선택 전에는 Send가 비활성이라 눌러도 팝업이
    뜨지 않는다. `select_first_image()`를 먼저 호출할 것.

    반환: {"scope","clicked","dialog":bool}
    """
    from .ui import children
    if scope not in SEND_SCOPE:
        raise WorkflowError("알 수 없는 전송 범위: %s" % scope)
    want = SEND_SCOPE[scope]

    for _ in range(attempts):
        hits = by_id(ui, TOOL["send"])
        if not hits:
            raise WorkflowError("Send 버튼(%d)을 찾지 못했습니다." % TOOL["send"])
        ui.click(hits[0], settle=settle)
        end = time.time() + dialog_timeout
        while time.time() < end:
            d = ui.dialog()
            if d is not None:
                btn = [c for c in children(d.hwnd, 3) if c.ctrl_id == want]
                if btn:
                    ui.click(btn[0], settle=2.0)
                    return {"scope": scope, "clicked": want, "dialog": True}
            time.sleep(0.5)
    return {"scope": scope, "clicked": None, "dialog": False}


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


def database_search(ui, settle=3.0):
    """Database 화면에서 조회를 실행하고 요약 문구를 돌려준다.

    Search 버튼은 Registration과 같은 ID(`30689`)다(실측). 검사를 Close한 직후에는
    목록이 자동으로 갱신되지 않아 `Result: 0 / 0`이 남아 있다 — 조회하지 않으면
    "촬영했는데 Database에 없다"는 잘못된 판정이 난다.
    """
    goto(ui, "database")
    time.sleep(1.0)
    hits = by_id(ui, REG_SEARCH_BUTTON)
    if hits:
        ui.click(hits[0], settle=settle)
    time.sleep(1.0)
    return result_summary(ui)


def close_study(ui, cfg, settle=3.0, evidence_dir=None):
    """열려 있는 검사를 닫는다(Database 화면의 Close).

    체크리스트 TC02 Step 4: "스터디를 Close 하고 Database 에서 스터디 정보를
    확인한다." Close 후 뜨는 확인 팝업까지 처리한다.

    반환: {"clicked": bool, "dialogs": [...], "state": 촬영 상태}
    """
    out = {"clicked": False, "dialogs": [], "state": "", "pre_dialogs": []}
    out["pre_dialogs"] = pending_dialogs(ui, evidence_dir=evidence_dir, cfg=cfg)
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
    out["state"] = acquisition_state(ui, cfg)
    return out
