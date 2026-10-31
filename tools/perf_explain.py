# -*- coding: utf-8 -*-
"""4단계 검증: 실 DB 사본(격리)에서 인덱스 추가 전/후 EXPLAIN + 조회 소요.
운영 DB(%APPDATA%)는 건드리지 않는다 — %TEMP%\il_measure 사본만 사용."""
import os
import statistics
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from immediatelylaw.db import _SCHEMA  # noqa: E402

COPY = os.path.join(os.environ["TEMP"], "il_measure", "AppData", "Roaming",
                    "immediatelylaw", "data", "immediatelylaw.db")
Q1 = ("SELECT * FROM law WHERE pending=0 AND "
      "replace(replace(name,' ',''),'\u3000','')=?")
Q2 = ("SELECT * FROM law WHERE pending=0 AND short IS NOT NULL AND "
      "replace(short,' ','')=?")
NAMES = ["민법", "형법", "개인정보 보호법", "도서관법", "건축법",
         "도로법", "형사소송법", "상법"]


def plan(conn, q, p):
    return " | ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + q, p))


def bench(conn, label):
    for n in NAMES:                       # 페이지 캐시 워밍
        conn.execute(Q1, (n.replace(" ", ""),)).fetchall()
    ts = []
    for i in range(200):
        n = NAMES[i % len(NAMES)].replace(" ", "")
        t0 = time.perf_counter()
        conn.execute(Q1, (n,)).fetchall()
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    print(f"  {label}: n=200 중앙={statistics.median(ts):.3f}ms "
          f"p95={ts[int(len(ts) * 0.95)]:.3f}ms 최대={ts[-1]:.3f}ms")


print("copy size:", os.path.getsize(COPY))
conn = sqlite3.connect(COPY)
print("[BEFORE] Q1 계획:", plan(conn, Q1, ("민법",)))
print("[BEFORE] Q2 계획:", plan(conn, Q2, ("형법",)))
bench(conn, "인덱스 추가 전")
conn.close()

# 앱 부트와 동일 경로: _SCHEMA 실행(식 인덱스 2종 생성) — 부트 비용도 재는 다
conn = sqlite3.connect(COPY)
t0 = time.perf_counter()
conn.executescript(_SCHEMA)
conn.commit()
print(f"인덱스 생성(부트 시 1회) 소요: {(time.perf_counter() - t0) * 1000:.0f}ms")
print("[AFTER ] Q1 계획:", plan(conn, Q1, ("민법",)))
print("[AFTER ] Q2 계획:", plan(conn, Q2, ("형법",)))
bench(conn, "인덱스 추가 후")
conn.close()
