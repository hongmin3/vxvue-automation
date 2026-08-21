# -*- coding: utf-8 -*-
r"""다른 프로세스의 표준 컨트롤에 Win32 메시지를 보내는 공통 도구.

## 왜 필요한가

VXvue의 목록·트리 안쪽 항목은 `ListItem` / `ScrollWnd`처럼 **자기 텍스트가 없는
자식 창**이라 `WM_GETTEXT`로 값을 읽을 수 없다. 그래서 이 프로젝트는 그 값들을
OCR로 읽어 왔는데, 표준 컨트롤(`SysHeader32`, `SysTreeView32`)이 섞여 있는
자리에서는 **메시지로 정확히 읽을 수 있다** — OCR은 잘린 라벨과 한글에서 실제로
틀렸다(2026-08-21: `VXvue1 (E:)` → `VXvuel (E)`로 읽어 엉뚱한 노드를 눌렀다).

표준 컨트롤에 구조체를 넘기는 메시지(`HDM_GETITEMW`, `TVM_GETITEMW` 등)는 그
구조체와 문자열 버퍼가 **대상 프로세스 주소공간에** 있어야 한다. 그 준비를
여기서 한 번만 구현한다.

## 공유 ctypes 객체를 건드리지 않는다

`ctypes.windll.user32`는 프로세스 전체가 공유하는 캐시 객체다. 초기 구현에서
`user32.SendMessageW.restype = c_void_p`로 바꿨더니 `core/ui.py`의 `_text_of()`가
길이 0을 `None`으로 받아 `TypeError`로 죽었다(실측 2026-08-21). 그래서 필요한
원형은 **별도 함수 포인터**로 만들어 쓴다.
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

send_message = ctypes.WINFUNCTYPE(
    ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
    ctypes.c_void_p, ctypes.c_void_p)(("SendMessageW", user32))
_VirtualAllocEx = ctypes.WINFUNCTYPE(
    ctypes.c_void_p, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t,
    wintypes.DWORD, wintypes.DWORD)(("VirtualAllocEx", kernel32))

PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04


class RemoteMemError(RuntimeError):
    pass


def window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def send(hwnd, msg, wparam=0, lparam=0):
    """`SendMessageW` — 포인터 크기 반환값을 잃지 않는다."""
    return send_message(hwnd, msg,
                        None if wparam in (0, None) else ctypes.c_void_p(wparam),
                        None if lparam in (0, None) else ctypes.c_void_p(lparam))


class RemoteMem(object):
    """대상 프로세스에 잡아 두는 작업용 버퍼.

    `with RemoteMem(hwnd, size) as m:` 로 쓰면 반드시 회수한다.
    `m.addr`가 그 프로세스에서 유효한 주소다.
    """

    def __init__(self, hwnd, size):
        self.pid = window_pid(hwnd)
        access = (PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE
                  | PROCESS_QUERY_INFORMATION)
        self._proc = kernel32.OpenProcess(access, False, self.pid)
        if not self._proc:
            raise RemoteMemError("PID %d 프로세스를 열 수 없다(오류 %d)."
                                 % (self.pid, kernel32.GetLastError()))
        self.size = size
        self.addr = _VirtualAllocEx(self._proc, None, size,
                                    MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not self.addr:
            kernel32.CloseHandle(self._proc)
            raise RemoteMemError("원격 버퍼(%d바이트)를 만들 수 없다(오류 %d)."
                                 % (size, kernel32.GetLastError()))

    def close(self):
        if getattr(self, "addr", None):
            kernel32.VirtualFreeEx(self._proc, ctypes.c_void_p(self.addr),
                                   0, MEM_RELEASE)
            self.addr = None
        if getattr(self, "_proc", None):
            kernel32.CloseHandle(self._proc)
            self._proc = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def write(self, offset, obj):
        written = ctypes.c_size_t(0)
        if not kernel32.WriteProcessMemory(
                self._proc, ctypes.c_void_p(self.addr + offset),
                ctypes.byref(obj), ctypes.sizeof(obj), ctypes.byref(written)):
            raise RemoteMemError("원격 쓰기 실패(오류 %d)." % kernel32.GetLastError())
        return written.value

    def read_into(self, offset, obj):
        read = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(
                self._proc, ctypes.c_void_p(self.addr + offset),
                ctypes.byref(obj), ctypes.sizeof(obj), ctypes.byref(read)):
            raise RemoteMemError("원격 읽기 실패(오류 %d)." % kernel32.GetLastError())
        return obj

    def read_text(self, offset, chars):
        buf = ctypes.create_unicode_buffer(chars)
        read = ctypes.c_size_t(0)
        if not kernel32.ReadProcessMemory(
                self._proc, ctypes.c_void_p(self.addr + offset), buf,
                chars * 2, ctypes.byref(read)):
            raise RemoteMemError("원격 문자열 읽기 실패(오류 %d)."
                                 % kernel32.GetLastError())
        return buf.value
