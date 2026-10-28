# -*- coding: utf-8 -*-
"""즉시로 데이터 발행 도구 (발행자 전용, OC 키 필요).

사용:
  python -m tools.publisher build [--limit N]   # 현행 법령 전체 수집(재개됨)
  python -m tools.publisher status              # 진행 현황
  python -m tools.publisher update              # 개정분만 반영 + 델타 생성
  python -m tools.publisher package             # 배포용 스냅샷(.db.xz)+manifest
"""
import argparse
import hashlib
import json
import lzma
import os
import shutil
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from immediatelylaw import config as cfgmod
from immediatelylaw import db as dbmod
from immediatelylaw.db import Database, norm_name
from immediatelylaw.lawapi import LawApi, LawApiError

OUT_DIR = os.path.join(dbmod.DATA_DIR, "dist")


def _api():
    key = cfgmod.get_config().get_oc_key() or os.environ.get("IMMEDIATELYLAW_OC", "")
    if not key:
        print("OC 키 없음: 설정 앱에서 입력하거나 IMMEDIATELYLAW_OC 환경변수를 사용하세요.")
        sys.exit(2)
    return LawApi(key)


def _aliases(law):
    keys = {norm_name(law["name"])}
    if law.get("short"):
        keys.add(norm_name(law["short"]))
    return [k for k in keys if k]


def _fetch_one(api, d, m_row):
    law, arts = api.fetch_full(m_row["mst"])
    if not law["law_id"]:
        law["law_id"] = m_row["law_id"]
    if not law["name"]:
        law["name"] = m_row["name"]
    if not arts:
        raise LawApiError("조문 0건")
    d.replace_law(law, arts, _aliases(law), action="build")
    return law, arts


def cmd_build(args):
    api = _api()
    d = Database()
    print("현행 법령 목록 열거 중…")
    todo = list(api.iter_current_laws())
    msts = [r["mst"] for r in todo]
    by_mst = {r["mst"]: r for r in todo}
    remain = d.build_remaining(msts)
    if args.limit:
        remain = remain[:args.limit]
    total = len(remain)
    print(f"전체 {len(msts)}건, 이미 완료 {len(msts)-len(remain) if not args.limit else '-'}, "
          f"수집 예정 {total}건")
    t0, ok, fail = time.time(), 0, 0
    for i, mst in enumerate(remain, 1):
        row = by_mst[mst]
        try:
            _fetch_one(api, d, row)
            d.build_mark(mst, row["law_id"], "ok")
            ok += 1
        except LawApiError as e:
            d.build_mark(mst, row["law_id"], "fail", str(e))
            fail += 1
        if i % 20 == 0 or i == total:
            el = time.time() - t0
            eta = el / i * (total - i)
            print(f"[{i}/{total}] ok={ok} fail={fail} "
                  f"elapsed={el/60:.1f}분 eta={eta/60:.1f}분 "
                  f"({row['name']})", flush=True)
    # 실패분 1회 재시도
    fails = d.build_failed()
    if fails and not args.limit:
        print(f"실패 {len(fails)}건 재시도…")
        for row in fails:
            try:
                law2, arts = api.fetch_full(row["mst"])
                d.replace_law(law2, arts, _aliases(law2), action="retry")
                d.build_mark(row["mst"], row["law_id"], "ok")
            except LawApiError as e:
                d.build_mark(row["mst"], row["law_id"], "fail", str(e))
    ver = time.strftime("%Y%m%d%H%M")
    d.set_meta("data_ver", ver)
    d.set_meta("built_at", time.strftime("%Y-%m-%d %H:%M"))
    print("완료.", d.stats())


def cmd_status(_args):
    d = Database()
    print("DB:", dbmod.DB_PATH)
    for k, v in d.stats().items():
        print(f"  {k}: {v}")
    left = d.conn.execute(
        "SELECT COUNT(*) c FROM build_state WHERE status IS NULL OR status!='ok'"
    ).fetchone()["c"]
    print(f"  미완/실패 표시: {left}")


def cmd_update(_args):
    api = _api()
    d = Database()
    print("현행 목록 재열거…")
    todo = list(api.iter_current_laws())
    cur_mst = {r["mst"] for r in todo}
    db_rows = d.conn.execute("SELECT mst, law_id FROM law").fetchall()
    db_mst = {r["mst"] for r in db_rows}
    db_lawids = {r["law_id"] for r in db_rows}
    cur_lawids = {r["law_id"] for r in todo}
    changed = [r for r in todo if r["mst"] not in db_mst]
    removed = db_lawids - cur_lawids
    print(f"개정/신규 {len(changed)}건, 폐지 {len(removed)}건")
    by_mst = {r["mst"]: r for r in todo}
    updated_delta = []
    for r in changed:
        try:
            law, arts = api.fetch_full(r["mst"])
            d.replace_law(law, arts, _aliases(law), action="update")
            updated_delta.append({"law": law, "articles": arts})
            print(f"  반영: {r['name']} (mst {r['mst']})")
        except LawApiError as e:
            print(f"  실패: {r['name']} - {e}")
    for law_id in removed:
        d.conn.execute("DELETE FROM law WHERE law_id=?", (law_id,))
        d.conn.commit()
    ver = time.strftime("%Y%m%d%H%M")
    d.set_meta("data_ver", ver)
    os.makedirs(OUT_DIR, exist_ok=True)
    if updated_delta or removed:
        raw = json.dumps({"ver": ver, "laws": updated_delta,
                          "removed": sorted(removed)}, ensure_ascii=False)
        path = _write_xz(os.path.join(OUT_DIR, f"delta-{ver}.json"), raw)
        print("델타:", path)
    print("완료.", d.stats())


def cmd_package(_args):
    d = Database()
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = os.path.join(OUT_DIR, "snapshot-src.db")
    d.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    src = sqlite3.connect(dbmod.DB_PATH)
    dst = sqlite3.connect(tmp)
    src.backup(dst)
    dst.execute("VACUUM")
    dst.commit()
    dst.close()
    src.close()
    ver = d.get_meta("data_ver") or time.strftime("%Y%m%d%H%M")
    final = os.path.join(OUT_DIR, f"immediatelylaw-{ver}.db.xz")
    with open(tmp, "rb") as fin, lzma.open(final, "wb", preset=9) as fout:
        shutil.copyfileobj(fin, fout)
    os.remove(tmp)
    raw = open(final, "rb").read()
    manifest = {
        "app": "immediatelylaw",
        "data_ver": ver,
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "snapshot": {
            "file": os.path.basename(final),
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "source": "출처: 국가법령정보센터(법제처) OPEN API",
        "deltas": [],
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("패키지 완료:", final, f"{len(raw)/1024/1024:.1f} MiB")


def _write_xz(path, text):
    with lzma.open(path + ".xz", "wb", preset=9) as f:
        f.write(text.encode("utf-8"))
    return path + ".xz"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--limit", type=int, default=0)
    b.set_defaults(func=cmd_build)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("update").set_defaults(func=cmd_update)
    sub.add_parser("package").set_defaults(func=cmd_package)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
