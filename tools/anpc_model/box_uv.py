"""Box-part geometry: turns a spec's part list into verts/UVs/faces/groups.

Conventions (shared with the b3d exporter family - do NOT "fix" signs):
  * Blender Z-up; model units; feet at z=0 by authoring choice.
  * File (.b3d) UV: u in [0,1] left->right, v in [0,1] with v=0 at the image
    TOP. The exporter writes (u, 1 - v_blender), so the Blender UV we store is
    (u, 1 - pixel_row / ATLAS) - do not "simplify" away the flip.
  * Each box = 24 unshared verts, 6 quads, face order
    ['+Y', '-Y', '+X', '-X', '+Z', '-Z'] (front, back, right, left, top, bottom
    for a part facing +Y).
  * Per-face vertex loop = the (corner, tex-corner) pairs in _FACE_LOOPS.
    Side faces sweep [BL, BR, TR, TL]; top/bottom deliberately sweep
    [BL, TL, TR, BR] - only that winding survives the exporter's triangle
    reversal + the det -1 axis swap and renders in-engine. Do NOT
    "normalize" all faces to one sweep (the faces get culled, invisible).
  * Face pixel size = part size along the face's (u, v) axes * px_per_unit,
    overridable per face with part["face_px"][face] = (w, h). (The cat uses
    (10,10) instead of the derived (12,10) on the head front/back - a
    deliberate horizontal squish.)

Face -> (u-axis, v-axis) into part "size" (x, y, z):
  +Y / -Y : (x, z)   front/back
  +X / -X : (y, z)   sides
  +Z / -Z : (x, y)   top/bottom
"""
FACE_ORDER = ['+Y', '-Y', '+X', '-X', '+Z', '-Z']
FACE_AXES = {'+Y': (0, 2), '-Y': (0, 2), '+X': (1, 2), '-X': (1, 2),
             '+Z': (0, 1), '-Z': (0, 1)}
FACE_SUFFIX = {'+Y': 'front', '-Y': 'back', '+X': 'right', '-X': 'left',
               '+Z': 'top', '-Z': 'bottom'}

# Per-face quad winding: (corner_sign, tex_corner) pairs in the vertex order
# that renders CORRECTLY in the engine. tex_corner = position of that vertex
# inside the face's pixel rect (col, row: 0 or 1 of (w, h)).
#
# The four side faces sweep [BL, BR, TR, TL]. The top/bottom faces must sweep
# [BL, TL, TR, BR] - the naive [BL, BR, TR, TL] there winds the quad inward
# in Blender. The exporter reverses the winding and the b3d axis swap
# (det -1) flips it back, so the file triangles come out in the same
# convention as the side faces; deviate from that and the engine culls the
# face (it renders invisible). The 3D-corner <-> pixel-corner pairing is
# identical to the naive sweep, so the skin look does not change - only the
# triangle winding.
_TEXUV = {'BL': (0, 1), 'BR': (1, 1), 'TR': (1, 0), 'TL': (0, 0)}
_FACE_LOOPS = {
    '+Y': [((1, 1, 0), 'BL'), ((0, 1, 0), 'BR'), ((0, 1, 1), 'TR'), ((1, 1, 1), 'TL')],
    '-Y': [((0, 0, 0), 'BL'), ((1, 0, 0), 'BR'), ((1, 0, 1), 'TR'), ((0, 0, 1), 'TL')],
    '+X': [((1, 0, 0), 'BL'), ((1, 1, 0), 'BR'), ((1, 1, 1), 'TR'), ((1, 0, 1), 'TL')],
    '-X': [((0, 1, 0), 'BL'), ((0, 0, 0), 'BR'), ((0, 0, 1), 'TR'), ((0, 1, 1), 'TL')],
    '+Z': [((0, 1, 1), 'BL'), ((0, 0, 1), 'TL'), ((1, 0, 1), 'TR'), ((1, 1, 1), 'BR')],
    '-Z': [((0, 0, 0), 'BL'), ((0, 1, 0), 'TL'), ((1, 1, 0), 'TR'), ((1, 0, 0), 'BR')],
}


def part_faces(part):
    """{face: region_name} for a part - explicit part['faces'] or derived."""
    if part.get('faces'):
        faces = dict(part['faces'])
        missing = [f for f in FACE_ORDER if f not in faces]
        if missing:
            raise ValueError("part %r faces missing %r" % (part['name'], missing))
        return faces
    return {f: "%s_%s" % (part['name'], FACE_SUFFIX[f]) for f in FACE_ORDER}


