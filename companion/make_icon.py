#!/usr/bin/env python3
# ============================================================================
#  ICON GENERATOR  (Pip-Boy 3000 Mk V weather app)
#  Renders the same Fallout-style holotape design the 3000 build used, but
#  writes it as the PNG registry icon referenced by pipboy/metadata.json
#  ("icon": "assets/icon.png"). The Mk V app list has no holotape .IMG icons,
#  so the 1-bpp Espruino image output was retired with the Mk V port.
#
#  Usage:  python make_icon.py [WIDTH HEIGHT [SCALE]]   (default 48 48 4)
#          WIDTH/HEIGHT are the base pixel-art grid; SCALE multiplies it up
#          for a crisp PNG (default 48x48 grid -> 192x192 PNG).
#  Output: ../pipboy/assets/icon.png  (+ an ASCII preview to stdout)
#
#  Requires Pillow:  pip install pillow
# ============================================================================

import math
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "pipboy", "assets", "icon.png")

# phosphor-green-on-black, matching the device palette in render_preview.py
BG = (4, 20, 10)
FG = (26, 255, 128)


def make_grid(w, h):
    return [[0] * w for _ in range(h)]


def px(grid, x, y, v=1):
    x, y = int(round(x)), int(round(y))
    if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
        grid[y][x] = v


def fill_rect(grid, x0, y0, x1, y1, v=1):
    for y in range(int(y0), int(y1) + 1):
        for x in range(int(x0), int(x1) + 1):
            px(grid, x, y, v)


def rect_outline(grid, x0, y0, x1, y1, v=1):
    for x in range(int(x0), int(x1) + 1):
        px(grid, x, y0, v); px(grid, x, y1, v)
    for y in range(int(y0), int(y1) + 1):
        px(grid, x0, y, v); px(grid, x1, y, v)


def circle(grid, cx, cy, r, fill=False, v=1):
    r2o, r2i = (r + 0.5) ** 2, (r - 0.5) ** 2
    for y in range(int(cy - r - 1), int(cy + r + 2)):
        for x in range(int(cx - r - 1), int(cx + r + 2)):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if (d2 <= r2o) if fill else (r2i <= d2 <= r2o):
                px(grid, x, y, v)


def line(grid, x0, y0, x1, y1, v=1):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(n + 1):
        t = i / n
        px(grid, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, v)


def chamfer_rect(grid, x0, y0, x1, y1, c, v=1):
    line(grid, x0 + c, y0, x1 - c, y0, v)
    line(grid, x1 - c, y0, x1, y0 + c, v)
    line(grid, x1, y0 + c, x1, y1 - c, v)
    line(grid, x1, y1 - c, x1 - c, y1, v)
    line(grid, x1 - c, y1, x0 + c, y1, v)
    line(grid, x0 + c, y1, x0, y1 - c, v)
    line(grid, x0, y1 - c, x0, y0 + c, v)
    line(grid, x0, y0 + c, x0 + c, y0, v)


def small_screw(grid, cx, cy, s):
    circle(grid, cx, cy, 1.55 * s)
    line(grid, cx - 1.1 * s, cy, cx + 1.1 * s, cy)


def draw_block_wx(grid, x, y, s):
    # Tiny hand-pixelled "WX" label. It survives 48px rendering better than
    # a font and keeps the label looking stamped onto the cartridge.
    w = [
        "10101",
        "10101",
        "10101",
        "11111",
        "01010",
    ]
    xglyph = [
        "10001",
        "01010",
        "00100",
        "01010",
        "10001",
    ]
    step = max(1, int(round(s)))
    for glyph, ox in ((w, 0), (xglyph, 7 * step)):
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    fill_rect(grid, x + (ox + gx * step), y + gy * step,
                              x + (ox + gx * step), y + gy * step)


def draw_weather_mark(grid, x, y, s):
    # Sun breaking through a cloud with a few rain ticks: compact enough to read
    # in the Pip-Boy app list while still saying "weather" at a glance.
    circle(grid, x + 3 * s, y + 3 * s, 2.1 * s)
    for x0, y0, x1, y1 in (
        (3, 0, 3, 1), (0, 3, 1, 3), (5, 1, 6, 0), (5, 5, 6, 6),
    ):
        line(grid, x + x0 * s, y + y0 * s, x + x1 * s, y + y1 * s)

    circle(grid, x + 8 * s, y + 6 * s, 2.0 * s)
    circle(grid, x + 11 * s, y + 5 * s, 2.4 * s)
    circle(grid, x + 14 * s, y + 7 * s, 1.8 * s)
    line(grid, x + 7 * s, y + 8 * s, x + 15 * s, y + 8 * s)
    line(grid, x + 8 * s, y + 10 * s, x + 7 * s, y + 12 * s)
    line(grid, x + 11 * s, y + 10 * s, x + 10 * s, y + 12 * s)
    line(grid, x + 14 * s, y + 10 * s, x + 13 * s, y + 12 * s)


