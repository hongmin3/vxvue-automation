# -*- coding: utf-8 -*-
r"""VXvue 자체 라이선스 확인 — Setting > System > License.

`core/xipl.py`의 `check_licenses()`는 **XIPL.SERVER의 About 창**만 확인한다
(영상처리 라이선스 4종). 이 모듈은 그것과 별개로 **VXvue 본체의 라이선스**
(Demo / CAD / Live View 등)를 확인한다.

## 근거 문서

| 근거 | 확인한 내용 |
|---|---|
| 사양서1 p.7 `VP-415 - Verify License Registration Status` | "The VXvue Option license supports up to 16 options, but currently only the CAD and Live View options are supported." / Company Code 표(None=0, Shimadzu=1 — Shimadzu VSS Integration 사용 가능) / 라이선스가 없거나 무효면 License Manager가 뜨고 VXvue는 일시 중단 / "VXvue / DxWorks do not check the license expiration date."(만료일은 VXvue가 확인하지 않고, 15일 이내면 알림만 표시) |
| 사양서2 p.111 `VP-657 - License` | 이 화면의 기능은 "License Manager를 실행한다" — 등록/변경/삭제는 License Manager가 담당 |
| Service Manual p.54 `4.2.5 License 메뉴` | "Add 버튼을 클릭하고 새로운 라이선스를 입력" / "Change 버튼을 클릭하고 새로운 라이선스를 입력" / "삭제하려는 라이선스를 선택한 후 Delete 버튼" / "라이선스 변경 시, XIPL 라이선스도 변경할 수 있습니다." |
| Service Manual p.43 `3.4 라이선스 등록하기` | VXvue 실행 중 "라이선스 등록 상태 확인"을 수행한다 / 라이선스 창의 Hardware Key로 발급받는다 |
| Service Manual p.51 그룹별 권한 | User 그룹도 System 그룹의 License 메뉴에 접근할 수 있다 |
| 사양서1 p.86 `VP-526 - Obtain Demo Image` | "VXvue Demo License 가 등록이 되어있어야 한다" — **F2 가상(데모) 촬영의 선행 조건** |
| 사양서1 p.90 `VP-529`, p.94 `VP-528 - Live View` | "Requires a registered Live View license to be used. Refer to Setting > System > License (VP-657 - License) for license registration." |
| 사양서2 p.57 `VP-616 - Integrated Image CAD` | "VUNO CXR(GPU/CPU) Requires A.I. (Computer Aided Detection) license registration in VXvue." / "CAD-CXR ... Requires VXCAD_CXR license registration in XIPL." |
| 사양서2 p.61 `VP-617` | "VXvue Option 라이선스(AI)의 만료일자는 고려하지 않는다." |

## 화면 구조 (2026-08-19 실측, `python run.py ui-probe` / work/probe_license.py)

```
System - License   (좌측 메뉴 System 대분류의 5번째 소분류, ctrl_id=5)
  GroupBox 20000 "License"
    Static 20000 "Hardware Key"   Edit 30089  (하드웨어 키 32자리 HEX, 읽기 전용 표시)
    ListCtrl 31116  헤더 SysHeader32 = "Name | License | Information"
      ListItem 1..N  (데이터 없는 행은 hidden — core/setting.list_rows()가 걸러낸다)
    TextButton 30881 Change / 30879 Add / 30880 Delete   (좌 -> 우)
```

## 판정 설계 — 왜 파일을 1차 근거로 쓰는가

목록 행은 owner-draw라 `GetWindowText`로 셀 텍스트를 읽을 수 없다(TC13/TC14,
DICOM Burning Option과 같은 한계). 그래서 두 근거를 함께 쓴다.

1. **파일이 1차 근거** — `<data_dir>\Database\license.lic`(본체),
   `Optionlicense<N>.lic`(옵션)에 라이선스 키가 **평문으로** 저장돼 있다(실측).
   키 값 대조는 이 파일로 한다. 정확하고 OCR 오인식이 없다.
2. **UI는 표시 검증** — 행 개수는 `list_rows()`로 속성 기반으로 세고(신뢰 가능),
   `Name`/`Information` 문구는 캡처+OCR로 읽는다. OCR은 `1`을 `L`로 읽는 등
   오인식이 있으므로(실측: 키 안의 숫자 `1`이 `L`로 읽혀 파일 값과 어긋났다) **키 대조의 근거로
   쓰지 않고**, `_normalize_key()`로 혼동쌍을 접어 비교한 뒤 그래도 다르면
   "OCR 한계"로 note에 남긴다 — FAIL로 단정하지 않는다.

즉 "UI에 무엇이 보이는가"와 "실제로 무엇이 설치돼 있는가"를 각각 다른 근거로
확인하고 서로 대조한다. 한쪽만 보고 판정하지 않는다.

## 보안 취급

하드웨어 키와 라이선스 키는 사내 자산이다(`VXvue/CLAUDE.md` 6절). 리포트에
남기는 값은 항상 `mask()`를 통과시켜 앞 4 / 뒤 4자만 남긴다. 원문 키를
`config.json`에 기대값으로 적지 않는다 — 기대값은 **라이선스 종류**(Demo /
CAD / Live View)로만 표현한다.
"""

