# -*- coding: utf-8 -*-
"""VXvue 자동화 CLI 진입점.

사용 예)
  python run.py env                 리포트 상단 헤더(Windows/패키지 정보) 출력
  python run.py preflight           실행 전 환경 점검 (NG가 있으면 종료코드 2)
  python run.py scope               TC별 자동화 수준(automation_scope.json) 표시
  python run.py ui-probe            현재 VXvue 화면의 컨트롤 트리 덤프
  python run.py ui-probe --save 파일  덤프를 파일로 저장
  python run.py mwl-list            공용 MWL 서버의 처방 목록
  python run.py mwl-ensure          VXvue 전용 DX 시험 처방을 오늘 날짜로 보장
  python run.py db-ae               Setting > DICOM 에 등록된 SCP 목록(DB 기준)
  python run.py xipl-license        XIPL.SERVER About의 영상처리 라이선스 4종 확인
  python run.py vxvue-license       VXvue 자체 라이선스(Demo/CAD/Live View) 확인
  python run.py tc02                TC02 MWL 조회 워크플로우(조회→촬영→Send→Close→DB)
  python run.py tc03                TC03 영상 조작(Interpolation + 툴 적용, 화면 변화 판정)
  python run.py tc05                TC05 DICOM 전송(Image + Dose SR 수신 객체 판정)
  python run.py tc07                TC07 DICOM Print(수신 필름 목록으로 판정)
  python run.py tc08                TC08 Study Export(E 드라이브 기준, #21049 회귀)
  python run.py report-sample       현재 환경 헤더만 넣은 빈 리포트 생성(형식 확인용)
  python run.py run-regression      체크리스트 전체 회귀. 구현된 TC는 실제로 실행하고,
                                     나머지는 automation_scope.json 수준을 리포트에
                                     그대로 표시한다(수행/미수행이 구분된다).
                                     선택 옵션:
                                       --reset-baseline       DB/폴더를 클린 baseline으로
                                                              되돌린 뒤 시작(파괴적)
                                       --approve-destructive  맨 마지막 Setting Import까지
                                                              실행(파괴적)
                                       --only TC_WindowsUpdate_14   특정 TC만
                                       --no-checklist         xlsx 결과 기록 생략

설계/진행 상황 문서: `지식/[자동화 설계] VXvue Windows Update 호환성 자동화 설계.md`
"""

import argparse
import json
import os
import sys
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 콘솔 코드페이지(CP949 등)가 못 담는 문자(예: em-dash '—')가 판정 문구에
# 섞이면 print()가 UnicodeEncodeError로 죽는다(실측: 2026-08-19). 리포트
# 파일은 이미 UTF-8로 저장된 뒤이므로, 콘솔 출력만 안전하게(대체 문자로)
# 내보내도록 한다 — 판정 자체를 놓치는 것보다 낫다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(errors="replace")
        except Exception:                              # noqa: BLE001
            pass

from core import preflight as preflight_mod          # noqa: E402
from core import result as result_mod                # noqa: E402
from core import ui as ui_mod                        # noqa: E402
from core.db import VXvueDb                          # noqa: E402
from core.mwl import MwlServer, make_dx_order        # noqa: E402


