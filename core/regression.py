# -*- coding: utf-8 -*-
"""체크리스트 전체 회귀 러너.

`automation_scope.json`의 TC별 자동화 수준을 읽어 EXCLUDED는 건너뛰고,
나머지는 의존 순서대로 실행한 뒤 **모든 TC 결과를 리포트 1건으로 합친다**
(HANDOFF.md 3.2절 요구사항).

지금 실제로 자동 수행되는 것은 preflight/mwl-ensure/xipl-license(선행조건),
TC14(Setting 전체 화면), TC_Setting_ExportImport(파괴적, 승인 필요) 뿐이다.
TC13/02/06/03/04/11/12와 그 외 TC는 아직 그 항목을 실제로 수행하는 자동화
코드가 없으므로, `automation_scope.json`에 기록된 현재 수준(MANUAL/PARTIAL/
BLOCKED/EXCLUDED)과 그 판단 근거를 리포트 항목으로 그대로 옮긴다.
**"이번에 실제로 수행했다"와 "아직 자동화 코드가 없어 수행하지 않았다"를
리포트만 보고 구분할 수 있어야 한다** — 이것이 이 러너의 핵심 요구사항이다.

실행 순서(파괴적 조작은 맨 뒤로):
    preflight -> mwl-ensure -> xipl-license
    -> TC13 -> TC14 -> TC02 -> TC06 -> TC03 -> TC04 -> TC11 -> TC12
    -> (나머지 TC: 05/07/08/09/01/10/15 — 실행 순서와 무관, 수준만 표시)
    -> TC_Setting_ExportImport(맨 마지막, 파괴적, 명시적 승인 필요)
"""

import os
from datetime import date

from . import preflight as preflight_mod
from . import result as result_mod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# automation_scope.json 의 level 문자열 -> 리포트 판정.
# "PARTIAL"과 "FULL 가능성 높음"은 코드가 없으면 MANUAL로 남긴다(추정 PASS 금지).
_LEVEL_TO_VERDICT_WHEN_NOT_IMPLEMENTED = {
    "EXCLUDED": result_mod.SKIP,
    "MANUAL": result_mod.MANUAL,
    "BLOCKED": result_mod.BLOCKED,
    "PARTIAL": result_mod.MANUAL,
    "FULL 가능성 높음": result_mod.MANUAL,
}

# 실행 순서. HANDOFF.md 3.2절 순서 그대로. 여기 없는 TC(01/05/07/08/09/10/15)는
# 실행 순서상 의미가 없으므로(모두 MANUAL/BLOCKED/EXCLUDED) 순서 뒤에 이어붙인다.
RUN_ORDER = [
    "TC_WindowsUpdate_13",
    "TC_WindowsUpdate_14",
    "TC_WindowsUpdate_02",
    "TC_WindowsUpdate_06",
    "TC_WindowsUpdate_03",
    "TC_WindowsUpdate_04",
    "TC_WindowsUpdate_11",
    "TC_WindowsUpdate_12",
]

