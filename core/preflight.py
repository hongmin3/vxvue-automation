# -*- coding: utf-8 -*-
"""자동화 실행 전 환경 점검.

Bellalun `auto/core/preflight.py`와 같은 역할이지만, 2026-08-18에 실제로
겪은 장애를 근거로 **메모리/페이지파일 여유 점검**을 추가했다. 당시 VXvue는
로그인 화면의 "Initializing offset refreshing"(Virtual Detector 0~3 연결)에서
무한 대기했고, 원인은 제품 결함이 아니라 물리 메모리 여유 1.74GB /
페이지파일 여유 0.12GB까지 떨어진 PC 자원 고갈이었다. 같은 시간대 이벤트
로그에 SQL Server "insufficient memory", DWM 재시작, TNetworkControl.exe
크래시가 함께 남아 있었다.

자원이 부족한 상태에서 클릭을 계속 보내면 '자동화 실패'가 아니라 '제품 결함'으로
오판하게 되므로, 부족하다는 사실은 반드시 리포트에 남긴다.

## 메모리 부족은 차단 사유가 아니다 (사용자 지시, 2026-08-19)

처음에는 물리 메모리/페이지파일 여유가 기준 미달이면 `NG`로 실행 자체를 막았다.
그런데 이 시험 PC는 XIPL.SERVER(약 2.2GB) 등 상주 프로세스 때문에 **물리 메모리
여유가 항상 기준(3GB) 아래**다. 사용자 지시: "메모리가 부족해도 일단 실행하고
문제가 있으면 그때 고민하는 방식으로 — 메모리는 항상 부족할 것."

그래서 메모리 계열 점검은 `WARN`으로 내려 실행을 막지 않고, 대신

  1. WARN이어도 리포트/콘솔에 실제 여유량을 남긴다(사후에 원인 추적이 되도록),
  2. 뷰어 기동이 실제로 실패했을 때 `memory_pressure()`로 그 시점 메모리를 다시
     읽어 "환경 자원 부족 가능성"을 판정 `note`에 명시한다.

즉 판단을 실행 전 추측에서 **실패 시점의 실측**으로 옮겼다. `NG`는 관리자 권한·
DPI·실행 파일·DB 접속처럼 **없으면 아무 것도 못 하는** 것만 남긴다.
"""

import os

from . import sysinfo

OK, WARN, NG = "OK", "WARN", "NG"


class CheckItem:
    def __init__(self, name, status, actual, expected="", note=""):
        self.name, self.status = name, status
        self.actual, self.expected, self.note = actual, expected, note

    def as_dict(self):
        return {"name": self.name, "status": self.status, "actual": self.actual,
                "expected": self.expected, "note": self.note}

    def __repr__(self):
        return "[%s] %-24s actual=%s expected=%s %s" % (
            self.status, self.name, self.actual, self.expected, self.note)


