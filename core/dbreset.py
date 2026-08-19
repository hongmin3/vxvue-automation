# -*- coding: utf-8 -*-
"""DRF DB 백업 / 복원 — 파괴적 조작 전용 모듈.

`core/db.py`는 의도적으로 조회만 제공한다. 쓰기·복원은 위험도가 달라서 이
모듈에 따로 모았고, 아래 규칙을 코드로 강제한다.

1. **복원 전에 항상 안전 백업을 먼저 뜬다.** 실패해도 되돌릴 수 있어야 한다.
2. **명시적 승인 인자 없이는 복원하지 않는다**(`confirm=True`).
3 .`SINGLE_USER WITH ROLLBACK IMMEDIATE` -> `RESTORE ... WITH REPLACE` ->
   `MULTI_USER` 순서를 지킨다(Bellalun `core/dbreset.py`와 동일한 사상).

Setting Import는 export 안의 `Data.bak`으로 **DB 전체를 복원**하는 조작이므로
(`core/vxs.py` 참고) Import를 실행하기 직전 이 모듈로 백업을 남긴다.
사용자 승인: 2026-08-18 "진행 (백업 뜨고)".
"""

import os
import subprocess
import time
from datetime import datetime

DEFAULT_SERVER = r".\CHAMELEON"
DEFAULT_DB = "DRF"
DEFAULT_BACKUP_DIR = r"D:\Database\Database\Bak"

# 실측(2026-08-19): 라이선스 파일은 `<data_dir>\Database\` 아래, 로그는
# `<data_dir>\log\` 아래에 있다(이 PC는 data_dir=D:\Database, 다른 PC는
# C:\Database 등일 수 있다 — 사용자 지시. 그래서 모듈 상수로 경로를
# 하드코딩하지 않고, 아래 함수들은 항상 `data_dir`을 인자로 받는다.
# `config.json`의 `data_dir`/`baseline.db_backup`/`baseline.folder_backup`을
# 호출부(core/regression.py)가 읽어서 넘겨준다.
LICENSE_SUBDIR = "Database"
# 라이선스 파일 이름을 상수로 열거하지 않는다 — 사양서1 p.7(VP-415)이
# "The VXvue Option license supports up to 16 options"라고 하므로
# `Optionlicense0/1`만 박아 두면 옵션이 3개 이상 등록된 PC에서 조용히
# 누락된다(이 PC 실측은 0/1 두 개). `core/license.license_files()`가 glob으로
# 실제 존재하는 파일을 찾고, 아래 백업/복원 함수는 그 목록을 그대로 쓴다.
LOG_SUBDIR = "log"

# 폴더 전체를 baseline으로 되돌릴 때(robocopy /MIR) 건드리지 않을 하위 폴더.
# - Bak: DB 백업 산출물 자체(우리가 만든 안전 백업 이력 포함) — 지워지면
#   되돌릴 방법이 없어지는 유일한 자산이라 보존한다.
# - log: 사용자 지시(2026-08-19) — 라이선스처럼 별도로 백업해 두고 되돌린
#   뒤 다시 덮어써서 회귀 실행마다 로그가 사라지지 않게 한다.
FOLDER_RESTORE_EXCLUDE_DIRS = ("Bak", LOG_SUBDIR)
# DB 파일은 SQL Server가 점유하고 있어 파일 복사로 다루면 안 된다(2절
# 실측: robocopy가 이미 실패하는 것으로 확인됨) — DB는 항상 restore()로
# SQL 레벨에서 복원한다.
FOLDER_RESTORE_EXCLUDE_FILES = ("*.mdf", "*.ldf")

# 복원 전 종료 대상 후보. 실제 상시 구동 프로세스는 PC 구성에 따라 다르므로
# 존재하는 것만 종료하고, 없는 것은 조용히 넘어간다.
APP_PROCESSES = (
    "VXvue", "VX.LAUNCHER", "VX.PROCEDURE.MANAGER", "VX.EXPORT.MANAGER",
    "VX.LOGGER.VIEWER", "VW.STATISTICS", "VW.COMMUNICATOR",
    "VX.WEB.DEVICE", "VX.WEB.IMAGE", "ImageExtractor",
)


