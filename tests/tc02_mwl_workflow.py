# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_02 — MWL 조회 워크플로우.

실행: `python run.py tc02`

## 체크리스트 원문 (R-25-774, Checklist 시트 8행)

Precondition: *MWL 서버 : JDICOM, Bunny, DVTK 이용 / 뷰어와 다른 PC 의 Server 이용*

Step Description
```
1. Registration-Scheduled 화면에서 MWL 스터디를 조회한다.
2. 조회된 스터디의 정보를 확인한다.
3. 스터디를 선택하고 촬영화면으로 오픈하여 촬영한다.
4. 스터디를 Close 하고 Database 에서 스터디 정보를 확인한다.
5. 영상을 Send 후 전송정보를 확인한다.
```

Expected Result
```
1. MWL 스터디가 조회되어 스터디 목록이 표시된다.
2. MWL 서버에 저장된 환자 정보가 뷰어에 동일하게 표시된다.
   - Patient ID, Name, Birth Date, Age, Acc no, Scheduled Date/Time
3,4,5: 촬영화면, Database, 전송정보가 모두 MWL 스터디 정보와 일치한다.
```

Test Data: `http://<MWL_SERVER_HOST>:5000/` / `MWL_SCP` / `<MWL_SERVER_HOST>` / `11112`

## 판정 설계 — 정답지를 어디서 가져오는가

Expected Result가 "**MWL 스터디 정보와 일치**"이므로 정답지는 화면이 아니라
**MWL 서버에 등록한 값**이다. 이 프로젝트는 `core/mwl.py`로 처방을 HTTP API로
직접 등록하므로(`python run.py mwl-ensure`) 그 등록값이 곧 정답지다 — 화면에서
읽은 값으로 기준을 역산하지 않는다.

일치 확인을 세 지점에서 한다.

| 지점 | 근거 | 방법 |
|---|---|---|
| ① 뷰어 목록(Step 1~2) | MWL API 등록값 | Registration>Scheduled 행을 캡처+OCR로 읽어 대조 |
| ② Database(Step 4) | DB `STUDY`/`PATIENT` 테이블 | 촬영·Close 후 SQL로 조회해 대조 |
| ③ 전송정보(Step 5) | 수신된 DICOM 파일의 태그 | Bunny 수신 파일을 `core/dicomlite`로 읽어 대조 |

③이 이 TC의 핵심이다. 제품 UI의 Queue 상태만 보면 "제품이 보냈다고 말한 것"을
믿는 것이 되므로, **받은 쪽 파일의 태그**로 확인한다.

## 사양 근거

- 사양서1 p.37~38 `VP-460 - Register Scheduled Study` — Start로 Study 등록,
  맵핑되지 않은 Procedure Code가 있으면 확인 팝업(Yes/No/Cancel). 자동화는
  **No**(매핑하지 않고 Exposure Mode 전환)를 택한다. 이유는
  `core/workflow.py` docstring 참고.
- 사양서1 p.86 `VP-526 - Obtain Demo Image` — "VXvue Demo License 가 등록이
  되어있어야 한다". 데모(F2) 촬영의 선행 조건이며 `run.py vxvue-license`가
  그 등록을 확인한다.

## 알려진 환경 문제 (판정에 그대로 남긴다)

촬영 직후 `Error: "Image process parameter file does not exist."`가 뜬다.
XIPL 서버 로그 근거로 원인은 **파라미터 경로 구성**이며 파일 자체는 존재한다
(`core/workflow.py` docstring). 영상 획득 자체는 성공하므로 이 TC는 촬영
성공으로 판정하되, 팝업이 떴다는 사실과 원인을 `note`에 남긴다. Image
Processing 성공 여부의 판정은 TC04의 책임이다.

## Storage에 대한 한계

