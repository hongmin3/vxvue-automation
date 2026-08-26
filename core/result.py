# -*- coding: utf-8 -*-
"""판정 결과 모델과 리포트 산출물.

Bellalun `auto/core/result.py`를 이식하되 VXvue 요구사항 두 가지를 반영했다.

1. **리포트 상단에 Windows 정보 + 패키지 정보를 반드시 출력한다**(사용자 요청).
   체크리스트 원본 `Checklist` 시트 1~5행(OS / OS Version / OS Build Version /
   Viewer Version / VX.LIVE.SERVER)과 같은 형식을 재현한다. 사람 검토용 HTML과
   구조화 이력용 JSON에 같은 환경 정보를 넣는다.
2. 판정에 `BLOCKED`를 추가했다. 선행 조건 자체가 이 PC에 갖춰지지 않아
   수행이 불가능한 경우(예: TC12의 카메라 하드웨어)를 SKIP과 구분한다.

  PASS    : 자동 판정으로 기대 결과 충족
  FAIL    : 자동 판정으로 기대 결과 불충족
  MANUAL  : 자동화 대상이 아니거나 기대값이 확정되지 않아 사람이 확인해야 함
  SKIP    : 사전 조건 미충족으로 수행하지 않음(환경상 정상적인 건너뜀)
  BLOCKED : 선행 조건이 구성되지 않아 수행 자체가 불가능
"""

import html
import json
import os
import re
import time
from datetime import datetime

from . import report_language

PASS, FAIL, MANUAL, SKIP, BLOCKED = "PASS", "FAIL", "MANUAL", "SKIP", "BLOCKED"
STATUSES = (PASS, FAIL, MANUAL, SKIP, BLOCKED)

REPORT_TITLE = "VXvue Windows Update 호환성 자동화 결과"
DOC_NUMBER = "R-25-774"

# 모든 리포트(HTML/JSON) 상단에 붙는 일반 유의사항(사용자 지시,
# 2026-08-25). 특정 TC의 note가 아니라 이번 회귀 전체에 적용되는 시험
# 범위/한계를 여기 모은다 — 개별 TC를 읽지 않고 리포트 요약만 봐도 알 수
# 있어야 한다.
REPORT_CAVEATS = (
    "이 회귀의 촬영 및 판정 범위는 DX(일반촬영)다.",
)

# 리포트는 자동화 구현자가 아니라 시험 결과를 판단하는 사용자가 먼저 읽는다.
# 코드/DB 용어는 원본 근거를 보존하되 아래 설명을 리포트 앞부분에 함께 보여 준다.
REPORT_GLOSSARY = (
    ("MWL", "촬영 전에 서버에서 받아오는 환자·검사 예약 목록"),
    ("DICOM SCP / C-STORE", "영상을 받는 시험 서버 / 그 서버로 영상을 보내는 전송"),
    ("DB", "VXvue가 환자·검사·영상 상태를 저장하는 데이터베이스"),
    ("ORDER_PATIENT / INSTANCE", "DB의 예약 환자 정보 / 저장된 영상 정보"),
    ("OCR / owner-draw", "화면 글자를 이미지로 읽는 방식 / 표준 API로 글자를 읽을 수 없는 화면"),
    ("baseline", "설치 직후와 같은 깨끗한 DB·폴더 기준 상태"),
    ("MANUAL", "자동 근거만으로 결론을 확정할 수 없어 사람의 판단이 필요한 상태"),
    ("SKIP / BLOCKED", "시험 범위·조건상 의도적으로 제외 / 필수 환경이 없어 수행 불가"),
)

TC_PURPOSES = {
    "Precondition": "본 시험을 시작할 수 있도록 권한, 저장 공간, 화면 환경, 프로그램과 서버 경로가 준비됐는지 확인한다.",
    "Baseline_Reset": "이전 시험 데이터의 영향을 없애기 위해 DB와 데이터 폴더를 설치 직후 기준 상태로 복원한다.",
    "VXvue_License": "VXvue와 사용 옵션의 라이선스가 시험에 필요한 상태로 등록돼 있는지 확인한다.",
    "DICOM_Servers": "검사 예약, 영상 저장, 출력에 사용하는 DICOM 서버가 등록돼 있고 통신되는지 확인한다.",
    "Viewer_Startup": "baseline 복원 후 VXvue가 다시 실행되고 시험 계정으로 로그인되는지 확인한다.",
    "Quick_Mode": "빠른 이상 감지를 위해 전체 회귀 중 축소한 범위와 정식 판정에 사용할 수 없는 이유를 명시한다.",
    "TC_WindowsUpdate_00": "실제 제품 시험 없이 Windows·패키지 환경 헤더와 사용자용 리포트 형식이 정상 생성되는지 확인한다.",
    "TC_WindowsUpdate_01": "Windows Update 설치 전후의 제품 설치 상태를 사람이 확인하는 제외 TC다.",
    "TC_WindowsUpdate_02": "예약 환자를 조회해 촬영하고 전송한 뒤, 화면·수신 영상·DB의 환자 및 검사 정보가 모두 같은지 확인한다.",
    "TC_WindowsUpdate_03": "영상 보간 설정과 선택·확대·이동·회전 도구가 실제 화면에 반영되는지 확인한다.",
    "TC_WindowsUpdate_04": "촬영 영상이 XIPL 영상처리를 거쳐 표시되고 XIPL Studio까지 정상 연결되는지 확인한다.",
    "TC_WindowsUpdate_05": "DX DICOM 영상이 다른 PC의 Storage SCP에 정상 전송되고 수신 객체의 Modality와 SOP Class가 기대값과 일치하는지 확인한다.",
    "TC_WindowsUpdate_06": "Extra Tool 서버 설정과 SBSC 제거 옵션을 적용한 뒤 영상 전송과 서버 처리 로그를 확인한다.",
    "TC_WindowsUpdate_07": "영상을 DICOM Print로 보내 수신 필름과 필름 위 환자·검사 표시 문구까지 올바른지 확인한다.",
    "TC_WindowsUpdate_08": "검사를 외부 폴더로 Export하고 파일·태그·포터블 뷰어를 확인한 뒤 다시 Import할 수 있는지 확인한다.",
    "TC_WindowsUpdate_09": "재부팅이 필요해 자동화할 수 없는 TC로, 자동 회귀에서는 SKIP한다.",
    "TC_WindowsUpdate_10": "사용자 결정으로 자동화 범위에서 제외한 TC다.",
    "TC_WindowsUpdate_11": "검증 영상을 CAD로 분석해 소견, 표시 옵션, 결과 영상 저장 동작이 올바른지 확인한다.",
    "TC_WindowsUpdate_12": "Live View 데모 영상 재생, 오버레이 창, 분석 표시와 스냅샷 전송 동작을 확인한다.",
    "TC_WindowsUpdate_13": "환자정보 파일의 미리보기·수동 Import·폴더 자동 Import·구분자·컬럼 설정이 사양대로 동작하는지 확인한다.",
    "TC_WindowsUpdate_14": "Setting의 모든 하위 화면이 열리고 제목과 본문이 정상 표시되는지 확인한다.",
    "TC_WindowsUpdate_15": "사용자 결정으로 자동화 범위에서 제외한 TC다.",
    "TC_Setting_ExportImport": "설정을 Export한 뒤 일부 값을 바꾸고 Import해 원래 설정으로 정확히 복원되는지 확인한다.",
    # 과거 리포트와 외부 호출자가 사용하던 별칭도 같은 설명을 유지한다.
    "Setting_Export_Import": "설정을 Export한 뒤 일부 값을 바꾸고 Import해 원래 설정으로 정확히 복원되는지 확인한다.",
}

