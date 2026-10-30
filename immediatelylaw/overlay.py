# -*- coding: utf-8 -*-
"""화면 한켠에 뜨는 담백한 조문 카드."""
import html
import re
import time

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QIcon, QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QPushButton, QTextBrowser,
                               QVBoxLayout, QWidget)

from . import theme
from .refparse import base_name

CIRCLED = "\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469" \
          "\u246a\u246b\u246c\u246d\u246e\u246f\u2470\u2471\u2472\u2473"

BADGE_TEXT = {
    "current": "현행", "check": "확인", "neutral": "로컬",
}


class FooterBar(QWidget):
    """카드·조회창 공용 하단바: 글자크기 −/+(둥근 그룹) · 상태문구 · 링크 ·
    복사(둥근 버튼). 테마 팔레트로 색을 입힌다."""
    copy_clicked = Signal()
    font_step = Signal(int)   # 새 pt (config에 저장 완료된 값)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 0)
        lay.setSpacing(10)

        # − / + 를 둥근 테두리 하나의 그룹으로 묶는다.
        self.grp = QFrame(self)
        self.grp.setObjectName("fontGroup")
        gl = QHBoxLayout(self.grp)
        gl.setContentsMargins(3, 2, 3, 2)
        gl.setSpacing(2)
        self.btn_font_dec = self._btn("−", "글자 작게 (장·절·본문)")
        self.btn_font_inc = self._btn("+", "글자 크게 (장·절·본문)")
        self.btn_font_dec.clicked.connect(lambda: self._step(-1))
        self.btn_font_inc.clicked.connect(lambda: self._step(1))
        gl.addWidget(self.btn_font_dec)
        gl.addWidget(self.btn_font_inc)

        self.lb_state = QLabel("")
        self.lb_state.setFont(QFont("Malgun Gothic", 8))
        self.btn_site = self._link(
            "https://www.law.go.kr/", "법령정보센터 ↗",
            "국가법령정보센터(www.law.go.kr) 열기")
        self.btn_author = self._link(
            "https://github.com/nazgregory", "제작자 ↗",
            "제작자 GitHub 페이지 열기")
        self.btn_copy = QPushButton("  복사  ")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setFocusPolicy(Qt.NoFocus)
        self.btn_copy.setIconSize(QSize(15, 15))
        self.btn_copy.clicked.connect(self.copy_clicked)
        for w in (self.grp, self.lb_state):
            lay.addWidget(w)
        lay.addStretch(1)
        for w in (self.btn_site, self.btn_author, self.btn_copy):
            lay.addWidget(w)

    @staticmethod
    def _copy_icon(color: str) -> QIcon:
        """두 장 겹친 문서 모양의 복사 아이콘을 그려 쓴다."""
        pm = QPixmap(16, 16)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(1.4)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(1.6, 4.6, 8, 8, 2.2, 2.2)
        p.drawRoundedRect(5.0, 1.4, 8, 8, 2.2, 2.2)
        p.end()
        return QIcon(pm)

    def apply_palette(self, p: dict):
        """테마 팔레트(theme.LIGHT/DARK)를 버튼·링크·상태 문구에 적용."""
        self.lb_state.setStyleSheet(f"color:{p['fg2']};")
        self.grp.setStyleSheet(
            "#fontGroup{background:transparent;"
            f"border:1px solid {p['border']};border-radius:11px;}}")
        bss = (
            f"QPushButton{{border:none;background:transparent;color:{p['fg']};"
            f"font-family:'Malgun Gothic';font-size:11pt;font-weight:bold;}}"
            f"QPushButton:hover{{background:{p['hover']};border-radius:8px;}}")
        self.btn_font_dec.setStyleSheet(bss)
        self.btn_font_inc.setStyleSheet(bss)
        self.btn_copy.setStyleSheet(
            f"QPushButton{{border:none;border-radius:11px;"
            f"background:{p.get('copy_bg', p['hover'])};color:{p['fg']};"
            f"font-family:'Malgun Gothic';font-size:10pt;padding:6px 14px;}}"
            f"QPushButton:hover{{background:{p['hover']};}}")
        self.btn_copy.setIcon(self._copy_icon(p["fg"]))
        for lb in (self.btn_site, self.btn_author):
            lb.setText(
                "<a href='" + str(lb.property('url')) + "' style='color:"
                + p['link'] + ";text-decoration:none'>"
                + str(lb.property('label')) + "</a>")

    def set_state(self, text: str):
        self.lb_state.setText(text)

    def _step(self, delta: int):
        try:
            cur = int(self.cfg["font_pt"])
        except (TypeError, ValueError):
            cur = 11
        pt = max(8, min(20, cur + delta))
        if pt == cur:
            return
        self.cfg["font_pt"] = pt
        self.cfg.save()           # 사용자가 조정하면 설정에 저장되어 유지
        self.font_step.emit(pt)

    def _link(self, url: str, label: str, tip: str) -> QLabel:
        lb = QLabel(f"<a href='{url}' style='text-decoration:none'>"
                    f"{label}</a>")
        lb.setProperty("url", url)
        lb.setProperty("label", label)
        lb.setFont(QFont("Malgun Gothic", 9))
        lb.setCursor(Qt.PointingHandCursor)
        lb.setToolTip(tip)
        lb.setOpenExternalLinks(True)
        return lb

    def _btn(self, text: str, tip: str) -> QPushButton:
        b = QPushButton(text)
        b.setFixedSize(30, 26)
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)   # 본체(Esc) 포커스 유지
        b.setToolTip(tip)
        return b


