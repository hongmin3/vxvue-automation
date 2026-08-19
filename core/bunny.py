# -*- coding: utf-8 -*-
r"""Bunny(로컬 DICOM Storage SCP) 수신 확인 — TC_WindowsUpdate_05/06 판정 근거.

## 왜 로컬 Storage로 확인하는가

체크리스트 TC05/06의 Precondition은 "다른 PC 의 Server 이용 - Storage"다. 하지만
지금 시험대에는 **이 PC에 Bunny가 떠 있고 VXvue가 그것을 Storage SCP로 등록해
Echo까지 성공**한 상태다(`config.json`의 `dicom.servers_to_register`,
`BUNNY_TEST` / AE `Bunny` / `<STORAGE_HOST>`:3000 — 이 주소가 이 PC 자신이다).

사용자 지시(2026-08-19): **"storage는 지금 PC에 연결되어 있으니 일단 지금 PC로
전송 확인하는 것으로 하고, 추후 다른 PC에서 연결해서 사용하는 것으로 고도화가
필요하다."**

그래서 이 모듈은 로컬 Bunny를 근거로 전송을 판정하되, **판정 note에 "체크리스트
Precondition은 다른 PC의 Storage이며 이 실행은 로컬 Storage로 확인했다"는 차이를
항상 남긴다.** 전송 경로(제품 → 네트워크 → SCP)는 같지만 "다른 PC"라는 조건은
충족하지 않으므로, 그 사실을 숨기면 리포트가 근거를 잘못 말하게 된다.

다른 PC로 옮길 때 바꿔야 하는 것은 `config.json`의 `dicom.servers_to_register`
Storage 항목(ip/port)과 `dicom.bunny.receive_dir`/`log_dir`(원격이면 UNC 경로 또는
그 PC에서 확인)뿐이다. 이 모듈은 경로를 하드코딩하지 않는다.

## 판정 근거 두 가지 (실측, 2026-08-19)

1. **로그** — `<log_dir>\<YYYYMMDD>_<CallingAE>.txt`. **Calling AE별로 파일이
   갈린다**(실측: `20260819_VXVUE.txt`). 그래서 Bellalun 자동화가 같은 Bunny로
   보낸 것과 섞이지 않는다. C-ECHO/C-STORE 요청·응답과 Status가 기록된다.

   ```
   18:32:42[9]:<< CEcho Request
   18:32:42[9]:>> CEcho Response
       PID: 1, Message ID: 1,  Dataset: 0101h, Status: 0000h
   ```

2. **수신 파일** — 수신 폴더 하위에 저장된 DICOM 파일. `core/dicomlite.py`로
   태그를 읽어 환자정보가 실제로 일치하는지 확인한다. 제품이 "보냈다"고 말한
   것을 그대로 믿지 않기 위한 것이다. 실측으로 확인한 값(2026-08-19):

   ```
   PatientID=VXVUE_MWL_DX_01  PatientName=AUTO^VXVUE^^^
   AccessionNumber=ACC_VX_AUTO_001  Modality=DX
   BodyPartExamined=CHEST  ViewPosition=PA  KVP=50
   SOPClassUID=1.2.840.10008.5.1.4.1.1.1.1  (DX Image Storage - For Presentation)
   TransferSyntax=1.2.840.10008.1.2  (Implicit VR LE)
   ```

   MWL 처방으로 등록한 값이 그대로 수신 파일에 담겨 있다 — TC02가 요구하는
   "촬영화면·Database·전송정보가 모두 MWL 스터디 정보와 일치"의 마지막 고리다.

로그 문구 하나로 성공을 단정하지 않고 **파일까지 교차 확인**한다.
"""

import io
import os
import re
import time
from datetime import date

# Bunny 로그의 성공 Status. DICOM 표준에서 0000h = Success.
_STATUS_RX = re.compile(r"Status:\s*([0-9A-Fa-f]{4})h")
_STORE_REQ_RX = re.compile(r"CStore\s*Request|C-STORE\s*Request", re.I)
_STORE_RSP_RX = re.compile(r"CStore\s*Response|C-STORE\s*Response", re.I)


class BunnyError(RuntimeError):
    pass


def _bunny_cfg(cfg):
    return ((cfg.get("dicom") or {}).get("bunny") or {})


