# -*- coding: utf-8 -*-
r"""TC_WindowsUpdate_04 — Image Processing.

실행: `python run.py tc04`

## 체크리스트 원문 (R-25-774, Checklist 시트 10행)

Precondition
```
1. XIPL 라이선스 적용
   - PureGrid
   - Deep denoising
   - VXCAD CXR
   - Bone Suppression
```

Step Description
```
1. Exposure에서 영상을 촬영한다.
2. Exposure/Veiwer 화면에서 툴의 Image Process 버튼을 누르고, 파라미터를 변경한 후 Process 를 한다.
3. 툴의 XIPL 버튼을 누른다.
4. XIPL Studio 화면에서 Process 버튼을 눌러 processing을 한다.
```

Expected Result
```
1. 영상을 촬영하면 Image Processing 이 성공한다.
2. Image Process 화면에서 Processing 이 성공한다.
   - 변경한 파라미터가 적용되어 프로세싱된다.
   - SBSC 가 적용된 경우 Process 화면에 SBSC 가 체크상태로 표시된다.
   - SBSC 가 적용되지 않은경우 Process 화면에서 SBSC 체크후 Processing을 하면
     영상에 SBSC 가 적용된다. (썸네일에 SBSC 아이콘 표시된다)
3. XIPL 버튼을 누르면 Studio가 오픈되고 선택한 영상이 Studio 화면에 로드된다.
   - 영상에 적용된 파라미터 파일이 로드된다
4. XIPL 에서 파라미터 파일을 변경, 또는 파라미터 값을 변경 후 Processing 성공한다.
```

## 이 TC가 열린 경위 (2026-08-20)

전날까지 이 TC는 `BLOCKED`였다. 촬영 직후
`Error: Image process parameter file does not exist.`가 떴고, XIPL 서버 로그에
`Loading base parameter : Chest PA_normal_H.hs8` → `Parameter file not found`가
기록됐다. 두 가지가 함께 해결되면서 열렸다.

1. **사용자가 파라미터 파일을 `C:\XIPL\PARAMETER` 루트로 옮기고 XIPL.SERVER를
   재시작했다.** 서버가 시작 시점에 파라미터를 잡기 때문에 파일만 옮겨서는
   반영되지 않았다(실측: 재시작 전에는 같은 오류가 계속 났다).
2. **촬영 전에 Step을 등록하도록 바꿨다**(사용자 지시). 인체도에서 Projection
   (`Chest`)과 Step(`PA`)을 골라 등록하면 그 Step에 대응하는 파라미터가 지정된다.
   Step 없이 F2만 누르던 이전 방식에서는 지정될 파라미터가 없었다.

이 둘을 적용한 뒤 촬영에서 **오류 팝업이 사라졌다**(실측 2026-08-20).
그래서 Step 1(촬영 시 Image Processing 성공)은 이제 자동 판정할 수 있다.

## 판정 근거

| Step | 근거 |
|---|---|
| 1 촬영 시 처리 성공 | XIPL 서버 로그에 `Parameter file not found`가 **없고**, 촬영 오류 팝업도 없고, DB `INSTANCE`가 늘어난다 |
| 2 Image Process 파라미터 변경 | 화면의 파라미터 값을 읽어 변경 전/후를 대조. **컨트롤 ID 미실측** — 이 Step은 화면 진입까지 확인하고 값 조작은 MANUAL로 남긴다 |
| 3 XIPL Studio 로드 | `XIPL.STUDIO` 프로세스 창이 뜨는지 + 로그에 로드 기록 |
| 4 Studio 재처리 | **MANUAL** — Studio는 WPF 앱이고 컨트롤을 실측하지 않았다 |

Step 2·4의 컨트롤을 실측하지 않은 상태에서 추측한 ID를 누르면 영상처리
파라미터를 엉뚱하게 바꾼다(`CLAUDE.md` 3절 — 근거 없는 조작 금지). 그래서
**확인 가능한 것만 자동 판정하고 나머지는 무엇을 실측해야 하는지 남긴다.**
"""

import glob
import io as _io
import os
import time

from core import dialogs
from core import workflow as W
from core.result import BLOCKED, FAIL, MANUAL, PASS, SKIP, TCResult

TC_ID = "TC_WindowsUpdate_04"
TC_TITLE = "Image Processing (촬영 시 처리 + Image Process 화면 + XIPL Studio)"

# XIPL 서버 로그에서 처리 실패를 알리는 문구(실측 2026-08-19)
PARAM_MISSING = "Parameter file not found"
PROCESSING_REQUEST = "MSG_REQUEST_PROCESSING"
LOADING_PARAM = "Loading base parameter"


