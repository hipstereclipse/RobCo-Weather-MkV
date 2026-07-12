#!/usr/bin/env python3
# ============================================================================
#  PREVIEW RENDERER
#  Renders PNG mock-ups of how the Pip-Boy Weather app looks on-device, plus
#  the companion GUI, so you can see it before installing anything.
#
#  It re-implements the WEATHER.js layout against the same WEATHER.JSON, in
#  the Pip-Boy green-phosphor aesthetic (scanlines + bezel). It is a visual
#  approximation - exact fonts/metrics on real hardware will differ.
#
#  Run:  python render_preview.py [path/to/WEATHER.JSON]
#  Out:  ../previews/*.png
#
#  Requires Pillow:  pip install pillow
# ============================================================================

import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "previews")
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "sample", "WEATHER.JSON")

# logical screen - the Pip-Boy 3000 Mk V draws LANDSCAPE 480x320, but the case
# shroud hides x < 38 and x > 438 of the surface; the preview masks those bands
# so anything drawn under the shroud is obviously clipped
LW, LH = 480, 320
VIS_X0, VIS_X1 = 38, 438  # visible window (mirrors WEATHER.js - keep in sync)
S = 2  # supersample factor
CORN = 56      # horizontal inset for the top/bottom rows so the case opening
               # does not clip the header/footer text
               # (mirrors CORN in WEATHER.js - keep the two in sync)
TOP = 10
FOOT = 26
R_SCREEN = 8   # corner radius of the case opening in logical px

BG    = (1, 16, 7)
FG    = (26, 255, 128)
HOT   = (166, 255, 205)
DIM   = (39, 121, 71)
AMBER = (255, 182, 66)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
]
FONT_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/consolab.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]


def _find(cands):
    for c in cands:
        if os.path.exists(c):
            return c
    return None


_FONT = _find(FONT_CANDIDATES)
_FONTB = _find(FONT_BOLD_CANDIDATES) or _FONT
_font_cache = {}


def font(size, bold=False):
    key = (int(size), bold)
    if key not in _font_cache:
        path = _FONTB if bold else _FONT
        if path:
            _font_cache[key] = ImageFont.truetype(path, int(size))
        else:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


# font sizes (logical px), mirroring the app's font tiers
F_BIG, F_HEAD, F_SMALL, F_TINY = 56, 24, 16, 12


class Screen:
    """Tiny Graphics-like wrapper so the port reads like the JS app."""
    def __init__(self):
        self.img = Image.new("RGB", (LW * S, LH * S), BG)
        self.d = ImageDraw.Draw(self.img)

    def line(self, x0, y0, x1, y1, fill=FG, w=1):
        self.d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill, width=max(1, int(w * S)))

    def rect(self, x0, y0, x1, y1, fill=FG, w=1):
        self.d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], outline=fill, width=max(1, int(w * S)))

    def frect(self, x0, y0, x1, y1, fill=FG):
        self.d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill)

    def circle(self, cx, cy, r, fill=FG, w=1):
        self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S],
                       outline=fill, width=max(1, int(w * S)))

    def disc(self, cx, cy, r, fill=FG):
        self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill)

    def poly(self, pts, fill=FG):
        self.d.polygon([p * S for p in pts], fill=fill)

    def text(self, txt, x, y, size, ax=-1, ay=-1, fill=FG, bold=False):
        anchor = ({-1: "l", 0: "m", 1: "r"}[ax]) + ({-1: "a", 0: "m", 1: "d"}[ay])
        self.d.text((x * S, y * S), str(txt), font=font(size * S, bold),
                    fill=fill, anchor=anchor)

    def strwidth(self, txt, size, bold=False):
        b = self.d.textbbox((0, 0), str(txt), font=font(size * S, bold))
        return (b[2] - b[0]) / S


