# -*- coding: utf-8 -*-
"""자동화 실행 전 환경 점검.

물리 메모리와 페이지파일 여유는 사용자 지시(2026-08-26)로 Precondition에서
제외했다. 둘은 시험의 성립 조건이 아니며 환경 변동만으로 전체 판정이 MANUAL이
되는 문제가 있었다. 실제 예외가 발생했을 때의 진단 문자열
``memory_pressure()``은 원인 분석용으로만 유지한다.
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

    # 2) 디스플레이 해상도 / DPI
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

    # 7) Bunny 수신 폴더 (TC06 Extra Tool 판정 근거)
    #    2026-08-26부터 Storage SCP는 원격(STORAGE_SCP)이고, Bunny는 Extra
    #    Tool(TC06) 전송 대상으로만 남는다 — 그래서 이 항목의 근거 TC가 05에서
    #    06으로 바뀌었다.
    recv = ((cfg.get("dicom") or {}).get("bunny") or {}).get("receive_dir")
    items.append(CheckItem("Bunny Receive 폴더",
                           OK if recv and os.path.isdir(recv) else WARN,
                           recv, "존재"))

    # 8) 원격 Storage SCP 가동 (TC02/TC05 판정 근거)
    #    "개별 TC 실행에서 왜 수신이 0건인가"를 앞에서 알려주기 위한 점검이다
    #    (NEXT_TASK.md P1 5b와 같은 취지). 폴더 존재만 보던 7)로는 원격 서버가
    #    죽어 있는 상태를 잡을 수 없다.
    from . import storagescp
    if storagescp.uses_local_bunny(cfg):
        items.append(CheckItem("Storage SCP 가동", OK, "로컬 Bunny 구성",
                               "원격 점검 대상 아님"))
    else:
        url = storagescp.server_url(cfg)
        spec = storagescp.storage_spec(cfg)
        try:
            status = storagescp.StorageServer(url, timeout=8).status() or {}
        except Exception as exc:                  # noqa: BLE001 - 점검 자체는 계속한다
            status, note = {}, "%s: %s" % (type(exc).__name__, exc)
        else:
            note = ""
        running = bool(status.get("running"))
        matches = (str(status.get("ae_title")) == str(spec.get("ae_title"))
                   and str(status.get("port")) == str(spec.get("port")))
        items.append(CheckItem(
            "Storage SCP 가동", OK if (running and matches) else NG,
            "%s AE=%s port=%s running=%s"
            % (url, status.get("ae_title"), status.get("port"), running),
            "AE=%s port=%s running=True" % (spec.get("ae_title"), spec.get("port")),
            note or ("" if matches else
                     "서버가 알려주는 AE/Port가 config의 등록값과 다르다 — "
                     "config.json의 dicom.servers_to_register[Storage]를 맞출 것.")))

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
