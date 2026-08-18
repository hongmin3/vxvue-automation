# -*- coding: utf-8 -*-
"""TC_WindowsUpdate_14 — Setting 전체 화면 표시 확인.

체크리스트 Step: Setting의 각 탭(대분류/소분류)을 순회하며 화면이 정상적으로
표시되는지 확인한다.

## 무엇을 근거로 PASS/FAIL을 정하는가

| # | 확인 내용 | 근거 |
|---|---|---|
| 1 | Setting 화면 진입 | 좌측 메뉴(ItemWnd) 존재 |
| 2 | 소분류 전부 열림 | 상단 제목 `Static`이 실제로 바뀜(평문으로 읽힘) |
| 3 | 제목 중복 없음 | 같은 제목이 두 번 = 클릭이 다른 항목에 안 먹은 것 |
| 4 | **모든 컨트롤이 스크롤 순회 중 화면에 온전히 노출됨** | 본문 대화상자의 자식 컨트롤 전수와, 페이지별로 뷰포트에 들어온 집합을 비교 |
| 5 | 스크롤을 끝까지 내렸는지 | 페이지 서명이 반복될 때까지 내려가며, 상한에 걸린 화면이 있으면 FAIL |
| 6 | SCP 목록 상세가 DB 등록값과 일치 | 목록 행을 클릭해 나타난 Edit 값 vs `AE_LIST` |
| 7 | **화면별 설정 값이 기준과 일치** | Edit/콤보 값, 라벨, 체크박스 구성 (테마 비의존) |
| 8 | 기준 캡처와 SSIM >= 0.99 | 테마까지 같은 **외형 서명** 기준과만 비교 |
| 9 | 내용이 거의 없는 화면 | 참고 정보 |
| 10 | Setting 트리 실측 목록 확보 | 정보 기록(체크리스트 대조용) |

### 4번이 이 시험의 핵심이다

화면에 보이는 부분만 캡처하면 스크롤 아래 설정은 전혀 검증되지 않는다.
그래서 본문 대화상자의 자식 컨트롤을 **전수 열거**하고(스크롤 밖에 있어도
잡힌다), 페이지를 내려가며 각 컨트롤이 뷰포트에 온전히 들어왔는지를 표시한다.
끝까지 내려도 한 번도 온전히 보이지 않은 컨트롤이 있으면 그 화면은 잘려서
조작할 수 없다는 뜻이므로 FAIL이다. "컨트롤이 하나라도 있으면 통과" 같은
느슨한 기준을 쓰지 않는다.

### 6번 — DICOM 화면은 목록을 클릭해야 상세가 나온다

사용자 확인(2026-08-18): DICOM 서버 설정은 SCP 목록의 항목을 클릭해야 상세
정보가 표시된다. 따라서 목록 행을 순서대로 클릭해 상세를 캡처하고, 표시된
값을 DB `AE_LIST`의 실제 등록값과 대조한다 — 캡처 비교보다 강한 근거다.

### 7번이 테마 문제의 답이다

사용자 확인(2026-08-18): 테마·폰트에 따라 **색상, Setting 창 크기, 폰트가
달라지지만 설정 값과 옵션, 메뉴 구성은 동일하다.** 그래서 판정은 픽셀이 아니라
**값 JSON**으로 한다. 화면마다 Edit 값, 콤보 값(부모 텍스트는 잘리므로 숨은
자식 Edit에서 전체값을 읽는다), 라벨, 체크박스 컨트롤 구성을 뽑아 기준과
비교한다. 좌표·크기·색은 넣지 않는다.

읽을 수 없는 것은 정직하게 남긴다 — 체크박스/라디오는 커스텀 owner-draw라
`BM_GETCHECK`가 항상 0이어서 **UI에서 on/off를 읽을 수 없다**(실측). 픽셀로
체크 여부를 판정하는 방법은 테마에 종속되므로 쓰지 않고, 실제 on/off 값은
DB 스냅샷(`python run.py snapshot`)으로 검증한다.

### 8번 — 기준 캡처는 컨텍스트별로 보관한다

Setting 메뉴는 라이선스·연동 상태에 따라 달라진다(Live View 라이선스가 있으면
`Integration > Camera`가 생기고, 제너레이터를 연동하면 `Integration > Generator`가
생긴다 — 실측). 기준을 하나로 두면 연동이 다른 PC에서 헛된 FAIL이 쏟아진다.
그래서 `core/context.py`의 서명으로 기준 폴더를 나누고, 리포트에 어떤 컨텍스트와
비교했는지 남긴다. 사용자 확인(2026-08-18): 현재 기준은 **VX.LIVE.SERVER 연동 +
XIPL 전체 옵션 + VXvue(Shimadzu) 라이선스 + VXvue AI(VXCAD) 라이선스** 상태다.

## 화소 균일도만으로 '빈 화면'을 판정하면 안 된다 (실측 교훈)

첫 실행에서 `Procedure - Procedure Manager` / `DICOM - Queue` /
`Integration - Generator` 3건이 '빈 화면'으로 FAIL 났는데, 캡처를 열어 보니
**세 화면 모두 실행 버튼 하나만 있는 정상 화면**이었다. 그래서 빈 화면 판정은
참고 정보로 낮추고, 4번(컨트롤 노출)과 7번(기준 대조)을 판정 근거로 쓴다.
"""