# `automation_scope.json` 의 `reason` 은 구현 이력·실측 기록이 쌓이는 **개발용
# 로그**다(한 TC 가 수천 자에 이른다). 그대로 리포트에 실으면 제출본이 읽히지
# 않으므로, 같은 내용을 시험 결과를 읽는 사람 기준으로 줄인 문장을 여기 둔다.
#
#   scope   이번 자동화가 **자동으로 판정하는 범위**
#   gap     자동으로 판정하지 **않는(못하는)** 것
#   unblock 무엇이 갖춰지면 gap 이 해제되는가
#
# 원칙(`VXvue/CLAUDE.md` 1절): 여기 적는 문장은 `automation_scope.json` 의
# `reason` 에 이미 기록된 사실만 줄여 옮긴다 — 새 사실을 만들지 않는다. 원문은
# 리포트 맨 뒤 '부록 B — 자동화 구현·검증 이력'에 그대로 실어 대조할 수 있게 한다.
# scope 항목이 추가되면 `selfcheck/static_checks.py` 가 여기 누락을 잡는다.
TC_AUTOMATION_SCOPE = {
    "TC_WindowsUpdate_01": {
        "scope": "이번 자동화에서 수행하지 않는다.",
        "gap": "패키지 설치와 뷰어 실행 확인 전체.",
        "unblock": "사용자가 이 TC를 자동화 범위에 포함하기로 결정하면 착수한다.",
    },
    "TC_WindowsUpdate_02": {
        "scope": "MWL 조회 → 목록 표시값 대조 → Study 등록 → 인체도에서 Projection·"
                 "Step 등록 → 촬영 → Send → 수신 DICOM 태그와 MWL 등록값 일치 확인 → "
                 "Close → DB·Database 화면 대조까지 전 단계를 자동 판정한다.",
        "gap": "없다.",
        "unblock": "-",
    },
    "TC_WindowsUpdate_03": {
        "scope": "Interpolation Mode 변경·원복, PA/AP 영상 2장 자동 촬영, 첫째/둘째 "
                 "영상 선택, Select/Zoom/Pan/회전 반영을 화면 비교로 판정하고 각 조작이 "
                 "사용자 확정 임의 기준 30초 이내인지 확인한다.",
        "gap": "없다.",
        "unblock": "-",
    },
    "TC_WindowsUpdate_04": {
        "scope": "Accession 교차검증으로 MWL 대상을 지목 → Chest PA Step 등록 → 촬영"
                 "(DB INSTANCE 증가·오류 팝업 0건) → XIPL 로그의 파라미터 파일 로드 "
                 "확인 → XIPL Studio 기동까지 자동 판정한다.",
        "gap": "XIPL.SERVER About 창의 영상처리 라이선스 4종, Image Process 화면 내부의 "
               "파라미터 변경, XIPL Studio 내부의 영상·파라미터 재처리는 조작 방법을 "
               "실측하지 못해 사람이 확인한다.",
        "unblock": "해당 화면(트레이 아이콘 메뉴, WPF Studio)의 조작 방법을 실측해 "
                   "확보하면 자동 판정할 수 있다.",
    },
    "TC_WindowsUpdate_05": {
        "scope": "DX 촬영 → Send → 다른 PC의 Storage SCP 수신 확인 → 수신 객체의 "
                 "Modality=DX와 영상 SOP Class 일치를 자동 판정한다.",
        "gap": "없다.",
        "unblock": "-",
    },
    "TC_WindowsUpdate_06": {
        "scope": "Extra Tool 서버 등록(AE Title/IP/Port)·Echo·Remove SBSC 설정을 실제 "
                 "DB까지 확인하고, 촬영 → Extra Tool 전송 → 수신 확인 → XIPL Server "
                 "로그의 PureGrid 적용값 확인 → 뷰어 모드에서 재전송까지 자동 판정한다.",
        "gap": "이 회귀가 쓰는 데모 촬영 경로의 Image Process 창에는 SBSC 체크박스가 "
               "없어, 촬영 화면에서 SBSC를 켠 뒤의 on→off 전환은 확인하지 못한다.",
        "unblock": "SBSC 체크박스가 있는 촬영 경로가 준비되면 그 전환까지 확인한다.",
    },
    "TC_WindowsUpdate_07": {
        "scope": "Print SCP 가동 확인 → Print 화면 설정 판독(서버·필름 크기·방향) → "
                 "촬영 → Database > Print의 확인 팝업과 필름 구성 화면의 Print 두 단계 "
                 "처리 → 수신 필름 목록에서 Calling AE의 신규 필름 확인까지 자동 "
                 "판정한다.",
        "gap": "없다.",
        "unblock": "-",
    },
    "TC_WindowsUpdate_08": {
        "scope": "대상 폴더 기준선 → 촬영·Close → Database에서 이번 실행의 Patient ID로 "
                 "대상 지목 → Export(드라이브·폴더·DICOM+IMG 형식 선택) → 산출물 DICOM "
                 "태그 대조 → 역방향 Import(결과 팝업·목록 값 대조·Database 건수 증가) "
                 "→ 포터블 뷰어 실행 파일 확인까지 자동 판정한다.",
        "gap": "없다. Export 대상은 사용자 지시대로 E 드라이브 기준이며, 없으면 D로 "
               "대체하고 그 사실을 판정에 남긴다.",
        "unblock": "-",
    },
    "TC_WindowsUpdate_09": {
        "scope": "이번 자동화에서 수행하지 않는다.",
        "gap": "TC 전체. 재부팅이 필요해 자동화할 수 없으므로 SKIP한다.",
        "unblock": "-",
    },
    "TC_WindowsUpdate_10": {
        "scope": "이번 자동화에서 수행하지 않는다.",
        "gap": "TC 전체. 사용자 지시로 직접 수행할 TC로 분류했다.",
        "unblock": "사용자가 이 TC를 자동화 범위에 포함하기로 결정하면 착수한다.",
    },
    "TC_WindowsUpdate_11": {
        "scope": "AI Tool 창 오픈 → 검증 샘플 등록 → 분석 요청 → 검출 소견명 대조 → "
                 "옵션 체크박스 3종의 체크/해제 반영 확인 → Detected list 행별 Use "
                 "토글 → Copy original image 체크·미체크 두 경로까지 자동 판정한다. "
                 "판정 전 체크박스의 실제 상태를 읽고 그 방향으로 토글한다.",
        "gap": "Detected list의 Use 체크박스를 여러 행 동시에 해제하는 조합은 검증하지 "
               "않는다(사용자 결정 — 검출 건수에 따라 조합이 지수로 늘어 비용 대비 "
               "가치가 낮다). 옵션 상태가 어디에 저장돼 유지되는지는 문서상 확인되지 "
               "않았다.",
        "unblock": "옵션 저장 위치가 사양서로 확인되면 그 부분도 판정에 넣는다.",
    },
    "TC_WindowsUpdate_12": {
        "scope": "Live View 오버레이 창이 영상 표시 영역과 같은 좌표로 뜨는지 → Play 후 "
                 "영상 표시 영역의 밝기 변화로 데모 영상 재생 여부 → 토글 해제 시 창이 "
                 "사라지는지까지 자동 판정한다.",
        "gap": "체크리스트 Step 4(Step Analysis 테두리 색 판정)와 Step 5(Include "
               "Snapshot Image 옵션과 Storage Queue 건수)는 Setting > Integration > "
               "Camera 화면의 컨트롤을 실측하지 못해 수행하지 않는다.",
        "unblock": "해당 화면의 컨트롤을 실측하면 자동 판정할 수 있다.",
    },
    "TC_WindowsUpdate_13": {
        "scope": "환자정보 파일 미리보기·수동 Import·폴더 자동 Import·구분자·컬럼 "
                 "설정을 자동 판정한다. 구분자는 결함 #22985의 재현 경로(Comma→Tab 직접 "
                 "전환)와 티켓에 적힌 워크어라운드 경로를 모두 실행해 결과를 비교한다.",
        "gap": "구분자 회귀 2건은 자동 판정하지 않고 사람 확인으로 남긴다 — 실행 결과가 "
               "사양(Data Delimiter=TAB이면 TAB만 성공)과도, 결함 #22985의 패턴(Tab "
               "실패·Comma 성공)과도 달라 새 결함으로 단정할 수 없다. 결함 발생 버전"
               "(1.0.11.014)과 이번 실행 버전이 달라 버전 간 동작 차이 가능성이 있다.",
        "unblock": "QA·연구소가 버전 간 동작 차이를 확인해 주면 판정 기준을 확정한다.",
    },
    "TC_WindowsUpdate_14": {
        "scope": "Setting 전체 트리(대분류 10개와 현재 표시되는 소분류 전체)를 "
                 "순회하며 화면이 열리고 제목과 본문이 표시되는지 확인한다.",
        "gap": "체크리스트 원문 범위에는 없다. 스크롤 전수 노출·SCP 상세 DB 대조·"
               "옵션 구성 기준 대조는 선택형 `--deep` 정밀 검증으로 분리돼 있다.",
        "unblock": "-",
    },
    "TC_WindowsUpdate_15": {
        "scope": "이번 자동화에서 수행하지 않는다.",
        "gap": "TC 전체. 사용자 지시로 직접 수행할 TC로 분류했다.",
        "unblock": "사용자가 이 TC를 자동화 범위에 포함하기로 결정하면 착수한다.",
    },
}


def automation_scope(tc_id):
    """TC의 자동화 범위 요약. 등록되지 않았으면 빈 dict."""
    return TC_AUTOMATION_SCOPE.get(tc_id) or {}


STATUS_EXPLANATIONS = {
    PASS: "자동으로 확보한 결과가 합격 기준을 충족해 PASS로 판정했다.",
    FAIL: "자동으로 확보한 결과가 합격 기준을 충족하지 못해 FAIL로 판정했다.",
    MANUAL: "자동으로 확보한 근거만으로 합격 또는 실패를 확정할 수 없어 사람의 판단이 필요하다.",
    SKIP: "이번 실행의 범위 또는 조건에 따라 이 확인을 수행하지 않았다.",
    BLOCKED: "필수 선행 환경이 준비되지 않아 이 확인을 수행할 수 없었다.",
}

STATUS_ACTIONS = {
    PASS: "추가 조치가 필요하지 않다.",
    FAIL: "실제값과 비고를 확인하고 원인을 조사한 뒤 해당 TC를 다시 실행해야 한다.",
    MANUAL: "비고의 확인 요청을 담당자 또는 사용자와 검토해 최종 판단해야 한다.",
    SKIP: "비고에서 제외 사유를 확인하고, 검증 범위에 포함해야 한다면 조건을 갖춰 다시 실행해야 한다.",
    BLOCKED: "비고에 적힌 선행 환경을 구성한 뒤 다시 실행해야 한다.",
}


def tc_purpose(tc_id, title=""):
    """TC가 무엇을 검증하는지 사용자 관점의 한 문장으로 반환한다."""
    if tc_id in TC_PURPOSES:
        return TC_PURPOSES[tc_id]
    if tc_id.startswith("TC_WindowsUpdate_"):
        return "%s 시험의 각 확인 단계가 기대 결과를 충족하는지 검증한다." % (title or tc_id)
    return "%s 과정이 기대한 상태로 완료되는지 확인한다." % (title or tc_id)


def _expected_for_reader(value, title):
    text = str(value).strip() if value is not None else ""
    if text.lower() == "true":
        return "이 단계에서 확인하는 조건이 모두 충족되어야 한다."
    if text.lower() == "false":
        return "이 단계에서 확인하는 조건이 발생하지 않아야 한다."
    return text or ("'%s' 단계의 요구 동작이 완료되고 결과 근거가 확인되어야 한다."
                    % title)


def _actual_for_reader(value, status):
    text = str(value).strip() if value is not None else ""
    if text.lower() == "true":
        return "자동으로 확인한 실제값은 True이다."
    if text.lower() == "false":
        return "자동으로 확인한 실제값은 False이다."
    if text:
        prefix = {
            PASS: "자동 확인 결과: ",
            FAIL: "기대 결과와 다른 실제 상태: ",
            MANUAL: "자동으로 확보한 참고 결과: ",
            SKIP: "미수행 상태: ",
            BLOCKED: "수행 불가 상태: ",
        }.get(status, "확인 결과: ")
        return prefix + text
    return {
        PASS: ("세부 실제값은 별도로 수집되지 않았지만, 자동 판정에 사용한 조건은 "
               "기대 결과와 일치했다."),
        FAIL: ("세부 실제값을 확보하지 못했거나 기대 결과와 다른 상태가 확인됐다. "
               "증거 파일과 실행 로그를 확인해야 한다."),
        MANUAL: ("자동으로 실제 결과를 확정할 수 없었다. 기대 결과와 같은지 "
                 "사용자가 직접 확인해야 한다."),
        SKIP: "이번 실행에서는 이 단계를 수행하지 않아 실제 결과가 없다.",
        BLOCKED: "필수 선행 조건이 없어 이 단계를 시작하지 못했으므로 실제 결과가 없다.",
    }.get(status, "실제 결과를 자동으로 확보하지 못했다. 사용자 확인이 필요하다.")


