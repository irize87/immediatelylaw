# -*- coding: utf-8 -*-
"""배포 zip을 원격(기본 gitlab)의 download 브랜치에 고아 커밋으로 올린다.

GitLab 릴리즈 기능이 없는 인스턴스에서도 브랜치 파일(raw)로 zip을 받을 수 있게 한다.
집행 예:
    python tools/push_gitlab_download.py out/ImmediatelyLaw-online.zip out/ImmediatelyLaw-offline.zip
"""
import argparse
import datetime
import os
import subprocess
import sys
import tempfile

BRANCH_README = """# 즉시로 다운로드 패키지

아래 파일을 눌러 Raw(원본)로 저장한 뒤 압축을 풀어 사용하세요.
(GitHub Releases 연동이 어려운 정부 GitLab 환경용 직접 다운로드 브랜치)

- **ImmediatelyLaw-online.zip** — 인터넷 연결 PC용 (앱만 포함, 데이터는 첫 실행 시 자동 다운로드)
- **ImmediatelyLaw-offline.zip** — 인터넷 없는 PC용 (앱 + 법령 데이터 동봉)

파일 원본(raw) 주소:

- `/raw/download/ImmediatelyLaw-online.zip`
- `/raw/download/ImmediatelyLaw-offline.zip`

링크가 바로 열리지 않으면 저장소에서 **브랜치를 `download`로 전환**한 뒤
파일名을 눌러 [Raw]를 선택하세요.

소스 코드: `main` 브랜치
GitHub Releases: https://github.com/nazgregory/ImmediatelyLaw/releases
"""


def run(args, env=None, capture=True, stdin=None):
    r = subprocess.run(["git"] + args, env=env, input=stdin,
                       capture_output=capture, text=capture,
                       encoding="utf-8" if capture else None)
    if r.returncode != 0:
        sys.exit("git " + " ".join(args) + " 실패:\n" + (r.stderr or ""))
    return (r.stdout or "").strip() if capture else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zips", nargs="+")
    ap.add_argument("--remote", default="gitlab")
    ap.add_argument("--branch", default="download")
    a = ap.parse_args()

    for z in a.zips:
        if not os.path.isfile(z):
            sys.exit("파일이 없습니다: " + z)

    idx = os.path.join(tempfile.gettempdir(), "ilaw_dl_index")
    if os.path.exists(idx):
        os.remove(idx)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = idx
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "ImmediatelyLaw"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = \
        "immediatelylaw@example.invalid"
    run(["read-tree", "--empty"], env=env)

    # 안내 README
    rsha = run(["hash-object", "-w", "--stdin"], env=env,
               stdin=BRANCH_README)
    run(["update-index", "--add", "--cacheinfo",
         f"100644,{rsha},README.md"], env=env)

    for z in a.zips:
        # 해시·추가 대상 파일은 작업트리와 무관하게 content만 staging 한다.
        absz = os.path.abspath(z)
        sha = run(["hash-object", "-w", absz])
        run(["update-index", "--add", "--cacheinfo",
             f"100644,{sha},{os.path.basename(z)}"], env=env)
        print("추가:", os.path.basename(z),
              f"{os.path.getsize(absz)/1048576:.1f}MB")

    tree = run(["write-tree"], env=env)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    commit = run(["commit-tree", tree, "-m",
                  f"download 패키지 갱신 ({stamp})"])
    run(["push", "--force", a.remote, f"{commit}:refs/heads/{a.branch}"],
        capture=False)
    os.remove(idx)
    print(f"완료 → {a.remote}/{a.branch} (커밋 {commit[:8]})")


if __name__ == "__main__":
    main()
