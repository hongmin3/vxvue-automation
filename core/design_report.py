# -*- coding: utf-8 -*-
"""TC 설계 리포트(HTML) 생성기.

`Reports/*.html`은 **특정 실행 회차의 결과**이고, `docs/TC_검증상세.md`는
손으로 쓴 설계 명세다. 사용자 요구(2026-08-20): "각 TC가 어떤 스텝으로
설계되었는지 상세한 리포트를 html 파일로 받고 싶다."

이 모듈은 손으로 쓰지 않고 **코드에서 뽑아** 그 리포트를 만든다 —
`tests/tc*.py` 각 모듈의 docstring·`TC_ID`·`TC_TITLE`, `automation_scope.json`의
현재 자동화 수준, (있으면) 가장 최근 회귀 리포트의 그 TC 판정을 모아 한 페이지로
렌더링한다. 코드가 바뀌면 다음 생성 때 자동으로 반영된다 — 손으로 쓴 HTML은
코드와 바로 어긋난다는 문제를 피한다.

사용: `python run.py design-report` → `docs/TC_설계리포트.html`
"""

import glob
import html as _html
import importlib
import json
import os
import re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TESTS_DIR = os.path.join(ROOT, "tests")
DEFAULT_OUTPUT = os.path.join(ROOT, "docs", "TC_설계리포트.html")


# --- 자료 수집 -----------------------------------------------------------
def _load_scope():
    p = os.path.join(ROOT, "automation_scope.json")
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _discover_modules():
    """`tests/tc*.py`를 import해 `TC_ID`가 있는 모듈만 모은다.

    import 자체가 실패하는 모듈(문법 오류 등)은 감추지 않고 오류로 남긴다 —
    설계 리포트가 조용히 낡은 정보를 보여주면 안 된다.
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(TESTS_DIR, "tc*.py"))):
        mod_name = "tests." + os.path.splitext(os.path.basename(path))[0]
        rel_path = os.path.relpath(path, ROOT).replace("\\", "/")
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:                              # noqa: BLE001
            out[mod_name] = {"import_error": "%s: %s" % (type(exc).__name__, exc),
                              "path": rel_path}
            continue
        tc_id = getattr(mod, "TC_ID", None)
        if not tc_id:
            continue
        out[tc_id] = {
            "module": mod_name,
            "path": rel_path,
            "title": getattr(mod, "TC_TITLE", ""),
            "doc": (mod.__doc__ or "").strip(),
        }
    return out


def _latest_report():
    reports_dir = os.path.join(ROOT, "Reports")
    files = sorted(glob.glob(os.path.join(reports_dir, "Result_*.json")))
    if not files:
        return None, None
    path = files[-1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:                                          # noqa: BLE001
        return path, None
    return path, data


def _report_row(report_data, tc_id):
    if not report_data:
        return None
    for row in report_data.get("results", []):
        if row.get("tc_id") == tc_id:
            return row
    return None


# --- 마크다운 라이트 렌더러 ------------------------------------------------
# tests/tc*.py 모듈 docstring이 실제로 쓰는 부분집합만 다룬다(헤더 #/##/###,
# 코드펜스 ```, 표 |...|, 목록 -/1., 굵게 **, 인라인 코드 `). 일반 마크다운
# 라이브러리는 requirements.txt에 없어 추가하지 않는다(README 3.2절 원칙 —
# 근거 없는 의존성을 늘리지 않는다).
_BULLET_RX = re.compile(r"^[-*]\s+")
_NUM_RX = re.compile(r"^\d+\.\s+")
_TABLE_SEP_RX = re.compile(r"^:?-{2,}:?$")


def _inline(text):
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def _render_table(rows_raw):
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in rows_raw]
    if len(rows) >= 2 and all(_TABLE_SEP_RX.match(c.replace(" ", "")) for c in rows[1]):
        header, body = rows[0], rows[2:]
    else:
        header, body = rows[0], rows[1:]
    out = ["<table>", "<tr>" + "".join("<th>%s</th>" % _inline(c) for c in header) + "</tr>"]
    for row in body:
        out.append("<tr>" + "".join("<td>%s</td>" % _inline(c) for c in row) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def render_markdown_lite(doc):
    """docstring 본문을 HTML로 렌더링한다. 먼저 통째로 escape하므로 원문에
    `<`/`&` 등이 있어도 안전하다 — 그 뒤 escape되지 않는 마크다운 기호(#, -,
    |, `, *)만 보고 태그를 만든다."""
    text = _html.escape(doc or "", quote=False)
    lines = text.split("\n")
    n = len(lines)
    out, para = [], []

    def flush_para():
        if para:
            out.append("<p>%s</p>" % _inline(" ".join(para)))
            para.clear()

    i = 0
    while i < n:
        stripped = lines[i].strip()
        if stripped.startswith("```"):
            flush_para()
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % "\n".join(code))
            continue
        if stripped.startswith("### "):
            flush_para()
            out.append("<h4>%s</h4>" % _inline(stripped[4:]))
            i += 1
            continue
        if stripped.startswith("## "):
            flush_para()
            out.append("<h3>%s</h3>" % _inline(stripped[3:]))
            i += 1
            continue
        if stripped.startswith("# "):
            flush_para()
            out.append("<h3>%s</h3>" % _inline(stripped[2:]))
            i += 1
            continue
        if stripped.startswith("|"):
            flush_para()
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            out.append(_render_table(table_lines))
            continue
        if _BULLET_RX.match(stripped):
            flush_para()
            items = []
            while i < n and _BULLET_RX.match(lines[i].strip()):
                items.append(_inline(_BULLET_RX.sub("", lines[i].strip())))
                i += 1
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % it for it in items))
            continue
        if _NUM_RX.match(stripped):
            flush_para()
            items = []
            while i < n and _NUM_RX.match(lines[i].strip()):
                items.append(_inline(_NUM_RX.sub("", lines[i].strip())))
                i += 1
            out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % it for it in items))
            continue
        if stripped == "":
            flush_para()
            i += 1
            continue
        para.append(stripped)
        i += 1
    flush_para()
    return "\n".join(out)


