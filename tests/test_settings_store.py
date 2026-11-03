# -*- coding: utf-8 -*-
"""Regression: _tab_general의 IS_STORE 분기 (스토어 포장 회귀).

v1.6.0 store build: the loop variable `w` shadowed the tab widget `w`;
the tab lost its last reference, its C++ object died immediately, and opening
settings raised RuntimeError("QCheckBox already deleted"). Desktop builds
never take this branch, so only Store packages hit it. This test forces
IS_STORE=True on the offscreen platform and verifies the general tab survives.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from immediatelylaw import buildflag, config
from immediatelylaw.settingsdlg import SettingsDialog


class _FakeDb:
    def stats(self):
        return {"laws": 1, "articles": 2, "local_laws": 0,
                "data_ver": "x", "built_at": "x"}


def test_general_tab_survives_is_store(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "cfg.json"))
    cfg = config.Config()
    cfg.load()
    monkeypatch.setattr(buildflag, "IS_STORE", True)
    # db-dependent tabs are out of scope here (fake db has no conn):
    monkeypatch.setattr(SettingsDialog, "_tab_data", lambda self: QWidget())
    monkeypatch.setattr(SettingsDialog, "_tab_local", lambda self: QWidget())
    dlg = SettingsDialog(cfg, _FakeDb())
    try:
        general = dlg.tabs.widget(4)  # data/local/api/overlay/general/info
        assert general is not None
        assert not isinstance(general, QPushButton)
        # shadowing bug would reparent btn_updnow into the tab widget and
        # destroy the original tab (and thus all checkboxes) instead
        assert dlg.chk_auto.parent() is general
        assert dlg.btn_updnow.parent() is general
        dlg.tabs.setCurrentIndex(4)
        assert not dlg.chk_auto.isVisibleTo(dlg)   # store build: hidden
        assert not dlg.chk_updchk.isVisibleTo(dlg)
        assert not dlg.btn_updnow.isVisibleTo(dlg)
        assert dlg.chk_hotkey.isVisibleTo(dlg)     # others stay visible
    finally:
        dlg.deleteLater()
