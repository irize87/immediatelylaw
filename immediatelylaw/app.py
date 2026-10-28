# -*- coding: utf-8 -*-
"""즉시로 앱 본체: 트레이·단축키·감시·오버레이·갱신을 배선한다."""
import logging
import os
import sys
import time

from PySide6.QtCore import (QAbstractNativeEventFilter, QObject, Qt, QTimer,
                            Signal)
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QIcon,
                           QKeySequence, QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QMenu, QMessageBox,
                               QProgressDialog, QSystemTrayIcon, QWidget)

from . import __version__, APP_TITLE, localreg, resolver
from .config import get_config
from .db import get_db
from .lawapi import LawApi
from .overlay import OverlayCard
from .searchwin import SearchWindow
from .settingsdlg import SettingsDialog
from .watcher import ClipboardWatcher, note_self_copy
from . import workers
from .workers import UpdaterWorker, VerifyWorker

HOTKEY_ID = 0x5B51


def make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor("#2563eb")))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    p.setPen(QPen(QColor("#ffffff")))
    p.setFont(QFont("Malgun Gothic", 30, QFont.Bold))
    p.drawText(pm.rect(), Qt.AlignCenter, "법")
    p.end()
    return QIcon(pm)


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._cb = callback

    def nativeEventFilter(self, event_type, message):
        if sys.platform != "win32" or not bytes(event_type).startswith(b"windows_msg"):
            return False, 0
        try:
            import ctypes.wintypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                self._cb()
                return True, 0
        except Exception:
            pass
        return False, 0


