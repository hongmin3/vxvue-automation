# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_11 — AI 분석(CAD).

실행: `python run.py tc11`

## 체크리스트 원문 (R-25-774, Checklist 시트)

Precondition: *인체용 뷰어* / 샘플 경로 `\\10.1.1.100\...\AI_VUNO_VXCAD\샘플`

Step Description
```
1. 뷰어 신규 설치
2. VXvue Option-AI 라이선스 추가, VXSetup에서 AI 사용 설정
3. XIPL에 VX CAD 라이선스 추가
4. 뷰어 실행
5. 영상 촬영 후 AI Tool 버튼 클릭
6. Request an analysis 선택
```

Expected Result: *5. 신규 설치 후 AI Tool 최초 실행 시 Serialization 진행
(GPU) 'Have to Data load for using. It takes a few minutes' 팝업 → Yes
클릭 시 Serialization 진행 → 완료 후 AI Medical findings tool 창 표시.
6. AI 분석 실시, 결과가 영상 위에 표시됨.*

Test Data: *동물용 뷰어는 기능 미제공 / GPU가 있는 경우에만 Serialization
진행 / Serialization 16분 정도 소요*

## 이 자동화가 검증하는 것 (2026-08-24 갱신 — 더는 SKIP하지 않는다)

**과거(2026-08-18~21) 설계는 GPU가 없어 "Request an analysis"를 누르지
않고 화면 구조만 확인·SKIP했다.** 사용자 지시(2026-08-24)로 지금은 실제로
누르고, 실제 소견이 있는 검증 샘플(아래 절)로 분석까지 끝까지 확인한다.
GPU/CPU 여부로 PASS를 가르지 않는다(사양서2 p.149-150 VP-616 — CPU 모드
(VUNO CXR(CPU))는 정식 지원 옵션).

- AI Tool 버튼 존재·클릭 → "AI Medical findings tool" 창 표시
- "Request an analysis" 클릭 → 화면 안정(에러 없이 완료)까지 확인
- 결과가 실제로 주입한 소견과 일치하는지 **Detected list를 통째로 캡처해
  OCR로 자동 대조**(2026-08-24 — 아래 "검출 소견명 자동 대조" 절)
- Detected list **각 행의 'Use' 체크박스**를 하나씩 토글해 그 항목의
  Annotation이 실제로 사라지고/되돌아오는지 확인(행마다 개별, 여러 행을
  동시에 해제하는 조합은 다루지 않음 — 아래 절)
- 옵션 체크박스 3종(Insert findings name / Insert probability text /
  Copy original image)의 **존재뿐 아니라 체크/해제가 실제로 영상 표시에
  반영되는지**까지 확인(아래 "옵션 체크/해제 검증" 절) — Copy original
  image는 체크·**미체크** 두 경로 모두 확인한다

## AI Tool 버튼 위치 (실측 2026-08-21)

`core/workflow.py`의 툴 팝업 판독(`read_tool_palette`)은 `section="tools"`
전용으로 검색 영역이 고정돼 있었다(`_PALETTE_SEARCH`) — `section=
"annotation"`(AI Tool이 있는 곳)의 팝업은 화면 위치가 달라 그 영역
밖에서 잘렸다. `read_tool_palette()`에 `search_area` 인자를 추가해
`_palette_area(_section_button(ui, "annotation"))`으로 그 버튼 기준
영역을 계산하도록 고쳤다(이 파일과 `core/workflow.py` 양쪽에서 재사용).

OCR로 "AI Tool" 라벨 자체를 안정적으로 못 읽는 문제도 실측했다(8px 라벨 +
아이콘 조합이라 "Extra Tool" 등으로 오인식). 그래서 좌우로 **표준 API로
안정적으로 읽히는 두 라벨(Ellipse/Circle/Delete)의 실제 좌표로 격자
칸 너비를 구해 AI Tool(3번째 칸) 위치를 보간**한다 — 이 팝업이 5칸
고정 그리드라는 것은 이미 화면 캡처로 실측 확인했으므로(2026-08-21),
"구조는 속성으로 확정한 뒤 그 안에서 위치를 계산"하는 CLAUDE.md 3절
2순위 규칙에 맞는다(고정 좌표를 저장해두지 않고, 매번 다시 읽은
Ellipse/Circle/Delete 좌표로 다시 계산한다).

## VXCAD-CXR 검증 샘플 영상으로 실제 분석까지 실행 (사용자 지시, 2026-08-24)

기존에는 GPU가 없어 "Request an analysis"를 누르지 않고 SKIP했다. 사용자
지시로 이제 **실제로 누른다** — 대신 결과 판정은 관대하게 잡는다: CPU
모드로 완료되면(에러 팝업 없이 화면이 안정되면) **PASS**로 보고 비고에
"CPU 모드로 동작함"만 남긴다. GPU/CPU 여부로 PASS를 가르지 않는다. 분석
대상도 일반 데모 패턴이 아니라 **실제 소견이 있는 검증 샘플**로 바꿨다 —
`core/ai_samples.py` 참고(Service Manual 5.2.5절의 `Default.img` 교체
메커니즘으로, 사내 공유폴더에서 캐시해 온 3종 소견 중 실행마다 무작위로
하나를 골라 등록하고 실행이 끝나면 반드시 원복한다).

**정정(2026-08-24)**: 처음엔 "클릭 전 캡처에 이미 분석 결과가 있었다 —
CPU 모드는 창이 열리는 시점에 분석이 끝나 있는 것 같다"고 적었는데, 이는
착각이었다. `_run_analysis()`의 안정화 루프가 매번 다른 파일명이 아니라
`before_shot`/`after_shot` 두 변수를 **서로 바꿔치기**하며 재사용하는데,
그 스왑 때문에 사후에 "before" 파일을 열어 봤을 때 이미 최신(분석 완료 후)
내용으로 덮여 있었던 것뿐이다. 실제로는(`work/probe_detected_list6.py`로
격리 재현) **"Request an analysis" 클릭이 분석을 실제로 트리거하고,
CPU 모드에서 약 2.5~4.7초 안에 완료된다** — 창이 열리자마자 자동으로
끝나 있는 게 아니다. 판정 로직(화면 안정 여부만 비교) 자체는 파일 이름과
무관하게 항상 옳았으므로 코드는 고치지 않았다 — 이 설명만 정정한다.

## 옵션 체크/해제 검증 (사양서2 VP-616, 사용자 지시 2026-08-24)

기존에는 옵션 체크박스 3종의 **존재만** 확인했다. 사양서2(260731)
p.150~152 VP-616 원문(영문) 근거로 실제 체크/해제 효과까지 확인한다.

| 옵션 | ID | 사양 |
|---|---|---|
| Insert findings name | 31509 | 체크 시 소견 이름이 영상에 text로 표시(기본 체크) |
| Insert probability text | 31510 | 체크 시 소견의 Probability(%)가 영상에 text로 표시(기본 체크) |
| Copy original image | 31512 | OK로 닫으면 진단 결과 Annotation이 추가된 새 영상이 저장됨(원본 복사 후 Annotation 추가). **예외**: Insert 옵션을 전부 해제했거나 소견이 없으면 저장하지 않음(기본 체크) |