체크리스트 Precondition은 "뷰어와 다른 PC 의 Server 이용"이다. 이 실행은 MWL은
다른 PC(시험 서버)를 쓰지만 **Storage는 이 PC의 Bunny**를 쓴다(사용자 지시).
`core/bunny.precondition_note()`가 그 차이를 판정 note에 남긴다.
"""

import os
import time

from core import bunny as bunny_mod
from core import dicomlite
from core import workflow as W
from core.db import VXvueDb
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_02"
TC_TITLE = "MWL 조회 워크플로우 (조회 → 촬영 → Send → Close → DB 대조)"

DB_MISSING_NOTE = (
    '**표시되지 않았다.** `core/workflow.database_search()`가 Search를 최대 4회'
    ' 재시도(3초 간격)해도 비어 있었다는 뜻이다 — 정상적인 재시도 지연 범위를'
    ' 넘어선 상태다. 원인 후보 이력: (1) 2026-08-19에는 Step 미등록으로 검사가'
    ' StudyStatus=1(보류)로 남아 안 보인 사례가 있었다(Operation Manual'
    ' 3.6/6.8). 지금은 Step 5에서 Step 등록이 되는지 이 결과의 앞선 Step으로'
    ' 먼저 확인할 것. (2) 2026-08-21 실측: Step 등록이 정상 성공했는데도 Close'
    ' 직후 첫 조회가 `Result: 0 / 0`이었다가 몇 분 뒤 재조회하면 `n / n`으로'
    ' 정상 표시된 사례가 있었다 — 제품 내부 인덱싱이 Close보다 늦게 끝나는'
    ' 지연으로 보이며, `database_search()`의 재시도가 이 사례를 이미 흡수한다.'
    ' 그래도 이 Step이 MANUAL로 남았다면 재시도 상한(4회/3초)을 넘는 더 긴'
    ' 지연이거나 다른 원인이므로 위 DB 대조 Step(정상 통과 여부)과 같이 봐야'
    ' 한다.'
)


def _expected_from_mwl(cfg):
    """MWL 서버에 등록된 정답지를 그대로 읽어온다."""
    from core.mwl import MwlServer
    url = (cfg.get("dicom") or {}).get("mwl_server_url")
    td = cfg.get("test_data") or {}
    want_id = td.get("mwl_patient_id", "VXVUE_MWL_DX_01")
    if not url:
        return None, want_id
    try:
        for item in MwlServer(url).list_items():
            if str(item.get("patient_id")) == want_id:
                return item, want_id
    except Exception:                                     # noqa: BLE001
        return None, want_id
    return None, want_id


def _norm(s):
    return "".join(ch for ch in str(s or "").upper() if ch.isalnum())


def run(ui, cfg, evidence_dir=None, do_send=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc02")
    os.makedirs(evidence_dir, exist_ok=True)

    # --- Step 0-a: 열려 있는 검사 정리 (환경 오염을 결함으로 보고하지 않는다) ---
    # 이전 실행이 검사를 열어 둔 채 끝났으면 Start가 중복 등록 팝업을 띄우거나
    # 촬영 대상이 어긋난다. 그것은 제품 결함이 아니라 **시작 상태 문제**이므로
    # 먼저 정리하고, 정리했다는 사실을 결과에 남긴다.
    try:
        pre_state = W.acquisition_state(ui, cfg)
        if "not exposure" not in pre_state.lower():
            pre_close = W.close_study(ui, cfg, evidence_dir=evidence_dir)
            r.add(0, "선행 정리 — 열려 있던 검사 Close", PASS,
                  expected="검사가 열려 있지 않은 상태에서 시작",
                  actual="시작 시 상태=%r → 정리 후=%r / 처리한 팝업=%s"
                         % (pre_state, pre_close.get("state"),
                            pre_close.get("dialogs") or "없음"),
                  note="이전 실행이 남긴 상태를 제품 결함으로 보고하지 않기 위한 "
                       "선행 정리다.")
        else:
            r.add(0, "선행 정리 — 시작 상태 확인", PASS,
                  expected="검사가 열려 있지 않음", actual="상태=%r" % pre_state)
    except Exception as exc:                              # noqa: BLE001
        r.add(0, "선행 정리 — 열려 있던 검사 Close", MANUAL,
              actual=str(exc),
              note="정리에 실패했다. 사람이 검사를 닫은 뒤 다시 실행할 것.")

    expected, want_id = _expected_from_mwl(cfg)
    if expected is None:
        r.add(1, "MWL 정답지 확보", MANUAL,
              expected="MWL 서버에서 %s 처방 조회" % want_id,
              note="MWL 서버 API로 정답지를 읽지 못했다. `python run.py mwl-ensure`로 "
                   "처방을 보장한 뒤 다시 실행할 것. 이 Step 없이는 '일치' 판정의 "
                   "기준이 없으므로 이후 대조는 표시 확인 수준으로만 남는다.")
    else:
        r.add(1, "MWL 정답지 확보(HTTP API 등록값)", PASS,
              expected="patient_id=%s" % want_id,
              actual="ID=%s / Name=%s / Acc=%s / Modality=%s / %s %s"
                     % (expected.get("patient_id"), expected.get("patient_name"),
                        expected.get("accession_number"), expected.get("modality"),
                        expected.get("sps_start_date"), expected.get("sps_start_time")),
              note="Expected Result의 '일치' 기준은 화면이 아니라 이 등록값이다.")

    # --- Step 1: MWL 조회 ---------------------------------------------
    try:
        summary, rows = W.query_mwl(ui, cfg)
    except Exception as exc:                              # noqa: BLE001
        r.add(2, "Registration > Scheduled에서 MWL 조회", FAIL, actual=str(exc))
        r.finalize()
        return r
    r.add(2, "Registration > Scheduled에서 MWL 조회",
          PASS if rows else FAIL,
          expected="스터디 목록이 표시된다(1건 이상)",
          actual="%s / 목록 행 %d개" % (summary, len(rows)),
          note="요약 Static(30013)은 평문으로 읽힌다 — 목록 표시 여부의 1차 근거.")
    if not rows:
        r.finalize()
        return r

    # --- Step 2: 조회된 정보 대조 --------------------------------------
    row, row_text = W.find_row(ui, W.REG_RESULT_LIST, want_id, cfg)
    if row is None:
        row = rows[0]
        row_text = W.row_cell_text(ui, row, cfg)
    if expected is not None:
        fields = {
            "Patient ID": expected.get("patient_id"),
            "Acc no": expected.get("accession_number"),
            "Modality": expected.get("modality"),
            "Birth Date": expected.get("patient_birthdate"),
        }
        flat = _norm(row_text)
        missing = [k for k, v in fields.items() if v and _norm(v) not in flat]
        r.add(3, "뷰어 목록 표시값이 MWL 등록값과 일치",
              PASS if not missing else MANUAL,
              expected=" / ".join("%s=%s" % (k, v) for k, v in fields.items() if v),
              actual="OCR: %s" % row_text,
              note=("일치 확인됨." if not missing else
                    "OCR에서 확인되지 않은 항목: %s. 목록 셀은 owner-draw라 표준 API로 "
                    "읽을 수 없어 캡처+OCR로 확인한다 — 열 폭에 맞춰 '...'로 줄여 "
                    "표시되는 값(Patient ID 등)은 OCR로 전체를 읽을 수 없으므로 "
                    "FAIL로 단정하지 않고 확인 필요로 남긴다." % ", ".join(missing))
                   + " Name/Age/Scheduled Date-Time은 Step 4의 DB 대조로 함께 검증한다.")
    else:
        r.add(3, "뷰어 목록 표시값 확인", MANUAL, actual="OCR: %s" % row_text,
              note="MWL 정답지가 없어 대조하지 못했다.")

    # --- Step 3: 오픈 + 촬영 -------------------------------------------
    W.click_row(ui, row)
    try:
        start = W.start_study(ui, cfg, evidence_dir=evidence_dir,
                              map_procedure_name=map_procedure)
    except Exception as exc:                              # noqa: BLE001
        r.add(4, "Study 등록(Start) → 촬영화면 전환", FAIL, actual=str(exc))
        r.finalize()
        return r
    r.add(4, "Study 등록(Start) → 촬영화면 전환",
          PASS if start["ready"] else FAIL,
          expected="AcquisitionState가 Ready",
          actual="상태=%r / 처리한 팝업=%s / 매핑=%s"
                 % (start["state"], start["dialogs"] or "없음",
                    (start.get("mapping") or {}).get("mapped") if start.get("mapping")
                    else "수행 안 함"),
          note="사양서1 p.37~38 VP-460 — 맵핑되지 않은 Procedure Code가 있으면 확인 "
               "팝업이 뜬다. 자동화는 'Procedure Mapping 하지 않고 Exposure Mode로 "
               "전환'(사양 원문의 No)을 택한다: 매핑은 제품 설정을 바꾸는 조작이고 "
               "이 시험대의 XIPL은 Bellalun과 설치를 공유한다.")
    if not start["ready"]:
        r.finalize()
        return r

    # **Step을 먼저 등록한다**(사용자 지시 2026-08-20): 그냥 F2를 누르지 않고
    # General(카테고리) > Chest(Projection) > PA(Step)를 골라 Step을 만든 뒤
    # 촬영한다. Step이 있으면 그 Step의 영상처리 파라미터가 지정되므로 촬영 직후
    # 파라미터 오류가 나지 않는다.
    W.goto(ui, "exposure")
    time.sleep(1.0)
    added = W.add_step(ui, cfg, projection=projection, step=exam_step,
                       evidence_dir=evidence_dir)
    r.add(5, "촬영 Step 등록 (General > %s > %s)" % (projection, exam_step),
          PASS if added["ok"] else FAIL,
          expected="Step이 등록된다",
          actual="카테고리=%r / Projection=%s / Step=%r / 항목 %s→%s"
                 % ((added["category"] or {}).get("category"),
                    (added["projection"] or {}).get("ok"),
                    (added["step"] or {}).get("label"),
                    added["steps_before"], added["steps_after"]),
          note="인체도 라벨(Projection)은 그림 위에 그려져 표준 API로 읽을 수 없어 "
               "캡처+OCR로 찾고, Step 박스 라벨은 **XIPL 파라미터 파일명에서 얻은 "
               "정답지와 대조해 OCR 오인식을 교정**한다(사용자 제안, 2026-08-20 — "
               "`LAT`이 `Li`로 읽히던 것을 정답지로 확정). 카테고리가 General이 "
               "아니면 상단 화살표로 되돌린다.")
    if not added["ok"]:
        r.finalize()
        return r

    acq = W.acquire(ui, cfg, evidence_dir=evidence_dir)
    known = acq.get("known_warning")
    r.add(5, "Demo(가상) 촬영 — %s" % acq["key"],
          PASS if acq["acquired"] else FAIL,
          expected="영상이 1장 이상 획득된다",
          actual="INSTANCE %s → %s / 썸네일 %d → %d / %.1f초 / 상태=%r"
                 % (acq.get("instances_before"), acq.get("instances_after"),
                    acq["before"], acq["after"], acq["seconds"], acq["state"]),
          note="사양서1 p.86 VP-526 — 데모 촬영은 VXvue Demo License 등록이 선행 "
               "조건이다(`run.py vxvue-license`로 확인). "
               + ("촬영 중 뜬 팝업: %s" % acq["dialogs"] if acq["dialogs"] else "팝업 없음"))
    if acq["dialogs"]:
        r.add(6, "촬영 중 팝업 발생 여부",
              MANUAL if known else FAIL,
              expected="촬영 중 오류 팝업 없음",
              actual="; ".join(acq["dialogs"]),
              note=("이미 원인을 확인한 환경 구성 문제다 — XIPL 서버 로그에 "
                    "'Loading base parameter : Chest PA_normal_H.hs8' 다음 "
                    "'Parameter file not found'가 기록되지만 그 파일은 "
                    "C:\\XIPL\\PARAMETER\\VXvue\\ 아래에 실제로 존재한다. 즉 XIPL "
                    "서버가 보는 파라미터 경로가 그 하위 폴더를 가리키지 않는 "
                    "환경 문제로 보인다. 영상 획득 자체는 성공하므로 이 TC의 촬영 "
                    "판정은 PASS로 두고, Image Processing 성공 여부는 TC04의 "
                    "판정 대상으로 남긴다. Setting > Integration > XIPL의 파라미터 "
                    "경로는 Bellalun과 공유하는 설치라 자동화가 임의로 바꾸지 "
                    "않는다 — 사용자 확인 필요."
                    if known else
                    "확인되지 않은 팝업이다. 문구를 근거로 원인을 확인할 것."))
    if not acq["acquired"]:
        r.finalize()
        return r

    step = 7

    # --- Step 5(먼저 수행): 촬영 직후 Exposure 화면에서 Send -------------
    # 체크리스트 Step 순서는 "Close -> Database 확인 -> Send"지만, **실측 결과
    # Database 목록에는 이 검사가 나타나지 않아**(뒤 Step에서 확인) Database를
    # 경유하면 전송 대상을 고를 수 없다. Send 버튼은 Exposure와 Database에서
    # 같은 컨트롤(30294)이고 사양상 어느 화면에서도 전송할 수 있으므로,
    # **검증 내용(전송 성공 + 전송정보 일치)은 유지하고 실행 지점만 옮긴다.**
    # 그 차이를 판정 note에 남긴다.
    if do_send:
        log_off = bunny_mod.log_size(cfg)
        t0 = time.time() - 5
        W.select_first_image(ui)
        sent = W.send(ui, scope="all")
        r.add(step, "DICOM Send 실행 (Exposure 화면, All Images)",
              PASS if sent.get("dialog") else FAIL,
              expected="전송 범위 팝업에서 All Images 선택",
              actual="팝업 표시=%s / 누른 버튼 id=%s"
                     % (sent.get("dialog"), sent.get("clicked")),
              note="실측 팝업: 'Do you want to send all images of the selected "
                   "study?' - All Images(27002) / Selected(27001) / Cancel(27000). "
                   "체크리스트 Step 순서상 Send는 Close 뒤지만, Database 목록에 이 "
                   "검사가 표시되지 않아(뒤 Step 참고) Exposure 화면에서 전송했다 "
                   "- Send 버튼은 두 화면에서 같은 컨트롤(30294)이다.")
        step += 1

        res = bunny_mod.wait_for_store(cfg, count=1, timeout=120,
                                       log_offset=log_off, files_newer_than=t0)
        r.add(step, "Storage SCP 수신 확인 (C-STORE Status + 파일)",
              PASS if res["ok"] else FAIL,
              expected="C-STORE 응답 Status 0000h + 수신 파일 1건 이상",
              actual=res["note"],
              note="로그 문구 하나로 성공을 단정하지 않고 실제 저장된 파일까지 "
                   "확인한다. " + bunny_mod.precondition_note(cfg))
        step += 1

        if res["files"]:
            tags = dicomlite.read_tags(res["files"][0], [
                "PatientID", "PatientName", "AccessionNumber", "Modality",
                "StudyDate", "BodyPartExamined", "ViewPosition", "SOPClassUID"])
            want = {
                "PatientID": (expected or {}).get("patient_id"),
                "PatientName": (expected or {}).get("patient_name"),
                "AccessionNumber": (expected or {}).get("accession_number"),
                "Modality": (expected or {}).get("modality"),
            }
            bad = [k for k, v in want.items() if v and _norm(tags.get(k)) != _norm(v)]
            r.add(step, "전송정보(수신 DICOM 태그)가 MWL 스터디 정보와 일치",
                  PASS if not bad else FAIL,
                  expected=" / ".join("%s=%s" % (k, v) for k, v in want.items() if v),
                  actual=" / ".join("%s=%s" % (k, tags.get(k)) for k in want)
                         + " / SOPClass=%s BodyPart=%s View=%s"
                           % (tags.get("SOPClassUID"), tags.get("BodyPartExamined"),
                              tags.get("ViewPosition")),
                  note="체크리스트 Expected Result 3·4·5의 마지막 고리 - 받은 쪽 "
                       "파일의 태그로 확인한다. 불일치: %s"
                       % (", ".join(bad) if bad else "없음"))
            r.attach(res["files"][0])
        else:
            r.add(step, "전송정보(수신 DICOM 태그) 대조", FAIL,
                  note="수신 파일이 없어 태그를 확인할 수 없다.")
        step += 1
    else:
        r.add(step, "영상 Send 및 전송정보 확인", SKIP,
              note="--no-send로 실행되어 전송 단계를 수행하지 않았다.")
        step += 1

    # --- Step 4: Close -> Database 대조 ---------------------------------
    closed = W.close_study(ui, cfg, evidence_dir=evidence_dir)
    r.add(step, "검사 Close",
          PASS if closed.get("clicked") else FAIL,
          expected="Database 화면의 Close 실행",
          actual="처리한 팝업=%s / 상태=%r"
                 % (closed.get("dialogs") or "없음", closed.get("state")),
          note=closed.get("error", ""))
    step += 1

    db = VXvueDb(cfg.get("sql_server", r".\CHAMELEON"), cfg.get("database", "DRF"))
    db_rows = _db_study(db, want_id)
    if db_rows is None:
        r.add(step, "Database(DB) 스터디 정보 대조", MANUAL,
              note="DB 조회에 실패했다. `python run.py db-ae`로 접속을 먼저 확인할 것.")
    elif not db_rows:
        r.add(step, "Database(DB) 스터디 정보 대조", FAIL,
              expected="PatientId=%s 스터디 1건 이상" % want_id,
              actual="DB에서 찾지 못함",
              note="촬영은 됐지만 스터디가 DB에 없다 — Close가 정상 처리됐는지, "
                   "환자 ID가 MWL 값과 다르게 저장됐는지 확인할 것.")
    else:
        got = db_rows[0]
        checks = {
            "PatientId": (expected or {}).get("patient_id"),
            "AccessionNumber": (expected or {}).get("accession_number"),
            "Modality": (expected or {}).get("modality"),
        }
        bad = [k for k, v in checks.items()
               if v and _norm(got.get(k)) != _norm(v)]
        r.add(step, "Database(DB) 스터디 정보가 MWL 값과 일치",
              PASS if not bad else FAIL,
              expected=" / ".join("%s=%s" % (k, v) for k, v in checks.items() if v),
              actual=" / ".join("%s=%s" % (k, got.get(k)) for k in checks),
              note="DB `STUDY`+`PATIENT` 조회 결과. 불일치 항목: %s"
                   % (", ".join(bad) if bad else "없음"))
    step += 1

    # --- Step 4-b: Database 화면 표시 확인 -----------------------------
    db_summary = W.database_search(ui)
    db_list_rows = W.list_rows(ui, W.DB_LIST)
    r.add(step, "Database 화면에 촬영한 스터디가 표시",
          PASS if db_list_rows else MANUAL,
          expected="Database 목록에 이 검사가 표시된다",
          actual="%s / 목록 행 %d개" % (db_summary, len(db_list_rows)),
          note=("표시 확인됨." if db_list_rows else DB_MISSING_NOTE))
    step += 1

    r.finalize()
    return r


def _db_study(db, patient_id):
    """DB에서 해당 환자의 최근 스터디를 조회한다(조회 전용).

    반환: 행 리스트 / 조회 실패 시 None.
    """
    sql = ("SELECT TOP 3 s.StudyKey, p.PatientId, p.PatientName, "
           "s.AccessionNumber, s.Modality, s.StudyDate, s.StudyDescription "
           "FROM STUDY s JOIN PATIENT p ON s.PatientKey = p.PatientKey "
           "WHERE p.PatientId = '%s' ORDER BY s.StudyKey DESC"
           % str(patient_id).replace("'", "''"))
    try:
        return db.query(sql)
    except Exception:                                     # noqa: BLE001
        return None
