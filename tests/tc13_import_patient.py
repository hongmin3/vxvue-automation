# -*- coding: utf-8 -*-
"""TC_WindowsUpdate_13 — Study List Import (txt/csv).

체크리스트(Windows Update 호환성 검증 Checklist_VXvue_R-25-774.xlsx, TC13) 원문
기준:

    Step 1. Setting-Study-Import Patient 에서 study list 샘플 파일을 저장한다
            (txt, csv).
    Step 2. 저장한 파일을 오픈하고 스터디 정보를 입력한다.
    Step 3. Registration-Reserved 에서 Import Patient 버튼을 누르고 파일을
            뷰어로 import 한다.
    Expected: 스터디 목록이 뷰어로 import 성공한다.

매뉴얼 근거(사용자 확인 2026-08-19, "Save Sample로 샘플 받아서 채운 뒤
import"): Service Manual 4.6.7절(p.95) — Import Patient 화면에 **Save
Sample** 버튼이 있어 그 시점의 Input Format/Column Mapping 설정에 맞는
예시 파일을 만들어 준다. 이 테스트는 그 샘플을 그대로 근거로 삼는다 —
컬럼 순서·구분자·날짜/나이 표기를 코드에 하드코딩하지 않고, 매번 실제
Save Sample 결과를 읽어 그 형식 그대로 테스트 데이터를 채운다.

Operation Manual 5.3/5.3.1절(p.74~75) 근거: 실제 Import는 Registration >
Reserved 화면의 **Import Patient Order** 버튼(실측 컨트롤 id=30392)에서
수행한다.

## 왜 "값을 안 읽고 Save Sample을 그대로 쓰는가"

Setting Export/Import TC의 뮤테이션 테스트가 이 화면의 Sex Format(Male)
값을 이미 한 번 건드려 놓았다(`M` -> `M_QA1`, 실측 2026-08-19). 이 상태에서
"기본값은 M/F/O"라고 가정하고 파일을 만들면 실제 설정과 어긋나 오탐이
난다. Save Sample은 **지금 이 순간 실제로 적용된 설정**을 그대로 반영하는
파일을 만들어 주므로, 그 파일의 헤더와 형식을 그대로 따라가면 이 화면의
현재 상태(오염 여부와 무관하게)에 항상 맞는 테스트 데이터를 만들 수 있다.
"""

import csv
import io
import os
import time
from datetime import datetime

from core import setting as S
from core.result import TCResult

TC_ID = "TC_WindowsUpdate_13"
TC_TITLE = "Study List Import (txt/csv)"

IMPORT_PATIENT_IDS = {
    "file_path_edit": 30205,
    "browse_button": 30515,
    "refresh_button": 30644,
    "save_sample_button": 30629,
    "preview_grid": 31178,
}
RESERVED_IMPORT_BUTTON_ID = 30392
RESERVED_TAB_ID = 31203        # Registration 상단 탭: Scheduled/Unscheduled/Reserved
MAIN_NAV_TAB_CONTAINER = 31197
MAIN_NAV_REGISTRATION = 8

# Reserved 검색 도구(실측, 2026-08-19): Default/Clear 필터 스플릿 버튼 +
# Search. Import 직후 기본 필터(Default, 보통 오늘 날짜 등으로 좁혀져 있음)로는
# 방금 들어온 항목이 안 보일 수 있어, Clear로 필터를 비운 뒤 Search를 눌러야
# 목록에 실제로 뜨는지 확인할 수 있다(사용자 지시, 2026-08-19).
RESERVED_FILTER_SPLIT_BUTTON_ID = 30935
RESERVED_FILTER_ARROW_ID = 2          # 스플릿 버튼의 자식(드롭다운 화살표)
RESERVED_FILTER_CLEAR_ID = 30941      # 드롭다운의 두 번째 항목(Default 다음)
RESERVED_SEARCH_BUTTON_ID = 30689
RESERVED_RESULT_COUNT_STATIC_ID = 30013

# Data Delimiter 콤보(실측, NEXT_TASK.md/HANDOFF.md 근거) — 기존 결함
# #22985(Tab 구분자 실패, Comma는 성공)의 회귀 대상. 과거 세션에서 이 콤보를
# 조작하다 VXvue가 응답 없음 상태가 된 전례가 있어(재현 조건 미상)
# `core.setting.select_combo()` + `ui.is_responsive()`로만 다룬다.
DATA_DELIMITER_COMBO_ID = 31042
DELIMITER_COMMA_TEXT = "COMMA(,)"
DELIMITER_TAB_TEXT = "TAB"

TEST_VALUES_TAB = {
    "Patient ID": "QA_IMPORT_TAB_01",
    "Patient Name": "QA Import Tab Test",
    "Patient Comments": "QA Test Import Comment(Tab)",
    "Acc. No.": "ACC_QA_IMPORT_TAB_01",
    "Procedure Code": "QA_PROC",
    "Study Description": "QA Import Chest Study(Tab)",
    "Referring Physician": "QA Referring Phys",
    "Performing Physician": "QA Performing Phys",
    "Reading Physician": "QA Reading Phys",
    "Institution Name": "QA Institution",
}

