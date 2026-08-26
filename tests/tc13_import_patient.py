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

from core import media
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
# Column Mapping 영역(실측 2026-08-21). Service Manual 4.6.7절 "입력 데이터의
# 형태와 동일하게 Column mapping 항목을 선택하고, Move Down/Move Up 버튼으로
# 순서를 정렬하십시오" — 이 리스트가 그 항목이다. 각 행은 owner-draw라
# 라벨은 OCR로, 체크 상태는 `core.setting.checkbox_checked()`로 읽는다.
# 사양서4(260820) p.60 VP-688 Column Mapping 표: Patient ID/Patient Name만
# "필수(체크 해제 불가)" — 나머지는 전부 선택 해제 가능하다.
COLUMN_MAPPING_LIST_ID = 31114
COLUMN_MAPPING_MOVE_UP_ID = 30554
COLUMN_MAPPING_MOVE_DOWN_ID = 30555
COLUMN_MAPPING_ADD_BLANK_ID = 30627
COLUMN_MAPPING_DELETE_BLANK_ID = 30628
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


def _read_sample(ui, work_dir, sample_name="PatientListSample.csv",
                 file_type_contains=None):
    """Save Sample 버튼을 눌러 현재 설정 그대로의 예시 파일을 받는다.

    `file_type_contains`를 주면 Save-As 대화상자의 '파일 형식' 콤보에서 그
    문구를 포함하는 항목을 명시적으로 선택한다 — 사양서4 p.60 VP-688 근거:
    이 파일의 구분자는 화면의 Data Delimiter 콤보가 아니라 **이 선택**으로
    결정된다(`core.setting.select_file_type`).

    반환: (파일 경로, delimiter, header 컬럼 리스트, 예시 데이터 행)
    """
    ids = IMPORT_PATIENT_IDS
    btn = field(ui, ids["save_sample_button"])
    if btn is None:
        return None, "Save Sample 버튼(%d)을 찾지 못함" % ids["save_sample_button"]

    ui.click(btn, settle=1.0)
    sample_path = os.path.join(work_dir, sample_name)
    ok, note = S._file_dialog_submit(ui, sample_path, file_type_contains=file_type_contains)
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
                          "OCR에서 찾지 못함(Result=%s, 행 %d개, 증거: %s)"
                          % (count_text, len(best_rows), img_path)),
                  note="목록 행은 owner-draw 단일 윈도우라 표준 API로 셀 텍스트를 읽을 수 "
                       "없어 캡처+OCR로 확인한다(pytesseract).")


def _set_delimiter(ui, target_text, jiggle=False):
    """Data Delimiter 콤보를 target_text로 맞추고 Update한다.

    `jiggle=True`면 결함 #22985 티켓에 적힌 우회 순서를 재현한다: "현
    상태에서 변경없이 Update활성화를 위해 다른 값 선택후 다시 기존값으로
    돌아온뒤 Update시 Expected Result결과대로 동작함" — 목표값으로 바로
    가지 않고 **반대값을 한 번 거쳤다가** 목표값으로 온 뒤에 Update한다.
    `jiggle=False`는 목표값으로 한 번에 바꾸는 "직접" 경로다(티켓의 결함
    재현 시나리오와 같은 조작).

    반환: (성공 여부, note, 최종 콤보 값)
    """
    combo = field(ui, DATA_DELIMITER_COMBO_ID)
    if combo is None:
        return False, "Data Delimiter 콤보(%d)를 찾지 못함" % DATA_DELIMITER_COMBO_ID, None
    if not ui.is_responsive(timeout_ms=3000):
        return False, "화면 응답 없음 — 콤보를 건드리지 않음", None

    if jiggle:
        other = DELIMITER_COMMA_TEXT if target_text == DELIMITER_TAB_TEXT else DELIMITER_TAB_TEXT
        ok, note = S.select_combo(ui, combo, other)
        if not ok:
            return False, "우회 1단계(%s로 임시 전환) 실패: %s" % (other, note), None
        combo = field(ui, DATA_DELIMITER_COMBO_ID)
        if combo is None or not ui.is_responsive(timeout_ms=3000):
            return False, "우회 1단계 후 화면/응답 이상", None

    ok, note = S.select_combo(ui, combo, target_text)
    if not ok:
        return False, "%s로 전환 실패: %s" % (target_text, note), None
    if not ui.is_responsive(timeout_ms=3000):
        return False, "전환 후 응답 없음(hang) 감지", None
    ack = S.update(ui, ack_timeout=8)
    if not ui.is_responsive(timeout_ms=3000):
        return False, "Update 후 응답 없음(hang) 감지", None
    combo2 = field(ui, DATA_DELIMITER_COMBO_ID)
    now = S.combo_value(ui, combo2) if combo2 is not None else None
    ok = (now == target_text)
    return ok, "Update 완료(팝업: %s), 콤보 값=%r" % (ack or "없음", now), now


