# -*- coding: utf-8 -*-
r"""VXvue의 표 목록을 **열 이름과 셀 값으로** 읽는다 — 어느 화면·팝업이든.

사용자 지시(2026-08-21): *"import 후 합불 판단은 각 열의 정보가 export 한 정보와
동일하게 나오면 될 것 같은데, 만약 열의 크기가 좁아서 `...`으로 개행이 되는 건
행의 크기를 넓히도록 해줘. 이건 core 함수로 구현해서 어디 탭이든지 사용할 수
있도록 해줘 — 레지스트레이션이나 데이터베이스나 어떤 팝업이든지."*

## 이 모듈이 푸는 문제

VXvue의 목록(`ListCtrl`)은 행이 `ListItem`이라는 **텍스트 없는 자식 창**이다
(`core/setting.list_rows()` docstring). 그래서 셀 값은 캡처+OCR로만 읽을 수 있다.
그런데 열 폭이 좁으면 제품이 값을 `ACC_VX_AUT...`처럼 **잘라 그린다** — 그 상태로
OCR하면 잘린 값을 진짜 값으로 착각해 "export한 값과 다르다"는 잘못된 FAIL이 난다.

핵심은 목록의 헤더가 **표준 `SysHeader32`** 라는 점이다. 실측(2026-08-21,
Database 목록)에서 `HDM_GETITEMCOUNT`가 14를 돌려주고 열 이름과 x 범위를 전부
정확히 읽었다.

```
Column(0, 'Study Key', w=39, x=18..57)      Column(7, 'Acc. No.', w=85, x=618..703)
Column(2, 'Patient ID', w=143, x=174..317)  Column(8, 'Study Description', ...)
```

그래서 **열 식별에는 OCR을 쓰지 않는다** — 헤더 라벨이 잘려 보여도 이름을 아는 데
지장이 없고, 헤더를 미리 넓힐 이유도 없다. OCR은 셀 값에만, 그것도 열 경계로
잘라 낸 한 칸에만 쓴다.

## 폭을 넓히는 방법 — 헤더 경계선 드래그 (사용자 선택, 2026-08-21)

`HDM_SETITEMW`로 폭 값만 바꾸면 owner-draw 목록이 셀을 다시 그리지 않을 수 있어
"헤더는 넓어졌는데 값은 여전히 잘린" 상태가 될 수 있다. 그래서 **헤더 경계선을
마우스로 드래그**한다 — 제품 자신의 재배치 로직을 타므로 반영이 보장된다.

넓히는 시점도 사용자 지시에 맞춘다: **검색이 끝나 목록이 채워진 뒤**, 잘려 보이는
셀이 있는 열만, 한 번에 한 열씩 넓혔다가 **원래 폭으로 되돌린다.** 화면 좌표를
저장해 재사용하지 않고 매번 헤더에서 다시 계산하므로 CLAUDE.md 3절의 좌표 규칙에
어긋나지 않는다.

## 쓰는 곳

Registration/Database 목록, Import Study 팝업 목록처럼 `ListCtrl` + `SysHeader32`
조합이면 어디든 같다.

    from core.listgrid import ListGrid
    grid = ListGrid(ui, list_ctrl)          # list_ctrl: by_id(ui, 31191)[0] 등
    for row in grid.read_rows():
        print(row["Patient ID"], row["Acc. No."])
"""

import ctypes
import os
import time
from ctypes import wintypes

from . import winmsg
from .ui import children

HDM_FIRST = 0x1200
HDM_GETITEMCOUNT = HDM_FIRST + 0
HDM_GETITEMRECT = HDM_FIRST + 7
HDM_GETITEMW = HDM_FIRST + 11

HDI_WIDTH = 0x0001
HDI_TEXT = 0x0002

HEADER_CLASS = "SysHeader32"
TEXT_MAX = 260

