# -*- coding: utf-8 -*-
"""Setting > DICOM > MWL/Storage/Print SCP 등록 자동화.

지금까지(2026-08-18 세션들)는 이 등록을 전부 사람이 손으로 했다 —
`automation_scope.json`의 "MWL_SCP 등록·Echo 검증 완료" 같은 서술은 그
수동 작업의 기록이다. 전체 회귀를 클린 DB(baseline)에서부터 돌리려면
이 등록을 자동으로 재현해야 한다(사용자 지시, 2026-08-19).

실측(2026-08-19, `python run.py ui-probe`로 세 화면 대조): MWL/Storage/
Print 세 화면이 SCP 등록에 필요한 컨트롤 ID를 공유한다 — 화면마다 그 외
필드 개수·배치는 다르지만(Print는 필드가 더 많다, 설계문서 3.4.6절),
등록에 필요한 최소 4개 필드 + 버튼 3개는 세 화면 모두 같은 ID다.

| 항목 | 컨트롤 ID | 확인 방법 |
|---|---|---|
| Add | 30440 | 캡처로 "Add" 라벨 확인 |
| Delete | 30441 | 캡처로 "Delete" 라벨 확인 |
| Echo | 30780 | 캡처로 "Echo" 라벨 확인 |
| Name Edit | 30090 | |
| AE Title Edit | 30092 | |
| IP Address Edit | 30097 | |
| Port Edit | 30098 | |

Update는 화면 공용 버튼(`core.setting.UPDATE_BUTTON_ID`, 30641)을 그대로
쓴다. Verification Log는 owner-draw ListCtrl이라 표준 API로 셀 텍스트를
읽을 수 없어(TC13/TC14와 같은 한계) 캡처+OCR(pytesseract)로 판정한다.
"""

import time

from . import setting as S

SCREEN_TITLES = {
    "MWL": "DICOM - MWL",
    "Storage": "DICOM - Storage",
    "Print": "DICOM - Print",
}
DB_TYPE = {
    "MWL": "DICOM_MWL",
    "Storage": "DICOM_STORAGE",
    "Print": "DICOM_PRINT",
}

ADD_BUTTON_ID = 30440
DELETE_BUTTON_ID = 30441
ECHO_BUTTON_ID = 30780
NAME_EDIT_ID = 30090
AE_TITLE_EDIT_ID = 30092
IP_EDIT_ID = 30097
PORT_EDIT_ID = 30098

# DICOM - Storage 전용: "Burning Option" 아래 체크박스 3개(실측 2026-08-19,
# 캡처로 라벨 확인). Annotation(31503)/Information(31504)이 한 행, 그
# 바로 아래 Orientation(31505)이 있다 — 사용자 지시로 셋 다 체크한다.
BURNING_OPTION_CHECK_IDS = {
    31503: "Annotation",
    31504: "Information",
    31505: "Orientation",
}


class DicomSettingsError(RuntimeError):
    pass


def _field(ui, cid):
    found = [c for c in S.content_controls(ui) if c.ctrl_id == cid]
    if not found:
        return None
    ctrl = found[0]

    # 실측(2026-08-19, 사용자 지적): DICOM - Storage 화면은 Options 섹션이
    # 길어서 Echo 버튼이 스크롤 없이는 화면 밖에 있다(설계문서 3.4.5절과
    # 동일). `content_controls()`는 스크롤 밖 컨트롤도 rect를 그대로 돌려주므로,
    # 스크롤하지 않고 그 rect를 그대로 클릭하면 그 좌표에 실제로 보이는
    # **다른 컨트롤**을 클릭하게 된다 — Storage Echo가 매번 엉뚱한
    # "Not Exposure Mode" 팝업을 띄운 원인이었다. 클릭 대상은 항상 뷰포트
    # 안으로 스크롤해서 끌어온 뒤 반환한다.
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


