"""Skin atlas painter - palette-driven, face-painter driven.

A spec provides:
  * palettes: {palette_name: {FUR, FUR_L, STRIPE, CREAM, PINK, NOSE, EYE}}
  * a painter function  painter(A)  on the spec MODULE (not the SPEC dict)
    that draws the canonical faces of every part.

Canonical faces per part: front (+Y), back (-Y), left (-X), top (+Z),
bottom (-Z). The right face (+X) is auto-filled as the horizontal flip of
the left face when the part has mirror_right (default True) - this mirrors
how a +X face samples its texture from the back of the box, so symmetric
markings appear mirrored in 3D. Set mirror_right: False on a part and
paint the +X face explicitly when it must differ.

Grid orientation (per face, row 0 = top of the rect, col 0 = left):
  front/back : col 0 = +X = the model's RIGHT side
  left       : col 0 = +Y = the model's FRONT
  right      : col 0 = -Y = the model's BACK (before auto-flip it reads
               like the left face; the flip fixes the axis direction)
  top/bottom : col 0 = model left, row 0 = model back (top) / front (bottom)

After painting, the atlas is audited: every layout rect fully opaque,
everything outside transparent.
"""
from PIL import Image


class Atlas:
    """Working surface + helpers handed to the painter."""

    def __init__(self, size, layout, palette):
        self.img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self.layout = layout
        self.palette = palette
        self.FUR = palette["FUR"]
        self._put_done = set()
        self._grids = {}

    # -- low level -----------------------------------------------------
    def rect(self, name):
        return self.layout[name]

    def grid(self, name):
        """Fresh FUR-filled grid for a region."""
        x, y, w, h = self.layout[name]
        return [[self.FUR] * w for _ in range(h)], x, y, w, h

    def put(self, name, g):
        x, y, w, h = self.layout[name]
        if len(g) != h or any(len(r) != w for r in g):
            raise ValueError("grid for %r is %dx%d, want %dx%d"
                             % (name, len(g[0]) if g else 0, len(g), w, h))
        for r, row in enumerate(g):
            for c, col in enumerate(row):
                self.img.putpixel((x + c, y + r), col + (255,))
        self._put_done.add(name)
        self._grids[name] = [row[:] for row in g]

    # -- drawing helpers (operate on a grid in place) -------------------
    def rows_of(self, g, r, cols, col):
        for c in cols:
            g[r][c] = col

    def band(self, g, r0, r1, cols, col):
        for r in range(r0, r1 + 1):
            self.rows_of(g, r, cols, col)

    def full_row(self, g, r, col):
        self.rows_of(g, r, range(len(g[0])), col)

    @staticmethod
    def flip(g):
        return [row[::-1] for row in g]


def audit(img, size, layout):
    """Opaque inside every rect, transparent outside. -> (covered, bad)."""
    px = img.load()
    bad_in = bad_out = covered = 0
    for y in range(size):
        for x in range(size):
            inside = any(
                a <= x < a + w and b <= y < b + h
                for (a, b, w, h) in layout.values()
            )
            a = px[x, y][3]
            if inside:
                covered += 1
                if a != 255:
                    bad_in += 1
            elif a != 0:
                bad_out += 1
    return covered, bad_in + bad_out


def make_atlas(spec, layout, size, palette, painter, mirror=True):
    """Paint one variant. Returns (Image, audit_report)."""
    A = Atlas(size, layout, palette)
    painter(A)

    if mirror:
        for part in spec['parts']:
            if not part.get('mirror_right', True):
                continue
            faces = part.get('faces') or {}
            left = faces.get('-X')
            right = faces.get('+X')
            if left and right and right not in A._put_done:
                A.put(right, A.flip(A._grids[left]))

    covered, bad = audit(A.img, size, layout)
    missing = set(layout) - A._put_done
    if missing:
        raise ValueError("regions never painted: %r" % sorted(missing))
    return A.img, {'covered': covered, 'bad': bad}
