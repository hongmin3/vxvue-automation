# -*- coding: utf-8 -*-
r"""TC11(AI 분석)용 VXCAD-CXR 검증 샘플 영상 — 데모 영상 교체.

## 왜 필요한가

기존 TC11은 F2(가상 촬영)로 얻은 **일반 데모 영상**에 AI Tool을 열어 화면
구성만 확인하고, 실제 분석(Request an analysis)은 결과물이 근거 없이 나올까봐
누르지 않았다. 사용자 지시(2026-08-24): 사내 공유폴더의 VXCAD-CXR 검증용
샘플 영상(소견별 3종)을 실제로 데모 영상으로 등록해 써서, AI Tool이 **의미
있는 소견이 있는 실제 영상**에 대해 동작하는 모습까지 확인하라는 것.

## 데모 영상 교체 메커니즘 (근거: Service Manual Rev.1.0.11 p.170-171, D-17-518, 5.2.5절)

> 기본 데모 영상으로 사용하고자 하는 영상(.Img)의 이름을 `Default.img`로
> 변경하고 `<data_dir>\DemoImage` 경로로 이동하십시오.
> VXvue에서 생성된 '.Img' 영상 형식만 데모 영상으로 사용할 수 있습니다.

실측(2026-08-24, 이 PC `data_dir=D:\Database`): `DemoImage` 폴더에 이미
`Default.img`(31.8MB)가 있고, F2로 촬영하면 Bodypart/Projection과 무관하게
항상 이 파일의 내용이 나온다(그래서 이전 세션들의 "가상 획득영상은 선택한
스텝과 어떠한 연관성도 없다"는 매뉴얼 문구와 일치). Bodypart/Projection별
파일(`chest.posteroanterior.1` 형식)은 두지 않는다 — 그러면 이후 다른 TC의
Chest/PA 데모 촬영에도 영향을 준다. **`Default.img` 하나만, TC11 실행 구간
동안만 교체하고 끝나면 반드시 원복**한다(다른 TC와 충돌 없음, 원복 실패 시
그 사실을 결과에 남긴다).

## 샘플 원본과 로컬 캐시

원본은 사내 공유폴더에 있다(경로는 `VXvue/HANDOFF.md`에만 기록 — 사내망
정보라 `auto/`에는 두지 않는다, CLAUDE.md 6절). 2026-08-24에 3종
(Nodule Mass / Pleural Effusion / Pneumothorax) 각 1장을 `auto/TestData/
tc11_ai_samples/<소견>/*.img`로 1회 복사해 로컬 캐시로 둔다(`.gitignore`
대상 — 사내 자산이라 공개 저장소에 커밋하지 않는다). 코드는 이 로컬 캐시만
읽고, 실행 중 네트워크 공유에 다시 접근하지 않는다(회귀 안정성 — 공유폴더가
그 순간 안 붙어 있어도 이 TC가 막히지 않도록).
"""

import glob
import os
import random
import shutil

SAMPLE_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "TestData", "tc11_ai_samples")

DEMO_SUBDIR = "DemoImage"
DEFAULT_IMG = "Default.img"


class AiSampleError(RuntimeError):
    pass


def list_local_samples(root=None):
    """로컬 캐시의 샘플 영상 목록. 반환: [{"finding": 소견명, "path": 절대경로}, ...]."""
    root = root or SAMPLE_ROOT
    out = []
    for path in sorted(glob.glob(os.path.join(root, "*", "*.img"))):
        finding = os.path.basename(os.path.dirname(path))
        out.append({"finding": finding, "path": path})
    return out


def pick_random(root=None):
    """샘플 중 하나를 무작위로 고른다. 없으면 None."""
    samples = list_local_samples(root)
    return random.choice(samples) if samples else None


def demo_image_path(data_dir):
    return os.path.join(data_dir, DEMO_SUBDIR, DEFAULT_IMG)


def stage_default_image(data_dir, sample_path):
    """`Default.img`를 `sample_path`로 바꾸기 전에 원본을 백업한다.

    반환: 백업 파일 경로(`restore_default_image()`에 그대로 넘길 것).
    """
    target = demo_image_path(data_dir)
    if not os.path.isfile(target):
        raise AiSampleError("기본 데모 영상(%s)이 없다 — 먼저 존재를 확인할 것" % target)
    backup = target + ".tc11_orig_backup"
    shutil.copy2(target, backup)
    shutil.copy2(sample_path, target)
    return backup


def restore_default_image(data_dir, backup_path):
    """`stage_default_image()`가 만든 백업으로 `Default.img`를 원복한다."""
    target = demo_image_path(data_dir)
    shutil.copy2(backup_path, target)
    os.remove(backup_path)
