> 이 문서는 내부 설계 노트의 **공개용 마스킹 사본**이다. 라이선스 키,
> 하드웨어 키, QA 계정, 시험망 주소, 사용자 계정 경로는 값만 가렸고
> 설계 근거와 실측 내용은 그대로 남겼다.

# VXvue Windows Update 호환성 검증 Checklist 자동화 설계

작성 시각: 2026-08-18. 대상 문서: `Windows Update 호환성 검증 Checklist_VXvue_R-25-774.xlsx`
(TC_WindowsUpdate_01~15, Sheet `Checklist`). 이 문서는 실제 자동화 코드를
만들기 전 단계의 **설계 산출물**이다 — `[QA 작성 규칙] Bellalun Viewer TC
설계·자동화·자체검토 가이드.md` 8절(자동화 설계) 및 `[QA 작성 규칙] VXvue TC
설계 및 자체검토 가이드_Rev1.7.md`의 원칙에 따라, 확인되지 않은 UI 컨트롤
ID·경로·판정 기준은 실제 값처럼 작성하지 않았다. `자동화 수준` 표기는 모두
Bellalun `automation_scope.json`과 동일한 잠정 분류이며, 실제 PoC 실행 전까지
`FULL`로 확정하지 않는다(가이드 8.1절).

## 0. 범위

- 자동화 대상: TC_WindowsUpdate_02 ~ 09, 11 ~ 14 (총 12건)
- **이번 자동화에서 제외**(사용자 지시):
  - `TC_WindowsUpdate_01`(패키지 설치·실행 확인) — 급하지 않음, 수행 불필요
  - `TC_WindowsUpdate_10`(OS User 계정 로그인 후 뷰어 실행) — 직접 수행 필요 TC
  - `TC_WindowsUpdate_15`(모듈 실행, OS Admin/User 계정 모두 확인) — 직접 수행 필요 TC
- 최종 목표: 이번 Windows Update 호환성 자동화를 시작으로 VXvue **기본기능
  Basic Function Checklist**(`(TC) RA16-14B-010_VXvue Basic Function
  Checklist.xlsx`)까지 확장하는 회귀(regression) 자동화 체계 구축. 폴더·리포트
  구조를 처음부터 이 확장을 고려해 설계한다(1절).

## 1. 선례 재사용 매핑

이 PC(`C:\Users\<user>\Documents\자동화`)에는 이미 검증된 3개의 선례가 있다.
VXvue 자동화는 이 선례들의 **설계 원칙**을 재사용하고, 코드는 VXvue 실제 UI가
확인된 뒤 새로 작성한다(다른 제품의 컨트롤 ID를 그대로 가져다 쓰지 않음).

| 선례 | 위치 | 재사용 대상 |
|---|---|---|
| Bellalun Viewer 자동화 | `Bellalun Viewer\auto` | 폴더 구조, 상태 기반 대기, PASS/FAIL 증적 정책, GPU 미탑재 SKIP 규칙, `automation_scope.json` 분류, 리포트(csv/json/html/txt) 포맷, 의존성 최소화 원칙(Win32 ctypes + Pillow + pytesseract + openpyxl만 사용, pywinauto/psutil/pydicom 불필요) |
| Setting 화면 검증 도구 | `Bellalun Viewer\ORG\Setting Export\bellalunSetting.py` | TC_WindowsUpdate_14(Setting 화면 표시) 자동화의 개념적 원형 — 탭 순회 클릭 → 지정 영역 스크린샷 → SSIM 구조적 유사도 비교(임계값 0.99) → CSV 리포트. VXvue는 좌표 캘리브레이션 대신 가능하면 Win32 컨트롤 ID/UI Automation으로 순회하는 방식으로 고도화 검토(3.5절) |
| VX.LIVE.SERVER 데모 설정 자동화 | `VX_LIVE_SERVER_데모모드_자동화\setup_demo.ps1` | TC_WindowsUpdate_12(카메라 연동)의 Precondition 자동 구성 — 데모 이미지셋 23종 검증·보충, 데모 트리거 파일 생성을 이미 무인 실행 가능. 단, 이 PC엔 VX.LIVE.SERVER가 미설치 상태(4.3절) |
| Model Version Checker v2.3 | `모델버전체크자동화\dist\ModelVersionChecker_v2.3` | 리포트 상단 "패키지 정보" 섹션 — `--product "VXvue"` 실행 시 VXvue/XIPL/VX.LIVE.SERVER 등 구성요소 버전을 릴리즈노트와 대조해 TXT/JSON으로 출력. 2절 리포트 헤더에 그대로 결합 |

## 2. 오늘 수행한 사전 조치 — 클린 설치 기준(Baseline) 백업