# 개정 이력 표기: <개정 2009.12.29>, <2013.8.6>, [전문개정 2010.6.8] 등
_HIST_RAW_RE = re.compile(
    r"<(?:(?:개정|추가|삭제|휴면|제명개정|시행|폐지|복구|실효|신설|강화"
    r"|전문개정|일부개정|조문번호변경|본문개정|이전제|단서개정)[^<]*"
    r"|[0-9]{4}\.[0-9.,\s]*)>"
    r"|\[(?:전문개정|제정|일부개정|법률제[0-9-]+|시행)[^\]]*\]")


def article_html(res: dict, pt: float = 11, dark: bool = False) -> str:
    """장·절 표기와 본문이 같은 폰트(맑은 고딕)·같은 크기로 렌더된다."""
    fg = "#e8eaed" if dark else "#20242b"
    fg2 = "#9aa3ad" if dark else "#5b6470"
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
    # 개정 이력 표기(<개정 …>, [전문개정 …] 등)는 본문 단락에서 떼어
    # 단락 바로 아래 작고 옅은 줄로 배치한다(본문이 먼저 보이게).
    hpt = max(pt - 2, 8)
    hstyle = ("font-family:'Malgun Gothic';font-size:%gpt;line-height:1.5;"
              % hpt)
    parts = []
    for p in paras:
        ml = "0"   # 호/목 들여쓰기로 계층을 시각화
        if re.match(r"^\d+(?:의\d+)?[．.]", p):
            ml = "14px"
        elif re.match(r"^[가-하][．.]", p):
            ml = "28px"
        marks = _HIST_RAW_RE.findall(p)
        p_text = _HIST_RAW_RE.sub("", p).strip() if marks else p
        if p_text:
            parts.append(f'<p style="margin:4px 0 4px {ml};{style}'
                         f'color:{fg};">{html.escape(p_text)}</p>')
        if marks:
            line = "  ".join(m.strip() for m in marks)
            parts.append(f'<p style="margin:0 0 4px {ml};{hstyle}'
                         f'color:{fg2};">{html.escape(line)}</p>')
    inner = "".join(parts)
    chap = res.get("chap")
    chap_html = (f'<div style="{style}color:{fg2};margin-bottom:4px;">'
                 f'{html.escape(chap)}</div>') if chap else ""
    # 주의: style 특성 안에 이중따옴표 금지(파싱 깨짐). 폰트도 강제로 지정.
    return chap_html + inner


def section_head(res: dict, pt: float, dark: bool) -> str:
    """조문 구간 머리: 법령명 제N조(제목) — 굵게."""
    fg = "#e8eaed" if dark else "#20242b"
    style = ("font-family:'Malgun Gothic';font-size:%gpt;line-height:1.62;"
             % pt)
    head = f"{res['law_name']} 제{res['art_no']}조"
    if res.get("title"):
        head += f"({res['title']})"
    if res.get("source") == "local-reg":
        head += "  [자치]"
    return (f'<div style="{style}font-weight:bold;color:{fg};'
            f'margin:0 0 2px 0;">{html.escape(head)}</div>')


def articles_html_multi(res_list, pt: float = 11, dark: bool = False) -> str:
    """법+시행령 등 여러 조문을 이어서 표시 — 구간마다 법령명 헤더와
    구분선(테마 색)으로 시각적 분리. 한 개면 기존 렌더와 동일."""
    if not res_list:
        return ""
    if len(res_list) == 1:
        return article_html(res_list[0], pt, dark)
    bd = "#39414b" if dark else "#d7dbe0"
    parts = []
    for i, res in enumerate(res_list):
        if i:
            parts.append(f'<div style="border-top:1px solid {bd};'
                         f'margin:13px 0 9px 0;"></div>')
        parts.append(section_head(res, pt, dark))
        parts.append(article_html(res, pt, dark))
    return "".join(parts)


