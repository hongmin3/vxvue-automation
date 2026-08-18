# -*- coding: utf-8 -*-
"""리포트 헤더의 '패키지 정보' 수집.

1순위는 사내 `ModelVersionChecker_v2.3`(무인 실행 지원, `--product "VXvue"`)의
JSON 리포트다. 도구가 없거나 실패하면 파일 버전 직접 조회로 대체한다.

ModelVersionChecker가 지원하는 제품은 Bellalun / VXvue Mammo / VXvue /
DxWorks / NewAitella / XIPL.STUDIO / XIPL 7종이며, **VX.LIVE.SERVER는 지원
목록에 없다.** 따라서 VX.LIVE.SERVER 버전은 항상 파일 버전으로 조회한다.
"""

import glob
import json
import os
import subprocess

from . import sysinfo

# 도구가 없을 때 대신 읽는 파일들 (체크리스트 상단 항목과 1:1 대응)
FALLBACK_FILES = {
    "VXvue": r"C:\Program Files\Vxvue\VXvue.exe",
    "VXService": r"C:\Program Files\Vxvue\VXService.exe",
    "License.dll": r"C:\Program Files\Vxvue\License.dll",
    "vunoSDK.dll": r"C:\Program Files\Vxvue\vunoSDK.dll",
    "XIPL.CONNECTOR.dll": r"C:\Program Files\Vxvue\XIPL.CONNECTOR.dll",
    "VX.LIVE.VIEW": r"C:\Program Files\Vxvue\VX.LIVE.VIEW\VX.LIVE.VIEW.exe",
    "VX.LIVE.SERVER": r"C:\VX.LIVE.SERVER\VX.LIVE.SERVER.exe",
    "XIPL.SERVER": r"C:\XIPL\SERVER_X64\XIPL.SERVER.exe",
    "XIPL.STUDIO": r"C:\XIPL\STUDIO_X64\XIPL.STUDIO.exe",
}

NOT_INSTALLED = "미설치"


def run_checker(exe, product="VXvue", timeout=180):
    """ModelVersionChecker를 무인 실행하고 최신 JSON 리포트를 읽어 반환한다."""
    if not exe or not os.path.exists(exe):
        return None
    work = os.path.dirname(os.path.abspath(exe))
    try:
        subprocess.run([exe, "--product", product], cwd=work,
                       capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    reports = sorted(glob.glob(os.path.join(work, "reports", "*.json")),
                     key=os.path.getmtime)
    if not reports:
        return None
    try:
        with open(reports[-1], "r", encoding="utf-8-sig") as f:
            return {"report_path": reports[-1], "data": json.load(f)}
    except (OSError, ValueError):
        return None


def _flatten_checker(payload):
    """checker JSON의 `installed_inventory`에서 '파일명 -> 현재 버전' 맵을 만든다.

    스키마(tool_version 2.3 / schema_version 1)는 파일마다 여러 버전 후보를
    준다. 예를 들어 VXvue.exe는 `FileVersion=1.0.11.015`(체크리스트가 쓰는
    표기)와 `FixedVersion=1.0.11.0`(버전 리소스 고정 필드)을 둘 다 갖는다.
    체크리스트 상단과 같은 표기를 내기 위해 **FileVersion을 우선**한다.
    """
    out = {}
    inv = (payload or {}).get("installed_inventory") or {}
    if not isinstance(inv, dict):
        return out
    for fname, info in inv.items():
        if not isinstance(info, dict):
            continue
        versions = info.get("versions") or []
        pick = None
        for want in ("FileVersion", "ProductVersion", "FixedVersion"):
            pick = next((v.get("raw") for v in versions
                         if isinstance(v, dict) and v.get("source") == want and v.get("raw")),
                        None)
            if pick:
                break
        if not pick and versions and isinstance(versions[0], dict):
            pick = versions[0].get("raw")
        if pick:
            out[str(fname).lower()] = str(pick)
    return out


def _release_note_summary(payload):
    """릴리즈노트 대조 요약 한 줄. 값이 없으면 None."""
    s = (payload or {}).get("summary") or {}
    if not s:
        return None
    return ("%s (대조 %s건 / 불일치 %s / 경고 %s)"
            % (s.get("result", "?"), s.get("compared", "?"),
               s.get("fail", 0), s.get("warn", 0)))


def collect(config=None):
    """리포트 헤더에 넣을 패키지 정보 dict를 만든다.

    반환 예)
      {"VXvue": "1.0.11.015", "VX.LIVE.SERVER": "...", "XIPL": "...", ...}
    확인 불가한 항목은 '미설치' 또는 '(확인 필요)'로 남기고 임의 값을 넣지 않는다.
    """
    cfg = config or {}
    pkg = {}

    checker = (cfg.get("package_info") or {}).get("model_version_checker_exe")
    product = (cfg.get("package_info") or {}).get("product", "VXvue")
    result = run_checker(checker, product) if checker else None
    if result:
        flat = _flatten_checker(result.get("data"))
        for label, path in FALLBACK_FILES.items():
            base = os.path.basename(path).lower()
            if base in flat:
                pkg[label] = flat[base]
        note = _release_note_summary(result.get("data"))
        if note:
            pkg["릴리즈노트 대조"] = note
        pkg["_source"] = os.path.basename(result["report_path"])

    # 도구가 못 채운 항목은 파일 버전으로 보완한다.
    for label, path in FALLBACK_FILES.items():
        if pkg.get(label):
            continue
        if not os.path.exists(path):
            pkg[label] = NOT_INSTALLED
            continue
        pkg[label] = sysinfo.file_version(path) or "(확인 필요)"

    return pkg
