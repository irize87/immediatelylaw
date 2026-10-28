# -*- coding: utf-8 -*-
"""화면 한켠에 뜨는 담백한 조문 카드."""
import html
import re
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QTextBrowser,
                               QVBoxLayout, QWidget)

CIRCLED = "\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469" \
          "\u246a\u246b\u246c\u246d\u246e\u246f\u2470\u2471\u2472\u2473"

BADGE_STYLE = {
    "current": ("color:#1a7f37;background:#e3f5e9;", ""),
    "check":   ("color:#b45309;background:#fdf0d9;", ""),
    "neutral": ("color:#5b6470;background:#eef0f3;", ""),
}
BADGE_TEXT = {
    "current": "(현행)", "check": "(확인)", "neutral": "(로컬)",
}


def article_html(res: dict, pt: float = 11) -> str:
    """장·절 표기와 본문이 같은 폰트(맑은 고딕)·같은 크기로 렌더된다."""
    body = res.get("body", "")
    # 헤더에 이미 나오는 '제N조(제목)' 접두만 본문에서 제거
    body = re.sub(r"^\s*제\s*[0-9]+(?:의[0-9]+)?\s*조\s*[（(][^）)]*[）)]\s*",
                  "", body, count=1)
    body = re.sub(r"^\s*제\s*[0-9]+(?:의[0-9]+)?\s*조\s*", "", body, count=1)
    # ①②… 또는 줄바꿈 기준으로 단락 분리
    paras = [p.strip() for p in
             re.split(r"(?=[%s])|\n" % CIRCLED, body) if p.strip()]
    if not paras:
        paras = [body.strip()]
    style = ("font-family:'Malgun Gothic';font-size:%gpt;line-height:1.62;"
             % pt)
    inner = "".join(
        f'<p style="margin:4px 0 4px 0;{style}color:#20242b;">'
        f'{html.escape(p)}</p>' for p in paras)
    chap = res.get("chap")
    chap_html = (f'<div style="{style}color:#5b6470;margin-bottom:4px;">'
                 f'{html.escape(chap)}</div>') if chap else ""
    # 주의: style 특성 안에 이중따옴표 금지(파싱 깨짐). 폰트도 강제로 지정.
    return chap_html + inner


