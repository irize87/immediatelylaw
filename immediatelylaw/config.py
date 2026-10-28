# -*- coding: utf-8 -*-
"""설정 저장. OC(API 인증키)는 Windows DPAPI로 암호화해 저장한다."""
import base64
import ctypes
import ctypes.wintypes
import json
import os
import sys

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
    "font_pt": 11,                 # 장·절 표기와 조문 본문 글자크기(pt)
    "overlay_corner": "bottom_right", # top_right/top_left/bottom_right/bottom_left
    "auto_hide_sec": 30,           # 0 = 자동 숨김 없음(고정)
    "verify_enabled": True,        # 현행 여부 백그라운드 검증
    "hotkey_enabled": True,        # Ctrl+Alt+L 조회창
    "autostart": True,             # Windows 시작 시 자동 실행(기본 켬)
    "clipboard_paused": False,
    "last_update_check": "",       # 마지막 개정 점검(YYYYMMDDHHMM)
    "data_base_url": "https://raw.githubusercontent.com/nazgregory/immediatelylaw-data/dist",
                                   # 배포 데이터 주소(manifest.json 상위)
}

# ---------------- DPAPI ----------------
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
    fn = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(blob_in), None, None, None, None,
            _DATA_DATA_BLOB_FLAGS(encrypt), ctypes.byref(blob_out))
    if not ok:
        raise OSError("DPAPI 호출 실패")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _DATA_DATA_BLOB_FLAGS(encrypt: bool) -> int:
    return _DATA_BLOB_FLAG_CRYPTPROTECT_UI_FORBIDDEN


def encrypt_str(s: str) -> str:
    return base64.b64encode(_dpapi(s.encode("utf-8"), True)).decode()


def decrypt_str(b64: str) -> str:
    return _dpapi(base64.b64decode(b64), False).decode("utf-8")


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
