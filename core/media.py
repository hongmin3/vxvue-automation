# -*- coding: utf-8 -*-
"""TC08/TC13 공용 이동식 매체 탐지.

USB 드라이브 문자는 PC와 연결 순서에 따라 D:/E: 등으로 달라진다. 설정 경로의
드라이브가 실제 이동식 매체로 준비돼 있으면 그대로 쓰고, 아니면 현재 준비된
이동식 드라이브가 정확히 하나일 때만 그 드라이브로 경로를 옮긴다. 여러 USB가
있으면 엉뚱한 매체를 지우거나 덮어쓸 수 있으므로 자동 선택하지 않는다.
"""

import ctypes
import os
import string


DRIVE_REMOVABLE = 2


def _drive_type(root):
    return int(ctypes.windll.kernel32.GetDriveTypeW(str(root)))


def _logical_roots():
    mask = int(ctypes.windll.kernel32.GetLogicalDrives())
    return ["%s:\\" % letter for index, letter in enumerate(string.ascii_uppercase)
            if mask & (1 << index)]


def removable_roots():
    """현재 준비된 이동식 드라이브 루트를 정렬해 반환한다."""
    return sorted(root for root in _logical_roots()
                  if os.path.isdir(root) and _drive_type(root) == DRIVE_REMOVABLE)


def resolve_destination(configured_path):
    """설정 경로를 현재 USB 문자에 맞추고 ``(경로 또는 None, 설명)``을 준다."""
    configured = os.path.abspath(configured_path)
    configured_drive, tail = os.path.splitdrive(configured)
    configured_root = configured_drive + os.sep if configured_drive else ""
    roots = removable_roots()

    if configured_root and configured_root in roots:
        return configured, "설정된 이동식 드라이브 %s 사용" % configured_root
    if len(roots) == 1:
        resolved = os.path.join(roots[0], tail.lstrip("\\/"))
        return resolved, ("설정 경로 %s의 드라이브가 준비되지 않아 현재 연결된 "
                          "이동식 드라이브 %s로 자동 대체" %
                          (configured, roots[0]))
    if not roots:
        return None, "준비된 이동식 드라이브가 없음(설정 경로: %s)" % configured
    return None, ("이동식 드라이브가 여러 개라 자동 선택하지 않음: %s" %
                  ", ".join(roots))
