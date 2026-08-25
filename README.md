# VXvue 의료영상 뷰어 QA 자동화

Windows 업데이트마다 반복되는 **의료영상 뷰어 호환성 검증 체크리스트**를 무인
실행 + 자동 판정 + 증거 리포트로 옮긴 프로젝트다. 이어서 기본기능 회귀 시험까지
확장할 수 있도록 구조를 설계했다.

같은 방식으로 먼저 만든 자매 프로젝트: **Bellalun Viewer 자동화**
(`bellalun-viewer-automation`). 이 저장소는 그 설계 원칙을 재사용하되, 다른
제품의 컨트롤 ID나 좌표를 그대로 가져오지 않고 VXvue에서 실측한 값만 쓴다.

---

## 1. 무엇을 푸는 프로젝트인가

의료영상 뷰어는 Windows 보안 업데이트가 적용될 때마다 호환성을 다시 검증해야
한다. 체크리스트는 15개 TC로 구성되고, 그 안에는

- Setting **55개 화면**이 정상 표시되는지
- DICOM 연동 3종(Worklist / Storage / Print) 등록·Echo·전송
- 영상처리(XIPL) 라이선스와 산과물, AI(CAD) 분석
- 설정 Export/Import 후 값 보존
- 환자정보 Import(txt/csv), Study Export(CD/USB)

같은 항목이 섞여 있다. 사람이 하면 반나절이 걸리고, 매번 같은 화면을 수십 개
클릭하다 보니 **누락과 판정 편차**가 생긴다. 증거도 캡처를 손으로 모아야 한다.

이 저장소는 그 반복 구간을 자동화하고, **자동 판정이 불가능한 항목은 정직하게
MANUAL로 남기는 것**을 원칙으로 한다.

---

## 2. 설계에서 가장 신경 쓴 것 — "헛된 PASS"를 만들지 않기

자동화의 실패 방식은 두 가지다. 잡아야 할 결함을 놓치거나(false negative),
아무것도 검증하지 않고 통과하는 것(vacuous pass)이다. 후자가 더 위험하다.
녹색 리포트가 나오면 사람은 더 이상 보지 않기 때문이다. 그래서:

**① 첫 실행을 PASS로 위장하지 않는다.**
기준 캡처·기준 값이 없는 최초 실행은 기준을 생성하고 그 항목을 `MANUAL`로
보고한다. "비교할 대상이 없어서 통과"는 통과가 아니다.

**② 변경이 실제로 반영됐는지 먼저 증명한다.**
Setting Export/Import 회귀는 3단 비교로 설계했다.

```
S0 스냅샷 ──> Export(A) ──> 설정 변경 ──> S1 스냅샷 ──> Import(A) ──> 재기동 ──> S2 스냅샷
                                          │                                      │
                                    [검증] S1 ≠ S0                         [검증] S2 = S0
                                    변경이 실제로 먹었다                   Export 값이 보존됐다
```

중간 검증(`S1 ≠ S0`)이 없으면 **변경이 한 건도 반영되지 않아도 마지막 대조가
통과한다.** 아무것도 안 바꿨으니 당연히 같기 때문이다.

**③ 판정 근거를 화면 픽셀에 의존하지 않는다.**
제품은 테마·폰트에 따라 색상·창 크기·폰트가 달라지지만 **설정 값과 옵션, 메뉴
구성은 동일**하다. 그래서 판정은 값(JSON)으로 하고, 픽셀 비교는 테마까지 같은
기준자료 안에서만 보조로 쓴다(4.1절).

**④ 읽을 수 없는 것은 읽을 수 없다고 적는다.**
체크박스는 커스텀 렌더링이라 UI에서 on/off를 읽을 수 없다. 픽셀을 찍어 추측하는
대신, 컨트롤 구성만 UI에서 대조하고 실제 값은 DB 스냅샷으로 검증한다.

---

## 3. 지금 동작하는 것

```bash
python run.py run-regression        # 표준 전체 회귀(사용자 지시, 2026-08-25)
                                    # — baseline 초기화가 기본. 설치 직후와 같은 클린
                                    # DB/폴더 상태에서 시작. 선행조건 → 라이선스
                                    # → DICOM 연동 → 구현된 TC를 **번호순**으로
                                    # → 리포트 (실측 39분, baseline 복원 시간 별도)
python run.py run-regression --no-reset-baseline  # 임시 디버깅용(정식 판정 아님)
python run.py run-regression --quick   # 짧은 회귀(범위 축소 — 정식 판정용이 아니다)
python run.py tc02                  # MWL 조회 → Step 등록 → 촬영 → Send → Close → DB
python run.py tc03                  # 영상 조작(Interpolation 설정 + 툴 적용 SSIM)
python run.py tc04                  # Image Processing (촬영 처리 + Proc. + XIPL Studio)
python run.py tc05                  # DICOM 전송 (수신 객체의 SOP Class UID로 판정)
python run.py tc07                  # DICOM Print (받은 쪽 필름 목록으로 판정)
python run.py tc08                  # Study Export (E 드라이브)
python run.py tc11                  # AI 분석(CAD) — 실제 검증 샘플 영상으로 분석 실행
python run.py tc13                  # 환자정보 Import 회귀 (TAB 구분자 결함 회귀 포함)
python run.py tc14                  # Setting 각 탭 순회·표시 확인 (--deep으로 전수 검증)
python run.py setting-export-import # Export → 변경 → Import → 보존 검증 (3단 비교)
python run.py vxvue-license         # VXvue 본체 라이선스(Demo/CAD/Live View) 확인
python run.py xipl-license          # XIPL 영상처리 라이선스 4종 확인 (위와 다른 검증)
python run.py preflight             # 실행 전 환경 점검
python run.py ui-probe              # 현재 화면 컨트롤 트리 덤프 (새 화면 자동화의 첫 단계)
python run.py snapshot / snapshot-diff / vxs-info / db-ae / mwl-list / scope / env
```

각 명령의 옵션과 실행 순서, 결과물 위치는 **5절 실행 방법**에 정리했다.

지금 자동으로 판정되는 것을 한 줄로 요약하면 이렇다.

