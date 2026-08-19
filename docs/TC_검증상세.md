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

## 판정 설계에서 반복되는 원칙 (세 TC 공통)

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
