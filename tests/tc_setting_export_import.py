# -*- coding: utf-8 -*-
"""TC_Setting_ExportImport — Setting 값 Export / 변경 / Import 복원 회귀.

사용자 제안 시나리오를 실측 근거로 보강한 것이다. 상세 설계는
`지식/[자동화 설계] VXvue Setting Export-Import 회귀 설계.md` 참고.
사용자 확인(2026-08-18): Windows Update 체크리스트에 없는 항목이므로
**기본기능 회귀 쪽 신규 TC**로 관리한다.

## 흐름 (3단 비교)

```
S0  설정 스냅샷(DB 설정 테이블 + 설정 파일 해시) + UI 표시값 전체 캡처
 +-> Export  ->  export_A.vxs
 +-> 변경 수행 (탭별 최대 1건 + Extra Tool)
S1  스냅샷      [검증] S1 != S0   <- 변경이 실제로 반영됐다는 증명
 +-> Import  export_A.vxs   (파괴적. 사전 백업 후 실행)
 +-> 뷰어 재기동 + 로그인
S2  스냅샷 + UI 표시값 전체 재캡처
    [검증] S2 == S0 (DB)          <- Export 당시 값이 DB에 그대로 복원됐다
    [검증] UI(S2) == UI(S0)       <- 화면에도 그 값이 그대로 다시 그려진다
```

**중간 검증(S1 != S0)이 핵심이다.** 이것이 없으면 변경이 한 건도 먹지 않아도
마지막 대조가 통과해 헛된 PASS가 난다.

사용자 확인(2026-08-19): "옵션 값이 기준과 완전히 같아야 PASS"인 정밀 회귀는
TC14가 아니라 이 TC의 책임이다. TC14는 Windows Update로 탭 클릭·옵션 노출이
깨지지 않았는지만 보고, 값이 달라도 `확인 필요`로만 표시한다. DB가 정확히
복원돼도 Setting 화면이 그 값을 제대로 다시 그리지 못하는 경우(렌더링 결함)는
DB 스냅샷 비교만으로 잡히지 않으므로, 화면에 실제로 표시되는 값도 S0/S2로
비교한다(`core/setting.capture_all_screen_values`,
`core/setting.diff_all_screen_values` — TC14와 공유하는 헬퍼).

## 판정에서 제외하는 것

`C:\\ProgramData\\VXvue\\Viewer.xml`(Theme/Language/Generator/AIEngine/Camera 등
머신 단위 설정)은 `.vxs` 안에 **포함되지 않는다**. 사용자 확인(2026-08-18):
복원되지 않는 것이 정상이므로 판정에서 제외하고 참고 정보로만 기록한다.

## 안전 장치

- Import는 `.vxs` 안의 `Data.bak`으로 **DB 전체를 복원**한다(환자·검사 포함).
  실행 전에 `core/dbreset.backup()`으로 안전 백업을 남긴다.
- 변경 대상에서 아래 화면은 제외한다. 되돌리기 위험이 크거나 다른 TC의 선행
  조건을 깨뜨린다.
"""

import ctypes
import os
import time
from datetime import datetime

_u32 = ctypes.windll.user32
_GWL_STYLE = -16
_ES_READONLY = 0x0800

from core import config_snapshot as snap
from core import dbreset
from core import setting as S
from core import vxs as vxs_mod
from core.result import TCResult

TC_ID = "TC_Setting_ExportImport"
TC_TITLE = "Setting Export / 변경 / Import 복원 회귀"

