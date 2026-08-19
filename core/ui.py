# -*- coding: utf-8 -*-
"""VXvue UI 드라이버.

VXvue.exe는 Bellalun VIEWER.exe와 같은 사내 UI SDK 계열(AfxWnd140u 커스텀
렌더링)이다. Bellalun `auto/core/ui.py`의 구조를 그대로 따르되, 실측으로
확인한 **VXvue 고유의 함정** 두 가지를 모듈 차원에서 흡수한다.

1. Update/저장 직후 뜨는 모달 Info 팝업(`#32770`, 제목 "Info")을 닫기 전에는
   그 뒤의 모든 클릭이 조용히 무시된다  -> `dismiss_info()` / `click_and_ack()`
2. Edit 필드에서 Ctrl+A 전체선택이 항상 통하지 않는다(IP 필드에서 기존 값 뒤에
   이어붙어 깨짐)  -> `clear_edit()`는 End 이동 후 Backspace 반복으로 비운다.

또 Setting의 일부 화면(DICOM > Storage 등)은 대상 버튼이 스크롤 아래에 있어
좌표 고정이 불가능하다 -> `find_scrolling()`으로 대상이 보일 때까지 스크롤한다.

중요: VXvue는 관리자 권한으로 동작한다. 이 모듈을 쓰는 프로세스도 관리자
권한이어야 한다. 아니면 Windows UIPI가 합성 입력을 전부 차단한다.
"""

import ctypes
import ctypes.wintypes as w
import time

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

try:
    u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # Per-Monitor V2
except Exception:
    try:
        u32.SetProcessDPIAware()
    except Exception:
        pass

WM_SETTEXT, WM_GETTEXT, WM_GETTEXTLENGTH = 0x000C, 0x000D, 0x000E
BM_CLICK = 0x00F5
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002
VK = {"F1": 0x70, "F2": 0x71, "F5": 0x74, "F8": 0x77,
      "ENTER": 0x0D, "TAB": 0x09, "ESC": 0x1B, "END": 0x23, "HOME": 0x24,
      "BACKSPACE": 0x08, "DELETE": 0x2E, "CTRL": 0x11}

_EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)


# --- SendInput (유니코드 타이핑) --------------------------------------
class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD),
                ("time", w.DWORD), ("dwExtraInfo", ctypes.POINTER(w.ULONG))]


class _INPUTUNION(ctypes.Union):
    # MOUSEINPUT이 64비트에서 32바이트라 union도 32바이트여야 한다.
    _fields_ = [("ki", _KEYBDINPUT), ("padding", ctypes.c_byte * 32)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _INPUTUNION)]


INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004

u32.SendInput.argtypes = (w.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
u32.SendInput.restype = w.UINT


def send_unicode(ch):
    sent = 0
    for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
        inp = _INPUT(type=INPUT_KEYBOARD)
        inp.u.ki = _KEYBDINPUT(wVk=0, wScan=ord(ch), dwFlags=flags,
                               time=0, dwExtraInfo=None)
        sent += u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
    return sent


def send_ascii(ch):
    vk = u32.VkKeyScanW(ord(ch))
    if vk == -1:
        return False
    code, shift = vk & 0xFF, (vk >> 8) & 0xFF
    if shift & 1:
        u32.keybd_event(0x10, 0, 0, 0)
    u32.keybd_event(code, 0, 0, 0)
    time.sleep(0.02)
    u32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)
    if shift & 1:
        u32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)
    return True


class Control:
    __slots__ = ("hwnd", "ctrl_id", "cls", "text", "rect", "visible", "depth")

    def __init__(self, hwnd, ctrl_id, cls, text, rect, visible, depth):
        self.hwnd, self.ctrl_id, self.cls = hwnd, ctrl_id, cls
        self.text, self.rect, self.visible, self.depth = text, rect, visible, depth

    @property
    def center(self):
        l, t, r, b = self.rect
        return (l + r) // 2, (t + b) // 2

    @property
    def size(self):
        l, t, r, b = self.rect
        return (r - l, b - t)

    def __repr__(self):
        l, t, r, b = self.rect
        indent = "  " * self.depth
        return (indent + "id=%-6d cls=%-14s text=%-24r rect=(%d,%d,%dx%d) %s"
                % (self.ctrl_id, self.cls, self.text, l, t, r - l, b - t,
                   "" if self.visible else "[hidden]"))


