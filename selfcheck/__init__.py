# -*- coding: utf-8 -*-
r"""회귀를 돌리기 전에 자동화 자신을 검사하는 계층 (사용자 승인, 2026-08-25).

## 왜 `tests/`가 아니라 별도 폴더인가

`auto/tests/`는 **체크리스트 TC 하나 = 파일 하나**이고 파일명의 번호가 TC ID와
맵핑돼야 한다(`CLAUDE.md` 3절). 자동화 자신을 검사하는 코드를 그 안에 두면 그
규칙이 깨지고, `core/regression.IMPLEMENTED`와의 일치 검사도 자기 자신을
TC로 착각한다. 그래서 여기로 분리했다.

## 무엇을 검사하는가

**제품을 조작하지 않는다** — VXvue도, DB도, 시험 서버도 건드리지 않는다.
순수 로직과 저장소 안의 일관성만 본다. 그래서 언제든, 시험 PC가 아닌 곳에서도
돌릴 수 있다.

1. `test_verdict.py` — `TCResult.verdict`의 판정 규칙. 이게 이 자동화에서
   가장 위험한 단일 함수다: 사용자가 확정한 규칙 여러 개(FAIL 우선, PASS 0일
   때의 분기, SKIP도 PASS를 막는다, `blocks_verdict=False` 예외)가 한 프로퍼티에
   모여 있고, 잘못되면 **모든 TC의 판정이 조용히 틀어진다.**
2. `test_report_quality.py` — 리포트 완전성 게이트(`report_quality` /
   `assert_report_readable`)가 미등록 Step·빈 사용자 필드를 실제로 잡는지.
3. `test_crash.py` — `crash.find_dumps()`의 `since` 필터. 이걸 잘못 만들면
   **예전 덤프를 이번 크래시로 오인**해 정상 종료를 크래시로 보고한다.
4. `test_notify.py` — 종료 알림의 판정 합산과 줄바꿈(경로가 잘리지 않는지).
5. `static_checks.py` — 저장소 일관성. TC ID가
   `automation_scope.json` ↔ `core/regression.IMPLEMENTED` ↔ `tests/*.TC_ID`
   세 곳에서 일치하는지 등. 어긋나면 리포트의 TC ID와 실제 실행된 코드가
   달라져 **체크리스트 기록이 엉뚱한 행에 들어간다**(`CLAUDE.md` 3절).

## 어떻게 돌리는가

```bash
python run.py selfcheck
```

정적 검사와 단위테스트를 한 번에 돌리고, 실패가 있으면 종료 코드 2를 낸다.
`unittest`만 쓰므로 새 의존성이 없다. 개별로 돌리려면:

```bash
python -m unittest discover -s selfcheck -t .
```
"""
