# -*- coding: utf-8 -*-
"""버전 단일 정본 견제 테스트.

정본: immediatelylaw/__init__.py::__version__.
앱 코드·릴리스 산출물은 전부 참조로 파생되므로 리터럴 분산이 없고,
수동 지점(web/index.html 정적 폴백 zip href 2곳, README 버전 배지)을
이 테스트가 감시한다. 어긋나면 python -m tools.sync_version 으로 맞춘다."""
import os
import re

from immediatelylaw import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HREF_RE = re.compile(r"ImmediatelyLaw-(?:offline|online)-(\d+\.\d+\.\d+)\.zip")
BADGE_RE = re.compile(r"version-v(\d+\.\d+\.\d+)-blue")


def test_landing_fallback_follows_single_source_of_truth():
    with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as f:
        found = HREF_RE.findall(f.read())
    assert len(found) == 2, f"정적 폴백 링크는 2곳이어야 하는데 {len(found)}곳"
    assert all(v == __version__ for v in found), (
        f"web/index.html 폴백 {found} != 정본 v{__version__} — "
        "python -m tools.sync_version 실행 후 커밋")


def test_readme_badge_follows_single_source_of_truth():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        found = BADGE_RE.findall(f.read())
    assert found, "README 버전 배지를 찾지 못함"
    assert all(v == __version__ for v in found), (
        f"README 배지 {found} != 정본 v{__version__} — "
        "python -m tools.sync_version 실행 후 커밋")


def test_readme_has_no_hardcoded_server_ip():
    # README는 고정 링크(-latest.zip)만 쓰고 배포 서버 IP를 노출하지 않는다.
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        text = f.read()
    assert not re.search(r"(?<!\d)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!\d)",
                         text), "README에 하드코딩된 IP 주소가 있습니다"


def test_version_string_shape():
    # 세 자리 숫자형(도구들의 파싱·정규식 패턴이 이 형태를 전제한다).
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__