사용자 요청("지금 설치하고 아무것도 안한 깨끗한 vxVue이니 DB와 DATABASE
폴더를 백업해두자")에 따라 자동화 착수 전 다음을 완료했다. Bellalun의
`core/dbreset.py`(backup_baseline/restore_baseline)와 동일한 사상이며, 향후
회귀 시험 후 클린 상태로 되돌릴 때 이 백업을 기준으로 삼는다.

- SQL Server 인스턴스: `.\CHAMELEON`, DB명 `DRF`(파일: `D:\Database\Database\DRF_dat.mdf` 9MB,
  `DRF_log.mdf` 7MB — 검사 영상 없음, DB 용량 자체가 클린 상태와 일치)
- 네이티브 DB 백업: `BACKUP DATABASE DRF TO DISK =
  'D:\Database\Database\Bak\BASELINE_CleanInstall_20260818_baseline.bak'` 완료
  (기존 정기 백업 로테이션 파일명과 구분되도록 `BASELINE_CleanInstall_` 접두 사용)
- 폴더 백업: `D:\Database` 전체(Configuration/DemoImage/Image/ImageTemp/
  Language/log/Manual/Theme, 총 130MB)를 `D:\Database_Baseline\CleanInstall_20260818`로
  robocopy 미러링. `DRF_dat.mdf`/`DRF_log.mdf`는 SQL Server가 점유 중이라 파일
  복사가 실패했으나(예상된 동작), 대신 위 네이티브 `.bak`이 그 폴더 안에 포함되어
  있어 동일 스냅샷 시점을 대표한다.
- `C:\ProgramData\VXvue\Viewer.xml`(머신별 뷰어 설정)도 같은 백업 폴더의
  `_ProgramData_VXvue\`에 함께 보관.
- 복원 절차와 주의사항은 `D:\Database_Baseline\CleanInstall_20260818\_BASELINE_README.txt`에 기록.
- 참고: SQL Server 백업 이력(`msdb.dbo.backupset`)에는 2026-06-24부터의
  과거 백업 기록이 남아 있었으나 실제 파일은 `Bak` 폴더에 없었다(이력만
  남고 파일은 이미 정리된 상태로 추정) — DB 실 데이터 용량과 Image/ImageTemp
  폴더가 비어 있는 점으로 볼 때 현재 DB 내용 자체는 클린 상태라고 판단했다.
  이 판단이 틀리다면(즉 진짜 초기 설치 시점이 오늘이 아니라면) 알려달라.

향후 회귀 자동화 실행 전 이 백업으로 복원하는 `reset-environment`류 명령을
Bellalun과 동일한 방식(APP_PROCESSES 강제 종료 → `SINGLE_USER WITH ROLLBACK
IMMEDIATE` → `RESTORE ... WITH REPLACE` → `MULTI_USER`)으로 구현 예정이다.
VXvue 쪽 프로세스 목록(Viewer/Launcher/Service 등 강제 종료 대상)은 아직
목록화하지 않았다 — 3.6절 확인 필요 항목 참고.

## 3. 아키텍처 제안

### 3.1 폴더 구조 (Bellalun `auto`와 동일한 뼈대)

```text
VXvue\auto\
├─ README.md
├─ NEXT_TASK.md
├─ config.example.json        # 설치 경로, DB 접속정보, DICOM 서버, 계정 등 (자격증명은 config.json으로 분리, Git 제외)
├─ automation_scope.json      # TC별 FULL/PARTIAL/MANUAL/BLOCKED/EXCLUDED 분류 (작성 완료, 1절 참고)
├─ run.py                     # CLI 진입점 (run-regression, run-tc02 ... list 등)
├─ core/
│  ├─ ui.py                   # Win32 컨트롤 클릭/텍스트 입력 (ctypes + win32api, 물리 마우스/키보드 제어 — Bellalun과 동일 방식 필요 여부는 VXvue UI Framework 확인 후 결정, 3.4절)
│  ├─ db.py                   # DRF DB 조회 (.NET SqlClient 또는 pyodbc — 3.3절에서 방식 결정)
│  ├─ dbreset.py              # 2절 백업/복원
│  ├─ sysinfo.py              # OS/서비스/프로세스/파일버전 조회 (Bellalun 그대로 이식 가능)
│  ├─ preflight.py            # 실행 전 환경 점검 (관리자 권한, DB 접속, DRF 서비스, 해상도/DPI 등)
│  ├─ result.py               # Check/TCResult/리포트 생성 (Bellalun 그대로 이식, env 헤더 확장은 4절)
│  ├─ dicomlite.py            # 필요 시 DICOM 파일 최소 파싱 (Bellalun dicomlite.py 재사용 검토)
│  └─ package_info.py         # ModelVersionChecker_v2.3 호출 래퍼 (4.2절)
├─ tests/
│  ├─ tc02_mwl.py … tc14_setting_display.py
├─ Reports/ Evidence/ Log/ Cache/ Temp/   # Bellalun과 동일하게 Git 제외
```

### 3.2 의존성 정책

Bellalun `auto`가 증명한 대로 **pywinauto/psutil/pydicom 없이** 표준 라이브러리
+ `pywin32`(이미 설치됨) + `Pillow`(설치됨) + `pytesseract`(설치됨) +
`openpyxl`(설치됨)만으로 충분하다. 이 PC에는 이미 4개 패키지가 모두 설치되어
있어 **추가 설치가 필요 없다.** DB 접속은 Bellalun처럼 PowerShell +
.NET `System.Data.SqlClient`를 쓸지, 이미 설치된 `sqlcmd.exe`를 subprocess로
호출할지 3.3절에서 확인 후 결정한다.

### 3.3 DB 접근 방식 확인 필요

VXvue DB는 `.\CHAMELEON` 인스턴스의 `DRF` 단일 데이터베이스로 확인됨(Bellalun의
DATA/ACCOUNT/CONFIGURATION/PROCEDURE 4분리 구조와 다름). Windows 인증
(`Integrated Security=True`)로 접속 가능한지, 자동화 실행 계정이 `.\CHAMELEON`
로그인 권한을 가졌는지는 아직 확인하지 않았다. `sqlcmd.exe -S .\CHAMELEON -E`
로는 이 세션 계정에서 조회 성공을 확인했다(2절).

### 3.4 UI 자동화 방식 — 1차 탐색 완료 (2026-08-18)

VXvue를 실제 실행해 확인한 결과, **Bellalun과 동일하게 `AfxWnd140u` 커스텀
렌더링 컨트롤**을 사용한다(설치 폴더의 `GUI.SKIN.dll`/`GUI.FLEXIBLE.CONTROL.dll`
등으로 볼 때 같은 사내 UI SDK 계열로 추정). 즉 표준 `BM_CLICK` 메시지가 아니라
Bellalun처럼 물리적 `SetCursorPos`+`mouse_event`(또는 `SendInput`) 방식이
필요할 가능성이 높다 — 다만 `GetDlgCtrlID`로 안정적인 컨트롤 ID를 읽는 것
자체는 가능함을 확인했다(아래 로그인 화면 예시).

VXvue 실행 화면은 **Shimadzu 브랜딩 로그인 화면**이었다(제품 실행 파일은
동일하나 OEM 스킨 적용, `Theme\Login.xml` 등과 일치). 부팅 시 디텍터 오프셋
보정("Initializing offset refreshing")이 진행되는 것을 확인했다. 로그인 화면
컨트롤 ID(창 클래스 `#32770`, 자식 컨트롤 전부 `AfxWnd140u`/`Edit`):

| 항목 | Win32 컨트롤 ID | 비고 |
|---|---|---|
| Account 선택 (ComboBox) | 30968 | |
| Password 입력 (Edit) | 30147 | |
| Login 버튼 | 30729 | |
| 화상 키보드 아이콘 | 30391 | 옆의 IconButton, Password 필드 오른쪽 |
| 좌측 하단 종료/전원 아이콘 | 30316 | |

**로그인 계정 정보가 없어 이 이상 진행하지 못했다.** 실제 환자정보·운영 계정을
쓰지 않고 QA 전용 테스트 계정을 써야 한다는 원칙(가이드 8.11절)에 따라, 임의
계정으로 로그인을 시도하지 않고 사용자에게 자동화용 QA 테스트 계정 정보를
요청한다(하단 질문 참고). 계정을 받는 대로 로그인 이후 화면(메인 메뉴,
Setting, Registration 등)의 컨트롤 ID 탐색을 이어간다.

이후 각 TC의 실제 클릭 대상(메뉴 탭, 버튼, 입력창)의 컨트롤 ID를 알아내는
탐색은 물리 마우스/키보드를 점유해 같은 Windows 세션에서 다른 작업이
어려워진다(Bellalun 지침 5절과 동일한 제약).

### 3.4.1 로그인 성공 및 환경 이슈 해결 (2026-08-18)

- 계정 `<QA 계정>`/`<QA 비밀번호>`로 로그인 성공 확인(`Succeeded to login as <QA 계정>.`,
  11:45:04). 메인 화면은 우측 세로 탭 `Registration / Exposure / Database /
  Viewer / Print / Setting / Exit` 구조이며 하단 상태바에 계정명, Exposure
  모드 상태, Dose, 저장공간(%), USB/네트워크 상태, 날짜·시간이 표시된다 —
  이 정보들은 4절 리포트 헤더 및 TC 판정 근거로 재사용 가능하다.
- **로그인 전 겪었던 "뷰어가 제대로 실행되지 않는" 문제의 원인을 규명하고
  해결했다**: 원인은 VXvue 결함이 아니라 **PC 메모리/페이지파일 고갈**이었다.
  물리 메모리 여유 1.74GB, 페이지파일 여유 0.12GB/19.73GB까지 떨어졌던 시점에
  로그인 화면의 "Initializing offset refreshing"(Virtual Detector 0~3 자동
  연결 단계)이 무한 대기했고, 같은 시간대 Windows 이벤트 로그에도 SQL
  Server(MAMMO) "insufficient memory" 오류, 바탕화면 창 관리자(DWM) 재시작,
  `TNetworkControl.exe` 크래시가 함께 발생했다. 사용자가 메모리를 정리한 뒤
  (여유 1.74GB→3.32GB, 페이지파일 0.12GB→5.55GB) 재시도하니 감지기 연결과
  로그인이 정상 완료됐다. **자동화 실행 전 preflight 점검 항목에 "가용
  메모리/페이지파일 여유 공간" 체크를 추가할 것을 제안한다**(`core/preflight.py`
  설계, 6절 항목).
- 참고: 11:08:18에 `<도메인>\<user>` 계정이 시작 메뉴로 재부팅을
  실행한 이벤트가 있었다(자동화가 실행한 것 아님) — 그 재부팅 자체는
  근본 원인이 아니었고(재부팅 후에도 동일 증상 재현), 재부팅 전후 모두
  메모리 고갈이 원인이었다.

### 3.4.2 Setting 화면 구조 확인 (2026-08-18, 3.5절 질문 해소)

Setting 탭 진입 화면을 확인했다. 좌측 메뉴는 Bellalun처럼 평평한 탭 목록이
아니라 **아코디언(대분류 클릭 시 하위 소분류가 펼쳐지는) 트리** 구조다.

- 대분류(펼침 시 순서): **System**(System Info., Product Info., Account,
  Theme, License, Access) / **Registration** / **Display** / **Tool** /
  **Study** / **Procedure** / **Integration** / **DICOM** / **Backup** /
  **Account Default**
- 화면 좌하단에 전체 설정 **Export / Import 버튼**이 있다(TC14와 별개로,
  향후 "설정값 저장/복원" 계열 TC에 재사용 가능한 발견).
