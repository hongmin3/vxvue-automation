# -*- coding: utf-8 -*-
r"""체크리스트 전체 회귀 러너.

## 실행 순서 (NEXT_TASK.md "최우선" 큐 그대로)

```
Phase 0  선행조건       preflight -> mwl-ensure -> xipl-license
Phase 1  baseline 초기화 (기본 수행, 파괴적; --no-reset-baseline으로만 생략)
           라이선스 파일 백업 -> 로그 백업 -> 뷰어 종료 확인
           -> dbreset.restore()      (DB를 baseline .bak으로)
           -> dbreset.restore_folder() (data_dir를 baseline 폴더로)
           -> restore_license_files() / restore_log_files()  (되돌린 것 복구)
           -> 뷰어 재기동 + 로그인
Phase 2  라이선스 확인   core/license.check()  (Setting > System > License)
Phase 3  서버 연동       dicom_settings.ensure_registered()  (MWL/Storage/Print + Echo)
Phase 4  TC 실행         구현된 TC -> (그 외는 automation_scope 수준 표시)
리포트                   Reports/*.html|json + 체크리스트 xlsx 사본
```

## 이 러너의 핵심 요구사항

**"이번에 실제로 수행했다"와 "아직 자동화 코드가 없어 수행하지 않았다"를
리포트만 보고 구분할 수 있어야 한다.** 그래서 자동화 코드가 없는 TC는 추정
PASS를 내지 않고 `automation_scope.json`에 기록된 수준(MANUAL/PARTIAL/BLOCKED/
EXCLUDED)과 그 판단 근거를 리포트 항목으로 그대로 옮긴다.

## 파괴적 조작 정책

전체 회귀의 baseline 초기화는 사용자 확정 지시(2026-08-25)에 따라 기본으로
수행한다. 임시 디버깅에서만 `--no-reset-baseline`으로 명시적으로 생략하며,
생략 사실은 리포트에 SKIP으로 남긴다. Setting Import는 별도 명령으로 분리한다.

- 기본 동작(`--reset-baseline`은 호환용 별칭): Phase 1. DB와 `data_dir` 폴더를 2026-08-18 클린 설치
  시점으로 되돌린다. 지금 DB에 있는 환자·검사·설정이 전부 사라진다.
- `--no-reset-baseline` : 임시 디버깅에서만 Phase 1을 생략한다.
- `--approve-destructive` : Phase 5의 실제 Import. DB 전체가 마지막 Export
  시점으로 복원된다.

Phase 1을 켜면 그 안에서 뷰어를 내리므로, 복원 뒤 **반드시 다시 띄우고
로그인까지 확인**한다(Bellalun에서 서비스를 내려놓고 다시 올리지 않아 이후
TC가 연쇄 실패한 사례가 있다 — `Bellalun Viewer/auto/PORTABILITY_AUDIT.md`).

## 실패 격리

한 Phase가 예외로 죽어도 나머지를 계속 실행한다. 예외는 그 Phase의 FAIL로
기록하고, 뷰어 기동/화면 진입 실패에는 그 시점 메모리 여유
(`preflight.memory_pressure()`)를 함께 남긴다 — 이 시험 PC는 물리 메모리
여유가 항상 기준 아래라(사용자 지시로 차단하지 않음) 실패 원인이 자원 부족인지
제품 문제인지 사후에 구분할 근거가 필요하다.

**baseline 초기화, 필수 라이선스, DICOM 서버 연결은 중단 게이트다.** 이 셋 중
하나라도 실패하면 뒤 Phase를 실행하지 않는다. 초기 상태·기능 활성화·서버 연결이
보장되지 않은 상태의 연쇄 실패를 제품 결함과 섞어 보고하지 않기 위해서다.

특히 필수 DICOM 서버 등록·Echo(Phase 3)는 MWL,
Storage, Print 중 하나가 끊긴 상태는 전체 회귀의 선행조건 실패다. 그 상태로
Phase 4를 계속 돌리면 뒤 TC가 같은 환경 원인으로 줄줄이 실패하고, 제품 결함과
환경 결함을 섞어 보고하게 된다. 그래서 `_run_dicom_registration()`이
`servers_ok=False`를 돌려주면 Phase 4를 건너뛰고 구현 여부와 무관하게 **모든
TC를 `_downstream_fail()`로 즉시 FAIL 처리한 뒤 회귀를 끝낸다.**
"""

import os
import time
import traceback
from datetime import date, datetime

from . import crash as crash_mod
from . import preflight as preflight_mod
from . import result as result_mod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# automation_scope.json 의 level 문자열 -> 리포트 판정.
# "PARTIAL"과 "FULL 가능성 높음"은 코드가 없으면 MANUAL로 남긴다(추정 PASS 금지).
_LEVEL_TO_VERDICT_WHEN_NOT_IMPLEMENTED = {
    "EXCLUDED": result_mod.SKIP,
    "SKIP": result_mod.SKIP,
    "MANUAL": result_mod.MANUAL,
    "BLOCKED": result_mod.BLOCKED,
    "PARTIAL": result_mod.MANUAL,
    "FULL 가능성 높음": result_mod.MANUAL,
}