# 잘린 셀을 알아보는 표시. 제품은 말줄임표를 `...`(점 3개)로 그리고, OCR은 그것을
# `..` 또는 `…`로 흘려 읽기도 한다(실측). 값 끝에 점이 둘 이상 붙어 있으면 잘린
# 것으로 본다.
TRUNCATION_MARKS = ("...", "\u2026", "..")

WIDEN_STEP = 220          # 한 번에 넓히는 px
WIDEN_ROUNDS = 2          # 그래도 잘리면 한 번 더
DIVIDER_GRAB_INSET = 1    # 경계선을 잡을 때 x를 이만큼 왼쪽으로


class HDITEMW(ctypes.Structure):
    _fields_ = [("mask", wintypes.UINT),
                ("cxy", ctypes.c_int),
                ("pszText", ctypes.c_void_p),
                ("hbm", ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int),
                ("fmt", ctypes.c_int),
                ("lParam", ctypes.c_void_p),
                ("iImage", ctypes.c_int),
                ("iOrder", ctypes.c_int),
                ("type", wintypes.UINT),
                ("pvFilter", ctypes.c_void_p),
                ("state", wintypes.UINT)]


class Column(object):
    __slots__ = ("index", "name", "width", "left", "right")

    def __init__(self, index, name, width, left, right):
        self.index, self.name, self.width = index, name, width
        self.left, self.right = left, right

    def __repr__(self):
        return ("Column(%d, %r, w=%d, x=%s..%s)"
                % (self.index, self.name, self.width, self.left, self.right))


class ListGridError(RuntimeError):
    pass


def _tess():
    import pytesseract
    exe = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(exe):
        pytesseract.pytesseract.tesseract_cmd = exe
    return pytesseract


def looks_truncated(value):
    """셀 값이 잘려 보이는가."""
    v = (value or "").strip()
    if not v:
        return False
    return any(v.endswith(m) for m in TRUNCATION_MARKS) or "..." in v


