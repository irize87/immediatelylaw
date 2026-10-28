# -*- coding: utf-8 -*-
"""법령명·조번호 입력 조회 창."""
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QTextBrowser,
                               QAbstractItemView, QVBoxLayout, QWidget)

from . import refparse, resolver
from .overlay import article_html, BADGE_STYLE


class SearchWindow(QWidget):
    copy_requested = Signal(str)

    def __init__(self, db, api_getter, cfg, parent=None):
        super().__init__(parent)
        self.db = db
        self.api_getter = api_getter
        self.cfg = cfg
        self._last_res = None
        self._workers = []

        self.setWindowTitle("즉시로 법령 조회")
        self.resize(680, 560)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        bar = QHBoxLayout()
        self.ed = QLineEdit()
        self.ed.setPlaceholderText(
            "예: 형법 제23조   ·   개인정보 보호법 13   ·   「민법」 제750조")
        f = QFont("Malgun Gothic", 10)
        self.ed.setFont(f)
        self.ed.returnPressed.connect(self.do_search)
        bar.addWidget(self.ed, 1)
        self.lb_badge = QLabel("")
        bar.addWidget(self.lb_badge)
        root.addLayout(bar)

        self.list = QListWidget()
        self.list.setFont(QFont("Malgun Gothic", 9))
        self.list.setMaximumHeight(170)
        self.list.itemActivated.connect(self._on_pick)
        self.list.itemClicked.connect(self._on_pick)
        root.addWidget(self.list)

        self.tv = QTextBrowser()
        self.tv.setStyleSheet("QTextBrowser{border:1px solid #e3e6ea;"
                              "border-radius:6px;background:#fff;}")
        root.addWidget(self.tv, 1)

        foot = QHBoxLayout()
        self.lb_state = QLabel("법령명과 조번호를 입력하세요. "
                               "Enter = 조회, 목록 더블클릭 = 조문 열기")
        self.lb_state.setStyleSheet("color:#8a919c;font-size:9pt;")
        btn = QWidget(self)
        copyb = _CopyButton("조문 복사")
        copyb.clicked.connect(self._on_copy)
        foot.addWidget(self.lb_state, 1)
        foot.addWidget(copyb)
        root.addLayout(foot)

        QShortcut(QKeySequence("Ctrl+F"), self,
                  activated=lambda: self.ed.setFocus())

    # ---------- 검색 ----------
    def do_search(self):
        q = refparse.parse_query(self.ed.text())
        if not q:
            return
        self.list.clear()
        self._show_badge("neutral", "(조회)")
        if q["art"]:
            self._resolve(q["law"], q["art"])
            return
        rows = self.db.search_laws_by_name(q["law"], limit=40)
        for r in rows:
            it = QListWidgetItem(f"{r['name']}  [{r['cls'] or ''} "
                                 f"시행 {r['enforced'] or ''}]")
            it.setData(Qt.UserRole, {"kind": "law", "mst": r["mst"],
                                     "name": r["name"]})
            self.list.addItem(it)
        if not rows:
            self._toc_fallback_search(q["law"])

    def _toc_fallback_search(self, name):
        rows = self.db.conn.execute(
            "SELECT a.art_no, a.title, l.name FROM article a "
            "JOIN law l ON l.mst=a.mst WHERE l.pending=0 AND a.title LIKE ? "
            "ORDER BY l.name LIMIT 60", (f"%{name}%",)).fetchall()
        for r in rows:
            it = QListWidgetItem(f"{r['name']} 제{r['art_no']}조({r['title']})")
            it.setData(Qt.UserRole, {"kind": "art", "mst": None,
                                     "name": r["name"], "art": r["art_no"]})
            self.list.addItem(it)
        if not rows:
            self.tv.setHtml("<p style='color:#8a919c;padding:12px;'>일치하는 "
                            "법령·조제목이 없습니다. (예: <b>형법 제23조</b>)</p>")
            self.lb_state.setText("결과 없음")

    def _on_pick(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole) or {}
        if data.get("kind") == "law":
            self._show_toc(data["mst"], data["name"])
        elif data.get("kind") == "art":
            self._resolve(data["name"], data["art"])
        elif data.get("kind") == "art_direct":
            self._show_result(data["res"], note="")

    def _show_toc(self, mst, name):
        arts = self.db.conn.execute(
            "SELECT art_no, title FROM article WHERE mst=? ORDER BY ord",
            (mst,)).fetchall()
        self.list.clear()
        for a in arts:
            it = QListWidgetItem(f"제{a['art_no']}조 {a['title'] or ''}")
            it.setData(Qt.UserRole, {"kind": "art", "name": name,
                                     "art": a["art_no"]})
            self.list.addItem(it)
        self.lb_state.setText(f"{name} 목차 — 조문을 선택하세요")

    # ---------- 조문 해석/표시 ----------
    def _resolve(self, hint, art):
        res = resolver.resolve(self.db, hint, art, None)
        if res.get("found"):
            self._show_result(res)
            return
        api = self.api_getter()
        if api is None:
            self.tv.setHtml(
                f"<p style='color:#8a919c;padding:12px;'>"
                f"<b>{hint} 제{art}조</b>를 로컬 데이터에서 찾지 못했습니다.<br>"
                f"· 등재된 법령명이 정확한지 확인하세요.<br>"
                f"· API 키를 등록하면 미등재 법령도 바로 가져올 수 있습니다."
                f"</p>")
            self.lb_state.setText("로컬 데이터에 없음")
            self._show_badge("check", "(확인)")
            return
        self.lb_state.setText("법제처에서 가져오는 중…")
        from .workers import ResolveWorker
        w = ResolveWorker(self.db, api, hint, art)
        w.done.connect(self._on_live)
        self._workers.append(w)
        w.start()

    def _on_live(self, res):
        if res.get("found"):
            self._show_result(res)
        else:
            self.tv.setHtml("<p style='color:#b45309;padding:12px;'>"
                            "법제처에서도 찾지 못했습니다.</p>")
            self._show_badge("check", "(확인)")

    def _show_result(self, res, note="검증 중…"):
        self._last_res = res
        src = res.get("source")
        one = QListWidgetItem(
            f"{res['law_name']} 제{res['art_no']}조"
            + (f"({res['title']})" if res.get('title') else "")
            + ("  [자치]" if src == "local-reg" else ""))
        one.setData(Qt.UserRole, {"kind": "art_direct", "res": res})
        self.list.insertItem(0, one)
        head = f"<h3 style='margin:6px 4px 2px 4px;'>{res['law_name']} " \
               f"제{res['art_no']}조" + (f"({res['title']})" if res.get('title') else "") \
               + ("" if src != "local-reg" else " [자치]") + "</h3>"
        self.tv.setHtml(head + article_html(res))
        if src == "local-reg":
            self._show_badge("neutral", "(자치)")
            self.lb_state.setText("등록 자치법규")
        else:
            self._show_badge("neutral", "(조회)")
            self.lb_state.setText(note)
            if self.cfg["verify_enabled"]:
                self._verify(res)

    def _verify(self, res):
        from .workers import VerifyWorker
        w = VerifyWorker(self.db, self.api_getter(), res)
        w.done.connect(self._on_verified)
        self._workers.append(w)
        w.start()

    def _on_verified(self, kind, msg):
        text = {"current": "(현행)", "check": "(확인)",
                "offline": "(오프라인)"}.get(kind, f"({kind})")
        self._show_badge(kind if kind in BADGE_STYLE else "neutral", text)
        self.lb_state.setText(msg)

    def _show_badge(self, kind, text):
        style = BADGE_STYLE.get(kind, BADGE_STYLE["neutral"])[0]
        self.lb_badge.setText(text)
        self.lb_badge.setStyleSheet(style + "padding:2px 6px;"
                                    "border-radius:4px;font-weight:bold;")

    def _on_copy(self):
        if self._last_res:
            self.copy_requested.emit(self._last_res["body"])
            self.lb_state.setText("클립보드에 복사했습니다.")


class _CopyButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton{border:1px solid #c6cbd2;border-radius:5px;"
            "padding:5px 12px;background:#f7f8fa;font-size:9pt;}"
            "QPushButton:hover{background:#eef2f8;border-color:#9db6d9;}")
