# 다른 PC 실행 이식성 점검 결과 (2026-08-25)

> **역할**: 이 자동화를 **개발·실측에 쓴 시험 PC 밖의 다른 PC**에서 돌릴 때
> 무엇이 필요하고, 무엇이 아직 안 되는지를 기록한다. `config.example.json`의
> 키 하나하나가 실제로 코드에서 어떻게 쓰이는지 소스를 따라가 확인한 결과다.
> **읽는 순서**: `README.md` 5.1절(준비)을 먼저 보고, 그 절이 다루지 않는
> "다른 PC에서 왜 안 되는가"를 알아야 할 때 이 문서를 연다.
>
> 점검 방법: `config.example.json`의 모든 키에 대해 (1) 코드가 그 값을 실제로
> 읽는지, (2) 값이 없을 때 어떤 기본값으로 떨어지는지, (3) 그 기본값이 이 시험
> PC 전용인지를 소스에서 확인했다. 확인하지 않은 것은 아래에 쓰지 않았다.

---

## 1. 다른 PC에 반드시 있어야 하는 것 (없으면 시작 자체가 안 된다)

`python run.py preflight`가 아래 항목을 검사하고, **NG가 하나라도 있으면 UI
자동화를 시작하지 않는다**(`cmd_preflight`는 종료 코드 2, 전체 회귀는 이후
단계를 SKIP 처리 — `core/regression.py:177`).

| 항목 | 판정 | 근거 |
|---|---|---|
| **관리자 권한** | **NG(차단)** | VXvue가 관리자 권한으로 동작한다. 자동화가 일반 권한이면 Windows UIPI가 합성 입력을 차단하는데, **캡처는 되고 클릭만 조용히 실패**해 엉뚱한 증상으로 보인다 |
| **DPI 100%(96 DPI)** | **NG(차단)** | 배율은 로그아웃 없이 안전하게 바꿀 수 없어 자동화가 대신 고쳐 주지 않는다. 사람이 먼저 바꿔야 한다 |
| **VXvue 실행 파일** (`viewer.exe`) | **NG(차단)** | 경로가 존재하지 않으면 기동 자체가 불가능 |
| **DRF DB 접속** (`sql_server` / `database`) | **NG(차단)** | 판정의 상당 부분이 DB 대조라, 접속이 안 되면 "눌렀다"까지만 확인되고 결과를 확인할 수 없다 |
| 화면 해상도 1920×1080 | WARN | 컨트롤은 ID·실제 rect 기준으로 찾으므로 다른 해상도에서도 상당 부분 동작한다. 다만 실측 좌표에 의존하는 owner-draw 화면(Setting 좌측 메뉴 등)은 어긋날 수 있어 경고로 남긴다 |
| 물리 메모리 / 페이지파일 여유 | WARN | **의도적으로 차단하지 않는다**(사용자 판단). 이 시험 PC는 상주 프로세스 때문에 기준(3GB) 아래가 상시다. 대신 뷰어 기동·화면 진입이 실패하면 그 시점 메모리를 다시 읽어 판정 note에 남긴다(`preflight.memory_pressure()`) — 판단을 실행 전 추측에서 **실패 시점의 실측**으로 옮긴 것 |
| XIPL 서버 로그 폴더 | WARN | 없으면 XIPL 로그 근거를 쓰는 Step만 확인 불가 |
| Bunny Receive 폴더 | WARN | 없으면 Storage 수신 판정만 확인 불가 |

이 밖에 **pip 밖의 외부 설치**가 두 개 필요하다.

- **Tesseract-OCR** — owner-draw 목록·로그 영역을 읽는 데 쓴다(코드 22곳).
  경로는 `config.json`의 `xipl.tesseract_exe`로 지정한다.
- **SQL Server 인스턴스** — 기본 `.\CHAMELEON` / DB `DRF`.

Python 의존성은 4개뿐이다(`requirements.txt`: Pillow, pytesseract, openpyxl,
pypdf). Win32 UI 조작·화면 캡처·SQL 접속은 표준 라이브러리 + Windows 기본
PowerShell/.NET만 쓰므로 pywin32·pyodbc는 필요 없다.

## 2. 이미 이식성이 확보된 부분

- **컨트롤 접근은 MFC Control ID + 실제 control rect 기준**이다. 절대 좌표에
  의존하는 자리는 owner-draw로 ID를 읽을 수 없는 화면(Setting 좌측 메뉴)뿐이고,
  그 경우에도 전환 성공은 상단 제목 Static(`20000`) 문구로 판정한다.
