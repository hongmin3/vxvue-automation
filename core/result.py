# -*- coding: utf-8 -*-
"""판정 결과 모델과 리포트 산출물.

Bellalun `auto/core/result.py`를 이식하되 VXvue 요구사항 두 가지를 반영했다.

1. **리포트 상단에 Windows 정보 + 패키지 정보를 반드시 출력한다**(사용자 요청).
   체크리스트 원본 `Checklist` 시트 1~5행(OS / OS Version / OS Build Version /
   Viewer Version / VX.LIVE.SERVER)과 같은 형식을 재현하며, Bellalun이 TXT에만
   넣던 환경 헤더를 **TXT/HTML/JSON/CSV 네 포맷 모두**에 넣는다.
2. 판정에 `BLOCKED`를 추가했다. 선행 조건 자체가 이 PC에 갖춰지지 않아
   수행이 불가능한 경우(예: TC12의 카메라 하드웨어)를 SKIP과 구분한다.

  PASS    : 자동 판정으로 기대 결과 충족
  FAIL    : 자동 판정으로 기대 결과 불충족
  MANUAL  : 자동화 대상이 아니거나 기대값이 확정되지 않아 사람이 확인해야 함
  SKIP    : 사전 조건 미충족으로 수행하지 않음(환경상 정상적인 건너뜀)
  BLOCKED : 선행 조건이 구성되지 않아 수행 자체가 불가능
"""

import csv
import html
import json
import os
import time
from datetime import datetime

from . import report_language

PASS, FAIL, MANUAL, SKIP, BLOCKED = "PASS", "FAIL", "MANUAL", "SKIP", "BLOCKED"
STATUSES = (PASS, FAIL, MANUAL, SKIP, BLOCKED)

REPORT_TITLE = "VXvue Windows Update 호환성 자동화 결과"
DOC_NUMBER = "R-25-774"

# 모든 리포트(TXT/HTML/JSON/CSV) 상단에 붙는 일반 유의사항(사용자 지시,
# 2026-08-25). 특정 TC의 note가 아니라 이번 회귀 전체에 적용되는 시험
# 범위/한계를 여기 모은다 — 개별 TC를 읽지 않고 리포트 요약만 봐도 알 수
# 있어야 한다.
REPORT_CAVEATS = (
    "이 회귀의 모든 촬영은 DX(일반촬영) 환자/절차로만 수행한다. MG(유방촬영) "
    "절차는 검증하지 않았다 — Dose SR 등 MG 전용 기능의 PASS/FAIL은 이 결과에 "
    "포함되지 않는다(TC_WindowsUpdate_05 참고).",
)

# 리포트는 자동화 구현자가 아니라 시험 결과를 판단하는 사용자가 먼저 읽는다.
# 코드/DB 용어는 원본 근거를 보존하되 아래 설명을 리포트 앞부분에 함께 보여 준다.
REPORT_GLOSSARY = (
    ("MWL", "촬영 전에 서버에서 받아오는 환자·검사 예약 목록"),
    ("DICOM SCP / C-STORE", "영상을 받는 시험 서버 / 그 서버로 영상을 보내는 전송"),
    ("DB", "VXvue가 환자·검사·영상 상태를 저장하는 데이터베이스"),
    ("ORDER_PATIENT / INSTANCE", "DB의 예약 환자 정보 / 저장된 영상 정보"),
    ("OCR / owner-draw", "화면 글자를 이미지로 읽는 방식 / 표준 API로 글자를 읽을 수 없는 화면"),
    ("baseline", "설치 직후와 같은 깨끗한 DB·폴더 기준 상태"),
    ("MANUAL", "자동 근거만으로 결론을 확정할 수 없어 사람의 판단이 필요한 상태"),
    ("SKIP / BLOCKED", "시험 범위·조건상 의도적으로 제외 / 필수 환경이 없어 수행 불가"),
)

