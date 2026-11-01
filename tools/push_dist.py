# -*- coding: utf-8 -*-
"""배포 파일(data/dist)을 데이터 저장소 dist(고아) 브랜치로 push.

채널 분리 원칙: 로컬 dist 작업본(커밋)은 항상 만들고, 각 원격으로의 push는
최선(best-effort)으로 시도한다. 하나의 원격이 죽어도(계정 정지·망 차단)
나머지 채널 배포와 로컬 이력은 계속된다.

사용:
  python -m tools.push_dist --repo https://github.com/<계정>/immediatelylaw-data.git \
      [--also gitlab] [--also 다른 원격]
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
    """로컬 git 작업용: 실패 시 종료."""
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        sys.exit(1)
    return r.stdout.strip()


def try_run(*cmd, cwd=None):
    """네트워크 git 작업용: 실패해도 종료하지 않고 (ok, msg) 반환."""
    print("+", " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    msg = ((r.stdout or "") + (r.stderr or "")).strip()
    return r.returncode == 0, msg.splitlines()[-1] if msg else ""


def _has_branch(work, name):
    r = subprocess.run(["git", "rev-parse", "--verify", name], cwd=work,
                       capture_output=True)
    return r.returncode == 0


def sync_dist_branch(a):
    """_distrepo를 dist 브랜치 상태로 준비(origin 죽음이면 지역 상태 사용)."""
    if not os.path.isdir(os.path.join(WORK, ".git")):
        os.makedirs(os.path.dirname(WORK), exist_ok=True)
        ok, msg = try_run("git", "clone", a.repo, WORK)
        if not ok:
            print("!! clone 실패 — 빈 저장소로 지역 생성:", msg)
            os.makedirs(WORK, exist_ok=True)
            run("git", "init", "-q", cwd=WORK)
            run("git", "remote", "add", "origin", a.repo, cwd=WORK)
    else:
        ok, msg = try_run("git", "fetch", "origin", cwd=WORK)
        if not ok:
            print("!! origin fetch 실패(지역 dist 브랜치로 계속):", msg)
    ok_cur, cur = try_run("git", "rev-parse", "--abbrev-ref", "HEAD",
                          cwd=WORK)
    if ok_cur and cur == "dist":
        return
    ok_remote, _ = try_run("git", "rev-parse", "--verify", "origin/dist",
                           cwd=WORK)
    if ok_remote:
        run("git", "checkout", "-B", "dist", "origin/dist", cwd=WORK)
    elif _has_branch(WORK, "dist"):
        run("git", "checkout", "dist", cwd=WORK)
    else:
        run("git", "checkout", "--orphan", "dist", cwd=WORK)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="데이터 저장소 git URL")
    ap.add_argument("--also", action="append", default=[],
                    help="추가 push 대상 원격 이름(여러 번 지정 가능)")
    ap.add_argument("--msg", default="data update")
    a = ap.parse_args()
    if not os.path.isdir(DIST):
        print("data/dist 없음: package/update 먼저.")
        sys.exit(2)

    sync_dist_branch(a)

    # dist 작업 폴더 내용 = data/dist 미러
    import shutil
    for fn in os.listdir(WORK):
        if fn == ".git":
            continue
        p = os.path.join(WORK, fn)
        os.remove(p) if os.path.isfile(p) else shutil.rmtree(p)
    for fn in os.listdir(DIST):
        src = os.path.join(DIST, fn)
        dst = os.path.join(WORK, fn)
        shutil.copy2(src, dst) if os.path.isfile(src) else shutil.copytree(
            src, dst, dirs_exist_ok=True)

    run("git", "add", "-A", cwd=WORK)
    st = run("git", "status", "--porcelain", cwd=WORK)
    if not st:
        print("변경 없음")
    else:
        run("git", "commit", "-m", a.msg, cwd=WORK)
    remotes = ["origin"] + [r for r in a.also if r != "origin"]
    failed = []
    for remote in remotes:
        if remote != "origin":
            r = subprocess.run(["git", "remote", "get-url", remote],
                               cwd=WORK, capture_output=True)
            if r.returncode != 0:
                print(f"- {remote}: 원격 미등록 — 건너뜀")
                continue
        ok, msg = try_run("git", "push", "-u", remote, "dist", cwd=WORK)
        print(("- " if not ok else "✔ ") + f"{remote}: " + (msg or "push 완료"))
        if not ok:
            failed.append(remote)
    if st or failed:
        print("push 완료 → dist 브랜치" if not failed
              else "!! 실패 채널: " + ", ".join(failed))
    sys.exit(0)


if __name__ == "__main__":
    main()
