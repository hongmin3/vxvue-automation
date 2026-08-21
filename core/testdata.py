# -*- coding: utf-8 -*-
r"""실행마다 **구분되는** 시험 처방을 만든다.

## 왜 필요한가

사용자 지적(2026-08-21): *"patient id가 다 너무 똑같아서 실제 import가 잘되었는지
확인이 불가능한데, 날짜 시간 이런 걸 id에 넣는 건 불가능할까? 각 patient 생성할 때
출생일 성별 이런 걸 랜덤으로 설정해서 등록하게 해주는 것도 좋은 것 같아."*

맞는 지적이고, 판정의 신뢰도 문제다. `config.json`의 시험 처방은 지금까지 고정
값이었다(`VXVUE_MWL_DX_01` / `ACC_VX_AUTO_001`). 그래서 Database 목록에 같은
Patient ID의 스터디가 수십 건 쌓여 있고, TC08의 역방향 Import 판정이 "Export한
그 스터디가 들어왔다"가 아니라 **"같은 ID를 가진 어떤 스터디가 있다"** 밖에 확인하지
못했다. 실행마다 값이 달라야 그 구분이 생긴다.

## 무엇을 바꾸고 무엇을 고정하는가

| 필드 | 처리 | 이유 |
|---|---|---|
| `mwl_patient_id` | **실행 시각 각인** | 그 실행의 스터디를 목록에서 유일하게 지목 |
| `mwl_patient_name` | 실행 시각 각인 | 위와 같음 |
| `mwl_accession` | 실행 시각 각인 | Print Overlay `Acc. No.`·Export 태그 대조에 쓰임 |
| `mwl_sps_id` | 실행 시각 각인 | 처방 단계 식별자 |
| `mwl_patient_sex` | 시각 시드 기반 선택 | 열 값이 실제로 처방에서 온 것인지 구분 |
| `mwl_patient_birthdate` | 시각 시드 기반 선택 | 위와 같음 |
| `mwl_procedure_id` | **고정** | `--map-procedure`의 Procedure Code 매핑 대상이다. 매 실행마다 바뀌면 제품의 매핑 표에 항목이 쌓이고 매번 다시 매핑해야 한다 |
| `mwl_procedure_description` / `mwl_sps_description` | **고정** | 위와 같은 이유(매핑·Step 등록의 기준) |
| `mwl_modality` | **고정** | 회귀 대상 Modality 자체가 시험 조건이다 |

**성별·생년월일은 난수가 아니라 실행 시각을 시드로 뽑는다.** 완전한 난수로 하면
리포트에 남은 값으로 되짚어도 같은 조건을 다시 만들 수 없다. 시각을 시드로 쓰면
`VXVUE_260821_150312`라는 ID만 보고 그 실행의 성별·생년월일을 그대로 재현할 수
있다 — 실측 근거를 남기라는 CLAUDE.md 3절 원칙과 같은 방향이다.

## 언제 새로 뽑고, 언제 그대로 쓰는가

사용자 지시(2026-08-21): *"mwl에서 스터디를 생성을 너가 하잖아, 그때부터 랜덤으로
생성되게 해줘. 기존 환자는 삭제하고."* 그래서 **새 값을 뽑는 시점은 MWL 처방을
만드는 순간 하나뿐**이다.

* `new_for_mwl(cfg)` — MWL 처방을 만들기 직전에 부른다. 새 각인을 뽑아
  `cfg["test_data"]`에 넣고 **상태 파일에 기록**한다.
* `load(cfg)` — 그 밖의 모든 명령이 시작할 때 부른다. 상태 파일에 기록된
  **가장 최근에 만든 처방**을 그대로 읽어 쓴다.

이렇게 나눈 이유가 있다. `python run.py mwl-ensure`와 `python run.py tc08`은
**서로 다른 프로세스**다. 실행할 때마다 각인을 새로 뽑으면 tc08이 존재하지 않는
환자를 Registration 목록에서 찾다 실패한다. 상태 파일을 두면 "만든 처방"과
"쓰는 처방"이 어긋나지 않는다.

상태 파일은 `Cache/current_testdata.json`이다 — `Cache/`는 `.gitignore` 대상이라
환자 식별자가 공개 저장소로 나가지 않는다.

끄려면 `config.json`에 `"test_data": {"unique_per_run": false}`를 둔다. 그러면
예전처럼 config의 고정 값을 쓴다.

## 기존 처방 삭제

`prune_auto_orders()`가 **이 자동화가 만든 처방만** 지운다 — `patient_id`가
`VXVUE_`로 시작하는 것(예전 고정값 `VXVUE_MWL_DX_01`도 여기 걸린다). 다른 제품의
시험 처방(Bellalun `DATA_FLOW_MWL_01` 등)은 접두가 달라 건드리지 않는다.
**VXvue DB의 스터디는 지우지 않는다** — 그건 훨씬 파괴적인 조작이고
`core/dbreset.py`의 백업/복원이 담당한다.
"""

