# -*- coding: utf-8 -*-
"""클립보드 감시. 복사 이벤트가 오면 즉시 인용을 파싱해 알림."""
import hashlib
import itertools
import os
import time

from PySide6.QtCore import QObject, QTimer, Signal

from . import perf, refparse

_self_copy = {"t": 0.0, "h": ""}
DEBUG_LOG = os.environ.get("IMMEDIATELYLAW_DEBUG_LOG", "")


def _dbg(*a):
    if DEBUG_LOG:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(" ".join(str(x) for x in a) + "\n")


def note_self_copy(text: str):
    _self_copy["t"] = time.time()
    _self_copy["h"] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


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
        self._ev = itertools.count(1)          # 이벤트 세대 번호(계측용)
        self._ev_now = 0

    def _on_changed(self):
        self._ev_now = next(self._ev)
        perf.mark(self._ev_now, "clipboard_event")
        if self.cfg["clipboard_paused"]:
            return
        self._timer.start()

    def _handle(self):
        rid = self._ev_now
        perf.mark(rid, "read_start")
        try:
            text = self.clip.text()
        except Exception as e:
            _dbg("clip.text error:", e)
            perf.mark(rid, "read_fail")
            return
        perf.mark(rid, "read_end", n=len(text or ""))
        if not text or len(text) > 500_000:
            return
        now = time.time()
        h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        if now - _self_copy["t"] < 1.0 and h == _self_copy["h"]:
            return  # 우리 프로그램이 복사한 것
        cites = refparse.parse(text, prev_law=self.cfg.get("last_law") or "")
        perf.mark(rid, "parse_end", cites=len(cites))
        if cites:
            self.citation.emit({"cites": cites, "text": text, "rid": rid})
