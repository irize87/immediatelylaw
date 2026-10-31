# -*- coding: utf-8 -*-
"""공개 배포 검증(재사용): 버전/다운로드 sha256/랜딩 폴백·동일성.

사용: python tools/release_verify.py 1.5.1
시스템 curl.exe를 쓴다. 배포 서버는 자기서명 인증서이므로 -k로 TLS 검증을
우회한다(배포물 무결성은 sha256로 검증 — 이 도구의 핵심 목적)."""
import hashlib
import json
import subprocess
import sys

BASE = "https://152.67.205.216"
EXPECT = sys.argv[1] if len(sys.argv) > 1 else ""


def curl(path, timeout=300):
    r = subprocess.run(["curl", "-sk", "--fail", BASE + path],
                       capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"curl 실패({r.returncode}): {path}")
    return r.stdout


latest = json.loads(curl("/app-latest.json").decode("utf-8"))
ok = True
print("version:", latest["version"])
for kind, info in latest["files"].items():
    blob = curl("/" + info["file"], timeout=900)
    h = hashlib.sha256(blob).hexdigest()
    m = h == info["sha256"] and len(blob) == info["size"]
    ok &= m
    print(f"{kind}: {info['file']} {len(blob)}B {'OK' if m else 'MISMATCH'}")

html = curl("/").decode("utf-8")
loc = open("web/index.html", encoding="utf-8").read()
same = html == loc
stale = html.count(".zip") - html.count(f"{EXPECT}.zip")
print("landing identical:", same, "| fallback", EXPECT, ":",
      html.count(f"{EXPECT}.zip"), "| 다른 버전 폴백:", stale)
print("ALL OK" if ok and same and latest["version"] == EXPECT else "CHECK FAILED")
