"""Minimal BB3D (chunked Blitz3D b3d) parser - generic, no model assumptions.

Parses .b3d files: TEXS/BRUS datablocks, node tree, meshes (verts/uv/tris),
bone weight tables, KEYS (animation) and ANIM headers.
"""
import struct


class R:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def u8(self):
        v = self.data[self.pos]; self.pos += 1; return v

    def u16(self):
        v = struct.unpack_from('<H', self.data, self.pos)[0]; self.pos += 2; return v

    def i32(self):
        v = struct.unpack_from('<i', self.data, self.pos)[0]; self.pos += 4; return v

    def f32(self):
        v = struct.unpack_from('<f', self.data, self.pos)[0]; self.pos += 4; return v

    def vec3(self):
        return (self.f32(), self.f32(), self.f32())

    def vec4(self):
        return (self.f32(), self.f32(), self.f32(), self.f32())

    def cstr(self):
        start = self.pos
        while self.data[self.pos] != 0:
            self.pos += 1
        s = self.data[start:self.pos].decode('utf-8', 'replace')
        self.pos += 1
        return s

    def chunk(self):
        tag = self.data[self.pos:self.pos + 4].decode('latin1')
        self.pos += 4
        length = self.i32()
        end = self.pos + length
        return tag, self, end

    def seek(self, p):
        self.pos = p


def parse_file(path):
    data = open(path, 'rb').read()
    r = R(data)
    tag, cr, end = r.chunk()
    assert tag == 'BB3D', tag
    version = r.i32()
    result = {'version': version, 'texs': [], 'brus': [], 'nodes': []}

    while r.pos < end:
        tag, cr, e = r.chunk()
        if tag == 'TEXS':
            while cr.pos < e:
                name = cr.cstr()
                flags = cr.i32(); blend = cr.i32()
                x = cr.f32(); y = cr.f32(); xs = cr.f32(); ys = cr.f32(); rot = cr.f32()
                result['texs'].append((name, flags, blend, (x, y, xs, ys, rot)))
        elif tag == 'BRUS':
            n_texs = cr.i32()
            while cr.pos < e:
                name = cr.cstr()
                rgba = cr.vec4(); shin = cr.f32()
                blend = cr.i32(); fx = cr.i32()
                tids = [cr.i32() for _ in range(n_texs)]
                result['brus'].append((name, rgba, shin, blend, fx, tids))
        elif tag == 'NODE':
            node = parse_node(cr, e)
            result['nodes'].append(node)
    return result


def parse_node(r, end):
    name = r.cstr()
    pos = r.vec3(); scale = r.vec3(); rot = r.vec4()
    node = {'name': name, 'pos': pos, 'scale': scale, 'rot': rot,
            'mesh': None, 'bones': None, 'keys': None, 'anim': None, 'children': []}
    while r.pos < end:
        tag, cr, e = r.chunk()
        if tag == 'MESH':
            node['mesh'] = parse_mesh(cr, e)
        elif tag == 'BONE':
            bones = []
            while cr.pos < e:
                vid = cr.i32(); w = cr.f32()
                bones.append((vid, w))
            node['bones'] = bones
        elif tag == 'KEYS':
            flags = cr.i32()
            keys = []
            while cr.pos < e:
                frame = cr.i32()
                p = cr.vec3() if flags & 1 else None
                s = cr.vec3() if flags & 2 else None
                rotq = cr.vec4() if flags & 4 else None
                keys.append((frame, p, s, rotq))
            node['keys'] = (flags, keys)
        elif tag == 'ANIM':
            flags = cr.i32(); frames = cr.i32(); fps = cr.f32()
            node['anim'] = (flags, frames, fps)
        elif tag == 'NODE':
            node['children'].append(parse_node(cr, e))
    return node


def parse_mesh(r, end):
    brush_id = r.i32()
    mesh = {'brush_id': brush_id, 'vrts': None, 'tris': []}
    while r.pos < end:
        tag, cr, e = r.chunk()
        if tag == 'VRTS':
            flags = cr.i32(); sets = cr.i32(); size = cr.i32()
            verts = []
            while cr.pos < e:
                xyz = cr.vec3()
                n = cr.vec3() if flags & 1 else None
                c = cr.vec4() if flags & 2 else None
                uvs = []
                for i in range(sets):
                    uvs.append(tuple(cr.f32() for _ in range(size)))
                verts.append((xyz, n, c, uvs))
            mesh['vrts'] = (flags, sets, size, verts)
        elif tag == 'TRIS':
            bid = cr.i32()
            tris = []
            while cr.pos < e:
                tris.append((cr.i32(), cr.i32(), cr.i32()))
            mesh['tris'].append((bid, tris))
    return mesh


def find_node(n, name):
    """Depth-first search for a node by name."""
    if n['name'] == name:
        return n
    for c in n['children']:
        r = find_node(c, name)
        if r:
            return r
    return None


def bone_nodes(root):
    """All descendant nodes that carry a BONE table."""
    out = []
    def walk(n):
        if n['bones']:
            out.append(n)
        for c in n['children']:
            walk(c)
    walk(root)
    return out


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        sys.exit("usage: b3d.py <file.b3d>")
    f = parse_file(path)
    print("VERSION", f['version'])
    print("TEXS", f['texs'])
    for b in f['brus']:
        print("BRUS", b)

    def walk(n, depth=0):
        ind = '  ' * depth
        anim = " ANIM(frames=%s,fps=%s)" % (n['anim'][1], n['anim'][2]) if n['anim'] else ""
        keys = ""
        if n['keys']:
            frames = [k[0] for k in n['keys'][1]]
            keys = " KEYS(flags=%s,n=%s,frames %s..%s)" % (n['keys'][0], len(frames), min(frames), max(frames))
        meshinfo = ""
        if n['mesh'] and n['mesh']['vrts']:
            m = n['mesh']
            meshinfo = " MESH(v=%s,t=%s,brush_id=%s)" % (
                len(m['vrts'][3]), sum(len(t[1]) for t in m['tris']), m['brush_id'])
        bones = " BONE(n=%s)" % len(n['bones']) if n['bones'] else ""
        print(ind, "NODE", repr(n['name']), "pos", n['pos'], "scale", n['scale'],
              anim, keys, meshinfo, bones)
        for c in n['children']:
            walk(c, depth + 1)

    print("NODES:", len(f['nodes']))
    for n in f['nodes']:
        walk(n)
