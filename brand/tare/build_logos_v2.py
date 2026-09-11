#!/usr/bin/env python3
"""Tare logo v1.1 — scale icon + Poppins ExtraBold wordmark, no ®."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path("/home/workdir/artifacts/tare-brand-kit/logos")
OUT.mkdir(parents=True, exist_ok=True)

BG = (10, 10, 10, 255)
BG_ICON = (17, 17, 17, 255)
BG_LIGHT = (255, 255, 255, 255)
FG = (240, 240, 240, 255)
FG_W = (255, 255, 255, 255)
INK = (10, 10, 10, 255)
RED = (239, 68, 68, 255)  # #EF4444
MUTED = (163, 163, 163, 255)

POPPINS_XB = "/usr/share/fonts/SlidesCarnival/google/Poppins/Poppins-ExtraBold.ttf"
POPPINS_B = "/usr/share/fonts/SlidesCarnival/google/Poppins/Poppins-Bold.ttf"


def rounded_rect(draw, xy, r, fill):
    x0, y0, x1, y1 = xy
    r = max(0, min(r, int((x1 - x0) / 2), int((y1 - y0) / 2)))
    draw.rounded_rectangle(xy, radius=r, fill=fill)


def draw_scale(draw, cx, cy, size, fg, red):
    """Simplified scale: tall white mass, red net mass, capsule beam, down-triangle."""
    s = float(size)
    beam_w = s * 0.72
    beam_h = s * 0.105
    beam_x0 = cx - beam_w / 2
    beam_y0 = cy + s * 0.02
    beam_x1 = beam_x0 + beam_w
    beam_y1 = beam_y0 + beam_h
    rounded_rect(draw, [beam_x0, beam_y0, beam_x1, beam_y1], beam_h / 2, fg)

    # Left mass (gross)
    lw = s * 0.168
    lh = s * 0.38
    lx = beam_x0 + s * 0.055
    ly = beam_y0 - lh
    draw.rectangle([lx, ly, lx + lw, beam_y0 + 1], fill=fg)

    # Right mass (net / inflation) — red
    rw = s * 0.125
    rh = s * 0.168
    rx = beam_x1 - s * 0.055 - rw
    ry = beam_y0 - rh
    draw.rectangle([rx, ry, rx + rw, beam_y0 + 1], fill=red)

    # Fulcrum — downward triangle
    th = s * 0.195
    tw = s * 0.195
    top = beam_y1 - 1
    draw.polygon(
        [(cx, top + th), (cx - tw / 2, top), (cx + tw / 2, top)],
        fill=fg,
    )


def app_icon(size, dark=True):
    bg = BG_ICON if dark else (245, 245, 245, 255)
    fg = FG_W if dark else INK
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rad = int(size * 0.22)
    rounded_rect(d, [0, 0, size - 1, size - 1], rad, bg)
    draw_scale(d, size / 2, size * 0.50, size * 0.78, fg, RED)
    return img


def mark_plain(size, dark=True, transparent=False):
    if transparent:
        bg = (0, 0, 0, 0)
    else:
        bg = BG if dark else BG_LIGHT
    fg = FG_W if dark else INK
    img = Image.new("RGBA", (size, size), bg)
    d = ImageDraw.Draw(img)
    draw_scale(d, size / 2, size * 0.50, size * 0.82, fg, RED)
    return img


def wordmark(width, height, fg, bg, weight="bold", align="center"):
    img = Image.new("RGBA", (width, height), bg)
    d = ImageDraw.Draw(img)
    path = POPPINS_XB if weight == "extrabold" else POPPINS_B
    size_pt = int(height * 0.42)
    font = ImageFont.truetype(path, size_pt)
    text = "tare"
    bbox = font.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if align == "left":
        x = -bbox[0]
    else:
        x = (width - tw) // 2 - bbox[0]
    y = (height - th) // 2 - bbox[1]
    d.text((x, y), text, font=font, fill=fg)
    return img


def wordmark_tight(fg, bg, pad_x=80, pad_y=48, size_pt=180):
    font = ImageFont.truetype(POPPINS_B, size_pt)
    bbox = font.getbbox("tare")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = tw + pad_x * 2, th + pad_y * 2
    img = Image.new("RGBA", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.text((pad_x - bbox[0], pad_y - bbox[1]), "tare", font=font, fill=fg)
    return img


def lockup_horizontal(width, height, dark=True):
    bg = BG if dark else BG_LIGHT
    fg = FG_W if dark else INK
    img = Image.new("RGBA", (width, height), bg)
    icon_s = int(height * 0.62)
    icon = app_icon(icon_s, dark=dark)
    iy = (height - icon_s) // 2
    ix = int(width * 0.06)
    img.alpha_composite(icon, (ix, iy))
    rest_x = ix + icon_s + int(height * 0.18)
    wm = wordmark(width - rest_x - ix, height, fg, (0, 0, 0, 0), align="left")
    img.alpha_composite(wm, (rest_x, 0))
    return img


def usage_board():
    """Recreate the user's two-panel reference: app icon + wordmark-only."""
    W, H = 2000, 780
    img = Image.new("RGBA", (W, H), (12, 12, 12, 255))
    d = ImageDraw.Draw(img)
    # left card
    rounded_rect(d, [40, 40, 620, 740], 48, (20, 20, 20, 255))
    icon = app_icon(420, dark=True)
    img.alpha_composite(icon, (140, 110))
    cap = ImageFont.truetype(POPPINS_B, 28)
    # caption
    font_cap = ImageFont.truetype(
        "/usr/share/fonts/SlidesCarnival/google/IBM Plex Sans/static/IBMPlexSans-Regular.ttf",
        26,
    )
    t = "app icon"
    bb = font_cap.getbbox(t)
    d.text((330 - (bb[2] - bb[0]) / 2, 660), t, font=font_cap, fill=MUTED)
    # right card
    rounded_rect(d, [660, 40, 1960, 740], 48, (18, 18, 18, 255))
    wm = wordmark(1200, 320, FG_W, (0, 0, 0, 0), weight="bold")
    img.alpha_composite(wm, (710, 200))
    t2 = "wordmark-only, for tight spaces"
    bb2 = font_cap.getbbox(t2)
    d.text((1310 - (bb2[2] - bb2[0]) / 2, 500), t2, font=font_cap, fill=MUTED)
    return img


