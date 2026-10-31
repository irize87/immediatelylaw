# -*- coding: utf-8 -*-
"""법령정보센터 링크 회귀 테스트.

요구 동작: 라벨은 항상 '법령정보센터', 주소는 lsSc.do?query=본법 —
시행령·시행규칙이 표시 중이어도 본법 쿼리여야 이동 후 사이드메뉴에
법+시행령+시행규칙 패널이 모두 열린다."""
from urllib.parse import parse_qs, urlparse

from immediatelylaw.overlay import FooterBar, OverlayCard


def _q(url):
    return parse_qs(urlparse(url).query).get("query", [""])[0]


def test_center_url_strips_decree_suffix():
    url = FooterBar.center_url("개인정보 보호법 시행령")
    assert url.startswith("https://www.law.go.kr/lsSc.do?query=")
    assert _q(url) == "개인정보 보호법"
    url2 = FooterBar.center_url("개인정보 보호법 시행규칙")
    assert _q(url2) == "개인정보 보호법"


def test_center_url_keeps_base_law():
    assert _q(FooterBar.center_url("민법")) == "민법"


def test_card_link_uses_base_law_query(qtbot):
    cfg = {"overlay_width": 520, "font_pt": 11, "theme": "light",
           "overlay_corner": "top-right", "auto_hide_sec": 0}
    card = OverlayCard(cfg)
    qtbot.addWidget(card)
    card._place_and_show = lambda: None
    res = {"found": True, "source": "local", "law_name": "개인정보 보호법 시행령",
           "art_no": "31", "title": "", "chap": "", "body": "본문",
           "pending": 0}
    card.show_results([res])
    lb = card.footer.btn_site
    assert not lb.isHidden()
    assert "법령정보센터" in lb.text()
    assert _q(lb.property("url")) == "개인정보 보호법"


def test_card_link_hidden_for_local_reg(qtbot):
    cfg = {"overlay_width": 520, "font_pt": 11, "theme": "light",
           "overlay_corner": "top-right", "auto_hide_sec": 0}
    card = OverlayCard(cfg)
    qtbot.addWidget(card)
    card._place_and_show = lambda: None
    res = {"found": True, "source": "local-reg", "law_name": "서초구 규칙",
           "art_no": "1", "title": "", "chap": "", "body": "본문",
           "pending": 0}
    card.show_results([res])
    assert card.footer.btn_site.isHidden()
