# -*- coding: utf-8 -*-
"""Setting Export 파일(`.vxs`) 판독.

2026-08-18 실측: Setting 좌하단 `Export`가 만드는 `.vxs`는 **ZIP 아카이브**이고
기본 파일명은 `VXvueSetting.vxs`다(확장자를 다르게 주면 뒤에 `.vxs`가 덧붙는다).

내용물(2,491 엔트리):

| 최상위 | 내용 |
|---|---|
| `Data.bak` | **DRF DB 전체 네이티브 백업**(MTF `TAPE` 헤더, 약 9.9MB) |
| `Configuration/` | Configuration.xml, Property.json, CamAppClientSetting.ini 등 9개 |
| `LUT_Data/` | 1.lut ~ 8.lut |
| `PARAMETER/` | XIPL 파라미터 (.pim/.eap/.xtp/.egp) |
| `BodypartCategory/` | 부위 아이콘 bmp |
| (기타) | 디텍터 데이터 .hs8 / .pi 각 1,218개 |

**중요**: `Data.bak`이 DB 전체 백업이므로 Import는 "설정 되돌리기"가 아니라
**DB 전체 복원**이다. export 이후 생성된 환자·검사가 사라진다. Import를 호출하는
쪽은 반드시 사전 백업을 남겨야 한다(`core/dbreset.py`).

또 `C:\\ProgramData\\VXvue\\Viewer.xml`은 이 파일에 **포함되지 않는다.** 따라서
Theme/Language/Generator/AIEngine/Camera 같은 머신 단위 설정은 Import로
복원되지 않는다 — 사용자 확인(2026-08-18): **정상 동작이며 판정에서 제외**한다.
"""

import os
import zipfile

DEFAULT_EXPORT_NAME = "VXvueSetting.vxs"
DB_BACKUP_ENTRY = "Data.bak"

# 값 비교에서 제외할 엔트리. DB 백업은 같은 내용이어도 바이트가 매번 달라진다
# (백업 헤더에 타임스탬프/LSN이 들어간다). 이것을 비교에 넣으면 항상 FAIL이 난다.
VOLATILE_ENTRIES = (DB_BACKUP_ENTRY,)

# 사용자 확인(2026-08-18): export 범위 밖이라 판정에서 제외하는 설정 파일
OUT_OF_SCOPE_FILES = (r"C:\ProgramData\VXvue\Viewer.xml",)


class VxsError(RuntimeError):
    pass


def is_vxs(path):
    return bool(path) and os.path.exists(path) and zipfile.is_zipfile(path)


def entries(path, skip_volatile=True):
    """엔트리별 (크기, CRC) 맵. 설정 변화 비교의 기본 단위다."""
    if not is_vxs(path):
        raise VxsError("ZIP 형식의 .vxs 파일이 아닙니다: %s" % path)
    out = {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if skip_volatile and info.filename in VOLATILE_ENTRIES:
                continue
            out[info.filename] = (info.file_size, info.CRC)
    return out


def summary(path):
    """리포트에 넣을 요약. 확인만 하고 압축을 풀지 않는다."""
    if not is_vxs(path):
        return {"path": path, "valid": False}
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        roots = {}
        for i in infos:
            root = i.filename.split("/")[0]
            roots[root] = roots.get(root, 0) + 1
        has_db = any(i.filename == DB_BACKUP_ENTRY for i in infos)
        db_size = next((i.file_size for i in infos if i.filename == DB_BACKUP_ENTRY), 0)
    return {"path": path, "valid": True,
            "size_bytes": os.path.getsize(path),
            "entry_count": len(infos),
            "roots": roots,
            "has_db_backup": has_db,
            "db_backup_bytes": db_size}


def diff(path_a, path_b):
    """두 export 파일의 엔트리 차이. Data.bak은 제외한다.

    반환: dict(added=[...], removed=[...], changed=[...], same=n)
    `changed`는 크기나 CRC가 다른 엔트리 이름 목록이다.
    """
    a, b = entries(path_a), entries(path_b)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = sorted(k for k in (set(a) & set(b)) if a[k] != b[k])
    same = len(set(a) & set(b)) - len(changed)
    return {"added": added, "removed": removed, "changed": changed, "same": same}


def identical(path_a, path_b):
    d = diff(path_a, path_b)
    return not (d["added"] or d["removed"] or d["changed"]), d


def read_text_entry(path, entry, encodings=("utf-8-sig", "utf-8", "utf-16")):
    """설정 텍스트 엔트리(xml/json/ini)를 읽는다. 없으면 None."""
    with zipfile.ZipFile(path) as z:
        if entry not in z.namelist():
            return None
        data = z.read(entry)
    for enc in encodings:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return data.decode("utf-8", "replace")


def extract_db_backup(path, out_path):
    """`Data.bak`을 꺼낸다. 복원 전 내용 확인이나 별도 보관에 쓴다."""
    with zipfile.ZipFile(path) as z:
        if DB_BACKUP_ENTRY not in z.namelist():
            raise VxsError("%s 엔트리가 없습니다." % DB_BACKUP_ENTRY)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with z.open(DB_BACKUP_ENTRY) as src, open(out_path, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
    return out_path