# 실제로 실행하는 TC — tc_id -> (모듈 경로, run() 키워드 인자)
#
# **파일명은 TC ID와 맵핑한다**(사용자 지시, 2026-08-19): `tests/tcNN_*.py` 의
# `NN`이 `TC_WindowsUpdate_NN`의 번호다. 체크리스트에 없는 자체 TC만
# 번호 대신 이름을 쓴다(`tc_setting_export_import.py` ->
# `TC_Setting_ExportImport`).
IMPLEMENTED = {
    "TC_WindowsUpdate_02": ("tests.tc02_mwl_workflow", {}),
    "TC_WindowsUpdate_03": ("tests.tc03_image_display", {}),
    "TC_WindowsUpdate_04": ("tests.tc04_image_processing", {}),
    "TC_WindowsUpdate_05": ("tests.tc05_dicom_send", {}),
    "TC_WindowsUpdate_06": ("tests.tc06_extra_tool", {}),
    "TC_WindowsUpdate_07": ("tests.tc07_dicom_print", {}),
    "TC_WindowsUpdate_08": ("tests.tc08_study_export", {}),
    "TC_WindowsUpdate_11": ("tests.tc11_ai_analysis", {}),
    "TC_WindowsUpdate_12": ("tests.tc12_camera_live_view", {}),
    "TC_WindowsUpdate_13": ("tests.tc13_import_patient", {}),
    "TC_WindowsUpdate_14": ("tests.tc14_setting_display", {}),
}


# 실행 순서는 **TC 번호순(01, 02, 03 …)이다**(사용자 지시, 2026-08-20).
#
# 이렇게 두면 리포트 순서가 체크리스트 행 순서와 같아져 대조하기 쉽다. 예전에는
# 촬영이 필요한 TC를 앞으로 묶고 Setting을 건드리는 TC를 뒤로 뺐는데, 그럴 필요가
# 없다 — **각 TC가 자기 시작 상태를 스스로 정리하고**(열린 검사 닫기, Exposure
# 레이아웃 복귀), 설정을 바꾸는 TC는 끝에서 원래 값으로 되돌린다(TC03의
# Interpolation Mode). 그래서 순서가 판정을 바꾸지 않는다.
def _tc_sort_key(tc_id):
    """`TC_WindowsUpdate_07` -> (0, 7). 번호가 없는 자체 TC는 뒤로 보낸다."""
    import re
    m = re.search(r"_(\d+)$", tc_id or "")
    return (0, int(m.group(1))) if m else (1, 0, tc_id)


def run_order(tc_ids):
    """번호순 실행 순서. 번호 없는 항목은 이름순으로 뒤에 붙인다."""
    return sorted(tc_ids, key=_tc_sort_key)


TC_LABELS = {
    "TC_WindowsUpdate_01": "TC01 패키지 설치 확인",
    "TC_WindowsUpdate_02": "TC02 MWL 조회 워크플로우",
    "TC_WindowsUpdate_03": "TC03 영상 조작(표시/도구)",
    "TC_WindowsUpdate_04": "TC04 Image Processing(XIPL)",
    "TC_WindowsUpdate_05": "TC05 DICOM 전송",
    "TC_WindowsUpdate_06": "TC06 Extra Tool 전송(SBSC)",
    "TC_WindowsUpdate_07": "TC07 DICOM Print",
    "TC_WindowsUpdate_08": "TC08 Study Export(CD/USB)",
    "TC_WindowsUpdate_09": "TC09 (재부팅 필요 — 자동화 SKIP)",
    "TC_WindowsUpdate_10": "TC10 (범위 제외)",
    "TC_WindowsUpdate_11": "TC11 AI 분석(CAD)",
    "TC_WindowsUpdate_12": "TC12 카메라/Live View",
    "TC_WindowsUpdate_13": "TC13 Import Patient",
    "TC_WindowsUpdate_14": "TC14 Setting 전체 화면",
    "TC_WindowsUpdate_15": "TC15 (범위 제외)",
}


def _load_scope():
    p = os.path.join(HERE, "automation_scope.json")
    if not os.path.exists(p):
        return []
    import json
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg), flush=True)


def _fail_from_exception(r, step, title, exc, cfg):
    r.add(step, "예외 발생 — %s" % title, result_mod.FAIL,
          actual="%s: %s" % (type(exc).__name__, exc),
          note=(traceback.format_exc(limit=3).strip()[-600:] + " | "
                + preflight_mod.memory_pressure(cfg)))


