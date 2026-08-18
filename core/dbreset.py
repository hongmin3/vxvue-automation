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
from datetime import datetime

DEFAULT_SERVER = r".\CHAMELEON"
DEFAULT_DB = "DRF"
DEFAULT_BACKUP_DIR = r"D:\Database\Database\Bak"

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


def stop_app(processes=APP_PROCESSES):
    """VXvue 관련 프로세스를 종료한다. 종료한 이름 목록을 반환.

    VXService 등 서비스는 건드리지 않는다 — 서비스를 임의로 멈추면 복원 후
    제품이 정상 기동하지 않는 상태를 만들 수 있고, `SINGLE_USER WITH ROLLBACK
    IMMEDIATE`가 남은 연결을 끊어주므로 필요하지 않다.
    """
    stopped = []
    for name in processes:
        out = _ps("$p = Get-Process -Name '%s' -ErrorAction SilentlyContinue; "
                  "if ($p) { $p | Stop-Process -Force; 'killed' }" % name)
        if out.strip() == "killed":
            stopped.append(name)
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
