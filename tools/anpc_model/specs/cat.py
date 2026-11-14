"""Cat spec for the anpc_dev cat - the reference/regression spec.

Ported from the original cat_work one-offs (cat_geo.py, cat_build.py,
make_cat_skin.py). selftest.py rebuilds from this spec and compares
structurally against the shipped models/cat.b3d + textures/cat.png.

Coordinate conventions:
  * Blender Z-up. Cat faces +Y, +X is the cat's right. Feet at z=0.
  * 1 model unit = 0.1 block.
  * Skin: 64x64 px, 4 px per model unit (head front/back squished to
    10 px wide - intentional, see face_px).
  * Animation: 221 b3d frames (1..221); anpc anim frame = b3d frame - 1.
    Clips below are 0-based anpc frames (like npc.model.register_animation).
"""
import math

SPEC = {
    "name": "cat",
    # Blender mesh-object/material name (the b3d node name). Differs from the
    # file base name on purpose: the shipped cat.b3d says 'Cat'.
    "object_name": "Cat",
    "armature": "CatArm",
    "px_per_unit": 4.0,
    "atlas": 64,
    # Explicit layout (hand-tuned; auto-packing would also work but this
    # keeps the shipped skin byte-identical).
    "layout": {
        # head (3.0 x 2.0 x 2.5)
        "head_front": (0, 0, 10, 10),
        "head_back": (10, 0, 10, 10),
        "head_left": (20, 0, 8, 10),
        "head_right": (28, 0, 8, 10),
        "head_top": (36, 0, 12, 8),
        "head_bottom": (48, 0, 12, 8),
        # ears (0.75^3, shared between both ears)
        "ear_top": (0, 10, 3, 3),
        "ear_back": (3, 10, 3, 3),
        "ear_left": (6, 10, 3, 3),
        "ear_bottom": (0, 13, 3, 3),
        "ear_front": (3, 13, 3, 3),
        "ear_right": (6, 13, 3, 3),
        # tail segments (0.75^3 each, shared by all 3 -> ringed tail)
        "tail_top": (10, 10, 3, 3),
        "tail_back": (13, 10, 3, 3),
        "tail_left": (16, 10, 3, 3),
        "tail_bottom": (10, 13, 3, 3),
        "tail_front": (13, 13, 3, 3),
        "tail_right": (16, 13, 3, 3),
        # body (2.5 x 4.0 x 2.5)
        "body_top": (0, 16, 10, 16),
        "body_bottom": (10, 16, 10, 16),
        "body_left": (20, 16, 16, 10),
        "body_right": (20, 26, 16, 10),
        "body_front": (36, 16, 10, 10),
        "body_back": (46, 16, 10, 10),
        # legs (1.25 x 1.25 x 2.0, shared between all four)
        "leg_front": (0, 36, 5, 8),
        "leg_back": (5, 36, 5, 8),
        "leg_left": (10, 36, 5, 8),
        "leg_right": (15, 36, 5, 8),
        "leg_top": (20, 36, 5, 5),
        "leg_bottom": (25, 36, 5, 5),
    },
    "parts": [
        {"name": "Body", "center": (0.0, 0.0, 3.25), "size": (2.5, 4.0, 2.5),
         "group": "Body",
         "faces": {"+Y": "body_front", "-Y": "body_back", "+X": "body_right",
                   "-X": "body_left", "+Z": "body_top", "-Z": "body_bottom"}},
        {"name": "Head", "center": (0.0, 3.0, 4.75), "size": (3.0, 2.0, 2.5),
         "group": "Head",
         # 10 px wide instead of the derived 12: deliberate 1.2x horizontal
         # squish of the face - do not "fix".
         "face_px": {"+Y": (10, 10), "-Y": (10, 10)},
         "faces": {"+Y": "head_front", "-Y": "head_back", "+X": "head_right",
                   "-X": "head_left", "+Z": "head_top", "-Z": "head_bottom"}},
        {"name": "Ear_L", "center": (-0.75, 3.0, 6.375), "size": (0.75, 0.75, 0.75),
         "group": "Head",
         "faces": {"+Y": "ear_front", "-Y": "ear_back", "+X": "ear_right",
                   "-X": "ear_left", "+Z": "ear_top", "-Z": "ear_bottom"}},
        {"name": "Ear_R", "center": (0.75, 3.0, 6.375), "size": (0.75, 0.75, 0.75),
         "group": "Head",
         "faces": {"+Y": "ear_front", "-Y": "ear_back", "+X": "ear_right",
                   "-X": "ear_left", "+Z": "ear_top", "-Z": "ear_bottom"}},
        {"name": "Leg_FL", "center": (-0.75, 1.25, 1.0), "size": (1.25, 1.25, 2.0),
         "group": "Leg_FL",
         "faces": {"+Y": "leg_front", "-Y": "leg_back", "+X": "leg_right",
                   "-X": "leg_left", "+Z": "leg_top", "-Z": "leg_bottom"}},
        {"name": "Leg_FR", "center": (0.75, 1.25, 1.0), "size": (1.25, 1.25, 2.0),
         "group": "Leg_FR",
         "faces": {"+Y": "leg_front", "-Y": "leg_back", "+X": "leg_right",
                   "-X": "leg_left", "+Z": "leg_top", "-Z": "leg_bottom"}},
        {"name": "Leg_BL", "center": (-0.75, -1.25, 1.0), "size": (1.25, 1.25, 2.0),
         "group": "Leg_BL",
         "faces": {"+Y": "leg_front", "-Y": "leg_back", "+X": "leg_right",
                   "-X": "leg_left", "+Z": "leg_top", "-Z": "leg_bottom"}},
        {"name": "Leg_BR", "center": (0.75, -1.25, 1.0), "size": (1.25, 1.25, 2.0),
         "group": "Leg_BR",
         "faces": {"+Y": "leg_front", "-Y": "leg_back", "+X": "leg_right",
                   "-X": "leg_left", "+Z": "leg_top", "-Z": "leg_bottom"}},
        {"name": "Tail_1", "center": (0.0, -2.4, 3.375), "size": (0.75, 0.75, 0.75),
         "group": "Tail",
         "faces": {"+Y": "tail_front", "-Y": "tail_back", "+X": "tail_right",
                   "-X": "tail_left", "+Z": "tail_top", "-Z": "tail_bottom"}},
        {"name": "Tail_2", "center": (0.0, -2.4, 4.125), "size": (0.75, 0.75, 0.75),
         "group": "Tail",
         "faces": {"+Y": "tail_front", "-Y": "tail_back", "+X": "tail_right",
                   "-X": "tail_left", "+Z": "tail_top", "-Z": "tail_bottom"}},
        {"name": "Tail_3", "center": (0.0, -2.4, 4.875), "size": (0.75, 0.75, 0.75),
         "group": "Tail",
         "faces": {"+Y": "tail_front", "-Y": "tail_back", "+X": "tail_right",
                   "-X": "tail_left", "+Z": "tail_top", "-Z": "tail_bottom"}},
    ],
    "bones": [
        {"name": "Body", "head": (0.0, 0.0, 2.0), "tail": (0.0, 0.0, 4.5), "parent": None},
        {"name": "Head", "head": (0.0, 3.0, 3.5), "tail": (0.0, 3.0, 6.0), "parent": "Body"},
        {"name": "Tail", "head": (0.0, -2.4, 3.0), "tail": (0.0, -2.4, 5.25), "parent": "Body"},
        {"name": "Leg_FL", "head": (-0.75, 1.25, 2.0), "tail": (-0.75, 1.25, 0.0), "parent": "Body"},
        {"name": "Leg_FR", "head": (0.75, 1.25, 2.0), "tail": (0.75, 1.25, 0.0), "parent": "Body"},
        {"name": "Leg_BL", "head": (-0.75, -1.25, 2.0), "tail": (-0.75, -1.25, 0.0), "parent": "Body"},
        {"name": "Leg_BR", "head": (0.75, -1.25, 2.0), "tail": (0.75, -1.25, 0.0), "parent": "Body"},
    ],
    "animation": {
        "frames": 221,
        "fps": 60,
        # 0-based anpc anim frames (b3d KEYS frame = anim frame + 1):
        "clips": [
            {"name": "stand", "start": 0, "end": 79, "speed": 30, "loop": True},
            {"name": "lay", "start": 162, "end": 166, "loop": True},
            {"name": "walk", "start": 168, "end": 187, "loop": True},
            {"name": "mine_once", "start": 192, "end": 196, "speed": 15,
             "loop": False, "after": "stand"},
        ],
    },
    "palettes": {
        "orange": {
            "FUR": (228, 158, 86), "FUR_L": (246, 199, 133),
            "STRIPE": (138, 77, 35), "CREAM": (250, 243, 228),
            "PINK": (235, 158, 162), "NOSE": (216, 108, 120),
            "EYE": (62, 47, 34),
        },
        "gray": {
            "FUR": (148, 152, 160), "FUR_L": (180, 184, 192),
            "STRIPE": (74, 78, 92), "CREAM": (238, 238, 244),
            "PINK": (235, 158, 162), "NOSE": (150, 110, 115),
            "EYE": (74, 96, 64),
        },
        "black": {
            "FUR": (42, 40, 44), "FUR_L": (58, 55, 60),
            "STRIPE": (24, 23, 26), "CREAM": (235, 232, 228),
            "PINK": (235, 158, 162), "NOSE": (150, 105, 115),
            "EYE": (214, 180, 84),
        },
    },
}