# --------------------------------------------------------------- weather icons
def draw_icon(g, code, cx, cy, r, is_day=True):
    def thick(x0, y0, x1, y1):
        g.line(x0, y0, x1, y1, w=2)

    def sun(cx, cy, r):
        d, s, q = r + 10, r + 3, r / 2
        g.circle(cx, cy, r, w=2)
        g.circle(cx, cy, r - 3)
        thick(cx - d, cy, cx - s, cy)
        thick(cx + s, cy, cx + d, cy)
        thick(cx, cy - d, cx, cy - s)
        thick(cx, cy + s, cx, cy + d)
        thick(cx - q - 5, cy - q - 5, cx - q, cy - q)
        thick(cx + q, cy - q, cx + q + 5, cy - q - 5)
        thick(cx - q - 5, cy + q + 5, cx - q, cy + q)
        thick(cx + q, cy + q, cx + q + 5, cy + q + 5)

    def cloud(cx, cy, r):
        g.circle(cx - r / 2, cy + 2, r / 2, w=2)
        g.circle(cx + r / 2, cy + 2, r / 2, w=2)
        g.circle(cx, cy - 4, r / 2 + 3, w=2)
        thick(cx - r, cy + r / 2 + 2, cx + r, cy + r / 2 + 2)

    def rain(cx, cy, r):
        cloud(cx, cy, r)
        for i in (-1, 0, 1):
            x = cx + i * 8
            thick(x, cy + r, x - 4, cy + r + 12)

    def snow(cx, cy, r):
        cloud(cx, cy, r)
        for i in (-1, 0, 1):
            x, y = cx + i * 8, cy + r + 6
            thick(x - 4, y, x + 4, y)
            thick(x, y - 4, x, y + 4)

    def storm(cx, cy, r):
        cloud(cx, cy, r)
        thick(cx, cy + r - 3, cx - 6, cy + r + 9)
        thick(cx - 6, cy + r + 9, cx + 2, cy + r + 5)
        thick(cx + 2, cy + r + 5, cx - 1, cy + r + 15)

    def fog(cx, cy, r):
        for i in range(3):
            y = cy + r + i * 6
            thick(cx - r, y, cx + r, y)

    def partly(cx, cy, r):
        sun(cx - r / 2, cy - r / 2, max(5, r / 2))
        cloud(cx + 4, cy + 3, r)

    if code == 0:
        sun(cx, cy, r)
    elif code in (1, 2):
        partly(cx, cy, r)
    elif code == 3:
        cloud(cx, cy, r)
    elif code in (45, 48):
        fog(cx, cy, r)
    elif 51 <= code <= 67 or 80 <= code <= 82:
        rain(cx, cy, r)
    elif 71 <= code <= 77 or 85 <= code <= 86:
        snow(cx, cy, r)
    elif code >= 95:
        storm(cx, cy, r)
    else:
        cloud(cx, cy, r)


# --------------------------------------------------------------- app chrome
def hr(g, y):
    g.line(40, y, 436, y)


def pad_hex(n):
    return "0x%04X" % max(0, int(n))


def kp_label(sp, i):
    labels = (sp or {}).get("kpt") or []
    if 0 <= i < len(labels) and labels[i]:
        s = str(labels[i])
        m = re.match(r"^(\d\d/\d\d)[ T](\d\d)(?::\d\d)?Z?$", s, re.I)
        if m:
            h = int(m.group(2))
            return "%s %d %s UTC" % (
                m.group(1), h % 12 or 12, "PM" if h >= 12 else "AM")
        return re.sub(r"Z$", " UTC", s, flags=re.I).upper()
    return "T+%dH" % (i * 3)


def box(g, x0, y0, x1, y1, label):
    g.rect(x0, y0, x1, y1)
    if label:
        g.frect(x0 + 7, y0 - 1, x0 + 19 + len(label) * 7, y0 + 8, fill=BG)
        g.text(" " + label + " ", x0 + 9, y0 - 1, F_TINY, fill=FG)


