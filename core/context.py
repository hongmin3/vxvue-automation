# -*- coding: utf-8 -*-
"""시험 환경 컨텍스트 — "어떤 라이선스·연동 상태에서 저장한 기준인가".

VXvue의 Setting 메뉴는 **라이선스와 연동 상태에 따라 달라진다.** 실측 예:

- VX.LIVE.SERVER 설치 + Live View 라이선스 적용 후 `Integration > Camera`가
  새로 나타났다(그 전에는 없었다).
- 제너레이터를 연동한 뒤 `Integration > Generator`가 나타났다.
- 그 결과 소분류가 53개 -> 55개로 늘었다.

따라서 화면 캡처 기준(baseline)을 하나로만 두면, 연동이 달라진 PC에서 돌릴 때
"화면이 다르다"는 헛된 FAIL이 쏟아진다. 기준자료를 **컨텍스트별로 분리 보관**
하고, 리포트에 어떤 컨텍스트와 비교했는지 남겨야 한다.

컨텍스트에 담는 것(전부 UI 없이 읽을 수 있는 값):

| 항목 | 출처 |
|---|---|
| VXvue 라이선스 키 | `D:\\Database\\Database\\license.lic`, `Optionlicense*.lic` |
| XIPL 라이선스 이름 | `XIPL.SERVER` About 창(열려 있을 때) |
| 제너레이터 / AI 엔진 / 카메라 연동 | `C:\\ProgramData\\VXvue\\Viewer.xml` 속성 |
| 테마 / 언어 | 같음 |
| 패키지 버전 | 파일 버전 |
| Setting 트리 | 실행 시점에 순회로 얻은 소분류 제목 목록 |

사용자 확인(2026-08-18): 현재 상태는 **VX.LIVE.SERVER 연동 + XIPL 전체 옵션 +
VXvue Shimadzu 라이선스 + VXvue AI(VXCAD) 라이선스 등록·연동** 상태이며, 이
상태의 Setting 설정을 기준으로 저장한다.

## 서명을 둘로 나누는 이유 (사용자 확인, 2026-08-18)

테마·폰트·옵션에 따라 **VXvue의 색상, Setting 창 크기, 폰트가 달라진다. 그러나
각 설정 값과 옵션, Setting 메뉴 구성은 동일하다.**

그래서 기준을 하나의 서명으로 묶으면, 테마만 바꿔도 화면 캡처가 전부 달라져
"설정이 바뀌었다"는 헛된 FAIL이 난다. 서명을 둘로 나눈다.

| 서명 | 포함 | 쓰임 |
|---|---|---|
| `structure_signature` | 라이선스, 연동(Generator/AIEngine/Camera 등), Setting 메뉴 목록 — **테마·폰트 제외** | 구조 기준(컨트롤 ID·클래스·표시 텍스트) 비교. 판정 근거 |
| `visual_signature` | 위 + 테마 + 폰트 + 본문 창 크기 | 캡처(SSIM) 비교. 같은 테마끼리만 비교 |

즉 판정은 테마에 영향받지 않는 **구조**로 하고, 픽셀 비교는 테마가 같은
기준자료 안에서만 수행한다.
"""

import glob
import hashlib
import io
import json
import os
import re

LICENSE_GLOBS = (r"D:\Database\Database\license.lic",
                 r"D:\Database\Database\Optionlicense*.lic")
VIEWER_XML = r"C:\ProgramData\VXvue\Viewer.xml"

# Viewer.xml에서 컨텍스트로 삼을 속성
VIEWER_XML_KEYS = (
    ("Application", "Theme"), ("Application", "Language"),
    ("Application", "TranslateIconText"),
    ("Generator", "product"), ("AIEngine", "product"),
    ("Camera", "UseLiveView"), ("Detector", "UseAEC"),
    ("Collimator", "product"), ("DAP", "product"),
)

# 외형(테마/폰트)에만 영향을 주는 키. 구조 서명에서는 제외한다.
APPEARANCE_KEYS = ("Application.Theme", "Application.Language",
                   "Application.TranslateIconText")

CONFIGURATION_XML = r"D:\Database\Configuration\Configuration.xml"


def vxvue_license_keys():
    keys = []
    for pattern in LICENSE_GLOBS:
        for path in sorted(glob.glob(pattern)):
            try:
                keys.append({"file": os.path.basename(path),
                             "key": io.open(path, encoding="utf-8",
                                            errors="replace").read().strip()})
            except OSError:
                keys.append({"file": os.path.basename(path), "key": None})
    return keys


def viewer_xml_attrs(path=VIEWER_XML):
    """Viewer.xml에서 연동 관련 속성만 뽑는다(정규식 — 파일이 한 줄짜리 XML)."""
    if not os.path.exists(path):
        return {}
    text = io.open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for tag, attr in VIEWER_XML_KEYS:
        m = re.search(r"<%s\b[^>]*\b%s\s*=\s*\"([^\"]*)\"" % (tag, attr), text)
        out["%s.%s" % (tag, attr)] = m.group(1) if m else None
    return out


def xipl_licenses():
    """XIPL.SERVER About 창에서 읽은 라이선스 이름 목록(창이 닫혀 있으면 None)."""
    try:
        from . import xipl
    except ImportError:
        return None
    names, raw = xipl.about_licenses()
    return names


def package_versions():
    from . import sysinfo
    targets = {
        "VXvue": r"C:\Program Files\Vxvue\VXvue.exe",
        "VX.LIVE.SERVER": r"C:\VX.LIVE.SERVER\VX.LIVE.SERVER.exe",
        "XIPL.SERVER": r"C:\XIPL\SERVER_X64\XIPL.SERVER.exe",
        "vunoSDK.dll": r"C:\Program Files\Vxvue\vunoSDK.dll",
    }
    return dict((name, sysinfo.file_version(path) if os.path.exists(path) else "미설치")
                for name, path in targets.items())


