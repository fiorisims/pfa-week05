"""3D human-skeleton viewport with a camera-angle slider and a Photoshop hand-off.

    python human_viewer.py

A standalone pygame app: an anatomical human skeleton (ivory bone, skull with
eye sockets and jaw, vertebral column, ribcage, pelvis, and long limb bones)
built from primitives and drawn with a small software renderer (painter's
algorithm + Lambert shading). Click-drag a joint to pose the limb (rotation
carries down the chain); drag empty space to orbit the camera. "Open in
Photoshop" renders the current view to human_view.png and imports it as a
layer in the Photoshop document titled "New Illustration" (creating/refreshing
that document each send), so the model can be looked at inside the Photoshop
interface. Auto-sync re-sends the view a moment after you stop moving a slider.

Photoshop dropped its 3D engine in 2022 (v23), so a *live* 3D viewport cannot
exist inside Photoshop - a refreshed image document is the closest equivalent.

"Import model..." loads any OBJ or Maya scene (.ma/.mb) into the viewport
instead of the skeleton (see model_import.py); "Use skeleton" restores it.

Keys: Left/Right = camera angle, Up/Down = distance, A = toggle auto-sync,
S = send to Photoshop, Esc = quit. Mouse wheel zooms; drag the slider to orbit.
"""

import math
import sys
import time
from pathlib import Path

import pygame

import model_import

HERE = Path(__file__).resolve().parent
PNG_PATH = HERE / "human_view.png"
VIEW_NAME = "human_view.png"
DOC_NAME = "New Illustration"      # Photoshop document the render is placed into
LAYER_NAME = "Skeleton render"     # layer the imported PNG lives on

BONE = (0.87, 0.85, 0.75)          # ivory bone
BONE_DARK = (0.62, 0.60, 0.52)     # teeth / cartilage
SOCKET = (0.11, 0.10, 0.09)        # eye sockets, nasal cavity (holes)

LIGHT = (-0.35, 0.78, 0.52)
AMBIENT = 0.38
DIFFUSE = 0.68
FOV = 34.0
FAR_CLIP = 0.06

WINDOW = (980, 700)
VIEWPORT = pygame.Rect(12, 12, 956, 500)
JOINT_RADIUS = 16.0        # click tolerance for grabbing a joint, in pixels
ROT_PER_PIXEL = 0.014      # radians of limb rotation per pixel dragged


# --------------------------------------------------------------------------- #
# vector helpers
# --------------------------------------------------------------------------- #
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def normalize(a):
    n = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


