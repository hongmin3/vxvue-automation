# -*- coding: utf-8 -*-
r"""TC ID → 그 판정을 만든 코드 파일 목록.

HTML 리포트의 "자동화 코드 위치" 섹션이 쓴다. 리포트만 보고 판정 코드를 찾을 수
있어야 감사가 된다(`VXvue/CLAUDE.md` 3절 — 판정 근거의 출처를 남긴다).

**실행 TC는 추론하지 않고 `core/regression.IMPLEMENTED` 한 곳에서만 읽는다.**
그 맵이 실제로 import 되는 모듈이므로, 여기서 목록을 다시 적으면 두 곳이 어긋날
때 리포트가 조용히 틀린 경로를 가리킨다.

회귀 러너가 직접 만드는 보조 TC(Precondition / Baseline_Reset / ...)만 아래에
명시한다 — `core/regression.py` 안에서 만들어지므로 파일명 규칙으로 유도할 수
없다. 각 항목은 2026-08-26에 `core/regression.py`에서 실제 호출부를 확인해
적었다.
"""

import os

# 회귀 러너가 자체적으로 만드는 보조 TC. 경로는 저장소 루트(`auto/`) 기준.
SUPPORT_MODULES = {
    "Precondition":    ["core/regression.py", "core/preflight.py",
                        "core/mwl.py"],
    "Baseline_Reset":  ["core/regression.py", "core/dbreset.py"],
    "Viewer_Startup":  ["core/regression.py", "core/ui.py"],
    "VXvue_License":   ["core/regression.py", "core/license.py"],
    "DICOM_Servers":   ["core/regression.py", "core/dicom_settings.py",
                        "core/db.py"],
    "Quick_Mode":      ["core/regression.py"],
    # `python run.py report-sample` 이 만드는 형식 확인용 TC.
    "TC_WindowsUpdate_00": ["run.py", "core/result.py"],
    # 체크리스트에 없는 자체 TC — `IMPLEMENTED` 가 아니라 `run.py` 의
    # `setting-export-import` 명령에서 직접 실행한다.
    "TC_Setting_ExportImport": ["tests/tc_setting_export_import.py"],
}


def _implemented_map():
    """`regression.IMPLEMENTED` 의 모듈 경로를 파일 경로로 바꾼다."""
    try:
        from . import regression
    except Exception:                                     # noqa: BLE001
        return {}
    out = {}
    for tc_id, entry in (getattr(regression, "IMPLEMENTED", {}) or {}).items():
        mod_name = entry[0] if isinstance(entry, (tuple, list)) else entry
        path = str(mod_name).replace(".", "/") + ".py"
        if os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), path)):
            out[tc_id] = [path]
    return out


def modules_for(tc_id):
    """TC ID 를 구현한 파일 목록. 모르는 ID 는 빈 목록."""
    return as_map().get(tc_id, [])


def as_map(tc_ids=None):
    """`{TC ID: [파일 경로, ...]}`. `tc_ids` 를 주면 그 TC 만 추린다."""
    table = dict(SUPPORT_MODULES)
    table.update(_implemented_map())
    if tc_ids is None:
        return table
    return dict((t, table[t]) for t in tc_ids if t in table)
