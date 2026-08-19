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
  python run.py report-sample       현재 환경 헤더만 넣은 빈 리포트 생성(형식 확인용)
  python run.py run-regression      체크리스트 전체 회귀(구현된 TC는 실행, 나머지는
                                     automation_scope.json 수준을 리포트에 그대로 표시)

설계/진행 상황 문서: `지식/[자동화 설계] VXvue Windows Update 호환성 자동화 설계.md`
"""

import argparse
import json
import os
import sys
from datetime import date

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
    results = reg_mod.run(cfg, ui_factory=lambda: _ready_ui(cfg),
                          approve_destructive=args.approve_destructive)
    env = None if args.no_env else result_mod.collect_env(cfg)
    paths = result_mod.write_reports(results, os.path.join(HERE, "Reports"), env=env)
    print("\n%-26s %-8s" % ("TC ID", "판정"))
    for r in results:
        print("%-26s %-8s %s" % (r.tc_id, r.verdict, r.title))
    total = dict((s, 0) for s in result_mod.STATUSES)
    for r in results:
        for k, v in r.counts.items():
            total[k] = total.get(k, 0) + v
    print("\n판정 합계: PASS %d / FAIL %d / MANUAL %d / SKIP %d / BLOCKED %d"
          % tuple(total[s] for s in result_mod.STATUSES))
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
    "xipl-license": cmd_xipl_license,
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
    p.add_argument("--no-import", action="store_true",
                   help="setting-export-import에서 파괴적인 Import 단계를 생략한다")
    p.add_argument("--approve-destructive", action="store_true",
                   help="run-regression 맨 마지막의 Setting Import(DB 전체 복원)까지 "
                        "실행한다. 지정하지 않으면 Export까지만 수행한다.")
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
