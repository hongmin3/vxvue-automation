# -*- coding: utf-8 -*-
"""설정 스냅샷 — Setting Export/Import 회귀의 판정 오라클.

## 왜 UI로 설정값을 읽지 않는가

Setting 화면의 좌측 메뉴와 체크박스·라디오는 커스텀 owner-draw라
`GetWindowText`로 **상태를 읽을 수 없다**(실측). Edit/콤보는 읽히지만 전체
설정의 일부에 불과하다. "전체 탭을 돌며 현재 설정을 확인"을 UI 판독으로
구현하면 판정 근거가 부실해진다.

대신 **DB의 설정 테이블 + 설정 파일 해시**를 스냅샷으로 쓴다. 값 단위로
정확하고, 화면을 열지 않아도 되며, diff가 그대로 리포트가 된다. UI 캡처는
사람이 검토할 증적으로만 남긴다.

## 스냅샷 범위

- `CONFIGURATION` 및 `CONFIGURATION_*` 테이블 전체 (실행 시점에 자동 열거)
- `AE_LIST`(DICOM SCP 등록 + `RemoveSBSC`)
- Procedure Manager 계열: `TB_PROCEDURE` / `PROCSTEP` / `STEP` / `LOCATION*`
- 그 외 설정성 테이블: `LUT`, `IMAGE_PROCESS_PARAM*`, `STITCH_PROTOCOL*`,
  `PRE_DEFINED_TEXT_*`, `EXTENDED_FIELD`, `USER_DEFINED_FIELD_MAPPING`,
  `SMTP_INFO`, `STORAGE_PROTOCOL`, `BACKUP_DEVICE`, `TARGET_*`, `REASON`
- `D:\\Database\\Configuration\\*` 파일 SHA-256
- `C:\\ProgramData\\VXvue\\Viewer.xml` SHA-256 — **export 범위 밖이므로 판정에서
  제외**하고 참고 정보로만 기록한다(사용자 확인, 2026-08-18)

환자·검사 데이터 테이블(`PATIENT`/`STUDY`/`SERIES`/`INSTANCE`)은 설정이 아니라
넣지 않는다. 단, Import가 DB 전체를 복원하는 파괴적 조작임을 리포트에 남기기
위해 **건수만** 따로 기록한다.
"""

import hashlib
import io
import json
import os
from datetime import datetime

# 설정성으로 분류하는 테이블(CONFIGURATION* 는 실행 시점에 자동으로 더한다)
EXTRA_SETTING_TABLES = (
    "AE_LIST", "LUT", "IMAGE_PROCESS_PARAM", "IMAGE_PROCESS_PARAM_MAPPING",
    "STITCH_PROTOCOL", "STITCH_PROTOCOL_STEP", "PRE_DEFINED_TEXT_GROUP",
    "PRE_DEFINED_TEXT_CONTENTS", "EXTENDED_FIELD", "USER_DEFINED_FIELD_MAPPING",
    "SMTP_INFO", "STORAGE_PROTOCOL", "BACKUP_DEVICE", "REASON",
    "TARGET_EXPOSURE_INDEX", "TARGET_PIXEL_VALUE", "STAND_TABLE_PARAM",
    "IMAGE_LAYOUT", "IMAGE_LAYOUT_INFO", "MAIL_BOOK",
    # Procedure Manager 계열
    "TB_PROCEDURE", "PROCSTEP", "STEP", "LOCATION", "LOCATION_STEP_LIST",
    "ANATOMIC", "BODYPARTCODE", "PROJECTIONCODE", "CATEGORY",
)

# 데이터(설정 아님) — 건수만 센다
DATA_TABLES = ("PATIENT", "STUDY", "SERIES", "INSTANCE", "ORDER_PATIENT",
               "RESERVED_PROCEDURE", "EXPORT_FILE")

CONFIG_FILE_DIR = r"D:\Database\Configuration"

# export 범위 밖이라 판정에서 제외하는 파일(참고 기록만)
OUT_OF_SCOPE_FILES = (r"C:\ProgramData\VXvue\Viewer.xml",)