# --- Phase 0: 선행조건 -------------------------------------------------
def _run_precondition(cfg):
    """preflight + mwl-ensure + xipl-license 를 한 TCResult로 묶는다.

    반환: (TCResult, blocked). blocked=True면 UI 자동화를 시작하지 않는다.
    메모리 부족은 WARN이므로 blocked에 들지 않는다(`core/preflight.py` docstring).
    """
    r = result_mod.TCResult("Precondition", "회귀 실행 전 환경/선행조건 점검")
    items = preflight_mod.run(cfg)
    for i, it in enumerate(items, 1):
        status = (result_mod.PASS if it.status == preflight_mod.OK else
                  result_mod.FAIL if it.status == preflight_mod.NG else
                  result_mod.MANUAL)
        r.add(i, it.name, status, expected=it.expected, actual=it.actual, note=it.note)
    step = len(items) + 1

    bad = preflight_mod.blocking(items)
    if bad:
        r.add(step, "mwl-ensure / xipl-license", result_mod.SKIP,
              note="preflight NG(%s)로 인해 건너뜀"
                   % ", ".join(i.name for i in bad))
        r.finalize()
        return r, True

    try:
        from .mwl import MwlServer, make_dx_order
        td = cfg.get("test_data") or {}
        url = (cfg.get("dicom") or {}).get("mwl_server_url")
        if not url:
            r.add(step, "mwl-ensure", result_mod.MANUAL,
                  note="config의 dicom.mwl_server_url 이 비어 있어 건너뜀")
        else:
            m = MwlServer(url)
            # 회귀의 MWL 단계가 **이 실행의 처방을 새로 뽑는 시점**이다
            # (`core/testdata.py`). 실행마다 Patient ID·Acc. No.·성별·생년월일이
            # 달라지므로, 뒤따르는 TC들이 "이번 실행의 스터디"를 목록에서 유일하게
            # 지목할 수 있다. 지난 실행의 처방은 접두로 골라 지운다(사용자 지시).
            from . import testdata
            fresh = testdata.new_for_mwl(cfg)
            td = cfg.get("test_data") or {}
            pruned = testdata.prune_auto_orders(
                m, keep_patient_id=td.get("mwl_patient_id"))
            fields = make_dx_order(
                patient_id=td.get("mwl_patient_id", "VXVUE_MWL_DX_01"),
                patient_name=td.get("mwl_patient_name", "AUTO^VXVUE^^^"),
                accession_number=td.get("mwl_accession", "ACC_VX_AUTO_001"),
                sps_id=td.get("mwl_sps_id", "SPS_VX_AUTO_001"),
                station_ae=(cfg.get("dicom") or {}).get("local_ae_title", "VXVUE"),
                sps_start_date=date.today().isoformat(),
                sps_start_time=td.get("mwl_sps_start_time", "09:00"),
                procedure_id=td.get("mwl_procedure_id"),
                procedure_description=td.get("mwl_procedure_description", "CHEST"),
                sps_description=td.get("mwl_sps_description", "CHEST PA"),
                patient_sex=td.get("mwl_patient_sex", "M"),
                patient_birthdate=td.get("mwl_patient_birthdate", "1980-01-01"),
            )
            item, how, removed = m.ensure_order(date.today().isoformat(), **fields)
            r.add(step, "mwl-ensure (당일 DX 처방 보장)", result_mod.PASS,
                  expected="오늘 날짜의 VXvue 전용 DX 처방 1건",
                  actual="%s / %s / 지난 처방 삭제 %d건(당일 %d건)"
                         % (how, testdata.describe(cfg), pruned["deleted"],
                            removed),
                  note="이 실행의 시험 처방은 여기서 새로 뽑는다 — Patient ID에 "
                       "실행 시각을 각인하고 성별·생년월일은 그 각인을 시드로 "
                       "정한다(사용자 지시, 2026-08-21: 같은 ID가 쌓여 import "
                       "검증이 불가능했다). 지운 처방: %s / 다른 제품 처방은 "
                       "건드리지 않았다: %s"
                       % (pruned["deleted_ids"], pruned["kept"]))
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, step, "mwl-ensure", exc, cfg)
    step += 1

    try:
        from . import xipl
        res = xipl.check_licenses()
        status = (result_mod.PASS if res["status"] == "OK" else
                  result_mod.MANUAL if res["status"] == xipl.ABOUT_CLOSED else
                  result_mod.FAIL)
        r.add(step, "xipl-license (XIPL 영상처리 라이선스 4종)", status,
              expected="필요 라이선스 전체 등록",
              actual=", ".join(res.get("found", [])),
              note=(xipl.ABOUT_OPEN_HINT if status == result_mod.MANUAL else
                    ("누락: %s" % ", ".join(res["missing"]) if res.get("missing") else ""))
                   + " | 이것은 XIPL.SERVER About 창의 라이선스다. VXvue 본체"
                     " 라이선스(Demo/CAD/Live View)는 VXvue_License 항목 참고.")
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, step, "xipl-license", exc, cfg)

    r.finalize()
    return r, False


