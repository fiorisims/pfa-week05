"""Spiral Generator - a live-updating Maya GUI for the cube spiral.

    python maya_bridge.py spiral_gui.py

Every control updates the scene immediately while you drag it (no Apply button).
State lives in the scene - `spiral_cube_*` transforms plus one `spiral_color_*`
material per cube - so re-running the script adopts whatever is already there.

Controls: radius start/end, turns, height, cube size, cube count, colour mode
(gradient / alternating / solid), the two gradient colours, gradient cycles.
"""

import math

import maya.cmds as cmds

WINDOW_NAME = "spiral_generator_window"
GROUP = "spiral_cubes"
MAX_CUBES = 150

DT = {
    "radius0": 3.0,
    "radius1": 14.0,
    "turns": 4.0,
    "height": 40.0,
    "size": 1.6,
    "count": 48,
    "mode": "Alternate",
    "colorA": (0.10, 0.35, 0.95),
    "colorB": (0.98, 0.35, 0.65),
    "cycles": 1,
}
W = {}


def cube_name(i):
    return "spiral_cube_%03d" % i


def mat_name(i):
    return "spiral_color_%03d" % i


def index_of(name):
    try:
        return int(name.rsplit("_", 1)[-1])
    except ValueError:
        return 0


def get_cubes():
    found = cmds.ls("spiral_cube_*", type="transform") or []
    return sorted(found, key=lambda n: (index_of(n), n))


def normalize():
    """Rename every cube (old 2-digit names from create_spiral.py included) to the
    canonical `spiral_cube_000` form, via temp names so renames can never collide."""
    cubes = (cmds.ls("spiral_cube_*", type="transform") or []) + \
            (cmds.ls("spiral_tmp_*", type="transform") or [])
    cubes = sorted(set(cubes), key=lambda n: (index_of(n), n))
    staged = [cmds.rename(c, "spiral_tmp_%04d" % i) for i, c in enumerate(cubes)]
    for i, c in enumerate(staged):
        cmds.rename(c, cube_name(i))


def ensure_mat(i):
    """Lambert + shading group for cube i; returns (material, shading group)."""
    mat = mat_name(i)
    if not cmds.objExists(mat):
        cmds.shadingNode("lambert", asShader=True, name=mat)
    sg = mat + "SG"
    if not cmds.objExists(sg):
        cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=sg)
        cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)
    return mat, sg


def adopt(cubes):
    """Give every existing cube its index material (forceElement unassigns others)."""
    for i, cube in enumerate(cubes):
        mat, sg = ensure_mat(i)
        shapes = cmds.listRelatives(cube, shapes=True) or []
        if not shapes:
            continue
        members = cmds.sets(sg, q=True) or []
        if shapes[0] not in members:
            cmds.sets(shapes[0], e=True, forceElement=sg)


def ensure_count(n):
    """Create/delete cubes so exactly n exist. Returns (cubes, created)."""
    cubes = get_cubes()
    created = []
    while len(cubes) < n and len(created) < MAX_CUBES:
        i = len(cubes)
        new = cmds.polyCube(name=cube_name(i), width=1.0, height=1.0, depth=1.0)[0]
        mat, sg = ensure_mat(i)
        shapes = cmds.listRelatives(new, shapes=True) or []
        if shapes:
            cmds.sets(shapes[0], e=True, forceElement=sg)
        created.append(new)
        cubes = get_cubes()

    cubes = get_cubes()
    while len(cubes) > n:
        victim = cubes[-1]
        idx = len(cubes) - 1          # position == material index after normalize()
        cmds.delete(victim)
        for node in (mat_name(idx), mat_name(idx) + "SG"):
            if cmds.objExists(node):
                cmds.delete(node)
        cubes = get_cubes()
    return get_cubes(), created


def color_at(i, n, p):
    a, b = p["colorA"], p["colorB"]
    mode = p["mode"]
    if mode == "Solid":
        return a
    if mode == "Alternate":
        return a if i % 2 == 0 else b
    t = i / float(n - 1) if n > 1 else 0.0
    x = (t * p["cycles"]) % 2.0
    u = x if x <= 1.0 else 2.0 - x          # triangle wave: A->B->A per cycle
    return tuple(a[k] + (b[k] - a[k]) * u for k in range(3))


def read_values():
    if not W:
        return dict(DT)
    v = dict(DT)
    v["radius0"] = cmds.floatSliderGrp(W["radius0"], q=True, value=True)
    v["radius1"] = cmds.floatSliderGrp(W["radius1"], q=True, value=True)
    v["turns"] = cmds.floatSliderGrp(W["turns"], q=True, value=True)
    v["height"] = cmds.floatSliderGrp(W["height"], q=True, value=True)
    v["size"] = cmds.floatSliderGrp(W["size"], q=True, value=True)
    v["count"] = cmds.intSliderGrp(W["count"], q=True, value=True)
    v["cycles"] = cmds.intSliderGrp(W["cycles"], q=True, value=True)
    v["mode"] = cmds.optionMenu(W["mode"], q=True, value=True)
    v["colorA"] = tuple(cmds.colorSliderGrp(W["colorA"], q=True, rgb=True))
    v["colorB"] = tuple(cmds.colorSliderGrp(W["colorB"], q=True, rgb=True))
    return v


