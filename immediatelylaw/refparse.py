# -*- coding: utf-8 -*-
"""클립보드/입력 텍스트에서 법령 인용을 찾아낸다.

전략: '제N조(의2 포함)' 지점을 찾은 뒤, 바로 앞의 법령명 토큰을 역축합한다.
  - 「형법」 제23조      : 인용부호 우선
  - “민법 제750조”       : 인용부호가 법령명+조문 전체를 감싼 형태
  - 개인정보 보호법  제13조 : 공백 포함 법령명(조사·연결어는 제외)
  - 형법 제23조 및 같은 법 제24조 : '같은 법/동법'은 직전 법령명 사용
"""
import re

ART_RE = re.compile(r"제\s*([0-9]{1,4})\s*조(?:의([0-9]{1,3}))?")

# 법령명 어미로 인정되는 접미사(긴 것 우선)
SUFFIXES = ("시행규칙", "시행령", "법", "률", "령", "칙", "조례", "규정", "규칙", "요강",
             "지침", "고시", "훈령", "세칙", "예규", "강령", "요령", "절차")

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

# Generic administrative-rule tail words (whitespace-stripped form).
# A candidate made only of these words is NOT a law name -- it is the
# tail of some longer title, and handing it to the fuzzy DB tiers turns
# 'GANG-RYEONG art.3' into a lottery hit like '...GANG-RYEONG'.
GENERIC_TAILS = frozenset((
    "법", "률", "령", "칙", "시행규칙", "시행령", "조례", "규정", "규칙", "요강", "지침", "고시",
    "훈령", "세칙", "예규", "강령", "요령", "절차", "시행규정", "시행준칙", "운영규정", "운영세칙",
    "처리요령"))

def _is_generic(name: str) -> bool:
    return re.sub(r"[\s\u3000]+", "", name) in GENERIC_TAILS

# Title-tail tokens that mark a registrable self-governance rule file
# (localreg.NAME_HINT policy, single source here).
LOCAL_TAIL_HINTS = (
    "조례", "규칙", "규정", "훈령", "예규", "고시", "지침", "요강", "강령", "요령", "절차", "세칙")

BRACKET_RE = re.compile(
    r"[「『“\"'‘]+\s*([\u3131-\uD79A0-9a-zA-Z\s·\(\)ー\-]{2,58}?)\s*[」』”\"'’]+\s*"
    r"제\s*([0-9]{1,4})\s*조(?:의([0-9]{1,3}))?")

# 인용부호가 법령명뿐 아니라 조문까지 함께 감싼 형태: "○○법 제15조", 「○○법 제15조」.
# BRACKET_RE는 닫는 부호가 조 앞에 있어야 하므로 두 패턴은 겹치지 않는다.
# 이름 문자 클래스에 인용부호·문장부호가 없어 다른 문장으로 번지지 않는다.
# (가드) 이름이 중간에 '제+숫자'를 삼키면 여러 조문을 한 쌍의 따옴표로 감싼
# 입력에서 잘못된 장문 후보가 생기므로, 그런 확장만 막는다.
_NAME_NO_ART = r"(?:(?!제\s*[0-9])[\u3131-\uD79A0-9a-zA-Z\s·\(\)ー\-])"
QUOTE_FULL_RE = re.compile(
    r"[「『“\"'‘]\s*(" + _NAME_NO_ART + r"{2,58}?)\s*"
    r"제\s*([0-9]{1,4})\s*조(?:의([0-9]{1,3}))?\s*[」』”\"'’]")

# 여는 인용부호(역축합에서 토큰 앞면만 제거; 이 부호=법령명의 시작 경계)
OPEN_QUOTES = "「『“\"'‘"

NAME_CHAR = re.compile(r"^[\u3131-\uD79A0-9a-zA-Z·\-ー\(\)\.]+$")

# 법령명에서 위임 법령 접미사를 벗긴 '본법' 이름으로 만든다
DELEG_RE = re.compile(r"\s*(시행령|시행규칙|시행규정|시행준칙)$")


def base_name(name: str) -> str:
    """'○○법 시행령' → '○○법'. 본법 이름 반환('같은 법' 해석의 기준)."""
    return DELEG_RE.sub("", name or "").strip()


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
        # 앞에만 붙은 여는 인용부호 제거(예: '“개인정보'). 그 따옴표가 인용의
        # 시작이므로 처리 이후로는 법령명 앞 문장 쪽으로 절대 넘지 않는다.
        quoted_head = False
        while tok2 and tok2[0] in OPEN_QUOTES:
            tok2 = tok2[1:]
            quoted_head = True
        if not tok2 or not NAME_CHAR.match(tok2):
            break
        if not picked:
            if not _ends_suffix(tok2):
                break
            picked.insert(0, tok2)
            if quoted_head:
                break
            continue
        # 시행령/시행규칙 이음: "○○법 시행령"
        if picked[0] in ("시행령", "시행규칙", "시행규정", "시행준칙"):
            if _ends_suffix(tok2):
                picked.insert(0, tok2)
                if quoted_head:
                    break
                continue
            break
        if tok2 in STOP_WORDS and tok2 not in STOP_EXCEPTION:
            break
        if len(" ".join(picked)) + len(tok2) > 56:
            break
        if _ends_suffix(tok2):
            break  # 다른 법령명이 앞선 경우
        picked.insert(0, tok2)
        if quoted_head:
            break
    if not picked:
        return []
    cands = []
    for i in range(len(picked)):
        c = " ".join(picked[i:])
        if not _ends_suffix(c):
            continue
        if _is_generic(c):
            continue  # tail-word-only fragment: not a law-name candidate
        cands.append(c)
    # 가장 긴 후보 뒤로 "시행령/시행규칙" 붙은 변형도 후보에 추가
    if cands:
        for sfx in ("시행령", "시행규칙"):
            cands.append(cands[0] + " " + sfx)
    return cands


def parse(text: str, prev_law: str = ""):
    """후보 인용 목록. [{law, art, title, index}] (문서 등장순).
    prev_law: 직전 조회/표시로 기억된 본법 이름 — 텍스트 단독으로
    '같은 법 시행령 제19조'처럼만 표기된 인용을 해석할 때 쓴다."""
    if not text:
        return []
    out = []
    seen = set()
    last_law = base_name(prev_law) or None
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
    # 인용부호가 조문까지 감싼 형태("○○법 제N조"). 같은 조 위치에서는
    # 「…」 제N조 형태가 이미 잡았으므로 그것이 우선한다(setdefault).
    for qm in QUOTE_FULL_RE.finditer(text):
        qart = qm.group(2) + (f"의{qm.group(3)}" if qm.group(3) else "")
        bracket_map.setdefault(qm.start(2), (qm.group(1).strip(), qart))

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
        # 2) 같은 법 / 동법 (+ 시행령·시행규칙 변형): "같은 법 시행령 제19조"
        mm = re.search(
            r"(?:같은\s*법|동\s*법|같은\s*법령|동\s*법령)\s*"
            r"(시행령|시행규칙|시행규정)?\s*$", ctx)
        if mm and last_law:
            sfx = mm.group(1) or ""
            law = last_law + (f" {sfx}" if sfx else "")
            cands = [law]
        # 3) 바로 앞 명사축합(후보 여러 개). '같은 법' 어구인데 직전
        #    법령이 없으면 축합 시도로 잘못된 법령을 잡지 않고 건너뛴다.
        if not law and not mm:
            cands = _back_name(ctx)
            law = cands[0] if cands else None
        if law:
            last_law = base_name(law)
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