def draw_holotape(w, h):
    g = make_grid(w, h)
    s = w / 48.0  # scale factor relative to the reference 48px design

    # Angled holotape cartridge, tuned for a 1-bpp Pip-Boy menu icon.
    bx0, by0 = 4 * s, 8 * s
    bx1, by1 = (w - 1) - 4 * s, (h - 1) - 6 * s
    chamfer_rect(g, bx0, by0, bx1, by1, 4 * s)
    chamfer_rect(g, bx0 + 2 * s, by0 + 2 * s, bx1 - 2 * s, by1 - 2 * s, 3 * s)

    # Rivets and worn cartridge teeth.
    for sx, sy in ((9, 12), (39, 12), (9, 37), (39, 37)):
        small_screw(g, sx * s, sy * s, s)
    for x in (12, 16, 20, 28, 32, 36):
        line(g, x * s, 39 * s, (x + 1) * s, 41 * s)

    # Paper label: stamped WX and an overprinted weather pictogram.
    lx0, ly0, lx1, ly1 = 10 * s, 12 * s, 38 * s, 20 * s
    rect_outline(g, lx0, ly0, lx1, ly1)
    line(g, lx0 + 1 * s, ly1 - 2 * s, lx1 - 1 * s, ly1 - 2 * s)
    draw_block_wx(g, 13 * s, 14 * s, s)
    draw_weather_mark(g, 23 * s, 12 * s, s)

    # Recessed reel bay and tape path.
    rect_outline(g, 9 * s, 22 * s, 39 * s, 35 * s)
    line(g, 15 * s, 28 * s, 33 * s, 28 * s)
    line(g, 16 * s, 31 * s, 32 * s, 31 * s)

    cy = 28.5 * s
    r = 5.2 * s
    for cx in (16 * s, 32 * s):
        circle(g, cx, cy, r)
        circle(g, cx, cy, r * 0.42)
        circle(g, cx, cy, r * 0.18, fill=True)
        for a in range(22, 360, 72):
            rad = math.radians(a)
            line(g, cx + math.cos(rad) * r * 0.45, cy + math.sin(rad) * r * 0.45,
                 cx + math.cos(rad) * r * 0.86, cy + math.sin(rad) * r * 0.86)

    # Hand-placed scuffs and signal-noise pixels for the aged terminal look.
    for x0, y0, x1, y1 in (
        (6, 17, 9, 15), (36, 9, 39, 11), (6, 32, 8, 35),
        (28, 36, 31, 34), (40, 25, 42, 23), (18, 10, 21, 9),
    ):
        line(g, x0 * s, y0 * s, x1 * s, y1 * s, 1)
    for x, y in ((12, 24), (20, 23), (26, 25), (35, 24),
                 (14, 35), (24, 37), (34, 34), (42, 16)):
        px(g, x * s, y * s)

    return g


def save_png(grid, scale, path):
    try:
        from PIL import Image
    except ImportError:
        sys.exit("make_icon.py needs Pillow for PNG output: "
                 "python -m pip install pillow")
    w, h = len(grid[0]), len(grid)
    img = Image.new("RGB", (w, h), BG)
    px = img.load()
    for y in range(h):
        for x in range(w):
            if grid[y][x]:
                px[x, y] = FG
    img = img.resize((w * scale, h * scale), Image.NEAREST)
    img.save(path)
    return img.size


def preview(grid):
    for row in grid:
        print("".join("##" if c else "  " for c in row))


def main():
    w = h = 48
    scale = 4
    if len(sys.argv) >= 3:
        w, h = int(sys.argv[1]), int(sys.argv[2])
    if len(sys.argv) >= 4:
        scale = int(sys.argv[3])
    grid = draw_holotape(w, h)
    preview(grid)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pw, ph = save_png(grid, scale, OUT)
    print("\nwrote %s  (%dx%d grid -> %dx%d PNG, %d bytes)"
          % (os.path.normpath(OUT), w, h, pw, ph, os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