TC_PURPOSES = {
    "Precondition": "본 시험을 시작할 수 있도록 권한, 저장 공간, 화면 환경, 프로그램과 서버 경로가 준비됐는지 확인한다.",
    "Baseline_Reset": "이전 시험 데이터의 영향을 없애기 위해 DB와 데이터 폴더를 설치 직후 기준 상태로 복원한다.",
    "VXvue_License": "VXvue와 사용 옵션의 라이선스가 시험에 필요한 상태로 등록돼 있는지 확인한다.",
    "DICOM_Servers": "검사 예약, 영상 저장, 출력에 사용하는 DICOM 서버가 등록돼 있고 통신되는지 확인한다.",
    "Viewer_Startup": "baseline 복원 후 VXvue가 다시 실행되고 시험 계정으로 로그인되는지 확인한다.",
    "Quick_Mode": "빠른 이상 감지를 위해 전체 회귀 중 축소한 범위와 정식 판정에 사용할 수 없는 이유를 명시한다.",
    "TC_WindowsUpdate_00": "실제 제품 시험 없이 Windows·패키지 환경 헤더와 사용자용 리포트 형식이 정상 생성되는지 확인한다.",
    "TC_WindowsUpdate_01": "Windows Update 설치 전후의 제품 설치 상태를 사람이 확인하는 제외 TC다.",
    "TC_WindowsUpdate_02": "예약 환자를 조회해 촬영하고 전송한 뒤, 화면·수신 영상·DB의 환자 및 검사 정보가 모두 같은지 확인한다.",
    "TC_WindowsUpdate_03": "영상 보간 설정과 선택·확대·이동·회전 도구가 실제 화면에 반영되는지 확인한다.",
    "TC_WindowsUpdate_04": "촬영 영상이 XIPL 영상처리를 거쳐 표시되고 XIPL Studio까지 정상 연결되는지 확인한다.",
    "TC_WindowsUpdate_05": "Send Dose SR 설정을 적용한 뒤 DICOM 영상이 저장 서버에 정상 전송되는지 확인한다. MG 전용 Dose SR은 현재 DX 검증 범위 밖이다.",
    "TC_WindowsUpdate_06": "Extra Tool 서버 설정과 SBSC 제거 옵션을 적용한 뒤 영상 전송과 서버 처리 로그를 확인한다.",
    "TC_WindowsUpdate_07": "영상을 DICOM Print로 보내 수신 필름과 필름 위 환자·검사 표시 문구까지 올바른지 확인한다.",
    "TC_WindowsUpdate_08": "검사를 외부 폴더로 Export하고 파일·태그·포터블 뷰어를 확인한 뒤 다시 Import할 수 있는지 확인한다.",
    "TC_WindowsUpdate_09": "재부팅이 필요한 수동 TC로, 자동 회귀에서는 사람이 수행할 항목임을 기록한다.",
    "TC_WindowsUpdate_10": "사용자 결정으로 자동화 범위에서 제외한 TC다.",
    "TC_WindowsUpdate_11": "검증 영상을 CAD로 분석해 소견, 표시 옵션, 결과 영상 저장 동작이 올바른지 확인한다.",
    "TC_WindowsUpdate_12": "Live View 데모 영상 재생, 오버레이 창, 분석 표시와 스냅샷 전송 동작을 확인한다.",
    "TC_WindowsUpdate_13": "환자정보 파일의 미리보기·수동 Import·폴더 자동 Import·구분자·컬럼 설정이 사양대로 동작하는지 확인한다.",
    "TC_WindowsUpdate_14": "Setting의 모든 하위 화면이 열리고 제목과 본문이 정상 표시되는지 확인한다.",
    "TC_WindowsUpdate_15": "사용자 결정으로 자동화 범위에서 제외한 TC다.",
    "TC_Setting_ExportImport": "설정을 Export한 뒤 일부 값을 바꾸고 Import해 원래 설정으로 정확히 복원되는지 확인한다.",
    # 과거 리포트와 외부 호출자가 사용하던 별칭도 같은 설명을 유지한다.
    "Setting_Export_Import": "설정을 Export한 뒤 일부 값을 바꾸고 Import해 원래 설정으로 정확히 복원되는지 확인한다.",
}

STATUS_EXPLANATIONS = {
    PASS: "자동으로 확보한 결과가 합격 기준을 충족해 PASS로 판정했다.",
    FAIL: "자동으로 확보한 결과가 합격 기준을 충족하지 못해 FAIL로 판정했다.",
    MANUAL: "자동으로 확보한 근거만으로 합격 또는 실패를 확정할 수 없어 사람의 판단이 필요하다.",
    SKIP: "이번 실행의 범위 또는 조건에 따라 이 확인을 수행하지 않았다.",
    BLOCKED: "필수 선행 환경이 준비되지 않아 이 확인을 수행할 수 없었다.",
}

STATUS_ACTIONS = {
    PASS: "추가 조치가 필요하지 않다.",
    FAIL: "실제값과 비고를 확인하고 원인을 조사한 뒤 해당 TC를 다시 실행해야 한다.",
    MANUAL: "비고의 확인 요청을 담당자 또는 사용자와 검토해 최종 판단해야 한다.",
    SKIP: "비고에서 제외 사유를 확인하고, 검증 범위에 포함해야 한다면 조건을 갖춰 다시 실행해야 한다.",
    BLOCKED: "비고에 적힌 선행 환경을 구성한 뒤 다시 실행해야 한다.",
}


def tc_purpose(tc_id, title=""):
    """TC가 무엇을 검증하는지 사용자 관점의 한 문장으로 반환한다."""
    if tc_id in TC_PURPOSES:
        return TC_PURPOSES[tc_id]
    if tc_id.startswith("TC_WindowsUpdate_"):
        return "%s 시험의 각 확인 단계가 기대 결과를 충족하는지 검증한다." % (title or tc_id)
    return "%s 과정이 기대한 상태로 완료되는지 확인한다." % (title or tc_id)


def _expected_for_reader(value, title):
    text = str(value).strip() if value is not None else ""
    if text.lower() == "true":
        return "이 단계에서 확인하는 조건이 모두 충족되어야 한다."
    if text.lower() == "false":
        return "이 단계에서 확인하는 조건이 발생하지 않아야 한다."
    return text or ("'%s' 단계의 요구 동작이 완료되고 결과 근거가 확인되어야 한다."
                    % title)