def sha256(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def setting_tables(db):
    """스냅샷 대상 테이블 목록을 실행 시점에 결정한다.

    테이블 목록을 하드코딩하면 제품 버전이 올라가 새 설정 테이블이 생겼을 때
    조용히 빠진다. `CONFIGURATION*`는 패턴으로 잡고, 그 외는 위 목록과
    교집합을 취한다(존재하지 않는 테이블은 자동 제외).
    """
    rows = db.query(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
    present = set(r["TABLE_NAME"] for r in rows)
    names = sorted(t for t in present if t == "CONFIGURATION"
                   or t.startswith("CONFIGURATION_"))
    names += sorted(t for t in EXTRA_SETTING_TABLES if t in present)
    return names


def take(db, label="", config_file_dir=CONFIG_FILE_DIR):
    """설정 스냅샷을 취득한다."""
    tables = setting_tables(db)
    specs = [{"name": t, "sql": "SELECT * FROM [%s]" % t} for t in tables]
    data = db.query_many(specs)

    counts = {}
    count_specs = [{"name": t, "sql": "SELECT COUNT(*) AS c FROM [%s]" % t}
                   for t in DATA_TABLES]
    for name, rows in (db.query_many(count_specs) or {}).items():
        if isinstance(rows, list) and rows:
            counts[name] = rows[0].get("c")

    files = {}
    if config_file_dir and os.path.isdir(config_file_dir):
        for fn in sorted(os.listdir(config_file_dir)):
            p = os.path.join(config_file_dir, fn)
            if os.path.isfile(p):
                files[p] = sha256(p)

    out_of_scope = dict((p, sha256(p)) for p in OUT_OF_SCOPE_FILES)

    return {"label": label,
            "taken": datetime.now().isoformat(timespec="seconds"),
            "tables": data,
            "data_row_counts": counts,
            "files": files,
            "out_of_scope_files": out_of_scope}


def save(snapshot, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1, default=str,
                  sort_keys=True)
    return path


def load(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def _norm(rows):
    """행 목록을 비교 가능한 형태로 만든다.

    행 순서는 DB가 보장하지 않으므로 정렬한다. 값은 문자열로 정규화해
    타입 차이(정수 vs 문자열)로 헛된 차이가 생기지 않게 한다.
    """
    if not isinstance(rows, list):
        return [json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str)]
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append(json.dumps(dict((k, "" if v is None else str(v))
                                       for k, v in r.items()),
                                  ensure_ascii=False, sort_keys=True))
        else:
            out.append(str(r))
    return sorted(out)


def compare(a, b, ignore_out_of_scope=True):
    """두 스냅샷을 비교한다.

    반환: dict(
      identical=bool,
      table_diffs={table: {"only_in_a": [...], "only_in_b": [...]}},
      file_diffs={path: (hash_a, hash_b)},
      out_of_scope_diffs={path: (hash_a, hash_b)},   # 판정 제외, 참고용
      missing_tables=[...])
    """
    table_diffs, missing = {}, []
    names = sorted(set(a.get("tables", {})) | set(b.get("tables", {})))
    for t in names:
        ra, rb = a.get("tables", {}).get(t), b.get("tables", {}).get(t)
        if ra is None or rb is None:
            missing.append(t)
            continue
        na, nb = _norm(ra), _norm(rb)
        if na == nb:
            continue
        sa, sb = set(na), set(nb)
        table_diffs[t] = {"only_in_a": sorted(sa - sb)[:20],
                          "only_in_b": sorted(sb - sa)[:20],
                          "count_a": len(na), "count_b": len(nb)}

    file_diffs = {}
    for p in sorted(set(a.get("files", {})) | set(b.get("files", {}))):
        ha, hb = a.get("files", {}).get(p), b.get("files", {}).get(p)
        if ha != hb:
            file_diffs[p] = (ha, hb)

    oos = {}
    for p in sorted(set(a.get("out_of_scope_files", {}))
                    | set(b.get("out_of_scope_files", {}))):
        ha = a.get("out_of_scope_files", {}).get(p)
        hb = b.get("out_of_scope_files", {}).get(p)
        if ha != hb:
            oos[p] = (ha, hb)

    identical = not table_diffs and not file_diffs and not missing
    if not ignore_out_of_scope:
        identical = identical and not oos
    return {"identical": identical, "table_diffs": table_diffs,
            "file_diffs": file_diffs, "out_of_scope_diffs": oos,
            "missing_tables": missing}


def changed_names(cmp_result):
    """바뀐 테이블/파일 이름만 뽑아 요약 문자열로 만든다."""
    parts = []
    if cmp_result["table_diffs"]:
        parts.append("테이블 %d개(%s)" % (
            len(cmp_result["table_diffs"]),
            ", ".join(sorted(cmp_result["table_diffs"])[:8])))
    if cmp_result["file_diffs"]:
        parts.append("파일 %d개(%s)" % (
            len(cmp_result["file_diffs"]),
            ", ".join(os.path.basename(p) for p in sorted(cmp_result["file_diffs"])[:8])))
    if cmp_result["missing_tables"]:
        parts.append("한쪽에만 있는 테이블 %d개" % len(cmp_result["missing_tables"]))
    return " / ".join(parts) if parts else "차이 없음"