- Win32 컨트롤 관점: 좌측 메뉴 항목은 `MenuList`/`ItemList` 안에 `StepItem`
  이라는 이름의 자식 윈도우들로 구현되어 있고, **`GetWindowText`로 항목의
  실제 표시 텍스트(예: "System Info.")를 읽을 수 없었다**(커스텀 owner-draw,
  ID도 펼침 상태에 따라 바뀌는 위치 인덱스일 뿐 항목과 고정 매핑되지 않음).
  즉 **3.5절에서 예상한 대로 좌측 메뉴 트리 탐색 자체는 Win32 ID 매칭이 아니라
  Bellalun `bellalunSetting.py`처럼 화면 좌표 클릭 + OCR/스크린샷 비교
  방식이 필요**하다. 반면 각 소분류 화면 안의 개별 입력 필드·버튼(Institution
  Name Edit, Configure 버튼, Language ComboBox 등)은 로그인 화면처럼 안정적인
  Win32 컨트롤 ID를 가질 가능성이 높다(개별 화면 진입 후 확인 예정).
- 결론(3.5절 갱신): TC14는 **좌표 캘리브레이션이 필요하지만, 이번에 대분류
  10개의 실제 목록과 순서를 확인했으므로 하드코딩이 아니라 문서화된 목록
  기준으로 좌표/OCR 캘리브레이션 스크립트를 만들 수 있다.**

### 3.4.3 Setting 전체 트리 확정 (2026-08-18, 10개 대분류 전부 펼쳐서 확인)

총 53개 소분류(좌측 `StepItem` 컨트롤 총 개수 53과 일치, 교차 검증 완료).

| 대분류 | 소분류 (개수) |
|---|---|
| System (6) | System Info. / Product Info. / Account / Theme / License / Access |
| Registration (4) | General / Unscheduled / Scheduled / Physician |
| Display (7) | General / Information Overlay / Overlay Item / Annotation / LUT / Monitor Correction / Layout |
| Tool (7) | General / Pre-defined Text / Image Tool / Quick Access / Thumbnail / Status Bar / Collimation |
| Study (7) | General / Study Delete / External Save / Rejected List / Rejected Reason / Image Area / **Import Patient**(TC13 대상) |
| Procedure (1) | Procedure Manager |
| Integration (6) | General / Detector / Shock Log / XIPL / Extra Tool / Bucky |
| DICOM (9) | General / Queue / MWL / MPPS / Storage / Storage Commitment / Print / Print Overlay / Tag Mapping |
| Backup (3) | **Backup** / Clean / **Restore** |
| Account Default (3) | Image Tool / Quick Access / Thumbnail |

중요 발견 2건:

1. **Integration에 "Camera" 소분류가 없다.** 체크리스트 TC_WindowsUpdate_12는
   "Setting-Integration-Camera-Step Analysis"를 언급하는데, 현재 이 PC는
   VX.LIVE.SERVER 미설치·Live View 라이선스 미적용 상태라 Camera 항목 자체가
   메뉴에 나타나지 않는 것으로 보인다(조건부 표시 추정, 확정은 아님). TC12는
   여전히 BLOCKED 상태 유지 — VX.LIVE.SERVER 설치가 선행되어야 이 메뉴가
   나타나는지까지 확인 필요.
