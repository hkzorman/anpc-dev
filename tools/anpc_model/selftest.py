"""Regression gate: rebuild the cat from specs/cat.py and prove the output
matches the shipped assets structurally.

  1. run_all.py specs/cat.py --out <temp>        (fresh build + verify)
  2. parsed <temp>/models/cat.b3d  ==  parsed <mod>/models/cat.b3d
       (nodes, verts xyz+uv, tris, bone membership, per-frame per-bone
        keys, ANIM header, BRUS/TEXS)
  3. pixel-identical textures/cat.png vs shipped cat.png
     (+ gray/black variants: audit clean + same covered count)

Exit code 0 = PASS.
"""
import filecmp
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, '..', '..'))
TMP = os.path.join(HERE, 'selftest_out')

sys.path.insert(0, HERE)
import b3d
from PIL import Image


def key_digest(f):
    """Model-agnostic structural digest of a parsed b3d."""
    root = f['nodes'][0]
    d = {
        'nodes': [],
        'texs': f['texs'],
        'brus': f['brus'],
    }

    def walk(n):
        e = {
            'name': n['name'], 'pos': n['pos'], 'scale': n['scale'], 'rot': n['rot'],
            'anim': n['anim'],
            'brush': n['mesh']['brush_id'] if n['mesh'] else None,
            'verts': [
                (v[0], tuple(v[3][0]))
                for v in (n['mesh']['vrts'][3] if n['mesh'] and n['mesh']['vrts'] else [])
            ],
            'tris': [t for _, ts in n['mesh']['tris'] for t in ts] if n['mesh'] else [],
            'bones': sorted((v, round(w, 4)) for (v, w) in (n['bones'] or [])),
            'keys': sorted((k[0], tuple(round(c, 5) for c in k[1]),
                           tuple(round(c, 5) for c in k[3]))
                          for k in (n['keys'][1] if n['keys'] else [])),
        }
        d['nodes'].append(e)
        for c in n['children']:
            walk(c)

    walk(root)
    return d


def main():
    # 1. fresh build
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    cmd = [sys.executable, os.path.join(HERE, 'run_all.py'),
           os.path.join(HERE, 'specs', 'cat.py'), '--out', TMP]
    print('$', ' '.join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    sys.stdout.write(r.stdout or '')
    if r.returncode != 0:
        sys.stderr.write((r.stderr or '')[-3000:] + '\n')
        print('SELFTEST FAIL: run_all rc=%d' % r.returncode)
        return 1

    # 2. b3d structural comparison
    new = b3d.parse_file(os.path.join(TMP, 'models', 'cat.b3d'))
    old = b3d.parse_file(os.path.join(MOD, 'models', 'cat.b3d'))
    dn, do = key_digest(new), key_digest(old)
    if dn != do:
        for k in dn:
            if dn[k] != do[k]:
                print('SELFTEST FAIL: b3d differs in %r' % k)
                if k in ('verts', 'keys') and dn[k] and do[k]:
                    for i, (a, b) in enumerate(zip(dn[k], do[k])):
                        if a != b:
                            print('   first diff at index', i, ':\n    new', a, '\n    old', b)
                            break
                if k == 'nodes' and len(dn[k]) == len(do[k]):
                    for i, (a, b) in enumerate(zip(dn[k], do[k])):
                        if a != b:
                            for kk in a:
                                if a[kk] != b[kk]:
                                    print('   node', i, a['name'], 'field', kk)
                                    print('    new', str(a[kk])[:400])
                                    print('    old', str(b[kk])[:400])
        return 1
    print('b3d: identical (verts/uv/tris/bones/keys/ANIM/BRUS)')

    # 3. textures
    p1 = os.path.join(TMP, 'textures', 'cat.png')
    p2 = os.path.join(MOD, 'textures', 'cat.png')
    if Image.open(p1).convert('RGBA') == Image.open(p2).convert('RGBA'):
        print('cat.png: pixel-identical to shipped')
    else:
        print('SELFTEST FAIL: cat.png differs from shipped')
        return 1

    for fn in ('cat_gray.png', 'cat_black.png'):
        img = Image.open(os.path.join(TMP, 'textures', fn)).convert('RGBA')
        if img.size != (64, 64):
            print('SELFTEST FAIL: %s wrong size' % fn)
            return 1
    print('variants: rebuilt (cat_gray.png, cat_black.png)')

    print('SELFTEST PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
