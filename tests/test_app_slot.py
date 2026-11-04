# -*- coding: utf-8 -*-
"""App._on_citation 슬롯 스모크 테스트.

Qt 위젯을 전부 띄우지 않고 인스턴스를 합성해, 슬롯 본문 자체(임포트·호출
조합)가 도중에 죽지 않는지 확인한다. 계측 작업 중 슬롯 내부 NameError로
조용히 죽었던 사고에 대한 방어선이다.
"""
from types import SimpleNamespace

from immediatelylaw.app import ImmediatelyLaw


def make_stub(found_article=None):
    """ImmediatelyLaw 인스턴스를 우회 생성해 슬롯이 쓰는 속성만 채운다."""
    stub = ImmediatelyLaw.__new__(ImmediatelyLaw)
    calls = []

    class OverlayStub:
        def show_results(self, res_list, note="", rid=0):
            calls.append(("show", len(res_list), rid))

        def set_state(self, text):
            calls.append(("state", text))

        def lb_title(self):
            pass

        def isVisible(self):
            return True

    class DbStub:
        def meta(self):
            return {}

    stub.db = DbStub()
    stub.cfg = {"last_law": "민법", "verify_enabled": False}
    stub.overlay = OverlayStub()
    stub.api = None
    stub._workers = []

    import immediatelylaw.resolver as rs
    orig = rs.resolve

    def fake_resolve(db, law, art, api, hints=None, auto=None):
        if found_article is None:
            return {"found": False}
        return {"found": True, "law_name": law, "art_no": art,
                "title": "", "body": "본문", "source": "local"}

    rs.resolve = fake_resolve
    return stub, calls, orig


def teardown_original(orig):
    import immediatelylaw.resolver as rs
    rs.resolve = orig


def test_slot_shows_found_article():
    from immediatelylaw import refparse
    stub, calls, orig = make_stub(found_article=True)
    try:
        cites = refparse.parse("「민법」 제750조")
        stub._on_citation({"cites": cites, "text": "x", "rid": 42})
        assert calls and calls[0][0] == "show"
        assert calls[0][2] == 42          # rid가 오버레이까지 전달된다
    finally:
        teardown_original(orig)


def test_slot_notfound_no_api_shows_state():
    from immediatelylaw import refparse
    stub, calls, orig = make_stub(found_article=None)

    class Overlay2:
        def __init__(self):
            class LB:
                def setText(self, t):
                    calls.append(("title", t))
            self.lb_title = LB()

        def set_badge(self, k, t="", tip=""):
            calls.append(("badge", k))

        def set_state(self, text):
            calls.append(("state", text))

        def isVisible(self):
            return True

    stub.overlay = Overlay2()
    try:
        cites = refparse.parse("「존재않는법」 제1조")
        stub._on_citation({"cites": cites, "text": "x", "rid": 7})
        kinds = [c[0] for c in calls]
        assert "title" in kinds and "state" in kinds
    finally:
        teardown_original(orig)


def test_slot_empty_cites_noop():
    stub, calls, orig = make_stub()
    try:
        stub._on_citation({"cites": [], "text": "", "rid": 0})
        assert calls == []
    finally:
        teardown_original(orig)
