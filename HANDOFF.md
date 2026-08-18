# VXvue 자동화 인수인계 (2026-08-18 세션)

이전 세션이 토큰 한계로 끊긴 지점부터 이어받아 진행한 내용과, 다음 세션에서
할 일을 정리했다. **다음 목표는 명확하다 — 체크리스트 전체 회귀를 실제로
수행해서 TC별 PASS/FAIL 결과를 보는 것.** 지금은 그 직전 단계까지 와 있다.

---

## 1. 이번 세션에서 요청받아 고도화한 내용

요청한 순서대로 정리했다. 모두 실측으로 확인하고 근거를 코드 주석에 남겼다.

### 1.1 VXvue 전용 DX MWL 처방 생성 (요청: "DX인 환자를 만들어줘")

공용 MWL 서버의 HTTP API로 등록했다. UI 조작이 필요 없고 `python run.py
mwl-ensure` 한 번으로 당일 날짜 처방을 보장한다(오늘 것이면 재사용, 지난
것이면 삭제 후 재생성). 다른 제품(Bellalun/VXvue Mammo)의 MG 처방은 건드리지
않는다.

| 항목 | 값 |
|---|---|
| Patient ID / Name | `VXVUE_MWL_DX_01` / `AUTO^VXVUE^^^` (비식별) |
| Modality | **DX** |
| Accession / SPS / RP | `ACC_VX_AUTO_001` / `SPS_VX_AUTO_001` / `RP_VX_AUTO_001` |
| Procedure | CHEST / CHEST PA |

Registration > Scheduled에서 Search로 **실제 조회 성공**(Result 2/2)까지 확인했다.

### 1.2 "Remove Image Processing" 확인 (요청: "이거인 것 같은데 해봐줄래?")

**맞다.** Integration > Extra Tool 맨 아래 `Remove Image Processing` 행의
체크박스 라벨이 실제로 **`S.B.S.C.`** 다. 컨트롤 ID `31523`, DB `AE_LIST.RemoveSBSC`
컬럼과 대응한다. 화면 라벨과 체크리스트 용어가 다를 뿐 같은 것이다.
Options 섹션 맨 아래라 **스크롤해야 보인다.**

### 1.3 연동 상태 반영 (요청: "가상 제너레이터·VXCAD·VXLIVESERVER 연동했으니 참고")

`Viewer.xml`과 라이선스 화면에서 실측 확인했다.

- `<Generator product="8">`, `<AIEngine product="3">`, `<Camera UseLiveView="1"/>`
- VXvue 라이선스: **Demo License** + **Computer Aided Detection** + **Live View**
- `C:\VX.LIVE.SERVER` 설치 완료(DEMO 트리거 파일 존재, test_image 2,045개)
- 그 결과 **Setting 메뉴가 늘어났다**: Integration에 `Camera` / `Generator` /
  `Collimation`이 나타나 소분류가 53개 → **55개**

### 1.4 TC05 → MANUAL (요청: "다른 PC의 PACS가 필요하니 일단 MANUAL")

`automation_scope.json` 반영 완료. Bunny 등록·Echo·수신 판정 경로는 이미
확보돼 있어 PACS 접근이 가능해지면 그대로 재사용할 수 있다.

### 1.5 XIPL 라이선스 4종 확인 (요청: "About에서 4개 등록 확인")

`XIPL.SERVER` About 창의 라이선스 목록이 표준 `Edit`(ID 1030)이라 **평문으로
읽힌다** — OCR이 필요 없다. `python run.py xipl-license`로 판정한다.

**SBSC / Bone-X AI / VXCAD_CXR / Noise-X AI 4종 모두 등록 확인(OK).**

한계: About 창을 여는 경로가 트레이 아이콘 메뉴뿐이다(시스템 메뉴·명령행·
레지스트리에 라이선스 목록이 없음을 확인). 창이 닫혀 있으면 자동으로 열 수
없어 "사람이 열어야 함"을 알린다.

### 1.6 Setting Export/Import 회귀 설계 (요청: "이렇게 하면 좋겠는데 다른 의견 있어?")

원안을 실측으로 보강했다. 결정적 발견 3가지:

1. **파일은 `.vxs`이고 내용은 ZIP이다.** 안에 **DRF DB 전체 백업
   (`Data.bak` 9.9MB)** 이 들어 있다. 즉 **Import는 DB 전체 복원**이고, Export
   이후 생성된 검사 데이터가 사라진다. → 파괴적 조작으로 분류, 승인 인자 필수,
   사전 안전 백업 자동 생성, 회귀 순서 맨 마지막 배치.
