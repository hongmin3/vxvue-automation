# VXvue 의료영상 뷰어 QA 자동화

Windows 업데이트마다 반복되는 **의료영상 뷰어 호환성 검증 체크리스트**를 무인
실행 + 자동 판정 + 증적 리포트로 옮긴 프로젝트다. 이어서 기본기능 회귀 시험까지
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
클릭하다 보니 **누락과 판정 편차**가 생긴다. 증적도 캡처를 손으로 모아야 한다.

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
기준자료 안에서만 보조로 쓴다(4.4절).

**④ 읽을 수 없는 것은 읽을 수 없다고 적는다.**
체크박스는 커스텀 렌더링이라 UI에서 on/off를 읽을 수 없다. 픽셀을 찍어 추측하는
대신, 컨트롤 구성만 UI에서 대조하고 실제 값은 DB 스냅샷으로 검증한다.

---

## 3. 지금 동작하는 것

```bash
python run.py run-regression        # 전체 회귀 — 선행조건 → 라이선스 → DICOM 연동
                                    #  → TC13 → TC14 → Setting Export/Import → 리포트
python run.py tc13                  # 환자정보 Import 회귀 (TAB 구분자 결함 회귀 포함)
python run.py tc14                  # Setting 55화면 전수 순회 + 값 추출 + 판정
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
| 설정 55화면이 정상 표시되는가 | 실행 시점에 만든 **메뉴 지도** + 화면별 값 추출 |
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

이 프로젝트에서 실제 시간을 잡아먹은 것은 테스트 로직이 아니라 **제품·환경의
관측 가능성 문제**였다. 각 항목은 모두 실측으로 확인하고 코드에 근거를 남겼다.

### 4.1 표준 Windows API로 읽히지 않는 커스텀 UI

제품 UI는 사내 SDK로 직접 렌더링하는 컨트롤(`AfxWnd140u`)을 쓴다. 좌측 설정
메뉴 항목은 `GetWindowText`로 **라벨을 읽을 수 없고**, 표준 `BM_CLICK`에도
반응하지 않는다. 자매 프로젝트는 좌표를 캘리브레이션해 OCR로 읽는 방식을
썼지만, 해상도·테마가 바뀌면 다시 재야 한다.

**해결** — 두 가지 관측점을 찾아 좌표 의존을 없앴다.

| 발견 | 활용 |
|---|---|
| 메뉴 항목이 자식 윈도우로 존재하고, 소분류는 컨트롤 ID가 1~55로 고유 | 좌표 대신 ID로 항목 지목 |
| 화면 전환 시 **상단 제목이 평문으로 읽힌다**(`Integration - Extra Tool`) | 클릭 결과를 제목으로 확인 |

덕분에 메뉴 지도를 하드코딩하지 않고 **실행 시점에 순회로 스스로 만들어낸다.**
그 결과가 곧 "제품이 실제로 보여준 메뉴 목록"이라 체크리스트 대조에도 쓰인다.

> 부수 효과: 문서에 53개로 적혀 있던 설정 소분류가 실제로는 **55개**였고, 한
> 항목은 다른 대분류로 이동해 있었다. 연동 상태에 따라 메뉴가 늘어나는 것도
> 이 순회로 확인했다.

### 4.2 저장 직후 뜨는 모달 팝업이 이후 클릭을 전부 삼킨다

설정 저장(`Update`) 뒤에 확인 팝업이 뜨는데, **닫기 전까지 그 뒤로 보낸 모든
클릭이 아무 반응 없이 무시된다.** 팝업이 메인 창 위에 겹쳐 있어 스크린샷만
보면 "화면은 그대로인데 왜 반응이 없지"로 오인하기 쉽다.

**해결** — 저장 성격의 클릭을 `click_and_ack()`로 감쌌다. 클릭 → 최상위 창
확인 → 팝업이면 문구를 증적으로 남기고 닫기까지 한 동작으로 처리한다.

### 4.3 `Ctrl+A`가 통하지 않는 입력 필드

IP 주소 필드에서 전체 선택이 먹지 않아 기존 값 뒤에 새 값이 이어붙고
(`127.0.0.110.13.…`) 검증 팝업이 떴다.

**해결** — `clear_edit()`은 `End` 이동 후 `Backspace` 반복으로 필드를 비운다.
모든 입력 헬퍼가 이 방식을 기본으로 쓴다.

### 4.4 테마·폰트가 바뀌면 픽셀 비교가 통째로 무의미해진다

캡처를 SSIM으로 비교하는 방식은 테마를 바꾸는 순간 55개 화면이 전부 FAIL이
된다. 실제로는 색과 크기만 달라졌을 뿐 **설정 값은 동일**하다.

**해결** — 판정 근거를 픽셀에서 값으로 옮겼다. 다만 이 TC(TC14)가 실제로
검증해야 하는 것은 "Windows Update로 탭 클릭과 옵션 노출이 깨지지 않았는가"
이지, 옵션 값이 기준과 완전히 같아야 하는 정밀 회귀가 아니다(사용자 확인
2026-08-19). 그래서 값·옵션 구성이 기준과 다르면 **FAIL이 아니라 `확인
필요`로만 표시**하고 무엇이 달라졌는지 남긴다 — 라이선스·연동 상태에 따라
메뉴가 정상적으로 늘어나는 사례가 실제로 있어(4.1절), 차이를 곧 결함으로
단정할 수 없기 때문이다. **값이 완전히 같아야만 PASS로 인정하는 정밀 회귀는
Setting Export/Import TC 쪽 책임으로 분리했다**(4.9절, `snapshot`/
`config_snapshot.py`가 그 판정 오라클이다).

기준자료는 구조 서명(라이선스·연동 상태·메뉴 목록, 테마·폰트 제외) 하나로
관리한다 — 테마별 외형 캡처 비교(SSIM)는 "탭이 클릭되는가"라는 이 TC의
목적과 맞지 않아 뺐다. 캡처 자체는 화면마다 계속 저장해 사람이 참고할 증적
으로 남긴다.

값 추출에서 막힌 지점도 실측으로 풀었다. 콤보박스는 부모 컨트롤의 텍스트가
폭에 맞춰 **잘려 있어**(`ScreenLUT` → `ScreenLU`) 그대로 쓰면 값이 틀린다.
숨은 자식 `Edit`에 전체 값이 들어 있어 그것을 읽는다.

```json
{
  "title": "Display - General",
  "edits":  { "30171": "10", "30172": "W1 Increase" },
  "combos": { "30974": "ScreenLUT", "30975": "Bicubic" },
  "labels": ["Down", "Left", "Right", "Speed", "Up", "min"],
  "unreadable_state_controls": [ {"id": 31531, "kind": "CheckBox"} ]
}
```

마지막 항목이 이 설계의 정직성이다 — 읽을 수 없는 컨트롤은 **읽을 수 없다고
기록**하고, 그 값은 DB 스냅샷으로 검증한다.

### 4.5 화면 밖에 있는 설정은 검증되지 않는다

보이는 영역만 캡처하면 스크롤 아래 설정은 아무도 확인하지 않는다. 한 화면은
전체 컨트롤 75개 중 **57개만 노출**되어 있었다.

**해결** — 본문 컨트롤을 전수 열거하고(스크롤 밖도 잡힌다), 페이지를 끝까지
내리며 각 컨트롤이 화면에 온전히 들어왔는지 표시한다. 끝까지 내려도 한 번도
온전히 보이지 않은 컨트롤이 있으면 그 화면은 잘려서 조작할 수 없다는 뜻이므로
FAIL이다. "컨트롤이 하나라도 있으면 통과" 같은 느슨한 기준을 쓰지 않는다.

스크롤 종료 판정도 픽셀이 아니라 **컨트롤 위치**로 한다. 픽셀 서명으로 하면
스크롤바 썸네일만 움직여도 다음 페이지로 오해해, 119px만 넘치는 화면에서 6장이
찍혔다.

### 4.6 목록을 클릭해야 상세가 나오는 화면

DICOM 서버 설정은 등록 목록에서 항목을 **클릭해야** 상세가 표시된다. 화면만
캡처하면 등록된 서버 정보는 한 건도 검증되지 않는다.

**해결** — 목록 행을 순서대로 클릭해 상세를 캡처하고, 표시된 값을 **DB의 실제
등록값과 대조**한다. 캡처 비교보다 강한 근거이고, 행 개수도 DB에서 가져와
"몇 건을 확인해야 하는지"를 코드가 알고 있다.

### 4.7 환경이 자동화를 멈춰 세운 두 사건

**WMI가 물렸다.** `Get-CimInstance`가 어떤 클래스든 응답하지 않는 상태가
발생해(한 호출에 60초 초과) 환경 조회 단계에서 자동화 전체가 멈췄다.
→ 환경 조회를 **WMI 비의존으로 재작성**했다. 메모리는 `GlobalMemoryStatusEx`,
OS 정보·GPU는 레지스트리, 파일 버전은 버전 리소스 직접 읽기, 해상도/DPI는
Win32 API. 불가피한 WMI 호출에는 타임아웃을 걸어 실패해도 리포트 생성이
계속되게 했다.

**커밋 메모리가 고갈됐다.** 제품이 감지기 초기화 단계에서 무한 대기했는데,
원인은 제품 결함이 아니라 **페이지파일 여유 0GB**였다. 설정상 32GB 페이지파일이
다른 드라이브에 지정돼 있었지만 파일이 생성되지 않아 커밋 한도가 묶여 있었다.
→ `preflight`가 실행 전에 이 조건을 잡고 UI 자동화를 시작하지 않는다.
**환경 문제를 제품 결함으로 오판하는 것을 막는 것도 자동화의 일**이다.

### 4.8 UTF-16 로그와 제목 읽기 경쟁 조건

영상처리 서버 로그는 **UTF-16LE**로 기록된다. 바이트 grep이나 기본 인코딩
읽기로는 판정 문구를 절대 찾을 수 없어 전용 리더를 만들었다.

화면 제목은 갱신 도중에 읽으면 잘린 문자열이 잡힌다(`DICOM - Storage`를
`DICOM - Stor`로 읽었다). 같은 값이 연속으로 읽힐 때까지 기다리고, 본문
대화상자 교체도 전환 완료 신호로 함께 본다.

### 4.9 설정 Export 파일의 정체

Export 산출물은 확장자만 보면 설정 파일 같지만, 열어 보니 **ZIP 아카이브**이고
그 안에 **DB 전체 백업이 들어 있었다.** 즉 Import는 "설정 되돌리기"가 아니라
**DB 전체 복원**이고, Export 이후 생성된 검사 데이터가 사라진다.

**해결** — Import를 파괴적 조작으로 분류했다. 명시적 승인 인자 없이는 실행되지
않고, 실행 직전 안전 백업을 자동으로 남긴다. 회귀 순서에서도 이 TC를 맨
마지막에 배치한다. 또 이 Export에 포함되지 않는 머신 단위 설정 파일을 찾아내
**판정 대상에서 분리**했다(복원되지 않는 것이 정상임을 확인).

### 4.10 DICOM SCP 등록 버튼이 여는 것은 파일 대화상자가 아니었다

Import Patient Order 버튼(TC13)도, DICOM 서버 등록도 처음 설계할 때는
"버튼을 누르면 표준 동작이 바로 일어난다"고 가정했지만 둘 다 실측해 보니
**Setting 화면과 같은 구조를 재사용한 별도 모달 팝업**을 먼저 여는
2단 구조였다. 문서만 보고 짐작한 설계가 실측 전까지 계속 틀려 있었던
사례다 — 그래서 이 저장소는 "확인되지 않은 동작을 그대로 코드에 넣지
않는다"는 규칙을 UI 흐름에도 똑같이 적용한다.

DICOM 서버(MWL/Storage/Print) 등록 자동화(`core/dicom_settings.py`)에서
실측으로 걸린 함정 세 가지:

1. **Storage 화면은 Options 섹션이 길어 Echo 버튼이 스크롤 없이는 화면
   밖에 있다.** 컨트롤 조회(`content_controls()`)는 스크롤 밖 컨트롤의
   rect도 그대로 돌려주므로, 스크롤 없이 그 rect를 클릭하면 **그 좌표에
   실제로 보이는 다른 컨트롤**을 클릭하게 된다 — Storage의 Echo가 매번
   전혀 다른 팝업을 띄운 원인이었다. 클릭 대상은 항상 뷰포트 안으로
   스크롤해서 끌어온 뒤 클릭한다.
2. **체크박스는 상태를 읽을 수 없어 무조건 클릭하면 안 된다.** 이미
   체크된 걸 다시 누르면 꺼진다. `BM_GETCHECK`가 항상 0을 반환하는 대신,
   체크됐을 때만 나타나는 특정 색(체크 표시)이 캡처 안에 있는지로
   판별한다(`core/setting.checkbox_checked()`) — 판별 후 필요한 것만
   클릭한다.
3. **같은 대분류 안의 화면을 오갈 때도 좌측 메뉴 전체를 훑고 있었다.**
   화면 전환 헬퍼(`goto_screen()`)가 매번 대분류 10개를 전부 접었다 펴며
   확인하고 있었던 것 — MWL→Storage→Print를 오가는 등록 자동화에서
   특히 비용이 컸다. "지금 이미 그 화면이면 아무것도 누르지 않는다",
   "지금 펼쳐진 대분류 안에서 먼저 찾는다" 두 개의 빠른 경로를 추가하고,
   못 찾을 때만 원래의 전체 탐색으로 되돌아가게 했다.

### 4.11 Study 등록에서 Procedure Mapping을 건너뛰면 뒤가 줄줄이 막힌다

TC02를 구현하면서 처음 만난 문제다. MWL 처방을 `Start`로 등록하면 확인 팝업이
먼저 뜬다.

```
Info: "Some procedures are not existing. Do you want to register them?"
      [Yes] [No] [Cancel]
