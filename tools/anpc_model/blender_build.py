"""Headless Blender build: spec -> mesh + armature + animation -> .b3d.

Run via:  blender --background --python blender_build.py \
              --spec <spec_module.py> --layout <layout.json> --out <file.b3d>

The spec module (pure python) provides:
    SPEC = {
      'name': str,                 # mesh/object/material base name
      'atlas_size': int,
      'parts': [...], 'bones': [...],   # see box_uv / spec doc
      'animation': {'frames': N, 'fps': fps},
      ...
    }
    pose(b3d_frame) -> {bone: ((lx, ly, lz), (rx, ry, rz))}   # optional;
        1-based b3d frame; bones not returned stay at rest (zero).

Blender 5.x gotchas handled here (do not "simplify"):
  * Pose-bone Vectors have no keyframe_insert in the exec context - key via
    arm.keyframe_insert(data_path='pose.bones["B"].location', frame=f).
  * Set pb.rotation_mode = 'XYZ' before writing rotation_euler.
  * LINEAR must be set explicitly; fcurves live at
    action.layers[].strips[].channelbags[].fcurves (no action.fcurves).
  * Exporter: material must have NO image node (BRUS tex [-1]) - the skin is
    supplied by the entity's textures property, so leave it untextured.
"""
import argparse
import importlib.util
import json
import os
import sys

import bpy


def load_spec(path):
    path = os.path.abspath(path)
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_mesh(spec, layout, verts, uvs, quads, groups):
    name = spec.get('object_name') or spec['name']
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], quads)
    me.update()
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uv.data[li].uv = uvs[vi]
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    gm = {}
    for i, gname in enumerate(groups):
        if gname not in gm:
            gm[gname] = obj.vertex_groups.new(name=gname)
    for i, gname in enumerate(groups):
        gm[gname].add([i], 1.0, 'REPLACE')
    return obj


