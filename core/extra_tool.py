# -*- coding: utf-8 -*-
"""Setting > Integration > Extra Tool 화면 자동화 (TC06).

실측(2026-08-24, `work/probe_extra_tool.py` 및 스크롤 캡처): DICOM
MWL/Storage/Print(core/dicom_settings.py)와 컨트롤 ID 체계를 공유하지
않는 완전히 별도 화면이다(VP-698, 사양서4 p.74-75) — Name 필드가 없고
Max PDU/Retry Count/Timeout/Verification Timeout, Options(LUT/Modality/
DAP Unit Type/Software Collimation/Burning Option/Transfer Syntax/
Language/Compression/Image bits/DICOM Option) 전부 이 화면 전용이다.

| 항목 | 컨트롤 ID | 확인 방법 |
|---|---|---|
| Use extra tool(최상단 마스터) | 31516 | 캡처로 라벨 확인, 기본 체크 상태였음 |
| AE Title Edit | 30092 | |
| IP Address Edit | 30097 | |
| Port Edit | 30098 | |
| Echo | 30780 | DICOM 화면들과 같은 ID(공용 버튼) |
| S.B.S.C.(행 라벨"Remove Image Processing") | 31523 | 체크박스 자체 캡션이 "S.B.S.C."임을 캡처로 확인 |

Update는 화면 공용 버튼(`core.setting.UPDATE_BUTTON_ID`, 30641)을 그대로
쓴다. Echo 판정은 Verification 로그가 owner-draw라 dicom_settings.echo()와
동일하게 캡처+OCR로 한다.

사용자 지시(2026-08-24): Extra Tool 서버는 Storage SCP(Bunny: AE
Title=Bunny, IP=10.201.0.139, Port=3000)와 동일하게 등록한다. 실측 결과
AE Title 필드에는 이미 "Bunny"가 입력돼 있었고(이전 세션의 미완료 작업으로
추정) IP/Port는 비어 있었다 — `configure()`가 세 필드 모두 지정값으로
덮어써 확정한다.
"""

import time

from . import setting as S

SCREEN_TITLE = "Integration - Extra Tool"

MASTER_CHECK_ID = 31516
AE_TITLE_EDIT_ID = 30092
IP_EDIT_ID = 30097
PORT_EDIT_ID = 30098
ECHO_BUTTON_ID = 30780
SBSC_CHECK_ID = 31523


class ExtraToolError(RuntimeError):
    pass


def _field(ui, cid):
    """dicom_settings._field()와 동일한 이유로 필요하다: Extra Tool 화면은
    길어서(Options 섹션까지) 스크롤 없이는 Echo/S.B.S.C.가 화면 밖에 있다
    — content_controls()가 돌려주는 rect를 스크롤 없이 그대로 클릭하면
    그 좌표에 실제로 보이는 다른 컨트롤을 클릭하게 된다.
    """
    found = [c for c in S.content_controls(ui) if c.ctrl_id == cid]
    if not found:
        return None
    ctrl = found[0]
    dlg = S.content_dialog(ui)
    if dlg is None:
        return ctrl
    for _ in range(12):
        if S.in_viewport(ctrl, dlg.rect):
            return ctrl
        S.scroll_down(ui)
        again = [c for c in S.content_controls(ui) if c.ctrl_id == cid]
        if not again:
            return ctrl
        ctrl = again[0]
    return ctrl


def _open_screen(ui):
    if not S.open_setting(ui):
        raise ExtraToolError("Setting 화면 진입 실패")
    minor = S.goto_screen(ui, SCREEN_TITLE)
    if minor is None:
        raise ExtraToolError("%s 화면을 찾지 못함" % SCREEN_TITLE)
    S.scroll_to_top(ui)
    return minor


def ensure_enabled(ui):
    """'Use extra tool' 마스터 체크박스가 켜져 있는지 확인하고, 꺼져 있으면 켠다.

    owner-draw 체크박스라 `core.setting.checkbox_checked()`(캡처 기반)로
    실제 상태를 읽는다 — 이미 켜져 있는데 또 누르면 꺼지므로 무조건 클릭하면
    안 된다(다른 체크박스들과 같은 함정).
    """
    ctrl = _field(ui, MASTER_CHECK_ID)
    if ctrl is None:
        return False, "'Use extra tool' 체크박스(%d)를 찾지 못함" % MASTER_CHECK_ID
    checked = S.checkbox_checked(ui, ctrl)
    if checked:
        return True, "이미 켜져 있음"
    ui.click(ctrl, settle=0.5)
    ctrl = _field(ui, MASTER_CHECK_ID)
    now = S.checkbox_checked(ui, ctrl) if ctrl is not None else None
    if now is not True:
        return False, "클릭했지만 켜지지 않음(캡처 확인 결과 checked=%r)" % now
    return True, "꺼져 있어 클릭으로 켬"