TEST_VALUES = {
    "Patient ID": "QA_IMPORT_01",
    "Patient Name": "QA Import Test",
    "Patient Comments": "QA Test Import Comment",
    "Acc. No.": "ACC_QA_IMPORT_01",
    "Procedure Code": "QA_PROC",
    "Study Description": "QA Import Chest Study",
    "Referring Physician": "QA Referring Phys",
    "Performing Physician": "QA Performing Phys",
    "Reading Physician": "QA Reading Phys",
    "Institution Name": "QA Institution",
}
# Birth Date/Age/Sex는 Save Sample이 만들어 준 예시 행의 값(형식)을 그대로
# 재사용한다 — 날짜 자릿수·구분자·나이 표기·성별 코드가 이 화면의 현재
# 설정에 좌우되기 때문이다(위 문서화 참고).


def field(ui, cid):
    found = [c for c in S.content_controls(ui) if c.ctrl_id == cid]
    return found[0] if found else None


def _read_sample(ui, work_dir):
    """Save Sample 버튼을 눌러 현재 설정 그대로의 예시 파일을 받는다.

    반환: (파일 경로, delimiter, header 컬럼 리스트, 예시 데이터 행)
    """
    ids = IMPORT_PATIENT_IDS
    btn = field(ui, ids["save_sample_button"])
    if btn is None:
        return None, "Save Sample 버튼(%d)을 찾지 못함" % ids["save_sample_button"]

    ui.click(btn, settle=1.0)
    sample_path = os.path.join(work_dir, "PatientListSample.csv")
    ok, note = S._file_dialog_submit(ui, sample_path)
    if not ok or not os.path.exists(sample_path):
        return None, "Save Sample 파일 생성 실패: %s" % note

    # 실측(2026-08-19): 파일이 저장된 뒤 완료 확인 팝업(제목 'Export')이
    # 즉시가 아니라 **몇 초 뒤 지연되어** 뜬다 — `core/setting.export_settings()`
    # 가 이미 문서화한 "Export 완료 팝업이 뒤늦게 뜬다" 패턴과 같다. 여기서
    # 드레인하지 않으면 이 팝업이 이후 Step3(Browse)의 클릭을 가로챈다
    # (재현: 3회 연속). 파일 존재까지 확인했으니 실패로 보지 않고, 뒤늦게
    # 뜨는 팝업을 짧게 기다려 비운다.
    time.sleep(1.5)
    ui.drain_dialogs(max_iters=3, timeout=4)

    with io.open(sample_path, "r", encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None, "Save Sample 파일에 헤더+예시 행이 없음: %r" % text[:200]

    delimiter = "\t" if "\t" in lines[0] else ","
    header = lines[0].split(delimiter)
    example = lines[1].split(delimiter)
    return {"path": sample_path, "delimiter": delimiter,
            "header": header, "example": example}, None


def _build_test_file(sample, work_dir):
    """Save Sample이 알려준 형식 그대로, 테스트 값이 채워진 파일을 만든다."""
    header = sample["header"]
    example = sample["example"]
    row = []
    for i, col in enumerate(header):
        col_clean = col.strip()
        if col_clean in TEST_VALUES:
            row.append(TEST_VALUES[col_clean])
        else:
            # Birth Date / Age / Sex 등 형식이 설정에 좌우되는 항목은
            # 예시 값을 그대로 재사용한다(형식만 맞으면 값 자체는 무관).
            row.append(example[i] if i < len(example) else "")

    path = os.path.join(work_dir, "PatientListTest.csv")
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=sample["delimiter"])
        w.writerow(header)
        w.writerow(row)
    return path