class OverlayCard(QWidget):
    copy_requested = Signal(str)
    verify_requested = Signal(dict)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._drag = None
        self._current = None
        self._current_list = None
        self._hide_timer = QTimer(self, singleShot=True)
        self._hide_timer.timeout.connect(self.hide)

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setObjectName("cardRoot")
        # 둥근 카드 본문 + 그림자용 여백(카드 본문 폭은 설정값 그대로)
        self.MARGIN = 14
        self.setFixedWidth(int(cfg["overlay_width"]) + self.MARGIN * 2)

        root = QVBoxLayout(self)
        root.setContentsMargins(self.MARGIN, self.MARGIN - 2,
                                self.MARGIN, self.MARGIN + 6)
        root.setSpacing(0)
        # 앱 전역 다크 QSS(QWidget 배경)로부터 창 자체는 투명 유지
        self.setStyleSheet("#cardRoot{background:transparent;}")

        self.body = QFrame(self)
        self.body.setObjectName("cardBody")
        root.addWidget(self.body)
        shadow = QGraphicsDropShadowEffect(self.body)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(30, 41, 59, 70))
        self.body.setGraphicsEffect(shadow)
        self._shadow = shadow

        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        top = QHBoxLayout(); top.setSpacing(8)
        self.lb_title = QLabel("")
        f = QFont("Malgun Gothic", 11); f.setBold(True)
        self.lb_title.setFont(f)
        self.lb_title.setStyleSheet("color:#20242b;")
        self.lb_badge = QLabel("")
        bf = QFont("Malgun Gothic", 9); bf.setBold(True)
        self.lb_badge.setFont(bf)
        top.addWidget(self.lb_title)
        top.addWidget(self.lb_badge)      # 제목 바로 뒤 알약 배지
        top.addStretch(1)
        # (현행) 배지 옆 닫기 버튼
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFocusPolicy(Qt.NoFocus)   # 카드(Esc) 포커스 유지
        self.btn_close.setToolTip("창 닫기 (Esc 두 번)")
        self.btn_close.clicked.connect(self.hide)
        top.addWidget(self.btn_close)
        lay.addLayout(top)

        self.tv = QTextBrowser(self.body)
        self.tv.setOpenExternalLinks(False)
        self.tv.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tv.setStyleSheet(
            "QTextBrowser{border:none;background:transparent;}")
        self.tv.setMinimumHeight(60)
        self.tv.setMaximumHeight(int(self._screen_h() * 0.5))
        lay.addWidget(self.tv)

        # 본문과 하단바를 가늘게 가르는 구분선(카드 끝까지 전폭)
        self.line = QFrame(self.body)
        self.line.setFixedHeight(1)
        line_l = QHBoxLayout()
        line_l.setContentsMargins(-16, 0, -16, 0)
        line_l.addWidget(self.line)
        lay.addLayout(line_l)

        # 공용 하단바: 글자크기 −/+ · 상태 · 법령정보센터/제작자 링크 · 복사
        self.footer = FooterBar(self.cfg)
        self.footer.copy_clicked.connect(self._on_copy)
        self.footer.font_step.connect(self._change_font)
        self.lb_state = self.footer.lb_state   # Esc 안내/복사 문구용 별칭
        lay.addWidget(self.footer)

        self._badge = ("neutral", "")
        self._refresh_palette()

    # ---------- 테마 ----------
    def _refresh_palette(self):
        p = theme.palette(self.cfg)
        self.body.setStyleSheet(
            f"#cardBody{{background:{p['bg']};border:1px solid {p['border']};"
            f"border-radius:16px;}}")
        self.line.setStyleSheet(
            f"QFrame{{background:{p['border']};border:none;}}")
        handle = "#4a525e" if p["dark"] else "#d3d8df"
        self.tv.setStyleSheet(
            "QTextBrowser{border:none;background:transparent;}"
            "QScrollBar:vertical{background:transparent;width:8px;"
            "margin:2px 2px 2px 0;}"
            f"QScrollBar::handle:vertical{{background:{handle};"
            "border-radius:3px;min-height:32px;}}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical"
            "{height:0;background:none;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical"
            "{background:none;}")
        self._shadow.setColor(
            QColor(0, 0, 0, 110) if p["dark"] else QColor(30, 41, 59, 70))
        self.lb_title.setStyleSheet(f"color:{p['fg']};")
        self.btn_close.setStyleSheet(
            f"QPushButton{{border:none;border-radius:7px;"
            f"background:transparent;color:{p['fg2']};"
            f"font-family:'Malgun Gothic';font-size:10pt;}}"
            f"QPushButton:hover{{background:{p['hover']};color:{p['fg']};}}")
        self.footer.apply_palette(p)
        if self._current_list:
            self.tv.setHtml(articles_html_multi(
                self._current_list, self._pt(), p["dark"]))
        self._apply_badge()

    def _apply_badge(self):
        kind, text = self._badge
        p = theme.palette(self.cfg)
        style = p.get(f"badge_{kind}") or p["badge_neutral"]
        self.lb_badge.setText(text)
        # 알약(pill) 모양 배지
        self.lb_badge.setStyleSheet(style + "padding:3px 10px;"
                                    "border-radius:11px;"
                                    "font-family:'Malgun Gothic';")

    @staticmethod
    def _screen_h():
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen()
        return scr.availableGeometry().height() if scr else 1080

    # ---------- 표시 ----------
    def show_result(self, res: dict, note: str = ""):
        self.show_results([res], note)

    def show_results(self, res_list, note: str = ""):
        """조문 1건 또는 여러 건(법+시행령 등)을 이어서 표시."""
        res = res_list[0]
        self._current = res
        self._current_list = list(res_list)
        self._esc_at = 0.0
        self.lb_title.setText(self._combined_title(res_list))
        src = res.get("source")
        if src == "local-reg":
            self.set_badge("neutral", "자치")
        elif res.get("pending"):
            self.set_badge("check", "시행예정")
        else:
            self.set_badge("neutral", "조회")
        self.tv.setHtml(articles_html_multi(
            res_list, self._pt(), theme.palette(self.cfg)["dark"]))
        self.lb_state.setText(note)
        self._place_and_show()
        if res.get("source") != "local-reg":
            self.verify_requested.emit(res)

    def _combined_title(self, res_list) -> str:
        def head1(res):
            h = f"{res['law_name']} 제{res['art_no']}조"
            if res.get("title"):
                h += f"({res['title']})"
            if res.get("source") == "local-reg":
                h += "  [자치]"
            return h
        if len(res_list) <= 1:
            return head1(res_list[0])
        b0 = base_name(res_list[0]["law_name"])
        names = [head1(res_list[0])]
        for res in res_list[1:]:
            nm = res["law_name"]
            if base_name(nm) == b0:
                nm = "같은 법 " + nm[len(b0):].strip()
            names.append(f"{nm} 제{res['art_no']}조")
        return "  ·  ".join(names)

    # ---------- 글자크기 ----------
    def _pt(self) -> int:
        try:
            return max(8, min(20, int(self.cfg["font_pt"])))
        except (TypeError, ValueError):
            return 11

    def _change_font(self, pt: int):
        """FooterBar(font_step) 수신: 현재 결과를 새 크기로 다시 렌더."""
        if self._current_list:
            self.tv.setHtml(articles_html_multi(
                self._current_list, pt, theme.palette(self.cfg)["dark"]))
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
        self._badge = (kind, text or BADGE_TEXT.get(kind, ""))
        self._apply_badge()

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
        ml, mt, mr, mb = self.MARGIN, self.MARGIN - 2, self.MARGIN, \
            self.MARGIN + 6
        # 투명 여백(MARGIN)을 뺀 '보이는 카드' 기준으로 화면 가장자리 정렬
        x = scr.right() - self.width() + mr - m if "right" in corner \
            else scr.left() + m - ml
        y = scr.top() + m - mt if corner.startswith("top") \
            else scr.bottom() - h + mb - m
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
            gp = None
            try:
                gp = ev.globalPosition().toPoint()
            except (AttributeError, TypeError):
                try:
                    gp = ev.globalPos()
                except AttributeError:
                    pass
            if gp is not None:
                tl = self.mapToGlobal(QPoint(self.body.x(), self.body.y()))
                g = QRect(tl, self.body.size())   # 그림자 여백 제외한 본문
                if not g.contains(gp):
                    self.hide()
        return False

    # ---------- 동작 ----------
    def _on_copy(self):
        lst = self._current_list or ([self._current] if self._current else [])
        if not lst:
            return
        if len(lst) == 1:
            text = lst[0]["body"]
        else:
            blocks = []
            for res in lst:
                head = f"{res['law_name']} 제{res['art_no']}조"
                if res.get("title"):
                    head += f"({res['title']})"
                blocks.append(f"{head}\n{res['body']}")
            text = "\n\n".join(blocks)
        self.copy_requested.emit(text)
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
