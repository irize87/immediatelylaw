# -*- coding: utf-8 -*-
"""릴리스 산출물을 깃랩 downloads 브랜치(LFS)에 발행한다.

README가 가리키는 고정 링크(-latest.zip)와 버전 파일, app-latest.json을
out/에서 복사해 gitlab 원격의 downloads 브랜치에 커밋·푸시한다. 같은 버전
재발행이면 같은 내용으로 교체(무해), 신버전이면 신규 추가 + latest 갱신.

사용:  python -m tools.make_release            # 먼저 빌드·패키징
       python -m tools.publish_gitlab.py       # 그 다음 깃랩 채널 발행
요구사항: gitlab 원격 자격증명 저장 완료, git-lfs 설치(.gitattributes는
브랜치에 이미 있음). LFS 대상체는 sha로 중복 제거되므로 latest와 버전 파일이
저장소를 두 배로 쓰지 않는다."""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from immediatelylaw import __version__  # noqa: E402

OUT = os.path.join(ROOT, "out")
WT = os.path.join(os.path.dirname(ROOT), "il-downloads")  # 형제 작업트리
REMOTE = "gitlab"


def git(*args):
    subprocess.run(("git", "-C", WT) + args, check=True)


def main():
    if not os.path.isdir(WT):
        print(f"작업트리 없음: {WT}\n"
              "  git branch downloads <빈 커밋> ; git worktree add "
              f"{WT} downloads   # 최초 1회")
        sys.exit(2)
    names = ["app-latest.json", f"ImmediatelyLaw-online-{__version__}.zip"]
    if os.path.isfile(os.path.join(OUT, f"ImmediatelyLaw-offline-{__version__}.zip")):
        names.append(f"ImmediatelyLaw-offline-{__version__}.zip")
    for kind in ("online", "offline"):
        if os.path.isfile(os.path.join(OUT, f"ImmediatelyLaw-{kind}-latest.zip")):
            names.append(f"ImmediatelyLaw-{kind}-latest.zip")
    for n in names:
        if not os.path.isfile(os.path.join(OUT, n)):
            print(f"산출물 누락: out/{n} — make_release 먼저.")
            sys.exit(2)
    for n in names:
        shutil.copyfile(os.path.join(OUT, n), os.path.join(WT, n))
        print("+", n)
    git("add", "-A")
    if subprocess.run(("git", "-C", WT, "diff", "--cached", "--quiet"),
                      capture_output=True).returncode == 0:
        print("변경 없음 — 이미 발행됨.")
        return
    git("commit", "-m", f"v{__version__} 배포 파일 발행(latest 갱신)")
    git("push", REMOTE, "downloads")
    print(f"깃랩 downloads 발행 완료 v{__version__}")


if __name__ == "__main__":
    main()
