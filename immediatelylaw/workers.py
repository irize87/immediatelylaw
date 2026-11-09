# -*- coding: utf-8 -*-
"""백그라운드 워커: 검증, 데이터 갱신(멀티 채널·델타 우선), 온디맨드 수집."""
import hashlib
import json
import lzma
import os
import tempfile
import zipfile

import requests
from PySide6.QtCore import QThread, Signal

from . import resolver
from .config import clean_base_url
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


MAX_XZ_BYTES = 400 * 1024 * 1024    # 압축 스냅샷 상한(실측 ~30MB)
MAX_DB_BYTES = 900 * 1024 * 1024    # 해제 후 DB 상한(호·목 전문 복원 후 실측 ~412MB)
MAX_DELTA_JSON = 64 * 1024 * 1024   # 델타 1건 해제 후 상한(실측 ≪1MB, 압축풀기 폭탄 방어)


def _https(url: str) -> str:
    """데이터를 로컬에 반영하는 받기는 https만 허용(평문 전달·다운그레이드 방지)."""
    if not (url or "").lower().startswith("https://"):
        raise IOError("https 주소만 허용됩니다: " + (url or "")[:80])
    return url


# ---------- 배포 채널 ----------
# 배포(데이터·프로그램·앱) 채널의 1순위는 공식 배포 서버(도메인, CA 인증서)다.
# GitHub는 소스 코드 공개 전용으로만 쓰고 데이터 채널에서는 제외한다(옛 GitHub
# 데이터 배포는 종료되어 현재 404 — 옛 값 걸러내기는 config.clean_base_url이
# 담당). 같은 레이아웃(manifest.json / delta-*.json.xz / immediatelylaw-*.db.xz /
# app-latest.json)을 배포하는 채널을 순서대로 시도한다.
# 소스 공개 범위 정책: 실제 서버 IP는 코드에 적지 않는다. 도메인은 Let's
# Encrypt 인증서로 검증되므로 별도 고정 없이 TLS가 성립한다.
MIRROR_BASE = "https://immediatelylaw.kro.kr"   # 공식 배포 서버(CA 인증서)
UA = "immediatelylaw-updater"

# 고정(pinning) 채널은 의도적으로 verify=False + 사후 지문 검증 구조라
# urllib3의 반복 경고가 로그를 오염시킨다. 본 앱은 verify=False를
# 고정 호스트 외에는 쓰지 않는다.
import urllib3  # noqa: E402
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 배포 서버 인증서 고정: 호스트 → 인증서(DER) sha256. 정책상 소스에는 지문을
# 두지 않는다(기본 채널이 CA 검증 도메인이어서 고정이 불필요). 특수 채널(예:
# IP 직접 지정 미러)을 쓸 일이 생기면 배포 시점에 이 사전에 채워 넣는다 —
# 값이 있는 호스트만 verify=False + 지문 검증 경로로 진행하고, 없으면 평범한
# CA 검증을 쓴다.
CERT_PINS: dict[str, str] = {}
_pin_cache = {}


def _pin_ok(host: str, port: int = 443) -> bool:
    """고정 대상 호스트는 별도 TLS 핸드셰이크로 인증서 지문을 확인한다."""
    want = CERT_PINS.get(host or "")
    if not want:
        return True
    key = (host, port)
    if key in _pin_cache:
        return _pin_cache[key]
    ok = False
    try:
        import socket
        import ssl as _ssl
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=8) as s:
            with ctx.wrap_socket(s) as ss:
                der = ss.getpeercert(True)
        ok = hashlib.sha256(der).hexdigest() == want
    except Exception:
        ok = False
    _pin_cache[key] = ok
    return ok


def _url_pin_ok(url: str) -> bool:
    from urllib.parse import urlparse
    u = urlparse(url)
    return _pin_ok(u.hostname or "", u.port or 443)


def _verify_flag(url: str) -> bool:
    from urllib.parse import urlparse
    return (urlparse(url).hostname or "") not in CERT_PINS


def _lzma_decompress_limited(content: bytes, limit: int) -> bytes:
    """xz 해제 결과를 limit 바이트로 묶어 해제(초과 시 IOError). 압축풀기
    폭탄 방어용(소량 데이터·델타 전용)이며, 대량 스냅샷은 _inflate이 별도 처리."""
    import io
    out = bytearray()
    with lzma.open(io.BytesIO(content), "rb") as fin:
        while True:
            b = fin.read(1 << 20)
            if not b:
                break
            out += b
            if len(out) > limit:
                raise IOError("데이터 해제 용량이 상한을 넘어 파기했습니다.")
    return bytes(out)


