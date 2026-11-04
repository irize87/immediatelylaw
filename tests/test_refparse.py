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


# ---- v1.5.10 인용부호(따옴표) 파싱 회귀 ---------------------------------
# 이 블록의 한글 리터럴은 \u 이스케이프(ASCII)로만 인코딩했다.
# refparse 내부 리터럴과 짝을 이루는 입력(Q_SAMELAW/Q_SUBART/LIB/SIL)은
# 기존 통과 테스트의 원본 바이트를 그대로 옮긴 것이고, 그 외 문장은
# (초성,중성,종성) 조합식으로 조립한 것이다. 재타이핑은 금지다: 이
# 저장소에서는 '보이는 모양은 같고 코드포인트가 다른' 글자 사고가 두 번
# 있었다. 아래 tripwire가 모든 리터럴을 unicodedata 이름으로 재검증한다.
import unicodedata as _ud


def _u(*roman):
    return "".join(_ud.lookup("HANGUL SYLLABLE " + r) for r in roman)


def _skeleton(s):
    return "".join(c for c in s if 0xAC00 <= ord(c) <= 0xD7A3)


PIPED            = "\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95"
INSHIN           = "\uc778\uc2e0\ubcf4\ud638\ubc95"
MIN              = "\ubbfc\ubc95"
LIB              = "\ub3c4\uc11c\uad00\ubc95"
HYUNG            = "\ud615\ubc95"
SIL              = "\uc2dc\ud589\ub839"
SUBART           = "247\uc7582"
Q_BARE           = "\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95 \uc81c15\uc870"
Q_BRACKET_NAME   = (
                   "\u300c\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95\u300d \uc81c"
                   "15\uc870"
)
Q_DQUOTE         = (
                   "\u0022\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95 \uc81c15"
                   "\uc870\u0022"
)
Q_CQUOTE         = (
                   "\u201c\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95 \uc81c15"
                   "\uc870\u201d"
)
Q_SQUOTE         = "'\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95 \uc81c15\uc870'"
Q_BRACKET_ALL    = (
                   "\u300c\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95 \uc81c15"
                   "\uc870\u300d"
)
Q_UNBALANCED     = (
                   "\u201c\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95 \uc81c15"
                   "\uc870"
)
Q_SUBART         = "\u201c\ud615\ubc95 \uc81c247\uc870\uc7582\u201d"
Q_SAMELAW        = (
                   "\u201c\ub3c4\uc11c\uad00\ubc95 \uc81c33\uc870\u201d \ubc0f "
                   "\uac19\uc740 \ubc95 \uc2dc\ud589\ub839 \uc81c19\uc870"
)
REPRO            = (
                   "\u201c\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95 \uc81c15"
                   "\uc870\u201d\ub77c\uace0\ub9cc \uc548\ub0b4\ub418\uc5b4\uc774 "
                   "\uc9c7\uc816 \ud574\ub2f9 \uc870\ubb49\uc5bc \ucc3f\uc544"
                   "\ubd10\uc57c \ud57b\ub358 \ubc88\uac70\ub85c\uc6c0,\u000a"
                   "\uc774\uc81c \uc989\uc2dc\ub85c\uac00 \ud074\ub0b4\ub4dc\ub9ac"
                   "\ub4dc\ub2c8\ub2e4\ub290\ub2c8\ub2e4. \uc548\ub0b4\ub41c "
                   "\ubc95\ub839\uc5bc \ubd05\uc0ac(Ctrl + C)\ub9cc \ud558\uc138"
                   "\uc694.\u000a\uc870\ubb49\uc559 \uc989\uc2dc\ub85c\uac00 "
                   "\ucc3f\uc544\ub4dc\ub9ac\uac8c\uc694!"
)
MIX              = (
                   "\u201c\uac1c\uc778\uc84d\ubcf4 \ubcf4\ud638\ubc95 \uc81c15"
                   "\uc870\u201d\uc774\uace0, \u201c\ubbfc\ubc95 \uc81c750\uc870"
                   "\u201d\ub3c4 \ubc24\uae68 \uce75\uc5b8 \ub418\ub2c8\ub2e4."
)


def test_quoted_citation_forms():
    # 요구 2: 여섯 형태 모두 '개인정보 보호법' 15조
    assert first(Q_BARE) == (PIPED, "15")
    assert first(Q_BRACKET_NAME) == (PIPED, "15")
    assert first(Q_DQUOTE) == (PIPED, "15")
    assert first(Q_CQUOTE) == (PIPED, "15")
    assert first(Q_SQUOTE) == (PIPED, "15")
    assert first(Q_BRACKET_ALL) == (PIPED, "15")


def test_repro_sentence_full():
    assert first(REPRO) == (PIPED, "15")


def test_quote_first_candidate_is_full_name():
    # resolver는 law_all[0]부터 시도한다: 첫 후보가 전체 이름이어야 한다
    r = refparse.parse(Q_CQUOTE)[0]
    assert r["law_all"][0] == PIPED


