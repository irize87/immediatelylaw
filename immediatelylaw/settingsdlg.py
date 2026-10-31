# -*- coding: utf-8 -*-
"""설정 창: 데이터 / 자치법규 / API 키 / 오버레이 / 일반 / 정보."""
import os
import shutil
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSpinBox, QTabWidget, QTableWidget,
                               QTableWidgetItem, QTextEdit, QVBoxLayout,
                               QWidget)

from . import __version__, localreg, theme
from .db import norm_name

OPEN_LAW_URL = "https://open.law.go.kr/LSO/main.do"

GUIDE_TEXT = """<b>국가법령정보 공동활용 API 인증키(OC) 발급받기</b>
<ol style='margin:4px 0 4px 16px;'>
<li>아래 버튼으로 <b>국가법령정보 공동활용</b> 사이트 열기</li>
<li><b>회원가입</b> → <b>로그인</b></li>
<li>메뉴에서 <b>OPEN API › OPEN API 신청</b></li>
<li>서비스 <b>전체선택 + 이용약관 동의</b> 후 신청 저장</li>
<li><b>API인증키관리</b>에서 발급된 <b>API 인증키(OC)</b>를 복사해 아래에 붙여넣기</li>
</ol>
<span style='color:#6b7280;font-size:9pt;'>※ 키는 Windows 사용자 계정으로 암호화(DPAPI)되어 이 PC에서만 열람할 수 있습니다.
※ 키가 없어도 프로그램은 정상 동작합니다(키 검증이 필요한 항목만 표시가 달라짐).</span>"""

AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    script = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "run.py")
    return f'"{pyw}" "{script}"'


def set_autostart(enable: bool):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0,
                        winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, "ImmediatelyLaw", 0, winreg.REG_SZ,
                              _autostart_command())
            try:   # 옛 한글 이름 항목이 남아 있으면 시작 시 중복 실행된다
                winreg.DeleteValue(k, "즉시로")
            except FileNotFoundError:
                pass
        else:
            for name in ("ImmediatelyLaw", "즉시로"):
                try:
                    winreg.DeleteValue(k, name)
                except FileNotFoundError:
                    pass


