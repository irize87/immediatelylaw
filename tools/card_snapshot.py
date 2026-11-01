# -*- coding: utf-8 -*-
"""조문 카드 스냅샷: 화면에 띄우지 않고 라이트/다크 PNG로 렌더해 준다.

UI 개정 후 눈으로 확인하는 용도. 실행:  python tools/card_snapshot.py
출력:  %TEMP%\\il_measure\\card2_light.png / card2_dark.png
(오프스크린 QPA는 한글 폰트를 해석하지 못하므로 기본 windows QPA를 쓴다.)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication                      # noqa: E402
from PySide6.QtGui import QColor, QPainter, QPixmap             # noqa: E402
from immediatelylaw.overlay import OverlayCard                  # noqa: E402

OUT = os.path.join(os.environ["TEMP"], "il_measure")

BODY = (
    "① 법률에서 정한 절차에 따라서는 청구권을 보전(保全) 할 수 없는 경우에 "
    "그 청구권의 실행이 불가능해지거나 현저히 곤란해지는 상황을 피하기 "
    "위하여 한 행위는 상당한 이유가 있는 때에는 벌하지 아니한다.\n"
    "② 제1항의 행위가 그 정도를 초과한 경우에는 형법에 따라 그 형을 "
    "감경하거나 면제할 수 있다. [전문개정 2020.12.8]"
)
RES = {
    "found": True, "source": "local", "law_name": "형법", "art_no": "23",
    "title": "자구행위", "chap": "제1절 죄의 성립과 형의 감면", "body": BODY,
    "mst": "100000012345", "law_id": "형법", "enforced": "", "pending": 0,
    "cls": "법률",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    app = QApplication(sys.argv)
    for mode in ("light", "dark"):
        cfg = {"overlay_width": 560, "font_pt": 11, "theme": mode,
               "overlay_corner": "top-right", "auto_hide_sec": 0}
        card = OverlayCard(cfg)
        card._place_and_show = lambda: None   # 실제 표시(위치·포커스) 생략
        card.show_results([RES], note="")
        card.set_badge("current")             # 검증 완료 상태 재현
        card.adjustSize()
        card.resize(card.width(), min(card.sizeHint().height() + 20, 800))
        card.ensurePolished()
        card.layout().activate()
        pm = card.grab()
        canvas = QPixmap(pm.size())
        canvas.fill(QColor("#dfe3e8" if mode == "light" else "#14171c"))
        p = QPainter(canvas)
        p.drawPixmap(0, 0, pm)
        p.end()
        path = os.path.join(OUT, f"card2_{mode}.png")
        canvas.save(path, "PNG")
        print("saved", path, canvas.width(), "x", canvas.height())
        card.deleteLater()


if __name__ == "__main__":
    main()
