# -*- coding: utf-8 -*-
r"""표준 `SysTreeView32`(폴더 찾아보기 등)를 **속성으로** 읽고 조작한다.

## 왜 이 모듈이 필요한가

`Import Study`(Database > Import)의 Location은 Edit(`30116`)에 써 넣을 수 없다
— 타이핑이 들어가지 않는 표시 전용 컨트롤이다(실측 2026-08-21, Export Manager의
경로 Edit과 같은 성질). 경로는 `...`(`30515`)이 띄우는 표준 `SHBrowseForFolder`
창("폴더 찾아보기")에서만 정할 수 있다.

그 창의 트리를 **OCR로 읽으면 안 된다.** 실측(2026-08-21)에서 한글 노드는
`바탕 화면` → `'mvs sa'`, `내 PC` → `'il!' 'PC'`처럼 알아볼 수 없게 나오고,
영문 노드조차 `VXvue1 (E:)` → `'me VXvuel (E)'`로 읽혀 **부분 문자열로 맞추면
엉뚱한 노드(`VXvue1.0.11.015(SMZ)`)를 눌렀다.** 실제로 그 사고가 났다.

`SysTreeView32`는 표준 컨트롤이므로 `TVM_*` 메시지로 노드 텍스트를 **정확히**
읽고 선택·펼침까지 할 수 있다. 다른 프로세스의 컨트롤이라 문자열 버퍼를 그
프로세스 주소공간에 만들어야 한다(`VirtualAllocEx` → `WriteProcessMemory` →
`SendMessage` → `ReadProcessMemory`). CLAUDE.md 3절의 "좌표가 아니라 속성으로
찾는다"를 이 창에서도 지키기 위한 구현이다.
"""

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# **공유 ctypes 함수 객체의 restype을 바꾸지 않는다.**
# `ctypes.windll.user32`는 프로세스 전체가 공유하는 캐시된 객체다. 처음 구현에서
# `user32.SendMessageW.restype = c_void_p`로 고쳤더니 `core/ui.py`의 `_text_of()`가
# 길이 0을 `None`으로 받아 `TypeError: unsupported operand type(s) for +:
# 'NoneType' and 'int'`로 죽었다(실측 2026-08-21, 이 모듈을 import한 스크립트에서
# 재현). 그래서 필요한 원형은 **별도 함수 포인터로** 만들어 쓴다.
_SendMessage = ctypes.WINFUNCTYPE(
    ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
    ctypes.c_void_p, ctypes.c_void_p)(("SendMessageW", user32))
_VirtualAllocEx = ctypes.WINFUNCTYPE(
    ctypes.c_void_p, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
    wintypes.DWORD, wintypes.DWORD)(("VirtualAllocEx", kernel32))

TV_FIRST = 0x1100
TVM_GETNEXTITEM = TV_FIRST + 10
TVM_GETITEMW = TV_FIRST + 62
TVM_EXPAND = TV_FIRST + 2
TVM_SELECTITEM = TV_FIRST + 11
TVM_ENSUREVISIBLE = TV_FIRST + 20

TVGN_ROOT = 0x0000
TVGN_NEXT = 0x0001
TVGN_CHILD = 0x0004
TVGN_CARET = 0x0009

TVIF_TEXT = 0x0001
TVIF_CHILDREN = 0x0040
TVE_EXPAND = 0x0002

PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

TEXT_MAX = 260


class TVITEMW(ctypes.Structure):
    _fields_ = [("mask", wintypes.UINT),
                ("hItem", ctypes.c_void_p),
                ("state", wintypes.UINT),
                ("stateMask", wintypes.UINT),
                ("pszText", ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int),
                ("iImage", ctypes.c_int),
                ("iSelectedImage", ctypes.c_int),
                ("cChildren", ctypes.c_int),
                ("lParam", ctypes.c_void_p)]


class ShellTreeError(RuntimeError):
    pass


