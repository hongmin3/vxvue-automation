# -*- coding: utf-8 -*-
"""Windows 환경 조회.

Bellalun `auto/core/sysinfo.py`를 이식하고 VXvue 리포트 헤더 요구사항에 맞춰
아래를 반영했다.

- `os_build_full()` : 체크리스트의 "OS Build Version"(예: 17763.9020)은
  BuildNumber만으로는 재현되지 않는다. UBR(Update Build Revision)과 결합한다.
- `memory_info()` : preflight 판정 근거. 2026-08-18에 VXvue가 "Initializing
  offset refreshing"에서 무한 대기한 실제 원인이 메모리/페이지파일 고갈이었다.

**WMI/CIM에 의존하지 않는 것을 원칙으로 한다.** 2026-08-18 이 시험 PC에서
`Get-CimInstance`/`Get-WmiObject`가 통째로 응답하지 않는 상태가 실제로
발생했고(WMI가 물려 모든 조회가 무한 대기), 그 때문에 자동화 전체가 멈췄다.
그래서 메모리는 `GlobalMemoryStatusEx`(kernel32), OS 정보와 GPU는 레지스트리로
읽는다. WMI가 필요한 항목(설치된 KB 목록 등)은 **반드시 타임아웃을 걸고**
실패하면 값을 비워 두되 자동화는 계속 진행한다.
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess

PS_TIMEOUT = 20          # 초. WMI가 물려도 자동화를 멈추지 않기 위한 상한
PS_TIMEOUT_WMI = 25


def _ps(script, timeout=PS_TIMEOUT):
    """PowerShell 한 줄 실행. 타임아웃이면 빈 문자열을 반환한다(예외 아님)."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;" + script],
            capture_output=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.decode("utf-8", "replace").strip()


def _ps_json(script, default=None, timeout=PS_TIMEOUT):
    out = _ps(script, timeout=timeout)
    if not out:
        return default if default is not None else []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return default if default is not None else []
    return [data] if isinstance(data, dict) else data


# --- 레지스트리 --------------------------------------------------------
CURRENT_VERSION_KEY = r"HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
_WINREG_CV = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"


def _reg_read(root, subkey, name):
    """winreg 직접 조회. PowerShell을 띄우지 않아 빠르고 WMI와 무관하다."""
    import winreg
    try:
        with winreg.OpenKey(root, subkey, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def registry_value(key, name):
    """'HKLM:\\SOFTWARE\\...' 형식 경로를 받는 호환 API."""
    import winreg
    roots = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    path = key.replace("/", "\\")
    head, _, rest = path.partition(":\\")
    root = roots.get(head.upper())
    if root is None:
        return None
    v = _reg_read(root, rest, name)
    return None if v is None else str(v)


# --- OS ---------------------------------------------------------------
def os_info():
    """OS Caption/Version/Build/Architecture. WMI 없이 레지스트리로 읽는다."""
    import winreg
    hklm = winreg.HKEY_LOCAL_MACHINE
    build = _reg_read(hklm, _WINREG_CV, "CurrentBuildNumber")
    major = _reg_read(hklm, _WINREG_CV, "CurrentMajorVersionNumber")
    minor = _reg_read(hklm, _WINREG_CV, "CurrentMinorVersionNumber")
    caption = _reg_read(hklm, _WINREG_CV, "ProductName")

    # Windows 11은 레지스트리 ProductName이 여전히 'Windows 10 ...'인 경우가 있다.
    # 빌드 22000 이상이면 11로 보정한다(마이크로소프트 공개 기준).
    try:
        build_n = int(build)
    except (TypeError, ValueError):
        build_n = 0
    if caption and build_n >= 22000 and "Windows 10" in caption:
        caption = caption.replace("Windows 10", "Windows 11")

    version = None
    if major is not None:
        version = "%s.%s.%s" % (major, minor if minor is not None else 0, build)
    return {"Caption": caption, "Version": version, "BuildNumber": build,
            "OSArchitecture": os.environ.get("PROCESSOR_ARCHITECTURE", "")}


def os_build_full():
    """체크리스트 'OS Build Version' 형식(CurrentBuild.UBR)."""
    import winreg
    build = _reg_read(winreg.HKEY_LOCAL_MACHINE, _WINREG_CV, "CurrentBuildNumber")
    ubr = _reg_read(winreg.HKEY_LOCAL_MACHINE, _WINREG_CV, "UBR")
    if build is None:
        return None
    return "%s.%s" % (build, ubr) if ubr is not None else str(build)


def os_display_version():
    """22H2 / 24H2 같은 기능 업데이트 표기. 구버전(1809 등)은 ReleaseId."""
    import winreg
    hklm = winreg.HKEY_LOCAL_MACHINE
    v = _reg_read(hklm, _WINREG_CV, "DisplayVersion") or _reg_read(hklm, _WINREG_CV, "ReleaseId")
    return None if v is None else str(v)


# --- 화면 / 메모리 / GPU (전부 WMI 비의존) --------------------------------
def display_info():
    """Primary display 해상도와 DPI 배율. Win32 API로 직접 읽는다."""
    u32 = ctypes.windll.user32
    try:
        u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            u32.SetProcessDPIAware()
        except Exception:
            pass
    width = u32.GetSystemMetrics(0)
    height = u32.GetSystemMetrics(1)
    hdc = u32.GetDC(0)
    try:
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)   # LOGPIXELSX
    finally:
        u32.ReleaseDC(0, hdc)
    dpi = dpi or 96
    return {"width": width, "height": height, "dpi": dpi,
            "scale_percent": round(dpi * 100 / 96)}


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def memory_info():
    """물리 메모리와 커밋(=물리+페이지파일) 여유(GB).

    `Win32_PageFileUsage`/`Win32_OperatingSystem`은 쓰지 않는다 - 2026-08-18
    이 PC에서 WMI 자체가 물려 한 번 호출에 60초 이상 걸리거나 아예 응답하지
    않았다. `GlobalMemoryStatusEx`는 커널 호출이라 즉시 답한다.

    ullTotalPageFile은 '커밋 한도'(물리 + 페이지파일)이므로 페이지파일 크기는
    그 차이로 계산한다.
    """
    st = _MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(st)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return {}

    def gb(b):
        return round(b / (1024.0 ** 3), 2)

    phys_total, phys_free = gb(st.ullTotalPhys), gb(st.ullAvailPhys)
    commit_total, commit_free = gb(st.ullTotalPageFile), gb(st.ullAvailPageFile)
    return {"physical_total_gb": phys_total, "physical_free_gb": phys_free,
            "commit_total_gb": commit_total, "commit_free_gb": commit_free,
            "pagefile_total_gb": round(commit_total - phys_total, 2),
            "pagefile_free_gb": round(max(commit_free - phys_free, 0.0), 2),
            "memory_load_percent": st.dwMemoryLoad}


