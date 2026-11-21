#!/usr/bin/env python3
"""Print-ready tags for the tag ceiling test (drone/tag_climb.py), one letter page each, exact size.

    pip install pillow
    git clone --depth 1 https://github.com/AprilRobotics/apriltag-imgs   (tag36h11, tagCustom48h12)
    python tools/make_test_tags.py --imgs apriltag-imgs --out tags/ [--size-in 6]

tag36h11_id0.pdf    tag36h11 ID 0, black square --size-in (default 6 in), 1-cell white margin
nested48h12.pdf     tagCustom48h12 ID 0 with its 8-cell black ring --size-in, and tagCustom48h12
                    ID 1 in its 2x2 center hole (1/5 scale). Detector sizes for apriltag_ros:
                    outer 0.75 x ring, inner 0.15 x ring (the 6-cell inner white square).
Print at 100% / "actual size" (no fit to page) and check the 100 mm bar with a ruler; measure the
black square / ring after printing and pass the measured sizes to eval/tag_climb_score.py.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

DPI = 600
PAGE = (int(8.5 * DPI), int(11 * DPI))


def bits(imgs, fam, i):
    f = {"tag36h11": "tag36h11/tag36_11_%05d.png", "tagCustom48h12": "tagCustom48h12/tag48_12_%05d.png"}[fam]
    im = Image.open(Path(imgs) / (f % i)).convert("RGBA")
    return [[(im.getpixel((c, r))[0] > 128, im.getpixel((c, r))[3] > 128) for c in range(im.width)] for r in range(im.height)]


def paint(draw, b, x0, y0, cell):
    for r, row in enumerate(b):
        for c, (white, opaque) in enumerate(row):
            if opaque:
                draw.rectangle([round(x0 + c * cell), round(y0 + r * cell), round(x0 + (c + 1) * cell) - 1,
                                round(y0 + (r + 1) * cell) - 1], fill=255 if white else 0)


def page(title, lines):
    im = Image.new("L", PAGE, 255)
    d = ImageDraw.Draw(im)
    mm = DPI / 25.4
    y = PAGE[1] - int(1.1 * DPI)
    d.rectangle([int(0.5 * DPI), y, int(0.5 * DPI + 100 * mm), y + int(0.06 * DPI)], fill=0)
    d.text((int(0.5 * DPI), y + int(0.1 * DPI)), "this bar must measure 100 mm", fill=0)
    for k, t in enumerate([title] + lines):
        d.text((int(0.5 * DPI), int(0.35 * DPI) + k * int(0.18 * DPI)), t, fill=0)
    return im, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgs", required=True)
    ap.add_argument("--out", default="tags")
    ap.add_argument("--size-in", type=float, default=6.0, help="tag36h11 black square = nested black ring edge, inches")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cell = a.size_in * DPI / 8

    im, d = page(f"tag36h11 ID 0, black square {a.size_in:g} in ({a.size_in * 25.4:.1f} mm)",
                 [f"apriltag_ros: family 36h11, size {a.size_in * 0.0254:.4f}"])
    x0, y0 = (PAGE[0] - 10 * cell) / 2, (PAGE[1] - 10 * cell) / 2
    paint(d, bits(a.imgs, "tag36h11", 0), x0, y0, cell)
    d.rectangle([round(x0), round(y0), round(x0 + 10 * cell), round(y0 + 10 * cell)], outline=160, width=2)   # cut line
    im.save(out / "tag36h11_id0.pdf", resolution=DPI)

    ring = a.size_in * 0.0254
    im, d = page(f"nested tagCustom48h12: ID 0 (black ring {a.size_in:g} in) with ID 1 inside",
                 [f"apriltag_ros: family Custom48h12, outer size {0.75 * ring:.4f}, inner size {0.15 * ring:.5f}",
                  "(size = the 6-cell inner white square, not the black ring)"])
    x0, y0 = (PAGE[0] - 10 * cell) / 2, (PAGE[1] - 10 * cell) / 2
    if 10 * cell > PAGE[0] - 0.4 * DPI:
        raise SystemExit("nested tag too wide for letter at this size; use --size-in 6 or less")
    paint(d, bits(a.imgs, "tagCustom48h12", 0), x0, y0, cell)
    paint(d, bits(a.imgs, "tagCustom48h12", 1), x0 + 4 * cell, y0 + 4 * cell, cell / 5)
    im.save(out / "nested48h12.pdf", resolution=DPI)
    print(f"wrote {out}/tag36h11_id0.pdf and {out}/nested48h12.pdf")


if __name__ == "__main__":
    main()