# --- Phase 1: baseline 초기화 ------------------------------------------
def _run_baseline_reset(cfg, approved):
    """DB/폴더를 baseline으로 되돌리고 라이선스·로그는 그대로 지킨다."""
    from . import dbreset

    r = result_mod.TCResult("Baseline_Reset",
                            "DB/폴더/라이선스 클린 초기화 (baseline 복원)")
    base = cfg.get("baseline") or {}
    bak = base.get("db_backup")
    folder = base.get("folder_backup")
    data_dir = cfg.get("data_dir")

    if not approved:
        r.add(1, "baseline 복원", result_mod.SKIP,
              expected="DB=%s / 폴더=%s" % (bak, folder),
              note="--no-reset-baseline로 지정해 초기화를 명시적으로 건너뛰었다. 이 회귀는 "
                   "**현재 DB 상태 위에서** 수행됐다 — 클린 상태 전제가 필요한 판정"
                   "(예: 목록 건수 비교)은 이 사실을 감안해 읽을 것.")
        r.finalize()
        return r, False

    if not (bak and folder and data_dir):
        r.add(1, "baseline 설정 확인", result_mod.FAIL,
              expected="config.json의 baseline.db_backup / baseline.folder_backup / data_dir",
              actual="db_backup=%r folder_backup=%r data_dir=%r" % (bak, folder, data_dir))
        r.finalize()
        return r, False

    work = os.path.join(HERE, "work", "license_roundtrip")
    log_work = os.path.join(HERE, "work", "log_roundtrip")
    step = 1

    # 1) 지금 적용된 라이선스/로그를 왕복용으로 뜬다.
    try:
        saved = dbreset.backup_license_files(data_dir, work)
        r.add(step, "라이선스 파일 백업(왕복용)",
              result_mod.PASS if saved else result_mod.FAIL,
              expected="현재 적용된 .lic 파일 보관",
              actual="%d개: %s" % (len(saved), ", ".join(os.path.basename(p) for p in saved)),
              note="라이선스는 하드웨어 키에 묶여 있어 기준 백업/git에 값으로 남기지 "
                   "않는다(사용자 지시). 되돌리기 직전에 떴다가 되돌린 뒤 다시 "
                   "덮어쓰는 왕복 전용이다.")
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, step, "라이선스 파일 백업", exc, cfg)
        r.finalize()
        return r, False
    step += 1

    try:
        log_saved = dbreset.backup_log_files(data_dir, log_work)
        r.add(step, "운영 로그 백업(왕복용)",
              result_mod.PASS if log_saved else result_mod.SKIP,
              expected="%s\\log 보관" % data_dir,
              actual=log_saved or "log 폴더가 없어 건너뜀",
              note="사용자 지시(2026-08-19) — 회귀 실행마다 운영 로그가 사라지지 "
                   "않게 한다. restore_folder()도 log/를 제외하지만 이중으로 지킨다.")
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, step, "운영 로그 백업", exc, cfg)
    step += 1

    # 2) DB 복원 (내부에서 뷰어 프로세스를 내리고 완전히 꺼졌는지 확인한다)
    try:
        _log("DB 복원 시작: %s" % bak)
        info = dbreset.restore(bak, server=cfg.get("sql_server", r".\CHAMELEON"),
                               database=cfg.get("database", "DRF"), confirm=True)
        r.add(step, "DB 복원 (baseline .bak)", result_mod.PASS,
              expected=os.path.basename(bak),
              actual="안전 백업=%s / 종료한 프로세스=%s"
                     % (os.path.basename(str(info.get("safety_backup"))),
                        ", ".join(info.get("stopped") or []) or "없음"),
              note="복원 전 PRERESTORE 안전 백업을 자동으로 뜬다.")
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, step, "DB 복원", exc, cfg)
        r.finalize()
        return r, False
    step += 1

    # 3) 폴더 복원
    try:
        _log("폴더 복원 시작: %s -> %s" % (folder, data_dir))
        finfo = dbreset.restore_folder(folder, data_dir, confirm=True)
        rc = finfo.get("returncode")
        # robocopy 종료코드는 0~7이 성공(8 이상이 실패)이다.
        r.add(step, "폴더 복원 (baseline 폴더)",
              result_mod.PASS if rc is not None and rc < 8 else result_mod.FAIL,
              expected="robocopy 종료코드 < 8",
              actual="종료코드=%s" % rc,
              note="Bak/(DB 백업 이력)과 log/(운영 로그)는 제외한다. DB 파일"
                   "(*.mdf/*.ldf)도 제외 — SQL Server가 점유 중이라 파일 복사로 "
                   "다루면 안 되고 위 DB 복원이 담당한다.")
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, step, "폴더 복원", exc, cfg)
    step += 1

    # 4) 라이선스/로그 되돌리기
    try:
        restored = dbreset.restore_license_files(data_dir, work)
        r.add(step, "라이선스 파일 복원", result_mod.PASS if restored else result_mod.FAIL,
              expected="백업해 둔 .lic 전부 제자리로",
              actual="%d개: %s" % (len(restored),
                                  ", ".join(os.path.basename(p) for p in restored)))
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, step, "라이선스 파일 복원", exc, cfg)
    step += 1

    try:
        dbreset.restore_log_files(data_dir, log_work)
        r.add(step, "운영 로그 복원", result_mod.PASS)
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, step, "운영 로그 복원", exc, cfg)

    r.finalize()
    return r, True


# --- Phase 2/3 ---------------------------------------------------------
def _run_license_check(cfg, ui, evidence_dir):
    from . import license as license_mod
    r = result_mod.TCResult("VXvue_License",
                            "VXvue 자체 라이선스 확인 (Setting > System > License)")
    try:
        license_mod.check(ui, cfg, r, first_step=1, evidence_dir=evidence_dir)
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, len(r.checks) + 1, "라이선스 확인", exc, cfg)
    return r.finalize()