def _actual_for_reader(value, status):
    text = str(value).strip() if value is not None else ""
    if text.lower() == "true":
        return "자동으로 확인한 실제값은 True이다."
    if text.lower() == "false":
        return "자동으로 확인한 실제값은 False이다."
    if text:
        prefix = {
            PASS: "자동 확인 결과: ",
            FAIL: "기대 결과와 다른 실제 상태: ",
            MANUAL: "자동으로 확보한 참고 결과: ",
            SKIP: "미수행 상태: ",
            BLOCKED: "수행 불가 상태: ",
        }.get(status, "확인 결과: ")
        return prefix + text
    return {
        PASS: ("세부 실제값은 별도로 수집되지 않았지만, 자동 판정에 사용한 조건은 "
               "기대 결과와 일치했다."),
        FAIL: ("세부 실제값을 확보하지 못했거나 기대 결과와 다른 상태가 확인됐다. "
               "증거 파일과 실행 로그를 확인해야 한다."),
        MANUAL: ("자동으로 실제 결과를 확정할 수 없었다. 기대 결과와 같은지 "
                 "사용자가 직접 확인해야 한다."),
        SKIP: "이번 실행에서는 이 단계를 수행하지 않아 실제 결과가 없다.",
        BLOCKED: "필수 선행 조건이 없어 이 단계를 시작하지 못했으므로 실제 결과가 없다.",
    }.get(status, "실제 결과를 자동으로 확보하지 못했다. 사용자 확인이 필요하다.")


class Check:
    def __init__(self, tc_id, step, title, status, expected="", actual="", note="",
                 blocks_verdict=True):
        self.tc_id = tc_id
        self.step = step
        self.title = title
        self.status = status
        self.expected = expected
        self.actual = actual
        self.note = note
        # 기본은 True — MANUAL/SKIP/BLOCKED 어느 것이든 그 TC를 PASS로 올리지
        # 못하게 막는다("완전 자동화"는 모든 Step이 PASS/FAIL인 상태, TODO_전체
        # 자동화.md 0절). 사용자가 명시적으로 확정한 예외 하나만 False를 쓴다 —
        # TC14의 "--deep 미수행" Step(체크리스트 원문 범위는 가벼운 모드로 이미
        # 충족되고 --deep은 그 위의 정밀 검증이라 미수행이 PASS를 막을 이유가
        # 아니다, 사용자 확정 2026-08-21). 다른 TC에서 새로 False를 쓰려면 같은
        # 수준의 명시적 사용자 확정이 있어야 한다.
        self.blocks_verdict = blocks_verdict

    @property
    def reader_activity(self):
        return report_language.describe_step(self.tc_id, self.title)[0]

    @property
    def activity_is_catalogued(self):
        return report_language.describe_step(self.tc_id, self.title)[1]

    @property
    def reader_expected(self):
        return _expected_for_reader(self.expected, self.title)

    @property
    def reader_actual(self):
        return _actual_for_reader(self.actual, self.status)

    @property
    def reader_reason(self):
        reason = STATUS_EXPLANATIONS.get(self.status, "판정 상태를 확인해야 한다.")
        note = str(self.note).strip() if self.note is not None else ""
        if note:
            reason += " 상세 근거: %s" % note
        if not self.blocks_verdict and self.status in (MANUAL, SKIP, BLOCKED):
            reason += " 이 항목은 사용자 확정 예외이므로 TC 최종 PASS를 막지 않는다."
        return reason

    @property
    def reader_action(self):
        return STATUS_ACTIONS.get(self.status, "담당자가 판정 내용을 검토해야 한다.")

    def as_dict(self):
        return {"step": self.step, "title": self.title, "status": self.status,
                "expected": str(self.expected), "actual": str(self.actual),
                "note": self.note, "blocks_verdict": self.blocks_verdict,
                "reader_activity": self.reader_activity,
                "activity_is_catalogued": self.activity_is_catalogued,
                "reader_expected": self.reader_expected,
                "reader_actual": self.reader_actual,
                "reader_reason": self.reader_reason,
                "reader_action": self.reader_action}