# Palette name order for run_all: first -> <name>.png
PALETTE_ORDER = ["orange", "gray", "black"]

BONE_NAMES = ['Body', 'Head', 'Tail', 'Leg_FL', 'Leg_FR', 'Leg_BL', 'Leg_BR']

# ---------------------------------------------------------------- pose ------
# Pose model: local-space location offset + Euler XYZ per bone, per b3d frame
# (1-based). Frames outside the clips are the rest pose (all zeros).
# b3d clip ranges: stand 1..80, lay 163..167, walk 169..188, mine_once 193..197.


def _pose_stand(t):
    TAU = 2.0 * math.pi
    return {
        'Body': ((0.0, 0.12 * math.sin(TAU * t / 80.0), 0.0),
                 (0.05 * math.sin(TAU * t / 40.0), 0.0, 0.0)),
        'Head': ((0.0, 0.0, 0.0),
                 (0.06 * math.sin(TAU * t / 40.0 + 1.0), 0.0,
                  0.18 * math.sin(TAU * t / 80.0))),
        'Tail': ((0.0, 0.0, 0.0),
                 (0.20 * math.sin(TAU * t / 40.0), 0.0,
                  0.25 * math.sin(TAU * t / 40.0 + math.pi / 2.0))),
    }


def _pose_lay(t):
    TAU = 2.0 * math.pi
    # Roll the body ~83 deg onto the left (-X) side and drop it to the floor;
    # upper-side legs (FR/BR) counter-roll down, ground-side legs (FL/BL)
    # fold up, head turns so the face is up. (Empirically tuned values.)
    return {
        'Body': ((0.0, -0.66, 0.0),
                 (0.0, 0.0, 1.45 + 0.02 * math.sin(TAU * t / 4.0))),
        'Head': ((0.0, 0.0, 0.0), (0.0, 0.0, -1.57)),
        'Tail': ((0.0, 0.0, 0.0), (-1.40, 0.0, -0.55)),
        'Leg_FR': ((0.0, 0.0, 0.0), (0.0, 0.0, 1.57)),
        'Leg_BR': ((0.0, 0.0, 0.0), (0.0, 0.0, 1.57)),
        'Leg_FL': ((0.0, 0.0, 0.0), (3.14, 0.0, 0.0)),
        'Leg_BL': ((0.0, 0.0, 0.0), (3.14, 0.0, 0.0)),
    }


