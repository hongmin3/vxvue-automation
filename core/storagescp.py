# -*- coding: utf-8 -*-
r"""DICOM Storage SCP 시험 서버(웹) 클라이언트 — TC02/TC05 수신 판정 근거.

## 왜 이 모듈이 생겼나

2026-08-26까지 Storage SCP는 **이 PC에 설치된 Bunny**였고, 수신 판정은
`core/bunny.py`가 로컬 로그와 수신 폴더를 읽어서 했다. 그 구성에는 두 가지
한계가 있었다.

1. 체크리스트 TC02/TC05의 Precondition은 *"다른 PC 의 Server 이용"* 인데
   로컬 Bunny는 그 조건을 충족하지 못했다(`bunny.precondition_note()`가 그
   차이를 리포트에 고지하고 있었다).
2. **Bunny로는 Dose SR과 스냅샷(XC)이 확인되지 않았다.** 체크리스트 TC05의
   Test Data는 *"Image, 스냅샷 영상, Dose SR 전송됨"* 을 기대하는데 수신
   폴더에는 DX 영상만 남아, 자동화는 사양서(Conformance Statement Rev.4.2
   p.10 2.2.9절 "…for correctly transferred MG images")를 근거로 "Dose SR은
   MG 전용"이라 보고 SKIP 처리하고 있었다.

사용자 지시(2026-08-26)로 Storage SCP를 MWL/Print와 같은 사내 공용 시험 서버
(`STORAGE_SCP` / `10.13.0.222:11116`)로 옮겼다. 이 서버는 수신 목록과 원본
객체를 웹 API로 돌려주므로 **받은 쪽에서** 판정할 수 있다(`core/printscp.py`가
Print에서 쓰는 것과 같은 방식).

**실측(2026-08-26)**: 이 서버에 이미 들어와 있던 VXvue 스터디를 내려받아
태그를 읽으니 한 검사 안에 세 종류가 모두 있었다 —
`1.2.840.10008.5.1.4.1.1.1.1`(DX 영상), `1.2.840.10008.5.1.4.1.1.7`(XC
스냅샷), `1.2.840.10008.5.1.4.1.1.88.67`(**X-Ray Radiation Dose SR**).
Modality는 `DX,SR,XC`로 MG가 아니다. 즉 **DX 촬영에서도 Dose SR이 전송된다** —
이전의 "MG 전용" 결론은 서버가 그 객체를 받지 못한 결과였을 가능성이 크다.
TC05가 이 모듈로 재판정한다.

## 확인된 엔드포인트 (2026-08-26 실제 응답)

```
GET    /api/scp-status              {"running":true,"ae_title":"STORAGE_SCP",
                                     "host":"10.13.0.222","port":11116,
                                     "tls_running":true,"tls_port":21116,
                                     "retention_days":5,"max_storage_mib":3072}
GET    /api/studies                 [{"study_instance_uid":...,"patient_id":...,
                                      "modalities":"DX,SR,XC","instance_count":5,
                                      "station_names":...,"last_received_at":...}, ...]
GET    /api/studies/signature       {"signature":"9|2026-08-26T05:42:35Z"}  (건수|최종수신)
GET    /api/studies/<uid>/download  study ZIP (<seriesUID>/<sopUID>.dcm)
GET    /api/usage                   {"bytes":...,"count":...,"max_bytes":...}
DELETE /api/studies[/<uid>]         삭제 — **이 자동화는 절대 호출하지 않는다**
```

## 다른 사람의 시험 자산을 건드리지 않는다

이 서버는 여러 사람이 공유한다(실측: `station_names`가 `VXvue_JJH`,
`vieworks` 등으로 섞여 있다). 그래서 **삭제 API를 쓰지 않고**, 이번 실행이
만든 `Patient ID`(`core/testdata.py`가 실행 시각을 각인해 유일하게 만든다)로
우리 스터디만 골라낸다(`CLAUDE.md` 3절). 서버는 `retention_days`가 지나면
스스로 지운다.
"""

import io
import json
import os
import time
import urllib.parse
import urllib.request
import zipfile

