# -*- coding: utf-8 -*-
"""ClipboardWatcher 회귀 테스트(가짜 클립보드, Qt 신호 기준).

시간 판정은 느슨하게 잡는다(OS 스케줄링). 기준 동작은 '발생 여부와 개수'다.
즉시 처리(0ms 예약)·재시도 사다리 관련 신규 동작 테스트는 watcher 개선 커밋에서 추가.
"""
import time

import pytest
from PySide6.QtCore import QObject, Signal

from immediatelylaw import watcher as wmod
from immediatelylaw.watcher import ClipboardWatcher, note_self_copy


class FakeClipboard(QObject):
    """text()가 각본 목록을 하나씩 소비하는 클립보드."""
    dataChanged = Signal()

    def __init__(self, script=None):
        super().__init__()
        self.script = list(script or [])

    def text(self):
        if self.script:
            item = self.script.pop(0)
        else:
            item = ""
        if isinstance(item, Exception):
            raise item
        return item

    def push(self, value):
        """새 복사를 시뮬레이션: 값 넣고 dataChanged."""
        self.script.append(value)
        self.dataChanged.emit()


@pytest.fixture
def cfg():
    return {"clipboard_paused": False, "last_law": ""}


def test_normal_copy_emits(qtbot, cfg):
    clip = FakeClipboard(["민법 제750조"])
    w = ClipboardWatcher(clip, cfg)
    with qtbot.waitSignal(w.citation, timeout=1000):
        clip.dataChanged.emit()


def test_same_loop_events_merge(qtbot, cfg):
    """같은 이벤트 루프의 중복 알림은 조회 1회로 합쳐야 한다."""
    clip = FakeClipboard(["민법 제750조"])
    w = ClipboardWatcher(clip, cfg)
    hits = []
    w.citation.connect(hits.append)
    clip.dataChanged.emit()
    clip.dataChanged.emit()
    clip.dataChanged.emit()
    qtbot.wait(600)
    assert len(hits) == 1


def test_recopy_same_text_reopens(qtbot, cfg):
    """같은 조문을 다시 복사하면 카드는 다시 열려야 한다(장기 중복억제 금지)."""
    clip = FakeClipboard(["민법 제750조", "민법 제750조"])
    w = ClipboardWatcher(clip, cfg)
    hits = []
    w.citation.connect(hits.append)
    clip.dataChanged.emit()
    qtbot.wait(400)
    clip.dataChanged.emit()
    qtbot.wait(400)
    assert len(hits) == 2


def test_self_copy_suppressed(qtbot, cfg):
    """앱이 스스로 복사 버튼으로 복사한(note_self_copy) 직후 조회 반복 금지."""
    text = "민법 제750조 고의 또는 과실로…"
    note_self_copy(text)
    clip = FakeClipboard([text])
    w = ClipboardWatcher(clip, cfg)
    hits = []
    w.citation.connect(hits.append)
    clip.dataChanged.emit()
    qtbot.wait(500)
    assert hits == []


def test_empty_and_huge_and_error(qtbot, cfg):
    clip = FakeClipboard(["", "가" * 500_001, RuntimeError("clip busy")])
    w = ClipboardWatcher(clip, cfg)
    hits = []
    w.citation.connect(hits.append)
    for _ in range(3):
        clip.dataChanged.emit()
        qtbot.wait(300)
    assert hits == []


def test_paused_ignores(qtbot, cfg):
    cfg["clipboard_paused"] = True
    clip = FakeClipboard(["민법 제750조"])
    w = ClipboardWatcher(clip, cfg)
    hits = []
    w.citation.connect(hits.append)
    clip.dataChanged.emit()
    qtbot.wait(400)
    assert hits == []


def test_citation_payload(qtbot, cfg):
    clip = FakeClipboard(["「형법」 제23조"])
    w = ClipboardWatcher(clip, cfg)
    with qtbot.waitSignal(w.citation, timeout=1000) as sig:
        clip.dataChanged.emit()
    payload = sig.args[0]
    assert payload["cites"][0]["law"] == "형법"
    assert payload["cites"][0]["art"] == "23"
    assert isinstance(payload.get("rid"), int)
