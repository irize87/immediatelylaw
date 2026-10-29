# -*- coding: utf-8 -*-
"""법령명·조번호 입력 조회 창."""
import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QTextBrowser,
                               QAbstractItemView, QVBoxLayout, QWidget)

from . import refparse, resolver, theme
from .overlay import FooterBar, article_html


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

        # 카드와 동일한 공용 하단바(글자크기 −/+ · 링크 · 복사)
        self.footer = FooterBar(self.cfg)
        self.footer.copy_clicked.connect(self._on_copy)
        self.footer.font_step.connect(self._on_font)
        self.lb_state = self.footer.lb_state
        self.footer.set_state("법령명과 조번호를 입력하세요. "
                              "Enter = 조회, 목록 클릭 = 조문 열기")
        root.addWidget(self.footer)

        self._badge = ("neutral", "")
        self._refresh_palette()

    # ---------- 테마 ----------
    def _refresh_palette(self):
        p = theme.palette(self.cfg)
        self.tv.setStyleSheet(
            f"QTextBrowser{{border:1px solid {p['border']};"
            f"border-radius:6px;background:{p['panel']};}}")
        self.footer.apply_palette(p)
        self._render()
        self._apply_badge()

        QShortcut(QKeySequence("Ctrl+F"), self,
                  activated=lambda: self.ed.setFocus())

    # ---------- 검색 ----------
    def do_search(self):
        q = refparse.parse_query(self.ed.text())
        if not q:
            return
        self._clear_transient()
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
        self._clear_transient()
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

    def _show_result(self, res, note=""):
        self._last_res = res
        src = res.get("source")
        self._push_history(res)
        self._render()
        if src == "local-reg":
            self._show_badge("neutral", "(자치)")
            self.footer.set_state("등록 자치법규")
        else:
            self._show_badge("neutral", "(조회)")
            self.footer.set_state(note)
            if self.cfg["verify_enabled"]:
                self._verify(res)

    # ---------- 조회 이력 ----------
    def _history_label(self, res):
        return (f"{res['law_name']} 제{res['art_no']}조"
                + (f"({res['title']})" if res.get("title") else "")
                + ("  [자치]" if res.get("source") == "local-reg" else ""))

    def _push_history(self, res):
        """본 조문 목록은 열람 이력. 동일 항목은 중복 추가하지 않고 맨 위로 이동."""
        it = None
        for i in range(self.list.count()):
            cand = self.list.item(i)
            d = cand.data(Qt.UserRole) or {}
            r = d.get("res") or {}
            if (d.get("kind") == "art_direct"
                    and r.get("law_name") == res["law_name"]
                    and str(r.get("art_no")) == str(res["art_no"])):
                # 최신 해석 데이터로 갱신 후 맨 위로 이동
                cand.setData(Qt.UserRole, {"kind": "art_direct", "res": res})
                self.list.takeItem(i)
                it = cand
                break
        if it is None:
            it = QListWidgetItem(self._history_label(res))
            it.setData(Qt.UserRole, {"kind": "art_direct", "res": res})
        self.list.insertItem(0, it)
        self.list.setCurrentItem(it)

    def _clear_transient(self):
        """검색결과·목차 같은 임시 항목만 지운다(열람 이력은 최상단 유지)."""
        for i in range(self.list.count() - 1, -1, -1):
            d = self.list.item(i).data(Qt.UserRole) or {}
            if d.get("kind") != "art_direct":
                self.list.takeItem(i)

    # ---------- 렌더 ----------
    def _render(self):
        """법령명(굵게) · 장·절(회색) · 본문 — 모두 같은 폰트·같은 크기."""
        res = self._last_res
        if not res:
            return
        try:
            pt = int(self.cfg["font_pt"])
        except (TypeError, ValueError):
            pt = 11
        pt = max(8, min(20, pt))
        p = theme.palette(self.cfg)
        head = self._history_label(res).replace("  [자치]", " [자치]")
        self.tv.setHtml(
            f'<div style="font-family:\'Malgun Gothic\';font-size:{pt}pt;'
            f'font-weight:bold;color:{p["fg"]};margin:0 2px 6px 2px;">'
            f'{html.escape(head)}</div>'
            + article_html(res, pt, p["dark"]))

    def _on_font(self, pt: int):
        self._render()

    def _verify(self, res):
        from .workers import VerifyWorker
        w = VerifyWorker(self.db, self.api_getter(), res)
        w.done.connect(self._on_verified)
        self._workers.append(w)
        w.start()

    def _on_verified(self, kind, msg):
        text = {"current": "(현행)", "check": "(확인)",
                "offline": "(오프라인)"}.get(kind, f"({kind})")
        self._show_badge(kind if kind in ("current", "check") else "neutral",
                         text)

    def _show_badge(self, kind, text):
        self._badge = (kind, text)
        self._apply_badge()

    def _apply_badge(self):
        kind, text = self._badge
        p = theme.palette(self.cfg)
        style = p.get(f"badge_{kind}") or p["badge_neutral"]
        self.lb_badge.setText(text)
        self.lb_badge.setStyleSheet(style + "padding:2px 6px;"
                                    "border-radius:4px;font-weight:bold;")

    def _on_copy(self):
        if self._last_res:
            self.copy_requested.emit(self._last_res["body"])
            self.footer.set_state("클립보드에 복사했습니다.")
