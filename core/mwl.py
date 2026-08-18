# -*- coding: utf-8 -*-
"""DICOM MWL SCP 서버(웹) 클라이언트.

Bellalun `auto/core/mwl.py`와 동일한 파일이다(제품 비의존 HTTP 클라이언트).
다만 VXvue는 Mammography(MG)가 아니라 일반 촬영(DX)이므로 처방 생성 헬퍼로
`make_dx_order()`를 추가했다. Bellalun의 `DATA_FLOW_MWL_01`(MG) 처방은
공용 시험 서버를 함께 쓰는 다른 제품 것이므로 건드리지 않는다.

http://<host>:5000 에서 동작하는 시험용 MWL SCP를 HTTP로 제어한다.
브라우저 조작 없이 처방 등록/조회/삭제와 SCP 기동/정지가 가능하므로
MWL 관련 TC의 테스트 데이터 준비가 완전 자동화된다.

확인된 엔드포인트 (2026-08-10, 실제 응답으로 검증)
  GET  /                          Worklist 목록 (HTML)
  GET  /worklist/new              신규 등록 폼
  POST /worklist/new              처방 등록
  GET  /worklist/<id>/json        처방 1건 JSON
  POST /worklist/<id>/delete      처방 1건 삭제
  POST /worklist/delete-all       전체 삭제
  POST /scp/start                 SCP 기동 (ae_title, port, default_charset)
  POST /scp/stop                  SCP 정지
  POST /test/load-samples         샘플 처방 적재
"""

import json
import re
import urllib.parse
import urllib.request

_UUID = re.compile(r"/worklist/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                   r"[0-9a-f]{4}-[0-9a-f]{12})/json")

# Mammography 처방 기본값. 값이 없는 필드는 서버가 빈 값으로 둔다.
MG_DEFAULTS = {
    "modality": "MG",
    "requested_procedure_priority": "",
    "specific_character_set": "ISO_IR 192",
}


class MwlError(RuntimeError):
    pass


class MwlServer:
    def __init__(self, base_url, timeout=15):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    # --- 저수준 -------------------------------------------------------
    def _get(self, path):
        req = urllib.request.Request(self.base + path)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read().decode("utf-8", "replace")

    def _post(self, path, data=None):
        body = urllib.parse.urlencode(data or {}).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")

    # --- 처방 ---------------------------------------------------------
    def list_ids(self):
        return sorted(set(_UUID.findall(self._get("/"))))

    def get(self, item_id):
        return json.loads(self._get(f"/worklist/{item_id}/json"))

    def list_items(self):
        return [self.get(i) for i in self.list_ids()]

    def find(self, **match):
        """필드값이 모두 일치하는 처방을 반환한다. 예) find(patient_id='X')"""
        out = []
        for item in self.list_items():
            if all(str(item.get(k, "")) == str(v) for k, v in match.items()):
                out.append(item)
        return out

    def create(self, **fields):
        """처방을 등록하고 등록된 항목의 JSON을 반환한다.

        날짜는 YYYY-MM-DD, 시간은 HH:MM 형식으로 넣는다(폼 input type 기준).
        """
        data = dict(MG_DEFAULTS)
        data.update({k: v for k, v in fields.items() if v is not None})
        before = set(self.list_ids())
        status, _ = self._post("/worklist/new", data)
        if status not in (200, 302):
            raise MwlError(f"처방 등록 실패: HTTP {status}")
        after = set(self.list_ids())
        new = after - before
        if not new:
            raise MwlError("처방이 등록되지 않았습니다. 필수 필드를 확인하십시오.")
        return self.get(next(iter(new)))

    def delete(self, item_id):
        status, _ = self._post(f"/worklist/{item_id}/delete")
        return status in (200, 302)

    def delete_where(self, **match):
        """조건에 맞는 처방만 삭제한다. delete_all보다 안전해 기본으로 쓴다."""
        n = 0
        for item in self.find(**match):
            if self.delete(item["id"]):
                n += 1
        return n

    # --- SCP ----------------------------------------------------------
    def scp_start(self, ae_title, port, default_charset="ISO_IR 192"):
        status, _ = self._post("/scp/start", {
            "ae_title": ae_title, "port": port, "default_charset": default_charset})
        return status in (200, 302)

    def scp_stop(self):
        status, _ = self._post("/scp/stop")
        return status in (200, 302)

    def scp_running(self):
        """목록 페이지의 상태 배지로 기동 여부를 판단한다."""
        html = self._get("/")
        m = re.search(r'class="badge(?: on)?"[^>]*>([^<]*)<', html)
        return ("badge on" in html), (m.group(1).strip() if m else "")


    # --- 테스트 데이터 준비 --------------------------------------------
    def ensure_order(self, today, **fields):
        """오늘 날짜의 시험 처방을 보장한다.

        - 같은 patient_id의 처방이 오늘(sps_start_date) 것이면 그대로 재사용
        - 오늘 것이 아니면 **삭제하고 새로 생성** (검증 기록을 당일 것으로 유지)
        - 다른 patient_id의 처방은 건드리지 않는다

        today는 'YYYY-MM-DD'. 반환: (처방 JSON, 'reused'|'recreated'|'created', 삭제건수)
        """
        pid = fields.get("patient_id")
        compact = today.replace("-", "")
        stale = []
        for item in self.find(patient_id=pid):
            if str(item.get("sps_start_date", "")).replace("-", "") == compact:
                return item, "reused", 0
            stale.append(item)

        for item in stale:
            self.delete(item["id"])
        return (self.create(**fields),
                "recreated" if stale else "created", len(stale))