def data_host_list(cfg) -> list:
    """cfg 기준의 채널 순서 목록(비어 있음·중복·유통불가 주소 제거).

    순서: 사용자가 지정한 배포 주소(설정, 있으면 우선) → 내장 배포 서버 →
    추가 채널(mirror_url). 배포 주소는 config.clean_base_url로 검증하므로
    사용자가 스페이스 같은 값을 넣으면 그 칸은 없는 셈 쳐져 배포 서버를
    바라본다. 전부 실패하면 업데이트만 멈추고 앱·데이터는 지금 상태로 계속
    동작한다."""
    raw = [clean_base_url(cfg.get("data_base_url")), MIRROR_BASE,
           clean_base_url(cfg.get("mirror_url"))]
    out = []
    for u in raw:
        if not u or u in out:
            continue
        out.append(u)
    return out


def _fetch_any(hosts, rel: str, timeout=30, session=None):
    """상대 경로 파일을 채널 목록에서 시도해 bytes로 반환."""
    from urllib.parse import urlparse
    errs = []
    s = session or requests
    for h in hosts:
        url = _https(h.rstrip("/") + "/" + rel.lstrip("/"))
        host = urlparse(url).hostname or ""
        if not _url_pin_ok(url):
            errs.append(f"{host}: 인증서 고정 검증 실패")
            continue
        try:
            r = s.get(url, timeout=timeout,
                      headers={"User-Agent": UA},
                      verify=_verify_flag(url))
            r.raise_for_status()
            return r.content
        except Exception as e:
            errs.append(f"{host}: {e}")
    raise IOError(" / ".join(errs) or "채널 없음")


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

    def __init__(self, db, api, hint, art, hints=None, auto=None,
                 parent=None):
        super().__init__(parent)
        self.db, self.api, self.hint, self.art = db, api, hint, art
        self.hints = hints
        self.auto = auto

    def run(self):
        try:
            res = resolver.resolve(self.db, self.hint, self.art, self.api,
                                   hints=self.hints, auto=self.auto)
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
    """배포 채널 목록으로 로컬 DB를 최신화(델타 우선, 폴백 스냅샷)."""
    progress = Signal(str, int)          # message, percent(-1 = 진행률 없음)
    done = Signal(bool, str)             # ok, message
    db_replaced = Signal(str)            # 새 DB 파일 경로(app에서 재오픈)

    def __init__(self, db, base_url, apply_deltas=True, parent=None):
        super().__init__(parent)
        self.db = db
        if isinstance(base_url, str) or base_url is None:
            base_url = [base_url] if base_url else []
        self.hosts = [str(u).strip().rstrip("/") for u in base_url if u]
        self.base_url = self.hosts[0] if self.hosts else ""
        self.apply_deltas = apply_deltas

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.done.emit(False, f"갱신 실패: {e}")

    # ---- 내부 ----
    def _run(self):
        if not self.hosts:
            self.done.emit(False, "데이터 소스(URL)가 설정되지 않았습니다. "
                                  "설정 › 데이터에서 배포 주소를 입력하세요.")
            return
        try:
            for h in self.hosts:
                _https(h)
        except IOError as e:
            self.done.emit(False, str(e))
            return
        stats = self.db.stats()
        self.progress.emit("버전 정보 확인 중…", -1)
        manifest = None
        for h in list(self.hosts):
            try:
                j = _fetch_any([h], "manifest.json", timeout=20)
                m = json.loads(j.decode("utf-8"))
                if m.get("snapshot", {}).get("file"):
                    manifest = m
                    self.base_url = h   # 이후 파일은 이 채널 우선
                    break
            except Exception:
                continue
        if manifest is None:
            self.done.emit(False, "모든 채널에서 버전 정보를 받지 못했습니다 "
                                  "(네트워크/차단 확인).")
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
        """local_ver→목표까지 빈틈없는 델타 체인을 적용. 성공 시 반영 건수,
        체인 불완전/무결성 실패 시 -1(호스트 내부에서 스냅샷 폴백)."""
        deltas = sorted((d for d in manifest.get("deltas", [])
                         if d.get("from") and d.get("to")),
                        key=lambda d: (d["from"], d["to"]))
        if not deltas or deltas[0]["from"] != local_ver:
            return -1
        cur = local_ver
        total = 0
        for d in deltas:
            if d["from"] != cur or not d.get("sha256"):
                return -1                  # 체인 틈/해시 누락 → 스냅샷
            try:
                self.progress.emit(f"개정 반영 {d['to']} …", -1)
                content = _fetch_any([self.base_url] + self.hosts,
                                     d["file"], timeout=60)
                if hashlib.sha256(content).hexdigest() != d["sha256"]:
                    return -1
                payload = json.loads(
                    _lzma_decompress_limited(
                        content, MAX_DELTA_JSON).decode("utf-8"))
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
                cur = d["to"]
                total += len(payload.get("laws", []))
            except Exception:
                return -1
        if cur != manifest.get("data_ver", ""):
            return -1                      # 목표까지 도달 실패
        return total

    def _download_snapshot(self, manifest):
        snap = manifest["snapshot"]
        size = int(snap.get("size", 0) or 0)
        if size and size > MAX_XZ_BYTES:
            raise IOError("스냅샷 크기가 비정상적으로 커 파기를 중단했습니다.")
        if not snap.get("sha256"):
            raise IOError("manifest에 sha256이 없어 무결성을 검증할 수 없습니다.")
        self.progress.emit(f"법령 데이터 받는 중… ({size/1048576:.0f}MB)", 0)
        fd, tmp_xz = tempfile.mkstemp(suffix=".db.xz",
                                      dir=os.path.dirname(DB_PATH))
        os.close(fd)
        from urllib.parse import urlparse
        errs = []
        for h in [self.base_url] + [x for x in self.hosts
                                    if x != self.base_url]:
            url = _https(h + "/" + snap["file"])
            host = urlparse(url).hostname or ""
            if not _url_pin_ok(url):
                errs.append(f"{host}: 인증서 고정 검증 실패")
                continue
            got = 0
            hsh = hashlib.sha256()
            try:
                with open(tmp_xz, "wb") as f:
                    r = requests.get(url, stream=True, timeout=60,
                                     headers={"User-Agent": UA},
                                     verify=_verify_flag(url))
                    r.raise_for_status()
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
                        hsh.update(chunk)
                        got += len(chunk)
                        if got > MAX_XZ_BYTES:
                            raise IOError("다운로드 용량이 상한을 넘어 "
                                          "파기를 중단했습니다.")
                        if size:
                            self.progress.emit(
                                f"법령 데이터 받는 중… "
                                f"{got/1048576:.0f}/{size/1048576:.0f}MB",
                                min(99, int(got * 100 / size)))
                if hsh.hexdigest() != snap["sha256"]:
                    raise IOError("sha256 불일치(다운로드 손상)")
                if size and got != size:
                    raise IOError("다운로드 길이 불일치")
                self.progress.emit("데이터 푸는 중…", 99)
                try:
                    return _inflate(tmp_xz)
                finally:
                    if os.path.exists(tmp_xz):
                        os.remove(tmp_xz)
            except Exception as e:
                errs.append(f"{host}: {e}")
        if os.path.exists(tmp_xz):
            os.remove(tmp_xz)
        raise IOError(" / ".join(errs) or "스냅샷 다운로드 실패")