import io
import json
import os
import shutil
import time
from datetime import datetime

from core import context as ctx_mod
from core import screen as screen_mod
from core import setting as S
from core.result import TCResult

TC_ID = "TC_WindowsUpdate_14"
TC_TITLE = "Setting 전체 화면 표시 확인 (스크롤·목록 상세 포함)"

# 실행 버튼 하나만 있는 화면. 참고 정보로만 쓴다(판정 근거 아님).
SPARSE_BY_DESIGN = frozenset((
    "Procedure - Procedure Manager",
    "DICOM - Queue",
    "Integration - Generator",
))

# 화면 제목 -> AE_LIST.Type. 목록 상세를 DB와 대조할 화면.
SCP_SCREEN_TYPES = {
    "DICOM - MWL": "DICOM_MWL",
    "DICOM - Storage": "DICOM_STORAGE",
    "DICOM - Print": "DICOM_PRINT",
}

MAX_LIST_ROWS = 8


def _safe(name):
    out = []
    for ch in (name or "unknown"):
        out.append(ch if (ch.isalnum() or ch in " -_.") else "_")
    return "".join(out).strip().replace(" ", "_")


def _capture_dir(root, run_name):
    return os.path.join(root, "Evidence", "tc14", run_name)


def run(ui, cfg, evidence_root=None, run_name="last"):
    r = TCResult(TC_ID, TC_TITLE)
    root = evidence_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = _capture_dir(root, run_name)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)

    if not S.open_setting(ui):
        r.add(1, "Setting 화면 진입", "FAIL", "Setting 화면", "진입 실패")
        return r.finalize()
    r.add(1, "Setting 화면 진입", "PASS", "Setting 화면", S.title(ui) or "(제목 없음)")

    scp_expected = _load_scp_expected(cfg)
    rows = []

    def on_screen(mi, mj, ctrl_id, scr_title):
        base = "%02d_%02d_%s" % (mi + 1, mj + 1, _safe(scr_title))

        def capture_fn(page_index, viewport):
            path = os.path.join(out_dir, "%s_p%02d.png" % (base, page_index + 1))
            return screen_mod.capture(path, bbox=viewport)

        walked = S.page_through(ui, capture_fn)
        controls = walked.get("controls") or []
        unreached = [c for c in controls if c.hwnd not in walked["seen"]]
        values = S.screen_values(ui, scr_title)
        with io.open(os.path.join(out_dir, base + ".json"), "w",
                     encoding="utf-8") as vf:
            json.dump(values, vf, ensure_ascii=False, indent=1, sort_keys=True)

        detail = _walk_list_details(ui, out_dir, base, scr_title, scp_expected)

        blank_pages = [p for p in walked["pages"] if screen_mod.blankness(p)[0]]
        rows.append({
            "major": mi, "minor": mj, "ctrl_id": ctrl_id, "title": scr_title,
            "pages": walked["pages"], "page_count": len(walked["pages"]),
            "controls": len(controls), "unreached": unreached,
            "hit_limit": walked["hit_limit"], "overflow_px": walked["overflow_px"],
            "oversized": walked.get("oversized") or [],
            "values": values,
            "blank_pages": len(blank_pages), "detail": detail,
        })
        for p in walked["pages"]:
            r.attach(p)

    started_wall, started_perf = datetime.now(), time.perf_counter()
    S.walk(ui, on_screen=on_screen)
    r.record_timing("Setting 전체 순회(스크롤·목록 포함)", started_wall, started_perf,
                    "완료", "%d개 화면 / 캡처 %d장"
                    % (len(rows), sum(x["page_count"] for x in rows)), kind="walk")

    # --- 컨텍스트 확정 + 기준 폴더 결정 --------------------------------
    titles = [x["title"] for x in rows if x["title"]]
    dlg = S.content_dialog(ui)
    viewport = (dlg.size if dlg else None)
    context = ctx_mod.collect(setting_titles=titles, viewport=viewport,
                              note="TC14 기준을 만든 시점의 라이선스·연동·테마 상태")
    # 캡처는 테마까지 같은 기준과만 비교한다(테마가 바뀌면 픽셀은 전부 달라진다).
    baseline_dir = os.path.join(root, "Evidence", "tc14_baseline",
                                context["visual_signature"])
    # 구조 기준은 테마와 무관하므로 별도 서명으로 보관한다.
    values_path = os.path.join(root, "Evidence", "tc14_baseline",
                               "values_%s.json" % context["structure_signature"])
    ctx_path = ctx_mod.save(context, os.path.join(out_dir, "context.json"))
    r.attach(ctx_path)

    # --- 판정 ---------------------------------------------------------
    opened = [x for x in rows if x["title"]]
    r.assert_true(2, "모든 소분류 화면이 열렸는지",
                  bool(rows) and len(opened) == len(rows),
                  expected="열기 실패 0건 / 화면 %d개" % len(rows),
                  actual="열림 %d / 전체 %d" % (len(opened), len(rows)))

    tl = [x["title"] for x in opened]
    r.assert_true(3, "화면 제목 중복 없음",
                  len(set(tl)) == len(tl),
                  expected="제목 %d개 모두 서로 다름" % len(tl),
                  actual="고유 제목 %d개" % len(set(tl)),
                  note="중복은 클릭이 다른 항목에 먹지 않았다는 신호다.")

    bad_reach = [x for x in rows if x["unreached"]]
    r.assert_true(4, "모든 컨트롤이 스크롤 순회 중 화면에 온전히 노출됨",
                  not bad_reach,
                  expected="노출되지 않은 컨트롤 0건 (컨트롤 총 %d개)"
                           % sum(x["controls"] for x in rows),
                  actual=("미노출 %d화면: %s" % (len(bad_reach), "; ".join(
                      "%s(%d개)" % (x["title"], len(x["unreached"]))
                      for x in bad_reach[:8])) if bad_reach else "미노출 0건"),
                  note="스크롤로도 끝까지 보이지 않는 컨트롤은 잘려서 조작할 수 없다는 뜻이다.")

    limited = [x for x in rows if x["hit_limit"]]
    scrolled = [x for x in rows if x["page_count"] > 1]
    r.assert_true(5, "스크롤이 필요한 화면을 끝까지 내렸는지",
                  not limited,
                  expected="페이지 상한에 걸린 화면 0건",
                  actual=("상한 도달 %d건: %s" % (len(limited), ", ".join(
                      x["title"] for x in limited[:8])) if limited
                      else "정상 종료 / 스크롤 필요 화면 %d건, 총 캡처 %d장"
                           % (len(scrolled), sum(x["page_count"] for x in rows))))

    _judge_scp(r, rows, scp_expected)

    _judge_values(r, rows, values_path)

    _judge_ssim(r, rows, baseline_dir, out_dir)

    sparse = [x for x in rows if x["blank_pages"]]
    unexpected_sparse = [x for x in sparse if x["title"] not in SPARSE_BY_DESIGN]
    r.add(9, "내용이 거의 없는 화면(참고)", "PASS" if not unexpected_sparse else "MANUAL",
          "허용 목록: %s" % ", ".join(sorted(SPARSE_BY_DESIGN)),
          "%d화면" % len(sparse) + (
              " / 허용 외: %s" % ", ".join(x["title"] for x in unexpected_sparse)
              if unexpected_sparse else ""),
          note="화소 균일도 기준은 오탐이 나기 쉬워 판정 근거로 쓰지 않고 참고로만 둔다.")

    tree_path = _write_tree(rows, out_dir, context)
    r.attach(tree_path)
    r.add(10, "Setting 트리 실측 목록 확보", "PASS",
          "대분류/소분류 목록",
          "%d개 화면 / 구조서명 %s / 외형서명 %s"
          % (len(rows), context["structure_signature"], context["visual_signature"]),
          note=ctx_mod.describe(context))

    return r.finalize()