def _run_dicom_registration(cfg, ui):
    """반환: (TCResult, servers_ok).

    config에 등록된 MWL/Storage/Print 중 하나라도 등록 또는 Echo가 실패하거나,
    처리 결과에서 누락되면 ``servers_ok=False``다. 전체 회귀의 필수 연결
    선행조건이므로 ``run()``이 Phase 4를 시작하지 않는다.
    """
    from . import dicom_settings
    from .db import VXvueDb

    r = result_mod.TCResult("DICOM_Servers",
                            "DICOM SCP 연동 확인·구성 (MWL / Storage / Print)")
    specs = (cfg.get("dicom") or {}).get("servers_to_register") or []
    if not specs:
        r.add(1, "등록 대상 서버", result_mod.SKIP,
              note="config.json의 dicom.servers_to_register가 비어 있다.")
        return r.finalize(), True
    servers_ok = True
    try:
        db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
        rows = dicom_settings.ensure_registered(ui, cfg, db)
        for i, row in enumerate(rows, 1):
            ok = row.get("registered") and row.get("echo_ok")
            if not ok:
                servers_ok = False
            r.add(i, "%s SCP: %s" % (row.get("kind"), row.get("name")),
                  result_mod.PASS if ok else result_mod.FAIL,
                  expected="등록 확인 + Echo 성공",
                  actual="등록=%s / Echo=%s" % (row.get("registered"), row.get("echo_ok")),
                  note=row.get("note", ""))
        missing = len(specs) - len(rows)
        if missing > 0:
            servers_ok = False
            r.add(len(rows) + 1, "등록 대상 누락", result_mod.FAIL,
                  expected="%d건 처리" % len(specs), actual="%d건 처리" % len(rows))
    except Exception as exc:                              # noqa: BLE001
        _fail_from_exception(r, len(r.checks) + 1, "DICOM 서버 등록", exc, cfg)
        servers_ok = False
    return r.finalize(), servers_ok


# --- Phase 4: TC 실행 --------------------------------------------------
# --- 짧은 회귀(`--quick`) -----------------------------------------------
#
# ## 먼저: 시간을 잡아먹던 것은 대기가 아니었다
#
# 전체 회귀는 실측 71분(2026-08-19)이었다. 프로파일링(2026-08-20) 결과 원인은
# 제품을 기다리는 시간이 아니라 **자동화가 스스로 만든 낭비**였다.
#
# 1. `ui.children()`이 `EnumChildWindows`(이미 모든 자손을 열거한다) 결과마다
#    다시 재귀해, 같은 창을 최대 120번 중복 열거했다. TC 하나에서 85만 번
#    호출됐다. 한 번만 열거하도록 고쳐 **depth=4 기준 6.10초 → 0.28초**.
# 2. 클릭 뒤 안정화를 `time.sleep(상한)`으로 무조건 기다렸다. 화면이 준비됐는지
#    물어보고 일찍 끝내도록 고쳤다(`ui.VXvueUi.wait_settle`).
#
# 두 수정으로 TC03이 **143.8초 → 34.5초(4.2배)**가 됐고 판정은 그대로다.
# 범위를 줄이지 않고 얻은 것이므로 이쪽이 먼저다.
#
# ## 그래도 남는 것 — 범위를 줄이는 선택
#
# 위 수정 뒤에도 반복이 남는다. TC02/03/04/05/07/08이 각자 MWL 조회 → Step
# 등록 → 촬영을 다시 하고, TC14가 Setting 55개 화면을 순회한다. `--quick`은
# 그 **범위를 줄인다** — 빨라지는 대신 확인하는 것이 줄어든다.
#
# **무엇을 줄였는지는 반드시 리포트에 남긴다.** 짧은 회귀는 빠른 이상 감지
# 용도이고, 체크리스트에 기록할 정식 판정은 전체 회귀로 받아야 한다.
QUICK_KWARGS = {
    # TC02는 촬영을 재사용할 수 없다 — MWL 조회부터 촬영·전송·Close·DB 확인까지가
    # 이 TC 자체의 검증 대상이다. 그래서 여기서 촬영하고 뒤 TC가 그것을 쓴다.
    "TC_WindowsUpdate_03": {"do_acquire": False},
    "TC_WindowsUpdate_04": {"do_acquire": False},
    "TC_WindowsUpdate_05": {"do_acquire": False},
    "TC_WindowsUpdate_07": {"do_acquire": False},
    "TC_WindowsUpdate_08": {"do_acquire": False},
    "TC_WindowsUpdate_11": {"do_acquire": False},
    "TC_WindowsUpdate_12": {"do_acquire": False},
    "TC_WindowsUpdate_14": {"sample": True},
}


def _quick_notice(applied):
    """짧은 회귀가 무엇을 줄였는지 리포트에 남긴다."""
    r = result_mod.TCResult("Quick_Mode", "짧은 회귀 — 축소한 범위")
    r.add(1, "촬영 재사용", result_mod.MANUAL,
          expected="각 TC가 스스로 촬영해 자기 영상으로 검증(전체 회귀)",
          actual="TC02에서 1회만 촬영하고 %s는 그 영상을 재사용"
                 % ", ".join(sorted(k.replace("TC_WindowsUpdate_", "TC")
                                    for k in applied if k in QUICK_KWARGS
                                    and "do_acquire" in QUICK_KWARGS[k])),
          note="**각 TC가 촬영을 독립적으로 수행하는지는 확인하지 않았다.** "
               "촬영 경로 자체의 회귀는 TC02 결과로만 담보된다. 전송·인쇄·Export "
               "대상 영상이 존재하는지는 그대로 확인한다.")
    r.add(2, "Setting 화면 순회 범위", result_mod.MANUAL,
          expected="전 화면 순회 후 기준 대조(전체 회귀)",
          actual="TC14를 대분류별 첫 소분류만 보는 표본 모드로 실행",
          note="건너뛴 화면 목록은 TC14 결과의 해당 항목에 있다.")
    r.add(3, "정식 판정 경로", result_mod.MANUAL,
          expected="체크리스트 기록은 전체 회귀 결과로 한다",
          actual="이번 실행은 `--quick`(빠른 이상 감지용)",
          note="정식 판정: `python run.py run-regression`(baseline 기본 복원). "
               "짧은 회귀에서 FAIL이 나오면 그것은 "
               "실제 결함일 가능성이 높지만, **PASS는 전체 회귀의 PASS를 "
               "대신하지 못한다.**")
    return r.finalize()


