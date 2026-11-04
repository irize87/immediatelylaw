# -*- coding: utf-8 -*-
"""자치법규 파일 등록기. regulations/ 폴더의 파일을 국가지방법령과 같은 형태로 색인.

지원: .txt/.md(UTF-8/CP949), .hwpx/.docx(zip+xml), .pdf(pypdf),
      .doc/.rtf(RTF 형태 포함 — 실제 유포의 다수), .hwp(HWPML XML 또는
      HWP5 OLE: zlib 스트림 탐색으로 본문 XML 복구)

파일 형식 규칙(가장 간단):
    서울특별시 주차장 조례        ← 첫 줄 = 조례명(생략 시 파일명 사용)
    제1조(목적) 이 조례는 …      ← 조문 시작. 다음 제N조까지 본문.
"""
import io
import os
import re
import time
import zlib
import zipfile
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError as XMLParseError
from defusedxml.ElementTree import fromstring as XML_fromstring

from .db import Database, norm_name, DATA_DIR
from .refparse import LOCAL_TAIL_HINTS

REG_DIR = os.path.join(DATA_DIR, "regulations")

ART_HEAD = re.compile(r"^\s*(제\s*[0-9]+(?:의[0-9]+)?\s*조(?:\s*\([^)\n]{1,40}\))?)\s*")
NAME_HINT = re.compile("(" + "|".join(LOCAL_TAIL_HINTS) + ")$")
# 조례명 검색 시 건너뛰는 헤더/각주성 라인 (PDF 앞부분 잡음)
NOISE = re.compile(r"법제처|국가법령정보센터|법령번호|검색결과|페이지"
                   r"|^\d+\s*$|^http|대한민국 법령|^@")
STOP = re.compile(r"^\s*(부\s*칙|별\s*표|붙\s*임)")


# ─────────────────────────── 포맷별 텍스트 추출 ───────────────────────────
def _read_text(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:4] == b"PK\x03\x04":                       # hwpx / docx
        return _read_zip_xml(raw)
    if raw[:5] == b"%PDF-":
        return _read_pdf(path)
    if raw[:4] == b"\xd0\xcf\x11\xe0":                 # hwp5(ole) / doc(ole)
        return _read_ole(raw)
    if raw[:5] == b"{\\rtf":                            # rtf(.doc로 유포됨 포함)
        return _read_rtf(raw)
    head = raw[:200].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<HWPML"):
        return _read_hwpml(raw.decode("utf-8", "replace"))
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _read_zip_xml(raw: bytes) -> str:
    """hwpx(Contents|Documents/sectionN.xml) 및 docx(word/document.xml)."""
    lines = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        sections = sorted(n for n in names
                          if re.search(r"(Contents|Documents)/section\d*\.xml$", n)
                          or re.match(r"section\d*\.xml$", n))
        if sections:                                   # hwpx (hp:p / hp:t)
            for n in sections:
                if z.getinfo(n).file_size > 50_000_000:
                    raise ValueError("본문 XML이 비정상적으로 큽니다.")
                root = XML_fromstring(z.read(n))
                for el in root.iter():
                    if _local(el.tag) == "p":
                        t = "".join(x.text or "" for x in el.iter()
                                    if _local(x.tag) == "t")
                        if t:
                            lines.append(t)
            return "\n".join(lines)
        if "word/document.xml" in names:               # docx
            if z.getinfo("word/document.xml").file_size > 50_000_000:
                raise ValueError("본문 XML이 비정상적으로 큽니다.")
            root = XML_fromstring(z.read("word/document.xml"))
            for p in root.iter():
                if _local(p.tag) == "p":
                    lines.append("".join(t.text or "" for t in p.iter()
                                         if _local(t.tag) == "t"))
            return "\n".join(lines)
    raise ValueError("hwpx/docx 본문 XML을 찾지 못했습니다.")


def _read_pdf(path: str) -> str:
    from pypdf import PdfReader
    r = PdfReader(path)
    return "\n".join((pg.extract_text() or "") for pg in r.pages)