# --------------------------------------------------------------------------- #
# primitives -> faces  (a face is ([world points], (r, g, b)))
# --------------------------------------------------------------------------- #
def box(center, size, color):
    cx, cy, cz = center
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    v = [(cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
         (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
         (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
         (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz)]
    quads = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return [([v[i] for i in q], color) for q in quads]


def cylinder(p0, p1, radius, color, sides=10):
    axis = normalize(sub(p1, p0))
    ref = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = normalize(cross(axis, ref))
    v = cross(axis, u)

    def ring(p):
        out = []
        for j in range(sides):
            t = 2.0 * math.pi * j / sides
            out.append(add(p, scale(add(scale(u, math.cos(t)),
                                        scale(v, math.sin(t))), radius)))
        return out

    r0, r1 = ring(p0), ring(p1)
    faces = [([r0[j], r0[(j + 1) % sides], r1[(j + 1) % sides], r1[j]], color)
             for j in range(sides)]
    faces.append((r0, color))          # caps (winding is irrelevant: no culling)
    faces.append((r1, color))
    return faces


def sphere(center, radius, color, seg=12, rings=8, squash=(1.0, 1.0, 1.0)):
    cx, cy, cz = center
    sx, sy, sz = squash

    def point(i, j):
        theta = math.pi * i / rings
        phi = 2.0 * math.pi * j / seg
        return (cx + math.sin(theta) * math.cos(phi) * radius * sx,
                cy + math.cos(theta) * radius * sy,
                cz + math.sin(theta) * math.sin(phi) * radius * sz)

    faces = []
    for i in range(rings):
        for j in range(seg):
            j2 = (j + 1) % seg
            faces.append(([point(i, j), point(i, j2),
                           point(i + 1, j2), point(i + 1, j)], color))
    return faces


def loft(rings, color, sides=16):
    """Smooth vertical surface through elliptical rings: rings = [(y, rx, rz)]."""
    loops = [[(math.cos(2.0 * math.pi * j / sides) * rx, y,
               math.sin(2.0 * math.pi * j / sides) * rz)
              for j in range(sides)] for y, rx, rz in rings]
    faces = []
    for a, b in zip(loops, loops[1:]):
        for j in range(sides):
            j2 = (j + 1) % sides
            faces.append(([a[j], a[j2], b[j2], b[j]], color))
    faces.append((loops[0], color))      # end caps (mostly hidden)
    faces.append((loops[-1], color))
    return faces


def long_bone(p0, p1, radius, color, sides=8, bulge=1.5, cap=(6, 4)):
    """A limb bone: a shaft with a bulged epiphysis (ball) at each end."""
    return (cylinder(p0, p1, radius, color, sides) +
            sphere(p0, radius * bulge, color, cap[0], cap[1]) +
            sphere(p1, radius * bulge, color, cap[0], cap[1]))


def tube_along(points, radius, color, sides=6):
    """A bent tube threaded through a list of points (ribs, jaw, clavicles)."""
    pts = [normalize(sub(b, a)) for a, b in zip(points, points[1:])]
    rings = []
    n = len(points)
    for i, p in enumerate(points):
        if i == 0:
            d = pts[0]
        elif i == n - 1:
            d = pts[-1]
        else:
            d = normalize(add(pts[i - 1], pts[i]))
        ref = (0.0, 1.0, 0.0) if abs(d[1]) < 0.9 else (1.0, 0.0, 0.0)
        u = normalize(cross(d, ref))
        v = cross(d, u)
        rings.append([add(p, add(scale(u, math.cos(t) * radius),
                                scale(v, math.sin(t) * radius)))
                      for t in (2.0 * math.pi * j / sides
                                for j in range(sides))])
    faces = []
    for a, b in zip(rings, rings[1:]):
        for j in range(sides):
            j2 = (j + 1) % sides
            faces.append(([a[j], a[j2], b[j2], b[j]], color))
    faces.append((rings[0], color))
    faces.append((rings[-1], color))
    return faces


# --------------------------------------------------------------------------- #
# tiny 3x3 matrix maths (rotations are stored as 3x3 matrices)
# --------------------------------------------------------------------------- #
IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def mat_mul(A, B):
    return tuple(tuple(sum(A[i][k] * B[k][j] for k in range(3))
                       for j in range(3)) for i in range(3))


def mat_vec(A, v):
    return tuple(A[i][0] * v[0] + A[i][1] * v[1] + A[i][2] * v[2]
                 for i in range(3))


def axis_angle(axis, angle):
    x, y, z = normalize(axis)
    c, s, C = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    return ((x * x * C + c, x * y * C - z * s, x * z * C + y * s),
            (y * x * C + z * s, y * y * C + c, y * z * C - x * s),
            (z * x * C - y * s, z * y * C + x * s, z * z * C + c))


# --------------------------------------------------------------------------- #
# skeleton: bones with pivots + parents, so rotating a joint carries its limbs
# --------------------------------------------------------------------------- #
class Bone:
    def __init__(self, name, parent, pivot, parts, tip, exposed=True):
        self.name = name
        self.parent = parent
        self.pivot = pivot          # rest-position of the joint, world space
        self.parts = parts          # static faces in rest space
        self.tip = tip              # a rest point at the far end (drag lever)
        self.exposed = exposed      # dragged by the user?
        self.rot = IDENTITY         # local rotation about the pivot
        self.m_pos = pivot          # current world joint position
        self.m_tip = tip            # current world tip position

    def reset(self):
        self.rot = IDENTITY


def build_skeleton():
    """A human skeleton as a bone hierarchy (feet at y=0, ~1.72 m tall).
    Proportions follow standard anthropometry: hip pivot at the greater
    trochanter (~half height), shoulder ~0.82 H, elbow ~0.63 H, wrist ~0.49 H,
    knee ~0.28 H, ankle ~0.04 H."""
    specs = []

    # ---- pelvis (fixed root): sacrum + iliac blades + ischium + pubis ----
    pelvis = box((0.0, 0.905, -0.045), (0.075, 0.175, 0.05), BONE)
    for s in (-1, 1):
        pelvis += sphere((0.088 * s, 0.94, -0.02), 0.090, BONE, 8, 6,
                         (0.60, 1.05, 0.40))
        pelvis += sphere((0.058 * s, 0.815, -0.01), 0.030, BONE, 6, 4)
    pelvis += tube_along([(-0.075, 0.815, 0.02), (-0.040, 0.800, 0.055),
                          (0.0, 0.795, 0.06), (0.040, 0.800, 0.055),
                          (0.075, 0.815, 0.02)], 0.011, BONE, 5)
    specs.append(("pelvis", None, (0.0, 0.90, 0.0), pelvis,
                  (0.0, 1.00, 0.0), False))

    # ---- torso: spine, ribcage, sternum, clavicles, scapulae ----
    torso = []
    for i in range(11):                                   # lumbar + thoracic
        y = 1.05 + i * 0.037
        torso += cylinder((0.0, y, -0.035), (0.0, y + 0.022, -0.035),
                          0.022, BONE, 6)
        torso += box((0.0, y + 0.008, -0.062), (0.018, 0.014, 0.026), BONE)
    for i in range(9):                                    # 9 rib pairs
        yb = 1.40 - i * 0.028
        for s in (-1, 1):
            torso += tube_along(
                [(s * (0.03 + 0.11 * math.sin(math.pi * t)),
                  yb - 0.055 * t, -0.035 + 0.115 * t) for t in
                 (k / 5.0 for k in range(6))], 0.008, BONE, 5)
    torso += box((0.0, 1.285, 0.082), (0.050, 0.235, 0.018), BONE)   # sternum
    for s in (-1, 1):
        torso += tube_along([(0.012 * s, 1.40, 0.060),
                             (0.090 * s, 1.425, 0.030),
                             (0.175 * s, 1.415, -0.005)], 0.009, BONE, 5)
        torso += box((0.100 * s, 1.30, -0.078), (0.085, 0.14, 0.012), BONE)
    specs.append(("torso", "pelvis", (0.0, 1.05, 0.0), torso,
                  (0.0, 1.42, 0.0), True))

    # ---- neck (cervical vertebrae) ----
    neck = cylinder((0.0, 1.45, -0.02), (0.0, 1.51, -0.015), 0.024, BONE, 6)
    specs.append(("neck", "torso", (0.0, 1.45, 0.0), neck,
                  (0.0, 1.51, 0.0), True))

    # ---- head: cranium, face, eye sockets, nasal cavity, mandible, teeth ----
    head = sphere((0.0, 1.635, -0.01), 0.080, BONE, 12, 9, (0.95, 1.00, 1.05))
    head += sphere((0.0, 1.545, 0.028), 0.055, BONE, 8, 6, (0.92, 0.95, 0.85))
    for s in (-1, 1):
        head += sphere((0.033 * s, 1.575, 0.062), 0.021, SOCKET, 8, 6,
                       (1.0, 0.85, 0.60))
    head += sphere((0.0, 1.545, 0.075), 0.012, SOCKET, 6, 5)
    head += tube_along([(-0.058, 1.550, -0.020), (-0.052, 1.515, 0.020),
                        (-0.028, 1.497, 0.050), (0.0, 1.493, 0.055),
                        (0.028, 1.497, 0.050), (0.052, 1.515, 0.020),
                        (0.058, 1.550, -0.020)], 0.012, BONE, 5)
    head += box((0.0, 1.513, 0.050), (0.075, 0.009, 0.030), BONE_DARK)
    specs.append(("head", "neck", (0.0, 1.50, 0.0), head,
                  (0.0, 1.72, 0.0), True))

    for s, side in ((1, "L"), (-1, "R")):
        # upper arm: humeral head + shaft
        humerus = (sphere((0.185 * s, 1.41, 0.0), 0.033, BONE, 8, 6) +
                   long_bone((0.19 * s, 1.40, 0.0), (0.205 * s, 1.09, 0.0),
                             0.016, BONE, 8, 1.5))
        specs.append(("shoulder" + side, "torso", (0.19 * s, 1.41, 0.0),
                      humerus, (0.205 * s, 1.09, 0.0), True))

        # forearm: ulna + radius + olecranon
        forearm = (long_bone((0.205 * s, 1.090, -0.006), (0.232 * s, 0.845, -0.006),
                             0.011, BONE, 6, 1.5, (6, 4)) +
                   long_bone((0.214 * s, 1.085, 0.008), (0.240 * s, 0.850, 0.004),
                             0.010, BONE, 6, 1.5, (6, 4)) +
                   sphere((0.205 * s, 1.105, -0.022), 0.017, BONE, 6, 5))
        specs.append(("elbow" + side, "shoulder" + side, (0.205 * s, 1.09, 0.0),
                      forearm, (0.236 * s, 0.845, 0.0), True))

        # hand: carpals + metacarpals + four fingers + thumb
        hand = (box((0.235 * s, 0.815, 0.0), (0.038, 0.035, 0.050), BONE) +
                box((0.245 * s, 0.775, 0.0), (0.042, 0.055, 0.050), BONE))
        for k in range(4):
            x = (0.224 + 0.013 * k) * s
            hand += long_bone((x, 0.748, 0.0), (x, 0.674, 0.0),
                              0.0065, BONE, 5, 1.25, (5, 4))
        hand += long_bone((0.268 * s, 0.782, 0.005), (0.292 * s, 0.752, 0.028),
                          0.0075, BONE, 5, 1.3, (5, 4))
        specs.append(("wrist" + side, "elbow" + side, (0.235 * s, 0.84, 0.0),
                      hand, (0.245 * s, 0.66, 0.0), True))

        # thigh: femoral head + angled neck + greater trochanter + shaft
        femur = (sphere((0.075 * s, 0.89, 0.0), 0.024, BONE, 6, 5) +
                 cylinder((0.075 * s, 0.885, 0.0), (0.100 * s, 0.835, 0.0),
                          0.014, BONE, 6) +
                 sphere((0.108 * s, 0.858, 0.0), 0.020, BONE, 6, 5) +
                 long_bone((0.100 * s, 0.835, 0.0), (0.100 * s, 0.49, 0.0),
                           0.017, BONE, 8, 1.5, (6, 4)))
        specs.append(("hip" + side, "pelvis", (0.085 * s, 0.89, 0.0), femur,
                      (0.100 * s, 0.49, 0.0), True))

        # shin: patella + tibia + fibula
        shin = (sphere((0.100 * s, 0.478, 0.030), 0.020, BONE, 6, 5,
                       (1.0, 1.0, 0.55)) +
                long_bone((0.096 * s, 0.49, 0.0), (0.096 * s, 0.075, 0.0),
                          0.015, BONE, 8, 1.5, (6, 4)) +
                long_bone((0.118 * s, 0.485, -0.006), (0.112 * s, 0.085, -0.006),
                          0.008, BONE, 6, 1.5, (6, 4)))
        specs.append(("knee" + side, "hip" + side, (0.100 * s, 0.49, 0.0), shin,
                      (0.100 * s, 0.075, 0.0), True))

        # foot: calcaneus + talus + midfoot + toes
        foot = (sphere((0.100 * s, 0.034, -0.050), 0.028, BONE, 6, 5,
                       (0.90, 0.80, 1.10)) +
                sphere((0.100 * s, 0.058, -0.008), 0.021, BONE, 6, 5) +
                box((0.100 * s, 0.026, 0.030), (0.060, 0.028, 0.110), BONE) +
                box((0.100 * s, 0.014, 0.115), (0.066, 0.018, 0.060), BONE))
        specs.append(("ankle" + side, "knee" + side, (0.100 * s, 0.075, 0.0), foot,
                      (0.100 * s, 0.03, 0.15), True))

    bones, order = {}, []
    for name, parent, pivot, parts, tip, exposed in specs:
        bones[name] = Bone(name, bones.get(parent), pivot, parts, tip, exposed)
        order.append(name)
    return bones, order


SKELETON, BONE_ORDER = build_skeleton()


def pose_mesh():
    """Apply every bone's rotation down the chain; return world-space faces.
    Also refreshes each bone's current joint (m_pos) and tip (m_tip)."""
    world = {}
    faces = []
    for name in BONE_ORDER:
        b = SKELETON[name]
        if b.parent is None:
            Mp, tp = IDENTITY, (0.0, 0.0, 0.0)
        else:
            Mp, tp = world[b.parent.name]
        rp = mat_vec(b.rot, b.pivot)
        M = mat_mul(Mp, b.rot)
        t = add(mat_vec(Mp, sub(b.pivot, rp)), tp)
        world[name] = (M, t)
        b.m_pos = add(mat_vec(Mp, b.pivot), tp)
        b.m_tip = add(mat_vec(M, b.tip), t)
        for pts, color in b.parts:
            faces.append(([add(mat_vec(M, p), t) for p in pts], color))
    return faces


def reset_pose():
    for b in SKELETON.values():
        b.reset()


def rotate_joint(name, axis, angle):
    """Rotate one joint about a world-space axis (composes with its pose)."""
    b = SKELETON[name]
    b.rot = mat_mul(axis_angle(axis, angle), b.rot)


HUMAN = pose_mesh()


def make_projector(cam, rect):
    """Return a function projecting world points into `rect`'s pixels."""
    pos, right, up, fwd = cam.basis()
    f = (rect.height / 2.0) / math.tan(math.radians(FOV) / 2.0)
    ox, oy = rect.centerx, rect.centery

    def project(p):
        rel = sub(p, pos)
        x, y, z = dot(rel, right), dot(rel, up), dot(rel, fwd)
        if z < FAR_CLIP:
            return None
        return (ox + x * f / z, oy - y * f / z)
    return project


def pick_joint(cam, screen_pos, rect, radius=16.0):
    """The draggable joint nearest to a screen point, or None."""
    project = make_projector(cam, rect)
    best, best_d = None, radius
    for b in SKELETON.values():
        if not b.exposed:
            continue
        sp = project(b.m_pos)
        if sp is None:
            continue
        d = math.hypot(sp[0] - screen_pos[0], sp[1] - screen_pos[1])
        if d < best_d:
            best, best_d = b, d
    return best


def floor_faces():
    s = 7.0
    return [([(-s, 0.0, -s), (s, 0.0, -s), (s, 0.0, s), (-s, 0.0, s)],
             (0.19, 0.20, 0.23))]


def shadow_poly(radius=0.42, y=0.003, n=24):
    return [(math.cos(2 * math.pi * i / n) * radius, y,
             math.sin(2 * math.pi * i / n) * radius) for i in range(n)]


# --------------------------------------------------------------------------- #
# camera + renderer
# --------------------------------------------------------------------------- #
class Camera:
    def __init__(self):
        self.angle = 35.0        # azimuth, degrees  <-- the slider drives this
        self.height = 12.0       # elevation, degrees
        self.distance = 4.2
        self.target = (0.0, 0.9, 0.0)

    def basis(self):
        az = math.radians(self.angle)
        el = math.radians(self.height)
        d = self.distance
        t = self.target
        pos = (t[0] + d * math.cos(el) * math.sin(az),
               t[1] + d * math.sin(el),
               t[2] + d * math.cos(el) * math.cos(az))
        fwd = normalize(sub(t, pos))
        right = normalize(cross(fwd, (0.0, 1.0, 0.0)))
        up = cross(right, fwd)
        return pos, right, up, fwd


_gradients = {}


def backdrop(size):
    surf = _gradients.get(size)
    if surf is None:
        w, h = size
        surf = pygame.Surface(size)
        top, bottom = (13, 15, 21), (34, 38, 49)
        for y in range(h):
            k = y / max(1, h - 1)
            surf.fill((int(top[0] + (bottom[0] - top[0]) * k),
                       int(top[1] + (bottom[1] - top[1]) * k),
                       int(top[2] + (bottom[2] - top[2]) * k)),
                      pygame.Rect(0, y, w, 1))
        _gradients[size] = surf
    return surf


def project_point(cam, point, size=(640, 640)):
    """Project a world point onto the screen; None if it is behind the camera."""
    return make_projector(cam, pygame.Rect(0, 0, size[0], size[1]))(point)


def render_view(surface, rect, cam, faces=HUMAN):
    """Draw the scene into `rect` of `surface` (works for window or offscreen)."""
    surface.blit(backdrop((rect.width, rect.height)), rect.topleft)

    pos, right, up, fwd = cam.basis()
    f = (rect.height / 2.0) / math.tan(math.radians(FOV) / 2.0)
    ox, oy = rect.centerx, rect.centery

    def project(p):
        rel = sub(p, pos)
        x, y, z = dot(rel, right), dot(rel, up), dot(rel, fwd)
        if z < FAR_CLIP:
            return None
        return (ox + x * f / z, oy - y * f / z, z)

    def shade(pts, color):
        n = normalize(cross(sub(pts[1], pts[0]), sub(pts[2], pts[0])))
        light = AMBIENT + DIFFUSE * abs(dot(n, LIGHT))
        return (min(255, int(color[0] * 255 * light)),
                min(255, int(color[1] * 255 * light)),
                min(255, int(color[2] * 255 * light)))

    def emit(pts, color, out):
        screen = []
        for p in pts:
            pr = project(p)
            if pr is None:
                return
            screen.append(pr)
        depth = sum(s[2] for s in screen) / len(screen)
        out.append((depth, [(s[0], s[1]) for s in screen], shade(pts, color)))

    flat = []
    for face in floor_faces():
        emit(face[0], face[1], flat)
    flat.sort(key=lambda t: -t[0])
    for _, pts, color in flat:
        pygame.draw.polygon(surface, color, pts)
    shadow = [project(p) for p in shadow_poly()]
    if all(shadow):
        pygame.draw.polygon(surface, (0.10, 0.11, 0.14),
                            [(s[0], s[1]) for s in shadow])

    solid = []
    for pts, color in faces:
        emit(pts, color, solid)
    solid.sort(key=lambda t: -t[0])
    for _, pts, color in solid:
        pygame.draw.polygon(surface, color, pts)


def render_png(cam, size=(1000, 1000), faces=HUMAN):
    surf = pygame.Surface(size)
    render_view(surf, surf.get_rect(), cam, faces)
    pygame.image.save(surf, str(PNG_PATH))
    return surf


# --------------------------------------------------------------------------- #
# Photoshop hand-off
# --------------------------------------------------------------------------- #
JSX = """app.displayDialogs = DialogModes.NO;
var path = "%s";
var docName = "%s";
var layerName = "%s";
for (var i = app.documents.length - 1; i >= 0; i--) {
    if (app.documents[i].name === docName) {
        app.documents[i].close(SaveOptions.DONOTSAVECHANGES);
    }
}
var src = app.open(File(path));
var doc = app.documents.add(src.width.value, src.height.value, 72, docName,
    NewDocumentMode.RGB, DocumentFill.WHITE);
app.activeDocument = src;
var placed = src.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
app.activeDocument = doc;
placed.name = layerName;
app.activeDocument = src;
src.close(SaveOptions.DONOTSAVECHANGES);
app.activeDocument = doc;
__result__ = "illustration: " + doc.name + " | layer: " + placed.name +
    " " + doc.width.value + "x" + doc.height.value;
"""


def photoshop_running():
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return None
    pythoncom.CoInitialize()
    try:
        win32com.client.GetActiveObject("Photoshop.Application")
        return True
    except Exception:
        return False


def send_to_photoshop(cam, faces=HUMAN):
    """Render the current view and import it as a layer in the Photoshop
    document titled ``DOC_NAME`` (creating/refreshing that document).

    Photoshop does not have to be open first: when it is closed the bridge
    launches it via COM (the first cold start can take up to a minute).
    """
    if photoshop_running() is None:
        return False, "pywin32 is not installed (python -m pip install pywin32)"

    render_png(cam, faces=faces)
    payload = JSX % (str(PNG_PATH).replace("\\", "/"), DOC_NAME, LAYER_NAME)
    try:
        import photoshop_bridge
        text = photoshop_bridge.run(payload).strip()
    except Exception as exc:                                  # noqa: BLE001
        return False, "Photoshop error: %s" % exc
    line = next((ln for ln in text.splitlines() if ln.startswith("__result__")),
                text)
    return "BRIDGE ERROR" not in text, line


# --------------------------------------------------------------------------- #
# file dialog + tiny widgets
# --------------------------------------------------------------------------- #
def ask_model_file():
    """Open a native file picker for a 3D model; "" if cancelled/unavailable."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:                                          # noqa: BLE001
        return ""
    root = tk.Tk()
    root.withdraw()
    try:
        return filedialog.askopenfilename(
            title="Import model into the viewport",
            filetypes=[("3D models", "*.obj *.ma *.mb"),
                       ("Wavefront OBJ", "*.obj"),
                       ("Maya ASCII", "*.ma"),
                       ("Maya binary", "*.mb"),
                       ("All files", "*.*")])
    finally:
        root.destroy()


FONT = None


def font(size=16, bold=False):
    global FONT
    if FONT is None or FONT[0] != (size, bold):
        FONT = ((size, bold), pygame.font.SysFont("segoeui", size, bold=bold))
    return FONT[1]


class Slider:
    KNOB = 8

    def __init__(self, x, y, w, label, lo, hi, value, fmt="%.0f"):
        self.rect = pygame.Rect(x, y, w, 22)
        self.label, self.lo, self.hi, self.fmt = label, lo, hi, fmt
        self.value = value
        self.dragging = False

    def _set_from_x(self, mx):
        pad = self.KNOB + 2
        t = (mx - (self.rect.x + pad)) / max(1, self.rect.width - 2 * pad)
        self.value = self.lo + min(1.0, max(0.0, t)) * (self.hi - self.lo)

    def hits(self, pos):
        return self.rect.inflate(0, 14).collidepoint(pos)

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and \
                self.hits(event.pos):
            self.dragging = True
            self._set_from_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_from_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and self.dragging:
            self.dragging = False
            return True
        return False

    def nudge(self, delta):
        span = self.hi - self.lo
        self.value = min(self.hi, max(self.lo, self.value + delta * span / 90.0))

    def draw(self, surface, focused=True):
        lbl = font(15).render("%s  %s" % (self.label, self.fmt % self.value),
                              True, (214, 220, 232))
        surface.blit(lbl, (self.rect.x, self.rect.y - 20))
        y = self.rect.centery
        pygame.draw.line(surface, (62, 68, 84), (self.rect.x, y),
                         (self.rect.right, y), 4)
        t = (self.value - self.lo) / (self.hi - self.lo or 1.0)
        kx = int(self.rect.x + self.KNOB + 2 +
                 t * (self.rect.width - 2 * self.KNOB - 4))
        pygame.draw.line(surface, (86, 140, 224), (self.rect.x, y), (kx, y), 4)
        pygame.draw.circle(surface, (226, 233, 245) if focused else (150, 158, 172),
                           (kx, y), self.KNOB)


class Button:
    def __init__(self, rect, label, action, accent=False):
        self.rect, self.label, self.action = pygame.Rect(rect), label, action
        self.accent, self.hover = accent, False

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and \
                self.rect.collidepoint(event.pos):
            self.action()
            return True
        return False

    def draw(self, surface):
        base = (58, 108, 190) if self.accent else (54, 60, 74)
        if self.hover:
            base = tuple(min(255, c + 22) for c in base)
        pygame.draw.rect(surface, base, self.rect, border_radius=6)
        pygame.draw.rect(surface, (110, 120, 140), self.rect, 1, border_radius=6)
        txt = font(16, bold=True).render(self.label, True, (238, 242, 250))
        surface.blit(txt, txt.get_rect(center=self.rect.center))


class Toggle:
    def __init__(self, rect, label, value=False):
        self.rect, self.label, self.value = pygame.Rect(rect), label, value

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and \
                self.rect.collidepoint(event.pos):
            self.value = not self.value
            return True
        return False

    def draw(self, surface):
        box = pygame.Rect(self.rect.x, self.rect.y + 3, 18, 18)
        pygame.draw.rect(surface, (58, 108, 190) if self.value else (40, 44, 54),
                         box, border_radius=4)
        pygame.draw.rect(surface, (140, 148, 164), box, 1, border_radius=4)
        if self.value:
            pygame.draw.lines(surface, (240, 245, 252), False,
                              [(box.x + 4, box.y + 9), (box.x + 8, box.y + 13),
                               (box.x + 14, box.y + 5)], 2)
        txt = font(15).render(self.label, True, (206, 213, 226))
        surface.blit(txt, (box.right + 8, self.rect.y + 3))


# --------------------------------------------------------------------------- #
# app
# --------------------------------------------------------------------------- #
class Viewer:
    def __init__(self):
        self.cam = Camera()
        self.faces = pose_mesh()
        self.custom = False          # True once an imported model is shown
        self.model_name = ""
        self.auto_sync = False
        self.dirty = False
        self.last_change = 0.0
        self.status = "Drag a joint to pose the skeleton."
        self.status_ok = True

        # posing state
        self.hover = None
        self.selected = None
        self.dragging = None
        self.orbiting = False
        self.drag_start = (0, 0)
        self.drag_rot0 = IDENTITY
        self.drag_pivot = (0.0, 0.0, 0.0)
        self.drag_tip = (0.0, 0.0, 0.0)
        self.drag_right = (1.0, 0.0, 0.0)
        self.drag_up = (0.0, 1.0, 0.0)
        self.orbit_angle0 = 0.0
        self.orbit_height0 = 0.0

        self.angle = Slider(150, 544, 380, "Camera angle", 0.0, 360.0,
                            self.cam.angle, "%.0f deg")
        self.height = Slider(150, 590, 380, "Camera height", 5.0, 60.0,
                             self.cam.height, "%.0f deg")
        self.distance = Slider(600, 544, 350, "Distance", 2.0, 8.0,
                               self.cam.distance, "%.1f m")
        self.auto = Toggle((600, 584, 20, 20), "Auto-sync to Photoshop", False)
        self.send = Button((600, 616, 200, 30), "Open in Photoshop",
                           self.on_send, accent=True)
        self.save = Button((812, 616, 138, 30), "Save PNG", self.on_save)
        self.import_btn = Button((302, 618, 158, 30), "Import model...",
                                 self.on_import)
        self.skeleton_btn = Button((466, 618, 130, 30), "Use skeleton",
                                   self.on_use_skeleton)
        self.reset_btn = Button((150, 618, 140, 30), "Reset pose", self.on_reset)
        self.sliders = [self.angle, self.height, self.distance]
        self.focus = self.angle

    # -- actions ----------------------------------------------------------- #
    def sync_from_sliders(self):
        self.cam.angle = self.angle.value
        self.cam.height = self.height.value
        self.cam.distance = self.distance.value

    def mark_dirty(self):
        self.last_change = time.time()
        self.dirty = True

    def on_send(self):
        self.sync_from_sliders()
        self.status = "Sending to Photoshop..."
        self.status_ok = True
        self.draw_frame()
        pygame.display.flip()
        ok, msg = send_to_photoshop(self.cam, self.faces)
        self.status, self.status_ok = msg, ok
        self.dirty = False
        print("[photoshop]", msg)

    def on_save(self):
        self.sync_from_sliders()
        render_png(self.cam, faces=self.faces)
        self.status = "Saved %s" % PNG_PATH.name
        self.status_ok = True
        print("[saved]", PNG_PATH)

    def on_reset(self):
        if self.custom:
            self.status = ("Import active - click 'Use skeleton' to bring the "
                           "skeleton back.")
            self.status_ok = True
            return
        reset_pose()
        self.faces = pose_mesh()
        self.selected = self.dragging = self.hover = None
        self.status = "Pose reset."
        self.status_ok = True
        self.mark_dirty()

    def on_import(self):
        path = ask_model_file()
        if not path:
            return
        self.sync_from_sliders()
        self.status = "Importing %s..." % Path(path).name
        self.status_ok = True
        self.draw_frame()
        pygame.display.flip()
        try:
            faces, summary = model_import.load_model(path)
            self.faces = model_import.fit_to_view(faces)
        except Exception as exc:                               # noqa: BLE001
            self.status = "Import failed: %s" % exc
            self.status_ok = False
            print("[import]", exc)
            return
        self.custom = True
        self.model_name = Path(path).name
        self.selected = self.dragging = self.hover = None
        self.cam.target = (0.0, model_import.FIT_TARGET_Y, 0.0)
        self.distance.value = model_import.FIT_DISTANCE
        self.cam.distance = model_import.FIT_DISTANCE
        self.status = "Imported %s (%s)" % (self.model_name, summary)
        self.status_ok = True
        self.mark_dirty()
        print("[import]", self.status)

    def on_use_skeleton(self):
        reset_pose()
        self.faces = pose_mesh()
        self.custom = False
        self.model_name = ""
        self.selected = self.dragging = self.hover = None
        self.cam.target = (0.0, 0.9, 0.0)
        self.distance.value = 4.2
        self.cam.distance = 4.2
        self.status = "Skeleton restored."
        self.status_ok = True
        self.mark_dirty()

    # -- posing ------------------------------------------------------------ #
    def handle_viewport(self, event):
        """Joint picking / dragging and background orbiting inside the view."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and \
                VIEWPORT.collidepoint(event.pos):
            bone = None if self.custom else pick_joint(self.cam, event.pos,
                                                       VIEWPORT)
            self.selected = bone
            self.drag_start = event.pos
            if bone is not None:
                self.dragging = bone
                self.drag_rot0 = bone.rot
                self.drag_pivot = bone.m_pos
                self.drag_tip = bone.m_tip
                _, self.drag_right, self.drag_up, _ = self.cam.basis()
                self.status = "Posing %s - drag to rotate it" % bone.name
                self.status_ok = True
            else:
                self.orbiting = True
                self.orbit_angle0 = self.cam.angle
                self.orbit_height0 = self.cam.height
            return True

        if event.type == pygame.MOUSEMOTION:
            if self.dragging is not None:
                self.pose_drag(event.pos)
                return True
            if self.orbiting:
                self.cam.angle = (self.orbit_angle0 + (
                    event.pos[0] - self.drag_start[0]) * 0.4) % 360.0
                self.cam.height = min(self.height.hi, max(
                    self.height.lo, self.orbit_height0 - (
                        event.pos[1] - self.drag_start[1]) * 0.3))
                self.angle.value, self.height.value = (self.cam.angle,
                                                       self.cam.height)
                self.mark_dirty()
                return True
            self.hover = (None if self.custom else
                          pick_joint(self.cam, event.pos, VIEWPORT)
                          if VIEWPORT.collidepoint(event.pos) else None)
            return False

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = None
            self.orbiting = False
        return False

    def pose_drag(self, pos):
        """Rotate the grabbed joint so its tip swings toward the cursor."""
        dx = pos[0] - self.drag_start[0]
        dy = pos[1] - self.drag_start[1]
        lever = sub(self.drag_tip, self.drag_pivot)
        if dot(lever, lever) < 1e-9:
            return
        motion = sub(scale(self.drag_right, float(dx)),
                     scale(self.drag_up, float(dy)))
        axis = cross(lever, motion)
        if dot(axis, axis) < 1e-12:
            return
        angle = math.hypot(dx, dy) * ROT_PER_PIXEL
        self.dragging.rot = mat_mul(axis_angle(axis, angle), self.drag_rot0)
        self.faces = pose_mesh()
        self.mark_dirty()

    # -- events ------------------------------------------------------------ #
    def handle(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.focus.nudge(1 if event.key == pygame.K_RIGHT else -1)
                self.sliders_changed()
            elif event.key in (pygame.K_UP, pygame.K_DOWN):
                step = -0.2 if event.key == pygame.K_UP else 0.2
                self.distance.value = min(self.distance.hi, max(
                    self.distance.lo, self.distance.value + step))
                self.sliders_changed()
            elif event.key == pygame.K_a:
                self.auto.value = not self.auto.value
            elif event.key == pygame.K_s:
                self.on_send()
            elif event.key == pygame.K_r:
                self.on_reset()
        if event.type == pygame.MOUSEWHEEL:
            self.distance.value = min(self.distance.hi, max(
                self.distance.lo, self.distance.value - event.y * 0.25))
            self.sliders_changed()
        self.handle_viewport(event)
        for w in self.sliders:
            if w.handle(event):
                self.focus = w
                self.sliders_changed()
        self.auto.handle(event)
        self.send.handle(event)
        self.save.handle(event)
        self.reset_btn.handle(event)
        self.import_btn.handle(event)
        self.skeleton_btn.handle(event)
        return True

    def sliders_changed(self):
        self.sync_from_sliders()
        self.mark_dirty()

    # -- drawing ----------------------------------------------------------- #
    def draw_handles(self, screen):
        if self.custom:
            return
        project = make_projector(self.cam, VIEWPORT)
        for b in SKELETON.values():
            if not b.exposed:
                continue
            sp = project(b.m_pos)
            if sp is None:
                continue
            active = b is self.dragging or b is self.selected
            hot = active or b is self.hover
            r = 8 if active else 6
            centre = (int(sp[0]), int(sp[1]))
            pygame.draw.circle(screen, (255, 210, 120) if hot
                               else (74, 82, 100), centre, r)
            pygame.draw.circle(screen, (18, 20, 26), centre, r, 2)

    def draw_frame(self):
        screen = self.screen
        screen.fill((16, 18, 24))
        render_view(screen, VIEWPORT, self.cam, self.faces)
        self.draw_handles(screen)
        pygame.draw.rect(screen, (52, 58, 72), VIEWPORT, 1)
        for w in self.sliders:
            w.draw(screen, w is self.focus)
        self.auto.draw(screen)
        self.send.draw(screen)
        self.save.draw(screen)
        self.reset_btn.draw(screen)
        self.import_btn.draw(screen)
        self.skeleton_btn.draw(screen)
        help_txt = ("Click-drag a joint to pose   drag background to orbit   "
                    "wheel zoom   R reset   A auto   S send   Esc quit")
        screen.blit(font(14).render(help_txt, True, (128, 136, 152)),
                    (310, 660))
        colour = (150, 214, 158) if self.status_ok else (236, 158, 150)
        screen.blit(font(14).render(self.status[:120], True, colour),
                    (12, 682))

    def run(self):
        pygame.init()
        pygame.display.set_caption("3D Human Viewport")
        self.screen = pygame.display.set_mode(WINDOW)
        pygame.key.set_repeat(300, 40)
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if not self.handle(event):
                    running = False
            if self.auto.value and self.dirty and \
                    time.time() - self.last_change > 0.35:
                self.on_send()
            self.draw_frame()
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()
        return 0


def main():
    return Viewer().run()


if __name__ == "__main__":
    sys.exit(main())
