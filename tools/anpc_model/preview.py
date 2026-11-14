"""ASCII preview of a skin atlas (for chats / phones / logs).

Renders the full atlas downscaled (2x2 average by default) with luminance
glyphs, plus any extra lines a spec module's optional preview(img) hook
returns (e.g. an assembled front view).
"""
from PIL import Image

GLYPH = [
    (215, '░'),   # cream / white
    (150, '▒'),   # mid-light (base fur / pink)
    (110, '▓'),   # mid-dark
    (0, '█'),     # dark (stripes / eyes / nose)
]


def glyph(r, g, b, a):
    if a < 128:
        return ' '
    l = 0.299 * r + 0.587 * g + 0.114 * b
    for thr, ch in GLYPH:
        if l >= thr:
            return ch
    return '█'


def atlas_ascii(img, block=2):
    px = img.load()
    W, H = img.size
    lines = []
    for y in range(0, H, block):
        row = []
        for x in range(0, W, block):
            rs = gs = bs = 0
            vis = 0
            for dy in range(block):
                for dx in range(block):
                    r, g, b, a = px[x + dx, y + dy]
                    if a >= 128:
                        rs += r
                        gs += g
                        bs += b
                        vis += 1
            if vis == 0:
                row.append(' ')
            else:
                row.append(glyph(rs // vis, gs // vis, bs // vis, 255))
        lines.append(''.join(row).rstrip())
    return lines


def preview(img, spec_module=None, block=2):
    lines = ['=== ATLAS %dx%d @ %dx%d downscale ===' % (img.size[0], img.size[1], block, block)]
    lines += atlas_ascii(img, block)
    lines.append('legend: ░ light  ▒ base/mid  ▓ mid-dark  █ dark  (space = unused)')
    if spec_module is not None and hasattr(spec_module, 'preview'):
        lines += spec_module.preview(img)
    return lines


if __name__ == '__main__':
    import sys
    im = Image.open(sys.argv[1]).convert('RGBA')
    print('\n'.join(preview(im)))
