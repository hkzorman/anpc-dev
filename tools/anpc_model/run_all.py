"""One-command build: spec module -> .b3d + skin atlas(es) + icon + report.

Usage:
    python run_all.py <spec_module.py> --out <dir> [--blender <exe>]
                      [--no-blender] [--palettes a,b]

Outputs under <dir>:
    models/<name>.b3d
    textures/<name>.png            (first palette)
    textures/<name>_<palette>.png  (other palettes)
    textures/<name>_spawner.png    (if the spec module has icon(pal))
    build/layout.json  build/ascii.txt  build/report.txt

The spec module (pure python, no third-party imports at module level) must
provide:
    SPEC = {
        'name': str,                      # base name (mesh, armature suffix, file)
        'px_per_unit': 4.0,
        'atlas': 64 or None,              # None = auto (smallest power of 2)
        'layout': {...} or None,          # explicit rects, else auto-packed
        'parts': [ {name, center, size, group, faces?, face_px?, mirror_right?} ],
        'bones': [ {name, head, tail, parent?} ],
        'armature': optional armature object name,
        'animation': {
            'frames': N,                  # b3d KEYS frames (1..N)
            'fps': 60,
            'clips': [ {name, start, end, speed?, loop?, after?} ],
                                             # 0-based anpc frames (b3d = +1)
            'rest': optional {bone: (loc, rot)},
        },
        'palettes': {name: {FUR, FUR_L, STRIPE, CREAM, PINK, NOSE, EYE}},
    }
    paint(A)  -> painter: draw canonical faces via A.grid/A.put/A.band/...
    pose(f)   -> optional: {bone: ((lx,ly,lz),(rx,ry,rz))} per b3d frame f
    icon(pal) -> optional: 16x16 RGBA Image
    preview(img) -> optional: extra ascii preview lines

Exit code 0 only if Blender build, skin audit and b3d verification all pass.
"""
import argparse
import glob
import importlib.util
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import box_uv
import layout_pack
import skin as skins
import verify_b3d
import preview as prev


def load_spec_module(path):
    path = os.path.abspath(path)
    mod_name = os.path.splitext(os.path.basename(path))[0]
    s = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(mod)
    return mod


