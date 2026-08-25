# -*- coding: utf-8 -*-
r"""저장소 일관성 정적 검사 — 제품을 켜지 않고, 파일만 읽어서 확인한다.

## 왜 필요한가

`CLAUDE.md` 3절: *"각 모듈은 최상단에 `TC_ID` 상수를 두고,
`core/regression.IMPLEMENTED`의 키와 그 값이 일치해야 한다 — 어긋나면 리포트의
TC ID와 실행된 코드가 달라져 체크리스트 기록이 엉뚱한 행에 들어간다."*

이 규칙은 문서에만 있고 **아무도 검사하지 않았다.** 어긋나도 실행은 성공하고,
리포트도 정상으로 보이며, 엉뚱한 체크리스트 행에 결과가 들어간 뒤에야
드러난다 — 가장 발견이 늦는 종류의 오류다.

## 검사 방식

TC 모듈을 **import하지 않는다.** import하면 `core.ui` 등 무거운 의존성이 딸려
오고, 시험 PC가 아닌 곳에서는 그 자체가 실패할 수 있다. `TC_ID = "..."` 줄을
소스에서 정규식으로 읽는다 — 이 상수는 관례상 항상 최상단의 리터럴이다.

반환은 **문제 문자열의 리스트**다. 빈 리스트면 통과.
"""

import glob
import io
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(HERE, "tests")

_TC_ID_RE = re.compile(r'^TC_ID\s*=\s*["\']([^"\']+)["\']', re.M)
#: tests/tcNN_*.py 의 파일명 번호를 뽑는다(tc_setting_export_import 처럼 번호가
#: 없는 자체 회귀는 대상에서 빠진다 — CLAUDE.md 3절이 명시한 예외).
_FILE_NUM_RE = re.compile(r"^tc(\d+)_")


def _read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def tc_ids_in_tests():
    """{파일 basename: TC_ID}. TC_ID 선언이 없으면 값이 None."""
    out = {}
    for path in sorted(glob.glob(os.path.join(TESTS_DIR, "tc*.py"))):
        name = os.path.basename(path)
        m = _TC_ID_RE.search(_read(path))
        out[name] = m.group(1) if m else None
    return out


def scope_entries():
    p = os.path.join(HERE, "automation_scope.json")
    if not os.path.exists(p):
        return []
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


def implemented_map():
    """`core/regression.IMPLEMENTED`를 소스에서 읽는다(무거운 import 회피)."""
    src = _read(os.path.join(HERE, "core", "regression.py"))
    m = re.search(r"^IMPLEMENTED\s*=\s*\{(.*?)^\}", src, re.M | re.S)
    if not m:
        return {}
    out = {}
    for tc_id, mod in re.findall(r'"([^"]+)"\s*:\s*\("([^"]+)"', m.group(1)):
        out[tc_id] = mod
    return out


def labels():
    src = _read(os.path.join(HERE, "core", "regression.py"))
    m = re.search(r"^TC_LABELS\s*=\s*\{(.*?)^\}", src, re.M | re.S)
    if not m:
        return {}
    return dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', m.group(1)))


# --- 개별 검사 ---------------------------------------------------------
def check_tc_id_declared():
    """모든 `tests/tc*.py`가 `TC_ID` 상수를 갖는다."""
    return ["%s: TC_ID 상수가 없다" % name
            for name, tc_id in tc_ids_in_tests().items() if not tc_id]


def check_filename_matches_tc_id():
    """파일명의 번호가 TC_ID의 번호와 같다(`CLAUDE.md` 3절)."""
    problems = []
    for name, tc_id in tc_ids_in_tests().items():
        if not tc_id:
            continue
        m = _FILE_NUM_RE.match(name)
        if not m:                                   # 번호 없는 자체 회귀는 예외
            continue
        want = "TC_WindowsUpdate_%s" % m.group(1)
        if tc_id != want:
            problems.append("%s: 파일명은 %s를 뜻하는데 TC_ID는 %s다"
                            % (name, want, tc_id))
    return problems


def check_implemented_points_at_right_module():
    """`IMPLEMENTED[tc_id]`가 가리키는 모듈의 `TC_ID`가 그 키와 같다.

    여기가 어긋나면 **리포트에 찍히는 TC ID와 실제 실행된 코드가 다르다.**
    """
    problems = []
    by_module = {}
    for name, tc_id in tc_ids_in_tests().items():
        by_module["tests." + name[:-3]] = tc_id
    for tc_id, mod in implemented_map().items():
        if mod not in by_module:
            problems.append("IMPLEMENTED[%s] = %s — 그런 모듈 파일이 없다"
                            % (tc_id, mod))
        elif by_module[mod] != tc_id:
            problems.append("IMPLEMENTED[%s] = %s 인데 그 모듈의 TC_ID는 %s다"
                            % (tc_id, mod, by_module[mod]))
    return problems


