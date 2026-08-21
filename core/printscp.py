# -*- coding: utf-8 -*-
r"""DICOM Print SCP 시험 서버(웹) 클라이언트 — TC_WindowsUpdate_07 판정 근거.

Bellalun `auto/core/printscp.py`에서 가져왔다(2026-08-19). 같은 사내 시험 서버를
두 제품이 공유하므로 엔드포인트는 동일하고, **VXvue 자동화가 보낸 필름만
골라내는 필터**를 더했다 — Bellalun 자동화가 같은 서버로 계속 필름을 보내고
있어서(실측: `calling_ae_title="BELLALUN"` 필름 70건) 신규 수신 판정에 그것이
섞이면 안 된다.

## 왜 웹 API로 판정하는가

체크리스트 TC07의 Expected Result는 "Print 성공한다"뿐이다. 제품 UI의 DICOM
Queue만 보고 판정하면 **제품이 "보냈다"고 말한 것을 그대로 믿는 것**이 된다.
이 시험 서버는 수신 필름 목록을 JSON으로 주므로 **받은 쪽에서 확인**할 수 있다.

확인된 엔드포인트 (2026-08-19 실제 응답으로 재확인)

```
GET    /api/scp-status     {"running":true,"ae_title":"PRINT_SCP","host":...,
                            "port":11113,"tls_running":true,"tls_port":21113}
GET    /api/jobs           [{"id":70,"received_at":"...","calling_ae_title":"BELLALUN",
                            "film_size_id":"8INX10IN"}, ...]
DELETE /api/jobs/<id>      필름 1건 삭제
GET    /api/storage-usage  저장 사용량
```

`calling_ae_title`이 있으므로 **기존 필름을 지우지 않고도** VXvue가 보낸 것만
가려낼 수 있다. 다른 제품의 시험 자산을 건드리지 않는다(`CLAUDE.md` 3절).
"""

import json
import os
import time
import urllib.request

# Tesseract 설치 경로(이 QA PC 실측). 없으면 PATH의 tesseract를 쓴다.
TESSERACT_EXE = os.path.join("C:", os.sep, "Program Files", "Tesseract-OCR",
                             "tesseract.exe")


class PrintScpError(RuntimeError):
    pass


