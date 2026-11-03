# -*- coding: utf-8 -*-
"""Microsoft Store 스크린샷(1920x1080) 합성.

재료를 그대로 쓰고 배경 합성만 한다:
  01_light : 라이트 카드 + 브랜드 카피
  02_dark  : 다크 카드 + 동일 카피
  03_gallery: 실제 사용 갤러리 스크린샷(assets/screenshot.png) 여백 확장
한글은 코드포인트로 검증한 '즉시로'만 그린다(그 외 카피는 영문).
"""
import os
import unicodedata as ud

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(os.environ["TEMP"], "il_measure")
OUT = os.path.join(ROOT, "docs", "store", "screenshots")
os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080

SSIK = "".join(chr(c) for c in (0xC989, 0xC2DC, 0xB85C))
assert [ud.name(c).split()[-1] for c in SSIK] == ["JEUG", "SI", "RO"]

F_BD = "C:/Windows/Fonts/malgunbd.ttf"
F_RG = "C:/Windows/Fonts/malgun.ttf"


def grad(top, bottom):
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        row = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        for x in range(W):
            px[x, y] = row
    return img


def font(path, size):
    return ImageFont.truetype(path, size)


def shadow(card, off=18, radius=30, alpha=70):
    layer = Image.new("RGBA", (card.width + off * 4, card.height + off * 4),
                      (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([off * 2, off * 2, off * 2 + card.width,
                 off * 2 + card.height], fill=(20, 24, 32, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    return layer, off * 2


def place(base, img, box):
    sh, pad = shadow(img.convert("RGBA"))
    base.paste(sh, (box[0] - pad, box[1] - pad), sh)
    base.paste(img.convert("RGBA"), box, img.convert("RGBA"))


def shot_card(png, out, dark):
    base = grad((21, 24, 29) if dark else (247, 248, 250),
                (26, 30, 37) if dark else (231, 236, 242))
    card = Image.open(png).convert("RGBA")
    scale = 760 / card.height
    card = card.resize((int(card.width * scale), 760), Image.LANCZOS)
    cx, cy = W - card.width - 90, (H - card.height) // 2 + 20
    place(base, card, (cx, cy))
    d = ImageDraw.Draw(base)
    fg = (231, 234, 240) if dark else (26, 31, 38)
    mut = (154, 163, 178) if dark else (107, 114, 128)
    d.text((110, 310), SSIK, font=font(F_BD, 96), fill=fg)
    d.text((118, 445), "Immediately Law", font=font(F_RG, 36), fill=mut)
    d.text((118, 555), "Copy any legal text. (Ctrl + C)",
           font=font(F_BD, 42), fill=fg)
    d.text((118, 620), "The article appears instantly,",
           font=font(F_RG, 36), fill=mut)
    d.text((118, 678), "bottom-right of your screen.",
           font=font(F_RG, 36), fill=mut)
    d.text((118, 780), "Offline-first · 5,600 statutes · Daily updates",
           font=font(F_RG, 28), fill=mut)
    base.save(os.path.join(OUT, out), optimize=True)
    print(out, os.path.getsize(os.path.join(OUT, out)))


def gallery():
    base = grad((247, 248, 250), (231, 236, 242))
    img = Image.open(os.path.join(ROOT, "assets", "screenshot.png"))
    scale = 940 / img.width
    img = img.resize((940, int(img.height * scale)), Image.LANCZOS)
    place(base, img, (int((W - 940) / 2), int((H - img.height) / 2)))
    d = ImageDraw.Draw(base)
    d.text((int((W - 940) / 2), 250), SSIK, font=font(F_BD, 96),
           fill=(26, 31, 38))
    d.text((int((W - 940) / 2) + 8, 385), "Immediately Law",
           font=font(F_RG, 36), fill=(107, 114, 128))
    base.save(os.path.join(OUT, "03_gallery.png"), optimize=True)
    print("03_gallery.png", os.path.getsize(os.path.join(OUT, "03_gallery.png")))


light = os.path.join(CARDS, "card2_light.png")
dark = os.path.join(CARDS, "card2_dark.png")
shot_card(light, "01_light.png", dark=False)
shot_card(dark, "02_dark.png", dark=True)
gallery()