def get_autostart_command():
    """Run 키에 등록되어 있는 실행 문자열. 미등록이면 None."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as k:
            for name in ("ImmediatelyLaw", "즉시로"):
                try:
                    return winreg.QueryValueEx(k, name)[0]
                except FileNotFoundError:
                    continue
    except OSError:
        pass
    return None


def get_autostart() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as k:
            for name in ("ImmediatelyLaw", "즉시로"):
                try:
                    winreg.QueryValueEx(k, name)
                    return True
                except FileNotFoundError:
                    continue
        return False
    except OSError:
        return False


class SettingsDialog(QDialog):
    update_requested = Signal()
    app_update_requested = Signal()   # 프로그램 새 버전 확인(수동)
    saved = Signal()

    def __init__(self, cfg, db, parent=None):
        super().__init__(parent)
        self.cfg, self.db = cfg, db
        self.setWindowTitle(f"즉시로 설정  v{__version__}")
        self.resize(520, 460)
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self.tabs.addTab(self._tab_data(), "데이터")
        self.tabs.addTab(self._tab_local(), "자치법규")
        self.tabs.addTab(self._tab_api(), "API 키")
        self.tabs.addTab(self._tab_overlay(), "오버레이")
        self.tabs.addTab(self._tab_general(), "일반")
        self.tabs.addTab(self._tab_info(), "정보")

    # ---------- 데이터 ----------
    def _tab_data(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        st = self.db.stats()
        info = (f"현행 법령 <b>{st['laws']:,}</b>종 · 조문 <b>{st['articles']:,}</b>조"
                f" · 자치법규 <b>{st['local_laws']}</b>건<br>"
                f"데이터 기준일: <b>{st['data_ver'] or '없음'}</b>"
                f"  (갱신: {st['built_at'] or '-'})")
        lb = QLabel(info)
        lb.setTextFormat(Qt.RichText)
        lay.addWidget(lb)
        row = QHBoxLayout()
        self.ed_url = QLineEdit(self.cfg["data_base_url"])
        self.ed_url.setPlaceholderText("비우면 기본 배포 서버를 사용합니다")
        self.ed_url.setToolTip("직접 운영한 배포 서버 주소로 바꾸면 그곳을 먼저,\n"
                               "실패하면 기본 배포 서버로 자동 전환됩니다.")
        row.addWidget(QLabel("배포 주소"))
        row.addWidget(self.ed_url, 1)
        lay.addLayout(row)
        self.btn_upd = QPushButton("지금 업데이트")
        self.btn_upd.clicked.connect(self._req_update)
        lay.addWidget(self.btn_upd)
        lay.addStretch(1)
        tip = QLabel("· 조문 열람은 항상 이 PC의 로컬 데이터로 동작합니다(오프라인 OK).\n"
                     "· 업데이트는 하루 1회 자동이며, 아래 버튼으로 수동 실행도 됩니다.")
        tip.setStyleSheet("color:#6b7280;")
        lay.addWidget(tip)
        return w

    def _req_update(self):
        self._save_fields()
        self.update_requested.emit()

    # ---------- 자치법규 ----------
    LOCAL_FILTER = ("자치법규 파일 (*.hwpx *.hwp *.doc *.docx *.pdf *.rtf "
                    "*.txt *.md;;모든 파일 (*.*)")

    def _tab_local(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        tip = QLabel("기관에서 사용하는 자치법규(조례·규칙·훈령 등)를 등록하면 "
                     "국가 법령과 같은 방식으로 조문이 표시됩니다.\n"
                     "지원: .hwpx .hwp .doc .docx .pdf .rtf .txt .md — "
                     "regulations 폴더에 둔 파일은 시작 시 자동 등록됩니다.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#6b7280;")
        lay.addWidget(tip)
        self.local_tbl = QTableWidget(0, 3)
        self.local_tbl.setHorizontalHeaderLabels(["법령명", "조문", "파일"])
        self.local_tbl.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        self.local_tbl.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        self.local_tbl.setColumnWidth(1, 52)
        self.local_tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.local_tbl.setSelectionMode(QTableWidget.SingleSelection)
        self.local_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.local_tbl.setAlternatingRowColors(True)
        lay.addWidget(self.local_tbl, 1)
        row = QHBoxLayout()
        b_add = QPushButton("파일 추가…")
        b_add.clicked.connect(self._local_add)
        b_upd = QPushButton("제·개정 반영…")
        b_upd.clicked.connect(self._local_update)
        b_del = QPushButton("선택 삭제")
        b_del.clicked.connect(self._local_delete)
        for b in (b_add, b_upd, b_del):
            row.addWidget(b)
        lay.addLayout(row)
        self.lb_local = QLabel("")
        self.lb_local.setStyleSheet("color:#6b7280;")
        self.lb_local.setWordWrap(True)
        lay.addWidget(self.lb_local)
        self._local_refresh()
        return w

    def _local_refresh(self):
        rows = self.db.conn.execute(
            "SELECT ll.id, ll.name, ll.source, "
            "(SELECT COUNT(*) FROM local_article la WHERE la.lid=ll.id) n "
            "FROM local_law ll ORDER BY ll.name").fetchall()
        t = self.local_tbl
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            src = r["source"] or ""
            it0 = QTableWidgetItem(r["name"])
            it0.setData(Qt.UserRole, r["id"])
            it0.setData(Qt.UserRole + 1, src)
            it0.setData(Qt.UserRole + 2, r["name"])
            it1 = QTableWidgetItem(str(r["n"]))
            it1.setTextAlignment(Qt.AlignCenter)
            t.setItem(i, 0, it0)
            t.setItem(i, 1, it1)
            t.setItem(i, 2, QTableWidgetItem(os.path.basename(src)))
        if not rows:
            self.lb_local.setText("등록된 자치법규가 없습니다. [파일 추가…]로 "
                                  "추가하세요.")
        else:
            self.lb_local.setText(f"총 {len(rows)}건 등록됨.")

    def _local_selected(self):
        r = self.local_tbl.currentRow()
        if r < 0 or self.local_tbl.item(r, 0) is None:
            QMessageBox.information(self, "즉시로", "목록에서 자치법규를 "
                                                "선택하세요.")
            return None
        it = self.local_tbl.item(r, 0)
        return (it.data(Qt.UserRole), it.data(Qt.UserRole + 1),
                it.data(Qt.UserRole + 2))

    def _local_add(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "자치법규 파일 추가", localreg.REG_DIR, self.LOCAL_FILTER)
        if not files:
            return
        os.makedirs(localreg.REG_DIR, exist_ok=True)
        done, errs = [], []
        for f in files:
            dest = os.path.join(localreg.REG_DIR, os.path.basename(f))
            if os.path.abspath(f) != os.path.abspath(dest):
                if os.path.exists(dest):
                    resp = QMessageBox.question(
                        self, "동일 파일 존재",
                        f"{os.path.basename(dest)} 이(가) 이미 있습니다.\n"
                        "덮어쓰고 다시 등록할까요?",
                        QMessageBox.Yes | QMessageBox.No)
                    if resp != QMessageBox.Yes:
                        continue
                try:
                    shutil.copy2(f, dest)
                except OSError as e:
                    errs.append(f"{os.path.basename(f)}: {e}")
                    continue
            try:
                name, n = localreg.import_file(self.db, dest)
                done.append(f"{name} ({n}조)")
            except Exception as e:
                errs.append(f"{os.path.basename(f)}: {e}")
        self._local_refresh()
        self.saved.emit()
        if done and not errs:
            QMessageBox.information(self, "즉시로",
                                    "등록 완료\n" + "\n".join(done))
        else:
            QMessageBox.warning(
                self, "즉시로",
                ("\n".join(f"{n} 등록됨" for n in done) + "\n\n"
                 if done else "") + "실패:\n" + "\n".join(errs))

    def _local_update(self):
        sel = self._local_selected()
        if not sel:
            return
        lid, source, name = sel
        f, _ = QFileDialog.getOpenFileName(
            self, f"{name} — 제·개정된 새 파일 선택",
            os.path.dirname(source) or localreg.REG_DIR, self.LOCAL_FILTER)
        if not f:
            return
        dest = source or os.path.join(localreg.REG_DIR, os.path.basename(f))
        try:
            shutil.copy2(f, dest)
        except OSError as e:
            QMessageBox.warning(self, "즉시로", f"복사 실패: {e}")
            return
        try:
            new_name, n = localreg.import_file(self.db, dest)
        except Exception as e:
            QMessageBox.warning(self, "즉시로", f"등록 실패: {e}")
            return
        self._local_refresh()
        self.saved.emit()
        QMessageBox.information(
            self, "즉시로", f"{new_name} — 새 파일로 다시 등록했습니다"
                            f"({n}조).")

    def _local_delete(self):
        sel = self._local_selected()
        if not sel:
            return
        lid, source, name = sel
        resp = QMessageBox.question(
            self, "삭제",
            f"{name}을(를) 삭제할까요?\n"
            "등록 데이터와 regulations 폴더의 원본 파일이 함께 삭제됩니다.",
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        with self.db._lock:
            self.db.conn.execute("DELETE FROM local_article WHERE lid=?",
                                 (lid,))
            self.db.conn.execute("DELETE FROM local_law WHERE id=?", (lid,))
            self.db.conn.execute("DELETE FROM alias WHERE key=?",
                                 (norm_name(name),))
            self.db.conn.commit()
        if source and os.path.isfile(source):
            try:
                os.remove(source)
            except OSError:
                pass
        self._local_refresh()
        self.saved.emit()

    # ---------- API ----------
    def _tab_api(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        g = QTextEdit()
        g.setHtml(GUIDE_TEXT)
        g.setReadOnly(True)
        g.setMaximumHeight(160)
        lay.addWidget(g)
        row = QHBoxLayout()
        btn_site = QPushButton("발급 사이트 열기 ›")
        btn_site.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(OPEN_LAW_URL)))
        lay.addWidget(btn_site)
        self.ed_key = QLineEdit()
        self.ed_key.setEchoMode(QLineEdit.Password)
        self.ed_key.setPlaceholderText("발급받은 OC 인증키 붙여넣기")
        self.chk_show = QCheckBox("표시")
        self.chk_show.toggled.connect(
            lambda on: self.ed_key.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password))
        r2 = QHBoxLayout()
        r2.addWidget(self.ed_key, 1)
        r2.addWidget(self.chk_show)
        lay.addLayout(r2)
        r3 = QHBoxLayout()
        b_test = QPushButton("연결 테스트")
        b_test.clicked.connect(self._test_key)
        b_save = QPushButton("암호화 저장")
        b_save.clicked.connect(self._save_key)
        b_del = QPushButton("키 삭제")
        b_del.clicked.connect(self._del_key)
        for b in (b_test, b_save, b_del):
            r3.addWidget(b)
        lay.addLayout(r3)
        self.lb_api = QLabel(
            f"현재 저장됨: {self.cfg.masked_oc_key() or '없음'}")
        self.lb_api.setStyleSheet("color:#6b7280;")
        lay.addWidget(self.lb_api)
        lay.addStretch(1)
        return w

    def _test_key(self):
        key = self.ed_key.text().strip() or self.cfg.get_oc_key()
        if not key:
            QMessageBox.information(self, "즉시로", "키를 입력하세요.")
            return
        from .lawapi import LawApi
        try:
            ok = LawApi(key).ping()
            QMessageBox.information(
                self, "즉시로", "연결 성공 — 정상적으로 사용 가능합니다."
                if ok else "키는 응답했지만 결과가 없습니다.")
        except Exception as e:
            QMessageBox.warning(self, "즉시로", f"연결 실패: {e}")

    def _save_key(self):
        key = self.ed_key.text().strip()
        if not key:
            QMessageBox.information(self, "즉시로", "키를 입력하세요.")
            return
        self.cfg.set_oc_key(key)
        self.ed_key.clear()
        self.lb_api.setText(f"현재 저장됨: {self.cfg.masked_oc_key()}")
        self.saved.emit()
        QMessageBox.information(self, "즉시로",
                                "인증키를 이 PC 전용으로 암호화해 저장했습니다.")

    def _del_key(self):
        self.cfg.set_oc_key("")
        self.lb_api.setText("현재 저장됨: 없음")
        self.saved.emit()

    # ---------- 오버레이 ----------
    def _tab_overlay(self):
        w = QWidget()
        form = QFormLayout(w)
        self.sp_w = QSpinBox(minimum=320, maximum=720, singleStep=10,
                             value=int(self.cfg["overlay_width"]))
        self.cb_corner = QComboBox()
        for k, label in (("top_right", "우측 상단"), ("top_left", "좌측 상단"),
                         ("bottom_right", "우측 하단"),
                         ("bottom_left", "좌측 하단")):
            self.cb_corner.addItem(label, k)
        i = self.cb_corner.findData(self.cfg["overlay_corner"])
        self.cb_corner.setCurrentIndex(max(0, i))
        self.sp_hide = QSpinBox(minimum=0, maximum=300,
                                value=int(self.cfg["auto_hide_sec"]))
        self.sp_hide.setSuffix(" 초  (0 = 고정)")
        self.sp_font = QSpinBox(minimum=8, maximum=20,
                                value=int(self.cfg["font_pt"]))
        self.sp_font.setSuffix(" pt")
        self.chk_verify = QCheckBox("표시 후 현행 여부 자동 확인")
        self.chk_verify.setChecked(bool(self.cfg["verify_enabled"]))
        self.cb_theme = QComboBox()
        for k, label in (("system", "시스템 모드"), ("light", "라이트 모드"),
                         ("dark", "다크 모드")):
            self.cb_theme.addItem(label, k)
        i = self.cb_theme.findData(str(self.cfg.get("theme", "system")))
        self.cb_theme.setCurrentIndex(max(0, i))
        form.addRow("모드", self.cb_theme)
        form.addRow("카드 폭", self.sp_w)
        form.addRow("위 위치", self.cb_corner)
        form.addRow("글자 크기 (장·절·본문)", self.sp_font)
        form.addRow("자동 숨김", self.sp_hide)
        form.addRow("검증", self.chk_verify)
        return w

    # ---------- 일반 ----------
    def _tab_general(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.chk_hotkey = QCheckBox("단축키 Ctrl+Alt+L로 조회 창 열기")
        self.chk_hotkey.setChecked(bool(self.cfg["hotkey_enabled"]))
        self.chk_pause = QCheckBox("클립보드 감시 일시정지 (복사해도 카드 미표시)")
        self.chk_pause.setChecked(bool(self.cfg["clipboard_paused"]))
        self.chk_auto = QCheckBox("Windows 시작 시 자동으로 실행")
        self.chk_auto.setChecked(get_autostart())
        self.chk_updchk = QCheckBox("새 버전 알림(자동 업데이트 확인)")
        self.chk_updchk.setChecked(bool(self.cfg.get("update_check", True)))
        self.btn_updnow = QPushButton("지금 새 버전 확인")
        self.btn_updnow.clicked.connect(self.app_update_requested.emit)
        lay.addWidget(self.chk_hotkey)
        lay.addWidget(self.chk_pause)
        lay.addWidget(self.chk_auto)
        lay.addWidget(self.chk_updchk)
        lay.addWidget(self.btn_updnow)
        lay.addStretch(1)
        return w

    # ---------- 정보 ----------
    def _tab_info(self):
        p = theme.palette(self.cfg)
        link = p["fg"]          # 링크는 본문과 같은 색(검정)으로 표기
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        t1 = QLabel("즉시로 (Immediately Law)")
        t1.setFont(QFont("Malgun Gothic", 12, QFont.Bold))
        t2 = QLabel(f"v{__version__}")
        t2.setStyleSheet("color:#6b7280;")
        row.addWidget(t1)
        row.addStretch(1)
        row.addWidget(t2)
        lay.addLayout(row)
        lay.addSpacing(26)
        msg = QLabel("복사(Ctrl + C)만 하면 조문이 화면 오른쪽 아래에 "
                     "나옵니다.")
        msg.setFont(QFont("Malgun Gothic", 10))
        msg.setWordWrap(True)
        lay.addWidget(msg)
        lay.addSpacing(26)

        def a(url: str, text: str) -> str:
            return (f"<a href='{url}' style='color:{link};"
                    f"text-decoration:underline'>{text}</a>")

        td = "color:#6b7280;padding-right:12px;"
        info = QLabel(
            "<table cellspacing='0' cellpadding='2'>"
            f"<tr><td style='{td}'>제작자</td><td>홍성민 주무관(서초구청)</td></tr>"
            f"<tr><td style='{td}'>연락처</td>"
            "<td>" + a("mailto:irize@seocho.go.kr", "irize@seocho.go.kr")
            + "<br>02-2155-6089</td></tr>"
            f"<tr><td style='{td}'>소스 코드</td><td>"
            + a("https://github.com/nazgregory/ImmediatelyLaw",
                "github.com/nazgregory/ImmediatelyLaw") + " (MIT)</td></tr>"
            f"<tr><td style='{td}'>법령 데이터</td><td>"
            + a("https://152.67.205.216/manifest.json", "자가 배포 서버")
            + " — 국가법령정보센터(법제처) 개방 데이터</td></tr>"
            "</table>")
        info.setTextFormat(Qt.RichText)
        info.setOpenExternalLinks(True)
        info.setTextInteractionFlags(Qt.TextBrowserInteraction)
        lay.addWidget(info)
        tip = QLabel("· 법령의 효력 판정은 공식 원문이 기준이며, "
                     "즉시로의 표시는 참고용입니다.")
        tip.setStyleSheet("color:#6b7280;")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        lay.addStretch(1)
        return w

    # ---------- 저장 ----------
    def _save_fields(self):
        self.cfg["overlay_width"] = self.sp_w.value()
        self.cfg["overlay_corner"] = self.cb_corner.currentData()
        self.cfg["auto_hide_sec"] = self.sp_hide.value()
        self.cfg["font_pt"] = self.sp_font.value()
        self.cfg["theme"] = self.cb_theme.currentData()
        self.cfg["verify_enabled"] = self.chk_verify.isChecked()
        self.cfg["hotkey_enabled"] = self.chk_hotkey.isChecked()
        self.cfg["clipboard_paused"] = self.chk_pause.isChecked()
        url = self.ed_url.text().strip().rstrip("/")
        if url and not url.lower().startswith("https://"):
            QMessageBox.warning(
                self, "즉시로 설정",
                "데이터 배포 주소는 https만 사용할 수 있습니다.\n"
                "입력한 주소는 저장되지 않았습니다.")
        else:
            self.cfg["data_base_url"] = url
        # 의도된 시작 실행 상태를 설정에 기록(부팅 시 자동 등록 판단용)
        self.cfg["autostart"] = self.chk_auto.isChecked()
        self.cfg["update_check"] = self.chk_updchk.isChecked()
        self.cfg.save()
        if self.chk_auto.isChecked() != get_autostart():
            try:
                set_autostart(self.chk_auto.isChecked())
            except OSError:
                pass

    def done(self, r):
        self._save_fields()
        self.saved.emit()
        super().done(r)
