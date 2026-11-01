# -*- coding: utf-8 -*-
"""라이트/다크 모드: 해결(theme.system/light/dark)과 창·위젯에 적용할 색 팔레트."""

SYSTEM = "system"

DARK = dict(
    dark=True,
    bg="#1f242b", panel="#262c34", fg="#e8eaed", fg2="#9aa3ad",
    border="#39414b", hover="#323a45", link="#6cb2ff",
    copy_bg="#2c333b",
    accent="#2f6bff", accent_hover="#4d80ff", accent_fg="#ffffff",
    badge_current="color:#7ee2a1;background:#22402e;",
    badge_check="color:#f0c674;background:#403418;",
    badge_neutral="color:#b6bdc7;background:#333a44;",
)
LIGHT = dict(
    dark=False,
    bg="#ffffff", panel="#ffffff", fg="#20242b", fg2="#8a919c",
    border="#e2e6ea", hover="#eef2f8", link="#2563eb",
    copy_bg="#f3f4f6",
    accent="#2563eb", accent_hover="#1d4ed8", accent_fg="#ffffff",
    badge_current="color:#1a7f37;background:#e3f5e9;",
    badge_check="color:#b45309;background:#fdf0d9;",
    badge_neutral="color:#5b6470;background:#eef0f3;",
)


def _system_dark() -> bool:
    """Windows 앱 모드(밝기) 설정 따르기."""
    try:
        import winreg
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion"
                r"\Themes\Personalize") as k:
            v, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return int(v) == 0
    except (OSError, ValueError):
        return False


def is_dark(cfg) -> bool:
    mode = str(cfg.get("theme", SYSTEM) if hasattr(cfg, "get")
               else cfg["theme"])
    if mode == "dark":
        return True
    if mode == "light":
        return False
    return _system_dark()


def palette(cfg) -> dict:
    return DARK if is_dark(cfg) else LIGHT


def app_qss(cfg) -> str:
    """다이얼로그·조회창 등 공통 위젯용 스타일시트(라이트면 빈 문자열)."""
    if not is_dark(cfg):
        return ""
    p = DARK
    return f"""
    QWidget {{ background:{p['bg']}; color:{p['fg']}; }}
    QLineEdit, QTextEdit, QTextBrowser, QListWidget, QListView, QTreeView,
    QPlainTextEdit {{
        background:{p['panel']}; color:{p['fg']};
        border:1px solid {p['border']};
        selection-background-color:#2f6fb3; selection-color:#ffffff; }}
    QTabWidget::pane {{ border:1px solid {p['border']}; background:{p['bg']}; }}
    QTabBar::tab {{ background:{p['panel']}; color:{p['fg2']};
        padding:6px 14px; border:1px solid {p['border']};
        border-bottom:none; }}
    QTabBar::tab:selected {{ background:{p['bg']}; color:{p['fg']}; }}
    QSpinBox, QComboBox, QAbstractItemView {{ background:{p['panel']};
        color:{p['fg']}; border:1px solid {p['border']}; }}
    QCheckBox {{ color:{p['fg']}; background:transparent; }}
    QScrollBar:vertical {{ background:{p['bg']}; width:10px; margin:0; }}
    QScrollBar::handle:vertical {{ background:{p['border']};
        border-radius:5px; min-height:24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height:0; width:0; }}
    QScrollBar::up-button, QScrollBar::down-button {{
        width:0; height:0; border:none; background:transparent; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
    QToolTip {{ background:{p['panel']}; color:{p['fg']};
        border:1px solid {p['border']}; }}
    QMenu {{ background:{p['panel']}; color:{p['fg']};
        border:1px solid {p['border']}; }}
    QMenu::item:selected {{ background:#2f6fb3; color:#ffffff; }}
    QSplitter::handle {{ background:{p['border']}; }}
    """