def _open_screen(ui, kind):
    title = SCREEN_TITLES[kind]
    if not S.open_setting(ui):
        raise DicomSettingsError("Setting 화면 진입 실패")
    minor = S.goto_screen(ui, title)
    if minor is None:
        raise DicomSettingsError("%s 화면을 찾지 못함" % title)
    S.scroll_to_top(ui)
    return title


def _scp_list_ctrl(ui, add_btn):
    """Add 버튼과 같은 세로 열(x 범위)에서, 그 버튼보다 위에 있는 목록.

    화면마다 SCP 목록의 컨트롤 ID가 다를 수 있어(실측 확인 안 됨) 좌표
    관계로 찾는다 — Add/Delete 버튼은 항상 SCP 목록 바로 아래에 있다.
    """
    ax1, ay1, ax2, _ = add_btn.rect
    candidates = [c for c in S.content_controls(ui) if c.text.strip() == "ListCtrl"
                 and c.rect[1] < ay1 and c.rect[0] < ax2 and c.rect[2] > ax1]
    if not candidates:
        return None
    return min(candidates, key=lambda c: ay1 - c.rect[1])


def _log_panel_rect(ui, echo_btn):
    """Echo 버튼을 담고 있는 가장 안쪽 GroupBox의 rect(Verification Log 영역).

    화면마다 로그 목록의 컨트롤 ID가 다를 수 있어 캡처 범위를 좌표 관계로
    정한다 — Echo 버튼은 항상 그 로그를 보여주는 GroupBox 안에 있다.
    """
    boxes = [c for c in S.content_controls(ui) if c.text.strip() == "GroupBox"]
    ex, ey = echo_btn.center
    containing = [b for b in boxes
                 if b.rect[0] <= ex <= b.rect[2] and b.rect[1] <= ey <= b.rect[3]]
    if not containing:
        return None
    return min(containing, key=lambda b: (b.rect[2] - b.rect[0]) * (b.rect[3] - b.rect[1])).rect


def add_server(ui, kind, name, ae_title, ip, port, ack_timeout=10):
    """SCP 하나를 등록한다(Add → 필드 입력 → Update).

    실측(설계문서 3.4.4절)과 동일한 함정: Update 뒤 "DICOM - ... Update
    successfully." Info 팝업이 뜨고 닫기 전엔 이후 클릭이 무시된다 —
    `core.setting.update()`(→`ui.click_and_ack()`)가 이미 처리한다.
    반환: (성공 여부, 메모)
    """
    _open_screen(ui, kind)

    add_btn = _field(ui, ADD_BUTTON_ID)
    if add_btn is None:
        return False, "Add 버튼(%d)을 찾지 못함" % ADD_BUTTON_ID
    ui.click(add_btn, settle=0.8)

    name_edit = _field(ui, NAME_EDIT_ID)
    ae_edit = _field(ui, AE_TITLE_EDIT_ID)
    ip_edit = _field(ui, IP_EDIT_ID)
    port_edit = _field(ui, PORT_EDIT_ID)
    if not all((name_edit, ae_edit, ip_edit, port_edit)):
        return False, "입력 필드(Name/AE Title/IP/Port)를 찾지 못함"

    # 실측(2026-08-24, TC06 Extra Tool 개발 중): `type_text()`가 쓰는
    # `_unicode_char()`(SendInput 유니코드 주입)는 IP Address류 필드의 자체
    # 입력 검증기를 통과하지 못해 필드가 계속 비어 있는 채로 "Update
    # successfully" 팝업만 뜨는 조용한 실패가 있었다(core/ui.py
    # `type_ascii()` 참고) — 실제 VK 코드 기반 입력으로 바꾼다. Name/AE
    # Title/IP/Port 전부 ASCII 값만 쓰므로(config.json 확인) 안전하다.
    ui.type_ascii(name_edit, name, clear=True)
    ui.type_ascii(ae_edit, ae_title, clear=True)
    ui.type_ascii(ip_edit, ip, clear=True)
    ui.type_ascii(port_edit, str(port), clear=True)

    ack = S.update(ui, ack_timeout=ack_timeout)
    return True, "Update 완료(팝업: %s)" % (ack or "없음")


