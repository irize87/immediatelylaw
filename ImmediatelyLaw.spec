# -*- coding: utf-8 -*-
"""즉시로 PyInstaller 스펙.
사용:  pyinstaller immediatelylaw.spec
결과:  dist/즉시로/  폴더째로 배포(압축) — onefile은 Qt 부팅 지연/AV 오탐 있어 지양.
"""
# PyInstaller에 PySide6 훅이 내장되어 수집을 자동 처리한다.
# (collect_submodules로 전체를 강제하면 WebEngine까지 들어가지므로 쓰지 않는다)
a = Analysis(
    ["run.py"],
    pathex=["."],
    datas=[],
    hiddenimports=[],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml",
              "tkinter"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="ImmediatelyLaw",
    debug=False, strip=False, upx=False,
    console=False,   # GUI 앱: 콘솔 창 없음
    icon="assets/icon.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name="ImmediatelyLaw")