class TCResult:
    def __init__(self, tc_id, title):
        self.tc_id = tc_id
        self.title = title
        self.checks = []
        self.started = datetime.now()
        self.completed = None
        self.timings = []
        self._step_cursor_wall = self.started
        self._step_cursor = time.perf_counter()
        self.evidence = []

    # --- 등록 헬퍼 -----------------------------------------------------
    def add(self, step, title, status, expected="", actual="", note="",
            blocks_verdict=True):
        now_wall = datetime.now()
        now = time.perf_counter()
        self.timings.append({
            "kind": "step", "name": "Step %s: %s" % (step, title),
            "started": self._step_cursor_wall.isoformat(timespec="milliseconds"),
            "ended": now_wall.isoformat(timespec="milliseconds"),
            "duration_seconds": round(now - self._step_cursor, 3),
            "outcome": status, "detail": "check recorded",
        })
        self._step_cursor_wall, self._step_cursor = now_wall, now
        self.checks.append(Check(self.tc_id, step, title, status, expected, actual, note,
                                 blocks_verdict=blocks_verdict))
        return self.checks[-1]

    def record_timing(self, name, started_wall, started_perf, outcome, detail="",
                      kind="wait"):
        """PASS/FAIL 판정을 바꾸지 않고 소요시간만 기록한다."""
        ended = datetime.now()
        self.timings.append({
            "kind": kind, "name": name,
            "started": started_wall.isoformat(timespec="milliseconds"),
            "ended": ended.isoformat(timespec="milliseconds"),
            "duration_seconds": round(time.perf_counter() - started_perf, 3),
            "outcome": outcome, "detail": str(detail),
        })

    def finalize(self, completed=None):
        if self.completed is None:
            self.completed = completed or datetime.now()
        return self

    @property
    def duration_seconds(self):
        end = self.completed or datetime.now()
        return round((end - self.started).total_seconds(), 3)

    def assert_equal(self, step, title, expected, actual, note=""):
        ok = str(expected).strip().lower() == str(actual).strip().lower()
        return self.add(step, title, PASS if ok else FAIL, expected, actual, note)

    def assert_true(self, step, title, cond, expected="True", actual=None, note=""):
        return self.add(step, title, PASS if cond else FAIL,
                        expected, actual if actual is not None else cond, note)

    def manual(self, step, title, note, expected="", actual="", blocks_verdict=True):
        return self.add(step, title, MANUAL, expected, actual, note,
                        blocks_verdict=blocks_verdict)

    def skip(self, step, title, note, blocks_verdict=True):
        return self.add(step, title, SKIP, note=note, blocks_verdict=blocks_verdict)

    def blocked(self, step, title, note, blocks_verdict=True):
        return self.add(step, title, BLOCKED, note=note, blocks_verdict=blocks_verdict)

    def attach(self, path):
        self.evidence.append(path)

    # --- 집계 ----------------------------------------------------------
    @property
    def counts(self):
        c = dict((s, 0) for s in STATUSES)
        for chk in self.checks:
            c[chk.status] = c.get(chk.status, 0) + 1
        return c

    @property
    def verdict(self):
        c = self.counts
        if c[FAIL]:
            return FAIL
        if c[PASS] == 0:
            if c[BLOCKED]:
                return BLOCKED
            return SKIP if c[SKIP] else MANUAL
        # SKIP도 MANUAL과 마찬가지로 PASS를 막는다 — "완전 자동화"는 모든 Step이
        # PASS/FAIL로만 판정되는 상태를 뜻하고(TODO_전체자동화.md 0절, 사용자 확정
        # 2026-08-20), SKIP 1건이라도 있으면 그 TC는 완전 자동화된 것이 아니다.
        # 예외: `blocks_verdict=False`로 등록된 Check(현재는 TC14의 `--deep`
        # 미수행 Step 1건뿐, 사용자 확정 2026-08-21)는 이 계산에서 빠진다 —
        # 비고에는 남지만 PASS를 막지 않는다.
        blocking_bad = any(chk.status in (MANUAL, BLOCKED, SKIP) and chk.blocks_verdict
                           for chk in self.checks)
        return MANUAL if blocking_bad else PASS

    def as_dict(self):
        return {
            "tc_id": self.tc_id, "title": self.title, "verdict": self.verdict,
            "purpose": tc_purpose(self.tc_id, self.title),
            "started": self.started.isoformat(timespec="seconds"),
            "completed": (self.completed or datetime.now()).isoformat(timespec="seconds"),
            "duration_seconds": self.duration_seconds,
            "counts": self.counts, "evidence": self.evidence,
            "timings": self.timings,
            "checks": [dict(c.as_dict(), sequence=i)
                       for i, c in enumerate(self.checks, 1)],
        }


# --- 환경 헤더 ---------------------------------------------------------
def collect_env(config=None):
    """리포트 상단 헤더용 Windows 정보 + 패키지 정보를 수집한다.

    체크리스트 `Checklist` 시트 상단(OS / OS Version / OS Build Version /
    Viewer Version / VX.LIVE.SERVER)과 같은 항목을 채운다.
    확인되지 않은 값은 임의로 채우지 않고 '(확인 필요)'로 남긴다.
    """
    from . import package_info
    from . import sysinfo

    cfg = config or {}
    osi = sysinfo.os_info()
    disp = sysinfo.display_info()
    mem = sysinfo.memory_info()

    windows = {
        "OS": osi.get("Caption") or "(확인 필요)",
        "OS Version": sysinfo.os_display_version() or osi.get("Version") or "(확인 필요)",
        "OS Build Version": sysinfo.os_build_full() or "(확인 필요)",
        "Architecture": osi.get("OSArchitecture") or "(확인 필요)",
        "Display": ("%sx%s / %s%% (%d DPI)"
                    % (disp.get("width"), disp.get("height"),
                       disp.get("scale_percent"), disp.get("dpi", 96))
                    if disp else "(확인 필요)"),
        "GPU": ", ".join(g["name"] for g in sysinfo.gpu_list()) or "(확인 필요)",
        "Memory": ("물리 여유 %sGB / %sGB, 페이지파일 여유 %sGB / %sGB"
                   % (mem.get("physical_free_gb"), mem.get("physical_total_gb"),
                      mem.get("pagefile_free_gb"), mem.get("pagefile_total_gb"))
                   if mem else "(확인 필요)"),
    }
    return {
        "document": DOC_NUMBER,
        "windows": windows,
        "packages": package_info.collect(cfg),
        "windows_updates": sysinfo.windows_updates(5),
    }


def _env_lines(env):
    if not env:
        return []
    L = []
    win = env.get("windows") or {}
    if win:
        L.append(" [ Windows 정보 ]")
        for k, v in win.items():
            L.append("   - %-18s: %s" % (k, v))
    pkg = env.get("packages") or {}
    if pkg:
        L.append(" [ 패키지 정보 ]")
        for k, v in pkg.items():
            L.append("   - %-18s: %s" % (k, v))
    ups = env.get("windows_updates") or []
    if ups:
        L.append(" [ 최근 Windows 업데이트 ]")
        for u in ups:
            L.append("   - %s  %s  (%s)" % (u.get("kb"), u.get("installed_on") or "",
                                            u.get("kind") or ""))
    return L