# --- 값 기준 대조 (테마·폰트 비의존) ---------------------------------
def _judge_values(r, rows, values_path):
    """화면별 **설정 값**을 기준과 대조한다. 이 시험의 주 판정 근거다.

    사용자 확인(2026-08-18): 테마·폰트·옵션에 따라 색상, Setting 창 크기, 폰트가
    달라지지만 **각 설정 값과 옵션, 메뉴 구성은 동일하다.** 그래서 픽셀이 아니라
    값으로 비교한다 — 좌표·크기·색은 지문에 넣지 않는다.

    읽을 수 있는 값의 범위와 한계는 `core/setting.screen_values()` 참고.
    체크박스 상태는 UI에서 읽히지 않으므로 컨트롤 목록만 대조하고, 실제 on/off는
    DB 스냅샷(`snapshot` 명령)으로 검증한다.
    """
    current = dict((x["title"], x["values"]) for x in rows if x["title"])

    if not os.path.exists(values_path):
        os.makedirs(os.path.dirname(values_path), exist_ok=True)
        with io.open(values_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=1, sort_keys=True)
        r.manual(7, "화면별 설정 값 기준 대조 (테마 비의존)",
                 "이 구조 서명의 값 기준이 없어 이번 실행분을 기준으로 저장했다(%s). "
                 "다음 실행부터 자동 비교된다. 첫 실행을 PASS로 위장하지 않는다."
                 % os.path.basename(values_path),
                 expected="기준과 값이 완전 일치",
                 actual="기준 %d화면 생성 (Edit %d개 / 콤보 %d개 / 라벨 %d개)"
                        % (len(current),
                           sum(len(v["edits"]) for v in current.values()),
                           sum(len(v["combos"]) for v in current.values()),
                           sum(len(v["labels"]) for v in current.values())))
        return

    with io.open(values_path, encoding="utf-8") as f:
        baseline = json.load(f)

    missing = sorted(set(baseline) - set(current))
    added = sorted(set(current) - set(baseline))
    diffs = []
    for title in sorted(set(baseline) & set(current)):
        b, c = baseline[title], current[title]
        for kind in ("edits", "combos"):
            bd, cd = b.get(kind) or {}, c.get(kind) or {}
            for key in sorted(set(bd) | set(cd)):
                if bd.get(key) != cd.get(key):
                    diffs.append("%s / %s[%s]: %r -> %r"
                                 % (title, kind, key, bd.get(key), cd.get(key)))
        if sorted(b.get("labels") or []) != sorted(c.get("labels") or []):
            only_b = sorted(set(b.get("labels") or []) - set(c.get("labels") or []))
            only_c = sorted(set(c.get("labels") or []) - set(b.get("labels") or []))
            diffs.append("%s / labels: 기준에만 %s / 현재에만 %s"
                         % (title, only_b[:5], only_c[:5]))
        bids = [x["id"] for x in b.get("unreadable_state_controls") or []]
        cids = [x["id"] for x in c.get("unreadable_state_controls") or []]
        if sorted(bids) != sorted(cids):
            diffs.append("%s / 체크박스 구성: %s -> %s" % (title, bids, cids))

    ok = not (missing or added or diffs)
    r.assert_true(7, "화면별 설정 값 기준 대조 (테마 비의존)",
                  ok,
                  expected="기준 %d화면의 값과 완전 일치" % len(baseline),
                  actual=("일치 (Edit/콤보/라벨/체크박스 구성 전부 동일)" if ok else
                          "없어진 화면 %d / 새 화면 %d / 값 차이 %d건%s"
                          % (len(missing), len(added), len(diffs),
                             (" -> " + "; ".join(diffs[:6])) if diffs else "")),
                  note="좌표·크기·색은 비교하지 않는다. 테마·폰트가 바뀌어도 값과 "
                       "옵션은 같아야 하므로 이 비교가 테마에 영향받지 않는 판정 "
                       "근거가 된다. 체크박스 on/off는 UI에서 읽히지 않아 DB "
                       "스냅샷으로 별도 검증한다. 기준: %s"
                       % os.path.basename(values_path))