def gauge(g, x, y, w, value, max_value):
    g.rect(x, y, x + w, y + 6, fill=DIM)
    try:
        fill = max(0, min(w - 2, round((w - 2) * float(value) / max_value)))
    except (TypeError, ValueError, ZeroDivisionError):
        return
    if fill > 0:
        g.frect(x + 1, y + 1, x + fill, y + 5, fill=FG)


def item_count(data, loc, view):
    if view == "current":
        return 4
    if view == "forecast":
        return max(1, min(5, len(loc.get("daily") or [])))
    return max(1, min(24, len((data.get("space") or {}).get("kpf") or [])))


def header(g, data, loc_i, view="current", item_mode=False, item_i=0, stale=False, age="27H"):
    n = len(data["locations"])
    if stale:
        g.text("! CACHE %s OLD - SYNC" % age, CORN, TOP, F_TINY, fill=HOT)
    else:
        g.text("ROBCO INDUSTRIES (TM) TERMLINK", CORN, TOP, F_TINY)
    if item_mode:
        n = item_count(data, data["locations"][loc_i], view)
        g.text("ITEM [%d/%d]" % (item_i + 1, n), LW - CORN, TOP, F_TINY, ax=1)
    else:
        g.text("SITE [%d/%d]" % (loc_i + 1, n), LW - CORN, TOP, F_TINY, ax=1)
    hr(g, 24)


def footer(g, data, item_mode=False, stale=False):
    y = LH - FOOT
    hr(g, y - 6)
    label = "WHEEL:ITEM PUSH:SITE K2:VIEW" if item_mode else "WHEEL:SITE PUSH:ITEM K2:VIEW"
    g.text(label, CORN, y, F_TINY)
    stamp = data.get("generated", "")[5:]
    g.text(("! " if stale else "UPD ") + stamp, LW - CORN, y, F_TINY,
           ax=1, fill=HOT if stale else FG)


def title(g, loc, loc_i=0):
    g.text(loc.get("name", "?").upper(), CORN, 32, F_SMALL, ax=-1, bold=True)
    if loc.get("region"):
        g.text(loc["region"].upper(), CORN, 51, F_TINY, ax=-1, fill=DIM)
    g.text("SITE " + pad_hex(0xA100 + loc_i * 0x23), LW - CORN, 51, F_TINY,
           ax=1, fill=DIM)


TABS = ["ATMOS", "5-DAY", "SOLAR"]


def tabs(g, active):
    y = 66
    bw = (LW - 84) / len(TABS)
    for i, t in enumerate(TABS):
        x0 = 40 + i * bw
        col = HOT if i == active else DIM
        if i == active:
            g.rect(x0 + 3, y, x0 + bw - 3, y + 15, fill=HOT)
        g.text(("> " if i == active else "  ") + t, x0 + bw / 2, y + 8,
               F_TINY, ax=0, ay=0, fill=col)
    hr(g, 85)


def stat(g, label, value, x, y, w):
    g.text(label, x + w / 2, y, F_TINY, ax=0, fill=DIM)
    g.text(value, x + w / 2, y + 12, F_SMALL, ax=0)


def stat_row(g, label, value, xL, xR, y):
    g.text(label, xL, y, F_TINY, ax=-1, ay=0, fill=DIM)
    g.text(value, xR, y, F_SMALL, ax=1, ay=0)


def metric(g, label, value, x, y):
    g.text(label, x, y, F_TINY, ax=0, fill=DIM)
    g.text(value, x, y + 17, F_SMALL, ax=0, ay=0)


def flare_level(cls):
    return {"X": 3, "M": 2, "C": 1}.get(str(cls)[:1].upper(), 0) if cls else 0


def scale_num(s):
    m = re.search(r"\d+", str(s or ""))
    return int(m.group()) if m else 0


def solar_active(sp):
    return sp and (flare_level(sp.get("flare")) >= 2 or scale_num(sp.get("g_scale")) >= 1
                   or scale_num(sp.get("s_scale")) >= 1 or scale_num(sp.get("r_scale")) >= 1)