from . import bunny as bunny_mod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEWLINE = chr(10)

#: 이 자동화가 판정에 쓰는 SOP Class UID.
SOP_DX_IMAGE = "1.2.840.10008.5.1.4.1.1.1.1"
SOP_SECONDARY_CAPTURE = "1.2.840.10008.5.1.4.1.1.7"
SOP_DOSE_SR = "1.2.840.10008.5.1.4.1.1.88.67"


class StorageScpError(RuntimeError):
    pass


# --- 설정 읽기 ---------------------------------------------------------

def _dicom_cfg(cfg):
    return (cfg.get("dicom") or {})


def storage_spec(cfg):
    """`dicom.servers_to_register`의 Storage 항목(없으면 빈 dict)."""
    for spec in (_dicom_cfg(cfg).get("servers_to_register") or []):
        if spec.get("kind") == "Storage":
            return spec
    return {}


def server_url(cfg):
    return (_dicom_cfg(cfg).get("storage_server_url") or "").rstrip("/")


def uses_local_bunny(cfg):
    """Storage SCP가 **이 PC의 Bunny**인가.

    설정된 Storage 항목의 ip/port가 `dicom.bunny`가 여는 포트와 같은지로
    판단한다 — 드라이브 문자나 PC 이름처럼 사람이 잊고 못 고치는 값을
    기준으로 삼지 않는다. 웹 API 주소가 없으면 원격 판정 자체가 불가능하므로
    로컬로 본다.
    """
    if not server_url(cfg):
        return True
    spec = storage_spec(cfg)
    bunny = _dicom_cfg(cfg).get("bunny") or {}
    if not bunny:
        return False
    # Bunny는 이 PC에서만 뜬다 — 포트가 같고 app_path가 있으면 로컬 구성이다.
    return (str(spec.get("port")) == "3000"
            and bool(bunny.get("app_path"))
            and str(spec.get("ae_title", "")).lower() == "bunny")


# --- HTTP 클라이언트 ---------------------------------------------------

