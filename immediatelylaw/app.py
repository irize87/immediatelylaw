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

from . import (__version__, APP_TITLE, localreg, perf, refparse, resolver,
               theme)
from .config import get_config
from .db import get_db
from .lawapi import LawApi
from .overlay import OverlayCard
from .searchwin import SearchWindow
from .settingsdlg import SettingsDialog
from .watcher import ClipboardWatcher, note_self_copy
from . import workers
from .workers import (AppDownloadWorker, AppUpdateWorker, UpdaterWorker,
                      VerifyWorker)

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


def set_app_user_model_id():
    """작업표시줄 단추를 호스트(pythonw.exe=파이썬 아이콘)에서 떼어
    앱 고유의 트레이 아이콘('법')으로 뜨게 한다. 패키징 exe에서도 동일 적용."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Seocho.ImmediatelyLaw")
    except Exception:
        pass


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
        app.setStyleSheet(theme.app_qss(self.cfg))   # 시스템/라이트/다크

        self.watcher = ClipboardWatcher(app.clipboard(), self.cfg)
        self.watcher.citation.connect(self._on_citation)

        self.search = None
        self.settings = None
        self._app_upd = None     # 실행 중인 버전 확인 워커
        self._dl = None          # 실행 중인 설치 파일 다운로드 워커
        self._dlprog = None

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
        self._upd_timer.timeout.connect(self._timer_tick)
        # 프로그램 새 버전 확인: 부팅 20초 후 1회, 이후 8시간마다.
        QTimer.singleShot(20000, lambda: self._check_app_update(auto=True))

    def _timer_tick(self):
        self._update(auto=True)
        self._check_app_update(auto=True)

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

    def _apply_theme(self):
        """테마(시스템/라이트/다크) 변경 반영: 전역 스타일 + 카드 + 조회창."""
        self.app.setStyleSheet(theme.app_qss(self.cfg))
        self.overlay._refresh_palette()
        if self.search is not None:
            self.search._refresh_palette()

    def _refresh_api(self):
        key = self.cfg.get_oc_key()
        self.api = LawApi(key) if key else None

    # ---------- 클립보드 ----------
    def _on_citation(self, payload: dict):
        cites = payload.get("cites") or []
        if not cites:
            return
        rid = int(payload.get("rid") or 0)
        c0 = cites[0]
        # 같은 법령 계열(본법 기준) 인용은 이어서 함께 표시한다.
        # 예: 「도서관법」 제33조 및 같은 법 시행령 제19조
        base0 = refparse.base_name(c0["law"])
        group = [c for c in cites
                 if refparse.base_name(c["law"]) == base0][:3]
        found = []
        perf.mark(rid, "resolve_start", group=len(group))
        for c in group:
            r = resolver.resolve(self.db, c["law"], c["art"], None,
                                 hints=c.get("law_all"))
            if r.get("found"):
                found.append(r)
        perf.mark(rid, "resolve_end", found=len(found))
        if found:
            self.overlay.show_results(found, rid=rid)
            self._remember_law(found[0]["law_name"])
            rest = len(cites) - len(group)
            if rest > 0:
                self.overlay.set_state(
                    f"이 텍스트에 인용 {len(cites)}건 — 같은 법령 계열 "
                    f"{len(found)}건 표시")
            return
        c = c0
        # 미보유: OC 키 있으면 라이브 폴백
        if self.api is not None:
            from .workers import ResolveWorker
            self.overlay.lb_title.setText(
                f"{c['law']} 제{c['art']}조")
            self.overlay.set_badge("neutral", "가져오는 중",
                                   "법제처에서 조문을 가져오는 중입니다.")
            self.overlay.set_state("법제처에서 가져오는 중…")
            w = ResolveWorker(self.db, self.api, c["law"], c["art"],
                              hints=c.get("law_all"))
            gen = self.overlay.card_gen()
            w.done.connect(
                lambda res, g=gen: self._on_live_resolved(g, res))
            self._workers.append(w)
            w.start()
        else:
            self.overlay.lb_title.setText(f"{c['law']} 제{c['art']}조")
            self.overlay.set_badge("check", "확인",
                                   "저장된 데이터에서 찾지 못했습니다.\n"
                                   "데이터 갱신이나 API 키를 확인하세요.")
            self.overlay.set_state("로컬 데이터에 없는 법령입니다. "
                                   "데이터 갱신이나 API 키를 확인하세요.")
            if not self.overlay.isVisible():
                self.overlay._place_and_show()

    def _on_live_resolved(self, gen: int, res: dict):
        if gen != self.overlay.card_gen():
            return   # 이미 다른 조문이 표시됨 — 늦은 라이브 결과는 폐기
        if res.get("found"):
            self.overlay.show_result(res)
            self._remember_law(res["law_name"])
        else:
            self.overlay.set_badge("check", "확인",
                                   "법제처에서도 찾을 수 없습니다.")
            self.overlay.set_state("법제처에서도 찾을 수 없습니다.")

    def _remember_law(self, law_name: str):
        """마지막으로 표시한 본법 이름을 기억 — '같은 법' 단독 인용 해석에 쓰인다."""
        b = refparse.base_name(law_name)
        if b and self.cfg.get("last_law") != b:
            self.cfg["last_law"] = b
            self.cfg.save()

    # ---------- 검증 ----------
    def _start_verify(self, res: dict):
        gen = self.overlay.card_gen()   # 이 검증이 속한 카드 세대
        if not self.cfg["verify_enabled"]:
            # 실시간 확인 꺼짐 — 배지도 '데이터 기준'임을 분명히 표시한다.
            ver = self.db.get_meta("data_ver") or ""
            if ver:
                self.overlay.set_badge(
                    "current", "현행",
                    f"데이터 기준 확인 — 마지막 데이터 갱신({ver}) 시점의 "
                    "현행 여부입니다.\n실시간 대조는 설정에서 켤 수 있습니다.")
            else:
                self.overlay.set_badge(
                    "check", "확인",
                    "데이터 갱신 시점을 알 수 없습니다. 데이터 갱신을 "
                    "실행해 보세요.")
            return
        w = VerifyWorker(self.db, self.api, res)
        w.done.connect(lambda kind, msg, g=gen: self._on_verified(g, kind, msg))
        self._workers.append(w)
        w.start()

    def _on_verified(self, gen: int, kind: str, msg: str):
        if gen != self.overlay.card_gen():
            return   # 다른 조문이 이미 표시됨 — 늦은 결과는 폐기한다
        text = {"current": "현행", "check": "확인",
                "offline": "오프라인"}.get(kind)
        if kind == "check" and msg:
            tip = f"실시간 확인 결과\n{msg}"
        elif kind not in ("current", "check"):
            tip = ("오프라인 — 실시간 확인을 수행하지 못했습니다.\n"
                   "표시 내용은 데이터 갱신 시점 기준입니다.")
        else:
            tip = ""   # current: 카드 기본 문구(법제처 실시간 확인) 사용
        self.overlay.set_badge(kind if kind in ("current", "check")
                               else "neutral", text, tip)

    def _copy_out(self, text: str):
        note_self_copy(text)
        self.app.clipboard().setText(text)

    # ---------- 갱신 ----------
    def _update(self, auto=True):
        if self._progress is not None:
            return
        hosts = workers.data_host_list(self.cfg)
        if not hosts:
            if not auto:
                self.show_settings()
            return
        w = UpdaterWorker(self.db, hosts)
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

    # ---------- 프로그램 새 버전(자동 업데이트) ----------
    def _check_app_update(self, auto=True):
        if auto and not self.cfg.get("update_check", True):
            return
        if self._app_upd is not None or self._dl is not None:
            return
        w = AppUpdateWorker(__version__,
                            offline=bool(workers.bundled_snapshot()),
                            hosts=workers.data_host_list(self.cfg))
        self._app_upd = w
        self._workers.append(w)
        w.finished.connect(lambda: self._workers.remove(w)
                           if w in self._workers else None)
        w.finished.connect(lambda: setattr(self, "_app_upd", None))
        w.found.connect(lambda info: self._offer_update(info, auto))
        w.latest.connect(lambda: None if auto else QMessageBox.information(
            self.search or None, APP_TITLE,
            f"이미 최신 버전(v{__version__})입니다."))
        w.failed.connect(lambda m: None if auto else QMessageBox.information(
            self.search or None, APP_TITLE, f"버전 확인에 실패했습니다.\n{m}"))
        w.start()

    def _offer_update(self, info: dict, auto: bool):
        ver = info["version"]
        if auto and ver == self.cfg.get("update_skip_ver", ""):
            return
        if getattr(self, "_offer_open", False):
            return          # 이미 제안 대화상자가 열려 있다
        self._offer_open = True
        box = QMessageBox(QMessageBox.Information, APP_TITLE,
                          f"새 버전 v{ver}이(가) 나왔습니다 "
                          f"(현재 v{__version__}).\n\n"
                          "지금 자동 업데이트할까요?\n"
                          "다운로드 후 설치가 끝나면 프로그램이 자동으로 "
                          "재시작됩니다.",
                          QMessageBox.NoButton, None)
        b_yes = box.addButton("자동 업데이트", QMessageBox.AcceptRole)
        b_no = box.addButton("나중에", QMessageBox.RejectRole)
        b_skip = box.addButton("이 버전은 알림 끄기", QMessageBox.DestructiveRole) \
            if auto else None
        box.setDefaultButton(b_no)
        box.setWindowFlags(box.windowFlags() | Qt.WindowStaysOnTopHint)
        # exec() 반환값은 표준 버튼 int라 커스텀 버튼과 대조가 불안정하다.
        # 클릭 시그널로 선택을 기록한다.
        choice = []
        b_yes.clicked.connect(lambda: choice.append("yes"))
        b_no.clicked.connect(lambda: choice.append("no"))
        if b_skip is not None:
            b_skip.clicked.connect(lambda: choice.append("skip"))
        try:
            box.exec()
        finally:
            self._offer_open = False
        sel = choice[0] if choice else "no"
        if sel == "yes":
            self._download_update(info)
        elif sel == "skip":
            self.cfg["update_skip_ver"] = ver
            self.cfg.save()
        elif not auto:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            if info.get("page"):
                QDesktopServices.openUrl(QUrl(info["page"]))

    def _download_update(self, info: dict):
        if self._dl is not None:
            return
        w = AppDownloadWorker(info)
        self._dl = w
        self._workers.append(w)
        w.finished.connect(lambda: self._workers.remove(w)
                           if w in self._workers else None)
        w.finished.connect(lambda: setattr(self, "_dl", None))
        dlg = QProgressDialog(f"v{info['version']} 업데이트 준비 중…",
                              "취소", 0, 100, None)
        dlg.setWindowTitle(APP_TITLE)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        self._dlprog = dlg
        w.progress.connect(self._dl_progress)
        w.failed.connect(self._dl_failed)
        dlg.canceled.connect(lambda: setattr(w, "cancel", True))
        w.ready.connect(lambda path: self._apply_update(path, info))
        w.start()

    def _dl_progress(self, msg, pct):
        if self._dlprog is None:
            return
        self._dlprog.setRange(0, 100 if pct >= 0 else 0)
        self._dlprog.setLabelText(msg)
        if pct >= 0:
            self._dlprog.setValue(pct)

    def _dl_failed(self, msg: str):
        if self._dlprog is not None:
            self._dlprog.reset()
            self._dlprog = None
        QMessageBox.warning(self.search or None, APP_TITLE,
                            f"업데이트 준비에 실패했습니다.\n{msg}")

    def _apply_update(self, src_dir: str, info: dict):
        """지금 프로세스를 종료하고, 교체 배치(update.bat)로 파일을 덮어쓴 뒤
        새 exe를 실행한다. 설정·법령 데이터(%APPDATA%)는 그대로 남는다."""
        if self._dlprog is not None:
            self._dlprog.reset()
            self._dlprog = None
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self.search or None, APP_TITLE,
                "개발 환경에서는 자동 업데이트를 적용할 수 없습니다.\n"
                "GitHub Releases에서 설치 파일을 받아 설치하세요.")
            return
        import subprocess
        import tempfile
        exe = sys.executable
        dst = os.path.dirname(exe)
        # ASCII만 사용: 코드 페이지와 무관하게 동작하도록.
        script = (
            "@echo off\r\n"
            "set PID=%~1\r\n"
            "set SRC=%~2\r\n"
            "set DST=%~3\r\n"
            ":loop\r\n"
            "ping -n 2 127.0.0.1 >nul\r\n"
            "taskkill /PID %PID% /F >nul 2>&1\r\n"
            "if not errorlevel 1 goto loop\r\n"
            "robocopy \"%SRC%\" \"%DST%\" /E /R:5 /W:2 /NFL /NDL /NJH /NJS"
            " >\"%TEMP%\\immediatelylaw-update.log\" 2>&1\r\n"
            "if %ERRORLEVEL% GEQ 8 goto fail\r\n"
            "start \"\" \"%DST%\\ImmediatelyLaw.exe\"\r\n"
            "goto end\r\n"
            ":fail\r\n"
            "start \"\" /min cmd /k type"
            " \"%TEMP%\\immediatelylaw-update.log\"\r\n"
            ":end\r\n"
            "del \"%~f0\"\r\n")
        try:
            # 고정 이름 대신 배타 생성(mkstemp): 같은 사용자 악성 프로세스가
            # 미리 파일을 만들어 실행 내용을 바꾸는 선점경쟁 원천 차단.
            fd, bat = tempfile.mkstemp(prefix="immediatelylaw-update-",
                                       suffix=".bat")
            with os.fdopen(fd, "w", encoding="ascii") as f:
                f.write(script)
            detached = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
            subprocess.Popen(["cmd.exe", "/c", bat, str(os.getpid()),
                              src_dir, dst],
                             creationflags=detached, close_fds=True)
        except OSError as e:
            QMessageBox.warning(self.search or None, APP_TITLE,
                                f"업데이트 시작에 실패했습니다.\n{e}")
            return
        self.tray.showMessage(APP_TITLE,
                              f"v{info['version']} 업데이트 적용 후 "
                              "재시작합니다…",
                              QSystemTrayIcon.Information, 4000)
        QTimer.singleShot(600, lambda: os._exit(0))

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
            self.settings.saved.connect(self._apply_theme)
            self.settings.update_requested.connect(lambda: self._update(auto=False))
            self.settings.app_update_requested.connect(
                lambda: self._check_app_update(auto=False))
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
        act_set = m.addAction(f"설정  (v{__version__})")
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
    set_app_user_model_id()
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