# --- HTML 조립 -----------------------------------------------------------
_STYLE = """
body{font-family:'Malgun Gothic',sans-serif;margin:24px;color:#1a1a1a;background:#fff;max-width:1100px}
h1{font-size:21px;margin:0 0 4px}
h2{font-size:17px;margin:34px 0 4px;border-bottom:2px solid #333;padding-bottom:4px}
h3{font-size:14.5px;margin:16px 0 4px}
h4{font-size:13px;margin:10px 0 3px;color:#444}
.meta{color:#666;font-size:12px;margin-bottom:18px}
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:700;
       color:#fff;margin-left:8px;vertical-align:middle}
.b-FULL{background:#0a7f3f}.b-PARTIAL{background:#a06000}.b-MANUAL{background:#777}
.b-BLOCKED{background:#6a1b9a}.b-EXCLUDED{background:#999}.b-none{background:#c62828}
.scope-reason{background:#f7f7f7;border-left:3px solid #999;padding:8px 12px;font-size:12.5px;margin:6px 0 14px}
.no-code{background:#fff3e0;border-left:3px solid #e65100;padding:8px 12px;font-size:12.5px;margin:6px 0 14px}
.import-error{background:#ffebee;border-left:3px solid #c62828;padding:8px 12px;font-size:12.5px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0 14px}
th,td{border:1px solid #d8d8d8;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#f3f4f6;font-weight:600}
code{font-family:Consolas,monospace;font-size:12px;word-break:break-all;background:#f5f5f5;padding:1px 3px}
pre{background:#f5f5f5;padding:8px 10px;overflow-x:auto;font-size:12px}
pre code{background:none;padding:0}
.PASS{color:#0a7f3f;font-weight:700}.FAIL{color:#c62828;font-weight:700}
.MANUAL{color:#a06000;font-weight:700}.SKIP{color:#777;font-weight:700}.BLOCKED{color:#6a1b9a;font-weight:700}
.result-box{border:1px solid #d8d8d8;padding:8px 12px;margin:10px 0;font-size:12.5px}
.toc{columns:2;font-size:13px;margin-bottom:20px}
.toc a{text-decoration:none;color:#1a56db}
</style>
"""

_LEVEL_CLASS = {"FULL": "b-FULL", "PARTIAL": "b-PARTIAL", "MANUAL": "b-MANUAL",
                "BLOCKED": "b-BLOCKED", "EXCLUDED": "b-EXCLUDED"}


def _e(s):
    return _html.escape(str(s or ""), quote=True)


def _tc_order(scope, modules):
    seen = []
    for row in scope:
        seen.append(row["tc_id"])
    for tc_id in modules:
        if tc_id not in seen and not tc_id.startswith("tests."):
            seen.append(tc_id)
    return seen


