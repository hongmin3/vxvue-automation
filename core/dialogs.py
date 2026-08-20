# -*- coding: utf-8 -*-
r"""모달 팝업 판독·분류·처리 — 이 저장소의 **유일한** 팝업 처리 경로.

## 왜 이 모듈이 생겼나 (사용자 지적, 2026-08-20)

이 제품은 **모달 팝업이 떠 있으면 이후 클릭을 조용히 무시한다.** 그래서
"클릭했는데 화면이 안 바뀐다"의 첫 번째 원인은 거의 항상 팝업이다. 그런데
자동화가 그 대응을 세 곳에 따로 땜질해 놓았고(`setting.open_setting()`,
`workflow.goto()`, `workflow.pending_dialogs()`), 각자 조금씩 달랐다. 결과:

- Setting 좌측 메뉴를 9번 눌렀는데 화면 제목이 계속 `Study - General`이었다.
  진짜 원인은 앞선 `Update`가 남긴 `Info: "Study - General Update successfully."`
  팝업이었지만, 증상은 "메뉴 클릭이 안 먹는다"로 보였다.
- "New Procedure" 창이 닫히지 않은 채 남아 이후 TC가 전부 원인 불명으로 실패했다.

**그리고 더 나쁜 문제**: 팝업을 분류하지 않고 닫았다. 사용자 지적 —
*"팝업 클릭을 무지성으로 하지말고 fail이 난 팝업인지 그냥 성공업데이트 팝업인지도
확인 해서 처리해주는 걸로 해줘."* 성공 알림과 오류 팝업을 같은 방식으로 닫아
버리면 **오류가 조용히 사라진다** — QA 자동화에서 가장 하면 안 되는 일이다.

## 분류와 처리 방침

| 종류 | 판별 근거 | 처리 |
|---|---|---|
| `SUCCESS` | 문구에 `success` / `성공`, 또는 제목이 `Info`이고 버튼 1개 | 닫는다. 기록은 남기지만 판정을 바꾸지 않는다 |
| `ERROR` | 제목이 `Error`, 문구에 `error`/`fail`/`not exist`/`오류`/`실패` | 닫되 **판정에 반영해야 한다**. `blocking=True`로 표시해 호출부가 FAIL/MANUAL로 올리게 한다 |
| `WARNING` | 제목이 `Warning`, 문구에 `warning`/`경고` | 닫되 판정에 반영 |
| `QUESTION` | 버튼이 2개 이상(Yes/No/Cancel 등) | **닫지 않는다.** 어느 버튼이 옳은지는 사양이 정하므로 호출부가 결정해야 한다. 자동으로 누르면 제품 설정을 바꿀 수 있다(실측: Procedure Mapping에서 그렇게 Procedure가 생겼다) |
| `PROGRESS` | 진행률 표시 문구(`%`, `완료`, `중...`) | **닫지 않고 기다린다** |
| `INTERACTION` | Image Process 창, 확장 Tool 팔레트, DICOM 대기열 창 | 정상 기능·상태 화면. **제목줄 닫기(`-4`)로만** 닫는다 — 내부 버튼을 누르면 제품 상태가 바뀔 수 있다 |
| `UNKNOWN` | 위에 없음 | 닫되 `blocking=True`로 표시 — 모르는 팝업을 조용히 넘기지 않는다 |

`QUESTION`을 자동으로 닫지 않는 것이 이 설계의 핵심이다. 확인 팝업은 "예"와
"아니오"가 제품 상태를 다르게 만들기 때문에, **어느 쪽이 맞는지 아는 호출부만**
누를 수 있어야 한다(`workflow.start_study()`가 사양서1 p.38을 근거로 "No"를
택하는 것처럼).

## 문구를 못 읽을 때

이 제품의 팝업 본문은 owner-draw인 경우가 있어 `GetWindowText`가 빈 값을 준다
(실측: `Error` 팝업이 `(문구 미노출)`로 나왔다). **문구를 못 읽는 것과 모르는
팝업인 것은 다르다** — 그래서 캡처+OCR로 한 번 더 시도한 뒤에 분류한다.
실측 예: OCR로 `"Error x A Image process parameter file does not exist."`를 읽어
`ERROR`로 정확히 분류했다.

## 사용법

```python
from core import dialogs

# 조작 전에 길을 막는 팝업을 걷어낸다. 확인 팝업은 남겨 둔다(닫으면 위험).
records = dialogs.clear_blocking(ui, cfg)
if any(r.blocking for r in records):
    ...  # 판정에 반영

# 클릭이 먹지 않았을 때 원인 확인
if dialogs.present(ui):
    ...
```
"""

import os
import re
import time

SUCCESS = "SUCCESS"
ERROR = "ERROR"
WARNING = "WARNING"
QUESTION = "QUESTION"
PROGRESS = "PROGRESS"
INTERACTION = "INTERACTION"
UNKNOWN = "UNKNOWN"