# 변경하지 않을 화면. 이유를 함께 적어 두어 나중에 판단을 되짚을 수 있게 한다.
MUTATION_EXCLUDE = {
    "System - License": "라이선스 키를 건드리면 복구가 어렵다",
    "System - Access": "KIOSK/접근 제어를 켜면 이후 조작이 막힐 수 있다",
    "System - Product Info.": "읽기 전용 정보 화면",
    "Backup - Backup": "아카이브 실행 위험",
    "Backup - Clean": "데이터 삭제 실행 위험",
    "Backup - Restore": "복원 실행 위험",
    "Procedure - Procedure Manager": "외부 프로그램을 실행하는 버튼만 있음",
    "DICOM - Queue": "실행 버튼만 있음",
    "DICOM - MWL": "MWL_SCP 등록을 바꾸면 TC02 선행 조건이 깨진다",
    "DICOM - Storage": "BUNNY_TEST 등록을 바꾸면 TC05 선행 조건이 깨진다",
    "DICOM - Print": "PRINT_SCP 등록을 바꾸면 TC07 선행 조건이 깨진다",
    "Integration - Detector": "장비(디텍터) 설정",
    "Integration - Generator": "장비(제너레이터) 설정",
    "Integration - Camera": "장비(카메라/VX.LIVE.SERVER) 설정",
    "Integration - Bucky": "장비 설정",
    "Integration - Collimation": "장비 설정",
    "Integration - XIPL": "XIPL 파라미터 경로 - 공유 설치라 다른 제품에 영향",
    "System - Account": "사용자 판단(2026-08-19): Add 직후 자동 저장, 이후 Update가 "
                        "'Empty password' 오류로 거부되는 등 흐름이 불안정했고, 목록 "
                        "행 선택도 신뢰할 수 없어(어느 행을 클릭해도 같은 값이 표시됨) "
                        "실제 admin/service 계정을 잘못 건드릴 위험이 있었다. 위험 대비 "
                        "이익이 낮아 이 화면은 다루지 않기로 함. 부작용: 테스트 중 생성된 "
                        "'service1' 테스트 계정(ACCOUNT.accountKey=3, systemFlag=0)이 "
                        "남아 있음 — 필요하면 사람이 UI에서 직접 삭제할 것.",
}

# --- 컨트롤 단위 뮤테이션 금지 -----------------------------------------
# 화면 전체를 제외하면 그 화면의 회귀 자체를 못 하므로, **특정 컨트롤만**
# 건드리지 않도록 하는 목록이다.
#
# `System - Theme`의 "Use virtual keyboard"가 그 대상이다(사용자 지시,
# 2026-08-19: "화상키보드 옵션은 자동화할 때 체크하지 않도록 예외처리").
# 이 옵션을 Yes로 켜면 이후 모든 입력 필드에서 **화상 키보드 창이 떠서 자동화의
# 키 입력이 그쪽으로 가고**, 그 창을 닫기 전에는 조작이 진행되지 않는다. 즉
# 자동화가 스스로 이후 단계를 막아 버리는 설정이다(HANDOFF 세션 3부 "환경/도구
# 관련 주의"에도 "켜져 있으면 안 된다"고 기록돼 있다).
#
# 컨트롤 ID를 실측으로 확정하지 못한 상태에서 이름만으로 막을 수는 없으므로
# (owner-draw라 라벨을 표준 API로 읽을 수 없다) **두 겹으로** 막는다.
#   1) `MUTATION_EXCLUDE_CONTROLS`: 실측된 컨트롤 ID는 여기서 정확히 뺀다.
#   2) `VIRTUAL_KEYBOARD_SCREEN`: 그 화면에서는 RadioButton/CheckBox를 아예
#      건드리지 않는다(Edit 텍스트 변경만 한다). 어느 라디오가 화상키보드인지
#      ID로 특정하지 못하는 동안의 안전장치다.
MUTATION_EXCLUDE_CONTROLS = {
    # "System - Theme": (라디오 ID, ...)  <- 실측 후 채운다
}

# 이 화면에서는 라디오/체크박스를 건드리지 않는다(위 주석 참고).
NO_TOGGLE_SCREENS = {
    "System - Theme": "Use virtual keyboard를 켜면 화상 키보드 창이 떠서 이후 "
                      "자동화 입력이 전부 막힌다(사용자 지시로 예외처리). "
                      "이 화면에서는 Edit 텍스트 변경만 수행한다.",
}

MUTATION_SUFFIX = "_QA1"


def _editable_edits(ui):
    """이 화면에서 안전하게 값을 바꿀 수 있는 Edit 컨트롤 목록.

    읽기 전용(ES_READONLY)과 비활성 컨트롤은 제외한다. 값이 이미 있는 것을
    우선하되, 빈 칸도 후보로 둔다(입력 자체가 변경이 된다).
    """
    out = []
    for c in S.content_controls(ui):
        if c.cls != "Edit":
            continue
        w, h = c.size
        if w < 60 or h < 12:
            continue
        style = _u32.GetWindowLongW(c.hwnd, _GWL_STYLE)
        if style & _ES_READONLY:
            continue
        if not _u32.IsWindowEnabled(c.hwnd):
            continue
        out.append(c)
    return out