2. **`Viewer.xml`은 Export에 포함되지 않는다.** 사용자 확인: 복원되지 않는 것이
   정상이므로 판정 제외(참고 기록만).
3. **원안의 허점** — 변경이 한 건도 반영되지 않아도 마지막 대조가 통과한다.
   그래서 3단 비교로 바꿨다.

```
S0 → Export(A) → 변경 → S1 → [검증 S1≠S0] → Import(A) → 재기동 → S2 → [검증 S2=S0]
```

판정 오라클은 UI 판독이 아니라 **DB 설정 테이블 62개 + 설정파일 9개 해시
스냅샷**이다. 연속 2회 스냅샷이 완전히 동일함(오탐 0)을 확인했다.

### 1.7 TC14 전면 재작성 (요청: 스크롤·목록·테마·속도)

요청 4건을 모두 반영했다.

**① 스크롤 아래 설정까지 전부 확인** — 본문 컨트롤을 전수 열거하고(스크롤 밖도
잡힌다) 페이지를 끝까지 내리며 각 컨트롤이 화면에 온전히 들어왔는지 기록한다.
한 번도 온전히 안 보인 컨트롤이 있으면 FAIL. `page_through()`의 종료 판정은
픽셀이 아니라 **컨트롤 위치**로 한다(픽셀 서명으로 하면 스크롤바 썸네일만
움직여도 다음 페이지로 오해해, 119px만 넘치는 화면에서 6장이 찍혔다).

**② 목록 상세 순회** — 요청대로 좌표 추정을 없앴다. 행은 `ListItem` 자식
윈도우로 실제 존재하고 **데이터가 없는 행은 hidden**이다. 그래서 보이는
`ListItem`을 직접 클릭한다. 화면의 **모든 목록**을 돌고, 목록이 화면보다 길면
목록 내부를 스크롤해 끝까지 내려간다. 행에 CheckBox가 있으면 그 오른쪽을
클릭한다(체크박스를 누르면 설정이 바뀌므로).

**③ 테마·폰트 비의존 판정** — 판정 근거를 픽셀에서 **값 JSON**으로 옮겼다.

| 종류 | 읽기 | 방법 |
|---|---|---|
| Edit | 가능 | `WM_GETTEXT` |
| 콤보 | 가능 | **부모 텍스트는 잘림**(`ScreenLUT`→`ScreenLU`), 숨은 자식 Edit에 전체값 |
| 라벨 | 가능 | `WM_GETTEXT` |
| 체크박스/라디오 | **불가** | 커스텀 owner-draw라 `BM_GETCHECK`가 항상 0 |

체크박스는 픽셀로 추측하지 않고 **DB 스냅샷으로 검증**한다. 기준 서명도 둘로
나눴다 — `구조서명`(라이선스·연동·메뉴목록, 테마 제외)으로 값 비교(주 판정),
`외형서명`(+테마·폰트·창크기)으로 캡처 SSIM(보조, 같은 테마끼리만).

**④ 속도** — 프로파일링해서 세 곳을 고쳤다.

| 항목 | 전 | 후 | 방법 |
|---|---|---|---|
| 화면 캡처 | 0.20s | **0.04s** | 가상 데스크톱 전체(5560×2297) 캡처 후 자르기 → 주 모니터만 |
| 컨트롤 열거 | ~2.5s | **0.24s** | 전체 창 트리 재귀 → 프레임 창 직속 자식만 + hwnd 캐시 |
| 화면 전환 | **13.1s** | **1.7s** | 같은 화면 재진입 시 제목이 안 바뀌어 매번 10초 타임아웃 소진 → 본문 대화상자 교체도 전환 신호로 인정 |

### 1.8 포트폴리오 리포지토리 (요청: "공개 리포지토리로 push")

- 포트폴리오 형식 `README.md` 작성(문제 정의 → 판정 설계 원칙 → 실전 문제와
  해결 9건 → 성능 → 아키텍처 → 범위와 한계)
- `.gitignore`로 `config.json` / `지식/`(원본 노트) / 산출물 폴더 제외
- `work/scrub_docs.py`가 설계문서의 **라이선스 키·하드웨어 키·QA 계정·시험망
  IP·사용자 계정 경로를 마스킹한 사본**을 `docs/`에 생성