import datetime
import random

# 각인하는 필드와 그 서식. `{stamp}`는 `YYMMDD_HHMMSS`.
STAMPED_FIELDS = {
    "mwl_patient_id": "VXVUE_{stamp}",
    "mwl_patient_name": "AUTO^VX{stamp}^^^",
    "mwl_accession": "ACC_{stamp}",
    "mwl_sps_id": "SPS_{stamp}",
}

# 고정하는 필드(위 docstring 표 참고) — 각인 대상에서 명시적으로 제외한다.
KEPT_FIELDS = ("mwl_modality", "mwl_procedure_id", "mwl_procedure_description",
               "mwl_sps_description", "mwl_sps_start_time")

SEXES = ("M", "F")
BIRTH_YEAR_RANGE = (1945, 2005)


def run_stamp(now=None):
    """`YYMMDD_HHMMSS` — 실행을 가리키는 각인."""
    now = now or datetime.datetime.now()
    return now.strftime("%y%m%d_%H%M%S")


def derive_demographics(stamp):
    """각인을 시드로 성별·생년월일을 뽑는다(같은 각인 → 같은 값)."""
    rnd = random.Random(stamp)
    sex = rnd.choice(SEXES)
    year = rnd.randint(*BIRTH_YEAR_RANGE)
    month = rnd.randint(1, 12)
    # 말일 문제를 피하려고 28일까지만 쓴다 — 생년월일의 정확한 분포는 이
    # 시험에서 의미가 없고, 목록 열 값이 처방에서 왔는지 구분하는 것이 목적이다.
    day = rnd.randint(1, 28)
    return sex, "%04d-%02d-%02d" % (year, month, day)


def stamp(cfg, now=None):
    """`cfg["test_data"]`에 이번 실행용 값을 채운다(제자리 변경).

    반환: {"applied": bool, "stamp": str, "values": {...}, "note": str}
    """
    td = cfg.setdefault("test_data", {})
    if td.get("unique_per_run") is False:
        return {"applied": False, "stamp": None, "values": {},
                "note": "test_data.unique_per_run=false — 고정 시험 처방을 쓴다."}
    if td.get("_run_stamp"):
        # 한 실행 안에서 두 번 불려도 값이 바뀌지 않아야 한다.
        return {"applied": True, "stamp": td["_run_stamp"],
                "values": {k: td.get(k) for k in STAMPED_FIELDS},
                "note": "이미 이 실행의 처방이 정해져 있다(%s)." % td["_run_stamp"]}

    s = run_stamp(now)
    values = {}
    for key, template in STAMPED_FIELDS.items():
        values[key] = template.format(stamp=s)
    sex, birth = derive_demographics(s)
    values["mwl_patient_sex"] = sex
    values["mwl_patient_birthdate"] = birth

    td.update(values)
    td["_run_stamp"] = s
    return {"applied": True, "stamp": s, "values": values,
            "note": ("이번 실행 시험 처방: %s (성별 %s, 생년월일 %s). 고정 필드: %s"
                     % (values["mwl_patient_id"], sex, birth,
                        ", ".join("%s=%s" % (k, td.get(k)) for k in KEPT_FIELDS
                                  if td.get(k))))}


def describe(cfg):
    """리포트·로그에 남길 한 줄 설명."""
    td = cfg.get("test_data") or {}
    if not td.get("_run_stamp"):
        return "시험 처방=고정값 (%s)" % td.get("mwl_patient_id")
    return ("시험 처방=%s / 이름=%s / Acc=%s / 성별=%s / 생년월일=%s (각인 %s)"
            % (td.get("mwl_patient_id"), td.get("mwl_patient_name"),
               td.get("mwl_accession"), td.get("mwl_patient_sex"),
               td.get("mwl_patient_birthdate"), td.get("_run_stamp")))