def make_mg_order(patient_id, patient_name, accession_number, sps_id,
                  station_ae, sps_start_date, sps_start_time="09:00",
                  procedure_id=None, procedure_description="Routine Mammography",
                  patient_sex="F", patient_birthdate="1980-01-01",
                  hospital_code=None, station_name="MAMMO"):
    """Mammography MWL 처방 필드 묶음.

    hospital_code는 TC_Basic_WorkFlow_11에서 Requested Procedure Code Value로
    전달한다. 실제 Bellalun Viewer가 Hospital Code를 어느 Tag에서 읽는지는
    Setting > DICOM > MWL 의 Code Mapping Tag 설정에 따르므로, 사용 전
    해당 설정과 대조할 것.
    """
    fields = {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "patient_sex": patient_sex,
        "patient_birthdate": patient_birthdate,
        "accession_number": accession_number,
        "modality": "MG",
        "scheduled_station_ae_title": station_ae,
        "scheduled_station_name": station_name,
        "requested_procedure_id": procedure_id or sps_id,
        "requested_procedure_description": procedure_description,
        "sps_id": sps_id,
        "sps_description": procedure_description,
        "sps_start_date": sps_start_date,
        "sps_start_time": sps_start_time,
    }
    if hospital_code:
        fields["rp_code_value"] = hospital_code
        fields["rp_code_meaning"] = procedure_description
        fields["rp_code_scheme"] = "99VIEWORKS"
    return fields


def make_dx_order(patient_id, patient_name, accession_number, sps_id,
                  station_ae, sps_start_date, sps_start_time="09:00",
                  procedure_id=None, procedure_description="CHEST",
                  sps_description="CHEST PA", patient_sex="M",
                  patient_birthdate="1980-01-01", station_name="VXVUE"):
    """VXvue(일반 촬영)용 DX MWL 처방 필드 묶음.

    2026-08-18 사용자 지시로 추가했다. 기존 공용 MWL 서버에는 Bellalun/VXvue
    Mammo가 쓰는 MG 처방만 있어 VXvue 워크플로우와 Modality가 맞지 않았다.
    실제 환자정보를 쓰지 않는 비식별 시험 데이터만 등록한다.
    """
    return {
        "specific_character_set": "ISO_IR 192",
        "patient_id": patient_id,
        "patient_name": patient_name,
        "patient_sex": patient_sex,
        "patient_birthdate": patient_birthdate,
        "accession_number": accession_number,
        "modality": "DX",
        "scheduled_station_ae_title": station_ae,
        "scheduled_station_name": station_name,
        "requested_procedure_id": procedure_id or sps_id,
        "requested_procedure_description": procedure_description,
        "study_description": procedure_description,
        "sps_id": sps_id,
        "sps_description": sps_description,
        "sps_start_date": sps_start_date,
        "sps_start_time": sps_start_time,
        "requested_procedure_priority": "",
    }