class ImmediatelyLaw(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.cfg = get_config()
        self.db = get_db()
        self.api = None
        self._refresh_api()
        self._workers = []
        self._progress = None

        app.setWindowIcon(make_icon())
        self.overlay = OverlayCard(self.cfg)
        self.overlay.copy_requested.connect(self._copy_out)
        self.overlay.verify_requested.connect(self._start_verify)

        self.watcher = ClipboardWatcher(app.clipboard(), self.cfg)
        self.watcher.citation.connect(self._on_citation)

        self.search = None
        self.settings = None

        self.tray = QSystemTrayIcon(make_icon(), app)
        self.tray.setToolTip(APP_TITLE)
        self._build_menu()
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        # 전역 단축키
        self.hkf = HotkeyFilter(self.show_search)
        app.installNativeEventFilter(self.hkf)
        self._register_hotkey()

        # 시작 시: 자치법규 스캔 → 데이터 부팅 → 백그라운드 갱신
        QTimer.singleShot(60, self._boot)
        self._upd_timer = QTimer(self, interval=8 * 3600 * 1000)
        self._upd_timer.timeout.connect(lambda: self._update(auto=True))

    # ---------- 부팅 ----------
    def _boot(self):
        # 시작 프로그램 기본 켬: 설정에서 꺼둔 적(autostart=False 저장)이
        # 없으면 Run 키를 항상 유지하고, 실행 경로가 바뀌었으면 갱신한다.
        try:
            from .settingsdlg import (_autostart_command, get_autostart_command,
                                      set_autostart)
            if self.cfg["autostart"] and \
                    get_autostart_command() != _autostart_command():
                set_autostart(True)
        except OSError:
            pass
        try:
            ok, fail = localreg.scan_dir(self.db)
            for fn, name, n in ok:
                self.tray.showMessage(APP_TITLE,
                                      f"자치법규 등록: {name} ({n}조)",
                                      QSystemTrayIcon.Information, 4000)
            for fn, err in fail:
                self.tray.showMessage(APP_TITLE,
                                      f"자치법규 실패: {fn} — {err}",
                                      QSystemTrayIcon.Warning, 6000)
        except Exception as e:
            print("localreg scan error:", e)
        st = self.db.stats()
        if st["laws"] == 0:
            # 1순위: 오프라인 배포본에 동봉된 스냅샷(exe 옆 *.db.xz)
            xz = workers.bundled_snapshot()
            if xz:
                try:
                    self.db.reload_from_file(workers.install_xz(xz))
                    ver = self.db.get_meta("data_ver", "")
                    self.tray.showMessage(
                        APP_TITLE, f"오프라인 데이터 적용 완료 ({ver} 기준). "
                        "조문을 복사하면 카드가 뜹니다.",
                        QSystemTrayIcon.Information, 6000)
                    self._upd_timer.start()
                    self._update(auto=True)   # 네트워크 있으면 최신 확인
                    return
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        "bundled snapshot failed: %s", e)
            if self.cfg["data_base_url"]:
                self._update(auto=False)
            else:
                self.tray.showMessage(
                    APP_TITLE, "법령 데이터가 없습니다. 설정 › 데이터에서 "
                    "배포 주소를 입력하세요.", QSystemTrayIcon.Warning, 8000)
                self.show_settings()
        else:
            self._upd_timer.start()
            self._update(auto=True)

    def _refresh_api(self):
        key = self.cfg.get_oc_key()
        self.api = LawApi(key) if key else None

    # ---------- 클립보드 ----------
    def _on_citation(self, payload: dict):
        cites = payload.get("cites") or []
        if not cites:
            return
        c = cites[0]
        res = resolver.resolve(self.db, c["law"], c["art"], None,
                               hints=c.get("law_all"))
        if res.get("found"):
            if res["source"] == "local":
                self.overlay.show_result(res, note="로컬 데이터")
            elif res["source"] == "local-reg":
                self.overlay.show_result(res, note="등록 파일")
            else:
                self.overlay.show_result(res)
            if len(cites) > 1:
                self.overlay.set_state(
                    f"이 텍스트에 인용 {len(cites)}건 — 첫 인용 표시")
            return
        # 미보유: OC 키 있으면 라이브 폴백
        if self.api is not None:
            from .workers import ResolveWorker
            self.overlay.lb_title.setText(
                f"{c['law']} 제{c['art']}조")
            self.overlay.set_badge("neutral", "(가져오는 중)")
            self.overlay.set_state("법제처에서 가져오는 중…")
            w = ResolveWorker(self.db, self.api, c["law"], c["art"],
                              hints=c.get("law_all"))
            w.done.connect(self._on_live_resolved)
            self._workers.append(w)
            w.start()
        else:
            self.overlay.lb_title.setText(f"{c['law']} 제{c['art']}조")
            self.overlay.set_badge("check", "(확인)")
            self.overlay.set_state("로컬 데이터에 없는 법령입니다. "
                                   "데이터 갱신이나 API 키를 확인하세요.")
            if not self.overlay.isVisible():
                self.overlay._place_and_show()

    def _on_live_resolved(self, res: dict):
        if res.get("found"):
            self.overlay.show_result(res, note="법제처에서 가져옴")
        else:
            self.overlay.set_badge("check", "(확인)")
            self.overlay.set_state("법제처에서도 찾을 수 없습니다.")

    # ---------- 검증 ----------
    def _start_verify(self, res: dict):
        if not self.cfg["verify_enabled"]:
            ver = self.db.get_meta("data_ver")
            if ver:
                kind, msg = "current", f"데이터 {ver[4:6]}.{ver[6:8]} 기준 · 미검증"
            else:
                kind, msg = "check", "미검증"
            self.overlay.set_badge(kind, "(현행)" if kind == "current" else "(확인)")
            self.overlay.set_state(msg)
            return
        w = VerifyWorker(self.db, self.api, res)
        w.done.connect(self._on_verified)
        self._workers.append(w)
        w.start()

    def _on_verified(self, kind: str, msg: str):
        text = {"current": "(현행)", "check": "(확인)",
                "offline": "(오프라인)"}.get(kind)
        self.overlay.set_badge(kind if kind in ("current", "check")
                               else "neutral", text)
        self.overlay.set_state(msg)

    def _copy_out(self, text: str):
        note_self_copy(text)
        self.app.clipboard().setText(text)

    # ---------- 갱신 ----------
    def _update(self, auto=True):
        if self._progress is not None:
            return
        base = self.cfg["data_base_url"]
        if not base:
            if not auto:
                self.show_settings()
            return
        w = UpdaterWorker(self.db, base)
        # QThread 래퍼가 지역변수면 함수 종료 후 GC되어
        # "Destroyed while running" qFatal 크래시가 난다. 참조 유지 필수.
        self._workers.append(w)
        w.finished.connect(lambda: self._workers.remove(w)
                           if w in self._workers else None)
        dlg = QProgressDialog("법령 데이터 확인 중…", "취소", 0, 0, None)
        dlg.setWindowTitle(APP_TITLE)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(400)
        dlg.setValue(0)
        self._progress = dlg
        w.progress.connect(self._upd_progress)
        w.db_replaced.connect(lambda p: self.db.reload_from_file(p))
        w.done.connect(lambda ok, msg: self._upd_done(ok, msg, auto))
        w.start()

    def _upd_progress(self, msg, pct):
        if self._progress is None:
            return
        if pct < 0:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, 100)
        self._progress.setLabelText(msg)
        if pct >= 0:
            self._progress.setValue(pct)

    def _upd_done(self, ok: bool, msg: str, auto: bool):
        if self._progress is not None:
            self._progress.reset()
            self._progress = None
        if ok:
            self.db.set_meta("last_update_check",
                             time.strftime("%Y%m%d%H%M"))
            self.tray.showMessage(APP_TITLE, msg,
                                  QSystemTrayIcon.Information, 5000)
        elif not auto:
            QMessageBox.information(self.search or None, APP_TITLE, msg)

    # ---------- 창 ----------
    @staticmethod
    def _center(win):
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen().availableGeometry()
        win.move(scr.center().x() - win.width() // 2,
                 max(scr.top() + 20, scr.center().y() - win.height() // 2))

    def show_search(self):
        if self.search is None:
            self.search = SearchWindow(self.db, lambda: self.api, self.cfg)
            self.search.copy_requested.connect(self._copy_out)
            self.search.destroyed.connect(lambda: setattr(self, "search", None))
            self._center(self.search)
        self.search.show()
        self.search.raise_()
        self.search.activateWindow()
        QTimer.singleShot(50, lambda: self.search.ed.setFocus())

    def show_settings(self):
        if self.settings is None:
            self.settings = SettingsDialog(self.cfg, self.db)
            self.settings.saved.connect(self._refresh_api)
            self.settings.update_requested.connect(lambda: self._update(auto=False))
            self.settings.finished.connect(
                lambda _: setattr(self, "settings", None))
            self._center(self.settings)
        self.settings.show()
        self.settings.raise_()

    # ---------- 트레이 ----------
    def _build_menu(self):
        # 요청 사양: 우클릭 메뉴는 3개만 — 법령검색창 / 설정 / 종료
        m = QMenu()
        act_search = m.addAction("법령 검색창  (Ctrl+Alt+L)")
        act_search.triggered.connect(self.show_search)
        act_set = m.addAction("설정")
        act_set.triggered.connect(self.show_settings)
        act_quit = m.addAction("종료")
        act_quit.triggered.connect(self.app.quit)
        self.tray.setContextMenu(m)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_search()

    def _register_hotkey(self):
        if sys.platform != "win32" or not self.cfg["hotkey_enabled"]:
            return
        import ctypes
        MOD_ALT, MOD_CONTROL = 0x0001, 0x0002
        ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID,
                                            MOD_ALT | MOD_CONTROL, 0x4C)


def _single_instance() -> bool:
    """이미 실행 중이면 False."""
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    probe = QLocalSocket()
    probe.connectToServer("jisilo_single_instance")
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(300)
        probe.disconnectFromServer()
        return False
    QLocalServer.removeServer("jisilo_single_instance")
    server = QLocalServer()
    if not server.listen("jisilo_single_instance"):
        return True
    app_ref = {}

    def on_conn():
        c = server.nextPendingConnection()
        if c is not None:
            c.waitForReadyRead(200)
            c.deleteLater()
            inst = app_ref.get("win")
            if inst is not None:
                inst.show_search()
    server.newConnection.connect(on_conn)
    app_ref["server"] = server  # 가비지 방지
    _single_instance._keepalive = (server, app_ref)
    return True


def main():
    import logging
    from .db import DATA_DIR
    log_dir = DATA_DIR
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_dir, "immediatelylaw.log"), level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s")

    def hook(t, v, tb):
        logging.error("".join(__import__("traceback").format_exception(t, v, tb)))
    sys.excepthook = hook

    app = QApplication(sys.argv)
    # Windows 다크 테마여도 앱은 밝은 팔레트를 강제한다
    # (흰 배경 위 기본 흰 글자 = invisible 방지).
    from PySide6.QtGui import QPalette
    app.setStyle("Fusion")
    pal = app.palette()
    C = QColor
    pal.setColor(QPalette.Window, C("#f2f4f7"))
    pal.setColor(QPalette.Base, C("#ffffff"))
    pal.setColor(QPalette.Text, C("#20242b"))
    pal.setColor(QPalette.WindowText, C("#20242b"))
    pal.setColor(QPalette.ButtonText, C("#20242b"))
    pal.setColor(QPalette.Button, C("#e8ebef"))
    pal.setColor(QPalette.Highlight, C("#2563eb"))
    pal.setColor(QPalette.HighlightedText, C("#ffffff"))
    app.setPalette(pal)
    app.setApplicationName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)
    if not _single_instance():
        sys.exit(0)
    inst = ImmediatelyLaw(app)
    _single_instance._keepalive[1]["win"] = inst
    sys.exit(app.exec())