2. **Setting > Backup > Backup 화면 확인 결과, 이 기능은 "클린 설치 기준
   전체 백업"이 아니라 Patient/Study 아카이브 기능으로 보인다.** 화면 구성이
   Name/ID 컬럼을 가진 목록 + `Location: E:\`(외장 드라이브 추정) + `Refresh`/
   `Archive` 버튼이며, 지금은 목록이 비어 있다(검사 데이터가 없는 클린 상태와
   일치). 즉 DB 전체나 `D:\Database` 폴더 자체의 스냅샷이 아니라 **개별
   Study를 외부 위치로 내보내는 기능에 가깝다** — 2절의 SQL `BACKUP DATABASE`
   + 폴더 미러링 방식이 "클린 설치 기준 백업" 목적에는 여전히 더 적합하다.
   `Restore`/`Clean` 화면까지는 이번에 확인하지 않았다(다음 탐색에서 필요 시
   확인).

### 3.4.5 DICOM > Storage(Bunny) 등록 및 Echo 검증 완료 (2026-08-18)

TC05 검증 서버를 QXLink 대신 Bunny로 대체하라는 사용자 지시에 따라 진행했다.
앞서 `<시험 PC>:3000` 연결 테스트가 실패했던 이유는 **그 IP가 다른 원격
서버가 아니라 바로 이 VXvue 시험 PC 자신의 IP였고(`ipconfig` 확인,
`<시험 PC 호스트명>`, <시험 PC>/16), 단지 Bunny.exe가 아직 실행되지 않은
상태였기 때문**이었다.

- `C:\Program Files (x86)\Bunny\Bunny.exe`가 이미 이 PC에 설치되어 있음을
  확인. 사용자 지시대로 직접 실행(작업 디렉터리를 설치 폴더로 지정, Bellalun
  README 5절 규칙과 동일)했다.
- Bunny 실행 후 좌측 메뉴는 `Storage Server`(기본 선택) / `Work List Server`
  / `Print Server` / `Network Monitor` / `Setting` / `Convert`. `Setting`
  화면에서 `Network > Local Port = 3000`(기본값)을 확인 — 별도 "활성화"
  토글은 없고 앱 실행 자체로 Storage Server가 포트 3000에서 수신 대기
  상태가 됨을 TCP 연결 테스트로 확인했다.
- VXvue Setting > DICOM > Storage에서 `Add` → Name `BUNNY_TEST` / AE Title
  `Bunny` / IP `<시험 PC>` / Port `3000`(Bellalun DICOM 설정 규칙과 100%
  동일하게 맞춤) → `Update` → Info 팝업 OK → `Echo` → `Connect succeeded.`
  ~ `Verification succeeded.` ~ `Closing connection.` 전 단계 성공.
  **TC05의 Storage(Bunny) 연동 Precondition 충족·검증 완료.**
- 참고: Storage 화면에는 `QXLink Server`(No/[선택]) 옵션과 연동 계정
  입력란이 있다 — 체크리스트의 "QXLink로 전송 확인"이 이 옵션과 관련된
  것으로 보이나 이번에는 Bunny 대체 지시에 따라 `No`(기본값) 상태 그대로
  두었다.
- **UI 함정 추가**: Storage 화면은 Options 섹션이 길어 `Echo` 버튼이 화면
  스크롤 없이는 안 보인다. 화면 오른쪽 끝의 얇은 스크롤바를 찾아 클릭/드래그로
  페이지를 내려야 했다 — 화면별로 스크롤이 필요한 경우가 있으므로 자동화
  코드에서는 좌표 고정 대신 대상 컨트롤을 찾을 때까지 스크롤하는 로직이
  필요하다.
- **TC05 판정 근거 확보 방법(Bunny 측)**: `C:\Program Files (x86)\Bunny\Log\
  <YYYYMMDD>_<발신 AE Title>.txt`(오늘은 `20260818_VXVUE.txt`)에 Associate/
  C-ECHO/C-STORE 요청·응답이 시간순으로 기록되고, 실제 수신 영상은
  `C:\Program Files (x86)\Bunny\Receive\`에 저장된다. VXvue는 등록된 SCP를
  주기적으로 자동 C-ECHO 하는 것으로 확인됨(약 5분 간격 로그 확인). TC05
  자동 판정은 Send 전후 `Receive` 폴더 파일 목록 diff + 로그의 `C-STORE ...
  Status: 0000h` 확인 방식으로 설계한다.

### 3.4.6 DICOM > Print 서버 등록 및 Echo 검증 완료 (2026-08-18)

TC_WindowsUpdate_07의 Precondition을 동일한 방식으로 구성했다. Print 화면은
MWL/Storage보다 필드가 많다(Type=DICOM, LUT, Overlay, Print Layout, Printer
Format(Size/Orientation/Magnification Type/Medium Type/Priority/Trim/Min
Density/Max Density 등) — Print 항목은 SCP 등록 후 기본값이 자동 채워졌다
(14INX17IN/PORTRAIT/BILINEAR/BLUE FILM/MED/NO/50/400).

- `Add` → Name/AE Title `PRINT_SCP`, IP `<시험 서버>`, Port `11113` 입력 →
  `Update` → Info 팝업("DICOM - Print Update successfully.") OK로 닫음 →
  `Echo` → `Connect succeeded.` ~ `Verification succeeded.` ~ `Closing
  connection.` 전 단계 성공. **TC07의 Print 연동 Precondition 충족·검증
  완료.**
- MWL과 마찬가지로 Update 후 Info 모달이 뜨는 패턴이 Print에도 동일하게
  적용됨을 재확인(3.4.4절 공통 헬퍼화 필요성 재확인).

### 3.4.7 Study > Import Patient 화면 확인 (TC13, 2026-08-18)

- 화면 구성: Input Format(Data 구분자=COMMA(,)/TAB 등 선택, Use Header, Sex
  Format(M/F/O 매핑), Date Format(YYYY/MM/DD), Age Type(Y), Language) +
  Column Mapping(Use 체크박스 + Item 순서: Patient ID/Patient Name/Birth
  Date/Age/Sex/Patient Comm.../Acc. No./Procedure Code/Study Descript...
  /Referring Phys...(스크롤 더 있음), Move Up/Down/Add Blank/Delete Blank로
  순서·구성 편집 가능) + Sample Test(File 경로 지정 → `...`으로 찾아보기 →
  `Refresh`로 파싱 미리보기 그리드 표시).
- 기존 결함 #22985(Tab 구분자 실패)와 직접 관련된 화면이다. 현재 Data 구분자
  기본값이 `COMMA(,)`로 설정되어 있음을 확인(결함 재현 시 이 값을 TAB으로
  바꿔 비교 필요).
- TC13 자동화 설계: (1) 헤더+구분자 규칙에 맞는 샘플 csv/txt 생성 (2) File
  경로 입력 후 Refresh로 파싱 결과 그리드 텍스트를 읽어 원본과 대조 (3) 실제
  Registration-Reserved에서 Import 버튼으로 가져와 DB 반영까지 확인 — 장비
  의존이 없어 Full 자동화 유력(automation_scope.json 기존 판단 유지).

### 3.4.8 Integration > XIPL, GPU 확인, 공유 XIPL 설치 확인 (2026-08-18)

- Setting > Integration > XIPL 화면: 감지기별(0~3, 전부 Virtual) Parameter
  Path가 전부 `C:\XIPL\PARAMETER`로 설정되어 있음을 확인. Grid Suppression
  Unit Type(inch/cm), Line per Unit Type 옵션도 있으나 현재 비활성.
- **`C:\XIPL\PARAMETER`에 Bellalun 자동화가 쓰는 것과 동일한 이름의 테스트
  픽스처가 이미 존재한다**: `TEST_2D_A.pim`, `TEST_2D_B.pim`,
  `TEST_2D_FLOW.pim`, `TEST_3D_FLOW.xtp`, `TEST_QC_2D.pim`,
  `TEST_QC_3D.eap`, `TEST_XIPL_SAVED.pim`. 즉 **이 PC의 XIPL Studio/Server는
  Bellalun과 VXvue가 공유하는 단일 설치**다. VXvue TC04/06용 테스트
  Parameter 파일은 이 기존 Bellalun 픽스처를 건드리지 않도록 별도 이름
  (예: `TEST_2D_FLOW_VXVUE.pim`)으로 복사·생성해야 한다.
- `C:\XIPL\SERVER_X64\log\<YYYY_MM_DD>.log` 경로 존재 확인(사용자 제공 경로와
  일치). TC06의 `PureGrid.Apply="0"` 판정에 사용할 예정.
- **GPU 확인 완료**: `Get-CimInstance Win32_VideoController` 결과 `Intel(R)
  Iris(R) Xe Graphics`(내장 GPU)와 `Mirage Driver`(가상 디스플레이 드라이버)
  뿐, 별도 CUDA 지원 GPU 없음. 사용자가 지시한 "CPU-only PC" 전제가 실측으로
  확인됨 — TC11은 Bellalun의 GPU 미탑재 정책(3절)과 동일하게 결과물 생성
  검증만 SKIP하고 나머지(라이선스 적용, Serialization 시작, UI 흐름)는
  자동화 대상으로 유지한다. `SERVER_X64` 폴더에 cuBLAS/cuDNN 등 CUDA 런타임
  DLL이 포함돼 있으나 이는 패키지에 기본 포함된 것일 뿐 실제 GPU 유무와는
  무관함을 확인.

### 3.4.9 Integration > Extra Tool 화면 확인 (TC06, 2026-08-18)

- `Use extra tool` 체크박스(현재 해제) + 단일 대상 AE Title/IP/Port(현재
  127.0.0.1:0, 미설정) + Options(LUT/Modality/DAP Unit/Software
  Collimation=Cut/Burning Option/Transfer Syntax/Compression/Image bits).
  MWL/Print/Storage와 달리 **다중 SCP 목록이 아니라 단일 대상**이다.
- 체크리스트가 언급한 "Remove SBSC" 옵션은 이 화면(스크롤 전체 확인)에서
  보이지 않았다 — `Use extra tool`을 켜야 추가 필드가 나타나는지, 다른
  화면(General?)에 있는지 확인 필요(`추가 사양 확인 필요`로 표시).

### 3.4.10 Display > General 화면 확인 (TC03, 2026-08-18)

- `Interpolation Mode` 드롭다운 확인 — 현재값 `Bicubic`(체크리스트 Test
  Data의 `*default(Bicubic)`와 일치). 같은 화면에 Screen Lock(10~60분),
  Monitor LUT(ScreenLUT), Window Level Option(Speed·Left/Right/Up/Down
  W1/W2 증감 매핑), Drawing Annotation 옵션도 함께 있다.
- TC03 Step1(Interpolation Mode 변경)의 정확한 컨트롤 위치 확보. Step2/3
  (Zoom/Select/Pan/Rotation Tool 적용, 다중 영상 전환)은 Setting 화면이
  아니라 실제 촬영/뷰어 화면에서 확인해야 하므로 다음 탐색 대상.

### 3.4.11 Registration(MWL 조회) 실제 검색 성공 (TC02, 2026-08-18)

MWL_SCP 등록 후 Registration > Scheduled 탭에서 `Search`를 눌러본 결과, 오늘
날짜(2026-08-18) 필터로 **실제 예약 검사 1건이 조회됐다**.

| Patient ID | Patient Name | Sex | Age | Birth Date | Acc. No. | Study Description | Scheduled Date/Time | Modality |
|---|---|---|---|---|---|---|---|---|
| DATA_FLOW...(잘림, `DATA_FLOW_MWL_01`로 추정) | AUTO MWL | F | 46Y | 1980-01-01 | ACC_AUTO_001 | Mammography | 2026-08-18 09:00:00 | MG |

- Patient ID가 `DATA_FLOW_MWL_01`로 추정되는 점은 **Bellalun 자동화가 쓰는
  것과 정확히 같은 명명 규칙**이다(Bellalun MWL 지침 4절 "DATA_FLOW_MWL_01"
  참고). 즉 이 공용 MWL_SCP 시험 서버에는 이미 자동화 전용 비식별 테스트
  환자가 상시 등록되어 있고(매일 자동 갱신되는 것으로 추정, 오늘 날짜로
  조회됨), 실명·실제 환자정보가 아님을 확인했다.
- **다만 Modality가 `MG`(Mammography)로, VXvue(방사선 촬영기) 대상 워크플로우와
  맞지 않을 수 있다.** 이 서버가 여러 제품(Bellalun/VXvue/VXvue Mammo 등)이
  공유하는 시험 서버라, 이 특정 항목은 VXvue Mammo용으로 등록된 것일 가능성이
  있다. **VXvue TC02 자동화에 이 기존 항목을 그대로 재사용해도 되는지, 아니면
  VXvue(비Mammo) 전용 Modality(예: DX)로 별도 항목이 필요한지 확인이
  필요하다** — 임의로 이 항목을 촬영·전송 대상으로 사용하지 않고 사용자
  확인을 기다린다.

### 진행 현황 요약 (2026-08-18 기준)

| 항목 | 상태 |
|---|---|
| VXvue 로그인(<QA 계정>/<QA 비밀번호>) | 완료 |
| 뷰어 실행 안 되던 문제 원인·해결 | 완료 (메모리 고갈) |
| Setting 전체 메뉴 트리(10대분류/53소분류) | 완료 |
| MWL_SCP 등록+Echo 검증 (TC02) | 완료 |
| PRINT_SCP 등록+Echo 검증 (TC07) | 완료 |
| Storage(Bunny) 등록+Echo 검증 (TC05) | 완료 — Bunny 직접 실행, 로그/Receive 폴더 위치 확인 |
| GPU 미탑재 실측 확인 (TC11) | 완료 |
| XIPL 공유 설치 및 기존 Bellalun 픽스처 확인 | 완료 |
| Study > Import Patient 화면 확인 (TC13) | 완료 |
| Integration > Extra Tool 화면 확인 (TC06) | 완료 — Remove SBSC 위치는 미확인 |
| Display > General 화면 확인 (TC03 Step1) | 완료 |
| TC02 Registration 화면 (MWL 조회) | 미착수 |
| TC03 Step2/3 (뷰어 화면 Tool 적용) | 미착수 |
| TC04 XIPL Studio 실제 Processing 흐름 | 미착수 |
| TC12 VX.LIVE.SERVER 설치 | 미착수 (사용자 지시로 보류) |
| TC14 좌표/OCR 캘리브레이션 스크립트 작성 | 미착수 |

### 3.4.4 DICOM > MWL 서버 등록 및 Echo 검증 완료 (2026-08-18)

TC_WindowsUpdate_02의 Precondition(MWL 서버 연동)을 실제로 구성했다.

- Setting > DICOM > MWL 화면 진입 시 SCP List가 비어 있었다(신규 설치라 당연).
- `Add` → Name/AE Title `MWL_SCP`, IP `<시험 서버>`, Port `11112` 입력 →
  `Update` → 좌측 목록에 `MWL_SCP` 등록 확인.
- `Echo` 버튼 클릭 → Verification 로그에 `Connect succeeded.` → `Sending
  C-ECHO request.` → `Verification C-Echo completed` → `Sending release
  request.` → `Receiving release response.` → `Verification succeeded.` →
  `Closing connection.` 전 단계 성공 확인. **TC02의 MWL 연동 Precondition이
  실제로 충족·검증되었다.**
- **자동화 구현 시 반드시 반영할 UI 함정**: `Update` 클릭 후 "DICOM - MWL
  Update successfully." **모달 Info 팝업(클래스 `#32770`, 제목 "Info")이
  뜨고, 이 팝업을 OK로 닫기 전까지는 그 뒤에 보낸 모든 클릭(Echo 포함)이
  아무 반응 없이 무시된다.** 팝업이 메인 창 위에 겹쳐 있어 스크린샷만
  보면 "화면은 그대로인데 왜 반응이 없지"로 오인하기 쉽다 — 매 Update/저장
  동작 뒤에는 항상 최상위 창(`GetForegroundWindow`)의 클래스/제목을 확인해
  `#32770`+"Info" 류 팝업이면 OK를 눌러 닫는 절차를 `core/ui.py`의 공통
  헬퍼로 만들어야 한다(Bellalun에는 없던 VXvue 고유 패턴).