def solar_line(data, loc):
    sp = data.get("space")
    if not sp:
        return None
    if solar_active(sp):
        s = "SOLAR " + (sp.get("flare") or "ACTIVE")
        if scale_num(sp.get("g_scale")) >= 1:
            s += " / " + sp["g_scale"]
        elif scale_num(sp.get("s_scale")) >= 1:
            s += " / " + sp["s_scale"]
    else:
        s = "SOLAR QUIET"
    au = loc.get("aurora")
    if au and au.get("chance") and au["chance"] != "UNLIKELY":
        s += "   AURORA " + au["chance"]
    return s


# --------------------------------------------------------------- views
def view_current(g, data, loc, item_i=0):
    c = loc.get("current", {})
    unit = data.get("units", {}).get("temp", "F")
    d0 = (loc.get("daily") or [{}])[0]
    box(g, 40, 96, 232, 246, "LOCAL ATMOS")
    box(g, 240, 96, 436, 246, "INSTRUMENTS")

    draw_icon(g, c.get("code", 0), 78, 136, 24, c.get("is_day", 1))
    temp = str(round(c.get("temp", 0)))
    g.text(temp, 118, 144, F_BIG, ax=-1, ay=0, bold=True)
    g.circle(200 + 5, 124 + 4, 4)
    g.text(unit, 200 + 14, 124 + 6, F_TINY, ax=-1, ay=0)

    g.text("> CONDITION", 50, 181, F_TINY, fill=DIM)
    if c.get("time"):
        g.text("OBS " + c["time"][5:16], 222, 181, F_TINY, ax=1, fill=DIM)
    g.text(c.get("desc", "--").upper()[:15], 50, 199, F_SMALL)
    metric(g, "HI", str(round(d0.get("hi", 0))), 72, 216)
    metric(g, "LO", str(round(d0.get("lo", 0))), 126, 216)
    metric(g, "RAIN", "%s%%" % round(d0.get("pop", 0)), 188, 216)

    xL, xR = 252, 424
    rows = [(104, 127), (134, 157), (164, 193), (202, 233)]
    for i, (y0, y1) in enumerate(rows):
        if i == item_i:
            g.rect(246, y0, 430, y1, fill=HOT)
    stat_row(g, "FEELS", str(round(c.get("feels", 0))) + unit, xL, xR, 116)
    stat_row(g, "WIND", str(round(c.get("wind", 0))) + " " + c.get("dir", ""), xL, xR, 146)
    stat_row(g, "HUMID", str(round(c.get("humidity", 0))) + "%", xL, xR, 176)
    gauge(g, xL, 188, 172, c.get("humidity"), 100)
    stat_row(g, "RAD UV", str(round(c.get("uv", 0))), xL, xR, 214)
    gauge(g, xL, 226, 172, c.get("uv"), 11)

    if item_i == 0:
        detail = "FEELS %s%s  ACTUAL %s%s" % (round(c.get("feels", 0)), unit, round(c.get("temp", 0)), unit)
    elif item_i == 1:
        detail = "WIND %s %s %s" % (round(c.get("wind", 0)), c.get("dir", ""), data.get("units", {}).get("wind", ""))
    elif item_i == 2:
        detail = "HUMID %s%%  RAIN %s%%" % (round(c.get("humidity", 0)), round(d0.get("pop", 0)))
    else:
        detail = "UV %s  %s" % (round(c.get("uv", 0)), solar_line(data, loc) or "SOLAR QUIET")
    box(g, 40, 250, 436, 282, "SELECTED TELEMETRY")
    g.text(detail[:31], 50, 266, F_SMALL, ay=0,
           fill=HOT if item_i == 3 and solar_active(data.get("space")) else FG)