| 무엇을 | 어떤 근거로 |
|---|---|
| MWL 조회·촬영·전송 정보가 일치하는가 | MWL 서버 **API 등록값** ↔ 화면 OCR ↔ **DB** ↔ **수신 DICOM 파일 태그** 네 지점 대조 |
| 전송이 성공했는가 | Storage SCP 로그의 **C-STORE Status 0000h** + 실제 저장된 파일 (제품 Queue를 믿지 않는다) |
| Print가 성공했는가 | Print SCP의 **수신 필름 목록**(Calling AE로 다른 제품 필름과 구분) |
| 툴이 영상에 적용됐는가 | 영상 영역 캡처 **SSIM 비교** (버튼 클릭 성공을 적용으로 인정하지 않는다) |
| 라이선스가 등록됐는가 | 설치된 `.lic` **파일** ↔ 화면 목록 OCR 대조 |
| 설정 55화면이 정상 표시되는가 | 실행 시점에 만든 **메뉴 지도** + 화면별 본문 표시 확인 (`--deep`이면 스크롤 전수 노출·값 추출까지) |
| 촬영할 부위·Step을 제대로 골랐는가 | 인체도 **파란 점 검출 → 국소대비 OCR → 정답지 소거 → 클릭 후 Step 목록 대조** 4단계 (색으로 찾지 않는다 — 4.1절) |
| 영상처리가 성공했는가 | XIPL 서버 로그(UTF-16LE)에 `Parameter file not found`가 없고 DB `INSTANCE`가 늘어남 |
| AI(CAD) 분석이 실제로 동작하는가 | 사내 검증 샘플 영상을 데모 영상으로 등록(무작위 선택) → 분석 실행 → 옵션 체크박스 3종의 체크/해제가 영상 표시에 실제로 반영되는지 **SSIM**으로, 'Copy original image' 저장은 DB `INSTANCE` 증가로 확인 (GPU 없이도 CPU 모드로 정확한 소견을 검출함을 실측) |
| Export/Import가 값을 보존하는가 | DB 62개 테이블 스냅샷 **3단 비교**(S1≠S0 확인 후 S2=S0) |

리포트는 **TXT / CSV / JSON / HTML** 4종으로 생성되고, 모든 포맷 상단에 체크리스트
원본과 같은 형식의 **Windows 정보 + 패키지 정보 헤더**가 들어간다.

```
================================================================================
 VXvue Windows Update 호환성 자동화 결과   (문서번호: R-25-774)
================================================================================
 수행 일시     : 2026-08-18 14:27:54
 [ Windows 정보 ]
   - OS                : Windows 11 Enterprise
   - OS Version        : 25H2
   - OS Build Version  : 26200.8655        <- BuildNumber + UBR 조합
   - Display           : 1920x1080 / 100% (96 DPI)
   - Memory            : 물리 여유 3.91GB / 15.73GB, 페이지파일 여유 30.2GB / 32GB
 [ 패키지 정보 ]
   - VXvue             : 1.0.11.015
   - 릴리즈노트 대조    : FAIL (대조 22건 / 불일치 12 / 경고 3)
 판정 합계     : PASS n / FAIL n / MANUAL n / SKIP n / BLOCKED n
================================================================================
```

---

## 4. 실전에서 부딪힌 문제와 해결

이 절은 **판정을 틀리게 만들었던 원인**만 골라 짧게 남긴다. 각 항목의 실측 근거와
컨트롤 ID는 코드 주석과 [`docs/TC_검증상세.md`](docs/TC_검증상세.md)에 있다.

### 4.1 표준 API로 읽히지 않는 커스텀 UI → 속성 우선, 좌표는 그때그때 계산

제품 UI는 사내 SDK 컨트롤(`AfxWnd140u`)이라 좌측 설정 메뉴는 `GetWindowText`로
라벨이 읽히지 않고 `BM_CLICK`에도 반응하지 않는다. 그래서 이 저장소는 **컨트롤
ID·클래스·텍스트로 대상을 찾고**, 라벨을 표준 API로 읽을 수 없는 곳에서만 위치를
쓴다. 그 위치도 상수로 저장하지 않고 **실행 시점에 찾은 컨트롤의 `rect`에서
계산**한다 — 해상도·테마·스크롤이 바뀌어도 다시 재지 않아도 된다.

관련해서 값 판정도 픽셀에서 값으로 옮겼다. 캡처 SSIM 비교는 테마를 바꾸는 순간
55개 화면이 전부 FAIL이 되는데 실제 설정 값은 그대로다. 목록 상세는 DB 실제
등록값과 대조하고, 스크롤 밖 컨트롤도 전수 열거해 "화면에 보이지 않아 검증되지
않는" 구간을 없앤다(한 화면은 컨트롤 75개 중 57개만 노출되어 있었다).

### 4.2 팝업 하나, 창 하나가 이후 판정 전체를 무의미하게 만든다

설정 저장 뒤 뜨는 확인 팝업을 닫기 전까지 **그 뒤로 보낸 모든 클릭이 조용히
무시된다.** 화면만 보면 "왜 반응이 없지"로 보인다. 저장 성격의 클릭은
`click_and_ack()`로 감싸 팝업을 확인하고 넘어간다.

같은 문제가 규모를 키워 두 번 더 났다.

- 회귀에서 FAIL 10건이 났는데 증상이 제각각이었다. 원인은 **TC 하나가 XIPL
  Studio를 닫지 않은 것** 하나였다 — Studio가 떠 있는 동안 제품이 DICOM 전송을
  아예 시도하지 않는다(Bunny 로그에 C-STORE 0건, C-ECHO만). 그래서 시험이 끝나면
  열어 둔 것을 반드시 닫는다(`close_all_studies()`).
- TC08의 `Import Study` 창이 모달로 남은 채 Close와 조회 클릭이 무시됐고, 리포트에
  `Database 건수 70 → 70`이 남았다 — **조회가 아예 돌지 않았는데 판정 근거처럼
  보였다.** 이제 창이 사라진 것을 확인하기 전에는 그 근거를 쓰지 않는다.

### 4.3 "클릭은 했다"와 "실제로 일어났다"는 다르다

이 프로젝트에서 가장 많이 반복된 실수다.

| 겉모습 | 실제 | 대응 |
|---|---|---|
| Database 목록이 비어 있다 | 제품 내부 인덱싱이 화면 Close보다 늦다(몇 분 뒤 정상 표시) | `database_search()`가 결과가 비면 재시도 |
| Print/Export를 눌렀는데 전송 안 됨 | 확인이 **두 번** 필요하다 — 범위 팝업 + 필름 구성 화면의 Print 버튼 | `confirm_scope_popup()` + `finish_print()` |
| Export 경로를 바꿨는데 이전 경로에 생성됨 | 경로 Edit은 내부 상태의 **표시 전용** | 드라이브 드롭다운·Browse 대화상자로 실제 변경 |
| Import 성공인데 FAIL | 먼저 뜨는 `Importing files ...` **진행 팝업**을 결과로 읽었다 | 진행 문구는 건너뛰고 종료 팝업을 기다린다 |
| Close를 눌렀는데 스터디가 DB에 없다 | `Database > Close`(30275)를 눌러도 **열린 검사가 닫히지 않았다**(`사양 확인 필요`) | 열린 검사 탭 수를 앞뒤로 세어 확인하고, 안 닫히면 Close All 툴로 닫는다 |

마지막 항목이 실제 피해로 이어졌다. 검사가 닫히지 않아 스터디가 DB에 커밋되지
않았고, Export가 **이전 실행의 오래된 스터디**를 대상으로 삼았다.

