# -*- coding: utf-8 -*-
"""백그라운드 워커: 검증, 데이터 갱신(GitHub 배포), 온디맨드 수집."""
import hashlib
import lzma
import os
import tempfile
import zipfile

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


MAX_XZ_BYTES = 200 * 1024 * 1024   # 압축 스냅샷 상한(현재 실측 ~21MB)
MAX_DB_BYTES = 400 * 1024 * 1024   # 해제 후 DB 상한(현재 실측 ~110MB)


def _https(url: str) -> str:
    """데이터를 로컬에 반영하는 받기는 https만 허용(평문 전달·다운그레이드 방지)."""
    if not (url or "").lower().startswith("https://"):
        raise IOError("https 주소만 허용됩니다: " + (url or "")[:80])
    return url


def _inflate(xz_path):
    """xz 해제. 용량 상한을 넘어설 수 있는 이상 파일은 파기를 중단한다."""
    new_db = DB_PATH + ".new"
    total = 0
    try:
        with lzma.open(xz_path, "rb") as fin, open(new_db, "wb") as fout:
            while True:
                b = fin.read(1 << 20)
                if not b:
                    break
                total += len(b)
                if total > MAX_DB_BYTES:
                    raise IOError("데이터 해제 용량이 상한을 넘어 파기를 중단했습니다.")
                fout.write(b)
    except Exception:
        if os.path.exists(new_db):
            os.remove(new_db)
        raise
    return new_db


def install_xz(xz_path):
    """오프라인 동봉(또는 내려받은) xz 스냅샷을 풀어 새 DB 파일 경로를 반환."""
    return _inflate(xz_path)


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
        try:
            _https(self.base_url)
        except IOError as e:
            self.done.emit(False, str(e))
            return
        stats = self.db.stats()
        self.progress.emit("버전 정보 확인 중…", -1)
        manifest = self._get(f"{self.base_url}/manifest.json").json()
        if not manifest.get("snapshot", {}).get("file"):
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
                r = requests.get(_https(d.get("url") or f"{self.base_url}/{f}"),
                                 timeout=60)
                r.raise_for_status()
                if d.get("sha256") and (
                        hashlib.sha256(r.content).hexdigest()
                        != d["sha256"]):
                    return -1          # 무결성 실패 → 전체 스냅샷으로 전환
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
        url = _https(snap.get("url") or f"{self.base_url}/{snap['file']}")
        size = int(snap.get("size", 0) or 0)
        if size and size > MAX_XZ_BYTES:
            raise IOError("스냅샷 크기가 비정상적으로 커 파기를 중단했습니다.")
        if not snap.get("sha256"):
            raise IOError("manifest에 sha256이 없어 무결성을 검증할 수 없습니다.")
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
                    if got > MAX_XZ_BYTES:
                        raise IOError("다운로드 용량이 상한을 넘어 파기를 중단했습니다.")
                    if size:
                        self.progress.emit(
                            f"법령 데이터 받는 중… "
                            f"{got/1048576:.0f}/{size/1048576:.0f}MB",
                            min(99, int(got * 100 / size)))
            if h.hexdigest() != snap["sha256"]:
                raise IOError("sha256 불일치(다운로드 손상)")
            self.progress.emit("데이터 푸는 중…", 99)
            return _inflate(tmp_xz)
        finally:
            if os.path.exists(tmp_xz):
                os.remove(tmp_xz)


# ---------- 프로그램 자체 업데이트(GitHub Releases) ----------
GH_LATEST_URL = ("https://api.github.com/repos/nazgregory/"
                 "ImmediatelyLaw/releases/latest")
# 설치 파일을 내려받아도 되는 공식 호스트만 허용(리디렉트도 검증).
UPDATE_HOSTS = {"api.github.com", "github.com", "codeload.github.com",
                "objects.githubusercontent.com",
                "release-assets.githubusercontent.com"}
MAX_ZIP_BYTES = 300 * 1024 * 1024   # 설치 zip 상한(실측 ~62MB)


def _ver_tuple(s: str):
    core = (s or "").strip().lstrip("vV").split("-")[0]
    return tuple(int(x) if x.isdigit() else 0 for x in core.split("."))