```

사양서1 p.38 `VP-460`이 세 선택지의 동작을 정의한다 — *"Yes : Procedure Mapping
창 팝업 / No : Procedure Mapping 하지 않고 Exposure Mode 로 전환 / Cancel :
Study 등록을 취소"*.

자동화는 처음에 **No**를 택했다. 매핑은 제품 설정(Procedure ↔ Code)을 바꾸는
조작이고, 이 시험대의 XIPL은 자매 프로젝트와 설치를 공유하므로 함부로 건드릴 수
없다고 판단했다. Study는 등록되고 촬영도 성공했다. 그런데 **그 뒤가 셋이나
막혔다.**

| 증상 | 실제 원인 |
|---|---|
| 촬영 직후 `Error: Image process parameter file does not exist.` | Step이 없어 영상처리 파라미터가 지정되지 않는다 |
| Database 목록에 이 검사가 안 보인다(`Result: 0 / 0`) | Operation Manual 3.6(p.41) — Database는 **완료된 검사**만 조회한다. Step이 남아 있어 검사가 보류로 남고 `STUDY.StudyStatus`가 1이다(정상 종료된 검사는 0) |
| TC07 Print·TC08 Export가 대상을 고를 수 없다 | 둘 다 Database 목록에서 스터디를 선택해야 실행된다 |

**하나의 선택이 세 TC를 막은 것**이고, 표면 증상은 서로 무관해 보였다. 파라미터
오류는 XIPL 설정 문제로, Database 미표시는 조회 조건 문제로 보였다. 원인을
확정한 것은 두 근거였다 — XIPL 서버 로그(`Loading base parameter : Chest
PA_normal_H.hs8` → `Parameter file not found`, 그런데 그 파일은 실제로 존재한다)와
DB의 `StudyStatus` 값 비교.

그래서 각 TC의 판정에 **막힌 이유와 해제 조건**을 함께 적었다. 예를 들어 TC08은
`BLOCKED`로 판정하면서 "Procedure Mapping이 선행돼야 하고, 그래서 알려진 결함
#21049의 재발 여부도 이번 실행으로는 판단할 수 없다"고 남긴다. 막혔다는 사실만
적으면 다음 사람이 같은 조사를 반복한다.

### 4.12 매핑을 자동화하려다 제품 설정을 오염시킨 일

위 문제를 풀려고 `map_procedure()`를 만들어 Mapping 버튼(`30647`)을 누르게 했다.
라이브로 처음 돌렸을 때 **New(`30646`) 경로가 타졌고**, "New Procedure" 창에서
Add가 눌려 `TB_PROCEDURE`에 없던 Procedure가 생겼다.

```
ProcedureKey=267  Name='Inserted:RP_VX_AUTO_001'
Code='RP_VX_AUTO_001'  Description='CHEST PA'   (PROCSTEP에 Step 없음)
```

게다가 그 "New Procedure" 창은 Cancel이 없어 `dismiss_dialog()`로 닫히지 않았고,
**남은 채로 이후 모든 조작을 조용히 삼켰다.** 다음 실행의 TC03이 "Display -
General 화면으로 이동하지 못했습니다"로 실패했는데, 진짜 원인은 화면 전환이 아니라
그 창이었다.

세 가지를 고쳤다.

1. **`map_procedure()`를 비활성화**했다(`ENABLE_PROCEDURE_MAPPING = False`).
   함수는 남기고, 호출되면 아무것도 누르지 않고 "왜 하지 않는지"와 **다시 켜기
   전에 확인할 것 4가지**를 반환한다. 원인을 확정하기 전에 제품 설정을 만지는
   코드가 회귀에 섞이는 것이 더 위험하다.
2. **`pending_dialogs()`가 닫히지 않는 창을 제목줄 X(`ctrl_id=-4`)로 닫게** 했다.
   아무 버튼이나 누르지 않는다 — Add를 누르면 설정이 또 바뀐다. 그래도 안 닫히면
   무한 루프 대신 "닫지 못한 창"으로 사실을 남기고 멈춘다.
3. **`open_setting()`과 `goto()`가 화면 전환 전에 팝업을 걷어내게** 했다. 이 제품은
   모달 팝업이 떠 있으면 클릭을 조용히 무시하므로, 전환 실패의 원인이 팝업인지
   화면 구조인지 구분되지 않는다.

오염된 Procedure(267번)는 `--reset-baseline`으로 DB를 클린 시점으로 되돌리면
사라진다. **DB에서 직접 DELETE 하지 않았다** — 이 저장소는 DB 조회 전용이 원칙이고
(7절 설계 규칙 ①), 그 원칙을 자기 실수를 덮는 데 쓰면 원칙이 무의미해진다.

---

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

```bash
python run.py run-regression
```

Phase 순서대로 실행하고 **모든 결과를 리포트 1건으로 합친다.**

| Phase | 내용 | 기본 동작 |
|---|---|---|
| 0 | `preflight` → `mwl-ensure`(당일 DX 처방 보장) → `xipl-license` | 항상 수행 |
| 1 | DB/폴더를 클린 baseline으로 복원 (라이선스·로그는 왕복 백업으로 보존) | **건너뜀** — `--reset-baseline` 필요 |
| 2 | VXvue 자체 라이선스 확인 (Setting > System > License) | 항상 수행 |
| 3 | DICOM SCP 등록 확인·구성 + C-ECHO (MWL / Storage / Print) | 항상 수행 |
| 4 | TC13 → TC14 → (미구현 TC는 `automation_scope.json` 수준 표시) | 항상 수행 |
| 5 | Setting Export/Import 회귀 (맨 마지막, 파괴적) | Export까지만 — Import는 `--approve-destructive` 필요 |

**파괴적 옵션은 기본으로 실행하지 않고, 실행하지 않았다는 사실을 리포트에
`SKIP`으로 남긴다.**

```bash
python run.py run-regression --reset-baseline
```

DB와 `data_dir` 폴더를 클린 설치 시점으로 되돌린 뒤 회귀를 시작한다. 현재 DB의
환자·검사·설정이 **전부 사라진다.** 라이선스(`.lic`)와 운영 로그(`log/`)는
되돌리기 직전에 떠서 복원 후 다시 덮어쓴다(라이선스는 하드웨어 키에 묶여 있어
기준 백업에 값으로 남기지 않는다). `Bak/`(DB 백업 이력)은 절대 지우지 않는다.

```bash
python run.py run-regression --reset-baseline --approve-destructive
```

체크리스트가 요구하는 전 범위. Phase 5의 실제 Import까지 수행하므로 DB가 마지막
Export 시점으로 복원된다.

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
| `python run.py tc02` | **TC02 MWL 조회 워크플로우** — MWL 조회 → 목록 표시값 대조 → Study 등록 → F2 데모 촬영 → DICOM Send → **수신 파일 태그가 MWL 등록값과 일치하는지** → Close → DB 대조 | 약 4분 |
| `python run.py tc03` | **TC03 영상 조작** — Interpolation Mode 변경·원복 + Select/Zoom/Pan/CW/CCW 툴 적용을 **영상 영역 캡처 SSIM으로 판정** | 약 3분 |
| `python run.py tc05` | **TC05 DICOM 전송** — 촬영 → Send → **수신 객체의 SOP Class UID로 Image/Dose SR 포함 여부 판정** | 약 4분 |
| `python run.py tc07` | **TC07 DICOM Print** — Print SCP 가동 확인 → 촬영 → Print → **받은 쪽 서버의 필름 목록으로 판정**(Calling AE로 다른 제품 필름과 구분) | 약 4분 |
| `python run.py tc08` | **TC08 Study Export** — E 드라이브로 Export → 산출물 DICOM 태그 대조 → QXLink 포함 확인. 알려진 결함 **#21049**(Win11 Export 에러) 회귀 | 약 3분 |
| `python run.py tc13` | **TC13 Import Patient** — Study > Import Patient 설정 → 환자정보 txt/csv Import → Registration-Reserved 목록 표시까지. TAB 구분자 회귀(#22985) 포함 | 316초 |
| `python run.py tc13 --with-folder-watch` | 위에 더해 "Import Patient Information From a Specific Folder"(폴더 자동 감지) 경로까지. Import Patient Order와 **상호 배타**라 기본은 끔 | — |
| `python run.py tc14` | **TC14 Setting 전체 화면** — 좌측 메뉴 대분류 10개를 펼쳐 소분류 55개 화면을 전수 순회, 각 화면의 값·컨트롤 구성 추출 + 캡처 258장 | 963초 |
| `python run.py setting-export-import` | **Setting Export/Import 회귀** — 3단 비교(S0 → Export → 변경 → S1 → Import → S2). 파괴적 | — |
| `python run.py setting-export-import --no-import` | 위에서 Import 단계만 생략(Export까지) | — |
| `python run.py vxvue-license` | **VXvue 자체 라이선스** — Setting > System > License의 Hardware Key / 목록 3행(Demo·CAD·Live View) / Add·Change·Delete 버튼을 확인하고 설치된 `.lic` 파일과 대조 | 약 30초 |
| `python run.py xipl-license` | **XIPL 영상처리 라이선스 4종** — XIPL.SERVER About 창 판독. 위 항목과 **다른 검증**이다(VXvue 본체 라이선스 ≠ XIPL 라이선스) | 약 10초 |

촬영이 필요한 TC(02/03/05/07/08)의 공통 옵션:

| 옵션 | 뜻 |
|---|---|
| `--no-acquire` | 촬영 단계를 건너뛰고 **이미 열려 있는 영상**을 쓴다. 반복 디버깅용 |
| `--no-send` | (tc02) 마지막 DICOM Send를 생략한다 |
| `--map-procedure [이름]` | MWL 처방의 Procedure Code를 지정 Procedure(기본 `Chest PA`)에 매핑한다. **제품 설정을 바꾸는 조작이라 기본은 하지 않는다** — 현재는 안전장치 미비로 코드에서 비활성(`core/workflow.ENABLE_PROCEDURE_MAPPING`), 자세한 사정은 4.12절 |

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
PASS·FAIL·MANUAL·SKIP·BLOCKED 건수 / 실패 항목 / 수동 확인 항목 / 증적` 열이
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