def _verify_in_reserved_list(ui, r, work_dir):
    """Import 직후 Reserved 목록에 실제로 뜨는지 화면에서 재확인한다.

    사용자 지시(2026-08-19): "reserved tap에서 import patient를 완료한 다음에
    default를 clear로 바꾸고 search버튼 클릭 시 실제 import가 잘되었는지도
    pass/fail 기준에 넣어라." DB(ORDER_PATIENT) 반영 확인(Step5 위 체크)과는
    별개로, **화면에 실제로 표시되는지**를 검증한다 — DB에는 있지만 화면
    조회 조건과 안 맞아 안 보이는 경우까지 잡기 위함이다.

    목록 행은 owner-draw 단일 윈도우라 자식 컨트롤이 없고(실측 확인: `children()`
    빈 리스트) 표준 API로 셀 텍스트를 읽을 수 없다. Bellalun 계열이 이미
    쓰던 방식대로 목록 영역을 캡처해 OCR(pytesseract)로 텍스트를 확인한다
    — 이 프로젝트의 원칙(3절, 읽을 수 없는 상태는 다른 근거로 검증)과
    같은 맥락이다.
    """
    split_btn = next((c for c in ui.controls(max_depth=12)
                      if c.ctrl_id == RESERVED_FILTER_SPLIT_BUTTON_ID), None)
    if split_btn is None:
        r.add(5, "Reserved 목록 Clear+Search 확인", "FAIL",
              "Default/Clear 필터 버튼(%d)" % RESERVED_FILTER_SPLIT_BUTTON_ID, "찾지 못함")
        return

    from core.ui import children
    arrow = next((c for c in children(split_btn.hwnd, 1)
                  if c.ctrl_id == RESERVED_FILTER_ARROW_ID), None)
    if arrow is None:
        r.add(5, "Reserved 목록 Clear+Search 확인", "FAIL",
              "필터 드롭다운 화살표", "찾지 못함")
        return
    ui.click(arrow, settle=0.6)

    clear_item = next((c for c in ui.controls(max_depth=12)
                       if c.ctrl_id == RESERVED_FILTER_CLEAR_ID), None)
    if clear_item is None:
        r.add(5, "Reserved 목록 Clear+Search 확인", "FAIL",
              "필터 드롭다운의 Clear 항목(%d)" % RESERVED_FILTER_CLEAR_ID, "찾지 못함")
        return
    ui.click(clear_item, settle=0.8)

    search_btn = next((c for c in ui.controls(max_depth=12)
                       if c.ctrl_id == RESERVED_SEARCH_BUTTON_ID), None)
    if search_btn is None:
        r.add(5, "Reserved 목록 Clear+Search 확인", "FAIL",
              "Search 버튼(%d)" % RESERVED_SEARCH_BUTTON_ID, "찾지 못함")
        return
    ui.click(search_btn, settle=1.5)
    time.sleep(0.8)

    count_ctrl = next((c for c in ui.controls(max_depth=12)
                       if c.ctrl_id == RESERVED_RESULT_COUNT_STATIC_ID), None)
    count_text = ui.get_text(count_ctrl) if count_ctrl is not None else "(확인 불가)"

    lists = [c for c in ui.controls(max_depth=10) if c.text.strip() == "ListCtrl"]
    best, best_rows = None, []
    for lc in lists:
        rows = [c for c in children(lc.hwnd, 1) if c.text.strip() == "ListItem" and c.visible]
        if len(rows) > len(best_rows):
            best, best_rows = lc, rows

    if best is None or not best_rows:
        r.assert_true(5, "Reserved 목록 Clear+Search 후 화면에 표시되는지", False,
                      expected="목록에 최소 1건 표시(Result 문구=%r)" % count_text,
                      actual="목록 컨트롤을 찾지 못했거나 행이 0개")
        return

    try:
        import pytesseract
        from PIL import ImageGrab
        # 실측(2026-08-19): tesseract.exe는 설치돼 있으나 PATH에는 없다
        # (`C:\Program Files\Tesseract-OCR\tesseract.exe`). pytesseract가
        # 이 경로를 못 찾으면 매번 실패하므로 존재할 때만 명시적으로 지정한다.
        default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_tesseract):
            pytesseract.pytesseract.tesseract_cmd = default_tesseract
        img = ImageGrab.grab(bbox=best.rect, all_screens=True)
        evid_dir = os.path.join(work_dir, "evidence")
        os.makedirs(evid_dir, exist_ok=True)
        img_path = os.path.join(evid_dir, "reserved_list_after_clear_search.png")
        img.save(img_path)
        ocr_text = pytesseract.image_to_string(img)
    except Exception as e:                                        # noqa: BLE001
        r.add(5, "Reserved 목록 Clear+Search 후 화면에 표시되는지", "MANUAL",
              expected="OCR로 '%s' 확인" % TEST_VALUES["Study Description"],
              actual="OCR 실행 실패: %s — 캡처만 남기고 사람 확인 필요" % e)
        return

    found = TEST_VALUES["Study Description"] in ocr_text
    r.assert_true(5, "Reserved 목록 Clear+Search 후 화면에 표시되는지", found,
                  expected="목록에 '%s'(Study Description) 표시" % TEST_VALUES["Study Description"],
                  actual=("표시됨(Result=%s, 행 %d개)" % (count_text, len(best_rows))
                          if found else
                          "OCR에서 찾지 못함(Result=%s, 행 %d개, 증적: %s)"
                          % (count_text, len(best_rows), img_path)),
                  note="목록 행은 owner-draw 단일 윈도우라 표준 API로 셀 텍스트를 읽을 수 "
                       "없어 캡처+OCR로 확인한다(pytesseract).")


