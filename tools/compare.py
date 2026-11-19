"""A sheet: per texture, the 26.3 port's (left) beside the replacement (right), six pairs a row.

    python3 -I tools/compare.py <26.3 textures> <replaced textures> <out.png> sub/name...
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import png  # noqa: E402

S, GAP, PAIR_GAP, PER_ROW = 5, 3, 14, 6
BG = (0x2b, 0x2b, 0x2b)


def first(im):
    return png.Image(im.w, im.w, bytearray(im.px[:im.w * im.w * 4]))


def main():
    a_root, b_root, out = sys.argv[1:4]
    pairs = [(first(png.read(os.path.join(a_root, n + '.png'))), first(png.read(os.path.join(b_root, n + '.png'))))
             for n in sys.argv[4:]]
    cw = 16 * S
    pw = 2 * cw + GAP
    rows = (len(pairs) + PER_ROW - 1) // PER_ROW
    w = PAIR_GAP + PER_ROW * (pw + PAIR_GAP)
    h = PAIR_GAP + rows * (cw + PAIR_GAP)
    px = bytearray(bytes((*BG, 255)) * (w * h))
    for k, pair in enumerate(pairs):
        r, c = divmod(k, PER_ROW)
        for j, im in enumerate(pair):
            ox = PAIR_GAP + c * (pw + PAIR_GAP) + j * (cw + GAP)
            oy = PAIR_GAP + r * (cw + PAIR_GAP)
            for y in range(cw):
                for x in range(cw):
                    i = (((y * im.w) // cw) * im.w + (x * im.w) // cw) * 4
                    rr, gg, bb, al = im.px[i:i + 4]
                    if al < 128:
                        rr, gg, bb = (0x55, 0x55, 0x55) if ((x // 8 + y // 8) % 2) else (0x48, 0x48, 0x48)
                    q = ((oy + y) * w + ox + x) * 4
                    px[q:q + 4] = bytes((rr, gg, bb, 255))
    png.write(out, png.Image(w, h, px))


main()
