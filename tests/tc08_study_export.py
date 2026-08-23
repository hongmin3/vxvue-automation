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
E드라이브를 기준으로 수행되도록 해주면 될것 같아."** 사용자 지시(2026-08-21):
**"E가 없다면 일단 D로 하고 결과에 D로 했다고 리포팅해라 — 이건 외부 드라이브
export/import를 보는 테스트라서."** → `_pick_drive()`가 `dest`의 드라이브가 실제
있는지 확인하고, 없으면 로컬 드라이브로 대체하며 그 사실을 판정에 명시한다.

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
| 역방향 Import 전제조건 | **IMG 형식**이 함께 Export됐는지 확인(아래 참고) |
| 역방향 Import | Database `Import`(30315)로 되읽기 |

"export 된 영상 오픈하여 확인"이라는 Expected Result를 **뷰어로 열어 보는 대신
파일 태그를 직접 읽어** 확인한다 — 사람이 눈으로 보는 것보다 대조 항목이 명확하고
증거로 남는다.

## VXvue의 Import는 DICOM이 아니라 IMG만 받는다 (문서 근거, 사용자 지적 2026-08-21)

Operation Manual 8.14 "검사 가져오기"(p.204): **"VXvue에서 생성된 IMG 파일만
가져올 수 있습니다."** DICOM/DICOMDIR로만 Export하면 파일 자체는 정상 생성돼도
**뷰어로 다시 가져올 방법이 없다** — Expected Result 2("뷰어로 import 성공한다")를
검증하려면 File Format에 **IMG를 반드시 함께 선택**해야 한다.

8.13.1(p.200)에 따르면 File Format은 "최소 1개 이상 다중 설정"할 수 있다(실측
확인: DICOM과 IMG를 동시에 체크해도 서로 배타적이지 않다 — DICOM/DICOMDIR끼리만
배타적). 그래서 이 자동화는 **DICOM(태그 대조용)과 IMG(Import 전제조건)를 함께
선택**하고 Start한다. 실측(2026-08-21): 한 번의 Export로 `dcm\...\*.dcm`과
`S{Series}I{Instance}.img`가 같은 대상 폴더에 함께 생성됨을 확인했다.

## Export Manager 컨트롤 (실측 2026-08-21, 캡처+OCR로 확정)

이전 세션은 이 창의 컨트롤을 실측하지 못해 Step 4~7이 전부 MANUAL이었다.
`python run.py ui-probe`로는 owner-draw 라벨이 안 보여, 창이 뜬 상태에서
캡처+OCR을 여러 번 돌려 확정했다(Bellalun의 `core/export_manager.py`와 창 구조는
같지만 컨트롤 ID는 VXvue에서 새로 실측한 값만 쓴다).

