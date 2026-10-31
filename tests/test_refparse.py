# -*- coding: utf-8 -*-
"""refparse 회귀 특성화 테스트. 기준값은 변경 전 실제 출력으로 고정했다.
성능 작업 중 파싱 결과가 달라지면 이 테스트가 먼저 잡는다."""
from immediatelylaw import refparse


def first(t, prev=""):
    r = refparse.parse(t, prev_law=prev)
    assert r, f"인용을 찾지 못함: {t!r}"
    return r[0]["law"], r[0]["art"]


def test_bare_name():
    assert first("개인정보 보호법 제15조") == ("개인정보 보호법", "15")


def test_bracket_name():
    assert first("「개인정보 보호법」 제15조") == ("개인정보 보호법", "15")


def test_minp():
    assert first("민법 제750조") == ("민법", "750")


def test_hyung():
    assert first("형법 제23조") == ("형법", "23")


def test_constitution_words():
    # 파싱 단계에서는 입력 문자열 그대로; 헌법→대한민국헌법 치환은 resolver 소관
    assert first("헌법 제11조")[0] == "헌법"
    assert first("대한민국헌법 제31조") == ("대한민국헌법", "31")


def test_law_and_decree_group():
    r = refparse.parse("도서관법 제33조 및 같은 법 시행령 제19조")
    assert [(c["law"], c["art"]) for c in r] == [
        ("도서관법", "33"), ("도서관법 시행령", "19")]


def test_sub_article():
    assert first("형법 제247조의2") == ("형법", "247의2")


def test_prev_law_context():
    assert first("같은 법 제5조", prev="도서관법") == ("도서관법", "5")
    assert first("동법 제5조", prev="도서관법") == ("도서관법", "5")
    assert first("같은 법 시행령 제19조", prev="도서관법") == \
        ("도서관법 시행령", "19")


def test_citation_inside_sentence():
    r = refparse.parse(
        "위 사항에 대하여 「건축법」 제11조 및 같은 법 시행령 제6조에 따라 "
        "처리한다.")
    assert [(c["law"], c["art"]) for c in r] == [
        ("건축법", "11"), ("건축법 시행령", "6")]


def test_unknown_law_still_parses():
    # 파싱은 사전 검증 없이 인용만 추출 — 찾을 수 없음 판정은 resolver/DB가 한다
    assert first("존재하지않는법령 제999조") == ("존재하지않는법령", "999")


def test_no_citation_plain_text():
    assert refparse.parse("오늘 회의는 3시로 변경되었습니다.") == []