class DbResetError(RuntimeError):
    pass


def _sqlcmd(server, sql, timeout=1800):
    """sqlcmd로 T-SQL을 실행한다. (returncode, stdout, stderr)"""
    proc = subprocess.run(
        ["sqlcmd", "-S", server, "-E", "-b", "-Q", sql],
        capture_output=True, timeout=timeout)
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace").strip(),
            proc.stderr.decode("utf-8", "replace").strip())


def _ps(script, timeout=120):
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, timeout=timeout)
    return proc.stdout.decode("utf-8", "replace").strip()


def is_app_running(processes=APP_PROCESSES):
    """뷰어 관련 프로세스 중 지금 살아있는 것의 이름 목록."""
    alive = []
    for name in processes:
        out = _ps("if (Get-Process -Name '%s' -ErrorAction SilentlyContinue) { 'alive' }" % name)
        if out.strip() == "alive":
            alive.append(name)
    return alive


def stop_app(processes=APP_PROCESSES, wait_timeout=30, poll=1.0):
    """뷰어 관련 프로세스를 종료하고 **실제로 완전히 꺼졌는지 확인**한다.

    사용자 지시(2026-08-19): "DB/폴더 초기화 할 때는 뷰어가 꺼져있어야 한다.
    켜져 있다면 끈 다음에 작업할 수 있도록 예외처리 해줘." — 켜져 있으면
    끄고, 종료가 실제로 확인될 때까지 기다린다(파일 잠금·DB 연결이 완전히
    풀려야 폴더 복사/DB 복원이 안전하다). 시간 내에 안 꺼지면 예외를 던져
    초기화 자체를 막는다 — "꺼진 걸로 치고 진행"하지 않는다.

    VXService 등 서비스는 건드리지 않는다 — 서비스를 임의로 멈추면 복원 후
    제품이 정상 기동하지 않는 상태를 만들 수 있고, `SINGLE_USER WITH ROLLBACK
    IMMEDIATE`가 남은 DB 연결은 끊어주므로 필요하지 않다.
    """
    stopped = []
    for name in processes:
        out = _ps("$p = Get-Process -Name '%s' -ErrorAction SilentlyContinue; "
                  "if ($p) { $p | Stop-Process -Force; 'killed' }" % name)
        if out.strip() == "killed":
            stopped.append(name)

    end = time.time() + wait_timeout
    remaining = list(processes)
    while time.time() < end:
        remaining = is_app_running(remaining)
        if not remaining:
            break
        time.sleep(poll)
    if remaining:
        raise DbResetError(
            "다음 프로세스가 %d초 내에 종료되지 않아 초기화를 진행할 수 없습니다: %s"
            % (wait_timeout, ", ".join(remaining)))
    return stopped


def backup(server=DEFAULT_SERVER, database=DEFAULT_DB, out_dir=DEFAULT_BACKUP_DIR,
           prefix="SAFETY", note=""):
    """DB를 네이티브 백업한다. 만들어진 .bak 경로를 반환.

    파일명에 접두를 붙여 제품의 정기 백업 로테이션과 섞이지 않게 한다.
    """
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, "%s_%s_%s.bak" % (prefix, database, stamp))
    desc = (note or "automation safety backup").replace("'", "''")
    sql = ("BACKUP DATABASE [%s] TO DISK = N'%s' WITH INIT, NAME = N'%s', "
           "DESCRIPTION = N'%s'" % (database, path, os.path.basename(path), desc))
    rc, out, err = _sqlcmd(server, sql)
    if rc != 0 or not os.path.exists(path):
        raise DbResetError("백업 실패: %s" % (err or out))
    return path


def backup_files(path):
    """백업 파일에 담긴 논리 파일 이름과 물리 경로를 읽는다(복원 MOVE 구성용)."""
    rc, out, err = _sqlcmd(DEFAULT_SERVER, "RESTORE FILELISTONLY FROM DISK = N'%s'" % path)
    if rc != 0:
        raise DbResetError("백업 파일 목록 조회 실패: %s" % (err or out))
    return out


