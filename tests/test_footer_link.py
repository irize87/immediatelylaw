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


def test_article_url_opens_that_article_only():
    from urllib.parse import unquote
    from immediatelylaw.overlay import article_url
    assert unquote(article_url("민법", "75")) == \
        "https://www.law.go.kr/법령/민법/제75조"
    assert unquote(article_url("민법 시행령", "19")) == \
        "https://www.law.go.kr/법령/민법 시행령/제19조"
    assert unquote(article_url("형법", "247의2")) == \
        "https://www.law.go.kr/법령/형법/제247조의2"


def test_card_link_article_mode_keeps_decree_name(qtbot):
    from urllib.parse import unquote
    cfg = {"overlay_width": 520, "font_pt": 11, "theme": "light",
           "overlay_corner": "top-right", "auto_hide_sec": 0,
           "law_link_mode": "article"}
    card = OverlayCard(cfg)
    qtbot.addWidget(card)
    card._place_and_show = lambda: None
    res = {"found": True, "source": "local", "law_name": "민법 시행령",
           "art_no": "19", "title": "", "chap": "", "body": "본문",
           "pending": 0}
    card.show_results([res])
    assert unquote(card.footer.btn_site.property("url")) == \
        "https://www.law.go.kr/법령/민법 시행령/제19조"


def test_copy_drops_heading_already_in_body():
    from immediatelylaw.overlay import format_copy
    body = (
        "제15조(개인정보의 수집\u318d이용)\n"
        "① 개인정보처리자는 다음 각 호의 어느 하나에 해당하는 경우에는 "
        "개인정보를 수집할 수 있으며 그 수집 목적의 범위에서 이용할 수 있다."
    )
    text = format_copy([{
        "law_name": "개인정보 보호법", "art_no": "15",
        "title": "개인정보의 수집\u318d이용", "body": body,
    }])
    assert text.startswith("개인정보 보호법 제15조 (개인정보의 수집\u318d이용)\n① ")
    assert text.count("제15조") == 1


def test_copy_includes_citation_and_body():
    from immediatelylaw.overlay import format_copy
    text = format_copy([{
        "law_name": "민법", "art_no": "750", "title": "불법행위의 내용",
        "body": "고의 또는 과실로 인한 위법행위로 타인에게 손해를 가한 자는",
    }])
    assert text.startswith("민법 제750조 (불법행위의 내용)\n")
    assert "고의 또는 과실" in text


def test_long_title_does_not_cover_badge(qtbot):
    cfg = {"overlay_width": 470, "font_pt": 11, "theme": "light",
           "overlay_corner": "bottom_right", "auto_hide_sec": 0}
    card = OverlayCard(cfg)
    qtbot.addWidget(card)
    res = {"found": True, "source": "local",
           "law_name": "개인정보 보호법", "art_no": "15",
           "title": "개인정보의 수집·이용", "chap": "제1절",
           "body": "본문", "pending": 0}
    card.show_results([res])
    card.set_badge("neutral", "조회")
    qtbot.wait(30)
    title = card.lb_title.geometry()
    badge = card.lb_badge.geometry()
    close = card.btn_close.geometry()
    assert title.width() >= 48
    assert title.right() <= badge.left()
    assert badge.right() <= close.left()
    assert badge.width() >= card.lb_badge.sizeHint().width() - 2


def test_long_title_is_kept_for_marquee(qtbot):
    from immediatelylaw.overlay import MarqueeLabel
    w = MarqueeLabel()
    qtbot.addWidget(w)
    title = "산업안전보건법 시행규칙 제73조 (산업재해 발생 보고 등) 추가 설명"
    w.setFixedWidth(80)
    w.show()
    w.setText(title)
    assert w.text() == title
    assert w._timer.isActive()
    qtbot.wait(1500)
    assert w._offset > 0


def test_fixed_card_height(qtbot):
    cfg = {"overlay_width": 520, "overlay_height": 640, "font_pt": 11,
           "theme": "light", "overlay_corner": "bottom_right",
           "auto_hide_sec": 0}
    card = OverlayCard(cfg)
    qtbot.addWidget(card)
    card.apply_box()
    assert card.height() == card._configured_height()
    assert card.height() == min(640, card._screen_h() - 8)


def test_apply_button_saves_without_closing(qtbot, tmp_path):
    from immediatelylaw.db import Database
    from immediatelylaw.settingsdlg import SettingsDialog

    class Bag:
        def __init__(self):
            self.d = {
                "overlay_width": 470, "overlay_height": 0, "theme": "light",
                "font_pt": 11, "overlay_corner": "bottom_right",
                "auto_hide_sec": 30, "verify_enabled": True,
                "hotkey_enabled": True, "hotkey": "ctrl+alt+l",
                "clipboard_paused": False, "law_link_mode": "set",
                "update_check": True, "data_base_url": "", "autostart": True,
            }
            self.saves = 0

        def __getitem__(self, key):
            return self.d[key]

        def get(self, key, default=None):
            return self.d.get(key, default)

        def __setitem__(self, key, value):
            self.d[key] = value

        def save(self):
            self.saves += 1

        def masked_oc_key(self):
            return ""

    db = Database(str(tmp_path / "s.db"))
    cfg = Bag()
    try:
        dlg = SettingsDialog(cfg, db)
        qtbot.addWidget(dlg)
        dlg.sp_w.setValue(800)
        dlg.sp_h.setValue(500)
        dlg.cb_link.setCurrentIndex(dlg.cb_link.findData("article"))
        dlg.chk_pause.setChecked(True)
        dlg._apply_now()
        assert dlg.isVisible() is False
        assert cfg.saves == 1
        assert cfg.d["overlay_width"] == 800
        assert cfg.d["overlay_height"] == 500
        assert cfg.d["law_link_mode"] == "article"
        assert cfg.d["clipboard_paused"] is True
    finally:
        db.close()


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