import glob
import os
import re

SCREEN_TITLE = "System - License"

# 2026-08-19 실측 컨트롤 ID
HARDWARE_KEY_EDIT_ID = 30089
LICENSE_LIST_ID = 31116
CHANGE_BUTTON_ID = 30881
ADD_BUTTON_ID = 30879
DELETE_BUTTON_ID = 30880

# 라이선스 파일 위치. data_dir 하위 상대 경로만 상수로 둔다 — data_dir 자체는
# PC마다 다르므로(이 PC는 D:\Database, 다른 PC는 C:\Database일 수 있다)
# 호출부가 config.json의 `data_dir`을 넘긴다(core/dbreset.py와 같은 규칙).
LICENSE_SUBDIR = "Database"
MAIN_LICENSE_FILE = "license.lic"
OPTION_LICENSE_GLOB = "Optionlicense*.lic"

# 라이선스 키 형식(실측): 4-5-4-5 문자 그룹. OCR 결과에서 키를 뽑을 때 쓴다.
KEY_RX = re.compile(r"[A-Z0-9]{4}-[A-Z0-9]{5}-[A-Z0-9]{4}-[A-Z0-9]{5}")

# Information 열에서 라이선스 종류를 판별하는 문구. **사양서 원문 표기**를 그대로
# 쓴다(사양서1 p.7 "CAD and Live View", p.86 "VXvue Demo License",
# 사양서2 p.57 "A.I. (Computer Aided Detection)").
KIND_PATTERNS = (
    ("Demo",      re.compile(r"demo\s*licen[cs]e", re.I)),
    ("CAD",       re.compile(r"computer\s*aided\s*detect", re.I)),
    ("LiveView",  re.compile(r"live\s*view", re.I)),
)

# 만료일 표기(실측: "Demo License 2100-08-18(Shimadzu)")
EXPIRY_RX = re.compile(r"(\d{4})[-./](\d{2})[-./](\d{2})")

# OCR 혼동쌍. 키 비교에서만 접는다(표시 문구 판정에는 쓰지 않는다).
_OCR_FOLD = str.maketrans({"L": "1", "I": "1", "O": "0", "S": "5", "B": "8", "Z": "2"})


class LicenseError(RuntimeError):
    pass


def mask(value, head=4, tail=4):
    """라이선스/하드웨어 키를 리포트에 남길 형태로 가린다."""
    s = str(value or "").strip()
    if len(s) <= head + tail:
        return s
    return "%s...%s (%d자)" % (s[:head], s[-tail:], len(s))


def _normalize_key(text):
    """OCR 혼동 문자를 접어 키를 비교 가능한 형태로 만든다."""
    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper()).translate(_OCR_FOLD)


# --- 파일 근거 ---------------------------------------------------------
def license_dir(data_dir):
    return os.path.join(data_dir, LICENSE_SUBDIR)


def license_files(data_dir):
    """설치된 라이선스 파일을 읽어 리스트로 돌려준다.

    반환: [{"file": 파일명, "slot": "main"|"option0".., "key": 키}]

    옵션 파일은 **glob으로 찾는다.** 사양서1 p.7이 "VXvue Option license
    supports up to 16 options"라고 하므로 `Optionlicense0/1`만 이름으로
    박아 두면 옵션이 늘었을 때 조용히 누락된다(이 PC 실측은 0/1 두 개).
    """
    root = license_dir(data_dir)
    out = []
    main = os.path.join(root, MAIN_LICENSE_FILE)
    if os.path.isfile(main):
        out.append({"file": MAIN_LICENSE_FILE, "slot": "main",
                    "key": _read_key(main)})
    for path in sorted(glob.glob(os.path.join(root, OPTION_LICENSE_GLOB))):
        name = os.path.basename(path)
        out.append({"file": name,
                    "slot": os.path.splitext(name)[0].replace("Optionlicense", "option"),
                    "key": _read_key(path)})
    return out


