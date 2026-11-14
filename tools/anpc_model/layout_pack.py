"""UV layout: place face pixel-rects on the atlas grid.

Two modes:
  * explicit - spec['layout'] = {region_name: (x, y, w, h)} is used as-is and
    validated (bounds + no overlaps). The cat's hand-tuned LAYOUT lives here
    so its skin stays byte-identical.
  * auto     - shelf packing (first-fit-decreasing by height, then width),
    no gutter: touching rects are fine because UVs land exactly on rect
    borders. Atlas size = spec['atlas'] if set, else the smallest power of
    two (>= 16) that fits.

Rects are (px0, py0, w, h) with py0 measured from the TOP of the image
(matches PIL and the file-UV v convention).
"""


def validate(layout, size):
    """Bounds + overlap check. Returns sorted list of region names."""
    rects = {}
    for name, (x, y, w, h) in layout.items():
        if x < 0 or y < 0 or x + w > size or y + h > size:
            raise ValueError("region %r (%d,%d %dx%d) out of %d x %d atlas"
                             % (name, x, y, w, h, size, size))
        if w <= 0 or h <= 0:
            raise ValueError("region %r has empty size" % name)
        rects[name] = (x, y, x + w, y + h)
    names = sorted(rects)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = rects[names[i]], rects[names[j]]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                raise ValueError("overlap: %r %r vs %r %r"
                                 % (names[i], a, names[j], b))
    return names


def shelf_pack(sizes, W, H):
    """Shelf-pack rects into W x H. Returns {name: (x, y, w, h)} or None."""
    items = sorted(sizes.items(), key=lambda kv: (-kv[1][1], -kv[1][0]))
    layout, y, sh, xn = {}, 0, 0, 0
    for name, (w, h) in items:
        if xn + w > W:                      # wrap to next shelf
            y += sh
            sh, xn = 0, 0
        if y + h > H:
            return None
        layout[name] = (xn, y, w, h)
        xn += w
        sh = max(sh, h)
    return layout


def resolve(spec, region_sizes):
    """Pick (layout, atlas_size) for a spec.

    spec['layout'] explicit wins (validated against spec['atlas'] or the
    smallest power of two that fits). Otherwise auto-pack.
    """
    if spec.get('layout'):
        layout = {k: tuple(v) for k, v in spec['layout'].items()}
        missing = set(region_sizes) - set(layout)
        extra = set(layout) - set(region_sizes)
        if missing or extra:
            raise ValueError("explicit layout mismatch: missing %r, extra %r"
                             % (sorted(missing), sorted(extra)))
        # sizes must agree with the derived face sizes
        for name, (w, h) in region_sizes.items():
            x, y, lw, lh = layout[name]
            if (lw, lh) != (w, h):
                raise ValueError("explicit layout size for %r is (%d,%d), expected (%d,%d)"
                                 % (name, lw, lh, w, h))
        size = spec.get('atlas') or 64
        validate(layout, size)
        return layout, size

    size = spec.get('atlas')
    if size:
        layout = shelf_pack(region_sizes, size, size)
        if layout is None:
            raise ValueError("regions do not fit in %d x %d atlas" % (size, size))
        return layout, size

    # grow: smallest power of two >= 16 that fits
    size = 16
    while True:
        layout = shelf_pack(region_sizes, size, size)
        if layout is not None:
            return layout, size
        if size > 1024:
            raise ValueError("regions do not fit in a 1024 x 1024 atlas")
        size *= 2