def _host_ok(url: str) -> bool:
    from urllib.parse import urlparse
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname or "") in UPDATE_HOSTS


class AppUpdateWorker(QThread):
    """GitHub Releases 최신 릴리스 확인."""
    found = Signal(dict)     # {version, url, size, page}
    latest = Signal()
    failed = Signal(str)

    def __init__(self, cur_ver: str, offline=False, parent=None):
        super().__init__(parent)
        self.cur_ver, self.offline = cur_ver, offline

    def run(self):
        try:
            r = requests.get(GH_LATEST_URL, timeout=15,
                             headers={"User-Agent": "immediatelylaw-updater"})
            r.raise_for_status()
            j = r.json()
            tag = (j.get("tag_name") or "").strip()
            if _ver_tuple(tag) <= _ver_tuple(self.cur_ver):
                self.latest.emit()
                return
            want = ("ImmediatelyLaw-offline.zip" if self.offline
                    else "ImmediatelyLaw-online.zip")
            assets = {a.get("name"): a for a in j.get("assets", [])}
            a = assets.get(want) or assets.get("ImmediatelyLaw-online.zip")
            url = (a or {}).get("browser_download_url", "")
            if not a or not _host_ok(url):
                self.failed.emit("새 릴리스에서 설치 파일을 찾지 못했습니다.")
                return
            self.found.emit({
                "version": tag.lstrip("vV"), "url": url,
                "size": int(a.get("size") or 0),
                "page": j.get("html_url", "")})
        except Exception as e:
            self.failed.emit(str(e))


class AppDownloadWorker(QThread):
    """동의한 뒤 설치 zip을 내려받아 안전 검사와 함께 풀어둔다."""
    progress = Signal(str, int)
    ready = Signal(str)      # 압출 푼 ImmediatelyLaw 폴더 경로
    failed = Signal(str)

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info, self.cancel = info, False

    def run(self):
        import zipfile
        zpath = None
        try:
            fd, zpath = tempfile.mkstemp(suffix=".zip",
                                         prefix="immediatelylaw-")
            got = total = 0
            with os.fdopen(fd, "wb") as f:
                with requests.get(self.info["url"], stream=True, timeout=60,
                                  headers={"User-Agent":
                                           "immediatelylaw-updater"}) as r:
                    r.raise_for_status()
                    if not _host_ok(r.url):
                        raise IOError("리디렉트 대상이 신뢰할 수 없는 주소입니다.")
                    total = int(r.headers.get("content-length")
                                or self.info.get("size") or 0)
                    for chunk in r.iter_content(1 << 16):
                        if self.cancel:
                            raise IOError("사용자가 취소했습니다.")
                        f.write(chunk)
                        got += len(chunk)
                        if got > MAX_ZIP_BYTES:
                            raise IOError("설치 파일이 허용 크기를 넘습니다.")
                        pct = min(99, int(got * 100 / total)) if total else -1
                        self.progress.emit(
                            f"v{self.info['version']} 받는 중… "
                            f"{got/1048576:.0f}/"
                            f"{(total or got)/1048576:.0f}MB", pct)
            if total and got != total:
                raise IOError(
                    f"다운로드 중 연결이 끊겼습니다 "
                    f"({got/1048576:.0f}/{total/1048576:.0f}MB).")
            out = tempfile.mkdtemp(prefix="immediatelylaw-update-")
            with zipfile.ZipFile(zpath) as z:
                for n in z.namelist():
                    nn = n.replace("\\", "/")
                    if nn.startswith("/") or ".." in nn.split("/"):
                        raise IOError("설치 압축에 의심스러운 경로가 있습니다.")
                if "ImmediatelyLaw/ImmediatelyLaw.exe" not in z.namelist():
                    raise IOError("설치 압축의 구조가 예상과 다릅니다.")
                z.extractall(out)
            self.ready.emit(os.path.join(out, "ImmediatelyLaw"))
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            if zpath and os.path.exists(zpath):
                try:
                    os.remove(zpath)
                except OSError:
                    pass
