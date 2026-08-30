#!/usr/bin/env -S uv run --quiet --with pillow python
"""Composite a phone silhouette around each captured 390x844 screenshot.

A bare viewport crop reads as a browser window shrunk down, not as the app on a
phone, and the README's claim is that this is usable one-handed while somebody is
deciding where to eat. The frame is drawn rather than sourced: an image of a real
handset is somebody's copyrighted render, and this repository is about to be public.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

SCALE = 2  # the captures are @2x
W, H = 390 * SCALE, 844 * SCALE
BEZEL = 12 * SCALE
RADIUS = 46 * SCALE
INNER_RADIUS = RADIUS - BEZEL
ISLAND_W, ISLAND_H = 108 * SCALE, 30 * SCALE
BODY = (26, 26, 28, 255)
PAD = 8 * SCALE
# The capture starts at the app's own header -- there is no iOS status bar in a
# viewport screenshot. Without this band the island lands on top of live UI, which
# on /discover meant covering the theme toggle. The band is tinted from the shot's
# own top row so it reads as the same surface rather than a grey stripe.
STATUS_H = 52 * SCALE


def frame(src: Path, dst: Path) -> tuple[int, int]:
    shot = Image.open(src).convert('RGBA')
    if shot.size != (W, H):
        shot = shot.resize((W, H), Image.LANCZOS)

    tint = shot.crop((0, 0, W, 1)).resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    screen = Image.new('RGBA', (W, H + STATUS_H), tint)
    screen.paste(shot, (0, STATUS_H))
    shot = screen

    out_w, out_h = W + 2 * BEZEL + 2 * PAD, H + STATUS_H + 2 * BEZEL + 2 * PAD
    canvas = Image.new('RGBA', (out_w, out_h), (0, 0, 0, 0))

    body = Image.new('RGBA', (out_w - 2 * PAD, out_h - 2 * PAD), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle((0, 0, body.width - 1, body.height - 1), radius=RADIUS, fill=BODY)
    canvas.alpha_composite(body, (PAD, PAD))

    # Round the screenshot's own corners so it sits inside the bezel rather than
    # poking square corners through it.
    mask = Image.new('L', shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, shot.width - 1, shot.height - 1), radius=INNER_RADIUS, fill=255)
    canvas.paste(shot, (PAD + BEZEL, PAD + BEZEL), mask)

    d = ImageDraw.Draw(canvas)
    ix = PAD + BEZEL + (W - ISLAND_W) // 2
    iy = PAD + BEZEL + 11 * SCALE
    d.rounded_rectangle((ix, iy, ix + ISLAND_W, iy + ISLAND_H), radius=ISLAND_H // 2, fill=BODY)

    canvas.save(dst, 'WEBP', quality=84, method=6)
    return canvas.size


if __name__ == '__main__':
    img_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('docs/img')
    for src in sorted(img_dir.glob('*-phone.webp')):
        dst = src.with_name(src.stem + '-framed.webp')
        size = frame(src, dst)
        print(f'  {dst.name:28} {size[0]}x{size[1]}  {dst.stat().st_size // 1024} KB')