def _pose_walk(t):
    TAU = 2.0 * math.pi
    swing = math.sin(TAU * t / 20.0)
    S = 0.5
    return {
        'Body': ((0.0, 0.08 * math.sin(TAU * 2.0 * t / 20.0), 0.0),
                 (0.06 * math.sin(TAU * 2.0 * t / 20.0), 0.0, 0.0)),
        'Head': ((0.0, 0.0, 0.0),
                 (0.05 * math.sin(TAU * 2.0 * t / 20.0), 0.0,
                  0.06 * math.sin(TAU * t / 20.0))),
        'Tail': ((0.0, 0.15, 0.0),
                 (0.35, 0.0, 0.18 * math.sin(TAU * t / 20.0))),
        'Leg_FL': ((0.0, 0.0, 0.0), (S * swing, 0.0, 0.0)),
        'Leg_BR': ((0.0, 0.0, 0.0), (S * swing, 0.0, 0.0)),
        'Leg_FR': ((0.0, 0.0, 0.0), (-S * swing, 0.0, 0.0)),
        'Leg_BL': ((0.0, 0.0, 0.0), (-S * swing, 0.0, 0.0)),
    }


def _pose_mine(t):
    # positive local X on the head tilts it backwards -> negate for a dip
    dip = 0.45 * math.sin(math.pi * t / 4.0)
    return {'Head': ((0.0, 0.0, 0.0), (-dip, 0.0, 0.0))}


