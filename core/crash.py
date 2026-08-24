# -*- coding: utf-8 -*-
r"""VXvue가 시험 도중 실제로 크래시했는지 확인한다.

## 왜 필요한가 (사용자 지시, 2026-08-24)

전체 회귀 도중 어떤 TC를 수행하다 VXvue가 강제종료되면, 그 뒤 TC들도 같은
`ui` 객체를 계속 재사용하는데 지금까지는 그걸 감지해 재기동하는 코드가
없었다. `core/ui.VXvueUi.pid`는 읽을 때마다 살아있는지 다시 확인하지만
(`_alive()`), 죽어 있으면 조용히 `None`을 돌려줄 뿐이다 — 그러면 이후 모든
컨트롤 조회가 그냥 빈 목록이 되고, 각 TC 코드가 그 상황을 예외로 만나 죽거나
(그러면 `core.regression._run_tc()`가 FAIL 하나로 감싼다) "화면을 못 찾음"류의
MANUAL로 조용히 넘어간다 — 어느 쪽이든 **"VXvue가 실제로 죽었다"는 진짜
원인이 리포트에 남지 않고, 그 뒤 TC도 되살리지 않은 채 계속 실패한다.**

## 크래시와 정상 종료를 어떻게 구분하는가 (실측 2026-08-24)

`ui.pid`가 `None`이 됐다는 사실만으로 "크래시"라고 단정하지 않는다 — 사람이
의도적으로 닫았거나 자동화가 정리 목적으로 `taskkill`한 경우도 똑같이
`pid`가 사라진다. **실제 크래시인지는 Windows Error Reporting이 남기는
덤프 파일로 확인**한다 — 기본 위치는 `%LOCALAPPDATA%\CrashDumps\
<프로세스명>.exe.<pid>.dmp`(WER의 LocalDumps 레지스트리 설정을 안 건드린
기본값). **사용자가 언급한 "database 폴더 안의 dmp"는 실측 결과 그 폴더가
아니라 이 표준 Windows 위치였다** — `D:\Database`(`config.json`의
`data_dir`)를 재귀 검색했지만 dmp 파일이 없었고, 대신
`%LOCALAPPDATA%\CrashDumps`에 이 PC에서 실제로 발생했던 `XIPL.SERVER.exe`
크래시 덤프 2건(2026-08-18)이 이미 있는 것을 확인했다 — VXvue가 크래시하면
같은 자리에 `VXvue.exe.<pid>.dmp`로 남을 것이다.

## 사용법

```python
t0 = time.time()
r = mod.run(ui, cfg)
if not ui.pid:
    dumps = crash.find_dumps(ui.process_name, since=t0)
    if dumps:
        ...  # 실제 크래시 확인됨 — dumps[-1]이 가장 최근 덤프
    else:
        ...  # 프로세스가 사라졌지만 덤프는 없음(원인 불명 — 정상 종료 가능성 포함)
```
"""

import glob
import os

CRASH_DUMP_DIR = os.path.expandvars(r"%LOCALAPPDATA%\CrashDumps")


def find_dumps(process_name, since=None):
    """`<process_name>.exe.*.dmp` 덤프 목록(오래된 것부터, 가장 최근이 마지막).

    `since`(epoch 초)를 주면 그 이후 수정된 것만 돌려준다 — 그 전에 이미
    있던 오래된 덤프(다른 원인, 다른 세션)를 이번 크래시로 오인하지 않기
    위함이다.
    """
    pattern = os.path.join(CRASH_DUMP_DIR, "%s.exe.*.dmp" % process_name)
    paths = glob.glob(pattern)
    if since is not None:
        paths = [p for p in paths if os.path.getmtime(p) >= since]
    return sorted(paths, key=os.path.getmtime)