def _section(tc_id, scope_row, mod_info, report_row):
    level = (scope_row or {}).get("level", "")
    reason = (scope_row or {}).get("reason", "")
    title = (mod_info or {}).get("title") or (scope_row or {}).get("title") or ""

    parts = ["<h2>%s%s%s</h2>" % (
        _e(tc_id),
        (" — %s" % _e(title)) if title else "",
        (" <span class='badge %s'>%s</span>" % (_LEVEL_CLASS.get(level, "b-none"), _e(level))
         if level else ""))]

    if reason:
        parts.append("<div class='scope-reason'><b>automation_scope.json 근거</b> — %s</div>"
                     % _e(reason))

    if mod_info is None:
        parts.append("<div class='no-code'>자동화 코드 모듈이 없다 — 현재 수준(%s)이 "
                     "그대로 이번 회귀의 실행 결과다. 코드가 생기면 이 섹션에 "
                     "Step별 설계가 자동으로 채워진다.</div>" % _e(level or "확인 필요"))
    elif "import_error" in mod_info:
        parts.append("<div class='import-error'><b>모듈 import 실패</b> — <code>%s</code>: %s</div>"
                     % (_e(mod_info["path"]), _e(mod_info["import_error"])))
    else:
        parts.append("<div class='meta'>코드: <code>%s</code></div>" % _e(mod_info["path"]))
        parts.append(render_markdown_lite(mod_info["doc"]))

    if report_row:
        c = report_row.get("counts", {})
        parts.append(
            "<div class='result-box'><b>최신 실행 결과</b> "
            "(%s, %s초) — 판정 <span class='%s'>%s</span> · "
            "PASS %d / FAIL %d / MANUAL %d / SKIP %d / BLOCKED %d</div>"
            % (_e(report_row.get("completed", "")), report_row.get("duration_seconds", "?"),
               _e(report_row.get("verdict", "")), _e(report_row.get("verdict", "")),
               c.get("PASS", 0), c.get("FAIL", 0), c.get("MANUAL", 0),
               c.get("SKIP", 0), c.get("BLOCKED", 0)))

    return "\n".join(parts)


def build_html():
    scope = _load_scope()
    modules = _discover_modules()
    report_path, report_data = _latest_report()
    scope_by_id = dict((r["tc_id"], r) for r in scope)

    order = _tc_order(scope, modules)
    sections = []
    for tc_id in order:
        sections.append(_section(tc_id, scope_by_id.get(tc_id), modules.get(tc_id),
                                 _report_row(report_data, tc_id)))

    # scope에도 modules에도 없지만 import에 실패한 모듈(모듈명 자체가 TC_ID가 아님)도 놓치지 않는다.
    orphan_errors = [info for name, info in modules.items()
                     if "import_error" in info and name not in scope_by_id]
    for info in orphan_errors:
        sections.append("<h2>%s</h2><div class='import-error'>%s</div>"
                        % (_e(info["path"]), _e(info["import_error"])))

    toc = "".join("<a href='#%s'>%s</a>" % (_e(tid), _e(tid)) for tid in order)
    # 앵커를 걸기 위해 각 섹션 h2에 id를 심는다.
    sections = [re.sub(r"^<h2>", "<h2 id='%s'>" % _e(tid), s, count=1)
               for tid, s in zip(order, sections)] + sections[len(order):]

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_note = ("최신 실행 결과 출처: <code>%s</code>" % _e(os.path.relpath(report_path, ROOT))
                  if report_path else "최신 실행 결과 없음 — 아직 회귀를 실행하지 않았거나 Reports/가 비어 있다.")

    html_doc = "\n".join([
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>VXvue TC 설계 리포트</title><style>%s" % _STYLE,
        "</head><body>",
        "<h1>VXvue TC 설계 리포트</h1>",
        "<div class='meta'>생성 %s &nbsp;|&nbsp; %s"
        "<br>이 문서는 <code>tests/tc*.py</code> 모듈 docstring과 "
        "<code>automation_scope.json</code>에서 **코드 기준으로 뽑아** 생성한다 "
        "(<code>python run.py design-report</code>). 특정 실행의 PASS/FAIL 결과는 "
        "<code>Reports/</code>를 본다.</div>" % (_e(generated), report_note),
        "<div class='toc'>%s</div>" % toc,
        "\n".join(sections),
        "</body></html>",
    ])
    return html_doc


def write(output_path=None):
    output_path = output_path or DEFAULT_OUTPUT
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    html_doc = build_html()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return output_path