class PrintServer:
    def __init__(self, base_url, timeout=15):
        self.base = (base_url or "").rstrip("/")
        self.timeout = timeout

    def _req(self, path, method="GET"):
        req = urllib.request.Request(self.base + path, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
        return json.loads(raw) if raw.strip() else None

    def status(self):
        """SCP 기동 상태와 SCU 등록에 필요한 AE/IP/Port."""
        return self._req("/api/scp-status")

    def running(self):
        try:
            st = self.status() or {}
        except Exception as exc:                          # noqa: BLE001
            return False, "상태 조회 실패: %s" % exc
        return bool(st.get("running")), "AE=%s %s:%s" % (
            st.get("ae_title"), st.get("host"), st.get("port"))

    def jobs(self):
        return self._req("/api/jobs") or []

    def jobs_from(self, calling_ae):
        """지정한 Calling AE가 보낸 필름만 돌려준다.

        VXvue 자동화의 판정에는 이것만 쓴다 — 같은 서버를 Bellalun 자동화와
        공유하므로 전체 목록으로 판정하면 다른 제품의 필름을 자기 결과로
        착각한다(실측: 이 서버에 BELLALUN 필름이 이미 70건 있었다).
        """
        want = str(calling_ae or "").strip().upper()
        return [j for j in self.jobs()
                if str(j.get("calling_ae_title") or "").strip().upper() == want]

    def wait_for_job(self, calling_ae, exclude_ids=(), timeout=90, poll=3.0):
        """`calling_ae`가 보낸 **신규** 필름이 들어올 때까지 대기한다.

        반환: (신규 필름 리스트, 설명 문구). 시간이 초과되면 빈 리스트와 함께
        지금까지 본 것을 설명에 담는다 — 예외로 던지지 않는 이유는 호출부가
        "전송이 확인되지 않았다"를 판정으로 남길 수 있어야 하기 때문이다.
        """
        exclude = set(str(v) for v in exclude_ids)
        end = time.time() + timeout
        seen_total = 0
        while time.time() < end:
            try:
                mine = self.jobs_from(calling_ae)
            except Exception as exc:                      # noqa: BLE001
                return [], "필름 목록 조회 실패: %s" % exc
            seen_total = len(mine)
            fresh = [j for j in mine if str(j.get("id")) not in exclude]
            if fresh:
                return fresh, "신규 필름 %d건 (id %s)" % (
                    len(fresh), ", ".join(str(j.get("id")) for j in fresh))
            time.sleep(poll)
        return [], ("%ds 안에 %s가 보낸 신규 필름이 확인되지 않았다"
                    "(기존 %d건은 그대로)." % (timeout, calling_ae, seen_total))

    def delete_job(self, job_id):
        self._req("/api/jobs/%s" % job_id, method="DELETE")
        return True

    def preview_bytes(self, job_id):
        """수신 필름의 실제 픽셀(JPEG)을 받아온다.

        `/api/jobs/<id>` 응답의 `preview_url` 필드로 실존을 확인했다(문서화된
        4개 엔드포인트에는 없었다, 2026-08-21 실측 — 사용자 제보로 Print
        Overlay가 실제 필름에 반영되는지 픽셀로 확인해야 해서 찾아냈다).
        """
        req = urllib.request.Request(self.base + "/api/jobs/%s/preview" % job_id)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read()

    # 필름 전체를 한 장으로 OCR하면 오버레이 라벨을 거의 못 읽는다(실측
    # 2026-08-21: 1318x1600 필름에서 `50 qi E DOI : 2026-08-21 EI. j 1115`만
    # 나오고 Acc. No / Performing Physician은 통째로 누락됐다). 라벨이 X-ray
    # 픽셀에 둘러싸인 **네 모서리의 작은 흰 글씨**라서, 큰 이미지 하나로는
    # Tesseract의 레이아웃 분석이 그 줄을 글자로 보지 않는다. 그래서 오버레이가
    # 그려지는 네 모서리 띠만 잘라 확대해 각각 OCR하고 결과를 합친다 — 같은
    # 필름에서 4개 라벨 전부가 평문으로 읽힌다(job 86/89/91 3장으로 확인).
    #
    # 띠 크기와 전처리·psm 조합은 추측이 아니라 3장으로 실측해 고른 값이다:
    #  - 세로 12%: bottom_left에 3줄(Acc. No / Performing Physician / TOI)이
    #    들어가므로 7%로는 맨 윗줄(Acc. No)이 잘려 나갔다.
    #  - psm 6(균일 블록)과 psm 11(희소 텍스트)의 결과가 서로 달랐다 —
    #    top_right는 psm 6에서 빈 문자열, psm 11에서만 `DOI : 2026-08-21`이
    #    읽혔다. 어느 하나로 정하지 않고 둘 다 돌려 합집합을 쓴다.
    #  - 반전(invert)은 오히려 나빠져 쓰지 않는다. 임계값 150 이진화는 psm 6에서
    #    top_right를 살려 주므로 세 번째 조합으로 넣었다.
    OVERLAY_BAND_RATIO = 0.12
    OVERLAY_SIDE_RATIO = 0.60

    def preview_ocr_text(self, job_id, tesseract_exe=None):
        """수신 필름 이미지를 OCR해 텍스트를 돌려준다(Print Overlay 판정용).

        실측(2026-08-21): 오버레이 라벨은 사양서의 항목명과 다르게 그려진다
        (예: "Exposure Index" -> `E.I. : 1115`, "Exposure Date" ->
        `DOI : 2026-08-21`, "Accession Number" -> `Acc. No : ...`).
        """
        import io
        import pytesseract
        from PIL import Image

        exe = tesseract_exe or TESSERACT_EXE
        if os.path.exists(exe):
            pytesseract.pytesseract.tesseract_cmd = exe
        img = Image.open(io.BytesIO(self.preview_bytes(job_id))).convert("L")
        w, h = img.size
        bh = max(1, int(h * self.OVERLAY_BAND_RATIO))
        bw = max(1, int(w * self.OVERLAY_SIDE_RATIO))
        corners = [(0, 0, bw, bh), (w - bw, 0, w, bh),
                   (0, h - bh, bw, h), (w - bw, h - bh, w, h)]
        chunks = []
        for box in corners:
            crop = img.crop(box)
            big = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
            binz = crop.point(lambda v: 0 if v > 150 else 255).resize(
                (crop.width * 4, crop.height * 4), Image.LANCZOS)
            for im, psm in ((big, 6), (big, 11), (binz, 6)):
                try:
                    chunks.append(pytesseract.image_to_string(
                        im, config="--psm %d" % psm))
                except Exception:                             # noqa: BLE001
                    pass
        # 필름 전체 OCR도 덧붙인다 — 모서리 띠 밖(중앙 Scale 등)에 그려지는
        # 것까지 놓치지 않으려는 것이다. 이것만으로는 부족하다는 것이 위 주석.
        chunks.append(pytesseract.image_to_string(img))
        return "\n".join(chunks)