- **체크리스트 xlsx는 상대경로로 찾는다**(`core/checklist.source_path()`).
  `config.json`의 `checklist_xlsx`는 **실제로 존재할 때만** 쓰고, 없으면 저장소
  상위 폴더를 4단계까지 올라가며 찾는다 — 다른 PC 사용자의 Downloads 경로가
  박혀 있어 결과 기록이 조용히 빠지는 일을 막기 위한 설계다. 못 찾으면 침묵하지
  않고 이유를 출력한다.
- **TC11 AI 샘플 영상은 저장소 기준 상대경로**(`core/ai_samples.SAMPLE_ROOT` =
  `<repo>/TestData/...`)에서 찾는다. 사내 공유폴더에 매번 접근하지 않는다.
- **`data_dir`을 인자로 받는 설계**: baseline 복원(`core/dbreset.py`)의
  라이선스·로그 백업 함수는 경로를 모듈 상수로 박지 않고 호출부
  (`core/regression.py`)가 `config.json`의 `data_dir` /
  `baseline.db_backup` / `baseline.folder_backup`을 읽어 넘긴다.
- **라이선스 파일 이름을 열거하지 않는다**: 사양서1 p.7(VP-415)이 옵션
  라이선스 최대 16개를 허용하므로 `Optionlicense0/1`만 박으면 옵션이 3개 이상인
  PC에서 조용히 누락된다. glob으로 실제 존재하는 파일을 찾는다.
- **설정 테이블 목록도 실행 시점에 결정한다**: `CONFIGURATION*`는 패턴으로
  잡고 나머지는 존재하는 테이블과 교집합을 취한다 — 제품 버전이 올라가 새 설정
  테이블이 생겨도 조용히 빠지지 않는다.
- **시험 데이터는 실행마다 새로 만든다**(`test_data.unique_per_run`, 기본
  `true`) — 같은 Patient ID가 쌓여 Import 검증이 무의미해지는 것을 막는다.
- **시험 서버 정보는 전부 config에서 읽는다**: `dicom.servers_to_register`와
  `extra_tool.server`가 독립돼 있어, Extra Tool 대상만 다른 서버로 바꿀 수 있다
  (`tests/tc06_extra_tool.py`는 `extra_tool` 블록만 읽고 하드코딩하지 않는다).

## 3. 남아 있는 이식성 결함 (수정 대상)

아래 4건은 **이 시험 PC의 `data_dir`이 `D:\Database`라는 전제**가 모듈 상수로
남은 자리다. `data_dir`이 다른 PC(예: `C:\Database`)에서는 예외가 아니라
**조용히 빈 결과**가 되므로, 판정이 "확인 못 함"이 아니라 "차이 없음"으로
보일 수 있어 위험하다.

| # | 위치 | 문제 | 확인한 내용 |
|---|---|---|---|
| 1 | `core/config_snapshot.py` `CONFIG_FILE_DIR` | `D:\Database\Configuration` 하드코딩 | `take()`의 기본 인자인데 **호출부 4곳이 전부 인자를 넘기지 않는다**(`run.py:460`, `tests/tc_setting_export_import.py:375·455·507`) → 다른 PC에서는 설정 파일 해시가 전부 빠진 스냅샷으로 Export/Import를 판정하게 된다 |
| 2 | `core/context.py` `LICENSE_GLOBS` | `D:\Database\Database\license.lic*` 하드코딩 | `vxvue_license_keys()`가 이 상수를 직접 쓴다 — **오버라이드 경로가 없다** |
| 3 | `core/context.py` `CONFIGURATION_XML` | `D:\Database\Configuration\Configuration.xml` 하드코딩 | 컨텍스트 수집에서 직접 참조(127~128행) — 없으면 그 항목이 조용히 비어 있다 |
| 4 | `core/dbreset.py` `backup()`의 `out_dir` 기본값 | `D:\Database\Database\Bak` 하드코딩 | `tests/tc_setting_export_import.py:474`가 `out_dir` 없이 호출한다 → 다른 PC에서는 Setting Import 전 **안전 백업이 엉뚱한 드라이브를 향한다** |