def view_forecast(g, data, loc, item_i=0):
    days = loc.get("daily", [])[:5]
    if days:
        item_i = min(item_i, len(days) - 1)
    box(g, 40, 96, 436, 222, "FORECAST BUFFER")
    g.text("5 ENTRIES  //  SELECT DAY WITH WHEEL", 52, 111, F_TINY, fill=DIM)
    colW = (LW - 84) / 5
    for i, dday in enumerate(days):
        cx = 40 + colW * i + colW / 2
        if i > 0:
            g.line(40 + colW * i, 126, 40 + colW * i, 216, fill=DIM)
        if i == item_i:
            g.rect(40 + colW * i + 4, 122, 40 + colW * (i + 1) - 4, 216, fill=HOT)
        g.text(dday.get("d", "?"), cx, 134, F_SMALL, ax=0)
        draw_icon(g, dday.get("code", 0), cx, 169, 10, True)
        g.text(dday.get("desc", "--").upper()[:9], cx, 192, F_TINY, ax=0, fill=DIM)
        g.text("%s/%s %s%%" % (round(dday.get("hi", 0)), round(dday.get("lo", 0)),
               round(dday.get("pop", 0))), cx, 207, F_TINY, ax=0)
    dday = days[item_i] if days else {}
    box(g, 40, 232, 436, 282, "ENTRY DETAIL")
    g.text(("%s  %s" % (dday.get("date", dday.get("d", "D%d" % (item_i + 1))),
           dday.get("desc", "--").upper()))[:31], 50, 249, F_SMALL)
    g.text("HI/LO %s/%s" % (round(dday.get("hi", 0)), round(dday.get("lo", 0))),
           50, 272, F_SMALL, ax=-1, ay=0)
    g.text("RAIN %s%%" % round(dday.get("pop", 0)), 426, 272, F_SMALL, ax=1, ay=0)


def kp_graph(g, sp, loc, x0, y0, x1, y1, item_i=0):
    kpf = sp.get("kpf", [])
    base, span = y1, y1 - (y0 + 5)

    def ky(kp):
        return base - (max(0, min(9, kp)) / 9) * span

    g.text("KP", x0 - 18, y0 - 8, F_TINY)
    g.line(x0, y0, x0, y1)
    g.line(x0, y1, x1, y1)
    g.text("0", x0 - 4, base, F_TINY, ax=1, ay=0, fill=DIM)
    for v in (3, 6, 9):
        g.text(str(v), x0 - 2, ky(v), F_TINY, ax=1, ay=0, fill=DIM)
        g.line(x0 - 2, ky(v), x0 + 2, ky(v), fill=DIM)
    needed = (loc.get("aurora") or {}).get("needed", 99)
    n = len(kpf) or 1
    bw = (x1 - x0) / n
    for i, kp in enumerate(kpf):
        bx0, bx1 = x0 + i * bw + 1, x0 + (i + 1) * bw - 1
        by = ky(kp)
        if kp >= needed or i == item_i:
            g.frect(bx0, by, bx1, base - 1, fill=HOT if i == item_i else FG)
        else:
            g.rect(bx0, by, bx1, base - 1, fill=DIM)
        if i == item_i:
            g.rect(bx0 - 3, y0 - 2, bx1 + 3, base + 2, fill=HOT, w=2)
            g.rect(bx0 - 5, y0 - 4, bx1 + 5, base + 4, fill=HOT)
    if needed <= 9:
        ty = ky(needed)
        dx = x0
        while dx < x1:
            g.line(dx, ty, dx + 3, ty, fill=HOT)
            dx += 6
    for tk in sp.get("kpf_ticks", []):
        tx = x0 + tk["i"] * bw
        g.line(tx, base, tx, base + 3)
        g.text(str(tk.get("d", ""))[:5], tx, base + 4, F_TINY, ax=0)


