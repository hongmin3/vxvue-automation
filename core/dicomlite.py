# -*- coding: utf-8 -*-
r"""최소 DICOM 리더 — Export / Send 결과를 **받은 쪽에서** 확인한다.

Bellalun `auto/core/dicomlite.py`에서 가져왔다(2026-08-19). 파서 자체는 제품과
무관한 DICOM 표준 처리라 그대로 재사용할 수 있다 — `CLAUDE.md` 3절이 금지하는
것은 다른 제품의 **컨트롤 ID·좌표·문구**를 가져오는 것이고, 표준 파일 형식
파서는 해당하지 않는다.

## 왜 필요한가

`TC_WindowsUpdate_05`(DICOM 전송)와 `TC_WindowsUpdate_08`(Study Export)의
Expected Result는 "전송/Export가 성공한다"인데, 제품 UI의 Queue 상태만 보면
**제품이 '보냈다'고 말한 것을 그대로 믿는 것**이 된다. 수신된 파일(또는 Export
산출물)의 태그를 직접 읽어 환자정보·Modality가 실제로 일치하는지 확인한다.

TC08은 "export 된 영상 오픈하여 확인"을 명시적으로 요구하므로 특히 그렇다.

Export/Send 결과 검증에 필요한 최상위 Tag만 읽는다. pydicom이 설치되어 있으면
그쪽을 쓰고, 없으면 내장 파서로 동작한다(검증 PC 추가 설치 불필요 — VXvue
자동화의 `requirements.txt`에도 pydicom은 없다). Pixel Data는 읽지 않는다.
"""

import os
import struct

try:  # pragma: no cover
    import pydicom  # type: ignore
    _HAS_PYDICOM = True
except Exception:
    _HAS_PYDICOM = False

# 검증에 쓰는 Tag (Conformance Statement / TC에서 근거가 확인된 항목만)
TAGS = {
    "SOPClassUID":        (0x0008, 0x0016),
    "SOPInstanceUID":     (0x0008, 0x0018),
    "StudyDate":          (0x0008, 0x0020),
    "Modality":           (0x0008, 0x0060),
    "AccessionNumber":    (0x0008, 0x0050),
    "InstitutionName":    (0x0008, 0x0080),
    "PatientName":        (0x0010, 0x0010),
    "PatientID":          (0x0010, 0x0020),
    "PatientBirthDate":   (0x0010, 0x0030),
    "PatientSex":         (0x0010, 0x0040),
    "BodyPartExamined":   (0x0018, 0x0015),
    "KVP":                (0x0018, 0x0060),
    "StudyInstanceUID":   (0x0020, 0x000D),
    "SeriesInstanceUID":  (0x0020, 0x000E),
    "StudyID":            (0x0020, 0x0010),
    "InstanceNumber":     (0x0020, 0x0013),
    "ImageLaterality":    (0x0020, 0x0062),
    "Rows":               (0x0028, 0x0010),
    "Columns":            (0x0028, 0x0011),
    "ViewPosition":       (0x0018, 0x5101),
}
_BY_TAG = {v: k for k, v in TAGS.items()}

_VR_WITH_LONG_LEN = {b"OB", b"OW", b"OF", b"SQ", b"UT", b"UN"}
_PIXEL_DATA = (0x7FE0, 0x0010)


def _decode(vr, raw):
    if vr in (b"US", b"AE"):
        if vr == b"US":
            return struct.unpack("<H", raw[:2])[0] if len(raw) >= 2 else None
    if vr == b"UL":
        return struct.unpack("<I", raw[:4])[0] if len(raw) >= 4 else None
    try:
        return raw.decode("latin-1").strip().strip("\x00")
    except Exception:
        return None


def _skip_item_undefined(buf, pos, explicit, end):
    """길이 미정 Item(FFFE,E000) 안의 태그들을 Item Delimitation까지 건너뛴다.

    Item 내부는 일반 태그(그룹,엘리먼트,VR,길이,값)의 나열이다 — 8바이트
    고정폭(FFFE류 태그와 같은 모양)으로 가정하고 건너뛰면 VR 필드만큼
    어긋난다(아래 `_parse`의 옛 버그, 2026-08-21 실측: Anatomic Region
    Sequence(0008,2218)처럼 길이 미정 Item을 포함한 시퀀스를 지나가는 순간
    이후 모든 태그 위치가 틀어져 PatientID/PatientName이 안 읽혔다).
    """
    while pos + 8 <= end:
        group, elem = struct.unpack_from("<HH", buf, pos)
        pos += 4
        if (group, elem) == (0xFFFE, 0xE00D):        # Item Delimitation
            return pos + 4
        if (group, elem) == (0xFFFE, 0xE000):        # 드문 중첩 Item
            length = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
            pos = (_skip_item_undefined(buf, pos, explicit, end)
                  if length == 0xFFFFFFFF else pos + length)
            continue
        if explicit:
            vr = buf[pos:pos + 2]
            pos += 2
            if vr in _VR_WITH_LONG_LEN:
                pos += 2
                length = struct.unpack_from("<I", buf, pos)[0]
                pos += 4
            else:
                length = struct.unpack_from("<H", buf, pos)[0]
                pos += 2
        else:
            length = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
        pos = (_skip_undefined_sequence(buf, pos, explicit, end)
              if length == 0xFFFFFFFF else pos + length)
    return pos