# --- SCP 목록 상세 ----------------------------------------------------
def _load_scp_expected(cfg):
    """DB `AE_LIST`에서 화면별 기대 등록값을 읽어 온다."""
    try:
        from core.db import VXvueDb
        db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
        rows = db.ae_list()
    except Exception as exc:                        # noqa: BLE001
        return {"_error": str(exc)}
    out = {}
    for row in rows:
        out.setdefault(row.get("Type"), []).append(row)
    for key in out:
        out[key].sort(key=lambda x: x.get("AEListKey") or 0)
    return out


def _walk_list_details(ui, out_dir, base, scr_title, scp_expected):
    """화면의 **모든 목록**에서 실제 행을 전부 클릭해 상세를 캡처·판독한다.

    두 가지 실패를 고친 구현이다(2026-08-18 사용자 지적).

    1. 예전에는 면적이 가장 큰 목록 하나만 다뤘다. DICOM 화면에는 비어 있는 큰
       목록(Verification 로그)이 함께 있어서 **빈 영역을 좌표로 몇 번 찍다 끝났다.**
       -> 화면의 모든 목록을 돌고, 행이 실제로 있는 것만 처리한다.
    2. 행 위치를 헤더/행 높이로 추정했다. -> 행은 `ListItem` 자식 윈도우로
       존재하고 데이터가 없으면 hidden이므로, **보이는 ListItem을 직접 클릭**한다.
       좌표 추정이 사라졌다.

    목록이 화면보다 길면 목록 내부를 스크롤해 끝까지 내려간다.
    """
    lists = S.list_ctrls(ui)
    if not lists:
        return None

    scp_type = SCP_SCREEN_TYPES.get(scr_title)
    expected = (scp_expected or {}).get(scp_type) or []
    items, seen_sigs = [], set()

    for li, lc in enumerate(lists):
        def on_row(page, idx, row, _li=li):
            key = "%s_l%02d_p%02d_r%02d" % (base, _li + 1, page + 1, idx + 1)
            ui.click(S.row_click_point(ui, row), settle=0.7)
            dlg = S.content_dialog(ui)
            path = screen_mod.capture(os.path.join(out_dir, key + ".png"),
                                      bbox=dlg.rect if dlg else None)
            sig = S._page_signature(path)
            fields = S.scp_detail_fields(ui)
            items.append({"list": _li, "page": page, "index": idx,
                          "capture": path, "fields": fields,
                          "duplicate": sig in seen_sigs})
            seen_sigs.add(sig)

        S.iter_list_rows(ui, lc, on_row)

    if not items:
        return None
    return {"screen": scr_title, "scp_type": scp_type,
            "expected": expected, "items": items,
            "list_count": len(lists)}


