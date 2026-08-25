# -*- coding: utf-8 -*-
r"""실행이 끝났다는 것을 놓치지 않게 알린다.

## 왜 필요한가 (사용자 지시, 2026-08-25)

전체 회귀는 25~40분이 걸린다. 그동안 사람이 자리를 비우거나 다른 창을 보고
있으면 **끝났는지, 끝났다면 통과했는지**를 알 방법이 스크롤을 되짚는 것밖에
없었다. `core/regression._log()`는 `print()` 하나뿐이라 긴 실행 로그 속에
마지막 줄이 묻힌다.

실제로 이 프로젝트에서 손해가 났다: 백그라운드로 돌린 전체 회귀가 두 차례
중간에 끊겼는데, **끊긴 것을 바로 알지 못해** 그 시간만큼 검증이 밀렸다
(2026-08-24~25).

## 무엇을 하는가

1. `banner()` — 터미널에 상자로 둘러싼 결과 블록을 찍는다. 로그가 아무리
   길어도 눈에 걸린다. 판정에 따라 `완료` / `실패` / `확인 필요`로 첫 줄이
   달라진다.
2. `popup()` — **별도 창**을 하나 띄운다(Windows MessageBox). 터미널을 보고
   있지 않아도 화면에 남아 있으므로 자리를 비웠다 돌아왔을 때 바로 보인다.

## 설계상 지킨 것

- **알림이 판정을 바꾸지 않는다.** 알림 자체가 실패해도(PowerShell이 없다,
  세션이 대화형이 아니다 등) 예외를 밖으로 내보내지 않고 조용히 넘어간다 —
  시험 결과를 알리는 장치가 시험 결과를 망치면 안 된다.
- **팝업은 비차단(detached)이다.** `Popen`으로 띄우고 기다리지 않으므로
  아무도 닫지 않아도 명령이 끝나고 종료 코드가 나간다. 예약 실행·CI처럼
  사람이 없는 환경에서 프로세스가 팝업을 붙들고 매달리지 않는다.
- **팝업은 UI 자동화가 다 끝난 뒤에만 부른다.** 포커스를 가져가므로 VXvue를
  조작하는 중에 띄우면 합성 입력이 엉뚱한 창으로 간다(`CLAUDE.md` 3절의
  "모달 창이 남아 있으면 그 뒤 관측값을 근거로 쓰지 않는다"와 같은 이유).
"""

import os
import subprocess
import sys

#: 판정 → (배너 머리말, 팝업 아이콘). 아이콘은 .NET MessageBoxIcon 이름이다.
_HEADLINE = {
    "PASS": ("자동화 완료 — 전부 통과", "Information"),
    "FAIL": ("자동화 실패 — FAIL 있음", "Error"),
    "MANUAL": ("자동화 완료 — 사람이 확인할 항목 있음", "Warning"),
    "SKIP": ("자동화 완료 — 수행하지 않은 항목 있음", "Warning"),
    "BLOCKED": ("자동화 중단 — 선행조건 미충족", "Error"),
    "ABORTED": ("자동화 비정상 종료", "Error"),
}

_WIDTH = 78


def headline(verdict):
    return _HEADLINE.get(verdict, _HEADLINE["MANUAL"])[0]


def banner(verdict, lines, stream=None):
    """터미널에 결과 블록을 찍는다. 반환값 없음, 예외 없음."""
    out = stream or sys.stdout
    try:
        head = headline(verdict)
        body = ["", "=" * _WIDTH, "  " + head, "=" * _WIDTH]
        for line in lines:
            for chunk in _wrap(str(line)):
                body.append("  " + chunk)
        body.append("=" * _WIDTH)
        body.append("")
        out.write("\n".join(body) + "\n")
        out.flush()
    except Exception:                                     # noqa: BLE001
        pass


def _wrap(text, width=_WIDTH - 4):
    """표시 폭 기준으로 줄을 나눈다(동아시아 문자는 2칸).

    **토큰(공백으로 나뉜 조각) 자체는 쪼개지 않는다** — 파일 경로가 중간에서
    끊기면 복사해 쓸 수 없어 알림의 목적을 잃는다. 긴 토큰은 상자 밖으로
    넘치게 둔다.
    """
    if not text:
        return [""]
    if _display_width(text) <= width:
        return [text]
    out, cur = [], ""
    for token in text.split(" "):
        if not cur:
            cur = token
        elif _display_width(cur) + 1 + _display_width(token) <= width:
            cur += " " + token
        else:
            out.append(cur)
            cur = token
    if cur:
        out.append(cur)
    return out


def _display_width(text):
    return sum(2 if _wide(c) else 1 for c in text)


def _wide(ch):
    o = ord(ch)
    return (0x1100 <= o <= 0x115F or 0x2E80 <= o <= 0xA4CF
            or 0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF
            or 0xFE30 <= o <= 0xFE6F or 0xFF00 <= o <= 0xFF60
            or 0xFFE0 <= o <= 0xFFE6)


def popup(verdict, lines, title="VXvue 자동화"):
    """별도 창을 하나 띄운다(비차단). 실패하면 조용히 넘어간다.

    반환: 창을 띄우는 프로세스를 실제로 시작했으면 True.
    """
    head, icon = _HEADLINE.get(verdict, _HEADLINE["MANUAL"])
    text = head + "\n\n" + "\n".join(str(x) for x in lines)
    # PowerShell 인자로 넘기면 따옴표·개행 이스케이프에 걸린다. Base64로 감싸
    # -EncodedCommand로 넘기면 문구에 무엇이 들어와도 안전하다.
    script = (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null;"
        "[System.Windows.Forms.MessageBox]::Show(%s, %s, 'OK', '%s') | Out-Null"
        % (_ps_literal(text), _ps_literal(title), icon)
    )
    try:
        import base64
        enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        creation = 0x08000000 if os.name == "nt" else 0     # CREATE_NO_WINDOW
        subprocess.Popen(
            ["powershell", "-NoProfile", "-EncodedCommand", enc],
            creationflags=creation,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:                                     # noqa: BLE001
        return False


def _ps_literal(s):
    """PowerShell single-quoted 문자열. 내부 홑따옴표는 두 번 쓴다."""
    return "'" + str(s).replace("'", "''") + "'"


def announce(verdict, lines, want_popup=True, title="VXvue 자동화"):
    """배너 + (원하면) 팝업. 실행 명령의 맨 마지막에 한 번 부른다."""
    banner(verdict, lines)
    if want_popup:
        popup(verdict, lines, title=title)