# ---------- 프로그램 자체 업데이트(배포 서버 app-latest.json) ----------
# 설치 파일을 내려받아도 되는 호스트는 배포 채널 호스트로 한정한다
# (확인 시점의 채널 호스트가 AppDownloadWorker에서 extra로 전달된다).
# GitHub는 소스 코드 공개 전용이며 배포·다운로드 채널로 쓰지 않는다.
UPDATE_HOSTS = set()
MAX_ZIP_BYTES = 300 * 1024 * 1024   # 설치 zip 상한(실측 ~89MB)


def _ver_tuple(s: str):
    core = (s or "").strip().lstrip("vV").split("-")[0]
    return tuple(int(x) if x.isdigit() else 0 for x in core.split("."))


def _host_ok(url: str, extra=()) -> bool:
    from urllib.parse import urlparse
    u = urlparse(url)
    return (u.scheme == "https"
            and ((u.hostname or "") in UPDATE_HOSTS
                 or (u.hostname or "") in set(extra)))


class AppUpdateWorker(QThread):
    """최신 릴리스 확인: 배포 채널의 app-latest.json만 사용한다.

    app-latest.json = {version, updated,
                       files: {online|offline: {file, size, sha256}}}
    채널 목록(app-latest.json)은 만료본이 최신을 가리지 않도록 전부 조회해
    가장 높은 버전만 제안한다. 채널 파일 다운로드에는 sha256이 필수다."""
    found = Signal(dict)     # {version, url, size, sha256, page}
    latest = Signal()
    failed = Signal(str)

    def __init__(self, cur_ver: str, offline=False, hosts=None, parent=None):
        super().__init__(parent)
        self.cur_ver, self.offline = cur_ver, offline
        self.hosts = [str(u).strip().rstrip("/") for u in (hosts or []) if u]

    def run(self):
        try:
            best = None
            errs = []
            for h in self.hosts:
                try:
                    raw = _fetch_any([h], "app-latest.json", timeout=15)
                    j = json.loads(raw.decode("utf-8"))
                    want = ("offline" if self.offline else "online")
                    pick = (j.get("files") or {}).get(want) \
                        or (j.get("files") or {}).get("online")
                    if not pick or not pick.get("file"):
                        continue
                    if not pick.get("sha256"):
                        errs.append(f"{h}: sha256 없음(채널은 해시 필수)")
                        continue
                    ver = str(j.get("version") or "")
                    if (best is None
                            or _ver_tuple(ver) > _ver_tuple(best[0])):
                        best = (ver, h, pick)
                except Exception as e:
                    errs.append(f"{h}: {e}")
            if best and _ver_tuple(best[0]) > _ver_tuple(self.cur_ver):
                ver, h, pick = best
                url = h + "/" + pick["file"].lstrip("/")
                if not _url_pin_ok(url):
                    self.failed.emit("배포 서버 인증서 고정 검증에 실패했습니다.")
                    return
                self.found.emit({
                    "version": ver.lstrip("vV"), "url": url,
                    "size": int(pick.get("size") or 0),
                    "sha256": pick.get("sha256") or "",
                    "page": h})
                return
            if best:
                self.latest.emit()      # 채널들이 확인됐고 전부 현재 이하
                return
            # 어떤 채널도 응답하지 못함 — 배포 서버 접속 실패로 처리
            self.failed.emit("; ".join(errs)[:260] or "배포 서버에 연결하지 못했습니다.")
        except Exception as e:
            self.failed.emit(str(e))