def _read_key(path):
    import io
    try:
        return io.open(path, encoding="utf-8", errors="replace").read().strip()
    except OSError as exc:                                   # noqa: BLE001
        return "(읽기 실패: %s)" % exc


# --- UI 근거 -----------------------------------------------------------
def _tesseract(cfg):
    """pytesseract 모듈을 준비한다. 없으면 None."""
    try:
        import pytesseract
    except ImportError:
        return None
    exe = ((cfg or {}).get("xipl") or {}).get("tesseract_exe") \
        or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
    return pytesseract


def _ocr_line(pytesseract, bbox, scale=3, ui=None):
    """한 줄 영역을 확대해 OCR한다(작은 글씨의 인식률을 올리기 위해).

    `ui`가 있으면 캡처 직전 `ensure_foreground()`를 다시 불러 다른 창(터미널
    등)이 그 자리를 덮은 상태로 캡처되는 것을 막는다(실측 2026-08-21 —
    `core/screen.looks_contaminated()` 참고).
    """
    if ui is not None:
        ui.ensure_foreground()
    from PIL import ImageGrab
    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale))
    return pytesseract.image_to_string(img, config="--psm 7").strip()


def read_screen(ui, cfg, evidence_dir=None):
    """License 화면을 열고 표시 내용을 읽는다.

    반환:
      {
        "title": 상단 제목,
        "hardware_key": 하드웨어 키(원문 — 리포트에 넣을 때 mask() 필수),
        "header": 목록 헤더 OCR 결과,
        "row_count": 속성 기준 행 수(신뢰 가능),
        "slot_count": 행 슬롯 총 개수(hidden 포함),
        "rows": [{"index":1, "raw": OCR 원문, "key": 키, "kind": 종류,
                  "expiry": 만료일, "truncated": bool}],
        "buttons": {"change": bool, "add": bool, "delete": bool},
        "ocr_available": bool,
        "evidence": [캡처 경로...],
      }
    """
    from . import setting

    if setting.goto_screen(ui, SCREEN_TITLE) is None:
        raise LicenseError("Setting > %s 화면으로 이동하지 못했습니다." % SCREEN_TITLE)

    info = {"title": setting.title(ui), "hardware_key": "", "header": "",
            "row_count": 0, "slot_count": 0, "rows": [], "buttons": {},
            "ocr_available": False, "evidence": []}

    ctrls = setting.content_controls(ui, min_size=6, include_offscreen=True)
    for c in ctrls:
        if c.ctrl_id == HARDWARE_KEY_EDIT_ID and c.cls == "Edit":
            info["hardware_key"] = ui.get_text(c).strip()
            break

    present = set(c.ctrl_id for c in ctrls)
    info["buttons"] = {"change": CHANGE_BUTTON_ID in present,
                       "add": ADD_BUTTON_ID in present,
                       "delete": DELETE_BUTTON_ID in present}

    lists = [c for c in ctrls if c.ctrl_id == LICENSE_LIST_ID
             and c.text.strip() == "ListCtrl"]
    if not lists:
        raise LicenseError("라이선스 목록(ListCtrl %d)을 찾지 못했습니다."
                           % LICENSE_LIST_ID)
    lc = lists[0]
    info["slot_count"] = setting.list_row_slots(ui, lc)

    tess = _tesseract(cfg)
    info["ocr_available"] = tess is not None

    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        shot = os.path.join(evidence_dir, "license_screen.png")
        try:
            from PIL import ImageGrab
            ImageGrab.grab(bbox=lc.rect, all_screens=True).save(shot)
            info["evidence"].append(shot)
        except Exception:                                    # noqa: BLE001
            pass

    if tess is not None:
        from .ui import children
        for kid in children(lc.hwnd, 2):
            if kid.cls == "SysHeader32":
                info["header"] = _ocr_line(tess, kid.rect, ui=ui)
                break

    # 행 순회. 사양서1 p.7이 옵션 최대 16개를 허용하므로 스크롤이 필요할 수
    # 있다 — 슬롯보다 행이 많으면 iter_list_rows()가 스크롤해서 끝까지 간다.
    seen = []

    def on_row(_page, _index, row_ctrl):
        raw = _ocr_line(tess, row_ctrl.rect, ui=ui) if tess is not None else ""
        seen.append(_parse_row(len(seen) + 1, raw, row_ctrl.rect))

    setting.iter_list_rows(ui, lc, on_row)
    info["rows"] = seen
    info["row_count"] = len(seen)
    return info


