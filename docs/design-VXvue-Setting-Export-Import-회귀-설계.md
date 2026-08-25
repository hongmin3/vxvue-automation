> 이 문서는 내부 설계 노트의 **공개용 마스킹 사본**이다. 라이선스 키,
> 하드웨어 키, QA 계정, 시험망 주소, 사용자 계정 경로는 값만 가렸고
> 설계 근거와 실측 내용은 그대로 남겼다.

# VXvue Setting Export / Import 회귀 자동화 설계

작성: 2026-08-18. 사용자 제안 시나리오를 실측 근거로 보강한 설계다.
대상 화면: Setting 좌하단 `Export`(컨트롤 30300) / `Import`(30685).

## 0. 사용자 제안 시나리오 (원안)

1. Setting 전체 탭에 들어가 현재 설정을 확인하고 저장
2. Export로 전체 설정을 파일로 내보냄
3. 각 탭에 다시 들어가 최소 1~2개씩 설정을 변경(Procedure Manager, DICOM 포함)
4. Import로 아까 내보낸 파일을 되돌림
5. 뷰어 재실행
6. 전체 설정을 다시 확인해 Export 당시 값이 유지됐는지 점검

## 1. 실측으로 확인한 사실 (원안을 그대로 쓰면 안 되는 이유)

### 1.1 파일 확장자는 `.vxs`이며, **내용은 ZIP**이다

Export 시 표준 Windows "다른 이름으로 저장" 대화상자가 뜨고 기본 파일명은
`VXvueSetting.vxs`다. 확장자를 임의로 주면 뒤에 `.vxs`가 덧붙는다
(`baseline_A.vms` -> `baseline_A.vms.vxs`).

실제로 만들어진 파일(7,383,400 bytes)은 ZIP 아카이브이고 엔트리는 2,491개다.

| 최상위 | 내용 |
|---|---|
| `Data.bak` | **9,965,568 bytes — SQL Server 네이티브 백업(MTF `TAPE` 헤더)** |
| `Configuration/` | `Configuration.xml`(+`.bak`), `Property.json`, `CamAppClientSetting.ini`, `DetectorSensitivitySpec.xml`, `MeasurementGuide.xml`, `ParameterSpec.xml`, `VxWebDeviceServerConfig.json`, `VxWebImageServerConfig.json` |
| `LUT_Data/` | `1.lut` ~ `8.lut` |
| `PARAMETER/` | XIPL 파라미터(`.pim`/`.eap`/`.xtp`/`.egp`) 18개 |
| `BodypartCategory/` | 부위 아이콘 bmp 19개 |
| (그 외) | 디텍터 데이터 `.hs8` 1,218개 + `.pi` 1,218개 |

### 1.2 그래서 Export/Import는 "설정만"이 아니라 **DB 전체 스냅샷**이다

`Data.bak`이 DRF 데이터베이스 전체 백업이므로, **Import는 export 시점의 DB로
되돌린다.** 즉 export 이후에 생성된 환자·검사·영상이 전부 사라진다.

원안 6단계를 그대로 수행하면 이 부작용이 검증 결과에 섞인다. 반드시 아래를
지켜야 한다.

- 이 TC는 **회귀 순서에서 맨 마지막**에 둔다(앞선 TC들이 만든 데이터를 지우므로).
- Import **직전에** 별도 DB 백업을 뜬다(`core/dbreset.py`).
- Import는 파괴적 조작이므로 **사용자 승인 없이 자동 실행하지 않는다.**

### 1.3 `C:\ProgramData\VXvue\Viewer.xml`은 export에 **포함되지 않는다**

ZIP 안에 `Viewer.xml`도 `ProgramData` 경로도 없다. 따라서 Viewer.xml에 있는
**머신 단위 설정은 Import로 복원되지 않을 것으로 예상**된다.

- `Theme`(현재 Onyx Classic), `Language`, `LastLoginID`
- `<Generator product="8">`, `<AIEngine product="3">`, `<Camera UseLiveView="1"/>`
- `DBServer` / `DBName` / `DSN` 등 접속 정보

**기대값 확인 필요**: 이 항목들이 "Import로 복원되지 않는 것이 정상"인가?
정상이라면 판정에서 제외 대상으로 명시해야 하고, 복원되어야 하는 것이라면
결함 후보다. 임의로 정하지 않는다.

## 2. 판정 오라클 — UI 판독 대신 DB + 파일 해시

원안의 "Setting 전체 탭에 들어가 현재 설정을 확인"을 UI 판독으로 구현하면
신뢰도가 낮다. 좌측 메뉴 항목과 체크박스·라디오가 커스텀 owner-draw여서
`GetWindowText`로 **상태를 읽을 수 없다**(실측). Edit/콤보는 읽히지만 전체
설정의 일부에 불과하다.

대신 아래를 스냅샷으로 쓴다. 값 단위로 정확하고, 화면을 열지 않아도 되며,
diff가 그대로 리포트가 된다.