def _judge_scp(r, rows, scp_expected):
    """SCP 목록 상세 표시값이 DB 등록값과 맞는지 판정한다."""
    if isinstance(scp_expected, dict) and scp_expected.get("_error"):
        r.manual(6, "SCP 목록 상세와 DB 등록값 대조",
                 "DB 조회 실패로 대조하지 못했다: %s" % scp_expected["_error"])
        return

    checked, mismatches = [], []
    for x in rows:
        d = x["detail"]
        if not d or not d.get("scp_type"):
            continue
        # 여러 목록 중 상세가 채워진 항목만 대조 대상으로 본다.
        filled = [it for it in d["items"] if it["fields"]["texts"]]
        for exp, item in zip(d["expected"], filled):
            joined = " | ".join(item["fields"]["texts"])
            want = [str(exp.get("Title") or ""), str(exp.get("IP") or ""),
                    str(exp.get("Port") or "")]
            missing = [w for w in want if w and w not in joined]
            checked.append("%s row%d(%s)" % (d["screen"], item["index"] + 1,
                                             exp.get("Name")))
            if missing:
                mismatches.append("%s: 화면에 없음=%s / 화면값=%s"
                                  % (d["screen"], ",".join(missing), joined[:200]))

    if not checked:
        r.manual(6, "SCP 목록 상세와 DB 등록값 대조",
                 "대조 대상 화면에서 목록 행을 열지 못했다. 등록된 SCP가 없거나 "
                 "행 클릭 좌표(헤더/행 높이)를 재확인해야 한다.")
        return

    r.assert_true(6, "SCP 목록 상세가 DB 등록값과 일치",
                  not mismatches,
                  expected="대조 %d건 모두 일치 (AE Title/IP/Port)" % len(checked),
                  actual=("불일치 %d건: %s" % (len(mismatches), "; ".join(mismatches[:5]))
                          if mismatches else "대조 %d건 일치: %s"
                          % (len(checked), ", ".join(checked))),
                  note="DICOM 서버 설정은 목록 항목을 클릭해야 상세가 나타나므로, "
                       "행을 순서대로 클릭해 표시값을 읽고 DB와 비교했다.")


