# -*- coding: utf-8 -*-
"""화면 캡처와 구조적 유사도(SSIM) 비교.

TC_WindowsUpdate_14(Setting 각 화면 표시 확인)에서 "빈 화면 / 깨짐 / 겹침"을
사람 눈 대신 잡아내기 위한 모듈이다. Bellalun `ORG/Setting Export/
bellalunSetting.py`가 검증한 방식(기준 캡처와 SSIM 비교, 임계값 0.99)을
그대로 따르되, 두 가지를 보완했다.

1. `scikit-image`가 있으면 그것을 쓰고, 없으면 **numpy만으로 계산하는 대체
   구현**으로 넘어간다. 검증 PC에 추가 설치를 요구하지 않기 위해서다.
2. SSIM만으로는 "기준 캡처도 이미 비어 있었던" 경우를 못 잡는다. 그래서
   화면이 비어 있는지(`blankness`)를 따로 본다 — 표준편차와 최빈색 비율로
   판정하며, 이는 기준 캡처가 없는 최초 실행에서도 동작한다.
"""

import os

from PIL import Image, ImageDraw, ImageGrab

SSIM_THRESHOLD = 0.99

# 비어 있다고 볼 기준: 화소 표준편차가 이보다 낮고, 한 색이 이 비율 이상을 차지
BLANK_STDDEV = 6.0
BLANK_DOMINANT_RATIO = 0.985


def capture(path, bbox=None, all_screens=False):
    """화면(또는 영역)을 캡처해 저장하고 경로를 반환한다.

    `all_screens=True`는 가상 데스크톱 전체(이 PC는 5560x2297)를 잡은 뒤
    자르기 때문에 같은 영역을 뜨는데도 5배 느리다(0.20s vs 0.04s 실측).
    VXvue는 주 모니터에서 동작하므로 기본값을 False로 둔다. 화면당 캡처가
    수백 번 발생하는 순회 시험에서는 이 차이가 전체 실행 시간을 지배한다.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    img = ImageGrab.grab(bbox=bbox, all_screens=all_screens)
    img.save(path)
    return path


def _gray_array(path_or_img):
    import numpy as np
    img = path_or_img
    if isinstance(img, str):
        img = Image.open(img)
    return np.asarray(img.convert("L"), dtype=np.float64)


def blankness(path_or_img):
    """화면이 얼마나 '비어 있는지' 재서 (is_blank, stddev, dominant_ratio) 반환."""
    import numpy as np
    a = _gray_array(path_or_img)
    std = float(a.std())
    counts = np.bincount(a.astype(np.uint8).ravel(), minlength=256)
    dominant = float(counts.max()) / float(a.size)
    return (std < BLANK_STDDEV and dominant > BLANK_DOMINANT_RATIO), std, dominant


def _ssim_numpy(a, b, c1=(0.01 * 255) ** 2, c2=(0.03 * 255) ** 2, win=8):
    """scikit-image가 없을 때 쓰는 블록 단위 SSIM 근사.

    win x win 블록마다 SSIM을 계산하고 평균한다. 전역 SSIM과 달리 국소적인
    깨짐(한쪽 패널만 비어 있는 경우 등)을 잡아낼 수 있다.
    """
    import numpy as np
    h = min(a.shape[0], b.shape[0]) // win * win
    w = min(a.shape[1], b.shape[1]) // win * win
    if h == 0 or w == 0:
        return 0.0
    a = a[:h, :w].reshape(h // win, win, w // win, win).transpose(0, 2, 1, 3)
    b = b[:h, :w].reshape(h // win, win, w // win, win).transpose(0, 2, 1, 3)
    a = a.reshape(-1, win * win)
    b = b.reshape(-1, win * win)
    mu_a, mu_b = a.mean(axis=1), b.mean(axis=1)
    va, vb = a.var(axis=1), b.var(axis=1)
    cov = ((a - mu_a[:, None]) * (b - mu_b[:, None])).mean(axis=1)
    num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    den = (mu_a ** 2 + mu_b ** 2 + c1) * (va + vb + c2)
    return float(np.mean(num / den))


def ssim(path_a, path_b):
    """두 캡처의 구조적 유사도(0~1). 크기가 다르면 b를 a에 맞춰 줄인다."""
    import numpy as np
    img_a, img_b = Image.open(path_a), Image.open(path_b)
    if img_a.size != img_b.size:
        img_b = img_b.resize(img_a.size)
    a, b = _gray_array(img_a), _gray_array(img_b)
    try:
        from skimage.metrics import structural_similarity
        return float(structural_similarity(a, b, data_range=255))
    except Exception:
        return _ssim_numpy(a, b)


def compare(baseline_path, current_path, threshold=SSIM_THRESHOLD, diff_path=None):
    """기준 캡처와 비교한다.

    반환: dict(score=..., passed=..., diff=경로 또는 None)
    기준이 없으면 score=None, passed=None (호출부가 '기준 생성'으로 처리).
    """
    if not baseline_path or not os.path.exists(baseline_path):
        return {"score": None, "passed": None, "diff": None,
                "note": "기준 캡처 없음(이번 실행분이 기준이 됨)"}

    score = ssim(baseline_path, current_path)
    passed = score >= threshold
    diff = None
    if not passed and diff_path:
        diff = _write_diff(baseline_path, current_path, score, diff_path)
    return {"score": score, "passed": passed, "diff": diff, "note": ""}


def _write_diff(baseline_path, current_path, score, out_path):
    """실패 시 기준/현재를 나란히 붙인 비교 이미지를 남긴다."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    a, b = Image.open(baseline_path), Image.open(current_path)
    comp = Image.new("RGB", (a.width + b.width + 10, max(a.height, b.height) + 40),
                     (240, 240, 240))
    draw = ImageDraw.Draw(comp)
    draw.text((10, 10), "%s | SSIM %.6f  (왼쪽=기준, 오른쪽=현재)"
              % (os.path.basename(current_path), score), fill=(0, 0, 0))
    comp.paste(a.convert("RGB"), (5, 35))
    comp.paste(b.convert("RGB"), (a.width + 5, 35))
    comp.save(out_path)
    return out_path