### 4.4 OCR을 믿을 수 없는 자리에서는 Win32 메시지로 읽는다

커스텀 컨트롤 때문에 OCR을 많이 쓰지만, **표준 컨트롤이 섞인 자리에서 OCR을 쓰면
손해만 본다.** TC08의 폴더 선택 트리(`SysTreeView32`)를 OCR로 읽었더니

```
'바탕 화면'    → 'mvs sa'
'VXvue1 (E:)'  → 'me VXvuel (E)'      ← 1 을 l 로 읽었다
```

한글은 깨지고 영문도 틀려, 부분 문자열 매칭이 **전혀 다른 노드
(`VXvue1.0.11.015(SMZ)`)를 선택하는 사고**로 이어졌다. 표준 컨트롤이므로 `TVM_*` /
`HDM_*` 메시지로 정확히 읽을 수 있다 — 다른 프로세스라 구조체·문자열 버퍼를 그
프로세스 주소공간에 만들어 주는 준비를 `core/winmsg.py`에 한 번만 구현하고,
`core/shelltree.py`(트리)와 `core/listgrid.py`(목록 헤더)가 그것을 쓴다.

주의 하나: `ctypes.windll.user32`는 프로세스 전체가 공유하는 캐시 객체다.
`SendMessageW.restype`을 바꾸자 같은 프로세스의 다른 모듈이 길이 0을 `None`으로
받아 죽었다 — 필요한 원형은 **별도 함수 포인터**로 만들어 쓴다.

### 4.5 잘려 그려진 값·빈 판독을 진짜 값으로 착각하지 않기

목록 셀 값은 OCR로만 읽히는데(행이 텍스트 없는 `ListItem` 자식 창) **열 폭이
좁으면 제품이 값을 잘라 그린다.** `ACC_VX_AUT...`를 그대로 믿으면 잘못된 FAIL이
나고, 반대로 설정 화면에서는 `Accession Num...`을 항목명과 한 방향으로만 비교해
**있는 항목을 없다고 판정**하다 엉뚱한 항목을 추가해 필름에 잘못된 오버레이가
인쇄됐다.

`core/listgrid.py`가 이 문제를 담당한다. 열 이름·x범위는 헤더(`SysHeader32`)에서
메시지로 정확히 얻고(OCR 아님), OCR은 **열 경계로 잘라 낸 셀 한 칸**에만 쓴다.
잘려 보이는 열은 **헤더 경계선을 마우스로 드래그해** 넓혀 다시 읽고 **원래 폭으로
되돌린다**(폭 값만 바꾸면 owner-draw 목록이 셀을 다시 안 그릴 수 있다). 판정에 쓸
열이 비어 읽히는 경우도 같이 넓힌다 — 폭 30px인 `Age` 열은 잘린 표시 없이 그냥
빈 문자열로 읽혔다. 끝까지 잘린 열은 일치로 세지 않고 따로 표시한다.

필름 OCR도 같은 계열의 교훈이었다. 1318×1600 필름을 통째로 읽으면 모서리 오버레이
글자를 Tesseract가 글자로 보지 않는다 — **네 모서리 띠만 잘라 확대**해 읽자 4개
라벨이 모두 평문으로 나왔다.

### 4.6 고정된 시험 데이터는 검증을 공허하게 만든다

시험 처방이 고정값(`VXVUE_MWL_DX_01`)이라 Database에 같은 Patient ID의 스터디가
수십 건 쌓였고, 역방향 Import 판정이 "Export한 그 스터디가 돌아왔다"가 아니라
**"같은 ID를 가진 어떤 스터디가 있다"** 밖에 확인하지 못했다.

`core/testdata.py`가 MWL 처방을 만드는 시점에 실행 시각을 각인한다
(`VXVUE_260821_150947`). 성별·생년월일은 난수가 아니라 **그 각인을 시드로** 뽑아
리포트 값만 보고 재현할 수 있게 했다. Procedure Code 계열은 매핑 대상이라 고정한다.

효과는 즉시 나타났다. 각인 후 첫 실행에서 TC08이
`기대=VXVUE_260821_150157 / 실제=VXVUE_MWL_DX_01`로 FAIL을 냈다 — 위 4.3절의
Close 결함이 그 순간 드러난 것이다. 고정 ID였다면 계속 PASS로 가려졌다.

### 4.7 회귀가 71분 걸린 이유는 제품이 느려서가 아니었다

대기값을 줄이려 하기 전에 **먼저 계측했다.** `time.sleep`, OCR, 캡처, 컨트롤 열거,
DB 조회를 각각 감싸 TC 하나의 소요를 쪼갰더니 고정 대기는 26%였고, 지배적 비용은
**컨트롤 트리를 중복 열거하는 자기 자신**이었다(`children()` 한 TC에서 85만 회
호출). 중복 제거로 depth 4 기준 6.10초 → 0.28초가 됐다. 범위를 깎지 않고
72분 → 39분 27초로 줄었다.

**교훈은 순서다** — 범위를 줄이기 전에 자동화가 스스로 만드는 낭비를 먼저 없앤다.

### 4.8 제품 설정을 오염시킨 일 (되돌린 기록)

Procedure Mapping을 자동화하려다 실측하지 않은 버튼 경로를 타서 `TB_PROCEDURE`에
없던 Procedure가 생성됐다. 되돌리고 그 기능을 끈 뒤, **Step 등록으로 우회**하는
방식으로 바꿨다. 이 사건 이후 규칙을 굳혔다 — 실측하지 않은 컨트롤은 누르지
않는다. DB는 조회 전용이고, 쓰기는 백업/복원 경로에서 명시적 승인으로만 한다.

또 Export 산출물은 확장자만 보면 설정 파일 같지만 **ZIP 안에 DB 전체 백업**이
들어 있었다. 즉 Import는 "설정 되돌리기"가 아니라 DB 전체 복원이다 — 파괴적
조작으로 분류해 승인 없이는 실행하지 않는다.

## 5. 실행 방법

### 5.1 준비

```bash
python -m pip install -r requirements.txt
```

```bash
copy config.example.json config.json
```

`config.json`에 이 PC의 값을 채운다. **확인되지 않은 값은 빈 문자열로 두고 임의
값을 넣지 않는다** — 자동화가 "설정이 비어 있어 건너뜀"으로 정직하게 보고한다.