class Check:
    def __init__(self, tc_id, step, title, status, expected="", actual="", note="",
                 blocks_verdict=True):
        self.tc_id = tc_id
        self.step = step
        self.title = title
        self.status = status
        self.expected = expected
        self.actual = actual
        self.note = note
        # 기본은 True — MANUAL/SKIP/BLOCKED 어느 것이든 그 TC를 PASS로 올리지
        # 못하게 막는다("완전 자동화"는 모든 Step이 PASS/FAIL인 상태, TODO_전체
        # 자동화.md 0절). 사용자가 명시적으로 확정한 예외 하나만 False를 쓴다 —
        # TC14의 "--deep 미수행" Step(체크리스트 원문 범위는 가벼운 모드로 이미
        # 충족되고 --deep은 그 위의 정밀 검증이라 미수행이 PASS를 막을 이유가
        # 아니다, 사용자 확정 2026-08-21). 다른 TC에서 새로 False를 쓰려면 같은
        # 수준의 명시적 사용자 확정이 있어야 한다.
        self.blocks_verdict = blocks_verdict

    @property
    def reader_activity(self):
        return report_language.describe_step(self.tc_id, self.title)[0]

    @property
    def activity_is_catalogued(self):
        return report_language.describe_step(self.tc_id, self.title)[1]

    @property
    def reader_expected(self):
        return _expected_for_reader(self.expected, self.title)

    @property
    def reader_actual(self):
        return _actual_for_reader(self.actual, self.status)

    @property
    def reader_reason(self):
        reason = STATUS_EXPLANATIONS.get(self.status, "판정 상태를 확인해야 한다.")
        note = str(self.note).strip() if self.note is not None else ""
        if note:
            reason += " 상세 근거: %s" % note
        if not self.blocks_verdict and self.status in (MANUAL, SKIP, BLOCKED):
            reason += " 이 항목은 사용자 확정 예외이므로 TC 최종 PASS를 막지 않는다."
        return reason

    @property
    def reader_action(self):
        return STATUS_ACTIONS.get(self.status, "담당자가 판정 내용을 검토해야 한다.")

    def as_dict(self):
        return {"step": self.step, "title": self.title, "status": self.status,
                "expected": str(self.expected), "actual": str(self.actual),
                "note": self.note, "blocks_verdict": self.blocks_verdict,
                "reader_activity": self.reader_activity,
                "activity_is_catalogued": self.activity_is_catalogued,
                "reader_expected": self.reader_expected,
                "reader_actual": self.reader_actual,
                "reader_reason": self.reader_reason,
                "reader_action": self.reader_action}


class TCResult:
    def __init__(self, tc_id, title):
        self.tc_id = tc_id
        self.title = title
        self.checks = []
        self.started = datetime.now()
        self.completed = None
        self.timings = []
        self._step_cursor_wall = self.started
        self._step_cursor = time.perf_counter()
        self.evidence = []

    # --- 등록 헬퍼 -----------------------------------------------------
    def add(self, step, title, status, expected="", actual="", note="",
            blocks_verdict=True):
        now_wall = datetime.now()
        now = time.perf_counter()
        self.timings.append({
            "kind": "step", "name": "Step %s: %s" % (step, title),
            "started": self._step_cursor_wall.isoformat(timespec="milliseconds"),
            "ended": now_wall.isoformat(timespec="milliseconds"),
            "duration_seconds": round(now - self._step_cursor, 3),
            "outcome": status, "detail": "check recorded",
        })
        self._step_cursor_wall, self._step_cursor = now_wall, now
        self.checks.append(Check(self.tc_id, step, title, status, expected, actual, note,
                                 blocks_verdict=blocks_verdict))
        return self.checks[-1]

    def record_timing(self, name, started_wall, started_perf, outcome, detail="",
                      kind="wait"):
        """PASS/FAIL 판정을 바꾸지 않고 소요시간만 기록한다."""
        ended = datetime.now()
        self.timings.append({
            "kind": kind, "name": name,
            "started": started_wall.isoformat(timespec="milliseconds"),
            "ended": ended.isoformat(timespec="milliseconds"),
            "duration_seconds": round(time.perf_counter() - started_perf, 3),
            "outcome": outcome, "detail": str(detail),
        })

    def finalize(self, completed=None):
        if self.completed is None:
            self.completed = completed or datetime.now()
        return self

    @property
    def duration_seconds(self):
        end = self.completed or datetime.now()
        return round((end - self.started).total_seconds(), 3)

    def assert_equal(self, step, title, expected, actual, note=""):
        ok = str(expected).strip().lower() == str(actual).strip().lower()
        return self.add(step, title, PASS if ok else FAIL, expected, actual, note)

    def assert_true(self, step, title, cond, expected="True", actual=None, note=""):
        return self.add(step, title, PASS if cond else FAIL,
                        expected, actual if actual is not None else cond, note)

    def manual(self, step, title, note, expected="", actual="", blocks_verdict=True):
        return self.add(step, title, MANUAL, expected, actual, note,
                        blocks_verdict=blocks_verdict)

    def skip(self, step, title, note, blocks_verdict=True):
        return self.add(step, title, SKIP, note=note, blocks_verdict=blocks_verdict)

    def blocked(self, step, title, note, blocks_verdict=True):
        return self.add(step, title, BLOCKED, note=note, blocks_verdict=blocks_verdict)

    def attach(self, path):
        self.evidence.append(path)

    # --- 집계 ----------------------------------------------------------
    @property
    def counts(self):
        c = dict((s, 0) for s in STATUSES)
        for chk in self.checks:
            c[chk.status] = c.get(chk.status, 0) + 1
        return c

    @property
    def verdict(self):
        c = self.counts
        if c[FAIL]:
            return FAIL
        if c[PASS] == 0:
            if c[BLOCKED]:
                return BLOCKED
            return SKIP if c[SKIP] else MANUAL
        # SKIP도 MANUAL과 마찬가지로 PASS를 막는다 — "완전 자동화"는 모든 Step이
        # PASS/FAIL로만 판정되는 상태를 뜻하고(TODO_전체자동화.md 0절, 사용자 확정
        # 2026-08-20), SKIP 1건이라도 있으면 그 TC는 완전 자동화된 것이 아니다.
        # 예외: `blocks_verdict=False`로 등록된 Check(현재는 TC14의 `--deep`
        # 미수행 Step 1건뿐, 사용자 확정 2026-08-21)는 이 계산에서 빠진다 —
        # 비고에는 남지만 PASS를 막지 않는다.
        blocking_bad = any(chk.status in (MANUAL, BLOCKED, SKIP) and chk.blocks_verdict
                           for chk in self.checks)
        return MANUAL if blocking_bad else PASS

    def as_dict(self):
        return {
            "tc_id": self.tc_id, "title": self.title, "verdict": self.verdict,
            "purpose": tc_purpose(self.tc_id, self.title),
            "started": self.started.isoformat(timespec="seconds"),
            "completed": (self.completed or datetime.now()).isoformat(timespec="seconds"),
            "duration_seconds": self.duration_seconds,
            "counts": self.counts, "evidence": self.evidence,
            "timings": self.timings,
            "checks": [dict(c.as_dict(), sequence=i)
                       for i, c in enumerate(self.checks, 1)],
        }


# --- 환경 헤더 ---------------------------------------------------------
def collect_env(config=None):
    """리포트 상단 헤더용 Windows 정보 + 패키지 정보를 수집한다.

    체크리스트 `Checklist` 시트 상단(OS / OS Version / OS Build Version /
    Viewer Version / VX.LIVE.SERVER)과 같은 항목을 채운다.
    확인되지 않은 값은 임의로 채우지 않고 '(확인 필요)'로 남긴다.
    """
    from . import package_info
    from . import sysinfo

    cfg = config or {}
    osi = sysinfo.os_info()
    disp = sysinfo.display_info()
    mem = sysinfo.memory_info()

    windows = {
        "OS": osi.get("Caption") or "(확인 필요)",
        "OS Version": sysinfo.os_display_version() or osi.get("Version") or "(확인 필요)",
        "OS Build Version": sysinfo.os_build_full() or "(확인 필요)",
        "Architecture": osi.get("OSArchitecture") or "(확인 필요)",
        "Display": ("%sx%s / %s%% (%d DPI)"
                    % (disp.get("width"), disp.get("height"),
                       disp.get("scale_percent"), disp.get("dpi", 96))
                    if disp else "(확인 필요)"),
        "GPU": ", ".join(g["name"] for g in sysinfo.gpu_list()) or "(확인 필요)",
        "Memory": ("물리 여유 %sGB / %sGB, 페이지파일 여유 %sGB / %sGB"
                   % (mem.get("physical_free_gb"), mem.get("physical_total_gb"),
                      mem.get("pagefile_free_gb"), mem.get("pagefile_total_gb"))
                   if mem else "(확인 필요)"),
    }
    return {
        "document": DOC_NUMBER,
        "windows": windows,
        "packages": package_info.collect(cfg),
        "windows_updates": sysinfo.windows_updates(5),
    }


def _env_lines(env):
    if not env:
        return []
    L = []
    win = env.get("windows") or {}
    if win:
        L.append(" [ Windows 정보 ]")
        for k, v in win.items():
            L.append("   - %-18s: %s" % (k, v))
    pkg = env.get("packages") or {}
    if pkg:
        L.append(" [ 패키지 정보 ]")
        for k, v in pkg.items():
            L.append("   - %-18s: %s" % (k, v))
    ups = env.get("windows_updates") or []
    if ups:
        L.append(" [ 최근 Windows 업데이트 ]")
        for u in ups:
            L.append("   - %s  %s  (%s)" % (u.get("kb"), u.get("installed_on") or "",
                                            u.get("kind") or ""))
    return L


