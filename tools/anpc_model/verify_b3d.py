"""Spec-driven verification of an exported .b3d (run after every build).

Checks (all derived from the spec + layout - no model-specific code):
  1.  root node name, ANIM header (frames-1, fps)
  2.  vert/quad counts
  3.  every vertex UV inside [0,1]
  4.  per-quad corner UVs match the layout rect exactly (end-to-end UV check)
  5.  triangle list matches the expected 2-tris-per-quad order
  6.  per-face triangle winding matches the engine culling convention
      (top/bottom faces with the wrong sweep are culled - invisible)
  7.  bone weight tables match the spec part->group mapping
  8.  every bone keyed at every frame 1..N
  9.  frames outside all clips are bit-identical to each other (neutral rest)
  10. every clip contains motion somewhere (some bone differs from f1)
  11. the mesh brush carries no textures (skin comes from the entity)

Exit code 0 = all pass.
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from b3d import parse_file, bone_nodes
from box_uv import FACE_ORDER, part_faces, _FACE_LOOPS, _TEXUV

EPS = 1e-5


def _is_unit_quat(q):
    n = math.sqrt(sum(c * c for c in q))
    return abs(n - 1.0) < 1e-4


def _clip_b3d_frames(spec):
    """0-based anim clips -> {b3d_frame: clip_name}."""
    out = {}
    for c in spec.get('animation', {}).get('clips', []):
        for f in range(c['start'] + 1, c['end'] + 2):
            out[f] = c['name']
    return out


def _is_identity_quat(q):
    # accept both (w,x,y,z) and (x,y,z,w) storage orders
    if abs(q[0]) > 1 - EPS and max(abs(q[1]), abs(q[2]), abs(q[3])) < EPS:
        return True
    if abs(q[3]) > 1 - EPS and max(abs(q[0]), abs(q[1]), abs(q[2])) < EPS:
        return True
    return False


def verify(spec, layout, path):
    f = parse_file(path)
    root = f['nodes'][0]
    A = spec['atlas_size']
    parts = spec['parts']
    anim = spec['animation']
    N = anim['frames']
    clips = _clip_b3d_frames(spec)
    report = []

    def check(name, ok, detail=''):
        report.append((name, bool(ok), detail))

    # 1. structure ---------------------------------------------------------
    check('root name', root['name'] == (spec.get('object_name') or spec['name']),
          root['name'])
    if root['anim']:
        check('ANIM header',
              root['anim'][1] == N - 1 and abs(root['anim'][2] - anim['fps']) < EPS,
              '(%d,%d,%g) want (frames-1=%d, fps=%g)' % (
                  root['anim'][0], root['anim'][1], root['anim'][2], N - 1, anim['fps']))
    else:
        check('ANIM header', False, 'missing')

    m = root['mesh']
    verts = m['vrts'][3]
    tris = [t for _, ts in m['tris'] for t in ts]

    # 2. counts -------------------------------------------------------------
    check('vert count', len(verts) == 24 * len(parts),
          '%d want %d' % (len(verts), 24 * len(parts)))
    check('tri count', len(tris) == 12 * len(parts),
          '%d want %d' % (len(tris), 12 * len(parts)))

    # 3. UV range -------------------------------------------------------------
    uv_out = 0
    for v in verts:
        for u in v[3][0]:
            if not (-EPS <= u <= 1 + EPS):
                uv_out += 1
    check('UVs in [0,1]', uv_out == 0, '%d out of range' % uv_out)

    # 4/5. per-quad UV corners + triangle order -------------------------------
    bad_uv, bad_tri = [], []
    for i, p in enumerate(parts):
        base = i * 24
        regions = part_faces(p)
        for k, face in enumerate(FACE_ORDER):
            px0, py0, w, h = layout[regions[face]]
            # vertex order per face (side faces [BL,BR,TR,TL], top/bottom
            # [BL,TL,TR,BR] - see box_uv._FACE_LOOPS)
            want_uv = [((px0 + _TEXUV[tc][0] * w) / A,
                        (py0 + _TEXUV[tc][1] * h) / A)
                       for _, tc in _FACE_LOOPS[face]]
            # exporter tessellation per quad: (v2,v1,v0) then (v3,v2,v0)
            want_tris = [(base + k * 4 + 2, base + k * 4 + 1, base + k * 4),
                         (base + k * 4 + 3, base + k * 4 + 2, base + k * 4)]
            for j in range(4):
                got = verts[base + k * 4 + j][3][0]
                if any(abs(got[a] - want_uv[j][a]) > EPS for a in range(2)):
                    bad_uv.append('%s.%s v%d' % (p['name'], face, j))
            if [tris[2 * (i * 6 + k)], tris[2 * (i * 6 + k) + 1]] != want_tris:
                bad_tri.append('%s.%s' % (p['name'], face))
    check('per-quad UV corners', not bad_uv, ' '.join(bad_uv[:6]))
    check('triangle order', not bad_tri, ' '.join(bad_tri[:6]))

    # 6. per-face winding -------------------------------------------------------
    # Engine front-facing convention (what the working side faces establish):
    # the file-space triangle normal points AWAY from the face's outward
    # direction. File space = (Bx, Bz, By): blender +Y -> file +Z,
    # blender +Z -> file +Y, +X unchanged.
    outw_file = {'+Y': (0, 0, 1), '-Y': (0, 0, -1), '+X': (1, 0, 0),
                 '-X': (-1, 0, 0), '+Z': (0, 1, 0), '-Z': (0, -1, 0)}
    bad_wind = []
    for i, p in enumerate(parts):
        base = i * 24
        for k, face in enumerate(FACE_ORDER):
            b = base + k * 4
            v0, v1, v2 = (verts[b + j][0] for j in range(3))
            e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            nm = (e1[1] * e2[2] - e1[2] * e2[1],
                  e1[2] * e2[0] - e1[0] * e2[2],
                  e1[0] * e2[1] - e1[1] * e2[0])
            o = outw_file[face]
            if sum(nm[a] * o[a] for a in range(3)) > -EPS:
                bad_wind.append('%s.%s' % (p['name'], face))
    check('face winding', not bad_wind, ' '.join(bad_wind[:6]))

    # 6. bone membership --------------------------------------------------------
    bnodes = {n['name']: n for n in bone_nodes(root)}
    want_bones = set(b['name'] for b in spec['bones'])
    check('bone set', want_bones <= set(bnodes),
          'file %r spec %r' % (sorted(bnodes), sorted(want_bones)))
    bad_bone = []
    for bn in sorted(want_bones):
        if bn not in bnodes:
            continue
        have = set(v for (v, w) in bnodes[bn]['bones'] if w > 0.001)
        want = set()
        for i, p in enumerate(parts):
            if p['group'] == bn:
                want.update(range(i * 24, i * 24 + 24))
        if have != want:
            bad_bone.append('%s (have %d want %d)' % (bn, len(have), len(want)))
    check('bone membership', not bad_bone, ' '.join(bad_bone[:6]))

    # 7. every bone keyed at every frame ------------------------------------------
    bad_keys = []
    key_map = {}
    for bn, n in bnodes.items():
        if bn not in want_bones or not n['keys']:
            bad_keys.append('%s missing keys' % bn)
            continue
        frames = set(k[0] for k in n['keys'][1])
        if frames != set(range(1, N + 1)):
            bad_keys.append('%s %d/%d frames' % (bn, len(frames), N))
        key_map[bn] = {k[0]: k for k in n['keys'][1]}
    check('keys complete', not bad_keys, ' '.join(bad_keys[:6]))

    # 8. non-clip frames all bit-identical (the neutral rest) ---------------------
    # f1 itself may sit INSIDE the first clip (the cat's stand loop starts at
    # t=0 with a head phase offset), so the reference is the first frame that
    # is not in any clip. anpc relies on all non-clip frames being one and the
    # same rest for animation_after hand-offs.
    bad_rest = []
    f1 = {bn: key_map.get(bn, {}).get(1) for bn in key_map}
    nonclip = [fr for fr in range(1, N + 1) if fr not in clips]
    if nonclip and key_map:
        ref = nonclip[0]
        for bn in key_map:
            kref = key_map[bn].get(ref)
            if not kref:
                bad_rest.append('%s f%d missing' % (bn, ref))
                continue
            if not _is_unit_quat(kref[3]):
                bad_rest.append('%s f%d quat norm %r' % (bn, ref, kref[3]))
        for fr in nonclip[1:]:
            for bn in key_map:
                k = key_map[bn].get(fr)
                kref = key_map[bn].get(ref)
                if not k or not kref:
                    continue
                if (k[1] != kref[1]) or (k[3] != kref[3]):
                    bad_rest.append('%s f%d != f%d' % (bn, fr, ref))
    check('rest frames neutral', not bad_rest, ' '.join(bad_rest[:6]))

    # 9. every clip contains motion somewhere ------------------------------------
    # (a clip may START on the rest pose - compare against the neutral rest)
    dead = []
    clip_frames = {}
    for fr, cname in sorted(clips.items()):
        clip_frames.setdefault(cname, []).append(fr)
    ref = nonclip[0] if nonclip else None
    for cname, frames in clip_frames.items():
        moved = False
        for fr in frames:
            for bn, ks in key_map.items():
                k = ks.get(fr)
                if ref is not None:
                    kref = ks.get(ref)
                    base = kref
                else:
                    k1 = f1.get(bn)
                    base = k1
                if k and base and (k[1] != base[1] or k[3] != base[3]):
                    moved = True
                    break
            if moved:
                break
        if not moved:
            dead.append(cname)
    check('clips animated', not dead, ' '.join(dead[:8]))

    # 10. no textures on the mesh brush ----------------------------------------------
    bid = m['brush_id']
    if bid < 0:
        check('brush untextured', True, 'sentinel -1 (skin comes from entity)')
    elif bid < len(f['brus']):
        tids = f['brus'][bid][5]
        check('brush untextured', not tids or all(t < 0 for t in tids), str(tids))
    else:
        check('brush untextured', False, 'brush id %d out of range' % bid)

    return report


def main():
    if len(sys.argv) < 3:
        sys.exit('usage: verify_b3d.py <spec_module.py> <file.b3d> [layout.json]')
    import importlib.util
    import json

    spath = os.path.abspath(sys.argv[1])
    s = importlib.util.spec_from_file_location('specmod', spath)
    mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(mod)
    spec = mod.SPEC

    if len(sys.argv) > 3:
        ldata = json.load(open(sys.argv[3]))
        if isinstance(ldata, dict) and 'regions' in ldata:
            layout = {k: tuple(v) for k, v in ldata['regions'].items()}
            size = ldata['size']
        else:
            layout = {k: tuple(v) for k, v in ldata.items()}
            size = max(max(x + w, y + h) for (x, y, w, h) in layout.values())
        spec = dict(spec)
        spec['atlas_size'] = size
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import box_uv, layout_pack
        spec = dict(spec)
        layout, size = layout_pack.resolve(spec, box_uv.region_sizes(spec))
        spec['atlas_size'] = size

    report = verify(spec, layout, sys.argv[2])
    fails = 0
    for name, ok, detail in report:
        print('%-22s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        fails += (not ok)
    print('VERIFY %s (%d/%d)' % ('PASS' if fails == 0 else 'FAIL', len(report) - fails, len(report)))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