# 제목줄 닫기 버튼. `dismiss_dialog()`로 안 닫히는 창(Cancel이 없는 창)에 쓴다.
TITLE_CLOSE_CTRL_ID = -4

_SUCCESS_RX = re.compile(r"success|성공|완료되었|저장되었", re.I)
_ERROR_RX = re.compile(r"\berror\b|\bfail(ed|ure)?\b|does not exist|not found|"
                       r"오류|실패|없습니다|잘못", re.I)
_WARNING_RX = re.compile(r"\bwarning\b|\bcaution\b|경고|주의", re.I)
_PROGRESS_RX = re.compile(r"\d+\s*%|복사 중|처리 중|중\.\.\.|progress", re.I)

# 제목만으로 판별되는 것 (문구를 못 읽어도 이만큼은 안다)
_TITLE_KIND = {"error": ERROR, "warning": WARNING, "caution": WARNING}
_INTERACTION_TITLE_RX = re.compile(r"^image\s+process(?:\s|\[|$)", re.I)

# 확장 Tool 팔레트를 알아보는 표지. **특정 이름 두 개를 순서대로 요구하면 안 된다** —
# 이 모듈의 OCR은 2배 확대 단일 패스라(팝업 문구용) 팔레트의 8px 라벨 대부분이
# 깨진다. 실측(2026-08-20 12:12 실행)에서 27개 툴 중 `Extra Tool`, `Soft Tissue`
# 둘만 살아남아 이전 정규식이 통과하지 못했고, 팔레트가 `UNKNOWN`(=blocking)으로
# 기록됐다. 그러면 호출부의 "오류 팝업 없음" 판정이 엉뚱하게 FAIL이 된다.
#
# 그래서 **이름 몇 개가 살아남았는지 센다.** 제목도 버튼도 없는 창에서 이 이름이
# 둘 이상 보이면 팔레트다. 전체 목록은 `workflow.KNOWN_TOOLS`에 있고, 여기에는
# 오류 문구에 우연히 나올 수 없는 **식별용 이름만** 둔다(계층 역전을 피하려고
# workflow를 import하지 않는다).
_PALETTE_NAMES = ("multi-send", "multisend", "ext.save", "extsave", "stitch",
                  "xipl", "retake", "move img", "target e.i", "orientation",
                  "ps image", "proc.", "get img", "full view", "extra tool",
                  "soft tissue", "live view", "compare", "save pro")
_PALETTE_MIN_HITS = 2

# DICOM 전송/인쇄 대기열 창(Pending List / Storage Queue / Print Queue).
# 제품이 Send 후 스스로 띄우며, **열린 채 남으면 이후 모든 조작을 삼킨다**
# (실측 2026-08-20: 이 창 하나 때문에 회귀에서 TC 7개가 연쇄 FAIL했다 —
# Setting 진입 실패, MWL 조회 0/0, 촬영 영상 0장). 확인을 묻는 창이 아니라
# 상태를 보여주는 창이므로 닫아야 한다.
#
# 실측 구조: `#32770` / 제목 없음 / 제목줄 닫기 `-4` / 동작 버튼 `30651`,
# `30642` / 목록 `31098`(Storage Queue), `31099`(Print Queue).
# 버튼이 2개라 예전에는 `QUESTION`으로 분류돼 **닫지 않고 남겨졌다.**
_QUEUE_RX = re.compile(r"storage\s*queue|print\s*queue|pending\s*list", re.I)
QUEUE_LIST_IDS = (31098, 31099)


def _palette_hits(message):
    """팝업 문구에서 알아본 팔레트 툴 이름의 개수."""
    blob = " ".join((message or "").split()).lower()
    return sum(1 for name in _PALETTE_NAMES if name in blob)


class DialogRecord:
    """팝업 하나를 어떻게 처리했는지의 기록.

    `blocking`은 "이 팝업이 판정에 영향을 줘야 한다"는 뜻이다 — 호출부가 이걸
    보고 FAIL/MANUAL로 올린다. 성공 알림은 False, 오류·경고·모르는 팝업은 True.
    """

    def __init__(self, title, message, kind, action, evidence=None):
        self.title = title
        self.message = message
        self.kind = kind
        self.action = action                  # "closed" / "left_open" / "close_failed"
        self.evidence = evidence

    @property
    def blocking(self):
        return self.kind in (ERROR, WARNING, UNKNOWN)

    def as_dict(self):
        return {"title": self.title, "message": self.message, "kind": self.kind,
                "action": self.action, "evidence": self.evidence,
                "blocking": self.blocking}

    def __repr__(self):
        text = ("%s: %s" % (self.title, self.message)).strip(": ")
        return "[%s/%s] %s" % (self.kind, self.action, text[:120])

    def __str__(self):
        return repr(self)