# ---------------------------------------------------------------------
_STYLE = """
:root{--fg:#1a1a1a;--mut:#666;--line:#d8d8d8;--head:#f3f4f6;--card:#fafafa}
body{font-family:'Malgun Gothic',sans-serif;margin:0;color:var(--fg);background:#fff}
.wrap{max-width:1500px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:26px 0 8px;padding-top:10px;border-top:2px solid #eee}
h3{font-size:13px;margin:14px 0 4px;color:#444}
.meta{color:var(--mut);font-size:12px;margin-bottom:18px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-bottom:8px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:var(--head);font-weight:600}
td.s{font-weight:700;text-align:center}
/* 단계별 판정 표 — 기대값/실제값을 **같은 폭**으로 고정하고 판정 열을 줄인다.
   `table-layout:fixed` + colgroup 이라야 브라우저가 내용 길이로 폭을 재조정하지
   않아 두 열이 실제로 같은 크기로 보인다(Bellalun 리포트와 동일). */
table.steps{table-layout:fixed}
table.steps td,table.steps th{overflow-wrap:anywhere;word-break:break-word}
table.steps col.c-step{width:56px}
table.steps col.c-title{width:16%}
table.steps col.c-verdict{width:46px}
table.steps col.c-exp{width:26%}
table.steps col.c-act{width:26%}
table.steps col.c-note{width:auto}
table.steps td.s{padding:6px 2px;font-size:10.5px;letter-spacing:-.4px}
table.steps code{font-size:11.5px}
/* 실패 항목 표도 같은 균형을 쓴다(TC/순서 열만 다르다). */
table.fails{table-layout:fixed}
table.fails td,table.fails th{overflow-wrap:anywhere;word-break:break-word}
table.fails col.c-tc{width:190px}
table.fails col.c-step{width:56px}
table.fails col.c-title{width:16%}
table.fails col.c-exp{width:26%}
table.fails col.c-act{width:26%}
table.fails col.c-note{width:auto}
.PASS{color:#0a7f3f}.FAIL{color:#c62828}.MANUAL{color:#a06000}.SKIP{color:#777}.BLOCKED{color:#6a1b9a}
.sum td.s{font-size:13px}
tr.hdr td{background:var(--card)}
code{font-family:Consolas,monospace;font-size:12px;word-break:break-all}
/* 대시보드 */
.dash{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0 6px}
.tile{flex:1 1 150px;border:1px solid var(--line);border-radius:8px;padding:12px 14px;background:var(--card)}
.tile .n{font-size:26px;font-weight:700;line-height:1.1}
.tile .k{font-size:11.5px;color:var(--mut);margin-top:2px}
.bar{display:flex;height:14px;border-radius:7px;overflow:hidden;border:1px solid var(--line);margin:8px 0 2px}
.bar span{display:block}
.bPASS{background:#2e9e63}.bFAIL{background:#d34a4a}.bMANUAL{background:#e0a740}.bSKIP{background:#b8b8b8}.bBLOCKED{background:#8e44ad}
.legend{font-size:11.5px;color:var(--mut)}
.k{font-size:11px;color:var(--mut)}
table.cov{table-layout:fixed}
table.cov td,table.cov th{overflow-wrap:anywhere}
tr.gh td{background:#eef1f5;font-weight:700;font-size:12.5px}
table.holds{table-layout:fixed}
table.holds td,table.holds th{overflow-wrap:anywhere}
/* TC 카드 */
.spec{display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 12px}
.spec>div{flex:1 1 260px;border:1px solid var(--line);border-radius:6px;padding:8px 10px;background:var(--card)}
.spec h4{margin:0 0 4px;font-size:11.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}
.spec pre{margin:0;font-family:'Malgun Gothic',sans-serif;font-size:12px;white-space:pre-wrap;line-height:1.5}
.files code{display:block}
.badge{display:inline-block;font-size:11px;padding:1px 7px;border-radius:9px;border:1px solid var(--line);margin-left:6px;vertical-align:2px;color:var(--mut);background:#fff}
a{color:#1558b0}
.note{white-space:pre-wrap}
details>summary{cursor:pointer;color:var(--mut);font-weight:600}
details[open]>summary{margin-bottom:6px}
/* 구현 이력 원문(automation_scope.json 의 reason) — 한 글자도 줄이지 않고
   문장/열거 단위로 세워서 읽히게만 한다(2026-08-26 사용자 지시). */
.hist{font-size:12.5px;line-height:1.62}
.hist .para{border-left:3px solid var(--line);padding:2px 0 2px 10px;margin:0 0 10px}
.hist .para:last-child{margin-bottom:0}
.hist .s-line{margin:0 0 3px}
.hist .h{font-weight:700;color:#22447a;margin:0 0 4px}
.hist ul.enum{margin:4px 0 6px;padding-left:0;list-style:none}
.hist ul.enum li{margin:0 0 3px;padding-left:26px;text-indent:-26px}
.hist .enum{display:inline-block;min-width:22px;font-weight:700;color:#1558b0;text-indent:0}
.hist code{background:#f3f4f6;padding:0 3px;border-radius:3px}
details.hist-box{border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:0 0 8px;background:var(--card)}
details.hist-box>summary{font-size:13px;color:var(--fg)}
details.hist-box[open]{background:#fff}
/* VXvue 전용 — 읽는 사람이 먼저 알아야 하는 시험 범위·용어·리포트 품질 안내.
   Bellalun 리포트에는 없지만 사용자 지시(2026-08-25)로 유지하는 블록이다. */
.caveats{background:#fff8e1;border:1px solid #f0d878;border-radius:6px;padding:8px 14px;margin:12px 0 6px;font-size:12.5px}
.caveats ul{margin:4px 0 0;padding-left:18px}
.glossary{background:#f7f9fc;border:1px solid #dbe3ef;border-radius:6px;padding:8px 14px;margin:8px 0;font-size:12.5px}
.glossary dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;margin:6px 0 0}
.glossary dt{font-weight:700}.glossary dd{margin:0}
.purpose{background:#eef6ff;border-left:4px solid #4b83c3;padding:8px 12px;margin:6px 0 10px;font-size:12.5px}
.ok{background:#f2f8f4;border:1px solid #cfe6d8;border-radius:6px;padding:8px 14px;margin:8px 0;font-size:12.5px}
"""


def _totals(results):
    total = dict((s, 0) for s in STATUSES)
    for r in results:
        for k, v in r.counts.items():
            total[k] = total.get(k, 0) + v
    return total


def _attention_items(results):
    """사용자가 결정을 내려야 하는 비-PASS Step을 실행 순서와 함께 반환한다."""
    items = []
    for result in results:
        for sequence, check in enumerate(result.checks, 1):
            if check.status != PASS:
                items.append((result, sequence, check))
    return items


def report_quality(results):
    """사용자용 필드 완전성과 Step 문장 사전 적용 여부를 검사한다."""
    uncatalogued_tc_purposes = []
    uncatalogued = []
    invalid_statuses = []
    synthesized_expected = 0
    synthesized_actual = 0
    empty_reader_fields = []
    for result in results:
        if result.tc_id not in TC_PURPOSES:
            uncatalogued_tc_purposes.append("%s/%s" % (result.tc_id, result.title))
        for sequence, check in enumerate(result.checks, 1):
            location = "%s/순서%d/Step%s/%s" % (
                result.tc_id, sequence, check.step, check.title)
            if not check.activity_is_catalogued:
                uncatalogued.append(location)
            if check.status not in STATUSES:
                invalid_statuses.append("%s/%s" % (location, check.status))
            if not str(check.expected).strip():
                synthesized_expected += 1
            if not str(check.actual).strip():
                synthesized_actual += 1
            fields = (check.reader_activity, check.reader_expected,
                      check.reader_actual, check.reader_reason, check.reader_action)
            if any(not str(value).strip() for value in fields):
                empty_reader_fields.append(location)
    return {
        "readable": not (uncatalogued_tc_purposes or uncatalogued or invalid_statuses
                         or empty_reader_fields),
        "uncatalogued_tc_purposes": uncatalogued_tc_purposes,
        "uncatalogued_steps": uncatalogued,
        "invalid_statuses": invalid_statuses,
        "empty_reader_fields": empty_reader_fields,
        "synthesized_expected_count": synthesized_expected,
        "synthesized_actual_count": synthesized_actual,
    }


def assert_report_readable(results):
    """새 TC 개발·문서 검증에서 쓰는 엄격한 품질 게이트.

    실제 시험 중에는 미등록 Step이 있어도 리포트를 반드시 남겨야 하므로
    `write_reports()`는 중단하지 않는다. 대신 개발 완료 전 이 함수를 호출해
    사용자 문장 사전 미등록과 빈 사용자 필드가 0건인지 확인한다.
    """
    quality = report_quality(results)
    problems = (quality["uncatalogued_tc_purposes"]
                + quality["uncatalogued_steps"]
                + quality["invalid_statuses"]
                + quality["empty_reader_fields"])
    if problems:
        raise AssertionError("사용자용 리포트 품질 미충족:\n- " + "\n- ".join(problems))
    return quality


def _append_text_glossary(lines):
    lines.append("-" * 80)
    lines.append(" 리포트 용어 설명")
    lines.append("-" * 80)
    for term, meaning in REPORT_GLOSSARY:
        lines.append(" - %-22s: %s" % (term, meaning))
    lines.append("")


def _append_text_quality(lines, results):
    quality = report_quality(results)
    lines.append("-" * 80)
    lines.append(" 리포트 가독성 품질 검사")
    lines.append("-" * 80)
    lines.append(" - 사용자용 필드 누락       : %d건" % len(quality["empty_reader_fields"]))
    lines.append(" - 시험 목적 미등록 TC      : %d건" % len(quality["uncatalogued_tc_purposes"]))
    lines.append(" - 문장 사전 미등록 Step    : %d건" % len(quality["uncatalogued_steps"]))
    lines.append(" - 잘못된 판정 상태         : %d건" % len(quality["invalid_statuses"]))
    lines.append(" - 기대 결과 자동 보완      : %d건" % quality["synthesized_expected_count"])
    lines.append(" - 실제 결과 자동 보완      : %d건" % quality["synthesized_actual_count"])
    pending = (quality["uncatalogued_tc_purposes"] + quality["uncatalogued_steps"]
               + quality["invalid_statuses"])
    if pending:
        lines.append(" - 주의: 아래 항목은 새 TC 완료 전에 사용자용 사전에 등록하거나 수정해야 한다.")
        for item in pending:
            lines.append("   · %s" % item)
    lines.append("")