## 6. 회귀 실적 (모두 실측)

`python run.py run-regression` 전체 실행 결과. **파괴적 옵션 없이** 돌린 것이며
(`--reset-baseline` / `--approve-destructive` 제외) 그 사실이 리포트에 SKIP으로
남는다.

| 실행 | 판정 합계 | 소요 | 비고 |
|---|---|---|---|
| 2026-08-19 1차 (18:47) | PASS 42 / FAIL 0 / MANUAL 17 / SKIP 5 / BLOCKED 0 | 72분 | 구현된 TC는 TC13·TC14·Setting Export/Import 3건 |
| 2026-08-19 2차 (20:47) | **PASS 72 / FAIL 1 / MANUAL 18 / SKIP 5 / BLOCKED 2** | 72분 | TC02·03·05·07·08 추가 구현 후. 같은 시간에 판정 항목이 30건 늘었다 |

TC별 소요(2차 실측): TC02 404초 · TC05 399초 · TC07 523초 · TC08 344초 ·
TC13 343초 · TC03 260초 · TC14 829초 · Setting Export/Import 약 17분 ·
DICOM 서버 연동 94초 · 라이선스 확인 57초.

**2차의 FAIL 1건과 BLOCKED 2건은 모두 원인이 규명돼 있다.**

| 항목 | 판정 | 원인 |
|---|---|---|
| TC07 Step 6 — Print 필름 수신 | FAIL | Print 대상을 Database 목록에서 골라야 하는데 목록이 비어 있다(아래 공통 원인) |
| TC08 Step 3 — Export 대상 선택 | BLOCKED | 같은 원인 |
| TC04 — Image Processing | BLOCKED | XIPL 서버가 보는 파라미터 경로가 VXvue 하위 폴더를 가리키지 않는다(4.11절) |