**사내 주소 문자열이 이 저장소에 남아 있는 것은 사용자 판단으로 그대로 둔다**
(2026-08-25 결정) — 시험망 내부 주소라 노출 위험이 낮다고 판단했다. 다른 PC로
옮길 때는 그 주석·docstring의 값이 그 PC의 실제 서버와 다를 수 있으니 **설명으로만
읽고 `config.json`을 근거로 삼는다.**

추가로 사소한 불일치 1건:

- Tesseract 실행 경로는 대부분 `config.json`을 먼저 보고 없을 때만 기본 경로로
  떨어지는데(`or r"C:\Program Files\Tesseract-OCR\tesseract.exe"` 형태),
  `core/listgrid.py:113`과 `core/workflow.py:2350`은 **config 폴백 없이 기본
  경로를 바로 쓴다.** Tesseract를 다른 위치에 설치한 PC에서 이 두 경로만 실패한다.

## 4. 구조상 다른 PC에서 그대로 되지 않는 것 (제한)

- **제품 버전이나 UI 언어/테마가 바뀌어 Control ID 자체가 달라지면 새 컨트롤
  맵이 필요하다.** 현재 맵은 `1920x1080 / 100% DPI / Onyx Classic 테마 /
  Shimadzu OEM` 기준 실측이다(`config.example.json`의 `control_ids._source`).
  `python run.py ui-probe`로 덤프해 다시 확정한다 — **추측해서 누르지 않는다.**
- **화면 해상도를 자동화가 바꾸지 않는다.** 이 저장소에는 해상도를 변경하는
  코드가 없다(확인함). 1920×1080이 아니면 경고만 나가고 실행은 계속되므로,
  owner-draw 좌표에 의존하는 화면에서 어긋날 수 있다.
- **DPI 배율은 100%가 아니면 차단**된다. 사람이 먼저 바꿔야 한다.
- **MWL / Storage / Print 연결은 대상 PC의 NIC·방화벽·서버 접근성에 의존한다.**
  MWL·Print 시험 서버는 HTTP API로 처방·출력 큐를 제어하므로 그 API에 닿지
  않으면 테스트 데이터 준비 자체가 되지 않는다.
- **Storage(Bunny)는 시험 PC 자신에서 떠 있어야 한다** — `Bunny.exe`가 실행
  중이어야 포트 3000이 열린다. 수신 객체는 `Receive`가 아니라 `Temp`에 저장되는
  경우가 있어 판정은 두 폴더를 모두 본다(2026-08-19 실측).
- **baseline 복원은 `baseline.db_backup` / `baseline.folder_backup`에 클린 설치
  시점 백업이 실제로 있어야 동작한다.** 이 백업은 저장소에 포함되지 않는다
  (용량·사내 데이터). 다른 PC에서는 그 PC의 클린 시점 백업을 새로 만들어야 한다.
- **TC08 Export는 `E:` 드라이브 기준**(`export.dest_dir`)이다. 체크리스트
  Precondition은 CD/USB지만 물리 매체 굽기는 사람이 해야 하므로, Export 실행·
  산출물 검증·역방향 Import까지를 이 경로로 자동화했다. 드라이브 문자가 없는
  PC에서는 `config.json`에서 바꿔야 한다.
- **XIPL 설치는 Bellalun 자동화와 공유한다.** `C:\XIPL\PARAMETER`의 Bellalun
  픽스처를 덮어쓰지 말고 `_VXVUE` 접미 이름으로 복사해 쓴다.
- **GPU가 없으면 TC11의 AI 결과물 생성 검증은 SKIP**이다(라이선스·UI 흐름만
  확인). 이미 `automation_scope.json`에 반영돼 있다.
- **실물 장비·물리 매체가 필요한 항목은 자동화 대상이 아니다** — 검출기/장비
  연동, CD/USB 굽기, MG 절차(이 자동화는 **DX 전용**).
- **검증 범위는 DX(일반촬영) 전용**이다. 모든 리포트 상단에 이 제한이 자동으로
  표시된다(`core/result.REPORT_CAVEATS`).

## 5. 점검 명령

```bash
python -m pip install -r requirements.txt
copy config.example.json config.json
```

```bash
python run.py preflight
```

```bash
python run.py ui-probe --all --save probe_out.txt
```

`preflight`가 통과하고 `ui-probe` 덤프의 컨트롤 ID가 `config.json`의
`control_ids`와 일치하면, 그 PC에서 UI 자동화를 시작할 수 있는 상태다.
일치하지 않으면 **덤프 결과로 `control_ids`를 갱신한 뒤** 시작한다.