def write_txt(results, path, env=None):
    """사람이 바로 읽는 요약 텍스트. 상단에 환경 헤더를 붙인다."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    total = _totals(results)

    L = []
    L.append("=" * 80)
    L.append(" %s   (문서번호: %s)" % (REPORT_TITLE, DOC_NUMBER))
    L.append("=" * 80)
    L.append(" 수행 일시     : %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    L.extend(_env_lines(env))
    L.append(" TC 건수       : %d" % len(results))
    L.append(" 판정 합계     : PASS %d / FAIL %d / MANUAL %d / SKIP %d / BLOCKED %d"
             % (total[PASS], total[FAIL], total[MANUAL], total[SKIP], total[BLOCKED]))
    L.append("=" * 80)
    L.append("")

    if REPORT_CAVEATS:
        L.append("-" * 80)
        L.append(" 유의사항")
        L.append("-" * 80)
        for cav in REPORT_CAVEATS:
            L.append(" - %s" % cav)
        L.append("")

    _append_text_glossary(L)
    _append_text_quality(L, results)

    L.append("-" * 80)
    L.append(" TC 별 판정")
    L.append("-" * 80)
    for r in results:
        c = r.counts
        L.append(" [%s] %-28s %s (%.1fs)"
                 % (r.verdict.center(8), r.tc_id, r.title, r.duration_seconds))
        L.append("            P%d F%d M%d S%d B%d"
                 % (c[PASS], c[FAIL], c[MANUAL], c[SKIP], c[BLOCKED]))
    L.append("")

    attention = _attention_items(results)
    L.append("-" * 80)
    L.append(" 사용자가 먼저 확인할 항목 (FAIL / MANUAL / SKIP / BLOCKED)")
    L.append("-" * 80)
    if not attention:
        L.append(" 모든 Step이 PASS이므로 별도 확인이 필요한 항목이 없다.")
    for r, sequence, chk in attention:
        L.append(" [%s] %s / 실행 순서 %d (원본 Step %s) / %s"
                 % (chk.status, r.tc_id, sequence, chk.step, chk.title))
        L.append("   - 확인 결과 : %s" % chk.reader_actual)
        L.append("   - 판정 이유 : %s" % chk.reader_reason)
        L.append("   - 후속 조치 : %s" % chk.reader_action)
    L.append("")

    for r in results:
        L.append("=" * 80)
        L.append(" %s - %s   ->  %s" % (r.tc_id, r.title, r.verdict))
        L.append("=" * 80)
        L.append("  [시험 목적] %s" % tc_purpose(r.tc_id, r.title))
        L.append("")
        for sequence, chk in enumerate(r.checks, 1):
            L.append("  실행 순서 %d / 원본 Step %s / [%s]" %
                     (sequence, chk.step, chk.status))
            L.append("    수행 내용 : %s" % chk.reader_activity)
            L.append("    합격 기준 : %s" % chk.reader_expected)
            L.append("    확인 결과 : %s" % chk.reader_actual)
            L.append("    판정 이유 : %s" % chk.reader_reason)
            L.append("    후속 조치 : %s" % chk.reader_action)
            L.append("")
        if r.evidence:
            L.append("  [증거]")
            for e in r.evidence:
                L.append("    - %s" % e)
        if r.timings:
            L.append("  [기술 참고: 단계별 소요시간]")
            for t in r.timings:
                L.append("    - %s %s: %.3fs / %s / %s"
                         % (t["kind"], t["name"], t["duration_seconds"],
                            t["outcome"], t["detail"]))
        L.append("")

    L.append("=" * 80)
    if attention:
        L.append(" 최종 확인 필요 항목 %d건" % len(attention))
        L.append("=" * 80)
        for r, sequence, c in attention:
            L.append("  [%s] %s / 실행 순서 %d (원본 Step %s) / %s"
                     % (c.status, r.tc_id, sequence, c.step, c.title))
            L.append("     확인 결과: %s" % c.reader_actual)
            L.append("     후속 조치: %s" % c.reader_action)
    else:
        L.append(" 최종 확인 필요 항목 없음")
    L.append("=" * 80)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


# --- HTML 리포트 ------------------------------------------------------
# 구성은 Bellalun `auto/core/result.py` 의 상세 리포트와 같다(사용자 요청,
# 2026-08-26). 요약 대시보드 -> 실행 환경 -> 자동화 커버리지 총괄 -> 실패 원인
# -> 수동/미수행 사유 -> TC별 판정 -> TC 상세 순서로 읽게 만든다.
#
# VXvue 고유 항목(유의사항 / 용어 설명 / 리포트 품질 검사 / 시험 목적 /
# 사용자용 문장 5종)은 그대로 유지한다 — 형식만 Bellalun 쪽에 맞춘다.

def _pct(part, whole):
    return 0 if not whole else round(part * 100.0 / whole, 1)


def _file_url(path):
    """로컬 파일을 브라우저에서 눌러 열 수 있는 링크로 만든다."""
    from urllib.parse import quote
    p = str(path or "").replace("\\", "/")
    if not p:
        return ""
    return "file:///" + quote(p, safe="/:")


def _exists(text):
    """`os.path.exists` 를 안전하게 부른다(긴 문자열·잘못된 문자 대비)."""
    try:
        return bool(text) and os.path.exists(text)
    except (OSError, ValueError):
        return False


def _numbered_items(text):
    """체크리스트의 ``1. ...`` 문단을 단계 번호별로 나눈다.

    번호를 못 붙인 문장은 `0` 키에 모아 두고, 특정 Step 원문을 못 찾았을 때의
    대체값으로 쓴다(예: Expected Result 가 `2,3. ...` 처럼 묶여 있는 경우).
    """
    items = {}
    current = None
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"^(\d+)\s*[.)]\s*(.*)$", line)
        if match:
            current = int(match.group(1))
            items[current] = match.group(2).strip()
        elif current is not None:
            items[current] = (items[current] + " " + line).strip()
        else:
            items[0] = (items.get(0, "") + " " + line).strip()
    return items


def _step_context(meta, tc_id, step):
    """한 판정에 대응하는 **기준 체크리스트 원문**(수행 절차 / 기대 결과).

    자동화가 요약한 문장이 아니라 원문을 실어야 판정 근거를 감사할 수 있다
    (`VXvue/CLAUDE.md` 3절). 체크리스트를 못 읽었으면 빈 문자열이다 —
    리포트가 사유를 지어내지 않는다.
    """
    try:
        number = int(step)
    except (TypeError, ValueError):
        number = 0
    spec = ((meta or {}).get("checklist") or {}).get(tc_id) or {}
    procedures = _numbered_items(spec.get("steps"))
    expected = _numbered_items(spec.get("expected"))
    return {
        "step_description": procedures.get(number, procedures.get(0, "")),
        "source_expected_result": expected.get(number, expected.get(0, "")),
    }


#: 자동화 커버리지 총괄 섹션의 표시 순서와 설명.
#  분류는 `automation_scope.json` 의 `level` 값 그대로이고, 뒤에 붙는 설명은
#  `core/regression.py` 의 수준별 판정(SKIP/EXCLUDED->SKIP,
#  PARTIAL/MANUAL->MANUAL, BLOCKED->BLOCKED)이 실제로 쓰는 의미를 옮긴 것이다.
#  사유 문장 자체는
#  각 TC 의 `reason` 에서 그대로 읽는다 — 리포트가 만들어 내지 않는다.
COVERAGE_LEVELS = (
    ("FULL", "FULL — 전 단계를 자동으로 판정한다"),
    ("PARTIAL", "PARTIAL — 일부 단계는 사람이 확인해야 한다"),
    ("MANUAL", "MANUAL — 수동 전용 TC 다"),
    ("BLOCKED", "BLOCKED — 선행 환경이 없어 수행 자체가 불가능하다"),
    ("SKIP", "SKIP — 자동화할 수 없는 절차라 이번 실행에서 건너뛴다"),
    ("EXCLUDED", "EXCLUDED — 사용자 결정으로 이번 자동화 범위에서 제외했다"),
)

#: 커버리지 타일 색. 등급을 판정 상태 색에 맞춰 읽기 쉽게만 한다.
COVERAGE_TONES = {"FULL": PASS, "PARTIAL": MANUAL, "MANUAL": MANUAL,
                  "BLOCKED": BLOCKED, "SKIP": SKIP, "EXCLUDED": SKIP}


def _coverage_groups(coverage):
    """커버리지 항목을 자동화 등급별로 묶어 표시 순서대로 돌려준다."""
    buckets = {}
    for item in coverage:
        buckets.setdefault(str(item.get("level") or "(등급 미기재)"), []).append(item)
    ordered = [(level, label, buckets.pop(level))
               for level, label in COVERAGE_LEVELS if level in buckets]
    ordered.extend((name, name, items) for name, items in sorted(buckets.items()))
    return ordered


def _html_env(env):
    """실행 환경 및 버전 — Bellalun 리포트와 같은 라벨/값 표 형식."""
    if not env:
        return ""
    e = html.escape
    body = []
    for label, key in (("Windows 정보", "windows"), ("패키지 정보", "packages")):
        data = env.get(key) or {}
        if not data:
            continue
        body.append("<tr class='gh'><td colspan='2'>%s</td></tr>" % e(label))
        for k, v in data.items():
            text = str(v)
            # 실제로 존재하는 경로는 눌러서 열 수 있게 링크로 만든다.
            cell = ("<a href='%s'><code>%s</code></a>" % (_file_url(text), e(text))
                    if _exists(text) else "<code>%s</code>" % e(text))
            body.append("<tr><th style='width:230px'>%s</th><td>%s</td></tr>"
                        % (e(str(k)), cell))
    P = ["<h2>실행 환경 및 버전</h2>"]
    if body:
        P.append("<table>%s</table>" % "".join(body))
    ups = env.get("windows_updates") or []
    if ups:
        P.append("<h3>최근 Windows 업데이트</h3>")
        P.append("<table><tr><th style='width:150px'>KB</th>"
                 "<th style='width:170px'>설치 일자</th><th>종류</th></tr>")
        for u in ups:
            P.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (e(str(u.get("kb") or "")),
                        e(str(u.get("installed_on") or "")),
                        e(str(u.get("kind") or ""))))
        P.append("</table>")
    return "\n".join(P) if len(P) > 1 else ""


def _html_caveats():
    if not REPORT_CAVEATS:
        return ""
    e = html.escape
    return ("<div class='caveats'><b>유의사항 — 이번 회귀 전체에 적용되는 시험 "
            "범위와 한계</b><ul>%s</ul></div>"
            % "".join("<li>%s</li>" % e(cav) for cav in REPORT_CAVEATS))


def _html_glossary():
    e = html.escape
    rows = "".join("<dt>%s</dt><dd>%s</dd>" % (e(term), e(meaning))
                   for term, meaning in REPORT_GLOSSARY)
    return "<div class='glossary'><b>리포트 용어 설명</b><dl>%s</dl></div>" % rows


def _html_quality(results):
    e = html.escape
    quality = report_quality(results)
    status = "PASS" if quality["readable"] else "확인 필요"
    detail = ("사용자용 필드 누락 %d건 / 시험 목적 미등록 %d건 / "
              "문장 사전 미등록 %d건 / 잘못된 판정 상태 %d건 / "
              "기대 결과 자동 보완 %d건 / 실제 결과 자동 보완 %d건"
              % (len(quality["empty_reader_fields"]),
                 len(quality["uncatalogued_tc_purposes"]),
                 len(quality["uncatalogued_steps"]),
                 len(quality["invalid_statuses"]),
                 quality["synthesized_expected_count"],
                 quality["synthesized_actual_count"]))
    missing_items = (quality["uncatalogued_tc_purposes"]
                     + quality["uncatalogued_steps"] + quality["invalid_statuses"])
    missing = "".join("<li>%s</li>" % e(item) for item in missing_items)
    if missing:
        missing = ("<div style='margin-top:6px'><b>새 TC 완료 전에 문장 사전에 "
                   "등록할 Step:</b><ul>%s</ul></div>" % missing)
    return ("<div class='glossary'><b>리포트 가독성 품질 검사: "
            "<span class='%s'>%s</span></b><div>%s</div>%s</div>"
            % (PASS if quality["readable"] else MANUAL, e(status), e(detail),
               missing))


# --- 표 셀 조립 -------------------------------------------------------
# 사용자용 문장(reader_*)을 본문으로 두고, 체크리스트 원문과 코드가 만든 원본
# 값은 보조 줄(`.k` / `<code>`)로 붙인다. 원본 값이 사용자용 문장에 이미 그대로
# 들어 있으면 다시 찍지 않는다 — 같은 문자열이 두 번 보이면 대조가 어려워진다.

def _cell_step(sequence, check):
    return ("%d<div class='k'>Step %s</div>"
            % (sequence, html.escape(str(check.step))))


def _cell_title(check, source):
    e = html.escape
    out = [e(check.title)]
    activity = check.reader_activity
    if activity and activity != check.title:
        out.append("<div class='k'>수행 내용: %s</div>" % e(activity))
    if source["step_description"]:
        out.append("<div class='k'>기준 절차: %s</div>" % e(source["step_description"]))
    return "".join(out)


def _cell_expected(check, source):
    e = html.escape
    out = []
    if source["source_expected_result"]:
        out.append("<div class='k'>기준 기대 결과: %s</div>"
                   % e(source["source_expected_result"]))
    reader = check.reader_expected
    out.append("<div class='note'>%s</div>" % e(reader))
    raw = str(check.expected).strip()
    if raw and raw not in reader:
        out.append("<code>%s</code>" % e(raw))
    return "".join(out)


def _cell_actual(check):
    e = html.escape
    reader = check.reader_actual
    out = ["<div class='note'>%s</div>" % e(reader)]
    raw = str(check.actual).strip()
    if raw and raw not in reader:
        out.append("<code>%s</code>" % e(raw))
    return "".join(out)


def _cell_reason(check):
    e = html.escape
    return ("<div class='note'>%s</div>"
            "<div class='k' style='margin-top:5px'>후속 조치: %s</div>"
            % (e(check.reader_reason), e(check.reader_action)))


#: 구현 이력 원문에서 열거를 시작하는 표기. `(1)`/`①`/`(a)` 처럼 원문이 이미
#  쓰고 있는 것만 인식한다 — 없는 구조를 만들어 넣지 않는다.
_ENUM_MARK = re.compile(r"(?<!\S)(\(\d{1,2}\)|[①-⑮]|\([a-h]\))\s*")

#: 문장 경계. **한글 글자나 닫는 괄호 뒤의 마침표**, 그리고 영문 뒤라도 뒤에
#  공백과 한글·대문자가 오는 마침표(`...tc11_ai_analysis.py. Viewer`)까지 본다.
#  `1.0.11.014` / `p.10` / `Rev.4.2` / `2.2.9절` 은 마침표 뒤에 공백이 없어
#  잘리지 않는다 — 버전·페이지 표기를 문장으로 오인하지 않게 하려는 것이다.
_SENT_SPLIT = re.compile(r"(?<=[가-힣)\]])\.\s+"
                         r"|(?<=[A-Za-z])\.\s+(?=[가-힣A-Z])")

#: 문단 머리말. 원문이 `**...**:` / `**...**—` 로 절을 나눠 쓰고 있어 그대로 쓴다.
_HEAD_MARK = re.compile(r"^\*\*(.+?)\*\*\s*(?:[:：]|—|-)?\s*")


def _inline_marks(text):
    """원문의 `**강조**` 와 백틱 코드 표기를 HTML 로 옮긴다(내용은 그대로)."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out, flags=re.DOTALL)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def _rich_text(raw):
    """개발 기록 원문을 **줄이지 않고** 읽을 수 있게 구조화한다.

    `automation_scope.json` 의 `reason` 은 한 TC 가 수천 자에 이르는 단일 문단
    이라, 그대로 넣으면 표 한 칸이 글 덩어리가 된다(2026-08-26 사용자 지적).
    한 글자도 버리지 않고 아래만 한다:

      * `**강조**` / `` `코드` `` 표기를 실제 강조·코드로 보여 준다
      * 한국어 종결어미 뒤에서 문장을 나눠 한 줄씩 세운다
      * 굵은 머리말이나 날짜로 시작하는 문장에서 새 문단을 연다
      * 원문이 이미 쓰는 `(1)` / `①` / `(a)` 열거를 목록으로 세운다
    """
    text = " ".join(str(raw or "").split())
    if not text:
        return ""
    paragraphs, current = [], []
    for sentence in _SENT_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if not sentence.endswith(".") and not sentence.endswith(":"):
            sentence += "."
        starts_section = bool(re.match(r"^(\*\*|20\d\d-\d\d-\d\d)", sentence))
        if starts_section and current:
            paragraphs.append(current)
            current = []
        current.append(sentence)
    if current:
        paragraphs.append(current)

    out = []
    for group in paragraphs:
        lines = []
        # 원문이 `**머리말**:` 로 절을 나눈 곳은 소제목으로 세운다.
        head = _HEAD_MARK.match(group[0])
        if head:
            lines.append("<div class='h'>%s</div>" % _inline_marks(head.group(1)))
            group = [group[0][head.end():]] + group[1:]
        for sentence in group:
            parts = _ENUM_MARK.split(sentence)
            lead = parts[0].strip()
            if lead:
                lines.append("<div class='s-line'>%s</div>" % _inline_marks(lead))
            items = []
            for mark, body in zip(parts[1::2], parts[2::2]):
                items.append("<li><span class='enum'>%s</span> %s</li>"
                             % (html.escape(mark), _inline_marks(body.strip())))
            if items:
                lines.append("<ul class='enum'>%s</ul>" % "".join(items))
        out.append("<div class='para'>%s</div>" % "".join(lines))
    return "<div class='hist'>%s</div>" % "".join(out)


