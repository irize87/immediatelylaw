# -*- coding: utf-8 -*-
"""배포 주소 검증 회귀 테스트.

요청 사양: 배포 주소 기본갑은 빈칸, 비어 있으면 배포 서버를 바라본다.
실수로 스페이스 같은 갑을 넣어 유통 검증을 통과하지 못해도 배포 서버로
폴백돼야 한다(예외·Crash 없이)."""
import json

from immediatelylaw import config as cfgmod
from immediatelylaw.config import Config, clean_base_url
from immediatelylaw.workers import MIRROR_BASE, data_host_list

LEGACY = "https://raw.githubusercontent.com/nazgregory/immediatelylaw-data/dist"


# ---------- clean_base_url ----------
def test_empty_and_blank_fall_back_to_mirror():
    for bad in ("", " ", "   \t \n\u3000", None):
        assert clean_base_url(bad) == ""


def test_non_https_and_hostless_rejected():
    for bad in ("http://example.com", "ftp://example.com", "https://",
                "https:///path", "just text", "https:// ", "203.0.113.7"):
        assert clean_base_url(bad) == ""


def test_legacy_github_data_url_never_survives():
    # 끝의 '/'·내부 공백이 섞인 변형까지 모두 폐기.
    assert clean_base_url(LEGACY) == ""
    assert clean_base_url(LEGACY + "/") == ""
    assert clean_base_url(" " + LEGACY.replace("//", "// ") + " ") == ""


def test_valid_urls_normalized():
    assert clean_base_url("https://203.0.113.7/") == "https://203.0.113.7"
    assert clean_base_url("  https://a.example:8443/dist//  ") == \
        "https://a.example:8443/dist"
    # 내부 공백은 제거 후 재평가(붙여쓰면 유효한 주소가 되는 오타 구제).
    assert clean_base_url("https://a.example /dist") == "https://a.example/dist"


# ---------- Config.load() 자가 치유 ----------
def test_load_normalizes_stale_config(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "data_base_url": LEGACY,                      # 구버전 잔재(현실 사례)
        "mirror_url": "   ",                          # 스페이스 오입력
    }), encoding="utf-8")
    monkeypatch.setattr(cfgmod, "CONFIG_PATH", str(p))
    c = Config()
    assert c["data_base_url"] == ""
    assert c["mirror_url"] == ""


def test_load_keeps_valid_url(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"data_base_url": "https://a.example/dist/"}),
                 encoding="utf-8")
    monkeypatch.setattr(cfgmod, "CONFIG_PATH", str(p))
    assert Config()["data_base_url"] == "https://a.example/dist"


# ---------- workers.data_host_list ----------
def test_garbage_channels_never_become_channels():
    cfg = {"data_base_url": " ", "mirror_url": "http://10.0.0.1"}
    assert data_host_list(cfg) == [MIRROR_BASE]


def test_valid_custom_channel_first_then_mirror():
    cfg = {"data_base_url": "https://a.example/dist/",
           "mirror_url": LEGACY}   # 옛 갑 → 제거, 중복 없는 2채널
    assert data_host_list(cfg) == ["https://a.example/dist", MIRROR_BASE]


def test_duplicate_channels_collapsed():
    cfg = {"data_base_url": MIRROR_BASE + "/",
           "mirror_url": "https://b.example"}
    assert data_host_list(cfg) == [MIRROR_BASE, "https://b.example"]
