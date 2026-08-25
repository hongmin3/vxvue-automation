# -*- coding: utf-8 -*-
r"""사양서·매뉴얼 원문을 코드에서 직접 찾아 인용한다.

`VXvue/CLAUDE.md` 2절은 판정 근거의 우선순위를 정하고, 3절은 "판정 근거를
제시할 때는 `문서명 → SRS No·기능명 → 세부 항목·조건 → 페이지/장/절` 순서로
출처를 남긴다"고 요구한다. 그런데 근거 문서가 전부 `.pdf`라 grep이 되지 않아
지금까지 사람이 열어 보고 손으로 옮겨 적어야 했다.

이 모듈이 그 간격을 메운다(Bellalun `auto/core/specs.py`를 이식하되 VXvue의
문서 구성과 SRS 번호 체계에 맞췄다).

## VXvue의 요구사항 ID는 `VP-###` 형식이다

Bellalun 사양서는 `SRS 01-10-10` 형식이지만, VXvue 사양서는 실측 결과
**`VP-415 - Verify License Registration Status`** 처럼 `VP-` + 숫자 + 제목
형식을 쓴다(2026-08-19 확인). 그래서 `VP_PATTERN`으로 뽑고, 인용문에는
쪽 번호와 함께 그 VP 번호를 넣는다.

## 캐시

`pypdf`로 쪽 단위 텍스트를 뽑아 원본과 같은 폴더에 `.txt`로 캐시한다. 사양서1은
141쪽, System Integration Guide는 401쪽이라 매번 추출하면 느리다. 캐시가
있으면 이후 세션에서 사람도 그냥 grep할 수 있다.

사용 예

    from core import specs

    hits = specs.search(cfg, "Demo License")
    # [{'source': '사양서1', 'page': 7, 'vp': ['VP-415 - Verify License ...'],
    #   'text': '... VXvue Demo License ...'}, ...]

    note = specs.cite(cfg, r"supports up to 16 options")
    # '근거: 사양서1 7쪽 VP-415 - Verify License Registration Status — "..."'
"""

import io
import os
import re

KNOWLEDGE_DIR = "VXvue 지식파일"

# VXvue 사양서의 요구사항 ID (실측: "VP-415 - Verify License Registration Status")
VP_PATTERN = re.compile(r"VP-\d+\s*-\s*[^\n(]{2,60}")

# 매뉴얼은 VP 번호 대신 장·절 번호를 쓴다(실측: Service Manual "4.2.5 License 메뉴").
SECTION_PATTERN = re.compile(r"^\s*(\d+\.\d+(?:\.\d+)?)\s+(\S[^\n]{1,50})", re.M)

# 파일명 일부 -> 짧은 이름. 파일명에 개정 날짜가 붙어 바뀔 수 있으므로 부분
# 일치로 찾는다. `VXvue/CLAUDE.md` 4절의 문서 목록과 대응한다.
DOC_FILES = {
    # 번호 사양서(사양서1, 2, 3 ...)는 **여기 열거하지 않는다** — 개수가 늘어나므로
    # `_SPEC_NUM_RE` 패턴으로 찾는다(`spec_shorts()` 참고).
    "License SRS": "Licence Manager SRS",
    "Operation Manual": "VXvue Operation Manual",
    "Service Manual": "VXvue Service Manual",
    "DICOM CS": "DICOM Conformance Statement",
    "Integration Guide": "System Integration Guide",
    "Web API": "Web System Design",
}

# 사양이 아니라 조작 절차/연동 구성 문서 — 기본 검색 대상에서 뺀다.
# `CLAUDE.md` 2절: 매뉴얼은 사양서보다 우선하지 않는다.
#: 하위 호환용 — 호출부가 명시적으로 넘기지 않으면 `search()`가 `spec_only(cfg)`로
#: 실재하는 사양서를 찾는다. 이 상수를 근거 목록으로 신뢰하지 말 것.
SPEC_ONLY = None


class SpecError(RuntimeError):
    pass


