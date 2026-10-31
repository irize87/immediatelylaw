# -*- coding: utf-8 -*-
"""릴리스 패키징: dist/ImmediatelyLaw를 두 가지 zip으로 만들고 앱 자체
업데이트용 app-latest.json(sha256 포함)을 생성한다.

사용:
  pyinstaller ImmediatelyLaw.spec             # 먼저 빌드
  python -m tools.make_release                # out/ 에 산출물 생성
  python -m tools.make_release --server ubuntu@100.109.191.50
        # 추가로 서버 data/dist 에 scp(다음 cron이 배포 서버로 발행)

산출물:
  out/ImmediatelyLaw-online-<ver>.zip    (프로그램만)
  out/ImmediatelyLaw-offline-<ver>.zip   (+ 최신 데이터 xz 동봉)
  out/app-latest.json                    (모든 배포 채널 공통 최신 버전 정보)
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from immediatelylaw import __version__  # noqa: E402

DIST_APP = os.path.join(ROOT, "dist", "ImmediatelyLaw")
DATA_DIST = os.path.join(ROOT, "data", "dist")
OUT = os.path.join(ROOT, "out")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _zip_dir(src_dir, zip_path, extra_files=()):
    base = os.path.basename(src_dir)          # ImmediatelyLaw
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as z:
        for root, _dirs, files in os.walk(src_dir):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, os.path.dirname(src_dir))
                z.write(p, rel.replace("\\", "/"))
        for p in extra_files:
            z.write(p, f"{base}/{os.path.basename(p)}")


def latest_snapshot():
    if not os.path.isdir(DATA_DIST):
        return None
    cands = sorted(f for f in os.listdir(DATA_DIST)
                   if f.startswith("immediatelylaw-") and f.endswith(".db.xz"))
    return os.path.join(DATA_DIST, cands[-1]) if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="",
                    help="scp 대상(host:user 생략 시 ubuntu@…). "
                         "data/dist에 산출물을 둔다.")
    ap.add_argument("--xz", default="", help="오프라인 동봉 xz(기본: 최신분)")
    a = ap.parse_args()

    if not os.path.isfile(os.path.join(DIST_APP, "ImmediatelyLaw.exe")):
        print("dist/ImmediatelyLaw/ImmediatelyLaw.exe 없음: 빌드 먼저.")
        sys.exit(2)
    os.makedirs(OUT, exist_ok=True)
    ver = __version__

    online = os.path.join(OUT, f"ImmediatelyLaw-online-{ver}.zip")
    _zip_dir(DIST_APP, online)

    xz = a.xz or (latest_snapshot() or "")
    offline = os.path.join(OUT, f"ImmediatelyLaw-offline-{ver}.zip")
    if xz and os.path.isfile(xz):
        _zip_dir(DIST_APP, offline, extra_files=[xz])
    else:
        print("!! 동봉할 데이터 xz 없음 — 오프라인 패키지 생략")
        offline = ""

    files = {"online": {"file": os.path.basename(online),
                        "size": os.path.getsize(online),
                        "sha256": _sha256(online)}}
    if offline:
        files["offline"] = {"file": os.path.basename(offline),
                            "size": os.path.getsize(offline),
                            "sha256": _sha256(offline)}
    latest = {"app": "immediatelylaw", "version": ver,
              "updated": time.strftime("%Y-%m-%d %H:%M"), "files": files}
    latest_path = os.path.join(OUT, "app-latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=1)

    print(f"v{ver} 패키징 완료")
    for k, v in files.items():
        print(f"  {k}: {v['file']} {v['size']/1048576:.1f}MB "
              f"sha256={v['sha256'][:16]}…")
    print(f"  app-latest.json: {latest_path}")

    if a.server:
        payloads = [latest_path, online] + ([offline] if offline else [])
        for p in payloads:
            print("+ scp", os.path.basename(p))
            subprocess.run(["scp", p,
                            f"{a.server}:ImmediatelyLaw/data/dist/"],
                           check=True)
        print("서버 반영 완료 — 이후 daily 또는 배포 서버 동기화에서 발행됩니다.")


if __name__ == "__main__":
    main()