def _clickable_by_text(ui, text, min_size=12):
    """`text`로 표시되는 컨트롤(CheckBox/RadioButton 등) 중 클릭 가능한 것.

    체크박스/라디오는 커스텀 owner-draw라 클릭 전 상태를 표준 API로 읽을 수
    없다(`core/setting.screen_values`의 `unreadable_state_controls`와 같은
    한계). 그래서 여기서는 "무엇을 클릭했는지"만 확정하고, 실제로 값이
    바뀌었는지는 호출부가 DB 스냅샷 비교로 검증한다.
    """
    out = []
    for c in S.content_controls(ui):
        if c.text.strip() != text:
            continue
        w, h = c.size
        if w < min_size or h < min_size:
            continue
        if not _u32.IsWindowEnabled(c.hwnd):
            continue
        out.append(c)
    return out


def mutate_screen(ui, screen_title, evidence_dir=None):
    """화면 하나에서 가능한 만큼 다양하게 값을 바꾸고 Update한다.

    사용자 확인(2026-08-19): "텍스트 입력만이 아니라 체크박스·토글도 다양하게
    바꿔봐라." Edit 텍스트 변경에 더해, 이 화면에 있는 CheckBox/RadioButton도
    하나씩 클릭한다. 체크박스/라디오는 커스텀 owner-draw라 클릭 전 상태를
    표준 API로 읽을 수 없으므로(`core/setting.screen_values`와 같은 한계),
    "무엇을 클릭했는지"만 기록하고 실제 반영 여부는 Step 5(DB 스냅샷
    S1 != S0)로 검증한다.

    반환: dict(screen=..., changed=bool, detail=..., skipped_reason=...)
    """
    if screen_title in MUTATION_EXCLUDE:
        return {"screen": screen_title, "changed": False,
                "skipped_reason": MUTATION_EXCLUDE[screen_title]}

    edits = _editable_edits(ui)
    banned = set(MUTATION_EXCLUDE_CONTROLS.get(screen_title, ()))
    no_toggle = screen_title in NO_TOGGLE_SCREENS
    if no_toggle:
        checkboxes, radios = [], []
    else:
        checkboxes = [c for c in _clickable_by_text(ui, "CheckBox")
                      if c.ctrl_id not in banned]
        radios = [c for c in _clickable_by_text(ui, "RadioButton")
                  if c.ctrl_id not in banned]
    edits = [c for c in edits if c.ctrl_id not in banned]
    if not edits and not checkboxes and not radios:
        return {"screen": screen_title, "changed": False,
                "skipped_reason": ("변경 가능한 Edit/CheckBox/RadioButton 컨트롤이 없음"
                                   if not no_toggle else
                                   "토글 금지 화면이고 변경 가능한 Edit도 없음: %s"
                                   % NO_TOGGLE_SCREENS[screen_title])}

    actions = []
    text_changed = False

    if edits:
        target = edits[0]
        before = ui.get_text(target)
        after = (before + MUTATION_SUFFIX) if before else MUTATION_SUFFIX
        # 길이 제한이 있는 필드에서 잘릴 수 있으므로 너무 길면 접미만 남긴다.
        if len(after) > 60:
            after = MUTATION_SUFFIX
        ui.type_text(target, after, clear=True)
        actual = ui.get_text(target)
        text_changed = actual != before
        actions.append("Edit %d: %r -> %r" % (target.ctrl_id, before, actual))

    if checkboxes:
        cb = checkboxes[0]
        ui.click(cb, settle=0.4)
        actions.append("CheckBox %d 클릭(상태는 DB 스냅샷으로 검증)" % cb.ctrl_id)

    if radios:
        rb = radios[0]
        ui.click(rb, settle=0.4)
        actions.append("RadioButton %d 클릭(상태는 DB 스냅샷으로 검증)" % rb.ctrl_id)

    evidence = None
    if evidence_dir:
        evidence = os.path.join(evidence_dir, "mutate_%s.png"
                                % screen_title.replace(" ", "_").replace("/", "_"))
    popup = S.update(ui, evidence_path=evidence)
    actions.append("Update 팝업: %s" % (popup or "없음"))

    changed = text_changed or bool(checkboxes) or bool(radios)
    return {"screen": screen_title, "changed": changed,
            "detail": "; ".join(actions),
            "skipped_reason": None}


