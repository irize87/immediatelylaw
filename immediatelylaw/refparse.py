# -*- coding: utf-8 -*-
"""클립보드/입력 텍스트에서 법령 인용을 찾아낸다.

전략: '제N조(의2 포함)' 지점을 찾은 뒤, 바로 앞의 법령명 토큰을 역축합한다.
  - 「형법」 제23조      : 인용부호 우선
  - 개인정보 보호법  제13조 : 공백 포함 법령명(조사·연결어는 제외)
  - 형법 제23조 및 같은 법 제24조 : '같은 법/동법'은 직전 법령명 사용
"""
import re

ART_RE = re.compile(r"제\s*([0-9]{1,4})\s*조(?:의([0-9]{1,3}))?")

# 법령명 어미로 인정되는 접미사(긴 것 우선)
SUFFIXES = ("시행규칙", "시행령", "법", "률", "령", "칙", "조례", "규정",
            "규칙", "요강", "지침", "고시", "훈령", "세칙")

# 법령명이 아닌 조사·접속어(역축합 중단용)
STOP_WORDS = {
    "의", "을", "를", "이", "가", "과", "와", "및", "또", "또는", "은", "는",
    "도", "로", "으로", "에서", "에게", "부터", "까지", "위", "위해",
    "따라", "따른", "근거", "근거로", "같은", "동", "같은법", "동법", "등",
    "등의", "그", "해당", "관련", "이하", "별도", "다음", "재", "또한",
    "하며", "하는", "한", "하며", "되", "며", "고", "다", "합니다",
    "규정", "같은법령",
}
# 명사로 쓰여 법령명의 일부가 될 수 있는 어절(예외)
STOP_EXCEPTION = {"법", "률", "령", "칙"}

BRACKET_RE = re.compile(
    r"[「『“\"'‘]+\s*([\u3131-\uD79A0-9a-zA-Z\s·\(\)ー\-]{2,58}?)\s*[」』”\"'’]+\s*"
    r"제\s*([0-9]{1,4})\s*조(?:의([0-9]{1,3}))?")

NAME_CHAR = re.compile(r"^[\u3131-\uD79A0-9a-zA-Z·\-ー\(\)\.]+$")


def _ends_suffix(word: str) -> bool:
    return any(word.endswith(s) for s in SUFFIXES)


def _back_name(text_before: str):
    """제N조 바로 앞 텍스트에서 법령명 후보 목록(긴 것→짧은 것). 없으면 []."""
    t = text_before.rstrip()
    t = re.sub(r"[」』””’'\)·\.,;:·]+$", "", t).rstrip()
    if not t:
        return []
    tokens = t.split()
    if not tokens:
        return []
    picked = []
    for tok in reversed(tokens):
        tok2 = tok.rstrip("」』”’'.,;:·")
        if not tok2 or not NAME_CHAR.match(tok2):
            break
        if not picked:
            if not _ends_suffix(tok2):
                break
            picked.insert(0, tok2)
            continue
        # 시행령/시행규칙 이음: "○○법 시행령"
        if picked[0] in ("시행령", "시행규칙", "시행규정", "시행준칙"):
            if _ends_suffix(tok2):
                picked.insert(0, tok2)
                continue
            break
        if tok2 in STOP_WORDS and tok2 not in STOP_EXCEPTION:
            break
        if len(" ".join(picked)) + len(tok2) > 56:
            break
        if _ends_suffix(tok2):
            break  # 다른 법령명이 앞선 경우
        picked.insert(0, tok2)
    if not picked:
        return []
    cands = []
    for i in range(len(picked)):
        c = " ".join(picked[i:])
        if _ends_suffix(c):
            cands.append(c)
    # 가장 긴 후보 뒤로 "시행령/시행규칙" 붙은 변형도 후보에 추가
    if cands:
        for sfx in ("시행령", "시행규칙"):
            cands.append(cands[0] + " " + sfx)
    return cands


def parse(text: str):
    """후보 인용 목록. [{law, art, title, index}] (문서 등장순)."""
    if not text:
        return []
    out = []
    seen = set()

    def add(law, art, idx, law_all=None):
        key = (law, art)
        if key in seen:
            return
        seen.add(key)
        out.append({"law": law, "art": art, "index": idx,
                    "law_all": law_all or [law]})

    # 인용부호형(「○○법」 제N조)을 먼저 전수 매핑
    bracket_map = {}
    for bm in BRACKET_RE.finditer(text):
        bart = bm.group(2) + (f"의{bm.group(3)}" if bm.group(3) else "")
        bracket_map[bm.start(2)] = (bm.group(1).strip(), bart)

    last_law = None
    for m in ART_RE.finditer(text):
        art = m.group(1) + (f"의{m.group(2)}" if m.group(2) else "")
        start = m.start()
        ctx = text[max(0, start - 80):start]
        law = None
        cands = []
        # 1) 인용부호 「○○법」 제N조
        hit = bracket_map.get(m.start(1))
        if hit and hit[1] == art:
            law = hit[0]
        # 2) 같은 법 / 동법
        if not law:
            if re.search(r"(같은\s*법|동\s*법|동\s*법령|같은\s*법령)\s*$", ctx):
                law = last_law
        # 3) 바로 앞 명사축합(후보 여러 개)
        if not law:
            cands = _back_name(ctx)
            law = cands[0] if cands else None
        if law:
            last_law = law
            add(law, art, start, cands or [law])
    # 제목 추출 보강: 제N조(타이틀)
    title_re = re.compile(
        r"^제\s*[0-9]+\s*조(?:의[0-9]+)?\s*[（(]([^）)]{1,40})[)）]")
    for item in out:
        m = title_re.match(text[item["index"]:item["index"] + 60])
        item["title"] = m.group(1).strip() if m else ""
    return out


def parse_query(text: str):
    """조회창 입력 파싱: '형법 23', '형법 제23조', '형법 제247조의2', '민법1' 등."""
    text = (text or "").strip()
    if not text:
        return None
    m = re.match(
        r"^(.+?)\s*제?\s*([0-9]{1,4})\s*조?\s*(?:의\s*([0-9]{1,3})\s*조?)?\s*$",
        text)
    if m:
        law = m.group(1).strip(" 「」\"'")
        art = m.group(2) + (f"의{m.group(3)}" if m.group(3) else "")
        return {"law": law, "art": art}
    return {"law": text, "art": None}