def _read_rtf(raw: bytes) -> str:
    """RTF → 텍스트. \\uN 유니코드, \\'hh(ASCII/cp949 쌍), \\par\\cell 처리."""
    for kw in (b"fonttbl", b"colortbl", b"stylesheet", b"info", b"generator",
               b"listtable", b"listoverridetable", b"themedata",
               b"colorschememapping", b"latentstyles", b"xmlnstbl", b"pntext"):
        raw = re.sub(rb"\{" + kw + rb"\b[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", b"", raw)
    out: list = []
    text = bytearray()
    i, n = 0, len(raw)

    def eol():
        nonlocal text
        out.append(bytes(text))
        text = bytearray()

    while i < n:
        c = raw[i]
        if c == 0x7B:                                   # '{'
            i += 1
            if raw[i:i + 2] in (b"\\*", b"\\shp", b"\\pict"):
                depth, i = 1, i + 2
                while i < n and not (0x61 <= raw[i] <= 0x7A):
                    i += 1
                while i < n and depth:
                    if raw[i] == 0x7B:
                        depth += 1
                    elif raw[i] == 0x7D:
                        depth -= 1
                    i += 1
            continue
        if c == 0x7D:                                   # '}' — 그룹만 닫고 라인은 유지
            i += 1
            continue
        if c == 0x5C:                                   # '\'
            m = re.match(rb"\\([a-zA-Z]+)(-?\d{1,10})? ?", raw[i:])
            if m:
                word, num = m.group(1), m.group(2)
                i += m.end()
                if word in (b"par", b"line", b"sect", b"row", b"nestcell"):
                    eol()
                elif word in (b"cell", b"tab"):
                    text += b" "
                elif word == b"u" and num is not None:
                    code = int(num)
                    if code < 0:
                        code += 65536
                    text += chr(code).encode("utf-8")
                    if raw[i:i + 1] == b"?":            # 대체 문자 소비
                        i += 1
                continue
            if raw[i:i + 2] == b"\\'":
                try:
                    b0 = int(raw[i + 2:i + 4], 16)
                    i += 4
                except ValueError:
                    i += 2
                    continue
                if 0x81 <= b0 <= 0xFE:
                    m2 = re.match(rb"\\'([0-9a-fA-F]{2})", raw[i:])
                    if m2 and 0x41 <= int(m2.group(1), 16) <= 0xFE:
                        try:
                            pair = bytes([b0, int(m2.group(1), 16)])
                            text += pair.decode("cp949").encode("utf-8")
                            i += m2.end()
                            continue
                        except UnicodeDecodeError:
                            pass
                text += bytes([b0 if b0 < 0x80 else 0x20])
                continue
            if raw[i:i + 2] in (b"\\\\", b"\\{", b"\\}"):
                text += raw[i + 1:i + 2]
                i += 2
                continue
            i += 1
            continue
        if c not in (0x0A, 0x0D):
            text += bytes([c])
        i += 1
    if text:
        eol()
    buf = b"\n".join(x for x in out if x)
    return buf.decode("utf-8", "replace")


_ENT = {"&nbsp;": " ", "&lt;": "<", "&gt;": ">", "&amp;": "&",
        "&quot;": '"', "&#160;": " "}


def _unescape(s: str) -> str:
    for k, v in _ENT.items():
        s = s.replace(k, v)
    return s


def _read_hwpml(raw: str) -> str:
    """법제처 내보내기 HWPML 2.1(.hwp/.xml) → 텍스트. 본문은 <P>(본문)/
    <PARA>(표 안) 블록이고 문자열은 <CHAR> 안에 있다."""
    m = re.search(r"<TITLE>([^<]+)</TITLE>", raw)
    lines = [_unescape(m.group(1).strip())] if m else []
    for pm in re.finditer(r"<(?:P|PARA)\b[^>]*>(.*?)</(?:P|PARA)\s*>",
                          raw, re.S):
        txt = _unescape("".join(
            re.findall(r"<CHAR>([^<]*)</CHAR>", pm.group(1))))
        if txt.strip():
            lines.append(txt.strip())
    if len(lines) <= 1:                                # 최후 수단
        lines = [_unescape(m.group(1).strip())] if m else []
        for cm in re.finditer(r"<CHAR>([^<]+)</CHAR>", raw):
            lines.append(_unescape(cm.group(1)))
    return "\n".join(lines)


def _read_ole(raw: bytes) -> str:
    """OLE 컨테이너. hwp5는 zlib XML 스트림, doc은 UTF-16 조각 추출 시도."""
    texts = []
    i = 0
    while len(texts) == 0:
        i = raw.find(b"\x78\x9c", i)
        if i < 0:
            break
        try:
            data = zlib.decompressobj(15).decompress(raw[i:], 8_000_000)
        except zlib.error:
            i += 1
            continue
        if b"<" in data[:200] and (b"wp:section" in data[:2000]
                                   or b"hwp" in data[:2000].lower()
                                   or b"<hp:" in data[:200]):
            try:
                root = XML_fromstring(data)
                for el in root.iter():
                    if _local(el.tag) == "p":
                        t = "".join(x.text or "" for x in el.iter()
                                    if _local(x.tag) == "t")
                        if t:
                            texts.append(t)
            except (XMLParseError, DefusedXmlException):
                pass
        i += 1
    if texts:
        return "\n".join(texts)
    idx = raw.find(b"WordDocument")                    # Word97 .doc 최후 수단
    if idx >= 0:
        u = raw[idx:].decode("utf-16-le", "ignore")
        lines = [ln.strip() for ln in u.splitlines() if re.search(r"[가-힣]", ln)]
        if lines:
            return "\n".join(lines)
    raise ValueError("HWP/DOC 바이너리 본문을 복구하지 못했습니다. "
                     "HWPX나 PDF로 다시 저장해 넣으면 바로 등록됩니다.")


