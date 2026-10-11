"""Headless checks for human_viewer.py (no window; dummy SDL drivers).

    python test_human_viewer.py

Verifies the mesh, the camera/projection maths, that a render lands on disk and
actually changes when the camera-angle slider moves, and (if Photoshop is up)
the PNG -> Photoshop document hand-off. Exits 1 on any failure.

If the file is double-clicked from Explorer (its console would vanish when the
run ends) it waits for Enter at the end so the results stay readable; run from a
terminal it exits immediately.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import atexit  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

import pygame  # noqa: E402

import human_viewer as hv  # noqa: E402
import model_import as mi  # noqa: E402


def _ancestor_names():
    """Lowercased names of this Windows process's ancestors, nearest first."""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    k32 = ctypes.windll.kernel32
    TH32CS_SNAPPROCESS = 0x2
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return []
    parents, names = {}, {}
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    ok = k32.Process32First(snap, ctypes.byref(entry))
    while ok:
        parents[entry.th32ProcessID] = entry.th32ParentProcessID
        names[entry.th32ProcessID] = entry.szExeFile.decode(
            "mbcs", "replace").lower()
        ok = k32.Process32Next(snap, ctypes.byref(entry))
    k32.CloseHandle(snap)

    chain, pid, seen = [], os.getpid(), set()
    while pid in parents and pid not in seen:
        seen.add(pid)
        pid = parents[pid]
        if pid not in names:
            break
        chain.append(names[pid])
    return chain


# A shell ancestor means we were started from a terminal; an explorer.exe ancestor
# means the file was double-clicked. (py.exe/pyw.exe are launchers, not shells.)
_SHELLS = {"cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe",
           "bash.exe", "wsl.exe", "conhost.exe", "python.exe", "pythonw.exe"}


def _owns_console():
    """True when the script was double-clicked from Explorer (so we should pause)."""
    if os.name != "nt":
        return False
    try:
        chain = _ancestor_names()
    except Exception:                                          # noqa: BLE001
        return False
    return "explorer.exe" in chain and not (_SHELLS & set(chain))


def _hold_open():
    """Keep the console alive after a double-click run so results stay readable."""
    if not _owns_console():
        return
    try:
        input("\nPress Enter to close...")
    except (EOFError, KeyboardInterrupt):
        pass


atexit.register(_hold_open)

failures = []


def check(label, got, want):
    ok = got == want
    if not ok:
        failures.append("%s: got %r want %r" % (label, got, want))
    print("%-40s %s  %r" % (label, "ok" if ok else "FAIL", got))


def truth(label, value):
    check(label, bool(value), True)


def close_photoshop_viewport():
    import photoshop_bridge
    photoshop_bridge.run(
        'for (var i = app.documents.length - 1; i >= 0; i--) {'
        '  if (app.documents[i].name === "%s") {'
        '    app.documents[i].close(SaveOptions.DONOTSAVECHANGES); } }'
        '__result__ = app.documents.length;' % hv.DOC_NAME)


print("--- mesh ---")
ys = [p[1] for face in hv.HUMAN for p in face[0]]
xs = [p[0] for face in hv.HUMAN for p in face[0]]
zs = [p[2] for face in hv.HUMAN for p in face[0]]
check("face count", len(hv.HUMAN) > 300, True)
check("finite numbers", all(isinstance(v, float) for v in xs + ys + zs), True)
check("feet on the ground", min(ys) > -0.001, True)
check("head height ~1.7m", 1.70 < max(ys) < 1.85, True)
check("arms within reach", max(abs(x) for x in xs) < 0.45, True)
check("is thin (depth)", max(zs) - min(zs) < 0.35, True)

print("--- camera ---")
cam = hv.Camera()
pos, right, up, fwd = cam.basis()
target = hv.sub(cam.target, pos)
check("camera in front of model (+z)", pos[2] > 0, True)
check("camera above the floor", pos[1] > 0, True)
truth("camera looks at the target", hv.dot(fwd, target) > 0)
truth("up vector is up", up[1] > 0.9)
truth("right vector is horizontal", abs(right[1]) < 1e-6)

print("--- projection ---")
head = hv.project_point(cam, (0.0, 1.73, 0.0))
feet = hv.project_point(cam, (0.0, 0.0, 0.0))
truth("head and feet on screen", head and feet)
check("head is above feet", head[1] < feet[1], True)
truth("feet above the bottom edge", feet[1] < 640)
truth("head below the top edge", head[1] > 0)