def check_scope_covers_implemented():
    """`IMPLEMENTED`의 모든 TC가 `automation_scope.json`에 있다."""
    scope_ids = set(e.get("tc_id") for e in scope_entries())
    return ["automation_scope.json에 %s 항목이 없다 — 자동화 수준과 근거가 기록되지 않는다" % tc_id
            for tc_id in sorted(implemented_map()) if tc_id not in scope_ids]


def check_scope_has_reason():
    """모든 scope 항목이 `level`과 그 판단 `reason`을 갖는다(`CLAUDE.md` 4절)."""
    problems = []
    for e in scope_entries():
        tc_id = e.get("tc_id") or "(tc_id 없음)"
        if not (e.get("level") or "").strip():
            problems.append("%s: level이 비어 있다" % tc_id)
        if not (e.get("reason") or "").strip():
            problems.append("%s: reason이 비어 있다 — 근거 없이 수준을 기록하지 않는다" % tc_id)
    return problems


def check_scope_levels_known():
    known = {"FULL", "PARTIAL", "MANUAL", "BLOCKED", "EXCLUDED"}
    return ["%s: 알 수 없는 level '%s'" % (e.get("tc_id"), e.get("level"))
            for e in scope_entries() if (e.get("level") or "") not in known]


def check_scope_ids_unique():
    seen, dup = set(), []
    for e in scope_entries():
        tc_id = e.get("tc_id")
        if tc_id in seen:
            dup.append("automation_scope.json에 %s가 중복돼 있다" % tc_id)
        seen.add(tc_id)
    return dup


def check_labels_cover_scope():
    """리포트 콘솔 라벨이 scope의 모든 TC를 덮는다(없으면 tc_id가 그대로 찍힌다)."""
    lab = labels()
    return ["core/regression.TC_LABELS에 %s가 없다" % e.get("tc_id")
            for e in scope_entries()
            if e.get("tc_id") and e.get("tc_id") not in lab]


def check_purposes_cover_implemented():
    """`core/result.TC_PURPOSES`가 실행되는 모든 TC의 시험 목적을 갖는다.

    `CLAUDE.md` 9절 1번: 리포트의 각 TC에는 시험 목적이 반드시 표시된다.
    """
    src = _read(os.path.join(HERE, "core", "result.py"))
    m = re.search(r"^TC_PURPOSES\s*=\s*\{(.*?)^\}", src, re.M | re.S)
    have = set(re.findall(r'"([^"]+)"\s*:', m.group(1))) if m else set()
    want = set(implemented_map())
    want.update(t for t in tc_ids_in_tests().values() if t)
    return ["core/result.TC_PURPOSES에 %s의 시험 목적이 없다" % tc_id
            for tc_id in sorted(want - have)]


def check_commands_registered():
    """`run.py`의 `COMMANDS`에 등록된 이름과 함수가 모두 정의돼 있다."""
    src = _read(os.path.join(HERE, "run.py"))
    m = re.search(r"^COMMANDS\s*=\s*\{(.*?)^\}", src, re.M | re.S)
    if not m:
        return ["run.py에서 COMMANDS 사전을 찾지 못했다"]
    problems = []
    for name, func in re.findall(r'"([^"]+)"\s*:\s*(\w+)', m.group(1)):
        if not re.search(r"^def %s\(" % re.escape(func), src, re.M):
            problems.append("COMMANDS['%s'] = %s — 그 함수가 run.py에 없다"
                            % (name, func))
    return problems


CHECKS = (
    ("tests/*.py에 TC_ID 선언", check_tc_id_declared),
    ("파일명 번호 ↔ TC_ID 일치", check_filename_matches_tc_id),
    ("IMPLEMENTED ↔ 모듈 TC_ID 일치", check_implemented_points_at_right_module),
    ("automation_scope.json이 구현 TC를 덮는가", check_scope_covers_implemented),
    ("scope 항목의 level·reason 존재", check_scope_has_reason),
    ("scope level 값이 알려진 값인가", check_scope_levels_known),
    ("scope tc_id 중복 없음", check_scope_ids_unique),
    ("TC_LABELS가 scope를 덮는가", check_labels_cover_scope),
    ("TC_PURPOSES가 구현 TC를 덮는가", check_purposes_cover_implemented),
    ("run.py COMMANDS의 함수 존재", check_commands_registered),
)


def run_all():
    """[(검사명, [문제...]), ...] — 문제 목록이 비어 있으면 그 검사는 통과."""
    return [(name, fn()) for name, fn in CHECKS]