def load_config(path=None):
    p = path or os.path.join(HERE, "config.json")
    if not os.path.exists(p):
        p = os.path.join(HERE, "config.example.json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def load_scope():
    p = os.path.join(HERE, "automation_scope.json")
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# --- 명령 -------------------------------------------------------------
def cmd_env(cfg, args):
    env = result_mod.collect_env(cfg)
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


def cmd_preflight(cfg, args):
    items = preflight_mod.run(cfg)
    for i in items:
        print(i)
    bad = preflight_mod.blocking(items)
    if bad:
        print("\n실행 불가 항목 %d건 — 해결 전에는 UI 자동화를 시작하지 않는다." % len(bad))
        return 2
    print("\npreflight 통과")
    return 0


def cmd_scope(cfg, args):
    rows = load_scope()
    if not rows:
        print("automation_scope.json 이 없습니다.")
        return 1
    for r in rows:
        print("%-22s %-14s %s" % (r.get("tc_id"), r.get("level"), r.get("reason", "")[:120]))
    return 0


def cmd_ui_probe(cfg, args):
    name = (cfg.get("viewer") or {}).get("process_name", "VXvue")
    text = ui_mod.dump(name, max_depth=args.depth, visible_only=not args.all)
    if args.save:
        os.makedirs(os.path.dirname(os.path.abspath(args.save)) or ".", exist_ok=True)
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(text)
        print("저장: %s (%d줄)" % (args.save, text.count("\n") + 1))
    else:
        print(text)
    return 0


def _mwl(cfg):
    url = (cfg.get("dicom") or {}).get("mwl_server_url")
    if not url:
        raise SystemExit("config의 dicom.mwl_server_url 이 비어 있습니다.")
    return MwlServer(url)


def cmd_mwl_list(cfg, args):
    m = _mwl(cfg)
    running, badge = m.scp_running()
    print("SCP: %s (%s)" % ("RUNNING" if running else "STOPPED", badge))
    for it in m.list_items():
        print("%-20s %-24s %-3s %-10s %s" % (
            it.get("patient_id"), it.get("patient_name"), it.get("modality"),
            it.get("sps_start_date"), it.get("accession_number")))
    return 0


def cmd_mwl_ensure(cfg, args):
    """VXvue 전용 DX 시험 처방을 오늘 날짜로 보장한다.

    같은 patient_id의 처방이 오늘 것이면 재사용하고, 지난 날짜면 지우고 다시
    만든다. 다른 제품(Bellalun 등)의 처방은 건드리지 않는다.
    """
    td = cfg.get("test_data") or {}
    m = _mwl(cfg)
    today = args.date or date.today().isoformat()
    fields = make_dx_order(
        patient_id=td.get("mwl_patient_id", "VXVUE_MWL_DX_01"),
        patient_name=td.get("mwl_patient_name", "AUTO^VXVUE^^^"),
        accession_number=td.get("mwl_accession", "ACC_VX_AUTO_001"),
        sps_id=td.get("mwl_sps_id", "SPS_VX_AUTO_001"),
        station_ae=(cfg.get("dicom") or {}).get("local_ae_title", "VXVUE"),
        sps_start_date=today,
        sps_start_time=td.get("mwl_sps_start_time", "09:00"),
        procedure_id=td.get("mwl_procedure_id"),
        procedure_description=td.get("mwl_procedure_description", "CHEST"),
        sps_description=td.get("mwl_sps_description", "CHEST PA"),
        patient_sex=td.get("mwl_patient_sex", "M"),
        patient_birthdate=td.get("mwl_patient_birthdate", "1980-01-01"),
    )
    item, how, removed = m.ensure_order(today, **fields)
    print("%s (지난 처방 삭제 %d건)" % (how, removed))
    print(json.dumps(item, ensure_ascii=False, indent=2))
    return 0


def cmd_db_ae(cfg, args):
    db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
    rows = db.ae_list(args.kind)
    if not rows:
        print("등록된 SCP가 없습니다.")
        return 0
    print("%-6s %-16s %-16s %-16s %-6s %-10s" %
          ("Key", "Type", "Name", "AE Title", "Port", "RemoveSBSC"))
    for r in rows:
        print("%-6s %-16s %-16s %-16s %-6s %-10s" % (
            r.get("AEListKey"), r.get("Type"), r.get("Name"), r.get("Title"),
            r.get("Port"), r.get("RemoveSBSC")))
    return 0


def cmd_report_sample(cfg, args):
    """환경 헤더 형식 확인용. TC 결과는 비어 있고 헤더만 채워진 리포트를 만든다."""
    env = result_mod.collect_env(cfg)
    r = result_mod.TCResult("TC_WindowsUpdate_00", "리포트 헤더 형식 확인")
    r.manual(1, "환경 헤더 출력", "Windows/패키지 정보가 상단에 표시되는지 사람이 확인")
    r.finalize()
    paths = result_mod.write_reports([r], os.path.join(HERE, "Reports"), env=env)
    for k, v in paths.items():
        print("%-5s %s" % (k, v))
    return 0


def _print_result(result):
    """TCResult를 콘솔에 표로 출력한다(각 cmd_*가 같은 루프를 복사하던 것)."""
    print()
    print("판정: %s" % result.verdict)
    for c in result.checks:
        print("  [%s] Step %s %s" % (c.status, c.step, c.title))
        if str(c.expected):
            print("        기대: %s" % str(c.expected)[:400])
        if str(c.actual):
            print("        실제: %s" % str(c.actual)[:400])
        if c.note:
            print("        비고: %s" % str(c.note)[:400])
    print()
    print("합계: " + " / ".join("%s %d" % (k, v) for k, v in result.counts.items()))


def _ready_ui(cfg, login=True):
    """VXvue 드라이버를 준비한다(필요하면 기동·로그인까지)."""
    from core.ui import VXvueUi
    v = cfg.get("viewer") or {}
    ui = VXvueUi(v.get("process_name", "VXvue"))
    if not ui.pid:
        raise SystemExit("VXvue가 실행되어 있지 않습니다. 'python work/launch_login.py'로 먼저 기동하십시오.")
    if login:
        lg = v.get("login") or {}
        ui.ensure_ready(user_id=lg.get("id"), password=lg.get("password"))
    return ui


def cmd_xipl_license(cfg, args):
    """TC04 선행 조건: XIPL.SERVER About의 라이선스 4종 확인."""
    from core import xipl
    res = xipl.check_licenses()
    print("XIPL.SERVER 버전: %s" % (xipl.about_version() or "(확인 불가)"))
    print("판정: %s" % res["status"])
    if res["status"] == xipl.ABOUT_CLOSED:
        print(xipl.ABOUT_OPEN_HINT)
        return 2
    print("필요 라이선스 확인: %s" % ", ".join(res["found"]) or "(없음)")
    if res["missing"]:
        print("누락: %s" % ", ".join(res["missing"]))
    print("전체 등록 목록: %s" % ", ".join(res["all"]))
    return 0 if res["status"] == "OK" else 2


def cmd_vxvue_license(cfg, args):
    """VXvue 자체 라이선스 확인 — Setting > System > License.

    `xipl-license`(XIPL.SERVER About 창의 영상처리 라이선스 4종)와는 다른
    검증이다. 이쪽은 VXvue 본체/옵션 라이선스(Demo / CAD / Live View)를
    화면과 설치된 `.lic` 파일 양쪽에서 확인한다.
    """
    from core import license as license_mod
    ui = _ready_ui(cfg)
    result = license_mod.run_standalone(
        ui, cfg, evidence_dir=os.path.join(HERE, "Evidence"))
    env = None if args.no_env else result_mod.collect_env(cfg)
    paths = result_mod.write_reports([result], os.path.join(HERE, "Reports"), env=env)
    _print_result(result)
    for k, v in paths.items():
        print("%-5s %s" % (k, v))
    return 0 if result.verdict != "FAIL" else 2


def _run_tc_module(cfg, args, mod_name, **kwargs):
    """TC 모듈 하나를 실행하고 리포트까지 낸다(각 cmd_tcNN이 공유)."""
    import importlib
    mod = importlib.import_module(mod_name)
    ui = _ready_ui(cfg)
    result = mod.run(ui, cfg, **kwargs)
    env = None if args.no_env else result_mod.collect_env(cfg)
    paths = result_mod.write_reports([result], os.path.join(HERE, "Reports"), env=env)
    _print_result(result)
    for k, v in paths.items():
        print("%-5s %s" % (k, v))
    return 0 if result.verdict != "FAIL" else 2


def cmd_tc02(cfg, args):
    """TC02 MWL 조회 워크플로우 — 조회 → 촬영 → Close → DB 대조 → Send → 수신 확인."""
    return _run_tc_module(cfg, args, "tests.tc02_mwl_workflow",
                          do_send=not args.no_send,
                          map_procedure=args.map_procedure)


def cmd_tc03(cfg, args):
    """TC03 영상 조작 — Interpolation 변경 + Zoom/Pan/Rotation 툴 적용(화면 변화로 판정)."""
    return _run_tc_module(cfg, args, "tests.tc03_image_display",
                          do_acquire=not args.no_acquire,
                          map_procedure=args.map_procedure)


def cmd_tc05(cfg, args):
    """TC05 DICOM 전송 — Send Dose SR 확인 → 촬영 → Send → 수신 객체 종류 판정."""
    return _run_tc_module(cfg, args, "tests.tc05_dicom_send",
                          do_acquire=not args.no_acquire,
                          map_procedure=args.map_procedure)


def cmd_tc07(cfg, args):
    """TC07 DICOM Print — Print SCP 가동 확인 → 촬영 → Print → 수신 필름 확인."""
    return _run_tc_module(cfg, args, "tests.tc07_dicom_print",
                          do_acquire=not args.no_acquire,
                          map_procedure=args.map_procedure)


def cmd_tc08(cfg, args):
    """TC08 Study Export — E 드라이브로 Export → 산출물 DICOM 태그 검증 → 역방향 Import."""
    return _run_tc_module(cfg, args, "tests.tc08_study_export",
                          do_acquire=not args.no_acquire,
                          map_procedure=args.map_procedure)


def cmd_tc13(cfg, args):
    from tests import tc13_import_patient as tc13
    ui = _ready_ui(cfg)
    result = tc13.run(ui, cfg, with_folder_watch=getattr(args, "with_folder_watch", False))
    env = result_mod.collect_env(cfg) if not args.no_env else None
    paths = result_mod.write_reports([result], os.path.join(HERE, "Reports"), env=env)
    print("\n판정: %s" % result.verdict)
    for c in result.checks:
        print("  [%s] Step %s %s" % (c.status, c.step, c.title))
        if str(c.actual):
            print("        실제: %s" % c.actual)
        if c.note:
            print("        비고: %s" % c.note)
    for k, v in paths.items():
        print("%-5s %s" % (k, v))
    return 0 if result.verdict != "FAIL" else 2


def cmd_tc14(cfg, args):
    from tests import tc14_setting_display as tc14
    ui = _ready_ui(cfg)
    result = tc14.run(ui, cfg)
    env = result_mod.collect_env(cfg) if not args.no_env else None
    paths = result_mod.write_reports([result], os.path.join(HERE, "Reports"), env=env)
    print("\n판정: %s" % result.verdict)
    for c in result.checks:
        print("  [%s] Step %s %s" % (c.status, c.step, c.title))
        if str(c.actual):
            print("        실제: %s" % c.actual)
    for k, v in paths.items():
        print("%-5s %s" % (k, v))
    return 0 if result.verdict != "FAIL" else 2


def cmd_snapshot(cfg, args):
    """설정 스냅샷을 떠서 파일로 저장한다(Export/Import 회귀의 기준자료)."""
    from core import config_snapshot as snapshot_mod
    from core.db import VXvueDb
    from datetime import datetime as _dt
    db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
    snap = snapshot_mod.take(db, label=args.label or "manual")
    out = args.save or os.path.join(
        HERE, "work", "snapshot_%s.json" % _dt.now().strftime("%Y%m%d_%H%M%S"))
    snapshot_mod.save(snap, out)
    print("테이블 %d개 / 설정파일 %d개 / 데이터 건수 %s"
          % (len(snap["tables"]), len(snap["files"]), snap["data_row_counts"]))
    print(out)
    return 0


def cmd_snapshot_diff(cfg, args):
    """두 스냅샷 파일을 비교한다."""
    from core import config_snapshot as snapshot_mod
    if not args.a or not args.b:
        print("사용: python run.py snapshot-diff --a <파일> --b <파일>")
        return 1
    result = snapshot_mod.compare(snapshot_mod.load(args.a), snapshot_mod.load(args.b))
    print("동일 여부: %s" % result["identical"])
    print("요약: %s" % snapshot_mod.changed_names(result))
    for table, d in sorted(result["table_diffs"].items()):
        print("\n[%s] 행수 %s -> %s" % (table, d["count_a"], d["count_b"]))
        for row in d["only_in_a"][:3]:
            print("   - A만: %s" % row[:220])
        for row in d["only_in_b"][:3]:
            print("   + B만: %s" % row[:220])
    for path, (ha, hb) in sorted(result["file_diffs"].items()):
        print("\n[파일] %s\n   %s -> %s" % (path, ha, hb))
    if result["out_of_scope_diffs"]:
        print("\n[판정 제외] %s" % ", ".join(result["out_of_scope_diffs"]))
    return 0


def cmd_vxs_info(cfg, args):
    """`.vxs` export 파일의 구성을 보여준다(또는 두 파일을 비교)."""
    from core import vxs as vxs_mod
    if args.b:
        same, d = vxs_mod.identical(args.a, args.b)
        print("동일 여부: %s (같은 엔트리 %d개)" % (same, d["same"]))
        for kind in ("added", "removed", "changed"):
            if d[kind]:
                print("%s %d개: %s" % (kind, len(d[kind]), ", ".join(d[kind][:12])))
        return 0
    info = vxs_mod.summary(args.a)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_run_regression(cfg, args):
    """체크리스트 전체 회귀. automation_scope.json을 읽어 EXCLUDED는 건너뛰고,
    의존 순서대로 실행한 뒤 모든 TC 결과를 리포트 1건으로 합친다.
    아직 자동화 코드가 없는 TC는 automation_scope.json의 현재 수준(MANUAL/
    PARTIAL/BLOCKED/EXCLUDED)을 리포트 항목으로 그대로 옮겨 "실행하지
    않았음"이 리포트만 보고 구분되게 한다.
    """
    from core import regression as reg_mod
    only = set(args.only.split(",")) if getattr(args, "only", None) else None
    results = reg_mod.run(cfg, ui_factory=lambda: _ready_ui(cfg),
                          approve_destructive=args.approve_destructive,
                          reset_baseline=args.reset_baseline,
                          evidence_root=os.path.join(HERE, "Evidence"),
                          only=only)
    env = None if args.no_env else result_mod.collect_env(cfg)
    paths = result_mod.write_reports(results, os.path.join(HERE, "Reports"), env=env)

    print()
    print("%-28s %-8s %s" % ("TC ID", "판정", "제목"))
    print("-" * 100)
    for r in results:
        print("%-28s %-8s %s" % (r.tc_id, r.verdict, r.title))
        for c in r.checks:
            if c.status in (result_mod.FAIL, result_mod.BLOCKED):
                print("      [%s] Step %s %s" % (c.status, c.step, c.title))
                if str(c.actual):
                    print("            실제: %s" % str(c.actual)[:300])
    total = dict((s, 0) for s in result_mod.STATUSES)
    for r in results:
        for k, v in r.counts.items():
            total[k] = total.get(k, 0) + v
    print()
    print("판정 합계: PASS %d / FAIL %d / MANUAL %d / SKIP %d / BLOCKED %d"
          % tuple(total[s] for s in result_mod.STATUSES))

    # 체크리스트 원본(xlsx) 사본에 결과 열을 채운다. 원본은 읽기만 한다.
    if not args.no_checklist:
        try:
            from core import checklist as checklist_mod
            src = checklist_mod.source_path(cfg, root=HERE)
            if not src:
                print("체크리스트 원본을 찾지 못해 xlsx 기록을 건너뜁니다 "
                      "(config.json의 checklist_xlsx 또는 VXvue/ 루트 확인).")
            else:
                out = os.path.join(
                    HERE, "Reports",
                    "Checklist_Result_%s.xlsx" % datetime.now().strftime("%Y%m%d_%H%M%S"))
                info = checklist_mod.write_results(src, results, out_path=out, env=env)
                print("xlsx  %s (기록 %d행 / 미수행 %d행 / 추가 %d행, 시트 %s)"
                      % (info["path"], info["written"], info["not_run"],
                         info["extra"], info["sheet"]))
        except Exception as exc:                          # noqa: BLE001
            print("체크리스트 기록 실패: %s: %s" % (type(exc).__name__, exc))

    for k, v in paths.items():
        print("%-5s %s" % (k, v))
    return 2 if total[result_mod.FAIL] else 0


def cmd_setting_export_import(cfg, args):
    from tests import tc_setting_export_import as tc
    ui = _ready_ui(cfg)
    result = tc.run(ui, cfg, do_import=not args.no_import)
    env = None if args.no_env else result_mod.collect_env(cfg)
    paths = result_mod.write_reports([result], os.path.join(HERE, "Reports"), env=env)
    print("\n판정: %s" % result.verdict)
    for c in result.checks:
        print("  [%s] Step %s %s" % (c.status, c.step, c.title))
        if str(c.actual):
            print("        실제: %s" % str(c.actual)[:400])
        if c.note:
            print("        비고: %s" % str(c.note)[:400])
    for k, v in paths.items():
        print("%-5s %s" % (k, v))
    return 0 if result.verdict != "FAIL" else 2


COMMANDS = {
    "env": cmd_env,
    "tc02": cmd_tc02,
    "tc03": cmd_tc03,
    "tc05": cmd_tc05,
    "tc07": cmd_tc07,
    "tc08": cmd_tc08,
    "xipl-license": cmd_xipl_license,
    "vxvue-license": cmd_vxvue_license,
    "tc13": cmd_tc13,
    "tc14": cmd_tc14,
    "snapshot": cmd_snapshot,
    "snapshot-diff": cmd_snapshot_diff,
    "vxs-info": cmd_vxs_info,
    "setting-export-import": cmd_setting_export_import,
    "run-regression": cmd_run_regression,
    "preflight": cmd_preflight,
    "scope": cmd_scope,
    "ui-probe": cmd_ui_probe,
    "mwl-list": cmd_mwl_list,
    "mwl-ensure": cmd_mwl_ensure,
    "db-ae": cmd_db_ae,
    "report-sample": cmd_report_sample,
}


def main(argv=None):
    p = argparse.ArgumentParser(description="VXvue 자동화 CLI")
    p.add_argument("command", choices=sorted(COMMANDS))
    p.add_argument("--config", help="설정 파일 경로 (기본 config.json)")
    p.add_argument("--save", help="ui-probe 덤프 저장 경로")
    p.add_argument("--depth", type=int, default=5, help="ui-probe 탐색 깊이")
    p.add_argument("--all", action="store_true", help="ui-probe에 숨은 컨트롤도 포함")
    p.add_argument("--kind", help="db-ae 필터 (DICOM_MWL / DICOM_PRINT / DICOM_STORAGE)")
    p.add_argument("--date", help="mwl-ensure 기준 날짜 (YYYY-MM-DD, 기본 오늘)")
    p.add_argument("--no-env", action="store_true",
                   help="리포트 상단 환경 헤더 수집을 건너뛴다(ModelVersionChecker 실행 생략)")
    p.add_argument("--label", help="snapshot 라벨")
    p.add_argument("--a", help="비교 대상 A (snapshot-diff / vxs-info)")
    p.add_argument("--b", help="비교 대상 B (snapshot-diff / vxs-info)")
    p.add_argument("--map-procedure", nargs="?", const="Chest PA", default=None,
                   metavar="PROCEDURE",
                   help="MWL 처방의 Procedure Code를 지정한 Procedure(기본 'Chest PA')에 "
                        "매핑한다. **제품 설정을 바꾸는 조작이라 기본은 하지 않는다.** "
                        "매핑하지 않으면 Step이 등록되지 않아 (1) 촬영 직후 영상처리 "
                        "파라미터 오류가 뜨고 (2) 검사가 완료되지 않아 Database 목록에 "
                        "나타나지 않으며 (3) Database에서 Print/Export 대상을 고를 수 "
                        "없다(2026-08-19 실측). TC04/05/07/08의 정상 흐름을 검증할 때 "
                        "지정한다.")
    p.add_argument("--no-acquire", action="store_true",
                   help="tc05/tc07/tc08에서 촬영 단계를 생략하고 이미 열려 있는 "
                        "영상을 사용한다(반복 디버깅용).")
    p.add_argument("--no-send", action="store_true",
                   help="tc02에서 마지막 DICOM Send 단계를 생략한다(조회·촬영·DB "
                        "대조까지만 수행).")
    p.add_argument("--no-import", action="store_true",
                   help="setting-export-import에서 파괴적인 Import 단계를 생략한다")
    p.add_argument("--approve-destructive", action="store_true",
                   help="run-regression 맨 마지막의 Setting Import(DB 전체 복원)까지 "
                        "실행한다. 지정하지 않으면 Export까지만 수행한다.")
    p.add_argument("--reset-baseline", action="store_true",
                   help="run-regression 시작 시 DB와 data_dir 폴더를 baseline "
                        "(config.json의 baseline.db_backup / folder_backup) 상태로 "
                        "되돌린다. **파괴적 조작** — 현재 DB의 환자·검사·설정이 전부 "
                        "사라진다. 라이선스와 운영 로그는 왕복 백업으로 보존한다. "
                        "지정하지 않으면 현재 DB 상태 위에서 회귀를 수행하고 그 사실을 "
                        "리포트에 SKIP으로 남긴다.")
    p.add_argument("--no-checklist", action="store_true",
                   help="run-regression 결과를 체크리스트 xlsx 사본에 기록하는 단계를 "
                        "생략한다(원본은 어떤 경우에도 수정하지 않는다).")
    p.add_argument("--only",
                   help="run-regression에서 특정 TC만 실행한다(쉼표 구분, 디버깅용). "
                        "예: --only TC_WindowsUpdate_14")
    p.add_argument("--with-folder-watch", action="store_true",
                   help="tc13에서 'Import Patient Information From a Specific Folder' "
                        "기능(Import Patient Order와 상호 배타)까지 켜서 확인한다. "
                        "아직 라이브 미검증 경로라 기본은 끔(경고: 이 옵션 없이도 "
                        "관련 컨트롤 존재 여부는 보고된다).")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    return COMMANDS[args.command](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
