# -*- coding: utf-8 -*-
"""defusedxml 전환 검증: 정상 hwpx 파싱 + 외부 엔티티 차단."""
import io
import os
import sys
import zipfile

sys.path.insert(0, ".")
from immediatelylaw import localreg  # noqa: E402

# 1) 정상 hwpx 형태의 zip+xml
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("mimetype", "application/hwp+zip")
    z.writestr(
        "Contents/section0.xml",
        '<hs:sec xmlns:hs="x"><hs:p><hs:t>테스트 조례</hs:t></hs:p>'
        '<hs:p><hs:t>제1조(목적) 이 조례는 가나다를 목적으로 한다.</hs:t>'
        '</hs:p></hs:sec>')
open("_t_sample.hwpx", "wb").write(buf.getvalue())
name, arts = localreg.parse_regulation(
    localreg._read_text("_t_sample.hwpx"), "sample")
print("good hwpx:", name, len(arts))

# 2) 외부 엔티티(SSRF/파일열람) 악성 xml
buf2 = io.BytesIO()
with zipfile.ZipFile(buf2, "w") as z:
    z.writestr(
        "Contents/section0.xml",
        '<?xml version="1.0"?>'
        '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///c:/windows/win.ini")]>'
        '<hs:sec xmlns:hs="x"><hs:p><hs:t>&e;</hs:t></hs:p></hs:sec>')
open("_t_evil.hwpx", "wb").write(buf2.getvalue())
try:
    localreg._read_text("_t_evil.hwpx")
    print("EVIL NOT BLOCKED!!")
except Exception as e:
    print("evil blocked:", type(e).__name__)

os.remove("_t_sample.hwpx")
os.remove("_t_evil.hwpx")
