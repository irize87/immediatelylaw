# -*- coding: utf-8 -*-
"""버전 단일 정본 동기화 도구.

정본은 immediatelylaw/__init__.py의 __version__ 하나다. 앱 코드(트레이 메뉴·
설정창·업데이터)와 릴리스 산출물(app-latest.json·zip 이름)은 모두 여기서
파생되지만, 랜딩 페이지의 정적 폴백 링크(web/index.html의 zip href 2곳)만
HTML 상에 리터럴로 존재해 수동 유지가 필요했다.

사용: 버전 상향 후  python -m tools.sync_version
      → web/index.html의 폴백 zip href 2곳을 __version__에 맞춘다.

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


def find_landing_versions():
    """(현재 html의 폴백 버전 목록, 파일 내용) — 도구는 이것만 읽는다."""
    with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as f:
        html = f.read()
    return HREF_RE.findall(html), html


def sync(write=True):
    """폴백 링크를 __version__으로 맞춤. 변경 수를 반환(0이면 이미 정합)."""
    found, html = find_landing_versions()
    bad = [v for v in found if v != __version__]
    if not bad:
        print(f"web/index.html 이미 정합 (v{__version__}, 변경 없음)")
        return 0
    new_html, n = HREF_RE.subn(
        lambda m: m.group(0).replace(m.group(1), __version__), html)
    if write:
        with open(os.path.join(ROOT, "web", "index.html"), "w",
                  encoding="utf-8", newline="") as f:
            f.write(new_html)
    print(f"web/index.html 폴백 {len(bad)}곳 갱신: "
          f"{sorted(set(bad))} → v{__version__} (교체 {n}곳)")
    return len(bad)


if __name__ == "__main__":
    sync()