class OverlayCard(QWidget):
    copy_requested = Signal(str)
    verify_requested = Signal(dict)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._drag = None
        self._current = None
        self._hide_timer = QTimer(self, singleShot=True)
        self._hide_timer.timeout.connect(self.hide)

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setObjectName("cardRoot")
        w = int(cfg["overlay_width"])
        self.setFixedWidth(w)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(6)
        # objectName 스코프: 자식 캐스케이드(원치 않는 테두리) 방지.
        # 색을 명시하지 않으면 시스템 다크테마 기본 글자색과 충돌한다.
        self.setStyleSheet(
            "#cardRoot{background:#ffffff;border:1px solid #d7dbe0;}")

        top = QHBoxLayout(); top.setSpacing(8)
        self.lb_title = QLabel("")
        f = QFont("Malgun Gothic", 11); f.setBold(True)
        self.lb_title.setFont(f)
        self.lb_title.setStyleSheet("color:#20242b;")
        self.lb_badge = QLabel("")
        bf = QFont("Malgun Gothic", 9); bf.setBold(True)
        self.lb_badge.setFont(bf)
        top.addWidget(self.lb_title)
        top.addStretch(1)
        top.addWidget(self.lb_badge)
        # (현행) 배지 옆 닫기 버튼
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFocusPolicy(Qt.NoFocus)   # 카드(Esc) 포커스 유지
        self.btn_close.setToolTip("창 닫기 (Esc 두 번)")
        self.btn_close.setStyleSheet(
            "QPushButton{border:none;border-radius:5px;background:transparent;"
            "color:#8a919c;font-family:'Malgun Gothic';font-size:10pt;}"
            "QPushButton:hover{background:#f0f2f5;color:#3a3f46;}"
            "QPushButton:pressed{background:#e2e5e9;}")
        self.btn_close.clicked.connect(self.hide)
        top.addWidget(self.btn_close)
        root.addLayout(top)

        self.tv = QTextBrowser(self)
        self.tv.setOpenExternalLinks(False)
        self.tv.setStyleSheet(
            "QTextBrowser{border:none;background:transparent;}")
        self.tv.setMinimumHeight(60)
        self.tv.setMaximumHeight(int(self._screen_h() * 0.5))
        root.addWidget(self.tv)

        foot = QHBoxLayout(); foot.setSpacing(8)
        # 장·절·본문 글자크기 조절 버튼(둥근네모). 값은 설정에 저장되어 유지된다.
        self.btn_font_dec = self._font_btn("−", "글자 작게 (장·절·본문)")
        self.btn_font_inc = self._font_btn("+", "글자 크게 (장·절·본문)")
        self.btn_font_dec.clicked.connect(lambda: self._change_font(-1))
        self.btn_font_inc.clicked.connect(lambda: self._change_font(1))
        self.lb_state = QLabel("")
        sf = QFont("Malgun Gothic", 8)
        self.lb_state.setFont(sf)
        self.lb_state.setStyleSheet("color:#8a919c;")
        self.btn_copy = QPushButton("  복사  ")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet(
            "QPushButton{border:1px solid #c6cbd2;border-radius:5px;"
            "padding:4px 10px;background:#f7f8fa;color:#2a2f36;"
            "font-family:'Malgun Gothic';font-size:9pt;}"
            "QPushButton:hover{background:#eef2f8;border-color:#9db6d9;}"
            "QPushButton:pressed{background:#e2e9f4;}")
        self.btn_copy.clicked.connect(self._on_copy)
        foot.addWidget(self.btn_font_dec)
        foot.addWidget(self.btn_font_inc)
        foot.addWidget(self.lb_state)
        foot.addStretch(1)
        # 법령정보센터 바로 이동 링크
        self.btn_site = QLabel("<a href='https://www.law.go.kr/'>법령정보센터 ↗</a>")
        self.btn_site.setFont(QFont("Malgun Gothic", 8))
        self.btn_site.setCursor(Qt.PointingHandCursor)
        self.btn_site.setToolTip("국가법령정보센터(www.law.go.kr) 열기")
        self.btn_site.linkActivated.connect(self._open_site)
        foot.addWidget(self.btn_site)
        # 제작자 링크(깃허브 페이지)
        self.btn_author = QLabel(
            "<a href='https://github.com/nazgregory'>제작자 ↗</a>")
        self.btn_author.setFont(QFont("Malgun Gothic", 8))
        self.btn_author.setCursor(Qt.PointingHandCursor)
        self.btn_author.setToolTip("제작자 GitHub 페이지 열기")
        foot.addWidget(self.btn_author)
        foot.addWidget(self.btn_copy)
        root.addLayout(foot)

    def _font_btn(self, text: str, tip: str) -> QPushButton:
        b = QPushButton(text)
        b.setFixedSize(24, 24)
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)   # 카드(Esc) 포커스 유지
        b.setToolTip(tip)
        b.setStyleSheet(
            "QPushButton{border:1px solid #c6cbd2;border-radius:7px;"
            "background:#f7f8fa;color:#4a5058;"
            "font-family:'Malgun Gothic';font-size:11pt;font-weight:bold;}"
            "QPushButton:hover{background:#eef2f8;border-color:#9db6d9;}"
            "QPushButton:pressed{background:#e2e9f4;}")
        return b

    @staticmethod
    def _open_site():
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl("https://www.law.go.kr/"))

    @staticmethod
    def _screen_h():
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen()
        return scr.availableGeometry().height() if scr else 1080

    # ---------- 표시 ----------
    def show_result(self, res: dict, note: str = ""):
        self._current = res
        self._esc_at = 0.0
        head = f"{res['law_name']} 제{res['art_no']}조"
        if res.get("title"):
            head += f"({res['title']})"
        if res.get("source") == "local-reg":
            head += "  [자치]"
        self.lb_title.setText(head)
        src = res.get("source")
        if src == "local-reg":
            self.set_badge("neutral", "(자치)")
        elif res.get("pending"):
            self.set_badge("check", "(시행예정)")
        else:
            self.set_badge("neutral", "(조회)")
        self.tv.setHtml(article_html(res, self._pt()))
        self.lb_state.setText(note)
        self._place_and_show()
        if res.get("source") != "local-reg":
            self.verify_requested.emit(res)

    # ---------- 글자크기 ----------
    def _pt(self) -> int:
        try:
            return max(8, min(20, int(self.cfg["font_pt"])))
        except (TypeError, ValueError):
            return 11

    def _change_font(self, delta: int):
        pt = max(8, min(20, self._pt() + delta))
        if pt == self._pt():
            return
        self.cfg["font_pt"] = pt
        self.cfg.save()               # 사용자가 조정하면 설정에 저장되어 유지
        if self._current:
            self.tv.setHtml(article_html(self._current, pt))
        self._reflow()

    def _reflow(self):
        """글자크기 변경 후 높이를 다시 맞추되 밑변(위쪽 고정 모서리는 윗변)을 유지."""
        self.adjustSize()
        h = min(self.sizeHint().height() + 20,
                int(self._screen_h() * 0.72))
        bottom = self.y() + self.height()
        self.setFixedHeight(h)
        if not str(self.cfg["overlay_corner"]).startswith("top"):
            self.move(self.x(), bottom - h)

    def set_badge(self, kind: str, text: str = ""):
        style = BADGE_STYLE.get(kind, BADGE_STYLE["neutral"])[0]
        self.lb_badge.setText(text or BADGE_TEXT.get(kind, ""))
        self.lb_badge.setStyleSheet(style + "padding:2px 6px;border-radius:4px;")

    def set_state(self, text: str):
        self.lb_state.setText(text)

    def _place_and_show(self):
        self.adjustSize()
        h = min(self.sizeHint().height() + 20,
                int(self._screen_h() * 0.72))
        self.setFixedHeight(h)
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen().availableGeometry()
        corner = self.cfg["overlay_corner"]
        m = 14
        x = scr.right() - self.width() - m if "right" in corner \
            else scr.left() + m
        y = scr.top() + m if corner.startswith("top") \
            else scr.bottom() - h - m
        self.move(x, y)
        self.show(); self.raise_(); self.activateWindow()
        self._restart_hide()

    def _restart_hide(self):
        sec = int(self.cfg["auto_hide_sec"] or 0)
        if sec > 0:
            self._hide_timer.start(sec * 1000)

    def enterEvent(self, e):
        self._hide_timer.stop()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._restart_hide()
        super().leaveEvent(e)

    # 카드 바깥을 클릭하면 사라진다(전역 마우스 필터).
    def showEvent(self, e):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None and not getattr(self, "_filter_on", False):
            app.installEventFilter(self)
            self._filter_on = True
        super().showEvent(e)

    def hideEvent(self, e):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None and getattr(self, "_filter_on", False):
            app.removeEventFilter(self)
            self._filter_on = False
        super().hideEvent(e)

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.MouseButtonPress and self.isVisible():
            gp = getattr(ev, "globalPosition", None)
            if gp is not None:
                pt = gp.toPoint()
                g = self.frameGeometry()
                if not g.contains(pt):
                    self.hide()
        return False

    # ---------- 동작 ----------
    def _on_copy(self):
        if self._current:
            self.copy_requested.emit(self._current["body"])
            self.lb_state.setText("클립보드에 복사했습니다.")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Q:
            self.hide()
        elif e.key() == Qt.Key_Escape:
            # 2초 안에 두 번 눌러야 닫힌다(실수 닫기 방지).
            now = time.monotonic()
            if now - getattr(self, "_esc_at", 0.0) <= 2.0:
                self._esc_at = 0.0
                self.hide()
            else:
                self._esc_at = now
                self._state_saved = self.lb_state.text()
                self.lb_state.setText("닫으려면 Esc를 한 번 더 누르세요")
                QTimer.singleShot(2100, self._esc_hint_off)
        else:
            super().keyPressEvent(e)

    def _esc_hint_off(self):
        if time.monotonic() - getattr(self, "_esc_at", 0.0) > 2.0:
            self._esc_at = 0.0
            if self.isVisible():
                self.lb_state.setText(getattr(self, "_state_saved", ""))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = None
