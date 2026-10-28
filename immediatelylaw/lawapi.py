# -*- coding: utf-8 -*-
"""국가법령정보 공동활용 DRF API 클라이언트.

- 목록: lawSearch.do (무query = 현행 법령 전체, 페이징)
- 전문: lawService.do type=XML MST=... (조문 단위 파싱)
"""
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

BASE = "https://www.law.go.kr/DRF"


class LawApiError(Exception):
    pass


class LawApi:
    def __init__(self, oc_key: str, min_interval=0.35):
        self.oc = (oc_key or "").strip()
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "JisiloLaw/0.1"})
        self._min_interval = min_interval
        self._last = 0.0
        self._lock = threading.Lock()

    # ---- 기반 ----
    def _get(self, url, params=None, tries=4, timeout=25):
        if not self.oc:
            raise LawApiError("OC 키가 설정되지 않았습니다.")
        wait = 1.0
        last_err = None
        for _ in range(tries):
            with self._lock:
                gap = time.time() - self._last
                if gap < self._min_interval:
                    time.sleep(self._min_interval - gap)
                self._last = time.time()
            try:
                p = dict(params or {})
                p.update({"OC": self.oc, "type": p.get("type", "JSON")})
                r = self.s.get(url, params=p, timeout=timeout)
                if r.status_code == 200:
                    r.encoding = "utf-8"
                    body = r.text
                    if body and len(body) > 10:
                        return body
                    last_err = LawApiError("빈 응답")
                else:
                    last_err = LawApiError(f"HTTP {r.status_code}")
            except requests.RequestException as e:
                last_err = LawApiError(f"네트워크 오류: {e}")
            time.sleep(wait)
            wait = min(wait * 2, 8)
        raise last_err

    # ---- 목록 ----
    def search(self, query="", page=1, disp=100, cls=None):
        """현행 법령 목록/검색. (total, [row]) 반환. row: mst/law_id/name/..."""
        p = {"OC": None, "target": "law", "type": "JSON",
             "display": str(min(int(disp), 100)), "page": str(page)}
        if query:
            p["query"] = query
        if cls:
            p["lsClsCd"] = cls
        import json
        body = self._get(f"{BASE}/lawSearch.do", {k: v for k, v in p.items()
                                                  if k != "OC" and v})
        try:
            j = json.loads(body)["LawSearch"]
        except Exception as e:
            raise LawApiError(f"목록 응답 파싱 실패: {e}")
        total = int(j.get("totalCnt", "0") or 0)
        laws = j.get("law") or []
        if isinstance(laws, dict):      # 결과가 1건이면 dict 하나로 온다
            laws = [laws]
        out = []
        for x in laws:
            out.append({
                "mst": int(x["법령일련번호"]),
                "law_id": x.get("법령ID", ""),
                "name": x.get("법령명한글", "").strip(),
                "short": (x.get("법령약칭명") or "").strip(),
                "cls": x.get("법령구분명", ""),
                "promulgated": x.get("공포일자", ""),
                "enforced": x.get("시행일자", ""),
                "agency": x.get("소관부처명", ""),
            })
        return total, out

    def iter_current_laws(self, page_size=100, max_pages=300):
        """현행 법령 전체 열거(무query)."""
        page, seen = 1, set()
        while page <= max_pages:
            total, rows = self.search(page=page, disp=page_size)
            if not rows:
                break
            for r in rows:
                if r["mst"] not in seen:
                    seen.add(r["mst"])
                    yield r
            if page * page_size >= total or len(rows) < page_size:
                break
            page += 1

    def resolve_current(self, name: str):
        """법령명으로 현행 버전 검색. dict 또는 None."""
        best = None
        total, rows = self.search(query=f'"{name}"', disp=10)
        if not rows:
            total, rows = self.search(query=name, disp=10)
        target = re.sub(r"\s+", "", name)
        for r in rows:
            if re.sub(r"\s+", "", r["name"]) == target:
                return r
            if r["short"] and re.sub(r"\s+", "", r["short"]) == target:
                best = best or r
        return best or (rows[0] if rows else None)

    # ---- 전문 ----
    def fetch_full(self, mst: int):
        """MST로 법령 전문. returns (law_dict, [article_dict])."""
        xml_text = self._get(f"{BASE}/lawService.do",
                             {"target": "law", "type": "XML", "MST": str(mst)})
        return self._parse_full(xml_text, mst)

    @staticmethod
    def _parse_full(xml_text, mst):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            raise LawApiError(f"전문 XML 파싱 실행: {e}")

        def txt(el, tag):
            t = el.find(tag)
            return (t.text or "").strip() if t is not None and t.text else ""

        base = root.find("기본정보")
        if base is None:
            raise LawApiError("기본정보 없음(권한/키 오류 가능)")
        name = txt(base, "법령명_한글")
        law = {
            "mst": mst,
            "law_id": txt(base, "법령ID"),
            "name": name,
            "short": txt(base, "법령명약칭"),
            "cls": (base.findtext("법종구분") or "").strip(),
            "promulgated": txt(base, "공포일자"),
            "enforced": txt(base, "시행일자"),
            "agency": (base.find("소관부처").text or "").strip()
                      if base.find("소관부처") is not None else "",
        }
        try:
            today = time.strftime("%Y%m%d")
            law["pending"] = 1 if law["enforced"] and law["enforced"] > today else 0
        except Exception:
            law["pending"] = 0

        arts, chap, ordn = [], "", 0
        zm = root.find("조문")
        if zm is None:
            return law, arts
        for u in zm.findall("조문단위"):
            content = (u.findtext("조문내용") or "").strip()
            kind = (u.findtext("조문여부") or "").strip()
            # 항(①②…)은 조문단위 자식으로 분리 제공 → 본문에 병합
            hangs = u.findall("항")
            if hangs:
                extra = []
                for h in hangs:
                    hc = (h.findtext("항내용") or "").strip()
                    if hc and hc not in content:
                        extra.append(hc)
                if extra:
                    content = "\n".join([content] + extra)
            m = re.match(r"^제\s*([0-9]+)\s*조(?:의([0-9]+))?\s*(?:[（(]([^）)]*)[)）])?",
                         content)
            if m:
                ordn += 1
                no = m.group(1) + (f"의{m.group(2)}" if m.group(2) else "")
                arts.append({
                    "art_no": no,
                    "title": m.group(3) or (u.findtext("조문제목") or "").strip(),
                    "chap": chap,
                    "body": content,
                    "ord": ordn,
                })
            elif kind in ("편", "장", "절", "관") or re.match(
                    r"^제[0-9]+(?:의[0-9]+)?(?:편|장|절|관)", content):
                if content:
                    chap = content
        return law, arts

    def fetch_article(self, mst: int, art_no: str):
        _, arts = self.fetch_full(mst)
        a = re.sub(r"\s+", "", art_no)
        for x in arts:
            if re.sub(r"\s+", "", x["art_no"]) == a:
                return x
        return None

    def ping(self):
        total, rows = self.search(query="형법", disp=1)
        return total > 0