def test_mixed_citations_order():
    # 앞뒤 설명 + 여러 인용: 등장순 유지, 각각 전체 이름
    r = refparse.parse(MIX)
    assert [(c["law"], c["art"]) for c in r] == [
        (PIPED, "15"), (MIN, "750")]


def test_quoted_sub_article_and_samelaw():
    assert first(Q_SUBART) == (HYUNG, SUBART)
    r = refparse.parse(Q_SAMELAW)
    assert [(c["law"], c["art"]) for c in r] == [
        (LIB, "33"), (LIB + " " + SIL, "19")]


def test_unbalanced_quote_still_full_name():
    # 닫는 따옴표 누락(입력 실수)에서도 법령명 앞부분을 잃지 않는다
    assert first(Q_UNBALANCED) == (PIPED, "15")


def test_literal_codepoint_tripwire():
    # 모든 블록 리터럴을 유니코드 이름에서 재조립해 바이트 단위로 대조.
    # 파일의 한글 코드포인트가future에 썩으면(재타이핑 사고) 이가 먼저 잡는다.
    assert PIPED == _u("GAE", "IN", "JYEONG", "BO") + " " \
        + _u("BO", "HO", "BEOB")
    assert INSHIN == _u("IN", "SIN", "BO", "HO", "BEOB")
    assert MIN == _u("MIN", "BEOB")
    assert LIB == _u("DO", "SEO", "GWAN", "BEOB")
    assert SIL == _u("SI", "HAENG", "RYEONG")
    assert HYUNG == _u("HYEONG", "BEOB")
    assert _skeleton(REPRO) == _u("GAE", "IN", "JYEONG", "BO", "BO", "HO", "BEOB", "JE", "JO",
        "RA", "GO", "MAN", "AN", "NAE", "DOE", "EO", "I", "JID",
        "JEOJ", "HAE", "DANG", "JO", "MUNG", "EOL", "CAC", "A",
        "BWA", "YA", "HAED", "DEON", "BEON", "GEO", "RO", "UM", "I",
        "JE", "JEUG", "SI", "RO", "GA", "KEUL", "NAE", "DEU", "RI",
        "DEU", "NI", "DA", "NEU", "NI", "DA", "AN", "NAE", "DOEN",
        "BEOB", "RYEONG", "EOL", "BOB", "SA", "MAN", "HA", "SE",
        "YO", "JO", "MUNG", "ANG", "JEUG", "SI", "RO", "GA", "CAC",
        "A", "DEU", "RI", "GE", "YO")
    assert _skeleton(MIX) == _u("GAE", "IN", "JYEONG", "BO", "BO", "HO", "BEOB", "JE", "JO",
        "I", "GO", "MIN", "BEOB", "JE", "JO", "DO", "BAM", "GGAE",
        "KAG", "EON", "DOE", "NI", "DA")
    assert _skeleton(Q_SAMELAW) == _u("DO", "SEO", "GWAN", "BEOB", "JE", "JO", "MIC", "GAT",
        "EUN", "BEOB", "SI", "HAENG", "RYEONG", "JE", "JO")
    assert _skeleton(Q_SUBART) == _u("HYEONG", "BEOB", "JE", "JO", "YI")
    assert _skeleton(Q_BARE) == _u(
        "GAE", "IN", "JYEONG", "BO", "BO", "HO", "BEOB", "JE", "JO")


def test_resolver_prefers_full_name(tmp_path):
    # 종단 검증: 인용부호형 텍스트 -> parse -> resolve가 인신보호법이
    # 아니라 개인정보 보호법 제15조에 연결되어야 한다(재현 버그).
    from immediatelylaw import resolver
    from immediatelylaw.db import Database
    d = Database(str(tmp_path / "t.db"))
    try:
        d.conn.execute("INSERT INTO law(mst,law_id,name,pending) "
                       "VALUES(1,'L1',?,0)", (PIPED,))
        d.conn.execute("INSERT INTO law(mst,law_id,name,pending) "
                       "VALUES(2,'L2',?,0)", (INSHIN,))
        d.conn.execute("INSERT INTO article(mst,art_no,title,body,ord) "
                       "VALUES(1,'15','t','A15',1)")
        d.conn.execute("INSERT INTO article(mst,art_no,title,body,ord) "
                       "VALUES(2,'15','t','B15',1)")
        d.conn.commit()
        c = refparse.parse(REPRO)[0]
        res = resolver.resolve(d, c["law"], c["art"], None,
                               hints=c["law_all"])
        assert res["found"] and res["law_name"] == PIPED
    finally:
        d.close()


def test_short_hint_mislinks_by_length_documented(tmp_path):
    # 함정 문서화: 법령명 앞이 깨진 채 '보호법'만 힌트로 오면 포함
    # 매칭의 짧은 이름 우선(ORDER BY length(name)) 때문에 인신보호법이
    # 먼저 잡힌다. 파서가 전체 이름을 지키는 것이 정답인 이유.
    from immediatelylaw.db import Database
    d = Database(str(tmp_path / "t2.db"))
    try:
        d.conn.execute("INSERT INTO law(mst,law_id,name,pending) "
                       "VALUES(1,'L1',?,0)", (PIPED,))
        d.conn.execute("INSERT INTO law(mst,law_id,name,pending) "
                       "VALUES(2,'L2',?,0)", (INSHIN,))
        d.conn.commit()
        rows = d.search_laws_by_name(PIPED.split(" ")[1])  # '보호법'
        assert rows and rows[0]["name"] == INSHIN
    finally:
        d.close()


