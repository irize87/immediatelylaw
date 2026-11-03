# -*- coding: utf-8 -*-
"""즉시로 로컬 DB. 조문 열람은 항상 이 SQLite만 봐서 즉시 응답한다."""
import os
import re
import sqlite3
import sys
import threading
import time

APP_DIR = (getattr(sys, "_MEIPASS", None)
           or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _data_dir():
    """개발 중엔 프로젝트 data/, exe(패키지)에선 %APPDATA%\\immediatelylaw\\data."""
    d = os.environ.get("IMMEDIATELYLAW_DATA_DIR")
    if d:
        return d
    if getattr(sys, "frozen", False):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "immediatelylaw", "data")
    return os.path.join(APP_DIR, "data")


DATA_DIR = _data_dir()
DB_PATH = os.path.join(DATA_DIR, "immediatelylaw.db")

SCHEMA_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS law(
  mst INTEGER PRIMARY KEY,
  law_id TEXT NOT NULL,
  name TEXT NOT NULL,
  short TEXT,
  cls TEXT,
  promulgated TEXT,
  enforced TEXT,
  pending INTEGER DEFAULT 0,
  agency TEXT
);
CREATE INDEX IF NOT EXISTS idx_law_name ON law(name);
CREATE INDEX IF NOT EXISTS idx_law_lawid ON law(law_id);
CREATE INDEX IF NOT EXISTS idx_law_short ON law(short);
/* 검색어 정확조회(search_laws_by_name)의 정규화 표현식과
   문자 그대로 동일해야 식(expression) 인덱스가 사용된다. */
CREATE INDEX IF NOT EXISTS idx_law_effective_norm_name
  ON law(replace(replace(name,' ',''),'\u3000',''));
CREATE INDEX IF NOT EXISTS idx_law_effective_norm_short
  ON law(replace(short,' ',''));