def build_armature(bones, mesh_obj, arm_name):
    arm_data = bpy.data.armatures.new(arm_name)
    arm_obj = bpy.data.objects.new(arm_name, arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    by_name = {}
    for b in bones:
        e = eb.new(b['name'])
        e.head = b['head']
        e.tail = b['tail']
        by_name[b['name']] = e
    for b in bones:
        if b.get('parent'):
            by_name[b['name']].parent = by_name[b['parent']]
    bpy.ops.object.mode_set(mode='OBJECT')
    mod = mesh_obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm_obj
    return arm_obj


def build_animation(arm, anim, pose_fn, bone_names):
    frames = anim['frames']
    action = bpy.data.actions.new(arm.name + 'Anim')
    arm.animation_data_create()
    arm.animation_data.action = action
    for f in range(1, frames + 1):
        bpy.context.scene.frame_set(f)
        pose = pose_fn(f) if pose_fn else {}
        for b in bone_names:
            pb = arm.pose.bones[b]
            pb.rotation_mode = 'XYZ'
            loc, rot = pose.get(b, ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
            pb.location = loc
            pb.rotation_euler = rot
            arm.keyframe_insert(data_path='pose.bones["%s"].location' % b, frame=f)
            arm.keyframe_insert(data_path='pose.bones["%s"].rotation_euler' % b, frame=f)
    for layer in action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                for fc in cb.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
    bpy.context.scene.frame_set(1)
    return action


def make_material(spec, mesh_obj):
    mat = bpy.data.materials.new(spec.get('object_name') or spec['name'])
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)
    return mat


def ensure_b3d_exporter():
    """The io_scene_b3d addon may not load in a clean headless session."""
    try:
        bpy.ops.export_scene.b3d  # raises if unregistered
        return
    except AttributeError:
        pass
    addon = os.environ.get('B3D_ADDON') or r'C:\Users\hecto\AppData\Roaming\Blender Foundation\Blender\5.3\scripts\addons\io_scene_b3d-master'
    path = os.path.join(addon, 'export_b3d.py')
    if not os.path.exists(path):
        raise RuntimeError('b3d exporter not found and fallback missing at %s' % path)
    s = importlib.util.spec_from_file_location('io_scene_b3d_export', path)
    mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(mod)
    if hasattr(mod, 'register'):
        mod.register()


def _patched_anim_end(armature):
    """Drop-in replacement for the addon's getArmatureAnimationEnd.

    Blender 5.x removed Action.fcurves; keyframes live at
    action.layers[].strips[].channelbags[].fcurves. The hasattr branch
    keeps this working on Blender 4.x too.
    """
    end_frame = 1
    ad = armature.animation_data
    if ad and ad.action:
        action = ad.action
        if hasattr(action, 'fcurves'):
            curves = list(action.fcurves)
        else:
            curves = []
            for layer in action.layers:
                for strip in layer.strips:
                    for bag in getattr(strip, 'channelbags', ()):
                        curves.extend(bag.fcurves)
        for fc in curves:
            if 'pose' in fc.data_path and fc.keyframe_points:
                end_frame = max(end_frame, fc.keyframe_points[-1].co[0])
    if ad:
        for nla_track in ad.nla_tracks:
            if len(nla_track.strips) > 0:
                end_frame = max(end_frame, nla_track.strips[-1].frame_end)
    return end_frame


def patch_b3d_exporter():
    """Patch the io_scene_b3d addon IN MEMORY for the Blender 5.x Action API.

    The addon's getArmatureAnimationEnd reads action.fcurves (pre-4.0), which
    5.x removed -> AttributeError during export. We swap the function in the
    loaded module; the addon file on disk stays untouched.

    The export operator lazy-imports its export_b3d submodule on first use,
    so pre-import it through the package and patch that module object too.
    Returns the list of module names patched.
    """
    import importlib
    patched = []
    for mod in list(sys.modules.values()):
        d = getattr(mod, '__dict__', None)
        if d is not None and 'getArmatureAnimationEnd' in d:
            mod.getArmatureAnimationEnd = _patched_anim_end
            patched.append(getattr(mod, '__name__', '?'))
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        nm = getattr(mod, '__name__', '')
        if 'b3d' in nm.lower() and hasattr(mod, '__path__'):
            try:
                sub = importlib.import_module(nm + '.export_b3d')
                sub.getArmatureAnimationEnd = _patched_anim_end
                patched.append(sub.__name__)
            except Exception as e:
                print('B3D_PATCH: pre-import of %s.export_b3d failed: %r' % (nm, e))
    return patched


def export_b3d(mesh_obj, out_path):
    ensure_b3d_exporter()
    patched = patch_b3d_exporter()
    print('B3D_PATCH', patched)
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.context.scene.frame_set(1)
    res = bpy.ops.export_scene.b3d(
        filepath=out_path,
        use_local_transform=False,
        export_ambient=False,
        enable_mipmaps=False,
        use_selection=True,
        use_visible=False,
        use_collection=False,
        object_mesh=True,
        object_armature=True,
        object_light=False,
        object_camera=False,
        export_texcoords=True,
        export_materials=True,
        export_normals=True,
        export_colors=False,
    )
    return res


def save_blend(mesh_obj, out_path):
    """Save the built scene as a .blend next to the .b3d.

    The .b3d is a baked snapshot (rest verts + keys); the .blend is the
    editable source (mesh, armature, keyframes) for humans tweaking the
    model later. Same base name as the .b3d.
    """
    blend_path = os.path.splitext(out_path)[0] + '.blend'
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    return blend_path


def get_script_args():
    """Args for this script from sys.argv.

    Blender 5.x passes the full command line (blender.exe + every flag); the
    script's own args follow the --python <script> pair. Direct
    `python blender_build.py ...` sees only its own args.
    """
    argv = sys.argv
    for flag in ('--python', '--python-text', '--py', '--py-text'):
        if flag in argv:
            i = argv.index(flag)
            return argv[i + 2:]
    return argv[1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', default=None)
    ap.add_argument('--layout', default=None)
    ap.add_argument('--out', default=None)
    args = ap.parse_args(get_script_args())

    # Env vars win: run_all passes paths this way because Blender 5.x
    # swallows unknown --flags after --python and tries to load them as files.
    if os.environ.get('ANPC_SPEC'):
        args.spec = os.environ['ANPC_SPEC']
        args.layout = os.environ['ANPC_LAYOUT']
        args.out = os.environ['ANPC_OUT']
    if not (args.spec and args.layout and args.out):
        ap.error('need --spec/--layout/--out or ANPC_SPEC/ANPC_LAYOUT/ANPC_OUT')

    mod = load_spec(args.spec)
    spec = mod.SPEC
    ldata = json.load(open(args.layout))
    if isinstance(ldata, dict) and 'regions' in ldata:
        size = ldata['size']
        layout = {k: tuple(v) for k, v in ldata['regions'].items()}
    else:
        layout = {k: tuple(v) for k, v in ldata.items()}
        size = max(max(x + w, y + h) for (x, y, w, h) in layout.values())
    for (x, y, w, h) in layout.values():
        assert 0 <= x and x + w <= size and 0 <= y and y + h <= size

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import box_uv
    spec = dict(spec)
    spec['atlas_size'] = size
    parts_data, verts, uvs, quads, groups = box_uv.build_mesh(spec, layout)

    # --- clean scene -----------------------------------------------------
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions,
                 bpy.data.materials):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)
    sc = bpy.context.scene
    frames = spec['animation']['frames']
    sc.frame_start = 1
    sc.frame_end = frames
    sc.frame_set(1)

    mesh_obj = build_mesh(spec, layout, verts, uvs, quads, groups)
    bones = spec['bones']
    arm = build_armature(bones, mesh_obj, spec.get('armature', spec['name'] + 'Arm'))
    pose_fn = getattr(mod, 'pose', None)
    action = build_animation(arm, spec['animation'], pose_fn, [b['name'] for b in bones])
    make_material(spec, mesh_obj)
    blend_path = save_blend(mesh_obj, args.out)
    export_b3d(mesh_obj, args.out)

    print('B3D_OK', json.dumps({
        'out': args.out,
        'blend': blend_path,
        'verts': len(mesh_obj.data.vertices),
        'faces': len(mesh_obj.data.polygons),
        'bones': [b.name for b in arm.data.bones],
        'frames': frames,
        'fps': spec['animation']['fps'],
        'vgroups': [g.name for g in mesh_obj.vertex_groups],
        'uv_layers': [l.name for l in mesh_obj.data.uv_layers],
        'modifiers': [m.name + ':' + m.type for m in mesh_obj.modifiers],
    }))


if __name__ == '__main__':
    main()
