# -*- coding: utf-8 -*-
"""4단계: 정규화 표현식 인덱스 회귀 테스트.

검색 정확조회의 WHERE 표현식과 인덱스 식이 문자 그대로 일치해야 하므로,
양쪽을 이 테스트가 동시에 감시한다."""
import sqlite3

from immediatelylaw import db as dbmod
from immediatelylaw.db import Database

NORM_NAME_EXPR = "replace(replace(name,' ',''),'\u3000','')"
NORM_SHORT_EXPR = "replace(short,' ','')"


def index_names(d):
    return {r["name"] for r in d.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}


def test_schema_creates_norm_indexes(tmp_path):
    d = Database(str(tmp_path / "t.db"))
    try:
        names = index_names(d)
        assert "idx_law_effective_norm_name" in names
        assert "idx_law_effective_norm_short" in names
    finally:
        d.close()


def test_exact_match_finds_spaced_name(tmp_path):
    """공백 다른 검색어도 정확조회로 찾아져야 한다(인덱스 식의 의미 검증)."""
    d = Database(str(tmp_path / "t.db"))
    try:
        d.conn.execute(
            "INSERT INTO law(mst,law_id,name,pending) "
            "VALUES(1,'L1','개인정보 보호법',0)")
        d.conn.commit()
        rows = d.search_laws_by_name("개인정보보호법")
        assert [r["name"] for r in rows] == ["개인정보 보호법"]
    finally:
        d.close()


def test_exact_match_query_plan_uses_index(tmp_path):
    """조회 계획이 TABLE FULL SCAN 대신 인덱스를 타야 한다(4단계의 목적)."""
    d = Database(str(tmp_path / "t.db"))
    try:
        rows = d.conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM law WHERE pending=0 AND "
            f"{NORM_NAME_EXPR}=?", ("민법",)).fetchall()
        plan = " ".join(r["detail"] for r in rows)
        assert "idx_law_effective_norm_name" in plan, plan
    finally:
        d.close()


def test_short_exact_match_plan_uses_index(tmp_path):
    d = Database(str(tmp_path / "t.db"))
    try:
        rows = d.conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM law WHERE pending=0 AND "
            "short IS NOT NULL AND "
            f"{NORM_SHORT_EXPR}=?", ("형법",)).fetchall()
        plan = " ".join(r["detail"] for r in rows)
        assert "idx_law_effective_norm_short" in plan, plan
    finally:
        d.close()


def test_reload_from_file_reapplies_schema(tmp_path, monkeypatch):
    """업데이터로 내려받은 DB가 구(舊)구조여도 재접속 시 인덱스를 보장한다."""
    live = tmp_path / "live.db"
    fresh = tmp_path / "fresh.db"
    monkeypatch.setattr(dbmod, "DB_PATH", str(live))

    # 인덱스 없는 최소 스키마의 '다운로드 파일'을 만든다
    c = sqlite3.connect(fresh)
    c.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE law(mst INTEGER PRIMARY KEY, law_id TEXT NOT "
              "NULL, name TEXT NOT NULL, short TEXT, cls TEXT, promulgated "
              "TEXT, enforced TEXT, pending INTEGER DEFAULT 0, agency TEXT)")
    c.commit()
    c.close()

    d = Database(str(live))
    try:
        assert "idx_law_effective_norm_name" in index_names(d)
        d.reload_from_file(str(fresh))
        assert "idx_law_effective_norm_name" in index_names(d)
        assert "idx_law_effective_norm_short" in index_names(d)
    finally:
        d.close()
