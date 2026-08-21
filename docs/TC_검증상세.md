# TC 자동화 검증 상세

> 이 문서는 각 TC 자동화 코드(`tests/*.py`)가 **실제로 어떤 Step을 밟고
> 무엇을 Expected Result로 확인하는지**를 코드 기준으로 정리한 명세다.
> 특정 실행 회차의 PASS/FAIL 결과가 아니라 "코드가 무엇을 검증하도록
> 설계되어 있는가"를 다룬다 — 실행 결과 리포트는 `Reports/`에 별도로
> 남는다. **TC 자동화 코드를 추가하거나 Step 구성을 바꿀 때는 이 문서도
> 함께 갱신한다**(작업 규칙, `CLAUDE.md` 참고).

각 표의 "판정"열 기호: **PASS/FAIL** = 자동 판정(둘 중 하나로만 떨어짐,
근거가 명확할 때), **PASS/MANUAL** = 자동으로 확인은 하지만 값이 달라도
결함으로 단정하지 않고 "확인 필요"로만 남기는 항목.

---

## 회귀 러너의 Phase 구성 (`core/regression.py`)

`python run.py run-regression`은 아래 순서로 돌고, **각 Phase도 TC와 같은
형식의 판정 항목으로 리포트에 남는다.** 체크리스트 TC ID가 없는 항목
(`Precondition` / `Baseline_Reset` / `VXvue_License` / `DICOM_Servers`)은
체크리스트 xlsx 사본에서 "자동화 추가 항목"으로 따로 기록된다.

| Phase | 리포트 항목 ID | 내용 | 기본 수행 |
|---|---|---|---|
| 0 | `Precondition` | preflight 9항목 → mwl-ensure → xipl-license | 항상 |
| 1 | `Baseline_Reset` | DB/폴더 baseline 복원 (라이선스·로그는 왕복 보존) | **아니오** (`--reset-baseline`) |
| 2 | `VXvue_License` | Setting > System > License 확인 | 항상 |
| 3 | `DICOM_Servers` | MWL/Storage/Print 등록 확인 + C-ECHO | 항상 |
| 4 | `TC_WindowsUpdate_*` | 구현된 TC 실행, 미구현은 scope 수준 표시 | 항상 |

**Setting Export/Import는 이 회귀에 포함하지 않는다**(사용자 지시, 2026-08-20).
검증 목적이 다르다 — 이 회귀는 Windows Update 후 제품 동작을 보고, 그쪽은 설정
백업·복원 기능 자체의 회귀로 DB를 통째로 되돌린다(실측 1021초, 단일 항목 중
최장). 회귀에 섞으면 뒤 TC의 시작 상태를 바꾸고 실행 시간도 전체를 지배한다.
따로 돌린다: `python run.py setting-export-import [--approve-destructive]`.

**짧은 회귀(`--quick`)** — 촬영을 TC02에서 1회만 하고 뒤 TC는 그 영상을
재사용하며, TC14는 대분류별 첫 소분류만 본다. **확인 범위가 줄어들므로**
`Quick_Mode` 항목과 각 TC의 해당 판정에 무엇을 줄였는지 남긴다. 정식 판정은
전체 회귀로 받는다.

**실행 순서는 TC 번호순이다**(01 → 02 → 03 …, 사용자 지시 2026-08-20). 리포트
순서가 체크리스트 행 순서와 같아져 대조하기 쉽다. 순서가 판정을 바꾸지 않도록
각 TC가 자기 시작 상태를 스스로 정리하고(열린 검사 닫기, Exposure 레이아웃 복귀),
설정을 바꾸는 TC는 끝에서 원래 값으로 되돌린다(TC03의 Interpolation Mode).

## 인체도 Projection·Step 선택 (`core/workflow`)

촬영 TC(02/03/04/05/07/08)가 공통으로 쓴다. 라벨이 컨트롤이 아니라 그림 위
글자이므로 판독이 필요하고, **판독을 신뢰하지 않는 것이 설계의 핵심이다.**

| 단계 | 하는 일 | 근거 |
|---|---|---|
| 1 | 캡처 전에 **커서를 인체도 밖으로** 옮긴다 | 커서가 얹힌 라벨은 색이 바뀐다(사용자 확인 2026-08-20). 치우면 22개가 같은 색으로 그려진다 |
| 2 | **파란 점**을 찾는다 | 점은 배경 밝기와 무관하게 색으로 구분된다. 실측 22개 라벨 = 점 22개 |
| 3 | 점 오른쪽 글자를 **국소 대비**로 읽고 정답지와 유사도 대조 | 전역 밝기 임계값은 밝은 뼈 위 라벨을 놓친다(실측 13/22) |
| 4 | 선택된 라벨은 **파란 글자**로 따로 찾는다 | 선택 시 점은 흰색, 글자는 파란색으로 바뀐다(실측) |
| 5 | 남은 라벨 1개 ↔ 남은 점 1개면 **소거로 확정** | 후보 목록이 완전하고 개수가 같으므로 결정된다. 일대일이 아니면 버린다 |
| 6 | 이미 선택된 부위면 **다시 누르지 않는다** | 같은 항목 재클릭의 제품 동작(유지/해제)을 확정하지 않았다 |
| 7 | 클릭 후 나타난 **Step 목록을 정답지와 대조** | 비슷한 이름 혼동(C/T/L-spine)을 눌러 본 결과로 잡는다 |

Step 정답지는 XIPL 파라미터 파일명에서 얻는다(`{Projection} {Step}_{강도}_H.hs8`,
실측 135개 조합). `Chest → AP/Lat/PA`, `Knee → AP/Lat/Obl`. 화면 OCR이 `Lat`을
`Li`로 읽어도 이 정답지로 교정한다.

판독이 실패하면 **Step 등록이 실패하고, 그러면 촬영·전송·인쇄·Export가 모두
막힌다** — 실측(2026-08-20): `Chest`를 못 읽어 TC04/05/07/08이 연쇄 FAIL했다.
그래서 이 경로는 촬영 TC 전체의 선행 조건이다.

**미구현 TC를 어떻게 다루는가** — 자동화 코드가 없는 TC는 추정 PASS를 내지
않고 `automation_scope.json`의 수준을 그대로 옮긴다: `EXCLUDED`→SKIP,
`MANUAL`→MANUAL, `BLOCKED`→BLOCKED, `PARTIAL`/`FULL 가능성 높음`→MANUAL
(코드가 없으므로 수준만 높아도 수행한 것으로 취급하지 않는다). 판정의
`actual`에 "이번 회귀에서 수행하지 않음"을 명시한다.

---

## Precondition — 실행 전 환경/선행조건 점검

코드: `core/regression._run_precondition()` · 단독: `python run.py preflight`

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1~9 | preflight 9항목: 관리자 권한 / 물리 메모리 / 페이지파일 / 해상도 / DPI / VXvue 실행 파일 / DRF DB 접속 / XIPL 로그 경로 / Bunny 수신 폴더 | 관리자 권한·DPI·실행 파일·DB 접속은 **없으면 아무것도 못 하므로 NG(FAIL)**. 메모리/페이지파일·해상도·경로는 WARN(MANUAL) — 실행을 막지 않는다 | PASS/FAIL 또는 PASS/MANUAL |
| 10 | 시험 Worklist 서버에 **당일 날짜** VXvue 전용 DX 처방을 보장(같은 patient_id의 지난 처방은 삭제하고 재생성) | 처방 1건이 오늘 날짜로 존재해야 한다 | PASS/FAIL |
| 11 | XIPL.SERVER About 창에서 영상처리 라이선스 4종 등록 확인 | 필요 라이선스가 전부 등록돼야 한다. About 창이 닫혀 있으면 판정 불가 → MANUAL(사람이 열어야 함) | PASS/FAIL/MANUAL |

**메모리 부족을 차단 조건에서 뺀 이유**(사용자 지시, 2026-08-19): 이 시험 PC는
상주 프로세스(XIPL.SERVER 약 2.2GB) 때문에 물리 메모리 여유가 항상 기준(3GB)
아래다. 실행 전 추측으로 막는 대신, 실패했을 때 `preflight.memory_pressure()`로
그 시점 메모리를 다시 읽어 판정 `note`에 남긴다 — 판단을 **실패 시점의 실측**으로
옮긴 것이다.

---

## Baseline_Reset — DB/폴더/라이선스 클린 초기화

