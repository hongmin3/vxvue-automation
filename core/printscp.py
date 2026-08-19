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
import time
import urllib.request


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