앞의 두 건은 **하나의 공통 원인**이다 — Procedure Mapping을 생략하면 Step이
등록되지 않아 검사가 완료 처리되지 않고, Database는 완료된 검사만 표시한다
(4.11절). 사람이 한 번 매핑한 뒤 다시 돌리면 해제된다. 그 조건을 각 TC의 판정
`note`에 적어 두었다.

MANUAL 18건은 "자동화가 실패한 것"이 아니라 **판정 근거가 없거나 사람이 확인해야
하는 것**이다. 대표적으로 "delay 없이"의 정량 기준 미확정(TC03), Send Dose SR
컨트롤 ID 미실측(TC05), Export Manager 창 내부 미실측(TC08), 그리고 아직 자동화
코드가 없는 TC의 `automation_scope.json` 수준 표시.

---

## 7. 성능

55개 화면을 매번 도는 시험이라 화면당 비용이 전체를 지배한다. 프로파일링으로
세 지점을 고쳤다.

| 항목 | 개선 전 | 개선 후 | 방법 |
|---|---|---|---|
| 화면 캡처 | 0.20s | **0.04s** | 가상 데스크톱 전체(5560×2297)를 잡고 자르던 것을 주 모니터만 캡처 |
| 컨트롤 열거 | ~2.5s | **0.24s** | 전체 창 트리 재귀 탐색 → 프레임 창의 직속 자식만 조회 + hwnd 캐시 |
| 화면 전환 | 13.1s | **1.7s** | 같은 화면 재진입 시 제목이 안 바뀌어 매번 타임아웃(10s)을 소진하던 것을, 본문 대화상자 교체를 전환 신호로 함께 인정 |