def _dedup(texts):
    """같은 문장이 여러 Step 에 반복되는 경우가 많다 — 서로 다른 것만 남긴다."""
    out, seen = [], set()
    for value in texts:
        text = " ".join(str(value or "").split())
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _render_html(results, meta, siblings=None):
    """상세 HTML 리포트를 만든다(Bellalun 상세 리포트와 같은 구성).

    `meta` 로 받는 것(모두 선택):
      env               `collect_env()` 결과 — 실행 환경·버전
      command           이 리포트를 만든 실행 명령
      checklist         `{TC ID: {precondition, steps, expected, test_data}}`
      checklist_source  위 원문을 읽은 xlsx 경로
      modules           `{TC ID: ["tests/tc02_mwl_workflow.py", ...]}`
      scope             `{TC ID: {"level":.., "reason":..}}`
      coverage          `[{tc_id, title, level, reason}, ...]` (기준 TC 전체)
    """
    e = html.escape
    meta = meta or {}
    total = _totals(results)
    checks = sum(total.values())
    tc_total = dict((s, 0) for s in STATUSES)
    for r in results:
        if r.verdict in tc_total:
            tc_total[r.verdict] += 1
    wall = sum(r.duration_seconds for r in results)
    first_start = min((r.started for r in results), default=None)
    last_end = max(((r.completed or datetime.now()) for r in results), default=None)

    cl = meta.get("checklist") or {}
    mods = meta.get("modules") or {}
    scope = meta.get("scope") or {}

    P = ["<meta charset='utf-8'>",
         "<title>%s</title>" % e(REPORT_TITLE),
         "<style>%s</style>" % _STYLE,
         "<div class='wrap'>",
         "<h1>%s</h1>" % e(REPORT_TITLE)]
    head = ["문서번호 <code>%s</code>" % e(DOC_NUMBER)]
    if meta.get("checklist_source"):
        head.append("기준 문서 <code>%s</code>"
                    % e(os.path.basename(str(meta["checklist_source"]))))
    head.append("생성 %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if meta.get("command"):
        head.append("실행 명령 <code>%s</code>" % e(str(meta["command"])))
    P.append("<div class='meta'>%s</div>" % " &nbsp;|&nbsp; ".join(head))

    # --- 요약 대시보드 -------------------------------------------------
    P.append("<h2 style='border:0;padding:0;margin-top:6px'>요약 대시보드</h2>")
    P.append("<div class='dash'>")
    P.append("<div class='tile'><div class='n'>%d</div>"
             "<div class='k'>수행 TC</div></div>" % len(results))
    for k in STATUSES:
        P.append("<div class='tile'><div class='n %s'>%d</div>"
                 "<div class='k'>TC %s</div></div>" % (k, tc_total[k], k))
    P.append("<div class='tile'><div class='n'>%d</div>"
             "<div class='k'>검증 항목(Step 단위)</div></div>" % checks)
    P.append("<div class='tile'><div class='n'>%.1f<span style='font-size:14px'>"
             " 분</span></div><div class='k'>총 소요 시간</div></div>"
             % (wall / 60.0))
    P.append("</div>")

    P.append("<div class='bar'>")
    for k in STATUSES:
        if total[k]:
            P.append("<span class='b%s' style='width:%s%%' title='%s %d'></span>"
                     % (k, _pct(total[k], checks), k, total[k]))
    P.append("</div>")
    P.append("<div class='legend'>검증 항목 %s</div>"
             % " / ".join("<b class='%s'>%s %d</b> (%s%%)"
                          % (k, k, total[k], _pct(total[k], checks))
                          for k in STATUSES))
    if first_start and last_end:
        P.append("<div class='meta'>실행 구간 %s ~ %s</div>"
                 % (first_start.strftime("%Y-%m-%d %H:%M:%S"),
                    last_end.strftime("%Y-%m-%d %H:%M:%S")))

    # 시험 범위·한계는 결과를 읽기 **전에** 봐야 하므로 여기 둔다.
    # 용어 설명과 리포트 품질 검사는 제출본 본문에서 결론을 가리므로 부록으로
    # 내렸다(2026-08-26 사용자 지시) — 내용은 그대로 남는다.
    P.append(_html_caveats())

    # --- 실행 환경 -----------------------------------------------------
    P.append(_html_env(meta.get("env")))

    # --- 자동화 커버리지 총괄 (기준 체크리스트 전체) --------------------
    # 이번 실행 결과와 별개로 "기준 체크리스트의 모든 TC 가 자동화됐는가,
    # 못 한 것은 왜인가"를 리포트 앞에서 한 번에 보여 준다.
    coverage = meta.get("coverage") or []
    if coverage:
        groups = _coverage_groups(coverage)
        levels = {}
        for x in coverage:
            key = str(x.get("level"))
            levels[key] = levels.get(key, 0) + 1
        P.append("<h2>자동화 커버리지 총괄 — 기준 체크리스트 %d TC</h2>" % len(coverage))
        P.append("<div class='meta'>이번 실행 결과와 별개로 <b>기준 체크리스트의 "
                 "모든 TC</b>가 자동화됐는지를 한눈에 보는 표다. 등급"
                 "(<code>level</code>)은 <code>automation_scope.json</code> 에서 "
                 "그대로 읽고, 범위·미자동화·해제 조건은 같은 파일의 "
                 "<code>reason</code> 을 읽는 사람 기준으로 정리한 문장이다"
                 "(<code>core/result.TC_AUTOMATION_SCOPE</code>). <b>줄이지 않은 "
                 "구현·검증 이력 원문은 이 리포트 맨 뒤 '부록 B'</b> 에 TC 별로 "
                 "그대로 실려 있다.</div>")
        P.append("<div class='dash'>")
        P.append("<div class='tile'><div class='n'>%d</div>"
                 "<div class='k'>기준 TC 총계</div></div>" % len(coverage))
        for level, label in COVERAGE_LEVELS:
            if not levels.get(level):
                continue
            P.append("<div class='tile'><div class='n %s'>%d</div>"
                     "<div class='k'>%s</div></div>"
                     % (COVERAGE_TONES.get(level, ""), levels[level], e(label)))
        P.append("</div>")
        P.append("<table class='cov'><colgroup>"
                 "<col style='width:178px'><col style='width:12%'>"
                 "<col style='width:66px'><col style='width:78px'>"
                 "<col style='width:27%'><col style='width:25%'><col>"
                 "</colgroup><tr><th>TC ID</th><th>Title</th><th>범위</th>"
                 "<th>이번 실행</th><th>자동으로 판정하는 범위</th>"
                 "<th>자동으로 판정하지 않는 것</th><th>해제 조건</th></tr>")
        ran = dict((r.tc_id, r.verdict) for r in results)
        for level, label, items in groups:
            P.append("<tr class='gh'><td colspan='7'>%s — %d건</td></tr>"
                     % (e(label), len(items)))
            for x in items:
                tc_id = str(x.get("tc_id") or "")
                verdict = ran.get(tc_id)
                link = ("<a href='#%s'>%s</a>" % (e(tc_id), e(tc_id))
                        if verdict else e(tc_id))
                summary = automation_scope(tc_id)
                P.append("<tr><td>%s<div class='k'>"
                         "<a href='#history-%s'>구현 이력 →</a></div></td>"
                         "<td>%s</td><td class='s'>%s</td>"
                         "<td class='s %s'>%s</td>"
                         "<td class='note'>%s</td><td class='note'>%s</td>"
                         "<td class='note'>%s</td></tr>"
                         % (link, e(tc_id), e(str(x.get("title") or "-")),
                            e(str(x.get("level") or "-")),
                            verdict or "", verdict or "미수행",
                            e(summary.get("scope") or "(요약 미등록)"),
                            e(summary.get("gap") or "(요약 미등록)"),
                            e(summary.get("unblock") or "-")))
        P.append("</table>")

    # --- 먼저 볼 것: FAIL 원인 ------------------------------------------
    fails = [(r, seq, c) for r in results
             for seq, c in enumerate(r.checks, 1) if c.status == FAIL]
    if fails:
        P.append("<h2>실패 항목 %d건 — 원인</h2>" % len(fails))
        P.append("<div class='meta'>회귀는 앞 단계가 뒤 TC 의 전제다. "
                 "<b>가장 위의 FAIL 부터</b> 읽는다 — 아래 FAIL 중 일부는 그 "
                 "실패의 결과일 수 있다.</div>")
        P.append("<table class='fails'><colgroup>"
                 "<col class='c-tc'><col class='c-step'><col class='c-title'>"
                 "<col class='c-exp'><col class='c-act'><col class='c-note'>"
                 "</colgroup><tr><th>TC</th><th>순서</th><th>확인 항목</th>"
                 "<th>합격 기준 / 기대값</th><th>확인 결과 / 실제값</th>"
                 "<th>판정 이유 / 후속 조치</th></tr>")
        for r, seq, c in fails:
            source = _step_context(meta, r.tc_id, c.step)
            P.append("<tr><td><a href='#%s'>%s</a></td><td>%s</td><td>%s</td>"
                     "<td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (e(r.tc_id), e(r.tc_id), _cell_step(seq, c),
                        _cell_title(c, source), _cell_expected(c, source),
                        _cell_actual(c), _cell_reason(c)))
        P.append("</table>")

    # --- MANUAL / SKIP / BLOCKED 사유 (TC 별로 한 행) --------------------
    holds = []
    for r in results:
        items = [(seq, c) for seq, c in enumerate(r.checks, 1)
                 if c.status in (MANUAL, SKIP, BLOCKED)]
        if items:
            holds.append((r, items))
    if holds:
        total_items = sum(len(x) for _, x in holds)
        P.append("<h2>수동 확인 / 미수행 / 수행 불가 — TC %d건 (확인 항목 %d개) "
                 "— 사유와 후속 조치</h2>" % (len(holds), total_items))
        P.append("<div class='meta'>TC 하나에 여러 항목이 걸려 있어도 <b>한 행</b>"
                 "으로 묶어 적는다. 항목별 원문 사유는 각 TC 상세의 단계별 판정 "
                 "표에 그대로 남아 있다.</div>")
        P.append("<table class='holds'><colgroup><col style='width:200px'>"
                 "<col style='width:52px'><col style='width:26%'>"
                 "<col style='width:34%'><col></colgroup>"
                 "<tr><th>TC</th><th>건수</th><th>확인 항목</th>"
                 "<th>판정 이유</th><th>후속 조치</th></tr>")
        for r, items in holds:
            labels = "<br>".join(
                "<span class='s %s'>[%s]</span> 순서 %d (Step %s) %s"
                % (c.status, c.status, seq, e(str(c.step)), e(c.title))
                for seq, c in items)
            reasons = "<br><br>".join(e(x) for x in
                                      _dedup(c.reader_reason for _, c in items))
            actions = "<br>".join(e(x) for x in
                                  _dedup(c.reader_action for _, c in items))
            P.append("<tr><td><a href='#%s'>%s</a><br><span class='k'>%s</span></td>"
                     "<td style='text-align:center'>%d</td><td>%s</td>"
                     "<td class='note'>%s</td><td class='note'>%s</td></tr>"
                     % (e(r.tc_id), e(r.tc_id), e(r.title), len(items), labels,
                        reasons or "(사유 미기재)", actions or "(후속 조치 미기재)"))
        P.append("</table>")

    if not fails and not holds:
        P.append("<div class='ok'>모든 검증 항목이 PASS 다 — 사용자가 따로 판단해야 "
                 "할 FAIL / MANUAL / SKIP / BLOCKED 항목이 없다.</div>")

    # --- TC 요약 표 + 목차 -----------------------------------------------
    P.append("<h2>TC 별 판정</h2>")
    P.append("<table class='sum'><tr><th>TC ID</th><th>Title</th>"
             "<th>자동화 범위</th><th>판정</th><th>P</th><th>F</th><th>M</th>"
             "<th>S</th><th>B</th><th>시작</th><th>종료</th><th>소요</th></tr>")
    for r in results:
        c = r.counts
        lvl = (scope.get(r.tc_id) or {}).get("level") or "-"
        end = r.completed or datetime.now()
        P.append("<tr><td><a href='#%s'>%s</a></td><td>%s</td><td>%s</td>"
                 "<td class='s %s'>%s</td><td>%d</td><td>%d</td><td>%d</td>"
                 "<td>%d</td><td>%d</td><td>%s</td><td>%s</td><td>%.1fs</td></tr>"
                 % (e(r.tc_id), e(r.tc_id), e(r.title), e(str(lvl)),
                    r.verdict, r.verdict, c[PASS], c[FAIL], c[MANUAL], c[SKIP],
                    c[BLOCKED], r.started.strftime("%H:%M:%S"),
                    end.strftime("%H:%M:%S"), r.duration_seconds))
    P.append("</table>")

    # --- TC 상세 ---------------------------------------------------------
    for r in results:
        spec = cl.get(r.tc_id) or {}
        sc = scope.get(r.tc_id) or {}
        end = r.completed or datetime.now()
        P.append("<h2 id='%s'>%s — %s <span class='%s'>[%s]</span>%s</h2>"
                 % (e(r.tc_id), e(r.tc_id), e(r.title), r.verdict, r.verdict,
                    ("<span class='badge'>%s</span>" % e(str(sc.get("level"))))
                    if sc.get("level") else ""))
        P.append("<div class='meta'>시작 %s &nbsp;→&nbsp; 종료 %s "
                 "&nbsp;|&nbsp; 소요 %.1fs</div>"
                 % (r.started.strftime("%Y-%m-%d %H:%M:%S"),
                    end.strftime("%Y-%m-%d %H:%M:%S"), r.duration_seconds))
        P.append("<div class='purpose'><b>시험 목적:</b> %s</div>"
                 % e(tc_purpose(r.tc_id, r.title)))

        # 기준 문서 원문 — 체크리스트에서 읽은 그대로만 싣는다.
        cells = []
        if spec.get("precondition"):
            cells.append(("사전 조건 (Precondition)", spec["precondition"]))
        if spec.get("steps"):
            cells.append(("수행 단계 (Step Description)", spec["steps"]))
        if spec.get("expected"):
            cells.append(("기대 결과 (Expected Result)", spec["expected"]))
        if spec.get("test_data"):
            cells.append(("테스트 데이터 (Test Data)", spec["test_data"]))
        if cells:
            P.append("<h3>기준 문서 원문 — 이 TC 가 무엇을 검증하는가</h3>")
            P.append("<div class='spec'>")
            for head_text, body in cells:
                P.append("<div><h4>%s</h4><pre>%s</pre></div>"
                         % (e(head_text), e(str(body))))
            P.append("</div>")

        # 자동화 범위 — 무엇까지 자동으로 판정했고 무엇을 남겼는가.
        # 구현 이력 원문은 부록 B 에 그대로 있고 여기서는 링크만 건다
        # (같은 글을 두 곳에 싣지 않는다).
        summary = automation_scope(r.tc_id)
        if summary or sc.get("level") or sc.get("reason"):
            P.append("<h3>자동화 범위 — 무엇을 자동으로 판정했는가</h3>")
            P.append("<div class='spec'>")
            P.append("<div><h4>자동으로 판정하는 범위</h4><pre>%s</pre></div>"
                     % e(summary.get("scope") or "(요약 미등록)"))
            P.append("<div><h4>자동으로 판정하지 않는 것</h4><pre>%s</pre></div>"
                     % e(summary.get("gap") or "(요약 미등록)"))
            P.append("<div><h4>해제 조건</h4><pre>%s</pre></div>"
                     % e(summary.get("unblock") or "-"))
            P.append("</div>")
            if sc.get("reason"):
                P.append("<div class='meta'>구현·검증 이력 원문은 "
                         "<a href='#history-%s'>부록 B</a> 에 줄이지 않고 "
                         "그대로 실려 있다.</div>" % e(r.tc_id))

        # 자동화 코드 위치
        files = mods.get(r.tc_id) or []
        if files:
            P.append("<h3>자동화 코드 위치</h3><div class='meta files'>%s</div>"
                     % "".join("<code>%s</code>" % e(p) for p in files))

        # 단계별 판정
        P.append("<h3>단계별 판정 — 기대값 / 실제값 / 근거</h3>")
        P.append("<table class='steps'><colgroup>"
                 "<col class='c-step'><col class='c-title'><col class='c-verdict'>"
                 "<col class='c-exp'><col class='c-act'><col class='c-note'>"
                 "</colgroup><tr><th>순서</th><th>확인 항목</th><th>판정</th>"
                 "<th>합격 기준 / 기대값</th><th>확인 결과 / 실제값</th>"
                 "<th>판정 이유 / 후속 조치</th></tr>")
        for seq, c in enumerate(r.checks, 1):
            source = _step_context(meta, r.tc_id, c.step)
            P.append("<tr><td>%s</td><td>%s</td><td class='s %s'>%s</td>"
                     "<td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (_cell_step(seq, c), _cell_title(c, source), c.status,
                        c.status, _cell_expected(c, source), _cell_actual(c),
                        _cell_reason(c)))
        P.append("</table>")

        # 증거 (클릭 가능한 링크)
        if r.evidence:
            P.append("<h3>증거 (스크린샷·파일)</h3><table>"
                     "<tr><th style='width:46px'>#</th><th>경로</th></tr>")
            for i, p in enumerate(r.evidence, 1):
                P.append("<tr><td>%d</td><td><a href='%s'>%s</a></td></tr>"
                         % (i, _file_url(p), e(str(p))))
            P.append("</table>")

        # 소요시간 분해
        if r.timings:
            accounted = sum(t["duration_seconds"] for t in r.timings)
            unaccounted = r.duration_seconds - accounted
            P.append("<h3>소요 시간 분해</h3>")
            P.append("<table><tr><th style='width:60px'>종류</th>"
                     "<th>단계 / 대기</th><th style='width:90px'>소요</th>"
                     "<th style='width:80px'>결과</th><th>상세</th></tr>")
            for t in r.timings:
                P.append("<tr><td>%s</td><td>%s</td><td>%.3fs</td>"
                         "<td class='%s'>%s</td><td>%s</td></tr>"
                         % (e(str(t["kind"])), e(str(t["name"])),
                            t["duration_seconds"], t["outcome"],
                            e(str(t["outcome"])), e(str(t["detail"]))))
            if unaccounted > 5:
                P.append("<tr class='hdr'><td>-</td><td>(스텝 외) 전제 준비·재시도 등"
                         "</td><td>%.1fs</td><td>-</td>"
                         "<td>스텝 합계 %.1fs / TC 전체 %.1fs</td></tr>"
                         % (unaccounted, accounted, r.duration_seconds))
            P.append("</table>")

    # --- 부록 — 용어 / 구현 이력 원문 / 리포트 품질 / 산출물 -------------
    # 본문에는 읽는 사람 기준으로 정리한 문장을 싣고, **줄이지 않은 원문**은
    # 여기에 TC 별로 그대로 둔다. 판정 근거를 감사하려면 원문이 있어야 한다
    # (`VXvue/CLAUDE.md` 3절). 본문이 요약이라는 사실도 함께 밝힌다.
    P.append("<h2>부록 A — 리포트 용어 설명</h2>")
    P.append(_html_glossary())

    histories = [x for x in coverage if str(x.get("reason") or "").strip()]
    if histories:
        P.append("<h2>부록 B — 자동화 구현·검증 이력 (원문)</h2>")
        P.append("<div class='meta'>본문의 '자동화 범위'는 읽기 위해 정리한 문장이고, "
                 "여기 실린 것은 <code>automation_scope.json</code> 의 "
                 "<code>reason</code> <b>원문 전체</b>다 — 한 글자도 줄이지 않았고, "
                 "문장·열거 단위로 세워 두기만 했다. 각 TC 제목을 눌러 펼친다.</div>")
        for x in histories:
            tc_id = str(x.get("tc_id") or "")
            P.append("<details id='history-%s' class='hist-box'><summary>%s — %s "
                     "<span class='badge'>%s</span></summary>%s</details>"
                     % (e(tc_id), e(tc_id), e(str(x.get("title") or "-")),
                        e(str(x.get("level") or "-")), _rich_text(x.get("reason"))))

    # 리포트 자신의 품질 검사 — 시험 결과가 아니라 **이 리포트가 읽을 수 있게
    # 만들어졌는지**를 보는 개발용 지표라 부록에 둔다.
    P.append("<h2>부록 C — 리포트 가독성 품질 검사</h2>")
    P.append("<div class='meta'>시험 판정이 아니라 <b>이 리포트 자체</b>의 품질 "
             "지표다. 사용자용 문장이 비어 있거나 사전에 등록되지 않은 Step 이 "
             "있으면 여기에 드러난다.</div>")
    P.append(_html_quality(results))

    if siblings:
        P.append("<h2>부록 D — 구조화된 실행 이력</h2>")
        P.append("<div class='meta'>같은 판정을 기계가 다시 읽을 수 있는 JSON으로 "
                 "남긴다.</div><table>")
        for k, p in siblings.items():
            P.append("<tr><th style='width:80px'>%s</th>"
                     "<td><a href='%s'>%s</a></td></tr>"
                     % (e(k), _file_url(p), e(str(p))))
        P.append("</table>")
    P.append("</div>")
    return "\n".join(x for x in P if x)