# Registration - Physician 화면의 Referring Physician 목록/버튼(실측,
# work/probe_physician_account.py). Reading/Performing 목록도 구조가
# 같지만, 다양화 목적으로는 하나만 건드려도 충분하다.
PHYSICIAN_LIST_ID = 31147
PHYSICIAN_ADD_BUTTON_ID = 30797


def mutate_physician_screen(ui, evidence_dir=None):
    """Registration - Physician: Referring Physician 목록에 신규 항목을 추가한다.

    사용자 확인(2026-08-19): "add를 클릭해서 신규로... 전문의 명단을
    추가한다든지." 매뉴얼 근거(Service Manual p.60-61): Add 클릭 -> 빈
    항목 생성 -> 더블클릭으로 이름 인라인 수정(별도 ID 필드 없이 이름
    텍스트만 있다).
    """
    from core.ui import children

    add_btn = [c for c in S.content_controls(ui) if c.ctrl_id == PHYSICIAN_ADD_BUTTON_ID]
    if not add_btn:
        return {"screen": "Registration - Physician", "changed": False,
                "skipped_reason": "Add 버튼(%d)을 찾지 못함" % PHYSICIAN_ADD_BUTTON_ID}

    target_list = next((lc for lc in S.list_ctrls(ui)
                        if lc.ctrl_id == PHYSICIAN_LIST_ID), None)
    if target_list is None:
        return {"screen": "Registration - Physician", "changed": False,
                "skipped_reason": "대상 목록(%d)을 찾지 못함" % PHYSICIAN_LIST_ID}

    before_rows = len(S.list_rows(ui, target_list))
    ui.click(add_btn[0], settle=1.0)
    after_rows = S.list_rows(ui, target_list)
    if len(after_rows) <= before_rows:
        return {"screen": "Registration - Physician", "changed": False,
                "skipped_reason": "Add 클릭 후에도 목록 행이 늘지 않음"}

    new_row = after_rows[-1]
    ui.double_click(S.row_click_point(ui, new_row), settle=0.6)

    edit_ctrl = next((k for k in children(new_row.hwnd, 2) if k.cls == "Edit"), None)
    if edit_ctrl is None:
        return {"screen": "Registration - Physician", "changed": True,
                "detail": "행은 추가됐으나(31147: %d -> %d) 더블클릭 후 인라인 편집 "
                         "Edit을 찾지 못해 이름은 기본값(빈 값)으로 남음"
                         % (before_rows, len(after_rows)),
                "skipped_reason": None}

    name = "QA Test Physician"
    ui.type_text(edit_ctrl, name, clear=True)
    ui.raw_key(0x0D)
    time.sleep(0.3)

    evidence = os.path.join(evidence_dir, "mutate_RegistrationPhysician.png") if evidence_dir else None
    popup = S.update(ui, evidence_path=evidence)

    return {"screen": "Registration - Physician", "changed": True,
            "detail": "신규 전문의 추가: 목록 %d 행 %d -> %d, 이름=%r (Update 팝업: %s)"
                      % (PHYSICIAN_LIST_ID, before_rows, len(after_rows), name,
                         popup or "없음"),
            "skipped_reason": None}