def _placeholder(tc_id, scope_by_id, override_note=None):
    row = scope_by_id.get(tc_id) or {}
    level = row.get("level", "확인 필요")
    reason = row.get("reason", "")
    r = result_mod.TCResult(tc_id, TC_LABELS.get(tc_id, tc_id))
    verdict = _LEVEL_TO_VERDICT_WHEN_NOT_IMPLEMENTED.get(level, result_mod.MANUAL)
    note = override_note or reason
    if level in ("PARTIAL", "FULL 가능성 높음") and not override_note:
        note = (reason + " | automation_scope.json 상 수준은 '%s'이지만 이를 실제로 "
                "수행하는 자동화 코드가 아직 없다. 수동으로 수행하거나 다음 "
                "세션에서 구현해야 한다." % level)
    r.add(1, "automation_scope.json 기준 현재 수준: %s" % level, verdict,
          expected="자동 수행", actual="이번 회귀에서 수행하지 않음", note=note)
    r.finalize()
    return r


def _downstream_fail(tc_id, reason, prerequisite="필수 선행조건"):
    """상류 단계(DICOM 서버 등록 등)가 실패해 이 TC를 아예 실행하지 않고
    강제로 FAIL 처리할 때 쓴다(사용자 지시, 2026-08-25).

    `_placeholder()`와 달리 `automation_scope.json`의 수준(MANUAL/PARTIAL 등)을
    보지 않는다 — "아직 자동화가 없다"가 아니라 "자동화는 있지만 그 앞
    단계가 실패해서 의미 있게 실행할 수 없었다"는 다른 상황이라, 애매한
    MANUAL로 묻히지 않고 항상 FAIL로 남긴다.
    """
    r = result_mod.TCResult(tc_id, TC_LABELS.get(tc_id, tc_id))
    r.add(1, "상류 단계 실패로 실행 안 함", result_mod.FAIL,
          expected="%s 성공 후 정상 실행" % prerequisite,
          actual="실행하지 않음", note=reason)
    r.finalize()
    return r


def _check_crash(tc_id, cfg, ui, label, started, r):
    """`mod.run()`이 끝난 뒤 VXvue가 실제로 죽었는지 확인하고, 죽었으면 그
    TC를 FAIL로 확정한 뒤 다음 TC를 위해 재기동한다(사용자 지시, 2026-08-24).

    `ui.pid`는 매번 살아있는지 다시 확인하므로(`VXvueUi.pid` 프로퍼티) 그냥
    `None`이 됐다는 사실은 알 수 있지만, 그 이전 TC 모듈 코드는 각자 짜여진
    방식대로(예외로 죽거나, "화면을 못 찾음"류의 MANUAL로 조용히) 반응했을
    뿐 **"VXvue가 실제로 죽었다"는 진짜 원인을 리포트에 남기지 않는다.**
    그래서 여기서 명시적으로 확인해 FAIL Step을 하나 추가한다 — `TCResult.
    verdict`는 FAIL이 하나라도 있으면 전체가 FAIL이 되므로(`core/result.py`),
    이미 기록된 Step들이 우연히 PASS/MANUAL이었어도 이 TC의 최종 판정은
    FAIL로 확정된다.
    """
    if ui.pid:
        return r
    dumps = crash_mod.find_dumps(ui.process_name, since=started)
    if dumps:
        actual = "크래시 덤프 확인: %s" % dumps[-1]
        note = ("VXvue가 이 TC 실행 중 실제로 크래시했다(Windows Error Reporting이 "
                "%s에 남긴 덤프로 확인) — 그 이후 기록된 Step 결과는 신뢰할 수 없다. "
                "다음 TC를 위해 재기동·재로그인한다." % crash_mod.CRASH_DUMP_DIR)
    else:
        actual = "프로세스가 사라졌지만 크래시 덤프는 없음"
        note = ("원인 불명 — 사람/다른 프로세스의 종료(taskkill 등)였을 가능성도 있어 "
                "크래시로 단정하지 않지만, 이 TC가 의도대로 끝나지 못한 것은 분명하다. "
                "다음 TC를 위해 재기동·재로그인한다.")
    r.add(len(r.checks) + 1, "VXvue 실행 중 종료 감지", result_mod.FAIL,
          expected="시험 도중 VXvue가 종료되지 않아야 한다", actual=actual, note=note)
    r.finalize(r.completed)
    _log("%s: VXvue 종료 감지(%s) — 재기동한다" % (label, "크래시" if dumps else "원인 불명"))
    try:
        v = cfg.get("viewer") or {}
        lg = v.get("login") or {}
        ui.ensure_ready(exe_path=v.get("exe"), user_id=lg.get("id"), password=lg.get("password"))
    except Exception as exc:                              # noqa: BLE001
        _log("%s: 재기동 실패 — %s (다음 TC도 실패할 수 있다)" % (label, exc))
    return r