def region_size(part, face, px_per_unit):
    """Pixel (w, h) of one face rect, incl. part['face_px'] overrides."""
    ax_u, ax_v = FACE_AXES[face]
    size = part['size']
    w = int(round(size[ax_u] * px_per_unit))
    h = int(round(size[ax_v] * px_per_unit))
    if w <= 0 or h <= 0:
        raise ValueError("part %r face %s has non-positive px size (%d,%d)"
                         % (part['name'], face, w, h))
    ov = part.get('face_px', {}).get(face)
    if ov:
        w, h = ov
    return w, h


def region_sizes(spec):
    """{region_name: (w, h)} for every face of every part."""
    ppu = spec.get('px_per_unit', 4.0)
    out = {}
    for part in spec['parts']:
        for face, name in part_faces(part).items():
            if name in out:
                w1, h1 = out[name]
                w2, h2 = region_size(part, face, ppu)
                if (w1, h1) != (w2, h2):
                    raise ValueError("region %r size mismatch: (%d,%d) vs (%d,%d)"
                                     % (name, w1, h1, w2, h2))
            else:
                out[name] = region_size(part, face, ppu)
    return out


def box_geom(cx, cy, cz, sx, sy, sz, face_regions, layout, atlassize):
    """Verts/UVs/face-quad indices for one axis-aligned box.

    Returns (verts, uvs, quads):
      verts: 24 (x,y,z), uvs: 24 (u, v_file) matching verts,
      quads: 6 (i0,i1,i2,i3) in FACE_ORDER, indices local to this box.
    """
    x0, x1 = cx - sx / 2.0, cx + sx / 2.0
    y0, y1 = cy - sy / 2.0, cy + sy / 2.0
    z0, z1 = cz - sz / 2.0, cz + sz / 2.0
    span = [(x0, x1), (y0, y1), (z0, z1)]

    verts, uvs, quads = [], [], []
    for fname in FACE_ORDER:
        px0, py0, w, h = layout[face_regions[fname]]
        base = len(verts)
        for (sx_, sy_, sz_), tc in _FACE_LOOPS[fname]:
            verts.append((span[0][sx_], span[1][sy_], span[2][sz_]))
            # tex-corner file-UV position (v_file = pixel row from image top)
            col, row = _TEXUV[tc]
            uvs.append(((px0 + col * w) / atlassize,
                        1.0 - (py0 + row * h) / atlassize))
        quads.append((base, base + 1, base + 2, base + 3))
    return verts, uvs, quads


def build_mesh(spec, layout):
    """Flatten all parts: (parts_data, verts, uvs, quads, groups).

    parts_data[i] = {name, group, regions {face: region_name}, base_vert,
                     quads (global indices), px {face: (w,h)}}
    Verts are 24 per part in FACE_ORDER, so quad k of part i uses global
    indices base + k*4 .. base + k*4+3 (k = position in FACE_ORDER).
    """
    A = spec['atlas_size']
    parts_data, verts, uvs, quads, groups = [], [], [], [], []
    for part in spec['parts']:
        regions = part_faces(part)
        v, uv, q = box_geom(*part['center'], *part['size'], regions, layout, A)
        base = len(verts)
        verts.extend(v)
        uvs.extend(uv)
        quads.extend(tuple(base + i for i in quad) for quad in q)
        groups.extend([part['group']] * len(v))
        parts_data.append({
            'name': part['name'], 'group': part['group'], 'regions': regions,
            'base': base,
            'px': {f: region_size(part, f, spec.get('px_per_unit', 4.0))
                   for f in FACE_ORDER},
        })
    return parts_data, verts, uvs, quads, groups


def model_bbox(spec):
    """(min, max) tuples of the model bounding box in MODEL UNITS.

    1 model unit = 0.1 in-game block. Used to derive the collision box:
    square cross-section (side = min(width, depth)), height = model height.
    """
    mn = [float('inf')] * 3
    mx = [float('-inf')] * 3
    for part in spec['parts']:
        c, s = part['center'], part['size']
        for i in range(3):
            mn[i] = min(mn[i], c[i] - s[i] / 2.0)
            mx[i] = max(mx[i], c[i] + s[i] / 2.0)
    return tuple(mn), tuple(mx)
