# -*- coding: utf-8 -*-
"""법령 텍스트 정규화(현행 여부 비교용)."""
import re
import unicodedata

_REMOVE = re.compile(
    r"[\s\*\†\‡\＊\∘\uf0fc\u200b\ufeff·]"      # 공백·주석부호
)
_PAREN = str.maketrans({"（": "(", "）": ")", "［": "[", "］": "]"})


def normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_PAREN)
    s = _REMOVE.sub("", s)
    # 별표/주해 인용 각주는 비교에서 제외
    s = re.sub(r"[＜<]개정>", "", s)
    return s
