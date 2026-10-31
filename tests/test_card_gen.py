# -*- coding: utf-8 -*-
"""카드 세대(generation) 보호 회귀 테스트.

늦게 도착한 검증/라이브 결과가 이미 바뀐 카드에 배지를 찍지 못하게 하는
3단계.fix의 동작을 고정한다."""
from immediatelylaw.app import ImmediatelyLaw
from immediatelylaw.overlay import OverlayCard


def gen_stub(overlay_gen):
    """ImmediatelyLaw 인스턴스 우회 생성 — 검증 콜백이 쓰는 것만 채운다."""
    stub = ImmediatelyLaw.__new__(ImmediatelyLaw)
    calls = []
    box = {"gen": overlay_gen}

    class Ov:
        def card_gen(self):
            return box["gen"]

        def set_badge(self, k, t="", tip=""):
            calls.append(("badge", k, t))

        def set_state(self, s):
            calls.append(("state", s))

        def show_result(self, res, note="", rid=0):
            calls.append(("show", res.get("law_name")))

    stub.overlay = Ov()
    stub.cfg = {"last_law": "민법"}     # _remember_law의 save() 경로 회피
    stub._workers = []
    return stub, calls, box


def test_verified_from_stale_generation_discarded():
    stub, calls, box = gen_stub(overlay_gen=7)
    ImmediatelyLaw._on_verified(stub, 6, "current", "")   # 옛 카드의 결과
    assert calls == []


def test_verified_from_current_generation_applied():
    stub, calls, box = gen_stub(overlay_gen=7)
    ImmediatelyLaw._on_verified(stub, 7, "current", "")
    assert ("badge", "current", "현행") in calls


def test_live_resolve_stale_discarded():
    stub, calls, box = gen_stub(overlay_gen=3)
    res = {"found": True, "law_name": "민법", "art_no": "750",
           "title": "", "body": "본문", "source": "live"}
    ImmediatelyLaw._on_live_resolved(stub, 2, res)
    assert calls == []


def test_live_resolve_current_applied():
    stub, calls, box = gen_stub(overlay_gen=3)
    res = {"found": True, "law_name": "민법", "art_no": "750",
           "title": "", "body": "본문", "source": "live"}
    ImmediatelyLaw._on_live_resolved(stub, 3, res)
    assert ("show", "민법") in calls


def test_card_gen_increments_per_show(qtbot):
    cfg = {"overlay_width": 520, "font_pt": 11, "theme": "light",
           "overlay_corner": "top-right", "auto_hide_sec": 0}
    card = OverlayCard(cfg)
    qtbot.addWidget(card)
    card._place_and_show = lambda: None     # 실제 표시(화면 노출) 생략
    res = {"found": True, "source": "local", "law_name": "민법",
           "art_no": "750", "title": "불법행위", "chap": "", "body": "본문",
           "pending": 0}
    g0 = card.card_gen()
    card.show_results([res])
    card.show_results([res])
    assert card.card_gen() == g0 + 2


def test_verify_start_stamps_card_generation(qtbot):
    """_start_verify는 표시 시점의 세대를 워커 콜백에 못 박는다(실배선 검증)."""
    stub, calls, box = gen_stub(overlay_gen=11)
    stub.cfg = {"verify_enabled": True, "last_law": ""}
    stub.db = None
    stub.api = None
    started = {}

    import immediatelylaw.app as appmod

    class FakeWorker:
        class _Sig:
            def connect(self, fn):
                started["fn"] = fn

        def __init__(self, *a, **k):
            self.done = FakeWorker._Sig()

        def start(self):
            started["started"] = True

    orig = appmod.VerifyWorker
    appmod.VerifyWorker = FakeWorker
    try:
        stub._start_verify({"law_name": "민법", "art_no": "750"})
        assert started.get("started")
        box["gen"] = 12                    # 그사이에 새 조문이 표시됨
        started["fn"]("current", "일치")   # 늦은 결과 도착
        assert calls == []                 # 폐기되어야 한다
        box["gen"] = 11                    # 세대를 되돌려 재확인 → 적용됨
        started["fn"]("current", "일치")
        assert calls
    finally:
        appmod.VerifyWorker = orig
