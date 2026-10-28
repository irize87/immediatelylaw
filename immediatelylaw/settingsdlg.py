# -*- coding: utf-8 -*-
"""설정 창: 데이터 / API 키(발급 안내 + DPAPI 저장) / 오버레이 / 일반."""
import os
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout,
                               QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox,
                               QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from . import __version__

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
        self.tabs.addTab(self._tab_api(), "API 키")
        self.tabs.addTab(self._tab_overlay(), "오버레이")
        self.tabs.addTab(self._tab_general(), "일반")

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
        self.ed_url.setPlaceholderText("데이터 배포 주소 (…/immediatelylaw-data/dist)")
        row.addWidget(QLabel("배포 주소"))
        row.addWidget(self.ed_url, 1)
        lay.addLayout(row)
        self.btn_upd = QPushButton("지금 업데이트 (GitHub)")
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
        self.chk_verify = QCheckBox("표시 후 현행 여부 자동 확인")
        self.chk_verify.setChecked(bool(self.cfg["verify_enabled"]))
        form.addRow("카드 폭", self.sp_w)
        form.addRow("위 위치", self.cb_corner)
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
        lay.addWidget(self.chk_hotkey)
        lay.addWidget(self.chk_pause)
        lay.addWidget(self.chk_auto)
        lay.addStretch(1)
        return w

    # ---------- 저장 ----------
    def _save_fields(self):
        self.cfg["overlay_width"] = self.sp_w.value()
        self.cfg["overlay_corner"] = self.cb_corner.currentData()
        self.cfg["auto_hide_sec"] = self.sp_hide.value()
        self.cfg["verify_enabled"] = self.chk_verify.isChecked()
        self.cfg["hotkey_enabled"] = self.chk_hotkey.isChecked()
        self.cfg["clipboard_paused"] = self.chk_pause.isChecked()
        self.cfg["data_base_url"] = self.ed_url.text().strip()
        # 의도된 시작 실행 상태를 설정에 기록(부팅 시 자동 등록 판단용)
        self.cfg["autostart"] = self.chk_auto.isChecked()
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
