# -*- coding: utf-8 -*-
"""TC_Setting_ExportImport — Setting 값 Export / 변경 / Import 복원 회귀.

사용자 제안 시나리오를 실측 근거로 보강한 것이다. 상세 설계는
`지식/[자동화 설계] VXvue Setting Export-Import 회귀 설계.md` 참고.
사용자 확인(2026-08-18): Windows Update 체크리스트에 없는 항목이므로
**기본기능 회귀 쪽 신규 TC**로 관리한다.

## 흐름 (3단 비교)

```
S0  설정 스냅샷(DB 설정 테이블 + 설정 파일 해시)
 +-> Export  ->  export_A.vxs
 +-> 변경 수행 (탭별 최대 1건 + Extra Tool)
S1  스냅샷      [검증] S1 != S0   <- 변경이 실제로 반영됐다는 증명
 +-> Import  export_A.vxs   (파괴적. 사전 백업 후 실행)
 +-> 뷰어 재기동 + 로그인
S2  스냅샷      [검증] S2 == S0   <- Export 당시 값이 유지됐다
```

**중간 검증(S1 != S0)이 핵심이다.** 이것이 없으면 변경이 한 건도 먹지 않아도
마지막 대조가 통과해 헛된 PASS가 난다.

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

import os
import time
from datetime import datetime

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
    "Integration - XIPL": "XIPL 파라미터 경로 — 공유 설치라 다른 제품에 영향",
}

MUTATION_SUFFIX = "_QA1"


def _editable_edits(ui):
    """이 화면에서 안전하게 값을 바꿀 수 있는 Edit 컨트롤 목록.

    읽기 전용(ES_READONLY)과 비활성 컨트롤은 제외한다. 값이 이미 있는 것을
    우선하되, 빈 칸도 후보로 둔다(입력 자체가 변경이 된다).
    """
    import ctypes
    u32 = ctypes.windll.user32
    GWL_STYLE = -16
    ES_READONLY = 0x0800

    out = []
    for c in S.content_controls(ui):
        if c.cls != "Edit":
            continue
        w, h = c.size
        if w < 60 or h < 12:
            continue
        style = u32.GetWindowLongW(c.hwnd, GWL_STYLE)
        if style & ES_READONLY:
            continue
        if not u32.IsWindowEnabled(c.hwnd):
            continue
        out.append(c)
    return out


def mutate_screen(ui, screen_title, evidence_dir=None):
    """화면 하나에서 설정 1건을 바꾸고 Update한다.

    반환: dict(screen=..., changed=bool, detail=..., skipped_reason=...)
    """
    if screen_title in MUTATION_EXCLUDE:
        return {"screen": screen_title, "changed": False,
                "skipped_reason": MUTATION_EXCLUDE[screen_title]}

    edits = _editable_edits(ui)
    if not edits:
        return {"screen": screen_title, "changed": False,
                "skipped_reason": "변경 가능한 Edit 컨트롤이 없음(체크박스/콤보 전용 화면)"}

    target = edits[0]
    before = ui.get_text(target)
    after = (before + MUTATION_SUFFIX) if before else MUTATION_SUFFIX
    # 길이 제한이 있는 필드에서 잘릴 수 있으므로 너무 길면 접미만 남긴다.
    if len(after) > 60:
        after = MUTATION_SUFFIX

    ui.type_text(target, after, clear=True)
    actual = ui.get_text(target)
    evidence = None
    if evidence_dir:
        evidence = os.path.join(evidence_dir, "mutate_%s.png"
                                % screen_title.replace(" ", "_").replace("/", "_"))
    popup = S.update(ui, evidence_path=evidence)

    return {"screen": screen_title, "changed": actual != before,
            "detail": "컨트롤 %d: %r -> %r (Update 팝업: %s)"
                      % (target.ctrl_id, before, actual, popup or "없음"),
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

    # --- Step 2: Export ----------------------------------------------
    export_a = os.path.join(work_dir, "export_A_%s.vxs" % stamp)
    made, note = S.export_settings(ui, export_a)
    if not made:
        r.add(2, "Setting Export", "FAIL", export_a, note or "파일 생성 실패")
        return r.finalize()
    summary = vxs_mod.summary(made)
    r.add(2, "Setting Export", "PASS", ".vxs 생성",
          "%s (%d bytes, 엔트리 %d개, DB백업 포함=%s)"
          % (os.path.basename(made), summary["size_bytes"],
             summary["entry_count"], summary["has_db_backup"]),
          note=("Data.bak(%d bytes)이 포함돼 있어 Import는 DB 전체 복원이다. %s"
                % (summary["db_backup_bytes"], note)).strip())
    r.attach(made)

    # --- Step 3: 변경 수행 --------------------------------------------
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
            else:
                mutations.append(mutate_screen(ui, scr, evidence_dir))
        S.toggle_major(ui, mi)
        time.sleep(0.2)

    changed = [m for m in mutations if m["changed"]]
    skipped = [m for m in mutations if not m["changed"]]
    r.assert_true(3, "설정 변경 시도",
                  bool(changed),
                  expected="1건 이상 변경",
                  actual="변경 %d건 / 건너뜀 %d건" % (len(changed), len(skipped)),
                  note="; ".join("%s: %s" % (m["screen"], m.get("detail") or
                                             m.get("skipped_reason"))
                                 for m in mutations)[:1500])

    # --- Step 4: S1 스냅샷 + 변경 반영 확인 -----------------------------
    s1 = snap.take(db, label="S1 (변경 후)")
    s1_path = snap.save(s1, os.path.join(work_dir, "snapshot_S1_%s.json" % stamp))
    r.attach(s1_path)
    diff_01 = snap.compare(s0, s1)
    r.assert_true(4, "변경이 실제로 DB에 반영되었는지 (S1 != S0)",
                  not diff_01["identical"],
                  expected="S0과 S1이 달라야 한다",
                  actual=snap.changed_names(diff_01),
                  note="이 검증이 없으면 변경이 한 건도 먹지 않아도 마지막 대조가 "
                       "통과해 헛된 PASS가 난다.")

    if not do_import:
        r.manual(5, "Import 복원", "사용자 지시로 Import는 수행하지 않았다. "
                                  "export_A와 S0/S1 스냅샷은 보관되어 있어 나중에 이어서 검증할 수 있다.",
                 expected="Import 후 S2 == S0", actual="미수행")
        return r.finalize()

    # --- Step 5: 안전 백업 + Import ------------------------------------
    try:
        safety = dbreset.backup(cfg.get("sql_server", r".\CHAMELEON"),
                                cfg.get("database", "DRF"),
                                prefix="PRE_SETTING_IMPORT",
                                note="before Setting Import in %s" % TC_ID)
    except dbreset.DbResetError as exc:
        r.add(5, "Import 전 안전 백업", "FAIL", "백업 생성", str(exc))
        return r.finalize()
    r.add(5, "Import 전 안전 백업", "PASS", "백업 생성", safety,
          note="Import는 DB 전체를 되돌리므로 실패 시 이 백업으로 복구한다.")

    ok, imp_note = S.import_settings(ui, made, confirm=True)
    r.assert_true(6, "Setting Import 실행", ok,
                  expected="Import 완료", actual=imp_note or ("성공" if ok else "실패"))

    # --- Step 6: 재기동 + S2 ------------------------------------------
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
    r.assert_true(7, "Import 후 뷰어 재기동 및 로그인", bool(relaunched),
                  expected="재기동 후 로그인 성공",
                  actual="성공" if relaunched else "실패")

    s2 = snap.take(db, label="S2 (Import 후)")
    s2_path = snap.save(s2, os.path.join(work_dir, "snapshot_S2_%s.json" % stamp))
    r.attach(s2_path)
    diff_02 = snap.compare(s0, s2)
    r.assert_true(8, "Export 당시 설정이 그대로 복원되었는지 (S2 == S0)",
                  diff_02["identical"],
                  expected="S0과 S2가 완전히 같아야 한다",
                  actual=snap.changed_names(diff_02),
                  note="복원되지 않은 항목이 있으면 위 목록이 그 항목이다.")

    if diff_02["out_of_scope_diffs"]:
        r.add(9, "판정 제외 항목(머신 단위 설정) 변화", "MANUAL",
              "Viewer.xml 등은 .vxs에 포함되지 않아 복원 대상이 아님",
              ", ".join(os.path.basename(p) for p in diff_02["out_of_scope_diffs"]),
              note="사용자 확인(2026-08-18): 복원되지 않는 것이 정상이므로 판정에서 제외한다.")

    return r.finalize()