def present(ui):
    """지금 모달 팝업이 떠 있는가."""
    return ui.dialog() is not None


def read(ui, dlg, cfg=None):
    """팝업의 제목·문구·버튼 수를 읽는다.

    문구는 표준 API로 먼저 읽고, 비어 있으면 **캡처+OCR로 한 번 더** 시도한다.
    문구를 못 읽는 것과 모르는 팝업인 것은 다르다.

    반환: {"title", "message", "buttons": n, "ocr_used": bool}
    """
    from .ui import children

    title = (dlg.text or "").strip()
    message = (ui.dialog_text(dlg) or "").strip()
    ocr_used = False
    if not message or message == "(문구 미노출)":
        ocr = _ocr(dlg, cfg)
        if ocr:
            message, ocr_used = ocr, True

    buttons = [c for c in children(dlg.hwnd, 3)
               if (c.text.strip() in ("TextButton", "Button") or c.cls == "Button")
               and c.size[0] >= 40 and c.size[1] >= 18 and c.visible]
    return {"title": title, "message": message, "buttons": len(buttons),
            "ocr_used": ocr_used}


def _ocr(dlg, cfg=None):
    try:
        import pytesseract
        from PIL import ImageGrab
    except ImportError:
        return ""
    exe = ((cfg or {}).get("xipl") or {}).get("tesseract_exe") \
        or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
    try:
        img = ImageGrab.grab(bbox=dlg.rect, all_screens=True)
        img = img.resize((img.width * 2, img.height * 2))
        return " ".join(pytesseract.image_to_string(img).split())
    except Exception:                                    # noqa: BLE001
        return ""


def classify(info):
    """읽은 내용으로 팝업 종류를 판별한다.

    순서가 중요하다.
    1. 진행률 팝업은 닫으면 안 되므로 가장 먼저 가려낸다.
    2. 오류·경고는 성공보다 먼저 본다 — "Update failed successfully"처럼 두
       단어가 함께 나오는 문구에서 성공으로 오판하지 않기 위함이다.
    3. 버튼이 2개 이상이면 확인 팝업이다. 단, 오류·경고로 이미 판별된 것은
       그대로 둔다(오류 팝업에 Retry/Cancel이 함께 있을 수 있다).
    """
    title = (info.get("title") or "").strip().lower()
    message = info.get("message") or ""
    blob = "%s %s" % (title, message)

    if _PROGRESS_RX.search(blob):
        return PROGRESS
    # Proc. 툴이 여는 파라미터 조작 창은 오류 알림이 아니라 정상 기능 화면이다.
    # 일반 팝업 가드가 UNKNOWN으로 분류하면 정상 진입을 blocking 오류처럼 기록한다.
    if _INTERACTION_TITLE_RX.search((info.get("title") or "").strip()):
        return INTERACTION
    # Tools ≡의 owner-draw 팔레트는 `ui.dialog()`에 잡히지만 오류 팝업이 아니다.
    # 표준 버튼/제목이 없고 고유 툴 이름 조합이 OCR되면 정상 상호작용 창이다.
    if (not title and info.get("buttons", 0) == 0
            and _palette_hits(message) >= _PALETTE_MIN_HITS):
        return INTERACTION
    # 대기열 창은 버튼이 2개라 확인 팝업처럼 보이지만 물어보는 창이 아니다.
    # 제목이 없고 대기열 목록 문구가 보이면 상태 창이다.
    if not title and _QUEUE_RX.search(" ".join(message.split())):
        return INTERACTION
    for key, kind in _TITLE_KIND.items():
        if key in title:
            return kind
    if _ERROR_RX.search(blob):
        return ERROR
    if _WARNING_RX.search(blob):
        return WARNING
    if info.get("buttons", 0) >= 2:
        return QUESTION
    if _SUCCESS_RX.search(blob):
        return SUCCESS
    # 제목이 Info이고 버튼이 하나면 알림이다(실측: "... Update successfully."가
    # 이 형태이고, 문구를 못 읽어도 버튼 수로 알림임을 알 수 있다).
    if title in ("info", "information", "알림") and info.get("buttons", 0) <= 1:
        return SUCCESS
    return UNKNOWN


def _close_by_title_bar(ui, dlg):
    """제목줄 닫기 버튼(`-4`)만 눌러 창을 닫는다. 버튼을 찾았으면 True."""
    from .ui import children
    closer = [c for c in children(dlg.hwnd, 2)
              if c.ctrl_id == TITLE_CLOSE_CTRL_ID and c.visible
              and c.size[0] > 0 and c.size[1] > 0]
    if not closer:
        return False
    ui.click(closer[0], settle=0.6)
    return True