# --- 상태 파일 -------------------------------------------------------
# `Cache/`는 .gitignore 대상이다(환자 식별자를 공개 저장소로 내보내지 않는다).
STATE_DIRNAME = "Cache"
STATE_FILENAME = "current_testdata.json"

# 이 자동화가 만든 처방을 알아보는 접두. 예전 고정값(`VXVUE_MWL_DX_01`)도 걸린다.
AUTO_PATIENT_PREFIX = "VXVUE_"


def state_path(root=None):
    import os
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, STATE_DIRNAME, STATE_FILENAME)


def load(cfg, root=None):
    """가장 최근에 만든 처방을 `cfg["test_data"]`에 얹는다.

    상태 파일이 없거나 `unique_per_run=false`면 config의 고정 값을 그대로 쓴다.
    반환: {"applied", "stamp", "note"}
    """
    import json
    import os
    td = cfg.setdefault("test_data", {})
    if td.get("unique_per_run") is False:
        return {"applied": False, "stamp": None,
                "note": "test_data.unique_per_run=false — 고정 처방을 쓴다."}
    path = state_path(root)
    if not os.path.exists(path):
        return {"applied": False, "stamp": None,
                "note": ("아직 만든 처방이 없다(%s 없음) — config의 고정 값을 쓴다. "
                         "`python run.py mwl-ensure`를 먼저 실행하면 그때 새로 "
                         "뽑는다." % STATE_FILENAME)}
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError) as exc:
        return {"applied": False, "stamp": None,
                "note": "상태 파일을 읽지 못했다(%s) — 고정 값을 쓴다." % exc}
    values = saved.get("values") or {}
    td.update(values)
    td["_run_stamp"] = saved.get("stamp")
    return {"applied": bool(values), "stamp": saved.get("stamp"),
            "note": "기록된 처방을 불러왔다: %s" % describe(cfg)}


def save(cfg, root=None):
    import json
    import os
    td = cfg.get("test_data") or {}
    path = state_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"stamp": td.get("_run_stamp"),
               "values": {k: td.get(k) for k in
                          list(STAMPED_FIELDS) + ["mwl_patient_sex",
                                                  "mwl_patient_birthdate"]
                          if td.get(k) is not None}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return path


def new_for_mwl(cfg, now=None, root=None):
    """MWL 처방을 만들기 직전에 부른다 — 새 각인을 뽑아 기록까지 한다."""
    td = cfg.setdefault("test_data", {})
    if td.get("unique_per_run") is False:
        return {"applied": False, "stamp": None, "values": {},
                "note": "test_data.unique_per_run=false — 고정 처방을 쓴다."}
    td.pop("_run_stamp", None)           # 새로 뽑도록 이전 각인을 지운다
    res = stamp(cfg, now=now)
    if res.get("applied"):
        res["state_path"] = save(cfg, root=root)
    return res


def prune_auto_orders(mwl, keep_patient_id=None, prefix=AUTO_PATIENT_PREFIX):
    """이 자동화가 만든 지난 MWL 처방을 지운다.

    사용자 지시(2026-08-21): *"기존 환자는 삭제하고."* 실행마다 patient_id가
    달라지면 `ensure_order()`의 "같은 patient_id의 지난 처방 삭제"가 더는
    걸리지 않아 처방이 계속 쌓인다. 그래서 접두로 이 자동화의 것만 골라 지운다.

    **다른 제품의 처방은 건드리지 않는다** — 접두가 다르면 건너뛴다.
    반환: {"deleted": n, "kept": [...], "deleted_ids": [...]}
    """
    deleted, deleted_ids, kept = 0, [], []
    for item in mwl.list_items():
        pid = str(item.get("patient_id") or "")
        if not pid.startswith(prefix):
            kept.append(pid)
            continue
        if keep_patient_id and pid == keep_patient_id:
            kept.append(pid)
            continue
        if mwl.delete(item["id"]):
            deleted += 1
            deleted_ids.append(pid)
    return {"deleted": deleted, "kept": sorted(set(kept)),
            "deleted_ids": deleted_ids}
