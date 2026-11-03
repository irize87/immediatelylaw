# -*- coding: utf-8 -*-
"""빌드 결과물(immediatelylaw exe)에 실제로 박힌 문자열을
PyInstaller 공식 리더로 읽어 코드포인트 판독한다.

사용: python -X utf8 tools/pyz_scan.py [path/to/ImmediatelyLaw.exe]
정본 '업데프트'(EOB-DE-PEU-TEU) 접두가 아닌 '업' 시작 토큰 전부 보고.
"""
import marshal  # nosemgrep: python.lang.security.audit.marshal.marshal-usage
import re
import sys
import types
import unicodedata as ud

from PyInstaller.archive.readers import CArchiveReader

EXE = sys.argv[1] if len(sys.argv) > 1 else \
    "dist/ImmediatelyLaw/ImmediatelyLaw.exe"

UP = chr(0xC5C5)
RIGHT = UP + chr(0xB370) + chr(0xD504) + chr(0xD2B8)
pat = re.compile(UP + r"[\uAC00-\uD7A3]{1,5}")


def nm(s):
    return "-".join(ud.name(ch, "?").split()[-1] for ch in s
                    if 0xAC00 <= ord(ch) <= 0xD7A3)


def consts(code, out):
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            consts(c, out)
        elif isinstance(c, str):
            out.append(c)


r = CArchiveReader(EXE)
try:
    z = r.open_embedded_archive("PYZ.pyz")
except Exception as e:
    print("PYZ open fail:", e)
    print("CArchive toc 샘플:", list(r.toc)[:20])
    raise SystemExit(2)
names = list(z.toc)
ours = [n for n in names if n.startswith("immediatelylaw")]
print("frozen modules:", len(names), "| immediatelylaw*:", sorted(ours))
bad = 0
good = 0
for m in sorted(ours):
    try:
        obj = z.extract(m)
        co = obj if isinstance(obj, types.CodeType) else marshal.loads(  # noqa: E501  # nosemgrep: python.lang.security.audit.marshal.marshal-usage
            bytes(obj)[16:])
    except Exception:
        co = None
    if co is None:
        continue
    strs = []
    consts(co, strs)
    for s in strs:
        for mm in pat.finditer(s):
            tok = mm.group(0)
            if tok.startswith(RIGHT):
                good += 1
                continue
            bad += 1
            i = mm.start()
            print("BAD", m, "tok=" + nm(tok),
                  "ctx=" + nm(s[max(0, i - 8):i + 12]))
print("result: good(업데프트X포함)=%d bad=%d" % (good, bad))