- 입력 필드 관련 함정: 텍스트 Edit 필드에 값을 새로 넣을 때 `Ctrl+A`로 전체
  선택이 항상 되는 것은 아니었다(IP Address 필드는 기존 값 뒤에 이어붙여져
  `127.0.0.110.13.`처럼 깨졌고 "Only IP address is allowed" 검증 팝업이
  떴다). `End` 이동 후 `Backspace`/`Delete`를 반복해 완전히 비운 뒤 입력하는
  방식으로 해결했다 — 향후 모든 Edit 필드 입력 헬퍼는 Ctrl+A 대신 이 방식을
  기본으로 한다.

### 3.5 TC_WindowsUpdate_14 (Setting 화면 표시) — Setting Export 재사용 가능성 판단

**결론: 개념적으로 가능하나, 그대로 복사할 수는 없다.**

- `bellalunSetting.py`는 Bellalun 전용으로 캘리브레이션된 좌표(대분류 9개:
  System/Patient/Display/Tool/Study/Procedure/DICOM/Device/Q.C, 소분류
  각각의 개수)와 화면 해상도에 종속되어 있다. VXvue의 Setting 화면 대분류·
  소분류 목록, 탭 개수, 레이아웃은 다르다(체크리스트에는 System/Study/DICOM/
  Integration 등 메뉴명이 산발적으로 언급될 뿐 전체 목록은 없음).
- 재사용 가능한 것은 **방법론**이다: (1) 각 대분류→소분류 탭을 순서대로 열고
  (2) 지정 화면 영역을 캡처하고 (3) 기준(BASE) 캡처와 SSIM으로 비교해 빈
  화면/깨짐/겹침을 잡아낸다. VXvue에서는 가능하면 `bellalunSetting.py`의
  좌표 캘리브레이션 방식보다 **Win32 UI Automation으로 실제 탭 컨트롤을
  순회**하는 방식으로 고도화하는 것을 제안한다(해상도 변경에 더 강건함).
- 실행 전제: VXvue Setting 화면의 정확한 대분류/소분류 탭 목록과 개수를
  알아야 한다. 문서에서 전체 목록을 찾지 못했다 — 사용자 확인 또는
  실행 중 UI 탐색(3.4절 탐색 작업에 포함)이 필요하다.
- SSIM 임계값(0.99)도 VXvue 화면(폰트 렌더링, 애니메이션 유무)에 그대로
  적용 가능한지는 실측 후 조정이 필요하며, 사양 없이 임의로 확정하지 않는다.

### 3.6 프로세스 목록 확인 필요

`preflight.py`의 전제조건 점검, `dbreset.py`의 복원 전 강제 종료 대상, Viewer
기동 확인(`sysinfo.process_names()`)에 VXvue 실행 파일 프로세스명 목록이
필요하다. 설치 폴더 확인 결과 후보는 `VXvue.exe`, `VX.LAUNCHER.exe`,
`VXService.exe`, `VX.SERVICE.DELEGATOR.exe`, `VX.WEB.DEVICE.exe`,
`VX.WEB.IMAGE.exe`, `ImageExtractor.exe`, `VX.PROCEDURE.MANAGER.exe`,
`VX.LOGGER.VIEWER.exe`, `VW.STATISTICS.exe`, `VW.COMMUNICATOR.exe`,
`VX.EXPORT.MANAGER.exe` 등이 있으나, 실제 상시 구동 프로세스와 역할은 실행
로그(`D:\Database\log\Viewer\2026_08_18.log` 등)로 교차 확인 후 확정한다.
임의로 "이 프로세스가 살아있으면 정상"이라고 단정하지 않는다.

## 4. 리포트 상단 — Windows 정보 + 패키지 정보 (사용자 요청 반영)

체크리스트 원본의 Checklist 시트 1~5행 형식(OS / OS Version / OS Build
Version / Viewer Version / VX.LIVE.SERVER)과 Summary 시트(문서번호, 업데이트
회차별 VXvue/XIPL/VX.LIVE.SERVER 버전)를 그대로 리포트 상단에 재현한다.
Bellalun `core/result.py`의 `write_txt(..., env=...)` 패턴을 확장해 HTML/JSON
리포트에도 동일한 헤더 블록을 추가한다(현재 Bellalun은 TXT에만 `env`를 반영함 —
VXvue에서는 세 포맷 모두에 반영하도록 고도화).

### 4.1 Windows 정보 (Bellalun `sysinfo.py` 그대로 이식)

```json
{
  "os_caption": "Get-CimInstance Win32_OperatingSystem 의 Caption",
  "os_version": "...Version",
  "os_build": "...BuildNumber (필요 시 UBR 레지스트리값과 결합해 17763.9020 형식으로)",
  "os_architecture": "...OSArchitecture",
  "display_resolution": "Primary display 해상도",
  "dpi_scale": "Windows 배율(%)",
  "is_elevated": "관리자 권한 여부"
}
```

