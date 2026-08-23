# -*- coding: utf-8 -*-
"""TC_WindowsUpdate_14 — Setting 전체 화면 표시 확인.

체크리스트 Step: Setting의 각 탭(대분류/소분류)을 순회하며 화면이 정상적으로
표시되는지 확인한다.

## 이 TC가 실제로 검증하는 것 (사용자 확인 2026-08-19)

TC14는 **Windows Update 이후 각 탭(대분류/소분류)이 여전히 정상적으로
클릭·표시되고, 화면에 있어야 할 옵션이 그대로 있는지**를 확인하는 시험이다.
"기준값과 완전히 같아야 PASS"인 정밀 회귀는 이 TC의 목적이 아니다 — 그런
값 단위 회귀는 `tests/tc_setting_export_import.py`(Setting Export/Import)
쪽에서 다룬다. 그래서 여기서는:

- 화면 진입·노출·스크롤 등 **탐색 자체가 깨졌는지**는 FAIL로 판정한다.
- 화면에 있는 **옵션 구성(트리)이나 표시 텍스트가 이전 실행과 달라진 것**은
  FAIL이 아니라 `확인 필요`(MANUAL)로만 표시하고, 무엇이 달라졌는지 적는다.
  달라졌다는 사실 자체가 결함이라고 단정할 수 없기 때문이다(연동·라이선스
  상태에 따라 메뉴 구성이 정상적으로 늘어나는 사례가 실제로 있었다).

| # | 확인 내용 | 근거 | 판정 |
|---|---|---|---|
| 1 | Setting 화면 진입 | 좌측 메뉴(ItemWnd) 존재 | PASS/FAIL |
| 2 | 소분류 전부 열림 | 상단 제목 `Static`이 실제로 바뀜(평문으로 읽힘) | PASS/FAIL |
| 3 | 제목 중복 없음 | 같은 제목이 두 번 = 클릭이 다른 항목에 안 먹은 것 | PASS/FAIL |
| 4 | **모든 컨트롤이 스크롤 순회 중 화면에 온전히 노출됨** | 본문 대화상자의 자식 컨트롤 전수와, 페이지별로 뷰포트에 들어온 집합을 비교 | PASS/FAIL |
| 5 | 스크롤을 끝까지 내렸는지 | 페이지 서명이 반복될 때까지 내려가며, 상한에 걸린 화면이 있으면 FAIL | PASS/FAIL |
| 6 | SCP 목록 상세가 DB 등록값과 일치 | 목록 행을 클릭해 나타난 Edit 값 vs `AE_LIST` | PASS/FAIL |
| 7 | **화면별 옵션 구성(트리) 확인** | Edit/콤보/라벨/체크박스의 **존재 여부**를 기준과 대조. 값 텍스트가 달라도 FAIL이 아니라 확인 필요 | PASS/MANUAL |
| 8 | 내용이 거의 없는 화면 | 참고 정보 | PASS/MANUAL |
| 9 | Setting 트리 실측 목록 확보 | 정보 기록(체크리스트 대조용) | PASS |

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

### 7번 — 트리(구성) 대조이지 값 대조가 아니다

사용자 확인(2026-08-19): 테마·폰트에 따라 **색상, Setting 창 크기, 폰트가
달라지지만 설정 값과 옵션, 메뉴 구성은 동일하다.** 그래서 판정은 픽셀이 아니라
**값 JSON**으로 한다. 화면마다 Edit 값, 콤보 값(부모 텍스트는 잘리므로 숨은
자식 Edit에서 전체값을 읽는다), 라벨, 체크박스 컨트롤 구성을 뽑아 기준과
비교한다. 좌표·크기·색은 넣지 않는다.

다만 **이 비교의 결론은 PASS 또는 `확인 필요`뿐이고 FAIL은 없다.** 옵션
구성(어떤 Edit/콤보/체크박스/라벨이 있는지)이나 표시 텍스트가 기준과 달라도
그 자체를 결함으로 단정하지 않는다 — 라이선스·연동 상태에 따라 메뉴가 정상
적으로 늘어나는 사례가 실제로 있었다(Live View 연동 시 `Integration > Camera`
등장). 값이 완전히 같아야만 PASS로 인정하는 정밀 회귀는
`tests/tc_setting_export_import.py` 쪽 책임이다.

읽을 수 없는 것은 정직하게 남긴다 — 체크박스/라디오는 커스텀 owner-draw라
`BM_GETCHECK`가 항상 0이어서 **UI에서 on/off를 읽을 수 없다**(실측). 픽셀로
체크 여부를 판정하는 방법은 테마에 종속되므로 쓰지 않고, 실제 on/off 값은
DB 스냅샷(`python run.py snapshot`)으로 검증한다.

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
from core.result import MANUAL, PASS, SKIP, TCResult

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


def run(ui, cfg, evidence_root=None, run_name="last", sample=False, deep=False):
    """Setting 각 탭을 순회해 화면이 정상 표시되는지 확인한다.

    `deep=False`(기본)는 **체크리스트 원문 그대로** 한다 — 탭을 하나씩 열어
    제목이 실제로 바뀌는지, 본문에 컨트롤이 그려지는지, 화면 1장을 증거로
    남긴다. 사용자 지시(2026-08-20): *"그냥 각 탭을 한번씩 클릭하고 각 탭의
    내용이 문제없이 나온다, 이 정도만 테스트하면 되는 것 같은데."*

    `deep=True`는 여기에 스크롤 전수 순회·SCP 상세 DB 대조·기준 트리 대조를
    더한다(실측 1219초 / 55화면 / 캡처 76장). 이쪽이 잡아내는 것이 따로 있어
    지우지 않고 옵션으로 남겼다 — Windows Update로 폰트·DPI가 바뀌면 컨트롤이
    화면 밖으로 밀려 **조작할 수 없는 설정**이 생기는데(README 4.5절), 그것은
    탭을 열어 보는 것만으로는 드러나지 않는다. 정밀 검증이 필요할 때 쓴다:
    `python run.py tc14 --deep`.

    `sample=True`면 **대분류마다 첫 소분류 하나만** 열어본다(짧은 회귀용).
    전 화면 순회는 실측 829초로 회귀에서 가장 오래 걸리는 항목이다. 표본
    모드는 "대분류 10개가 모두 펼쳐지고 그 아래 화면이 그려진다"는 것까지만
    확인하며, **화면별 값 대조 범위가 줄어든다** — 그 사실을 판정 항목으로
    남기므로 전체 순회 결과와 혼동되지 않는다.
    """
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

        if not deep:
            # 가벼운 확인: 화면 1장 캡처하고 본문 컨트롤 유무만 본다.
            # 스크롤 순회·값 추출·목록 상세 클릭은 하지 않는다.
            content_dlg = S.content_dialog(ui)
            page = capture_fn(0, content_dlg.rect if content_dlg else None)
            content = S.content_controls(ui)
            rows.append({
                "major": mi, "minor": mj, "ctrl_id": ctrl_id, "title": scr_title,
                "pages": [page], "page_count": 1,
                "controls": len(content), "unreached": [],
                "hit_limit": False, "overflow_px": 0, "oversized": [],
                "values": {}, "blank_pages": 0, "detail": None,
            })
            r.attach(page)
            return

        walked = S.page_through(ui, capture_fn)
        controls = walked.get("controls") or []
        unreached = [c for c in controls if c.hwnd not in walked["seen"]]
        values = S.screen_values(ui, scr_title)
        with io.open(os.path.join(out_dir, base + ".json"), "w",
                     encoding="utf-8") as vf:
            json.dump(values, vf, ensure_ascii=False, indent=1, sort_keys=True)

        # page_through()가 화면을 마지막 페이지(스크롤 맨 아래)에 둔 채로
        # 끝난다. 목록 행의 rect는 현재 스크롤 위치 기준으로 갱신되므로, 맨
        # 위로 되돌리지 않으면 row_click_point()가 화면 밖(스크롤로 밀려난
        # 위치)을 클릭한다 — DICOM - Storage(9페이지 화면)에서 실측 확인된
        # 원인. 클릭이 목록을 완전히 비켜가면 상세 패널이 아직 그 항목으로
        # 갱신되지 않은 채 남아 있던 필드(QXLink Server='service' 등)만
        # 읽혀 "화면값=service"처럼 대조가 어긋난다(2026-08-19).
        S.scroll_to_top(ui)
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
    # 표본 모드는 대분류별 첫 소분류만 연다. `walk()`가 대분류를 펼치는 일 자체는
    # 그대로 하므로 "대분류 10개가 모두 펼쳐진다"는 확인은 유지된다.
    skipped = []

    def _filter(mi, mj, minor_id):
        if mj == 0:
            return True
        skipped.append((mi, mj, minor_id))
        return False

    walked = S.walk(ui, on_screen=on_screen,
                    screen_filter=_filter if sample else None)
    r.record_timing("Setting %s 순회(%s)"
                    % ("표본" if sample else "전체",
                       "스크롤·목록 포함" if deep else "탭 열기·표시 확인"),
                    started_wall, started_perf,
                    "완료", "%d개 화면 / 캡처 %d장"
                    % (len(rows), sum(x["page_count"] for x in rows)), kind="walk")
    if sample:
        # **줄인 범위를 판정 항목으로 명시한다.** 그러지 않으면 리포트만 보고
        # 전 화면을 확인한 것으로 오해한다.
        r.add(len(r.checks) + 1, "짧은 회귀 — Setting 표본 순회 범위", MANUAL,
              expected="전 화면 순회(기준 대조의 정식 범위)",
              actual="대분류 %d개 / 확인한 화면 %d개 / 건너뛴 화면 %d개"
                     % (len(set(x["major"] for x in walked)), len(rows),
                        len(skipped)),
              note="`--quick`으로 실행되어 **대분류마다 첫 소분류만** 열었다. "
                   "대분류가 모두 펼쳐지는 것과 그 아래 화면이 그려지는 것까지는 "
                   "확인했으나, **건너뛴 화면의 값 대조는 수행하지 않았다.** "
                   "정식 판정은 `python run.py regression`(전체 순회)으로 받아야 "
                   "한다. 건너뛴 화면 ctrl_id: %s"
                   % (", ".join(str(c) for _mi, _mj, c in skipped) or "없음"))

    # --- 컨텍스트 확정 + 기준 폴더 결정 --------------------------------
    titles = [x["title"] for x in rows if x["title"]]
    dlg = S.content_dialog(ui)
    viewport = (dlg.size if dlg else None)
    context = ctx_mod.collect(setting_titles=titles, viewport=viewport,
                              note="TC14 기준을 만든 시점의 라이선스·연동·테마 상태")
    # 옵션 구성(트리) 기준은 테마·폰트와 무관하므로 구조 서명으로 보관한다.
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

    # 본문에 컨트롤이 실제로 그려졌는지 — 가벼운 확인의 핵심이다.
    # "탭 내용이 문제없이 나온다"는 것을 이것으로 판정한다.
    empty = [x for x in opened if not x["controls"]]
    r.assert_true(4, "각 탭의 본문 내용이 표시됨",
                  not empty,
                  expected="본문 컨트롤 0개인 화면 없음",
                  actual=("빈 화면 %d건: %s" % (len(empty), ", ".join(
                      x["title"] for x in empty[:8])) if empty
                      else "화면 %d개 모두 본문 표시 / 컨트롤 총 %d개"
                           % (len(opened), sum(x["controls"] for x in rows))),
                  note="탭을 열었는데 본문이 비어 있으면 화면이 그려지지 않은 것이다.")

    if not deep:
        # **확인하지 않은 것을 PASS로 적지 않는다.** 아래 세 항목은 깊은 검증
        # 전용이므로, 가벼운 모드에서는 수행하지 않았다는 사실만 남긴다.
        r.add(len(r.checks) + 1, "깊은 검증 항목 (이번 실행에서 미수행)", SKIP,
              expected="스크롤 전수 노출 확인 / SCP 상세 DB 대조 / 옵션 구성 기준 대조",
              actual="수행하지 않음 — 탭 열기·표시 확인까지만",
              note="체크리스트 원문(각 탭 순회·정상 표시)은 위 항목으로 충족한다. "
                   "폰트·DPI 변화로 컨트롤이 화면 밖으로 밀려 **조작할 수 없는 "
                   "설정**이 생기는 경우는 탭을 여는 것만으로 드러나지 않으므로, "
                   "그 확인이 필요하면 `python run.py tc14 --deep`으로 수행한다"
                   "(실측 1219초 / 55화면). 이 Step은 사용자 확정(2026-08-21)에 "
                   "따라 PASS를 막지 않는 예외다 — 체크리스트 원문 범위는 위에서 "
                   "이미 충족했고 `--deep`은 그 위의 정밀 검증이기 때문이다.",
              blocks_verdict=False)
        tree_path = _write_tree(rows, out_dir, context)
        r.attach(tree_path)
        r.add(len(r.checks) + 1, "Setting 트리 실측 목록 확보", PASS,
              expected="대분류/소분류 목록",
              actual="%d개 화면 / 구조서명 %s"
                     % (len(rows), context["structure_signature"]),
              note=ctx_mod.describe(context))
        return r.finalize()

    bad_reach = [x for x in rows if x["unreached"]]
    r.assert_true(5, "모든 컨트롤이 스크롤 순회 중 화면에 온전히 노출됨",
                  not bad_reach,
                  expected="노출되지 않은 컨트롤 0건 (컨트롤 총 %d개)"
                           % sum(x["controls"] for x in rows),
                  actual=("미노출 %d화면: %s" % (len(bad_reach), "; ".join(
                      "%s(%d개)" % (x["title"], len(x["unreached"]))
                      for x in bad_reach[:8])) if bad_reach else "미노출 0건"),
                  note="스크롤로도 끝까지 보이지 않는 컨트롤은 잘려서 조작할 수 없다는 뜻이다.")

    limited = [x for x in rows if x["hit_limit"]]
    scrolled = [x for x in rows if x["page_count"] > 1]
    r.assert_true(6, "스크롤이 필요한 화면을 끝까지 내렸는지",
                  not limited,
                  expected="페이지 상한에 걸린 화면 0건",
                  actual=("상한 도달 %d건: %s" % (len(limited), ", ".join(
                      x["title"] for x in limited[:8])) if limited
                      else "정상 종료 / 스크롤 필요 화면 %d건, 총 캡처 %d장"
                           % (len(scrolled), sum(x["page_count"] for x in rows))))

    _judge_scp(r, rows, scp_expected)

    _judge_option_tree(r, rows, values_path)

    sparse = [x for x in rows if x["blank_pages"]]
    unexpected_sparse = [x for x in sparse if x["title"] not in SPARSE_BY_DESIGN]
    r.add(8, "내용이 거의 없는 화면(참고)", "PASS" if not unexpected_sparse else "MANUAL",
          "허용 목록: %s" % ", ".join(sorted(SPARSE_BY_DESIGN)),
          "%d화면" % len(sparse) + (
              " / 허용 외: %s" % ", ".join(x["title"] for x in unexpected_sparse)
              if unexpected_sparse else ""),
          note="화소 균일도 기준은 오탐이 나기 쉬워 판정 근거로 쓰지 않고 참고로만 둔다.")

    tree_path = _write_tree(rows, out_dir, context)
    r.attach(tree_path)
    r.add(9, "Setting 트리 실측 목록 확보", "PASS",
          "대분류/소분류 목록",
          "%d개 화면 / 구조서명 %s / 외형서명 %s"
          % (len(rows), context["structure_signature"], context["visual_signature"]),
          note=ctx_mod.describe(context))

    return r.finalize()


# --- 옵션 구성(트리) 대조 (테마·폰트 비의존, FAIL 없음) ----------------
def _judge_option_tree(r, rows, values_path):
    """화면별 **옵션 구성(어떤 Edit/콤보/라벨/체크박스가 있는지)**을 기준과
    대조한다. 값 텍스트가 다르거나 구성이 달라져도 FAIL이 아니라 `확인 필요`
    (MANUAL)로만 표시한다.

    사용자 확인(2026-08-19): TC14의 목적은 "Windows Update로 탭 클릭·옵션
    노출이 깨지지 않았는가"이지, 각 옵션 값이 기준과 완전히 같아야 하는 정밀
    회귀가 아니다. 값 단위로 PASS/FAIL을 가르는 회귀는
    `tests/tc_setting_export_import.py`에서 수행한다. 여기서는 차이가 있다는
    사실과 무엇이 달라졌는지만 남긴다 — 라이선스·연동 상태 변화로 메뉴 구성이
    정상적으로 늘어나는 사례가 실제로 있었기 때문에, 차이를 곧 결함으로
    단정하지 않는다.

    읽을 수 있는 값의 범위와 한계는 `core/setting.screen_values()` 참고.
    체크박스 상태는 UI에서 읽히지 않으므로 컨트롤 목록만 대조하고, 실제 on/off는
    DB 스냅샷(`snapshot` 명령)으로 검증한다.
    """
    current = dict((x["title"], x["values"]) for x in rows if x["title"])

    if not os.path.exists(values_path):
        os.makedirs(os.path.dirname(values_path), exist_ok=True)
        with io.open(values_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=1, sort_keys=True)
        r.manual(7, "화면별 옵션 구성(트리) 기준 대조",
                 "이 구조 서명의 기준이 없어 이번 실행분을 기준으로 저장했다(%s). "
                 "다음 실행부터 자동 비교된다. 첫 실행을 PASS로 위장하지 않는다."
                 % os.path.basename(values_path),
                 expected="기준과 옵션 구성이 동일 (다르면 확인 필요로 표시, FAIL 아님)",
                 actual="기준 %d화면 생성 (Edit %d개 / 콤보 %d개 / 라벨 %d개)"
                        % (len(current),
                           sum(len(v["edits"]) for v in current.values()),
                           sum(len(v["combos"]) for v in current.values()),
                           sum(len(v["labels"]) for v in current.values())))
        return

    with io.open(values_path, encoding="utf-8") as f:
        baseline = json.load(f)

    d = S.diff_all_screen_values(baseline, current)
    missing, added = d["missing"], d["added"]
    struct_diffs, value_diffs = d["struct_diffs"], d["value_diffs"]

    ok = not (missing or added or struct_diffs or value_diffs)
    status = PASS if ok else MANUAL
    r.add(7, "화면별 옵션 구성(트리) 기준 대조", status,
          expected="기준 %d화면의 옵션 구성과 표시값이 동일" % len(baseline),
          actual=("일치 (Edit/콤보/라벨/체크박스 구성과 값 전부 동일)" if ok else
                  "확인 필요 - 없어진 화면 %d / 새 화면 %d / 구성 차이 %d건 / "
                  "값 차이 %d건%s"
                  % (len(missing), len(added), len(struct_diffs), len(value_diffs),
                     (" -> " + "; ".join((struct_diffs + value_diffs)[:6])) if
                     (struct_diffs or value_diffs) else "")),
          note="구성(옵션 존재 여부)이나 값이 달라도 FAIL로 판정하지 않는다 - "
               "Windows Update로 탐색 자체가 깨졌는지가 이 TC의 판정 기준이고, "
               "값 단위 회귀(완전 일치=PASS)는 Setting Export/Import TC의 책임이다. "
               "차이가 있으면 사람이 원인(정상적인 연동/라이선스 변화인지, 실제 "
               "결함인지)을 확인해야 한다. 기준: %s" % os.path.basename(values_path))


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
            fields = S.scp_detail_fields(ui)
            # 상세 패널이 클릭 직후 아직 채워지지 않은 상태로 잡힐 수 있다
            # (2026-08-19 실측: DICOM - Storage에서 Edit 1개(불특정 텍스트)만
            # 읽힌 사례). 값이 1개 이하로 빈약하면 한 번 더 대기 후 재판독한다.
            if len(fields["texts"]) <= 1:
                time.sleep(0.6)
                fields = S.scp_detail_fields(ui)
            dlg = S.content_dialog(ui)
            path = screen_mod.capture(os.path.join(out_dir, key + ".png"),
                                      bbox=dlg.rect if dlg else None)
            sig = S._page_signature(path)
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
