# -*- coding: utf-8 -*-
"""클립보드 감시. 복사 이벤트가 오면 즉시 인용을 파싱해 알림."""
import hashlib
import os
import time

from PySide6.QtCore import QObject, QTimer, Signal

from . import refparse

_self_copy = {"t": 0.0, "h": ""}
DEBUG_LOG = os.environ.get("IMMEDIATELYLAW_DEBUG_LOG", "")


def _dbg(*a):
    if DEBUG_LOG:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(" ".join(str(x) for x in a) + "\n")


def note_self_copy(text: str):
    _self_copy["t"] = time.time()
    _self_copy["h"] = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


class ClipboardWatcher(QObject):
    """text가 클립보드에 들어오면 인용 후보를 분석해 citation 신호를 낸다.
    citation payload: {"cites":[...], "text":str}"""
    citation = Signal(dict)

    def __init__(self, clipboard, cfg, parent=None):
        super().__init__(parent)
        self.clip = clipboard
        self.cfg = cfg
        self.clip.dataChanged.connect(self._on_changed)
        self._timer = QTimer(self, singleShot=True, interval=120)
        self._timer.timeout.connect(self._handle)

    def _on_changed(self):
        if self.cfg["clipboard_paused"]:
            return
        self._timer.start()

    def _handle(self):
        try:
            text = self.clip.text()
        except Exception as e:
            _dbg("clip.text error:", e)
            return
        _dbg("dataChanged len=", len(text or ""), "text=", (text or "")[:60])
        if not text or len(text) > 500_000:
            return
        now = time.time()
        h = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()
        if now - _self_copy["t"] < 1.0 and h == _self_copy["h"]:
            return  # 우리 프로그램이 복사한 것
        cites = refparse.parse(text)
        _dbg("parsed cites:", [(c['law'], c['art']) for c in cites])
        if cites:
            self.citation.emit({"cites": cites, "text": text})