def _xipl_log_path(cfg):
    log_dir = ((cfg.get("xipl") or {}).get("server_log_dir")
               or os.path.join("C:" + os.sep, "XIPL", "SERVER_X64", "log"))
    logs = sorted(glob.glob(os.path.join(log_dir, "*")), key=os.path.getmtime)
    return logs[-1] if logs else None


def _read_xipl_log(path, offset=0):
    """XIPL 서버 로그는 **UTF-16LE**다(HANDOFF 4절 5번). 일반 grep으로 안 읽힌다."""
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as f:
            if offset and 0 < offset <= os.path.getsize(path):
                f.seek(offset)
            raw = f.read()
    except OSError:
        return ""
    return raw.decode("utf-16le", errors="replace")


def run(ui, cfg, evidence_dir=None, do_acquire=True, map_procedure=None,
        projection="Chest", exam_step="PA"):
    r = TCResult(TC_ID, TC_TITLE)
    evidence_dir = evidence_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Evidence", "tc04")
    os.makedirs(evidence_dir, exist_ok=True)
    step = 1

    # --- Step 0: XIPL 라이선스 (Precondition) ---------------------------
    try:
        from core import xipl
        lic = xipl.check_licenses()
        status = (PASS if lic["status"] == "OK" else
                  MANUAL if lic["status"] == xipl.ABOUT_CLOSED else FAIL)
        r.add(step, "XIPL 라이선스 4종 (Precondition)", status,
              expected="PureGrid / Deep denoising / VXCAD CXR / Bone Suppression",
              actual=", ".join(lic.get("found", [])) or "(확인 불가)",
              note=(xipl.ABOUT_OPEN_HINT if status == MANUAL else
                    ("누락: %s" % ", ".join(lic["missing"]) if lic.get("missing")
                     else "체크리스트 Precondition 충족.")))
    except Exception as exc:                              # noqa: BLE001
        r.add(step, "XIPL 라이선스 4종 (Precondition)", MANUAL, actual=str(exc))
    step += 1

    # --- Step 1: 촬영 시 Image Processing 성공 --------------------------
    log_path = _xipl_log_path(cfg)
    log_offset = os.path.getsize(log_path) if log_path and os.path.isfile(log_path) else 0

    if do_acquire:
        try:
            flow = W.open_and_acquire(
                ui, cfg,
                patient_id=(cfg.get("test_data") or {}).get("mwl_patient_id"),
                projection=projection, step=exam_step,
                evidence_dir=evidence_dir, map_procedure_name=map_procedure)
        except Exception as exc:                          # noqa: BLE001
            r.add(step, "촬영 (Step 등록 후 F2)", FAIL, actual=str(exc))
            r.finalize()
            return r
        acq = flow["acquire"] or {}
        added = flow["step"] or {}
        r.add(step, "촬영 Step 등록 (General > %s > %s)" % (projection, exam_step),
              PASS if added.get("ok") else FAIL,
              expected="Step이 등록된다",
              actual="Projection=%s / Step=%r / 항목 %s→%s"
                     % ((added.get("projection") or {}).get("ok"),
                        (added.get("step") or {}).get("label"),
                        added.get("steps_before"), added.get("steps_after")),
              note="**Step 등록이 이 TC의 전제다.** Step이 없으면 영상처리 파라미터가 "
                   "지정되지 않아 촬영 직후 `Image process parameter file does not "
                   "exist`가 뜬다(2026-08-19 실측). 사용자 지시로 인체도에서 "
                   "Projection·Step을 골라 등록한 뒤 촬영한다.")
        step += 1

        r.add(step, "촬영 성공 (DB INSTANCE 증가)",
              PASS if acq.get("acquired") else FAIL,
              expected="INSTANCE 행이 늘어난다",
              actual="INSTANCE %s → %s / %.1f초 / 상태=%r"
                     % (acq.get("instances_before"), acq.get("instances_after"),
                        acq.get("seconds", 0), acq.get("state")),
              note=acq.get("note") or "")
        step += 1

        popups = acq.get("dialogs") or []
        blocking = [d for d in popups if getattr(d, "blocking", False)]
        r.add(step, "촬영 시 Image Processing 성공 — 오류 팝업 없음",
              PASS if not blocking else FAIL,
              expected="촬영 중 오류·경고 팝업 없음",
              actual="; ".join(str(d) for d in popups) or "팝업 없음",
              note="체크리스트 Expected Result 1: \"영상을 촬영하면 Image "
                   "Processing 이 성공한다.\" 팝업을 **분류해서** 본다 — 성공 알림은 "
                   "판정을 바꾸지 않고 오류·경고만 FAIL로 센다(core/dialogs.py).")
        step += 1
    else:
        r.add(step, "촬영", SKIP, note="--no-acquire로 실행되어 기존 영상을 사용한다.")
        step += 1
        acq = {}

    # --- Step 1의 두 번째 근거: XIPL 서버 로그 --------------------------
    new_log = _read_xipl_log(log_path, log_offset)
    missing = new_log.count(PARAM_MISSING)
    requested = new_log.count(PROCESSING_REQUEST)
    loaded = [ln.split(":", 1)[-1].strip()
              for ln in new_log.splitlines() if LOADING_PARAM in ln]
    r.add(step, "XIPL 서버 로그 — 파라미터 로드 성공",
          PASS if (requested and not missing) else
          (FAIL if missing else MANUAL),
          expected="처리 요청이 있고 `%s`가 없다" % PARAM_MISSING,
          actual="처리 요청 %d건 / 파라미터 미발견 %d건 / 로드한 파라미터: %s"
                 % (requested, missing, "; ".join(loaded[-3:]) or "기록 없음"),
          note="XIPL 서버 로그는 **UTF-16LE**라 일반 grep으로 읽히지 않는다"
               "(HANDOFF 4절). 이 로그가 '촬영 시 처리 성공'의 두 번째 근거다 — "
               "팝업이 없어도 로그에 `%s`가 남으면 처리는 실패한 것이다. "
               "2026-08-19에는 파일이 존재하는데도 이 오류가 났고, 파라미터를 "
               "`C:\\XIPL\\PARAMETER` 루트로 옮기고 XIPL.SERVER를 재시작한 뒤 "
               "해소됐다(사용자 조치, 2026-08-20)." % PARAM_MISSING)
    if new_log:
        excerpt = os.path.join(evidence_dir, "xipl_log_excerpt.txt")
        try:
            _io.open(excerpt, "w", encoding="utf-8", newline="\n").write(new_log[:8000])
            r.attach(excerpt)
        except OSError:
            pass
    step += 1

    # --- Viewer 모드로 전환하고 확장 툴 팔레트를 읽는다 -----------------
    # 사용자 안내(2026-08-20): Exposure 화면 우측 상단 최대/최소 버튼으로 Viewer
    # 모드에 들어가면 도구 패널이 나오고, Tools 섹션의 ≡ 를 누르면 전체 툴 팝업이
    # 열린다. 그 팝업에 `Proc.`(Image Process)와 `XIPL`이 있다.
    W.select_first_image(ui)
    in_viewer = W.viewer_mode(ui, cfg)
    palette = W.read_tool_palette(ui, cfg, evidence_dir=evidence_dir, refresh=True)
    r.add(step, "확장 툴 팔레트 판독 (Viewer 모드 > Tools ≡)",
          PASS if palette else FAIL,
          expected="팝업에서 툴 라벨과 위치를 읽는다",
          actual="Viewer 모드=%s / 읽어낸 툴 %d개: %s"
                 % (in_viewer, len(palette), ", ".join(sorted(palette)) or "없음"),
          note="팝업은 약 **2.1초 뒤 스스로 닫힌다**(실측: 0.32s 열림 → 2.42s 닫힘). "
               "그 안에 컨트롤 트리를 열거할 수 없어(한 번에 8.13초) **열린 동안 "
               "캡처만 하고 OCR은 닫힌 뒤에** 한다. "
               "**툴 개수는 라이선스·옵션 설정에 따라 달라진다**(사용자 확인) — "
               "격자를 가정하지 않고 읽힌 것만 다루며, 필요한 툴이 없으면 "
               "'이 환경에 노출되지 않았다'로 보고한다.")
    step += 1

    # --- Step 2: Proc.(Image Process) ------------------------------------
    if "Proc." not in palette:
        r.add(step, "Image Process 화면 진입 (Proc.)", MANUAL,
              expected="팔레트의 Proc. 버튼",
              actual="팔레트에서 Proc.을 찾지 못했다(읽어낸 툴: %s)"
                     % (", ".join(sorted(palette)) or "없음"),
              note="이 환경에 노출되지 않았거나 라벨 판독에 실패했다. 증거 캡처"
                   "(Evidence/tc04)를 확인할 것.")
        step += 1
    else:
        proc = W.click_tool(ui, cfg, "Proc.", evidence_dir=evidence_dir)
        popups = dialogs.clear_blocking(ui, cfg, evidence_dir=evidence_dir)
        r.add(step, "Image Process 화면 진입 (Proc.)",
              PASS if proc.get("ok") else FAIL,
              expected="Proc. 버튼을 눌러 Image Process 화면이 열린다",
              actual="클릭 지점=%s / 처리한 팝업=%s"
                     % (proc.get("point"), [str(d) for d in popups] or "없음"),
              note="체크리스트 Step 2의 'Image Process 버튼'에 해당한다.")
        step += 1

        r.add(step, "Image Process 화면에서 파라미터 변경 후 Process", MANUAL,
              expected="파라미터를 바꿔 Processing이 성공하고 변경값이 반영된다",
              actual="화면 진입까지만 수행",
              note="**이 화면 안의 파라미터 컨트롤은 아직 실측하지 않았다.** 추측한 "
                   "ID를 누르면 영상처리 파라미터를 엉뚱하게 바꾸므로 조작하지 "
                   "않는다(CLAUDE.md 3절). 확정 방법: 이 화면이 열린 상태에서 "
                   "`python run.py ui-probe`로 덤프해 캡처와 대조할 것. "
                   "체크리스트 Expected Result 2의 SBSC 체크 상태 확인도 이 화면 "
                   "소관이다(Setting>Integration>Extra Tool의 31523과는 별개).")
        step += 1
        # 열었으면 닫아 다음 Step에 영향을 주지 않게 한다.
        dialogs.clear_blocking(ui, cfg)

    # --- Step 3: XIPL Studio ---------------------------------------------
    studio_exe = (cfg.get("xipl") or {}).get("studio_exe")
    # 코드 결함 수정(2026-08-21, 사용자 실측 제보): Image Process 창을 열고
    # 닫으면 Viewer가 다시 그려져 팔레트 좌표가 바뀐다(Result_20260821_094303 —
    # 팔레트 25개를 읽었는데도 "XIPL을 찾지 못했다"고 오판했던 원인). 재판독은
    # 이전까지 `else` 분기 안에만 있어서, 판정 자체는 Step 2 진입 전에 캡처한
    # **낡은** 팔레트를 보고 있었다. XIPL 판정 직전에 팔레트를 다시 읽는다 —
    # 실제로는 Studio가 정상 기동한다(사용자 확인, 2026-08-21).
    W.viewer_mode(ui, cfg)
    palette = W.read_tool_palette(ui, cfg, evidence_dir=evidence_dir, refresh=True)
    if "XIPL" not in palette:
        r.add(step, "XIPL 버튼 → Studio 오픈", MANUAL,
              expected="팔레트의 XIPL 버튼",
              actual="재판독한 팔레트에서도 XIPL을 찾지 못했다(읽어낸 툴: %s)"
                     % (", ".join(sorted(palette)) or "없음"),
              note="이 환경에 노출되지 않았거나 라벨 판독에 실패했다. 증거 캡처"
                   "(Evidence/tc04)를 확인할 것.")
        step += 1
    else:
        before_up = _process_running("XIPL.STUDIO")
        xipl_click = W.click_tool(ui, cfg, "XIPL", evidence_dir=evidence_dir)
        time.sleep(5)
        popups = dialogs.clear_blocking(ui, cfg, evidence_dir=evidence_dir)
        after_up = None
        for _ in range(10):
            after_up = _process_running("XIPL.STUDIO")
            if after_up:
                break
            time.sleep(3)
        r.add(step, "XIPL 버튼 → Studio 오픈",
              PASS if after_up else FAIL,
              expected="XIPL.STUDIO 프로세스가 기동한다",
              actual="클릭 지점=%s / 기동 전=%s → 후=%s / 처리한 팝업=%s"
                     % (xipl_click.get("point"), before_up, after_up,
                        [str(d) for d in popups] or "없음"),
              note="체크리스트 Step 3. 실측(2026-08-20): 팔레트의 XIPL을 누르면 "
                   "`XIPL.STUDIO.exe`가 기동한다. 실행 파일=%s"
                   % (studio_exe or "(config 미설정)"))
        step += 1

        r.add(step, "Studio에 선택한 영상·파라미터 파일 로드 확인", MANUAL,
              expected="선택한 영상과 그 영상에 적용된 파라미터 파일이 로드된다",
              actual="Studio 기동까지만 확인",
              note="**Studio는 WPF 앱이라 Win32 컨트롤 열거로 내부를 볼 수 없다** — "
                   "UI Automation이 필요하다. 자매 프로젝트의 `core/xipl.py`가 그 "
                   "패턴을 이미 다루므로 설계는 옮길 수 있고 **컨트롤만 이 환경에서 "
                   "새로 실측하면 된다.**")
        step += 1

        r.add(step, "XIPL Studio에서 파라미터 변경 후 Processing", MANUAL,
              expected="파라미터 파일/값을 바꿔 Processing이 성공한다",
              actual="수행하지 않음",
              note="위 Step이 선행 조건이다(Studio 내부 컨트롤 미실측).")
        step += 1

        # --- 정리: XIPL Studio를 닫는다 --------------------------------
        # **이것을 빼먹으면 뒤 TC가 전부 깨진다.** 실측(2026-08-20): Studio가
        # 떠 있는 동안 VXvue가 **DICOM 전송을 아예 시도하지 않는다** — Bunny
        # 로그에 C-STORE 요청이 0건이고 C-ECHO만 남는다. 제품 하단 상태바의
        # Storage 전송 아이콘도 X로 바뀌는데, 전송 목록은 비어 있어서 원인을
        # 짚기 어렵다(사용자가 이 표시를 먼저 발견했다).
        #
        # 그래서 회귀에서 TC04를 TC05/07/08보다 먼저 돌리면 그 세 개가 전부
        # "수신 확인 안 됨"으로 FAIL했다. Studio를 닫으면 그대로 통과한다
        # (실측: 닫은 뒤 TC05 PASS 4 / FAIL 0).
        closed = _close_studio()
        r.add(step, "시험 후 정리 — XIPL Studio 닫기",
              PASS if closed.get("closed") else MANUAL,
              expected="XIPL.STUDIO 프로세스 종료",
              actual="방법=%s / 종료됨=%s"
                     % (closed.get("how"), closed.get("closed")),
              note="Studio가 남아 있으면 이후 TC의 DICOM 전송이 조용히 막힌다"
                   "(실측 2026-08-20). 창을 먼저 정상 종료 요청하고, 그래도 "
                   "남으면 프로세스를 종료한다 — 어느 방법을 썼는지 남긴다.")

    r.finalize()
    return r


