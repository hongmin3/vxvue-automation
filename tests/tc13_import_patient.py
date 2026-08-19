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
MAIN_NAV_TAB_CONTAINER = 31197
MAIN_NAV_REGISTRATION = 8

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


def run(ui, cfg, work_dir=None):
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

    from core.db import VXvueDb
    db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
    before = db.query("SELECT COUNT(*) as n FROM ORDER_PATIENT "
                      "WHERE PatientId = '%s'" % TEST_VALUES["Patient ID"])
    before_n = before[0]["n"] if before else 0

    import_btn = field(ui, RESERVED_IMPORT_BUTTON_ID)
    if import_btn is None:
        r.add(5, "Import Patient Order 실행", "FAIL",
              "Import 버튼(%d)" % RESERVED_IMPORT_BUTTON_ID, "찾지 못함")
        return r.finalize()

    ui.click(import_btn, settle=1.5)
    ok, note = S._file_dialog_submit(ui, test_path)
    while ui.dismiss_info(timeout=3):
        pass

    if not ok:
        r.add(5, "Import Patient Order 실행", "FAIL", "파일 선택·확인", note)
        return r.finalize()

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

    return r.finalize()