코드: `core/regression._run_baseline_reset()` + `core/dbreset.py`
실행: `python run.py run-regression --reset-baseline` (**파괴적**)

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | 지금 적용된 `.lic` 파일을 로컬 임시 폴더로 백업(`Optionlicense*.lic`은 **glob으로** 찾는다 — 사양서1 p.7 VP-415가 옵션 최대 16개를 허용하므로 이름을 열거하면 누락된다) | 파일이 1건 이상 백업돼야 한다 | PASS/FAIL |
| 2 | `<data_dir>\log\`을 임시 폴더로 백업 | log 폴더가 없으면 SKIP | PASS/SKIP |
| 3 | `dbreset.restore(confirm=True)` — 뷰어 프로세스를 내리고 **완전히 꺼졌는지 확인한 뒤**(최대 30초) DB를 baseline `.bak`으로 복원. 복원 전 PRERESTORE 안전 백업을 자동으로 뜬다 | 복원 성공. 실패 시 DB를 MULTI_USER로 반드시 되돌린다 | PASS/FAIL |
| 4 | `dbreset.restore_folder(confirm=True)` — `data_dir`을 baseline 폴더로 미러링. `Bak/`(DB 백업 이력)과 `log/`는 제외, DB 파일(`*.mdf/*.ldf`)도 제외(SQL Server 점유 중이라 파일 복사로 다루면 안 되고 Step 3이 담당) | robocopy 종료코드 < 8 (0~7은 성공) | PASS/FAIL |
| 5 | Step 1에서 뜬 `.lic`을 제자리에 다시 덮어쓴다 | 백업한 파일 전부 복원 | PASS/FAIL |
| 6 | Step 2의 로그를 되돌린다 | — | PASS |

**라이선스를 값으로 저장하지 않는 이유**(사용자 지시): 라이선스는 하드웨어 키에
묶여 있어 git·설계 문서·기준 백업 어디에도 값으로 남기지 않는다. 되돌리기
**직전**에 지금 적용된 파일만 떴다가 되돌린 뒤 다시 덮어쓰는 왕복 전용이다.

---

## VXvue_License — VXvue 본체 라이선스 확인

코드: `core/license.py` · 실행: `python run.py vxvue-license`

**XIPL 라이선스(`xipl-license`)와 다른 검증이다.** 그쪽은 XIPL.SERVER About
창의 영상처리 라이선스 4종이고, 이쪽은 VXvue 본체/옵션 라이선스다.

근거: 사양서1 p.7 `VP-415 - Verify License Registration Status` / 사양서2 p.111
`VP-657 - License` / Service Manual p.54 `4.2.5 License 메뉴` / p.43
`3.4 라이선스 등록하기` / 사양서1 p.86 `VP-526 - Obtain Demo Image` / 사양서1
p.94 `VP-528 - Live View` / 사양서2 p.57 `VP-616 - Integrated Image CAD`

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | `<data_dir>\Database\`의 `license.lic`(본체) + `Optionlicense*.lic`(옵션)을 읽는다 | 파일이 1건 이상 존재해야 한다. 키 값은 사내 자산이라 앞 4/뒤 4자만 남기고 마스킹해 기록 | PASS/FAIL |
| 2 | Setting > System > License 화면으로 이동 | 상단 제목이 `System - License`여야 한다 | PASS/FAIL |
| 3 | Hardware Key(Edit 30089) 표시 확인 | 비어 있지 않아야 한다(이 값으로 라이선스를 발급받는다 — Service Manual p.43) | PASS/FAIL |
| 4 | Add(30879) / Change(30881) / Delete(30880) 버튼 존재 확인 | 3개 모두 존재해야 한다. **누르지 않는다** — 라이선스 변경은 복구가 어려운 파괴적 조작 | PASS/FAIL |
| 5 | 라이선스 목록(ListCtrl 31116)의 행 수를 **속성으로** 센다(빈 행은 hidden이므로 `list_rows()`가 정확히 걸러낸다) | 화면 행 수 = 설치된 `.lic` 파일 수 | PASS/FAIL |
| 6 | 각 행을 캡처+OCR해 `Information` 열 문구로 라이선스 종류를 판별한다(`Demo License` / `Computer Aided Detection` / `Live View`) | `config.json`의 `license.required`(기본 Demo/CAD/LiveView)가 전부 표시돼야 한다. 사양서1 p.7 근거: 현재 지원되는 VXvue Option은 CAD와 Live View뿐 | PASS/FAIL |
| 7 | 화면에서 읽은 키를 `.lic` 파일 키와 대조한다. OCR 혼동쌍(1/L/I, 0/O, 5/S, 8/B, 2/Z)을 접어 비교 | 모든 행이 파일 중 하나와 일치. **불일치는 FAIL이 아니라 MANUAL** — OCR은 `1`을 `L`로 읽는 오인식이 있고(실측: `B35C-F1EAG`→`B35C-FLEAG`) 키의 1차 근거는 파일이다 | PASS/MANUAL |
| 8 | `Information` 열이 목록 폭에 맞춰 `...`로 줄여 표시되는지 확인 | 잘린 행이 있으면 그 사실을 MANUAL로 남긴다(실측: `Demo License 2100-08-18(Shima...` — Company Code 뒷부분을 읽을 수 없다) | MANUAL(잘렸을 때만) |
| 9 | Demo License 행의 만료일 판독 | 만료일이 표시돼야 한다. **만료 임박 여부의 PASS/FAIL 기준으로 쓰지 않는다** — 사양서1 p.7: "VXvue / DxWorks do not check the license expiration date." | PASS/MANUAL |

---

## DICOM_Servers — DICOM SCP 등록 확인·구성

코드: `core/dicom_settings.ensure_registered()`

`config.json`의 `dicom.servers_to_register` 각 항목에 대해 반복한다. 세 화면
(DICOM - MWL / Storage / Print)이 등록에 필요한 컨트롤 ID를 공유한다(실측:
Add=30440 / Delete=30441 / Echo=30780 / Name=30090 / AE Title=30092 / IP=30097 /
Port=30098).

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| n | Storage인 경우 먼저 로컬 `Bunny.exe`가 떠 있는지 확인하고 없으면 실행한다(포트 3000이 열려야 Echo가 성립) | Bunny 실행 확인 | (아래 판정에 포함) |
| n | DB(`AE_LIST`)에 그 AE Title+Port가 이미 있는지 확인 → 없으면 화면에서 Add로 등록, 있으면 목록에서 그 행을 선택 | 등록 상태여야 한다 | PASS/FAIL |
| n | Storage인 경우 Burning Option 3종(Annotation 31503 / Information 31504 / Orientation 31505)을 전부 체크하고 Update. 체크박스가 owner-draw라 상태를 못 읽어 **캡처 기반 색 판별**(체크 시 나타나는 황금색 `(223,182,56)`)로 이미 체크된 건 다시 누르지 않는다 | 3종 모두 체크 상태 | (판정 note에 상태 기록) |
| n | Echo(C-ECHO) 버튼을 눌러 로그 영역을 캡처+OCR로 판독 | `succeeded`가 나와야 한다 | PASS/FAIL |

---

## 촬영·전송 공통 인프라 (`core/workflow.py`)

TC02/03/05/07/08은 앞부분(MWL 처방 열기 → 촬영)이 같다. 각 TC가 따로 구현하면
곧 어긋나므로 한 모듈로 모았다. **여기 적힌 컨트롤 ID는 전부 2026-08-19에 이
프로젝트에서 실측한 값**이며, 다른 제품에서 가져온 것이 없다.

| 단계 | 함수 | 확정된 사실 |
|---|---|---|
| 화면 전환 | `goto(ui, name)` | 메인 네비 Tab `31197` 아래 TabItem `8`=Registration `9`=Exposure `10`=Database `11`=Viewer `12`=Print `13`=Setting `14`=Exit. **전환 전에 팝업을 걷어낸다** — 모달이 떠 있으면 클릭이 조용히 무시된다 |
| MWL 조회 | `query_mwl(ui, cfg)` | Registration 탭 `31201`=Scheduled, Search `30689`, 결과 목록 `31119`, 요약 Static `30013`(평문 판독 가능) |
| 열 자동 확장 | `expand_truncated_columns()` | `SysHeader32`의 실제 열 경계를 읽고 목록 전체를 1회 OCR한다. `...`가 검출된 열만 헤더 경계를 우측으로 드래그한다. 실측: Patient ID 열 109px→249px |
| 행 판독 | `row_cell_text()` / `find_row()` | 목록 셀은 owner-draw → 행 rect를 캡처해 OCR. Patient ID가 잘리면 열을 먼저 확장하고 Accession을 보조 키로 교차 확인한다. 둘 다 없으면 첫 행으로 대체하지 않는다 |
| Study 등록 | `start_study()` | Scheduled 탭 Start `30371`. 사양서1 p.37~38 `VP-460`의 Yes/No/Cancel 팝업을 처리하고 기본은 **매핑하지 않는 쪽**을 택한다 |
| 촬영 레이아웃 | `ensure_exposure_mode()` | Viewer Tools 패널(`30403`)이 보이면 복귀 버튼 `30331`을 누른다(Exposure→Viewer는 `30330`). 인체도 `CUIBodypartDlg`가 표시돼야 Step 등록을 시작한다 |
| 촬영 | `acquire(ui, cfg)` | `viewer.demo_exposure_key`(F2). Step 등록 후 미촬영 항목을 선택하고 DB `INSTANCE` 증가로 획득을 확인한다. **획득 뒤에도 늦게 뜨는 팝업을 한 번 더 훑는다** |
| 촬영 상태 | `acquisition_state()` | `31093` `AcquisitionState` — 캡처+OCR. 실측 문구: `Not Exposure mode`(검사 없음) / `Ready`(촬영 준비 완료) |
| 영상 선택 | `select_first_image()` | 선택 전에는 Send가 동작하지 않는다 |
| 전송 | `send(ui, scope)` | Send `30294`(Exposure·Database 공통). 팝업 `All Images 27002` / `Selected 27001` / `Cancel 27000`. 내부적으로 `confirm_scope_popup()`을 호출한다 |
| 확인 팝업만 처리 | `confirm_scope_popup(ui, scope)` | 이미 떠 있는 'Do you want to send/print all images...' 팝업의 범위 버튼만 누른다(`send()`에서 분리, 2026-08-21). Print(`db_button('print')`)·Export(`db_button('export')`) 등 **버튼을 직접 트리거하지 않는 호출부**가 쓴다 — Send와 Print 확인 팝업이 문구만 다르고 버튼 ID는 같다(실측) |
| 검사 종료 | `close_study()` | Database Close `30275` |
| DB 조회 | `database_search()` | Database 목록 `31191`, Search는 Registration과 같은 `30689`. **Close 직후 목록이 자동 갱신되지 않아** 조회하지 않으면 "Database에 없다"는 잘못된 판정이 난다. **한 번으로도 비어 있을 수 있다**(실측 2026-08-21: Close 직후 첫 조회 `0/0` → 몇 분 뒤 재조회 시 `n/n`, 제품 내부 인덱싱 지연으로 보인다) — 결과가 비면 Search를 최대 4회(3초 간격) 재시도한다 |
| 팝업 정리 | `pending_dialogs()` | 문구를 표준 API로 못 읽으면 캡처+OCR(`dialog_message()`). `dismiss_dialog()`로 안 닫히는 창은 제목줄 X(`-4`)로 닫는다 |

Tool 레일(Exposure): `30360` Select · `30284` Rect. · `30390` Zoom · `30338` Pan ·
`30357` CW · `30356` CCW · `30354` R · `30327` L · `30290` Reject · `30435` Retake ·
`30474` Change · `30294` Send

Database 버튼: `30334` New · `30318` Insert · `30298` Edit · `30332` Move Img ·
`30337` Open · `30292` Reject · `30275` Close · `30300` Export · `30315` Import ·
`30373` Stitch · `30294` Send · `30295` Multi-Send · `30293` Print · `30372`
Statistics · `30378` Multi-Study · `30348` QXLink · `30471` Report · `30473` Compare

**Procedure Mapping 자동화는 비활성 상태다**(`ENABLE_PROCEDURE_MAPPING = False`).
이유와 다시 켜기 전 확인 사항은 `core/workflow.map_procedure()` docstring과
`README.md` 4.12절에 있다.

---

## 표 목록을 열 이름·셀 값으로 읽기 (`core/listgrid.py`)

사용자 지시(2026-08-21): *"각 열의 정보가 export 한 정보와 동일하게 나오면 될 것
같은데, 만약 열의 크기가 좁아서 `...`으로 개행이 되는 건 행의 크기를 넓히도록
해줘. 이건 core 함수로 구현해서 어디 탭이든지 사용할 수 있도록 해줘 —
레지스트레이션이나 데이터베이스나 어떤 팝업이든지."*

VXvue의 목록은 행이 `ListItem`이라는 **텍스트 없는 자식 창**이라 셀 값은 캡처+OCR로만
읽을 수 있다. 그런데 열 폭이 좁으면 제품이 값을 `ACC_VX_AUT...`로 잘라 그리고, 그
상태로 OCR하면 잘린 값을 진짜 값으로 착각해 잘못된 FAIL이 난다.

핵심은 목록 헤더가 **표준 `SysHeader32`** 라는 점이다. 실측(Database 목록)에서
`HDM_GETITEMCOUNT`가 14를 돌려주고 열 이름·x 범위를 전부 정확히 읽었다.

```
Column(0, 'Study Key', w=39, x=18..57)       Column(7, 'Acc. No.', w=85, x=618..703)
Column(2, 'Patient ID', w=143, x=174..317)   Column(8, 'Study Description', w=138, ...)
```

| 하는 일 | 방법 | 왜 이렇게 |
|---|---|---|
| 열 식별 | `HDM_GETITEMW` / `HDM_GETITEMRECT` (메시지) | **OCR을 쓰지 않는다** — 헤더 라벨이 잘려 보여도 이름을 아는 데 지장이 없고, 헤더를 미리 넓힐 이유도 없다 |
| 셀 값 읽기 | 열 경계로 잘라 낸 한 칸만 OCR(`--psm 7`) | 행 전체를 한 번에 읽으면 열 구분이 사라진다 |
| 잘린 값 | **헤더 경계선을 마우스로 드래그**해 넓히고, 다시 읽은 뒤 **원래 폭으로 되돌린다** | `HDM_SETITEMW`로 폭 값만 바꾸면 owner-draw 목록이 셀을 다시 안 그릴 수 있다. 드래그는 제품 자신의 재배치 로직을 타므로 반영이 보장된다(사용자 선택) |
| 빈 값 | 판정에 쓸 열이 빈 문자열로 읽히면 그 열도 넓혀 다시 읽는다 | 실측: `Age`(폭 30)는 잘린 표시 없이 그냥 빈 문자열로 읽혔다 — 빈 판독을 믿으면 잘못된 FAIL이 난다 |
| 끝까지 잘린 열 | `_truncated`로 표시하고, `compare_row()`가 **일치로 세지 않고** `partial`로 따로 담는다 | 잘린 값을 완전한 값처럼 판정에 쓰지 않는다 |

넓히는 시점은 **검색이 끝나 목록이 채워진 뒤**이고, 한 번에 한 열씩만 넓힌다 —
여러 열을 동시에 넓히면 오른쪽 열이 화면 밖으로 밀려 못 읽힌다. 폭 복원은 실측으로
확인했다(`폭이 되돌아오지 않은 열: 없음`).

`ListCtrl` + `SysHeader32` 조합이면 화면 종류를 가리지 않는다 — Registration/Database
목록, Import Study 팝업 목록에서 같은 코드로 쓴다.

---

## 실행마다 구분되는 시험 처방 (`core/testdata.py`)

사용자 지적(2026-08-21): *"patient id가 다 너무 똑같아서 실제 import가 잘되었는지
확인이 불가능한데, 날짜 시간 이런 걸 id에 넣는 건 불가능할까? 각 patient 생성할 때
출생일 성별 이런 걸 랜덤으로 설정해서 등록하게 해주는 것도 좋은 것 같아."*

판정의 신뢰도 문제였다. 시험 처방이 고정값(`VXVUE_MWL_DX_01` / `ACC_VX_AUTO_001`)
이라 Database에 같은 Patient ID의 스터디가 수십 건 쌓였고, TC08의 역방향 Import
판정이 "Export한 그 스터디가 들어왔다"가 아니라 **"같은 ID를 가진 어떤 스터디가
있다"** 밖에 확인하지 못했다.

| 필드 | 처리 | 이유 |
|---|---|---|
| `mwl_patient_id` / `mwl_patient_name` / `mwl_accession` / `mwl_sps_id` | 실행 시각 각인(`VXVUE_260821_150157`) | 그 실행의 스터디를 목록에서 유일하게 지목 |
| `mwl_patient_sex` / `mwl_patient_birthdate` | 각인을 시드로 선택 | 열 값이 실제로 그 처방에서 왔는지 구분 |
| `mwl_procedure_id` / `*_description` / `mwl_modality` | **고정** | Procedure Code 매핑(`--map-procedure`)의 대상이다. 매 실행 바뀌면 제품 매핑 표에 항목이 쌓이고 매번 다시 매핑해야 한다 |

성별·생년월일은 **난수가 아니라 각인을 시드로** 뽑는다. 완전 난수면 리포트에 남은
값으로도 같은 조건을 재현할 수 없다. 각인을 시드로 쓰면 ID만 보고 그 실행의
성별·생년월일을 그대로 되짚을 수 있다.

새 값을 뽑는 시점은 **MWL 처방을 만드는 순간 하나뿐**이다(`new_for_mwl()`).
`python run.py mwl-ensure`와 `python run.py tc08`은 서로 다른 프로세스라, 실행마다
새로 뽑으면 tc08이 존재하지 않는 환자를 찾다 실패한다. 그래서 만든 처방을
`Cache/current_testdata.json`에 기록하고 다른 명령은 `load()`로 그것을 읽는다
(`Cache/`는 `.gitignore` 대상 — 환자 식별자가 공개 저장소로 나가지 않는다).

지난 실행의 처방은 `prune_auto_orders()`가 지운다(사용자 지시: *"기존 환자는
삭제하고"*). **`patient_id`가 `VXVUE_`로 시작하는 것만** 지우므로 다른 제품의 시험
처방(`DATA_FLOW_MWL_01` 등 14건)은 건드리지 않는다 — 실측으로 확인했다. VXvue DB의
스터디는 지우지 않는다(그건 `core/dbreset.py`의 백업/복원 담당).

끄려면 `config.json`에 `"test_data": {"unique_per_run": false}`.

---

## Database 조회는 `Clear` 프리셋으로 시작한다

사용자 지시(2026-08-21): *"검색할 때 default를 clear로 바꾸고 search를 누르게 해줘."*
`database_search()`가 조회 전에 프리셋 스플릿 버튼(`30935`)의 드롭다운에서
`Clear`(`30941`)를 고르고 Search(`30689`)를 누른다. `Clear`는 날짜 범위 등 조회
조건을 비워 **전체 범위로 조회**하게 한다 — Import로 들어온 스터디처럼 검사일이
오늘이 아닐 수 있는 건을 날짜 필터가 걸러 버리는 것을 막는다. `Clear`는 결과 목록도
비우므로 **반드시 그 뒤에 Search를 눌러야** 한다.

실측 확정: 이 컨트롤은 `TextSplitButton`이고 자식이 둘이다 — `1`은 라벨(누르면 그
프리셋을 즉시 적용), `2`가 드롭다운 화살표다. 화살표를 누르면 `ItemList`라는 별도
최상위 창이 뜨고 그 안에 `30940`=Default, `30941`=Clear가 있다(각 버튼을 캡처+OCR해
라벨 확정). 처음에 라벨 쪽(`1`)을 눌러 메뉴가 열리지 않고 Default가 적용되는
헛걸음을 했다.

---

## TC_WindowsUpdate_02 — MWL 조회 워크플로우

코드: `tests/tc02_mwl_workflow.py` · 실행: `python run.py tc02`

체크리스트 Step: *Registration-Scheduled에서 MWL 스터디 조회 → 정보 확인 →
오픈·촬영 → Close 후 Database 확인 → Send 후 전송정보 확인.* Expected Result:
*촬영화면·Database·전송정보가 모두 MWL 스터디 정보와 일치한다.*

**정답지는 화면이 아니라 MWL 서버에 HTTP API로 등록한 값**이다. 화면에서 읽은
값으로 기준을 역산하지 않는다.

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 0 | 열려 있는 검사가 있으면 먼저 Close한다 | 검사가 열려 있지 않은 상태에서 시작. 이전 실행이 남긴 상태를 제품 결함으로 보고하지 않기 위한 선행 정리 | PASS/MANUAL |
| 1 | MWL 서버 API에서 시험 처방(`VXVUE_MWL_DX_01`)을 읽어 **정답지**로 삼는다 | 처방 조회 성공. 실패하면 이후 대조가 표시 확인 수준으로만 남는다는 것을 명시 | PASS/MANUAL |
| 2 | Registration > Scheduled에서 Search | 목록에 1건 이상 표시. 요약 Static(`Result: n / n`)이 1차 근거 | PASS/FAIL |
| 3 | 대상 행을 캡처+OCR해 Patient ID / Acc no / Modality / Birth Date를 정답지와 대조 | 전부 일치. **OCR로 확인되지 않은 항목은 FAIL로 단정하지 않는다** — 열 폭에 맞춰 `...`로 줄여 표시되는 값(Patient ID)이 있어 전체를 읽을 수 없다. 그 항목은 Step 8의 DB 대조로 검증 | PASS/MANUAL |
| 4 | 행 선택 → Start → 확인 팝업 처리 | `AcquisitionState`가 `Ready` | PASS/FAIL |
| 5 | F2 데모 촬영 | 영상 1장 이상 획득. 사양서1 p.86 `VP-526` — Demo License 등록이 선행 조건 | PASS/FAIL |
| 6 | 촬영 중 뜬 팝업 판정 | 오류 팝업 없음. 단 **이미 원인을 규명한 환경 문제**(`Image process parameter file does not exist` — XIPL 파라미터 경로 구성)는 MANUAL로 내리고 근거를 남긴다 | FAIL/MANUAL |
| 7 | 영상 선택 후 Exposure 화면에서 Send(All Images) | 전송 범위 팝업 처리 성공. **체크리스트 Step 순서는 Close 뒤지만 Database 목록이 비어 대상을 고를 수 없어 실행 지점을 옮겼다** — 검증 내용은 동일하고 그 차이를 note에 남긴다 | PASS/FAIL |
| 8 | Bunny 로그의 C-STORE Status와 실제 수신 파일을 함께 확인 | Status 0000h + 파일 1건 이상. **로그 문구 하나로 성공을 단정하지 않는다** | PASS/FAIL |
| 9 | 수신 파일의 DICOM 태그를 정답지와 대조 | PatientID / PatientName / AccessionNumber / Modality 일치. 체크리스트 Expected Result 3·4·5의 마지막 고리 | PASS/FAIL |
| 10 | 검사 Close | Database 화면의 Close 실행, 상태가 `Not Exposure mode`로 | PASS/FAIL |
| 11 | DB(`STUDY`+`PATIENT`) 조회로 대조 | PatientId / AccessionNumber / Modality 일치 | PASS/FAIL |
| 12 | Database 화면에 이 검사가 표시되는지 | 표시돼야 한다. `database_search()`가 재시도까지 마쳐도 안 보이면 원인(Operation Manual 3.6 — 완료된 검사만 조회 / Step 미등록 / 재시도 상한을 넘는 인덱싱 지연)과 해제 조건을 note에 적고 MANUAL로 남긴다 — 제품 결함으로 단정하지 않는다. **2026-08-21 재검증에서는 재시도로 해소되어 PASS** | PASS/MANUAL |

2026-08-21 실측: **PASS 13 / FAIL 0 / MANUAL 0** — 위 표의 모든 Step이 자동
판정으로 떨어진다(FULL). 이전까지 Step 12가 MANUAL로 남던 원인은 Step 등록
누락이 아니라 `database_search()`가 한 번만 조회했기 때문이었다(위 공통 인프라
표 참고).

---

## TC_WindowsUpdate_03 — 영상 조작(표시/도구)

코드: `tests/tc03_image_display.py` · 실행: `python run.py tc03`

체크리스트 Expected Result: *선택한 영상이 화면에 display 되고, **delay 없이**
선택한 툴이 영상에 적용된다.*

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | Setting > Display - General의 Interpolation Mode 콤보(`30975`) 값을 읽는다 | 값을 읽을 수 있어야 한다. Test Data의 기본값(`Bicubic`)과 달라도 결함으로 단정하지 않는다 — 앞선 시험이 바꿨을 수 있다 | PASS/FAIL |
| 2 | 다른 값으로 바꾸고 Update → **화면을 다시 읽어** 반영 확인 | 변경 후 표시값이 목표값 | PASS/FAIL |
| 3 | 촬영된 영상을 준비(없으면 MWL 오픈 + 촬영) | 영상 1장 이상 | PASS/FAIL |
| 4~8 | Select / Zoom / Pan / CW / CCW를 적용하고 **영상 표시 영역을 조작 전후로 캡처해 SSIM 비교** | Zoom/Pan/회전은 화면이 변해야 한다(SSIM < 0.999). Select는 그 자체로 표시를 바꾸지 않으므로 화면 변화로 판정하지 않는다. **버튼 클릭만으로 적용을 인정하지 않는 이유**: 비활성 버튼을 눌러도 클릭은 조용히 성공한다 | PASS/FAIL |
| 9 | "delay 없이" 판정 | **판정하지 않는다.** 정량 기준이 사양서·매뉴얼에 없어 임의 기준을 만들면 근거 없는 판정이 된다 — 각 툴의 소요 시간은 측정해 위 Step들의 `actual`에 남긴다 | MANUAL |
| 10 | 영상 2장 이상에서 선택 전환하며 툴 적용 | 영상 2장 이상 필요. 확보하려면 Step이 2개 이상인 Procedure가 있어야 하고 그것은 Procedure Mapping이 선행돼야 한다 | PASS/MANUAL |
| 11 | Interpolation Mode를 **원래 값으로 되돌린다** | 원복 성공. **실패도 반드시 결과에 남긴다** — 조용히 넘기면 다음 시험이 오염된 상태에서 시작한다 | PASS/FAIL |

실측 SSIM(2026-08-19): Select `1.00000`(변화 없음) / Zoom `0.36874` /
Pan `0.67934` / CW `0.11371` / CCW `0.48457` — 툴이 실제로 영상을 바꾼다는 것이
수치로 확인된다.

---

## TC_WindowsUpdate_04 — Image Processing / XIPL

코드: `tests/tc04_image_processing.py` · 실행: `python run.py tc04 --no-env`

2026-08-20 최종 실측: **PASS 8 / FAIL 0 / MANUAL 4**
(`Reports/Result_20260820_121234.*`).

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | XIPL 라이선스 4종 확인 | PureGrid / Deep denoising / VXCAD CXR / Bone Suppression. About 창이 닫혀 있으면 추정하지 않는다 | PASS/MANUAL |
| 2 | Viewer 최대화 해제 → General > Chest > PA Step 등록 | 인체도 표시 + Step 항목 0→1 | PASS/FAIL |
| 3 | F2 데모 촬영 | 대상 환자 `INSTANCE` 증가. 최종 실측 17→18, 18.1초 | PASS/FAIL |
| 4~5 | 촬영 팝업 분류 + XIPL UTF-16LE 로그 | 오류·경고 0건, 처리 요청 존재, `Parameter file not found` 0건, `Chest PA_normal_H.hs8` 로드 | PASS/FAIL/MANUAL |
| 6 | Viewer > Tools ≡ 즉시 캡처 + 다중 OCR | 환경에 실제 노출된 툴만 판독. 최종 실측 27개, `Proc.`/`XIPL` 포함 | PASS/FAIL |
| 7 | `Proc.` 클릭 | `Image Process [HS8]` 진입. 정상 기능 창은 `INTERACTION`으로 분류 | PASS/FAIL |
| 8 | Image Process 파라미터 변경·Process | 내부 컨트롤 미실측 | MANUAL |
| 9 | 팔레트를 새로 판독해 `XIPL` 클릭 | `XIPL.STUDIO.exe` 기동 | PASS/FAIL |
| 10~11 | Studio 영상/파라미터 로드·재처리 | WPF 내부 컨트롤 미실측 | MANUAL |
| 12 | 열린 Study 정리 + Viewer 최대화 해제 | 열린 Study 0개, 다음 TC가 Step 등록 가능한 레이아웃 | PASS/MANUAL |

---

## TC_WindowsUpdate_05 — DICOM 전송

코드: `tests/tc05_dicom_send.py` · 실행: `python run.py tc05`

체크리스트: *Setting-DICOM-General의 Send Dose SR을 Yes로 하고 영상을 선택해
DICOM Send.* Expected Result: *영상 전송이 성공한다 — **Image, DSR***.

TC02와 다른 점: TC02는 "정보 일치"를, 이 TC는 **"전송된 객체의 종류"** 를 본다.

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | Setting > DICOM - General 화면 진입 후 Send Dose SR 항목 확인 | **컨트롤 ID를 실측으로 확정하지 못했다** — 어느 컨트롤이 Send Dose SR인지 모르는 상태에서 누르면 다른 설정을 바꾼다. 사람이 확인해야 한다(확정 방법을 note에 적었다) | MANUAL |
| 2 | MWL 오픈 + 촬영 | 영상 1장 이상 | PASS/FAIL |
| 3 | Send(All Images) | 팝업 처리 성공. All Images를 택하는 이유: Test Data가 `Image, 스냅샷 영상, Dose SR 전송됨`을 기대하므로 검사의 객체 전부를 보내야 한다 | PASS/FAIL |
| 4 | Bunny 로그 Status + 수신 파일 확인 | Status 0000h + 파일 1건 이상 | PASS/FAIL |
| 5 | 수신 객체에 **Image**(`1.2.840.10008.5.1.4.1.1.1.1`) 포함 | 포함돼야 한다 | PASS/FAIL |
| 6 | 수신 객체에 **Dose SR**(`1.2.840.10008.5.1.4.1.1.88.67`) 포함 | 포함되지 않으면 **MANUAL** — 전제 둘이 확정되지 않았다: (1) Send Dose SR이 Yes인지(Step 1이 MANUAL), (2) 가상 제너레이터에서 선량 정보가 생성되는지. 결함으로 단정하지 않는다 | PASS/MANUAL |

---

## TC_WindowsUpdate_07 — DICOM Print

코드: `tests/tc07_dicom_print.py` · 실행: `python run.py tc07`

체크리스트 Expected Result가 *"Print 성공한다"* 뿐이므로, 제품 UI의 Queue만 보면
"제품이 보냈다고 말한 것"을 믿는 것이 된다. **받은 쪽 서버의 필름 목록으로
판정한다.**

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | Print SCP 가동 확인(`GET /api/scp-status`) | `running=true`. Precondition에 해당하며 가동하지 않으면 이후 판정이 무의미 | PASS/FAIL |
| 2 | **VXvue가 보낸 기존 필름 id를 기준선으로 뜬다** | 기존 필름을 지우지 않고 id로 걸러낸다 — 같은 시험 서버를 자매 프로젝트와 공유하므로 전체 목록으로 판정하면 남의 필름을 자기 결과로 착각한다 | PASS |
| 3 | Print 화면의 서버/필름 크기/방향 콤보 판독(`30955`/`30956`/`30957`) | 서버 콤보가 등록된 Print SCP를 가리킨다. 콤보 텍스트가 잘려 표시되므로 접두만 대조 | PASS/MANUAL |
| 4 | **Print Overlay 설정 보장** — `Setting > DICOM - Print Overlay`에 프로파일(6개 항목, 4구역 분배)을 만들고, `Setting > DICOM - Print`의 Overlay 콤보로 그 SCP와 연결 | 두 화면 다 저장돼야 실제 인쇄물에 반영된다(사용자 제보로 실측 확인). 이미 구성돼 있으면 재구성하지 않고 확인만 한다 — 계획에 없는 항목이 섞여 있으면 빼낸다 | PASS/MANUAL |
| 5 | MWL 오픈 + 촬영 | 영상 1장 이상 | PASS/FAIL |
| 6 | Print 실행 — Database `Print`(30293) → 확인 팝업 → 필름 구성 화면의 Print(`30718`) | **두 번의 확인이 필요하다**(실측 2026-08-21). 두 번째 클릭이 빠지면 필름 구성만 되고 아무것도 전송되지 않는다(이전 버전의 거짓양성 원인) | PASS/FAIL |
| 7 | `GET /api/jobs`에서 **Calling AE=VXVUE의 신규 필름**을 기다린다 | 1건 이상 신규 수신. 'Print 성공'의 유일한 객관적 근거 | PASS/FAIL |
| 8 | 수신 필름의 속성(id / film_size / received_at) 기록 | 증적으로 남긴다 | PASS |
| 9 | **수신 필름의 픽셀을 OCR해 Overlay 반영 확인** — `/api/jobs/<id>/preview`(JPEG)를 받아 네 모서리 띠만 잘라 확대해 읽는다 | `E.I.` / `DOI` / `Acc. No` / `Performing Physician`이 필름에 전부 그려져 있다. 제품 UI가 아니라 **받은 쪽 픽셀**로 판정한다 | PASS/FAIL |
| 10 | 시험 후 정리 — 열린 검사 닫기 | 열린 검사 0개. 남으면 다음 시험의 시작 상태가 불분명해진다 | PASS/FAIL |

### Print Overlay 판정에서 실제로 틀렸던 것 (2026-08-21)

세 가지가 겹쳐 "제품은 정상인데 자동화가 FAIL"을 만들었다. 필름을 직접 받아 눈으로
확인해 보니 6개 항목이 전부 정상 인쇄돼 있었다.

| 문제 | 원인 | 고친 방법 |
|---|---|---|
| Step 9에서 `DOI`만 검출, 나머지 3개 누락 | 1318x1600 필름을 통째로 OCR하면 X-ray 픽셀에 둘러싸인 모서리 흰 글씨를 Tesseract가 글자로 보지 않는다(`50 qi E DOI : 2026-08-21 EI. j 1115`만 나왔다) | `core/printscp.preview_ocr_text()`가 **네 모서리 띠(세로 12%)만 잘라 확대**해 psm 6·11 + 임계값 이진화의 합집합으로 읽는다. 띠 크기·psm 조합은 저장된 필름 3장으로 비교 측정해 골랐다 |
| Step 4가 항목이 있는데도 MANUAL | 목록이 폭에 맞춰 라벨을 잘라 그리는데(`Accession Num...`) 코드가 `항목명 in 행텍스트` 방향으로만 비교했다 | `_overlay_row_has()` — **행 텍스트가 항목명의 앞부분인 경우도 인정**한다(4글자 미만 조각은 우연 일치 위험이 있어 거부) |
| 계획에 없는 `Exposure Time`이 Bottom Left에 끼어들어 필름에 `TOI`가 인쇄됨 | 위 오판으로 매번 재추가를 시도했고, OCR 줄 번호와 행 번호를 **인덱스로 맞추던** 로직이 한 칸 밀려 엉뚱한 행을 클릭했다 | `_ocr_lines_with_rows()` — 단어 좌표(`image_to_data`)로 각 줄의 y 중심을 구해 **그 y를 품는 행 rect와 짝짓는다**. 그리고 `_print_overlay_strip_extras()`가 계획 외 항목을 빼낸다 |

Print SCP는 체크리스트 Precondition대로 **다른 PC**에 있다 — Storage와 달리 이
조건은 충족한다.

2026-08-21 재검증: **PASS 7 / FAIL 0 / MANUAL 0**(FULL). 이전 FAIL(Step 6 "120초
안에 신규 필름 미확인")의 진짜 원인은 Database 목록 지연이 아니라 위 Step 5의
두 번째 확인(Film Manager Print 버튼) 누락이었다 — Database 목록 문제는
`database_search()` 재시도로, Print 확인 누락은 `finish_print()` 추가로 각각
해소했다.

---

## TC_WindowsUpdate_08 — Study Export

코드: `tests/tc08_study_export.py` · 실행: `python run.py tc08`

체크리스트 Precondition은 *CD/USB*지만 물리 매체 굽기·삽입은 사람이 해야 한다.
사용자 지시로 **E 드라이브를 기준**으로 수행하고(`config.json > export.dest_dir`),
**E가 없으면 D로 대체하며 그 사실을 판정에 남긴다**(2026-08-21 지시 — "이건
외부 드라이브 export/import를 보는 테스트라서"). 경로를 코드에 박지 않았으므로
실제 USB 드라이브 문자로 바꾸면 그대로 동작한다.

체크리스트 Comment에 **알려진 결함 `#21049`(Win11에서 Study Export 시 에러 발생
하며 Export 안 됨)** 이력이 있다. 이 시험대는 Windows 11이므로 **이 TC는 그
결함의 재발 확인 회귀**다. 2026-08-21 실행에서는 재현되지 않았다.

## Export Manager 내부 자동화 (2026-08-21 신규 실측)

이전 버전은 이 창의 컨트롤을 실측하지 못해 Step 5~9가 전부 MANUAL이었다.
캡처+OCR로 컨트롤을 확정해 전면 자동화했다(`tests/tc08_study_export.py`의
`_run_export_manager()` 등, 상세 근거는 모듈 docstring 참고).

| 조작 | 함수 | 확정된 사실 |
|---|---|---|
| 경로 표시(읽기 전용) | — (`30191` Edit) | `SendMessage(WM_SETTEXT)`로는 **표시만 바뀌고 실제 대상은 안 바뀐다**(실측: 텍스트를 바꿔도 파일은 이전 경로에 생성됨) |
| 드라이브 변경 | `_select_export_drive()` | `31003` 위젯의 드롭다운(owner-draw)에서 원하는 드라이브 문자를 **OCR로 찾아 클릭**해야 실제로 바뀐다. 이미 그 드라이브면 건드리지 않는다(재클릭 방지) |
| 폴더 선택 | `_browse_to_folder()` | Browse(`30680`)가 여는 표준 `SHBrowseForFolder` 트리는 **현재 선택된 드라이브 위치에서 시작**한다 — 드라이브를 먼저 맞추면 대상 폴더가 트리 첫 화면에 보인다. 폴더명을 OCR로 찾아 클릭 후 확인 |
| 형식 선택 | `_format_selected()` + 클릭 | File Format(`30696`=DICOM `30698`=IMG 등)은 **다중 선택 토글**이고 owner-draw라 표준 API로 상태를 못 읽는다. 선택 시 테두리 `(255,255,0)`(노랑), 아니면 `(32,32,32)`(회색) — 픽셀로 판별해 **이미 선택된 것은 다시 누르지 않는다**(다시 누르면 꺼진다) |
| 시작 | `30683`(Start) | 확인 팝업 없이 곧바로 전송 시작 |
| 완료 대기 | `_export_state()` | 'Current State' 라벨과 값 모두 `Static`에 공용 ctrl_id(`20000`)라 위치로 구분(라벨보다 오른쪽) — `Ready → Done` |
| 완료 팝업 | ctrl_id `27000` 단일 버튼 | "Succeed to export. Export Manager will be closed." — 누르면 프로세스 자체가 종료된다. 안 닫으면 다음 실행과 충돌한다 |

**VXvue 자체 Import는 DICOM이 아니라 IMG만 받는다**(Operation Manual 8.14,
p.204: "VXvue에서 생성된 IMG 파일만 가져올 수 있습니다.", 사용자 지적으로
재확인). File Format은 다중 선택이 가능하므로(8.13.1) **DICOM(태그 대조용)과
IMG(Import 전제조건)를 함께 선택**한다 — 실측: 한 번의 Export로 `dcm\*.dcm`과
`S{Series}I{Instance}.img`가 같은 폴더에 함께 생성된다.

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 0 | 대상 드라이브 확인. 설정된 드라이브가 없으면 D로 대체 | 사용 가능한 드라이브 확보. 대체 시 **PASS로 올리지 않고 MANUAL**로 남겨 "외부 매체 대신 내장 드라이브로 대체했다"는 사실을 표시 | PASS/MANUAL/BLOCKED |
| 1 | 대상 폴더 준비, **기존 파일 목록을 먼저 뜬다** | 대상 사용 가능. 기준선이 없으면 이전 산출물을 이번 결과로 착각한다 | PASS/FAIL |
| 2 | MWL 오픈 + 촬영 + **Close(닫힘 확인)** | 영상 획득 후 **검사가 실제로 닫혀야** 한다 — 열린 검사 탭 수가 줄었는지 센다. 닫히지 않으면 스터디가 DB에 커밋되지 않아 이후 Export가 다른 스터디를 대상으로 삼는다 | PASS/FAIL/SKIP |
| 3 | Database에서 **이번 실행의 Patient ID로 대상 행을 지목**(`ListGrid.find_row()`) | 첫 행을 그대로 쓰지 않는다. 못 찾으면 첫 행으로 대체하지 않고 FAIL — 대체하는 순간 "무엇을 검증했는지"를 잃는다 | PASS/FAIL |
| 4 | Export(`30300`, 확인 팝업 처리) → Export Manager 창 확인 | 별도 프로세스 `VX.EXPORT.MANAGER` 창이 열린다. **에러 팝업이 뜨면 #21049 재발 가능성으로 표시** | PASS/FAIL/MANUAL |
| 5 | 위 표대로 드라이브·폴더·형식(DICOM+IMG) 지정 후 Start, 완료까지 대기 | Export Path가 요청한 대상과 일치 + Current State=Done | PASS/FAIL/MANUAL |
| 6 | 대상 폴더의 신규 파일 확인 | 산출물 생성 | PASS/MANUAL |
| 7 | IMG 형식 산출물 확인 | `S{Series}I{Instance}.img` 1개 이상 — 이게 있어야 Step 9(역방향 Import)가 원칙적으로 가능하다 | PASS/MANUAL |
| 8 | 산출물의 DICOM 태그 대조(가장 큰 DICOM 파일 기준) | PatientID 일치. **같은 검사에서 Dose SR(수 KB)도 함께 Export되므로 크기순으로 골라 실제 영상 파일을 본다** — 안 그러면 SR 객체를 잘못 골라 태그가 비어 보일 수 있다(2026-08-21 실측 재현) | PASS/FAIL |
| 9 | 포터블 뷰어 포함 확인 — 대상 폴더 전체에서 `PV.Loader.exe` / `PortView\QXL.PV.exe`를 찾는다 | 산출물에 포함. **실행 여부는 사람이 확인**한다(외부 실행 파일을 자동으로 띄우지 않는다). 파일명에 `qxlink`가 들어가지 않고(실측), 뷰어는 매체에 한 번만 기록되므로 '이번 실행의 신규 파일'에서 찾으면 두 번째 실행부터 못 찾는다 | PASS/MANUAL |
| 10 | **역방향 Import** — `Database > Import`(`30315`) → Location 지정 → 목록 열 값 대조 → Import → 결과 팝업 → 창 닫힘 확인 → Database 재조회 | 아래 "역방향 Import 자동화" 절 참고. `--no-import`로 끄면 MANUAL로 남는다 | PASS/FAIL/MANUAL |
| 11 | **매체 정리** — Export 대상 폴더 안을 비운다 | 사용자 지시(2026-08-21). 남기면 다음 실행의 Import 목록에 이전 스터디가 섞여 판정 근거가 흐려진다. 삭제 범위는 설정된 Export 폴더 안뿐이고, 드라이브 루트이거나 설정과 다른 경로면 아무것도 지우지 않는다. `--keep-export`로 끔 | PASS/MANUAL/SKIP |

2026-08-21 재검증: **PASS 11 / FAIL 0 / MANUAL 0 / SKIP 0 (FULL)**.

### 실측으로 드러난 것 — Database 화면의 Close가 검사를 닫지 않는다

Step 2의 닫힘 확인을 넣자 곧바로 드러났다. `Database > Close`(`30275`)를 눌러도
**열린 검사 탭이 그대로 남았고**, 뒤이은 `close_all_studies()`(Close All 툴
`30274`)에서 비로소 닫혔다 — 리포트에 `열린 탭 1 → 0 (database_close(무효) →
close_all_button)`으로 남는다.

체크리스트 TC02 Step 4가 *"스터디를 Close 하고 Database 에서 스터디 정보를
확인한다"* 이므로 이 버튼의 의미를 확정해야 한다. 지금 확인된 것은 "이 버튼을
눌러도 열린 검사 탭이 줄지 않았다"는 사실뿐이고, **그것이 제품 결함인지, 이
버튼이 원래 다른 대상(예: Database 목록에서 선택한 항목)에 대한 것인지는 문서로
확정하지 못했다** — `사양 확인 필요`로 남긴다. 자동화는 어느 경로로 닫혔는지
`method`에 남기므로 판정이 가려지지 않는다.

## 역방향 Import 자동화 (2026-08-21 신규 실측)

사용자 지시: *"Export 실행부터 산출물 검증, 역방향 Import까지 전부 자동 판정되게."*
이전까지는 "DB에 데이터를 추가하는 조작"이라 고정 MANUAL로 남겨 뒀지만, 이것이
체크리스트 Step 2 자체(*CD/USB에 Export된 스터디를 선택 후 뷰어로 import 한다*)라
지시대로 자동 수행한다. 되돌리기가 필요하면 `core/dbreset.py`의 백업/복원을 쓴다.

**Import Study 창은 제목이 빈 최상위 팝업이다.** 제목("Import Study")을
owner-draw로 그리기 때문에 (1) 메인 윈도우의 자식 트리에 없고 (2) 제목으로 창을
거를 수도 없다. 그래서 `top_windows()`를 훑어 **필요한 컨트롤 ID를 모두 가진
창**으로 확정한다(`W.find_import_dialog()`). 이걸 몰라서 두 번 헛돌았다.

| 컨트롤 | ID | 확정된 사실 |
|---|---|---|
| Location Edit | `30116` | **표시 전용** — `type_text()`가 통하지 않는다(Export Manager 경로 Edit과 같은 성질) |
| Browse `...` | `30515` | 표준 `SHBrowseForFolder`("폴더 찾아보기")를 띄운다 |
| 스터디 목록 | `31118` | Patient Name / Patient ID / Acc. No. / Birth Date / Age / Sex / Study Date Time |
| Import | `30685` | 누르면 범위 확인 팝업(`27002` All Studies / `27001` Selected / `27000` Cancel — Print·Export와 같은 구성) |
| Close | `30467` | |

판정 근거는 셋을 함께 본다.

1. **결과 팝업** — `Info: Succeed to import the studies.` 단, **먼저 뜨는
   `Importing files 1/1 ...` 진행 팝업을 결과로 읽으면 안 된다.** 실제로 그것을
   결과로 읽어 잘못 FAIL이 났다(`Result_20260821_145739`) — 진행 문구는 건너뛰고
   종료 팝업을 기다린다.
2. **목록 각 열의 값이 Export한 DICOM 태그와 일치** — 사용자 지시: *"각 열의
   정보가 export 한 정보와 동일하게 나오면 될 것 같은데."* `core/listgrid.py`가
   담당한다(아래 절).
3. **Database 재조회 건수 증가** — 단, **창이 닫힌 것을 확인한 뒤에만** 이
   근거를 쓴다. 이 창이 모달로 남아 있으면 Close와 조회 클릭이 조용히 무시돼
   "건수 70 → 70"이라는 의미 없는 근거가 리포트에 남는다(실제 사고, 사용자 제보:
   *"지금 import study 창이 켜져 있어서 네가 클릭한 다른 버튼들이 다 먹히지
   않았어"*). `_close_import_dialog()`가 Close를 누른 뒤 **창이 사라진 것을
   확인**하고, 안 닫히면 제목줄 닫기(`-4`)까지 시도한다.

### 폴더 선택 — 트리를 OCR로 읽지 않는다 (`core/shelltree.py`)

Location은 `...`의 폴더 찾아보기 트리에서만 정할 수 있다. 그 트리를 OCR로 읽으면
한글 노드가 `바탕 화면` → `'mvs sa'`로 깨지고 영문조차 `VXvue1 (E:)` →
`'me VXvuel (E)'`로 읽혀, 부분 문자열로 맞추다 **엉뚱한 노드
(`VXvue1.0.11.015(SMZ)`)를 선택하는 사고가 실제로 났다.**

`SysTreeView32`는 표준 컨트롤이므로 `TVM_*` 메시지로 노드 라벨을 정확히 읽고
선택·펼침까지 할 수 있다. 다른 프로세스의 컨트롤이라 문자열 버퍼를 그 프로세스
주소공간에 만들어야 하고(`core/winmsg.RemoteMem`), 셸 트리는 노드를 펼치면 폴더를
**비동기로** 열거하므로 자식이 채워질 때까지 기다린다(`expand_and_wait()`).
이동식 드라이브는 바탕 화면 루트에 바로 보이지만 내장 드라이브는 `내 PC` 아래에
있어, 로케일에 의존하지 않도록 **루트 → 루트의 자식 한 단계**까지 `(X:)`로 끝나는
노드를 찾는다.

### 부수 발견 — `core/dicomlite.py` DICOM 파서 버그 수정 (2026-08-21)

Step 8의 태그 대조가 PatientID/PatientName을 계속 `None`으로 돌려줘 원인을
추적했다. Export된 영상에 포함된 `(0008,2218) Anatomic Region Sequence`가
**길이 미정(0xFFFFFFFF) Item**을 담고 있었는데, 기존 `_parse()`가 이런 Item을
8바이트 고정폭(FFFE류 태그와 같은 모양)으로 건너뛰려 해 VR 필드만큼 위치가
어긋났다 — 그 뒤로 나오는 모든 태그가 잘못된 위치에서 읽혀 (0010,0010)/
(0010,0020)이 조용히 빈 값이 됐다. `_skip_undefined_sequence()`/
`_skip_item_undefined()`를 추가해 길이 미정 Item 내부를 explicit VR 규칙으로
재귀적으로 건너뛰도록 고쳤다(TC02/05/07/08이 공유하는 모듈이라 전부에 이득이
적용된다). 수정 전후로 Bunny 수신 파일(TC02/05/07)에 대해서도 결과가 그대로임을
확인해 회귀가 없음을 검증했다.

---

## TC_WindowsUpdate_13 — Import Patient (txt/csv)

코드: `tests/tc13_import_patient.py` · 실행: `python run.py tc13`
`--with-folder-watch`로 폴더 자동 감지 경로 추가 확인 가능(기본은 끔).

체크리스트 원문 Step: *Setting-Study-Import Patient에서 study list 샘플을
저장한다 → 저장한 파일을 열고 스터디 정보를 입력한다 → Registration-Reserved
에서 Import Patient 버튼으로 파일을 뷰어에 import한다.* Expected Result:
*스터디 목록이 뷰어로 import 성공한다.*

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | Setting > Study - Import Patient 화면에서 **Save Sample** 버튼을 눌러, 지금 화면에 적용된 구분자/컬럼 순서 그대로의 예시 파일을 받는다 | 예시 파일이 실제로 생성되고 헤더 13개 컬럼과 구분자를 읽을 수 있어야 한다 | PASS/FAIL |
| 2 | Step 1에서 받은 헤더·구분자 형식 그대로, 테스트 값을 채운 CSV 파일을 코드가 직접 만든다(값 자체를 하드코딩하지 않고 형식만 재사용) | 테스트 파일이 실제로 만들어져야 한다 | PASS/FAIL |
| 3 | **Browse**(파일 열기 대화상자)로 Step 2 파일을 선택하고 **Refresh**를 눌러 파싱 미리보기를 갱신한다 | 미리보기 그리드에 데이터 행이 1건 표시돼야 한다(그리드 셀 텍스트는 owner-draw라 행 존재 여부까지만 확인 — 값 자체는 Step 5의 DB 대조로 검증) | PASS/FAIL |
| 4 | VXvue를 재기동하고 다시 로그인해 Registration 기본 화면으로 돌아간다(Setting 화면에 깊이 들어간 상태에서는 메인 네비 탭 전환이 먹지 않는 현상이 있어, 재기동이 유일하게 신뢰할 수 있는 복귀 경로) | 재기동 후 로그인 성공 | PASS/FAIL |
| 5 | Registration > **Reserved** 탭으로 이동해 **Import Patient Order** 버튼을 누른다. 뜨는 팝업(Setting 화면과 같은 구조 재사용) 안에서 다시 Browse→파일 선택→Refresh→미리보기 확인 후, 좌측 확인 버튼 → "Import" 확인창에서 **All Patients** 선택 → 완료 팝업 닫기(최대 4회 반복) | Import 실행 후 DB(`ORDER_PATIENT`)에 해당 PatientId 행이 새로 생기고, Patient Name/Acc. No./Study Description이 파일 값과 일치해야 한다 | PASS/FAIL |
| 5(확장) | Registration > Reserved의 검색 필터를 **Default → Clear**로 바꾸고 **Search**를 눌러, 방금 Import된 항목이 실제로 화면에 표시되는지 확인한다(목록 행은 owner-draw라 표준 API로 셀 텍스트를 못 읽어 캡처+OCR로 Study Description 문구를 찾는다) | 목록에 해당 Study Description이 표시돼야 한다 | PASS/FAIL |
| 6 | **TAB 구분자 회귀(기존 결함 #22985)**: Data Delimiter 콤보를 COMMA→TAB으로 바꾸고(응답 없음 감지 시 즉시 중단), Update → Save Sample 재확보 → TAB 구분 테스트 파일로 다시 Sample Test 파싱 미리보기 확인 → **항상 COMMA로 원복**(성공 여부와 무관하게) | TAB 구분자로도 Comma와 동일하게 파싱 미리보기가 표시돼야 한다(#22985 재발 없음). 원복 실패는 FAIL로 남겨 사람이 직접 확인하게 한다 | PASS/FAIL(원복은 항상 확인) |
| 7 | Service Manual 4.6.7절 근거: "Import Patient Order"(수동)와 "Import Patient Information From a Specific Folder"(폴더 자동 감지)는 상호 배타 기능이다. 화면에서 관련 라벨("Target Directory", "Use Import Patient Information From a Specific Folder")의 존재만 확인한다. `--with-folder-watch`를 줬을 때만 실제로 체크박스를 켜고 곧바로 되돌린다 | 라벨이 존재해야 한다(존재 확인=PASS). 실제 On/Off 전환 검증은 옵트인 실행에서만 수행하며 아직 라이브 미검증 경로임을 명시 | PASS/MANUAL |

---

## TC_WindowsUpdate_14 — Setting 전체 화면 표시 확인

코드: `tests/tc14_setting_display.py` · 실행: `python run.py tc14`

이 TC가 검증하는 것은 **"Windows Update 이후에도 각 탭(대분류/소분류)이
여전히 정상적으로 클릭·표시되는가"**다. 기준값과 완전히 같아야 PASS인
정밀 회귀는 이 TC의 목적이 아니다(그건 아래 `TC_Setting_ExportImport`의
책임) — 그래서 "탐색 자체가 깨졌는가"만 FAIL로 판정하고, "옵션 구성이나
값이 기준과 달라졌는가"는 결함으로 단정하지 않고 `확인 필요`(MANUAL)로만
남긴다.

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | Setting 화면으로 진입한다(좌측 메뉴 `ItemWnd` 존재 확인) | 진입 성공 | PASS/FAIL |
| 2 | 대분류를 하나씩 펼쳐 그 안의 소분류를 전부 열어본다. 각 소분류 화면의 제목이 실제로 바뀌는지(평문으로 읽히는 상단 제목 `Static`) 확인 | 열기 실패 0건 — 화면 수만큼 전부 정상적으로 제목이 바뀌어야 한다 | PASS/FAIL |
| 3 | 열린 화면들의 제목이 서로 겹치지 않는지 확인 | 제목 중복 0건(중복은 클릭이 다른 항목에 안 먹었다는 신호) | PASS/FAIL |
| 4 | **(핵심)** 각 화면의 본문 컨트롤을 전수 열거(스크롤 밖도 포함)하고, 페이지를 끝까지 내리며 각 컨트롤이 뷰포트에 최소 한 번 온전히 들어왔는지 기록한다 | 스크롤로도 끝까지 한 번도 온전히 보이지 않은 컨트롤이 0건이어야 한다(잘려서 조작 불가능한 화면이 없어야 함) | PASS/FAIL |
| 5 | 스크롤이 필요한 화면에서 페이지 서명이 반복될 때까지(더 내려갈 곳이 없을 때까지) 내려갔는지 확인 | 페이지 상한(14장)에 걸려 강제 종료된 화면이 0건 | PASS/FAIL |
| 6 | DICOM(MWL/Storage/Print) 화면은 SCP 목록의 **모든 행을 실제로 클릭**해 상세 패널 값을 읽고, DB `AE_LIST`의 실제 등록값(AE Title/IP/Port)과 대조한다 | 화면에 표시된 상세값과 DB 등록값이 전부 일치해야 한다 | PASS/FAIL |
| 7 | 화면별 **옵션 구성(어떤 Edit/콤보/라벨/체크박스가 존재하는지)**과 표시 텍스트를 추출해, 기준(첫 실행 시 저장된 스냅샷)과 대조한다 | 기준과 완전히 같으면 PASS. **구성이나 값이 달라져도 FAIL이 아니라 MANUAL** — 라이선스/연동 상태에 따라 메뉴가 정상적으로 늘어나는 사례가 실제로 있었기 때문에, 차이가 곧 결함이라고 단정하지 않는다 | PASS/MANUAL(FAIL 없음) |
| 8 | 캡처한 페이지들의 화소 균일도로 "내용이 거의 없는 화면"을 참고 정보로 표시한다(오탐이 많아 판정 근거로는 안 씀) | 실행 버튼 하나만 있는 정상 화면(허용 목록)을 제외하고 예상 밖의 빈 화면이 없어야 한다 | PASS/MANUAL(참고용) |
| 9 | 실측으로 확인된 Setting 트리(대분류/소분류 목록·개수)와 구조 서명/외형 서명을 기록한다 | 정보 기록 그 자체가 목적(체크리스트 대조 근거) | PASS |

체크박스/라디오는 owner-draw라 UI에서 on/off를 표준 API로 읽을 수 없다
(`BM_GETCHECK`이 항상 0) — 그래서 이 값은 Step 7의 판정에 넣지 않고,
컨트롤이 존재한다는 사실만 대조한다. 실제 on/off 값 검증은
`python run.py snapshot`(DB 스냅샷)의 책임이다.

---

## TC_Setting_ExportImport — Setting Export / 변경 / Import 복원 회귀

코드: `tests/tc_setting_export_import.py` · 실행:
`python run.py setting-export-import` (`--no-import`로 파괴적 Import
단계를 생략할 수 있다)

Windows Update 체크리스트에는 없는 별도 신규 TC다. **"옵션 값이 기준과
완전히 같아야 PASS"인 정밀 회귀**는 TC14가 아니라 이 TC가 담당한다. 3단
비교(S0→변경→S1→Import→S2)로 설계했다 — 중간 검증(S1≠S0)이 없으면
변경이 한 건도 반영되지 않아도 마지막 대조가 통과해 헛된 PASS가 나기
때문이다.

| Step | 코드가 하는 일 | Expected Result(판정 기준) | 판정 |
|---|---|---|---|
| 1 | 설정 스냅샷 **S0**을 뜬다(DB 설정 테이블 62개 + 설정 파일 해시) | 스냅샷이 정상적으로 만들어져야 한다 | PASS/FAIL |
| 2 | Setting 화면에 진입해 **UI에 실제로 표시되는 값 전체**(Edit/콤보/라벨/체크박스 구성)를 캡처한다(`ui0`) | Setting 진입 성공 | PASS/FAIL |
| 3 | **Export**를 실행해 `.vxs` 파일을 만든다 | 파일이 생성되고, 그 안에 DB 백업(`Data.bak`)이 포함돼 있어야 한다(=Import가 DB 전체 복원이라는 근거) | PASS/FAIL |
| 4 | 대분류를 순회하며 화면마다 **가능한 만큼 다양하게** 값을 바꾼다 — Edit 텍스트 변경, CheckBox/RadioButton 클릭, Registration-Physician에 신규 전문의 추가, Integration-Extra Tool에 Bunny 대상 설정 + S.B.S.C. 체크. 위험한 화면(라이선스, KIOSK 접근 제어, 백업/복원 실행, 장비 설정, DICOM 서버 등록 등)은 제외 목록(`MUTATION_EXCLUDE`)으로 건드리지 않는다 | 최소 1건 이상 변경이 시도돼야 한다 | PASS/FAIL |
| 5 | 설정 스냅샷 **S1**을 뜨고 S0과 비교한다 | **S1이 S0과 달라야 한다** — 이게 없으면 "변경 안 됐는데 통과"가 가능해진다 | PASS/FAIL |
| 6 | Import 실행 직전 DB 안전 백업을 뜬다(`core/dbreset.backup`) | 백업이 실제로 생성돼야 한다(Import 실패 시 복구 수단) | PASS/FAIL |
| 7 | **Import**를 실행한다(`confirm=True` 명시 필요 — 파괴적 조작) | Import가 완료돼야 한다 | PASS/FAIL |
| 8 | Import 후 뷰어를 재기동하고 다시 로그인한다 | 재기동 후 로그인 성공 | PASS/FAIL |
| 9 | 설정 스냅샷 **S2**를 뜨고 S0과 비교한다 | **S2가 S0과 완전히 같아야 한다** — Export 당시 값이 DB에 그대로 복원됐다는 증명 | PASS/FAIL |
| 10 | `.vxs`에 포함되지 않는 머신 단위 설정(`Viewer.xml`: Theme/Language/Generator/AIEngine/Camera 등)의 변화를 별도로 기록한다 | 복원되지 않는 것이 정상(사용자 확인) — 판정에서는 제외하고 참고로만 남긴다 | MANUAL(참고) |
| 11 | Import·재기동 후 Setting 화면을 다시 순회해 **UI 표시값**(`ui2`)을 캡처하고, Step 2의 `ui0`과 비교한다 | **S0에서 캡처한 화면 구성·표시값과 완전히 일치해야 한다.** DB는 정확히 복원돼도 화면이 그 값을 제대로 다시 그리지 못하는 렌더링 결함은 DB 비교(Step 9)만으로 못 잡기 때문에 화면 값도 따로 대조한다 — 여기서는 TC14와 달리 **값이 다르면 FAIL**이다 | PASS/FAIL |

---

## 판정 설계에서 반복되는 원칙 (모든 TC 공통)

1. **첫 실행을 PASS로 위장하지 않는다.** 기준(baseline) 캡처·값이 없는
   최초 실행은 기준을 만들고 그 항목을 MANUAL로 보고한다(TC14 Step 7).
2. **변경이 실제로 반영됐는지 먼저 증명한다.** 중간 상태(S1)를 S0과
   비교해 "변경이 진짜 먹었다"를 확인한 뒤에야 마지막 대조를 판정 근거로
   쓴다(Setting Export/Import Step 5).
3. **판정 근거는 화면 픽셀이 아니라 값(JSON) 또는 DB다.** 테마·폰트가
   바뀌어도 설정 값과 옵션 구성은 동일하다는 전제로, 좌표·크기·색은
   판정에 넣지 않는다.
4. **읽을 수 없는 것은 읽을 수 없다고 남긴다.** 체크박스/라디오 on/off,
   목록 그리드 셀 텍스트는 owner-draw라 표준 Win32 API로 읽을 수
   없다(실측) — 이 경우 "존재 여부"만 UI로 확인하고, 실제 값/상태는
   DB 스냅샷 또는 캡처+OCR로 검증한다.
5. **결함 단정과 확인 필요를 구분한다.** 탐색·클릭 같은 "동작 자체가
   깨졌는가"는 FAIL, "값·구성이 기준과 달라졌는가"는 정밀 회귀 책임
   TC(Setting Export/Import)가 아니면 MANUAL로 낮춘다 — 라이선스·연동
   상태에 따라 메뉴/옵션이 정상적으로 달라지는 사례가 실제로 있었기
   때문이다.
6. **정답지를 화면에서 역산하지 않는다.** "일치한다"를 판정할 때는 외부에
   등록한 값(MWL API 등록값), DB, 수신 파일 태그처럼 **제품 UI 밖의 근거**를
   기준으로 쓴다(TC02). 화면에서 읽은 값으로 기준을 만들면 결함을 정상으로
   인증해 버린다.
7. **보낸 쪽이 아니라 받은 쪽에서 확인한다.** 전송·Print·Export의 성공은
   제품 Queue가 아니라 수신 서버의 파일/필름 목록, Export 산출물의 태그로
   판정한다(TC05/07/08). 제품이 "보냈다"고 말한 것을 그대로 믿지 않는다.
8. **막혔으면 막힌 이유와 해제 조건을 함께 적는다.** BLOCKED/MANUAL로
   내릴 때 "무엇이 없어서 못 했고, 무엇을 갖추면 되는가"를 note에 남긴다 —
   그러지 않으면 다음 사람이 같은 조사를 처음부터 반복한다(TC08 Step 3).
9. **자원 부족을 제품 결함으로 보고하지 않는다.** 뷰어 기동·화면 진입이
   실패하면 그 시점 메모리 여유를 판정 note에 함께 남겨
   (`preflight.memory_pressure()`) 사후에 환경 문제와 구분할 수 있게 한다.
10. **자동화가 바꾼 것은 자동화가 되돌리고, 되돌리기 실패도 남긴다.**
    설정을 바꾸는 TC는 원복을 Step으로 두고(TC03 Interpolation), 실패하면
    조용히 넘기지 않는다 — 다음 시험이 오염된 상태에서 시작한다.
11. **"완전 자동화"는 모든 Step이 PASS/FAIL로만 떨어지는 상태를 뜻한다.**
    `core/result.TCResult.verdict`는 Step 하나라도 MANUAL이면 TC 전체를
    MANUAL로 올린다 — **SKIP도 마찬가지다**(2026-08-21 수정). 이전에는 PASS
    Step만 있고 SKIP이 섞여 있으면 TC가 PASS로 보고됐다(TC14가 실제 사례) —
    SKIP은 "환경상 정상적인 건너뜀"이지 "확인했다"는 뜻이 아니므로, 그 TC를
    완전 자동화로 보고하면 안 된다는 판정 규칙(사용자 확정, 2026-08-20)에
    맞게 고쳤다.
12. **"버튼을 눌렀다"와 "원하는 일이 일어났다"를 같은 것으로 취급하지
    않는다.** 확인 팝업을 분류만 하고 누르지 않았거나(Print/Export가 두 번의
    확인을 요구하는데 한 번만 처리), owner-draw 위젯의 표시 텍스트만 바뀌고
    실제 내부 상태는 그대로였던 사례(Export Manager 경로 Edit)가 있었다
    (2026-08-21, README 4.16절). 조작의 결과물(수신 파일, 실제 대상 경로,
    DB 표시)을 직접 확인해야 판정이 된다.