def _run_tc(tc_id, cfg, ui, evidence_root, extra_kwargs=None):
    """구현된 TC 모듈을 실행한다. 예외는 그 TC의 FAIL로 격리한다."""
    import importlib
    mod_name, kwargs = IMPLEMENTED[tc_id]
    if extra_kwargs:
        kwargs = dict(kwargs, **extra_kwargs)
    label = TC_LABELS.get(tc_id, tc_id)
    _log("%s 실행 시작" % label)
    started = time.time()
    try:
        mod = importlib.import_module(mod_name)
        r = mod.run(ui, cfg, **kwargs)
        # 시험이 끝나면 열린 검사를 닫는다(사용자 지시, 2026-08-20) — 회귀에서는
        # TC가 여러 개 이어 돌기 때문에 특히 중요하다. 쌓인 검사가 다음 TC의
        # 촬영 대상 선택을 엉키게 한다.
        try:
            from . import workflow as W
            # **미리 open_study_tabs()로 게이트를 걸지 않는다** — 스터디 탭 바는
            # Registration 목록 화면에서는 렌더링되지 않는다(실측 2026-08-21).
            # TC가 그 화면에서 끝났다면 여기서 미리 확인하면 0개로 보여 정리를
            # 통째로 건너뛴다. close_all_studies()가 내부에서 Exposure로 옮겨
            # 직접 확인한다.
            info = W.close_all_studies(ui, cfg)
            # close_all_studies()가 Close All 툴을 쓰려고 Viewer를 최대화할
            # 수 있다 — 되돌리지 않으면 다음 TC가 인체도(Step 등록)를 못 본다
            # (README 4.14절, 2026-08-19 사고와 같은 패턴).
            W.restore_exposure_layout(ui, cfg)
            if info["closed"] or info["remaining"]:
                r.add(len(r.checks) + 1, "시험 후 정리 — 열린 검사 닫기",
                      result_mod.PASS if info["remaining"] == 0 else result_mod.MANUAL,
                      expected="열린 검사 0개",
                      actual="닫음 %d개 / 남음 %d개 (%s)"
                             % (info["closed"], info["remaining"], info.get("method") or "-"))
                r.finalize(r.completed)
        except Exception as exc:                          # noqa: BLE001
            _log("%s 검사 정리 실패: %s" % (label, exc))
        r = _check_crash(tc_id, cfg, ui, label, started, r)
        _log("%s 완료: %s (%.0f초)" % (label, r.verdict, time.time() - started))
        return r
    except Exception as exc:                              # noqa: BLE001
        r = result_mod.TCResult(tc_id, label)
        _fail_from_exception(r, 1, "%s 실행" % label, exc, cfg)
        _log("%s 예외로 실패: %s" % (label, exc))
        r = _check_crash(tc_id, cfg, ui, label, started, r)
        return r.finalize()