def _close_studio(timeout=10):
    """XIPL Studio를 닫는다. 반환: {"closed": bool, "how": str}

    WPF 앱이라 내부를 조작할 수 없으므로 **창에 닫기 요청(WM_CLOSE)** 을 보내고,
    그래도 남으면 프로세스를 종료한다. 시험 대상 제품(VXvue)이 아니라 시험이
    띄운 보조 앱이므로 강제 종료가 허용되지만, 어느 방법을 썼는지는 남긴다.
    """
    import ctypes
    import subprocess
    if not _process_running("XIPL.STUDIO"):
        return {"closed": True, "how": "이미 떠 있지 않음"}

    u32 = ctypes.windll.user32
    WM_CLOSE = 0x0010
    closed_by = None
    try:
        # 프로세스 id를 찾아 그 최상위 창에 닫기 요청을 보낸다.
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq XIPL.STUDIO.exe",
                              "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=20)
        pids = []
        for line in (out.stdout or "").splitlines():
            parts = [x.strip('" ') for x in line.split('","')]
            if len(parts) >= 2 and parts[1].isdigit():
                pids.append(int(parts[1]))
        if pids:
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                          ctypes.c_void_p)

            def cb(hwnd, _lparam):
                pid = ctypes.c_ulong()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in pids and u32.IsWindowVisible(hwnd):
                    u32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                return True

            u32.EnumWindows(EnumProc(cb), 0)
            closed_by = "창 닫기 요청(WM_CLOSE)"
    except Exception:                                     # noqa: BLE001
        pass

    end = time.time() + timeout
    while time.time() < end:
        if not _process_running("XIPL.STUDIO"):
            return {"closed": True, "how": closed_by or "창 닫기 요청"}
        time.sleep(0.5)

    try:
        subprocess.run(["taskkill", "/F", "/IM", "XIPL.STUDIO.exe"],
                       capture_output=True, text=True, timeout=20)
    except Exception:                                     # noqa: BLE001
        return {"closed": False, "how": "종료 실패"}
    time.sleep(1.5)
    return {"closed": not _process_running("XIPL.STUDIO"),
            "how": "프로세스 강제 종료(창 닫기로는 닫히지 않음)"}


def _process_running(name):
    import subprocess
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq %s.exe" % name],
                             capture_output=True, text=True, timeout=20)
        return ("%s.exe" % name) in (out.stdout or "")
    except Exception:                                     # noqa: BLE001
        return None