# ---------------------------------------------------------------------
_STYLE = """
body{font-family:'Malgun Gothic',sans-serif;margin:24px;color:#1a1a1a;background:#fff}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 6px}
.meta{color:#666;font-size:12px;margin-bottom:18px}
.caveats{background:#fff8e1;border:1px solid #f0d878;border-radius:4px;
        padding:8px 14px;margin-bottom:16px;font-size:12.5px}
.caveats ul{margin:4px 0 0;padding-left:18px}
.glossary{background:#f7f9fc;border:1px solid #dbe3ef;border-radius:4px;
          padding:8px 14px;margin-bottom:16px;font-size:12.5px}
.glossary dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;margin:6px 0}
.glossary dt{font-weight:700}.glossary dd{margin:0}
.attention{border:2px solid #d79a00;background:#fffaf0;border-radius:6px;
           padding:10px 14px;margin:12px 0 20px}
.attention h2{margin:0 0 8px}.attention-item{border-top:1px solid #ead7aa;padding:8px 0}
.attention-item:first-of-type{border-top:0}.purpose{background:#eef6ff;border-left:4px solid #4b83c3;
         padding:8px 12px;margin:6px 0 10px;font-size:13px}
.check-card{border:1px solid #d8d8d8;border-left:5px solid #8b8b8b;border-radius:5px;
            padding:10px 12px;margin:8px 0 12px;background:#fff}
.check-card.PASS{border-left-color:#0a7f3f}.check-card.FAIL{border-left-color:#c62828}
.check-card.MANUAL{border-left-color:#a06000}.check-card.SKIP{border-left-color:#777}
.check-card.BLOCKED{border-left-color:#6a1b9a}
.check-head{font-size:14px;font-weight:700;margin-bottom:8px}.check-head .s{float:right}
.check-card dl{display:grid;grid-template-columns:105px 1fr;gap:5px 10px;margin:0}
.check-card dt{font-weight:700;color:#444}.check-card dd{margin:0;white-space:pre-wrap}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-bottom:8px}
th,td{border:1px solid #d8d8d8;padding:6px 8px;text-align:left;vertical-align:top;
     word-break:break-word;overflow-wrap:anywhere}
th{background:#f3f4f6;font-weight:600}
td.s{font-weight:700;text-align:center;width:80px}
/* 기대값/실제값을 넓히고 비고를 좁힌다(사용자 지시, 2026-08-21) — 기본 표는
   내용 길이에 따라 열 너비가 정해져 비고(자유 서술)가 기대값/실제값(핵심
   판정 근거)보다 넓어지기 쉽다. table-layout:fixed + colgroup으로 비율을
   고정한다. */
table.steps{table-layout:fixed}
table.steps col.c-step{width:4%}
table.steps col.c-title{width:16%}
table.steps col.c-status{width:7%}
table.steps col.c-expected{width:27%}
table.steps col.c-actual{width:27%}
table.steps col.c-note{width:19%}
.PASS{color:#0a7f3f}.FAIL{color:#c62828}.MANUAL{color:#a06000}
.SKIP{color:#777}.BLOCKED{color:#6a1b9a}
.sum td.s{font-size:13px}
.env{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:18px}
.env table{width:auto;min-width:340px}
code{font-family:Consolas,monospace;font-size:12px;word-break:break-all}
"""


def _totals(results):
    total = dict((s, 0) for s in STATUSES)
    for r in results:
        for k, v in r.counts.items():
            total[k] = total.get(k, 0) + v
    return total


def _attention_items(results):
    """사용자가 결정을 내려야 하는 비-PASS Step을 실행 순서와 함께 반환한다."""
    items = []
    for result in results:
        for sequence, check in enumerate(result.checks, 1):
            if check.status != PASS:
                items.append((result, sequence, check))
    return items


def report_quality(results):
    """사용자용 필드 완전성과 Step 문장 사전 적용 여부를 검사한다."""
    uncatalogued_tc_purposes = []
    uncatalogued = []
    invalid_statuses = []
    synthesized_expected = 0
    synthesized_actual = 0
    empty_reader_fields = []
    for result in results:
        if result.tc_id not in TC_PURPOSES:
            uncatalogued_tc_purposes.append("%s/%s" % (result.tc_id, result.title))
        for sequence, check in enumerate(result.checks, 1):
            location = "%s/순서%d/Step%s/%s" % (
                result.tc_id, sequence, check.step, check.title)
            if not check.activity_is_catalogued:
                uncatalogued.append(location)
            if check.status not in STATUSES:
                invalid_statuses.append("%s/%s" % (location, check.status))
            if not str(check.expected).strip():
                synthesized_expected += 1
            if not str(check.actual).strip():
                synthesized_actual += 1
            fields = (check.reader_activity, check.reader_expected,
                      check.reader_actual, check.reader_reason, check.reader_action)
            if any(not str(value).strip() for value in fields):
                empty_reader_fields.append(location)
    return {
        "readable": not (uncatalogued_tc_purposes or uncatalogued or invalid_statuses
                         or empty_reader_fields),
        "uncatalogued_tc_purposes": uncatalogued_tc_purposes,
        "uncatalogued_steps": uncatalogued,
        "invalid_statuses": invalid_statuses,
        "empty_reader_fields": empty_reader_fields,
        "synthesized_expected_count": synthesized_expected,
        "synthesized_actual_count": synthesized_actual,
    }


