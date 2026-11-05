# -*- coding: utf-8 -*-
"""refparse 회귀 특성화 테스트. 기준갑은 변경 전 실제 출력으로 고정했다.
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


# ---- G1..G7 policy regression (design review 2026-11-05) -----------------
# All syllables again strictly from the DB-witnessed name set.
GUGSE = _u("GUG", "SE")                    # gug-se
GYUJEONG = _u("GYU", "JEONG")
NAME_A = GUGSE + GANGRYEONG                # has art 1, NOT art 3
NAME_B = GUGSE + _u("YUN", "RI") + GANGRYEONG   # has art 3
BEOB = _u("BEOB")                          # beob (law suffix)


def _seed_two(tmp_path):
    from immediatelylaw.db import Database
    d = Database(str(tmp_path / "g.db"))
    d.conn.execute("INSERT INTO law(mst,law_id,name,pending) VALUES(1,'L1',?,0)",
                   (NAME_A,))
    d.conn.execute("INSERT INTO law(mst,law_id,name,pending) VALUES(2,'L2',?,0)",
                   (NAME_B,))
    d.conn.execute("INSERT INTO article(mst,art_no,title,body,ord) "
                   "VALUES(1,'1','t','A1',1)")
    d.conn.execute("INSERT INTO article(mst,art_no,title,body,ord) "
                   "VALUES(2,'3','t','B3',1)")
    d.conn.commit()
    return d


def test_g4_no_article_never_substitutes(tmp_path):
    # NAME_A matches exactly but has no art 3; NAME_B would match via the
    # short second hint. The design: stop -- never borrow another law's art.
    from immediatelylaw import resolver
    d = _seed_two(tmp_path)
    try:
        res = resolver.resolve(d, NAME_A, "3", None,
                               hints=[NAME_A, _u("YUN", "RI") + GANGRYEONG])
        assert not res["found"]
        assert res.get("reason") == "law_no_article"
        assert res.get("law_name") == NAME_A
    finally:
        d.close()


def test_g3_g6_containment_last_and_low_conf(tmp_path):
    # without an exact hit the containment tier still works, flagged low
    from immediatelylaw import resolver
    d = _seed_two(tmp_path)
    try:
        res = resolver.resolve(d, _u("YUN", "RI") + GANGRYEONG, "3", None,
                               hints=[_u("YUN", "RI") + GANGRYEONG])
        assert res["found"] and res["law_name"] == NAME_B
        assert res.get("low_conf") is True
        from immediatelylaw import resolver as R
        kind, msg = R.verify(d, None, res)
        assert kind == "check"
    finally:
        d.close()


def test_g1_like_wildcards_are_literal(tmp_path):
    # % and _ coming from clipboard text must not act as LIKE wildcards
    from immediatelylaw.db import Database
    d = Database(str(tmp_path / "esc.db"))
    for mst, nm in ((1, "A_B" + BEOB), (2, "A%B" + BEOB), (3, "XAxB" + BEOB)):
        d.conn.execute(
            "INSERT INTO law(mst,law_id,name,pending) "
            "VALUES(?, 'E' || ?, ?, 0)", (mst, mst, nm))
    d.conn.commit()
    try:
        got = [r["name"] for r in d.search_laws_contains("A%B")]
        assert got == ["A%B" + BEOB]
        got = [r["name"] for r in d.search_laws_contains("A_B")]
        assert got == ["A_B" + BEOB]
        assert d.search_laws_contains("XA_B") == []   # _ must not match x
    finally:
        d.close()


def test_g2_api_no_first_hit_fallback():
    # resolve_current must answer None unless name/short match exactly
    from immediatelylaw import lawapi
    api = object.__new__(lawapi.LawApi)
    rows = [{"mst": 9, "name": NAME_B, "short": None}]
    api.search = lambda **kw: (1, [dict(r) for r in rows])
    assert lawapi.LawApi.resolve_current(api, GANGRYEONG + "X") is None
    assert lawapi.LawApi.resolve_current(
        api, NAME_B)["mst"] == 9


def test_g7_auto_variants_exact_only(tmp_path):
    # an inferred 'NAME_A 시행령' guess must never resolve via containment;
    # without the auto flag the same containment hit stays available
    from immediatelylaw.db import Database
    from immediatelylaw import resolver, refparse
    d = Database(str(tmp_path / "au.db"))
    SIHAENGRYEONG = _u("SI", "HAENG", "RYEONG")
    STORED = NAME_A + " " + SIHAENGRYEONG + " " + GANGRYEONG
    d.conn.execute("INSERT INTO law(mst,law_id,name,pending) "
                   "VALUES(1,'A1',?,0)", (STORED,))
    d.conn.execute("INSERT INTO article(mst,art_no,title,body,ord) "
                   "VALUES(1,'3','t','D3',1)")
    d.conn.commit()
    try:
        auto = NAME_A + " " + SIHAENGRYEONG
        res = resolver.resolve(d, NAME_A, "3", None,
                               hints=[auto], auto=[auto])
        assert not res["found"], res            # guess may not fuzzy-hit
        res = resolver.resolve(d, auto, "3", None, hints=[auto])
        assert res["found"] and res["law_name"] == STORED  # non-flagged ok
        assert res.get("low_conf") is True
        c = refparse.parse(NAME_A + " " + _u("JE") + "3" + _u("JO"))[0]
        assert c["law_auto"] and not any(a in c["law_all"] for a in
                                         c["law_auto"])
    finally:
        d.close()


def test_g5_local_commit_rename_alias_lifecycle(tmp_path):
    from immediatelylaw.db import Database, norm_name
    from immediatelylaw import localreg, resolver
    f = tmp_path / "reg.txt"
    f.write_text(GUGSE + GYUJEONG + "\n"
                 + _u("JE") + "1" + _u("JO") + " body-1\n"
                 + _u("JE") + "2" + _u("JO") + " body-2\n", encoding="utf-8")
    d = Database(str(tmp_path / "loc.db"))
    try:
        name, arts = localreg.preview_file(str(f))
        assert name == GUGSE + GYUJEONG and len(arts) == 2
        name, n = localreg.commit_file(d, str(f), name, arts)
        assert n == 2
        res = resolver.resolve(d, name, "1")
        assert res["found"] and res["source"] == "local-reg"
        assert not res.get("low_conf")          # exact title: no flag
        # rename (user edited the confirmed title): old key retires
        new = _u("YUN", "RI") + GANGRYEONG
        localreg.commit_file(d, str(f), new, arts)
        assert d.conn.execute("SELECT 1 FROM alias WHERE key=?",
                              (norm_name(name),)).fetchone() is None
        assert not resolver.resolve(d, name, "1")["found"]   # no ghost
        assert resolver.resolve(d, new, "2")["found"]
    finally:
        d.close()


def test_long_sentence_multi_citation_parses():
    # design case 4 (long copy) + multi-citation: glued citations with an
    # ASCII comma between them. Constants reused; nothing re-typed.
    t = "「" + INSHIN + "」 " + _u("JE") + "1" + _u("JO") + ", 「" \
        + INSHIN + "」 " + _u("JE") + "15" + _u("JO")
    r = refparse.parse(t)
    assert [(x["law"], x["art"]) for x in r] == [(INSHIN, "1"),
                                                 (INSHIN, "15")]


# ---- bare article numbers, no marker (v1.7.x) ------------------------------
# '형법 22조' (spoken style, marker 'je' dropped) must parse. Guards:
# digit-run lookbehind, and _back_name's law-suffix requirement keep money
# ("300조 원") and long numbers ("12247조") silent. Also pins the tuple
# early-return in _back_name: a citation copied ALONE (empty context) used
# to crash the unpack in resolve callers.
JE = _u("JE")                                    # article marker
JO = _u("JO")                                    # article noun
WON = _u("WEON")                                 # currency (U+C6D0)


def test_bare_article_space():
    assert first(HYUNG + " 22" + JO) == (HYUNG, "22")


def test_bare_article_nospace():
    assert first(HYUNG + "22" + JO) == (HYUNG, "22")


def test_bare_article_sub():
    assert first(HYUNG + " 22" + JO + _u("YI") + "3") == (HYUNG, "22" + _u("YI") + "3")


def test_bare_number_after_bracket():
    # 「법령명」 15조: bare number after a quoted title still binds to it
    assert first("\u300c" + INSHIN + "\u300d 15" + JO) == (INSHIN, "15")


def test_bare_money_and_longnum_silent():
    assert refparse.parse("300" + JO + " " + WON) == []
    assert refparse.parse("12247" + JO) == []


def test_bare_after_marker_only_counts_once():
    # '제3조 22조' is one citation: a bare number right after a finished
    # article reference must not invent a second candidate
    r = refparse.parse(HYUNG + " " + JE + "3" + JO + " 22" + JO)
    assert [x["art"] for x in r] == ["3"]


def test_marker_alone_does_not_crash():
    # early returns in _back_name must stay 2-tuples: unpacking crash fix
    assert refparse.parse(JE + "3" + JO) == []
    assert refparse.parse("  " + JO) == []