체크리스트의 "OS Build Version"(예: `17763.9020`)은 `BuildNumber`만으로는
부족하고 UBR(Update Build Revision) 레지스트리 값
(`HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\UBR`)과 결합해야 정확히
재현된다 — Bellalun `sysinfo.py`에는 이 조합이 없어 VXvue에서 추가한다.

### 4.2 패키지 정보 (Model Version Checker 재사용)

`ModelVersionChecker_v2.3.exe --product "VXvue"` 실행 결과(JSON)를 파싱해
VXvue/관련 구성요소 버전을 리포트 헤더에 그대로 병합한다. 릴리즈노트 비교가
필요 없고 현재 버전만 필요하면 `--product` 인자만으로 충분하다(README_v2.md
확인). VX.LIVE.SERVER, XIPL 버전도 동일 도구가 지원하는지는 7개 지원 제품
목록(Bellalun, VXvue Mammo, VXvue, DxWorks, NewAitella, XIPL.STUDIO, XIPL)
기준으로 VX.LIVE.SERVER 자체는 별도 확인이 필요하다 — 미지원이면 파일
버전(`sysinfo.file_version()` 방식)으로 직접 조회한다.

### 4.3 리포트 헤더 예시 (초안)

```text
================================================================================
 VXvue Windows Update 호환성 자동화 결과   (문서번호: R-25-774)
================================================================================
 수행 일시     : 2026-08-18 15:00:00
 [ Windows 정보 ]
   - OS               : Windows 11 Pro
   - OS Version        : 24H2
   - OS Build          : 26100.xxxx
   - Architecture      : 64-bit
   - Display           : 1920x1080 / 100% (96 DPI)
 [ 패키지 정보 ]
   - VXvue             : 1.0.11.015
   - XIPL              : (ModelVersionChecker 결과 또는 확인 필요)
   - VX.LIVE.SERVER    : 미설치 (TC_WindowsUpdate_12 BLOCKED)
 TC 건수        : 12 (제외 3: TC01, TC10, TC15)
 판정 합계      : PASS n / FAIL n / MANUAL n / SKIP n / BLOCKED n
================================================================================
```

## 5. TC별 설계 메모 (Step 분류 요약)

전체 TC 상세 Step 분류표는 각 `tests/tcNN_*.py` 구현 착수 시 개별 문서로
분리한다(가이드 8.6절 "자동화 설계 출력 순서" 준수). 여기서는 핵심만 요약한다.
자동화 수준은 `automation_scope.json`(1절 파일) 참고.