def view_space(g, data, loc, item_i=0):
    sp = data.get("space")
    if not sp:
        g.text("NO SPACE WX DATA", 238, LH / 2, F_SMALL, ax=0, ay=0)
        return
    kpf = sp.get("kpf") or []
    if kpf:
        item_i = min(item_i, len(kpf) - 1)
    box(g, 40, 96, 232, 232, "ROBCO SOLAR RELAY")
    box(g, 240, 96, 436, 232, "KP BUFFER")
    stat_row(g, "FLARE", sp.get("flare", "NONE"), 52, 220, 118)
    stat_row(g, "R/S/G", "%s %s %s" % (sp.get("r_scale", "R0"),
             sp.get("s_scale", "S0"), sp.get("g_scale", "G0")), 52, 220, 152)
    stat_row(g, "KP NOW/PK", "%s / %s" % (sp.get("kp_now", "--"),
             sp.get("kp_peak", "--")), 52, 220, 186)
    g.text((sp.get("g_text") or "FIELD QUIET").upper()[:25], 52, 216, F_TINY, fill=DIM)
    g.text("KP FORECAST UTC", 252, 114, F_TINY, fill=DIM)
    kp_graph(g, sp, loc, 274, 132, 424, 210, item_i)

    box(g, 40, 242, 436, 282, "AURORA ESTIMATE")
    au = loc.get("aurora", {})
    g.text("AURORA @ " + loc.get("name", "").upper()[:18], 50, 258, F_TINY,
           ax=-1, ay=0)
    chance = au.get("chance", "UNKNOWN")
    g.text(chance, 426, 258, F_HEAD, ax=1, ay=0, bold=True,
           fill=HOT if chance in ("LIKELY", "POSSIBLE") else FG)
    kv = kpf[item_i] if kpf else "--"
    g.text(("%s  KP %s" % (kp_label(sp, item_i), kv))[:15],
           50, 276, F_SMALL, fill=FG, ay=0)
    g.text("NEED %s PK %s" % (au.get("needed", "?"), au.get("maxkp", "?")),
           426, 276, F_SMALL, fill=FG, ax=1, ay=0)


