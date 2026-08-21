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

PASS, FAIL, MANUAL, SKIP, BLOCKED = "PASS", "FAIL", "MANUAL", "SKIP", "BLOCKED"
STATUSES = (PASS, FAIL, MANUAL, SKIP, BLOCKED)

REPORT_TITLE = "VXvue Windows Update 호환성 자동화 결과"
DOC_NUMBER = "R-25-774"


class Check:
    def __init__(self, step, title, status, expected="", actual="", note="",
                 blocks_verdict=True):
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

    def as_dict(self):
        return {"step": self.step, "title": self.title, "status": self.status,
                "expected": str(self.expected), "actual": str(self.actual),
                "note": self.note, "blocks_verdict": self.blocks_verdict}


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
        self.checks.append(Check(step, title, status, expected, actual, note,
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
            "started": self.started.isoformat(timespec="seconds"),
            "completed": (self.completed or datetime.now()).isoformat(timespec="seconds"),
            "duration_seconds": self.duration_seconds,
            "counts": self.counts, "evidence": self.evidence,
            "timings": self.timings,
            "checks": [c.as_dict() for c in self.checks],
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

    for r in results:
        L.append("=" * 80)
        L.append(" %s - %s   ->  %s" % (r.tc_id, r.title, r.verdict))
        L.append("=" * 80)
        for chk in r.checks:
            L.append("  [%s] Step %-3s %s" % (chk.status.center(8), chk.step, chk.title))
            if str(chk.expected):
                L.append("              기대 : %s" % chk.expected)
            if str(chk.actual):
                L.append("              실제 : %s" % chk.actual)
            if chk.note:
                L.append("              비고 : %s" % chk.note)
        if r.evidence:
            L.append("  [증적]")
            for e in r.evidence:
                L.append("    - %s" % e)
        if r.timings:
            L.append("  [소요시간]")
            for t in r.timings:
                L.append("    - %s %s: %.3fs / %s / %s"
                         % (t["kind"], t["name"], t["duration_seconds"],
                            t["outcome"], t["detail"]))
        L.append("")

    fails = [(r, c) for r in results for c in r.checks if c.status == FAIL]
    L.append("=" * 80)
    if fails:
        L.append(" 실패 항목 %d건" % len(fails))
        L.append("=" * 80)
        for r, c in fails:
            L.append("  %s / Step %s / %s" % (r.tc_id, c.step, c.title))
            L.append("     기대=%s" % c.expected)
            L.append("     실제=%s" % c.actual)
    else:
        L.append(" 실패 항목 없음")
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
        for label, key in (("Windows", "windows"), ("Package", "packages")):
            for k, v in (env or {}).get(key, {}).items():
                w.writerow(["# %s" % label, k, v])
        w.writerow([])
        w.writerow(["TC ID", "Title", "TC 판정", "Step", "확인 항목", "판정",
                    "기대값", "실제값", "비고"])
        for r in results:
            for c in r.checks:
                w.writerow([r.tc_id, r.title, r.verdict, c.step, c.title,
                            c.status, c.expected, c.actual, c.note])

    # JSON
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"title": REPORT_TITLE, "document": DOC_NUMBER,
                   "generated": datetime.now().isoformat(timespec="seconds"),
                   "environment": env or {},
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
             _html_env(env),
             "<h2>요약</h2><table class='sum'><tr><th>TC ID</th><th>Title</th><th>판정</th>"
             "<th>P</th><th>F</th><th>M</th><th>S</th><th>B</th><th>소요시간</th></tr>"]
    for r in results:
        c = r.counts
        parts.append("<tr><td>%s</td><td>%s</td><td class='s %s'>%s</td>"
                     "<td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td>"
                     "<td>%.1fs</td></tr>"
                     % (e(r.tc_id), e(r.title), r.verdict, r.verdict,
                        c[PASS], c[FAIL], c[MANUAL], c[SKIP], c[BLOCKED],
                        r.duration_seconds))
    parts.append("</table>")

    for r in results:
        parts.append("<h2>%s - %s <span class='%s'>[%s]</span></h2>"
                     % (e(r.tc_id), e(r.title), r.verdict, r.verdict))
        parts.append("<table class='steps'><colgroup>"
                     "<col class='c-step'><col class='c-title'><col class='c-status'>"
                     "<col class='c-expected'><col class='c-actual'><col class='c-note'>"
                     "</colgroup>"
                     "<tr><th>Step</th><th>확인 항목</th>"
                     "<th>판정</th><th>기대값</th><th>실제값</th>"
                     "<th>비고</th></tr>")
        for c in r.checks:
            parts.append("<tr><td>%s</td><td>%s</td><td class='s %s'>%s</td>"
                         "<td><code>%s</code></td><td><code>%s</code></td><td>%s</td></tr>"
                         % (e(str(c.step)), e(c.title), c.status, c.status,
                            e(str(c.expected)), e(str(c.actual)), e(c.note)))
        parts.append("</table>")
        if r.timings:
            parts.append("<table><tr><th>종류</th><th>단계/대기</th><th>소요시간</th>"
                         "<th>종료 원인</th><th>상세</th></tr>")
            for t in r.timings:
                parts.append("<tr><td>%s</td><td>%s</td><td>%.3fs</td><td>%s</td>"
                             "<td>%s</td></tr>"
                             % (e(t["kind"]), e(t["name"]), t["duration_seconds"],
                                e(t["outcome"]), e(t["detail"])))
            parts.append("</table>")
        if r.evidence:
            parts.append("<div class='meta'>증적: " +
                         ", ".join("<code>%s</code>" % e(p) for p in r.evidence) + "</div>")

    html_path = base + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    txt_path = write_txt(results, base + ".txt", env=env)
    return {"csv": csv_path, "json": json_path, "html": html_path, "txt": txt_path}