class ListGrid(object):
    """`ListCtrl` 하나를 표로 다룬다."""

    def __init__(self, ui, list_ctrl):
        self.ui = ui
        self.list = list_ctrl
        self.header = next((c for c in children(list_ctrl.hwnd, 3)
                            if c.cls == HEADER_CLASS), None)
        if self.header is None:
            raise ListGridError("목록(%s) 안에서 %s 헤더를 찾지 못했다."
                                % (list_ctrl.ctrl_id, HEADER_CLASS))

    # --- 헤더 -------------------------------------------------------
    def column_count(self):
        return int(winmsg.send(self.header.hwnd, HDM_GETITEMCOUNT) or 0)

    def columns(self):
        """열 목록 — 이름과 **화면 좌표** x 범위. 매번 새로 읽는다."""
        n = self.column_count()
        if not n:
            return []
        size = ctypes.sizeof(HDITEMW) + TEXT_MAX * 2 + ctypes.sizeof(wintypes.RECT)
        out = []
        with winmsg.RemoteMem(self.header.hwnd, size) as mem:
            text_off = ctypes.sizeof(HDITEMW)
            rect_off = text_off + TEXT_MAX * 2
            for i in range(n):
                item = HDITEMW()
                item.mask = HDI_TEXT | HDI_WIDTH
                item.pszText = ctypes.c_void_p(mem.addr + text_off)
                item.cchTextMax = TEXT_MAX
                mem.write(0, item)
                name, width = "", 0
                if winmsg.send(self.header.hwnd, HDM_GETITEMW, i, mem.addr):
                    width = mem.read_into(0, HDITEMW()).cxy
                    name = mem.read_text(text_off, TEXT_MAX)
                mem.write(rect_off, wintypes.RECT())
                left = right = None
                if winmsg.send(self.header.hwnd, HDM_GETITEMRECT, i,
                               mem.addr + rect_off):
                    got = mem.read_into(rect_off, wintypes.RECT())
                    left = self.header.rect[0] + got.left
                    right = self.header.rect[0] + got.right
                out.append(Column(i, name.strip(), width, left, right))
        return out

    def column(self, index):
        return next((c for c in self.columns() if c.index == index), None)

    def drag_column_edge(self, index, delta, settle=0.35):
        """열 `index`의 **오른쪽 경계선을 드래그**해 폭을 `delta`만큼 바꾼다.

        `HDM_SETITEMW`로 폭 값만 바꾸지 않는 이유는 모듈 docstring 참고 —
        owner-draw 목록이 셀을 다시 그리지 않을 수 있다. 드래그 목표 x는 목록의
        오른쪽 안쪽으로 제한한다(창 밖으로 끌면 드래그가 취소된다).

        반환: 드래그 후 실제 폭(못 찾으면 None).
        """
        col = self.column(index)
        if col is None or col.right is None:
            return None
        y = (self.header.rect[1] + self.header.rect[3]) // 2
        start_x = col.right - DIVIDER_GRAB_INSET
        limit = self.list.rect[2] - 6
        end_x = min(start_x + delta, limit) if delta > 0 else max(start_x + delta,
                                                                 col.left + 12)
        if end_x == start_x:
            return col.width
        self.ui.drag((start_x, y), (end_x, y), settle=settle)
        fresh = self.column(index)
        return fresh.width if fresh else None

    def set_column_width_by_drag(self, index, width, settle=0.35):
        """드래그로 열 폭을 `width`에 맞춘다(되돌릴 때 쓴다)."""
        col = self.column(index)
        if col is None:
            return None
        return self.drag_column_edge(index, int(width) - col.width, settle=settle)

    # --- 행 ---------------------------------------------------------
    def rows(self):
        """보이는 실제 행(`ListItem`). 데이터 없는 행은 hidden이다."""
        out = [c for c in children(self.list.hwnd, 3)
               if c.text.strip() == "ListItem" and c.visible]
        return sorted(out, key=lambda c: c.rect[1])

    def _row_at(self, top, tolerance=3):
        return next((r for r in self.rows()
                     if abs(r.rect[1] - top) <= tolerance), None)

    # --- 셀 값 ------------------------------------------------------
    def cell_text(self, row_rect, col, scale=4, pad=3):
        """열 경계로 잘라 낸 셀 하나만 OCR한다(psm 7 — 항상 한 줄)."""
        from PIL import ImageGrab
        pytesseract = _tess()
        if col.left is None or col.right is None:
            return ""
        x1 = max(col.left + pad, self.list.rect[0])
        x2 = min(col.right - pad, self.list.rect[2])
        if x2 - x1 < 6:
            return ""
        img = ImageGrab.grab(bbox=(x1, row_rect[1] + 1, x2, row_rect[3] - 1),
                             all_screens=True)
        big = img.resize((img.width * scale, img.height * scale))
        return " ".join(pytesseract.image_to_string(
            big, config="--psm 7").split())

    def read_row(self, row, columns=None, widen=True, want=None):
        """행 하나를 `{열이름: 값}`으로 읽는다.

        `widen=True`면 잘려 보이는 셀이 있는 열만 경계선 드래그로 넓혀 다시 읽고
        **원래 폭으로 되돌린다.** `want`(열 이름 집합)를 주면 그 열만 넓힌다 —
        판정에 쓰지 않는 열까지 건드리지 않으려는 것이다.

        반환값에는 `_truncated` 키로 끝까지 잘린 채 남은 열 목록이 담긴다.
        잘린 값을 완전한 값처럼 판정에 쓰지 않기 위한 표시다.
        """
        cols = columns if columns is not None else self.columns()
        values = {}
        for col in cols:
            if col.name:
                values[col.name] = self.cell_text(row.rect, col)
        if not widen:
            values["_truncated"] = [c.name for c in cols
                                    if c.name and looks_truncated(values.get(c.name))]
            return values

        row_top = row.rect[1]
        still = []
        for col in cols:
            if not col.name:
                continue
            # 잘려 보이는 셀뿐 아니라 **판정에 쓸 열이 빈 값으로 읽힌 경우도**
            # 넓혀 다시 읽는다. 실측 2026-08-21: Database 목록의 `Age`(폭 30)는
            # 잘린 표시 없이 그냥 빈 문자열로 읽혔다 — 빈 판독을 그대로 믿으면
            # 기대값과 다르다는 잘못된 FAIL이 난다.
            wanted = want is None or col.name in want
            value = values.get(col.name)
            if not (looks_truncated(value) or (wanted and not value)):
                continue
            if not wanted:
                still.append(col.name)
                continue
            original = col.width
            try:
                for _ in range(WIDEN_ROUNDS):
                    if self.drag_column_edge(col.index, WIDEN_STEP) is None:
                        break
                    fresh_col = self.column(col.index)
                    fresh_row = self._row_at(row_top)
                    if fresh_col is None or fresh_row is None:
                        break
                    text = self.cell_text(fresh_row.rect, fresh_col)
                    if text:
                        values[col.name] = text
                    if text and not looks_truncated(text):
                        break
                else:
                    pass
            finally:
                self.set_column_width_by_drag(col.index, original)
                time.sleep(0.1)
            if looks_truncated(values.get(col.name)):
                still.append(col.name)
        values["_truncated"] = still
        return values

    def find_row(self, column_name, want, columns=None):
        """`column_name` 열의 값이 `want`인 행을 찾아 돌려준다.

        사용자 지시(2026-08-21): *"실제 export 를 할 때도 내가 원하는 Study를
        export 하는지 확인하는 것도 step에 추가해 주고 확인해 주라. 그냥 무지성으로
        제일 상단에 있는 거 export 하지 말고."* — 목록의 첫 행을 그대로 쓰면
        **이전 실행의 오래된 스터디를 대상으로 삼는 사고**가 난다(실제 발생:
        `Result_20260821_150508`에서 새 스터디가 닫히지 않아 DB에 없었고, 첫 행에
        있던 옛 스터디가 Export됐다).

        속도를 위해 **먼저 넓히지 않고** 모든 행의 그 열만 읽는다(행당 OCR 1회).
        잘려 보이는 값은 접두로 후보에 넣고, 후보가 남으면 그 열을 **한 번만**
        넓혀 후보 행들만 다시 읽어 확정한 뒤 원래 폭으로 되돌린다.

        반환: {"row", "value", "index", "candidates", "read", "note"}
        """
        cols = columns if columns is not None else self.columns()
        col = next((c for c in cols if c.name == column_name), None)
        if col is None:
            return {"row": None, "value": None, "index": None, "candidates": [],
                    "read": [], "note": "열 '%s'이 목록에 없다(있는 열: %s)."
                                        % (column_name,
                                           [c.name for c in cols if c.name])}
        rows = self.rows()
        nw = _norm(want)
        read, exact, partial = [], [], []
        for i, row in enumerate(rows):
            v = self.cell_text(row.rect, col)
            read.append(v)
            nv = _norm(v)
            if nv and nv == nw:
                exact.append((i, row, v))
            elif looks_truncated(v):
                core = _norm(str(v).split("...")[0].rstrip(". "))
                if core and nw.startswith(core):
                    partial.append((i, row, v))
        if len(exact) == 1:
            i, row, v = exact[0]
            return {"row": row, "value": v, "index": i,
                    "candidates": [i for i, _r, _v in exact], "read": read,
                    "note": "'%s' 열에서 %r을 %d행에서 찾았다(잘림 없음)."
                            % (column_name, want, i)}
        if not exact and not partial:
            return {"row": None, "value": None, "index": None, "candidates": [],
                    "read": read,
                    "note": ("'%s' 열에서 %r을 찾지 못했다. 읽은 값 %d건: %s"
                             % (column_name, want, len(read), read[:12]))}

        # 후보가 여럿이거나 잘려 있다 — 그 열을 한 번만 넓혀 확정한다.
        original = col.width
        cands = exact + partial
        tops = [r.rect[1] for _i, r, _v in cands]
        confirmed = None
        try:
            for _ in range(WIDEN_ROUNDS):
                if self.drag_column_edge(col.index, WIDEN_STEP) is None:
                    break
                fresh_col = self.column(col.index)
                if fresh_col is None:
                    break
                for (i, _row, _v), top in zip(cands, tops):
                    fresh_row = self._row_at(top)
                    if fresh_row is None:
                        continue
                    v2 = self.cell_text(fresh_row.rect, fresh_col)
                    if _norm(v2) == nw:
                        confirmed = (i, top, v2)
                        break
                if confirmed:
                    break
        finally:
            self.set_column_width_by_drag(col.index, original)
            time.sleep(0.1)
        if confirmed is None:
            return {"row": None, "value": None, "index": None,
                    "candidates": [i for i, _r, _v in cands], "read": read,
                    "note": ("'%s' 열을 넓혀 다시 읽어도 %r과 정확히 일치하는 행이 "
                             "없었다. 후보 행 %s / 읽은 값: %s"
                             % (column_name, want,
                                [i for i, _r, _v in cands], read[:12]))}
        idx, top, value = confirmed
        row = self._row_at(top)
        return {"row": row, "value": value, "index": idx,
                "candidates": [i for i, _r, _v in cands], "read": read,
                "note": ("'%s' 열을 넓혀 %r을 %d행에서 확정했다(후보 %s)."
                         % (column_name, want, idx,
                            [i for i, _r, _v in cands]))}

    def read_rows(self, widen=True, limit=None, want=None):
        cols = self.columns()
        out = []
        for i, row in enumerate(self.rows()):
            if limit is not None and i >= limit:
                break
            out.append(self.read_row(row, columns=cols, widen=widen, want=want))
        return out


