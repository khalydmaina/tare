#!/usr/bin/env python3
"""Tare Brand Kit — A4 forensic brand book."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

ROOT = Path("/home/workdir/artifacts/tare-brand-kit")
LOGO = ROOT / "logos"
OUT = ROOT / "Tare_Brand_Kit.pdf"

FONT = "/usr/share/fonts/SlidesCarnival/google/IBM Plex Sans/static"
MONO = "/usr/share/fonts/SlidesCarnival/google/IBM Plex Mono"
pdfmetrics.registerFont(TTFont("Plex", f"{FONT}/IBMPlexSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("PlexMed", f"{FONT}/IBMPlexSans-Medium.ttf"))
pdfmetrics.registerFont(TTFont("PlexLight", f"{FONT}/IBMPlexSans-Light.ttf"))
pdfmetrics.registerFont(TTFont("PlexBold", f"{FONT}/IBMPlexSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("PlexMono", f"{MONO}/IBMPlexMono-Regular.ttf"))
pdfmetrics.registerFont(TTFont("PlexMonoMed", f"{MONO}/IBMPlexMono-Medium.ttf"))
pdfmetrics.registerFont(TTFont("Poppins", "/usr/share/fonts/SlidesCarnival/google/Poppins/Poppins-Bold.ttf"))
pdfmetrics.registerFont(TTFont("PoppinsXB", "/usr/share/fonts/SlidesCarnival/google/Poppins/Poppins-ExtraBold.ttf"))

W, H = A4
M = 22 * mm
CANVAS = (0.039, 0.039, 0.039)
PANEL = (0.067, 0.067, 0.067)
ELEV = (0.086, 0.086, 0.086)
BORDER = (0.133, 0.133, 0.133)
BORDER2 = (0.20, 0.20, 0.20)
TEXT = (0.941, 0.941, 0.941)
MUTED = (0.639, 0.639, 0.639)
WHITE = (1, 1, 1)
GREEN = (0.133, 0.773, 0.369)
RED = (0.937, 0.267, 0.267)
REDDEEP = (0.498, 0.114, 0.114)
INK = (0.039, 0.039, 0.039)

PAGES = []


def rgb_hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


class Book:
    def __init__(self):
        self.c = canvas.Canvas(str(OUT), pagesize=A4)
        self.c.setTitle("Tare — Brand Kit")
        self.c.setAuthor("Tare Design")
        self.c.setSubject("Brand system for Tare, an agentic trader with evidence-based brakes")
        self.n = 0

    def new(self, folio=True, number=None):
        if self.n:
            self.c.showPage()
        self.n += 1
        self.c.setFillColorRGB(*CANVAS)
        self.c.rect(0, 0, W, H, fill=1, stroke=0)
        if folio:
            self.footer(number or self.n)

    def footer(self, n):
        self.c.setFillColorRGB(*BORDER)
        self.c.rect(M, 14 * mm, W - 2 * M, 0.3, fill=1, stroke=0)
        self.c.setFillColorRGB(*MUTED)
        self.c.setFont("PlexMono", 7)
        self.c.drawString(M, 9 * mm, "tare  ·  BRAND KIT  ·  1.1")
        self.c.drawRightString(W - M, 9 * mm, f"{n:02d}")

    def kicker(self, text, x, y):
        self.c.setFillColorRGB(*MUTED)
        self.c.setFont("PlexMono", 8)
        self.c.drawString(x, y, text.upper())

    def h1(self, text, x, y, size=26):
        self.c.setFillColorRGB(*WHITE)
        self.c.setFont("PlexMed", size)
        self.c.drawString(x, y, text)

    def body(self, text, x, y, size=10, color=TEXT, font="Plex"):
        self.c.setFillColorRGB(*color)
        self.c.setFont(font, size)
        self.c.drawString(x, y, text)

    def wrap(self, text, x, y, width, size=10, leading=15, color=TEXT, font="Plex"):
        self.c.setFont(font, size)
        self.c.setFillColorRGB(*color)
        words = text.split()
        line = ""
        yy = y
        for w in words:
            trial = (line + " " + w).strip()
            if self.c.stringWidth(trial, font, size) <= width:
                line = trial
            else:
                self.c.drawString(x, yy, line)
                yy -= leading
                line = w
        if line:
            self.c.drawString(x, yy, line)
            yy -= leading
        return yy

    def rule(self, x, y, w, color=BORDER):
        self.c.setFillColorRGB(*color)
        self.c.rect(x, y, w, 0.4, fill=1, stroke=0)

    def panel(self, x, y, w, h, fill=PANEL, stroke=BORDER):
        self.c.setFillColorRGB(*fill)
        self.c.setStrokeColorRGB(*stroke)
        self.c.setLineWidth(0.8)
        self.c.roundRect(x, y, w, h, 3, fill=1, stroke=1)

    def save(self):
        self.c.save()


def cover(b: Book):
    b.new(folio=False)
    c = b.c
    # thin frame
    c.setStrokeColorRGB(*BORDER2)
    c.setLineWidth(0.8)
    c.rect(12 * mm, 12 * mm, W - 24 * mm, H - 24 * mm, fill=0, stroke=1)

    mark = ImageReader(str(LOGO / "tare-icon-dark-512.png"))
    c.drawImage(mark, (W - 38 * mm) / 2, H - 78 * mm, 38 * mm, 38 * mm, mask="auto")

    c.setFillColorRGB(*WHITE)
    c.setFont("Poppins", 52)
    c.drawCentredString(W / 2, H - 102 * mm, "tare")

    c.setFillColorRGB(*MUTED)
    c.setFont("PlexMono", 9)
    sub = "ZERO THE CONFIDENCE.  WEIGH THE RECORD."
    c.drawCentredString(W / 2, H - 114 * mm, sub)

    b.rule(M + 20 * mm, H - 124 * mm, W - 2 * M - 40 * mm)

    c.setFillColorRGB(*TEXT)
    c.setFont("Plex", 11)
    blurb = "Brand kit for an agentic paper trader with a non-LLM Inspector."
    c.drawCentredString(W / 2, H - 136 * mm, blurb)
    c.setFillColorRGB(*MUTED)
    c.setFont("Plex", 10)
    c.drawCentredString(W / 2, H - 144 * mm, "Flight Recorder  ·  Guarded vs Shadow  ·  Attack Lab")

    # metaphor strip
    b.panel(M, 32 * mm, W - 2 * M, 38 * mm)
    c.setFillColorRGB(*MUTED)
    c.setFont("PlexMono", 7.5)
    c.drawString(M + 8 * mm, 60 * mm, "METAPHOR")
    c.setFillColorRGB(*TEXT)
    c.setFont("Plex", 10)
    lines = [
        "Tare is the empty weight you subtract so the scale reads what is actually there.",
        "Stated confidence is gross. Calibrated probability is net.",
        "The Inspector zeros the model before size is allowed to move.",
    ]
    yy = 50 * mm
    for ln in lines:
        c.drawString(M + 8 * mm, yy, ln)
        yy -= 5.2 * mm

    c.setFillColorRGB(*MUTED)
    c.setFont("PlexMono", 8)
    c.drawString(M, 18 * mm, "VERSION 1.1")
    c.drawRightString(W - M, 18 * mm, "BITGET AI  ·  GENESIS S2")


def contents(b: Book):
    b.new()
    b.kicker("Index", M, H - 28 * mm)
    b.h1("Contents", M, H - 40 * mm)
    items = [
        ("01", "Name & metaphor", "Why Tare, not another LLM judge"),
        ("02", "Positioning", "Brand spine, one-liner, what it is not"),
        ("03", "Audience", "Judges, builders, operators"),
        ("04", "Logo system", "Mark, wordmark, lockups, favicon"),
        ("05", "Clear space & misuse", "Construction and prohibitions"),
        ("06", "Color", "Semantic tokens only"),
        ("07", "Typography", "Plex Sans / Plex Mono / scale"),
        ("08", "Voice", "Vocabulary, taglines, microcopy"),
        ("09", "UI system", "Radius, density, components"),
        ("10", "Product surfaces", "Flight Recorder, Attack Lab, landing"),
        ("11", "Evidence rules", "Gates, attacks, honesty aesthetic"),
        ("12", "Do / Don’t", "Implementation notes"),
    ]
    y = H - 56 * mm
    for num, title, desc in items:
        b.rule(M, y + 8 * mm, W - 2 * M)
        b.c.setFont("PlexMono", 9)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M, y, num)
        b.c.setFont("PlexMed", 12)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M + 18 * mm, y, title)
        b.c.setFont("Plex", 10)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawRightString(W - M, y, desc)
        y -= 16 * mm


def metaphor(b: Book):
    b.new()
    b.kicker("01  ·  Name", M, H - 28 * mm)
    b.h1("Tare the model.", M, H - 40 * mm)
    y = b.wrap(
        "On a scale, tare is the mechanical act of zeroing out the empty container so the instrument reports true net weight. Tare the product does the same thing to an LLM trader: it subtracts inflated confidence and reads the calibrated probability underneath.",
        M, H - 54 * mm, W - 2 * M, size=11, leading=16,
    )
    y = b.wrap(
        "The name is short, unfashionable, and exact. It is a verb and a measurement. It does not celebrate intelligence. It describes a correction.",
        M, y - 2 * mm, W - 2 * M, size=11, leading=16,
    )

    # three columns
    cols = [
        ("GROSS", "Stated confidence", "The model’s P(TP before SL). A claim. Often overweight."),
        ("TARE", "Inspector correction", "Historical hit rate, independent sensors, hard limits. The empty weight."),
        ("NET", "Calibrated p / size", "What is allowed to pass the gate. The number that may trade."),
    ]
    cw = (W - 2 * M - 10 * mm) / 3
    top = y - 14 * mm
    for i, (k, t, d) in enumerate(cols):
        x = M + i * (cw + 5 * mm)
        b.panel(x, top - 52 * mm, cw, 52 * mm)
        b.c.setFont("PlexMono", 8)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(x + 6 * mm, top - 10 * mm, k)
        b.c.setFont("PlexMed", 11)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(x + 6 * mm, top - 18 * mm, t)
        b.wrap(d, x + 6 * mm, top - 28 * mm, cw - 12 * mm, size=8.5, leading=12, color=MUTED)

    y = top - 64 * mm
    b.kicker("Pronunciation & writing", M, y)
    y -= 8 * mm
    rules = [
        ("Say", "tair  —  same vowel as “care.” Not “tar-ee.”"),
        ("Write", "tare wordmark  ·  Tare in sentences  ·  TARE only as a terminal stamp."),
        ("Never", "TareAI   Tare Bot   The Tare   tare®   ProsecutorAI"),
        ("Keep", "Inspector, Flight Recorder, Shadow, Gate G0–G2, Attack A1–A5."),
    ]
    for lab, txt in rules:
        b.c.setFont("PlexMono", 8)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M, y, lab.upper())
        b.c.setFont("Plex", 10)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M + 28 * mm, y, txt)
        y -= 8 * mm

    y -= 4 * mm
    b.panel(M, 22 * mm, W - 2 * M, 28 * mm)
    b.c.setFont("PlexMono", 8)
    b.c.setFillColorRGB(*MUTED)
    b.c.drawString(M + 8 * mm, 42 * mm, "ONE-LINER")
    b.c.setFont("PlexMed", 11)
    b.c.setFillColorRGB(*WHITE)
    b.c.drawString(M + 8 * mm, 32 * mm, "An AI trader with brakes that tighten where the model can’t be trusted.")


def positioning(b: Book):
    b.new()
    b.kicker("02  ·  Positioning", M, H - 28 * mm)
    b.h1("Not a smarter judge.", M, H - 40 * mm)
    b.h1("A scale.", M, H - 50 * mm)

    y = b.wrap(
        "A second AI reviewing the first shares the same blind spots. When the trader is fooled, the peer reviewer fails at the same moment. Tare never asks another model to grade a model. It asks the record, and independent evidence the trader cannot fake.",
        M, H - 64 * mm, W - 2 * M, size=11, leading=16,
    )

    # is / is not
    colw = (W - 2 * M - 8 * mm) / 2
    top = y - 8 * mm
    b.panel(M, 28 * mm, colw, top - 28 * mm)
    b.panel(M + colw + 8 * mm, 28 * mm, colw, top - 28 * mm)

    b.c.setFont("PlexMono", 8)
    b.c.setFillColorRGB(*GREEN)
    b.c.drawString(M + 8 * mm, top - 12 * mm, "IT IS")
    b.c.setFillColorRGB(*RED)
    b.c.drawString(M + colw + 16 * mm, top - 12 * mm, "IT IS NOT")

    is_items = [
        "Rules-based market-structure setups",
        "LLM proposes take/skip + confidence",
        "Non-LLM Inspector sizes or vetoes",
        "Calibration against stated confidence",
        "Independent anomaly sensors",
        "Hard risk limits the model cannot edit",
        "Shadow book (unguarded counterfactual)",
        "Attack Lab that poisons trader inputs",
        "Flight Recorder of every decision",
    ]
    not_items = [
        "A smarter LLM that reviews another LLM",
        "A signal group or call channel",
        "A meme-coin launcher",
        "A DeFi yield product",
        "A black-box “AI alpha” flex",
        "Web3 carnival branding",
        "Friendly toast notifications for harm",
        "Social trading, NFTs, or a mobile app",
        "Anything that hides a bad metric",
    ]
    yy = top - 24 * mm
    for t in is_items:
        b.c.setFont("Plex", 9)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M + 8 * mm, yy, "·  " + t)
        yy -= 7.2 * mm
    yy = top - 24 * mm
    for t in not_items:
        b.c.setFont("Plex", 9)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M + colw + 16 * mm, yy, "·  " + t)
        yy -= 7.2 * mm


def audience(b: Book):
    b.new()
    b.kicker("03  ·  Audience", M, H - 28 * mm)
    b.h1("Prove it in seconds.", M, H - 40 * mm)
    rows = [
        ("Hackathon judges", "Novelty, rigor, demo clarity", "This is not another LLM trader. It has brakes. We attack them."),
        ("Agentic-trading builders", "Trust, risk, adversarial robustness", "Calibration vs stated confidence. Veto with numbers. Green vs red equity."),
        ("Technical reviewers", "Honesty under attack", "A4 slips past calibration-only. Full gate G2 catches it."),
        ("Live operator", "Job-to-be-done", "Show me whether the AI is overconfident — and whether the gate stopped it."),
    ]
    y = H - 54 * mm
    for who, care, prove in rows:
        b.panel(M, y - 28 * mm, W - 2 * M, 30 * mm)
        b.c.setFont("PlexMed", 11)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M + 6 * mm, y - 8 * mm, who)
        b.c.setFont("Plex", 9)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M + 6 * mm, y - 16 * mm, care)
        b.c.setFont("Plex", 9)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M + 6 * mm, y - 24 * mm, prove)
        y -= 36 * mm

    b.panel(M, 24 * mm, W - 2 * M, 28 * mm, fill=ELEV)
    b.c.setFont("PlexMono", 8)
    b.c.setFillColorRGB(*MUTED)
    b.c.drawString(M + 8 * mm, 42 * mm, "SUCCESS TEST")
    b.c.setFont("Plex", 10)
    b.c.setFillColorRGB(*TEXT)
    b.c.drawString(M + 8 * mm, 32 * mm, "In 5 seconds: this product distrusts AI confidence. It does not celebrate it.")


def logo_system(b: Book):
    b.new()
    b.kicker("04  ·  Logo system", M, H - 28 * mm)
    b.h1("Mark, word, lockup.", M, H - 40 * mm)
    y = b.wrap(
        "Two parts, never mixed in tight chrome. The icon is the scale: white gross mass, red net mass, capsule beam, downward fulcrum. The wordmark is lowercase tare in Poppins Bold. No registered-mark glyph. No gavel, no brain, no chain link.",
        M, H - 52 * mm, W - 2 * M, size=10.5, leading=15,
    )

    # two marks
    dark = ImageReader(str(LOGO / "tare-icon-dark-512.png"))
    light = ImageReader(str(LOGO / "tare-icon-light-512.png"))
    box = 48 * mm
    b.panel(M, y - box - 18 * mm, box + 10 * mm, box + 16 * mm, fill=CANVAS)
    b.c.drawImage(dark, M + 5 * mm, y - box - 10 * mm, box, box, mask="auto")
    b.c.setFillColorRGB(*MUTED)
    b.c.setFont("PlexMono", 7)
    b.c.drawString(M, y - box - 24 * mm, "MARK  ·  DARK")

    # light mark on light panel
    lx = M + box + 24 * mm
    b.c.setFillColorRGB(1, 1, 1)
    b.c.roundRect(lx, y - box - 18 * mm, box + 10 * mm, box + 16 * mm, 3, fill=1, stroke=0)
    b.c.drawImage(light, lx + 5 * mm, y - box - 10 * mm, box, box, mask="auto")
    b.c.setFillColorRGB(*MUTED)
    b.c.setFont("PlexMono", 7)
    b.c.drawString(lx, y - box - 24 * mm, "MARK  ·  LIGHT")

    # wordmark
    wm = ImageReader(str(LOGO / "tare-wordmark-dark.png"))
    wy = y - box - 72 * mm
    b.panel(M, wy, W - 2 * M, 32 * mm, fill=CANVAS)
    b.c.drawImage(wm, M + 8 * mm, wy + 4 * mm, 72 * mm, 24 * mm, mask="auto")
    b.c.setFillColorRGB(*MUTED)
    b.c.setFont("PlexMono", 7)
    b.c.drawString(M + 88 * mm, wy + 14 * mm, "WORDMARK  ·  POPPINS BOLD  ·  NO REGISTERED MARK")

    # lockup
    lk = ImageReader(str(LOGO / "tare-lockup-dark.png"))
    ly = 26 * mm
    b.panel(M, ly, W - 2 * M, 38 * mm, fill=CANVAS)
    b.c.drawImage(lk, M + 6 * mm, ly + 4 * mm, 120 * mm, 30 * mm, mask="auto")
    b.c.setFillColorRGB(*MUTED)
    b.c.setFont("PlexMono", 7)
    b.c.drawRightString(W - M - 6 * mm, ly + 16 * mm, "PRIMARY LOCKUP")


def construction(b: Book):
    b.new()
    b.kicker("05  ·  Construction", M, H - 28 * mm)
    b.h1("Clear space is the beam.", M, H - 40 * mm)
    y = b.wrap(
        "Clear space on all sides equals the height of the icon's capsule beam. Do not crowd the lockup. Minimum digital size: icon 28 px, wordmark 72 px wide. Favicon and app icon use the scale only.",
        M, H - 52 * mm, W - 2 * M, size=10.5, leading=15,
    )

    mark = ImageReader(str(LOGO / "tare-icon-dark-512.png"))
    s = 52 * mm
    cx = M + 8 * mm
    cy = y - s - 10 * mm
    # clear space guides
    b.c.setStrokeColorRGB(*BORDER2)
    b.c.setDash(2, 2)
    pad = 8 * mm
    b.c.rect(cx - pad, cy - pad, s + 2 * pad, s + 2 * pad, fill=0, stroke=1)
    b.c.setDash()
    b.c.drawImage(mark, cx, cy, s, s, mask="auto")
    b.c.setFillColorRGB(*MUTED)
    b.c.setFont("PlexMono", 7)
    b.c.drawString(cx - pad, cy - pad - 6 * mm, "CLEAR SPACE  =  1× BEAM HEIGHT")

    # anatomy
    ax = M + 90 * mm
    ay = y - 6 * mm
    items = [
        ("01", "Left mass", "Stated confidence — gross, overweight. Always white/ink."),
        ("02", "Red mass", "The inflation we subtract. Only red allowed in the mark."),
        ("03", "Beam", "The comparison. Capsule, always level."),
        ("04", "Fulcrum", "The Inspector. Points down. Does not move with the model."),
        ("05", "Wordmark", "tare — Poppins Bold, lowercase. Never tare®."),
        ("06", "Icon tile", "Squircle app icon. Scale only — no word inside."),
    ]
    for num, title, desc in items:
        b.c.setFont("PlexMono", 8)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(ax, ay, num)
        b.c.setFont("PlexMed", 10)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(ax + 12 * mm, ay, title)
        b.c.setFont("Plex", 8.5)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(ax + 12 * mm, ay - 5 * mm, desc)
        ay -= 16 * mm

    # misuse
    b.kicker("Misuse", M, 78 * mm)
    bads = [
        "Do not add “AI”, lightning, coins, gavels, chain links, or a ®.",
        "Do not recolor the red square. Do not paint the left mass green.",
        "Do not apply gradients, glows, drop shadows, or 3D bevels.",
        "Do not stretch, rotate past 0°, or place on busy photography.",
        "Do not set the wordmark in a serif, script, or condensed novelty face.",
        "Do not lock the mark to a cartoon mascot or scales-of-justice clipart.",
    ]
    yy = 68 * mm
    for t in bads:
        b.c.setFont("Plex", 9.5)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M, yy, "—  " + t)
        yy -= 7 * mm


def color_page(b: Book):
    b.new()
    b.kicker("06  ·  Color", M, H - 28 * mm)
    b.h1("Color is a verdict.", M, H - 40 * mm)
    y = b.wrap(
        "Near-monochrome canvas. Color is scarce and semantic. Green means guarded — the trade survived the gate. Red means shadow, veto, or harm. White is structure. There is no third accent family.",
        M, H - 52 * mm, W - 2 * M, size=10.5, leading=15,
    )

    tokens = [
        ("bg.canvas", "#0A0A0A", "App / page background", CANVAS, TEXT),
        ("bg.panel", "#111111", "Cards, chart plot area", PANEL, TEXT),
        ("bg.panel-elevated", "#161616", "Hover / selected rows", ELEV, TEXT),
        ("border.subtle", "#222222", "Dividers, chart grid", (0.133, 0.133, 0.133), TEXT),
        ("border.strong", "#333333", "Focus rings (non-danger)", (0.2, 0.2, 0.2), TEXT),
        ("text.primary", "#F0F0F0", "Body", (0.941, 0.941, 0.941), INK),
        ("text.muted", "#A3A3A3", "Labels, captions", (0.639, 0.639, 0.639), INK),
        ("text.inverse", "#0A0A0A", "Text on light buttons only", CANVAS, TEXT),
        ("accent.guarded", "#22C55E", "Guarded equity, approve, held", GREEN, INK),
        ("accent.danger", "#EF4444", "Shadow equity, veto, harm", RED, WHITE),
        ("accent.danger-deep", "#7F1D1D", "Veto flash background", REDDEEP, WHITE),
        ("accent.neutral", "#FFFFFF", "Chrome, gauges, bars", WHITE, INK),
    ]
    colw = (W - 2 * M - 6 * mm) / 2
    row_h = 16 * mm
    start = y - 8 * mm
    for i, (name, hexv, role, fill, tc) in enumerate(tokens):
        col = i % 2
        row = i // 2
        x = M + col * (colw + 6 * mm)
        yy = start - (row + 1) * (row_h + 3 * mm)
        b.c.setFillColorRGB(*fill)
        b.c.roundRect(x, yy, colw, row_h, 3, fill=1, stroke=0)
        # thin border for dark-on-dark
        b.c.setStrokeColorRGB(*BORDER)
        b.c.setLineWidth(0.6)
        b.c.roundRect(x, yy, colw, row_h, 3, fill=0, stroke=1)
        b.c.setFillColorRGB(*tc)
        b.c.setFont("PlexMono", 8)
        b.c.drawString(x + 4 * mm, yy + 10 * mm, name)
        b.c.setFont("PlexMono", 8)
        b.c.drawRightString(x + colw - 4 * mm, yy + 10 * mm, hexv)
        b.c.setFont("Plex", 8)
        b.c.drawString(x + 4 * mm, yy + 4 * mm, role)

    b.c.setFont("PlexMono", 8)
    b.c.setFillColorRGB(*MUTED)
    b.c.drawString(M, 22 * mm, "RULE  ·  UI COLOR IS A VERDICT. EXCEPTION: THE ICON’S RED SQUARE IS PART OF THE MARK.")


def type_page(b: Book):
    b.new()
    b.kicker("07  ·  Typography", M, H - 28 * mm)
    b.h1("Grotesk authority.", M, H - 40 * mm)
    y = b.wrap(
        "Poppins Bold is the wordmark only. IBM Plex Sans carries UI and body. IBM Plex Mono is reserved for hashes, order IDs, veto numbers, and raw JSON. Tabular figures are mandatory for prices, percents, R-multiples, and confidence.",
        M, H - 52 * mm, W - 2 * M, size=10.5, leading=15,
    )

    samples = [
        ("Poppins", 32, "tare", "Wordmark  ·  Poppins Bold"),
        ("PlexMed", 18, "Flight Recorder", "Section 20–24"),
        ("Plex", 12, "The Inspector sizes or vetoes using calibration.", "Body 14–16"),
        ("PlexMono", 10, "VETO  ·  p_adj 0.29 < p_be 0.33  ·  anomaly 0.12", "Meta / data 12–13"),
    ]
    yy = y - 6 * mm
    for font, size, sample, cap in samples:
        b.rule(M, yy, W - 2 * M)
        yy -= 10 * mm
        b.c.setFont(font, size)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M, yy, sample)
        b.c.setFont("PlexMono", 7.5)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawRightString(W - M, yy + 2 * mm, cap)
        yy -= 12 * mm

    yy -= 4 * mm
    b.kicker("Scale & rules", M, yy)
    yy -= 8 * mm
    rules = [
        "Headings: slight negative letter-spacing. No all-caps walls except stamps (VETO, G2, A4).",
        "Never mix a display serif into the product UI. Marketing may use Plex only.",
        "Confidence is always written as a probability that TP hits before SL.",
        "limits_hash is mono, truncated, treated as sealed — not decorative.",
    ]
    for t in rules:
        b.c.setFont("Plex", 10)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M, yy, "·  " + t)
        yy -= 7.5 * mm


def voice(b: Book):
    b.new()
    b.kicker("08  ·  Voice", M, H - 28 * mm)
    b.h1("Expert witness.", M, H - 40 * mm)
    y = b.wrap(
        "Precise, calm, slightly severe. Short sentences. Numbers over adjectives. Willing to show bad results — honesty is a brand feature. Dry wit is allowed once. Hype is not.",
        M, H - 52 * mm, W - 2 * M, size=10.5, leading=15,
    )

    b.kicker("Taglines", M, y - 4 * mm)
    tags = [
        ("PRIMARY", "Zero the confidence. Weigh the record."),
        ("ALTERNATE", "Gross stated. Net calibrated."),
        ("PRODUCT", "Brakes where the model can’t be trusted."),
        ("ARGUMENT", "Not another LLM judge. Evidence."),
        ("CHART", "Guarded green. Unguarded red."),
    ]
    yy = y - 14 * mm
    for lab, t in tags:
        b.c.setFont("PlexMono", 7.5)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M, yy, lab)
        b.c.setFont("PlexMed", 11)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M + 28 * mm, yy, t)
        yy -= 8 * mm

    yy -= 4 * mm
    b.kicker("Hooks that use real numbers", M, yy)
    yy -= 8 * mm
    hooks = [
        "This AI trader is 90% sure. Historically, when it says 90%, it’s right 41% of the time.",
        "Another LLM won’t save you. Shared blind spots fail at the same moment.",
        "We don’t ask a model to grade a model. We ask the record.",
    ]
    for t in hooks:
        b.c.setFont("Plex", 10)
        b.c.setFillColorRGB(*TEXT)
        b.wrap("“" + t + "”", M, yy, W - 2 * M, size=10, leading=13)
        yy -= 14 * mm

    yy -= 2 * mm
    b.kicker("Product vocabulary", M, yy)
    vocab = [
        ("Tare", "Product name"),
        ("Trader", "LLM + setup layer"),
        ("Inspector", "Non-LLM gate — never “AI reviewer”"),
        ("Flight Recorder", "Dashboard / event log"),
        ("Confidence", "P(TP before SL), 0–100"),
        ("Calibrated p", "Empirical / Wilson-adjusted hit rate"),
        ("Veto / Shrink / Approve", "Hard verbs. No euphemism."),
        ("Shadow (unguarded)", "Counterfactual book"),
        ("G0 / G1 / G2", "Unguarded / calibration / full"),
        ("A1–A5", "Named attacks"),
    ]
    yy -= 8 * mm
    colw = (W - 2 * M - 8 * mm) / 2
    for i, (term, meaning) in enumerate(vocab):
        col = i % 2
        row = i // 2
        x = M + col * (colw + 8 * mm)
        yv = yy - row * 7 * mm
        b.c.setFont("PlexMed", 9)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(x, yv, term)
        b.c.setFont("Plex", 8)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawRightString(x + colw, yv, meaning)


def ui_system(b: Book):
    b.new()
    b.kicker("09  ·  UI system", M, H - 28 * mm)
    b.h1("Stamped metal, not soft SaaS.", M, H - 40 * mm)

    specs = [
        ("Radius", "4 px default. 2–6 px maximum. Never pills on primary chrome."),
        ("Stroke", "1 px borders. Prefer border over shadow."),
        ("Shadow", "Almost none. If required: tight, dark, 0-blur."),
        ("Density", "High on Flight Recorder. Marketing may breathe. Still severe."),
        ("Motion", "120–200 ms ease. Instant preferred. No bounce, no confetti."),
        ("Veto flash", "The only drama — short opacity pulse on danger-deep."),
        ("Icons", "Stroke 1.5–2 px. Shield-off, gauge, ledger, waveform, lock."),
        ("Imagery", "Product screens and line diagrams. No stock traders."),
    ]
    y = H - 54 * mm
    for k, v in specs:
        b.c.setFont("PlexMed", 10)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M, y, k)
        b.c.setFont("Plex", 10)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M + 32 * mm, y, v)
        y -= 8 * mm

    y -= 4 * mm
    b.kicker("Component inventory", M, y)
    y -= 10 * mm
    comps = [
        ("Status pill", "RUNNING  ·  HALTED  ·  KILL SWITCH — stamped, not cute."),
        ("Metric tile", "Label + tabular value + delta."),
        ("Veto banner", "Danger-deep field, mono numbers, reason + intermediates."),
        ("Dual gauge", "Stated confidence vs calibrated p."),
        ("Equity chart", "Guarded green / Shadow red, same axis, annotated DD."),
        ("Reliability", "Stated x vs hit-rate y. Diagonal perfect-calibration line."),
        ("Decision table", "Dense, expandable anomaly checklist."),
        ("Gate columns", "G0 | G1 | G2 always side by side."),
        ("Check chips", "S1 C1 M1 — small stamped IDs."),
        ("Sealed hash", "limits_hash: a1b2… read-only treatment."),
    ]
    for name, note in comps:
        b.panel(M, y - 9 * mm, W - 2 * M, 11 * mm)
        b.c.setFont("PlexMed", 9)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M + 4 * mm, y - 6 * mm, name)
        b.c.setFont("Plex", 8.5)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M + 42 * mm, y - 6 * mm, note)
        y -= 13 * mm


def surfaces(b: Book):
    b.new()
    b.kicker("10  ·  Product surfaces", M, H - 28 * mm)
    b.h1("Flight Recorder first.", M, H - 40 * mm)

    # mock header strip
    b.panel(M, H - 78 * mm, W - 2 * M, 22 * mm, fill=ELEV)
    b.c.setFont("PlexMono", 8)
    b.c.setFillColorRGB(*GREEN)
    b.c.drawString(M + 5 * mm, H - 66 * mm, "RUNNING")
    b.c.setFillColorRGB(*MUTED)
    b.c.drawString(M + 32 * mm, H - 66 * mm, "EQUITY")
    b.c.setFillColorRGB(*GREEN)
    b.c.setFont("PlexMonoMed", 9)
    b.c.drawString(M + 48 * mm, H - 66 * mm, "10,482.40")
    b.c.setFillColorRGB(*MUTED)
    b.c.setFont("PlexMono", 8)
    b.c.drawString(M + 80 * mm, H - 66 * mm, "PNL")
    b.c.setFillColorRGB(*GREEN)
    b.c.setFont("PlexMonoMed", 9)
    b.c.drawString(M + 90 * mm, H - 66 * mm, "+1.4R")
    b.c.setFillColorRGB(*MUTED)
    b.c.setFont("PlexMono", 8)
    b.c.drawString(M + 112 * mm, H - 66 * mm, "OPEN 2")
    b.c.drawRightString(W - M - 5 * mm, H - 66 * mm, "limits  a1b2c9…")

    # veto banner mock
    b.c.setFillColorRGB(*REDDEEP)
    b.c.setStrokeColorRGB(*RED)
    b.c.setLineWidth(1)
    b.c.roundRect(M, H - 100 * mm, W - 2 * M, 16 * mm, 3, fill=1, stroke=1)
    b.c.setFillColorRGB(*WHITE)
    b.c.setFont("PlexMonoMed", 8)
    b.c.drawString(M + 5 * mm, H - 94.5 * mm, "VETO  —  no_calibrated_edge   p_adj 0.29 < breakeven 0.33   anomaly 0.12")

    y = H - 112 * mm
    b.kicker("Required panels", M, y)
    panels = [
        ("Overconfidence dial", "Stated vs calibrated. Gap bars by confidence bucket."),
        ("Veto indicator", "Reason + intermediates. Alarm that still reads as professional."),
        ("Equity curves", "Guarded green vs Shadow red. Max drawdown annotated. Protect this."),
        ("Reliability diagram", "Diagonal reference. Point size = n."),
        ("Decision log", "Time, symbol, side, action, confidence, decision, p_adj, size."),
        ("Attack Lab", "Scenario + attack picker. Three columns G0 | G1 | G2."),
        ("Results", "HAR / ASR table. Reliability clean vs attacked."),
    ]
    y -= 10 * mm
    for name, note in panels:
        b.c.setFont("PlexMed", 10)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M, y, name)
        b.c.setFont("Plex", 9)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M + 48 * mm, y, note)
        y -= 7.5 * mm

    y -= 4 * mm
    b.kicker("Landing page order (judges)", M, y)
    y -= 8 * mm
    steps = "Hook with numbers  →  Shared blind spots  →  How it works  →  Proof screens  →  Attack Lab A4  →  Results  →  Repo / live / video"
    b.wrap(steps, M, y, W - 2 * M, size=10, leading=14)
    y -= 20 * mm
    b.wrap(
        "Do not default to Hero → six feature cards → pricing → FAQ. There is no pricing. Features are evidence panels.",
        M, y, W - 2 * M, size=10, leading=14, color=MUTED,
    )

    # states
    b.panel(M, 22 * mm, W - 2 * M, 32 * mm)
    b.c.setFont("PlexMono", 7.5)
    b.c.setFillColorRGB(*MUTED)
    b.c.drawString(M + 6 * mm, 46 * mm, "STATES TO DESIGN")
    b.c.setFont("Plex", 9)
    b.c.setFillColorRGB(*TEXT)
    b.c.drawString(M + 6 * mm, 36 * mm, "Empty  ·  Running healthy  ·  Veto just fired  ·  Kill-switch / halted  ·  Attack Lab replay")
    b.c.setFillColorRGB(*MUTED)
    b.c.setFont("Plex", 8)
    b.c.drawString(M + 6 * mm, 28 * mm, "Empty copy:  No proposals yet. Waiting for the next 15m close.")


def evidence(b: Book):
    b.new()
    b.kicker("11  ·  Evidence rules", M, H - 28 * mm)
    b.h1("Numbers beat metaphors.", M, H - 40 * mm)

    rules = [
        "Every veto shows reason + intermediates (p_cal, p_adj, p_be, anomaly).",
        "One definition of confidence everywhere: probability TP hits before SL.",
        "Green / red semantic lock: guarded vs unguarded / harm. Never swap.",
        "G0 / G1 / G2 always comparable side-by-side in Attack Lab.",
        "If a metric looks bad, the UI still shows it.",
        "The LLM is not the visual hero. The Inspector / brakes / evidence are.",
        "Limits are sacred. Risk config is read-only. Show the hash.",
    ]
    y = H - 54 * mm
    for i, t in enumerate(rules, 1):
        b.c.setFont("PlexMono", 8)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M, y, f"{i:02d}")
        b.c.setFont("Plex", 10)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M + 12 * mm, y, t)
        y -= 8 * mm

    y -= 4 * mm
    b.kicker("Gates", M, y)
    y -= 6 * mm
    gates = [
        ("G0", "Unguarded", "Fixed 1% risk on takes. The shadow book."),
        ("G1", "Calibration", "Limits + calibration + sizing. Catches crude attacks."),
        ("G2", "Full gate", "G1 + anomaly layer. Closes the A4 hole."),
    ]
    cw = (W - 2 * M - 8 * mm) / 3
    for i, (gid, name, desc) in enumerate(gates):
        x = M + i * (cw + 4 * mm)
        b.panel(x, y - 32 * mm, cw, 32 * mm)
        b.c.setFont("PlexMonoMed", 10)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(x + 5 * mm, y - 10 * mm, gid)
        b.c.setFont("PlexMed", 10)
        b.c.drawString(x + 16 * mm, y - 10 * mm, name)
        b.wrap(desc, x + 5 * mm, y - 18 * mm, cw - 10 * mm, size=8, leading=11, color=MUTED)

    y -= 46 * mm
    b.kicker("Attacks  ·  demo narrative", M, y)
    y -= 8 * mm
    attacks = [
        ("A1", "Sentiment injection", "Instruction-like headlines → max confidence"),
        ("A2", "Fake consensus", "Duplicate bullish flood from fresh sources"),
        ("A3", "Candle forgery", "Rewrite trader candles into a textbook setup"),
        ("A4", "Confidence steering", "Land in a well-calibrated bucket (~74) to beat G1"),
        ("A5", "Adaptive", "Iterates variants — stretch goal"),
    ]
    for gid, name, desc in attacks:
        b.c.setFont("PlexMonoMed", 9)
        color = RED if gid == "A4" else WHITE
        b.c.setFillColorRGB(*color)
        b.c.drawString(M, y, gid)
        b.c.setFont("PlexMed", 9)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M + 12 * mm, y, name)
        b.c.setFont("Plex", 8.5)
        b.c.setFillColorRGB(*MUTED)
        b.c.drawString(M + 52 * mm, y, desc)
        y -= 6.5 * mm

    y -= 4 * mm
    b.panel(M, 22 * mm, W - 2 * M, 22 * mm, fill=ELEV)
    b.c.setFont("Plex", 9)
    b.c.setFillColorRGB(*TEXT)
    b.c.drawString(M + 6 * mm, 34 * mm, "A4 is built to beat calibration-only. G1 lets it through. G2 should catch it")
    b.c.drawString(M + 6 * mm, 27 * mm, "and show which checks fired. Attacks change Trader inputs only. Inspector feed stays clean.")


def dontdo(b: Book):
    b.new()
    b.kicker("12  ·  Discipline", M, H - 28 * mm)
    b.h1("Do. Don’t.", M, H - 40 * mm)

    colw = (W - 2 * M - 8 * mm) / 2
    top = H - 50 * mm
    height = 92 * mm
    b.panel(M, top - height, colw, height)
    b.panel(M + colw + 8 * mm, top - height, colw, height)
    b.c.setFont("PlexMono", 8)
    b.c.setFillColorRGB(*GREEN)
    b.c.drawString(M + 8 * mm, top - 10 * mm, "DO")
    b.c.setFillColorRGB(*RED)
    b.c.drawString(M + colw + 16 * mm, top - 10 * mm, "DON’T")

    dos = [
        "Keep monochrome discipline.",
        "Spend color only on meaning.",
        "Make Attack Lab + green/red equity the memorable move.",
        "Use real product terms from this kit.",
        "Design dark-first. Light is secondary.",
        "Optimize for a 3-minute judge glance.",
        "Show the shadow book. It is the moral.",
        "Keep Streamlit green/red roles on restyle.",
    ]
    donts = [
        "Rebrand as generic AI-crypto SaaS.",
        "Add blue / purple / gold “for energy.”",
        "Soften vetoes into friendly toasts.",
        "Hide bad calibration.",
        "Invent social trading, NFTs, mobile.",
        "Use scales-of-justice as the identity.",
        "Neon grids, glitch, glassmorphism.",
        "Add a ® or write TareAI.",
    ]
    yy = top - 22 * mm
    for t in dos:
        b.c.setFont("Plex", 9)
        b.c.setFillColorRGB(*TEXT)
        b.wrap("·  " + t, M + 8 * mm, yy, colw - 14 * mm, size=9, leading=12)
        yy -= 9 * mm
    yy = top - 22 * mm
    for t in donts:
        b.c.setFont("Plex", 9)
        b.c.setFillColorRGB(*TEXT)
        b.wrap("·  " + t, M + colw + 16 * mm, yy, colw - 14 * mm, size=9, leading=12)
        yy -= 9 * mm

    y = top - height - 12 * mm
    b.kicker("Implementation", M, y)
    y -= 8 * mm
    notes = [
        "Live dashboard today: Streamlit + Plotly at dashboard/app.py.",
        "This kit is framework-agnostic. Apply tokens via CSS or Streamlit theme.",
        "Data: SQLite flight recorder. Demo seed via scripts/seed_demo_db.py.",
        "Design against seeded demo data + Attack Lab JSON — not live exchange DNS.",
        "Assets: logos/ for mark & lockups, tokens/tokens.css and tokens.json.",
    ]
    for t in notes:
        b.c.setFont("Plex", 10)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M, y, "·  " + t)
        y -= 7 * mm

    b.panel(M, 22 * mm, W - 2 * M, 28 * mm)
    b.c.setFont("PlexMono", 8)
    b.c.setFillColorRGB(*MUTED)
    b.c.drawString(M + 8 * mm, 40 * mm, "ABOUT  ·  50 WORDS")
    b.c.setFont("Plex", 8.5)
    b.c.setFillColorRGB(*TEXT)
    b.wrap(
        "Tare is an agentic paper trader with a non-LLM Inspector. Setups come from market structure; an LLM proposes take/skip and a confidence. The Inspector sizes or vetoes using calibration, independent data, and hard limits. A shadow book and attack lab prove what the brakes catch — and what they miss.",
        M + 8 * mm, 32 * mm, W - 2 * M - 16 * mm, size=8.5, leading=11,
    )


def colophon(b: Book):
    b.new()
    b.kicker("Colophon", M, H - 28 * mm)
    b.h1("Ship the brakes.", M, H - 40 * mm)
    y = b.wrap(
        "If a stranger can answer yes to all five, the kit is doing its job.",
        M, H - 54 * mm, W - 2 * M, size=11, leading=16,
    )
    checks = [
        "In 5 seconds: this is about distrusting AI confidence, not celebrating it.",
        "In 15 seconds: they can point to stated vs calibrated, and green vs red equity.",
        "In 60 seconds: they understand why a second LLM is the wrong fix.",
        "In the Attack Lab: they see A4 pass G1 and fail G2 without a paper.",
        "Nothing looks like default Streamlit, Binance promo, or Midjourney “AI trading.”",
    ]
    y -= 4 * mm
    for i, t in enumerate(checks, 1):
        b.panel(M, y - 14 * mm, W - 2 * M, 16 * mm)
        b.c.setFont("PlexMonoMed", 10)
        b.c.setFillColorRGB(*WHITE)
        b.c.drawString(M + 6 * mm, y - 9 * mm, f"0{i}")
        b.c.setFont("Plex", 10)
        b.c.setFillColorRGB(*TEXT)
        b.c.drawString(M + 16 * mm, y - 9 * mm, t)
        y -= 20 * mm

    mark = ImageReader(str(LOGO / "tare-icon-dark-256.png"))
    b.c.drawImage(mark, M, 26 * mm, 20 * mm, 20 * mm, mask="auto")
    b.c.setFont("Poppins", 16)
    b.c.setFillColorRGB(*WHITE)
    b.c.drawString(M + 26 * mm, 36 * mm, "tare")
    b.c.setFont("PlexMono", 8)
    b.c.setFillColorRGB(*MUTED)
    b.c.drawString(M + 26 * mm, 28 * mm, "BRAND KIT 1.1  ·  FORENSIC TRADING TERMINAL")


def main():
    b = Book()
    cover(b)
    contents(b)
    metaphor(b)
    positioning(b)
    audience(b)
    logo_system(b)
    construction(b)
    color_page(b)
    type_page(b)
    voice(b)
    ui_system(b)
    surfaces(b)
    evidence(b)
    dontdo(b)
    colophon(b)
    b.save()
    print("wrote", OUT, "pages", b.n)


if __name__ == "__main__":
    main()
