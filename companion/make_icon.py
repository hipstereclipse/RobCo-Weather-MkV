#!/usr/bin/env python3
# ============================================================================
#  HOLOTAPE ICON GENERATOR  (Pip-Boy 3000 weather app)
#  Renders a Fallout-style holotape and writes it as an Espruino 1-bpp image
#  file (the format referenced by APPINFO/<APP>.info "icon").
#
#  Espruino image format:  byte0=width, byte1=height, byte2=bpp,
#  then pixel bits packed MSB-first, continuous (no per-row padding).
#
#  Usage:  python make_icon.py [WIDTH HEIGHT]      (default 48 48)
#  Output: ../pipboy/APPINFO/WEATHER.IMG  (+ an ASCII preview to stdout)
#
#  If your firmware expects a different icon size, just pass new dimensions.
# ============================================================================

import math
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "pipboy", "APPINFO", "WEATHER.IMG")


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


def draw_holotape(w, h):
    g = make_grid(w, h)
    s = w / 48.0  # scale factor relative to the reference 48px design

    # cartridge body (rounded-ish rectangle: outline + clipped corners)
    bx0, by0, bx1, by1 = 4 * s, 9 * s, (w - 1) - 4 * s, (h - 1) - 7 * s
    rect_outline(g, bx0, by0, bx1, by1)
    rect_outline(g, bx0 + 1, by0 + 1, bx1 - 1, by1 - 1)
    # knock out the four corners for a rounded look
    for (cx, cy) in [(bx0, by0), (bx1, by0), (bx0, by1), (bx1, by1)]:
        px(g, cx, cy, 0)

    # label window near the top
    lx0, lx1 = bx0 + 6 * s, bx1 - 6 * s
    rect_outline(g, lx0, by0 + 3 * s, lx1, by0 + 9 * s)

    # two tape reels
    cy = (by0 + by1) / 2 + 2 * s
    r = 6 * s
    for cx in (w * 0.34, w * 0.66):
        circle(g, cx, cy, r)            # rim
        circle(g, cx, cy, r * 0.32, fill=True)   # hub
        for a in range(0, 360, 45):     # spokes
            rad = math.radians(a)
            line(g, cx + math.cos(rad) * r * 0.35, cy + math.sin(rad) * r * 0.35,
                 cx + math.cos(rad) * r * 0.85, cy + math.sin(rad) * r * 0.85)

    return g


def pack(grid):
    w, h = len(grid[0]), len(grid)
    bits = []
    for row in grid:
        bits.extend(row)
    out = bytearray([w & 0xFF, h & 0xFF, 1])  # width, height, bpp=1
    acc = 0
    nbits = 0
    for b in bits:
        acc = (acc << 1) | (b & 1)
        nbits += 1
        if nbits == 8:
            out.append(acc)
            acc, nbits = 0, 0
    if nbits:
        out.append(acc << (8 - nbits))
    return bytes(out)


def preview(grid):
    for row in grid:
        print("".join("##" if c else "  " for c in row))


def main():
    w = h = 48
    if len(sys.argv) >= 3:
        w, h = int(sys.argv[1]), int(sys.argv[2])
    grid = draw_holotape(w, h)
    preview(grid)
    data = pack(grid)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(data)
    print("\nwrote %s  (%dx%d, 1bpp, %d bytes)"
          % (os.path.normpath(OUT), w, h, len(data)))


if __name__ == "__main__":
    main()