| 컨트롤 | ID | 확정 방법 |
|---|---|---|
| Export Path (표시 전용) | `30191` Edit | `SendMessage(WM_SETTEXT)`로는 **표시만 바뀌고 실제 Export 대상은 안 바뀐다**(실측: 텍스트를 "E:\..."로 바꿔도 파일은 여전히 이전 D: 경로에 생성됨) — 이 필드는 내부 상태의 읽기 전용 반영판이다 |
| 드라이브 선택 | `31003` (자식 `1`=드롭다운 화살표) | 클릭하면 owner-draw 드롭다운(C/D/E...)이 뜬다. **이 목록으로 드라이브를 바꿔야 실제 내부 경로가 바뀐다**(실측 확인: 드롭다운에서 E 클릭 → Export Path가 진짜 `E:\`로 바뀌고 그 뒤 Export도 실제 E:에 생성됨) |
| 경로 찾아보기 | `30680` "..." | 표준 `SHBrowseForFolder` 창을 연다. 트리는 **현재 선택된 드라이브 위치에서 시작**하므로, 위 드라이브 선택으로 먼저 드라이브를 맞추면 하위 폴더까지 몇 단계 안 걸린다. 확인(`1`)/취소(`2`) 버튼은 표준 폴더 찾아보기 다이얼로그의 것 |
| File Format | `30696`=DICOM `30697`=DICOMDIR `30698`=IMG `30703`=RAW `30699`=JPEG `30702`=BMP `30700`=TIF 8 `30701`=TIF 16 | 다중 선택(토글) — 눌러도 이미 선택된 다른 항목이 풀리지 않는다(DICOM/DICOMDIR만 상호배타, Operation Manual 8.13.1) |
| Start / Cancel | `30683` / `30684` | OCR로 라벨 확정. **Start를 눌러야 실제 전송된다** — 확인 팝업이 없다 |
| Current State | 라벨 옆 값(둘 다 ctrl_id 공용값 `20000`이라 위치로 구분, `_export_state()`) | `Ready` → (진행) → `Done` |
| 완료 알림 | `Info` 팝업, 버튼 `27000` 하나만 표시 | "Succeed to export. Export Manager will be closed." — 누르면 Export Manager 프로세스 자체가 종료된다 |

## Export Manager는 별도 프로세스다 (실측)

`C:\Program Files\Vxvue\VX.EXPORT.MANAGER.exe`가 별도 최상위 창으로 뜬다
(Bellalun의 `EXPORT.MANAGER`와 같은 구조). VXvue 프로세스에 붙은 드라이버로는
이 창의 컨트롤이 보이지 않으므로 `VXvueUi("VX.EXPORT.MANAGER")`로 따로 붙는다.
"""

import os
import time

from core import dicomlite
from core import workflow as W
from core.listgrid import ListGrid
from core.result import BLOCKED, FAIL, MANUAL, PASS, SKIP, TCResult
from core.ui import VXvueUi

TC_ID = "TC_WindowsUpdate_08"
TC_TITLE = "Study Export (외부 저장 매체 Export → 산출물 검증 → 역방향 Import)"

KNOWN_DEFECT = "#21049 (Win11에서 Study Export 시 에러 발생하며 Export 안 됨)"

# Export Manager 창 컨트롤 (실측 2026-08-21, 캡처+OCR로 확정. 모듈 docstring의
# "Export Manager 컨트롤" 표 참고). Burning Option(Annotations/Information/
# Orientation)과 Include Option(Portable Viewer/Snapshot Image 등) 체크박스는
# 기본값을 그대로 둔다 — 켜고 끄는 것은 owner-draw라 상태를 표준 API로 못 읽고,
# 기본값(DICOM 선택 시 Portable Viewer/Dose SR ON)이 이미 체크리스트 요구
# ("QXlink portable viewer 확인")를 만족한다(실측 확인).
EXPORT_PATH_EDIT = 30191
EXPORT_DRIVE_WIDGET = 31003     # 자식 ctrl_id=1이 드롭다운 화살표
EXPORT_BROWSE_BUTTON = 30680    # "..."
EXPORT_FORMAT_DICOM = 30696
EXPORT_FORMAT_IMG = 30698       # VXvue 자체 Import가 요구하는 유일한 형식
EXPORT_START_BUTTON = 30683     # OCR: "Start"
EXPORT_CANCEL_BUTTON = 30684    # OCR: "Cancel"
EXPORT_DONE_STATES = ("done", "complete", "completed")
EXPORT_ERROR_STATES = ("error", "fail", "failed")
BROWSE_TREE_CLASS = "SysTreeView32"
# 포터블 뷰어 산출물(실측 2026-08-21, E 드라이브 Export 결과에서 확인).
PORTABLE_VIEWER_FILES = ("pv.loader.exe", "qxl.pv.exe")
BROWSE_OK_ID = 1
BROWSE_CANCEL_ID = 2


def _format_selected(mgr, ctrl_id):
    """File Format 버튼(예: `30698` IMG)이 선택 상태인지 테두리 색으로 판별한다.

    owner-draw TextButton이라 표준 API로 체크 상태를 못 읽는다. 선택되면 순수
    노란색(255,255,0) 테두리, 아니면 어두운 회색(32,32,32) 테두리로 그려진다
    (실측 픽셀 확인, 2026-08-21 — DICOM/RAW 버튼을 각각 캡처해 대조). 둘 다
    아니면 판별 불가로 `None`을 돌려준다 — 모르면 모른다고 한다.
    """
    from PIL import ImageGrab
    hits = mgr.by_id(ctrl_id)
    if not hits:
        return None
    x, y, x2, _y2 = hits[0].rect
    img = ImageGrab.grab(bbox=(x, y, x2, y + 2), all_screens=True)
    px = img.getpixel((min(5, img.width - 1), 0))[:3]
    if px == (255, 255, 0):
        return True
    if px == (32, 32, 32):
        return False
    return None


def _export_state(mgr):
    """'Current State' 라벨 옆 값을 읽는다.

    라벨과 값 모두 `Static`이고 ctrl_id가 공용값(20000)이라 id로 구분할 수
    없다 — 라벨을 텍스트로 먼저 찾고, 같은 높이(y)에서 더 오른쪽에 있는
    Static을 값으로 본다(실측: 라벨 rect x=645, 값 rect x=775, 둘 다 y=627).
    """
    ctrls = mgr.controls(max_depth=3)
    label = next((c for c in ctrls if c.text.strip() == "Current State"), None)
    if label is None:
        return None
    ly = label.rect[1]
    lx = label.rect[0]
    candidates = [c for c in ctrls
                  if c.cls == "Static" and c.rect[0] > lx and abs(c.rect[1] - ly) <= 5]
    return mgr.get_text(candidates[0]) if candidates else None


def _ocr_word_center(bbox, want, scale=3):
    """`bbox` 영역을 캡처+OCR해 `want`와 일치하는 단어의 화면 중심 좌표를 찾는다.

    owner-draw 팝업(드라이브 드롭다운)이나 표준 다이얼로그의 자유 배치 항목
    (폴더 찾아보기 트리)처럼 항목 개수·위치를 코드에 가정할 수 없는 곳에 쓴다
    — 항목 수만큼 화면을 읽어 실행 시점에 좌표를 계산한다(CLAUDE.md 좌표 규칙).
    """
    import pytesseract
    from PIL import ImageGrab

    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    big = img.resize((img.width * scale, img.height * scale))
    data = pytesseract.image_to_data(big, output_type=pytesseract.Output.DICT)
    want_norm = want.strip().upper()
    for i, txt in enumerate(data.get("text", [])):
        if txt.strip().upper() == want_norm:
            cx = bbox[0] + (data["left"][i] + data["width"][i] / 2) / scale
            cy = bbox[1] + (data["top"][i] + data["height"][i] / 2) / scale
            return (cx, cy)
    return None


def _select_export_drive(mgr, letter):
    """드라이브 선택 위젯(`31003`)의 드롭다운을 열어 `letter` 드라이브를 고른다.

    드롭다운은 owner-draw 팝업이라 컨트롤 트리·`ui.dialog()` 어느 쪽에도 잡히지
    않는다(Tools ≡ 팔레트와 같은 부류). 화살표를 누른 직후 필드 아래 영역을
    캡처+OCR해 원하는 글자의 위치를 찾아 클릭한다 — 연결된 드라이브 개수가
    PC마다 다르므로 항목 수·간격을 가정하지 않는다.
    """
    from core.ui import children

    widget_hits = mgr.by_id(EXPORT_DRIVE_WIDGET)
    if not widget_hits:
        return False, "드라이브 선택 위젯(%d)을 찾지 못했다." % EXPORT_DRIVE_WIDGET
    widget = widget_hits[0]
    if (mgr.get_text(widget) or "").strip().upper() == letter.upper():
        return True, "이미 %s로 선택되어 있었다(건드리지 않음)." % letter
    arrow = next((c for c in children(widget.hwnd, 2) if c.ctrl_id == 1), None)
    if arrow is None:
        return False, "드라이브 드롭다운 화살표를 찾지 못했다."
    mgr.click(arrow, settle=0.6)
    x, y, x2, _ = widget.rect
    region = (x, y + (widget.rect[3] - widget.rect[1]), x2 + 40, y + 320)
    point = _ocr_word_center(region, letter)
    if point is None:
        mgr.key("ESC", settle=0.3)
        return False, "드롭다운에서 '%s' 항목을 OCR로 찾지 못했다." % letter
    mgr.click(point, settle=1.0)
    now = mgr.get_text(widget)
    return (now or "").strip().upper() == letter.upper(), "선택 후 위젯 표시값=%r" % now


def _browse_to_folder(mgr, dest):
    """Browse('...', `30680`)로 `dest` 폴더를 선택하고 확인한다.

    실측(2026-08-21): 이 표준 `SHBrowseForFolder` 트리는 **현재 선택된
    드라이브 위치에서 시작**한다 — `_select_export_drive()`로 먼저 드라이브를
    맞춰 두면 목표 폴더가 트리의 첫 화면에 바로 보인다(하위 폴더까지 계층
    탐색을 별도로 구현하지 않는다: `dest`가 드라이브 바로 아래 폴더라는
    전제, `config.json`의 `export.dest_dir` 형식과 일치). 폴더가 안 보이면
    새로 만들지 않고 실패로 보고한다 — 엉뚱한 폴더를 만들지 않기 위함이다.
    """
    from core.ui import children

    path_hits = mgr.by_id(EXPORT_PATH_EDIT)
    current = (mgr.get_text(path_hits[0]) if path_hits else "") or ""
    if os.path.normcase(os.path.normpath(current)) == os.path.normcase(os.path.normpath(dest)):
        return True, "이미 %s로 설정되어 있었다(건드리지 않음)." % dest

    hits = mgr.by_id(EXPORT_BROWSE_BUTTON)
    if not hits:
        return False, "Browse 버튼(%d)을 찾지 못했다." % EXPORT_BROWSE_BUTTON
    mgr.click(hits[0], settle=1.5)
    dlg = mgr.dialog()
    if dlg is None:
        return False, "폴더 찾아보기 창이 뜨지 않았다."
    tree = next((c for c in children(dlg.hwnd, 4) if c.cls == BROWSE_TREE_CLASS), None)
    if tree is None:
        return False, "폴더 트리(SysTreeView32)를 찾지 못했다."
    folder_name = os.path.basename(os.path.normpath(dest))
    point = _ocr_word_center(tree.rect, folder_name)
    if point is None:
        ok_btn = next((c for c in children(dlg.hwnd, 3) if c.ctrl_id == BROWSE_CANCEL_ID), None)
        if ok_btn:
            mgr.click(ok_btn, settle=0.5)
        return False, ("트리에서 '%s' 폴더를 OCR로 찾지 못했다(새로 만들지 않음)"
                       % folder_name)
    mgr.click(point, settle=0.5)
    ok_btn = next((c for c in children(dlg.hwnd, 3) if c.ctrl_id == BROWSE_OK_ID), None)
    if ok_btn is None:
        return False, "확인 버튼을 찾지 못했다."
    mgr.click(ok_btn, settle=1.0)
    path_hits = mgr.by_id(EXPORT_PATH_EDIT)
    now = mgr.get_text(path_hits[0]) if path_hits else None
    return (now or "").strip().lower() == dest.strip().lower(), "확인 후 Export Path=%r" % now


def _run_export_manager(proc_name, dest, timeout_done=180):
    """Export Manager에서 대상 드라이브·폴더·형식을 지정하고 Start를 누른다.

    **Export Path Edit(30191)는 표시 전용이다** — `SendMessage(WM_SETTEXT)`로
    바꿔도 겉보기 텍스트만 바뀔 뿐 실제 Export 대상은 그대로다(실측: 텍스트를
    "E:\\..."로 바꾼 뒤 Start해도 파일은 이전 D: 경로에 생성됐다). 실제로
    바꾸려면 **드라이브 드롭다운(`_select_export_drive`) → Browse
    (`_browse_to_folder`)** 순서를 거쳐야 한다. File Format은 DICOM(기존
    태그 대조용)에 **IMG를 추가로 선택**한다 — VXvue 자체 Import는 IMG만
    받는다(Operation Manual 8.14, 모듈 docstring 참고). File Format은 다중
    선택이라 DICOM을 다시 누르지 않아도 그대로 유지된다(실측 확인).

    반환: {"ok", "state", "drive", "path_before", "path_final", "format_ok", "note"}
    """
    mgr = VXvueUi(proc_name)
    if not mgr.pid or not mgr.main_window():
        return {"ok": False, "note": "Export Manager 창을 찾지 못했다."}
    mgr.activate()
    time.sleep(1.0)          # 창이 막 뜬 직후에는 자식 컨트롤 열거가 비어 있을 수 있다(실측).

    drive = (os.path.splitdrive(dest)[0] or dest[:2]).rstrip(":\\")
    path_hits = mgr.by_id(EXPORT_PATH_EDIT)
    path_before = mgr.get_text(path_hits[0]) if path_hits else None

    drive_ok, drive_note = _select_export_drive(mgr, drive)
    path_final = path_before
    browse_note = "드라이브 선택 실패로 건너뜀"
    if drive_ok:
        browse_ok, browse_note = _browse_to_folder(mgr, dest)
        path_hits = mgr.by_id(EXPORT_PATH_EDIT)
        path_final = mgr.get_text(path_hits[0]) if path_hits else None
    else:
        browse_ok = False

    format_hits = mgr.by_id(EXPORT_FORMAT_IMG)
    format_ok = False
    format_note = ""
    if format_hits:
        before_sel = _format_selected(mgr, EXPORT_FORMAT_IMG)
        if before_sel is True:
            format_ok = True
            format_note = "이미 선택되어 있었다(건드리지 않음 — 다시 누르면 꺼진다)."
        else:
            mgr.click(format_hits[0], settle=0.8)
            after_sel = _format_selected(mgr, EXPORT_FORMAT_IMG)
            format_ok = bool(after_sel)
            format_note = "클릭 전=%s / 클릭 후=%s" % (before_sel, after_sel)
    else:
        format_note = "IMG 포맷 버튼(%d)을 찾지 못했다." % EXPORT_FORMAT_IMG

    start_hits = mgr.by_id(EXPORT_START_BUTTON)
    if not start_hits:
        return {"ok": False, "note": "Start 버튼(%d)을 찾지 못했다." % EXPORT_START_BUTTON,
                "drive": drive_note, "path_before": path_before, "path_final": path_final,
                "format_ok": format_ok}
    mgr.click(start_hits[0], settle=1.0)

    end = time.time() + timeout_done
    last = None
    while time.time() < end:
        last = _export_state(mgr)
        if last and last.strip().lower() in EXPORT_DONE_STATES + EXPORT_ERROR_STATES:
            break
        time.sleep(2.0)
    ok = bool(last and last.strip().lower() in EXPORT_DONE_STATES)

    # 완료 시 "Succeed to export. Export Manager will be closed." Info 팝업이
    # 뜬다(버튼 1개, ctrl_id=27000 — Send/Print 확인 팝업과 같은 컨트롤 슬롯을
    # 재사용한다). 닫아 주지 않으면 다음 실행이 이 팝업과 충돌한다(사용자 지적,
    # 2026-08-21 — "지금 열려 있는 팝업은 안 끌꺼야?"). 'Done' 판정 직후에는
    # 팝업이 아직 안 뜬 순간일 수 있어 최대 3회 재시도하고, 클릭 뒤에는 창이
    # 실제로 사라졌는지(프로세스 종료) 확인한다 — 클릭했다는 사실만으로 닫혔다고
    # 적지 않는다.
    from core.ui import children
    close_note = ""
    for _ in range(3):
        dlg = mgr.dialog()
        if dlg is None:
            time.sleep(1.0)
            continue
        btn = [c for c in children(dlg.hwnd, 3) if c.ctrl_id == 27000 and c.visible]
        if btn:
            mgr.click(btn[0], settle=1.5)
        time.sleep(1.0)
        if not VXvueUi(proc_name).pid:
            close_note = "완료 팝업 닫음(프로세스 종료 확인)."
            break
    else:
        if mgr.dialog() is not None:
            close_note = "완료 팝업이 떠 있으나 3회 시도 후에도 닫히지 않았다."

    path_ok = bool(path_final) and os.path.normcase(os.path.normpath(path_final)) == \
        os.path.normcase(os.path.normpath(dest))
    note_parts = ["드라이브: %s" % drive_note, "폴더: %s" % browse_note,
                 "IMG 포맷: %s" % format_note]
    if close_note:
        note_parts.append(close_note)
    if not path_ok:
        note_parts.append("요청한 대상(%s)과 실제 Export Path(%s)가 다르다 — "
                          "산출물 확인은 실제 경로 기준으로 해야 한다."
                          % (dest, path_final))
    if not ok:
        note_parts.append("%d초 안에 완료 상태를 확인하지 못했다(마지막 값=%r)."
                          % (timeout_done, last))
    return {"ok": ok, "state": last, "drive": drive_note,
            "path_before": path_before, "path_final": path_final, "path_ok": path_ok,
            "format_ok": format_ok, "note": " / ".join(note_parts)}


def _export_cfg(cfg):
    ex = cfg.get("export") or {}
    return (ex.get("dest_dir") or r"E:\VXvue_QA_Export",
            ex.get("process_name") or "VX.EXPORT.MANAGER",
            ex.get("exe") or r"C:\Program Files\Vxvue\VX.EXPORT.MANAGER.exe")


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA", do_import=True,
        purge_export=True):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc08")
    os.makedirs(evidence_dir, exist_ok=True)
    dest, proc_name, exe = _export_cfg(cfg)
    step = 1

    # --- Step 0: 대상 매체(드라이브) 준비 -------------------------------
    drive = os.path.splitdrive(dest)[0] or dest[:2]
    if not os.path.isdir(drive + os.sep):
        fallback_drive = "D:"
        if os.path.isdir(fallback_drive + os.sep):
            folder_name = os.path.basename(os.path.normpath(dest))
            r.add(step, "Export 대상 드라이브 확인", MANUAL,
                  expected="%s 사용 가능(체크리스트 Precondition: 외부 매체 CD/USB)"
                           % drive,
                  actual="%s 없음 → 내장 드라이브 %s로 대체" % (drive, fallback_drive),
                  note="사용자 지시(2026-08-21): 'E가 없다면 일단 D로 하고 결과에 "
                       "D로 했다고 리포팅해라 — 이건 외부 드라이브 export/import를 "
                       "보는 테스트라서.' **외부 매체가 아닌 내장 드라이브로 대체 "
                       "수행했으므로 이 TC를 PASS로 올리지 않는다** — 실제 USB/CD "
                       "검증은 사람이 물리 매체로 다시 확인해야 한다.")
            step += 1
            dest = os.path.join(fallback_drive + os.sep, folder_name)
            drive = fallback_drive
        else:
            r.add(step, "Export 대상 드라이브 확인", BLOCKED,
                  expected="%s 또는 대체 드라이브 %s 사용 가능" % (drive, fallback_drive),
                  actual="둘 다 사용할 수 없음",
                  note="config.json의 export.dest_dir을 실제 매체 경로로 바꾼 뒤 "
                       "다시 실행할 것.")
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
          note=("체크리스트 Precondition은 CD/USB지만 물리 매체 굽기·삽입은 사람이 "
               "해야 하므로 **드라이브 %s를 기준으로 수행**한다(사용자 지시, "
               "2026-08-19/21 — 기본은 E, 없으면 D로 대체하고 위 Step에 남긴다). "
               "실제 USB로 바꿀 때는 config.json의 export.dest_dir만 "
               "고치면 된다 — 경로를 코드에 박지 않았다. 기존 파일 목록을 먼저 떠 "
               "이번 Export 산출물만 가려낸다." % drive))
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
            closed = W.close_study(ui, cfg, evidence_dir=evidence_dir)
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "Export 대상 스터디 준비", FAIL, actual=str(exc))
            r.finalize()
            return r
        # **Close가 실제로 됐는지 판정에 넣는다.** 실측 2026-08-21
        # (`Result_20260821_150508`): 버튼을 눌렀다는 사실만 믿었더니 검사가 닫히지
        # 않았고, 닫히지 않으면 **DB에 커밋되지 않아** 이 뒤의 Export가 이전 실행의
        # 오래된 스터디를 대상으로 삼았다(사용자 제보로 확인).
        r.add(step, "Export 대상 스터디 준비 (MWL 오픈 + 촬영 + Close)",
              PASS if (acq["acquired"] and closed.get("ok")) else FAIL,
              expected="영상 1장 이상 획득 후 **검사가 실제로 닫힘**",
              actual="영상 %d → %d장 / 처리한 팝업=%s / 검사 닫기: 열린 탭 %d → %d "
                     "(%s)"
                     % (acq["before"], acq["after"], acq["dialogs"] or "없음",
                        closed.get("tabs_before", -1), closed.get("tabs_after", -1),
                        closed.get("method") or "?"),
              note="검사를 닫지 않으면 스터디가 Database에 커밋되지 않아 Export 대상"
                   "으로 고를 수 없다(Operation Manual 3.6/6.8). Database의 Close가"
                   " 먹지 않으면 Close All 툴로 확실히 닫고 그 사실을 method에 남긴다.")
        if not acq["acquired"] or not closed.get("ok"):
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
              note="Export는 Database 목록에서 대상을 골라야 실행할 수 있는데 "
                   "`W.database_search()`가 재시도(최대 4회, 3초 간격)해도 목록이 "
                   "비었다. 원인 후보: (1) Step 미등록으로 검사가 완료 처리되지 "
                   "않음(STUDY.StudyStatus=1, Operation Manual 3.6/6.8) — Step 1의 "
                   "촬영이 정상 등록됐는지 먼저 볼 것. (2) 2026-08-21 실측: Step "
                   "등록이 정상이어도 Close 직후 제품 내부 인덱싱이 늦어 재조회가 "
                   "필요한 경우가 있었는데(`database_search()`가 이미 재시도로 "
                   "흡수) 그 상한(4회/3초)을 넘는 더 긴 지연일 수 있다. Export "
                   "자체를 검증하지 못했으므로 알려진 결함 %s의 재발 여부도 이번 "
                   "실행으로는 판단할 수 없다." % KNOWN_DEFECT)
        r.finalize()
        return r
    # **첫 행을 그대로 쓰지 않는다.** 사용자 지시(2026-08-21): "실제 export 를 할
    # 때도 내가 원하는 Study를 export 하는지 확인하는 것도 step에 추가해 주고 확인해
    # 주라. 그냥 무지성으로 제일 상단에 있는 거 export 하지 말고." 이번 실행의
    # Patient ID(`core/testdata.py`가 실행 시각으로 각인한 값)를 목록 열에서 찾아
    # 그 행을 고른다 — 잘려 보이면 그 열을 넓혀 확정한다(`core/listgrid.py`).
    want_pid = (cfg.get("test_data") or {}).get("mwl_patient_id")
    picked = None
    if want_pid:
        try:
            grid = ListGrid(ui, W.by_id(ui, W.DB_LIST)[0])
            picked = grid.find_row("Patient ID", want_pid)
        except Exception as exc:                          # noqa: BLE001
            picked = {"row": None, "note": "목록 판독 실패: %s" % exc, "read": []}
    if picked is None:
        W.click_row(ui, rows[0])
        r.add(step, "Database에서 Export 대상 스터디 선택", MANUAL,
              expected="이번 실행의 Patient ID를 가진 행 선택",
              actual="%s / config에 test_data.mwl_patient_id가 없어 첫 행을 선택" % summary,
              note="어느 스터디를 Export했는지 확정할 수 없다.")
    elif picked.get("row") is None:
        r.add(step, "Database에서 Export 대상 스터디 선택", FAIL,
              expected="Patient ID=%s 인 행" % want_pid,
              actual="%s / %s" % (summary, picked.get("note")),
              note="이번 실행에서 촬영한 스터디가 목록에 없다. 촬영 직후 검사가 "
                   "닫혔는지(Step 2)와 제품 인덱싱 지연을 먼저 볼 것 — 첫 행을 "
                   "대신 쓰면 **이전 실행의 스터디를 Export**하게 되므로 그렇게 "
                   "하지 않는다.")
        r.finalize()
        return r
    else:
        W.click_row(ui, picked["row"])
        r.add(step, "Database에서 Export 대상 스터디 선택 (Patient ID로 지목)", PASS,
              expected="Patient ID=%s 인 행" % want_pid,
              actual="%s / %s" % (summary, picked.get("note")),
              note="목록 정렬이나 인덱싱 지연에 관계없이 **이번 실행의 스터디**를 "
                   "대상으로 삼는다.")
    step += 1

    # --- Step 3: Export 실행 -------------------------------------------
    # Export(30300)도 Send/Print와 같은 확인 팝업(All Images/Selected/Cancel,
    # 27002/27001/27000)을 띄운다(실측 2026-08-21) — 눌러 주지 않으면 Export
    # Manager 프로세스 자체가 뜨지 않는다(Print의 #21049류 재발과 겉모습이
    # 같아 보이지만 원인은 확인 누락이었다).
    try:
        W.db_button(ui, "export", settle=3.0)
        W.confirm_scope_popup(ui, scope="all")
    except Exception as exc:                              # noqa: BLE001
        r.add(step, "Export 실행 (Database > Export)", FAIL, actual=str(exc))
        r.finalize()
        return r

    popups = W.pending_dialogs(ui, evidence_dir=evidence_dir, cfg=cfg)
    # 25초는 전체 회귀처럼 앞서 TC를 여럿 돈 뒤(메모리 압박, README 4절)라면
    # 부족할 수 있다(실측 2026-08-21: 개별 실행은 항상 25초 안에 떴지만, 전체
    # 회귀 중에는 그 뒤에 열려 BLOCKED로 남고 창만 뒤늦게 나타났다). 45초로
    # 넉넉히 늘린다 — 정상 상황에서는 어차피 훨씬 빨리 뜬다.
    mgr_up, mgr_note = _wait_manager(proc_name, timeout=45)
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
                  "팝업 문구를 증거로 남겼으니 원본 이슈와 대조할 것."
                  % KNOWN_DEFECT if defect_hit else
                  "체크리스트 Comment의 알려진 결함 %s는 이번 실행에서 에러 팝업으로 "
                  "재현되지 않았다." % KNOWN_DEFECT))
    step += 1

    if not mgr_up:
        r.add(step, "Export 산출물 검증", BLOCKED,
              note="Export Manager 창이 열리지 않아 이후 단계를 수행할 수 없다.")
        r.finalize()
        return r

    # --- Step 4: Export Manager에서 드라이브·경로·형식 지정 후 Start -----
    exp = _run_export_manager(proc_name, dest)
    r.add(step, "Export Manager에서 대상 드라이브·경로·형식(DICOM+IMG) 지정 및 Start",
          PASS if (exp["ok"] and exp.get("path_ok")) else
          (FAIL if exp.get("path_before") is not None else MANUAL),
          expected="Export Path=%s / IMG 형식 포함 / Start 후 Current State=Done" % dest,
          actual="path_before=%r / path_final=%r / format_ok=%s / start 후 상태=%r"
                 % (exp.get("path_before"), exp.get("path_final"),
                    exp.get("format_ok"), exp.get("state")),
          note=exp.get("note") or "")
    step += 1

    # --- Step 5: 산출물 검증 --------------------------------------------
    actual_dir = exp.get("path_final") or dest
    dir_matches_snapshot = (os.path.normcase(os.path.normpath(actual_dir))
                            == os.path.normcase(os.path.normpath(dest)))
    if dir_matches_snapshot:
        added = [p for p in _walk(actual_dir) if p not in before]
        diff_note = ""
    else:
        added = _walk(actual_dir) if os.path.isdir(actual_dir) else []
        diff_note = (" **실제 대상 폴더가 Step 0에서 스냅샷한 폴더와 달라(%s) "
                    "'이번 실행의 신규 파일'이 아니라 그 폴더의 전체 목록이다.**"
                    % actual_dir)
    dicoms = []
    imgs = [p for p in added if p.lower().endswith(".img")]
    for path in added:
        try:
            with open(path, "rb") as f:
                if f.read(132)[128:132] == b"DICM":
                    dicoms.append(path)
        except OSError:
            continue
    # 태그 대조는 가장 큰 DICOM 파일로 한다 — 같은 검사에서 Dose SR(수 KB)도
    # 함께 Export되므로(Include Dose SR 기본 ON, 실측) 크기순 정렬 없이 첫 번째를
    # 쓰면 영상이 아니라 SR 객체를 집어 태그가 비어 보일 수 있다(실측 재현).
    dicoms.sort(key=lambda p: os.path.getsize(p), reverse=True)
    r.add(step, "Export 산출물 생성 확인",
          PASS if added else MANUAL,
          expected="대상 폴더(%s)에 파일이 생성된다" % actual_dir,
          actual="신규 파일 %d개 (DICOM %d개, IMG %d개)"
                 % (len(added), len(dicoms), len(imgs)),
          note=("Export Manager Start가 성공하지 못했다." if not exp["ok"] else "표시 확인됨.")
               + diff_note)
    step += 1

    r.add(step, "IMG 형식 Export 확인 (VXvue 자체 Import의 유일한 전제조건)",
          PASS if imgs else MANUAL,
          expected="S{Series}I{Instance}.img 파일 1개 이상",
          actual="%d개: %s" % (len(imgs), [os.path.basename(p) for p in imgs[:3]]),
          note="Operation Manual 8.14: 'VXvue에서 생성된 IMG 파일만 가져올 수 "
               "있습니다.' DICOM만 Export하면 파일은 생성돼도 뷰어로 다시 가져올 "
               "방법이 없다 — 이 파일이 있어야 Step 6(역방향 Import)이 원칙적으로 "
               "가능하다.")
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
                   "증거로 남는다.")
        r.attach(dicoms[0])
        step += 1

        # 실측 2026-08-21: 이 매체에 실제로 들어간 포터블 뷰어는 아래 두 파일이다.
        #   E:\VXvue_QA_Export\PV.Loader.exe        (루트 로더, 140KB)
        #   E:\VXvue_QA_Export\PortView\QXL.PV.exe  (뷰어 본체, 25MB)
        # **파일명에 'qxlink'가 들어가지 않는다** — 그 이름으로 찾던 이전 판정은
        # 뷰어가 정상 포함돼 있어도 항상 MANUAL이었다(Result_20260821_145739).
        # 그리고 뷰어는 매체에 **한 번만** 기록되므로 '이번 실행의 신규 파일'에서
        # 찾으면 두 번째 실행부터 못 찾는다 → 대상 폴더 전체에서 확인한다.
        viewer_all = _walk(actual_dir) if os.path.isdir(actual_dir) else []
        qx = [p for p in viewer_all
              if os.path.basename(p).lower() in PORTABLE_VIEWER_FILES
              or os.path.basename(p).lower().startswith("qxl.")]
        fresh_qx = [p for p in qx if p in added]
        r.add(step, "Portable viewer(QXLink) 포함 확인",
              PASS if qx else MANUAL,
              expected="Export 산출물에 포터블 뷰어(%s) 포함"
                       % ", ".join(sorted(PORTABLE_VIEWER_FILES)),
              actual="%d개: %s%s"
                     % (len(qx), [os.path.basename(p) for p in qx[:4]],
                        "" if fresh_qx else " (이번 실행의 신규 파일은 아니다 — "
                                           "뷰어는 매체에 한 번만 기록된다)"),
              note="체크리스트 Test Data: 'CD 안의 QXlink portable viewer 가 정상 "
                   "실행되는지 확인할것.' — **실행 여부는 사람이 확인해야 한다**"
                   "(외부 실행 파일을 자동으로 띄우지 않는다). 자동화는 포함 여부까지 "
                   "확인한다. Export Manager의 'Portable Viewer' 옵션을 켜야 "
                   "포함되므로, 포함되지 않았다면 그 옵션 상태를 함께 확인할 것.")
        step += 1

    # --- Step 6: 역방향 Import (Expected Result 2) ----------------------
    # 사용자 지시(2026-08-21): "Export 실행부터 산출물 검증, 역방향 Import까지
    # 전부 자동 판정되게." 이전 세션까지는 "DB에 데이터를 추가하는 조작"이라
    # 고정 MANUAL로 남겨 뒀지만, 이것이 체크리스트 Step 2 자체(`CD/USB에 Export
    # 된 스터디를 선택 후 뷰어로 import 한다`)이므로 지시대로 자동 수행한다.
    # 되돌리기가 필요하면 `core/dbreset.py`의 백업/복원을 쓴다.
    #
    # 판정 근거 세 가지를 함께 본다(실측 2026-08-21):
    #  1. 결과 팝업 문구 `Succeed to import the studies.`
    #  2. Import Study 목록의 **각 열 값이 Export한 DICOM 태그와 일치**
    #     (사용자 지시: "각 열의 정보가 export 한 정보와 동일하게 나오면")
    #  3. Database 조회 건수 증가
    if not do_import:
        r.add(step, "Export된 스터디를 뷰어로 Import", MANUAL,
              expected="Database > Import로 되읽기 성공",
              actual="--no-import로 실행되어 수행하지 않음 (IMG %d개 확보됨)"
                     % len(imgs),
              note="Import를 건너뛰면 체크리스트 Expected Result 2를 확인하지 "
                   "못한다 — 반복 디버깅용 옵션이다.")
    else:
        want_cols = {}
        if dicoms:
            src = dicomlite.read_tags(dicoms[0],
                                      ["PatientID", "PatientName",
                                       "AccessionNumber", "PatientBirthDate",
                                       "PatientSex"])
            want_cols = {"Patient ID": str(src.get("PatientID") or ""),
                         "Patient Name": str(src.get("PatientName") or ""),
                         "Acc. No.": str(src.get("AccessionNumber") or ""),
                         "Birth Date": str(src.get("PatientBirthDate") or ""),
                         "Sex": str(src.get("PatientSex") or "")}
            want_cols = {k: v for k, v in want_cols.items() if v}
        try:
            imp = W.import_studies(ui, cfg, actual_dir, expected=want_cols,
                                   scope="selected", evidence_dir=evidence_dir)
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "Export된 스터디를 뷰어로 Import", FAIL,
                  actual="%s: %s" % (type(exc).__name__, exc))
        else:
            m = imp.get("match") or {}
            r.add(step, "Export된 스터디를 뷰어로 Import (열 값 대조 포함)",
                  PASS if imp.get("ok") else FAIL,
                  expected=("Location=%s / 목록 열 값이 Export 태그와 일치(%s) / "
                            "결과 팝업이 성공" % (actual_dir, sorted(want_cols)))
                           if want_cols else
                           "Location=%s / 결과 팝업이 성공" % actual_dir,
                  actual=imp.get("note"),
                  note="Location은 표시 전용 Edit이라 타이핑이 통하지 않아 "
                       "`...`의 표준 폴더 찾아보기 트리에서 지정한다 — 그 트리는 "
                       "OCR이 한글·잘린 라벨에서 틀리므로 `core/shelltree.py`가 "
                       "`TVM_*` 메시지로 노드를 정확히 읽는다. 목록 열 값은 "
                       "`core/listgrid.py`가 헤더(`SysHeader32`)에서 열 경계를 "
                       "얻어 셀 단위로 읽고, 값이 `...`로 잘려 보이면 그 열의 "
                       "경계선을 드래그해 넓혀 다시 읽은 뒤 원래 폭으로 "
                       "되돌린다(사용자 지시, 2026-08-21). 읽은 값: %s"
                       % (imp.get("row_values") or "(못 읽음)"))
            if m.get("partial"):
                r.attach("열이 끝까지 잘려 접두만 대조한 항목: %s"
                         % sorted(m["partial"]))
        step += 1

    # --- Step 7: 매체 정리 — Export 산출물 삭제 -------------------------
    # 사용자 지시(2026-08-21): *"export/import 테스트가 완료되면 실제 E드라이브에
    # export 했던 파일은 삭제까지 해주라."* 남겨 두면 (1) 매체가 계속 차고
    # (2) 다음 실행의 Import 목록에 이전 스터디가 섞여 "어느 것이 이번 것인지"가
    # 흐려진다(오늘 실제로 그 혼란이 있었다).
    #
    # 파괴적 조작이므로 범위를 좁게 못 박는다 — 지우는 대상은 **config의
    # `export.dest_dir` 그 폴더 안**뿐이고, 드라이브 루트이거나 설정된 폴더 이름과
    # 다르면 아무것도 지우지 않는다. `--keep-export`로 끌 수 있다.
    if not purge_export:
        r.add(step, "매체 정리 — Export 산출물 삭제", SKIP,
              note="--keep-export로 실행되어 %s를 그대로 남겼다." % actual_dir)
    else:
        purge = _purge_export_dir(actual_dir, dest)
        r.add(step, "매체 정리 — Export 산출물 삭제",
              PASS if purge["ok"] else MANUAL,
              expected="%s 안의 Export 산출물 삭제" % actual_dir,
              actual=purge["note"],
              note="사용자 지시(2026-08-21). 남겨 두면 다음 실행의 Import 목록에 "
                   "이전 스터디가 섞여 판정 근거가 흐려진다. **삭제 범위는 설정된 "
                   "Export 대상 폴더 안뿐**이며, 드라이브 루트이거나 설정과 다른 "
                   "경로면 아무것도 지우지 않는다.")

    r.finalize()
    return r