class ShellTree(object):
    """다른 프로세스의 `SysTreeView32` 하나를 읽고 조작한다.

    `with ShellTree(hwnd) as tree:` 로 쓰면 원격 버퍼를 반드시 회수한다.
    """

    def __init__(self, hwnd):
        self.hwnd = hwnd
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        self.pid = pid.value
        access = (PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE
                  | PROCESS_QUERY_INFORMATION)
        self._proc = kernel32.OpenProcess(access, False, self.pid)
        if not self._proc:
            raise ShellTreeError("PID %d 프로세스를 열 수 없다(오류 %d)."
                                 % (self.pid, kernel32.GetLastError()))
        self._size = ctypes.sizeof(TVITEMW) + TEXT_MAX * 2
        self._remote = _VirtualAllocEx(self._proc, None, self._size,
                                       MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not self._remote:
            kernel32.CloseHandle(self._proc)
            raise ShellTreeError("원격 버퍼를 만들 수 없다(오류 %d)."
                                 % kernel32.GetLastError())

    # --- 자원 정리 ----------------------------------------------------
    def close(self):
        if getattr(self, "_remote", None):
            kernel32.VirtualFreeEx(self._proc, ctypes.c_void_p(self._remote),
                                   0, MEM_RELEASE)
            self._remote = None
        if getattr(self, "_proc", None):
            kernel32.CloseHandle(self._proc)
            self._proc = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    # --- 트리 이동 ----------------------------------------------------
    def _next(self, flag, hitem=0):
        return _SendMessage(self.hwnd, TVM_GETNEXTITEM,
                            ctypes.c_void_p(flag),
                            ctypes.c_void_p(hitem or 0))

    def root(self):
        return self._next(TVGN_ROOT)

    def first_child(self, hitem):
        return self._next(TVGN_CHILD, hitem)

    def next_sibling(self, hitem):
        return self._next(TVGN_NEXT, hitem)

    def selected(self):
        return self._next(TVGN_CARET)

    # --- 노드 읽기 ----------------------------------------------------
    def text(self, hitem):
        """노드 라벨을 정확히 읽는다(OCR 아님)."""
        text_addr = self._remote + ctypes.sizeof(TVITEMW)
        item = TVITEMW()
        item.mask = TVIF_TEXT | TVIF_CHILDREN
        item.hItem = ctypes.c_void_p(hitem)
        item.pszText = ctypes.c_void_p(text_addr)
        item.cchTextMax = TEXT_MAX
        written = ctypes.c_size_t(0)
        if not kernel32.WriteProcessMemory(
                self._proc, ctypes.c_void_p(self._remote), ctypes.byref(item),
                ctypes.sizeof(item), ctypes.byref(written)):
            raise ShellTreeError("원격 구조체 쓰기 실패(오류 %d)."
                                 % kernel32.GetLastError())
        if not _SendMessage(self.hwnd, TVM_GETITEMW, None,
                            ctypes.c_void_p(self._remote)):
            return ""
        buf = ctypes.create_unicode_buffer(TEXT_MAX)
        read = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(
                self._proc, ctypes.c_void_p(text_addr), buf, TEXT_MAX * 2,
                ctypes.byref(read)):
            raise ShellTreeError("원격 문자열 읽기 실패(오류 %d)."
                                 % kernel32.GetLastError())
        return buf.value

    def children(self, hitem):
        """`hitem`의 자식 노드를 `[(hItem, 텍스트)]`로 돌려준다."""
        out = []
        child = self.first_child(hitem)
        while child:
            out.append((child, self.text(child)))
            child = self.next_sibling(child)
        return out

    # --- 조작 --------------------------------------------------------
    def expand(self, hitem):
        return bool(_SendMessage(self.hwnd, TVM_EXPAND,
                                 ctypes.c_void_p(TVE_EXPAND),
                                 ctypes.c_void_p(hitem)))

    def select(self, hitem):
        _SendMessage(self.hwnd, TVM_ENSUREVISIBLE, None, ctypes.c_void_p(hitem))
        return bool(_SendMessage(self.hwnd, TVM_SELECTITEM,
                                 ctypes.c_void_p(TVGN_CARET),
                                 ctypes.c_void_p(hitem)))

    def expand_and_wait(self, hitem, timeout=6.0, poll=0.2):
        """펼친 뒤 자식이 채워질 때까지 기다린다.

        셸 트리는 노드를 펼치면 폴더를 **비동기로** 열거한다(실측 2026-08-21:
        `TVM_EXPAND` 직후에는 `TVGN_CHILD`가 0이었고 잠시 뒤 채워졌다). 기다리지
        않으면 "폴더가 없다"는 잘못된 판정이 난다.
        """
        self.expand(hitem)
        end = time.time() + timeout
        while time.time() < end:
            if self.first_child(hitem):
                return True
            time.sleep(poll)
        return bool(self.first_child(hitem))

    # --- 경로 탐색 ----------------------------------------------------
    def find_child(self, parent, predicate):
        for hitem, label in self.children(parent):
            if predicate(label):
                return hitem, label
        return None, None

    def walk_path(self, steps, start=None):
        """`steps`(판정 함수 목록)를 따라 한 단계씩 펼치며 내려간다.

        각 단계는 `label -> bool` 함수다. 라벨 표기가 로케일·볼륨 이름에 따라
        달라지므로 고정 문자열이 아니라 판정 함수를 받는다(예: `"(E:)" in label`).
        반환: (마지막 노드 핸들, [지나온 라벨]) — 못 찾으면 (None, 지나온 라벨).
        """
        node = start if start is not None else self.root()
        trail = []
        for pred in steps:
            self.expand_and_wait(node)
            found, label = self.find_child(node, pred)
            if found is None:
                return None, trail
            trail.append(label)
            node = found
        return node, trail

    def dump(self, hitem=None, depth=0, maxdepth=2, out=None):
        """디버깅용 계층 덤프."""
        out = [] if out is None else out
        node = self.root() if hitem is None else hitem
        while node:
            out.append("  " * depth + repr(self.text(node)))
            if depth < maxdepth:
                child = self.first_child(node)
                if child:
                    self.dump(child, depth + 1, maxdepth, out)
            node = self.next_sibling(node)
        return out
