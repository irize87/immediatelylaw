# -*- coding: utf-8 -*-
"""설정 저장. OC(API 인증키)는 Windows DPAPI로 암호화해 저장한다.
Linux(발행 서버)에서는 DPAPI가 없어 평문 base64 폴백이며, 발행자는
환경변수 IMMEDIATELYLAW_OC를 우선 사용한다."""
import base64
import json
import os
import sys

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

APP_NAME = "immediatelylaw"
_OLD_APP_NAME = "임시로"


def _appdata_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:  # 개발 보조
        base = os.path.expanduser("~/.config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    # 이전 한글 디렉터리(%APPDATA%\임시로)에서 1회 이관
    old = os.path.join(base, _OLD_APP_NAME, "config.json")
    new = os.path.join(d, "config.json")
    if os.path.isfile(old) and not os.path.isfile(new):
        try:
            import shutil
            shutil.copy2(old, new)
        except OSError:
            pass
    return d


CONFIG_PATH = os.path.join(_appdata_dir(), "config.json")

DEFAULTS = {
    "overlay_width": 470,          # 오버레이 카드 폭(px)
    "theme": "light",              # 시스템(system)/라이트(light)/다크(dark)
    "font_pt": 11,                 # 장·절 표기와 조문 본문 글자크기(pt)
    "overlay_corner": "bottom_right", # top_right/top_left/bottom_right/bottom_left
    "auto_hide_sec": 30,           # 0 = 자동 숨김 없음(고정)
    "verify_enabled": True,        # 현행 여부 백그라운드 검증
    "hotkey_enabled": True,        # Ctrl+Alt+L 조회창
    "autostart": True,             # Windows 시작 시 자동 실행(기본 켬)
    "clipboard_paused": False,
    "last_update_check": "",       # 마지막 개정 점검(YYYYMMDDHHMM)
    "last_law": "",                # 마지막 표시/조회 본법('같은 법' 해석용)
    "update_check": True,          # 프로그램 새 버전 알림(GitHub Releases)
    "update_skip_ver": "",         # 사용자가 "알림 끄기"한 버전
    "data_base_url": "https://raw.githubusercontent.com/nazgregory/immediatelylaw-data/dist",
                                   # 배포 데이터 주소(manifest.json 상위)
}

# ---------------- DPAPI (Windows 전용) ----------------
if sys.platform == "win32":
    _DATA_BLOB_FLAG_CRYPTPROTECT_UI_FORBIDDEN = 0x01

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _dpapi(data: bytes, encrypt: bool) -> bytes:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = _DATA_BLOB(len(data),
                             ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = _DATA_BLOB()
        fn = (crypt32.CryptProtectData if encrypt
              else crypt32.CryptUnprotectData)
        ok = fn(ctypes.byref(blob_in), None, None, None, None,
                _DATA_BLOB_FLAG_CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(blob_out))
        if not ok:
            raise OSError("DPAPI 호출 실패")
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)

    def encrypt_str(s: str) -> str:
        return base64.b64encode(_dpapi(s.encode("utf-8"), True)).decode()

    def decrypt_str(b64: str) -> str:
        return _dpapi(base64.b64decode(b64), False).decode("utf-8")

else:  # Linux 등: 마크용 base64(암호화 아님) — 서버는 env 키를 사용
    def encrypt_str(s: str) -> str:
        return base64.b64encode(s.encode("utf-8")).decode()

    def decrypt_str(b64: str) -> str:
        return base64.b64decode(b64).decode("utf-8")


# ---------------- 설정 ----------------
class Config:
    def __init__(self):
        self._d = dict(DEFAULTS)
        self.oc_key_enc = ""   # DPAPI 암호화 + base64
        self.load()

    def load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k in DEFAULTS:
                if k in raw:
                    self._d[k] = raw[k]
            self.oc_key_enc = raw.get("oc_key_enc", "") or ""
            # 과거 평문 마이그레이션
            if raw.get("oc_key") and not self.oc_key_enc:
                self.set_oc_key(raw["oc_key"])
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save(self):
        raw = dict(self._d)
        raw["oc_key_enc"] = self.oc_key_enc
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)

    def __getitem__(self, k):
        return self._d[k]

    def get(self, k, default=None):
        return self._d.get(k, default)

    def __setitem__(self, k, v):
        self._d[k] = v

    # --- OC 키 ---
    def set_oc_key(self, key: str):
        key = (key or "").strip()
        self.oc_key_enc = encrypt_str(key) if key else ""
        self.save()

    def get_oc_key(self) -> str:
        if not self.oc_key_enc:
            return ""
        try:
            return decrypt_str(self.oc_key_enc)
        except OSError:
            return ""

    def has_oc_key(self) -> bool:
        return bool(self.oc_key_enc)

    def masked_oc_key(self) -> str:
        k = self.get_oc_key()
        if not k:
            return ""
        if len(k) <= 8:
            return k[0] + "•" * (len(k) - 2) + k[-1]
        return f"{k[:4]}{'•' * 8}{k[-4:]}"


_cfg = None


def get_config() -> Config:
    global _cfg
    if _cfg is None:
        _cfg = Config()
    return _cfg