- 공개 대상 파일 전체에 민감값 스캔을 돌려 3건을 잡아 수정(코드에 하드코딩된
  주소도 설정에서만 읽도록 변경)

---

## 2. 지금 동작이 확인된 것

```bash
python run.py preflight             # 전 항목 OK 확인 (재부팅 후)
python run.py env                   # Windows/패키지 헤더 수집 OK
python run.py xipl-license          # 4종 라이선스 OK
python run.py mwl-ensure            # DX 처방 보장 OK
python run.py db-ae                 # SCP 등록 + RemoveSBSC 조회 OK
python run.py snapshot              # 62개 테이블 스냅샷 OK
python run.py snapshot-diff --a A --b B   # 오탐 0 확인
python run.py vxs-info --a x.vxs    # Export 파일 구조 판독 OK
python run.py report-sample         # 리포트 4종 + 헤더 OK
python work/launch_login.py         # 기동 → 무인 로그인 OK
python run.py tc14                  # 55화면 전수 순회 OK (아래 결과)
```

### TC14 최근 실행 결과 (2026-08-18 16:04)

| Step | 결과 | 실제 |
|---|---|---|
| 1 Setting 진입 | PASS | |
| 2 소분류 전부 열림 | PASS | 55 / 55 |
| 3 제목 중복 없음 | PASS | 고유 제목 55개 |
| 4 컨트롤 전부 노출 | PASS | **미노출 0건** |
| 5 스크롤 끝까지 | PASS | 스크롤 필요 3화면, 캡처 76장 |
| 6 SCP 상세 vs DB | **FAIL** | 목록 선택이 빈 영역을 찍고 있었음 → **1.7절 ②로 수정 완료, 재실행 필요** |
| 7 값 기준 대조 | MANUAL | 기준 55화면 생성(Edit 117 / 콤보 318 / 라벨 228) |
| 8 캡처 SSIM | MANUAL | 기준 200장 생성 |
| 9 내용 적은 화면 | PASS | 3화면(설계상 정상, 캡처로 확인) |
| 10 트리 확보 | PASS | 구조서명 `cdcb4e1d` / 외형서명 `e1fd2664` |

**Step 6은 수정했지만 아직 재실행하지 않았다. 다음 세션의 첫 작업이다.**

---

## 3. 다음 세션에서 할 일 (우선순위 순)

### 3.1 TC14 재실행으로 목록 순회 수정 검증 — 첫 작업

```bash
rm -rf Evidence/tc14 Evidence/tc14_baseline
python run.py tc14 --no-env      # 1회차: 기준 생성
python run.py tc14 --no-env      # 2회차: 값·캡처 비교가 실제로 도는지 확인
```

확인 포인트: Step 6이 PASS로 바뀌는지, `Display - Overlay Item` /
`Display - Information Overlay`의 목록 행이 전부 클릭되는지(캡처 파일명
`*_l01_p01_r01.png` 형식으로 목록·페이지·행 번호가 남는다), 2회차에서 Step 7/8이
MANUAL이 아니라 PASS/FAIL로 판정되는지.

### 3.2 체크리스트 전체 회귀 러너 만들기 — 이번 세션의 미완 부분

**사용자 요구: "체크리스트 전체 회귀를 돌려서 TC별 PASS/FAIL을 보고 싶다."**
지금은 TC14와 Export/Import만 개별 실행된다. 필요한 것:

1. `run.py run-regression` — `automation_scope.json`을 읽어 EXCLUDED를 건너뛰고,
   의존 순서대로 실행한 뒤 **모든 TC 결과를 한 리포트에 합친다**.
   `core/result.write_reports()`는 이미 여러 TCResult를 받으므로 러너만 필요하다.
2. 실행 순서(파괴적 조작을 뒤로):
   `preflight → mwl-ensure → xipl-license → TC13 → TC14 → TC02 → TC06 →
    TC03 → TC04 → TC11 → TC12 → TC_Setting_ExportImport(맨 마지막)`
3. MANUAL/BLOCKED/EXCLUDED TC도 **리포트에 항목으로 표시**해야 한다. 빠지면
   "수행했다"와 "수행하지 않았다"가 구분되지 않는다.

### 3.3 아직 구현되지 않은 TC (자동화 수준은 `run.py scope` 참고)