def _skip_undefined_sequence(buf, pos, explicit, end):
    """길이 미정 SQ 값 전체(Item 0개 이상 + Sequence Delimitation)를 건너뛴다."""
    while pos + 8 <= end:
        group, elem = struct.unpack_from("<HH", buf, pos)
        length = struct.unpack_from("<I", buf, pos + 4)[0]
        pos += 8
        if (group, elem) == (0xFFFE, 0xE0DD):        # Sequence Delimitation
            return pos
        if length == 0xFFFFFFFF:
            pos = _skip_item_undefined(buf, pos, explicit, end)
        else:
            pos += length
    return pos


def _parse(buf, pos, explicit, wanted, out, end=None):
    end = len(buf) if end is None else end
    while pos + 8 <= end:
        group, elem = struct.unpack_from("<HH", buf, pos)
        pos += 4
        if (group, elem) == _PIXEL_DATA:
            return
        if group == 0xFFFE:  # item / delimiter
            length = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
            if length == 0xFFFFFFFF:
                continue
            pos += length
            continue

        if explicit:
            vr = buf[pos:pos + 2]
            pos += 2
            if vr in _VR_WITH_LONG_LEN:
                pos += 2
                length = struct.unpack_from("<I", buf, pos)[0]
                pos += 4
            else:
                length = struct.unpack_from("<H", buf, pos)[0]
                pos += 2
        else:
            vr = b"UN"
            length = struct.unpack_from("<I", buf, pos)[0]
            pos += 4

        if length == 0xFFFFFFFF:  # 정의되지 않은 길이의 SQ 값 — 재귀적으로 건너뛴다
            pos = _skip_undefined_sequence(buf, pos, explicit, end)
            continue

        if (group, elem) in wanted:
            # 호출자는 TAGS에 없는 태그도 요청한다(파일 메타의 TransferSyntaxUID
            # (0002,0010)이 그 경우다). 그때 _BY_TAG를 그대로 인덱싱하면
            # KeyError로 파싱 전체가 죽는다(2026-08-18 실측: 수신 객체 판독 실패).
            # 이름이 없으면 태그를 그대로 키로 쓴다.
            key = _BY_TAG.get((group, elem), (group, elem))
            out[key] = _decode(vr, buf[pos:pos + length])
        pos += length


def read_tags(path, tags=None):
    """DICOM 파일에서 지정 Tag를 dict로 읽는다. 실패 시 {'_error': ...}."""
    names = tags or list(TAGS.keys())
    if _HAS_PYDICOM:
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
            out = {}
            for n in names:
                v = getattr(ds, n, None)
                out[n] = None if v is None else str(v)
            return out
        except Exception as exc:
            return {"_error": f"pydicom 읽기 실패: {exc}"}

    try:
        with open(path, "rb") as f:
            buf = f.read()
    except OSError as exc:
        return {"_error": str(exc)}

    if len(buf) < 132 or buf[128:132] != b"DICM":
        return {"_error": "DICM preamble 없음 (DICOM 파일 아님)"}

    wanted = {TAGS[n] for n in names if n in TAGS}
    out = {}

    # File Meta (group 0002)는 항상 Explicit VR Little Endian
    pos = 132
    meta_end = len(buf)
    if buf[132:136] == b"\x02\x00\x00\x00":
        # (0002,0000) File Meta Information Group Length
        glen = struct.unpack_from("<I", buf, 132 + 8)[0]
        meta_end = 132 + 12 + glen
    ts = {}
    _parse(buf, pos, True, {(0x0002, 0x0010)}, ts, meta_end)
    # TransferSyntaxUID는 TAGS에 없으므로 직접 추출
    tsuid = _find_transfer_syntax(buf, 132, meta_end)
    explicit = not (tsuid or "").startswith("1.2.840.10008.1.2") or tsuid != "1.2.840.10008.1.2"
    if tsuid == "1.2.840.10008.1.2":
        explicit = False

    _parse(buf, meta_end, explicit, wanted, out)
    out.setdefault("_transfer_syntax", tsuid)
    for n in names:
        out.setdefault(n, None)
    return out


def _find_transfer_syntax(buf, pos, end):
    while pos + 8 <= end:
        group, elem = struct.unpack_from("<HH", buf, pos)
        vr = buf[pos + 4:pos + 6]
        if vr in _VR_WITH_LONG_LEN:
            length = struct.unpack_from("<I", buf, pos + 8)[0]
            data_at = pos + 12
        else:
            length = struct.unpack_from("<H", buf, pos + 6)[0]
            data_at = pos + 8
        if (group, elem) == (0x0002, 0x0010):
            return buf[data_at:data_at + length].decode("latin-1").strip("\x00 ")
        pos = data_at + length
    return None


def scan_dir(root, tags=None):
    """폴더 하위 DICOM 파일을 모두 읽는다. (확장자 무관, DICM 시그니처 기준)"""
    found = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            p = os.path.join(dirpath, name)
            try:
                with open(p, "rb") as f:
                    if f.read(132)[128:132] != b"DICM":
                        continue
            except OSError:
                continue
            info = read_tags(p, tags)
            info["_path"] = p
            found.append(info)
    return found