def restore(bak_path, server=DEFAULT_SERVER, database=DEFAULT_DB,
            confirm=False, safety_backup=True, stop_processes=True):
    """DB를 백업 파일로 복원한다. **파괴적 조작이다.**

    confirm=True 없이 호출하면 아무 것도 하지 않고 예외를 던진다.
    반환: dict(safety_backup=경로 또는 None, stopped=[...], log=...)
    """
    if not confirm:
        raise DbResetError(
            "복원은 명시적 승인이 필요합니다. restore(..., confirm=True)로 호출하십시오. "
            "이 조작은 현재 DB 내용(환자·검사 포함)을 덮어씁니다.")
    if not os.path.exists(bak_path):
        raise DbResetError("백업 파일이 없습니다: %s" % bak_path)

    safety = backup(server, database, prefix="PRERESTORE",
                    note="taken automatically before restore") if safety_backup else None
    stopped = stop_app() if stop_processes else []

    sql = ("ALTER DATABASE [{db}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
           "RESTORE DATABASE [{db}] FROM DISK = N'{bak}' WITH REPLACE; "
           "ALTER DATABASE [{db}] SET MULTI_USER;").format(db=database, bak=bak_path)
    rc, out, err = _sqlcmd(server, sql)
    if rc != 0:
        # 복원이 실패하면 DB가 SINGLE_USER로 남을 수 있다. 반드시 되돌린다.
        _sqlcmd(server, "ALTER DATABASE [%s] SET MULTI_USER" % database)
        raise DbResetError("복원 실패: %s (안전 백업: %s)" % (err or out, safety))

    return {"safety_backup": safety, "stopped": stopped, "log": out}


def restore_from_vxs(vxs_path, work_dir, **kwargs):
    """`.vxs` 안의 `Data.bak`을 꺼내 복원한다.

    제품의 Import 버튼과 같은 결과를 스크립트로 재현할 때 쓴다. 다만 **TC 수행은
    제품 UI의 Import를 써야 한다** — 제품 동작을 검증하는 것이 목적이므로, 이
    함수는 환경 복구용 보조 수단으로만 쓴다.
    """
    from . import vxs as vxs_mod
    os.makedirs(work_dir, exist_ok=True)
    bak = vxs_mod.extract_db_backup(
        vxs_path, os.path.join(work_dir, "from_vxs_Data.bak"))
    return restore(bak, **kwargs)


# --- 라이선스 파일 보존 ------------------------------------------------
def backup_license_files(data_dir, dest_dir):
    """`<data_dir>\\Database\\*.lic`을 로컬 임시 위치로 백업한다.

    라이선스는 하드웨어 키에 묶여 있어 git/설계 문서/기준 백업 어디에도
    값으로 남기지 않는다 — 폴더를 baseline으로 되돌리기 **직전**에 "지금
    적용된" 파일만 이 프로세스가 쓰는 임시 폴더에 떴다가, 되돌린 뒤 그대로
    다시 덮어쓰는 왕복용으로만 쓴다(사용자 지시, 2026-08-19).
    """
    import shutil
    from . import license as license_mod
    os.makedirs(dest_dir, exist_ok=True)
    saved = []
    src_dir = os.path.join(data_dir, LICENSE_SUBDIR)
    for entry in license_mod.license_files(data_dir):
        src = os.path.join(src_dir, entry["file"])
        if os.path.exists(src):
            dst = os.path.join(dest_dir, entry["file"])
            shutil.copy2(src, dst)
            saved.append(dst)
    return saved


def restore_license_files(data_dir, src_dir):
    """`backup_license_files()`로 떠 둔 파일을 제자리에 다시 덮어쓴다."""
    import glob as _glob
    import shutil
    dst_dir = os.path.join(data_dir, LICENSE_SUBDIR)
    os.makedirs(dst_dir, exist_ok=True)
    restored = []
    # 백업해 둔 폴더에 실제로 있는 `.lic`을 전부 되돌린다(이름을 열거하지
    # 않는 이유는 LICENSE_SUBDIR 주석 참고).
    for src in sorted(_glob.glob(os.path.join(src_dir, "*.lic"))):
        dst = os.path.join(dst_dir, os.path.basename(src))
        shutil.copy2(src, dst)
        restored.append(dst)
    return restored


