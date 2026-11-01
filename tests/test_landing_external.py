# -*- coding: utf-8 -*-
"""랜딩 자체 호스팅 정책 감시.

정책: 랜딩 페이지는 폰트·스타일·스크립트를 외부에서 가져오지 않는다
(CDN 공급망 의존 제거 — 폰트는 web/fonts에 SIL OFL 텍스트 포함 보관).
<a href> 내비게이션 링크(github·law.go.kr 등)와 SVG 네임스페이스,
같은 소스(배포 서버) 참조는 허용된다."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "web", "fonts", "PretendardVariable.woff2")


def html():
    with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as f:
        return f.read()


def test_no_third_party_runtime_fetches():
    h = html()
    for host in ("cdn.jsdelivr", "fonts.googleapis", "unpkg.com", "cdnjs"):
        assert host not in h, f"외부 CDN 참조 잔존: {host}"
    assert not re.search(r"<link[^>]+rel=[\"']?stylesheet[^>]*https?://", h,
                         re.I), "외부 스타일시트 링크 금지"
    assert not re.search(r"<script[^>]+src=[\"']?https?://", h, re.I), \
        "외부 스크립트 금지"
    assert not re.search(r"url\(['\"]?https?://", h, re.I), \
        "CSS url() 외부 참조 금지"
    assert not re.search(r"@import\s+url", h, re.I), "@import 금지"


def test_self_hosted_font_present_and_valid():
    assert "fonts/PretendardVariable.woff2" in html()
    assert os.path.getsize(FONT) > 1_000_000, "폰트 파일이 비정상적으로 작다"
    with open(FONT, "rb") as f:
        assert f.read(4) == b"wOF2", "woff2 매직 넘버 불일치"
    # OFL 재배포 요건(라이선스 텍스트 동봉).
    ofl = os.path.join(ROOT, "web", "fonts", "OFL.txt")
    assert os.path.getsize(ofl) > 1_000
    assert "SIL Open Font License" in open(ofl, encoding="utf-8").read()


def test_mirror_serve_admits_fonts():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import mirror_serve as ms
    ok = ["index.html", "app-latest.json", "fonts/PretendardVariable.woff2",
          "ImmediatelyLaw-online-0.0.0.zip"]
    bad = ["a.exe", "../etc/passwd", "fonts/sub/x.woff2",  # 다단계 불허
           "fonts/shell.sh", ".hidden", "x.woff2/../y"]
    for p in ok:
        assert ms.SAFE.fullmatch(p), f"허용해야 할 경로: {p}"
    for p in bad:
        assert not ms.SAFE.fullmatch(p), f"차단해야 할 경로: {p}"
    h = ms.Handler
    assert h.guess_type(None, "a/b.woff2") == "font/woff2"
    assert h.guess_type(None, "a/b.woff") == "font/woff"