def _purge_export_dir(actual_dir, configured_dest):
    """Export 대상 폴더 **안의 내용만** 지운다(폴더 자체는 남긴다).

    안전장치:
      * 경로에 폴더명이 없으면(드라이브 루트) 거부한다.
      * 설정된 `export.dest_dir`의 폴더명과 다르면 거부한다 — 엉뚱한 경로를
        지우지 않기 위한 최소 조건이다.

    반환: {"ok", "files", "bytes", "note"}
    """
    import shutil
    want_name = os.path.basename(os.path.normpath(configured_dest or ""))
    have_name = os.path.basename(os.path.normpath(actual_dir or ""))
    if not have_name or len(os.path.normpath(actual_dir)) <= 3:
        return {"ok": False, "files": 0, "bytes": 0,
                "note": "대상이 드라이브 루트로 보여 삭제하지 않았다(%r)." % actual_dir}
    if want_name and have_name.lower() != want_name.lower():
        return {"ok": False, "files": 0, "bytes": 0,
                "note": ("실제 대상(%s)이 설정된 Export 폴더명(%s)과 달라 "
                         "삭제하지 않았다." % (have_name, want_name))}
    if not os.path.isdir(actual_dir):
        return {"ok": True, "files": 0, "bytes": 0,
                "note": "폴더가 없어 지울 것이 없었다(%s)." % actual_dir}
    files = _walk(actual_dir)
    total = 0
    for path in files:
        try:
            total += os.path.getsize(path)
        except OSError:
            pass
    errors = []
    for name in os.listdir(actual_dir):
        target = os.path.join(actual_dir, name)
        try:
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
        except OSError as exc:
            errors.append("%s: %s" % (name, exc))
    left = _walk(actual_dir)
    ok = not left
    return {"ok": ok, "files": len(files), "bytes": total,
            "note": ("%s 안 %d개 파일(%.1fMB) 삭제%s"
                     % (actual_dir, len(files), total / 1048576.0,
                        "" if ok else " — 남은 파일 %d개 %s"
                                     % (len(left), errors[:3])))}


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