# --- 로그 폴더 보존 -----------------------------------------------------
def backup_log_files(data_dir, dest_dir):
    """`<data_dir>\\log\\`을 로컬 임시 위치로 백업한다(사용자 지시, 2026-08-19).

    라이선스와 같은 이유 — 폴더를 baseline으로 되돌리는 `restore_folder()`가
    `log/`를 건드리지 않도록 이미 제외해 두지만(FOLDER_RESTORE_EXCLUDE_DIRS),
    "빼먹지 않고 보존한다"는 걸 별도로 증명하기 위해 명시적으로도 백업해 둔다.
    """
    import shutil
    src_dir = os.path.join(data_dir, LOG_SUBDIR)
    if not os.path.isdir(src_dir):
        return None
    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)
    shutil.copytree(src_dir, dest_dir)
    return dest_dir


def restore_log_files(data_dir, src_dir):
    """`backup_log_files()`로 떠 둔 로그를 제자리로 되돌린다."""
    import shutil
    if not os.path.isdir(src_dir):
        return None
    dst_dir = os.path.join(data_dir, LOG_SUBDIR)
    os.makedirs(dst_dir, exist_ok=True)
    for name in os.listdir(src_dir):
        s = os.path.join(src_dir, name)
        d = os.path.join(dst_dir, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    return dst_dir


# --- 폴더 전체(D:\Database 등) 백업/복원 --------------------------------
def _robocopy(src, dst, extra_args, timeout=1800):
    proc = subprocess.run(
        ["robocopy", src, dst, "/MIR", "/R:1", "/W:1"] + list(extra_args),
        capture_output=True, timeout=timeout)
    # robocopy는 0~7이 정상(복사/스킵 조합), 8 이상이 실제 오류다.
    if proc.returncode >= 8:
        raise DbResetError(
            "robocopy 실패(종료코드 %d): %s -> %s\n%s"
            % (proc.returncode, src, dst,
               proc.stdout.decode("utf-8", "replace")[-2000:]))
    return proc.returncode


def backup_folder(data_dir, out_dir):
    """`data_dir` 전체를 `out_dir`로 미러링한다(robocopy /MIR).

    DB 파일(*.mdf/*.ldf)은 SQL Server가 점유 중이라 애초에 복사가 실패한다
    (2절 실측과 동일한 원리, 예상된 동작) — DB는 `backup()`으로 따로 다룬다.
    """
    os.makedirs(out_dir, exist_ok=True)
    extra = []
    for pat in FOLDER_RESTORE_EXCLUDE_FILES:
        extra += ["/XF", pat]
    rc = _robocopy(data_dir, out_dir, extra)
    return {"out_dir": out_dir, "returncode": rc}


def restore_folder(baseline_dir, data_dir, confirm=False, stop_processes=True,
                    safety_backup_dir=None):
    """`data_dir`를 `baseline_dir` 상태로 되돌린다(robocopy /MIR). **파괴적 조작이다.**

    confirm=True 없이 호출하면 아무 것도 하지 않고 예외를 던진다.
    `Bak/`(DB 백업 이력)과 `log/`(운영 로그)는 절대 지우지 않는다
    (`FOLDER_RESTORE_EXCLUDE_DIRS`) — baseline 스냅샷에 그 폴더들이 있어도
    없어도, 지금 이 PC에 있는 내용을 그대로 둔다.
    """
    if not confirm:
        raise DbResetError(
            "폴더 복원은 명시적 승인이 필요합니다. restore_folder(..., confirm=True). "
            "이 조작은 현재 폴더 내용을 baseline으로 덮어씁니다(Bak/log 제외).")
    if not os.path.isdir(baseline_dir):
        raise DbResetError("baseline 폴더가 없습니다: %s" % baseline_dir)

    stopped = stop_app() if stop_processes else []

    safety = None
    if safety_backup_dir:
        safety = backup_folder(data_dir, safety_backup_dir)

    extra = []
    for pat in FOLDER_RESTORE_EXCLUDE_FILES:
        extra += ["/XF", pat]
    extra += ["/XD"] + [os.path.join(data_dir, d) for d in FOLDER_RESTORE_EXCLUDE_DIRS]
    rc = _robocopy(baseline_dir, data_dir, extra)

    return {"stopped": stopped, "returncode": rc, "safety_backup": safety}