def _try_import_preview(ui, path, label):
    """Import Patient 화면에서 파일을 선택 후 Refresh해 미리보기 행 개수를 본다.

    반환: (행이 1개 이상 있는지, 행 개수, note).
    """
    ids = IMPORT_PATIENT_IDS
    browse_btn = field(ui, ids["browse_button"])
    refresh_btn = field(ui, ids["refresh_button"])
    if browse_btn is None or refresh_btn is None:
        return False, 0, "Browse/Refresh 컨트롤을 찾지 못함"
    ui.click(browse_btn, settle=1.0)
    ok, note = S._file_dialog_submit(ui, path)
    if not ok:
        return False, 0, "파일 선택 실패(%s): %s" % (label, note)
    ui.click(refresh_btn, settle=1.0)
    time.sleep(0.5)
    grid = next((c for c in S.list_ctrls(ui) if c.ctrl_id == ids["preview_grid"]), None)
    rows = S.list_rows(ui, grid) if grid is not None else []
    return bool(rows), len(rows), ""


def _tab_delimiter_regression(ui, r, work_dir):
    """TAB 구분자 회귀 — 기존 결함 #22985 확인 대상.

    ## 결함 #22985 (내부 QA 결함 추적, 사용자 제공 캡처로 확인, 2026-08-25)

    제목: "Setting Import 후 import patient시 Tab구분자임에도 Comma시 성공하고
    Tab시 실패함." 상태=보류 / Grade D / 발생 버전 1.0.11.014 / 연구소도 이
    이슈를 인지하고 있다(등록·추적 중, 연구소 자체 재현 테스트는 아직 안 됨).

    Expected(사양대로): Data Delimiter=TAB이면 TAB 파일 Import는 성공하고
    COMMA 파일 Import는 실패해야 한다.
    Actual(결함 티켓 원문): 정반대다 — TAB 파일 Import가 실패하고 COMMA
    파일 Import가 성공한다.

    티켓에 적힌 우회: "현 상태에서 변경없이 Update활성화를 위해 다른 값
    선택후 다시 기존값으로 돌아온뒤 Update시 Expected Result결과대로 동작함
    - 내부적으로 설정값이 꼬인것 같기도함." 즉 Comma→Tab으로 **한 번에**
    바꾸면 결함이 재현되고, 반대값을 한 번 거쳤다가 목표값으로 오면(아래
    `_set_delimiter(jiggle=True)`) 정상 동작한다고 보고돼 있다 — 이 함수는
    두 경로를 전부 실행해 실제로 그렇게 갈리는지 확인한다.

    ## Save Sample과는 별개다 (사양서4 260824 VP-688, p.60)

    "예시의 내용은 Input Format의 값을 바탕으로 생성되며, Data Delimiter는
    클릭 후 나오는 다른 이름으로 저장하기 창에서 선택된 파일 형식에 따라
    바뀐다." — Save Sample이 만드는 **파일의 구분자**는 화면의 Data
    Delimiter 콤보가 아니라 Save-As 대화상자의 파일 형식 선택으로 정해진다.
    반면 **Import 시 그 파일을 인식하는 것**은 Data Delimiter(Input Format)
    콤보가 결정한다("Setting에서 저장된 Data 형태와 Import 하기 위해 선택한
    파일의 Data 형태가 일치하면 로드 가능" — 사양서 원문). 이 둘은 서로 다른
    컨트롤이 서로 다른 것을 결정한다. 이전 세션은 Save-As 대화상자의 파일
    형식 선택 자동화(세 가지 방법)에 실패해서 그 뒤에 있는 **진짜 확인
    대상**(Data Delimiter 설정에 따른 Import 성공/실패)까지 통째로 건너뛰고
    있었다 — 이 버전은 Save-As 자동화에 더 이상 의존하지 않는다. 이미 확보한
    COMMA 샘플의 헤더를 그대로 써서 TAB 파일을 파이썬 `csv` 모듈로 직접
    만든다(Save Sample 없이도 파일의 델리미터만 바꾸면 되므로 충분하다).

    콤보 조작 중 VXvue가 응답 없음 상태가 된 전례가 있어(재현 조건 미상,
    2026-08-19) 매 전환마다 `ui.is_responsive()`로 확인하고, 멈춤이 감지되면
    더 재시도하지 않는다. 성공하든 실패하든 **항상 COMMA로 원복**한다 — 이
    값을 TAB으로 남기면 이후 모든 정상 Import가 깨진다.
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

    # COMMA 샘플로 헤더를 확보한다(Save-As 자동화 없이 기본 저장 그대로 —
    # 이미 이 TC의 메인 흐름에서 안정적으로 동작하는 경로다).
    sample, err = _read_sample(ui, work_dir, sample_name="PatientListSample_ForTab.csv")
    if sample is None:
        r.add(6, "TAB 구분자 회귀(#22985) 준비", "MANUAL",
              "Save Sample로 컬럼 헤더 확보", err)
        return
    header, example = sample["header"], sample["example"]
    comma_file = sample["path"]

    def _make_tab_file(name, values):
        path = os.path.join(work_dir, name)
        row = [values.get(col.strip(), example[i] if i < len(example) else "")
               for i, col in enumerate(header)]
        with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(header)
            w.writerow(row)
        return path

    tab_file = _make_tab_file("PatientListTest_TAB.txt", TEST_VALUES_TAB)

    KNOWN_DEFECT_NOTE = (
        "결함(QA) #22985 \"Setting Import 후 import patient시 Tab구분자임에도 "
        "Comma시 성공하고 Tab시 실패함.\" (상태=보류, Grade D, 발생 버전 "
        "1.0.11.014, 연구소 인지·추적 중) — 이 결과와 일치한다. 새로 발견한 "
        "결함이 아니라 이미 등록된 이슈이므로 중복 등록하지 말 것.")

    def _run_scenario(label, jiggle, expect_note):
        set_ok, set_note, now = _set_delimiter(ui, DELIMITER_TAB_TEXT, jiggle=jiggle)
        r.add(6, "Data Delimiter -> TAB 전환(%s)" % label,
              "PASS" if set_ok else "FAIL",
              expected="TAB으로 전환 + Update, 콤보 값이 TAB으로 확정",
              actual=set_note)
        if not set_ok:
            return None
        tab_ok, tab_n, tab_note = _try_import_preview(ui, tab_file, "TAB(%s)" % label)
        comma_ok, comma_n, comma_note = _try_import_preview(ui, comma_file, "COMMA(%s)" % label)
        spec_match = tab_ok and not comma_ok
        defect_match = (not tab_ok) and comma_ok
        # TAB/COMMA 결과가 자동으로 측정됐으므로 사양과 다르면 사람이 다시
        # 판단할 문제가 아니라 제품 이슈다(사용자 지시, 2026-08-26).
        verdict = "PASS" if spec_match else "FAIL"
        r.add(6, "TAB 설정 상태에서 Import 결과(%s)" % label, verdict,
              expected="TAB 파일 Import 성공(행 1개 이상) + COMMA 파일(불일치) Import 실패",
              actual="TAB 파일: %s(행 %d) / COMMA 파일: %s(행 %d)%s%s"
                     % ("성공" if tab_ok else "실패", tab_n,
                        "성공" if comma_ok else "실패", comma_n,
                        (" / %s" % tab_note) if tab_note else "",
                        (" / %s" % comma_note) if comma_note else ""),
              note=(expect_note + (" " + KNOWN_DEFECT_NOTE if defect_match else
                     (" 사양대로 정상 동작." if spec_match else
                      " 알려진 #22985 패턴과 형태가 다르더라도 사양 불일치가 "
                      "자동 확인됐으므로 제품 이슈로 FAIL 처리한다."))))
        return spec_match, defect_match

    # 시나리오 A: 직접 전환(결함 티켓의 재현 경로) — Comma에서 Tab으로 한
    # 번에 바꾼다.
    _run_scenario("직접 전환, 결함 재현 시도",
                  jiggle=False,
                  expect_note="결함 #22985의 재현 시나리오(직접 전환)와 같은 조작이다.")

    # 되돌렸다가(원복 확인 없이 바로 다음 시나리오로 넘어가면 상태가 섞인다)
    revert_ok, revert_note, _ = _set_delimiter(ui, DELIMITER_COMMA_TEXT, jiggle=False)
    if not revert_ok:
        r.add(6, "시나리오 전환 전 COMMA 원복", "FAIL",
              "다음 시나리오 전 COMMA로 복원", revert_note)
        r.add(6, "Data Delimiter 최종 원복(COMMA)", "FAIL",
              expected="테스트 종료 후 원래 값(%s)으로 복원" % original,
              actual="중간 복원 실패로 원복 시도를 건너뜀 — 사람이 Setting > "
                     "Study - Import Patient에서 직접 확인할 것")
        return

    # 시나리오 B: 티켓에 적힌 우회(다른 값을 한 번 거쳤다가 목표값으로 옴).
    _run_scenario("우회 경로(티켓 워크어라운드)",
                  jiggle=True,
                  expect_note="결함 #22985 티켓에 적힌 우회(반대값을 한 번 거쳤다가 목표값으로 "
                              "옴)와 같은 조작이다 — 티켓은 이 경로에서는 정상 동작한다고 "
                              "적어 두었다.")

    # --- 원복: 반드시 COMMA로 되돌린다 -----------------------------------
    revert_ok, revert_note, _ = _set_delimiter(ui, DELIMITER_COMMA_TEXT, jiggle=False)
    r.assert_true(6, "Data Delimiter 최종 원복(COMMA)", revert_ok,
                  expected="테스트 종료 후 원래 값(%s)으로 복원" % original,
                  actual="복원 완료" if revert_ok else
                  ("복원 실패: %s — 사람이 Setting > Study - Import Patient에서 "
                   "직접 확인·복원할 것" % revert_note))


FOLDER_WATCH_LABEL_HINTS = ("Specific Folder", "Target Directory")

# 실측(2026-08-21): "Use Import Patient Information From a Specific Folder"는
# 체크박스가 아니라 **Yes/No 라디오**다(이전 세션에 라벨 근처 CheckBox를 찾다
# 실패해 MANUAL로 남겼던 원인). Target Directory는 표시 전용 Edit이라 표준
# '폴더 찾아보기' 트리(`core.setting.browse_to_folder`)로만 정할 수 있다.
FOLDER_WATCH_YES_ID = 31366
FOLDER_WATCH_NO_ID = 31367
TARGET_DIRECTORY_EDIT_ID = 30082
TARGET_DIRECTORY_BROWSE_ID = 30653

# 실측(2026-08-21): 이 기능을 Yes로 켜면 Registration > Reserved의 수동
# Import 버튼(RESERVED_IMPORT_BUTTON_ID=30392)이 사라지고, 그 자리에
# **Auto Patient Import 버튼**과 **Patient Import Status**(성공/실패/전체
# 건수 문구)가 나타난다 — 사양서1(260820) p.87~88 VP-474와 정확히 일치.
RESERVED_AUTO_IMPORT_BUTTON_ID = 30671
RESERVED_PATIENT_IMPORT_STATUS_ID = 30021


def _goto_registration_reserved(ui):
    """메인 네비 Registration -> Reserved 탭. 성공하면 True."""
    from core.ui import children
    tabs = [c for c in ui.controls(max_depth=8) if c.ctrl_id == MAIN_NAV_TAB_CONTAINER]
    if not tabs:
        return False, "메인 네비 Tab을 찾지 못함"
    nav_items = [c for c in children(tabs[0].hwnd, 2) if c.text.strip() == "TabItem"]
    reg_tab = next((c for c in nav_items if c.ctrl_id == MAIN_NAV_REGISTRATION), None)
    if reg_tab is None:
        return False, "Registration TabItem을 찾지 못함"
    ui.click(reg_tab, settle=1.2)
    reserved_tabs = [c for c in ui.controls(max_depth=8) if c.ctrl_id == RESERVED_TAB_ID]
    if not reserved_tabs:
        return False, "Reserved 탭을 찾지 못함"
    ui.click(reserved_tabs[0], settle=1.2)
    time.sleep(0.4)
    return True, ""


def _folder_watch_step(ui, r, cfg, work_dir, with_folder_watch=True):
    """Import Patient Information From a Specific Folder 경로(폴더 자동 감지).

    사양서1(260820) p.87~88 VP-474 근거(2026-08-21 문서 조사 + 실측으로 확정,
    Service Manual 4.6.7절 "본 기능 설정 시 Registration > Reserved > Import
    Patient Order 기능을 사용할 수 없습니다"와 일치): Yes로 켜면 수동 Import
    버튼이 사라지고 Auto Patient Import 버튼 + Patient Import Status가
    나타난다. Target Directory에 파일을 넣고 **Search를 누르면 그 순간 1회
    스캔해 반영한다**(Manual mode, VP-474) — 처리된 파일은 그 폴더 아래
    `end/`(성공)로 옮겨진다(사양서에는 없는 동작, 실측으로 확인).

    `with_folder_watch=False`를 주면(디버깅용) 라디오 존재만 확인하고 실제
    조작은 하지 않는다. 실패하더라도 반드시 Yes -> No 원복을 시도한다
    (`finally`) — 이 기능을 켠 채로 남기면 이후의 모든 Import Patient Order
    기반 회귀(Step 1~6)가 깨진다.
    """
    if not S.open_setting(ui):
        r.add(7, "폴더 자동 감지 경로 확인", "FAIL",
              "Setting 화면 재진입", "실패")
        return
    if S.goto_screen(ui, "Study - Import Patient") is None:
        r.add(7, "폴더 자동 감지 경로 확인", "FAIL",
              "Study - Import Patient 화면 재진입", "찾지 못함")
        return

    yes_radio = field(ui, FOLDER_WATCH_YES_ID)
    no_radio = field(ui, FOLDER_WATCH_NO_ID)
    if yes_radio is None or no_radio is None:
        r.add(7, "폴더 자동 감지 Yes/No 라디오 확인", "MANUAL",
              expected="Yes(%d)/No(%d) 라디오 존재(사양서1 p.87 VP-474)"
                       % (FOLDER_WATCH_YES_ID, FOLDER_WATCH_NO_ID),
              actual="찾지 못함 — 화면 구조가 실측과 달라졌을 수 있음")
        return

    was_yes = S.checkbox_checked(ui, yes_radio)
    r.add(7, "폴더 자동 감지 Yes/No 라디오 확인", "PASS",
          expected="Yes/No 라디오 존재(사양서1 p.87 VP-474)",
          actual="현재 선택=%s" % ("Yes" if was_yes else "No"))

    if not with_folder_watch:
        r.manual(7, "폴더 자동 감지 경로 실행 검증",
                 "--skip-folder-watch로 이번 실행에서는 실제 조작을 건너뛴다.")
        return

    def _revert(note_prefix=""):
        no2 = field(ui, FOLDER_WATCH_NO_ID)
        if no2 is None:
            if not S.open_setting(ui) or S.goto_screen(ui, "Study - Import Patient") is None:
                r.add(7, "%s폴더 자동 감지 원복(No)" % note_prefix, "FAIL",
                      "No 라디오 재확보", "Setting 화면 재진입 실패 — 사람이 직접 확인할 것")
                return
            no2 = field(ui, FOLDER_WATCH_NO_ID)
        if no2 is None:
            r.add(7, "%s폴더 자동 감지 원복(No)" % note_prefix, "FAIL",
                  "No 라디오 재확보", "찾지 못함 — 사람이 Setting > Study - Import Patient에서 "
                                  "직접 No로 되돌릴 것")
            return
        ui.click(no2, settle=0.8)
        ack = S.update(ui, ack_timeout=8)
        no3 = field(ui, FOLDER_WATCH_NO_ID)
        ok = no3 is not None and S.checkbox_checked(ui, no3)
        r.assert_true(7, "%s폴더 자동 감지 원복(No)" % note_prefix, ok,
                      expected="No로 복원", actual="복원 확인" if ok else "복원 실패(Update 팝업: %s)" % (ack or "없음"))

    try:
        if was_yes:
            r.add(8, "폴더 자동 감지 활성화(Yes)", "PASS", "이미 Yes였음(건드리지 않음)", "")
        else:
            ui.click(yes_radio, settle=0.8)
            yes2 = field(ui, FOLDER_WATCH_YES_ID)
            yes_ok = yes2 is not None and S.checkbox_checked(ui, yes2)
            r.assert_true(8, "폴더 자동 감지 활성화(Yes 클릭)", yes_ok,
                          expected="Yes 선택 반영", actual="반영 확인" if yes_ok else "반영 실패")
            if not yes_ok:
                return

        configured = (cfg.get("export") or {}).get("dest_dir", "E:\\")
        media_dest, media_note = media.resolve_destination(configured)
        if not media_dest:
            r.add(8, "Folder Watch 대상 USB 확인", "MANUAL",
                  "연결된 이동식 드라이브 1개", media_note)
            return
        drive = os.path.splitdrive(media_dest)[0]
        target_dir = os.path.join(drive + os.sep, "VXvue_QA_ImportWatch")
        os.makedirs(target_dir, exist_ok=True)

        browse_btn = field(ui, TARGET_DIRECTORY_BROWSE_ID)
        target_edit = field(ui, TARGET_DIRECTORY_EDIT_ID)
        current_target = ui.get_text(target_edit) if target_edit is not None else ""
        same = (os.path.normcase(os.path.normpath(current_target or "."))
                == os.path.normcase(os.path.normpath(target_dir)))
        if not same:
            if browse_btn is None:
                r.add(8, "Target Directory 설정", "FAIL",
                      "Browse 버튼(%d)" % TARGET_DIRECTORY_BROWSE_ID, "찾지 못함")
                return
            ui.click(browse_btn, settle=1.2)
            res = S.browse_to_folder(ui, target_dir)
            if not res["ok"]:
                r.add(8, "Target Directory 설정", "FAIL",
                      "폴더 선택 성공(%s)" % target_dir, res["note"])
                return
        target_edit2 = field(ui, TARGET_DIRECTORY_EDIT_ID)
        now_target = ui.get_text(target_edit2) if target_edit2 is not None else ""
        target_ok = (os.path.normcase(os.path.normpath(now_target or "."))
                    == os.path.normcase(os.path.normpath(target_dir)))
        r.assert_true(8, "Target Directory 설정", target_ok,
                      expected=target_dir, actual=now_target)
        if not target_ok:
            return

        ack = S.update(ui, ack_timeout=8)
        r.add(8, "폴더 자동 감지 Update 적용", "PASS",
              expected="Update 성공 팝업 또는 오류 없이 설정 저장 완료",
              actual="완료 팝업: %s" % (ack or "없음(오류 없이 창 닫힘)"))

        # Setting 화면에 아직 있는 동안 이번 실행 전용 예시 파일을 만든다.
        sample, err = _read_sample(ui, work_dir, sample_name="FolderWatchSample.csv")
        if sample is None:
            r.add(8, "폴더 자동 감지용 예시 형식 확보", "FAIL", "Save Sample", err)
            return
        stamp = str(int(time.time()))
        watch_patient_id = "QA_FOLDERWATCH_" + stamp
        header, example = sample["header"], sample["example"]
        values = dict(TEST_VALUES)
        values["Patient ID"] = watch_patient_id
        values["Patient Name"] = "QA FolderWatch Test"
        values["Acc. No."] = "ACC_" + watch_patient_id
        values["Study Description"] = "QA FolderWatch Study " + stamp
        row = [values.get(col.strip(), example[i] if i < len(example) else "")
               for i, col in enumerate(header)]
        watch_file = os.path.join(target_dir, "watch_%s.csv" % stamp)
        with io.open(watch_file, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=sample["delimiter"])
            w.writerow(header)
            w.writerow(row)

        nav_ok, nav_note = _goto_registration_reserved(ui)
        if not nav_ok:
            r.add(9, "Registration - Reserved 이동", "FAIL", "탭 이동", nav_note)
            return

        import_order_present = bool([c for c in ui.controls(max_depth=8)
                                     if c.ctrl_id == RESERVED_IMPORT_BUTTON_ID])
        auto_btn_hits = [c for c in ui.controls(max_depth=8)
                         if c.ctrl_id == RESERVED_AUTO_IMPORT_BUTTON_ID]
        r.assert_true(9, "Reserved 버튼 교체(수동 Import 숨김 + Auto Patient Import 노출)",
                      (not import_order_present) and bool(auto_btn_hits),
                      expected="Import Patient Order(%d) 숨김 + Auto Patient Import(%d) 노출"
                               % (RESERVED_IMPORT_BUTTON_ID, RESERVED_AUTO_IMPORT_BUTTON_ID),
                      actual="Import Patient Order 존재=%s / Auto Patient Import 존재=%s"
                             % (import_order_present, bool(auto_btn_hits)),
                      note="사양서1 p.87~88 VP-474.")

        from core.db import VXvueDb
        db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
        before = db.query("SELECT COUNT(*) as n FROM ORDER_PATIENT WHERE PatientId = '%s'"
                          % watch_patient_id)
        before_n = before[0]["n"] if before else 0

        search_btn = next((c for c in ui.controls(max_depth=8)
                           if c.ctrl_id == RESERVED_SEARCH_BUTTON_ID), None)
        if search_btn is None:
            r.add(10, "Search로 폴더 1회 스캔(Manual mode)", "FAIL",
                  "Search 버튼(%d)" % RESERVED_SEARCH_BUTTON_ID, "찾지 못함")
            return
        ui.click(search_btn, settle=2.0)
        time.sleep(2.0)

        status_ctrl = next((c for c in ui.controls(max_depth=8)
                            if c.ctrl_id == RESERVED_PATIENT_IMPORT_STATUS_ID), None)
        status_text = ui.get_text(status_ctrl) if status_ctrl is not None else "(확인 불가)"

        after = db.query("SELECT * FROM ORDER_PATIENT WHERE PatientId = '%s'" % watch_patient_id)
        after_n = len(after)
        imported_ok = after_n > before_n
        mismatches = []
        if imported_ok:
            row0 = after[0]
            for key, col in (("Patient Name", "PatientName"),
                             ("Acc. No.", "AccessionNumber"),
                             ("Study Description", "StudyDescription")):
                if str(row0.get(col) or "").strip() != values[key]:
                    mismatches.append("%s: DB=%r 기대=%r" % (col, row0.get(col), values[key]))
        moved = os.path.exists(os.path.join(target_dir, "end"))
        r.assert_true(10, "Search로 폴더 1회 스캔(Manual mode) -> DB(ORDER_PATIENT) 반영",
                      imported_ok and not mismatches,
                      expected="PatientId=%s 행이 새로 생기고 필드가 파일과 일치" % watch_patient_id,
                      actual=("반영 안 됨(가져오기 전 %d건 -> 후 %d건)" % (before_n, after_n)
                              if not imported_ok else
                              ("불일치 없음" if not mismatches else "; ".join(mismatches))),
                      note="Patient Import Status=%r(사양서1 VP-474 'Patient Import: 성공/실패/"
                           "전체' 형식). end/ 하위 폴더 존재=%s(처리된 파일이 옮겨지는 실측 동작)."
                           % (status_text, moved))
    finally:
        _revert()
        if with_folder_watch:
            nav_ok, _ = _goto_registration_reserved(ui)
            if nav_ok:
                import_order_back = bool([c for c in ui.controls(max_depth=8)
                                          if c.ctrl_id == RESERVED_IMPORT_BUTTON_ID])
                r.assert_true(11, "원복 후 Reserved에 수동 Import 버튼 복귀",
                              import_order_back,
                              expected="Import Patient Order(%d) 버튼 재노출" % RESERVED_IMPORT_BUTTON_ID,
                              actual="존재=%s" % import_order_back)


def _ocr_row_label(row_ctrl):
    """Column Mapping 행(owner-draw)의 라벨을 캡처+OCR로 읽는다.

    체크박스 상태와 마찬가지로 표준 API로는 읽을 수 없다(TC13/TC14, DICOM
    Burning Option과 같은 한계, CLAUDE.md 3절 3항).
    """
    try:
        import pytesseract
        from PIL import ImageGrab
        default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_tess):
            pytesseract.pytesseract.tesseract_cmd = default_tess
        img = ImageGrab.grab(bbox=row_ctrl.rect, all_screens=True)
        img = img.resize((img.width * 3, img.height * 3))
        return pytesseract.image_to_string(img, config="--psm 7").strip()
    except Exception as e:                                       # noqa: BLE001
        return "(OCR 실패: %s)" % e


def _find_mapping_row(ui, list_ctrl, label_contains, max_scroll=12):
    """Column Mapping 목록에서 라벨에 `label_contains`를 포함하는 행을 찾는다.

    실측(2026-08-21): 이 목록은 슬롯 10개짜리 **가상 목록**이라(`ListItem`이
    스크롤해도 10개로 고정, 스크롤바 크기도 변화 없음) `core.setting.
    iter_list_rows()`의 마우스 휠 스크롤이 먹지 않는다(실측: 6회 굴려도
    같은 10행 그대로) — 이 목록은 스크롤바의 위/아래 화살표
    아이콘(`Scroll` 자식 IconButton, id=1/2)을 눌러야만 실제로 넘어간다.
    그래서 여기서는 그 화살표를 직접 눌러 찾는다.

    반환: (row_ctrl, checkbox_ctrl, ocr_text) 또는 (None, None, 마지막 OCR 텍스트).
    """
    from core.ui import children

    scrollbar = S.list_scrollbar(ui, list_ctrl)
    up_btn = down_btn = None
    if scrollbar is not None:
        kids = children(scrollbar.hwnd, 1)
        up_btn = next((k for k in kids if k.ctrl_id == 1), None)
        down_btn = next((k for k in kids if k.ctrl_id == 2), None)

    def _scan():
        last_text = ""
        for row in S.list_rows(ui, list_ctrl):
            text = _ocr_row_label(row)
            last_text = text
            if label_contains.lower() in text.lower():
                checkbox = next((k for k in children(row.hwnd, 1)
                                 if k.text.strip() == "CheckBox"), None)
                return row, checkbox, text
        return None, None, last_text

    if up_btn is not None:
        for _ in range(max_scroll):
            ui.click(up_btn, settle=0.15)

    row, checkbox, text = _scan()
    if row is not None or down_btn is None:
        return row, checkbox, text

    for _ in range(max_scroll):
        ui.click(down_btn, settle=0.25)
        row, checkbox, text = _scan()
        if row is not None:
            return row, checkbox, text
    return None, None, text


def _column_mapping_regression(ui, r, work_dir):
    """헤더 설정(Column Mapping) 회귀 — 선택 컬럼을 줄여도 Import가 되는지.

    사용자 지시(NEXT_TASK.md 2절 4항): "몇 개를 빼고 Import하거나 컬럼 순서를
    바꿔서 Import가 제대로 되는지 확인. 사양서·매뉴얼에서 그 동작이 어떻게
    규정돼 있는지 먼저 확인하고 그 기준으로 판정할 것."

    사양서4(260820) p.60 VP-688 Column Mapping 표 근거: Patient ID/Patient
    Name만 "필수(체크 해제 불가)"이고 나머지는 선택 해제할 수 있다. 그래서
    필수가 아닌 컬럼(여기서는 'Institution Name') 하나를 선택 해제하고,
    Service Manual 4.6.7절이 검증 수단으로 명시한 **Sample Test**(파일
    선택 -> Refresh -> 미리보기)로 "선택을 줄여도 정상적으로 읽히는지"를
    확인한다 — Operation Manual 5.3.1절 근거로 이미 구현된 Step3과 같은
    방식이며, 값 자체가 아니라 파싱 성공 여부를 본다(Step3과 동일 원칙).

    Move Up/Move Down(컬럼 순서 재배열, 컨트롤 ID 30554/30555 실측 확인)을
    이용한 순서 변경 회귀는 이번 세션에서는 구현하지 않았다 — 행 선택 상태를
    안정적으로 유지하며 재배열·복원까지 검증하려면 추가 실측이 필요해
    범위를 좁혔다. `사양 확인 필요`가 아니라 **미구현**임을 명시한다(다음
    과제, HANDOFF.md에 근거와 함께 남김).
    """
    if not S.open_setting(ui):
        r.add(12, "헤더 설정(Column Mapping) 회귀 준비", "FAIL",
              "Setting 화면 재진입", "실패")
        return
    if S.goto_screen(ui, "Study - Import Patient") is None:
        r.add(12, "헤더 설정(Column Mapping) 회귀 준비", "FAIL",
              "화면 재진입", "찾지 못함")
        return

    list_ctrl = next((c for c in S.content_controls(ui)
                      if c.ctrl_id == COLUMN_MAPPING_LIST_ID), None)
    if list_ctrl is None:
        r.add(12, "Column Mapping 목록 확인", "FAIL",
              "ListCtrl(%d)" % COLUMN_MAPPING_LIST_ID, "찾지 못함")
        return

    target_label = "Institution Name"
    row, checkbox, ocr_text = _find_mapping_row(ui, list_ctrl, target_label)
    if row is None or checkbox is None:
        r.add(12, "선택 해제 대상 컬럼('%s') 확인" % target_label, "MANUAL",
              expected="목록에서 '%s' 행과 체크박스 발견" % target_label,
              actual="찾지 못함(마지막 OCR: %r)" % ocr_text,
              note="사양서4 p.60 VP-688 Column Mapping 표 기준 선택 해제 가능 컬럼. "
                   "OCR로 라벨을 못 찾으면 대상을 특정할 수 없어 진행하지 않는다.")
        return
    before_checked = S.checkbox_checked(ui, checkbox)
    r.add(12, "선택 해제 대상 컬럼('%s') 확인" % target_label, "PASS",
          expected="필수 아님(사양서4 p.60 VP-688, 체크 해제 가능)",
          actual="OCR=%r, 현재 체크=%s" % (ocr_text, before_checked))

    # 실측: 체크박스는 클릭 후 리스트가 재구성될 수 있어(가상 목록) 같은
    # 객체를 재사용하지 않고 매번 다시 찾는다.
    ui.click(checkbox, settle=0.6)
    row2, checkbox2, _ = _find_mapping_row(ui, list_ctrl, target_label)
    unchecked_ok = checkbox2 is not None and S.checkbox_checked(ui, checkbox2) == (not before_checked)
    r.assert_true(12, "'%s' 선택 해제" % target_label, unchecked_ok,
                  expected="체크 상태가 %s -> %s로 반영" % (before_checked, not before_checked),
                  actual="반영 확인" if unchecked_ok else "반영 확인 실패")
    if not unchecked_ok:
        return

    try:
        ack = S.update(ui, ack_timeout=8)
        r.add(12, "Column Mapping 변경 Update 적용", "PASS",
              expected="Update 성공 팝업 또는 오류 없이 설정 저장 완료",
              actual="완료 팝업: %s" % (ack or "없음(오류 없이 창 닫힘)"))

        sample, err = _read_sample(ui, work_dir, sample_name="ColumnMappingSample.csv")
        header_ok = (sample is not None
                    and all(target_label.lower() not in c.lower() for c in sample["header"]))
        r.assert_true(12, "Save Sample로 선택 해제 반영 확인", header_ok,
                      expected="Save Sample 헤더에서 '%s' 제외" % target_label,
                      actual=(err if sample is None else
                              "컬럼 %d개: %s" % (len(sample["header"]),
                                                ", ".join(c.strip() for c in sample["header"]))))
        if not header_ok:
            return

        header, example = sample["header"], sample["example"]
        row_vals = [TEST_VALUES.get(col.strip(), example[i] if i < len(example) else "")
                    for i, col in enumerate(header)]
        test_path = os.path.join(work_dir, "PatientListTest_ColumnMapping.csv")
        with io.open(test_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=sample["delimiter"])
            w.writerow(header)
            w.writerow(row_vals)

        ids = IMPORT_PATIENT_IDS
        browse_btn = field(ui, ids["browse_button"])
        refresh_btn = field(ui, ids["refresh_button"])
        if not (browse_btn and refresh_btn):
            r.add(12, "축소된 헤더로 Sample Test 파싱 미리보기", "FAIL",
                  "Browse/Refresh 컨트롤", "찾지 못함")
            return
        ui.click(browse_btn, settle=1.0)
        ok, note = S._file_dialog_submit(ui, test_path)
        if not ok:
            r.add(12, "축소된 헤더로 Sample Test 파싱 미리보기", "FAIL", "파일 선택", note)
            return
        ui.click(refresh_btn, settle=1.0)
        time.sleep(0.5)
        grid = next((c for c in S.list_ctrls(ui) if c.ctrl_id == ids["preview_grid"]), None)
        rows = S.list_rows(ui, grid) if grid is not None else []
        r.assert_true(12, "축소된 헤더(%d개 컬럼)로 Sample Test 파싱 미리보기" % len(header),
                      bool(rows),
                      expected="Service Manual 4.6.7절 Step4(Sample Test) 기준 "
                               "정상 파싱 — 필수 컬럼(Patient ID/Patient Name)만 "
                               "있으면 선택 해제된 나머지 컬럼과 무관하게 표시돼야 함"
                               "(사양서4 p.60 VP-688)",
                      actual="미리보기 행 %d개" % len(rows))
    finally:
        row3, checkbox3, _ = _find_mapping_row(ui, list_ctrl, target_label)
        revert_ok = False
        if checkbox3 is not None:
            if S.checkbox_checked(ui, checkbox3) != before_checked:
                ui.click(checkbox3, settle=0.6)
            _, checkbox4, _ = _find_mapping_row(ui, list_ctrl, target_label)
            revert_ok = checkbox4 is not None and S.checkbox_checked(ui, checkbox4) == before_checked
            if revert_ok:
                S.update(ui, ack_timeout=8)
        r.assert_true(12, "'%s' 선택 상태 원복" % target_label, revert_ok,
                      expected="원래 체크 상태(%s)로 복원" % before_checked,
                      actual="복원 확인" if revert_ok else
                      "복원 실패 — 사람이 Setting > Study - Import Patient에서 직접 확인할 것")


def run(ui, cfg, work_dir=None, with_folder_watch=True):
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
    _column_mapping_regression(ui, r, work_dir)
    _folder_watch_step(ui, r, cfg, work_dir, with_folder_watch)

    return r.finalize()
