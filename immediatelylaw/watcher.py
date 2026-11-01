# -*- coding: utf-8 -*-
"""클립보드 감시. 복사 이벤트가 오면 다음 이벤트 루프에서 즉시 인용을 파싱해 알림.

- 정상 복사는 고정 대기가 없다: dataChanged → singleShot(0) 예약(같은 루프 내
  중복 알림은 하나의 읽기로 병합) → 읽기.
- 읽기 실패/일시적 빈 값만 제한 재시도(15→35→75ms). 의도적 '전체 선택 삭제'로
  빈 클립보드가 남을 수 있으므로 무한 재시도는 하지 않는다.
- generation(세대) 번호로 이전 복사의 지연 재시도가 최신 결과를 덮지 않게 한다.
- 모든 재시도는 이벤트 루프 타이머로만 동작하며 GUI 스레드 밖으로 나가지 않는다.
"""
import hashlib
import os
import time

from PySide6.QtCore import QObject, QTimer, Signal

from . import perf, refparse

_self_copy = {"t": 0.0, "h": ""}   # monotonic 기준 — 부팅 이후 경과시계
DEBUG_LOG = os.environ.get("IMMEDIATELYLAW_DEBUG_LOG", "")
RETRY_MS = (15, 35, 75)            # 읽기 실패/공백 재시도 사다리(합계 125ms)


def _dbg(*a):
    if DEBUG_LOG:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(" ".join(str(x) for x in a) + "\n")


def note_self_copy(text: str):
    _self_copy["t"] = time.monotonic()
    _self_copy["h"] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


class ClipboardWatcher(QObject):
    """text가 클립보드에 들어오면 인용 후보를 분석해 citation 신호를 낸다.
    citation payload: {"cites":[...], "text":str, "rid":세대번호}"""
    citation = Signal(dict)

    def __init__(self, clipboard, cfg, parent=None):
        super().__init__(parent)
        self.clip = clipboard
        self.cfg = cfg
        self.clip.dataChanged.connect(self._on_changed)
        self._gen = 0            # 복사 세대: dataChanged마다 증가
        self._scheduled = False  # 다음 루프 읽기 예약 병합용
        self._retry_left = 0     # 현 세대에 남은 재시도 허용치

    # ---------- 이벤트 진입 ----------
    def _on_changed(self):
        if self.cfg["clipboard_paused"]:
            return
        self._gen += 1
        self._retry_left = len(RETRY_MS)
        perf.mark(self._gen, "clipboard_event")
        if not self._scheduled:
            self._scheduled = True
            QTimer.singleShot(0, self._next_loop_read)

    def _next_loop_read(self):
        # 같은 루프에서 여러 번 온 알림은 이 한 번의 읽기로 합쳐진다.
        self._scheduled = False
        self._try_read(self._gen, first=True)

    def _retry_read(self, gen: int):
        if gen != self._gen:           # 새 복사가 이미 도착 — 구세대 폐기
            return
        if self._retry_left <= 0:
            perf.mark(gen, "read_giveup")
            return
        self._retry_left -= 1
        idx = len(RETRY_MS) - self._retry_left - 1
        QTimer.singleShot(RETRY_MS[min(idx, len(RETRY_MS) - 1)],
                          lambda: self._try_read(gen, first=False))

    # ---------- 읽기/판석 ----------
    def _try_read(self, gen: int, first: bool):
        if gen != self._gen and not first:
            return                     # 구세대 재시도는 조용히 폐기
        if gen != self._gen:
            gen = self._gen            # 같은 루프 병합: 최신 세대를 읽는다
        if self.cfg["clipboard_paused"]:   # 읽기 직전 재검사
            return
        perf.mark(gen, "read_start")
        try:
            text = self.clip.text()
        except Exception as e:
            _dbg("clip.text error:", e)
            perf.mark(gen, "read_fail")
            self._retry_read(gen)
            return
        perf.mark(gen, "read_end", n=len(text or ""))
        if not text:
            # 지연 제공(delayed render) 가능성: 사다리(15/35/75ms) 소진까지 재시도
            self._retry_read(gen)
            return
        if len(text) > 500_000:
            return
        now = time.monotonic()
        h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        if now - _self_copy["t"] < 1.0 and h == _self_copy["h"]:
            return  # 우리 프로그램이 복사한 것
        cites = refparse.parse(text, prev_law=self.cfg.get("last_law") or "")
        perf.mark(gen, "parse_end", cites=len(cites))
        if cites:
            self.citation.emit({"cites": cites, "text": text, "rid": gen})