Detected list 각 행에도 별도의 **Use** 체크박스가 있다(해제 시 그 항목의
Annotation/이름/확률 전체가 숨겨짐, 기본 체크). **사용자 지시(2026-08-24):
Use 체크박스의 조합(여러 행을 동시에 해제한 상태들)은 검증하지 않는다** —
검출 항목 수(N)에 따라 2^N으로 늘어나는 조합을 전부 확인하는 건 비용
대비 가치가 낮다. 그 대신 **각 행을 하나씩(한 번에 한 행만) 토글해
메커니즘 자체가 개별적으로 정상 동작하는지는 전부 확인한다**(사용자
후속 지시, 2026-08-24: "Use 조합은 설계 밖으로 넘겨도 각 체크박스를
체크·해제 시 정상적으로 되는지까지는 확인하고 싶어") — 이건 선형(N)
비용이라 조합(2^N)과는 다르다. `_verify_use_checkbox()`가 검출된 행
전체를 순서대로 토글·복원한다(라이브 확인: Nodule Mass 2건 검출 시
첫 행만 해제하면 그 원만 사라지고 둘째 원은 남음 → 복원하면 둘 다
돌아옴 → 둘째 행도 같은 방식으로 확인).

검증 방법: 영상 표시 영역(`UIInstanceMedicalFindings`, ctrl_id 880902,
실측 2026-08-24)만 캡처해 체크 해제 전/후 SSIM을 비교한다(달라야 함),
다시 체크하면 원래 캡처와 다시 비슷해져야 한다(복원 확인). **Copy original
image**는 두 경로 모두 확인한다(사용자 지시, 2026-08-24) — ① 기본값
(체크) 상태로 OK 버튼(30688)을 눌러 닫으면 DB `INSTANCE`가 +1 되는지,
② 그다음 **AI Tool을 다시 열어**(재획득 없이 같은 영상 재사용) 미체크로
바꾸고 OK로 닫으면 INSTANCE가 **늘지 않는지**(예외 경로, VP-616).

**실측 발견(2026-08-24, 사용자가 라이브로 관찰해 지적) — 옵션 체크박스가
사양서 기본값과 다르게, 그리고 실행 간에도 유지된다.** 처음 두 번의 라이브
실행에서 'Insert findings name'이 매번 **미체크**로 시작했고(사양서2
VP-616 원문은 기본값을 "Checked"라고 적어 놓았다), 두 번째 실행에서는
'Copy original image'도 미체크로 시작했다 — 정확히 **직전 실행이
'Copy original image' 미체크 경로 검증(위 ②)을 끝내며 그 상태로 닫은 것과
일치**한다. 즉 이 옵션들은 분석마다 사양서 기본값으로 초기화되는 게
아니라 **마지막으로 설정한 값을 기억하는 것으로 보인다**(정확한 저장
위치·범위는 문서로 확인되지 않음 — `사양 확인 필요`). 그래서 코드는
이제 각 체크박스를 만지기 전에 **실제 상태를 읽는다**(`core.setting.
checkbox_checked()` 재사용, Setting 화면과 같은 금색 체크 표시
`(223,182,56)`를 이 창도 그대로 쓴다는 것을 실측으로 확인) — "기본
체크"를 가정하고 무조건 (해제→재체크) 순서로 클릭하던 이전 코드는
방향을 알 수 없어 틀릴 수 있었다(사용자 지적: "첫번째 옵션은 계속
체크 안 하고 테스트하는 것 같은데 아니야?" — 정확했다).

## 검출 소견명 자동 대조 (사용자 지시, 2026-08-24)

Detected list의 헤더는 표준 `SysHeader32`라 `core/listgrid.ListGrid`로
열 이름·셀 값을 읽을 수 있다(다른 화면의 목록과 같은 구조). 검출된 각 행의
소견명을 이 절차가 데모 영상으로 등록한 `sample["finding"]`과 대소문자·
공백을 무시하고 대조해, **적어도 한 행이 일치하면 PASS**로 본다(같은
소견이 여러 위치에서 검출될 수 있음 — 실측: Pneumothorax 샘플에서
Pneumothorax 54%/98% 2행 검출).
"""

import os
import time

from core import ai_samples
from core import dialogs as dialogs_mod
from core import license as license_mod
from core import screen as screen_mod
from core import workflow as W
from core.result import FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_11"
TC_TITLE = "AI 분석(CAD) — AI Tool 버튼 -> AI Medical findings tool 창 확인"

ANNOTATION_SECTION = "annotation"
AI_TOOL_DIALOG_TITLE = "AI Medical findings tool"
REQUEST_ANALYSIS_BUTTON_ID = 30736
# VP-616(사양서2 p.150-152) 옵션 3종 — 실측(2026-08-21)으로 라벨과 ID까지 확인.
AI_OPTION_CHECKBOXES = {
    31509: "Insert findings name",
    31510: "Insert probability text",
    31512: "Copy original image",
}
AI_CLOSE_ICON_ID = -4
# 실측(2026-08-24, work/probe_ai_dialog.py): 영상+Annotation이 그려지는 영역 —
# 옵션 체크/해제 반영을 이 영역만 캡처해서 비교한다(체크박스 패널의 시각적
# 변화까지 섞이지 않도록).
IMAGE_AREA_CTRL_ID = 880902
# 실측(2026-08-24): 왼쪽이 OK(30688) — 체크된 항목을 영상에 반영하고 닫는다.
# 오른쪽이 Cancel(30642) — 그린 Outline을 지우고 닫는다(사양서2 VP-616).
OK_BUTTON_ID = 30688
CANCEL_BUTTON_ID = 30642
# 실측(2026-08-24, work/probe_ai_dialog.py): Detected list. 헤더가
# SysHeader32라 core/listgrid.ListGrid로 열 이름·셀 값을 읽을 수 있다.
DETECTED_LIST_CTRL_ID = 31100


def _find_ai_tool_point(ui, cfg, evidence_dir, attempts=2):
    """annotation 팝업에서 Ellipse/Circle/Delete 좌표로 AI Tool(3번째 칸) 위치를 보간한다.

    OCR 판독이라 기준 라벨(Ellipse/Circle/Delete)을 간헐적으로 못 읽는다
    (실측: 2026-08-26 전체 회귀에서 같은 코드로 1차 PASS -> 2차 MANUAL,
    `Delete` 라벨을 한 번 못 읽어 이 Step부터 전체가 멈췄다). 팝업이 열려
    있는 동안만 캡처할 수 있고 약 2.1초 뒤 스스로 닫히므로(실측: 0.32s 열림
    -> 2.42s 닫힘, `read_tool_palette` docstring과 이 파일의 Step 6 재시도
    루프가 같은 근거를 쓴다), 실패하면 그 수명만큼 기다린 뒤 팝업을 다시 열어
    재시도한다.
    """
    btn = W._section_button(ui, ANNOTATION_SECTION)
    if btn is None:
        return None, None, "annotation 섹션 ≡ 버튼을 찾지 못함"
    area = W._palette_area(btn)

    last_note = "annotation 팝업 영역을 찾지 못함"
    for attempt in range(1, attempts + 1):
        if attempt > 1:
            time.sleep(2.5)  # 팝업이 스스로 닫히길 기다린 뒤 재시도(Step 6과 동일 근거)
        palette = W.read_tool_palette(ui, cfg, section=ANNOTATION_SECTION,
                                      evidence_dir=evidence_dir, refresh=True,
                                      search_area=area)
        suffix = " (%d/%d번째 시도에서 성공)" % (attempt, attempts) if attempt > 1 else ""
        if "AI Tool" in palette:
            return btn, palette["AI Tool"], "OCR로 직접 읽음: %s%s" % (sorted(palette), suffix)
        ellipse, circle, delete = palette.get("Ellipse"), palette.get("Circle"), palette.get("Delete")
        if ellipse and circle and delete:
            gap = (delete[0] - circle[0]) / 3.0
            point = (circle[0] + gap, (circle[1] + delete[1]) / 2.0)
            return btn, point, ("직접 매칭 실패(읽힌 라벨: %s) — Ellipse=%s/Circle=%s/Delete=%s 기준 "
                                "3번째 칸으로 보간: %s%s"
                                % (sorted(palette), ellipse, circle, delete, point, suffix))
        last_note = "보간에 필요한 기준 라벨(Ellipse/Circle/Delete)을 못 읽음(읽힌 것: %s)" % sorted(palette)
    return None, None, "%s — %d회 재시도해도 실패" % (last_note, attempts)


def _other_dialog(ui, exclude_title):
    """`exclude_title`이 아닌 다른 #32770 팝업이 떠 있으면 그것을 돌려준다.

    AI Medical findings tool 창도 #32770이라 `ui.dialog()`는 그 창과 그
    위에 새로 뜬 팝업(에러 등)을 구분하지 못한다 — 제목으로 걸러야 한다.
    """
    for c in ui.windows():
        if c.cls != "#32770":
            continue
        l, t, r, b = c.rect
        if (r - l) * (b - t) >= ui.MAIN_WINDOW_MIN_AREA:
            continue
        if c.text == exclude_title:
            continue
        return c
    return None


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc11")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    # --- Step 1: VXvue 본체 CAD 라이선스 (Precondition) ------------------
    data_dir = cfg.get("data_dir") or ""
    files = license_mod.license_files(data_dir) if data_dir else []
    cad_present = any(True for f in files)  # 종류 판별은 VXvue_License가 이미 함
    r.add(step, "VXvue Option(Computer Aided Detection) 라이선스 (Precondition)",
          PASS if files else MANUAL,
          expected="사양서5 p.63~64 VP-770 — AI Engine 사용 위해 필요",
          actual="라이선스 파일 %d개 확인" % len(files) if files else "확인 불가(data_dir 미설정)",
          note="종류별 상세 대조(Demo/CAD/LiveView)는 VXvue_License 항목이 담당한다. "
               "이 Step은 이 TC 단독 실행 시에도 선행 조건이 충족됐는지 참고로만 본다.")
    step += 1

    # --- Step 2: VXCAD-CXR 검증 샘플 영상을 데모 영상으로 등록 ------------
    # Service Manual Rev.1.0.11 p.170-171(D-17-518) 5.2.5절 근거 —
    # `<data_dir>\DemoImage\Default.img`를 바꾸면 F2 가상 촬영이 그 내용을
    # 그대로 보여준다. 끝나면(성공/실패 무관) 반드시 원복해야 하므로 이
    # 지점부터 함수 끝까지를 통째로 try/finally로 감싼다.
    sample = ai_samples.pick_random() if do_acquire else None
    backup_path = None
    if do_acquire and data_dir and sample is not None:
        try:
            backup_path = ai_samples.stage_default_image(data_dir, sample["path"])
            r.add(step, "VXCAD-CXR 검증 샘플 영상을 데모 영상으로 등록",
                  PASS,
                  expected="Service Manual p.170-171 5.2.5절 — Default.img 교체 시 F2 촬영에 반영",
                  actual="선택된 샘플: %s (%s)" % (sample["finding"], os.path.basename(sample["path"])),
                  note="실행마다 Nodule Mass/Pleural Effusion/Pneumothorax 중 무작위로 하나를 "
                       "고른다. TC11 실행 구간에서만 <data_dir>\\DemoImage\\Default.img를 "
                       "바꾸고 끝나면 원복한다(다른 TC의 Chest/PA 데모 촬영과 충돌하지 않도록).")
        except ai_samples.AiSampleError as exc:
            r.add(step, "VXCAD-CXR 검증 샘플 영상을 데모 영상으로 등록", MANUAL, actual=str(exc))
    elif do_acquire:
        r.add(step, "VXCAD-CXR 검증 샘플 영상을 데모 영상으로 등록", MANUAL,
              actual="로컬 샘플 캐시(auto/TestData/tc11_ai_samples)가 없어 기존 기본 데모 "
                     "영상을 그대로 쓴다 — 실제 소견 검증 없이 UI 흐름만 확인한다.")
    step += 1

    final_step = step
    try:
        final_step = _run_body(r, ui, cfg, evidence_dir, do_acquire, map_procedure,
                               projection, exam_step, sample, step)
    finally:
        if backup_path:
            try:
                ai_samples.restore_default_image(data_dir, backup_path)
                r.add(final_step, "데모 영상 원복 (Default.img)", PASS, actual="원복 완료")
            except Exception as exc:                      # noqa: BLE001
                r.add(final_step, "데모 영상 원복 (Default.img)", FAIL,
                      actual="원복 실패: %s — 사람이 %s\\DemoImage\\Default.img*를 확인할 것"
                             % (exc, data_dir))

    return r.finalize()


def _run_body(r, ui, cfg, evidence_dir, do_acquire, map_procedure,
              projection, exam_step, sample, step):
    # --- Step 3: 촬영 ------------------------------------------------------
    if do_acquire:
        try:
            flow = W.open_and_acquire(
                ui, cfg,
                patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"),
                projection=projection, step=exam_step,
                evidence_dir=evidence_dir, map_procedure_name=map_procedure)
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "AI 분석용 영상 준비 (MWL 오픈 + Demo 촬영)", FAIL, actual=str(exc))
            return step
        acq = flow["acquire"] or {}
        r.add(step, "AI 분석용 영상 준비 (MWL 오픈 + Demo 촬영)",
              PASS if acq.get("acquired") else FAIL,
              expected="영상 1장 이상 획득",
              actual="INSTANCE %s → %s / %.1f초"
                     % (acq.get("instances_before"), acq.get("instances_after"),
                        acq.get("seconds", 0)),
              note=("촬영된 영상 = %s 샘플(데모 영상 교체됨)" % sample["finding"]
                    if sample is not None else ""))
        if not acq.get("acquired"):
            return step
    else:
        r.add(step, "AI 분석용 영상 준비", SKIP,
              note="--no-acquire로 실행되어 이미 열려 있는 영상을 사용한다.")
    step += 1

    in_viewer = W.viewer_mode(ui, cfg)
    r.assert_true(step, "Viewer 모드 전환(Tools 패널 노출)", in_viewer,
                  expected="Tools 섹션 ≡ 노출", actual="전환 성공" if in_viewer else "전환 실패")
    if not in_viewer:
        return step
    step += 1

    # --- Step: AI Tool 버튼 클릭 -> AI Medical findings tool 창 -----------
    btn, point, note = _find_ai_tool_point(ui, cfg, evidence_dir)
    if point is None:
        r.add(step, "annotation 팝업에서 AI Tool 위치 확인", MANUAL,
              expected="AI Tool 버튼 좌표 확보", actual=note)
        return step
    r.add(step, "annotation 팝업에서 AI Tool 위치 확인", PASS,
          expected="AI Tool 버튼 좌표 확보(사양서2 p.150 VP-616)", actual=note)
    step += 1

    from core.ui import children

    # 실측(2026-08-21): 이 창을 코드가 못 찾고 끝내면(예외·타임아웃) 창이
    # 열린 채로 남아 **다음 실행의 화면 전환을 막는다**(실측: Registration
    # 탭 전환 15초 타임아웃으로 재현됨) — 그래서 여기서부터는 무슨 일이
    # 있어도 `finally`에서 닫기를 시도한다. `core/dialogs.py`의 범용
    # 팝업 정리(QUESTION으로 분류돼 아무 버튼이나 눌림)에 맡기면 이 창은
    # 실제로 닫히지 않는다(실측 확인) — 이 파일이 직접 책임진다.
    dlg = None
    already_closed = False
    try:
        # 실측(2026-08-24): 같은 좌표·같은 settle로 클릭해도 간헐적으로 창이
        # 안 뜨는 사례가 있었다 — 원인은 `read_tool_palette()`(위 Step에서
        # `_find_ai_tool_point()`가 호출) 자체 docstring에 이미 적혀 있었다:
        # "팝업은 약 2.1초 뒤 스스로 닫힌다"(0.32s 열림 → 2.42s 닫힘). 그
        # 팝업이 아직 열려 있는 상태에서 여기서 `ui.click(btn, ...)`을 또
        # 누르면 **토글로 오히려 팝업이 닫혀버리고**, 뒤이은 `click(point)`은
        # 빈 화면(영상 표시 영역)을 누르는 셀이 된다 — OCR/보간 처리 속도가
        # 매번 달라 팝업이 아직 열려 있을 때도, 이미 닫혔을 때도 있어
        # 간헐적으로 재현됐다. **팝업이 확실히 닫힌 뒤 다시 여는 것**으로
        # 이 경쟁 상태를 없앤다(추측이 아니라 팝업 자체의 실측 수명 2.42초
        # 근거). 그래도 안 뜨면 최대 3회까지 재시도한다.
        MAX_ATTEMPTS = 3
        attempts = 0
        for attempts in range(1, MAX_ATTEMPTS + 1):
            if attempts > 1:
                _, retry_point, _ = _find_ai_tool_point(ui, cfg, evidence_dir)
                if retry_point is None:
                    break
                point = retry_point
            time.sleep(2.5)  # 팝업이 스스로 닫히는 걸 확실히 기다린 뒤 다시 연다
            ui.click(btn, settle=0.05)
            time.sleep(W.PALETTE_OPEN_DELAY)
            ui.click(point, settle=2.5)

            # `ui.dialog_text()`는 창 제목이 아니라 **내부 Static 라벨**(예:
            # "Dog Normal Variation ...", "VHS: ")을 이어붙인 값을 돌려준다 —
            # 창 제목과 비교하면 항상 어긋난다(실측). `ui.dialog(title=...)`가
            # 창의 `text`(=제목, `_text_of(hwnd)`)로 직접 거른다.
            end = time.time() + 8
            while time.time() < end:
                d = ui.dialog(title=AI_TOOL_DIALOG_TITLE)
                if d is not None:
                    dlg = d
                    break
                time.sleep(0.4)
            if dlg is not None:
                break
        r.assert_true(step, "AI Tool 클릭 -> 'AI Medical findings tool' 창 표시", dlg is not None,
                      expected="Operation Manual 근거 — AI Tool 클릭 시 이 창이 뜬다",
                      actual=("표시됨(%d번째 시도)" % attempts) if dlg is not None
                             else "%d회 재시도(각 8초 대기)에도 나타나지 않음" % MAX_ATTEMPTS,
                      note=("" if attempts == 1 else
                            "1회차에 뜨지 않아 재시도했다 — 같은 좌표/설정으로 클릭이 "
                            "간헐적으로 반응하지 않는 사례를 진단 스크립트로 재현한 바 "
                            "있다(2026-08-24). 여러 번 재현되면 원인을 더 조사할 것."))
        step += 1

        if dlg is not None:
            kids = children(dlg.hwnd, 5)
            req_btn = next((c for c in kids if c.ctrl_id == REQUEST_ANALYSIS_BUTTON_ID and c.visible), None)
            r.assert_true(step, "'Request an analysis' 버튼 존재", req_btn is not None,
                          expected="체크리스트 Step6 근거", actual="존재" if req_btn is not None else "찾지 못함")
            step += 1

            found_opts = [label for cid, label in AI_OPTION_CHECKBOXES.items()
                         if any(c.ctrl_id == cid and c.visible for c in kids)]
            r.assert_true(step, "AI 결과 표시 옵션 체크박스 3종 확인",
                          len(found_opts) == len(AI_OPTION_CHECKBOXES),
                          expected="사양서2 p.150-152 VP-616: %s" % ", ".join(AI_OPTION_CHECKBOXES.values()),
                          actual="확인됨: %s" % (", ".join(found_opts) or "없음"))
            step += 1

            if req_btn is not None:
                step = _run_analysis(r, ui, dlg, req_btn, step)
                # 분석이 안정된 뒤에만 옵션 반영을 의미 있게 확인할 수 있다.
                if ui.dialog(title=AI_TOOL_DIALOG_TITLE) is not None:
                    step = _verify_finding_match(r, ui, dlg, sample, step)
                    step = _verify_use_checkbox(r, ui, dlg, step)
                    step = _verify_option_checkbox(r, ui, dlg, step, 31509,
                                                   "Insert findings name", "name")
                    step = _verify_option_checkbox(r, ui, dlg, step, 31510,
                                                   "Insert probability text", "prob")
                    step, already_closed = _verify_copy_original_image(r, ui, cfg, dlg, step)
                    if already_closed:
                        step = _verify_copy_unchecked(r, ui, cfg, evidence_dir, step)
            else:
                r.add(step, "'Request an analysis' 실행 및 분석 결과 검증", MANUAL,
                      actual="버튼을 찾지 못해 실행하지 않음")
                step += 1
    finally:
        # 위에서 OK로 이미 닫았으면(`Copy original image` 검증) 다시 닫지 않는다.
        target = None if already_closed else (dlg or ui.dialog(title=AI_TOOL_DIALOG_TITLE))
        if target is not None:
            close_icon = next((c for c in children(target.hwnd, 1)
                               if c.ctrl_id == AI_CLOSE_ICON_ID), None)
            if close_icon is not None:
                ui.click(close_icon, settle=1.0)
        closed = ui.dialog(title=AI_TOOL_DIALOG_TITLE) is None
        r.assert_true(step, "AI Tool 창 닫기", closed,
                      expected="창 닫힘",
                      actual=("OK로 이미 닫힘" if already_closed else
                              ("닫힘 확인" if closed else "닫히지 않음 — 사람 확인 필요")))
        step += 1

    return step


def _run_analysis(r, ui, dlg, req_btn, step):
    """'Request an analysis'를 실제로 눌러 완료(또는 에러)까지 지켜본다.

    사용자 지시(2026-08-24): 이 PC는 GPU가 없어 항상 CPU 모드로 동작한다.
    **GPU/CPU 여부로 PASS를 가르지 않는다** — 에러 팝업 없이 화면이
    안정되면(더 이상 안 바뀌면) PASS로 보고 비고에 CPU 모드로 동작했다는
    사실만 남긴다. 진짜 에러(별도 팝업)가 뜨면 그건 결과로 반영한다.

    완료 판정은 창 안의 픽셀 변화가 멈췄는지로 본다 — 결과 표시 방식이
    실측되지 않은 상태라 owner-draw 여부와 무관하게 항상 통하는 방법이다.
    """
    before_shot = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "Cache", "tc11_analysis_before.png")
    after_shot = before_shot.replace("_before.png", "_after.png")
    os.makedirs(os.path.dirname(before_shot), exist_ok=True)
    screen_mod.capture(before_shot, bbox=dlg.rect, all_screens=True)

    ui.click(req_btn, settle=1.0)

    timeout, poll = 90, 3.0
    end = time.time() + timeout
    stable_hits = 0
    other = None
    while time.time() < end:
        time.sleep(poll)
        other = _other_dialog(ui, AI_TOOL_DIALOG_TITLE)
        if other is not None:
            break
        if ui.dialog(title=AI_TOOL_DIALOG_TITLE) is None:
            break  # 창 자체가 닫혀버림(비정상) — 아래에서 별도로 판정
        screen_mod.capture(after_shot, bbox=dlg.rect, all_screens=True)
        score = screen_mod.ssim(before_shot, after_shot)
        if score >= 0.995:
            stable_hits += 1
            if stable_hits >= 2:
                break
        else:
            stable_hits = 0
            before_shot, after_shot = after_shot, before_shot  # 다음 비교 기준을 최신으로

    elapsed = timeout - max(0, end - time.time())
    dlg_now = ui.dialog(title=AI_TOOL_DIALOG_TITLE)

    if other is not None:
        info = dialogs_mod.read(ui, other)
        kind = dialogs_mod.classify(info)
        verdict = FAIL if kind in (dialogs_mod.ERROR, dialogs_mod.WARNING) else MANUAL
        r.add(step, "'Request an analysis' 실행 및 분석 결과 확인", verdict,
              expected="에러 없이 분석이 완료돼야 한다",
              actual="별도 팝업 감지: [%s] %s / %s" % (kind, info.get("title"), info.get("message")),
              note="CPU 모드(이 PC는 GPU 없음)에서 실행. 이 팝업이 QUESTION이면 어느 버튼이 "
                   "옳은지 사양이 없어 자동으로 누르지 않는다 — 사람 확인 필요.")
    elif dlg_now is None:
        r.add(step, "'Request an analysis' 실행 및 분석 결과 확인", MANUAL,
              actual="분석 도중 'AI Medical findings tool' 창 자체가 사라짐 — 원인 불명",
              note="CPU 모드(이 PC는 GPU 없음)에서 실행.")
    else:
        img = screen_mod.capture(
            os.path.join(os.path.dirname(before_shot), "tc11_analysis_result.png"),
            bbox=dlg_now.rect, all_screens=True)
        r.attach(img)
        r.add(step, "'Request an analysis' 실행 및 분석 결과 확인",
              PASS if stable_hits >= 2 else MANUAL,
              expected="에러 없이 분석이 완료돼야 한다(체크리스트 Step6)",
              actual=("화면 안정 확인(%.0f초)" % elapsed if stable_hits >= 2
                      else "%.0f초 동안 화면이 계속 바뀌어 완료 시점을 확정하지 못함" % elapsed),
              note="CPU 모드로 동작함(이 PC는 GPU가 없음, Intel Iris Xe 내장 그래픽만) — "
                   "사양서2 p.149-150 VP-616: Serialization은 GPU 환경에서 처음 연동할 때만 "
                   "걸리는 절차이고 CPU 모드(VUNO CXR(CPU))는 정식 지원 옵션이다. "
                   "GPU/CPU 여부로 PASS를 가르지 않는다(사용자 지시, 2026-08-24).")
    return step + 1


def _image_area_rect(dlg):
    """영상+Annotation이 그려지는 영역(`UIInstanceMedicalFindings`)의 rect.

    못 찾으면 창 전체 rect로 대체한다(그래도 비교는 가능하다 — 정밀도만
    떨어진다는 사실을 note에 남긴다).
    """
    from core.ui import children
    for c in children(dlg.hwnd, 6):
        if c.ctrl_id == IMAGE_AREA_CTRL_ID:
            return c.rect, True
    return dlg.rect, False


def _cache_path(name):
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, name)


def _verify_option_checkbox(r, ui, dlg, step, ctrl_id, label, cache_prefix):
    """옵션 체크박스의 **실제 기본 상태**를 읽고, 토글 -> 되돌리기가 영상
    표시 영역에 반영되는지 SSIM으로 확인한다.

    사용자 지적(2026-08-24, 라이브 관찰): "AI 분석 창에서 첫번째 옵션은
    계속 체크 안 하고 테스트하는 것 같다" — 정확했다. 실측해 보니 'Insert
    findings name'(31509)은 **기본이 미체크**였다(캡처로 직접 확인,
    `S.checkbox_checked()`가 쓰는 것과 같은 체크 표시 금색 `(223,182,56)`
    이 그 칸에 없음). 사양서2(260731) p.150-152 VP-616 원문은 이 옵션의
    기본값을 "Checked(Selected)"라고 적어 놓아 **실측과 어긋난다.** 이전
    코드는 "기본 체크"를 가정하고 무조건 (해제 -> 재체크) 순서로 클릭했는데,
    실제로 미체크 상태에서 시작하면 이 순서가 (체크 -> 재해제)로 뒤집혀
    **어느 방향인지 기록하지 않은 채** "토글하면 달라진다"만 확인하고
    끝냈다 — 방향을 밝히지 않은 것과 사양과 다른 기본값을 조용히 넘긴 것,
    둘 다 이 사용자 지적으로 고친다.

    이제 클릭 전에 `core.setting.checkbox_checked()`(Setting 화면과 같은
    금색 체크 표시 판별, 이 AI 창도 같은 테마를 쓴다는 것을 실측으로
    확인)로 실제 상태를 읽고, 그 방향을 그대로 기록하며, 사양서 기본값
    (체크)과 다르면 그 사실을 note에 명시한다.
    """
    from core.ui import children
    from core import setting as S

    ctrl = next((c for c in children(dlg.hwnd, 6) if c.ctrl_id == ctrl_id and c.visible), None)
    if ctrl is None:
        r.add(step, "'%s' 체크박스 기본 상태 확인 및 토글 반영 확인" % label, MANUAL,
              expected="사양서2 p.150-152 VP-616",
              actual="체크박스(%d)를 찾지 못함" % ctrl_id)
        return step + 1

    was_checked = S.checkbox_checked(ui, ctrl)

    rect, exact = _image_area_rect(dlg)
    initial_shot = _cache_path("tc11_opt_%s_initial.png" % cache_prefix)
    toggled_shot = _cache_path("tc11_opt_%s_toggled.png" % cache_prefix)
    restored_shot = _cache_path("tc11_opt_%s_restored.png" % cache_prefix)

    screen_mod.capture(initial_shot, bbox=rect, all_screens=True)
    ui.click(ctrl, settle=1.0)
    screen_mod.capture(toggled_shot, bbox=rect, all_screens=True)
    toggle_score = screen_mod.ssim(initial_shot, toggled_shot)

    ui.click(ctrl, settle=1.0)
    screen_mod.capture(restored_shot, bbox=rect, all_screens=True)
    restore_score = screen_mod.ssim(initial_shot, restored_shot)

    # 실측(2026-08-24): 전체 영상 영역 기준으로는 텍스트 한두 글자 변화가
    # SSIM에 크게 반영되지 않는다(측정값 0.9952~0.9993, Probability text는
    # "98%" 처럼 짧아 Findings name보다도 덜 반영됨) — 배경 X-ray가 차지하는
    # 면적이 훨씬 크기 때문이다. 반면 재체크(복원) 시 SSIM은 항상 정확히
    # 1.0000이었다(이 환경은 캡처 노이즈가 없다) — 그래서 "완전히 같지 않으면
    # 변화가 있었다"로 봐도 안전하다. 0.995~0.999는 둘 다 너무 느슨해 실제
    # 변화를 놓친 사례가 있었다(0.999로도 Probability text 0.9993을 못 잡음).
    THRESH = 0.9999
    reflects = toggle_score < THRESH and restore_score >= THRESH
    direction = "체크 -> 해제 -> 재체크" if was_checked else "미체크 -> 체크 -> 재해제"

    default_note = ""
    if not was_checked:
        default_note = ("**실측: 이번 실행에서 기본 상태가 미체크였다 — 사양서2 VP-616 원문의 "
                        "기본값(체크/Selected)과 다르다.** 제품이 이전 조작(다른 세션의 수동 "
                        "테스트 등)의 값을 기억해 남긴 것인지, 이 옵션만 기본값이 실제로 다른 것인지 "
                        "확정하지 못했다 — 사람 확인 필요. ")

    # 실측(2026-08-24, 사용자 지적): 이 창은 캡처 노이즈가 없다는 것을 여러
    # 번 확인했다(재체크 SSIM은 항상 정확히 1.0000) — 그래서 "체크박스를
    # 찾아 클릭까지 했는데 화면이 안 바뀐다"는 측정 불확실성이 아니라
    # 실제로 반영이 안 된 것으로 본다. **찾지 못해 시도조차 못 한 경우만
    # MANUAL**이고, 시도했는데 기대와 다르면 FAIL이다.
    r.add(step, "'%s' 체크박스 기본 상태 확인 및 토글 반영 확인" % label,
          PASS if reflects else FAIL,
          expected="사양서2 p.150-152 VP-616 — 기본값은 체크. 토글하면(%s) 영상 표시가 "
                   "달라지고 원래 상태로 되돌아와야 한다" % direction,
          actual="실측 기본 상태=%s / 토글 SSIM=%.4f(< %.4f여야 함) / 복원 SSIM=%.4f(>= %.4f여야 함)"
                 % ("체크" if was_checked else "미체크", toggle_score, THRESH, restore_score, THRESH),
          note=default_note + ("" if exact else "UIInstanceMedicalFindings(880902)를 못 찾아 "
                                                 "창 전체로 비교했다 — 정밀도가 떨어질 수 있다."))
    r.attach(toggled_shot)
    return step + 1


def _verify_copy_original_image(r, ui, cfg, dlg, step):
    """'Copy original image' 기본값(체크) 상태로 OK를 눌러 닫으면 새 영상이
    저장되는지 DB `INSTANCE` 행 수로 확인한다(사양서2 VP-616).

    미체크 시 저장되지 않는 예외 경로는 분석을 한 번 더 도는 왕복이 필요해
    이번 세션에서는 자동화하지 않았다(NEXT_TASK.md 참고). 이 함수가 OK로
    창을 닫으므로, 반환값 두 번째 항목이 True면 호출부는 다시 닫으려 하지
    않아야 한다.
    """
    from core.ui import children
    from core import setting as S

    kids = children(dlg.hwnd, 6)
    ok_btn = next((c for c in kids if c.ctrl_id == OK_BUTTON_ID and c.visible), None)
    copy_ctrl = next((c for c in kids if c.ctrl_id == 31512 and c.visible), None)
    if ok_btn is None:
        r.add(step, "'Copy original image' 체크(기본값) 상태로 OK 닫기 -> 새 영상 저장 확인",
              MANUAL, expected="사양서2 p.150-152 VP-616", actual="OK 버튼을 찾지 못함")
        return step + 1, False

    # 실측(2026-08-24): 다른 옵션(Insert findings name)의 기본 상태가 사양과
    # 달랐던 사례가 있어, 이 체크박스도 **가정하지 않고 실제로 읽는다** —
    # 미체크 상태면 먼저 체크해서 "체크 상태로 닫는" 시나리오를 보장한다.
    forced_check_note = ""
    if copy_ctrl is not None and not S.checkbox_checked(ui, copy_ctrl):
        ui.click(copy_ctrl, settle=0.5)
        copy_ctrl2 = next((c for c in children(dlg.hwnd, 6) if c.ctrl_id == 31512 and c.visible), None)
        now_checked = copy_ctrl2 is not None and S.checkbox_checked(ui, copy_ctrl2)
        forced_check_note = ("실측: 'Copy original image'가 기본이 미체크였다(사양서 기본값과 "
                             "다름) — 체크로 바꾼 뒤(%s) 이 검증을 진행했다. " %
                             ("전환 확인됨" if now_checked else "전환 확인 실패"))

    patient_id = (cfg.get("test_data") or {}).get("mwl_patient_id")
    before = W.instance_count(cfg, patient_id)
    ui.click(ok_btn, settle=1.5)
    end = time.time() + 15
    after = before
    while time.time() < end:
        time.sleep(1.0)
        after = W.instance_count(cfg, patient_id)
        if after is not None and after > before:
            break
    ok = after == before + 1
    # DB INSTANCE 행 수는 SQL 조회로 직접 읽는 값이라 캡처/OCR 같은 측정
    # 불확실성이 없다 — OK를 실제로 눌렀는데 안 늘었으면 결함으로 본다(FAIL).
    r.add(step, "'Copy original image' 체크(기본값) 상태로 OK 닫기 -> 새 영상 저장 확인",
          PASS if ok else FAIL,
          expected="OK로 닫으면 진단 결과 Annotation이 추가된 영상이 원본 복사 후 "
                   "새로 저장돼야 한다(INSTANCE +1)",
          actual="INSTANCE %s -> %s" % (before, after),
          note=forced_check_note + "'Copy original image' 미체크 시 저장되지 않아야 하는 "
               "예외 경로는 AI Tool을 다시 열어 별도로 확인한다(아래 Step 참고).")
    return step + 1, True


def _verify_finding_match(r, ui, dlg, sample, step):
    """검출된 소견명이 주입한 샘플과 일치하는지 Detected list를 OCR로 읽어
    대조한다(사용자 지시 2026-08-24 — "사람이 캡처로 확인"에서 자동 대조로).

    **실측(2026-08-24)으로 방식을 바꿨다.** 처음엔 `core/listgrid.ListGrid`
    (헤더는 표준 `SysHeader32` API로, 셀은 행 rect로 잘라 OCR)로 시도했는데,
    이 목록의 행(`ListItem`)은 `visible=False`로 보고되고(다른 화면의
    목록과 다른 특성 — Database 등에서는 `visible`이 데이터 유무를
    정확히 반영했지만 이 창은 아니다) `ListGrid.rows()`가 그 값을 필터로
    쓰기 때문에 항상 빈 목록으로 읽혔다. 행 rect를 직접 잘라도 캡처가
    완전히 빈 배경이었다(진단: `work/probe_detected_list.py` 계열,
    HANDOFF.md 참고) — 개별 행의 rect 자체가 실제 화면 위치와 안 맞는
    것으로 보인다. 그래서 **행 단위가 아니라 목록 전체 영역을 통째로
    캡처해 OCR**하는 방식으로 바꿨다 — 헤더까지 포함해도 상관없다
    (찾는 것은 부분 문자열 포함 여부뿐이다). 이 방식은 실제 분석 결과가
    채워진 상태에서 라이브로 검증했다(`work/probe_detected_list6.py`).
    """
    from core.ui import children

    if sample is None:
        r.add(step, "검출된 소견명이 주입한 샘플과 일치하는지 확인", MANUAL,
              actual="이번 실행에 주입한 샘플 정보가 없어(로컬 캐시 없음) 대조할 수 없음")
        return step + 1

    list_ctrl = next((c for c in children(dlg.hwnd, 6)
                      if c.ctrl_id == DETECTED_LIST_CTRL_ID and c.visible), None)
    if list_ctrl is None:
        r.add(step, "검출된 소견명이 주입한 샘플과 일치하는지 확인", MANUAL,
              expected="주입한 샘플=%s" % sample["finding"],
              actual="Detected list(%d)를 찾지 못함" % DETECTED_LIST_CTRL_ID)
        return step + 1

    try:
        import pytesseract
        from PIL import ImageGrab
        exe = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(exe):
            pytesseract.pytesseract.tesseract_cmd = exe
    except ImportError:
        r.add(step, "검출된 소견명이 주입한 샘플과 일치하는지 확인", MANUAL,
              expected="주입한 샘플=%s" % sample["finding"], actual="pytesseract 미설치")
        return step + 1

    img = ImageGrab.grab(bbox=list_ctrl.rect, all_screens=True)
    big = img.resize((img.width * 2, img.height * 2))
    raw_text = pytesseract.image_to_string(big)
    shot_path = _cache_path("tc11_detected_list.png")
    img.save(shot_path)

    def norm(s):
        return "".join(ch for ch in (s or "").lower() if ch.isalnum())

    want = norm(sample["finding"])
    matched = want in norm(raw_text)

    r.add(step, "검출된 소견명이 주입한 샘플과 일치하는지 확인",
          PASS if matched else MANUAL,
          expected="주입한 샘플=%s (사양서2 VP-616 — Detected list에 그 소견명이 표시돼야 한다)"
                   % sample["finding"],
          actual="Detected list OCR 판독: %s" % (" / ".join(raw_text.split(chr(10))).strip()
                                                 or "(빈 값)"),
          note=("" if matched else
                "OCR 오독이거나 실제로 다른 소견이 검출된 것일 수 있다 — 첨부 캡처로 "
                "사람이 재확인할 것."))
    r.attach(shot_path)
    return step + 1


def _verify_use_checkbox(r, ui, dlg, step):
    """Detected list의 **각 행**을 하나씩 토글해 그 소견의 Annotation(윤곽선/
    이름/확률)이 영상에서 사라지고/되돌아오는지 확인한다(사양서2 VP-616).

    사용자 지시(2026-08-24): "Use 조합은 설계 밖으로 넘겨도 각 체크박스를
    체크·해제 시 정상적으로 되는지까지는 확인하고 싶어." — 그래서 **행이
    여러 개면 한 번에 한 행씩만** 토글·복원한다(항상 한 행 빼고 나머지는
    원래 상태). 이는 2^N으로 늘어나는 **조합**(여러 행을 동시에 해제한
    상태들)이 아니다 — 검출 항목 수만큼 **선형으로** 늘어나는 개별 확인이라
    비용이 설계 범위에서 뺀 조합 테스트와는 다르다.

    실측(2026-08-24): 처음엔 분석 전(빈 목록) 상태에서 행 rect를 읽어
    "rect가 실제 화면 위치와 안 맞는다"고 잘못 판단했었다 — 분석이 끝나
    행이 실제로 채워진 뒤에는 rect가 정확했다(`work/probe_use_checkbox.py`
    로 라이브 확인: Nodule Mass 2건 검출 후 첫 행 Use 해제 → 69% 원만
    사라지고 10% 원은 남음 → 재체크 → 둘 다 복원). `visible` 속성도 분석
    전에는 모든 행이 False였다가 분석 후 실제 데이터가 있는 행만 True로
    바뀌는 것으로 확인됨 — Database 등 다른 화면과 같은 규칙이었다.
    """
    from core.ui import children
    from core import setting as S

    TITLE = "Detected list 각 행의 'Use' 체크 토글 시 Annotation 반영 확인"
    EXPECTED = ("사양서2 VP-616 — 각 행의 Use를 해제하면 그 항목의 Annotation이 "
                "사라지고, 다시 체크하면 되돌아와야 한다(행마다 하나씩만 토글 — "
                "여러 행을 동시에 해제하는 조합은 다루지 않는다)")

    list_ctrl = next((c for c in children(dlg.hwnd, 6)
                      if c.ctrl_id == DETECTED_LIST_CTRL_ID and c.visible), None)
    if list_ctrl is None:
        r.add(step, TITLE, MANUAL, expected=EXPECTED,
              actual="Detected list(%d)를 찾지 못함" % DETECTED_LIST_CTRL_ID)
        return step + 1

    rows = sorted([c for c in children(list_ctrl.hwnd, 3)
                  if c.text.strip() == "ListItem" and c.visible],
                 key=lambda c: c.rect[1])
    if not rows:
        r.add(step, TITLE, MANUAL, expected=EXPECTED,
              actual="검출된 행이 없어(분석 결과 없음) 확인할 수 없음")
        return step + 1

    rect, exact = _image_area_rect(dlg)
    THRESH = 0.9999
    results = []
    attachments = []
    for i, row in enumerate(rows, start=1):
        checkbox = next((c for c in children(row.hwnd, 1) if c.text.strip() == "CheckBox"), None)
        if checkbox is None:
            results.append("행%d: 체크박스를 찾지 못함" % i)
            continue

        was_checked = S.checkbox_checked(ui, checkbox)
        initial_shot = _cache_path("tc11_use_row%d_initial.png" % i)
        toggled_shot = _cache_path("tc11_use_row%d_toggled.png" % i)
        restored_shot = _cache_path("tc11_use_row%d_restored.png" % i)

        screen_mod.capture(initial_shot, bbox=rect, all_screens=True)
        ui.click(checkbox, settle=1.0)
        screen_mod.capture(toggled_shot, bbox=rect, all_screens=True)
        toggle_score = screen_mod.ssim(initial_shot, toggled_shot)

        ui.click(checkbox, settle=1.0)  # 다음 행을 보기 전에 반드시 원복 — 항상 한 행만 바뀐 상태를 유지
        screen_mod.capture(restored_shot, bbox=rect, all_screens=True)
        restore_score = screen_mod.ssim(initial_shot, restored_shot)

        reflects = toggle_score < THRESH and restore_score >= THRESH
        results.append("행%d(기본=%s): %s(토글SSIM=%.4f/복원SSIM=%.4f)"
                       % (i, "체크" if was_checked else "미체크",
                          "정상" if reflects else "불일치",
                          toggle_score, restore_score))
        attachments.append(toggled_shot)

    # "찾지 못함"(시도조차 못 함)과 "불일치"(시도했는데 기대와 다름)를 구분한다
    # — 후자는 이 창에 캡처 노이즈가 없다는 것을 실측했으므로 측정 불확실성이
    # 아니라 결함으로 본다(FAIL). 전자만 있으면 MANUAL로 남긴다.
    not_found = any("찾지 못함" in v for v in results)
    mismatch = any("불일치" in v for v in results)
    all_ok = bool(results) and not not_found and not mismatch
    verdict = PASS if all_ok else (FAIL if mismatch else MANUAL)

    r.add(step, TITLE, verdict,
          expected=EXPECTED,
          actual="; ".join(results),
          note=("" if exact else "UIInstanceMedicalFindings(880902)를 못 찾아 창 전체로 "
                                  "비교했다. ")
               + "검출 항목 수(%d)만큼 한 행씩 순서대로 토글·복원했다(조합 아님)." % len(rows))
    for shot in attachments:
        r.attach(shot)
    return step + 1


def _reopen_ai_tool(ui, cfg, evidence_dir):
    """AI Tool을 다시 연다 — 이미 한 번 연 뒤 재확인용이라 다이얼로그 미표시
    재시도(Step 6의 MAX_ATTEMPTS 루프)는 넣지 않는다. 좌표 재획득 자체의 OCR
    재시도는 `_find_ai_tool_point()`가 내부적으로 한다."""
    btn, point, note = _find_ai_tool_point(ui, cfg, evidence_dir)
    if point is None:
        return None, note
    time.sleep(2.5)  # 팝업이 스스로 닫히는 걸 확실히 기다린 뒤 다시 연다(Step 6과 동일 근거)
    ui.click(btn, settle=0.05)
    time.sleep(W.PALETTE_OPEN_DELAY)
    ui.click(point, settle=2.5)
    end = time.time() + 8
    dlg = None
    while time.time() < end:
        dlg = ui.dialog(title=AI_TOOL_DIALOG_TITLE)
        if dlg is not None:
            break
        time.sleep(0.4)
    return dlg, note


def _verify_copy_unchecked(r, ui, cfg, evidence_dir, step):
    """'Copy original image'를 미체크하고 OK로 닫으면 새 영상이 저장되지
    **않아야** 한다(사양서2 VP-616 예외 경로). 사용자 지시(2026-08-24)로
    자동화했다 — 이미 분석까지 끝난 같은 영상을 AI Tool을 다시 열어
    재사용한다(재획득 없음, 왕복 비용을 줄인다).
    """
    from core.ui import children
    from core import setting as S

    dlg2, note = _reopen_ai_tool(ui, cfg, evidence_dir)
    if dlg2 is None:
        r.add(step, "'Copy original image' 미체크 시 저장 안 됨(예외 경로) 확인", MANUAL,
              actual="AI Tool 창을 다시 열지 못함: %s" % note)
        return step + 1

    kids = children(dlg2.hwnd, 6)
    copy_ctrl = next((c for c in kids if c.ctrl_id == 31512 and c.visible), None)
    ok_btn = next((c for c in kids if c.ctrl_id == OK_BUTTON_ID and c.visible), None)
    if copy_ctrl is None or ok_btn is None:
        r.add(step, "'Copy original image' 미체크 시 저장 안 됨(예외 경로) 확인", MANUAL,
              actual="체크박스(31512) 또는 OK 버튼(%d)을 찾지 못함" % OK_BUTTON_ID)
        close_icon = next((c for c in children(dlg2.hwnd, 1)
                           if c.ctrl_id == AI_CLOSE_ICON_ID), None)
        if close_icon is not None:
            ui.click(close_icon, settle=1.0)
        return step + 1

    # 실측(2026-08-24): 다른 체크박스의 기본 상태가 가정과 달랐던 사례가
    # 있어, 여기서도 실제 상태를 읽고서만 클릭한다 — 이미 미체크면 다시
    # 클릭해 체크로 만들어버리는 사고를 막는다.
    was_checked = S.checkbox_checked(ui, copy_ctrl)
    if was_checked:
        ui.click(copy_ctrl, settle=0.5)
    state_note = ("" if was_checked else
                 "실측: 재오픈 시 이미 미체크 상태였다(클릭하지 않고 그대로 진행). ")

    patient_id = (cfg.get("test_data") or {}).get("mwl_patient_id")
    before = W.instance_count(cfg, patient_id)
    ui.click(ok_btn, settle=1.5)

    # 저장되지 않아야 하는 쪽을 확인하는 것이므로 폴링으로 "늘어남"을 기다리지
    # 않는다 — 충분히 기다린 뒤 그대로인지 한 번 확인한다.
    time.sleep(6.0)
    after = W.instance_count(cfg, patient_id)
    ok = after == before
    # DB INSTANCE 조회는 측정 불확실성이 없다 — 미체크인데도 저장됐다면
    # 사양서2 VP-616 예외 조항 위반이므로 결함으로 본다(FAIL).
    r.add(step, "'Copy original image' 미체크 시 저장 안 됨(예외 경로) 확인",
          PASS if ok else FAIL,
          expected="사양서2 p.150-152 VP-616 — 미체크 상태로 OK를 눌러 닫으면 원본 영상이 "
                   "새로 저장되지 않아야 한다(INSTANCE 불변)",
          actual="INSTANCE %s -> %s" % (before, after),
          note=state_note + "1차(체크 상태) 검증에서 이미 분석까지 끝낸 같은 영상을 AI Tool을 "
               "다시 열어 재사용했다(재획득 없음).")

    if ui.dialog(title=AI_TOOL_DIALOG_TITLE) is not None:
        close_icon = next((c for c in children(dlg2.hwnd, 1)
                           if c.ctrl_id == AI_CLOSE_ICON_ID), None)
        if close_icon is not None:
            ui.click(close_icon, settle=1.0)
    return step + 1