def pose(f):
    """{bone: (local_location, local_euler_xyz)} for b3d frame f (1-based)."""
    p = {b: ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)) for b in BONE_NAMES}
    if 1 <= f <= 80:
        p.update(_pose_stand(f - 1))
    elif 163 <= f <= 167:
        p.update(_pose_lay(f - 163))
    elif 169 <= f <= 188:
        p.update(_pose_walk(f - 169))
    elif 193 <= f <= 197:
        p.update(_pose_mine(f - 193))
    return p


# ---------------------------------------------------------------- skin ------
# Painter contract: draw the canonical faces (front, back, left, top, bottom)
# of every part. Right faces are auto-filled as the flip of the left face.

def paint(A):
    STRIPE, CREAM = A.palette["STRIPE"], A.palette["CREAM"]
    PINK, NOSE, EYE = A.palette["PINK"], A.palette["NOSE"], A.palette["EYE"]

    # --- head: front (the face), back, left, top, bottom -------------------
    g, x, y, w, h = A.grid("head_front")
    A.band(g, 1, 2, [4, 5], STRIPE)        # small forehead marking
    A.rows_of(g, 4, [2, 3], EYE)           # right eye
    A.rows_of(g, 4, [6, 7], EYE)           # left eye
    A.rows_of(g, 6, [4, 5], NOSE)
    A.band(g, 7, 7, range(3, 7), CREAM)    # muzzle
    A.band(g, 8, 8, range(2, 8), CREAM)
    A.band(g, 9, 9, range(1, 9), CREAM)    # chin
    A.put("head_front", g)

    g, x, y, w, h = A.grid("head_back")
    A.band(g, 0, 0, [4, 5], STRIPE)        # back of the tabby "M"
    A.band(g, 1, 1, range(3, 7), STRIPE)
    A.band(g, 2, 2, [4, 5], STRIPE)
    A.put("head_back", g)

    g, x, y, w, h = A.grid("head_left")
    A.band(g, 0, 4, [5, 6], STRIPE)        # back-of-head stripe
    A.rows_of(g, 4, [1, 2], EYE)           # eye toward the front
    A.band(g, 7, 9, [0, 1], CREAM)         # white muzzle/chin at the front
    A.put("head_left", g)

    g, x, y, w, h = A.grid("head_top")
    A.band(g, 0, 0, range(4, 8), STRIPE)   # crown band
    A.band(g, 1, 3, [5, 6], STRIPE)        # nape center stripe
    A.band(g, 5, 5, [3, 4, 7, 8], STRIPE)  # tabby "M" (front = bottom rows)
    A.band(g, 6, 6, range(4, 8), STRIPE)
    A.band(g, 7, 7, [5, 6], STRIPE)
    A.put("head_top", g)

    g, x, y, w, h = A.grid("head_bottom")
    A.band(g, 0, 1, range(3, 9), CREAM)    # chin under the front (row 0 = front)
    A.put("head_bottom", g)

    # --- ears ----------------------------------------------------------------
    A.put("ear_top", A.grid("ear_top")[0])                             # fur tip
    A.put("ear_back", A.grid("ear_back")[0])                           # fur
    g, x, y, w, h = A.grid("ear_front")
    A.band(g, 1, 2, range(3), PINK)
    A.put("ear_front", g)
    g, x, y, w, h = A.grid("ear_bottom")
    A.full_row(g, 0, A.FUR)
    A.band(g, 1, 2, range(3), PINK)
    A.put("ear_bottom", g)
    g, x, y, w, h = A.grid("ear_left")
    A.band(g, 1, 2, range(3), PINK)
    A.put("ear_left", g)

    # --- tail (shared by all 3 segments -> ringed tail) ----------------------
    for face in ("tail_top", "tail_back", "tail_left", "tail_bottom", "tail_front"):
        g, x, y, w, h = A.grid(face)
        A.full_row(g, 1, STRIPE)                    # dark ring row
        A.put(face, g)

    # --- body -----------------------------------------------------------------
    g, x, y, w, h = A.grid("body_top")
    A.band(g, 2, 3, range(10), STRIPE)              # transverse back bands
    A.band(g, 6, 7, range(10), STRIPE)
    A.band(g, 11, 12, range(10), STRIPE)
    A.put("body_top", g)

    g, x, y, w, h = A.grid("body_bottom")
    A.band(g, 4, 15, range(10), CREAM)              # belly (rows 0-3 = rump)
    A.put("body_bottom", g)

    g, x, y, w, h = A.grid("body_left")             # column 0 = front
    for r in range(1, 5):
        A.rows_of(g, r, [3, 4, 8, 9, 13, 14], STRIPE)   # side stripe bands
    A.band(g, 5, 5, range(0, 4), CREAM)             # white chest (front)
    A.band(g, 6, 6, range(0, 5), CREAM)
    A.band(g, 7, 8, range(0, 6), CREAM)
    A.band(g, 9, 9, range(0, 7), CREAM)
    A.put("body_left", g)

    g, x, y, w, h = A.grid("body_front")
    A.band(g, 5, 5, range(3, 7), CREAM)             # chest (row 9 = ground)
    A.band(g, 6, 6, range(2, 8), CREAM)
    A.band(g, 7, 7, range(1, 9), CREAM)
    A.band(g, 8, 9, range(10), CREAM)
    A.put("body_front", g)

    g, x, y, w, h = A.grid("body_back")
    A.band(g, 0, 0, [4, 5], STRIPE)                 # rump, tail-base shade
    A.band(g, 1, 1, range(3, 7), STRIPE)
    A.put("body_back", g)

    # --- legs (shared between all four) ----------------------------------------
    for face in ("leg_front", "leg_back", "leg_left"):
        g, x, y, w, h = A.grid(face)
        A.band(g, 5, 7, range(5), CREAM)            # white paws (bottom)
        A.put(face, g)
    A.put("leg_top", A.grid("leg_top")[0])
    g, x, y, w, h = A.grid("leg_bottom")
    A.full_row(g, 0, CREAM)
    A.full_row(g, 1, CREAM)
    A.full_row(g, 2, CREAM)                         # paw sole
    A.put("leg_bottom", g)


