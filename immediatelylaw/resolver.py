# -*- coding: utf-8 -*-
"""인용(법령명, 조번호) → 조문 본문. 항상 로컬 DB를 우선해 즉시 응답한다."""
import re
import time

from .db import norm_name
from . import textnorm


def _art_key(art_no: str) -> str:
    return re.sub(r"\s+", "", art_no or "")


# 줄여 부르는 기본법 이름 → 공식 법령명(기본 법률 범위 확장).
# 예: '헌법'은 대한민국헌법이지 헌법재판소법이 아니다.
NAME_ALIAS = {
    "헌법": "대한민국헌법",
    "대한민국 헌법": "대한민국헌법",
}


def _canonical(hint: str) -> str:
    return NAME_ALIAS.get(norm_name(hint), "")


_TITLE_IN_BODY = re.compile(
    r"^\s*제\s*[0-9]+(?:의[0-9]+)?\s*조\s*[（(]([^）)]{1,40})[）)]")


def _fill(res: dict) -> dict:
    """일부 법령(헌법 등)은 조문 제목이 본문 접두에 있다 — 빈 title 보강."""
    if res.get("found") and not res.get("title"):
        m = _TITLE_IN_BODY.match(res.get("body") or "")
        if m:
            res["title"] = m.group(1).strip()
    return res


def _try_local(d, hint: str, art: str):
    rows = d.search_laws_by_name(hint)
    if not rows:  # 시행예정 버전까지 마지막 시도
        h = norm_name(hint)
        rows = d.conn.execute(
            "SELECT * FROM law WHERE replace(name,' ','')=? "
            "ORDER BY enforced DESC LIMIT 3", (h,)).fetchall()
    for row in rows:
        a = d.find_article(row["mst"], art)
        if a:
            return row, a
    return None, None


def resolve(d, hint: str, art: str, api=None, hints=None):
    """dict(found, source, law_name, art_no, title, body, chap, mst, law_id,
    enforced, pending, cls) 반환. hints: 법령명 후보(긴 순)."""
    art = _art_key(art)
    hints = [h for h in (hints or [hint]) if h]
    # 기본법 약칭('헌법' 등)은 공식명을 가장 먼저 시도한다.
    canon = _canonical(hint)
    if canon and canon not in hints:
        hints.insert(0, canon)
    for h in hints:
        row, a = _try_local(d, h, art)
        if a:
            return _fill({"found": True, "source": "local",
                          "law_name": row["name"],
                          "art_no": art, "title": a["title"] or "",
                          "chap": a["chap"] or "", "body": a["body"],
                          "mst": row["mst"], "law_id": row["law_id"],
                          "enforced": row["enforced"],
                          "pending": row["pending"], "cls": row["cls"]})
    # 자치법규(파일/API 등록)
    for h in hints:
        for lrow in d.local_search(h):
            la = d.local_find(lrow["id"], art)
            if la:
                return _fill({"found": True, "source": "local-reg",
                              "law_name": lrow["name"], "art_no": art,
                              "title": la["title"] or "", "chap": "",
                              "body": la["body"], "mst": None,
                              "law_id": None,
                              "enforced": "", "pending": 0,
                              "cls": lrow["kind"] or "자치법규"})
    # 라이브(OC 키가 있을 때만): fetch 후 로컬에 캐시 → 이후 즉시
    if api is not None:
        for h in hints:
            cur = api.resolve_current(h)
            if not cur:
                continue
            law, arts = api.fetch_full(cur["mst"])
            if law.get("law_id"):
                keys = {norm_name(law["name"])}
                if law.get("short"):
                    keys.add(norm_name(law["short"]))
                d.replace_law(law, arts, [k for k in keys if k],
                              action="on-demand")
            for x in arts:
                if _art_key(x["art_no"]) == art:
                    return _fill({"found": True, "source": "live",
                                  "law_name": law["name"], "art_no": art,
                                  "title": x.get("title") or "",
                                  "chap": x.get("chap") or "",
                                  "body": x["body"], "mst": law["mst"],
                                  "law_id": law["law_id"],
                                  "enforced": law["enforced"],
                                  "pending": law["pending"],
                                  "cls": law["cls"]})
    return {"found": False}


def verify(d, api, res: dict):
    """표시된 조문이 최신인지 확인.
    반환: ('current'|'check'|'offline', 설명)
    설명 문구는 카드 하단 '최신화 일자' 표시로 쓰인다."""
    def _mdd(ver):
        return f"{ver[4:6]}.{ver[6:8]}" if len(ver) >= 8 else ver

    if not res or not res.get("found"):
        return "check", "조문을 찾을 수 없음"
    if res["source"] == "local-reg":
        return "current", "등록된 자치법규 파일 기준"
    ver = d.get_meta("data_ver", "")
    # 라이브 키 있음: 법제처 현행과 직접 비교
    if api is not None:
        try:
            cur = api.resolve_current(res["law_name"])
        except Exception:
            return "offline", f"오프라인 · 데이터 {_mdd(ver)} 기준"
        if not cur:
            return "check", "법제처에서 법령을 찾지 못함"
        if cur["mst"] == res.get("mst") and cur["enforced"] == res.get("enforced"):
            return "current", "법제처 실시간 확인 · 현행"
        # 버전이 다름 → 해당 조문 원문 비교
        try:
            x = api.fetch_article(cur["mst"], res["art_no"])
        except Exception:
            return "offline", f"오프라인 · 데이터 {_mdd(ver)} 기준"
        if x is None:
            return "check", "현행판에 해당 조문 없음(신설/삭제?)"
        if textnorm.normalize(x["body"]) == textnorm.normalize(res["body"]):
            return "current", "법제처 실시간 확인 · 현행"
        return "check", "현행 조문과 다름(데이터 갱신 필요)"
    # 키 없음: 배포 데이터 기준
    try:
        dver = time.strptime(ver[:8], "%Y%m%d")
        age = (time.time() - time.mktime(dver)) / 86400
    except Exception:
        return "check", "데이터 기준일 없음"
    if res.get("pending"):
        return "check", "시행예정 버전 표시"
    if age <= 7:
        return "current", f"데이터 {_mdd(ver)} 기준 · 현행"
    return "check", f"데이터가 {int(age)}일 전({_mdd(ver)})"