print("--- slider drives the camera angle ---")
s = hv.Slider(150, 544, 380, "Camera angle", 0.0, 360.0, 0.0)
s._set_from_x(s.rect.x)
check("left end = 0", round(s.value), 0)
s._set_from_x(s.rect.right)
check("right end = 360", round(s.value), 360)
s._set_from_x(s.rect.centerx)
check("middle = 180", round(s.value), 180)

print("--- render to PNG ---")
pygame.init()
hv.render_png(cam, (400, 400))
check("png written", hv.PNG_PATH.exists(), True)
check("png not empty", hv.PNG_PATH.stat().st_size > 4000, True)

print("--- rotating the camera changes the view ---")
front = pygame.Surface((400, 400))
hv.render_view(front, front.get_rect(), hv.Camera())
side_cam = hv.Camera()
side_cam.angle = 90.0
side = pygame.Surface((400, 400))
hv.render_view(side, side.get_rect(), side_cam)
changed = sum(1 for y in range(0, 400, 4) for x in range(0, 400, 4)
              if front.get_at((x, y)) != side.get_at((x, y)))
truth("many pixels differ after a 90 deg turn", changed > 400)

left_hand = hv.project_point(cam, (0.278, 0.80, 0.0))
side_hand = hv.project_point(side_cam, (0.278, 0.80, 0.0))
truth("a hand projects to a different spot", abs(left_hand[0] - side_hand[0]) > 20)

print("--- the skeleton is drawn, upright, in a window-sized viewport ---")
view = pygame.Surface((hv.VIEWPORT.width, hv.VIEWPORT.height))
hv.render_view(view, view.get_rect(), hv.Camera())
bone = 0
top_bone = None
min_x, max_x = 10 ** 9, -1
for y in range(0, view.get_height(), 2):
    for x in range(0, view.get_width(), 2):
        r, g, b = view.get_at((x, y))[:3]
        if r > g > b and r > 70 and r - b > 6:       # warm ivory bone tone
            bone += 1
            min_x, max_x = min(min_x, x), max(max_x, x)
            if top_bone is None:
                top_bone = y
check("bone pixels found", bone > 400, True)
check("head is in the upper half", top_bone is not None and top_bone < 190, True)
check("figure is roughly centred", abs((min_x + max_x) / 2 - view.get_width() / 2) < 60, True)

print("--- skeleton and posing ---")
hv.reset_pose()
rest = hv.pose_mesh()


def dist(a, b):
    d = hv.sub(a, b)
    return math.sqrt(hv.dot(d, d))


need = {"torso", "head", "shoulderL", "elbowL", "wristL", "hipR", "kneeR", "ankleR"}
check("skeleton bones present", need <= set(hv.SKELETON), True)

hv.reset_pose()
hv.pose_mesh()
hand0 = hv.SKELETON["wristL"].m_tip
head0 = hv.SKELETON["head"].m_pos
hv.rotate_joint("elbowL", (1.0, 0.0, 0.0), math.radians(80))
posed = hv.pose_mesh()
truth("bending the elbow moves the hand",
      dist(hv.SKELETON["wristL"].m_tip, hand0) > 0.1)
truth("bending the elbow leaves the head still",
      dist(hv.SKELETON["head"].m_pos, head0) < 1e-9)
check("face count unchanged by posing", len(posed), len(rest))

hv.reset_pose()
hv.pose_mesh()
elbow0 = hv.SKELETON["elbowL"].m_pos
wrist0 = hv.SKELETON["wristL"].m_pos
hv.rotate_joint("shoulderL", (0.0, 0.0, 1.0), math.radians(60))
hv.pose_mesh()
truth("shoulder rotation carries the elbow",
      dist(hv.SKELETON["elbowL"].m_pos, elbow0) > 0.05)
truth("shoulder rotation carries the wrist",
      dist(hv.SKELETON["wristL"].m_pos, wrist0) > 0.1)
truth("shoulder rotation leaves the hip still",
      dist(hv.SKELETON["hipL"].m_pos, hv.SKELETON["hipL"].pivot) < 1e-9)

hv.reset_pose()
hv.pose_mesh()
project = hv.make_projector(hv.Camera(), hv.VIEWPORT)
sp = project(hv.SKELETON["kneeR"].m_pos)
picked = hv.pick_joint(hv.Camera(), sp, hv.VIEWPORT)
check("clicking a joint picks that joint", picked.name if picked else None, "kneeR")
far = hv.pick_joint(hv.Camera(), (hv.VIEWPORT.x + 2, hv.VIEWPORT.y + 2),
                    hv.VIEWPORT)