# ─────────────────────────── 조문 파싱 ───────────────────────────
def parse_regulation(text: str, fallback_name: str):
    """텍스트 → (law_name, [{art_no,title,body,ord}])."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    name = fallback_name
    body_start = 0
    for i, ln in enumerate(lines[:10]):
        t = re.sub(r"^#+\s*", "", ln).strip()
        if not t or NOISE.search(t):
            continue
        if ART_HEAD.match(t):
            break
        if NAME_HINT.search(t) and len(t) <= 120:
            name = t
            body_start = i + 1
            break
    arts, cur = [], None
    ordn = 0
    for ln in lines[body_start:]:
        if STOP.match(ln):                             # 부칙/별표 이후는 버린다
            break
        m = ART_HEAD.match(ln)
        if m:
            head = re.sub(r"\s+", "", m.group(1))
            no = re.match(r"제([0-9]+(?:의[0-9]+)?)조", head).group(1)
            title = re.search(r"\(([^)]*)\)", head)
            ordn += 1
            cur = {"art_no": no, "title": title.group(1) if title else "",
                   "body": ln.strip(), "ord": ordn}
            arts.append(cur)
        elif cur and ln.strip():
            cur["body"] += "\n" + ln.strip()
    return name, arts


def import_file(d: Database, path: str):
    """파일 1개 등록/갱신. (law_name, 조문수) 반환."""
    text = _read_text(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    name, arts = parse_regulation(text, stem)
    if not arts:
        raise ValueError("조문(제N조…)을 찾지 못했습니다.")
    old = d.conn.execute("SELECT id FROM local_law WHERE source=?",
                         (path,)).fetchone()
    now = time.strftime("%Y-%m-%d %H:%M")
    with d._lock:
        if old:
            lid = old["id"]
            d.conn.execute("DELETE FROM local_article WHERE lid=?", (lid,))
            d.conn.execute("UPDATE local_law SET name=?, added_at=? WHERE id=?",
                           (name, now, lid))
        else:
            cur = d.conn.execute(
                "INSERT INTO local_law(name,source,kind,added_at) "
                "VALUES(?,?,?,?)", (name, path, "자치법규", now))
            lid = cur.lastrowid
        d.conn.executemany(
            "INSERT OR REPLACE INTO local_article(lid,art_no,title,body,ord) "
            "VALUES(?,?,?,?,?)",
            [(lid, a["art_no"], a["title"], a["body"], a["ord"]) for a in arts])
        d.conn.execute("INSERT OR REPLACE INTO alias(key,law_id) VALUES(?,?)",
                       (norm_name(name), f"local:{lid}"))
        d.conn.commit()
    return name, len(arts)


def scan_dir(d: Database, reg_dir: str = REG_DIR):
    """폴더 전체 스캔. (성공 목록, 실패 목록) 반환. 파일 삭제분도 정리."""
    os.makedirs(reg_dir, exist_ok=True)
    ok, fail = [], []
    present = set()
    for fn in sorted(os.listdir(reg_dir)):
        p = os.path.join(reg_dir, fn)
        if not os.path.isfile(p):
            continue
        if os.path.splitext(fn)[1].lower() not in (
                ".txt", ".md", ".hwpx", ".hwp", ".pdf", ".doc", ".docx",
                ".rtf"):
            continue
        present.add(os.path.abspath(p))
        try:
            name, n = import_file(d, p)
            ok.append((fn, name, n))
        except Exception as e:
            fail.append((fn, str(e)))
    # 삭제된 파일 정리
    for row in d.conn.execute(
            "SELECT id, name, source FROM local_law").fetchall():
        if row["source"] and os.path.isabs(row["source"]) \
                and os.path.abspath(row["source"]) not in present:
            d.conn.execute("DELETE FROM local_law WHERE id=?", (row["id"],))
            d.conn.execute("DELETE FROM local_article WHERE lid=?",
                           (row["id"],))
            d.conn.commit()
    return ok, fail