def select_first_row(ui, kind):
    """이미 등록된 SCP가 1건일 때, 그 행을 클릭해 선택한다(Echo 대상 지정).

    이 프로젝트는 서버당 등록 1건만 관리하므로(config.json
    `dicom.servers_to_register`), 행이 1개면 모호함이 없다. 2건 이상이면
    어떤 행인지 확정할 수 없어(목록 셀 텍스트를 못 읽음) 손대지 않는다.
    """
    _open_screen(ui, kind)
    add_btn = _field(ui, ADD_BUTTON_ID)
    if add_btn is None:
        return False, "Add 버튼을 찾지 못해 목록 위치를 특정할 수 없음"
    list_ctrl = _scp_list_ctrl(ui, add_btn)
    if list_ctrl is None:
        return False, "SCP 목록을 찾지 못함"
    rows = S.list_rows(ui, list_ctrl)
    if len(rows) != 1:
        return False, "등록된 행이 %d개라 자동으로 선택하지 않음(1개일 때만 선택)" % len(rows)
    ui.click(S.row_click_point(ui, rows[0]), settle=0.6)
    return True, "행 선택 완료"


def echo(ui, kind, timeout=15, poll=1.0, evidence_path=None):
    """선택된 SCP에 Echo를 보내고 성공 여부를 판정한다.

    Verification 로그는 owner-draw라 표준 API로 읽을 수 없어, Echo 클릭
    후 로그 영역을 주기적으로 캡처해 pytesseract로 'succeeded'/'failed'
    문구를 찾는다(TC13의 Reserved 목록 확인과 같은 방식).
    """
    _open_screen(ui, kind)
    echo_btn = _field(ui, ECHO_BUTTON_ID)
    if echo_btn is None:
        return False, "Echo 버튼(%d)을 찾지 못함" % ECHO_BUTTON_ID

    panel_rect = _log_panel_rect(ui, echo_btn)
    ui.click(echo_btn, settle=1.0)
    if panel_rect is None:
        time.sleep(timeout)
        return False, "로그 영역을 찾지 못해 OCR 확인 불가(캡처 없이 %ds 대기만 함)" % timeout

    from PIL import ImageGrab
    try:
        import pytesseract
        default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        import os
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
        # 캡처 직전 다시 foreground를 확인한다 — 실측(2026-08-21)으로,
        # VXvue를 foreground로 올린 뒤에도 폴링 중 다른 창(터미널 등)이
        # 잠깐 그 자리를 덮어 OCR이 그 창의 내용을 읽은 사례가 있었다.
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
        note += " [주의: 캡처 중 다른 창이 겹친 것으로 보이는 프레임을 " \
                "제외했다 — 이 결과는 오염 없는 캡처만으로 판정한 것이다]"
    return False, note


def ensure_burning_options(ui, ack_timeout=10):
    """DICOM - Storage의 Burning Option(Annotation/Information/Orientation)을
    모두 체크한다(사용자 지시, 2026-08-19).

    체크박스는 owner-draw라 표준 API로 현재 상태를 읽을 수 없다 —
    `core.setting.checkbox_checked()`(캡처 기반 판별)로 이미 체크됐는지
    먼저 확인하고, 체크 안 된 것만 클릭한다(이미 체크된 걸 다시 누르면
    꺼져 버리므로 무조건 클릭하면 안 된다). 다 확인한 뒤 **Update를 눌러야
    실제로 적용된다**(사용자 지시) — 이 함수가 마지막에 Update까지 누른다.

    반환: (dict(ctrl_id: {"label", "was_checked", "now_checked"}), update_ack)
    """
    _open_screen(ui, "Storage")
    detail = {}
    for cid, label in BURNING_OPTION_CHECK_IDS.items():
        ctrl = _field(ui, cid)
        if ctrl is None:
            detail[cid] = {"label": label, "was_checked": None, "now_checked": None,
                          "note": "컨트롤을 찾지 못함"}
            continue
        was = S.checkbox_checked(ui, ctrl)
        if not was:
            ui.click(ctrl, settle=0.4)
            ctrl2 = _field(ui, cid)
            now = S.checkbox_checked(ui, ctrl2) if ctrl2 is not None else None
        else:
            now = was
        detail[cid] = {"label": label, "was_checked": was, "now_checked": now}

    ack = S.update(ui, ack_timeout=ack_timeout)
    return detail, ack