def knowledge_dir(cfg=None, root=None):
    """`VXvue 지식파일` 폴더를 PC 독립적으로 찾는다.

    `core/checklist.source_path()`와 같은 방식 — 저장소 위치 기준으로 위로
    올라가며 찾는다. 절대경로를 코드에 박지 않는다.
    """
    override = ((cfg or {}).get("knowledge_dir") or "").strip()
    if override and os.path.isdir(override):
        return override
    here = os.path.abspath(root or os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    for _ in range(4):                      # auto -> VXvue -> 자동화 ...
        here = os.path.dirname(here)
        if not here:
            break
        for candidate in (os.path.join(here, KNOWLEDGE_DIR),
                          os.path.join(here, "VXvue", KNOWLEDGE_DIR)):
            if os.path.isdir(candidate):
                return candidate
    return ""


#: `(사양서) VXvue 사양서<N>(날짜).pdf` — N을 그대로 짧은 이름으로 쓴다.
_SPEC_NUM_RE = re.compile(r"^\(사양서\)\s*VXvue\s*사양서\s*(\d+)\s*\(")


def spec_shorts(cfg=None):
    """지식파일 폴더에 **실제로 있는** 번호 사양서의 짧은 이름 목록(번호순).

    **개수를 코드에 박지 않는다**(사용자 지시, 2026-08-25). 사양서는 늘어난다 —
    2026-08-20에 3종 → 5종(사양서4·5 신설)이 됐는데 `DOC_FILES`에 등록되지 않아
    `search()`가 그 두 권을 **조용히 건너뛰고 있었다**(2026-08-25 발견). 근거를
    못 찾은 것과 문서를 아예 열지 않은 것이 구분되지 않는 상태였다. 그래서
    파일명의 `(사양서) VXvue 사양서<N>` 패턴으로 찾는다.
    """
    root = knowledge_dir(cfg)
    if not root:
        return []
    nums = []
    for name in os.listdir(root):
        if not name.lower().endswith(".pdf"):
            continue
        m = _SPEC_NUM_RE.match(name)
        if m:
            nums.append(int(m.group(1)))
    return ["사양서%d" % n for n in sorted(nums)]


def spec_only(cfg=None):
    """`search()`의 기본 검색 대상 — 실재하는 번호 사양서 + License SRS."""
    return tuple(spec_shorts(cfg)) + ("License SRS",)


def doc_paths(cfg=None, only=None):
    """근거 문서 경로를 {짧은 이름: 경로}로 돌려준다.

    번호 사양서는 `DOC_FILES` 등록 여부와 무관하게 파일명 패턴으로 잡는다 —
    새 사양서가 추가돼도 코드를 고치지 않아도 되게 하려는 것이다.
    """
    root = knowledge_dir(cfg)
    if not root:
        return {}
    wanted = set(only) if only else None
    found = {}
    for name in os.listdir(root):
        if not name.lower().endswith(".pdf"):
            continue
        m = _SPEC_NUM_RE.match(name)
        if m:
            short = "사양서%d" % int(m.group(1))
            if wanted is None or short in wanted:
                found[short] = os.path.join(root, name)
            continue
        for short, marker in DOC_FILES.items():
            if wanted is not None and short not in wanted:
                continue
            if marker in name:
                found[short] = os.path.join(root, name)
    return found


def _cache_path(pdf_path):
    """추출 텍스트 캐시 경로. 원본과 같은 폴더에 `.txt`로 둔다.

    다음 사람이 grep으로 바로 찾을 수 있는 것이 목적이다. 이 `.txt`는 사양서
    원문이므로 **git에 올리지 않는다**(`VXvue/CLAUDE.md` 6절 — 지식파일 폴더
    전체가 저장소 범위 밖이다).
    """
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    for prefix in ("(사양서) ", "(매뉴얼) "):
        base = base.replace(prefix, "")
    return os.path.join(os.path.dirname(pdf_path), base + ".txt")


def extract(pdf_path, force=False):
    """PDF 텍스트를 쪽 단위로 뽑고 `.txt`로 캐시한다.

    반환: 쪽별 문자열 리스트(0번째 원소가 1쪽).
    캐시가 원본보다 새로우면 재추출하지 않는다.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:                      # pragma: no cover
        raise SpecError(
            "pypdf가 없어 사양서를 읽을 수 없습니다. "
            "`python -m pip install -r requirements.txt`로 설치하십시오.") from exc

    cache = _cache_path(pdf_path)
    if not force and os.path.isfile(cache):
        if os.path.getmtime(cache) >= os.path.getmtime(pdf_path):
            return io.open(cache, encoding="utf-8").read().split("\f")

    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:                           # noqa: BLE001 - 한 쪽 실패로 전체를 버리지 않는다
            pages.append("")
    try:
        io.open(cache, "w", encoding="utf-8", newline="\n").write("\f".join(pages))
    except OSError:
        pass                                        # 캐시 실패는 치명적이지 않다
    return pages


def search(cfg, pattern, flags=re.I, context=200, limit=20, only=None):
    """근거 문서에서 문구를 찾아 쪽 번호와 VP 번호를 함께 돌려준다.

    반환: [{"source": 짧은 이름, "page": 1-based 쪽, "vp": [ID...],
            "text": 주변 문구}]

    `only`로 검색 대상을 좁힌다. 기본은 사양서류만 — `CLAUDE.md` 2절이 사양서를
    매뉴얼보다 우선하므로, 매뉴얼 근거가 필요하면 호출부가 명시적으로
    `only=("Service Manual",)`처럼 지정한다.
    """
    regex = re.compile(pattern, flags)
    if only is None:                       # 기본: 실재하는 사양서 + License SRS
        only = spec_only(cfg)
    out = []
    for short, path in sorted(doc_paths(cfg, only=only).items()):
        pages = extract(path)
        for index, page_text in enumerate(pages, start=1):
            if not page_text:
                continue
            match = regex.search(page_text)
            if not match:
                continue
            start = max(0, match.start() - context // 2)
            snippet = " ".join(page_text[start:match.end() + context // 2].split())
            prev = pages[index - 2] if index >= 2 else ""
            out.append({
                "source": short,
                "page": index,
                "vp": _ids_near(page_text, match.start(), VP_PATTERN, prev),
                "section": _ids_near(page_text, match.start(), SECTION_PATTERN, prev),
                "text": snippet,
            })
            if len(out) >= limit:
                return out
    return out


def _ids_near(page_text, pos, pattern, prev_page_text=""):
    """매치 위치 기준으로 **바로 앞에 나온** ID를 먼저 놓고 목록을 만든다.

    사양서는 "ID 다음에 그 요구사항의 본문"이 오는 구조이므로, 매치 앞쪽의 가장
    가까운 ID가 근거다. 단순 정렬로는 두 번 틀렸다(둘 다 2026-08-19 실측).

    1. 한 쪽에 요구사항이 여러 개 있는 경우 — 사양서1 7쪽에는 VP-415의 본문과
       그 뒤에 시작하는 `VP-416 - Check System Status`가 함께 있다.
    2. **요구사항 제목이 이전 쪽 끝에 있고 본문만 다음 쪽에 있는 경우** —
       `VP-415 - Verify License Registration Status`는 6쪽 마지막 줄이고
       "supports up to 16 options" 본문은 7쪽이다. 그래서 같은 쪽만 보면
       앞쪽 ID가 아예 없어 뒤에 나온 VP-416이 뽑혔다. 이럴 때는 이전 쪽의
       **마지막** ID로 거슬러 올라간다.
    """
    def found(text_block, offset):
        items = []
        for m in pattern.finditer(text_block or ""):
            label = (m.group(0) if pattern is VP_PATTERN
                     else "%s %s" % (m.group(1), m.group(2))).strip()
            items.append((m.start() + offset, " ".join(label.split())))
        return items

    hits = found(page_text, 0)
    before = [(p, t) for p, t in hits if p <= pos]
    after = [(p, t) for p, t in hits if p > pos]
    if not before:
        # 이전 쪽 끝의 마지막 ID가 이 본문의 근거다. 음수 위치를 주어 항상
        # 같은 쪽의 뒤쪽 ID보다 먼저 오게 한다.
        prev = found(prev_page_text, -(len(prev_page_text or "") + 1))
        if prev:
            before = [max(prev, key=lambda x: x[0])]

    ordered = [t for _, t in sorted(before, key=lambda x: -x[0])] \
        + [t for _, t in sorted(after, key=lambda x: x[0])]
    seen, uniq = set(), []
    for t in ordered:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def cite(cfg, pattern, only=None, **kw):
    """`search` 결과를 판정 `note`에 넣을 한 줄 인용문으로 만든다.

    찾지 못하면 빈 문자열을 돌려준다. **근거가 없으면 없다고 말하는 것**이
    이 프로젝트의 규칙(`CLAUDE.md` 3절)이라, 억지로 문구를 만들지 않는다.
    """
    hits = search(cfg, pattern, limit=1, only=only, **kw)
    if not hits:
        return ""
    hit = hits[0]
    # 사양서는 VP 번호, 매뉴얼은 장·절 번호를 인용 단위로 쓴다.
    ident = (hit["vp"] or hit.get("section") or [""])[0]
    ident = " %s" % ident if ident else ""
    return "근거: %s %d쪽%s — \"%s\"" % (hit["source"], hit["page"], ident,
                                       hit["text"][:140])