def _parse_row(index, raw, rect):
    """행 OCR 원문에서 키/종류/만료일을 뽑는다."""
    from . import screen as screen_mod

    contaminated = screen_mod.looks_contaminated(raw)
    flat = raw.upper().replace(" ", "")
    keys = KEY_RX.findall(flat)
    kind = None
    for name, rx in KIND_PATTERNS:
        if rx.search(raw):
            kind = name
            break
    expiry = None
    m = EXPIRY_RX.search(raw)
    if m:
        expiry = "%s-%s-%s" % m.groups()
    return {"index": index, "raw": raw, "rect": rect,
            "key": keys[0] if keys else "",
            "kind": kind, "expiry": expiry,
            # 실측(2026-08-21): 다른 창이 이 행 자리를 덮은 캡처에서 나온
            # OCR 결과로 보이면 종류 판별 실패를 FAIL 근거로 쓰지 않는다
            # (core/screen.looks_contaminated()).
            "contaminated": contaminated,
            # Information 열이 목록 폭보다 길면 제품이 "..."로 줄여 그린다
            # (실측: "Demo License 2100-08-18(Shima...").
            "truncated": "..." in raw or "…" in raw}


# --- 판정 -------------------------------------------------------------
DEFAULT_REQUIRED = ("Demo", "CAD", "LiveView")

KIND_LABELS = {
    "Demo": "VXvue Demo License (사양서1 p.86 VP-526 — F2 가상 촬영 선행 조건)",
    "CAD": "A.I. Computer Aided Detection (사양서2 p.57 VP-616)",
    "LiveView": "Live View (사양서1 p.94 VP-528)",
}