# HANDOFF.md 3.3절에서 정리한 작업용 명칭. 체크리스트 원본(엑셀)의 정식
# 제목이 아니라 이 프로젝트 안에서 부르는 이름이므로, 정확한 원본 제목은
# `VXvue 지식파일/(TC) RA16-14B-010_VXvue Basic Function Checklist.xlsx`를
# 직접 확인해야 한다.
TC_LABELS = {
    "TC_WindowsUpdate_01": "TC01 (범위 제외)",
    "TC_WindowsUpdate_02": "TC02 MWL 워크플로우",
    "TC_WindowsUpdate_03": "TC03 표시/도구",
    "TC_WindowsUpdate_04": "TC04 XIPL 처리",
    "TC_WindowsUpdate_05": "TC05 원격 PACS 전송",
    "TC_WindowsUpdate_06": "TC06 Extra Tool/SBSC",
    "TC_WindowsUpdate_07": "TC07 DICOM Print",
    "TC_WindowsUpdate_08": "TC08 Export(CD/USB)",
    "TC_WindowsUpdate_09": "TC09 (재부팅 필요)",
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


def _placeholder(tc_id, scope_by_id, override_note=None):
    row = scope_by_id.get(tc_id) or {}
    level = row.get("level", "확인 필요")
    reason = row.get("reason", "")
    r = result_mod.TCResult(tc_id, TC_LABELS.get(tc_id, tc_id))
    verdict = _LEVEL_TO_VERDICT_WHEN_NOT_IMPLEMENTED.get(level, result_mod.MANUAL)
    note = override_note or reason
    if level in ("PARTIAL", "FULL 가능성 높음") and not override_note:
        note = (reason + " | automation_scope.json 상 수준은 '%s'이지만 이를 실제로 "
                "수행하는 자동화 코드가 아직 없다(HANDOFF.md 3.3절 참고). "
                "수동으로 수행하거나 다음 세션에서 구현해야 한다." % level)
    r.add(1, "automation_scope.json 기준 현재 수준: %s" % level, verdict, note=note)
    r.finalize()
    return r


def _run_precondition(cfg):
    """preflight + mwl-ensure + xipl-license 를 한 TCResult로 묶는다."""
    r = result_mod.TCResult("Precondition", "회귀 실행 전 환경/선행조건 점검")
    items = preflight_mod.run(cfg)
    for i, it in enumerate(items, 1):
        status = result_mod.PASS if it.status == preflight_mod.OK else (
            result_mod.FAIL if it.status == preflight_mod.NG else result_mod.MANUAL)
        r.add(i, it.name, status, expected=it.expected, actual=it.actual, note=it.note)
    step = len(items) + 1

    bad = preflight_mod.blocking(items)
    if bad:
        r.add(step, "mwl-ensure / xipl-license",
              result_mod.SKIP, note="preflight NG로 인해 건너뜀")
        r.finalize()
        return r, True  # blocked=True

    try:
        from datetime import date as _date
        from .mwl import MwlServer, make_dx_order
        td = cfg.get("test_data") or {}
        url = (cfg.get("dicom") or {}).get("mwl_server_url")
        if not url:
            r.add(step, "mwl-ensure", result_mod.MANUAL,
                  note="config의 dicom.mwl_server_url 이 비어 있어 건너뜀")
        else:
            m = MwlServer(url)
            fields = make_dx_order(
                patient_id=td.get("mwl_patient_id", "VXVUE_MWL_DX_01"),
                patient_name=td.get("mwl_patient_name", "AUTO^VXVUE^^^"),
                accession_number=td.get("mwl_accession", "ACC_VX_AUTO_001"),
                sps_id=td.get("mwl_sps_id", "SPS_VX_AUTO_001"),
                station_ae=(cfg.get("dicom") or {}).get("local_ae_title", "VXVUE"),
                sps_start_date=_date.today().isoformat(),
                sps_start_time=td.get("mwl_sps_start_time", "09:00"),
                procedure_id=td.get("mwl_procedure_id"),
                procedure_description=td.get("mwl_procedure_description", "CHEST"),
                sps_description=td.get("mwl_sps_description", "CHEST PA"),
                patient_sex=td.get("mwl_patient_sex", "M"),
                patient_birthdate=td.get("mwl_patient_birthdate", "1980-01-01"),
            )
            item, how, removed = m.ensure_order(_date.today().isoformat(), **fields)
            r.add(step, "mwl-ensure (당일 DX 처방 보장)", result_mod.PASS,
                  actual="%s (지난 처방 삭제 %d건)" % (how, removed))
    except Exception as exc:                              # noqa: BLE001
        r.add(step, "mwl-ensure", result_mod.FAIL, note=str(exc))
    step += 1

    try:
        from . import xipl
        res = xipl.check_licenses()
        ok = res["status"] == "OK"
        status = result_mod.PASS if ok else (
            result_mod.MANUAL if res["status"] == xipl.ABOUT_CLOSED else result_mod.FAIL)
        r.add(step, "xipl-license (영상처리 라이선스 4종)", status,
              expected="필요 라이선스 전체 등록", actual=", ".join(res.get("found", [])),
              note=(xipl.ABOUT_OPEN_HINT if status == result_mod.MANUAL else
                    ("누락: %s" % ", ".join(res["missing"]) if res.get("missing") else "")))
    except Exception as exc:                              # noqa: BLE001
        r.add(step, "xipl-license", result_mod.FAIL, note=str(exc))

    r.finalize()
    return r, False


def run(cfg, ui_factory, approve_destructive=False, no_env=False):
    """전체 회귀를 실행하고 TCResult 리스트를 반환한다.

    ui_factory: () -> VXvueUi. preflight를 통과했을 때만 호출한다(UI를
    아직 준비하지 못한 상태에서 자동화를 시작하지 않기 위해).
    approve_destructive: True일 때만 Setting Export/Import의 실제 Import
    단계를 수행한다(파괴적 조작 — DB 전체가 마지막 Export 시점으로 복원된다).
    """
    scope = _load_scope()
    scope_by_id = {r["tc_id"]: r for r in scope}
    all_ids = list(scope_by_id) or list(TC_LABELS)

    results = []
    pre, blocked = _run_precondition(cfg)
    results.append(pre)

    if blocked:
        for tc_id in all_ids:
            results.append(_placeholder(
                tc_id, scope_by_id,
                override_note="preflight 실패로 이번 회귀에서 실행되지 않았다"
                              "(Precondition TC 결과 참고)."))
        return results

    ui = ui_factory()

    ran = set()
    for tc_id in RUN_ORDER:
        if tc_id == "TC_WindowsUpdate_14":
            from tests import tc14_setting_display as tc14
            results.append(tc14.run(ui, cfg))
        else:
            results.append(_placeholder(tc_id, scope_by_id))
        ran.add(tc_id)

    for tc_id in all_ids:
        if tc_id in ran:
            continue
        results.append(_placeholder(tc_id, scope_by_id))

    # 파괴적 조작은 항상 맨 마지막.
    from tests import tc_setting_export_import as tc_ei
    if approve_destructive:
        results.append(tc_ei.run(ui, cfg, do_import=True))
    else:
        r = tc_ei.run(ui, cfg, do_import=False)
        r.add(len(r.checks) + 1, "Import(파괴적 조작) 실행 여부",
              result_mod.MANUAL,
              note="--approve-destructive 없이 실행되어 Import(DB 전체 복원) 단계는 "
                   "건너뛰었다. Export까지의 결과만 포함한다.")
        results.append(r)

    return results