class StorageServer:
    def __init__(self, base_url, timeout=20):
        self.base = (base_url or "").rstrip("/")
        self.timeout = timeout

    def _get(self, path, raw=False):
        req = urllib.request.Request(self.base + path, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = resp.read()
        if raw:
            return data
        text = data.decode("utf-8", "replace")
        return json.loads(text) if text.strip() else None

    def status(self):
        """SCP 기동 상태와 SCU 등록에 필요한 AE/IP/Port."""
        return self._get("/api/scp-status")

    def running(self):
        try:
            return bool((self.status() or {}).get("running"))
        except Exception:                                     # noqa: BLE001
            return False

    def usage(self):
        return self._get("/api/usage")

    def studies(self):
        return self._get("/api/studies") or []

    def signature(self):
        """`"<건수>|<최종 수신 시각>"` — 변화 감지용 싼 폴링 지표."""
        return ((self._get("/api/studies/signature") or {}).get("signature") or "")

    def studies_of(self, patient_id):
        want = str(patient_id or "").strip()
        if not want:
            return []
        return [s for s in self.studies()
                if str(s.get("patient_id", "")).strip() == want]

    def download_study(self, study_uid, dest_dir):
        """스터디 ZIP을 받아 `dest_dir`에 풀고 .dcm 경로 목록을 돌려준다.

        ZIP 안은 `<SeriesInstanceUID>/<SOPInstanceUID>.dcm` 구조지만 **그대로
        풀지 않고 파일명만 남겨 한 폴더에 편다.** DICOM UID는 하나가 60자를
        넘고 그게 폴더명·파일명에 두 번 들어가면 Windows MAX_PATH(260자)를
        넘겨 추출이 `FileNotFoundError`로 실패한다(2026-08-26 실측: 스크래치
        경로에서 두 스터디가 이 이유로 실패했다). SOP UID는 그 자체로 유일해
        같은 폴더에 펴도 덮어쓸 위험이 없고, 판정은 태그만 읽으므로 시리즈
        폴더 구조가 필요하지 않다.
        """
        blob = self._get("/api/studies/%s/download" % urllib.parse.quote(study_uid),
                         raw=True)
        os.makedirs(dest_dir, exist_ok=True)
        out = []
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                target = os.path.join(dest_dir, os.path.basename(name))
                with open(target, "wb") as f:
                    f.write(zf.read(name))
                out.append(target)
        out.sort()
        return out


def server(cfg):
    url = server_url(cfg)
    return StorageServer(url) if url else None


# --- TC가 쓰는 판정 API -------------------------------------------------

def mark(cfg, force_backend=None):
    """전송 직전의 기준점. 이 값을 `wait_for_store()`에 그대로 넘긴다.

    로컬 Bunny면 로그 오프셋과 파일 mtime 기준을, 원격 서버면 수신 목록
    signature를 담는다 — 두 백엔드의 "이번 전송으로 새로 생긴 것"을 가르는
    기준이 서로 다르기 때문에 TC 쪽에서 그 차이를 몰라도 되게 감싼다.

    `force_backend`("bunny"/"storagescp")를 주면 `uses_local_bunny(cfg)`
    판단(= `dicom.servers_to_register`의 Storage 항목 기준) 대신 그 값을
    쓴다. Extra Tool(TC06)처럼 **Storage와 별개로 등록되는 대상**(`config.json`의
    `extra_tool.server`, 사용자 지시 2026-08-24로 `dicom.servers_to_register`와
    독립)의 수신 판정에 이 모듈을 재사용할 때 필요하다 — Storage 자신의 등록이
    나중에 바뀌어도(예: 다시 로컬로) Extra Tool의 판단은 그것과 무관해야 한다.
    """
    backend = force_backend or ("bunny" if uses_local_bunny(cfg) else "storagescp")
    if backend == "bunny":
        return {"backend": "bunny",
                "log_offset": bunny_mod.log_size(cfg),
                "since": time.time() - 5}
    srv = server(cfg)
    try:
        signature = srv.signature() if srv else ""
    except Exception:                                         # noqa: BLE001
        signature = ""
    return {"backend": "storagescp", "signature": signature,
            "since": time.time() - 5}


def _work_dir(patient_id):
    stamp = str(patient_id or time.strftime("%Y%m%d_%H%M%S"))
    return os.path.join(HERE, "work", "storage_receive", stamp)


def _remote_result(ok, files, study, note):
    """원격 경로의 반환값. `log_excerpt`를 여기서 한 번만 만든다.

    로컬 Bunny 경로는 로그 원문을 `log_excerpt`로 주므로, 원격도 같은 키에
    **받은 쪽 근거**를 담아 TC가 백엔드를 구분하지 않고 증거로 첨부할 수 있게
    한다(키가 없으면 리포트 직전에 KeyError로 죽는다 — 2026-08-26 실제 발생).
    """
    lines = ["# Storage SCP 수신 근거 (서버 웹 API)", "", note, ""]
    if study:
        lines.append("## 서버가 돌려준 스터디 레코드")
        lines.append(json.dumps(study, ensure_ascii=False, indent=2))
        lines.append("")
    lines.append("## 내려받은 객체 %d건" % len(files))
    lines.extend("  " + os.path.basename(f) for f in files)
    return {"ok": bool(ok), "files": files, "study": study,
            "backend": "storagescp", "note": note,
            "log_excerpt": NEWLINE.join(lines) + NEWLINE}


def wait_for_store(cfg, baseline, count=1, timeout=150, poll=3.0,
                   patient_id=None, work_dir=None, force_backend=None):
    """C-STORE 수신을 기다린다. 반환 형식은 두 백엔드가 동일하다.

    반환: {"ok", "files"(로컬 .dcm 경로), "note", "log_excerpt"(수신 근거 텍스트),
           "study"(원격일 때만), "backend"}

    `log_excerpt`는 두 백엔드가 모두 채운다 — 로컬은 Bunny 로그 구간, 원격은
    서버가 돌려준 스터디 레코드와 내려받은 객체 목록이다. TC는 이것을 증거
    파일로 첨부하므로 키가 없으면 리포트 직전에 죽는다(2026-08-26 실제 발생).

    원격에서는 **이번 실행의 Patient ID로 스터디를 지목**하고, 그 스터디의
    객체를 내려받아 파일로 준다 — 판정하는 쪽(TC05의 SOP Class 확인)이
    로컬/원격을 구분하지 않아도 되게 하기 위함이다.

    `force_backend`는 `mark()`와 같은 이유로 있다 — 보통은 `baseline`이 이미
    `mark()`가 정한 `backend`를 담고 있어 그대로 따르지만, 명시적으로 override할
    수 있게 남겨 둔다.
    """
    baseline = baseline or {}
    backend = force_backend or baseline.get("backend")
    if backend == "bunny" or (backend is None and uses_local_bunny(cfg)):
        res = bunny_mod.wait_for_store(
            cfg, count=count, timeout=timeout, poll=poll,
            log_offset=baseline.get("log_offset", 0),
            files_newer_than=baseline.get("since"))
        res.setdefault("study", None)
        res["backend"] = "bunny"
        return res

    srv = server(cfg)
    if srv is None:
        return _remote_result(False, [], None,
                              "config.json의 dicom.storage_server_url이 비어 있어 "
                              "원격 Storage SCP 수신을 확인할 수 없다.")
    if not patient_id:
        return _remote_result(False, [], None,
                              "이번 실행의 Patient ID를 받지 못해 공용 시험 서버에서 "
                              "우리 스터디를 지목할 수 없다(다른 사람의 스터디를 "
                              "이번 결과로 세지 않기 위해 여기서 멈춘다).")

    end = time.time() + timeout
    study, last_error = None, ""
    while time.time() < end:
        try:
            found = srv.studies_of(patient_id)
        except Exception as exc:                              # noqa: BLE001
            last_error = "%s: %s" % (type(exc).__name__, exc)
            found = []
        if found:
            study = max(found, key=lambda s: str(s.get("last_received_at") or ""))
            if int(study.get("instance_count") or 0) >= count:
                # 전송이 여러 객체로 나뉘어 오는 중일 수 있어 한 번 더 쉬고
                # 건수가 늘지 않는 것을 확인한 뒤 확정한다.
                time.sleep(poll)
                try:
                    again = srv.studies_of(patient_id)
                    if again:
                        study = max(again, key=lambda s: str(s.get("last_received_at") or ""))
                except Exception:                             # noqa: BLE001
                    pass
                break
        time.sleep(poll)

    if not study:
        note = ("%ds 안에 Storage SCP(%s)에서 Patient ID=%s 스터디를 찾지 못했다."
                % (timeout, server_url(cfg), patient_id))
        if last_error:
            note += " 마지막 오류: %s" % last_error
        return _remote_result(False, [], None, note)

    dest = work_dir or _work_dir(patient_id)
    try:
        files = srv.download_study(study.get("study_instance_uid"), dest)
    except Exception as exc:                                  # noqa: BLE001
        return _remote_result(
            False, [], study,
            "스터디는 수신됐으나(Instances=%s, Modality=%s) 원본을 내려받지 못해 "
            "객체 종류를 판정할 수 없다: %s: %s"
            % (study.get("instance_count"), study.get("modalities"),
               type(exc).__name__, exc))

    ok = len(files) >= count
    return _remote_result(
        ok, files, study,
        ("Storage SCP(%s %s:%s)가 Patient ID=%s 스터디를 수신했다 — "
                 "Modality=%s / Series %s / Instances %s / 최종 수신 %s. "
                 "원본 %d건을 내려받아 객체 종류를 확인했다."
                 % (storage_spec(cfg).get("ae_title"), storage_spec(cfg).get("ip"),
                    storage_spec(cfg).get("port"), patient_id,
                    study.get("modalities"), study.get("series_count"),
                    study.get("instance_count"), study.get("last_received_at"),
                    len(files))
         if ok else
         "스터디는 보이는데 내려받은 객체가 %d건(기대 %d건 이상)이다."
         % (len(files), count)))


def wait_for_resend(cfg, patient_id, since_last_received_at, timeout=90, poll=3.0,
                    work_dir=None):
    """같은 영상을 다시 보냈을 때(재전송) 원격 서버가 실제로 다시 받았는지 확인한다.

    `wait_for_store()`의 "건수가 N 이상"과는 다른 신호가 필요하다 — **재전송은
    같은 SOP Instance UID를 다시 보내는 것**이라 서버가 기존 객체를 갱신 처리하고
    `instance_count`가 늘지 않는다(2026-08-27 실측: TC06 2차 전송 후에도
    Instances=3 그대로였다 — 그래서 `wait_for_store(count=이전+1)`로 재전송을
    판정하려던 첫 시도가 오탐 FAIL을 냈다). 대신 스터디의 `last_received_at`이
    `since_last_received_at`(1차 전송 직후 값)보다 **뒤로 갱신**됐는지로 판정한다.

    반환 형식은 `wait_for_store()`와 동일하다.
    """
    srv = server(cfg)
    if srv is None:
        return _remote_result(
            False, [], None,
            "config.json의 dicom.storage_server_url이 비어 있어 재전송 수신을 "
            "확인할 수 없다.")
    if not patient_id:
        return _remote_result(
            False, [], None,
            "이번 실행의 Patient ID를 받지 못해 재전송 확인 대상을 지목할 수 없다.")

    since = str(since_last_received_at or "")
    end = time.time() + timeout
    study, last_error = None, ""
    while time.time() < end:
        try:
            found = srv.studies_of(patient_id)
        except Exception as exc:                                 # noqa: BLE001
            last_error = "%s: %s" % (type(exc).__name__, exc)
            found = []
        if found:
            candidate = max(found, key=lambda s: str(s.get("last_received_at") or ""))
            if str(candidate.get("last_received_at") or "") > since:
                study = candidate
                break
        time.sleep(poll)

    if not study:
        note = ("%ds 안에 Storage SCP(%s)에서 Patient ID=%s 스터디의 최종 수신 "
                "시각이 %s 이후로 갱신되는 것을 확인하지 못했다."
                % (timeout, server_url(cfg), patient_id, since or "(없음)"))
        if last_error:
            note += " 마지막 오류: %s" % last_error
        return _remote_result(False, [], None, note)

    dest = work_dir or _work_dir(str(patient_id) + "_resend")
    try:
        files = srv.download_study(study.get("study_instance_uid"), dest)
    except Exception as exc:                                     # noqa: BLE001
        return _remote_result(
            True, [], study,
            "재전송으로 최종 수신 시각이 %s → %s로 갱신된 것은 확인했으나 원본을 "
            "다시 내려받지 못했다: %s: %s"
            % (since or "(없음)", study.get("last_received_at"),
               type(exc).__name__, exc))

    return _remote_result(
        True, files, study,
        "재전송을 확인했다 — Patient ID=%s 스터디의 최종 수신 시각이 %s → %s로 "
        "갱신됐다(Instances=%s, 같은 SOP Instance UID라 건수는 그대로다). "
        "원본 %d건을 다시 내려받았다."
        % (patient_id, since or "(없음)", study.get("last_received_at"),
           study.get("instance_count"), len(files)))


def precondition_note(cfg):
    """판정 note에 붙일, 어느 Storage로 확인했는지에 대한 고지문."""
    if uses_local_bunny(cfg):
        return bunny_mod.precondition_note(cfg)
    spec = storage_spec(cfg)
    return ("체크리스트 Precondition의 '다른 PC 의 Server 이용 - Storage'를 "
            "충족한다 — 이 실행은 **다른 PC의 사내 공용 시험 서버**"
            "(%s %s:%s, MWL/Print와 같은 서버)를 Storage SCP로 사용했고, 수신은 "
            "그 서버의 웹 API(%s)로 **받은 쪽에서** 확인했다(사용자 지시, "
            "2026-08-26). 이 서버는 여러 사람이 공유하므로 삭제 API를 쓰지 않고 "
            "이번 실행의 Patient ID로만 골라낸다."
            % (spec.get("ae_title"), spec.get("ip"), spec.get("port"),
               server_url(cfg)))