def log_path(cfg, calling_ae=None, day=None):
    """오늘(또는 지정일) Calling AE의 Bunny 로그 파일 경로.

    실측: 파일명이 `<YYYYMMDD>_<CallingAE>.txt`라서 AE별로 갈린다. VXvue의
    전송만 보려면 이 파일만 읽으면 된다.
    """
    log_dir = _bunny_cfg(cfg).get("log_dir")
    if not log_dir:
        return ""
    ae = calling_ae or (cfg.get("dicom") or {}).get("local_ae_title") or "VXVUE"
    d = (day or date.today()).strftime("%Y%m%d")
    return os.path.join(log_dir, "%s_%s.txt" % (d, ae.upper()))


def read_log(cfg, calling_ae=None, day=None):
    """Bunny 로그 전문. 없으면 빈 문자열."""
    p = log_path(cfg, calling_ae, day)
    if not p or not os.path.isfile(p):
        return ""
    try:
        return io.open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def log_size(cfg, calling_ae=None, day=None):
    """로그 크기(바이트). 전송 전후 증가분으로 '이번 실행의 기록'을 가려낸다.

    로그는 누적 파일이라 전체를 검사하면 **이전 실행의 성공을 이번 것으로
    착각한다.** 그래서 항상 "전송 직전 크기"를 받아 그 이후 구간만 본다.
    """
    p = log_path(cfg, calling_ae, day)
    try:
        return os.path.getsize(p) if p and os.path.isfile(p) else 0
    except OSError:
        return 0


def log_since(cfg, offset, calling_ae=None, day=None):
    """`offset` 바이트 이후에 새로 기록된 로그 구간만 돌려준다."""
    p = log_path(cfg, calling_ae, day)
    if not p or not os.path.isfile(p):
        return ""
    try:
        with io.open(p, encoding="utf-8", errors="replace") as f:
            f.seek(0)
            text = f.read()
    except OSError:
        return ""
    # 문자 오프셋이 아니라 바이트 오프셋이므로 보수적으로 처리한다 — 크기가
    # 줄었으면(로그 회전) 전체를 돌려준다.
    if offset <= 0 or offset >= len(text.encode("utf-8", "replace")):
        return text if offset <= 0 else ""
    raw = text.encode("utf-8", "replace")[offset:]
    return raw.decode("utf-8", "replace")


def store_results(log_text):
    """로그 구간에서 C-STORE 응답 Status 목록을 뽑는다.

    반환: {"requests": n, "responses": n, "statuses": ["0000", ...],
           "all_success": bool}
    """
    requests = len(_STORE_REQ_RX.findall(log_text or ""))
    statuses = []
    for line in (log_text or "").splitlines():
        if _STORE_RSP_RX.search(line):
            statuses.append(None)                 # 응답 줄, Status는 다음 줄
        elif statuses and statuses[-1] is None:
            m = _STATUS_RX.search(line)
            if m:
                statuses[-1] = m.group(1).upper()
    done = [s for s in statuses if s]
    return {"requests": requests, "responses": len(statuses),
            "statuses": done,
            "all_success": bool(done) and all(s == "0000" for s in done)}


def receive_dirs(cfg):
    """수신 파일을 찾을 폴더 목록.

    **실측(2026-08-19): Bunny는 수신한 객체를 `Receive` 폴더가 아니라 `Temp`
    폴더에 쓴다.** 이 PC에서 VXvue가 C-STORE로 보낸 흉부 영상은
    <Bunny 설치폴더>/Temp/1.dcm (15.7MB)로 저장됐고 `Receive`는 비어 있었다.
    그래서 `receive_dir`만 보면 "C-STORE는 성공했는데 파일이 없다"는 잘못된
    판정이 난다(실제로 한 번 그렇게 났다).

    두 폴더를 모두 본다 — 어느 쪽에 쓰는지가 Bunny 설정/버전에 달려 있으므로
    한쪽만 고정하지 않는다. `config.json`의 `dicom.bunny.temp_dir`이 없으면
    `receive_dir`의 형제 폴더 `Temp`를 추정한다(경로를 하드코딩하지 않는다).
    """
    b = _bunny_cfg(cfg)
    out = []
    recv = b.get("receive_dir") or ""
    if recv:
        out.append(recv)
    temp = b.get("temp_dir") or ""
    if not temp and recv:
        temp = os.path.join(os.path.dirname(recv.rstrip(chr(92) + chr(47))), "Temp")
    if temp:
        out.append(temp)
    return [d for d in out if d and os.path.isdir(d)]