def check(ui, cfg, result, first_step=1, evidence_dir=None):
    """`TCResult`에 라이선스 확인 Step을 채운다. 채운 Step 수를 반환한다.

    회귀 러너와 단독 CLI(`python run.py vxvue-license`)가 같은 코드를 쓰도록
    TCResult를 인자로 받는다.
    """
    from . import result as result_mod

    required = tuple((cfg.get("license") or {}).get("required") or DEFAULT_REQUIRED)
    data_dir = cfg.get("data_dir") or ""
    step = first_step

    # Step 1: 파일 기준 등록 상태 (1차 근거)
    files = license_files(data_dir) if data_dir else []
    if not data_dir:
        result.add(step, "라이선스 파일 확인", result_mod.MANUAL,
                   note="config.json의 data_dir이 비어 있어 파일 근거를 확인할 수 없다.")
    else:
        result.add(step, "라이선스 파일 확인 (%s)" % license_dir(data_dir),
                   result_mod.PASS if files else result_mod.FAIL,
                   expected="license.lic + Optionlicense*.lic 존재",
                   actual="; ".join("%s=%s" % (f["file"], mask(f["key"])) for f in files)
                          or "(파일 없음)",
                   note="키 값은 사내 자산이라 마스킹해 기록한다(CLAUDE.md 6절). "
                        "옵션 파일은 glob으로 찾는다 — 사양서1 p.7 'VXvue Option "
                        "license supports up to 16 options' 근거.")
    step += 1

    # Step 2: 화면 표시 내용
    try:
        info = read_screen(ui, cfg, evidence_dir=evidence_dir)
    except Exception as exc:                                 # noqa: BLE001
        from . import preflight as preflight_mod
        result.add(step, "System - License 화면 확인", result_mod.FAIL,
                   expected="화면 진입 및 목록 판독",
                   actual=str(exc),
                   note=preflight_mod.memory_pressure(cfg))
        return step - first_step + 1

    for path in info.get("evidence", []):
        result.attach(path)

    result.assert_equal(step, "Setting > System > License 화면 진입",
                        SCREEN_TITLE, info["title"],
                        note="Service Manual p.54 4.2.5 License 메뉴.")
    step += 1

    # Step 3: Hardware Key 표시
    hk = info["hardware_key"]
    result.add(step, "Hardware Key 표시", result_mod.PASS if hk else result_mod.FAIL,
               expected="Hardware Key 표시됨(비어 있지 않음)", actual=mask(hk),
               note="Service Manual p.43 3.4.2 — 이 Hardware Key로 라이선스를 "
                    "발급받는다. 값은 마스킹해 기록한다.")
    step += 1

    # Step 4: 버튼 3종 존재 (Service Manual p.54)
    btn = info["buttons"]
    result.add(step, "Add / Change / Delete 버튼 존재",
               result_mod.PASS if all(btn.values()) else result_mod.FAIL,
               expected="Add(%d) / Change(%d) / Delete(%d) 모두 존재"
                        % (ADD_BUTTON_ID, CHANGE_BUTTON_ID, DELETE_BUTTON_ID),
               actual=", ".join("%s=%s" % (k, v) for k, v in sorted(btn.items())),
               note="Service Manual p.54 4.2.5 — 추가/변경/삭제 버튼. "
                    "이 자동화는 존재만 확인하고 누르지 않는다(라이선스 변경은 "
                    "복구가 어려운 파괴적 조작).")
    step += 1

    # Step 5: 목록 행 수 == 파일 수
    if not info["ocr_available"]:
        result.add(step, "라이선스 목록 행 수", result_mod.MANUAL,
                   actual="행 %d개(속성 기준)" % info["row_count"],
                   note="pytesseract가 없어 행 내용을 읽지 못했다. 행 수만 확인함.")
    else:
        ok = info["row_count"] == len(files)
        result.add(step, "라이선스 목록 행 수 = 설치된 라이선스 파일 수",
                   result_mod.PASS if ok else result_mod.FAIL,
                   expected="%d개(파일 기준)" % len(files),
                   actual="%d개(화면 목록, 슬롯 %d)" % (info["row_count"], info["slot_count"]),
                   note="행은 owner-draw지만 ListItem 자식 윈도우로 존재하고 빈 행은 "
                        "hidden이므로 개수는 속성으로 정확히 센다"
                        "(core/setting.list_rows()).")
    step += 1

    # Step 6: 필요한 라이선스 종류가 모두 표시되는가
    found_kinds = [r["kind"] for r in info["rows"] if r["kind"]]
    missing = [k for k in required if k not in found_kinds]
    unknown = [r["index"] for r in info["rows"] if not r["kind"]]
    contaminated_rows = [r["index"] for r in info["rows"] if r.get("contaminated")]
    detail = "; ".join(
        "행%d %s%s" % (r["index"], r["kind"] or "(종류 판별 실패)",
                       " 만료 %s" % r["expiry"] if r["expiry"] else "")
        for r in info["rows"]) or "(행 없음)"
    if not info["ocr_available"]:
        result.add(step, "필요 라이선스 종류 표시", result_mod.MANUAL,
                   expected=", ".join(KIND_LABELS.get(k, k) for k in required),
                   note="OCR 불가로 Information 열을 읽지 못했다.")
    elif contaminated_rows and missing:
        # 실측(2026-08-21): 캡처 영역에 다른 창(터미널 등)이 겹쳐 OCR이 그
        # 창의 내용을 읽은 사례가 있었다 — 그 경우 종류 판별 실패를 제품
        # 결함으로 단정하지 않는다(core/screen.looks_contaminated()).
        result.add(step, "필요 라이선스 종류 표시 (%s)" % ", ".join(required),
                   result_mod.MANUAL,
                   expected=" / ".join(KIND_LABELS.get(k, k) for k in required),
                   actual=detail,
                   note="행 %s의 캡처가 다른 창(터미널 등)에 오염된 것으로 "
                        "보여 판별 실패를 FAIL로 단정하지 않는다 — 재실행해서 "
                        "재확인할 것(누락 판정: %s)." % (contaminated_rows, ", ".join(missing)))
    else:
        result.add(step, "필요 라이선스 종류 표시 (%s)" % ", ".join(required),
                   result_mod.PASS if not missing else result_mod.FAIL,
                   expected=" / ".join(KIND_LABELS.get(k, k) for k in required),
                   actual=detail,
                   note=("누락: %s. " % ", ".join(missing) if missing else "")
                        + ("종류를 판별하지 못한 행: %s. " % unknown if unknown else "")
                        + "Information 열의 문구로 판별한다(사양서1 p.7 — 현재 "
                          "지원되는 VXvue Option은 CAD와 Live View뿐).")
    step += 1

    # Step 7: 파일 키 <-> 화면 키 대조 (OCR 한계를 정직하게 남긴다)
    if not info["ocr_available"]:
        result.add(step, "파일 키와 화면 표시 키 대조", result_mod.MANUAL,
                   note="OCR 불가.")
    else:
        file_keys = dict((_normalize_key(f["key"]), f["file"]) for f in files)
        matched, unmatched = [], []
        for r in info["rows"]:
            norm = _normalize_key(r["key"])
            if norm and norm in file_keys:
                matched.append("행%d=%s" % (r["index"], file_keys[norm]))
            else:
                unmatched.append("행%d(%s)" % (r["index"], mask(r["key"]) or "키 판독 실패"))
        all_matched = len(matched) == len(info["rows"]) and not unmatched
        result.add(step, "화면 표시 키가 설치된 라이선스 파일과 일치",
                   result_mod.PASS if all_matched else result_mod.MANUAL,
                   expected="모든 행이 license.lic / Optionlicense*.lic 중 하나와 일치",
                   actual="일치 %d건(%s)%s" % (len(matched), ", ".join(matched),
                                             " / 불일치 %s" % ", ".join(unmatched)
                                             if unmatched else ""),
                   note="OCR은 `1`을 `L`로 읽는 등 오인식이 있다(실측: 키 안의 "
                        "숫자 1이 L로 읽혀 파일 값과 어긋났다). 그래서 "
                        "혼동쌍(1/L/I, 0/O, 5/S, 8/B, 2/Z)을 접어 "
                        "비교하고, 그래도 불일치면 FAIL이 아니라 MANUAL로 남긴다 — "
                        "키의 1차 근거는 파일이고 화면은 표시 검증용이다.")
    step += 1

    # Step 8: Information 열 잘림 — 확인하지 못한 것을 확인하지 못했다고 남긴다
    truncated = [r["index"] for r in info["rows"] if r["truncated"]]
    if truncated:
        result.add(step, "Information 열 전체 문구", result_mod.MANUAL,
                   actual="행 %s의 Information이 목록 폭에 맞춰 '...'로 줄여 표시됨"
                          % truncated,
                   note="제품이 열 폭에 맞춰 줄여 그리므로 Company Code 등 뒷부분을 "
                        "읽을 수 없다(실측: 'Demo License 2100-08-18(Shima...'). "
                        "만료일까지는 읽히므로 종류·만료일 판정에는 영향이 없다. "
                        "구조적 한계다(2026-08-30 재검토) — 이 목록은 표준 리스트뷰가 "
                        "아니라 커스텀 MFC 컨트롤이라 열 폭 조정·hover 툴팁·더블클릭 "
                        "상세창·우클릭 메뉴가 전부 없고, 라이선스 파일에도 이 문구가 "
                        "없다(화면 전용 렌더링). 화면에서는 사람도 이 이상 읽을 수 "
                        "없다 — Company Code 확인이 꼭 필요하면 사양서1 p.7 표"
                        "(None=0, Shimadzu=1)와 발급 기록 등 다른 경로로 확인할 것.")
        step += 1

    # Step 9: Demo License 만료일 — 사양 근거를 그대로 남긴다
    demo = next((r for r in info["rows"] if r["kind"] == "Demo"), None)
    if demo is not None:
        result.add(step, "Demo License 만료일 표시", result_mod.PASS if demo["expiry"]
                   else result_mod.MANUAL,
                   expected="만료일이 목록에 표시됨",
                   actual=demo["expiry"] or "(판독 실패)",
                   note="사양서1 p.7: \"VXvue / DxWorks do not check the license "
                        "expiration date.\" — VXvue 자체는 만료일로 기능을 막지 않고, "
                        "15일 이내면 알림만 표시한다. 따라서 이 값은 **표시 확인**이며 "
                        "만료 임박 여부의 PASS/FAIL 기준으로 쓰지 않는다.")
        step += 1

    return step - first_step


def run_standalone(ui, cfg, evidence_dir=None):
    """`python run.py vxvue-license`용 단독 TCResult."""
    from . import result as result_mod
    r = result_mod.TCResult(
        "VXvue_License",
        "VXvue 자체 라이선스 확인 (Setting > System > License)")
    check(ui, cfg, r, first_step=1, evidence_dir=evidence_dir)
    return r.finalize()