# --------------------------------------------------------------- compositing
def scanlines(img):
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(0, img.size[1], 3):
        d.line([(0, y), (img.size[0], y)], fill=(0, 0, 0, 60))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def vignette(img):
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    w, h = img.size
    steps = 32
    for i in range(steps):
        alpha = int(((steps - i) / steps) ** 2 * 90)
        d.rectangle([i, i, w - 1 - i, h - 1 - i], outline=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def crt_effect(img):
    glow = img.filter(ImageFilter.GaussianBlur(2.2))
    img = Image.blend(img, glow, 0.18)
    img = scanlines(img)
    return vignette(img)


def bezel(screen_img, caption):
    m = 26 * S
    top = 50 * S
    W = screen_img.size[0] + m * 2
    H = screen_img.size[1] + top + m
    out = Image.new("RGB", (W, H), (8, 12, 9))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([6, 6, W - 6, H - 6], radius=18 * S, outline=DIM, width=2 * S)
    d.text((m, 18 * S), caption, font=font(F_HEAD * S, True), fill=FG)
    d.text((W - m, 24 * S), "PIP-BOY 3000 MK V", font=font(F_TINY * S, False),
           fill=DIM, anchor="ra")
    # inner screen recess around the visible window only
    d.rectangle([m + (VIS_X0 - 4) * S, top - 4 * S,
                 m + (VIS_X1 + 4) * S, H - m + 4 * S], outline=DIM, width=S)
    # mask everything outside the Mk V case opening (x in [VIS_X0, VIS_X1]);
    # hidden pixels fall back to the bezel so clipped content is obvious
    mask = Image.new("L", screen_img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [VIS_X0 * S, 0, VIS_X1 * S - 1, screen_img.size[1] - 1],
        radius=R_SCREEN * S, fill=255)
    out.paste(screen_img, (m, top), mask)
    return out


def render_device(data, loc_i, view, caption, stale=False, item_mode=False, item_i=0):
    g = Screen()
    loc = data["locations"][loc_i]
    header(g, data, loc_i, view=view, item_mode=item_mode, item_i=item_i, stale=stale)
    title(g, loc, loc_i)
    tabs(g, {"current": 0, "forecast": 1, "space": 2}[view])
    {"current": view_current, "forecast": view_forecast, "space": view_space}[view](g, data, loc, item_i)
    footer(g, data, item_mode=item_mode, stale=stale)
    img = crt_effect(g.img)
    return bezel(img, caption)


# --------------------------------------------------------------- GUI mockup
def render_gui():
    s = 2
    W, H = 980 * s, 720 * s
    BGc, PANEL, EDGE, GREEN, DIMc, AMB, SELc = ((6, 18, 10), (11, 32, 20), (29, 92, 51),
        (70, 255, 120), (47, 157, 84), (255, 182, 66), (16, 59, 34))
    img = Image.new("RGB", (W, H), BGc)
    d = ImageDraw.Draw(img)
    w = W / s

    def t(txt, x, y, size, fill=GREEN, bold=False, anchor="la"):
        d.text((x * s, y * s), txt, font=font(size * s, bold), fill=fill, anchor=anchor)

    def panel(x0, y0, x1, y1, label):
        d.rectangle([x0 * s, y0 * s, x1 * s, y1 * s], outline=EDGE, width=s)
        d.rectangle([(x0 + 6) * s, (y0 - 7) * s, (x0 + 18 + len(label) * 7) * s, (y0 + 4) * s], fill=BGc)
        t(" " + label + " ", x0 + 8, y0 - 11, 9, fill=DIMc)

    def button(x0, y0, x1, y1, label, fill=GREEN, bold=True, selected=False):
        d.rectangle([x0 * s, y0 * s, x1 * s, y1 * s],
                    fill=SELc if selected else PANEL, outline=EDGE, width=s)
        t(label, (x0 + x1) / 2, (y0 + y1) / 2 + 1, 10, fill=fill,
          bold=bold, anchor="mm")

    # header
    t("ROBCO WEATHER RELAY", 14, 12, 22, bold=True)
    t("ROBCO INDUSTRIES (TM) TERMLINK PROTOCOL", w - 14, 24, 9,
      fill=DIMc, anchor="ra")
    d.rectangle([14 * s, 46 * s, (w - 14) * s, 48 * s], fill=EDGE)

    # notebook tabs
    d.rectangle([14 * s, 58 * s, (w - 14) * s, 88 * s], outline=EDGE, width=s)
    button(24, 62, 180, 86, "RELAY CONTROL", selected=True)
    button(184, 62, 346, 86, "DEVICE PREVIEW", fill=DIMc, selected=False)

    # saved locations panel
    panel(14, 112, 472, 350, "SAVED LOCATIONS")
    locs = ["GOODSPRINGS            MOJAVE WASTELAND",
            "CAPITAL WASTELAND      WASHINGTON D.C.",
            "THE COMMONWEALTH       BOSTON, MASS.",
            "NORTHERN OUTPOST       ALASKA TERRITORY"]
    for i, l in enumerate(locs):
        yy = 126 + i * 23
        if i == 3:
            d.rectangle([18 * s, (yy - 2) * s, 466 * s, (yy + 16) * s], fill=SELc)
        t(" " + l, 20, yy, 11, fill=(AMB if i == 3 else GREEN))
    t("4 SAVED - LIKELY OK FOR DEVICE CACHE", 20, 296, 9, fill=DIMc)
    button(20, 318, 58, 338, "UP")
    button(66, 318, 104, 338, "DN")
    button(282, 318, 398, 338, "RESET DEFAULTS")
    button(408, 318, 462, 338, "REMOVE", fill=AMB)

    # add location panel
    panel(494, 112, 966, 350, "ADD LOCATION  (search anywhere on Earth)")
    d.rectangle([502 * s, 126 * s, 858 * s, 150 * s], outline=EDGE, width=s)
    t("goodsprings", 510, 131, 11)
    button(870, 126, 958, 150, "SEARCH")
    results = ["Goodsprings, Nevada, United States",
               "Goodsprings, Alabama, United States",
               "Springs, Gauteng, South Africa"]
    for i, r in enumerate(results):
        yy = 172 + i * 22
        if i == 0:
            d.rectangle([502 * s, (yy - 2) * s, 958 * s, (yy + 16) * s], fill=SELc)
        t("  " + r, 504, yy, 10, fill=(GREEN if i == 0 else DIMc))
    button(826, 318, 958, 338, "ADD SELECTED <-")

    # settings
    panel(14, 376, 966, 506, "SETTINGS")
    t("UNITS", 24, 394, 9, fill=DIMc)
    t("(X) DEG F   ( ) DEG C", 70, 392, 11)
    t("SD CARD ROOT", 256, 394, 9, fill=DIMc)
    d.rectangle([356 * s, 390 * s, 610 * s, 414 * s], outline=EDGE, width=s)
    t("E:\\", 364, 395, 11)
    button(622, 390, 724, 414, "BROWSE...")
    t("APP SOURCE", 24, 428, 9, fill=DIMc)
    t("( ) LATEST (GIT)   (X) LOCAL FOLDER", 118, 426, 10)
    d.rectangle([428 * s, 422 * s, 800 * s, 446 * s], outline=EDGE, width=s)
    t("C:\\Users\\Eclipse\\.claude\\Workspaces\\Weather MkV", 436, 427, 9)
    button(814, 422, 934, 446, "BROWSE...")
    t("APP FILES  <-  C:\\Users\\Eclipse\\.claude\\Workspaces\\Weather MkV  (bundled)",
      24, 462, 9, fill=DIMc)
    t("OUTPUT  ->  E:\\USER\\WEATHER.JSON", 24, 480, 9, fill=DIMc)
    t("SYNC INCLUDES: OPEN-METEO WEATHER + NOAA SWPC SPACE WX", 24, 494, 9, fill=DIMc)

    # shared action bar
    labels = [("FETCH DATA ONLY", AMB), ("INSTALL SD + DATA", GREEN),
              ("USB DATA ONLY", GREEN), ("USB INSTALL + DATA", GREEN)]
    x0, gap = 14, 8
    bw = (w - 28 - gap * 3) / 4
    for i, (label, col) in enumerate(labels):
        bx = x0 + i * (bw + gap)
        d.rectangle([bx * s, 528 * s, (bx + bw) * s, 566 * s],
                    outline=AMB if i == 0 else EDGE, width=2 * s if i == 0 else s)
        t(label, bx + bw / 2, 548, 13, fill=col, bold=True, anchor="mm")

    # terminal log
    panel(14, 590, 966, 704, "TERMINAL")
    log = ["ROBCO WEATHER RELAY ONLINE.",
           "Sync includes Open-Meteo weather + NOAA SWPC space weather.",
           "DEVICE PREVIEW tab mirrors the on-device screen.",
           "==== DEVICE INSTALL / UPDATE ====",
           "  > installing 2 app file(s) ...",
           "DEVICE UPDATE COMPLETE - app files plus 4 location(s) cached."]
    for i, line in enumerate(log):
        t(line, 22, 604 + i * 15, 9, fill=GREEN)

    return scanlines(img)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    # find a high-latitude location for the aurora demo, else use 0
    north = next((i for i, l in enumerate(data["locations"])
                  if (l.get("aurora") or {}).get("chance") == "LIKELY"), 0)

    jobs = [
        (render_device(data, 0, "current", "CURRENT CONDITIONS"), "01_current.png"),
        (render_device(data, 0, "forecast", "5-DAY FORECAST", item_mode=True, item_i=3), "02_forecast.png"),
        (render_device(data, north, "space", "SPACE WEATHER", item_mode=True, item_i=6), "03_space_weather.png"),
        (render_device(data, north, "current", "CURRENT + SOLAR TIE-IN"), "04_current_solar.png"),
        (render_device(data, 0, "current", "STALE-DATA WARNING", stale=True), "05_stale_warning.png"),
        (render_gui(), "06_companion_gui.png"),
    ]
    for img, name in jobs:
        path = os.path.join(OUT_DIR, name)
        img.save(path)
        print("wrote", os.path.normpath(path))


if __name__ == "__main__":
    main()