def run(config):
    """점검 항목 리스트를 반환한다. NG가 하나라도 있으면 실행을 중단해야 한다."""
    cfg = config or {}
    pf = cfg.get("preflight") or {}
    items = []

    # 1) 관리자 권한 - 없으면 UIPI가 합성 입력을 전부 차단한다.
    elevated = sysinfo.is_elevated()
    items.append(CheckItem(
        "관리자 권한", OK if elevated or not pf.get("require_elevated", True) else NG,
        elevated, True,
        "" if elevated else "관리자 권한이 없으면 VXvue 창에 클릭/키 입력이 전달되지 않는다."))

    # 2) 메모리 / 페이지파일
    mem = sysinfo.memory_info()
    min_phys = float(pf.get("min_physical_free_gb", 3.0))
    min_page = float(pf.get("min_pagefile_free_gb", 4.0))
    phys_free = mem.get("physical_free_gb")
    page_free = mem.get("pagefile_free_gb")
    # 메모리 계열은 WARN까지만 올린다(위 docstring "메모리 부족은 차단 사유가
    # 아니다" 참고 — 사용자 지시, 2026-08-19). 실행을 막지 않되 여유량은 남긴다.
    phys_ok = (phys_free or 0) >= min_phys
    items.append(CheckItem(
        "물리 메모리 여유", OK if phys_ok else WARN,
        "%sGB" % phys_free, ">= %sGB" % min_phys,
        "" if phys_ok else "기준 미달이지만 실행은 계속한다(사용자 지시). "
                           "2026-08-18 무한 대기 장애의 실제 원인이었으므로, 이후 "
                           "기동/촬영이 실패하면 이 값을 먼저 의심할 것."))
    page_ok = (page_free or 0) >= min_page
    items.append(CheckItem(
        "페이지파일 여유", OK if page_ok else WARN,
        "%sGB" % page_free, ">= %sGB" % min_page,
        "" if page_ok else "기준 미달이지만 실행은 계속한다(사용자 지시)."))

    # 3) 디스플레이 해상도 / DPI
    disp = sysinfo.display_info()
    want = cfg.get("display") or {}
    if want.get("enforce"):
        res_ok = (disp.get("width") == want.get("width")
                  and disp.get("height") == want.get("height"))
        dpi_ok = disp.get("dpi") == want.get("expected_dpi", 96)
        items.append(CheckItem(
            "해상도", OK if res_ok else WARN,
            "%sx%s" % (disp.get("width"), disp.get("height")),
            "%sx%s" % (want.get("width"), want.get("height")),
            "" if res_ok else "좌표 캘리브레이션(TC14)이 해상도에 종속된다."))
        items.append(CheckItem(
            "DPI 배율", OK if dpi_ok else NG,
            "%s%% (%s DPI)" % (disp.get("scale_percent"), disp.get("dpi")),
            "100%% (%s DPI)" % want.get("expected_dpi", 96),
            "" if dpi_ok else "DPI는 로그아웃 없이 안전하게 바꿀 수 없다. 사람이 먼저 변경할 것."))

    # 4) 설치 경로 / 실행 파일
    exe = (cfg.get("viewer") or {}).get("exe")
    items.append(CheckItem("VXvue 실행 파일", OK if exe and os.path.exists(exe) else NG,
                           exe, "존재"))

    # 5) DB 접속 (DRF). master는 항상 열리므로 판정에 쓰지 않는다.
    try:
        from .db import VXvueDb
        db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
        ping = db.ping()
    except Exception as exc:                      # noqa: BLE001 - 점검 자체는 계속한다
        ping, exc_note = False, str(exc)
    else:
        exc_note = ""
    items.append(CheckItem("DRF DB 접속", OK if ping else NG, ping, True, exc_note))

    # 6) XIPL 서버 로그 경로 (TC06 판정 근거)
    xipl_log = (cfg.get("xipl") or {}).get("server_log_dir")
    items.append(CheckItem("XIPL Server Log 경로",
                           OK if xipl_log and os.path.isdir(xipl_log) else WARN,
                           xipl_log, "존재"))

    # 7) Bunny 수신 폴더 (TC05 판정 근거)
    recv = ((cfg.get("dicom") or {}).get("bunny") or {}).get("receive_dir")
    items.append(CheckItem("Bunny Receive 폴더",
                           OK if recv and os.path.isdir(recv) else WARN,
                           recv, "존재"))

    return items


def blocking(items):
    return [i for i in items if i.status == NG]


def warnings(items):
    return [i for i in items if i.status == WARN]


def memory_pressure(config=None):
    """지금 이 순간의 메모리 여유를 문자열로 돌려준다.

    뷰어 기동/촬영이 실패했을 때 판정 `note`에 붙여, 그 실패가 제품 결함인지
    환경 자원 부족인지 사후에 구분할 수 있게 한다. 기준 미달이면 그 사실을
    문장에 포함한다.
    """
    pf = (config or {}).get("preflight") or {}
    min_phys = float(pf.get("min_physical_free_gb", 3.0))
    min_page = float(pf.get("min_pagefile_free_gb", 4.0))
    try:
        mem = sysinfo.memory_info()
    except Exception as exc:                      # noqa: BLE001
        return "메모리 조회 실패: %s" % exc
    phys = mem.get("physical_free_gb")
    page = mem.get("pagefile_free_gb")
    short = []
    if (phys or 0) < min_phys:
        short.append("물리 %sGB < %sGB" % (phys, min_phys))
    if (page or 0) < min_page:
        short.append("페이지파일 %sGB < %sGB" % (page, min_page))
    base = "실패 시점 메모리 여유: 물리 %sGB / 페이지파일 %sGB" % (phys, page)
    if short:
        return base + " — 기준 미달(%s). 환경 자원 부족 가능성을 먼저 확인할 것." % ", ".join(short)
    return base + " — 기준 충족. 자원 부족이 원인은 아니다."