def save(img, name):
    p = OUT / name
    img.save(p, "PNG")
    print("wrote", p.name, img.size)


# Icons
for s in (1024, 512, 256, 180, 128):
    save(app_icon(s, True), f"tare-icon-dark-{s}.png")
    save(app_icon(s, False), f"tare-icon-light-{s}.png")

save(app_icon(1024, True), "app-icon-1024.png")
save(mark_plain(1024, True), "tare-mark-dark-1024.png")
save(mark_plain(512, True), "tare-mark-dark-512.png")
save(mark_plain(256, True), "tare-mark-dark-256.png")
save(mark_plain(1024, False), "tare-mark-light-1024.png")
save(mark_plain(512, False), "tare-mark-light-512.png")
save(mark_plain(1024, True, True), "tare-mark-transparent-dark-fg.png")
save(mark_plain(1024, False, True), "tare-mark-transparent-light-fg.png")

# Favicons from the icon
ico = app_icon(256, True)
for s in (64, 32, 16):
    save(ico.resize((s, s), Image.Resampling.LANCZOS), f"favicon-{s}.png")

# Wordmarks
save(wordmark_tight(FG_W, BG, 120, 80, 220), "tare-wordmark-dark.png")
save(wordmark_tight(INK, BG_LIGHT, 120, 80, 220), "tare-wordmark-light.png")
save(wordmark_tight(FG_W, (0, 0, 0, 0), 80, 40, 220), "tare-wordmark-transparent-white.png")
save(wordmark_tight(INK, (0, 0, 0, 0), 80, 40, 220), "tare-wordmark-transparent-black.png")

# Lockups
save(lockup_horizontal(2000, 560, True), "tare-lockup-dark.png")
save(lockup_horizontal(2000, 560, False), "tare-lockup-light.png")
save(usage_board(), "tare-system-board.png")

# SVG icon + wordmark
svg_icon = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Tare">
  <rect width="512" height="512" rx="112" fill="#111111"/>
  <!-- left mass -->
  <rect x="118" y="118" width="68" height="156" fill="#FFFFFF"/>
  <!-- red mass -->
  <rect x="318" y="206" width="52" height="68" fill="#EF4444"/>
  <!-- beam -->
  <rect x="96" y="270" width="320" height="44" rx="22" fill="#FFFFFF"/>
  <!-- fulcrum -->
  <polygon points="256,314 216,394 296,394" fill="#FFFFFF"/>
</svg>
"""
(OUT / "tare-mark.svg").write_text(svg_icon)

svg_wm = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 240" role="img" aria-label="tare">
  <rect width="720" height="240" fill="#0A0A0A"/>
  <text x="360" y="162" text-anchor="middle"
        font-family="Poppins, Montserrat, Helvetica, Arial, sans-serif"
        font-size="140" font-weight="700" fill="#FFFFFF">tare</text>
</svg>
"""
(OUT / "tare-wordmark.svg").write_text(svg_wm)

print("done")