def mutate_extra_tool(ui, cfg, evidence_dir=None):
    """Integration > Extra Tool: Bunny를 대상으로 설정하고 S.B.S.C.를 켠다.

    사용자 확인(2026-08-18): Extra Tool 전송 대상은 Bunny를 재사용한다.
    이 변경은 DB `AE_LIST.RemoveSBSC`로 값 단위 검증이 가능해서, 스냅샷 비교의
    '변경이 실제로 반영됐다'는 근거로 가장 확실하다. TC06의 선행 조건도 함께
    갖춰진다.
    """
    ids = ((cfg.get("viewer") or {}).get("control_ids") or {}) \
        .get("setting_integration_extra_tool") or {}
    bunny = ((cfg.get("dicom") or {}).get("bunny") or {})
    servers = (cfg.get("dicom") or {}).get("servers_to_register") or []
    storage = next((s for s in servers if s.get("kind") == "Storage"), {})

    def one(ctrl_id):
        found = [c for c in ui.controls(max_depth=6) if c.ctrl_id == ctrl_id]
        return found[0] if found else None

    # 주소를 코드에 하드코딩하지 않는다. 설정에 없으면 그 필드는 건너뛴다.
    steps = []
    for key, value in (("ae_title_edit", storage.get("ae_title")),
                       ("ip_edit", storage.get("ip")),
                       ("port_edit", str(storage.get("port")) if storage.get("port") else None)):
        if not value:
            steps.append("%s: 설정(dicom.servers_to_register[Storage])에 값이 없어 건너뜀" % key)
            continue
        cid = ids.get(key)
        ctrl = one(cid) if cid else None
        if ctrl is None:
            steps.append("%s(%s) 컨트롤 없음" % (key, cid))
            continue
        ui.type_text(ctrl, value, clear=True)
        steps.append("%s <- %s" % (key, value))

    for key in ("use_extra_tool_check", "remove_sbsc_check"):
        cid = ids.get(key)
        ctrl = one(cid) if cid else None
        if ctrl is None:
            # 스크롤 밖일 수 있으니 찾아서 끌어온다.
            ctrl = ui.find_scrolling(lambda c, _cid=cid: c.ctrl_id == _cid,
                                     anchor=(680, 700))
        if ctrl is None:
            steps.append("%s(%s) 컨트롤 없음" % (key, cid))
            continue
        ui.click(ctrl, settle=0.5)
        steps.append("%s 클릭" % key)

    evidence = os.path.join(evidence_dir, "mutate_ExtraTool.png") if evidence_dir else None
    popup = S.update(ui, evidence_path=evidence)
    steps.append("Update 팝업: %s" % (popup or "없음"))
    return {"screen": "Integration - Extra Tool", "changed": True,
            "detail": " / ".join(steps), "skipped_reason": None}


