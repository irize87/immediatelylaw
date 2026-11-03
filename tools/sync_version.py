# -*- coding: utf-8 -*-
"""버전 단일 정본 동기화 도구.

정본은 immediatelylaw/__init__.py의 __version__ 하나다. 앱 코드(트레이 메뉴·
설정창·업데이읕)와 릴리스 산출물(app-latest.json·zip 이름)은 모두 여기서
파생되지만, 랜딩 페이지의 정적 폴백 링크(web/index.html의 zip href 2곳)와
README 버전 배지는 문서 상에 리터럴로 존재해 수동 유지가 필요했다.

사용: 버전 상향 후  python -m tools.sync_version
      → web/index.html의 폴백 zip href 2곳과 README 배지 2곳을 __version__에 맞춘다.
      (README의 설치 파일 링크는 `-latest.zip` 고정명이라 버전 동기 불필요.)

누락 견제: tests/test_version_sync.py가 상시 감시, make_release가 발행 직전
다시 확인(어긋나면 발행 중단)."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from immediatelylaw import __version__  # noqa: E402

# web/index.html 안의 폴백 링크 패턴(offline/online 각 1곳이 기대치).
HREF_RE = re.compile(r"ImmediatelyLaw-(?:offline|online)-(\d+\.\d+\.\d+)\.zip")

# README 상단 버전 배지(shields.io URL과 alt 텍스트 두 곳에 같은 버전이 들어간다).
BADGE_RE = re.compile(r"(version-)v(\d+\.\d+\.\d+)(-blue)")
ALT_RE = re.compile(r'alt="v(\d+\.\d+\.\d+)"')


def find_landing_versions():
    """(현재 html의 폴백 버전 목록, 파일 내용) — 도구는 이것만 읽는다."""
    with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as f:
        html = f.read()
    return HREF_RE.findall(html), html


def _sync_readme_badge(text):
    """README 텍스트의 버전 배지·alt를 __version__으로 맞춘다. (본문, 교체수)."""
    n = 0

    def _b(m):
        nonlocal n
        if m.group(2) != __version__:
            n += 1
        return f"{m.group(1)}v{__version__}{m.group(3)}"

    def _a(m):
        return f'alt="v{__version__}"'

    text = BADGE_RE.sub(_b, text)
    text = ALT_RE.sub(_a, text)
    return text, n


def readme_versions():
    """README에 적힌 버전 배지 목록(테스트가 정본 일치 확인에 쓴다)."""
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        text = f.read()
    return [v for _p, v, _s in BADGE_RE.findall(text)]


def sync(write=True):
    """랜딩 폴백·README 배지를 __version__으로 맞춤. 변경 파일 수 반환."""
    changed = 0

    found, html = find_landing_versions()
    bad = [v for v in found if v != __version__]
    if bad:
        new_html, n = HREF_RE.subn(
            lambda m: m.group(0).replace(m.group(1), __version__), html)
        if write:
            with open(os.path.join(ROOT, "web", "index.html"), "w",
                      encoding="utf-8", newline="") as f:
                f.write(new_html)
        print(f"web/index.html 폴백 {len(bad)}곳 갱신: "
              f"{sorted(set(bad))} → v{__version__} (교체 {n}곳)")
        changed += 1
    else:
        print(f"web/index.html 이미 정합 (v{__version__})")

    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        text = f.read()
    new_text, n = _sync_readme_badge(text)
    if n:
        if write:
            with open(os.path.join(ROOT, "README.md"), "w",
                      encoding="utf-8", newline="") as f:
                f.write(new_text)
        print(f"README.md 버전 배지 {n}곳 갱신 → v{__version__}")
        changed += 1
    else:
        print(f"README.md 이미 정합 (v{__version__})")
    return changed


if __name__ == "__main__":
    sync()
