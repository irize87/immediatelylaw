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
        """새 복사를 시뮬레이션: 갑 넣고 dataChanged."""
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


# ---------- 2단계: 즉시 처리·재시도 사다리·세대 보호 ----------

def test_response_is_immediate(qtbot, cfg):
    """고정 대기가 있으면 안 된다: 복사→ 알림이 옛 120ms 디바운스보다 훨씬 빨라야 한다."""
    import time as _t
    clip = FakeClipboard(["민법 제750조"])
    w = ClipboardWatcher(clip, cfg)
    t0 = _t.perf_counter()
    with qtbot.waitSignal(w.citation, timeout=1000):
        clip.dataChanged.emit()
    dt = (_t.perf_counter() - t0) * 1000
    assert dt < 80, f"응답 지연 {dt:.0f}ms — 즉시 처리로 회귀했다"


def test_transient_error_recovers_via_ladder(qtbot, cfg):
    """일시적 읽기 실패는 재시도 사다리 안에서 복구한다."""
    clip = FakeClipboard([RuntimeError("clip busy"), "민법 제750조"])
    w = ClipboardWatcher(clip, cfg)
    with qtbot.waitSignal(w.citation, timeout=1000):
        clip.dataChanged.emit()


def test_empty_then_text_recovers(qtbot, cfg):
    """지연 제공(delayed render): 첫 읽기가 비었다가 조금 뒤 들어온 복사도 잡는다."""
    clip = FakeClipboard(["", "형법 제23조"])
    w = ClipboardWatcher(clip, cfg)
    with qtbot.waitSignal(w.citation, timeout=1000) as sig:
        clip.dataChanged.emit()
    assert sig.args[0]["cites"][0]["law"] == "형법"


def test_retry_ladder_gives_up(qtbot, cfg):
    """빈 클립드는 사다리(합계 125ms)만큼만 읽고 포기 — 무한 재시도 금지."""
    clip = FakeClipboard(["", "", "", "", "형법 제23조"])
    w = ClipboardWatcher(clip, cfg)
    hits = []
    w.citation.connect(hits.append)
    clip.dataChanged.emit()
    qtbot.wait(500)
    assert hits == []
    assert len(clip.script) == 1          # 최초 1회+재시도 3회만 읽고 멈췄다
    with qtbot.waitSignal(w.citation, timeout=1000):
        clip.push("민법 제750조")           # 새 세대는 정상 동작


def test_stale_generation_retry_not_read(qtbot, cfg):
    """구세대 재시도는 읽기 자체를 하지 않는다 — 최신 복사를 덮을 수 없다."""
    clip = FakeClipboard(["민법 제750조"])
    reads = []
    orig = clip.text

    def spy():
        reads.append(1)
        return orig()

    clip.text = spy
    w = ClipboardWatcher(clip, cfg)
    w._gen = 10
    w._try_read(9, first=False)            # A복사의 지연 재시도 도착
    qtbot.wait(60)
    assert reads == []