def handle_one(ui, cfg=None, evidence_dir=None, tag="", close_questions=False):
    """떠 있는 팝업 하나를 분류해 처리한다. 없으면 None.

    `close_questions=False`(기본)면 **확인 팝업과 진행률 팝업은 닫지 않고**
    `action="left_open"`으로 돌려준다 — 어느 버튼이 옳은지는 사양이 정하므로
    호출부가 결정해야 한다.
    """
    dlg = ui.dialog()
    if dlg is None:
        return None

    info = read(ui, dlg, cfg)
    kind = classify(info)

    evidence = None
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        evidence = os.path.join(evidence_dir, "dialog_%s%s.png"
                                % (kind.lower(), ("_" + tag) if tag else ""))
        try:
            ui.capture_dialog(dlg, evidence)
        except Exception:                                # noqa: BLE001
            evidence = None

    if kind in (QUESTION, PROGRESS) and not close_questions:
        return DialogRecord(info["title"], info["message"], kind, "left_open", evidence)

    before = dlg.hwnd
    # **INTERACTION 창은 제목줄 닫기를 먼저 쓴다.** `dismiss_dialog()`는
    # ctrl_id 500/1/2를 확인 버튼으로 보고 누르는데, 대기열 창에는 그 ID를 가진
    # 목록 항목·스크롤이 있어서(실측 2026-08-20) 엉뚱한 것을 누른다. 게다가 이
    # 창의 동작 버튼(`30651`/`30642`)은 어느 쪽이 무엇인지 확정하지 않았으므로
    # 누르면 대기 중인 전송을 지울 수 있다 — 제목줄 닫기만 안전하다.
    if kind == INTERACTION and _close_by_title_bar(ui, dlg):
        time.sleep(0.3)
        if (ui.dialog() or dlg).hwnd != before or ui.dialog() is None:
            return DialogRecord(info["title"], info["message"], kind,
                                "closed", evidence)
    ui.dismiss_dialog(timeout=3)
    time.sleep(0.4)
    still = ui.dialog()
    action = "closed"
    if still is not None and still.hwnd == before:
        # Cancel이 없어 dismiss로 안 닫히는 창이 있다(실측: "New Procedure").
        # 아무 버튼이나 누르지 않고 **제목줄 닫기 버튼만** 쓴다 — Add를 누르면
        # 제품 설정이 바뀐다.
        from .ui import children
        closer = [c for c in children(before, 2) if c.ctrl_id == TITLE_CLOSE_CTRL_ID]
        if closer:
            ui.click(closer[0], settle=1.0)
            time.sleep(0.4)
        again = ui.dialog()
        if again is not None and again.hwnd == before:
            action = "close_failed"
    return DialogRecord(info["title"], info["message"], kind, action, evidence)


def clear_blocking(ui, cfg=None, evidence_dir=None, max_iters=4, tag="",
                   close_questions=False):
    """조작을 막는 팝업을 걷어낸다. 처리 기록 리스트를 반환한다.

    확인·진행률 팝업을 만나면 **그 자리에서 멈춘다** — 닫지 않고 남겨 두므로
    계속 돌면 같은 팝업을 무한히 다시 읽게 된다. 호출부가 그 기록을 보고
    사양에 맞는 버튼을 누르거나 기다려야 한다.

    반환된 기록 중 `blocking=True`가 있으면 **판정에 반영해야 한다.**
    """
    out = []
    for i in range(max_iters):
        rec = handle_one(ui, cfg, evidence_dir, tag="%s%d" % (tag, i + 1),
                         close_questions=close_questions)
        if rec is None:
            break
        out.append(rec)
        if rec.action in ("left_open", "close_failed"):
            break
    return out


def summarize(records):
    """판정 note에 넣을 한 줄 요약. 팝업이 없었으면 빈 문자열."""
    if not records:
        return ""
    parts = []
    for r in records:
        text = ("%s: %s" % (r.title, r.message)).strip(": ") or "(문구 미노출)"
        parts.append("[%s/%s] %s" % (r.kind, r.action, text[:160]))
    return " / ".join(parts)


def blocking_records(records):
    return [r for r in records if r.blocking]


def wait_until_clear(ui, cfg=None, timeout=60, poll=2.0, evidence_dir=None):
    """진행률 팝업이 사라질 때까지 기다린 뒤 남은 팝업을 처리한다.

    파일 복사·Export처럼 오래 걸리는 조작 뒤에 쓴다. 진행률 팝업을 닫으면
    작업이 취소되므로 기다리는 것이 유일하게 옳다.
    """
    end = time.time() + timeout
    while time.time() < end:
        dlg = ui.dialog()
        if dlg is None:
            return []
        if classify(read(ui, dlg, cfg)) != PROGRESS:
            break
        time.sleep(poll)
    return clear_blocking(ui, cfg, evidence_dir=evidence_dir)