def assert_report_readable(results):
    """새 TC 개발·문서 검증에서 쓰는 엄격한 품질 게이트.

    실제 시험 중에는 미등록 Step이 있어도 리포트를 반드시 남겨야 하므로
    `write_reports()`는 중단하지 않는다. 대신 개발 완료 전 이 함수를 호출해
    사용자 문장 사전 미등록과 빈 사용자 필드가 0건인지 확인한다.
    """
    quality = report_quality(results)
    problems = (quality["uncatalogued_tc_purposes"]
                + quality["uncatalogued_steps"]
                + quality["invalid_statuses"]
                + quality["empty_reader_fields"])
    if problems:
        raise AssertionError("사용자용 리포트 품질 미충족:\n- " + "\n- ".join(problems))
    return quality


def _append_text_glossary(lines):
    lines.append("-" * 80)
    lines.append(" 리포트 용어 설명")
    lines.append("-" * 80)
    for term, meaning in REPORT_GLOSSARY:
        lines.append(" - %-22s: %s" % (term, meaning))
    lines.append("")


def _append_text_quality(lines, results):
    quality = report_quality(results)
    lines.append("-" * 80)
    lines.append(" 리포트 가독성 품질 검사")
    lines.append("-" * 80)
    lines.append(" - 사용자용 필드 누락       : %d건" % len(quality["empty_reader_fields"]))
    lines.append(" - 시험 목적 미등록 TC      : %d건" % len(quality["uncatalogued_tc_purposes"]))
    lines.append(" - 문장 사전 미등록 Step    : %d건" % len(quality["uncatalogued_steps"]))
    lines.append(" - 잘못된 판정 상태         : %d건" % len(quality["invalid_statuses"]))
    lines.append(" - 기대 결과 자동 보완      : %d건" % quality["synthesized_expected_count"])
    lines.append(" - 실제 결과 자동 보완      : %d건" % quality["synthesized_actual_count"])
    pending = (quality["uncatalogued_tc_purposes"] + quality["uncatalogued_steps"]
               + quality["invalid_statuses"])
    if pending:
        lines.append(" - 주의: 아래 항목은 새 TC 완료 전에 사용자용 사전에 등록하거나 수정해야 한다.")
        for item in pending:
            lines.append("   · %s" % item)
    lines.append("")