def receive_dir(cfg):
    """호환용 — 첫 번째 수신 폴더."""
    dirs = receive_dirs(cfg)
    return dirs[0] if dirs else (_bunny_cfg(cfg).get("receive_dir") or "")


def received_files(cfg, newer_than=None):
    """수신 폴더들의 DICOM 파일 목록(확장자 무관, DICM 시그니처 기준).

    `newer_than`(epoch 초)을 주면 그 시각 이후에 만들어진 것만 돌려준다 —
    이전 실행이 남긴 파일을 이번 결과로 착각하지 않기 위함이다.
    """
    roots = receive_dirs(cfg)
    if not roots:
        return []
    out = []
    for root in roots:
        out.extend(_scan(root, newer_than))
    out.sort(key=lambda p: os.path.getmtime(p))
    return out


def _scan(root, newer_than):
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            p = os.path.join(dirpath, name)
            try:
                if newer_than is not None and os.path.getmtime(p) < newer_than:
                    continue
                with open(p, "rb") as f:
                    if f.read(132)[128:132] != b"DICM":
                        continue
            except OSError:
                continue
            out.append(p)
    return out


def wait_for_store(cfg, count=1, timeout=120, poll=3.0, log_offset=0,
                   files_newer_than=None, calling_ae=None):
    """C-STORE 수신을 로그와 파일 양쪽에서 기다린다.

    반환: {
      "files": [경로...], "log_excerpt": 새로 기록된 로그 구간(앞 4000자),
      "store": store_results() 결과, "ok": bool, "note": 설명
    }

    `ok`는 **파일이 실제로 생겼고 로그의 C-STORE Status가 전부 0000h**일 때만
    True다. 한쪽만 보고 성공으로 단정하지 않는다.
    """
    end = time.time() + timeout
    files, log_text = [], ""
    while time.time() < end:
        files = received_files(cfg, newer_than=files_newer_than)
        log_text = log_since(cfg, log_offset, calling_ae)
        st = store_results(log_text)
        if len(files) >= count and st["all_success"]:
            return {"files": files, "log_excerpt": log_text[:4000], "store": st,
                    "ok": True,
                    "note": "수신 파일 %d건 / C-STORE 응답 %d건 모두 Status 0000h"
                            % (len(files), len(st["statuses"]))}
        time.sleep(poll)

    st = store_results(log_text)
    reason = []
    if len(files) < count:
        reason.append("수신 파일 %d건(기대 %d건 이상)" % (len(files), count))
    if not st["all_success"]:
        reason.append("C-STORE 응답 Status=%s" % (", ".join(st["statuses"]) or "기록 없음"))
    return {"files": files, "log_excerpt": log_text[:4000], "store": st,
            "ok": False,
            "note": "%ds 안에 수신을 확인하지 못했다: %s" % (timeout, "; ".join(reason))}


def precondition_note(cfg):
    """판정 note에 붙일, 로컬 Storage로 확인했다는 사실 고지문.

    체크리스트 Precondition("다른 PC 의 Server 이용 - Storage")과의 차이를
    리포트에서 숨기지 않기 위한 것이다.
    """
    spec = next((s for s in ((cfg.get("dicom") or {}).get("servers_to_register") or [])
                 if s.get("kind") == "Storage"), {})
    return ("체크리스트 Precondition은 '다른 PC 의 Server 이용 - Storage'이지만, "
            "이 실행은 **이 PC에 설치된 Bunny**(%s %s:%s)를 Storage SCP로 사용해 "
            "확인했다(사용자 지시, 2026-08-19). 전송 경로(제품 → DICOM 네트워크 "
            "→ SCP)는 동일하나 '다른 PC'라는 조건은 충족하지 않는다 — 원격 PC "
            "Storage 검증은 config.json의 Storage 항목만 바꿔 재실행하면 되도록 "
            "설계했고, 고도화 대상으로 NEXT_TASK.md에 남겼다."
            % (spec.get("ae_title", "Bunny"), spec.get("ip", "?"), spec.get("port", "?")))