def update(*_):
    """Rebuild the spiral from the current control values."""
    p = read_values()
    if "cycles" in W:
        try:
            cmds.control(W["cycles"], e=True, enable=p["mode"] == "Gradient")
        except Exception:
            pass

    cmds.undoInfo(openChunk=True, chunkName="spiral_gui")
    try:
        cubes, created = ensure_count(int(p["count"]))
        if cubes:
            if not cmds.objExists(GROUP):
                cmds.group(cubes, name=GROUP)
            elif created:
                cmds.parent(created, GROUP)

        n = len(cubes)
        for i, cube in enumerate(cubes):
            t = i / float(n - 1) if n > 1 else 0.0
            angle = t * p["turns"] * math.tau
            radius = p["radius0"] + (p["radius1"] - p["radius0"]) * t
            pos = (math.cos(angle) * radius,
                   t * p["height"],
                   math.sin(angle) * radius)
            cmds.xform(cube, ws=True, t=pos,
                       ro=(0.0, math.degrees(angle), 0.0),
                       s=(p["size"], p["size"], p["size"]))
            mat, _ = ensure_mat(i)
            cmds.setAttr(mat + ".color", *color_at(i, n, p), type="double3")
    finally:
        cmds.undoInfo(closeChunk=True)
    return len(get_cubes())


def rebuild(*_):
    delete_spiral(silent=True)
    update()


def delete_spiral(silent=False):
    cmds.undoInfo(openChunk=True, chunkName="spiral_delete")
    try:
        for cube in get_cubes() + (cmds.ls("spiral_tmp_*", type="transform") or []):
            if cmds.objExists(cube):
                cmds.delete(cube)
        for node in cmds.ls("spiral_color_*") or []:
            if cmds.objExists(node):
                cmds.delete(node)
        if cmds.objExists(GROUP):
            cmds.delete(GROUP)
    finally:
        cmds.undoInfo(closeChunk=True)
    if not silent:
        print("spiral deleted")


def build_gui():
    seed = dict(DT)
    old_window = cmds.window(WINDOW_NAME, exists=True)
    if old_window:
        try:
            seed.update(read_values())       # keep the user's settings across re-runs
        except Exception:
            pass
    if get_cubes():
        seed["count"] = len(get_cubes())
    if old_window:
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(WINDOW_NAME, title="Spiral Generator", sizeable=True,
                widthHeight=(370, 470))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5,
                      columnAttach=("both", 10))

    def slider(label, key, mn, mx, step=0.1):
        W[key] = cmds.floatSliderGrp(label=label, field=True, min=mn, max=mx,
                                     value=seed[key], step=step,
                                     dragCommand=update, changeCommand=update)

    cmds.text(label="Spiral", font="boldLabelFont", align="left")
    slider("Radius start", "radius0", 0.0, 50.0)
    slider("Radius end", "radius1", 0.0, 50.0)
    slider("Turns", "turns", 0.25, 12.0, step=0.25)
    slider("Height", "height", 0.0, 120.0, step=1.0)
    slider("Cube size", "size", 0.1, 8.0, step=0.05)

    cmds.separator(height=7, style="in")
    cmds.text(label="Cubes", font="boldLabelFont", align="left")
    W["count"] = cmds.intSliderGrp(label="Count", field=True, min=1, max=MAX_CUBES,
                                   value=seed["count"], step=1,
                                   dragCommand=update, changeCommand=update)

    cmds.separator(height=7, style="in")
    cmds.text(label="Colours", font="boldLabelFont", align="left")
    W["mode"] = cmds.optionMenu(label="Mode", changeCommand=update)
    for lbl in ("Gradient", "Alternate", "Solid"):
        cmds.menuItem(label=lbl)
    cmds.optionMenu(W["mode"], e=True,
                    value=seed["mode"] if seed["mode"] in
                    ("Gradient", "Alternate", "Solid") else "Alternate")
    W["colorA"] = cmds.colorSliderGrp(label="Color A", rgb=seed["colorA"],
                                      dragCommand=update, changeCommand=update)
    W["colorB"] = cmds.colorSliderGrp(label="Color B", rgb=seed["colorB"],
                                      dragCommand=update, changeCommand=update)
    W["cycles"] = cmds.intSliderGrp(label="Gradient cycles", field=True,
                                    min=1, max=8, value=seed["cycles"], step=1,
                                    dragCommand=update, changeCommand=update)

    cmds.separator(height=7, style="in")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(175, 175))
    cmds.button(label="Rebuild", command=rebuild)
    cmds.button(label="Delete Spiral", command=delete_spiral)
    cmds.setParent("..")

    cmds.showWindow(WINDOW_NAME)
    normalize()
    adopt(get_cubes())
    update()
    return WINDOW_NAME


try:
    cmds._spiral_gui = {"update": update, "read": read_values, "build": build_gui,
                        "delete": delete_spiral, "rebuild": rebuild,
                        "widgets": W, "defaults": DT}
except Exception:
    pass

window = build_gui()
print("opened", window, "with", len(get_cubes()), "cubes")
__result__ = {"window": window, "cubes": len(get_cubes()), "controls": len(W)}