# --- 진입점 -------------------------------------------------------------
def run(cfg, ui_factory, approve_destructive=False, reset_baseline=True,
        evidence_root=None, only=None, quick=False):
    """전체 회귀를 실행하고 TCResult 리스트를 반환한다.

    ui_factory: () -> VXvueUi. preflight를 통과했을 때만 호출한다.
                Phase 1(baseline 복원)이 뷰어를 내리므로 그 뒤에 **다시** 호출해
                재기동·로그인까지 맡긴다.
    approve_destructive: 남겨 둔 인자. Setting Export/Import를 이 회귀에서
                         분리했으므로(사용자 지시 2026-08-20) 지금은 쓰이지
                         않는다 — `run.py setting-export-import`가 담당한다.
    reset_baseline: Phase 1 수행 여부. 전체 회귀 기본값은 True이며 임시
                    디버깅에서만 명시적으로 False로 둔다.
    only: 특정 TC만 돌릴 때의 tc_id 집합(디버깅용). None이면 전체.
    quick: 짧은 회귀. 촬영을 TC02에서 한 번만 하고 TC14는 표본만 본다.
           축소한 범위를 `Quick_Mode` 결과로 남긴다(QUICK_KWARGS 주석 참고).
    """
    scope = _load_scope()
    scope_by_id = dict((row["tc_id"], row) for row in scope)
    all_ids = list(scope_by_id) or list(TC_LABELS)
    evidence_root = evidence_root or os.path.join(HERE, "Evidence")

    results = []

    # Phase 0
    _log("Phase 0 — 선행조건 점검")
    pre, blocked = _run_precondition(cfg)
    results.append(pre)
    if blocked:
        _log("preflight NG — UI 자동화를 시작하지 않는다.")
        results.append(_run_baseline_reset(cfg, approved=False)[0])
        for tc_id in all_ids:
            results.append(_placeholder(
                tc_id, scope_by_id,
                override_note="preflight 실패로 이번 회귀에서 실행되지 않았다"
                              "(Precondition 결과 참고)."))
        return results

    # Phase 1
    _log("Phase 1 — baseline 초기화 (%s)"
         % ("수행(전체 회귀 기본값)" if reset_baseline
            else "건너뜀: --no-reset-baseline 지정"))
    reset_result, did_reset = _run_baseline_reset(cfg, approved=reset_baseline)
    results.append(reset_result)
    if reset_baseline and reset_result.verdict == result_mod.FAIL:
        _log("baseline 초기화 실패 — 이후 Phase를 실행하지 않고 전체 FAIL로 종료한다.")
        for tc_id in run_order(set(all_ids) | set(IMPLEMENTED)):
            if only and tc_id not in only:
                continue
            results.append(_downstream_fail(
                tc_id, "baseline 초기화가 실패해(Baseline_Reset 결과 참고) 이번 "
                       "회귀에서 이 TC를 실행하지 않았다. 초기 상태가 보장되지 않은 "
                       "판정을 정식 회귀 결과로 만들지 않기 위해 중단했다.",
                prerequisite="baseline 초기화"))
        return results

    # 뷰어 준비. Phase 1이 뷰어를 내렸으면 여기서 다시 띄운다.
    ui = None
    try:
        if did_reset:
            _log("baseline 복원 후 뷰어 재기동")
        ui = ui_factory()
    except Exception as exc:                              # noqa: BLE001
        r = result_mod.TCResult("Viewer_Startup", "뷰어 기동·로그인")
        _fail_from_exception(r, 1, "뷰어 기동·로그인", exc, cfg)
        results.append(r.finalize())
        for tc_id in all_ids:
            results.append(_placeholder(
                tc_id, scope_by_id,
                override_note="뷰어를 준비하지 못해 실행되지 않았다"
                              "(Viewer_Startup 결과 참고)."))
        return results

    # Phase 2
    _log("Phase 2 — VXvue 라이선스 확인")
    license_result = _run_license_check(cfg, ui, evidence_root)
    results.append(license_result)
    if license_result.verdict == result_mod.FAIL:
        _log("필수 라이선스 확인 실패 — 이후 Phase를 실행하지 않고 전체 FAIL로 종료한다.")
        for tc_id in run_order(set(all_ids) | set(IMPLEMENTED)):
            if only and tc_id not in only:
                continue
            results.append(_downstream_fail(
                tc_id, "필수 VXvue 라이선스 확인이 실패해(VXvue_License 결과 참고) "
                       "이번 회귀에서 이 TC를 실행하지 않았다. 기능이 비활성화된 "
                       "상태의 연쇄 실패를 제품 결함과 섞지 않기 위해 중단했다.",
                prerequisite="필수 VXvue 라이선스 확인"))
        return results

    # Phase 3
    _log("Phase 3 — DICOM 서버 연동 확인·구성")
    dicom_result, servers_ok = _run_dicom_registration(cfg, ui)
    results.append(dicom_result)
    if not servers_ok:
        _log("필수 DICOM 서버 등록·Echo 실패 — Phase 4(TC 실행)를 건너뛰고 "
             "전체 FAIL로 종료한다.")
        for tc_id in run_order(set(all_ids) | set(IMPLEMENTED)):
            if only and tc_id not in only:
                continue
            results.append(_downstream_fail(
                tc_id, "필수 DICOM 서버 등록·Echo가 실패해(DICOM_Servers 결과 "
                       "참고) 이번 회귀에서 이 TC를 실행하지 않았다. 연결 선행조건이 "
                       "깨진 상태의 연쇄 실패를 제품 결함과 섞지 않기 위해 실행을 "
                       "중단했다(사용자 지시, 2026-08-26).",
                prerequisite="필수 DICOM 서버 등록·Echo"))
        return results

    # Phase 4
    _log("Phase 4 — TC 실행%s" % (" (짧은 회귀)" if quick else ""))
    if quick:
        results.append(_quick_notice(set(QUICK_KWARGS)))
    # 구현된 TC와 미구현 TC를 **한 루프에서 번호순으로** 처리한다. 예전에는
    # 실행 목록을 먼저 돌고 남은 것을 뒤에 붙여서, 리포트에서 미구현 TC가
    # 뒤로 몰려 체크리스트 행 순서와 어긋났다.
    for tc_id in run_order(set(all_ids) | set(IMPLEMENTED)):
        if only and tc_id not in only:
            continue
        if tc_id in IMPLEMENTED:
            results.append(_run_tc(tc_id, cfg, ui, evidence_root,
                                   QUICK_KWARGS.get(tc_id) if quick else None))
        else:
            results.append(_placeholder(tc_id, scope_by_id))

    # Setting Export/Import는 **이 회귀에 넣지 않는다**(사용자 지시 2026-08-20:
    # "Export/Import 테스트는 전체 회귀랑 별개야 (...) 아예 다르게 관리해주라").
    #
    # 성격이 다르다. 이 회귀는 제품이 Windows Update 후에도 정상 동작하는지
    # 보는 것이고, Export/Import는 **설정 백업·복원 기능 자체의 회귀**로 DB를
    # 통째로 되돌린다(실측 1021초, 단일 항목 중 최장). 회귀에 섞으면 뒤 TC의
    # 시작 상태를 바꾸고, 실행 시간도 회귀 전체를 지배한다.
    #
    #     python run.py setting-export-import                # Export까지만
    #     python run.py setting-export-import --approve-destructive   # Import 포함
    return results