def appearance():
    """외형에 영향을 주는 값(테마/폰트/본문 창 크기 등)."""
    out = {}
    vx = viewer_xml_attrs()
    for key in APPEARANCE_KEYS:
        out[key] = vx.get(key)
    if os.path.exists(CONFIGURATION_XML):
        text = io.open(CONFIGURATION_XML, encoding="utf-8", errors="replace").read()
        m = re.search(r"Font\s*=\s*\"([^\"]*)\"", text)
        out["Configuration.Font"] = m.group(1) if m else None
        m = re.search(r"ViewerType\s*=\s*\"([^\"]*)\"", text)
        out["Configuration.ViewerType"] = m.group(1) if m else None
    return out


def collect(setting_titles=None, note="", viewport=None):
    """컨텍스트를 수집한다.

    setting_titles: 순회로 얻은 소분류 제목 목록.
    viewport: Setting 본문 대화상자 크기 (w, h). 테마에 따라 달라지므로 외형
              서명에 포함한다.
    """
    ctx = {
        "note": note,
        "vxvue_license_keys": vxvue_license_keys(),
        "xipl_licenses": xipl_licenses(),
        "viewer_xml": viewer_xml_attrs(),
        "appearance": appearance(),
        "viewport": list(viewport) if viewport else None,
        "packages": package_versions(),
        "setting_titles": list(setting_titles) if setting_titles else None,
    }
    ctx["structure_signature"] = structure_signature(ctx)
    ctx["visual_signature"] = visual_signature(ctx)
    # 이전 버전 호환
    ctx["signature"] = ctx["structure_signature"]
    return ctx


def _hash(payload):
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8]


def structure_signature(ctx):
    """구조 기준 서명 — 테마·폰트는 넣지 않는다.

    라이선스와 연동 상태, Setting 메뉴 목록만 넣는다. 패키지 버전은 넣지 않는다
    — 빌드가 올라가도 같은 기준과 비교해 **구조가 달라졌는지**를 보는 것이 이
    시험의 목적이기 때문이다.
    """
    vx = dict(ctx.get("viewer_xml") or {})
    for key in APPEARANCE_KEYS:
        vx.pop(key, None)
    return _hash({
        "licenses": sorted(k.get("key") or "" for k in ctx.get("vxvue_license_keys") or []),
        "xipl": sorted(ctx.get("xipl_licenses") or []),
        "integration": vx,
        "titles": ctx.get("setting_titles") or [],
    })


def visual_signature(ctx):
    """캡처 비교용 서명 — 구조 서명 + 테마/폰트/본문 창 크기."""
    return _hash({
        "structure": structure_signature(ctx),
        "appearance": ctx.get("appearance") or {},
        "viewport": ctx.get("viewport"),
    })


# 이전 이름 호환
signature = structure_signature


def save(ctx, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=1, sort_keys=True)
    return path


def load(path):
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def describe(ctx):
    """리포트에 한 줄로 넣을 요약."""
    vx = ctx.get("viewer_xml") or {}
    xipl_names = ctx.get("xipl_licenses")
    parts = ["구조서명 %s" % ctx.get("structure_signature"),
             "외형서명 %s" % ctx.get("visual_signature")]
    parts.append("Theme=%s" % vx.get("Application.Theme"))
    parts.append("Font=%s" % ((ctx.get("appearance") or {}).get("Configuration.Font") or "(기본)"))
    if ctx.get("viewport"):
        parts.append("본문 %sx%s" % tuple(ctx["viewport"]))
    parts.append("Generator=%s" % vx.get("Generator.product"))
    parts.append("AIEngine=%s" % vx.get("AIEngine.product"))
    parts.append("LiveView=%s" % vx.get("Camera.UseLiveView"))
    parts.append("VXvue 라이선스 %d개" % len(ctx.get("vxvue_license_keys") or []))
    parts.append("XIPL 라이선스=%s" % (", ".join(xipl_names) if xipl_names else "확인 불가"))
    if ctx.get("setting_titles"):
        parts.append("Setting 소분류 %d개" % len(ctx["setting_titles"]))
    return " / ".join(parts)


def diff(a, b):
    """두 컨텍스트의 차이. 기준과 다른 환경에서 돌렸는지 알려준다."""
    out = {}
    for key in ("viewer_xml", "packages"):
        da, db = a.get(key) or {}, b.get(key) or {}
        changed = dict((k, (da.get(k), db.get(k)))
                       for k in sorted(set(da) | set(db)) if da.get(k) != db.get(k))
        if changed:
            out[key] = changed
    la = sorted(k.get("key") or "" for k in a.get("vxvue_license_keys") or [])
    lb = sorted(k.get("key") or "" for k in b.get("vxvue_license_keys") or [])
    if la != lb:
        out["vxvue_license_keys"] = {"only_in_a": sorted(set(la) - set(lb)),
                                     "only_in_b": sorted(set(lb) - set(la))}
    xa, xb = sorted(a.get("xipl_licenses") or []), sorted(b.get("xipl_licenses") or [])
    if xa != xb:
        out["xipl_licenses"] = {"only_in_a": sorted(set(xa) - set(xb)),
                                "only_in_b": sorted(set(xb) - set(xa))}
    ta, tb = a.get("setting_titles") or [], b.get("setting_titles") or []
    if ta != tb:
        out["setting_titles"] = {"only_in_a": sorted(set(ta) - set(tb)),
                                 "only_in_b": sorted(set(tb) - set(ta))}
    return out