| 키 | 내용 |
|---|---|
| `install_dir` / `viewer.exe` | VXvue 설치 경로 (기본 `C:\Program Files\Vxvue`) |
| `data_dir` | 데이터 폴더. **PC마다 다르다** (이 시험대는 `D:\Database`, 다른 PC는 `C:\Database`). 라이선스 `.lic`과 운영 로그가 이 아래에 있어 초기화 대상 판단에 쓴다 |
| `sql_server` / `database` | SQL Server 인스턴스와 DB(기본 `.\CHAMELEON` / `DRF`) |
| `viewer.login` | 자동 로그인 계정 |
| `dicom.servers_to_register` | 등록·Echo를 확인할 MWL / Storage / Print SCP 목록 |
| `baseline.db_backup` / `baseline.folder_backup` | 클린 설치 시점 기준 백업. `--reset-baseline`이 이 값으로 되돌린다 |
| `checklist_xlsx` | 체크리스트 원본. 없으면 저장소 상위(`VXvue/`)에서 자동으로 찾는다 |
| `xipl.tesseract_exe` | Tesseract-OCR 실행 파일 (owner-draw 목록 판독에 필요) |

**필수 조건**

- **관리자 권한** — VXvue가 관리자 권한으로 동작하므로, 자동화가 일반 권한이면
  Windows UIPI가 합성 입력을 차단한다. 이때 **캡처는 되고 클릭만 조용히 실패**해
  엉뚱한 증상으로 보인다. `preflight`가 NG로 막는다.
- **1920×1080 @ 100%(96 DPI)** — DPI는 로그아웃 없이 안전하게 바꿀 수 없어
  100%가 아니면 중단한다(사람이 먼저 바꿔야 한다).
- Tesseract-OCR, SQL Server 인스턴스, (Storage Echo용) Bunny.exe

**물리 메모리 여유는 차단 조건이 아니다.** 이 시험 PC는 XIPL.SERVER 등 상주
프로세스 때문에 여유가 항상 기준(3GB) 아래다. 사용자 판단으로 `WARN`까지만
올리고 실행은 계속하며, 대신 뷰어 기동·화면 진입이 실패하면 그 시점 메모리를
다시 읽어 판정 `note`에 남긴다(`preflight.memory_pressure()`). 판단을 실행 전
추측에서 **실패 시점의 실측**으로 옮긴 것이다.

```bash
python run.py preflight
```

### 5.2 뷰어 기동·로그인

UI를 조작하는 명령은 VXvue가 이미 떠서 로그인된 상태를 전제하지 않는다 —
`_ready_ui()`가 필요하면 기동·로그인까지 한다. 다만 처음 한 번은 상태를 눈으로
확인하는 편이 낫다.

```bash
python work/launch_login.py
```

### 5.3 전체 회귀

**표준 실행(사용자 지시, 2026-08-25)은 baseline 초기화를 기본 수행한다** — 정식
전체 회귀는 항상 설치 직후와 같은 클린 DB/폴더 상태에서 시작하며, 매 실행 전
별도 승인을 다시 묻지 않는다:

```bash
python run.py run-regression
```

기존 `--reset-baseline` 옵션은 이전 명령과의 호환을 위해 남아 있지만 이제
붙이지 않아도 같은 동작이다. 임시 확인(짧은 반복 테스트, 디버깅)에서만
`--no-reset-baseline`을 명시해 Phase 1을 생략하며, 생략 사실은 SKIP으로
리포트에 남는다.
**정식 판정에는 항상 위 명령을 쓸 것.**

Phase 순서대로 실행하고 **모든 결과를 리포트 1건으로 합친다.**

| Phase | 내용 | 기본 동작 |
|---|---|---|
| 0 | `preflight` → `mwl-ensure`(당일 DX 처방 보장) → `xipl-license` | 항상 수행 |
| 1 | DB/폴더를 클린 baseline으로 복원 (라이선스·로그는 왕복 백업으로 보존) | **기본 수행** — `--no-reset-baseline`으로만 생략 |
| 2 | VXvue 자체 라이선스 확인 (Setting > System > License) | 항상 수행 |
| 3 | DICOM SCP 등록 확인·구성 + C-ECHO (MWL / Storage / Print) | 항상 수행 |
| 4 | 구현된 TC 실행 → (미구현 TC는 `automation_scope.json` 수준 표시) | 항상 수행 |

baseline 복원은 전체 회귀의 코드 기본값이다. `--no-reset-baseline`으로 생략하면
그 사실을 리포트에 `SKIP`으로 남기며, 그 실행은 정식 판정으로 사용하지 않는다.

**Setting Export/Import는 이 회귀에 들어 있지 않다**(사용자 지시, 2026-08-20).
성격이 다르다 — 이 회귀는 Windows Update 후 제품이 정상 동작하는지 보는 것이고,
그쪽은 설정 백업·복원 기능 자체의 회귀로 DB를 통째로 되돌린다(실측 1021초로
단일 항목 중 최장이었다). 회귀에 섞으면 뒤 TC의 시작 상태를 바꾸고 실행 시간도
전체를 지배한다. 5.5절의 `setting-export-import`로 따로 돌린다.

```bash
python run.py run-regression
```

DB와 `data_dir` 폴더를 클린 설치 시점으로 되돌린 뒤 회귀를 시작한다. 현재 DB의
환자·검사·설정이 **전부 사라진다.** 라이선스(`.lic`)와 운영 로그(`log/`)는
되돌리기 직전에 떠서 복원 후 다시 덮어쓴다(라이선스는 하드웨어 키에 묶여 있어
기준 백업에 값으로 남기지 않는다). `Bak/`(DB 백업 이력)은 절대 지우지 않는다.

```bash
python run.py run-regression --quick
```

**짧은 회귀.** 촬영을 TC02에서 한 번만 하고 뒤 TC는 그 영상을 재사용하며,
TC14는 대분류별 첫 화면만 본다. **확인하는 범위가 줄어든다** — 무엇을 줄였는지는
리포트의 `Quick_Mode` 항목과 각 TC의 해당 판정에 남는다. 빠른 이상 감지용이고,
**체크리스트에 기록할 정식 판정은 전체 회귀로 받아야 한다.**

`--quick`을 만들기 전에 먼저 한 일이 있다 — 4.7절 참고. 회귀가 71분이나 걸린
주된 이유는 제품을 기다리는 시간이 아니라 자동화가 스스로 만든 낭비였고, 그쪽을
고치는 것이 범위를 줄이는 것보다 먼저였다.

```bash
python run.py run-regression --only TC_WindowsUpdate_14
```

디버깅용. 지정한 TC만 실행하고 나머지는 리포트에서 제외한다. Phase 0/2/3은
그대로 수행한다(선행조건이 갖춰지지 않은 상태에서 TC를 돌리지 않기 위함).

```bash
python run.py run-regression --no-env
```

리포트 상단 환경 헤더 수집(ModelVersionChecker 실행)을 생략한다. 헤더 수집만
수십 초가 걸리므로 반복 디버깅에 쓴다. **정식 회귀에서는 쓰지 않는다** — 어떤
빌드에서 나온 결과인지가 리포트의 핵심 정보다.

```bash
python run.py run-regression --no-checklist
```

체크리스트 xlsx 사본 기록을 생략한다.

### 5.4 개별 TC 실행