# --- SSIM ------------------------------------------------------------
def _judge_ssim(r, rows, baseline_dir, out_dir):
    os.makedirs(baseline_dir, exist_ok=True)
    compared, failed, created = [], [], 0
    for x in rows:
        caps = list(x["pages"])
        d = x["detail"]
        if d:
            caps += [i["capture"] for i in d["items"]]
        for cur in caps:
            name = os.path.basename(cur)
            base = os.path.join(baseline_dir, name)
            result = screen_mod.compare(
                base, cur, diff_path=os.path.join(out_dir, "DIFF_" + name))
            if result["score"] is None:
                try:
                    shutil.copyfile(cur, base)
                    created += 1
                except OSError:
                    pass
                continue
            compared.append((name, result["score"]))
            if not result["passed"]:
                failed.append((name, result["score"], result["diff"]))

    if not compared:
        r.manual(8, "기준 캡처와 구조적 유사도(SSIM) 비교",
                 "이 컨텍스트의 기준 캡처가 없어 이번 실행분 %d장을 기준으로 저장했다"
                 "(%s). 다음 실행부터 자동 비교되며 임계값 적정성도 그때 실측으로 "
                 "조정한다. 첫 실행을 PASS로 위장하지 않는다." % (created, baseline_dir),
                 expected="SSIM >= %.2f" % screen_mod.SSIM_THRESHOLD,
                 actual="기준 %d장 생성" % created)
        return

    worst = min(compared, key=lambda t: t[1])
    r.assert_true(8, "기준 캡처와 구조적 유사도(SSIM) 비교",
                  not failed,
                  expected="전 페이지 SSIM >= %.2f" % screen_mod.SSIM_THRESHOLD,
                  actual="비교 %d장 / 미달 %d장 / 최저 %.6f (%s)%s"
                         % (len(compared), len(failed), worst[1], worst[0],
                            (" / 신규 기준 %d장" % created) if created else ""),
                  note="기준 폴더: %s" % baseline_dir)


def _write_tree(rows, out_dir, context):
    path = os.path.join(out_dir, "setting_tree.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("컨텍스트: %s\n" % ctx_mod.describe(context))
        f.write("=" * 78 + "\n")
        cur = None
        for x in rows:
            if x["major"] != cur:
                cur = x["major"]
                f.write("\n[대분류 %d]\n" % (cur + 1))
            f.write("  minor=%-3s ctrl_id=%-3s pages=%-2d controls=%-3d "
                    "overflow=%-4d rows=%-2s title=%s\n"
                    % (x["minor"] + 1 if x["minor"] is not None else "-",
                       x["ctrl_id"], x["page_count"], x["controls"],
                       x["overflow_px"],
                       len(x["detail"]["items"]) if x["detail"] else 0,
                       x["title"]))
    return path