| TC ID | 핵심 Step | 주요 확인 필요 사항 |
|---|---|---|
| WindowsUpdate_02 | MWL 조회→정보 대조→촬영→Close→DB 대조→Send→전송정보 대조 | **촬영이 Demo 모드인지 실제 노출인지** (P0 안전) |
| WindowsUpdate_03 | Interpolation 설정 변경, Zoom/Pan/Rotation Tool, 다중 영상 전환 | "delay 없이" 판정 정량화 기준 |
| WindowsUpdate_04 | XIPL 라이선스 적용, 촬영, Image Process, XIPL Studio Processing | SBSC 아이콘 판정 근거(썸네일 이미지 인식 vs DB 플래그) |
| WindowsUpdate_05 | Dose SR 설정, DICOM Send | QXLink 수신측 검증 방법(DB/로그 접근권한 여부) |
| WindowsUpdate_06 | SBSC 촬영, Extra Tool 전송, XIPL Server Log 확인 | 로그 파일 경로/포맷 |
| WindowsUpdate_07 | Print 전송 | Print 서버 접속·웹 preview 접근권한(Bellalun WF03 인프라 재사용 여부) |
| WindowsUpdate_08 | Study Export(CD/USB), Import 역방향 확인 | 물리 매체 대신 폴더 경로 사용 가능 여부 |
| WindowsUpdate_09 | KIOSK 설정 저장, PC 재부팅, System Launcher 메뉴 확인 | 재부팅 트리거 방식 |
| WindowsUpdate_11 | AI 라이선스, Serialization(~16분), AI 분석 실행 | GPU 유무, VUNO 라이선스, 샘플 데이터 |
| WindowsUpdate_12 | VX.LIVE.SERVER 설치, Live View, Step Analysis, 스냅샷 전송 | VX.LIVE.SERVER 미설치 — 설치 필요 |
| WindowsUpdate_13 | txt/csv Import (수동+폴더 자동 감지 두 가지 경로) | 기존 결함(#22985) 회귀 케이스로 포함 |
| WindowsUpdate_14 | Setting 각 탭 순회 및 화면 표시 확인 | Setting 메뉴 전체 목록 (3.5절) |

## 5.1 사용자 확정 사항 (2026-08-18)

- UI 컨트롤 탐색: 지금 세션에서 바로 진행 (진행 중, 3.4절)
- TC_WindowsUpdate_08: 실제 CD/USB 물리 매체 사용 → PARTIAL(매체 삽입은 수동,
  나머지 자동화)로 `automation_scope.json` 갱신 완료
- TC_WindowsUpdate_09: 재부팅 제약으로 TC09 전체 MANUAL 처리로
  `automation_scope.json` 갱신 완료
- DICOM 시험 서버: 기존 공용 서버 재사용 확정. TCP 접속 테스트 결과
  `<시험 서버>:11112`(MWL_SCP), `:11113`(PRINT_SCP), `:5000`(MWL 관리 웹),
  `:8000`(Print 관리 웹) 모두 이 PC에서 연결 성공 확인(2026-08-18). Bellalun
  전용 Storage 서버(`<시험 PC>:3000`, Bunny)는 연결 실패했으나 VXvue TC05는
  QXLink로 전송하므로 별도 확인 대상(6절 항목 5 참고).

## 6. 사용자 확인이 필요한 항목 (요약)

이 설계 문서를 실제 코드로 전환하려면 아래가 먼저 정리되어야 한다. 채팅에서
답변받은 뒤 해당 TC부터 순서대로 구현에 들어간다.

~~1. UI 컨트롤 ID 탐색 시점~~ → 해결(5.1절, 진행 중)
~~4. DICOM 시험 서버 재사용 여부~~ → 해결(5.1절, 접속 확인 완료)
~~6. TC_WindowsUpdate_08 Export 대상~~ → 해결(5.1절, 실제 CD/USB)
~~7. TC_WindowsUpdate_09 재부팅 처리 방식~~ → 해결(5.1절, 전체 MANUAL)

남은 항목:

1. **VXvue 로그인용 QA 테스트 계정(Account/Password)** — 로그인 화면까지
   확인했으나 자동화용 계정 정보가 없어 더 진행하지 못했다(3.4절). 실제
   운영 계정이 아닌 QA 전용 테스트 계정을 요청한다.
2. **VXvue Setting 화면의 대분류/소분류 탭 전체 목록**(3.5절) — 문서에서
   찾지 못했다. 로그인 후 직접 탐색 예정이나, 이미 정리된 목록이 있으면
   더 빠르다.
3. **TC_WindowsUpdate_02의 촬영 Step이 Demo 모드로 대체 가능한지**(P0 안전
   확인, Bellalun의 `viewer.demo_mode=true` 가드와 동일한 것이 VXvue에도
   있는지).
4. **TC_WindowsUpdate_05/06 판정 근거** — QXLink 수신 확인, XIPL Server Log
   경로에 대한 접근 권한/방법.
5. **TC_WindowsUpdate_11 선행 조건** — 이 PC의 GPU 탑재 여부(확인 시도했으나
   실패), VX CAD/VUNO 라이선스 적용 여부.
6. **TC_WindowsUpdate_12 선행 조건** — VX.LIVE.SERVER 설치 여부(현재
   미설치 확인됨) 및 설치를 이번 자동화 준비 작업에 포함할지.
7. **DB 접근 계정 권한**(3.3절) — 자동화 실행 계정의 `.\CHAMELEON` 로그인
   권한.
8. **오늘 백업한 DRF DB/D:\Database 폴더가 정말 "클린 설치 직후" 상태가
    맞는지**(2절 참고 — 과거 백업 이력이 남아있던 점에 대한 확인).

이 문서와 `automation_scope.json`은 답변을 받는 대로 갱신한다.


---

## 7. 후속 세션 (2026-08-18 오후) — 코드베이스 착수와 환경 재확인

앞선 세션이 토큰 한계로 끊긴 지점("DX 처방 생성 + 연동된 가상 제너레이터/
VX CAD/VX.LIVE.SERVER 반영 + Extra Tool의 Remove Image Processing 확인")부터
이어서 진행했다.

### 7.1 VXvue 전용 DX MWL 처방 등록 완료

사용자 지시대로 Bellalun/VXvue Mammo가 쓰는 MG 처방(`DATA_FLOW_MWL_01`)을
건드리지 않고, VXvue(일반 촬영)용 **Modality `DX`** 처방을 새로 등록했다.
공용 MWL 서버의 HTTP API(`http://<시험 서버>:5000`)로 등록했으므로 UI 조작이
전혀 필요 없고, 매 시험 전 `python run.py mwl-ensure` 한 번으로 당일 날짜
처방을 보장할 수 있다(오늘 것이면 재사용, 지난 것이면 삭제 후 재생성).

| 항목 | 값 |
|---|---|
| Patient ID | `VXVUE_MWL_DX_01` |
| Patient Name | `AUTO^VXVUE^^^` (비식별) |
| Modality | `DX` |
| Accession No. | `ACC_VX_AUTO_001` |
| SPS ID / RP ID | `SPS_VX_AUTO_001` / `RP_VX_AUTO_001` |
| Scheduled Station AE | `VXVUE` (Bunny 로그 파일명 `20260818_VXVUE.txt`로 확인한 VXvue의 Calling AE) |
| Procedure | `CHEST` / `CHEST PA` |
| Sex / Birth Date | `M` / `1980-01-01` |

### 7.2 "Remove Image Processing" = DB의 `RemoveSBSC` (강한 근거 확보)

사용자가 지목한 Integration > Extra Tool 화면의 **"Remove Image Processing"**
체크 옵션이 체크리스트의 "Remove SBSC"와 같은 것인지 확인하기 위해, 먼저
DRF DB 스키마를 조사했다.

- `AE_LIST` 테이블에 **`RemoveSBSC` 컬럼이 실제로 존재한다.** 현재 등록된
  3개 SCP(MWL_SCP / PRINT_SCP / BUNNY_TEST) 모두 값은 `0`이다.
- 즉 이 옵션은 화면 라벨만 "Remove Image Processing"이고 저장 필드는
  `RemoveSBSC`인 것으로 보인다. **UI에서 체크 후 이 컬럼이 `1`로 바뀌는지
  확인하면 확정된다** — 이것이 TC_WindowsUpdate_06의 자동 판정 근거가 된다.
- 확인 명령: `python run.py db-ae` (Type/Name/AE Title/Port/RemoveSBSC 출력)

Extra Tool은 MWL/Print/Storage와 달리 다중 목록이 아니라 **단일 대상**이며,
`Use extra tool` 체크 전에는 AE_LIST에 행이 생기지 않는 것으로 보인다
(현재 `DICOM_EXTRA` 계열 행 없음).

### 7.3 사용자가 연동한 항목 실측 확인 (`C:\ProgramData\VXvue\Viewer.xml`)

Viewer.xml이 2026-08-18 13:51에 갱신되어 있었고, 아래가 실제로 반영돼 있다.

| 항목 | Viewer.xml 값 | 의미 |
|---|---|---|
| Generator | `<Generator product="8" gs_path="C:\Program Files\Vxvue\GENERATOR\Protocol\">` | 제너레이터 연동됨(가상) |
| AI Engine | `<AIEngine product="3">` | AI 엔진 선택됨 (TC11 관련) |
| Camera | `<Camera UseLiveView="1"/>` | **Live View 활성** — TC12의 Setting > Integration > Camera 메뉴가 나타날 조건으로 추정 |
| Theme | `Onyx Classic` | 앞선 세션의 Shimadzu 스킨에서 변경됨 |

- `C:\VX.LIVE.SERVER`가 **설치 완료**됐다(`VX.LIVE.SERVER.exe` 1.1.0.1,
  `Setting.exe`, `Configuration`, `test_image` 2,045개). 데모 트리거 파일
  `VX.LIVE.SERVER.DEMO.txt`도 이미 존재한다.
- `CamAppServerSetting.ini` / `CamAppClientSetting.ini`로 확인한 연동 포트:
  서버 `127.0.0.1`, VXvue↔서버 TCP `55556`, 클라이언트 TCP `55555` /
  UDP `55559`. `SystemInfo = ./Configuration/Shimadzu_RadSpeed pro SR5/Left.ini`.
- 라이선스: `D:\Database\Database\license.lic` + `Optionlicense0/1.lic`
  (10:20~10:21 적용). **Option 라이선스가 2개뿐이므로 VX CAD/VUNO/Live View 중
  무엇이 적용된 상태인지는 파일만으로는 알 수 없다** — Setting > System >
  License 화면에서 확인이 필요하다(7.6절 확인 필요 항목).

### 7.4 자동화 코드베이스 착수 (`VXvue\auto`)

설계만 있고 코드가 없던 상태에서, Bellalun과 같은 뼈대로 실행 가능한
코드베이스를 만들었다. 지금 바로 동작하는 명령은 다음과 같다.

```
python run.py env             리포트 상단 헤더(Windows 정보 + 패키지 정보)
python run.py preflight       실행 전 환경 점검 (NG면 종료코드 2)
python run.py scope           TC별 자동화 수준
python run.py ui-probe        현재 화면 컨트롤 트리 덤프
python run.py mwl-list        공용 MWL 서버 처방 목록
python run.py mwl-ensure      VXvue 전용 DX 처방 보장
python run.py db-ae           등록된 SCP + RemoveSBSC 값
python run.py report-sample   헤더 형식 확인용 리포트 생성
```

모듈은 `core/ui.py`(VXvue 고유 함정 흡수), `core/db.py`(DRF 조회 전용),
`core/sysinfo.py`, `core/package_info.py`, `core/preflight.py`,
`core/result.py`, `core/mwl.py`다. 추가 패키지 설치는 필요 없다.

### 7.5 실행 중 확인된 이 PC의 함정 두 가지 (자동화 설계에 반영)

1. **WMI/CIM이 통째로 물릴 수 있다.** 이번 세션 중 `Get-CimInstance`가 어떤
   클래스든 응답하지 않는 상태가 실제로 발생했고(`Win32_PageFileUsage`는 60초
   초과), 그 때문에 환경 조회가 자동화 전체를 멈춰 세웠다. 그래서
   `core/sysinfo.py`를 **WMI 비의존으로 재작성**했다 — 메모리는
   `GlobalMemoryStatusEx`(kernel32), OS 정보·GPU는 레지스트리, 파일 버전은
   버전 리소스 직접 읽기, 해상도/DPI는 Win32 API. 남은 WMI 항목(설치된 KB
   목록)은 타임아웃을 걸고 실패해도 리포트 생성이 계속되게 했다.
2. **커밋(가상) 메모리 고갈이 앞선 세션 장애의 실제 원인이었다.** 재부팅 전
   시점에 물리 여유 3.6GB인데 **페이지파일 여유 0.0GB / 커밋 여유 1.28GB**
   였다. 레지스트리에는 `D:\pagefile.sys 32768 32768`이 설정돼 있었지만
   **D:\pagefile.sys 파일이 존재하지 않아** 커밋 한도가 19.73GB에 묶여
   있었다. 재부팅 후에는 32GB 페이지파일이 **C: 드라이브에** 생성되어
   (`C:\pagefile.sys` 32768MB, C: 여유 67.2GB) 페이지파일 여유 30.2GB로
   정상화됐다. 페이지파일을 D:로 두려던 의도였다면 별도 조치가 필요하다.
   → `core/preflight.py`가 이 조건을 실행 전에 잡는다(NG면 UI 자동화 중단).

### 7.6 이번 세션에서 새로 생긴 확인 필요 항목

1. **적용된 Option 라이선스 2개의 정체** — VX CAD / VUNO / Live View / XIPL 중
   무엇인가? (Setting > System > License 화면 확인 예정)
2. **AIEngine product="3"이 가리키는 엔진** — VUNO인지 VX CAD인지. TC11의
   "AI 라이선스 적용" Step 판정 기준과 직결된다.
3. **Generator product="8"의 실제 모델** — 가상/시뮬레이터인지, 특정 벤더
   모델인지. TC02/04/06의 촬영 Step이 실제 노출을 유발하지 않는지(P0 안전)
   확인하는 근거가 된다.


### 7.7 "Remove Image Processing" = Remove SBSC — **확정**

재부팅 후 VXvue를 자동으로 기동·로그인해 Setting > Integration > Extra Tool
화면 맨 아래까지 스크롤해 실물을 확인했다.

- 항목 라벨은 **`Remove Image Processing`**, 그 오른쪽 체크박스의 라벨이
  **`S.B.S.C.`** 다. 즉 사용자가 지목한 옵션이 체크리스트의 "Remove SBSC"가
  맞다 — **화면 라벨과 체크리스트 용어가 다를 뿐 같은 것**이다.
- 바로 위 항목은 `DICOM Option` / `Include Edited Dose` 체크박스다.
- DB 근거와도 일치한다: `AE_LIST` 테이블에 `RemoveSBSC` 컬럼이 존재하며
  현재 값은 전부 `0`. TC06 자동 판정은 **UI 체크 → Update → `RemoveSBSC`가
  1인지 DB로 확인**하는 방식으로 설계한다(`python run.py db-ae`).
- 이 체크박스는 Options 섹션 맨 아래에 있어 **스크롤하지 않으면 보이지
  않는다.** 좌표 고정 금지 규칙(`ui.find_scrolling()`)이 적용되는 화면이다.
- Extra Tool은 다중 SCP 목록이 아니라 **단일 대상**이며, `Use extra tool`
  체크 + AE Title/IP/Port 입력이 되어야 Update가 통과할 것으로 보인다
  (현재 AE Title 공란, IP `127.0.0.1`, Port `0`).

### 7.8 Setting > System > License — 적용 라이선스 확정

7.6절의 "Option 라이선스 2개의 정체" 질문이 해소됐다.

| Name | License Key | Information |
|---|---|---|
| VXvue | `****-*****-****-*****` | **Demo License** 2100-08-18 (Shimadzu…) |
| VXvue Option | `****-*****-****-*****` | **Computer Aided Detection** (= VX CAD, TC11) |
| VXvue Option | `****-*****-****-*****` | **Live View** (TC12) |

- Hardware Key: `(하드웨어 키 생략)`
- **TC11(AI)과 TC12(카메라/Live View)의 라이선스 선행 조건이 모두 충족**됐다.
- 본 제품 라이선스가 **Demo License**라는 점이 중요하다. 사용자가 연동한
  가상 제너레이터(`Viewer.xml`의 `<Generator product="8">`)와 함께, 촬영
  Step을 실제 X-ray 노출 없이 수행할 수 있다는 근거가 된다(P0 안전 항목).
- **XIPL 라이선스는 이 목록에 없다.** TC04가 요구하는 "XIPL 라이선스 적용"이
  VXvue의 License 화면이 아니라 XIPL 자체(설치본)의 라이선스를 가리키는
  것으로 보인다 — 확인 필요(7.10절).

### 7.9 Integration > Camera 소분류 등장 — TC12 BLOCKED 해소

앞선 세션에서 "Integration에 Camera 소분류가 없다"고 기록했던 것이,
VX.LIVE.SERVER 설치 + Live View 라이선스 적용 + `<Camera UseLiveView="1"/>`
이후 **실제로 나타났다.** 조건부 표시라는 추정이 확인된 것이다.

Integration 소분류(현재 7개): General / Detector / Shock Log / XIPL /
Extra Tool / **Camera** / Bucky
→ 3.4.3절의 전체 트리는 10개 대분류 / **54개 소분류**로 갱신된다(기존 53 + Camera).

### 7.9.1 확보한 컨트롤 지도 (config.json `viewer.control_ids`에 기록)

| 화면 | 컨트롤 | ID |
|---|---|---|
| 우측 메인 네비 | Tab 컨테이너 | `31197` |
| | TabItem (위→아래) | `8` Registration / `9` Exposure / `10` Database / `11` Viewer / `12` Print / `13` Setting / `14` Exit |
| Registration | 상단 탭 | `31201` Scheduled / `31202` Unscheduled / `31203` Reserved |
| | Search / Default | `30689` / `30935` |
| | Today / Week / Month | `30764` / `30765` / `30766` |
| | 검색 항목 콤보 | `30952` |
| | Station Name / Modality / Station AE | `30950` / `30951` / `30949` |
| | 결과 목록 / SPS 목록 / 건수 | `31119` / `31120` / `30013`(Static) |
| Setting | 좌측 MenuList / Update | `30894` / `30641` |
| Extra Tool | Use extra tool | `31516` |
| | AE Title / IP / Port | `30092` / `30097` / `30098` |
| | Include Edited Dose | `31522` |
| | **S.B.S.C. (Remove Image Processing)** | **`31523`** |
| | Echo | `30780` |

**우측 메인 네비의 TabItem ID가 8~14로 고정**이라는 점이 큰 수확이다. 화면
전환을 좌표가 아니라 컨트롤 ID로 할 수 있어 해상도 변화에 강건해진다.

### 7.9.2 TC02 MWL 조회 실측 — DX 처방 정상 조회

Registration > Scheduled에서 `Search`(30689)를 눌러 오늘 날짜 조회 결과
**2건**이 나왔다(`Range: 2026-08-18 ~ 2026-08-18, Result: 2 / 2`).

| Patient ID | Patient Name | Sex | Age | Birth Date | Acc. No. | Study Description | Scheduled | Modality |
|---|---|---|---|---|---|---|---|---|
| `VXVUE_MWL...` | AUTO VXVUE | M | 46Y | 1980-01-01 | `ACC_VX_AUTO_001` | CHEST PA | 2026-08-18 09:00:00 | **DX** |
| `DATA_FLOW...` | AUTO MWL | F | 46Y | 1980-01-01 | `ACC_AUTO_001` | Mammography | 2026-08-18 09:00:00 | MG |

즉 **TC02 Step1(MWL 조회 및 처방 정보 대조)은 이미 완전 자동 판정이
가능하다** — MWL 서버 API로 등록한 값이 정답지이므로, 화면 조회 결과와
1:1 대조하면 된다. 남은 것은 오픈 → F2 촬영 → Close → DB 대조 → Send 흐름이다.

### 7.10 남은 확인 필요 항목 (갱신)

~~1. 적용된 Option 라이선스 2개의 정체~~ → 해소(7.8절: CAD + Live View)
~~2. Integration에 Camera가 나타나는 조건~~ → 해소(7.9절)
~~3. Remove Image Processing이 Remove SBSC인지~~ → 해소(7.7절, 확정)

남은 항목:

1. **Extra Tool의 전송 대상(AE Title / IP / Port)을 무엇으로 할 것인가**
   (TC06). 현재 미설정(공란 / 127.0.0.1 / 0)이다. Bunny(`<시험 PC>:3000`)를
   그대로 재사용해도 되는지, 아니면 체크리스트가 지정한 별도 수신처가 있는지
   확인이 필요하다. 임의로 정하지 않고 대기한다.
2. **TC04의 "XIPL 라이선스 적용"이 가리키는 것** — VXvue License 화면에는
   XIPL 항목이 없다. XIPL 설치본 자체의 라이선스인지 확인 필요.
3. **`AIEngine product="3"`이 CAD를 의미하는지** — License에 Computer Aided
   Detection이 있으므로 정황상 일치하나, product 번호와 엔진의 매핑표는
   확인하지 못했다. TC11 판정 문구를 확정하려면 필요하다.
4. **`Generator product="8"`의 실제 모델명** — 가상/시뮬레이터가 맞는지
   Setting > Integration > General(또는 Detector) 화면에서 확인 예정.
5. **TC03 Expected Result의 "delay 없이"를 무엇으로 정량화할 것인가** — 기존
   미해결 항목 그대로.