각 TC는 단독으로도 돌아간다. 회귀에서 한 TC만 다시 확인할 때 쓴다.

자동화 코드 파일명은 **TC ID와 1:1로 맵핑**한다(`tests/tc02_*.py` →
`TC_WindowsUpdate_02`). 체크리스트에 대응 TC가 없는 자체 회귀만 번호 대신 이름을
쓴다(`tc_setting_export_import.py` → `TC_Setting_ExportImport`).

| 명령 | 검증 내용 | 대략 소요 |
|---|---|---|
| `python run.py tc02` | **TC02 MWL 조회 워크플로우** — MWL 조회 → 목록 표시값 대조 → Study 등록 → **Chest/PA Step 등록 후 촬영** → DICOM Send → **수신 파일 태그가 MWL 등록값과 일치하는지** → Close → DB 대조 | **173초** |
| `python run.py tc03` | **TC03 영상 조작** — Interpolation Mode 변경·원복 + Select/Zoom/Pan/CW/CCW 툴 적용을 **영상 영역 캡처 SSIM으로 판정** | **219초** |
| `python run.py tc04` | **TC04 Image Processing** — 정확한 MWL 대상 → Exposure 레이아웃 → Chest/PA Step → 촬영(DB INSTANCE) → XIPL 로그 → 확장 팔레트 → `Proc.` → `XIPL.STUDIO` → **Studio 정리** | **299초** |
| `python run.py tc05` | **TC05 DICOM 전송** — 촬영 → Send → 수신 객체의 SOP Class UID로 Image/Dose SR 포함 여부 판정. 이 자동화는 DX만 검증하므로 MG 전용 Dose SR은 범위 밖(SKIP) | 약 4분 |
| `python run.py tc07` | **TC07 DICOM Print** — Print SCP 가동 확인 → 촬영 → Print → **받은 쪽 서버의 필름 목록으로 판정**(Calling AE로 다른 제품 필름과 구분) | 약 4분 |
| `python run.py tc08` | **TC08 Study Export** — E 드라이브로 Export → 산출물 DICOM 태그 대조 → QXLink 포함 확인. 알려진 결함 **#21049**(Win11 Export 에러) 회귀 | 약 3분 |
| `python run.py tc13` | **TC13 Import Patient** — Study > Import Patient 설정 → 환자정보 txt/csv Import → Registration-Reserved 목록 표시까지. TAB 구분자 회귀(#22985) 포함 | 316초 |
| `python run.py tc13 --with-folder-watch` | 위에 더해 "Import Patient Information From a Specific Folder"(폴더 자동 감지) 경로까지. Import Patient Order와 **상호 배타**라 기본은 끔 | — |
| `python run.py tc14` | **TC14 Setting 각 탭 표시 확인** — 대분류 10개를 펼쳐 소분류 55개 화면을 열고, 제목이 실제로 바뀌는지·본문이 그려지는지 확인 + 화면별 캡처 1장 | **182초** |
| `python run.py tc14 --deep` | 위에 더해 **스크롤 전수 노출 확인 + SCP 상세 DB 대조 + 옵션 구성 기준 대조**. 폰트·DPI 변화로 화면 밖으로 밀려 조작할 수 없게 된 설정을 잡아낸다 | 1219초 |
| `python run.py setting-export-import` | **Setting Export/Import 회귀** — 3단 비교(S0 → Export → 변경 → S1 → Import → S2). 파괴적 | — |
| `python run.py setting-export-import --no-import` | 위에서 Import 단계만 생략(Export까지) | — |
| `python run.py vxvue-license` | **VXvue 자체 라이선스** — Setting > System > License의 Hardware Key / 목록 3행(Demo·CAD·Live View) / Add·Change·Delete 버튼을 확인하고 설치된 `.lic` 파일과 대조 | 약 30초 |
| `python run.py xipl-license` | **XIPL 영상처리 라이선스 4종** — XIPL.SERVER About 창 판독. 위 항목과 **다른 검증**이다(VXvue 본체 라이선스 ≠ XIPL 라이선스) | 약 10초 |

촬영이 필요한 TC(02/03/05/07/08)의 공통 옵션:

| 옵션 | 뜻 |
|---|---|
| `--no-acquire` | 촬영 단계를 건너뛰고 **이미 열려 있는 영상**을 쓴다. 반복 디버깅용 |
| `--no-send` | (tc02) 마지막 DICOM Send를 생략한다 |
| `--map-procedure [이름]` | MWL 처방의 Procedure Code를 지정 Procedure(기본 `Chest PA`)에 매핑한다. **제품 설정을 바꾸는 조작이라 기본은 하지 않는다** — 현재는 안전장치 미비로 코드에서 비활성(`core/workflow.ENABLE_PROCEDURE_MAPPING`), 자세한 사정은 4.8절 |

### 5.5 조사·진단 명령

TC를 새로 구현하거나 화면 구조가 바뀌었을 때 쓰는 조회 전용 명령이다.

| 명령 | 내용 |
|---|---|
| `python run.py ui-probe` | 지금 떠 있는 VXvue 화면의 컨트롤 트리를 덤프한다. **새 화면을 자동화할 때 첫 단계** — 컨트롤 ID·클래스·rect를 여기서 실측한다 |
| `python run.py ui-probe --save dump.txt --depth 8 --all` | 파일로 저장 / 탐색 깊이 조정 / 숨은 컨트롤 포함 |
| `python run.py scope` | TC별 자동화 수준(FULL/PARTIAL/MANUAL/BLOCKED/EXCLUDED)과 그 판단 근거 |
| `python run.py env` | 리포트 헤더용 Windows/패키지 정보를 JSON으로 출력 |
| `python run.py db-ae [--kind DICOM_MWL]` | DB(`AE_LIST`) 기준 등록된 SCP 목록. UI 표시와 교차 확인용 |
| `python run.py mwl-list` | 시험 Worklist 서버의 처방 목록 |
| `python run.py mwl-ensure [--date YYYY-MM-DD]` | VXvue 전용 DX 시험 처방을 그 날짜로 보장(지난 처방은 지우고 재생성) |
| `python run.py snapshot [--label 이름]` | 설정 스냅샷(DB 62개 테이블 + 설정파일 해시)을 파일로 저장 |
| `python run.py snapshot-diff --a A.json --b B.json` | 두 스냅샷 비교 |
| `python run.py vxs-info --a export.vxs [--b other.vxs]` | Export 파일(`.vxs`) 구성 판독 / 두 파일 비교 |
| `python run.py report-sample` | 리포트 4종 형식 확인(판정은 비어 있음) |
| `python run.py design-report [--save 경로]` | TC별 **설계**(Step 구성·판정 근거) HTML 리포트를 `tests/tc*.py` docstring과 `automation_scope.json`에서 뽑아 생성한다(기본 `docs/TC_설계리포트.html`). 특정 실행의 PASS/FAIL이 아니라 "코드가 무엇을 검증하도록 설계됐는가"를 본다 — 코드가 바뀌면 다음 생성 때 그대로 반영된다 |

### 5.6 결과물

| 위치 | 내용 |
|---|---|
| `Reports/Result_<시각>.html` | 사람이 읽는 판정 리포트(판정별 색상 구분) |
| `Reports/Result_<시각>.txt` | 콘솔·메일에 붙이는 텍스트 리포트 |
| `Reports/Result_<시각>.json` | 기계 판독용 전체 판정·근거·소요시간 |
| `Reports/Result_<시각>.csv` | 표 계산용 |
| `Reports/Checklist_Result_<시각>.xlsx` | **체크리스트 원본 사본에 판정 열을 덧붙인 것.** 원본은 읽기만 한다 |
| `Evidence/` | 단계별 화면 캡처(실패 원인 추적용) |

리포트 4종 **모두** 상단에 체크리스트 원본과 같은 형식의 Windows 정보 + 패키지
정보 헤더가 들어간다. 어떤 빌드·어떤 OS에서 나온 결과인지 없이는 판정이 근거가
되지 않기 때문이다.

체크리스트 xlsx 사본에는 원본 TC 행 오른쪽에 `자동화 판정 / 판정 일시 /
PASS·FAIL·MANUAL·SKIP·BLOCKED 건수 / 실패 항목 / 수동 확인 항목 / 증거` 열이
붙는다. 사람이 손으로 채운 `Result` / `Comment` 열은 **건드리지 않는다.**
이번 실행에 포함되지 않은 TC는 빈칸이 아니라 **`미수행`** 으로 적는다 — 빈칸으로
두면 "확인했는데 이상 없음"으로 오해되기 때문이다.

### 5.7 실행 중 유의사항

- **실제 마우스 커서를 점유한다.** 실행 중에는 같은 세션에서 다른 작업을 하기
  어렵다. 원격 데스크톱 세션을 최소화하면 화면 캡처가 검게 나온다.
- **같은 VXvue 인스턴스를 두 개의 자동화가 동시에 조작하면 충돌한다.** 조사용
  세션과 실행용 세션을 분리할 것.
- **`Use virtual keyboard`(Setting > System - Theme)가 켜져 있으면 안 된다.**
  화상 키보드가 뜨면 입력이 그쪽으로 간다.
- Setting Export/Import는 설정을 실제로 바꾼다. 회귀 순서상 **맨 마지막**에 두고,
  Import는 명시적 승인 없이 수행하지 않는다.

---

## 6. 회귀 실적

`python run.py run-regression` **가장 최근 전체 실행**만 적는다. 실행 회차를 이
문서에 쌓지 않는다 — 회차별 이력·TC별 소요 비교는 실행 리포트(`Reports/`)와 별도
상세 기록에 있다.

| 실행 | 판정 합계 | 소요 |
|---|---|---|
| 2026-08-24 08:10 | PASS 120 / FAIL 2 / MANUAL 13 / SKIP 5 / BLOCKED 0 | 21분 |

이 실행은 화면 캡처 오염 방지 수정(`core/screen.looks_contaminated()`)이
실제로 통했음을 확인했다 — 직전 회귀의 FAIL 2건(`VXvue_License`,
`DICOM_Servers`)이 각각 MANUAL/PASS로 해소됐다. 대신 **새 FAIL 2건**이
나왔고 둘 다 원인을 규명·수정했다: `TC_WindowsUpdate_05`는 Dose SR
미수신이 결함이 아니라 DX 촬영에는 애초에 해당하지 않는 검증이었음을
DICOM Conformance Statement로 확인했다. 2026-08-25에 검증 범위를 DX로
확정하면서 이 항목은 MANUAL에서 범위 밖 SKIP으로 재조정했다. `TC_WindowsUpdate_11`
은 툴 팝업이 스스로 닫히는 것과 재오픈 클릭이 경쟁하던 타이밍 버그를
고쳤다. 두 수정 모두 개별 재실행으로 확인했으나(TC05 당시
`PASS 6/FAIL 0/MANUAL 1`, 이후 DX 범위 결정으로 마지막 항목은 SKIP;
TC11 `PASS 9/FAIL 0/MANUAL 1`), **셋을 함께
반영한 전체 회귀 재실행은 두 차례 환경 문제로 끝까지 완료하지 못했다**
(중간에 프로세스가 외부 요인으로 중단됨 — 제품/코드 결함 아님). 다음
회귀 실행에서 최종 확인할 것.

소요가 72분 → 39분으로 줄어든 경위는 4.7절에 있다(확인 범위를 줄인 것이 아니다).

---

## 7. 성능

55개 화면을 매번 도는 시험이라 화면당 비용이 전체를 지배한다. 프로파일링으로
세 지점을 고쳤다.

| 항목 | 개선 전 | 개선 후 | 방법 |
|---|---|---|---|
| 화면 캡처 | 0.20s | **0.04s** | 가상 데스크톱 전체(5560×2297)를 잡고 자르던 것을 주 모니터만 캡처 |
| 컨트롤 열거 | ~2.5s | **0.24s** | 전체 창 트리 재귀 탐색 → 프레임 창의 직속 자식만 조회 + hwnd 캐시 |
| 화면 전환 | 13.1s | **1.7s** | 같은 화면 재진입 시 제목이 안 바뀌어 매번 타임아웃(10s)을 소진하던 것을, 본문 대화상자 교체를 전환 신호로 함께 인정 |

그 뒤 전체 회귀를 다시 프로파일링해 더 큰 것을 찾았다(4.7절). **추측하지 않고
`time.sleep`·OCR·캡처·컨트롤 열거·DB 조회를 각각 감싸 측정한 것이 핵심이었다** —
느린 곳이 예상과 달랐다.

| 항목 | 개선 전 | 개선 후 | 방법 |
|---|---|---|---|
| `children()` (depth=4) | 6.10s | **0.28s** | `EnumChildWindows`가 이미 전체 자손을 열거하는데 그 각각에 다시 재귀해 같은 창을 최대 64배 중복 담고 있었다. 한 번만 열거하고 중복 제거 |
| TC03 1회 | 143.8s | **34.5s** | 위 수정 + 클릭 뒤 고정 대기를 조건 대기로(`ui.VXvueUi.wait_settle`) |
| TC14 1회 | 1219s | **182s** | 체크리스트 원문 수준(탭 순회·표시 확인)으로 되돌리고 전수 검증은 `--deep`으로 분리 |
| **전체 회귀** | **72분** | **39분 27초** | 위 전부. 확인 범위를 줄이지 않고 얻은 결과 |

측정값은 모두 이 PC(1920×1080 / 100% DPI, 메모리 여유 3GB 안팎) 실측이다.

---

## 8. 아키텍처

```
auto/
├─ run.py                     CLI 진입점
├─ automation_scope.json      TC별 자동화 수준 (FULL/PARTIAL/MANUAL/BLOCKED/EXCLUDED)
├─ config.example.json        설정 템플릿 (실제 값은 config.json, Git 제외)
├─ core/
│  ├─ ui.py                   Win32 UI 드라이버 + 제품 고유 함정 흡수
│  ├─ winmsg.py               표준 컨트롤에 Win32 메시지 보내기 (원격 버퍼 준비 공통화)
│  ├─ shelltree.py            표준 SysTreeView32(폴더 찾아보기)를 OCR 없이 읽고 조작
│  ├─ listgrid.py             표 목록을 열 이름·셀 값으로 읽기 (잘린 열은 드래그로 넓혀 재판독)
│  ├─ workflow.py             촬영·전송·설정 조작 등 제품 워크플로 공통 함수
│  ├─ dialogs.py              팝업 분류(정보/질문/차단/상호작용)와 처리 정책
│  ├─ setting.py              설정 화면 순회 엔진 (스크롤·목록 상세·값 추출)
│  ├─ screen.py               캡처 / SSIM / 빈 화면 판정
│  ├─ context.py              라이선스·연동·테마 컨텍스트와 서명 이원화
│  ├─ config_snapshot.py      설정 스냅샷 (DB 62개 테이블 + 파일 해시)
│  ├─ vxs.py                  Export 파일(ZIP) 판독·비교
│  ├─ dbreset.py              DB/폴더 백업·복원 — 파괴적 조작 전용, 승인 필수
│  ├─ dicom_settings.py       DICOM SCP(MWL/Storage/Print) 등록·Echo 자동화
│  ├─ dicomlite.py            의존성 없는 DICOM 태그 판독기
│  ├─ db.py                   DB 조회 전용 브릿지 (쓰기 API 없음)
│  ├─ mwl.py                  Worklist 시험 서버 HTTP 클라이언트
│  ├─ printscp.py             Print SCP 시험 서버 클라이언트 + 수신 필름 픽셀 OCR
│  ├─ bunny.py                Storage(Bunny) 시험 서버 클라이언트
│  ├─ testdata.py             실행마다 구분되는 시험 처방 생성·기록·지난 처방 정리
│  ├─ license.py              VXvue 본체 라이선스 확인 (화면 OCR + .lic 파일 대조)
│  ├─ xipl.py                 XIPL 영상처리 라이선스 확인 + UTF-16 로그 판독
│  ├─ specs.py                사양서·매뉴얼 PDF에서 근거를 찾아 쪽·VP번호까지 인용
│  ├─ checklist.py            체크리스트 xlsx 사본에 판정 열 기록 (원본은 읽기만)
│  ├─ design_report.py        TC 설계(Step·판정 근거) HTML 리포트 생성 (docstring+scope에서 추출)
│  ├─ watchdog.py             상태 기반 대기·재시도·팝업 가드·단계 실패 격리
│  ├─ sysinfo.py              환경 조회 (WMI 비의존)
│  ├─ package_info.py         패키지 버전 수집
│  ├─ preflight.py            실행 전 환경 점검 + 실패 시점 메모리 근거
│  ├─ result.py               판정 모델 + 리포트 4종
│  └─ regression.py           체크리스트 전체 회귀 러너 (Phase 0~5, scope 반영)
└─ tests/
   ├─ tc02_mwl_workflow.py           MWL 조회 → 촬영 → Close → Database 확인
   ├─ tc03_image_display.py          영상 표시·조작 도구
   ├─ tc04_image_processing.py       Image Processing / XIPL Studio
   ├─ tc05_dicom_send.py             DICOM Storage 전송 (받은 쪽 서버로 판정)
   ├─ tc07_dicom_print.py            DICOM Print + Print Overlay (수신 필름 픽셀로 판정)
   ├─ tc08_study_export.py           외부 매체 Export → 산출물 검증 → 역방향 Import → 매체 정리
   ├─ tc13_import_patient.py         환자정보 txt/csv Import 회귀 (팝업 처리, TAB 구분자 결함 회귀)
   ├─ tc14_setting_display.py        설정 55화면 전수 검증
   └─ tc_setting_export_import.py    Export/Import 보존 회귀 (3단 비교)
```

### 의존성

`requirements.txt` 4개 + 표준 라이브러리가 전부다.

| 패키지 | 쓰는 곳 |
|---|---|
| `Pillow` | 화면 캡처(`ImageGrab`), 체크박스 색 판별 |
| `pytesseract` | owner-draw 목록·로그 영역 OCR (Tesseract 본체는 별도 설치) |
| `openpyxl` | 체크리스트 xlsx 읽기·결과 기록 |
| `pypdf` | 사양서·매뉴얼 PDF 근거 검색 (`core/specs.py`) |

UI 자동화 프레임워크(`pywinauto`), 프로세스 라이브러리(`psutil`), DICOM
라이브러리(`pydicom`), DB 드라이버(`pyodbc`)는 **쓰지 않는다.** 검증 PC에 추가
설치를 요구하지 않는 것이 목적이다. Win32 조작은 `ctypes`로 직접 하고, DB
접근은 PowerShell + .NET `SqlClient` 브릿지로 처리한다. `scikit-image`가 있으면
SSIM에 쓰고, 없으면 numpy 구현으로 대체한다.

### 설계 규칙

1. **DB는 조회만 한다.** 설정 변경은 반드시 제품 UI를 거쳐야 검증 의미가 남는다.
   파괴적 조작은 별도 모듈로 격리하고 명시적 승인 인자를 요구한다.
2. **좌표를 저장해 재사용하지 않는다.** 매번 다시 열거하고, 필요하면 대상이
   보일 때까지 스크롤해서 끌어온다.
3. **다른 제품의 컨트롤 ID를 가져다 쓰지 않는다.** 설계 원칙만 재사용한다.
4. **확인되지 않은 값을 실제 값처럼 적지 않는다.** 사양이 불확실한 항목은
   `MANUAL`로 남기고 무엇을 확인해야 하는지 함께 적는다.
5. **판정 기준은 화면이 아니라 사양서·매뉴얼에서 가져온다.** 화면에서 보이는
   동작으로 합격 기준을 역산하면 결함을 정상으로 인증해 버린다. 그래서
   `core/specs.py`로 사양서 PDF를 코드에서 직접 검색해 **쪽 번호와 요구사항
   ID(`VP-415` 등)까지 판정 `note`에 남긴다.**
6. **하나의 근거만 믿지 않는다.** 라이선스는 화면(OCR)과 `.lic` 파일 양쪽에서
   확인하고 서로 대조한다. OCR은 `1`을 `L`로 읽는 오인식이 있어(실측) 키
   대조의 1차 근거로 쓰지 않는다.
7. **자원 부족을 제품 결함으로 보고하지 않는다.** 물리 메모리가 부족해도
   실행을 막지 않되(이 PC는 항상 부족하다), 실패하면 그 시점 메모리 여유를
   판정 `note`에 남겨 사후에 구분할 수 있게 한다.
8. **컴파일 통과를 검증으로 여기지 않는다.** `python -m py_compile`은 `import`
   누락을 잡지 못한다 — `os.path.join`을 쓰면서 `import os`를 빠뜨려도 통과하고
   **실행 시점에** 죽는다. 그래서 바꾼 모듈은 실제로 import 해 새 함수를 한 번
   호출해 본다(자매 프로젝트에서 이 한 줄로 회귀가 첫 단계에서 무너져 TC 14개가
   연쇄 실패한 전례가 있다).

---

## 9. 범위와 한계

자동화하지 않는 것을 명시하는 것도 설계의 일부다.

| 항목 | 처리 | 이유 |
|---|---|---|
| 실제 X-ray 노출 | 하지 않음 | Demo 라이선스 + 가상 제너레이터로 촬영 흐름만 검증 |
| 물리 매체(CD/USB) 삽입·굽기 | MANUAL Step | 사람이 매체를 넣어야 한다 |
| PC 재부팅이 필요한 TC | MANUAL | 재부팅 전후 상태를 자동화가 이어받기 어렵다 |
| OS 계정 전환 후 실행 | 범위 제외 | 세션 전환이 필요하다 |
| 원격 PACS 전송 검증 | MANUAL (추후) | 다른 PC의 서버 접근이 필요하다 |
| 체크박스 on/off | DB로 검증 | UI에서 상태를 읽을 수 없다 |
| GPU 필요한 3D 산출물 | SKIP (규칙화) | 검증 PC에 CUDA GPU가 없다. 라이선스·UI 흐름은 검증 |
| Procedure ↔ Code 매핑 | 하지 않음 | 제품 설정을 바꾸는 조작이고, 자동화가 잘못 눌러 Procedure를 하나 만든 사고가 있었다(4.8절). 사람이 한 번 매핑한 뒤 회귀를 돌린다 |
| Export Manager 창 내부 조작 | **자동화됨**(2026-08-21) | 별도 프로세스(`VX.EXPORT.MANAGER`)의 드라이브·경로·형식(DICOM+IMG) 지정과 Start까지 캡처+OCR·픽셀 색으로 실측해 자동화했다(4.3절) |
| Setting > DICOM - General 의 Send Dose SR | **DX 범위에서 자동화됨** | Yes/No 라디오 컨트롤 ID를 2026-08-21 실측해 상태 확인·전환·원복까지 자동화했다. 다만 DICOM Conformance Statement상 Dose SR은 MG 영상 전용이며 이 프로젝트는 DX만 검증하므로 Dose SR 미수신 자체는 범위 밖(SKIP)이다 |
| Export된 스터디의 역방향 Import | **자동화됨**(2026-08-21) | 폴더 선택 트리를 `TVM_*` 메시지로 정확히 읽고(4.4절), 목록 각 열 값을 Export한 DICOM 태그와 대조하고(4.5절), 결과 팝업·창 닫힘·DB 건수 증가를 함께 근거로 쓴다. `--no-import`로 끌 수 있다. VXvue 자체 Import는 IMG만 받으므로(Operation Manual 8.14) Export에서 DICOM+IMG를 함께 만든다 |
| 시험 후 Export 매체 정리 | **자동화됨**(2026-08-21) | 설정된 Export 대상 폴더 안만 비운다. 드라이브 루트이거나 설정과 다른 경로면 아무것도 지우지 않는다. `--keep-export`로 끔 |
| XIPL Studio 재처리(TC04) | MANUAL | `C:\XIPL\PARAMETER` 구성과 서버 재시작으로 촬영 처리 및 Studio 기동은 확인됐다. WPF 내부 컨트롤 실측 후 로드·Process 조작을 추가해야 한다 |

UI를 조작하는 명령은 **관리자 권한**으로 실행해야 한다(제품이 관리자 권한으로
동작하므로, 권한이 낮으면 Windows UIPI가 합성 입력을 차단한다). 또 실제 마우스
커서를 점유하므로 실행 중에는 같은 세션에서 다른 작업을 하기 어렵다.

---

## 10. 문서

| 문서 | 내용 |
|---|---|
| `docs/TC_검증상세.md` | **각 TC가 코드상 어떤 Step을 밟고 무엇을 Expected Result로 확인하는지**의 명세. 특정 실행의 PASS/FAIL 결과(`Reports/`)와는 별개로, "코드가 무엇을 검증하도록 설계돼 있는가"를 다룬다. 회귀 러너의 Phase 구성과 촬영·전송 공통 인프라의 실측 컨트롤 ID도 여기 정리돼 있다 |
| `docs/design-VXvue-Windows-Update-호환성-자동화-설계.md` | TC별 설계와 실측 기록, 확인 필요 항목(마스킹 사본) |
| `docs/design-VXvue-Setting-Export-Import-회귀-설계.md` | 3단 비교 설계(마스킹 사본) |
| `automation_scope.json` | TC별 자동화 수준(FULL/PARTIAL/MANUAL/BLOCKED/EXCLUDED)과 **그 판단 근거**. 수준을 올리거나 내릴 때 반드시 `reason`에 근거를 남긴다 |
| `docs/TC_설계리포트.html` | 위 명세를 **코드에서 뽑아 렌더링**한 리포트(`python run.py design-report`). 손으로 쓰지 않으므로 코드와 어긋나지 않는다 |
| `requirements.txt` | 의존성 4개와 각각을 쓰는 곳 |

이 README는 **포트폴리오 문서**다 — 설계 의도와 핵심 교훈만 담고, 실행 회차별
수치나 사고 경위 전문은 쌓지 않는다. 그런 상세 기록은 저장소 밖(비공개 작업 폴더)에
별도로 관리한다.

**TC 자동화 코드를 추가하거나 Step 구성을 바꿀 때는 `docs/TC_검증상세.md`도 같은
커밋에서 갱신한다.** 코드와 문서가 어긋나면 코드를 기준으로 문서를 맞춘다.

자동화 코드 파일명은 **TC ID와 맵핑**한다(`tests/tc02_*.py` →
`TC_WindowsUpdate_02`). 각 모듈의 `TC_ID` 상수가 `core/regression.IMPLEMENTED`의
키와 일치해야 한다 — 어긋나면 리포트의 TC ID와 실행된 코드가 달라져 체크리스트
기록이 엉뚱한 행에 들어간다.

작업 인수인계·다음 작업 큐(`HANDOFF.md` / `NEXT_TASK.md`)와 판단 기준
문서(`CLAUDE.md`)는 이 저장소 상위 폴더(`VXvue/`)에서 관리한다. 사내 실측
기록·사양 원문 인용이 섞여 있어 이 공개 저장소에는 포함하지 않는다.