def ensure_bunny_running(cfg, wait=5):
    """Storage(Bunny) 수신은 이 PC에서 Bunny.exe가 떠 있어야 포트가 열린다
    (설계문서 3.4.5절 실측). 실측(2026-08-19): Bunny가 안 떠 있으면 Echo가
    "Not Exposure Mode"류 문구와 함께 실패한다 — 안 떠 있으면 설치 폴더를
    작업 디렉터리로 실행한다(상대 경로로 Log/Receive 폴더를 만들기 때문에
    설치 폴더에서 실행해야 한다, README 6절 규칙과 동일).
    """
    import os
    import subprocess
    import time

    bunny_cfg = (cfg.get("dicom") or {}).get("bunny") or {}
    app_path = bunny_cfg.get("app_path")
    if not app_path or not os.path.exists(app_path):
        return False, "Bunny 실행 파일 경로가 설정되지 않았거나 없음: %s" % app_path

    check = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "if (Get-Process Bunny -ErrorAction SilentlyContinue) { 'RUNNING' }"],
        capture_output=True)
    if check.stdout.decode("utf-8", "replace").strip() == "RUNNING":
        return True, "이미 실행 중"

    subprocess.Popen([app_path], cwd=os.path.dirname(app_path))
    time.sleep(wait)
    return True, "실행함(대기 %ds)" % wait


def ensure_registered(ui, cfg, db, echo_timeout=15):
    """`config.json`의 `dicom.servers_to_register`를 확인하고, 없으면 등록한다.

    각 서버에 대해: (1) DB(AE_LIST)에 이미 있는지 확인 → 없으면 `add_server()`.
    (2) 있으면(또는 막 등록했으면) 목록에서 그 행을 선택하고 `echo()`로
    실제 연결까지 확인한다. 반환: [{"kind","name","registered","echo_ok","note"}, ...]
    """
    results = []
    specs = (cfg.get("dicom") or {}).get("servers_to_register") or []
    for spec in specs:
        kind = spec["kind"]

        note_parts = []
        if kind == "Storage":
            bunny_ok, bunny_note = ensure_bunny_running(cfg)
            note_parts.append("Bunny: %s" % bunny_note)
            if not bunny_ok:
                results.append({"kind": kind, "name": spec["name"], "registered": False,
                               "echo_ok": False, "note": "; ".join(note_parts)})
                continue

        rows = db.ae_list(DB_TYPE.get(kind))
        exists = any(str(r.get("Title")) == str(spec["ae_title"])
                    and str(r.get("Port")) == str(spec["port"]) for r in rows)

        if not exists:
            ok, note = add_server(ui, kind, spec["name"], spec["ae_title"],
                                  spec["ip"], spec["port"])
            note_parts.append("등록 시도: %s" % note)
            if not ok:
                results.append({"kind": kind, "name": spec["name"], "registered": False,
                               "echo_ok": False, "note": "; ".join(note_parts)})
                continue
        else:
            sel_ok, sel_note = select_first_row(ui, kind)
            note_parts.append("기존 등록 확인, 행 선택: %s" % sel_note)

        if kind == "Storage":
            burn_detail, burn_ack = ensure_burning_options(ui)
            note_parts.append("Burning Option: %s (Update 팝업: %s)"
                              % ("; ".join("%s=%s" % (v["label"], v["now_checked"])
                                          for v in burn_detail.values()),
                                 burn_ack or "없음"))

        echo_ok, echo_note = echo(ui, kind, timeout=echo_timeout)
        note_parts.append("Echo: %s" % echo_note)
        results.append({"kind": kind, "name": spec["name"], "registered": True,
                        "echo_ok": echo_ok, "note": "; ".join(note_parts)})
    return results