_DISPLAY_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


def gpu_list():
    """설치된 디스플레이 어댑터. 레지스트리 Display 클래스에서 읽는다."""
    import winreg
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _DISPLAY_CLASS, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                if not sub.isdigit():
                    continue
                desc = _reg_read(winreg.HKEY_LOCAL_MACHINE,
                                 _DISPLAY_CLASS + "\\" + sub, "DriverDesc")
                ver = _reg_read(winreg.HKEY_LOCAL_MACHINE,
                                _DISPLAY_CLASS + "\\" + sub, "DriverVersion")
                if desc:
                    out.append({"name": str(desc), "driver": str(ver or "")})
    except OSError:
        return []
    return out


def is_elevated():
    """관리자 권한 여부. shell32.IsUserAnAdmin으로 즉시 판정한다."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# --- 설치물 / 파일 / 서비스 ---------------------------------------------
def installed_programs():
    """Programs and Features 목록. 레지스트리 조회라 WMI와 무관하다."""
    rows = _ps_json(
        r"Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*,"
        r"HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* "
        r"-ErrorAction SilentlyContinue | Where-Object { $_.DisplayName } | "
        r"Select-Object DisplayName,DisplayVersion | ConvertTo-Json -Compress"
    )
    out = {}
    for r in rows:
        name = (r.get("DisplayName") or "").strip()
        if name and name not in out:
            out[name] = (r.get("DisplayVersion") or "").strip()
    return out


def file_version(path):
    """파일의 FileVersion. 없으면 None. 버전 리소스를 직접 읽어 빠르다."""
    if not os.path.exists(path):
        return None
    ver = ctypes.windll.version
    size = ver.GetFileVersionInfoSizeW(ctypes.c_wchar_p(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(ctypes.c_wchar_p(path), 0, size, buf):
        return None
    ptr = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not ver.VerQueryValueW(buf, ctypes.c_wchar_p("\\"),
                              ctypes.byref(ptr), ctypes.byref(length)):
        return None

    class _FFI(ctypes.Structure):
        _fields_ = [("dwSignature", ctypes.c_uint32),
                    ("dwStrucVersion", ctypes.c_uint32),
                    ("dwFileVersionMS", ctypes.c_uint32),
                    ("dwFileVersionLS", ctypes.c_uint32),
                    ("dwProductVersionMS", ctypes.c_uint32),
                    ("dwProductVersionLS", ctypes.c_uint32)]

    ffi = ctypes.cast(ptr, ctypes.POINTER(_FFI)).contents
    return "%d.%d.%d.%d" % (ffi.dwFileVersionMS >> 16, ffi.dwFileVersionMS & 0xFFFF,
                            ffi.dwFileVersionLS >> 16, ffi.dwFileVersionLS & 0xFFFF)


def service_state(name):
    rows = _ps_json(
        "Get-Service -Name '%s' -ErrorAction SilentlyContinue | Select-Object Name,"
        "@{n='Status';e={$_.Status.ToString()}},"
        "@{n='StartType';e={$_.StartType.ToString()}} | ConvertTo-Json -Compress" % name
    )
    if not rows:
        return None
    r = rows[0]
    return {"name": r.get("Name"), "status": str(r.get("Status")),
            "start_type": str(r.get("StartType"))}


def process_names():
    return _ps("Get-Process | Select-Object -ExpandProperty ProcessName").splitlines()


def windows_updates(limit=10):
    """설치된 Windows 업데이트(KB) 최근 목록.

    Get-HotFix는 WMI(Win32_QuickFixEngineering) 기반이라 WMI가 물리면 응답하지
    않는다. 타임아웃을 걸고, 실패하면 빈 목록을 반환해 리포트 생성 자체는
    계속되게 한다(값을 지어내지 않는다).
    """
    rows = _ps_json(
        "Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | "
        "Select-Object -First %d HotFixID,Description,"
        "@{n='InstalledOn';e={if($_.InstalledOn){$_.InstalledOn.ToString('yyyy-MM-dd')}else{''}}} | "
        "ConvertTo-Json -Compress" % limit, timeout=PS_TIMEOUT_WMI)
    return [{"kb": r.get("HotFixID"), "kind": r.get("Description"),
             "installed_on": r.get("InstalledOn")} for r in rows]
