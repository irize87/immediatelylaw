# -*- coding: utf-8 -*-
"""백그라운드 워커: 검증, 데이터 갱신(GitHub 배포), 온디맨드 수집."""
import hashlib
import lzma
import os
import tempfile

import requests
from PySide6.QtCore import QThread, Signal

from . import resolver
from .db import DB_PATH


def bundled_snapshot():
    """오프라인 배포용 동봉 스냅샷(immediatelylaw-<ver>.db.xz) 경로.
    exe 배포본 = exe와 같은 폴더(또는 data/), 개발 중 = data/dist/."""
    import glob
    import sys
    base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(DB_PATH))
    cands = []
    for d in (base, os.path.join(base, "data"), os.path.join(base, "dist")):
        cands += glob.glob(os.path.join(d, "immediatelylaw-*.db.xz"))
    return sorted(cands)[-1] if cands else None


def install_xz(xz_path):
    """xz 스냅샷을 풀어 새 DB 파일 경로를 반환(적용은 reload_from_file)."""
    new_db = DB_PATH + ".new"
    with lzma.open(xz_path, "rb") as fin, open(new_db, "wb") as fout:
        while True:
            b = fin.read(1 << 20)
            if not b:
                break
            fout.write(b)
    return new_db


class ResolveWorker(QThread):
    """DB 미보유 법령의 라이브 폴백(OC 키) 포함 해석."""
    done = Signal(dict)   # resolver.resolve 결과

    def __init__(self, db, api, hint, art, hints=None, parent=None):
        super().__init__(parent)
        self.db, self.api, self.hint, self.art = db, api, hint, art
        self.hints = hints

    def run(self):
        try:
            res = resolver.resolve(self.db, self.hint, self.art, self.api,
                                   hints=self.hints)
        except Exception as e:
            res = {"found": False, "error": str(e)}
        self.done.emit(res)


class VerifyWorker(QThread):
    """표시된 조문의 현행 여부 확인 → (kind, message)."""
    done = Signal(str, str)

    def __init__(self, db, api, res, parent=None):
        super().__init__(parent)
        self.db, self.api, self.res = db, api, res

    def run(self):
        try:
            kind, msg = resolver.verify(self.db, self.api, self.res)
        except Exception as e:
            kind, msg = "check", f"검증 오류: {e}"
        self.done.emit(kind, msg)


class UpdaterWorker(QThread):
    """GitHub(raw) 배포본으로 로컬 DB를 최신화. 네트워크 없으면 조용히 실패."""
    progress = Signal(str, int)          # message, percent(-1 =_indeterminate)
    done = Signal(bool, str)             # ok, message
    db_replaced = Signal(str)            # 새 DB 파일 경로(app에서 재오픈)

    def __init__(self, db, base_url, apply_deltas=True, parent=None):
        super().__init__(parent)
        self.db, self.base_url = db, (base_url or "").rstrip("/")
        self.apply_deltas = apply_deltas

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.done.emit(False, f"갱신 실패: {e}")

    # ---- 내부 ----
    def _get(self, url, stream=False, timeout=30):
        r = requests.get(url, timeout=timeout, stream=stream,
                         headers={"User-Agent": "immediatelylaw-updater"})
        r.raise_for_status()
        return r

    def _run(self):
        if not self.base_url:
            self.done.emit(False, "데이터 소스(URL)가 설정되지 않았습니다. "
                                  "설정 › 데이터에서 배포 주소를 입력하세요.")
            return
        stats = self.db.stats()
        self.progress.emit("버전 정보 확인 중…", -1)
        manifest = self._get(f"{self.base_url}/manifest.json").json()
        snap = manifest.get("snapshot", {})
        url = snap.get("url") or f"{self.base_url}/{snap.get('file','')}"
        if not snap.get("file"):
            self.done.emit(False, "manifest에 스냅샷 정보가 없습니다.")
            return

        need_snapshot = stats["laws"] == 0 or not self.apply_deltas
        applied = 0
        if not need_snapshot:
            local_ver = self.db.get_meta("data_ver", "")
            if local_ver >= manifest.get("data_ver", ""):
                self.done.emit(True, f"이미 최신입니다 (데이터 {local_ver}).")
                return
            applied = self._try_deltas(manifest, local_ver)
            need_snapshot = applied < 0
        if need_snapshot:
            new_path = self._download_snapshot(manifest)
            self.db_replaced.emit(new_path)
            self.done.emit(True, f"전체 데이터 적용 완료 "
                                 f"(데이터 {manifest.get('data_ver','')})")
            return
        self.db.set_meta("data_ver", manifest.get("data_ver", ""))
        self.db.set_meta("built_at", manifest.get("updated", ""))
        self.done.emit(True, f"델타 {applied}건 반영 완료 "
                             f"(데이터 {manifest.get('data_ver','')})")

    def _try_deltas(self, manifest, local_ver):
        """적용 성공 시 반영 건수(0 이상), 실패 시 -1."""
        deltas = [d for d in manifest.get("deltas", [])
                  if d.get("from", "") >= local_ver]
        deltas.sort(key=lambda d: d["from"])
        if not deltas:
            return -1
        total = 0
        for d in deltas:
            f = d["file"]
            try:
                self.progress.emit(f"개정 반영 {f} …", -1)
                r = requests.get(d.get("url") or f"{self.base_url}/{f}",
                                 timeout=60)
                r.raise_for_status()
                import json
                payload = json.loads(lzma.decompress(r.content).decode("utf-8"))
                from .db import norm_name
                for item in payload.get("laws", []):
                    law, arts = item["law"], item["articles"]
                    keys = {norm_name(law["name"])}
                    if law.get("short"):
                        keys.add(norm_name(law["short"]))
                    self.db.replace_law(law, arts, [k for k in keys if k],
                                        action="delta")
                for law_id in payload.get("removed", []):
                    self.db.conn.execute("DELETE FROM law WHERE law_id=?",
                                         (law_id,))
                    self.db.conn.commit()
                total += len(payload.get("laws", []))
            except Exception:
                return -1
        return total

    def _download_snapshot(self, manifest):
        snap = manifest["snapshot"]
        url = snap.get("url") or f"{self.base_url}/{snap['file']}"
        size = int(snap.get("size", 0) or 0)
        self.progress.emit(f"법령 데이터 받는 중… ({size/1048576:.0f}MB)", 0)
        fd, tmp_xz = tempfile.mkstemp(suffix=".db.xz", dir=os.path.dirname(DB_PATH))
        got = 0
        h = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as f:
                r = self._get(url, stream=True, timeout=60)
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    if size:
                        self.progress.emit(
                            f"법령 데이터 받는 중… "
                            f"{got/1048576:.0f}/{size/1048576:.0f}MB",
                            min(99, int(got * 100 / size)))
            if snap.get("sha256") and h.hexdigest() != snap["sha256"]:
                raise IOError("sha256 불일치(다운로드 손상)")
            self.progress.emit("데이터 푸는 중…", 99)
            new_db = DB_PATH + ".new"
            with lzma.open(tmp_xz, "rb") as fin, open(new_db, "wb") as fout:
                while True:
                    b = fin.read(1 << 20)
                    if not b:
                        break
                    fout.write(b)
            return new_db
        finally:
            if os.path.exists(tmp_xz):
                os.remove(tmp_xz)