def run(ui, cfg, work_dir=None, evidence_dir=None, do_import=True,
        relaunch=None):
    """3단 비교 시나리오를 수행한다.

    relaunch: Import 후 뷰어를 재기동·로그인하는 콜러블. None이면 이 TC가
    직접 처리한다(config의 viewer.exe / login 사용).
    """
    from core.db import VXvueDb

    r = TCResult(TC_ID, TC_TITLE)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work_dir = work_dir or os.path.join(root, "work", "vms")
    evidence_dir = evidence_dir or os.path.join(root, "Evidence", "setting_export_import")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(evidence_dir, exist_ok=True)

    db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- Step 1: S0 스냅샷 -------------------------------------------
    s0 = snap.take(db, label="S0 (export 직전)")
    s0_path = snap.save(s0, os.path.join(work_dir, "snapshot_S0_%s.json" % stamp))
    r.add(1, "설정 스냅샷 S0 취득", "PASS",
          "설정 테이블 + 설정 파일 해시",
          "테이블 %d개 / 파일 %d개" % (len(s0["tables"]), len(s0["files"])),
          note="환자·검사 건수: %s" % s0["data_row_counts"])
    r.attach(s0_path)

    if not S.open_setting(ui):
        r.add(2, "Setting 화면 진입", "FAIL", "Setting 화면", "진입 실패")
        return r.finalize()

    # UI 표시값 기준(S0) — 실제로 화면에 보이는 Edit/콤보/라벨/체크박스 구성을
    # 통째로 캡처한다. Import 후(S2) 이것과 완전히 같아야 PASS다(Step 11).
    # 사용자 확인(2026-08-19): 값이 완전히 같아야 PASS인 정밀 회귀는 TC14가
    # 아니라 이 TC의 책임이다.
    ui0 = S.capture_all_screen_values(ui)
    r.add(2, "Setting 화면 진입 + UI 표시값 캡처(S0)", "PASS",
          "Setting 화면 진입 성공", "%s / 화면 %d개 캡처" % (S.title(ui) or "(제목 없음)",
                                                     len(ui0)))

    # --- Step 3: Export ----------------------------------------------
    # 확장자를 안 줘도 제품이 자동으로 .vxs를 붙인다(사용자 확인 2026-08-19).
    # 확장자를 직접 붙이면 오히려 이중으로 남을 수 있어 빼고 넘긴다.
    export_a = os.path.join(work_dir, "export_A_%s" % stamp)
    made, note = S.export_settings(ui, export_a)
    if not made:
        r.add(3, "Setting Export", "FAIL", export_a, note or "파일 생성 실패")
        return r.finalize()
    summary = vxs_mod.summary(made)
    r.add(3, "Setting Export", "PASS", ".vxs 생성",
          "%s (%d bytes, 엔트리 %d개, DB백업 포함=%s)"
          % (os.path.basename(made), summary["size_bytes"],
             summary["entry_count"], summary["has_db_backup"]),
          note=("Data.bak(%d bytes)이 포함돼 있어 Import는 DB 전체 복원이다. %s"
                % (summary["db_backup_bytes"], note)).strip())
    r.attach(made)

    # Export 완료 확인 Info 팝업이 파일 생성 직후가 아니라 몇 초 더 지나서
    # 뜨는 경우가 실측됐다(2026-08-19, export_settings() 자체의 dismiss도
    # 놓친 사례 확인). 이 팝업을 닫지 않으면 Step 4의 모든 클릭이 무시되고
    # "변경 0건"으로 조용히 실패하므로, Step 4 진입 전 한 번 더 넉넉하게
    # 확인해 닫는다.
    while ui.dismiss_info(timeout=3):
        pass

    # --- Step 4: 변경 수행 --------------------------------------------
    mutations = []
    S.collapse_all(ui)
    majors, _ = S.menu_items(ui)
    for mi in range(len(majors)):
        before_ids = S.visible_minor_ids(ui)
        if S.toggle_major(ui, mi) is None:
            continue
        time.sleep(0.3)
        child_ids = sorted(S.visible_minor_ids(ui) - before_ids)
        for minor_id in child_ids:
            scr = S.open_screen(ui, minor_id)
            if not scr:
                continue
            if scr == "Integration - Extra Tool":
                mutations.append(mutate_extra_tool(ui, cfg, evidence_dir))
            elif scr == "Registration - Physician":
                mutations.append(mutate_physician_screen(ui, evidence_dir))
            else:
                mutations.append(mutate_screen(ui, scr, evidence_dir))
        S.toggle_major(ui, mi)
        time.sleep(0.2)

    changed = [m for m in mutations if m["changed"]]
    skipped = [m for m in mutations if not m["changed"]]
    r.assert_true(4, "설정 변경 시도",
                  bool(changed),
                  expected="1건 이상 변경",
                  actual="변경 %d건 / 건너뜀 %d건" % (len(changed), len(skipped)),
                  note="; ".join("%s: %s" % (m["screen"], m.get("detail") or
                                             m.get("skipped_reason"))
                                 for m in mutations)[:1500])

    # --- Step 5: S1 스냅샷 + 변경 반영 확인 -----------------------------
    s1 = snap.take(db, label="S1 (변경 후)")
    s1_path = snap.save(s1, os.path.join(work_dir, "snapshot_S1_%s.json" % stamp))
    r.attach(s1_path)
    diff_01 = snap.compare(s0, s1)
    r.assert_true(5, "변경이 실제로 DB에 반영되었는지 (S1 != S0)",
                  not diff_01["identical"],
                  expected="S0과 S1이 달라야 한다",
                  actual=snap.changed_names(diff_01),
                  note="이 검증이 없으면 변경이 한 건도 먹지 않아도 마지막 대조가 "
                       "통과해 헛된 PASS가 난다.")

    if not do_import:
        r.manual(6, "Import 복원", "사용자 지시로 Import는 수행하지 않았다. "
                                  "export_A와 S0/S1 스냅샷은 보관되어 있어 나중에 이어서 검증할 수 있다.",
                 expected="Import 후 S2 == S0", actual="미수행")
        return r.finalize()

    # --- Step 6: 안전 백업 + Import ------------------------------------
    try:
        safety = dbreset.backup(cfg.get("sql_server", r".\CHAMELEON"),
                                cfg.get("database", "DRF"),
                                prefix="PRE_SETTING_IMPORT",
                                note="before Setting Import in %s" % TC_ID)
    except dbreset.DbResetError as exc:
        r.add(6, "Import 전 안전 백업", "FAIL", "백업 생성", str(exc))
        return r.finalize()
    r.add(6, "Import 전 안전 백업", "PASS", "백업 생성", safety,
          note="Import는 DB 전체를 되돌리므로 실패 시 이 백업으로 복구한다.")

    ok, imp_note = S.import_settings(ui, made, confirm=True)
    r.assert_true(7, "Setting Import 실행", ok,
                  expected="Import 완료", actual=imp_note or ("성공" if ok else "실패"))

    # --- Step 8: 재기동 + S2 ------------------------------------------
    if relaunch is None:
        def relaunch():
            v = cfg.get("viewer") or {}
            lg = v.get("login") or {}
            if not ui.pid:
                ui.launch(v.get("exe"), wait=20)
            end = time.time() + v.get("startup_timeout", 240)
            while time.time() < end and not ui.at_login_screen():
                if not ui.pid:
                    ui.launch(v.get("exe"), wait=20)
                time.sleep(3)
            return ui.login(lg.get("id"), lg.get("password"))

    relaunched = relaunch()
    r.assert_true(8, "Import 후 뷰어 재기동 및 로그인", bool(relaunched),
                  expected="재기동 후 로그인 성공",
                  actual="성공" if relaunched else "실패")

    s2 = snap.take(db, label="S2 (Import 후)")
    s2_path = snap.save(s2, os.path.join(work_dir, "snapshot_S2_%s.json" % stamp))
    r.attach(s2_path)
    diff_02 = snap.compare(s0, s2)
    r.assert_true(9, "Export 당시 설정이 그대로 복원되었는지 (S2 == S0)",
                  diff_02["identical"],
                  expected="S0과 S2가 완전히 같아야 한다",
                  actual=snap.changed_names(diff_02),
                  note="복원되지 않은 항목이 있으면 위 목록이 그 항목이다.")

    if diff_02["out_of_scope_diffs"]:
        r.add(10, "판정 제외 항목(머신 단위 설정) 변화", "MANUAL",
              "Viewer.xml 등은 .vxs에 포함되지 않아 복원 대상이 아님",
              ", ".join(os.path.basename(p) for p in diff_02["out_of_scope_diffs"]),
              note="사용자 확인(2026-08-18): 복원되지 않는 것이 정상이므로 판정에서 제외한다.")

    # --- Step 11: UI 표시값 대조 (S2 vs S0) ----------------------------
    # 사용자 확인(2026-08-19): "옵션 값이 기준과 완전히 같아야 PASS"인 정밀
    # 회귀는 TC14가 아니라 이 TC의 책임이다. Import가 DB를 정확히 복원했어도,
    # Setting 화면이 그 값을 제대로 다시 그려내지 못하면(렌더링 결함) DB
    # 스냅샷 비교(Step 9)만으로는 못 잡는다 — 그래서 실제 화면 표시값도
    # S0(Export 직전)과 대조한다.
    ui2 = S.capture_all_screen_values(ui)
    d = S.diff_all_screen_values(ui0, ui2)
    ok = not (d["missing"] or d["added"] or d["struct_diffs"] or d["value_diffs"])
    r.assert_true(11, "UI 표시값이 Export 당시와 완전히 같은지 (S2 화면 == S0 화면)",
                  ok,
                  expected="S0에서 캡처한 %d개 화면의 옵션 구성·표시값과 완전 일치"
                           % len(ui0),
                  actual=("일치 (Edit/콤보/라벨/체크박스 구성과 값 전부 동일)" if ok else
                          "불일치 - 없어진 화면 %d / 새 화면 %d / 구성 차이 %d건 / "
                          "값 차이 %d건%s"
                          % (len(d["missing"]), len(d["added"]),
                             len(d["struct_diffs"]), len(d["value_diffs"]),
                             (" -> " + "; ".join(
                                 (d["struct_diffs"] + d["value_diffs"])[:8]))
                             if (d["struct_diffs"] or d["value_diffs"]) else "")),
                  note="Setting 화면 진입 직후(변경 전) 캡처한 S0 표시값과, Import·"
                       "재기동 후(S2) 같은 화면을 다시 순회해 얻은 표시값을 비교한다. "
                       "여기서는 (TC14와 달리) 값이 다르면 FAIL이다 - 이 TC의 목적이 "
                       "'Export 당시 값이 그대로 복원되는가'이기 때문이다.")

    return r.finalize()