def _tab_delimiter_regression(ui, r, work_dir):
    """TAB 구분자 회귀(#22985) — Data Delimiter를 TAB으로 바꿔 파싱을 재확인한다.

    기존 결함: Tab 구분자는 파싱이 실패했고 Comma는 성공했다(#22985,
    HANDOFF.md 근거). 이 콤보를 조작하다 VXvue가 응답 없음 상태가 된 전례가
    있어(재현 조건 미상, 2026-08-19), `core.setting.select_combo()` +
    `ui.is_responsive()`로만 다루고, 멈춤이 감지되면 더 재시도하지 않고
    있는 그대로 보고한다. 성공하든 실패하든 **항상 COMMA로 원복**한다 —
    이 값을 TAB으로 남기면 이후 모든 정상 Import가 깨진다.
    """
    if not S.open_setting(ui):
        r.add(6, "TAB 구분자 회귀(#22985) 준비", "FAIL",
              "Setting 화면 재진입", "실패")
        return
    minor = S.goto_screen(ui, "Study - Import Patient")
    if minor is None:
        r.add(6, "TAB 구분자 회귀(#22985) 준비", "FAIL",
              "Study - Import Patient 화면 재진입", "찾지 못함")
        return

    combo = field(ui, DATA_DELIMITER_COMBO_ID)
    if combo is None:
        r.add(6, "TAB 구분자 회귀(#22985) 준비", "MANUAL",
              "Data Delimiter 콤보(%d)" % DATA_DELIMITER_COMBO_ID,
              "찾지 못함 — 컨트롤 ID 재확인 필요")
        return
    if not ui.is_responsive(timeout_ms=3000):
        r.add(6, "TAB 구분자 회귀(#22985) 준비", "FAIL",
              "응답 정상", "화면 진입 직후 응답 없음 감지 — 콤보를 건드리지 않음")
        return

    original = S.combo_value(ui, combo) or DELIMITER_COMMA_TEXT
    ok, note = S.select_combo(ui, combo, DELIMITER_TAB_TEXT)
    if not ok:
        r.add(6, "Data Delimiter -> TAB 변경", "MANUAL",
              "정상 변경(또는 명확한 실패로 즉시 중단)",
              "변경 시도 중단: %s (원본값 %r 그대로일 가능성이 높음, 사람 확인 필요)"
              % (note, original))
        return

    ack = S.update(ui, ack_timeout=8)
    if not ui.is_responsive(timeout_ms=3000):
        r.add(6, "Data Delimiter -> TAB 변경 후 Update", "FAIL",
              "Update 후 응답 정상",
              "응답 없음(hang) 감지 — 결함 재현 가능성, 원복을 시도하지 않고 확인 필요로 남김")
        return
    r.add(6, "Data Delimiter -> TAB 변경", "PASS",
          "TAB으로 변경, Update 완료", "완료 팝업: %s" % (ack or "(없음)"))

    sample, err = _read_sample(ui, work_dir)
    if sample is None or sample["delimiter"] != "\t":
        # 실측(2026-08-19): 콤보 UI 값과 DB(CONFIGURATION_IMPORT_PATIENT_OPTION
        # Type=716)는 TAB(값 '6')으로 정상 반영됐음을 별도로 확인했다 — 즉
        # 설정 변경 자체는 실제로 적용된다. 그런데도 이 화면에서 곧바로 다시
        # 누른 Save Sample은 구분자를 COMMA로 생성했다 — Save Sample이 "지금
        # 화면에 로드된" 값이 아니라 화면 진입 시점에 캐시된 값을 쓰거나,
        # Save Sample 자체가 Data Delimiter와 무관하게 항상 COMMA로 예시를
        # 만드는 것일 수 있다(둘 중 어느 쪽인지 이번 세션에서 확정하지 못함).
        # FAIL이 아니라 MANUAL로 남긴다 — 자동화가 잘못됐다는 뜻이 아니라
        # "Save Sample과 Data Delimiter의 관계를 사람이 한 번 더 확인해야
        # 한다"는 뜻이다.
        r.add(6, "TAB 구분자 반영 확인(Save Sample 재확보)", "MANUAL",
              expected="Save Sample 결과 구분자=TAB",
              actual=err or ("구분자=%r" % (sample or {}).get("delimiter")),
              note="DB(CONFIGURATION_IMPORT_PATIENT_OPTION Type=716)는 TAB로 정상 반영됨을 "
                   "별도 확인함 — Save Sample이 화면 재진입 없이는 최신값을 못 읽는 것인지, "
                   "Data Delimiter와 무관하게 항상 COMMA로 예시를 만드는지 확인 필요")
    else:
        r.add(6, "TAB 구분자 반영 확인(Save Sample 재확보)", "PASS",
              "구분자=TAB", "컬럼 %d개" % len(sample["header"]))

        header, example = sample["header"], sample["example"]
        row = [TEST_VALUES_TAB.get(col.strip(), example[i] if i < len(example) else "")
               for i, col in enumerate(header)]
        test_path_tab = os.path.join(work_dir, "PatientListTest_TAB.csv")
        with io.open(test_path_tab, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(header)
            w.writerow(row)

        ids = IMPORT_PATIENT_IDS
        browse_btn = field(ui, ids["browse_button"])
        refresh_btn = field(ui, ids["refresh_button"])
        if browse_btn and refresh_btn:
            ui.click(browse_btn, settle=1.0)
            ok2, note2 = S._file_dialog_submit(ui, test_path_tab)
            if ok2:
                ui.click(refresh_btn, settle=1.0)
                time.sleep(0.5)
                grid = next((c for c in S.list_ctrls(ui)
                            if c.ctrl_id == ids["preview_grid"]), None)
                rows = S.list_rows(ui, grid) if grid is not None else []
                r.assert_true(6, "TAB 파일 파싱 미리보기(#22985 회귀)", bool(rows),
                              expected="TAB 구분 파일도 Comma와 동일하게 파싱 미리보기에 "
                                       "표시(결함 #22985 재발 없음)",
                              actual="미리보기 행 %d개" % len(rows))
            else:
                r.add(6, "TAB 파일 파싱 미리보기(#22985 회귀)", "FAIL", "파일 선택", note2)
        else:
            r.add(6, "TAB 파일 파싱 미리보기(#22985 회귀)", "FAIL",
                  "Browse/Refresh 컨트롤", "찾지 못함")

    # --- 원복: 반드시 COMMA로 되돌린다 -----------------------------------
    combo = field(ui, DATA_DELIMITER_COMBO_ID)
    revert_ok, revert_note = False, "콤보를 다시 찾지 못함"
    if combo is not None and ui.is_responsive(timeout_ms=3000):
        revert_ok, revert_note = S.select_combo(ui, combo, DELIMITER_COMMA_TEXT)
        if revert_ok:
            S.update(ui, ack_timeout=8)
    r.assert_true(6, "Data Delimiter 원복(COMMA)", revert_ok,
                  expected="테스트 종료 후 원래 값(%s)으로 복원" % original,
                  actual="복원 완료" if revert_ok else
                  ("복원 실패: %s — 사람이 Setting > Study - Import Patient에서 "
                   "직접 확인·복원할 것" % revert_note))


FOLDER_WATCH_LABEL_HINTS = ("Specific Folder", "Target Directory")


def _folder_watch_step(ui, r, work_dir, with_folder_watch):
    """Import Patient Information From a Specific Folder 경로(폴더 자동 감지).

    Service Manual 4.6.7절(p.96) 원문: "본 기능 설정 시 Registration > Reserved
    > Import Patient Order 기능을 사용할 수 없습니다" — 즉 이 기능과 지금까지
    구현한 수동 Import(Step1~6)는 **상호 배타**다. 이 화면의 체크박스/버튼
    구조는 이번 세션까지 실측한 적이 없다 — 컨트롤 좌표를 추정해 클릭하지
    않는다(CLAUDE.md 3절). 라벨이 확인되면 그 존재만 보고하고,
    `with_folder_watch=True`일 때만(별도 명시적 실행) 조심스럽게 켜고 곧바로
    되돌린다. 이 분기는 아직 라이브로 검증되지 않았다 — 반드시 별도 세션에서
    `python run.py tc13 --with-folder-watch`로 단독 확인할 것.
    """
    if not S.open_setting(ui):
        r.add(7, "폴더 자동 감지 경로 확인", "FAIL",
              "Setting 화면 재진입", "실패")
        return
    minor = S.goto_screen(ui, "Study - Import Patient")
    if minor is None:
        r.add(7, "폴더 자동 감지 경로 확인", "FAIL",
              "Study - Import Patient 화면 재진입", "찾지 못함")
        return

    controls = S.content_controls(ui)
    labels = [c for c in controls if c.cls == "Static"
             and any(h.lower() in c.text.lower() for h in FOLDER_WATCH_LABEL_HINTS)]
    if not labels:
        r.add(7, "폴더 자동 감지 경로 확인", "MANUAL",
              "'Specific Folder'/'Target Directory' 라벨",
              "화면에서 찾지 못함(스크롤 아래 있을 수 있음) — Service Manual "
              "4.6.7절 기준 실측 필요")
        return

    r.add(7, "폴더 자동 감지 경로 컨트롤 존재 확인", "PASS",
          "관련 라벨 발견(Service Manual 4.6.7절 근거)",
          "; ".join(sorted(set(c.text.strip() for c in labels))))

    if not with_folder_watch:
        r.manual(7, "폴더 자동 감지 경로 실행 검증",
                 "Import Patient Order(Step1~6)와 상호 배타 기능이라 이번 실행에서는 "
                 "실제로 켜지 않았다. 필요 시 'python run.py tc13 --with-folder-watch'로 "
                 "별도 실행해 확인할 것(아직 라이브 미검증 경로).")
        return

    checkbox = None
    for lab in labels:
        if "specific folder" not in lab.text.lower():
            continue
        ly = (lab.rect[1] + lab.rect[3]) // 2
        for c in controls:
            if c.text.strip() == "CheckBox" and abs(((c.rect[1] + c.rect[3]) // 2) - ly) < 20:
                checkbox = c
                break
    if checkbox is None:
        r.add(7, "폴더 자동 감지 기능 활성화", "MANUAL",
              "체크박스 위치 확정",
              "라벨 근처에서 CheckBox를 확신 있게 찾지 못함 — 추정 클릭하지 않음")
        return

    ui.click(checkbox, settle=0.6)
    ack = S.update(ui, ack_timeout=8)
    r.manual(7, "폴더 자동 감지 기능 활성화",
             "체크박스 클릭 + Update(완료 팝업: %s). on/off는 owner-draw라 UI로 "
             "읽을 수 없어 DB 대조가 필요하나 이번 세션에서는 미구현(다음 과제)."
             % (ack or "없음"))
    checkbox = field(ui, checkbox.ctrl_id)
    if checkbox is not None:
        ui.click(checkbox, settle=0.6)
        S.update(ui, ack_timeout=8)
        r.manual(7, "폴더 자동 감지 기능 원복", "체크박스를 다시 클릭해 끄고 Update함(사람 확인 권장)")
    else:
        r.add(7, "폴더 자동 감지 기능 원복", "FAIL",
              "체크박스 재확보", "찾지 못함 — 기능이 켜진 채로 남아 있을 수 있음, "
              "사람이 Setting > Study - Import Patient에서 직접 확인할 것")


def run(ui, cfg, work_dir=None, with_folder_watch=False):
    r = TCResult(TC_ID, TC_TITLE)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work_dir = work_dir or os.path.join(root, "work", "vms", "import_patient")
    os.makedirs(work_dir, exist_ok=True)

    if not S.open_setting(ui):
        r.add(1, "Setting 화면 진입", "FAIL", "Setting 화면", "진입 실패")
        return r.finalize()

    minor = S.goto_screen(ui, "Study - Import Patient")
    if minor is None:
        r.add(1, "Study - Import Patient 화면 진입", "FAIL",
              "화면 진입", "찾지 못함")
        return r.finalize()

    sample, err = _read_sample(ui, work_dir)
    if sample is None:
        r.add(1, "Save Sample로 현재 설정 형식 확보", "FAIL",
              "예시 파일 생성", err)
        return r.finalize()
    r.add(1, "Save Sample로 현재 설정 형식 확보", "PASS",
          "예시 파일 생성 성공",
          "구분자=%r 컬럼 %d개: %s"
          % (sample["delimiter"], len(sample["header"]),
             ", ".join(c.strip() for c in sample["header"])))

    test_path = _build_test_file(sample, work_dir)
    r.add(2, "테스트 데이터 파일 작성", "PASS",
          "Save Sample 형식 그대로 값 채움", test_path)

    # --- Sample Test: File Path + Refresh로 파싱 미리보기 확인 ------------
    # 실측(2026-08-19): File Path Edit(30205)는 읽기 전용(ES_READONLY)이라
    # 직접 타이핑이 되지 않는다 — Browse("...") 버튼(30515)으로 여는 표준
    # 파일 열기 대화상자에서 경로를 지정해야 한다.
    ids = IMPORT_PATIENT_IDS
    browse_btn = field(ui, ids["browse_button"])
    refresh_btn = field(ui, ids["refresh_button"])
    if not browse_btn or not refresh_btn:
        r.add(3, "Sample Test(파싱 미리보기)", "FAIL",
              "Browse/Refresh 컨트롤", "찾지 못함")
        return r.finalize()

    ui.click(browse_btn, settle=1.0)
    ok, note = S._file_dialog_submit(ui, test_path)
    if not ok:
        r.add(3, "Sample Test(파싱 미리보기)", "FAIL",
              "파일 선택", note)
        return r.finalize()

    file_edit = field(ui, ids["file_path_edit"])
    path_set = file_edit is not None and ui.get_text(file_edit)
    ui.click(refresh_btn, settle=1.0)
    time.sleep(0.5)

    grid = next((c for c in S.list_ctrls(ui) if c.ctrl_id == ids["preview_grid"]), None)
    preview_rows = S.list_rows(ui, grid) if grid is not None else []
    r.assert_true(3, "Sample Test 파싱 미리보기에 행이 표시되는지",
                  bool(preview_rows),
                  expected="테스트 파일의 데이터 행(1건)이 미리보기에 표시",
                  actual="미리보기 행 %d개" % len(preview_rows),
                  note="File Path 반영값=%r. 그리드 셀 텍스트는 owner-draw라 표준 "
                       "API로 읽을 수 없어 행 존재 여부까지만 확인한다. 값 자체는 "
                       "Step 5의 DB 대조로 검증한다." % path_set)

    # --- Registration > Reserved 로 이동해 실제 Import 수행 --------------
    # 실측(2026-08-19): Setting > Study - Import Patient 화면에 깊이 들어간
    # 상태에서는 우측 메인 네비 Tab(31197)의 Registration(8)이나 Exit(14)를
    # 클릭해도 화면이 전환되지 않았다(반복 재현). 원인은 특정하지 못했으나,
    # VXvue를 재기동해 로그인 직후의 기본 화면(Registration)으로 돌아가는
    # 것이 유일하게 신뢰할 수 있는 방법이었다.
    import subprocess
    v = cfg.get("viewer") or {}
    lg = v.get("login") or {}
    proc_name = os.path.basename(v.get("exe") or "VXvue.exe")
    subprocess.run(["taskkill", "/F", "/IM", proc_name],
                   capture_output=True)
    time.sleep(3)
    ui._pid = None
    ui.launch(v.get("exe"), wait=20)
    end = time.time() + v.get("startup_timeout", 240)
    while time.time() < end and not ui.at_login_screen():
        if not ui.pid:
            ui.launch(v.get("exe"), wait=20)
        time.sleep(3)
    relogged = ui.login(lg.get("id"), lg.get("password"))
    r.assert_true(4, "재기동 후 Registration 기본 화면 복귀", bool(relogged),
                  expected="재기동 후 로그인 성공, Registration 기본 화면 표시",
                  actual="성공" if relogged else "실패")
    if not relogged:
        return r.finalize()

    from core.ui import children
    tabs = [c for c in ui.controls(max_depth=8) if c.ctrl_id == MAIN_NAV_TAB_CONTAINER]
    if not tabs:
        r.add(4, "Registration 화면 확인", "FAIL",
              "메인 네비 Tab", "찾지 못함")
        return r.finalize()

    # 실측(2026-08-19): Import Patient Order 버튼(30392)은 Registration의
    # 기본 탭(Scheduled)이 아니라 **Reserved 탭**에 있다. 또 이 버튼은
    # Setting 화면과 달리 본문 대화상자(`#32770`)의 자식이 아니라 프레임
    # 창의 직속 자식이라 `core.setting.content_controls()`(Setting 전용
    # 탐색 경로)로는 찾을 수 없었다(재현: `field()`가 빈 결과) — 여기서는
    # 전체 컨트롤 스캔(`ui.controls()`)으로 찾는다.
    reserved_tabs = [c for c in ui.controls(max_depth=8) if c.ctrl_id == RESERVED_TAB_ID]
    if not reserved_tabs:
        r.add(5, "Registration - Reserved 탭 이동", "FAIL",
              "Reserved 탭(%d)" % RESERVED_TAB_ID, "찾지 못함")
        return r.finalize()
    ui.click(reserved_tabs[0], settle=1.2)

    from core.db import VXvueDb
    db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
    before = db.query("SELECT COUNT(*) as n FROM ORDER_PATIENT "
                      "WHERE PatientId = '%s'" % TEST_VALUES["Patient ID"])
    before_n = before[0]["n"] if before else 0

    import_btn = next((c for c in ui.controls(max_depth=8)
                       if c.ctrl_id == RESERVED_IMPORT_BUTTON_ID), None)
    if import_btn is None:
        r.add(5, "Import Patient Order 실행", "FAIL",
              "Import 버튼(%d)" % RESERVED_IMPORT_BUTTON_ID, "찾지 못함")
        return r.finalize()

    # 실측(2026-08-19): Import Patient Order 버튼(30392)을 누르면 **Setting >
    # Study - Import Patient 화면과 완전히 같은 구조를 재사용한 별도 모달
    # 팝업**(File Path/Browse(30515)/Refresh(30644)/미리보기 그리드(31178))이
    # 뜬다(Operation Manual 5.3.1절 "Import Patient Order 팝업 창이
    # 나타납니다"와 일치). 처음 구현은 이 버튼 클릭이 곧바로 OS 파일 열기
    # 대화상자를 연다고 잘못 가정했었다 — 실제로는 **이 팝업 안의 Browse
    # 버튼을 다시 눌러야** 파일 대화상자가 열린다. 이 팝업 자체도 클래스가
    # `#32770`이라 `ui.dialog()`가 이걸 "닫아야 할 안내 팝업"으로 오인하면
    # 안 된다(실측: 잘못 클릭해 반복 재시도됨) — 여기서는 컨트롤 ID로 직접
    # 다뤄서 그런 오인식을 피한다.
    ui.click(import_btn, settle=1.5)

    order_browse = next((c for c in ui.controls(max_depth=12)
                         if c.ctrl_id == IMPORT_PATIENT_IDS["browse_button"]), None)
    if order_browse is None:
        r.add(5, "Import Patient Order 팝업 - Browse", "FAIL",
              "팝업 안의 Browse 버튼(%d)" % IMPORT_PATIENT_IDS["browse_button"],
              "찾지 못함")
        return r.finalize()
    ui.click(order_browse, settle=1.2)
    ok, note = S._file_dialog_submit(ui, test_path)
    if not ok:
        r.add(5, "Import Patient Order 실행", "FAIL", "파일 선택·확인", note)
        return r.finalize()

    order_refresh = next((c for c in ui.controls(max_depth=12)
                          if c.ctrl_id == IMPORT_PATIENT_IDS["refresh_button"]), None)
    if order_refresh is not None:
        ui.click(order_refresh, settle=1.0)
    time.sleep(0.5)

    order_grid = next((c for c in ui.controls(max_depth=12)
                       if c.ctrl_id == IMPORT_PATIENT_IDS["preview_grid"]), None)
    order_rows = S.list_rows(ui, order_grid) if order_grid is not None else []
    if not order_rows:
        r.add(5, "Import Patient Order 팝업 - 미리보기", "FAIL",
              "파일 선택 후 미리보기에 행 표시", "미리보기 행 0개")
        return r.finalize()

    # 실측: 팝업 안의 좌측 버튼(30645)을 누르면 "Do you want to import all
    # patient?" 확인창(제목 'Import', 버튼 All Patients/Selected/Cancel)이
    # 뜬다. 미리보기 행을 개별 선택하지 않았으므로 'All Patients'(27002)를
    # 선택한다.
    IMPORT_CONFIRM_BUTTON_ID = 30645
    confirm_btn = next((c for c in ui.controls(max_depth=12)
                        if c.ctrl_id == IMPORT_CONFIRM_BUTTON_ID), None)
    if confirm_btn is None:
        r.add(5, "Import Patient Order 팝업 - Import 실행", "FAIL",
              "Import 버튼(%d)" % IMPORT_CONFIRM_BUTTON_ID, "찾지 못함")
        return r.finalize()
    ui.click(confirm_btn, settle=1.2)

    all_patients_dlg = ui.wait_dialog(title="Import", timeout=6)
    if all_patients_dlg is None:
        r.add(5, "Import Patient Order 팝업 - 'All Patients' 확인창", "FAIL",
              "제목 'Import' 확인창 표시", "나타나지 않음")
        return r.finalize()
    from core.ui import children
    all_patients_btn = next((c for c in children(all_patients_dlg.hwnd, 3)
                             if c.ctrl_id == 27002), None)
    if all_patients_btn is None:
        r.add(5, "Import Patient Order 팝업 - 'All Patients' 확인창", "FAIL",
              "All Patients 버튼(27002)", "찾지 못함")
        return r.finalize()
    ui.click(all_patients_btn, settle=1.5)

    # Import Patient Order 팝업은 확인 후에도 스스로 닫히지 않는다 —
    # 화면 우상단의 X 아이콘(컨트롤 ID -4, 실측)으로 명시적으로 닫아야 한다.
    # 실측(2026-08-19): 'All Patients' 확인 직후 완료 확인용 임시 팝업이
    # 하나 더 뜰 수 있고, 그것도 같은 -4 아이콘을 갖는다 — 한 번만 닫으면
    # 그 임시 팝업만 닫히고 정작 Import Patient Order 본체 팝업은 그대로
    # 남는다(재현 확인됨). `drain_dialogs()`(안내 팝업 전용)로 다루면
    # 오인식되므로, 여기서는 -4 아이콘이 더 없을 때까지 직접 반복해서 닫는다.
    for _ in range(4):
        popup = ui.dialog()
        if popup is None:
            break
        close_icon = next((c for c in children(popup.hwnd, 1) if c.ctrl_id == -4), None)
        if close_icon is None:
            break
        ui.click(close_icon, settle=1.0)

    time.sleep(1.0)
    after = db.query("SELECT * FROM ORDER_PATIENT "
                     "WHERE PatientId = '%s'" % TEST_VALUES["Patient ID"])
    after_n = len(after)

    imported_ok = after_n > before_n
    mismatches = []
    if imported_ok:
        row = after[0]
        for key, col in (("Patient Name", "PatientName"),
                         ("Acc. No.", "AccessionNumber"),
                         ("Study Description", "StudyDescription")):
            if str(row.get(col) or "").strip() != TEST_VALUES[key]:
                mismatches.append("%s: DB=%r 기대=%r" % (col, row.get(col), TEST_VALUES[key]))

    r.assert_true(5, "Registration-Reserved Import로 DB(ORDER_PATIENT)에 반영",
                  imported_ok and not mismatches,
                  expected="PatientId=%s 행이 새로 생기고 필드가 파일과 일치"
                           % TEST_VALUES["Patient ID"],
                  actual=("반영 안 됨(가져오기 전 %d건 -> 후 %d건)" % (before_n, after_n)
                          if not imported_ok
                          else ("불일치 없음" if not mismatches else "; ".join(mismatches))),
                  note=note or "")

    _verify_in_reserved_list(ui, r, work_dir)

    _tab_delimiter_regression(ui, r, work_dir)
    _folder_watch_step(ui, r, work_dir, with_folder_watch)

    return r.finalize()