def configure(ui, ae_title, ip, port, ack_timeout=10):
    """AE Title/IP/Port를 지정값으로 설정하고 Update한다.

    반환: (성공 여부, 메모).
    """
    _open_screen(ui)

    ok, note = ensure_enabled(ui)
    if not ok:
        return False, note

    S.scroll_to_top(ui)
    ae_edit = _field(ui, AE_TITLE_EDIT_ID)
    ip_edit = _field(ui, IP_EDIT_ID)
    port_edit = _field(ui, PORT_EDIT_ID)
    if not all((ae_edit, ip_edit, port_edit)):
        return False, "입력 필드(AE Title/IP/Port)를 찾지 못함"

    ui.type_ascii(ae_edit, ae_title, clear=True)
    ui.type_ascii(ip_edit, ip, clear=True)
    ui.type_ascii(port_edit, str(port), clear=True)

    ack = S.update(ui, ack_timeout=ack_timeout)
    return True, "Update 완료(팝업: %s) [마스터 체크박스: %s]" % (ack or "없음", note)


def set_sbsc(ui, checked, ack_timeout=10):
    """S.B.S.C.(Remove Image Processing) 체크박스를 지정 상태로 맞추고 Update한다.

    실제 상태를 먼저 읽어(`core.setting.checkbox_checked()`) 이미 원하는
    상태면 클릭하지 않는다. 반환: (성공 여부, 메모).
    """
    _open_screen(ui)
    ctrl = _field(ui, SBSC_CHECK_ID)
    if ctrl is None:
        return False, "S.B.S.C. 체크박스(%d)를 찾지 못함" % SBSC_CHECK_ID
    now = S.checkbox_checked(ui, ctrl)
    if now == checked:
        return True, "이미 목표 상태(checked=%r)" % checked
    ui.click(ctrl, settle=0.5)
    ctrl = _field(ui, SBSC_CHECK_ID)
    after = S.checkbox_checked(ui, ctrl) if ctrl is not None else None
    if after != checked:
        return False, "클릭 후에도 목표 상태에 도달하지 못함(checked=%r)" % after
    ack = S.update(ui, ack_timeout=ack_timeout)
    return True, "Update 완료(팝업: %s)" % (ack or "없음")


def echo(ui, timeout=15, poll=1.0, evidence_path=None):
    """등록된 Extra Tool 대상에 Echo를 보내고 성공 여부를 판정한다.

    `core.dicom_settings.echo()`와 동일한 OCR 판정 방식(owner-draw
    Verification 로그라 표준 API로 셀 텍스트를 읽을 수 없음).
    """
    _open_screen(ui)
    echo_btn = _field(ui, ECHO_BUTTON_ID)
    if echo_btn is None:
        return False, "Echo 버튼(%d)을 찾지 못함" % ECHO_BUTTON_ID

    boxes = [c for c in S.content_controls(ui) if c.text.strip() == "GroupBox"]
    ex, ey = echo_btn.center
    containing = [b for b in boxes
                 if b.rect[0] <= ex <= b.rect[2] and b.rect[1] <= ey <= b.rect[3]]
    panel_rect = None
    if containing:
        panel_rect = min(containing, key=lambda b: (b.rect[2] - b.rect[0]) * (b.rect[3] - b.rect[1])).rect

    ui.click(echo_btn, settle=1.0)
    if panel_rect is None:
        time.sleep(timeout)
        return False, "로그 영역을 찾지 못해 OCR 확인 불가(캡처 없이 %ds 대기만 함)" % timeout

    from PIL import ImageGrab
    try:
        import pytesseract
        import os
        default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_tess):
            pytesseract.pytesseract.tesseract_cmd = default_tess
    except ImportError:
        pytesseract = None

    from . import screen as screen_mod

    end = time.time() + timeout
    last_text = ""
    contaminated_once = False
    while time.time() < end:
        time.sleep(poll)
        ui.ensure_foreground()
        img = ImageGrab.grab(bbox=panel_rect, all_screens=True)
        if evidence_path:
            img.save(evidence_path)
        if pytesseract is None:
            continue
        try:
            text = pytesseract.image_to_string(img)
        except Exception as e:                                   # noqa: BLE001
            return False, "OCR 실행 실패: %s" % e
        if screen_mod.looks_contaminated(text):
            contaminated_once = True
            continue
        last_text = text
        lowered = last_text.lower()
        if "verification succeeded" in lowered or "succeeded" in lowered:
            return True, last_text.strip()[-500:]
        if "failed" in lowered or "refused" in lowered:
            return False, last_text.strip()[-500:]
    note = "시간 내 성공/실패 문구를 찾지 못함: %s" % last_text.strip()[-500:]
    if contaminated_once:
        note += " [주의: 캡처 중 다른 창이 겹친 것으로 보이는 프레임을 제외했다]"
    return False, note