CREATE TABLE IF NOT EXISTS article(
  mst INTEGER NOT NULL,
  art_no TEXT NOT NULL,
  title TEXT,
  chap TEXT,
  body TEXT NOT NULL,
  ord INTEGER,
  PRIMARY KEY(mst, art_no)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS alias(key TEXT PRIMARY KEY, law_id TEXT);
CREATE TABLE IF NOT EXISTS local_law(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, source TEXT, kind TEXT, added_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_local_name ON local_law(name);
CREATE TABLE IF NOT EXISTS local_article(
  lid INTEGER NOT NULL,
  art_no TEXT NOT NULL,
  title TEXT,
  body TEXT NOT NULL,
  ord INTEGER,
  PRIMARY KEY(lid, art_no)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS build_state(
  mst INTEGER PRIMARY KEY, law_id TEXT, status TEXT, msg TEXT
);
CREATE TABLE IF NOT EXISTS changelog(
  at TEXT, law_id TEXT, mst INTEGER, name TEXT, action TEXT
);
"""


def norm_name(s: str) -> str:
    """법령명 비교용 정규화: 공백 제거, 전/반각 괄호 통일."""
    if not s:
        return ""
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")").replace("『", "").replace("』", "")
    return s


class Database:
    def __init__(self, path=DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(_SCHEMA)
        ver = self.conn.execute(
            "SELECT value FROM meta WHERE key='schema_ver'").fetchone()
        if not ver:
            self.set_meta("schema_ver", SCHEMA_VERSION)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def reload_from_file(self, new_path):
        """업데이트가 내려받은 DB 파일로 스토어를 교체한다."""
        with self._lock:
            try:
                self.conn.close()
            except sqlite3.Error:
                pass
            for ext in ("-wal", "-shm"):
                p = DB_PATH + ext
                if os.path.exists(p):
                    os.remove(p)
            os.replace(new_path, DB_PATH)
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            # 내려받은 파일이 옛 스키마여도 앱 기준 구조·인덱스를 보장한다.
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

    def set_meta(self, key, value):
        with self._lock:
            self.conn.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))
            self.conn.commit()

    def get_meta(self, key, default=""):
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    # ---------- 조회 ----------
    def find_article(self, law_mst: int, art_no: str):
        return self.conn.execute(
            "SELECT * FROM article WHERE mst=? AND art_no=?",
            (law_mst, art_no)).fetchone()

    def find_law(self, law_id: str, only_effective=True):
        q = ("SELECT * FROM law WHERE law_id=?")
        if only_effective:
            q += " AND pending=0"
        q += " ORDER BY enforced DESC LIMIT 1"
        return self.conn.execute(q, (law_id,)).fetchone()

    def latest_mst(self, law_id: str):
        row = self.conn.execute(
            "SELECT * FROM law WHERE law_id=? "
            "ORDER BY enforced DESC LIMIT 1", (law_id,)).fetchone()
        return row

    def search_laws_by_name(self, hint: str, limit=30):
        h = norm_name(hint)
        if not h:
            return []
        rows = self.conn.execute(
            "SELECT * FROM law WHERE pending=0 AND replace(replace(name,' ',''),'\u3000','')=?"
            " ORDER BY enforced DESC", (h,)).fetchall()
        if rows:
            return rows
        rows = self.conn.execute(
            "SELECT * FROM law WHERE pending=0 AND short IS NOT NULL "
            "AND replace(short,' ','')=? ORDER BY enforced DESC", (h,)).fetchall()
        if rows:
            return rows
        # 접두/포함 매칭(짧은 이름 우선)
        rows = self.conn.execute(
            "SELECT l.* FROM law l JOIN alias a ON a.law_id=l.law_id "
            "WHERE l.pending=0 AND a.key LIKE ?||'%' "
            "ORDER BY length(a.key) LIMIT ?", (h, limit)).fetchall()
        if rows:
            return rows
        return self.conn.execute(
            "SELECT * FROM law WHERE pending=0 "
            "AND replace(name,' ','') LIKE ? "
            "ORDER BY length(name) LIMIT ?", ('%' + h + '%', limit)).fetchall()

    def get_alias(self, key):
        return self.conn.execute(
            "SELECT law_id FROM alias WHERE key=?", (key,)).fetchone()

    def local_search(self, hint: str, limit=20):
        h = norm_name(hint)
        return self.conn.execute(
            "SELECT * FROM local_law WHERE replace(name,' ','') LIKE ? "
            "ORDER BY length(name) LIMIT ?", ('%' + h + '%', limit)).fetchall()

    def local_find(self, lid: int, art_no: str):
        return self.conn.execute(
            "SELECT * FROM local_article WHERE lid=? AND art_no=?",
            (lid, art_no)).fetchone()

    def local_articles(self, lid: int):
        return self.conn.execute(
            "SELECT * FROM local_article WHERE lid=? ORDER BY ord",
            (lid,)).fetchall()

    def stats(self):
        d = {}
        d["laws"] = self.conn.execute(
            "SELECT COUNT(*) c FROM law WHERE pending=0").fetchone()["c"]
        d["pending_laws"] = self.conn.execute(
            "SELECT COUNT(*) c FROM law WHERE pending=1").fetchone()["c"]
        d["articles"] = self.conn.execute(
            "SELECT COUNT(*) c FROM article").fetchone()["c"]
        d["local_laws"] = self.conn.execute(
            "SELECT COUNT(*) c FROM local_law").fetchone()["c"]
        d["data_ver"] = self.get_meta("data_ver")
        d["built_at"] = self.get_meta("built_at")
        return d

    # ---------- 쓰기(빌더/업데이트용) ----------
    def replace_law(self, law: dict, articles: list, aliases: list,
                    action="upsert"):
        """law dict: mst/law_id/name/short/cls/promulgated/enforced/pending/agency.
        articles: [{art_no,title,chap,body,ord}]  aliases: [key,...]"""
        today = time.strftime("%Y%m%d")
        with self._lock:
            cur = self.conn
            cur.execute("DELETE FROM law WHERE law_id=? AND mst<>?",
                        (law["law_id"], law["mst"]))
            cur.execute("DELETE FROM article WHERE mst=?", (law["mst"],))
            cur.execute(
                "INSERT OR REPLACE INTO law"
                "(mst,law_id,name,short,cls,promulgated,enforced,pending,agency)"
                " VALUES(:mst,:law_id,:name,:short,:cls,:promulgated,"
                ":enforced,:pending,:agency)", law)
            cur.executemany(
                "INSERT OR REPLACE INTO article"
                "(mst,art_no,title,chap,body,ord) VALUES(?,?,?,?,?,?)",
                [(law["mst"], a["art_no"], a.get("title"), a.get("chap"),
                  a["body"], a.get("ord", 0)) for a in articles])
            for k in aliases:
                cur.execute("INSERT OR REPLACE INTO alias(key,law_id) "
                            "VALUES(?,?)", (k, law["law_id"]))
            cur.execute(
                "INSERT INTO changelog(at,law_id,mst,name,action) "
                "VALUES(?,?,?,?,?)",
                (today, law["law_id"], law["mst"], law["name"], action))
            cur.execute("DELETE FROM build_state WHERE mst=?", (law["mst"],))
            cur.commit()

    # ---------- 빌더 진행상태 ----------
    def build_remaining(self, all_msts):
        done = {r["mst"] for r in self.conn.execute(
            "SELECT mst FROM build_state WHERE status='ok'")}
        return [m for m in all_msts if m not in done]

    def build_mark(self, mst, law_id, status, msg=""):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO build_state(mst,law_id,status,msg) "
                "VALUES(?,?,?,?)", (mst, law_id, status, msg[:300]))
            self.conn.commit()

    def build_failed(self):
        return self.conn.execute(
            "SELECT mst, law_id, msg FROM build_state WHERE status='fail'"
        ).fetchall()


_db = None


def get_db(path=DB_PATH):
    global _db
    if _db is None:
        _db = Database(path)
    return _db