def _norm(s):
    """대소문자·공백·구분자를 무시한 비교용 정규화.

    제품이 DICOM `AUTO^VXVUE^^^`를 목록에서는 `AUTO VXVUE`로, 생년월일
    `19800101`을 `1980-01-01`로 다르게 그리기 때문이다(실측).
    """
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def compare_row(values, expected):
    """`{열이름: 값}`을 기대값과 대조한다.

    `expected`는 `{열이름: 기대문자열}`이다. 비교는 대소문자·공백·구분자를
    무시한다 — 제품이 DICOM `AUTO^VXVUE^^^`를 목록에서는 `AUTO VXVUE`로,
    생년월일 `19800101`을 `1980-01-01`로 다르게 그리기 때문이다(실측).

    **끝까지 잘린 열(`_truncated`)은 일치로 세지 않는다.** 잘린 값이 기대값의
    앞부분과 같아도 `partial`로 따로 담아, 판정에서 "완전 일치"와 구분한다.

    반환: {"ok", "matched", "partial", "mismatched", "missing"}
    """
    norm = _norm

    truncated = set(values.get("_truncated") or [])
    matched, partial, mismatched, missing = {}, {}, {}, []
    for name, want in (expected or {}).items():
        if name not in values:
            missing.append(name)
            continue
        got = values.get(name)
        nw, ng = norm(want), norm(got)
        if not nw:
            continue
        if name in truncated:
            core = norm(str(got).split("...")[0])
            if core and nw.startswith(core):
                partial[name] = (want, got)
            else:
                mismatched[name] = (want, got)
        elif nw in ng or ng in nw:
            matched[name] = got
        else:
            mismatched[name] = (want, got)
    return {"ok": not mismatched and not missing and not partial,
            "matched": matched, "partial": partial,
            "mismatched": mismatched, "missing": missing}