| 스냅샷 요소 | 취득 방법 |
|---|---|
| `CONFIGURATION` 및 `CONFIGURATION_*` 42개 테이블 전체 행 | `core/db.py` `query_many()` 1회 호출 |
| `AE_LIST`(DICOM SCP 등록 + `RemoveSBSC`) | 같음 |
| `TB_PROCEDURE` / `PROCSTEP` / `STEP` / `LOCATION*`(Procedure Manager) | 같음 |
| `LUT`, `IMAGE_PROCESS_PARAM*`, `STITCH_PROTOCOL*` | 같음 |
| `D:\Database\Configuration\*` 파일 해시 | SHA-256 |
| `C:\ProgramData\VXvue\Viewer.xml` 해시 | SHA-256 (1.3절 검증용, 별도 분류) |
| export `.vxs` 내부 엔트리별 CRC (Data.bak 제외) | `zipfile.infolist()` |

UI 캡처는 **증거**로만 남긴다(사람 검토용). 판정 근거로 삼지 않는다.

## 3. 개선한 시나리오 — 3단 비교

원안의 가장 큰 허점은 **"설정을 정말로 바꿨는지"를 검증하지 않는다**는 점이다.
변경이 한 건도 먹지 않았어도 마지막 대조는 통과한다(아무것도 안 바뀌었으니
당연히 같다). 헛된 PASS를 막기 위해 중간 확인을 넣는다.

```text
S0  설정 스냅샷 (기준)
 |
 +--> Export  ->  baseline_A.vxs      (엔트리 CRC 맵 기록)
 |
 +--> 변경 수행 (탭별 1~2개 + Procedure Manager + DICOM)
 |
S1  설정 스냅샷
 |     [검증 1] S1 != S0  — 변경이 실제로 반영되었다  (이게 없으면 시험 무효)
 |     [검증 2] 변경 목록의 각 항목이 S1에서 기대한 새 값인가
 |
 +--> Import  baseline_A.vxs   (파괴적: DB 전체 복원. 사용자 승인 필요)
 +--> 뷰어 재실행 + 로그인
 |
S2  설정 스냅샷
       [검증 3] S2 == S0  — Export 당시 값이 유지되었다
       [검증 4] 복원되지 않은 항목 목록을 그대로 보고(Viewer.xml 계열은 별도 분류)
```

선택적으로 변경 직후 한 번 더 Export(`mutated_B.vxs`)해서 A와 CRC를 비교하면,
"Export가 변경을 반영하는지"까지 함께 검증된다(엔트리 단위로 무엇이 바뀌었는지
바로 보인다).

## 4. 변경 목록(Mutation Table) 설계

"바꿀 수 있는 모든 옵션"은 범위가 너무 넓고 되돌리기 위험도 크다. 대신
**리뷰 가능한 표를 JSON으로 두고** 그것만 바꾼다. 표에는 값 유형과 검증
가능성을 함께 적는다.

```json
{
  "id": "display_general_interpolation",
  "screen": "Display - General",
  "minor_ctrl_id": null,
  "control": {"kind": "combo", "id": null},
  "from": "Bicubic",
  "to": "Bilinear",
  "verify": {"source": "db", "table": "CONFIGURATION", "key": "...(확인 필요)"}
}
```

- `verify.source`가 `db`인 항목만 값 단위 자동 판정한다.
- 체크박스처럼 DB 매핑을 아직 못 찾은 항목은 `verify.source: "snapshot-diff"`로
  두고 **S0/S1 스냅샷의 어느 필드가 바뀌었는지 역추적**해 매핑을 채운다.
  이 역추적 자체가 설정↔DB 매핑표를 만들어 주며, 이후 TC들이 재사용한다.
- DICOM 변경은 기존 SCP(MWL_SCP/PRINT_SCP/BUNNY_TEST)를 건드리지 말고
  **전용 임시 SCP를 추가**하는 방향이 안전하다(다른 TC의 선행 조건 파괴 방지).

## 5. 구현 순서

1. `core/config_snapshot.py` — 2절 스냅샷 취득/비교/리포트
2. `core/vxs.py` — `.vxs` ZIP 엔트리 CRC 맵, A/B 비교
3. `core/dbreset.py` — Import 직전 안전 백업, 실패 시 복구
4. `tests/tc_setting_export_import.py` — 3절 흐름
5. `mutations.json` — 4절 변경 목록(리뷰 후 확정)

## 6. 확인이 필요한 항목

1. **Import를 실제로 수행해도 되는가** — DB 전체가 export 시점으로 복원되어
   현재 검사 데이터(현재 `EM-260818-134831 / Urgent^Patient` 1건)가 사라진다.
2. **Viewer.xml 계열 설정이 복원되지 않는 것이 정상인가**(1.3절).
3. 이 시험을 **어느 TC 번호로 관리할 것인가** — Windows Update 체크리스트에는
   해당 항목이 없다. 기본기능 회귀 쪽 신규 TC로 두면 될지.

## 7. 이후 Step에도 적용할 리포트 언어 기준

각 Step은 시험 목적·구체적인 수행 내용·합격 기준·확인 결과·판정 이유·후속
조치를 사용자 문장으로 출력한다. 원본 DB·파일·로그 값은 보존하되 기술 용어에는
설명을 붙인다. 정확한 실제값을 자동으로 얻지 못하면 추측하지 않고 기대 결과와
같은지 사용자 확인이 필요하다고 적는다. 새 Step은 `core/report_language.py`에
등록하고 `core.result.assert_report_readable()` 검사를 통과해야 완료로 본다.
