# -*- coding: utf-8 -*-
r"""dist/ImmediatelyLaw(온디렉터리 빌드) → MSIX 패키징(+테스트 서명).

- 매니페스트 원본은 storekit/AppxManifest.xml(1.5.7 MSIX에서 바이트 그대로
  추출해 보존한 것). 이 도구는 Identity의 ASCII 속성(Version/Name/Publisher)만
  정규식으로 바꾸고, 한글 바이트(DisplayName 등)는 절대 재타이핑하지 않는다.
- 식별자 기본값은 개발 인증서 신원(Name=ImmediatelyLaw, CN=ImmediatelyLaw-Dev).
  파트너 센터 예약 값이 확정되면 --name/--publisher로 교체해 최종 빌드한다.
- 패키징·서명은 winapp CLI(Windows SDK 불필요). 인증서는 커밋하지 않는다 —
  기본값은 %TEMP%\il_scan\store\devcert.pfx(winapp 기본 비밀번호 'password').
- 스토어 제출본은 --no-sign(스토어가 재서명) 또는 서명본 그대로도 접수된다.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from immediatelylaw import __version__  # noqa: E402

DIST_APP = os.path.join(ROOT, "dist", "ImmediatelyLaw")
STOREKIT = os.path.join(ROOT, "storekit")
OUT = os.path.join(ROOT, "out")


def _patch_manifest(name=None, publisher=None):
    xml = open(os.path.join(STOREKIT, "AppxManifest.xml"),
               encoding="utf-8").read()
    ver = "%s.0" % __version__
    xml, n = re.subn(r'(<Identity\b[^>]*\bVersion=")[^"]*(")',
                     r"\g<1>%s\g<2>" % ver, xml, count=1)
    assert n == 1, "Identity Version attribute not found"
    if name:
        assert name.isascii(), "identity overrides must be ascii"
        xml, n = re.subn(r'(<Identity\b[^>]*\bName=")[^"]*(")',
                         r"\g<1>%s\g<2>" % name, xml, count=1)
        assert n == 1
    if publisher:
        assert publisher.isascii(), "identity overrides must be ascii"
        xml, n = re.subn(r'(<Identity\b[^>]*\bPublisher=")[^"]*(")',
                         lambda m: m.group(1) + publisher + m.group(2),
                         xml, count=1)
        assert n == 1
    return xml, ver


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", help="Identity Name override (store reserved)")
    ap.add_argument("--publisher", help="Identity Publisher DN override")
    ap.add_argument("--cert", default=os.path.join(
        os.environ.get("TEMP", ""), "il_scan", "store", "devcert.pfx"))
    ap.add_argument("--cert-password", default="password")
    ap.add_argument("--no-sign", action="store_true",
                    help="unsigned package for store submission")
    a = ap.parse_args()

    exe = os.path.join(DIST_APP, "ImmediatelyLaw.exe")
    if not os.path.isfile(exe):
        sys.exit("dist 빌드가 없습니다. 먼저 PyInstaller 빌드를 실행하세요: %s"
                 % DIST_APP)

    layout = os.path.join(OUT, "msix-layout")
    shutil.rmtree(layout, ignore_errors=True)
    shutil.copytree(DIST_APP, layout)
    shutil.copytree(os.path.join(STOREKIT, "Assets"),
                    os.path.join(layout, "Assets"))

    xml, ver = _patch_manifest(a.name, a.publisher)
    with open(os.path.join(layout, "AppxManifest.xml"), "w",
              encoding="utf-8", newline="") as f:
        f.write(xml)

    msix = os.path.join(OUT, "ImmediatelyLaw_%s_x64.msix" % ver)
    cmd = ["winapp", "package", layout,
           "--manifest", os.path.join(layout, "AppxManifest.xml"),
           "--output", msix]
    if a.no_sign:
        cmd.append("--no-sign")
    else:
        if not os.path.isfile(a.cert):
            sys.exit("서명 인증서 없음: %s (winapp --generate-cert 로 생성하거나 "
                     "--cert 지정, 또는 --no-sign)" % a.cert)
        cmd += ["--cert", a.cert, "--cert-password", a.cert_password]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("MSIX: %s (%.1fMB)" % (msix, os.path.getsize(msix) / 1048576))


if __name__ == "__main__":
    main()
