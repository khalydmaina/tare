#!/usr/bin/env python3
"""Generate Tare logo lockups, marks, wordmarks, favicons, and SVGs."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path("/home/workdir/artifacts/tare-brand-kit/logos")
OUT.mkdir(parents=True, exist_ok=True)

BG_DARK = (10, 10, 10, 255)
FG_DARK = (240, 240, 240, 255)
BG_LIGHT = (255, 255, 255, 255)
FG_LIGHT = (10, 10, 10, 255)
MUTED_DARK = (163, 163, 163, 255)
MUTED_LIGHT = (82, 82, 82, 255)

PLEX = "/usr/share/fonts/SlidesCarnival/google/IBM Plex Sans/static/IBMPlexSans-{}.ttf"
PLEX_MED = PLEX.format("Medium")
PLEX_REG = PLEX.format("Regular")
PLEX_LIGHT = PLEX.format("Light")


def new_canvas(w, h, bg):
    return Image.new("RGBA", (w, h), bg)


def draw_mark(draw, cx, cy, size, fg, stroke=None):
    """Geometric tare mark: asymmetric masses on a beam over a zero plate.

    Left mass = stated (gross). Right mass = calibrated (net).
    Beam + knife-edge fulcrum + tare plate (zero line).
    """
    s = size
    beam_y = cy - int(s * 0.04)
    beam_h = max(2, int(s * 0.055))
    beam_w = int(s * 0.78)
    beam_x = cx - beam_w // 2

    # Beam
    draw.rectangle([beam_x, beam_y, beam_x + beam_w, beam_y + beam_h], fill=fg)

    # Left mass (gross) — taller and wider
    lw, lh = int(s * 0.20), int(s * 0.34)
    lx = beam_x + int(s * 0.06)
    ly = beam_y - lh
    draw.rectangle([lx, ly, lx + lw, beam_y + 1], fill=fg)

    # Right mass (net) — shorter, narrower
    rw, rh = int(s * 0.12), int(s * 0.16)
    rx = beam_x + beam_w - int(s * 0.06) - rw
    ry = beam_y - rh
    draw.rectangle([rx, ry, rx + rw, beam_y + 1], fill=fg)

    # Fulcrum (knife edge)
    f_top = beam_y + beam_h
    f_h = int(s * 0.16)
    f_half = int(s * 0.09)
    draw.polygon(
        [(cx, f_top), (cx - f_half, f_top + f_h), (cx + f_half, f_top + f_h)],
        fill=fg,
    )

    # Tare plate (zero line)
    plate_y = f_top + f_h + int(s * 0.06)
    plate_w = int(s * 0.36)
    plate_h = max(2, int(s * 0.04))
    draw.rectangle(
        [cx - plate_w // 2, plate_y, cx + plate_w // 2, plate_y + plate_h],
        fill=fg,
    )

    # Zero tick rising from plate
    tick_h = int(s * 0.07)
    tick_w = max(2, int(s * 0.025))
    draw.rectangle(
        [cx - tick_w // 2, plate_y - tick_h, cx + tick_w // 2, plate_y + 1],
        fill=fg,
    )


def framed_mark(size, fg, bg, with_frame=True):
    img = new_canvas(size, size, bg)
    d = ImageDraw.Draw(img)
    inset = int(size * 0.08)
    if with_frame:
        sw = max(2, int(size * 0.018))
        d.rectangle(
            [inset, inset, size - inset - 1, size - inset - 1],
            outline=fg,
            width=sw,
        )
        inner = size - inset * 2 - sw * 2
        draw_mark(d, size // 2, int(size * 0.52), int(inner * 0.78), fg)
    else:
        draw_mark(d, size // 2, int(size * 0.50), int(size * 0.72), fg)
    return img


def wordmark(width, height, fg, bg, tracking=18, size_pt=None):
    img = new_canvas(width, height, bg)
    d = ImageDraw.Draw(img)
    if size_pt is None:
        size_pt = int(height * 0.42)
    font = ImageFont.truetype(PLEX_MED, size_pt)
    text = "TARE"
    # Manual tracking
    glyphs = []
    for ch in text:
        bbox = font.getbbox(ch)
        glyphs.append((ch, bbox[2] - bbox[0], bbox[3] - bbox[1]))
    total = sum(g[1] for g in glyphs) + tracking * (len(glyphs) - 1)
    x = (width - total) // 2
    # Vertical center using capital H metrics
    hb = font.getbbox("H")
    y = (height - (hb[3] - hb[1])) // 2 - hb[1]
    for ch, w, _ in glyphs:
        d.text((x, y), ch, font=font, fill=fg)
        x += w + tracking
    return img


def lockup(width, height, fg, bg, muted, stacked=False):
    img = new_canvas(width, height, bg)
    if stacked:
        mark_s = int(height * 0.48)
        mark = framed_mark(mark_s, fg, bg, with_frame=True)
        mx = (width - mark_s) // 2
        my = int(height * 0.10)
        img.alpha_composite(mark, (mx, my))
        wm = wordmark(width, int(height * 0.28), fg, (0, 0, 0, 0), tracking=14)
        img.alpha_composite(wm, (0, int(height * 0.58)))
        d = ImageDraw.Draw(img)
        font = ImageFont.truetype(PLEX_LIGHT, max(12, int(height * 0.055)))
        sub = "ZERO THE CONFIDENCE"
        bbox = font.getbbox(sub)
        sw = bbox[2] - bbox[0]
        d.text(((width - sw) // 2, int(height * 0.82)), sub, font=font, fill=muted)
    else:
        mark_s = int(height * 0.72)
        mark = framed_mark(mark_s, fg, bg, with_frame=True)
        my = (height - mark_s) // 2
        mx = int(width * 0.06)
        img.alpha_composite(mark, (mx, my))
        rest_x = mx + mark_s
        rest_w = width - rest_x
        wm = wordmark(rest_w, int(height * 0.55), fg, (0, 0, 0, 0), tracking=16)
        img.alpha_composite(wm, (rest_x, int(height * 0.12)))
        d = ImageDraw.Draw(img)
        font = ImageFont.truetype(PLEX_LIGHT, max(11, int(height * 0.12)))
        sub = "ZERO THE CONFIDENCE"
        bbox = font.getbbox(sub)
        # Center subtitle under wordmark within remaining column
        sw = bbox[2] - bbox[0]
        sx = rest_x + (rest_w - sw) // 2
        d.text((sx, int(height * 0.66)), sub, font=font, fill=muted)
    return img


def save(img, name):
    path = OUT / name
    img.save(path, "PNG")
    print("wrote", path, img.size)


# Dark / light marks
for theme, fg, bg in (("dark", FG_DARK, BG_DARK), ("light", FG_LIGHT, BG_LIGHT)):
    save(framed_mark(1024, fg, bg, True), f"tare-mark-{theme}-1024.png")
    save(framed_mark(512, fg, bg, True), f"tare-mark-{theme}-512.png")
    save(framed_mark(256, fg, bg, True), f"tare-mark-{theme}-256.png")
    save(framed_mark(128, fg, bg, True), f"tare-mark-{theme}-128.png")
    save(wordmark(1600, 400, fg, bg, tracking=22), f"tare-wordmark-{theme}.png")
    muted = MUTED_DARK if theme == "dark" else MUTED_LIGHT
    save(lockup(2000, 560, fg, bg, muted, stacked=False), f"tare-lockup-{theme}.png")
    save(lockup(1200, 1400, fg, bg, muted, stacked=True), f"tare-lockup-stacked-{theme}.png")

# Transparent mark (no background) for overlays
trans = framed_mark(1024, FG_DARK, (0, 0, 0, 0), True)
save(trans, "tare-mark-transparent-light-fg.png")
trans2 = framed_mark(1024, (255, 255, 255, 255), (0, 0, 0, 0), True)
save(trans2, "tare-mark-transparent-dark-fg.png")

# Favicons
fav_bg = framed_mark(256, FG_DARK, BG_DARK, True)
save(fav_bg.resize((64, 64), Image.Resampling.LANCZOS), "favicon-64.png")
save(fav_bg.resize((32, 32), Image.Resampling.LANCZOS), "favicon-32.png")
save(fav_bg.resize((16, 16), Image.Resampling.LANCZOS), "favicon-16.png")

# App icon rounded-ish (still severe 6% radius drawn as square frame — already framed)
save(framed_mark(1024, FG_DARK, BG_DARK, True), "app-icon-1024.png")

# SVG
svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Tare mark">
  <title>Tare</title>
  <rect width="512" height="512" fill="#0A0A0A"/>
  <rect x="40" y="40" width="432" height="432" fill="none" stroke="#F0F0F0" stroke-width="10"/>
  <!-- left mass (gross) -->
  <rect x="118" y="148" width="78" height="132" fill="#F0F0F0"/>
  <!-- right mass (net) -->
  <rect x="328" y="218" width="48" height="62" fill="#F0F0F0"/>
  <!-- beam -->
  <rect x="96" y="276" width="320" height="22" fill="#F0F0F0"/>
  <!-- fulcrum -->
  <polygon points="256,298 220,360 292,360" fill="#F0F0F0"/>
  <!-- tare plate + zero tick -->
  <rect x="184" y="386" width="144" height="16" fill="#F0F0F0"/>
  <rect x="250" y="368" width="12" height="22" fill="#F0F0F0"/>
</svg>
"""
(OUT / "tare-mark.svg").write_text(svg)

svg_inv = svg.replace("#0A0A0A", "#FFFFFF").replace("#F0F0F0", "#0A0A0A")
# after first replace fill of canvas is white; stroke/marks became black. Good.
# Wait: first replace changes bg AND would change fg if we did fg first.
# We replaced bg first then fg #F0F0F0 -> #0A0A0A. Canvas was already #FFFFFF so OK.
(OUT / "tare-mark-inverted.svg").write_text(svg_inv)

svg_word = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 160" role="img" aria-label="Tare wordmark">
  <rect width="760" height="160" fill="#0A0A0A"/>
  <text x="380" y="104" text-anchor="middle"
        font-family="IBM Plex Sans, Inter, Helvetica, Arial, sans-serif"
        font-size="92" font-weight="500" letter-spacing="18" fill="#F0F0F0">TARE</text>
</svg>
"""
(OUT / "tare-wordmark.svg").write_text(svg_word)

print("done")