def icon(pal):
    """16x16 spawner icon: front-facing cat head + shoulders."""
    from PIL import Image
    FUR, PINK, EYE = pal["FUR"], pal["PINK"], pal["EYE"]
    NOSE, CREAM = pal["NOSE"], pal["CREAM"]
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))

    def iput(cx, cy, col):
        im.putpixel((cx, cy), col + (255,))

    for cx in (3, 4, 11, 12):
        iput(cx, 0, FUR)
    for cx in (2, 3, 4, 5, 10, 11, 12, 13):
        iput(cx, 1, FUR)
    iput(3, 1, PINK)
    iput(12, 1, PINK)
    for r in range(2, 12):
        for c in range(2, 14):
            if (r, c) in ((2, 2), (2, 13), (11, 2), (11, 13)):
                continue
            iput(c, r, FUR)
    for c in (4, 5, 10, 11):
        iput(c, 5, EYE)
    iput(7, 7, NOSE)
    iput(8, 7, NOSE)
    for c in range(5, 11):
        iput(c, 8, CREAM)
        iput(c, 9, CREAM)
    for c in range(6, 10):
        iput(c, 10, CREAM)
    for r in range(12, 16):
        for c in range(2, 14):
            if r >= 14 and c in (2, 13):
                continue
            iput(c, r, FUR)
        for c in range(6, 10):
            iput(c, r, CREAM)
    return im


# ------------------------------------------------------------ preview -------
def preview(img):
    """Assembled front view (ears + face + body + paws) as ASCII lines."""
    from preview import glyph
    px = img.load()
    L = SPEC["layout"]

    def px_at(region, dx, dy):
        x0, y0, w, h = L[region]
        r, g, b, a = px[x0 + dx, y0 + dy]
        return glyph(r, g, b, a)

    W = 10
    lines = ['', '=== FRONT VIEW (assembled) ===']
    for i in range(3):                                  # ears (3x3)
        row = [' '] * W
        for dx in range(3):
            row[1 + dx] = px_at('ear_front', dx, i)
            row[6 + dx] = px_at('ear_front', dx, i)
        lines.append(''.join(row))
    for j in range(10):
        lines.append(''.join(px_at('head_front', i, j) for i in range(W)))
    for j in range(10):
        lines.append(''.join(px_at('body_front', i, j) for i in range(W)))
    for j in range(8):
        row = [' '] * W
        for dx in range(5):
            row[dx] = px_at('leg_front', dx, j)
            row[5 + dx] = px_at('leg_front', dx, j)
        lines.append(''.join(row))
    return lines
