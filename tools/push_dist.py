# -*- coding: utf-8 -*-
"""배포 파일(data/dist)을 데이터 저장소 GitHub의 dist(고아) 브랜치로 push.

사용:
  python -m tools.push_dist --repo https://github.com/<계정>/immediatelylaw-data.git
저장소엔 미리 빈 브랜치만 있으면 되고, 없으면 이 도구가 만든다.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "data", "dist")
WORK = os.path.join(ROOT, "data", "_distrepo")


def run(*cmd, cwd=None):
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        sys.exit(1)
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="데이터 저장소 git URL")
    ap.add_argument("--msg", default="data update")
    a = ap.parse_args()
    if not os.path.isdir(DIST):
        print("data/dist 없음: package/update 먼저.")
        sys.exit(2)

    if os.path.isdir(os.path.join(WORK, ".git")):
        run("git", "fetch", "origin", cwd=WORK)
        has = run("git", "ls-remote", "--heads", "origin", "dist", cwd=WORK)
        if has:
            run("git", "checkout", "-B", "dist", "origin/dist", cwd=WORK)
        else:
            run("git", "checkout", "--orphan", "dist", cwd=WORK)
    else:
        os.makedirs(os.path.dirname(WORK), exist_ok=True)
        run("git", "clone", a.repo, WORK)
        has = run("git", "ls-remote", "--heads", "origin", "dist", cwd=WORK)
        if not has:
            run("git", "checkout", "--orphan", "dist", cwd=WORK)
        else:
            run("git", "checkout", "-B", "dist", "origin/dist", cwd=WORK)

    # dist 작업 폴더 내용 = data/dist 미러
    for fn in os.listdir(WORK):
        if fn == ".git":
            continue
        p = os.path.join(WORK, fn)
        os.remove(p) if os.path.isfile(p) else __import__("shutil").rmtree(p)
    import shutil
    for fn in os.listdir(DIST):
        src = os.path.join(DIST, fn)
        dst = os.path.join(WORK, fn)
        shutil.copy2(src, dst) if os.path.isfile(src) else shutil.copytree(
            src, dst, dirs_exist_ok=True)

    run("git", "add", "-A", cwd=WORK)
    st = run("git", "status", "--porcelain", cwd=WORK)
    if not st:
        print("변경 없음")
        return
    run("git", "commit", "-m", a.msg, cwd=WORK)
    run("git", "push", "-u", "origin", "dist", cwd=WORK)
    print("push 완료 → dist 브랜치")


if __name__ == "__main__":
    main()