| TC | 남은 작업 | 난이도 |
|---|---|---|
| **TC13** Import Patient | txt/csv 생성 → 파싱 미리보기 대조 → Registration Import → DB 확인. 파일 기반이라 장비 의존 없음. 기존 결함 #22985(Tab 구분자) 회귀 케이스 포함 | 낮음, **먼저 하기 좋음** |
| **TC06** Extra Tool/SBSC | 전송 대상은 Bunny로 확정됨. S.B.S.C. 체크(31523) → Update → `db-ae`로 `RemoveSBSC=1` 확인 → 촬영·전송 → XIPL 로그 `PureGrid.Apply="0"` 확인(UTF-16 리더 준비됨) | 중간 |
| **TC02** MWL 워크플로우 | Step1(조회·대조)은 정답지가 API 등록값이라 바로 가능. 남은 것: 오픈 → **F2** 촬영 → Close → DB 대조 → Send | 중간 |
| **TC03** 표시/도구 | Interpolation 변경은 Display>General(콤보 30975)에서 가능. Zoom/Pan/Rotation은 Viewer 화면 컨트롤 지도가 없음. **"delay 없이"의 정량 기준 미확정** | 중간 |
| **TC04** XIPL 처리 | 라이선스 4종 확인은 됨. 촬영 + Image Process + XIPL Studio 흐름 필요. Bellalun `core/xipl.py`(XIPL.STUDIO 드라이버) 재사용 검토 | 높음 |
| **TC11** AI 분석 | CAD 라이선스 확인됨. GPU 미탑재라 결과물 생성 검증은 SKIP 규칙 적용, 라이선스·UI 흐름만 | 중간 |
| **TC12** 카메라 | Camera 메뉴 등장 확인됨. Live View / Step Analysis / 스냅샷 전송 흐름 미착수 | 높음 |
| TC08 Export | 실제 CD/USB. 매체 삽입은 MANUAL Step으로 사람 대기 처리 방식 결정 필요 | 중간 |
| TC01/09/10/15 | 범위 제외 또는 MANUAL 확정 | — |

### 3.4 성능: `--fast` 모드 (제안)

회귀 실행 때 **값 JSON을 먼저 비교하고 값이 바뀐 화면만 캡처**하면 TC14
실행시간이 크게 줄어든다(값 비교는 클릭·캡처 없이 끝난다). 55화면 전수 캡처는
기준 갱신이 필요할 때만 하면 된다.

### 3.5 남은 확인 필요 항목

1. **TC03의 "delay 없이"** 정량 기준 (예: 상태 전이 완료까지 N초 이내)
2. **TC08 매체 삽입 대기 방식** — 사람 확인 프롬프트를 넣을지
3. **`AIEngine product="3"` ↔ 엔진 매핑표** — License에 CAD가 있어 정황은
   맞지만 product 번호와 엔진의 공식 매핑은 미확인
4. **`Generator product="8"`의 실제 모델명** — 가상/시뮬레이터 확인
5. **페이지파일이 C:에 생성됨** — 의도가 D:였다면 별도 조치 필요
   (재부팅 후 32GB가 C:에 생성되어 C: 여유 67GB로 감소)

---

## 4. 환경 관련 주의 (다음 세션에서 반복될 수 있음)

1. **WMI가 물릴 수 있다.** `Get-CimInstance`가 응답하지 않는 상태가 실제로
   발생했다. `core/sysinfo.py`는 WMI 비의존으로 작성됐다 — **새 코드에서
   `Get-CimInstance`를 쓰지 말 것.**
2. **커밋 메모리 고갈**이 뷰어 기동 실패의 실제 원인이었다. `preflight`가 NG를
   내면 UI 자동화를 시작하지 말 것. 환경 문제를 제품 결함으로 오판하지 않기 위한
   장치다.
3. **Update/저장 뒤 Info 팝업**을 닫기 전에는 이후 클릭이 전부 무시된다.
   → `ui.click_and_ack()`
4. **Edit는 Ctrl+A로 지워지지 않는다.** → `ui.clear_edit()` (End + Backspace 반복)
5. **XIPL 서버 로그는 UTF-16LE**다. 일반 grep으로는 판정 문구를 찾을 수 없다.
   → `core/xipl.read_log()`
6. **Demo 촬영 키는 F2**다(Bellalun은 F8).
7. **XIPL은 Bellalun 자동화와 설치를 공유한다.** `C:\XIPL\PARAMETER`의 기존
   픽스처를 덮어쓰지 말고 `_VXVUE` 접미 이름으로 복사해 쓸 것.
8. UI 명령은 **관리자 권한**으로 실행해야 한다(UIPI 차단).