def write_txt(results, path, env=None):
    """사람이 바로 읽는 요약 텍스트. 상단에 환경 헤더를 붙인다."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    total = _totals(results)

    L = []
    L.append("=" * 80)
    L.append(" %s   (문서번호: %s)" % (REPORT_TITLE, DOC_NUMBER))
    L.append("=" * 80)
    L.append(" 수행 일시     : %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    L.extend(_env_lines(env))
    L.append(" TC 건수       : %d" % len(results))
    L.append(" 판정 합계     : PASS %d / FAIL %d / MANUAL %d / SKIP %d / BLOCKED %d"
             % (total[PASS], total[FAIL], total[MANUAL], total[SKIP], total[BLOCKED]))
    L.append("=" * 80)
    L.append("")

    if REPORT_CAVEATS:
        L.append("-" * 80)
        L.append(" 유의사항")
        L.append("-" * 80)
        for cav in REPORT_CAVEATS:
            L.append(" - %s" % cav)
        L.append("")

    _append_text_glossary(L)
    _append_text_quality(L, results)

    L.append("-" * 80)
    L.append(" TC 별 판정")
    L.append("-" * 80)
    for r in results:
        c = r.counts
        L.append(" [%s] %-28s %s (%.1fs)"
                 % (r.verdict.center(8), r.tc_id, r.title, r.duration_seconds))
        L.append("            P%d F%d M%d S%d B%d"
                 % (c[PASS], c[FAIL], c[MANUAL], c[SKIP], c[BLOCKED]))
    L.append("")

    attention = _attention_items(results)
    L.append("-" * 80)
    L.append(" 사용자가 먼저 확인할 항목 (FAIL / MANUAL / SKIP / BLOCKED)")
    L.append("-" * 80)
    if not attention:
        L.append(" 모든 Step이 PASS이므로 별도 확인이 필요한 항목이 없다.")
    for r, sequence, chk in attention:
        L.append(" [%s] %s / 실행 순서 %d (원본 Step %s) / %s"
                 % (chk.status, r.tc_id, sequence, chk.step, chk.title))
        L.append("   - 확인 결과 : %s" % chk.reader_actual)
        L.append("   - 판정 이유 : %s" % chk.reader_reason)
        L.append("   - 후속 조치 : %s" % chk.reader_action)
    L.append("")

    for r in results:
        L.append("=" * 80)
        L.append(" %s - %s   ->  %s" % (r.tc_id, r.title, r.verdict))
        L.append("=" * 80)
        L.append("  [시험 목적] %s" % tc_purpose(r.tc_id, r.title))
        L.append("")
        for sequence, chk in enumerate(r.checks, 1):
            L.append("  실행 순서 %d / 원본 Step %s / [%s]" %
                     (sequence, chk.step, chk.status))
            L.append("    수행 내용 : %s" % chk.reader_activity)
            L.append("    합격 기준 : %s" % chk.reader_expected)
            L.append("    확인 결과 : %s" % chk.reader_actual)
            L.append("    판정 이유 : %s" % chk.reader_reason)
            L.append("    후속 조치 : %s" % chk.reader_action)
            L.append("")
        if r.evidence:
            L.append("  [증거]")
            for e in r.evidence:
                L.append("    - %s" % e)
        if r.timings:
            L.append("  [기술 참고: 단계별 소요시간]")
            for t in r.timings:
                L.append("    - %s %s: %.3fs / %s / %s"
                         % (t["kind"], t["name"], t["duration_seconds"],
                            t["outcome"], t["detail"]))
        L.append("")

    L.append("=" * 80)
    if attention:
        L.append(" 최종 확인 필요 항목 %d건" % len(attention))
        L.append("=" * 80)
        for r, sequence, c in attention:
            L.append("  [%s] %s / 실행 순서 %d (원본 Step %s) / %s"
                     % (c.status, r.tc_id, sequence, c.step, c.title))
            L.append("     확인 결과: %s" % c.reader_actual)
            L.append("     후속 조치: %s" % c.reader_action)
    else:
        L.append(" 최종 확인 필요 항목 없음")
    L.append("=" * 80)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def _html_env(env):
    if not env:
        return ""
    e = html.escape
    blocks = []
    for label, key in (("Windows 정보", "windows"), ("패키지 정보", "packages")):
        data = env.get(key) or {}
        if not data:
            continue
        rows = "".join("<tr><th>%s</th><td>%s</td></tr>" % (e(str(k)), e(str(v)))
                       for k, v in data.items())
        blocks.append("<table><tr><th colspan='2'>%s</th></tr>%s</table>" % (label, rows))
    ups = env.get("windows_updates") or []
    if ups:
        rows = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                       % (e(str(u.get("kb"))), e(str(u.get("installed_on") or "")),
                          e(str(u.get("kind") or ""))) for u in ups)
        blocks.append("<table><tr><th colspan='3'>최근 Windows 업데이트</th></tr>%s</table>" % rows)
    return "<div class='env'>%s</div>" % "".join(blocks)


def _html_glossary():
    e = html.escape
    rows = "".join("<dt>%s</dt><dd>%s</dd>" % (e(term), e(meaning))
                   for term, meaning in REPORT_GLOSSARY)
    return "<div class='glossary'><b>리포트 용어 설명</b><dl>%s</dl></div>" % rows


def _html_attention(results):
    e = html.escape
    items = _attention_items(results)
    if not items:
        return ("<div class='attention'><h2>사용자가 먼저 확인할 항목</h2>"
                "<div>모든 Step이 PASS이므로 별도 확인이 필요한 항목이 없습니다.</div></div>")
    rows = []
    for result, sequence, check in items:
        rows.append(
            "<div class='attention-item'><b class='%s'>[%s]</b> "
            "<b>%s / 실행 순서 %d (원본 Step %s)</b> — %s"
            "<br><b>확인 결과:</b> %s"
            "<br><b>판정 이유:</b> %s"
            "<br><b>후속 조치:</b> %s</div>"
            % (check.status, check.status, e(result.tc_id), sequence,
               e(str(check.step)), e(check.title), e(check.reader_actual),
               e(check.reader_reason), e(check.reader_action)))
    return ("<div class='attention'><h2>사용자가 먼저 확인할 항목 "
            "(FAIL / MANUAL / SKIP / BLOCKED)</h2>%s</div>" % "".join(rows))


def _html_quality(results):
    e = html.escape
    quality = report_quality(results)
    status = "PASS" if quality["readable"] else "확인 필요"
    detail = ("사용자용 필드 누락 %d건 / 시험 목적 미등록 %d건 / "
              "문장 사전 미등록 %d건 / 잘못된 판정 상태 %d건 / "
              "기대 결과 자동 보완 %d건 / 실제 결과 자동 보완 %d건"
              % (len(quality["empty_reader_fields"]),
                 len(quality["uncatalogued_tc_purposes"]),
                 len(quality["uncatalogued_steps"]),
                 len(quality["invalid_statuses"]),
                 quality["synthesized_expected_count"],
                 quality["synthesized_actual_count"]))
    missing_items = (quality["uncatalogued_tc_purposes"]
                     + quality["uncatalogued_steps"] + quality["invalid_statuses"])
    missing = "".join("<li>%s</li>" % e(item) for item in missing_items)
    if missing:
        missing = ("<div><b>새 TC 완료 전에 문장 사전에 등록할 Step:</b>"
                   "<ul>%s</ul></div>" % missing)
    return ("<div class='glossary'><b>리포트 가독성 품질 검사: %s</b>"
            "<div>%s</div>%s</div>" % (e(status), e(detail), missing))


def write_reports(results, out_dir, run_name=None, env=None):
    """CSV / JSON / HTML / TXT 리포트를 out_dir에 생성하고 경로를 반환한다."""
    os.makedirs(out_dir, exist_ok=True)
    stamp = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(out_dir, "Result_%s" % stamp)
    e = html.escape
    total = _totals(results)

    # CSV (환경 헤더를 상단 주석 행으로 먼저 기록)
    csv_path = base + ".csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["# %s (문서번호: %s)" % (REPORT_TITLE, DOC_NUMBER)])
        w.writerow(["# 수행 일시", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        for cav in REPORT_CAVEATS:
            w.writerow(["# 유의사항", cav])
        for term, meaning in REPORT_GLOSSARY:
            w.writerow(["# 용어 설명", term, meaning])
        quality = report_quality(results)
        w.writerow(["# 리포트 품질", "사용자용 필드 누락",
                    len(quality["empty_reader_fields"])])
        w.writerow(["# 리포트 품질", "시험 목적 미등록 TC",
                    len(quality["uncatalogued_tc_purposes"])])
        w.writerow(["# 리포트 품질", "문장 사전 미등록 Step",
                    len(quality["uncatalogued_steps"])])
        w.writerow(["# 리포트 품질", "잘못된 판정 상태",
                    len(quality["invalid_statuses"])])
        w.writerow(["# 리포트 품질", "기대 결과 자동 보완",
                    quality["synthesized_expected_count"]])
        w.writerow(["# 리포트 품질", "실제 결과 자동 보완",
                    quality["synthesized_actual_count"]])
        for label, key in (("Windows", "windows"), ("Package", "packages")):
            for k, v in (env or {}).get(key, {}).items():
                w.writerow(["# %s" % label, k, v])
        w.writerow([])
        w.writerow(["TC ID", "TC 시험 목적", "TC 판정", "실행 순서", "원본 Step",
                    "수행 내용", "판정", "합격 기준(사용자용)", "확인 결과(사용자용)",
                    "판정 이유(사용자용)", "후속 조치", "원본 기대값", "원본 실제값",
                    "원본 비고"])
        for r in results:
            for sequence, c in enumerate(r.checks, 1):
                w.writerow([r.tc_id, tc_purpose(r.tc_id, r.title), r.verdict,
                            sequence, c.step, c.reader_activity, c.status,
                            c.reader_expected, c.reader_actual, c.reader_reason,
                            c.reader_action, c.expected, c.actual, c.note])

    # JSON
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"title": REPORT_TITLE, "document": DOC_NUMBER,
                   "generated": datetime.now().isoformat(timespec="seconds"),
                   "caveats": list(REPORT_CAVEATS),
                   "environment": env or {},
                   "report_quality": report_quality(results),
                   "totals": total,
                   "results": [r.as_dict() for r in results]},
                  f, ensure_ascii=False, indent=2)

    # HTML
    parts = ["<meta charset='utf-8'><style>%s</style>" % _STYLE,
             "<h1>%s</h1>" % e(REPORT_TITLE),
             "<div class='meta'>문서번호 %s &nbsp;|&nbsp; 생성 %s &nbsp;|&nbsp; TC %d건 "
             "&nbsp;|&nbsp; <span class='PASS'>PASS %d</span> / "
             "<span class='FAIL'>FAIL %d</span> / <span class='MANUAL'>MANUAL %d</span> / "
             "<span class='SKIP'>SKIP %d</span> / <span class='BLOCKED'>BLOCKED %d</span></div>"
             % (DOC_NUMBER, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), len(results),
                total[PASS], total[FAIL], total[MANUAL], total[SKIP], total[BLOCKED]),
             _html_env(env)]
    if REPORT_CAVEATS:
        parts.append("<div class='caveats'><b>유의사항</b><ul>%s</ul></div>"
                     % "".join("<li>%s</li>" % e(cav) for cav in REPORT_CAVEATS))
    parts.append(_html_glossary())
    parts.append(_html_quality(results))
    parts.append(
             "<h2>요약</h2><table class='sum'><tr><th>TC ID</th><th>Title</th><th>판정</th>"
             "<th>P</th><th>F</th><th>M</th><th>S</th><th>B</th><th>소요시간</th></tr>")
    for r in results:
        c = r.counts
        parts.append("<tr><td>%s</td><td>%s</td><td class='s %s'>%s</td>"
                     "<td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td>"
                     "<td>%.1fs</td></tr>"
                     % (e(r.tc_id), e(r.title), r.verdict, r.verdict,
                        c[PASS], c[FAIL], c[MANUAL], c[SKIP], c[BLOCKED],
                        r.duration_seconds))
    parts.append("</table>")
    parts.append(_html_attention(results))

    for r in results:
        parts.append("<h2>%s - %s <span class='%s'>[%s]</span></h2>"
                     % (e(r.tc_id), e(r.title), r.verdict, r.verdict))
        parts.append("<div class='purpose'><b>시험 목적:</b> %s</div>"
                     % e(tc_purpose(r.tc_id, r.title)))
        for sequence, c in enumerate(r.checks, 1):
            parts.append(
                "<div class='check-card %s'>"
                "<div class='check-head'>실행 순서 %d / 원본 Step %s — %s "
                "<span class='s %s'>[%s]</span></div>"
                "<dl><dt>수행 내용</dt><dd>%s</dd>"
                "<dt>합격 기준</dt><dd>%s</dd>"
                "<dt>확인 결과</dt><dd>%s</dd>"
                "<dt>판정 이유</dt><dd>%s</dd>"
                "<dt>후속 조치</dt><dd>%s</dd></dl></div>"
                % (c.status, sequence, e(str(c.step)), e(c.title), c.status,
                   c.status, e(c.reader_activity), e(c.reader_expected), e(c.reader_actual),
                   e(c.reader_reason), e(c.reader_action)))
        if r.timings:
            parts.append("<details><summary>기술 참고: 단계별 소요시간</summary>"
                         "<table><tr><th>종류</th><th>단계/대기</th><th>소요시간</th>"
                         "<th>종료 원인</th><th>상세</th></tr>")
            for t in r.timings:
                parts.append("<tr><td>%s</td><td>%s</td><td>%.3fs</td><td>%s</td>"
                             "<td>%s</td></tr>"
                             % (e(t["kind"]), e(t["name"]), t["duration_seconds"],
                                e(t["outcome"]), e(t["detail"])))
            parts.append("</table></details>")
        if r.evidence:
            parts.append("<div class='meta'>증거: " +
                         ", ".join("<code>%s</code>" % e(p) for p in r.evidence) + "</div>")

    html_path = base + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    txt_path = write_txt(results, base + ".txt", env=env)
    return {"csv": csv_path, "json": json_path, "html": html_path, "txt": txt_path}
