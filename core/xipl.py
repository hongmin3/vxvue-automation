# -*- coding: utf-8 -*-
"""XIPL.SERVER 연동 — 라이선스 확인과 서버 로그 판독.

## 라이선스 (TC_WindowsUpdate_04)

사용자 확인(2026-08-18): VXvue의 Setting > System > License가 아니라
**XIPL.SERVER의 About 창**에 아래 4종이 등록돼 있는지 보면 된다(대괄호 날짜는 무시).

    SBSC / Bone-X AI / VXCAD_CXR / Noise-X AI

About 창의 라이선스 목록은 표준 `Edit`(컨트롤 ID 1030)이라 `GetWindowText`로
**그대로 읽힌다** — OCR이 필요 없다. 다만 이 창을 여는 경로는 트레이 아이콘
메뉴뿐이고(시스템 메뉴에 About 항목이 없음을 실측 확인), 명령행·레지스트리
어디에도 라이선스 목록이 없다. 그래서 이 모듈은 **창이 떠 있으면 자동 판정,
없으면 사람이 열어야 함을 알리는** 방식으로 동작한다. 없는 자동화를 있는 척
하지 않는다.

## 서버 로그 (TC_WindowsUpdate_06)

`C:\\XIPL\\SERVER_X64\\log\\<YYYY_MM_DD>.log`는 **UTF-16LE**로 기록된다.
바이트 기준 grep이나 기본 인코딩 읽기로는 `PureGrid.Apply="0"` 문구를 절대
찾을 수 없다(실측 확인). 반드시 이 모듈의 리더를 쓸 것.
"""

import ctypes
import ctypes.wintypes as wt
import io
import os
import re
from datetime import date

from .ui import VXvueUi, children

u32 = ctypes.windll.user32

ABOUT_TITLE = "About XIPL.SERVER"
ABOUT_LICENSE_EDIT = 1030
ABOUT_VERSION_STATIC = 1145

# TC04가 요구하는 4종 (사용자 확인, 2026-08-18)
REQUIRED_LICENSES = ("SBSC", "Bone-X AI", "VXCAD_CXR", "Noise-X AI")

ABOUT_CLOSED = "ABOUT_CLOSED"


def _about_dialog():
    ui = VXvueUi("XIPL.SERVER")
    if not ui.pid:
        return None, None
    for w in ui.windows():
        if w.text == ABOUT_TITLE:
            return ui, w
    return ui, None


def about_licenses():
    """About 창의 라이선스 목록을 파싱해 반환한다.

    반환: (names, raw)  — 창이 없으면 (None, ABOUT_CLOSED)
    names는 대괄호 날짜를 제거한 이름 리스트. 예) ['PureImpact', 'SBSC', ...]
    """
    ui, dlg = _about_dialog()
    if ui is None:
        return None, "XIPL.SERVER 프로세스를 찾을 수 없습니다."
    if dlg is None:
        return None, ABOUT_CLOSED

    raw = ""
    for c in children(dlg.hwnd, 3):
        if c.cls == "Edit" and c.ctrl_id == ABOUT_LICENSE_EDIT:
            raw = c.text
            break
    names = []
    for line in raw.splitlines():
        line = re.sub(r"\[[^\]]*\]", "", line).strip()
        if line:
            names.append(line)
    return names, raw


def about_version():
    _, dlg = _about_dialog()
    if dlg is None:
        return None
    for c in children(dlg.hwnd, 3):
        if c.cls == "Static" and c.ctrl_id == ABOUT_VERSION_STATIC:
            return c.text.strip()
    return None


def check_licenses(required=REQUIRED_LICENSES):
    """필요한 라이선스가 모두 등록됐는지 확인한다.

    반환: dict(status=..., found=[...], missing=[...], all=[...])
      status: 'OK' | 'MISSING' | ABOUT_CLOSED | 'NO_PROCESS'
    """
    names, raw = about_licenses()
    if names is None:
        return {"status": ABOUT_CLOSED if raw == ABOUT_CLOSED else "NO_PROCESS",
                "found": [], "missing": list(required), "all": [], "note": raw}

    norm = dict((n.lower().replace(" ", "").replace("-", "").replace("_", ""), n)
                for n in names)
    found, missing = [], []
    for want in required:
        key = want.lower().replace(" ", "").replace("-", "").replace("_", "")
        if key in norm:
            found.append(norm[key])
        else:
            missing.append(want)
    return {"status": "OK" if not missing else "MISSING",
            "found": found, "missing": missing, "all": names, "note": ""}


ABOUT_OPEN_HINT = (
    "XIPL.SERVER About 창이 닫혀 있습니다. 작업 표시줄 알림 영역의 XIPL.SERVER "
    "트레이 아이콘을 우클릭해 About을 연 뒤 다시 실행하십시오. "
    "(시스템 메뉴·명령행·레지스트리에는 라이선스 목록이 없어 자동으로 열 수 없습니다)")


# --- 서버 로그 -------------------------------------------------------
def log_path(log_dir, when=None):
    when = when or date.today()
    return os.path.join(log_dir, when.strftime("%Y_%m_%d") + ".log")


def read_log(path):
    """XIPL 서버 로그를 읽는다. UTF-16LE가 기본이며 실패 시 UTF-8로 대체한다."""
    if not os.path.exists(path):
        return ""
    with io.open(path, "rb") as f:
        data = f.read()
    for enc in ("utf-16-le", "utf-16", "utf-8"):
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
        # UTF-16 파일을 UTF-8로 잘못 읽으면 NUL이 잔뜩 섞인다. 그걸로 판별한다.
        if text.count("\x00") < len(text) / 10:
            return text.replace("\ufeff", "")
    return data.decode("utf-8", "replace")


_TS = re.compile(r"^\s*\[(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2}):(\d{2})")


def log_lines_since(path, since=None):
    """지정 시각 이후의 로그 줄만 반환한다. since는 datetime."""
    out = []
    for line in read_log(path).splitlines():
        if since is not None:
            m = _TS.match(line)
            if m:
                y, mo, d, h, mi, s = (int(v) for v in m.groups())
                from datetime import datetime
                if datetime(y, mo, d, h, mi, s) < since:
                    continue
        if line.strip():
            out.append(line.rstrip())
    return out


def find_marker(log_dir, marker, since=None, when=None):
    """로그에서 문구를 찾는다. 찾은 줄 목록을 반환(없으면 빈 리스트).

    TC_WindowsUpdate_06의 `PureGrid.Apply="0"` 판정에 쓴다.
    """
    path = log_path(log_dir, when)
    return [ln for ln in log_lines_since(path, since) if marker in ln]
