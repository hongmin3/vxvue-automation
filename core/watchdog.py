# -*- coding: utf-8 -*-
r"""행(hang) 방지 · 실패 격리 계층.

Bellalun `auto/core/watchdog.py`에서 가져온 계층이다(2026-08-19). VXvue 쪽에는
`ui.drain_dialogs()`처럼 개별 대응만 있었고, **모든 대기에 상한을 두고 실패한
단계를 격리하는 공용 계층**이 없어서 `core/regression.py`와 각 TC 모듈이 같은
try/except를 복사해 쓰고 있었다.

UI 자동화가 멈추는 원인은 대부분 셋 중 하나다.

1. 기대한 화면이 안 떠서 무한 대기
2. 예상 못 한 모달 대화상자가 떠서 이후 조작이 전부 막힘
   — VXvue에서 특히 잦다. Update/저장 뒤 Info 팝업을 닫기 전에는 이후 클릭이
     **조용히 무시된다**(HANDOFF 4절 3번). 실패가 아니라 "아무 일도 안 일어남"
     으로 나타나 원인을 찾기 어렵다.
3. 조작은 됐는데 DB 반영이 늦어 판정이 어긋남

## VXvue에 맞게 더한 것

`guarded()`가 예외를 FAIL로 기록할 때 **그 시점 메모리 여유를 함께 남긴다**
(`preflight.memory_pressure()`). 이 시험 PC는 물리 메모리 여유가 항상 기준
아래인데(사용자 지시로 실행을 막지 않는다) 그 상태에서 뷰어가 멈춘 전례가 있어
(2026-08-18 "Initializing offset refreshing" 무한 대기), 실패가 제품 문제인지
자원 부족인지 리포트만 보고 구분할 수 있어야 한다.

## 고정 sleep 대신 상태 기반 대기

`time.sleep(10)`처럼 "이 정도면 되겠지"로 기다리면 느린 PC에서 깨지고 빠른 PC
에서는 시간을 버린다. 이 모듈의 대기는 전부 **증거가 나타날 때까지 polling +
상한**이다.
"""

import time
import traceback


class StepTimeout(RuntimeError):
    pass


class StepFailed(RuntimeError):
    pass


def wait_until(predicate, timeout=30, poll=0.5, desc="조건"):
    """predicate()가 참을 반환할 때까지 대기. 초과하면 StepTimeout.

    predicate 안에서 예외가 나도(크로스 프로세스 조회가 일시적으로 실패하는
    일이 있다) 대기를 계속하고, 마지막 값/예외를 오류 문구에 남긴다.
    """
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = predicate()
            if last:
                return last
        except Exception as exc:                  # noqa: BLE001
            last = exc
        time.sleep(poll)
    raise StepTimeout("%s 대기 시간 초과 (%ss). 마지막 값=%r" % (desc, timeout, last))


def wait_value(getter, target, timeout=40, poll=1.0, desc="값"):
    """getter()가 target에 도달할 때까지 대기. 초과해도 예외 없이 최종값 반환.

    "도달하지 못했다"를 판정으로 남겨야 하는 경우에 쓴다 — 예외로 던지면
    호출부가 실제값을 리포트에 적을 수 없다.
    """
    end = time.time() + timeout
    val = getter()
    while time.time() < end and val != target:
        time.sleep(poll)
        val = getter()
    return val


def retry(fn, attempts=3, delay=1.0, desc="동작"):
    """일시적 실패를 재시도한다. 마지막 예외를 그대로 올린다."""
    err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:                  # noqa: BLE001
            err = exc
            if i < attempts - 1:
                time.sleep(delay)
    raise StepFailed("%s %d회 실패: %s" % (desc, attempts, err)) from err


class DialogGuard:
    """예기치 않은 모달 대화상자를 걷어내는 가드.

    뜬 팝업의 문구를 증거로 남기고 닫는다. **닫았다는 사실을 삼키지 않는다** —
    닫은 목록을 `caught`에 쌓아 호출부가 판정에 반영할 수 있게 한다. 예상하지
    못한 팝업이 떴다는 것 자체가 결함의 신호일 수 있기 때문이다.

    VXvue의 완료 팝업이 343회 반복해 뜬 실측 사례가 있어(HANDOFF 0.2절),
    반복 상한(`max_rounds`)을 반드시 둔다.
    """

    def __init__(self, ui, allow_titles=(), evidence_dir=None):
        self.ui = ui
        self.allow = set(allow_titles)
        self.evidence_dir = evidence_dir
        self.caught = []

    def sweep(self, max_rounds=5, tag=""):
        """지금 떠 있는 대화상자를 모두 닫고, 닫은 내용을 반환한다.

        VXvue의 커스텀 팝업은 문구를 컨트롤로 노출하지 않는 경우가 있어 캡처를
        함께 남긴다.
        """
        import os
        closed = []
        for _ in range(max_rounds):
            d = self.ui.dialog()
            if not d or d.text in self.allow:
                break
            path = None
            if self.evidence_dir:
                os.makedirs(self.evidence_dir, exist_ok=True)
                path = os.path.join(self.evidence_dir,
                                    "dialog%s_%d.png" % (tag, len(self.caught) + 1))
            msg = self.ui.dismiss_dialog(timeout=1, evidence_path=path)
            if msg is None:
                break
            info = {"title": d.text, "message": msg, "evidence": path}
            closed.append(info)
            self.caught.append(info)
            time.sleep(0.4)
        return closed


def guarded(step_name, result, step_no=0, guard=None, on_error="fail", cfg=None):
    """단계 실행을 격리하는 컨텍스트 매니저.

        with guarded("DICOM 서버 등록", r, 3, guard, cfg=cfg):
            dicom_settings.ensure_registered(ui, cfg, db)

    블록 안에서 예외가 나면 TCResult에 FAIL로 기록하고 삼킨다 — 한 단계의
    실패가 나머지 TC 전체를 중단시키지 않게 하려는 것이다.
    `on_error='raise'`면 다시 올린다(선행 단계가 실패해 뒤가 무의미할 때).

    `cfg`를 주면 실패 note에 그 시점 메모리 여유를 함께 남긴다.
    """
    return _Guarded(step_name, result, step_no, guard, on_error, cfg)


class _Guarded:
    def __init__(self, name, result, step_no, guard, on_error, cfg):
        self.name, self.result, self.step_no = name, result, step_no
        self.guard, self.on_error, self.cfg = guard, on_error, cfg
        self.ok = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        from .result import FAIL
        if exc is None:
            self.ok = True
            if self.guard:
                for d in self.guard.sweep():
                    self.result.add(self.step_no, "%s 중 예상 못 한 팝업 표시"
                                    % self.name, FAIL,
                                    expected="팝업 없음",
                                    actual="%s: %s" % (d["title"], d["message"]),
                                    note="자동화가 닫고 계속 진행했다. 팝업이 뜬 "
                                         "것 자체가 결함 신호일 수 있어 판정에 "
                                         "남긴다.")
            return False

        note = "".join(traceback.format_exception_only(exc_type, exc)).strip()
        if self.cfg is not None:
            from . import preflight as preflight_mod
            note += " | " + preflight_mod.memory_pressure(self.cfg)
        self.result.add(self.step_no, self.name, FAIL,
                        actual="%s: %s" % (exc_type.__name__, exc), note=note)
        if self.guard:
            self.guard.sweep()
        return self.on_error != "raise"