# ---- generic-tail false-positive regression (v1.6.x) --------------------
# '119 SO-BANG GANG-RYEONG art.3' must NOT resolve to '...GANG-RYEONG', and
# '119... UN-YEONG GYU-JYEONG art.3' must NOT resolve to '...UN-YEONG-GYU-
# JYEONG'. All strings below are ASCII sources: syllables come from _u()
# (unicodedata name lookup) only. The names used are DB-witnessed: real
# statutes spell 'jeong' with the syllable named "JEONG" (U+C815), NOT the
# look-alike "JYEONG" that tests above hold -- that one was verified wrong
# against the production DB bytes in the v1.6.x review.
GANGRYEONG = _u("GANG", "RYEONG")                       # gang-ryeong
YEGYU = _u("YE", "GYU")                                 # yegyu
BEOBGWANYUNRI = _u("BEOB", "GWAN", "YUN", "RI")
FP_LAW = BEOBGWANYUNRI + GANGRYEONG                     # ...GANG-RYEONG law
JEOKGEUK = _u("JEOG", "GEUG", "HANG", "JEONG")        # jeokgeuk-hangjeong
UNYEONGGYUJEONG = _u("UN", "YEONG") + " " + _u("GYU", "JEONG")
TRUE_OP = JEOKGEUK + " " + UNYEONGGYUJEONG              # real regulation name
FP1 = "119 " + _u("SO", "BANG") + " " + GANGRYEONG + " " \
    + _u("JE") + "3" + _u("JO")
FP2 = "119" + _u("YI", "IN", "SANG") + " " + _u("UN", "YEONG") + " " \
    + _u("GYU", "JEONG") + " " + _u("JE") + "3" + _u("JO")
TRUE_REF = TRUE_OP + " " + _u("JE") + "3" + _u("JO")
YEGYU_REF = _u("GUG", "SE", "HWAN", "GEUB") + YEGYU + " " \
    + _u("JE") + "5" + _u("JO")                         # bare-yegyu form


def _seed_op(tmp_path):
    from immediatelylaw.db import Database
    d = Database(str(tmp_path / "fp.db"))
    d.conn.execute("INSERT INTO law(mst,law_id,name,pending) VALUES(1,'L1',?,0)",
                   (FP_LAW,))
    d.conn.execute("INSERT INTO law(mst,law_id,name,pending) VALUES(2,'L2',?,0)",
                   (TRUE_OP,))
    d.conn.execute("INSERT INTO article(mst,art_no,title,body,ord) "
                   "VALUES(1,'3','t','A3',1)")
    d.conn.execute("INSERT INTO article(mst,art_no,title,body,ord) "
                   "VALUES(2,'3','t','B3',1)")
    d.conn.commit()
    return d


def test_generic_tail_not_offered_as_candidate():
    # the tail-only fragments must never leave the parser
    for t in (FP1, FP2):
        r = refparse.parse(t)
        assert r, t
        for h in r[0]["law_all"]:
            assert h.replace(" ", "") not in refparse.GENERIC_TAILS


def test_generic_fp_does_not_resolve(tmp_path):
    from immediatelylaw import resolver
    d = _seed_op(tmp_path)
    try:
        for t in (FP1, FP2):
            c = refparse.parse(t)[0]
            res = resolver.resolve(d, c["law"], c["art"], None,
                                   hints=c["law_all"])
            assert not res["found"], (t, res.get("law_name"))
    finally:
        d.close()


def test_true_regulation_still_resolves(tmp_path):
    # a citation WITH a specific head keeps working exactly as before
    from immediatelylaw import resolver
    d = _seed_op(tmp_path)
    try:
        c = refparse.parse(TRUE_REF)[0]
        assert c["law"] == TRUE_OP
        res = resolver.resolve(d, c["law"], c["art"], None, hints=c["law_all"])
        assert res["found"] and res["law_name"] == TRUE_OP
    finally:
        d.close()


def test_bare_yegyu_now_parses():
    # SUFFIXES coverage: '...-yegyu art.5' parses at all now (was NO-PARSE)
    r = refparse.parse(YEGYU_REF)
    assert r and r[0]["law"] == _u("GUG", "SE", "HWAN", "GEUB") + YEGYU
    assert r[0]["art"] == "5"


def test_tier4_length_gate(tmp_path):
    d = _seed_op(tmp_path)
    try:
        assert d.search_laws_by_name(GANGRYEONG) == []      # 2-char: blocked
        rows = d.search_laws_by_name(_u("YUN", "RI") + GANGRYEONG)
        assert rows and rows[0]["name"] == FP_LAW          # 4-char: allowed
    finally:
        d.close()