def _text_of(hwnd):
    n = u32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(n + 2)
    u32.SendMessageW(hwnd, WM_GETTEXT, n + 1, buf)
    return buf.value


def _class_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _rect_of(hwnd):
    r = w.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def top_windows(pid):
    out = []

    def cb(hwnd, _):
        p = w.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(hwnd):
            out.append(Control(hwnd, u32.GetDlgCtrlID(hwnd), _class_of(hwnd),
                               _text_of(hwnd), _rect_of(hwnd), True, 0))
        return True

    u32.EnumWindows(_EnumProc(cb), 0)
    return out


def children(hwnd, max_depth=4, _depth=1):
    out = []

    def cb(child, _):
        out.append(Control(child, u32.GetDlgCtrlID(child), _class_of(child),
                           _text_of(child), _rect_of(child),
                           bool(u32.IsWindowVisible(child)), _depth))
        if _depth < max_depth:
            out.extend(children(child, max_depth, _depth + 1))
        return True

    u32.EnumChildWindows(hwnd, _EnumProc(cb), 0)
    return out


class VXvueUi:
    """VXvue 프로세스 1개를 대상으로 하는 드라이버."""

    # 로그인 화면 컨트롤 ID (2026-08-18 실측, 1920x1080 / Shimadzu 스킨)
    LOGIN_ID_COMBO = 30968
    LOGIN_PW_EDIT = 30147
    LOGIN_BUTTON = 30729
    LOGIN_OSK_ICON = 30391
    LOGIN_POWER_ICON = 30316

    MAIN_WINDOW_MIN_AREA = 1000000
    DIALOG_OK_IDS = (500, 1, 2)

    def __init__(self, process_name="VXvue"):
        self.process_name = process_name
        self._pid = None

    # --- 프로세스 ------------------------------------------------------
    @property
    def pid(self):
        if self._pid and self._alive(self._pid):
            return self._pid
        self._pid = self._find_pid()
        return self._pid

    def _find_pid(self):
        import subprocess
        cmd = ("(Get-Process %s -ErrorAction SilentlyContinue | "
               "Select-Object -First 1).Id" % self.process_name)
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True).stdout.decode("utf-8", "replace").strip()
        return int(out) if out.isdigit() else None

    @staticmethod
    def _alive(pid):
        h = k32.OpenProcess(0x1000, False, pid)
        if h:
            k32.CloseHandle(h)
            return True
        return False

    def launch(self, exe_path, wait=25):
        """설치 폴더를 작업 디렉터리로 지정해 실행한다.

        앱이 상대 경로로 Cache/Log/Temp를 만들기 때문에 자동화 작업 폴더에서
        실행하면 그 폴더를 런타임 저장소로 오염시킨다(Bellalun과 동일 규칙).
        """
        import os
        import subprocess
        subprocess.Popen([exe_path], cwd=os.path.dirname(os.path.abspath(exe_path)))
        time.sleep(wait)
        self._pid = None
        return self.pid

    # --- 창 / 컨트롤 ---------------------------------------------------
    def windows(self):
        return top_windows(self.pid) if self.pid else []

    def main_window(self):
        wins = self.windows()
        if not wins:
            return None
        return max(wins, key=lambda c: (len(children(c.hwnd, 1)),
                                        (c.rect[2] - c.rect[0]) * (c.rect[3] - c.rect[1])))

    def controls(self, window=None, max_depth=5, visible_only=True, all_windows=True):
        if window is not None:
            wins = [window]
        elif all_windows:
            wins = self.windows()
        else:
            win = self.main_window()
            wins = [win] if win else []

        seen, items = set(), []
        for wnd in wins:
            for c in children(wnd.hwnd, max_depth):
                if c.hwnd in seen:
                    continue
                seen.add(c.hwnd)
                items.append(c)
        return [c for c in items if c.visible] if visible_only else items

    def by_id(self, ctrl_id, window=None):
        return [c for c in self.controls(window) if c.ctrl_id == ctrl_id]

    def by_text(self, text, window=None, exact=False):
        t = text.lower()
        return [c for c in self.controls(window)
                if (c.text.lower() == t if exact else t in c.text.lower())]

    def by_class(self, cls, window=None):
        return [c for c in self.controls(window) if c.cls == cls]

    # --- 대화상자 / Info 팝업 -------------------------------------------
    def dialog(self, title=None):
        for c in self.windows():
            if c.cls != "#32770":
                continue
            l, t, r, b = c.rect
            if (r - l) * (b - t) >= self.MAIN_WINDOW_MIN_AREA:
                continue                      # 메인 화면
            if title is not None and c.text != title:
                continue
            return c
        return None

    def dialog_buttons(self, dlg, min_size=12):
        out = []
        for c in children(dlg.hwnd, 3):
            if not c.visible:
                continue
            wd, ht = c.size
            if wd < min_size or ht < min_size:
                continue
            if c.cls == "Button":
                out.append(c)
            elif c.cls.startswith("AfxWnd") and c.text in ("TextButton", "IconButton"):
                out.append(c)
        return sorted(out, key=lambda c: c.rect[0])

    def dialog_text(self, dlg):
        parts = [c.text for c in children(dlg.hwnd, 3) if c.cls == "Static" and c.text]
        return " / ".join(parts)

    def capture_dialog(self, dlg, path):
        import os
        from PIL import ImageGrab
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        ImageGrab.grab(bbox=dlg.rect, all_screens=True).save(path)
        return path

    def wait_dialog(self, title=None, timeout=20, poll=0.5):
        end = time.time() + timeout
        while time.time() < end:
            d = self.dialog(title)
            if d:
                return d
            time.sleep(poll)
        return None

    def dismiss_dialog(self, title=None, timeout=20, evidence_path=None):
        d = self.wait_dialog(title, timeout)
        if not d:
            return None
        msg = self.dialog_text(d)
        if evidence_path:
            try:
                self.capture_dialog(d, evidence_path)
            except Exception:
                pass
        buttons = self.dialog_buttons(d)
        buttons.sort(key=lambda c: (c.ctrl_id not in self.DIALOG_OK_IDS, c.rect[0]))
        for b in buttons:
            if b.cls == "Button":
                self.click_button(b.hwnd)
            else:
                self.click(b, settle=0.5)
            return msg or "(문구 미노출)"
        return msg or "(문구 미노출, 버튼 없음)"

    def dismiss_info(self, timeout=6, evidence_path=None):
        """VXvue 고유: Update/저장 뒤의 모달 Info 팝업을 닫는다.

        이 팝업을 닫지 않으면 이후 클릭이 전부 무시되므로, 저장 성격의 클릭
        뒤에는 항상 호출해야 한다. 팝업이 없으면 None을 반환하고 넘어간다.
        """
        return self.dismiss_dialog(timeout=timeout, evidence_path=evidence_path)

    def click_and_ack(self, target, settle=0.6, ack_timeout=6, evidence_path=None):
        """클릭 후 Info 팝업까지 닫는다. 팝업 문구(없으면 None)를 반환."""
        self.click(target, settle=settle)
        return self.dismiss_info(timeout=ack_timeout, evidence_path=evidence_path)

    # --- 조작 ----------------------------------------------------------
    def click(self, target, settle=0.4):
        x, y = target.center if isinstance(target, Control) else target
        u32.SetCursorPos(int(x), int(y))
        time.sleep(0.08)
        u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.06)
        u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(settle)

    def click_button(self, hwnd):
        u32.SendMessageW(hwnd, BM_CLICK, 0, 0)
        time.sleep(0.4)

    def double_click(self, target, settle=0.4):
        """더블클릭(예: 목록 항목 인라인 이름 편집 진입)."""
        x, y = target.center if isinstance(target, Control) else target
        u32.SetCursorPos(int(x), int(y))
        time.sleep(0.08)
        for _ in range(2):
            u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.05)
        time.sleep(settle)

    def drag(self, start, end, duration=0.4, settle=0.4):
        sx, sy = start.center if isinstance(start, Control) else start
        ex, ey = end.center if isinstance(end, Control) else end
        u32.SetCursorPos(int(sx), int(sy))
        time.sleep(0.08)
        u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        steps = max(4, int(duration / 0.03))
        for i in range(1, steps + 1):
            u32.SetCursorPos(int(sx + (ex - sx) * i / steps),
                             int(sy + (ey - sy) * i / steps))
            time.sleep(duration / steps)
        u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(settle)

    def wheel(self, target, notches, settle=0.2):
        x, y = target.center if isinstance(target, Control) else target
        u32.SetCursorPos(int(x), int(y))
        time.sleep(0.08)
        delta = ctypes.c_ulong(int(notches * 120) & 0xFFFFFFFF).value
        u32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
        time.sleep(settle)

    def find_scrolling(self, predicate, anchor, max_scroll=8, notches=-3):
        """대상이 보일 때까지 anchor 지점에서 스크롤하며 찾는다.

        DICOM > Storage처럼 Echo 버튼이 화면 밖에 있는 경우를 위한 것이다.
        좌표를 고정하지 말고 항상 이 함수로 대상을 확보한다.
        """
        for _ in range(max_scroll + 1):
            for c in self.controls():
                if predicate(c):
                    return c
            self.wheel(anchor, notches)
        return None

    # --- 텍스트 입력 ----------------------------------------------------
    def set_text(self, control, text):
        u32.SendMessageW(control.hwnd, WM_SETTEXT, 0, ctypes.c_wchar_p(text))
        time.sleep(0.15)

    def get_text(self, control):
        return _text_of(control.hwnd)

    def clear_edit(self, control, max_len=64):
        """VXvue 고유: End 이동 후 Backspace 반복으로 완전히 비운다.

        Ctrl+A가 통하지 않는 필드(IP Address 등)에서 기존 값 뒤에 새 값이
        이어붙어 깨지는 것을 막는다.
        """
        self.click(control, settle=0.2)
        self.raw_key(VK["END"])
        for _ in range(max_len):
            self.raw_key(VK["BACKSPACE"], settle=0.01)
        self.raw_key(VK["DELETE"])
        time.sleep(0.1)

    def type_text(self, control, text, clear=True, settle=0.3):
        if clear:
            self.clear_edit(control)
        else:
            self.click(control, settle=0.2)
        for ch in text:
            self._unicode_char(ch)
            time.sleep(0.02)
        time.sleep(settle)

    @staticmethod
    def _unicode_char(ch):
        if send_unicode(ch) == 0:
            send_ascii(ch)

    @staticmethod
    def raw_key(vk, settle=0.05):
        u32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.03)
        u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(settle)

    @staticmethod
    def key_combo(mod_vk, vk):
        u32.keybd_event(mod_vk, 0, 0, 0)
        u32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.03)
        u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        u32.keybd_event(mod_vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.08)

    def key(self, name, settle=0.3):
        vk = VK[name.upper()] if name.upper() in VK else ord(name.upper())
        u32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(settle)

    def activate(self):
        win = self.main_window()
        if win:
            u32.SetForegroundWindow(win.hwnd)
            time.sleep(0.3)
        return win

    # --- 로그인 --------------------------------------------------------
    def at_login_screen(self):
        """로그인 화면 여부.

        `LOGIN_PW_EDIT`(30147) 하나만 보고 판단하면 오탐이 난다 — 이 ID가
        Setting > System - Account 화면의 Password 필드와 우연히 같아서,
        그 화면에 머물러 있을 때도 "로그인 화면"으로 오판했다(실측
        2026-08-19: Setting에서 로그인 화면이 아닌데 `login()`이 로그인
        컨트롤을 찾다 실패해 크래시). Account 콤보(`LOGIN_ID_COMBO`)까지
        함께 있어야 로그인 화면으로 판단한다.
        """
        controls = self.controls()
        has_pw = any(c.cls == "Edit" and c.ctrl_id == self.LOGIN_PW_EDIT
                    for c in controls)
        has_combo = any(c.ctrl_id == self.LOGIN_ID_COMBO for c in controls)
        return has_pw and has_combo

    def current_login_id(self):
        c = self.by_id(self.LOGIN_ID_COMBO)
        return c[0].text if c else None

    def login(self, user_id, password, timeout=60):
        """로그인하고 성공 여부를 반환한다.

        Account 콤보는 커스텀 컨트롤이라 텍스트 주입이 통하지 않는다. 현재
        선택된 계정이 다르면 예외를 던져 잘못된 계정으로 진행하는 것을 막는다.
        """
        if not self.at_login_screen():
            return True

        # 로그인 화면에서 다른 창(탐색기 등)이 위에 떠 있으면, 좌표 기반
        # 클릭(self.click)이 VXvue가 아니라 그 창을 때린다 — 로그인 실패의
        # 실측 원인 중 하나(2026-08-19). VXvue를 최전면으로 올린다.
        self.activate()
        if not self.at_login_screen():
            # activate() 이후 화면이 바뀌었다면 이미 다른 처리가 끝난 것이다.
            return True
        cur = (self.current_login_id() or "").strip()
        if cur and cur.lower() != user_id.strip().lower():
            raise RuntimeError(
                "Account 콤보가 '%s'로 선택되어 있습니다(요청: '%s'). "
                "콤보(컨트롤 %d)를 먼저 변경하십시오."
                % (cur, user_id, self.LOGIN_ID_COMBO))

        pw = self.by_id(self.LOGIN_PW_EDIT)
        btn = self.by_id(self.LOGIN_BUTTON)
        if not pw or not btn:
            raise RuntimeError("로그인 컨트롤을 찾지 못했습니다. 'python run.py ui-probe'로 확인하십시오.")

        self.type_text(pw[0], password)
        self.click(btn[0], settle=1.5)

        end = time.time() + timeout
        gone = 0
        while time.time() < end:
            if self.at_login_screen():
                gone = 0
            else:
                gone += 1
                if gone >= 2:
                    return True
            time.sleep(0.7)
        return False

    def ensure_ready(self, exe_path=None, user_id=None, password=None, dismiss_popup=True):
        notes = []
        if not self.pid and exe_path:
            self.launch(exe_path)
            notes.append("VXvue 실행")
        if not self.pid:
            raise RuntimeError("VXvue가 실행되어 있지 않습니다.")
        if dismiss_popup:
            msg = self.dismiss_info(timeout=8)
            if msg:
                notes.append("팝업 닫음: " + msg)
        if user_id and password:
            ok = self.login(user_id, password)
            notes.append("로그인 성공" if ok else "로그인 실패")
        return notes


def dump(process_name="VXvue", max_depth=5, visible_only=True):
    """현재 화면의 컨트롤 트리를 출력한다. 화면별 컨트롤 ID 지도 작성용."""
    ui = VXvueUi(process_name)
    if not ui.pid:
        return "%s 프로세스를 찾을 수 없습니다." % process_name
    lines = ["PID %d" % ui.pid]
    for win in ui.windows():
        lines.append("\n[WINDOW] %r" % win)
        for c in ui.controls(win, max_depth, visible_only):
            lines.append(repr(c))
    return "\n".join(lines)