class AppDownloadWorker(QThread):
    """동의한 뒤 설치 zip을 내려받아 무결성 검사(sha256)와 함께 풀어둔다."""
    progress = Signal(str, int)
    ready = Signal(str)      # 압축 푼 ImmediatelyLaw 폴더 경로
    failed = Signal(str)

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info, self.cancel = info, False

    def run(self):
        import zipfile
        from urllib.parse import urlparse
        zpath = None
        try:
            url = self.info["url"]
            _https(url)
            start_host = urlparse(url).hostname or ""
            extra = {start_host}
            if not _url_pin_ok(url):
                raise IOError("배포 서버 인증서 고정 검증 실패")
            fd, zpath = tempfile.mkstemp(suffix=".zip",
                                         prefix="immediatelylaw-")
            got = total = 0
            hsh = hashlib.sha256()
            with os.fdopen(fd, "wb") as f:
                with requests.get(url, stream=True, timeout=60,
                                  headers={"User-Agent": UA},
                                  verify=_verify_flag(url)) as r:
                    r.raise_for_status()
                    if not _host_ok(r.url, extra):
                        raise IOError("리디렉트 대상이 신뢰할 수 없는 주소입니다.")
                    total = int(r.headers.get("content-length")
                                or self.info.get("size") or 0)
                    for chunk in r.iter_content(1 << 16):
                        if self.cancel:
                            raise IOError("사용자가 취소했습니다.")
                        f.write(chunk)
                        hsh.update(chunk)
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
            want_sha = self.info.get("sha256") or ""
            if want_sha and hsh.hexdigest() != want_sha:
                raise IOError("설치 파일 sha256이 배포 정보와 일치하지 않습니다.")
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