def find_blender(explicit):
    cands = [explicit, os.environ.get('BLENDER_EXE')]
    if not explicit:
        cands += glob.glob(r'C:\Program Files\Blender Foundation\*\blender.exe')
        cands += glob.glob(r'C:\Program Files\Blender Foundation\Blender\*\blender.exe')
        cands += glob.glob(r'C:\Program Files (x86)\Blender Foundation\*\blender.exe')
        cands += glob.glob(r'C:\Users\hecto\AppData\Roaming\Blender Foundation\Blender\*\blender.exe')
        cands += glob.glob(os.path.expanduser(r'~\AppData\Local\Programs\Blender\*\blender.exe'))
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def build(spec, mod, layout, out_dir, blender, do_blender, palettes):
    name = spec['name']
    build_dir = os.path.join(out_dir, 'build')
    os.makedirs(build_dir, exist_ok=True)
    models_dir = os.path.join(out_dir, 'models')
    tex_dir = os.path.join(out_dir, 'textures')
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(tex_dir, exist_ok=True)
    report_lines = []

    def log(line=''):
        print(line)
        report_lines.append(line)

    # --- mesh + layout ----------------------------------------------------
    sizes = box_uv.region_sizes(spec)
    layout, size = layout_pack.resolve(spec, sizes)
    spec = dict(spec)
    spec['atlas_size'] = size
    parts_data, verts, uvs, quads, groups = box_uv.build_mesh(spec, layout)
    layout_path = os.path.join(build_dir, 'layout.json')
    json.dump({'size': size, 'regions': layout}, open(layout_path, 'w'))
    log('layout: %d x %d atlas, %d regions' % (size, size, len(layout)))

    # --- blender ----------------------------------------------------------
    b3d_path = os.path.join(models_dir, name + '.b3d')
    if do_blender:
        if not blender:
            raise SystemExit('no blender executable found (use --blender / BLENDER_EXE)')
        # Paths via env vars: Blender 5.x swallows unknown --flags after
        # --python (tries to load them as files), but env passes through.
        env = dict(os.environ)
        env['ANPC_SPEC'] = os.path.abspath(sys.argv[1])
        env['ANPC_LAYOUT'] = layout_path
        env['ANPC_OUT'] = b3d_path
        cmd = [blender, '--background', '--python', os.path.join(HERE, 'blender_build.py')]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=env)
        ok = 'B3D_OK' in (r.stdout or '')
        if not ok:
            log('BLENDER FAILED (rc=%s)' % r.returncode)
            log((r.stdout or '')[-2000:])
            log((r.stderr or '')[-2000:])
            open(os.path.join(build_dir, 'report.txt'), 'w',
                  encoding='utf-8').write('\n'.join(report_lines))
            raise SystemExit(1)
        else:
            for line in r.stdout.splitlines():
                if line.startswith('B3D_OK'):
                    log('blender: ' + line[len('B3D_OK '):].strip())
    else:
        if not os.path.exists(b3d_path):
            raise SystemExit('--no-blender but %s does not exist' % b3d_path)
        log('blender: skipped (using existing %s)' % b3d_path)

    # --- skins -------------------------------------------------------------
    pnames = palettes or list(spec['palettes'])
    skin_report = []
    first = True
    for pn in pnames:
        if pn not in spec['palettes']:
            raise SystemExit('unknown palette %r' % pn)
        img, audit = skins.make_atlas(spec, layout, size, spec['palettes'][pn], mod.paint)
        fn = name + ('' if first else '_' + pn) + '.png'
        img.save(os.path.join(tex_dir, fn))
        skin_report.append((fn, audit))
        log('skin %s: covered=%d bad=%d' % (fn, audit['covered'], audit['bad']))
        first = False
    if hasattr(mod, 'icon'):
        icon_path = os.path.join(tex_dir, name + '_spawner.png')
        mod.icon(spec['palettes'][pnames[0]]).save(icon_path)
        log('icon: %s' % os.path.basename(icon_path))

    # --- verify -------------------------------------------------------------
    log('verify %s:' % os.path.basename(b3d_path))
    vreport = verify_b3d.verify(spec, layout, b3d_path)
    vfail = 0
    for cname, ok, detail in vreport:
        log('  %-22s %s  %s' % (cname, 'PASS' if ok else 'FAIL', detail))
        vfail += (not ok)

    # --- collision box suggestion (paste into the mod lua) --------------------
    # Square-rule (all anpc mods): cross-section side = min(width, depth),
    # height = model height; 1 model unit = 0.1 block.
    def snap(v):
        return math.ceil(v / 0.05 - 1e-9) * 0.05
    mn, mx = box_uv.model_bbox(spec)
    dims = [(mx[i] - mn[i]) / 10.0 for i in range(3)]
    side = snap(min(dims[0], dims[1]))
    height = snap(dims[2])
    half = side / 2.0
    log('collisionbox: {%.2f, 0, %.2f, %.2f, %.2f, %.2f}'
        '   # square %.2f x %.2f, height %.2f (model %.3f x %.3f x %.3f blocks)'
        % (-half, -half, half, height, half, side, side, height,
           dims[0], dims[1], dims[2]))

    # --- preview --------------------------------------------------------------
    ascii_path = os.path.join(build_dir, 'ascii.txt')
    from PIL import Image as _Image
    pimg = _Image.open(os.path.join(tex_dir, name + '.png'))
    ascii_lines = prev.preview(pimg, mod)
    open(ascii_path, 'w', encoding='utf-8').write('\n'.join(ascii_lines))
    log('preview: %s' % ascii_path)

    open(os.path.join(build_dir, 'report.txt'), 'w').write('\n'.join(report_lines))
    log('report: %s' % os.path.join(build_dir, 'report.txt'))

    ok = vfail == 0 and all(a['bad'] == 0 for _, a in skin_report)
    log('RUN_ALL %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('spec')
    ap.add_argument('--out', required=True)
    ap.add_argument('--blender', default=None)
    ap.add_argument('--no-blender', action='store_true')
    ap.add_argument('--palettes', default=None, help='comma list; default all')
    args = ap.parse_args()

    mod = load_spec_module(args.spec)
    spec = mod.SPEC
    blender = None if args.no_blender else find_blender(args.blender)
    if args.palettes:
        pals = args.palettes.split(',')
    else:
        pals = getattr(mod, 'PALETTE_ORDER', None) or list(spec['palettes'])
    sys.exit(build(spec, mod, None, args.out, blender, not args.no_blender, pals))


if __name__ == '__main__':
    main()