---

## 8. 아키텍처

```
auto/
├─ run.py                     CLI 진입점
├─ automation_scope.json      TC별 자동화 수준 (FULL/PARTIAL/MANUAL/BLOCKED/EXCLUDED)
├─ config.example.json        설정 템플릿 (실제 값은 config.json, Git 제외)
├─ core/
│  ├─ ui.py                   Win32 UI 드라이버 + 제품 고유 함정 흡수
│  ├─ setting.py              설정 화면 순회 엔진 (스크롤·목록 상세·값 추출)
│  ├─ screen.py               캡처 / SSIM / 빈 화면 판정
│  ├─ context.py              라이선스·연동·테마 컨텍스트와 서명 이원화
│  ├─ config_snapshot.py      설정 스냅샷 (DB 62개 테이블 + 파일 해시)
│  ├─ vxs.py                  Export 파일(ZIP) 판독·비교
│  ├─ dbreset.py              DB/폴더 백업·복원 — 파괴적 조작 전용, 승인 필수
│  ├─ dicom_settings.py       DICOM SCP(MWL/Storage/Print) 등록·Echo 자동화
│  ├─ db.py                   DB 조회 전용 브릿지 (쓰기 API 없음)
│  ├─ mwl.py                  Worklist 시험 서버 HTTP 클라이언트
│  ├─ license.py              VXvue 본체 라이선스 확인 (화면 OCR + .lic 파일 대조)
│  ├─ xipl.py                 XIPL 영상처리 라이선스 확인 + UTF-16 로그 판독
│  ├─ specs.py                사양서·매뉴얼 PDF에서 근거를 찾아 쪽·VP번호까지 인용
│  ├─ checklist.py            체크리스트 xlsx 사본에 판정 열 기록 (원본은 읽기만)
│  ├─ watchdog.py             상태 기반 대기·재시도·팝업 가드·단계 실패 격리
│  ├─ sysinfo.py              환경 조회 (WMI 비의존)
│  ├─ package_info.py         패키지 버전 수집
│  ├─ preflight.py            실행 전 환경 점검 + 실패 시점 메모리 근거
│  ├─ result.py               판정 모델 + 리포트 4종
│  └─ regression.py           체크리스트 전체 회귀 러너 (Phase 0~5, scope 반영)
└─ tests/
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
| Procedure ↔ Code 매핑 | 하지 않음 | 제품 설정을 바꾸는 조작이고, 자동화가 잘못 눌러 Procedure를 하나 만든 사고가 있었다(4.12절). 사람이 한 번 매핑한 뒤 회귀를 돌린다 |
| Export Manager 창 내부 조작 | MANUAL | 별도 프로세스(`VX.EXPORT.MANAGER`)의 컨트롤 ID를 실측하지 못했다. 추측한 ID를 누르면 형식·익명화·Portable viewer 포함 여부를 바꾼다 |
| Setting > DICOM - General 의 Send Dose SR | MANUAL | 어느 컨트롤인지 실측 확정 전 — 잘못 누르면 다른 전송 정책을 바꾼다 |
| Export된 스터디의 역방향 Import | MANUAL | DB에 데이터를 추가하는 조작이라 자동 승인 없이 실행하지 않는다 |
| XIPL Studio 재처리(TC04) | BLOCKED | XIPL 서버가 보는 파라미터 경로가 VXvue 하위 폴더를 가리키지 않아 촬영 직후 영상처리가 실패한다. 그 경로는 자매 프로젝트와 공유하는 설치라 자동화가 바꾸지 않는다 |

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
| `requirements.txt` | 의존성 4개와 각각을 쓰는 곳 |

**TC 자동화 코드를 추가하거나 Step 구성을 바꿀 때는 `docs/TC_검증상세.md`도 같은
커밋에서 갱신한다.** 코드와 문서가 어긋나면 코드를 기준으로 문서를 맞춘다.

자동화 코드 파일명은 **TC ID와 맵핑**한다(`tests/tc02_*.py` →
`TC_WindowsUpdate_02`). 각 모듈의 `TC_ID` 상수가 `core/regression.IMPLEMENTED`의
키와 일치해야 한다 — 어긋나면 리포트의 TC ID와 실행된 코드가 달라져 체크리스트
기록이 엉뚱한 행에 들어간다.

작업 인수인계·다음 작업 큐(`HANDOFF.md` / `NEXT_TASK.md`)와 판단 기준
문서(`CLAUDE.md`)는 이 저장소 상위 폴더(`VXvue/`)에서 관리한다. 사내 실측
기록·사양 원문 인용이 섞여 있어 이 공개 저장소에는 포함하지 않는다.