def write_reports(results, out_dir, run_name=None, env=None, meta=None):
    """HTML / JSON 리포트를 out_dir에 생성하고 경로를 반환한다.

    `meta` 는 **HTML 상세 리포트**에만 쓰는 부가 정보다(`_render_html` 참고).
    `env` 는 따로 받아 두 형식 모두에 싣는다 — `meta["env"]` 가
    비어 있으면 이 값으로 채운다.

    HTML은 사람이 읽는 제출·검토본이고 JSON은 원본 값과 실행 이력을 보존하는
    기계 판독본이다. CSV와 TXT는 두 파일의 내용을 중복하므로 기본 생성하지
    않는다(사용자 결정, 2026-08-26).
    """
    meta = dict(meta or {})
    if env and not meta.get("env"):
        meta["env"] = env
    os.makedirs(out_dir, exist_ok=True)
    stamp = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(out_dir, "Result_%s" % stamp)
    total = _totals(results)

    # JSON
    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"title": REPORT_TITLE, "document": DOC_NUMBER,
                   "generated": datetime.now().isoformat(timespec="seconds"),
                   "caveats": list(REPORT_CAVEATS),
                   "environment": env or {},
                   "report_quality": report_quality(results),
                   "totals": total,
                   "results": [r.as_dict() for r in results]},
                  f, ensure_ascii=False, indent=2)

    # HTML — Bellalun 상세 리포트와 같은 구성(`_render_html`).
    html_path = base + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_render_html(results, meta,
                             siblings={"json": json_path}))

    return {"json": json_path, "html": html_path}