check("clicking empty space picks nothing", far, None)

hv.rotate_joint("shoulderR", (0.0, 1.0, 0.0), 1.2)
hv.rotate_joint("hipL", (1.0, 0.0, 0.0), -0.7)
hv.pose_mesh()
hv.reset_pose()
back = hv.pose_mesh()
truth("reset restores the rest pose",
      all(abs(a - b) < 1e-9 for fa, fb in zip(rest, back)
          for pa, pb in zip(fa[0], fb[0]) for a, b in zip(pa, pb)))


class _Viewer(hv.Viewer):
    def __init__(self):
        hv.Viewer.__init__(self)
        self.screen = pygame.Surface(hv.WINDOW)


v = _Viewer()
hv.reset_pose()
v.faces = hv.pose_mesh()
proj = hv.make_projector(v.cam, hv.VIEWPORT)
start = proj(hv.SKELETON["kneeL"].m_pos)
down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                          pos=(int(start[0]), int(start[1])))
v.handle(down)
truth("mouse-down on a joint grabs it", v.dragging is not None)
knee0 = hv.SKELETON["kneeL"].m_tip
move = pygame.event.Event(pygame.MOUSEMOTION,
                          pos=(int(start[0]) + 60, int(start[1]) + 20))
v.handle(move)
truth("dragging swings the lower leg",
      dist(hv.SKELETON["kneeL"].m_tip, knee0) > 0.05)
end = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1,
                         pos=(int(start[0]) + 60, int(start[1]) + 20))
v.handle(end)
truth("mouse-up releases the joint", v.dragging is None)
v.on_reset()
truth("reset button clears the pose", v.selected is None and v.dragging is None)

print("--- model import ---")
_tmp = Path(tempfile.mkdtemp(prefix="hv_test_"))
(_tmp / "tri.mtl").write_text("newmtl green\nKd 0.1 0.8 0.2\n", encoding="utf-8")
(_tmp / "tri.obj").write_text(
    "mtllib tri.mtl\n"
    "v 0 0 0\nv 2 0 0\nv 0 2 0\nv 0 0 4\n"
    "usemtl green\nf 1 2 3\nf 1 2 4\nf 2 3 4\n",
    encoding="utf-8")
faces, summary = mi.load_model(str(_tmp / "tri.obj"))
check("obj faces parsed", len(faces), 3)
check("obj material colour read", faces[0][1], (0.1, 0.8, 0.2))
truth("obj summary mentions faces", "faces" in summary)

fitted = mi.fit_to_view(faces)
fp = [p for face, _ in fitted for p in face]
xs2, ys2, zs2 = zip(*fp)
span = max(max(xs2) - min(xs2), max(ys2) - min(ys2), max(zs2) - min(zs2))
check("fit scales the model", round(span, 2), mi.FIT_SIZE)
check("fit puts feet on the floor", round(min(ys2), 3), 0.0)

v.faces, v.custom = fitted, True
v.draw_frame()                       # an imported mesh must render without error
green = any(px[1] > px[0] + 30 and px[1] > px[2] + 30
            for px in (v.screen.get_at((x, y))
                       for x in range(0, hv.VIEWPORT.width, 4)
                       for y in range(0, hv.VIEWPORT.height, 4)))
truth("imported model renders in its material colour", green)
click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(400, 200))
v.handle(click)
truth("import disables joint posing (orbits instead)", v.dragging is None)
v.on_use_skeleton()
truth("skeleton restored", not v.custom and len(v.faces) == len(hv.HUMAN))
shutil.rmtree(_tmp, ignore_errors=True)

print("--- Photoshop hand-off ---")
running = hv.photoshop_running()
if running:
    cam.angle = 120.0
    ok, msg = hv.send_to_photoshop(cam)
    check("send succeeded", ok, True)
    print("      ", msg)
    check("illustration document present", "illustration:" in msg, True)
    check("png imported as a layer", "layer:" in msg, True)
    close_photoshop_viewport()
    print("       illustration document closed again")
elif running is False:
    print("skipped - Photoshop is not running")
else:
    print("skipped - pywin32 is not installed")

if failures:
    print("\n%d FAILURES: %s" % (len(failures), failures))
    sys.exit(1)
print("\nall checks passed")
